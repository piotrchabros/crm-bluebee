"""Thin client for the BlueBee AI offer-generation API (https://bluebee.marketing).

All offer generation/editing logic lives on the BlueBee side. This module is a
backend-only proxy: it attaches the secret `x-api-key` (never exposed to the
frontend) and forwards requests. See `bottlecrm-integration-agent.md` for the
API contract.
"""

from __future__ import annotations

import requests
from django.conf import settings


class OfferAPIError(Exception):
    """Raised when the BlueBee offers API returns a non-2xx response.

    `status_code` carries the upstream HTTP status so the view can map it back
    to the client; `detail` is a human-readable message.
    """

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"BlueBee offers API {status_code}: {detail}")


class OfferTimeout(Exception):
    """Raised when the BlueBee offers API does not respond within the timeout."""


def _headers() -> dict:
    return {
        "x-api-key": settings.BLUEBEE_OFFERS_API_KEY,
        "Content-Type": "application/json",
    }


def _post(path: str, payload: dict) -> dict:
    if not settings.BLUEBEE_OFFERS_API_KEY:
        raise OfferAPIError(503, "BLUEBEE_OFFERS_API_KEY is not configured on the server.")
    url = f"{settings.BLUEBEE_OFFERS_BASE_URL.rstrip('/')}{path}"
    try:
        resp = requests.post(
            url,
            json=payload,
            headers=_headers(),
            timeout=settings.BLUEBEE_OFFERS_TIMEOUT,
        )
    except requests.Timeout as exc:
        raise OfferTimeout() from exc
    except requests.RequestException as exc:
        raise OfferAPIError(502, f"Could not reach BlueBee offers API: {exc}") from exc

    if resp.status_code != 200:
        # Surface upstream detail (BlueBee returns text or JSON) without leaking the key.
        detail = resp.text[:500] if resp.text else f"HTTP {resp.status_code}"
        raise OfferAPIError(resp.status_code, detail)
    try:
        return resp.json()
    except ValueError as exc:
        raise OfferAPIError(502, "BlueBee offers API returned malformed JSON.") from exc


def create_offer(
    *,
    brand: str,
    client_name: str,
    brief: str,
    title: str | None = None,
    value=None,
    valid_until: str | None = None,
    status: str = "sent",
) -> dict:
    """Create an offer. Returns {id, slug, accessToken, brand, url}."""
    payload = {
        "brand": brand,
        "clientName": client_name,
        "brief": brief,
        "status": status,
    }
    if title:
        payload["title"] = title
    if value is not None:
        payload["value"] = value
    if valid_until:
        payload["validUntil"] = valid_until
    return _post("/api/offers/create", payload)


def edit_offer(offer_id: int, instruction: str) -> dict:
    """Apply a natural-language edit to an existing offer. Returns {id, url, offerData}."""
    return _post(f"/api/offers/{offer_id}/edit", {"instruction": instruction})
