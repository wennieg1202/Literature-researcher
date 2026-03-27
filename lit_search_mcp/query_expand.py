"""
Query expansion — pure keyword-based, no external API calls.
Combines the user's query words with perspective seed terms.
Results are cached in-session to avoid redundant work.
"""

from __future__ import annotations
import logging

from sociology import get_perspective_seeds

log = logging.getLogger(__name__)

_EXPANSION_CACHE: dict[str, dict] = {}


def _expand(query: str, perspective: str, mode: str) -> dict:
    terms = [t.strip() for t in query.replace("?", " ").split() if len(t.strip()) > 3]
    seeds = get_perspective_seeds(perspective)[:4] if perspective else []
    primary = list(dict.fromkeys(terms[:4] + seeds[:2]))[:6]
    synonyms = list(dict.fromkeys(seeds[2:6] if seeds else terms[4:8]))

    # For "frontier" mode, prepend recency modifiers to the boolean string
    recency = ' AND ("recent" OR "emerging" OR "new")' if mode == "frontier" else ""
    boolean_string = " AND ".join(f'"{t}"' for t in primary[:3]) + recency

    return {
        "primary_terms": primary,
        "synonyms": synonyms,
        "boolean_string": boolean_string,
        "scope_note": f"Keyword search ({mode}) for: {query}",
        "question_reframe": query,
    }


async def expand_query(
    query: str,
    mode: str = "balanced",
    perspective: str = "",
) -> dict:
    """Return structured search terms for the given query, mode, and perspective.
    Results are cached per (query, mode, perspective) for the session lifetime."""
    cache_key = f"{query}|{mode}|{perspective}"
    if cache_key not in _EXPANSION_CACHE:
        _EXPANSION_CACHE[cache_key] = _expand(query, perspective, mode)
    return _EXPANSION_CACHE[cache_key]


def get_search_terms(expanded: dict) -> list[str]:
    """Flatten expanded query into a deduplicated list of search terms."""
    terms = list(expanded.get("primary_terms", []))
    terms += list(expanded.get("synonyms", []))[:4]
    return list(dict.fromkeys(terms))
