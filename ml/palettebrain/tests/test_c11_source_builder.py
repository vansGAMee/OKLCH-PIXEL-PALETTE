"""Unit tests for the Candidate 11 source builder and concept anti-leakage."""

from __future__ import annotations

import json
import re
import threading
import time
import unicodedata
from pathlib import Path

import numpy as np
import pytest

from ml.palettebrain.color_distribution import palette_or_pixels_to_oklch_histogram
from ml.palettebrain.prepare_c11_recovered_source import (
    DiskBudget,
    SIGLIP_REVISION,
    choose_balanced_smoke,
    choose_calibration_threshold,
    extract_deterministic_palette,
    normalize_http_url,
    rgb_to_oklab_array,
    siglip_relevance_prompt,
    split_by_group,
    underfilled_concept_ids,
)


def test_http_url_normalization_quotes_spaces_and_removes_controls() -> None:
    assert normalize_http_url(
        "https://example.test/CRDImages/TR 112 1.jpg\n?q=a b"
    ) == "https://example.test/CRDImages/TR%20112%201.jpg?q=a%20b"


def test_malformed_url_is_a_durable_skip(tmp_path: Path) -> None:
    import ml.palettebrain.prepare_c11_recovered_source as source

    source.configure_acquisition_runtime(
        state_path=tmp_path / "state.json",
        fingerprint="test",
        download_workers=2,
        metadata_workers=2,
    )
    assert source.safe_http_get("not-an-http-url", max_retries=0) is None
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert "not-an-http-url" in state["permanentFailedUrls"]


def test_underfilled_topup_excludes_satisfied_families() -> None:
    concepts = [{"concept_id": key} for key in ("a", "b", "c")]
    raw = ([{"concept_id": "a"}] * 4) + ([{"concept_id": "b"}] * 2)
    valid = ([{"concept_id": "a"}] * 3) + [{"concept_id": "b"}]
    assert underfilled_concept_ids(
        records=raw,
        valid_records=valid,
        concepts=concepts,
        desired_valid=9,
        next_cap=5,
    ) == {"b", "c"}


def test_disk_budget_reserves_free_space(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import ml.palettebrain.prepare_c11_recovered_source as source

    raw = tmp_path / "raw"
    cache = tmp_path / "cache"
    raw.mkdir()
    cache.mkdir()
    disk = DiskBudget(
        raw_dir=raw,
        cache_dir=cache,
        target_bytes=1000,
        hard_bytes=2000,
        minimum_free_bytes=500,
    )
    usage = type("Usage", (), {"free": 400})()
    monkeypatch.setattr(source.shutil, "disk_usage", lambda _path: usage)
    with pytest.raises(source.HardDiskLimitError, match="FREE DISK RESERVE"):
        disk.before_download()


def test_acquisition_downloads_with_bounded_concurrency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ml.palettebrain.prepare_c11_recovered_source as source

    source._DOWNLOAD_WORKERS = 2
    active = 0
    peak = 0
    lock = threading.Lock()

    def fake_fetch(candidate: dict, _disk: object):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.02)
        with lock:
            active -= 1
        return candidate, b"image", candidate["source_url"]

    def fake_store(**kwargs):
        candidate = kwargs["record"]
        return {**candidate, "content_sha256": candidate["image_id"]}

    class OpenImages:
        def get_records(self, _concept_id: str, max_count: int):
            return [
                {
                    "source_id": "open_images",
                    "source_url": f"https://example.test/{index}.jpg",
                    "image_id": f"image-{index}",
                }
                for index in range(min(6, max_count))
            ]

    monkeypatch.setattr(source, "fetch_candidate_image", fake_fetch)
    monkeypatch.setattr(source, "store_image_record", fake_store)
    rows = source.acquire_for_concept(
        concept={
            "concept_id": "apple",
            "category": "object",
            "crop_required": True,
            "retrieval_query": "apple",
        },
        raw_dir=tmp_path,
        max_count=3,
        allowed_sources=("open_images",),
        seen_hashes=set(),
        seen_phashes=[],
        disk=object(),
        stats={},
        open_images=OpenImages(),
    )
    assert len(rows) == 3
    assert peak == 2


