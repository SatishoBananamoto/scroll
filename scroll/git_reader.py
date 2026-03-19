"""Read structured data from git history."""

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

SEPARATOR = "---SCROLL_SEP---"


@dataclass
class Commit:
    hash: str
    short_hash: str
    author: str
    date: str
    message: str
    files_changed: list[str] = field(default_factory=list)


def read_git_log(
    repo_path: Path,
    max_commits: int = 100,
    since_commit: Optional[str] = None,
) -> list[Commit]:
    """Read git log from a repository.

    If since_commit is provided, only returns commits after that hash.
    Returns list of Commit objects, newest first.
    """
    fmt = f"%H{SEPARATOR}%h{SEPARATOR}%an{SEPARATOR}%ai{SEPARATOR}%B{SEPARATOR}{SEPARATOR}"

    cmd = ["git", "-C", str(repo_path), "log", f"--format={fmt}"]

    if since_commit:
        cmd.append(f"{since_commit}..HEAD")
    else:
        cmd.append(f"--max-count={max_commits}")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # Empty repo (no commits yet) — not an error
        if "does not have any commits" in result.stderr:
            return []
        # Invalid since_commit (e.g. force-pushed away) — fall back to max_commits
        if since_commit and "unknown revision" in result.stderr:
            return read_git_log(repo_path, max_commits, since_commit=None)
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
