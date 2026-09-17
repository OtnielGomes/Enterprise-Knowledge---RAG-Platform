from datetime import date

import pytest

from ask.service import ask


def test_ask_returns_insufficient_evidence_for_a_teletrabalho_question():
    result = ask("O teletrabalho é um direito do servidor?")

    assert result.status == "insufficient_evidence"
    assert result.citations == []
    assert "Evidência insuficiente" in result.message


def test_ask_includes_the_corpus_cutoff():
    result = ask("Qual a modalidade permitida de teletrabalho?")

    assert result.corpus_cutoff == date(2025, 12, 31)


def test_ask_rejects_a_blank_question():
    with pytest.raises(ValueError, match="question"):
        ask("   ")
