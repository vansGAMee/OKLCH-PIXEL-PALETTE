"""Canonical, pre-augmentation records for PaletteBrain Candidate 1."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

try:
    from .acquire_sources import load_manifest, verify_acquired_provenance
except ImportError:  # Allow direct execution from the repository root.
    from acquire_sources import load_manifest, verify_acquired_provenance


PREPROCESSING_VERSION = "palettebrain-candidate-records-v1"
PALETTE_HASH_VERSION = "palettebrain-canonical-palette-v1"
SPLIT_HASH_VERSION = "source-group-sha256-bucket-v1"
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
EXPECTED_SPLIT_ALGORITHM = (
    "sha256(source-group-sha256-bucket-v1, splitSeed, source_group_id) modulo 100"
)
REQUIRED_PROVENANCE_FIELDS = frozenset(
    {
        "source",
        "source_id",
        "source_group_id",
        "semantic_group_id",
        "text_origin",
        "palette_origin",
        "semantic_alignment",
        "license",
        "license_status",
        "source_revision",
        "colors",
        "native_count",
        "requested_count",
        "derived_count",
        "quality_weight",
    }
)


class CandidateRecordError(ValueError):
    """Raised when verified inputs cannot form safe canonical records."""


@dataclass(frozen=True)
class SplitConfig:
    seed: int
    algorithm: str
    ranges: dict[str, tuple[int, int]]
    evaluation_config_hash: str


@dataclass(frozen=True)
class CandidateCorpus:
    palette_groups: tuple[dict[str, Any], ...]
    semantic_records: tuple[dict[str, Any], ...]
    split_config: SplitConfig

    def summary(self) -> dict[str, Any]:
        split_counts = {"train": 0, "validation": 0, "test": 0}
        for group in self.palette_groups:
            split_counts[group["split"]] += 1
        return {
            "independent_groups": len(self.palette_groups),
            "semantic_records": len(self.semantic_records),
            "wada_mirrors": sum(
                record.get("is_wada_mirror") is True
                for record in self.semantic_records
            ),
            "splits": split_counts,
        }


def _canonical_colors(colors: Sequence[str]) -> list[str]:
    if not colors:
        raise CandidateRecordError("a canonical palette cannot be empty")
    normalized: list[str] = []
    for color in colors:
        if not isinstance(color, str) or HEX_RE.fullmatch(color) is None:
            raise CandidateRecordError(f"invalid HEX color: {color!r}")
        normalized.append(color.lower())
    return normalized


def canonical_palette_hash(colors: Sequence[str]) -> str:
    """Return the frozen, order-sensitive hash of normalized native colors."""

    payload = PALETTE_HASH_VERSION.encode("ascii") + b"\0" + b"\0".join(
        color.encode("ascii") for color in _canonical_colors(colors)
    )
    return hashlib.sha256(payload).hexdigest()


def source_group_split(
    source_group_id: str,
    split_seed: int,
    split_ranges: Mapping[str, tuple[int, int]],
) -> tuple[str, int]:
    """Assign a source group using the frozen SHA-256 bucket algorithm."""

    if not source_group_id or not isinstance(split_seed, int):
        raise CandidateRecordError("source group and integer split seed are required")
    payload = "\x1f".join(
        (SPLIT_HASH_VERSION, str(split_seed), source_group_id)
    ).encode("utf-8")
    bucket = int.from_bytes(hashlib.sha256(payload).digest(), "big") % 100
    for split_name in ("train", "validation", "test"):
        bounds = split_ranges.get(split_name)
        if bounds is not None and bounds[0] <= bucket <= bounds[1]:
            return split_name, bucket
    raise CandidateRecordError(f"split bucket {bucket} is not assigned")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source_file:
            for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise CandidateRecordError(f"cannot read verified artifact {path}: {exc}") from exc
    return digest.hexdigest()


def _verify_artifacts(manifest: dict[str, Any], raw_dir: Path) -> None:
    for artifact in manifest["artifacts"]:
        path = raw_dir / artifact["path"]
        if not path.is_file():
            raise CandidateRecordError(
                f"missing verified artifact {artifact['id']}; run acquire_sources.py"
            )
        if path.stat().st_size != artifact["bytes"]:
            raise CandidateRecordError(f"size mismatch for {artifact['id']}")
        if _sha256_file(path) != artifact["sha256"]:
            raise CandidateRecordError(f"sha256 mismatch for {artifact['id']}")


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CandidateRecordError(f"cannot parse {path}: {exc}") from exc


def _load_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as csv_file:
            return list(csv.DictReader(csv_file))
    except OSError as exc:
        raise CandidateRecordError(f"cannot parse {path}: {exc}") from exc


def _load_split_config(path: Path) -> SplitConfig:
    freeze = _load_json(path)
    if not isinstance(freeze, dict):
        raise CandidateRecordError("evaluation freeze must be an object")
    split = freeze.get("split")
    if (
        freeze.get("frozenBeforeCandidate1") is not True
        or not isinstance(split, dict)
        or split.get("beforeAugmentation") is not True
        or split.get("algorithm") != EXPECTED_SPLIT_ALGORITHM
    ):
        raise CandidateRecordError(
            "evaluation split must be frozen before Candidate 1 augmentation"
        )
    seed = split.get("splitSeed")
    if not isinstance(seed, int):
        raise CandidateRecordError("frozen split seed must be an integer")
    try:
        ranges = {
            "train": tuple(split["trainBuckets"]),
            "validation": tuple(split["validationBuckets"]),
            "test": tuple(split["testBuckets"]),
        }
    except (KeyError, TypeError) as exc:
        raise CandidateRecordError("frozen split ranges are incomplete") from exc
    if any(
        len(bounds) != 2
        or not all(isinstance(value, int) for value in bounds)
        or bounds[0] > bounds[1]
        for bounds in ranges.values()
    ):
        raise CandidateRecordError("frozen split ranges are invalid")
    memberships = {
        bucket: [
            split_name
            for split_name, bounds in ranges.items()
            if bounds[0] <= bucket <= bounds[1]
        ]
        for bucket in range(100)
    }
    if any(len(split_names) != 1 for split_names in memberships.values()):
        raise CandidateRecordError("frozen split ranges must partition 100 buckets")
    config_hash = freeze.get("configHash")
    if not isinstance(config_hash, str) or re.fullmatch(r"[0-9a-f]{64}", config_hash) is None:
        raise CandidateRecordError("evaluation freeze has no valid config hash")
    return SplitConfig(
        seed=seed,
        algorithm=split["algorithm"],
        ranges=ranges,
        evaluation_config_hash=config_hash,
    )


def _source_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {source["id"]: source for source in manifest["sources"]}


def _artifact_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {artifact["id"]: artifact for artifact in manifest["artifacts"]}


def _source_revision(
    source: dict[str, Any], artifact: dict[str, Any] | None = None
) -> str:
    revision = source["revision"]
    if revision["kind"] == "git_commit":
        return revision["value"]
    if revision["kind"] == "http_snapshot" and artifact is not None:
        etag = revision.get("observed_etag")
        return f"sha256:{artifact['sha256']};etag:{etag}"
    raise CandidateRecordError(f"unsupported revision for source {source['id']}")


def _base_record(
    *,
    source: dict[str, Any],
    source_id: str,
    source_group_id: str,
    colors: Sequence[str],
    split_config: SplitConfig,
    source_revision: str,
    text_origin: str,
    palette_origin: str,
    semantic_alignment: str,
) -> dict[str, Any]:
    canonical_colors = _canonical_colors(colors)
    split_name, split_bucket = source_group_split(
        source_group_id, split_config.seed, split_config.ranges
    )
    return {
        "source": source["id"],
        "source_id": source_id,
        "source_group_id": source_group_id,
        "semantic_group_id": None,
        "text_origin": text_origin,
        "palette_origin": palette_origin,
        "semantic_alignment": semantic_alignment,
        "license": source["license"]["spdx"],
        "license_status": "verified",
        "license_evidence": source["license"]["evidence"],
        "attribution": source["license"]["attribution"],
        "source_revision": source_revision,
        "colors": canonical_colors,
        "canonical_palette_hash": canonical_palette_hash(canonical_colors),
        "canonical_palette_hash_algorithm": PALETTE_HASH_VERSION,
        "native_count": len(canonical_colors),
        "requested_count": len(canonical_colors),
        "derived_count": False,
        "quality_weight": 1.0,
        "split": split_name,
        "split_bucket": split_bucket,
        "split_seed": split_config.seed,
        "split_algorithm": split_config.algorithm,
        "evaluation_config_hash": split_config.evaluation_config_hash,
        "preprocessing_version": PREPROCESSING_VERSION,
    }


def _hexes_from_row(row: dict[str, str]) -> list[str]:
    count_text = row.get("color_count", "")
    try:
        expected_count = int(count_text)
    except ValueError as exc:
        raise CandidateRecordError(f"invalid color_count for {row.get('slug')}") from exc
    colors = [row.get(f"hex_{index}", "") for index in range(1, 13)]
    colors = [color for color in colors if color]
    if len(colors) != expected_count:
        raise CandidateRecordError(f"color count mismatch for {row.get('slug')}")
    return _canonical_colors(colors)


def _color_names_from_row(row: dict[str, str], suffix: str = "") -> list[str]:
    field_suffix = f"_{suffix}" if suffix else ""
    return [
        value
        for index in range(1, 13)
        if (value := row.get(f"color_{index}{field_suffix}", ""))
    ]


def _semantic_fields_from_colorcombinations(
    row: dict[str, str]
) -> dict[str, Any]:
    return {
        "title": row.get("title", ""),
        "title_ja": row.get("title_ja", "") or None,
        "summary": row.get("summary", ""),
        "moods": [mood for mood in row.get("moods", "").split("|") if mood],
        "era": row.get("era", ""),
        "color_names": _color_names_from_row(row),
        "color_names_ja": _color_names_from_row(row, "ja"),
    }


def _validate_corpus(
    corpus: CandidateCorpus, manifest: dict[str, Any]
) -> None:
    sources = _source_map(manifest)
    expected_groups = (
        sources["wada"]["provenance"]["expected_palettes"]
        + sources["colorcombinations"]["provenance"][
            "expected_editorial_palettes"
        ]
        + sources["rang"]["provenance"]["expected_palettes"]
    )
    if len(corpus.palette_groups) != expected_groups:
        raise CandidateRecordError(
            f"expected {expected_groups} independent groups, found {len(corpus.palette_groups)}"
        )
    groups: dict[str, dict[str, Any]] = {}
    for group in corpus.palette_groups:
        group_id = group["source_group_id"]
        if group_id in groups:
            raise CandidateRecordError(f"duplicate source group {group_id}")
        groups[group_id] = group
        if not REQUIRED_PROVENANCE_FIELDS <= group.keys():
            raise CandidateRecordError(f"incomplete provenance for group {group_id}")

    mirror_count = 0
    for record in corpus.semantic_records:
        if not REQUIRED_PROVENANCE_FIELDS <= record.keys():
            raise CandidateRecordError(f"incomplete provenance for {record.get('record_id')}")
        group = groups.get(record["source_group_id"])
        if group is None:
            raise CandidateRecordError("semantic record references an unknown source group")
        for field in (
            "colors",
            "canonical_palette_hash",
            "native_count",
            "requested_count",
            "derived_count",
            "split",
            "split_bucket",
            "split_seed",
            "split_algorithm",
        ):
            if record[field] != group[field]:
                raise CandidateRecordError(
                    f"source-group leakage or palette mismatch for {record['record_id']}"
                )
        if record.get("is_wada_mirror") is True:
            mirror_count += 1
        semantic_fields = record.get("semantic_fields")
        if not isinstance(semantic_fields, dict):
            raise CandidateRecordError("semantic record has no raw semantic fields")
        if {"image", "card_image"} & semantic_fields.keys():
            raise CandidateRecordError("photograph fields may not enter semantic records")

    expected_mirrors = sources["colorcombinations"]["provenance"][
        "expected_wada_mirrors"
    ]
    expected_records = (
        sources["wada"]["provenance"]["expected_palettes"]
        + sources["colorcombinations"]["provenance"]["expected_rows"]
        + sources["rang"]["provenance"]["expected_palettes"]
    )
    if mirror_count != expected_mirrors:
        raise CandidateRecordError(
            f"expected {expected_mirrors} mirrors, found {mirror_count}"
        )
    if len(corpus.semantic_records) != expected_records:
        raise CandidateRecordError(
            f"expected {expected_records} original records, found {len(corpus.semantic_records)}"
        )


def build_candidate_records(
    *,
    manifest_path: Path | None = None,
    raw_dir: Path | None = None,
    evaluation_freeze_path: Path | None = None,
) -> CandidateCorpus:
    """Build canonical groups and raw semantic records before augmentation."""

    package_dir = Path(__file__).resolve().parent
    manifest_path = manifest_path or package_dir / "source_manifest.v1.json"
    raw_dir = raw_dir or package_dir / "data" / "raw"
    evaluation_freeze_path = (
        evaluation_freeze_path
        or package_dir / "reports" / "evaluation-freeze.v1.json"
    )
    manifest = load_manifest(manifest_path)
    _verify_artifacts(manifest, raw_dir)
    try:
        verify_acquired_provenance(manifest, raw_dir)
    except ValueError as exc:
        raise CandidateRecordError(f"raw provenance validation failed: {exc}") from exc
    split_config = _load_split_config(evaluation_freeze_path)
    sources = _source_map(manifest)
    artifacts = _artifact_map(manifest)

    palette_groups: list[dict[str, Any]] = []
    semantic_records: list[dict[str, Any]] = []
    groups_by_id: dict[str, dict[str, Any]] = {}

    wada_source = sources["wada"]
    wada_policy = wada_source["provenance"]
    wada_artifact = artifacts["wada-colors"]
    wada_colors = _load_json(raw_dir / wada_artifact["path"])
    plates: dict[int, list[tuple[str, str]]] = {}
    for color in wada_colors:
        for plate_id in color["combinations"]:
            plates.setdefault(plate_id, []).append((color["hex"], color["name"]))
    for plate_id in sorted(plates):
        colors = [color for color, _name in plates[plate_id]]
        names = [name for _color, name in plates[plate_id]]
        group_id = wada_policy["source_group_id_template"].format(plate_id=plate_id)
        base = _base_record(
            source=wada_source,
            source_id=f"plate-{plate_id:03d}",
            source_group_id=group_id,
            colors=colors,
            split_config=split_config,
            source_revision=_source_revision(wada_source),
            text_origin=wada_policy["text_origin"],
            palette_origin=wada_policy["palette_origin"],
            semantic_alignment=wada_policy["semantic_alignment"],
        )
        group = {**base, "record_kind": "palette_group"}
        palette_groups.append(group)
        groups_by_id[group_id] = group
        semantic_records.append(
            {
                **base,
                "record_kind": "semantic_record",
                "record_id": f"wada:plate-{plate_id:03d}:color-names",
                "semantic_fields": {"color_names": names},
                "is_independent_palette": True,
                "is_wada_mirror": False,
            }
        )

    colorcombinations_source = sources["colorcombinations"]
    colorcombinations_policy = colorcombinations_source["provenance"]
    colorcombinations_artifact = artifacts["colorcombinations-palettes"]
    colorcombinations_revision = _source_revision(
        colorcombinations_source, colorcombinations_artifact
    )
    rows = _load_csv(raw_dir / colorcombinations_artifact["path"])
    mirror_pattern = re.compile(colorcombinations_policy["wada_mirror_slug_regex"])
    for row in rows:
        slug = row["slug"]
        colors = _hexes_from_row(row)
        mirror_match = mirror_pattern.match(slug)
        if mirror_match is not None:
            plate_id = int(mirror_match.group(1))
            group_id = manifest["deduplication"][
                "shared_source_group_id_template"
            ].format(plate_id=plate_id)
            group = groups_by_id.get(group_id)
            if group is None or colors != group["colors"]:
                raise CandidateRecordError(f"Wada mirror mismatch for {slug}")
            text_origin = colorcombinations_policy["wada_mirror_text_origin"]
            palette_origin = colorcombinations_policy["wada_mirror_palette_origin"]
            semantic_alignment = colorcombinations_policy[
                "wada_mirror_semantic_alignment"
            ]
            is_independent = False
            is_wada_mirror = True
        else:
            group_id = colorcombinations_policy[
                "editorial_source_group_id_template"
            ].format(slug=slug)
            text_origin = colorcombinations_policy["editorial_text_origin"]
            palette_origin = colorcombinations_policy["editorial_palette_origin"]
            semantic_alignment = colorcombinations_policy[
                "editorial_semantic_alignment"
            ]
            is_independent = True
            is_wada_mirror = False

        base = _base_record(
            source=colorcombinations_source,
            source_id=slug,
            source_group_id=group_id,
            colors=colors,
            split_config=split_config,
            source_revision=colorcombinations_revision,
            text_origin=text_origin,
            palette_origin=palette_origin,
            semantic_alignment=semantic_alignment,
        )
        if is_independent:
            group = {
                **base,
                "record_kind": "palette_group",
                "source_reference_url": row.get("canonical_url") or None,
            }
            palette_groups.append(group)
            groups_by_id[group_id] = group
        semantic_records.append(
            {
                **base,
                "record_kind": "semantic_record",
                "record_id": f"colorcombinations:{slug}:metadata",
                "semantic_fields": _semantic_fields_from_colorcombinations(row),
                "source_reference_url": row.get("canonical_url") or None,
                "is_independent_palette": is_independent,
                "is_wada_mirror": is_wada_mirror,
            }
        )

    rang_source = sources["rang"]
    rang_policy = rang_source["provenance"]
    rang_artifacts = sorted(
        (
            artifact
            for artifact in manifest["artifacts"]
            if artifact["source"] == "rang"
        ),
        key=lambda artifact: artifact["path"],
    )
    for artifact in rang_artifacts:
        palette = _load_json(raw_dir / artifact["path"])
        slug = Path(artifact["path"]).stem.lower()
        group_id = rang_policy["source_group_id_template"].format(name_slug=slug)
        base = _base_record(
            source=rang_source,
            source_id=slug,
            source_group_id=group_id,
            colors=palette["colors"],
            split_config=split_config,
            source_revision=_source_revision(rang_source),
            text_origin=rang_policy["text_origin"],
            palette_origin=rang_policy["palette_origin"],
            semantic_alignment=rang_policy["semantic_alignment"],
        )
        source_reference_url = palette.get("source", {}).get("url")
        group = {
            **base,
            "record_kind": "palette_group",
            "native_order": list(palette["order"]),
            "source_reference_url": source_reference_url,
        }
        palette_groups.append(group)
        groups_by_id[group_id] = group
        semantic_records.append(
            {
                **base,
                "record_kind": "semantic_record",
                "record_id": f"rang:{slug}:native-notes",
                "semantic_fields": {
                    "name": palette["name"],
                    "notes": list(palette["notes"]),
                    "native_order": list(palette["order"]),
                },
                "source_reference_url": source_reference_url,
                "is_independent_palette": True,
                "is_wada_mirror": False,
            }
        )

    corpus = CandidateCorpus(
        palette_groups=tuple(palette_groups),
        semantic_records=tuple(semantic_records),
        split_config=split_config,
    )
    _validate_corpus(corpus, manifest)
    return corpus
