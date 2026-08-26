#!/usr/bin/env python3
"""SketchAgent XML → SVG/PNG, plus cheap structural gates."""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
_SA_CANDIDATES = [
    ROOT / "third_party" / "SketchAgent-main",
    Path(__file__).resolve().parent / "third_party" / "SketchAgent-main",
    Path("/root/autodl-tmp/grpo_sa_pilot/third_party/SketchAgent-main"),
]
SA = next((p for p in _SA_CANDIDATES if (p / "utils.py").exists()), _SA_CANDIDATES[0])
if str(SA) not in sys.path:
    sys.path.insert(0, str(SA))
import utils  # noqa: E402

RES = 50
CELL = 12
STROKE_W = 7
CELL_RE = re.compile(r"x(\d+)y(\d+)")


def extract_strokes_xml(text: str) -> str | None:
    start = text.find("<strokes>")
    end = text.find("</strokes>")
    if start == -1 or end == -1:
        return None
    return text[start : end + len("</strokes>")]


def parse_cells(xml: str) -> list[list[tuple[int, int]]]:
    parsed = utils.parse_xml_string(xml, RES)
    if parsed is None:
        raise ValueError("parse_xml_string returned None")
    strokes_str, _t = parsed
    strokes = ast.literal_eval(strokes_str)
    out = []
    for stroke in strokes:
        pts = []
        for cell in stroke:
            m = CELL_RE.fullmatch(str(cell).strip("'\""))
            if not m:
                continue
            pts.append((int(m.group(1)), int(m.group(2))))
        if pts:
            out.append(pts)
    return out


def xml_to_svg(xml: str) -> str:
    strokes_str, t_str = utils.parse_xml_string(xml, RES)
    strokes, t_values = ast.literal_eval(strokes_str), ast.literal_eval(t_str)
    cells = utils.cells_to_pixels(res=RES, cell_size=CELL)
    cps = utils.get_control_points(strokes, t_values, cells)
    dim = ((RES + 1) * CELL, (RES + 1) * CELL)
    return utils.format_svg(cps, dim=dim, stroke_width=STROKE_W)


def _patch_cairo() -> None:
    cairo_lib = "/opt/homebrew/opt/cairo/lib/libcairo.2.dylib"
    if not Path(cairo_lib).exists():
        return
    import ctypes.util

    original = ctypes.util.find_library

    def find_library(name):
        if name in ("cairo-2", "cairo", "libcairo-2"):
            return cairo_lib
        return original(name)

    ctypes.util.find_library = find_library


def rasterize_svg(svg: str, png_path: Path) -> None:
    _patch_cairo()
    try:
        import cairosvg

        cairosvg.svg2png(
            bytestring=svg.encode("utf-8"),
            write_to=str(png_path),
            background_color="white",
        )
        return
    except Exception:
        pass
    from xml.etree import ElementTree as ET

    root = ET.fromstring(svg)
    w = int(float(root.attrib.get("width", "612")))
    h = int(float(root.attrib.get("height", "612")))
    img = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(img)
    token_re = re.compile(r"[A-Za-z]|[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")

    def cubic(p0, p1, p2, p3, n=20):
        pts = []
        for i in range(n + 1):
            t = i / n
            mt = 1 - t
            x = mt**3 * p0[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t**2 * p2[0] + t**3 * p3[0]
            y = mt**3 * p0[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t**2 * p2[1] + t**3 * p3[1]
            pts.append((x, y))
        return pts

    for el in root.iter():
        if el.tag.split("}")[-1] != "path":
            continue
        tokens = token_re.findall(el.attrib.get("d", ""))
        i = 0
        cx = cy = 0.0
        while i < len(tokens):
            cmd = tokens[i]
            i += 1
            nums = []
            while i < len(tokens) and tokens[i] not in "MLQCZmlqcz":
                nums.append(float(tokens[i]))
                i += 1
            if cmd == "M" and len(nums) >= 2:
                cx, cy = nums[0], nums[1]
            elif cmd == "L" and len(nums) >= 2:
                draw.line([(cx, cy), (nums[0], nums[1])], fill="black", width=STROKE_W)
                cx, cy = nums[0], nums[1]
            elif cmd == "C" and len(nums) >= 6:
                draw.line(
                    cubic((cx, cy), (nums[0], nums[1]), (nums[2], nums[3]), (nums[4], nums[5])),
                    fill="black",
                    width=STROKE_W,
                )
                cx, cy = nums[4], nums[5]
            elif cmd == "Q" and len(nums) >= 4:
                samples = []
                for k in range(17):
                    t = k / 16
                    mt = 1 - t
                    x = mt**2 * cx + 2 * mt * t * nums[0] + t**2 * nums[2]
                    y = mt**2 * cy + 2 * mt * t * nums[1] + t**2 * nums[3]
                    samples.append((x, y))
                draw.line(samples, fill="black", width=STROKE_W)
                cx, cy = nums[2], nums[3]
    img.save(png_path)


def intact_ok(strokes: list[list[tuple[int, int]]], gap: int = 12) -> bool:
    """True unless stroke bboxes are split into far-apart clusters."""
    if not strokes:
        return False
    boxes = []
    for pts in strokes:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        boxes.append((min(xs), min(ys), max(xs), max(ys)))
    # union-find on boxes if they overlap/expand by `gap`
    n = len(boxes)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def near(a, b):
        ax0, ay0, ax1, ay1 = a
        bx0, by0, bx1, by1 = b
        return not (ax1 + gap < bx0 or bx1 + gap < ax0 or ay1 + gap < by0 or by1 + gap < ay0)

    for i in range(n):
        for j in range(i + 1, n):
            if near(boxes[i], boxes[j]):
                parent[find(i)] = find(j)
    roots = {find(i) for i in range(n)}
    if len(roots) <= 2:
        return True
    # allow 3 tiny leftover strokes
    sizes = []
    for r in roots:
        area = 0
        for i, box in enumerate(boxes):
            if find(i) == r:
                area += (box[2] - box[0] + 1) * (box[3] - box[1] + 1)
        sizes.append(area)
    sizes.sort(reverse=True)
    return sizes[0] >= 0.6 * sum(sizes)


def convert_completion(raw: str, png_path: Path) -> dict:
    rec = {"valid": False, "intact": False, "n_strokes": 0, "png": None, "xml": None}
    xml = extract_strokes_xml(raw)
    if not xml:
        return rec
    try:
        strokes = parse_cells(xml)
        svg = xml_to_svg(xml)
        png_path.parent.mkdir(parents=True, exist_ok=True)
        rasterize_svg(svg, png_path)
        rec.update(
            valid=True,
            intact=intact_ok(strokes),
            n_strokes=len(strokes),
            png=str(png_path),
            xml=xml,
        )
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {e}"
    return rec
