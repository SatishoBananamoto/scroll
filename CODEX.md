# CODEX — scroll

> Institutional memory extracted from git history, delivered to AI agents.
> Updated before every commit. Single source of truth for this project.

**Current version**: v0.1.0 (on PyPI as `git-scroll`)
**Last session**: 2026-07-03 — public CI and license repair
**Repo**: Ready to commit. 134 tests passing.

---

## NEXT SESSION — START HERE

### What just happened (2026-07-03 — Codex public-readiness pass)

**Public CI and license metadata were repaired.** GitHub Actions used the
invalid command `pip install pytest pip install -e .`, so public runs failed
before pytest started. The workflow now upgrades pip and installs pytest plus
editable scroll in separate valid steps. README already claimed MIT license,
but the repo had no LICENSE file and GitHub reported no license; an MIT
LICENSE file and package `readme`/`license` metadata are now present.
The engram parser compatibility test now skips when the sibling engram checkout
is unavailable, so public CI does not require private/local workspace state.

Verification: `python3 -B -m pytest -q -p no:cacheprovider` passed with 134
tests, `python3 -B -m compileall scroll tests` passed, `git diff --check`
passed, and editable package metadata/install succeeded in a throwaway venv
with `pip install -e . --no-deps --no-build-isolation`. The clean-CI path was
simulated with `HOME=/tmp/codex-no-engram`, where the engram parser test skips.

Previous session (2026-05-12 — Codex extraction-verification pass):

**Deterministic extraction verification is now wired into ingest.** After each
LLM extraction batch, scroll checks that every extracted entry cites source refs
that are present in the source batch. Entries with fabricated or mismatched
commit/PR/issue refs are skipped before `save_entries()`. Entries with very low
lexical overlap are accepted but reported as warnings so deeper review can
inspect likely weak grounding without blocking valid summaries.

Why: REVIEW.md identified unverified extraction as the load-bearing risk. This
does not replace a live LLM re-prompt verifier, but it closes the mechanical
grounding gap that can be proven locally and gives the future verifier a stable
module to build on.

Verification: `python3 -B -m pytest -q -p no:cacheprovider` passed with 134
tests, `python3 -B -m compileall scroll tests` passed, and `git diff --check`
passed.

Previous session (2026-05-11 — Codex quality-gate pass):

**Deposit quality gate hardened.** Scroll deposits now check for:
1. Near-duplicates against existing engram entries (Jaccard word similarity ≥ 70%)
2. Minimum body length (20 words — filters trivial entries)
3. Intra-batch duplicate detection (second similar entry in same deposit is caught)

Why: Reasoning audit found 16 of 33 scroll-deposited entries (48%) failed the "so what?" test (DEC-003). The deposit pipeline had no quality filter. Now it does.

Codex follow-up tightened the first uncommitted pass:
- Quality rejections are tracked separately from real system errors.
- CLI output no longer labels quality-gated entries as already deposited.
- `scroll deposit --no-quality-check` preserves a deliberate backfill escape hatch.
- Duplicate matching normalizes punctuation before Jaccard comparison.

Previous session (2026-03-27): Shipped v0.1.0 to PyPI. CI added. Deposit module wired.

### #1 Priority: Extraction verification

REVIEW.md (grade B) identified the core weakness: LLM extraction is unverified. The system extracts knowledge but has no way to know if it's accurate. A simple re-prompting check on 2-3 entries per batch catches obvious hallucinations. This is the single most important quality improvement.

### What NOT to do

- Don't add features before extraction verification — the foundation is untrustworthy until tested
- Don't refactor the pipeline — it works well structurally
- Don't build a web UI or dashboard — CLI-first, keep it lean

---

## Work

### Extraction verification (REVIEW Priority #1)

_LLM extraction hallucinations go undetected. The core value proposition is unverified._

- [x] Design verification approach — deterministic source-ref gate first; live re-prompt verifier remains future work
- [x] Build verification module — check batch source refs before saving extracted entries
- [x] Add extraction regression test — known commits → expected source-ref grounding behavior
- [ ] Run verification on existing scroll-extracted entries across projects
- [ ] Update REVIEW.md with findings
- [ ] Continue

### Ingestion improvements

_Usability and quality improvements from REVIEW.md._

- [ ] Add `--dry-run` to ingestion — show what would be processed + estimated cost
- [ ] Add synonym expansion to relevance scoring — 20-line map, big impact
- [ ] Pin model version in extractor.py — model update could silently change quality
- [ ] Continue

### Positioning

_Scroll is engram's extraction layer, not a standalone product._

