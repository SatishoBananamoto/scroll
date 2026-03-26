"""Tests for scroll.deposit — scroll → engram knowledge transfer."""

import json
import tempfile
from datetime import date
from pathlib import Path

import pytest

from scroll.deposit import (
    DepositResult,
    deposit,
    find_max_engram_num,
    load_deposit_state,
    render_engram_entry,
    save_deposit_state,
)
from scroll.store import ScrollEntry, entry_to_markdown


# --- Helpers ---

def make_scroll_entry(
    id="DEC-001", type="decision", title="Use gRPC", tags=None,
    body="## Context\nNeeded fast RPC.\n\n## Choice\ngRPC.",
    confidence="high", source_commits=None, project="myapi",
):
    return ScrollEntry(
        id=id, type=type, date="2026-03-20", title=title,
        tags=tags or ["architecture"], body=body, status="active",
        confidence=confidence,
        source_commits=source_commits if source_commits is not None else ["abc1234"],
        project=project,
    )


def setup_scroll_dir(tmp: Path, entries: list[ScrollEntry]) -> Path:
    """Create a .scroll directory with entries."""
    scroll_dir = tmp / ".scroll"
    entries_dir = scroll_dir / "entries"
    entries_dir.mkdir(parents=True)

    for entry in entries:
        md = entry_to_markdown(entry)
        (entries_dir / f"{entry.id}.md").write_text(md)

    return scroll_dir


def setup_engram_dir(tmp: Path, existing_files: dict[str, str] = None) -> Path:
    """Create an engram directory with optional existing entries."""
    engram = tmp / "engram"
    entries_dir = engram / "entries"
    entries_dir.mkdir(parents=True)

    if existing_files:
        for name, content in existing_files.items():
            (entries_dir / name).write_text(content)

    return engram


MINIMAL_ENGRAM_ENTRY = """---
id: {id}
type: {type}
date: 2026-03-15
tags: [test]
status: active
confidence: medium
project: existing
---

# Existing entry

## Context
Already here.
"""


# --- Tests: find_max_engram_num ---

class TestFindMaxEngramNum:

    def test_empty_directory(self, tmp_path):
        entries_dir = tmp_path / "entries"
        entries_dir.mkdir()
        assert find_max_engram_num(entries_dir, "decision") == 0

    def test_finds_max(self, tmp_path):
        entries_dir = tmp_path / "entries"
        entries_dir.mkdir()
        for n in [1, 3, 7]:
            (entries_dir / f"DEC-{n:03d}.md").write_text("x")
        assert find_max_engram_num(entries_dir, "decision") == 7

    def test_ignores_other_types(self, tmp_path):
        entries_dir = tmp_path / "entries"
        entries_dir.mkdir()
        (entries_dir / "LRN-050.md").write_text("x")
        (entries_dir / "DEC-003.md").write_text("x")
        assert find_max_engram_num(entries_dir, "decision") == 3
        assert find_max_engram_num(entries_dir, "learning") == 50

    def test_ignores_malformed_filenames(self, tmp_path):
        entries_dir = tmp_path / "entries"
        entries_dir.mkdir()
        (entries_dir / "DEC-abc.md").write_text("x")
        (entries_dir / "DEC-002.md").write_text("x")
        (entries_dir / "README.md").write_text("x")
        assert find_max_engram_num(entries_dir, "decision") == 2


# --- Tests: render_engram_entry ---

class TestRenderEngramEntry:

    def test_basic_rendering(self):
        entry = make_scroll_entry()
        result = render_engram_entry(entry, "DEC-042")

        assert "id: DEC-042" in result
        assert "type: decision" in result
        assert "date: 2026-03-20" in result
        assert "source: scroll" in result
        assert "scroll-extracted" in result
        assert "architecture" in result
        assert "# Use gRPC" in result
        assert "project: myapi" in result
        assert "confidence: high" in result

    def test_adds_scroll_extracted_tag(self):
        entry = make_scroll_entry(tags=["grpc", "api"])
        result = render_engram_entry(entry, "DEC-001")
        assert "scroll-extracted" in result

    def test_no_duplicate_scroll_tag(self):
        entry = make_scroll_entry(tags=["grpc", "scroll-extracted"])
        result = render_engram_entry(entry, "DEC-001")
        assert result.count("scroll-extracted") == 1

    def test_source_provenance(self):
        entry = make_scroll_entry(source_commits=["abc1234", "def5678"])
        result = render_engram_entry(entry, "DEC-001")
        assert "## Source" in result
        assert "abc1234" in result
        assert "def5678" in result
        assert "Original scroll ID: DEC-001" in result

    def test_no_source_section_without_commits(self):
        entry = make_scroll_entry(source_commits=[])
        result = render_engram_entry(entry, "DEC-001")
        assert "## Source" not in result

    def test_no_source_commits_in_frontmatter(self):
        """Engram doesn't recognize source_commits — must not be in frontmatter."""
        entry = make_scroll_entry()
        result = render_engram_entry(entry, "DEC-001")
        # Split at the closing --- to get just the frontmatter
        parts = result.split("---")
        frontmatter = parts[1]  # between first and second ---
        assert "source_commits" not in frontmatter

    def test_no_project_when_none(self):
        entry = make_scroll_entry(project=None)
        result = render_engram_entry(entry, "DEC-001")
        assert "project:" not in result


