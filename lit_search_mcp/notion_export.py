"""
Notion database export.
Pushes papers to a Notion database with fields: Name, topics, status, DOI, Year, Authors, Abstract, URL.
"""

from __future__ import annotations
import logging
import os
from typing import List, Optional

import httpx

from models import Paper

log = logging.getLogger(__name__)

# Set via environment variable NOTION_API_KEY and NOTION_DATABASE_ID
# or pass directly to export_papers_to_notion()
DEFAULT_NOTION_TOKEN = os.getenv("NOTION_API_KEY", "")
DEFAULT_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "32f87c1298c2804bbf70d96984ed8e05")

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def _make_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _rich_text(text: str, limit: int = 2000) -> list:
    if not text:
        return []
    return [{"type": "text", "text": {"content": text[:limit]}}]


def _paper_to_page(paper: Paper, database_id: str) -> dict:
    authors_str = ", ".join(str(a) for a in paper.authors[:5])
    if len(paper.authors) > 5:
        authors_str += " et al."

    props: dict = {
        "Name": {"title": _rich_text(paper.title or "Untitled")},
    }

    # Optional fields — only add if non-empty (avoids Notion property-type errors)
    if paper.year:
        props["Year"] = {"number": paper.year}
    if authors_str:
        props["Authors"] = {"rich_text": _rich_text(authors_str)}
    if paper.doi:
        props["DOI"] = {"rich_text": _rich_text(paper.doi)}
    if paper.venue:
        props["Venue"] = {"rich_text": _rich_text(paper.venue)}
    if paper.citation_count:
        props["Citations"] = {"number": paper.citation_count}
    if paper.url or paper.pdf_url:
        props["URL"] = {"url": (paper.pdf_url or paper.url)}

    # Status select (matches the database's Status property)
    props["Status"] = {"select": {"name": "To Read"}}

    # Abstract as page body
    children = []
    if paper.abstract:
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": _rich_text(paper.abstract, limit=1800)},
        })

    return {
        "parent": {"database_id": database_id},
        "properties": props,
        "children": children,
    }


async def export_papers_to_notion(
    papers: List[Paper],
    notion_token: Optional[str] = None,
    database_id: Optional[str] = None,
) -> dict:
    """
    Push a list of papers to a Notion database.
    Returns {"pushed": N, "skipped": M, "errors": [...]}
    """
    token = notion_token or os.getenv("NOTION_API_KEY") or DEFAULT_NOTION_TOKEN
    db_id = database_id or os.getenv("NOTION_DATABASE_ID") or DEFAULT_DATABASE_ID

    pushed = 0
    skipped = 0
    errors = []

    async with httpx.AsyncClient() as client:
        for paper in papers:
            page_data = _paper_to_page(paper, db_id)
            try:
                r = await client.post(
                    f"{NOTION_API}/pages",
                    headers=_make_headers(token),
                    json=page_data,
                    timeout=15.0,
                )
                if r.status_code in (200, 201):
                    pushed += 1
                else:
                    body = r.text[:300]
                    errors.append({"title": paper.title, "status": r.status_code, "body": body})
                    log.warning("Notion push failed for '%s': %s %s", paper.title, r.status_code, body)
            except Exception as e:
                errors.append({"title": paper.title, "error": str(e)})
                log.warning("Notion push exception for '%s': %s", paper.title, e)

    return {"pushed": pushed, "skipped": skipped, "errors": errors}
