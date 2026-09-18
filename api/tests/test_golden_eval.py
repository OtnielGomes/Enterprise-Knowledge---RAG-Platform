import pytest

from ask.golden_eval import (
    REQUIRED_CATEGORIES,
    evaluate_item,
    load_golden_set,
)
from ask.service import Draft, DraftCitation, ask
from ask.snapshot import load_snapshot


@pytest.fixture(scope="module")
def snapshot_articles() -> dict[str, object]:
    return {article.id: article for article in load_snapshot().articles}


@pytest.fixture(scope="module")
def article_ids(snapshot_articles: dict[str, object]) -> set[str]:
    return set(snapshot_articles)


def test_golden_set_covers_annotator_owned_ask_categories():
    payload = load_golden_set()
    items = payload["items"]
    assert 25 <= len(items) <= 40
    categories = {item["category"] for item in items}
    assert REQUIRED_CATEGORIES <= categories
    for item in items:
        assert item["id"]
        assert item["question"]
        assert item["category"] in REQUIRED_CATEGORIES
        assert "expected_act" in item
        assert "expected_article" in item
        assert isinstance(item["must_abstain"], bool)
        if item["must_abstain"] is False:
            assert item["expected_act"]
            assert item["expected_article"]


@pytest.mark.parametrize(
    "item",
    load_golden_set()["items"],
    ids=lambda item: item["id"],
)
def test_golden_item_is_scored_through_ask_only(item: dict, article_ids: set[str]):
    result = ask(item["question"])
    failures = evaluate_item(item, result, article_ids)
    assert failures == [], (
        item["id"],
        failures,
        result.status,
        [(citation.act_id, citation.article) for citation in result.citations],
    )


def test_eval_fails_a_fabricated_citation_even_when_the_prose_looks_right(
    snapshot_articles: dict[str, object],
    article_ids: set[str],
):
    article_19 = snapshot_articles["unifesp-resolucao-262-2025:19"]
    result = ask(
        "A participação no teletrabalho constitui direito adquirido?",
        retrieve=lambda _question: [article_19],
        draft=lambda _question, _articles: Draft(
            message=(
                "A participação no PGD Teletrabalho não constitui direito "
                "adquirido, nos termos do art. 19 da Resolução 262/2025."
            ),
            citations=[
                DraftCitation(
                    article_id="unifesp-resolucao-262-2025:999",
                    quote="artigo fabricado que não está no conjunto recuperado",
                )
            ],
        ),
    )
    item = {
        "id": "eval-fabricated-citation",
        "category": "easy",
        "expected_act": "unifesp-resolucao-262-2025",
        "expected_article": "19",
        "must_abstain": False,
    }

    assert result.status == "insufficient_evidence"
    assert result.citations == []
    failures = evaluate_item(item, result, article_ids)
    assert "retrieve_missed" in failures
    assert "missing_expected_act" in failures


def test_eval_fails_when_a_conflict_item_hides_one_act(
    snapshot_articles: dict[str, object],
    article_ids: set[str],
):
    in_24 = snapshot_articles["in-conjunta-24-2023:14"]
    item = next(
        row
        for row in load_golden_set()["items"]
        if row["id"] == "conflict-prioridade-vagas"
    )
    result = ask(item["question"], retrieve=lambda _question: [in_24])

    failures = evaluate_item(item, result, article_ids)
    assert "conflict_single_winner" in failures
    assert result.status == "answered"
    assert {citation.act_id for citation in result.citations} == {
        "in-conjunta-24-2023"
    }
