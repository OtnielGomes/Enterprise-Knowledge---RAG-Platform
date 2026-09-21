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
ANNEX_START = re.compile(r"(?m)^\s*ANEXO\b")
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
MIN_STRONG_COVERAGE = 0.4
HISTORICAL_MARKERS = re.compile(
    r"(?i)\b213\b|\b2021\b|antes\s+da\s+(?:resolu[cç][aã]o\s+)?262|"
    r"resolu[cç][aã]o\s+antiga|regra\s+anterior|ato\s+revogado|norma\s+revogada"
)
WEAK_QUERY_TERMS = {
    "pgd",
    "servidor",
    "servidores",
    "teletrabalho",
    "tltra",
    "unifesp",
    "unidade",
}


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
    supersedes: str | None = None
    superseded_by: str | None = None


@dataclass(frozen=True)
class SnapshotIndex:
    corpus_cutoff: date
    acts: tuple[NormativeActRecord, ...]
    articles: tuple[RetrievedArticle, ...]

    def retrieve(self, question: str) -> list[RetrievedArticle]:
        current_articles, superseded_articles = self._articles_by_currency()
        if not is_historical_question(question):
            return rank_articles(question, current_articles)
        superseded_hits = rank_articles(question, superseded_articles)
        if not superseded_hits:
            identities = " ".join(
                act.identity for act in self.acts if _is_superseded(act)
            )
            superseded_hits = rank_articles(identities, superseded_articles)
        current_hits = rank_articles(question, current_articles)
        return _prefer(superseded_hits, current_hits)[:DEFAULT_TOP_K]

    def _articles_by_currency(
        self,
    ) -> tuple[list[RetrievedArticle], list[RetrievedArticle]]:
        current_ids = {act.id for act in self.acts if act.status == "current"}
        current: list[RetrievedArticle] = []
        superseded: list[RetrievedArticle] = []
        for article in self.articles:
            if article.act_id in current_ids:
                current.append(article)
            else:
                superseded.append(article)
        return current, superseded


def is_historical_question(question: str) -> bool:
    return bool(HISTORICAL_MARKERS.search(question))


def _is_superseded(act: NormativeActRecord) -> bool:
    return act.status == "superseded" or bool(act.superseded_by)


def _prefer(
    first: Sequence[RetrievedArticle], second: Sequence[RetrievedArticle]
) -> list[RetrievedArticle]:
    merged: list[RetrievedArticle] = []
    seen: set[str] = set()
    for article in (*first, *second):
        if article.id in seen:
            continue
        seen.add(article.id)
        merged.append(article)
    return merged


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
) -> list[RetrievedArticle]:
    query = set(_tokens(question))
    query_strong = query - WEAK_QUERY_TERMS
    if not query:
        return []
    scored: list[tuple[float, RetrievedArticle]] = []
    for article in articles:
        overlap = query.intersection(_tokens(article.text))
        overlap_strong = overlap - WEAK_QUERY_TERMS
        if not overlap_strong:
            continue
        coverage = (
            len(overlap_strong) / len(query_strong)
            if query_strong
            else len(overlap) / len(query)
        )
        if coverage < MIN_STRONG_COVERAGE and len(overlap_strong) < 2:
            continue
        score = coverage * 10 + len(overlap_strong)
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
        return Draft(
            message=INSUFFICIENT_EVIDENCE_MESSAGE,
            citations=(),
            drafter="extractive",
        )
    citations = tuple(
        DraftCitation(article_id=article.id, quote=_quote_span(article.text))
        for article in articles
    )
    message = (
        "Com base nos artigos recuperados do instantâneo: "
        + " ".join(_quote_span(article.text, 120) for article in articles[:2])
    )
    return Draft(
        message=message,
        citations=citations,
        drafter="extractive",
    )


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
    span_start: str | None = None,
    span_end: str | None = None,
) -> list[RetrievedArticle]:
    full_text = _pdf_text_with_pages(pdf_path)
    start = full_text.find(span_start) if span_start else 0
    if start < 0:
        start = 0
    end = len(full_text)
    if span_end:
        found_end = full_text.find(span_end, start + 1)
        if found_end >= 0:
            end = found_end
    headings = [
        match
        for match in ARTICLE_HEADING.finditer(full_text)
        if start <= match.start() < end
    ]
    annex = ANNEX_START.search(full_text, start, end)
    limit = annex.start() if annex else end
    articles: list[RetrievedArticle] = []
    for index, match in enumerate(headings):
        if match.start() >= limit:
            break
        next_start = headings[index + 1].start() if index + 1 < len(headings) else limit
        article_end = min(next_start, limit)
        body = PAGE_MARK.sub(" ", full_text[match.start() : article_end])
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
            supersedes=raw.get("supersedes"),
            superseded_by=raw.get("superseded_by"),
        )
        acts.append(record)
        articles.extend(
            parse_articles(
                pdf_path,
                act_id=record.id,
                act_label=record.identity,
                pdf_url=f"/snapshot/{record.file}",
                span_start=raw.get("span_start"),
                span_end=raw.get("span_end"),
            )
        )
    return SnapshotIndex(
        corpus_cutoff=cutoff,
        acts=tuple(acts),
        articles=tuple(articles),
    )
