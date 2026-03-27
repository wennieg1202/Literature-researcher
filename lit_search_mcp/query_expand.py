"""
Claude-powered query expansion.
Converts a natural-language question or keywords into structured search terms,
optionally applying a sociology perspective and search mode.
"""

from __future__ import annotations
import json
import logging
import os
from typing import Optional

from sociology import get_perspective_seeds, get_perspective_label

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are an expert academic research assistant specializing in systematic literature search.
Your task is to expand a user's query into optimized search terms for academic databases.

Given:
- A query (question or keywords)
- A search mode: "classic" (foundational/high-citation), "frontier" (recent 2-3 years), or "balanced"
- An optional sociology perspective with seed terms

Return ONLY a valid JSON object with these fields:
{
  "primary_terms": ["term1", "term2", ...],   // 3-6 core search terms
  "synonyms": ["alt1", "alt2", ...],           // 4-8 synonyms/related concepts
  "boolean_string": "term1 AND (term2 OR term3)",  // boolean query for databases
  "scope_note": "one sentence explaining the search strategy",
  "question_reframe": "the query reframed as a precise academic question"
}

Guidelines:
- For "classic" mode: include established theoretical terms, key author names
- For "frontier" mode: include "recent", "emerging", "new", contemporary terms
- For "balanced" mode: mix both
- Incorporate any provided perspective seed terms where relevant
- Keep terms concise and database-friendly (no full sentences)
"""


def _fallback_expand(query: str, perspective: str, mode: str) -> dict:
    """Simple fallback when Claude is unavailable."""
    terms = [t.strip() for t in query.replace("?", " ").split() if len(t.strip()) > 3]
    seeds = get_perspective_seeds(perspective)[:3] if perspective else []
    primary = (terms[:4] + seeds[:2])[:6]
    return {
        "primary_terms": primary,
        "synonyms": seeds[2:6] if seeds else terms[4:8],
        "boolean_string": " AND ".join(f'"{t}"' for t in primary[:3]),
        "scope_note": f"Keyword-based search for: {query}",
        "question_reframe": query,
    }


async def expand_query(
    query: str,
    mode: str = "balanced",
    perspective: str = "",
) -> dict:
    """
    Expand query using Claude API.
    Falls back to simple split if ANTHROPIC_API_KEY is not set.
    Returns a dict with primary_terms, synonyms, boolean_string, scope_note, question_reframe.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        log.warning("ANTHROPIC_API_KEY not set, using fallback query expansion")
        return _fallback_expand(query, perspective, mode)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        perspective_label = get_perspective_label(perspective)
        seeds = get_perspective_seeds(perspective)

        user_content = f"Query: {query}\nMode: {mode}"
        if perspective_label:
            user_content += f"\nPerspective: {perspective_label}"
        if seeds:
            user_content += f"\nPerspective seed terms: {', '.join(seeds[:10])}"

        response = client.messages.create(
            model=os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001"),
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        text = response.content[0].text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        result = json.loads(text)
        # Validate required fields
        for field in ("primary_terms", "synonyms", "boolean_string"):
            if field not in result:
                raise ValueError(f"Missing field: {field}")
        return result
    except Exception as e:
        log.warning("Claude query expansion failed (%s), using fallback", e)
        return _fallback_expand(query, perspective, mode)


def get_search_terms(expanded: dict) -> list[str]:
    """Flatten expanded query into a single list of search terms."""
    terms = list(expanded.get("primary_terms", []))
    terms += list(expanded.get("synonyms", []))[:4]
    return list(dict.fromkeys(terms))  # deduplicate, preserve order
