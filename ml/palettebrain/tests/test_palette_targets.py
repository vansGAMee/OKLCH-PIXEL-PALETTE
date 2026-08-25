from __future__ import annotations

import unittest
import json
from pathlib import Path

import numpy as np

from ml.palettebrain.palette_targets import (
    family_palette,
    hex_to_oklab,
    hex_palette_target,
    perceptual_subset,
)
from ml.palettebrain.color_math import oklch_to_srgb


class PaletteTargetTests(unittest.TestCase):
    def test_frozen_python_browser_physical_fixture(self) -> None:
        fixture_path = Path("ml/palettebrain/physical_color_parity.v1.json")
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        tolerance = float(fixture["tolerance"])
        for case in fixture["hexCases"]:
            np.testing.assert_allclose(
                hex_to_oklab(case["hex"]), case["oklab"], atol=tolerance
            )
        for case in fixture["oklchCases"]:
            np.testing.assert_allclose(
                oklch_to_srgb(*case["oklch"]), case["srgb"], atol=tolerance
            )

    def test_culori_oklab_reference_colors(self) -> None:
        np.testing.assert_allclose(
            hex_to_oklab("#ff0000"),
            np.asarray([0.627955, 0.224863, 0.125846]),
            atol=2e-6,
        )
        np.testing.assert_allclose(
            hex_to_oklab("#0000ff"),
            np.asarray([0.452014, -0.032457, -0.311528]),
            atol=2e-6,
        )

    def test_reduction_keeps_value_extremes_and_requested_count(self) -> None:
        colors = ["#111111", "#303030", "#808080", "#d0d0d0", "#ffffff"]
        reduced = perceptual_subset(colors, 3)
        self.assertEqual(len(reduced), 3)
        self.assertIn("#111111", reduced)
        self.assertIn("#ffffff", reduced)

    def test_reduction_refuses_palette_expansion(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not invent"):
            perceptual_subset(["#000000", "#ffffff"], 3)

    def test_family_targets_cover_every_native_count(self) -> None:
        for count in range(2, 10):
            target, locks = family_palette("#e31b35", count, family="red")
            self.assertEqual(target.shape, (9, 5))
            self.assertEqual(locks.shape, (9, 4))
            self.assertTrue(np.isfinite(target).all())
            self.assertTrue(np.allclose(target[count:], 0.0))

    def test_source_order_does_not_create_importance_labels(self) -> None:
        target, _ = hex_palette_target(["#000000", "#ffffff"])
        self.assertTrue(np.all(target[:, 4] == 0.0))


if __name__ == "__main__":
    unittest.main()
