"""
Deduplication and ranking of papers.
Strategy: DOI exact match → fuzzy title match → rank by mode.
"""

from __future__ import annotations
import datetime
import logging
from typing import List

from models import Paper

log = logging.getLogger(__name__)

try:
    from rapidfuzz import fuzz
    _HAS_RAPIDFUZZ = True
except ImportError:
    _HAS_RAPIDFUZZ = False
    log.warning("rapidfuzz not installed, falling back to exact title match")

FUZZY_THRESHOLD = 88  # title similarity threshold (0-100)
CURRENT_YEAR = datetime.datetime.now().year


def _norm(title: str) -> str:
    return " ".join(title.lower().split())


def dedup(papers: List[Paper]) -> List[Paper]:
    """
    Remove duplicate papers.
    - First pass: merge by DOI (exact)
    - Second pass: merge by fuzzy title similarity
    Merged papers accumulate all sources.
    """
    # DOI pass
    doi_map: dict[str, Paper] = {}
    no_doi: List[Paper] = []
    for p in papers:
        if p.doi:
            key = p.doi.lower().strip()
            if key in doi_map:
                existing = doi_map[key]
                existing.sources = list(set(existing.sources + p.sources))
                existing.citation_count = max(existing.citation_count, p.citation_count)
                if not existing.abstract and p.abstract:
                    existing.abstract = p.abstract
                if not existing.pdf_url and p.pdf_url:
                    existing.pdf_url = p.pdf_url
            else:
                doi_map[key] = p
        else:
            no_doi.append(p)

    unique: List[Paper] = list(doi_map.values())

    # Title fuzzy pass for no-doi papers
    for p in no_doi:
        norm_title = _norm(p.title)
        merged = False
        for existing in unique:
            if _HAS_RAPIDFUZZ:
                score = fuzz.token_sort_ratio(norm_title, _norm(existing.title))
            else:
                score = 100 if norm_title == _norm(existing.title) else 0
            if score >= FUZZY_THRESHOLD:
                existing.sources = list(set(existing.sources + p.sources))
                existing.citation_count = max(existing.citation_count, p.citation_count)
                if not existing.abstract and p.abstract:
                    existing.abstract = p.abstract
                if not existing.doi and p.doi:
                    existing.doi = p.doi
                if not existing.pdf_url and p.pdf_url:
                    existing.pdf_url = p.pdf_url
                merged = True
                break
        if not merged:
            unique.append(p)

    return unique


def rank(papers: List[Paper], mode: str = "balanced") -> List[Paper]:
    """
    Rank papers by mode:
    - classic:  citation_count descending
    - frontier: recency descending (year, then citation)
    - balanced: weighted score (0.6 * norm_citations + 0.4 * norm_recency)
    """
    if not papers:
        return papers

    max_cites = max((p.citation_count for p in papers), default=1) or 1
    min_year = min((p.year for p in papers if p.year), default=CURRENT_YEAR)
    year_range = max(CURRENT_YEAR - min_year, 1)

    for p in papers:
        norm_cites = p.citation_count / max_cites
        norm_recency = ((p.year or min_year) - min_year) / year_range
        source_bonus = 0.05 * len(p.sources)  # appearing in more sources = higher quality

        if mode == "classic":
            p.relevance_score = norm_cites + source_bonus
        elif mode == "frontier":
            p.relevance_score = 0.8 * norm_recency + 0.2 * norm_cites + source_bonus
        else:  # balanced
            p.relevance_score = 0.5 * norm_cites + 0.4 * norm_recency + source_bonus

    return sorted(papers, key=lambda p: p.relevance_score, reverse=True)
