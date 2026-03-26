"""Query expansion via Claude.

Takes a natural-language user query and returns a structured dict of
expanded search terms tailored for different academic databases.

Falls back to a simple split if ANTHROPIC_API_KEY is not set.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from .. import config

_SYSTEM = """\
You are a systematic literature review specialist. Given a research query, \
produce expanded search terms in JSON.

Return ONLY valid JSON matching this schema exactly:
{
  "primary_terms": ["...", "..."],   // 2-4 concise core terms
  "synonyms": ["...", "..."],        // 3-6 alternative phrasings
  "mesh_terms": ["...", "..."],      // 0-4 MeSH/thesaurus terms (empty list if not applicable)
  "boolean_string": "...",          // one combined boolean search string
  "scope_note": "..."               // one sentence describing the search scope
}

Rules:
- primary_terms: short (1-3 words), high-precision terms
- synonyms: include plurals, acronyms, related concepts
- boolean_string: use AND/OR/NOT, quote multi-word phrases
- Keep all terms in English unless the query is in another language
"""


def expand(query: str) -> dict:
    """Return expanded query dict. Falls back gracefully if no API key."""
    if not config.ANTHROPIC_API_KEY:
        return _fallback(query)

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=config.MAX_TOKENS_EXPAND,
            system=_SYSTEM,
            messages=[{"role": "user", "content": query}],
        )
        text = msg.content[0].text.strip()
        # Strip markdown fences if present
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        result = json.loads(text)
        # Validate required keys
        for key in ("primary_terms", "synonyms", "boolean_string"):
            if key not in result:
                raise ValueError(f"Missing key: {key}")
        result.setdefault("mesh_terms", [])
        result.setdefault("scope_note", "")
        return result
    except Exception:
        return _fallback(query)


def _fallback(query: str) -> dict:
    """Minimal expansion when Claude is unavailable."""
    terms = [t.strip() for t in query.split() if len(t.strip()) > 2]
    primary = [query]
    return {
        "primary_terms": primary,
        "synonyms": terms[:4],
        "mesh_terms": [],
        "boolean_string": " AND ".join(f'"{t}"' if " " in t else t for t in primary),
        "scope_note": f"Direct search for: {query}",
    }


def all_terms(expanded: dict) -> list[str]:
    """Flatten expanded dict into a deduplicated list of search strings."""
    seen: set[str] = set()
    result: list[str] = []
    for term in expanded.get("primary_terms", []) + expanded.get("synonyms", []):
        t = term.strip()
        if t and t.lower() not in seen:
            seen.add(t.lower())
            result.append(t)
    return result
