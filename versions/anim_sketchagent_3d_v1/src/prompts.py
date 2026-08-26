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

Identity vs motion: head size/shape, body build, limb length, who is who are UNCHANGING. Moving parts SHOULD change pose: a weight shift, a swinging arm, a traveling ball. If a person walks, keys must show a real stride — one leg forward and the other back, then they swap; never ice-skate with both feet planted while the body slides. One clear action, not a busy mix.

Mark each part "motion": "moving" or "anchored". Ground, pillars, walls, doorframes, elevator shafts, platforms, and crane bases are anchored. Sliding doors, people, balls, hooks, and crates are moving.
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
    staging = str(task.get("staging") or "").strip()
    staging_block = f"\nStaging that must be visible in four views:\n{staging}\n" if staging else ""
    return f"""User request: {task['prompt']}
{staging_block}
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
    "pillar_peek": {
        "task_id": "anim3d_pillar_peek",
        "concept": "a stick figure peeking around a square pillar",
        "prompt": "A stick figure peeks from behind a square pillar, then steps fully out to the other side.",
        "staging": (
            "One square pillar at the origin, tall and anchored. One stick person only. "
            "Key A: person on the LEFT of the pillar, fully visible in front view. "
            "Key B: person has walked AROUND the pillar in +y (deeper); front view the body is hidden "
            "behind the pillar, top view shows them on the far side of the square. "
            "Key C: person emerges on the RIGHT of the pillar, fully visible again. "
            "Do not slide left-right in a flat plane. The path is an arc around the pillar. "
            "Front/side/top must disagree in a 3D way: front occludes, top shows the go-around."
        ),
        "part_range": (8, 14),
        "target_frames": 12,
        "gif_ms": 80,
        "n_subjects": 1,
    },
    "ball_door": {
        "task_id": "anim3d_ball_door",
        "concept": "a ball rolling through a doorway into the next room",
        "prompt": "A ball rolls across the floor and disappears through an open doorway, then reappears in the room behind.",
        "staging": (
            "Two rooms stacked in depth (+y), split by an anchored wall with a rectangular open doorway. "
            "No people. One ball on the floor. "
            "Key A: ball in the FRONT room, fully visible through the doorway from the front camera. "
            "Key B: ball IN the doorway threshold (half in each room); front view the ball sits in the opening. "
            "Key C: ball in the BACK room; from the front camera it is mostly gone or tiny in the doorway, "
            "but top view shows it clearly behind the wall. "
            "Wall and doorframe stay put. The ball must travel in +y, not just +x across the same room."
        ),
        "part_range": (7, 14),
        "target_frames": 12,
        "gif_ms": 80,
        "n_subjects": 0,
    },
    "elevator": {
        "task_id": "anim3d_elevator",
        "concept": "a stick figure walking into an elevator as the doors close",
        "prompt": "Elevator doors open; a stick figure walks in with swinging legs; doors close.",
        "staging": (
            "An elevator shaft/cabin as an anchored box with a floor, at the back of a short lobby. "
            "Two sliding door leaves are moving parts (not anchored). One stick person. "
            "Key A: doors CLOSED; person stands in the lobby, both feet planted. "
            "Key B: doors OPEN; person MID-STRIDE crossing the threshold (one leg forward into the cabin, "
            "the other still in the lobby, opposite arm forward). "
            "Key C: person INSIDE the cabin (deeper +y) on the elevator floor; doors closing or closed; "
            "the walk has finished or is on the opposite stride from Key B. "
            "Side view must show the person crossing the threshold. Walking is stepping, not sliding: "
            "legs and arms swing in opposition. Do not keep the person frozen in the lobby while only doors move."
        ),
        "part_range": (8, 16),
        "target_frames": 12,
        "gif_ms": 80,
        "n_subjects": 1,
    },
    "badminton": {
        "task_id": "anim3d_badminton",
        "concept": "two stick figures rallying badminton over a net",
        "prompt": "Two stick figures play badminton: one hits a shuttle over the net, the other returns it.",
        "staging": (
            "A net (anchored) splits the court in x: left player and right player, both stick figures with simple racket lines. "
            "One shuttlecock, smaller than a head. Ground/court lines anchored. "
            "Key A: left player at contact — racket arm fully forward, opposite leg stepping into the shot, shuttle just leaving the racket. "
            "Key B: shuttle high over the net (detach); both players in recovery/ready strides, not T-poses. "
            "Key C: right player at contact — racket arm forward, opposite leg planted, shuttle just leaving that racket toward the left. "
            "Front view: shuttle crosses the net. Top view: shuttle travels left to right then right to left. "
            "Hits are swings, not sliding statues. Unique id prefixes for the two people (left_*, right_*)."
        ),
        "part_range": (10, 16),
        "target_frames": 12,
        "gif_ms": 80,
        "n_subjects": 2,
    },
    "crane_gap": {
        "task_id": "anim3d_crane_gap",
        "concept": "a crane swinging a crate over a gap onto the far platform",
        "prompt": "A crane boom swings a crate over a gap and sets it on the far platform.",
        "staging": (
            "Two blocky platforms with a visible GAP between them (near platform toward camera, far platform deeper +y or to +x). "
            "A simple crane: vertical mast + one boom + hook. Large separated masses, no tiny hinges. "
            "Crate starts sitting on the NEAR platform. "
            "Key A: crate on near platform, hook attached or just lifting. "
            "Key B: crate hanging over the GAP, boom swung; top view the crate is between platforms, not over land. "
            "Key C: crate set down on the FAR platform, hook still above it. "
            "Platforms and mast stay anchored. Boom/hook/crate move. No people."
        ),
        "part_range": (8, 16),
        "target_frames": 12,
        "gif_ms": 80,
        "n_subjects": 0,
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
        "Do not rename parts between keys or between edit rounds (no walker_head_new / _emerge / _2).",
        "Head size/shape and build stay unchanging. Moving parts must pose this beat.",
        "If this beat is walking or stepping, show a stride: one leg forward, the other back; arms counter-swing.",
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
    parts = plan.get("parts") or []
    part_lines = "\n".join(
        f"- {p.get('id')} {p.get('name')} ({p.get('how')}, {p.get('motion')}). {p.get('notes') or ''}"
        for p in parts
    )
    t = float(slot.get("t", 0.5))
    return f"""3D INBETWEEN between keys '{slot.get('from')}' and '{slot.get('to')}' at t={t:.3f} ease={slot.get('ease')}.
