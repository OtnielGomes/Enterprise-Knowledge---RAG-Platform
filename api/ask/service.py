from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Literal


INSUFFICIENT_EVIDENCE_MESSAGE = (
    "Evidência insuficiente. O instantâneo normativo não permite "
    "sustentar uma resposta com citação verificável."
)

PLACEHOLDER_CORPUS_CUTOFF = date(2025, 12, 31)

AskStatus = Literal["answered", "insufficient_evidence"]


@dataclass(frozen=True)
class RetrievedArticle:
    id: str
    act_id: str
    act_label: str
    article: str
    page: int
    text: str
    pdf_url: str


@dataclass(frozen=True)
class DraftCitation:
    article_id: str | None = None
    quote: str | None = None


@dataclass(frozen=True)
class Draft:
    message: str
    citations: Sequence[DraftCitation] = field(default_factory=tuple)


@dataclass(frozen=True)
class Citation:
    act_id: str
    act_label: str
    article: str
    page: int
    pdf_url: str


@dataclass(frozen=True)
class AskResult:
    status: AskStatus
    message: str
    citations: list[Citation]
    corpus_cutoff: date


Retriever = Callable[[str], Sequence[RetrievedArticle]]
Drafter = Callable[[str, Sequence[RetrievedArticle]], Draft]


def _default_retrieve(question: str) -> list[RetrievedArticle]:
    from ask.snapshot import load_snapshot

    return list(load_snapshot().retrieve(question))


def _default_cutoff() -> date:
    from ask.snapshot import load_snapshot

    try:
        return load_snapshot().corpus_cutoff
    except FileNotFoundError:
        return PLACEHOLDER_CORPUS_CUTOFF


def _default_draft(
    question: str, articles: Sequence[RetrievedArticle]
) -> Draft:
    from ask.generate import default_drafter

    return default_drafter()(question, articles)


def _citation_from_article(article: RetrievedArticle) -> Citation:
    pdf_url = article.pdf_url
    if "#page=" not in pdf_url:
        pdf_url = f"{pdf_url}#page={article.page}"
    return Citation(
        act_id=article.act_id,
        act_label=article.act_label,
        article=article.article,
        page=article.page,
        pdf_url=pdf_url,
    )


def _quote_in_article(quote: str, article: RetrievedArticle) -> bool:
    needle = " ".join(quote.lower().split())
    haystack = " ".join(article.text.lower().split())
    return bool(needle) and needle in haystack


def apply_citation_gate(
    draft: Draft, retrieved: Sequence[RetrievedArticle]
) -> list[Citation]:
    by_id = {article.id: article for article in retrieved}
    kept: list[Citation] = []
    seen: set[str] = set()
    for proposed in draft.citations:
        article = by_id.get(proposed.article_id or "")
        if article is None and proposed.quote:
            article = next(
                (
                    candidate
                    for candidate in retrieved
                    if _quote_in_article(proposed.quote, candidate)
                ),
                None,
            )
        if article is None:
            continue
        if article.id in seen:
            continue
        seen.add(article.id)
        kept.append(_citation_from_article(article))
    return kept


def ask(
    question: str,
    *,
    corpus_cutoff: date | None = None,
    retrieve: Retriever | None = None,
    draft: Drafter | None = None,
) -> AskResult:
    if not question.strip():
        raise ValueError("question must not be blank")
    cutoff = corpus_cutoff if corpus_cutoff is not None else _default_cutoff()
    retrieved = list((retrieve or _default_retrieve)(question))
    produced = (draft or _default_draft)(question, retrieved)
    citations = apply_citation_gate(produced, retrieved)
    if not citations:
        return AskResult(
            status="insufficient_evidence",
            message=INSUFFICIENT_EVIDENCE_MESSAGE,
            citations=[],
            corpus_cutoff=cutoff,
        )
    return AskResult(
        status="answered",
        message=produced.message,
        citations=citations,
        corpus_cutoff=cutoff,
    )
