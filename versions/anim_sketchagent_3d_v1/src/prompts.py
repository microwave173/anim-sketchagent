"""Pose-to-pose planner prompts for 3D Path3D clips."""
from __future__ import annotations

import json

MIN_FRAMES = 4
MAX_FRAMES = 20
MIN_KEYS = 2
MAX_KEYS = 6
MIN_PARTS = 6
MAX_PARTS = 20

KEY_PLAN_SYSTEM = """You are a sketch planner for pose-to-pose 3D wireframe animation.
Return JSON only. No markdown.

A 3D drawer will draw ONLY the key poses as Path3D spatial line sketches (front/side/top/perspective).
Inbetweens are a later one-shot redraw of the SAME named parts — the key drawer will not see them.
You pick a few extremes, not a full frame list. YOU choose how many keys: at least 2, at most 6.
Two keys is enough for one continuous travel. Add a key only when interpolation cannot invent that beat (contact, detach, a new silhouette). Do not pad. Never output 2D grid cells like x12y20.

First rewrite the user prompt into "action": 4–8 practical sentences a 3D drawer can follow. Cover who/what is on stage, where in the unit cube, beat order, what travels, what pose changes, and what stays unchanging (head size/shape, build, hoop/net). Then pick keys that realize THAT action.

Around 12 frames is a default length, not a quota. Real length is keys + all n_inbetween. Stay in 4–20.

World: +x right, +y deeper, +z up. Coordinates roughly [-1,1]. People about 1/4–1/3 of the scene height. Props follow the person (ball smaller than a head; hoop rim above head height on a pole; net is one vertical line to chest/head).

Identity vs motion: head size/shape, body build, limb length, who is who are UNCHANGING. Moving parts SHOULD change pose: a weight shift, a swinging arm, a traveling ball. One clear action, not a busy mix.

Mark each part "motion": "moving" or "anchored". Ground, hoop pole, hoop rim, net are anchored.
Every parts[].id is a cross-frame contract. Each key scene must contain that exact id once.
If a part needs helper strokes, prefix them with "<part_id>_". Do not rename people or parts between keys.
Keep all geometry inside the shared world box [-1,1] on x/y/z; final animation uses one fixed camera and no per-frame recentering.
"""


