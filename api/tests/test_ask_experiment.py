import json
from collections.abc import Sequence
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone

import pytest

from ask.experiment import AskRevision, main
from ask.service import Draft, Drafter, DrafterName, RetrievedArticle
from ask.snapshot import extractive_draft


def test_missing_chat_key_refuses_before_ask_or_the_host(
    capsys: pytest.CaptureFixture[str],
):
    published: list[object] = []
    asked: list[str] = []

    code = main(
        chat_key="",
        host_key="host-key",
        load_set=_golden_set,
        snapshot_cutoff=date(2026, 9, 18),
        read_revision=lambda: AskRevision(commit="abc123", dirty=False),
        publisher=lambda record: published.append(record),
        clock=lambda: datetime(2026, 10, 1, tzinfo=timezone.utc),
        ask=lambda question: asked.append(question),
    )

    output = capsys.readouterr().out
    assert code == 1
    assert "OPENAI_API_KEY is empty" in output
    assert "no Ask Experiment was published" in output
    assert "Golden Pass Rate" not in output
    assert published == []
    assert asked == []


def test_missing_host_key_refuses_before_ask_or_the_host(
    capsys: pytest.CaptureFixture[str],
):
    published: list[object] = []
    asked: list[str] = []

    code = main(
        chat_key="chat-key",
        host_key="",
        load_set=_golden_set,
        snapshot_cutoff=date(2026, 9, 18),
        read_revision=lambda: AskRevision(commit="abc123", dirty=False),
        publisher=lambda record: published.append(record),
        clock=lambda: datetime(2026, 10, 1, tzinfo=timezone.utc),
        ask=lambda question: asked.append(question),
    )

    output = capsys.readouterr().out
    assert code == 1
    assert "LANGSMITH_API_KEY is empty" in output
    assert "no Ask Experiment was published" in output
    assert "Golden Pass Rate" not in output
    assert published == []
    assert asked == []


def test_corpus_cutoff_mismatch_refuses_before_ask_or_the_host(
    capsys: pytest.CaptureFixture[str],
):
    published: list[object] = []
    asked: list[str] = []

    code = main(
        chat_key="chat-key",
        host_key="host-key",
        load_set=_golden_set,
        snapshot_cutoff=date(2026, 1, 1),
        read_revision=lambda: AskRevision(commit="abc123", dirty=False),
        publisher=lambda record: published.append(record),
        clock=lambda: datetime(2026, 10, 1, tzinfo=timezone.utc),
        ask=lambda question: asked.append(question),
    )

    output = capsys.readouterr().out
    assert code == 1
    assert "Corpus Cutoff" in output
    assert "2026-01-01" in output
    assert "2026-09-18" in output
    assert "no Ask Experiment was published" in output
    assert "Golden Pass Rate" not in output
    assert published == []
    assert asked == []


def test_rejected_golden_set_refuses_before_ask_or_the_host(
    capsys: pytest.CaptureFixture[str],
):
    published: list[object] = []
    asked: list[str] = []

    def load_set() -> dict:
        raise ValueError("golden set must include an items list")

    code = main(
        chat_key="chat-key",
        host_key="host-key",
        load_set=load_set,
        snapshot_cutoff=date(2026, 9, 18),
        read_revision=lambda: AskRevision(commit="abc123", dirty=False),
        publisher=lambda record: published.append(record),
        clock=lambda: datetime(2026, 10, 1, tzinfo=timezone.utc),
        ask=lambda question: asked.append(question),
    )

    output = capsys.readouterr().out
    assert code == 1
    assert "Golden Set cannot be loaded" in output
    assert "golden set must include an items list" in output
    assert "no Ask Experiment was published" in output
    assert "Golden Pass Rate" not in output
    assert published == []
    assert asked == []


