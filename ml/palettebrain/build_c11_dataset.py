"""Audit or build the versioned Candidate 11 compact training archive.

The current 192-row archive has no prompts, source IDs, image IDs, crop/mask
coordinates, or licenses.  This tool reports that fact rather than fabricating
provenance.  Rebuilding requires a metadata-rich NPZ produced by an authorized
offline image/teacher pipeline; it does not download a corpus.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


CORE_FIELDS = {
    "text_embedding": (384,), "color_prior": (390,), "teacher_latent": (128,),
    "count_mask": (9,), "seed_noise": (9, 4), "locked_mask": (9,),
    "locked_colors": (9, 4), "target": (9, 5),
}
PROVENANCE_FIELDS = {
    "prompt", "source_id", "source_group_id", "image_id", "crop_coordinates",
    "mask_area_fraction", "license", "split",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit(path: Path) -> dict[str, Any]:
    archive = np.load(path, allow_pickle=False)
    names = set(archive.files)
    errors: list[str] = []
    record_count = int(archive["text_embedding"].shape[0]) if "text_embedding" in names else 0
    for name, trailing_shape in CORE_FIELDS.items():
        if name not in names:
            errors.append(f"missing core field: {name}")
        elif archive[name].shape != (record_count, *trailing_shape):
            errors.append(f"{name}: expected {(record_count, *trailing_shape)}, got {archive[name].shape}")
        elif not np.isfinite(archive[name]).all():
            errors.append(f"{name}: contains non-finite values")
    missing_provenance = sorted(PROVENANCE_FIELDS - names)
    if missing_provenance:
        errors.append(f"unverifiable provenance; missing fields: {missing_provenance}")
    unique_embeddings = 0
    duplicate_embeddings = 0
    if "text_embedding" in names:
        hashes = [hashlib.sha256(row.tobytes()).digest() for row in archive["text_embedding"]]
        unique_embeddings = len(set(hashes))
        duplicate_embeddings = len(hashes) - unique_embeddings
    split_counts: dict[str, int] = {}
    if "split" in names:
        values, counts = np.unique(archive["split"], return_counts=True)
        split_counts = {str(value): int(count) for value, count in zip(values, counts, strict=True)}
    count_values: dict[str, int] = {}
    if "count_mask" in names:
        values, counts = np.unique(archive["count_mask"].sum(axis=1), return_counts=True)
        count_values = {str(int(value)): int(count) for value, count in zip(values, counts, strict=True)}
    lock_values: dict[str, int] = {}
    if "locked_mask" in names:
        values, counts = np.unique(archive["locked_mask"].sum(axis=1), return_counts=True)
        lock_values = {str(int(value)): int(count) for value, count in zip(values, counts, strict=True)}
    provenance: dict[str, Any] = {}
    hue_balance = None
    if "color_prior" in names:
        mean_prior = np.asarray(archive["color_prior"], dtype=np.float64).mean(axis=0)
        hue_balance = mean_prior[:384].reshape(16, 24).sum(axis=1).tolist()
    if not missing_provenance:
        prompts = np.asarray(archive["prompt"]).astype(str)
        image_ids = np.asarray(archive["image_id"]).astype(str)
        groups = np.asarray(archive["source_group_id"]).astype(str)
        splits = np.asarray(archive["split"]).astype(str)
        licenses = np.asarray(archive["license"]).astype(str)
        mask_area = np.asarray(archive["mask_area_fraction"], dtype=np.float64)
        crops = np.asarray(archive["crop_coordinates"], dtype=np.float64)
        leaking_groups = sorted({
            group for group in set(groups.tolist())
            if len(set(splits[groups == group].tolist())) > 1
        })
        suspicious_background = int(np.sum(mask_area < 0.20))
        if leaking_groups:
            errors.append(f"source-group split leakage: {len(leaking_groups)} groups")
        if np.any(np.char.str_len(licenses) == 0):
            errors.append("license metadata contains empty values")
        if crops.shape != (record_count, 4) or not np.isfinite(crops).all():
            errors.append("crop_coordinates must be finite [N,4]")
        if not np.isfinite(mask_area).all() or np.any((mask_area <= 0) | (mask_area > 1)):
            errors.append("mask_area_fraction must be finite in (0,1]")
        if suspicious_background / max(record_count, 1) > 0.10:
            errors.append("more than 10% of object targets occupy under 20% of the crop")
        provenance = {
            "uniquePromptCount": len(set(prompts.tolist())),
            "duplicatePromptCount": record_count - len(set(prompts.tolist())),
            "uniqueImageCount": len(set(image_ids.tolist())),
            "duplicateImageRecordCount": record_count - len(set(image_ids.tolist())),
            "sourceGroupLeakCount": len(leaking_groups),
            "licenses": sorted(set(licenses.tolist())),
            "russianPromptFraction": float(np.mean([
                any("а" <= character.lower() <= "я" or character.lower() == "ё" for character in prompt)
                for prompt in prompts
            ])),
            "maskAreaMean": float(mask_area.mean()),
            "backgroundDominationSuspiciousCount": suspicious_background,
        }
    return {
        "schemaVersion": 1,
        "candidate": "candidate-11",
        "path": str(path).replace("\\", "/"),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "recordCount": record_count,
        "uniqueEmbeddingCount": unique_embeddings,
        "duplicateEmbeddingCount": duplicate_embeddings,
        "splitCounts": split_counts,
        "countCoverage": count_values,
        "lockCoverage": lock_values,
        "fields": sorted(names),
        "missingProvenanceFields": missing_provenance,
        "provenance": provenance,
        "meanHueBinMass": hue_balance,
        "backgroundDominationAudit": "UNVERIFIABLE" if missing_provenance else "MEASURED",
        "sourceGroupLeakageAudit": "UNVERIFIABLE" if missing_provenance else "MEASURED",
        "pass": not errors,
        "errors": errors,
    }


def build(source: Path, output: Path) -> dict[str, Any]:
    source_archive = np.load(source, allow_pickle=False)
    missing = sorted((set(CORE_FIELDS) | PROVENANCE_FIELDS) - set(source_archive.files))
    if missing:
        raise RuntimeError(
            "refusing to invent a C11 dataset; metadata-rich source is missing: "
            + ", ".join(missing)
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp.npz")
    np.savez_compressed(temporary, **{name: source_archive[name] for name in source_archive.files})
    temporary.replace(output)
    report = audit(output)
    if not report["pass"]:
        output.unlink(missing_ok=True)
        raise RuntimeError(f"built dataset failed audit: {report['errors']}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="ml/palettebrain/data/palettebrain_c11_v1.npz")
    parser.add_argument("--output")
    parser.add_argument("--report", default="ml/palettebrain/reports/candidate-11-dataset-audit.json")
    args = parser.parse_args()
    report = build(Path(args.input), Path(args.output)) if args.output else audit(Path(args.input))
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
