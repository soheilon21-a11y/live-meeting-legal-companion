"""One-time download script for Niyosh — caches all AI models locally.

Run once (with internet) so the product works fully offline afterwards.
Safe to re-run: already-cached models are skipped.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "0"

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
MODELS_DIR = ROOT_DIR / "models"

WHISPER_REPO = "Systran/faster-whisper-small"
PIPER_VOICES = {
    "English": "en_US-lessac-medium",
    "German": "de_DE-thorsten-medium",
}

results = {}


def section(title: str) -> None:
    print("\n" + "=" * 64)
    print(title)
    print("=" * 64)


def ok(name: str) -> None:
    results[name] = True
    print(f"  [OK]   {name}")


def fail(name: str, err: object) -> None:
    results[name] = False
    print(f"  [FAIL] {name}: {err}")


def human_size(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024:
            return f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} PB"


def dir_size(path: Path) -> int:
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            total += p.stat().st_size
    return total


def download_whisper() -> None:
    section("1/3  faster-whisper 'small' model (transcription)")
    target = MODELS_DIR / "faster-whisper-small"
    target.mkdir(parents=True, exist_ok=True)
    try:
        from huggingface_hub import snapshot_download

        print(f"  Repo:   {WHISPER_REPO}")
        print(f"  Target: {target}")
        path = snapshot_download(repo_id=WHISPER_REPO, local_dir=str(target))
        print(f"  Cached: {path}")
        ok(f"faster-whisper-small  ->  {path}")
    except Exception as exc:
        fail("faster-whisper-small", exc)


def download_silero() -> None:
    section("2/3  Silero VAD (voice activity detection)")
    try:
        import torch

        hub_dir = MODELS_DIR / "torch_hub"
        hub_dir.mkdir(parents=True, exist_ok=True)
        os.environ["TORCH_HOME"] = str(hub_dir)

        print("  Source: snakers4/silero-vad (torch.hub)")
        model = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            trust_repo=True,
        )
        if isinstance(model, tuple):
            model = model[0]
        print(f"  Loaded: {type(model).__name__}")
        print(f"  Cache:  {hub_dir / 'hub' / 'checkpoints'}")
        ok("silero-vad  ->  " + str(hub_dir / "hub" / "checkpoints"))
    except Exception as exc:
        fail("silero-vad", exc)


def download_piper() -> None:
    section("3/3  Piper TTS voices (text-to-speech)")
    piper_dir = MODELS_DIR / "piper"
    try:
        import piper  # noqa: F401
    except ImportError:
        print("  piper-tts is NOT installed - skipping automatic TTS voice download.")
        print("  To cache the voices manually:")
        print("    1) pip install piper-tts")
        print("    2) python -m piper.download_voices en_US-lessac-medium de_DE-thorsten-medium")
        print("       (or grab the .onnx + .onnx.json pairs from rhasspy/piper-voices)")
        fail("piper TTS voices (en_US-lessac-medium, de_DE-thorsten-medium)",
             "piper-tts not installed")
        return

    try:
        piper_dir.mkdir(parents=True, exist_ok=True)
        voices = list(PIPER_VOICES.values())
        print("  Voices:", ", ".join(voices))
        subprocess.run(
            [sys.executable, "-m", "piper.download_voices", *voices],
            check=True,
        )
        ok("piper TTS voices  ->  " + str(piper_dir))
    except Exception as exc:
        fail("piper TTS voices", exc)


def summarize() -> None:
    section("Summary")
    print(f"Cache root: {MODELS_DIR}")
    print()
    print("Downloaded models:")
    entries = sorted(MODELS_DIR.iterdir()) if MODELS_DIR.exists() else []
    total = 0
    for child in entries:
        if child.is_dir():
            size = dir_size(child)
            total += size
            print(f"  - {child.name}  ({human_size(size)})")
    print()
    print(f"Total disk size: {human_size(total)}")
    print()
    print("Checklist:")
    for name, status in results.items():
        print(f"  [{'OK  ' if status else 'FAIL'}] {name}")

    failures = [n for n, s in results.items() if not s]
    print()
    if failures:
        print("Some models were NOT downloaded. Re-run once you have a stable")
        print("connection - already-cached models will be skipped.")
    else:
        print("All models cached successfully.")


def main() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    download_whisper()
    download_silero()
    download_piper()
    summarize()


if __name__ == "__main__":
    main()
