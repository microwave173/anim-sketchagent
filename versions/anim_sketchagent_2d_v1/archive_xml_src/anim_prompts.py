"""Plan → Draw prompts for short SketchAgent stick-figure clips."""
from __future__ import annotations

from drawer_prompts import CIRCLE, ELLIPSE, HOUSE, xml_tail

MAX_FRAMES = 20
MIN_FRAMES = 4
MIN_PARTS = 5
MAX_PARTS = 16
MIN_KEYS = 2
MAX_KEYS = 6


def key_count_bounds(pin_frames: int | None = None) -> tuple[int, int]:
    """How many keys fit when each gap is 1–10 inbetweens. pin_frames locks the clip length."""
    lo, hi = MIN_KEYS, MAX_KEYS
    budget = int(pin_frames) if pin_frames else MAX_FRAMES
    hi = min(hi, (budget + 1) // 2)
    if pin_frames:
        lo = max(lo, (int(pin_frames) + 20) // 11)
    if lo > hi:
        lo = hi
    return lo, hi


ANIMAL_STYLE_LAWS = """Mammal sketch style (dog / rabbit / cat / mouse, and similar mammals):
- Two primitives only for the mass: BODY is a closed ELLIPSE (one closed stroke, 8–12 points, like a stretched circle — do not split into two arcs that leave a seam at the sides). HEAD is a CIRCLE overlapping the upper-front of the body (right if facing right). Do not fuse them into a bean. Do not use a stick-person torso line.
- Side profile, even stroke weight. Pretty is optional; species must still be readable.
- After head+body, add only SPECIES SIGNATURES (the few marks that name the animal):
  dog: floppy ear set back on the head; a sideways U mouth on the right of the head (NO nose); four SHORT vertical tick-legs that TOUCH the belly; a tail that cocks upward. Head circle sits ABOVE the body oval, overlapping only the upper-front.
  rabbit: rounder / more circular body ellipse; smaller head circle on the upper-front; two long upright ears; a small round cottontail; one short vertical-line eye; OMIT legs.
  cat: pointed triangle ears + a tiny smile + 2–3 whiskers per side; four SHORT tick-legs; a long tail that curves up.
  mouse: small round ears + a tiny nose + whiskers; four SHORT tick-legs; a long thin tail.
- Other mammals: same recipe — ellipse body, circle head, then only the 2–4 marks that name the species.
- Round / plump animals (rabbit-like, sitting bun, etc.): OMIT legs entirely. Standing or walking animals: 2–4 SHORT thin vertical ticks under the body — not long stick-person limbs, not four tall posts.
- Eye: one short vertical line. No circular pupils, no clothes, no second outline.
- SCALE: keep the animal SMALL on the 50x50 grid so it can travel. Body ellipse about 10–14 cells wide (never 20+). Head circle about 6–8 cells across. The whole silhouette occupies at most about one-third of the canvas width. Sit it in the LEFT third for a still or a start pose, feet near the bottom third, and leave the travel side empty. Hitting the right or top border is a failure. For a hop, chase, or any beat that needs visual impact, go even smaller so the path is long."""

DOG_EXAMPLE = """<example>
<concept>Dog</concept>
<strokes>
    <s1>
        <points>'x9y35', 'x13y34', 'x18y34', 'x21y37', 'x19y42', 'x15y43', 'x10y42', 'x8y39', 'x9y35'</points>
        <t_values>0.00,0.125,0.25,0.375,0.50,0.625,0.75,0.875,1.00</t_values>
        <id>body</id>
    </s1>
    <s2>
        <points>'x19y29', 'x22y31', 'x23y34', 'x22y36', 'x19y37', 'x17y35', 'x16y33', 'x17y30', 'x19y29'</points>
        <t_values>0.00,0.125,0.25,0.375,0.50,0.625,0.75,0.875,1.00</t_values>
        <id>head</id>
    </s2>
    <s3>
        <points>'x17y31', 'x15y28', 'x18y27', 'x20y29', 'x19y32'</points>
        <t_values>0.00,0.25,0.50,0.75,1.00</t_values>
        <id>floppy ear</id>
    </s3>
    <s4>
        <points>'x20y32', 'x20y34'</points>
        <t_values>0.00,1.00</t_values>
        <id>eye</id>
    </s4>
    <s5>
        <points>'x22y34', 'x24y34', 'x25y35', 'x24y36', 'x22y35'</points>
        <t_values>0.00,0.25,0.50,0.75,1.00</t_values>
        <id>mouth</id>
    </s5>
    <s6>
        <points>'x19y42', 'x19y46'</points>
        <t_values>0.00,1.00</t_values>
        <id>front leg</id>
    </s6>
    <s7>
        <points>'x17y42', 'x17y46'</points>
        <t_values>0.00,1.00</t_values>
        <id>front leg 2</id>
    </s7>
    <s8>
        <points>'x12y42', 'x12y46'</points>
        <t_values>0.00,1.00</t_values>
        <id>hind leg</id>
    </s8>
    <s9>
        <points>'x10y41', 'x10y45'</points>
        <t_values>0.00,1.00</t_values>
        <id>hind leg 2</id>
    </s9>
    <s10>
        <points>'x8y38', 'x7y35', 'x8y32'</points>
        <t_values>0.00,0.50,1.00</t_values>
        <id>tail</id>
    </s10>
</strokes>
</example>"""

RABBIT_EXAMPLE = """<example>
<concept>Rabbit</concept>
<strokes>
    <s1>
        <points>'x9y39', 'x10y36', 'x14y35', 'x17y36', 'x18y39'</points>
        <t_values>0.00,0.25,0.50,0.75,1.00</t_values>
        <id>body top arc</id>
    </s1>
    <s2>
        <points>'x18y39', 'x17y42', 'x14y44', 'x10y42', 'x9y39'</points>
        <t_values>0.00,0.25,0.50,0.75,1.00</t_values>
        <id>body bottom arc</id>
    </s2>
    <s3>
        <points>'x17y32', 'x19y32', 'x20y34', 'x19y36', 'x17y37', 'x15y36', 'x15y34', 'x15y32', 'x17y32'</points>
        <t_values>0.00,0.125,0.25,0.375,0.50,0.625,0.75,0.875,1.00</t_values>
        <id>head</id>
    </s3>
    <s4>
        <points>'x16y32', 'x16y29', 'x16y27', 'x17y29', 'x16y32'</points>
        <t_values>0.00,0.25,0.50,0.75,1.00</t_values>
        <id>ear</id>
    </s4>
    <s5>
        <points>'x18y32', 'x18y29', 'x18y26', 'x19y29', 'x18y32'</points>
        <t_values>0.00,0.25,0.50,0.75,1.00</t_values>
        <id>ear 2</id>
    </s5>
    <s6>
        <points>'x17y33', 'x17y35'</points>
        <t_values>0.00,1.00</t_values>
        <id>eye</id>
    </s6>
    <s7>
        <points>'x10y40', 'x11y40', 'x11y41', 'x11y42', 'x10y43', 'x9y42', 'x8y41', 'x9y40', 'x10y40'</points>
        <t_values>0.00,0.125,0.25,0.375,0.50,0.625,0.75,0.875,1.00</t_values>
        <id>cottontail</id>
    </s7>
</strokes>
</example>"""

ANIM_LAWS = """Shared animation laws:
- Identity: the same named parts on every key. Interpolation matches by <id>; dropping a part makes it vanish.
- Two subjects (people or animals): unique name prefixes. Never merge two bodies into one stick.
- Moving parts (heads, torsos, limbs, hands, sword, racket, shuttle, anything that acts) MUST change cells when the beat changes. Copying the previous key's head, torso, or sword is a mistake. A lunge moves the head with the body.
- Anchored parts (ground, floor, horizon, court, wall, scenery) MUST reuse the exact same points and t_values on every key. Do not slide, tilt, lengthen, shorten, or drop them. Prefer one shared ground line, not a ground per person.
- Keep proportions: same head size and similar limb lengths; change pose and placement.
- Topology changes (contact, detach, a part leaving a parent) are keys. Interpolation cannot invent them.
- Timing: the same action should read at a similar speed in every stage. A swing-in and its follow-through, or a toss and a hit, must not whip then crawl. Give more inbetweens to the longer travel, fewer to the short settle, and use the same ease on both halves of one action.
- SCALE (real-world-ish; people first, props follow):
  Sport / rally / shot: a person is 1/4–1/3 of the canvas tall — readable, not ants. Two people leave a middle lane for the ball. A net is one vertical line up to chest or head. A hoop rim sits above head height on a pole. Ball smaller than the head; racket about a forearm.
  Acting in place (sit, pick up, kick): 1/3–1/2 tall is fine.
  Crossing the page (walk, chase, hop): about 1/4 tall, start with the travel side empty.
  Never fill the canvas with one body. Never go below ~1/5 or the figure vanishes.
- People: sparse stick figures. No clothes, no circular pupils, no blood, no extra clutter.
- HEADS: every person head is a closed CIRCLE — 8 compass points plus the start cell, width ≈ height. Never a wide bean, heart, or sausage oval.
- A gun/blaster is a readable prop: a short body (small rectangle or L) plus a barrel sticking out. Never one dash collinear with the arm.
- If a metal sword is present: short grip in the fist, short guard perpendicular to the blade, longer blade — a readable T hilt, not two collinear sticks. A beam/saber blade is a short grip plus a long blade only (no crossguard).
- Animals follow ANIMAL STYLE (ellipse body + circle head, signatures only; plump animals skip legs). Do not collapse them into stick people.

""" + ANIMAL_STYLE_LAWS

ANIM_PLAN_SYSTEM = f"""You are a sketch planner for a SHORT black-line animation.
Return JSON only. No markdown.

A separate drawer will draw each frame as a sparse SketchAgent stick figure.
You give STRUCTURE and POSE, not a tracing template.
Never output grid cells like x12y20, never list numeric coordinates, never give pixel positions.
Describe regions in words: left / center / right, top / middle / bottom, and rough fractions of the canvas.

Unless the task has two subjects, draw one subject only.
Joints may be slightly loose; do not CAD-snap.

{ANIM_LAWS}"""


ANIM_PLAN_SYSTEM_ANIMAL = f"""You are a sketch planner for a SHORT black-line mammal animation.
Return JSON only. No markdown.

A separate drawer will draw each frame as an ellipse-body + circle-head mammal sketch, not a stick person.
You give STRUCTURE and POSE, not a tracing template.
Never output grid cells like x12y20, never list numeric coordinates, never give pixel positions.
Describe regions in words: left / center / right, top / middle / bottom, and rough fractions of the canvas.

Plan BODY as an ellipse and HEAD as a circle overlapping the upper-front of the body. Species signatures (ears, tail, snout, whiskers) are extra parts. Plump animals may have no leg parts.

Unless the task has two subjects, draw one subject only.

{ANIM_LAWS}"""


def anim_plan_user(task: dict, n_frames: int) -> str:
    concept = task["concept"]
    prompt = task["prompt"]
    rules = task.get("motion_rules", "")
    schema = task.get("frame_schema", "")
    n_min, n_max = task.get("part_range", (MIN_PARTS, MAX_PARTS))
    return f"""Plan a {n_frames}-frame sparse stick-figure animation (at most {MAX_FRAMES} frames).

concept: {concept}
prompt: {prompt}

Motion that must be readable:
{rules}

Return JSON:
{{
  "concept": "{concept}",
  "n_frames": {n_frames},
  "viewpoint": "{task.get('viewpoint', 'side view facing right')}",
  "layout_notes": "where the action happens, words and fractions only",
  "parts": [
    {{
      "id": "s1",
      "name": "head",
      "how": "circle|line|curve|zigzag",
      "motion": "moving|anchored",
      "notes": "same size every frame; anchored = ground/scenery"
    }}
  ],
  "frames": [
    {{
      "i": 1,
      {schema}
    }}
  ]
}}

Hard rules:
- Do NOT write cells (xNyM), numbers as coordinates, or t_values.
- n_frames must be {n_frames}. frames length must match.
- parts count {n_min}–{n_max}. Reuse the same part ids in every frame, even if a prop later flies.
- Consecutive frames must change the action, not redraw the same pose.
- Order parts as a sensible draw order."""


def anim_plan_text(plan: dict, frame_i: int) -> str:
    parts = plan.get("parts") or plan.get("strokes") or []
    frames = plan.get("frames") or []
    fr = next((f for f in frames if int(f.get("i", -1)) == frame_i), None)
    if fr is None and 1 <= frame_i <= len(frames):
        fr = frames[frame_i - 1]
    fr = fr or {}
    lines = [
        f"Concept: {plan.get('concept', '')}",
        f"Viewpoint: {plan.get('viewpoint', '')}",
        f"Action path: {plan.get('layout_notes', '')}",
        f"Frame {frame_i} of {plan.get('n_frames', len(frames))}.",
        "Same stick person every frame. Choose your own 1–50 cells; do not copy a tracing template.",
        "",
        "Parts (keep these identities):",
    ]
    for s in parts:
        notes = (s.get("notes") or "").strip()
        extra = f" {notes}" if notes else ""
        lines.append(f"{s.get('id')} {s.get('name')} ({s.get('how')}).{extra}")
    lines += ["", "This frame pose (words only):"]
    for k, v in fr.items():
        if k == "i":
            continue
        lines.append(f"{k}: {v}")
    return "\n".join(lines)


ANIM_DRAW_SYSTEM = f"""You are an expert artist drawing sparse black-line stick figures on a 50x50 grid.
Origin top-left: x right, y down. Cells are 'x1y1' ... 'x50y50'. Never use Cartesian bottom-left coordinates.
Output SketchAgent XML only. No markdown fences, no <thinking> tags.

This is one frame / key of an animation.
Keep the stroke count in the planner's part list. Abstract stick person: CIRCLE head (equal width and height), torso line, limb lines.
SIZE: copy the 8-point circle recipe only — never the example's diameter. Scale the whole figure down uniformly (head, body, limbs together) so it matches SCALE: sport people about 1/4–1/3 of the canvas tall; in-place acting may be larger; a walk/chase about 1/4 with empty travel space.
Props are simple: a racket is a shaft line plus a small oval/loop head; a shuttle is a tiny diamond or two short crossing lines; a blaster is a small body plus a barrel (not one dash); a saber is a short grip plus a long blade.
Circles close by repeating the start cell. Each <points> length must equal <t_values>. t starts at 0.00 and ends at 1.00.

Head circle recipe (shape only; pick a smaller center and scale down):
{CIRCLE}

Unless the task has two characters, draw one subject only.

If previous XML is given:
- Copy ANCHORED strokes (ground, floor, horizon, court, wall) verbatim — same points, same t_values.
- Redraw MOVING strokes in the new pose. Do not freeze a head, torso, limb, or sword on the previous cells.
- Match circle size and limb length, not the previous pose.

{ANIM_LAWS}"""


ANIM_DRAW_SYSTEM_ANIMAL = f"""You are an expert artist drawing sparse black-line mammal sketches on a 50x50 grid.
Origin top-left: x right, y down. Cells are 'x1y1' ... 'x50y50'. Never use Cartesian bottom-left coordinates.
Output SketchAgent XML only. No markdown fences, no <thinking> tags.

This is one KEY of an animation. Follow mammal style: ELLIPSE body + CIRCLE head overlapping the upper-front, then only signature features. Not a stick person (no torso line).
If a character sheet is given, IGNORE the composition-example cells and unprefixed ids below. Copy the sheet's exact <id> names, stroke counts, and SIZE; only retarget points for this key's pose. Do not enlarge the sheet. Start on the left third; later keys translate into empty space. No cell may use x<3 or x>48.

Head circle: 8 compass points + start cell, even t. Body ellipse: one closed stroke (8–12 points), close by repeating the start cell. Each <points> length must equal <t_values>. t starts at 0.00 and ends at 1.00.

Format examples (copy the geometry, pick your own cells):
{CIRCLE}

{ELLIPSE}

Mammal composition examples (copy the geometry, pick your own cells; one animal only):
{DOG_EXAMPLE}

{RABBIT_EXAMPLE}

If previous XML is given:
- Copy ANCHORED strokes (ground, floor, branch, fence, water) verbatim.
- Redraw MOVING animal parts in the new pose; do not freeze the sheet's rest pose.

{ANIM_LAWS}"""


ANIMAL_PLAN_SYSTEM = f"""You are a sketch planner for sparse black-line mammal drawings.
Return JSON only. No markdown.

The drawer is a separate model. You give STRUCTURE, not a tracing template.
Never output grid cells like x12y20, never list numeric coordinates, never give pixel positions.
Describe regions in words: top / middle / bottom, left / center / right, and rough fractions of the canvas.

Keep 4–10 strokes. Cute-simple is enough; do not add detail for beauty.
Plan BODY as an ellipse and HEAD as a circle overlapping the upper-front of the body. Then only signature extras (ears, tail, snout, whiskers, optional short leg ticks). Do not plan a fused bean.

{ANIMAL_STYLE_LAWS}"""


ANIMAL_STILL_DRAW_SYSTEM = f"""You are an expert artist drawing sparse black-line mammal sketches on a 50x50 grid.
Origin top-left: x right, y down. Cells are 'x1y1' ... 'x50y50'. Never use Cartesian bottom-left coordinates.
Output SketchAgent XML only. No markdown fences, no <thinking> tags.
Pretty is optional. Readability of the species is enough.

BODY is one closed ellipse (8–12 points). HEAD is a circle overlapping the upper-front of the body. Close by repeating the start cell.
Then add only the signature strokes. Short vertical ticks for legs must TOUCH the belly, unless the animal is plump enough to skip legs.
Each <points> length must equal <t_values>. t starts at 0.00 and ends at 1.00.

Format examples (copy the geometry, pick your own cells):
{CIRCLE}

{ELLIPSE}

Mammal composition examples (copy the geometry, pick your own cells; one animal only):
{DOG_EXAMPLE}

{RABBIT_EXAMPLE}

{ANIMAL_STYLE_LAWS}"""


def animal_still_user_prompt(task: dict, plan: str) -> str:
    reqs = "; ".join(r["description"] for r in task.get("requirements") or [])
    return f"""Draw a sparse black-line mammal: {task['concept']}
{task['prompt']}
Must communicate: {reqs}

Planner layout (coarse regions only; choose your own cells; do not copy a tracing template):
{plan}

Copy the mammal composition geometry from the system examples, but keep the animal SMALL (body ~12 cells wide, left third of the canvas). One animal only. No house.

{xml_tail(task['concept'])}"""


_MAMMAL_WORDS = (
    "dog",
    "cat",
    "rabbit",
    "mouse",
    "horse",
    "fox",
    "bear",
    "pig",
    "cow",
    "mammal",
)


def is_animal_task(task: dict) -> bool:
    if task.get("kind") == "animal" or task.get("bucket") == "animal":
        return True
    blob = f"{task.get('concept', '')} {task.get('prompt', '')}".lower()
    return any(w in blob for w in _MAMMAL_WORDS)


STICK_EXAMPLE = """<example>
<concept>Stick person</concept>
<strokes>
    <s1>
        <points>'x18y16', 'x22y17', 'x23y21', 'x22y25', 'x18y26', 'x14y25', 'x13y21', 'x14y17', 'x18y16'</points>
        <t_values>0.00,0.125,0.25,0.375,0.50,0.625,0.75,0.875,1.00</t_values>
        <id>head</id>
    </s1>
    <s2>
        <points>'x18y26', 'x18y36'</points>
        <t_values>0.00,1.00</t_values>
        <id>torso</id>
    </s2>
    <s3>
        <points>'x18y30', 'x12y34'</points>
        <t_values>0.00,1.00</t_values>
        <id>left arm</id>
    </s3>
    <s4>
        <points>'x18y30', 'x24y34'</points>
        <t_values>0.00,1.00</t_values>
        <id>right arm</id>
    </s4>
    <s5>
        <points>'x18y36', 'x12y46'</points>
        <t_values>0.00,1.00</t_values>
        <id>left leg</id>
    </s5>
    <s6>
        <points>'x18y36', 'x24y46'</points>
        <t_values>0.00,1.00</t_values>
        <id>right leg</id>
    </s6>
</strokes>
</example>"""

RACKET_EXAMPLE = """<example>
<concept>Racket and shuttle</concept>
<strokes>
    <s7>
        <points>'x28y32', 'x34y26'</points>
        <t_values>0.00,1.00</t_values>
        <id>racket shaft</id>
    </s7>
    <s8>
        <points>'x34y24', 'x37y25', 'x38y28', 'x37y31', 'x34y32', 'x31y31', 'x30y28', 'x31y25', 'x34y24'</points>
        <t_values>0.00,0.125,0.25,0.375,0.50,0.625,0.75,0.875,1.00</t_values>
        <id>racket head</id>
    </s8>
    <s9>
        <points>'x36y22', 'x38y20', 'x36y18', 'x34y20', 'x36y22'</points>
        <t_values>0.00,0.25,0.50,0.75,1.00</t_values>
        <id>shuttle</id>
    </s9>
</strokes>
</example>"""


BLASTER_EXAMPLE = """<example>
<concept>Blaster</concept>
<strokes>
    <s1>
        <points>'x18y30', 'x18y33', 'x23y33', 'x23y31', 'x28y31'</points>
        <t_values>0.00,0.25,0.50,0.75,1.00</t_values>
        <id>blaster</id>
    </s1>
</strokes>
</example>"""


FIGHT_EXAMPLE = """<example>
<concept>Two stick people</concept>
<strokes>
    <s1>
        <points>'x12y16', 'x15y17', 'x16y20', 'x15y23', 'x12y24', 'x9y23', 'x8y20', 'x9y17', 'x12y16'</points>
        <t_values>0.00,0.125,0.25,0.375,0.50,0.625,0.75,0.875,1.00</t_values>
        <id>attacker_head</id>
    </s1>
    <s2>
        <points>'x12y24', 'x12y34'</points>
        <t_values>0.00,1.00</t_values>
        <id>attacker_torso</id>
    </s2>
    <s3>
        <points>'x12y28', 'x18y30'</points>
        <t_values>0.00,1.00</t_values>
        <id>attacker_sword_arm</id>
    </s3>
    <s4>
        <points>'x16y31', 'x20y29'</points>
        <t_values>0.00,1.00</t_values>
        <id>sword_grip</id>
    </s4>
    <s5>
        <points>'x19y26', 'x21y32'</points>
        <t_values>0.00,1.00</t_values>
        <id>sword_guard</id>
    </s5>
    <s6>
        <points>'x20y29', 'x30y26'</points>
        <t_values>0.00,1.00</t_values>
        <id>sword_blade</id>
    </s6>
    <s7>
        <points>'x34y16', 'x37y17', 'x38y20', 'x37y23', 'x34y24', 'x31y23', 'x30y20', 'x31y17', 'x34y16'</points>
        <t_values>0.00,0.125,0.25,0.375,0.50,0.625,0.75,0.875,1.00</t_values>
        <id>victim_head</id>
    </s7>
    <s8>
        <points>'x34y24', 'x34y34'</points>
        <t_values>0.00,1.00</t_values>
        <id>victim_torso</id>
    </s8>
    <s9>
        <points>'x4y42', 'x46y42'</points>
        <t_values>0.00,1.00</t_values>
        <id>ground</id>
    </s9>
</strokes>
</example>"""


TWO_PERSON_EXAMPLE = """<example>
<concept>Two stick friends</concept>
<strokes>
    <s1>
        <points>'x12y16', 'x15y17', 'x16y20', 'x15y23', 'x12y24', 'x9y23', 'x8y20', 'x9y17', 'x12y16'</points>
        <t_values>0.00,0.125,0.25,0.375,0.50,0.625,0.75,0.875,1.00</t_values>
        <id>left_head</id>
    </s1>
    <s2>
        <points>'x12y24', 'x12y34'</points>
        <t_values>0.00,1.00</t_values>
        <id>left_torso</id>
    </s2>
    <s3>
        <points>'x12y28', 'x18y24'</points>
        <t_values>0.00,1.00</t_values>
        <id>left_arm</id>
    </s3>
    <s4>
        <points>'x34y16', 'x37y17', 'x38y20', 'x37y23', 'x34y24', 'x31y23', 'x30y20', 'x31y17', 'x34y16'</points>
        <t_values>0.00,0.125,0.25,0.375,0.50,0.625,0.75,0.875,1.00</t_values>
        <id>right_head</id>
    </s4>
    <s5>
        <points>'x34y24', 'x34y34'</points>
        <t_values>0.00,1.00</t_values>
        <id>right_torso</id>
    </s5>
    <s6>
        <points>'x34y28', 'x28y24'</points>
        <t_values>0.00,1.00</t_values>
        <id>right_arm</id>
    </s6>
    <s7>
        <points>'x4y42', 'x46y42'</points>
        <t_values>0.00,1.00</t_values>
        <id>ground</id>
    </s7>
</strokes>
</example>"""


BALL_EXAMPLE = """<example>
<concept>Small ball</concept>
<strokes>
    <s9>
        <points>'x28y36', 'x30y37', 'x31y39', 'x30y41', 'x28y42', 'x26y41', 'x25y39', 'x26y37', 'x28y36'</points>
        <t_values>0.00,0.125,0.25,0.375,0.50,0.625,0.75,0.875,1.00</t_values>
        <id>ball</id>
    </s9>
</strokes>
</example>"""


STICK_DOG_EXAMPLE = """<example>
<concept>Stick dog</concept>
<strokes>
    <s1>
        <points>'x16y24', 'x19y25', 'x20y28', 'x19y31', 'x16y32', 'x13y31', 'x12y28', 'x13y25', 'x16y24'</points>
        <t_values>0.00,0.125,0.25,0.375,0.50,0.625,0.75,0.875,1.00</t_values>
        <id>dog_head</id>
    </s1>
    <s2>
        <points>'x16y32', 'x28y32'</points>
        <t_values>0.00,1.00</t_values>
        <id>dog_body</id>
    </s2>
    <s3>
        <points>'x18y32', 'x16y42'</points>
        <t_values>0.00,1.00</t_values>
        <id>dog_front_leg</id>
    </s3>
    <s4>
        <points>'x26y32', 'x28y42'</points>
        <t_values>0.00,1.00</t_values>
        <id>dog_back_leg</id>
    </s4>
    <s5>
        <points>'x28y32', 'x32y28'</points>
        <t_values>0.00,1.00</t_values>
        <id>dog_tail</id>
    </s5>
</strokes>
</example>"""


def _draw_extra_block(task: dict) -> tuple[str, str]:
    example_map = {
        "racket": RACKET_EXAMPLE,
        "ball": BALL_EXAMPLE,
        "fight": FIGHT_EXAMPLE,
        "two": TWO_PERSON_EXAMPLE,
        "dog": STICK_DOG_EXAMPLE,
    }
    names = list(task.get("examples") or [])
    if not names:
        if task.get("props"):
            names.append("racket")
        if task.get("n_subjects", 1) >= 2:
            names.append("fight" if task.get("fight") else "two")
    extra = ""
    for name in names:
        blob = example_map.get(name)
        if blob:
            extra += "\n" + blob
    extra_notes = (task.get("draw_extra") or "").strip()
    if extra_notes:
        extra += "\n" + extra_notes
    who = task.get("who") or (
        "Two people with unique name prefixes. Never merge the two bodies."
        if task.get("n_subjects", 1) >= 2
        else "One person only."
    )
    return extra, who


def anim_draw_user(task: dict, plan_text: str, frame_i: int, n_frames: int, prev_xml: str | None) -> str:
    n_min, n_max = task.get("part_range", (MIN_PARTS, MAX_PARTS))
    prev = ""
    if prev_xml:
        prev = f"""
Previous frame XML:
- Copy ground / floor / horizon / bench / water strokes with the EXACT same points.
- Do NOT copy the same cells for heads, limbs, or moving props — those must pose this frame.
{prev_xml}
"""
    extra, who = _draw_extra_block(task)
    return f"""Draw frame {frame_i}/{n_frames} of: {task['concept']}
{task['prompt']}

This is a full redraw of the frame (not an interpolated inbetween). The action must be readable here.

Format example (copy the stick-figure geometry, pick new cells for THIS frame):
{STICK_EXAMPLE}

{extra}

Also legal:
{HOUSE}

Planner layout for THIS frame:
{plan_text}
{prev}
Keep {n_min}–{n_max} strokes. Same part names as the plan. {who}

{xml_tail(task['concept'])}"""


WALK_TASK = {
    "task_id": "anim_stick_walk_right",
    "concept": "stick person walking",
    "viewpoint": "side view facing right",
    "prompt": (
        "Side view, facing right. Abstract stick figure walking left-to-right. "
        "The whole body translates. Legs alternate: contact, pass, contact, pass. "
        "Opposite arm swing. Sparse, cute, readable stride. No background."
    ),
    "motion_rules": (
        "- the body translates across the page\n"
        "- legs swap which one is forward, with passing poses between contacts"
    ),
    "frame_schema": (
        '"body_region": "e.g. left quarter, standing on the bottom third",\n'
        '      "left_leg": "forward planted / back pushing / passing under hip",\n'
        '      "right_leg": "the opposite of left_leg",\n'
        '      "left_arm": "opposite the left leg",\n'
        '      "right_arm": "opposite the right leg",\n'
        '      "notes": "contact or passing pose"'
    ),
    "part_range": (5, 8),
    "allow_detached_prop": False,
    "props": False,
    "gif_ms": 280,
    "suggested_keys": "start (first contact stride), passing or opposite contact, end further along the path",
}

SERVE_TASK = {
    "task_id": "anim_stick_badminton_serve",
    "concept": "stick person serving badminton",
    "viewpoint": "side view facing right",
    "prompt": (
        "Side view, facing right. Abstract stick figure doing a low badminton serve. "
        "Person stays mostly in the left half. Right hand holds a simple racket. "
        "A tiny shuttle starts at the racket, is struck, then flies up and to the right. "
        "Sequence must read: ready, racket back, contact, follow-through, shuttle leaving. "
        "Sparse. No net, no court lines, no second player."
    ),
    "motion_rules": (
        "- one person, one racket, one shuttle in every frame\n"
        "- early frames: ready / racket drawn back, shuttle near the racket or non-racket hand\n"
        "- a middle frame is the hit: racket meets shuttle in front of the body, low or mid\n"
        "- later frames: follow-through, racket swings forward/up, shuttle travels up-right, farther each frame\n"
        "- the person stays on the left half; only a small weight shift, they do not walk away\n"
        "- shuttle after contact must be clearly detached and progressing toward the right"
    ),
    "frame_schema": (
        '"body_region": "left half, feet on the bottom third",\n'
        '      "stance": "feet staggered, slight crouch or upright",\n'
        '      "racket_arm": "backswing / coming forward / contact / follow-through",\n'
        '      "free_arm": "holding shuttle / released / counterbalance",\n'
        '      "racket": "where the racket head is relative to the body",\n'
        '      "shuttle": "at the hand / at the racket / just off the strings / flying up-right",\n'
        '      "notes": "name the beat: ready, toss, hit, or fly"'
    ),
    "part_range": (7, 10),
    "allow_detached_prop": True,
    "props": True,
    "gif_ms": 180,
    "suggested_keys": "start/ready, hit/contact (shuttle leaving the racket), end (shuttle far up-right)",
}

SWORD_TASK = {
    "task_id": "anim_stick_sword_cut",
    "concept": "stick person cutting another stick person away with a sword",
    "viewpoint": "side view, attacker on the left facing right",
    "prompt": (
        "Two abstract stick figures. Attacker on the left swings a sword with a VISIBLE HILT. "
        "The sword has three strokes: a short grip (柄) in the hand, a short crossguard (护手) "
        "perpendicular to the blade, and a longer blade. The guard must be readable as a T or cross, "
        "not a continuation of the blade. "
        "The attacker's HEAD MUST MOVE with the lunge: back on the ready key, clearly farther right on the hit key, "
        "then settle on follow-through. Do not freeze the head on the same cells across keys. "
        "Victim on the right is struck and knocked flying up-right. "
        "No blood, no background, no third person."
    ),
    "motion_rules": (
        "- two people with unique part names attacker_* and victim_* plus sword_grip, sword_guard, sword_blade\n"
        "- sword_guard is a short line crossing the grip/blade join, roughly perpendicular to the blade\n"
        "- attacker_head center must change between keys (lunge forward on hit, not a copied circle)\n"
        "- start: both on the ground, attacker left, victim right, sword raised, head over the back foot\n"
        "- hit: sword contacts the victim; attacker head and torso have shifted toward the victim\n"
        "- after hit: victim translates up and right; attacker follow-through, head may drop slightly\n"
        "- interpolation cannot invent the hit or the detach; those must be keys\n"
        "- the incoming sword arc (start→hit) is the longest rotation; give it MORE inbetweens than the follow-through so both halves of the swing read at similar speed\n"
        "- use the same ease on the swing gaps; do not dump leftover inbetweens after the hit just because the victim flies\n"
        "- one shared anchored ground line; bodies move, the ground does not"
    ),
    "frame_schema": (
        '"attacker": "head location relative to the feet, sword angle, stance",\n'
        '      "victim": "standing / crumpling / airborne / farther",\n'
        '      "sword": "grip in the hand, guard visible, blade where it points or what it touches",\n'
        '      "notes": "beat name: ready, hit, fly, or end"'
    ),
    "part_range": (13, 16),
    "allow_detached_prop": True,
    "props": False,
    "n_subjects": 2,
    "gif_ms": 80,
    "target_frames": 12,
    "forced_gaps": [
        {"n_inbetween": 4, "ease": "smooth", "why": "long incoming sword arc; match swing speed"},
        {"n_inbetween": 2, "ease": "smooth", "why": "follow-through plus victim lift-off"},
        {"n_inbetween": 2, "ease": "smooth", "why": "victim farther, sword already settling"},
    ],
    "suggested_keys": "start (both standing, head back), hit (head lunged forward, sword contacts victim), fly (victim airborne), end (victim farther)",
    "examples": ["fight"],
    "fight": True,
    "who": "Two people with unique names attacker_* and victim_*. Never merge the two bodies.",
    "draw_extra": (
        "Sword anatomy: sword_grip (short handle in the fist), sword_guard (short crossbar), "
        "sword_blade (long line). The guard must stick out sideways so the hilt reads as a hilt.\n"
        "Attacker head: change its grid cells on EVERY key. Ready = head more left/back; "
        "hit = head several cells to the right as the body lunges; fly/end = head not identical to hit."
    ),
}

def _clip(**kwargs) -> dict:
    base = {
        "gif_ms": 80,
        "target_frames": 12,
        "allow_detached_prop": False,
        "props": False,
        "n_subjects": 1,
    }
    base.update(kwargs)
    return base


def _gaps(n1: int, n2: int, why1: str, why2: str) -> list:
    return [
        {"n_inbetween": n1, "ease": "smooth", "why": why1},
        {"n_inbetween": n2, "ease": "smooth", "why": why2},
    ]


KICK_TASK = _clip(
    task_id="anim_stick_penalty_kick",
    concept="stick person taking a penalty kick",
    viewpoint="side view facing right",
    prompt=(
        "One stick person on the left plants and kicks a round ball into the top-right. "
        "Start: person coiled, ball on the ground at their feet. "
        "Hit: kicking foot meets the ball. Then the ball flies up-right, clearly off the foot. "
        "Sparse, cute. One shared ground. No goal posts, no keeper."
    ),
    motion_rules=(
        "- one person, one ball, one anchored ground\n"
        "- hit key: foot contacts the ball; interpolation cannot invent the kick\n"
        "- after hit the ball detaches and travels farther each key; the kicker follows through in place\n"
        "- more inbetweens after the hit because the ball travels farther; same ease on both gaps"
    ),
    frame_schema=(
        '"kicker": "coil / plant / follow-through",\n'
        '      "ball": "on the ground at the foot / leaving the foot / far up-right",\n'
        '      "notes": "plant, hit, or fly"'
    ),
    part_range=(7, 11),
    allow_detached_prop=True,
    examples=["ball"],
    suggested_keys="start (coiled, ball at feet), hit (foot meets ball), end (ball far up-right)",
    forced_gaps=_gaps(3, 6, "short plant into the kick", "ball flies farther; keep swing/follow speed similar"),
    draw_extra="Ball is a small circle. After the hit key it must not stay stuck to the foot.",
)

THROW_TASK = _clip(
    task_id="anim_stick_snowball_throw",
    concept="stick person throwing a snowball",
    viewpoint="side view facing right",
    prompt=(
        "One stick person throws a small snowball overhand. "
        "Start: arm cocked back, snowball in the throwing hand. "
        "Release: hand snaps forward, snowball just leaving the fingers. "
        "End: snowball is far up-right; person in follow-through. No second person, no trees."
    ),
    motion_rules=(
        "- one person, one snowball, one anchored ground\n"
        "- release is a key: snowball detaches; interpolation cannot invent the leaving-hand\n"
        "- after release the snowball travels farther; body stays in the left half\n"
        "- more inbetweens on the flight than on the short wind-up; same ease"
    ),
    frame_schema=(
        '"thrower": "cocked / snapping / follow-through",\n'
        '      "snowball": "in the hand / just off the fingers / far up-right",\n'
        '      "notes": "windup, release, or fly"'
    ),
    part_range=(7, 11),
    allow_detached_prop=True,
    examples=["ball"],
    suggested_keys="start (arm back, snowball in hand), release (snowball leaving), end (snowball far)",
    forced_gaps=_gaps(3, 6, "short wind-up", "snowball flies farther"),
    draw_extra="Name the projectile snowball. It is a tiny circle, not a second head.",
)

JUMP_TASK = _clip(
    task_id="anim_stick_creek_jump",
    concept="stick person leaping a small creek",
    viewpoint="side view facing right",
    prompt=(
        "One stick person jumps a small creek. Two short ground pads: left_ground and right_ground, both anchored. "
        "The middle is empty water — do not draw a connecting floor. "
        "Start: crouched on the left bank. Mid: tucked in the air over the gap, feet off both pads. "
        "End: landed on the right bank. Head and body must travel with the jump."
    ),
    motion_rules=(
        "- one person, two anchored pads left_ground and right_ground; pads never move\n"
        "- airborne key: feet off both pads; interpolation cannot invent the launch\n"
        "- body translates left-bank to right-bank; up then down\n"
        "- similar inbetween counts on takeoff and landing so the jump does not whip then crawl"
    ),
    frame_schema=(
        '"body": "crouched on left / tucked over the gap / landed on right",\n'
        '      "feet": "on left_ground / in the air / on right_ground",\n'
        '      "notes": "crouch, air, or land"'
    ),
    part_range=(8, 12),
    suggested_keys="start (crouch on left bank), air (tucked over the creek), end (land on right bank)",
    forced_gaps=_gaps(4, 5, "takeoff arc", "landing arc, similar speed"),
    draw_extra="Two separate short ground strokes. Do not draw one long floor across the creek.",
)

HIGHFIVE_TASK = _clip(
    task_id="anim_stick_jumping_highfive",
    concept="two stick friends jumping high-five",
    viewpoint="side view, two people facing inward",
    prompt=(
        "Two stick friends. Left one faces right, right one faces left. "
        "They run in a step, jump, and clap open palms together in the air, then land apart. "
        "Start: both on the ground, hands not touching. Contact: both airborne, palms meet in the middle. "
        "End: back on the ground, a little farther apart. No swords, no props."
    ),
    motion_rules=(
        "- two people with unique names left_* and right_* plus one shared anchored ground\n"
        "- contact key: palms meet; interpolation cannot invent the clap\n"
        "- both heads and bodies leave the ground on the contact key, then land\n"
        "- similar speed into the clap and out of it; same ease"
    ),
    frame_schema=(
        '"left": "on ground approaching / jumping, hand high / landed",\n'
        '      "right": "mirror of left",\n'
        '      "hands": "apart / palms together / apart again",\n'
        '      "notes": "approach, clap, or land"'
    ),
    part_range=(12, 16),
    n_subjects=2,
    examples=["two"],
    who="Two friends named left_* and right_*. Never merge the two bodies. No swords.",
    suggested_keys="start (both on ground, hands apart), clap (airborne, palms meet), end (landed, apart)",
    forced_gaps=_gaps(4, 5, "into the jump-clap", "out of the clap, similar speed"),
    draw_extra="Palms meeting is two short hand/forearm lines that touch at the tips on the clap key only.",
)

SIT_TASK = _clip(
    task_id="anim_stick_sit_bench",
    concept="stick person sitting down on a bench",
    viewpoint="side view facing right",
    prompt=(
        "One tired stick person sits down on a simple park bench. "
        "The bench is two anchored strokes: a horizontal seat and a short support. It never moves. "
        "Start: standing beside the bench. Mid: hovering, knees bent, hips lowering. "
        "End: fully seated, hips on the seat, knees forward. Head drops a little as they sit."
    ),
    motion_rules=(
        "- one person, anchored bench_seat and bench_leg, one anchored ground\n"
        "- seated key: hips on the bench; interpolation cannot invent sitting\n"
        "- body folds (torso tilts, knees bend); do not slide the bench\n"
        "- similar speed lowering and settling"
    ),
    frame_schema=(
        '"body": "standing / lowering / seated",\n'
        '      "bench": "unchanged",\n'
        '      "notes": "stand, lower, or sit"'
    ),
    part_range=(8, 12),
    suggested_keys="start (standing by the bench), lower (hips dropping), end (fully seated)",
    forced_gaps=_gaps(4, 5, "sit-down fold", "settle onto the seat"),
    draw_extra="bench_seat is a short horizontal line. Copy it exactly on every key. Person sits ON it, not through it.",
)

ARCHERY_TASK = _clip(
    task_id="anim_stick_archery",
    concept="stick archer loosing an arrow",
    viewpoint="side view facing right",
    prompt=(
        "One stick archer. Bow is a simple C-curve plus a string line. Arrow is a long thin line. "
        "Start: full draw, arrow nocked on the string. Loose: string snaps, arrow just leaving the bow. "
        "End: arrow far to the right; archer in follow-through. No target, no extra people."
    ),
    motion_rules=(
        "- one person, bow_curve, bow_string, arrow, anchored ground\n"
        "- loose is a key: arrow detaches from the string; interpolation cannot invent the shot\n"
        "- after loose the arrow travels farther; archer stays in the left half\n"
        "- more inbetweens on the arrow flight; same ease"
    ),
    frame_schema=(
        '"archer": "full draw / loose / follow-through",\n'
        '      "arrow": "nocked / just off the string / far right",\n'
        '      "notes": "draw, loose, or fly"'
    ),
    part_range=(9, 13),
    allow_detached_prop=True,
    suggested_keys="start (full draw, arrow on string), loose (arrow leaving), end (arrow far right)",
    forced_gaps=_gaps(3, 6, "short loose", "arrow flies farther"),
    draw_extra="Arrow is one long line. After the loose key it must not stay stuck to the bow.",
)

PICKUP_TASK = _clip(
    task_id="anim_stick_pickup_gift",
    concept="stick person picking up a gift box",
    viewpoint="side view facing right",
    prompt=(
        "One stick person picks a small square gift box off the ground and hugs it to their chest. "
        "Start: standing, box on the ground, hands empty. Grasp: bent over, both hands on the box still on the floor. "
        "End: upright, box against the torso. The box moves only after the grasp key."
    ),
    motion_rules=(
        "- one person, one box (tiny square or two short lines), one anchored ground\n"
        "- grasp is a key: hands meet the box; interpolation cannot invent the pickup\n"
        "- after grasp the box parents to the hands and rises with the body\n"
        "- similar speed bending down and standing up"
    ),
    frame_schema=(
        '"body": "stand / bend / hug upright",\n'
        '      "box": "on the ground / in both hands on the ground / hugged to chest",\n'
        '      "notes": "reach, grasp, or lift"'
    ),
    part_range=(8, 12),
    suggested_keys="start (box on ground, hands empty), grasp (hands on box), end (box hugged to chest)",
    forced_gaps=_gaps(4, 5, "bend to the box", "lift and hug, similar speed"),
    draw_extra="Box is a tiny square (four short sides or a small closed loop). It stays on the ground until the grasp key.",
)

FISH_TASK = _clip(
    task_id="anim_stick_lucky_catch",
    concept="stick person fishing as a tiny fish leaps off the line",
    viewpoint="side view facing right",
    prompt=(
        "One stick person on the left bank with a simple fishing rod (a long line). "
        "A tiny fish is the only other moving prop. "
        "Start: rod cast, fish still in the water on the right, on the line. "
        "Yank: person leans back, fish just leaving the water. "
        "End: fish flies up-right off the hook; person in a surprised lean. "
        "Optional short anchored water line. No boat, no second person."
    ),
    motion_rules=(
        "- one person, rod, line, fish, anchored ground; water line if present is anchored\n"
        "- yank is a key: fish leaves the water; interpolation cannot invent the leap\n"
        "- after yank the fish travels up-right and detaches from the line\n"
        "- more inbetweens on the fish flight; same ease"
    ),
    frame_schema=(
        '"fisher": "waiting / yanking back / surprised",\n'
        '      "fish": "in the water on the line / leaving the water / flying off up-right",\n'
        '      "notes": "wait, yank, or leap"'
    ),
    part_range=(9, 13),
    allow_detached_prop=True,
    suggested_keys="start (rod out, fish in water), yank (fish leaving water), end (fish flying off)",
    forced_gaps=_gaps(3, 6, "short yank", "fish leaps farther"),
    draw_extra="Fish is a tiny sideways V or oval, not a second person. After the yank it must leave the hook.",
)

DOG_CHASE_TASK = _clip(
    task_id="anim_stick_dog_chase_ball",
    concept="stick dog chasing a bouncing ball",
    viewpoint="side view facing right",
    prompt=(
        "One abstract stick dog, not a human. Circle head, long body line, four short legs, a tail. "
        "A small ball rolls then bounces ahead to the right; the dog runs after it. "
        "Start: dog coiled on the left, ball near its nose. "
        "Mid: dog stretched in a run, ball farther right and a bit off the ground. "
        "End: dog still chasing, ball farther still. One anchored ground. No person."
    ),
    motion_rules=(
        "- one dog (dog_head, dog_body, legs, tail), one ball, one anchored ground\n"
        "- the dog translates right; legs swap a running pose between keys\n"
        "- the ball stays ahead of the dog and must not merge into the head\n"
        "- similar chase speed across keys; same ease"
    ),
    frame_schema=(
        '"dog": "coiled / stretched run / still running farther",\n'
        '      "ball": "at the nose / ahead and up / farther right",\n'
        '      "notes": "ready, chase, or farther"'
    ),
    part_range=(8, 16),
    allow_detached_prop=True,
    kind="animal",
    assets=[
        {
            "id": "dog",
            "prefix": "dog",
            "concept": "standing dog",
            "prompt": (
                "A cute simple dog stands in side view facing right. "
                "Four legs planted, a tail, an ear. Two short vertical-line eyes, no circular pupils. "
                "Silhouette with a body, not a stick person."
            ),
        }
    ],
    examples=["ball"],
    who="One dog from the character sheet, plus a ball. Not a stick person.",
    suggested_keys="start (dog coiled, ball at nose), chase (running, ball ahead), end (farther right)",
    forced_gaps=_gaps(4, 5, "first burst of the chase", "keep chasing at similar speed"),
    draw_extra="Dog has four short legs and a tail. Ball is a small circle, never a second head.",
)

CAT_POUNCE_TASK = _clip(
    task_id="anim_stick_cat_pounce",
    concept="stick cat pouncing on a mouse",
    viewpoint="side view facing right",
    prompt=(
        "A stick cat on the left and a tiny stick mouse on the right. "
        "Cat: round head, arched back, four legs, long tail. Mouse: tiny circle plus a tail, much smaller. "
        "Start: cat crouched, mouse standing still to the right. "
        "Pounce: cat airborne stretched toward the mouse, mouse just starting to flee. "
        "End: cat landed farther right, mouse escaped farther still. Unique names cat_* and mouse_*. No person."
    ),
    motion_rules=(
        "- two animals cat_* and mouse_*; never merge them; one anchored ground\n"
        "- pounce key: cat leaves the ground; interpolation cannot invent the leap\n"
        "- mouse translates right after the pounce; cat follows but stays larger\n"
        "- similar speed into and out of the pounce; same ease"
    ),
    frame_schema=(
        '"cat": "crouch / airborne pounce / landed",\n'
        '      "mouse": "still / darting / farther",\n'
        '      "notes": "crouch, pounce, or miss"'
    ),
    part_range=(8, 16),
    n_subjects=2,
    allow_detached_prop=True,
    kind="animal",
    assets=[
        {
            "id": "cat",
            "prefix": "cat",
            "concept": "standing cat",
            "prompt": (
                "A cute cat stands in side view facing right, slightly crouched. "
                "Pointed ears, long tail, four legs. Two short vertical-line eyes, no circular pupils."
            ),
        },
        {
            "id": "mouse",
            "prefix": "mouse",
            "concept": "standing mouse",
            "prompt": (
                "A tiny cute mouse stands in side view facing right. Round ears, long thin tail. "
                "Much smaller than a cat. Line eyes, no circular pupils."
            ),
        },
    ],
    examples=[],
    who="Two animals from the character sheets: cat_* and mouse_*. Mouse is much smaller. No humans.",
    suggested_keys="start (cat crouched, mouse still), pounce (cat in the air), end (mouse farther, cat landed)",
    forced_gaps=_gaps(4, 5, "into the pounce", "after the pounce, similar speed"),
    draw_extra="Cat back arches on the crouch and stretches on the pounce. Mouse is a tiny circle plus a thin tail.",
)

BIRD_TASK = _clip(
    task_id="anim_stick_bird_takeoff",
    concept="stick bird taking off from a branch",
    viewpoint="side view facing right",
    prompt=(
        "One stick bird: tiny round head, short body, two wing lines, two tiny legs. "
        "An anchored branch (a short line) on the left. "
        "Start: bird perched, wings folded. "
        "Lift: wings up, feet just off the branch. "
        "End: bird farther up-right, wings in a flap; branch unchanged. No person, no second bird."
    ),
    motion_rules=(
        "- one bird, one anchored branch, optional anchored ground\n"
        "- lift key: feet leave the branch; interpolation cannot invent takeoff\n"
        "- after lift the bird translates up-right; branch never moves\n"
        "- more inbetweens on the flight than on the crouch; same ease"
    ),
    frame_schema=(
        '"bird": "perched / lifting off / flying up-right",\n'
        '      "branch": "unchanged",\n'
        '      "notes": "perch, lift, or fly"'
    ),
    part_range=(8, 16),
    allow_detached_prop=True,
    kind="animal",
    assets=[
        {
            "id": "bird",
            "prefix": "bird",
            "concept": "perched bird",
            "prompt": (
                "A cute small bird perches in side view facing right. Round body, short beak, "
                "two folded wings, two tiny legs. Line eyes, no circular pupils."
            ),
        }
    ],
    who="One bird from the character sheet. Prefix bird_*. Branch is anchored.",
    suggested_keys="start (perched on branch), lift (feet off, wings up), end (flying up-right)",
    forced_gaps=_gaps(3, 6, "short crouch into takeoff", "flight travels farther"),
    draw_extra="Wings are two short lines. Copy the branch points exactly on every key.",
)

RABBIT_TASK = _clip(
    task_id="anim_rabbit_hop",
    concept="small ellipse-body rabbit hopping to the right",
    viewpoint="side view facing right",
    prompt=(
        "One SMALL rabbit from the character sheet hops to the right. "
        "Rounder body ellipse, smaller head circle on the upper-front, two long upright ears, "
        "cottontail, one vertical-line eye, NO legs. "
        "Start: LEFT third, crouched on the ground; right half empty. "
        "Air: CENTER, body and head translated up-right, still the same small size. "
        "End: RIGHT-CENTER, landed back on the ground, still several empty cells before the right border. "
        "One anchored ground. No person."
    ),
    motion_rules=(
        "- one small rabbit from the sheet plus one anchored ground; no legs\n"
        "- body, head, ears, cottontail translate together; keep the same sizes; do not enlarge\n"
        "- air key is higher and farther right; land key is on the ground farther still, with margin\n"
        "- similar hop speed up and down; same ease"
    ),
    frame_schema=(
        '"rabbit": "left third crouched / center airborne up-right / right-center landed",\n'
        '      "notes": "crouch, air, or land"'
    ),
    part_range=(7, 16),
    kind="animal",
    assets=[
        {
            "id": "rabbit",
            "prefix": "rabbit",
            "concept": "standing rabbit",
            "seed": "rabbit_example",
            "max_w": 16,
            "max_h": 18,
            "prompt": (
                "A SMALL rabbit sits in the left third, side view facing right. "
                "Rounder body ellipse, smaller head, two long upright ears, cottontail, no legs."
            ),
        }
    ],
    examples=[],
    who="One rabbit from the character sheet. Prefix rabbit_*. Long ears must stay. No legs.",
    suggested_keys="start (left third, crouched), air (center, up-right), end (right-center, landed, margin left)",
    forced_gaps=_gaps(4, 5, "takeoff", "landing at similar speed"),
    draw_extra="Keep the two long ear strokes and cottontail. Omit legs. Keep the SMALL size; hop by translating the whole rabbit.",
)

CAT_WALK_TASK = _clip(
    task_id="anim_cat_walk_cycle",
    concept="small ellipse-body cat walking to the right",
    viewpoint="side view facing right",
    prompt=(
        "One SMALL cat from the character sheet walks to the right. "
        "Ellipse body, circle head on the upper-front, two pointed triangle ears, a tiny smile, "
        "2–3 whiskers per side, four SHORT tick-legs, a long tail that curves up, one vertical-line eye. "
        "Start: LEFT third, diagonal contact stride; right half empty. "
        "Pass: CENTER, legs gathered under the body. "
        "End: RIGHT-CENTER, opposite contact, still several empty cells before the right border. "
        "Head stays above the body. One anchored ground. No mouse, no person."
    ),
    motion_rules=(
        "- one small cat from the sheet plus one anchored ground; no mouse\n"
        "- SMALL: body ~1/3 canvas width; start left third, end right-center with margin\n"
        "- body and head translate right together; keep the same sizes; do not enlarge\n"
        "- legs are short ticks that change angle; tail stays a long up-curve\n"
        "- similar walk speed on both gaps; same ease"
    ),
    frame_schema=(
        '"cat": "left third, contact A / center passing / right-center contact B",\n'
        '      "notes": "contact A, pass, or contact B"'
    ),
    part_range=(8, 16),
    kind="animal",
    assets=[
        {
            "id": "cat",
            "prefix": "cat",
            "concept": "standing cat",
            "max_w": 16,
            "max_h": 20,
            "prompt": (
                "A SMALL cat stands in the left third, side view facing right. "
                "Ellipse body about 12 cells wide, circle head above the upper-front, "
                "two pointed ears, tiny smile, whiskers, four short tick-legs, long tail curving up."
            ),
        }
    ],
    examples=[],
    who="One cat from the character sheet (cat_*). Pointed ears and whiskers. Not a stick person.",
    suggested_keys="start (left third, first contact), pass (center, legs under body), end (right-center, opposite contact)",
    forced_gaps=_gaps(4, 5, "into the passing stride", "out of the pass, similar walk speed"),
    draw_extra=(
        "Keep pointed ears, whiskers, tiny smile, and the long up-curved tail. "
        "Keep the SMALL size. Only retarget placement and the four tick-legs. Head stays above the body."
    ),
)

MOUSE_WALK_TASK = _clip(
    task_id="anim_mouse_walk_cycle",
    concept="tiny ellipse-body mouse walking to the right",
    viewpoint="side view facing right",
    prompt=(
        "One TINY mouse from the character sheet walks to the right. "
        "Ellipse body even smaller than a cat (about 8–10 cells wide), small circle head, "
        "two small round ears, a tiny nose, whiskers, four SHORT tick-legs, a long thin tail. "
        "Start: LEFT third, diagonal contact; most of the canvas empty. "
        "Pass: a bit right of center, legs under the body. "
        "End: farther right but still with empty margin. "
        "Head stays above the body. One anchored ground. No cat, no person."
    ),
    motion_rules=(
        "- one tiny mouse from the sheet plus one anchored ground\n"
        "- TINY: smaller than the cat/dog; start left third; plenty of empty travel room\n"
        "- body and head translate right together; keep the same sizes; do not enlarge\n"
        "- long thin tail trails; tick-legs change angle between keys\n"
        "- similar walk speed on both gaps; same ease"
    ),
    frame_schema=(
        '"mouse": "left third, contact A / farther passing / farther still contact B",\n'
        '      "notes": "contact A, pass, or contact B"'
    ),
    part_range=(8, 16),
    kind="animal",
    assets=[
        {
            "id": "mouse",
            "prefix": "mouse",
            "concept": "standing mouse",
            "max_w": 12,
            "max_h": 14,
            "prompt": (
                "A TINY mouse stands in the left third, side view facing right. "
                "Body ellipse about 8–10 cells wide, small head, round ears, tiny nose, "
                "whiskers, four short tick-legs, long thin tail."
            ),
        }
    ],
    examples=[],
    who="One tiny mouse from the character sheet (mouse_*). Round ears, long thin tail. Not a stick person.",
    suggested_keys="start (left third, first contact), pass (legs under body), end (farther, opposite contact, margin left)",
    forced_gaps=_gaps(4, 5, "into the passing stride", "out of the pass, similar walk speed"),
    draw_extra=(
        "Keep round ears, tiny nose, whiskers, and the long thin tail. "
        "Stay TINY. Only retarget placement and the four tick-legs. Head stays above the body."
    ),
)

DOG_WALK_TASK = _clip(
    task_id="anim_dog_walk_cycle",
    concept="ellipse-body dog walking to the right",
    viewpoint="side view facing right",
    prompt=(
        "One dog from the character sheet walks to the right. "
        "Keep it SMALL (body about 12 cells wide) so there is room to walk. "
        "Ellipse body, circle head overlapping the upper-front, sideways U mouth, no nose, "
        "floppy ear, short vertical-line eye, four SHORT tick-legs, tail cocked up. "
        "Start: LEFT third of the canvas, one front tick forward and the opposite hind tick forward; right half empty. "
        "Pass: CENTER, farther right, legs gathered under the body. "
        "End: RIGHT-CENTER, opposite contact stride, still several empty cells before the right border. "
        "Head stays above the body. One anchored ground. No person, no ball."
    ),
    motion_rules=(
        "- one dog from the sheet plus one anchored ground; no person\n"
        "- SMALL animal: body ~1/3 canvas width; start left third, end right-center with margin\n"
        "- body and head translate right together; keep the same sizes; do not enlarge\n"
        "- legs are short ticks that change placement/angle between keys (walk, not a stand)\n"
        "- similar walk speed on both gaps; same ease"
    ),
    frame_schema=(
        '"dog": "left third, front tick forward / center passing stride / right-center opposite contact",\n'
        '      "notes": "contact A, pass, or contact B"'
    ),
    part_range=(8, 16),
    kind="animal",
    assets=[
        {
            "id": "dog",
            "prefix": "dog",
            "concept": "standing dog",
            "seed": "dog_example",
            "prompt": (
                "A SMALL dog stands in the left third, side view facing right. "
                "Body ellipse about 12 cells wide. Ellipse body, circle head above the "
                "upper-front, floppy ear, sideways U mouth, no nose, four short tick-legs, tail up."
            ),
        }
    ],
    examples=[],
    who="One dog from the character sheet (dog_*). Ellipse body + circle head. Not a stick person.",
    suggested_keys="start (left third, first contact), pass (center, legs under body), end (right-center, opposite contact, margin left)",
    forced_gaps=_gaps(4, 5, "into the passing stride", "out of the pass, similar walk speed"),
    draw_extra=(
        "Keep the sheet's ellipse body, circle head, U mouth, floppy ear, and cocked tail. "
        "Keep the SMALL size. Only retarget placement and the four tick-legs for the walk. Head stays above the body."
    ),
)

WALKDOG_TASK = _clip(
    task_id="anim_stick_walk_the_dog",
    concept="stick person walking a stick dog on a leash",
    viewpoint="side view facing right",
    prompt=(
        "A stick person on the left and a stick dog slightly ahead on the right, connected by a short leash line. "
        "They walk right together. Person: head, torso, two arms, two legs. Dog: head, body, legs, tail. "
        "Start: both standing, leash slack-ish. Mid: opposite passing step, leash taut. "
        "End: farther right, next contact step. Unique names person_* and dog_*. One anchored ground."
    ),
    motion_rules=(
        "- two subjects person_* and dog_* plus leash and anchored ground; never merge\n"
        "- both bodies translate right; legs alternate\n"
        "- leash stays a short line between person hand and dog neck\n"
        "- similar walking speed for both; same ease"
    ),
    frame_schema=(
        '"person": "contact stride / passing / next contact farther",\n'
        '      "dog": "walk matching the person, a little ahead",\n'
        '      "leash": "hand to dog neck",\n'
        '      "notes": "step A, pass, or step B"'
    ),
    part_range=(10, 16),
    n_subjects=2,
    kind="animal",
    assets=[
        {
            "id": "dog",
            "prefix": "dog",
            "concept": "standing dog",
            "prompt": (
                "A cute simple dog stands in side view facing right. Four legs, a tail, an ear. "
                "Line eyes, no circular pupils. Silhouette, not a stick person."
            ),
        }
    ],
    examples=[],
    who="One stick person (person_*) and one dog from the character sheet (dog_*). Never merge. Leash is one short line.",
    suggested_keys="start (first contact stride), pass (opposite legs), end (farther contact)",
    forced_gaps=_gaps(4, 5, "into the passing stride", "out of the pass, similar walk speed"),
    draw_extra="Dog is four-legged with a tail, not a second stick person. Person holds the leash.",
)

HORSE_TASK = _clip(
    task_id="anim_stick_horse_jump",
    concept="stick horse jumping a fence",
    viewpoint="side view facing right",
    prompt=(
        "One stick horse: long head/neck, long body, four legs, tail. "
        "An anchored two-line fence in the middle (two short posts or one rail). The fence never moves. "
        "Start: horse approaching on the left, gathered. "
        "Air: horse tucked over the fence, all hooves off the ground. "
        "End: landed on the right of the fence. No rider, no second animal."
    ),
    motion_rules=(
        "- one horse, anchored fence, anchored ground\n"
        "- air key: hooves off the ground over the fence; interpolation cannot invent the jump\n"
        "- fence points stay identical; horse translates left to right\n"
        "- similar speed into and out of the jump"
    ),
    frame_schema=(
        '"horse": "approach / over the fence / landed right",\n'
        '      "fence": "unchanged",\n'
        '      "notes": "approach, air, or land"'
    ),
    part_range=(8, 16),
    kind="animal",
    assets=[
        {
            "id": "horse",
            "prefix": "horse",
            "concept": "standing horse",
            "prompt": (
                "A cute horse stands in side view facing right. Long neck, body, four legs, tail. "
                "Line eyes, no circular pupils. Silhouette, not a stick person. No rider."
            ),
        }
    ],
    who="One horse from the character sheet. Prefix horse_*. Fence is anchored. No rider.",
    suggested_keys="start (approach left of fence), air (over the fence), end (landed on the right)",
    forced_gaps=_gaps(4, 5, "takeoff to the fence", "landing, similar speed"),
    draw_extra="Horse neck is a line from head to body. Copy fence cells exactly on every key.",
)

DEFLECT_TASK = _clip(
    task_id="anim_stick_saber_deflect",
    concept="small stick trooper firing a bolt that a stick jedi deflects with a saber",
    viewpoint="side view, trooper left facing right, jedi right facing left",
    prompt=(
        "Two SMALL stick figures on a 50x50 grid — each only about 8–12 cells tall, "
        "far apart, so the bolt has a long empty path. No armor detail, no logos. "
        "Trooper on the FAR LEFT (left fifth): round CIRCLE helmet-head (equal width and height, not a bean), torso, "
        "two legs, one gun-arm. Blaster is a SMALL GUN: a short body plus a barrel, not one dash. "
        "Jedi on the FAR RIGHT (right fifth): round CIRCLE head, torso, two legs, one saber-arm. "
        "Saber is a short grip in the fist plus a long blade (no crossguard). "
        "Bolt is a tiny short dash, the star of the shot. "
        "Start: trooper aiming right, bolt JUST OFF the muzzle (already detached, a few cells in front of the gun); "
        "jedi saber held back, not yet on the bolt's path. "
        "Deflect: bolt TOUCHES the saber blade in the right-center; jedi has swung the saber into a diagonal block. "
        "Rebound: bolt flying BACK toward the left, farther and a bit higher; saber follow-through; "
        "trooper may lean back. One shared anchored ground. No blood, no third person, no background ships."
    ),
    motion_rules=(
        "- two people trooper_* and jedi_* plus blaster, saber_grip, saber_blade, bolt, one anchored ground; never merge\n"
        "- BOTH people stay SMALL and parked: trooper left fifth, jedi right fifth; they do not walk across the page\n"
        "- the BOLT is the long travel: start just off the muzzle, deflect ON the saber, rebound far back left\n"
        "- deflect is a key: interpolation cannot invent the saber meeting the bolt\n"
        "- saber must change angle between start and deflect (block), then follow-through on rebound\n"
        "- inbound bolt path and rebound path should read at similar speed; same ease; more inbetweens on the farther hop\n"
        "- bolt stays a tiny dash, never a second head"
    ),
    frame_schema=(
        '"trooper": "left fifth, aiming / still aiming, maybe recoil / lean back",\n'
        '      "jedi": "right fifth, saber back / saber blocking in the bolt path / follow-through",\n'
        '      "bolt": "just off the muzzle / touching the saber / flying back left and up",\n'
        '      "notes": "shot, deflect, or rebound"'
    ),
    part_range=(12, 16),
    n_subjects=2,
    allow_detached_prop=True,
    examples=["skip"],
    who=(
        "Two small people: trooper_* on the left, jedi_* on the right. Never merge. "
        "Bolt, blaster, saber_grip, saber_blade are extra named parts."
    ),
    suggested_keys="start (bolt just off muzzle, saber back), deflect (bolt on saber), rebound (bolt far back left)",
    forced_gaps=_gaps(4, 5, "bolt flies to the saber", "bolt rebounds farther back, similar speed"),
    draw_extra=(
        "Keep both people TINY and pinned to opposite edges so the bolt path is long. "
        "Heads are CIRCLES (8 compass points, width = height), never beans. "
        "Trooper helmet is just a slightly larger circle. "
        "Blaster = short body + barrel (an L or tiny rectangle plus a line), not one dash on the arm. "
        "Saber = short grip + long blade, no T-guard. "
        "Bolt = one tiny dash. Copy ground exactly on every key."
    ),
)

RALLY_TASK = _clip(
    task_id="anim_stick_badminton_rally",
    concept="two stick figures playing badminton",
    viewpoint="side view",
    prompt="Two stick figures playing badminton.",
    part_range=(10, 16),
    n_subjects=2,
    allow_detached_prop=True,
    examples=["skip"],
)

BASKETBALL_TASK = _clip(
    task_id="anim_stick_basketball",
    concept="two stick figures playing basketball",
    viewpoint="side view",
    prompt="Two stick figures playing basketball.",
    part_range=(10, 16),
    n_subjects=2,
    allow_detached_prop=True,
    examples=["skip"],
)

TASKS = {
    "walk": WALK_TASK,
    "serve": SERVE_TASK,
    "badminton": RALLY_TASK,
    "rally": RALLY_TASK,
    "basketball": BASKETBALL_TASK,
    "hoop": BASKETBALL_TASK,
    "sword": SWORD_TASK,
    "cut": SWORD_TASK,
    "kick": KICK_TASK,
    "throw": THROW_TASK,
    "jump": JUMP_TASK,
    "highfive": HIGHFIVE_TASK,
    "sit": SIT_TASK,
    "archery": ARCHERY_TASK,
    "pickup": PICKUP_TASK,
    "fish": FISH_TASK,
    "dog": DOG_CHASE_TASK,
    "cat": CAT_POUNCE_TASK,
    "bird": BIRD_TASK,
    "rabbit": RABBIT_TASK,
    "walkdog": WALKDOG_TASK,
    "dogwalk": DOG_WALK_TASK,
    "catwalk": CAT_WALK_TASK,
    "mousewalk": MOUSE_WALK_TASK,
    "horse": HORSE_TASK,
    "saber": DEFLECT_TASK,
    "deflect": DEFLECT_TASK,
    "jedi": DEFLECT_TASK,
}

SUITE_TASKS = ["kick", "throw", "jump", "highfive", "sit", "archery", "pickup", "fish"]
ANIMAL_SUITE = ["dog", "cat", "bird", "rabbit", "walkdog", "dogwalk", "catwalk", "mousewalk", "horse"]

KEY_PLAN_SYSTEM = f"""You are a sketch planner for pose-to-pose stick-figure animation.
Return JSON only. No markdown.

A drawer will draw ONLY the key poses. Inbetweens are geometric interpolation of the same named parts — the drawer will not see them.
You pick a few extremes, not a full frame list. YOU choose how many keys: at least 2, at most 6. Two keys is enough when the motion is one continuous travel with no topology change. Add a key only when interpolation cannot invent that beat (contact, detach, a new silhouette). Do not pad with near-duplicate poses. Never output grid cells like x12y20, never numeric coordinates.
Sports scale: people 1/4–1/3 of the canvas tall; leave a lane for the ball; props in proportion to the person (not tiny ants, not filling the page).

Always include a start pose and an end pose. Insert extra keys only for beats interpolation cannot invent.
First rewrite the user prompt into "action": a detailed, practical shot a drawer can follow (4–8 sentences). Cover who is on screen and where they stand (canvas fractions), what travels, beat order in time, which contact/detach interpolation cannot invent, and what does NOT happen. Be physically reasonable for a sparse stick sketch on a 50x50 grid. No grid cells. Then pick keys that realize THAT action — not a different story.
Around 12 frames is a good default clip length, not a quota: the real length is keys + all n_inbetween. Do not pad or cut gaps just to hit 12.
Inbetween counts should follow how far the MOVING part travels (weapon tip on a swing, flying shuttle), not leftover frames dumped after the hit.
Use the same ease on both halves of a swing so the speed does not flip after contact.
Mark each part "motion": "moving" or "anchored". Ground and scenery are anchored; bodies, heads, limbs, and props are moving.
Identity vs motion: anything that must stay the same — head size and shape, body build, limb length, who is who — must be written as UNCHANGING (same size, same proportions on every key). Do not restyle a character between keys.
Encourage readable motion: moving parts SHOULD change pose. Prefer a weight shift, a swinging arm, a step, or a traveling prop. One clear action, not a busy mix of jumps, spins, and extras. Do not freeze a whole person unless they are scenery; parked feet can still shift weight and swing an arm.

{ANIM_LAWS}"""


KEY_PLAN_SYSTEM_ANIMAL = f"""You are a sketch planner for pose-to-pose mammal animation.
Return JSON only. No markdown.

A drawer will draw ONLY the key poses as ellipse-body + circle-head mammal sketches (not stick people). Inbetweens are geometric interpolation of the same named parts — the drawer will not see them.
You pick a few extremes, not a full frame list. YOU choose how many keys: at least 2, at most 6. Two keys is enough when the motion is one continuous travel with no topology change. Add a key only when interpolation cannot invent that beat (contact, detach, a new silhouette). Do not pad with near-duplicate poses. Never output grid cells like x12y20, never numeric coordinates.

Plan BODY as an ellipse and HEAD as a circle overlapping the upper-front of the body. Then only species signatures (ears, tail, snout, whiskers) and optional short tick-legs. Do not plan a fused bean.

The animal is SMALL: at most about one-third of the canvas wide. Start pose in the LEFT third. End pose in the RIGHT third with empty margin still left at the border. Mid/pass in the center. Interpolation cannot invent travel if the start already fills the canvas.

Always include a start pose and an end pose. Insert extra keys only for beats interpolation cannot invent.
First rewrite the user prompt into "action": a detailed, practical shot a drawer can follow (4–8 sentences). Cover who is on screen and where they stand (canvas fractions), what travels, beat order in time, which contact/detach interpolation cannot invent, and what does NOT happen. Be physically reasonable for a small mammal sketch on a 50x50 grid. No grid cells. Then pick keys that realize THAT action — not a different story.
Around 12 frames is a good default clip length, not a quota: the real length is keys + all n_inbetween. Do not pad or cut gaps just to hit 12.
Inbetween counts should follow how far the MOVING part travels, not leftover frames dumped after the beat.
Use the same ease on both halves of one action so the speed does not flip.
Mark each part "motion": "moving" or "anchored". Ground and scenery are anchored; head, body, ears, tail, and legs are moving.
Identity vs motion: anything that must stay the same — head size and shape, body ellipse, species marks, who is who — must be written as UNCHANGING (same size, same proportions on every key). Do not restyle the animal between keys.
Encourage readable motion: moving parts SHOULD change pose. Prefer travel, a hop, a weight shift, or a wag. One clear action, not a busy mix. Do not freeze the whole animal unless it is scenery.

{ANIM_LAWS}"""


def key_plan_user(
    task: dict,
    n_keys: int | None = None,
    suggested_frames: int | None = None,
    pin_frames: int | None = None,
) -> str:
    n_min, n_max = task.get("part_range", (MIN_PARTS, MAX_PARTS))
    suggested = task.get("suggested_keys")
    schema = task.get("frame_schema", '"notes": "pose"')
    suggested_frames = int(suggested_frames or task.get("target_frames") or 12)
    pin_frames = int(pin_frames) if pin_frames else None
    lo, hi = key_count_bounds(pin_frames)
    pinned = n_keys is not None
    if pinned:
        n_keys = int(n_keys)
        gap_n = n_keys - 1
        inb = max(gap_n, (pin_frames - n_keys) if pin_frames else suggested_frames - n_keys)
        pick = f"Pick exactly {n_keys} keys."
        if suggested:
            pick += f" Suggested beats: {suggested}."
        key_rule = f"- keys length must be {n_keys}. First key is the start, last key is the end.\n- gaps length must be {gap_n}, one after each key except the last.\n"
        example_inb = max(1, inb // max(gap_n, 1))
    else:
        pick = (
            f"YOU choose how many keys: {lo}–{hi}. Two is enough for one continuous travel. "
            f"Add a key only for a beat interpolation cannot invent. Do not pad."
        )
        if suggested:
            pick += f" Suggested beats (a menu, not a required length): {suggested}."
        key_rule = (
            f"- keys length is YOUR choice, {lo}–{hi}. First key is the start, last key is the end.\n"
            "- gaps length must be keys-1, one after each key except the last.\n"
        )
        example_inb = 3
    if pin_frames:
        if pinned:
            need = pin_frames - n_keys
            gap_n = n_keys - 1
            frame_rule = (
                f"- keys + all n_inbetween MUST total {pin_frames} frames "
                f"({n_keys} keys + {need} inbetweens across {gap_n} gaps).\n"
            )
        else:
            frame_rule = (
                f"- keys + all n_inbetween MUST total {pin_frames} frames. "
                f"If you pick K keys, put {pin_frames}-K inbetweens across K-1 gaps "
                f"(each gap 1–10).\n"
            )
    else:
        frame_rule = (
            f"- Around {suggested_frames} frames is the default length, not a quota. "
            f"The real length is keys + all n_inbetween; stay in {MIN_FRAMES}–{MAX_FRAMES}. "
            f"Do not pad or cut gaps just to hit {suggested_frames}.\n"
        )
    timing_hint = ""
    forced = task.get("forced_gaps") or []
    if isinstance(forced, list) and forced and not pin_frames:
        bits = []
        for i, g in enumerate(forced, 1):
            why = (g.get("why") or "").strip()
            bits.append(f"interval {i} ~{int(g.get('n_inbetween', 3))} inbetweens" + (f" ({why})" if why else ""))
        timing_hint = "- Timing hint (optional; change it if your key count differs): " + "; ".join(bits) + ".\n"
    sheet = ""
    sheet_names = task.get("sheet_part_names") or []
    if sheet_names:
        names = ", ".join(sheet_names)
        sheet = (
            f"- Character-sheet parts are FIXED: include ALL of these names in parts[]: {names}. "
            "You may ADD extras (ground, ball, fence, branch, leash, person_*). "
            "Do not rename or drop sheet parts.\n"
        )
    motion = str(task.get("motion_rules") or "").strip()
    motion_block = f"\nMotion:\n{motion}\n" if motion else ""
    return f"""User request: {task['prompt']}
{motion_block}
{pick}

Return JSON:
{{
  "concept": "{task['concept']}",
  "viewpoint": "{task.get('viewpoint', 'side view facing right')}",
  "action": "4-8 sentence rewrite: who, where, beat order, what travels, what pose changes, what stays unchanging (head size/shape, build)",
  "layout_notes": "where the action lives, words and fractions only",
  "parts": [
    {{"id": "s1", "name": "attacker_head", "how": "circle", "motion": "moving", "notes": "same size on every key"}}
  ],
  "keys": [
    {{
      "name": "start",
      "beat": "short beat name",
      {schema}
    }}
  ],
  "gaps": [
    {{
      "after": "start",
      "n_inbetween": {example_inb},
      "ease": "linear|smooth|ease_out",
      "why": "why this many inbetweens"
    }}
  ]
}}

Hard rules:
- "action" is required: a detailed practical rewrite of the user prompt, 4–8 sentences, no cells. Keys must follow it. Say what stays unchanging (head size/shape, build) and what actually moves.
- In parts[].notes, mark identity as unchanging; for moving parts say the simple pose change.
- No cells (xNyM) or coordinates.
- parts {n_min}–{n_max}, same ids on every key. Two-person shots: prefix names attacker_ / victim_ / sword.
{sheet}- Each part has motion "moving" or "anchored". One shared ground if you include a floor; never a ground per person.
- Put more inbetweens on the interval where travel is farthest (usually after hit/detach).
{key_rule}- Each n_inbetween is an integer 1–10.
{frame_rule}{timing_hint}- Include a hit/contact/detach key if the action has one; do not skip it and hope interpolation will create it."""



def key_draw_text(plan: dict, key: dict, key_i: int, n_keys: int) -> str:
    parts = plan.get("parts") or []
    lines = [
        f"Concept: {plan.get('concept', '')}",
        f"Viewpoint: {plan.get('viewpoint', '')}",
        f"Shot: {plan.get('action') or plan.get('layout_notes', '')}",
        f"Staging: {plan.get('layout_notes', '')}",
        f"This is KEY {key_i}/{n_keys} named '{key.get('name')}' (beat: {key.get('beat', '')}).",
        "Inbetweens will be interpolated from your strokes. Draw a clear extreme, not a halfway pose.",
        "MOVING parts must change cells (heads, bodies, limbs, sword, bolt). ANCHORED parts (ground) keep the same cells.",
        "If travel is the point, keep characters SMALL and leave a long empty path for the moving prop.",
        "Same named parts on every key. Choose your own 1–50 cells for moving parts.",
        "",
        "Parts:",
    ]
    for s in parts:
        notes = (s.get("notes") or "").strip()
        motion = (s.get("motion") or "").strip() or (
            "anchored" if any(k in str(s.get("name", "")).lower() for k in ("ground", "floor", "horizon", "court")) else "moving"
        )
        extra = f" {notes}" if notes else ""
        lines.append(f"{s.get('id')} {s.get('name')} ({s.get('how')}, {motion}).{extra}")
    lines += ["", "This key pose:"]
    for k, v in key.items():
        if k in {"name", "i"}:
            continue
        lines.append(f"{k}: {v}")
    return "\n".join(lines)


def key_draw_user(
    task: dict,
    plan_text: str,
    key_name: str,
    prev_xml: str | None,
    asset_xml: str | None = None,
) -> str:
    n_min, n_max = task.get("part_range", (MIN_PARTS, MAX_PARTS))
    prev = ""
    if prev_xml:
        prev = f"""
Previous KEY XML:
- Copy ground / floor / horizon / bench / water / branch / fence strokes with the EXACT same points.
- Do NOT copy the same cells for heads, limbs, or moving props — those must pose this beat.
{prev_xml}
"""
    extra, who = _draw_extra_block(task)
    sheet = ""
    if asset_xml:
        names = ", ".join(task.get("sheet_part_names") or [])
        must = f" Exact <id> strings required: {names}." if names else ""
        sheet = f"""
CHARACTER SHEET (still SketchAgent drawing). Reuse these named strokes. Pose them for this key; do not redraw as a stick person.{must}
Keep the sheet's SIZE — do not scale up. Translate the whole animal together (body+head+signatures).
Start = left third with empty space to the right; later keys move into that space. Never park the snout on the right border.
For a walk, only the tick-legs change angle/placement; head stays above the body.
{asset_xml}
"""
    fmt = STICK_EXAMPLE if not asset_xml else "Use the character sheet above as the format example. Keep ellipse body + circle head."
    house = "" if asset_xml else f"Also legal:\n{HOUSE}\n"
    return f"""Draw the KEY pose '{key_name}' of: {task['concept']}
{task['prompt']}

This drawing is an extreme. Later frames between keys are interpolated, so the beat must be readable in THIS drawing.

Format example:
{fmt}

{extra}
{sheet}
{house}Planner layout for THIS key:
{plan_text}
{prev}
Keep {n_min}–{n_max} strokes. Same part names as the plan. {who}

{xml_tail(task['concept'])}"""

