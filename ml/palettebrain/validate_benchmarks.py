"""Validate frozen PaletteBrain semantic benchmarks without running a model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


EXPLICIT_COLOR_TERMS = {
    "red", "green", "blue", "black", "white", "orange", "purple", "yellow",
    "crimson", "красный", "красная", "красное", "зелёный", "зелёная",
    "синий", "чёрный", "черный", "белый", "оранжевый", "фиолетовый",
}


def validate_v2(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    concepts = value.get("concepts", {})
    for concept_id, concept in concepts.items():
        prompts = concept.get("prompts", [])
        if not prompts or len(prompts) != len(set(prompts)):
            errors.append(f"{concept_id}: prompts must be non-empty and unique")
        for prompt in prompts:
            tokens = set(str(prompt).lower().replace("-", " ").split())
            leaked = tokens & EXPLICIT_COLOR_TERMS
            if leaked:
                errors.append(f"{concept_id}: explicit color leakage in {prompt!r}: {sorted(leaked)}")
        references = concept.get("reference_palettes", [])
        if len(references) < 2 or any(len(palette) < 2 for palette in references):
            errors.append(f"{concept_id}: requires at least two multi-color references")
    for index, pair in enumerate(value.get("contrast_pairs", [])):
        for side in ("a", "b"):
            concept_id = pair.get(f"concept_{side}")
            prompt = pair.get(f"prompt_{side}")
            if concept_id not in concepts:
                errors.append(f"contrast_pairs[{index}].concept_{side} is missing: {concept_id}")
            elif prompt not in concepts[concept_id].get("prompts", []):
                errors.append(
                    f"contrast_pairs[{index}] {prompt!r} does not belong to {concept_id!r}"
                )
    controls = value.get("explicit_color_controls", [])
    if not controls:
        errors.append("explicit_color_controls must be separate and non-empty")
    return {
        "path": str(path).replace("\\", "/"),
        "concepts": len(concepts),
        "contrastPairs": len(value.get("contrast_pairs", [])),
        "explicitColorControls": len(controls),
        "errors": errors,
        "pass": not errors,
    }


def validate_v3(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    required_buckets = {
        "explicit_color_controls", "basic_physical", "nature", "places_interiors",
        "weather", "lighting", "materials", "styles_media",
    }
    missing = sorted(required_buckets - set(value.get("buckets", {})))
    if missing:
        errors.append(f"missing buckets: {missing}")
    for bucket, prompts in value.get("buckets", {}).items():
        if not prompts or len(prompts) != len(set(prompts)):
            errors.append(f"{bucket}: prompts must be non-empty and unique")
    for field in (
        "bilingualPairs", "abstract", "longText", "compositionContrasts",
        "oodParaphraseGroups", "adversarialComposition", "negationControls",
    ):
        if not value.get(field):
            errors.append(f"{field} must be non-empty")
    if len(value.get("abstract", [])) < 9:
        errors.append("abstract requires at least nine bilingual concepts")
    if len(value.get("longText", [])) < 5:
        errors.append("longText requires at least five bilingual prompts")
    if value.get("sealed") is not True:
        errors.append("v3 must be sealed before repaired training")
    return {
        "path": str(path).replace("\\", "/"),
        "bucketCount": len(value.get("buckets", {})),
        "abstractCount": len(value.get("abstract", [])),
        "longTextCount": len(value.get("longText", [])),
        "errors": errors,
        "pass": not errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v2", default="ml/palettebrain/benchmark_visual_semantic_v2.json")
    parser.add_argument("--v3", default="ml/palettebrain/benchmark_semantic_v3.json")
    args = parser.parse_args()
    report = {"v2": validate_v2(Path(args.v2)), "v3": validate_v3(Path(args.v3))}
    report["pass"] = report["v2"]["pass"] and report["v3"]["pass"]
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
