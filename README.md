# scroll

Your codebase already knows. Scroll extracts it.

## What It Does

Scroll reads git history, GitHub PRs, and issues, then uses LLM-powered extraction to produce structured knowledge entries: decisions, learnings, mistakes, observations, goals. These feed into [engram](https://github.com/SatishoBananamoto/engram) and agent instruction files (CLAUDE.md).

```bash
# Initialize in your repo
scroll init

# Extract knowledge from last 20 commits
scroll ingest -n 20 -p my-project

# Deposit into engram knowledge base
scroll deposit -p my-project

# Sync into CLAUDE.md for agent context
scroll sync -t claude
```

## The Pipeline

```
git log / GitHub PRs → LLM extraction → structured entries → engram deposit
                                                          → CLAUDE.md sync
                                                          → search/query
```

## Why Not Just Read Git Log?

Commit messages say WHAT changed. Scroll extracts WHY — the decisions, tradeoffs, and learnings buried in diffs and PR discussions.

From a commit diff:
```
-name = "caliber"
+name = "caliber-trust"
```

Scroll extracts:
> **DEC-001**: Changed PyPI distribution name from 'caliber' to 'caliber-trust'.
> The original name was already taken by an existing ML library.

## Commands

| Command | What it does |
|---------|-------------|
| `scroll init` | Initialize scroll in a repo |
| `scroll ingest` | Extract knowledge from git/GitHub |
| `scroll deposit` | Push entries into engram |
| `scroll sync` | Inject knowledge into CLAUDE.md |
| `scroll list` | List extracted entries |
| `scroll search` | Search entries by text |
| `scroll stats` | Show summary statistics |
| `scroll health` | Check knowledge base health |

## Requirements

- Python 3.10+
- An Anthropic API key (for LLM extraction)
- Git repository

## License

MIT
