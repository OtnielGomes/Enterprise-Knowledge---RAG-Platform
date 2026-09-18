from __future__ import annotations

import json
from pathlib import Path

from ask.service import AskResult
from ask.snapshot import load_snapshot

SUPERSEDED_ACT_ID = "unifesp-resolucao-213-2021"
REQUIRED_CATEGORIES = frozenset(
    {
        "easy",
        "temporal_current",
        "historical",
        "unanswerable",
        "amendment_conflict",
        "chefia",
    }
)


def golden_set_path() -> Path:
    return Path(__file__).resolve().parents[2] / "eval" / "golden_set.json"


def load_golden_set(path: Path | None = None) -> dict:
    payload = json.loads((path or golden_set_path()).read_text(encoding="utf-8"))
    if not isinstance(payload.get("items"), list):
        raise ValueError("golden set must include an items list")
    return payload


def evaluate_item(
    item: dict,
    result: AskResult,
    article_ids: set[str],
) -> list[str]:
    failures: list[str] = []
    cited_acts = {citation.act_id for citation in result.citations}
    cited_pairs = {
        (citation.act_id, citation.article) for citation in result.citations
    }

    if any(
        f"{citation.act_id}:{citation.article}" not in article_ids
        for citation in result.citations
    ):
        failures.append("fabricated_citation")

    if item.get("category") != "historical" and SUPERSEDED_ACT_ID in cited_acts:
        failures.append("cited_213_as_current")

    if item.get("must_abstain"):
        if result.status != "insufficient_evidence":
            failures.append("expected_insufficient_evidence")
    elif result.status != "answered":
        failures.append("retrieve_missed")

    expected_act = item.get("expected_act")
    expected_article = item.get("expected_article")
    if expected_act:
        if expected_act not in cited_acts:
            failures.append("missing_expected_act")
        elif expected_article and (expected_act, str(expected_article)) not in cited_pairs:
            failures.append("missing_expected_article")

    conflict_acts = set(item.get("conflict_acts") or [])
    cited_conflict = conflict_acts & cited_acts
    if cited_conflict and cited_conflict != conflict_acts:
        failures.append("conflict_single_winner")

    return failures


def evaluate_golden_set(
    *,
    path: Path | None = None,
) -> list[dict]:
    from ask.service import ask

    snapshot = load_snapshot()
    article_ids = {article.id for article in snapshot.articles}
    rows: list[dict] = []
    for item in load_golden_set(path)["items"]:
        result = ask(item["question"])
        failures = evaluate_item(item, result, article_ids)
        rows.append({"id": item["id"], "failures": failures, "status": result.status})
    return rows


def main() -> int:
    rows = evaluate_golden_set()
    failed = [row for row in rows if row["failures"]]
    print(f"{len(rows) - len(failed)}/{len(rows)} golden items passed through Ask")
    for row in failed:
        print(f"{row['id']}: {row['failures']} ({row['status']})")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
