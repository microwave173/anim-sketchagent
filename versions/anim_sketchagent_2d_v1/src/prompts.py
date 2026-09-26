"""Pose-to-pose planner/drawer prompts for 2D Path2D clips."""
from __future__ import annotations

import json

MIN_FRAMES = 4
MAX_FRAMES = 20
MIN_KEYS = 2
MAX_KEYS = 6
MIN_PARTS = 6
MAX_PARTS = 22
DEFAULT_PEOPLE_SCALE = (
    "Standing height (feet to head-top) is 1/5–1/4 of the GROUND LINE LENGTH "
    "(the horizontal span of the anchored ground stroke), not 1/4 of the canvas. "
    "Torso M neck Q hip: neck under the head (higher y), hip lower y, halfway from head-top to feet. "
    "Attached parts share the joint (x,y). A small traveling prop is smaller than a head."
)
DRAWER_ORIENTATION = (
    "Do not flip the figure upside-down or left-right. "
    "Head and ears stay above the body (higher y); feet on the ground (lower y). "
    "If facing right, the head/muzzle is at +x and the tail at −x. "
    "Keep each head the same size on every frame. "
    "Scale: a standing person is 1/5–1/4 as tall as the ground line is long. "
    "People heads MUST be round Q loops (four or more Q segments, then Z). "
    "Example: M cx cy+r Q cx+r cy+r cx+r cy Q cx+r cy-r cx cy-r Q cx-r cy-r cx-r cy Q cx-r cy+r cx cy+r Z. "
    "Do not draw people heads as polygons of L (no hexagon, octagon, or diamond), teardrops, or long ovals. "
    "The neck attaches at the BOTTOM of the head circle (the lowest y on the Q loop), never at the head center. "
    "Do not run the torso or arms through the middle of the head. "
    "A stick person's head is ONLY that one round Q loop. "
    "Do not add hair, ponytails, bangs, hats, faces, eyelashes, or ticks beside the head. "
    "Do not invent helper ids like '<head_id>_ponytail' or '<head_id>_hair'. "
    "Animal ears sit on the CROWN of the head (apex y greater than the head-center y), "
    "not on the chin, not on the snout, and not hanging under the head. "
    "Connectivity (hard): every attached pair of strokes shares the exact joint (x,y) on THIS frame. "
    "No gaps, no floating parts. If a parent joint moves, the child's attachment end moves with it — "
    "do not copy a previous-frame path for a child whose parent moved. "
    "People: torso is M neck Q hip (a curve, not a straight L). Neck is the FIRST point, under the head, HIGHER y; "
    "hip is the LAST point, LOWER y, halfway from head-top to the feet — never above the head. "
    "Head meets the neck at the chin/bottom of the circle; BOTH arms meet that same neck; BOTH legs meet the hip. "
    "If a limb bends (elbow/knee), consecutive segments share that vertex. "
    "Animals: ears on the crown; legs meet the body/chest; tail meets the rump. "
    "A held prop meets the hand. A hanging prop meets its support; that support meets its fixture. "
    "A traveling object only detaches after the contact beat. "
    "Scale (hard): obey the plan notes when they specify scale. Standing height is a fraction of the GROUND STROKE LENGTH drawn on THIS frame, "
    "not of the canvas. If the plan says 1/5–1/4, feet-to-head-top must be that fraction of the ground line you actually drew. "
    "Do not draw a figure that is half the ground span unless the plan says so. "
    "Relative placement (hard): if two parts should touch, their strokes meet at that joint this frame. "
    "A projectile that has not yet left sits at the emitting end of the held tool — same height as that shaft's last point, "
    "a tiny offset past the tip — not floating in empty space toward the target. "
    "Do not start a traveler halfway down the path on the first pose. "
    "A planted foot may stay on the ground, but that leg's hip end still tracks the current hip. "
    "Distinctive props must read as their type, not as extra limbs or scribbles: use the fewest strokes that make the object recognizable. "
    "Curves vs straight (hard): Q/C for swinging/bent limbs, spines, tails, hanging lines, bouncing arcs, "
    "and round heads or round props. Straight L MUST be used when the thing is actually straight: ground, poles, "
    "posts, flat edges, and rigid shafts. Do not put a Q on a vertical post or a flat ground line. "
    "Do not build a whole pose as a polygon of L. "
    "Open centerlines (people): torso, limbs, and held props are open strokes — never Z. "
    "Z is only for stick heads, round props, and animal body/head masses. "
    "People: do not outline a filled silhouette or double-stroke a limb. "
    "Whole-body motion: head, torso/spine, hips, and both arms change pose between keys. "
    "Do not freeze the trunk and only swing one limb or one prop. "
    "Head keeps a constant SIZE but its center travels with the neck (lean, crouch, look). "
    "Identity (hard): keep the SAME height, limb length, and stocky-vs-slim build as the plan notes and previous pose. "
    "Do not grow, shrink, or fatten a character between keys or inbetweens. "
    "Walk/run (hard): a traveling person is NEVER both feet under the hip. "
    "Contact stride: one foot reaching or planted forward, the other trailing back (heel may lift). "
    "Do not ice-skate. Consecutive keys that travel must swap which leg is forward. "
    "Torso tilts with the beat: coil away on the wind-up, lean into contact, continue through follow-through. "
    "Only anchored scenery stays still."
)
ANIMAL_DRAWING = (
    "People vs animals (hard): "
    "People stay stick figures. Animals are NOT stick figures. "
    "Draw animals as cute, lively children's sketches, not realistic anatomy, "
    "not a round lollipop head on a stick spine. "
    "Animal construction: "
    "Body is one closed oval, bean, or a slightly reshaped closed curve (Z allowed). "
    "Head is likewise a closed oval, bean, or simple closed curve. "
    "Short-neck animals (cat, dog, pig, rabbit, bear, etc.): do NOT draw a neck; "
    "join the head directly to the body as two touching or overlapping closed shapes. "
    "Long-neck animals (horse, giraffe, swan, goose, etc.): body + neck + head is ONE continuous closed outline, "
    "like a single pen stroke. No seam line where neck meets body, and no seam where neck meets head. "
    "Default long-neck pose: the neck stands UP, erect toward the sky, not laid flat along the back. "
    "Muzzle (horse, dog, pig, etc.): an extra oval on the front of the head is allowed; "
    "if joining muzzle and head in ONE closed outline looks cleaner, fuse them instead of a separate muzzle oval. "
    "Legs: one open stroke each (a single line). Four legs if the animal has four. Far legs sit slightly behind. "
    "Legs default SHORT — cute stubby ticks, not long stick-person limbs. "
    "Tail length (hard): shortening the legs does NOT shorten the tail. "
    "Default tails are LONG: from the rump they should read about as long as the body mass, "
    "streaming well past the hind legs (horse: a flowing plume; cat/dog: a long curve). "
    "Do not draw a tiny stub tail. Exceptions: rabbit cottontail is a small puff; pig tail may be a small curl. "
    "No tube legs, no double outline, no hoof boxes unless the plan names hooves as a tiny extra mark. "
    "Face marks (hard): do NOT omit eyes, nose, or ears on animals. "
    "Tell-tale parts must be OBVIOUSLY readable at a glance — ears, eyes, nose/muzzle, mane, tail. "
    "Do not hide them by tracing the head or body outline. "
    "An ear must stick OUT from the crown as its own silhouette: "
    "a floppy dog ear hangs off the back of the head; cat/horse/rabbit ears poke up from the crown. "
    "Do not draw an ear as a curve that follows the skull. "
    "The eye tick sits INSIDE the head, not on the outline. "
    "Eyes default to a short vertical tick (a tiny L or Q dash). Only PEOPLE omit eyes (and hair/face). "
    "Distinctive features must be drawn — the marks that make the species readable "
    "(cat: pointed ears on the CROWN; dog: floppy ear hanging OFF the crown; horse: mane, upright neck, and long muzzle; pig: snout disk and curly tail; "
    "bird: beak and wing; rabbit: long ears; cow: horns; fish: tail fin). "
    "Draw order (hard): (1) body, and neck if long-neck, and head as the closed mass(es) — "
    "fuse muzzle into that outline when it reads better; "
    "(2) then the legs, each a SHORT single line from the body toward the ground; "
    "(3) then the other tell-tale parts (ears, nose or muzzle oval if not fused, mane, tail from the rump, "
    "eye as a short vertical tick, beak, etc.). "
    "Do not leave construction seams, inner ovals, or a stick skeleton inside the animal."
)
ANIMAL_PLAN_PARTS = (
    "Plan the parts list to match that recipe. Animals MUST include drawable parts for eyes "
    "(short vertical ticks), ears, and nose — unless muzzle is fused into the head/body outline, "
    "in which case still include eyes and ears. Those face parts must stay obviously readable, not fused into the head outline. "
    "In parts[].notes, name the parent and the relative seat: ears ON TOP of the head (crown, above the head-center); "
    "eye tick INSIDE the head; tail from the rump; legs from the body toward the ground. "
    "People still omit eyes, hair, and face. "
    "Default short legs. Tails stay LONG (do not stub them when legs are short). Default long-neck: neck stands upright."
)
INK_STYLE = (
    "Ink (hard): every stroke uses color #111111, stroke_width 3, and opacity 1. "
    "Never change line thickness or color between strokes, parts, or frames."
)
VISUAL_COMMUNICATION = (
    "Visual communication outranks literal realism (hard): draw for an audience who must understand the event immediately, "
    "not for anatomical or mechanical realism alone. Preserve physical logic, but use clear staging, separated silhouettes, "
    "purposeful exaggeration, iconic shapes, motion signs, and uncluttered negative space when they make the subject, action, "
    "cause, or state change easier to recognize. Make the decisive information visibly large enough and spatially unambiguous: "
    "the acting hand must visibly meet the control, an emitted stream must visibly connect source to target, and a removed or "
    "transformed object must have a clearly different silhouette/state. Do not hide a critical event in tiny realistic detail, "
    "occlusion, tangency, or decorative clutter. A viewer should understand each key beat from the drawing without reading its caption."
)
DRAWER_ORIENTATION = DRAWER_ORIENTATION + " " + ANIMAL_DRAWING + " " + INK_STYLE + " " + VISUAL_COMMUNICATION
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
    "a fire disappears only after water reaches it. If this frame is before the causal boundary, preserve the earlier state. "
    "If it is after the boundary, make the new state visibly legible instead of blending both states ambiguously. "
    "Keep the same character height and build as FROM; only the pose advances. "
    "Honor the planned duration of this gap: a short snap should already be close to TO, "
    "a long interval should still look early if t is small — do not jump to the next key in one frame. "
    "Walk/run fill (hard): if FROM and TO are opposite contact strides, this frame is a passing pose "
    "(legs gathered or crossing under the body), not both feet sliding the same way. "
    "Advance the stride: the trailing leg of FROM starts to swing forward. Do not copy FROM's feet. "
    "Do not copy FROM or TO."
)


