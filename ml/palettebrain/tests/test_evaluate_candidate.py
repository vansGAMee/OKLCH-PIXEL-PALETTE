from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch

from ml.palettebrain.color_math import representation_to_oklab_numpy
from ml.palettebrain.dataset import seed_noise_from_uint32
from ml.palettebrain.evaluate_candidate import (
    GenerationRequest,
    LoadedCandidate,
    build_release_decision,
    collect_benchmark_texts,
    evaluate_candidate,
    select_real_holdout_mask,
    summarize_engineering_contract,
)


class TinyRawDecoder(torch.nn.Module):
    """Deterministic count-native decoder used without importing or loading E5."""

    def __init__(self) -> None:
        super().__init__()
        self.bias = torch.nn.Parameter(torch.tensor(0.0))

    def forward(
        self,
        text_embedding: torch.Tensor,
        count_mask: torch.Tensor,
        seed_noise: torch.Tensor,
        locked_mask: torch.Tensor,
        locked_colors: torch.Tensor,
    ) -> torch.Tensor:
        del text_embedding, seed_noise, locked_mask, locked_colors
        batch = count_mask.shape[0]
        raw = torch.zeros((batch, 9, 5), device=count_mask.device)
        raw[..., 0] = self.bias
        raw[..., 1] = self.bias
        raw[..., 3] = 1.0
        raw[..., 4] = 0.5
        return raw * count_mask.unsqueeze(-1)


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _tiny_fixtures(tmp_path: Path) -> tuple[Path, Path, Path]:
    representative = np.zeros((1, 1, 5), dtype=np.float32)
    representative[..., 3] = 1.0
    prototype = representation_to_oklab_numpy(representative)[0, 0].tolist()
    color = {
        "schemaVersion": 1,
        "benchmarkVersion": "tiny-colors-v1",
        "defaultCount": 2,
        "seeds": [1, 7],
        "thresholds": {
            "anchorOklabDistance": 0.01,
            "chromaticChroma": 0.01,
            "stronglyUnrelatedOklabDistance": 0.2,
            "maximumUnrelatedChromaticRatio": 0.25,
            "exclusionOklabDistance": 0.005,
            "nearDuplicateOklabDistance": 0.025,
            "blackMaximumLightness": 0.2,
            "whiteMinimumLightness": 0.85,
            "neutralMaximumChroma": 0.04,
            "grayMinimumLightness": 0.3,
            "grayMaximumLightness": 0.75,
        },
        "families": {
            "red": {"kind": "chromatic", "oklabPrototypes": [prototype]},
        },
        "prompts": [
            {
                "id": "red-en",
                "prompt": "red",
                "language": "en",
                "required": ["red"],
                "standalone": True,
            },
            {
                "id": "red-ru",
                "prompt": "красный",
                "language": "ru",
                "required": ["red"],
                "standalone": True,
            },
        ],
    }
    semantic = {
        "schemaVersion": 1,
        "benchmarkVersion": "tiny-semantic-v1",
        "defaultCount": 2,
        "seeds": [1, 7],
        "modifierPairs": [["red", "dark red"]],
        "translationPairs": [["red", "красный"]],
        "requiredSanityOutputs": ["red", "красный", "dark red"],
    }
    evaluation = {
        "schemaVersion": 1,
        "configHash": "frozen-tiny-config",
        "fixtures": {},
        "releaseTargets": {
            "rawDirectColorRate": 0.95,
            "exactCountRate": 1.0,
            "inactiveSlotRate": 1.0,
            "srgbGamutRate": 1.0,
            "determinismRate": 1.0,
            "maximumNearDuplicatePaletteRate": 0.05,
        },
    }
    color_path = tmp_path / "colors.json"
    semantic_path = tmp_path / "semantic.json"
    evaluation_path = tmp_path / "evaluation.json"
    _write_json(color_path, color)
    _write_json(semantic_path, semantic)
    _write_json(evaluation_path, evaluation)
    return color_path, semantic_path, evaluation_path


