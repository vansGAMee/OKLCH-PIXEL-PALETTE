from __future__ import annotations

import argparse
import csv
import hashlib
import http.client
import io
import json
import math
import os
import re
import shutil
import sys
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from pathlib import Path
from typing import Any, Iterable

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import numpy as np
from PIL import Image
import torch
import torch.nn.functional as F
import transformers
from transformers import AutoModel, AutoProcessor, AutoTokenizer

from ml.palettebrain.color_distribution import palette_or_pixels_to_oklch_histogram
from ml.palettebrain.dataset import MAX_COLORS, seed_noise_from_uint32
from ml.palettebrain.e5_embedding import (
    E5_MODEL_ID,
    E5_REVISION,
    embed_texts,
    load_encoder,
)
from ml.palettebrain.palette_targets import oklab_to_oklch, physical_oklch_to_target

SIGLIP_MODEL_ID = "google/siglip-base-patch16-224"
SIGLIP_REVISION = "7fd15f0689c79d79e38b1c2e2e2370a7bf2761ed"

METADATA_INDEX_SCHEMA = "palettebrain-c11-metadata-index/v3"
CALIBRATION_SCHEMA = "palettebrain-c11-siglip-calibration/v1"
ACQUISITION_STATE_SCHEMA = "palettebrain-c11-acquisition-state/v1"
RELEVANCE_CACHE_SCHEMA = "palettebrain-c11-relevance-cache/v1"

OPEN_IMAGES_RELEASE = "Open Images V7"
OPEN_IMAGES_CLASS_URL = (
    "https://storage.googleapis.com/openimages/v7/"
    "oidv7-class-descriptions-boxable.csv"
)
# The official Open Images V7 download page intentionally links these legacy object URLs.
OPEN_IMAGES_VALIDATION_BBOX_URL = (
    "https://storage.googleapis.com/openimages/v5/"
    "validation-annotations-bbox.csv"
)
OPEN_IMAGES_VALIDATION_META_URL = (
    "https://storage.googleapis.com/openimages/2018_04/validation/"
    "validation-images-with-rotation.csv"
)

MAX_SINGLE_IMAGE_BYTES = 25 * 1024 * 1024
MAX_API_BYTES = 16 * 1024 * 1024
MAX_OPEN_IMAGES_METADATA_BYTES = 256 * 1024 * 1024
NEAR_DUP_HAMMING = 2

SMOKE_VALID_IMAGES = 48
SMOKE_MIN_VALID_PER_SOURCE = 2
SMOKE_SOURCE_TARGETS = {
    "open_images": 20,
    "met": 60,
    "artic": 60,
    "openverse": 20,
}
FULL_MIN_UNIQUE_IMAGES = 1500
FULL_TARGET_UNIQUE_IMAGES = 2500
FULL_MAX_VALID_IMAGES = 3500
FULL_ACQUISITION_CAPS = (8, 10, 12, 14)
FULL_MAX_PER_CONCEPT = max(FULL_ACQUISITION_CAPS)
TARGETED_MAX_TRAINING_QUERIES = 4
FULL_MIN_CATEGORY_COVERAGE = 0.65
FULL_MIN_CATEGORY_IMAGES = 20
FULL_MIN_CROP_REQUIRED_CONCEPT_COVERAGE = 1.0
FULL_MIN_CROP_REQUIRED_IMAGES_PER_CONCEPT = 2
FULL_MIN_REAL_WORLD_FRACTION = 0.20
FULL_MIN_ARTWORK_FRACTION = 0.20

ALLOWED_OPENVERSE_LICENSES = {"pdm", "cc0", "by"}

# Exact Open Images boxable names are resolved against the official class CSV.
# If a candidate name is absent, that mapping is skipped instead of guessed.
CONCEPT_TO_OPENIMAGES_CLASSES: dict[str, tuple[str, ...]] = {
    "ripe_orchard_apple": ("Apple", "Fruit"),
    "antique_glass_bottle": ("Bottle",),
    "anthracite_coal_lump": ("Coal", "Rock"),
    "structural_steel_beam": ("Building material",),
    "antique_leather_volume": ("Book",),
    "terracotta_earthenware_pot": ("Flowerpot", "Vase"),
    "iridescent_nacre_seashell": ("Shell",),
    "harvest_pumpkin_gourd": ("Pumpkin", "Fruit"),
    "sliced_pomegranate_fruit": ("Fruit",),
    "fresh_purple_fig": ("Fruit",),
    "wild_chanterelle_mushrooms": ("Mushroom",),
    "sunflower_head_seeds": ("Flower",),
    "bleached_beach_driftwood": ("Wood",),
    "raw_wax_honeycomb": ("Food",),
    "glossy_obsidian_mineral": ("Rock",),
    "rough_granite_chunk": ("Rock",),
    "vintage_brass_pocketwatch": ("Watch", "Clock"),
    "hammered_copper_kettle": ("Kettle", "Teapot"),
    "blacksmith_iron_anvil": ("Tool",),
    "carved_walnut_chest": ("Chest of drawers", "Box"),
    "wild_blackberry_cluster": ("Fruit",),
    "ripe_dark_cherries": ("Fruit",),
    "yellow_citrus_lemon": ("Lemon", "Fruit"),
    "walnut_in_cracked_shell": ("Nut", "Food"),
    "dark_grape_cluster": ("Grape", "Fruit"),
    "scarlet_poppy_blossom": ("Flower",),
    "white_waterlily_flower": ("Flower",),
    "raw_flax_fiber": ("Textile",),
    "carved_amber_pendant": ("Necklace",),
    "hand_carved_soapstone": ("Sculpture",),
    "polished_lapis_lazuli": ("Gemstone", "Rock"),
}


class HardDiskLimitError(RuntimeError):
    pass


class ProvenanceError(RuntimeError):
    pass


