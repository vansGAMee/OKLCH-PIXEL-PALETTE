"""
Generate deterministic synthetic dataset.
RU/EN descriptions -> palette intent targets.
Usage: python generate_dataset.py [--seed 42] [--samples 40000] [--out ml/data/]
"""
import json
import math
import random
import argparse
from pathlib import Path
from normalize import normalize_text

# --- Load ontology ---
_CONCEPTS_PATH = Path(__file__).parent / "concepts.json"
with open(_CONCEPTS_PATH, "r", encoding="utf-8") as _f:
    _CONCEPTS = json.load(_f)

SUBJECTS = {s["id"]: s for s in _CONCEPTS["subjects"]}
MODIFIERS = {m["id"]: m for m in _CONCEPTS["modifiers"]}

# --- Color math helpers ---

L_MIN = 0.07
L_MAX = 0.93


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def circular_mean(angles_weights: list[tuple[float, float]]) -> float:
    """Weighted circular mean of angles in degrees."""
    xs = sum(w * math.cos(math.radians(a)) for a, w in angles_weights)
    ys = sum(w * math.sin(math.radians(a)) for a, w in angles_weights)
    return (math.degrees(math.atan2(ys, xs)) + 360.0) % 360.0


HARMONY_CLASSES = ["splitComplementary", "complementary", "analogous"]


def compose_palette_intent(
    subject: dict, modifiers_list: list[dict]
) -> dict:
    """
    Combine subject + modifiers into a palette intent target.
    Returns:
      target_L, target_hue_sin, target_hue_cos, target_relative_chroma,
      target_harmony_class, target_absolute_chroma (for hue weight)
    """
    # Base from subject
    L = subject["lightness"]
    hue = float(subject["hue"])
    rel_chroma = subject["relativeChroma"]
    harmony_str = subject["harmony"]

    # Hue blending: circular weighted average
    hue_contributions = [(hue, 1.0)]
    for mod in modifiers_list:
        L += mod["lightnessDelta"]
        rel_chroma *= mod["chromaMultiplier"]
        hue_contributions.append((mod["huePull"], mod["hueWeight"]))

    hue = circular_mean(hue_contributions)

    # Clamp
    L = clamp(L, L_MIN, L_MAX)
    rel_chroma = clamp(rel_chroma, 0.0, 1.0)

    # Harmony: subject wins unless modifiers override
    # Use most recent explicit override from modifiers
    for mod in reversed(modifiers_list):
        # Modifiers don't directly override harmony in this schema;
        # it stays as subject harmony. But toxic / neon pull toward splitComplementary.
        if mod["id"] in ("toxic", "neon", "volcanic"):
            harmony_str = "splitComplementary"
            break
        if mod["id"] in ("foggy", "cold", "snowy", "starry", "moonlit"):
            harmony_str = "analogous"
            break

    harmony_class = HARMONY_CLASSES.index(harmony_str)

    theta = math.radians(hue)
    target_hue_sin = math.sin(theta)
    target_hue_cos = math.cos(theta)

    # Approximate absolute chroma for hue-weight computation
    # Using a simple estimate: max chroma at L=0.5 is ~0.32 for typical hues
    approx_max_chroma = 0.28
    target_absolute_chroma = rel_chroma * approx_max_chroma

    return {
        "target_L": L,
        "target_hue_sin": target_hue_sin,
        "target_hue_cos": target_hue_cos,
        "target_relative_chroma": rel_chroma,
        "target_harmony_class": harmony_class,
        "target_absolute_chroma": target_absolute_chroma,
    }


# --- Phrase templates ---

def _subj_aliases(s: dict) -> list[str]:
    return s["aliases"]

def _mod_aliases(m: dict) -> list[str]:
    return m["aliases"]


TEMPLATES_EN = [
    lambda s, ms: s,
    lambda s, ms: f"{ms[0]} {s}" if ms else s,
    lambda s, ms: f"{s} in {ms[0]}" if ms else s,
    lambda s, ms: f"{s} at {ms[0]}" if ms else s,
    lambda s, ms: f"{s} under {ms[0]} {ms[1] if len(ms)>1 else ''}" if ms else s,
    lambda s, ms: f"{ms[0]} {ms[1] if len(ms)>1 else ''} {s}" if ms else s,
    lambda s, ms: f"{ms[0]} {s} at {ms[1]}" if len(ms) > 1 else (f"{ms[0]} {s}" if ms else s),
    lambda s, ms: f"dark {ms[0]} {s}" if ms else f"dark {s}",
    lambda s, ms: f"warm {ms[0]} {s}" if ms else f"warm {s}",
    lambda s, ms: f"{s} landscape" if not ms else f"{ms[0]} {s} landscape",
]

