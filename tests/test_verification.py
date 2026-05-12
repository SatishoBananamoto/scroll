"""Tests for extraction source verification."""

from scroll.verification import verify_extractions


def _entry(source_refs=None, title="Use incremental commits"):
    return {
        "entry_type": "learning",
        "title": title,
        "tags": ["git", "process"],
        "body": (
            "## Context\nGit history used small commits.\n\n"
            "## What Happened\nIncremental commits made recovery easier.\n\n"
            "## Insight\nKeep commits focused.\n\n"
            "## Applies To\nDevelopment workflows."
        ),
        "confidence": "medium",
        "source_commits": source_refs or ["abc1234"],
    }


def test_accepts_entry_when_commit_ref_is_in_source():
    source = "[abc1234] 2026-03-19 by Test\nMessage: Use incremental commits"

    report = verify_extractions([_entry()], source)

    assert len(report.accepted) == 1
    assert report.rejected == []


def test_rejects_entry_when_commit_ref_is_missing_from_source():
    source = "[abc1234] 2026-03-19 by Test\nMessage: Use incremental commits"

    report = verify_extractions([_entry(["deadbeef"])], source)

    assert report.accepted == []
    assert len(report.rejected) == 1
    assert "not present" in report.rejected[0]["_errors"][0]


def test_accepts_pr_and_issue_refs_from_formatted_github_sources():
    source = (
        "=== PR #42: Add import flow ===\n"
        "Description:\nAdded importer.\n\n"
        "=== Issue #7: Broken state ===\n"
        "Description:\nState recovery failed."
    )

    report = verify_extractions([
        _entry(["PR#42"], "Add import flow"),
        _entry(["I#7"], "Fix state recovery"),
    ], source)

    assert len(report.accepted) == 2
    assert report.rejected == []


def test_low_overlap_is_warning_not_rejection():
    source = "[abc1234] 2026-03-19 by Test\nMessage: Add retry state"

    report = verify_extractions([_entry(["abc1234"], "Unrelated payment strategy")], source)

    assert len(report.accepted) == 1
    assert len(report.warnings) == 1
    assert report.warnings[0].kind == "low-source-overlap"
