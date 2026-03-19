"""scroll CLI — Institutional memory, extracted from the work itself."""

import sys
from pathlib import Path

import click

from scroll.git_reader import read_git_log, format_commits_for_extraction
from scroll.extractor import extract_knowledge
from scroll.store import save_entries, load_entries
from scroll.query import search, filter_by_type, filter_by_tag

SCROLL_DIR = ".scroll"


@click.group()
@click.option("--repo", "-r", type=click.Path(exists=True), default=".",
              help="Repository path (default: current directory)")
@click.pass_context
def cli(ctx, repo):
    """scroll — Institutional memory, extracted from the work itself."""
    ctx.ensure_object(dict)
    ctx.obj["repo"] = Path(repo).resolve()
    ctx.obj["scroll_dir"] = ctx.obj["repo"] / SCROLL_DIR


@cli.command()
@click.pass_context
def init(ctx):
    """Initialize scroll in a repository."""
    scroll_dir = ctx.obj["scroll_dir"]
    entries_dir = scroll_dir / "entries"
    entries_dir.mkdir(parents=True, exist_ok=True)
    click.echo(f"Initialized scroll at {scroll_dir}")


@cli.command()
@click.option("--max-commits", "-n", default=100, help="Max commits to analyze")
@click.option("--batch-size", "-b", default=25, help="Commits per extraction batch")
@click.option("--project", "-p", default=None, help="Project name tag")
@click.option("--model", "-m", default="claude-sonnet-4-6", help="Model for extraction")
@click.pass_context
def ingest(ctx, max_commits, batch_size, project, model):
    """Read git history and extract knowledge."""
    repo = ctx.obj["repo"]
    scroll_dir = ctx.obj["scroll_dir"]

    if not scroll_dir.exists():
        click.echo("Not initialized. Run 'scroll init' first.")
        sys.exit(1)

    if not project:
        project = repo.name

    click.echo(f"Reading git history ({max_commits} commits max)...")
    commits = read_git_log(repo, max_commits)
    click.echo(f"Found {len(commits)} commits.")

    if not commits:
        click.echo("No commits found.")
        return

    # Batch commits for extraction
    batches = []
    for i in range(0, len(commits), batch_size):
        batch = commits[i:i + batch_size]
        batches.append(format_commits_for_extraction(batch))

    click.echo(f"Extracting knowledge from {len(batches)} batch(es)...")

    all_entries = []
    for i, batch_text in enumerate(batches):
        click.echo(f"  Batch {i + 1}/{len(batches)}...")
        entries = extract_knowledge(batch_text, model=model)
        all_entries.extend(entries)
        click.echo(f"    -> {len(entries)} entries extracted")

    if not all_entries:
        click.echo("No knowledge extracted.")
        return

    saved = save_entries(all_entries, scroll_dir, project)
    click.echo(f"\nSaved {len(saved)} entries to {scroll_dir / 'entries'}/")
    for entry in saved:
        click.echo(f"  [{entry.id}] {entry.title}")


@cli.command("list")
@click.option("--type", "-t", "entry_type", default=None,
              type=click.Choice(["decision", "learning", "mistake", "observation", "goal"]),
              help="Filter by entry type")
@click.option("--tag", default=None, help="Filter by tag")
@click.pass_context
def list_entries(ctx, entry_type, tag):
    """List all extracted knowledge entries."""
    scroll_dir = ctx.obj["scroll_dir"]
    entries = load_entries(scroll_dir)

    if entry_type:
        entries = filter_by_type(entries, entry_type)
    if tag:
        entries = filter_by_tag(entries, tag)

    if not entries:
        click.echo("No entries found.")
        return

    for entry in entries:
        tags = ", ".join(entry.tags)
        click.echo(f"  [{entry.id}] {entry.title}")
        click.echo(f"      type={entry.type}  confidence={entry.confidence}  tags=[{tags}]")


@cli.command("search")
@click.argument("query")
@click.pass_context
def search_cmd(ctx, query):
    """Search entries by text."""
    scroll_dir = ctx.obj["scroll_dir"]
    entries = load_entries(scroll_dir)
    results = search(entries, query)

    if not results:
        click.echo("No matches found.")
        return

    click.echo(f"Found {len(results)} match(es):")
    for entry in results:
        tags = ", ".join(entry.tags)
        click.echo(f"  [{entry.id}] {entry.title}")
        click.echo(f"      type={entry.type}  confidence={entry.confidence}  tags=[{tags}]")


@cli.command()
@click.argument("entry_id")
@click.pass_context
def show(ctx, entry_id):
    """Show full details of an entry."""
    scroll_dir = ctx.obj["scroll_dir"]
    entries = load_entries(scroll_dir)
    entry = next((e for e in entries if e.id.upper() == entry_id.upper()), None)

    if not entry:
        click.echo(f"Entry {entry_id} not found.")
        sys.exit(1)

    tags = ", ".join(entry.tags)
    sources = ", ".join(entry.source_commits) if entry.source_commits else "none"

    click.echo(f"{entry.id}: {entry.title}")
    click.echo(f"Type: {entry.type}  Status: {entry.status}  Confidence: {entry.confidence}")
    click.echo(f"Date: {entry.date}  Project: {entry.project or 'none'}")
    click.echo(f"Tags: {tags}")
    click.echo(f"Source commits: {sources}")
    click.echo()
    click.echo(entry.body)


@cli.command()
@click.pass_context
def stats(ctx):
    """Show summary statistics."""
    scroll_dir = ctx.obj["scroll_dir"]
    entries = load_entries(scroll_dir)

    if not entries:
        click.echo("No entries yet.")
        return

    by_type = {}
    by_confidence = {}
    all_tags = {}

    for e in entries:
        by_type[e.type] = by_type.get(e.type, 0) + 1
        by_confidence[e.confidence] = by_confidence.get(e.confidence, 0) + 1
        for t in e.tags:
            all_tags[t] = all_tags.get(t, 0) + 1

    click.echo(f"Total entries: {len(entries)}")
    click.echo()
    click.echo("By type:")
    for t, count in sorted(by_type.items()):
        click.echo(f"  {t}: {count}")
    click.echo()
    click.echo("By confidence:")
    for c, count in sorted(by_confidence.items()):
        click.echo(f"  {c}: {count}")
    click.echo()
    top_tags = sorted(all_tags.items(), key=lambda x: -x[1])[:10]
    click.echo("Top tags:")
    for t, count in top_tags:
        click.echo(f"  {t}: {count}")
