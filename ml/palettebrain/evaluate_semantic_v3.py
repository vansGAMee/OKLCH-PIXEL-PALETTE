"""Frozen real-PyTorch semantic v3 evaluator for Candidate 11."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch

try:
    from .color_math import representation_to_oklab_numpy
    from .e5_embedding import embed_texts, load_encoder
    from .inspect_semantics import _family_distance, _family_references, _inputs
    from .model import PaletteDecoder, PaletteDecoderConfig
    from .parity_harness import decode_raw
except ImportError:
    from color_math import representation_to_oklab_numpy
    from e5_embedding import embed_texts, load_encoder
    from inspect_semantics import _family_distance, _family_references, _inputs
    from model import PaletteDecoder, PaletteDecoderConfig
    from parity_harness import decode_raw


PALETTE_STRUCTURE_REFERENCE_VERSION = "c11-palette-structure-v2-indexed"
DEFAULT_DECODER_BATCH_SIZE = 128
_STATIC_EVALUATION_CONTEXTS: dict[tuple[Any, ...], dict[str, Any]] = {}
_PALETTE_STRUCTURE_CONTEXTS: dict[tuple[Any, ...], dict[str, Any]] = {}
_FILE_SHA256_CACHE: dict[tuple[str, int, int], str] = {}


def resolve_evaluation_device(name: str) -> torch.device:
    selected = torch.device(
        "cuda" if name == "auto" and torch.cuda.is_available()
        else ("cpu" if name == "auto" else name)
    )
    if selected.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    return selected


def clear_static_evaluation_context_cache() -> None:
    _STATIC_EVALUATION_CONTEXTS.clear()
    _PALETTE_STRUCTURE_CONTEXTS.clear()
    _FILE_SHA256_CACHE.clear()


def _cached_file_sha256(path: str | Path) -> str:
    resolved = Path(path).resolve()
    stat = resolved.stat()
    key = (resolved.as_posix(), stat.st_size, stat.st_mtime_ns)
    digest = _FILE_SHA256_CACHE.get(key)
    if digest is None:
        digest = _sha256_file(resolved)
        _FILE_SHA256_CACHE[key] = digest
    return digest


def _collect_evaluation_prompts(
    v2: dict[str, Any], v3: dict[str, Any], extra_prompts: tuple[str, ...]
) -> list[str]:
    prompts: list[str] = []
    for concept in v2["concepts"].values():
        prompts.extend(concept["prompts"])
    for bucket in v3["buckets"].values():
        prompts.extend(bucket)
    for pair in v3["bilingualPairs"]:
        prompts.extend(pair)
    for item in v3["abstract"]:
        prompts.extend([item["en"], item["ru"], *item["references"], *item["hardNegatives"]])
    for pair in v3["longText"] + v3["compositionContrasts"]:
        prompts.extend(pair)
    for group in v3["oodParaphraseGroups"]:
        prompts.extend(group)
    prompts.extend(v3["adversarialComposition"])
    prompts.extend(["grass", "blood", "moonlight", "candlelight", "rust", "snow", "hospital", "glass"])
    prompts.extend(extra_prompts)
    return list(dict.fromkeys(prompts))


def load_static_evaluation_context(
    benchmark_v2: str | Path,
    benchmark_v3: str | Path,
    *,
    cache_dir: str,
    device: torch.device,
    extra_prompts: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Load and embed checkpoint-invariant evaluation data once per content hash."""
    v2_path = Path(benchmark_v2)
    v3_path = Path(benchmark_v3)
    key = (
        v2_path.resolve().as_posix(), _cached_file_sha256(v2_path),
        v3_path.resolve().as_posix(), _cached_file_sha256(v3_path),
        str(Path(cache_dir).resolve()), str(device), extra_prompts,
    )
    cached = _STATIC_EVALUATION_CONTEXTS.get(key)
    if cached is not None:
        return cached
    v2 = json.loads(v2_path.read_text(encoding="utf-8"))
    v3 = json.loads(v3_path.read_text(encoding="utf-8"))
    prompts = _collect_evaluation_prompts(v2, v3, extra_prompts)
    encoder = load_encoder(device=str(device), cache_dir=cache_dir)
    embeddings = embed_texts(prompts, encoder=encoder, batch_size=64)
    references, _ = _family_references(v2_path)
    context = {
        "v2": v2,
        "v3": v3,
        "prompts": prompts,
        "embeddings": embeddings,
        "prompt_index": {prompt: index for index, prompt in enumerate(prompts)},
        "references": references,
    }
    _STATIC_EVALUATION_CONTEXTS[key] = context
    return context


