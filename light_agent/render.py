"""Preview artifacts; 3D renders only the perspective camera."""
from __future__ import annotations

import html
import json
from dataclasses import replace
from pathlib import Path
import tempfile

from PIL import Image, ImageDraw
from scene import Path2DScene, Path3DScene, SVG_STROKE
from path2d.renderer import render_scene
from path3d.geometry import sample_stroke
from path3d.renderer import DEFAULT_CAMERAS, _project, render_view


def render_2d_preview(scene, path, size):
    settings = json.loads((Path(__file__).parent / "prompts/PRESENTATION_2D.json").read_text())
    raster = min(size, settings["raster_size"])
    supersample = settings.get("antialias_scale", 1)
    scene = replace(scene, strokes=tuple(replace(
        s, stroke=SVG_STROKE, stroke_width=settings["stroke_width"] * supersample, opacity=1.0
    ) for s in scene.strokes))
    render_scene(scene, path, width=raster * supersample, height=raster * supersample)
    with Image.open(path) as im:
        result = im.convert("RGB")
        if supersample != 1:
            result = result.resize((raster, raster), resample=Image.Resampling.LANCZOS)
        if raster != size:
            method = {"nearest": Image.Resampling.NEAREST, "bicubic": Image.Resampling.BICUBIC}[settings["resize"]]
            result = result.resize((size, size), resample=method)
    result.save(path)


def render_3d_preview(scene, path, size):
    settings = json.loads((Path(__file__).parent / "prompts/PRESENTATION_2D.json").read_text())
    raster = min(size, settings["raster_size"])
    scene = replace(scene, strokes=tuple(replace(
        s, stroke=SVG_STROKE, stroke_width=settings["stroke_width"], opacity=1.0
    ) for s in scene.strokes))
    camera = next(c for c in DEFAULT_CAMERAS if c.name == "perspective")
    render_view(scene, camera, path, width=raster, height=raster, normalize=False)
    with Image.open(path) as image:
        result = image.convert("RGB")
        if raster != size:
            method = {"nearest": Image.Resampling.NEAREST,
                      "bicubic": Image.Resampling.BICUBIC}[settings["resize"]]
            result = result.resize((size, size), resample=method)
    result.save(path)


def _svg_paths(frame: dict, *, prefix: str = "") -> str:
    rows = []
    for stroke in frame["strokes"]:
        part_id = str(stroke["id"])
        element_id = prefix + part_id
        description = str(stroke["description"])
        d = str(stroke["path"])
        rows.append(
            f'<path id="{html.escape(element_id, quote=True)}" '
            f'data-part-id="{html.escape(part_id, quote=True)}" '
            f'data-description="{html.escape(description, quote=True)}" '
            f'd="{html.escape(d, quote=True)}" vector-effect="non-scaling-stroke">'
            f'<title>{html.escape(description)}</title></path>'
        )
    return "\n".join(rows)


def _svg_shell(body: str, size: int, stroke_width: float, extra: str = "") -> str:
    # The expanded viewBox exactly matches the raster renderer's 8% margin.
    edge = 1.0 / (1.0 - 2.0 * 0.08)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
            f'viewBox="{-edge:.8f} {-edge:.8f} {2*edge:.8f} {2*edge:.8f}" '
            f'role="img">\n{extra}'
            f'<rect x="{-edge:.8f}" y="{-edge:.8f}" width="{2*edge:.8f}" height="{2*edge:.8f}" fill="#ffffff"/>\n'
            f'<g transform="scale(1 -1)" fill="none" stroke="{SVG_STROKE}" '
            f'stroke-width="{stroke_width:g}" stroke-linecap="round" stroke-linejoin="round">\n'
            f'{body}\n</g>\n</svg>\n')


