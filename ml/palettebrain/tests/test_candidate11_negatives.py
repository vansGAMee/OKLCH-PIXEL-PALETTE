from __future__ import annotations

import time

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


def _scaled_fixture(rows: int) -> dict[str, np.ndarray]:
    indices = np.arange(rows)
    priors = np.zeros((rows, 32), dtype=np.float32)
    priors[indices, indices % priors.shape[1]] = 1.0
    return {
        "split": np.asarray(["train"] * rows),
        "source_group_id": np.asarray([f"group-{index}" for index in indices]),
        "concept_id": np.asarray([f"concept-{index}" for index in indices]),
        "image_id": np.asarray([f"image-{index}" for index in indices]),
        "content_sha256": np.asarray([f"content-{index}" for index in indices]),
        "target": np.arange(rows * 9 * 5, dtype=np.float32).reshape(rows, 9, 5),
        "color_prior": priors,
        "teacher_latent": np.zeros((rows, 4), dtype=np.float32),
    }


def test_safe_negative_records_the_selected_index_and_every_identity_contract() -> None:
    fixture = _scaled_fixture(96)
    fixture["source_group_id"][1:6] = fixture["source_group_id"][0]
    fixture["concept_id"][6:11] = fixture["concept_id"][0]
    fixture["image_id"][11:16] = fixture["image_id"][0]
    fixture["content_sha256"][16:21] = fixture["content_sha256"][0]
    fixture["target"][21] = fixture["target"][0]

    result = build_safe_ranking_negatives(fixture)

    assert "ranking_negative_index" in result
    for row, candidate in enumerate(result["ranking_negative_index"]):
        if result["ranking_negative_valid"][row] == 0:
            continue
        candidate = int(candidate)
        assert fixture["split"][candidate] == "train"
        assert fixture["source_group_id"][candidate] != fixture["source_group_id"][row]
        assert fixture["concept_id"][candidate] != fixture["concept_id"][row]
        assert fixture["image_id"][candidate] != fixture["image_id"][row]
        assert fixture["content_sha256"][candidate] != fixture["content_sha256"][row]
        assert not np.array_equal(fixture["target"][candidate], fixture["target"][row])


def test_safe_negative_scaling_is_not_quadratic() -> None:
    timings = []
    for rows in (128, 512):
        fixture = _scaled_fixture(rows)
        started = time.perf_counter()
        build_safe_ranking_negatives(fixture)
        timings.append(time.perf_counter() - started)
    # Four times the input must remain comfortably below quadratic 16x growth.
    assert timings[1] < timings[0] * 8.0, timings
