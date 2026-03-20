"""scroll CLI — Institutional memory, extracted from the work itself."""

import sys
from pathlib import Path

import click

from scroll.git_reader import read_git_log, format_commits_for_extraction
from scroll.extractor import extract_knowledge
from scroll.store import save_entries, load_entries
from scroll.state import get_last_commit, get_processed_commits, update_state
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
@click.option("--full", is_flag=True, help="Ignore state, re-process all")
@click.option("--github", is_flag=True, help="Also ingest PRs and issues from GitHub")
@click.option("--github-only", is_flag=True, help="Only ingest from GitHub (skip git commits)")
@click.option("--max-prs", default=50, help="Max PRs to analyze")
@click.option("--max-issues", default=50, help="Max issues to analyze")
@click.pass_context
def ingest(ctx, max_commits, batch_size, project, model, full, github, github_only, max_prs, max_issues):
    """Read git history (and optionally GitHub PRs/issues) and extract knowledge."""
    repo = ctx.obj["repo"]
    scroll_dir = ctx.obj["scroll_dir"]

    if not scroll_dir.exists():
        click.echo("Not initialized. Run 'scroll init' first.")
        sys.exit(1)

    if not project:
        project = repo.name

    # Load existing entries once for dedup
    existing = load_entries(scroll_dir)
    total_saved = 0
    total_invalid = 0
    total_duplicate = 0
    all_saved = []

    # --- Git commits ---
    if not github_only:
        total_saved, total_invalid, total_duplicate, all_saved = _ingest_commits(
            repo, scroll_dir, existing, project, model,
            max_commits, batch_size, full,
        )

    # --- GitHub PRs and Issues ---
    if github or github_only:
        gh_saved, gh_invalid, gh_dup = _ingest_github(
            repo, scroll_dir, existing, project, model,
            max_prs, max_issues, full, batch_size,
        )
        total_saved += gh_saved
        total_invalid += gh_invalid
        total_duplicate += gh_dup

    # Summary
    click.echo()
    if all_saved:
        click.echo(f"Saved {total_saved} entries:")
        for entry in all_saved:
            click.echo(f"  [{entry.id}] {entry.title}")
    elif total_saved:
        click.echo(f"Saved {total_saved} entries total.")
    if total_invalid:
        click.echo(f"Skipped {total_invalid} invalid entries.")
    if total_duplicate:
        click.echo(f"Skipped {total_duplicate} duplicate entries.")
    if not total_saved and not total_invalid and not total_duplicate:
        click.echo("No knowledge extracted.")


def _ingest_commits(repo, scroll_dir, existing, project, model, max_commits, batch_size, full):
    """Ingest from git commit history. Returns (saved, invalid, duplicate, saved_entries)."""
    from scroll.state import get_last_commit, get_processed_commits, update_state

    since_commit = None
    if not full:
        since_commit = get_last_commit(scroll_dir)
        if since_commit:
            click.echo(f"Incremental mode: processing commits after {since_commit[:8]}...")

    click.echo(f"Reading git history ({max_commits} commits max)...")
    commits = read_git_log(repo, max_commits, since_commit=since_commit)

    if not full:
        processed = get_processed_commits(scroll_dir)
        before = len(commits)
        commits = [c for c in commits if c.hash not in processed]
        if before != len(commits):
            click.echo(f"Skipped {before - len(commits)} already-processed commits.")

    click.echo(f"Found {len(commits)} new commits.")

    if not commits:
        click.echo("Nothing new to process from git.")
        return 0, 0, 0, []

    batches = []
    batch_commits = []
    for i in range(0, len(commits), batch_size):
        batch = commits[i:i + batch_size]
        batches.append(format_commits_for_extraction(batch))
        batch_commits.append(batch)

    click.echo(f"Extracting knowledge from {len(batches)} commit batch(es)...")

    total_saved = 0
    total_invalid = 0
    total_duplicate = 0
    all_saved = []

    for i, batch_text in enumerate(batches):
        click.echo(f"  Batch {i + 1}/{len(batches)}...")

        try:
            entries = extract_knowledge(batch_text, model=model)
        except Exception as e:
            click.echo(f"    !! Extraction failed: {e}")
            click.echo(f"    Saving progress and stopping.")
            break

        click.echo(f"    -> {len(entries)} entries extracted")

        saved, invalid, duplicate = save_entries(entries, scroll_dir, project, existing)
        total_saved += len(saved)
        total_invalid += len(invalid)
        total_duplicate += len(duplicate)
        all_saved.extend(saved)

        if invalid:
            click.echo(f"    -> {len(invalid)} skipped (invalid)")
        if duplicate:
            click.echo(f"    -> {len(duplicate)} skipped (duplicate)")

        batch_hashes = [c.hash for c in batch_commits[i]]
        last_successful_commit = batch_commits[i][0].hash
        update_state(scroll_dir, batch_hashes, last_successful_commit)

    return total_saved, total_invalid, total_duplicate, all_saved


