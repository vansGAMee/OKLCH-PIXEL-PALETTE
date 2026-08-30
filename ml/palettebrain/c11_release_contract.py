"""Evidence-calibrated release contracts for Candidate 11."""

from __future__ import annotations

from typing import Any


def phase_artifact_reusable(
    *, artifact_valid: bool, recorded_dependency: str | None,
    current_dependency: str, content_validates_current_contract: bool,
) -> bool:
    if not artifact_valid:
        return False
    if recorded_dependency is None or recorded_dependency == current_dependency:
        return True
    return content_validates_current_contract


def stage_a_metrics_contract(
    metrics: dict[str, Any], calibration: dict[str, float]
) -> tuple[bool, list[str]]:
    failures: list[str] = []
    minimums = {
        "semanticFamilyWin": "minimumSemanticFamilyWin",
        "semanticTargetContrastMargin": "minimumSemanticTargetContrastMargin",
        "directEn": "minimumDirectEn",
        "directRu": "minimumDirectRu",
        "paletteStructureWinRate": "minimumPaletteStructureWinRate",
    }
    for metric_name, calibration_name in minimums.items():
        value = metrics.get(metric_name)
        threshold = calibration[calibration_name]
        if not isinstance(value, (int, float)) or value < threshold:
            failures.append(f"{metric_name} {value!r} < {threshold}")
    collapse = metrics.get("crossPromptCollapseRate")
    maximum_collapse = calibration["maximumCrossPromptCollapseRate"]
    if not isinstance(collapse, (int, float)) or collapse > maximum_collapse:
        failures.append(f"crossPromptCollapseRate {collapse!r} > {maximum_collapse}")
    if metrics.get("crossPromptCollapseGate") is not True:
        failures.append("crossPromptCollapseGate is not true")
    return not failures, failures


def stage_b_probe_metrics_contract(
    stage_a: dict[str, Any], probe: dict[str, Any]
) -> tuple[bool, list[str]]:
    """Bounded guardrail before production Stage B, not a release gate."""
    failures: list[str] = []

    def number(values: dict[str, Any], name: str) -> float | None:
        value = values.get(name)
        return float(value) if isinstance(value, (int, float)) else None

    stage_family = number(stage_a, "semanticFamilyWin")
    probe_family = number(probe, "semanticFamilyWin")
    if stage_family is None or probe_family is None:
        failures.append("semanticFamilyWin is missing or non-numeric")
    elif probe_family < stage_family - 0.05:
        failures.append(
            f"semanticFamilyWin {probe_family:g} < Stage A {stage_family:g} - 0.05"
        )

    probe_margin = number(probe, "semanticTargetContrastMargin")
    if probe_margin is None or probe_margin <= 0.0:
        failures.append(
            f"semanticTargetContrastMargin {probe.get('semanticTargetContrastMargin')!r} <= 0"
        )

    for name in ("directEn", "directRu"):
        stage_value = number(stage_a, name)
        probe_value = number(probe, name)
        if stage_value is None or probe_value is None:
            failures.append(f"{name} is missing or non-numeric")
        elif probe_value < stage_value:
            failures.append(f"{name} {probe_value:g} < Stage A {stage_value:g}")

    stage_structure = number(stage_a, "paletteStructureWinRate")
    probe_structure = number(probe, "paletteStructureWinRate")
    if stage_structure is None or probe_structure is None:
        failures.append("paletteStructureWinRate is missing or non-numeric")
    elif probe_structure < stage_structure - 0.02:
        failures.append(
            f"paletteStructureWinRate {probe_structure:g} < Stage A {stage_structure:g} - 0.02"
        )

    collapse = number(probe, "crossPromptCollapseRate")
    if collapse is None or collapse > 0.05:
        failures.append(
            f"crossPromptCollapseRate {probe.get('crossPromptCollapseRate')!r} > 0.05"
        )
    if probe.get("crossPromptCollapseGate") is not True:
        failures.append("crossPromptCollapseGate is not true")
    return not failures, failures
