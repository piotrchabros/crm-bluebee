"""Unit tests for the AI parse/retry logic + per-org branding (Tasks 11.1 / 16.3).

The Gemini call is injected, so these run offline and deterministically.
"""

import json

import pytest

from offers import ai
from offers.ai import (
    OfferGenerationError,
    apply_edit_to_offer_data,
    brief_to_offer_data,
    strip_fence,
)

VALID_OFFER = {
    "hero": {"titleLead": "Asystent", "titleEm": "głosowy AI", "subtitle": "S", "meta": []},
    "sections": [{"type": "prose", "title": "T", "paragraphs": ["a"]}],
}

BRANDING = {
    "label": "BespokeSoft",
    "company_name": "BespokeSoft",
    "email": "hello@bespokesoft.pl",
    "site": "https://bespokesoft.pl",
    "prepared_by": "BespokeSoft (Dawid Kawalec)",
    "theme": "light",
    "accent": "#0d6efd",
    "has_logo": False,
}


def _gen_returning(*payloads):
    """Fake generate() returning the given strings in order; records prompts."""
    seq = list(payloads)
    calls = {"n": 0, "systems": []}

    def gen(system, user, temperature):
        calls["n"] += 1
        calls["systems"].append(system)
        return seq.pop(0)

    gen.calls = calls
    return gen


def test_strip_fence():
    assert strip_fence("```json\n{}\n```") == "{}"
    assert strip_fence("```\n{}\n```") == "{}"
    assert strip_fence('{"a":1}') == '{"a":1}'


def test_generate_happy_path_first_try():
    gen = _gen_returning(json.dumps(VALID_OFFER))
    data = brief_to_offer_data("brief", BRANDING, "Klient", generate=gen)
    assert data["sections"][0]["type"] == "prose"
    assert gen.calls["n"] == 1


def test_branding_injected_into_prompt():
    gen = _gen_returning(json.dumps(VALID_OFFER))
    brief_to_offer_data("brief", BRANDING, "Klient X", generate=gen)
    system = gen.calls["systems"][0]
    assert "BespokeSoft" in system
    assert "hello@bespokesoft.pl" in system
    assert "bespokesoft.pl" in system
    assert "#0d6efd" in system  # accent in theme phrase
    assert "Klient X" in system  # eyebrow client


def test_retry_on_bad_json_then_success():
    gen = _gen_returning("not json at all", json.dumps(VALID_OFFER))
    data = brief_to_offer_data("brief", BRANDING, "Klient", generate=gen)
    assert data["sections"]
    assert gen.calls["n"] == 2


def test_retry_on_schema_invalid_then_success():
    invalid = {"hero": {}, "sections": []}  # missing hero fields + empty sections
    gen = _gen_returning(json.dumps(invalid), json.dumps(VALID_OFFER))
    data = brief_to_offer_data("brief", BRANDING, "Klient", generate=gen)
    assert data["sections"]
    assert gen.calls["n"] == 2


def test_raises_after_two_failures():
    gen = _gen_returning("bad", "still bad")
    with pytest.raises(OfferGenerationError):
        brief_to_offer_data("brief", BRANDING, "Klient", generate=gen)
    assert gen.calls["n"] == 2


def test_edit_preserves_legacy_brand_if_present():
    current = {**VALID_OFFER, "brand": "bluebee"}
    returned = {**VALID_OFFER, "brand": "bespoke"}  # model wrongly flips brand
    gen = _gen_returning(json.dumps(returned))
    data = apply_edit_to_offer_data(current, "podnieś cenę", generate=gen)
    assert data["brand"] == "bluebee"


def test_edit_without_brand_stays_brandless():
    gen = _gen_returning(json.dumps(VALID_OFFER))
    data = apply_edit_to_offer_data(VALID_OFFER, "zmień coś", generate=gen)
    assert "brand" not in data


def test_missing_key_raises_in_live_path(monkeypatch):
    from offers import config

    monkeypatch.setattr(config, "api_key", lambda: "")
    with pytest.raises(OfferGenerationError):
        ai._live_generate("sys", "user", 0.3)
