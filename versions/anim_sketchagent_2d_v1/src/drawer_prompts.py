"""Drawer chat prompts for SketchAgent GRPO (thinking off, no grid image)."""
from __future__ import annotations

SYSTEM = """You are an expert artist drawing sparse black-line sketches on a 50x50 grid.
Origin top-left: x right, y down. Cells are 'x1y1' ... 'x50y50'. Never use Cartesian bottom-left coordinates.
Output SketchAgent XML only. No markdown fences, no <thinking> tags.
For characters and animals: pleasing silhouette, two short vertical-line eyes by default, no circular pupils.
Prefer a coordinated simple drawing over crowded detail. Hand-drawn looseness is good; scattered broken parts are not.
Ellipses = two connecting arcs. Circles close by repeating the start cell. Corners may duplicate a cell with adjacent t.
Each <points> length must equal <t_values>. t starts at 0.00 and ends at 1.00.
Primitive recipes: copy the geometry, not the cells. Circle = 8 compass points + start cell, even t. Ellipse = two connecting arcs. Rectangle/triangle = polyline with duplicated corner cells."""

HOUSE = """<example>
<concept>House</concept>
<strokes>
    <s1>
        <points>'x13y24', 'x24y24', 'x24y24', 'x24y40', 'x24y40', 'x13y40', 'x13y40', 'x13y24'</points>
        <t_values>0.00,0.3,0.25,0.5,0.5,0.75,0.75,1.00</t_values>
        <id>house base</id>
    </s1>
    <s2>
        <points>'x13y24', 'x18y14', 'x18y14', 'x24y24'</points>
        <t_values>0.00,0.55,0.5,1.00</t_values>
        <id>roof</id>
    </s2>
</strokes>
</example>"""

CIRCLE = """<example>
<concept>Circle</concept>
<strokes>
    <s1>
        <points>'x25y17', 'x31y19', 'x33y25', 'x31y31', 'x25y33', 'x19y31', 'x17y25', 'x19y19', 'x25y17'</points>
        <t_values>0.00,0.125,0.25,0.375,0.50,0.625,0.75,0.875,1.00</t_values>
        <id>circle</id>
    </s1>
</strokes>
</example>"""

TRIANGLE = """<example>
<concept>Triangle</concept>
<strokes>
    <s1>
        <points>'x25y14', 'x34y36', 'x34y36', 'x16y36', 'x16y36', 'x25y14'</points>
        <t_values>0.00,0.33,0.33,0.67,0.67,1.00</t_values>
        <id>triangle</id>
    </s1>
</strokes>
</example>"""

RECTANGLE = """<example>
<concept>Rectangle</concept>
<strokes>
    <s1>
        <points>'x16y20', 'x34y20', 'x34y20', 'x34y36', 'x34y36', 'x16y36', 'x16y36', 'x16y20'</points>
        <t_values>0.00,0.25,0.25,0.50,0.50,0.75,0.75,1.00</t_values>
        <id>rectangle</id>
    </s1>
</strokes>
</example>"""

ELLIPSE = """<example>
<concept>Ellipse</concept>
<strokes>
    <s1>
        <points>'x16y25', 'x18y20', 'x25y17', 'x32y20', 'x34y25'</points>
        <t_values>0.00,0.25,0.50,0.75,1.00</t_values>
        <id>ellipse top arc</id>
    </s1>
    <s2>
        <points>'x34y25', 'x32y30', 'x25y33', 'x18y30', 'x16y25'</points>
        <t_values>0.00,0.25,0.50,0.75,1.00</t_values>
        <id>ellipse bottom arc</id>
    </s2>
</strokes>
</example>"""

LINE = """<example>
<concept>Line</concept>
<strokes>
    <s1>
        <points>'x25y16', 'x25y36'</points>
        <t_values>0.00,1.00</t_values>
        <id>vertical rod</id>
    </s1>
</strokes>
</example>"""

SHAPE_EXAMPLES = f"""Shape format examples (copy the geometry, pick your own cells):
{CIRCLE}

{TRIANGLE}

{RECTANGLE}

{ELLIPSE}

{LINE}

Composition example:
{HOUSE}"""


