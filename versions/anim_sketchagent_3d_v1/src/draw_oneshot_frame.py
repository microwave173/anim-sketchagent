#!/usr/bin/env python3
"""One-shot GLM inbetween for a single timeline index, compared against an existing run."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from glm_anim_3d import (  # noqa: E402
    expand_timeline,
    load_run_keys,
    pin_anchored_scene,
    require_scene_contract,
)
from oneshot_glm import generate_scene, render_scene  # noqa: E402
from path3d.schema import Path3DScene  # noqa: E402
from prompts import inbetween_oneshot_prompt  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-run", type=Path, required=True)
    ap.add_argument("--frame", type=int, default=2, help="1-based timeline index (f02 = 2)")
    ap.add_argument("--width", type=int, default=512)
    ap.add_argument("--height", type=int, default=512)
    args = ap.parse_args()
    out = args.from_run if args.from_run.is_absolute() else HERE / args.from_run
    plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
    key_scenes, anchor, canonical = load_run_keys(out, plan)
    timeline = expand_timeline(plan["keys"], plan["gaps"])
    slot = next((item for item in timeline if item["i"] == int(args.frame)), None)
    if slot is None:
        raise SystemExit(f"no timeline slot i={args.frame}")
    if slot["kind"] != "inbetween":
        raise SystemExit(f"frame {args.frame} is a {slot['kind']}, not an inbetween")
    prompt = inbetween_oneshot_prompt(plan, slot, key_scenes[slot["from"]], key_scenes[slot["to"]])
    prompt += f"\nInclude every canonical stroke id exactly once: {sorted(canonical)}.\n"
    dest = out / f"oneshot_f{int(args.frame):02d}"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "prompt.txt").write_text(prompt, encoding="utf-8")
    print(f"== oneshot inbetween i={slot['i']} {slot['from']}->{slot['to']} t={slot['t']:.2f} -> {dest} ==", flush=True)
    scene, raw = generate_scene(prompt)
    (dest / "raw.txt").write_text(raw, encoding="utf-8")
    value = pin_anchored_scene(scene.to_dict(), anchor, plan)
    report = require_scene_contract(
        value, plan, label=f"oneshot f{slot['i']:02d}", canonical_ids=canonical
    )
    scene = Path3DScene.from_dict(value, prompt=plan.get("concept", ""))
    rec = render_scene(scene, dest, width=args.width, height=args.height, normalize=False)
    (dest / "contract.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, **report, "contact_sheet": rec["contact_sheet"]}, indent=2), flush=True)


if __name__ == "__main__":
    main()
