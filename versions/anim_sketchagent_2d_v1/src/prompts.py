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
    "Heads MUST be round Q loops (four or more Q segments, then Z). "
    "Example: M cx cy+r Q cx+r cy+r cx+r cy Q cx+r cy-r cx cy-r Q cx-r cy-r cx-r cy Q cx-r cy+r cx cy+r Z. "
    "Do not draw heads as polygons of L (no hexagon, octagon, or diamond), teardrops, or long ovals. "
    "The neck attaches at the BOTTOM of the head circle (the lowest y on the Q loop), never at the head center. "
    "Do not run the torso or arms through the middle of the head. "
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
    "Scale (hard): obey the plan's people_scale. Standing height is a fraction of the GROUND STROKE LENGTH drawn on THIS frame, "
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
    "Open centerlines: torso, limbs, tails, and props are open strokes — never Z. "
    "Z is only for heads and other round loops. "
    "Do not outline a filled silhouette or double-stroke a limb. "
    "Whole-body motion: head, torso/spine, hips, and both arms change pose between keys. "
    "Do not freeze the trunk and only swing one limb or one prop. "
    "Head keeps a constant SIZE but its center travels with the neck (lean, crouch, look). "
    "Identity (hard): keep the SAME height, limb length, and stocky-vs-slim build as people_scale and the previous pose. "
    "Do not grow, shrink, or fatten a character between keys or inbetweens. "
    "Torso tilts with the beat: coil away on the wind-up, lean into contact, continue through follow-through. "
    "Only anchored scenery stays still."
)
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
    "Keep the same character height and build as FROM; only the pose advances. "
    "Honor the planned duration of this gap: a short snap should already be close to TO, "
    "a long interval should still look early if t is small — do not jump to the next key in one frame. "
    "Do not copy FROM or TO."
)


def people_scale_line(plan_or_task: dict | None = None) -> str:
    text = str((plan_or_task or {}).get("people_scale") or "").strip()
    if len(text) < 80:
        return DEFAULT_PEOPLE_SCALE + " Plan people_scale: " + text
    return text


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
        "Keep the same stroke ids, head SIZE, and character build. "
        "Redraw the WHOLE pose for THIS beat — head center, torso tilt, hips, and arms must move, not only the acting limb. "
        "Do not copy previous-key coordinates for head or torso.\n"
        f"{brief}"
    )


