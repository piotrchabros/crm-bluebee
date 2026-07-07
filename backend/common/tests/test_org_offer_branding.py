"""Org settings branding fields (Task 18.1)."""

URL = "/api/org/settings/"


def test_get_includes_branding(admin_client):
    r = admin_client.get(URL)
    assert r.status_code == 200
    data = r.json()
    assert "offer_theme" in data
    assert "offer_accent" in data
    assert "offer_prepared_by" in data


def test_patch_branding_persists(admin_client, org_a):
    r = admin_client.patch(
        URL,
        {"offer_theme": "light", "offer_accent": "#123456", "offer_prepared_by": "X Co"},
        format="json",
    )
    assert r.status_code == 200, r.content
    org_a.refresh_from_db()
    assert org_a.offer_theme == "light"
    assert org_a.offer_accent == "#123456"
    assert org_a.offer_prepared_by == "X Co"


def test_patch_invalid_accent_400(admin_client):
    r = admin_client.patch(URL, {"offer_accent": "red"}, format="json")
    assert r.status_code == 400


def test_patch_invalid_theme_400(admin_client):
    r = admin_client.patch(URL, {"offer_theme": "neon"}, format="json")
    assert r.status_code == 400


def test_non_admin_cannot_patch(user_client):
    r = user_client.patch(URL, {"offer_accent": "#000000"}, format="json")
    assert r.status_code == 403
