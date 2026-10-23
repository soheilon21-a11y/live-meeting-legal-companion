# Scripts

## Launcher (recommended)

`scripts/start-windows.ps1` is the recommended way to run Niyosh on Windows. It verifies Python, reuses (or creates) the virtual environment, installs `backend/requirements.txt` only when packages are missing, starts the backend on `127.0.0.1:8002`, then opens the Live Analysis control panel. Run it from a PowerShell prompt:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-windows.ps1
```

It works fully offline once the virtual environment exists — it only reaches the network to install missing packages.

## Model download script

`scripts/download_models.py` downloads and caches every AI model Niyosh needs, so the product runs **fully offline** afterwards. Run it once while you have internet (e.g. from Tehran on a good connection); after that, no model will ever be fetched again.

## What each model is for

| Model | Purpose | How it's downloaded |
|---|---|---|
| `faster-whisper-small` (CTranslate2) | **Transcription** — converts meeting audio into text. | `huggingface_hub.snapshot_download` |
| `silero-vad` | **Voice activity detection** — detects when speech starts/stops in the audio stream. | `torch.hub.load("snakers4/silero-vad")` |
| `piper` voices (`en_US-lessac-medium`, `de_DE-thorsten-medium`) | **Text-to-speech** — synthesizes spoken audio in English and German. | `piper-tts` package (if installed) |

## How to run

```bash
python scripts/download_models.py
```

The script is **idempotent**: re-running it is safe — already-cached models are skipped, and any failed download is retried without re-downloading the rest.

It writes everything under `./models/`:

- `./models/faster-whisper-small/` — Whisper "small" model
- `./models/torch_hub/hub/checkpoints/` — Silero VAD
- `./models/piper/` — Piper TTS voices (only if `piper-tts` is installed; otherwise it prints manual instructions)

## Verify models are cached

```bash
# Whisper: look for model.bin / config.json / tokenizer files
ls models/faster-whisper-small

# Silero VAD: look for silero_vad.jit
ls models/torch_hub/hub/checkpoints

# Piper: look for *.onnx and *.onnx.json pairs
ls models/piper
```

## Offline use

Once everything is cached, set this environment variable to force offline-only operation:

```bash
# Windows (PowerShell)
$env:HF_HUB_OFFLINE = "1"

# Linux / macOS
export HF_HUB_OFFLINE=1
```

With `HF_HUB_OFFLINE=1`, `huggingface_hub` and `faster-whisper` will never touch the network and will load models from the local cache.

## Notes

- `piper-tts` is optional. If it isn't installed, the script skips TTS and prints the commands to install it and fetch the voices (`en_US-lessac-medium`, `de_DE-thorsten-medium`) from `rhasspy/piper-voices`.
- Add `models/` to your `.gitignore` so large model files are not committed.
