"""Fine-tune Candidate 3 -> Candidate 4.

Two targeted fixes:
  FIX 1 - Multi-color supervision: inject compact in-memory multi-color
           training records (EN + RU pairs/triples) so the model learns to
           place each requested color family in a DISTINCT palette slot.
           Uses permutation-invariant family assignment: one prediction must
           not satisfy two different requested families simultaneously.

  FIX 2 - Target-aware duplicate loss: replace the global repulsion penalty
           with one conditioned on the *matched* target distances.  If two
           target colors are meaningfully distinct (> TARGET_DISTINCT_THRESH)
           but the corresponding predicted colors collapse (< PRED_CLOSE_THRESH),
           penalize the collapse.  Leave naturally-close target pairs alone.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import time
from typing import Any

import numpy as np

try:
    import torch
    from torch import Tensor
    import torch.nn.functional as F
    from torch.utils.data import DataLoader, WeightedRandomSampler
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "PyTorch is required. Install ml/palettebrain/requirements.txt."
    ) from exc

try:
    from .color_math import hue_relevance_from_oklab, representation_to_oklab
    from .dataset import PaletteBrainDataset, seed_noise_from_uint32
    from .e5_embedding import load_encoder, embed_texts
    from .matching import match_free_targets
    from .model import PaletteDecoder, PaletteDecoderConfig
    from .palette_targets import (
        hex_to_oklab,
        oklab_to_oklch,
        physical_oklch_to_target,
        hex_to_target,
        MAX_COLORS,
    )
except ImportError:
    from color_math import hue_relevance_from_oklab, representation_to_oklab  # type: ignore[no-redef]
    from dataset import PaletteBrainDataset, seed_noise_from_uint32  # type: ignore[no-redef]
    from e5_embedding import load_encoder, embed_texts  # type: ignore[no-redef]
    from matching import match_free_targets  # type: ignore[no-redef]
    from model import PaletteDecoder, PaletteDecoderConfig  # type: ignore[no-redef]
    from palette_targets import (  # type: ignore[no-redef]
        hex_to_oklab,
        oklab_to_oklch,
        physical_oklch_to_target,
        hex_to_target,
        MAX_COLORS,
    )


METRICS_VERSION = 1

# ---------------------------------------------------------------------------
# Loss hyper-parameters
# ---------------------------------------------------------------------------
# Target-aware duplicate: penalize predicted collapse only when targets differ
TARGET_DISTINCT_THRESH = 0.08   # matched targets must be at least this far apart
PRED_CLOSE_THRESH = 0.035       # predicted pair is "collapsed" if closer than this
TARGET_AWARE_DUP_WEIGHT = 0.25  # weight of target-aware duplicate term

# Multi-color supervision weight
MULTI_COLOR_STEP_WEIGHT = 1.5

# Original loss weights (unchanged)
IMPORTANCE_LOSS_WEIGHT = 0.0

# ---------------------------------------------------------------------------
# Canonical anchor HEX values for the color families used in multi-color prompts
# ---------------------------------------------------------------------------
FAMILY_HEX: dict[str, str] = {
    "red":     "#e63333",
    "blue":    "#2244cc",
    "yellow":  "#f5d020",
    "green":   "#2e8b57",
    "orange":  "#e07820",
    "purple":  "#7b2fbe",
    "cyan":    "#00aacc",
    "pink":    "#e04488",
    "white":   "#f0f0f0",
    "black":   "#1a1a1a",
    "brown":   "#7b4a24",
    "violet":  "#6832cc",
    "magenta": "#cc2299",
    "teal":    "#008080",
}

# ---------------------------------------------------------------------------
# Multi-color training prompts (distinct from frozen evaluation fixture)
# ---------------------------------------------------------------------------
MULTI_COLOR_SPECS: list[tuple[str, str, list[str]]] = [
    # Pairs
    ("red and blue",           "красный и синий",              ["red", "blue"]),
    ("blue and red",           "синий и красный",              ["blue", "red"]),
    ("red and yellow",         "красный и жёлтый",             ["red", "yellow"]),
    ("yellow and red",         "жёлтый и красный",             ["yellow", "red"]),
    ("purple and cyan",        "фиолетовый и голубой",         ["purple", "cyan"]),
    ("cyan and purple",        "голубой и фиолетовый",         ["cyan", "purple"]),
    ("green and orange",       "зелёный и оранжевый",          ["green", "orange"]),
    ("orange and green",       "оранжевый и зелёный",          ["orange", "green"]),
    ("blue and yellow",        "синий и жёлтый",               ["blue", "yellow"]),
    ("yellow and blue",        "жёлтый и синий",               ["yellow", "blue"]),
    ("red and green",          "красный и зелёный",            ["red", "green"]),
    ("green and red",          "зелёный и красный",            ["green", "red"]),
    ("pink and teal",          "розовый и бирюзовый",          ["pink", "teal"]),
    ("teal and pink",          "бирюзовый и розовый",          ["teal", "pink"]),
    ("orange and violet",      "оранжевый и фиолетовый",       ["orange", "violet"]),
    ("violet and orange",      "фиолетовый и оранжевый",       ["violet", "orange"]),
    ("magenta and green",      "малиновый и зелёный",          ["magenta", "green"]),
    ("blue and orange",        "синий и оранжевый",            ["blue", "orange"]),
    ("red and cyan",           "красный и циан",               ["red", "cyan"]),
    ("yellow and purple",      "жёлтый и фиолетовый",          ["yellow", "purple"]),
    # Triples
    ("red blue yellow",        "красный синий жёлтый",         ["red", "blue", "yellow"]),
    ("blue yellow red",        "синий жёлтый красный",         ["blue", "yellow", "red"]),
    ("red green blue",         "красный зелёный синий",        ["red", "green", "blue"]),
    ("orange purple cyan",     "оранжевый фиолетовый голубой", ["orange", "purple", "cyan"]),
    ("pink blue yellow",       "розовый синий жёлтый",         ["pink", "blue", "yellow"]),
    ("teal orange violet",     "бирюзовый оранжевый фиолетовый", ["teal", "orange", "violet"]),
    # Compound phrasings
    ("palette with red and blue",    "палитра с красным и синим",     ["red", "blue"]),
    ("colors: red, blue, yellow",    "цвета: красный, синий, жёлтый", ["red", "blue", "yellow"]),
    ("red alongside blue",           "красный рядом с синим",         ["red", "blue"]),
    ("combining red with yellow",    "сочетание красного с жёлтым",   ["red", "yellow"]),
]


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_torch_save(payload: dict[str, object], path: Path) -> None:
    temporary = path.with_name(path.name + ".tmp")
    try:
        torch.save(payload, temporary)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def masked_mean(values: Tensor, mask: Tensor) -> Tensor:
    return (values * mask).sum() / mask.sum().clamp_min(1.0)


# ---------------------------------------------------------------------------
# Multi-color target builder
# ---------------------------------------------------------------------------

def build_multicolor_target(
    families: list[str],
    count: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, list[str | None]]:
    """Build a palette target with one anchor slot per requested family.

    Returns:
        targets:  [MAX_COLORS, 5] float32
        slot_family: list[str | None] length MAX_COLORS
    """
    assert 2 <= len(families) <= count <= MAX_COLORS

    targets = np.zeros((MAX_COLORS, 5), dtype=np.float32)
    slot_family: list[str | None] = [None] * MAX_COLORS

    for slot_idx, fam in enumerate(families):
        hex_val = FAMILY_HEX[fam]
        t, _ = hex_to_target(hex_val)
        targets[slot_idx] = t
        slot_family[slot_idx] = fam

    # Fill remaining active slots with desaturated fillers
    filler_slots = list(range(len(families), count))
    if filler_slots:
        lightnesses = np.linspace(0.25, 0.80, len(filler_slots))
        for k, slot_idx in enumerate(filler_slots):
            hue = float(rng.integers(0, 360))
            t, _ = physical_oklch_to_target(float(lightnesses[k]), 0.04, hue)
            targets[slot_idx] = t

    return targets, slot_family


def build_multicolor_batch(
    specs: list[tuple[str, list[str]]],
    embeddings: np.ndarray,
    device: torch.device,
    seed: int = 0,
) -> dict[str, Any]:
    """Convert specs + pre-computed E5 embeddings into one training batch dict."""
    rng_global = np.random.default_rng(seed)
    batch_size = len(specs)
    count = 5  # fixed count for all multi-color items

    count_mask = np.zeros((batch_size, MAX_COLORS), dtype=np.float32)
    count_mask[:, :count] = 1.0

    targets_all = np.zeros((batch_size, MAX_COLORS, 5), dtype=np.float32)
    families_all: list[list[str | None]] = []

    for i, (text, families) in enumerate(specs):
        rng_item = np.random.default_rng(rng_global.integers(0, 2**32))
        n_fam = len(families)
        item_count = max(count, n_fam)
        t, slot_fam = build_multicolor_target(families, item_count, rng_item)
        targets_all[i] = t
        families_all.append(slot_fam)

    browser_seeds = rng_global.integers(0, 2**32, size=batch_size).astype(np.uint32)
    seed_noise = np.stack([seed_noise_from_uint32(int(s)) for s in browser_seeds])

    locked_mask = np.zeros((batch_size, MAX_COLORS), dtype=np.float32)
    locked_colors = np.zeros((batch_size, MAX_COLORS, 4), dtype=np.float32)

    return {
        "text_embedding": torch.as_tensor(embeddings, dtype=torch.float32).to(device),
        "count_mask": torch.as_tensor(count_mask, dtype=torch.float32).to(device),
        "seed_noise": torch.as_tensor(seed_noise, dtype=torch.float32).to(device),
        "locked_mask": torch.as_tensor(locked_mask, dtype=torch.float32).to(device),
        "locked_colors": torch.as_tensor(locked_colors, dtype=torch.float32).to(device),
        "target": torch.as_tensor(targets_all, dtype=torch.float32).to(device),
        "_families": families_all,
    }


# ---------------------------------------------------------------------------
# Multi-color family loss (FIX 1)
# ---------------------------------------------------------------------------

def multicolor_family_loss(
    output: Tensor,
    target: Tensor,
    count_mask: Tensor,
    families_all: list[list[str | None]],
) -> Tensor:
    """Permutation-invariant per-family loss with distinct slot assignment.

    Each requested family slot must be satisfied by a DIFFERENT prediction
    slot. The assignment is greedy-nearest (detached) then we compute
    smooth-L1 on the matched pairs.
    """
    predicted_oklab = representation_to_oklab(output)
    with torch.no_grad():
        target_oklab = representation_to_oklab(target)

    batch_size = output.shape[0]
    total_loss = output.new_zeros(())
    count_families = 0

    for b in range(batch_size):
        slot_families = families_all[b]
        active_mask = count_mask[b] > 0.5  # [9] bool
        active_slots = torch.nonzero(active_mask, as_tuple=False).flatten().tolist()

        family_slots = [
            slot for slot in active_slots
            if slot < len(slot_families) and slot_families[slot] is not None
        ]
        if len(family_slots) < 2:
            continue

        fam_slot_t = torch.stack(
            [target_oklab[b, slot] for slot in family_slots]
        )  # [F, 3]

        pred_active = predicted_oklab[b, active_mask]  # [A, 3]

        cost = torch.cdist(
            fam_slot_t.unsqueeze(0), pred_active.unsqueeze(0)
        ).squeeze(0).detach()  # [F, A]

        # Greedy distinct assignment
        num_fam = len(family_slots)
        assigned_pred: list[int] = []
        used: set[int] = set()
        for f_idx in range(num_fam):
            row = cost[f_idx].clone()
            if used:
                row[list(used)] = 1e9
            best_pred = int(row.argmin().item())
            used.add(best_pred)
            assigned_pred.append(best_pred)

        # Gather active slots list for index mapping
        active_list = active_slots  # list length A

        for f_idx, f_slot in enumerate(family_slots):
            p_global = active_list[assigned_pred[f_idx]]
            pred_vec = output[b, p_global, :4]
            tgt_vec = target[b, f_slot, :4]
            total_loss = total_loss + F.smooth_l1_loss(pred_vec, tgt_vec)
            count_families += 1

    if count_families == 0:
        return output.new_zeros(())
    return total_loss / count_families


# ---------------------------------------------------------------------------
# Target-aware duplicate loss (FIX 2)
# ---------------------------------------------------------------------------

def target_aware_duplicate_loss(
    predicted_oklab: Tensor,
    matched_target_oklab: Tensor,
    free: Tensor,
) -> Tensor:
    """Penalize prediction collapse only when matched targets are distinct.

    For each active-free slot pair (i, j):
      - target_dist(i,j) > TARGET_DISTINCT_THRESH  AND
      - pred_dist(i,j)   < PRED_CLOSE_THRESH
      -> penalize relu(PRED_CLOSE_THRESH - pred_dist)
    """
    pair_mask = free.unsqueeze(2) * free.unsqueeze(1)  # [B, 9, 9]
    upper = torch.triu(torch.ones_like(pair_mask), diagonal=1)
    pair_mask = pair_mask * upper

    pred_dist = torch.cdist(predicted_oklab, predicted_oklab)
    target_dist = torch.cdist(
        matched_target_oklab.detach(), matched_target_oklab.detach()
    )

    targets_distinct = (target_dist > TARGET_DISTINCT_THRESH).float()
    penalty = F.relu(PRED_CLOSE_THRESH - pred_dist) * targets_distinct * pair_mask

    denom = (pair_mask * targets_distinct).sum().clamp_min(1.0)
    return penalty.sum() / denom


# ---------------------------------------------------------------------------
# Combined loss
# ---------------------------------------------------------------------------

def finetune_decoder_loss(
    output: Tensor,
    target: Tensor,
    count_mask: Tensor,
    locked_mask: Tensor,
) -> tuple[Tensor, dict[str, Tensor]]:
    """Standard palette loss + target-aware duplicate term (no global repulsion)."""
    active = count_mask.clamp(0.0, 1.0)
    locked = active * locked_mask.clamp(0.0, 1.0)
    free = active * (1.0 - locked_mask.clamp(0.0, 1.0))

    predicted_oklab = representation_to_oklab(output)
    with torch.no_grad():
        target_oklab = representation_to_oklab(target)
        matched_target, matched_target_oklab = match_free_targets(
            target, predicted_oklab, target_oklab, count_mask, locked_mask,
        )

    lightness = masked_mean(
        F.smooth_l1_loss(output[..., 0], matched_target[..., 0], reduction="none"), free
    )
    chroma = masked_mean(
        F.smooth_l1_loss(output[..., 1], matched_target[..., 1], reduction="none"), free
    )
    predicted_hue = F.normalize(output[..., 2:4], dim=-1, eps=1e-6)
    target_hue = F.normalize(matched_target[..., 2:4], dim=-1, eps=1e-6)
    hue_error = 1.0 - (predicted_hue * target_hue).sum(dim=-1)
    hue_relevance = hue_relevance_from_oklab(matched_target_oklab)
    hue = masked_mean(hue_error * hue_relevance, free)

    locked_lightness = masked_mean(
        F.smooth_l1_loss(output[..., 0], matched_target[..., 0], reduction="none"), locked
    )
    locked_chroma = masked_mean(
        F.smooth_l1_loss(output[..., 1], matched_target[..., 1], reduction="none"), locked
    )
    locked_hue = masked_mean(hue_error * hue_relevance, locked)

    dup_penalty = target_aware_duplicate_loss(predicted_oklab, matched_target_oklab, free)

    total = (
        lightness
        + chroma
        + 1.5 * hue
        + TARGET_AWARE_DUP_WEIGHT * dup_penalty
        + 0.25 * (locked_lightness + locked_chroma + locked_hue)
    )
    return total, {
        "lightness": lightness,
        "chroma": chroma,
        "hue": hue,
        "targetAwareDupPenalty": dup_penalty,
        "lockedLightness": locked_lightness,
        "lockedChroma": locked_chroma,
        "lockedHue": locked_hue,
    }


# ---------------------------------------------------------------------------
# Training loop
# ---------------------------------------------------------------------------

def run_epoch(
    model: PaletteDecoder,
    loader: DataLoader,
    device: torch.device,
    optimizer: torch.optim.Optimizer | None,
    multicolor_batches: list[dict[str, Any]] | None = None,
    multicolor_weight: float = MULTI_COLOR_STEP_WEIGHT,
) -> dict[str, float]:
    training = optimizer is not None
    model.train(training)
    totals: dict[str, float] = {"loss": 0.0}
    batches = 0
    mc_pool = list(multicolor_batches) if multicolor_batches else []
    mc_idx = 0

    for batch in loader:
        inputs = {
            "text_embedding": batch["text_embedding"].to(device),
            "count_mask": batch["count_mask"].to(device),
            "seed_noise": batch["seed_noise"].to(device),
            "locked_mask": batch["locked_mask"].to(device),
            "locked_colors": batch["locked_colors"].to(device),
        }
        target = batch["target"].to(device)

        if training:
            optimizer.zero_grad(set_to_none=True)

        with torch.set_grad_enabled(training):
            output = model(**inputs)
            loss, components = finetune_decoder_loss(
                output, target, inputs["count_mask"], inputs["locked_mask"]
            )

        if not torch.isfinite(loss):
            raise RuntimeError("non-finite training loss")

        if training:
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            # Inject one multi-color mini-batch per regular step
            if mc_pool:
                mc_batch = mc_pool[mc_idx % len(mc_pool)]
                mc_idx += 1
                mc_inputs = {
                    "text_embedding": mc_batch["text_embedding"],
                    "count_mask": mc_batch["count_mask"],
                    "seed_noise": mc_batch["seed_noise"],
                    "locked_mask": mc_batch["locked_mask"],
                    "locked_colors": mc_batch["locked_colors"],
                }
                mc_target = mc_batch["target"]
                mc_families = mc_batch["_families"]

                optimizer.zero_grad(set_to_none=True)
                mc_output = model(**mc_inputs)

                mc_palette_loss, _ = finetune_decoder_loss(
                    mc_output, mc_target,
                    mc_batch["count_mask"], mc_batch["locked_mask"],
                )
                mc_family_loss = multicolor_family_loss(
                    mc_output, mc_target, mc_batch["count_mask"], mc_families
                )
                mc_total = mc_palette_loss + mc_family_loss
                if torch.isfinite(mc_total):
                    (multicolor_weight * mc_total).backward()
                    torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                    optimizer.step()
                    totals["mcPaletteLoss"] = (
                        totals.get("mcPaletteLoss", 0.0) + float(mc_palette_loss.detach())
                    )
                    totals["mcFamilyLoss"] = (
                        totals.get("mcFamilyLoss", 0.0) + float(mc_family_loss.detach())
                    )

        totals["loss"] += float(loss.detach())
        for name, value in components.items():
            totals[name] = totals.get(name, 0.0) + float(value.detach())
        batches += 1

    if batches == 0:
        raise RuntimeError("dataset split produced zero batches")
    return {name: value / batches for name, value in totals.items()}


def choose_device(requested: str) -> torch.device:
    device = (
        torch.device(requested)
        if requested != "auto"
        else torch.device("cuda" if torch.cuda.is_available() else "cpu")
    )
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but not available")
    return device


# ---------------------------------------------------------------------------
# Multi-color data preparation
# ---------------------------------------------------------------------------

def prepare_multicolor_batches(
    device: torch.device,
    cache_dir: str = "ml/.cache/hub",
    batch_size: int = 16,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Embed all multi-color prompts and package into mini-batches."""
    print("Embedding multi-color prompts with E5 encoder...")
    encoder = load_encoder(device="auto", cache_dir=cache_dir)

    all_specs: list[tuple[str, list[str]]] = []
    texts_to_embed: list[str] = []

    for text_en, text_ru, families in MULTI_COLOR_SPECS:
        all_specs.append((text_en, families))
        texts_to_embed.append(text_en)
        all_specs.append((text_ru, families))
        texts_to_embed.append(text_ru)

    embeddings = embed_texts(texts_to_embed, encoder=encoder)
    print(f"  Embedded {len(texts_to_embed)} multi-color texts -> shape {embeddings.shape}")

    batches = []
    rng = np.random.default_rng(seed)
    for start in range(0, len(all_specs), batch_size):
        end = min(start + batch_size, len(all_specs))
        batch_specs = all_specs[start:end]
        batch_emb = embeddings[start:end]
        batch_seed = int(rng.integers(0, 2**32))
        batches.append(build_multicolor_batch(batch_specs, batch_emb, device, seed=batch_seed))
    print(f"  Prepared {len(batches)} multi-color mini-batches.")
    return batches


