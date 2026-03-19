"""Tests for scroll.state — ingestion state tracking."""

import tempfile
from pathlib import Path

from scroll.state import (
    load_state, save_state, get_last_commit,
    get_processed_commits, update_state,
)


def test_empty_state_on_fresh_dir():
    with tempfile.TemporaryDirectory() as td:
        assert load_state(Path(td)) == {}


def test_save_and_load_roundtrip():
    with tempfile.TemporaryDirectory() as td:
        scroll_dir = Path(td)
        state = {"last_commit": "abc123", "commits_processed": 5}
        save_state(scroll_dir, state)
        loaded = load_state(scroll_dir)
        assert loaded["last_commit"] == "abc123"
        assert loaded["commits_processed"] == 5


def test_get_last_commit_none_when_fresh():
    with tempfile.TemporaryDirectory() as td:
        assert get_last_commit(Path(td)) is None


def test_get_processed_commits_empty_when_fresh():
    with tempfile.TemporaryDirectory() as td:
        assert get_processed_commits(Path(td)) == set()


def test_update_state_accumulates():
    with tempfile.TemporaryDirectory() as td:
        scroll_dir = Path(td)

        update_state(scroll_dir, ["aaa", "bbb"], "bbb")
        assert get_last_commit(scroll_dir) == "bbb"
        assert get_processed_commits(scroll_dir) == {"aaa", "bbb"}

        update_state(scroll_dir, ["ccc"], "ccc")
        assert get_last_commit(scroll_dir) == "ccc"
        assert get_processed_commits(scroll_dir) == {"aaa", "bbb", "ccc"}


def test_update_state_deduplicates():
    with tempfile.TemporaryDirectory() as td:
        scroll_dir = Path(td)

        update_state(scroll_dir, ["aaa", "bbb"], "bbb")
        update_state(scroll_dir, ["aaa", "ccc"], "ccc")

        processed = get_processed_commits(scroll_dir)
        assert len(processed) == 3  # aaa, bbb, ccc — not 4
