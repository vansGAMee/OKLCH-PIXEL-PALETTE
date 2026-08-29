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
import shutil
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
NEGATIVE_SELECTION_VERSION = "c11-safe-ranking-negative-v3-bounded-global-order"
NEGATIVE_POOL_SIZE = 256
MIN_COLOR_PRIOR_COSINE_DISTANCE = 0.08


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_safe_ranking_negatives(arrays: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Precompute bounded deterministic TRAIN-only semantic negatives.

    Identity evidence is checked before perceptual separation. A row with no
    trustworthy candidate is explicitly marked invalid instead of receiving a
    fabricated within-batch negative.
    """

    required = {
        "split", "source_group_id", "concept_id", "image_id", "content_sha256",
        "target", "color_prior", "teacher_latent",
    }
    missing = sorted(required - arrays.keys())
    if missing:
        raise RuntimeError(f"safe negative construction missing fields: {missing}")
    rows = len(arrays["split"])
    split = np.asarray(arrays["split"]).astype(str)
    groups = np.asarray(arrays["source_group_id"]).astype(str)
    concepts = np.asarray(arrays["concept_id"]).astype(str)
    images = np.asarray(arrays["image_id"]).astype(str)
    contents = np.asarray(arrays["content_sha256"]).astype(str)
    targets = np.asarray(arrays["target"], dtype=np.float32)
    priors = np.asarray(arrays["color_prior"], dtype=np.float32)
    teachers = np.asarray(arrays["teacher_latent"], dtype=np.float32)
    target_hashes = np.asarray([
        hashlib.sha256(np.ascontiguousarray(row).tobytes()).hexdigest()
        for row in targets
    ])
    prior_norms = np.maximum(np.linalg.norm(priors, axis=1), 1e-12)
    negatives = np.zeros_like(priors)
    negative_groups = np.full(rows, "", dtype=f"<U{max(1, max(map(len, groups), default=1))}")
    negative_indices = np.full(rows, -1, dtype=np.int64)
    valid = np.zeros(rows, dtype=np.float32)
    train_indices = np.flatnonzero(split == "train")

    # Candidate identity hashes and ordering are immutable for this archive and
    # therefore paid once.  The previous implementation rebuilt a full boolean
    # mask and sorted an O(N) list independently for every row.
    stable_candidate_keys = {
        int(candidate): hashlib.sha256(
            "|".join((
                NEGATIVE_SELECTION_VERSION,
                groups[candidate],
                concepts[candidate],
                images[candidate],
                contents[candidate],
                target_hashes[candidate],
                str(int(candidate)),
            )).encode("utf-8")
        ).digest()
        for candidate in train_indices
    }
    ordered_train = sorted(
        (int(candidate) for candidate in train_indices),
        key=stable_candidate_keys.__getitem__,
    )

    for row_index_value in train_indices:
        row_index = int(row_index_value)
        candidate_block: list[int] = []
        selected = -1
        for candidate in ordered_train:
            if (
                candidate == row_index
                or groups[candidate] == groups[row_index]
                or concepts[candidate] == concepts[row_index]
                or images[candidate] == images[row_index]
                or contents[candidate] == contents[row_index]
                or target_hashes[candidate] == target_hashes[row_index]
            ):
                continue
            candidate_block.append(candidate)
            if len(candidate_block) < NEGATIVE_POOL_SIZE:
                continue
            candidates = np.asarray(candidate_block, dtype=np.int64)
            cosine = (priors[candidates] @ priors[row_index]) / (
                prior_norms[candidates] * prior_norms[row_index]
            )
            prior_distance = 1.0 - cosine
            separated = prior_distance >= MIN_COLOR_PRIOR_COSINE_DISTANCE
            if separated.any():
                legal = candidates[separated]
                selected = int(legal[int(np.argmin(prior_distance[separated]))])
                break
            candidate_block.clear()

        if selected < 0 and candidate_block:
            candidates = np.asarray(candidate_block, dtype=np.int64)
            cosine = (priors[candidates] @ priors[row_index]) / (
                prior_norms[candidates] * prior_norms[row_index]
            )
            prior_distance = 1.0 - cosine
            separated = prior_distance >= MIN_COLOR_PRIOR_COSINE_DISTANCE
            if separated.any():
                legal = candidates[separated]
                selected = int(legal[int(np.argmin(prior_distance[separated]))])

        if selected < 0:
            continue
        negatives[row_index] = priors[selected]
        negative_groups[row_index] = groups[selected]
        negative_indices[row_index] = selected
        valid[row_index] = 1.0

    return {
        "ranking_negative_color_prior": negatives,
        "ranking_negative_source_group_id": negative_groups,
        "ranking_negative_index": negative_indices,
        "ranking_negative_valid": valid,
        "negative_selection_version": np.asarray(NEGATIVE_SELECTION_VERSION),
    }


def split_membership_leaks(values: np.ndarray, splits: np.ndarray) -> list[str]:
    """Return identities occurring in more than one split in one pass."""
    identities = np.asarray(values).astype(str)
    split_values = np.asarray(splits).astype(str)
    if identities.shape != split_values.shape:
        raise ValueError("identity and split arrays must have matching shapes")
    memberships: dict[str, set[str]] = {}
    for identity, split_value in zip(identities.tolist(), split_values.tolist(), strict=True):
        memberships.setdefault(identity, set()).add(split_value)
    return sorted(identity for identity, seen in memberships.items() if len(seen) > 1)


def audit(path: Path, *, engineering_smoke: bool = False) -> dict[str, Any]:
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
        leaking_groups = split_membership_leaks(groups, splits)
        content_hashes = np.asarray(archive["content_sha256"]).astype(str)
        leaking_content = split_membership_leaks(content_hashes, splits)
        leaking_images = split_membership_leaks(image_ids, splits)
        suspicious_background = int(np.sum(mask_area < 0.20))
        if leaking_groups:
            errors.append(f"source-group split leakage: {len(leaking_groups)} groups")
        if leaking_content:
            errors.append(f"content-hash split leakage: {len(leaking_content)} identities")
        if leaking_images:
            errors.append(f"image split leakage: {len(leaking_images)} identities")
        if np.any(np.char.str_len(licenses) == 0):
            errors.append("license metadata contains empty values")
        if crops.shape != (record_count, 4) or not np.isfinite(crops).all():
            errors.append("crop_coordinates must be finite [N,4]")
        if not np.isfinite(mask_area).all() or np.any((mask_area <= 0) | (mask_area > 1)):
            errors.append("mask_area_fraction must be finite in (0,1]")
        if suspicious_background / max(record_count, 1) > 0.10 and not engineering_smoke:
            errors.append("more than 10% of object targets occupy under 20% of the crop")
        provenance = {
            "uniquePromptCount": len(set(prompts.tolist())),
            "duplicatePromptCount": record_count - len(set(prompts.tolist())),
            "uniqueImageCount": len(set(image_ids.tolist())),
            "duplicateImageRecordCount": record_count - len(set(image_ids.tolist())),
            "sourceGroupLeakCount": len(leaking_groups),
            "contentHashLeakCount": len(leaking_content),
            "imageIdentityLeakCount": len(leaking_images),
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


def build(source: Path, output: Path, *, engineering_smoke: bool = False) -> dict[str, Any]:
    used = (source.stat().st_size if source.is_file() else 0) + (
        output.stat().st_size if output.is_file() else 0
    )
    free = shutil.disk_usage(output.parent if output.parent.exists() else Path.cwd()).free
    print(f"DISK used={used / 1024**3:.2f} GiB free={free / 1024**3:.2f} GiB")
    source_sha256 = sha256_file(source)
    source_archive = np.load(source, allow_pickle=False)
    missing = sorted((set(CORE_FIELDS) | PROVENANCE_FIELDS) - set(source_archive.files))
    if missing:
        raise RuntimeError(
            "refusing to invent a C11 dataset; metadata-rich source is missing: "
            + ", ".join(missing)
        )
    arrays = {name: np.asarray(source_archive[name]) for name in source_archive.files}
    arrays.update(build_safe_ranking_negatives(arrays))
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp.npz")
    np.savez_compressed(temporary, **arrays)
    temporary.replace(output)
    report = audit(output, engineering_smoke=engineering_smoke)
    report["sourceSha256"] = source_sha256
    report["sourcePath"] = str(source).replace("\\", "/")
    if engineering_smoke:
        report["testClassification"] = "ENGINEERING_SMOKE_ONLY"
        report["productionReady"] = False
    if not report["pass"]:
        output.unlink(missing_ok=True)
        raise RuntimeError(f"built dataset failed audit: {report['errors']}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="ml/palettebrain/data/palettebrain_c11_v1.npz")
    parser.add_argument("--output")
    parser.add_argument("--report", default="ml/palettebrain/reports/candidate-11-dataset-audit.json")
    parser.add_argument("--engineering-smoke", action="store_true")
    args = parser.parse_args()
    report = build(Path(args.input), Path(args.output), engineering_smoke=args.engineering_smoke) if args.output else audit(Path(args.input), engineering_smoke=args.engineering_smoke)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