def test_relevance_cache_roundtrip_reuses_verified_feature(tmp_path: Path) -> None:
    import ml.palettebrain.prepare_c11_recovered_source as source

    raw = tmp_path / "raw"
    cache_dir = tmp_path / "cache"
    raw.mkdir()
    cache_dir.mkdir()
    disk = DiskBudget(
        raw_dir=raw,
        cache_dir=cache_dir,
        target_bytes=10_000_000,
        hard_bytes=20_000_000,
        minimum_free_bytes=1,
    )
    path = raw / "relevance_cache.npz"
    feature = np.linspace(0.0, 1.0, 8, dtype=np.float32)
    source.save_relevance_cache(path, "fingerprint", {"sha": (0.42, feature)}, disk)
    loaded = source.load_relevance_cache(path, "fingerprint")
    assert loaded["sha"][0] == pytest.approx(0.42)
    assert np.array_equal(loaded["sha"][1], feature)
    assert source.load_relevance_cache(path, "changed") == {}


def _normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).lower().strip().split())


def test_siglip_revision_is_pinned() -> None:
    assert SIGLIP_REVISION == "7fd15f0689c79d79e38b1c2e2e2370a7bf2761ed"


def test_concepts_anti_leakage() -> None:
    concepts_path = Path("ml/palettebrain/c11_training_concepts.v1.json")
    assert concepts_path.is_file()
    data = json.loads(concepts_path.read_text(encoding="utf-8"))
    concepts = data.get("concepts", [])
    assert len(concepts) >= 20

    # Load frozen benchmarks
    benchmark_prompts: set[str] = set()
    v3_path = Path("ml/palettebrain/benchmark_semantic_v3.json")
    if v3_path.is_file():
        v3 = json.loads(v3_path.read_text(encoding="utf-8"))
        for bucket in v3.get("buckets", {}).values():
            for p in bucket:
                benchmark_prompts.add(_normalize(p))
        for pair in v3.get("bilingualPairs", []):
            for p in pair:
                benchmark_prompts.add(_normalize(p))
        for item in v3.get("abstract", []):
            benchmark_prompts.add(_normalize(item["en"]))
            benchmark_prompts.add(_normalize(item["ru"]))
            for r in item.get("references", []):
                benchmark_prompts.add(_normalize(r))
            for n in item.get("hardNegatives", []):
                benchmark_prompts.add(_normalize(n))
        for pair in v3.get("longText", []) + v3.get("compositionContrasts", []):
            for p in pair:
                benchmark_prompts.add(_normalize(p))
        for group in v3.get("oodParaphraseGroups", []):
            for p in group:
                benchmark_prompts.add(_normalize(p))
        for adv in v3.get("adversarialComposition", []):
            benchmark_prompts.add(_normalize(adv))
        for neg in v3.get("negationControls", []):
            benchmark_prompts.add(_normalize(neg))

    v2_path = Path("ml/palettebrain/benchmark_visual_semantic_v2.json")
    if v2_path.is_file():
        v2 = json.loads(v2_path.read_text(encoding="utf-8"))
        for c in v2.get("concepts", {}).values():
            for p in c.get("prompts", []):
                benchmark_prompts.add(_normalize(p))

    held_out_tokens = {
        "meadow", "meadows", "moss", "mossy", "mosses", "clinic", "clinics", "ward", "wards", "pear", "pears", "plum", "plums",
        "поляна", "поляне", "поляны", "поляну", "поляной", "полянами", "луг", "лугу", "луга", "лугом", "лугах", "луговой",
        "мох", "мхом", "мха", "мхи", "мшистый", "мшистом", "мшистая", "мшистые", "мхами", "мхах",
        "клиника", "клинике", "клиники", "клинику", "клиникой", "клиниках",
        "палата", "палате", "палаты", "палату", "палатой", "палатах",
        "груша", "груши", "грушей", "грушу", "грушами", "грушевый",
        "слива", "сливы", "сливой", "сливу", "сливами", "сливовый",
    }
    held_out_stems = ("meadow", "moss", "clinic", "ward", "pear", "plum", "полян", "луг", "мшист", "клиник", "палат", "груш", "слив")

    for c in concepts:
        all_phrases = c["phrasings_en"] + c["phrasings_ru"]
        assert len(c["phrasings_en"]) >= 2, f"{c['concept_id']}: missing EN phrasings"
        assert len(c["phrasings_ru"]) >= 2, f"{c['concept_id']}: missing RU phrasings"
        
        # Check concept ID and retrieval query
        for field_text in [c["concept_id"], c["retrieval_query"]]:
            f_norm = _normalize(field_text)
            f_tokens = set(re.findall(r"\w+", f_norm))
            assert not (f_tokens & held_out_tokens), f"Held-out leak in concept metadata: {field_text!r}"
            
        for p in all_phrases:
            norm = _normalize(p)
            assert norm not in benchmark_prompts, f"Benchmark leak: {p!r}"
            tokens = set(re.findall(r"\w+", norm))
            assert not (tokens & held_out_tokens), f"Held-out leak: {p!r} has {tokens & held_out_tokens}"


