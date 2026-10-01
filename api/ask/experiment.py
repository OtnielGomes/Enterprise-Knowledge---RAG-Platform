from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from ask.service import AskResult, Drafter


@dataclass(frozen=True)
class AskRevision:
    commit: str
    dirty: bool


@dataclass(frozen=True)
class PublishedCitation:
    act_id: str
    act_label: str
    article: str
    page: int
    pdf_url: str


@dataclass(frozen=True)
class PublishedItem:
    id: str
    category: str
    question: str
    expected_act: str | None
    expected_article: str | None
    must_abstain: bool
    conflict_acts: tuple[str, ...]
    status: str
    message: str
    citations: tuple[PublishedCitation, ...]
    drafter: str
    scorer_failures: tuple[str, ...]
    latency_ms: int
    prompt_tokens: int | None
    completion_tokens: int | None


@dataclass(frozen=True)
class AskExperimentRecord:
    chat_model: str
    commit: str
    dirty: bool
    corpus_cutoff: date
    items: tuple[PublishedItem, ...]


def main(
    argv: list[str] | None = None,
    *,
    chat_key: str | None = None,
    host_key: str | None = None,
    load_set: Callable[[], dict] | None = None,
    snapshot_cutoff: date | None = None,
    read_revision: Callable[[], AskRevision] | None = None,
    publisher: Callable[..., None] | None = None,
    clock: Callable[[], datetime] | None = None,
    ask: Callable[..., object] | None = None,
    draft: Drafter | None = None,
    chat_model: str | None = None,
    host: Any | None = None,
) -> int:
    del argv
    if chat_key is None:
        from ask.settings import get_settings

        chat_key = get_settings().openai_api_key
    if not chat_key.strip():
        return _refuse("OPENAI_API_KEY is empty")
    if host_key is None:
        host_key = os.environ.get("LANGSMITH_API_KEY", "")
    if not host_key.strip():
        return _refuse("LANGSMITH_API_KEY is empty")
    if load_set is None:
        from ask.golden_eval import load_golden_set

        load_set = load_golden_set
    try:
        golden_set = load_set()
        golden_cutoff = date.fromisoformat(str(golden_set["corpus_cutoff"]))
    except Exception as error:
        return _refuse(f"Golden Set cannot be loaded: {error}")
    if snapshot_cutoff is None:
        from ask.snapshot import load_snapshot

        snapshot_cutoff = load_snapshot().corpus_cutoff
    if golden_cutoff != snapshot_cutoff:
        return _refuse(
            "snapshot Corpus Cutoff "
            f"{snapshot_cutoff.isoformat()} does not match the Golden Set "
            f"Corpus Cutoff {golden_cutoff.isoformat()}"
        )
    if read_revision is None:
        read_revision = read_git_revision
    try:
        revision = read_revision()
    except Exception as error:
        return _refuse(f"Ask revision cannot be read: {error}")
    if chat_model is None:
        from ask.settings import get_settings

        chat_model = get_settings().chat_model
    try:
        record = _collect(
            golden_set,
            revision=revision,
            chat_model=chat_model,
            corpus_cutoff=golden_cutoff,
            clock=clock or _wall_clock,
            ask=ask,
            draft=draft,
        )
    except _InvalidRun as error:
        return _refuse(str(error))
    if publisher is None:
        client = host if host is not None else _langsmith_client()

        def publish(experiment: AskExperimentRecord) -> None:
            publish_experiment(experiment, client=client)
    else:
        publish = publisher
    publish(record)
    return _report(record)


def _collect(
    golden_set: dict,
    *,
    revision: AskRevision,
    chat_model: str,
    corpus_cutoff: date,
    clock: Callable[[], datetime],
    ask: Callable[..., object] | None,
    draft: Drafter | None,
) -> AskExperimentRecord:
    from ask.golden_eval import evaluate_item
    from ask.service import ask as ask_question
    from ask.snapshot import load_snapshot

    runner = ask if ask is not None else ask_question
    article_ids = {article.id for article in load_snapshot().articles}
    items: list[PublishedItem] = []
    for item in golden_set["items"]:
        started = clock()
        try:
            result = (
                runner(item["question"], draft=draft)
                if draft
                else runner(item["question"])
            )
        except Exception as error:
            raise _InvalidRun(f"Ask failed: {error}") from error
        finished = clock()
        produced = result if isinstance(result, AskResult) else None
        if produced is None:
            raise _InvalidRun("Ask failed: result was not an Ask Result")
        if produced.drafter != "openai":
            raise _InvalidRun("Ask Result used the extractive draft")
        if produced.prompt_tokens is None or produced.completion_tokens is None:
            raise _InvalidRun("model draft is missing a token count")
        failures = evaluate_item(item, produced, article_ids)
        items.append(
            _published_item(
                item,
                produced,
                failures,
                _latency_ms(started, finished),
            )
        )
    return AskExperimentRecord(
        chat_model=chat_model,
        commit=revision.commit,
        dirty=revision.dirty,
        corpus_cutoff=corpus_cutoff,
        items=tuple(items),
    )


