from app.core.config import settings

MODEL_MISSING = (
    "Embedding model is not provisioned locally. Run scripts/download_models.py "
    "once (with internet) to cache it, then retry. Niyosh never downloads "
    "models automatically."
)

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        model_dir = settings.EMBEDDING_MODEL_DIR
        if not model_dir.is_dir() or not (
            (model_dir / "model.safetensors").exists()
            or (model_dir / "pytorch_model.bin").exists()
        ):
            raise RuntimeError(MODEL_MISSING)
        # Load from the provisioned local directory with local_files_only=True so
        # uploading a document can never silently initiate a model download.
        _model = SentenceTransformer(str(model_dir), local_files_only=True)
    return _model


def embed(texts: list[str]) -> list[list[float]]:
    model = _get_model()
    return model.encode(texts, normalize_embeddings=True).tolist()
