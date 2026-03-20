"""LLM-powered knowledge extraction from git history, PRs, and issues."""

import anthropic


EXTRACTION_TOOL = {
    "name": "record_knowledge",
    "description": "Record structured knowledge entries extracted from development history",
    "input_schema": {
        "type": "object",
        "properties": {
            "entries": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "entry_type": {
                            "type": "string",
                            "enum": ["decision", "learning", "mistake", "observation", "goal"],
                        },
                        "title": {
                            "type": "string",
                            "description": "One-line summary of the knowledge",
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Lowercase tags for filtering",
                        },
                        "body": {
                            "type": "string",
                            "description": "Structured markdown body with required sections",
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                        "source_commits": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Source references: commit short hashes, PR numbers (PR#42), or issue numbers (I#15)",
                        },
                    },
                    "required": ["entry_type", "title", "tags", "body", "confidence", "source_commits"],
                },
            },
        },
        "required": ["entries"],
    },
}


SYSTEM_PROMPT = """You are a knowledge extraction system. You analyze development history — git commits, pull requests, issues, and review comments — and extract structured knowledge entries.

Entry types and their REQUIRED markdown sections:

- decision: A choice that was made with reasoning
  Sections: ## Context, ## Choice, ## Reasoning, ## Alternatives Considered

- learning: Something discovered through the work
  Sections: ## Context, ## What Happened, ## Insight, ## Applies To

- mistake: Something that went wrong and was fixed
  Sections: ## Context, ## What Went Wrong, ## Root Cause, ## Prevention

- observation: A pattern noticed across the history
  Sections: ## Context, ## Observation, ## Significance

- goal: An objective being worked toward
  Sections: ## Objective, ## Success Criteria, ## Current Status

Rules:
- NOT every item has extractable knowledge. Skip trivial commits, bot PRs, and low-signal items.
- Synthesize across related items. Multiple commits in one PR should yield entries about the PR, not per-commit.
- PR descriptions and review comments are the RICHEST source. Extract the reasoning, debates, and alternatives from them.
- Review comments often contain rejected alternatives — capture these in the "Alternatives Considered" section.
- Bug fix PRs and issues with resolution often contain mistake patterns — extract the root cause and prevention.
- The body MUST use the required markdown sections for each type.
- Tags should be lowercase, specific, and useful for filtering.
- Be conservative: only extract knowledge that is genuinely useful. Quality over quantity.
- Confidence: high = explicit in the source, medium = reasonable inference, low = speculative.
- Source references: use commit short hashes for commits, PR#N for pull requests, I#N for issues.
- IMPORTANT: Only state facts that are explicitly present in or directly supported by the source material. Do NOT fabricate details, root causes, or prevention steps that aren't evidenced in the input.
- If there is no extractable knowledge, return an empty entries array."""


def extract_knowledge(source_text: str, model: str = "claude-sonnet-4-6") -> list[dict]:
    """Extract knowledge entries from formatted development history.

    source_text can contain commits, PRs, issues, or any mix.
    Returns list of entry dicts.
    """
    client = anthropic.Anthropic()

    response = client.messages.create(
        model=model,
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        tools=[EXTRACTION_TOOL],
        tool_choice={"type": "tool", "name": "record_knowledge"},
        messages=[{
            "role": "user",
            "content": f"Extract knowledge from this development history:\n\n{source_text}",
        }],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "record_knowledge":
            return block.input.get("entries", [])

    return []
