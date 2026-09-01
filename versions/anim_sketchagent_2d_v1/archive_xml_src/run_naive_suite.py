#!/usr/bin/env python3
"""Run the 8 prompts with naive full-draw (one GLM XML per frame)."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
from anim_prompts import SUITE_TASKS


def main() -> None:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    parent = HERE / "outputs" / f"ablation_naive_full_draw_{stamp}"
    parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for name in SUITE_TASKS:
        print(f"\n######## naive {name} ########", flush=True)
        t0 = time.time()
        out = parent / name
        proc = subprocess.run(
            [sys.executable, str(HERE / "glm_anim_two_stage.py"), "--task", name, "--out", str(out)],
            cwd=str(HERE),
        )
        rec = {
            "task": name,
            "ok": proc.returncode == 0,
            "seconds": round(time.time() - t0, 1),
            "returncode": proc.returncode,
            "out": str(out),
        }
        rows.append(rec)
        print(f"  naive {name} ok={rec['ok']} {rec['seconds']}s", flush=True)
    summary = parent / "suite.json"
    summary.write_text(json.dumps({"pipeline": "naive_full_draw_every_frame", "rows": rows}, indent=2), encoding="utf-8")
    n_ok = sum(1 for r in rows if r["ok"])
    print(f"\n== naive suite {n_ok}/{len(rows)} ok -> {summary} ==", flush=True)
    if n_ok != len(rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
