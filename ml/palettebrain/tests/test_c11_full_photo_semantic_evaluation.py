from __future__ import annotations

import numpy as np

from ml.palettebrain.evaluate_semantic_v3 import (
    full_photo_category_rates,
    full_photo_semantic_rows,
)


def test_full_photo_semantic_contrast_accepts_natural_target_not_stereotype() -> None:
    # A natural rainy photo can be gray.  Its text-linked target, rather than
    # a hand-authored "rain must be blue" family, defines the semantic check.
    gray_rain = np.asarray([[0.55, 0.0, 0.0], [0.42, 0.0, 0.0]], dtype=np.float32)
    warm_kitchen = np.asarray([[0.72, 0.12, 0.08], [0.58, 0.10, 0.06]], dtype=np.float32)
    rows = full_photo_semantic_rows(
        {"rain": gray_rain}, ["rain"], np.asarray([[1.0, 0.0]], dtype=np.float32),
        np.asarray([[1.0, 0.0], [-1.0, 0.0]], dtype=np.float32),
        np.stack((gray_rain, warm_kitchen)), np.asarray([2, 2]),
        np.asarray(["rain on a city street", "warm kitchen"]),
        np.asarray(["rain-group", "kitchen-group"]), neighbors=1,
    )
    assert rows[0]["nearestRealPrompt"] == "rain on a city street"
    assert rows[0]["pass"] is True
    assert rows[0]["contrastMargin"] > 0.0


def test_full_photo_category_rates_use_target_grounded_rows() -> None:
    rows = [
        {"category": "weather", "pass": True},
        {"category": "weather", "pass": False},
        {"category": "nature", "pass": True},
    ]
    assert full_photo_category_rates(rows) == {"weather": 0.5, "nature": 1.0}
