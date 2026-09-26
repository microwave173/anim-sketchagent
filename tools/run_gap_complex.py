"""Finish a complex run by generating each complete key-to-key gap in one call."""
from __future__ import annotations

import argparse
import copy
import importlib
import json
from pathlib import Path
import shutil
import sys
import time

from common import ROOT, gzip_file, write_gif, write_json, write_sheet


def scene_motion_brief(scene: dict) -> dict:
    """Geometry context for estimating boundary direction without another model call."""
    return {
        "strokes": [
            {
                "id": stroke.get("id"),
                "path": stroke.get("path"),
                "description": stroke.get("description"),
            }
            for stroke in scene.get("strokes") or []
        ]
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dim", type=int, choices=(2, 3), required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--gif-ms", type=int, default=120)
    parser.add_argument("--size", type=int, default=384)
    parser.add_argument("--reasoning-effort", choices=("low", "high", "max"), default="high")
    args = parser.parse_args()
    out = args.run
    plan = json.loads((out / "plan.json").read_text())
    key_files = sorted((out / "keys").glob("*/final/scene.json"))
    if len(key_files) != len(plan["keys"]):
        raise ValueError(f"expected {len(plan['keys'])} keys, found {len(key_files)}")

    anim = ROOT / "versions" / f"anim_sketchagent_{args.dim}d_v1" / "src"
    sys.path[:0] = [str(anim), str(ROOT / f"versions/path{args.dim}d_v1")]
    prompts = importlib.import_module("prompts")
    native = importlib.import_module(f"glm_anim_{args.dim}d")
    from terra_client import call_deepseek, parse_json_obj

    if args.dim == 2:
        from path2d.parser import parse_path2d as parse_path
        from path2d.renderer import render_scene
        from path2d.schema import Path2DScene as Scene
        system = native.INBETWEEN_DRAWER_SYSTEM + "\nGenerate every requested inbetween of one gap in one JSON response. The gap is part of a longer animation: preserve incoming and outgoing velocity at both shared-key boundaries."
    else:
        from path3d.generator import SYSTEM_PROMPT
        from path3d.parser import parse_path3d as parse_path
        from path3d.renderer import render_scene_views
        from path3d.schema import Path3DScene as Scene
        system = SYSTEM_PROMPT + "\n" + prompts.INBETWEEN_REASONING + "\nGenerate every requested inbetween of one gap in one JSON response. Preserve real spatial depth and incoming/outgoing velocity at both shared-key boundaries."

    keys = {
        spec["name"]: json.loads(path.read_text())
        for spec, path in zip(plan["keys"], key_files)
    }
    anchor = copy.deepcopy(keys[plan["keys"][0]["name"]])
    canonical_ids = {
        str(stroke.get("id") or "").strip()
        for stroke in anchor.get("strokes") or []
        if str(stroke.get("id") or "").strip()
    }
    key_positions: list[int] = []
    frames: dict[int, dict] = {}
    cursor = 1
    for i, key in enumerate(plan["keys"]):
        key_positions.append(cursor)
        frames[cursor] = copy.deepcopy(keys[key["name"]])
        if i < len(plan["gaps"]):
            cursor += 1 + int(plan["gaps"][i]["n_inbetween"])
    if cursor != int(plan["n_frames"]):
        raise ValueError(f"timeline ends at {cursor}, plan says {plan['n_frames']}")

    started = time.time()
    gap_rows = []
    try:
        for gap_i, gap in enumerate(plan["gaps"]):
            start_i, end_i = key_positions[gap_i], key_positions[gap_i + 1]
            wanted = list(range(start_i + 1, end_i))
            from_name = plan["keys"][gap_i]["name"]
            to_name = plan["keys"][gap_i + 1]["name"]
            previous_name = plan["keys"][gap_i - 1]["name"] if gap_i > 0 else None
            next_name = plan["keys"][gap_i + 2]["name"] if gap_i + 2 < len(plan["keys"]) else None
            incoming_context = (
                json.dumps(
                    {
                        "previous_key": plan["keys"][gap_i - 1],
                        "previous_scene": scene_motion_brief(keys[previous_name]),
                    },
                    ensure_ascii=False,
                )
                if previous_name
                else "none: FROM is the first animation key"
            )
            outgoing_context = (
                json.dumps(
                    {
                        "next_key": plan["keys"][gap_i + 2],
                        "next_scene": scene_motion_brief(keys[next_name]),
                    },
                    ensure_ascii=False,
                )
                if next_name
                else "none: TO is the final animation key"
            )
            gap_dir = out / "gaps" / f"{gap_i + 1:02d}_{from_name}_to_{to_name}"
            gap_dir.mkdir(parents=True, exist_ok=True)
            progress = [{"i": i, "t": round((i - start_i) / (end_i - start_i), 4)} for i in wanted]
            user = f"""Generate exactly the intermediate frames listed below in ONE response.
The endpoint key frames are context only and must not be returned.

Expanded action: {plan.get('action')}
Plan notes: {plan.get('notes')}
This interval: {gap.get('why')}
Ease: {gap.get('ease')}
FROM key '{from_name}' is frame {start_i}. TO key '{to_name}' is frame {end_i}.
Requested frames: {json.dumps(progress)}

Rules:
- Treat these frames as one continuous mini-animation; progress monotonically from FROM to TO.
- Infer the motion bridge from the ordinary previous/current/next key beat+notes and their geometry; the planner has no special continuity fields.
- This gap must splice into the full clip with C1-like motion continuity. The first returned frame continues the displacement and articulation direction arriving at FROM; the last returned frame approaches TO in a direction compatible with what leaves TO toward the next key.
- A key is a sampled pose, not an automatic pause. Do not decelerate to zero at FROM or TO unless the beat explicitly says impact hold, landing, reversal, or final settle.
- Track causal state monotonically: which foot is planted, which limb leads, which hand holds a prop, whether an object is approaching/touching/held/released, and which side of an obstacle it occupies. Never reset these at a gap boundary.
- Contact precedes release, landing precedes settling, and moving bodies visibly advance in every frame.
- Every frame contains every canonical stroke id exactly once: {sorted(canonical_ids)}.
- Preserve identity, proportions, part sizes, attachment joints, and the fixed camera.
- Use the FIRST KEY identity anchor below only for shape and proportions. Use neighboring keys for motion. Never drift gradually from the first-key model sheet.
- Anchored scenery is geometrically identical to FROM.
- Return complete geometry, never deltas, code, interpolation instructions, or commentary.
- Coordinates remain inside [-1,1].

PREVIOUS-KEY context for incoming velocity at FROM:
{incoming_context}

NEXT-KEY context for outgoing velocity after TO:
{outgoing_context}

FIRST KEY identity anchor (appearance only, never pose timing):
{json.dumps(scene_motion_brief(anchor), ensure_ascii=False)}

FROM scene:
{json.dumps(keys[from_name], ensure_ascii=False)}

TO scene:
{json.dumps(keys[to_name], ensure_ascii=False)}

Return JSON only: {{"frames":[{{"i":{wanted[0]},"strokes":[{{"id":"...","path":"M ...","description":"..."}}]}}]}}
The frames array contains exactly {wanted} in ascending order.
"""
            (gap_dir / "prompt.txt").write_text(user, encoding="utf-8")
            gap_started = time.time()
            raw = call_deepseek(
                [{"role": "system", "content": system}, {"role": "user", "content": user}],
                model="deepseek-flash", reasoning_effort=args.reasoning_effort,
                thinking=args.reasoning_effort != "low",
                max_tokens=131072, timeout=900, temperature=0.4,
            )
            (gap_dir / "raw.txt").write_text(raw, encoding="utf-8")
            value = parse_json_obj(raw)
            returned = value.get("frames")
            got = [int(frame.get("i", -1)) for frame in returned] if isinstance(returned, list) else []
            if got != wanted:
                raise ValueError(f"gap {gap_i + 1}: expected {wanted}, got {got}")
            contracts = []
            for frame in returned:
                scene_value = {"prompt": args.prompt, "strokes": frame.get("strokes") or []}
                if args.dim == 2:
                    scene_value = native.pin_stroke_ink(scene_value)
                    scene_value = native.pin_anchored_scene(scene_value, anchor, plan)
                    report = native.scene_contract_report(scene_value, plan, canonical_ids=canonical_ids)
                    if not report["ok"]:
                        raise ValueError(f"frame {frame['i']} contract: {report}")
                else:
                    scene_value = native.pin_anchored_scene(scene_value, anchor, plan)
                    report = native.require_scene_contract(
                        scene_value, plan, label=f"gap {gap_i + 1} frame {frame['i']}", canonical_ids=canonical_ids
                    )
                scene = Scene.from_dict(scene_value, prompt=args.prompt)
                for stroke in scene.strokes:
                    parse_path(stroke.path)
                frames[int(frame["i"])] = scene.to_dict()
                contracts.append({"frame": frame["i"], "report": report})
            write_json(gap_dir / "contracts.json", contracts)
            gzip_file(gap_dir / "raw.txt")
            row = {
                "gap": gap_i + 1, "from": from_name, "to": to_name,
                "frames": wanted, "seconds": round(time.time() - gap_started, 2), "generation_calls": 1,
            }
            gap_rows.append(row)
            print(f"gap {gap_i + 1}/{len(plan['gaps'])} frames={wanted} seconds={row['seconds']}", flush=True)

        if sorted(frames) != list(range(1, int(plan["n_frames"]) + 1)):
            raise ValueError("incomplete timeline")
        for index, value in frames.items():
            scene_dir = out / "frames" / f"f{index:02d}"
            scene_dir.mkdir(parents=True, exist_ok=True)
            scene = Scene.from_dict(value, prompt=args.prompt)
            (scene_dir / "scene.json").write_text(scene.to_json(), encoding="utf-8")

        cache = out / "_render_cache"
        shutil.rmtree(cache, ignore_errors=True)
        cache.mkdir()
        primary: list[Path] = []
        views = {name: [] for name in ("front", "side", "top", "perspective")}
        for index in range(1, int(plan["n_frames"]) + 1):
            scene = Scene.from_dict(frames[index], prompt=args.prompt)
            dest = cache / f"f{index:02d}"
            dest.mkdir()
            if args.dim == 2:
                path = dest / "view.png"
                render_scene(scene, path, width=args.size, height=args.size)
                primary.append(path)
            else:
                paths = render_scene_views(scene, dest / "views", width=args.size, height=args.size, normalize=False)
                by_name = {path.stem.removeprefix("view_"): path for path in paths}
                for name in views:
                    views[name].append(by_name[name])
                primary.append(by_name["perspective"])
        write_gif(primary, out / "clip.gif", args.gif_ms)
        write_sheet(primary, out / "contact_sheet.jpg")
        if args.dim == 3:
            for name, paths in views.items():
                write_gif(paths, out / f"clip_{name}.gif", args.gif_ms)
        shutil.rmtree(cache, ignore_errors=True)

        old_summary = {}
        if (out / "summary.json").exists():
            old_summary = json.loads((out / "summary.json").read_text())
        summary = {
            "ok": True,
            "pipeline": "first_plan_oneshot_keys_gap_oneshot",
            "dimension": args.dim,
            "n_frames": plan["n_frames"],
            "n_keys": len(plan["keys"]),
            "key_rows": old_summary.get("key_rows"),
            "key_generation_seconds": round(sum(float(row.get("seconds") or 0) for row in old_summary.get("key_rows") or []), 2),
            "gap_rows": gap_rows,
            "gap_generation_seconds": round(sum(row["seconds"] for row in gap_rows), 2),
            "gap_wall_seconds": round(time.time() - started, 2),
            "gif_ms": args.gif_ms,
            "geometry_hand_edited": False,
            "prompt_protocol": "continuity_v2",
            "reasoning_effort": args.reasoning_effort,
        }
        write_json(out / "summary.json", summary)
        (out / "exit_code.txt").write_text("0")
    except BaseException as exc:
        write_json(out / "gap_failure.json", {
            "error_type": type(exc).__name__, "error": str(exc),
            "wall_seconds": round(time.time() - started, 2), "completed_gaps": gap_rows,
        })
        (out / "exit_code.txt").write_text("1")
        raise


if __name__ == "__main__":
    main()
