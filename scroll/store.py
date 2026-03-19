"""Store and load knowledge entries in engram-compatible format."""

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional


PREFIXES = {
    "decision": "DEC",
    "learning": "LRN",
    "mistake": "MST",
    "observation": "OBS",
    "goal": "GOL",
}

VALID_TYPES = set(PREFIXES.keys())
VALID_CONFIDENCE = {"high", "medium", "low"}
FRONTMATTER_RE = re.compile(r"^---\s*\n(.+?)\n---\s*\n", re.DOTALL)


@dataclass
class ScrollEntry:
    id: str
    type: str
    date: str
    title: str
    tags: list[str]
    body: str
    status: str = "active"
    confidence: str = "medium"
    source_commits: list[str] = field(default_factory=list)
    project: Optional[str] = None


@dataclass
class ValidationError:
    field: str
    message: str


def validate_entry(raw: dict) -> list[ValidationError]:
    """Validate an extracted entry dict before saving.

    Returns list of errors. Empty list means valid.
    """
    errors = []

    entry_type = raw.get("entry_type", "")
    if entry_type not in VALID_TYPES:
        errors.append(ValidationError("entry_type", f"Invalid type '{entry_type}'"))

    title = raw.get("title", "")
    if not title or not title.strip():
        errors.append(ValidationError("title", "Title is empty"))

    tags = raw.get("tags", [])
    if not tags or not isinstance(tags, list):
        errors.append(ValidationError("tags", "Tags must be a non-empty list"))

    body = raw.get("body", "")
    if not body or not body.strip():
        errors.append(ValidationError("body", "Body is empty"))
    elif "## " not in body:
        errors.append(ValidationError("body", "Body has no section headers (## )"))

    confidence = raw.get("confidence", "")
    if confidence not in VALID_CONFIDENCE:
        errors.append(ValidationError("confidence", f"Invalid confidence '{confidence}'"))

    source_commits = raw.get("source_commits", [])
    if not source_commits or not isinstance(source_commits, list):
        errors.append(ValidationError("source_commits", "Must have at least one source commit"))

    return errors


def normalize_title(title: str) -> str:
    """Normalize a title for dedup comparison."""
    return re.sub(r"[^a-z0-9\s]", "", title.lower()).strip()


def is_duplicate(raw: dict, existing_entries: list[ScrollEntry]) -> bool:
    """Check if an extracted entry is a duplicate of an existing one."""
    new_title = normalize_title(raw.get("title", ""))
    if not new_title:
        return False

    for entry in existing_entries:
        if normalize_title(entry.title) == new_title:
            return True

    # Also check source commit overlap — if all source commits already
    # appear in an existing entry, likely duplicate
    new_sources = set(raw.get("source_commits", []))
    if new_sources:
        for entry in existing_entries:
            existing_sources = set(entry.source_commits)
            if existing_sources and new_sources.issubset(existing_sources):
                return True

    return False


def get_next_id(entries_dir: Path, entry_type: str) -> str:
    """Get the next available ID for an entry type."""
    prefix = PREFIXES[entry_type]
    existing = list(entries_dir.glob(f"{prefix}-*.md"))

    max_num = 0
    for f in existing:
        match = re.match(rf"{prefix}-(\d+)\.md", f.name)
        if match:
            max_num = max(max_num, int(match.group(1)))

    return f"{prefix}-{max_num + 1:03d}"


def entry_to_markdown(entry: ScrollEntry) -> str:
    """Convert a ScrollEntry to engram-compatible markdown."""
    tags_str = "[" + ", ".join(entry.tags) + "]"
    sources_str = "[" + ", ".join(entry.source_commits) + "]"

    lines = [
        "---",
        f"id: {entry.id}",
        f"type: {entry.type}",
        f"date: {entry.date}",
        f"tags: {tags_str}",
        f"status: {entry.status}",
        f"confidence: {entry.confidence}",
        f"source_commits: {sources_str}",
    ]
    if entry.project:
        lines.append(f"project: {entry.project}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {entry.title}")
    lines.append("")
    lines.append(entry.body)

    return "\n".join(lines) + "\n"


def save_entries(
    entries: list[dict],
    scroll_dir: Path,
    project_name: str = None,
    existing: list[ScrollEntry] = None,
) -> tuple[list[ScrollEntry], list[dict], list[dict]]:
    """Save extracted entries to disk with validation and dedup.

    Returns (saved, skipped_invalid, skipped_duplicate).
    """
    entries_dir = scroll_dir / "entries"
    entries_dir.mkdir(parents=True, exist_ok=True)

    if existing is None:
        existing = load_entries(scroll_dir)

    today = date.today().isoformat()
    saved = []
    skipped_invalid = []
    skipped_duplicate = []

    for raw in entries:
        # Validate
        errors = validate_entry(raw)
        if errors:
            raw["_errors"] = [f"{e.field}: {e.message}" for e in errors]
            skipped_invalid.append(raw)
            continue

        # Dedup
        if is_duplicate(raw, existing):
            skipped_duplicate.append(raw)
            continue

        entry_type = raw["entry_type"]
        entry_id = get_next_id(entries_dir, entry_type)

        entry = ScrollEntry(
            id=entry_id,
            type=entry_type,
            date=today,
            title=raw["title"],
            tags=raw.get("tags", []),
            body=raw.get("body", ""),
            confidence=raw.get("confidence", "medium"),
            source_commits=raw.get("source_commits", []),
            project=project_name,
        )

        md = entry_to_markdown(entry)
        file_path = entries_dir / f"{entry_id}.md"
        file_path.write_text(md, encoding="utf-8")
        saved.append(entry)
        existing.append(entry)  # Track for within-batch dedup

    return saved, skipped_invalid, skipped_duplicate


def load_entries(scroll_dir: Path) -> list[ScrollEntry]:
    """Load all entries from a scroll directory."""
    entries_dir = scroll_dir / "entries"
    if not entries_dir.exists():
        return []

    entries = []
    for md_file in sorted(entries_dir.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        entry = parse_scroll_entry(text)
        if entry:
            entries.append(entry)

    return entries


def parse_yaml_list(raw: str) -> list[str]:
    """Parse [a, b, c] style YAML list."""
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1]
        return [v.strip().strip("'\"") for v in inner.split(",") if v.strip()]
    return [raw] if raw else []


def parse_scroll_entry(text: str) -> Optional[ScrollEntry]:
    """Parse a scroll entry from markdown text."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None

    raw_yaml = match.group(1)
    body_full = text[match.end():].strip()

    # Parse frontmatter
    meta = {}
    for line in raw_yaml.split("\n"):
        line = line.strip()
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                meta[key] = parse_yaml_list(value)
            else:
                meta[key] = value.strip("'\"")

    # Extract title from H1
    title = ""
    body_lines = []
    for line in body_full.split("\n"):
        if line.startswith("# ") and not line.startswith("## ") and not title:
            title = line[2:].strip()
        else:
            body_lines.append(line)
    body = "\n".join(body_lines).strip()

    tags = meta.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]

    source_commits = meta.get("source_commits", [])
    if isinstance(source_commits, str):
        source_commits = [source_commits]

    return ScrollEntry(
        id=meta.get("id", ""),
        type=meta.get("type", ""),
        date=meta.get("date", ""),
        title=title,
        tags=tags,
        body=body,
        status=meta.get("status", "active"),
        confidence=meta.get("confidence", "medium"),
        source_commits=source_commits,
        project=meta.get("project"),
    )
