from html import escape
from .schema import Sketch


def render_svg(sketch: Sketch) -> str:
    hand_drawn = sketch.metadata.get("style") == "hand_drawn"
    stroke_joins = ' stroke-linecap="round" stroke-linejoin="round"' if hand_drawn else ""
    groups: dict[str, list] = {}
    for stroke in sketch.strokes:
        groups.setdefault(stroke.group, []).append(stroke)
    body: list[str] = []
    for group, strokes in groups.items():
        body.append(f'<g id="{escape(group)}">')
        for s in strokes:
            body.append(
                f'<path id="{escape(s.id)}" d="{escape(s.path)}" '
                f'fill="{escape(s.fill)}" stroke="{escape(s.stroke)}" '
                f'stroke-width="{s.stroke_width:g}" opacity="{s.opacity:g}" '
                f'data-description="{escape(s.description)}"{stroke_joins} />'
            )
        body.append("</g>")
    return '\n'.join([
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{sketch.width}" height="{sketch.height}" viewBox="0 0 {sketch.width} {sketch.height}">',
        *body,
        "</svg>",
    ])
