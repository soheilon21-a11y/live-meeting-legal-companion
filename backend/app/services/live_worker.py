import logging
import queue
import threading
import time
from datetime import datetime, timezone

from app.core.config import settings
from app.services import session_store, transcription

log = logging.getLogger(__name__)

# ASR and the LLM must never run concurrently (8 GB RAM constraint). Both
# acquire this lock before using the CPU-bound model.
model_lock = threading.Lock()

_chunk_queue = queue.Queue(maxsize=settings.LIVE_MAX_QUEUE)

_state_lock = threading.Lock()
_state: dict[str, dict] = {}


def _state_for(session_id: str) -> dict:
    with _state_lock:
        if session_id not in _state:
            _state[session_id] = {
                "recording": False,
                "processed": 0,
                "backlog": [],
            }
        return _state[session_id]


def enqueue_chunk(session_id: str, chunk_index: int, audio_bytes: bytes) -> str:
    item = (session_id, chunk_index, audio_bytes)
    try:
        _chunk_queue.put_nowait(item)
    except queue.Full:
        # The raw chunk is already on disk; remember its index for later.
        _state_for(session_id)["backlog"].append(chunk_index)
        return "backlogged"
    return "queued"


def mark_recording(session_id: str, recording: bool) -> None:
    _state_for(session_id)["recording"] = recording


def status(session_id: str) -> dict:
    st = _state_for(session_id)
    return {
        "recording": st["recording"],
        "queue_depth": _chunk_queue.qsize(),
        "processed": st["processed"],
        "backlog": len(st["backlog"]),
    }


_inflight_cond = threading.Condition()
_inflight: dict[str, int] = {}


def process_chunk(session_id: str, chunk_index: int, audio_bytes: bytes) -> None:
    with _inflight_cond:
        _inflight[session_id] = _inflight.get(session_id, 0) + 1
    try:
        try:
            with model_lock:
                result = transcription.transcribe_audio(
                    audio_bytes,
                    language=settings.LIVE_WHISPER_LANGUAGE,
                    initial_prompt=settings.LIVE_WHISPER_INITIAL_PROMPT,
                    condition_on_previous_text=False,
                    no_speech_threshold=0.6,
                )
            text = result.get("text", "")
            language = result.get("language")
        except Exception:
            log.exception(
                "live transcription failed session=%s chunk=%s size=%dB",
                session_id,
                chunk_index,
                len(audio_bytes),
            )
            text = "[transcription failed — audio preserved]"
            language = None
        session_store.append_transcript(
            session_id,
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "mode": "live",
                "chunk_index": chunk_index,
                "text": text,
                "language": language,
            },
        )
        _state_for(session_id)["processed"] += 1
    finally:
        with _inflight_cond:
            if _inflight[session_id] > 1:
                _inflight[session_id] -= 1
            else:
                del _inflight[session_id]
            _inflight_cond.notify_all()


def _drain_queue(session_id: str, limit: int) -> int:
    processed = 0
    others: list = []
    while processed < limit:
        try:
            item = _chunk_queue.get_nowait()
        except queue.Empty:
            break
        if item[0] == session_id:
            process_chunk(*item)
            processed += 1
        else:
            others.append(item)
    for other in others:
        try:
            _chunk_queue.put_nowait(other)
        except queue.Full:
            break
    return processed


def _process_backlog(session_id: str, limit: int) -> int:
    st = _state_for(session_id)
    audio_dir = settings.DATA_DIR / "audio" / session_id
    processed = 0
    remaining: list = []
    for chunk_index in st["backlog"]:
        if processed >= limit:
            remaining.append(chunk_index)
            continue
        path = audio_dir / f"chunk_{chunk_index}.webm"
        if not path.exists():
            continue
        process_chunk(session_id, chunk_index, path.read_bytes())
        processed += 1
    st["backlog"] = remaining
    return processed


def flush(session_id: str, limit: int = 100) -> int:
    total = _drain_queue(session_id, limit)
    total += _process_backlog(session_id, limit - total)
    _wait_inflight(session_id)
    return total


def _wait_inflight(session_id: str, timeout: float = 60.0) -> None:
    with _inflight_cond:
        deadline = time.monotonic() + timeout
        while _inflight.get(session_id, 0) > 0:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                log.warning(
                    "live flush timed out waiting for in-flight transcription session=%s",
                    session_id,
                )
                return
            _inflight_cond.wait(timeout=remaining)


def _worker_loop() -> None:
    while True:
        try:
            item = _chunk_queue.get(timeout=1)
        except queue.Empty:
            continue
        try:
            process_chunk(*item)
        except Exception:
            log.exception(
                "live transcription failed session=%s chunk=%s size=%dB",
                item[0],
                item[1],
                len(item[2]),
            )
        _chunk_queue.task_done()


_worker = threading.Thread(target=_worker_loop, daemon=True, name="live-worker")
_worker.start()
