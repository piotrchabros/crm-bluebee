"""Slug + access-token helpers, ported 1:1 from bluebee-website `Offers.ts`.

Kept in their own module so they can be unit-tested without the ORM.
"""

import base64
import re
import secrets
import unicodedata

# Number of random bytes behind an access token. Source uses 6 → 8 url-safe
# chars. This is the ONLY guard on a public offer link, so do not lower it.
ACCESS_TOKEN_BYTES = 6
ACCESS_TOKEN_LEN = 8


def generate_access_token() -> str:
    """Random 8-char lowercase [a-z0-9] token.

    Mirrors source: randomBytes(6).base64url.toLowerCase, strip non-alnum,
    take 8, pad with 'x'. `secrets` (CSPRNG) is used, not `random`.
    """
    raw = base64.urlsafe_b64encode(secrets.token_bytes(ACCESS_TOKEN_BYTES)).decode("ascii")
    cleaned = re.sub(r"[^a-z0-9]", "", raw.lower())[:ACCESS_TOKEN_LEN]
    return cleaned.ljust(ACCESS_TOKEN_LEN, "x")


def slugify(value: str) -> str:
    """ASCII slug, mirroring source `slugify` (incl. the Polish ł→l rule).

    lowercase → NFKD strip diacritics → ł→l → non-alnum runs to '-' → trim '-'.
    """
    value = (value or "").lower()
    value = value.replace("ł", "l")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")
