import psycopg
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ask.service import ask
from ask.settings import get_settings

settings = get_settings()

app = FastAPI(title="PGD Teletrabalho Ask")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str


@app.post("/ask")
def post_ask(body: AskRequest) -> dict[str, object]:
    try:
        result = ask(body.question, corpus_cutoff=settings.corpus_cutoff)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "status": result.status,
        "message": result.message,
        "citations": result.citations,
        "corpus_cutoff": result.corpus_cutoff.isoformat(),
    }


@app.get("/health")
def health() -> dict[str, str]:
    database = "unconfigured"
    if settings.database_url:
        try:
            with psycopg.connect(settings.database_url, connect_timeout=2) as connection:
                connection.execute("SELECT 1")
            database = "up"
        except Exception:
            database = "down"
    return {
        "status": "ok",
        "corpus_cutoff": settings.corpus_cutoff.isoformat(),
        "database": database,
    }
