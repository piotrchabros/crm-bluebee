"""Gemini-backed offer generation, ported 1:1 from bluebee-website `offer-ai.ts`.

`brief_to_offer_data` (create) and `apply_edit_to_offer_data` (NL edit) return a
schema-valid offer_data dict. The system prompt (brand info, hard rules, block
doc, worked example) is a faithful port. Validation + retry-once live in
`_structured`, which accepts an injectable `generate` callable so the
parse/retry/brand-override logic is unit-testable without hitting the network.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone as dt_timezone

from offers.schema import validate_offer_data


class OfferGenerationError(Exception):
    """AI failed to return a schema-valid offer (maps to HTTP 422 upstream)."""


PL_MONTHS = [
    "styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec",
    "lipiec", "sierpień", "wrzesień", "październik", "listopad", "grudzień",
]


def _date_label() -> str:
    d = datetime.now(dt_timezone.utc)
    return f"{PL_MONTHS[d.month - 1]} {d.year}"


def strip_fence(text: str) -> str:
    """Remove a leading ```json / ``` fence and trailing ``` (mirror source)."""
    text = re.sub(r"^```(?:json)?\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return text.strip()


# Block-type doc for the prompt — kept verbatim from the source schema file.
BLOCK_TYPES_DOC = """Dostępne typy sekcji (pole "type"):
- "prose": { number, title, intro?, paragraphs: string[] } — akapity tekstu.
- "checklist": { number, title, intro?, listTitle?, items: string[] } — lista z ptaszkami (funkcje, warunki, rozwój).
- "stats": { number, title, intro?, stats: {value,label}[], chips: {label, items:string[]}[], highlight?: {label,value,note?} } — profil: liczby + chipsy.
- "techGrid": { number, title, intro?, items: {label,value}[], note? } — siatka technologii.
- "valueGrid": { number, title, intro?, lead?, items: {title,body}[], highlight? } — karty wartości (np. "Dlaczego my", GrowGPT).
- "table": { number, title, intro?, headers?: string[], rows: {cells:string[], isTotal?}[] } — tabela.
- "highlight": { number, title, label, value, note? } — pojedynczy box akcentowy.
- "warmNote": { number, title, noteTitle, body } — box ostrzegawczy (np. "Poza zakresem").
- "pricing": { number, title, intro?, preset:"standard-ab", valueA?:number=20000, subscription?:number=1000, minutes?:number=1000, estimated?:boolean, note? } — warianty A/B (rozwijane automatycznie do porównania + tabeli + 2 kart cenowych).
- "cta": { number, title, ctaTitle, description, actions: {label,href,ghost?}[] } — sekcja kontakt.

Tekst (paragraphs/intro/value/body/description/items) to "rich string": dozwolone TYLKO **pogrubienie** i linki [tekst](url). ZERO HTML. Myślniki TYLKO krótkie "-" (nigdy — ani –)."""


COMMON_RULES = """ZASADY (twarde):
- Myślniki: TYLKO krótkie "-". NIGDY długie — ani –.
- Tekst to rich-string: dozwolone TYLKO **pogrubienie** i linki [tekst](url). ZERO HTML, zero <tagów>.
- hero.titleLead = "Asystent" lub "Agent"; hero.titleEm = "głosowy AI".
- hero.meta = DOKŁADNIE 4 pozycje, w tym {label:"Przygotowano dla", value:<klient>} oraz {label:"Data oferty", value:<podana data>} i {label:"Ważność", value:"30 dni"}. Czwarta: "Na ręce"/"Profil"/"Lokalizacje" zależnie od kontekstu.
- Sekcje numeruj "01 / ...", "02 / ..." itd. po kolei.
- Standardowy układ: 01 W skrócie (prose; w drugim akapicie dodaj zdanie z linkiem [heyheyo](https://heyheyo.com) jako działający przykład), 02 Profil i dopasowanie (stats: liczby + chipsy), 03 Funkcje (checklist, pogrub lead każdego punktu), [opcjonalnie 04 Integracja z CRM (checklist)], Technologia (techGrid), Warianty współpracy (pricing, preset standard-ab), Warunki i czas realizacji (checklist + highlight z czasem np. "ok. 5-7 tygodni"), [opcjonalnie rozwój/upsell], Kontakt (cta).
- techGrid - użyj standardowych kategorii (dostosuj integrację do klienta): "Aplikacja i panel"=Next.js, w kontenerach Docker; "Usługa głosowa"=Proces ciągły, obsługa rozmowy w czasie rzeczywistym; "Baza danych"=PostgreSQL z wyszukiwaniem wektorowym, w regionie UE; "Telefonia i SMS"=Twilio (numer polski); "Rozpoznawanie mowy"=Deepgram; "Model językowy"=Google Gemini, z mechanizmem awaryjnym; "Synteza mowy"=ElevenLabs, polskie głosy; "Integracja ..."=specyficzna dla klienta (CRM/ERP/system rezerwacji). Dodaj note o infrastrukturze w UE.
- pricing: zawsze preset "standard-ab". Domyślnie valueA=20000, subscription=1000, minutes=1000. Jeśli brief mówi "wartość szacunkowa"/"do potwierdzenia" → estimated=true i dodaj note.
- cta.actions: [{label:"Napisz do nas · <EMAIL>", href:"mailto:<EMAIL>"}, {label:"<SITE bez https>", href:"<SITE>", ghost:true}].
- Zwróć WYŁĄCZNIE obiekt JSON oferty (bez code fence, bez komentarzy)."""


