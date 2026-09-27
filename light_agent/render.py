"""Preview artifacts; 3D renders only the perspective camera."""
from __future__ import annotations

import html
import json
from dataclasses import replace
from pathlib import Path
import tempfile

from PIL import Image, ImageDraw
from scene import Path2DScene, Path3DScene
from path2d.renderer import render_scene
from path3d.renderer import DEFAULT_CAMERAS, render_view


def render_2d_preview(scene, path, size):
    settings = json.loads((Path(__file__).parent / "prompts/PRESENTATION_2D.json").read_text())
    raster = min(size, settings["raster_size"])
    supersample = settings.get("antialias_scale", 1)
    scene = replace(scene, strokes=tuple(replace(s, stroke_width=settings["stroke_width"] * supersample) for s in scene.strokes))
    render_scene(scene, path, width=raster * supersample, height=raster * supersample)
    with Image.open(path) as im:
        result = im.convert("RGB")
        if supersample != 1:
            result = result.resize((raster, raster), resample=Image.Resampling.LANCZOS)
        if raster != size:
            method = {"nearest": Image.Resampling.NEAREST, "bicubic": Image.Resampling.BICUBIC}[settings["resize"]]
            result = result.resize((size, size), resample=method)
    result.save(path)


def export(frames: dict[int, dict], out: Path, dim: int, frame_ms: int, size: int, prompt: str):
    images = []
    with tempfile.TemporaryDirectory(prefix="anim_light_") as tmp:
        for index, frame in sorted(frames.items()):
            path = Path(tmp) / f"{index}.png"
            if dim == 2:
                render_2d_preview(Path2DScene.from_dict(frame, prompt=prompt), path, size)
            else:
                camera = next(c for c in DEFAULT_CAMERAS if c.name == "perspective")
                render_view(Path3DScene.from_dict(frame, prompt=prompt), camera, path,
                            width=size, height=size, normalize=False)
            with Image.open(path) as image:
                images.append(image.convert("RGB"))
    images[0].save(out / "clip.gif", save_all=True, append_images=images[1:], duration=frame_ms, loop=0, optimize=False)
    if dim == 2:
        settings = json.loads((Path(__file__).parent / "prompts/PRESENTATION_2D.json").read_text())
        (out / "presentation.json").write_text(json.dumps({**settings, "output_size": size,
            "actual_raster_size": min(size, settings["raster_size"]), "geometry_modified": False}, indent=2) + "\n")
    thumb, cols = 160, 8
    sheet = Image.new("RGB", (cols * thumb, ((len(images) + cols - 1) // cols) * (thumb + 20)), "white")
    draw = ImageDraw.Draw(sheet)
    for i, image in enumerate(images):
        x, y = (i % cols) * thumb, (i // cols) * (thumb + 20)
        sheet.paste(image.resize((thumb, thumb)), (x, y))
        draw.text((x + 4, y + thumb + 3), f"frame {i + 1}", fill="black")
    sheet.save(out / "contact_sheet.jpg", quality=92)
    title = html.escape(prompt)
    (out / "index.html").write_text(f'''<!doctype html><meta charset="utf-8"><title>Anim Agent Light V2</title>
<style>body{{font:16px system-ui;max-width:1200px;margin:30px auto;padding:20px;background:#eee}}img{{background:white;max-width:100%}}.clip{{width:min(780px,100%)}}pre{{white-space:pre-wrap}}</style>
<h1>Anim Agent Light V2 · {dim}D · {len(images)} frames</h1><p>{title}</p>
<img class="clip" src="clip.gif"><p><a href="storyboard.md">Storyboard</a> · <a href="metrics.json">Timings</a> · <a href="animation.json">Geometry</a></p>
<img src="contact_sheet.jpg"><pre id="metrics"></pre><script>fetch('metrics.json').then(r=>r.json()).then(v=>document.getElementById('metrics').textContent=JSON.stringify(v,null,2)).catch(()=>{{}})</script>''', encoding="utf-8")