# --- Tests: deposit state ---

class TestDepositState:

    def test_empty_state(self, tmp_path):
        state = load_deposit_state(tmp_path)
        assert state == {}

    def test_roundtrip(self, tmp_path):
        mapping = {"DEC-001": "DEC-042", "LRN-003": "LRN-019"}
        save_deposit_state(tmp_path, mapping)
        loaded = load_deposit_state(tmp_path)
        assert loaded == mapping

    def test_state_file_format(self, tmp_path):
        save_deposit_state(tmp_path, {"DEC-001": "DEC-042"})
        data = json.loads((tmp_path / "deposit_state.json").read_text())
        assert "deposited" in data
        assert "last_deposit" in data
        assert data["last_deposit"] == date.today().isoformat()


# --- Tests: full deposit flow ---

class TestDeposit:

    def test_deposit_single_entry(self, tmp_path):
        entry = make_scroll_entry(id="DEC-001")
        scroll_dir = setup_scroll_dir(tmp_path, [entry])
        engram = setup_engram_dir(tmp_path)

        result = deposit(scroll_dir, engram_root=engram)

        assert len(result.deposited) == 1
        assert result.deposited[0] == ("DEC-001", "DEC-001")
        assert not result.skipped
        assert not result.errors

        # Verify file was written
        written = engram / "entries" / "DEC-001.md"
        assert written.exists()
        content = written.read_text()
        assert "id: DEC-001" in content
        assert "scroll-extracted" in content

    def test_deposit_continues_from_existing_ids(self, tmp_path):
        entry = make_scroll_entry(id="DEC-001")
        scroll_dir = setup_scroll_dir(tmp_path, [entry])
        engram = setup_engram_dir(tmp_path, {
            "DEC-005.md": MINIMAL_ENGRAM_ENTRY.format(id="DEC-005", type="decision"),
        })

        result = deposit(scroll_dir, engram_root=engram)

        assert result.deposited[0] == ("DEC-001", "DEC-006")
        assert (engram / "entries" / "DEC-006.md").exists()

    def test_deposit_multiple_types(self, tmp_path):
        entries = [
            make_scroll_entry(id="DEC-001", type="decision", title="Decision A"),
            make_scroll_entry(id="LRN-001", type="learning", title="Learning A",
                              body="## Context\nX\n\n## What Happened\nY\n\n## Insight\nZ\n\n## Applies To\nAll"),
            make_scroll_entry(id="MST-001", type="mistake", title="Mistake A",
                              body="## Context\nX\n\n## What Went Wrong\nY\n\n## Root Cause\nZ\n\n## Prevention\nDon't"),
        ]
        scroll_dir = setup_scroll_dir(tmp_path, entries)
        engram = setup_engram_dir(tmp_path)

        result = deposit(scroll_dir, engram_root=engram)

        assert len(result.deposited) == 3
        ids = {engram_id for _, engram_id in result.deposited}
        assert "DEC-001" in ids
        assert "LRN-001" in ids
        assert "MST-001" in ids

    def test_deposit_batch_id_increment(self, tmp_path):
        """Two entries of the same type should get sequential IDs."""
        entries = [
            make_scroll_entry(id="DEC-001", title="Decision A"),
            make_scroll_entry(id="DEC-002", title="Decision B"),
        ]
        scroll_dir = setup_scroll_dir(tmp_path, entries)
        engram = setup_engram_dir(tmp_path, {
            "DEC-010.md": MINIMAL_ENGRAM_ENTRY.format(id="DEC-010", type="decision"),
        })

        result = deposit(scroll_dir, engram_root=engram)

        assert len(result.deposited) == 2
        assert result.deposited[0] == ("DEC-001", "DEC-011")
        assert result.deposited[1] == ("DEC-002", "DEC-012")

    def test_skips_already_deposited(self, tmp_path):
        entries = [
            make_scroll_entry(id="DEC-001", title="Already done"),
            make_scroll_entry(id="LRN-001", type="learning", title="New one",
                              body="## Context\nX\n\n## Insight\nY"),
        ]
        scroll_dir = setup_scroll_dir(tmp_path, entries)
        engram = setup_engram_dir(tmp_path)

        # Pre-populate deposit state
        save_deposit_state(scroll_dir, {"DEC-001": "DEC-042"})

        result = deposit(scroll_dir, engram_root=engram)

        assert len(result.deposited) == 1
        assert result.deposited[0][0] == "LRN-001"
        assert result.skipped == ["DEC-001"]

    def test_dry_run_writes_nothing(self, tmp_path):
        entry = make_scroll_entry(id="DEC-001")
        scroll_dir = setup_scroll_dir(tmp_path, [entry])
        engram = setup_engram_dir(tmp_path)

        result = deposit(scroll_dir, engram_root=engram, dry_run=True)

        assert len(result.deposited) == 1
        # No files written
        assert not list((engram / "entries").glob("DEC-*.md"))
        # No state saved
        assert not (scroll_dir / "deposit_state.json").exists()

    def test_project_filter(self, tmp_path):
        entries = [
            make_scroll_entry(id="DEC-001", project="alpha"),
            make_scroll_entry(id="DEC-002", project="beta"),
        ]
        scroll_dir = setup_scroll_dir(tmp_path, entries)
        engram = setup_engram_dir(tmp_path)

        result = deposit(scroll_dir, engram_root=engram, project_filter="alpha")

        assert len(result.deposited) == 1
        assert result.deposited[0][0] == "DEC-001"

    def test_error_missing_engram(self, tmp_path):
        entry = make_scroll_entry(id="DEC-001")
        scroll_dir = setup_scroll_dir(tmp_path, [entry])
        fake_engram = tmp_path / "nonexistent"

        result = deposit(scroll_dir, engram_root=fake_engram)

        assert len(result.errors) == 1
        assert "not found" in result.errors[0]

    def test_empty_scroll_dir(self, tmp_path):
        scroll_dir = tmp_path / ".scroll"
        (scroll_dir / "entries").mkdir(parents=True)
        engram = setup_engram_dir(tmp_path)

        result = deposit(scroll_dir, engram_root=engram)

        assert not result.deposited
        assert not result.skipped
        assert not result.errors

    def test_state_persists_across_deposits(self, tmp_path):
        """Second deposit should skip entries from the first."""
        entries = [make_scroll_entry(id="DEC-001")]
        scroll_dir = setup_scroll_dir(tmp_path, entries)
        engram = setup_engram_dir(tmp_path)

        # First deposit
        r1 = deposit(scroll_dir, engram_root=engram)
        assert len(r1.deposited) == 1

        # Second deposit — same entries
        r2 = deposit(scroll_dir, engram_root=engram)
        assert len(r2.deposited) == 0
        assert r2.skipped == ["DEC-001"]

    def test_engram_entry_parseable(self, tmp_path):
        """Deposited entries must parse correctly with engram's parser."""
        entry = make_scroll_entry(
            id="DEC-001", title="Test Decision",
            tags=["testing", "integration"],
            body="## Context\nTest.\n\n## Choice\nDo it.\n\n## Reasoning\nWhy not.",
            confidence="high", project="scroll",
        )
        scroll_dir = setup_scroll_dir(tmp_path, [entry])
        engram = setup_engram_dir(tmp_path)

        deposit(scroll_dir, engram_root=engram)

        # Parse with engram's own parser
        import sys
        sys.path.insert(0, str(Path.home() / "engram"))
        from tools.parser import parse_entry

        written = engram / "entries" / "DEC-001.md"
        parsed, errors = parse_entry(written)

        assert parsed is not None, f"Parse errors: {errors}"
        assert parsed.id == "DEC-001"
        assert parsed.type == "decision"
        assert parsed.source == "scroll"
        assert "scroll-extracted" in parsed.tags
        assert parsed.project == "scroll"
        assert parsed.confidence == "high"
