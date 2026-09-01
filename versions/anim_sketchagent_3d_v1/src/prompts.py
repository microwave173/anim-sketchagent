"""Pose-to-pose planner prompts for 3D Path3D clips."""
from __future__ import annotations

import json

MIN_FRAMES = 4
MAX_FRAMES = 20
MIN_KEYS = 2
MAX_KEYS = 6
MIN_PARTS = 6
MAX_PARTS = 20
DEFAULT_PEOPLE_SCALE = "People about 1/4–1/3 of the scene height."
INBETWEEN_REASONING = (
    "You are drawing ONE inbetween pose, not blending two drawings. "
    "FROM is history (what already happened). TO is the next key: a destination story beat, not a mix target. "
    "Decide what must causally happen between FROM and this frame on the way to TO: "
    "approach, contact, compression, bounce, detach, follow-through, or an airborne arc. Draw that moment. "
    "Ease only changes how soon a beat arrives, not whether it happens. "
    "Do not independently slide each stroke toward TO. When a traveling object and a striker/support must interact, "
    "keep them on a collision course until they meet; never send the traveler on a chord that misses. "
    "If TO already shows the object AFTER the hit (leaving the tool), this frame is still BEFORE that key: "
    "the object must still be approaching or touching, never already past on the far side. "
    "Do not tunnel through a striker, the ground, or an obstacle. "
    "Airborne hops and hits travel on an arc, not a straight chord. "
    "Do not copy FROM or TO."
)


def people_scale_line(plan_or_task: dict | None = None) -> str:
    text = str((plan_or_task or {}).get("people_scale") or "").strip()
    return text or DEFAULT_PEOPLE_SCALE


def previous_key_context(prev_scene: dict, *, prev_name: str, key_i: int, limit: int = 24000) -> str:
    brief = json.dumps(
        {
            "strokes": [
                {
                    "id": item.get("id"),
                    "path": item.get("path"),
                    "description": item.get("description"),
                    "group": item.get("group"),
                }
                for item in prev_scene.get("strokes") or []
            ]
        },
        ensure_ascii=False,
    )[: int(limit)]
    return (
        f"\n\nPREVIOUS KEY '{prev_name}' (already drawn, key {key_i - 1}). "
        "Keep the same stroke ids, head size, build, and world placement. "
        "Change pose for THIS beat; do not invent a new character.\n"
        f"{brief}"
    )

KEY_PLAN_SYSTEM = """You are a sketch planner for pose-to-pose 3D wireframe animation.
Return JSON only. No markdown.

A 3D drawer will draw ONLY the key poses as Path3D spatial line sketches (front/side/top/perspective).
Inbetweens are a later one-shot redraw of the SAME named parts — the key drawer will not see them.
You pick a few extremes, not a full frame list. YOU choose how many keys: at least 2, at most 6.
The first key is frame 1 of the clip. The last key is the last frame. The last key must show the finished action, not a mid-travel pose.
Two keys is enough for one continuous travel. Add a key only when interpolation cannot invent that beat (contact, detach, a new silhouette). Do not pad. Never output 2D grid cells like x12y20.

First rewrite the user prompt into "action": 4–8 practical sentences a 3D drawer can follow. This is a DIRECTOR rewrite: restage for readable, expressive motion while keeping the user's intent. Spread the cast when the story needs distance; give traveling things room to read; say how distinctive props should be recognized. Cover who/what is on stage, where in the unit cube, beat order, what travels, what pose changes, and what stays unchanging (head size/shape, build, scenery). Then pick keys that realize THAT action.

Around 12 frames is a default length, not a quota. Real length is keys + all n_inbetween. Stay in 4–20.

World: +x right, +y deeper, +z up. Coordinates roughly [-1,1]. People about 1/4–1/3 of the scene height. Small traveling props are smaller than a head.

Identity vs motion: head size/shape, body build, limb length, who is who are UNCHANGING. Moving parts SHOULD change pose: a weight shift, a swinging arm, a traveling object. If a person walks, keys must show a real stride — one leg forward and the other back, then they swap; never ice-skate with both feet planted while the body slides. One clear action, not a busy mix.

Timing (hard): gaps[].n_inbetween is how much TIME sits between those two keys, not padding. A fast hit uses few inbetweens (1–3). A long travel or settle uses more. Do not give every gap the same count unless the beats last the same. gaps[].why must say quick/medium/long and why this many frames.

Mark each part "motion": "moving" or "anchored". Ground and architectural scenery are anchored. People, traveling objects, and articulated props are moving.
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
    scale_block = f"\nFigure scale (hard):\n{people_scale_line(task)}\n"
    return f"""User request: {task['prompt']}
{staging_block}{scale_block}
{pick}