EXAMPLE = {
    "brand": "bespoke",
    "hero": {
        "eyebrow": "Oferta współpracy · BespokeSoft × Demo Sp. z o.o.",
        "titleLead": "Asystent",
        "titleEm": "głosowy AI",
        "subtitle": "Asystent głosowy AI do obsługi klientów. Odciąża zespół od powtarzalnych telefonów, obsługuje zapytania poza godzinami pracy i zapisuje **pełną historię kontaktu w CRM**.",
        "meta": [
            {"label": "Przygotowano dla", "value": "Demo Sp. z o.o."},
            {"label": "Profil", "value": "Usługi B2B"},
            {"label": "Data oferty", "value": "czerwiec 2026"},
            {"label": "Ważność", "value": "30 dni"},
        ],
    },
    "sections": [
        {
            "type": "prose",
            "number": "01 / W skrócie",
            "title": "Mniej powtarzalnych telefonów, pełna historia w CRM",
            "paragraphs": [
                "Firma odbiera dużo powtarzalnych połączeń. Asystent głosowy AI przejmuje je, kwalifikuje i kieruje do właściwego działu.",
                "Działający przykład tego typu systemu głosowego dostępny jest pod adresem [heyheyo](https://heyheyo.com).",
            ],
        },
        {
            "type": "stats",
            "number": "02 / Profil i dopasowanie",
            "title": "Wysoki wolumen i praca poza godzinami",
            "intro": "Automatyzacja połączeń daje najszybszy zwrot.",
            "stats": [
                {"value": "24/7", "label": "obsługa zapytań"},
                {"value": "2", "label": "języki (PL / EN)"},
            ],
            "chips": [{"label": "Tematy", "items": ["Zamówienia", "Reklamacje", "B2B"]}],
        },
        {
            "type": "checklist",
            "number": "03 / Funkcje asystenta",
            "title": "Co robi asystent na połączeniach",
            "items": [
                "**Odbieranie i kwalifikacja połączeń:** ustalenie sprawy i przekierowanie do właściwego działu.",
                "**Obsługa po godzinach:** zapytania nocą i w weekendy, podsumowanie rano do zespołu.",
            ],
        },
        {
            "type": "techGrid",
            "number": "04 / Technologia",
            "title": "Sprawdzony stack pod jakość rozmowy po polsku",
            "items": [
                {"label": "Aplikacja i panel", "value": "Next.js, w kontenerach Docker."},
                {"label": "Telefonia i SMS", "value": "Twilio (numer polski)."},
                {"label": "Model językowy", "value": "Google Gemini, z mechanizmem awaryjnym."},
                {"label": "Integracja CRM", "value": "Zapis podsumowań i leadów po stronie systemów klienta."},
            ],
            "note": "Aplikacja i baza danych pracują na infrastrukturze w Unii Europejskiej.",
        },
        {
            "type": "pricing",
            "number": "05 / Warianty współpracy",
            "title": "Dwa modele - na własność albo w abonamencie",
            "intro": "Oba warianty realizują ten sam zakres funkcjonalny.",
            "preset": "standard-ab",
            "valueA": 20000,
            "subscription": 1000,
            "minutes": 1000,
            "estimated": False,
        },
        {
            "type": "checklist",
            "number": "06 / Warunki i czas realizacji",
            "title": "Co jest potrzebne do startu",
            "items": [
                "Dostęp do CRM (API lub uzgodniony format danych).",
                "Wskazanie osoby do ustaleń wdrożeniowych.",
            ],
            "highlight": {
                "label": "Szacowany czas wdrożenia",
                "value": "ok. 5-7 tygodni od startu",
                "note": "Czas zależny od zakresu integracji.",
            },
        },
        {
            "type": "cta",
            "number": "07 / Kontakt",
            "title": "Porozmawiajmy o wdrożeniu",
            "ctaTitle": "Doprecyzujmy zakres i wybór wariantu",
            "description": "Oferta przygotowana przez **BespokeSoft** (Dawid Kawalec). Po zielonym świetle doprecyzujemy zakres i umówimy rozmowę.",
            "actions": [
                {"label": "Napisz do nas · hello@bespokesoft.pl", "href": "mailto:hello@bespokesoft.pl"},
                {"label": "bespokesoft.pl", "href": "https://bespokesoft.pl", "ghost": True},
            ],
        },
    ],
}
EXAMPLE_JSON = json.dumps(EXAMPLE, ensure_ascii=False)


def _theme_phrase(branding: dict) -> str:
    base = "ciemny motyw" if branding.get("theme") == "dark" else "jasny motyw"
    return f"{base}, akcent {branding.get('accent', '')}"