def plan_text(plan: dict) -> str:
    """Format a frozen plan for the drawer. Prefers coarse regions over cell traces."""
    lines = [
        f"Concept: {plan.get('concept', '')}",
        f"Viewpoint: {plan.get('viewpoint', '')}",
        f"Layout: {plan.get('layout_notes', '')}",
        "Follow this stroke order loosely. Choose your own 1–50 cells; do not copy a tracing template.",
        "",
    ]
    for s in plan.get("strokes") or []:
        region = (s.get("region") or "").strip()
        notes = (s.get("notes") or "").strip()
        if region:
            extra = f" {notes}" if notes else ""
            lines.append(f"{s.get('id')} {s.get('name')} ({s.get('how')}): {region}.{extra}")
            continue
        pts = ", ".join(s.get("approx_points") or [])
        lines.append(
            f"{s.get('id')} {s.get('name')} ({s.get('how')}): points [{pts}]; "
            f"t_values {s.get('t_hint')}. {notes}"
        )
    return "\n".join(lines)


PLAN_DRAW_SYSTEM = """You are an expert artist drawing sparse black-line sketches on a 50x50 grid.
Origin top-left: x right, y down. Cells are 'x1y1' ... 'x50y50'. Never use Cartesian bottom-left coordinates.
No markdown fences, no <thinking> tags.
For characters and animals: pleasing silhouette, two short vertical-line eyes by default, no circular pupils.
Prefer a coordinated simple drawing over crowded detail. Hand-drawn looseness is good; scattered broken parts are not.
Ellipses = two connecting arcs. Circles close by repeating the start cell. Corners may duplicate a cell with adjacent t.
Each <points> length must equal <t_values>. t starts at 0.00 and ends at 1.00.
A circle uses 8 compass points plus the start cell again, with even t (0, 0.125, …, 1.00). The join should be smooth, not a sharp crease.

Work in two parts in one reply:
1) A coarse <plan> JSON. Structure only: words and fractions, never grid cells like x12y20, never numeric coordinates.
2) Then the SketchAgent XML drawing that follows that plan."""


def xml_tail(concept: str) -> str:
    return f"""Output exactly:
<answer>
<concept>{concept}</concept>
<strokes>
    <s1>
        <points>'x..y..', ...</points>
        <t_values>0.00,...,1.00</t_values>
        <id>short name</id>
    </s1>
</strokes>
</answer>
"""


def plan_draw_user_prompt(task: dict) -> str:
    reqs = "; ".join(r["description"] for r in task.get("requirements") or [])
    return f"""Draw a visually appealing black-line sketch of: {task['concept']}
{task['prompt']}
Must communicate: {reqs}

First write a coarse plan (6–12 strokes). Then draw.
Plan rules: no cells (xNyM), no coordinates, no t_values. Regions in words/fractions only.

XML format examples (after the plan):
{SHAPE_EXAMPLES}

Output exactly:
<plan>
{{
  "concept": "{task['concept']}",
  "viewpoint": "short viewpoint",
  "layout_notes": "where the subject sits, words and fractions only",
  "strokes": [
    {{
      "id": "s1",
      "name": "part name",
      "how": "circle|ellipse_two_arcs|line|zigzag|corner_polyline|curve",
      "region": "e.g. upper center; about one-fifth of the canvas tall",
      "notes": "shape/pose hint only, no coordinates"
    }}
  ]
}}
</plan>
<answer>
<concept>{task['concept']}</concept>
<strokes>
    <s1>
        <points>'x..y..', ...</points>
        <t_values>0.00,...,1.00</t_values>
        <id>short name</id>
    </s1>
</strokes>
</answer>
"""


SYSTEM_BARE = """You are an expert artist drawing sparse black-line sketches on a 50x50 grid.
Origin top-left: x right, y down. Cells are 'x1y1' ... 'x50y50'. Never use Cartesian bottom-left coordinates.
Output SketchAgent XML only. No markdown fences, no <thinking> tags.
For characters and animals: pleasing silhouette, two short vertical-line eyes by default, no circular pupils.
Prefer a coordinated simple drawing over crowded detail. Hand-drawn looseness is good; scattered broken parts are not.
Ellipses = two connecting arcs. Circles close by repeating the start cell. Corners may duplicate a cell with adjacent t.
Each <points> length must equal <t_values>. t starts at 0.00 and ends at 1.00."""

SYSTEM_TEXT_RECIPE = SYSTEM_BARE + """
Circle recipe in words (copy the geometry, pick your own cells): eight compass points plus the start cell again, even t 0, 0.125, ..., 1.00. The join should be smooth.
Lamp shades, cones, and cups stay open: an opening rim, not a closed ellipse blob.
"""

