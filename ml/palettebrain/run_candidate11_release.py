"""Resumable, one-command Candidate 11 training and release pipeline.

This file only orchestrates the repository's existing builders, trainers, and
evaluators.  It never overwrites the protected historical checkpoints.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
ML = ROOT / "ml" / "palettebrain"
REPORTS = ML / "reports"
LOGS = REPORTS / "candidate-11-logs"
STATE_PATH = REPORTS / "candidate-11-run-state.json"
PREFLIGHT_REPORT = REPORTS / "candidate-11-preflight.json"
PYTHON = Path(sys.executable).resolve()
SEED = "20260826"

PROTECTED = {
    (ML / "checkpoints" / "candidate-7-best.pt").resolve(),
    (ML / "checkpoints" / "candidate-8-best.pt").resolve(),
    (ML / "checkpoints" / "candidate-11-best.pt").resolve(),
}
HISTORICAL_C11 = ML / "checkpoints" / "candidate-11-best.pt"
BASE = ML / "checkpoints" / "candidate-11-base.pt"

SMOKE_SOURCE = ML / "data" / "palettebrain_c11_smoke_recovered_source.npz"
FULL_SOURCE = ML / "data" / "palettebrain_c11_recovered_source.npz"
TRAIN_DATA = ML / "data" / "palettebrain_c11_repaired_v2.npz"
STAGE_A = ML / "checkpoints" / "candidate-11-stage-a-best.pt"
STAGE_B = ML / "checkpoints" / "candidate-11-stage-b-best.pt"
STAGE_A_EVAL = REPORTS / "candidate-11-stage-a-semantic-v3.json"
STAGE_B_EVAL = REPORTS / "candidate-11-stage-b-semantic-v3.json"
STAGE_A_SELECTION = REPORTS / "candidate-11-stage-a-dev-selection.json"
STAGE_B_SELECTION = REPORTS / "candidate-11-stage-b-dev-selection.json"
RELEASE_EVAL = REPORTS / "candidate-11-release-semantic-v3.json"
SEALED_EVAL = REPORTS / "candidate-11-sealed-evaluation.json"
VISUAL_REPORT = REPORTS / "candidate-11-visual-report.html"
ONNX = ROOT / "public" / "models" / "palettebrain-v4-candidate11-repaired.onnx"
MANIFEST = ROOT / "public" / "models" / "palettebrain-v2.manifest.json"
PARITY = REPORTS / "candidate-11-parity.json"
BROWSER_EMBEDDINGS = REPORTS / "candidate-11-browser-embeddings.json"
BROWSER_PALETTES = REPORTS / "candidate-11-browser-current-parity.json"
BROWSER_EMBEDDING_INPUT = REPORTS / "candidate-11-browser-embedding-input.json"
BROWSER_PALETTE_INPUT = REPORTS / "candidate-11-browser-palette-input.json"
BROWSER_SMOKE = REPORTS / "real-browser-semantic-smoke.json"
QUALIFICATION = REPORTS / "candidate-11-stage-b-qualification.json"
DEV_QUALIFICATION = REPORTS / "candidate-11-dev-qualification.json"

PHASE_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "source_data_preflight": ("validate_benchmarks.py", "benchmark_semantic_v3.json", "benchmark_visual_semantic_v2.json"),
    "smoke_48_images": ("prepare_c11_recovered_source.py", "c11_training_concepts.v1.json", "c11_source_manifest.v1.json"),
    "full_visual_source": ("prepare_c11_recovered_source.py", "c11_training_concepts.v1.json", "c11_source_manifest.v1.json"),
    "repaired_training_dataset": ("build_c11_dataset.py",),
    "stage_a": ("train_candidate11.py", "model.py", "train_decoder.py", "color_distribution.py"),
    "stage_b": ("train_candidate11.py", "model.py", "train_decoder.py", "color_distribution.py"),
    "stage_a_dev_selection": ("select_candidate11_checkpoint.py", "evaluate_semantic_v3.py", "benchmark_semantic_v3.json"),
    "stage_b_dev_selection": ("select_candidate11_checkpoint.py", "evaluate_semantic_v3.py", "benchmark_semantic_v3.json"),
    "stage_a_semantic_evaluation": ("evaluate_semantic_v3.py", "benchmark_semantic_v3.json", "benchmark_visual_semantic_v2.json"),
    "frozen_pytorch_evaluation": ("evaluate_semantic_v3.py", "benchmark_semantic_v3.json", "benchmark_visual_semantic_v2.json"),
    "visual_report": ("inspect_semantics.py",),
    "onnx_export": ("export_c11_onnx.py", "model.py"),
    "pytorch_ort_parity": ("parity_harness.py", "model.py", "color_math.py"),
    "ort_browser_parity": ("parity_harness.py", "browser_runtime_harness.mjs", "model.py"),
    "browser_semantic_smoke": ("../../scripts/test-real-browser.mjs", "../../src/lib/ai-palette/inference.ts", "../../src/lib/ai-palette/paletteAdapter.ts"),
    "canonical_qualification": ("evaluate_semantic_v3.py", "qualify_candidate.py", "benchmark_semantic_v3.json"),
}


def configure_engineering_smoke_paths() -> None:
    global STATE_PATH, PREFLIGHT_REPORT, LOGS, TRAIN_DATA, STAGE_A, STAGE_B, STAGE_A_EVAL
    global STAGE_B_EVAL, STAGE_A_SELECTION, STAGE_B_SELECTION, RELEASE_EVAL, SEALED_EVAL
    global VISUAL_REPORT, ONNX, PARITY, BROWSER_EMBEDDINGS, BROWSER_PALETTES
    global BROWSER_EMBEDDING_INPUT, BROWSER_PALETTE_INPUT
    global BROWSER_SMOKE, QUALIFICATION, DEV_QUALIFICATION
    STATE_PATH = REPORTS / "candidate-11-engineering-smoke-run-state.json"
    PREFLIGHT_REPORT = REPORTS / "candidate-11-engineering-smoke-preflight.json"
    LOGS = REPORTS / "candidate-11-engineering-smoke-logs"
    TRAIN_DATA = ML / "data" / "palettebrain_c11_engineering_smoke.npz"
    STAGE_A = ML / "checkpoints" / "candidate-11-smoke-stage-a-best.pt"
    STAGE_B = ML / "checkpoints" / "candidate-11-smoke-stage-b-best.pt"
    STAGE_A_EVAL = REPORTS / "candidate-11-smoke-stage-a-dev.json"
    STAGE_B_EVAL = REPORTS / "candidate-11-smoke-stage-b-dev.json"
    STAGE_A_SELECTION = REPORTS / "candidate-11-smoke-stage-a-selection.json"
    STAGE_B_SELECTION = REPORTS / "candidate-11-smoke-stage-b-selection.json"
    RELEASE_EVAL = REPORTS / "candidate-11-smoke-release-evidence.json"
    SEALED_EVAL = REPORTS / "candidate-11-smoke-sealed-evidence.json"
    VISUAL_REPORT = REPORTS / "candidate-11-smoke-visual-report.html"
    ONNX = ROOT / "public" / "models" / "palettebrain-v4-candidate11-engineering-smoke.onnx"
    PARITY = REPORTS / "candidate-11-smoke-parity.json"
    BROWSER_EMBEDDINGS = REPORTS / "candidate-11-smoke-browser-embeddings.json"
    BROWSER_PALETTES = REPORTS / "candidate-11-smoke-browser-palettes.json"
    BROWSER_EMBEDDING_INPUT = REPORTS / "candidate-11-smoke-browser-embedding-input.json"
    BROWSER_PALETTE_INPUT = REPORTS / "candidate-11-smoke-browser-palette-input.json"
    BROWSER_SMOKE = REPORTS / "candidate-11-smoke-browser-evidence.json"
    QUALIFICATION = REPORTS / "candidate-11-smoke-qualification.json"
    DEV_QUALIFICATION = REPORTS / "candidate-11-smoke-dev-qualification.json"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def phase_dependency_fingerprint(name: str) -> str:
    digest = hashlib.sha256()
    for relative_name in PHASE_DEPENDENCIES.get(name, ("run_candidate11_release.py",)):
        path = (ML / relative_name).resolve()
        digest.update(relative_name.encode("utf-8"))
        digest.update(sha256_file(path).encode("ascii"))
    return digest.hexdigest()


def training_dependency_fingerprint() -> str:
    return phase_dependency_fingerprint("stage_a")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for attempt in range(5):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.05 * (attempt + 1))


def artifact(path: Path, metrics: dict[str, Any] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"artifact": relative(path), "timestamp": now()}
    if path.is_file():
        result.update({"sha256": sha256_file(path), "bytes": path.stat().st_size})
    if metrics:
        result["metrics"] = metrics
    return result


def source_valid(report_path: Path, output: Path, minimum: int) -> tuple[bool, dict[str, Any]]:
    report = load_json(report_path)
    count = int(report.get("validUniqueImages", 0) or 0)
    valid = (
        output.is_file()
        and count >= minimum
        and report.get("sha256") == sha256_file(output)
        and report.get("output") == relative(output)
    )
    return valid, {"validUniqueImages": count, "minimum": minimum}


def dataset_valid() -> tuple[bool, dict[str, Any]]:
    report = load_json(REPORTS / "candidate-11-repaired-dataset-audit.json")
    valid = TRAIN_DATA.is_file() and report.get("pass") is True and report.get("sha256") == sha256_file(TRAIN_DATA)
    return valid, {"recordCount": report.get("recordCount"), "pass": report.get("pass")}


def checkpoint_valid(path: Path, stage: str, final_epoch: int) -> tuple[bool, dict[str, Any]]:
    last_path = path.with_name(f"{path.stem.removesuffix('-best')}-last{path.suffix}")
    if not path.is_file() or not last_path.is_file():
        return False, {"epoch": None}
    import torch

    try:
        checkpoint = torch.load(path, map_location="cpu", weights_only=True)
        last_checkpoint = torch.load(last_path, map_location="cpu", weights_only=True)
        epoch = int(last_checkpoint.get("epoch", -1))
        valid = (
            checkpoint.get("candidate") == "candidate-11"
            and checkpoint.get("stage") == stage
            and last_checkpoint.get("candidate") == "candidate-11"
            and last_checkpoint.get("stage") == stage
            and epoch >= final_epoch
            and checkpoint.get("epoch_complete", True) is True
        )
        return valid, {"completedEpoch": epoch, "bestEpoch": checkpoint.get("epoch"), "stage": checkpoint.get("stage")}
    except Exception as error:
        return False, {"error": str(error)}


def training_valid(path: Path, stage: str, final_epoch: int) -> tuple[bool, dict[str, Any]]:
    last_path = path.with_name(f"{path.stem.removesuffix('-best')}-last{path.suffix}")
    candidates = list(path.parent.glob(
        f"{path.stem.removesuffix('-best')}-dev-epoch-*{path.suffix}"
    ))
    if not last_path.is_file() or not candidates:
        return False, {"completedEpoch": None, "candidateCount": len(candidates)}
    import torch
    try:
        checkpoint = torch.load(last_path, map_location="cpu", weights_only=True)
        epoch = int(checkpoint.get("epoch", -1))
        valid = (
            checkpoint.get("candidate") == "candidate-11"
            and checkpoint.get("stage") == stage
            and epoch >= final_epoch
            and checkpoint.get("epoch_complete", True) is True
            and checkpoint.get("dataset_identity", {}).get("primary") == sha256_file(TRAIN_DATA)
            and checkpoint.get("dependency_fingerprint") == training_dependency_fingerprint()
        )
        return valid, {"completedEpoch": epoch, "candidateCount": len(candidates)}
    except Exception as error:
        return False, {"error": str(error), "candidateCount": len(candidates)}


def selection_valid(path: Path, output: Path, stage: str) -> tuple[bool, dict[str, Any]]:
    report = load_json(path)
    valid = (
        output.is_file()
        and report.get("stage") == stage
        and report.get("selectedCheckpoint") == relative(output)
        and report.get("selectedCheckpointSha256") == sha256_file(output)
        and report.get("datasetSha256") == sha256_file(TRAIN_DATA)
    )
    if "smoke" in path.name:
        valid = valid and report.get("testClassification") == "ENGINEERING_SMOKE_ONLY" and report.get("productionReady") is False
    return valid, {"candidateCount": len(report.get("candidates", [])), "selected": report.get("selectedSourceCheckpoint")}


def semantic_valid(
    path: Path, require_gate: bool, checkpoint: Path | None = None
) -> tuple[bool, dict[str, Any]]:
    report = load_json(path)
    metric = report.get("metrics", {}).get("semanticFamilyWin")
    source_valid = checkpoint is None or (
        checkpoint.is_file()
        and report.get("sources", {}).get("checkpointSha256") == sha256_file(checkpoint)
        and report.get("sources", {}).get("datasetSha256") == sha256_file(TRAIN_DATA)
    )
    if "smoke" in path.name:
        source_valid = source_valid and report.get("testClassification") == "ENGINEERING_SMOKE_ONLY" and report.get("productionReady") is False
    valid = source_valid and isinstance(metric, (int, float)) and (not require_gate or metric >= 0.80)
    return valid, {"semanticFamilyWin": metric, "gate": 0.80 if require_gate else None}


def manifest_valid() -> tuple[bool, dict[str, Any]]:
    manifest = load_json(MANIFEST)
    decoder = manifest.get("decoder", {})
    valid = ONNX.is_file() and decoder.get("sha256") == sha256_file(ONNX) and decoder.get("bytes") == ONNX.stat().st_size
    return valid, {"modelVersion": manifest.get("modelVersion"), "productionReady": manifest.get("productionReady", False)}


class Runner:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        existing = load_json(STATE_PATH) if args.resume else {}
        self.state: dict[str, Any] = existing or {
            "schemaVersion": 1,
            "candidate": "candidate-11",
            "branch": "codex/candidate11-recovery",
            "productionReady": False,
            "codename": None,
            "phases": {},
        }
        smoke_flag = " --engineering-smoke" if args.engineering_smoke else ""
        self.state["command"] = f"{relative(PYTHON)} -u ml/palettebrain/run_candidate11_release.py --device {args.device} --resume{smoke_flag}"
        self.state["logsDirectory"] = relative(LOGS)
        if args.engineering_smoke:
            self.state["testClassification"] = "ENGINEERING_SMOKE_ONLY"
        LOGS.mkdir(parents=True, exist_ok=True)
        self.save()

    def save(self) -> None:
        self.state["updatedAt"] = now()
        atomic_json(STATE_PATH, self.state)

    def record(self, name: str, status: str, details: dict[str, Any]) -> None:
        self.state["currentPhase"] = name
        self.state.setdefault("phases", {})[name] = {
            "status": status,
            "dependencyFingerprint": phase_dependency_fingerprint(name),
            **details,
        }
        self.save()

    def command(
        self, phase: str, command: list[str], environment: dict[str, str] | None = None
    ) -> None:
        log_path = LOGS / f"{phase}.log"
        print(f"[{phase}] log: {relative(log_path)}", flush=True)
        tail: deque[str] = deque(maxlen=12)
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"\n[{now()}] {' '.join(command)}\n")
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=environment,
            )
            assert process.stdout is not None
            for line in process.stdout:
                print(line, end="", flush=True)
                log.write(line)
                log.flush()
                if line.strip():
                    tail.append(line.strip())
            code = process.wait()
        if code:
            detail = tail[-1] if tail else "no diagnostic output"
            raise RuntimeError(
                f"command exited with code {code}: {detail}; "
                f"see {relative(log_path)}"
            )

    def smoke_flag(self, command: list[str]) -> list[str]:
        return [*command, "--engineering-smoke"] if self.args.engineering_smoke else command

    def phase(
        self,
        name: str,
        validator: Callable[[], tuple[bool, dict[str, Any]]],
        action: Callable[[], None],
        output: Path,
    ) -> None:
        print(f"\n=== Candidate 11 phase: {name} ===", flush=True)
        valid, metrics = validator()
        recorded = self.state.get("phases", {}).get(name, {})
        current_fingerprint = phase_dependency_fingerprint(name)
        valid = valid and recorded.get("dependencyFingerprint") == current_fingerprint
        metrics = {**metrics, "dependencyFingerprint": current_fingerprint}
        if valid:
            print(f"PASS (verified existing artifact): {relative(output)}", flush=True)
            self.record(name, "passed", artifact(output, metrics))
            return
        self.record(name, "running", {"timestamp": now(), "metrics": metrics})
        try:
            action()
            valid, metrics = validator()
            if not valid:
                raise RuntimeError(f"phase artifact failed validation: {metrics}")
            self.record(name, "passed", artifact(output, metrics))
            print(f"PASS: {relative(output)}", flush=True)
        except Exception as error:
            self.record(name, "failed", {"timestamp": now(), "reason": str(error), "metrics": metrics})
            print(f"HARD STOP in {name}: {error}", flush=True)
            print(f"Resume with: {self.state['command']}", flush=True)
            raise

    def run(self) -> None:
        phases: list[tuple[str, Callable[[], None]]] = [
            ("source_data_preflight", self.preflight),
            ("smoke_48_images", self.smoke),
            ("full_visual_source", self.full_source),
            ("repaired_training_dataset", self.training_dataset),
            ("stage_a", self.stage_a),
            ("stage_a_dev_selection", self.stage_a_selection),
            ("stage_a_semantic_evaluation", self.stage_a_evaluation),
            ("stage_b", self.stage_b),
            ("stage_b_dev_selection", self.stage_b_selection),
            ("frozen_pytorch_evaluation", self.frozen_evaluation),
            ("visual_report", self.visual_report),
            ("onnx_export", self.onnx_export),
            ("pytorch_ort_parity", self.pytorch_ort_parity),
            ("ort_browser_parity", self.ort_browser_parity),
            ("browser_semantic_smoke", self.browser_semantic_smoke),
            ("canonical_qualification", self.canonical_qualification),
        ]
        for name, operation in phases:
            operation()
            if self.args.stop_after == name:
                print(f"Stopped after requested phase: {name}")
                return
        self.state["currentPhase"] = "complete"
        qualification = load_json(QUALIFICATION)
        self.state["productionReady"] = qualification.get("productionReady") is True
        self.state["codename"] = qualification.get("codename")
        self.save()
        if self.state["productionReady"]:
            print("Candidate 11 release qualification PASS.")
        else:
            print("Candidate 11 experimental model integrated; productionReady=false.")

    def preflight(self) -> None:
        output = PREFLIGHT_REPORT

        def validate() -> tuple[bool, dict[str, Any]]:
            report = load_json(output)
            protected = all(path.is_file() for path in PROTECTED) and BASE.is_file()
            return report.get("pass") is True and protected, {"protectedCheckpointsPresent": protected}

        def action() -> None:
            branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()
            if branch in {"main", "master"}:
                raise RuntimeError("refusing to run Candidate 11 release on the production branch")
            self.command("source_data_preflight", [str(PYTHON), str(ML / "validate_benchmarks.py")])
            if not BASE.exists():
                temporary = BASE.with_suffix(BASE.suffix + ".tmp")
                shutil.copyfile(HISTORICAL_C11, temporary)
                temporary.replace(BASE)
            required = [ML / "c11_training_concepts.v1.json", ML / "c11_source_manifest.v1.json", *PROTECTED, BASE]
            missing = [relative(path) for path in required if not path.is_file()]
            atomic_json(output, {"pass": not missing, "branch": branch, "missing": missing, "timestamp": now(), "testClassification": "ENGINEERING_SMOKE_ONLY" if self.args.engineering_smoke else "REAL_PREFLIGHT", "productionReady": False})
            if missing:
                raise RuntimeError(f"missing required artifacts: {missing}")

        self.phase("source_data_preflight", validate, action, output)

    def smoke(self) -> None:
        report = REPORTS / "candidate-11-source-smoke.json"
        self.phase(
            "smoke_48_images",
            lambda: source_valid(report, SMOKE_SOURCE, 48),
            lambda: self.command("smoke_48_images", [str(PYTHON), "-u", str(ML / "prepare_c11_recovered_source.py"), "--smoke", "--limit-images", "48", "--output", relative(SMOKE_SOURCE), "--device", self.args.device, "--seed", SEED]),
            SMOKE_SOURCE,
        )

    def full_source(self) -> None:
        if self.args.engineering_smoke:
            self.phase(
                "full_visual_source",
                lambda: source_valid(REPORTS / "candidate-11-source-smoke.json", SMOKE_SOURCE, 48),
                lambda: None,
                SMOKE_SOURCE,
            )
            return
        report = REPORTS / "candidate-11-source-full.json"
        self.phase(
            "full_visual_source",
            lambda: source_valid(report, FULL_SOURCE, 1500),
            lambda: self.command("full_visual_source", [str(PYTHON), "-u", str(ML / "prepare_c11_recovered_source.py"), "--output", relative(FULL_SOURCE), "--device", self.args.device, "--seed", SEED]),
            FULL_SOURCE,
        )

    def training_dataset(self) -> None:
        report = REPORTS / "candidate-11-repaired-dataset-audit.json"
        if self.args.engineering_smoke:
            report = REPORTS / "candidate-11-engineering-smoke-dataset-audit.json"
        command = [str(PYTHON), str(ML / "build_c11_dataset.py"), "--input", relative(SMOKE_SOURCE if self.args.engineering_smoke else FULL_SOURCE), "--output", relative(TRAIN_DATA), "--report", relative(report)]
        if self.args.engineering_smoke:
            command.append("--engineering-smoke")
        self.phase(
            "repaired_training_dataset",
            lambda: (TRAIN_DATA.is_file() and load_json(report).get("pass") is True and load_json(report).get("sha256") == sha256_file(TRAIN_DATA), {"recordCount": load_json(report).get("recordCount"), "pass": load_json(report).get("pass")}),
            lambda: self.command("repaired_training_dataset", command),
            TRAIN_DATA,
        )

    def train_command(self, stage: str) -> list[str]:
        is_a = stage == "a"
        output, epochs = ((STAGE_A, 1) if is_a else (STAGE_B, 1)) if self.args.engineering_smoke else ((STAGE_A, 30) if is_a else (STAGE_B, 20))
        command = [str(PYTHON), "-u", str(ML / "train_candidate11.py"), "--stage", stage, "--data", relative(TRAIN_DATA), "--initialize-from", relative(BASE if is_a else STAGE_A), "--output", relative(output), "--epochs", str(epochs), "--batch-size", "32", "--new-lr", "3e-4" if is_a else "1e-4", "--inherited-lr", "2e-5", "--seed", SEED, "--device", self.args.device]
        valid, _ = training_valid(output, stage, epochs - 1)
        last_output = output.with_name(f"{output.stem.removesuffix('-best')}-last{output.suffix}")
        if last_output.is_file() and not valid:
            import torch
            try:
                resume_checkpoint = torch.load(last_output, map_location="cpu", weights_only=True)
                compatible = (
                    resume_checkpoint.get("candidate") == "candidate-11"
                    and resume_checkpoint.get("stage") == stage
                    and resume_checkpoint.get("dataset_identity", {}).get("primary") == sha256_file(TRAIN_DATA)
                    and resume_checkpoint.get("dependency_fingerprint") == training_dependency_fingerprint()
                )
            except Exception:
                compatible = False
            if compatible:
                command.extend(["--resume", relative(last_output)])
            else:
                last_output.unlink(missing_ok=True)
                output.unlink(missing_ok=True)
                for stale in output.parent.glob(
                    f"{output.stem.removesuffix('-best')}-dev-epoch-*{output.suffix}"
                ):
                    stale.unlink(missing_ok=True)
        if not is_a:
            command.extend(["--stage-a-eval-report", relative(STAGE_A_EVAL), "--replay-data", "ml/palettebrain/data/palettebrain_candidate3_direct8_v1.npz"])
        return command

    def stage_a(self) -> None:
        final_epoch = 0 if self.args.engineering_smoke else 29
        self.phase("stage_a", lambda: training_valid(STAGE_A, "a", final_epoch), lambda: self.command("stage_a", self.train_command("a")), STAGE_A.with_name(f"{STAGE_A.stem.removesuffix('-best')}-last.pt"))

    def stage_a_selection(self) -> None:
        self.phase("stage_a_dev_selection", lambda: selection_valid(STAGE_A_SELECTION, STAGE_A, "a"), lambda: self.command("stage_a_dev_selection", self.smoke_flag([str(PYTHON), str(ML / "select_candidate11_checkpoint.py"), "--stage", "a", "--output", relative(STAGE_A), "--report", relative(STAGE_A_SELECTION), "--dataset", relative(TRAIN_DATA), "--device", self.args.device])), STAGE_A_SELECTION)

    def stage_a_evaluation(self) -> None:
        self.phase("stage_a_semantic_evaluation", lambda: semantic_valid(STAGE_A_EVAL, not self.args.engineering_smoke, STAGE_A), lambda: self.command("stage_a_semantic_evaluation", self.smoke_flag([str(PYTHON), str(ML / "evaluate_semantic_v3.py"), "--checkpoint", relative(STAGE_A), "--output", relative(STAGE_A_EVAL), "--dataset", relative(TRAIN_DATA), "--device", self.args.device])), STAGE_A_EVAL)

    def stage_b(self) -> None:
        final_epoch = 0 if self.args.engineering_smoke else 19
        self.phase("stage_b", lambda: training_valid(STAGE_B, "b", final_epoch), lambda: self.command("stage_b", self.train_command("b")), STAGE_B.with_name(f"{STAGE_B.stem.removesuffix('-best')}-last.pt"))

    def stage_b_selection(self) -> None:
        self.phase("stage_b_dev_selection", lambda: selection_valid(STAGE_B_SELECTION, STAGE_B, "b"), lambda: self.command("stage_b_dev_selection", self.smoke_flag([str(PYTHON), str(ML / "select_candidate11_checkpoint.py"), "--stage", "b", "--output", relative(STAGE_B), "--report", relative(STAGE_B_SELECTION), "--dataset", relative(TRAIN_DATA), "--device", self.args.device])), STAGE_B_SELECTION)

    def frozen_evaluation(self) -> None:
        self.phase("frozen_pytorch_evaluation", lambda: semantic_valid(STAGE_B_EVAL, False, STAGE_B), lambda: self.command("frozen_pytorch_evaluation", self.smoke_flag([str(PYTHON), str(ML / "evaluate_semantic_v3.py"), "--checkpoint", relative(STAGE_B), "--output", relative(STAGE_B_EVAL), "--dataset", relative(TRAIN_DATA), "--device", self.args.device])), STAGE_B_EVAL)

    def visual_report(self) -> None:
        def validate() -> tuple[bool, dict[str, Any]]:
            return VISUAL_REPORT.is_file() and VISUAL_REPORT.stat().st_size > 1000, {"bytes": VISUAL_REPORT.stat().st_size if VISUAL_REPORT.exists() else 0}

        def action() -> None:
            generic_outputs = [
                REPORTS / "semantic_color_table.html",
                REPORTS / "semantic_color_table.csv",
                REPORTS / "semantic_embedding_map.html",
            ]
            backups = {path: path.read_bytes() for path in generic_outputs if path.is_file()} if self.args.engineering_smoke else {}
            try:
                self.command("visual_report", [str(PYTHON), str(ML / "inspect_semantics.py"), "--checkpoint", relative(STAGE_B), "--output-dir", relative(REPORTS), "--device", self.args.device])
                shutil.copyfile(REPORTS / "semantic_color_table.html", VISUAL_REPORT)
            finally:
                for path, content in backups.items():
                    temporary = path.with_suffix(path.suffix + ".restore")
                    temporary.write_bytes(content)
                    temporary.replace(path)

        self.phase("visual_report", validate, action, VISUAL_REPORT)

    def onnx_export(self) -> None:
        self.phase("onnx_export", manifest_valid, lambda: self.command("onnx_export", [str(PYTHON), str(ML / "export_c11_onnx.py"), "--checkpoint", relative(STAGE_B), "--output", relative(ONNX), "--manifest", relative(MANIFEST)]), ONNX)

    def pytorch_ort_parity(self) -> None:
        def validate() -> tuple[bool, dict[str, Any]]:
            report = load_json(PARITY)
            delta = report.get("pytorchOnnx", {}).get("maxAbsDelta")
            classification_ok = not self.args.engineering_smoke or (report.get("testClassification") == "ENGINEERING_SMOKE_ONLY" and report.get("productionReady") is False)
            return classification_ok and report.get("pytorchOnnx", {}).get("pass") is True and report.get("artifacts", {}).get("onnxSha256") == sha256_file(ONNX), {"maxAbsDelta": delta}

        self.phase("pytorch_ort_parity", validate, lambda: self.command("pytorch_ort_parity", self.smoke_flag([str(PYTHON), str(ML / "parity_harness.py"), "--checkpoint", relative(STAGE_B), "--onnx", relative(ONNX), "--output", relative(PARITY), "--device", self.args.device])), PARITY)

    def ort_browser_parity(self) -> None:
        prompts = ["rain", "дождь", "grass", "трава", "snow", "снег", "hospital", "больница", "glass", "стекло", "red", "red and blue"]

        def validate() -> tuple[bool, dict[str, Any]]:
            report = load_json(PARITY)
            browser = report.get("onnxBrowser", {})
            return browser.get("pass") is True and int(browser.get("rawPromptCount", 0)) >= len(prompts), {"maxAbsDelta": browser.get("maxAbsDelta"), "rawPromptCount": browser.get("rawPromptCount")}

        def action() -> None:
            embedding_input = BROWSER_EMBEDDING_INPUT
            palette_input = BROWSER_PALETTE_INPUT
            atomic_json(embedding_input, {"schemaVersion": 1, "mode": "embeddings", "prompts": prompts})
            atomic_json(palette_input, {"schemaVersion": 1, "mode": "palettebrain", "requests": [{"prompt": prompt, "count": 5, "seed": 42, "lockedColors": []} for prompt in prompts]})
            self.command("ort_browser_embeddings", ["node", str(ML / "browser_runtime_harness.mjs"), "--input", relative(embedding_input), "--output", relative(BROWSER_EMBEDDINGS)])
            self.command("ort_browser_palettes", ["node", str(ML / "browser_runtime_harness.mjs"), "--input", relative(palette_input), "--output", relative(BROWSER_PALETTES)])
            self.command("ort_browser_parity", self.smoke_flag([str(PYTHON), str(ML / "parity_harness.py"), "--checkpoint", relative(STAGE_B), "--onnx", relative(ONNX), "--output", relative(PARITY), "--browser-embeddings", relative(BROWSER_EMBEDDINGS), "--browser-palette-report", relative(BROWSER_PALETTES), "--device", self.args.device]))

        self.phase("ort_browser_parity", validate, action, PARITY)

    def browser_semantic_smoke(self) -> None:
        def validate() -> tuple[bool, dict[str, Any]]:
            report = load_json(BROWSER_SMOKE)
            manifest = load_json(MANIFEST)
            expected_classification = "ENGINEERING_SMOKE_ONLY" if self.args.engineering_smoke else "REAL_BROWSER"
            valid = (
                report.get("pass") is True
                and report.get("testClassification") == expected_classification
                and report.get("fallbackUsed") is False
                and report.get("countPass") is True
                and report.get("seedPass") is True
                and report.get("lockPass") is True
                and report.get("modelVersion") == manifest.get("modelVersion")
                and report.get("decoderSha256") == manifest.get("decoder", {}).get("sha256")
            )
            return valid, {"promptCount": report.get("promptCount"), "modelVersion": report.get("modelVersion"), "fallbackUsed": report.get("fallbackUsed")}

        def action() -> None:
            server: subprocess.Popen[str] | None = None
            server_log = (LOGS / "next-server.log").open("a", encoding="utf-8")
            port = 3101
            app_url = f"http://localhost:{port}"
            environment = os.environ.copy()
            environment.update({
                "NEXT_PUBLIC_PALETTEBRAIN_ALLOW_EXPERIMENTAL": "1",
                "C11_DIAGNOSTIC_BROWSER": "1",
                "C11_APP_URL": app_url,
                "C11_BROWSER_REPORT_PATH": relative(BROWSER_SMOKE),
            })
            if self.args.engineering_smoke:
                environment["C11_ENGINEERING_SMOKE"] = "1"
            try:
                npm = "npm.cmd" if os.name == "nt" else "npm"
                server = subprocess.Popen([npm, "run", "dev", "--", "-p", str(port)], cwd=ROOT, stdout=server_log, stderr=subprocess.STDOUT, text=True, env=environment, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                for _ in range(120):
                    if server.poll() is not None:
                        raise RuntimeError("Next.js server exited; see candidate-11-logs/next-server.log")
                    try:
                        urllib.request.urlopen(f"{app_url}/create", timeout=2).close()
                        break
                    except Exception:
                        time.sleep(1)
                else:
                    raise RuntimeError(f"Next.js server did not become ready on port {port}")
                self.command("browser_semantic_smoke", ["node", str(ROOT / "scripts" / "test-real-browser.mjs")], environment)
            finally:
                if server is not None:
                    server.terminate()
                    try:
                        server.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        server.kill()
                server_log.close()

        self.phase("browser_semantic_smoke", validate, action, BROWSER_SMOKE)

    def canonical_qualification(self) -> None:
        def validate() -> tuple[bool, dict[str, Any]]:
            report = load_json(QUALIFICATION)
            manifest = load_json(MANIFEST)
            valid = (
                report.get("candidate") == "candidate-11"
                and isinstance(report.get("productionReady"), bool)
                and report.get("manifestDecoderSha256") == manifest.get("decoder", {}).get("sha256")
                and STAGE_B.is_file()
                and report.get("checkpointSha256") == sha256_file(STAGE_B)
                and report.get("datasetSha256") == sha256_file(TRAIN_DATA)
            )
            return valid, {"hardFailures": report.get("hardFailures", []), "productionReady": report.get("productionReady", False)}

        def action() -> None:
            self.command("release_semantic_evaluation", self.smoke_flag([str(PYTHON), str(ML / "evaluate_semantic_v3.py"), "--checkpoint", relative(STAGE_B), "--output", relative(RELEASE_EVAL), "--dataset", relative(TRAIN_DATA), "--parity-report", relative(PARITY), "--browser-smoke-report", relative(BROWSER_SMOKE), "--device", self.args.device]))
            self.command("dev_qualification", [str(PYTHON), str(ML / "qualify_candidate.py"), "--evidence", relative(RELEASE_EVAL), "--parity-report", relative(PARITY), "--manifest", relative(MANIFEST), "--output", relative(DEV_QUALIFICATION), "--no-fail-exit"])
            dev_qualification = load_json(DEV_QUALIFICATION)
            if dev_qualification.get("pass") is True:
                self.command("sealed_evaluation", self.smoke_flag([str(PYTHON), str(ML / "evaluate_semantic_v3.py"), "--checkpoint", relative(STAGE_B), "--output", relative(SEALED_EVAL), "--dataset", relative(TRAIN_DATA), "--evaluation-split", "test", "--parity-report", relative(PARITY), "--browser-smoke-report", relative(BROWSER_SMOKE), "--device", self.args.device]))
                self.command("canonical_qualification", [str(PYTHON), str(ML / "qualify_candidate.py"), "--evidence", relative(SEALED_EVAL), "--parity-report", relative(PARITY), "--manifest", relative(MANIFEST), "--output", relative(QUALIFICATION), "--no-fail-exit"])
            else:
                qualification = dict(dev_qualification)
                qualification["sealedConsumed"] = False
                qualification["sealedReport"] = None
                atomic_json(QUALIFICATION, qualification)
            qualification = load_json(QUALIFICATION)
            if qualification.get("pass") is True:
                manifest = load_json(MANIFEST)
                manifest["productionReady"] = True
                manifest["codename"] = "Mikhail Tal"
                atomic_json(MANIFEST, manifest)

        self.phase("canonical_qualification", validate, action, QUALIFICATION)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="auto", help="auto, cpu, cuda, or another PyTorch device")
    parser.add_argument("--resume", action="store_true", help="reuse only artifacts that pass fresh validation")
    parser.add_argument("--engineering-smoke", action="store_true")
    parser.add_argument("--stop-after", choices=["source_data_preflight", "smoke_48_images", "full_visual_source", "repaired_training_dataset", "stage_a", "stage_a_dev_selection", "stage_a_semantic_evaluation", "stage_b", "stage_b_dev_selection", "frozen_pytorch_evaluation", "visual_report", "onnx_export", "pytorch_ort_parity", "ort_browser_parity", "browser_semantic_smoke", "canonical_qualification"])
    return parser.parse_args()


def main() -> None:
    os.chdir(ROOT)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    if args.engineering_smoke:
        configure_engineering_smoke_paths()
    manifest_backup = MANIFEST.read_bytes() if args.engineering_smoke and MANIFEST.is_file() else None
    try:
        Runner(args).run()
    except KeyboardInterrupt:
        print("Interrupted safely. Re-run the same command with --resume.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as error:
        print(f"Candidate 11 stopped honestly: {error}", file=sys.stderr)
        raise SystemExit(1)
    finally:
        if manifest_backup is not None:
            temporary = MANIFEST.with_suffix(MANIFEST.suffix + ".restore")
            temporary.write_bytes(manifest_backup)
            temporary.replace(MANIFEST)


if __name__ == "__main__":
    main()
