"""Pose-to-pose planner prompts for 3D Path3D clips."""
from __future__ import annotations

import json

MIN_FRAMES = 4
MAX_FRAMES = 20
MIN_KEYS = 2
MAX_KEYS = 6
MIN_PARTS = 6
MAX_PARTS = 24
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
    "Causal order is a hard gate: do not show an effect, transformed state, or newly appearing object before its enabling action "
    "has visibly completed. A flower starts blooming only after watering ends; a sprinkler starts only after the alarm is pulled; "
    "a fire disappears only after water reaches it. Before the causal boundary preserve the earlier state; after it make the new "
    "state clearly legible instead of blending both states ambiguously. "
    "Walk/run fill (hard): if FROM and TO are opposite contact strides, this frame is a passing pose "
    "(legs gathered or crossing), not both feet sliding. Advance the trailing leg of FROM. "
    "Do not copy FROM or TO."
)

ANIMAL_DRAWING = (
    "People vs animals (hard): "
    "People stay stick figures. Animals are NOT stick figures. "
    "Draw animals as cute, lively children's sketches, not realistic anatomy, "
    "not a round lollipop head on a stick spine. "
    "World axes (hard): +x right, +y deeper (away from camera), +z up. Do not treat +y as up. "
    "Animal construction: "
    "Body is one closed oval, bean, or a slightly reshaped closed curve (Z allowed in Path3D). "
    "Head is likewise a closed oval, bean, or simple closed curve. "
    "Short-neck animals (cat, dog, pig, rabbit, bear, etc.): do NOT draw a neck; "
    "join the head directly to the body as two touching or overlapping closed shapes. "
    "Long-neck animals (horse, giraffe, swan, goose, etc.): body + neck + head is ONE continuous closed outline, "
    "like a single pen stroke. No seam line where neck meets body, and no seam where neck meets head. "
    "Default long-neck pose: the neck stands UP along +z, erect toward the sky, not laid flat along the back. "
    "Muzzle (horse, dog, pig, etc.): an extra oval on the front of the head is allowed; "
    "if joining muzzle and head in ONE closed outline looks cleaner, fuse them instead of a separate muzzle oval. "
    "If facing +x, the muzzle is at +x and the tail at −x. If facing +y (deeper), the muzzle aims +y. "
    "Legs: one open stroke each (a single line). Four legs if the animal has four. "
    "Far legs sit slightly behind along +y (deeper), not shifted sideways in −x. "
    "Legs default SHORT — cute stubby ticks, not long stick-person limbs. "
    "Legs run from the body toward the ground (−z). "
    "Tail length (hard): shortening the legs does NOT shorten the tail. "
    "Default tails are LONG: from the rump they should read about as long as the body mass, "
    "streaming well past the hind legs (horse: a flowing plume; cat/dog: a long curve). "
    "Do not draw a tiny stub tail. Exceptions: rabbit cottontail is a small puff; pig tail may be a small curl. "
    "No tube legs, no double outline, no hoof boxes unless the plan names hooves as a tiny extra mark. "
    "Face marks (hard): do NOT omit eyes, nose, or ears on animals. "
    "Tell-tale parts must be OBVIOUSLY readable at a glance — ears, eyes, nose/muzzle, mane, tail. "
    "Do not hide them by tracing the head or body outline. "
    "An ear must stick OUT from the crown as its own silhouette, higher z than the head-center: "
    "a floppy dog ear hangs off the back of the head; cat/horse/rabbit ears poke up from the crown along +z. "
    "Do not draw an ear as a curve that follows the skull. "
    "The eye tick sits INSIDE the head, not on the outline. "
    "Eyes default to a short vertical tick (a tiny L or Q dash). Only PEOPLE omit eyes (and hair/face). "
    "Distinctive features must be drawn — the marks that make the species readable "
    "(cat: pointed ears on the CROWN; dog: floppy ear hanging OFF the crown; horse: mane, upright neck, and long muzzle; pig: snout disk and curly tail; "
    "bird: beak and wing; rabbit: long ears; cow: horns; fish: tail fin). "
    "Four views (hard): front AND side must show ears on TOP of the skull (higher z), never on the chin. "
    "Top view must show left and right ears and travel along +y, not a sideways slide. "
    "Draw order (hard): (1) body, and neck if long-neck, and head as the closed mass(es) — "
    "fuse muzzle into that outline when it reads better; "
    "(2) then the legs, each a SHORT single line from the body toward the ground (−z); "
    "(3) then the other tell-tale parts (ears, nose or muzzle oval if not fused, mane, tail from the rump, "
    "eye as a short vertical tick, beak, etc.). "
    "Do not leave construction seams, inner ovals, or a stick skeleton inside the animal."
)
ANIMAL_PLAN_PARTS = (
    "Plan the parts list to match that recipe. Animals MUST include drawable parts for eyes "
    "(short vertical ticks), ears, and nose — unless muzzle is fused into the head/body outline, "
    "in which case still include eyes and ears. Those face parts must stay obviously readable, not fused into the head outline. "
    "In parts[].notes, name the parent and the relative seat: ears ON TOP of the head (crown, higher z than head-center); "
    "eye tick INSIDE the head; tail from the rump; legs from the body toward the ground (−z). "
    "People still omit eyes, hair, and face. "
    "Default short legs. Tails stay LONG (do not stub them when legs are short). Default long-neck: neck stands upright."
)
INK_STYLE = (
    "Ink (hard): every stroke uses the same color and the same thickness. "
    "Never change line thickness or color between strokes, parts, or frames."
)
VISUAL_COMMUNICATION = (
    "Visual communication outranks literal realism (hard): draw for an audience who must understand the event immediately, "
    "not for geometric realism alone. Preserve real 3D structure and physical logic, but use clear staging, separated silhouettes, "
    "purposeful exaggeration, iconic shapes, motion signs, and uncluttered negative space when they make the subject, action, cause, "
    "or state change easier to recognize in the perspective view and at least one orthographic view. Make decisive information "
    "visibly large and spatially unambiguous: the acting hand meets the control, an emitted stream connects source to target, and a "
    "removed or transformed object has a clearly different state. Do not hide a critical event in tiny realistic detail, occlusion, "
    "tangency, or decorative clutter. A viewer should understand each key beat without reading its caption."
)


