from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _compose_text() -> str:
    return (REPO_ROOT / "compose.yaml").read_text(encoding="utf-8")


def _env_example_text() -> str:
    return (REPO_ROOT / ".env.example").read_text(encoding="utf-8")


def test_compose_publishes_only_the_chat_port_on_all_interfaces():
    text = _compose_text()

    assert '"127.0.0.1:5432:5432"' in text
    assert '"127.0.0.1:8000:8000"' in text
    assert '"3000:3000"' in text
    assert '"5432:5432"' not in text
    assert '"8000:8000"' not in text


def test_compose_is_the_only_runtime_and_has_no_object_storage():
    compose_files = sorted(
        path.name
        for path in [
            *REPO_ROOT.glob("compose*.y*ml"),
            *REPO_ROOT.glob("docker-compose*.y*ml"),
        ]
    )
    assert compose_files == ["compose.yaml"]

    text = _compose_text().lower()
    assert "minio" not in text
    assert "redis" not in text
    for service in ("db:", "api:", "web:"):
        assert service in text


def test_openai_key_stays_in_environment_not_images_or_compose():
    compose = _compose_text()
    assert "OPENAI_API_KEY: ${OPENAI_API_KEY" in compose
    assert "sk-" not in compose

    example = _env_example_text()
    assert "OPENAI_API_KEY=" in example
    assert "WEB_ORIGIN=" in example
    for line in example.splitlines():
        if line.startswith("OPENAI_API_KEY="):
            assert line.strip() == "OPENAI_API_KEY="

    for relative in ("api/Dockerfile", "web/Dockerfile"):
        dockerfile = (REPO_ROOT / relative).read_text(encoding="utf-8")
        assert "OPENAI_API_KEY" not in dockerfile
        assert "sk-" not in dockerfile


def test_snapshot_contains_the_five_normative_act_pdfs():
    pdfs = sorted(path.name for path in (REPO_ROOT / "snapshot").glob("*.pdf"))
    assert pdfs == [
        "decreto-11072-2022.pdf",
        "in-conjunta-21-2024.pdf",
        "in-conjunta-24-2023.pdf",
        "unifesp-resolucao-213-2021.pdf",
        "unifesp-resolucao-262-2025.pdf",
    ]
