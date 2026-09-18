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


def test_post_ask_rejects_a_blank_question():
    response = client.post("/ask", json={"question": "   "})

    assert response.status_code == 422


def test_snapshot_pdf_is_served_for_citation_checks():
    response = client.get("/snapshot/unifesp-resolucao-262-2025.pdf")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF")
