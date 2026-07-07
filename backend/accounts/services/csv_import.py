"""CSV import for companies (accounts).

Two-phase: `parse_and_validate` reads + validates a CSV without writing to the
DB beyond read-only lookups; `commit_rows` writes inside a transaction. Both
phases re-run validation so the commit endpoint is safe even if called
directly.

Scope (this iteration): **core company fields only** — no assignees, teams,
tags, or linked contacts. Mirrors `contacts/services/csv_import.py` with a
smaller surface.

Duplicate policy (per org):
  * name — hard error. `Account` has a per-org case-insensitive unique
           constraint (`unique_account_name_per_org`); we mirror it in the
           importer so users see a clean row-level message instead of an
           IntegrityError at commit. A row whose name matches an existing
           account, or an earlier row in the same file, is rejected.

All duplicate lookups are scoped to the caller's org (one SELECT) so a
malicious CSV cannot reach across tenants.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import URLValidator
from django.db import IntegrityError, transaction
from django.db.models.functions import Lower

from accounts.models import Account
from common.utils import COUNTRIES, CURRENCY_CODES, INDCHOICES


REQUIRED_HEADERS = ("name",)
OPTIONAL_HEADERS = (
    "email",
    "phone",
    "website",
    "industry",
    "number_of_employees",
    "annual_revenue",
    "currency",
    "address_line",
    "city",
    "state",
    "postcode",
    "country",
    "description",
)
KNOWN_HEADERS = REQUIRED_HEADERS + OPTIONAL_HEADERS

MAX_ROWS = 5000
NAME_MAX_LEN = 255
POSTCODE_MAX_LEN = 64
# Account.annual_revenue = DecimalField(max_digits=15, decimal_places=2)
REVENUE_MAX_DIGITS = 15
REVENUE_DECIMAL_PLACES = 2
REVENUE_MAX_INT_DIGITS = REVENUE_MAX_DIGITS - REVENUE_DECIMAL_PLACES  # 13

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[\d\s\-\(\)\+\.]{7,25}$")
_url_validator = URLValidator(schemes=("http", "https"))

COUNTRY_CODES = {code.upper() for code, _label in COUNTRIES}
CURRENCY_CODE_SET = {code.upper() for code, _label in CURRENCY_CODES}
# Industry codes carry spaces/ampersands (e.g. "APPAREL & ACCESSORIES"); match
# case-insensitively and resolve back to the canonical stored code.
INDUSTRY_BY_LOWER = {code.lower(): code for code, _label in INDCHOICES}


@dataclass
class RowError:
    row: int  # 1-based, matching CSV line numbers (header is row 0)
    field: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"row": self.row, "field": self.field, "message": self.message}


@dataclass
class ValidatedRow:
    """A row that passed validation; values coerced to their stored form."""

    row: int
    name: str
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    industry: str | None = None
    number_of_employees: int | None = None
    annual_revenue: Decimal | None = None
    currency: str | None = None
    address_line: str | None = None
    city: str | None = None
    state: str | None = None
    postcode: str | None = None
    country: str | None = None
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "row": self.row,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "website": self.website,
            "industry": self.industry,
            "number_of_employees": self.number_of_employees,
            # Decimal is not JSON-serializable; render as a string for the UI.
            "annual_revenue": (
                str(self.annual_revenue) if self.annual_revenue is not None else None
            ),
            "currency": self.currency,
            "address_line": self.address_line,
            "city": self.city,
            "state": self.state,
            "postcode": self.postcode,
            "country": self.country,
            "description": self.description,
        }


@dataclass
class ImportResult:
    valid: list[ValidatedRow]
    errors: list[RowError]
    header_error: str | None = None

    @property
    def summary(self) -> dict[str, int]:
        return {
            "total": len(self.valid) + len({e.row for e in self.errors}),
            "valid": len(self.valid),
            "invalid": len({e.row for e in self.errors}),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "header_error": self.header_error,
            "valid": [r.to_dict() for r in self.valid],
            "errors": [e.to_dict() for e in self.errors],
            "summary": self.summary,
        }


def _decode(file_bytes: bytes) -> str | None:
    """Decode CSV bytes as UTF-8 (with or without BOM).

    Return None for non-UTF-8 so the caller can surface a "save as UTF-8"
    header_error rather than producing mojibake that passes validation.
    """
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return file_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def _normalize_headers(raw_headers: Iterable[str]) -> list[str]:
    return [(h or "").strip().lower() for h in raw_headers]


def _existing_names(parsed: list[tuple[int, dict[str, str]]], org) -> set[str]:
    """Lowercased names of accounts that already exist in `org`.

    One SELECT, scoped to `org`, restricted to the names actually referenced in
    the file so it stays cheap regardless of tenant size.
    """
    candidate_names = {
        record["name"].lower()
        for _idx, record in parsed
        if record.get("name")
    }
    if not candidate_names:
        return set()
    return set(
        Account.objects.filter(org=org)
        .annotate(name_lower=Lower("name"))
        .filter(name_lower__in=candidate_names)
        .values_list("name_lower", flat=True)
    )


def _parse_int(raw: str) -> tuple[int | None, str | None]:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None, "Must be a whole number"
    if value < 0:
        return None, "Must be zero or a positive number"
    return value, None


def _parse_decimal(raw: str) -> tuple[Decimal | None, str | None]:
    # Tolerate a thousands separator or currency spacing the user may paste.
    cleaned = raw.replace(" ", "").replace(",", "")
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None, "Must be a number"
    if not value.is_finite():
        return None, "Must be a finite number"
    if value < 0:
        return None, "Must be zero or a positive number"
    exponent = value.as_tuple().exponent
    if isinstance(exponent, int) and exponent < -REVENUE_DECIMAL_PLACES:
        return None, f"At most {REVENUE_DECIMAL_PLACES} decimal places"
    # Integer-part digit budget (max_digits - decimal_places).
    if value >= Decimal(10) ** REVENUE_MAX_INT_DIGITS:
        return None, f"Value is too large (max {REVENUE_MAX_INT_DIGITS} digits before the decimal)"
    return value, None


def parse_and_validate(file_bytes: bytes, org) -> ImportResult:
    """Parse a CSV byte string and validate every row against the given org.

    All duplicate lookups are scoped to `org` so a malicious CSV cannot reach
    across tenants.
    """
    text = _decode(file_bytes)
    if text is None:
        return ImportResult(
            valid=[],
            errors=[],
            header_error="File could not be decoded as UTF-8. Save your CSV as UTF-8 and try again.",
        )
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return ImportResult(valid=[], errors=[], header_error="CSV is empty")

    headers = _normalize_headers(rows[0])
    missing = [h for h in REQUIRED_HEADERS if h not in headers]
    if missing:
        return ImportResult(
            valid=[],
            errors=[],
            header_error=f"Missing required header(s): {', '.join(missing)}",
        )
    unknown = [h for h in headers if h and h not in KNOWN_HEADERS]
    if unknown:
        return ImportResult(
            valid=[],
            errors=[],
            header_error=f"Unknown header(s): {', '.join(unknown)}",
        )

    data_rows = rows[1:]
    if len(data_rows) > MAX_ROWS:
        return ImportResult(
            valid=[],
            errors=[],
            header_error=f"Too many rows ({len(data_rows)}); limit is {MAX_ROWS}",
        )

    # First pass: parse each row into a dict and skip blank rows.
    parsed: list[tuple[int, dict[str, str]]] = []
    for idx, raw_row in enumerate(data_rows, start=1):
        if not any((cell or "").strip() for cell in raw_row):
            continue
        record = {
            h: (raw_row[i].strip() if i < len(raw_row) else "")
            for i, h in enumerate(headers)
        }
        parsed.append((idx, record))

    existing = _existing_names(parsed, org)

    valid: list[ValidatedRow] = []
    errors: list[RowError] = []
    seen_names: dict[str, int] = {}  # name.lower() -> row number

    for idx, record in parsed:
        row_errors, validated = _validate_and_build(idx, record, existing, seen_names)
        if row_errors:
            errors.extend(row_errors)
            continue
        valid.append(validated)
        seen_names[validated.name.lower()] = idx

    return ImportResult(valid=valid, errors=errors)


def _validate_and_build(
    idx: int,
    record: dict,
    existing_names: set[str],
    seen_names: dict[str, int],
) -> tuple[list[RowError], ValidatedRow | None]:
    """Validate a single row and, on success, return the resolved ValidatedRow."""
    errors: list[RowError] = []

    name = record.get("name", "")
    if not name:
        errors.append(RowError(idx, "name", "Company name is required"))
    elif len(name) > NAME_MAX_LEN:
        errors.append(RowError(idx, "name", f"Name exceeds {NAME_MAX_LEN} characters"))
    else:
        name_lower = name.lower()
        prior = seen_names.get(name_lower)
        if prior:
            errors.append(
                RowError(idx, "name", f"Duplicate name also used by row {prior} in this file")
            )
        elif name_lower in existing_names:
            errors.append(
                RowError(idx, "name", "A company with this name already exists in your organization")
            )

    email = record.get("email", "")
    if email and not EMAIL_RE.match(email):
        errors.append(RowError(idx, "email", f"'{email}' is not a valid email"))

    phone = record.get("phone", "")
    if phone and not PHONE_RE.match(phone):
        errors.append(
            RowError(
                idx,
                "phone",
                "Phone must be 7-25 characters of digits and separators (+ - ( ) . space)",
            )
        )

    website = record.get("website", "")
    if website:
        try:
            _url_validator(website)
        except DjangoValidationError:
            errors.append(
                RowError(idx, "website", "Must be a valid URL starting with http:// or https://")
            )

    industry_raw = record.get("industry", "")
    industry: str | None = None
    if industry_raw:
        industry = INDUSTRY_BY_LOWER.get(industry_raw.strip().lower())
        if industry is None:
            errors.append(
                RowError(idx, "industry", f"'{industry_raw}' is not a known industry")
            )

    employees_raw = record.get("number_of_employees", "")
    number_of_employees: int | None = None
    if employees_raw:
        number_of_employees, err = _parse_int(employees_raw)
        if err:
            errors.append(RowError(idx, "number_of_employees", err))

    revenue_raw = record.get("annual_revenue", "")
    annual_revenue: Decimal | None = None
    if revenue_raw:
        annual_revenue, err = _parse_decimal(revenue_raw)
        if err:
            errors.append(RowError(idx, "annual_revenue", err))

    currency_raw = record.get("currency", "")
    currency: str | None = None
    if currency_raw:
        currency = currency_raw.strip().upper()
        if currency not in CURRENCY_CODE_SET:
            errors.append(
                RowError(idx, "currency", f"'{currency_raw}' is not a supported currency code")
            )
            currency = None

    country_raw = record.get("country", "")
    country: str | None = None
    if country_raw:
        country = country_raw.strip().upper()
        if country not in COUNTRY_CODES:
            errors.append(
                RowError(idx, "country", f"'{country_raw}' is not a known country code")
            )
            country = None

    for length_field in ("address_line", "city", "state"):
        val = record.get(length_field, "")
        if val and len(val) > NAME_MAX_LEN:
            errors.append(RowError(idx, length_field, f"Exceeds {NAME_MAX_LEN} characters"))

    postcode = record.get("postcode", "")
    if postcode and len(postcode) > POSTCODE_MAX_LEN:
        errors.append(RowError(idx, "postcode", f"Exceeds {POSTCODE_MAX_LEN} characters"))

    if errors:
        return errors, None

    return [], ValidatedRow(
        row=idx,
        name=name,
        email=email or None,
        phone=phone or None,
        website=website or None,
        industry=industry,
        number_of_employees=number_of_employees,
        annual_revenue=annual_revenue,
        currency=currency,
        address_line=record.get("address_line") or None,
        city=record.get("city") or None,
        state=record.get("state") or None,
        postcode=postcode or None,
        country=country,
        description=record.get("description") or None,
    )


def commit_rows(file_bytes: bytes, org, profile) -> dict[str, Any]:
    """Re-parse the uploaded CSV and create accounts in a single transaction.

    Any invalid row blocks the whole batch (users fix the file first). An
    IntegrityError race (a same-named account created between preview and
    commit by another request) is caught and reported as a 400-equivalent
    payload so the user sees an actionable message instead of a generic 500.
    """
    result = parse_and_validate(file_bytes, org)
    if result.header_error:
        return {"error": True, "header_error": result.header_error, "created": 0}
    if result.errors:
        return {
            "error": True,
            "message": "Fix the invalid rows before importing",
            "errors": [e.to_dict() for e in result.errors],
            "created": 0,
        }

    try:
        return _commit_validated(result.valid, org, profile)
    except IntegrityError as exc:
        return {
            "error": True,
            "message": (
                "A company was created concurrently that conflicts with this "
                "import (likely a duplicate name). Re-run preview and try again."
            ),
            "detail": str(exc),
            "created": 0,
        }


@transaction.atomic
def _commit_validated(rows: list[ValidatedRow], org, profile) -> dict[str, Any]:
    created_ids: list[str] = []

    for vr in rows:
        account = Account.objects.create(
            name=vr.name,
            email=vr.email,
            phone=vr.phone,
            website=vr.website,
            industry=vr.industry,
            number_of_employees=vr.number_of_employees,
            annual_revenue=vr.annual_revenue,
            currency=vr.currency,
            address_line=vr.address_line,
            city=vr.city,
            state=vr.state,
            postcode=vr.postcode,
            country=vr.country,
            description=vr.description,
            org=org,
            created_by=profile.user,
        )
        created_ids.append(str(account.id))

    return {"error": False, "created": len(created_ids), "ids": created_ids}