PLAN_SYSTEM_SHADE = """You are a sketch planner for sparse black-line drawings.
Return JSON only. No markdown.

The drawer is a separate model. You give STRUCTURE, not a tracing template.
Never output grid cells like x12y20, never list numeric coordinates, never give pixel positions.
Describe regions in words: top / middle / bottom, left / center / right, and rough fractions of the canvas
(e.g. "head occupies the upper fifth, roughly centered").

Keep 6–12 strokes. Cute simple silhouette over completeness.
Characters/animals: two short vertical-line eyes if the face shows; no circular pupils.
Ellipses = two connecting arcs (two stroke entries). Circles close. One stroke per rod for parallel parts.
Joints may be slightly loose; do not CAD-snap.
Lamp shades, cones, funnels, and hats: describe an OPEN silhouette (top/back/rim/front), never a closed ellipse for the shade."""

CIRCLE_SNIP = f"""Circle stroke snippet (copy the even-t close; pick your own cells):
{CIRCLE}

Composition example:
{HOUSE}"""

HOUSE_ONLY = f"""Format example:
{HOUSE}"""

_PLAN_SYSTEM_DEFAULT = """You are a sketch planner for sparse black-line drawings.
Return JSON only. No markdown.

The drawer is a separate model. You give STRUCTURE, not a tracing template.
Never output grid cells like x12y20, never list numeric coordinates, never give pixel positions.
Describe regions in words: top / middle / bottom, left / center / right, and rough fractions of the canvas
(e.g. "head occupies the upper fifth, roughly centered").

Keep 6–12 strokes. Cute simple silhouette over completeness.
Characters/animals: two short vertical-line eyes if the face shows; no circular pupils.
Ellipses = two connecting arcs (two stroke entries). Circles close. One stroke per rod for parallel parts.
Joints may be slightly loose; do not CAD-snap."""


def user_prompt_with_examples(task: dict, plan: str, examples: str) -> str:
    return f"""Draw a visually appealing black-line sketch of: {task['concept']}
{task['prompt']}

{examples}

Planner layout (coarse regions only; you may loosen cells for a hand-drawn look):
{plan}

{xml_tail(task['concept'])}"""


PROMPT_PACKS = {
    "A_house": {
        "plan_system": _PLAN_SYSTEM_DEFAULT,
        "draw_system": SYSTEM_BARE,
        "examples": HOUSE_ONLY,
    },
    "B_circle_snip": {
        "plan_system": _PLAN_SYSTEM_DEFAULT,
        "draw_system": SYSTEM_BARE,
        "examples": CIRCLE_SNIP,
    },
    "C_gallery": {
        "plan_system": _PLAN_SYSTEM_DEFAULT,
        "draw_system": SYSTEM,
        "examples": SHAPE_EXAMPLES,
    },
    "D_text_recipe": {
        "plan_system": PLAN_SYSTEM_SHADE,
        "draw_system": SYSTEM_TEXT_RECIPE,
        "examples": HOUSE_ONLY,
    },
}

# Frozen after prompt search (lamp veto; A beat B/C/D on composition).
ACTIVE_PACK = "A_house"


def apply_pack(name: str) -> dict:
    pack = PROMPT_PACKS[name]
    global SYSTEM, PLAN_SYSTEM_ACTIVE, ACTIVE_PACK
    ACTIVE_PACK = name
    SYSTEM = pack["draw_system"]
    PLAN_SYSTEM_ACTIVE = pack["plan_system"]
    return pack


PLAN_SYSTEM_ACTIVE = PROMPT_PACKS[ACTIVE_PACK]["plan_system"]


def user_prompt(task: dict, plan: str) -> str:
    examples = PROMPT_PACKS[ACTIVE_PACK]["examples"]
    return user_prompt_with_examples(task, plan, examples)


def direct_user_prompt(task: dict) -> str:
    reqs = "; ".join(r["description"] for r in task.get("requirements") or [])
    return f"""Draw a visually appealing black-line sketch of: {task['concept']}
{task['prompt']}
Must communicate: {reqs}

No external planner. Decide viewpoint, parts, and placement yourself.
Keep 6–12 strokes. Cute simple silhouette. Characters/animals: two short vertical-line eyes, no circular pupils.
Ellipses = two connecting arcs. Circles close. One subject only.

{SHAPE_EXAMPLES}

{xml_tail(task['concept'])}"""
