"""Gemini configuration for the offer generator (Task 11.2).

Model is pinned in one place with a stable fallback so a preview-model rename or
outage does not break production. Values are overridable via env/settings.
"""

from django.conf import settings

# `gemini-3-flash-preview` is what the source pins. It is a PREVIEW model and can
# be renamed/removed without notice — hence the fallback below.
PRIMARY_MODEL = getattr(settings, "GEMINI_MODEL", None) or "gemini-3-flash-preview"
# Stable GA model used if the primary errors/unavailable.
FALLBACK_MODEL = getattr(settings, "GEMINI_FALLBACK_MODEL", None) or "gemini-2.5-flash"
MODELS = [PRIMARY_MODEL, FALLBACK_MODEL]

MAX_OUTPUT_TOKENS = int(getattr(settings, "GEMINI_MAX_OUTPUT_TOKENS", 16384))


def api_key() -> str:
    return getattr(settings, "GEMINI_API_KEY", "") or ""
