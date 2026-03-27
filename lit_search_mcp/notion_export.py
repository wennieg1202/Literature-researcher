"""
Notion export — creates ONE summary page per search session.
No per-paper pages; all results are rendered as a structured list inside
a single Notion page, keeping API calls to a minimum (1-2 per export).
"""

from __future__ import annotations
import datetime
import logging
import os
from typing import Dict, List, Optional

import httpx

from models import Paper

log = logging.getLogger(__name__)

DEFAULT_NOTION_TOKEN = os.getenv("NOTION_API_KEY", "")
DEFAULT_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "32f87c1298c2804bbf70d96984ed8e05")

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
# Max children Notion accepts per request
_BLOCK_BATCH = 90


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _rt(text: str, limit: int = 2000) -> list:
    """Minimal rich-text block."""
    return [{"type": "text", "text": {"content": str(text)[:limit]}}]


def _paper_line(i: int, p: Paper) -> dict:
    """One numbered-list block per paper."""
    authors = ", ".join(str(a) for a in p.authors[:3])
    if len(p.authors) > 3:
        authors += " et al."
    parts = [f"{p.title or 'Untitled'}"]
    if p.year:
        parts[0] += f" ({p.year})"
    if authors:
        parts.append(authors)
    if p.citation_count:
        parts.append(f"cited {p.citation_count}×")
    if p.doi:
        parts.append(f"DOI: {p.doi}")
    elif p.url:
        parts.append(p.url)
    line = " — ".join(parts)
    return {
        "object": "block",
        "type": "numbered_list_item",
        "numbered_list_item": {"rich_text": _rt(line, 1900)},
    }


def _build_header_blocks(
    query: str,
    mode: str,
    perspective: str,
    stats: dict,
    total: int,
    showing: int,
    date_str: str,
) -> list:
    src_counts = ", ".join(
        f"{k}: {v}" for k, v in stats.get("by_source", {}).items() if k != "snowball_added"
    )
    snowball_added = stats.get("snowball_added", 0)
    sb_note = f" + {snowball_added} via snowball" if snowball_added else ""

    persp_label = perspective or "General"
    summary_line = (
        f"Mode: {mode}  ·  Perspective: {persp_label}  ·  "
        f"Found: {total} papers (after dedup){sb_note}  ·  {date_str}"
    )

    blocks = [
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": _rt(f"Query: {query}", 1500),
                "icon": {"type": "emoji", "emoji": "🔍"},
            },
        },
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": _rt(summary_line)},
        },
    ]
    if src_counts:
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": _rt(f"Sources: {src_counts}")},
        })
    blocks += [
        {"object": "block", "type": "divider", "divider": {}},
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": _rt(f"Top Papers  ({showing} / {total} shown)")
            },
        },
    ]
    return blocks


async def export_summary_to_notion(
    papers: List[Paper],
    query: str = "",
    mode: str = "balanced",
    perspective: str = "",
    stats: Optional[Dict] = None,
    notion_token: Optional[str] = None,
    database_id: Optional[str] = None,
) -> dict:
    """
    Create ONE Notion page summarising the search results.
    Uses at most 2 API calls regardless of how many papers there are.
    Returns {"page_id": ..., "url": ..., "papers_shown": N, "errors": [...]}
    """
    token = notion_token or os.getenv("NOTION_API_KEY") or DEFAULT_NOTION_TOKEN
    db_id = database_id or os.getenv("NOTION_DATABASE_ID") or DEFAULT_DATABASE_ID
    stats = stats or {}

    date_str = datetime.date.today().isoformat()
    title = f"{(query or 'Search')[:60]} · {date_str}"

    # Limit to top 50 for the summary (keeps the page readable)
    showing_papers = papers[:50]
    showing = len(showing_papers)
    total = len(papers)

    header_blocks = _build_header_blocks(
        query, mode, perspective, stats, total, showing, date_str
    )
    paper_blocks = [_paper_line(i + 1, p) for i, p in enumerate(showing_papers)]
    all_blocks = header_blocks + paper_blocks

    # Split into batches of _BLOCK_BATCH (Notion limit per request)
    first_batch = all_blocks[:_BLOCK_BATCH]
    overflow = all_blocks[_BLOCK_BATCH:]

    page_payload = {
        "parent": {"database_id": db_id},
        "properties": {
            "Name": {"title": _rt(title)},
        },
        "children": first_batch,
    }

    errors = []
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(
                f"{NOTION_API}/pages",
                headers=_headers(token),
                json=page_payload,
                timeout=20.0,
            )
            r.raise_for_status()
            page = r.json()
            page_id = page.get("id", "")
            page_url = page.get("url", "")
        except Exception as e:
            return {"page_id": "", "url": "", "papers_shown": 0,
                    "errors": [str(e)]}

        # Append overflow blocks if any
        if overflow and page_id:
            for i in range(0, len(overflow), _BLOCK_BATCH):
                batch = overflow[i: i + _BLOCK_BATCH]
                try:
                    r2 = await client.patch(
                        f"{NOTION_API}/blocks/{page_id}/children",
                        headers=_headers(token),
                        json={"children": batch},
                        timeout=20.0,
                    )
                    r2.raise_for_status()
                except Exception as e:
                    errors.append(f"append batch {i}: {e}")
                    log.warning("Notion append failed: %s", e)

    return {
        "page_id": page_id,
        "url": page_url,
        "papers_shown": showing,
        "total_papers": total,
        "errors": errors,
    }
