"""
Scroll MCP Server

Exposes scroll's extracted knowledge as MCP tools for AI coding agents.
Point it at any repo with a .scroll/ directory and agents get institutional memory.

Tools:
- scroll_search: Search knowledge entries
- scroll_show: Show full entry details
- scroll_list: List entries with filters
- scroll_relevant: Find entries relevant to a task
- scroll_stats: Summary statistics
- scroll_export: Export knowledge for context injection
"""

import sys
from pathlib import Path
from mcp.server.fastmcp import FastMCP

from scroll.store import load_entries
from scroll.query import search, filter_by_type, filter_by_tag
from scroll.relevance import find_relevant
from scroll.export import export_claude_md, export_json, export_summary


def _resolve_scroll_dir() -> Path:
    """Find the .scroll directory.

    Checks, in order:
    1. SCROLL_REPO env var
    2. Current working directory
    3. Parent directories (walk up)
    """
    import os

    env_repo = os.environ.get("SCROLL_REPO")
    if env_repo:
        candidate = Path(env_repo).resolve() / ".scroll"
        if candidate.exists():
            return candidate

    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        candidate = parent / ".scroll"
        if candidate.exists():
            return candidate

    return cwd / ".scroll"


SCROLL_DIR = _resolve_scroll_dir()

mcp = FastMCP("scroll", instructions="""
Scroll extracts institutional memory from git history. It reads commits and
produces structured knowledge entries: decisions, learnings, mistakes,
observations, and goals.

Use these tools to query what the team has learned, what decisions were made
and why, what mistakes to avoid, and what patterns have been observed.

Entry types:
- decision (DEC): A choice with reasoning and alternatives considered
- learning (LRN): Something discovered through doing
- mistake (MST): What broke, why, and how to prevent it
- observation (OBS): A pattern noticed across the history
- goal (GOL): An objective being worked toward
""")


def _load():
    return load_entries(SCROLL_DIR)


@mcp.tool()
def scroll_search(query: str) -> str:
    """Search knowledge entries by text. Searches titles, bodies, and tags."""
    entries = _load()
    results = search(entries, query)
    if not results:
        return f"No entries found for '{query}'."

    lines = [f"Found {len(results)} result(s) for '{query}':\n"]
    for entry in results:
        tags = ", ".join(entry.tags)
        lines.append(f"  {entry.id}: {entry.title}")
        lines.append(f"      type={entry.type}  confidence={entry.confidence}  tags=[{tags}]")
    return "\n".join(lines)


@mcp.tool()
def scroll_show(entry_id: str) -> str:
    """Show full details of a knowledge entry."""
    entries = _load()
    entry_id = entry_id.upper()
    entry = next((e for e in entries if e.id == entry_id), None)

    if not entry:
        return f"Entry '{entry_id}' not found."

    tags = ", ".join(entry.tags)
    sources = ", ".join(entry.source_commits) if entry.source_commits else "none"

    lines = [
        f"{entry.id}: {entry.title}",
        f"Type: {entry.type}  Status: {entry.status}  Confidence: {entry.confidence}",
        f"Date: {entry.date}  Project: {entry.project or 'none'}",
        f"Tags: {tags}",
        f"Source commits: {sources}",
        "",
        entry.body,
    ]
    return "\n".join(lines)


@mcp.tool()
def scroll_list(filter_type: str = "") -> str:
    """List entries. Optional filter: 'decisions', 'learnings', 'mistakes', 'observations', 'goals', or 'tag:X'."""
    entries = _load()

    if filter_type:
        ft = filter_type.lower().strip()
        type_map = {
            "decisions": "decision", "decision": "decision",
            "learnings": "learning", "learning": "learning",
            "mistakes": "mistake", "mistake": "mistake",
            "observations": "observation", "observation": "observation",
            "goals": "goal", "goal": "goal",
        }
        if ft in type_map:
            entries = filter_by_type(entries, type_map[ft])
        elif ft.startswith("tag:"):
            entries = filter_by_tag(entries, ft[4:])
        else:
            return f"Unknown filter '{filter_type}'. Use: decisions, learnings, mistakes, observations, goals, tag:X"

    if not entries:
        return "No entries found."

    lines = []
    for entry in entries:
        tags = ", ".join(entry.tags)
        lines.append(f"  {entry.id}: {entry.title}")
        lines.append(f"      type={entry.type}  confidence={entry.confidence}  tags=[{tags}]")
    return "\n".join(lines)


@mcp.tool()
def scroll_relevant(task: str, top_k: int = 5) -> str:
    """Find knowledge entries most relevant to a task description.

    Args:
        task: Description of what you're about to do
        top_k: Maximum number of entries to return (default 5)
    """
    entries = _load()
    results = find_relevant(entries, task, top_k=top_k)

    if not results:
        return f"No relevant entries found for: '{task}'"

    lines = [f"Top {len(results)} entries relevant to: '{task}'\n"]
    for entry, score in results:
        tags = ", ".join(entry.tags[:5])
        lines.append(f"  {entry.id}: {entry.title}  (relevance: {score:.1f})")
        lines.append(f"      type={entry.type}  tags=[{tags}]")

        # Show the key actionable content
        from scroll.export import _extract_key_section
        key = _extract_key_section(entry)
        if key:
            preview = key.split("\n")[0][:120]
            lines.append(f"      >> {preview}")
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
def scroll_stats() -> str:
    """Show summary statistics of the knowledge base."""
    entries = _load()

    if not entries:
        return "No entries yet."

    by_type = {}
    by_confidence = {}
    all_tags = {}
    projects = set()

    for e in entries:
        by_type[e.type] = by_type.get(e.type, 0) + 1
        by_confidence[e.confidence] = by_confidence.get(e.confidence, 0) + 1
        for t in e.tags:
            all_tags[t] = all_tags.get(t, 0) + 1
        if e.project:
            projects.add(e.project)

    lines = [
        f"Scroll Knowledge Base: {len(entries)} entries",
        "",
        "By type:",
    ]
    for t, count in sorted(by_type.items()):
        lines.append(f"  {t}: {count}")

    lines.append("\nBy confidence:")
    for c, count in sorted(by_confidence.items()):
        lines.append(f"  {c}: {count}")

    if projects:
        lines.append(f"\nProjects: {', '.join(sorted(projects))}")

    top_tags = sorted(all_tags.items(), key=lambda x: -x[1])[:10]
    lines.append("\nTop tags:")
    for t, count in top_tags:
        lines.append(f"  {t}: {count}")

    return "\n".join(lines)


@mcp.tool()
def scroll_export(format: str = "claude-md") -> str:
    """Export knowledge base in a specific format.

    Args:
        format: 'claude-md' (for CLAUDE.md injection), 'json' (structured), or 'summary' (compact)
    """
    entries = _load()
    project = None
    if entries:
        projects = {e.project for e in entries if e.project}
        project = projects.pop() if len(projects) == 1 else None

    if format == "claude-md":
        return export_claude_md(entries, project)
    elif format == "json":
        return export_json(entries)
    elif format == "summary":
        return export_summary(entries)
    else:
        return f"Unknown format '{format}'. Use: claude-md, json, summary"



@mcp.tool()
def scroll_health() -> str:
    """Check knowledge base health: staleness, missing sections, duplicates, coverage."""
    from scroll.integrity import compute_health, render_health
    entries = _load()
    report = compute_health(entries)
    return render_health(report)


if __name__ == "__main__":
    mcp.run(transport="stdio")