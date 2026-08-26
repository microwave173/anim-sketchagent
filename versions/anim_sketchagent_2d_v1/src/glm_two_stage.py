#!/usr/bin/env python3
"""Previous pipeline: GLM-5.3 plans JSON, then a second GLM call draws XML only."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from drawer_prompts import SYSTEM, plan_text, user_prompt
from loop_metrics import format_loop_report, measure_loops
from mint_plans import PLAN_SYSTEM, plan_has_cells, plan_user
from anim_prompts import ANIMAL_PLAN_SYSTEM, ANIMAL_STILL_DRAW_SYSTEM, animal_still_user_prompt, is_animal_task
from sa_render import convert_completion
from terra_client import call_glm, parse_json_obj

DEFAULT_IDS = (
    "tr_obj_desk_lamp_side",
    "tr_an_cat_sit_left",
    "tr_pe_happy_waving_person",
    "tr_an_penguin_stand_front",
)


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def mint_plan(task: dict) -> tuple[dict | None, str, str | None]:
    plan_sys = ANIMAL_PLAN_SYSTEM if is_animal_task(task) else PLAN_SYSTEM
    raw = call_glm(
        [
            {"role": "system", "content": plan_sys},
            {"role": "user", "content": plan_user(task)},
        ],
        max_tokens=2048,
        temperature=0.4,
        reasoning_effort="low",
        timeout=180,
    )
    err = None
    plan = None
    try:
        plan = parse_json_obj(raw)
        if not isinstance(plan.get("strokes"), list) or len(plan["strokes"]) < 3:
            raise ValueError("need >=3 strokes")
        if plan_has_cells(plan):
            raise ValueError("plan contains grid cells")
        plan["task_id"] = task["task_id"]
        plan["planner"] = "glm-5.3-two-stage"
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        plan = None
    return plan, raw, err


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", nargs="+", default=list(DEFAULT_IDS))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    data = HERE / "data"
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = Path(args.out) if args.out else HERE / "outputs" / f"glm53_two_stage_{stamp}"
    out.mkdir(parents=True, exist_ok=True)
    tasks = {t["task_id"]: t for t in read_jsonl(data / "train.jsonl") + read_jsonl(data / "holdout.jsonl")}
    rows = []
    for task_id in args.ids:
        if task_id not in tasks:
            raise SystemExit(f"unknown task_id {task_id}")
        task = tasks[task_id]
        print(f"== {task_id} plan ==", flush=True)
        t0 = time.time()
        plan, plan_raw, plan_err = mint_plan(task)
        plan_s = round(time.time() - t0, 2)
        (out / f"{task_id}.plan.raw.txt").write_text(plan_raw, encoding="utf-8")
        if plan is not None:
            (out / f"{task_id}.plan.json").write_text(
                json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        print(f"  plan {plan_s}s ok={plan is not None} {plan_err or ''}", flush=True)
        rec = {"valid": False, "intact": False, "n_strokes": 0, "error": "no plan"}
        draw_s = 0.0
        raw = ""
        loops = []
        if plan is not None:
            print(f"== {task_id} draw ==", flush=True)
            t1 = time.time()
            animal = is_animal_task(task)
            draw_sys = ANIMAL_STILL_DRAW_SYSTEM if animal else SYSTEM
            draw_user = animal_still_user_prompt(task, plan_text(plan)) if animal else user_prompt(task, plan_text(plan))
            raw = call_glm(
                [
                    {"role": "system", "content": draw_sys},
                    {"role": "user", "content": draw_user},
                ],
                max_tokens=4096,
                temperature=0.7,
                reasoning_effort="low",
                timeout=180,
            )
            draw_s = round(time.time() - t1, 2)
            (out / f"{task_id}.raw.txt").write_text(raw, encoding="utf-8")
            rec = convert_completion(raw, out / f"{task_id}.png")
            loops = measure_loops(raw)
            print(
                f"  draw {draw_s}s valid={rec.get('valid')} intact={rec.get('intact')} "
                f"strokes={rec.get('n_strokes')} chars={len(raw)}",
                flush=True,
            )
            if rec.get("error"):
                print(f"  render: {rec['error']}", flush=True)
            if loops:
                print(format_loop_report(loops), flush=True)
        rows.append(
            {
                "task_id": task_id,
                "plan_seconds": plan_s,
                "draw_seconds": draw_s,
                "plan_ok": plan is not None,
                "plan_error": plan_err,
                "plan_n_strokes": len(plan["strokes"]) if plan else 0,
                "has_plan_tag": "<plan>" in raw.lower(),
                "valid": rec.get("valid"),
                "intact": rec.get("intact"),
                "n_strokes": rec.get("n_strokes"),
                "error": rec.get("error"),
                "loops": loops,
            }
        )
    (out / "summary.json").write_text(
        json.dumps({"model": "glm-5.3", "pipeline": "plan_then_draw", "rows": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"wrote {out / 'summary.json'}", flush=True)


if __name__ == "__main__":
    main()
