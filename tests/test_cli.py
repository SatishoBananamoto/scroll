"""Integration tests for scroll CLI."""

import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from scroll.cli import cli
from scroll.store import ScrollEntry, entry_to_markdown


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


def _write_scroll_entry(repo: Path, entry: ScrollEntry):
    entries_dir = repo / ".scroll" / "entries"
    entries_dir.mkdir(parents=True, exist_ok=True)
    (entries_dir / f"{entry.id}.md").write_text(entry_to_markdown(entry), encoding="utf-8")


def _long_body():
    return "## Context\n" + " ".join(["substantive content here"] * 10)


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


def test_deposit_cli_reports_quality_gate_without_mislabeling(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    engram = tmp_path / "engram"
    (engram / "entries").mkdir(parents=True)

    entry = ScrollEntry(
        id="DEC-001",
        type="decision",
        date="2026-03-30",
        title="Stale positive signals from old metadata inflate scores on abandoned packages",
        tags=["quality"],
        body=_long_body(),
        confidence="high",
        source_commits=["abc1234"],
        project="scroll",
    )
    _write_scroll_entry(repo, entry)
    (engram / "entries" / "LRN-023.md").write_text(
        "---\nid: LRN-023\ntype: learning\ndate: 2026-03-27\n"
        "tags: [test]\nstatus: active\n---\n\n"
        "# Stale positive signals from metadata inflate scores on dead packages\n\n"
        "Body text here.\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["-r", str(repo), "deposit", "--engram-root", str(engram)])

    assert result.exit_code == 1
    assert "QUALITY: Skipped DEC-001: near-duplicate" in result.output
    assert "Skipped 1 quality-gated entries." in result.output
    assert "already-deposited" not in result.output
    assert not (engram / "entries" / "DEC-001.md").exists()


def test_deposit_cli_can_disable_quality_check(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    engram = tmp_path / "engram"
    (engram / "entries").mkdir(parents=True)

    entry = ScrollEntry(
        id="DEC-001",
        type="decision",
        date="2026-03-30",
        title="Short deliberate backfill",
        tags=["quality"],
        body="## Context\nShort.",
        confidence="high",
        source_commits=["abc1234"],
        project="scroll",
    )
    _write_scroll_entry(repo, entry)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["-r", str(repo), "deposit", "--engram-root", str(engram), "--no-quality-check"],
    )

    assert result.exit_code == 0
    assert "Deposited 1 entries into engram:" in result.output
    assert (engram / "entries" / "DEC-001.md").exists()