def test_unreadable_ask_revision_refuses_before_ask_or_the_host(
    capsys: pytest.CaptureFixture[str],
):
    published: list[object] = []
    asked: list[str] = []

    def read_revision() -> AskRevision:
        raise RuntimeError("git rev-parse failed")

    code = main(
        chat_key="chat-key",
        host_key="host-key",
        load_set=_golden_set,
        snapshot_cutoff=date(2026, 9, 18),
        read_revision=read_revision,
        publisher=lambda record: published.append(record),
        clock=lambda: datetime(2026, 10, 1, tzinfo=timezone.utc),
        ask=lambda question: asked.append(question),
    )

    output = capsys.readouterr().out
    assert code == 1
    assert "Ask revision cannot be read" in output
    assert "git rev-parse failed" in output
    assert "no Ask Experiment was published" in output
    assert "Golden Pass Rate" not in output
    assert published == []
    assert asked == []


def test_valid_run_publishes_one_experiment_and_exits_0(
    capsys: pytest.CaptureFixture[str],
):
    published: list[object] = []
    drafted: list[str] = []
    clock = _clock(milliseconds=1500)

    def publish(record: object) -> None:
        assert drafted == [
            "A participação no teletrabalho constitui direito adquirido?",
            "É vedada a autorização de horas extras no teletrabalho?",
        ]
        published.append(record)

    code = main(
        chat_key="chat-key",
        host_key="host-key",
        load_set=_two_passing_items,
        snapshot_cutoff=date(2026, 9, 18),
        read_revision=lambda: AskRevision(commit="abc123", dirty=False),
        publisher=publish,
        clock=clock,
        draft=_model_draft(drafted, prompt_tokens=11, completion_tokens=7),
        chat_model="gpt-test",
    )

    output = capsys.readouterr().out
    assert code == 0
    assert published != []
    assert len(published) == 1
    record = published[0]
    assert record.chat_model == "gpt-test"
    assert record.commit == "abc123"
    assert record.dirty is False
    assert record.corpus_cutoff == date(2026, 9, 18)
    assert [item.id for item in record.items] == [
        "easy-direito-adquirido",
        "easy-horas-extras",
    ]
    first = record.items[0]
    assert first.category == "easy"
    assert first.question == (
        "A participação no teletrabalho constitui direito adquirido?"
    )
    assert first.expected_act == "unifesp-resolucao-262-2025"
    assert first.expected_article == "19"
    assert first.must_abstain is False
    assert first.conflict_acts == ()
    assert first.status == "answered"
    assert first.message == "Resposta do modelo."
    assert ("unifesp-resolucao-262-2025", "19") in {
        (citation.act_id, citation.article) for citation in first.citations
    }
    assert first.drafter == "openai"
    assert first.scorer_failures == ()
    assert first.latency_ms == 1500
    assert first.prompt_tokens == 11
    assert first.completion_tokens == 7
    assert record.items[1].latency_ms == 1500
    assert record.items[1].prompt_tokens == 11
    assert record.items[1].completion_tokens == 7
    blob = json.dumps(asdict(record), default=str).lower()
    assert "price" not in blob
    assert "dollar" not in blob
    assert "Golden Pass Rate: 2/2" in output
    assert "drafter=openai" in output


def test_scorer_failure_still_publishes_and_exits_1(
    capsys: pytest.CaptureFixture[str],
):
    published: list[object] = []

    def draft(question: str, articles: Sequence[RetrievedArticle]) -> Draft:
        if question == "É vedada a autorização de horas extras no teletrabalho?":
            return Draft(
                message="Sem citação.",
                citations=(),
                drafter="openai",
                prompt_tokens=3,
                completion_tokens=4,
            )
        base = extractive_draft(question, articles)
        return Draft(
            message="Resposta do modelo.",
            citations=base.citations,
            drafter="openai",
            prompt_tokens=11,
            completion_tokens=7,
        )

    code = main(
        chat_key="chat-key",
        host_key="host-key",
        load_set=_two_passing_items,
        snapshot_cutoff=date(2026, 9, 18),
        read_revision=lambda: AskRevision(commit="abc123", dirty=False),
        publisher=lambda record: published.append(record),
        clock=_clock(milliseconds=1500),
        draft=draft,
        chat_model="gpt-test",
    )

    output = capsys.readouterr().out
    assert code == 1
    assert len(published) == 1
    record = published[0]
    assert [item.id for item in record.items] == [
        "easy-direito-adquirido",
        "easy-horas-extras",
    ]
    assert record.items[1].scorer_failures == (
        "retrieve_missed",
        "missing_expected_act",
    )
    assert "Golden Pass Rate: 1/2" in output
    assert (
        "easy-horas-extras: retrieve_missed, missing_expected_act" in output
    )
    assert "easy-direito-adquirido:" not in output