def _build_generate_system(branding: dict, client_name: str) -> str:
    label = branding["label"]
    email = branding.get("email") or ""
    site = branding.get("site") or ""
    prepared_by = branding.get("prepared_by") or label
    contact = ""
    if email or site:
        contact = f" W CTA użyj email {email} i strony {site}." if (email and site) else (
            f" W CTA użyj email {email}." if email else f" W CTA użyj strony {site}."
        )
    return f"""Jesteś generatorem ofert handlowych "asystent/agent głosowy AI" dla {label} ({_theme_phrase(branding)}).
Tworzysz dane oferty jako JSON zgodny ze schematem.

eyebrow każdej oferty: "Oferta współpracy · {label} × {client_name}".{contact} Ofertę przygotował: {prepared_by}.

{BLOCK_TYPES_DOC}

{COMMON_RULES}

PRZYKŁAD POPRAWNEJ STRUKTURY (skrót, dostosuj treść do briefu):
{EXAMPLE_JSON}"""


def _build_edit_system() -> str:
    return f"""Jesteś edytorem istniejącej oferty (JSON). Otrzymasz AKTUALNY JSON oferty oraz INSTRUKCJĘ zmiany w języku naturalnym.
Zastosuj instrukcję i zwróć PEŁNY, zaktualizowany JSON oferty. Zachowaj wszystko, czego instrukcja nie dotyczy (1:1).

Obsługujesz zmiany skalarne (np. "podnieś cenę Wariantu A o 20%" → zmień sections[].pricing.valueA; "zmień opiekę" → edytuj treść) oraz strukturalne (np. "dodaj sekcję FAQ z 3 pytaniami" → dodaj nowy blok, najczęściej typu "checklist" lub "valueGrid", z właściwym numerem sekcji i przelicz numerację jeśli trzeba).

{BLOCK_TYPES_DOC}

{COMMON_RULES}

Zwróć WYŁĄCZNIE pełny obiekt JSON oferty (bez code fence, bez komentarzy)."""


def _live_generate(system_instruction: str, user: str, temperature: float) -> str:
    """Real Gemini call with model fallback. Imported lazily so the module loads
    without the SDK/key present (e.g. during unit tests that inject `generate`)."""
    from google import genai
    from google.genai import types

    from offers import config

    key = config.api_key()
    if not key:
        raise OfferGenerationError("GEMINI_API_KEY is not configured on the server.")
    client = genai.Client(api_key=key)
    cfg = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=temperature,
        max_output_tokens=config.MAX_OUTPUT_TOKENS,
        response_mime_type="application/json",
    )
    last_exc = None
    for model in config.MODELS:
        try:
            resp = client.models.generate_content(
                model=model,
                contents=[types.Content(role="user", parts=[types.Part.from_text(text=user)])],
                config=cfg,
            )
            return strip_fence(resp.text or "")
        except Exception as exc:  # model unavailable / transient → try fallback
            last_exc = exc
            continue
    raise OfferGenerationError(f"Gemini call failed for all models: {last_exc}")


def _structured(system_instruction: str, user: str, temperature: float, *, generate=None) -> dict:
    """Call the model, validate, retry once with the schema error appended.

    `generate(system, user, temperature) -> raw_text` is injectable for tests.
    """
    gen = generate or _live_generate
    last_err = ""
    for attempt in range(2):
        u = (
            user
            if attempt == 0
            else f"{user}\n\nUWAGA: poprzednia odpowiedź była NIEZGODNA ze schematem ({last_err}). "
            "Zwróć POPRAWNY JSON zgodny ze schematem, bez komentarzy."
        )
        raw = gen(system_instruction, u, temperature)
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            last_err = "niepoprawny JSON"
            continue
        ok, data = validate_offer_data(parsed)
        if ok:
            return data
        last_err = data
    raise OfferGenerationError(f"AI nie zwróciło poprawnej struktury oferty: {last_err}")


def brief_to_offer_data(brief: str, branding: dict, client_name: str, *, generate=None) -> dict:
    """Generate offer_data from a brief using the org's `branding` dict
    (see offers.branding.org_branding). `offer_data.brand` is no longer set —
    theme/contacts come from branding, not from a fixed brand enum (Feature 5)."""
    user = f"""KLIENT: {client_name}
DATA OFERTY (użyj w meta): {_date_label()}

OPIS / BRIEF KLIENTA (zmapuj na sekcje oferty, zachowaj każdy istotny szczegół):
{brief}"""
    return _structured(_build_generate_system(branding, client_name), user, 0.3, generate=generate)


def apply_edit_to_offer_data(current: dict, instruction: str, *, generate=None) -> dict:
    user = f"""AKTUALNY JSON OFERTY:
{json.dumps(current, ensure_ascii=False)}

INSTRUKCJA ZMIANY (zastosuj dosłownie):
{instruction}"""
    data = _structured(_build_edit_system(), user, 0.2, generate=generate)
    # Preserve a legacy brand value if the original had one; don't invent it.
    if current.get("brand"):
        data["brand"] = current["brand"]
    return data
