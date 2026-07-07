"""Offer endpoints.

Internal (authenticated, org-scoped): create / edit / get — Task 12.1.
Public (unauthenticated, slug+token): render-data + view tracking — Task 12.2.
"""

from django.http import FileResponse, Http404
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import HasOrgContext
from offers.ai import OfferGenerationError
from offers.models import Offer
from offers.serializer import OfferSerializer, PublicOfferSerializer
from offers.services import create_offer, edit_offer, mark_viewed

BRANDS = {"bluebee", "bespoke"}

# User-agent fragments that should NOT count as a genuine human view.
_BOT_UA = (
    "bot", "crawler", "spider", "preview", "facebookexternalhit", "slackbot",
    "whatsapp", "telegrambot", "twitterbot", "discordbot", "embedly", "pinterest",
    "linkedinbot", "google-read-aloud", "headless",
)


class _OrgScopedMixin:
    permission_classes = (IsAuthenticated, HasOrgContext)

    def get_object(self, pk):
        return Offer.objects.filter(id=pk, org=self.request.profile.org).first()


@extend_schema(tags=["Offers"])
class OfferListCreateView(_OrgScopedMixin, APIView):
    """GET list / POST create (generate) an offer for the caller's org."""

    def get(self, request, format=None):
        qs = Offer.objects.filter(org=request.profile.org).order_by("-created_at")[:200]
        return Response(OfferSerializer(qs, many=True).data)

    @extend_schema(
        request=inline_serializer(
            name="OfferCreateRequest",
            fields={
                "client_name": serializers.CharField(),
                "brief": serializers.CharField(),
                "title": serializers.CharField(required=False),
                "value": serializers.DecimalField(max_digits=12, decimal_places=2, required=False),
                "valid_until": serializers.DateField(required=False),
                "status": serializers.ChoiceField(choices=["draft", "sent"], required=False),
                "opportunity": serializers.UUIDField(required=False),
            },
        ),
        responses={201: OfferSerializer},
    )
    def post(self, request, format=None):
        # Branding (incl. theme/contacts) comes from the caller's org — no brand input.
        data = request.data
        client_name = (data.get("client_name") or "").strip()
        if len(client_name) < 2:
            return Response({"detail": "client_name jest wymagane (min. 2 znaki)."}, status=400)
        brief = (data.get("brief") or "").strip()
        if len(brief) < 20:
            return Response({"detail": "brief jest za krótki (min. 20 znaków)."}, status=400)

        opportunity = None
        opp_id = data.get("opportunity")
        if opp_id:
            from opportunity.models import Opportunity

            opportunity = Opportunity.objects.filter(
                id=opp_id, org=request.profile.org
            ).first()

        try:
            offer = create_offer(
                request.profile.org,
                client_name=client_name,
                brief=brief,
                title=data.get("title"),
                value=data.get("value"),
                valid_until=data.get("valid_until"),
                status=data.get("status") or "sent",
                opportunity=opportunity,
            )
        except OfferGenerationError as exc:
            return Response({"detail": f"Generowanie nie powiodło się: {exc}"}, status=422)

        return Response(OfferSerializer(offer).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Offers"])
class OfferDetailView(_OrgScopedMixin, APIView):
    """GET a single offer (org-scoped)."""

    def get(self, request, pk, format=None):
        offer = self.get_object(pk)
        if offer is None:
            return Response({"detail": "Offer not found"}, status=404)
        return Response(OfferSerializer(offer).data)


@extend_schema(tags=["Offers"])
class OfferEditView(_OrgScopedMixin, APIView):
    """POST a natural-language edit to an offer."""

    @extend_schema(
        request=inline_serializer(
            name="OfferEditRequest",
            fields={"instruction": serializers.CharField()},
        ),
        responses={200: OfferSerializer},
    )
    def post(self, request, pk, format=None):
        offer = self.get_object(pk)
        if offer is None:
            return Response({"detail": "Offer not found"}, status=404)
        instruction = (request.data.get("instruction") or "").strip()
        if len(instruction) < 3:
            return Response({"detail": "Wpisz, co zmienić."}, status=400)
        try:
            offer = edit_offer(offer, instruction)
        except OfferGenerationError as exc:
            return Response({"detail": f"Edycja nie powiodła się: {exc}"}, status=422)
        return Response(OfferSerializer(offer).data)


@extend_schema(tags=["Offers"])
class PublicOfferView(APIView):
    """GET /api/public/offers/<slug>/<token>/ — unauthenticated render data.

    slug is globally unique → look it up, then constant-time compare the token.
    A wrong/absent token returns 404 (no enumeration signal). First genuine view
    flips draft/sent → viewed (skipped for previews and bots).
    """

    permission_classes = (AllowAny,)
    authentication_classes = ()

    def get(self, request, slug, token, format=None):
        import hmac

        offer = Offer.objects.filter(slug=slug).first()
        if offer is None or not hmac.compare_digest(offer.access_token or "", token or ""):
            return Response({"detail": "Not found"}, status=404)

        if request.query_params.get("preview") != "1" and not self._is_bot(request):
            mark_viewed(offer)

        return Response(PublicOfferSerializer(offer).data)

    @staticmethod
    def _is_bot(request) -> bool:
        ua = (request.META.get("HTTP_USER_AGENT") or "").lower()
        return any(frag in ua for frag in _BOT_UA)


@extend_schema(tags=["Offers"])
class PublicOfferLogoView(APIView):
    """GET /api/public/offers/<slug>/<token>/logo/ — stream the org logo.

    Token-scoped (same slug+token guard as the offer) so a public offer page can
    show its org's logo without exposing the auth-gated media volume.
    """

    permission_classes = (AllowAny,)
    authentication_classes = ()

    def get(self, request, slug, token, format=None):
        import hmac

        offer = Offer.objects.filter(slug=slug).first()
        if offer is None or not hmac.compare_digest(offer.access_token or "", token or ""):
            raise Http404
        logo = getattr(offer.org, "logo", None)
        if not logo:
            raise Http404
        try:
            return FileResponse(logo.open("rb"))
        except (FileNotFoundError, ValueError):
            raise Http404
