#!/usr/bin/env python3
"""Run the 12-task suite in synchronized 3D with at most 12 jobs at once."""

import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path("/root/autodl-tmp/anim-sketchagent")
MANIFEST = Path("/root/autodl-tmp/outputs/baseline_advantage_12/tasks.json")
OUTPUT = PROJECT / "outputs" / "baseline_advantage_12_synced_3d_v2"
PYTHON = PROJECT / ".venv-light" / "bin" / "python"
CLI = PROJECT / "light_agent" / "cli.py"
MAX_JOBS = 12
MAX_ROUNDS = 3


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def complete(directory, dim):
    metrics_file = directory / "metrics.json"
    if not metrics_file.is_file() or not (directory / "clip.gif").is_file():
        return False
    try:
        metrics = json.loads(metrics_file.read_text())
    except (OSError, ValueError):
        return False
    if not metrics.get("ok") or metrics.get("n_frames") != 24:
        return False
    return ((directory / "animation.svg").is_file() and
            len(list((directory / "frames_svg").glob("frame_*.svg"))) == 24)


def run_job(job, round_number):
    dim, task = job
    task_id = task["id"]
    directory = OUTPUT / f"{dim}d" / task_id
    directory.mkdir(parents=True, exist_ok=True)
    key = f"{dim}d/{task_id}"
    if complete(directory, dim):
        print(f"{key}: already complete", flush=True)
        return key, "complete"

    command = [
        str(PYTHON), "-u", str(CLI), "--prompt", task["prompt"],
        "--dim", str(dim), "--frames", "24", "--frame-ms", "120",
        "--size", "640", "--api-profile", "official", "--effort", "high",
        "--gap-workers", "2", "--debug", "--out", str(directory),
    ]
    started_at = datetime.now(timezone.utc).isoformat()
    print(f"{key}: round {round_number} starting", flush=True)
    write_json(directory / "runner_status.json", {
        "task_id": task_id, "dimension": dim, "state": "running",
        "round": round_number, "started_at": started_at,
    })
    started = time.monotonic()
    with (directory / "run.log").open("a", encoding="utf-8") as log:
        log.write(f"\n=== round {round_number} started {started_at} ===\n")
        log.flush()
        result = subprocess.run(command, cwd=PROJECT, stdout=log,
                                stderr=subprocess.STDOUT, check=False)
    ok = result.returncode == 0 and complete(directory, dim)
    state = "complete" if ok else "failed"
    write_json(directory / "runner_status.json", {
        "task_id": task_id, "dimension": dim, "state": state,
        "round": round_number, "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "wall_seconds": round(time.monotonic() - started, 3),
        "exit_code": result.returncode,
    })
    print(f"{key}: {state}, exit={result.returncode}", flush=True)
    return key, state


def main():
    tasks = json.loads(MANIFEST.read_text())["tasks"]
    jobs = [(3, task) for task in tasks]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_json(OUTPUT / "batch_config.json", {
        "source_manifest": str(MANIFEST), "task_count": len(tasks),
        "dimensions": [3], "total_jobs": len(jobs),
        "max_parallel_jobs": MAX_JOBS, "max_rounds": MAX_ROUNDS,
        "frames": 24, "frame_ms": 120, "size": 640,
        "api_profile": "official", "effort": "high", "gap_workers_per_job": 2,
        "output_protocol": "Path3D source plus standard perspective SVG projection",
        "task_ids": [task["id"] for task in tasks],
    })
    states = {}
    pending = jobs
    for round_number in range(1, MAX_ROUNDS + 1):
        if not pending:
            break
        print(f"round {round_number}: {len(pending)} pending jobs", flush=True)
        next_pending = []
        with ThreadPoolExecutor(max_workers=MAX_JOBS) as executor:
            futures = {executor.submit(run_job, job, round_number): job for job in pending}
            for future in as_completed(futures):
                dim, task = futures[future]
                key = f"{dim}d/{task['id']}"
                try:
                    _, state = future.result()
                except Exception as exc:
                    state = "runner_error"
                    print(f"{key}: runner_error {exc!r}", file=sys.stderr, flush=True)
                states[key] = state
                if state != "complete":
                    next_pending.append((dim, task))
                write_json(OUTPUT / "batch_status.json", states)
        pending = next_pending
        if pending and round_number < MAX_ROUNDS:
            print(f"round {round_number}: waiting 30s before retrying {len(pending)} jobs", flush=True)
            time.sleep(30)
    write_json(OUTPUT / "batch_summary.json", {
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "complete": sum(state == "complete" for state in states.values()),
        "failed": sorted(key for key, state in states.items() if state != "complete"),
        "results": states,
    })
    print("batch finished:", json.dumps(states, ensure_ascii=False), flush=True)
    raise SystemExit(0 if all(state == "complete" for state in states.values()) else 1)


if __name__ == "__main__":
    main()
