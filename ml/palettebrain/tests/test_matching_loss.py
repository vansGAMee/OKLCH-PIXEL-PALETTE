from __future__ import annotations

import math
import unittest


DEPENDENCY_ERROR: Exception | None = None
try:
    import numpy as np
    import torch

    from ml.palettebrain.color_math import (
        representation_to_oklab,
        representation_to_oklab_numpy,
    )
    from ml.palettebrain.matching import match_free_targets
    from ml.palettebrain.train_decoder import decoder_loss
except (ImportError, SystemExit) as exc:  # pragma: no cover - environment gate
    DEPENDENCY_ERROR = exc


def _logit(value: float) -> float:
    clipped = min(1.0 - 1e-5, max(1e-5, value))
    return math.log(clipped / (1.0 - clipped))


def _color(
    lightness: float,
    relative_chroma: float,
    hue_degrees: float,
    importance: float = 0.5,
) -> list[float]:
    angle = math.radians(hue_degrees)
    relative_lightness = (lightness - 0.07) / 0.86
    return [
        _logit(relative_lightness),
        _logit(relative_chroma),
        math.sin(angle),
        math.cos(angle),
        importance,
    ]


def _palette(*colors: list[float]):
    tensor = torch.zeros((1, 9, 5), dtype=torch.float32)
    for index, color in enumerate(colors):
        tensor[0, index] = torch.tensor(color)
    count_mask = torch.zeros((1, 9), dtype=torch.float32)
    count_mask[0, : len(colors)] = 1.0
    return tensor, count_mask


def _scalar(value) -> float:
    return float(value.detach())