def export_svg(frames: dict[int, dict], out: Path, frame_ms: int, size: int, prompt: str):
    settings = json.loads((Path(__file__).parent / "prompts/PRESENTATION_2D.json").read_text())
    raster = min(size, settings["raster_size"])
    stroke_width = settings["stroke_width"] * size / raster
    svg_dir = out / "frames_svg"
    svg_dir.mkdir(exist_ok=True)
    ordered = sorted(frames.items())
    for index, frame in ordered:
        title = f'<title>{html.escape(prompt)} — frame {index}</title>\n'
        document = _svg_shell(_svg_paths(frame), size, stroke_width, title)
        (svg_dir / f"frame_{index:04d}.svg").write_text(document, encoding="utf-8")

    count = len(ordered)
    duration = count * frame_ms / 1000.0
    rules = [".frame{opacity:0}"]
    groups = []
    epsilon = min(0.001, 25.0 / count)
    for position, (index, frame) in enumerate(ordered):
        start = position * 100.0 / count
        end = (position + 1) * 100.0 / count
        before = max(0.0, start - epsilon)
        after = min(100.0, end - epsilon)
        stops = (f"0%,{before:.6f}%{{opacity:0}}{start:.6f}%,{after:.6f}%{{opacity:1}}"
                 f"{end:.6f}%,100%{{opacity:0}}")
        rules.append(f".frame-{index}{{animation:frame-{index} {duration:g}s steps(1,end) infinite}}")
        rules.append(f"@keyframes frame-{index}{{{stops}}}")
        groups.append(f'<g id="frame-{index}" class="frame frame-{index}" data-frame="{index}">\n'
                      f'{_svg_paths(frame, prefix=f"f{index}_")}\n</g>')
    extra = (f'<title>{html.escape(prompt)}</title>\n'
             f'<metadata>frame-count={count}; frame-ms={frame_ms}; fixed-black-stroke=true</metadata>\n'
             f'<style>{"".join(rules)}</style>\n')
    (out / "animation.svg").write_text(
        _svg_shell("\n".join(groups), size, stroke_width, extra), encoding="utf-8")


def _projected_svg_paths(scene, camera, size: int, *, prefix: str = "") -> str:
    layers = []
    for stroke in scene.strokes:
        commands, depths = [], []
        for line in sample_stroke(stroke).polylines:
            pixels, line_depths = _project(line, camera, size, size, 0.12)
            commands.append("M " + " L ".join(f"{x:.4f} {y:.4f}" for x, y in pixels))
            depths.extend(float(value) for value in line_depths)
        part_id = str(stroke.id)
        description = str(stroke.description)
        element_id = prefix + part_id
        d = " ".join(commands)
        element = (f'<path id="{html.escape(element_id, quote=True)}" '
                   f'data-part-id="{html.escape(part_id, quote=True)}" '
                   f'data-description="{html.escape(description, quote=True)}" '
                   f'd="{html.escape(d, quote=True)}" vector-effect="non-scaling-stroke">'
                   f'<title>{html.escape(description)}</title></path>')
        layers.append((sum(depths) / len(depths), element))
    return "\n".join(element for _, element in sorted(layers, reverse=True))


def _pixel_svg_shell(body: str, size: int, stroke_width: float, extra: str = "") -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
            f'viewBox="0 0 {size} {size}" role="img">\n{extra}'
            f'<rect width="{size}" height="{size}" fill="#ffffff"/>\n'
            f'<g fill="none" stroke="{SVG_STROKE}" stroke-width="{stroke_width:g}" '
            f'stroke-linecap="round" stroke-linejoin="round">\n{body}\n</g>\n</svg>\n')


def export_projected_3d_svg(frames: dict[int, dict], out: Path, frame_ms: int,
                            size: int, prompt: str):
    settings = json.loads((Path(__file__).parent / "prompts/PRESENTATION_2D.json").read_text())
    raster = min(size, settings["raster_size"])
    stroke_width = settings["stroke_width"] * size / raster
    camera = next(c for c in DEFAULT_CAMERAS if c.name == "perspective")
    svg_dir = out / "frames_svg"
    svg_dir.mkdir(exist_ok=True)
    ordered = [(index, Path3DScene.from_dict(frame, prompt=prompt))
               for index, frame in sorted(frames.items())]
    for index, scene in ordered:
        extra = (f'<title>{html.escape(prompt)} — perspective frame {index}</title>\n'
                 f'<metadata>source=Path3D; camera=perspective; projection=perspective</metadata>\n')
        document = _pixel_svg_shell(
            _projected_svg_paths(scene, camera, size), size, stroke_width, extra)
        (svg_dir / f"frame_{index:04d}.svg").write_text(document, encoding="utf-8")

    count = len(ordered)
    duration = count * frame_ms / 1000.0
    rules = [".frame{opacity:0}"]
    groups = []
    epsilon = min(0.001, 25.0 / count)
    for position, (index, scene) in enumerate(ordered):
        start, end = position * 100.0 / count, (position + 1) * 100.0 / count
        before, after = max(0.0, start - epsilon), min(100.0, end - epsilon)
        stops = (f"0%,{before:.6f}%{{opacity:0}}{start:.6f}%,{after:.6f}%{{opacity:1}}"
                 f"{end:.6f}%,100%{{opacity:0}}")
        rules.append(f".frame-{index}{{animation:frame-{index} {duration:g}s steps(1,end) infinite}}")
        rules.append(f"@keyframes frame-{index}{{{stops}}}")
        groups.append(f'<g id="frame-{index}" class="frame frame-{index}" data-frame="{index}">\n'
                      f'{_projected_svg_paths(scene, camera, size, prefix=f"f{index}_")}\n</g>')
    extra = (f'<title>{html.escape(prompt)} — perspective projection</title>\n'
             f'<metadata>source=Path3D; camera=perspective; frame-count={count}; '
             f'frame-ms={frame_ms}; fixed-black-stroke=true</metadata>\n'
             f'<style>{"".join(rules)}</style>\n')
    (out / "animation.svg").write_text(
        _pixel_svg_shell("\n".join(groups), size, stroke_width, extra), encoding="utf-8")


