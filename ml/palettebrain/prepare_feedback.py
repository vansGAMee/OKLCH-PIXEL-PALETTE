"""Convert consented, versioned feedback events into explicit GOOD > BAD pairs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable


EVENT_SCHEMA_VERSION = 1
PAIR_SCHEMA_VERSION = 1


def read_events(path: Path) -> list[dict[str, Any]]:
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    if raw.startswith("["):
        payload = json.loads(raw)
        if not isinstance(payload, list):
            raise ValueError("JSON input must be an array of events")
        return [dict(item) for item in payload]
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def normalize_palette(value: Any, field_name: str) -> list[dict[str, float]]:
    if not isinstance(value, list) or not 2 <= len(value) <= 9:
        raise ValueError(f"{field_name} must contain 2..9 colors")
    normalized: list[dict[str, float]] = []
    for color in value:
        if not isinstance(color, dict):
            raise ValueError(f"{field_name} colors must be objects")
        try:
            lightness = float(color["l"])
            chroma = float(color["c"])
            hue = float(color["h"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} colors require numeric l/c/h") from exc
        if not (0.0 <= lightness <= 1.0 and chroma >= 0.0):
            raise ValueError(f"{field_name} has an out-of-range color")
        normalized.append({"l": lightness, "c": chroma, "h": hue % 360.0})
    return normalized


def candidate_palettes(event: dict[str, Any]) -> tuple[Any, list[Any]] | None:
    if "goodPalette" in event and "badPalette" in event:
        return event["goodPalette"], [event["badPalette"]]
    if "chosenPalette" in event and "rejectedPalettes" in event:
        rejected = event["rejectedPalettes"]
        if isinstance(rejected, list):
            return event["chosenPalette"], rejected

    if event.get("event") == "candidate_selected" and "palette" in event:
        selected_id = event.get("candidateId")
        rejected: list[Any] = []
        for candidate in event.get("candidates", []):
            if not isinstance(candidate, dict):
                continue
            if candidate.get("candidateId") != selected_id and "palette" in candidate:
                rejected.append(candidate["palette"])
        if rejected:
            return event["palette"], rejected
    return None


def convert_events(
    events: Iterable[dict[str, Any]],
    *,
    include_raw_prompts: bool,
    strict: bool,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    pairs: list[dict[str, Any]] = []
    stats = {"events": 0, "pairs": 0, "skipped": 0, "invalid": 0}
    for event_index, event in enumerate(events):
        stats["events"] += 1
        try:
            if int(event.get("schemaVersion", -1)) != EVENT_SCHEMA_VERSION:
                raise ValueError("unsupported feedback schemaVersion")
            candidates = candidate_palettes(event)
            if candidates is None:
                stats["skipped"] += 1
                continue
            good_raw, bad_values = candidates
            good = normalize_palette(good_raw, "good palette")
            for bad_index, bad_raw in enumerate(bad_values):
                bad = normalize_palette(bad_raw, "bad palette")
                if good == bad:
                    continue
                pair: dict[str, Any] = {
                    "schemaVersion": PAIR_SCHEMA_VERSION,
                    "relation": "GOOD>BAD",
                    "sourceEvent": str(event.get("event", "explicit_pair")),
                    "sourceEventIndex": event_index,
                    "sourcePairIndex": bad_index,
                    "modelVersion": event.get("modelVersion"),
                    "encoderVersion": event.get("encoderVersion"),
                    "requestedCount": int(event.get("requestedCount", len(good))),
                    "seed": event.get("seed"),
                    "promptRepresentation": event.get("promptRepresentation"),
                    "good": good,
                    "bad": bad,
                }
                if (
                    include_raw_prompts
                    and event.get("rawPromptConsent") is True
                    and isinstance(event.get("prompt"), str)
                ):
                    pair["prompt"] = event["prompt"]
                pairs.append(pair)
        except (TypeError, ValueError) as exc:
            stats["invalid"] += 1
            if strict:
                raise ValueError(f"event {event_index}: {exc}") from exc
    stats["pairs"] = len(pairs)
    return pairs, stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Feedback JSON array or JSONL file")
    parser.add_argument("output", help="Output GOOD>BAD JSONL file")
    parser.add_argument(
        "--include-raw-prompts",
        action="store_true",
        help="Include a prompt only when each event also has rawPromptConsent=true.",
    )
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    events = read_events(Path(args.input))
    pairs, stats = convert_events(
        events,
        include_raw_prompts=args.include_raw_prompts,
        strict=args.strict,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "".join(
            json.dumps(pair, ensure_ascii=False, separators=(",", ":")) + "\n"
            for pair in pairs
        ),
        encoding="utf-8",
    )
    print(json.dumps(stats, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
