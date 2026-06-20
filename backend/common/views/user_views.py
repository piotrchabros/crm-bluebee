from collections import defaultdict

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer

from rest_framework import serializers, status
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from cases.models import Case
from cases.serializer import CaseSerializer
from common import swagger_params
from common.models import Comment, Org, Profile, Teams, User
from common.serializer import (
    BillingAddressSerializer,
    CommentSerializer,
    CreateProfileSerializer,
    CreateUserSerializer,
    ProfileSerializer,
    TeamsSerializer,
    UserCreateSwaggerSerializer,
    UserUpdateStatusSwaggerSerializer,
)
from common.tasks import send_email_user_delete
from common.utils import COUNTRIES, ROLES
from contacts.models import Contact
from contacts.serializer import ContactSerializer
from opportunity.models import Opportunity
from opportunity.serializer import OpportunitySerializer


class GetTeamsAndUsersView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["users"],
        parameters=swagger_params.organization_params,
        responses={
            200: inline_serializer(
                name="TeamsAndUsersResponse",
                fields={
                    "teams": TeamsSerializer(many=True),
                    "profiles": ProfileSerializer(many=True),
                },
            )
        },
    )
    def get(self, request, *args, **kwargs):
        data = {}
        teams = Teams.objects.filter(org=request.profile.org).order_by("-id")
        teams_data = TeamsSerializer(teams, many=True).data
        profiles = Profile.objects.filter(
            is_active=True, org=request.profile.org
        ).order_by("user__email")
        profiles_data = ProfileSerializer(profiles, many=True).data
        data["teams"] = teams_data
        data["profiles"] = profiles_data
        return Response(data)


