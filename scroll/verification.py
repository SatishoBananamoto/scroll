"""Verify extracted knowledge against the source batch."""

import re
from dataclasses import dataclass, field


STOPWORDS = {
    "about",
    "after",
    "also",
    "and",
    "are",
    "because",
    "before",
    "commit",
    "commits",
    "context",
    "from",
    "into",
    "learned",
    "learning",
    "needs",
    "should",
    "that",
    "the",
    "this",
    "through",
    "with",
}


@dataclass
class VerificationIssue:
    """A source-grounding issue for one extracted entry."""

    title: str
    kind: str
    message: str
    source_ref: str | None = None


@dataclass
class VerificationReport:
    """Result of verifying extracted entries against a source batch."""

    accepted: list[dict] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)
    warnings: list[VerificationIssue] = field(default_factory=list)


def verify_extractions(entries: list[dict], source_text: str) -> VerificationReport:
    """Reject entries with source refs that are absent from the source batch.

    The LLM can still make a bad inference from a real source. This check only
    catches the mechanical grounding failures that can be proven locally:
    fabricated commit/PR/issue refs and entries with almost no lexical support.
    """
    report = VerificationReport()

    for entry in entries:
        issues = _missing_source_ref_issues(entry, source_text)
        if issues:
            entry["_errors"] = [issue.message for issue in issues]
            report.rejected.append(entry)
            continue

        overlap = _support_overlap(entry, source_text)
        if overlap < 2:
            report.warnings.append(VerificationIssue(
                title=entry.get("title", ""),
                kind="low-source-overlap",
                message=(
                    "Entry has fewer than two significant title/body tokens "
                    "also present in the source batch."
                ),
            ))

        report.accepted.append(entry)

    return report


def _missing_source_ref_issues(entry: dict, source_text: str) -> list[VerificationIssue]:
    title = entry.get("title", "")
    refs = entry.get("source_commits", [])
    if not isinstance(refs, list):
        return [VerificationIssue(
            title=title,
            kind="invalid-source-refs",
            message="source_commits must be a list before extraction verification.",
        )]

    issues = []
    for source_ref in refs:
        if not _source_ref_present(str(source_ref), source_text):
            issues.append(VerificationIssue(
                title=title,
                kind="missing-source-ref",
                source_ref=str(source_ref),
                message=(
                    f"Source ref '{source_ref}' is not present in the source batch."
                ),
            ))

    return issues


def _source_ref_present(source_ref: str, source_text: str) -> bool:
    normalized_source = " ".join(source_text.lower().split())
    compact_source = normalized_source.replace(" ", "")
    normalized_ref = source_ref.strip().lower().replace(" ", "")

    pr_match = re.fullmatch(r"pr#?(\d+)", normalized_ref)
    if pr_match:
        number = pr_match.group(1)
        return f"pr#{number}" in compact_source or f"pr #{number}" in normalized_source

    issue_match = re.fullmatch(r"(?:i|issue)#?(\d+)", normalized_ref)
    if issue_match:
        number = issue_match.group(1)
        return (
            f"issue#{number}" in compact_source
            or f"issue #{number}" in normalized_source
        )

    return source_ref.strip().lower() in normalized_source


def _support_overlap(entry: dict, source_text: str) -> int:
    entry_text = " ".join([
        str(entry.get("title", "")),
        " ".join(str(tag) for tag in entry.get("tags", [])),
        str(entry.get("body", "")),
    ])
    entry_tokens = _significant_tokens(entry_text)
    source_tokens = _significant_tokens(source_text)
    return len(entry_tokens & source_tokens)


def _significant_tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9][a-z0-9_-]{2,}", text.lower())
        if token not in STOPWORDS
    }
