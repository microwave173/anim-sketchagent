"""Incremental Path3D roles: DeepSeek-V4.1-Flash for text and four-view review."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = next(
    (parent for parent in HERE.parents if (parent / "versions" / "path3d_v1").exists()),
    HERE.parents[1],
)
PILOT = ROOT / "experiments" / "grpo_sa_pilot"
for p in (
    ROOT,
    ROOT / "versions" / "path3d_v1",
    ROOT / "versions" / "path3d_json_v1",
    ROOT / "versions" / "v1.4",
    ROOT / "versions" / "path3d_incremental_base_v1",
    PILOT,
):
    sp = str(p)
    if sp in sys.path:
        sys.path.remove(sp)
    sys.path.insert(0, sp)
if str(HERE) in sys.path:
    sys.path.remove(str(HERE))
sys.path.insert(0, str(HERE))

from drawer_v14.three_d.patch import PlannerReview  # noqa: E402
from path3d_json_agents.common import image_url  # noqa: E402
from path3d_json_agents.incremental import (  # noqa: E402
    STRUCTURED_EDITOR_SYSTEM_PROMPT as BASE_EDITOR_SYSTEM_PROMPT,
    STRUCTURED_PLANNER_SYSTEM_PROMPT as BASE_PLANNER_SYSTEM_PROMPT,
    StructuredPatchParseError,
    StructuredPlannerRole,
)
from path3d_json_agents.structured_patch import StructuredPath3DPatch  # noqa: E402
from terra_client import call_deepseek, data_url, parse_json_obj  # noqa: E402
from prompts import ANIMAL_DRAWING, INK_STYLE  # noqa: E402

# Still-sketch Editor prompt says delete old ids and add *new* ids. Animation forbids that.
ANIM_PLANNER_SYSTEM_PROMPT = BASE_PLANNER_SYSTEM_PROMPT.replace(
    "The Editor decides how to draw and may preserve, replace, or rebuild any geometry.",
    "The Editor decides geometry, but must keep stroke ids. Do not ask for a rebuild that invents new names.",
)
ANIM_EDITOR_SYSTEM_PROMPT = BASE_EDITOR_SYSTEM_PROMPT.replace(
    "4. Existing strokes are replaced by deleting their IDs and adding new IDs in the same patch.",
    "4. Existing strokes are replaced by deleting their IDs and adding strokes that REUSE those exact same IDs. "
    "Never rename. Forbidden suffixes: _new, _emerge, _2, _b, _v2.",
).replace(
    '"id":"new_unique_id"',
    '"id":"existing_id"',
) + """

Animation identity (hard):
- Every plan part id (e.g. actor_head, scenery_post) must exist as an exact stroke id. Helpers only: "<part_id>_...".
- Changing pose is the same id with new commands, not actor_head_new.
- Do not replace a required part with only helpers (scenery_post_front is not scenery_post).
- First-key ids are frozen for later keys: include each of them exactly once.

Exact command schemas (hard):
- M or L: {"command":"M","point":[x,y,z]} or {"command":"L","point":[x,y,z]}.
- Q3 is quadratic and has ONE control point named "control":
  {"command":"Q3","control":[x,y,z],"end":[x,y,z]}.
  Never put control_1 or control_2 in Q3. If two control points are needed, use C3.
- C3 is cubic: {"command":"C3","control_1":[x,y,z],"control_2":[x,y,z],"end":[x,y,z]}.
- Z: {"command":"Z"} only.
- These field names are literal; do not add style, point, or other fields to a curve command.

