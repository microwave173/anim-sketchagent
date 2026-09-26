from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from glm_anim_3d import (
    expand_timeline,
    pin_anchored_scene,
    require_scene_contract,
    scene_contract_report,
    normalize_key_plan_timing,
    validate_key_plan,
)
from glm_ds_roles import ANIM_EDITOR_SYSTEM_PROMPT, GlmDsPlanner
from prompts import ANIMAL_DRAWING, KEY_PLAN_SYSTEM, SUITE, TASKS, key_draw_prompt, key_plan_user, previous_key_context
from path3d.renderer import DEFAULT_CAMERAS
from render_orbit_clip import looping_yaws, orbit_camera, render_orbit_clip


PLAN = {
    "action": "A player releases one ball while a fixed hoop stays at the right side of the scene.",
    "notes": "Fixed player scale; hoop stays right.",
    "parts": [
        {"id": "person", "name": "person", "motion": "moving"},
        {"id": "ball", "name": "ball", "motion": "moving"},
        {"id": "hoop", "name": "hoop", "motion": "anchored"},
    ],
    "keys": [{"name": "start"}, {"name": "end"}],
    "gaps": [{"after": "start", "n_inbetween": 2, "ease": "smooth"}],
}


def scene(*, hoop_path: str = "M 0.8 0 0 L 0.8 0 0.8") -> dict:
    return {
        "prompt": "test",
        "strokes": [
            {"id": "person", "path": "M -0.5 0 0 L -0.5 0 0.5", "description": "person"},
            {"id": "person_arm", "path": "M -0.5 0 0.4 L -0.2 0 0.5", "description": "arm"},
            {"id": "ball", "path": "M -0.1 0 0.5 L -0.08 0 0.5", "description": "ball"},
            {"id": "hoop", "path": hoop_path, "description": "hoop"},
        ],
        "metadata": {},
    }


