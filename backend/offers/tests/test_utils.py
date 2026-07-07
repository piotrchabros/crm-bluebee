"""Unit tests for slug + access-token helpers (Task 10.1)."""

import re

from offers.utils import ACCESS_TOKEN_LEN, generate_access_token, slugify


def test_access_token_shape():
    for _ in range(50):
        t = generate_access_token()
        assert len(t) == ACCESS_TOKEN_LEN
        assert re.fullmatch(r"[a-z0-9]{8}", t), t


def test_access_token_is_random():
    tokens = {generate_access_token() for _ in range(100)}
    # Overwhelmingly likely all-unique; assert high entropy (no constant token).
    assert len(tokens) > 90


def test_slugify_basic():
    assert slugify("Demo Sp. z o.o.") == "demo-sp-z-o-o"


def test_slugify_polish_diacritics_and_l():
    # ł → l, other diacritics stripped, lowercased, non-alnum → '-'
    assert slugify("Spółka Łódź Testowa") == "spolka-lodz-testowa"
    assert slugify("Żółć Ćma Ńiebo") == "zolc-cma-niebo"


def test_slugify_trims_and_collapses():
    assert slugify("  --Hello,, World!!  ") == "hello-world"


def test_slugify_empty():
    assert slugify("") == ""
    assert slugify("???") == ""
