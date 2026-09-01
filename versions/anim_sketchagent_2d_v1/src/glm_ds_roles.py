"""Incremental Path2D roles: gpt-5.6-sol for text and visual review."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = next(
    (parent for parent in HERE.parents if (parent / "versions" / "path2d_v1").exists()),
    HERE.parents[1],
)
PILOT = ROOT / "experiments" / "grpo_sa_pilot"
for p in (ROOT, ROOT / "versions" / "path2d_v1", PILOT, HERE):
    sp = str(p)
    if sp in sys.path:
        sys.path.remove(sp)
    sys.path.insert(0, sp)

from terra_client import call_sol, data_url, parse_json_obj  # noqa: E402

from incremental import Path2DPatch, Path2DPatchParseError, PlannerReview  # noqa: E402


ANIM_PLANNER_SYSTEM_PROMPT = """You are the visual director of an incremental 2D stick-figure sketch.

Review the target and the current PNG. Decide whether to continue, retry, finish, roll back, or fail. Give the Editor one high-level objective and visual success criteria.

Do not design curves. Do not specify coordinates, stroke counts, stroke IDs, additions, or deletions. The Editor decides geometry but must keep stroke ids.

World: +x right, +y up. Larger y is sky; ground is near y=-0.7. Ears and head-top sit above the head center.

Return only the requested JSON object."""


ANIM_EDITOR_SYSTEM_PROMPT = """You are a 2D stick-figure sketch artist editing one Path2D line drawing.

Output rules:
1. Return one JSON patch with delete_stroke_ids, add_strokes, update_strokes, and summary.
2. Every added/updated stroke has id, path, description, and group.
3. Paths use M/L/Q/C/Z only, coordinates in [-1,1], +x right, +y up (larger y is sky).
4. Existing strokes are replaced by reusing the exact same id (update_strokes, or delete+add with the same id). Never rename. Forbidden suffixes: _new, _emerge, _2, _b, _v2.

Geometry rules:
1. Standing height 1/5–1/4 of the ground-line length. Hip halfway from head-top to feet.
2. Q/C for swinging/bent limbs, spines, tails, hanging lines, round heads. Straight L for ground, poles, posts, flat edges, and rigid shafts. Do not Q a vertical post or the ground. Heads MUST be round Q loops (four or more Q, then Z). Do not draw heads as polygons of L.
3. Connectivity: every attached pair shares the exact joint (x,y). Head/arms meet the neck; legs meet the hip (neck higher y, hip lower y); ears on the crown; tail at the rump; held props at the hand. No floating parts.
4. Follow the director's objective, but decide the geometry yourself.

Animation identity (hard):
- Every plan part id must exist as an exact stroke id. Helpers only: "<part_id>_...".
- Changing pose is the same id with a new path, not cat_head_new.
- First-key ids are frozen for later keys: include each of them exactly once.

