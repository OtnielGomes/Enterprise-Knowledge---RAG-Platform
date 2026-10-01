"""Fail when a public README names a local agent path or drops an official source URL.

The deny list is the .gitignore block under the ``# public-readme-deny`` sentinel.
A match inside an http(s) URL does not count, so official links that contain
``docs/`` stay valid. Every ``source_url`` in ``snapshot/manifest.json`` must
appear literally in both public READMEs.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SENTINEL = "# public-readme-deny"
READMES = ("README.md", "README.pt-BR.md")
MANIFEST_PATH = Path("snapshot/manifest.json")
URL_RE = re.compile(r"https?://[^\s)>\]\"']+")


class CheckError(Exception):
    """The guard cannot run because a required input is missing or malformed."""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def deny_patterns(gitignore: str) -> list[str]:
    lines = gitignore.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == SENTINEL)
    except StopIteration as exc:
        raise CheckError(f".gitignore is missing the {SENTINEL} marker") from exc

    patterns: list[str] = []
    for line in lines[start + 1 :]:
        stripped = line.strip()
        if stripped == "" or stripped.startswith("#"):
            break
        patterns.append(stripped)
    if not patterns:
        raise CheckError(f"{SENTINEL} block is empty")
    return patterns


def source_urls(manifest: object) -> list[str]:
    if not isinstance(manifest, dict):
        raise CheckError("snapshot/manifest.json must be an object")
    acts = manifest.get("acts")
    if not isinstance(acts, list) or not acts:
        raise CheckError("snapshot/manifest.json has no acts")

    urls: list[str] = []
    for act in acts:
        if not isinstance(act, dict):
            raise CheckError("a manifest act must be an object")
        url = act.get("source_url")
        identity = act.get("id", "?")
        if not isinstance(url, str) or not url.strip():
            raise CheckError(f"act {identity} is missing source_url")
        urls.append(url)
    return urls


def _url_spans(text: str) -> list[tuple[int, int]]:
    return [(match.start(), match.end()) for match in URL_RE.finditer(text)]


def _inside_url(index: int, spans: list[tuple[int, int]]) -> bool:
    return any(start <= index < end for start, end in spans)


def outside_hits(text: str, pattern: str) -> list[int]:
    spans = _url_spans(text)
    hits: list[int] = []
    start = 0
    while True:
        index = text.find(pattern, start)
        if index < 0:
            return hits
        if not _inside_url(index, spans):
            hits.append(index)
        start = index + len(pattern)


def line_number(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def violations(readme_name: str, text: str, patterns: list[str], urls: list[str]) -> list[str]:
    found: list[str] = []
    for pattern in patterns:
        for index in outside_hits(text, pattern):
            found.append(
                f"{readme_name}:{line_number(text, index)}: names local path {pattern!r}"
            )
    for url in urls:
        if url not in text:
            found.append(f"{readme_name}: missing source_url {url}")
    return found


def check(root: Path) -> list[str]:
    gitignore_path = root / ".gitignore"
    if not gitignore_path.is_file():
        raise CheckError(".gitignore is missing")
    patterns = deny_patterns(gitignore_path.read_text(encoding="utf-8"))

    manifest_path = root / MANIFEST_PATH
    if not manifest_path.is_file():
        raise CheckError("snapshot/manifest.json is missing")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CheckError(f"snapshot/manifest.json is not valid JSON: {exc}") from exc
    urls = source_urls(manifest)

    found: list[str] = []
    for name in READMES:
        path = root / name
        if not path.is_file():
            found.append(f"{name}: missing")
            continue
        found.extend(violations(name, path.read_text(encoding="utf-8"), patterns, urls))
    return found


def main() -> int:
    try:
        found = check(repo_root())
    except CheckError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if found:
        print("\n".join(found), file=sys.stderr)
        return 1
    print("public readmes ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