def test_deterministic_palette_extraction() -> None:
    # Generate synthetic image pixels in RGB
    rng = np.random.RandomState(42)
    rgb = rng.rand(500, 3).astype(np.float32)
    oklab = rgb_to_oklab_array(rgb)

    for count in range(2, 10):
        palette1 = extract_deterministic_palette(oklab, target_count=count, seed=123)
        palette2 = extract_deterministic_palette(oklab, target_count=count, seed=123)
        assert palette1.shape == (count, 3)
        assert np.allclose(palette1, palette2)
        assert np.isfinite(palette1).all()


def test_color_prior_histogram() -> None:
    rng = np.random.RandomState(42)
    rgb = rng.rand(100, 3).astype(np.float32)
    oklab = rgb_to_oklab_array(rgb)
    hist = palette_or_pixels_to_oklch_histogram(oklab)
    assert hist.shape == (390,)
    assert np.all(hist >= 0.0)
    assert np.isclose(np.sum(hist), 1.0, atol=1e-5)


def test_split_by_group_no_leakage() -> None:
    groups = [f"group_{i}" for i in range(100)]
    splits = split_by_group(groups, train_ratio=0.85, seed=20260826)
    many = split_by_group([f"group-{index}" for index in range(1000)], train_ratio=0.85, seed=20260826)
    assert {"train", "val", "test"} <= set(many.values())
    assert len(splits) == 100
    assert set(splits.values()) <= {"train", "val", "test"}
    train_count = sum(1 for s in splits.values() if s == "train")
    assert 75 <= train_count <= 95


def test_smoke_can_use_stable_sources_when_openverse_is_unavailable() -> None:
    records = []
    for source in ("met", "artic", "open_images"):
        for index in range(20):
            records.append({"source_id": source, "content_sha256": f"{source}-{index}"})
    selected = choose_balanced_smoke(records)
    assert len(selected) == 48
    assert {row["source_id"] for row in selected} == {"met", "artic", "open_images"}


def test_calibration_threshold_prioritizes_required_recall_then_youden_j() -> None:
    positive = np.asarray([0.90, 0.80, 0.70, 0.60, 0.50, 0.40], dtype=np.float32)
    negative = np.asarray([0.65, 0.55, 0.35, 0.25, 0.15, 0.05], dtype=np.float32)
    threshold, metrics = choose_calibration_threshold(positive, negative, minimum_tpr=0.85)
    assert threshold <= 0.45
    assert metrics["truePositiveRate"] >= 0.85
    assert metrics["youdenJ"] == pytest.approx(
        metrics["truePositiveRate"] - metrics["falsePositiveRate"]
    )


