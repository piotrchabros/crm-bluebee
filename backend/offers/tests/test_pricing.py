"""Golden tests for the standard-ab pricing expansion (Task 10.3)."""

from offers.pricing import expand_standard_ab, fmt_pln


def test_fmt_pln_grouping():
    assert fmt_pln(20000) == "20 000"
    assert fmt_pln(1000) == "1 000"
    assert fmt_pln(500) == "500"
    assert fmt_pln(1234567) == "1 234 567"


def test_expansion_structure():
    out = expand_standard_ab(20000, 1000, 1000, estimated=False, note=None)
    assert set(out) == {"comparison", "table", "cards", "note"}
    assert len(out["comparison"]["variants"]) == 2
    assert out["comparison"]["variants"][1]["recommended"] is True
    assert out["comparison"]["variants"][1]["badge"] == "Niski próg wejścia"
    # table: 6 rows incl. one total
    assert len(out["table"]["rows"]) == 6
    assert out["table"]["rows"][-1]["isTotal"] is True
    assert out["table"]["headers"][0] == "Kryterium"
    # two cards, B recommended with period
    assert len(out["cards"]) == 2
    assert out["cards"][1]["recommended"] is True
    assert out["cards"][1]["period"] == "/mies"


def test_expansion_interpolates_amounts():
    out = expand_standard_ab(50000, 2500, 800)
    opłata = out["table"]["rows"][0]["cells"]
    assert "50 000 PLN netto jednorazowo" == opłata[1]
    assert "2 500 PLN netto miesięcznie" == opłata[2]
    assert out["cards"][0]["netPrice"] == 50000
    assert out["cards"][1]["netPrice"] == 2500
    assert "800 min / mies" in out["cards"][1]["footer"]


def test_estimated_changes_card_sublabel():
    fixed = expand_standard_ab(20000, 1000, 1000, estimated=False)
    est = expand_standard_ab(20000, 1000, 1000, estimated=True)
    assert "cena stała" in fixed["cards"][0]["subLabel"]
    assert "wartość szacunkowa" in est["cards"][0]["subLabel"]


def test_note_passthrough():
    out = expand_standard_ab(20000, 1000, 1000, note="Uwaga **x**.")
    assert out["note"] == "Uwaga **x**."
