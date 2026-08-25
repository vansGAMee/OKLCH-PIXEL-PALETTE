from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from ml.palettebrain.candidate_records import CandidateCorpus, SplitConfig, source_group_split
from ml.palettebrain.dataset import EMBEDDING_DIM, SPLIT_IDS, validate_prepared_archive
from ml.palettebrain.prepare_candidate_data import (
    PreparationConfig,
    _atomic_save_npz,
    _atomic_write_json,
    assemble_candidate_archive,
    canonical_content_hash,
    honest_prompt_variants,
)


SPLIT_RANGES = {"train": (0, 79), "validation": (80, 89), "test": (90, 99)}
SPLIT_SEED = 20260825


def _group_id(wanted_split: str) -> tuple[str, int]:
    for index in range(10_000):
        group_id = f"fixture:{wanted_split}:{index}"
        split, bucket = source_group_split(group_id, SPLIT_SEED, SPLIT_RANGES)
        if split == wanted_split:
            return group_id, bucket
    raise AssertionError("could not find a fixture group")


def _record(
    *,
    source: str,
    record_id: str,
    split: str,
    colors: list[str],
    semantic_fields: dict[str, object],
    palette_origin: str = "human_curated",
    semantic_alignment: str = "metadata_derived",
) -> tuple[dict[str, object], dict[str, object]]:
    group_id, bucket = _group_id(split)
    base: dict[str, object] = {
        "source": source,
        "source_id": record_id,
        "source_group_id": group_id,
        "semantic_group_id": None,
        "text_origin": "human" if source == "rang" else "metadata_derived",
        "palette_origin": palette_origin,
        "semantic_alignment": semantic_alignment,
        "license": "MIT",
        "license_status": "verified",
        "source_revision": "fixture-revision",
        "colors": colors,
        "native_count": len(colors),
        "requested_count": len(colors),
        "derived_count": False,
        "quality_weight": 1.0,
        "split": split,
        "split_bucket": bucket,
    }
    group = {**base, "record_kind": "palette_group"}
    semantic = {
        **base,
        "record_kind": "semantic_record",
        "record_id": record_id,
        "semantic_fields": semantic_fields,
    }
    return group, semantic


def _tiny_corpus() -> CandidateCorpus:
    train_group, train = _record(
        source="wada",
        record_id="wada:fixture",
        split="train",
        colors=["#220000", "#cc2233", "#fff1dc"],
        semantic_fields={"color_names": ["Dark Red", "Scarlet", "Cream"]},
        semantic_alignment="weak",
    )
    # A second audited metadata record for the same original palette and group.
    metadata = {
        **train,
        "source": "colorcombinations",
        "source_id": "metadata-fixture",
        "record_id": "colorcombinations:fixture",
        "semantic_alignment": "metadata_derived",
        "semantic_fields": {
            "title": "Crimson and Cream",
            "summary": "A restrained crimson palette.",
            "moods": ["solemn", "warm"],
            "era": "edo",
            "color_names": ["Dark Red", "Scarlet", "Cream"],
            "scene": "invented hospital scene must be ignored",
        },
    }
    validation_group, validation = _record(
        source="rang",
        record_id="rang:fixture",
        split="validation",
        colors=["#101020", "#334488", "#77aacc", "#f0e8d0"],
        semantic_fields={"name": "Fixture Rang", "notes": ["cobalt, the field"]},
        palette_origin="human_curated_extracted",
        semantic_alignment="direct",
    )
    test_group, test = _record(
        source="colorcombinations",
        record_id="editorial:fixture",
        split="test",
        colors=["#112233", "#ddeeff"],
        semantic_fields={"title": "Ink and Ice"},
        semantic_alignment="direct",
    )
    return CandidateCorpus(
        palette_groups=(train_group, validation_group, test_group),
        semantic_records=(train, metadata, validation, test),
        split_config=SplitConfig(
            seed=SPLIT_SEED,
            algorithm=(
                "sha256(source-group-sha256-bucket-v1, splitSeed, "
                "source_group_id) modulo 100"
            ),
            ranges=SPLIT_RANGES,
            evaluation_config_hash="e" * 64,
        ),
    )


