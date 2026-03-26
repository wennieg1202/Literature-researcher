"""Query expansion via Claude.

Supports three enhancements over basic keyword search:
1. Search mode: 'classic' (high citation), 'frontier' (latest), 'balanced' (default)
2. Sociological perspective: injects theory lineage context into the prompt
3. Question-based input: detects research questions and extracts theoretical constructs

Falls back to a simple split if ANTHROPIC_API_KEY is not set.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from .. import config

# ── Prompt templates ──────────────────────────────────────────────────────────

_SYSTEM_BASE = """\
You are a systematic literature review specialist with deep expertise in sociology \
and social science research. Given a research input, produce expanded search terms in JSON.

Return ONLY valid JSON matching this schema exactly (no markdown fences):
{{
  "primary_terms": ["...", "..."],
  "synonyms": ["...", "..."],
  "mesh_terms": ["...", "..."],
  "boolean_string": "...",
  "scope_note": "...",
  "question_reframe": "..."
}}

Field rules:
- primary_terms: 3-5 high-precision terms (1-4 words each)
- synonyms: 4-8 alternative phrasings, related concepts, acronyms
- mesh_terms: 0-4 MeSH or thesaurus-style controlled vocabulary terms (empty list if not applicable)
- boolean_string: one combined boolean string using AND/OR/NOT with quoted phrases
- scope_note: one sentence describing the search scope and theoretical angle
- question_reframe: if the input is a research question, restate it as a declarative
  search hypothesis; otherwise set to empty string ""
{perspective_section}
{mode_section}
"""

_PERSPECTIVE_SECTION = """\

IMPORTANT — Theoretical perspective filter:
{context}

Bias your term selection toward this tradition. Include key theorists' names as search terms \
where relevant (e.g., "Bourdieu habitus", "Abbott jurisdiction"). Add perspective-specific \
jargon as primary_terms or synonyms.
"""

_MODE_SECTION_CLASSIC = """\

Search goal: CLASSIC THEORY INSIGHTS
The user wants highly cited, foundational works. Emphasize:
- Canonical terminology established in seminal papers (1960s-2010s)
- Theorists' own keywords and framing
- Terms that appear in highly cited reviews and handbooks
- Avoid very recent or niche jargon
"""

_MODE_SECTION_FRONTIER = """\

Search goal: FRONTIER RESEARCH
The user wants the latest developments (last 3-5 years). Emphasize:
- Emerging terminology and neologisms
- Computational/mixed-methods extensions of classic theories
- Current debates, critiques, and extensions
- Conference paper language and working-paper phrasings
- Explicitly add "2020", "2021", "2022", "2023", "2024" as date context in boolean_string
"""

_QUESTION_PREAMBLE = """\
The input below is a RESEARCH QUESTION, not a keyword query.
Before generating search terms:
1. Identify the implicit dependent variable (what is being explained)
2. Identify the key mechanism or theoretical claim
3. Identify the level of analysis (individual / organizational / field / societal)
4. Map these to canonical sociological constructs

Then generate search terms targeting those constructs, not just the surface words of the question.

"""


# ── Main expand function ──────────────────────────────────────────────────────

def expand(
    query: str,
    mode: str = "balanced",
    perspective: Optional[str] = None,
) -> dict:
    """Return expanded query dict.

    Args:
        query: Natural language query or research question.
        mode: 'balanced' | 'classic' | 'frontier'
        perspective: sociology perspective key from sociology.PERSPECTIVES, or None.
    """
    if not config.ANTHROPIC_API_KEY:
        return _fallback(query)

    is_question = _detect_question(query)

    try:
        import anthropic
        from .. import sociology

        # Build system prompt
        perspective_section = ""
        if perspective:
            ctx = sociology.perspective_context(perspective)
            if ctx:
                perspective_section = _PERSPECTIVE_SECTION.format(context=ctx)

        mode_section = ""
        if mode == "classic":
            mode_section = _MODE_SECTION_CLASSIC
        elif mode == "frontier":
            mode_section = _MODE_SECTION_FRONTIER

        system = _SYSTEM_BASE.format(
            perspective_section=perspective_section,
            mode_section=mode_section,
        )

        user_content = query
        if is_question:
            user_content = _QUESTION_PREAMBLE + query

        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=config.MAX_TOKENS_EXPAND,
            system=system,
            messages=[{"role": "user", "content": user_content}],
        )
        text = msg.content[0].text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        result = json.loads(text)

        for key in ("primary_terms", "synonyms", "boolean_string"):
            if key not in result:
                raise ValueError(f"Missing key: {key}")
        result.setdefault("mesh_terms", [])
        result.setdefault("scope_note", "")
        result.setdefault("question_reframe", "")
        result["_is_question"] = is_question
        result["_mode"] = mode
        result["_perspective"] = perspective

        # Inject perspective seed terms if applicable
        if perspective:
            p = sociology.get_perspective(perspective)
            if p:
                for seed in p.get("seed_terms", []):
                    if seed.lower() not in [t.lower() for t in result["primary_terms"]]:
                        result["synonyms"].append(seed)

        return result

    except Exception:
        return _fallback(query)


# ── Question detection ────────────────────────────────────────────────────────

_QUESTION_STARTERS = re.compile(
    r"^(what|why|how|when|where|who|which|is|are|does|do|can|could|would|should|"
    r"to what extent|in what way|under what condition)",
    re.IGNORECASE,
)


def _detect_question(query: str) -> bool:
    q = query.strip()
    return q.endswith("?") or bool(_QUESTION_STARTERS.match(q))


# ── Fallback ──────────────────────────────────────────────────────────────────

def _fallback(query: str) -> dict:
    """Minimal expansion when Claude is unavailable."""
    terms = [t.strip() for t in re.split(r"\s+", query) if len(t.strip()) > 2]
    primary = [query]
    return {
        "primary_terms": primary,
        "synonyms": terms[:4],
        "mesh_terms": [],
        "boolean_string": " AND ".join(f'"{t}"' if " " in t else t for t in primary),
        "scope_note": f"Direct search for: {query}",
        "question_reframe": "",
        "_is_question": False,
        "_mode": "balanced",
        "_perspective": None,
    }


# ── Term list extraction ──────────────────────────────────────────────────────

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
