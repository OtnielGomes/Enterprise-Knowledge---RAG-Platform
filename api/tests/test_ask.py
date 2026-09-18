from datetime import date

import pytest

from ask.service import Draft, DraftCitation, RetrievedArticle, ask
from ask.snapshot import extractive_draft, load_snapshot

ARTICLE_19 = RetrievedArticle(
    id="unifesp-resolucao-262-2025:19",
    act_id="unifesp-resolucao-262-2025",
    act_label="Resolução CONSU 262/2025",
    article="19",
    page=5,
    text=(
        "Art. 19. O(A) agente público(a) participante do programa de gestão e "
        "seu(ua) chefe imediato(a) deverão assinar um Termo de Ciência e "
        "Responsabilidade (TCR), na forma do ANEXO I desta Resolução, contendo, "
        "no mínimo: V - a declaração de que está ciente que sua participação "
        "no programa de gestão não constitui direito adquirido, podendo ser "
        "desligado(a) nas condições estabelecidas por meio de instrumento "
        "normativo que será publicado pela Pró-reitoria de Gestão com Pessoas."
    ),
    pdf_url="/snapshot/unifesp-resolucao-262-2025.pdf",
)


def test_ask_returns_insufficient_evidence_for_a_teletrabalho_question():
    result = ask(
        "Qual a alíquota do IOF para investimento no exterior?",
        draft=extractive_draft,
    )

    assert result.status == "insufficient_evidence"
    assert result.citations == []
    assert "Evidência insuficiente" in result.message


def test_ask_includes_the_corpus_cutoff():
    result = ask(
        "Qual a alíquota do IOF para investimento no exterior?",
        draft=extractive_draft,
    )

    assert result.corpus_cutoff == date(2026, 9, 18)


def test_ask_rejects_a_blank_question():
    with pytest.raises(ValueError, match="question"):
        ask("   ")


def test_ask_keeps_a_citation_that_matches_a_retrieved_article():
    result = ask(
        "A participação no teletrabalho constitui direito adquirido?",
        retrieve=lambda _question: [ARTICLE_19],
        draft=lambda _question, _articles: Draft(
            message=(
                "A participação no PGD Teletrabalho não constitui direito adquirido."
            ),
            citations=[
                DraftCitation(
                    article_id=ARTICLE_19.id,
                    quote="não constitui direito adquirido",
                )
            ],
        ),
    )

    assert result.status == "answered"
    assert len(result.citations) == 1
    citation = result.citations[0]
    assert citation.act_label == "Resolução CONSU 262/2025"
    assert citation.article == "19"
    assert citation.page == 5
    assert citation.pdf_url.endswith("#page=5")


def test_ask_drops_a_citation_whose_article_is_not_in_the_retrieved_set():
    result = ask(
        "A participação no teletrabalho constitui direito adquirido?",
        retrieve=lambda _question: [ARTICLE_19],
        draft=lambda _question, _articles: Draft(
            message="Citação fabricada ao art. 999.",
            citations=[
                DraftCitation(
                    article_id="unifesp-resolucao-262-2025:999",
                    quote="texto que não existe no artigo recuperado",
                )
            ],
        ),
    )

    assert result.status == "insufficient_evidence"
    assert result.citations == []
    assert "Evidência insuficiente" in result.message


def test_ask_cites_resolucao_262_that_participation_is_not_an_acquired_right():
    snapshot = load_snapshot()
    result = ask(
        "A participação no teletrabalho constitui direito adquirido?",
        retrieve=snapshot.retrieve,
        draft=extractive_draft,
        corpus_cutoff=snapshot.corpus_cutoff,
    )

    assert result.status == "answered"
    matching = [
        citation
        for citation in result.citations
        if citation.act_label == "Resolução CONSU 262/2025"
        and citation.article == "19"
        and citation.page == 5
    ]
    assert matching, result.citations
    assert matching[0].pdf_url.endswith(
        "/snapshot/unifesp-resolucao-262-2025.pdf#page=5"
    )
    act = snapshot.acts[0]
    assert act.status == "current"
    assert act.source_url.startswith("https://site.unifesp.br/")
    assert act.checksum_sha256
    assert act.retrieved_at == date(2026, 9, 18)


def test_ask_refuses_when_the_snapshot_cannot_support_the_question():
    snapshot = load_snapshot()
    result = ask(
        "Qual a alíquota do IOF para investimento no exterior?",
        retrieve=snapshot.retrieve,
        draft=extractive_draft,
    )

    assert result.status == "insufficient_evidence"
    assert result.citations == []


def test_default_ask_cites_resolucao_262_for_an_easy_current_question():
    result = ask(
        "A participação no teletrabalho constitui direito adquirido?",
        draft=extractive_draft,
    )

    assert result.status == "answered"
    assert any(
        citation.act_label == "Resolução CONSU 262/2025"
        and citation.article == "19"
        and citation.page == 5
        for citation in result.citations
    )
