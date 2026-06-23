"""
Common validators for CRM models.
"""

import os
import re

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _


# E.164 format: +[country code][number] (max 15 digits total)
# Examples: +12025551234, +442071234567
e164_phone_validator = RegexValidator(
    regex=r"^\+[1-9]\d{1,14}$",
    message=_("Phone must be in E.164 format (e.g., +12025551234)"),
)

# Flexible phone format allowing common separators
# Allows: digits, spaces, dashes, parentheses, plus sign
# Examples: +1 (202) 555-1234, 202-555-1234, +44 20 7123 4567
flexible_phone_validator = RegexValidator(
    regex=r"^[\d\s\-\(\)\+\.]{7,25}$",
    message=_(
        "Enter a valid phone number (7-25 characters, digits and separators only)"
    ),
)


def normalize_phone(phone: str) -> str:
    """
    Normalize a phone number by removing all non-digit characters.
    Returns the last 10 digits for comparison purposes.
    """
    if not phone:
        return ""
    digits_only = re.sub(r"[^\d]", "", phone)
    # Return last 10 digits for normalized comparison
    return digits_only[-10:] if len(digits_only) >= 10 else digits_only


# --- Attachment file validation -------------------------------------------
# Server-authoritative limits for files attached to CRM records
# (leads, contacts, accounts, opportunities, cases). The frontend mirrors
# these for fast feedback, but this is the trust boundary. See spec.md
# "Feature: File Attachments on CRM records".

# 10 MB
MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024

# Common business document / image / archive types. Executables and scripts
# are intentionally excluded.
ALLOWED_ATTACHMENT_EXTENSIONS = frozenset(
    {
        "pdf",
        "doc",
        "docx",
        "xls",
        "xlsx",
        "ppt",
        "pptx",
        "csv",
        "txt",
        "png",
        "jpg",
        "jpeg",
        "gif",
        "webp",
        "zip",
    }
)


def validate_attachment_file(value):
    """Validate an uploaded attachment's size and extension.

    Raises ``django.core.exceptions.ValidationError`` when the file is too
    large or has a disallowed extension. Usable both as a model/serializer
    field validator and as a direct call before saving an ``Attachments`` row.
    """
    if value is None:
        return

    # Read size defensively: a freshly uploaded file exposes its size in
    # memory, but reading .size on a committed FieldFile hits storage and can
    # raise if the file is absent (e.g. fixtures referencing missing files).
    # We only want to enforce the limit on actual uploads.
    try:
        size = value.size
    except (FileNotFoundError, OSError, ValueError):
        size = None
    if size is not None and size > MAX_ATTACHMENT_SIZE:
        max_mb = MAX_ATTACHMENT_SIZE // (1024 * 1024)
        raise ValidationError(
            _("File too large. Maximum size is %(max)d MB.") % {"max": max_mb}
        )

    name = getattr(value, "name", "") or ""
    ext = os.path.splitext(name)[1].lower().lstrip(".")
    if ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_ATTACHMENT_EXTENSIONS))
        raise ValidationError(
            _("File type '.%(ext)s' is not allowed. Allowed types: %(allowed)s.")
            % {"ext": ext or "?", "allowed": allowed}
        )
