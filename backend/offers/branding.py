"""Per-org offer branding (Feature 5).

`org_branding(org)` collapses an Org's branding-relevant fields into the dict the
AI prompt and the public renderer consume. label / prepared_by fall back to
company_name → name so an offer always has a sane signer.
"""

from __future__ import annotations


def org_branding(org) -> dict:
    company = (getattr(org, "company_name", "") or "").strip()
    name = (getattr(org, "name", "") or "").strip()
    label = company or name or "Nasza firma"
    prepared_by = (getattr(org, "offer_prepared_by", "") or "").strip() or label
    return {
        "label": label,
        "company_name": label,
        "email": (getattr(org, "email", "") or "").strip(),
        "site": (getattr(org, "website", "") or "").strip(),
        "prepared_by": prepared_by,
        "theme": getattr(org, "offer_theme", "") or "dark",
        "accent": getattr(org, "offer_accent", "") or "#E3FF04",
        "has_logo": bool(getattr(org, "logo", None)),
    }
