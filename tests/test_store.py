"""Tests for scroll.store — validation, dedup, ID assignment, roundtrip."""

import tempfile
from pathlib import Path

from scroll.store import (
    ScrollEntry, ValidationError,
    validate_entry, is_duplicate, normalize_title,
    get_next_id, entry_to_markdown, parse_scroll_entry,
    save_entries, load_entries,
)


def make_valid_entry(**overrides):
    """Create a valid extracted entry dict."""
    base = {
        "entry_type": "decision",
        "title": "Switch from REST to gRPC",
        "tags": ["architecture", "grpc"],
        "body": "## Context\nNeeded faster API.\n\n## Choice\ngRPC.\n\n## Reasoning\nLower latency.\n\n## Alternatives Considered\nREST, GraphQL.",
        "confidence": "high",
        "source_commits": ["abc1234"],
    }
    base.update(overrides)
    return base


# --- validate_entry ---

def test_valid_entry_passes():
    errors = validate_entry(make_valid_entry())
    assert errors == []


def test_invalid_type_rejected():
    errors = validate_entry(make_valid_entry(entry_type="poem"))
    assert any(e.field == "entry_type" for e in errors)


def test_empty_title_rejected():
    errors = validate_entry(make_valid_entry(title=""))
    assert any(e.field == "title" for e in errors)


def test_empty_tags_rejected():
    errors = validate_entry(make_valid_entry(tags=[]))
    assert any(e.field == "tags" for e in errors)


def test_empty_body_rejected():
    errors = validate_entry(make_valid_entry(body=""))
    assert any(e.field == "body" for e in errors)


def test_body_without_sections_rejected():
    errors = validate_entry(make_valid_entry(body="Just some text without headers."))
    assert any(e.field == "body" for e in errors)


def test_invalid_confidence_rejected():
    errors = validate_entry(make_valid_entry(confidence="very high"))
    assert any(e.field == "confidence" for e in errors)


def test_no_source_commits_rejected():
    errors = validate_entry(make_valid_entry(source_commits=[]))
    assert any(e.field == "source_commits" for e in errors)


# --- normalize_title ---

def test_normalize_title_strips_punctuation():
    assert normalize_title("Switch from REST to gRPC!") == "switch from rest to grpc"


def test_normalize_title_handles_empty():
    assert normalize_title("") == ""


# --- is_duplicate ---

def test_duplicate_detected_by_title():
    existing = [ScrollEntry(
        id="DEC-001", type="decision", date="2026-03-19",
        title="Switch from REST to gRPC", tags=["arch"], body="...",
    )]
    raw = make_valid_entry(title="Switch from REST to gRPC!")
    assert is_duplicate(raw, existing) is True


def test_duplicate_detected_by_source_commits():
    existing = [ScrollEntry(
        id="DEC-001", type="decision", date="2026-03-19",
        title="Different title", tags=["arch"], body="...",
        source_commits=["abc1234", "def5678"],
    )]
    raw = make_valid_entry(title="Totally new title", source_commits=["abc1234"])
    assert is_duplicate(raw, existing) is True


def test_not_duplicate_with_different_content():
    existing = [ScrollEntry(
        id="DEC-001", type="decision", date="2026-03-19",
        title="Switch from REST to gRPC", tags=["arch"], body="...",
        source_commits=["abc1234"],
    )]
    raw = make_valid_entry(title="Add authentication middleware", source_commits=["xyz9999"])
    assert is_duplicate(raw, existing) is False


# --- get_next_id ---

def test_first_id_is_001():
    with tempfile.TemporaryDirectory() as td:
        entries_dir = Path(td)
        assert get_next_id(entries_dir, "decision") == "DEC-001"


def test_increments_from_existing():
    with tempfile.TemporaryDirectory() as td:
        entries_dir = Path(td)
        (entries_dir / "DEC-001.md").touch()
        (entries_dir / "DEC-002.md").touch()
        assert get_next_id(entries_dir, "decision") == "DEC-003"


def test_different_types_independent():
    with tempfile.TemporaryDirectory() as td:
        entries_dir = Path(td)
        (entries_dir / "DEC-001.md").touch()
        assert get_next_id(entries_dir, "learning") == "LRN-001"


# --- markdown roundtrip ---

def test_markdown_roundtrip():
    entry = ScrollEntry(
        id="DEC-001", type="decision", date="2026-03-19",
        title="Use gRPC", tags=["arch", "api"], body="## Context\nTest body.",
        confidence="high", source_commits=["abc1234"], project="myproject",
    )
    md = entry_to_markdown(entry)
    parsed = parse_scroll_entry(md)

    assert parsed is not None
    assert parsed.id == "DEC-001"
    assert parsed.type == "decision"
    assert parsed.title == "Use gRPC"
    assert parsed.tags == ["arch", "api"]
    assert parsed.confidence == "high"
    assert parsed.source_commits == ["abc1234"]
    assert parsed.project == "myproject"
    assert "## Context" in parsed.body


def test_parse_returns_none_for_bad_input():
    assert parse_scroll_entry("no frontmatter here") is None


# --- save_entries with validation + dedup ---

def test_save_rejects_invalid_and_duplicates():
    with tempfile.TemporaryDirectory() as td:
        scroll_dir = Path(td)
        (scroll_dir / "entries").mkdir()

        entries = [
            make_valid_entry(title="Good entry"),
            make_valid_entry(title="", confidence="high"),  # invalid: empty title
            make_valid_entry(title="Good entry"),  # duplicate of first
        ]

        saved, invalid, duplicate = save_entries(entries, scroll_dir, "test")
        assert len(saved) == 1
        assert len(invalid) == 1
        assert len(duplicate) == 1
        assert saved[0].title == "Good entry"


def test_load_entries_from_disk():
    with tempfile.TemporaryDirectory() as td:
        scroll_dir = Path(td)
        entries_dir = scroll_dir / "entries"
        entries_dir.mkdir()

        saved, _, _ = save_entries([make_valid_entry()], scroll_dir, "test")
        loaded = load_entries(scroll_dir)

        assert len(loaded) == 1
        assert loaded[0].id == saved[0].id
        assert loaded[0].title == saved[0].title
