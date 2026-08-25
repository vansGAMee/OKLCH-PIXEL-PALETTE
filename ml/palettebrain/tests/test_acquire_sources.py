from __future__ import annotations

import hashlib
import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ml.palettebrain.acquire_sources import (
    AcquisitionError,
    BudgetError,
    ProvenanceError,
    acquire_artifacts,
    load_manifest,
    validate_disk_budget,
    verify_acquired_provenance,
    verify_wada_dedup,
)


PACKAGE_DIR = Path(__file__).resolve().parents[1]


class FakeResponse(io.BytesIO):
    def __init__(self, body: bytes, *, etag: str | None = None) -> None:
        super().__init__(body)
        self.headers = {"ETag": etag} if etag is not None else {}

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


class ManifestTests(unittest.TestCase):
    def test_tracked_manifest_declares_the_verified_bounded_snapshot(self) -> None:
        manifest = load_manifest(PACKAGE_DIR / "source_manifest.v1.json")

        self.assertEqual(manifest["schema"], "palettebrain-source-manifest/v1")
        self.assertEqual(len(manifest["artifacts"]), 12)
        self.assertEqual(sum(item["bytes"] for item in manifest["artifacts"]), 300_346)
        self.assertEqual(
            {source["license"]["spdx"] for source in manifest["sources"]},
            {"MIT", "CC-BY-4.0", "CC0-1.0"},
        )
        self.assertEqual(
            manifest["deduplication"]["verified_exact_wada_mirrors"], 348
        )

    def test_disk_budget_covers_the_snapshot_and_never_exceeds_ten_gib(self) -> None:
        manifest = load_manifest(PACKAGE_DIR / "source_manifest.v1.json")
        expected_bytes = sum(item["bytes"] for item in manifest["artifacts"])
        maximum_bytes = manifest["acquisition_policy"]["maximum_disk_budget_bytes"]

        with TemporaryDirectory() as temporary_directory:
            raw_dir = Path(temporary_directory)
            with self.assertRaises(BudgetError):
                validate_disk_budget(manifest, raw_dir, expected_bytes - 1)
            self.assertEqual(
                validate_disk_budget(manifest, raw_dir, expected_bytes), expected_bytes
            )
            with self.assertRaises(BudgetError):
                validate_disk_budget(manifest, raw_dir, maximum_bytes + 1)


class AcquisitionTests(unittest.TestCase):
    def test_verified_download_is_atomically_published(self) -> None:
        body = b'[{"name":"safe"}]\n'
        manifest = {
            "acquisition_policy": {"maximum_disk_budget_bytes": 1024},
            "artifacts": [
                {
                    "id": "fixture",
                    "path": "fixture/data.json",
                    "url": "https://example.test/data.json",
                    "bytes": len(body),
                    "sha256": hashlib.sha256(body).hexdigest(),
                    "etag": "snapshot-etag",
                }
            ],
        }

        with TemporaryDirectory() as temporary_directory:
            raw_dir = Path(temporary_directory)
            summary = acquire_artifacts(
                manifest,
                raw_dir,
                budget_bytes=1024,
                opener=lambda _url: FakeResponse(body, etag='"snapshot-etag"'),
            )

            self.assertEqual((raw_dir / "fixture/data.json").read_bytes(), body)
            self.assertEqual(summary.downloaded, 1)
            self.assertEqual(summary.reused, 0)
            self.assertEqual(list(raw_dir.rglob("*.tmp")), [])

    def test_hash_failure_preserves_existing_destination(self) -> None:
        expected_body = b"expected"
        corrupt_body = b"corrupt!"
        manifest = {
            "acquisition_policy": {"maximum_disk_budget_bytes": 1024},
            "artifacts": [
                {
                    "id": "fixture",
                    "path": "fixture/data.json",
                    "url": "https://example.test/data.json",
                    "bytes": len(expected_body),
                    "sha256": hashlib.sha256(expected_body).hexdigest(),
                }
            ],
        }

        with TemporaryDirectory() as temporary_directory:
            raw_dir = Path(temporary_directory)
            destination = raw_dir / "fixture/data.json"
            destination.parent.mkdir(parents=True)
            destination.write_bytes(b"existing")

            with self.assertRaises(AcquisitionError):
                acquire_artifacts(
                    manifest,
                    raw_dir,
                    budget_bytes=1024,
                    opener=lambda _url: FakeResponse(corrupt_body),
                )

            self.assertEqual(destination.read_bytes(), b"existing")
            self.assertEqual(list(raw_dir.rglob("*.tmp")), [])


