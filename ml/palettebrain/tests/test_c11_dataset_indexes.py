from __future__ import annotations

import numpy as np

from ml.palettebrain import build_c11_dataset


def test_split_leakage_index_is_one_pass_and_reports_each_identity() -> None:
    helper = getattr(build_c11_dataset, "split_membership_leaks", None)
    assert callable(helper)
    values = np.asarray(["safe", "group", "group", "other", "other"])
    splits = np.asarray(["train", "train", "val", "val", "val"])
    assert helper(values, splits) == ["group"]


def test_split_leakage_index_handles_empty_input() -> None:
    helper = getattr(build_c11_dataset, "split_membership_leaks", None)
    assert callable(helper)
    assert helper(np.asarray([], dtype=str), np.asarray([], dtype=str)) == []