def people_scale_line(plan_or_task: dict | None = None) -> str:
    value = plan_or_task or {}
    text = str(value.get("people_scale") or value.get("notes") or "").strip()
    return DEFAULT_PEOPLE_SCALE + (" Plan notes: " + text if text else "")


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
        "This is the immediate motion predecessor. Keep the same stroke ids, head size, build, spatial construction, "
        "attachment topology, facing, and prop dimensions. Infer and continue its displacement and articulation direction: do not teleport, "
        "reverse direction, swap limbs, change depth lane, or reset to neutral unless the plan explicitly says so. "
        "Change pose for THIS beat; do not invent a new character.\n"
        f"{brief}"
    )


def identity_anchor_context(anchor_scene: dict, *, anchor_name: str = "first", limit: int = 24000) -> str:
    """First-key geometry is an immutable 3D model-sheet reference."""
    brief = json.dumps(
        {
            "strokes": [
                {
                    "id": item.get("id"),
                    "path": item.get("path"),
                    "description": item.get("description"),
                    "group": item.get("group"),
                }
                for item in anchor_scene.get("strokes") or []
            ]
        },
        ensure_ascii=False,
    )[: int(limit)]
    return (
        f"\n\nIDENTITY ANCHOR '{anchor_name}' (the accepted first key). "
        "Use it only as the immutable spatial model sheet: preserve head radius, torso and limb lengths, body build, "
        "animal silhouette, prop dimensions, box thickness, depth construction, and attachment pattern in every view. "
        "The immediate PREVIOUS KEY controls current position and motion; this anchor controls appearance. "
        "Do not copy the anchor pose or coordinates into the new beat.\n"
        f"{brief}"
    )


