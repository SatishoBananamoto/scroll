"""Relevance engine — match entries to tasks using keyword extraction."""

import re
from scroll.store import ScrollEntry

# Common words to ignore when extracting keywords
STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "about", "between",
    "through", "after", "before", "above", "below", "and", "but", "or",
    "not", "no", "so", "if", "then", "than", "that", "this", "it", "its",
    "i", "we", "you", "he", "she", "they", "me", "us", "my", "your",
    "add", "make", "use", "get", "set", "new", "fix", "update", "change",
    "need", "want", "like", "just", "also", "how", "what", "when", "where",
    "why", "which", "who", "all", "each", "every", "any", "some",
}


def extract_keywords(text: str) -> set[str]:
    """Extract meaningful keywords from a task description."""
    words = re.findall(r"[a-z][a-z0-9_-]+", text.lower())
    return {w for w in words if w not in STOP_WORDS and len(w) > 2}


def score_entry(entry: ScrollEntry, keywords: set[str]) -> float:
    """Score an entry's relevance to a set of keywords.

    Scoring:
    - Title match: 3 points per keyword
    - Tag match: 2 points per keyword
    - Body match: 1 point per keyword
    """
    score = 0.0
    title_lower = entry.title.lower()
    body_lower = entry.body.lower()
    tags_lower = {t.lower() for t in entry.tags}

    for kw in keywords:
        if kw in title_lower:
            score += 3.0
        if kw in tags_lower:
            score += 2.0
        if kw in body_lower:
            score += 1.0

    return score


def find_relevant(
    entries: list[ScrollEntry],
    task_description: str,
    top_k: int = 10,
    min_score: float = 1.0,
) -> list[tuple[ScrollEntry, float]]:
    """Find entries most relevant to a task description.

    Returns list of (entry, score) tuples, sorted by score descending.
    """
    keywords = extract_keywords(task_description)
    if not keywords:
        return []

    scored = []
    for entry in entries:
        s = score_entry(entry, keywords)
        if s >= min_score:
            scored.append((entry, s))

    scored.sort(key=lambda x: -x[1])
    return scored[:top_k]
