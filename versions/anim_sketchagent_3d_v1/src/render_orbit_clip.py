#!/usr/bin/env python3
"""Re-render an existing Path3D run with a yaw orbit around world +z.

Default: the action loops while the camera keeps turning. Yaw is 60° per
animation cycle and 360° over the whole GIF, so looping the GIF is seamless
for both the action and the camera. Does not overwrite clip.gif.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = next(
    (parent for parent in HERE.parents if (parent / "versions" / "path3d_v1").exists()),
    HERE.parents[1],
)
for p in (ROOT, ROOT / "versions" / "path3d_v1", HERE):
    sp = str(p)
    if sp in sys.path:
        sys.path.remove(sp)
    sys.path.insert(0, sp)

from path3d.renderer import Camera, DEFAULT_CAMERAS, render_view  # noqa: E402
from path3d.schema import Path3DScene  # noqa: E402

from glm_anim_3d import write_contact_sheet, write_gif  # noqa: E402

PERSPECTIVE = next(cam for cam in DEFAULT_CAMERAS if cam.name == "perspective")


def orbit_camera(
    t: float,
    *,
    base: Camera = PERSPECTIVE,
    yaw_degrees: float = 60.0,
) -> Camera:
    """Yaw `base` around world +z. t=0 is unchanged; t=1 is `yaw_degrees`."""
    t = min(1.0, max(0.0, float(t)))
    x, y, z = base.position
    theta = math.radians(float(yaw_degrees) * t)
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    return Camera(
        name="orbit",
        position=(x * cos_t - y * sin_t, x * sin_t + y * cos_t, z),
        target=base.target,
        up=base.up,
        focal=base.focal,
        projection=base.projection,
    )


def camera_at_yaw(yaw_degrees: float, *, base: Camera = PERSPECTIVE) -> Camera:
    return orbit_camera(1.0 if yaw_degrees else 0.0, base=base, yaw_degrees=yaw_degrees)


def loop_counts(n_scene: int, *, degrees_per_cycle: float = 60.0, full_turn: float = 360.0) -> tuple[int, int]:
    loops = max(1, int(round(float(full_turn) / float(degrees_per_cycle))))
    return loops, n_scene * loops


def looping_yaws(n_scene: int, *, degrees_per_cycle: float = 60.0, full_turn: float = 360.0) -> list[float]:
    """Even yaw steps over a closed 360° turn, animation repeating `loops` times."""
    _loops, total = loop_counts(n_scene, degrees_per_cycle=degrees_per_cycle, full_turn=full_turn)
    return [float(full_turn) * i / total for i in range(total)]


def frame_scene_paths(run: Path) -> list[Path]:
    frames_dir = run / "frames"
    if not frames_dir.is_dir():
        raise FileNotFoundError(f"no frames/ in {run}")
    paths = sorted(
        path
        for path in frames_dir.glob("f*/scene.json")
        if path.is_file()
    )
    if not paths:
        raise FileNotFoundError(f"no frames/f*/scene.json in {run}")
    return paths


def render_orbit_clip(
    run: Path,
    *,
    yaw_degrees: float | None = None,
    width: int = 512,
    height: int = 512,
    gif_ms: int | None = None,
    once: bool = False,
) -> dict:
    run = run.resolve()
    scenes = frame_scene_paths(run)
    n = len(scenes)
    summary_path = run / "summary.json"
    if gif_ms is None and summary_path.is_file():
        gif_ms = int(json.loads(summary_path.read_text(encoding="utf-8")).get("gif_ms") or 80)
    gif_ms = int(gif_ms or 80)

    orbit_dir = run / "orbit_frames"
    if orbit_dir.exists():
        shutil.rmtree(orbit_dir)
    orbit_dir.mkdir(parents=True)

    pngs: list[Path] = []
    cameras: list[dict] = []
    labels: list[str] = []

    if once:
        degrees = 60.0 if yaw_degrees is None else float(yaw_degrees)
        loops = 1
        yaws = [0.0] if n == 1 else [degrees * i / (n - 1) for i in range(n)]
        schedule = [(i, scenes[i], yaws[i]) for i in range(n)]
    else:
        degrees = 60.0 if yaw_degrees is None else float(yaw_degrees)
        loops, total = loop_counts(n, degrees_per_cycle=degrees)
        yaws = looping_yaws(n, degrees_per_cycle=degrees)
        schedule = [(i, scenes[i % n], yaws[i]) for i in range(total)]

    loaded: dict[Path, Path3DScene] = {}
    for i, scene_path, yaw in schedule:
        if scene_path not in loaded:
            loaded[scene_path] = Path3DScene.from_dict(json.loads(scene_path.read_text(encoding="utf-8")))
        camera = camera_at_yaw(yaw)
        out_png = orbit_dir / f"f{i + 1:03d}.png"
        render_view(
            loaded[scene_path],
            camera,
            out_png,
            width=width,
            height=height,
            normalize=False,
        )
        pngs.append(out_png)
        anim_i = (i % n) + 1
        labels.append(f"f{anim_i}")
        cameras.append(
            {
                "frame": i + 1,
                "anim_frame": anim_i,
                "cycle": i // n,
                "t": yaw / 360.0 if not once else (0.0 if n == 1 else i / (n - 1)),
                "yaw_degrees": yaw,
                "position": list(camera.position),
            }
        )

    gif = run / "clip_orbit.gif"
    sheet = run / "contact_sheet_orbit.png"
    write_gif(pngs, gif, duration_ms=gif_ms, labels=labels)
    write_contact_sheet(pngs, sheet, labels=labels)
    meta = {
        "ok": True,
        "run": str(run),
        "n_scene_frames": n,
        "n_frames": len(pngs),
        "anim_loops": loops,
        "once": once,
        "degrees_per_cycle": degrees,
        "yaw_degrees": yaws[-1] if once else 360.0,
        "loop_yaw": not once,
        "axis": "+z",
        "base_camera": list(PERSPECTIVE.position),
        "gif_ms": gif_ms,
        "gif": str(gif),
        "contact_sheet": str(sheet),
        "cameras": cameras,
    }
    (run / "orbit.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Orbit-render an existing Path3D clip around +z")
    parser.add_argument("--run", type=Path, action="append", required=True, help="output folder with frames/f*/scene.json")
    parser.add_argument(
        "--degrees",
        type=float,
        default=None,
        help="yaw per animation cycle (looping, default 60) or total yaw with --once",
    )
    parser.add_argument("--once", action="store_true", help="one animation pass, no looping camera turn")
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--height", type=int, default=512)
    args = parser.parse_args(argv)
    for run in args.run:
        meta = render_orbit_clip(
            run,
            yaw_degrees=args.degrees,
            width=args.width,
            height=args.height,
            once=args.once,
        )
        print(
            f"wrote {meta['gif']} frames={meta['n_frames']} "
            f"loops={meta['anim_loops']} yaw_end={meta['cameras'][-1]['yaw_degrees']:.1f}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
