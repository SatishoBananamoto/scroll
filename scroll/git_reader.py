"""Read structured data from git history."""

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

SEPARATOR = "---LORE_SEP---"


@dataclass
class Commit:
    hash: str
    short_hash: str
    author: str
    date: str
    message: str
    files_changed: list[str] = field(default_factory=list)


def read_git_log(repo_path: Path, max_commits: int = 100) -> list[Commit]:
    """Read git log from a repository.

    Returns list of Commit objects, newest first.
    """
    fmt = f"%H{SEPARATOR}%h{SEPARATOR}%an{SEPARATOR}%ai{SEPARATOR}%B{SEPARATOR}{SEPARATOR}"

    result = subprocess.run(
        ["git", "-C", str(repo_path), "log",
         f"--max-count={max_commits}",
         f"--format={fmt}"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git log failed: {result.stderr}")

    commits = []
    entries = result.stdout.split(f"{SEPARATOR}{SEPARATOR}")

    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split(SEPARATOR)
        if len(parts) < 5:
            continue

        commits.append(Commit(
            hash=parts[0].strip(),
            short_hash=parts[1].strip(),
            author=parts[2].strip(),
            date=parts[3].strip(),
            message=parts[4].strip(),
        ))

    return commits


def format_commits_for_extraction(commits: list[Commit]) -> str:
    """Format commits into a readable block for LLM extraction."""
    parts = []
    for c in commits:
        parts.append(
            f"[{c.short_hash}] {c.date[:10]} by {c.author}\n"
            f"Message: {c.message}"
        )
    return "\n\n".join(parts)