class Anim3DContractTests(unittest.TestCase):
    def test_depth_tasks_are_registered_with_staging(self) -> None:
        self.assertEqual(len(SUITE), 5)
        self.assertEqual(SUITE, ("tabledrop", "stairs", "ball_door", "elevator", "fireworks"))
        for name in SUITE:
            self.assertIn(name, TASKS)
            self.assertTrue(TASKS[name]["staging"])
        for name in ("tabledrop", "stairs", "soccer", "pillar_peek", "parkour", "ball_door", "elevator", "crane_gap", "badminton", "fireworks", "catwalk", "starwars", "cmp_hoop", "cmp_horse", "cmp_punch"):
            self.assertIn(name, TASKS)
            self.assertTrue(TASKS[name]["staging"])
        sw = key_plan_user(TASKS["starwars"], n_keys=3)
        self.assertIn("DEFLECT CONTACT", sw)
        self.assertIn("FARTHER", sw)
        parkour = key_plan_user(TASKS["parkour"], n_keys=3)
        self.assertIn("VAULT", parkour)
        self.assertIn("BOX", parkour)
        text = key_plan_user(TASKS["tabledrop"], n_keys=3, pin_frames=12)
        self.assertIn("sampled pose, not an automatic pause", text)
        self.assertIn("Do not add extra schema fields", text)
        self.assertIn("FAR lip", text)
        self.assertIn("FLOOR", text)
        stairs = key_plan_user(TASKS["stairs"], n_keys=3)
        self.assertIn("MIDDLE tread", stairs)
        fw = key_plan_user(TASKS["fireworks"], n_keys=3)
        self.assertIn("Choose any bloom shape", fw)
        self.assertNotIn("into a spherical star", fw)
        from prompts import inbetween_prompt
        ib = inbetween_prompt(
            {"action": "walk", "notes": "Fixed scale.", "parts": [{"id": "a", "name": "a", "how": "line", "motion": "moving"}]},
            {
                "from": "k1",
                "to": "k2",
                "t": 0.5,
                "ease": "linear",
                "current_frame": 2,
                "from_frame": 1,
                "to_frame": 4,
                "n_frames": 4,
            },
            {"strokes": [{"id": "a", "path": "M 0 0 0 L 1 0 0"}]},
            {"strokes": [{"id": "a", "path": "M 0 0 0 L 2 0 0"}]},
        )
        self.assertIn("incremental Path3D", ib)
        self.assertIn("FROM is the already-drawn previous frame 1", ib)
        self.assertIn("TO is the next key, which is frame 4", ib)
        self.assertIn("draw frame 2", ib)
        self.assertNotIn("Advance the pose one step", ib)
        self.assertIn("collision course", ib)
        self.assertIn("BEFORE the TO key", ib)
        self.assertIn("Pick exactly 3 keys", text)
        self.assertIn("first key is frame 1", KEY_PLAN_SYSTEM)
        self.assertIn("last key is the last frame", KEY_PLAN_SYSTEM)
        self.assertIn("DIRECTOR rewrite", KEY_PLAN_SYSTEM)
        self.assertIn("Relative placement", KEY_PLAN_SYSTEM)
        self.assertIn("ON TOP of the head", KEY_PLAN_SYSTEM)
        self.assertIn("one concise notes field", KEY_PLAN_SYSTEM)
        self.assertIn("higher z", KEY_PLAN_SYSTEM)
        self.assertIn("ON TOP of the head", key_plan_user(TASKS["walk"], n_keys=3))
        self.assertIn(ANIMAL_DRAWING, KEY_PLAN_SYSTEM)
        self.assertIn("Legs default SHORT", KEY_PLAN_SYSTEM)
        self.assertIn("OBVIOUSLY readable", KEY_PLAN_SYSTEM)
        self.assertIn("Never change line thickness or color", KEY_PLAN_SYSTEM)
        self.assertIn("World axes (hard)", ANIMAL_DRAWING)
        self.assertIn("along +z", ANIMAL_DRAWING)
        self.assertIn("behind along +y", ANIMAL_DRAWING)
        self.assertIn("Four views (hard)", ANIMAL_DRAWING)
        self.assertIn("higher z than the head-center", ANIMAL_DRAWING)
        sys_l = KEY_PLAN_SYSTEM.lower()
        for leak in (
            "opposite ends",
            "hoop",
            "elevator",
            "firework",
            "crane",
            "badminton",
            "soccer",
            "net is one",
            "domino",
        ):
            self.assertNotIn(leak, sys_l)
        prev = previous_key_context(
            {"strokes": [{"id": "a", "path": "M 0 0 0 L 1 0 0", "description": "a"}]},
            prev_name="start",
            key_i=2,
        )
        self.assertIn("PREVIOUS KEY 'start'", prev)
        self.assertIn("M 0 0 0 L 1 0 0", prev)
        self.assertIn("REUSE those exact same IDs", ANIM_EDITOR_SYSTEM_PROMPT)
        self.assertIn("actor_head_new", ANIM_EDITOR_SYSTEM_PROMPT)
        self.assertNotIn("adding new IDs in the same patch", ANIM_EDITOR_SYSTEM_PROMPT)
        draw = key_draw_prompt(
            {"parts": [{"id": "walker_head", "name": "h", "how": "circle", "motion": "moving"}], "action": "x"},
            {"name": "emerge", "beat": "right"},
            3,
            3,
        )
        self.assertIn("Do not rename parts between keys", draw)
        self.assertIn("zero-length M stroke", draw)
        self.assertNotIn("chain of tipping rigid tiles", draw)
        self.assertIn(ANIMAL_DRAWING, draw)
        self.assertIn("short vertical tick", draw)
        draw_prev = key_draw_prompt(
            {"parts": [{"id": "walker_head", "name": "h", "how": "circle", "motion": "moving"}], "action": "x"},
            {"name": "stride", "beat": "walk"},
            2,
            3,
            prev_scene={"strokes": [{"id": "walker_head", "path": "M 0 0 0 L 0 0 0.1", "description": "h"}]},
            prev_name="start",
        )
        self.assertIn("PREVIOUS KEY 'start'", draw_prev)
        self.assertIn("M 0 0 0 L 0 0 0.1", draw_prev)
        draw_anchor = key_draw_prompt(
            {
                "parts": [{"id": "walker_head", "name": "h", "how": "circle", "motion": "moving"}],
                "action": "walk",
                "keys": [
                    {"name": "start", "beat": "depart", "notes": "move +y"},
                    {"name": "middle", "beat": "continue", "notes": "keep +y"},
                    {"name": "late", "beat": "continue", "notes": "still +y"},
                    {"name": "end", "beat": "settle", "notes": "land"},
                ],
            },
            {"name": "late", "beat": "continue", "notes": "still +y"},
            3,
            4,
            prev_scene={"strokes": [{"id": "walker_head", "path": "M 0 .2 0 L 0 .3 .1", "description": "previous"}]},
            prev_name="middle",
            anchor_scene={"strokes": [{"id": "walker_head", "path": "M 0 0 0 L 0 0 .1", "description": "model sheet"}]},
            anchor_name="start",
        )
        self.assertIn("MOTION NEIGHBORHOOD", draw_anchor)
        self.assertIn('"next": {"name": "end"', draw_anchor)
        self.assertIn("IDENTITY ANCHOR 'start'", draw_anchor)
        self.assertIn("immediate PREVIOUS KEY controls current position and motion", draw_anchor)
        badminton_plan = key_plan_user(TASKS["badminton"], n_keys=3)
        self.assertIn("one running step", badminton_plan)
        self.assertIn("3/5 of the court WIDTH", badminton_plan)
        draw_badminton = key_draw_prompt(
            {
                "parts": [{"id": "left_head", "name": "h", "how": "circle", "motion": "moving"}],
                "action": "rally",
                "notes": TASKS["badminton"]["people_scale"],
            },
            {"name": "left_contact", "beat": "hit"},
            1,
            3,
        )
        self.assertIn("3/5 of the court WIDTH", draw_badminton)

    def test_planner_schema_and_timing_normalization(self) -> None:
        user = key_plan_user(TASKS["walk"], n_keys=12, pin_frames=120)
        self.assertIn('"notes"', user)
        self.assertNotIn("pacing_summary", user)
        malformed = {
            "action": "A readable multi-stage three-dimensional action crosses the scene and ends with a clear consequence.",
            "notes": "Fixed small figure; clear depth lane.",
            "parts": [{"id": "p", "name": "p", "how": "line", "motion": "moving"}],
            "keys": [{"name": f"k{i}"} for i in range(12)],
            "gaps": [{"after": "k0", "n_inbetween": 3, "ease": "smooth", "why": "start"}],
        }
        fixed = normalize_key_plan_timing(malformed, n_keys=12, pin_frames=120, frame_duration_ms=100)
        self.assertEqual(len(fixed["gaps"]), 11)
        self.assertEqual(sum(g["n_inbetween"] for g in fixed["gaps"]), 108)
        self.assertTrue(all(1 <= g["n_inbetween"] <= 10 for g in fixed["gaps"]))
        self.assertEqual([g["after"] for g in fixed["gaps"]], [f"k{i}" for i in range(11)])

    def test_expand_timeline_uses_planned_gap(self) -> None:
        timeline = expand_timeline(PLAN["keys"], PLAN["gaps"])
        self.assertEqual([item["kind"] for item in timeline], ["key", "inbetween", "inbetween", "key"])
        self.assertAlmostEqual(timeline[1]["t"], 1 / 3)
        self.assertAlmostEqual(timeline[2]["t"], 2 / 3)
        self.assertEqual(timeline[1]["from_frame"], 1)
        self.assertEqual(timeline[1]["to_frame"], 4)
        self.assertEqual(timeline[-1]["i"], timeline[-1]["to_frame"])

    def test_validate_plan_keeps_free_length(self) -> None:
        value = validate_key_plan(
            {**PLAN, "parts": list(PLAN["parts"]), "keys": list(PLAN["keys"]), "gaps": [dict(PLAN["gaps"][0])]},
            None,
            {"part_range": (3, 5)},
        )
        self.assertEqual(value["n_frames"], 4)

    def test_scene_contract_accepts_prefixed_helpers(self) -> None:
        report = require_scene_contract(scene(), PLAN, label="test")
        self.assertTrue(report["ok"])
        self.assertEqual(report["unknown_ids"], [])

    def test_scene_contract_rejects_missing_canonical_id(self) -> None:
        value = scene()
        value["strokes"] = [item for item in value["strokes"] if item["id"] != "person_arm"]
        report = scene_contract_report(value, PLAN, canonical_ids={"person", "person_arm", "ball", "hoop"})
        self.assertFalse(report["ok"])
        self.assertEqual(report["canonical_missing"], ["person_arm"])

    def test_pin_anchored_scene_uses_first_key_geometry(self) -> None:
        first = scene()
        changed = scene(hoop_path="M 0 0 0 L 0 0 0.2")
        pinned = pin_anchored_scene(changed, first, PLAN)
        hoop = next(item for item in pinned["strokes"] if item["id"] == "hoop")
        self.assertEqual(hoop["path"], "M 0.8 0 0 L 0.8 0 0.8")
        self.assertEqual(pinned["metadata"]["animation_anchors_pinned_from"], "first_key")

    def test_visual_review_falls_back_after_two_invalid_directives(self) -> None:
        with TemporaryDirectory() as tmp:
            sheet = Path(tmp) / "sheet.png"
            sheet.write_bytes(b"not decoded by the role")
            with patch("glm_ds_roles._call_json", return_value=({}, "")) as call:
                review = GlmDsPlanner().review(
                    prompt="draw the planned pose",
                    plan={"steps": []},
                    current_contact_sheet=sheet,
                    round_index=1,
                    max_rounds=4,
                    current_revision="revision_000",
                    trajectory=[],
                    history=[],
                )
        self.assertEqual(call.call_count, 2)
        self.assertEqual(review.decision, "continue")
        self.assertIsNotNone(review.instruction)