This is the SAME task as drawing a key: incremental Path3D spatial line sketch, four views.

Shot: {plan.get('action') or ''}
Staging: {plan.get('layout_notes') or ''}

Draw ONE pose interpolated along the action (not a copy of FROM or TO).
t=0 would match FROM, t=1 would match TO; you are at t={t:.3f}.

Parts (exact ids required):
{part_lines}

Identity (hard):
- Include every plan part id exactly once. Helpers only: '<part_id>_...'.
- Do not rename (no _new, _emerge, _2, _b). Changing pose keeps the same ids.
- Head size/shape and build stay unchanging. Anchored scenery stays put.
- People about 1/4–1/3 of scene height. Keep the scene inside x/y/z [-1,1].
- Do not invent extra people.
- Walk gait: if the person is traveling, pose a step (one foot ahead, the other behind, opposite arm forward). Alternate which foot leads as t increases. Do not slide a T-pose along the floor.

FROM key scene:
{_scene_brief(from_scene)}

TO key scene:
{_scene_brief(to_scene)}
"""


def inbetween_oneshot_prompt(plan: dict, slot: dict, from_scene: dict, to_scene: dict) -> str:
    return (
        inbetween_prompt(plan, slot, from_scene, to_scene)
        .replace(
            "This is the SAME task as drawing a key: incremental Path3D spatial line sketch, four views.",
            "Draw this ONE pose as a complete Path3D scene in a single reply. No patches, no extra people.",
        )
        + "\nReturn JSON only: {\"prompt\":\"...\",\"strokes\":[{\"id\":\"...\",\"path\":\"M ...\",\"description\":\"...\",\"group\":\"...\"}]}.\n"
        "Reuse exact ids from FROM. Path commands only (M/L/C3/Q3/Z). Coordinates in [-1,1].\n"
    )
