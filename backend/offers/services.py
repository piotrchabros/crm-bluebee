"""Service layer for offer generation.

Used by both the offers API endpoints (12.1) and — after cutover (12.3) — the
Opportunity generate/edit views. Calling in-process avoids a self-HTTP hop.
"""

from __future__ import annotations

from django.utils import timezone

from offers.ai import apply_edit_to_offer_data, brief_to_offer_data
from offers.branding import org_branding
from offers.models import Offer


def create_offer(
    org,
    *,
    client_name: str,
    brief: str,
    title: str | None = None,
    value=None,
    valid_until=None,
    status: str = "sent",
    opportunity=None,
) -> Offer:
    """Generate offer_data from a brief (using the org's branding) and persist."""
    branding = org_branding(org)
    offer_data = brief_to_offer_data(brief, branding, client_name)
    offer = Offer(
        org=org,
        client_name=client_name,
        title=(title or "").strip() or f"Asystent głosowy AI - {client_name}",
        offer_data=offer_data,
        status="sent" if status == "sent" else "draft",
        value=value,
        valid_until=valid_until,
        opportunity=opportunity,
    )
    if offer.status == "sent":
        offer.sent_at = timezone.now()
    offer.save()
    return offer


def edit_offer(offer: Offer, instruction: str) -> Offer:
    """Apply a natural-language edit to an existing offer's offer_data."""
    offer.offer_data = apply_edit_to_offer_data(offer.offer_data, instruction)
    offer.save(update_fields=["offer_data", "updated_at"])
    return offer


def mark_viewed(offer: Offer) -> bool:
    """Flip draft/sent → viewed on first genuine view. Returns True if changed."""
    if offer.status in ("draft", "sent"):
        offer.status = "viewed"
        offer.viewed_at = timezone.now()
        offer.save(update_fields=["status", "viewed_at", "updated_at"])
        return True
    return False
