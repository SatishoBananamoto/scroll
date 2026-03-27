# Scroll — Review

**Reviewer**: Claude (Opus 4.6, partner session)
**Date**: 2026-03-20
**Version Reviewed**: v0.1.0, 12 modules, ~2,000 LOC, 75+ tests
**Previous Review**: First review

---

## Summary

Scroll extracts institutional memory from git history, GitHub PRs, and issues using LLM-powered knowledge extraction. It produces structured entries (decisions, learnings, mistakes, observations, goals) in engram-compatible format, and injects them into agent instruction files (CLAUDE.md, .cursorrules, copilot-instructions.md). It also exposes a MCP server for agent integration. The pipeline is well-designed with incremental state tracking, deduplication, and validation. The main risk is LLM extraction quality as the unverified load-bearing wall.

---

## Dimension Assessments

### Thesis & Positioning

The thesis: the work itself is the source of truth. Commits, PRs, and issue discussions contain decisions, learnings, and mistakes that are currently implicit — scroll makes them explicit and structured.

This is a genuinely valuable idea. Teams lose context constantly. The person who made a decision leaves, the PR discussion gets buried, the commit message is terse. Six months later someone asks "why did we do it this way?" and nobody knows.

**Differentiation concern**: GitHub Copilot, Cursor, and other AI coding tools are converging on "AI that understands your codebase history" via RAG over repo contents. They'll do it with embeddings, not structured extraction. The question is whether structured entries (searchable, linkable, validated) are meaningfully better than RAG retrieval for agent context. I believe they are — structured entries can be reviewed, corrected, and linked. RAG results can't. But the market may not care about that distinction.

**Best path**: Position scroll as the extraction layer for engram, not as a standalone tool. The value is in the structured output that feeds into a knowledge graph, not in the extraction itself.

### Architecture

12 modules with clear pipeline structure:

```
git_reader → extractor → store → export/sync
github_reader ↗            ↑
                     state (incremental tracking)
                     query/relevance (retrieval)
                     integrity (health)
                     cli/server (interfaces)
```

| Module | Role | Assessment |
|--------|------|-----------|
| git_reader.py | Parse git log, format for LLM | Solid. Handles force-push recovery. |
| github_reader.py | Read PRs/issues via gh CLI | Good. Extracts reviews, comments. |
| extractor.py | Claude API call with structured tool use | Works but unverified (see Weaknesses) |
| store.py | ScrollEntry dataclass, validation, dedup, markdown I/O | Clean. Two dedup strategies. |
| state.py | Incremental processing state (JSON) | Well-designed. Tracks commits, PRs, issues. |
| query.py | Search and filter entries | Simple, functional. |
| relevance.py | Keyword-based task relevance scoring | Works but fragile (see Weaknesses) |
| export.py | Format conversion (claude-md, json, summary) | Good. Key section extraction per type. |
| sync.py | Idempotent agent file injection | Clean. HTML markers for section replacement. |
| integrity.py | Health scoring with type-specific staleness | Thorough. 5 thresholds, required sections check. |
| cli.py | 11 Click commands | Comprehensive. |
| server.py | MCP server with 7 tools | Well-defined tool descriptions. |

Data flow is clear, module boundaries are clean. No circular dependencies.

### Code Quality

| Metric | Value | Assessment |
|--------|-------|-----------|
| Tests | 75+ across 12 test files | Good coverage |
| Modules | 12 source files | Each earns its place |
| Dependencies | click, anthropic (+ mcp for server) | Minimal, necessary |
| Test approach | Mocked extraction, real validation/dedup | Practical |

Test distribution covers all modules: git_reader (8), store (20), query (10), relevance (9), export (6), sync (14), state (7), cli (13), integrity (14), github_reader (12).

The extractor tests mock Claude's API response — correct for unit tests, but means the extraction prompt is effectively untested. A prompt change could silently degrade extraction quality.

Error handling is solid: git_reader falls back gracefully on missing commits (force-push recovery), state tracking resumes from last successful batch, extraction failures save progress before stopping.

### Completeness

**Complete:**
- Git history reading with incremental processing
- GitHub PR/issue reading via gh CLI with comment/review extraction
- LLM extraction with structured tool use (Claude Sonnet)
- Validation (type, title, body sections, confidence, sources)
- Deduplication (title normalization + source commit overlap)
- Markdown serialization (full roundtrip)
- State tracking (last commit, processed commits/PRs/issues)
- Full-text search and type/tag filtering
- Keyword-based relevance scoring
- Multi-format export (claude-md, json, summary)
- Idempotent agent file injection with HTML markers
- Post-commit git hook installation
- Knowledge health scoring
- MCP server with 7 tools
- CLI with 11 commands

**Missing:**
- Extraction verification layer (no check that LLM output is factually grounded)
- Semantic relevance (keyword-only, no embeddings or synonym expansion)
- Entry editing/supersession workflow (supersedes field exists but unused in CLI)
- Feedback loop (no signal about whether injected knowledge was useful to agents)
- Batching limits for GitHub API calls
- Multi-repo aggregation
- LLM model version pinning (prompt tuned for one model, may break on update)

### Usability

**Setup**: `scroll init` creates `.scroll/entries/`, then `scroll ingest` runs extraction. Requires `ANTHROPIC_API_KEY` environment variable. Straightforward for someone who's used CLI tools.

**CLI**: Well-designed Click interface with 11 commands. `--help` text is clear. Commands are logically named (init, ingest, list, search, show, stats, export, relevant, sync, hook, health).

