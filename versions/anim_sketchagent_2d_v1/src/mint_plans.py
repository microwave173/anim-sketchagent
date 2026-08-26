#!/usr/bin/env python3
"""Mint frozen GLM-5.3 stroke plans for every train/holdout task (resumable)."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from terra_client import call_glm, load_env, parse_json_obj

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT = DATA / "plans.jsonl"

PLAN_SYSTEM = """You are a sketch planner for sparse black-line drawings.
Return JSON only. No markdown.

The drawer is a separate model. You give STRUCTURE, not a tracing template.
Never output grid cells like x12y20, never list numeric coordinates, never give pixel positions.
Describe regions in words: top / middle / bottom, left / center / right, and rough fractions of the canvas
(e.g. "head occupies the upper fifth, roughly centered").

Keep 6–12 strokes. Cute simple silhouette over completeness.
Characters/animals: two short vertical-line eyes if the face shows; no circular pupils.
Ellipses = two connecting arcs (two stroke entries). Circles close. One stroke per rod for parallel parts.
Joints may be slightly loose; do not CAD-snap."""


def plan_user(task: dict) -> str:
    reqs = "; ".join(r["description"] for r in task["requirements"])
    return f"""Plan a sparse black-line sketch. One subject only.

concept: {task['concept']}
prompt: {task['prompt']}
must communicate: {reqs}

Return JSON:
{{
  "concept": "{task['concept']}",
  "viewpoint": "short viewpoint, e.g. side view facing left",
  "layout_notes": "where the subject sits on the page using words and fractions, not cells",
  "strokes": [
    {{
      "id": "s1",
      "name": "part name",
      "how": "circle|ellipse_two_arcs|line|zigzag|corner_polyline|curve",
      "region": "e.g. upper center; about one-fifth of the canvas tall",
      "notes": "shape/pose hint only, no coordinates"
    }}
  ]
}}

Hard rules:
- Do NOT write cells (xNyM), numbers as coordinates, or t_values.
- Stroke count 6–12.
- Order strokes as a sensible draw order.
- Pose and facing must be readable from the regions."""


CELL_RE = re.compile(r"x\d+y\d+", re.I)


def plan_has_cells(plan: dict) -> bool:
    blob = json.dumps(plan, ensure_ascii=False)
    return bool(CELL_RE.search(blob))


def call_planner(task: dict, env: dict[str, str]) -> dict:
    raw = call_glm(
        [
            {"role": "system", "content": PLAN_SYSTEM},
            {"role": "user", "content": plan_user(task)},
        ],
        max_tokens=4096,
        temperature=0.4,
        reasoning_effort="low",
        timeout=180,
        env=env,
    )
    plan = parse_json_obj(raw)
    if not isinstance(plan.get("strokes"), list) or len(plan["strokes"]) < 3:
        raise ValueError(f"bad plan strokes: {plan.get('strokes')!r}"[:200])
    if plan_has_cells(plan):
        raise ValueError("plan still contains grid cells; reject")
    for s in plan["strokes"]:
        if s.get("approx_points") or s.get("t_hint"):
            raise ValueError("plan still has approx_points/t_hint; reject")
    plan["task_id"] = task["task_id"]
    plan["planner"] = env.get("ZHIPU_MODEL", "glm-5.3")
    plan["reasoning_effort"] = "low"
    return plan


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", nargs="*", default=None, help="task_ids to mint for review only")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    env = load_env()
    all_tasks = load_jsonl(DATA / "train.jsonl") + load_jsonl(DATA / "holdout.jsonl")
    by_id = {t["task_id"]: t for t in all_tasks}
    if args.sample is not None:
        ids = args.sample or ["tr_obj_desk_lamp_side", "tr_pe_happy_waving_person"]
        tasks = [by_id[i] for i in ids]
        out = Path(args.out) if args.out else DATA / "plans_coarse_samples.jsonl"
        out.write_text("", encoding="utf-8")
    else:
        tasks = all_tasks
        out = Path(args.out) if args.out else OUT
    pending = list(tasks)
    print(f"minting {len(pending)} plans -> {out}", flush=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    errors = []
    rows = []
    for i, task in enumerate(pending, 1):
        last_err = None
        for attempt in range(6):
            try:
                t0 = time.time()
                plan = call_planner(task, env)
                rows.append(plan)
                print(
                    f"[{i}/{len(pending)}] {task['task_id']} strokes={len(plan['strokes'])} {time.time()-t0:.1f}s",
                    flush=True,
                )
                last_err = None
                time.sleep(1)
                break
            except KeyboardInterrupt:
                raise
            except Exception as e:
                last_err = e
                wait = 12 * (attempt + 1)
                print(
                    f"[{i}/{len(pending)}] {task['task_id']} retry {attempt+1}: {type(e).__name__}: {e}; sleep {wait}s",
                    flush=True,
                )
                time.sleep(wait)
        if last_err is not None:
            errors.append((task["task_id"], str(last_err)))
    out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(rows)} plans)", flush=True)
    if errors:
        raise SystemExit(f"still missing {len(errors)} plans: {errors}")


if __name__ == "__main__":
    main()
