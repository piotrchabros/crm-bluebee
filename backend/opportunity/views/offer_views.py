"""Opportunity → offer generation (Feature 4 cutover, Task 12.3).

Post-cutover these call the NATIVE generator (`offers.services`) in-process
instead of the external bluebee.marketing proxy. Request/response shapes are
unchanged so the existing "Generator Oferty" UI keeps working; the only
difference is `offer_url` now points at the CRM's own /oferta/ pages.
"""

from django.conf import settings
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import HasOrgContext
from offers.ai import OfferGenerationError
from offers.services import create_offer, edit_offer
from opportunity.models import Opportunity


def _public_url(offer) -> str:
    base = getattr(settings, "OFFERS_PUBLIC_BASE_URL", "").rstrip("/")
    return f"{base}{offer.public_path}"


class _OfferViewMixin:
    permission_classes = (IsAuthenticated, HasOrgContext)

    def get_object(self, pk):
        return Opportunity.objects.filter(id=pk, org=self.request.profile.org).first()


@extend_schema(tags=["Opportunities"])
class OpportunityGenerateOfferView(_OfferViewMixin, APIView):
    """POST /api/opportunities/<pk>/generate-offer/ — generate a native offer."""

    @extend_schema(
        operation_id="opportunities_generate_offer",
        request=None,
        responses={
            200: inline_serializer(
                name="GenerateOfferResponse",
                fields={
                    "url": serializers.CharField(),
                    "id": serializers.CharField(),
                },
            )
        },
    )
    def post(self, request, pk, format=None):
        opp = self.get_object(pk)
        if opp is None:
            return Response({"detail": "Opportunity not found"}, status=status.HTTP_404_NOT_FOUND)

        brief = (opp.description or "").strip()
        if len(brief) < 20:
            return Response(
                {"detail": "Uzupełnij opis klienta (Notes, min. 20 znaków) przed wygenerowaniem oferty."},
                status=400,
            )

        client_name = (opp.account.name if opp.account else None) or opp.name

        try:
            offer = create_offer(
                request.profile.org,
                client_name=client_name,
                brief=brief,
                title=f"Asystent głosowy AI - {client_name}",
                value=opp.amount,
                valid_until=opp.closed_on,
                status="sent",
                opportunity=opp,
            )
        except OfferGenerationError as exc:
            opp.offer_status = "error"
            opp.save(update_fields=["offer_status"])
            return Response({"detail": f"Generowanie nie powiodło się: {exc}"}, status=422)

        opp.generated_offer = offer
        opp.offer_url = _public_url(offer)
        opp.offer_status = "generated"
        opp.save(update_fields=["generated_offer", "offer_url", "offer_status"])
        return Response({"url": opp.offer_url, "id": str(offer.id)})


@extend_schema(tags=["Opportunities"])
class OpportunityEditOfferView(_OfferViewMixin, APIView):
    """POST /api/opportunities/<pk>/edit-offer/ — natural-language offer edit."""

    @extend_schema(
        operation_id="opportunities_edit_offer",
        request=inline_serializer(
            name="EditOfferRequest", fields={"instruction": serializers.CharField()}
        ),
        responses={200: inline_serializer(name="EditOfferResponse", fields={"url": serializers.CharField()})},
    )
    def post(self, request, pk, format=None):
        opp = self.get_object(pk)
        if opp is None:
            return Response({"detail": "Opportunity not found"}, status=status.HTTP_404_NOT_FOUND)
        if not opp.generated_offer:
            if opp.offer_id:
                return Response(
                    {"detail": "Ta oferta pochodzi ze starego systemu — wygeneruj ją ponownie."},
                    status=400,
                )
            return Response({"detail": "Najpierw wygeneruj ofertę."}, status=400)
        instruction = (request.data.get("instruction") or "").strip()
        if len(instruction) < 3:
            return Response({"detail": "Wpisz, co zmienić."}, status=400)

        try:
            offer = edit_offer(opp.generated_offer, instruction)
        except OfferGenerationError as exc:
            return Response({"detail": f"Edycja nie powiodła się: {exc}"}, status=422)

        opp.offer_url = _public_url(offer)
        opp.save(update_fields=["offer_url"])
        return Response({"url": opp.offer_url})
