# Gold clips + naive full-draw ablation

This folder keeps the **good pose-to-pose clips** in one place so later prompt or code edits cannot overwrite them. The ablation below asks: *if we keep the same prompts and the same 12-frame budget, does drawing every frame with GLM beat (or even match) sparse keys + geometric inbetweens?*

## What is frozen here

Date: 2026-08-25. Model: GLM-5.3. Grid: SketchAgent 50×50, origin top-left.

| alias | prompt (one line) | why it was kept | original run |
|---|---|---|---|
| `kick` | Penalty kick: plant, foot hits a ball, ball flies up-right | Clean detach; ball leaves the foot | `outputs/glm53_keys_anim_stick_penalty_kick_20260825_015841/` |
| `throw` | Overhand snowball throw | Release is a key; projectile identity holds | `outputs/glm53_keys_anim_stick_snowball_throw_20260825_015912/` |
| `jump` | Leap a small creek, two anchored banks | Body launches; pads should not slide | `outputs/glm53_keys_anim_stick_creek_jump_20260825_015940/` |
| `highfive` | Two friends jump and clap | Two-person contact without merging bodies | `outputs/glm53_keys_anim_stick_jumping_highfive_20260825_020010/` |
| `sit` | Sit down on a park bench | Bench stays put; pose folds | `outputs/glm53_keys_anim_stick_sit_bench_20260825_020051/` |
| `archery` | Full draw, then arrow leaves the string | Prop detach + short wind-up | `outputs/glm53_keys_anim_stick_archery_20260825_020121/` |
| `pickup` | Pick a gift box off the ground and hug it | Parenting: box idle, then rises with the hands | `outputs/glm53_keys_anim_stick_pickup_gift_20260825_020159/` |
| `fish` | Yank a tiny fish out of the water; it leaps off | Surprise detach, not a second person | `outputs/glm53_keys_anim_stick_lucky_catch_20260825_020227/` |
| `sword` | Sword cut with a T-hilt; attacker head lunges; victim flies | Extra keeper from the earlier fight probe (hilt + moving head + even swing) | `outputs/glm53_keys_anim_stick_sword_cut_20260825_015226/` |

Copies live under `pose_to_pose/<alias>/`. Each copy has at least `clip.gif`, `contact_sheet.png`, `summary.json`, `plan.json`, and the key XML.

## Method A (gold): pose-to-pose + lerp

Script: `glm_anim_keys.py`.

1. Planner emits **3 keys** (sword: 4) and gap sizes. No grid cells in the plan.
2. Drawer draws **only those keys**.
3. Named strokes are **lerped** into 12 frames. Ground / bench / water are pinned so scenery does not crawl.
4. GIF is 80 ms/frame.

This is the method that produced the clips above.

## Method B (ablation): naive full redraw

Script: `glm_anim_two_stage.py`. Same `TASKS` prompts, same 12 frames, same 80 ms GIF.

1. Planner emits a **pose for every frame** (still no cells).
2. Drawer **redraws every frame** in SketchAgent XML, using the previous frame only as a proportion hint.
3. No geometric inbetweens, no forced gaps, no code-side ground pin.

This is the earlier “LLM draws each SketchAgent frame” probe, not CSS/SDS on a still.

This ablation run (same 8 prompts, 12 frames, 80 ms GIF):

`outputs/ablation_naive_full_draw_20260825_022314/`

Each subfolder (`kick/`, `throw/`, …) has `clip.gif` next to the gold copy under `pose_to_pose/<alias>/clip.gif`.

Look-at protocol (eyes first, not metrics):

- Identity: is it the same person / ball / box, or a new drawing each frame?
- Contact / detach: does the hit, release, or grasp actually happen, or does the prop smear?
- Anchored lines: does the ground or bench drift?
- Timing: does one stage whip and the next crawl?

A fair kill for Method A is: Method B already looks as stable on detach/contact, so keys+lerp are not buying identity.

## How to re-run

```bash
cd experiments/grpo_sa_pilot

# Method A (will write a NEW stamp under outputs/; it will not touch gold/)
python3 run_key_suite.py

# Method B
python3 run_naive_suite.py
```

Manifest: `manifest.json`.
