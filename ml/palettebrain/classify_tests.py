"""Inventory PaletteBrain tests by evidence class; never treats green as quality."""

from __future__ import annotations

import json
from pathlib import Path


def classify(path: Path, text: str) -> list[str]:
    classes: list[str] = []
    lower = text.lower()
    if "legacy" in lower or "procedural" in lower:
        classes.append("LEGACY_PROCEDURAL")
    if "settestdecoderloader" in lower or "fake" in lower or "mock" in lower:
        classes.append("MOCKED_NEURAL")
    if "torch.load" in lower or "palettedecoder(" in lower:
        classes.append("REAL_PYTORCH")
    if "onnxruntime" in lower or "inferencesession" in lower:
        classes.append("REAL_ONNX")
    if "chromium" in lower or "cdp" in lower:
        classes.append("REAL_BROWSER")
    semantic_terms = ("semantic family", "hardnegative", "reference_palettes", "semanticfamilywin")
    if any(term in lower for term in semantic_terms):
        classes.append("SEMANTIC_QUALITY")
    if not classes or any(term in lower for term in ("shape", "finite", "gamut", "count", "determin")):
        classes.append("ENGINEERING_ONLY")
    return list(dict.fromkeys(classes))


def main() -> None:
    candidates = list(Path("ml/palettebrain/tests").glob("test_*.py"))
    candidates += list(Path("src/lib/ai-palette/__tests__").glob("*.test.ts"))
    candidates += [Path("scripts/test-real-browser.mjs")]
    rows = []
    for path in sorted(candidates):
        text = path.read_text(encoding="utf-8")
        classes = classify(path, text)
        rows.append({
            "path": str(path).replace("\\", "/"), "classes": classes,
            "releaseEligibleSemanticEvidence": "SEMANTIC_QUALITY" in classes and "MOCKED_NEURAL" not in classes,
        })
    report = {
        "schemaVersion": 1, "tests": rows,
        "rules": [
            "MOCKED_NEURAL never qualifies release",
            "LEGACY_PROCEDURAL never represents PaletteBrain neural semantics",
            "ENGINEERING_ONLY does not prove semantic quality",
        ],
    }
    output = Path("ml/palettebrain/reports/test-evidence-classification.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"tests": len(rows), "output": str(output)}, indent=2))


if __name__ == "__main__":
    main()