def _tiny_data(path: Path) -> None:
    rows = 3
    counts = np.full(rows, 2, dtype=np.int64)
    count_masks = (np.arange(9)[None, :] < counts[:, None]).astype(np.float32)
    embeddings = np.zeros((rows, 384), dtype=np.float32)
    embeddings[:, 0] = 1.0
    targets = np.zeros((rows, 9, 5), dtype=np.float32)
    targets[..., 3] = count_masks
    targets[..., 4] = 0.5 * count_masks
    locked_masks = np.zeros((rows, 9), dtype=np.float32)
    locked_masks[0, 0] = 1.0
    locked_colors = np.zeros((rows, 9, 4), dtype=np.float32)
    locked_physical = representation_to_oklab_numpy(targets[:1])[0, 0]
    locked_chroma = float(np.linalg.norm(locked_physical[1:3]))
    locked_colors[0, 0] = [
        locked_physical[0],
        locked_chroma,
        0.0,
        1.0,
    ]
    np.savez_compressed(
        path,
        embeddings=embeddings,
        counts=counts,
        seeds=np.asarray([1, 1, 1], dtype=np.uint32),
        count_masks=count_masks,
        seed_noise=np.stack([seed_noise_from_uint32(1)] * rows),
        locked_masks=locked_masks,
        locked_colors=locked_colors,
        targets=targets,
        splits=np.full(rows, 2, dtype=np.int8),
        holdout_eligible=np.asarray([True, False, False]),
        sources=np.asarray(["wada", "direct_anchors", "legacy_synthetic"]),
        palette_origins=np.asarray(
            ["human_curated", "direct_color_anchor", "synthetic"]
        ),
        text_origins=np.asarray(["curated", "anchor", "synthetic"]),
        prompt_kinds=np.asarray(["title", "direct", "synthetic"]),
        semantic_alignments=np.asarray(["strong", "strong", "weak"]),
        licenses=np.asarray(["CC0", "CC0", "internal"]),
        native_counts=np.asarray([2, 2, 2], dtype=np.int64),
        derived_counts=np.asarray([False, False, False]),
        metadata_json=np.asarray(
            json.dumps(
                {
                    "datasetVersion": "tiny-v1",
                    "kind": "test_fixture",
                    "contentHash": "tiny-content",
                }
            )
        ),
    )


def test_collect_benchmark_texts_deduplicates_overlapping_groups() -> None:
    result = collect_benchmark_texts(
        {"prompts": [{"prompt": "red"}, {"prompt": "красный"}]},
        {
            "modifierPairs": [["red", "dark red"]],
            "translationPairs": [["red", "красный"]],
            "requiredSanityOutputs": ["red", "dark red"],
        },
    )

    assert result["all"] == ["red", "красный", "dark red"]


def test_engineering_contract_catches_an_inactive_slot_leak_by_count() -> None:
    requests = [GenerationRequest("red", 1, count) for count in range(2, 10)]
    raw = np.zeros((8, 9, 5), dtype=np.float32)
    for row, request in enumerate(requests):
        raw[row, : request.count, 3] = 1.0
    raw[1, 8, 0] = 0.01
    palettes = [
        representation_to_oklab_numpy(raw[index : index + 1, : request.count])[0]
        for index, request in enumerate(requests)
    ]

    summary = summarize_engineering_contract(requests, raw, raw.copy(), palettes)

    assert summary["byCount"]["2"]["inactiveExactZeroRate"] == 1.0
    assert summary["byCount"]["3"]["inactiveExactZeroRate"] == 0.0
    assert summary["byCount"]["3"]["exactActiveMaskRate"] == 0.0
    assert summary["overall"]["sameSeedExactDeterminismRate"] == 1.0


def test_holdout_eligible_is_intersected_with_verified_real_provenance() -> None:
    mask, evidence = select_real_holdout_mask(
        {
            "splits": np.asarray([2, 2, 1, 2], dtype=np.int8),
            "holdout_eligible": np.asarray([True, False, True, True]),
            "palette_origins": np.asarray(
                ["human_curated", "human_curated", "human_curated", "synthetic"]
            ),
        }
    )

    np.testing.assert_array_equal(mask, [True, False, False, False])
    assert evidence["selectionMode"] == "holdout_eligible_provenance_and_test_split"
    assert evidence["eligibleProvenanceViolationRows"] == 1
    assert evidence["provenanceIntegrityPassed"] is False