def people_scale_line(plan_or_task: dict | None = None) -> str:
    value = plan_or_task or {}
    text = str(value.get("people_scale") or value.get("notes") or "").strip()
    return DEFAULT_PEOPLE_SCALE + (" Plan notes: " + text if text else "")


def previous_key_context(prev_scene: dict, *, prev_name: str, key_i: int, limit: int = 12000) -> str:
    brief = json.dumps(
        {
            "strokes": [
                {
                    "id": item.get("id"),
                    "path": item.get("path"),
                    "description": item.get("description"),
                }
                for item in prev_scene.get("strokes") or []
            ]
        },
        ensure_ascii=False,
    )[: int(limit)]
    return (
        f"\n\nPREVIOUS KEY '{prev_name}' (already drawn, key {key_i - 1}). "
        "This is the immediate motion predecessor. Keep the same stroke ids, head SIZE, character build, "
        "attachment topology, facing, and prop dimensions. Infer and continue its displacement and articulation direction: "
        "do not teleport, reverse direction, swap limbs, or reset to a neutral pose unless the plan explicitly says so. "
        "Redraw the WHOLE pose for THIS beat — head center, torso tilt, hips, and arms must move, not only the acting limb. "
        "Do not copy previous-key coordinates for head or torso.\n"
        f"{brief}"
    )


