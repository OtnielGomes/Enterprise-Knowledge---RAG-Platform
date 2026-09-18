from contextlib import asynccontextmanager
import logging
from pathlib import Path

import psycopg
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ask.service import AskResult, Citation, ask
from ask.settings import get_settings
from ask.snapshot import load_snapshot, snapshot_dir
from ask.store import persist_snapshot

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    snapshot = load_snapshot()
    if settings.database_url:
        try:
            persist_snapshot(settings.database_url, snapshot)
        except Exception:
            logger.exception("Could not persist snapshot metadata to Postgres")
    yield


app = FastAPI(title="PGD Teletrabalho Ask", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str


def _citation_payload(citation: Citation) -> dict[str, object]:
    return {
        "act_id": citation.act_id,
        "act_label": citation.act_label,
        "article": citation.article,
        "page": citation.page,
        "pdf_url": citation.pdf_url,
    }


def _ask_payload(result: AskResult) -> dict[str, object]:
    return {
        "status": result.status,
        "message": result.message,
        "citations": [_citation_payload(citation) for citation in result.citations],
        "corpus_cutoff": result.corpus_cutoff.isoformat(),
    }


@app.post("/ask")
def post_ask(body: AskRequest) -> dict[str, object]:
    try:
        result = ask(body.question)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _ask_payload(result)


@app.get("/snapshot/{filename}")
def snapshot_pdf(filename: str) -> FileResponse:
    safe_name = Path(filename).name
    if safe_name != filename or Path(filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=404, detail="Normative Act not found")
    path = snapshot_dir() / safe_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Normative Act not found")
    return FileResponse(path, media_type="application/pdf", filename=safe_name)


@app.get("/health")
def health() -> dict[str, str]:
    database = "unconfigured"
    cutoff = load_snapshot().corpus_cutoff.isoformat()
    if settings.database_url:
        try:
            with psycopg.connect(settings.database_url, connect_timeout=2) as connection:
                connection.execute("SELECT 1")
            database = "up"
        except Exception:
            database = "down"
    return {
        "status": "ok",
        "corpus_cutoff": cutoff,
        "database": database,
    }
