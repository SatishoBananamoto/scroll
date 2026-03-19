"""Sync scroll knowledge into agent instruction files.

Writes extracted knowledge directly into the files that agents are
forced to read — CLAUDE.md, .cursorrules, .github/copilot-instructions.md.

The knowledge is bracketed with markers so sync is idempotent:
repeated runs replace the scroll section, not duplicate it.
"""

import re
from pathlib import Path
from scroll.store import ScrollEntry, load_entries
from scroll.export import export_claude_md

# Markers that bracket the scroll section in target files
START_MARKER = "<!-- scroll:start -->"
END_MARKER = "<!-- scroll:end -->"

# Agent instruction files and their formats
AGENT_FILES = {
    "claude": "CLAUDE.md",
    "cursor": ".cursorrules",
    "copilot": ".github/copilot-instructions.md",
}


def build_scroll_section(entries: list[ScrollEntry], project: str = None) -> str:
    """Build the scroll knowledge section with markers."""
    content = export_claude_md(entries, project)
    return f"{START_MARKER}\n{content}\n{END_MARKER}"


def inject_into_file(file_path: Path, section: str) -> tuple[bool, str]:
    """Inject scroll section into a file. Returns (changed, message).

    If the file has existing scroll markers, replaces that section.
    If not, appends to the end.
    If the file doesn't exist, creates it.
    """
    if file_path.exists():
        existing = file_path.read_text(encoding="utf-8")

        # Check if scroll section already exists
        pattern = re.compile(
            re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
            re.DOTALL,
        )
        if pattern.search(existing):
            new_content = pattern.sub(section, existing)
            if new_content == existing:
                return False, "unchanged"
            file_path.write_text(new_content, encoding="utf-8")
            return True, "updated"
        else:
            # Append with spacing
            separator = "\n\n" if existing.rstrip() else ""
            file_path.write_text(existing.rstrip() + separator + section + "\n", encoding="utf-8")
            return True, "appended"
    else:
        # Create new file
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(section + "\n", encoding="utf-8")
        return True, "created"


def sync_to_agents(
    repo_path: Path,
    scroll_dir: Path,
    targets: list[str] = None,
) -> list[tuple[str, str, str]]:
    """Sync scroll knowledge to agent instruction files.

    Args:
        repo_path: Root of the git repository
        scroll_dir: Path to .scroll directory
        targets: List of agent targets ("claude", "cursor", "copilot").
                 Default: ["claude"]

    Returns:
        List of (agent_name, file_path, action) tuples.
    """
    if targets is None:
        targets = ["claude"]

    entries = load_entries(scroll_dir)
    if not entries:
        return []

    # Detect project name
    project = None
    projects = {e.project for e in entries if e.project}
    if len(projects) == 1:
        project = projects.pop()

    section = build_scroll_section(entries, project)
    results = []

    for target in targets:
        filename = AGENT_FILES.get(target)
        if not filename:
            results.append((target, "", f"unknown agent '{target}'"))
            continue

        file_path = repo_path / filename
        changed, action = inject_into_file(file_path, section)
        results.append((target, str(file_path), action))

    return results


def setup_git_hook(repo_path: Path) -> tuple[bool, str]:
    """Install a post-commit git hook that runs scroll sync.

    Returns (success, message).
    """
    hooks_dir = repo_path / ".git" / "hooks"
    if not hooks_dir.exists():
        return False, ".git/hooks not found — is this a git repo?"

    hook_path = hooks_dir / "post-commit"
    hook_line = 'python3 -m scroll -r "$(git rev-parse --show-toplevel)" sync --quiet 2>/dev/null || true'

    if hook_path.exists():
        existing = hook_path.read_text(encoding="utf-8")
        if "scroll" in existing:
            return False, "scroll hook already installed"
        # Append to existing hook
        content = existing.rstrip() + "\n\n# scroll: sync knowledge to agent files\n" + hook_line + "\n"
        hook_path.write_text(content, encoding="utf-8")
        hook_path.chmod(0o755)
        return True, "appended to existing post-commit hook"
    else:
        content = "#!/bin/sh\n\n# scroll: sync knowledge to agent files\n" + hook_line + "\n"
        hook_path.write_text(content, encoding="utf-8")
        hook_path.chmod(0o755)
        return True, "created post-commit hook"
