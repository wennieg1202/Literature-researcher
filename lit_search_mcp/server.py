"""
Literature Search MCP Server
Exposes 3 tools to Claude Code:
  1. search_literature   — multi-source academic search
  2. export_to_notion    — push papers to Notion database
  3. download_pdfs       — download PDFs via Sci-Hub
"""

from __future__ import annotations
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure the package directory is on sys.path when invoked directly
sys.path.insert(0, str(Path(__file__).parent))

from mcp.server.fastmcp import FastMCP

from cache import Cache
from dedup import dedup, rank
from models import Paper
from notion_export import export_papers_to_notion
from query_expand import expand_query, get_search_terms
from search_apis import multi_search, ALL_SOURCES
from snowball import snowball

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)

mcp = FastMCP("lit_search")
_cache = Cache()


# ─── Tool 1: search_literature ───────────────────────────────────────────────

@mcp.tool()
async def search_literature(
    query: str,
    mode: str = "balanced",
    perspective: str = "",
    sources: Optional[List[str]] = None,
    max_results: int = 20,
    do_snowball: bool = False,
    bib_output: str = "results.bib",
) -> Dict[str, Any]:
    """
    Search academic literature across up to 8 sources and return ranked results.

    Args:
        query: A natural-language research question or keywords.
               Example: "How do professional jurisdictions shape AI adoption in medicine?"
        mode: Search strategy.
              "classic"  — prioritise foundational / high-citation works.
              "frontier" — prioritise publications from the last 2-3 years.
              "balanced" — weighted mix of citation impact and recency (default).
        perspective: Optional sociology theory lens to bias query expansion.
                     One of: "profession", "organization", "symbolic",
                             "stratification", "network", "knowledge".
                     Leave empty for a general search.
        sources: List of sources to query. Default = all available.
                 Options: "openalex", "s2", "crossref", "arxiv",
                          "google_books", "openlibrary", "core", "acm".
        max_results: Maximum results to fetch per source (default 20).
        do_snowball: If True, expand the top-5 results via 1-hop citation
                     snowballing (slower, but increases recall).
        bib_output: Filename for the BibTeX export (written to working directory).

    Returns:
        {
          "papers": [...],          // list of paper objects
          "stats": {...},           // source counts, total, dedup'd
          "bib_file": "path/...",   // absolute path to .bib file
          "expanded_query": {...},  // what the query was expanded to
        }
    """
    # 1. Expand query
    expanded = await expand_query(query, mode=mode, perspective=perspective)
    terms = get_search_terms(expanded)

    # 2. Multi-source search
    raw = await multi_search(terms, sources=sources, max_per_source=max_results, cache=_cache)

    stats_raw: dict[str, int] = {}
    for p in raw:
        for s in p.sources:
            stats_raw[s] = stats_raw.get(s, 0) + 1

    # 3. Dedup + rank
    unique = dedup(raw)
    ranked = rank(unique, mode=mode)

    # 4. Optional snowballing
    if do_snowball and ranked:
        primary_terms = expanded.get("primary_terms", terms[:4])

        # Prefer seeds that have at least one primary term in their title
        # (avoids using high-citation methodology papers as seeds)
        def _title_hits(p: Paper) -> int:
            text = (p.title or "").lower()
            return sum(1 for t in primary_terms if t.lower() in text)

        topical_seeds = [p for p in ranked if _title_hits(p) >= 1]
        seeds = (topical_seeds or ranked)[:5]  # fall back to top-5 if no match

        snow_papers = await snowball(seeds, top_n=5, cache=_cache,
                                     filter_terms=primary_terms)
        snow_added = len(snow_papers)
        combined = dedup(ranked + snow_papers)
        ranked = rank(combined, mode=mode)
        stats_raw["snowball_added"] = snow_added

    # Apply mode-based year filter for "frontier"
    if mode == "frontier":
        import datetime
        cutoff = datetime.datetime.now().year - 2
        frontier = [p for p in ranked if p.year and p.year >= cutoff]
        # Keep at least 10 results even if filter is aggressive
        ranked = frontier if len(frontier) >= 10 else ranked

    # 5. BibTeX export
    bib_path = Path(os.getcwd()) / bib_output
    with open(bib_path, "w", encoding="utf-8") as f:
        for p in ranked:
            f.write(p.to_bibtex())
            f.write("\n\n")

    return {
        "papers": [p.to_dict() for p in ranked],
        "stats": {
            "raw_total": len(raw),
            "after_dedup": len(ranked),
            "by_source": stats_raw,
        },
        "bib_file": str(bib_path),
        "expanded_query": expanded,
    }


