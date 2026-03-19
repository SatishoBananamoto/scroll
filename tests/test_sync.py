"""Tests for scroll.sync — agent file injection."""

import tempfile
import subprocess
from pathlib import Path

from scroll.store import ScrollEntry
from scroll.sync import (
    build_scroll_section, inject_into_file,
    sync_to_agents, setup_git_hook,
    START_MARKER, END_MARKER,
)


def _make_entries():
    return [
        ScrollEntry(id="DEC-001", type="decision", date="2026-03-19",
                     title="Use gRPC", tags=["arch"],
                     body="## Context\nTest.\n\n## Choice\ngRPC.\n\n## Reasoning\nFast.\n\n## Alternatives Considered\nREST.",
                     confidence="high", source_commits=["abc"], project="test"),
    ]


def _make_scroll_dir(td):
    """Create a .scroll dir with one entry."""
    from scroll.store import save_entries
    scroll_dir = Path(td) / ".scroll"
    scroll_dir.mkdir()
    (scroll_dir / "entries").mkdir()
    save_entries([{
        "entry_type": "decision",
        "title": "Use gRPC",
        "tags": ["arch"],
        "body": "## Context\nTest.\n\n## Choice\ngRPC.\n\n## Reasoning\nFast.\n\n## Alternatives Considered\nREST.",
        "confidence": "high",
        "source_commits": ["abc"],
    }], scroll_dir, "test")
    return scroll_dir


# --- build_scroll_section ---

def test_section_has_markers():
    section = build_scroll_section(_make_entries(), "test")
    assert section.startswith(START_MARKER)
    assert section.endswith(END_MARKER)
    assert "DEC-001" in section


# --- inject_into_file ---

def test_inject_creates_new_file():
    with tempfile.TemporaryDirectory() as td:
        fp = Path(td) / "CLAUDE.md"
        changed, action = inject_into_file(fp, "test content")
        assert changed is True
        assert action == "created"
        assert fp.read_text() == "test content\n"


def test_inject_appends_to_existing():
    with tempfile.TemporaryDirectory() as td:
        fp = Path(td) / "CLAUDE.md"
        fp.write_text("# My Project\n\nExisting content.")
        changed, action = inject_into_file(fp, f"{START_MARKER}\nnew\n{END_MARKER}")
        assert changed is True
        assert action == "appended"
        content = fp.read_text()
        assert "Existing content." in content
        assert START_MARKER in content


def test_inject_replaces_existing_section():
    with tempfile.TemporaryDirectory() as td:
        fp = Path(td) / "CLAUDE.md"
        fp.write_text(f"# Project\n\n{START_MARKER}\nold content\n{END_MARKER}\n\nOther stuff.")
        changed, action = inject_into_file(fp, f"{START_MARKER}\nnew content\n{END_MARKER}")
        assert changed is True
        assert action == "updated"
        content = fp.read_text()
        assert "new content" in content
        assert "old content" not in content
        assert "Other stuff." in content


def test_inject_unchanged_when_identical():
    with tempfile.TemporaryDirectory() as td:
        fp = Path(td) / "CLAUDE.md"
        section = f"{START_MARKER}\ncontent\n{END_MARKER}"
        fp.write_text(f"# Project\n\n{section}\n")
        changed, action = inject_into_file(fp, section)
        assert changed is False
        assert action == "unchanged"


# --- sync_to_agents ---

def test_sync_creates_claude_md():
    with tempfile.TemporaryDirectory() as td:
        scroll_dir = _make_scroll_dir(td)
        results = sync_to_agents(Path(td), scroll_dir, ["claude"])
        assert len(results) == 1
        assert results[0][0] == "claude"
        assert results[0][2] == "created"
        assert (Path(td) / "CLAUDE.md").exists()


def test_sync_creates_cursorrules():
    with tempfile.TemporaryDirectory() as td:
        scroll_dir = _make_scroll_dir(td)
        results = sync_to_agents(Path(td), scroll_dir, ["cursor"])
        assert (Path(td) / ".cursorrules").exists()


def test_sync_creates_copilot_instructions():
    with tempfile.TemporaryDirectory() as td:
        scroll_dir = _make_scroll_dir(td)
        results = sync_to_agents(Path(td), scroll_dir, ["copilot"])
        assert (Path(td) / ".github" / "copilot-instructions.md").exists()


def test_sync_unknown_agent():
    with tempfile.TemporaryDirectory() as td:
        scroll_dir = _make_scroll_dir(td)
        results = sync_to_agents(Path(td), scroll_dir, ["vim"])
        assert "unknown" in results[0][2]


# --- setup_git_hook ---

def test_hook_creates_post_commit():
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        hooks_dir = repo / ".git" / "hooks"
        hooks_dir.mkdir(parents=True)

        success, msg = setup_git_hook(repo)
        assert success is True
        hook = hooks_dir / "post-commit"
        assert hook.exists()
        content = hook.read_text()
        assert "scroll" in content
        assert "sync" in content


def test_hook_appends_to_existing():
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        hooks_dir = repo / ".git" / "hooks"
        hooks_dir.mkdir(parents=True)
        (hooks_dir / "post-commit").write_text("#!/bin/sh\necho 'existing hook'\n")

        success, msg = setup_git_hook(repo)
        assert success is True
        assert "appended" in msg
        content = (hooks_dir / "post-commit").read_text()
        assert "existing hook" in content
        assert "scroll" in content


def test_hook_skips_if_already_installed():
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        hooks_dir = repo / ".git" / "hooks"
        hooks_dir.mkdir(parents=True)
        (hooks_dir / "post-commit").write_text("#!/bin/sh\n# scroll hook already here\n")

        success, msg = setup_git_hook(repo)
        assert success is False
        assert "already" in msg
