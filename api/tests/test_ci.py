from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ask-quality.yml"


def _workflow_text() -> str:
    files = sorted((REPO_ROOT / ".github" / "workflows").glob("*.y*ml"))
    assert [path.name for path in files] == ["ask-quality.yml"]
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def test_ci_runs_ask_pytest_on_pull_request_and_push_to_main():
    text = _workflow_text()

    assert "pull_request" in text
    assert "push" in text
    assert "main" in text
    assert "3.12" in text
    assert ".[dev]" in text
    assert "pytest" in text
    assert 'OPENAI_API_KEY: ""' in text


def test_ci_typechecks_the_chat_shell_as_a_separate_job():
    text = _workflow_text()

    assert "Ask pytest" in text
    assert "Chat typecheck" in text
    assert "npm ci" in text
    assert "npm run typecheck" in text
    assert "next build" not in text
    assert "compose" not in text.lower()


def test_ci_does_not_inject_a_chat_model_key_or_observability_stack():
    text = _workflow_text().lower()

    assert "secrets." not in text
    assert "langfuse" not in text
    assert "ragas" not in text
    assert "opentelemetry" not in text
    assert "ssh" not in text
    assert "droplet" not in text