**MCP server**: 7 tools with clear descriptions. `scroll_relevant` is the killer feature — "what should I know before starting this task?"

**Pain point**: `scroll ingest` costs real money (Claude API calls). No dry-run mode to preview what would be extracted before committing to API calls. No cost estimate before running.

### Sustainability

LLM dependency is the sustainability risk. The extraction prompt is doing heavy lifting: required sections per type, dedup instructions, confidence calibration, quality thresholds — all in one system prompt. One Claude model update could change extraction behavior. There's no regression test against a known corpus.

The non-LLM parts (git_reader, store, state, sync, integrity) are self-contained and robust. They'd survive indefinitely with zero maintenance.

Cost is an ongoing concern: every ingestion run costs money. For a solo dev this is manageable. For team adoption it becomes a line item.

### Portfolio Fit

Scroll is the extraction layer for engram. It produces engram-compatible entries from git history. The connection is already explicit and functional.

The relationship should be: scroll extracts → engram stores and validates → agents query via MCP. Scroll is the collector, engram is the curator.

Scroll could also feed vigil: "scroll found 3 decisions about why we chose library X → vigil assesses library X's health → the decision entry gets annotated with risk level."

---

## Strengths

1. **Incremental state tracking with force-push recovery.** Tracks all processed commits (not just last) so force-pushed commits don't get re-processed. This shows real-world git awareness — most tools don't handle this.

2. **Idempotent sync with HTML markers.** The `<!-- scroll:start -->` / `<!-- scroll:end -->` pattern for CLAUDE.md injection means re-running sync never duplicates content. Handles create/append/replace correctly.

3. **Two-strategy deduplication.** Title normalization catches near-duplicates. Source commit subset checking catches semantic duplicates from overlapping extraction batches. Both are needed.

4. **Git hook integration.** `scroll hook` installs a post-commit hook that auto-syncs knowledge to agent files. Zero-effort ongoing operation after setup.

5. **Comprehensive CLI.** 11 commands covering the full lifecycle from init through ingestion, querying, export, sync, and health monitoring.

---

## Weaknesses

1. **No extraction verification.** The LLM extracts "facts" from commits, but nothing validates that those facts are actually grounded in the source material. Confidence is self-reported by the same LLM that might be hallucinating. **Fix**: After extraction, pick 2-3 entries per batch, re-prompt Claude with "Given these commits, is this entry factually accurate? Quote the specific commit content that supports each claim." Flag disagreements for human review.

2. **Keyword-based relevance is fragile.** "Add OAuth to the mobile app" and "Implement authentication flow for Android" are the same task but share zero keywords after stopword removal. At ~100 entries this breaks down. **Fix**: Short-term: add a synonym map for common development terms (auth/authentication/oauth, test/testing/spec, deploy/deployment/release). Long-term: embeddings.

3. **No dry-run or cost estimate for ingestion.** `scroll ingest` calls the Claude API immediately. No way to preview what would be extracted or estimate cost. **Fix**: Add `scroll ingest --dry-run` that shows commit count, estimated batches, and approximate token cost without making API calls.

4. **Extraction prompt is a single point of failure.** All extraction logic lives in one system prompt in extractor.py. It's tuned for a specific Claude model version. A model update could silently change extraction quality. **Fix**: Add a regression test: known git history → expected extraction output. Run it when updating the model parameter.

5. **No feedback loop.** Scroll injects knowledge into CLAUDE.md but never knows if it was useful. Did the agent read the decision? Did it avoid the mistake? **Fix**: This is hard to solve fully, but a start: add a `scroll usage` command that greps agent session logs for scroll entry IDs, showing which entries were actually referenced.

---

## Recommendations (Priority Order)

1. **Add extraction verification.** Even a simple re-prompting check on 2-3 entries per batch catches obvious hallucinations. This is the single most important quality improvement.

2. **Add `--dry-run` to ingestion.** Show what would be processed and estimated cost. Reduces anxiety about running expensive operations.

3. **Add synonym expansion to relevance scoring.** A 20-line synonym map would significantly improve task-to-entry matching without adding complexity.

4. **Add extraction regression test.** Known commits → expected entries. Run on model version changes.

5. **Position as engram's extraction layer, not standalone tool.** Documentation, CLI help text, and README should frame scroll as "how you feed engram from git history" rather than a separate product.

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| LLM extraction hallucinations go undetected | High | High | Verification layer + regression tests |
| Model update changes extraction quality | Medium | High | Pin model version, regression test |
| Big players ship git-history RAG as a feature | High | Medium | Position as structured extraction for engram, not standalone |
| API cost limits adoption | Medium | Low | Dry-run, batch size controls, cost tracking |
| Keyword relevance fails at scale | High | Medium | Synonym expansion, eventual embeddings |

---

## Verdict

Scroll has the most ambitious technical goal in the portfolio: automated knowledge extraction from git history. The pipeline design is solid — incremental processing, deduplication, validation, sync, and health scoring all work. The weakness is that the core value proposition (LLM extraction) is unverified. The system extracts knowledge but has no way to know if that knowledge is accurate. Fix the verification gap and scroll becomes a genuine force multiplier. Without it, you're trusting the LLM completely, and that trust is unearned until tested.

**Grade: B**
Solid pipeline, well-architected, comprehensive CLI. The unverified extraction and fragile relevance scoring keep it from B+ until the core quality gap is addressed.
