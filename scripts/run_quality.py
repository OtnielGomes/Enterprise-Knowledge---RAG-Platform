"""Run Ask quality gates locally (CI mirror plus optional LangSmith Ask Experiment)."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

TRACKED_KEYS = ("OPENAI_API_KEY", "LANGSMITH_API_KEY")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def parse_dotenv(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped.removeprefix("export ").strip()
        if "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values


def resolved_key(name: str, dotenv: dict[str, str]) -> str:
    from_env = os.environ.get(name)
    if from_env is not None and from_env.strip():
        return from_env.strip()
    return dotenv.get(name, "").strip()


def key_status(name: str, dotenv: dict[str, str]) -> str:
    return "set" if resolved_key(name, dotenv) else "empty"


def experiment_env(dotenv: dict[str, str]) -> dict[str, str]:
    env = os.environ.copy()
    for name in TRACKED_KEYS:
        value = resolved_key(name, dotenv)
        if value:
            env[name] = value
    return env


def report_api_keys(dotenv: dict[str, str]) -> None:
    print("API keys (values not shown):", flush=True)
    for name in TRACKED_KEYS:
        print(f"  {name}: {key_status(name, dotenv)}", flush=True)
    print(flush=True)


def resolve_command(command: list[str]) -> list[str]:
    if not command:
        return command
    executable = command[0]
    if sys.platform == "win32" and executable == "npm":
        npm_cmd = shutil.which("npm.cmd") or shutil.which("npm")
        if npm_cmd:
            return [npm_cmd, *command[1:]]
    return command


def run_step(title: str, command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> int:
    command = resolve_command(command)
    print(f"== {title} ==", flush=True)
    print(f"$ {' '.join(command)}", flush=True)
    print(f"  (cwd: {cwd})", flush=True)
    try:
        subprocess.run(command, cwd=cwd, env=env, check=True)
    except FileNotFoundError:
        print(f"command not found: {command[0]}", file=sys.stderr, flush=True)
        return 1
    except subprocess.CalledProcessError as error:
        return error.returncode if error.returncode is not None else 1
    print(flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run Ask quality checks (CI mirror): pytest, chat typecheck, public READMEs.",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="skip pip install -e \".[dev]\" in api/",
    )
    parser.add_argument(
        "--skip-experiment",
        action="store_true",
        help="skip python -m ask.experiment even when API keys are configured",
    )
    args = parser.parse_args(argv)

    root = repo_root()
    api_dir = root / "api"
    web_dir = root / "web"
    dotenv = parse_dotenv(root / ".env")
    report_api_keys(dotenv)

    python = sys.executable

    if not args.skip_install:
        code = run_step(
            "Install Ask with dev extras",
            [python, "-m", "pip", "install", "-e", ".[dev]"],
            cwd=api_dir,
        )
        if code != 0:
            return code

    pytest_env = os.environ.copy()
    pytest_env["OPENAI_API_KEY"] = ""
    code = run_step(
        "Ask pytest (CI mirror, extractive draft)",
        [python, "-m", "pytest"],
        cwd=api_dir,
        env=pytest_env,
    )
    if code != 0:
        return code

    code = run_step("Install chat shell dependencies", ["npm", "ci"], cwd=web_dir)
    if code != 0:
        return code

    code = run_step("Typecheck the chat shell", ["npm", "run", "typecheck"], cwd=web_dir)
    if code != 0:
        return code

    code = run_step(
        "Check public READMEs",
        [python, str(root / "scripts" / "check_public_readmes.py")],
        cwd=root,
    )
    if code != 0:
        return code

    openai_key = resolved_key("OPENAI_API_KEY", dotenv)
    langsmith_key = resolved_key("LANGSMITH_API_KEY", dotenv)
    if args.skip_experiment:
        print("== Ask Experiment (skipped via --skip-experiment) ==", flush=True)
        print(flush=True)
    elif openai_key and langsmith_key:
        code = run_step(
            "Ask Experiment (LangSmith, live OpenAI draft)",
            [python, "-m", "ask.experiment"],
            cwd=api_dir,
            env=experiment_env(dotenv),
        )
        if code != 0:
            return code
    else:
        print("== Ask Experiment (skipped) ==", flush=True)
        print(
            "  Requires OPENAI_API_KEY and LANGSMITH_API_KEY in the environment or .env.",
            flush=True,
        )
        print(flush=True)

    print("All quality checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
