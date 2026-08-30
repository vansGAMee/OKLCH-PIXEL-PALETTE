from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pytest

from ml.palettebrain.color_distribution import (
    palette_or_pixels_to_oklch_histogram,
)
from ml.palettebrain.rescore_c11_semantic_source import rescore_source


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _prior(hue_degrees: float) -> np.ndarray:
    hue = math.radians(hue_degrees)
    return palette_or_pixels_to_oklch_histogram(
        np.asarray(
            [[0.60, 0.14 * math.cos(hue), 0.14 * math.sin(hue)]],
            dtype=np.float32,
        )
    )


def _write_policy(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "conceptBankSha256": "0" * 64,
                "defaultRule": {"id": "observational", "mode": "observational"},
                "rules": [
                    {
                        "id": "green",
                        "mode": "constrained",
                        "concepts": ["grass", "forest"],
                        "hueArcs": [[105, 175]],
                        "lightness": [0.2, 0.9],
                        "chroma": [0.03, 0.3],
                        "includeNeutral": False,
                        "minimumMass": 0.55,
                        "confidence": 0.9,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_rescore_filters_whole_source_groups_without_touching_input(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.npz"
    output = tmp_path / "source-semantic-v1.npz"
    report = tmp_path / "source-semantic-v1.json"
    policy = tmp_path / "policy.json"
    _write_policy(policy)
    priors = np.stack(
        [
            _prior(55.0),
            _prior(55.0),
            _prior(135.0),
            _prior(135.0),
            _prior(145.0),
            _prior(145.0),
        ]
    )
    np.savez_compressed(
        source,
        source_group_id=np.asarray(
            ["bad", "bad", "good-a", "good-a", "good-b", "good-b"]
        ),
        image_id=np.asarray(
            ["bad-image", "bad-image", "good-a", "good-a", "good-b", "good-b"]
        ),
        concept_id=np.asarray(
            ["grass", "grass", "forest", "forest", "forest", "forest"]
        ),
        color_prior=priors,
        quality_weight=np.ones(6, dtype=np.float32),
        count=np.asarray([2, 3, 2, 3, 2, 3], dtype=np.int64),
        split=np.asarray(["train"] * 6),
        scalar_metadata=np.asarray("preserved"),
    )
    before = _sha256(source)

    summary = rescore_source(
        input_path=source,
        output_path=output,
        report_path=report,
        policy_path=policy,
    )

    assert _sha256(source) == before
    assert summary["networkRequests"] == 0
    assert summary["inputRows"] == 6
    assert summary["outputRows"] == 4
    assert summary["inputUniqueImages"] == 3
    assert summary["outputUniqueImages"] == 2
    assert summary["provenDeficientConcepts"] == ["grass"]
    with np.load(output, allow_pickle=False) as archive:
        assert archive["source_group_id"].tolist() == [
            "good-a", "good-a", "good-b", "good-b"
        ]
        assert archive["concept_id"].tolist() == ["forest"] * 4
        assert archive["palette_semantic_rule_id"].tolist() == ["green"] * 4
        assert archive["quality_weight"].tolist() == pytest.approx([0.9] * 4)
        assert archive["scalar_metadata"].item() == "preserved"
        assert archive["rescore_source_sha256"].item() == before

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        rescore_source(
            input_path=source,
            output_path=output,
            report_path=report,
            policy_path=policy,
        )
