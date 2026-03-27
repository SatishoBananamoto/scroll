<!-- scroll:start -->
## Project Knowledge (scroll)

*Extracted from `scroll` git history.*

### Decisions

- **DEC-001**: Build scroll as incremental system with state tracking for reliable knowledge extraction (high)
  - - Large repositories would be expensive to re-process entirely each time
  - - API rate limits and costs make incremental processing essential
  - - Error recovery needed - partial completion should preserve progress
- **DEC-002**: Put knowledge where agents are forced to look rather than requiring tool usage (high)
  - Don't ask agents to use a tool - put the knowledge where they're already forced to look. This guarantees knowledge delivery without requiring agent cooperation. Auto-sync via git hooks keeps knowledge fresh automatically.
- **DEC-003**: Bridge scroll to engram with deposit module for knowledge system interoperability (high)
  - - Enables knowledge flow from automated extraction (scroll) to manual curation (engram)
  - - Preserves source provenance with scroll-extracted tag and source field
  - - Prevents duplicates through state tracking

### Learnings

- **LRN-001**: Commit messages are thin - PRs and issues contain the real knowledge (high)
  - Commit messages are brief and lack context. PRs and issues contain the real knowledge: reasoning behind decisions, alternatives that were debated, root causes of problems, and detailed discussions. Review comments often contain rejected alternatives that are valuable to capture.
- **LRN-002**: Knowledge systems need health scoring and staleness detection for maintenance (high)
  - Knowledge systems accumulate cruft over time. Automated quality assessment helps maintain institutional memory by flagging entries that need review, identifying gaps in coverage, and detecting duplicates that dilute signal.

<!-- scroll:end -->