def _published_item(
    item: dict,
    result: AskResult,
    failures: list[str],
    latency_ms: int,
) -> PublishedItem:
    expected_article = item.get("expected_article")
    return PublishedItem(
        id=item["id"],
        category=item["category"],
        question=item["question"],
        expected_act=item.get("expected_act"),
        expected_article=None if expected_article is None else str(expected_article),
        must_abstain=bool(item["must_abstain"]),
        conflict_acts=tuple(item.get("conflict_acts") or ()),
        status=result.status,
        message=result.message,
        citations=tuple(
            PublishedCitation(
                act_id=citation.act_id,
                act_label=citation.act_label,
                article=citation.article,
                page=citation.page,
                pdf_url=citation.pdf_url,
            )
            for citation in result.citations
        ),
        drafter=result.drafter,
        scorer_failures=tuple(failures),
        latency_ms=latency_ms,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )


def _latency_ms(started: datetime, finished: datetime) -> int:
    return int((finished - started).total_seconds() * 1000)


def _wall_clock() -> datetime:
    return datetime.now(timezone.utc)


DATASET_NAME = "ask-golden-set"


def publish_experiment(record: AskExperimentRecord, *, client: Any) -> None:
    dataset = _ensure_dataset(client)
    current_ids = {item.id for item in record.items}
    kept: dict[str, Any] = {}
    stale: list[object] = []
    for example in list(client.list_examples(dataset_id=dataset.id)):
        item_id = (example.metadata or {}).get("golden_item_id")
        if isinstance(item_id, str) and item_id in current_ids and item_id not in kept:
            kept[item_id] = example
        else:
            stale.append(example.id)
    example_ids: dict[str, object] = {}
    run_inputs: dict[str, dict[str, Any]] = {}
    for item in record.items:
        inputs, outputs, metadata = _example_bodies(item)
        run_inputs[item.id] = inputs
        previous = kept.get(item.id)
        if previous is None:
            created = client.create_example(
                inputs=inputs,
                outputs=outputs,
                metadata=metadata,
                dataset_id=dataset.id,
            )
            example_ids[item.id] = created.id
        else:
            client.update_example(
                previous.id,
                inputs=inputs,
                outputs=outputs,
                metadata=metadata,
            )
            example_ids[item.id] = previous.id
    if stale:
        client.delete_examples(stale)
    project = client.create_project(
        _experiment_name(record),
        reference_dataset_id=dataset.id,
        metadata={
            "chat_model": record.chat_model,
            "commit": record.commit,
            "dirty": record.dirty,
            "corpus_cutoff": record.corpus_cutoff.isoformat(),
        },
    )
    for item in record.items:
        end = datetime.now(timezone.utc)
        start = end - timedelta(milliseconds=item.latency_ms)
        client.create_run(
            item.id,
            run_inputs[item.id],
            "chain",
            project_name=project.name,
            outputs=_run_outputs(item),
            reference_example_id=example_ids[item.id],
            extra={"metadata": {"chat_model": record.chat_model}},
            prompt_tokens=item.prompt_tokens,
            completion_tokens=item.completion_tokens,
            start_time=start,
            end_time=end,
        )


def _ensure_dataset(client: Any) -> Any:
    if client.has_dataset(dataset_name=DATASET_NAME):
        return client.read_dataset(dataset_name=DATASET_NAME)
    return client.create_dataset(
        DATASET_NAME,
        description="Mirror of the Golden Set for Ask Experiments",
    )


def _example_bodies(
    item: PublishedItem,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    inputs = {
        "id": item.id,
        "category": item.category,
        "question": item.question,
        "expected_act": item.expected_act,
        "expected_article": item.expected_article,
        "must_abstain": item.must_abstain,
        "conflict_acts": list(item.conflict_acts),
    }
    return inputs, _run_outputs(item), {"golden_item_id": item.id}


def _run_outputs(item: PublishedItem) -> dict[str, Any]:
    return {
        "status": item.status,
        "message": item.message,
        "citations": [asdict(citation) for citation in item.citations],
        "drafter": item.drafter,
        "scorer_failures": list(item.scorer_failures),
        "latency_ms": item.latency_ms,
        "prompt_tokens": item.prompt_tokens,
        "completion_tokens": item.completion_tokens,
    }


def _experiment_name(record: AskExperimentRecord) -> str:
    dirty = "-dirty" if record.dirty else ""
    return (
        f"ask-{record.commit}{dirty}-{record.corpus_cutoff.isoformat()}-"
        f"{uuid4().hex[:12]}"
    )


def _langsmith_client() -> Any:
    from langsmith import Client

    return Client()


def _report(record: AskExperimentRecord) -> int:
    passed = sum(1 for item in record.items if not item.scorer_failures)
    print(f"Golden Pass Rate: {passed}/{len(record.items)}")
    drafters = {item.drafter for item in record.items}
    drafter = next(iter(drafters)) if len(drafters) == 1 else "mixed"
    print(f"drafter={drafter}")
    failed = [item for item in record.items if item.scorer_failures]
    for item in failed:
        print(f"{item.id}: {', '.join(item.scorer_failures)}")
    return 1 if failed else 0


def read_git_revision() -> AskRevision:
    root = Path(__file__).resolve().parents[2]
    try:
        commit = _git(root, "rev-parse", "HEAD")
        status = _git(root, "status", "--porcelain")
    except (OSError, subprocess.CalledProcessError) as error:
        raise RuntimeError(str(error)) from error
    if not commit:
        raise RuntimeError("git rev-parse returned an empty commit")
    return AskRevision(commit=commit, dirty=bool(status))


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


class _InvalidRun(Exception):
    pass


def _refuse(reason: str) -> int:
    print(reason)
    print("no Ask Experiment was published")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
