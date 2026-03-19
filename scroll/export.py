"""Export scroll knowledge in various formats."""

import json
from scroll.store import ScrollEntry, PREFIXES

TYPE_LABELS = {
    "decision": "Decisions",
    "learning": "Learnings",
    "mistake": "Known Mistakes",
    "observation": "Observations",
    "goal": "Goals",
}

TYPE_ICONS = {
    "decision": "[DEC]",
    "learning": "[LRN]",
    "mistake": "[MST]",
    "observation": "[OBS]",
    "goal": "[GOL]",
}


def export_claude_md(entries: list[ScrollEntry], project: str = None) -> str:
    """Export entries as a CLAUDE.md-compatible knowledge section.

    Organized by type, concise, designed for agent context injection.
    """
    if not entries:
        return "## Project Knowledge (scroll)\n\nNo entries yet.\n"

    lines = ["## Project Knowledge (scroll)", ""]
    if project:
        lines.append(f"*Extracted from `{project}` git history.*")
        lines.append("")

    # Group by type
    by_type: dict[str, list[ScrollEntry]] = {}
    for entry in entries:
        by_type.setdefault(entry.type, []).append(entry)

    # Render each type
    for entry_type in ["decision", "mistake", "learning", "observation", "goal"]:
        group = by_type.get(entry_type, [])
        if not group:
            continue

        label = TYPE_LABELS[entry_type]
        lines.append(f"### {label}")
        lines.append("")

        for entry in group:
            conf = f" ({entry.confidence})" if entry.confidence != "medium" else ""
            lines.append(f"- **{entry.id}**: {entry.title}{conf}")

            # Extract the most actionable section from body
            key_section = _extract_key_section(entry)
            if key_section:
                # Indent as sub-bullet, keep concise
                for sline in key_section.split("\n")[:3]:
                    sline = sline.strip()
                    if sline:
                        lines.append(f"  - {sline}")

        lines.append("")

    return "\n".join(lines)


def _extract_key_section(entry: ScrollEntry) -> str:
    """Extract the most actionable section from an entry body.

    For mistakes: Prevention
    For decisions: Reasoning
    For learnings: Insight
    For observations: Significance
    For goals: Success Criteria
    """
    priority_sections = {
        "mistake": ["## Prevention", "## Root Cause"],
        "decision": ["## Reasoning", "## Choice"],
        "learning": ["## Insight", "## Applies To"],
        "observation": ["## Significance"],
        "goal": ["## Success Criteria", "## Objective"],
    }

    sections = priority_sections.get(entry.type, [])
    body = entry.body

    for section_header in sections:
        if section_header in body:
            # Extract content between this header and the next
            start = body.index(section_header) + len(section_header)
            rest = body[start:]
            # Find next ## header
            next_header = rest.find("\n## ")
            if next_header != -1:
                content = rest[:next_header].strip()
            else:
                content = rest.strip()
            if content:
                return content

    return ""


def export_json(entries: list[ScrollEntry]) -> str:
    """Export entries as structured JSON."""
    data = []
    for entry in entries:
        data.append({
            "id": entry.id,
            "type": entry.type,
            "date": entry.date,
            "title": entry.title,
            "tags": entry.tags,
            "body": entry.body,
            "status": entry.status,
            "confidence": entry.confidence,
            "source_commits": entry.source_commits,
            "project": entry.project,
        })
    return json.dumps(data, indent=2)


def export_summary(entries: list[ScrollEntry]) -> str:
    """Export a compact one-line-per-entry summary."""
    lines = []
    for entry in entries:
        tags = ", ".join(entry.tags[:3])
        lines.append(f"{entry.id}  {entry.type:<12} {entry.title}  [{tags}]")
    return "\n".join(lines)