def planned_motion_neighborhood(plan: dict, key_i: int) -> str:
    """Use ordinary plan fields; continuity needs no additional planner schema."""
    keys = list(plan.get("keys") or [])
    neighborhood = {}
    for label, index in (("previous", key_i - 2), ("current", key_i - 1), ("next", key_i)):
        if 0 <= index < len(keys):
            key = keys[index]
            neighborhood[label] = {
                name: key.get(name) for name in ("name", "beat", "notes") if key.get(name) is not None
            }
        else:
            neighborhood[label] = None
    return json.dumps(neighborhood, ensure_ascii=False)

KEY_PLAN_SYSTEM = (
    """You are a sketch planner for pose-to-pose 3D wireframe animation.
Return JSON only. No markdown.

Spatial volume (hard): Solid spherical bodies must be genuine spatial wireframes, using at least three mutually perpendicular great-circle contours under their existing part id, not a flat circular billboard. Solid boxes/slabs must have depth and connected front/back edges. Front, side and top must all reveal volume. Do not force all curves into one depth plane. For an explosion, fragments travel in x, y and z; a destroyed spherical body must collapse into the explosion core rather than remain as an intact sphere. Any anchored emitter stays rigid and stationary. This describes shape and motion requirements, not supplied coordinates.

A 3D drawer will draw ONLY the key poses as Path3D spatial line sketches (front/side/top/perspective).
Inbetweens are a later one-shot redraw of the SAME named parts — the key drawer will not see them.
You pick sparse story extremes, not a full frame list. The user message gives the permitted or exact key count; follow it, with an absolute maximum of 12.
The first key is frame 1 of the clip. The last key is the last frame. The last key must show the finished action, not a mid-travel pose.
Two keys is enough for one continuous travel. Add a key only when interpolation cannot invent that beat (contact, detach, a new silhouette). Do not pad. Never output 2D grid cells like x12y20.

First rewrite the user prompt into "action": 4–8 practical sentences a 3D drawer can follow. This is a DIRECTOR rewrite: restage for readable, expressive motion while keeping the user's intent. Spread the cast when the story needs distance; give traveling things room to read; say how distinctive props should be recognized. Cover who/what is on stage, where in the unit cube, beat order, what travels, what pose changes, and what stays unchanging (head size/shape, build, scenery). Then pick keys that realize THAT action.

Causal chronology (hard): write the action and keys as an ordered chain of completed prerequisites and consequences. An effect, transformation, disappearance, or newly introduced object may begin only after its enabling beat is visibly complete. For example, watering must finish before blooming begins; an alarm must be pulled before a sprinkler starts; water must reach a fire before the fire disappears. Do not merge cause and consequence into one vague key. In every key beat/notes, state what has completed, what is happening now, and what has not started yet whenever the boundary could be ambiguous.

Visual communication (hard): plan for audience recognition, not literal realism alone. Choose staging, silhouette, scale, spacing, depth separation, iconic signs, and permissible exaggeration so the subject, action, causal link, and state change read immediately in the perspective view and remain identifiable in orthographic views. Reserve clear space around decisive interactions and require critical contacts or emissions to be visibly connected. Do not rely on tiny realistic detail or the text prompt to explain the drawing.

World: +x right, +y deeper, +z up. Coordinates roughly [-1,1]. People about 1/4–1/3 of the scene height. Small traveling props are smaller than a head.

Identity vs motion: head size/shape, body build, limb length, who is who are UNCHANGING. Moving parts SHOULD change pose: a weight shift, a swinging arm, a traveling object. If a person walks, keys must show a real stride — one leg forward and the other back, then they swap; never ice-skate with both feet planted while the body slides. One clear action, not a busy mix.

Each parts[].notes MUST name the parent and the relative seat — above/below, in front/behind, left/right, inside/outside — plus a short facing/pointing clause. Do not write path strings. Examples: "ON TOP of the head, higher z than head-center"; "meets the BOTTOM of the head"; "INSIDE the head, not on the outline"; "from the rump, streaming −x"; "from the belly DOWN toward the ground (−z)"; "looks +x".
Write one concise notes field: one short semicolon-separated sentence, at most 180 characters, covering only fixed scale/identity, essential stage placement or travel lane, and any crucial attachment the drawer could otherwise misunderstand. Do not retell the action.

Relative placement (hard): attached parts are not free-floating labels. The planner must say where each child sits on its parent using axes (+x right, +y deeper, +z up). People: neck under the head; both arms meet that neck; both legs meet the hip. Animals: ears ON TOP of the head (crown, higher z), never on the chin or tracing the skull; eye tick INSIDE the head; tail from the rump; legs from the body toward the ground. Front AND side views must still read ears on top of the skull; top view must show left/right ears, not a sideways slide.

Timing and action density (hard): the user message gives the exact frame count, milliseconds per frame, and total playback seconds. Design enough visible action for that real duration; do not stretch a short action by holding one pose. gaps[].n_inbetween is how much TIME sits between those two keys, not padding. A fast hit, release, catch, or snap uses few inbetweens (1–3). A brief gather, plant, or anticipation normally uses fewer frames than the travel or consequence it enables. A long travel, hang-time, or slow settle may use more only while something visibly changes in every frame. No stationary hold, carried-object pose, crouch, or finished pose may consume a large fraction of the clip unless the user explicitly asks for a pause. For a multi-stage action, reach the main event around the middle-to-late part of the clip and reserve meaningful time afterward for its visible consequence; do not postpone the defining event until the last few frames. If the requested runtime is longer than the described action naturally needs, enrich the director rewrite with plausible sub-beats (distinct strides, dribbles, follow-through, landing, rebound, or reaction) instead of slowing a single transition. Do not give every gap the same count unless the beats really last the same. gaps[].why must state the interval's approximate seconds, whether it is quick/medium/long, and what visible change fills that time.

Mark each part "motion": "moving" or "anchored". Ground and architectural scenery are anchored. People, traveling objects, and articulated props are moving.
Every parts[].id is a cross-frame contract. Each key scene must contain that exact id once.
If a part needs helper strokes, prefix them with "<part_id>_". Do not rename people or parts between keys.
Keep all geometry inside the shared world box [-1,1] on x/y/z; final animation uses one fixed camera and no per-frame recentering.

"""
    + ANIMAL_DRAWING
    + " "
    + ANIMAL_PLAN_PARTS
    + " "
    + INK_STYLE
    + """
"""
)


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
    frame_duration_ms: int = 80,
) -> str:
    n_min, n_max = task.get("part_range", (MIN_PARTS, MAX_PARTS))
    suggested_frames = int(suggested_frames or task.get("target_frames") or 12)
    pin_frames = int(pin_frames) if pin_frames else None
    lo, hi = key_count_bounds(pin_frames)
    playback_frames = int(pin_frames or suggested_frames)
    playback_ms = int(frame_duration_ms)
    playback_seconds = playback_frames * playback_ms / 1000.0
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
    legacy_notes = " ".join(
        text
        for text in (
            str(task.get("people_scale") or "").strip(),
            str(task.get("staging") or "").strip(),
        )
        if text
    )
    scale_block = f"\nExisting task constraints (compress into notes):\n{legacy_notes}\n" if legacy_notes else ""
    return f"""User request: {task['prompt']}
{staging_block}{scale_block}
{pick}

Playback budget (hard): {playback_frames} frames × {playback_ms} ms/frame = {playback_seconds:.2f} seconds. Expand or compress the visible story beats to fit this actual screen time. Do not fill surplus frames by holding a ball, prop, crouch, or finished pose.

Return JSON:
{{
  "concept": "{task['concept']}",
  "viewpoint": "3D wireframe, four views (front/side/top/perspective)",
  "action": "4-8 sentence rewrite: who, where in the unit cube, beat order, what travels, what stays unchanging",
  "notes": "one short sentence, <=180 chars: fixed identity; essential layout/travel; crucial attachment",
  "parts": [
    {{"id": "actor_head", "name": "actor_head", "how": "circle in 3D", "motion": "moving", "notes": "same size every key; neck meets BOTTOM of head"}}
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
- Each gap why must give approximate seconds, visible change, and justify the chosen frame count.
- Write each key's ordinary notes so the pose is causally compatible with the keys immediately before and after it: name x/y/z travel direction, depth lane, facing, leading or planted limb, held/touching/released state, and whole-body follow-through when relevant. A key is a sampled pose, not an automatic pause. Do not add extra schema fields for motion continuity.
- Adjacent key notes must not imply an unplanned stop, reversal, depth jump, limb swap, change of holding hand, or prop teleport. Gap drawers will infer boundary motion from these ordinary notes and neighboring key geometry.
- Keep preparation proportionate. Brief holds such as gather/plant/wind-up should be short; use the remaining runtime for distinct motion beats and consequences.
- parts[].notes must say where the part sits on its parent (ears ON TOP of the head, higher z; eye INSIDE the head; neck under the head). No coordinates.
- Animals: use the full animal construction (closed body/head; no extra neck on short-neck species; long-neck stands UP as one outline; SHORT single-line legs; LONG tail, not a stub; do not omit eyes/ears/nose; ears stick OUT from the crown and must be obviously readable; eyes are short vertical ticks inside the head; fuse muzzle into the head if cleaner).
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
    "parkour": {
        "task_id": "anim3d_parkour",
        "concept": "a stick figure vaulting a box while running into depth",
        "prompt": (
            "A stick figure parkours away from the camera: runs up, vaults a low box, and lands on the far side."
        ),
        "people_scale": (
            "Standing height about 1/4–1/3 of the scene height in every key. "
            "Same slim stick build, same head size, same limb length. Do not grow in the air or shrink on landing."
        ),
        "staging": (
            "Ground plane at z=0, anchored. One low BOX in the CENTER of the stage, anchored: "
            "a short rectangular crate (readable top + sides), hip-to-waist height — vaultable, not a wall. "
            "One stick person only, facing +y (deeper / away from camera). "
            "Leave run-up room on the NEAR side (smaller y) and landing room on the FAR side (larger +y). "
            "Key A: NEAR of the box (closer to camera), running +y, contact stride, torso leaning toward the box; not yet touching it. "
            "Key B: VAULT — hands (or one hand and a foot) plant on the BOX TOP; hips up and over the box; "
            "legs swinging toward +y; body not standing beside the box in the same depth. "
            "Key C: last frame — LANDED on the GROUND past the box (deeper +y), recovering a run stride, still facing +y; "
            "feet on the floor, not on the box. Same person size every key. Box and ground stay put. "
            "Front view: the person shrinks as they go deeper; mid-vault the box may hide the hips. "
            "Top view: a clear +y path from in front of the box, over it, to behind it. "
            "Side view: a vault arc in z over the box top. Do not ice-skate; vaulting is a plant-and-swing, landing is a stride."
        ),
        "part_range": (10, 18),
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
            "Cat about 1/5–1/4 of scene height. Closed ellipse/bean body, oval head joined at the front with no neck, "
            "two pointed ears, short vertical-tick eye, four SHORT single-line legs, long tail. Cute, not stick. "
            "Smaller than a standing stick person."
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
    "starwars": {
        "task_id": "anim3d_starwars",
        "concept": "a stick jedi deflecting a blaster bolt that then downs a far droid",
        "prompt": (
            "A stick-figure Jedi uses a lightsaber to deflect one blaster bolt back into a droid, defeating it."
        ),
        "people_scale": (
            "Jedi standing height about 1/4–1/3 of the scene height, slim stick, round head, no hair. "
            "Boxy droid about the same height. Saber longer than a forearm; bolt smaller than a head."
        ),
        "staging": (
            "Ground plane at z=0, anchored. Jedi (jedi_*) stands NEAR the camera (smaller y), facing +y. "
            "Boxy droid (droid_*) stands FARTHER in +y, facing the Jedi (−y), with a short blaster. "
            "ONE bolt part exists on EVERY key. One saber in the Jedi's hand. "
            "Do not stage this as a flat left-right 2D duel on one depth. "
            "Key A: droid firing in the distance; bolt already in the air, still FARTHER in +y than the saber, traveling toward the Jedi (−y). "
            "Key B: DEFLECT CONTACT — saber TOUCHES the bolt near the Jedi; bolt has not tunneled past the blade. "
            "Key C: last frame — the SAME bolt has reversed toward +y and HITS the droid; droid DEFEATED (tipped/slumped), not still aiming. "
            "Front view: bolt grows as it approaches then shrinks as it flies back. "
            "Top view: a clear +y then reverse −y ricochet on the same line. Side view: both figures on the ground, bolt at mid-height. "
            "Ground stays put. Unique prefixes jedi_* and droid_*."
        ),
        "part_range": (10, 16),
        "target_frames": 12,
        "gif_ms": 80,
        "n_subjects": 2,
    },
    "cmp_hoop": {
        "task_id": "anim3d_cmp_hoop",
        "concept": "a stick person shooting a basketball into a hoop in depth",
        "prompt": "This man is shooting at the basketball hoop in front of him.",
        "people_scale": "Person about 1/4–1/3 of scene height. Ball smaller than the head. Hoop larger than the ball.",
        "staging": (
            "Ground at z=0. One stick person near the camera (−y), facing +y. "
            "An anchored hoop farther in +y. One basketball exists on EVERY key. "
            "Key A: coiled shot, ball in the shooting hand. "
            "Key B: ball has left the hand and travels +y toward the hoop (front view shrinks; top view shows travel). "
            "Key C: last frame — ball at or through the rim; person follow-through. "
            "The ball must detach; it cannot stay in the palm."
        ),
        "part_range": (8, 16),
        "target_frames": 12,
        "gif_ms": 80,
        "n_subjects": 1,
    },
    "cmp_mo_basketball5": {
        "task_id": "anim3d_cmp_mo_basketball5",
        "concept": "a stick player dunking a basketball into a hoop in depth",
        "prompt": (
            "The player soars through the air with a basketball, arm extended for an electrifying slam dunk to a hoop."
        ),
        "people_scale": (
            "Person about 1/4–1/3 of scene height. Ball smaller than the head. "
            "An anchored hoop with backboard farther in +y, rim above the player's head."
        ),
        "staging": (
            "Ground at z=0. One stick player near the camera (−y), facing +y. "
            "An anchored hoop and backboard farther in +y. Persistent ids player, ball, hoop on every key. "
            "Key A: takeoff from the ground, ball in the raised driving hand, still far from the rim. "
            "Key B: AIRBORNE — player at rim height, arm fully extended, ball above the rim, body farther in +y. "
            "Key C: last frame — ball through the rim and below it; player hangs off the rim. "
            "The ball must leave the hand before the last key. Hoop never moves. "
            "The rim is a CLOSED horizontal loop in the XY plane, with nonzero extent in BOTH x and y; "
            "all rim points share the same z. Construct it with four curved quarter arcs around its center, "
            "not one curve going out and back along a line. It must enclose a visible opening in TOP view. "
            "Use a named rim center (cx, cy, h) and start its loop at the RIGHTMOST point (cx+r, cy, h); "
            "then visit back (cx, cy+r, h), left (cx-r, cy, h), front (cx, cy-r, h), and right again. "
            "The rim center is the midpoint of its sampled x/y bounds, not the first path point. "
            "Before the ball descends across rim height, its center must already be above that opening: "
            "at Key B place the ball center at the rim center's x and y, just above its z. "
            "During the dunk descent keep ball x and y inside the rim opening while z decreases below the rim. "
            "Perspective view: player recedes toward the hoop. Orthographic front view shows the jump in z; "
            "top view shows travel along +y toward the hoop."
        ),
        "part_range": (10, 16),
        "target_frames": 16,
        "gif_ms": 80,
        "n_subjects": 1,
    },
    "cmp_horse": {
        "task_id": "anim3d_cmp_horse",
        "concept": "a horse galloping away in depth",
        "prompt": "A galloping horse.",
        "people_scale": (
            "Horse about 1/4 of scene height. Cute closed body+neck+head as ONE outline, neck standing UP; "
            "fuse muzzle if cleaner else a small extra oval; mane, two ears, short vertical-tick eye, "
            "four SHORT single-line legs, LONG streaming tail about as long as the body. No rider. Not a stick horse."
        ),
        "staging": (
            "Ground at z=0. One horse facing +y, traveling deeper. "
            "Key A: near-camera contact stride, one foreleg reaching +y. "
            "Key B: opposite stride, body farther in +y. "
            "Key C: last frame — farther still, still a real stride. "
            "Top view must show +y travel, not a sideways slide. Swap which legs lead between keys."
        ),
        "part_range": (10, 18),
        "target_frames": 12,
        "gif_ms": 80,
        "n_subjects": 0,
    },
    "cmp_punch": {
        "task_id": "anim3d_cmp_punch",
        "concept": "a boxer throwing a powerful punch in 3D",
        "prompt": "The boxer throws a powerful punch.",
        "people_scale": "Person about 1/4–1/3 of scene height, stocky stick boxer, round head only.",
        "staging": (
            "Ground at z=0. One stick boxer facing +y, optional second boxer farther +y. "
            "Key A: guard, punching arm back, torso coiled. "
            "Key B: CONTACT — fist reaches the opponent or the air in front; torso leans into the punch. "
            "Key C: last frame — follow-through. Head center and torso move with the arm."
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
    anchor_scene: dict | None = None,
    anchor_name: str = "",
) -> str:
    parts = plan.get("parts") or []
    motion_neighborhood = planned_motion_neighborhood(plan, key_i)
    lines = [
        f"3D KEY {key_i}/{n_keys} named '{key.get('name')}' (beat: {key.get('beat', '')}).",
        f"Shot: {plan.get('action') or ''}",
        f"Plan notes: {plan.get('notes') or ''}",
        f"MOTION NEIGHBORHOOD from the existing plan (no extra planner fields): {motion_neighborhood}",
        "Draw this ONE pose as a Path3D spatial line sketch. Same named parts on every key.",
        'Spatial volume (hard): Solid spherical bodies must be genuine spatial wireframes, using at least three mutually perpendicular great-circle contours under their existing part id, not a flat circular billboard. Solid boxes/slabs must have depth and connected front/back edges. Front, side and top must all reveal volume. Do not force all curves into one depth plane. For an explosion, fragments travel in x, y and z; a destroyed spherical body must collapse into the explosion core rather than remain as an intact sphere. Any anchored emitter stays rigid and stationary. This describes shape and motion requirements, not supplied coordinates.',
        "Include every listed part using its EXACT id once. Helper strokes must use '<part_id>_...' ids.",
        "A character or prop that has not entered yet, or has already vanished, must still keep its exact id as "
        "one zero-length M stroke. Do not omit it. Expand that same id when it appears; collapse it again when absent.",
        "Do not rename parts between keys or between edit rounds (no walker_head_new / _emerge / _2).",
        "Head size/shape and build stay unchanging. People heads are circles of the same size every key.",
        ANIMAL_DRAWING,
        INK_STYLE,
        VISUAL_COMMUNICATION,
        "Animal ears sit on the crown (+z / on top of the head), not flipped onto the chin or snout.",
        "If this beat is walking or stepping, show a stride: one leg forward, the other back; arms counter-swing.",
        "Motion handoff (hard): infer how this pose is reached and left from the previous/current/next beats above. "
        "The pose must be compatible with both neighbors in x/y/z. A key is a sampled pose, not an automatic pause. "
        "Do not make an unplanned full stop at this key, reset acting limbs, "
        "swap which hand holds a prop, jump to another depth lane, or move a traveler discontinuously.",
        people_scale_line(None),
        "Four views must show the same 3D structure: front and side keep ears on the crown (+z); "
        "top view shows left/right ears and depth along +y.",
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
    if anchor_scene and key_i > 2:
        lines.append(identity_anchor_context(anchor_scene, anchor_name=anchor_name or "first"))
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
Plan notes: {plan.get('notes') or ''}
{story}

{INBETWEEN_REASONING}

Parts (exact ids required):
{part_lines}

Identity (hard):
- Include every plan part id exactly once. Helpers only: '<part_id>_...'.
- Do not rename (no _new, _emerge, _2, _b). Changing pose keeps the same ids.
- Head size/shape and build stay unchanging. Anchored scenery stays put.
- {ANIMAL_DRAWING}
- {VISUAL_COMMUNICATION}
- {people_scale_line(None)} Keep the scene inside x/y/z [-1,1].
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
