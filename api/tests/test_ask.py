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
    assert result.corpus_cutoff == date(2026, 9, 18)


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


def test_ask_refuses_a_leave_duration_question_the_act_does_not_answer():
    result = ask(
        "Quantos dias de férias o servidor em teletrabalho pode tirar?",
        draft=extractive_draft,
    )

    assert result.status == "insufficient_evidence"
    assert result.citations == []


def test_ask_cites_decreto_11072_that_pgd_is_not_a_right_of_the_servidor():
    result = ask(
        "A instituição e a manutenção do PGD constituem direito do agente público?",
        draft=extractive_draft,
    )

    assert result.status == "answered"
    matching = [
        citation
        for citation in result.citations
        if citation.act_label == "Decreto 11.072/2022"
        and citation.article == "5"
        and citation.page == 1
    ]
    assert matching, result.citations
    assert matching[0].pdf_url.endswith("/snapshot/decreto-11072-2022.pdf#page=1")


def test_ask_cites_in_24_for_partial_versus_integral_teletrabalho():
    result = ask(
        "Na modalidade de teletrabalho, o que distingue o regime de execução parcial do integral?",
        draft=extractive_draft,
    )

    matching = [
        citation
        for citation in result.citations
        if citation.act_label == "IN conjunta 24/2023"
        and citation.article == "10"
        and citation.page == 3
    ]
    assert matching, result.citations
    assert matching[0].pdf_url.endswith("/snapshot/in-conjunta-24-2023.pdf#page=3")
    if any(citation.act_label == "IN conjunta 21/2024" for citation in result.citations):
        assert result.status == "insufficient_evidence"
        assert "IN 24 vigente" not in result.message
    else:
        assert result.status == "answered"


def test_ask_cites_in_21_that_it_revokes_in_24_priority_items():
    result = ask(
        "A IN 21 revogou os incisos I e II do art. 14 da IN 24?",
        draft=extractive_draft,
    )

    matching = [
        citation
        for citation in result.citations
        if citation.act_label == "IN conjunta 21/2024"
        and citation.article == "2"
        and citation.page == 3
    ]
    assert matching, result.citations
    assert matching[0].pdf_url.endswith("/snapshot/in-conjunta-21-2024.pdf#page=3")


def test_ask_cites_both_unifesp_and_federal_acts_on_a_shared_current_question():
    result = ask(
        "A participação no teletrabalho constitui direito adquirido?",
        draft=extractive_draft,
    )

    assert result.status == "answered"
    act_labels = {citation.act_label for citation in result.citations}
    assert "Resolução CONSU 262/2025" in act_labels, result.citations
    assert act_labels & {"IN conjunta 24/2023", "Decreto 11.072/2022"}, result.citations
    assert any(
        citation.act_label == "Resolução CONSU 262/2025" and citation.article == "19"
        for citation in result.citations
    )


def test_ask_refuses_to_synthesize_when_in_24_and_in_21_both_speak():
    result = ask(
        "Quando há mais interessados do que vagas no PGD, quem tem prioridade?",
        draft=extractive_draft,
    )

    assert result.status == "insufficient_evidence"
    assert "Evidência insuficiente" in result.message
    assert "IN 24 vigente" not in result.message
    assert "consolidada" not in result.message.lower()
    act_labels = {citation.act_label for citation in result.citations}
    assert "IN conjunta 24/2023" in act_labels, result.citations
    assert "IN conjunta 21/2024" in act_labels, result.citations


def test_ask_does_not_keep_a_single_winner_when_unifesp_and_federal_conflict():
    local = RetrievedArticle(
        id="unifesp-resolucao-262-2025:13",
        act_id="unifesp-resolucao-262-2025",
        act_label="Resolução CONSU 262/2025",
        article="13",
        page=4,
        text=(
            "Art. 13. Só poderão ingressar no PGD - modalidade teletrabalho "
            "(TLTra), os(as) servidores(as) que já tenham cumprido 1 (um) ano "
            "de estágio probatório."
        ),
        pdf_url="/snapshot/unifesp-resolucao-262-2025.pdf",
    )
    federal = RetrievedArticle(
        id="in-conjunta-21-2024:1",
        act_id="in-conjunta-21-2024",
        act_label="IN conjunta 21/2024",
        article="1",
        page=1,
        text=(
            "Art. 1º Poderão ser dispensadas do disposto nos §§2º e 3º as "
            "pessoas: V - gestantes."
        ),
        pdf_url="/snapshot/in-conjunta-21-2024.pdf",
    )

    result = ask(
        "Servidora gestante em estágio probatório pode aderir ao teletrabalho?",
        retrieve=lambda _question: [local, federal],
        draft=lambda _question, _articles: Draft(
            message="Pela Resolução 262, a gestante em estágio não pode aderir.",
            citations=[
                DraftCitation(
                    article_id=local.id,
                    quote="já tenham cumprido 1 (um) ano de estágio probatório",
                )
            ],
        ),
    )

    act_labels = {citation.act_label for citation in result.citations}
    assert "Resolução CONSU 262/2025" in act_labels, result.citations
    assert "IN conjunta 21/2024" in act_labels, result.citations
    assert "IN 24 vigente" not in result.message


def test_historical_question_cites_resolucao_213_when_it_entered_into_force():
    result = ask(
        "Quando a resolução antiga de 2021, antes da 262, entra em vigor?",
        draft=extractive_draft,
    )

    matching = [
        citation
        for citation in result.citations
        if "213/2021" in citation.act_label
        and citation.article == "50"
        and citation.page == 18
    ]
    assert matching, result.citations
    assert matching[0].act_label == "Resolução CONSU 213/2021"
    assert matching[0].pdf_url.endswith(
        "/snapshot/unifesp-resolucao-213-2021.pdf#page=18"
    )
    assert all(
        citation.act_label != "PGD Unifesp v1" for citation in result.citations
    )


def test_default_current_question_does_not_cite_resolucao_213():
    result = ask(
        "A participação no teletrabalho constitui direito adquirido?",
        draft=extractive_draft,
    )

    assert result.status == "answered"
    assert all("213/2021" not in citation.act_label for citation in result.citations)
    assert any(
        citation.act_label == "Resolução CONSU 262/2025" and citation.article == "19"
        for citation in result.citations
    )


@pytest.mark.parametrize(
    "question",
    [
        "Qual era a regra de 2021 para o teletrabalho na Unifesp?",
        "Como funcionava o teletrabalho antes da 262?",
        "O que a resolução antiga dizia sobre o programa de gestão teletrabalho?",
    ],
)
def test_historical_question_examples_can_cite_resolucao_213(question: str):
    result = ask(question, draft=extractive_draft)

    matching = [
        citation
        for citation in result.citations
        if citation.act_label == "Resolução CONSU 213/2021"
        and citation.article
        and citation.page
    ]
    assert matching, (question, result.citations)
    assert all(
        citation.act_label != "PGD Unifesp v1" for citation in result.citations
    )