def _tiny_anchors() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "license": "project-owned",
        "families": [
            {
                "id": "red",
                "anchorHex": "#e31b35",
                "terms": [["red", "en", "base"], ["красный", "ru", "base"]],
            }
        ],
        "explicitPalettes": [
            {
                "id": "red-blue",
                "texts": [["red and blue", "en"]],
                "colors": [
                    "#110d18", "#541124", "#9d1731", "#f04a54", "#173b8f",
                    "#2457d6", "#82a7ff", "#bfc8eb", "#eee8dc",
                ],
            }
        ],
    }


def _tiny_legacy() -> dict[str, np.ndarray]:
    rows = 4
    embeddings = np.zeros((rows, EMBEDDING_DIM), dtype=np.float32)
    for index in range(rows):
        embeddings[index, 100 + index] = 1.0
    return {
        "embeddings": embeddings,
        "texts": np.asarray(["red", "old forest", "old ocean", "old dusk"]),
        "hues": np.asarray([0.0, 120.0, 220.0, 300.0], dtype=np.float32),
        "lightnesses": np.full(rows, 0.55, dtype=np.float32),
        "chromas": np.full(rows, 0.65, dtype=np.float32),
        "harmonies": np.asarray([0, 1, 2, 0], dtype=np.int64),
        "groups": np.asarray(["old-a", "old-a", "old-b", "old-b"]),
    }


class FakeEmbedder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, texts: object) -> np.ndarray:
        normalized = tuple(map(str, texts))  # type: ignore[arg-type]
        self.calls.append(normalized)
        result = np.zeros((len(normalized), EMBEDDING_DIM), dtype=np.float32)
        for row, text in enumerate(normalized):
            column = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:2], "big")
            result[row, column % EMBEDDING_DIM] = 1.0
        return result