def export(frames: dict[int, dict], out: Path, dim: int, frame_ms: int, size: int, prompt: str):
    images = []
    with tempfile.TemporaryDirectory(prefix="anim_light_") as tmp:
        for index, frame in sorted(frames.items()):
            path = Path(tmp) / f"{index}.png"
            if dim == 2:
                render_2d_preview(Path2DScene.from_dict(frame, prompt=prompt), path, size)
            else:
                render_3d_preview(Path3DScene.from_dict(frame, prompt=prompt), path, size)
            with Image.open(path) as image:
                images.append(image.convert("RGB"))
    images[0].save(out / "clip.gif", save_all=True, append_images=images[1:], duration=frame_ms, loop=0, optimize=False)
    if dim == 2:
        export_svg(frames, out, frame_ms, size, prompt)
        svg_source = "native standard SVG path data"
    else:
        export_projected_3d_svg(frames, out, frame_ms, size, prompt)
        svg_source = "perspective projection of Path3D sampled as SVG polylines"
    settings = json.loads((Path(__file__).parent / "prompts/PRESENTATION_2D.json").read_text())
    (out / "presentation.json").write_text(json.dumps({**settings, "dimension": dim,
        "output_size": size, "actual_raster_size": min(size, settings["raster_size"]),
        "geometry_modified": False, "svg": {"source": svg_source, "stroke": SVG_STROKE,
        "stroke_width_output_px": settings["stroke_width"] * size / min(size, settings["raster_size"]),
        "fill": "none", "linecap": "round", "linejoin": "round"}}, indent=2) + "\n")
    thumb, cols = 160, 8
    sheet = Image.new("RGB", (cols * thumb, ((len(images) + cols - 1) // cols) * (thumb + 20)), "white")
    draw = ImageDraw.Draw(sheet)
    for i, image in enumerate(images):
        x, y = (i % cols) * thumb, (i // cols) * (thumb + 20)
        sheet.paste(image.resize((thumb, thumb)), (x, y))
        draw.text((x + 4, y + thumb + 3), f"frame {i + 1}", fill="black")
    sheet.save(out / "contact_sheet.jpg", quality=92)
    title = html.escape(prompt)
    storyboard_link = ' · <a href="storyboard.md">Storyboard</a>' if (out / "storyboard.md").exists() else ''
    (out / "index.html").write_text(f'''<!doctype html><meta charset="utf-8"><title>Anim Agent Light V2</title>
<style>body{{font:16px system-ui;max-width:1200px;margin:30px auto;padding:20px;background:#eee}}img{{background:white;max-width:100%}}.clip{{width:min(780px,100%)}}pre{{white-space:pre-wrap}}</style>
<h1>Anim Agent Light V2 · {dim}D · {len(images)} frames</h1><p>{title}</p>
<img class="clip" src="clip.gif"><p><a href="animation.svg">Animated SVG</a> · <a href="frames_svg/">SVG frames</a>{storyboard_link} · <a href="metrics.json">Timings</a> · <a href="animation.json">Geometry</a></p>
<img src="contact_sheet.jpg"><pre id="metrics"></pre><script>fetch('metrics.json').then(r=>r.json()).then(v=>document.getElementById('metrics').textContent=JSON.stringify(v,null,2)).catch(()=>{{}})</script>''', encoding="utf-8")
