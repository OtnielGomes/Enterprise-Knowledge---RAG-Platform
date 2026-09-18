import pytest
from fastapi.testclient import TestClient

from ask.http import app

client = TestClient(app)


def test_post_ask_returns_insufficient_evidence_when_the_snapshot_cannot_answer():
    response = client.post(
        "/ask",
        json={"question": "Qual a alíquota do IOF para investimento no exterior?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "insufficient_evidence"
    assert body["citations"] == []
    assert "Evidência insuficiente" in body["message"]
    assert body["corpus_cutoff"] == "2026-09-18"


def test_post_ask_cites_resolucao_262_for_an_easy_current_question():
    response = client.post(
        "/ask",
        json={
            "question": "A participação no teletrabalho constitui direito adquirido?"
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "answered"
    matching = [
        citation
        for citation in body["citations"]
        if citation["act_label"] == "Resolução CONSU 262/2025"
        and citation["article"] == "19"
        and citation["page"] == 5
    ]
    assert matching
    assert matching[0]["pdf_url"].endswith(
        "/snapshot/unifesp-resolucao-262-2025.pdf#page=5"
    )
    federal = {
        citation["act_label"]
        for citation in body["citations"]
        if citation["act_label"] in {"IN conjunta 24/2023", "Decreto 11.072/2022"}
    }
    assert federal


def test_post_ask_refuses_to_synthesize_in_24_and_in_21_without_dropping_citations():
    response = client.post(
        "/ask",
        json={
            "question": "Quando há mais interessados do que vagas no PGD, quem tem prioridade?"
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "insufficient_evidence"
    assert "Evidência insuficiente" in body["message"]
    labels = {citation["act_label"] for citation in body["citations"]}
    assert "IN conjunta 24/2023" in labels
    assert "IN conjunta 21/2024" in labels


def test_post_ask_rejects_a_blank_question():
    response = client.post("/ask", json={"question": "   "})

    assert response.status_code == 422


def test_snapshot_pdf_is_served_for_citation_checks():
    response = client.get("/snapshot/unifesp-resolucao-262-2025.pdf")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF")


@pytest.mark.parametrize(
    "filename",
    [
        "decreto-11072-2022.pdf",
        "in-conjunta-24-2023.pdf",
        "in-conjunta-21-2024.pdf",
    ],
)
def test_snapshot_pdf_is_served_for_remaining_current_acts(filename: str):
    response = client.get(f"/snapshot/{filename}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF")
