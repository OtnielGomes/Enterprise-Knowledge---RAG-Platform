import logging

import pytest
from fastapi.testclient import TestClient

from ask.http import app
from ask.settings import get_settings

client = TestClient(app)

SERVIDOR_ASK_FIELDS = {"status", "message", "citations", "corpus_cutoff"}


def _assert_servidor_ask_body(body: dict) -> None:
    assert set(body) == SERVIDOR_ASK_FIELDS


def test_post_ask_returns_insufficient_evidence_when_the_snapshot_cannot_answer():
    response = client.post(
        "/ask",
        json={"question": "Qual a alíquota do IOF para investimento no exterior?"},
    )

    assert response.status_code == 200
    body = response.json()
    _assert_servidor_ask_body(body)
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
    _assert_servidor_ask_body(body)
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
    _assert_servidor_ask_body(body)
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
        "unifesp-resolucao-213-2021.pdf",
    ],
)
def test_snapshot_pdf_is_served_for_indexed_acts(filename: str):
    response = client.get(f"/snapshot/{filename}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF")


def test_post_ask_historical_question_cites_resolucao_213():
    response = client.post(
        "/ask",
        json={
            "question": (
                "Quando a resolução antiga de 2021, antes da 262, entra em vigor?"
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    _assert_servidor_ask_body(body)
    matching = [
        citation
        for citation in body["citations"]
        if citation["act_label"] == "Resolução CONSU 213/2021"
        and citation["article"] == "50"
        and citation["page"] == 18
    ]
    assert matching
    assert matching[0]["pdf_url"].endswith(
        "/snapshot/unifesp-resolucao-213-2021.pdf#page=18"
    )


def test_post_ask_default_current_question_does_not_cite_resolucao_213():
    response = client.post(
        "/ask",
        json={
            "question": "A participação no teletrabalho constitui direito adquirido?"
        },
    )

    assert response.status_code == 200
    body = response.json()
    _assert_servidor_ask_body(body)
    assert body["status"] == "answered"
    assert all(
        "213/2021" not in citation["act_label"] for citation in body["citations"]
    )


def test_post_ask_logs_duration_status_and_extractive_drafter(
    caplog: pytest.LogCaptureFixture,
):
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        response = client.post(
            "/ask",
            json={"question": "Qual a alíquota do IOF para investimento no exterior?"},
        )

    assert response.status_code == 200
    body = response.json()
    _assert_servidor_ask_body(body)
    log_text = caplog.text
    assert "duration_ms=" in log_text
    assert f"status={body['status']}" in log_text
    assert "drafter=extractive" in log_text
    assert "prompt_tokens=" not in log_text
    assert "completion_tokens=" not in log_text


def test_post_ask_logs_extractive_drafter_when_chat_model_falls_back(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-a-real-key")
    get_settings.cache_clear()

    def fail_openai(*_args, **_kwargs):
        raise RuntimeError("chat model unavailable")

    monkeypatch.setattr("ask.generate.openai_draft", fail_openai)
    try:
        with caplog.at_level(logging.INFO, logger="uvicorn.error"):
            response = client.post(
                "/ask",
                json={
                    "question": (
                        "A participação no teletrabalho constitui direito adquirido?"
                    )
                },
            )
    finally:
        monkeypatch.setenv("OPENAI_API_KEY", "")
        get_settings.cache_clear()

    assert response.status_code == 200
    _assert_servidor_ask_body(response.json())
    assert "drafter=extractive" in caplog.text
    assert "duration_ms=" in caplog.text
    assert "status=" in caplog.text
