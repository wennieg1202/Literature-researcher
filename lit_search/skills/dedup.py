"""Deduplication of Paper objects.

Strategy (applied in order):
1. DOI exact match — most reliable; merge duplicate entries.
2. arXiv ID exact match — for preprints without DOI.
3. Fuzzy title match (rapidfuzz) with year guard — catches records with no DOI
   or minor title variations across sources.

Merging preserves:
- Maximum citation count
- Union of sources list
- Best available abstract / venue / authors
"""

from __future__ import annotations

import math
from typing import Optional

from rapidfuzz import fuzz

from .. import config
from ..models import Paper


def deduplicate(papers: list[Paper]) -> list[Paper]:
    """Return a deduplicated list; duplicate records are merged."""
    # ── Pass 1: DOI buckets ──────────────────────────────────────────────────
    by_doi: dict[str, Paper] = {}
    no_doi: list[Paper] = []

    for p in papers:
        if p.doi and not p.doi.startswith("isbn:"):
            if p.doi in by_doi:
                by_doi[p.doi] = _merge(by_doi[p.doi], p)
            else:
                by_doi[p.doi] = p
        else:
            no_doi.append(p)

    # ── Pass 2: arXiv ID buckets (among no_doi) ───────────────────────────────
    by_arxiv: dict[str, Paper] = {}
    still_no_id: list[Paper] = []

    for p in no_doi:
        if p.arxiv_id:
            if p.arxiv_id in by_arxiv:
                by_arxiv[p.arxiv_id] = _merge(by_arxiv[p.arxiv_id], p)
            else:
                by_arxiv[p.arxiv_id] = p
        else:
            still_no_id.append(p)

    # ── Pass 3: fuzzy title on remaining ────────────────────────────────────
    dedupd_no_id = _fuzzy_dedup(still_no_id)

    return list(by_doi.values()) + list(by_arxiv.values()) + dedupd_no_id


def _fuzzy_dedup(papers: list[Paper]) -> list[Paper]:
    """O(n²) fuzzy dedup; acceptable for the typical <500-paper tail."""
    canonical: list[Paper] = []

    for p in papers:
        matched = False
        for i, c in enumerate(canonical):
            if _is_duplicate(p, c):
                canonical[i] = _merge(c, p)
                matched = True
                break
        if not matched:
            canonical.append(p)

    return canonical


def _is_duplicate(a: Paper, b: Paper) -> bool:
    if not a.title or not b.title:
        return False

    # Year guard: allow ±1 year (reprints, preprint → published)
    if a.year and b.year and abs(a.year - b.year) > 1:
        return False

    score = fuzz.ratio(a.title.lower(), b.title.lower())
    return score >= config.DEDUP_TITLE_THRESHOLD


def _merge(base: Paper, other: Paper) -> Paper:
    """Merge `other` into `base`, keeping the best data from each."""
    # Union sources
    sources = list(dict.fromkeys(base.sources + other.sources))

    # Keep max citation count
    citations = max(base.citation_count, other.citation_count)

    # Prefer non-None values from base, fall back to other
    def pick(a, b):
        return a if a is not None else b

    # For authors: prefer the longer list
    authors = base.authors if len(base.authors) >= len(other.authors) else other.authors

    # For abstract: prefer longer
    abstract = base.abstract
    if other.abstract and (not abstract or len(other.abstract) > len(abstract)):
        abstract = other.abstract

    return Paper(
        title=base.title,
        year=pick(base.year, other.year),
        doi=pick(base.doi, other.doi),
        arxiv_id=pick(base.arxiv_id, other.arxiv_id),
        s2_id=pick(base.s2_id, other.s2_id),
        openalex_id=pick(base.openalex_id, other.openalex_id),
        authors=authors,
        venue=pick(base.venue, other.venue),
        volume=pick(base.volume, other.volume),
        issue=pick(base.issue, other.issue),
        pages=pick(base.pages, other.pages),
        publisher=pick(base.publisher, other.publisher),
        url=pick(base.url, other.url),
        entry_type_hint=pick(base.entry_type_hint, other.entry_type_hint),
        abstract=abstract,
        citation_count=citations,
        sources=sources,
        relevance_score=base.relevance_score,
    )


def rank(papers: list[Paper]) -> list[Paper]:
    """Assign relevance_score and return sorted list (descending)."""
    for p in papers:
        # log-scaled citation count + bonus for appearing in multiple sources
        p.relevance_score = math.log1p(p.citation_count) + 2.0 * len(p.sources)
    papers.sort(key=lambda p: p.relevance_score, reverse=True)
    return papers
