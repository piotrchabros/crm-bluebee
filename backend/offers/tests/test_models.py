"""DB-backed tests for the Offer model (Task 10.1)."""

import re

import pytest

from offers.models import Offer


def _make(org, **kw):
    defaults = dict(client_name="Demo Sp. z o.o.", title="T", brand="bespoke", offer_data={})
    defaults.update(kw)
    return Offer.objects.create(org=org, **defaults)


def test_create_generates_slug_and_token(org_a):
    o = _make(org_a, client_name="Spółka Łódź Testowa")
    assert o.slug.startswith("spolka-lodz-testowa-")
    assert re.fullmatch(r"[a-z0-9]{8}", o.access_token)
    assert o.public_path == f"/oferta/{o.slug}-{o.access_token}"


def test_access_token_immutable_on_update(org_a):
    o = _make(org_a)
    original = o.access_token
    o.access_token = "HACKED"
    o.title = "Changed"
    o.save()
    o.refresh_from_db()
    assert o.access_token == original
    assert o.title == "Changed"


def test_slug_collision_suffix(org_a):
    o1 = _make(org_a, client_name="Acme")
    o2 = _make(org_a, client_name="Acme")
    assert o1.slug != o2.slug
    assert o2.slug.startswith(o1.slug)


def test_slug_is_globally_unique(org_a, org_b):
    o1 = _make(org_a, client_name="Acme")
    o2 = _make(org_b, client_name="Acme")
    assert o1.slug != o2.slug
