"""Ingestion state tracking for incremental processing."""

import json
from pathlib import Path
from typing import Optional


STATE_FILE = "state.json"


def load_state(scroll_dir: Path) -> dict:
    """Load ingestion state. Returns empty dict if no state exists."""
    state_path = scroll_dir / STATE_FILE
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(scroll_dir: Path, state: dict) -> None:
    """Write ingestion state to disk."""
    state_path = scroll_dir / STATE_FILE
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def get_last_commit(scroll_dir: Path) -> Optional[str]:
    """Get the hash of the last processed commit, or None."""
    state = load_state(scroll_dir)
    return state.get("last_commit")


def get_processed_commits(scroll_dir: Path) -> set[str]:
    """Get the set of all processed commit hashes."""
    state = load_state(scroll_dir)
    return set(state.get("processed_commits", []))


def update_state(scroll_dir: Path, new_commits: list[str], last_commit: str) -> None:
    """Update state with newly processed commits."""
    state = load_state(scroll_dir)
    existing = set(state.get("processed_commits", []))
    existing.update(new_commits)
    state["processed_commits"] = sorted(existing)
    state["last_commit"] = last_commit
    state["commits_processed"] = len(existing)
    save_state(scroll_dir, state)


def get_processed_prs(scroll_dir: Path) -> set[int]:
    """Get the set of all processed PR numbers."""
    state = load_state(scroll_dir)
    return set(state.get("processed_prs", []))


def get_processed_issues(scroll_dir: Path) -> set[int]:
    """Get the set of all processed issue numbers."""
    state = load_state(scroll_dir)
    return set(state.get("processed_issues", []))


def update_state_prs(scroll_dir: Path, pr_numbers: list[int]) -> None:
    """Update state with newly processed PRs."""
    state = load_state(scroll_dir)
    existing = set(state.get("processed_prs", []))
    existing.update(pr_numbers)
    state["processed_prs"] = sorted(existing)
    save_state(scroll_dir, state)


def update_state_issues(scroll_dir: Path, issue_numbers: list[int]) -> None:
    """Update state with newly processed issues."""
    state = load_state(scroll_dir)
    existing = set(state.get("processed_issues", []))
    existing.update(issue_numbers)
    state["processed_issues"] = sorted(existing)
    save_state(scroll_dir, state)
