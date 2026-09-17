from dataclasses import dataclass
from datetime import date
from typing import Literal


INSUFFICIENT_EVIDENCE_MESSAGE = (
    "Evidência insuficiente. O instantâneo normativo não permite "
    "sustentar uma resposta com citação verificável."
)

PLACEHOLDER_CORPUS_CUTOFF = date(2025, 12, 31)

AskStatus = Literal["insufficient_evidence"]


@dataclass(frozen=True)
class AskResult:
    status: AskStatus
    message: str
    citations: list[object]
    corpus_cutoff: date


def ask(question: str, *, corpus_cutoff: date | None = None) -> AskResult:
    if not question.strip():
        raise ValueError("question must not be blank")
    cutoff = corpus_cutoff if corpus_cutoff is not None else PLACEHOLDER_CORPUS_CUTOFF
    return AskResult(
        status="insufficient_evidence",
        message=INSUFFICIENT_EVIDENCE_MESSAGE,
        citations=[],
        corpus_cutoff=cutoff,
    )