# ---------------------------------------------------------------------------
# Main fine-tuning entry point
# ---------------------------------------------------------------------------

def finetune(args: argparse.Namespace) -> dict[str, object]:
    set_seed(args.seed)
    device = choose_device(args.device)

    # Load checkpoint
    checkpoint_path = Path(args.checkpoint)
    if not checkpoint_path.is_file():
        raise FileNotFoundError(f"checkpoint not found: {checkpoint_path}")
    print(f"Loading checkpoint: {checkpoint_path}")
    ckpt = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    cfg = ckpt["model_config"]
    config = PaletteDecoderConfig(**cfg)
    model = PaletteDecoder(config).to(device)
    model.load_state_dict(ckpt["model_state_dict"])
    source_candidate_id = ckpt.get("candidate_id", "unknown")
    print(f"  Source candidate: {source_candidate_id}  epoch: {ckpt.get('epoch')}")
    print(f"  Parameters: {model.count_parameters():,}")

    # Dataset
    max_train = 64 if args.smoke else args.max_train_samples
    max_val = 32 if args.smoke else args.max_val_samples
    epochs = 1 if args.smoke else args.epochs

    train_dataset = PaletteBrainDataset(args.data, "train", max_samples=max_train)
    val_dataset = PaletteBrainDataset(args.data, "val", max_samples=max_val)
    if len(train_dataset) == 0 or len(val_dataset) == 0:
        raise RuntimeError("Dataset must have non-empty train and val splits")

    sampler_generator = torch.Generator().manual_seed(args.seed)
    sampler = WeightedRandomSampler(
        torch.as_tensor(train_dataset.sampling_weights, dtype=torch.double),
        num_samples=len(train_dataset),
        replacement=True,
        generator=sampler_generator,
    )
    train_loader = DataLoader(
        train_dataset, batch_size=args.batch_size, sampler=sampler, num_workers=0
    )
    val_loader = DataLoader(
        val_dataset, batch_size=args.batch_size, shuffle=False, num_workers=0
    )

    # Multi-color batches
    multicolor_batches: list[dict[str, Any]] = []
    if not args.smoke:
        multicolor_batches = prepare_multicolor_batches(
            device, cache_dir=args.e5_cache_dir,
            batch_size=args.batch_size, seed=args.seed,
        )

    # Optimizer (low LR for fine-tuning)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay
    )

    # Paths
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_stem = args.candidate_id
    last_path = output_dir / f"{artifact_stem}-last.pt"
    best_path = output_dir / f"{artifact_stem}-best.pt"
    metrics_path = output_dir / f"{artifact_stem}-metrics.json"

    data_path = Path(args.data)
    dataset_sha256 = sha256_file(data_path)

    loss_config = {
        "matching": "detached_physical_oklab_hungarian",
        "lightnessWeight": 1.0,
        "relativeChromaWeight": 1.0,
        "circularHueWeight": 1.5,
        "targetAwareDupThresh": TARGET_DISTINCT_THRESH,
        "predCloseThresh": PRED_CLOSE_THRESH,
        "targetAwareDupWeight": TARGET_AWARE_DUP_WEIGHT,
        "multiColorFamilyLoss": True,
        "multiColorStepWeight": MULTI_COLOR_STEP_WEIGHT,
        "lockedAuxiliaryWeight": 0.25,
        "importanceWeight": IMPORTANCE_LOSS_WEIGHT,
        "fix1_multiColorSupervision": True,
        "fix2_targetAwareDuplicateLoss": True,
        "sourceCandidateId": source_candidate_id,
    }

    best_val_loss = math.inf
    best_epoch = 0
    stale_epochs = 0
    history: list[dict[str, object]] = []
    start = time.perf_counter()

    for epoch in range(1, epochs + 1):
        train_metrics = run_epoch(
            model, train_loader, device, optimizer,
            multicolor_batches=multicolor_batches if not args.smoke else None,
        )
        with torch.no_grad():
            val_metrics = run_epoch(model, val_loader, device, None)
        record: dict[str, object] = {"epoch": epoch, "train": train_metrics, "val": val_metrics}
        history.append(record)
        print(json.dumps(record, sort_keys=True))

        checkpoint: dict[str, object] = {
            "schema_version": 1,
            "epoch": epoch,
            "model_state_dict": model.state_dict(),
            "model_config": config.to_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "val_loss": val_metrics["loss"],
            "training_data_kind": train_dataset.metadata.get("kind"),
            "dataset_version": train_dataset.metadata.get("datasetVersion"),
            "dataset_sha256": dataset_sha256,
            "dataset_content_hash": train_dataset.metadata.get("contentHash"),
            "encoder_revision": train_dataset.metadata.get("encoderRevision"),
            "encoder_artifact_sha256": train_dataset.metadata.get("encoderArtifactSha256"),
            "training_seed": args.seed,
            "loss_config": loss_config,
            "candidate_id": artifact_stem,
            "source_candidate_id": source_candidate_id,
            "production_ready": False,
            "smoke": bool(args.smoke),
        }
        atomic_torch_save(checkpoint, last_path)
        if val_metrics["loss"] < best_val_loss - args.min_delta:
            best_val_loss = val_metrics["loss"]
            best_epoch = epoch
            stale_epochs = 0
            atomic_torch_save(checkpoint, best_path)
            print(f"  New best val loss: {best_val_loss:.6f} at epoch {epoch}")
        else:
            stale_epochs += 1
        if not args.smoke and stale_epochs >= args.patience:
            print(f"Early stopping at epoch {epoch} (patience={args.patience})")
            break

    elapsed_seconds = time.perf_counter() - start
    metrics = {
        "schemaVersion": METRICS_VERSION,
        "status": "smoke_only" if args.smoke else "candidate_training_complete",
        "productionReady": False,
        "candidateId": artifact_stem,
        "sourceCandidateId": source_candidate_id,
        "dataset": str(args.data),
        "datasetSha256": dataset_sha256,
        "device": str(device),
        "gpu": torch.cuda.get_device_name(device) if device.type == "cuda" else None,
        "torchVersion": torch.__version__,
        "parameterCount": model.count_parameters(),
        "maximumEpochs": epochs,
        "epochsCompleted": len(history),
        "bestEpoch": best_epoch,
        "earlyStopped": len(history) < epochs,
        "bestValLoss": best_val_loss,
        "elapsedSeconds": elapsed_seconds,
        "bestCheckpoint": str(best_path.as_posix()),
        "bestCheckpointSha256": sha256_file(best_path),
        "lastCheckpoint": str(last_path.as_posix()),
        "lossConfig": loss_config,
        "history": history,
        "warning": (
            "Fine-tuning from Candidate 3. Frozen semantic, holdout, "
            "ONNX, and browser gates must still pass before release."
        ),
    }
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--checkpoint",
        default="ml/palettebrain/checkpoints/candidate-3-best.pt",
    )
    parser.add_argument(
        "--data",
        default="ml/palettebrain/data/palettebrain_candidate3_direct8_v1.npz",
    )
    parser.add_argument("--output-dir", default="ml/palettebrain/checkpoints")
    parser.add_argument("--candidate-id", default="candidate-4")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--max-train-samples", type=int)
    parser.add_argument("--max-val-samples", type=int)
    parser.add_argument("--patience", type=int, default=8)
    parser.add_argument("--min-delta", type=float, default=1e-4)
    parser.add_argument("--e5-cache-dir", default="ml/.cache/hub")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    print(json.dumps(finetune(args), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
