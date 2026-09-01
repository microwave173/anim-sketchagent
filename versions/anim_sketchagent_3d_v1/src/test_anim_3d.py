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
    validate_key_plan,
)
from glm_ds_roles import ANIM_EDITOR_SYSTEM_PROMPT, GlmDsPlanner
from prompts import KEY_PLAN_SYSTEM, SUITE, TASKS, key_draw_prompt, key_plan_user, previous_key_context


PLAN = {
    "action": "A player releases one ball while a fixed hoop stays at the right side of the scene.",
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
        for name in ("tabledrop", "stairs", "soccer", "pillar_peek", "ball_door", "elevator", "crane_gap", "badminton", "fireworks", "catwalk"):
            self.assertIn(name, TASKS)
            self.assertTrue(TASKS[name]["staging"])
        text = key_plan_user(TASKS["tabledrop"], n_keys=3, pin_frames=12)
        self.assertIn("FAR lip", text)
        self.assertIn("FLOOR", text)
        stairs = key_plan_user(TASKS["stairs"], n_keys=3)
        self.assertIn("MIDDLE tread", stairs)
        fw = key_plan_user(TASKS["fireworks"], n_keys=3)
        self.assertIn("Choose any bloom shape", fw)
        self.assertNotIn("into a spherical star", fw)
        from prompts import inbetween_prompt
        ib = inbetween_prompt(
            {"action": "walk", "layout_notes": "", "parts": [{"id": "a", "name": "a", "how": "line", "motion": "moving"}]},
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
        badminton_plan = key_plan_user(TASKS["badminton"], n_keys=3)
        self.assertIn("one running step", badminton_plan)
        self.assertIn("3/5 of the court WIDTH", badminton_plan)
        draw_badminton = key_draw_prompt(
            {
                "parts": [{"id": "left_head", "name": "h", "how": "circle", "motion": "moving"}],
                "action": "rally",
                "people_scale": TASKS["badminton"]["people_scale"],
            },
            {"name": "left_contact", "beat": "hit"},
            1,
            3,
        )
        self.assertIn("3/5 of the court WIDTH", draw_badminton)

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


if __name__ == "__main__":
    unittest.main()
