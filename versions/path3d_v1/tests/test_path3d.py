from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops

from path3d.geometry import sample_stroke
from path3d.generator import (
    SPATIAL_CIRCLE_Q3_EXAMPLE_PATH,
    SPATIAL_S_CURVE_C3_EXAMPLE_PATH,
    SYSTEM_PROMPT,
)
from path3d.parser import parse_path3d
from path3d.renderer import Camera, render_scene_views, view_metrics
from path3d.schema import Path3DScene, Path3DStroke


class Path3DParserTest(unittest.TestCase):
    def test_system_prompt_format_example_is_valid(self):
        commands = parse_path3d(SPATIAL_S_CURVE_C3_EXAMPLE_PATH)
        self.assertEqual([item.command for item in commands], ["M", "C"])
        self.assertIn("C3 always has exactly 9 numbers", SYSTEM_PROMPT)
        self.assertIn("Do not use the 2D SVG commands Q or C", SYSTEM_PROMPT)
        self.assertIn("[control 1], [control 2], [endpoint]", SYSTEM_PROMPT)
        self.assertIn(SPATIAL_S_CURVE_C3_EXAMPLE_PATH, SYSTEM_PROMPT)

    def test_spatial_s_curve_is_nonplanar_and_reverses_xy_bend(self):
        commands = parse_path3d(SPATIAL_S_CURVE_C3_EXAMPLE_PATH)
        values = np.asarray(commands[1].values).reshape(3, 3)
        p0 = np.asarray(commands[0].values)
        p1, p2, p3 = values
        volume = np.linalg.det(np.stack((p1 - p0, p2 - p0, p3 - p0)))
        self.assertGreater(abs(float(volume)), 0.5)

        def derivative(t):
            return 3 * (1 - t) ** 2 * (p1 - p0) + 6 * (1 - t) * t * (p2 - p1) + 3 * t ** 2 * (p3 - p2)

        def second_derivative(t):
            return 6 * (1 - t) * (p2 - 2 * p1 + p0) + 6 * t * (p3 - 2 * p2 + p1)

        turns = []
        for t in (0.2, 0.8):
            first, second = derivative(t), second_derivative(t)
            turns.append(float(first[0] * second[1] - first[1] * second[0]))
        self.assertLess(turns[0] * turns[1], 0)

    def test_spatial_circle_prompt_example_is_valid_closed_q3_path(self):
        commands = parse_path3d(SPATIAL_CIRCLE_Q3_EXAMPLE_PATH)
        self.assertEqual(sum(item.command == "Q" for item in commands), 8)
        sampled = sample_stroke(
            Path3DStroke("circle", SPATIAL_CIRCLE_Q3_EXAMPLE_PATH, "format example"),
            curve_steps=16,
        ).polylines[0]
        self.assertTrue(np.allclose(sampled[0], sampled[-1]))
        self.assertIn(SPATIAL_CIRCLE_Q3_EXAMPLE_PATH, SYSTEM_PROMPT)

    def test_q3_and_c3_normalize_to_internal_bezier_commands(self):
        commands = parse_path3d(
            "M 0 0 0 Q3 0 1 0 1 1 0 C3 1 1 1 0 1 1 0 0 1"
        )
        self.assertEqual([item.command for item in commands], ["M", "Q", "C"])

    def test_parses_all_commands_and_multiple_subpaths(self):
        commands = parse_path3d(
            "M 0 0 0 L 1 0 0 Q 1 1 0 0 1 0 C 0 1 1 1 0 1 1 0 0 Z M 0 0 1 L 1 1 1"
        )
        self.assertEqual([item.command for item in commands], ["M", "L", "Q", "C", "Z", "M", "L"])

    def test_supports_svg_style_implicit_repeated_coordinate_groups(self):
        commands = parse_path3d("M 0 0 0 1 0 0 1 1 0 L 0 1 0 0 0 0")
        self.assertEqual([item.command for item in commands], ["M", "L", "L", "L", "L"])
        self.assertEqual(commands[-1].values, (0.0, 0.0, 0.0))

    def test_rejects_relative_or_wrong_arity(self):
        with self.assertRaisesRegex(ValueError, "uppercase"):
            parse_path3d("m 0 0 0 L 1 1 1")
        with self.assertRaisesRegex(ValueError, "groups of 9"):
            parse_path3d("M 0 0 0 C 1 1 1 2 2 2")

    def test_samples_true_three_dimensional_bezier(self):
        stroke = Path3DStroke("curve", "M 0 0 0 C 0 1 0 1 1 1 1 0 1", "3D curve")
        sampled = sample_stroke(stroke, curve_steps=8).polylines[0]
        self.assertEqual(sampled.shape, (9, 3))
        self.assertTrue(np.allclose(sampled[0], [0, 0, 0]))
        self.assertTrue(np.allclose(sampled[-1], [1, 0, 1]))
        self.assertGreater(float(sampled[:, 1].max()), 0.5)


class Path3DRendererTest(unittest.TestCase):
    def test_renders_nonblank_distinct_multiview_images(self):
        scene = Path3DScene("corner", (
            Path3DStroke("corner", "M -1 0 0 L 1 0 0 L 1 1 1", "3D corner", stroke_width=5),
        ))
        with tempfile.TemporaryDirectory() as temp:
            paths = render_scene_views(scene, Path(temp), width=160, height=160)
            self.assertEqual(len(paths), 4)
            images = [Image.open(path).convert("RGB") for path in paths]
            for image in images:
                self.assertIsNotNone(ImageChops.difference(image, Image.new("RGB", image.size, "white")).getbbox())
            self.assertIsNotNone(ImageChops.difference(images[0], images[1]).getbbox())
            self.assertTrue((Path(temp) / "contact_sheet.png").is_file())

    def test_view_metrics_report_coverage_and_clipping(self):
        scene = Path3DScene("wide", (Path3DStroke("line", "M -1 0 0 L 1 0 0", "wide line"),))
        camera = Camera("orthographic", (0, -4, 0), projection="orthographic")
        metrics = view_metrics(scene, camera, width=200, height=100, normalize=False)
        self.assertGreater(metrics["width_fraction"], 0.35)
        self.assertFalse(any(metrics["clipped"].values()))
        close = Camera("close", (0, -4, 0), focal=12)
        clipped = view_metrics(scene, close, width=200, height=100, normalize=False)
        self.assertTrue(clipped["clipped"]["left"] or clipped["clipped"]["right"])


if __name__ == "__main__":
    unittest.main()
