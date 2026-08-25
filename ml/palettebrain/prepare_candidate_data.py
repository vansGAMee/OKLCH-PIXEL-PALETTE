"""Prepare the legal, provenance-rich PaletteBrain Candidate 1 archive.

Real source groups arrive from :mod:`candidate_records` with their split already
frozen.  This module only augments *inside* that assignment with honest metadata
prompts, perceptual count reductions, and target-bound lock examples.  Direct
anchors are training-only and the old q8 synthetic archive remains a bounded,
low-weight auxiliary source.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

try:
    from .candidate_records import (
        CandidateCorpus,
        build_candidate_records,
        canonical_palette_hash,
        source_group_split,
    )
    from .color_math import CHROMA_HEADROOM, LIGHTNESS_MIN, LIGHTNESS_RANGE, max_srgb_chroma_at
    from .dataset import (
        EMBEDDING_DIM,
        MAX_COLORS,
        SPLIT_IDS,
        seed_noise_from_uint32,
        stable_uint64,
        synthesize_complete_palette,
        validate_prepared_archive,
        validate_source_archive,
    )
    from .e5_embedding import (
        BROWSER_E5_MODEL_ID,
        BROWSER_E5_REVISION,
        BROWSER_E5_SHA256,
        E5_MODEL_ID,
        E5_REVISION,
        embed_texts,
        load_encoder,
    )
    from .palette_targets import family_palette, hex_palette_target, perceptual_subset
except ImportError:  # Support direct execution from the repository root.
    from candidate_records import (  # type: ignore[no-redef]
        CandidateCorpus,
        build_candidate_records,
        canonical_palette_hash,
        source_group_split,
    )
    from color_math import (  # type: ignore[no-redef]
        CHROMA_HEADROOM,
        LIGHTNESS_MIN,
        LIGHTNESS_RANGE,
        max_srgb_chroma_at,
    )
    from dataset import (  # type: ignore[no-redef]
        EMBEDDING_DIM,
        MAX_COLORS,
        SPLIT_IDS,
        seed_noise_from_uint32,
        stable_uint64,
        synthesize_complete_palette,
        validate_prepared_archive,
        validate_source_archive,
    )
    from e5_embedding import (  # type: ignore[no-redef]
        BROWSER_E5_MODEL_ID,
        BROWSER_E5_REVISION,
        BROWSER_E5_SHA256,
        E5_MODEL_ID,
        E5_REVISION,
        embed_texts,
        load_encoder,
    )
    from palette_targets import (  # type: ignore[no-redef]
        family_palette,
        hex_palette_target,
        perceptual_subset,
    )


DATASET_VERSION = "palettebrain-candidate1-v1"
PREPARATION_VERSION = "palettebrain-candidate1-prepare-v1"
CONTENT_HASH_VERSION = "palettebrain-array-content-sha256-v1"
LOCK_VERSION = "target-bound-none-one-multi-v1"
DEFAULT_OUTPUT = "ml/palettebrain/data/palettebrain_candidate1_v1.npz"
DEFAULT_REPORT = "ml/palettebrain/reports/candidate1-data.v1.json"
SPLIT_NAME_TO_ID = {
    "train": SPLIT_IDS["train"],
    "validation": SPLIT_IDS["val"],
    "test": SPLIT_IDS["test"],
}


@dataclass(frozen=True)
class PreparationConfig:
    """Frozen preprocessing choices which contribute to ``configHash``."""

    dataset_version: str = DATASET_VERSION
    embedding_batch_size: int = 128
    legacy_max_rows: int = 2500
    legacy_sampling_cap: float = 0.15
    direct_family_weight: float = 0.60
    direct_composition_weight: float = 0.70
    legacy_weight: float = 0.08
    derived_count_factor: float = 0.90
    smoke: bool = False
    smoke_max_real_groups: int = 12
    smoke_max_new_texts: int = 128
    smoke_max_legacy_groups: int = 4

    def validate(self) -> None:
        if not self.dataset_version.strip():
            raise ValueError("dataset_version must be non-empty")
        if self.embedding_batch_size < 1:
            raise ValueError("embedding_batch_size must be positive")
        if self.legacy_max_rows < 0:
            raise ValueError("legacy_max_rows may not be negative")
        if not 0.0 < self.legacy_sampling_cap <= 0.15:
            raise ValueError("legacy_sampling_cap must be in (0, 0.15]")
        for name in (
            "direct_family_weight",
            "direct_composition_weight",
            "legacy_weight",
            "derived_count_factor",
        ):
            if float(getattr(self, name)) <= 0.0:
                raise ValueError(f"{name} must be positive")
        if self.smoke and (
            self.smoke_max_real_groups < 1
            or self.smoke_max_new_texts < 1
            or self.smoke_max_legacy_groups < 0
        ):
            raise ValueError("smoke limits must be positive (legacy groups may be zero)")


@dataclass(frozen=True)
class PromptVariant:
    text: str
    kind: str
    weight_factor: float


@dataclass(frozen=True)
class BaseExample:
    source: str
    source_id: str
    source_record_id: str
    source_group_id: str
    semantic_group_id: str
    text: str
    prompt_kind: str
    text_origin: str
    palette_origin: str
    semantic_alignment: str
    license: str
    source_revision: str
    palette_hash: str
    palette_hex_json: str
    native_count: int
    derived_count: bool
    count: int
    split: int
    target: np.ndarray
    physical_colors: np.ndarray
    quality_weight: float
    holdout_eligible: bool
    archived_embedding: np.ndarray | None = None


NewTextEmbedder = Callable[[Sequence[str]], np.ndarray]


def _clean_text(value: Any) -> str:
    return " ".join(str(value).split()).strip()


def honest_prompt_variants(record: Mapping[str, Any]) -> tuple[PromptVariant, ...]:
    """Derive prompts only from the source's audited semantic fields.

    The function intentionally has no scene/style lexicon.  Joining source
    strings with punctuation is allowed; adding semantic nouns or adjectives is
    not.  Exact duplicate strings within one record are removed deterministically.
    """

    fields = record.get("semantic_fields")
    if not isinstance(fields, Mapping):
        raise ValueError("semantic record must contain semantic_fields")
    candidates: list[PromptVariant] = []

    names = fields.get("color_names")
    if isinstance(names, Sequence) and not isinstance(names, (str, bytes)):
        cleaned = [_clean_text(value) for value in names if _clean_text(value)]
        if cleaned:
            candidates.append(PromptVariant(", ".join(cleaned), "color_names", 0.90))

    for key, factor in (("title", 1.0), ("summary", 1.0), ("era", 0.55)):
        text = _clean_text(fields.get(key, ""))
        if text:
            candidates.append(PromptVariant(text, key, factor))

    moods = fields.get("moods")
    if isinstance(moods, Sequence) and not isinstance(moods, (str, bytes)):
        for mood in moods:
            text = _clean_text(mood)
            if text:
                candidates.append(PromptVariant(text, "mood", 0.60))

    name = _clean_text(fields.get("name", ""))
    if name:
        candidates.append(PromptVariant(name, "rang_name", 1.0))
    notes = fields.get("notes")
    if isinstance(notes, Sequence) and not isinstance(notes, (str, bytes)):
        for note in notes:
            clean_note = _clean_text(note)
            if clean_note:
                text = f"{name}: {clean_note}" if name else clean_note
                candidates.append(PromptVariant(text, "rang_name_note", 0.95))

    unique: list[PromptVariant] = []
    seen: set[str] = set()
    for variant in candidates:
        key = variant.text.casefold()
        if key not in seen:
            seen.add(key)
            unique.append(variant)
    return tuple(unique)


def _quality_for_real(record: Mapping[str, Any], variant: PromptVariant) -> float:
    palette_origin = str(record["palette_origin"])
    alignment = str(record["semantic_alignment"])
    origin_weight = {
        "human_curated": 1.00,
        "human_curated_extracted": 1.08,
    }.get(palette_origin)
    if origin_weight is None:
        raise ValueError(f"real record has unsupported palette origin {palette_origin!r}")
    alignment_weight = {"direct": 1.0, "metadata_derived": 0.88, "weak": 0.70}.get(
        alignment
    )
    if alignment_weight is None:
        raise ValueError(f"unsupported semantic alignment {alignment!r}")
    return origin_weight * alignment_weight * variant.weight_factor


def _physical_from_target(target: np.ndarray, count: int) -> np.ndarray:
    physical = np.zeros((MAX_COLORS, 4), dtype=np.float32)
    for index in range(count):
        row = np.asarray(target[index], dtype=np.float64)
        lightness = LIGHTNESS_MIN + LIGHTNESS_RANGE / (1.0 + math.exp(-float(row[0])))
        hue_norm = math.hypot(float(row[2]), float(row[3]))
        if hue_norm <= 1e-8:
            hue_sin, hue_cos, chroma = 0.0, 0.0, 0.0
        else:
            hue_sin = float(row[2]) / hue_norm
            hue_cos = float(row[3]) / hue_norm
            hue = math.degrees(math.atan2(hue_sin, hue_cos)) % 360.0
            relative = 1.0 / (1.0 + math.exp(-float(row[1])))
            chroma = relative * max_srgb_chroma_at(lightness, hue) * CHROMA_HEADROOM
        physical[index] = (lightness, chroma, hue_sin, hue_cos)
    return physical


def _target_hash(target: np.ndarray, count: int) -> str:
    digest = hashlib.sha256()
    digest.update(b"palettebrain-physical-target-v1\0")
    digest.update(np.ascontiguousarray(target[:count, :4], dtype=np.float32).tobytes())
    return digest.hexdigest()


def _selected_real_groups(corpus: CandidateCorpus, config: PreparationConfig) -> set[str]:
    group_ids = {str(group["source_group_id"]) for group in corpus.palette_groups}
    if not config.smoke or len(group_ids) <= config.smoke_max_real_groups:
        return group_ids
    ordered = sorted(
        corpus.palette_groups,
        key=lambda group: (
            stable_uint64(PREPARATION_VERSION, "smoke-real", group["source_group_id"]),
            str(group["source_group_id"]),
        ),
    )
    chosen: list[str] = []
    for split in ("train", "validation", "test"):
        match = next((group for group in ordered if group["split"] == split), None)
        if match is not None and len(chosen) < config.smoke_max_real_groups:
            chosen.append(str(match["source_group_id"]))
    for group in ordered:
        if len(chosen) >= config.smoke_max_real_groups:
            break
        group_id = str(group["source_group_id"])
        if group_id not in chosen:
            chosen.append(group_id)
    return set(chosen)


def _real_base_examples(corpus: CandidateCorpus, config: PreparationConfig) -> list[BaseExample]:
    selected_groups = _selected_real_groups(corpus, config)
    seen_prompts: set[tuple[str, str]] = set()
    examples: list[BaseExample] = []
    for record in corpus.semantic_records:
        group_id = str(record["source_group_id"])
        if group_id not in selected_groups:
            continue
        split_name = str(record["split"])
        if split_name not in SPLIT_NAME_TO_ID:
            raise ValueError(f"unknown frozen split {split_name!r}")
        expected_split, expected_bucket = source_group_split(
            group_id, corpus.split_config.seed, corpus.split_config.ranges
        )
        if expected_split != split_name or int(record["split_bucket"]) != expected_bucket:
            raise ValueError(f"record no longer matches its frozen split: {group_id}")
        colors = tuple(str(value).lower() for value in record["colors"])
        native_count = int(record["native_count"])
        if native_count != len(colors) or not 2 <= native_count <= MAX_COLORS:
            raise ValueError(f"real palette must have a native count in 2..9: {group_id}")
        for variant in honest_prompt_variants(record):
            prompt_key = (group_id, variant.text.casefold())
            if prompt_key in seen_prompts:
                continue
            seen_prompts.add(prompt_key)
            base_quality = _quality_for_real(record, variant)
            for count in range(2, native_count + 1):
                subset = list(colors) if count == native_count else perceptual_subset(colors, count)
                target, physical = hex_palette_target(subset)
                derived = count != native_count
                quality = base_quality * (config.derived_count_factor if derived else 1.0)
                examples.append(
                    BaseExample(
                        source=str(record["source"]),
                        source_id=str(record["source_id"]),
                        source_record_id=str(record["record_id"]),
                        source_group_id=group_id,
                        semantic_group_id=str(record.get("semantic_group_id") or ""),
                        text=variant.text,
                        prompt_kind=variant.kind,
                        text_origin=str(record["text_origin"]),
                        palette_origin=str(record["palette_origin"]),
                        semantic_alignment=str(record["semantic_alignment"]),
                        license=str(record["license"]),
                        source_revision=str(record["source_revision"]),
                        palette_hash=canonical_palette_hash(subset),
                        palette_hex_json=json.dumps(subset, separators=(",", ":")),
                        native_count=native_count,
                        derived_count=derived,
                        count=count,
                        split=SPLIT_NAME_TO_ID[split_name],
                        target=target,
                        physical_colors=physical,
                        quality_weight=quality,
                        holdout_eligible=True,
                    )
                )
    return examples


def _validate_anchors(anchors: Mapping[str, Any]) -> None:
    if anchors.get("schemaVersion") != 1 or not isinstance(anchors.get("families"), list):
        raise ValueError("direct anchor fixture has an unsupported schema")
    if not isinstance(anchors.get("explicitPalettes"), list):
        raise ValueError("direct anchor fixture has no explicitPalettes")


def _anchor_base_examples(
    anchors: Mapping[str, Any], config: PreparationConfig, anchor_sha256: str
) -> list[BaseExample]:
    _validate_anchors(anchors)
    examples: list[BaseExample] = []
    revision = f"sha256:{anchor_sha256}"
    for family in anchors["families"]:
        family_id = str(family["id"])
        anchor_hex = str(family["anchorHex"])
        group_id = f"direct-anchor:family:{family_id}"
        for term_index, term in enumerate(family["terms"]):
            if not isinstance(term, list) or len(term) != 3:
                raise ValueError(f"invalid term in direct anchor family {family_id}")
            text, language, modifier = map(str, term)
            text = _clean_text(text)
            if not text:
                raise ValueError("direct anchor text may not be empty")
            for count in range(2, MAX_COLORS + 1):
                target, physical = family_palette(
                    anchor_hex, count, family=family_id, modifier=modifier
                )
                examples.append(
                    BaseExample(
                        source="direct_anchors",
                        source_id=f"family:{family_id}:term:{term_index}",
                        source_record_id=f"direct:{family_id}:{term_index}",
                        source_group_id=group_id,
                        semantic_group_id=f"direct-family:{family_id}",
                        text=text,
                        prompt_kind=f"direct_family_{language}_{modifier}",
                        text_origin="synthetic",
                        palette_origin="synthetic",
                        semantic_alignment="direct",
                        license=str(anchors.get("license", "project-owned")),
                        source_revision=revision,
                        palette_hash=_target_hash(target, count),
                        palette_hex_json="[]",
                        native_count=count,
                        derived_count=False,
                        count=count,
                        split=SPLIT_IDS["train"],
                        target=target,
                        physical_colors=physical,
                        quality_weight=config.direct_family_weight,
                        holdout_eligible=False,
                    )
                )
    for palette in anchors["explicitPalettes"]:
        palette_id = str(palette["id"])
        colors = tuple(str(value).lower() for value in palette["colors"])
        if len(colors) != MAX_COLORS:
            raise ValueError(f"explicit direct palette {palette_id} must have 9 colors")
        group_id = f"direct-anchor:composition:{palette_id}"
        for text_index, text_entry in enumerate(palette["texts"]):
            if not isinstance(text_entry, list) or len(text_entry) != 2:
                raise ValueError(f"invalid text for explicit direct palette {palette_id}")
            text, language = map(str, text_entry)
            for count in range(2, MAX_COLORS + 1):
                subset = perceptual_subset(colors, count)
                target, physical = hex_palette_target(subset)
                examples.append(
                    BaseExample(
                        source="direct_anchors",
                        source_id=f"composition:{palette_id}:text:{text_index}",
                        source_record_id=f"direct:{palette_id}:{text_index}",
                        source_group_id=group_id,
                        semantic_group_id=f"direct-composition:{palette_id}",
                        text=_clean_text(text),
                        prompt_kind=f"direct_composition_{language}",
                        text_origin="synthetic",
                        palette_origin="synthetic",
                        semantic_alignment="direct",
                        license=str(anchors.get("license", "project-owned")),
                        source_revision=revision,
                        palette_hash=canonical_palette_hash(subset),
                        palette_hex_json=json.dumps(subset, separators=(",", ":")),
                        native_count=MAX_COLORS,
                        derived_count=count != MAX_COLORS,
                        count=count,
                        split=SPLIT_IDS["train"],
                        target=target,
                        physical_colors=physical,
                        quality_weight=config.direct_composition_weight
                        * (config.derived_count_factor if count != MAX_COLORS else 1.0),
                        holdout_eligible=False,
                    )
                )
    return examples


def _limit_new_texts(examples: list[BaseExample], config: PreparationConfig) -> list[BaseExample]:
    if not config.smoke:
        return examples
    by_text: dict[str, list[BaseExample]] = defaultdict(list)
    order: list[str] = []
    for example in examples:
        if example.text not in by_text:
            order.append(example.text)
        by_text[example.text].append(example)
    if len(order) <= config.smoke_max_new_texts:
        return examples

    chosen: list[str] = []
    seen_groups: set[str] = set()
    for text in order:
        group_id = by_text[text][0].source_group_id
        if group_id not in seen_groups and len(chosen) < config.smoke_max_new_texts:
            chosen.append(text)
            seen_groups.add(group_id)
    for text in order:
        if len(chosen) >= config.smoke_max_new_texts:
            break
        if text not in chosen:
            chosen.append(text)
    allowed = set(chosen)
    return [example for example in examples if example.text in allowed]


def _selected_legacy_indices(
    source: Mapping[str, np.ndarray], config: PreparationConfig
) -> list[int]:
    groups = np.asarray(source["groups"])
    indices_by_group: dict[str, list[int]] = defaultdict(list)
    for index, group in enumerate(groups):
        indices_by_group[str(group)].append(index)
    ordered_groups = sorted(
        indices_by_group,
        key=lambda group: (stable_uint64(PREPARATION_VERSION, "legacy-select", group), group),
    )
    if config.smoke:
        ordered_groups = ordered_groups[: config.smoke_max_legacy_groups]
    selected: list[int] = []
    for group in ordered_groups:
        group_indices = indices_by_group[group]
        if len(selected) + len(group_indices) > config.legacy_max_rows:
            continue
        selected.extend(group_indices)
    return sorted(selected)


def _legacy_base_examples(
    source: Mapping[str, np.ndarray], corpus: CandidateCorpus, config: PreparationConfig
) -> list[BaseExample]:
    validate_source_archive(source)
    if "groups" not in source:
        raise ValueError("legacy source archive must include groups")
    examples: list[BaseExample] = []
    for source_index in _selected_legacy_indices(source, config):
        text = _clean_text(source["texts"][source_index])
        group = str(source["groups"][source_index])
        group_id = f"legacy-synthetic:{group}"
        count = 2 + int(
            stable_uint64(PREPARATION_VERSION, "legacy-count", source_index, group, text) % 8
        )
        target = synthesize_complete_palette(
            float(source["lightnesses"][source_index]),
            float(source["chromas"][source_index]),
            float(source["hues"][source_index]),
            int(source["harmonies"][source_index]),
            count,
        )
        target[:, 4] = 0.0
        physical = _physical_from_target(target, count)
        examples.append(
            BaseExample(
                source="legacy_synthetic",
                source_id=f"row:{source_index}",
                source_record_id=f"legacy:{source_index}",
                source_group_id=group_id,
                semantic_group_id=group,
                text=text,
                prompt_kind="legacy_repository_prompt",
                text_origin="synthetic",
                palette_origin="synthetic",
                semantic_alignment="weak",
                license="project-owned",
                source_revision="ml/dataset_embeddings.npz",
                palette_hash=_target_hash(target, count),
                palette_hex_json="[]",
                native_count=count,
                derived_count=False,
                count=count,
                # Auxiliary procedural supervision must never influence real
                # validation early stopping or the final real-palette test.
                split=SPLIT_IDS["train"],
                target=target,
                physical_colors=physical,
                quality_weight=config.legacy_weight,
                holdout_eligible=False,
                archived_embedding=np.asarray(source["embeddings"][source_index], dtype=np.float32),
            )
        )
    return examples


def _lock_variants(count: int, key: str) -> tuple[tuple[str, np.ndarray], ...]:
    none = np.zeros(MAX_COLORS, dtype=np.float32)
    rng = np.random.default_rng(stable_uint64(PREPARATION_VERSION, LOCK_VERSION, key))
    one = np.zeros(MAX_COLORS, dtype=np.float32)
    one[int(rng.integers(0, count))] = 1.0
    variants: list[tuple[str, np.ndarray]] = [("none", none), ("one", one)]
    if count >= 3:
        lock_count = 2 + int(rng.integers(0, count - 2))
        chosen = rng.choice(count, size=lock_count, replace=False)
        multi = np.zeros(MAX_COLORS, dtype=np.float32)
        multi[chosen] = 1.0
        variants.append(("multi", multi))
    return tuple(variants)


def _normalized_embeddings(values: np.ndarray, label: str) -> np.ndarray:
    result = np.asarray(values, dtype=np.float32)
    if result.ndim != 2 or result.shape[1] != EMBEDDING_DIM:
        raise ValueError(f"{label} embeddings must have shape [N, {EMBEDDING_DIM}]")
    if not np.isfinite(result).all():
        raise ValueError(f"{label} embeddings contain non-finite values")
    norms = np.linalg.norm(result, axis=1, keepdims=True)
    if np.any(norms <= 1e-8):
        raise ValueError(f"{label} embeddings contain a zero vector")
    return (result / norms).astype(np.float32, copy=False)


def _expand_examples(
    base_examples: Sequence[BaseExample], new_text_embedder: NewTextEmbedder
) -> dict[str, np.ndarray]:
    unique_new_texts = list(
        dict.fromkeys(example.text for example in base_examples if example.archived_embedding is None)
    )
    embedded = _normalized_embeddings(
        new_text_embedder(unique_new_texts), "new text"
    ) if unique_new_texts else np.empty((0, EMBEDDING_DIM), dtype=np.float32)
    if embedded.shape[0] != len(unique_new_texts):
        raise ValueError("new text embedder returned the wrong row count")
    new_by_text = dict(zip(unique_new_texts, embedded, strict=True))

    records: dict[str, list[Any]] = defaultdict(list)
    for source_index, base in enumerate(base_examples):
        target = np.asarray(base.target, dtype=np.float32).copy()
        if target.shape != (MAX_COLORS, 5):
            raise ValueError("target must have shape [9, 5]")
        target[:, 4] = 0.0
        target[base.count :] = 0.0
        embedding = (
            _normalized_embeddings(base.archived_embedding[None, :], "legacy")[0]
            if base.archived_embedding is not None
            else new_by_text[base.text]
        )
        lock_variants = _lock_variants(
            base.count,
            f"{base.source_record_id}\x1f{base.text}\x1f{base.count}\x1f{base.palette_hash}",
        )
        variant_weight = base.quality_weight / len(lock_variants)
        for lock_mode, locked_mask in lock_variants:
            seed = int(
                stable_uint64(
                    PREPARATION_VERSION,
                    base.source_group_id,
                    base.source_record_id,
                    base.text,
                    base.count,
                    lock_mode,
                )
                & 0xFFFF_FFFF
            )
            count_mask = np.zeros(MAX_COLORS, dtype=np.float32)
            count_mask[: base.count] = 1.0
            locked_colors = np.zeros((MAX_COLORS, 4), dtype=np.float32)
            locked = locked_mask > 0.5
            locked_colors[locked] = base.physical_colors[locked]
            example_hash = hashlib.sha256(
                "\x1f".join(
                    (
                        PREPARATION_VERSION,
                        base.source_group_id,
                        base.source_record_id,
                        base.text,
                        str(base.count),
                        lock_mode,
                        base.palette_hash,
                    )
                ).encode("utf-8")
            ).hexdigest()[:24]
            values = {
                "example_ids": f"pb-c1-{example_hash}",
                "source_indices": source_index,
                "texts": base.text,
                "embeddings": embedding,
                "counts": base.count,
                "seeds": seed,
                "count_masks": count_mask,
                "seed_noise": seed_noise_from_uint32(seed),
                "locked_masks": locked_mask,
                "locked_colors": locked_colors,
                "targets": target,
                "splits": base.split,
                "sources": base.source,
                "source_ids": base.source_id,
                "source_record_ids": base.source_record_id,
                "source_group_ids": base.source_group_id,
                "semantic_group_ids": base.semantic_group_id,
                "prompt_kinds": base.prompt_kind,
                "text_origins": base.text_origin,
                "palette_origins": base.palette_origin,
                "semantic_alignments": base.semantic_alignment,
                "licenses": base.license,
                "source_revisions": base.source_revision,
                "palette_hashes": base.palette_hash,
                "palette_hex_json": base.palette_hex_json,
                "native_counts": base.native_count,
                "derived_counts": base.derived_count,
                "holdout_eligible": base.holdout_eligible,
                "lock_modes": lock_mode,
                "quality_weights": variant_weight,
            }
            for name, value in values.items():
                records[name].append(value)

    string_names = {
        "example_ids", "texts", "sources", "source_ids", "source_record_ids",
        "source_group_ids", "semantic_group_ids", "prompt_kinds", "text_origins",
        "palette_origins", "semantic_alignments", "licenses", "source_revisions",
        "palette_hashes", "palette_hex_json", "lock_modes",
    }
    arrays: dict[str, np.ndarray] = {}
    for name, values in records.items():
        if name in string_names:
            arrays[name] = np.asarray(values, dtype=np.str_)
    arrays.update(
        {
            "source_indices": np.asarray(records["source_indices"], dtype=np.int32),
            "embeddings": np.asarray(records["embeddings"], dtype=np.float32),
            "counts": np.asarray(records["counts"], dtype=np.int64),
            "seeds": np.asarray(records["seeds"], dtype=np.uint32),
            "count_masks": np.asarray(records["count_masks"], dtype=np.float32),
            "seed_noise": np.asarray(records["seed_noise"], dtype=np.float32),
            "locked_masks": np.asarray(records["locked_masks"], dtype=np.float32),
            "locked_colors": np.asarray(records["locked_colors"], dtype=np.float32),
            "targets": np.asarray(records["targets"], dtype=np.float32),
            "splits": np.asarray(records["splits"], dtype=np.int8),
            "native_counts": np.asarray(records["native_counts"], dtype=np.int64),
            "derived_counts": np.asarray(records["derived_counts"], dtype=np.bool_),
            "holdout_eligible": np.asarray(records["holdout_eligible"], dtype=np.bool_),
            "quality_weights": np.asarray(records["quality_weights"], dtype=np.float32),
        }
    )
    return arrays


def _cap_legacy_sampling(arrays: dict[str, np.ndarray], cap: float) -> float:
    train = arrays["splits"] == SPLIT_IDS["train"]
    legacy = arrays["sources"] == "legacy_synthetic"
    legacy_weight = float(arrays["quality_weights"][train & legacy].sum(dtype=np.float64))
    other_weight = float(arrays["quality_weights"][train & ~legacy].sum(dtype=np.float64))
    if legacy_weight and not other_weight:
        raise ValueError("legacy synthetic data cannot be the only training source")
    if legacy_weight:
        fraction = legacy_weight / (legacy_weight + other_weight)
        if fraction > cap:
            maximum = (cap * other_weight) / ((1.0 - cap) * legacy_weight)
            arrays["quality_weights"][legacy] *= np.float32(maximum * (1.0 - 1e-6))
    total = float(arrays["quality_weights"][train].sum(dtype=np.float64))
    contribution = float(arrays["quality_weights"][train & legacy].sum(dtype=np.float64))
    return contribution / total if total else 0.0


def canonical_content_hash(arrays: Mapping[str, np.ndarray]) -> str:
    """Hash logical arrays independently of NPZ ZIP timestamps/compression."""

    digest = hashlib.sha256()
    digest.update(CONTENT_HASH_VERSION.encode("ascii") + b"\0")
    for name in sorted(key for key in arrays if key != "metadata_json"):
        value = np.ascontiguousarray(arrays[name])
        digest.update(name.encode("utf-8") + b"\0")
        digest.update(value.dtype.str.encode("ascii") + b"\0")
        digest.update(json.dumps(value.shape, separators=(",", ":")).encode("ascii") + b"\0")
        digest.update(value.tobytes())
    return digest.hexdigest()


def _canonical_json_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _source_report(arrays: Mapping[str, np.ndarray]) -> dict[str, Any]:
    train = arrays["splits"] == SPLIT_IDS["train"]
    total_train_weight = float(arrays["quality_weights"][train].sum(dtype=np.float64))
    report: dict[str, Any] = {}
    for source in sorted(set(map(str, arrays["sources"].tolist()))):
        mask = arrays["sources"] == source
        train_weight = float(arrays["quality_weights"][mask & train].sum(dtype=np.float64))
        report[source] = {
            "uniqueGroups": len(set(map(str, arrays["source_group_ids"][mask].tolist()))),
            "originalRecords": len(set(map(str, arrays["source_record_ids"][mask].tolist()))),
            "expandedRecords": int(mask.sum()),
            "effectiveSampledContribution": (
                train_weight / total_train_weight if total_train_weight else 0.0
            ),
        }
    return report


def _count_histogram(values: np.ndarray, mask: np.ndarray | None = None) -> dict[str, int]:
    selected = values if mask is None else values[mask]
    return {str(count): int(np.sum(selected == count)) for count in range(2, 10)}


def build_report(arrays: Mapping[str, np.ndarray], metadata: Mapping[str, Any]) -> dict[str, Any]:
    split_report: dict[str, Any] = {}
    for archive_name, display_name in (("train", "train"), ("val", "validation"), ("test", "test")):
        mask = arrays["splits"] == SPLIT_IDS[archive_name]
        split_report[display_name] = {
            "records": int(mask.sum()),
            "uniqueGroups": len(set(map(str, arrays["source_group_ids"][mask].tolist()))),
            "nativeRecords": int(np.sum(mask & ~arrays["derived_counts"])),
            "derivedRecords": int(np.sum(mask & arrays["derived_counts"])),
            "requestedCounts": _count_histogram(arrays["counts"], mask),
        }
    return {
        "schemaVersion": 1,
        "datasetVersion": metadata["datasetVersion"],
        "contentHash": metadata["contentHash"],
        "sourceHash": metadata["sourceHash"],
        "configHash": metadata["configHash"],
        "encoderArtifactSha256": metadata["encoderArtifactSha256"],
        "records": int(arrays["counts"].shape[0]),
        "uniqueGroups": len(set(map(str, arrays["source_group_ids"].tolist()))),
        "sources": _source_report(arrays),
        "splits": split_report,
        "nativeCounts": _count_histogram(arrays["native_counts"]),
        "requestedCounts": _count_histogram(arrays["counts"]),
        "derivedRecords": int(np.sum(arrays["derived_counts"])),
        "realHoldoutRecords": int(
            np.sum(arrays["holdout_eligible"] & (arrays["splits"] != SPLIT_IDS["train"]))
        ),
    }


def assemble_candidate_archive(
    *,
    corpus: CandidateCorpus,
    anchors: Mapping[str, Any],
    legacy_source: Mapping[str, np.ndarray],
    new_text_embedder: NewTextEmbedder,
    source_hashes: Mapping[str, str],
    config: PreparationConfig | None = None,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    """Assemble and validate Candidate 1 without doing file or model I/O."""

    config = config or PreparationConfig()
    config.validate()
    anchor_hash = source_hashes.get("directAnchors")
    if not anchor_hash or len(anchor_hash) != 64:
        raise ValueError("source_hashes must include directAnchors SHA-256")
    real = _real_base_examples(corpus, config)
    anchors_base = _anchor_base_examples(anchors, config, anchor_hash)
    new_examples = _limit_new_texts(real + anchors_base, config)
    legacy = _legacy_base_examples(legacy_source, corpus, config)
    if not new_examples:
        raise ValueError("Candidate 1 requires at least one new-text example")
    arrays = _expand_examples(new_examples + legacy, new_text_embedder)
    legacy_fraction = _cap_legacy_sampling(arrays, config.legacy_sampling_cap)
    if legacy_fraction > config.legacy_sampling_cap + 1e-7:
        raise ValueError("legacy effective training contribution exceeds its cap")
    if np.any(arrays["targets"][..., 4] != 0.0):
        raise ValueError("Candidate 1 importance targets must all be zero")
    if np.any(arrays["locked_masks"].sum(axis=1) >= arrays["counts"]):
        raise ValueError("a fully locked palette entered Candidate 1")
    validate_prepared_archive(arrays)

    source_hash = _canonical_json_hash(dict(sorted(source_hashes.items())))
    config_payload = {
        "preparationVersion": PREPARATION_VERSION,
        "lockVersion": LOCK_VERSION,
        "splitSeed": corpus.split_config.seed,
        "splitAlgorithm": corpus.split_config.algorithm,
        "evaluationConfigHash": corpus.split_config.evaluation_config_hash,
        "config": asdict(config),
    }
    metadata: dict[str, Any] = {
        "schemaVersion": 1,
        "kind": "legal_curated_candidate_with_bounded_synthetic_auxiliary",
        "datasetVersion": config.dataset_version,
        "productionReady": False,
        "preparationVersion": PREPARATION_VERSION,
        "contentHashAlgorithm": CONTENT_HASH_VERSION,
        "sourceHash": source_hash,
        "sourceHashes": dict(sorted(source_hashes.items())),
        "configHash": _canonical_json_hash(config_payload),
        "evaluationConfigHash": corpus.split_config.evaluation_config_hash,
        "splitSeed": corpus.split_config.seed,
        "splitAlgorithm": corpus.split_config.algorithm,
        "encoderModel": E5_MODEL_ID,
        "encoderRevision": E5_REVISION,
        "browserEncoderModel": BROWSER_E5_MODEL_ID,
        "browserEncoderRevision": BROWSER_E5_REVISION,
        "encoderArtifactSha256": BROWSER_E5_SHA256,
        "embeddingDimension": EMBEDDING_DIM,
        "maxColors": MAX_COLORS,
        "importanceTargetWeight": 0.0,
        "legacySamplingCap": config.legacy_sampling_cap,
        "lockAugmentation": LOCK_VERSION,
        "realPaletteExpansion": False,
        "trainingOnlyDirectAnchors": True,
    }
    metadata["contentHash"] = canonical_content_hash(arrays)
    report = build_report(arrays, metadata)
    metadata["effectiveSamplingContribution"] = {
        source: details["effectiveSampledContribution"]
        for source, details in report["sources"].items()
    }
    arrays["metadata_json"] = np.asarray(
        json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )
    return arrays, report


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _input_hashes(
    *,
    manifest_path: Path,
    raw_dir: Path,
    evaluation_freeze_path: Path,
    anchors_path: Path,
    legacy_path: Path,
) -> dict[str, str]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    hashes = {
        "sourceManifest": sha256_file(manifest_path),
        "evaluationFreeze": sha256_file(evaluation_freeze_path),
        "directAnchors": sha256_file(anchors_path),
        "legacySyntheticArchive": sha256_file(legacy_path),
    }
    raw_hashes = {
        str(artifact["id"]): sha256_file(raw_dir / str(artifact["path"]))
        for artifact in manifest["artifacts"]
    }
    hashes["rawArtifacts"] = _canonical_json_hash(raw_hashes)
    return hashes


def _atomic_save_npz(path: Path, arrays: Mapping[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        with temporary.open("wb") as output:
            np.savez_compressed(output, **arrays)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def prepare_candidate_data(
    *,
    output_path: Path,
    report_path: Path,
    manifest_path: Path,
    raw_dir: Path,
    evaluation_freeze_path: Path,
    anchors_path: Path,
    legacy_path: Path,
    device: str,
    cache_dir: Path,
    config: PreparationConfig,
) -> dict[str, Any]:
    """Load verified inputs, embed unique new text, and atomically write artifacts."""

    corpus = build_candidate_records(
        manifest_path=manifest_path,
        raw_dir=raw_dir,
        evaluation_freeze_path=evaluation_freeze_path,
    )
    anchors = json.loads(anchors_path.read_text(encoding="utf-8"))
    with np.load(legacy_path, allow_pickle=False) as archive:
        legacy = {name: np.asarray(archive[name]) for name in archive.files}
    hashes = _input_hashes(
        manifest_path=manifest_path,
        raw_dir=raw_dir,
        evaluation_freeze_path=evaluation_freeze_path,
        anchors_path=anchors_path,
        legacy_path=legacy_path,
    )
    encoder = load_encoder(device=device, cache_dir=cache_dir, local_files_only=True)

    def embedder(texts: Sequence[str]) -> np.ndarray:
        return embed_texts(texts, encoder=encoder, batch_size=config.embedding_batch_size)

    arrays, report = assemble_candidate_archive(
        corpus=corpus,
        anchors=anchors,
        legacy_source=legacy,
        new_text_embedder=embedder,
        source_hashes=hashes,
        config=config,
    )
    _atomic_save_npz(output_path, arrays)
    report = {
        **report,
        "archiveBytes": output_path.stat().st_size,
        "archiveSha256": sha256_file(output_path),
    }
    _atomic_write_json(report_path, report)
    return {
        "output": str(output_path),
        "report": str(report_path),
        "records": report["records"],
        "contentHash": report["contentHash"],
        "splits": {name: value["records"] for name, value in report["splits"].items()},
    }


def _parser() -> argparse.ArgumentParser:
    package_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(DEFAULT_OUTPUT))
    parser.add_argument("--report", type=Path, default=Path(DEFAULT_REPORT))
    parser.add_argument("--dataset-version", default=DATASET_VERSION)
    parser.add_argument("--manifest", type=Path, default=package_dir / "source_manifest.v1.json")
    parser.add_argument("--raw-dir", type=Path, default=package_dir / "data" / "raw")
    parser.add_argument(
        "--evaluation-freeze",
        type=Path,
        default=package_dir / "reports" / "evaluation-freeze.v1.json",
    )
    parser.add_argument("--anchors", type=Path, default=package_dir / "direct_color_anchors.v1.json")
    parser.add_argument("--legacy", type=Path, default=package_dir.parent / "dataset_embeddings.npz")
    parser.add_argument(
        "--cache-dir", type=Path, default=package_dir.parent / ".cache" / "hub"
    )
    parser.add_argument("--device", default="cuda", help="Pinned E5 device (default: cuda).")
    parser.add_argument("--embedding-batch-size", type=int, default=128)
    parser.add_argument("--legacy-max-rows", type=int, default=2500)
    parser.add_argument("--direct-weight-multiplier", type=float, default=1.0)
    parser.add_argument("--smoke", action="store_true", help="Limit source groups and unique texts.")
    parser.add_argument("--smoke-groups", type=int, default=12)
    parser.add_argument("--smoke-texts", type=int, default=128)
    parser.add_argument("--smoke-legacy-groups", type=int, default=4)
    return parser


def main() -> None:
    args = _parser().parse_args()
    config = PreparationConfig(
        dataset_version=args.dataset_version,
        embedding_batch_size=args.embedding_batch_size,
        legacy_max_rows=args.legacy_max_rows,
        direct_family_weight=0.60 * args.direct_weight_multiplier,
        direct_composition_weight=0.70 * args.direct_weight_multiplier,
        smoke=args.smoke,
        smoke_max_real_groups=args.smoke_groups,
        smoke_max_new_texts=args.smoke_texts,
        smoke_max_legacy_groups=args.smoke_legacy_groups,
    )
    result = prepare_candidate_data(
        output_path=args.output,
        report_path=args.report,
        manifest_path=args.manifest,
        raw_dir=args.raw_dir,
        evaluation_freeze_path=args.evaluation_freeze,
        anchors_path=args.anchors,
        legacy_path=args.legacy,
        device=args.device,
        cache_dir=args.cache_dir,
        config=config,
    )
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
