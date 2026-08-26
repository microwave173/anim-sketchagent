"""Geometric inbetweens between SketchAgent key XML frames, matched by stroke id."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

from sa_render import CELL_RE, convert_completion

STROKE_RE = re.compile(
    r"<s(\d+)>\s*"
    r"<points>(.*?)</points>\s*"
    r"<t_values>(.*?)</t_values>\s*"
    r"<id>(.*?)</id>\s*"
    r"</s\d+>",
    re.S | re.I,
)


@dataclass
class Stroke:
    tag: int
    name: str
    points: list[tuple[float, float]]
    t_values: list[float]


def parse_named_strokes(xml: str) -> list[Stroke]:
    out = []
    for m in STROKE_RE.finditer(xml):
        tag = int(m.group(1))
        pts = []
        for tok in m.group(2).split(","):
            cm = CELL_RE.search(tok)
            if cm:
                pts.append((float(cm.group(1)), float(cm.group(2))))
        ts = [float(x) for x in m.group(3).split(",") if x.strip()]
        name = m.group(4).strip()
        if pts:
            if len(ts) != len(pts):
                ts = [i / (len(pts) - 1) if len(pts) > 1 else 0.0 for i in range(len(pts))]
            out.append(Stroke(tag=tag, name=name, points=pts, t_values=ts))
    return out


def _closed(pts: list[tuple[float, float]]) -> bool:
    return len(pts) >= 2 and pts[0] == pts[-1]


def _length(pts: list[tuple[float, float]]) -> float:
    return sum(math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]) for i in range(1, len(pts)))


def resample(pts: list[tuple[float, float]], n: int) -> list[tuple[float, float]]:
    if n <= 1:
        return [pts[0]]
    if len(pts) == n:
        return list(pts)
    closed = _closed(pts)
    src = pts[:-1] if closed and len(pts) > 2 else pts
    if len(src) == 1:
        return [src[0]] * n
    segs = []
    total = 0.0
    for i in range(1, len(src)):
        d = math.hypot(src[i][0] - src[i - 1][0], src[i][1] - src[i - 1][1])
        segs.append(d)
        total += d
    if total < 1e-6:
        return [src[0]] * n
    out = []
    for j in range(n - (1 if closed else 0)):
        target = total * j / max(n - (2 if closed else 1), 1)
        acc = 0.0
        placed = False
        for i, d in enumerate(segs):
            if acc + d >= target or i == len(segs) - 1:
                t = 0.0 if d < 1e-6 else min(1.0, max(0.0, (target - acc) / d))
                x = src[i][0] + t * (src[i + 1][0] - src[i][0])
                y = src[i][1] + t * (src[i + 1][1] - src[i][1])
                out.append((x, y))
                placed = True
                break
            acc += d
        if not placed:
            out.append(src[-1])
    if closed:
        out.append(out[0])
    while len(out) < n:
        out.append(out[-1])
    return out[:n]


def ease(t: float, kind: str) -> float:
    t = min(1.0, max(0.0, t))
    if kind == "smooth":
        return t * t * (3 - 2 * t)
    if kind == "ease_out":
        return 1 - (1 - t) ** 2
    return t


def _norm_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


ANCHORED_TOKENS = (
    "ground",
    "floor",
    "horizon",
    "court",
    "baseline",
    "scenery",
    "wall",
    "bench",
    "stool",
    "seat",
    "water",
    "pad",
    "bank",
    "branch",
    "fence",
    "perch",
    "table",
)


def is_anchored_name(name: str, extra: set[str] | None = None) -> bool:
    n = _norm_name(name)
    if extra and n in extra:
        return True
    return any(tok in n for tok in ANCHORED_TOKENS)


def anchored_names_from_parts(parts) -> set[str]:
    extra: set[str] = set()
    for p in parts or []:
        if str(p.get("motion") or "").lower() == "anchored":
            extra.add(_norm_name(str(p.get("name") or "")))
    return extra


def strokes_only_xml(strokes: list[Stroke]) -> str:
    blocks = []
    for s in strokes:
        pts = ", ".join(f"'x{int(x)}y{int(y)}'" for x, y in s.points)
        ts = ",".join(f"{v:.3f}" for v in s.t_values)
        blocks.append(
            f"    <s{s.tag}>\n"
            f"        <points>{pts}</points>\n"
            f"        <t_values>{ts}</t_values>\n"
            f"        <id>{s.name}</id>\n"
            f"    </s{s.tag}>"
        )
    return "<strokes>\n" + "\n".join(blocks) + "\n</strokes>"


def pin_anchored_xml(dst_xml: str, src_xml: str, extra: set[str] | None = None) -> str:
    """Force ground/scenery in dst to match src; inject missing anchored strokes."""
    src = parse_named_strokes(src_xml)
    dst = parse_named_strokes(dst_xml)
    if not src or not dst:
        return dst_xml
    src_a = {_norm_name(s.name): s for s in src if is_anchored_name(s.name, extra)}
    if not src_a:
        return dst_xml
    out: list[Stroke] = []
    seen: set[str] = set()
    for s in dst:
        key = _norm_name(s.name)
        if key in src_a:
            pinned = src_a[key]
            out.append(Stroke(tag=s.tag, name=s.name, points=list(pinned.points), t_values=list(pinned.t_values)))
            seen.add(key)
        else:
            out.append(s)
    used_tags = {s.tag for s in out}
    for key, s in src_a.items():
        if key in seen:
            continue
        tag = s.tag
        while tag in used_tags:
            tag += 1
        used_tags.add(tag)
        out.append(Stroke(tag=tag, name=s.name, points=list(s.points), t_values=list(s.t_values)))
    return strokes_only_xml(out)


def pair_strokes(a: list[Stroke], b: list[Stroke]) -> list[tuple[Stroke, Stroke]]:
    used_b = set()
    pairs = []
    b_by = {_norm_name(s.name): i for i, s in enumerate(b)}
    for sa in a:
        j = b_by.get(_norm_name(sa.name))
        if j is not None and j not in used_b:
            pairs.append((sa, b[j]))
            used_b.add(j)
            continue
        for k, sb in enumerate(b):
            if k not in used_b and sa.tag == sb.tag:
                pairs.append((sa, sb))
                used_b.add(k)
                break
    return pairs


def lerp_stroke(sa: Stroke, sb: Stroke, t: float) -> Stroke:
    n = max(len(sa.points), len(sb.points), 2)
    pa, pb = resample(sa.points, n), resample(sb.points, n)
    pts = []
    for p, q in zip(pa, pb):
        x = p[0] + t * (q[0] - p[0])
        y = p[1] + t * (q[1] - p[1])
        xi = int(round(min(50, max(1, x))))
        yi = int(round(min(50, max(1, y))))
        pts.append((float(xi), float(yi)))
    if _closed(sa.points) or _closed(sb.points):
        pts[-1] = pts[0]
    ts = [i / (len(pts) - 1) for i in range(len(pts))]
    return Stroke(tag=sa.tag, name=sa.name, points=pts, t_values=ts)


def strokes_to_xml(strokes: list[Stroke], concept: str) -> str:
    blocks = []
    for s in strokes:
        pts = ", ".join(f"'x{int(x)}y{int(y)}'" for x, y in s.points)
        ts = ",".join(f"{v:.3f}" for v in s.t_values)
        blocks.append(
            f"    <s{s.tag}>\n"
            f"        <points>{pts}</points>\n"
            f"        <t_values>{ts}</t_values>\n"
            f"        <id>{s.name}</id>\n"
            f"    </s{s.tag}>"
        )
    inner = "\n".join(blocks)
    return f"<answer><concept>{concept}</concept><strokes>\n{inner}\n</strokes></answer>"


def interpolate_xml(
    xml_a: str,
    xml_b: str,
    t: float,
    concept: str,
    ease_kind: str = "linear",
    extra: set[str] | None = None,
) -> str:
    a, b = parse_named_strokes(xml_a), parse_named_strokes(xml_b)
    if not a or not b:
        raise ValueError("could not parse key XML")
    u = ease(t, ease_kind)
    out = []
    for sa, sb in pair_strokes(a, b):
        if is_anchored_name(sa.name, extra) or is_anchored_name(sb.name, extra):
            out.append(sa)
        else:
            out.append(lerp_stroke(sa, sb, u))
    if not out:
        raise ValueError("no matching strokes between keys")
    return strokes_to_xml(out, concept)


def render_xml(xml: str, png_path) -> dict:
    return convert_completion(xml, png_path)


def expand_timeline(keys: list[dict], gaps: list[dict]) -> list[dict]:
    """keys in order; gaps[i] is inbetweens AFTER keys[i] toward keys[i+1]."""
    if len(gaps) != len(keys) - 1:
        raise ValueError("gaps must be one per key interval")
    timeline = []
    idx = 1
    for i, key in enumerate(keys):
        timeline.append({"i": idx, "kind": "key", "key_name": key["name"], "key": key})
        idx += 1
        if i == len(keys) - 1:
            break
        n = int(gaps[i].get("n_inbetween", 2))
        n = min(10, max(1, n))
        ease_kind = str(gaps[i].get("ease", "linear"))
        for k in range(1, n + 1):
            timeline.append(
                {
                    "i": idx,
                    "kind": "inbetween",
                    "t": k / (n + 1),
                    "from": key["name"],
                    "to": keys[i + 1]["name"],
                    "ease": ease_kind,
                    "gap": i,
                }
            )
            idx += 1
    return timeline
