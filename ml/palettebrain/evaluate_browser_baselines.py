"""Freeze exact local-browser legacy and synthetic PaletteBrain baselines."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Iterable

import numpy as np

try:
    from .release_metrics import (
        deterministic_palette_equality,
        evaluate_direct_color_records,
        hungarian_matched_set_distance,
        load_color_family_fixture,
        load_semantic_release_fixture,
        near_duplicate_palette_rate,
        summarize_modifier_sensitivity,
        summarize_ru_en_parity,
    )
except ImportError:
    from release_metrics import (  # type: ignore[no-redef]
        deterministic_palette_equality,
        evaluate_direct_color_records,
        hungarian_matched_set_distance,
        load_color_family_fixture,
        load_semantic_release_fixture,
        near_duplicate_palette_rate,
        summarize_modifier_sensitivity,
        summarize_ru_en_parity,
    )


HARNESS = Path("ml/palettebrain/browser_runtime_harness.mjs")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def chunks(values: list[dict[str, Any]], size: int = 120) -> Iterable[list[dict[str, Any]]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def run_harness(mode: str, requests: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    results: list[dict[str, Any]] = []
    runtime: dict[str, Any] | None = None
    with tempfile.TemporaryDirectory(prefix="palettebrain-baseline-") as temporary_dir:
        temporary = Path(temporary_dir)
        for index, batch in enumerate(chunks(requests)):
            input_path = temporary / f"input-{index}.json"
            output_path = temporary / f"output-{index}.json"
            input_path.write_text(
                json.dumps({"schemaVersion": 1, "mode": mode, "requests": batch}, ensure_ascii=False),
                encoding="utf-8",
            )
            completed = subprocess.run(
                ["node", str(HARNESS), "--input", str(input_path), "--output", str(output_path)],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            if completed.returncode != 0:
                raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            results.extend(payload["results"])
            runtime = runtime or payload["runtime"]
    if len(results) != len(requests) or runtime is None:
        raise RuntimeError("browser harness returned an incomplete baseline")
    return results, runtime


def result_palette(mode: str, result: dict[str, Any]) -> np.ndarray:
    colors = (
        result["palette"]["colors"] if mode == "legacy" else result["result"]["colors"]
    )
    rows = []
    for item in colors:
        color = item["oklch"] if mode == "legacy" else item
        rows.append([float(color["l"]), float(color["c"]), float(color["h"] or 0.0)])
    return np.asarray(rows, dtype=np.float64)


def result_hex(mode: str, result: dict[str, Any]) -> list[str]:
    if mode == "legacy":
        return [str(color["hex"]).lower() for color in result["palette"]["colors"]]
    try:
        from .color_math import oklch_to_srgb
    except ImportError:
        from color_math import oklch_to_srgb  # type: ignore[no-redef]

    rendered: list[str] = []
    for color in result["result"]["colors"]:
        red, green, blue = oklch_to_srgb(
            float(color["l"]), float(color["c"]), float(color["h"] or 0.0)
        )
        channels = [round(255 * min(1.0, max(0.0, value))) for value in (red, green, blue)]
        rendered.append("#" + "".join(f"{channel:02x}" for channel in channels))
    return rendered


def build_requests(mode: str) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    color_fixture = load_color_family_fixture()
    semantic_fixture = load_semantic_release_fixture()
    seeds = [int(seed) for seed in color_fixture["seeds"]]
    count = int(color_fixture["defaultCount"])
    requests: list[dict[str, Any]] = []
    labels: dict[str, dict[str, Any]] = {}

    def add(identifier: str, prompt: str, requested_count: int, seed: int, kind: str, **extra: Any) -> None:
        request: dict[str, Any] = {
            "id": identifier,
            "prompt": prompt,
            "count": requested_count,
            "seed": seed,
        }
        if mode == "palettebrain":
            request["lockedColors"] = extra.pop("lockedColors", [])
        requests.append(request)
        labels[identifier] = {"kind": kind, "prompt": prompt, "seed": seed, **extra}

    for prompt_index, case in enumerate(color_fixture["prompts"]):
        for seed in seeds:
            add(f"direct-{prompt_index}-{seed}", case["prompt"], count, seed, "direct", prompt_id=case["id"])

    semantic_prompts = {
        prompt
        for pair_name in ("modifierPairs", "translationPairs")
        for pair in semantic_fixture[pair_name]
        for prompt in pair
    } | set(semantic_fixture["requiredSanityOutputs"])
    for prompt_index, prompt in enumerate(sorted(semantic_prompts)):
        for seed in seeds:
            add(f"semantic-{prompt_index}-{seed}", prompt, count, seed, "semantic")

    for requested_count in range(2, 10):
        add(f"count-{requested_count}", "winter forest", requested_count, 42, "count")
    add("determinism-a", "frozen vineyard at midnight", count, 1337, "determinism")
    add("determinism-b", "frozen vineyard at midnight", count, 1337, "determinism")
    if mode == "palettebrain":
        add(
            "lock",
            "warm childhood kitchen",
            count,
            42,
            "lock",
            lockedColors=[{"index": 1, "oklch": {"l": 0.5, "c": 0.0, "h": None}}],
        )
    return requests, labels


def evaluate_mode(mode: str) -> dict[str, Any]:
    color_fixture = load_color_family_fixture()
    semantic_fixture = load_semantic_release_fixture()
    requests, labels = build_requests(mode)
    raw_results, runtime = run_harness(mode, requests)
    by_id = {str(result["id"]): result for result in raw_results}

    direct_records = [
        {
            "prompt_id": label["prompt_id"],
            "prompt": label["prompt"],
            "seed": label["seed"],
            "palette": result_palette(mode, by_id[identifier]),
        }
        for identifier, label in labels.items()
        if label["kind"] == "direct"
    ]
    direct = evaluate_direct_color_records(
        direct_records, fixture=color_fixture, color_space="oklch"
    )

    palettes_by_prompt: dict[str, dict[int, np.ndarray]] = {}
    for identifier, label in labels.items():
        if label["kind"] == "semantic":
            palettes_by_prompt.setdefault(label["prompt"], {})[label["seed"]] = result_palette(
                mode, by_id[identifier]
            )
    modifier = summarize_modifier_sensitivity(
        palettes_by_prompt,
        semantic_fixture=semantic_fixture,
        color_fixture=color_fixture,
        color_space="oklch",
    )
    translation = summarize_ru_en_parity(
        palettes_by_prompt,
        semantic_fixture=semantic_fixture,
        color_fixture=color_fixture,
        color_space="oklch",
    )

    direct_palettes = [record["palette"] for record in direct_records]
    near_duplicates = near_duplicate_palette_rate(
        direct_palettes, fixture=color_fixture, color_space="oklch"
    )
    determinism = deterministic_palette_equality(
        result_palette(mode, by_id["determinism-a"]),
        result_palette(mode, by_id["determinism-b"]),
    )
    count_correct = all(
        len(result_palette(mode, by_id[f"count-{count}"])) == count for count in range(2, 10)
    )
    seed_distances: list[float] = []
    for case in color_fixture["prompts"]:
        variants = [
            record["palette"]
            for record in direct_records
            if record["prompt_id"] == case["id"]
        ]
        for left, right in zip(variants, variants[1:]):
            seed_distances.append(
                hungarian_matched_set_distance(
                    left, right, left_color_space="oklch", right_color_space="oklch"
                )
            )

    sanity = {
        prompt: result_hex(
            mode,
            by_id[
                next(
                    identifier
                    for identifier, label in labels.items()
                    if label["kind"] == "semantic" and label["prompt"] == prompt and label["seed"] == 42
                )
            ],
        )
        for prompt in semantic_fixture["requiredSanityOutputs"]
    }
    lock_preserved = None
    if mode == "palettebrain":
        locked = result_palette(mode, by_id["lock"])[1]
        lock_preserved = bool(np.array_equal(locked, np.asarray([0.5, 0.0, 0.0])))

    return {
        "id": "A-legacy-guarded-procedural" if mode == "legacy" else "B-synthetic-palettebrain",
        "mode": mode,
        "rawNeural": mode == "palettebrain",
        "direct": direct,
        "nearDuplicates": near_duplicates,
        "modifierSensitivity": modifier,
        "ruEnParity": translation,
        "deterministic": determinism,
        "countCorrect2To9": count_correct,
        "runtimeLockPreserved": lock_preserved,
        "meanCrossSeedSetDistance": float(np.mean(seed_distances)),
        "sanityHex": sanity,
        "runtime": runtime,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", default="ml/palettebrain/reports/browser-baselines-release.v1.json"
    )
    args = parser.parse_args()
    output_path = Path(args.output)
    result = {
        "schemaVersion": 1,
        "status": "frozen_before_candidate_1",
        "colorFixtureSha256": sha256_file(Path("ml/palettebrain/benchmark_color_families.v1.json")),
        "semanticFixtureSha256": sha256_file(Path("ml/palettebrain/benchmark_semantic_release.v1.json")),
        "baselines": [evaluate_mode("legacy"), evaluate_mode("palettebrain")],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(output_path.name + ".tmp")
    try:
        temporary.write_text(
            json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(output_path)
    finally:
        temporary.unlink(missing_ok=True)
    print(
        json.dumps(
            {
                baseline["id"]: baseline["direct"]["aggregate"]
                for baseline in result["baselines"]
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