def test_release_gate_rejects_dropped_nonfinite_holdout_rows() -> None:
    decision = build_release_decision(
        {
            "rawDirectColorRate": 0.95,
            "exactCountRate": 1.0,
            "inactiveSlotRate": 1.0,
            "srgbGamutRate": 1.0,
            "determinismRate": 1.0,
            "maximumNearDuplicatePaletteRate": 0.05,
        },
        {"aggregate": {"raw_direct_color": {"accuracy": 1.0}}},
        {
            "overall": {
                "exactCountRate": 1.0,
                "inactiveExactZeroRate": 1.0,
                "finiteActiveRate": 1.0,
                "srgbGamutPaletteRate": 1.0,
                "sameSeedExactDeterminismRate": 1.0,
            }
        },
        {"rate": 0.0},
        {
            "status": "evaluated",
            "validPredictionRows": 1,
            "invalidPredictionRows": 9,
            "validPredictionRate": 0.1,
            "selection": {"provenanceIntegrityPassed": True},
            "learnedLockCompletion": {"caseCount": 1},
        },
        {},
    )

    assert decision["frozenNumericGates"]["realHoldoutFiniteOutputs"]["passed"] is False
    assert "realHoldoutFiniteOutputs" in decision["failedOrUnevaluatedGates"]


def test_full_evaluation_uses_injected_embedder_and_never_promotes(
    tmp_path: Path,
) -> None:
    color_path, semantic_path, evaluation_path = _tiny_fixtures(tmp_path)
    data_path = tmp_path / "candidate.npz"
    checkpoint_path = tmp_path / "candidate.pt"
    output_path = tmp_path / "evaluation-output.json"
    _tiny_data(data_path)
    checkpoint_path.write_bytes(b"tiny checkpoint hash fixture")
    calls: list[list[str]] = []

    def embedding_provider(texts: list[str]) -> np.ndarray:
        calls.append(list(texts))
        values = np.zeros((len(texts), 384), dtype=np.float32)
        values[:, 0] = 1.0
        return values

    report = evaluate_candidate(
        checkpoint_path=checkpoint_path,
        data_path=data_path,
        output_path=output_path,
        device="cpu",
        cache_dir=tmp_path / "unused-e5-cache",
        model_label="tiny-test-candidate",
        color_fixture_path=color_path,
        semantic_fixture_path=semantic_path,
        evaluation_config_path=evaluation_path,
        embedding_provider=embedding_provider,
        loaded_candidate=LoadedCandidate(
            model=TinyRawDecoder(),
            checkpoint={
                "model_config": {"fixture": "tiny"},
                "production_ready": False,
            },
        ),
        batch_size=8,
    )

    assert calls == [["red", "красный", "dark red"]]
    assert report["benchmarkCoverage"]["decoderRequests"] == 3 * 2 * 8
    assert report["directColor"]["aggregate"]["raw_direct_color"][
        "accuracy"
    ] == 1.0
    assert report["directColor"]["aggregate"]["required_family"][
        "accuracy"
    ] == 1.0
    assert report["directColor"]["aggregate"]["standalone_consistency"][
        "accuracy"
    ] == 1.0
    assert report["engineering"]["overall"]["exactCountRate"] == 1.0
    assert report["realPaletteHoldout"]["selection"]["selectedRows"] == 1
    assert report["realPaletteHoldout"]["matchedOklab"]["mean_distance"] == 0.0
    assert report["realPaletteHoldout"]["learnedLockCompletion"]["caseCount"] == 1
    assert report["releaseDecision"]["releaseReady"] is False
    assert report["productionReady"] is False
    assert report["promotionPerformed"] is False
    assert output_path.is_file()
    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert '"productionReady": true' not in output_path.read_text(encoding="utf-8")
    assert persisted["sanityOutputs"]["seed"] == 1
    assert all(
        row["hex"] is not None
        for row in persisted["sanityOutputs"]["palettes"]
    )
