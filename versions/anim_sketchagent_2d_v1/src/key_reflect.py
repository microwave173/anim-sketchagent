"""One-shot key quality loop: look → compact experience → redraw → visual select.

This is Reflexion-style (verbal memory, full retry), not a Path2D patch editor.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from terra_client import call_sol, data_url, parse_json_obj

EXPERIENCE_KEYS = ("rules",)
MAX_ITEMS_PER = 6
MAX_ITEMS = 6
MAX_ITEM_CHARS = 220
PATHISH = re.compile(r"\b[MLQCZ]\s+-?\d", re.I)
COORDISH = re.compile(r"\(\s*-?\d+(?:\.\d+)?\s*,\s*-?\d+")

KEY_EXPERIENCE_SYSTEM = """You review one 2D stick-figure keyframe PNG. A later artist will REDRAW from scratch with only your caution rules plus the drawing system prompt — they will not see this PNG or any previous paths.

World: +x right, +y up. Larger y is sky; ground near y=-0.7. Heads should be round; attached parts share joints.

Write ONLY caution rules: what went wrong and must not recur. Do not list strengths, do not say what to keep, do not patch geometry.

Return JSON only:
{"ok":true|false,"rules":["..."]}

Rules:
- Each item is one imperative caution (e.g. "Do not attach limbs at the head center; neck is under the head, hip is lower y.").
- At most 6 items. Each item is one sentence, max 220 characters.
- Cover head placement/facing, torso tilt, joint connectivity, and beat readability when those fail.
- No coordinates, no path strings, no stroke-id edits, no "move X to Y".
- ok=true only if the pose is usable (readable figure, +y up, parts attached, beat visible).
- If ok=false, rules must be non-empty. If ok=true you may return an empty rules array.
"""

KEY_SELECTOR_SYSTEM = """You compare two drawings of the SAME 2D keyframe pose. Prefer the redraw unless it is clearly worse.

Worse means: flipped/upside-down, missing the beat, broken joints, unreadable scribble, or lost the character.