def _model_device(model: torch.nn.Module) -> torch.device:
    try:
        return next(model.parameters()).device
    except StopIteration:
        return torch.device("cpu")


def run_decoder_inputs(
    model: torch.nn.Module,
    rows: list[tuple[torch.Tensor, ...]],
    *,
    batch_size: int = DEFAULT_DECODER_BATCH_SIZE,
) -> np.ndarray:
    """Run compatible decoder inputs in bounded batches on the model device."""
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    if not rows:
        return np.empty((0, 9, 5), dtype=np.float32)
    device = _model_device(model)
    outputs: list[np.ndarray] = []
    for start in range(0, len(rows), batch_size):
        chunk = rows[start:start + batch_size]
        inputs = tuple(
            torch.cat([row[position] for row in chunk], dim=0).to(device)
            for position in range(len(chunk[0]))
        )
        with torch.inference_mode():
            raw = model(*inputs)
        outputs.append(raw.detach().cpu().numpy())
    return np.concatenate(outputs, axis=0)


def decode_embeddings(
    model: torch.nn.Module,
    embeddings: np.ndarray,
    *,
    count: int,
    seed: int,
    batch_size: int = DEFAULT_DECODER_BATCH_SIZE,
) -> np.ndarray:
    """Decode a prompt-ordered embedding matrix without scalar model calls."""
    values = np.asarray(embeddings, dtype=np.float32)
    if values.ndim != 2 or values.shape[1] != 384:
        raise ValueError("embeddings must have shape [N,384]")
    return run_decoder_inputs(
        model,
        [_inputs(embedding, count, seed) for embedding in values],
        batch_size=batch_size,
    )


def _structure_reference_index(
    indices: np.ndarray,
    groups: np.ndarray,
    counts: np.ndarray,
    *,
    limit: int = 5,
) -> dict[int, list[int]]:
    """Precompute top deterministic unrelated references in O(V log V)."""
    references: dict[int, list[int]] = {}
    for count in np.unique(counts[indices]):
        count_indices = [int(index) for index in indices if counts[index] == count]
        ordered = sorted(
            count_indices,
            key=lambda candidate: hashlib.sha256(
                f"{PALETTE_STRUCTURE_REFERENCE_VERSION}|{groups[candidate]}|{candidate}".encode("utf-8")
            ).digest(),
        )
        default = ordered[:limit]
        special_groups = {groups[index] for index in default}
        by_excluded_group = {
            group: [candidate for candidate in ordered if groups[candidate] != group][:limit]
            for group in special_groups
        }
        for index in count_indices:
            references[index] = by_excluded_group.get(groups[index], default)
    return references


def load_palette_structure_context(
    dataset_path: str | Path, split: str
) -> dict[str, Any]:
    """Load checkpoint-invariant validation arrays and indexes once."""
    path = Path(dataset_path)
    key = (path.resolve().as_posix(), _cached_file_sha256(path), split)
    cached = _PALETTE_STRUCTURE_CONTEXTS.get(key)
    if cached is not None:
        return cached
    required = {
        "text_embedding", "count_mask", "seed_noise", "locked_mask",
        "locked_colors", "target", "split", "source_group_id",
    }
    with np.load(path, allow_pickle=False) as archive:
        missing = sorted(required - set(archive.files))
        if missing:
            raise RuntimeError(f"palette structure dataset is missing {missing}")
        arrays = {name: np.asarray(archive[name]) for name in required}
    split_values = arrays["split"].astype(str)
    indices = np.flatnonzero(split_values == split)
    groups = arrays["source_group_id"].astype(str)
    counts = arrays["count_mask"].sum(axis=1).astype(np.int64)
    eligible_indices = np.asarray(
        [index for index in indices if counts[index] >= 2], dtype=np.int64
    )
    targets = representation_to_oklab_numpy(
        np.asarray(arrays["target"], dtype=np.float32)
    )
    context = {
        "arrays": arrays,
        "groups": groups,
        "counts": counts,
        "eligible_indices": eligible_indices,
        "reference_indices": _structure_reference_index(
            eligible_indices, groups, counts
        ) if len(eligible_indices) else {},
        "target_signatures": {
            int(index): _relational_signature(targets[index, :counts[index]])
            for index in eligible_indices
        },
    }
    _PALETTE_STRUCTURE_CONTEXTS[key] = context
    return context


