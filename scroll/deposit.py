"""Deposit scroll entries into engram knowledge base.

Scroll extracts knowledge from git history. Engram stores knowledge for
cross-session access. This module bridges them: scroll entries flow into
engram, enriching the knowledge graph with project history.
"""

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

from scroll.store import ScrollEntry, load_entries, PREFIXES, normalize_title


ENGRAM_DEFAULT_ROOT = Path.home() / "engram"
DEPOSIT_STATE_FILE = "deposit_state.json"


@dataclass
class DepositResult:
    """Result of a deposit operation."""
    deposited: list[tuple[str, str]] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    quality_skipped: list[str] = field(default_factory=list)


def load_deposit_state(scroll_dir: Path) -> dict[str, str]:
    """Load mapping of scroll_id -> engram_id from previous deposits."""
    state_file = scroll_dir / DEPOSIT_STATE_FILE
    if not state_file.exists():
        return {}

    data = json.loads(state_file.read_text(encoding="utf-8"))
    return data.get("deposited", {})


def save_deposit_state(scroll_dir: Path, deposited: dict[str, str]):
    """Save deposit state mapping."""
    state_file = scroll_dir / DEPOSIT_STATE_FILE
    data = {
        "deposited": deposited,
        "last_deposit": date.today().isoformat(),
    }
    state_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def find_max_engram_num(entries_dir: Path, entry_type: str) -> int:
    """Find the highest existing ID number for a type in engram."""
    prefix = PREFIXES[entry_type]
    max_num = 0

    for f in entries_dir.glob(f"{prefix}-*.md"):
        parts = f.stem.split("-")
        if len(parts) == 2:
            try:
                max_num = max(max_num, int(parts[1]))
            except ValueError:
                continue

    return max_num


def render_engram_entry(entry: ScrollEntry, engram_id: str) -> str:
    """Render a scroll entry as engram-compatible markdown.

    Engram entries have: id, type, date, tags, status, source, confidence, project.
    source is always 'scroll' for deposited entries.
    Scroll's source_commits go into the body (not frontmatter) for provenance.
    """
    tags = list(entry.tags)
    if "scroll-extracted" not in tags:
        tags.append("scroll-extracted")

    tags_str = "[" + ", ".join(tags) + "]"

    lines = [
        "---",
        f"id: {engram_id}",
        f"type: {entry.type}",
        f"date: {entry.date}",
        f"tags: {tags_str}",
        f"status: {entry.status}",
        f"source: scroll",
        f"confidence: {entry.confidence}",
    ]

    if entry.project:
        lines.append(f"project: {entry.project}")

    lines.append("---")
    lines.append("")
    lines.append(f"# {entry.title}")
    lines.append("")
    lines.append(entry.body)

    # Provenance section — so engram knows where this came from
    if entry.source_commits:
        sources = ", ".join(entry.source_commits)
        lines.append("")
        lines.append("## Source")
        lines.append(f"Extracted by scroll from: {sources}")
        lines.append(f"Original scroll ID: {entry.id}")

    return "\n".join(lines) + "\n"


def _word_set(title: str) -> set[str]:
    """Normalize title to word set for duplicate detection."""
    return set(normalize_title(title).split())


def _check_duplicate(title: str, existing_titles: list[str],
                     threshold: float = 0.70) -> Optional[str]:
    """Check if title is a near-duplicate of any existing title.

    Returns the matching title if found, None otherwise.
    """
    new_words = _word_set(title)
    if len(new_words) < 3:
        return None

    for existing in existing_titles:
        existing_words = _word_set(existing)
        if len(existing_words) < 3:
            continue
        intersection = new_words & existing_words
        union = new_words | existing_words
        jaccard = len(intersection) / len(union) if union else 0
        if jaccard >= threshold:
            return existing

    return None


def _load_existing_titles(engram_entries: Path) -> list[str]:
    """Load titles from existing engram entries for duplicate checking."""
    titles = []
    for f in engram_entries.glob("*.md"):
        text = f.read_text(encoding="utf-8")
        for line in text.split("\n"):
            if line.startswith("# ") and not line.startswith("## "):
                titles.append(line[2:].strip())
                break
    return titles


MIN_BODY_WORDS = 20  # Entries shorter than this are likely trivia


def deposit(
    scroll_dir: Path,
    engram_root: Path = None,
    dry_run: bool = False,
    project_filter: Optional[str] = None,
    quality_check: bool = True,
) -> DepositResult:
    """Deposit scroll entries into engram.

    Reads entries from scroll's .scroll/entries/, assigns fresh engram IDs,
    writes engram-compatible markdown to ~/engram/entries/, and tracks what
    was deposited to prevent duplicates on re-runs.

    Args:
        scroll_dir: Path to .scroll directory
        engram_root: Path to engram root (default: ~/engram)
        dry_run: If True, report what would happen without writing
        project_filter: Only deposit entries from this project
        quality_check: Reject near-duplicate or too-short entries before writing

    Returns:
        DepositResult with lists of deposited, skipped, and errors.
    """
    if engram_root is None:
        engram_root = ENGRAM_DEFAULT_ROOT

    result = DepositResult()

    # Validate engram exists
    engram_entries = engram_root / "entries"
    if not engram_entries.exists():
        result.errors.append(f"Engram entries directory not found: {engram_entries}")
        return result

    # Load scroll entries
    entries = load_entries(scroll_dir)
    if not entries:
        return result

    # Filter by project if specified
    if project_filter:
        entries = [e for e in entries if e.project == project_filter]

    if not entries:
        return result

    # Load deposit state (what we've already sent)
    state = load_deposit_state(scroll_dir)

    # Find max IDs per type in engram — we increment from here
    next_nums = {}
    for entry_type in PREFIXES:
        next_nums[entry_type] = find_max_engram_num(engram_entries, entry_type) + 1

    new_state = dict(state)

    # Quality gate: load existing titles for duplicate checking
    existing_titles = []
    if quality_check:
        existing_titles = _load_existing_titles(engram_entries)

    for entry in entries:
        # Already deposited?
        if entry.id in state:
            result.skipped.append(entry.id)
            continue

        # Quality gate: near-duplicate check
        if quality_check and existing_titles:
            dup = _check_duplicate(entry.title, existing_titles)
            if dup:
                msg = f"Skipped {entry.id}: near-duplicate of existing '{dup[:60]}'"
                result.skipped.append(entry.id)
                result.quality_skipped.append(msg)
                continue

        # Quality gate: minimum body length
        if quality_check and len(entry.body.split()) < MIN_BODY_WORDS:
            msg = (
                f"Skipped {entry.id}: body too short "
                f"({len(entry.body.split())} words, minimum {MIN_BODY_WORDS})"
            )
            result.skipped.append(entry.id)
            result.quality_skipped.append(msg)
            continue

        # Assign next engram ID
        prefix = PREFIXES[entry.type]
        num = next_nums[entry.type]
        engram_id = f"{prefix}-{num:03d}"
        next_nums[entry.type] = num + 1

        # Render and write
        content = render_engram_entry(entry, engram_id)

        if not dry_run:
            target = engram_entries / f"{engram_id}.md"
            target.write_text(content, encoding="utf-8")

        result.deposited.append((entry.id, engram_id))
        new_state[entry.id] = engram_id

        # Track title for intra-batch duplicate detection
        if quality_check:
            existing_titles.append(entry.title)

    # Persist state
    if not dry_run and result.deposited:
        save_deposit_state(scroll_dir, new_state)

    return result