Return JSON:
{{
  "concept": "{task['concept']}",
  "viewpoint": "3D wireframe, four views (front/side/top/perspective)",
  "action": "4-8 sentence rewrite: who, where in the unit cube, beat order, what travels, what stays unchanging",
  "layout_notes": "staging in fractions of the scene; +x right +y depth +z up",
  "parts": [
    {{"id": "actor_head", "name": "actor_head", "how": "circle in 3D", "motion": "moving", "notes": "same size every key"}}
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
{frame_rule}- First key = frame 1. Last key = last frame; that pose is the completed action.
- Include a hit/release/detach key if the action has one.
"""


# Paper eval set (5). Support/gravity + discrete bounce-in-depth + doorway + elevator + free bloom.
SUITE = ("tabledrop", "stairs", "ball_door", "elevator", "fireworks")

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
    "soccer": {
        "task_id": "anim3d_soccer",
        "concept": "a stick figure shooting a football into a far goal",
        "prompt": "A stick figure kicks a football into a goal at the far end of the pitch.",
        "staging": (
            "A rectangular pitch on the ground plane. The GOAL is at the FAR end in +y (deeper), anchored: "
            "two posts, a crossbar, optional simple net. One stick person and one ball near the camera (smaller y). "
            "Do not put the goal on the same left-right plane as a 2D side-view penalty. "
            "Key A: person coiled over the ball, kicking leg back, facing the far goal. "
            "Key B: CONTACT — kicking foot meets the ball; torso and head lean toward +y. "
            "Key C: last frame — DETACH, ball INSIDE the far goal; person in follow-through. "
            "Front view: the ball travels away into the goal mouth (it may shrink or sit in the opening). "
            "Top view: a clear +y path from the shooter into the net. Side view: the kick and the ball rising or rolling toward the far posts. "
            "Ground and goal stay anchored. Person and ball move."
        ),
        "part_range": (8, 16),
        "target_frames": 12,
        "gif_ms": 80,
        "n_subjects": 1,
    },
    "tabledrop": {
        "task_id": "anim3d_tabledrop",
        "concept": "a ball rolling off the far edge of a table and falling to the floor",
        "prompt": (
            "A ball rolls across a table toward the far edge, then falls to the floor. No people."
        ),
        "people_scale": (
            "No people. Ball much smaller than the tabletop. Table is a thick anchored slab; floor is z=0."
        ),
        "staging": (
            "An anchored TABLE occupies the near–mid depth: a rectangular top above the floor (z>0), with visible thickness. "
            "The FAR edge of the table is deeper in +y. Floor is a ground plane at z=0, also anchored. One ball. "
            "Key A: ball ON the tabletop, near the camera (smaller y), clearly above the floor. "
            "Key B: ball at the FAR lip of the table, still supported or just leaving; top view it sits on the table rectangle. "
            "Key C: last frame — ball has LEFT the table and sits on the FLOOR beyond the far edge "
            "(further +y than the table, z at floor height, not hovering at table height). "
            "Front view: ball shrinks then drops. Top view: ball exits the table rectangle. Side view: a step down in z. "
            "Do not let the ball tunnel through the slab. Table and floor stay put."
        ),
        "part_range": (6, 14),
        "target_frames": 12,
        "gif_ms": 80,
        "n_subjects": 0,
    },
    "stairs": {
        "task_id": "anim3d_stairs",
        "concept": "a ball bouncing down a staircase receding in depth",
        "prompt": (
            "A ball bounces down a short staircase that recedes away from the camera. "
            "Each bounce is lower. No people."
        ),
        "people_scale": (
            "No people. Ball smaller than one stair tread. Stairs are large anchored blocks stepping down in z while going +y."
        ),
        "staging": (
            "Three or four large STAIR blocks, anchored, receding in +y: each deeper step is LOWER in z. "
            "A floor landing at the bottom. One ball. "
            "Do not draw a smooth ramp — treads must be readable in side view as a staircase. "
            "Key A: ball on the HIGHEST tread (nearest / smallest y), round, at rest or just starting to fall off that step. "
            "Key B: mid-stair — CONTACT or squash on a MIDDLE tread, or airborne between two steps; depth has increased. "
            "Key C: last frame — ball on the BOTTOM landing (deepest +y, lowest z), after at least two step-downs; "
            "this rest/low bounce is lower than Key A. "
            "Front view: the ball goes down. Top view: it travels +y across successive treads. "
            "Stairs stay put. Only the ball moves."
        ),
        "part_range": (7, 16),
        "target_frames": 12,
        "gif_ms": 80,
        "n_subjects": 0,
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
        "prompt": (
            "Left player hits a shuttle over the net; the opponent takes one running step to meet it, then hits it back."
        ),
        "people_scale": (
            "Each player's standing height (feet to top of head) is about 3/5 of the court WIDTH "
            "(the left–right span of the court rectangle on the ground, not the whole scene box). "
            "People must look small on the court: clearly shorter than the court is wide, with empty court around them. "
            "Do not draw anyone as tall as a court half."
        ),
        "staging": (
            "A net (anchored) splits a wide court in x: left player and right player, both small stick figures with simple racket lines. "
            "One shuttlecock, smaller than a head. Ground/court lines anchored. "
            "Beat order is a one-two rally plus a chase step, not two statues swapping arms. "
            "Key A: left player at contact — racket arm fully forward, opposite leg stepping into the shot, shuttle just leaving the racket. "
            "Right player is still on their own side, not yet at the contact spot. "
            "Key B: shuttle high over the net; the RIGHT player has taken exactly ONE running step toward the incoming shuttle "
            "(feet swapped, body shifted closer to where the shuttle will land). Left player is in recovery, not frozen. "
            "Key C: right player, after that step, at contact — racket arm forward, opposite leg planted, shuttle just leaving that racket back toward the left. "
            "Front view: shuttle crosses the net twice (over, then back). Top view: shuttle left-to-right, then right-to-left; "
            "the right player's feet move between A and B. Hits are swings. Unique id prefixes (left_*, right_*)."
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
    "fireworks": {
        "task_id": "anim3d_fireworks",
        "concept": "a firework rocket launches then bursts in 3D",
        "prompt": (
            "A firework rocket launches from the ground and bursts in the sky. "
            "Choose any bloom shape you like — do not force a six-point star."
        ),
        "people_scale": (
            "No people. The rocket is a thin stick, much smaller than the scene height. "
            "The burst lives in the upper half of the cube and stays inside [-1,1]. "
            "Ground is a simple wide plane or line at z=0; the launcher is a tiny stub on the ground."
        ),
        "staging": (
            "One firework only. Ground and a tiny launcher are anchored at z=0 near the origin. "
            "A rocket/shell is moving. Burst pieces are ALSO named parts that exist on EVERY key "
            "(reuse the same ids). They must not appear as new ids at bloom. "
            "YOU choose the bloom shape: chrysanthemum, willow, ring, palm, random 3D spray, or anything else readable. "
            "Do not require a spherical six-axis star. "
            "Key A (launch): rocket sits on the launcher, almost on the ground; burst pieces are COLLAPSED "
            "into a tiny knot at the rocket tip. "
            "Key B (apex): rocket has traveled UP in +z to the upper half of the scene; burst still collapsed "
            "at the rocket; side view shows a tall vertical trail of travel, not a sideways slide. "
            "Key C (bloom): rocket is gone or a tiny leftover at the burst center; burst pieces have EXPANDED "
            "into your chosen 3D shape. Top view must not be a flat fan on one plane. "
            "Do not draw people, text, or extra fireworks."
        ),
        "part_range": (8, 16),
        "target_frames": 12,
        "gif_ms": 90,
        "n_subjects": 0,
    },
    "catwalk": {
        "task_id": "anim3d_catwalk",
        "concept": "a small cat walking to the right",
        "prompt": "A small cat walks to the right across the ground.",
        "people_scale": (
            "Cat about 1/5–1/4 of scene height. Ellipse-ish body, round head at the front, two pointed ears, "
            "four short legs, long tail curving up. Smaller than a standing stick person."
        ),
        "staging": (
            "Ground plane anchored. One cat, no person, no mouse. Side-view facing +x. "
            "Body and head translate together in +x and keep the same size. Legs are short ticks that change angle. "
            "Key A: LEFT third, contact stride (one front leg forward, opposite hind forward). "
            "Key B: CENTER, passing stride, legs gathered under the body. "
            "Key C: last frame — RIGHT-CENTER, opposite contact, leave empty space at the +x edge. "
            "Head stays above the body. Front/side/top must agree: the cat walks along +x on the ground, not floating. "
            "Last key is the last frame and must show the completed walk (cat at right-center, opposite contact)."
        ),
        "part_range": (8, 16),
        "target_frames": 12,
        "gif_ms": 80,
        "n_subjects": 1,
    },
}


def key_draw_prompt(
    plan: dict,
    key: dict,
    key_i: int,
    n_keys: int,
    *,
    prev_scene: dict | None = None,
    prev_name: str = "",
) -> str:
    parts = plan.get("parts") or []
    lines = [
        f"3D KEY {key_i}/{n_keys} named '{key.get('name')}' (beat: {key.get('beat', '')}).",
        f"Shot: {plan.get('action') or ''}",
        f"Staging: {plan.get('layout_notes') or ''}",
        "Draw this ONE pose as a Path3D spatial line sketch. Same named parts on every key.",
        "Include every listed part using its EXACT id once. Helper strokes must use '<part_id>_...' ids.",
        "Do not rename parts between keys or between edit rounds (no walker_head_new / _emerge / _2).",
        "Head size/shape and build stay unchanging. Heads are circles of the same size every key. "
        "Animal ears sit on the crown (+z / on top of the head), not flipped onto the chin or snout.",
        "If this beat is walking or stepping, show a stride: one leg forward, the other back; arms counter-swing.",
        people_scale_line(plan),
        "Four views must show the same 3D structure.",
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
        if k in {"name", "i", "parts", "strokes", "path"}:
            continue
        lines.append(f"{k}: {v}")
    if prev_scene:
        lines.append(
            previous_key_context(prev_scene, prev_name=prev_name or "previous", key_i=key_i)
        )
    return "\n".join(lines)


def _plan_key(plan: dict, name: str) -> dict:
    want = str(name or "").strip()
    for key in plan.get("keys") or []:
        if str(key.get("name") or "").strip() == want:
            return key
    return {}


def _gap_why(plan: dict, after: str) -> str:
    want = str(after or "").strip()
    for gap in plan.get("gaps") or []:
        if str(gap.get("after") or "").strip() == want:
            return str(gap.get("why") or "").strip()
    return ""


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
    cur = int(slot.get("current_frame") or slot.get("i") or 0)
    n_frames = int(slot.get("n_frames") or 0)
    from_i = int(slot.get("from_frame") or max(cur - 1, 1))
    to_i = int(slot.get("to_frame") or 0)
    span = f"clip has {n_frames} frames" if n_frames else "clip"
    to_key = _plan_key(plan, slot.get("to"))
    to_beat = str(to_key.get("beat") or slot.get("to") or "").strip()
    to_notes = str(to_key.get("notes") or "").strip()
    why = _gap_why(plan, slot.get("from"))
    story_lines = [
        f"Next key '{slot.get('to')}' (frame {to_i}) beat: {to_beat}." if to_beat else "",
        f"Next key pose notes: {to_notes}" if to_notes else "",
        f"Why this gap exists: {why}" if why else "",
    ]
    story = "\n".join(line for line in story_lines if line)
    return f"""3D INBETWEEN: draw frame {cur} ({span}).
FROM is the already-drawn previous frame {from_i}. TO is the next key, which is frame {to_i}.
Ease={slot.get('ease')}. Progress in this gap t={t:.3f} (0 is just after FROM's key, 1 would be TO).
This frame is still BEFORE the TO key.
This is the SAME task as drawing a key: incremental Path3D spatial line sketch, four views.

Shot: {plan.get('action') or ''}
Staging: {plan.get('layout_notes') or ''}
{story}

{INBETWEEN_REASONING}

Parts (exact ids required):
{part_lines}

Identity (hard):
- Include every plan part id exactly once. Helpers only: '<part_id>_...'.
- Do not rename (no _new, _emerge, _2, _b). Changing pose keeps the same ids.
- Head size/shape and build stay unchanging. Anchored scenery stays put.
- {people_scale_line(plan)} Keep the scene inside x/y/z [-1,1].
- Do not invent extra people.
- Walk gait: if the person is traveling, pose a step (one foot ahead, the other behind, opposite arm forward). Alternate which foot leads as the frame index increases toward the next key. Do not slide a T-pose along the floor.

FROM frame {from_i}:
{_scene_brief(from_scene)}

TO key (frame {to_i}):
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