# ─── Tool 2: export_to_notion ─────────────────────────────────────────────────

@mcp.tool()
async def export_to_notion(
    papers: List[Dict[str, Any]],
    notion_token: Optional[str] = None,
    database_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Export a list of papers to a Notion database.

    The default database is the Literature Knowledge Library.
    Fields written: Name (title), Year, Authors, DOI, Venue, Citations,
                    URL, Status (= "To Read"), and the abstract as page body.

    Args:
        papers: List of paper dicts as returned by search_literature.
        notion_token: Notion integration token. Defaults to the built-in token.
        database_id: Notion database ID. Defaults to the Literature Knowledge Library.

    Returns:
        {"pushed": N, "skipped": M, "errors": [...]}
    """
    paper_objects: List[Paper] = []
    for d in papers:
        from models import Author
        p = Paper(
            title=d.get("title") or "Untitled",
            year=d.get("year"),
            authors=[Author(name=a) for a in (d.get("authors") or [])],
            abstract=d.get("abstract"),
            doi=d.get("doi"),
            venue=d.get("venue"),
            url=d.get("url"),
            pdf_url=d.get("pdf_url"),
            citation_count=d.get("citation_count", 0),
            sources=d.get("sources", []),
        )
        paper_objects.append(p)

    result = await export_papers_to_notion(paper_objects, notion_token, database_id)
    return result


# ─── Tool 3: download_pdfs ────────────────────────────────────────────────────

@mcp.tool()
async def download_pdfs(
    papers: List[Dict[str, Any]],
    output_dir: str = "downloads",
) -> Dict[str, Any]:
    """
    Download PDFs for a list of papers using Sci-Hub (for DOI-based lookup)
    or direct PDF URLs where available.

    Papers without a DOI or direct PDF URL are skipped.

    Args:
        papers: List of paper dicts as returned by search_literature.
        output_dir: Directory to save PDFs (created if it doesn't exist).

    Returns:
        {
          "downloaded": [{"title": ..., "path": ..., "doi": ...}, ...],
          "failed":     [{"title": ..., "doi": ..., "reason": ...}, ...],
        }
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Add scihub package path (vendored in scihub_mcp/)
    scihub_pkg_path = str(Path(__file__).parent.parent / "scihub_mcp")
    if scihub_pkg_path not in sys.path:
        sys.path.insert(0, scihub_pkg_path)

    downloaded = []
    failed = []

    import httpx

    for paper in papers:
        title = paper.get("title") or "unknown"
        doi = paper.get("doi")
        pdf_url = paper.get("pdf_url")

        # Sanitize filename
        safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)[:80]
        filename = out_path / f"{safe_title}.pdf"

        # Try direct PDF URL first (arXiv, CORE, open access)
        if pdf_url:
            try:
                async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
                    r = await client.get(pdf_url)
                    if r.status_code == 200 and b"%PDF" in r.content[:8]:
                        filename.write_bytes(r.content)
                        downloaded.append({"title": title, "path": str(filename), "doi": doi, "source": "direct"})
                        continue
            except Exception as e:
                log.debug("Direct PDF download failed for '%s': %s", title, e)

        # Try Sci-Hub via DOI
        if doi:
            try:
                from scihub import SciHub
                sh = SciHub()
                sh.timeout = 30

                def _fetch_sync():
                    return sh.fetch(doi)

                result = await asyncio.to_thread(_fetch_sync)
                if result and result.get("url"):
                    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
                        r = await client.get(result["url"])
                        if r.status_code == 200 and b"%PDF" in r.content[:8]:
                            filename.write_bytes(r.content)
                            downloaded.append({"title": title, "path": str(filename), "doi": doi, "source": "scihub"})
                            continue
                failed.append({"title": title, "doi": doi, "reason": "scihub returned no valid PDF"})
            except Exception as e:
                failed.append({"title": title, "doi": doi, "reason": str(e)})
        else:
            failed.append({"title": title, "doi": None, "reason": "no DOI or PDF URL"})

    return {"downloaded": downloaded, "failed": failed}


# ─── entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")
