"""Tests for scroll.relevance."""

from scroll.store import ScrollEntry
from scroll.relevance import extract_keywords, score_entry, find_relevant


def _entries():
    return [
        ScrollEntry(id="DEC-001", type="decision", date="2026-03-19",
                     title="Switch authentication from JWT to session cookies",
                     tags=["auth", "jwt", "cookies", "security"],
                     body="## Context\nMobile clients couldn't store JWT.\n\n## Choice\nSession cookies."),
        ScrollEntry(id="MST-001", type="mistake", date="2026-03-19",
                     title="Hook output used wrong JSON format",
                     tags=["hooks", "json", "claude-code"],
                     body="## Context\nIntegrating with Claude Code.\n\n## What Went Wrong\nSilently ignored."),
        ScrollEntry(id="LRN-001", type="learning", date="2026-03-19",
                     title="gRPC requires HTTP/2 for streaming",
                     tags=["grpc", "http2", "networking"],
                     body="## Context\nMigrating API.\n\n## Insight\nHTTP/2 is required."),
    ]


def test_extract_keywords_filters_stopwords():
    kw = extract_keywords("add a new authentication check for mobile clients")
    assert "authentication" in kw
    assert "mobile" in kw
    assert "clients" in kw
    assert "add" not in kw
    assert "a" not in kw
    assert "new" not in kw


def test_extract_keywords_handles_empty():
    assert extract_keywords("") == set()
    assert extract_keywords("a the is") == set()


def test_score_entry_title_match():
    entries = _entries()
    score = score_entry(entries[0], {"authentication", "jwt"})
    assert score > 0


def test_score_entry_tag_match():
    entries = _entries()
    score = score_entry(entries[0], {"security"})
    assert score >= 2.0  # Tag match = 2 points


def test_score_entry_no_match():
    entries = _entries()
    score = score_entry(entries[2], {"authentication", "jwt"})
    assert score == 0


def test_find_relevant_ranks_correctly():
    entries = _entries()
    results = find_relevant(entries, "authentication JWT mobile session")
    assert len(results) > 0
    # DEC-001 should rank first — matches title, tags, and body
    assert results[0][0].id == "DEC-001"


def test_find_relevant_respects_top_k():
    entries = _entries()
    results = find_relevant(entries, "authentication JWT", top_k=1)
    assert len(results) <= 1


def test_find_relevant_respects_min_score():
    entries = _entries()
    results = find_relevant(entries, "authentication", min_score=100.0)
    assert results == []