class CandidatePreparationTests(unittest.TestCase):
    def _assemble(
        self, config: PreparationConfig | None = None
    ) -> tuple[dict[str, np.ndarray], dict[str, object], FakeEmbedder]:
        embedder = FakeEmbedder()
        arrays, report = assemble_candidate_archive(
            corpus=_tiny_corpus(),
            anchors=_tiny_anchors(),
            legacy_source=_tiny_legacy(),
            new_text_embedder=embedder,
            source_hashes={
                "directAnchors": "a" * 64,
                "sourceManifest": "b" * 64,
                "legacySyntheticArchive": "c" * 64,
            },
            config=config or PreparationConfig(legacy_max_rows=10),
        )
        return arrays, report, embedder

    def test_prompts_use_only_audited_fields(self) -> None:
        record = _tiny_corpus().semantic_records[1]
        variants = honest_prompt_variants(record)
        texts = {variant.text for variant in variants}
        self.assertIn("Crimson and Cream", texts)
        self.assertIn("A restrained crimson palette.", texts)
        self.assertIn("solemn", texts)
        self.assertIn("edo", texts)
        self.assertNotIn("invented hospital scene must be ignored", texts)

    def test_archive_contract_splits_counts_locks_and_provenance(self) -> None:
        arrays, report, embedder = self._assemble()
        validation = validate_prepared_archive(arrays)
        self.assertGreater(validation["train"], 0)
        self.assertGreater(validation["val"], 0)
        self.assertGreater(validation["test"], 0)

        required = {
            "sources", "source_ids", "source_record_ids", "source_group_ids",
            "texts", "prompt_kinds", "text_origins", "palette_origins",
            "semantic_alignments", "native_counts", "derived_counts",
            "quality_weights", "holdout_eligible", "metadata_json",
        }
        self.assertTrue(required <= arrays.keys())
        self.assertEqual(arrays["derived_counts"].dtype, np.dtype(np.bool_))
        self.assertTrue(np.all(arrays["targets"][..., 4] == 0.0))
        self.assertTrue(np.all(arrays["locked_masks"].sum(axis=1) < arrays["counts"]))
        self.assertEqual(set(arrays["lock_modes"].tolist()), {"none", "one", "multi"})

        for group_id in set(arrays["source_group_ids"].tolist()):
            mask = arrays["source_group_ids"] == group_id
            self.assertEqual(len(set(arrays["splits"][mask].tolist())), 1)
        anchors = arrays["sources"] == "direct_anchors"
        self.assertTrue(np.all(arrays["splits"][anchors] == SPLIT_IDS["train"]))
        self.assertFalse(np.any(arrays["holdout_eligible"][anchors]))
        self.assertEqual(set(arrays["counts"][anchors].tolist()), set(range(2, 10)))
        legacy = arrays["sources"] == "legacy_synthetic"
        self.assertTrue(np.all(arrays["splits"][legacy] == SPLIT_IDS["train"]))
        self.assertFalse(np.any(arrays["holdout_eligible"][legacy]))

        real = np.isin(arrays["sources"], ["wada", "colorcombinations", "rang"])
        self.assertTrue(np.all(arrays["counts"][real] <= arrays["native_counts"][real]))
        self.assertTrue(np.array_equal(
            arrays["derived_counts"][real],
            arrays["counts"][real] < arrays["native_counts"][real],
        ))
        self.assertFalse(any("hospital" in text for text in arrays["texts"].tolist()))

        # New texts are embedded once. Legacy rows retain their archived vectors,
        # even when a legacy string ("red") is also a new direct-anchor string.
        self.assertEqual(len(embedder.calls), 1)
        self.assertEqual(len(embedder.calls[0]), len(set(embedder.calls[0])))
        legacy_row = (arrays["sources"] == "legacy_synthetic") & (arrays["source_ids"] == "row:0")
        self.assertTrue(np.all(arrays["embeddings"][legacy_row, 100] == 1.0))

        legacy_fraction = report["sources"]["legacy_synthetic"][  # type: ignore[index]
            "effectiveSampledContribution"
        ]
        self.assertLessEqual(float(legacy_fraction), 0.15)

    def test_each_legacy_row_has_one_count_and_target_bound_locks(self) -> None:
        arrays, _, _ = self._assemble()
        legacy = arrays["sources"] == "legacy_synthetic"
        for source_id in set(arrays["source_ids"][legacy].tolist()):
            mask = legacy & (arrays["source_ids"] == source_id)
            self.assertEqual(len(set(arrays["counts"][mask].tolist())), 1)

        locked = arrays["locked_masks"] > 0.5
        self.assertTrue(np.all(arrays["locked_colors"][~locked] == 0.0))
        # Bound lock inputs have a physical lightness, unlike arbitrary filler.
        self.assertTrue(np.all(arrays["locked_colors"][locked, 0] > 0.0))

    def test_smoke_limits_real_groups_and_unique_new_texts(self) -> None:
        config = PreparationConfig(
            legacy_max_rows=10,
            smoke=True,
            smoke_max_real_groups=2,
            smoke_max_new_texts=4,
            smoke_max_legacy_groups=1,
        )
        arrays, _, embedder = self._assemble(config)
        real = np.isin(arrays["sources"], ["wada", "colorcombinations", "rang"])
        self.assertLessEqual(len(set(arrays["source_group_ids"][real].tolist())), 2)
        self.assertEqual(len(embedder.calls), 1)
        self.assertLessEqual(len(embedder.calls[0]), 4)

    def test_content_hash_and_atomic_artifacts_are_deterministic(self) -> None:
        arrays, report, _ = self._assemble()
        metadata = json.loads(str(arrays["metadata_json"].item()))
        self.assertEqual(metadata["contentHash"], canonical_content_hash(arrays))
        self.assertEqual(report["contentHash"], metadata["contentHash"])

        with TemporaryDirectory() as directory:
            archive_path = Path(directory) / "candidate.npz"
            report_path = Path(directory) / "candidate.json"
            _atomic_save_npz(archive_path, arrays)
            _atomic_write_json(report_path, report)
            with np.load(archive_path, allow_pickle=False) as loaded:
                validate_prepared_archive({name: loaded[name] for name in loaded.files})
            loaded_report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded_report["contentHash"], metadata["contentHash"])


if __name__ == "__main__":
    unittest.main()
