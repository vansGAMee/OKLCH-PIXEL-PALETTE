"""Strong acceptance check for a versioned Candidate 11 visual source."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import numpy as np


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--source-report", required=True, type=Path)
    parser.add_argument("--bounded-report", required=True, type=Path)
    parser.add_argument("--protected-old-source", required=True, type=Path)
    parser.add_argument("--expected-old-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite acceptance report: {args.output}")
    started = time.perf_counter()
    source_report = json.loads(args.source_report.read_text(encoding="utf-8"))
    bounded = json.loads(args.bounded_report.read_text(encoding="utf-8"))
    source_sha = sha256_file(args.source)
    old_sha = sha256_file(args.protected_old_source)

    failures: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            failures.append(message)

    require(source_report.get("sha256") == source_sha, "source/report SHA mismatch")
    require(old_sha == args.expected_old_sha256, "protected old source changed")
    require(
        source_report.get("acceptanceContract")
        == "SIGLIP_TEXT_IMAGE_RELEVANCE_ONLY",
        "wrong acquisition acceptance contract",
    )
    require(
        source_report.get("paletteStatisticsInfluenceAcceptance") is False,
        "palette statistics influence acceptance",
    )
    require(bounded.get("networkRecordsAdded") == 0, "bounded run used network")
    require(bounded.get("globalReacquisition") is False, "global reacquisition occurred")
    require(bounded.get("relevanceCacheFullyReused") is True, "relevance cache not fully reused")
    require(bounded.get("coveragePass") is True, "coverage gate failed")
    require(
        bounded.get("rawRecordsAtStart") == source_report.get("rawAcquired"),
        "bounded/source raw lineage mismatch",
    )

    with np.load(args.source, allow_pickle=False) as archive:
        required = {
            "content_sha256", "perceptual_hash64", "source_group_id", "split",
            "concept_id", "provider", "source_url", "license", "color_prior",
            "target", "text_embedding", "teacher_latent", "quality_weight",
            "builder_sha256", "pca_artifact_sha256",
        }
        missing = sorted(required - set(archive.files))
        require(not missing, f"missing arrays: {missing}")
        require("palette_semantic_score" not in archive.files, "palette family score leaked into source")
        require("palette_semantic_rule_id" not in archive.files, "palette family rule leaked into source")

        hashes = archive["content_sha256"].astype(str)
        phashes = archive["perceptual_hash64"].astype(str)
        groups = archive["source_group_id"].astype(str)
        splits = archive["split"].astype(str)
        concepts = archive["concept_id"].astype(str)
        priors = archive["color_prior"].astype(np.float32)
        row_count = len(hashes)
        unique_images = len(set(hashes))

        require(row_count == int(source_report.get("rows", -1)), "row count mismatch")
        require(
            unique_images == int(source_report.get("validUniqueImages", -1)),
            "unique image count mismatch",
        )
        require(unique_images >= 2500, "preferred image target not met")
        require(len(set(groups)) == unique_images, "source-group/image cardinality mismatch")
        require(len(set(phashes)) == unique_images, "perceptual duplicate survived")
        require(row_count == unique_images * 4, "unexpected rows per image")
        require(set(splits) == {"train", "val", "test"}, "split coverage invalid")
        require(np.isfinite(priors).all(), "non-finite color prior")
        require(
            float(np.max(np.abs(priors.sum(axis=1) - 1.0))) <= 1e-5,
            "color priors are not normalized",
        )
        require(np.isfinite(archive["target"]).all(), "non-finite target")
        require(np.isfinite(archive["text_embedding"]).all(), "non-finite text embedding")
        require(np.isfinite(archive["teacher_latent"]).all(), "non-finite teacher latent")
        require(
            np.array_equal(archive["quality_weight"], np.ones(row_count, dtype=np.float32)),
            "palette-dependent quality weighting present",
        )
        for field in ("content_sha256", "source_group_id", "concept_id", "provider", "source_url", "license"):
            require(not np.any(archive[field].astype(str) == ""), f"blank provenance field: {field}")

        group_contract: dict[str, tuple[str, str, str]] = {}
        for group, split, concept, content_hash in zip(groups, splits, concepts, hashes, strict=True):
            value = (split, concept, content_hash)
            previous = group_contract.setdefault(group, value)
            if previous != value:
                failures.append(f"split/provenance leakage in source group {group}")
                break

        embedded_builder_sha = str(archive["builder_sha256"].item())
        embedded_pca_sha = str(archive["pca_artifact_sha256"].item())

    pca_path = Path(str(source_report.get("pcaPath", "")))
    require(pca_path.is_file(), "PCA artifact missing")
    if pca_path.is_file():
        require(sha256_file(pca_path) == embedded_pca_sha, "PCA SHA mismatch")
    require(embedded_builder_sha == source_report.get("builderSha256"), "builder lineage mismatch")
    diversity = source_report.get("paletteDiversity", {})
    require(diversity.get("diagnosticOnly") is True, "diversity not diagnostic-only")
    require(diversity.get("influencesAcceptance") is False, "diversity influences acceptance")
    require(int(diversity.get("occupiedBins", 0)) >= 300, "palette bin diversity too low")
    require(int(diversity.get("hueBinsCovered", 0)) >= 14, "hue diversity too low")

    elapsed = time.perf_counter() - started
    result = {
        "testClassification": "REAL_VERSIONED_SOURCE_ACCEPTANCE",
        "pass": not failures,
        "source": str(args.source).replace("\\", "/"),
        "sourceSha256": source_sha,
        "protectedOldSourceSha256": old_sha,
        "oldArtifactUnchanged": old_sha == args.expected_old_sha256,
        "rows": int(source_report.get("rows", 0)),
        "uniqueImages": int(source_report.get("validUniqueImages", 0)),
        "networkRecordsAdded": bounded.get("networkRecordsAdded"),
        "relevanceCacheHits": bounded.get("relevanceCacheHitsAtStart"),
        "rawRecords": bounded.get("rawRecordsAtStart"),
        "sourceConstructionSeconds": source_report.get("elapsedSeconds"),
        "sourceImagesPerSecond": source_report.get("validImagesPerSecond"),
        "acceptanceValidationSeconds": elapsed,
        "paletteDiversity": diversity,
        "failures": failures,
    }
    atomic_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
