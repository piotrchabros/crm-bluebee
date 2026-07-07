"""Cutover tests: Opportunity generate/edit now use the native generator (12.3)."""

import pytest
from django.db import connection

from offers.models import Offer
from opportunity.models import Opportunity

VALID_OFFER = {
    "brand": "bespoke",
    "hero": {"titleLead": "Asystent", "titleEm": "głosowy AI", "subtitle": "S", "meta": []},
    "sections": [{"type": "prose", "title": "T", "paragraphs": ["a"]}],
}


def _set_rls(org):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as c:
        c.execute("SELECT set_config('app.current_org', %s, false)", [str(org.id)])


@pytest.fixture
def fake_ai(monkeypatch):
    monkeypatch.setattr(
        "offers.services.brief_to_offer_data",
        lambda brief, branding, client_name, **k: {**VALID_OFFER},
    )
    monkeypatch.setattr(
        "offers.services.apply_edit_to_offer_data",
        lambda current, instruction, **k: {**current, "sections": [{"type": "prose", "title": "EDITED", "paragraphs": ["b"]}]},
    )


@pytest.fixture
def opp(org_a):
    _set_rls(org_a)
    return Opportunity.objects.create(
        org=org_a, name="Deal X", description="Opis klienta dłuższy niż dwadzieścia znaków."
    )


def test_generate_creates_native_offer(user_client, opp, fake_ai):
    r = user_client.post(f"/api/opportunities/{opp.id}/generate-offer/", {}, format="json")
    assert r.status_code == 200, r.content
    body = r.json()
    assert "/oferta/" in body["url"]
    opp.refresh_from_db()
    assert opp.generated_offer is not None
    assert opp.offer_status == "generated"
    # a native Offer linked back to the opportunity exists
    offer = Offer.objects.get(id=opp.generated_offer_id)
    assert offer.opportunity_id == opp.id
    assert offer.org_id == opp.org_id


def test_generate_requires_description(user_client, org_a, fake_ai):
    _set_rls(org_a)
    bare = Opportunity.objects.create(org=org_a, name="No Desc")
    r = user_client.post(f"/api/opportunities/{bare.id}/generate-offer/", {}, format="json")
    assert r.status_code == 400


def test_edit_uses_native_offer(user_client, opp, fake_ai):
    user_client.post(f"/api/opportunities/{opp.id}/generate-offer/", {}, format="json")
    r = user_client.post(f"/api/opportunities/{opp.id}/edit-offer/", {"instruction": "zmień coś"}, format="json")
    assert r.status_code == 200, r.content
    opp.refresh_from_db()
    assert opp.generated_offer.offer_data["sections"][0]["title"] == "EDITED"


def test_edit_without_offer_400(user_client, opp, fake_ai):
    r = user_client.post(f"/api/opportunities/{opp.id}/edit-offer/", {"instruction": "x y z"}, format="json")
    assert r.status_code == 400


def test_cross_org_cannot_generate(org_b_client, opp, fake_ai):
    r = org_b_client.post(f"/api/opportunities/{opp.id}/generate-offer/", {}, format="json")
    assert r.status_code == 404
