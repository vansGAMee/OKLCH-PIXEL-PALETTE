"""Bounded, pinned acquisition for PaletteBrain's legal Candidate 1 sources."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse
from urllib.request import Request, urlopen


SCHEMA = "palettebrain-source-manifest/v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
HARD_MAX_DISK_BUDGET_BYTES = 10 * 1024**3


class ManifestError(ValueError):
    """Raised when the tracked source manifest is internally inconsistent."""


class BudgetError(ValueError):
    """Raised before acquisition would exceed its explicit disk allowance."""


class AcquisitionError(RuntimeError):
    """Raised when a remote artifact does not match its pinned snapshot."""


class ProvenanceError(ValueError):
    """Raised when pinned files violate the verified source relationship."""


@dataclass(frozen=True)
class AcquisitionSummary:
    downloaded: int
    reused: int
    verified_bytes: int


@dataclass(frozen=True)
class ProvenanceSummary:
    wada_palettes: int
    wada_mirrors: int
    editorial_palettes: int
    rang_palettes: int

    @property
    def independent_palettes(self) -> int:
        return self.wada_palettes + self.editorial_palettes + self.rang_palettes


def load_manifest(path: Path) -> dict[str, Any]:
    """Load and validate a source manifest before any network or disk mutation."""

    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"cannot load source manifest: {exc}") from exc
    _validate_manifest(manifest)
    return manifest


def _validate_manifest(manifest: object) -> None:
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        raise ManifestError(f"manifest schema must be {SCHEMA}")

    policy = manifest.get("acquisition_policy")
    sources = manifest.get("sources")
    artifacts = manifest.get("artifacts")
    if not isinstance(policy, dict) or not isinstance(sources, list) or not sources:
        raise ManifestError("manifest must declare acquisition policy and sources")
    if not isinstance(artifacts, list) or not artifacts:
        raise ManifestError("manifest must declare at least one artifact")

    source_ids: set[str] = set()
    for source in sources:
        if not isinstance(source, dict) or not isinstance(source.get("id"), str):
            raise ManifestError("every source must have a string id")
        source_id = source["id"]
        if source_id in source_ids:
            raise ManifestError(f"duplicate source id: {source_id}")
        source_ids.add(source_id)
        license_data = source.get("license")
        if not isinstance(license_data, dict):
            raise ManifestError(f"source {source_id} has no license record")
        for field in ("spdx", "evidence", "attribution"):
            if not isinstance(license_data.get(field), str) or not license_data[field]:
                raise ManifestError(f"source {source_id} license is missing {field}")

    allowed_hosts = set(policy.get("allowed_hosts", []))
    if not allowed_hosts:
        raise ManifestError("acquisition policy must declare allowed hosts")
    artifact_ids: set[str] = set()
    artifact_paths: set[str] = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise ManifestError("artifact entries must be objects")
        artifact_id = artifact.get("id")
        relative_path = artifact.get("path")
        if not isinstance(artifact_id, str) or artifact_id in artifact_ids:
            raise ManifestError(f"invalid or duplicate artifact id: {artifact_id!r}")
        if not isinstance(relative_path, str) or relative_path in artifact_paths:
            raise ManifestError(f"invalid or duplicate artifact path: {relative_path!r}")
        artifact_ids.add(artifact_id)
        artifact_paths.add(relative_path)
        path_parts = Path(relative_path).parts
        if Path(relative_path).is_absolute() or ".." in path_parts:
            raise ManifestError(f"artifact path escapes output directory: {relative_path}")
        if artifact.get("source") not in source_ids:
            raise ManifestError(f"artifact {artifact_id} references an unknown source")
        if not isinstance(artifact.get("bytes"), int) or artifact["bytes"] <= 0:
            raise ManifestError(f"artifact {artifact_id} has invalid expected size")
        if not isinstance(artifact.get("sha256"), str) or not SHA256_RE.fullmatch(
            artifact["sha256"]
        ):
            raise ManifestError(f"artifact {artifact_id} has invalid sha256")
        parsed_url = urlparse(str(artifact.get("url", "")))
        if parsed_url.scheme != "https" or parsed_url.hostname not in allowed_hosts:
            raise ManifestError(f"artifact {artifact_id} uses a disallowed URL")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_disk_budget(
    manifest: dict[str, Any], raw_dir: Path, budget_bytes: int
) -> int:
    """Return worst-case peak bytes or reject an unsafe acquisition budget."""

    maximum = manifest["acquisition_policy"]["maximum_disk_budget_bytes"]
    if (
        not isinstance(budget_bytes, int)
        or isinstance(budget_bytes, bool)
        or budget_bytes <= 0
    ):
        raise BudgetError("disk budget must be a positive integer number of bytes")
    if maximum > HARD_MAX_DISK_BUDGET_BYTES:
        raise ManifestError("manifest disk cap exceeds the hard 10 GiB limit")
    if budget_bytes > maximum or budget_bytes > HARD_MAX_DISK_BUDGET_BYTES:
        raise BudgetError("disk budget may not exceed 10 GiB")

    current_bytes = 0
    if raw_dir.exists():
        current_bytes = sum(
            path.stat().st_size
            for path in raw_dir.rglob("*")
            if path.is_file() and path.name != ".gitignore"
        )

    additional_bytes = 0
    for artifact in manifest["artifacts"]:
        destination = raw_dir / artifact["path"]
        if (
            destination.is_file()
            and destination.stat().st_size == artifact["bytes"]
            and _sha256_file(destination) == artifact["sha256"]
        ):
            continue
        additional_bytes += artifact["bytes"]

    required_peak_bytes = current_bytes + additional_bytes
    if required_peak_bytes > budget_bytes:
        raise BudgetError(
            f"acquisition needs {required_peak_bytes} bytes, budget is {budget_bytes}"
        )
    return required_peak_bytes


def _default_opener(url: str) -> Any:
    request = Request(url, headers={"User-Agent": "PaletteBrain-source-acquirer/1"})
    return urlopen(request, timeout=60)


def _normalized_etag(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if normalized.startswith("W/"):
        normalized = normalized[2:].strip()
    return normalized.strip('"')


def _is_verified_file(path: Path, artifact: dict[str, Any]) -> bool:
    return (
        path.is_file()
        and path.stat().st_size == artifact["bytes"]
        and _sha256_file(path) == artifact["sha256"]
    )


def acquire_artifacts(
    manifest: dict[str, Any],
    raw_dir: Path,
    *,
    budget_bytes: int,
    opener: Callable[[str], Any] = _default_opener,
) -> AcquisitionSummary:
    """Fetch missing pinned artifacts and atomically publish verified files."""

    validate_disk_budget(manifest, raw_dir, budget_bytes)
    raw_dir.mkdir(parents=True, exist_ok=True)
    downloaded = 0
    reused = 0
    verified_bytes = 0

    for artifact in manifest["artifacts"]:
        destination = raw_dir / artifact["path"]
        if _is_verified_file(destination, artifact):
            reused += 1
            verified_bytes += artifact["bytes"]
            continue

        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=f".{destination.name}.",
                suffix=".tmp",
                dir=destination.parent,
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                digest = hashlib.sha256()
                actual_bytes = 0
                with opener(artifact["url"]) as response:
                    expected_etag = artifact.get("etag")
                    observed_etag = _normalized_etag(response.headers.get("ETag"))
                    if expected_etag is not None and observed_etag != expected_etag:
                        raise AcquisitionError(
                            f"{artifact['id']} ETag mismatch: {observed_etag!r}"
                        )
                    while True:
                        chunk = response.read(64 * 1024)
                        if not chunk:
                            break
                        actual_bytes += len(chunk)
                        if actual_bytes > artifact["bytes"]:
                            raise AcquisitionError(
                                f"{artifact['id']} exceeds pinned size"
                            )
                        digest.update(chunk)
                        temporary_file.write(chunk)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())

            if actual_bytes != artifact["bytes"]:
                raise AcquisitionError(
                    f"{artifact['id']} size mismatch: {actual_bytes}"
                )
            actual_sha256 = digest.hexdigest()
            if actual_sha256 != artifact["sha256"]:
                raise AcquisitionError(
                    f"{artifact['id']} sha256 mismatch: {actual_sha256}"
                )
            os.replace(temporary_path, destination)
            temporary_path = None
            downloaded += 1
            verified_bytes += actual_bytes
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    return AcquisitionSummary(
        downloaded=downloaded,
        reused=reused,
        verified_bytes=verified_bytes,
    )


def verify_wada_dedup(
    wada_colors: list[dict[str, Any]],
    colorcombinations_rows: list[dict[str, str]],
    *,
    expected_mirrors: int,
    slug_pattern: str = r"^wada-(\d{3})-",
) -> int:
    """Prove that colorcombinations Wada rows mirror the native plate order."""

    palettes: dict[int, list[str]] = {}
    for color in wada_colors:
        hex_value = color.get("hex")
        combinations = color.get("combinations")
        if not isinstance(hex_value, str) or not isinstance(combinations, list):
            raise ProvenanceError("invalid Wada color record")
        for plate_id in combinations:
            if not isinstance(plate_id, int):
                raise ProvenanceError("invalid Wada plate id")
            palettes.setdefault(plate_id, []).append(hex_value.lower())

    expression = re.compile(slug_pattern)
    observed_plate_ids: set[int] = set()
    mirror_count = 0
    for row in colorcombinations_rows:
        match = expression.match(row.get("slug", ""))
        if match is None:
            continue
        plate_id = int(match.group(1))
        if plate_id in observed_plate_ids:
            raise ProvenanceError(f"duplicate colorcombinations Wada plate {plate_id}")
        observed_plate_ids.add(plate_id)
        mirror_count += 1
        site_hexes = [
            value.lower()
            for key, value in sorted(
                row.items(),
                key=lambda item: (
                    int(item[0].split("_", 1)[1])
                    if re.fullmatch(r"hex_\d+", item[0])
                    else 10_000
                ),
            )
            if re.fullmatch(r"hex_\d+", key) and value
        ]
        if site_hexes != palettes.get(plate_id):
            raise ProvenanceError(
                f"colorcombinations Wada plate {plate_id} is not an exact mirror"
            )

    if mirror_count != expected_mirrors:
        raise ProvenanceError(
            f"expected {expected_mirrors} Wada mirrors, found {mirror_count}"
        )
    if len(palettes) != expected_mirrors or observed_plate_ids != set(palettes):
        raise ProvenanceError("Wada plate ids and mirrored plate ids differ")
    return mirror_count


def _source_by_id(manifest: dict[str, Any], source_id: str) -> dict[str, Any]:
    for source in manifest["sources"]:
        if source["id"] == source_id:
            return source
    raise ProvenanceError(f"missing source record: {source_id}")


def _artifact_path(
    manifest: dict[str, Any], raw_dir: Path, artifact_id: str
) -> Path:
    for artifact in manifest["artifacts"]:
        if artifact["id"] == artifact_id:
            return raw_dir / artifact["path"]
    raise ProvenanceError(f"missing artifact record: {artifact_id}")


def verify_acquired_provenance(
    manifest: dict[str, Any], raw_dir: Path
) -> ProvenanceSummary:
    """Validate counts, Rang native records, and Wada mirror identity."""

    wada_source = _source_by_id(manifest, "wada")
    colorcombinations_source = _source_by_id(manifest, "colorcombinations")
    rang_source = _source_by_id(manifest, "rang")
    wada_policy = wada_source["provenance"]
    colorcombinations_policy = colorcombinations_source["provenance"]
    rang_policy = rang_source["provenance"]

    try:
        wada_colors = json.loads(
            _artifact_path(manifest, raw_dir, "wada-colors").read_text(
                encoding="utf-8"
            )
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise ProvenanceError(f"cannot parse Wada colors: {exc}") from exc
    if not isinstance(wada_colors, list):
        raise ProvenanceError("Wada colors must be a JSON array")
    if len(wada_colors) != wada_policy["expected_unique_colors"]:
        raise ProvenanceError("unexpected Wada unique-color count")

    csv_path = _artifact_path(manifest, raw_dir, "colorcombinations-palettes")
    try:
        with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
            rows = list(csv.DictReader(csv_file))
    except OSError as exc:
        raise ProvenanceError(f"cannot parse colorcombinations CSV: {exc}") from exc
    if len(rows) != colorcombinations_policy["expected_rows"]:
        raise ProvenanceError("unexpected colorcombinations row count")

    wada_mirrors = verify_wada_dedup(
        wada_colors,
        rows,
        expected_mirrors=colorcombinations_policy["expected_wada_mirrors"],
        slug_pattern=colorcombinations_policy["wada_mirror_slug_regex"],
    )
    editorial_palettes = len(rows) - wada_mirrors
    if editorial_palettes != colorcombinations_policy["expected_editorial_palettes"]:
        raise ProvenanceError("unexpected colorcombinations editorial count")

    rang_artifacts = [
        artifact
        for artifact in manifest["artifacts"]
        if artifact["source"] == "rang"
    ]
    if len(rang_artifacts) != rang_policy["expected_palettes"]:
        raise ProvenanceError("unexpected Rang artifact count")
    permitted_counts = set(rang_policy["native_color_counts"])
    for artifact in rang_artifacts:
        try:
            palette = json.loads(
                (raw_dir / artifact["path"]).read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise ProvenanceError(f"cannot parse {artifact['id']}: {exc}") from exc
        if not isinstance(palette, dict) or not isinstance(palette.get("name"), str):
            raise ProvenanceError(f"invalid native Rang record: {artifact['id']}")
        colors = palette.get("colors")
        notes = palette.get("notes")
        order = palette.get("order")
        if (
            not isinstance(colors, list)
            or len(colors) not in permitted_counts
            or not all(
                isinstance(color, str)
                and re.fullmatch(r"#[0-9a-fA-F]{6}", color) is not None
                for color in colors
            )
            or not isinstance(notes, list)
            or len(notes) != len(colors)
            or not isinstance(order, list)
            or sorted(order) != list(range(1, len(colors) + 1))
        ):
            raise ProvenanceError(f"invalid native Rang palette: {artifact['id']}")

    return ProvenanceSummary(
        wada_palettes=wada_policy["expected_palettes"],
        wada_mirrors=wada_mirrors,
        editorial_palettes=editorial_palettes,
        rang_palettes=len(rang_artifacts),
    )


def _argument_parser() -> argparse.ArgumentParser:
    package_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Acquire PaletteBrain's pinned, licensed palette sources."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=package_dir / "source_manifest.v1.json",
        help="tracked source manifest",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=package_dir / "data" / "raw",
        help="ignored raw-data directory",
    )
    parser.add_argument(
        "--disk-budget-bytes",
        type=int,
        default=None,
        help="positive byte limit; hard-capped at 10 GiB",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _argument_parser().parse_args(argv)
    try:
        manifest = load_manifest(args.manifest)
        budget_bytes = args.disk_budget_bytes
        if budget_bytes is None:
            budget_bytes = manifest["acquisition_policy"][
                "maximum_disk_budget_bytes"
            ]
        acquisition = acquire_artifacts(
            manifest,
            args.raw_dir,
            budget_bytes=budget_bytes,
        )
        provenance = verify_acquired_provenance(manifest, args.raw_dir)
    except (
        AcquisitionError,
        BudgetError,
        ManifestError,
        OSError,
        ProvenanceError,
    ) as exc:
        print(
            json.dumps(
                {"status": "error", "error": str(exc)},
                ensure_ascii=True,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        return 2

    print(
        json.dumps(
            {
                "status": "ok",
                "downloaded": acquisition.downloaded,
                "reused": acquisition.reused,
                "verified_bytes": acquisition.verified_bytes,
                "independent_palettes": provenance.independent_palettes,
                "wada_mirrors_deduplicated": provenance.wada_mirrors,
                "raw_dir": str(args.raw_dir.resolve()),
            },
            ensure_ascii=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