class UsersListView(APIView, LimitOffsetPagination):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["users"],
        parameters=swagger_params.organization_params,
        request=UserCreateSwaggerSerializer,
        responses={
            201: inline_serializer(
                name="UserCreateResponse",
                fields={
                    "error": serializers.BooleanField(),
                    "message": serializers.CharField(),
                },
            )
        },
    )
    def post(self, request, format=None):
        if self.request.profile.role != "ADMIN" and not self.request.user.is_superuser:
            return Response(
                {"error": True, "errors": "Permission Denied"},
                status=status.HTTP_403_FORBIDDEN,
            )
        params = request.data
        if not params:
            return Response(
                {"error": True, "errors": "Invalid request"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Resolve the target organization. Defaults to the caller's current org
        # (taken from the signed JWT) unless an explicit `org_id` is supplied.
        target_org = request.profile.org
        org_id = params.get("org_id")
        if org_id and str(org_id) != str(request.profile.org_id):
            try:
                target_org = Org.objects.get(id=org_id)
            except (Org.DoesNotExist, ValidationError, ValueError):
                return Response(
                    {"error": True, "errors": "Organization not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            # To write into a different org the caller must be a superuser, or
            # hold an active admin profile in that target org.
            is_target_admin = (
                Profile.objects.filter(
                    user=request.user, org=target_org, is_active=True
                )
                .filter(Q(role="ADMIN") | Q(is_organization_admin=True))
                .exists()
            )
            if not request.user.is_superuser and not is_target_admin:
                return Response(
                    {
                        "error": True,
                        "errors": "You are not an admin of the target organization",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Email is globally unique on User, but a person can belong to several
        # orgs via separate Profile rows. If the email already maps to a User we
        # reuse it and only create a new Profile in the target org — bypassing
        # CreateUserSerializer, whose ModelSerializer UniqueValidator would
        # otherwise reject any existing email outright.
        email = (params.get("email") or "").strip()
        existing_user = (
            User.objects.filter(email__iexact=email).first() if email else None
        )

        address_serializer = BillingAddressSerializer(data=params)
        profile_serializer = CreateProfileSerializer(data=params)
        user_serializer = None
        data = {}
        if existing_user:
            if Profile.objects.filter(user=existing_user, org=target_org).exists():
                data["user_errors"] = {
                    "email": ["User already belongs to this organization."]
                }
        else:
            user_serializer = CreateUserSerializer(data=params, org=target_org)
            if not user_serializer.is_valid():
                data["user_errors"] = dict(user_serializer.errors)
        if not profile_serializer.is_valid():
            data["profile_errors"] = profile_serializer.errors
        if not address_serializer.is_valid():
            data["address_errors"] = (address_serializer.errors,)
        if data:
            return Response(
                {"error": True, "errors": data},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            # The `address` table is RLS-protected: a row only inserts when its
            # org_id matches the session's `app.current_org` (set by middleware
            # to the caller's current org). When creating into a different org
            # we point that context at the target org for this transaction so
            # the insert passes the policy. `is_local=true` reverts it on commit.
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('app.current_org', %s, true)",
                    [str(target_org.id)],
                )
            address_obj = address_serializer.save(org=target_org)
            if existing_user:
                user = existing_user
            else:
                user = user_serializer.save(is_active=True)
            Profile.objects.create(
                user=user,
                date_of_joining=timezone.now(),
                role=params.get("role"),
                address=address_obj,
                org=target_org,
            )
        return Response(
            {
                "error": False,
                "message": "User Created Successfully",
                "org_id": str(target_org.id),
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        tags=["users"],
        parameters=swagger_params.user_list_params,
        responses={
            200: inline_serializer(
                name="UsersListResponse",
                fields={
                    "active_users": serializers.DictField(),
                    "inactive_users": serializers.DictField(),
                    "admin_email": serializers.CharField(),
                    "roles": serializers.ListField(),
                    "status": serializers.ListField(),
                },
            )
        },
    )
    def get(self, request, format=None):
        # Check if profile exists and user has permission
        if not self.request.profile:
            return Response(
                {"error": True, "errors": "Organization context required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if self.request.profile.role != "ADMIN" and not self.request.user.is_superuser:
            return Response(
                {"error": True, "errors": "Permission Denied"},
                status=status.HTTP_403_FORBIDDEN,
            )
        queryset = Profile.objects.filter(org=request.profile.org).order_by("-id")
        params = request.query_params
        if params:
            if params.get("email"):
                queryset = queryset.filter(user__email__icontains=params.get("email"))
            if params.get("role"):
                queryset = queryset.filter(role=params.get("role"))
            if params.get("status"):
                queryset = queryset.filter(is_active=params.get("status"))

        context = {}
        queryset_active_users = queryset.filter(is_active=True)
        results_active_users = self.paginate_queryset(
            queryset_active_users.distinct(), self.request, view=self
        )
        active_users = ProfileSerializer(results_active_users, many=True).data
        self._attach_organizations(results_active_users, active_users)
        if results_active_users:
            offset = queryset_active_users.filter(
                id__gte=results_active_users[-1].id
            ).count()
            if offset == queryset_active_users.count():
                offset = None
        else:
            offset = 0
        context["active_users"] = {
            "active_users_count": self.count,
            "active_users": active_users,
            "offset": offset,
        }

        queryset_inactive_users = queryset.filter(is_active=False)
        results_inactive_users = self.paginate_queryset(
            queryset_inactive_users.distinct(), self.request, view=self
        )
        inactive_users = ProfileSerializer(results_inactive_users, many=True).data
        self._attach_organizations(results_inactive_users, inactive_users)
        if results_inactive_users:
            offset = queryset_inactive_users.filter(
                id__gte=results_inactive_users[-1].id
            ).count()
            if offset == queryset_inactive_users.count():
                offset = None
        else:
            offset = 0
        context["inactive_users"] = {
            "inactive_users_count": self.count,
            "inactive_users": inactive_users,
            "offset": offset,
        }

        context["admin_email"] = settings.ADMIN_EMAIL
        context["roles"] = ROLES
        context["status"] = [("True", "Active"), ("False", "In Active")]
        return Response(context)

    @staticmethod
    def _attach_organizations(profile_objs, serialized_rows):
        """Add an `organizations` list to each serialized row listing every org
        the user belongs to (across all orgs, since a user can hold a Profile in
        many). `profile_objs` and `serialized_rows` are parallel/ordered. The
        `profile` table is not RLS-restricted, so the cross-org lookup is one
        extra query regardless of the caller's current org context.
        """
        user_ids = [p.user_id for p in profile_objs]
        if not user_ids:
            return
        org_map = defaultdict(list)
        memberships = (
            Profile.objects.filter(user_id__in=user_ids, is_active=True)
            .select_related("org")
            .order_by("org__name")
        )
        for m in memberships:
            org_map[m.user_id].append(
                {"id": str(m.org_id), "name": m.org.name, "role": m.role}
            )
        for prof, row in zip(profile_objs, serialized_rows):
            row["organizations"] = org_map.get(prof.user_id, [])


class UserDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    def get_object(self, pk):
        # Security fix: Filter by org to prevent cross-org enumeration
        # Lookup by user ID since frontend sends user.id, not profile.id
        return get_object_or_404(Profile, user__id=pk, org=self.request.profile.org)

    @extend_schema(
        tags=["users"],
        parameters=swagger_params.organization_params,
        responses={
            200: inline_serializer(
                name="UserDetailResponse",
                fields={
                    "error": serializers.BooleanField(),
                    "data": serializers.DictField(),
                },
            )
        },
    )
    def get(self, request, pk, format=None):
        profile_obj = self.get_object(pk)
        if (
            self.request.profile.role != "ADMIN"
            and not self.request.profile.is_admin
            and self.request.profile.id != profile_obj.id
        ):
            return Response(
                {"error": True, "errors": "Permission Denied"},
                status=status.HTTP_403_FORBIDDEN,
            )
        # Org check now handled by get_object_or_404 in get_object()
        assigned_data = Profile.objects.filter(
            org=request.profile.org, is_active=True
        ).values("id", "user__email")
        context = {}
        context["profile_obj"] = ProfileSerializer(profile_obj).data
        # Security fix: Add org filter to prevent cross-org data leakage
        opportunity_list = Opportunity.objects.filter(
            assigned_to=profile_obj, org=request.profile.org
        )
        context["opportunity_list"] = OpportunitySerializer(
            opportunity_list, many=True
        ).data
        contacts = Contact.objects.filter(
            assigned_to=profile_obj, org=request.profile.org
        )
        context["contacts"] = ContactSerializer(contacts, many=True).data
        cases = Case.objects.filter(assigned_to=profile_obj, org=request.profile.org)
        context["cases"] = CaseSerializer(cases, many=True).data
        context["assigned_data"] = assigned_data
        comments = Comment.objects.filter(commented_by=profile_obj, org=request.profile.org)
        context["comments"] = CommentSerializer(comments, many=True).data
        context["countries"] = COUNTRIES
        return Response(
            {"error": False, "data": context},
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=["users"],
        parameters=swagger_params.organization_params,
        request=UserCreateSwaggerSerializer,
        responses={
            200: inline_serializer(
                name="UserUpdateResponse",
                fields={
                    "error": serializers.BooleanField(),
                    "message": serializers.CharField(),
                },
            )
        },
    )
    def put(self, request, pk, format=None):
        params = request.data
        profile = self.get_object(pk)
        address_obj = profile.address
        if (
            self.request.profile.role != "ADMIN"
            and not self.request.user.is_superuser
            and self.request.profile.id != profile.id
        ):
            return Response(
                {"error": True, "errors": "Permission Denied"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if profile.org != request.profile.org:
            return Response(
                {"error": True, "errors": "User company doesnot match with header...."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = CreateUserSerializer(
            data=params, instance=profile.user, org=request.profile.org
        )
        address_serializer = BillingAddressSerializer(data=params, instance=address_obj)
        profile_serializer = CreateProfileSerializer(data=params, instance=profile)
        data = {}
        if not serializer.is_valid():
            data["contact_errors"] = serializer.errors
        if not address_serializer.is_valid():
            data["address_errors"] = (address_serializer.errors,)
        if not profile_serializer.is_valid():
            data["profile_errors"] = (profile_serializer.errors,)
        if data:
            data["error"] = True
            return Response(
                data,
                status=status.HTTP_400_BAD_REQUEST,
            )
        if address_serializer.is_valid():
            address_obj = address_serializer.save(org=request.profile.org)
            user = serializer.save()
            user.email = user.email
            user.save()
        if profile_serializer.is_valid():
            profile = profile_serializer.save()
            return Response(
                {"error": False, "message": "User Updated Successfully"},
                status=status.HTTP_200_OK,
            )
        return Response(
            {"error": True, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @extend_schema(
        tags=["users"],
        parameters=swagger_params.organization_params,
        request=UserCreateSwaggerSerializer,
        description="Partial User Update",
        responses={
            200: inline_serializer(
                name="UserPatchResponse",
                fields={
                    "error": serializers.BooleanField(),
                    "message": serializers.CharField(),
                },
            )
        },
    )
    def patch(self, request, pk, format=None):
        """Handle partial updates to a user."""
        params = request.data
        profile = self.get_object(pk)
        if (
            self.request.profile.role != "ADMIN"
            and not self.request.user.is_superuser
            and self.request.profile.id != profile.id
        ):
            return Response(
                {"error": True, "errors": "Permission Denied"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if profile.org != request.profile.org:
            return Response(
                {
                    "error": True,
                    "errors": "User company does not match with header....",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CreateUserSerializer(
            data=params, instance=profile.user, org=request.profile.org, partial=True
        )
        profile_serializer = CreateProfileSerializer(
            data=params, instance=profile, partial=True
        )
        data = {}
        if not serializer.is_valid():
            data["contact_errors"] = serializer.errors
        if not profile_serializer.is_valid():
            data["profile_errors"] = profile_serializer.errors
        if data:
            data["error"] = True
            return Response(data, status=status.HTTP_400_BAD_REQUEST)

        if serializer.is_valid():
            serializer.save()
        if profile_serializer.is_valid():
            profile = profile_serializer.save()
            return Response(
                {"error": False, "message": "User Updated Successfully"},
                status=status.HTTP_200_OK,
            )
        return Response(
            {"error": True, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @extend_schema(
        tags=["users"],
        parameters=swagger_params.organization_params,
        responses={
            200: inline_serializer(
                name="UserDeleteResponse", fields={"status": serializers.CharField()}
            )
        },
    )
    def delete(self, request, pk, format=None):
        if self.request.profile.role != "ADMIN" and not self.request.profile.is_admin:
            return Response(
                {"error": True, "errors": "Permission Denied"},
                status=status.HTTP_403_FORBIDDEN,
            )
        self.object = self.get_object(pk)
        if self.object.id == request.profile.id:
            return Response(
                {"error": True, "errors": "Permission Denied"},
                status=status.HTTP_403_FORBIDDEN,
            )
        deleted_by = self.request.profile.user.email
        send_email_user_delete.delay(
            self.object.user.email,
            deleted_by=deleted_by,
        )
        self.object.delete()
        return Response({"status": "success"}, status=status.HTTP_200_OK)


class UserStatusView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["users"],
        description="User Status View",
        parameters=swagger_params.organization_params,
        request=UserUpdateStatusSwaggerSerializer,
        responses={
            200: inline_serializer(
                name="UserStatusResponse",
                fields={
                    "active_profiles": ProfileSerializer(many=True),
                    "inactive_profiles": ProfileSerializer(many=True),
                },
            )
        },
    )
    def post(self, request, pk, format=None):
        if self.request.profile.role != "ADMIN" and not self.request.user.is_superuser:
            return Response(
                {
                    "error": True,
                    "errors": "You do not have permission to perform this action",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        params = request.data
        profiles = Profile.objects.filter(org=request.profile.org)
        # Lookup by user ID since frontend sends user.id, not profile.id
        profile = profiles.get(user__id=pk)

        if params.get("status"):
            user_status = params.get("status")
            if user_status == "Active":
                profile.is_active = True
            elif user_status == "Inactive":
                profile.is_active = False
            else:
                return Response(
                    {"error": True, "errors": "Please enter Valid Status for user"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            profile.save()

        context = {}
        active_profiles = profiles.filter(is_active=True)
        inactive_profiles = profiles.filter(is_active=False)
        context["active_profiles"] = ProfileSerializer(active_profiles, many=True).data
        context["inactive_profiles"] = ProfileSerializer(
            inactive_profiles, many=True
        ).data
        return Response(context)
