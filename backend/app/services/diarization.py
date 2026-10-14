from pathlib import Path

import numpy as np

from app.core.config import settings

ENGINE_MISSING = "Diarization engine not available — install speechbrain and scikit-learn"
MODEL_NAME = "speechbrain/spkrec-ecapa-voxceleb"
DEFAULT_THRESHOLD = 0.5
MIN_CHUNKS = 2


class DiarizationError(Exception):
    pass


_model = None


def _load_model():
    global _model
    if _model is not None:
        return _model
    try:
        from speechbrain.inference.speaker import EncoderClassifier
    except ImportError:
        raise DiarizationError(ENGINE_MISSING)
    try:
        _model = EncoderClassifier.from_hparams(
            source=MODEL_NAME,
            savedir=str(settings.DATA_DIR / "models" / "ecapa"),
        )
    except Exception as exc:
        raise DiarizationError(
            f"Could not download speaker model '{MODEL_NAME}' — check network access"
        ) from exc
    return _model


def _audio_dir(session_id: str) -> Path:
    return settings.DATA_DIR / "audio" / session_id


def _chunk_index(path: Path) -> int:
    return int(path.stem.rsplit("_", 1)[1])


def _chunk_files(session_id: str) -> list[Path]:
    d = _audio_dir(session_id)
    if not d.exists():
        return []
    return sorted(d.glob("chunk_*.webm"), key=_chunk_index)


def _extract_embedding(model, path: Path) -> np.ndarray:
    signal = model.load_audio(str(path))
    if signal.ndim == 1:
        signal = signal.unsqueeze(0)
    embedding = model.encode_batch(signal)
    vector = embedding.squeeze(0).mean(dim=0).detach().cpu().numpy()
    norm = float(np.linalg.norm(vector))
    if norm:
        vector = vector / norm
    return vector


def _cluster(embeddings: list[np.ndarray], expected_speakers: int | None = None) -> list[int]:
    try:
        from sklearn.cluster import AgglomerativeClustering
    except ImportError:
        raise DiarizationError(ENGINE_MISSING)
    n = len(embeddings)
    matrix = np.stack(embeddings)
    if expected_speakers:
        clustering = AgglomerativeClustering(
            n_clusters=min(int(expected_speakers), n),
            metric="cosine",
            linkage="average",
        )
    else:
        clustering = AgglomerativeClustering(
            n_clusters=None,
            metric="cosine",
            linkage="average",
            distance_threshold=DEFAULT_THRESHOLD,
        )
    return [int(label) for label in clustering.fit_predict(matrix)]


def _label_speakers(labels: list[int]) -> list[str]:
    order: dict[int, int] = {}
    counter = 1
    names: list[str] = []
    for label in labels:
        if label not in order:
            order[label] = counter
            counter += 1
        names.append(f"Speaker {order[label]}")
    return names


def diarize(session_id: str, expected_speakers: int | None = None) -> dict[int, str]:
    files = _chunk_files(session_id)
    if len(files) < MIN_CHUNKS:
        raise DiarizationError("Not enough audio to diarize")
    model = _load_model()
    embeddings = [_extract_embedding(model, path) for path in files]
    labels = _cluster(embeddings, expected_speakers)
    names = _label_speakers(labels)
    return {_chunk_index(path): name for path, name in zip(files, names)}
