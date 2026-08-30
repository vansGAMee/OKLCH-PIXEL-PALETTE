from __future__ import annotations

from ml.palettebrain.c11_release_contract import (
    phase_artifact_reusable,
    stage_a_metrics_contract,
    stage_b_probe_metrics_contract,
)
from ml.palettebrain.train_candidate11 import resume_dependency_fingerprints


CALIBRATION = {
    "minimumSemanticFamilyWin": 0.62,
    "minimumSemanticTargetContrastMargin": 0.009,
    "minimumDirectEn": 4 / 7,
    "minimumDirectRu": 1.0,
    "minimumPaletteStructureWinRate": 0.53,
    "maximumCrossPromptCollapseRate": 0.05,
}


def test_stage_a_contract_accepts_target_grounded_improvement_and_rejects_collapse() -> None:
    stage_a = {
        "semanticFamilyWin": 0.64,
        "semanticTargetContrastMargin": 0.0103,
        "directEn": 4 / 7,
        "directRu": 1.0,
        "paletteStructureWinRate": 0.583,
        "crossPromptCollapseRate": 0.021,
        "crossPromptCollapseGate": True,
    }
    passed, failures = stage_a_metrics_contract(stage_a, CALIBRATION)
    assert passed is True
    assert failures == []

    collapsed = {**stage_a, "crossPromptCollapseRate": 0.08}
    passed, failures = stage_a_metrics_contract(collapsed, CALIBRATION)
    assert passed is False
    assert failures == ["crossPromptCollapseRate 0.08 > 0.05"]


def test_completed_training_artifact_survives_orchestrator_fingerprint_change() -> None:
    assert phase_artifact_reusable(
        artifact_valid=True,
        recorded_dependency="old-orchestrator",
        current_dependency="new-orchestrator",
        content_validates_current_contract=True,
    ) is True
    assert phase_artifact_reusable(
        artifact_valid=True,
        recorded_dependency="old-evaluator",
        current_dependency="new-evaluator",
        content_validates_current_contract=False,
    ) is False


def test_completed_probe_fingerprint_remains_resume_compatible() -> None:
    assert (
        "d1ec28a8789eefb71a109cd7e8fd0928adb17d42d0635f371855a519bb0969c9"
        in resume_dependency_fingerprints()
    )


def test_stage_b_probe_contract_preserves_stage_a_signal() -> None:
    stage_a = {
        "semanticFamilyWin": 0.64,
        "semanticTargetContrastMargin": 0.0103,
        "directEn": 4 / 7,
        "directRu": 1.0,
        "paletteStructureWinRate": 0.583,
    }
    probe = {
        "semanticFamilyWin": 0.61,
        "semanticTargetContrastMargin": 0.009,
        "directEn": 4 / 7,
        "directRu": 1.0,
        "paletteStructureWinRate": 0.57,
        "crossPromptCollapseRate": 0.03,
        "crossPromptCollapseGate": True,
    }
    passed, failures = stage_b_probe_metrics_contract(stage_a, probe)
    assert passed is True
    assert failures == []

    collapsed = {**probe, "semanticFamilyWin": 0.50}
    passed, failures = stage_b_probe_metrics_contract(stage_a, collapsed)
    assert passed is False
    assert failures == ["semanticFamilyWin 0.5 < Stage A 0.64 - 0.05"]
