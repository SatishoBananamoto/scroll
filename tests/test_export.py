"""Tests for scroll.export."""

from scroll.store import ScrollEntry
from scroll.export import export_claude_md, export_json, export_summary


def _entries():
    return [
        ScrollEntry(id="DEC-001", type="decision", date="2026-03-19",
                     title="Use gRPC for service communication",
                     tags=["architecture", "grpc"],
                     body="## Context\nNeeded fast RPC.\n\n## Choice\ngRPC.\n\n## Reasoning\nLow latency, streaming support.\n\n## Alternatives Considered\nREST, GraphQL.",
                     confidence="high", source_commits=["abc123"], project="myapi"),
        ScrollEntry(id="MST-001", type="mistake", date="2026-03-19",
                     title="Forgot to configure HTTP/2 on load balancer",
                     tags=["grpc", "infrastructure"],
                     body="## Context\ngRPC deployment.\n\n## What Went Wrong\nLB stripped HTTP/2.\n\n## Root Cause\nDefault config.\n\n## Prevention\nAlways verify LB supports HTTP/2 before deploying gRPC.",
                     confidence="high", source_commits=["def456"], project="myapi"),
        ScrollEntry(id="LRN-001", type="learning", date="2026-03-19",
                     title="gRPC health checks need custom implementation",
                     tags=["grpc", "health-checks"],
                     body="## Context\nProduction monitoring.\n\n## What Happened\nStandard health checks didn't work.\n\n## Insight\ngRPC uses its own health protocol.\n\n## Applies To\nAny gRPC service.",
                     confidence="medium", source_commits=["ghi789"], project="myapi"),
    ]


def test_claude_md_has_sections():
    md = export_claude_md(_entries(), "myapi")
    assert "## Project Knowledge (scroll)" in md
    assert "### Decisions" in md
    assert "### Known Mistakes" in md
    assert "### Learnings" in md
    assert "DEC-001" in md
    assert "MST-001" in md


def test_claude_md_includes_key_content():
    md = export_claude_md(_entries(), "myapi")
    # Should include the Prevention section for mistakes
    assert "verify LB supports HTTP/2" in md
    # Should include Reasoning for decisions
    assert "Low latency" in md


def test_claude_md_shows_confidence_for_non_medium():
    md = export_claude_md(_entries(), "myapi")
    # high confidence should show
    assert "(high)" in md


def test_claude_md_empty_entries():
    md = export_claude_md([], None)
    assert "No entries yet" in md


def test_json_export_valid():
    import json
    result = export_json(_entries())
    data = json.loads(result)
    assert len(data) == 3
    assert data[0]["id"] == "DEC-001"
    assert data[0]["type"] == "decision"
    assert "grpc" in data[0]["tags"]


def test_summary_export():
    result = export_summary(_entries())
    lines = result.strip().split("\n")
    assert len(lines) == 3
    assert "DEC-001" in lines[0]
    assert "decision" in lines[0]