def _ingest_github(repo, scroll_dir, existing, project, model, max_prs, max_issues, full, batch_size):
    """Ingest from GitHub PRs and issues. Returns (saved, invalid, duplicate)."""
    from scroll.github_reader import (
        check_gh_available, read_pull_requests, read_issues,
        format_prs_for_extraction, format_issues_for_extraction,
    )
    from scroll.state import (
        get_processed_prs, get_processed_issues,
        update_state_prs, update_state_issues,
    )

    ok, msg = check_gh_available(repo)
    if not ok:
        click.echo(f"GitHub: {msg}")
        return 0, 0, 0

    total_saved = 0
    total_invalid = 0
    total_duplicate = 0

    # --- PRs ---
    click.echo(f"Reading GitHub PRs ({max_prs} max)...")
    prs = read_pull_requests(repo, max_prs)

    if not full:
        processed_prs = get_processed_prs(scroll_dir)
        before = len(prs)
        prs = [pr for pr in prs if pr.number not in processed_prs]
        if before != len(prs):
            click.echo(f"Skipped {before - len(prs)} already-processed PRs.")

    click.echo(f"Found {len(prs)} new PRs.")

    if prs:
        # Batch PRs (fewer per batch since they're larger)
        pr_batch_size = max(1, batch_size // 5)
        for i in range(0, len(prs), pr_batch_size):
            batch = prs[i:i + pr_batch_size]
            batch_text = format_prs_for_extraction(batch)
            click.echo(f"  PR batch {i // pr_batch_size + 1}...")

            try:
                entries = extract_knowledge(batch_text, model=model)
            except Exception as e:
                click.echo(f"    !! PR extraction failed: {e}")
                break

            click.echo(f"    -> {len(entries)} entries extracted")

            saved, invalid, duplicate = save_entries(entries, scroll_dir, project, existing)
            total_saved += len(saved)
            total_invalid += len(invalid)
            total_duplicate += len(duplicate)

            for s in saved:
                click.echo(f"    [{s.id}] {s.title}")

            update_state_prs(scroll_dir, [pr.number for pr in batch])

    # --- Issues ---
    click.echo(f"Reading GitHub issues ({max_issues} max)...")
    issues = read_issues(repo, max_issues)

    if not full:
        processed_issues = get_processed_issues(scroll_dir)
        before = len(issues)
        issues = [i for i in issues if i.number not in processed_issues]
        if before != len(issues):
            click.echo(f"Skipped {before - len(issues)} already-processed issues.")

    click.echo(f"Found {len(issues)} new issues.")

    if issues:
        issue_batch_size = max(1, batch_size // 5)
        for i in range(0, len(issues), issue_batch_size):
            batch = issues[i:i + issue_batch_size]
            batch_text = format_issues_for_extraction(batch)
            click.echo(f"  Issue batch {i // issue_batch_size + 1}...")

            try:
                entries = extract_knowledge(batch_text, model=model)
            except Exception as e:
                click.echo(f"    !! Issue extraction failed: {e}")
                break

            click.echo(f"    -> {len(entries)} entries extracted")

            saved, invalid, duplicate = save_entries(entries, scroll_dir, project, existing)
            total_saved += len(saved)
            total_invalid += len(invalid)
            total_duplicate += len(duplicate)

            for s in saved:
                click.echo(f"    [{s.id}] {s.title}")

            update_state_issues(scroll_dir, [iss.number for iss in batch])

    return total_saved, total_invalid, total_duplicate




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


@cli.command()
@click.option("--format", "-f", "fmt",
              type=click.Choice(["claude-md", "json", "summary"]),
              default="claude-md", help="Export format")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Write to file instead of stdout")
@click.pass_context
def export(ctx, fmt, output):
    """Export knowledge for agent context injection."""
    from scroll.export import export_claude_md, export_json, export_summary

    scroll_dir = ctx.obj["scroll_dir"]
    entries = load_entries(scroll_dir)

    if not entries:
        click.echo("No entries to export.")
        return

    project = None
    projects = {e.project for e in entries if e.project}
    if len(projects) == 1:
        project = projects.pop()

    if fmt == "claude-md":
        result = export_claude_md(entries, project)
    elif fmt == "json":
        result = export_json(entries)
    elif fmt == "summary":
        result = export_summary(entries)
    else:
        click.echo(f"Unknown format: {fmt}")
        return

    if output:
        Path(output).write_text(result, encoding="utf-8")
        click.echo(f"Exported {len(entries)} entries to {output}")
    else:
        click.echo(result)


@cli.command()
@click.argument("task")
@click.option("--top", "-k", default=5, help="Number of results")
@click.pass_context
def relevant(ctx, task, top):
    """Find entries relevant to a task description."""
    from scroll.relevance import find_relevant
    from scroll.export import _extract_key_section

    scroll_dir = ctx.obj["scroll_dir"]
    entries = load_entries(scroll_dir)
    results = find_relevant(entries, task, top_k=top)

    if not results:
        click.echo(f"No relevant entries for: '{task}'")
        return

    click.echo(f"Top {len(results)} entries for: '{task}'\n")
    for entry, score in results:
        tags = ", ".join(entry.tags[:5])
        click.echo(f"  [{entry.id}] {entry.title}  (score: {score:.1f})")
        click.echo(f"      type={entry.type}  tags=[{tags}]")

        key = _extract_key_section(entry)
        if key:
            preview = key.split("\n")[0][:120].strip()
            click.echo(f"      >> {preview}")
        click.echo()


@cli.command()
@click.option("--target", "-t", multiple=True, default=["claude"],
              help="Agent targets: claude, cursor, copilot (repeatable)")
@click.option("--quiet", "-q", is_flag=True, help="Suppress output (for hooks)")
@click.pass_context
def sync(ctx, target, quiet):
    """Sync knowledge into agent instruction files (CLAUDE.md, .cursorrules, etc.)."""
    from scroll.sync import sync_to_agents

    repo = ctx.obj["repo"]
    scroll_dir = ctx.obj["scroll_dir"]

    if not scroll_dir.exists():
        if not quiet:
            click.echo("Not initialized. Run 'scroll init' first.")
        sys.exit(1)

    results = sync_to_agents(repo, scroll_dir, list(target))

    if not results:
        if not quiet:
            click.echo("No entries to sync.")
        return

    if not quiet:
        for agent, path, action in results:
            click.echo(f"  {agent}: {action} ({path})")


@cli.command()
@click.pass_context
def hook(ctx):
    """Install a post-commit git hook to auto-sync after each commit."""
    from scroll.sync import setup_git_hook

    repo = ctx.obj["repo"]
    success, message = setup_git_hook(repo)

    if success:
        click.echo(f"Hook installed: {message}")
        click.echo("Knowledge will auto-sync to CLAUDE.md after each commit.")
    else:
        click.echo(f"Not installed: {message}")
