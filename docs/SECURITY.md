# Security & Privacy

## What runs locally

All processing happens on the host machine:

- The FastAPI app runs in a container (port 8002, bound to localhost).
- Ollama runs locally and serves Llama 3.
- ChromaDB stores embeddings and source passages locally.

## What never leaves the machine

No external requests are made at runtime. No telemetry, no analytics, no cloud services.

## Data storage

- Chroma data: `chroma_data/` (named Docker volume).
- Uploaded contracts: `uploads/` (reserved for a later phase).
- No cookies, no trackers, no browser storage.

## How to delete data

```bash
docker compose down -v
```

`-v` removes the named volumes, including `chroma_data`.

## Threat model

Minimal: single-user, local, no network surface.

- The API publishes port 8002 bound to `127.0.0.1` (localhost only).
- There is no multi-tenancy and no remote client trust boundary.
- The main risk is local: someone with filesystem access already has the machine.
- The website is fully static, serves no client-side JavaScript, and enforces a strict Content-Security-Policy.
