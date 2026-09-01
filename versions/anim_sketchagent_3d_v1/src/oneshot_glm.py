"""Single-shot Path3D generation with gpt-5.6-sol (no separate vision model)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = next(
    (parent for parent in HERE.parents if (parent / "versions" / "path3d_v1").exists()),
    HERE.parents[1],
)
for p in (ROOT, ROOT / "versions" / "path3d_v1", ROOT / "experiments" / "grpo_sa_pilot"):
    sp = str(p)
    if sp in sys.path:
        sys.path.remove(sp)
    sys.path.insert(0, sp)
if str(HERE) in sys.path:
    sys.path.remove(str(HERE))
sys.path.insert(0, str(HERE))

from path3d.generator import SYSTEM_PROMPT  # noqa: E402
from path3d.parser import parse_path3d  # noqa: E402
from path3d.renderer import render_scene_views  # noqa: E402
from path3d.schema import Path3DScene  # noqa: E402
from terra_client import call_sol, parse_json_obj  # noqa: E402


def generate_scene(user_content: str, *, extra_system: str = "") -> tuple[Path3DScene, str]:
    last_raw, last_err = "", None
    system = SYSTEM_PROMPT + (f"\n{extra_system}" if extra_system else "")
    for attempt in range(1, 3):
        raw = call_sol(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
            max_tokens=5000,
            temperature=0.4,
            timeout=240,
        )
        last_raw = raw
        try:
            scene = Path3DScene.from_dict(parse_json_obj(raw), prompt=user_content[:240])
            for stroke in scene.strokes:
                parse_path3d(stroke.path)
            return scene, raw
        except Exception as exc:
            last_err = exc
            user_content = (
                "Repair the JSON below so it is one valid Path3D scene "
                '(keys: prompt, strokes with id/path/description). Return JSON only.\n'
                f"{raw[:12000]}"
            )
            time.sleep(1)
    raise ValueError(f"one-shot Path3D failed: {last_err}") from last_err


def render_scene(
    scene: Path3DScene,
    out_dir: Path,
    *,
    width: int = 512,
    height: int = 512,
    normalize: bool = True,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "scene.json").write_text(scene.to_json(), encoding="utf-8")
    paths = render_scene_views(
        scene,
        out_dir / "views",
        width=width,
        height=height,
        normalize=normalize,
    )
    return {
        "scene": str(out_dir / "scene.json"),
        "views": [str(p) for p in paths],
        "contact_sheet": str(out_dir / "views" / "contact_sheet.png"),
        "perspective": str(out_dir / "views" / "view_perspective.png"),
        "stroke_count": len(scene.strokes),
    }