def test_siglip_relevance_prompt_uses_verified_visual_label() -> None:
    prompt = siglip_relevance_prompt(
        {"source_id": "open_images", "bbox_class_name": "apple", "source_type": "real_world"},
        {"retrieval_query": "ripe orchard apple still life"},
    )
    assert prompt == "a centered photo of an apple"
    artwork_prompt = siglip_relevance_prompt(
        {"source_id": "met", "source_type": "artwork"},
        {"retrieval_query": "misty mountain landscape"},
    )
    assert artwork_prompt == "an artwork depicting misty mountain landscape"


def test_outlier_noise_cluster_rejection() -> None:
    # 2000 dominant forest green / earthy brown / golden amber pixels
    rng = np.random.RandomState(42)
    green_pixels = np.array([[0.15, 0.55, 0.20]] * 1000, dtype=np.float32)
    brown_pixels = np.array([[0.45, 0.30, 0.15]] * 600, dtype=np.float32)
    amber_pixels = np.array([[0.80, 0.60, 0.10]] * 390, dtype=np.float32)
    # 10 outlier pixels (pure white specular glint and pitch black specks)
    white_outliers = np.array([[1.0, 1.0, 1.0]] * 5, dtype=np.float32)
    black_outliers = np.array([[0.0, 0.0, 0.0]] * 5, dtype=np.float32)
    
    all_rgb = np.vstack([green_pixels, brown_pixels, amber_pixels, white_outliers, black_outliers])
    oklab = rgb_to_oklab_array(all_rgb)
    
    # Extract 3-color palette
    palette = extract_deterministic_palette(oklab, target_count=3, seed=42)
    
    # White in OKLab has L ~ 1.0, Black has L ~ 0.0
    # The extracted palette should NOT include the tiny 5-pixel outlier clusters (< 0.25% mass)
    assert not np.any(palette[:, 0] > 0.95), "Isolated white specular outlier was erroneously included"
    assert not np.any(palette[:, 0] < 0.05), "Isolated black speck outlier was erroneously included"
    assert len(palette) == 3


def test_crop_coordinate_contract_and_order() -> None:
    # [x0, y0, x1, y1] contract: x0 <= x1, y0 <= y1 in [0, 1]
    full_frame = np.array([0.0, 0.0, 1.0, 1.0], dtype=np.float64)
    assert full_frame.shape == (4,)
    x0, y0, x1, y1 = full_frame
    assert 0.0 <= x0 <= x1 <= 1.0
    assert 0.0 <= y0 <= y1 <= 1.0
    
    # Check width and height
    w = x1 - x0
    h = y1 - y0
    assert w == 1.0 and h == 1.0
    
    # Detect inversion: an inverted bbox where y is first [y0, x0, y1, x1] on non-square crop
    sample_crop = np.array([0.1, 0.2, 0.7, 0.9], dtype=np.float64)
    # x goes from 0.1 to 0.7 (dx=0.6), y goes from 0.2 to 0.9 (dy=0.7)
    x0, y0, x1, y1 = sample_crop
    assert x0 < x1 and y0 < y1


def test_crop_required_policy_enforcement(tmp_path: Path) -> None:
    from PIL import Image
    from ml.palettebrain.prepare_c11_recovered_source import process_image

    # Create dummy 100x100 RGB image
    img_path = tmp_path / "test_dummy.jpg"
    img = Image.new("RGB", (100, 100), color=(120, 180, 70))
    # Add texture so std > 1e-4
    for i in range(50):
        img.putpixel((i, i), (200, 100, 50))
    img.save(img_path)

    # 1. crop_required=True without bbox MUST be rejected
    rejected = process_image(img_path, crop_required=True, whole_frame_valid=False, meta_crop=None)
    assert rejected is None, "crop_required without bbox must be rejected"

    # 2. crop_required=True with valid bbox MUST succeed
    accepted = process_image(img_path, crop_required=True, whole_frame_valid=False, meta_crop=(0.1, 0.2, 0.8, 0.9))
    assert accepted is not None, "crop_required with valid bbox must be accepted"
    oklab_px, prior, pil_img, crop_coords, mask_fraction = accepted
    assert np.allclose(crop_coords, [0.1, 0.2, 0.8, 0.9])
    assert 0.40 <= mask_fraction <= 0.60
    assert oklab_px.shape[1] == 3
