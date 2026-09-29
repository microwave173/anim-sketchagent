"""One drawing-system builder shared by naive clips and KeyGap intervals."""
from __future__ import annotations

import json
from pathlib import Path

from scene import protocol

HERE = Path(__file__).resolve().parent


def animation_guide(dim: int, size: int) -> str:
    if dim not in (2, 3):
        raise ValueError("dim must be 2 or 3")
    guide = (HERE / "prompts/ANIMATION_GUIDE.md").read_text(encoding="utf-8")
    if dim == 2:
        start = guide.index("## Drawing style")
        end = guide.index("## Show causes before consequences", start)
        guide = guide[:start] + (HERE / "prompts/STYLE_2D.md").read_text(encoding="utf-8") + "\n\n" + guide[end:]
    presentation = json.loads((HERE / "prompts/PRESENTATION_2D.json").read_text(encoding="utf-8"))
    native_size = min(size, presentation["raster_size"])
    if dim == 2:
        target = (f"\nActual drawing target: {native_size}x{native_size} pixels, "
            f"{presentation['stroke_width']}px native ink; smooth antialiased enlargement to {size}x{size}. "
            "Design compact, readable subjects for this small native canvas while keeping moving characters and props modest in the frame. "
            "Reserve an open corridor for the full motion and the final pose; keep complete subjects and decisive contacts readable. "
            "Simplify detail rather than omitting objects. Leave enough space between meaningful lines. "
            "The visible Path2D canvas spans [-1,1], not pixels; off-canvas coordinates are valid but clipped.")
    else:
        target = (f"\nActual projected drawing target: {native_size}x{native_size} pixels, "
            f"{presentation['stroke_width']}px native black ink; smooth antialiased enlargement to {size}x{size}. "
            "Design real 3D geometry while judging its perspective projection at this small native size. "
            "Keep traveling actors and moving props modest in the projected frame, normally 20-35% of frame height, "
            "and reserve open screen and depth space for a large visible displacement and final pose. "
            "Keep contacts readable; simplify secondary wireframe detail rather than enlarging the whole scene. "
            "The primary visible Path3D world spans [-1,1], not pixels; projected off-canvas geometry may be clipped.")
    guide += target
    if dim == 3:
        guide += "\n" + (HERE / "prompts/SPATIAL_3D.md").read_text(encoding="utf-8")
    return guide


def frame_batch_system(dim: int, size: int) -> str:
    """Identical system context for a whole naive clip or one KeyGap interval."""
    return (animation_guide(dim, size) + "\n\n" +
            (HERE / "prompts/FRAME_BATCH.md").read_text(encoding="utf-8") + "\n" + protocol(dim))


def joint_plan_key_system(dim: int, size: int) -> str:
    """One context in which story planning can revise the keys, and vice versa."""
    guide = animation_guide(dim, size)
    guide = guide.replace("Use the identity reference for appearance and the preceding frames for current pose and position. ", "")
    guide = guide.replace("Preserve the storyboard's camera plan.", "Choose and preserve one coherent camera plan.")
    continuation = guide.find("## Continue across segments")
    if continuation >= 0:
        guide = guide[:continuation].rstrip()
    return (guide + "\n\n" +
            (HERE / "prompts/JOINT_PLAN_KEYS.md").read_text(encoding="utf-8") +
            "\n\n" + protocol(dim))
