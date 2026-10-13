from chromadb.errors import NotFoundError

from app.core.config import settings
from app.services import embedding
from app.services.chroma_store import get


def retrieve(document_id: str, query: str, k: int = settings.TOP_K) -> list[dict]:
    try:
        collection = get(document_id)
    except NotFoundError:
        return []
    count = collection.count()
    if count == 0:
        return []
    query_embedding = embedding.embed([query])
    result = collection.query(
        query_embeddings=query_embedding,
        n_results=min(k, count),
        include=["documents", "metadatas"],
    )
    documents = result["documents"][0]
    metadatas = result["metadatas"][0]
    passages = []
    for text, meta in zip(documents, metadatas):
        passages.append({"text": text, "position": meta.get("position", "")})
    return passages