class ProvenanceTests(unittest.TestCase):
    def test_wada_mirrors_must_match_native_hex_order(self) -> None:
        wada_colors = [
            {"hex": "#aa0000", "combinations": [1, 2]},
            {"hex": "#00bb00", "combinations": [1]},
            {"hex": "#0000cc", "combinations": [2]},
        ]
        rows = [
            {
                "slug": "wada-001-red-green",
                "hex_1": "#aa0000",
                "hex_2": "#00bb00",
                "hex_3": "",
                "hex_4": "",
            },
            {
                "slug": "wada-002-red-blue",
                "hex_1": "#aa0000",
                "hex_2": "#0000cc",
                "hex_3": "",
                "hex_4": "",
            },
            {"slug": "editorial", "hex_1": "#ffffff"},
        ]

        self.assertEqual(
            verify_wada_dedup(wada_colors, rows, expected_mirrors=2), 2
        )
        rows[1]["hex_2"] = "#ffffff"
        with self.assertRaises(ProvenanceError):
            verify_wada_dedup(wada_colors, rows, expected_mirrors=2)

    def test_acquired_snapshot_reports_only_independent_palettes(self) -> None:
        manifest = {
            "sources": [
                {
                    "id": "wada",
                    "provenance": {
                        "expected_unique_colors": 3,
                        "expected_palettes": 2,
                    },
                },
                {
                    "id": "colorcombinations",
                    "provenance": {
                        "wada_mirror_slug_regex": r"^wada-(\d{3})-",
                        "expected_rows": 3,
                        "expected_wada_mirrors": 2,
                        "expected_editorial_palettes": 1,
                    },
                },
                {
                    "id": "rang",
                    "provenance": {
                        "expected_palettes": 1,
                        "native_color_counts": [2],
                    },
                },
            ],
            "artifacts": [
                {"id": "wada-colors", "source": "wada", "path": "wada.json"},
                {
                    "id": "colorcombinations-palettes",
                    "source": "colorcombinations",
                    "path": "palettes.csv",
                },
                {"id": "rang-one", "source": "rang", "path": "rang.json"},
            ],
        }
        wada = [
            {"hex": "#aa0000", "combinations": [1, 2]},
            {"hex": "#00bb00", "combinations": [1]},
            {"hex": "#0000cc", "combinations": [2]},
        ]
        csv_text = (
            "slug,hex_1,hex_2,hex_3,hex_4\n"
            "wada-001-a-b,#aa0000,#00bb00,,\n"
            "wada-002-a-c,#aa0000,#0000cc,,\n"
            "editorial,#ffffff,#000000,,\n"
        )
        rang = {
            "name": "Test",
            "colors": ["#111111", "#eeeeee"],
            "notes": ["dark", "light"],
            "order": [2, 1],
        }

        with TemporaryDirectory() as temporary_directory:
            raw_dir = Path(temporary_directory)
            (raw_dir / "wada.json").write_text(json.dumps(wada), encoding="utf-8")
            (raw_dir / "palettes.csv").write_text(csv_text, encoding="utf-8")
            (raw_dir / "rang.json").write_text(json.dumps(rang), encoding="utf-8")

            summary = verify_acquired_provenance(manifest, raw_dir)

        self.assertEqual(summary.wada_palettes, 2)
        self.assertEqual(summary.wada_mirrors, 2)
        self.assertEqual(summary.editorial_palettes, 1)
        self.assertEqual(summary.rang_palettes, 1)
        self.assertEqual(summary.independent_palettes, 4)


if __name__ == "__main__":
    unittest.main()