def normalize_text(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(text)).lower().strip().split())


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def atomic_savez(path: Path, **arrays: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.npz")
    np.savez(tmp, **arrays)
    with np.load(tmp, allow_pickle=False):
        pass
    tmp.replace(path)


def get_disk_usage_bytes(paths: Iterable[Path]) -> int:
    total = 0
    seen: set[Path] = set()
    for raw in paths:
        p = raw.resolve()
        if p in seen or not p.exists():
            continue
        seen.add(p)
        if p.is_file():
            total += p.stat().st_size
        else:
            for f in p.rglob("*"):
                if f.is_file():
                    total += f.stat().st_size
    return total


class DiskBudget:
    def __init__(
        self,
        *,
        raw_dir: Path,
        cache_dir: Path,
        target_bytes: int,
        hard_bytes: int,
        minimum_free_bytes: int = 2 * 1024**3,
    ) -> None:
        self.raw_dir = raw_dir
        self.cache_dir = cache_dir
        self.target_bytes = int(target_bytes)
        self.hard_bytes = int(hard_bytes)
        self.minimum_free_bytes = int(minimum_free_bytes)
        if self.target_bytes <= 0 or self.hard_bytes <= 0:
            raise ValueError("disk budgets must be positive")
        if self.target_bytes >= self.hard_bytes:
            raise ValueError("target disk budget must be below hard disk budget")
        self._tracked_artifacts: set[Path] = set()
        self._tracked_bytes: int | None = None
        self._last_reconcile: float = 0.0
        self._lock = threading.RLock()

    def free_bytes(self) -> int:
        anchor = self.raw_dir if self.raw_dir.exists() else self.raw_dir.parent
        anchor.mkdir(parents=True, exist_ok=True)
        return int(shutil.disk_usage(anchor).free)

    def summary(self) -> str:
        return (
            f"DISK used={self.usage() / 1024**3:.2f} GiB "
            f"free={self.free_bytes() / 1024**3:.2f} GiB"
        )

    def _check_free_space(self, additional_bytes: int = 0) -> None:
        remaining = self.free_bytes() - int(additional_bytes)
        if remaining < self.minimum_free_bytes:
            raise HardDiskLimitError(
                "FREE DISK RESERVE WOULD BE VIOLATED: "
                f"remaining={remaining} reserve={self.minimum_free_bytes}"
            )

    def _covered_by_primary_tree(self, path: Path) -> bool:
        resolved = path.resolve()
        for root in (self.raw_dir.resolve(), self.cache_dir.resolve()):
            try:
                resolved.relative_to(root)
                return True
            except ValueError:
                continue
        return False

    def track_artifact(self, path: Path) -> None:
        resolved = path.resolve()
        with self._lock:
            if not self._covered_by_primary_tree(resolved):
                if resolved not in self._tracked_artifacts:
                    self._tracked_artifacts.add(resolved)
                    if self._tracked_bytes is not None and resolved.is_file():
                        self._tracked_bytes += resolved.stat().st_size

    def reconcile(self) -> int:
        with self._lock:
            self._tracked_bytes = get_disk_usage_bytes(
                [self.raw_dir, self.cache_dir, *sorted(self._tracked_artifacts)]
            )
            self._last_reconcile = time.time()
            return self._tracked_bytes

    def usage(self, force_scan: bool = False) -> int:
        with self._lock:
            now = time.time()
            if (
                self._tracked_bytes is None
                or force_scan
                or (now - self._last_reconcile > 60.0)
            ):
                return self.reconcile()
            return self._tracked_bytes

    def add_bytes(self, byte_count: int) -> None:
        with self._lock:
            if self._tracked_bytes is not None:
                self._tracked_bytes += int(byte_count)

    def before_download(self) -> bool:
        self._check_free_space()
        usage = self.usage()
        if usage >= self.hard_bytes:
            raise HardDiskLimitError(
                f"HARD DISK LIMIT EXCEEDED: {usage} >= {self.hard_bytes}"
            )
        return usage < self.target_bytes

    def max_download_bytes(self, cap: int = MAX_SINGLE_IMAGE_BYTES) -> int:
        self._check_free_space()
        usage = self.usage()
        remaining = self.hard_bytes - usage - 1
        if remaining <= 0:
            raise HardDiskLimitError("no disk budget remains")
        return max(1, min(int(cap), remaining))

    def before_write(self, byte_count: int) -> None:
        self._check_free_space(byte_count)
        usage = self.usage()
        projected = usage + int(byte_count)
        if projected >= self.hard_bytes:
            raise HardDiskLimitError(
                f"HARD DISK LIMIT EXCEEDED BEFORE WRITE: "
                f"{projected} >= {self.hard_bytes}"
            )

    def before_temp_commit(self, temp_path: Path) -> None:
        if not temp_path.is_file():
            raise FileNotFoundError(temp_path)
        projected = self.usage()
        if not self._covered_by_primary_tree(temp_path):
            projected += temp_path.stat().st_size
        if projected >= self.hard_bytes:
            raise HardDiskLimitError(
                f"HARD DISK LIMIT EXCEEDED BEFORE ARTIFACT COMMIT: "
                f"{projected} >= {self.hard_bytes}"
            )
        self._check_free_space()

    def commit_file(self, tmp_path: Path, dest_path: Path) -> None:
        with self._lock:
            if not tmp_path.is_file():
                raise FileNotFoundError(tmp_path)
            new_size = tmp_path.stat().st_size
            old_size = dest_path.stat().st_size if dest_path.is_file() else 0
            delta = new_size - old_size
            self._check_free_space(max(0, delta))
            cur_usage = self.usage()
            if cur_usage + delta >= self.hard_bytes:
                raise HardDiskLimitError(
                    f"HARD DISK LIMIT EXCEEDED BEFORE FILE COMMIT: "
                    f"{cur_usage + delta} >= {self.hard_bytes}"
                )
            tmp_path.replace(dest_path)
            if self._tracked_bytes is not None:
                self._tracked_bytes += delta
            if not self._covered_by_primary_tree(dest_path):
                self._tracked_artifacts.add(dest_path.resolve())


def estimate_npz_bytes(arrays: dict[str, Any]) -> int:
    total = 64 * 1024
    for value in arrays.values():
        arr = np.asarray(value)
        total += int(arr.nbytes) + 512
    return total


def guarded_atomic_savez(
    path: Path,
    *,
    disk: DiskBudget,
    arrays: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    disk.track_artifact(path)
    disk.before_write(estimate_npz_bytes(arrays))
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.{uuid4().hex}.tmp.npz")
    np.savez(tmp, **arrays)
    try:
        with np.load(tmp, allow_pickle=False):
            pass
        disk.commit_file(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def guarded_atomic_write_text(
    path: Path,
    text: str,
    *,
    disk: DiskBudget,
) -> None:
    encoded = text.encode("utf-8")
    disk.track_artifact(path)
    disk.before_write(len(encoded))
    tmp = path.with_name(
        f"{path.name}.{os.getpid()}.{threading.get_ident()}.{uuid4().hex}.tmp"
    )
    tmp.write_bytes(encoded)
    try:
        disk.commit_file(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def guarded_atomic_write_bytes(path: Path, data: bytes, *, disk: DiskBudget) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    disk.track_artifact(path)
    disk.before_write(len(data))
    tmp = path.with_name(
        f"{path.name}.{os.getpid()}.{threading.get_ident()}.{uuid4().hex}.tmp"
    )
    tmp.write_bytes(data)
    try:
        disk.commit_file(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


class AcquisitionFunnel:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.start_time = time.time()
        self.last_report_time = time.time()
        self.siglip_seconds = 0.0
        self.providers = ("open_images", "met", "artic", "openverse")
        self.metrics: dict[str, dict[str, Any]] = {
            p: {
                "metadata_candidates": 0,
                "already_seen_skipped": 0,
                "download_attempted": 0,
                "download_success": 0,
                "decode_success": 0,
                "crop_success": 0,
                "siglip_scored": 0,
                "siglip_pass": 0,
                "siglip_fail": 0,
                "seconds_metadata": 0.0,
                "seconds_network": 0.0,
                "seconds_decode": 0.0,
                "seconds_siglip": 0.0,
            }
            for p in self.providers
        }
        self.concept_metrics: dict[str, dict[str, int]] = {}

    def record(self, provider: str, field: str, amount: int = 1, cid: str | None = None) -> None:
        p = provider if provider in self.metrics else "open_images"
        with self._lock:
            if field in self.metrics[p]:
                self.metrics[p][field] += amount
            if cid:
                c_stats = self.concept_metrics.setdefault(cid, {"scored": 0, "pass": 0})
                if field == "siglip_scored":
                    c_stats["scored"] += amount
                elif field == "siglip_pass":
                    c_stats["pass"] += amount

    def add_time(self, provider: str, field: str, duration: float) -> None:
        p = provider if provider in self.metrics else "open_images"
        with self._lock:
            if field in self.metrics[p]:
                self.metrics[p][field] += float(duration)

    def add_siglip_time(self, duration: float) -> None:
        with self._lock:
            self.siglip_seconds += float(duration)

    def summary(self, force: bool = False) -> str | None:
        with self._lock:
            now = time.time()
            if not force and (now - self.last_report_time < 30.0):
                return None
            self.last_report_time = now
            lines = ["\n==================== ACQUISITION FUNNEL ===================="]
            total_cand = sum(int(m["metadata_candidates"]) for m in self.metrics.values())
            total_seen = sum(int(m["already_seen_skipped"]) for m in self.metrics.values())
            total_dl_att = sum(int(m["download_attempted"]) for m in self.metrics.values())
            total_dl = sum(int(m["download_success"]) for m in self.metrics.values())
            total_dec = sum(int(m["decode_success"]) for m in self.metrics.values())
            total_scored = sum(int(m["siglip_scored"]) for m in self.metrics.values())
            total_pass = sum(int(m["siglip_pass"]) for m in self.metrics.values())
            total_rate = (total_pass / total_scored * 100) if total_scored > 0 else 0.0

            for p in self.providers:
                m = self.metrics[p]
                scored = int(m["siglip_scored"])
                passed = int(m["siglip_pass"])
                rate = (passed / scored * 100) if scored > 0 else 0.0
                lines.append(
                    f"  [{p:11s}] meta={m['metadata_candidates']:4d} | seen_skip={m['already_seen_skipped']:4d} | "
                    f"dl={m['download_success']:4d}/{m['download_attempted']:4d} | dec={m['decode_success']:4d} | "
                    f"scored={scored:4d} | pass={passed:4d} ({rate:5.1f}%) | "
                    f"time: meta={m['seconds_metadata']:5.1f}s net={m['seconds_network']:5.1f}s "
                    f"dec={m['seconds_decode']:5.1f}s sig={m['seconds_siglip']:5.1f}s"
                )
            lines.append(
                f"  [TOTAL] cand={total_cand} seen_skip={total_seen} dl={total_dl}/{total_dl_att} dec={total_dec} "
                f"scored={total_scored} pass={total_pass} ({total_rate:.1f}% valid_rate) "
                f"siglip_wall={self.siglip_seconds:.1f}s"
            )
            lines.append("=============================================================")
            return "\n".join(lines)


_FUNNEL = AcquisitionFunnel()
_OPENVERSE_LOCK = threading.RLock()
_OPENVERSE_COOLDOWN_UNTIL: float = 0.0
_OPENVERSE_CONSECUTIVE_429: int = 0
_OPENVERSE_LAST_SEARCH_TIME: float = 0.0
_OPENVERSE_SEARCH_MIN_INTERVAL: float = 3.5
_OPENVERSE_QUERY_CACHE: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
_OPENVERSE_UNAVAILABLE: bool = False
_ARTIC_LOCK = threading.RLock()
_ARTIC_CONSECUTIVE_403: int = 0
_ARTIC_UNAVAILABLE: bool = False
_ARTIC_403_CIRCUIT_THRESHOLD = 3

_API_CACHE_LOCK = threading.RLock()
_API_KEY_LOCKS: dict[tuple[str, tuple[Any, ...]], threading.Lock] = {}
_MET_QUERY_CACHE: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
_MET_SEARCH_CACHE: dict[str, list[Any]] = {}
_ARTIC_QUERY_CACHE: dict[tuple[Any, ...], list[dict[str, Any]]] = {}

_GLOBAL_NETWORK_SEMAPHORE = threading.Semaphore(16)
_GLOBAL_DEDUP_LOCK = threading.RLock()
_CACHED_RECORDS_LOCK = threading.RLock()
_RESERVED_HASHES: set[str] = set()
_RESERVED_PHASHES: list[str] = []
_DOWNLOAD_WORKERS = 6
_METADATA_WORKERS = 8
_ACQUISITION_STATE_PATH: Path | None = None
_ACQUISITION_STATE: dict[str, Any] = {
    "schema": ACQUISITION_STATE_SCHEMA,
    "fingerprint": "",
    "permanentFailedUrls": {},
    "disabledProviders": {},
}
_ACQUISITION_STATE_LOCK = threading.RLock()
_ACQUISITION_STATE_DIRTY = 0
_ACQUISITION_STATE_LAST_FLUSH = 0.0


class CandidateBatch(list[dict[str, Any]]):
    def __init__(self, values: Iterable[dict[str, Any]] = (), *, consumed: bool) -> None:
        super().__init__(values)
        self.consumed = bool(consumed)


def configure_acquisition_runtime(
    *,
    state_path: Path,
    fingerprint: str,
    download_workers: int,
    metadata_workers: int,
) -> None:
    global _ACQUISITION_STATE_PATH, _ACQUISITION_STATE
    global _DOWNLOAD_WORKERS, _METADATA_WORKERS, _OPENVERSE_UNAVAILABLE
    global _ARTIC_UNAVAILABLE, _ARTIC_CONSECUTIVE_403
    if not 1 <= download_workers <= 64 or not 1 <= metadata_workers <= 64:
        raise ValueError("acquisition worker counts must be in 1..64")
    _DOWNLOAD_WORKERS = int(download_workers)
    _METADATA_WORKERS = int(metadata_workers)
    _ACQUISITION_STATE_PATH = state_path
    loaded: dict[str, Any] = {}
    if state_path.is_file():
        try:
            candidate = json.loads(state_path.read_text(encoding="utf-8"))
            if (
                candidate.get("schema") == ACQUISITION_STATE_SCHEMA
                and candidate.get("fingerprint") == fingerprint
            ):
                loaded = candidate
        except (OSError, json.JSONDecodeError):
            loaded = {}
    _ACQUISITION_STATE = loaded or {
        "schema": ACQUISITION_STATE_SCHEMA,
        "fingerprint": fingerprint,
        "permanentFailedUrls": {},
        "disabledProviders": {},
    }
    # Provider challenges are transient external state. Never carry a run-local
    # circuit breaker into a future resume and silently starve a healthy route.
    _ACQUISITION_STATE.setdefault("disabledProviders", {}).pop("openverse", None)
    disabled_providers = _ACQUISITION_STATE.setdefault("disabledProviders", {})
    artic_disabled = disabled_providers.get("artic", {})
    artic_retry_after = float(artic_disabled.get("retryAfter", 0.0) or 0.0)
    recent_artic_403 = [
        float(details.get("timestamp", 0.0) or 0.0)
        for url, details in _ACQUISITION_STATE.get("permanentFailedUrls", {}).items()
        if "www.artic.edu/iiif/" in url
        and details.get("reason") == "http_403"
        and float(details.get("timestamp", 0.0) or 0.0) > time.time() - 6 * 60 * 60
    ]
    if len(recent_artic_403) >= _ARTIC_403_CIRCUIT_THRESHOLD:
        artic_retry_after = max(artic_retry_after, max(recent_artic_403) + 6 * 60 * 60)
        disabled_providers["artic"] = {
            "reason": "iiif_http_403",
            "timestamp": max(recent_artic_403),
            "retryAfter": artic_retry_after,
        }
    if artic_retry_after <= time.time():
        disabled_providers.pop("artic", None)
    _OPENVERSE_UNAVAILABLE = False
    _ARTIC_UNAVAILABLE = artic_retry_after > time.time()
    _ARTIC_CONSECUTIVE_403 = 0
    persist_acquisition_state()


def persist_acquisition_state() -> None:
    global _ACQUISITION_STATE_DIRTY, _ACQUISITION_STATE_LAST_FLUSH
    if _ACQUISITION_STATE_PATH is None:
        return
    with _ACQUISITION_STATE_LOCK:
        atomic_write_text(
            _ACQUISITION_STATE_PATH,
            json.dumps(_ACQUISITION_STATE, ensure_ascii=False, indent=2) + "\n",
        )
        _ACQUISITION_STATE_DIRTY = 0
        _ACQUISITION_STATE_LAST_FLUSH = time.time()


def _mark_permanent_url_failure(url: str, reason: str) -> None:
    global _ACQUISITION_STATE_DIRTY
    with _ACQUISITION_STATE_LOCK:
        failures = _ACQUISITION_STATE.setdefault("permanentFailedUrls", {})
        failures[url] = {"reason": reason, "timestamp": time.time()}
        _ACQUISITION_STATE_DIRTY += 1
        flush = (
            _ACQUISITION_STATE_DIRTY >= 25
            or time.time() - _ACQUISITION_STATE_LAST_FLUSH >= 10.0
        )
    if flush:
        persist_acquisition_state()


def _disable_provider(
    provider: str, reason: str, *, cooldown_seconds: float | None = None
) -> None:
    with _ACQUISITION_STATE_LOCK:
        disabled = _ACQUISITION_STATE.setdefault("disabledProviders", {})
        timestamp = time.time()
        disabled[provider] = {"reason": reason, "timestamp": timestamp}
        if cooldown_seconds is not None:
            disabled[provider]["retryAfter"] = timestamp + cooldown_seconds
    persist_acquisition_state()


def _route_key(concept_id: str, provider: str, query: str) -> str:
    return hashlib.sha256(
        f"{concept_id}\0{provider}\0{query.strip().lower()}".encode("utf-8")
    ).hexdigest()


def _record_route(route_key: str, field: str, amount: float = 1.0) -> None:
    global _ACQUISITION_STATE_DIRTY
    if not route_key:
        return
    with _ACQUISITION_STATE_LOCK:
        route = _ACQUISITION_STATE.setdefault("routeStats", {}).setdefault(
            route_key,
            {"metadata": 0, "attempted": 0, "downloaded": 0,
             "scored": 0, "passed": 0, "networkSeconds": 0.0},
        )
        route[field] = route.get(field, 0) + amount
        _ACQUISITION_STATE_DIRTY += 1


def _route_priority(route_key: str) -> float:
    with _ACQUISITION_STATE_LOCK:
        route = dict(_ACQUISITION_STATE.get("routeStats", {}).get(route_key, {}))
        has_route_cursor = route_key in _ACQUISITION_STATE.get("routeOffsets", {})
    # Stats written by the legacy provider-wide cursor cannot prove that this
    # query's first page was ever visited. Give it one correctly isolated pass.
    if route and not has_route_cursor:
        return 1.0
    attempted = int(route.get("attempted", 0))
    downloaded = int(route.get("downloaded", 0))
    scored = int(route.get("scored", 0))
    passed = int(route.get("passed", 0))
    seconds = float(route.get("networkSeconds", 0.0))
    if int(route.get("batches", 0)) >= 2 and int(route.get("metadata", 0)) == 0:
        return 0.0
    if attempted >= 20 and downloaded == 0:
        return 0.0
    if scored >= 10 and passed == 0:
        return 0.0
    if int(route.get("emptyBatches", 0)) >= 2:
        return 0.0
    expected_valid = (passed + 1.0) / (scored + 5.0)
    download_rate = (downloaded + 1.0) / (attempted + 2.0)
    latency = max(0.1, seconds / max(1, attempted))
    return expected_valid * download_rate / latency


def _provider_viable(provider: str) -> bool:
    if provider == "artic":
        with _ARTIC_LOCK:
            if _ARTIC_UNAVAILABLE:
                return False
    with _FUNNEL._lock:
        metrics = dict(_FUNNEL.metrics.get(provider, {}))
    attempted = int(metrics.get("download_attempted", 0))
    downloaded = int(metrics.get("download_success", 0))
    return not (attempted >= 30 and downloaded == 0)


def normalize_http_url(url: str) -> str:
    cleaned = "".join(character for character in url.strip() if ord(character) >= 32)
    parsed = urllib.parse.urlsplit(cleaned)
    return urllib.parse.urlunsplit((
        parsed.scheme,
        parsed.netloc,
        urllib.parse.quote(parsed.path, safe="/%:@"),
        urllib.parse.quote(parsed.query, safe="=&%+;,:@/?"),
        urllib.parse.quote(parsed.fragment, safe="%+;,:@/?"),
    ))


def safe_http_get(
    url: str,
    *,
    timeout: int = 20,
    max_retries: int = 2,
    max_bytes: int = MAX_API_BYTES,
    pause_seconds: float = 0.15,
    headers: dict[str, str] | None = None,
) -> bytes | None:
    global _OPENVERSE_CONSECUTIVE_429, _OPENVERSE_COOLDOWN_UNTIL, _OPENVERSE_UNAVAILABLE
    global _ARTIC_CONSECUTIVE_403, _ARTIC_UNAVAILABLE
    if not url.startswith(("https://", "http://")):
        _mark_permanent_url_failure(str(url), "unsupported_url_scheme")
        persist_acquisition_state()
        return None
    # Museum and Open Images metadata occasionally contains literal spaces or
    # control characters in otherwise valid URLs. urllib rejects these before
    # any request is made, so normalize components without double-encoding `%`.
    try:
        url = normalize_http_url(url)
    except (TypeError, ValueError, UnicodeError):
        _mark_permanent_url_failure(str(url), "malformed_url")
        persist_acquisition_state()
        return None
    is_artic_iiif = "www.artic.edu/iiif/" in url
    if is_artic_iiif:
        with _ARTIC_LOCK:
            if _ARTIC_UNAVAILABLE:
                return None
    if url in _ACQUISITION_STATE.get("permanentFailedUrls", {}):
        return None
    request_headers = {
        "User-Agent": "PaletteBrain-C11-DataBuilder/1.0",
        "Accept": "*/*",
    }
    if headers:
        request_headers.update(headers)
    for attempt in range(max_retries + 1):
        try:
            req = urllib.request.Request(
                url,
                headers=request_headers,
            )
            with _GLOBAL_NETWORK_SEMAPHORE:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    if "openverse.org" in url:
                        with _OPENVERSE_LOCK:
                            _OPENVERSE_CONSECUTIVE_429 = 0
                        burst_avail = resp.headers.get(
                            "x-ratelimit-available-anon_burst"
                        )
                        if burst_avail is not None:
                            try:
                                if int(burst_avail) <= 1:
                                    time.sleep(4.0)
                            except ValueError:
                                pass
                    if is_artic_iiif:
                        with _ARTIC_LOCK:
                            _ARTIC_CONSECUTIVE_403 = 0
                    length = resp.headers.get("Content-Length")
                    if length:
                        try:
                            if int(length) > max_bytes:
                                return None
                        except ValueError:
                            pass
                    out = bytearray()
                    while True:
                        chunk = resp.read(1024 * 256)
                        if not chunk:
                            break
                        out.extend(chunk)
                        if len(out) > max_bytes:
                            return None
                    if pause_seconds > 0:
                        time.sleep(pause_seconds)
                    return bytes(out)
        except urllib.error.HTTPError as exc:
            if is_artic_iiif and exc.code == 403:
                tripped = False
                with _ARTIC_LOCK:
                    _ARTIC_CONSECUTIVE_403 += 1
                    if (
                        _ARTIC_CONSECUTIVE_403 >= _ARTIC_403_CIRCUIT_THRESHOLD
                        and not _ARTIC_UNAVAILABLE
                    ):
                        _ARTIC_UNAVAILABLE = True
                        tripped = True
                _mark_permanent_url_failure(url, "http_403")
                if tripped:
                    _disable_provider(
                        "artic", "iiif_http_403", cooldown_seconds=6 * 60 * 60
                    )
                return None
            if (
                "openverse.org" in url
                and str(exc.headers.get("CF-Mitigated", "")).lower() == "challenge"
            ):
                with _OPENVERSE_LOCK:
                    if not _OPENVERSE_UNAVAILABLE:
                        print(
                            "Openverse returned CF-Mitigated: challenge; provider "
                            "disabled for this run without retry."
                        )
                    _OPENVERSE_UNAVAILABLE = True
                return None
            if exc.code in (400, 401, 403, 404, 405, 410, 422):
                _mark_permanent_url_failure(url, f"http_{exc.code}")
                return None
            if exc.code == 429:
                retry_after = exc.headers.get("Retry-After")
                wait_sec = 2.0 ** (attempt + 1)
                if retry_after:
                    try:
                        wait_sec = float(retry_after)
                    except ValueError:
                        pass
                wait_sec = min(max(wait_sec, 2.0), 35.0)
                if attempt < max_retries:
                    time.sleep(wait_sec)
                    continue
                if "openverse.org" in url:
                    with _OPENVERSE_LOCK:
                        _OPENVERSE_CONSECUTIVE_429 += 1
                        if _OPENVERSE_CONSECUTIVE_429 >= 2:
                            _OPENVERSE_COOLDOWN_UNTIL = time.time() + 60.0
                            print(
                                "Openverse circuit breaker tripped after repeated "
                                "429 responses; cooldown for 60s."
                            )
                return None
            elif exc.code in (500, 502, 503, 504) and attempt < max_retries:
                time.sleep(min(2.0 ** attempt, 8.0))
                continue
            return None
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError, http.client.HTTPException):
            if attempt < max_retries:
                time.sleep(min(0.75 * (attempt + 1), 3.0))
                continue
            return None
    return None


def fetch_json(
    url: str,
    *,
    timeout: int = 20,
    max_retries: int = 2,
) -> dict[str, Any] | None:
    raw = safe_http_get(
        url,
        timeout=timeout,
        max_retries=max_retries,
        max_bytes=MAX_API_BYTES,
    )
    if not raw:
        return None
    try:
        obj = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return obj if isinstance(obj, dict) else None


def load_and_validate_manifest(manifest_path: Path) -> dict[str, Any]:
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Source manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "palettebrain-c11-source-manifest/v1":
        raise ValueError(f"Invalid manifest schema: {manifest.get('schema')}")

    teacher = manifest.get("teacher", {})
    if teacher.get("revision") != SIGLIP_REVISION:
        raise ValueError(
            f"Manifest teacher revision mismatch: "
            f"{teacher.get('revision')} vs {SIGLIP_REVISION}"
        )
    teacher_id = teacher.get("model_id") or teacher.get("modelId")
    if teacher_id and teacher_id != SIGLIP_MODEL_ID:
        raise ValueError(
            f"Manifest teacher model mismatch: {teacher_id} vs {SIGLIP_MODEL_ID}"
        )

    text_encoder = manifest.get("text_encoder") or manifest.get("textEncoder") or {}
    if isinstance(text_encoder, dict):
        model_id = text_encoder.get("model_id") or text_encoder.get("modelId")
        revision = text_encoder.get("revision")
        if model_id and model_id != E5_MODEL_ID:
            raise ValueError(f"Manifest E5 model mismatch: {model_id} vs {E5_MODEL_ID}")
        if revision and revision != E5_REVISION:
            raise ValueError(
                f"Manifest E5 revision mismatch: {revision} vs {E5_REVISION}"
            )

    policy = manifest.get("acquisition_policy", {})
    max_disk = int(policy.get("maximum_disk_budget_bytes", 10 * 1024**3))
    target_disk = int(policy.get("target_disk_budget_bytes", int(8.5 * 1024**3)))
    if target_disk >= max_disk:
        raise ValueError("manifest target disk budget must be below hard budget")
    return manifest


def preflight_anti_leakage(concepts: list[dict[str, Any]]) -> None:
    benchmark_paths = [
        Path("ml/palettebrain/benchmark_semantic_v3.json"),
        Path("ml/palettebrain/benchmark_visual_semantic_v2.json"),
    ]
    benchmark_texts: set[str] = set()

    v3_path = benchmark_paths[0]
    if not v3_path.is_file():
        raise FileNotFoundError(f"Frozen benchmark missing: {v3_path}")
    v3 = json.loads(v3_path.read_text(encoding="utf-8"))
    for bucket in v3.get("buckets", {}).values():
        for p in bucket:
            benchmark_texts.add(normalize_text(p))
    for pair in v3.get("bilingualPairs", []):
        for p in pair:
            benchmark_texts.add(normalize_text(p))
    for item in v3.get("abstract", []):
        for key in ("en", "ru"):
            if item.get(key):
                benchmark_texts.add(normalize_text(item[key]))
        for key in ("references", "hardNegatives"):
            for p in item.get(key, []):
                benchmark_texts.add(normalize_text(p))
    for key in ("longText", "compositionContrasts"):
        for group in v3.get(key, []):
            for p in group:
                benchmark_texts.add(normalize_text(p))
    for group in v3.get("oodParaphraseGroups", []):
        for p in group:
            benchmark_texts.add(normalize_text(p))
    for key in ("adversarialComposition", "negationControls"):
        for p in v3.get(key, []):
            benchmark_texts.add(normalize_text(p))

    v2_path = benchmark_paths[1]
    if not v2_path.is_file():
        raise FileNotFoundError(f"Frozen benchmark missing: {v2_path}")
    v2 = json.loads(v2_path.read_text(encoding="utf-8"))
    for c in v2.get("concepts", {}).values():
        for p in c.get("prompts", []):
            benchmark_texts.add(normalize_text(p))

    held_out_tokens = {
        "meadow", "meadows", "moss", "mossy", "mosses",
        "clinic", "clinics", "ward", "wards", "pear", "pears", "plum", "plums",
        "поляна", "поляне", "поляны", "поляну", "поляной", "полянами",
        "луг", "лугу", "луга", "лугом", "лугах", "луговой",
        "мох", "мхом", "мха", "мхи", "мшистый", "мшистом", "мшистая",
        "мшистые", "мхами", "мхах",
        "клиника", "клинике", "клиники", "клинику", "клиникой", "клиниках",
        "палата", "палате", "палаты", "палату", "палатой", "палатах",
        "груша", "груши", "грушей", "грушу", "грушами", "грушевый",
        "слива", "сливы", "сливой", "сливу", "сливами", "сливовый",
    }

    benchmark_collisions: list[tuple[str, str]] = []
    held_out_collisions: list[tuple[str, str, list[str]]] = []
    seen_ids: set[str] = set()

    for c in concepts:
        cid = str(c["concept_id"])
        if cid in seen_ids:
            raise RuntimeError(f"duplicate concept_id: {cid}")
        seen_ids.add(cid)
        texts = (
            list(c.get("phrasings_en", []))
            + list(c.get("phrasings_ru", []))
            + [cid, str(c.get("retrieval_query", ""))]
        )
        for text in texts:
            norm = normalize_text(text)
            if norm in benchmark_texts:
                benchmark_collisions.append((cid, text))
            tokens = set(re.findall(r"\w+", norm))
            hit = sorted(tokens & held_out_tokens)
            if hit:
                held_out_collisions.append((cid, text, hit))

    if benchmark_collisions or held_out_collisions:
        raise RuntimeError(
            f"PREFLIGHT ANTI-LEAKAGE FAILED: "
            f"{len(benchmark_collisions)} benchmark collisions, "
            f"{len(held_out_collisions)} held-out collisions"
        )
    print(
        f"Preflight anti-leakage PASSED: 0 benchmark collisions, "
        f"0 held-out collisions across {len(concepts)} concepts."
    )


def rgb_to_oklab_array(rgb: np.ndarray) -> np.ndarray:
    rgb = np.asarray(rgb, dtype=np.float32)
    if rgb.ndim != 2 or rgb.shape[1] != 3:
        raise ValueError("rgb must have shape [N,3]")

    linear = np.empty_like(rgb)
    high = rgb > 0.04045
    linear[high] = ((rgb[high] + 0.055) / 1.055) ** 2.4
    linear[~high] = rgb[~high] / 12.92

    r = linear[:, 0]
    g = linear[:, 1]
    b = linear[:, 2]

    l_val = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m_val = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s_val = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b

    l_root = np.cbrt(np.maximum(l_val, 0.0))
    m_root = np.cbrt(np.maximum(m_val, 0.0))
    s_root = np.cbrt(np.maximum(s_val, 0.0))

    out = np.empty_like(rgb)
    out[:, 0] = (
        0.2104542553 * l_root
        + 0.7936177850 * m_root
        - 0.0040720468 * s_root
    )
    out[:, 1] = (
        1.9779984951 * l_root
        - 2.4285922050 * m_root
        + 0.4505937099 * s_root
    )
    out[:, 2] = (
        0.0259040371 * l_root
        + 0.7827717662 * m_root
        - 0.8086757660 * s_root
    )
    return out

def extract_deterministic_palette(
    oklab_pixels: np.ndarray,
    target_count: int,
    seed: int = 42,
) -> np.ndarray:
    if not 2 <= target_count <= MAX_COLORS:
        raise ValueError(f"target_count must be 2..{MAX_COLORS}")
    pixels = np.asarray(oklab_pixels, dtype=np.float32)
    if pixels.ndim != 2 or pixels.shape[1] != 3:
        raise ValueError("oklab_pixels must have shape [N,3]")
    if len(pixels) < target_count:
        raise ValueError("not enough pixels")

    rng = np.random.RandomState(seed)
    if len(pixels) > 4000:
        pts = pixels[rng.choice(len(pixels), 4000, replace=False)]
    else:
        pts = pixels.copy()

    k = min(24, len(pts))
    centers = [pts[int(rng.randint(0, len(pts)))]]
    for _ in range(1, k):
        centers_arr = np.asarray(centers, dtype=np.float32)
        d2 = np.min(
            np.sum((pts[:, None, :] - centers_arr[None, :, :]) ** 2, axis=-1),
            axis=1,
        )
        total = float(d2.sum())
        probs = d2 / total if total > 1e-12 else np.full(len(pts), 1.0 / len(pts))
        centers.append(pts[int(rng.choice(len(pts), p=probs))])
    centers_arr = np.asarray(centers, dtype=np.float32)

    labels = np.zeros(len(pts), dtype=np.int32)
    for _ in range(15):
        distances = np.linalg.norm(
            pts[:, None, :] - centers_arr[None, :, :], axis=-1
        )
        labels = np.argmin(distances, axis=1)
        updated = centers_arr.copy()
        for i in range(k):
            members = pts[labels == i]
            if len(members):
                updated[i] = members.mean(axis=0)
        centers_arr = updated

    counts = np.bincount(labels, minlength=k)
    masses = counts.astype(np.float32) / float(len(pts))
    keep = masses >= 0.015
    if not keep.any():
        keep[int(np.argmax(masses))] = True

    candidate_centers = centers_arr[keep]
    candidate_masses = masses[keep]
    candidate_labels = np.where(keep)[0]

    merged_centers: list[np.ndarray] = []
    merged_masses: list[float] = []
    merged_pixels: list[np.ndarray] = []

    for idx in np.argsort(-candidate_masses):
        center = candidate_centers[idx]
        mass = float(candidate_masses[idx])
        subset = pts[labels == candidate_labels[idx]]
        if not merged_centers:
            merged_centers.append(center.copy())
            merged_masses.append(mass)
            merged_pixels.append(subset.copy())
            continue

        distances = np.asarray(
            [np.linalg.norm(center - existing) for existing in merged_centers]
        )
        closest = int(np.argmin(distances))
        if float(distances[closest]) < 0.04:
            old_mass = merged_masses[closest]
            new_mass = old_mass + mass
            merged_centers[closest] = (
                merged_centers[closest] * old_mass + center * mass
            ) / max(new_mass, 1e-12)
            merged_masses[closest] = new_mass
            merged_pixels[closest] = np.vstack([merged_pixels[closest], subset])
        else:
            merged_centers.append(center.copy())
            merged_masses.append(mass)
            merged_pixels.append(subset.copy())

    while len(merged_centers) < target_count:
        splittable = [
            i
            for i, subset in enumerate(merged_pixels)
            if len(subset) >= 10 and float(np.std(subset)) > 1e-3
        ]
        if not splittable:
            raise ValueError(
                f"insufficient real color modes for target_count={target_count}"
            )
        split_idx = max(splittable, key=lambda i: merged_masses[i])
        subset = merged_pixels[split_idx]

        c0 = subset[0]
        c1 = subset[int(np.argmax(np.linalg.norm(subset - c0, axis=1)))]
        sub_centers = np.stack([c0, c1]).astype(np.float32)
        sub_labels = np.zeros(len(subset), dtype=np.int32)

        for _ in range(8):
            d = np.linalg.norm(
                subset[:, None, :] - sub_centers[None, :, :], axis=-1
            )
            sub_labels = np.argmin(d, axis=1)
            if not np.any(sub_labels == 0) or not np.any(sub_labels == 1):
                raise ValueError("cannot split a monochromatic cluster")
            sub_centers[0] = subset[sub_labels == 0].mean(axis=0)
            sub_centers[1] = subset[sub_labels == 1].mean(axis=0)

        n0 = int(np.sum(sub_labels == 0))
        n1 = int(np.sum(sub_labels == 1))
        parent_mass = merged_masses[split_idx]
        merged_centers[split_idx] = sub_centers[0]
        merged_masses[split_idx] = parent_mass * n0 / (n0 + n1)
        merged_pixels[split_idx] = subset[sub_labels == 0]
        merged_centers.append(sub_centers[1])
        merged_masses.append(parent_mass * n1 / (n0 + n1))
        merged_pixels.append(subset[sub_labels == 1])

    cand = np.asarray(merged_centers, dtype=np.float32)
    mass = np.asarray(merged_masses, dtype=np.float32)

    selected = [int(np.argmax(mass))]
    while len(selected) < target_count:
        remaining = [i for i in range(len(cand)) if i not in selected]
        if not remaining:
            raise ValueError("not enough unique candidate colors")
        best_idx = remaining[0]
        best_score = -1.0
        for idx in remaining:
            min_dist = min(
                float(np.linalg.norm(cand[idx] - cand[chosen]))
                for chosen in selected
            )
            score = min_dist * float(mass[idx] ** 0.35)
            if score > best_score:
                best_score = score
                best_idx = idx
        selected.append(best_idx)

    chosen = cand[selected]
    return chosen[np.argsort(chosen[:, 0])]


def perceptual_hash64(image: Image.Image) -> str:
    gray = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    arr = np.asarray(gray, dtype=np.int16)
    bits = (arr[:, 1:] > arr[:, :-1]).reshape(-1)
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return f"{value:016x}"


def phash_distance(a: str, b: str) -> int:
    return (int(a, 16) ^ int(b, 16)).bit_count()


def decode_image_bytes(data: bytes) -> tuple[Image.Image, str]:
    with Image.open(io.BytesIO(data)) as img:
        img.load()
        fmt = (img.format or "JPEG").upper()
        rgb = img.convert("RGB")
    extension = {
        "JPEG": ".jpg",
        "JPG": ".jpg",
        "PNG": ".png",
        "WEBP": ".webp",
    }.get(fmt, ".img")
    return rgb, extension


def strict_openverse_license(item: dict[str, Any]) -> tuple[str, str] | None:
    code = str(item.get("license", "")).strip().lower()
    if code not in ALLOWED_OPENVERSE_LICENSES:
        return None
    url = str(item.get("license_url") or "").strip()
    if not url:
        return None
    normalized = url.lower().replace("http://", "https://")
    if not normalized.startswith("https://creativecommons.org/"):
        return None

    if code == "cc0":
        if "/publicdomain/zero/" not in normalized:
            return None
        return "CC0", url
    if code == "pdm":
        if "/publicdomain/mark/" not in normalized:
            return None
        return "PDM", url
    if code == "by":
        if "/licenses/by/" not in normalized:
            return None
        version = str(item.get("license_version") or "").strip()
        return f"CC BY {version}".strip(), url
    return None


def strict_openimages_license(url: str) -> tuple[str, str] | None:
    raw = str(url or "").strip()
    normalized = raw.lower().replace("http://", "https://")
    allowed = (
        ("https://creativecommons.org/licenses/by/2.0/", "CC BY 2.0"),
        ("https://creativecommons.org/publicdomain/zero/1.0/", "CC0 1.0"),
        ("https://creativecommons.org/publicdomain/mark/1.0/", "PDM 1.0"),
    )
    for prefix, label in allowed:
        if normalized.startswith(prefix):
            return label, raw
    return None


def metadata_required_fields() -> set[str]:
    return {
        "filename",
        "content_sha256",
        "perceptual_hash64",
        "concept_id",
        "category",
        "source_id",
        "source_type",
        "source_group_id",
        "image_id",
        "crop_coordinates",
        "license",
        "license_url",
        "provider",
        "foreign_identifier",
        "source_url",
        "landing_url",
        "creator",
        "title",
    }


def validate_cached_record(record: dict[str, Any], raw_dir: Path) -> dict[str, Any] | None:
    if not metadata_required_fields().issubset(record):
        return None
    path = raw_dir / str(record["filename"])
    if not path.is_file() or path.stat().st_size <= 0:
        return None
    if sha256_file(path) != record["content_sha256"]:
        return None
    try:
        with Image.open(path) as img:
            img.load()
            rgb = img.convert("RGB")
        if perceptual_hash64(rgb) != record["perceptual_hash64"]:
            return None
    except Exception:
        return None

    if record["source_group_id"] != f"content_{record['content_sha256']}":
        return None

    crop = record.get("crop_coordinates")
    if record.get("source_id") == "open_images":
        if (
            not isinstance(crop, list)
            or len(crop) != 4
            or not record.get("bbox_provenance")
            or not record.get("bbox_annotation_key")
            or not record.get("bbox_class_name")
            or not record.get("bbox_label_mid")
            or not record.get("bbox_source")
        ):
            return None

    copy = dict(record)
    copy["local_path"] = path
    return copy


def load_metadata_index(
    index_path: Path,
    raw_dir: Path,
) -> tuple[dict[str, dict[str, Any]], list[str], int]:
    if not index_path.is_file():
        return {}, [], 0
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        return {}, [], 0
    if payload.get("schema") != METADATA_INDEX_SCHEMA:
        return {}, [], 0

    records: dict[str, dict[str, Any]] = {}
    phashes: list[str] = []
    invalid = 0
    raw_records = payload.get("records", [])

    def _validate_one(raw: Any) -> tuple[bool, dict[str, Any] | None]:
        if not isinstance(raw, dict):
            return False, None
        v = validate_cached_record(raw, raw_dir)
        return (v is not None), v

    with ThreadPoolExecutor(
        max_workers=min(16, max(1, os.cpu_count() or 4))
    ) as executor:
        results = list(executor.map(_validate_one, raw_records))

    for is_valid, valid in results:
        if not is_valid or valid is None:
            invalid += 1
            continue
        sha = str(valid["content_sha256"])
        if sha in records:
            invalid += 1
            continue
        records[sha] = valid
        phashes.append(str(valid["perceptual_hash64"]))
    return records, phashes, invalid


def write_metadata_index(
    index_path: Path,
    records: dict[str, dict[str, Any]],
    *,
    disk: DiskBudget,
) -> None:
    with _CACHED_RECORDS_LOCK:
        snapshot = [dict(record) for record in records.values()]
    serializable: list[dict[str, Any]] = []
    for record in sorted(snapshot, key=lambda r: str(r["content_sha256"])):
        item = {
            key: value
            for key, value in record.items()
            if key
            not in {
                "local_path",
                "oklab_pixels",
                "color_prior",
                "processed_pil",
                "siglip_feature",
            }
        }
        if isinstance(item.get("crop_coordinates"), np.ndarray):
            item["crop_coordinates"] = item["crop_coordinates"].tolist()
        serializable.append(item)
    guarded_atomic_write_text(
        index_path,
        json.dumps(
            {"schema": METADATA_INDEX_SCHEMA, "records": serializable},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        disk=disk,
    )


def store_image_record(
    *,
    raw_dir: Path,
    prefix: str,
    image_bytes: bytes,
    record: dict[str, Any],
    seen_hashes: set[str],
    seen_phashes: list[str],
    disk: DiskBudget,
    stats: dict[str, int],
    seen_urls: set[str] | None = None,
    seen_image_ids: set[str] | None = None,
    dedup_lock: Any | None = None,
) -> dict[str, Any] | None:
    _lock = dedup_lock or _GLOBAL_DEDUP_LOCK
    src_id = str(record.get("source_id", "open_images"))

    disk.before_write(len(image_bytes))
    sha = sha256_bytes(image_bytes)
    with _lock:
        if sha in seen_hashes or sha in _RESERVED_HASHES:
            stats["exact_duplicates"] = stats.get("exact_duplicates", 0) + 1
            return None
        _RESERVED_HASHES.add(sha)

    phash: str | None = None
    tmp: Path | None = None
    try:
        t0_dec = time.time()
        try:
            rgb, extension = decode_image_bytes(image_bytes)
        except (OSError, ValueError, SyntaxError):
            with _lock:
                _RESERVED_HASHES.discard(sha)
                stats["invalid_images"] = stats.get("invalid_images", 0) + 1
            return None
        _FUNNEL.add_time(src_id, "seconds_decode", time.time() - t0_dec)
        _FUNNEL.record(src_id, "decode_success", 1)

        phash = perceptual_hash64(rgb)
        with _lock:
            all_phashes = seen_phashes + _RESERVED_PHASHES
            if any(
                phash_distance(phash, existing) <= NEAR_DUP_HAMMING
                for existing in all_phashes
            ):
                _RESERVED_HASHES.discard(sha)
                stats["near_duplicates"] = stats.get("near_duplicates", 0) + 1
                return None
            _RESERVED_PHASHES.append(phash)

        dest = raw_dir / f"{prefix}_{sha[:20]}{extension}"
        tmp = dest.with_name(f"{dest.name}.{threading.get_ident()}.tmp")
        tmp.write_bytes(image_bytes)
        try:
            with Image.open(tmp) as check:
                check.load()
                check.convert("RGB")
        except Exception:
            tmp.unlink(missing_ok=True)
            with _lock:
                _RESERVED_HASHES.discard(sha)
                if phash in _RESERVED_PHASHES:
                    _RESERVED_PHASHES.remove(phash)
                stats["invalid_images"] = stats.get("invalid_images", 0) + 1
            return None

        disk.commit_file(tmp, dest)
        with _lock:
            seen_hashes.add(sha)
            _RESERVED_HASHES.discard(sha)
            seen_phashes.append(phash)
            try:
                _RESERVED_PHASHES.remove(phash)
            except ValueError:
                pass
            if seen_urls is not None:
                if record.get("source_url"):
                    seen_urls.add(str(record["source_url"]))
                if record.get("downloaded_url"):
                    seen_urls.add(str(record["downloaded_url"]))
            if seen_image_ids is not None and record.get("image_id"):
                seen_image_ids.add(str(record["image_id"]))
    except Exception:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
        with _lock:
            _RESERVED_HASHES.discard(sha)
            if phash is not None:
                try:
                    _RESERVED_PHASHES.remove(phash)
                except ValueError:
                    pass
        raise

    out = dict(record)
    out.update(
        {
            "filename": dest.name,
            "local_path": dest,
            "content_sha256": sha,
            "perceptual_hash64": phash,
            "source_group_id": f"content_{sha}",
        }
    )
    return out


class OpenImagesBboxIndex:
    def __init__(self, *, cache_dir: Path, disk: DiskBudget) -> None:
        self.cache_dir = cache_dir
        self.disk = disk
        self.class_map: dict[str, str] = {}
        self.records_by_class: dict[str, list[dict[str, Any]]] = {}
        self._loaded = False

    def _ensure_file(self, filename: str, url: str) -> Path:
        path = self.cache_dir / filename
        if path.is_file() and path.stat().st_size > 0:
            return path
        if not self.disk.before_download():
            raise HardDiskLimitError(
                "target disk budget reached while acquiring Open Images metadata"
            )
        data = safe_http_get(
            url,
            timeout=60,
            max_retries=2,
            max_bytes=min(
                MAX_OPEN_IMAGES_METADATA_BYTES,
                self.disk.max_download_bytes(MAX_OPEN_IMAGES_METADATA_BYTES),
            ),
            pause_seconds=0.0,
        )
        if not data:
            raise RuntimeError(f"failed to download Open Images metadata: {url}")
        guarded_atomic_write_bytes(path, data, disk=self.disk)
        return path

    def load(self) -> None:
        if self._loaded:
            return
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        class_path = self._ensure_file(
            "oidv7-class-descriptions-boxable.csv",
            OPEN_IMAGES_CLASS_URL,
        )
        bbox_path = self._ensure_file(
            "validation-annotations-bbox.csv",
            OPEN_IMAGES_VALIDATION_BBOX_URL,
        )
        image_meta_path = self._ensure_file(
            "validation-images-with-rotation.csv",
            OPEN_IMAGES_VALIDATION_META_URL,
        )

        with class_path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.reader(handle):
                if len(row) >= 2:
                    self.class_map[normalize_text(row[1])] = row[0].strip()

        desired_names = {
            normalize_text(name)
            for candidates in CONCEPT_TO_OPENIMAGES_CLASSES.values()
            for name in candidates
        }
        wanted_mid_to_name = {
            mid: name
            for name, mid in self.class_map.items()
            if name in desired_names
        }

        boxes_by_image: dict[str, list[dict[str, Any]]] = {}
        with bbox_path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                mid = str(row.get("LabelName") or "")
                if mid not in wanted_mid_to_name:
                    continue
                if str(row.get("Confidence") or "") not in {"1", "1.0"}:
                    continue
                if str(row.get("IsGroupOf") or "0") != "0":
                    continue
                if str(row.get("IsDepiction") or "0") != "0":
                    continue
                if str(row.get("IsInside") or "0") != "0":
                    continue
                if str(row.get("IsTruncated") or "0") != "0":
                    continue
                if str(row.get("IsOccluded") or "0") != "0":
                    continue

                try:
                    x0 = float(row["XMin"])
                    x1 = float(row["XMax"])
                    y0 = float(row["YMin"])
                    y1 = float(row["YMax"])
                except (KeyError, TypeError, ValueError):
                    continue
                if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
                    continue
                width, height = x1 - x0, y1 - y0
                area = width * height
                if width < 0.10 or height < 0.10 or area < 0.025 or area > 0.85:
                    continue

                image_id = str(row.get("ImageID") or "").strip()
                source = str(row.get("Source") or "").strip()
                if not image_id or source not in {"xclick", "activemil"}:
                    continue

                annotation_material = "|".join(
                    [
                        image_id,
                        mid,
                        source,
                        f"{x0:.6f}",
                        f"{y0:.6f}",
                        f"{x1:.6f}",
                        f"{y1:.6f}",
                    ]
                )
                annotation_key = hashlib.sha256(
                    annotation_material.encode("utf-8")
                ).hexdigest()

                boxes_by_image.setdefault(image_id, []).append(
                    {
                        "bbox_label_mid": mid,
                        "bbox_class_name": wanted_mid_to_name[mid],
                        "bbox_source": source,
                        "bbox_annotation_key": annotation_key,
                        "crop_coordinates": [x0, y0, x1, y1],
                        "bbox_provenance": (
                            f"{OPEN_IMAGES_RELEASE}|validation|"
                            f"{OPEN_IMAGES_VALIDATION_BBOX_URL}|"
                            f"annotation_sha256={annotation_key}"
                        ),
                    }
                )

        records_by_class: dict[str, list[dict[str, Any]]] = {}
        with image_meta_path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                image_id = str(row.get("ImageID") or "").strip()
                if image_id not in boxes_by_image:
                    continue

                rotation = str(row.get("Rotation") or "").strip().lower()
                if rotation not in {"0", "0.0"}:
                    continue

                license_info = strict_openimages_license(str(row.get("License") or ""))
                if license_info is None:
                    continue
                license_name, license_url = license_info

                original_url = str(row.get("OriginalURL") or "").strip()
                thumbnail_url = str(row.get("Thumbnail300KURL") or "").strip()
                source_url = original_url or thumbnail_url
                if not source_url.startswith(("http://", "https://")):
                    continue

                landing = str(row.get("OriginalLandingURL") or "").strip()
                if not landing:
                    landing = (
                        "https://openimages.org/web/detail?image_id="
                        + urllib.parse.quote(image_id)
                    )

                for bbox in boxes_by_image[image_id]:
                    class_name = bbox["bbox_class_name"]
                    record = {
                        "source_id": "open_images",
                        "source_type": "real_world",
                        "image_id": f"openimages_{image_id}",
                        "foreign_identifier": image_id,
                        "provider": "openimages",
                        "source_url": source_url,
                        "source_url_fallback": thumbnail_url
                        if thumbnail_url and thumbnail_url != source_url
                        else "",
                        "landing_url": landing,
                        "creator": str(row.get("Author") or "Unknown"),
                        "title": str(row.get("Title") or class_name),
                        "license": license_name,
                        "license_url": license_url,
                        "open_images_release": OPEN_IMAGES_RELEASE,
                        "open_images_subset": "validation",
                        "open_images_rotation": 0,
                        "open_images_image_metadata_url": OPEN_IMAGES_VALIDATION_META_URL,
                        "source_dataset_release": OPEN_IMAGES_RELEASE,
                        "source_annotation_url": OPEN_IMAGES_VALIDATION_BBOX_URL,
                        "source_image_metadata_url": OPEN_IMAGES_VALIDATION_META_URL,
                        **bbox,
                    }
                    records_by_class.setdefault(class_name, []).append(record)

        for class_name, records in records_by_class.items():
            records.sort(
                key=lambda r: hashlib.sha256(
                    str(r["image_id"]).encode("utf-8")
                ).hexdigest()
            )
        self.records_by_class = records_by_class
        self._loaded = True

        print(
            "Open Images bbox index loaded: "
            f"{sum(len(v) for v in self.records_by_class.values())} "
            f"records across {len(self.records_by_class)} mapped classes."
        )

    def get_records(
        self, concept_id: str, max_count: int, offset: int = 0
    ) -> list[dict[str, Any]]:
        self.load()
        names = CONCEPT_TO_OPENIMAGES_CLASSES.get(concept_id, ())
        found: list[dict[str, Any]] = []
        used_images: set[str] = set()
        for name in names:
            normalized = normalize_text(name)
            if normalized not in self.class_map:
                continue
            for record in self.records_by_class.get(normalized, []):
                if record["image_id"] in used_images:
                    continue
                found.append(dict(record))
                used_images.add(record["image_id"])
        return CandidateBatch(found[offset : offset + max_count], consumed=True)


def _api_key_lock(provider: str, key: tuple[Any, ...]) -> threading.Lock:
    with _API_CACHE_LOCK:
        return _API_KEY_LOCKS.setdefault((provider, key), threading.Lock())


def _met_candidates_impl(
    query: str,
    limit: int = 36,
    offset: int = 0,
    concept: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    norm_query = query.strip().lower()
    concept_id = str((concept or {}).get("concept_id", ""))
    cache_key = (norm_query, limit, offset, concept_id)
    with _API_CACHE_LOCK:
        if cache_key in _MET_QUERY_CACHE:
            return CandidateBatch(
                (dict(record) for record in _MET_QUERY_CACHE[cache_key]),
                consumed=True,
            )
        all_ids = _MET_SEARCH_CACHE.get(norm_query)

    t0 = time.time()
    if all_ids is None:
        search_url = (
            "https://collectionapi.metmuseum.org/public/collection/v1/search"
            f"?q={urllib.parse.quote(query)}&hasImages=true"
        )
        search = fetch_json(search_url, timeout=10, max_retries=1)
        if search is None:
            _FUNNEL.add_time("met", "seconds_metadata", time.time() - t0)
            return CandidateBatch(consumed=False)
        all_ids = list(search.get("objectIDs") or [])
        with _API_CACHE_LOCK:
            _MET_SEARCH_CACHE[norm_query] = all_ids

    object_ids = all_ids[offset : offset + limit]
    if not object_ids:
        _FUNNEL.add_time("met", "seconds_metadata", time.time() - t0)
        return []

    def load_object(object_id: Any) -> tuple[Any, dict[str, Any] | None]:
        return object_id, fetch_json(
            "https://collectionapi.metmuseum.org/public/collection/v1/objects/"
            + str(object_id),
            timeout=8,
            max_retries=0,
        )

    with ThreadPoolExecutor(
        max_workers=min(_METADATA_WORKERS, max(1, len(object_ids)))
    ) as executor:
        objects = list(executor.map(load_object, object_ids))
    consumed = all(obj is not None for _, obj in objects)

    _FUNNEL.add_time("met", "seconds_metadata", time.time() - t0)

    concept_kw: set[str] = set()
    if concept:
        all_text = (
            str(concept.get("retrieval_query", ""))
            + " "
            + " ".join(concept.get("phrasings_en", []))
        ).lower()
        words = re.findall(r"\b[a-zA-Z]{3,}\b", all_text)
        concept_kw = set(words) - {
            "with", "and", "the", "for", "from", "into", "over", "under", "after",
            "through", "texture", "surface", "specimen", "background", "style",
            "rustic", "fine", "light", "color", "painting", "drawing", "photo",
            "image",
        }

    out: list[dict[str, Any]] = []
    for object_id, obj in objects:
        if not obj or not obj.get("isPublicDomain"):
            continue
        image_url = str(obj.get("primaryImageSmall") or obj.get("primaryImage") or "")
        if not image_url:
            continue

        classification = str(obj.get("classification") or "")
        obj_name = str(obj.get("objectName") or "")
        title = str(obj.get("title") or "")
        tags = [
            str(t.get("term", ""))
            for t in (obj.get("tags") or [])
            if isinstance(t, dict)
        ]
        meta_blob = f"{title} {classification} {obj_name} {' '.join(tags)}".lower()

        if (
            classification.lower()
            in ("coins", "medals", "armor", "arms and armor", "fragments", "ceramics-pottery")
            and concept_kw
        ):
            if not any(kw in meta_blob for kw in concept_kw):
                continue

        out.append(
            {
                "source_id": "met",
                "source_type": "artwork",
                "image_id": f"met_{object_id}",
                "foreign_identifier": str(object_id),
                "provider": "metmuseum.org",
                "source_url": image_url,
                "landing_url": str(
                    obj.get("objectURL")
                    or f"https://www.metmuseum.org/art/collection/search/{object_id}"
                ),
                "creator": str(obj.get("artistDisplayName") or "Unknown"),
                "title": title,
                "object_name": obj_name,
                "classification": classification,
                "tags": tags,
                "license": "CC0 1.0",
                "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
                "crop_coordinates": None,
                "bbox_provenance": "",
                "bbox_annotation_key": "",
                "bbox_class_name": "",
                "bbox_label_mid": "",
                "bbox_source": "",
            }
        )
    if concept_kw:
        for record in out:
            metadata_blob = " ".join([
                str(record.get("title", "")),
                str(record.get("object_name", "")),
                str(record.get("classification", "")),
                " ".join(record.get("tags", [])),
            ]).lower()
            metadata_terms = set(re.findall(r"\b[a-zA-Z]{3,}\b", metadata_blob))
            record["metadata_relevance_matches"] = len(concept_kw & metadata_terms)
        out.sort(
            key=lambda record: int(record.get("metadata_relevance_matches", 0)),
            reverse=True,
        )
    with _API_CACHE_LOCK:
        _MET_QUERY_CACHE[cache_key] = out
    _FUNNEL.record("met", "metadata_candidates", len(out))
    return CandidateBatch((dict(record) for record in out), consumed=consumed)


def _artic_candidates_impl(
    query: str,
    limit: int = 24,
    page: int = 1,
    concept: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    norm_query = query.strip().lower()
    cache_key = (norm_query, limit, page)
    with _API_CACHE_LOCK:
        if cache_key in _ARTIC_QUERY_CACHE:
            return CandidateBatch(
                (dict(record) for record in _ARTIC_QUERY_CACHE[cache_key]),
                consumed=True,
            )

    t0 = time.time()
    url = (
        "https://api.artic.edu/api/v1/artworks/search"
        f"?q={urllib.parse.quote(query)}"
        "&query[term][is_public_domain]=true"
        "&fields=id,title,artist_display,image_id,is_public_domain"
        f"&limit={int(limit)}"
        f"&page={int(page)}"
    )
    payload = fetch_json(url, timeout=10, max_retries=1)
    _FUNNEL.add_time("artic", "seconds_metadata", time.time() - t0)

    if payload is None:
        return CandidateBatch(consumed=False)
    iiif_base = str(
        payload.get("config", {}).get("iiif_url")
        or "https://www.artic.edu/iiif/2"
    ).rstrip("/")
    out: list[dict[str, Any]] = []
    for item in payload.get("data", []):
        if not item.get("is_public_domain"):
            continue
        image_id = item.get("image_id")
        object_id = item.get("id")
        if not image_id or object_id is None:
            continue
        out.append(
            {
                "source_id": "artic",
                "source_type": "artwork",
                "image_id": f"artic_{object_id}",
                "foreign_identifier": str(object_id),
                "provider": "artic.edu",
                "source_url": (
                    f"{iiif_base}/{image_id}/full/600,/0/default.jpg"
                ),
                "landing_url": f"https://www.artic.edu/artworks/{object_id}",
                "creator": str(item.get("artist_display") or "Unknown"),
                "title": str(item.get("title") or ""),
                "license": "CC0 1.0",
                "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
                "crop_coordinates": None,
                "bbox_provenance": "",
                "bbox_annotation_key": "",
                "bbox_class_name": "",
                "bbox_label_mid": "",
                "bbox_source": "",
            }
        )
    with _API_CACHE_LOCK:
        _ARTIC_QUERY_CACHE[cache_key] = out
    _FUNNEL.record("artic", "metadata_candidates", len(out))
    return CandidateBatch((dict(record) for record in out), consumed=True)


def _openverse_candidates_impl(
    query: str,
    limit: int = 24,
    page: int = 1,
    concept: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    global _OPENVERSE_COOLDOWN_UNTIL, _OPENVERSE_LAST_SEARCH_TIME, _OPENVERSE_UNAVAILABLE
    with _OPENVERSE_LOCK:
        if _OPENVERSE_UNAVAILABLE:
            return CandidateBatch(consumed=False)
        norm_query = query.strip().lower()
        cache_key = (norm_query, limit, page)
        if cache_key in _OPENVERSE_QUERY_CACHE:
            return CandidateBatch(
                (dict(x) for x in _OPENVERSE_QUERY_CACHE[cache_key]),
                consumed=True,
            )
        now = time.time()
        if now < _OPENVERSE_COOLDOWN_UNTIL:
            remaining = int(_OPENVERSE_COOLDOWN_UNTIL - now)
            print(f"Openverse in cooldown ({remaining}s remaining), skipping query: {query}")
            return CandidateBatch(consumed=False)
        scheduled = max(now, _OPENVERSE_LAST_SEARCH_TIME + _OPENVERSE_SEARCH_MIN_INTERVAL)
        wait_seconds = scheduled - now
        _OPENVERSE_LAST_SEARCH_TIME = scheduled
    if wait_seconds > 0:
        time.sleep(wait_seconds)

    t0 = time.time()
    url = (
        "https://api.openverse.org/v1/images/"
        f"?q={urllib.parse.quote(query)}"
        "&license=pdm,cc0,by"
        f"&page_size={min(80, int(limit))}"
        f"&page={int(page)}"
    )
    payload = fetch_json(url, timeout=20)
    _FUNNEL.add_time("openverse", "seconds_metadata", time.time() - t0)

    if payload is None:
        return CandidateBatch(consumed=False)
    out: list[dict[str, Any]] = []
    for item in payload.get("results", []):
        if not isinstance(item, dict):
            continue
        license_info = strict_openverse_license(item)
        if license_info is None:
            continue
        license_name, license_url = license_info
        image_id = str(item.get("id") or "").strip()
        image_url = str(item.get("url") or "").strip()
        if not image_id or not image_url.startswith(("http://", "https://")):
            continue

        category = str(item.get("category") or "").strip().lower()
        if category == "photograph":
            source_type = "real_world"
        elif category in {"illustration", "digitized_artwork", "drawing"}:
            source_type = "artwork"
        else:
            source_type = "unknown"

        landing_url = str(
            item.get("foreign_landing_url") or item.get("detail_url") or ""
        ).strip()
        if not landing_url.startswith(("http://", "https://")):
            continue

        out.append(
            {
                "source_id": "openverse",
                "source_type": source_type,
                "image_id": f"openverse_{image_id}",
                "foreign_identifier": str(
                    item.get("foreign_identifier") or image_id
                ),
                "provider": str(item.get("provider") or "openverse"),
                "source_url": image_url,
                "landing_url": landing_url,
                "creator": str(item.get("creator") or "Unknown"),
                "title": str(item.get("title") or ""),
                "license": license_name,
                "license_url": license_url,
                "crop_coordinates": None,
                "bbox_provenance": "",
                "bbox_annotation_key": "",
                "bbox_class_name": "",
                "bbox_label_mid": "",
                "bbox_source": "",
            }
        )
    res = out[:limit]
    with _OPENVERSE_LOCK:
        _OPENVERSE_QUERY_CACHE[cache_key] = res
    _FUNNEL.record("openverse", "metadata_candidates", len(res))
    return CandidateBatch(res, consumed=True)


def met_candidates(
    query: str, limit: int = 36, offset: int = 0,
    concept: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    key = (
        query.strip().lower(), limit, offset,
        str((concept or {}).get("concept_id", "")),
    )
    with _api_key_lock("met", key):
        return _met_candidates_impl(query, limit, offset, concept)


def artic_candidates(
    query: str, limit: int = 24, page: int = 1,
    concept: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    key = (query.strip().lower(), limit, page)
    with _api_key_lock("artic", key):
        return _artic_candidates_impl(query, limit, page, concept)


def openverse_candidates(
    query: str, limit: int = 24, page: int = 1,
    concept: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    key = (query.strip().lower(), limit, page)
    with _api_key_lock("openverse", key):
        return _openverse_candidates_impl(query, limit, page, concept)


def fetch_candidate_image(
    candidate: dict[str, Any],
    disk: DiskBudget,
) -> tuple[dict[str, Any], bytes, str] | None:
    """Fetch one candidate without mutating shared deduplication state."""
    if not disk.before_download():
        return None
    urls = [str(candidate["source_url"])]
    fallback = str(candidate.get("source_url_fallback") or "")
    if fallback:
        urls.append(fallback)
    headers = None
    if str(candidate.get("source_id")) == "artic":
        headers = {
            "User-Agent": "Mozilla/5.0 PaletteBrain-C11/1.0",
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            "Referer": "https://www.artic.edu/",
        }
    provider = str(candidate.get("source_id") or "open_images")
    route_key = str(candidate.get("acquisition_route_key") or "")
    for url in urls:
        if not _provider_viable(provider):
            return None
        _FUNNEL.record(provider, "download_attempted", 1)
        _record_route(route_key, "attempted")
        started = time.time()
        data = safe_http_get(
            url,
            timeout=15,
            max_retries=1,
            max_bytes=disk.max_download_bytes(MAX_SINGLE_IMAGE_BYTES),
            headers=headers,
        )
        duration = time.time() - started
        _FUNNEL.add_time(provider, "seconds_network", duration)
        _record_route(route_key, "networkSeconds", duration)
        if data:
            _FUNNEL.record(provider, "download_success", 1)
            _record_route(route_key, "downloaded")
            return candidate, data, url
    return None


def acquire_for_concept(
    *,
    concept: dict[str, Any],
    raw_dir: Path,
    max_count: int,
    allowed_sources: tuple[str, ...],
    seen_hashes: set[str],
    seen_phashes: list[str],
    disk: DiskBudget,
    stats: dict[str, int],
    open_images: OpenImagesBboxIndex,
    seen_urls: set[str] | None = None,
    seen_image_ids: set[str] | None = None,
    dedup_lock: Any | None = None,
    max_training_queries: int = 3,
) -> list[dict[str, Any]]:
    if max_count <= 0:
        return []
    if max_training_queries < 1:
        raise ValueError("max_training_queries must be positive")

    crop_required = bool(concept.get("crop_required", False))
    cid = str(concept["concept_id"])

    raw_queries = [str(concept["retrieval_query"])]
    for phrasing in concept.get("phrasings_en", []):
        p_str = str(phrasing).strip()
        if p_str and p_str not in raw_queries:
            raw_queries.append(p_str)
        if len(raw_queries) >= max_training_queries:
            break

    if crop_required:
        if "open_images" not in allowed_sources:
            return []
        ordered_sources = ["open_images"]
    else:
        pref = [
            s
            for s in concept.get("source_preference", ["artic", "met", "openverse"])
            if s in allowed_sources and s in ("artic", "met", "openverse")
        ]
        ordered_sources = (
            pref if pref else [s for s in allowed_sources if s in ("artic", "met", "openverse")]
        )

    with _ACQUISITION_STATE_LOCK:
        concept_cursors = _ACQUISITION_STATE.setdefault("conceptCursors", {}).setdefault(
            cid, {
                "stage": 0,
                "offsets": {"met": 0, "artic": 1, "openverse": 1, "open_images": 0},
            }
        )
        offsets = concept_cursors.setdefault(
            "offsets", {"met": 0, "artic": 1, "openverse": 1, "open_images": 0}
        )
        legacy_offsets = _ACQUISITION_STATE.setdefault("conceptOffsets", {}).setdefault(
            cid, offsets
        )
        for k, v in legacy_offsets.items():
            if k not in offsets:
                offsets[k] = v

    stage_pairs: list[tuple[str, str]] = []
    for src in ordered_sources:
        for q in raw_queries:
            stage_pairs.append((src, q))
    stage_pairs.sort(
        key=lambda pair: _route_priority(_route_key(cid, pair[0], pair[1])),
        reverse=True,
    )

    candidates: list[dict[str, Any]] = []
    start_stage = int(concept_cursors.get("stage", 0))

    for step in range(len(stage_pairs)):
        actual_idx = (start_stage + step) % len(stage_pairs)
        src, query = stage_pairs[actual_idx]
        route_key = _route_key(cid, src, query)
        if not _provider_viable(src) or _route_priority(route_key) <= 0:
            continue

        with _ACQUISITION_STATE_LOCK:
            route_offsets = _ACQUISITION_STATE.setdefault("routeOffsets", {})
            route_offset = route_offsets.setdefault(
                route_key,
                1 if src in {"artic", "openverse"} else 0,
            )

        batch_candidates: list[dict[str, Any]] = []
        if src == "open_images":
            cur_off = offsets.get("open_images", 0)
            limit_oi = max(max_count * 4, 20)
            records = open_images.get_records(cid, max_count=limit_oi, offset=cur_off)
            if getattr(records, "consumed", True):
                offsets["open_images"] = cur_off + len(records)
                legacy_offsets["open_images"] = offsets["open_images"]
            if records:
                batch_candidates = records
        elif src == "artic":
            cur_page = int(route_offset)
            limit_art = min(max(max_count, 8), 12)
            records = artic_candidates(query, limit=limit_art, page=cur_page, concept=concept)
            if getattr(records, "consumed", False):
                with _ACQUISITION_STATE_LOCK:
                    route_offsets[route_key] = cur_page + 1
                    offsets["artic"] = max(
                        int(offsets.get("artic", 1)), cur_page + 1
                    )
                    legacy_offsets["artic"] = offsets["artic"]
            if records:
                batch_candidates = records
        elif src == "met":
            cur_off = int(route_offset)
            limit_met = min(max(max_count, 8), 12)
            records = met_candidates(query, limit=limit_met, offset=cur_off, concept=concept)
            if getattr(records, "consumed", False):
                with _ACQUISITION_STATE_LOCK:
                    route_offsets[route_key] = cur_off + limit_met
                    offsets["met"] = max(
                        int(offsets.get("met", 0)), cur_off + limit_met
                    )
                    legacy_offsets["met"] = offsets["met"]
            if records:
                batch_candidates = records
        elif src == "openverse":
            cur_page = int(route_offset)
            limit_ov = min(max(max_count, 8), 12)
            records = openverse_candidates(query, limit=limit_ov, page=cur_page, concept=concept)
            if getattr(records, "consumed", False):
                with _ACQUISITION_STATE_LOCK:
                    route_offsets[route_key] = cur_page + 1
                    offsets["openverse"] = max(
                        int(offsets.get("openverse", 1)), cur_page + 1
                    )
                    legacy_offsets["openverse"] = offsets["openverse"]
            if records:
                batch_candidates = records

        _record_route(route_key, "batches", 1)
        if getattr(records, "consumed", False) and not batch_candidates:
            _record_route(route_key, "emptyBatches", 1)
        _record_route(route_key, "metadata", len(batch_candidates))
        for cand in batch_candidates:
            cand["acquisition_route_key"] = route_key
            cand["acquisition_query"] = query
            img_id = str(cand.get("image_id") or "")
            src_url = str(cand.get("source_url") or "")
            fb_url = str(cand.get("source_url_fallback") or "")
            if seen_image_ids is not None and img_id and img_id in seen_image_ids:
                _FUNNEL.record(src, "already_seen_skipped", 1)
                continue
            if seen_urls is not None and src_url and src_url in seen_urls:
                _FUNNEL.record(src, "already_seen_skipped", 1)
                continue
            if seen_urls is not None and fb_url and fb_url in seen_urls:
                _FUNNEL.record(src, "already_seen_skipped", 1)
                continue
            candidates.append(cand)

        if len(candidates) >= max_count * 2:
            break
        if not batch_candidates:
            concept_cursors["stage"] = (actual_idx + 1) % len(stage_pairs)

    if not candidates:
        return CandidateBatch(consumed=True)

    candidates = candidates[:max_count]

    stored_records: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(len(candidates), _DOWNLOAD_WORKERS)) as executor:
        future_to_cand = {
            executor.submit(fetch_candidate_image, cand, disk): cand
            for cand in candidates
        }
        for future in concurrent.futures.as_completed(future_to_cand):
            if len(stored_records) >= max_count:
                for f in future_to_cand:
                    f.cancel()
                break
            try:
                payload = future.result()
            except (OSError, ValueError, urllib.error.URLError):
                continue
            if payload is None:
                continue
            cand, data, downloaded_url = payload
            rec = dict(cand)
            rec.update(
                {
                    "concept_id": concept["concept_id"],
                    "category": concept["category"],
                    "downloaded_url": downloaded_url,
                }
            )
            prefix = {
                "met": "met",
                "artic": "artic",
                "openverse": "ov",
                "open_images": "oi",
            }.get(str(cand["source_id"]), "src")

            stored = store_image_record(
                raw_dir=raw_dir,
                prefix=prefix,
                image_bytes=data,
                record=rec,
                seen_hashes=seen_hashes,
                seen_phashes=seen_phashes,
                disk=disk,
                stats=stats,
                seen_urls=seen_urls,
                seen_image_ids=seen_image_ids,
                dedup_lock=dedup_lock,
            )
            if stored is not None:
                stored_records.append(stored)

    return stored_records


def prepare_relevance_image(
    path: Path,
    *,
    crop_required: bool,
    whole_frame_valid: bool,
    meta_crop: list[float] | tuple[float, float, float, float] | None,
) -> tuple[Image.Image, np.ndarray, float] | None:
    """Decode, bound, crop, and validate only what SigLIP scoring needs."""
    try:
        with Image.open(path) as img:
            img.load()
            rgb = img.convert("RGB")

        max_dim = max(rgb.size)
        if max_dim > 600:
            scale = 600.0 / max_dim
            rgb = rgb.resize(
                (
                    max(1, round(rgb.width * scale)),
                    max(1, round(rgb.height * scale)),
                ),
                Image.Resampling.BILINEAR,
            )

        width, height = rgb.size
        if crop_required:
            if meta_crop is None or len(meta_crop) != 4:
                return None
            x0, y0, x1, y1 = (float(v) for v in meta_crop)
            if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
                return None
            px0 = max(0, min(width, int(math.floor(x0 * width))))
            py0 = max(0, min(height, int(math.floor(y0 * height))))
            px1 = max(0, min(width, int(math.ceil(x1 * width))))
            py1 = max(0, min(height, int(math.ceil(y1 * height))))
            if px1 <= px0 or py1 <= py0:
                return None
            rgb = rgb.crop((px0, py0, px1, py1))
            crop = np.asarray([x0, y0, x1, y1], dtype=np.float64)
            mask_fraction = ((px1 - px0) * (py1 - py0)) / float(width * height)
        elif whole_frame_valid:
            crop = np.asarray([0.0, 0.0, 1.0, 1.0], dtype=np.float64)
            mask_fraction = 1.0
        else:
            return None

    except (OSError, Image.DecompressionBombError):
        return None

    pixels = np.asarray(rgb, dtype=np.uint8).reshape(-1, 3)
    if len(pixels) < 100 or float(np.std(pixels)) < 1e-4:
        return None
    return rgb, crop, float(mask_fraction)


def extract_final_color_features(rgb: Image.Image) -> tuple[np.ndarray, np.ndarray]:
    """Compute final-only OKLab pixels and color prior for a relevance survivor."""
    pixels = np.asarray(rgb, dtype=np.float32).reshape(-1, 3) / 255.0
    oklab = rgb_to_oklab_array(pixels)
    color_prior = palette_or_pixels_to_oklch_histogram(oklab)
    return oklab, color_prior


def process_image(
    path: Path,
    *,
    crop_required: bool,
    whole_frame_valid: bool,
    meta_crop: list[float] | tuple[float, float, float, float] | None,
) -> tuple[np.ndarray, np.ndarray, Image.Image, np.ndarray, float] | None:
    """Decode an image and compute final color features.

    Expected corrupt-input failures return ``None``. Programming failures in
    color conversion or feature extraction propagate and cannot poison caches.
    """
    prepared = prepare_relevance_image(
        path,
        crop_required=crop_required,
        whole_frame_valid=whole_frame_valid,
        meta_crop=meta_crop,
    )
    if prepared is None:
        return None
    rgb, crop, mask_fraction = prepared
    oklab, color_prior = extract_final_color_features(rgb)
    return oklab, color_prior, rgb, crop, mask_fraction


def resolve_device(device: str) -> torch.device:
    if device == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    resolved = torch.device(device)
    if resolved.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    return resolved


def siglip_feature_tensor(value: Any) -> torch.Tensor:
    if isinstance(value, torch.Tensor):
        return value
    for attr in ("pooler_output", "image_embeds", "text_embeds"):
        maybe = getattr(value, attr, None)
        if isinstance(maybe, torch.Tensor):
            return maybe
    raise TypeError(f"unsupported SigLIP feature return type: {type(value)!r}")


def encode_siglip_images(
    model: Any,
    processor: Any,
    images: list[Image.Image],
    device: torch.device,
    batch_size: int = 16,
) -> np.ndarray:
    chunks: list[np.ndarray] = []
    for start in range(0, len(images), batch_size):
        # SigLIP's pinned processor owns resize/rescale/normalization.  Supplying
        # explicit RGB PIL images prevents alpha/grayscale and BGR array inputs
        # from silently changing the model contract.
        batch = [image.convert("RGB") for image in images[start : start + batch_size]]
        inputs = processor(images=batch, return_tensors="pt")
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.inference_mode():
            features = siglip_feature_tensor(model.get_image_features(**inputs))
            features = F.normalize(features, p=2, dim=-1)
        chunks.append(features.float().cpu().numpy())
    return np.concatenate(chunks, axis=0).astype(np.float32)


def encode_siglip_texts(
    model: Any,
    tokenizer: Any,
    texts: list[str],
    device: torch.device,
    batch_size: int = 32,
) -> np.ndarray:
    chunks: list[np.ndarray] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        inputs = tokenizer(
            batch,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.inference_mode():
            features = siglip_feature_tensor(model.get_text_features(**inputs))
            features = F.normalize(features, p=2, dim=-1)
        chunks.append(features.float().cpu().numpy())
    return np.concatenate(chunks, axis=0).astype(np.float32)


def choose_calibration_threshold(
    positive: np.ndarray,
    negative: np.ndarray,
    *,
    minimum_tpr: float = 0.85,
) -> tuple[float, dict[str, float]]:
    values = np.unique(np.concatenate([positive, negative]))
    if len(values) < 2:
        raise RuntimeError("SigLIP calibration scores have no separation")
    candidates = [
        float((values[i] + values[i + 1]) / 2.0)
        for i in range(len(values) - 1)
    ]
    best: tuple[float, float, float, float, float] | None = None
    for threshold in candidates:
        tpr = float(np.mean(positive >= threshold))
        fpr = float(np.mean(negative >= threshold))
        balanced = 0.5 * (tpr + (1.0 - fpr))
        precision_denominator = int(np.sum(positive >= threshold)) + int(np.sum(negative >= threshold))
        precision = float(np.sum(positive >= threshold) / precision_denominator) if precision_denominator else 0.0
        f1 = 2.0 * precision * tpr / (precision + tpr) if precision + tpr else 0.0
        youden_j = tpr - fpr
        # Enforce recall first, then maximize Youden's J with F1 as a stable
        # tie-breaker.  This avoids the previous high-threshold/low-TPR optimum.
        candidate = (float(tpr >= minimum_tpr), youden_j, f1, -fpr, threshold)
        if best is None or candidate > best:
            best = candidate
    assert best is not None
    _, _, _, _, threshold = best
    tpr = float(np.mean(positive >= threshold))
    fpr = float(np.mean(negative >= threshold))
    balanced = 0.5 * (tpr + (1.0 - fpr))
    precision_denominator = int(np.sum(positive >= threshold)) + int(np.sum(negative >= threshold))
    precision = float(np.sum(positive >= threshold) / precision_denominator) if precision_denominator else 0.0
    f1 = 2.0 * precision * tpr / (precision + tpr) if precision + tpr else 0.0
    metrics = {
        "balancedAccuracy": balanced,
        "truePositiveRate": tpr,
        "falsePositiveRate": fpr,
        "youdenJ": tpr - fpr,
        "f1": f1,
        "positiveMean": float(np.mean(positive)),
        "positiveMedian": float(np.median(positive)),
        "positiveMin": float(np.min(positive)),
        "positiveMax": float(np.max(positive)),
        "negativeMean": float(np.mean(negative)),
        "negativeMedian": float(np.median(negative)),
        "negativeMin": float(np.min(negative)),
        "negativeMax": float(np.max(negative)),
        "meanSeparation": float(np.mean(positive) - np.mean(negative)),
    }
    return threshold, metrics


def validate_siglip_preprocessing(processor: Any) -> dict[str, Any]:
    """Prove the pinned processor produces normalized RGB in [-1, 1]."""
    red = Image.new("RGB", (224, 224), (255, 0, 0))
    values = processor(images=[red], return_tensors="pt")["pixel_values"]
    if values.ndim != 4 or values.shape[1] != 3:
        raise RuntimeError(f"SigLIP processor emitted invalid pixel shape {tuple(values.shape)}")
    minimum = float(values.min())
    maximum = float(values.max())
    channel_means = values.mean(dim=(0, 2, 3)).tolist()
    if minimum < -1.001 or maximum > 1.001:
        raise RuntimeError(f"SigLIP processor scaling is outside [-1,1]: {minimum}, {maximum}")
    if not (channel_means[0] > 0.9 and channel_means[1] < -0.9 and channel_means[2] < -0.9):
        raise RuntimeError(f"SigLIP processor RGB channel order is invalid: {channel_means}")
    return {"range": [minimum, maximum], "solidRedChannelMeans": channel_means}


def siglip_relevance_prompt(record: dict[str, Any], concept: dict[str, Any]) -> str:
    """Align text with the visual evidence actually verified by each source."""
    bbox_class = str(record.get("bbox_class_name") or "").strip().lower()
    if record.get("source_id") == "open_images" and bbox_class:
        article = "an" if bbox_class[:1] in "aeiou" else "a"
        # Open Images supervision is an object-centred bounding-box crop, not a
        # whole-scene retrieval result.  State that geometry in the text side.
        return f"a centered photo of {article} {bbox_class}"
    query = str(concept["retrieval_query"]).strip()
    if str(record.get("source_type")) == "artwork":
        return f"an artwork depicting {query}"
    return f"a photo depicting {query}"


def calibrate_siglip_from_verified_openimages(
    *,
    model: Any,
    processor: Any,
    tokenizer: Any,
    processed_records: list[dict[str, Any]],
    concept_map: dict[str, dict[str, Any]],
    device: torch.device,
    report_path: Path,
    disk: DiskBudget,
    minimum_tpr: float = 0.85,
    minimum_balanced_accuracy: float = 0.80,
    maximum_fpr: float = 0.35,
) -> float:
    verified = [
        r
        for r in processed_records
        if r.get("source_id") == "open_images"
        and r.get("bbox_class_name")
        and isinstance(r.get("processed_pil"), Image.Image)
        and str(r.get("concept_id")) in concept_map
    ]

    concept_ids = sorted({str(r["concept_id"]) for r in verified})
    if len(verified) < 8 or len(concept_ids) < 4:
        raise RuntimeError(
            "SigLIP calibration requires >=8 source-verified Open Images crops "
            "across >=4 distinct concept families"
        )

    # Deterministic cap, balanced across concept families.
    by_concept: dict[str, list[dict[str, Any]]] = {}
    for record in verified:
        by_concept.setdefault(str(record["concept_id"]), []).append(record)
    for records in by_concept.values():
        records.sort(key=lambda r: str(r["content_sha256"]))

    balanced: list[dict[str, Any]] = []
    while len(balanced) < 48:
        progressed = False
        for cid in concept_ids:
            bucket = by_concept[cid]
            if bucket:
                balanced.append(bucket.pop(0))
                progressed = True
                if len(balanced) >= 48:
                    break
        if not progressed:
            break
    verified = balanced

    images = [r["processed_pil"] for r in verified]
    sample_concepts = [str(r["concept_id"]) for r in verified]
    unique_concepts = sorted(set(sample_concepts))
    class_names = sorted({str(r["bbox_class_name"]).strip().lower() for r in verified})
    if len(class_names) < 4:
        raise RuntimeError("SigLIP calibration requires >=4 distinct verified bbox classes")
    class_prompts = {
        name: siglip_relevance_prompt(
            {"source_id": "open_images", "bbox_class_name": name},
            {"retrieval_query": name},
        )
        for name in class_names
    }

    image_features = encode_siglip_images(model, processor, images, device)
    query_features = encode_siglip_texts(
        model,
        tokenizer,
        [class_prompts[name] for name in class_names],
        device,
    )
    query_index = {name: i for i, name in enumerate(class_names)}
    all_scores = image_features @ query_features.T

    positive_scores: list[float] = []
    hard_negative_scores: list[float] = []
    hard_negative_classes: list[str] = []

    for row_index, record in enumerate(verified):
        positive_class = str(record["bbox_class_name"]).strip().lower()
        positive_col = query_index[positive_class]
        positive_scores.append(float(all_scores[row_index, positive_col]))

        candidates = [
            (float(all_scores[row_index, col]), class_name)
            for class_name, col in query_index.items()
            if class_name != positive_class
        ]
        if not candidates:
            raise RuntimeError("SigLIP calibration has no hard-negative candidates")
        hard_score, hard_class = max(candidates, key=lambda pair: pair[0])
        hard_negative_scores.append(hard_score)
        hard_negative_classes.append(hard_class)

    positive = np.asarray(positive_scores, dtype=np.float32)
    negative = np.asarray(hard_negative_scores, dtype=np.float32)
    threshold, metrics = choose_calibration_threshold(
        positive,
        negative,
        minimum_tpr=minimum_tpr,
    )

    passed = (
        metrics["meanSeparation"] >= 0.02
        and metrics["truePositiveRate"] >= minimum_tpr
        and metrics["falsePositiveRate"] <= maximum_fpr
        and metrics["balancedAccuracy"] >= minimum_balanced_accuracy
    )
    report = {
        "schema": CALIBRATION_SCHEMA,
        "teacherModelId": SIGLIP_MODEL_ID,
        "teacherRevision": SIGLIP_REVISION,
        "source": "Open Images source-verified bbox crops",
        "negativeMode": "hardest other verified bbox-class prompt",
        "promptTemplate": "a centered photo of {article} {verified_bbox_class}",
        "sampleCount": len(verified),
        "conceptCount": len(unique_concepts),
        "concepts": unique_concepts,
        "verifiedBboxClasses": class_names,
        "threshold": threshold,
        "metrics": metrics,
        "criteria": {
            "minimumTruePositiveRate": minimum_tpr,
            "minimumBalancedAccuracy": minimum_balanced_accuracy,
            "maximumFalsePositiveRate": maximum_fpr,
            "minimumMeanSeparation": 0.02,
        },
        "hardNegativeClasses": hard_negative_classes,
        "passed": passed,
    }
    guarded_atomic_write_text(
        report_path,
        json.dumps(report, indent=2) + "\n",
        disk=disk,
    )
    if not passed:
        raise RuntimeError(
            "SigLIP calibration FAILED: " + json.dumps(metrics, sort_keys=True)
        )
    return float(threshold)


def load_frozen_calibration(report_path: Path) -> float:
    if not report_path.is_file():
        raise FileNotFoundError(
            f"frozen SigLIP calibration report missing: {report_path}"
        )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("schema") != CALIBRATION_SCHEMA or not report.get("passed"):
        raise RuntimeError("SigLIP calibration report is missing or failed")
    if report.get("teacherModelId") != SIGLIP_MODEL_ID:
        raise RuntimeError("SigLIP calibration model ID mismatch")
    if report.get("teacherRevision") != SIGLIP_REVISION:
        raise RuntimeError("SigLIP calibration revision mismatch")
    threshold = float(report["threshold"])
    if not np.isfinite(threshold):
        raise RuntimeError("invalid frozen SigLIP threshold")
    return threshold


def split_by_group(
    group_ids: list[str],
    *,
    train_ratio: float = 0.85,
    seed: int = 20260826,
) -> dict[str, str]:
    assignments: dict[str, str] = {}
    for group_id in sorted(set(group_ids)):
        digest = hashlib.sha256(
            f"c11-split:{seed}:{group_id}".encode("utf-8")
        ).hexdigest()
        bucket = int(digest[:8], 16) % 10000
        train_cutoff = int(train_ratio * 10000)
        dev_cutoff = train_cutoff + int((1.0 - train_ratio) * 5000)
        assignments[group_id] = (
            "train" if bucket < train_cutoff
            else ("val" if bucket < dev_cutoff else "test")
        )
    return assignments


def acquire_smoke_records(
    *,
    concepts: list[dict[str, Any]],
    raw_dir: Path,
    cached_records: dict[str, dict[str, Any]],
    seen_hashes: set[str],
    seen_phashes: list[str],
    disk: DiskBudget,
    stats: dict[str, int],
    open_images: OpenImagesBboxIndex,
) -> list[dict[str, Any]]:
    global _OPENVERSE_CONSECUTIVE_429, _OPENVERSE_COOLDOWN_UNTIL
    source_targets = SMOKE_SOURCE_TARGETS
    result: list[dict[str, Any]] = []

    for source, target in source_targets.items():
        source_records = [
            r for r in cached_records.values() if r.get("source_id") == source
        ]
        for record in source_records[:target]:
            result.append(record)

        needed = max(0, target - len(source_records))
        if needed == 0:
            continue

        if source == "openverse":
            openverse_waited_cooldown = False
            for concept in concepts:
                if needed <= 0:
                    break
                if bool(concept.get("crop_required", False)):
                    continue
                if _OPENVERSE_COOLDOWN_UNTIL > 0 and time.time() < _OPENVERSE_COOLDOWN_UNTIL:
                    if not openverse_waited_cooldown:
                        wait_sec = max(_OPENVERSE_COOLDOWN_UNTIL - time.time(), 0.0) + 1.5
                        print(
                            f"Openverse cooling down; waiting {wait_sec:.1f}s "
                            "once before retrying smoke acquisition..."
                        )
                        time.sleep(wait_sec)
                        _OPENVERSE_COOLDOWN_UNTIL = 0.0
                        _OPENVERSE_CONSECUTIVE_429 = 0
                        openverse_waited_cooldown = True
                    else:
                        continue

                batch_count = min(needed, 3)
                records = acquire_for_concept(
                    concept=concept,
                    raw_dir=raw_dir,
                    max_count=batch_count,
                    allowed_sources=("openverse",),
                    seen_hashes=seen_hashes,
                    seen_phashes=seen_phashes,
                    disk=disk,
                    stats=stats,
                    open_images=open_images,
                )
                for record in records:
                    with _CACHED_RECORDS_LOCK:
                        cached_records[record["content_sha256"]] = record
                    result.append(record)
                    needed -= 1
                    if needed <= 0:
                        break

            ov_valid = sum(
                1
                for r in result
                if r.get("source_id") == "openverse"
            )
            if ov_valid < SMOKE_MIN_VALID_PER_SOURCE and not _OPENVERSE_UNAVAILABLE:
                raise RuntimeError(
                    "Openverse API unavailable / rate-limited during smoke build: "
                    f"acquired only {ov_valid} records (minimum "
                    f"{SMOKE_MIN_VALID_PER_SOURCE} required)."
                )
        else:
            for concept in concepts:
                if needed <= 0:
                    break
                crop_required = bool(concept.get("crop_required", False))
                if source == "open_images" and not crop_required:
                    continue
                if source != "open_images" and crop_required:
                    continue
                records = acquire_for_concept(
                    concept=concept,
                    raw_dir=raw_dir,
                    max_count=1,
                    allowed_sources=(source,),
                    seen_hashes=seen_hashes,
                    seen_phashes=seen_phashes,
                    disk=disk,
                    stats=stats,
                    open_images=open_images,
                )
                for record in records:
                    with _CACHED_RECORDS_LOCK:
                        cached_records[record["content_sha256"]] = record
                    result.append(record)
                    needed -= 1
                    if needed <= 0:
                        break

        # Acquisition can be long and provider failures are expected. Preserve
        # every verified source group so the same command resumes after a crash.
        write_metadata_index(raw_dir / "metadata_index.json", cached_records, disk=disk)

    unique: dict[str, dict[str, Any]] = {}
    for record in result:
        unique[str(record["content_sha256"])] = record
    return list(unique.values())


def acquire_full_records(
    *,
    concepts: list[dict[str, Any]],
    raw_dir: Path,
    cached_records: dict[str, dict[str, Any]],
    seen_hashes: set[str],
    seen_phashes: list[str],
    disk: DiskBudget,
    stats: dict[str, int],
    open_images: OpenImagesBboxIndex,
    limit_images: int | None,
    per_concept_cap: int,
    only_concept_ids: set[str] | None = None,
    checkpoint_every: int = 10,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if per_concept_cap < 1 or per_concept_cap > FULL_MAX_PER_CONCEPT:
        raise ValueError(
            f"per_concept_cap must be 1..{FULL_MAX_PER_CONCEPT}, "
            f"got {per_concept_cap}"
        )
    per_concept = (
        max(1, math.ceil(limit_images / max(1, len(concepts))))
        if limit_images
        else per_concept_cap
    )
    per_concept = min(max(per_concept, 1), per_concept_cap)

    seen_urls: set[str] = {
        str(r.get("downloaded_url"))
        for r in cached_records.values()
        if r.get("downloaded_url")
    } | {
        str(r.get("source_url"))
        for r in cached_records.values()
        if r.get("source_url")
    }
    seen_image_ids: set[str] = {
        str(r.get("image_id"))
        for r in cached_records.values()
        if r.get("image_id")
    }

    for index, concept in enumerate(concepts):
        cid = str(concept["concept_id"])
        cached = [
            r for r in cached_records.values() if r.get("concept_id") == cid
        ][:per_concept]
        result.extend(cached)
        needed = per_concept - len(cached)

        should_acquire = only_concept_ids is None or cid in only_concept_ids
        if needed > 0 and should_acquire:
            allowed = (
                ("open_images",)
                if bool(concept.get("crop_required", False))
                else ("met", "artic", "openverse")
            )
            records = acquire_for_concept(
                concept=concept,
                raw_dir=raw_dir,
                max_count=needed,
                allowed_sources=allowed,
                seen_hashes=seen_hashes,
                seen_phashes=seen_phashes,
                disk=disk,
                stats=stats,
                open_images=open_images,
                seen_urls=seen_urls,
                seen_image_ids=seen_image_ids,
            )
            for record in records:
                with _CACHED_RECORDS_LOCK:
                    cached_records[record["content_sha256"]] = record
            result.extend(records)

        if limit_images and len(result) >= limit_images:
            result = result[:limit_images]
            break
        if (index + 1) % checkpoint_every == 0 or index + 1 == len(concepts):
            persist_acquisition_state()
            write_metadata_index(
                raw_dir / "metadata_index.json",
                cached_records,
                disk=disk,
            )
            print(
                f"Acquisition [{index + 1}/{len(concepts)}]: "
                f"RAW={len(result)} cache={len(cached_records)} "
                f"selected={len(only_concept_ids) if only_concept_ids is not None else len(concepts)}"
            )

    unique: dict[str, dict[str, Any]] = {}
    for record in result:
        unique[str(record["content_sha256"])] = record
    return list(unique.values())


def underfilled_concept_ids(
    *,
    records: list[dict[str, Any]],
    valid_records: list[dict[str, Any]],
    concepts: list[dict[str, Any]],
    desired_valid: int,
    next_cap: int,
) -> set[str]:
    """Select only families that still need valid coverage for a top-up."""
    raw_counts: dict[str, int] = {}
    valid_counts: dict[str, int] = {}
    for record in records:
        cid = str(record["concept_id"])
        raw_counts[cid] = raw_counts.get(cid, 0) + 1
    for record in valid_records:
        cid = str(record["concept_id"])
        valid_counts[cid] = valid_counts.get(cid, 0) + 1
    target = max(1, math.ceil(desired_valid / max(1, len(concepts))))
    selected = {
        str(concept["concept_id"])
        for concept in concepts
        if valid_counts.get(str(concept["concept_id"]), 0) < target
        and raw_counts.get(str(concept["concept_id"]), 0) < next_cap
    }
    if not selected:
        selected = {
            str(concept["concept_id"])
            for concept in concepts
            if raw_counts.get(str(concept["concept_id"]), 0) < next_cap
        }
    return selected


def initial_full_records(
    cached_records: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Reuse every verified cached record before considering new acquisition."""
    return list(cached_records.values())


def targeted_allowed_sources(concept: dict[str, Any]) -> tuple[str, ...]:
    """Production routes allowed during coverage-only recovery.

    ArtIC is intentionally absent: its image route is known dead in this
    environment. The normal broad collector retains its existing behavior.
    """
    if bool(concept.get("crop_required", False)):
        return ("open_images",)
    return ("openverse", "met")


def _concept_recovery_priority(concept: dict[str, Any]) -> float:
    cid = str(concept["concept_id"])
    queries = [str(concept["retrieval_query"])]
    for phrasing in concept.get("phrasings_en", []):
        value = str(phrasing).strip()
        if value and value not in queries:
            queries.append(value)
        if len(queries) >= TARGETED_MAX_TRAINING_QUERIES:
            break
    scores = [
        _route_priority(_route_key(cid, provider, query))
        for provider in targeted_allowed_sources(concept)
        for query in queries
        if _provider_viable(provider)
    ]
    return max(scores, default=0.0)


def select_balanced_full_records(
    records: list[dict[str, Any]],
    max_images: int,
) -> list[dict[str, Any]]:
    if len(records) <= max_images:
        return records
    by_concept: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_concept.setdefault(str(record["concept_id"]), []).append(record)
    for bucket in by_concept.values():
        bucket.sort(key=lambda r: str(r["content_sha256"]))

    concept_ids = sorted(by_concept)
    selected: list[dict[str, Any]] = []
    while len(selected) < max_images:
        progressed = False
        for cid in concept_ids:
            bucket = by_concept[cid]
            if bucket:
                selected.append(bucket.pop(0))
                progressed = True
                if len(selected) >= max_images:
                    break
        if not progressed:
            break
    return selected


def process_acquired_records(
    *,
    acquired: list[dict[str, Any]],
    concept_map: dict[str, dict[str, Any]],
    include_final_features: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    processed: list[dict[str, Any]] = []
    counters = {
        "crop_required_accepted_before_relevance": 0,
        "crop_required_skipped_no_valid_crop": 0,
    }
    for record in acquired:
        concept = concept_map[str(record["concept_id"])]
        crop_required = bool(concept.get("crop_required", False))
        prepared = prepare_relevance_image(
            Path(record["local_path"]),
            crop_required=crop_required,
            whole_frame_valid=bool(concept.get("whole_frame_valid", True)),
            meta_crop=record.get("crop_coordinates"),
        )
        if prepared is None:
            if crop_required:
                counters["crop_required_skipped_no_valid_crop"] += 1
            continue
        pil_image, crop, mask_fraction = prepared
        out = dict(record)
        out["processed_pil"] = pil_image
        out["crop_coordinates"] = crop
        out["mask_area_fraction"] = mask_fraction
        if include_final_features:
            oklab, prior = extract_final_color_features(pil_image)
            out["oklab_pixels"] = oklab
            out["color_prior"] = prior
        if crop_required:
            counters["crop_required_accepted_before_relevance"] += 1
        processed.append(out)
    return processed, counters


def score_and_filter_relevance(
    *,
    processed: list[dict[str, Any]],
    concept_map: dict[str, dict[str, Any]],
    model: Any,
    processor: Any,
    tokenizer: Any,
    device: torch.device,
    threshold: float,
) -> tuple[list[dict[str, Any]], int]:
    if not processed:
        return [], 0
    images = [r["processed_pil"] for r in processed]
    queries = [
        siglip_relevance_prompt(r, concept_map[str(r["concept_id"])])
        for r in processed
    ]
    image_features = encode_siglip_images(model, processor, images, device)
    text_features = encode_siglip_texts(model, tokenizer, queries, device)
    scores = np.sum(image_features * text_features, axis=1)

    valid: list[dict[str, Any]] = []
    rejected = 0
    for index, record in enumerate(processed):
        score = float(scores[index])
        if score < threshold:
            rejected += 1
            continue
        out = dict(record)
        out["relevance_score"] = score
        out["siglip_feature"] = image_features[index]
        valid.append(out)
    return valid, rejected


def load_relevance_cache(
    path: Path,
    fingerprint: str,
) -> dict[str, tuple[float, np.ndarray]]:
    if not path.is_file():
        return {}
    try:
        with np.load(path, allow_pickle=False) as payload:
            if str(payload["schema"].item()) != RELEVANCE_CACHE_SCHEMA:
                return {}
            if str(payload["fingerprint"].item()) != fingerprint:
                return {}
            hashes = payload["content_sha256"].astype(str)
            scores = payload["score"].astype(np.float32)
            features = payload["feature"].astype(np.float32)
        if features.ndim != 2 or len(hashes) != len(scores) or len(scores) != len(features):
            return {}
        return {
            sha: (float(scores[index]), features[index])
            for index, sha in enumerate(hashes.tolist())
        }
    except (OSError, KeyError, ValueError):
        return {}


def save_relevance_cache(
    path: Path,
    fingerprint: str,
    cache: dict[str, tuple[float, np.ndarray]],
    disk: DiskBudget,
) -> None:
    hashes = sorted(cache)
    feature_width = next((len(cache[sha][1]) for sha in hashes), 768)
    arrays = {
        "schema": np.asarray(RELEVANCE_CACHE_SCHEMA, dtype=str),
        "fingerprint": np.asarray(fingerprint, dtype=str),
        "content_sha256": np.asarray(hashes, dtype=str),
        "score": np.asarray([cache[sha][0] for sha in hashes], dtype=np.float32),
        "feature": np.stack([cache[sha][1] for sha in hashes]).astype(np.float32)
        if hashes else np.empty((0, feature_width), dtype=np.float32),
    }
    guarded_atomic_savez(path, disk=disk, arrays=arrays)


def score_records_with_cache(
    *,
    acquired: list[dict[str, Any]],
    concept_map: dict[str, dict[str, Any]],
    model: Any,
    processor: Any,
    tokenizer: Any,
    device: torch.device,
    threshold: float,
    cache: dict[str, tuple[float, np.ndarray]],
    cache_path: Path,
    cache_fingerprint: str,
    disk: DiskBudget,
    chunk_size: int = 64,
    save_cache: bool = True,
    cache_compaction_interval: int = 8,
) -> tuple[list[dict[str, Any]], int, int, dict[str, int]]:
    if chunk_size < 1 or cache_compaction_interval < 1:
        raise ValueError("chunk and cache compaction intervals must be positive")
    missing = [r for r in acquired if str(r["content_sha256"]) not in cache]
    crop_totals = {
        "crop_required_accepted_before_relevance": 0,
        "crop_required_skipped_no_valid_crop": 0,
    }

    # post-raw progress telemetry
    postraw_started = time.time()
    total_missing = len(missing)
    existing_cache_hits = len(acquired) - total_missing

    if total_missing:
        print(
            f"Post-raw preprocessing: 0/{total_missing} "
            f"(existing relevance cache hits={existing_cache_hits})"
        )

    total_chunks = (len(missing) + chunk_size - 1) // chunk_size
    for chunk_number, start in enumerate(range(0, len(missing), chunk_size), start=1):
        chunk = missing[start : start + chunk_size]
        processed, crop_stats = process_acquired_records(
            acquired=chunk,
            concept_map=concept_map,
            include_final_features=False,
        )
        for key, value in crop_stats.items():
            crop_totals[key] += value
        processed_by_hash = {str(r["content_sha256"]): r for r in processed}
        t0_sig = time.time()
        scored, _ = score_and_filter_relevance(
            processed=processed,
            concept_map=concept_map,
            model=model,
            processor=processor,
            tokenizer=tokenizer,
            device=device,
            threshold=-float("inf"),
        )
        sig_duration = time.time() - t0_sig
        for record in scored:
            sha = str(record["content_sha256"])
            cache[sha] = (
                float(record["relevance_score"]),
                np.asarray(record["siglip_feature"], dtype=np.float32),
            )
            src_id = str(record.get("source_id", "open_images"))
            cid = str(record.get("concept_id", ""))
            route_key = str(record.get("acquisition_route_key") or "")
            _FUNNEL.record(src_id, "siglip_scored", 1, cid=cid)
            _record_route(route_key, "scored")
            if float(record["relevance_score"]) >= threshold:
                _FUNNEL.record(src_id, "siglip_pass", 1, cid=cid)
                _record_route(route_key, "passed")
            else:
                _FUNNEL.record(src_id, "siglip_fail", 1, cid=cid)

        if scored:
            _FUNNEL.add_siglip_time(sig_duration)

        feature_width = next((len(value[1]) for value in cache.values()), 768)
        for record in chunk:
            sha = str(record["content_sha256"])
            if sha not in processed_by_hash:
                cache[sha] = (float("-inf"), np.zeros(feature_width, dtype=np.float32))
                src_id = str(record.get("source_id", "open_images"))
                cid = str(record.get("concept_id", ""))
                _FUNNEL.record(src_id, "siglip_scored", 1, cid=cid)
                _FUNNEL.record(src_id, "siglip_fail", 1, cid=cid)
        if save_cache and (
            chunk_number % cache_compaction_interval == 0
            or chunk_number == total_chunks
        ):
            save_relevance_cache(cache_path, cache_fingerprint, cache, disk)

        done = min(start + len(chunk), total_missing)
        elapsed = max(time.time() - postraw_started, 1e-9)
        rate = done / elapsed
        remaining = total_missing - done
        eta_seconds = remaining / rate if rate > 0 else float("inf")

        print(
            f"Post-raw preprocessing: {done}/{total_missing} "
            f"({100.0 * done / max(total_missing, 1):.1f}%) "
            f"rate={rate:.2f} rec/s "
            f"elapsed={elapsed / 60.0:.1f}m "
            f"ETA={eta_seconds / 60.0:.1f}m"
        )

    valid: list[dict[str, Any]] = []
    rejected = 0
    for record in acquired:
        cached = cache.get(str(record["content_sha256"]))
        if cached is None or cached[0] < threshold:
            rejected += 1
            continue
        out = dict(record)
        out["relevance_score"] = cached[0]
        out["siglip_feature"] = cached[1]
        valid.append(out)
    return valid, rejected, len(acquired) - len(missing), crop_totals


def choose_balanced_smoke(
    valid: list[dict[str, Any]],
    target: int = SMOKE_VALID_IMAGES,
) -> list[dict[str, Any]]:
    required = ("met", "artic", "open_images")
    if sum(1 for r in valid if r.get("source_id") == "openverse") >= SMOKE_MIN_VALID_PER_SOURCE:
        required = (*required, "openverse")
    by_source = {
        source: [r for r in valid if r.get("source_id") == source]
        for source in required
    }
    missing = {
        source: len(rows)
        for source, rows in by_source.items()
        if len(rows) < SMOKE_MIN_VALID_PER_SOURCE
    }
    if missing:
        raise RuntimeError(
            f"smoke did not exercise all sources with enough valid data: {missing}"
        )

    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in required:
        for record in by_source[source][:SMOKE_MIN_VALID_PER_SOURCE]:
            selected.append(record)
            seen.add(record["content_sha256"])

    for record in valid:
        if len(selected) >= target:
            break
        if record["content_sha256"] in seen:
            continue
        selected.append(record)
        seen.add(record["content_sha256"])

    if len(selected) < target:
        raise RuntimeError(
            f"smoke requires {target} valid images, got {len(selected)}"
        )
    return selected[:target]


def fit_pca(
    *,
    features: np.ndarray,
    records: list[dict[str, Any]],
    smoke: bool,
    output_dir: Path,
    disk: DiskBudget,
) -> tuple[np.ndarray, dict[str, Any]]:
    group_ids = [str(r["source_group_id"]) for r in records]
    splits = split_by_group(group_ids)
    train_indices = [
        i for i, record in enumerate(records)
        if splits[str(record["source_group_id"])] == "train"
    ]
    val_indices = [
        i for i, record in enumerate(records)
        if splits[str(record["source_group_id"])] == "val"
    ]
    if len(train_indices) < 2 or len(val_indices) < 1:
        raise RuntimeError(
            f"invalid train/val split: train={len(train_indices)}, val={len(val_indices)}"
        )

    train = features[train_indices]
    mean = train.mean(axis=0, keepdims=True)
    centered = train - mean
    rank = int(np.linalg.matrix_rank(centered))
    requested = 128
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    effective_components = min(rank, requested, int(vt.shape[0]))

    if not smoke and effective_components < requested:
        raise RuntimeError(
            f"FULL PCA FAILED: effective components {effective_components} < 128"
        )
    if effective_components <= 0:
        raise RuntimeError("PCA has zero effective components")

    components = np.zeros(
        (features.shape[1], requested),
        dtype=np.float32,
    )
    components[:, :effective_components] = vt[:effective_components].T.astype(
        np.float32
    )

    train_group_ids = sorted(
        str(records[i]["source_group_id"]) for i in train_indices
    )
    train_groups_sha = hashlib.sha256(
        "\n".join(train_group_ids).encode("utf-8")
    ).hexdigest()

    pca_path = output_dir / "palettebrain_c11_pca_projection.npz"
    guarded_atomic_savez(
        pca_path,
        disk=disk,
        arrays={
            "mean": mean.astype(np.float32),
            "components": components,
            "teacher_model_id": np.array(SIGLIP_MODEL_ID, dtype=str),
            "teacher_revision": np.array(SIGLIP_REVISION, dtype=str),
            "train_source_groups_sha256": np.array(train_groups_sha, dtype=str),
            "requested_components": np.array(requested, dtype=np.int32),
            "effective_rank": np.array(rank, dtype=np.int32),
            "effective_components": np.array(effective_components, dtype=np.int32),
            "zero_padded_for_smoke": np.array(
                smoke and effective_components < requested,
                dtype=bool,
            ),
        },
    )
    pca_sha = sha256_file(pca_path)

    projected = (features - mean) @ components
    norms = np.linalg.norm(projected, axis=1, keepdims=True)
    latents = (projected / np.maximum(norms, 1e-12)).astype(np.float32)

    for record in records:
        record["split"] = splits[str(record["source_group_id"])]

    diagnostics = {
        "pcaPath": str(pca_path).replace("\\", "/"),
        "pcaSha256": pca_sha,
        "requestedComponents": requested,
        "effectiveRank": rank,
        "effectiveComponents": effective_components,
        "zeroPaddedForSmoke": smoke and effective_components < requested,
        "trainImages": len(train_indices),
        "valImages": len(val_indices),
        "trainSourceGroupsSha256": train_groups_sha,
    }
    return latents, diagnostics


def build_rows(
    *,
    records: list[dict[str, Any]],
    teacher_latents: np.ndarray,
    concept_map: dict[str, dict[str, Any]],
    smoke: bool,
    seed: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for image_index, record in enumerate(records):
        concept = concept_map[str(record["concept_id"])]
        en = list(concept.get("phrasings_en", []))
        ru = list(concept.get("phrasings_ru", []))
        if not en or not ru:
            raise RuntimeError(
                f"concept {record['concept_id']} lacks RU/EN phrasings"
            )

        if smoke:
            counts = list(range(2, 10))
        else:
            counts = [
                2 + ((image_index * 4 + offset) % 8)
                for offset in range(4)
            ]

        for count in counts:
            try:
                palette = extract_deterministic_palette(
                    record["oklab_pixels"],
                    count,
                    seed=seed + image_index * 17 + count,
                )
            except ValueError:
                continue

            target = np.zeros((MAX_COLORS, 5), dtype=np.float32)
            lock_values = np.zeros((MAX_COLORS, 4), dtype=np.float32)
            for slot, color in enumerate(palette):
                encoded, lock = physical_oklch_to_target(
                    *oklab_to_oklch(color)
                )
                target[slot] = encoded
                lock_values[slot] = lock

            count_mask = np.zeros(MAX_COLORS, dtype=np.float32)
            count_mask[:count] = 1.0

            lang = "ru" if ((image_index + count) % 2) else "en"
            phrases = ru if lang == "ru" else en
            phrase_seed = int(
                hashlib.sha256(
                    f"{record['content_sha256']}:{count}:{lang}".encode("utf-8")
                ).hexdigest()[:8],
                16,
            )
            phrase = phrases[phrase_seed % len(phrases)]

            lock_seed = int(
                hashlib.sha256(
                    f"{record['content_sha256']}:{count}:locks".encode("utf-8")
                ).hexdigest()[:8],
                16,
            )
            lock_rng = np.random.RandomState(lock_seed)
            locked_mask = np.zeros(MAX_COLORS, dtype=np.float32)
            locked_colors = np.zeros((MAX_COLORS, 4), dtype=np.float32)
            lock_count = 0
            if count >= 3 and lock_rng.random_sample() < 0.25:
                lock_count = 1 if lock_rng.random_sample() < 0.70 else 2
                for idx in lock_rng.choice(count, size=lock_count, replace=False):
                    locked_mask[idx] = 1.0
                    locked_colors[idx] = lock_values[idx]

            row_seed = int(
                hashlib.sha256(
                    (
                        f"{record['content_sha256']}:{count}:{phrase}:{lock_count}"
                    ).encode("utf-8")
                ).hexdigest()[:8],
                16,
            )

            rows.append(
                {
                    "prompt": phrase,
                    "language": lang,
                    "count": count,
                    "concept_id": record["concept_id"],
                    "category": record["category"],
                    "source_id": record["source_id"],
                    "source_type": record["source_type"],
                    "source_group_id": record["source_group_id"],
                    "image_id": record["image_id"],
                    "content_sha256": record["content_sha256"],
                    "perceptual_hash64": record["perceptual_hash64"],
                    "crop_coordinates": record["crop_coordinates"],
                    "mask_area_fraction": record["mask_area_fraction"],
                    "relevance_score": record["relevance_score"],
                    "bbox_provenance": record.get("bbox_provenance", ""),
                    "bbox_annotation_key": record.get("bbox_annotation_key", ""),
                    "bbox_class_name": record.get("bbox_class_name", ""),
                    "bbox_label_mid": record.get("bbox_label_mid", ""),
                    "bbox_source": record.get("bbox_source", ""),
                    "source_dataset_release": record.get("source_dataset_release", ""),
                    "source_annotation_url": record.get("source_annotation_url", ""),
                    "source_image_metadata_url": record.get("source_image_metadata_url", ""),
                    "license": record["license"],
                    "license_url": record["license_url"],
                    "provider": record["provider"],
                    "foreign_identifier": record["foreign_identifier"],
                    "source_url": record["source_url"],
                    "downloaded_url": record.get(
                        "downloaded_url", record["source_url"]
                    ),
                    "landing_url": record["landing_url"],
                    "creator": record["creator"],
                    "color_prior": record["color_prior"],
                    "teacher_latent": teacher_latents[image_index],
                    "count_mask": count_mask,
                    "seed_noise": seed_noise_from_uint32(row_seed),
                    "locked_mask": locked_mask,
                    "locked_colors": locked_colors,
                    "target": target,
                    "quality_weight": 1.0,
                    "split": record["split"],
                }
            )
    if not rows:
        raise RuntimeError("no training rows were generated")
    return rows


def audit_rows(rows: list[dict[str, Any]], *, smoke: bool) -> dict[str, Any]:
    counts = {count: 0 for count in range(2, 10)}
    languages = {"ru": 0, "en": 0}
    locked_rows = 0
    for row in rows:
        counts[int(row["count"])] += 1
        languages[str(row["language"])] += 1
        if float(np.sum(row["locked_mask"])) > 0:
            locked_rows += 1

    missing_counts = [count for count, value in counts.items() if value == 0]
    if missing_counts:
        raise RuntimeError(f"count coverage missing: {missing_counts}")
    if languages["ru"] == 0 or languages["en"] == 0:
        raise RuntimeError(f"language coverage failed: {languages}")

    if not smoke:
        minimum_per_count = max(25, int(len(rows) * 0.01))
        weak = {
            count: value
            for count, value in counts.items()
            if value < minimum_per_count
        }
        if weak:
            raise RuntimeError(f"full count coverage too weak: {weak}")
        if locked_rows < int(len(rows) * 0.10):
            raise RuntimeError(
                f"lock coverage too weak: {locked_rows}/{len(rows)}"
            )

    return {
        "countRows": {str(k): v for k, v in counts.items()},
        "languageRows": languages,
        "lockedRows": locked_rows,
        "lockedFraction": locked_rows / len(rows),
    }


def full_visual_coverage_requirements(
    *,
    records: list[dict[str, Any]],
    concepts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return every FULL coverage result without raising on the first failure."""
    categories = sorted({str(c["category"]) for c in concepts})
    by_category: dict[str, dict[str, Any]] = {}
    zero_concepts: list[str] = []
    failing_categories: dict[str, dict[str, Any]] = {}

    for category in categories:
        family_ids = {
            str(c["concept_id"])
            for c in concepts
            if str(c["category"]) == category
        }
        rows = [r for r in records if str(r["category"]) == category]
        covered = {str(r["concept_id"]) for r in rows}
        fraction = len(covered) / len(family_ids) if family_ids else 0.0
        required_covered = math.ceil(
            len(family_ids) * FULL_MIN_CATEGORY_COVERAGE
        )
        details = {
            "images": len(rows),
            "coveredConcepts": len(covered),
            "totalConcepts": len(family_ids),
            "coverageFraction": fraction,
            "zeroConcepts": sorted(family_ids - covered),
            "requiredImages": FULL_MIN_CATEGORY_IMAGES,
            "requiredCoveredConcepts": required_covered,
            "additionalImagesNeeded": max(
                0, FULL_MIN_CATEGORY_IMAGES - len(rows)
            ),
            "additionalConceptsNeeded": max(
                0, required_covered - len(covered)
            ),
        }
        by_category[category] = details
        zero_concepts.extend(sorted(family_ids - covered))
        if (
            details["additionalImagesNeeded"] > 0
            or details["additionalConceptsNeeded"] > 0
        ):
            failing_categories[category] = details

    source_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    for record in records:
        source = str(record["source_id"])
        source_type = str(record["source_type"])
        source_counts[source] = source_counts.get(source, 0) + 1
        type_counts[source_type] = type_counts.get(source_type, 0) + 1

    total = max(1, len(records))
    real_fraction = type_counts.get("real_world", 0) / total
    artwork_fraction = type_counts.get("artwork", 0) / total

    bbox_valid = sum(
        1
        for r in records
        if r.get("source_id") == "open_images"
        and r.get("bbox_provenance")
        and r.get("crop_coordinates") is not None
    )
    crop_required_concepts = {
        str(c["concept_id"]) for c in concepts if bool(c.get("crop_required", False))
    }
    crop_counts = {
        cid: sum(1 for r in records if str(r["concept_id"]) == cid)
        for cid in sorted(crop_required_concepts)
    }
    crop_covered = {cid for cid, count in crop_counts.items() if count > 0}
    crop_coverage = (
        len(crop_covered) / len(crop_required_concepts)
        if crop_required_concepts
        else 1.0
    )
    weak_crop_concepts = {
        cid: count
        for cid, count in crop_counts.items()
        if count < FULL_MIN_CROP_REQUIRED_IMAGES_PER_CONCEPT
    }

    return {
        "categoryCoverage": by_category,
        "failingCategories": failing_categories,
        "remainingConcepts": sum(
            int(details["additionalConceptsNeeded"])
            for details in failing_categories.values()
        ),
        "zeroImageConcepts": sorted(set(zero_concepts)),
        "sourceCounts": source_counts,
        "sourceTypeCounts": type_counts,
        "realWorldFraction": real_fraction,
        "artworkFraction": artwork_fraction,
        "realWorldPass": real_fraction >= FULL_MIN_REAL_WORLD_FRACTION,
        "artworkPass": artwork_fraction >= FULL_MIN_ARTWORK_FRACTION,
        "realBboxImages": bbox_valid,
        "cropRequiredConcepts": len(crop_required_concepts),
        "cropRequiredCoveredConcepts": len(crop_covered),
        "cropRequiredConceptCoverage": crop_coverage,
        "cropRequiredImageCounts": crop_counts,
        "weakCropConcepts": weak_crop_concepts,
        "mandatoryPass": (
            not failing_categories
            and real_fraction >= FULL_MIN_REAL_WORLD_FRACTION
            and artwork_fraction >= FULL_MIN_ARTWORK_FRACTION
            and crop_coverage >= FULL_MIN_CROP_REQUIRED_CONCEPT_COVERAGE
            and not weak_crop_concepts
        ),
    }


def select_targeted_recovery_concept_ids(
    *,
    requirements: dict[str, Any],
    concepts: list[dict[str, Any]],
    unavailable_concept_ids: set[str] | None = None,
) -> list[str]:
    """Choose only the minimum families that can make failing gates green."""
    unavailable = unavailable_concept_ids or set()
    concept_map = {str(concept["concept_id"]): concept for concept in concepts}
    selected: list[str] = []

    for category, details in requirements["failingCategories"].items():
        zero = [
            cid
            for cid in details["zeroConcepts"]
            if cid not in unavailable and cid in concept_map
        ]
        zero.sort(
            key=lambda cid: (-_concept_recovery_priority(concept_map[cid]), cid)
        )
        concept_need = int(details["additionalConceptsNeeded"])
        chosen = zero[:concept_need]
        selected.extend(chosen)

        image_need = max(
            0,
            int(details["additionalImagesNeeded"]) - concept_need,
        )
        if image_need:
            category_ids = [
                str(concept["concept_id"])
                for concept in concepts
                if str(concept["category"]) == category
                and str(concept["concept_id"]) not in unavailable
                and str(concept["concept_id"]) not in selected
            ]
            category_ids.sort(
                key=lambda cid: (-_concept_recovery_priority(concept_map[cid]), cid)
            )
            selected.extend(category_ids[:image_need])

    for cid in sorted(requirements["weakCropConcepts"]):
        if cid not in unavailable and cid not in selected:
            selected.append(cid)
    return selected


def full_acquisition_complete(
    *,
    valid_count: int,
    desired_valid: int,
    requirements: dict[str, Any],
) -> bool:
    return valid_count >= desired_valid and bool(requirements["mandatoryPass"])


def require_full_visual_coverage(requirements: dict[str, Any]) -> None:
    """Fail before final feature extraction when canonical coverage is deficient."""
    if requirements.get("mandatoryPass") is True:
        return
    deficits = {
        category: {
            "additionalImagesNeeded": details["additionalImagesNeeded"],
            "additionalConceptsNeeded": details["additionalConceptsNeeded"],
        }
        for category, details in requirements.get("failingCategories", {}).items()
    }
    raise RuntimeError(
        "FULL DATASET COVERAGE FAILED: " + json.dumps(deficits, sort_keys=True)
    )


def audit_visual_coverage(
    *,
    records: list[dict[str, Any]],
    concepts: list[dict[str, Any]],
    smoke: bool,
) -> dict[str, Any]:
    result = full_visual_coverage_requirements(records=records, concepts=concepts)

    if not smoke and result["failingCategories"]:
        category = sorted(result["failingCategories"])[0]
        details = result["failingCategories"][category]
        raise RuntimeError(
            f"FULL CATEGORY COVERAGE FAILED for {category}: "
            f"{details['images']} images, "
            f"{details['coveredConcepts']}/{details['totalConcepts']} "
            f"({details['coverageFraction']:.1%})"
        )

    if smoke:
        required_sources = ["met", "artic", "open_images"]
        if result["sourceCounts"].get("openverse", 0) >= SMOKE_MIN_VALID_PER_SOURCE:
            required_sources.append("openverse")
        for source in required_sources:
            if result["sourceCounts"].get(source, 0) < SMOKE_MIN_VALID_PER_SOURCE:
                raise RuntimeError(
                    f"smoke source coverage failed for {source}: "
                    f"{result['sourceCounts'].get(source, 0)}"
                )
        if result["realBboxImages"] < SMOKE_MIN_VALID_PER_SOURCE:
            raise RuntimeError(
                f"smoke requires real bbox examples, got {result['realBboxImages']}"
            )
        return result

    if not result["realWorldPass"]:
        raise RuntimeError(
            "FULL real-world grounding too weak: "
            f"{result['realWorldFraction']:.1%}"
        )
    if not result["artworkPass"]:
        raise RuntimeError(
            "FULL artwork grounding too weak: "
            f"{result['artworkFraction']:.1%}"
        )
    if (
        result["cropRequiredConcepts"]
        and result["cropRequiredConceptCoverage"]
        < FULL_MIN_CROP_REQUIRED_CONCEPT_COVERAGE
    ):
        raise RuntimeError(
            "FULL crop-required concept coverage FAILED: "
            f"{result['cropRequiredCoveredConcepts']}/"
            f"{result['cropRequiredConcepts']} "
            f"({result['cropRequiredConceptCoverage']:.1%})"
        )
    if result["weakCropConcepts"]:
        raise RuntimeError(
            "FULL crop-required grounding too weak: "
            + json.dumps(result["weakCropConcepts"], sort_keys=True)
        )
    return result


def save_dataset(
    *,
    output_path: Path,
    rows: list[dict[str, Any]],
    relevance_threshold: float,
    pca_diagnostics: dict[str, Any],
    cache_dir: str,
    disk: DiskBudget,
    concepts_sha256: str,
    manifest_sha256: str,
    calibration_sha256: str,
    builder_sha256: str,
) -> tuple[str, int]:
    unique_prompts = list(dict.fromkeys(str(r["prompt"]) for r in rows))
    print(f"Embedding {len(unique_prompts)} unique prompts with repository E5...")
    encoder = load_encoder(
        device="auto",
        cache_dir=cache_dir,
        local_files_only=False,
    )
    embeddings = embed_texts(
        unique_prompts,
        encoder=encoder,
        batch_size=128,
    )
    prompt_to_embedding = dict(zip(unique_prompts, embeddings, strict=True))

    arrays = {
        "text_embedding": np.stack(
            [prompt_to_embedding[r["prompt"]] for r in rows]
        ).astype(np.float32),
        "color_prior": np.stack([r["color_prior"] for r in rows]).astype(np.float32),
        "teacher_latent": np.stack(
            [r["teacher_latent"] for r in rows]
        ).astype(np.float32),
        "count_mask": np.stack([r["count_mask"] for r in rows]).astype(np.float32),
        "seed_noise": np.stack([r["seed_noise"] for r in rows]).astype(np.float32),
        "locked_mask": np.stack(
            [r["locked_mask"] for r in rows]
        ).astype(np.float32),
        "locked_colors": np.stack(
            [r["locked_colors"] for r in rows]
        ).astype(np.float32),
        "target": np.stack([r["target"] for r in rows]).astype(np.float32),
        "quality_weight": np.asarray(
            [r["quality_weight"] for r in rows], dtype=np.float32
        ),
        "split": np.asarray([r["split"] for r in rows], dtype=str),
        "prompt": np.asarray([r["prompt"] for r in rows], dtype=str),
        "language": np.asarray([r["language"] for r in rows], dtype=str),
        "count": np.asarray([r["count"] for r in rows], dtype=np.int16),
        "concept_id": np.asarray([r["concept_id"] for r in rows], dtype=str),
        "category": np.asarray([r["category"] for r in rows], dtype=str),
        "source_id": np.asarray([r["source_id"] for r in rows], dtype=str),
        "source_type": np.asarray([r["source_type"] for r in rows], dtype=str),
        "source_group_id": np.asarray(
            [r["source_group_id"] for r in rows], dtype=str
        ),
        "image_id": np.asarray([r["image_id"] for r in rows], dtype=str),
        "content_sha256": np.asarray(
            [r["content_sha256"] for r in rows], dtype=str
        ),
        "perceptual_hash64": np.asarray(
            [r["perceptual_hash64"] for r in rows], dtype=str
        ),
        "crop_coordinates": np.stack(
            [np.asarray(r["crop_coordinates"], dtype=np.float64) for r in rows]
        ),
        "mask_area_fraction": np.asarray(
            [r["mask_area_fraction"] for r in rows], dtype=np.float64
        ),
        "relevance_score": np.asarray(
            [r["relevance_score"] for r in rows], dtype=np.float32
        ),
        "bbox_provenance": np.asarray(
            [r["bbox_provenance"] for r in rows], dtype=str
        ),
        "bbox_annotation_key": np.asarray(
            [r["bbox_annotation_key"] for r in rows], dtype=str
        ),
        "bbox_class_name": np.asarray(
            [r["bbox_class_name"] for r in rows], dtype=str
        ),
        "bbox_label_mid": np.asarray(
            [r["bbox_label_mid"] for r in rows], dtype=str
        ),
        "bbox_source": np.asarray(
            [r["bbox_source"] for r in rows], dtype=str
        ),
        "source_dataset_release": np.asarray(
            [r["source_dataset_release"] for r in rows], dtype=str
        ),
        "source_annotation_url": np.asarray(
            [r["source_annotation_url"] for r in rows], dtype=str
        ),
        "source_image_metadata_url": np.asarray(
            [r["source_image_metadata_url"] for r in rows], dtype=str
        ),
        "license": np.asarray([r["license"] for r in rows], dtype=str),
        "license_url": np.asarray([r["license_url"] for r in rows], dtype=str),
        "provider": np.asarray([r["provider"] for r in rows], dtype=str),
        "foreign_identifier": np.asarray(
            [r["foreign_identifier"] for r in rows], dtype=str
        ),
        "source_url": np.asarray([r["source_url"] for r in rows], dtype=str),
        "downloaded_url": np.asarray(
            [r["downloaded_url"] for r in rows], dtype=str
        ),
        "landing_url": np.asarray([r["landing_url"] for r in rows], dtype=str),
        "creator": np.asarray([r["creator"] for r in rows], dtype=str),
        "teacher_model_id": np.array(SIGLIP_MODEL_ID, dtype=str),
        "teacher_revision": np.array(SIGLIP_REVISION, dtype=str),
        "transformers_version": np.array(transformers.__version__, dtype=str),
        "e5_model_id": np.array(E5_MODEL_ID, dtype=str),
        "e5_revision": np.array(E5_REVISION, dtype=str),
        "relevance_threshold": np.array(relevance_threshold, dtype=np.float32),
        "pca_artifact_sha256": np.array(
            pca_diagnostics["pcaSha256"], dtype=str
        ),
        "pca_train_source_groups_sha256": np.array(
            pca_diagnostics["trainSourceGroupsSha256"], dtype=str
        ),
        "concept_bank_sha256": np.array(concepts_sha256, dtype=str),
        "source_manifest_sha256": np.array(manifest_sha256, dtype=str),
        "siglip_calibration_report_sha256": np.array(calibration_sha256, dtype=str),
        "builder_sha256": np.array(builder_sha256, dtype=str),
    }
    guarded_atomic_savez(output_path, disk=disk, arrays=arrays)
    with np.load(output_path, allow_pickle=False) as loaded:
        if loaded["text_embedding"].shape[0] != len(rows):
            raise RuntimeError("saved dataset row count mismatch")
        if loaded["text_embedding"].shape[1] != 384:
            raise RuntimeError("saved E5 embeddings are not 384-dimensional")
    return sha256_file(output_path), output_path.stat().st_size


def build_c11_dataset(
    *,
    concepts_path: Path,
    manifest_path: Path,
    raw_dir: Path,
    output_path: Path,
    smoke: bool,
    limit_images: int | None,
    seed: int,
    device: str,
    cache_dir: str,
    calibration_min_tpr: float = 0.85,
    calibration_min_balanced_accuracy: float = 0.80,
    calibration_max_fpr: float = 0.35,
    download_workers: int = 6,
    metadata_workers: int = 8,
    checkpoint_every: int = 10,
    adaptive_benchmark_seconds: float | None = None,
) -> dict[str, Any]:
    manifest = load_and_validate_manifest(manifest_path)
    policy = manifest.get("acquisition_policy", {})
    hard_disk = int(
        policy.get("maximum_disk_budget_bytes", 10 * 1024**3)
    )
    target_disk = int(
        policy.get("target_disk_budget_bytes", int(8.5 * 1024**3))
    )

    concepts_sha256 = sha256_file(concepts_path)
    manifest_sha256 = sha256_file(manifest_path)
    builder_sha256 = sha256_file(Path(__file__).resolve())

    concept_payload = json.loads(concepts_path.read_text(encoding="utf-8"))
    concepts = list(concept_payload.get("concepts", []))
    if not concepts:
        raise RuntimeError("concept bank is empty")
    concept_map = {str(c["concept_id"]): c for c in concepts}
    if len(concept_map) != len(concepts):
        raise RuntimeError("concept bank contains duplicate IDs")
    print(f"Loaded {len(concepts)} concept families.")

    preflight_anti_leakage(concepts)

    raw_dir.mkdir(parents=True, exist_ok=True)
    cache_path = Path(cache_dir)
    disk = DiskBudget(
        raw_dir=raw_dir,
        cache_dir=cache_path,
        target_bytes=target_disk,
        hard_bytes=hard_disk,
    )
    acquisition_fingerprint = hashlib.sha256(
        (concepts_sha256 + manifest_sha256 + ACQUISITION_STATE_SCHEMA).encode("ascii")
    ).hexdigest()
    configure_acquisition_runtime(
        state_path=raw_dir / "acquisition_state.json",
        fingerprint=acquisition_fingerprint,
        download_workers=download_workers,
        metadata_workers=metadata_workers,
    )
    print(disk.summary())

    index_path = raw_dir / "metadata_index.json"
    cached_records, seen_phashes, invalid_cache = load_metadata_index(
        index_path,
        raw_dir,
    )
    seen_hashes = set(cached_records)
    print(
        f"Resume: {len(cached_records)} verified cache records; "
        f"{invalid_cache} invalid/legacy records ignored."
    )

    stats: dict[str, int] = {}
    open_images = OpenImagesBboxIndex(
        cache_dir=raw_dir / "open_images_meta",
        disk=disk,
    )

    # crop_required means whole-frame fallback is forbidden. In full mode every such
    # family must resolve to at least one real Open Images boxable class.
    if not smoke:
        open_images.load()
        unresolved_crop_required: list[str] = []
        for concept in concepts:
            if not bool(concept.get("crop_required", False)):
                continue
            cid = str(concept["concept_id"])
            names = CONCEPT_TO_OPENIMAGES_CLASSES.get(cid, ())
            resolved_names = [
                normalize_text(name)
                for name in names
                if normalize_text(name) in open_images.class_map
            ]
            if not resolved_names:
                unresolved_crop_required.append(cid)
        if unresolved_crop_required:
            raise RuntimeError(
                "FULL crop-required preflight FAILED; no verified Open Images "
                "boxable mapping for: " + ", ".join(sorted(unresolved_crop_required))
            )

    if smoke:
        acquired = acquire_smoke_records(
            concepts=concepts,
            raw_dir=raw_dir,
            cached_records=cached_records,
            seen_hashes=seen_hashes,
            seen_phashes=seen_phashes,
            disk=disk,
            stats=stats,
            open_images=open_images,
        )
    elif adaptive_benchmark_seconds is not None:
        if adaptive_benchmark_seconds <= 0:
            raise ValueError("adaptive_benchmark_seconds must be positive")
        acquired = initial_full_records(cached_records)
    else:
        acquired = initial_full_records(cached_records)

    write_metadata_index(index_path, cached_records, disk=disk)
    print(
        f"Raw acquisition complete: {len(acquired)} records; "
        f"exact dupes={stats.get('exact_duplicates', 0)}; "
        f"near dupes={stats.get('near_duplicates', 0)}."
    )
    if not acquired and smoke:
        raise RuntimeError("no images acquired")

    processed: list[dict[str, Any]] = []
    crop_stats = {
        "crop_required_accepted_before_relevance": 0,
        "crop_required_skipped_no_valid_crop": 0,
    }
    if smoke:
        processed, crop_stats = process_acquired_records(
            acquired=acquired,
            concept_map=concept_map,
        )
        if not processed:
            raise RuntimeError("no images survived crop/image processing")

    resolved_device = resolve_device(device)
    processor = AutoProcessor.from_pretrained(
        SIGLIP_MODEL_ID,
        revision=SIGLIP_REVISION,
        use_fast=False,
        cache_dir=cache_dir,
    )
    tokenizer = AutoTokenizer.from_pretrained(
        SIGLIP_MODEL_ID,
        revision=SIGLIP_REVISION,
        cache_dir=cache_dir,
    )
    model = AutoModel.from_pretrained(
        SIGLIP_MODEL_ID,
        revision=SIGLIP_REVISION,
        cache_dir=cache_dir,
    ).to(resolved_device).eval()
    preprocessing_audit = validate_siglip_preprocessing(processor)

    calibration_path = (
        Path("ml/palettebrain/reports")
        / "candidate-11-siglip-calibration.json"
    )
    disk.track_artifact(calibration_path)
    if smoke:
        threshold = calibrate_siglip_from_verified_openimages(
            model=model,
            processor=processor,
            tokenizer=tokenizer,
            processed_records=processed,
            concept_map=concept_map,
            device=resolved_device,
            report_path=calibration_path,
            disk=disk,
            minimum_tpr=calibration_min_tpr,
            minimum_balanced_accuracy=calibration_min_balanced_accuracy,
            maximum_fpr=calibration_max_fpr,
        )
    else:
        threshold = load_frozen_calibration(calibration_path)

    if smoke:
        valid, relevance_rejected = score_and_filter_relevance(
            processed=processed,
            concept_map=concept_map,
            model=model,
            processor=processor,
            tokenizer=tokenizer,
            device=resolved_device,
            threshold=threshold,
        )
        valid = choose_balanced_smoke(valid, SMOKE_VALID_IMAGES)
    else:
        relevance_fingerprint = hashlib.sha256(
            (
                SIGLIP_MODEL_ID + SIGLIP_REVISION + concepts_sha256
                + sha256_file(calibration_path) + RELEVANCE_CACHE_SCHEMA
            ).encode("utf-8")
        ).hexdigest()
        relevance_cache_path = raw_dir / "relevance_cache.npz"
        disk.track_artifact(relevance_cache_path)
        relevance_cache = load_relevance_cache(
            relevance_cache_path,
            relevance_fingerprint,
        )
        valid, relevance_rejected, cache_hits, crop_stats = score_records_with_cache(
            acquired=acquired,
            concept_map=concept_map,
            model=model,
            processor=processor,
            tokenizer=tokenizer,
            device=resolved_device,
            threshold=threshold,
            cache=relevance_cache,
            cache_path=relevance_cache_path,
            cache_fingerprint=relevance_fingerprint,
            disk=disk,
        )
        print(f"Relevance: VALID={len(valid)} RAW={len(acquired)} cache_hits={cache_hits}")
        desired_valid = (
            min(limit_images, FULL_TARGET_UNIQUE_IMAGES)
            if limit_images is not None
            else FULL_TARGET_UNIQUE_IMAGES
        )
        coverage_state = full_visual_coverage_requirements(
            records=valid,
            concepts=concepts,
        )
        print(
            "Coverage deficits before network: "
            + json.dumps(
                {
                    category: {
                        "images": details["images"],
                        "requiredImages": details["requiredImages"],
                        "coveredConcepts": details["coveredConcepts"],
                        "requiredCoveredConcepts": details[
                            "requiredCoveredConcepts"
                        ],
                        "additionalImagesNeeded": details[
                            "additionalImagesNeeded"
                        ],
                        "additionalConceptsNeeded": details[
                            "additionalConceptsNeeded"
                        ],
                    }
                    for category, details in coverage_state[
                        "failingCategories"
                    ].items()
                },
                sort_keys=True,
            )
        )
        print("Starting adaptive streaming top-up...")
        import queue
        import threading
        import time
        import math

        seen_urls: set[str] = {
            str(r.get("downloaded_url"))
            for r in cached_records.values()
            if r.get("downloaded_url")
        } | {
            str(r.get("source_url"))
            for r in cached_records.values()
            if r.get("source_url")
        }
        seen_image_ids: set[str] = {
            str(r.get("image_id"))
            for r in cached_records.values()
            if r.get("image_id")
        }

        task_queue: queue.Queue = queue.Queue()
        result_queue: queue.Queue = queue.Queue()
        dedup_lock = threading.RLock()

        concept_state: dict[str, dict[str, Any]] = {}
        for c in concepts:
            cid = str(c["concept_id"])
            c_valid = sum(1 for r in valid if str(r.get("concept_id")) == cid)
            c_attempted = sum(1 for r in acquired if str(r.get("concept_id")) == cid)
            concept_state[cid] = {
                "concept_id": cid,
                "concept": c,
                "valid": c_valid,
                "attempted": c_attempted,
                "inflight": 0,
                "exhausted": False,
                "consecutive_empty": 0,
            }

        num_fetch_workers = 3

        def fetch_worker() -> None:
            while True:
                task = task_queue.get()
                if task is None:
                    task_queue.task_done()
                    break
                cid, concept, scheduled_amount, targeted_mode = task
                try:
                    allowed = (
                        targeted_allowed_sources(concept)
                        if targeted_mode
                        else (
                            ("open_images",)
                            if bool(concept.get("crop_required", False))
                            else ("met", "artic", "openverse")
                        )
                    )
                    records = acquire_for_concept(
                        concept=concept,
                        raw_dir=raw_dir,
                        max_count=scheduled_amount,
                        allowed_sources=allowed,
                        seen_hashes=seen_hashes,
                        seen_phashes=seen_phashes,
                        disk=disk,
                        stats=stats,
                        open_images=open_images,
                        seen_urls=seen_urls,
                        seen_image_ids=seen_image_ids,
                        dedup_lock=dedup_lock,
                        max_training_queries=(
                            TARGETED_MAX_TRAINING_QUERIES
                            if targeted_mode
                            else 3
                        ),
                    )
                    result_queue.put(
                        (
                            cid,
                            concept,
                            scheduled_amount,
                            targeted_mode,
                            records,
                            None,
                        )
                    )
                except Exception as exc:
                    result_queue.put(
                        (cid, concept, scheduled_amount, targeted_mode, [], exc)
                    )
                finally:
                    task_queue.task_done()

        threads = []
        for _ in range(num_fetch_workers):
            t = threading.Thread(target=fetch_worker, daemon=True)
            t.start()
            threads.append(t)

        def schedule_fetches() -> None:
            outstanding = sum(
                int(state["inflight"] > 0) for state in concept_state.values()
            )
            slots = max(0, 4 - outstanding)
            if slots <= 0:
                return

            global_deficit = desired_valid - len(valid)
            targeted_mode = global_deficit <= 0
            if targeted_mode:
                unavailable = {
                    cid
                    for cid, state in concept_state.items()
                    if state["exhausted"]
                }
                planned = select_targeted_recovery_concept_ids(
                    requirements=coverage_state,
                    concepts=concepts,
                    unavailable_concept_ids=unavailable,
                )
                active = [
                    concept_state[cid]
                    for cid in planned
                    if concept_state[cid]["inflight"] == 0
                ]
                active.sort(
                    key=lambda state: (
                        -_concept_recovery_priority(state["concept"]),
                        state["concept_id"],
                    )
                )
                for state in active[:slots]:
                    state["inflight"] += 2
                    task_queue.put(
                        (
                            state["concept_id"],
                            state["concept"],
                            2,
                            True,
                        )
                    )
                return

            active = [
                state
                for state in concept_state.values()
                if not state["exhausted"] and state["inflight"] == 0
            ]
            if not active:
                return
            active.sort(key=lambda state: state["valid"])
            base_target = max(8, math.ceil(desired_valid / max(1, len(concepts))))

            for s in active[:slots]:
                cid = s["concept_id"]
                c = s["concept"]
                if s["attempted"] > 0:
                    acc_rate = max(0.05, min(1.0, s["valid"] / s["attempted"]))
                else:
                    acc_rate = 0.25

                concept_deficit = base_target - s["valid"]
                if concept_deficit <= 0:
                    concept_deficit = max(
                        2, min(8, math.ceil(global_deficit / max(1, len(active))))
                    )

                needed_candidates = math.ceil(concept_deficit / acc_rate)
                schedule_amount = max(2, min(32, needed_candidates))
                s["inflight"] += schedule_amount
                task_queue.put((cid, c, schedule_amount, False))

        schedule_fetches()

        start_time = time.time()
        valid_at_start = len(valid)
        recovery_concepts_at_start = int(coverage_state["remainingConcepts"])
        last_checkpoint_time = time.time()
        benchmark_timed_out = False

        while not full_acquisition_complete(
            valid_count=len(valid),
            desired_valid=desired_valid,
            requirements=coverage_state,
        ):
            if (
                adaptive_benchmark_seconds is not None
                and time.time() - start_time >= adaptive_benchmark_seconds
            ):
                benchmark_timed_out = True
                break
            if not disk.before_download():
                break
            try:
                (
                    cid,
                    concept,
                    scheduled_amount,
                    targeted_mode,
                    records,
                    exc,
                ) = result_queue.get(timeout=2.0)
            except queue.Empty:
                if task_queue.empty() and all(
                    s["inflight"] == 0 for s in concept_state.values()
                ):
                    schedule_fetches()
                    if task_queue.empty() and all(
                        s["inflight"] == 0 for s in concept_state.values()
                    ):
                        print("No viable acquisition route remains for the current deficits.")
                        break
                    continue
                schedule_fetches()
                continue

            state = concept_state[cid]
            state["inflight"] = max(0, state["inflight"] - scheduled_amount)

            if exc is not None:
                state["consecutive_empty"] += 1
                if state["consecutive_empty"] >= 3:
                    state["exhausted"] = True
            elif len(records) == 0:
                state["consecutive_empty"] += 1
                if state["consecutive_empty"] >= 2:
                    state["exhausted"] = True
            else:
                state["attempted"] += len(records)
                for r in records:
                    with _CACHED_RECORDS_LOCK:
                        cached_records[str(r["content_sha256"])] = r
                acquired.extend(records)

                new_valid, _, cache_hits, pass_crop_stats = score_records_with_cache(
                    acquired=records,
                    concept_map=concept_map,
                    model=model,
                    processor=processor,
                    tokenizer=tokenizer,
                    device=resolved_device,
                    threshold=threshold,
                    cache=relevance_cache,
                    cache_path=relevance_cache_path,
                    cache_fingerprint=relevance_fingerprint,
                    disk=disk,
                    save_cache=False,
                )
                for key, value in pass_crop_stats.items():
                    crop_stats[key] += value
                valid.extend(new_valid)
                state["valid"] += len(new_valid)
                if targeted_mode and not new_valid:
                    state["consecutive_empty"] += 1
                    if state["consecutive_empty"] >= 2:
                        state["exhausted"] = True
                else:
                    state["consecutive_empty"] = 0

                coverage_state = full_visual_coverage_requirements(
                    records=valid,
                    concepts=concepts,
                )

                now = time.time()
                if (
                    targeted_mode
                    or now - last_checkpoint_time >= 10.0
                    or len(acquired) % 25 == 0
                ):
                    write_metadata_index(index_path, cached_records, disk=disk)
                    save_relevance_cache(
                        relevance_cache_path,
                        relevance_fingerprint,
                        relevance_cache,
                        disk,
                    )
                    persist_acquisition_state()
                    last_checkpoint_time = now

                elapsed = time.time() - start_time
                valid_gained = len(valid) - valid_at_start
                valid_per_sec = valid_gained / elapsed if elapsed > 0 else 0
                deficit_remaining = max(0, desired_valid - len(valid))
                eta_sec = deficit_remaining / valid_per_sec if valid_per_sec > 0 else None

                print(
                    f"Adaptive top-up: VALID={len(valid)} RAW={len(acquired)} cache_hits={cache_hits} "
                    f"(latest {cid}: fetched {len(records)} -> valid {len(new_valid)})"
                )
                if targeted_mode:
                    remaining = int(coverage_state["remainingConcepts"])
                    resolved = max(0, recovery_concepts_at_start - remaining)
                    resolved_per_min = resolved / max(elapsed / 60.0, 1e-9)
                    projected = (
                        remaining / resolved_per_min
                        if resolved_per_min > 0
                        else None
                    )
                    provider = (
                        str(records[0].get("source_id", "unknown"))
                        if records
                        else "none"
                    )
                    categories = " ".join(
                        f"{category}={details['coveredConcepts']}/"
                        f"{details['requiredCoveredConcepts']}"
                        for category, details in coverage_state[
                            "failingCategories"
                        ].items()
                    ) or "all=PASS"
                    print(
                        f"coverage: {categories} remaining_concepts={remaining} "
                        f"latest={cid} provider={provider} accepted={len(new_valid)} "
                        f"elapsed={elapsed:.1f}s projected_gate_eta="
                        f"{f'{projected:.1f}min' if projected is not None else 'unknown'}"
                    )
                if eta_sec is not None:
                    print(f"VALID/sec={valid_per_sec:.2f} ETA={eta_sec/60:.1f}min")

                report = _FUNNEL.summary()
                if report:
                    print(report)

            schedule_fetches()

        while not task_queue.empty():
            try:
                task_queue.get_nowait()
                task_queue.task_done()
            except (queue.Empty, ValueError):
                break
        for _ in threads:
            task_queue.put(None)
        for t in threads:
            t.join()
        if any(t.is_alive() for t in threads):
            raise RuntimeError("Acquisition worker threads failed to terminate cleanly")

        write_metadata_index(index_path, cached_records, disk=disk)
        save_relevance_cache(
            relevance_cache_path,
            relevance_fingerprint,
            relevance_cache,
            disk,
        )
        persist_acquisition_state()
        final_funnel = _FUNNEL.summary(force=True)
        if final_funnel:
            print(final_funnel)

        if adaptive_benchmark_seconds is not None:
            elapsed = max(time.time() - start_time, 1e-9)
            gained = len(valid) - valid_at_start
            with _FUNNEL._lock:
                funnel_metrics = {
                    provider: dict(values)
                    for provider, values in _FUNNEL.metrics.items()
                }
                siglip_seconds = _FUNNEL.siglip_seconds
            scored = sum(int(values["siglip_scored"]) for values in funnel_metrics.values())
            passed = sum(int(values["siglip_pass"]) for values in funnel_metrics.values())
            benchmark_summary = {
                "mode": "full-adaptive-benchmark",
                "testClassification": "REAL_FULL_ACQUISITION_BENCHMARK",
                "timedOut": benchmark_timed_out,
                "elapsedSeconds": elapsed,
                "currentValid": len(valid),
                "validAtStart": valid_at_start,
                "validGained": gained,
                "remainingTo2500": max(0, FULL_TARGET_UNIQUE_IMAGES - len(valid)),
                "validPerSecond": gained / elapsed,
                "siglipAcceptanceRate": passed / scored if scored else 0.0,
                "funnel": funnel_metrics,
                "siglipWallSeconds": siglip_seconds,
                "relevanceThreshold": threshold,
                "cacheRecords": len(cached_records),
            }
            benchmark_path = Path("ml/palettebrain/reports/candidate-11-adaptive-benchmark.json")
            guarded_atomic_write_text(
                benchmark_path,
                json.dumps(benchmark_summary, ensure_ascii=False, indent=2) + "\n",
                disk=disk,
            )
            print(json.dumps(benchmark_summary, ensure_ascii=False, indent=2))
            return benchmark_summary

        require_full_visual_coverage(coverage_state)
        if limit_images is None and len(valid) < FULL_MIN_UNIQUE_IMAGES:
            raise RuntimeError(
                f"FULL DATASET FAILED: {len(valid)} valid unique images "
                f"< hard minimum {FULL_MIN_UNIQUE_IMAGES}"
            )
        valid = select_balanced_full_records(valid, FULL_MAX_VALID_IMAGES)
        valid, final_crop_stats = process_acquired_records(
            acquired=valid,
            concept_map=concept_map,
        )
        if not valid:
            raise RuntimeError("no qualified images survived final image processing")
        crop_stats = final_crop_stats

    calibration_sha256 = sha256_file(calibration_path)

    visual_audit = audit_visual_coverage(
        records=valid,
        concepts=concepts,
        smoke=smoke,
    )

    features = np.stack([r["siglip_feature"] for r in valid]).astype(np.float32)
    teacher_latents, pca_diag = fit_pca(
        features=features,
        records=valid,
        smoke=smoke,
        output_dir=output_path.parent,
        disk=disk,
    )

    rows = build_rows(
        records=valid,
        teacher_latents=teacher_latents,
        concept_map=concept_map,
        smoke=smoke,
        seed=seed,
    )
    row_audit = audit_rows(rows, smoke=smoke)

    dataset_sha, dataset_bytes = save_dataset(
        output_path=output_path,
        rows=rows,
        relevance_threshold=threshold,
        pca_diagnostics=pca_diag,
        cache_dir=cache_dir,
        disk=disk,
        concepts_sha256=concepts_sha256,
        manifest_sha256=manifest_sha256,
        calibration_sha256=calibration_sha256,
        builder_sha256=builder_sha256,
    )

    source_counts = visual_audit["sourceCounts"]
    source_type_counts = visual_audit["sourceTypeCounts"]
    crop_required_final = sum(
        1
        for r in valid
        if bool(concept_map[str(r["concept_id"])].get("crop_required", False))
    )
    summary = {
        "mode": "smoke" if smoke else "full",
        "testClassification": "ENGINEERING_SMOKE_ONLY" if smoke else "REAL_TRAINING_DATA",
        "productionReady": False,
        "output": str(output_path).replace("\\", "/"),
        "sha256": dataset_sha,
        "bytes": dataset_bytes,
        "rawAcquired": len(acquired),
        "processedBeforeRelevance": len(processed),
        "validUniqueImages": len(valid),
        "preferredFullTarget": FULL_TARGET_UNIQUE_IMAGES,
        "hardFullMinimum": FULL_MIN_UNIQUE_IMAGES,
        "exactDuplicatesRejected": stats.get("exact_duplicates", 0),
        "nearDuplicatesRejected": stats.get("near_duplicates", 0),
        "invalidImagesRejected": stats.get("invalid_images", 0),
        "relevanceRejected": relevance_rejected,
        "relevanceThreshold": threshold,
        "sourceCounts": source_counts,
        "sourceTypeCounts": source_type_counts,
        "cropRequiredAcceptedBeforeRelevance": crop_stats[
            "crop_required_accepted_before_relevance"
        ],
        "cropRequiredSkippedNoValidCrop": crop_stats[
            "crop_required_skipped_no_valid_crop"
        ],
        "cropRequiredFinalValid": crop_required_final,
        "realBboxImages": visual_audit["realBboxImages"],
        "cropRequiredConcepts": visual_audit["cropRequiredConcepts"],
        "cropRequiredCoveredConcepts": visual_audit["cropRequiredCoveredConcepts"],
        "cropRequiredConceptCoverage": visual_audit["cropRequiredConceptCoverage"],
        "cropRequiredImageCounts": visual_audit["cropRequiredImageCounts"],
        "zeroImageConcepts": visual_audit["zeroImageConcepts"],
        "categoryCoverage": visual_audit["categoryCoverage"],
        "rows": len(rows),
        **row_audit,
        **pca_diag,
        "teacherModelId": SIGLIP_MODEL_ID,
        "teacherRevision": SIGLIP_REVISION,
        "e5ModelId": E5_MODEL_ID,
        "e5Revision": E5_REVISION,
        "transformersVersion": transformers.__version__,
        "siglipPreprocessing": preprocessing_audit,
        "conceptBankSha256": concepts_sha256,
        "sourceManifestSha256": manifest_sha256,
        "siglipCalibrationReportSha256": calibration_sha256,
        "builderSha256": builder_sha256,
        "diskUsageBytes": disk.usage(),
    }

    report_path = (
        Path("ml/palettebrain/reports")
        / (
            "candidate-11-source-smoke.json"
            if smoke
            else "candidate-11-source-full.json"
        )
    )
    guarded_atomic_write_text(
        report_path,
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        disk=disk,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare PaletteBrain Candidate 11 visual source dataset."
    )
    parser.add_argument(
        "--concepts",
        default="ml/palettebrain/c11_training_concepts.v1.json",
    )
    parser.add_argument(
        "--manifest",
        default="ml/palettebrain/c11_source_manifest.v1.json",
    )
    parser.add_argument(
        "--raw-dir",
        default="ml/palettebrain/data/raw_c11",
    )
    parser.add_argument(
        "--output",
        default="ml/palettebrain/data/palettebrain_c11_recovered_source.npz",
    )
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--limit-images", type=int, default=None)
    parser.add_argument("--seed", type=int, default=20260826)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--cache-dir", default="ml/.cache/hub")
    parser.add_argument("--calibration-min-tpr", type=float, default=0.85)
    parser.add_argument("--calibration-min-balanced-accuracy", type=float, default=0.80)
    parser.add_argument("--calibration-max-fpr", type=float, default=0.35)
    parser.add_argument("--download-workers", type=int, default=16)
    parser.add_argument("--metadata-workers", type=int, default=16)
    parser.add_argument("--checkpoint-every", type=int, default=10)
    parser.add_argument("--adaptive-benchmark-seconds", type=float)
    args = parser.parse_args()

    build_c11_dataset(
        concepts_path=Path(args.concepts),
        manifest_path=Path(args.manifest),
        raw_dir=Path(args.raw_dir),
        output_path=Path(args.output),
        smoke=bool(args.smoke),
        limit_images=args.limit_images,
        seed=int(args.seed),
        device=str(args.device),
        cache_dir=str(args.cache_dir),
        calibration_min_tpr=float(args.calibration_min_tpr),
        calibration_min_balanced_accuracy=float(args.calibration_min_balanced_accuracy),
        calibration_max_fpr=float(args.calibration_max_fpr),
        download_workers=int(args.download_workers),
        metadata_workers=int(args.metadata_workers),
        checkpoint_every=int(args.checkpoint_every),
        adaptive_benchmark_seconds=args.adaptive_benchmark_seconds,
    )


if __name__ == "__main__":
    main()
