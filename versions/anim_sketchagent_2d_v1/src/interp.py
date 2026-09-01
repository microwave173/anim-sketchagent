"""Geometric inbetweens between Path2D key scenes, matched by stroke id."""
from __future__ import annotations

import copy
import math
import re

from path2d.geometry import sample_stroke
from path2d.schema import Path2DScene, Path2DStroke


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(name or "").lower())


def ease(t: float, kind: str) -> float:
    t = min(1.0, max(0.0, t))
    if kind == "smooth":
        return t * t * (3 - 2 * t)
    if kind == "ease_out":
        return 1 - (1 - t) ** 2
    return t


def polyline_of(stroke: dict) -> list[tuple[float, float]]:
    sampled = sample_stroke(Path2DStroke.from_dict(stroke))
    pts: list[tuple[float, float]] = []
    for line in sampled.polylines:
        for row in line:
            pts.append((float(row[0]), float(row[1])))
    return pts


def resample(pts: list[tuple[float, float]], n: int) -> list[tuple[float, float]]:
    if n <= 1:
        return [pts[0]]
    closed = len(pts) >= 2 and math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) < 1e-4
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
    denom = max(n - (2 if closed else 1), 1)
    for j in range(n - (1 if closed else 0)):
        target = total * j / denom
        acc = 0.0
        placed = False
        for i, d in enumerate(segs):
            if acc + d >= target or i == len(segs) - 1:
                u = 0.0 if d < 1e-6 else min(1.0, max(0.0, (target - acc) / d))
                out.append((src[i][0] + u * (src[i + 1][0] - src[i][0]), src[i][1] + u * (src[i + 1][1] - src[i][1])))
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


def points_to_path(pts: list[tuple[float, float]]) -> str:
    if not pts:
        raise ValueError("empty polyline")
    bits = [f"M {pts[0][0]:.4f} {pts[0][1]:.4f}"]
    for x, y in pts[1:]:
        bits.append(f"L {x:.4f} {y:.4f}")
    if len(pts) >= 2 and math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) < 1e-3:
        bits.append("Z")
    return " ".join(bits)


_BODY_ID_MARKERS = (
    "_leg",
    "_arm",
    "_torso",
    "_head",
    "_body",
    "_neck",
    "_hip",
    "_shoulder",
    "_hand",
    "_foot",
    "_ear",
    "_tail",
    "_muzzle",
    "_wing",
)


def _belongs(stroke_id: str, part_id: str) -> bool:
    sid, pid = str(stroke_id), str(part_id)
    return sid == pid or sid.startswith(pid + "_")


def _is_body_part_id(part_id: str) -> bool:
    sid = str(part_id or "").lower()
    return sid.startswith("person") or any(marker in sid for marker in _BODY_ID_MARKERS)


def anchored_ids(plan: dict) -> list[str]:
    return [
        str(p.get("id") or "").strip()
        for p in (plan.get("parts") or [])
        if str(p.get("motion") or "").lower() == "anchored"
        and str(p.get("id") or "").strip()
        and not _is_body_part_id(str(p.get("id") or ""))
    ]


def pin_anchored_scene(scene: dict, anchor_scene: dict, plan: dict) -> dict:
    anchored = anchored_ids(plan)
    if not anchored:
        return copy.deepcopy(scene)
    source = [
        copy.deepcopy(item)
        for item in anchor_scene.get("strokes") or []
        if any(_belongs(str(item.get("id") or ""), part_id) for part_id in anchored)
    ]
    kept = [
        copy.deepcopy(item)
        for item in scene.get("strokes") or []
        if not any(_belongs(str(item.get("id") or ""), part_id) for part_id in anchored)
    ]
    value = copy.deepcopy(scene)
    value["strokes"] = kept + source
    return value


def scene_contract_report(scene: dict, plan: dict, *, canonical_ids: set[str] | None = None) -> dict:
    ids = [str(item.get("id") or "").strip() for item in scene.get("strokes") or []]
    id_set = set(ids)
    parts = [str(p.get("id") or "").strip() for p in (plan.get("parts") or []) if str(p.get("id") or "").strip()]
    missing = [part_id for part_id in parts if part_id not in id_set]
    canonical_missing = sorted((canonical_ids or set()) - id_set)
    return {
        "ok": not missing and not canonical_missing,
        "stroke_count": len(ids),
        "missing_part_ids": missing,
        "canonical_missing": canonical_missing,
    }


def interpolate_scene(scene_a: dict, scene_b: dict, t: float, *, ease_kind: str = "linear", plan: dict | None = None) -> dict:
    u = ease(t, ease_kind)
    extra = set(anchored_ids(plan or {}))
    by_a = {str(s.get("id") or ""): s for s in scene_a.get("strokes") or []}
    by_b = {str(s.get("id") or ""): s for s in scene_b.get("strokes") or []}
    out = []
    for sid, sa in by_a.items():
        sb = by_b.get(sid)
        if sb is None:
            out.append(copy.deepcopy(sa))
            continue
        if extra and any(_belongs(sid, part_id) for part_id in extra):
            out.append(copy.deepcopy(sa))
            continue
        pa, pb = polyline_of(sa), polyline_of(sb)
        n = max(len(pa), len(pb), 2)
        qa, qb = resample(pa, n), resample(pb, n)
        pts = [(p[0] + u * (q[0] - p[0]), p[1] + u * (q[1] - p[1])) for p, q in zip(qa, qb)]
        item = copy.deepcopy(sa)
        item["path"] = points_to_path(pts)
        out.append(item)
    value = copy.deepcopy(scene_a)
    value["strokes"] = out
    return value


def expand_timeline(keys: list[dict], gaps: list[dict]) -> list[dict]:
    if len(gaps) != len(keys) - 1:
        raise ValueError("gaps must be one per key interval")
    timeline = []
    idx = 1
    for i, key in enumerate(keys):
        timeline.append({"i": idx, "kind": "key", "key_name": key["name"], "key": key})
        idx += 1
        if i == len(keys) - 1:
            break
        n = min(10, max(1, int(gaps[i].get("n_inbetween", 2))))
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
                }
            )
            idx += 1
    stamp_frame_span(timeline)
    return timeline


def stamp_frame_span(timeline: list[dict]) -> list[dict]:
    n_frames = len(timeline)
    next_key = None
    for slot in reversed(timeline):
        if slot.get("kind") == "key":
            next_key = slot["i"]
        slot["n_frames"] = n_frames
        slot["current_frame"] = slot["i"]
        slot["from_frame"] = slot["i"] - 1 if slot["i"] > 1 else None
        slot["to_frame"] = next_key
    return timeline


def frames_to_redraw(timeline: list[dict], frame_i: int, cascade: bool = False) -> list[int]:
    n = len(timeline)
    if not 1 <= int(frame_i) <= n:
        raise ValueError(f"frame {frame_i} out of range 1–{n}")
    slot = timeline[int(frame_i) - 1]
    if int(slot["i"]) != int(frame_i):
        raise ValueError(f"timeline slot mismatch at {frame_i}")
    indices = [int(frame_i)]
    if not cascade:
        return indices
    for later in timeline[int(frame_i) :]:
        if later.get("kind") == "key":
            break
        indices.append(int(later["i"]))
    return indices
