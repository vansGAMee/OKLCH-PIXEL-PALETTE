from __future__ import annotations

import numpy as np
import pytest

from ml.palettebrain.dataset import seed_noise_from_uint32, validate_prepared_archive


def valid_archive() -> dict[str, np.ndarray]:
    rows = 8
    counts = np.arange(2, 10, dtype=np.int64)
    count_masks = (np.arange(9)[None, :] < counts[:, None]).astype(np.float32)
    embeddings = np.zeros((rows, 384), dtype=np.float32)
    embeddings[:, 0] = 1.0
    targets = np.zeros((rows, 9, 5), dtype=np.float32)
    targets[..., 3] = count_masks
    locked_masks = np.zeros((rows, 9), dtype=np.float32)
    locked_colors = np.zeros((rows, 9, 4), dtype=np.float32)
    return {
        "embeddings": embeddings,
        "counts": counts,
        "count_masks": count_masks,
        "seed_noise": np.stack([seed_noise_from_uint32(seed) for seed in range(rows)]),
        "locked_masks": locked_masks,
        "locked_colors": locked_colors,
        "targets": targets,
        "splits": np.asarray([0, 0, 0, 1, 1, 2, 2, 2], dtype=np.int8),
        "quality_weights": np.ones(rows, dtype=np.float32),
        "source_group_ids": np.asarray([f"group-{index}" for index in range(rows)]),
    }


def test_valid_contract_covers_every_count() -> None:
    assert validate_prepared_archive(valid_archive()) == {
        "rows": 8,
        "train": 3,
        "val": 2,
        "test": 3,
    }


def test_source_group_may_not_cross_splits() -> None:
    archive = valid_archive()
    archive["source_group_ids"][[0, 5]] = "leaked"
    with pytest.raises(ValueError, match="source group crosses splits"):
        validate_prepared_archive(archive)


def test_inactive_targets_must_be_zero() -> None:
    archive = valid_archive()
    archive["targets"][0, 8, 0] = 1.0
    with pytest.raises(ValueError, match="inactive targets"):
        validate_prepared_archive(archive)


def test_embeddings_must_be_normalized() -> None:
    archive = valid_archive()
    archive["embeddings"][0] *= 0.5
    with pytest.raises(ValueError, match="L2 normalized"):
        validate_prepared_archive(archive)


def test_locks_must_be_active_and_bound() -> None:
    archive = valid_archive()
    archive["locked_masks"][0, 8] = 1.0
    with pytest.raises(ValueError, match="inactive slot"):
        validate_prepared_archive(archive)


def test_seed_noise_is_repeatable_and_seed_sensitive() -> None:
    first = seed_noise_from_uint32(42)
    np.testing.assert_array_equal(first, seed_noise_from_uint32(42))
    assert not np.array_equal(first, seed_noise_from_uint32(43))
