"""Tests for scroll.github_reader — PR and issue formatting."""

from scroll.github_reader import (
    PullRequest, Issue,
    format_prs_for_extraction, format_issues_for_extraction,
)


def test_format_pr_basic():
    pr = PullRequest(
        number=42, title="Switch auth from JWT to cookies",
        body="JWT was unreliable on mobile.\n\nSession cookies handle it.",
        author="jane", created_at="2025-06-15", merged_at="2025-06-16",
        labels=["breaking-change"], files_changed=["auth/middleware.py"],
        comments=[], reviews=[],
    )
    text = format_prs_for_extraction([pr])
    assert "PR #42" in text
    assert "Switch auth" in text
    assert "jane" in text
    assert "JWT was unreliable" in text
    assert "breaking-change" in text
    assert "auth/middleware.py" in text


def test_format_pr_with_reviews():
    pr = PullRequest(
        number=10, title="Add caching layer",
        body="Performance optimization.", author="bob",
        created_at="2025-01-01", merged_at="2025-01-02",
        reviews=[
            {"author": "carol", "body": "Have you considered Redis?", "state": "CHANGES_REQUESTED", "date": "2025-01-01"},
            {"author": "bob", "body": "Switched to Redis, good call.", "state": "APPROVED", "date": "2025-01-02"},
        ],
        comments=[],
    )
    text = format_prs_for_extraction([pr])
    assert "@carol" in text
    assert "Redis" in text
    assert "CHANGES_REQUESTED" in text


def test_format_pr_with_comments():
    pr = PullRequest(
        number=5, title="Fix login bug",
        body="Users couldn't log in.", author="alice",
        created_at="2025-03-01", merged_at="2025-03-01",
        comments=[
            {"author": "dave", "body": "This also fixes #12", "date": "2025-03-01"},
        ],
        reviews=[],
    )
    text = format_prs_for_extraction([pr])
    assert "@dave" in text
    assert "fixes #12" in text


def test_format_pr_truncates_long_body():
    pr = PullRequest(
        number=1, title="Big PR",
        body="x" * 3000, author="test",
        created_at="2025-01-01", merged_at="2025-01-01",
    )
    text = format_prs_for_extraction([pr])
    assert "[... truncated]" in text


def test_format_issue_basic():
    issue = Issue(
        number=15, title="Login page crashes on Safari",
        body="Steps to reproduce:\n1. Open Safari\n2. Click login\n3. Crash",
        author="user1", created_at="2025-04-01",
        labels=["bug", "critical"],
        comments=[
            {"author": "dev1", "body": "Fixed in PR #42", "date": "2025-04-02"},
        ],
    )
    text = format_issues_for_extraction([issue])
    assert "Issue #15" in text
    assert "Safari" in text
    assert "bug" in text
    assert "Fixed in PR #42" in text


def test_format_issue_empty_body():
    issue = Issue(
        number=1, title="Something",
        body="", author="test", created_at="2025-01-01",
    )
    text = format_issues_for_extraction([issue])
    assert "Issue #1" in text
    assert "Something" in text


def test_format_multiple_prs():
    prs = [
        PullRequest(number=1, title="First", body="", author="a", created_at="2025-01-01", merged_at="2025-01-01"),
        PullRequest(number=2, title="Second", body="", author="b", created_at="2025-01-02", merged_at="2025-01-02"),
    ]
    text = format_prs_for_extraction(prs)
    assert "PR #1" in text
    assert "PR #2" in text
    assert "---" in text  # Separator between PRs
