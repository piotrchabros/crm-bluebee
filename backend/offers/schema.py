"""Offer-data validation, ported 1:1 from bluebee-website `src/lib/offer-schema.ts`.

`validate_offer_data(input)` returns `(ok, data)` on success — with defaults
applied and unknown keys dropped, mirroring zod's behavior — or `(False, error)`
where error is a `"path: message; …"` string (≤12 issues), matching the source's
`validateOfferData`.

No external dependency (no pydantic): a hand validator keeps behavior identical
and explicit, which is the whole point of the parity contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

BRANDS = ("bluebee", "bespoke")
BLOCK_TYPES = (
    "prose",
    "checklist",
    "stats",
    "techGrid",
    "valueGrid",
    "highlight",
    "warmNote",
    "table",
    "pricing",
    "cta",
)


@dataclass
class _Ctx:
    issues: list[str] = field(default_factory=list)

    def err(self, path: str, message: str) -> None:
        self.issues.append(f"{path or '(root)'}: {message}")


_MISSING = object()


# --- low-level field helpers ----------------------------------------------------


def _req_str(ctx: _Ctx, obj: dict, key: str, path: str) -> str | None:
    v = obj.get(key, _MISSING)
    if v is _MISSING:
        ctx.err(f"{path}.{key}", "Required")
        return None
    if not isinstance(v, str):
        ctx.err(f"{path}.{key}", "Expected string")
        return None
    return v


def _opt_str(ctx: _Ctx, obj: dict, key: str, path: str) -> str | None:
    v = obj.get(key, _MISSING)
    if v is _MISSING or v is None:
        return None
    if not isinstance(v, str):
        ctx.err(f"{path}.{key}", "Expected string")
        return None
    return v


def _str_array(
    ctx: _Ctx, obj: dict, key: str, path: str, *, min_len=0, max_len=None, default=_MISSING
):
    v = obj.get(key, _MISSING)
    if v is _MISSING:
        if default is not _MISSING:
            return list(default)
        ctx.err(f"{path}.{key}", "Required")
        return []
    if not isinstance(v, list):
        ctx.err(f"{path}.{key}", "Expected array")
        return []
    out = []
    for i, item in enumerate(v):
        if not isinstance(item, str):
            ctx.err(f"{path}.{key}.{i}", "Expected string")
        else:
            out.append(item)
    _check_len(ctx, out, f"{path}.{key}", min_len, max_len)
    return out


def _check_len(ctx: _Ctx, arr: list, path: str, min_len: int, max_len) -> None:
    if min_len and len(arr) < min_len:
        ctx.err(path, f"Array must contain at least {min_len} element(s)")
    if max_len is not None and len(arr) > max_len:
        ctx.err(path, f"Array must contain at most {max_len} element(s)")


def _pos_number(ctx: _Ctx, obj: dict, key: str, path: str, default: float) -> float:
    v = obj.get(key, _MISSING)
    if v is _MISSING:
        return default
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        ctx.err(f"{path}.{key}", "Expected number")
        return default
    if v <= 0:
        ctx.err(f"{path}.{key}", "Number must be positive")
        return default
    return v


def _bool(ctx: _Ctx, obj: dict, key: str, path: str, default: bool) -> bool:
    v = obj.get(key, _MISSING)
    if v is _MISSING:
        return default
    if not isinstance(v, bool):
        ctx.err(f"{path}.{key}", "Expected boolean")
        return default
    return v


def _section_base(ctx: _Ctx, b: dict, path: str) -> dict:
    out: dict[str, Any] = {}
    number = _opt_str(ctx, b, "number", path)
    if number is not None:
        out["number"] = number
    out["title"] = _req_str(ctx, b, "title", path)
    intro = _opt_str(ctx, b, "intro", path)
    if intro is not None:
        out["intro"] = intro
    return out


def _highlight(ctx: _Ctx, h: Any, path: str) -> dict | None:
    if not isinstance(h, dict):
        ctx.err(path, "Expected object")
        return None
    out = {"label": _req_str(ctx, h, "label", path), "value": _req_str(ctx, h, "value", path)}
    note = _opt_str(ctx, h, "note", path)
    if note is not None:
        out["note"] = note
    return out


# --- per-block validators -------------------------------------------------------


def _block_prose(ctx, b, p):
    out = {"type": "prose", **_section_base(ctx, b, p)}
    out["paragraphs"] = _str_array(ctx, b, "paragraphs", p, min_len=1)
    return out


def _block_checklist(ctx, b, p):
    out = {"type": "checklist", **_section_base(ctx, b, p)}
    lt = _opt_str(ctx, b, "listTitle", p)
    if lt is not None:
        out["listTitle"] = lt
    out["items"] = _str_array(ctx, b, "items", p, min_len=1, max_len=20)
    if b.get("highlight") is not None:
        out["highlight"] = _highlight(ctx, b.get("highlight"), f"{p}.highlight")
    return out


def _block_stats(ctx, b, p):
    out = {"type": "stats", **_section_base(ctx, b, p)}
    stats_in = b.get("stats", [])
    stats = []
    if isinstance(stats_in, list):
        for i, s in enumerate(stats_in):
            if not isinstance(s, dict):
                ctx.err(f"{p}.stats.{i}", "Expected object")
                continue
            stats.append(
                {
                    "value": _req_str(ctx, s, "value", f"{p}.stats.{i}"),
                    "label": _req_str(ctx, s, "label", f"{p}.stats.{i}"),
                }
            )
    elif "stats" in b:
        ctx.err(f"{p}.stats", "Expected array")
    _check_len(ctx, stats, f"{p}.stats", 0, 6)
    out["stats"] = stats

    chips_in = b.get("chips", [])
    chips = []
    if isinstance(chips_in, list):
        for i, c in enumerate(chips_in):
            if not isinstance(c, dict):
                ctx.err(f"{p}.chips.{i}", "Expected object")
                continue
            chips.append(
                {
                    "label": _req_str(ctx, c, "label", f"{p}.chips.{i}"),
                    "items": _str_array(ctx, c, "items", f"{p}.chips.{i}", min_len=1),
                }
            )
    elif "chips" in b:
        ctx.err(f"{p}.chips", "Expected array")
    _check_len(ctx, chips, f"{p}.chips", 0, 4)
    out["chips"] = chips

    if b.get("highlight") is not None:
        out["highlight"] = _highlight(ctx, b.get("highlight"), f"{p}.highlight")
    return out


def _label_value_array(ctx, b, key, p, *, min_len, max_len, value_key="value"):
    arr_in = b.get(key, _MISSING)
    out = []
    if arr_in is _MISSING:
        ctx.err(f"{p}.{key}", "Required")
        return out
    if not isinstance(arr_in, list):
        ctx.err(f"{p}.{key}", "Expected array")
        return out
    for i, it in enumerate(arr_in):
        if not isinstance(it, dict):
            ctx.err(f"{p}.{key}.{i}", "Expected object")
            continue
        out.append(
            {
                "label": _req_str(ctx, it, "label", f"{p}.{key}.{i}"),
                value_key: _req_str(ctx, it, value_key, f"{p}.{key}.{i}"),
            }
        )
    _check_len(ctx, out, f"{p}.{key}", min_len, max_len)
    return out


def _block_tech_grid(ctx, b, p):
    out = {"type": "techGrid", **_section_base(ctx, b, p)}
    out["items"] = _label_value_array(ctx, b, "items", p, min_len=1, max_len=12)
    note = _opt_str(ctx, b, "note", p)
    if note is not None:
        out["note"] = note
    return out


def _block_value_grid(ctx, b, p):
    out = {"type": "valueGrid", **_section_base(ctx, b, p)}
    lead = _opt_str(ctx, b, "lead", p)
    if lead is not None:
        out["lead"] = lead
    items_in = b.get("items", _MISSING)
    items = []
    if items_in is _MISSING:
        ctx.err(f"{p}.items", "Required")
    elif not isinstance(items_in, list):
        ctx.err(f"{p}.items", "Expected array")
    else:
        for i, it in enumerate(items_in):
            if not isinstance(it, dict):
                ctx.err(f"{p}.items.{i}", "Expected object")
                continue
            items.append(
                {
                    "title": _req_str(ctx, it, "title", f"{p}.items.{i}"),
                    "body": _req_str(ctx, it, "body", f"{p}.items.{i}"),
                }
            )
        _check_len(ctx, items, f"{p}.items", 1, 8)
    out["items"] = items
    if b.get("highlight") is not None:
        out["highlight"] = _highlight(ctx, b.get("highlight"), f"{p}.highlight")
    return out


def _block_highlight(ctx, b, p):
    out = {"type": "highlight", **_section_base(ctx, b, p)}
    out["label"] = _req_str(ctx, b, "label", p)
    out["value"] = _req_str(ctx, b, "value", p)
    note = _opt_str(ctx, b, "note", p)
    if note is not None:
        out["note"] = note
    return out


def _block_warm_note(ctx, b, p):
    out = {"type": "warmNote", **_section_base(ctx, b, p)}
    out["noteTitle"] = _req_str(ctx, b, "noteTitle", p)
    out["body"] = _req_str(ctx, b, "body", p)
    return out


def _block_table(ctx, b, p):
    out = {"type": "table", **_section_base(ctx, b, p)}
    if b.get("headers") is not None:
        out["headers"] = _str_array(ctx, b, "headers", p)
    rows_in = b.get("rows", _MISSING)
    rows = []
    if rows_in is _MISSING:
        ctx.err(f"{p}.rows", "Required")
    elif not isinstance(rows_in, list):
        ctx.err(f"{p}.rows", "Expected array")
    else:
        for i, r in enumerate(rows_in):
            if not isinstance(r, dict):
                ctx.err(f"{p}.rows.{i}", "Expected object")
                continue
            row = {"cells": _str_array(ctx, r, "cells", f"{p}.rows.{i}", min_len=1)}
            if r.get("isTotal") is not None:
                row["isTotal"] = _bool(ctx, r, "isTotal", f"{p}.rows.{i}", False)
            rows.append(row)
        _check_len(ctx, rows, f"{p}.rows", 1, None)
    out["rows"] = rows
    return out


def _block_pricing(ctx, b, p):
    out = {"type": "pricing", **_section_base(ctx, b, p)}
    preset = b.get("preset", "standard-ab")
    if preset != "standard-ab":
        ctx.err(f"{p}.preset", "Invalid literal value, expected 'standard-ab'")
    out["preset"] = "standard-ab"
    out["valueA"] = _pos_number(ctx, b, "valueA", p, 20000)
    out["subscription"] = _pos_number(ctx, b, "subscription", p, 1000)
    out["minutes"] = _pos_number(ctx, b, "minutes", p, 1000)
    out["estimated"] = _bool(ctx, b, "estimated", p, False)
    note = _opt_str(ctx, b, "note", p)
    if note is not None:
        out["note"] = note
    return out


def _block_cta(ctx, b, p):
    out = {"type": "cta", **_section_base(ctx, b, p)}
    out["ctaTitle"] = _req_str(ctx, b, "ctaTitle", p)
    out["description"] = _req_str(ctx, b, "description", p)
    actions_in = b.get("actions", _MISSING)
    actions = []
    if actions_in is _MISSING:
        ctx.err(f"{p}.actions", "Required")
    elif not isinstance(actions_in, list):
        ctx.err(f"{p}.actions", "Expected array")
    else:
        for i, a in enumerate(actions_in):
            if not isinstance(a, dict):
                ctx.err(f"{p}.actions.{i}", "Expected object")
                continue
            act = {
                "label": _req_str(ctx, a, "label", f"{p}.actions.{i}"),
                "href": _req_str(ctx, a, "href", f"{p}.actions.{i}"),
            }
            if a.get("ghost") is not None:
                act["ghost"] = _bool(ctx, a, "ghost", f"{p}.actions.{i}", False)
            actions.append(act)
        _check_len(ctx, actions, f"{p}.actions", 1, 3)
    out["actions"] = actions
    return out


_BLOCK_DISPATCH = {
    "prose": _block_prose,
    "checklist": _block_checklist,
    "stats": _block_stats,
    "techGrid": _block_tech_grid,
    "valueGrid": _block_value_grid,
    "highlight": _block_highlight,
    "warmNote": _block_warm_note,
    "table": _block_table,
    "pricing": _block_pricing,
    "cta": _block_cta,
}


def _validate_hero(ctx: _Ctx, hero: Any) -> dict:
    p = "hero"
    if not isinstance(hero, dict):
        ctx.err(p, "Required")
        return {}
    out: dict[str, Any] = {}
    eyebrow = _opt_str(ctx, hero, "eyebrow", p)
    if eyebrow is not None:
        out["eyebrow"] = eyebrow
    out["titleLead"] = _req_str(ctx, hero, "titleLead", p)
    out["titleEm"] = _req_str(ctx, hero, "titleEm", p)
    out["subtitle"] = _req_str(ctx, hero, "subtitle", p)
    meta_in = hero.get("meta", [])
    meta = []
    if isinstance(meta_in, list):
        for i, m in enumerate(meta_in):
            if not isinstance(m, dict):
                ctx.err(f"{p}.meta.{i}", "Expected object")
                continue
            meta.append(
                {
                    "label": _req_str(ctx, m, "label", f"{p}.meta.{i}"),
                    "value": _req_str(ctx, m, "value", f"{p}.meta.{i}"),
                }
            )
    elif "meta" in hero:
        ctx.err(f"{p}.meta", "Expected array")
    _check_len(ctx, meta, f"{p}.meta", 0, 4)
    out["meta"] = meta
    return out


def validate_offer_data(input: Any):
    """Return (True, normalized_data) or (False, error_string)."""
    ctx = _Ctx()
    if not isinstance(input, dict):
        return False, "(root): Expected object"

    data: dict[str, Any] = {}

    # brand is OPTIONAL since Feature 5 (per-org branding drives theme/contacts,
    # not this enum). If present it must still be valid; if absent it's omitted.
    brand = input.get("brand", _MISSING)
    if brand is _MISSING or brand is None:
        pass
    elif brand in BRANDS:
        data["brand"] = brand
    else:
        ctx.err("brand", f"Invalid enum value. Expected one of: {', '.join(BRANDS)}")

    data["hero"] = _validate_hero(ctx, input.get("hero"))

    sections_in = input.get("sections", _MISSING)
    sections = []
    if sections_in is _MISSING:
        ctx.err("sections", "Required")
    elif not isinstance(sections_in, list):
        ctx.err("sections", "Expected array")
    else:
        for i, blk in enumerate(sections_in):
            sp = f"sections.{i}"
            if not isinstance(blk, dict):
                ctx.err(sp, "Expected object")
                continue
            btype = blk.get("type")
            if btype not in _BLOCK_DISPATCH:
                ctx.err(
                    f"{sp}.type",
                    f"Invalid discriminator value. Expected one of: {', '.join(BLOCK_TYPES)}",
                )
                continue
            sections.append(_BLOCK_DISPATCH[btype](ctx, blk, sp))
        _check_len(ctx, sections, "sections", 1, 14)
    data["sections"] = sections

    if ctx.issues:
        return False, "; ".join(ctx.issues[:12])
    return True, data
