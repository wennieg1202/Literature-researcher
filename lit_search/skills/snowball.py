"""Citation snowballing — 1-hop forward citation expansion.

For the top-N seed papers, fetch papers that cite them using:
  - Semantic Scholar (citations endpoint, rich metadata)
  - OpenAlex (cited_by endpoint, as fallback)

New papers found are deduped against the existing set and returned
as an incremental list so the caller can merge them.
"""

from __future__ import annotations

import asyncio
from typing import Optional

import httpx

from .. import config
from ..cache import Cache
from ..models import Author, Paper
from .dedup import deduplicate
from .search_apis import _s2_to_paper, _openalex_to_paper


_S2_CIT_FIELDS = (
    "paperId,externalIds,title,authors,year,abstract,"
    "citationCount,venue,journal,openAccessPdf"
)


async def _fetch_s2_citations(
    paper: Paper,
    client: httpx.AsyncClient,
    cache: Optional[Cache],
    sem: asyncio.Semaphore,
) -> list[Paper]:
    """Fetch papers that cite `paper` via Semantic Scholar."""
    if not paper.s2_id:
        return []

    url = f"{config.S2_PAPER_BASE}/{paper.s2_id}/citations"
    params = {
        "fields": f"citingPaper.{_S2_CIT_FIELDS}",
        "limit": 50,
    }

    async with sem:
        try:
            r = await client.get(url, params=params, timeout=20.0)
            r.raise_for_status()
            data = r.json()
        except Exception:
            return []
        await asyncio.sleep(config.SLEEP_S2)

    if cache:
        cache.set(url, params, data)

    papers = []
    for item in data.get("data", []):
        citing = item.get("citingPaper", {})
        p = _s2_to_paper(citing)
        if p:
            papers.append(p)
    return papers


async def _fetch_openalex_citations(
    paper: Paper,
    client: httpx.AsyncClient,
    cache: Optional[Cache],
    sem: asyncio.Semaphore,
) -> list[Paper]:
    """Fetch papers that cite `paper` via OpenAlex cited_by filter."""
    if not paper.openalex_id:
        return []

    params = {
        "filter": f"cites:W{paper.openalex_id}",
        "per-page": 50,
        "select": (
            "id,doi,title,authorships,publication_year,primary_location,"
            "cited_by_count,abstract_inverted_index,biblio,type"
        ),
        "mailto": config.CROSSREF_EMAIL or "user@example.com",
    }

    async with sem:
        try:
            r = await client.get(config.OPENALEX_BASE, params=params, timeout=20.0)
            r.raise_for_status()
            data = r.json()
        except Exception:
            return []

    if cache:
        cache.set(config.OPENALEX_BASE, params, data)

    papers = []
    for w in data.get("results", []):
        p = _openalex_to_paper(w)
        if p:
            papers.append(p)
    return papers


async def snowball(
    seed_papers: list[Paper],
    existing_papers: list[Paper],
    cache: Optional[Cache] = None,
    console=None,
) -> list[Paper]:
    """Fetch 1-hop forward citations for seed_papers; return new papers only."""
    sem_s2 = asyncio.Semaphore(config.SEM_S2)
    sem_oa = asyncio.Semaphore(config.SEM_OPENALEX)

    existing_dois = {p.doi for p in existing_papers if p.doi}
    existing_s2   = {p.s2_id for p in existing_papers if p.s2_id}

    headers = {"User-Agent": config.USER_AGENT}

    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        tasks = []
        for paper in seed_papers:
            tasks.append(_fetch_s2_citations(paper, client, cache, sem_s2))
            tasks.append(_fetch_openalex_citations(paper, client, cache, sem_oa))

        results = await asyncio.gather(*tasks, return_exceptions=True)

    found: list[Paper] = []
    for r in results:
        if isinstance(r, list):
            found.extend(r)

    # Dedup within snowball results
    found = deduplicate(found)

    # Filter out papers already in the corpus
    new_papers = [
        p for p in found
        if not (p.doi and p.doi in existing_dois)
        and not (p.s2_id and p.s2_id in existing_s2)
    ]

    if console:
        console.print(
            f"  [green]✓ Snowball:[/green] {len(new_papers)} new papers "
            f"(from {len(found)} citations across {len(seed_papers)} seeds)"
        )

    return new_papers
