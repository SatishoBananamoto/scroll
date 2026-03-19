"""Integration tests for scroll CLI."""

import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from scroll.cli import cli


def _make_repo(num_commits=3):
    """Create a temp git repo."""
    td = tempfile.mkdtemp()
    repo = Path(td)
    subprocess.run(["git", "init", str(repo)], capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t.com"], capture_output=True)

    for i in range(1, num_commits + 1):
        (repo / f"file{i}.txt").write_text(f"content {i}")
        subprocess.run(["git", "-C", str(repo), "add", "."], capture_output=True)
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-m", f"feat: add feature {i}\n\nDetailed description of feature {i}."],
            capture_output=True,
        )
    return repo


MOCK_EXTRACTION = [
    {
        "entry_type": "decision",
        "title": "Add feature 3 as the primary capability",
        "tags": ["feature", "architecture"],
        "body": "## Context\nNeeded new capability.\n\n## Choice\nFeature 3.\n\n## Reasoning\nBest fit.\n\n## Alternatives Considered\nFeature 4.",
        "confidence": "high",
        "source_commits": ["abc1234"],
    },
    {
        "entry_type": "learning",
        "title": "Feature iteration requires incremental commits",
        "tags": ["process", "git"],
        "body": "## Context\nBuilding features.\n\n## What Happened\nSmall commits worked better.\n\n## Insight\nIncremental is better.\n\n## Applies To\nAll feature work.",
        "confidence": "medium",
        "source_commits": ["def5678"],
    },
]


def _mock_extract(commits_text, model="claude-sonnet-4-6"):
    return MOCK_EXTRACTION


def test_init_creates_directory():
    repo = _make_repo(1)
    runner = CliRunner()
    result = runner.invoke(cli, ["-r", str(repo), "init"])
    assert result.exit_code == 0
    assert (repo / ".scroll" / "entries").is_dir()


@patch("scroll.cli.extract_knowledge", side_effect=_mock_extract)
def test_ingest_saves_entries(mock_extract):
    repo = _make_repo(3)
    runner = CliRunner()
    runner.invoke(cli, ["-r", str(repo), "init"])
    result = runner.invoke(cli, ["-r", str(repo), "ingest"])

    assert result.exit_code == 0
    assert "Saved 2 entries" in result.output
    assert (repo / ".scroll" / "entries" / "DEC-001.md").exists()
    assert (repo / ".scroll" / "entries" / "LRN-001.md").exists()


@patch("scroll.cli.extract_knowledge", side_effect=_mock_extract)
def test_ingest_twice_deduplicates(mock_extract):
    repo = _make_repo(3)
    runner = CliRunner()
    runner.invoke(cli, ["-r", str(repo), "init"])

    # First ingest
    result1 = runner.invoke(cli, ["-r", str(repo), "ingest"])
    assert "Saved 2 entries" in result1.output

    # Second ingest (--full to bypass incremental, test dedup layer)
    result2 = runner.invoke(cli, ["-r", str(repo), "ingest", "--full"])
    assert "duplicate" in result2.output.lower() or "Nothing new" in result2.output


@patch("scroll.cli.extract_knowledge", side_effect=_mock_extract)
def test_incremental_skips_processed(mock_extract):
    repo = _make_repo(3)
    runner = CliRunner()
    runner.invoke(cli, ["-r", str(repo), "init"])

    # First ingest processes all 3 commits
    runner.invoke(cli, ["-r", str(repo), "ingest"])

    # Second ingest — no new commits
    result = runner.invoke(cli, ["-r", str(repo), "ingest"])
    assert "Nothing new" in result.output


@patch("scroll.cli.extract_knowledge", side_effect=_mock_extract)
def test_list_shows_entries(mock_extract):
    repo = _make_repo(3)
    runner = CliRunner()
    runner.invoke(cli, ["-r", str(repo), "init"])
    runner.invoke(cli, ["-r", str(repo), "ingest"])

    result = runner.invoke(cli, ["-r", str(repo), "list"])
    assert "DEC-001" in result.output
    assert "LRN-001" in result.output


@patch("scroll.cli.extract_knowledge", side_effect=_mock_extract)
def test_list_filters_by_type(mock_extract):
    repo = _make_repo(3)
    runner = CliRunner()
    runner.invoke(cli, ["-r", str(repo), "init"])
    runner.invoke(cli, ["-r", str(repo), "ingest"])

    result = runner.invoke(cli, ["-r", str(repo), "list", "-t", "decision"])
    assert "DEC-001" in result.output
    assert "LRN-001" not in result.output


@patch("scroll.cli.extract_knowledge", side_effect=_mock_extract)
def test_search_finds_entries(mock_extract):
    repo = _make_repo(3)
    runner = CliRunner()
    runner.invoke(cli, ["-r", str(repo), "init"])
    runner.invoke(cli, ["-r", str(repo), "ingest"])

    result = runner.invoke(cli, ["-r", str(repo), "search", "incremental"])
    assert "LRN-001" in result.output


@patch("scroll.cli.extract_knowledge", side_effect=_mock_extract)
def test_show_displays_full_entry(mock_extract):
    repo = _make_repo(3)
    runner = CliRunner()
    runner.invoke(cli, ["-r", str(repo), "init"])
    runner.invoke(cli, ["-r", str(repo), "ingest"])

    result = runner.invoke(cli, ["-r", str(repo), "show", "DEC-001"])
    assert "decision" in result.output
    assert "## Context" in result.output


@patch("scroll.cli.extract_knowledge", side_effect=_mock_extract)
def test_stats_shows_summary(mock_extract):
    repo = _make_repo(3)
    runner = CliRunner()
    runner.invoke(cli, ["-r", str(repo), "init"])
    runner.invoke(cli, ["-r", str(repo), "ingest"])

    result = runner.invoke(cli, ["-r", str(repo), "stats"])
    assert "Total entries: 2" in result.output
    assert "decision: 1" in result.output
    assert "learning: 1" in result.output


@patch("scroll.cli.extract_knowledge", side_effect=Exception("API rate limit"))
def test_api_failure_saves_nothing_gracefully(mock_extract):
    repo = _make_repo(3)
    runner = CliRunner()
    runner.invoke(cli, ["-r", str(repo), "init"])

    result = runner.invoke(cli, ["-r", str(repo), "ingest"])
    assert "failed" in result.output.lower() or "Extraction failed" in result.output