class Anim3DOrbitTests(unittest.TestCase):
    def test_orbit_starts_at_perspective_and_yaws_90(self) -> None:
        base = next(cam for cam in DEFAULT_CAMERAS if cam.name == "perspective")
        start = orbit_camera(0.0, yaw_degrees=90.0)
        end = orbit_camera(1.0, yaw_degrees=90.0)
        self.assertAlmostEqual(start.position[0], base.position[0], places=6)
        self.assertAlmostEqual(start.position[1], base.position[1], places=6)
        self.assertAlmostEqual(start.position[2], base.position[2], places=6)
        x, y, z = base.position
        self.assertAlmostEqual(end.position[0], -y, places=6)
        self.assertAlmostEqual(end.position[1], x, places=6)
        self.assertAlmostEqual(end.position[2], z, places=6)
        full = orbit_camera(1.0, yaw_degrees=360.0)
        self.assertAlmostEqual(full.position[0], x, places=6)
        self.assertAlmostEqual(full.position[1], y, places=6)
        yaws = looping_yaws(11, degrees_per_cycle=60.0)
        self.assertEqual(len(yaws), 66)
        self.assertAlmostEqual(yaws[0], 0.0)
        self.assertAlmostEqual(yaws[11], 60.0)
        self.assertLess(yaws[-1], 360.0)
        self.assertAlmostEqual(yaws[1] - yaws[0], 360.0 / 66)

    def test_orbit_clip_writes_gif_without_touching_original(self) -> None:
        from path3d.schema import Path3DScene

        with TemporaryDirectory() as tmp:
            run = Path(tmp) / "clip"
            for i, x in enumerate((-0.4, 0.4), start=1):
                dest = run / "frames" / f"f{i:02d}"
                dest.mkdir(parents=True)
                scene = Path3DScene.from_dict(
                    {
                        "prompt": "orbit test",
                        "strokes": [
                            {"id": "ground", "path": "M -1 0 0 L 1 0 0", "description": "ground"},
                            {"id": "post", "path": f"M {x} 0 0 L {x} 0 0.8", "description": "post"},
                        ],
                    }
                )
                (dest / "scene.json").write_text(scene.to_json(), encoding="utf-8")
            (run / "clip.gif").write_bytes(b"gif")
            meta = render_orbit_clip(run, width=64, height=64, gif_ms=80)
            self.assertTrue(Path(meta["gif"]).is_file())
            self.assertNotEqual(Path(meta["gif"]).name, "clip.gif")
            self.assertEqual((run / "clip.gif").read_bytes(), b"gif")
            self.assertEqual(meta["anim_loops"], 6)
            self.assertEqual(meta["n_scene_frames"], 2)
            self.assertEqual(meta["n_frames"], 12)
            self.assertAlmostEqual(meta["cameras"][0]["yaw_degrees"], 0.0)
            self.assertAlmostEqual(meta["cameras"][2]["yaw_degrees"], 60.0)
            self.assertAlmostEqual(meta["cameras"][-1]["yaw_degrees"], 330.0)
            self.assertEqual(meta["cameras"][0]["anim_frame"], 1)
            self.assertEqual(meta["cameras"][1]["anim_frame"], 2)
            self.assertEqual(meta["cameras"][2]["anim_frame"], 1)
            self.assertTrue((run / "orbit_frames" / "f001.png").is_file())

            once = render_orbit_clip(run, width=64, height=64, gif_ms=80, once=True)
            self.assertEqual(once["n_frames"], 2)
            self.assertAlmostEqual(once["cameras"][-1]["yaw_degrees"], 60.0)


if __name__ == "__main__":
    unittest.main()