def identity_anchor_context(anchor_scene: dict, *, anchor_name: str = "first", limit: int = 12000) -> str:
    """First-key geometry is an appearance reference, not a pose to copy."""
    brief = json.dumps(
        {
            "strokes": [
                {
                    "id": item.get("id"),
                    "path": item.get("path"),
                    "description": item.get("description"),
                }
                for item in anchor_scene.get("strokes") or []
            ]
        },
        ensure_ascii=False,
    )[: int(limit)]
    return (
        f"\n\nIDENTITY ANCHOR '{anchor_name}' (the accepted first key). "
        "Use it only as the immutable model sheet: preserve each subject's head radius, torso length, limb lengths, "
        "body build, animal silhouette, prop dimensions, line construction, and part-to-parent attachment pattern. "
        "The immediate PREVIOUS KEY controls position and motion; this anchor controls appearance. "
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
    """You are a sketch planner for pose-to-pose 2D stick-figure animation.
Return JSON only. No markdown.

The drawer draws ONLY keys as Path2D (M/L/Q/C/Z, [-1,1], +x right +y up).
Inbetweens are a later one-shot redraw of the SAME named parts — the key drawer will not see them.
The user message gives the permitted or exact key count; follow it. Never use more than 12 keys. Add a key only for contact, detach, a causally distinct story beat, or a new silhouette. No grid cells like x12y20.
Keys are pose notes only (name, beat, notes). Do not emit Path2D, path strings, or coordinates on keys — the drawer decides geometry.

The first key is frame 1 of the clip. The last key is the last frame. The last key must show the finished action, not a mid-travel pose.

"action" is a DIRECTOR rewrite, not a paraphrase. Restage so a viewer can read the story at a glance, while keeping the user's intent. Spread the cast across the stage when the story needs distance and give traveling things enough empty space to read.

Causal chronology (hard): write the action and keys as an ordered chain of completed prerequisites and consequences. An effect, transformation, disappearance, or newly introduced object may begin only after its enabling beat is visibly complete. For example, watering must finish before blooming begins; an alarm must be pulled before a sprinkler starts; water must reach a fire before the fire disappears. Do not merge cause and consequence into one vague key. In every key beat/notes, state what has completed, what is happening now, and what has not started yet whenever the boundary could be ambiguous.

Visual communication (hard): plan for audience recognition, not literal realism alone. Choose staging, silhouette, scale, spacing, iconic signs, and permissible exaggeration so the subject, action, causal link, and state change read immediately at thumbnail size. Reserve clear negative space around decisive interactions and require critical contacts or emissions to be visibly connected. Do not rely on tiny realistic detail or the text prompt to explain the drawing.

"action" still covers: who, left/right, beat order, what travels, what stays put (head SIZE, body BUILD, scenery).
Identity (hard): each character's height, stocky-vs-slim build, limb length, and head size are UNCHANGING across keys. Pose and placement change; the body recipe does not. Do not grow, shrink, or fatten anyone between keys.

Timing and action density (hard): the user message gives the exact frame count, milliseconds per frame, and total playback seconds. Design enough visible action for that real duration; do not stretch a short action by holding one pose. gaps[].n_inbetween is how much TIME sits between those two keys, not padding. A fast hit, release, catch, or snap uses few inbetweens (1–3). A brief gather, plant, or anticipation normally uses fewer frames than the travel or consequence it enables. A long travel, hang-time, or slow settle may use more only while something visibly changes in every frame. No stationary hold, carried-object pose, crouch, or finished pose may consume a large fraction of the clip unless the user explicitly asks for a pause. For a multi-stage action, reach the main event around the middle-to-late part of the clip and reserve meaningful time afterward for its visible consequence; do not postpone the defining event until the last few frames. If the requested runtime is longer than the described action naturally needs, enrich the director rewrite with plausible sub-beats (for example distinct strides, dribbles, follow-through, landing, rebound, or reaction) instead of slowing a single transition. Do not give every gap the same count unless the beats really last the same. gaps[].why must state the interval's approximate seconds, whether it is quick/medium/long, and what visible change fills that time. gaps[].ease matches the beat: linear for steady travel, ease_out for arriving/settling, smooth for an arc.

Each key must be a different WHOLE-BODY pose: head center, torso tilt, hips, arms, and acting limb all change. Do not freeze the trunk and only swing one limb.
If anyone is walking or running, consecutive keys must SWAP the stride: one key is contact (front foot +x, trailing foot −x, or the reverse); the next key uses the opposite pair. Write that into key.notes (which leg is forward). Never ice-skate with both feet planted under the hip while the body slides.
Each key.notes is brief but must include (1) head and torso for that beat and (2) ORIENTATION of the main parts: which way the head looks, which way the torso leans, which way a held tool or acting limb aims (+x/−x, up/down). No coordinates.
Each parts[].notes MUST name the parent and the relative seat — above/below, in front/behind, inside/outside — plus a short facing/pointing clause. Do not write path strings. Examples: "ON TOP of the head, higher y than head-center"; "meets the BOTTOM of the head"; "INSIDE the head, not on the outline"; "from the rump, streaming −x"; "from the belly DOWN to the ground"; "looks +x".

Write one concise notes field: one short semicolon-separated sentence, at most 180 characters, covering only fixed scale/identity, essential stage placement or travel lane, and any crucial attachment the drawer could otherwise misunderstand. Do not retell the action.

Relative placement (hard): attached parts are not free-floating labels. The planner must say where each child sits on its parent using axes (+x right, +y up). People: neck under the head; both arms meet that neck; both legs meet the hip. Animals: ears ON TOP of the head (crown, higher y), never on the chin or tracing the skull; eye tick INSIDE the head; tail from the rump; legs from the body toward the ground.
"""
    + ANIMAL_DRAWING
    + " "
    + ANIMAL_PLAN_PARTS
    + " "
    + INK_STYLE
    + """

Parts: motion "moving" or "anchored". Same parts[].id on every key.
Parts are drawable strokes only (head, torso, limbs, props, scenery, and animal face marks). Do not add joint-only parts such as neck, hip, shoulder, elbow, or knee as their own ids — those are shared endpoints on torso/limbs. A long-neck animal's neck is NOT its own part; it lives inside the one closed body+neck+head outline.
Stick people: one round head, torso, two arms, two legs. Do not add hair, ponytail, hat, or face parts. Do not write "her/his hair" into action.
"anchored" is scenery only. Never mark a limb, torso, head, tail, or held prop as anchored.
A planted foot or hanging support end may stay put in the world, but the attachment end still follows its parent joint.
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
    fewshot: bool = True,
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
        pick = f"Pick exactly {int(n_keys)} keys."
        key_rule = f"- keys length must be {int(n_keys)}. gaps length must be {int(n_keys) - 1}.\n"
    else:
        pick = f"YOU choose how many keys: {lo}–{hi}. Do not pad."
        key_rule = f"- keys length is YOUR choice, {lo}–{hi}. gaps length must be keys-1.\n"
    if pin_frames:
        frame_rule = f"- keys + all n_inbetween MUST total {pin_frames}.\n"
    else:
        frame_rule = f"- Around {suggested_frames} frames is the default. Stay in {MIN_FRAMES}–{MAX_FRAMES}.\n"
    if fewshot:
        staging = str(task.get("staging") or "").strip()
        staging_block = f"\nStaging:\n{staging}\n" if staging else ""
        legacy_notes = " ".join(
            text for text in (str(task.get("people_scale") or "").strip(), staging) if text
        )
        scale_block = f"\nExisting task constraints (compress into notes):\n{legacy_notes}\n" if legacy_notes else ""
        schema = f"""Return JSON:
{{
  "concept": "{task['concept']}",
  "action": "director rewrite: readable staging; beats; facing; what travels",
  "notes": "one short sentence, <=180 chars: fixed identity; essential layout/travel; crucial attachment",
        "parts": [{{"id": "person_head", "name": "person_head", "how": "circle", "motion": "moving", "notes": "same size; looks +x; neck meets BOTTOM of head"}}],
  "keys": [{{"name": "start", "beat": "short beat", "notes": "this pose; head/torso facing and lean"}}],
  "gaps": [{{"after": "start", "n_inbetween": 3, "ease": "linear|smooth|ease_out", "why": "how long this interval is and why this many frames"}}]
}}"""
    else:
        staging_block = ""
        scale_block = ""
        schema = """Return one JSON object with fields:
concept, action, notes,
parts (each: id, name, how, motion, notes),
keys (each: name, beat, notes),
gaps (each: after, n_inbetween, ease, why).
No example strokes, no sample poses."""
    return f"""User request: {task['prompt']}
{staging_block}{scale_block}
{pick}

Playback budget (hard): {playback_frames} frames × {playback_ms} ms/frame = {playback_seconds:.2f} seconds. Expand or compress the visible story beats to fit this actual screen time. Do not fill surplus frames by holding a ball, prop, crouch, or finished pose.

{schema}

Hard rules:
- parts {n_min}–{n_max}, same ids on every key.
- Fill notes with one short semicolon-separated sentence of at most 180 characters. Include only fixed scale/identity, essential layout/travel, and a crucial attachment if needed.
- First key = frame 1. Last key = last frame; that pose is the completed action.
{key_rule}{frame_rule}- Include a hit/release/detach key if the action has one.
- Each gap n_inbetween is timing: more frames = more time. why must give approximate seconds, visible change, and justify that duration.
- Write each key's ordinary notes so the pose is causally compatible with the keys immediately before and after it: name facing, travel direction, leading or planted limb, held/touching/released state, and the whole-body follow-through when relevant. A key is a sampled pose, not an automatic pause. Do not add extra schema fields for motion continuity.
- Adjacent key notes must not imply an unplanned stop, reversal, limb swap, change of holding hand, or prop teleport. Gap drawers will infer boundary motion from these ordinary notes and the neighboring key geometry.
- Keep preparation proportionate. Brief holds such as gather/plant/wind-up should be short; use the remaining runtime for distinct motion beats and consequences.
- Stick people: no hair/ponytail/hat parts. People omit eyes.
- parts[].notes must say where the part sits on its parent (ears ON TOP of the head; eye INSIDE the head; neck under the head). No coordinates.
- Animals: use the full animal construction (closed body/head; no extra neck on short-neck species; long-neck stands UP as one outline; SHORT single-line legs; LONG tail, not a stub; do not omit eyes/ears/nose; ears stick OUT from the crown and must be obviously readable; eyes are short vertical ticks inside the head; fuse muzzle into the head if cleaner).
- Walking/running keys must name which leg is forward; consecutive keys swap the stride.
"""


# Paper eval set (5). Physics (bounce, billiards) + shatter + rally + animal.
SUITE = ("bounce", "billiards", "bottleshot", "badminton", "catjump")

TASKS = {
    "kick": {
        "task_id": "path2d_kick",
        "concept": "a stick figure taking a penalty kick",
        "prompt": "A stick figure penalty-kicks a ball into the right-side goal.",
        "staging": (
            "Side view. Ground line anchored near y=-0.7. A simple goal (two posts + crossbar) on the right, anchored. "
            "One stick person on the left, one ball on the ground. "
            "Key A: torso coils back, head over the plant foot, kicking leg back, arms counter-rotate. "
            "Key B: CONTACT — torso and head lean into the kick, kicking foot meets the ball. "
            "Key C: last frame — DETACH, ball inside the goal; torso and head still leaning toward the goal, kicking leg followed through. "
            "People standing height 1/5–1/4 of the ground-line length. Head SIZE never changes, but the head and torso move. Ball smaller than the head."
        ),
        "part_range": (8, 16),
        "target_frames": 12,
        "gif_ms": 80,
    },
    "basketball": {
        "task_id": "path2d_basketball",
        "concept": "a stick figure shooting a basketball",
        "prompt": "A stick figure jump-shoots a basketball into a hoop on the right.",
        "staging": (
            "Side view. Ground anchored. Hoop on a pole at the right, rim above head, anchored. "
            "One person left-of-center, one ball. "
            "Key A: knees bent, torso crouched, head over the ball at chest. "
            "Key B: RELEASE — legs extend, torso and head rise, arms up, ball leaving the hands. "
            "Key C: last frame — ball at/through the rim; torso still arched, head looking at the rim. "
            "People standing height 1/5–1/4 of the ground-line length. Ball smaller than the head. Do not rename parts."
        ),
        "part_range": (8, 16),
        "target_frames": 12,
        "gif_ms": 80,
    },
    "badminton": {
        "task_id": "path2d_badminton",
        "concept": "two stick figures rallying badminton",
        "prompt": "Two people rally badminton across a full court: one at the far left, one at the far right; the shuttle flies a long path over the net, is returned, and comes all the way back.",
        "staging": (
            "Side view. Ground is a full-width straight L near y=-0.7. Net is one vertical L at x=0, chest/head height, anchored. "
            "WIDE COURT: left player's feet stay near the LEFT END of the ground (about x=-0.85); "
            "right player's feet stay near the RIGHT END (about x=+0.85). Do not park both near the net. "
            "The shuttle's flight is almost the full court — a long gap between them. "
            "Each racket is TWO parts: a straight L handle from the hand, plus a closed oval/ellipse head (Q loop + Z), smaller than a head. "
            "Left faces +x; right faces −x. Shuttle smaller than a head. "
            "The clip must finish a TWO-WAY rally: outbound hit, then a completed return that arrives back at the left. "
            "Use enough keys to make both hits readable (typically five): "
            "Key A: left contact at the left end — left racket meets the shuttle. "
            "Key B: shuttle HIGH over the net going +x in the long empty middle; both recovering at their ends. "
            "Key C: right contact at the right end — right racket meets the shuttle (not already past it). "
            "Key D: shuttle HIGH over the net going −x, inbound; both recovering. "
            "Last key: left contact again — left racket meets the returning shuttle. Do not end with the shuttle still leaving the right side. "
            "People standing height 1/5–1/4 of the ground-line length. Unique prefixes left_* and right_*."
        ),
        "part_range": (12, 22),
        "target_frames": 20,
        "gif_ms": 80,
    },
    "dogwalk": {
        "task_id": "path2d_dogwalk",
        "concept": "a small dog walking to the right",
        "prompt": "A small side-view dog walks to the right across the ground.",
        "people_scale": (
            "Dog about 1/5–1/4 of the ground-line length. Closed ellipse/bean body; closed oval head joined to the "
            "front of the body with NO separate neck; muzzle fused into the head if cleaner, else a small extra oval. "
            "Floppy ear hanging OFF the crown (its own silhouette, not tracing the skull), "
            "short vertical-tick eye INSIDE the head, SHORT single-line legs, LONG tail. Cute, not stick."
        ),
        "staging": (
            "Side view facing right. Ground line anchored near y=-0.7. One dog, no person, no ball. "
            "Closed ellipse body, oval head overlapping the upper-front (no neck stroke), "
            "floppy ear hanging OFF the crown so it is obviously readable, "
            "short vertical-tick eye inside the head, four SHORT single-line legs, LONG tail up. "
            "Key A: LEFT third, contact stride (one front leg forward, opposite hind forward). "
            "Key B: CENTER, passing stride, legs gathered under the body. "
            "Key C: last frame — RIGHT-CENTER, opposite contact, leave empty space at the right edge. "
            "Head stays above the body. Body and head translate right together and keep the same size."
        ),
        "part_range": (8, 16),
        "target_frames": 12,
        "gif_ms": 80,
    },
    "catjump": {
        "task_id": "path2d_catjump",
        "concept": "a small cat jumping onto a table",
        "prompt": "A small side-view cat jumps from the ground up onto a table.",
        "people_scale": (
            "Cat about 1/5–1/4 of the ground-line length. Closed ellipse/bean body; closed oval head joined to the "
            "front of the body with NO separate neck. Pointed ears on the crown, short vertical-tick eye, SHORT single-line legs. "
            "Long tail. Cute, not stick."
        ),
        "staging": (
            "Side view facing right (+x). Ground line anchored near y=-0.7. "
            "A simple table on the RIGHT is anchored: four short legs and a flat top at about mid-height. "
            "One cat, no person. Closed ellipse body. Closed oval head overlaps the UPPER-FRONT of the body; no neck stroke. "
            "Two pointed triangle ears sit on the crown (apex y greater than head-center y). Single-line legs. "
            "Key A: crouched on the GROUND left of the table, hips low, ready to spring. "
            "Key B: AIRBORNE — body stretching up-right toward the tabletop, feet off the ground, not yet landed. "
            "Key C: last frame — LANDED on the tabletop; all contact is on the table, not the ground; "
            "head still above the body, ears still on the crown. "
            "Head stays above the body. Face looks +x. Body and head keep the same size."
        ),
        "part_range": (9, 16),
        "target_frames": 12,
        "gif_ms": 80,
    },
    "catwand": {
        "task_id": "path2d_catwand",
        "concept": "a small cat playing with a teaser wand",
        "prompt": (
            "A small side-view cat plays with a teaser wand: a straight handle, a hanging string, "
            "and a tiny lure. The cat crouches, then bats the lure, then follows through."
        ),
        "people_scale": (
            "Cat about 1/5–1/4 of the ground-line length. Closed ellipse/bean body; closed oval head joined to the "
            "front of the body with NO separate neck. Pointed ears on the crown, short vertical-tick eye, SHORT single-line legs. "
            "Long tail. Cute, not stick. The lure is smaller than the cat's head."
        ),
        "staging": (
            "Side view facing right (+x). Ground line anchored near y=-0.7. "
            "One small cat on the LEFT–CENTER of the ground. No second animal. "
            "A teaser wand is THREE parts: a straight L handle from the UPPER RIGHT (held off the top-right, "
            "not a second person), a hanging string from the handle tip, and a tiny lure at the string's lower end. "
            "Handle is anchored. String and lure move. "
            "Key A: cat crouched on the ground, hips low, looking +x at the lure; lure hangs in front of the cat, not touching. "
            "Key B: CONTACT — a front paw meets the lure; body stretches toward +x/up; lure still on the string. "
            "Key C: last frame — lure yanked up-right away from the paw; cat in a follow-through stretch or sit-back, "
            "still looking at the lure. Head stays above the body. Ears stay on the crown. Same cat size every key."
        ),
        "part_range": (10, 18),
        "target_frames": 12,
        "gif_ms": 80,
    },
    "parkour": {
        "task_id": "path2d_parkour",
        "concept": "a stick figure vaulting a box while running right",
        "prompt": (
            "A small side-view stick person parkours to the right: runs up, vaults a box, and lands on the far side."
        ),
        "people_scale": (
            "Standing height (feet to head-top) is 1/5–1/4 of the ground-line length in every key. "
            "Same slim stick build, same head size, same limb length. Do not grow in the air or shrink on landing."
        ),
        "staging": (
            "Side view facing right (+x). Ground line anchored near y=-0.7 across the stage. "
            "One person only. An anchored BOX sits in the CENTER: a short rectangular obstacle "
            "(flat top + two vertical sides, straight L). Box top is about hip-to-waist height — vaultable, not a wall. "
            "Leave run-up room on the LEFT and landing room on the RIGHT. "
            "Key A: LEFT of the box, running +x, contact stride, torso leaning forward, looking at the box; not yet touching it. "
            "Key B: VAULT — hands (or one hand and a foot) plant on the BOX TOP; hips up and over the box; "
            "legs swinging toward +x; body not standing beside the box. "
            "Key C: last frame — LANDED on the GROUND to the RIGHT of the box, recovering a run stride, still facing +x; "
            "feet on the ground, not on the box. Same person size every key. Box and ground stay put."
        ),
        "part_range": (10, 18),
        "target_frames": 12,
        "gif_ms": 80,
    },
    "baton": {
        "task_id": "path2d_baton",
        "concept": "two stick figures handing off a baton",
        "prompt": (
            "Two side-view stick people pass a short baton: the left runner carries it, they meet, "
            "then the right runner leaves with the baton and the left hands are empty."
        ),
        "people_scale": (
            "Each person standing height is 1/5–1/4 of the ground-line length, same slim build and head size every key. "
            "The baton is a short straight L, smaller than a forearm."
        ),
        "staging": (
            "Side view. Ground anchored near y=-0.7. Two PLAIN stick people (round heads only, no hair): "
            "left_* faces +x, right_* faces +x (both running right). "
            "One baton. Unique prefixes left_* and right_*. "
            "Key A: LEFT of center — baton is IN the left hand only; right person's receiving hand is empty and still apart. "
            "Both are in a CONTACT stride (one leg reaching +x, the other trailing); not both feet under the hip. "
            "Key B: HANDOFF CONTACT — baton touches BOTH the left hand and the right hand at once; not floating between them. "
            "Each runner has the OPPOSITE stride from Key A (the trailing leg of A is now forward). "
            "Key C: last frame — baton is IN the right hand only, traveling +x with the right runner; left hands empty, left slowing or peeling off. "
            "Right runner another swapped stride; left may settle but still not a two-foot glide. "
            "Do not leave the baton in mid-air. Do not duplicate the baton. Same person sizes every key."
        ),
        "part_range": (12, 20),
        "target_frames": 12,
        "gif_ms": 80,
    },
    "cutrope": {
        "task_id": "path2d_cutrope",
        "concept": "scissors cutting a hanging rope into two pieces",
        "prompt": (
            "A hanging rope is cut by scissors: one line becomes two hanging ends."
        ),
        "people_scale": (
            "No full person required. Scissors about 1/6 of the ground-line length. "
            "The rope is a thin line. Two rope parts exist on EVERY key: rope_hi and rope_lo."
        ),
        "staging": (
            "Side view. Ground anchored near y=-0.7. An anchored fixture (hook or peg) in the UPPER LEFT. "
            "TWO rope strokes every key (do not rename, do not drop one): "
            "rope_hi hangs from the fixture; rope_lo is the lower half. "
            "Before the cut they JOIN end-to-end as ONE hanging line (rope_hi's lower tip equals rope_lo's upper tip). "
            "A scissors pair (two blades as L or a small X) is moving. "
            "Key A: one hanging line (the two rope parts joined); scissors approaching, NOT yet touching the join. "
            "Key B: CUT CONTACT — blade meets the join; the two rope parts still touch at that point. "
            "Key C: last frame — SEPARATED: rope_hi hangs from the fixture, rope_lo has fallen or hangs apart; "
            "a visible gap at the old join; scissors still near the cut but the rope is two pieces. "
            "Fixture and ground stay put. Do not keep a single uncut rope on the last key."
        ),
        "part_range": (8, 16),
        "target_frames": 12,
        "gif_ms": 80,
    },
    "dominos": {
        "task_id": "path2d_dominos",
        "concept": "four dominos knocking over in a chain",
        "prompt": (
            "Four upright dominos stand in a left-to-right row. The leftmost tips, each tile hits the next, "
            "and the last tile falls. They must fall one after another, not all at once."
        ),
        "people_scale": (
            "No people. Each domino is a tall thin rectangle about 1/6–1/5 of the ground-line length high, "
            "same size every key. Four tiles: d1 d2 d3 d4 from left to right."
        ),
        "staging": (
            "Side view. Ground anchored near y=-0.7. FOUR separate tiles in a row along +x, standing on the ground, not overlapping. "
            "Each tile is its own part (d1, d2, d3, d4), straight L rectangle (two longs + a top). Ground stays put. "
            "Use FIVE keys so the chain is readable (not three poses that lerp them all down together): "
            "Key A: all four UPRIGHT; d1 just beginning to lean +x, not yet touching d2. "
            "Key B: CONTACT — d1 hits d2; d1 clearly falling; d3 and d4 still upright. "
            "Key C: CONTACT — d2 hits d3; d1 mostly down; d4 still upright. "
            "Key D: CONTACT — d3 hits d4; d1 and d2 down or flat. "
            "Key E: last frame — d4 has FALLEN (flat or nearly); the cascade is finished. "
            "Never show all four at the same lean angle. Timing: short snaps between contacts (1–3 inbetweens), "
            "not one long blend. Total around 18 frames."
        ),
        "part_range": (8, 16),
        "target_frames": 18,
        "gif_ms": 70,
    },
    "boxing": {
        "task_id": "path2d_boxing",
        "concept": "two stick figures boxing",
        "prompt": "Two stick boxers face each other; the left one throws a punch that lands, then both recover.",
        "staging": (
            "Side view. Ground anchored near y=-0.7. Two people: left_* faces +x, right_* faces −x. No extra props. "
            "Key A: both in a guard, torsos coiled; left fist still back, heads up. "
            "Key B: CONTACT — left punch lands on the right guard or head; left torso and head lean into the punch; "
            "right torso and head snap back. "
            "Key C: last frame — follow-through/recover: left arm extending then dropping, right still recoiling or resetting. "
            "People standing height 1/5–1/4 of the ground-line length. Unique prefixes left_* and right_*."
        ),
        "part_range": (12, 16),
        "target_frames": 12,
        "gif_ms": 80,
    },
    "catwalk": {
        "task_id": "path2d_catwalk",
        "concept": "a small cat walking to the right",
        "prompt": "A small side-view cat walks to the right across the ground.",
        "people_scale": (
            "Cat about 1/5–1/4 of the ground-line length. Closed ellipse/bean body; closed oval head joined to the "
            "front of the body with NO separate neck. Pointed ears on the crown, short vertical-tick eye, SHORT single-line legs. "
            "Long tail. Cute, not stick."
        ),
        "staging": (
            "Side view facing right (+x). Ground line anchored near y=-0.7. One cat, no person, no mouse. "
            "Closed ellipse body. Oval head overlaps the UPPER-FRONT of the body; no neck stroke. "
            "Two pointed triangle ears sit on the crown of the head: apex y is GREATER than the head-center y "
            "(higher y; +y is up/sky; do not hang ears toward the ground or under the chin). "
            "Whiskers stick out from the +x muzzle. Tail from the rear (−x), curving up. Four SHORT single-line legs. "
            "Eye is a short vertical tick; do not omit ears, eye, or nose. "
            "Key A: LEFT third, contact stride (one front leg forward, opposite hind forward). "
            "Key B: CENTER, passing stride, legs gathered under the body. "
            "Key C: last frame — RIGHT-CENTER, opposite contact, leave empty space at the right edge. "
            "Head stays above the body. Ears on the crown (higher y). Face looks +x. Body and head translate right together and keep the same size."
        ),
        "part_range": (8, 16),
        "target_frames": 12,
        "gif_ms": 80,
    },
    "catmouse": {
        "task_id": "path2d_catmouse",
        "concept": "a small cat pouncing on a mouse",
        "prompt": (
            "A small side-view cat pounces on a mouse. The mouse runs right, the cat springs from behind "
            "and a front paw meets the mouse. Both are cute sketches, not stick figures. No person."
        ),
        "people_scale": (
            "ONE cute cat AND one cute mouse, both facing +x, no person. "
            "Cat about 1/5–1/4 of the ground-line length: closed ellipse/bean body, oval head joined at the front "
            "with NO neck stroke, pointed ears sticking OUT from the crown, short vertical-tick eye INSIDE the head, "
            "whiskers, SHORT single-line legs, LONG tail. "
            "Mouse much smaller than the cat (about a cat-head or less): closed oval body, oval head overlapping "
            "the upper-front with no neck, round ears sticking OUT from the crown, short vertical-tick eye inside the head, "
            "SHORT single-line legs, a LONG thin tail from the rump. Not stick animals."
        ),
        "staging": (
            "Side view facing +x. Ground line anchored near y=-0.7. ONE cat and ONE mouse; no person, no cheese, no hole. "
            "Left-to-right order until contact: cat (left, lesser x) then mouse (right, greater x). The cat chases; the mouse flees +x. "
            "Cat: closed ellipse body, oval head overlapping the upper-front, pointed ears on the crown, eye tick inside the head, "
            "LONG tail, SHORT legs. Mouse: tiny closed ovals, round ears sticking OUT from the crown, LONG thin tail, SHORT legs. "
            "Key A: LEFT–CENTER — cat crouched low looking +x at the mouse; mouse ahead on the ground, still free, not touching. "
            "Key B: CONTACT — cat springs +x; a front paw meets the mouse; mouse still its own shape, not fused into the cat. "
            "Key C: last frame — catch held: paw stays on the mouse; cat landed or settling; mouse under/at the paw, still readable as a mouse; "
            "leave a little empty ground at the right edge. "
            "Heads stay above bodies. Ears on the crown. Same sizes every key. Never ice-skate."
        ),
        "part_range": (14, 22),
        "target_frames": 12,
        "gif_ms": 80,
    },
    "highfive": {
        "task_id": "path2d_highfive",
        "concept": "two stick friends jumping high-five",
        "prompt": "Two stick friends run in, jump, and clap palms together in the air, then land apart.",
        "staging": (
            "Side view. Ground anchored near y=-0.7. Two people: left_* faces +x, right_* faces −x. No props. "
            "Key A: both on the ground, torsos leaning in, heads toward each other, hands apart. "
            "Key B: CONTACT — both airborne, hips up, heads still facing in, palms meet in the middle. "
            "Key C: last frame — both landed, torsos upright-ish, heads apart, hands down. "
            "People standing height 1/5–1/4 of the ground-line length. Unique prefixes left_* and right_*."
        ),
        "part_range": (12, 16),
        "target_frames": 12,
        "gif_ms": 80,
    },
    "creek": {
        "task_id": "path2d_creek",
        "concept": "a stick figure leaping a small creek",
        "prompt": "A stick figure jumps a small creek from the left bank onto the right bank.",
        "staging": (
            "Side view facing right. Two short ground pads only: left bank and right bank, both anchored. "
            "The middle is empty water — do not draw a connecting floor. One person. "
            "Key A: crouched on the LEFT bank, torso folded, head low. "
            "Key B: tucked in the AIR over the gap, hips up, head tucked, feet off both pads. "
            "Key C: last frame — landed on the RIGHT bank, torso unfolding, head up. "
            "People standing height 1/5–1/4 of the ground-line length. Head stays above the body. Do not flip."
        ),
        "part_range": (8, 14),
        "target_frames": 12,
        "gif_ms": 80,
    },
    "fish": {
        "task_id": "path2d_fish",
        "concept": "a stick figure yanking a tiny fish off the line",
        "prompt": "A stick figure on the left bank yanks a tiny fish out of the water; the fish leaps off the hook.",
        "staging": (
            "Side view. Ground/bank on the left, optional short water line on the right, both anchored. "
            "One person, one rod, one line, one tiny fish (oval or V, smaller than a head). No boat. "
            "Key A: rod cast, fish still in the water on the line. "
            "Key B: YANK — person leans back, fish just leaving the water. "
            "Key C: last frame — fish flying up-right off the hook; person in a surprised lean. "
            "People standing height 1/5–1/4 of the ground-line length."
        ),
        "part_range": (9, 14),
        "target_frames": 12,
        "gif_ms": 80,
    },
    "rabbithop": {
        "task_id": "path2d_rabbithop",
        "concept": "a small rabbit hopping to the right",
        "prompt": "A small side-view rabbit hops to the right: crouch, air, land.",
        "people_scale": (
            "Cute rabbit, not a stick figure, about 1/5–1/4 of the ground-line length. "
            "Eyes, nose, and long ears must be obviously readable so it is clearly a rabbit. "
            "The drawer chooses the rest of the construction."
        ),
        "staging": (
            "Side view facing right (+x). Ground anchored near y=-0.7. One rabbit, no person. "
            "No legs — the whole body translates. Ears stay on the crown, pointing +y, not hanging down. "
            "Key A: LEFT third, crouched on the ground. "
            "Key B: CENTER, airborne up-right, same size. "
            "Key C: last frame — RIGHT-CENTER, landed, empty space at the right edge. "
            "Head stays above the body. Face looks +x."
        ),
        "part_range": (7, 14),
        "target_frames": 12,
        "gif_ms": 80,
    },
    "bottleshot": {
        "task_id": "path2d_bottleshot",
        "concept": "a stick figure drawing a gun and shooting a hanging bottle",
        "prompt": (
            "A stick figure on the left draws a gun and shoots a bottle hanging from a rope on the right. "
            "The gun barrel points right toward the bottle, never reversed. "
            "The bullet hits the bottle and the bottle visibly explodes into shards."
        ),
        "staging": (
            "Side view facing right. Ground anchored near y=-0.7. "
            "One small person on the LEFT. A rope hangs from a high anchored hook on the RIGHT; a bottle dangles on that rope. "
            "Gun is a short L at the person's hand: the HANDLE/grip is at the hand, the BARREL is the long arm pointing +x "
            "(toward the bottle on the right). Do not reverse or mirror the gun. Do not point the muzzle left, at the ground, "
            "or back at the shooter. "
            "Bullet is a tiny tick, smaller than a head, traveling +x from the muzzle. "
            "Key A: gun drawn correctly (muzzle +x); torso and head leaning into the aim; bottle INTACT on the rope; "
            "bullet still at the muzzle. "
            "Key B: CONTACT — bullet meets the still-intact bottle; shooter still leaning; gun still aimed +x. "
            "Key C: last frame — the bottle has VISIBLY EXPLODED: the intact bottle silhouette is gone; "
            "draw several short shard ticks radiating from that spot. Keep the EXACT ids: "
            "'bottle' is those shards (one path with extra M subpaths), 'bullet' is still present as a tiny tick at/past the burst. "
            "Do not delete bottle or bullet. Do not rename them shards/debris. "
            "The rope still hangs empty; person in recoil, torso and head snapped back; gun may tilt but must not flip left-right. "
            "People standing height 1/5–1/4 of the ground-line length. Head is a circle and stays the same size. "
            "Do not flip the person."
        ),
        "part_range": (10, 16),
        "target_frames": 15,
        "gif_ms": 80,
    },
    "bounce": {
        "task_id": "path2d_bounce",
        "concept": "a ball bouncing twice with a lower second hop",
        "prompt": (
            "A ball falls, hits the ground, bounces up, then hits again. "
            "The second bounce is clearly lower than the first. No people."
        ),
        "people_scale": (
            "No people. The ball is about 1/10 of scene height. "
            "In the air it is a round Q loop; on contact it may squash into a wider oval, then round out again. "
            "Ground is a full-width anchored line near y=-0.7."
        ),
        "staging": (
            "Side view. Ground anchored. One ball only — no person, no hoop. "
            "The ball travels left-to-right while bouncing. "
            "Key A: HIGH in the air on the left, still ROUND, falling (not on the ground). "
            "Key B: first CONTACT — squash on the ground, wider than tall; this is the highest-energy hit. "
            "Key C: last frame — the SECOND hop: ball is airborne again but its peak is OBVIOUSLY lower than Key A, "
            "and it has moved right. Do not end still squashed on the first impact. Do not keep the same height. "
            "Ground stays put. Only the ball moves."
        ),
        "part_range": (6, 12),
        "target_frames": 12,
        "gif_ms": 80,
    },
    "billiards": {
        "task_id": "path2d_billiards",
        "concept": "a cue ball striking an object ball that then rolls away",
        "prompt": (
            "On a pool table, a cue ball hits a still object ball. "
            "After contact the object ball rolls away and the cue ball slows or stops. No people."
        ),
        "people_scale": (
            "No people. Two balls, each about 1/12 of scene height, round Q loops, smaller than a head would be. "
            "The table is a long anchored rectangle: a ground-like rail near y=-0.7 and short end cushions."
        ),
        "staging": (
            "Side view of a pool table. Table bed and two end cushions are anchored. Two balls, distinct ids. "
            "Cue ball starts LEFT; object ball is still, RIGHT of center. Optional pocket tick at the far right, anchored. "
            "Key A: cue ball traveling right, not yet touching; object ball fully still. "
            "Key B: CONTACT — the two balls meet; object ball just starting to move. "
            "Key C: last frame — object ball well to the RIGHT (near the far cushion or pocket); "
            "cue ball almost STOPPED or only creeping, left of the object ball. "
            "Do not make both balls fly at the same speed. Do not swap their identities."
        ),
        "part_range": (6, 14),
        "target_frames": 12,
        "gif_ms": 80,
    },
    "starwars": {
        "task_id": "path2d_starwars",
        "concept": "a stick jedi deflecting a blaster bolt that then downs a droid",
        "prompt": (
            "A stick-figure Jedi uses a lightsaber to deflect one blaster bolt back into a droid, defeating it."
        ),
        "people_scale": (
            "Jedi standing height is 1/5–1/4 of the ground-line length, slim stick build, round head only, no hair. "
            "The droid is a boxy stick machine about the same height, not a second person. "
            "The saber blade is a straight L a bit longer than a forearm; the bolt is a short thick dash, smaller than a head."
        ),
        "staging": (
            "Side view. Ground anchored near y=-0.7. One PLAIN stick Jedi (jedi_* prefix, faces +x) on the LEFT. "
            "One boxy droid (droid_* prefix, faces −x) on the RIGHT, with a short blaster arm. "
            "One saber in the Jedi's forward hand. ONE bolt stroke exists on EVERY key (id bolt) — never drop it, never duplicate it. "
            "Key A: droid has FIRING stance on the right; bolt is already in the air, still on the RIGHT half, traveling −x toward the Jedi; "
            "saber raised, not yet touching the bolt. "
            "Key B: DEFLECT CONTACT — saber blade TOUCHES the bolt at center-left; bolt has not passed the saber; Jedi torso coiled into the parry. "
            "Key C: last frame — the SAME bolt has reversed to +x and HITS the droid; droid is DEFEATED (tipped, slumped, or collapsing), not still aiming. "
            "Saber stays in the Jedi's hand. Do not leave the bolt floating unused. Same sizes every key."
        ),
        "part_range": (12, 18),
        "target_frames": 12,
        "gif_ms": 80,
    },
    "polevault": {
        "task_id": "path2d_polevault",
        "concept": "a stick athlete completing a pole vault",
        "prompt": (
            "A side-view stick athlete sprints right with a pole, plants it, swings over a high bar, "
            "releases the pole, and lands beyond the bar."
        ),
        "people_scale": (
            "Athlete standing height is 1/5–1/4 of the ground-line length in every key, with the same slim "
            "stick build, round head, limb lengths, and head size. The vaulting pole is a long thin open curve "
            "about twice the athlete's height."
        ),
        "staging": (
            "Side view facing +x. Ground is anchored near y=-0.7. One athlete only. A high bar and its two supports "
            "are anchored on the RIGHT; a small landing mat lies beyond it. The pole is one persistent part, never duplicated. "
            "Use FIVE keys so the sport reads correctly. "
            "Key A: RUN-UP on the left, athlete in a long stride carrying the pole diagonally forward; no plant contact yet. "
            "Key B: PLANT CONTACT before the bar, lower pole tip fixed on the ground box, pole visibly bent, arms loaded. "
            "Key C: SWING/INVERSION, hips and feet above the head, body rising along the bent pole on the left side of the bar. "
            "Key D: CLEARANCE/RELEASE, athlete arched horizontally above the bar with no body-bar contact; pole has sprung away and is no longer held. "
            "Key E: last frame — athlete has LANDED on the mat to the right, knees bent; bar remains on supports and pole lies/falls behind. "
            "Do not teleport through the bar. Ground, supports, bar, and mat stay put."
        ),
        "part_range": (12, 20),
        "target_frames": 18,
        "gif_ms": 75,
    },
    "magic_swap": {
        "task_id": "path2d_magic_swap",
        "concept": "a stick magician making a coin vanish and a flower appear",
        "prompt": (
            "A stick magician tosses a coin, snaps, and the coin suddenly vanishes while a large flower "
            "appears in the other empty hand."
        ),
        "people_scale": (
            "Magician standing height is 1/4 of the ground-line length, same slim stick build and round head every key. "
            "Coin is a tiny round mark smaller than a hand. Flower is a clearly readable stem plus a five-petal bloom, about head-sized."
        ),
        "staging": (
            "Side view. Ground anchored near y=-0.7. One plain stick magician at center; no hat, table, second person, or animal. "
            "The exact parts coin and flower exist on EVERY key to preserve ids, but visibility changes abruptly: an invisible part is encoded "
            "as one zero-length M at the relevant hand, never as a readable object. "
            "Use FOUR keys. Key A: coin visibly held in LEFT hand; RIGHT hand conspicuously empty; flower is collapsed to a zero-length M. "
            "Key B: coin visibly airborne just above the left hand; right hand still empty; torso and head track the coin. "
            "Key C: SNAP SWITCH — coin is now collapsed to a zero-length M and is not visible; flower is still collapsed; snapping hand at full extension. "
            "Key D: last frame — a full readable flower has SUDDENLY APPEARED in the raised RIGHT hand; coin remains invisible; magician presents it. "
            "Do not show coin and flower visibly at the same time. The reveal must be a topology change, not the coin morphing into a flower."
        ),
        "part_range": (10, 18),
        "target_frames": 14,
        "gif_ms": 90,
    },
    "firework": {
        "task_id": "path2d_firework",
        "concept": "a rocket rising and suddenly bursting into a firework",
        "prompt": (
            "A small firework rocket launches straight up, accelerates into the sky, then the rocket suddenly disappears "
            "and a wide starburst appears at its apex."
        ),
        "people_scale": (
            "No people or animals. Rocket is a small narrow body, about 1/7 of scene height. The final burst spans about half "
            "the scene width. Persistent ids rocket, trail, and burst exist on every key; inactive parts use one zero-length M."
        ),
        "staging": (
            "Vertical side view. A short anchored ground line and tiny launch stand sit at bottom center. No buildings or people. "
            "Use FOUR keys. Key A: rocket visibly rests on the stand; trail and burst are collapsed zero-length M marks. "
            "Key B: LIFTOFF — rocket is low in the air; a short visible trail begins below it; burst remains invisible. "
            "Key C: ASCENT/APEX — rocket is near the upper center with a longer tapering trail, still intact; burst remains invisible. "
            "Key D: last frame — EXPLOSION: rocket and trail are collapsed and not visible; burst suddenly becomes many radial rays/rings "
            "centered exactly at the former rocket apex. Do not keep an intact rocket inside the explosion. Stand and ground stay put."
        ),
        "part_range": (6, 12),
        "target_frames": 14,
        "gif_ms": 85,
    },
    # Published-prompt comparisons (not in SUITE). Same y as Live-Sketch / MoSketch / GroupSketch figures.
    "cmp_hoop": {
        "task_id": "path2d_cmp_hoop",
        "concept": "a stick person shooting a basketball into a hoop",
        "prompt": "This man is shooting at the basketball hoop in front of him.",
        "people_scale": (
            "Standing height 1/5–1/4 of the ground-line length, slim stick build, round head only. "
            "The ball is smaller than the head. The hoop is a simple rim, larger than the ball, smaller than the person."
        ),
        "staging": (
            "Side view. Ground anchored near y=-0.7. One stick person on the LEFT, facing +x. "
            "An anchored hoop+backboard on the RIGHT. One basketball (id ball) exists on EVERY key. "
            "Key A: person coiled to shoot, ball still in the shooting hand, not yet at the rim. "
            "Key B: RELEASE/ARC — ball has left the hand and is in the air between person and hoop, not stuck to the palm. "
            "Key C: last frame — ball at or through the rim; person in follow-through. "
            "Do not keep the ball glued to the hand on the last key."
        ),
        "part_range": (8, 16),
        "target_frames": 12,
        "gif_ms": 80,
    },
    "leadhorse": {
        "task_id": "path2d_leadhorse",
        "concept": "a stick figure leading a horse to the right",
        "prompt": (
            "A stick figure walks to the right IN FRONT of a horse, leading it. "
            "The horse FOLLOWS BEHIND the person on a lead rope. The person is on foot, not riding."
        ),
        "people_scale": (
            "ONE stick person AND one cute horse, both facing +x. "
            "Front/back is hard: the PERSON is IN FRONT (greater x, right side of the pair); "
            "the HORSE is BEHIND (lesser x, left side of the pair) and follows. "
            "Person standing height 1/5–1/4 of the ground-line length: round Q-loop head only (no hair/face/eyes), "
            "curved torso, open single-line arms and legs, hip halfway head-top to feet. "
            "Horse body length about 1/3 of the ground-line length; withers about as high as the person's shoulder. "
            "Horse: cute closed body+neck+head as ONE outline, neck standing UP; fuse muzzle if cleaner; "
            "mane, two ears sticking OUT from the crown, short vertical-tick eye INSIDE the head, "
            "four SHORT single-line legs, LONG streaming tail about as long as the body. Not a stick horse. Not a rider."
        ),
        "staging": (
            "Side view facing +x (right is the direction of travel). Ground line anchored near y=-0.7. "
            "ONE stick person leading ONE horse; no rider, no saddle, no second person. "
            "Left-to-right silhouette (hard, every key): horse rump (−x) → horse body → horse head/muzzle → lead rope → person. "
            "PERSON IN FRONT = rightmost of the two, larger x. HORSE BEHIND = left of the person, smaller x. "
            "Do not put the horse to the right of the person. The horse follows; the person walks ahead. "
            "The person's trailing (−x) hand holds the lead near hip height. "
            "A single open lead rope runs BACK (−x) from that hand to the horse muzzle; those joints meet. "
            "Person: round head, no face; walk stride. Horse: closed body+neck+head with neck UP; "
            "ears poke up from the crown; eye tick inside the head; SHORT legs; LONG tail from the rump (−x). "
            "Key A: pair in LEFT–CENTER; person still rightmost; both walk contact "
            "(person one foot +x / one −x; horse one foreleg +x, opposite hind trailing). "
            "Key B: pair at CENTER; both passing / gathered stride; person still ahead; lead still taut. "
            "Key C: last frame — pair at RIGHT–CENTER; person still ahead; opposite contact for both; "
            "leave empty space at the right edge ahead of the person. "
            "Person and horse translate right together, keep the same size, and keep this front/back order. Never ice-skate."
        ),
        "part_range": (14, 22),
        "target_frames": 12,
        "gif_ms": 80,
    },
    "cmp_horse": {
        "task_id": "path2d_cmp_horse",
        "concept": "a horse galloping to the right",
        "prompt": "A galloping horse.",
        "people_scale": (
            "Horse body length about 1/3 of the ground-line length. Cute closed body+neck+head as ONE outline, "
            "neck standing UP; fuse muzzle into that outline if cleaner, else a small extra oval. "
            "Mane, two ears, short vertical-tick eye, four SHORT single-line legs, LONG streaming tail about as long as the body. No rider. Not a stick horse."
        ),
        "staging": (
            "Side view. Ground anchored near y=-0.7. One horse facing +x, traveling right. "
            "Cute closed body+neck+head as one outline with the neck standing UP; fuse muzzle if cleaner; "
            "mane; two ears; eye as a short vertical tick; four SHORT single-line legs; LONG tail streaming past the hind legs. "
            "Key A: contact stride, one foreleg reaching +x, opposite hind trailing. "
            "Key B: opposite contact stride (legs swapped), body has moved +x. "
            "Key C: last frame — finished gallop still in a readable stride farther +x, not a freeze. "
            "Never ice-skate with all feet under the body."
        ),
        "part_range": (8, 16),
        "target_frames": 12,
        "gif_ms": 80,
    },
    "cmp_punch": {
        "task_id": "path2d_cmp_punch",
        "concept": "a boxer throwing a powerful punch",
        "prompt": "The boxer throws a powerful punch.",
        "people_scale": (
            "Standing height 1/5–1/4 of the ground-line length, stocky stick boxer, round head only. "
            "Optional second boxer on the right with unique right_* prefix."
        ),
        "staging": (
            "Side view. Ground anchored near y=-0.7. One or two stick boxers. "
            "If two, left_* faces +x and right_* faces −x. "
            "Key A: guard, punching arm still back, torso coiled. "
            "Key B: CONTACT — punching fist reaches the opponent guard or head; torso and head lean into the punch. "
            "Key C: last frame — follow-through or recover, punch already landed. "
            "Whole-body motion: head center and torso move with the arm."
        ),
        "part_range": (10, 16),
        "target_frames": 12,
        "gif_ms": 80,
    },
    # Verbatim captions from MoSketch data/raw/60sketches/caption.txt, so the
    # four baselines and we receive the same y on the same five scenes.
    "cmp_mo_basketball5": {
        "task_id": "path2d_cmp_mo_basketball5",
        "concept": "a stick player dunking a basketball into a hoop",
        "prompt": (
            "The player soars through the air with a basketball, arm extended for an electrifying slam dunk to a hoop."
        ),
        "people_scale": (
            "Standing height 1/5–1/4 of the ground-line length, slim stick build, round head only. "
            "The ball is smaller than the head. An anchored hoop with backboard on the RIGHT, rim above the player's head."
        ),
        "staging": (
            "Side view. Ground anchored near y=-0.7. One stick player on the LEFT facing +x; anchored hoop and backboard on the RIGHT. "
            "Persistent ids player, ball, hoop exist on every key. Use THREE keys. "
            "Key A: player takes off from the ground, ball held in the raised driving hand, still far from the rim. "
            "Key B: AIRBORNE — player is at rim height between the ground and the hoop, arm fully extended, ball above the rim. "
            "Key C: last frame — ball is through the rim and below it while the player hangs off the rim. "
            "Do not keep the ball glued to the hand on the last key. Hoop and backboard never move."
        ),
        "part_range": (10, 16),
        "target_frames": 16,
        "gif_ms": 80,
    },
    "cmp_mo_football4": {
        "task_id": "path2d_cmp_mo_football4",
        "concept": "a stick player bicycle-kicking a ball toward a goal",
        "prompt": (
            "A soccer player executes an acrobatic bicycle kick, sending the ball flying towards the goal."
        ),
        "people_scale": (
            "Standing height 1/5–1/4 of the ground-line length, slim stick build, round head only. "
            "The ball is smaller than the head. An anchored goal frame on the RIGHT, taller than the player."
        ),
        "staging": (
            "Side view. Ground anchored near y=-0.7. One stick player LEFT of center; anchored goal frame at the RIGHT edge. "
            "Persistent ids player, ball, goal exist on every key. Use THREE keys. "
            "Key A: player leaps backward off the ground, body tilting toward horizontal, ball in the air near kicking-foot height. "
            "Key B: CONTACT — player is inverted and nearly horizontal in mid-air, kicking foot meets the ball. "
            "Key C: last frame — ball has left the foot and travels +x toward the goal mouth; player falls back toward the ground. "
            "The ball must be clearly separated from the foot on the last key. Goal frame never moves."
        ),
        "part_range": (10, 16),
        "target_frames": 16,
        "gif_ms": 80,
    },
    "cmp_mo_cannon1": {
        "task_id": "path2d_cmp_mo_cannon1",
        "concept": "a cannon firing a shell that trails smoke",
        "prompt": (
            "A shell bursts from the cannon, leaving a trail of smoke as it hurtles through the air."
        ),
        "people_scale": (
            "No people or animals. The cannon spans about 1/4 of the ground-line length, barrel angled up toward +x. "
            "The shell is a small body, clearly smaller than the cannon wheel. "
            "Persistent ids cannon, shell, and smoke exist on every key; inactive parts use one zero-length M."
        ),
        "staging": (
            "Side view. Ground anchored near y=-0.7. Anchored cannon on the LEFT with the barrel angled up to the right. "
            "Use THREE keys. Key A: shell sits at the muzzle, smoke collapsed to a zero-length M mark. "
            "Key B: MUZZLE BLAST — shell has just left the muzzle, a short smoke puff suddenly appears at the muzzle. "
            "Key C: last frame — shell is far +x and higher in the air, with a longer tapering smoke trail behind it "
            "running back toward the muzzle. The cannon stays put and may recoil slightly."
        ),
        "part_range": (8, 14),
        "target_frames": 16,
        "gif_ms": 80,
    },
    "cmp_mo_tank2": {
        "task_id": "path2d_cmp_mo_tank2",
        "concept": "a tank firing a shell at a rectangular target",
        "prompt": (
            "A tank is firing shells towards a distant rectangular target, with a burst of energy smoke."
        ),
        "people_scale": (
            "No people or animals. The tank spans about 1/4 of the ground-line length, barrel pointing +x. "
            "An anchored upright rectangular target at the RIGHT edge, about as tall as the tank. "
            "Persistent ids tank, target, shell, and smoke exist on every key; inactive parts use one zero-length M."
        ),
        "staging": (
            "Side view. Ground anchored near y=-0.7. Anchored tank on the LEFT facing +x; anchored rectangular target at the RIGHT. "
            "Use THREE keys. Key A: tank aims at the target, shell and smoke collapsed to zero-length M marks. "
            "Key B: FIRING — a smoke burst suddenly appears at the muzzle and the shell appears just ahead of it, in the air between tank and target. "
            "Key C: last frame — shell reaches the target face; the muzzle smoke has spread wider and thinner. "
            "Tank and target never translate."
        ),
        "part_range": (8, 14),
        "target_frames": 16,
        "gif_ms": 80,
    },
    "cmp_mo_carside13": {
        "task_id": "path2d_cmp_mo_carside13",
        "concept": "a motorcycle jumping over an oncoming car",
        "prompt": "The motorcycle will jump over the oncoming car.",
        "people_scale": (
            "No people beyond the rider silhouette on the motorcycle. "
            "Car body length about 1/3 of the ground-line length; motorcycle about half the car length. "
            "Persistent ids car and motorcycle exist on every key."
        ),
        "staging": (
            "Side view. Ground anchored near y=-0.7. The motorcycle starts LEFT facing +x; the car starts RIGHT facing −x; they approach each other. "
            "Use THREE keys. Key A: both on the ground, far apart, motorcycle front wheel lifting. "
            "Key B: AIRBORNE — motorcycle is above the car roof, clear of it, both wheels off the ground; the car has moved −x and is under the motorcycle. "
            "Key C: last frame — motorcycle has landed on the ground to the RIGHT of the car and the car has continued −x past it. "
            "They must never overlap. Both vehicles keep their size and travel in opposite directions."
        ),
        "part_range": (10, 18),
        "target_frames": 16,
        "gif_ms": 80,
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
    experience: dict | None = None,
    fix_note: str = "",
) -> str:
    parts = plan.get("parts") or []
    motion_neighborhood = planned_motion_neighborhood(plan, key_i)
    lines = [
        f"2D KEY {key_i}/{n_keys} named '{key.get('name')}' (beat: {key.get('beat', '')}).",
        f"Shot: {plan.get('action') or ''}",
        f"Plan notes: {plan.get('notes') or ''}",
        f"MOTION NEIGHBORHOOD from the existing plan (no extra planner fields): {motion_neighborhood}",
        f"Scale and identity defaults: {people_scale_line(None)}",
        "Draw this ONE pose as a Path2D scene. Same named parts on every key.",
        "Include every listed part using its EXACT id once. "
        "Helpers only '<part_id>_...' for an extra bent segment of that limb/prop — never hair on a stick head.",
        "A character or prop that has not entered yet, or has already vanished, must still keep its exact id as "
        "one zero-length M stroke. Do not omit it. Expand that same id when it appears; collapse it again when absent.",
        "Do not rename ids. No grid cells. Coordinates in [-1,1], +x right, +y up "
        "(larger y is sky; ground is near y=-0.7). Ears and head-top sit above the head center.",
        DRAWER_ORIENTATION,
        "Keep scale and identity fixed against the ground stroke you draw. "
        "This key's pose must match the beat (not a copy of another key). "
        "Animate the whole figure: move the head center and torso with the acting limb. "
        "If this beat is a run or walk, draw a readable stride (front leg vs trailing leg), not a glide.",
        "Motion handoff (hard): infer how this pose is reached and left from the previous/current/next beats above. "
        "The pose must be compatible with both neighbors. A key is a sampled pose, not an automatic pause. "
        "Do not make an unplanned full stop at this key, reset acting limbs, "
        "swap which hand holds a prop, or move a traveler discontinuously.",
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
    if prev_scene and not experience:
        lines.append(
            previous_key_context(prev_scene, prev_name=prev_name or "previous", key_i=key_i)
        )
    if anchor_scene and not experience and key_i > 2:
        lines.append(identity_anchor_context(anchor_scene, anchor_name=anchor_name or "first"))
    if experience:
        rules = list(experience.get("rules") or experience.get("avoid") or [])
        lines.append(
            "\nCAUTION RULES from a visual review. You are not shown any previous drawing or Path2D. "
            "Redraw from scratch using only the system drawing prompt, this pose brief, and these rules:\n"
            + json.dumps(rules, ensure_ascii=False, indent=2)
        )
    note = str(fix_note or "").strip()
    if note:
        lines.append(f"\nREDRAW NOTE (hard): {note}")
    lines.append(
        '\nReturn JSON only: {"prompt":"...","strokes":[{"id":"...","path":"M ...","description":"...","group":"..."}]}.'
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


def scene_brief(scene: dict) -> str:
    strokes = [
        {"id": item.get("id"), "path": item.get("path"), "description": item.get("description")}
        for item in scene.get("strokes") or []
    ]
    return json.dumps({"strokes": strokes}, ensure_ascii=False)


def inbetween_oneshot_prompt(
    plan: dict, slot: dict, from_scene: dict, to_scene: dict, *, fix_note: str = ""
) -> str:
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
    note = str(fix_note or "").strip()
    note_block = f"REDRAW NOTE (hard): {note}\n\n" if note else ""
    return f"""2D INBETWEEN: draw frame {cur} ({span}).
FROM is the already-drawn previous frame {from_i}. TO is the next key, which is frame {to_i}.
Ease={slot.get('ease')}. Progress in this gap t={t:.3f} (0 is just after FROM's key, 1 would be TO).
This frame is still BEFORE the TO key.

Shot: {plan.get('action') or ''}
Plan notes: {plan.get('notes') or ''}
Scale and identity defaults: {people_scale_line(None)}
{story}

{INBETWEEN_REASONING}

Parts (exact ids required):
{part_lines}

Identity (hard):
- Include every plan part id exactly once.
- Helpers only: '<part_id>_...' for an extra bent segment of that SAME limb or prop. Never hair, ponytail, or face ticks on a stick head.
- Do not rename. Changing pose keeps the same ids.
- Head SIZE and build stay unchanging, but the head CENTER and torso must keep moving with the pose — do not freeze them and only move one limb.
- Anchored scenery stays put.
- Attached strokes share the current joint (x,y). A planted foot stays on the ground but is not frozen in world space.
- No grid cells. Coordinates in [-1,1], +x right, +y up (larger y is sky).
- {DRAWER_ORIENTATION}

{note_block}FROM frame {from_i}:
{scene_brief(from_scene)}

TO key (frame {to_i}):
{scene_brief(to_scene)}

Return JSON only: {{"prompt":"...","strokes":[{{"id":"...","path":"M ...","description":"...","group":"..."}}]}}.
Reuse exact ids from FROM. Path commands only (M/L/Q/C/Z).
"""