def test_extractive_drafter_discards_the_run_without_publishing(
    capsys: pytest.CaptureFixture[str],
):
    published: list[object] = []
    drafted: list[str] = []

    def draft(question: str, articles: Sequence[RetrievedArticle]) -> Draft:
        drafted.append(question)
        if question == "É vedada a autorização de horas extras no teletrabalho?":
            return Draft(
                message="Rascunho extrativo.",
                citations=(),
                drafter="extractive",
                prompt_tokens=11,
                completion_tokens=7,
            )
        base = extractive_draft(question, articles)
        return Draft(
            message="Resposta do modelo.",
            citations=base.citations,
            drafter="openai",
            prompt_tokens=11,
            completion_tokens=7,
        )

    code = main(
        chat_key="chat-key",
        host_key="host-key",
        load_set=_set_with_a_later_item,
        snapshot_cutoff=date(2026, 9, 18),
        read_revision=lambda: AskRevision(commit="abc123", dirty=False),
        publisher=lambda record: published.append(record),
        clock=_clock(milliseconds=1500),
        draft=draft,
        chat_model="gpt-test",
    )

    output = capsys.readouterr().out
    assert code == 1
    assert "Ask Result used the extractive draft" in output
    assert "no Ask Experiment was published" in output
    assert "Golden Pass Rate" not in output
    assert published == []
    assert drafted == [
        "A participação no teletrabalho constitui direito adquirido?",
        "É vedada a autorização de horas extras no teletrabalho?",
    ]


