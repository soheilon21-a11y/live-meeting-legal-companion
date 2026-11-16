import chromadb
from chromadb.errors import NotFoundError

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


def delete(document_id: str) -> bool:
    """Delete a session's vector collection; returns True if it existed.

    A missing collection is treated as already-deleted (idempotent). Genuine
    storage/database errors propagate so callers never report successful
    deletion when the collection still exists.
    """
    name = collection_name(document_id)
    try:
        client().delete_collection(name)
    except NotFoundError:
        return False
    except ValueError as exc:
        # ChromaDB 0.5.x raises a bare ValueError (instead of NotFoundError)
        # when the collection is absent. Only treat the exact missing-collection
        # message for *this* collection as idempotent; re-raise everything else.
        if str(exc) != f"Collection {name} does not exist.":
            raise
        return False
    return True
