"""Tests for scroll.git_reader."""

import tempfile
import subprocess
from pathlib import Path

from scroll.git_reader import read_git_log, format_commits_for_extraction


def _make_temp_repo(num_commits=3):
    """Create a temporary git repo with N commits."""
    td = tempfile.mkdtemp()
    repo = Path(td)
    subprocess.run(["git", "init", str(repo)], capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@test.com"], capture_output=True)

    for i in range(1, num_commits + 1):
        (repo / f"file{i}.txt").write_text(f"content {i}")
        subprocess.run(["git", "-C", str(repo), "add", "."], capture_output=True)
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-m", f"Commit {i}: add file{i}"],
            capture_output=True,
        )

    return repo


def test_reads_commits():
    repo = _make_temp_repo(3)
    commits = read_git_log(repo, max_commits=10)
    assert len(commits) == 3
    # Newest first
    assert "Commit 3" in commits[0].message
    assert "Commit 1" in commits[2].message


def test_max_commits_limits_results():
    repo = _make_temp_repo(5)
    commits = read_git_log(repo, max_commits=2)
    assert len(commits) == 2


def test_commit_fields_populated():
    repo = _make_temp_repo(1)
    commits = read_git_log(repo, max_commits=1)
    c = commits[0]
    assert len(c.hash) == 40
    assert len(c.short_hash) >= 7
    assert c.author == "Test"
    assert c.date  # Non-empty
    assert "Commit 1" in c.message


def test_empty_repo_returns_empty():
    td = tempfile.mkdtemp()
    repo = Path(td)
    subprocess.run(["git", "init", str(repo)], capture_output=True)
    commits = read_git_log(repo, max_commits=10)
    assert commits == []


def test_format_commits():
    repo = _make_temp_repo(2)
    commits = read_git_log(repo, max_commits=10)
    text = format_commits_for_extraction(commits)
    assert "Commit 2" in text
    assert "Commit 1" in text
    assert "by Test" in text