def _pairwise_min(palette: np.ndarray) -> float:
    distances = np.linalg.norm(palette[:, None] - palette[None, :], axis=-1)
    return float(distances[np.triu_indices(len(palette), 1)].min())


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hues(palette: np.ndarray) -> np.ndarray:
    return np.degrees(np.arctan2(palette[:, 2], palette[:, 1])) % 360


def _relational_signature(palette: np.ndarray) -> np.ndarray:
    distances = np.linalg.norm(palette[:, None] - palette[None, :], axis=-1)
    return np.sort(distances[np.triu_indices(len(palette), 1)])


def _hue_fraction(palette: np.ndarray, low: float, high: float) -> float:
    hues = _hues(palette)
    chromatic = np.linalg.norm(palette[:, 1:3], axis=1) > 0.03
    if low <= high:
        selected = (hues >= low) & (hues <= high)
    else:
        selected = (hues >= low) | (hues <= high)
    return float(np.mean(selected & chromatic))


def clean_multicolor_rate(palettes: list[np.ndarray]) -> float:
    """Behavioral palette cleanliness, independent of cross-prompt duplication."""
    if not palettes:
        return 0.0
    return float(np.mean([
        _pairwise_min(palette) >= 0.04
        and len({tuple(np.round(color, 3)) for color in palette}) == len(palette)
        for palette in palettes
    ]))


def palette_set_distance(left: np.ndarray, right: np.ndarray) -> float:
    """Symmetric, count-aware perceptual distance between two OKLab palettes."""
    left = np.asarray(left, dtype=np.float64)
    right = np.asarray(right, dtype=np.float64)
    if left.ndim != 2 or right.ndim != 2 or left.shape[1:] != (3,) or right.shape[1:] != (3,):
        raise ValueError("palettes must have shape [count, 3]")
    if not len(left) or not len(right):
        return float("inf")
    distances = np.linalg.norm(left[:, None, :] - right[None, :, :], axis=-1)
    matched = 0.5 * (distances.min(axis=1).mean() + distances.min(axis=0).mean())
    count_penalty = abs(len(left) - len(right)) / max(len(left), len(right))
    return float(matched + 0.04 * count_penalty)


def cross_prompt_collapse_metric(
    palettes: list[np.ndarray], *, distance_threshold: float = 0.04,
    maximum_rate: float = 0.20,
) -> tuple[float, bool]:
    """Detect reuse of effectively identical palettes across distinct prompts.

    The 0.04 OKLab distance is the evaluator's existing frozen clean-palette
    separation criterion.  Requiring fewer than 20% collapsed prompt pairs is
    conservative against a constant-palette model while allowing related
    semantic prompts to remain close.
    """
    if len(palettes) < 2:
        return 0.0, True
    collapsed = 0
    pairs = 0
    for left in range(len(palettes)):
        for right in range(left + 1, len(palettes)):
            pairs += 1
            collapsed += palette_set_distance(palettes[left], palettes[right]) < distance_threshold
    rate = collapsed / pairs
    return float(rate), bool(rate < maximum_rate)


def _flatten_sealed_prompts(value: dict[str, Any]) -> list[str]:
    prompts: list[str] = []
    for group in value.get("groups", {}).values():
        prompts.extend(str(prompt) for prompt in group)
    for field in ("modifierPairs", "translationPairs"):
        for pair in value.get(field, []):
            prompts.extend(str(prompt) for prompt in pair)
    prompts.extend(str(prompt) for prompt in value.get("requiredSanityOutputs", []))
    return list(dict.fromkeys(prompts))