KEY_PLAN_SYSTEM = """You are a sketch planner for pose-to-pose 2D stick-figure animation.
Return JSON only. No markdown.

The drawer draws ONLY keys as Path2D (M/L/Q/C/Z, [-1,1], +x right +y up).
Inbetweens are a later one-shot redraw of the SAME named parts — the key drawer will not see them.
2–6 keys. Add a key only for contact, detach, or a new silhouette. No grid cells like x12y20.
Keys are pose notes only (name, beat, notes). Do not emit Path2D, path strings, or coordinates on keys — the drawer decides geometry.

The first key is frame 1 of the clip. The last key is the last frame. The last key must show the finished action, not a mid-travel pose.

"action" is a DIRECTOR rewrite, not a paraphrase. Restage so a viewer can read the story at a glance, while keeping the user's intent. Spread the cast across the stage when the story needs distance; give traveling things enough empty space to read; say how distinctive props should be recognized as objects rather than extra limbs. Put that staging into layout_notes.

"action" still covers: who, left/right, beat order, what travels, what stays put (head SIZE, body BUILD, scenery).
Identity (hard): each character's height, stocky-vs-slim build, limb length, and head size are UNCHANGING across keys. Pose and placement change; the body recipe does not. Write that unchanging build into people_scale. Do not grow, shrink, or fatten anyone between keys.

Timing (hard): gaps[].n_inbetween is how much TIME sits between those two keys, not padding. A fast hit or snap uses few inbetweens (1–3). A long travel, hang-time, or slow settle uses more. Do not give every gap the same count unless the beats really last the same. gaps[].why must say what that interval is (quick / medium / long) and why this many frames. gaps[].ease matches the beat: linear for steady travel, ease_out for arriving/settling, smooth for an arc.

Each key must be a different WHOLE-BODY pose: head center, torso tilt, hips, arms, and acting limb all change. Do not freeze the trunk and only swing one limb.
Each key.notes is brief but must include (1) head and torso for that beat and (2) ORIENTATION of the main parts: which way the head looks, which way the torso leans, which way a held tool or acting limb aims (+x/−x, up/down). No coordinates.
Each parts[].notes: one short facing/pointing clause (e.g. "looks +x", "leans toward the traveling object"). Do not write path strings.

Write into the plan:
- people_scale: standing height 1/5–1/4 of GROUND LINE LENGTH (not canvas height); hip halfway head-top to feet; heads are circles of unchanging size; neck meets the bottom of the head, not the center; torso is a curve; attached parts share joint coordinates; swinging parts may use Q/C, straight scenery/props use L. Write this as a full sentence. Do not copy a short schema stub.
- layout_notes: placement and where traveling props go. Ground near y=-0.7.

Parts: motion "moving" or "anchored". Same parts[].id on every key.
Parts are drawable strokes only (head, torso, limbs, props, scenery). Do not add joint-only parts such as neck, hip, shoulder, elbow, or knee as their own ids — those are shared endpoints on torso/limbs.
"anchored" is scenery only. Never mark a limb, torso, head, tail, or held prop as anchored.
A planted foot or hanging support end may stay put in the world, but the attachment end still follows its parent joint.
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
    fewshot: bool = True,
) -> str:
    n_min, n_max = task.get("part_range", (MIN_PARTS, MAX_PARTS))
    suggested_frames = int(suggested_frames or task.get("target_frames") or 12)
    pin_frames = int(pin_frames) if pin_frames else None
    lo, hi = key_count_bounds(pin_frames)
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
        scale_block = f"\npeople_scale (copy into the JSON field):\n{people_scale_line(task)}\n"
        schema = f"""Return JSON:
{{
  "concept": "{task['concept']}",
  "action": "director rewrite: readable staging; beats; facing; what travels",
  "people_scale": "1/5–1/4 of ground-line length; hip halfway",
  "layout_notes": "placement; travel path; +x right +y up",
  "parts": [{{"id": "person_head", "name": "person_head", "how": "circle", "motion": "moving", "notes": "same size; looks +x"}}],
  "keys": [{{"name": "start", "beat": "short beat", "notes": "this pose; head/torso facing and lean"}}],
  "gaps": [{{"after": "start", "n_inbetween": 3, "ease": "linear|smooth|ease_out", "why": "how long this interval is and why this many frames"}}]
}}"""
    else:
        staging_block = ""
        scale_block = ""
        schema = """Return one JSON object with fields:
concept, action, people_scale, layout_notes,
parts (each: id, name, how, motion, notes),
keys (each: name, beat, notes),
gaps (each: after, n_inbetween, ease, why).
No example strokes, no sample poses."""
    return f"""User request: {task['prompt']}
{staging_block}{scale_block}
{pick}

{schema}

