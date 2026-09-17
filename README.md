# PGD Teletrabalho — Unifesp

v1 is not a generic enterprise RAG platform. It is a Unifesp assistant for **PGD Teletrabalho**: a technical-administrative Servidor asks about currently effective telework rules and receives a cited answer from a dated snapshot of numbered Normative Acts — or an explicit **Insufficient Evidence** refusal.

This repository still uses a platform-shaped name. The product is this case (see `docs/adr/0001-v1-is-pgd-teletrabalho-assistant.md`). Leave, reimbursement, contracts, FAQ, upload, and live gazette crawl are out of v1.

## Current slice

Walking skeleton (`#2`). `docker compose up` starts FastAPI, a single PT-BR chat route, and Postgres with pgvector. **No Normative Acts are indexed yet.** Every question returns Insufficient Evidence. The Corpus Cutoff is a placeholder (`2025-12-31`) until the snapshot is ingested.

## Run

```bash
docker compose up --build
```

Open [http://localhost:3000](http://localhost:3000). The Ask API is at [http://localhost:8000/ask](http://localhost:8000/ask).

Copy `.env.example` only if you want a local override; Compose already reads `.env` (empty `OPENAI_API_KEY` is expected for this stub).

## Environment

| Variable | Role |
| --- | --- |
| `OPENAI_API_KEY` | Unused by the stub; required later for embeddings and chat |
| `EMBEDDING_MODEL` | Default `text-embedding-3-small` |
| `CHAT_MODEL` | Default `gpt-4o-mini` |
| `CORPUS_CUTOFF` | Snapshot date shown in the UI (`YYYY-MM-DD`) |

Do not commit a real API key.

## Architecture

- **Ask** is the only product seam: question in, cited answer or Insufficient Evidence out.
- **FastAPI** owns Ask. Ingest, retrieval, Current/Historical filters, and the citation gate belong here in later tickets.
- **Next.js** is one Portuguese chat shell — no login, dashboard, or ingest UI.
- **PostgreSQL + pgvector** holds retrieval metadata. The five PDFs will ship in the image (not object storage).
- The same Compose file is the deploy shape (DigitalOcean droplet later). No MinIO, Redis, or extra vector database.

Domain language: `CONTEXT.md`. Binding ADRs: `docs/adr/`.

## Tests

From `api/`:

```bash
python -m pip install -e ".[dev]"
pytest
```

Tests hit Ask (in-process and HTTP). They do not inspect SQL or parser internals.
