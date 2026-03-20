"""Tests for scroll.integrity — health scoring and knowledge quality."""

from datetime import date, timedelta

from scroll.store import ScrollEntry
from scroll.integrity import (
    check_staleness, check_sections, check_low_confidence,
    check_duplicate_titles, compute_health, render_health,
    STALENESS_THRESHOLDS,
)


def _entry(**overrides):
    base = dict(
        id="DEC-001", type="decision", date=date.today().isoformat(),
        title="Use gRPC", tags=["arch"],
        body="## Context\nTest.\n\n## Choice\ngRPC.\n\n## Reasoning\nFast.\n\n## Alternatives Considered\nREST.",
        confidence="high", source_commits=["abc"], project="test",
    )
    base.update(overrides)
    return ScrollEntry(**base)


# --- check_staleness ---

def test_fresh_entry_not_stale():
    entries = [_entry()]
    assert check_staleness(entries) == []


def test_old_decision_is_stale():
    old_date = (date.today() - timedelta(days=100)).isoformat()
    entries = [_entry(date=old_date)]
    stale = check_staleness(entries)
    assert len(stale) == 1
    assert stale[0][1] == 100


def test_old_learning_not_stale_within_threshold():
    # Learnings have 180-day threshold
    old_date = (date.today() - timedelta(days=100)).isoformat()
    entries = [_entry(id="LRN-001", type="learning", date=old_date,
               body="## Context\nX.\n\n## What Happened\nY.\n\n## Insight\nZ.\n\n## Applies To\nW.")]
    assert check_staleness(entries) == []


# --- check_sections ---

def test_complete_entry_has_no_missing_sections():
    entries = [_entry()]
    assert check_sections(entries) == []


def test_missing_sections_detected():
    entries = [_entry(body="## Context\nJust context, nothing else.")]
    issues = check_sections(entries)
    assert len(issues) == 1
    assert "## Choice" in issues[0][1]
    assert "## Reasoning" in issues[0][1]


# --- check_low_confidence ---

def test_high_confidence_not_flagged():
    assert check_low_confidence([_entry()]) == []


def test_low_confidence_flagged():
    entries = [_entry(confidence="low")]
    assert len(check_low_confidence(entries)) == 1


# --- check_duplicate_titles ---

def test_no_duplicates():
    entries = [_entry(id="DEC-001", title="One"), _entry(id="DEC-002", title="Two")]
    assert check_duplicate_titles(entries) == []


def test_duplicate_titles_detected():
    entries = [
        _entry(id="DEC-001", title="Use gRPC for APIs"),
        _entry(id="DEC-002", title="Use gRPC for APIs!"),
    ]
    dupes = check_duplicate_titles(entries)
    assert len(dupes) == 1
    assert len(dupes[0][1]) == 2


# --- compute_health ---

def test_healthy_base_scores_high():
    entries = [
        _entry(id="DEC-001", type="decision"),
        _entry(id="LRN-001", type="learning",
               body="## Context\nX.\n\n## What Happened\nY.\n\n## Insight\nZ.\n\n## Applies To\nW."),
        _entry(id="MST-001", type="mistake",
               body="## Context\nX.\n\n## What Went Wrong\nY.\n\n## Root Cause\nZ.\n\n## Prevention\nW."),
        _entry(id="OBS-001", type="observation",
               body="## Context\nX.\n\n## Observation\nY.\n\n## Significance\nZ."),
        _entry(id="GOL-001", type="goal",
               body="## Objective\nX.\n\n## Success Criteria\nY.\n\n## Current Status\nZ."),
    ]
    report = compute_health(entries)
    assert report.score >= 90
    assert report.is_healthy


def test_empty_scores_zero():
    report = compute_health([])
    assert report.score == 0
    assert not report.is_healthy


def test_all_stale_scores_low():
    old = (date.today() - timedelta(days=200)).isoformat()
    entries = [_entry(date=old)]
    report = compute_health(entries)
    assert report.score < 80


def test_all_low_confidence_scores_low():
    entries = [_entry(confidence="low")]
    report = compute_health(entries)
    assert report.score < 90


# --- render_health ---

def test_render_includes_score():
    entries = [_entry()]
    report = compute_health(entries)
    text = render_health(report)
    assert "Health:" in text
    assert "/100" in text


def test_render_empty():
    report = compute_health([])
    text = render_health(report)
    assert "No entries" in text
