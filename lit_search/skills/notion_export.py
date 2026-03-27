"""Notion knowledge base export.

Saves papers to a Notion database. Each paper becomes one database entry.

Setup required:
  1. Go to https://www.notion.so/my-integrations → New integration → copy Secret
  2. Create or open a Notion database page → Share → invite your integration
  3. Copy the database ID from the URL:
       https://notion.so/your-workspace/{DATABASE_ID}?v=...
  4. Set environment variables:
       export NOTION_API_KEY=secret_...
       export NOTION_DATABASE_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

Database properties created automatically on first use:
  Title, Authors, Year, DOI, Venue, Abstract, Sources,
  Citation Count, Search Query, Mode, Perspective, URL
"""

from __future__ import annotations

import asyncio
from typing import Optional

import httpx

from .. import config
from ..models import Paper

_NOTION_VERSION = "2022-06-28"
_BASE = "https://api.notion.com/v1"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {config.NOTION_API_KEY}",
        "Notion-Version": _NOTION_VERSION,
        "Content-Type": "application/json",
    }


# ── Database schema bootstrap ─────────────────────────────────────────────────

_SCHEMA = {
    "Authors":        {"rich_text": {}},
    "Year":           {"number": {"format": "number"}},
    "DOI":            {"url": {}},
    "Venue":          {"rich_text": {}},
    "Abstract":       {"rich_text": {}},
    "Sources":        {"multi_select": {}},
    "Citation Count": {"number": {"format": "number"}},
    "Search Query":   {"rich_text": {}},
    "Mode":           {"select": {"options": [
        {"name": "balanced", "color": "default"},
        {"name": "classic",  "color": "blue"},
        {"name": "frontier", "color": "green"},
    ]}},
    "Perspective": {"select": {"options": [
        {"name": "profession",     "color": "purple"},
        {"name": "organization",   "color": "orange"},
        {"name": "symbolic",       "color": "pink"},
        {"name": "stratification", "color": "red"},
        {"name": "network",        "color": "yellow"},
        {"name": "culture",        "color": "brown"},
    ]}},
    "URL": {"url": {}},
}


async def ensure_schema(client: httpx.AsyncClient) -> bool:
    """Update the database schema to include all required properties."""
    try:
        r = await client.patch(
            f"{_BASE}/databases/{config.NOTION_DATABASE_ID}",
            headers=_headers(),
            json={"properties": _SCHEMA},
            timeout=15.0,
        )
        return r.status_code in (200, 201)
    except Exception:
        return False


# ── Paper → Notion page ───────────────────────────────────────────────────────

def _rich_text(value: Optional[str], limit: int = 2000) -> list:
    if not value:
        return []
    return [{"text": {"content": value[:limit]}}]


def _paper_to_page(
    paper: Paper,
    query: str,
    mode: str,
    perspective: Optional[str],
) -> dict:
    authors_str = ", ".join(a.name for a in paper.authors[:10])
    doi_clean = paper.doi if paper.doi and not paper.doi.startswith("isbn:") else None

    props: dict = {
        "Name": {
            "title": [{"text": {"content": (paper.title or "Untitled")[:2000]}}]
        },
        "Authors":        {"rich_text": _rich_text(authors_str)},
        "Venue":          {"rich_text": _rich_text(paper.venue)},
        "Abstract":       {"rich_text": _rich_text(paper.abstract, limit=2000)},
        "Sources":        {"multi_select": [{"name": s} for s in paper.sources]},
        "Search Query":   {"rich_text": _rich_text(query[:500])},
        "Mode":           {"select": {"name": mode}},
    }

    if paper.year:
        props["Year"] = {"number": paper.year}
    if paper.citation_count:
        props["Citation Count"] = {"number": paper.citation_count}
    if doi_clean:
        props["DOI"] = {"url": f"https://doi.org/{doi_clean}"}
    if paper.url:
        props["URL"] = {"url": paper.url}
    if perspective:
        props["Perspective"] = {"select": {"name": perspective}}

    return {
        "parent": {"database_id": config.NOTION_DATABASE_ID},
        "properties": props,
    }


# ── Batch export ──────────────────────────────────────────────────────────────

async def export_to_notion(
    papers: list[Paper],
    query: str,
    mode: str = "balanced",
    perspective: Optional[str] = None,
    console=None,
) -> int:
    """Push papers to Notion. Returns number of pages created."""
    if not config.NOTION_API_KEY or not config.NOTION_DATABASE_ID:
        if console:
            console.print(
                "[yellow]⚠ Notion not configured. "
                "Set NOTION_API_KEY and NOTION_DATABASE_ID.[/yellow]"
            )
        return 0

    sem = asyncio.Semaphore(3)  # Notion rate limit: 3 req/s
    created = 0

    async with httpx.AsyncClient() as client:
        # Ensure schema exists
        await ensure_schema(client)

        async def create_page(paper: Paper) -> bool:
            nonlocal created
            page_data = _paper_to_page(paper, query, mode, perspective)
            async with sem:
                try:
                    r = await client.post(
                        f"{_BASE}/pages",
                        headers=_headers(),
                        json=page_data,
                        timeout=15.0,
                    )
                    await asyncio.sleep(0.35)  # stay under rate limit
                    if r.status_code in (200, 201):
                        return True
                    if console:
                        console.print(f"  [dim red]Notion error {r.status_code}: {r.text[:200]}[/dim red]")
                    return False
                except Exception as e:
                    if console:
                        console.print(f"  [dim red]Notion exception: {e}[/dim red]")
                    return False

        tasks = [create_page(p) for p in papers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        created = sum(1 for r in results if r is True)

    if console:
        console.print(
            f"  [green]✓ Notion:[/green] {created}/{len(papers)} pages created → "
            f"[link=https://notion.so]notion.so[/link]"
        )

    return created