Return only:
{"delete_stroke_ids":[],"update_strokes":[{"id":"existing_id","path":"M ...","description":"...","group":"..."}],"add_strokes":[{"id":"...","path":"M ...","description":"...","stroke":"#111111","stroke_width":3,"opacity":1,"group":"..."}],"summary":"..."}
Never return SVG tags or 3D xyz / Q3 / C3."""


def _chat_content(content: str | list[dict[str, Any]]) -> str | list[dict[str, Any]]:
    if isinstance(content, str):
        return content
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
        elif kind == "text":
            parts.append(item)
        elif kind == "image_url":
            parts.append(item)
    return parts


def _messages(system: str, content: str | list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": _chat_content(content)},
    ]


def _validate_directive(value: dict[str, Any]) -> None:
    instruction = value.get("instruction")
    if not isinstance(instruction, dict):
        return
    forbidden = {
        "add",
        "remove",
        "remove_or_replace",
        "coordinate_constraints",
        "preserve_stroke_ids",
        "delete_stroke_ids",
        "add_strokes",
        "update_strokes",
        "stroke_count",
    }
    found = sorted(forbidden & set(instruction))
    if found:
        raise ValueError("planner crossed the drawing boundary: " + ", ".join(found))
    allowed = {"objective", "priority", "success_criteria", "scope"}
    unexpected = sorted(set(instruction) - allowed)
    if unexpected:
        raise ValueError("planner instruction has unsupported fields: " + ", ".join(unexpected))


def _call_json(*, system: str, content: str | list[dict[str, Any]], vision: bool, max_tokens: int) -> tuple[dict[str, Any], str]:
    last_raw = ""
    last_err: Exception | None = None
    for attempt in range(2):
        msgs = _messages(system, content)
        last_raw = call_sol(
            msgs,
            max_tokens=max_tokens,
            temperature=0.2 if vision else 0.4,
            timeout=300,
            reasoning_effort="high" if not vision else "low",
            thinking=True,
        )
        try:
            return parse_json_obj(last_raw), last_raw
        except Exception as exc:
            last_err = exc
            content = (
                "Repair the JSON below without changing its intended content. Return JSON only.\n"
                f"{last_raw[:8000]}"
            )
    raise ValueError(f"JSON parse failed: {last_err}") from last_err


class GlmDsPlanner:
    def create_plan(self, *, prompt: str) -> dict[str, Any]:
        value, _ = _call_json(
            system=ANIM_PLANNER_SYSTEM_PROMPT,
            content=(
                f"Target: {prompt}\n"
                'Return {"overall_goal":"...","priorities":["..."],"completion_criteria":["..."]}. '
                "Keep it visual and high-level."
            ),
            vision=False,
            max_tokens=900,
        )
        return value

    def review(self, **kwargs: Any) -> PlannerReview:
        prompt = kwargs["prompt"]
        content: list[dict[str, Any]] = [
            {
                "type": "input_text",
                "text": (
                    f"Target: {prompt}\nRound: {kwargs['round_index']}/{kwargs['max_rounds']}\n"
                    f"Revision: {kwargs['current_revision']}\n"
                    f"Plan: {json.dumps(kwargs['plan'], ensure_ascii=False)}\n"
                    f"History summary: {json.dumps(kwargs['history'], ensure_ascii=False)}\n"
                    f"Last validation error: {kwargs.get('last_error') or 'None'}\n"
                    "The image is one 2D sketch, +x right +y up. Return "
                    '{"decision":"continue|retry|rollback|finish|fail",'
                    '"assessment":{"strengths":["..."],"problems":["..."]},'
                    '"instruction":{"objective":"...","priority":"...","success_criteria":["..."],'
                    '"scope":"optional high-level scope"},'
                    '"rollback_revision":null,"reason":"..."}. '
                    "For continue/retry, instruction is required. Use at most 2 strengths, 3 problems, "
                    "and 3 success criteria. Do not prescribe drawing operations."
                ),
            },
            {"type": "input_image", "image_url": data_url(Path(kwargs["current_png"]))},
        ]
        last_error: Exception | None = None
        for _attempt in range(2):
            value, _ = _call_json(
                system=ANIM_PLANNER_SYSTEM_PROMPT,
                content=content,
                vision=True,
                max_tokens=2600,
            )
            try:
                _validate_directive(value)
                return PlannerReview.from_dict(value)
            except Exception as exc:
                last_error = exc
                content[0]["text"] = (
                    str(content[0]["text"])
                    + "\n\nYour previous JSON was structurally invalid: "
                    + f"{type(exc).__name__}: {exc}. Previous value: "
                    + json.dumps(value, ensure_ascii=False)[:6000]
                    + "\nReturn the exact requested review schema."
                )
        return PlannerReview.from_dict(
            {
                "decision": "continue",
                "assessment": {
                    "strengths": [],
                    "problems": ["The visual reviewer returned an invalid directive; continue conservatively."],
                },
                "instruction": {
                    "objective": "Improve prompt fidelity and complete every named semantic part.",
                    "priority": "Preserve existing valid geometry, identity, proportions, and anchored structure.",
                    "success_criteria": [
                        "All requested parts are present with exact ids.",
                        "The requested pose reads clearly; +y is up.",
                    ],
                    "scope": "Make one conservative structural or pose improvement.",
                },
                "rollback_revision": None,
                "reason": f"Fallback after two invalid visual directives: {last_error}",
            }
        )

    def select_best(self, *, prompt: str, plan: dict[str, Any], revisions: list[dict[str, Any]]) -> tuple[str, str]:
        if not revisions:
            raise ValueError("cannot select without revisions")
        if len(revisions) == 1:
            return str(revisions[0]["revision_id"]), "only non-empty revision"
        content: list[dict[str, Any]] = [
            {
                "type": "input_text",
                "text": (
                    f"Target: {prompt}\nPlan: {json.dumps(plan, ensure_ascii=False)}\n"
                    "Choose the best historical revision by visible recognizability, structure, "
                    "proportions, and +y-up orientation. "
                    'Return {"best_revision":"revision_NNN","reason":"..."}.'
                ),
            }
        ]
        valid = set()
        for item in revisions:
            valid.add(item["revision_id"])
            content.extend(
                [
                    {"type": "input_text", "text": f"Revision: {item['revision_id']}"},
                    {"type": "input_image", "image_url": data_url(Path(item["png_absolute"]))},
                ]
            )
        value, _ = _call_json(
            system=ANIM_PLANNER_SYSTEM_PROMPT, content=content, vision=True, max_tokens=900
        )
        selected = str(value.get("best_revision", ""))
        if selected not in valid:
            raise ValueError(f"planner selected unknown revision: {selected!r}")
        return selected, str(value.get("reason", "")).strip()


class GlmDsEditor:
    def edit(self, **kwargs: Any) -> tuple[Path2DPatch, str]:
        content = [
            {
                "type": "input_text",
                "text": f"""Target: {kwargs['prompt']}
High-level plan: {json.dumps(kwargs['plan'], ensure_ascii=False)}
Director objective: {json.dumps(kwargs['instruction'], ensure_ascii=False)}
Previous validation error: {kwargs.get('previous_error') or 'None'}
Previous invalid patch: {json.dumps(kwargs.get('previous_patch'), ensure_ascii=False) if kwargs.get('previous_patch') else 'None'}
Complete current scene: {json.dumps(kwargs['current_scene'], ensure_ascii=False)}
The PNG is one 2D sketch, +x right +y up. Interpret the target and decide the drawing solution yourself. Return one atomic patch.""",
            },
            {"type": "input_image", "image_url": data_url(Path(kwargs["current_png"]))},
        ]
        value, raw = _call_json(
            system=ANIM_EDITOR_SYSTEM_PROMPT, content=content, vision=True, max_tokens=8000
        )
        try:
            return Path2DPatch.from_dict(value), raw
        except Exception as exc:
            raise Path2DPatchParseError(str(exc), raw=raw, value=value) from exc