Hard rules:
- parts {n_min}–{n_max}, same ids on every key.
- Fill people_scale (full unchanging-build sentence) and layout_notes.
- First key = frame 1. Last key = last frame; that pose is the completed action.
{key_rule}{frame_rule}- Include a hit/release/detach key if the action has one.
- Each gap n_inbetween is timing: more frames = more time. why must justify that duration.
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
            "Dog about 1/5–1/4 of the ground-line length. Ellipse body, circle head above the front of the body. "
            "Short tick legs. Ball-sized snout/ear, not a stick person."
        ),
        "staging": (
            "Side view facing right. Ground line anchored near y=-0.7. One dog, no person, no ball. "
            "Ellipse body, circle head overlapping the upper-front, floppy ear, four short legs, tail up. "
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
            "Cat about 1/5–1/4 of the ground-line length. Ellipse body, circle head above the front (+x) of the body. "
            "Two pointed ears on the CROWN (higher y than the head center). Short tick legs, long tail curving up. "
            "Not a stick person."
        ),
        "staging": (
            "Side view facing right (+x). Ground line anchored near y=-0.7. "
            "A simple table on the RIGHT is anchored: four short legs and a flat top at about mid-height. "
            "One cat, no person. Ellipse body. Circle head overlaps the UPPER-FRONT of the body. "
            "Two pointed triangle ears sit on the crown (apex y greater than head-center y). "
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
            "Cat about 1/5–1/4 of the ground-line length. Ellipse body, circle head above the front (+x) of the body. "
            "Two pointed ears on the CROWN (higher y than the head center). Short tick legs, long tail curving up. "
            "Not a stick person. The lure is smaller than the cat's head."
        ),
        "staging": (
            "Side view facing right (+x). Ground line anchored near y=-0.7. "
            "One small cat on the LEFT–CENTER of the ground. No second animal. "
            "A teaser wand is THREE parts: a straight L handle from the UPPER RIGHT (held off the top-right, "
            "not a second person), a hanging string from the handle tip, and a tiny lure at the string's lower end. "
            "Handle is anchored. String and lure move. "
            "Ellipse body. Circle head overlaps the UPPER-FRONT of the body. "
            "Two pointed ears on the crown (apex y greater than head-center y). Tail from the rear (−x), curving up. "
            "Key A: cat crouched on the ground, hips low, looking +x at the lure; lure hangs in front of the cat, not touching. "
            "Key B: CONTACT — a front paw meets the lure; body stretches toward +x/up; lure still on the string. "
            "Key C: last frame — lure yanked up-right away from the paw; cat in a follow-through stretch or sit-back, "
            "still looking at the lure. Head stays above the body. Ears stay on the crown. Same cat size every key."
        ),
        "part_range": (10, 18),
        "target_frames": 12,
        "gif_ms": 80,
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
            "Cat about 1/5–1/4 of the ground-line length. Ellipse body, circle head above the front (+x) of the body. "
            "Two pointed ears on the CROWN (higher y than the head center). Short tick legs, long tail curving up. "
            "Not a stick person."
        ),
        "staging": (
            "Side view facing right (+x). Ground line anchored near y=-0.7. One cat, no person, no mouse. "
            "Ellipse body. Circle head overlaps the UPPER-FRONT of the body (right side, above the torso). "
            "Two pointed triangle ears sit on the crown of the head: apex y is GREATER than the head-center y "
            "(+y is up/sky; do not hang ears toward the ground or under the chin). "
            "Whiskers stick out from the +x muzzle. Tail from the rear (−x), curving up. Four short legs. "
            "Key A: LEFT third, contact stride (one front leg forward, opposite hind forward). "
            "Key B: CENTER, passing stride, legs gathered under the body. "
            "Key C: last frame — RIGHT-CENTER, opposite contact, leave empty space at the right edge. "
            "Head stays above the body. Face looks +x. Body and head translate right together and keep the same size."
        ),
        "part_range": (8, 16),
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
            "Rabbit about 1/5–1/4 of the ground-line length. Round ellipse body, smaller circle head at the +x front. "
            "Two long ears pointing UP (higher y than the head). Cottontail at −x. No stick-person legs."
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
}


def key_draw_prompt(
    plan: dict,
    key: dict,
    key_i: int,
    n_keys: int,
    *,
    prev_scene: dict | None = None,
    prev_name: str = "",
    experience: dict | None = None,
    fix_note: str = "",
) -> str:
    parts = plan.get("parts") or []
    lines = [
        f"2D KEY {key_i}/{n_keys} named '{key.get('name')}' (beat: {key.get('beat', '')}).",
        f"Shot: {plan.get('action') or ''}",
        f"Staging: {plan.get('layout_notes') or ''}",
        f"Scale (hard, from plan people_scale): {people_scale_line(plan)}",
        "Draw this ONE pose as a Path2D scene. Same named parts on every key.",
        "Include every listed part using its EXACT id once. Helpers only '<part_id>_...'.",
        "Do not rename ids. No grid cells. Coordinates in [-1,1], +x right, +y up "
        "(larger y is sky; ground is near y=-0.7). Ears and head-top sit above the head center.",
        DRAWER_ORIENTATION,
        "Keep the planned people_scale against the ground stroke you draw. "
        "This key's pose must match the beat (not a copy of another key). "
        "Animate the whole figure: move the head center and torso with the acting limb.",
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
Staging: {plan.get('layout_notes') or ''}
Scale (hard, from plan people_scale): {people_scale_line(plan)}
{story}

{INBETWEEN_REASONING}

Parts (exact ids required):
{part_lines}

Identity (hard):
- Include every plan part id exactly once. Helpers only: '<part_id>_...'.
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
