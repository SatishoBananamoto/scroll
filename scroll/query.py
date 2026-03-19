"""Search and filter scroll entries."""

from scroll.store import ScrollEntry


def search(entries: list[ScrollEntry], query: str) -> list[ScrollEntry]:
    """Full-text search over entry titles, bodies, and tags."""
    query_lower = query.lower()
    results = []
    for entry in entries:
        if (query_lower in entry.title.lower()
                or query_lower in entry.body.lower()
                or any(query_lower in tag.lower() for tag in entry.tags)):
            results.append(entry)
    return results


def filter_by_type(entries: list[ScrollEntry], entry_type: str) -> list[ScrollEntry]:
    """Filter entries by type name."""
    return [e for e in entries if e.type == entry_type]


def filter_by_tag(entries: list[ScrollEntry], tag: str) -> list[ScrollEntry]:
    """Filter entries that have a specific tag."""
    tag_lower = tag.lower()
    return [e for e in entries if any(t.lower() == tag_lower for t in e.tags)]
