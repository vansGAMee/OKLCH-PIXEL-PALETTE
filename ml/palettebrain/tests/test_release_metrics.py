from __future__ import annotations

import copy
import unittest

import numpy as np

from ml.palettebrain.release_metrics import (
    aggregate_direct_prompt_scores,
    deterministic_palette_equality,
    hungarian_matched_set_distance,
    load_color_family_fixture,
    match_required_families,
    matches_family,
    near_duplicate_palette_rate,
    palette_has_near_duplicate,
    palette_to_oklab,
    score_direct_prompt,
    score_exclusions,
    summarize_matched_set_distances,
    summarize_modifier_sensitivity,
    summarize_ru_en_parity,
)


class ReleaseMetricTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = load_color_family_fixture()
        cls.red = np.asarray(
            cls.fixture["families"]["red"]["oklabPrototypes"][0]
        )
        cls.blue = np.asarray(
            cls.fixture["families"]["blue"]["oklabPrototypes"][0]
        )
        cls.green = np.asarray(
            cls.fixture["families"]["green"]["oklabPrototypes"][0]
        )
        cls.cyan = np.asarray(
            cls.fixture["families"]["cyan"]["oklabPrototypes"][0]
        )
        cls.purple = np.asarray(
            cls.fixture["families"]["purple"]["oklabPrototypes"][0]
        )

    def prompt_case(self, case_id: str) -> dict[str, object]:
        return next(case for case in self.fixture["prompts"] if case["id"] == case_id)

    def test_consistent_red_passes_but_lucky_red_slot_does_not(self) -> None:
        consistent = np.vstack(
            (
                self.red,
                self.fixture["families"]["red"]["oklabPrototypes"][1],
                self.fixture["families"]["red"]["oklabPrototypes"][2],
                [0.12, 0.0, 0.0],
                [0.90, 0.0, 0.0],
            )
        )
        lucky_nonsense = np.vstack(
            (self.red, self.blue, self.green, self.cyan, self.purple)
        )

        good = score_direct_prompt(consistent, self.prompt_case("red-en"))
        bad = score_direct_prompt(lucky_nonsense, self.prompt_case("red-en"))

        self.assertTrue(good["required_passed"])
        self.assertTrue(good["consistency_passed"])
        self.assertTrue(good["passed"])
        self.assertTrue(bad["required_passed"])
        self.assertEqual(bad["consistency"]["ratio"], 0.8)
        self.assertFalse(bad["consistency_passed"])
        self.assertFalse(bad["passed"])

    def test_red_and_blue_require_distinct_generated_colors(self) -> None:
        one_slot = match_required_families([self.red], ["red", "blue"])
        two_slots = match_required_families(
            [self.blue, self.red], ["red", "blue"]
        )

        self.assertFalse(one_slot["passed"])
        self.assertEqual(one_slot["matched_count"], 1)
        self.assertEqual(len(one_slot["unmatched_families"]), 1)
        self.assertTrue(two_slots["passed"])
        self.assertEqual(
            len({item["color_index"] for item in two_slots["assignments"]}), 2
        )

    def test_exclusions_use_the_frozen_tighter_distance(self) -> None:
        red_exclusion = score_exclusions([self.red], ["red"])
        blue_exclusion = score_exclusions([self.blue], ["red"])

        self.assertFalse(red_exclusion["passed"])
        self.assertEqual(red_exclusion["violations"][0]["color_index"], 0)
        self.assertTrue(blue_exclusion["passed"])

    def test_black_white_and_gray_use_physical_ranges_not_hue(self) -> None:
        self.assertTrue(matches_family([0.19, 0.039, 0.0], "black"))
        self.assertFalse(matches_family([0.21, 0.0, 0.0], "black"))
        self.assertTrue(matches_family([0.86, -0.02, 0.02], "white"))
        self.assertFalse(matches_family([0.84, 0.0, 0.0], "white"))
        self.assertTrue(matches_family([0.50, 0.0, -0.039], "gray"))
        self.assertFalse(matches_family([0.80, 0.0, 0.0], "gray"))
        self.assertFalse(matches_family([0.50, 0.041, 0.0], "gray"))

    def test_near_duplicate_rate_uses_fixture_threshold_strictly(self) -> None:
        duplicate = [[0.50, 0.0, 0.0], [0.524, 0.0, 0.0]]
        distinct = [[0.50, 0.0, 0.0], [0.526, 0.0, 0.0]]

        self.assertTrue(palette_has_near_duplicate(duplicate))
        self.assertFalse(palette_has_near_duplicate(distinct))
        summary = near_duplicate_palette_rate([duplicate, distinct])
        self.assertEqual(summary["rate"], 0.5)
        self.assertEqual(summary["threshold"], 0.025)

        custom = copy.deepcopy(self.fixture)
        custom["thresholds"]["nearDuplicateOklabDistance"] = 0.02
        self.assertFalse(palette_has_near_duplicate(duplicate, fixture=custom))

    def test_hungarian_distance_is_palette_permutation_invariant(self) -> None:
        palette = np.vstack((self.red, self.blue, [0.5, 0.0, 0.0]))
        permuted = palette[[2, 0, 1]]

        self.assertEqual(hungarian_matched_set_distance(palette, permuted), 0.0)
        with self.assertRaisesRegex(ValueError, "same number"):
            hungarian_matched_set_distance(palette, permuted[:2])

    def test_holdout_summary_flattens_all_hungarian_color_matches(self) -> None:
        summary = summarize_matched_set_distances(
            [
                [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
                [[0.0, 0.0, 0.0]],
            ],
            [
                [[0.0, 0.0, 0.0], [0.3, 0.0, 0.0]],
                [[0.3, 0.0, 0.0]],
            ],
        )
        self.assertEqual(summary["matched_color_count"], 3)
        self.assertAlmostEqual(summary["mean_distance"], 0.2)
        self.assertAlmostEqual(summary["median_distance"], 0.3)
        self.assertAlmostEqual(summary["mean_set_distance"], 0.225)

    def test_direct_prompt_aggregation_reports_ru_and_en_separately(self) -> None:
        en = score_direct_prompt([self.red], self.prompt_case("red-en"))
        ru = score_direct_prompt([self.blue], self.prompt_case("red-ru"))
        summary = aggregate_direct_prompt_scores([en, ru])

        self.assertEqual(summary["raw_direct_color"]["accuracy"], 0.5)
        self.assertEqual(
            summary["raw_direct_color_by_language"]["en"]["accuracy"], 1.0
        )
        self.assertEqual(
            summary["raw_direct_color_by_language"]["ru"]["accuracy"], 0.0
        )

    def test_modifier_and_translation_summaries_pair_same_seed(self) -> None:
        base = np.vstack((self.red, [0.2, 0.0, 0.0]))
        changed = base.copy()
        changed[0, 0] -= 0.06
        modifier = summarize_modifier_sensitivity(
            {
                "grape": {1: base, 7: base},
                "dirty grape": {1: changed, 7: changed},
            }
        )
        self.assertEqual(modifier["evaluated_pair_count"], 1)
        self.assertEqual(modifier["sample_count"], 2)
        self.assertEqual(modifier["perceptible_change_rate"], 1.0)

        parity = summarize_ru_en_parity(
            {
                "red": {1: base},
                "красный": {1: base[[1, 0]]},
            }
        )
        self.assertEqual(parity["evaluated_pair_count"], 1)
        self.assertEqual(parity["mean_distance"], 0.0)
        self.assertEqual(parity["mean_family_agreement"], 1.0)

    def test_determinism_is_exact_and_ordered(self) -> None:
        palette = np.vstack((self.red, self.blue))
        self.assertTrue(deterministic_palette_equality(palette, palette.copy()))
        self.assertFalse(deterministic_palette_equality(palette, palette[::-1]))
        changed = palette.copy()
        changed[0, 0] = np.nextafter(changed[0, 0], 1.0)
        self.assertFalse(deterministic_palette_equality(palette, changed))

    def test_oklch_inputs_are_converted_to_physical_oklab(self) -> None:
        converted = palette_to_oklab([[0.5, 0.1, 90.0]], color_space="oklch")
        np.testing.assert_allclose(converted, [[0.5, 0.0, 0.1]], atol=1e-15)


if __name__ == "__main__":
    unittest.main()
