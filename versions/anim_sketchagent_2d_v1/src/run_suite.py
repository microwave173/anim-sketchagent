#!/usr/bin/env python3
"""Run the five 2D eval clips sequentially (oneshot keys, oneshot inbetweens, no reflect)."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
from prompts import SUITE  # noqa: E402


def main() -> None:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    root = HERE / "outputs" / f"suite2d_{stamp}"
    root.mkdir(parents=True, exist_ok=True)
    log = (root / "suite.log").open("a", encoding="utf-8")
    rows = []
    for name in SUITE:
        out = root / name
        cmd = [
            sys.executable,
            str(HERE / "glm_anim_2d.py"),
            "--task",
            name,
            "--keys",
            "3",
            "--out",
            str(out),
        ]
        print(f"== {name} -> {out} ==", flush=True)
        log.write(f"== {' '.join(cmd)}\n")
        log.flush()
        t0 = time.time()
        proc = subprocess.run(cmd, cwd=str(HERE), stdout=log, stderr=subprocess.STDOUT)
        sec = round(time.time() - t0, 1)
        rows.append({"task": name, "returncode": proc.returncode, "seconds": sec, "out": str(out)})
        print(f"  {name} exit={proc.returncode} {sec}s", flush=True)
    (root / "suite.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    log.close()
    failed = [row for row in rows if row["returncode"] != 0]
    if failed:
        raise SystemExit(f"failed: {[row['task'] for row in failed]}")
    print(f"wrote {root}", flush=True)


if __name__ == "__main__":
    main()
