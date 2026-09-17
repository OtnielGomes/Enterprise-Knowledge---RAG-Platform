from fastapi.testclient import TestClient

from ask.http import app

client = TestClient(app)


def test_post_ask_returns_insufficient_evidence():
    response = client.post(
        "/ask",
        json={"question": "O teletrabalho é um direito do servidor?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "insufficient_evidence"
    assert body["citations"] == []
    assert "Evidência insuficiente" in body["message"]
    assert body["corpus_cutoff"] == "2025-12-31"


def test_post_ask_rejects_a_blank_question():
    response = client.post("/ask", json={"question": "   "})

    assert response.status_code == 422
