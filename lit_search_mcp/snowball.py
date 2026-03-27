"""
1-hop citation snowballing via Semantic Scholar and OpenAlex.
Expands a seed set of papers by fetching their references (backwards) and
citations (forwards).
"""

from __future__ import annotations
import asyncio
import logging
from typing import List, Optional

import httpx

from models import Author, Paper
from cache import Cache
from search_apis import UA

log = logging.getLogger(__name__)


async def _s2_expand(paper: Paper, client: httpx.AsyncClient,
                     cache: Optional[Cache], sem: asyncio.Semaphore) -> List[Paper]:
    """Fetch references + citations for one paper via S2 API."""
    paper_id = paper.s2_id or (f"DOI:{paper.doi}" if paper.doi else None)
    if not paper_id:
        return []

    results: List[Paper] = []
    for endpoint in ("references", "citations"):
        url = f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}/{endpoint}"
        params = {"fields": "title,year,authors,externalIds,citationCount", "limit": 20}
        async with sem:
            try:
                if cache:
                    hit = cache.get(url, params)
                    if hit is not None:
                        data = hit
                    else:
                        r = await client.get(url, params=params, timeout=20.0)
                        r.raise_for_status()
                        data = r.json()
                        cache.set(url, params, data)
                else:
                    r = await client.get(url, params=params, timeout=20.0)
                    r.raise_for_status()
                    data = r.json()
                await asyncio.sleep(0.3)
            except Exception as e:
                log.warning("S2 %s expand failed for %s: %s", endpoint, paper_id, e)
                continue

        for item in data.get("data", []):
            cited = item.get("citedPaper") or item.get("citingPaper") or {}
            title = cited.get("title") or ""
            if not title:
                continue
            ext = cited.get("externalIds") or {}
            authors = [Author(name=a.get("name", "")) for a in cited.get("authors", []) if a.get("name")]
            results.append(Paper(
                title=title,
                year=cited.get("year"),
                authors=authors,
                doi=ext.get("DOI"),
                arxiv_id=ext.get("ArXiv"),
                s2_id=cited.get("paperId"),
                citation_count=cited.get("citationCount", 0),
                sources=["s2_snowball"],
            ))
    return results


def _is_relevant(paper: Paper, filter_terms: List[str]) -> bool:
    """Return True if the paper title contains at least one filter term."""
    if not filter_terms:
        return True
    text = (paper.title or "").lower()
    return any(t.lower() in text for t in filter_terms)


async def snowball(
    seed_papers: List[Paper],
    top_n: int = 5,
    cache: Optional[Cache] = None,
    filter_terms: Optional[List[str]] = None,
) -> List[Paper]:
    """
    Expand top_n seed papers via 1-hop snowballing.
    filter_terms: if provided, only keep new papers whose titles contain
    at least one of these terms (prevents citation-graph drift into
    unrelated disciplines).
    Returns the new papers found (not deduplicated against seeds yet).
    """
    seeds = seed_papers[:top_n]
    sem = asyncio.Semaphore(2)
    async with httpx.AsyncClient(headers={"User-Agent": UA}) as client:
        tasks = [_s2_expand(p, client, cache, sem) for p in seeds]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    new_papers: List[Paper] = []
    for res in results:
        if isinstance(res, list):
            new_papers.extend(res)

    if filter_terms:
        before = len(new_papers)
        new_papers = [p for p in new_papers if _is_relevant(p, filter_terms)]
        log.info("Snowball relevance filter: %d → %d papers (kept %d)",
                 before, len(new_papers), len(new_papers))

    return new_papers