Animals (hard): """ + ANIMAL_DRAWING + " " + INK_STYLE + """
"""


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
        "stroke_count",
    }
    found = sorted(forbidden & set(instruction))
    if found:
        raise ValueError("planner crossed the drawing boundary: " + ", ".join(found))
    allowed = {"objective", "priority", "success_criteria", "scope"}
    unexpected = sorted(set(instruction) - allowed)
    if unexpected:
        raise ValueError("planner instruction has unsupported fields: " + ", ".join(unexpected))


# Explicit experiment override; None preserves the original per-role defaults.
REASONING_EFFORT_OVERRIDE: str | None = None

SPATIAL_VOLUME_CONSTRAINT = 'Spatial volume (hard): Solid spherical bodies must be genuine spatial wireframes, using at least three mutually perpendicular great-circle contours under their existing part id, not a flat circular billboard. Solid boxes/slabs must have depth and connected front/back edges. Front, side and top must all reveal volume. Do not force all curves into one depth plane. For an explosion, fragments travel in x, y and z; a destroyed spherical body must collapse into the explosion core rather than remain as an intact sphere. Any anchored emitter stays rigid and stationary. This describes shape and motion requirements, not supplied coordinates.'
ANIM_PLANNER_SYSTEM_PROMPT += "\n" + SPATIAL_VOLUME_CONSTRAINT
ANIM_EDITOR_SYSTEM_PROMPT += "\n" + SPATIAL_VOLUME_CONSTRAINT

RIGID_CHAIN_CONTACT_CONSTRAINT = 'For a chain of tipping rigid tiles: each tile rotates about its ORIGINAL bottom-right floor-level edge, preserving height, thickness and depth. No pivot may slide or rise in the settled pose. The earlier left tile rests ON TOP OF the later tile to its right; the last rightmost tile rests directly on the floor. Thus the final row is a low overlapping shingle, earlier tiles slightly inclined with their tips supported by the next tile, all pivots still on the floor. Never draw a staircase of flat tiles with progressively lifted bases. Each downstream tile remains upright until the upstream neighbor actually contacts it. Check this support order in the director rewrite, every key and all four views.'
ANIM_PLANNER_SYSTEM_PROMPT += "\n" + RIGID_CHAIN_CONTACT_CONSTRAINT
ANIM_EDITOR_SYSTEM_PROMPT += "\n" + RIGID_CHAIN_CONTACT_CONSTRAINT

def _call_json(*, system: str, content: str | list[dict[str, Any]], vision: bool, max_tokens: int) -> tuple[dict[str, Any], str]:
    last_raw = ""
    last_err: Exception | None = None
    for attempt in range(2):
        msgs = _messages(system, content)
        last_raw = call_deepseek(
            msgs,
            max_tokens=max(max_tokens, 65536) if REASONING_EFFORT_OVERRIDE else max_tokens,
            temperature=0.2 if vision else 0.4,
            timeout=600,
            model="deepseek-flash",
            reasoning_effort=REASONING_EFFORT_OVERRIDE or ("high" if not vision else "low"),
            thinking=(REASONING_EFFORT_OVERRIDE != "low") if REASONING_EFFORT_OVERRIDE else not vision,
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


class GlmDsPlanner(StructuredPlannerRole):
    def create_plan(self, *, prompt: str) -> dict[str, Any]:
        value, _ = _call_json(
            system=ANIM_PLANNER_SYSTEM_PROMPT,
            content=(
                f"Target: {prompt}\n"
                'Return {"overall_goal":"...","priorities":["..."],"completion_criteria":["..."]}. '
                "Keep it visual and high-level."
            ),
            vision=False,
            max_tokens=4096,
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
                    "The contact sheet is front, side, top, perspective. Return "
                    '{"decision":"continue|retry|rollback|finish|fail",'
                    '"assessment":{"strengths":["..."],"problems":["..."]},'
                    '"instruction":{"objective":"...","priority":"...","success_criteria":["..."],'
                    '"scope":"optional high-level scope"},'
                    '"rollback_revision":null,"reason":"..."}. '
                    "For continue/retry, instruction is required. Use at most 2 strengths, 3 problems, "
                    "and 3 success criteria. Do not prescribe drawing operations."
                ),
            },
            {"type": "input_image", "image_url": image_url(Path(kwargs["current_contact_sheet"]))},
        ]
        last_error: Exception | None = None
        for attempt in range(2):
            value, _ = _call_json(
                system=ANIM_PLANNER_SYSTEM_PROMPT,
                content=content,
                vision=True,
                max_tokens=8192,
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
                    + "\nReturn the exact requested review schema. decision must be one of "
                    + "continue|retry|rollback|finish|fail. continue/retry requires a non-empty instruction."
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
                        "The requested pose reads clearly in all four views.",
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
        content: list[dict[str, Any]] = [
            {
                "type": "input_text",
                "text": (
                    f"Target: {prompt}\nPlan: {json.dumps(plan, ensure_ascii=False)}\n"
                    "Choose the best historical revision by visible recognizability, structure, "
                    "proportions, and four-view consistency. "
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
                    {"type": "input_image", "image_url": image_url(Path(item["contact_sheet_absolute"]))},
                ]
            )
        value, _ = _call_json(
            system=ANIM_PLANNER_SYSTEM_PROMPT, content=content, vision=True, max_tokens=4096
        )
        selected = str(value.get("best_revision", ""))
        if selected not in valid:
            raise ValueError(f"planner selected unknown revision: {selected!r}")
        return selected, str(value.get("reason", "")).strip()


class GlmDsEditor:
    def edit(self, **kwargs: Any) -> tuple[StructuredPath3DPatch, str]:
        content = [
            {
                "type": "input_text",
                "text": f"""Target: {kwargs['prompt']}
High-level plan: {json.dumps(kwargs['plan'], ensure_ascii=False)}
Director objective: {json.dumps(kwargs['instruction'], ensure_ascii=False)}
Previous validation error: {kwargs.get('previous_error') or 'None'}
Previous invalid patch: {json.dumps(kwargs.get('previous_patch'), ensure_ascii=False) if kwargs.get('previous_patch') else 'None'}
Complete current scene: {json.dumps(kwargs['current_scene'], ensure_ascii=False)}
The contact sheet is front, side, top, perspective. Interpret the target and decide the drawing solution yourself. Return one atomic patch.""",
            },
            {"type": "input_image", "image_url": image_url(Path(kwargs["current_contact_sheet"]))},
        ]
        value, raw = _call_json(
            system=ANIM_EDITOR_SYSTEM_PROMPT, content=content, vision=True, max_tokens=16000
        )
        try:
            return StructuredPath3DPatch.from_dict(value), raw
        except Exception as exc:
            raise StructuredPatchParseError(str(exc), raw=raw, value=value) from exc