TEMPLATES_RU = [
    lambda s, ms: s,
    lambda s, ms: f"{ms[0]} {s}" if ms else s,
    lambda s, ms: f"{s} в {ms[0]}" if ms else s,
    lambda s, ms: f"{s} под {ms[0]}" if ms else s,
    lambda s, ms: f"{ms[0]} {s} ночью" if ms else f"{s} ночью",
    lambda s, ms: f"{ms[0]} {ms[1] if len(ms)>1 else ''} {s}" if ms else s,
    lambda s, ms: f"темный {ms[0]} {s}" if ms else f"темный {s}",
    lambda s, ms: f"яркий {s}" if not ms else f"яркий {ms[0]} {s}",
]


def _pick(rng: random.Random, lst: list):
    return rng.choice(lst)


def generate_phrase(
    rng: random.Random,
    subject: dict,
    modifiers_list: list[dict],
    lang: str,
) -> str:
    """Generate one natural-language phrase for the combo."""
    s_alias = _pick(rng, subject["aliases"])
    mod_aliases = [_pick(rng, m["aliases"]) for m in modifiers_list]

    if lang == "en":
        tmpl = _pick(rng, TEMPLATES_EN)
    else:
        tmpl = _pick(rng, TEMPLATES_RU)

    phrase = tmpl(s_alias, mod_aliases)
    # Collapse multiple spaces
    phrase = " ".join(phrase.split())
    return normalize_text(phrase)


def generate_dataset(
    n_samples: int,
    seed: int,
    out_dir: Path,
) -> None:
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)

    subject_ids = list(SUBJECTS.keys())
    modifier_ids = list(MODIFIERS.keys())

    records: list[dict] = []
    group_id = 0

    # Enumerate subject x modifier combos, generate multiple paraphrases per group
    for s_id in subject_ids:
        subject = SUBJECTS[s_id]

        # Subject alone
        target = compose_palette_intent(subject, [])
        paraphrases_en = [generate_phrase(rng, subject, [], "en") for _ in range(3)]
        paraphrases_ru = [generate_phrase(rng, subject, [], "ru") for _ in range(3)]
        for p in paraphrases_en + paraphrases_ru:
            records.append({"group_id": group_id, "text": p, **target})
        group_id += 1

        # Subject + 1 modifier
        for m_id in modifier_ids:
            mod = MODIFIERS[m_id]
            target = compose_palette_intent(subject, [mod])
            paraphrases = []
            for lang in ["en", "ru"]:
                for _ in range(4):
                    paraphrases.append(generate_phrase(rng, subject, [mod], lang))
            for p in paraphrases:
                records.append({"group_id": group_id, "text": p, **target})
            group_id += 1

        # Subject + 2 modifiers (sample a subset)
        sampled_mods = rng.sample(modifier_ids, min(8, len(modifier_ids)))
        mod_pairs = [(sampled_mods[i], sampled_mods[j])
                     for i in range(len(sampled_mods))
                     for j in range(i+1, len(sampled_mods))]
        for m1_id, m2_id in rng.sample(mod_pairs, min(6, len(mod_pairs))):
            mod1 = MODIFIERS[m1_id]
            mod2 = MODIFIERS[m2_id]
            target = compose_palette_intent(subject, [mod1, mod2])
            paraphrases = []
            for lang in ["en", "ru"]:
                for _ in range(3):
                    paraphrases.append(generate_phrase(rng, subject, [mod1, mod2], lang))
            for p in paraphrases:
                records.append({"group_id": group_id, "text": p, **target})
            group_id += 1

    # If we need more samples, upsample by adding more paraphrases
    while len(records) < n_samples:
        s_id = _pick(rng, subject_ids)
        subject = SUBJECTS[s_id]
        n_mods = rng.randint(0, 2)
        mods = [MODIFIERS[_pick(rng, modifier_ids)] for _ in range(n_mods)]
        target = compose_palette_intent(subject, mods)
        lang = rng.choice(["en", "ru"])
        phrase = generate_phrase(rng, subject, mods, lang)
        records.append({"group_id": group_id, "text": phrase, **target})
        group_id += 1

    rng.shuffle(records)
    records = records[:n_samples]

    # Stable group-based split: hash group_id
    def split(rec: dict) -> str:
        h = rec["group_id"] % 10
        if h < 8:
            return "train"
        elif h < 9:
            return "val"
        else:
            return "test"

    train_recs = [r for r in records if split(r) == "train"]
    val_recs   = [r for r in records if split(r) == "val"]
    test_recs  = [r for r in records if split(r) == "test"]

    def save_jsonl(path: Path, recs: list[dict]) -> None:
        with open(path, "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    save_jsonl(out_dir / "train.jsonl", train_recs)
    save_jsonl(out_dir / "val.jsonl", val_recs)
    save_jsonl(out_dir / "test.jsonl", test_recs)

    print(f"Generated: train={len(train_recs)}, val={len(val_recs)}, test={len(test_recs)}")
    total = len(records)
    print(f"Total records: {total}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--samples", type=int, default=40000)
    parser.add_argument("--out", type=str, default="ml/data")
    args = parser.parse_args()
    generate_dataset(args.samples, args.seed, Path(args.out))


if __name__ == "__main__":
    main()
