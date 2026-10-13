import chromadb

from app.core.config import settings


def client() -> chromadb.PersistentClient:
    return chromadb.PersistentClient(path=str(settings.DATA_DIR / "chroma"))


def collection_name(document_id: str) -> str:
    return f"chroma_{document_id}"


def get_or_create(document_id: str):
    return client().get_or_create_collection(
        collection_name(document_id), metadata={"hnsw:space": "cosine"}
    )


def get(document_id: str):
    return client().get_collection(collection_name(document_id))


def delete(document_id: str) -> None:
    client().delete_collection(collection_name(document_id))