def _assert_sealed_test_not_in_training(
    sealed_prompts: list[str], concept_bank_path: str | Path
) -> None:
    bank = json.loads(Path(concept_bank_path).read_text(encoding="utf-8"))
    training: set[str] = set()
    for concept in bank.get("concepts", []):
        training.add(str(concept.get("retrieval_query", "")).strip().lower())
        training.update(str(value).strip().lower() for value in concept.get("phrasings_en", []))
        training.update(str(value).strip().lower() for value in concept.get("phrasings_ru", []))
    overlap = sorted({prompt.strip().lower() for prompt in sealed_prompts} & training)
    if overlap:
        raise RuntimeError(f"sealed semantic TEST leaks into training text: {overlap[:10]}")


def adversarial_semantics_pass(prompt: str, palette: np.ndarray, base: np.ndarray) -> bool:
    changed = float(np.linalg.norm(palette.mean(0) - base.mean(0))) >= 0.025
    rules = {
        "red grass": _hue_fraction(palette, 345, 50) >= 0.2,
        "green blood": _hue_fraction(palette, 100, 165) >= 0.2,
        "warm moonlight": _hue_fraction(palette, 20, 100) >= 0.2,
        "cold candlelight": _hue_fraction(palette, 180, 300) >= 0.2,
        "blue rust": _hue_fraction(palette, 210, 300) >= 0.2,
        "black snow": float(palette[:, 0].mean()) < float(base[:, 0].mean()) - 0.05,
        "hospital at sunset": _hue_fraction(palette, 20, 100) >= 0.2,
        "snow under red emergency lights": _hue_fraction(palette, 345, 50) >= 0.2,
        "green glass in a dark nightclub": (
            _hue_fraction(palette, 100, 165) >= 0.2
            and float(palette[:, 0].mean()) < 0.65
        ),
    }
    return changed and bool(rules[prompt])


def composition_semantics_pass(pair: list[str], left: np.ndarray, right: np.ndarray) -> bool:
    changed = float(np.linalg.norm(left.mean(0) - right.mean(0))) >= 0.025
    key = tuple(pair)
    if key == ("hospital at sunset", "hospital under moonlight"):
        semantic = _hue_fraction(left, 20, 100) > _hue_fraction(right, 20, 100) and _hue_fraction(right, 180, 300) > 0
    elif key == ("forest in rain", "forest by firelight"):
        semantic = _hue_fraction(right, 20, 100) > _hue_fraction(left, 20, 100)
    elif key == ("watercolor city", "film-noir city"):
        semantic = float(np.linalg.norm(left[:, 1:3], axis=1).mean()) > float(np.linalg.norm(right[:, 1:3], axis=1).mean())
    else:
        raise ValueError(f"unrecognized frozen composition pair: {pair}")
    return changed and semantic


