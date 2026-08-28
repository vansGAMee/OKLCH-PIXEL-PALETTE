"""Canonical all-hard-gates Candidate 11 qualification command.

No weighted average is computed. Missing evidence is a failure, mocked neural
tests are rejected, and a failed gate always leaves productionReady false and
codename null.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


THRESHOLDS = {
    "semanticFamilyWin": (">=", 0.80),
    "directRu": (">=", 0.95), "directEn": (">=", 0.95), "exclusion": (">=", 1.0),
    "cleanMultiColor": (">=", 0.70), "nearDuplicateRate": ("<=", 0.05),
    "count": (">=", 1.0), "inactive": (">=", 1.0), "locks": (">=", 1.0),
    "seedDiversity": (">=", 1.0), "seedStability": (">=", 1.0),
    "gamut": (">=", 1.0), "determinism": (">=", 1.0),
    "basicConcepts": (">=", 0.80), "nature": (">=", 0.80),
    "weatherScenes": (">=", 0.80), "materials": (">=", 0.80),
    "placesInteriors": (">=", 0.80), "lighting": (">=", 0.80),
    "stylesMedia": (">=", 0.80), "compositions": (">=", 0.75),
    "oodParaphrases": (">=", 0.75), "heldOutRelated": (">=", 0.70),
    "ruEnSemanticAgreement": (">=", 0.85),
    "paletteStructureWinRate": (">=", 0.60),
}
BOOLEAN_GATES = [
    "abstractConceptGate", "longPromptGate", "adversarialCompositionGate",
    "pytorchOnnxParity", "onnxBrowserParity", "realBrowserSemanticSmoke",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: str | None) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else {}


def qualify(args: argparse.Namespace) -> dict[str, Any]:
    evidence = _load(args.evidence)
    metrics = evidence.get("metrics", {})
    sources = evidence.get("sources", {})
    failures: list[str] = []
    gates: dict[str, Any] = {}
    if evidence and evidence.get("testClassification") not in {"REAL_PYTORCH_ONNX_BROWSER_SEMANTIC", "REAL_PYTORCH_SEMANTIC_STAGE_A"}:
        failures.append("evidence classification is absent, mocked, or engineering-only")
    for name, (operator, threshold) in THRESHOLDS.items():
        value = metrics.get(name)
        passed = isinstance(value, (int, float)) and ((value >= threshold) if operator == ">=" else (value <= threshold))
        gates[name] = {"value": value, "operator": operator, "threshold": threshold, "pass": passed}
        if not passed:
            failures.append(f"{name}: {value!r} does not satisfy {operator} {threshold}")
    for name in BOOLEAN_GATES:
        value = metrics.get(name)
        gates[name] = {"value": value, "required": True, "pass": value is True}
        if value is not True:
            failures.append(f"{name}: missing or false")

    parity = _load(args.parity_report)
    parity_ok = parity.get("pytorchOnnx", {}).get("pass") is True
    if metrics.get("pytorchOnnxParity") is True and not parity_ok:
        failures.append("claimed PT/ONNX parity is not supported by the machine report")
    manifest = _load(args.manifest)
    decoder_path_value = manifest.get("decoder", {}).get("path") or manifest.get("decoder", {}).get("url")
    artifact_ok = False
    if isinstance(decoder_path_value, str) and decoder_path_value.startswith("/models/"):
        artifact = Path("public") / decoder_path_value.lstrip("/")
        artifact_ok = (
            artifact.is_file()
            and artifact.stat().st_size == manifest.get("decoder", {}).get("bytes")
            and _sha256(artifact) == manifest.get("decoder", {}).get("sha256")
        )
    if not artifact_ok:
        failures.append("manifest decoder path/hash/size does not match the artifact")
    if sources.get("benchmarkId") not in (None, "palettebrain-candidate11-semantic-v3-frozen-2026-08-26"):
        failures.append("semantic evidence is not from the frozen v3 benchmark")

    passed = not failures
    report = {
        "schemaVersion": 1,
        "candidate": "candidate-11",
        "benchmarkId": "palettebrain-candidate11-semantic-v3-frozen-2026-08-26",
        "testClassification": evidence.get("testClassification"),
        "gates": gates,
        "artifactIntegrity": artifact_ok,
        "manifestDecoderSha256": manifest.get("decoder", {}).get("sha256"),
        "checkpointSha256": sources.get("checkpointSha256"),
        "datasetSha256": sources.get("datasetSha256"),
        "productionReady": passed,
        "codename": "Mikhail Tal" if passed else None,
        "pass": passed,
        "hardFailures": failures,
        "rule": "Every hard gate must pass; no weighted average can hide a failure.",
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence",
        default="ml/palettebrain/reports/candidate-11-semantic-v3.json",
        help="Real semantic evidence report (defaults to the current Candidate 11 report).",
    )
    parser.add_argument("--parity-report", default="ml/palettebrain/reports/candidate-11-parity.json")
    parser.add_argument("--manifest", default="public/models/palettebrain-v2.manifest.json")
    parser.add_argument("--output", default="ml/palettebrain/reports/candidate-11-qualification.json")
    parser.add_argument("--no-fail-exit", action="store_true")
    args = parser.parse_args()
    report = qualify(args)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["pass"] and not args.no_fail_exit:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
