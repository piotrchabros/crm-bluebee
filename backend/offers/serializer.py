import copy

from rest_framework import serializers

from offers.models import Offer
from offers.pricing import expand_standard_ab


class OfferSerializer(serializers.ModelSerializer):
    """Internal (authenticated) representation of an offer."""

    url = serializers.SerializerMethodField()

    class Meta:
        model = Offer
        fields = (
            "id",
            "client_name",
            "title",
            "brand",
            "status",
            "slug",
            "access_token",
            "url",
            "offer_data",
            "value",
            "valid_until",
            "sent_at",
            "viewed_at",
            "responded_at",
            "notes",
            "opportunity",
            "created_at",
        )
        read_only_fields = fields

    def get_url(self, obj):
        return obj.public_path


class PublicOfferSerializer(serializers.ModelSerializer):
    """Public representation — only what the rendered offer page needs.

    Deliberately omits org, notes, value, tracking timestamps, opportunity, id.
    """

    offer_data = serializers.SerializerMethodField()
    branding = serializers.SerializerMethodField()

    class Meta:
        model = Offer
        fields = ("slug", "brand", "client_name", "title", "status", "offer_data", "branding")
        read_only_fields = fields

    def get_branding(self, obj):
        """Per-org branding for the renderer (Feature 5): theme, accent, contacts,
        and a token-scoped public logo URL when the org has a logo."""
        from offers.branding import org_branding

        b = org_branding(obj.org)
        logo_url = None
        if b["has_logo"]:
            logo_url = f"/api/public/offers/{obj.slug}/{obj.access_token}/logo/"
        return {
            "theme": b["theme"],
            "accent": b["accent"],
            "company_name": b["company_name"],
            "email": b["email"],
            "website": b["site"],
            "prepared_by": b["prepared_by"],
            "logo_url": logo_url,
        }

    def get_offer_data(self, obj):
        """Return offer_data with every `pricing` block's `standard-ab` preset
        expanded server-side, so the renderer stays a dumb view of one canonical
        layout (single source of truth = offers.pricing)."""
        data = copy.deepcopy(obj.offer_data or {})
        for section in data.get("sections", []):
            if isinstance(section, dict) and section.get("type") == "pricing":
                section["expanded"] = expand_standard_ab(
                    section.get("valueA", 20000),
                    section.get("subscription", 1000),
                    section.get("minutes", 1000),
                    estimated=section.get("estimated", False),
                    note=section.get("note"),
                )
        return data