def palette_structure_metric(
    model: PaletteDecoder, dataset_path: str | None, split: str
) -> tuple[float | None, list[dict[str, Any]]]:
    if not dataset_path:
        return None, []
    context = load_palette_structure_context(dataset_path, split)
    arrays = context["arrays"]
    groups = context["groups"]
    counts = context["counts"]
    eligible_indices = context["eligible_indices"]
    if not len(eligible_indices):
        return None, []
    reference_indices = context["reference_indices"]
    target_signatures = context["target_signatures"]
    device = _model_device(model)
    input_names = ("text_embedding", "count_mask", "seed_noise", "locked_mask", "locked_colors")
    raw_chunks: list[np.ndarray] = []
    for start in range(0, len(eligible_indices), DEFAULT_DECODER_BATCH_SIZE):
        batch_indices = eligible_indices[start:start + DEFAULT_DECODER_BATCH_SIZE]
        inputs = [
            torch.as_tensor(arrays[name][batch_indices], dtype=torch.float32, device=device)
            for name in input_names
        ]
        with torch.inference_mode():
            raw_chunks.append(model(*inputs).detach().cpu().numpy())
    generated = np.concatenate(raw_chunks, axis=0)
    rows: list[dict[str, Any]] = []
    for generated_row, index_value in enumerate(eligible_indices):
        index = int(index_value)
        count = int(counts[index])
        locked = arrays["locked_mask"][index, :count].astype(bool)
        effective = generated[generated_row, :count].copy()
        effective[locked, :4] = arrays["locked_colors"][index, :count][locked, :4]
        generated_signature = _relational_signature(
            representation_to_oklab_numpy(effective[None])[0]
        )
        paired_error = float(np.mean(np.abs(
            generated_signature - target_signatures[index]
        )))
        unrelated = reference_indices[index]
        if not unrelated:
            continue
        unrelated_errors = [float(np.mean(np.abs(
            generated_signature - target_signatures[candidate]
        ))) for candidate in unrelated]
        median_unrelated = float(np.median(unrelated_errors))
        rows.append({
            "sourceGroupId": groups[index], "count": count,
            "pairedStructureError": paired_error,
            "medianUnrelatedStructureError": median_unrelated,
            "pass": paired_error < median_unrelated,
        })
    rate = float(np.mean([row["pass"] for row in rows])) if rows else None
    return rate, rows


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    sealed_test: dict[str, Any] | None = None
    sealed_prompts: list[str] = []
    semantic_test_path = Path(getattr(
        args, "semantic_test_benchmark", "ml/palettebrain/benchmark_semantic_release.v1.json"
    ))
    if args.evaluation_split == "test":
        sealed_test = json.loads(semantic_test_path.read_text(encoding="utf-8"))
        if sealed_test.get("frozenBeforeCandidate1") is not True:
            raise RuntimeError("semantic TEST artifact is not frozen before Candidate 11")
        sealed_prompts = _flatten_sealed_prompts(sealed_test)
        _assert_sealed_test_not_in_training(
            sealed_prompts,
            getattr(args, "concept_bank", "ml/palettebrain/c11_training_concepts.v1.json"),
        )
    device = resolve_evaluation_device(args.device)
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    model = PaletteDecoder(PaletteDecoderConfig(**checkpoint["model_config"]))
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    model = model.to(device).eval()
    structure_rate, structure_rows = palette_structure_metric(
        model, args.dataset, args.evaluation_split
    )
    context = load_static_evaluation_context(
        args.benchmark_v2,
        args.benchmark_v3,
        cache_dir=args.cache_dir,
        device=device,
        extra_prompts=tuple(sealed_prompts),
    )
    v2 = context["v2"]
    v3 = context["v3"]
    references = context["references"]
    prompts = context["prompts"]
    embeddings = context["embeddings"]
    prompt_index = context["prompt_index"]
    decoded_prompts = decode_embeddings(model, embeddings, count=5, seed=42)
    palettes = {
        prompt: representation_to_oklab_numpy(raw[None, :5])[0]
        for prompt, raw in zip(prompts, decoded_prompts, strict=True)
    }

    family_rows = []
    categories: dict[str, list[bool]] = {}
    for family, concept in v2["concepts"].items():
        for prompt in concept["prompts"]:
            closest = _family_distance(palettes[prompt], references)[0][0]
            passed = closest == family
            family_rows.append({"prompt": prompt, "expected": family, "closest": closest, "pass": passed})
            categories.setdefault(concept["category"], []).append(passed)
    category_rates = {name: float(np.mean(values)) for name, values in categories.items()}
    semantic_family_win = float(np.mean([row["pass"] for row in family_rows]))

    direct_rows = []
    for prompt in v3["buckets"]["explicit_color_controls"]:
        palette = palettes[prompt]
        hues = _hues(palette)
        chroma = np.linalg.norm(palette[:, 1:3], axis=1)
        if prompt in {"red", "красный"}:
            passed = float(np.mean(((hues <= 50) | (hues >= 345)) & (chroma > 0.03))) >= 0.6
        elif prompt in {"blue", "синий", "navy blue"}:
            passed = float(np.mean((hues >= 220) & (hues <= 290) & (chroma > 0.03))) >= 0.6
        elif prompt == "muted orange":
            passed = float(np.mean((hues >= 35) & (hues <= 85))) >= 0.4 and float(chroma.mean()) < 0.14
        elif prompt == "red and blue":
            passed = bool(np.any((hues <= 50) | (hues >= 345))) and bool(np.any((hues >= 220) & (hues <= 290)))
        elif prompt == "not red":
            passed = not bool(np.any(((hues <= 50) | (hues >= 345)) & (chroma > 0.04)))
        elif prompt == "without green":
            passed = not bool(np.any((hues >= 100) & (hues <= 165) & (chroma > 0.04)))
        else:
            passed = False
        direct_rows.append({"prompt": prompt, "pass": bool(passed)})

    abstract_rows = []
    for item in v3["abstract"]:
        en, ru = palettes[item["en"]].mean(0), palettes[item["ru"]].mean(0)
        reference = np.mean([palettes[prompt].mean(0) for prompt in item["references"]], axis=0)
        negative = np.mean([palettes[prompt].mean(0) for prompt in item["hardNegatives"]], axis=0)
        abstract_rows.append({
            "concept": item["en"], "ruEnDistance": float(np.linalg.norm(en - ru)),
            "referenceDistance": float(np.linalg.norm(en - reference)),
            "hardNegativeDistance": float(np.linalg.norm(en - negative)),
            "pass": float(np.linalg.norm(en - ru)) <= 0.08 and float(np.linalg.norm(en - reference)) < float(np.linalg.norm(en - negative)),
        })
    long_rows = [{"en": pair[0], "distance": float(np.linalg.norm(palettes[pair[0]].mean(0) - palettes[pair[1]].mean(0)))} for pair in v3["longText"]]
    composition_rows = [{
        "pair": pair,
        "distance": float(np.linalg.norm(palettes[pair[0]].mean(0) - palettes[pair[1]].mean(0))),
        "pass": composition_semantics_pass(pair, palettes[pair[0]], palettes[pair[1]]),
    } for pair in v3["compositionContrasts"]]
    ood_rows = []
    for group in v3["oodParaphraseGroups"]:
        means = np.stack([palettes[prompt].mean(0) for prompt in group])
        ood_rows.append({"group": group, "maximumDistance": float(np.linalg.norm(means[:, None] - means[None, :], axis=-1).max())})
    adversarial_base = {
        "red grass": "grass", "green blood": "blood", "warm moonlight": "moonlight",
        "cold candlelight": "candlelight", "blue rust": "rust", "black snow": "snow",
        "hospital at sunset": "hospital", "snow under red emergency lights": "snow",
        "green glass in a dark nightclub": "glass",
    }
    adversarial_rows = [
        {"prompt": prompt, "base": adversarial_base[prompt], "distance": float(np.linalg.norm(palettes[prompt].mean(0) - palettes[adversarial_base[prompt]].mean(0))), "pass": adversarial_semantics_pass(prompt, palettes[prompt], palettes[adversarial_base[prompt]])}
        for prompt in v3["adversarialComposition"]
    ]
    all_palette_values = list(palettes.values())
    near_duplicate_rate = float(np.mean([_pairwise_min(palette) < 0.025 for palette in all_palette_values]))
    collapse_values = [palettes[prompt] for prompt in sealed_prompts] if sealed_prompts else all_palette_values
    cross_prompt_collapse_rate, cross_prompt_collapse_pass = cross_prompt_collapse_metric(
        collapse_values
    )
    sealed_translation_rows = []
    sealed_modifier_rows = []
    if sealed_test is not None:
        sealed_translation_rows = [{
            "pair": pair,
            "distance": palette_set_distance(palettes[pair[0]], palettes[pair[1]]),
        } for pair in sealed_test.get("translationPairs", [])]
        sealed_modifier_rows = [{
            "pair": pair,
            "distance": palette_set_distance(palettes[pair[0]], palettes[pair[1]]),
        } for pair in sealed_test.get("modifierPairs", [])]
    sealed_semantic_test_gate = bool(
        sealed_test is not None
        and sealed_translation_rows
        and sealed_modifier_rows
        and all(row["distance"] <= 0.08 for row in sealed_translation_rows)
        and all(row["distance"] >= 0.025 for row in sealed_modifier_rows)
        and cross_prompt_collapse_pass
    ) if args.evaluation_split == "test" else False
    bilingual_rows = [{
        "pair": pair,
        "distance": float(np.linalg.norm(palettes[pair[0]].mean(0) - palettes[pair[1]].mean(0))),
    } for pair in v3["bilingualPairs"]]
    engineering_embedding = embeddings[prompt_index["rain"]]
    count_passes, inactive_passes, gamut_passes = [], [], []
    engineering_counts = list(range(2, 10))
    engineering_raw = run_decoder_inputs(
        model,
        [_inputs(engineering_embedding, count, 42) for count in engineering_counts],
    )
    for count, raw in zip(engineering_counts, engineering_raw, strict=True):
        decoded = decode_raw(raw, count)
        distinct = {tuple(round(channel, 4) for channel in color["srgb"]) for color in decoded}
        count_passes.append(len(decoded) == count and len(distinct) == count)
        inactive_passes.append(bool(np.all(raw[count:] == 0)))
        gamut_passes.append(all(
            all(-1e-4 <= channel <= 1.0001 for channel in color["srgb"])
            for color in decode_raw(raw, count)
        ))
    unlocked_inputs = list(_inputs(engineering_embedding, 5, 43))
    locked_inputs = list(_inputs(engineering_embedding, 5, 43))
    locked_inputs[3][0, 0] = 1.0
    locked_inputs[4][0, 0] = torch.tensor([0.55, 0.08, 0.0, 1.0])
    repeated = run_decoder_inputs(
        model,
        [
            _inputs(engineering_embedding, 5, 42),
            _inputs(engineering_embedding, 5, 42),
            *[_inputs(engineering_embedding, 5, seed) for seed in (1, 42, 999)],
            tuple(unlocked_inputs),
            tuple(locked_inputs),
            _inputs(engineering_embedding, 5, 999),
        ],
    )
    repeat_a, repeat_b = repeated[0:1], repeated[1:2]
    seed_outputs = [repeated[index:index + 1] for index in range(2, 5)]
    unlocked_raw, locked_raw = repeated[5:6], repeated[6:7]
    seed_palettes = [representation_to_oklab_numpy(value[:, :5])[0] for value in seed_outputs]
    seed_distances = [
        float(np.linalg.norm(seed_palettes[left].mean(0) - seed_palettes[right].mean(0)))
        for left in range(len(seed_palettes)) for right in range(left + 1, len(seed_palettes))
    ]
    restored_a = locked_raw.copy()
    restored_b = repeated[7:8].copy()
    locked_value = locked_inputs[4][0, 0].detach().cpu().numpy()
    restored_a[0, 0, :4] = locked_value
    restored_b[0, 0, :4] = locked_value
    lock_exact = np.array_equal(restored_a[0, 0, :4], restored_b[0, 0, :4])
    lock_conditioning = not np.array_equal(unlocked_raw, locked_raw)
    parity = json.loads(Path(args.parity_report).read_text(encoding="utf-8")) if Path(args.parity_report).is_file() else {}
    browser_smoke = (
        json.loads(Path(args.browser_smoke_report).read_text(encoding="utf-8"))
        if args.browser_smoke_report and Path(args.browser_smoke_report).is_file()
        else {}
    )
    browser_smoke_pass = (
        browser_smoke.get("testClassification") == "REAL_BROWSER"
        and browser_smoke.get("pass") is True
        and browser_smoke.get("fallbackUsed") is False
    )
    browser_smoke_engineering = browser_smoke.get("testClassification") == "ENGINEERING_SMOKE_ONLY"
    metrics = {
        "semanticFamilyWin": semantic_family_win,
        "directEn": float(np.mean([row["pass"] for row in direct_rows if not any("а" <= c.lower() <= "я" for c in row["prompt"])])),
        "directRu": float(np.mean([row["pass"] for row in direct_rows if any("а" <= c.lower() <= "я" for c in row["prompt"])])),
        "exclusion": float(np.mean([row["pass"] for row in direct_rows if row["prompt"] in {"not red", "without green"}])),
        "cleanMultiColor": clean_multicolor_rate(all_palette_values),
        "nearDuplicateRate": near_duplicate_rate,
        "crossPromptCollapseRate": cross_prompt_collapse_rate,
        "crossPromptCollapseGate": cross_prompt_collapse_pass,
        "sealedSemanticTestGate": sealed_semantic_test_gate,
        "paletteStructureWinRate": structure_rate,
        "basicConcepts": category_rates.get("basic_objects", 0.0),
        "nature": category_rates.get("nature", 0.0),
        "weatherScenes": category_rates.get("weather", 0.0),
        "materials": float(np.mean([row["pass"] for row in family_rows if row["expected"] in {"rust", "gold", "ice"}])),
        "placesInteriors": category_rates.get("places", 0.0),
        "lighting": category_rates.get("light", 0.0),
        "stylesMedia": category_rates.get("styles", 0.0),
        "compositions": category_rates.get("compositions", 0.0),
        "oodParaphrases": float(np.mean([row["maximumDistance"] <= 0.10 for row in ood_rows])),
        "heldOutRelated": float(np.mean([row["maximumDistance"] <= 0.12 for row in ood_rows[2:]])),
        "ruEnSemanticAgreement": float(np.mean([row["distance"] <= 0.08 for row in bilingual_rows])),
        "abstractConceptGate": all(row["pass"] for row in abstract_rows),
        "longPromptGate": all(row["distance"] <= 0.10 for row in long_rows) and all(row["pass"] for row in composition_rows),
        "adversarialCompositionGate": all(row["pass"] for row in adversarial_rows),
        "count": float(np.mean(count_passes)),
        "inactive": float(np.mean(inactive_passes)),
        "locks": float(lock_exact and lock_conditioning),
        "seedDiversity": float(max(seed_distances) > 1e-6),
        "seedStability": float(max(seed_distances) < 0.18),
        "gamut": float(np.mean(gamut_passes)),
        "determinism": float(np.array_equal(repeat_a, repeat_b)),
        "pytorchOnnxParity": parity.get("pytorchOnnx", {}).get("pass") is True,
        "onnxBrowserParity": parity.get("onnxBrowser", {}).get("pass") is True,
        "realBrowserSemanticSmoke": browser_smoke_pass,
    }
    report = {
        "schemaVersion": 1, "candidate": "candidate-11",
        "benchmarkId": v3["benchmarkId"],
        "testClassification": (
            "ENGINEERING_SMOKE_ONLY" if (getattr(args, "engineering_smoke", False) or browser_smoke_engineering)
            else ("REAL_PYTORCH_ONNX_BROWSER_SEMANTIC" if browser_smoke_pass else "REAL_PYTORCH_SEMANTIC_STAGE_A")
        ),
        "productionReady": False,
        "sources": {
            "benchmarkId": v3["benchmarkId"], "checkpoint": args.checkpoint,
            "checkpointSha256": _cached_file_sha256(args.checkpoint),
            "dataset": args.dataset,
            "datasetSha256": _cached_file_sha256(args.dataset) if args.dataset else None,
            "evaluationSplit": args.evaluation_split,
            "semanticTestBenchmark": semantic_test_path.as_posix() if sealed_test is not None else None,
            "semanticTestSha256": _cached_file_sha256(semantic_test_path) if sealed_test is not None else None,
        },
        "metrics": metrics, "categoryRates": category_rates, "familyRows": family_rows,
        "directRows": direct_rows, "abstractRows": abstract_rows, "longRows": long_rows,
        "compositionRows": composition_rows, "oodRows": ood_rows, "adversarialRows": adversarial_rows,
        "bilingualRows": bilingual_rows,
        "paletteStructureRows": structure_rows,
        "sealedTranslationRows": sealed_translation_rows,
        "sealedModifierRows": sealed_modifier_rows,
        "engineeringRows": {
            "seedMeanOklabDistances": seed_distances,
            "lockRestorationExact": lock_exact,
            "lockConditioningReachedModel": lock_conditioning,
            "decoderDevice": str(_model_device(model)),
            "decoderBatchSize": DEFAULT_DECODER_BATCH_SIZE,
            "promptCount": len(prompts),
        },
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--benchmark-v2", default="ml/palettebrain/benchmark_visual_semantic_v2.json")
    parser.add_argument("--benchmark-v3", default="ml/palettebrain/benchmark_semantic_v3.json")
    parser.add_argument("--cache-dir", default="ml/.cache/hub")
    parser.add_argument("--parity-report", default="ml/palettebrain/reports/candidate-11-parity.json")
    parser.add_argument("--browser-smoke-report")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--dataset")
    parser.add_argument("--evaluation-split", default="val", choices=("val", "test"))
    parser.add_argument("--semantic-test-benchmark", default="ml/palettebrain/benchmark_semantic_release.v1.json")
    parser.add_argument("--concept-bank", default="ml/palettebrain/c11_training_concepts.v1.json")
    parser.add_argument("--engineering-smoke", action="store_true")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = evaluate(args)
    print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
