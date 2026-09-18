# PGD Teletrabalho — Unifesp

v1 is not a generic enterprise RAG platform. It is a Unifesp assistant for **PGD Teletrabalho**: a technical-administrative Servidor asks about currently effective telework rules and receives a cited answer from a dated snapshot of numbered Normative Acts — or an explicit **Insufficient Evidence** refusal.

This repository still uses a platform-shaped name. The product is this case (see `docs/adr/0001-v1-is-pgd-teletrabalho-assistant.md`). Leave, reimbursement, contracts, FAQ, upload, and live gazette crawl are out of v1.

## Current slice

Ask on the Current snapshot: Unifesp Resolução CONSU 262/2025, Decreto 11.072/2022, IN conjunta 24/2023, and IN conjunta 21/2024 (`#4`). The acts are snapshotted in `snapshot/`. `docker compose up` starts FastAPI, a single PT-BR chat route, and Postgres with pgvector. An easy Current Teletrabalho question returns a Citation (act, Article, page). When Unifesp and federal acts both speak, both Citations can appear. IN 21 is an Amendment of IN 24, not a replacement; Ask does not merge them into a consolidated text and refuses to synthesize if that would hide a conflict, while still returning the Citations. Clicking a Citation opens the PDF at that page. Fabricated Citations are dropped; if none remain, Ask returns Insufficient Evidence.

Superseded Resolução 213/2021 is a later ticket.

## Run

```bash
docker compose up --build
```

Open [http://localhost:3000](http://localhost:3000). The Ask API is at [http://localhost:8000/ask](http://localhost:8000/ask).

Copy `.env.example` to `.env` and set `OPENAI_API_KEY` for model-written answers. With an empty key, Ask still indexes the Current snapshot and uses an extractive draft over retrieved Articles.

## Environment

| Variable | Role |
| --- | --- |
| `OPENAI_API_KEY` | Chat (and later embeddings). Empty key → extractive draft |
| `EMBEDDING_MODEL` | Default `text-embedding-3-small` |
| `CHAT_MODEL` | Default `gpt-4o-mini` |
| `CORPUS_CUTOFF` | Fallback snapshot date (`YYYY-MM-DD`); the UI uses `snapshot/manifest.json` |

Do not commit a real API key.

## Architecture

- **Ask** is the only product seam: question in, cited answer or Insufficient Evidence out.
- **FastAPI** owns Ask, snapshot ingest, retrieval, and the deterministic citation gate. No LLM-as-judge on the request path.
- **Next.js** is one Portuguese chat shell — no login, dashboard, or ingest UI.
- **PostgreSQL + pgvector** holds retrieval metadata. PDFs ship in the API image from `snapshot/`.
- The same Compose file is the deploy shape (DigitalOcean droplet later). No MinIO, Redis, or extra vector database.

Domain language: `CONTEXT.md`. Binding ADRs: `docs/adr/`.

## Tests

From `api/`:

```bash
python -m pip install -e ".[dev]"
pytest
```

Tests hit Ask (in-process and HTTP). They do not inspect SQL or parser internals.
