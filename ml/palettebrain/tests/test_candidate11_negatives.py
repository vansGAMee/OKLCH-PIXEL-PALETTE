from __future__ import annotations

import numpy as np

from ml.palettebrain.build_c11_dataset import (
    NEGATIVE_SELECTION_VERSION,
    build_safe_ranking_negatives,
)


def _fixture() -> dict[str, np.ndarray]:
    return {
        "split": np.asarray(["train", "train", "train", "dev"]),
        "source_group_id": np.asarray(["group-a", "group-a", "group-b", "group-c"]),
        "concept_id": np.asarray(["forest", "forest", "hospital", "snow"]),
        "image_id": np.asarray(["image-a", "image-a-translation", "image-b", "image-c"]),
        "content_sha256": np.asarray(["content-a", "content-a", "content-b", "content-c"]),
        "target": np.arange(4 * 9 * 5, dtype=np.float32).reshape(4, 9, 5),
        "color_prior": np.asarray([
            [1.0, 0.0, 0.0], [0.99, 0.01, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]
        ], dtype=np.float32),
        "teacher_latent": np.asarray([
            [0.0, 0.0], [0.01, 0.0], [1.0, 1.0], [2.0, 2.0]
        ], dtype=np.float32),
    }


def test_safe_negative_is_deterministic_and_excludes_equivalents_and_dev() -> None:
    first = build_safe_ranking_negatives(_fixture())
    second = build_safe_ranking_negatives(_fixture())
    assert first["negative_selection_version"].item() == NEGATIVE_SELECTION_VERSION
    np.testing.assert_array_equal(first["ranking_negative_valid"], second["ranking_negative_valid"])
    np.testing.assert_array_equal(first["ranking_negative_color_prior"], second["ranking_negative_color_prior"])
    assert first["ranking_negative_source_group_id"][0] == "group-b"
    assert first["ranking_negative_source_group_id"][1] == "group-b"
    assert first["ranking_negative_source_group_id"][2] == "group-a"
    assert first["ranking_negative_valid"][3] == 0.0


def test_no_valid_negative_is_explicitly_safe() -> None:
    fixture = _fixture()
    for key in fixture:
        fixture[key] = fixture[key][:2]
    result = build_safe_ranking_negatives(fixture)
    assert not result["ranking_negative_valid"].any()
    assert not result["ranking_negative_color_prior"].any()


def test_teacher_distance_cannot_make_equivalent_prior_eligible() -> None:
    fixture = _fixture()
    fixture["source_group_id"] = np.asarray(["a", "b", "c", "d"])
    fixture["concept_id"] = np.asarray(["a", "b", "c", "d"])
    fixture["image_id"] = np.asarray(["a", "b", "c", "d"])
    fixture["content_sha256"] = np.asarray(["a", "b", "c", "d"])
    fixture["color_prior"][1] = fixture["color_prior"][0]
    fixture["teacher_latent"][1] = np.asarray([1000.0, 1000.0])
    fixture["color_prior"][2] = np.asarray([0.8, 0.6, 0.0])
    result = build_safe_ranking_negatives(fixture)
    assert result["ranking_negative_source_group_id"][0] == "c"


def test_selects_closest_safe_prior_not_farthest() -> None:
    fixture = _fixture()
    fixture["source_group_id"] = np.asarray(["a", "b", "c", "d"])
    fixture["concept_id"] = np.asarray(["a", "b", "c", "d"])
    fixture["image_id"] = np.asarray(["a", "b", "c", "d"])
    fixture["content_sha256"] = np.asarray(["a", "b", "c", "d"])
    fixture["color_prior"][1] = np.asarray([0.9, 0.43589, 0.0])
    fixture["color_prior"][2] = np.asarray([0.0, 1.0, 0.0])
    result = build_safe_ranking_negatives(fixture)
    assert result["ranking_negative_source_group_id"][0] == "b"
