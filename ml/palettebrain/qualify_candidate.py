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


DEFAULT_GATE_CONFIG = Path(__file__).with_name(
    "c11_qualification_gate.target_grounded.v1.json"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: str | None) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else {}


def evaluate_gate_contract(
    metrics: dict[str, Any], config: dict[str, Any], *, require_sealed: bool
) -> tuple[bool, dict[str, Any], list[str]]:
    failures: list[str] = []
    gates: dict[str, Any] = {}
    thresholds = {
        **config.get("commonThresholds", {}),
        **config.get("sealedThresholds" if require_sealed else "devThresholds", {}),
    }
    for name, rule in thresholds.items():
        operator, threshold = rule
        value = metrics.get(name)
        passed = isinstance(value, (int, float)) and {
            ">=": lambda: value >= threshold,
            "<=": lambda: value <= threshold,
            ">": lambda: value > threshold,
        }[operator]()
        gates[name] = {
            "value": value, "operator": operator,
            "threshold": threshold, "pass": passed,
        }
        if not passed:
            failures.append(f"{name}: {value!r} does not satisfy {operator} {threshold}")
    boolean_names = list(config.get("commonBooleanGates", []))
    if require_sealed:
        boolean_names.extend(config.get("sealedBooleanGates", []))
    for name in boolean_names:
        value = metrics.get(name)
        gates[name] = {"value": value, "required": True, "pass": value is True}
        if value is not True:
            failures.append(f"{name}: missing or false")
    return not failures, gates, failures


def qualify(args: argparse.Namespace) -> dict[str, Any]:
    evidence = _load(args.evidence)
    metrics = evidence.get("metrics", {})
    sources = evidence.get("sources", {})
    config = _load(args.gate_config)
    contract_pass, gates, failures = evaluate_gate_contract(
        metrics, config, require_sealed=args.require_sealed
    )
    if evidence and evidence.get("testClassification") not in {"REAL_PYTORCH_ONNX_BROWSER_SEMANTIC", "REAL_PYTORCH_SEMANTIC_STAGE_A"}:
        failures.append("evidence classification is absent, mocked, or engineering-only")
    if not contract_pass and not failures:
        failures.append("target-grounded gate contract failed")

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
    if args.require_sealed:
        if sources.get("evaluationSplit") != "test":
            failures.append("sealed qualification requires evaluationSplit=test")
        if not sources.get("semanticTestSha256"):
            failures.append("sealed semantic TEST artifact SHA is missing")

    passed = not failures
    report = {
        "schemaVersion": 1,
        "candidate": "candidate-11",
        "benchmarkId": "palettebrain-candidate11-semantic-v3-frozen-2026-08-26",
        "testClassification": evidence.get("testClassification"),
        "qualificationMode": "sealed" if args.require_sealed else "dev",
        "gateContract": config.get("contract"),
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
    parser.add_argument("--gate-config", default=str(DEFAULT_GATE_CONFIG))
    parser.add_argument("--require-sealed", action="store_true")
    parser.add_argument("--no-fail-exit", action="store_true")
    args = parser.parse_args()
    report = qualify(args)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["pass"] and not args.no_fail_exit:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