@unittest.skipIf(DEPENDENCY_ERROR is not None, f"ML dependencies unavailable: {DEPENDENCY_ERROR}")
class DecoderMatchingLossTests(unittest.TestCase):
    def test_torch_and_numpy_physical_decoders_agree(self) -> None:
        representation, _ = _palette(
            _color(0.20, 0.75, 359.0),
            _color(0.50, 0.01, 90.0),
            _color(0.88, 0.55, 220.0),
        )
        representation[0, 1, 2:4] = 0.0

        torch_oklab = representation_to_oklab(representation).numpy()
        numpy_oklab = representation_to_oklab_numpy(representation.numpy())

        np.testing.assert_allclose(torch_oklab, numpy_oklab, atol=1e-6, rtol=1e-6)

    def test_free_palette_loss_is_permutation_invariant(self) -> None:
        target, count_mask = _palette(
            _color(0.25, 0.65, 20.0),
            _color(0.55, 0.45, 145.0),
            _color(0.82, 0.70, 275.0),
        )
        locked_mask = torch.zeros_like(count_mask)
        ordered = target.clone().requires_grad_(True)
        permuted = target.clone()
        permuted[0, :3] = target[0, torch.tensor([2, 0, 1])]
        permuted.requires_grad_(True)

        ordered_loss, _ = decoder_loss(ordered, target, count_mask, locked_mask)
        permuted_loss, components = decoder_loss(
            permuted, target, count_mask, locked_mask
        )

        self.assertAlmostEqual(
            _scalar(permuted_loss), _scalar(ordered_loss), places=6
        )
        self.assertAlmostEqual(_scalar(components["lightness"]), 0.0, places=6)
        self.assertAlmostEqual(_scalar(components["chroma"]), 0.0, places=6)
        self.assertAlmostEqual(_scalar(components["hue"]), 0.0, places=6)
        permuted_loss.backward()
        self.assertTrue(torch.isfinite(permuted.grad).all())

    def test_locked_target_stays_bound_and_is_excluded_from_free_pool(self) -> None:
        target, count_mask = _palette(
            _color(0.20, 0.60, 15.0),
            _color(0.50, 0.55, 135.0),
            _color(0.82, 0.65, 255.0),
        )
        locked_mask = torch.zeros_like(count_mask)
        locked_mask[0, 0] = 1.0

        free_permutation = target.clone()
        free_permutation[0, 1] = target[0, 2]
        free_permutation[0, 2] = target[0, 1]
        _, free_components = decoder_loss(
            free_permutation, target, count_mask, locked_mask
        )
        self.assertAlmostEqual(float(free_components["lightness"]), 0.0, places=6)
        self.assertAlmostEqual(float(free_components["chroma"]), 0.0, places=6)
        self.assertAlmostEqual(float(free_components["hue"]), 0.0, places=6)

        steals_locked_color = target.clone()
        steals_locked_color[0, 0] = target[0, 1]
        steals_locked_color[0, 1] = target[0, 0]
        predicted_oklab = representation_to_oklab(steals_locked_color)
        target_oklab = representation_to_oklab(target)
        aligned, _ = match_free_targets(
            target,
            predicted_oklab,
            target_oklab,
            count_mask,
            locked_mask,
        )
        self.assertTrue(torch.equal(aligned[0, 0], target[0, 0]))

        _, stolen_components = decoder_loss(
            steals_locked_color, target, count_mask, locked_mask
        )
        self.assertGreater(float(stolen_components["lightness"]), 0.0)
        self.assertGreater(float(stolen_components["lockedLightness"]), 0.0)

    def test_hue_loss_wraps_across_zero_degrees(self) -> None:
        target, count_mask = _palette(
            _color(0.42, 0.75, 359.0),
            _color(0.76, 0.50, 180.0),
        )
        output = target.clone()
        output[0, 0, 2] = math.sin(math.radians(1.0))
        output[0, 0, 3] = math.cos(math.radians(1.0))

        _, components = decoder_loss(
            output, target, count_mask, torch.zeros_like(count_mask)
        )

        self.assertGreater(float(components["hue"]), 0.0)
        self.assertLess(float(components["hue"]), 0.001)

    def test_neutral_targets_do_not_supervise_arbitrary_hue(self) -> None:
        target, count_mask = _palette(
            _color(0.25, 1e-5, 0.0),
            _color(0.75, 1e-5, 90.0),
        )
        output = target.clone()
        output[0, 0, 2:4] = torch.tensor([0.0, -1.0])
        output[0, 1, 2:4] = torch.tensor([-1.0, 0.0])

        _, components = decoder_loss(
            output, target, count_mask, torch.zeros_like(count_mask)
        )

        self.assertAlmostEqual(float(components["hue"]), 0.0, places=7)

    def test_duplicate_penalty_excludes_locked_and_inactive_slots(self) -> None:
        target, count_mask = _palette(
            _color(0.45, 0.60, 40.0),
            _color(0.45, 0.60, 40.0),
        )
        output = target.clone()
        locked_mask = torch.zeros_like(count_mask)
        locked_mask[0, 0] = 1.0

        _, locked_components = decoder_loss(
            output, target, count_mask, locked_mask
        )
        _, free_components = decoder_loss(
            output, target, count_mask, torch.zeros_like(count_mask)
        )

        self.assertEqual(float(locked_components["duplicatePenalty"]), 0.0)
        self.assertGreater(float(free_components["duplicatePenalty"]), 0.0)

    def test_importance_channel_never_changes_candidate_loss(self) -> None:
        target, count_mask = _palette(
            _color(0.30, 0.60, 30.0, importance=0.0),
            _color(0.72, 0.55, 220.0, importance=1.0),
        )
        output = target.clone()
        first_loss, first_components = decoder_loss(
            output, target, count_mask, torch.zeros_like(count_mask)
        )

        changed_output = output.clone()
        changed_output[..., 4] = 100.0
        changed_target = target.clone()
        changed_target[..., 4] = -100.0
        second_loss, second_components = decoder_loss(
            changed_output,
            changed_target,
            count_mask,
            torch.zeros_like(count_mask),
        )

        self.assertEqual(float(first_components["importance"]), 0.0)
        self.assertEqual(float(second_components["importance"]), 0.0)
        self.assertEqual(float(second_components["importanceWeight"]), 0.0)
        self.assertAlmostEqual(float(first_loss), float(second_loss), places=7)


if __name__ == "__main__":
    unittest.main()
