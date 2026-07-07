"""Tests for the accounts (company) CSV import endpoints (preview + commit).

Scope this iteration: core company fields only; name is the dedup key.

Edge cases the policy specifically targets:
  * name dup vs DB and within-file (DB-enforced case-insensitive unique per org)
  * choice-field validation (industry / currency / country)
  * numeric validation (number_of_employees int, annual_revenue decimal)
  * per-org isolation (a name in another org must not block this org)
  * permission gate (non-admin user blocked)
"""

import csv
import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import Account


def _csv(headers: list[str], rows: list[list[str]]) -> SimpleUploadedFile:
    """Build an in-memory CSV upload from header + row lists."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return SimpleUploadedFile(
        "accounts.csv",
        buf.getvalue().encode("utf-8"),
        content_type="text/csv",
    )


@pytest.fixture
def existing_account(org_a, admin_user):
    """A company already in org_a — used for vs-DB duplicate tests."""
    return Account.objects.create(name="Acme Corp", org=org_a, created_by=admin_user)


@pytest.mark.django_db
class TestImportPreview:
    def test_happy_path_coerces_fields(self, admin_client, org_a, admin_profile):
        csv_file = _csv(
            [
                "name", "email", "phone", "website", "industry",
                "number_of_employees", "annual_revenue", "currency",
                "address_line", "city", "state", "postcode", "country",
                "description",
            ],
            [[
                "Globex", "info@globex.test", "+1 555 111 2222",
                "https://globex.test", "banking", "42", "1234567.50", "pln",
                "1 Main St", "Metropolis", "NY", "00-123", "us", "A note",
            ]],
        )
        response = admin_client.post(
            "/api/accounts/import/preview/", {"file": csv_file}, format="multipart"
        )
        assert response.status_code == 200, response.json()
        body = response.json()
        assert body["header_error"] is None
        assert body["summary"] == {"total": 1, "valid": 1, "invalid": 0}
        row = body["valid"][0]
        assert row["name"] == "Globex"
        assert row["industry"] == "BANKING"          # case-insensitive → stored code
        assert row["currency"] == "PLN"
        assert row["country"] == "US"
        assert row["number_of_employees"] == 42
        assert row["annual_revenue"] == "1234567.50"  # Decimal rendered as string
        # Preview must not write anything
        assert Account.objects.filter(org=org_a).count() == 0

    def test_missing_required_header(self, admin_client, admin_profile):
        csv_file = _csv(["email"], [["a@b.test"]])
        response = admin_client.post(
            "/api/accounts/import/preview/", {"file": csv_file}, format="multipart"
        )
        assert response.status_code == 200
        body = response.json()
        assert "name" in (body["header_error"] or "")

    def test_unknown_header_rejected(self, admin_client, admin_profile):
        csv_file = _csv(["name", "totally_made_up"], [["A", "x"]])
        response = admin_client.post(
            "/api/accounts/import/preview/", {"file": csv_file}, format="multipart"
        )
        body = response.json()
        assert body["header_error"] and "totally_made_up" in body["header_error"]

    def test_name_duplicate_vs_db(self, admin_client, existing_account, admin_profile):
        csv_file = _csv(["name"], [["Acme Corp"]])
        response = admin_client.post(
            "/api/accounts/import/preview/", {"file": csv_file}, format="multipart"
        )
        body = response.json()
        assert body["summary"]["invalid"] == 1
        assert {(e["row"], e["field"]) for e in body["errors"]} == {(1, "name")}

    def test_name_duplicate_case_insensitive_vs_db(
        self, admin_client, existing_account, admin_profile
    ):
        csv_file = _csv(["name"], [["acme corp"]])
        response = admin_client.post(
            "/api/accounts/import/preview/", {"file": csv_file}, format="multipart"
        )
        body = response.json()
        assert body["summary"]["invalid"] == 1

    def test_name_duplicate_within_file(self, admin_client, admin_profile):
        csv_file = _csv(["name"], [["Dup Co"], ["dup co"]])
        response = admin_client.post(
            "/api/accounts/import/preview/", {"file": csv_file}, format="multipart"
        )
        body = response.json()
        assert body["summary"]["valid"] == 1
        assert body["summary"]["invalid"] == 1
        err = body["errors"][0]
        assert err["row"] == 2 and err["field"] == "name"
        assert "row 1" in err["message"]

    def test_name_in_other_org_does_not_block(
        self, admin_client, org_b, user_b, admin_profile
    ):
        # Same name exists only in org_b → org_a import must succeed.
        Account.objects.create(name="Shared Name", org=org_b, created_by=user_b)
        csv_file = _csv(["name"], [["Shared Name"]])
        response = admin_client.post(
            "/api/accounts/import/preview/", {"file": csv_file}, format="multipart"
        )
        body = response.json()
        assert body["summary"] == {"total": 1, "valid": 1, "invalid": 0}

    def test_name_too_long(self, admin_client, admin_profile):
        csv_file = _csv(["name"], [["x" * 256]])
        response = admin_client.post(
            "/api/accounts/import/preview/", {"file": csv_file}, format="multipart"
        )
        body = response.json()
        assert body["summary"]["invalid"] == 1
        assert any(e["field"] == "name" for e in body["errors"])

    def test_invalid_email(self, admin_client, admin_profile):
        csv_file = _csv(["name", "email"], [["A", "not-an-email"]])
        body = admin_client.post(
            "/api/accounts/import/preview/", {"file": csv_file}, format="multipart"
        ).json()
        assert any(e["field"] == "email" for e in body["errors"])

    def test_invalid_phone(self, admin_client, admin_profile):
        csv_file = _csv(["name", "phone"], [["A", "abc"]])
        body = admin_client.post(
            "/api/accounts/import/preview/", {"file": csv_file}, format="multipart"
        ).json()
        assert any(e["field"] == "phone" for e in body["errors"])

    def test_invalid_website(self, admin_client, admin_profile):
        csv_file = _csv(["name", "website"], [["A", "globex.test"]])
        body = admin_client.post(
            "/api/accounts/import/preview/", {"file": csv_file}, format="multipart"
        ).json()
        assert any(e["field"] == "website" for e in body["errors"])

    def test_invalid_industry(self, admin_client, admin_profile):
        csv_file = _csv(["name", "industry"], [["A", "TELEPORTATION"]])
        body = admin_client.post(
            "/api/accounts/import/preview/", {"file": csv_file}, format="multipart"
        ).json()
        assert any(e["field"] == "industry" for e in body["errors"])

    def test_invalid_currency(self, admin_client, admin_profile):
        csv_file = _csv(["name", "currency"], [["A", "ZZZ"]])
        body = admin_client.post(
            "/api/accounts/import/preview/", {"file": csv_file}, format="multipart"
        ).json()
        assert any(e["field"] == "currency" for e in body["errors"])

    def test_invalid_country(self, admin_client, admin_profile):
        csv_file = _csv(["name", "country"], [["A", "ZZ"]])
        body = admin_client.post(
            "/api/accounts/import/preview/", {"file": csv_file}, format="multipart"
        ).json()
        assert any(e["field"] == "country" for e in body["errors"])

    def test_invalid_employees_negative(self, admin_client, admin_profile):
        csv_file = _csv(["name", "number_of_employees"], [["A", "-5"]])
        body = admin_client.post(
            "/api/accounts/import/preview/", {"file": csv_file}, format="multipart"
        ).json()
        assert any(e["field"] == "number_of_employees" for e in body["errors"])

    def test_invalid_employees_non_integer(self, admin_client, admin_profile):
        csv_file = _csv(["name", "number_of_employees"], [["A", "12.5"]])
        body = admin_client.post(
            "/api/accounts/import/preview/", {"file": csv_file}, format="multipart"
        ).json()
        assert any(e["field"] == "number_of_employees" for e in body["errors"])

    def test_invalid_revenue_negative(self, admin_client, admin_profile):
        csv_file = _csv(["name", "annual_revenue"], [["A", "-1"]])
        body = admin_client.post(
            "/api/accounts/import/preview/", {"file": csv_file}, format="multipart"
        ).json()
        assert any(e["field"] == "annual_revenue" for e in body["errors"])

    def test_invalid_revenue_too_many_decimals(self, admin_client, admin_profile):
        csv_file = _csv(["name", "annual_revenue"], [["A", "1.234"]])
        body = admin_client.post(
            "/api/accounts/import/preview/", {"file": csv_file}, format="multipart"
        ).json()
        assert any(e["field"] == "annual_revenue" for e in body["errors"])

    def test_invalid_revenue_too_large(self, admin_client, admin_profile):
        csv_file = _csv(["name", "annual_revenue"], [["A", "1" * 14]])
        body = admin_client.post(
            "/api/accounts/import/preview/", {"file": csv_file}, format="multipart"
        ).json()
        assert any(e["field"] == "annual_revenue" for e in body["errors"])

    def test_revenue_with_thousands_separators_accepted(
        self, admin_client, admin_profile
    ):
        csv_file = _csv(["name", "annual_revenue"], [["A", "1,234,567.50"]])
        body = admin_client.post(
            "/api/accounts/import/preview/", {"file": csv_file}, format="multipart"
        ).json()
        assert body["summary"] == {"total": 1, "valid": 1, "invalid": 0}
        assert body["valid"][0]["annual_revenue"] == "1234567.50"

    def test_permission_denied_for_regular_user(self, user_client, user_profile):
        csv_file = _csv(["name"], [["A"]])
        response = user_client.post(
            "/api/accounts/import/preview/", {"file": csv_file}, format="multipart"
        )
        assert response.status_code == 403

    def test_non_csv_extension_rejected(self, admin_client, admin_profile):
        upload = SimpleUploadedFile(
            "accounts.xlsx", b"name\nA\n", content_type="text/csv"
        )
        response = admin_client.post(
            "/api/accounts/import/preview/", {"file": upload}, format="multipart"
        )
        assert response.status_code == 400

    def test_non_utf8_rejected(self, admin_client, admin_profile):
        upload = SimpleUploadedFile(
            "accounts.csv", "name\nCafé\n".encode("latin-1"), content_type="text/csv"
        )
        body = admin_client.post(
            "/api/accounts/import/preview/", {"file": upload}, format="multipart"
        ).json()
        assert body["header_error"] and "UTF-8" in body["header_error"]

    def test_empty_csv_rejected(self, admin_client, admin_profile):
        upload = SimpleUploadedFile("accounts.csv", b"", content_type="text/csv")
        body = admin_client.post(
            "/api/accounts/import/preview/", {"file": upload}, format="multipart"
        ).json()
        assert body["header_error"]


@pytest.mark.django_db
class TestImportCommit:
    def test_commits_in_one_transaction(
        self, admin_client, org_a, admin_user, admin_profile
    ):
        csv_file = _csv(
            ["name", "email", "industry", "annual_revenue", "currency"],
            [
                ["Alpha Co", "a@alpha.test", "banking", "1000.00", "usd"],
                ["Beta Co", "b@beta.test", "automotive", "2000", "eur"],
            ],
        )
        response = admin_client.post(
            "/api/accounts/import/commit/", {"file": csv_file}, format="multipart"
        )
        assert response.status_code == 200, response.json()
        body = response.json()
        assert body["error"] is False
        assert body["created"] == 2
        accounts = Account.objects.filter(org=org_a)
        assert accounts.count() == 2
        alpha = accounts.get(name="Alpha Co")
        assert alpha.industry == "BANKING"
        assert alpha.currency == "USD"
        assert str(alpha.annual_revenue) == "1000.00"
        assert alpha.created_by_id == admin_user.id

    def test_commit_refuses_if_any_row_invalid(
        self, admin_client, org_a, existing_account, admin_profile
    ):
        # Row 1 valid; row 2 collides on name with the existing account.
        # Atomic = all-or-nothing.
        csv_file = _csv(
            ["name"],
            [["Fresh Co"], ["Acme Corp"]],
        )
        response = admin_client.post(
            "/api/accounts/import/commit/", {"file": csv_file}, format="multipart"
        )
        assert response.status_code == 400
        body = response.json()
        assert body["error"] is True
        assert body["created"] == 0
        # Only the pre-existing account remains.
        assert Account.objects.filter(org=org_a).count() == 1

    def test_commit_name_in_other_org_succeeds(
        self, admin_client, org_a, org_b, user_b, admin_profile
    ):
        Account.objects.create(name="Cross Co", org=org_b, created_by=user_b)
        csv_file = _csv(["name"], [["Cross Co"]])
        response = admin_client.post(
            "/api/accounts/import/commit/", {"file": csv_file}, format="multipart"
        )
        assert response.status_code == 200, response.json()
        assert response.json()["created"] == 1
        assert Account.objects.filter(org=org_a, name="Cross Co").count() == 1

    def test_permission_denied_for_regular_user(self, user_client, user_profile):
        csv_file = _csv(["name"], [["A"]])
        response = user_client.post(
            "/api/accounts/import/commit/", {"file": csv_file}, format="multipart"
        )
        assert response.status_code == 403

    def test_integrity_error_race_returns_400_not_500(
        self, admin_client, org_a, admin_profile, monkeypatch
    ):
        # Another request inserts a colliding account AFTER parse_and_validate
        # reads the DB but BEFORE create runs → DB raises IntegrityError on
        # unique_account_name_per_org. Must surface as 400, not 500.
        from django.db import IntegrityError

        from accounts.services import csv_import

        def racing_create(**kwargs):
            raise IntegrityError("duplicate key value violates unique constraint")

        monkeypatch.setattr(csv_import.Account.objects, "create", racing_create)

        csv_file = _csv(["name"], [["Race Co"]])
        response = admin_client.post(
            "/api/accounts/import/commit/", {"file": csv_file}, format="multipart"
        )
        assert response.status_code == 400
        body = response.json()
        assert body["error"] is True
        assert body["created"] == 0
        assert "concurrently" in body["message"].lower()
