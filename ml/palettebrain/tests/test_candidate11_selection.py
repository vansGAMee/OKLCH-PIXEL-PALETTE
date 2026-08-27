from ml.palettebrain.select_candidate11_checkpoint import selection_key


def _report(**overrides):
    metrics = {
        "count": 1.0, "inactive": 1.0, "gamut": 1.0, "determinism": 1.0,
        "directEn": 0.8, "directRu": 0.8, "nearDuplicateRate": 0.1,
        "semanticFamilyWin": 0.7, "paletteStructureWinRate": 0.6,
        "ruEnSemanticAgreement": 0.8,
    }
    metrics.update(overrides)
    return {"metrics": metrics}


def test_semantics_and_structure_outrank_validation_loss() -> None:
    better_dev = selection_key(_report(semanticFamilyWin=0.8), 2.0)
    lower_loss = selection_key(_report(semanticFamilyWin=0.7), 0.1)
    assert better_dev > lower_loss


def test_engineering_invalid_candidate_is_rejected_first() -> None:
    invalid = selection_key(_report(count=0.0, semanticFamilyWin=1.0), 0.01)
    valid = selection_key(_report(semanticFamilyWin=0.1), 10.0)
    assert valid > invalid
