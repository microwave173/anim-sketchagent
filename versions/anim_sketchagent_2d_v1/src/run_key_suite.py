#!/usr/bin/env python3
"""Run the 8 pose-to-pose probe clips, continuing if one fails."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
from anim_prompts import ANIMAL_SUITE, SUITE_TASKS


def main() -> None:
    suite = sys.argv[1] if len(sys.argv) > 1 else "probe"
    names = ANIMAL_SUITE if suite in {"animal", "animals"} else SUITE_TASKS
    rows = []
    for name in names:
        print(f"\n######## {name} ########", flush=True)
        t0 = time.time()
        proc = subprocess.run(
            [sys.executable, str(HERE / "glm_anim_keys.py"), "--task", name],
            cwd=str(HERE),
        )
        rec = {
            "task": name,
            "ok": proc.returncode == 0,
            "seconds": round(time.time() - t0, 1),
            "returncode": proc.returncode,
        }
        rows.append(rec)
        print(f"  suite {name} ok={rec['ok']} {rec['seconds']}s", flush=True)
    out = HERE / "outputs" / f"suite_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"rows": rows}, indent=2), encoding="utf-8")
    n_ok = sum(1 for r in rows if r["ok"])
    print(f"\n== suite {n_ok}/{len(rows)} ok -> {out} ==", flush=True)
    if n_ok != len(rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
