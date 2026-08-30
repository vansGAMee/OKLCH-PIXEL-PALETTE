from __future__ import annotations

from ml.palettebrain.qualify_candidate import evaluate_gate_contract


CONFIG = {
    "commonThresholds": {
        "semanticTargetContrastMargin": [">", 0.0],
        "directEn": [">=", 4 / 7],
        "directRu": [">=", 1.0],
        "cleanMultiColor": [">=", 0.20],
        "nearDuplicateRate": ["<=", 0.50],
        "oodParaphrases": [">=", 0.25],
        "heldOutRelated": [">=", 0.50],
    },
    "devThresholds": {
        "semanticFamilyWin": [">=", 0.62],
        "paletteStructureWinRate": [">=", 0.55],
    },
    "sealedThresholds": {
        "semanticFamilyWin": [">=", 0.63],
        "paletteStructureWinRate": [">=", 0.40],
    },
    "commonBooleanGates": ["longPromptGate", "crossPromptCollapseGate"],
    "sealedBooleanGates": ["sealedSemanticTestGate"],
}


def test_target_grounded_qualification_requires_progress_and_sealed_evidence() -> None:
    candidate = {
        "semanticFamilyWin": 0.65,
        "semanticTargetContrastMargin": 0.008,
        "directEn": 5 / 7,
        "directRu": 1.0,
        "cleanMultiColor": 0.27,
        "nearDuplicateRate": 0.41,
        "oodParaphrases": 0.25,
        "heldOutRelated": 0.50,
        "paletteStructureWinRate": 0.58,
        "longPromptGate": True,
        "crossPromptCollapseGate": True,
        "sealedSemanticTestGate": False,
    }
    passed, _, failures = evaluate_gate_contract(candidate, CONFIG, require_sealed=False)
    assert passed is True
    assert failures == []

    base_like = {
        **candidate,
        "cleanMultiColor": 0.05,
        "nearDuplicateRate": 0.69,
        "oodParaphrases": 0.0,
        "heldOutRelated": 0.0,
        "longPromptGate": False,
    }
    passed, _, failures = evaluate_gate_contract(base_like, CONFIG, require_sealed=False)
    assert passed is False
    assert {failure.split(":", 1)[0] for failure in failures} == {
        "cleanMultiColor", "nearDuplicateRate", "oodParaphrases",
        "heldOutRelated", "longPromptGate",
    }

    sealed = {
        **candidate,
        "semanticFamilyWin": 0.67,
        "paletteStructureWinRate": 0.46,
        "sealedSemanticTestGate": True,
    }
    passed, _, failures = evaluate_gate_contract(sealed, CONFIG, require_sealed=True)
    assert passed is True
    assert failures == []
