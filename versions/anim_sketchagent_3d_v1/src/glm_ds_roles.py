"""Incremental Path3D roles: GLM for text, DeepSeek vision when an image is present."""
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
from terra_client import call_deepseek, call_glm, data_url, parse_json_obj  # noqa: E402

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
- Every plan part id (e.g. walker_head, pillar) must exist as an exact stroke id. Helpers only: "<part_id>_...".
- Changing pose is the same id with new commands, not walker_head_new.
- Do not replace a required part with only helpers (shaft_box_front is not shaft_box).
- First-key ids are frozen for later keys: include each of them exactly once.
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


def _call_json(*, system: str, content: str | list[dict[str, Any]], vision: bool, max_tokens: int) -> tuple[dict[str, Any], str]:
    last_raw = ""
    last_err: Exception | None = None
    for attempt in range(2):
        msgs = _messages(system, content)
        if vision:
            last_raw = call_deepseek(msgs, max_tokens=max_tokens, temperature=0.2, timeout=240)
        else:
            last_raw = call_glm(msgs, max_tokens=max_tokens, temperature=0.4, timeout=240)
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
            system=ANIM_PLANNER_SYSTEM_PROMPT, content=content, vision=True, max_tokens=900
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
            system=ANIM_EDITOR_SYSTEM_PROMPT, content=content, vision=True, max_tokens=8000
        )
        try:
            return StructuredPath3DPatch.from_dict(value), raw
        except Exception as exc:
            raise StructuredPatchParseError(str(exc), raw=raw, value=value) from exc
