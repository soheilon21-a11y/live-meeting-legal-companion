from io import BytesIO
from pathlib import Path

from app.services import embedding
from app.services.chroma_store import get_or_create

CHUNK_SIZE = 600
CHUNK_OVERLAP = 120


def extract_text(filename: str, content: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        import pymupdf as fitz

        doc = fitz.open(stream=content, filetype="pdf")
        return "\n".join(page.get_text() for page in doc)
    if ext == ".docx":
        import docx

        document = docx.Document(BytesIO(content))
        return "\n".join(p.text for p in document.paragraphs if p.text.strip())
    if ext == ".txt":
        return content.decode("utf-8", errors="replace")
    raise ValueError(f"Unsupported file type: {ext}")


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = text.strip()
    if not text:
        return []
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + size, n)
        chunks.append(text[start:end])
        if end >= n:
            break
        start = end - overlap
    return chunks


def ingest(document_id: str, filename: str, content: bytes) -> int:
    text = extract_text(filename, content)
    chunks = chunk_text(text)
    if not chunks:
        raise ValueError("No text extracted from document")
    collection = get_or_create(document_id)
    embeddings = embedding.embed(chunks)
    ids = [f"{document_id}:{i}" for i in range(len(chunks))]
    metadatas = [{"position": f"passage {i + 1} of {len(chunks)}"} for i in range(len(chunks))]
    collection.add(ids=ids, documents=chunks, embeddings=embeddings, metadatas=metadatas)
    return len(chunks)
