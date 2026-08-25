from __future__ import annotations

import unittest
from pathlib import Path

from ml.palettebrain.candidate_records import (
    build_candidate_records,
    canonical_palette_hash,
    source_group_split,
)


PACKAGE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = PACKAGE_DIR / "data" / "raw"


class FrozenIdentityTests(unittest.TestCase):
    def test_palette_hash_and_source_group_split_are_frozen(self) -> None:
        self.assertEqual(
            canonical_palette_hash(["#D96629", "#0093A5"]),
            "ab8a89a424f41a3a3fd06b52b0b394c1a03bd56ab67bc7d4a7d69ef20cc3de13",
        )
        self.assertNotEqual(
            canonical_palette_hash(["#D96629", "#0093A5"]),
            canonical_palette_hash(["#0093A5", "#D96629"]),
        )

        split_ranges = {
            "train": (0, 79),
            "validation": (80, 89),
            "test": (90, 99),
        }
        self.assertEqual(
            source_group_split("wada:plate-001", 20260825, split_ranges),
            ("train", 43),
        )
        self.assertEqual(
            source_group_split("wada:plate-010", 20260825, split_ranges),
            ("validation", 80),
        )
        self.assertEqual(
            source_group_split("wada:plate-013", 20260825, split_ranges),
            ("test", 90),
        )


@unittest.skipUnless(
    (RAW_DIR / "wada/colors.json").is_file(),
    "run acquire_sources.py to materialize the verified raw snapshot",
)
class VerifiedSnapshotTests(unittest.TestCase):
    def test_snapshot_builds_388_groups_and_736_original_semantic_records(self) -> None:
        corpus = build_candidate_records(
            manifest_path=PACKAGE_DIR / "source_manifest.v1.json",
            raw_dir=RAW_DIR,
            evaluation_freeze_path=PACKAGE_DIR / "reports/evaluation-freeze.v1.json",
        )

        self.assertEqual(len(corpus.palette_groups), 388)
        self.assertEqual(len(corpus.semantic_records), 736)
        self.assertEqual(
            corpus.summary()["splits"],
            {"train": 306, "validation": 42, "test": 40},
        )
        self.assertEqual(
            len(
                [
                    record
                    for record in corpus.semantic_records
                    if record.get("is_wada_mirror") is True
                ]
            ),
            348,
        )

        groups = {group["source_group_id"]: group for group in corpus.palette_groups}
        wada = groups["wada:plate-001"]
        self.assertEqual(wada["colors"], ["#d96629", "#0093a5"])
        mirror = next(
            record
            for record in corpus.semantic_records
            if record["source"] == "colorcombinations"
            and record["source_group_id"] == "wada:plate-001"
        )
        self.assertEqual(mirror["canonical_palette_hash"], wada["canonical_palette_hash"])
        self.assertEqual(mirror["split"], wada["split"])
        self.assertEqual(mirror["semantic_fields"]["title"], "English Red & Cerulian Blue")
        self.assertEqual(mirror["text_origin"], "metadata_derived")

        required = {
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
            "canonical_palette_hash",
            "native_count",
            "requested_count",
            "derived_count",
            "quality_weight",
            "split",
            "split_bucket",
        }
        self.assertTrue(
            all(required <= record.keys() for record in corpus.semantic_records)
        )
        self.assertTrue(
            all(
                "image" not in record and "card_image" not in record
                for record in corpus.semantic_records
            )
        )
        self.assertTrue(
            all(
                record["requested_count"] == record["native_count"]
                and record["derived_count"] is False
                and "text" not in record
                for record in corpus.semantic_records
            )
        )

        split_assignments: dict[str, set[tuple[str, int]]] = {}
        for group in corpus.palette_groups:
            split_assignments.setdefault(group["source_group_id"], set()).add(
                (group["split"], group["split_bucket"])
            )
        for record in corpus.semantic_records:
            split_assignments.setdefault(record["source_group_id"], set()).add(
                (record["split"], record["split_bucket"])
            )
        self.assertTrue(all(len(assignments) == 1 for assignments in split_assignments.values()))

        group_source_counts = {
            source: sum(group["source"] == source for group in corpus.palette_groups)
            for source in ("wada", "colorcombinations", "rang")
        }
        self.assertEqual(
            group_source_counts,
            {"wada": 348, "colorcombinations": 30, "rang": 10},
        )
        self.assertTrue(
            all(
                record["palette_origin"] == "human_curated_extracted"
                and set(record["semantic_fields"])
                == {"name", "notes", "native_order"}
                for record in corpus.semantic_records
                if record["source"] == "rang"
            )
        )


if __name__ == "__main__":
    unittest.main()
