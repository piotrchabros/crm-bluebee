"""Tests for org_branding (Task 16.2)."""

from offers.branding import org_branding


class _Org:
    def __init__(self, **kw):
        self.name = kw.get("name", "")
        self.company_name = kw.get("company_name", "")
        self.email = kw.get("email", "")
        self.website = kw.get("website", "")
        self.offer_theme = kw.get("offer_theme", "dark")
        self.offer_accent = kw.get("offer_accent", "#E3FF04")
        self.offer_prepared_by = kw.get("offer_prepared_by", "")
        self.logo = kw.get("logo", None)


def test_full_org():
    b = org_branding(_Org(
        name="BlueBee", company_name="BlueBee Sp. z o.o.", email="x@bluebee.marketing",
        website="https://bluebee.marketing", offer_theme="dark", offer_accent="#E3FF04",
        offer_prepared_by="BlueBee", logo="org_logos/a.png",
    ))
    assert b["label"] == "BlueBee Sp. z o.o."
    assert b["email"] == "x@bluebee.marketing"
    assert b["site"] == "https://bluebee.marketing"
    assert b["theme"] == "dark" and b["accent"] == "#E3FF04"
    assert b["prepared_by"] == "BlueBee"
    assert b["has_logo"] is True


def test_fallbacks():
    b = org_branding(_Org(name="Acme"))  # no company_name, no prepared_by, no logo
    assert b["label"] == "Acme"
    assert b["company_name"] == "Acme"
    assert b["prepared_by"] == "Acme"  # falls back to label
    assert b["email"] == "" and b["site"] == ""
    assert b["has_logo"] is False
    assert b["theme"] == "dark" and b["accent"] == "#E3FF04"


def test_prepared_by_overrides_label():
    b = org_branding(_Org(name="X", company_name="X Co", offer_prepared_by="Jan Kowalski"))
    assert b["label"] == "X Co"
    assert b["prepared_by"] == "Jan Kowalski"
