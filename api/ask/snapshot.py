from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from collections.abc import Sequence

import pymupdf

from ask.service import (
    INSUFFICIENT_EVIDENCE_MESSAGE,
    Draft,
    DraftCitation,
    RetrievedArticle,
)

ARTICLE_HEADING = re.compile(r"(?m)^\s*Art\.?\s*(\d+)\s*[oº°ª]?", re.UNICODE)
PAGE_MARK = re.compile(r"\[\[PAGE (\d+)\]\]")
TOKEN = re.compile(r"\w+", re.UNICODE)
STOPWORDS = {
    "a",
    "ao",
    "aos",
    "as",
    "com",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "é",
    "na",
    "nas",
    "no",
    "nos",
    "o",
    "os",
    "ou",
    "para",
    "pela",
    "pelas",
    "pelo",
    "pelos",
    "por",
    "qual",
    "que",
    "se",
    "um",
    "uma",
}

DEFAULT_TOP_K = 6
MIN_RETRIEVE_SCORE = 1.5


def snapshot_dir() -> Path:
    configured = os.environ.get("SNAPSHOT_DIR")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "snapshot"


@dataclass(frozen=True)
class NormativeActRecord:
    id: str
    identity: str
    type: str
    number: str
    year: int
    status: str
    source_url: str
    retrieved_at: date
    checksum_sha256: str
    file: str


@dataclass(frozen=True)
class SnapshotIndex:
    corpus_cutoff: date
    acts: tuple[NormativeActRecord, ...]
    articles: tuple[RetrievedArticle, ...]

    def retrieve(self, question: str) -> list[RetrievedArticle]:
        return rank_articles(question, self.articles)


def _tokens(text: str) -> list[str]:
    return [
        token.lower()
        for token in TOKEN.findall(text)
        if token.lower() not in STOPWORDS and len(token) > 2
    ]


def rank_articles(
    question: str,
    articles: Sequence[RetrievedArticle],
    *,
    top_k: int = DEFAULT_TOP_K,
    min_score: float = MIN_RETRIEVE_SCORE,
) -> list[RetrievedArticle]:
    query = set(_tokens(question))
    if not query:
        return []
    scored: list[tuple[float, RetrievedArticle]] = []
    for article in articles:
        overlap = query.intersection(_tokens(article.text))
        if not overlap:
            continue
        length = max(len(_tokens(article.text)), 1)
        score = len(overlap) + (len(overlap) / (length ** 0.5))
        if score >= min_score:
            scored.append((score, article))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [article for _score, article in scored[:top_k]]


def _quote_span(text: str, limit: int = 180) -> str:
    collapsed = " ".join(text.split())
    return collapsed[:limit]


def extractive_draft(
    question: str, articles: Sequence[RetrievedArticle]
) -> Draft:
    del question
    if not articles:
        return Draft(message=INSUFFICIENT_EVIDENCE_MESSAGE, citations=())
    citations = tuple(
        DraftCitation(article_id=article.id, quote=_quote_span(article.text))
        for article in articles
    )
    message = (
        "Com base nos artigos recuperados do instantâneo: "
        + " ".join(_quote_span(article.text, 120) for article in articles[:2])
    )
    return Draft(message=message, citations=citations)


def _pdf_text_with_pages(pdf_path: Path) -> str:
    document = pymupdf.open(pdf_path)
    parts: list[str] = []
    for number, page in enumerate(document, start=1):
        parts.append(f"\n[[PAGE {number}]]\n{page.get_text()}")
    return "".join(parts).replace("\xa0", " ")


def _page_at(text: str, offset: int) -> int:
    page = 1
    for match in PAGE_MARK.finditer(text):
        if match.start() > offset:
            break
        page = int(match.group(1))
    return page


def parse_articles(
    pdf_path: Path,
    *,
    act_id: str,
    act_label: str,
    pdf_url: str,
) -> list[RetrievedArticle]:
    full_text = _pdf_text_with_pages(pdf_path)
    headings = list(ARTICLE_HEADING.finditer(full_text))
    articles: list[RetrievedArticle] = []
    for index, match in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(full_text)
        body = PAGE_MARK.sub(" ", full_text[match.start() : end])
        body = " ".join(body.split())
        number = match.group(1)
        articles.append(
            RetrievedArticle(
                id=f"{act_id}:{number}",
                act_id=act_id,
                act_label=act_label,
                article=number,
                page=_page_at(full_text, match.start()),
                text=body,
                pdf_url=pdf_url,
            )
        )
    return articles


def _load_manifest(directory: Path) -> tuple[date, list[dict]]:
    payload = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    cutoff = date.fromisoformat(payload["corpus_cutoff"])
    return cutoff, list(payload["acts"])


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


@lru_cache(maxsize=1)
def load_snapshot(directory: str | None = None) -> SnapshotIndex:
    root = Path(directory) if directory else snapshot_dir()
    cutoff, raw_acts = _load_manifest(root)
    acts: list[NormativeActRecord] = []
    articles: list[RetrievedArticle] = []
    for raw in raw_acts:
        pdf_path = root / raw["file"]
        checksum = _sha256(pdf_path)
        if checksum != raw["checksum_sha256"]:
            raise ValueError(
                f"checksum mismatch for {raw['file']}: expected "
                f"{raw['checksum_sha256']}, got {checksum}"
            )
        record = NormativeActRecord(
            id=raw["id"],
            identity=raw["identity"],
            type=raw["type"],
            number=raw["number"],
            year=int(raw["year"]),
            status=raw["status"],
            source_url=raw["source_url"],
            retrieved_at=date.fromisoformat(raw["retrieved_at"]),
            checksum_sha256=checksum,
            file=raw["file"],
        )
        acts.append(record)
        if record.status != "current":
            continue
        articles.extend(
            parse_articles(
                pdf_path,
                act_id=record.id,
                act_label=record.identity,
                pdf_url=f"/snapshot/{record.file}",
            )
        )
    return SnapshotIndex(
        corpus_cutoff=cutoff,
        acts=tuple(acts),
        articles=tuple(articles),
    )
