"""
Literature Search MCP Server
Exposes 3 tools to Claude Code:
  1. search_literature   — multi-source academic search
  2. export_to_notion    — push papers to Notion database
  3. download_pdfs       — download PDFs via Sci-Hub
"""

from __future__ import annotations
import asyncio
import datetime
import httpx
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
from models import Author, Paper
from notion_export import export_summary_to_notion
from query_expand import expand_query, get_search_terms
from search_apis import multi_search
from snowball import snowball
from sociology import list_perspectives, save_perspective

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
    bib_output: str = "papers/results.bib",
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
        cutoff = datetime.datetime.now().year - 2
        frontier = [p for p in ranked if p.year and p.year >= cutoff]
        # Keep at least 10 results even if filter is aggressive
        ranked = frontier if len(frontier) >= 10 else ranked

    # 5. BibTeX export
    bib_path = Path(os.getcwd()) / bib_output
    bib_path.parent.mkdir(parents=True, exist_ok=True)
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
    query: str = "",
    mode: str = "balanced",
    perspective: str = "",
    stats: Optional[Dict[str, Any]] = None,
    notion_token: Optional[str] = None,
    database_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Export search results as a single summary page in Notion.

    Creates ONE page containing the search parameters and a ranked paper list
    (top 50). Uses at most 2 API calls regardless of result size.

    Args:
        papers: List of paper dicts as returned by search_literature.
        query: Original search query (used as page title context).
        mode: Search mode used ("classic", "frontier", "balanced").
        perspective: Sociology perspective used, if any.
        stats: Stats dict from search_literature (source breakdown, counts).
        notion_token: Notion integration token. Defaults to env NOTION_API_KEY.
        database_id: Notion database ID. Defaults to env NOTION_DATABASE_ID.

    Returns:
        {"page_id": ..., "url": ..., "papers_shown": N, "total_papers": N, "errors": [...]}
    """
    paper_objects = [
        Paper(
            title=d.get("title") or "Untitled",
            year=d.get("year"),
            authors=[Author(name=a) for a in (d.get("authors") or [])],
            doi=d.get("doi"),
            url=d.get("url"),
            pdf_url=d.get("pdf_url"),
            citation_count=d.get("citation_count", 0),
        )
        for d in papers
    ]
    return await export_summary_to_notion(
        papers=paper_objects,
        query=query,
        mode=mode,
        perspective=perspective,
        stats=stats or {},
        notion_token=notion_token,
        database_id=database_id,
    )


# ─── Tool 3: download_pdfs ────────────────────────────────────────────────────

@mcp.tool()
async def download_pdfs(
    papers: List[Dict[str, Any]],
    output_dir: str = "papers/downloads",
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


# ─── Tool 4: add_perspective ──────────────────────────────────────────────────

@mcp.tool()
async def add_perspective(
    key: str,
    label: str,
    theorists: List[str],
    core_concepts: List[str],
    seed_terms: List[str],
) -> Dict[str, Any]:
    """
    Add a new research perspective to the library (persisted across sessions).

    Call this automatically when:
    - The user mentions a theoretical lens or discipline not yet in the library.
    - A search query implies a perspective that has no matching key.
    Use Claude's knowledge to generate appropriate theorists, concepts and terms
    if the user only provides a name.

    Args:
        key: Short snake_case identifier, e.g. "critical_realism".
        label: Human-readable name, e.g. "Critical Realism".
        theorists: Key scholars, e.g. ["Bhaskar", "Archer", "Sayer"].
        core_concepts: 6-12 central theoretical concepts.
        seed_terms: 6-12 database-friendly search phrases.

    Returns:
        {"saved": True/False, "key": key, "all_perspectives": {key: label, ...}}
    """
    ok = await asyncio.to_thread(
        save_perspective, key, label, theorists, core_concepts, seed_terms
    )
    return {
        "saved": ok,
        "key": key.strip().lower().replace(" ", "_"),
        "all_perspectives": list_perspectives(),
    }


@mcp.tool()
async def list_perspectives_tool() -> Dict[str, Any]:
    """
    List all available research perspectives (built-in + custom).

    Returns:
        {"perspectives": {"key": "Label", ...}, "total": N}
    """
    all_p = list_perspectives()
    return {"perspectives": all_p, "total": len(all_p)}


# ─── entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")
