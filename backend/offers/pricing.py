"""Deterministic `standard-ab` pricing expansion.

Ported 1:1 from `DataOffer.tsx` `StandardPricing`. Given the compact pricing
block fields it returns the full comparison + table + two-card structure. This is
the single source of truth shared by the backend golden test (10.3) and the
SvelteKit pricing renderer (13.4) — the SvelteKit side renders this dict, it does
NOT re-hardcode the copy.

Rich-text cells use the same rich-string convention as everything else
(`**bold**` + `[link](url)`), so the renderer's RT handles them.
"""

from __future__ import annotations


def fmt_pln(n) -> str:
    """Mirror `Intl.NumberFormat('pl-PL')`: group thousands with U+00A0.

    Integers render with no decimals; non-integers use a comma decimal sep.
    """
    if isinstance(n, bool):
        n = int(n)
    if isinstance(n, int) or (isinstance(n, float) and n.is_integer()):
        s = str(abs(int(n)))
        grouped = _group_thousands(s)
        return f"-{grouped}" if n < 0 else grouped
    # Non-integer: pl-PL uses ',' decimal sep, ' ' grouping.
    neg = n < 0
    whole, frac = f"{abs(n)}".split(".")
    out = f"{_group_thousands(whole)},{frac}"
    return f"-{out}" if neg else out


def _group_thousands(digits: str) -> str:
    parts = []
    while len(digits) > 3:
        parts.insert(0, digits[-3:])
        digits = digits[:-3]
    parts.insert(0, digits)
    return " ".join(parts)


def expand_standard_ab(
    value_a: float,
    subscription: float,
    minutes: float,
    estimated: bool = False,
    note: str | None = None,
) -> dict:
    """Return the full structured A/B pricing layout (comparison + table + cards)."""
    return {
        "comparison": {
            "variants": [
                {
                    "title": "Wariant A - na własność",
                    "subtitle": "Wdrożenie dedykowane · jednorazowo",
                    "description": (
                        "Jednorazowe wdrożenie dedykowanego systemu na infrastrukturze "
                        "klienta. Po końcowej płatności pełne prawa do dostarczonego "
                        "systemu przechodzą na klienta."
                    ),
                    "benefits": [
                        {"label": "Prawa do systemu", "value": "Pełne, po stronie klienta po końcowej płatności"},
                        {"label": "Konta dostawców", "value": "Klient zakłada i opłaca konta; ich pełna konfiguracja w cenie wdrożenia"},
                        {"label": "Koszty operacyjne", "value": "Minuty rozmów, zużycie usług i hosting - bezpośrednio u dostawców"},
                        {"label": "Opieka", "value": "Opcjonalna comiesięczna opieka i utrzymanie (do uzgodnienia)"},
                    ],
                    "recommendation": "**Najlepszy gdy:** chcecie mieć system na własność oraz jednorazowy model rozliczenia.",
                    "recommended": False,
                },
                {
                    "title": "Wariant B - subskrypcja",
                    "subtitle": "Abonament · hosting i utrzymanie po naszej stronie",
                    "recommended": True,
                    "badge": "Niski próg wejścia",
                    "description": (
                        "System hostowany i utrzymywany na infrastrukturze wykonawcy w UE, "
                        "wraz z pokryciem kosztów operacyjnych."
                    ),
                    "benefits": [
                        {"label": "Pakiet", "value": f"{fmt_pln(minutes)} minut rozmów miesięcznie; minuty ponad pakiet w stawce 1,20 PLN / min"},
                        {"label": "Prawa do systemu", "value": "Korzystanie z usługi, bez nabycia praw do kodu"},
                        {"label": "Pilotaż", "value": "Opcjonalny okres pilotażowy (1-3 miesiące)"},
                        {"label": "Umowa", "value": "Minimalny okres 12 miesięcy"},
                    ],
                    "recommendation": "**Najlepszy gdy:** chcecie wejść niskim kosztem początkowym, bez utrzymywania infrastruktury i kont dostawców.",
                },
            ],
        },
        "table": {
            "title": "Zestawienie wariantów",
            "headers": ["Kryterium", "Wariant A: na własność", "Wariant B: subskrypcja"],
            "rows": [
                {"cells": ["Opłata", f"{fmt_pln(value_a)} PLN netto jednorazowo", f"{fmt_pln(subscription)} PLN netto miesięcznie"]},
                {"cells": ["Prawa do systemu", "Pełne, po stronie klienta", "Korzystanie z usługi"]},
                {"cells": ["Hosting i utrzymanie", "Po stronie klienta", "Po stronie wykonawcy"]},
                {"cells": ["Koszty operacyjne", "Po stronie klienta", f"W abonamencie (pakiet {fmt_pln(minutes)} minut)"]},
                {"cells": ["Bariera wejścia", "Wyższa opłata początkowa", "Niska, model abonamentowy"]},
                {
                    "cells": ["**Rozliczenie**", "**50% start, 50% wdrożenie**", "**Miesięczne, min. 12 miesięcy**"],
                    "isTotal": True,
                },
            ],
        },
        "cards": [
            {
                "variant": "Wariant A - na własność",
                "title": "Wdrożenie dedykowane",
                "netPrice": value_a,
                "subLabel": "netto · jednorazowo · wartość szacunkowa"
                if estimated
                else "netto · jednorazowo · cena stała",
                "recommended": False,
                "footer": "**Płatność:** 50% przy starcie, 50% po wdrożeniu. Opcjonalna comiesięczna opieka i utrzymanie do uzgodnienia.",
            },
            {
                "variant": "Wariant B - subskrypcja",
                "title": "Model abonamentowy",
                "netPrice": subscription,
                "period": "/mies",
                "subLabel": "netto · abonament miesięczny",
                "recommended": True,
                "footer": f"Pakiet **{fmt_pln(minutes)} min / mies**, nadwyżka 1,20 PLN / min. Minimalny okres umowy 12 miesięcy. Opcjonalny pilotaż 1-3 miesiące.",
            },
        ],
        "note": note,
    }
