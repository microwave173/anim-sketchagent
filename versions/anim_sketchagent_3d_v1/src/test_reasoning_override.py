"""Check that an explicit effort reaches visual editing and inbetween calls."""
import json
import unittest
from unittest.mock import patch

import glm_ds_roles
import oneshot_glm


class ReasoningOverrideTests(unittest.TestCase):
    def test_max_enables_thinking_for_visual_role(self):
        with patch.object(glm_ds_roles, "REASONING_EFFORT_OVERRIDE", "max"), patch.object(
            glm_ds_roles, "call_deepseek", return_value='{"ok":true}'
        ) as call:
            glm_ds_roles._call_json(system="test", content="test", vision=True, max_tokens=4096)
        self.assertEqual(call.call_args.kwargs["reasoning_effort"], "max")
        self.assertTrue(call.call_args.kwargs["thinking"])
        self.assertGreaterEqual(call.call_args.kwargs["max_tokens"], 65536)

    def test_default_visual_role_remains_non_thinking(self):
        with patch.object(glm_ds_roles, "REASONING_EFFORT_OVERRIDE", None), patch.object(
            glm_ds_roles, "call_deepseek", return_value='{"ok":true}'
        ) as call:
            glm_ds_roles._call_json(system="test", content="test", vision=True, max_tokens=4096)
        self.assertFalse(call.call_args.kwargs["thinking"])

    def test_max_enables_thinking_for_oneshot_inbetween(self):
        raw=json.dumps({"prompt":"test", "strokes":[{"id":"a", "path":"M 0 0 0 L 0.2 0 0", "description":"line"}]})
        with patch.object(oneshot_glm, "REASONING_EFFORT_OVERRIDE", "max"), patch.object(
            oneshot_glm, "call_deepseek", return_value=raw
        ) as call:
            oneshot_glm.generate_scene("test")
        self.assertEqual(call.call_args.kwargs["reasoning_effort"], "max")
        self.assertTrue(call.call_args.kwargs["thinking"])


if __name__=="__main__":unittest.main()
