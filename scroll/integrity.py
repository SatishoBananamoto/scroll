"""Knowledge integrity — health scoring, staleness detection, and cross-entry links.

Adapted from engram's quality layer. Gives scroll a way to assess
whether its knowledge base is trustworthy and well-maintained.
"""

import re
from datetime import date, timedelta
from dataclasses import dataclass, field
from scroll.store import ScrollEntry, PREFIXES

# How many days before an entry is considered stale (by type)
STALENESS_THRESHOLDS = {
    "decision": 90,     # Decisions should be reviewed quarterly
    "learning": 180,    # Learnings are more durable
    "mistake": 120,     # Mistakes should be checked — was prevention applied?
    "observation": 90,  # Observations may no longer hold
    "goal": 60,         # Goals should be checked frequently
}


@dataclass
class HealthReport:
    total_entries: int
    by_type: dict[str, int]
    stale_entries: list[tuple[ScrollEntry, int]]  # (entry, days_old)
    low_confidence: list[ScrollEntry]
    missing_sections: list[tuple[ScrollEntry, list[str]]]
    duplicate_titles: list[tuple[str, list[ScrollEntry]]]
    score: float  # 0-100

    @property
    def is_healthy(self) -> bool:
        return self.score >= 80


# Required sections per type
REQUIRED_SECTIONS = {
    "decision": ["## Context", "## Choice", "## Reasoning", "## Alternatives Considered"],
    "learning": ["## Context", "## What Happened", "## Insight", "## Applies To"],
    "mistake": ["## Context", "## What Went Wrong", "## Root Cause", "## Prevention"],
    "observation": ["## Context", "## Observation", "## Significance"],
    "goal": ["## Objective", "## Success Criteria", "## Current Status"],
}


def check_staleness(entries: list[ScrollEntry]) -> list[tuple[ScrollEntry, int]]:
    """Find entries older than their type's staleness threshold."""
    today = date.today()
    stale = []

    for entry in entries:
        if not entry.date:
            continue
        try:
            entry_date = date.fromisoformat(entry.date)
        except ValueError:
            continue

        days_old = (today - entry_date).days
        threshold = STALENESS_THRESHOLDS.get(entry.type, 90)

        if days_old > threshold:
            stale.append((entry, days_old))

    return sorted(stale, key=lambda x: -x[1])


def check_sections(entries: list[ScrollEntry]) -> list[tuple[ScrollEntry, list[str]]]:
    """Find entries missing required sections for their type."""
    issues = []

    for entry in entries:
        required = REQUIRED_SECTIONS.get(entry.type, [])
        missing = [s for s in required if s not in entry.body]
        if missing:
            issues.append((entry, missing))

    return issues


def check_low_confidence(entries: list[ScrollEntry]) -> list[ScrollEntry]:
    """Find entries with low confidence that may need verification."""
    return [e for e in entries if e.confidence == "low"]


def check_duplicate_titles(entries: list[ScrollEntry]) -> list[tuple[str, list[ScrollEntry]]]:
    """Find entries with very similar titles."""
    from scroll.store import normalize_title

    title_groups: dict[str, list[ScrollEntry]] = {}
    for entry in entries:
        normalized = normalize_title(entry.title)
        if normalized:
            title_groups.setdefault(normalized, []).append(entry)

    return [(title, group) for title, group in title_groups.items() if len(group) > 1]


def compute_health(entries: list[ScrollEntry]) -> HealthReport:
    """Compute a health report for the knowledge base."""
    if not entries:
        return HealthReport(
            total_entries=0, by_type={}, stale_entries=[],
            low_confidence=[], missing_sections=[], duplicate_titles=[],
            score=0.0,
        )

    by_type = {}
    for e in entries:
        by_type[e.type] = by_type.get(e.type, 0) + 1

    stale = check_staleness(entries)
    low_conf = check_low_confidence(entries)
    missing = check_sections(entries)
    dupes = check_duplicate_titles(entries)

    # Score calculation (0-100)
    # Start at 100, deduct for issues
    score = 100.0
    n = len(entries)

    # Staleness: up to -30 points
    stale_ratio = len(stale) / n
    score -= stale_ratio * 30

    # Missing sections: up to -30 points
    missing_ratio = len(missing) / n
    score -= missing_ratio * 30

    # Low confidence: up to -20 points
    low_conf_ratio = len(low_conf) / n
    score -= low_conf_ratio * 20

    # Duplicates: up to -10 points
    dupe_count = sum(len(g) - 1 for _, g in dupes)
    dupe_ratio = dupe_count / n if n > 0 else 0
    score -= dupe_ratio * 10

    # Type coverage: -10 if missing any type
    type_coverage = len(by_type) / len(PREFIXES)
    if type_coverage < 1.0:
        score -= (1.0 - type_coverage) * 10

    score = max(0.0, min(100.0, score))

    return HealthReport(
        total_entries=n,
        by_type=by_type,
        stale_entries=stale,
        low_confidence=low_conf,
        missing_sections=missing,
        duplicate_titles=dupes,
        score=score,
    )


def render_health(report: HealthReport) -> str:
    """Render a health report as readable text."""
    if report.total_entries == 0:
        return "No entries. Run 'scroll ingest' first."

    grade = "A" if report.score >= 90 else "B" if report.score >= 80 else "C" if report.score >= 70 else "D" if report.score >= 60 else "F"

    # Progress bar
    filled = int(report.score / 2)
    bar = "[" + "#" * filled + "." * (50 - filled) + "]"

    lines = [
        f"Health: {report.score:.1f}/100 ({grade})",
        f"  {bar}",
        f"  Entries: {report.total_entries}",
        "",
    ]

    # By type
    lines.append("  By type:")
    for t, count in sorted(report.by_type.items()):
        lines.append(f"    {t}: {count}")

    # Issues
    if report.stale_entries:
        lines.append(f"\n  Stale entries ({len(report.stale_entries)}):")
        for entry, days in report.stale_entries[:5]:
            lines.append(f"    {entry.id}: {entry.title} ({days} days old)")

    if report.missing_sections:
        lines.append(f"\n  Missing sections ({len(report.missing_sections)}):")
        for entry, missing in report.missing_sections[:5]:
            lines.append(f"    {entry.id}: missing {', '.join(missing)}")

    if report.low_confidence:
        lines.append(f"\n  Low confidence ({len(report.low_confidence)}):")
        for entry in report.low_confidence[:5]:
            lines.append(f"    {entry.id}: {entry.title}")

    if report.duplicate_titles:
        lines.append(f"\n  Possible duplicates ({len(report.duplicate_titles)}):")
        for title, group in report.duplicate_titles[:3]:
            ids = ", ".join(e.id for e in group)
            lines.append(f"    {ids}: \"{group[0].title}\"")

    if report.is_healthy:
        lines.append("\n  Status: healthy")
    else:
        lines.append("\n  Status: needs attention")

    return "\n".join(lines)
