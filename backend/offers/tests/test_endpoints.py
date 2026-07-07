"""Contract tests for offer endpoints (Tasks 12.1 / 12.2).

The Gemini call is monkeypatched at the service layer so these are deterministic
and offline.
"""

import pytest

VALID_OFFER = {
    "brand": "bespoke",
    "hero": {"titleLead": "Asystent", "titleEm": "głosowy AI", "subtitle": "S", "meta": []},
    "sections": [{"type": "prose", "title": "T", "paragraphs": ["a"]}],
}

CREATE_URL = "/api/offers/"


@pytest.fixture
def fake_ai(monkeypatch):
    def fake_brief(brief, branding, client_name, **kw):
        return {**VALID_OFFER}

    def fake_edit(current, instruction, **kw):
        out = {**current}
        # simulate a change so the test can observe an edit happened
        out["sections"] = [{"type": "prose", "title": "EDITED", "paragraphs": ["b"]}]
        return out

    monkeypatch.setattr("offers.services.brief_to_offer_data", fake_brief)
    monkeypatch.setattr("offers.services.apply_edit_to_offer_data", fake_edit)


def _create(client, **over):
    body = {"client_name": "Klient Sp. z o.o.", "brief": "x" * 30}
    body.update(over)
    return client.post(CREATE_URL, body, format="json")


def test_create_requires_auth(unauthenticated_client):
    r = _create(unauthenticated_client)
    assert r.status_code in (401, 403)


def test_create_offer_persists_and_returns_link(user_client, fake_ai):
    r = _create(user_client)
    assert r.status_code == 201, r.content
    data = r.json()
    assert data["slug"]
    assert len(data["access_token"]) == 8
    assert data["url"] == f"/oferta/{data['slug']}-{data['access_token']}"
    assert data["offer_data"]["sections"][0]["type"] == "prose"


def test_create_validates_short_brief(user_client, fake_ai):
    r = _create(user_client, brief="too short")
    assert r.status_code == 400


def test_edit_changes_offer_data_same_link(user_client, fake_ai):
    created = _create(user_client).json()
    oid, slug, token = created["id"], created["slug"], created["access_token"]
    r = user_client.post(f"/api/offers/{oid}/edit/", {"instruction": "zmień coś"}, format="json")
    assert r.status_code == 200, r.content
    edited = r.json()
    assert edited["slug"] == slug
    assert edited["access_token"] == token  # link stable
    assert edited["offer_data"]["sections"][0]["title"] == "EDITED"


def test_get_detail(user_client, fake_ai):
    oid = _create(user_client).json()["id"]
    r = user_client.get(f"/api/offers/{oid}/")
    assert r.status_code == 200
    assert r.json()["id"] == oid


def test_cross_org_cannot_read(user_client, org_b_client, fake_ai):
    oid = _create(user_client).json()["id"]
    r = org_b_client.get(f"/api/offers/{oid}/")
    assert r.status_code == 404


# --- public endpoint (12.2) ---------------------------------------------------


def test_public_valid_token_returns_data(user_client, unauthenticated_client, fake_ai):
    c = _create(user_client).json()
    r = unauthenticated_client.get(f"/api/public/offers/{c['slug']}/{c['access_token']}/")
    assert r.status_code == 200, r.content
    body = r.json()
    assert body["slug"] == c["slug"]
    assert "offer_data" in body
    # public payload must NOT leak internal fields
    assert "notes" not in body and "value" not in body and "id" not in body


def test_public_wrong_token_404(user_client, unauthenticated_client, fake_ai):
    c = _create(user_client).json()
    r = unauthenticated_client.get(f"/api/public/offers/{c['slug']}/wrongtok0/")
    assert r.status_code == 404


def test_public_unknown_slug_404(unauthenticated_client):
    r = unauthenticated_client.get("/api/public/offers/does-not-exist/abcd1234/")
    assert r.status_code == 404


def test_public_first_view_marks_viewed(user_client, unauthenticated_client, fake_ai):
    c = _create(user_client, status="sent").json()
    url = f"/api/public/offers/{c['slug']}/{c['access_token']}/"
    first = unauthenticated_client.get(url)
    assert first.json()["status"] == "viewed"


def test_public_preview_does_not_mark_viewed(user_client, unauthenticated_client, fake_ai):
    c = _create(user_client, status="sent").json()
    url = f"/api/public/offers/{c['slug']}/{c['access_token']}/?preview=1"
    r = unauthenticated_client.get(url)
    assert r.json()["status"] == "sent"


def test_public_bot_does_not_mark_viewed(user_client, unauthenticated_client, fake_ai):
    c = _create(user_client, status="sent").json()
    url = f"/api/public/offers/{c['slug']}/{c['access_token']}/"
    r = unauthenticated_client.get(url, HTTP_USER_AGENT="Mozilla/5.0 (compatible; Googlebot/2.1)")
    assert r.json()["status"] == "sent"


# --- per-org branding in public payload (17.1) + logo endpoint (17.2) ---


def test_public_payload_includes_branding(user_client, unauthenticated_client, fake_ai):
    c = _create(user_client).json()
    r = unauthenticated_client.get(f"/api/public/offers/{c['slug']}/{c['access_token']}/")
    assert r.status_code == 200
    b = r.json()["branding"]
    assert set(b) >= {"theme", "accent", "company_name", "email", "website", "prepared_by", "logo_url"}
    assert b["theme"] in ("dark", "light")
    assert b["accent"].startswith("#")
    assert b["logo_url"] is None  # org_a has no logo


def test_public_logo_404_when_no_logo(user_client, unauthenticated_client, fake_ai):
    c = _create(user_client).json()
    r = unauthenticated_client.get(f"/api/public/offers/{c['slug']}/{c['access_token']}/logo/")
    assert r.status_code == 404


def test_public_logo_bad_token_404(user_client, unauthenticated_client, fake_ai):
    c = _create(user_client).json()
    r = unauthenticated_client.get(f"/api/public/offers/{c['slug']}/wrongtok0/logo/")
    assert r.status_code == 404