- [ ] Update README to frame as "how you feed engram from git history"
- [ ] Update CLI help text to reference engram integration
- [ ] Consider: `scroll usage` command — grep agent sessions for scroll entry IDs
- [ ] Continue

### Done

<details>
<summary>Phase 1-4 + Shipping — completed 2026-03-27</summary>

- [x] Phase 1: incremental ingestion, validation, dedup, error recovery — `commit:9e1d818` (49 tests)
- [x] Phase 2: agent integration — MCP server, export, relevance engine — `commit:5cae31d` (63 tests)
- [x] Phase 3: multi-source — PRs, issues, review comments via GitHub API — `commit:d665626`
- [x] Phase 4: knowledge integrity — health scoring, staleness detection — `commit:7e38531` (97 tests)
- [x] scroll sync: guaranteed knowledge delivery — `commit:37f32ca`
- [x] Deposit module: scroll → engram bridge with source tracking — `commit:3e95e5e` (25 tests)
- [x] REVIEW.md: structured assessment, grade B — `commit:241c81b`
- [x] Self-extraction: CLAUDE.md from own git history — `commit:8b6c986`
- [x] Ship to PyPI as git-scroll v0.1.0 — `commit:0f41cff`
- [x] CI: run tests on push and PR — `commit:f44dea2`
- [x] README added — `commit:76bc8c3`
- [x] Deposit quality gate hardened — 129 tests passing
- [x] Deterministic extraction source-ref verification — 134 tests passing
- [x] Public CI/license repair — 2026-07-03 — valid install workflow, MIT LICENSE, pyproject readme/license metadata, external engram parser test isolated, 134 tests passing

</details>

---

## Decision Log

| ID | Date | Decision | Why |
|----|------|----------|-----|
| D-001 | 2026-03-19 | Incremental state tracking | Large repos expensive to reprocess. API rate limits. Error recovery. |
| D-002 | 2026-03-19 | Put knowledge where agents look (CLAUDE.md) | Don't require tool usage — guarantee delivery by putting it where agents already read. |
| D-003 | 2026-03-19 | Bridge to engram via deposit module | Enables knowledge flow from automated extraction to manual curation. State tracking prevents duplicates. |

---

## Session Log

### 2026-03-19 to 2026-03-20 — Core development (Session 1)

- **Worked on:** Full pipeline: git_reader → extractor → store → sync
- **Completed:** Phases 1-4 in one session. 97 tests. ~2,000 LOC.
- **Decisions:** D-001, D-002, D-003
- **State:** Working pipeline, not yet published

### 2026-03-26 — Deposit module (Session 2)

- **Worked on:** scroll deposit — push extracted knowledge into engram
- **Completed:** deposit.py (189 LOC), 25 tests, source:scroll field wired
- **State:** Ready to deposit, waiting for engram source field (shipped same day)

### 2026-03-27 — Ship + polish (Session 3)

- **Worked on:** PyPI release, README, CI, CLAUDE.md self-extraction
- **Completed:** v0.1.0 on PyPI, CI green, README written
- **State:** Shipped. 122 tests. Next: extraction verification.

### 2026-05-12 — Codex extraction-verification pass

- **Worked on:** Local verification of extracted entries against the source batch
- **Completed:** `scroll.verification`, ingest wiring for commits/PRs/issues, source-ref rejection, low-overlap warnings, and regression tests
- **Why:** LLM extraction could cite refs that were not present in the batch; that grounding failure is deterministic and should be caught before saving
- **State:** 134 tests passing. Next: live re-prompt verifier or audit existing extracted entries.

### 2026-07-03 — Codex public-readiness pass

- **Worked on:** Keep `scroll` public-worthy after repo review.
- **Completed:** Fixed GitHub Actions install command, added MIT LICENSE, added package readme/license metadata, and isolated the optional engram parser compatibility test from clean public CI.
- **State:** 134 tests passing locally; clean-CI no-engram path skips the external parser test; editable install metadata verified in `/tmp` venv. Next: commit/push and confirm GitHub Actions.

---

## How we work

- **Chunk by chunk.** One item. Fix. Test. Update CODEX.md. Commit. Repeat.
- **Find the seed.** Don't patch symptoms. Trace to root cause first.
- Universal rules in CLAUDE.md apply.

### Key reference files

| File | What it contains |
|------|-----------------|
| CODEX.md | This file. All tasks, decisions, sessions. |
| REVIEW.md | Structured assessment (grade B). 5 priority recommendations. |
| CLAUDE.md | scroll-extracted project knowledge (decisions, learnings). |
| .scroll/state.json | Ingestion state — which commits/PRs processed. |
| .scroll/deposit_state.json | Which entries deposited to engram. |