def key_count_bounds(pin_frames: int | None = None) -> tuple[int, int]:
    lo, hi = MIN_KEYS, MAX_KEYS
    budget = int(pin_frames) if pin_frames else MAX_FRAMES
    hi = min(hi, (budget + 1) // 2)
    if pin_frames:
        lo = max(lo, (int(pin_frames) + 20) // 11)
    if lo > hi:
        lo = hi
    return lo, hi


def key_plan_user(
    task: dict,
    n_keys: int | None = None,
    suggested_frames: int | None = None,
    pin_frames: int | None = None,
) -> str:
    n_min, n_max = task.get("part_range", (MIN_PARTS, MAX_PARTS))
    suggested_frames = int(suggested_frames or task.get("target_frames") or 12)
    pin_frames = int(pin_frames) if pin_frames else None
    lo, hi = key_count_bounds(pin_frames)
    if n_keys is not None:
        n_keys = int(n_keys)
        pick = f"Pick exactly {n_keys} keys."
        key_rule = f"- keys length must be {n_keys}. gaps length must be {n_keys - 1}.\n"
    else:
        pick = f"YOU choose how many keys: {lo}–{hi}. Do not pad."
        key_rule = f"- keys length is YOUR choice, {lo}–{hi}. gaps length must be keys-1.\n"
    if pin_frames:
        frame_rule = f"- keys + all n_inbetween MUST total {pin_frames}.\n"
    else:
        frame_rule = (
            f"- Around {suggested_frames} frames is the default, not a quota. "
            f"Stay in {MIN_FRAMES}–{MAX_FRAMES}.\n"
        )
    return f"""User request: {task['prompt']}

{pick}

Return JSON:
{{
  "concept": "{task['concept']}",
  "viewpoint": "3D wireframe, four views (front/side/top/perspective)",
  "action": "4-8 sentence rewrite: who, where in the unit cube, beat order, what travels, what stays unchanging",
  "layout_notes": "staging in fractions of the scene; +x right +y depth +z up",
  "parts": [
    {{"id": "shooter_head", "name": "shooter_head", "how": "circle in 3D", "motion": "moving", "notes": "same size every key"}}
  ],
  "keys": [
    {{"name": "start", "beat": "short beat", "notes": "pose in words"}}
  ],
  "gaps": [
    {{"after": "start", "n_inbetween": 3, "ease": "linear|smooth|ease_out", "why": "why this many"}}
  ]
}}

Hard rules:
- "action" is required, 4–8 sentences, no 2D cells. Keys must follow it.
- parts {n_min}–{n_max}, same ids on every key. Two people: unique prefixes.
- Each part motion is moving or anchored.
{key_rule}- Each n_inbetween is an integer 1–10.
{frame_rule}- Include a hit/release/detach key if the action has one.
"""


TASKS = {
    "basketball": {
        "task_id": "anim3d_basketball",
        "concept": "two stick figures playing basketball",
        "prompt": "Two stick figures playing basketball.",
        "part_range": (8, 16),
        "target_frames": 12,
        "gif_ms": 80,
        "n_subjects": 2,
    },
    "walk": {
        "task_id": "anim3d_walk",
        "concept": "a stick figure walking",
        "prompt": "A stick figure walking.",
        "part_range": (6, 12),
        "target_frames": 12,
        "gif_ms": 80,
        "n_subjects": 1,
    },
}


def key_draw_prompt(plan: dict, key: dict, key_i: int, n_keys: int) -> str:
    parts = plan.get("parts") or []
    lines = [
        f"3D KEY {key_i}/{n_keys} named '{key.get('name')}' (beat: {key.get('beat', '')}).",
        f"Shot: {plan.get('action') or ''}",
        f"Staging: {plan.get('layout_notes') or ''}",
        "Draw this ONE pose as a Path3D spatial line sketch. Same named parts on every key.",
        "Include every listed part using its EXACT id once. Helper strokes must use '<part_id>_...' ids.",
        "Head size/shape and build stay unchanging. Moving parts must pose this beat.",
        "People about 1/4–1/3 of scene height. Four views must show the same 3D structure.",
        "Keep the whole scene inside x/y/z [-1,1]. The animation camera is fixed and will not recenter this key.",
        "",
        "Parts:",
    ]
    for p in parts:
        lines.append(
            f"- {p.get('id')} {p.get('name')} ({p.get('how')}, {p.get('motion')}). {p.get('notes') or ''}"
        )
    lines += ["", "This key pose:"]
    for k, v in key.items():
        if k in {"name", "i"}:
            continue
        lines.append(f"{k}: {v}")
    return "\n".join(lines)


def _scene_brief(scene: dict) -> str:
    strokes = []
    for item in scene.get("strokes") or []:
        strokes.append(
            {
                "id": item.get("id"),
                "path": item.get("path"),
                "description": item.get("description"),
                "group": item.get("group"),
            }
        )
    return json.dumps({"strokes": strokes}, ensure_ascii=False)


def inbetween_prompt(plan: dict, slot: dict, from_scene: dict, to_scene: dict) -> str:
    return f"""Redraw the SAME 3D wireframe as one complete Path3D scene for an inbetween pose.

Shot: {plan.get('action') or ''}
This frame is between keys '{slot.get('from')}' and '{slot.get('to')}' at t={float(slot.get('t', 0.5)):.3f} ease={slot.get('ease')}.
Keep identical stroke ids and identity (head size, build, hoop/ground). Only pose and traveling props change.
Include every plan part id exactly once; helper strokes may only use '<part_id>_...' ids.
Keep the whole scene inside the same x/y/z [-1,1] world box. Do not recenter or rescale the composition.
Anchored parts will be replaced by the first key after generation, so preserve their ids.
Do not invent extra people. Return one full scene JSON (the whole object), not a patch.

FROM key scene:
{_scene_brief(from_scene)}

TO key scene:
{_scene_brief(to_scene)}
"""
