"""Read structured data from GitHub PRs and issues via gh CLI."""

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class PullRequest:
    number: int
    title: str
    body: str
    author: str
    created_at: str
    merged_at: str
    labels: list[str] = field(default_factory=list)
    files_changed: list[str] = field(default_factory=list)
    comments: list[dict] = field(default_factory=list)
    reviews: list[dict] = field(default_factory=list)


@dataclass
class Issue:
    number: int
    title: str
    body: str
    author: str
    created_at: str
    labels: list[str] = field(default_factory=list)
    comments: list[dict] = field(default_factory=list)


def _run_gh(repo_path: Path, args: list[str]) -> Optional[str]:
    """Run a gh CLI command and return stdout, or None on failure."""
    cmd = ["gh"] + args
    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=str(repo_path),
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def check_gh_available(repo_path: Path) -> tuple[bool, str]:
    """Check if gh CLI is available and authenticated for this repo."""
    result = subprocess.run(
        ["gh", "auth", "status"], capture_output=True, text=True, cwd=str(repo_path),
    )
    if result.returncode != 0:
        return False, "gh CLI not authenticated. Run 'gh auth login'."

    # Check if repo has a GitHub remote
    result2 = subprocess.run(
        ["gh", "repo", "view", "--json", "name"], capture_output=True, text=True, cwd=str(repo_path),
    )
    if result2.returncode != 0:
        return False, "Not a GitHub repository or no remote configured."

    return True, "ok"


def read_pull_requests(
    repo_path: Path,
    max_prs: int = 50,
    state: str = "merged",
) -> list[PullRequest]:
    """Read pull requests from the GitHub repo.

    Args:
        repo_path: Path to git repo
        max_prs: Maximum PRs to fetch
        state: "merged", "closed", "open", or "all"
    """
    fields = "number,title,body,author,createdAt,mergedAt,labels,files,comments,reviews"
    raw = _run_gh(repo_path, [
        "pr", "list",
        "--state", state,
        "--limit", str(max_prs),
        "--json", fields,
    ])
    if not raw:
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []

    prs = []
    for item in data:
        author = item.get("author", {})
        author_name = author.get("login", "") if isinstance(author, dict) else str(author)

        labels = [l.get("name", "") for l in item.get("labels", []) if isinstance(l, dict)]

        files = [f.get("path", "") for f in item.get("files", []) if isinstance(f, dict)]

        comments = []
        for c in item.get("comments", []):
            if isinstance(c, dict) and c.get("body", "").strip():
                c_author = c.get("author", {})
                comments.append({
                    "author": c_author.get("login", "") if isinstance(c_author, dict) else "",
                    "body": c.get("body", "").strip(),
                    "date": c.get("createdAt", "")[:10],
                })

        reviews = []
        for r in item.get("reviews", []):
            if isinstance(r, dict) and r.get("body", "").strip():
                r_author = r.get("author", {})
                reviews.append({
                    "author": r_author.get("login", "") if isinstance(r_author, dict) else "",
                    "body": r.get("body", "").strip(),
                    "state": r.get("state", ""),
                    "date": r.get("submittedAt", "")[:10] if r.get("submittedAt") else "",
                })

        prs.append(PullRequest(
            number=item.get("number", 0),
            title=item.get("title", ""),
            body=item.get("body", "") or "",
            author=author_name,
            created_at=item.get("createdAt", "")[:10],
            merged_at=(item.get("mergedAt") or "")[:10],
            labels=labels,
            files_changed=files,
            comments=comments,
            reviews=reviews,
        ))

    return prs


def read_issues(
    repo_path: Path,
    max_issues: int = 50,
    state: str = "closed",
) -> list[Issue]:
    """Read issues from the GitHub repo."""
    raw = _run_gh(repo_path, [
        "issue", "list",
        "--state", state,
        "--limit", str(max_issues),
        "--json", "number,title,body,author,createdAt,labels,comments",
    ])
    if not raw:
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []

    issues = []
    for item in data:
        author = item.get("author", {})
        author_name = author.get("login", "") if isinstance(author, dict) else str(author)

        labels = [l.get("name", "") for l in item.get("labels", []) if isinstance(l, dict)]

        comments = []
        for c in item.get("comments", []):
            if isinstance(c, dict) and c.get("body", "").strip():
                c_author = c.get("author", {})
                comments.append({
                    "author": c_author.get("login", "") if isinstance(c_author, dict) else "",
                    "body": c.get("body", "").strip(),
                    "date": c.get("createdAt", "")[:10],
                })

        issues.append(Issue(
            number=item.get("number", 0),
            title=item.get("title", ""),
            body=item.get("body", "") or "",
            author=author_name,
            created_at=item.get("createdAt", "")[:10],
            labels=labels,
            comments=comments,
        ))

    return issues


def format_prs_for_extraction(prs: list[PullRequest]) -> str:
    """Format PRs into a readable block for LLM extraction."""
    parts = []
    for pr in prs:
        lines = [
            f"=== PR #{pr.number}: {pr.title} ===",
            f"Author: {pr.author} | Merged: {pr.merged_at or 'not merged'} | Created: {pr.created_at}",
        ]
        if pr.labels:
            lines.append(f"Labels: {', '.join(pr.labels)}")
        if pr.files_changed:
            files_preview = ", ".join(pr.files_changed[:8])
            if len(pr.files_changed) > 8:
                files_preview += f" (+{len(pr.files_changed) - 8} more)"
            lines.append(f"Files: {files_preview}")

        if pr.body:
            # Truncate very long descriptions
            body = pr.body[:2000]
            if len(pr.body) > 2000:
                body += "\n[... truncated]"
            lines.append(f"\nDescription:\n{body}")

        if pr.reviews:
            lines.append("\nReviews:")
            for r in pr.reviews[:10]:
                state_tag = f" [{r['state']}]" if r.get("state") else ""
                body_preview = r["body"][:500]
                lines.append(f"  @{r['author']}{state_tag}: {body_preview}")

        if pr.comments:
            lines.append("\nComments:")
            for c in pr.comments[:10]:
                body_preview = c["body"][:500]
                lines.append(f"  @{c['author']}: {body_preview}")

        parts.append("\n".join(lines))

    return "\n\n---\n\n".join(parts)


def format_issues_for_extraction(issues: list[Issue]) -> str:
    """Format issues into a readable block for LLM extraction."""
    parts = []
    for issue in issues:
        lines = [
            f"=== Issue #{issue.number}: {issue.title} ===",
            f"Author: {issue.author} | Created: {issue.created_at}",
        ]
        if issue.labels:
            lines.append(f"Labels: {', '.join(issue.labels)}")

        if issue.body:
            body = issue.body[:2000]
            if len(issue.body) > 2000:
                body += "\n[... truncated]"
            lines.append(f"\nDescription:\n{body}")

        if issue.comments:
            lines.append("\nComments:")
            for c in issue.comments[:10]:
                body_preview = c["body"][:500]
                lines.append(f"  @{c['author']}: {body_preview}")

        parts.append("\n".join(lines))

    return "\n\n---\n\n".join(parts)