@pytest.mark.parametrize(
    ("prompt_tokens", "completion_tokens"),
    [(None, 4), (4, None)],
)
def test_missing_token_count_discards_the_run_without_publishing(
    capsys: pytest.CaptureFixture[str],
    prompt_tokens: int | None,
    completion_tokens: int | None,
):
    published: list[object] = []

    def draft(question: str, articles: Sequence[RetrievedArticle]) -> Draft:
        if question == "É vedada a autorização de horas extras no teletrabalho?":
            return Draft(
                message="Sem uso.",
                citations=(),
                drafter="openai",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
        base = extractive_draft(question, articles)
        return Draft(
            message="Resposta do modelo.",
            citations=base.citations,
            drafter="openai",
            prompt_tokens=11,
            completion_tokens=7,
        )

    code = main(
        chat_key="chat-key",
        host_key="host-key",
        load_set=_two_passing_items,
        snapshot_cutoff=date(2026, 9, 18),
        read_revision=lambda: AskRevision(commit="abc123", dirty=False),
        publisher=lambda record: published.append(record),
        clock=_clock(milliseconds=1500),
        draft=draft,
        chat_model="gpt-test",
    )

    output = capsys.readouterr().out
    assert code == 1
    assert "model draft is missing a token count" in output
    assert "no Ask Experiment was published" in output
    assert "Golden Pass Rate" not in output
    assert published == []


def test_ask_exception_discards_the_run_without_publishing(
    capsys: pytest.CaptureFixture[str],
):
    published: list[object] = []
    asked: list[str] = []

    def ask(question: str, draft: Drafter | None = None) -> object:
        asked.append(question)
        if len(asked) == 2:
            raise RuntimeError("model disconnected")
        from ask.service import ask as ask_question

        return ask_question(question, draft=draft)

    code = main(
        chat_key="chat-key",
        host_key="host-key",
        load_set=_set_with_a_later_item,
        snapshot_cutoff=date(2026, 9, 18),
        read_revision=lambda: AskRevision(commit="abc123", dirty=False),
        publisher=lambda record: published.append(record),
        clock=_clock(milliseconds=1500),
        ask=ask,
        draft=_model_draft([], prompt_tokens=11, completion_tokens=7),
        chat_model="gpt-test",
    )

    output = capsys.readouterr().out
    assert code == 1
    assert "Ask failed: model disconnected" in output
    assert "no Ask Experiment was published" in output
    assert "Golden Pass Rate" not in output
    assert published == []
    assert asked == [
        "A participação no teletrabalho constitui direito adquirido?",
        "É vedada a autorização de horas extras no teletrabalho?",
    ]


def test_golden_set_without_a_corpus_cutoff_refuses(
    capsys: pytest.CaptureFixture[str],
):
    published: list[object] = []
    asked: list[str] = []

    code = main(
        chat_key="chat-key",
        host_key="host-key",
        load_set=lambda: {"items": []},
        snapshot_cutoff=date(2026, 9, 18),
        read_revision=lambda: AskRevision(commit="abc123", dirty=False),
        publisher=lambda record: published.append(record),
        clock=lambda: datetime(2026, 10, 1, tzinfo=timezone.utc),
        ask=lambda question: asked.append(question),
    )

    output = capsys.readouterr().out
    assert code == 1
    assert "Golden Set cannot be loaded" in output
    assert "no Ask Experiment was published" in output
    assert "Golden Pass Rate" not in output
    assert published == []
    assert asked == []


def test_ask_latency_does_not_include_publisher_time(
    capsys: pytest.CaptureFixture[str],
):
    del capsys
    published: list[object] = []
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    moments = iter(
        [
            start,
            start + timedelta(milliseconds=1500),
            start + timedelta(milliseconds=1500),
            start + timedelta(milliseconds=3000),
            start + timedelta(hours=5),
        ]
    )

    def publish(record: object) -> None:
        next(moments)
        published.append(record)

    code = main(
        chat_key="chat-key",
        host_key="host-key",
        load_set=_items_with_conflict,
        snapshot_cutoff=date(2026, 9, 18),
        read_revision=lambda: AskRevision(commit="abc123", dirty=True),
        publisher=publish,
        clock=lambda: next(moments),
        draft=_model_draft([], prompt_tokens=11, completion_tokens=7),
        chat_model="gpt-test",
    )

    assert code == 0
    record = published[0]
    assert record.dirty is True
    assert record.commit == "abc123"
    assert [item.latency_ms for item in record.items] == [1500, 1500]
    assert record.items[0].conflict_acts == (
        "unifesp-resolucao-262-2025",
        "in-conjunta-24-2023",
    )
    assert record.items[1].conflict_acts == ()


def test_default_publisher_mirrors_the_host_and_keeps_earlier_experiments(
    capsys: pytest.CaptureFixture[str],
):
    del capsys
    host = _FakeLangSmith()
    for _attempt in range(2):
        code = main(
            chat_key="chat-key",
            host_key="host-key",
            load_set=_items_with_conflict,
            snapshot_cutoff=date(2026, 9, 18),
            read_revision=lambda: AskRevision(commit="abc123", dirty=False),
            clock=_clock(milliseconds=1500),
            draft=_model_draft([], prompt_tokens=11, completion_tokens=7),
            chat_model="gpt-test",
            host=host,
        )
        assert code == 0
        assert len(host.examples) == 2

    assert [dataset.name for dataset in host.datasets] == ["ask-golden-set"]
    ids = {example.metadata["golden_item_id"] for example in host.examples}
    assert ids == {"easy-direito-adquirido", "easy-horas-extras"}
    assert len(host.examples) == 2
    kept = next(
        example
        for example in host.examples
        if example.metadata["golden_item_id"] == "easy-direito-adquirido"
    )
    assert kept.inputs["question"] == (
        "A participação no teletrabalho constitui direito adquirido?"
    )
    assert kept.inputs["conflict_acts"] == [
        "unifesp-resolucao-262-2025",
        "in-conjunta-24-2023",
    ]
    assert kept.outputs["expected_act"] == "unifesp-resolucao-262-2025"
    assert "message" not in kept.outputs
    assert "latency_ms" not in kept.outputs
    assert "prompt_tokens" not in kept.outputs
    names = [project.name for project in host.projects]
    assert "earlier-experiment" in names
    fresh = [name for name in names if name != "earlier-experiment"]
    assert len(fresh) == 2
    assert len(set(fresh)) == 2
    fresh_project = next(project for project in host.projects if project.name == fresh[0])
    assert fresh_project.metadata == {
        "chat_model": "gpt-test",
        "commit": "abc123",
        "dirty": False,
        "corpus_cutoff": "2026-09-18",
    }
    assert host.runs[0]["prompt_tokens"] == 11
    assert host.runs[0]["completion_tokens"] == 7
    assert host.runs[0]["outputs"]["message"] == "Resposta do modelo."
    assert "extra" not in host.runs[0]
    assert "total_tokens" not in host.runs[0]
    blob = json.dumps(host.recorded, default=str).lower()
    assert "price" not in blob
    assert "dollar" not in blob
    assert "prompt_cost" not in blob
    assert "completion_cost" not in blob


class _Obj:
    def __init__(self, **kwargs: object) -> None:
        self.__dict__.update(kwargs)


class _FakeLangSmith:
    def __init__(self) -> None:
        self.datasets = [_Obj(id="dataset-1", name="ask-golden-set")]
        self.examples = [
            _Obj(
                id="ex-retired",
                dataset_id="dataset-1",
                inputs={"id": "retired-item", "question": "antiga"},
                outputs={},
                metadata={"golden_item_id": "retired-item"},
            ),
            _Obj(
                id="ex-easy",
                dataset_id="dataset-1",
                inputs={
                    "id": "easy-direito-adquirido",
                    "question": "pergunta antiga",
                },
                outputs={},
                metadata={"golden_item_id": "easy-direito-adquirido"},
            ),
            _Obj(
                id="ex-unknown-1",
                dataset_id="dataset-1",
                inputs={"question": "sem id"},
                outputs={},
                metadata={},
            ),
            _Obj(
                id="ex-unknown-2",
                dataset_id="dataset-1",
                inputs={"question": "sem id tambem"},
                outputs={},
                metadata={},
            ),
        ]
        self.projects = [_Obj(id="prev", name="earlier-experiment", metadata={})]
        self.runs: list[dict] = []
        self.recorded: list[dict] = []

    def has_dataset(self, *, dataset_name: str | None = None, dataset_id: object = None) -> bool:
        del dataset_id
        return any(dataset.name == dataset_name for dataset in self.datasets)

    def read_dataset(self, *, dataset_name: str | None = None, dataset_id: object = None) -> _Obj:
        del dataset_id
        return next(dataset for dataset in self.datasets if dataset.name == dataset_name)

    def create_dataset(self, dataset_name: str, **kwargs: object) -> _Obj:
        dataset = _Obj(id=f"dataset-{len(self.datasets) + 1}", name=dataset_name)
        self.datasets.append(dataset)
        self.recorded.append({"create_dataset": {"name": dataset_name, **kwargs}})
        return dataset

    def list_examples(self, dataset_id: object = None, **kwargs: object) -> list[_Obj]:
        del kwargs
        return [example for example in self.examples if example.dataset_id == dataset_id]

    def create_example(
        self,
        inputs: dict | None = None,
        dataset_id: object = None,
        outputs: dict | None = None,
        metadata: dict | None = None,
        **kwargs: object,
    ) -> _Obj:
        del kwargs
        example = _Obj(
            id=f"ex-{metadata['golden_item_id']}",
            dataset_id=dataset_id,
            inputs=dict(inputs or {}),
            outputs=dict(outputs or {}),
            metadata=dict(metadata or {}),
        )
        self.examples.append(example)
        self.recorded.append(
            {"create_example": {"inputs": inputs, "outputs": outputs, "metadata": metadata}}
        )
        return example

    def update_example(
        self,
        example_id: object,
        *,
        inputs: dict | None = None,
        outputs: dict | None = None,
        metadata: dict | None = None,
        **kwargs: object,
    ) -> dict:
        del kwargs
        example = next(item for item in self.examples if item.id == example_id)
        if inputs is not None:
            example.inputs = dict(inputs)
        if outputs is not None:
            example.outputs = dict(outputs)
        if metadata is not None:
            example.metadata = dict(metadata)
        self.recorded.append(
            {
                "update_example": {
                    "inputs": inputs,
                    "outputs": outputs,
                    "metadata": metadata,
                }
            }
        )
        return {}

    def delete_examples(self, example_ids: list[object], **kwargs: object) -> None:
        del kwargs
        removed = set(example_ids)
        self.examples = [example for example in self.examples if example.id not in removed]
        self.recorded.append({"delete_examples": list(example_ids)})

    def create_project(self, project_name: str, **kwargs: object) -> _Obj:
        if any(project.name == project_name for project in self.projects):
            raise RuntimeError(f"experiment name collision: {project_name}")
        project = _Obj(id=f"proj-{len(self.projects)}", name=project_name, metadata=kwargs.get("metadata") or {})
        self.projects.append(project)
        self.recorded.append({"create_project": {"name": project_name, **kwargs}})
        return project

    def create_run(self, name: str, inputs: dict, run_type: str, **kwargs: object) -> None:
        run = {"name": name, "inputs": inputs, "run_type": run_type, **kwargs}
        self.runs.append(run)
        self.recorded.append({"create_run": run})


def _golden_set() -> dict:
    return {"corpus_cutoff": "2026-09-18", "items": []}


def _set_with_a_later_item() -> dict:
    payload = _two_passing_items()
    payload["items"] = [
        *payload["items"],
        {
            "id": "easy-later",
            "category": "easy",
            "question": "Esta pergunta não deve ser enviada ao Ask.",
            "expected_act": "unifesp-resolucao-262-2025",
            "expected_article": "19",
            "must_abstain": False,
        },
    ]
    return payload


def _items_with_conflict() -> dict:
    payload = _two_passing_items()
    payload["items"][0] = {
        **payload["items"][0],
        "conflict_acts": [
            "unifesp-resolucao-262-2025",
            "in-conjunta-24-2023",
        ],
    }
    return payload


def _two_passing_items() -> dict:
    return {
        "corpus_cutoff": "2026-09-18",
        "items": [
            {
                "id": "easy-direito-adquirido",
                "category": "easy",
                "question": "A participação no teletrabalho constitui direito adquirido?",
                "expected_act": "unifesp-resolucao-262-2025",
                "expected_article": "19",
                "must_abstain": False,
            },
            {
                "id": "easy-horas-extras",
                "category": "easy",
                "question": "É vedada a autorização de horas extras no teletrabalho?",
                "expected_act": "unifesp-resolucao-262-2025",
                "expected_article": "34",
                "must_abstain": False,
            },
        ],
    }


def _model_draft(
    drafted: list[str],
    *,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    drafter: DrafterName = "openai",
) -> Drafter:
    def draft(question: str, articles: Sequence[RetrievedArticle]) -> Draft:
        drafted.append(question)
        base = extractive_draft(question, articles)
        return Draft(
            message="Resposta do modelo.",
            citations=base.citations,
            drafter=drafter,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    return draft


def _clock(milliseconds: int):
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    ticks = {"n": 0}

    def clock() -> datetime:
        moment = start + timedelta(milliseconds=milliseconds * ticks["n"])
        ticks["n"] += 1
        return moment

    return clock
