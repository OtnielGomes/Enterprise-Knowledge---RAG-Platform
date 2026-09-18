from collections.abc import Sequence
import json
import logging

from openai import OpenAI

from ask.service import (
    INSUFFICIENT_EVIDENCE_MESSAGE,
    Draft,
    DraftCitation,
    Drafter,
    RetrievedArticle,
)
from ask.settings import get_settings
from ask.snapshot import extractive_draft

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Unifesp PGD Teletrabalho assistant.
Answer only from the retrieved Articles of the dated snapshot.
Write the Servidor-facing message in Brazilian Portuguese.
Return JSON with keys message (string) and citations (array of objects with article_id and quote).
Each article_id MUST be one of the retrieved ids. Each quote MUST be a span copied from that Article.
If the Articles do not contain a rule that answers the question, return citations as [] and a short refusal.
Do not invent leave duration, furniture reimbursement, tax, or other HR rules that are not in the Articles.
Do not merge IN 24/2023 and IN 21/2024 into one consolidated Current text; they are distinct Current acts (21 is an Amendment of 24).
If Unifesp and federal Articles, or IN 24 and IN 21, both speak and a single synthesis would hide a conflict, do not pick a winner. Return citations for both sides and an empty or refusal message so the citation gate can keep the Citations.
Do not use an LLM-as-judge voice. Do not cite ghost Articles.
"""


def _format_articles(articles: Sequence[RetrievedArticle]) -> str:
    blocks = []
    for article in articles:
        blocks.append(
            f"id={article.id}\n"
            f"act={article.act_label}\n"
            f"article={article.article}\n"
            f"page={article.page}\n"
            f"text={article.text}"
        )
    return "\n\n".join(blocks)


def openai_draft(
    question: str,
    articles: Sequence[RetrievedArticle],
    *,
    client: OpenAI,
    model: str,
) -> Draft:
    if not articles:
        return Draft(message=INSUFFICIENT_EVIDENCE_MESSAGE, citations=())
    completion = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Question:\n{question}\n\nRetrieved Articles:\n"
                    f"{_format_articles(articles)}"
                ),
            },
        ],
    )
    content = completion.choices[0].message.content or "{}"
    payload = json.loads(content)
    citations = tuple(
        DraftCitation(
            article_id=item.get("article_id"),
            quote=item.get("quote"),
        )
        for item in payload.get("citations", [])
        if isinstance(item, dict)
    )
    return Draft(
        message=str(payload.get("message") or INSUFFICIENT_EVIDENCE_MESSAGE),
        citations=citations,
    )


def default_drafter() -> Drafter:
    settings = get_settings()
    if not settings.openai_api_key:
        return extractive_draft
    client = OpenAI(api_key=settings.openai_api_key)

    def draft(question: str, articles: Sequence[RetrievedArticle]) -> Draft:
        try:
            return openai_draft(
                question,
                articles,
                client=client,
                model=settings.chat_model,
            )
        except Exception:
            logger.exception("OpenAI draft failed; falling back to extractive draft")
            return extractive_draft(question, articles)

    return draft
