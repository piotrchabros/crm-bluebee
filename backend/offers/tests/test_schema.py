"""Schema-parity tests for validate_offer_data (Tasks 10.2 / 14.3).

For each of the 10 block types: a valid payload passes; an intentionally-broken
one fails. Plus hero, bounds, defaults, discriminator and brand checks.
"""

import pytest

from offers.schema import validate_offer_data

HERO = {
    "titleLead": "Asystent",
    "titleEm": "głosowy AI",
    "subtitle": "Sub **bold**.",
    "meta": [{"label": "Przygotowano dla", "value": "Demo"}],
}

# One valid sample per block type.
VALID_BLOCKS = {
    "prose": {"type": "prose", "title": "T", "paragraphs": ["a", "b"]},
    "checklist": {"type": "checklist", "title": "T", "items": ["a"]},
    "stats": {"type": "stats", "title": "T", "stats": [{"value": "24/7", "label": "x"}], "chips": [{"label": "c", "items": ["i"]}]},
    "techGrid": {"type": "techGrid", "title": "T", "items": [{"label": "l", "value": "v"}]},
    "valueGrid": {"type": "valueGrid", "title": "T", "items": [{"title": "t", "body": "b"}]},
    "highlight": {"type": "highlight", "title": "T", "label": "l", "value": "v"},
    "warmNote": {"type": "warmNote", "title": "T", "noteTitle": "n", "body": "b"},
    "table": {"type": "table", "title": "T", "rows": [{"cells": ["a", "b"]}]},
    "pricing": {"type": "pricing", "title": "T"},
    "cta": {"type": "cta", "title": "T", "ctaTitle": "c", "description": "d", "actions": [{"label": "l", "href": "mailto:x@y.z"}]},
}


def _offer(*sections):
    return {"brand": "bespoke", "hero": HERO, "sections": list(sections)}


@pytest.mark.parametrize("btype", list(VALID_BLOCKS))
def test_each_valid_block_passes(btype):
    ok, data = validate_offer_data(_offer(VALID_BLOCKS[btype]))
    assert ok, data
    assert data["sections"][0]["type"] == btype


# (block, missing_key_path_fragment) — break one required field per block type.
BROKEN_CASES = [
    ({"type": "prose", "title": "T"}, "paragraphs"),  # missing required
    ({"type": "checklist", "title": "T"}, "items"),
    ({"type": "techGrid", "title": "T"}, "items"),
    ({"type": "valueGrid", "title": "T"}, "items"),
    ({"type": "highlight", "title": "T", "label": "l"}, "value"),
    ({"type": "warmNote", "title": "T", "noteTitle": "n"}, "body"),
    ({"type": "table", "title": "T"}, "rows"),
    ({"type": "cta", "title": "T", "ctaTitle": "c", "description": "d"}, "actions"),
    ({"type": "prose", "paragraphs": ["a"]}, "title"),  # missing base title
]


@pytest.mark.parametrize("block,fragment", BROKEN_CASES)
def test_broken_block_fails_with_path(block, fragment):
    ok, err = validate_offer_data(_offer(block))
    assert not ok
    assert fragment in err, err


def test_unknown_block_type_rejected():
    ok, err = validate_offer_data(_offer({"type": "bogus", "title": "T"}))
    assert not ok
    assert "discriminator" in err


def test_brand_enum_enforced():
    ok, err = validate_offer_data({"brand": "nope", "hero": HERO, "sections": [VALID_BLOCKS["prose"]]})
    assert not ok
    assert "brand" in err


def test_sections_min_and_max_bounds():
    ok, err = validate_offer_data({"brand": "bespoke", "hero": HERO, "sections": []})
    assert not ok and "sections" in err
    too_many = [VALID_BLOCKS["prose"]] * 15
    ok, err = validate_offer_data({"brand": "bespoke", "hero": HERO, "sections": too_many})
    assert not ok and "sections" in err


def test_hero_meta_max_four():
    bad_hero = {**HERO, "meta": [{"label": "l", "value": "v"}] * 5}
    ok, err = validate_offer_data({"brand": "bespoke", "hero": bad_hero, "sections": [VALID_BLOCKS["prose"]]})
    assert not ok and "meta" in err


def test_checklist_items_max_twenty():
    blk = {"type": "checklist", "title": "T", "items": ["x"] * 21}
    ok, err = validate_offer_data(_offer(blk))
    assert not ok and "items" in err


def test_pricing_defaults_applied():
    ok, data = validate_offer_data(_offer({"type": "pricing", "title": "T"}))
    assert ok, data
    pricing = data["sections"][0]
    assert pricing["valueA"] == 20000
    assert pricing["subscription"] == 1000
    assert pricing["minutes"] == 1000
    assert pricing["estimated"] is False
    assert pricing["preset"] == "standard-ab"


def test_pricing_rejects_nonpositive():
    ok, err = validate_offer_data(_offer({"type": "pricing", "title": "T", "valueA": 0}))
    assert not ok and "valueA" in err


def test_stats_defaults_to_empty_arrays():
    ok, data = validate_offer_data(_offer({"type": "stats", "title": "T"}))
    assert ok, data
    assert data["sections"][0]["stats"] == []
    assert data["sections"][0]["chips"] == []


def test_unknown_keys_dropped():
    blk = {"type": "prose", "title": "T", "paragraphs": ["a"], "bogus": "x"}
    ok, data = validate_offer_data(_offer(blk))
    assert ok
    assert "bogus" not in data["sections"][0]


def test_non_object_root_rejected():
    ok, err = validate_offer_data("not an object")
    assert not ok


def test_brand_optional_since_feature5():
    # No brand key at all → valid (per-org branding drives theme now).
    payload = {"hero": HERO, "sections": [VALID_BLOCKS["prose"]]}
    ok, data = validate_offer_data(payload)
    assert ok, data
    assert "brand" not in data


def test_brand_kept_when_present_and_valid():
    ok, data = validate_offer_data(_offer(VALID_BLOCKS["prose"]))  # _offer sets brand=bespoke
    assert ok and data["brand"] == "bespoke"