Return JSON only: {"winner":"draft"|"redraw","reason":"..."}.
"""


def format_experience(experience: dict[str, Any] | None) -> str:
    if not experience:
        return "None; solve the pose directly."
    return json.dumps(
        {
            "ok": bool(experience.get("ok")),
            "rules": list(experience.get("rules") or []),
        },
        ensure_ascii=False,
        indent=2,
    )


def _clean_items(raw: Any, key: str) -> list[str]:
    if not isinstance(raw, list):
        raise ValueError(f"experience.{key} must be an array")
    if len(raw) > MAX_ITEMS_PER:
        raise ValueError(f"experience.{key} has {len(raw)} items; maximum is {MAX_ITEMS_PER}")
    cleaned: list[str] = []
    for item in raw:
        text = str(item).strip()
        if not text:
            raise ValueError(f"experience.{key} contains an empty item")
        if len(text) > MAX_ITEM_CHARS:
            raise ValueError(f"experience.{key} item exceeds {MAX_ITEM_CHARS} characters")
        low = text.lower()
        if PATHISH.search(text) or COORDISH.search(text):
            raise ValueError(f"experience.{key} looks like a path/coordinate patch")
        if any(tok in low for tok in ("update_strokes", "delete_stroke", "change the path", "move stroke")):
            raise ValueError(f"experience.{key} looks like an editor patch")
        cleaned.append(text)
    return cleaned


def validate_experience(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("experience must be an object")
    ok = value.get("ok")
    if not isinstance(ok, bool):
        raise ValueError("experience.ok must be a boolean")
    raw_rules = value.get("rules")
    if raw_rules is None:
        raw_rules = value.get("avoid")
    rules = _clean_items(raw_rules if raw_rules is not None else [], "rules")
    if len(rules) > MAX_ITEMS:
        raise ValueError(f"experience has {len(rules)} items; maximum is {MAX_ITEMS}")
    if not ok and not rules:
        raise ValueError("ok=false requires at least one rule")
    return {"ok": ok, "rules": rules}


def should_redraw(experience: dict[str, Any]) -> bool:
    return bool(experience.get("rules")) or not bool(experience.get("ok"))


def _messages(system: str, content: list[dict[str, Any]]) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    for item in content:
        kind = item.get("type")
        if kind == "input_text":
            parts.append({"type": "text", "text": item.get("text", "")})
        elif kind == "input_image":
            url = item.get("image_url") or ""
            if not str(url).startswith("data:"):
                url = data_url(Path(str(url)))
            parts.append({"type": "image_url", "image_url": {"url": url}})
        else:
            parts.append(item)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": parts},
    ]


def _call_vision_json(system: str, content: list[dict[str, Any]], *, max_tokens: int) -> tuple[dict[str, Any], str]:
    last_raw, last_err = "", None
    payload = content
    for _ in range(2):
        last_raw = call_sol(
            _messages(system, payload),
            max_tokens=max_tokens,
            temperature=0.2,
            timeout=240,
            reasoning_effort="low",
        )
        try:
            return parse_json_obj(last_raw), last_raw
        except Exception as exc:
            last_err = exc
            payload = [
                {
                    "type": "input_text",
                    "text": "Repair JSON only.\n" + last_raw[:8000],
                }
            ]
    raise ValueError(f"vision JSON failed: {last_err}") from last_err


def review_key_experience(
    png: Path,
    *,
    plan: dict,
    key: dict,
    key_i: int,
    n_keys: int,
) -> tuple[dict[str, Any], str]:
    text = (
        f"This PNG is key {key_i}/{n_keys} named '{key.get('name')}' (beat: {key.get('beat', '')}).\n"
        f"Shot: {plan.get('action') or ''}\n"
        f"Staging: {plan.get('layout_notes') or ''}\n"
        f"Scale: {plan.get('people_scale') or ''}\n"
        "Inspect the drawing. Return the experience JSON."
    )
    content = [
        {"type": "input_text", "text": text},
        {"type": "input_image", "image_url": data_url(png)},
    ]
    last_err: Exception | None = None
    raw = ""
    for _ in range(2):
        value, raw = _call_vision_json(KEY_EXPERIENCE_SYSTEM, content, max_tokens=900)
        try:
            return validate_experience(value), raw
        except Exception as exc:
            last_err = exc
            content = [
                {
                    "type": "input_text",
                    "text": (
                        f"{text}\n\nPrevious JSON failed validation: {exc}. "
                        f"Previous value: {json.dumps(value, ensure_ascii=False)[:4000]}\n"
                        "Return a corrected experience object with ok and rules only. No preserve, no coordinates, no path strings."
                    ),
                },
                {"type": "input_image", "image_url": data_url(png)},
            ]
    raise ValueError(f"experience validation failed: {last_err}") from last_err


def select_key_winner(
    draft_png: Path,
    redraw_png: Path,
    *,
    plan: dict,
    key: dict,
) -> tuple[str, str, str]:
    content = [
        {
            "type": "input_text",
            "text": (
                f"Same key '{key.get('name')}' beat={key.get('beat', '')}. "
                f"Shot: {plan.get('action') or ''}\n"
                "First image is DRAFT. Second image is REDRAW after experience. "
                'Return {"winner":"draft"|"redraw","reason":"..."}.'
            ),
        },
        {"type": "input_text", "text": "DRAFT"},
        {"type": "input_image", "image_url": data_url(draft_png)},
        {"type": "input_text", "text": "REDRAW"},
        {"type": "input_image", "image_url": data_url(redraw_png)},
    ]
    try:
        value, raw = _call_vision_json(KEY_SELECTOR_SYSTEM, content, max_tokens=400)
        winner = str(value.get("winner") or "").strip().lower()
        if winner not in {"draft", "redraw"}:
            raise ValueError(f"unknown winner {winner!r}")
        return winner, str(value.get("reason") or "").strip(), raw
    except Exception as exc:
        return "redraw", f"selector fallback to redraw: {exc}", ""
