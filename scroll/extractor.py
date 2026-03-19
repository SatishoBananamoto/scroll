"""LLM-powered knowledge extraction from git history."""

import anthropic


EXTRACTION_TOOL = {
    "name": "record_knowledge",
    "description": "Record structured knowledge entries extracted from git history",
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
                            "description": "Short hashes of commits this entry is derived from",
                        },
                    },
                    "required": ["entry_type", "title", "tags", "body", "confidence", "source_commits"],
                },
            },
        },
        "required": ["entries"],
    },
}


SYSTEM_PROMPT = """You are a knowledge extraction system. You analyze git commit history and extract structured knowledge entries.

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
- NOT every commit has extractable knowledge. Skip trivial commits (typo fixes, formatting, version bumps) unless they form a pattern.
- Synthesize across related commits. A series of commits implementing a feature should yield one or two entries, not one per commit.
- The body MUST use the required markdown sections for each type.
- Tags should be lowercase, specific, and useful for filtering.
- Be conservative: only extract knowledge that is genuinely useful. Quality over quantity.
- Confidence: high = clear evidence in commits, medium = reasonable inference, low = speculative.
- Source each entry to the specific commit short hash(es) it came from.
- If there is no extractable knowledge in the batch, return an empty entries array."""


def extract_knowledge(commits_text: str, model: str = "claude-sonnet-4-6") -> list[dict]:
    """Extract knowledge entries from formatted git commits.

    Returns list of entry dicts with keys: entry_type, title, tags, body, confidence, source_commits.
    """
    client = anthropic.Anthropic()

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        tools=[EXTRACTION_TOOL],
        tool_choice={"type": "tool", "name": "record_knowledge"},
        messages=[{
            "role": "user",
            "content": f"Extract knowledge from these git commits:\n\n{commits_text}",
        }],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "record_knowledge":
            return block.input.get("entries", [])

    return []
