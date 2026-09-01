from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = next(
    (parent for parent in HERE.parents if (parent / "versions" / "path2d_v1").exists()),
    HERE.parents[1],
)
for p in (ROOT, ROOT / "versions" / "path2d_v1", HERE):
    sp = str(p)
    if sp in sys.path:
        sys.path.remove(sp)
    sys.path.insert(0, sp)

from interp import expand_timeline, frames_to_redraw, interpolate_scene, points_to_path, resample
from path2d.parser import parse_path2d
from path2d.schema import Path2DScene
from prompts import DRAWER_ORIENTATION, INBETWEEN_REASONING, KEY_PLAN_SYSTEM, SUITE, TASKS, inbetween_oneshot_prompt, key_draw_prompt, key_plan_user, previous_key_context


class Path2DTests(unittest.TestCase):
    def test_parse_and_scene(self) -> None:
        cmds = parse_path2d("M -0.2 0.1 L 0.2 0.1 Z")
        self.assertEqual(cmds[0].command, "M")
        scene = Path2DScene.from_dict(
            {
                "prompt": "t",
                "strokes": [{"id": "a", "path": "M 0 0 L 0.1 0.2", "description": "line"}],
            }
        )
        self.assertEqual(len(scene.strokes), 1)

    def test_tasks_and_lerp(self) -> None:
        for name in (
            "kick",
            "basketball",
            "badminton",
            "dogwalk",
            "catwalk",
            "catjump",
            "boxing",
            "highfive",
            "creek",
            "fish",
            "rabbithop",
            "bottleshot",
        ):
            self.assertIn(name, TASKS)
            user = key_plan_user(TASKS[name], n_keys=3)
            self.assertIn("Key", user)
            self.assertIn("people_scale", user)
            self.assertIn("1/5–1/4", user)
        self.assertEqual(len(SUITE), 5)
        self.assertEqual(SUITE, ("bounce", "billiards", "bottleshot", "badminton", "catjump"))
        for name in SUITE:
            self.assertIn(name, TASKS)
        bounce_user = key_plan_user(TASKS["bounce"], n_keys=3)
        self.assertIn("SECOND hop", bounce_user)
        self.assertIn("squash", bounce_user.lower())
        pool_user = key_plan_user(TASKS["billiards"], n_keys=3)
        self.assertIn("almost STOPPED", pool_user)
        bottle_user = key_plan_user(TASKS["bottleshot"], n_keys=3)
        self.assertIn("BARREL", bottle_user)
        self.assertIn("VISIBLY EXPLODED", bottle_user)
        cat_user = key_plan_user(TASKS["catwalk"], n_keys=3)
        self.assertIn("crown", cat_user.lower())
        self.assertIn("higher y", cat_user.lower())
        jump_user = key_plan_user(TASKS["catjump"], n_keys=3)
        self.assertIn("table", jump_user.lower())
        self.assertIn("crown", jump_user.lower())
        bare = key_plan_user(TASKS["dogwalk"], n_keys=3, fewshot=False)
        self.assertNotIn("Staging:", bare)
        self.assertNotIn("person_head", bare)
        self.assertNotIn("ellipse", bare.lower())
        self.assertIn("one-shot", KEY_PLAN_SYSTEM)
        ib = inbetween_oneshot_prompt(
            {
                "action": "walk",
                "layout_notes": "",
                "people_scale": "small",
                "parts": [{"id": "a", "name": "a", "how": "line", "motion": "moving"}],
                "keys": [
                    {"name": "start", "beat": "ready", "notes": "stand"},
                    {"name": "end", "beat": "contact then leave", "notes": "object just left the striker"},
                ],
                "gaps": [{"after": "start", "n_inbetween": 4, "why": "carry the traveler into the hit"}],
            },
            {
                "from": "start",
                "to": "end",
                "current_frame": 2,
                "from_frame": 1,
                "to_frame": 6,
                "n_frames": 11,
                "ease": "linear",
            },
            {"strokes": [{"id": "a", "path": "M 0 0 L 0.1 0", "description": "a"}]},
            {"strokes": [{"id": "a", "path": "M 0.2 0 L 0.3 0", "description": "a"}]},
        )
        self.assertIn("2D INBETWEEN", ib)
        self.assertIn("M/L/Q/C/Z", ib)
        self.assertIn("FROM is the already-drawn previous frame 1", ib)
        self.assertIn("TO is the next key, which is frame 6", ib)
        self.assertIn("draw frame 2", ib)
        self.assertNotIn("C3", ib)
        self.assertNotIn("Advance the pose one step", ib)
        self.assertIn("collision course", ib)
        self.assertIn("BEFORE the TO key", ib)
        self.assertIn("carry the traveler into the hit", ib)
        self.assertIn("upside-down", ib)
        self.assertNotIn("REDRAW NOTE", ib)
        ib_fix = inbetween_oneshot_prompt(
            {
                "action": "walk",
                "layout_notes": "",
                "people_scale": "small",
                "parts": [{"id": "a", "name": "a", "how": "line", "motion": "moving"}],
                "keys": [
                    {"name": "start", "beat": "ready", "notes": "stand"},
                    {"name": "end", "beat": "contact then leave", "notes": "object just left the striker"},
                ],
                "gaps": [{"after": "start", "n_inbetween": 4, "why": "carry the traveler into the hit"}],
            },
            {
                "from": "start",
                "to": "end",
                "current_frame": 2,
                "from_frame": 1,
                "to_frame": 6,
                "n_frames": 11,
                "ease": "linear",
            },
            {"strokes": [{"id": "a", "path": "M 0 0 L 0.1 0", "description": "a"}]},
            {"strokes": [{"id": "a", "path": "M 0.2 0 L 0.3 0", "description": "a"}]},
            fix_note="keep FROM height; do not flatten the body",
        )
        self.assertIn("REDRAW NOTE (hard): keep FROM height; do not flatten the body", ib_fix)
        kd = key_draw_prompt(
            {
                "action": "walk",
                "layout_notes": "side",
                "people_scale": "small",
                "parts": [{"id": "a", "name": "a", "how": "line", "motion": "moving"}],
            },
            {
                "name": "start",
                "beat": "contact",
                "notes": "lean",
                "parts": [{"id": "a", "path": "M -0.47 0.17 L 0 0 Z"}],
            },
            1,
            3,
        )
        self.assertIn("upside-down", kd)
        self.assertNotIn("M -0.47 0.17", kd)
        kd_prev = key_draw_prompt(
            {
                "action": "walk",
                "layout_notes": "side",
                "people_scale": "small",
                "parts": [{"id": "a", "name": "a", "how": "line", "motion": "moving"}],
            },
            {"name": "contact", "beat": "hit", "notes": "kick"},
            2,
            3,
            prev_scene={"strokes": [{"id": "a", "path": "M 0 0 L 0.2 0", "description": "a"}]},
            prev_name="start",
        )
        self.assertIn("PREVIOUS KEY 'start'", kd_prev)
        self.assertIn("M 0 0 L 0.2 0", kd_prev)
        kd_exp = key_draw_prompt(
            {
                "action": "walk",
                "layout_notes": "side",
                "people_scale": "small",
                "parts": [{"id": "a", "name": "a", "how": "line", "motion": "moving"}],
            },
            {"name": "contact", "beat": "hit", "notes": "kick"},
            2,
            3,
            prev_scene={"strokes": [{"id": "a", "path": "M 0 0 L 0.2 0", "description": "a"}]},
            prev_name="start",
            experience={
                "ok": False,
                "rules": ["Do not close the torso with Z.", "Do not attach arms at the head center."],
            },
        )
        self.assertIn("CAUTION RULES", kd_exp)
        self.assertIn("Do not close the torso", kd_exp)
        self.assertIn("not shown any previous drawing", kd_exp)
        self.assertNotIn("PREVIOUS KEY", kd_exp)
        self.assertNotIn("M 0 0 L 0.2 0", kd_exp)
        kd_exp_blind = key_draw_prompt(
            {
                "action": "walk",
                "layout_notes": "side",
                "people_scale": "small",
                "parts": [{"id": "a", "name": "a", "how": "line", "motion": "moving"}],
            },
            {"name": "contact", "beat": "hit", "notes": "kick"},
            2,
            3,
            experience={"ok": False, "rules": ["Do not freeze the torso."]},
        )
        self.assertNotIn("PREVIOUS KEY", kd_exp_blind)
        self.assertIn("left-right", DRAWER_ORIENTATION)
        self.assertIn("same size", DRAWER_ORIENTATION)
        self.assertIn("Q", DRAWER_ORIENTATION)
        self.assertIn("CROWN", DRAWER_ORIENTATION)
        self.assertIn("polygons of L", DRAWER_ORIENTATION)
        self.assertIn("LAST point", DRAWER_ORIENTATION)
        self.assertIn("BOTTOM of the head", DRAWER_ORIENTATION)
        self.assertIn("M neck Q hip", DRAWER_ORIENTATION)
        self.assertIn("never above the head", DRAWER_ORIENTATION)
        self.assertIn("planted foot", DRAWER_ORIENTATION)
        self.assertIn("Connectivity", DRAWER_ORIENTATION)
        self.assertIn("elbow/knee", DRAWER_ORIENTATION)
        self.assertIn("rump", DRAWER_ORIENTATION)
        self.assertIn("Q/C for swinging", DRAWER_ORIENTATION)
        self.assertIn("GROUND STROKE LENGTH", DRAWER_ORIENTATION)
        self.assertIn("emitting end", DRAWER_ORIENTATION)
        self.assertIn("relative placement", DRAWER_ORIENTATION.lower())
        self.assertIn("GROUND LINE LENGTH", KEY_PLAN_SYSTEM)
        self.assertIn("ORIENTATION", KEY_PLAN_SYSTEM)
        self.assertIn("UNCHANGING", KEY_PLAN_SYSTEM)
        self.assertIn("how much TIME", KEY_PLAN_SYSTEM)
        self.assertIn("stocky-vs-slim", DRAWER_ORIENTATION)
        self.assertIn("planned duration", INBETWEEN_REASONING)
        self.assertIn("LEFT END", TASKS["badminton"]["staging"])
        self.assertIn("oval", TASKS["badminton"]["staging"].lower())
        self.assertIn("TWO-WAY", TASKS["badminton"]["staging"])
        self.assertIn("Last key: left contact again", TASKS["badminton"]["staging"])
        for blob in (KEY_PLAN_SYSTEM.lower(), DRAWER_ORIENTATION.lower(), INBETWEEN_REASONING.lower()):
            for leak in (
                "badminton",
                "paddle",
                "shuttle",
                "racket",
                "court",
                "opposite ends",
                "gun",
                "hoop",
                "bottle",
                "goal",
                "hook",
                "cue",
            ):
                self.assertNotIn(leak, blob)
        self.assertIn("first key is frame 1", KEY_PLAN_SYSTEM)
        self.assertIn("last key is the last frame", KEY_PLAN_SYSTEM)
        self.assertIn("drawable strokes only", KEY_PLAN_SYSTEM)
        self.assertIn("WHOLE-BODY", KEY_PLAN_SYSTEM)
        self.assertIn("Whole-body motion", DRAWER_ORIENTATION)
        self.assertIn("torso coils", TASKS["kick"]["staging"])
        self.assertIn("head center", previous_key_context(
            {"strokes": [{"id": "a", "path": "M 0 0 L 0.1 0", "description": "a"}]},
            prev_name="start",
            key_i=2,
        ))
        self.assertIn("Open centerlines", DRAWER_ORIENTATION)
        self.assertIn("pose notes only", KEY_PLAN_SYSTEM)
        prev = previous_key_context(
            {"strokes": [{"id": "a", "path": "M 0 0 L 0.1 0", "description": "a"}]},
            prev_name="start",
            key_i=2,
        )
        self.assertIn("PREVIOUS KEY 'start'", prev)
        self.assertIn("key 1", prev)
        self.assertIn("M 0 0 L 0.1 0", prev)
        a = {
            "prompt": "t",
            "strokes": [{"id": "ball", "path": "M -0.4 -0.6 L -0.35 -0.6", "description": "ball", "group": "ball"}],
        }
        b = {
            "prompt": "t",
            "strokes": [{"id": "ball", "path": "M 0.4 0.1 L 0.45 0.1", "description": "ball", "group": "ball"}],
        }
        mid = interpolate_scene(a, b, 0.5)
        self.assertIn("L", mid["strokes"][0]["path"])
        self.assertGreater(len(resample([(0.0, 0.0), (1.0, 0.0)], 5)), 2)
        self.assertTrue(points_to_path([(0.0, 0.0), (1.0, 0.0)]).startswith("M"))

    def test_timeline(self) -> None:
        tl = expand_timeline([{"name": "a"}, {"name": "b"}], [{"n_inbetween": 2, "ease": "linear"}])
        self.assertEqual([x["kind"] for x in tl], ["key", "inbetween", "inbetween", "key"])
        self.assertEqual(frames_to_redraw(tl, 2, cascade=False), [2])
        self.assertEqual(frames_to_redraw(tl, 2, cascade=True), [2, 3])
        self.assertEqual(frames_to_redraw(tl, 1, cascade=True), [1, 2, 3])
        self.assertEqual(frames_to_redraw(tl, 4, cascade=True), [4])
        with self.assertRaises(ValueError):
            frames_to_redraw(tl, 9, cascade=False)
        self.assertEqual(tl[1]["from_frame"], 1)
        self.assertEqual(tl[1]["to_frame"], 4)
        self.assertEqual(tl[1]["current_frame"], 2)

    def test_rebuild_clip_previews(self) -> None:
        from tempfile import TemporaryDirectory

        from glm_anim_2d import rebuild_clip_previews, save_scene

        tl = expand_timeline([{"name": "a"}, {"name": "b"}], [{"n_inbetween": 1, "ease": "linear"}])
        scene = {
            "prompt": "t",
            "strokes": [{"id": "ground", "path": "M -1 -0.7 L 1 -0.7", "description": "g"}],
        }
        with TemporaryDirectory() as tmp:
            out = Path(tmp)
            for slot in tl:
                dest = out / "frames" / f"f{int(slot['i']):02d}"
                save_scene(scene, dest, width=64, height=64)
                (dest / "view.png").unlink()
            gif, sheet = rebuild_clip_previews(out, tl, width=64, height=64, gif_ms=80)
            self.assertTrue(gif.exists())
            self.assertTrue(sheet.exists())
            self.assertGreater(gif.stat().st_size, 0)
            self.assertGreater(sheet.stat().st_size, 0)
            for slot in tl:
                self.assertTrue((out / "frames" / f"f{int(slot['i']):02d}" / "view.png").exists())

    def test_path2d_patch_and_incremental_loop(self) -> None:
        from tempfile import TemporaryDirectory

        from incremental import Path2DIncrementalLoop, Path2DPatch, PlannerReview, apply_path2d_patch

        empty = {"prompt": "t", "strokes": []}
        added = apply_path2d_patch(
            empty,
            {
                "delete_stroke_ids": [],
                "update_strokes": [],
                "add_strokes": [{"id": "a", "path": "M 0 0 L 0.2 0", "description": "a"}],
                "summary": "add",
            },
        )
        self.assertEqual(added["strokes"][0]["id"], "a")
        moved = apply_path2d_patch(
            added,
            Path2DPatch.from_dict(
                {
                    "delete_stroke_ids": [],
                    "add_strokes": [],
                    "update_strokes": [{"id": "a", "path": "M 0.1 0.2 L 0.3 0.2", "description": "a"}],
                    "summary": "move",
                }
            ),
        )
        self.assertIn("0.1", moved["strokes"][0]["path"])
        reused = apply_path2d_patch(
            moved,
            {
                "delete_stroke_ids": ["a"],
                "add_strokes": [{"id": "a", "path": "M 0.4 0 L 0.5 0", "description": "a"}],
                "update_strokes": [],
                "summary": "reuse id",
            },
        )
        self.assertEqual(len(reused["strokes"]), 1)
        self.assertIn("0.4", reused["strokes"][0]["path"])

        class FakePlanner:
            def create_plan(self, *, prompt: str) -> dict:
                return {"overall_goal": "draw a line"}

            def review(self, **kwargs):
                if int(kwargs["round_index"]) == 1:
                    return PlannerReview.from_dict(
                        {
                            "decision": "continue",
                            "assessment": {"strengths": [], "problems": ["blank"]},
                            "instruction": {
                                "objective": "Draw the line",
                                "priority": "structure",
                                "success_criteria": ["a line is visible"],
                            },
                            "rollback_revision": None,
                            "reason": "empty",
                        }
                    )
                return PlannerReview.from_dict(
                    {
                        "decision": "finish",
                        "assessment": {"strengths": ["line"], "problems": []},
                        "instruction": None,
                        "rollback_revision": None,
                        "reason": "done",
                    }
                )

            def select_best(self, *, prompt, plan, revisions):
                return revisions[0]["revision_id"], "only"

        class FakeEditor:
            def edit(self, **kwargs):
                return (
                    Path2DPatch.from_dict(
                        {
                            "delete_stroke_ids": [],
                            "update_strokes": [],
                            "add_strokes": [{"id": "a", "path": "M -0.2 0 L 0.2 0", "description": "line"}],
                            "summary": "add line",
                        }
                    ),
                    "{}",
                )

        with TemporaryDirectory() as td:
            out = Path(td) / "run"
            result = Path2DIncrementalLoop(
                output_dir=out,
                planner=FakePlanner(),
                editor=FakeEditor(),
                max_rounds=3,
                width=64,
                height=64,
            ).run("a horizontal line")
            self.assertEqual(result.status, "complete")
            self.assertTrue((out / "final" / "scene.json").exists())
            scene = json.loads((out / "final" / "scene.json").read_text(encoding="utf-8"))
            self.assertEqual(scene["strokes"][0]["id"], "a")

    def test_pin_skips_mislabeled_limbs(self) -> None:
        from interp import pin_anchored_scene

        plan = {
            "parts": [
                {"id": "ground", "motion": "anchored"},
                {"id": "person_plant_leg", "motion": "anchored"},
                {"id": "person_torso", "motion": "moving"},
            ]
        }
        key1 = {
            "prompt": "t",
            "strokes": [
                {"id": "ground", "path": "M -1 -0.7 L 1 -0.7", "description": "g"},
                {"id": "person_torso", "path": "M 0 0.2 L 0 -0.2", "description": "t"},
                {"id": "person_plant_leg", "path": "M 0 -0.2 L 0 -0.7", "description": "leg"},
            ],
        }
        later = {
            "prompt": "t",
            "strokes": [
                {"id": "ground", "path": "M -0.5 -0.5 L 0.5 -0.5", "description": "moved ground"},
                {"id": "person_torso", "path": "M 0.1 0.2 L 0.1 -0.2", "description": "lean"},
                {"id": "person_plant_leg", "path": "M 0.1 -0.2 L 0.05 -0.7", "description": "attached"},
            ],
        }
        pinned = pin_anchored_scene(later, key1, plan)
        by_id = {s["id"]: s["path"] for s in pinned["strokes"]}
        self.assertEqual(by_id["ground"], "M -1 -0.7 L 1 -0.7")
        self.assertEqual(by_id["person_plant_leg"], "M 0.1 -0.2 L 0.05 -0.7")
        self.assertEqual(by_id["person_torso"], "M 0.1 0.2 L 0.1 -0.2")

    def test_key_experience_schema(self) -> None:
        from key_reflect import should_redraw, validate_experience

        ok = validate_experience({"ok": True, "rules": []})
        self.assertTrue(ok["ok"])
        self.assertFalse(should_redraw(ok))
        bad = validate_experience(
            {"ok": False, "rules": ["Do not draw the head as an L polygon."]}
        )
        self.assertTrue(should_redraw(bad))
        aliased = validate_experience(
            {"ok": False, "avoid": ["Do not freeze the torso upright."]}
        )
        self.assertEqual(aliased["rules"], ["Do not freeze the torso upright."])
        with self.assertRaises(ValueError):
            validate_experience({"ok": False, "rules": []})
        with self.assertRaises(ValueError):
            validate_experience(
                {"ok": False, "rules": ["Move person_leg to M -0.2 0.1 L 0 0"]}
            )


if __name__ == "__main__":
    unittest.main()
