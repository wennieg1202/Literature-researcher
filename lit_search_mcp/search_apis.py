"""
Async API adapters for 8 academic sources.
All return List[Paper] with a unified schema.
"""

from __future__ import annotations
import asyncio
import logging
import os
from typing import List, Optional

import httpx

from models import Author, Paper
from cache import Cache

log = logging.getLogger(__name__)

UA = "LitSearchMCP/1.0 (mailto:research@example.com)"
CROSSREF_EMAIL = os.getenv("CROSSREF_EMAIL", "")


# ─── helpers ────────────────────────────────────────────────────────────────

async def _get(client: httpx.AsyncClient, url: str, params: dict,
               cache: Optional[Cache] = None, sleep: float = 0.0) -> Optional[dict | list]:
    if cache:
        hit = cache.get(url, params)
        if hit is not None:
            return hit
    try:
        r = await client.get(url, params=params, timeout=20.0)
        r.raise_for_status()
        data = r.json()
        if cache:
            cache.set(url, params, data)
        if sleep:
            await asyncio.sleep(sleep)
        return data
    except Exception as e:
        log.warning("GET %s failed: %s", url, e)
        return None


def _authors_from_list(raw: list) -> List[Author]:
    out = []
    for a in raw:
        if isinstance(a, str):
            out.append(Author(name=a))
        elif isinstance(a, dict):
            name = (
                a.get("name")
                or a.get("display_name")
                or f"{a.get('given','')} {a.get('family','')}".strip()
                or a.get("author_name", "")
            )
            if name:
                out.append(Author(name=name, orcid=a.get("orcid")))
    return out


# ─── OpenAlex ───────────────────────────────────────────────────────────────

async def _search_openalex(terms: list[str], max_results: int,
                            client: httpx.AsyncClient, cache: Optional[Cache],
                            sem: asyncio.Semaphore) -> List[Paper]:
    query = " ".join(terms[:5])
    params = {
        "search": query,
        "per-page": min(max_results, 25),
        "select": "id,title,publication_year,authorships,primary_location,doi,"
                  "cited_by_count,abstract_inverted_index,biblio",
    }
    async with sem:
        data = await _get(client, "https://api.openalex.org/works", params, cache)
    if not data:
        return []
    papers = []
    for item in data.get("results", []):
        title = item.get("title") or ""
        if not title:
            continue
        abstract = ""
        inv = item.get("abstract_inverted_index") or {}
        if inv:
            words = [""] * (max(max(v) for v in inv.values()) + 1)
            for word, positions in inv.items():
                for p in positions:
                    words[p] = word
            abstract = " ".join(words)
        venue = None
        loc = item.get("primary_location") or {}
        src = loc.get("source") or {}
        venue = src.get("display_name")
        biblio = item.get("biblio") or {}
        authors = []
        for a in item.get("authorships", []):
            au = a.get("author") or {}
            name = au.get("display_name", "")
            orcid = au.get("orcid")
            if name:
                authors.append(Author(name=name, orcid=orcid))
        doi = (item.get("doi") or "").replace("https://doi.org/", "")
        papers.append(Paper(
            title=title,
            year=item.get("publication_year"),
            authors=authors,
            abstract=abstract or None,
            doi=doi or None,
            openalex_id=item.get("id"),
            venue=venue,
            volume=biblio.get("volume"),
            issue=biblio.get("issue"),
            pages=f"{biblio.get('first_page','')}-{biblio.get('last_page','')}".strip("-") or None,
            citation_count=item.get("cited_by_count", 0),
            sources=["openalex"],
        ))
    return papers


# ─── Semantic Scholar ────────────────────────────────────────────────────────

async def _search_s2(terms: list[str], max_results: int,
                     client: httpx.AsyncClient, cache: Optional[Cache],
                     sem: asyncio.Semaphore) -> List[Paper]:
    query = " ".join(terms[:5])
    params = {
        "query": query,
        "limit": min(max_results, 25),
        "fields": "title,year,authors,abstract,externalIds,venue,citationCount,openAccessPdf",
    }
    async with sem:
        data = await _get(client, "https://api.semanticscholar.org/graph/v1/paper/search",
                          params, cache, sleep=0.5)
    if not data:
        return []
    papers = []
    for item in data.get("data", []):
        title = item.get("title") or ""
        if not title:
            continue
        ext = item.get("externalIds") or {}
        pdf_url = None
        oa = item.get("openAccessPdf") or {}
        if oa.get("url"):
            pdf_url = oa["url"]
        papers.append(Paper(
            title=title,
            year=item.get("year"),
            authors=_authors_from_list(item.get("authors", [])),
            abstract=item.get("abstract"),
            doi=ext.get("DOI"),
            arxiv_id=ext.get("ArXiv"),
            s2_id=item.get("paperId"),
            venue=item.get("venue") or None,
            pdf_url=pdf_url,
            citation_count=item.get("citationCount", 0),
            sources=["s2"],
        ))
    return papers


# ─── CrossRef ────────────────────────────────────────────────────────────────

async def _search_crossref(terms: list[str], max_results: int,
                            client: httpx.AsyncClient, cache: Optional[Cache],
                            sem: asyncio.Semaphore) -> List[Paper]:
    query = " ".join(terms[:5])
    params: dict = {"query": query, "rows": min(max_results, 20)}
    if CROSSREF_EMAIL:
        params["mailto"] = CROSSREF_EMAIL
    async with sem:
        data = await _get(client, "https://api.crossref.org/works", params, cache, sleep=0.3)
    if not data:
        return []
    papers = []
    for item in (data.get("message") or {}).get("items", []):
        title_list = item.get("title") or []
        title = title_list[0] if title_list else ""
        if not title:
            continue
        year = None
        for date_field in ("published-print", "published-online", "created"):
            dp = item.get(date_field) or {}
            parts = dp.get("date-parts") or [[]]
            if parts and parts[0]:
                year = parts[0][0]
                break
        venue_list = item.get("container-title") or []
        venue = venue_list[0] if venue_list else None
        authors = []
        for a in item.get("author") or []:
            name = f"{a.get('given','')} {a.get('family','')}".strip()
            if name:
                authors.append(Author(name=name, orcid=a.get("ORCID")))
        abstract = item.get("abstract") or None
        if abstract:
            # Strip JATS XML tags
            import re
            abstract = re.sub(r"<[^>]+>", "", abstract).strip()
        papers.append(Paper(
            title=title,
            year=year,
            authors=authors,
            abstract=abstract,
            doi=item.get("DOI"),
            venue=venue,
            volume=item.get("volume"),
            issue=item.get("issue"),
            publisher=item.get("publisher"),
            url=(item.get("URL") or None),
            citation_count=item.get("is-referenced-by-count", 0),
            sources=["crossref"],
        ))
    return papers


# ─── arXiv ───────────────────────────────────────────────────────────────────

async def _search_arxiv(terms: list[str], max_results: int,
                         client: httpx.AsyncClient, cache: Optional[Cache],
                         sem: asyncio.Semaphore) -> List[Paper]:
    import xml.etree.ElementTree as ET
    query = " AND ".join(f'all:"{t}"' for t in terms[:3])
    params = {
        "search_query": query,
        "max_results": min(max_results, 15),
        "sortBy": "relevance",
    }
    async with sem:
        if cache:
            hit = cache.get("https://export.arxiv.org/api/query", params)
            if hit is not None:
                text = hit
            else:
                try:
                    r = await client.get("https://export.arxiv.org/api/query", params=params, timeout=20.0)
                    r.raise_for_status()
                    text = r.text
                    cache.set("https://export.arxiv.org/api/query", params, text)
                except Exception as e:
                    log.warning("arXiv failed: %s", e)
                    return []
        else:
            try:
                r = await client.get("https://export.arxiv.org/api/query", params=params, timeout=20.0)
                r.raise_for_status()
                text = r.text
            except Exception as e:
                log.warning("arXiv failed: %s", e)
                return []
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    papers = []
    for entry in root.findall("atom:entry", ns):
        title_el = entry.find("atom:title", ns)
        title = (title_el.text or "").strip().replace("\n", " ") if title_el is not None else ""
        if not title:
            continue
        abstract_el = entry.find("atom:summary", ns)
        abstract = (abstract_el.text or "").strip() if abstract_el is not None else None
        year = None
        pub_el = entry.find("atom:published", ns)
        if pub_el is not None and pub_el.text:
            year = int(pub_el.text[:4])
        arxiv_id = None
        id_el = entry.find("atom:id", ns)
        if id_el is not None and id_el.text:
            arxiv_id = id_el.text.split("/abs/")[-1]
        authors = []
        for a in entry.findall("atom:author", ns):
            n = a.find("atom:name", ns)
            if n is not None and n.text:
                authors.append(Author(name=n.text))
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}" if arxiv_id else None
        papers.append(Paper(
            title=title,
            year=year,
            authors=authors,
            abstract=abstract,
            arxiv_id=arxiv_id,
            url=f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else None,
            pdf_url=pdf_url,
            venue="arXiv",
            sources=["arxiv"],
        ))
    return papers


# ─── Google Books ─────────────────────────────────────────────────────────────

async def _search_google_books(terms: list[str], max_results: int,
                                client: httpx.AsyncClient, cache: Optional[Cache],
                                sem: asyncio.Semaphore) -> List[Paper]:
    query = " ".join(terms[:4])
    params: dict = {"q": query, "maxResults": min(max_results, 10), "printType": "books"}
    api_key = os.getenv("GOOGLE_BOOKS_API_KEY")
    if api_key:
        params["key"] = api_key
    async with sem:
        data = await _get(client, "https://www.googleapis.com/books/v1/volumes", params, cache)
    if not data:
        return []
    papers = []
    for item in data.get("items", []):
        info = item.get("volumeInfo") or {}
        title = info.get("title") or ""
        if not title:
            continue
        authors = [Author(name=a) for a in (info.get("authors") or [])]
        year = None
        pub_date = info.get("publishedDate") or ""
        if pub_date:
            year = int(pub_date[:4]) if pub_date[:4].isdigit() else None
        isbn = None
        for id_info in info.get("industryIdentifiers") or []:
            if id_info.get("type") in ("ISBN_13", "ISBN_10"):
                isbn = id_info.get("identifier")
                break
        papers.append(Paper(
            title=title,
            year=year,
            authors=authors,
            abstract=info.get("description"),
            publisher=info.get("publisher"),
            venue=info.get("publisher"),
            url=info.get("infoLink"),
            sources=["google_books"],
        ))
    return papers


# ─── OpenLibrary ──────────────────────────────────────────────────────────────

async def _search_openlibrary(terms: list[str], max_results: int,
                               client: httpx.AsyncClient, cache: Optional[Cache],
                               sem: asyncio.Semaphore) -> List[Paper]:
    query = " ".join(terms[:4])
    params = {"q": query, "limit": min(max_results, 10), "fields": "title,author_name,first_publish_year,subject,key"}
    async with sem:
        data = await _get(client, "https://openlibrary.org/search.json", params, cache)
    if not data:
        return []
    papers = []
    for item in data.get("docs", []):
        title = item.get("title") or ""
        if not title:
            continue
        authors = [Author(name=a) for a in (item.get("author_name") or [])]
        year = item.get("first_publish_year")
        key = item.get("key") or ""
        papers.append(Paper(
            title=title,
            year=year,
            authors=authors,
            url=f"https://openlibrary.org{key}" if key else None,
            sources=["openlibrary"],
        ))
    return papers


# ─── CORE ─────────────────────────────────────────────────────────────────────

async def _search_core(terms: list[str], max_results: int,
                        client: httpx.AsyncClient, cache: Optional[Cache],
                        sem: asyncio.Semaphore) -> List[Paper]:
    query = " ".join(terms[:4])
    params = {"q": query, "limit": min(max_results, 10)}
    api_key = os.getenv("CORE_API_KEY")
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    async with sem:
        if cache:
            hit = cache.get("https://api.core.ac.uk/v3/search/works", params)
            if hit is not None:
                data = hit
            else:
                try:
                    r = await client.get("https://api.core.ac.uk/v3/search/works",
                                         params=params, headers=headers, timeout=20.0)
                    r.raise_for_status()
                    data = r.json()
                    cache.set("https://api.core.ac.uk/v3/search/works", params, data)
                except Exception as e:
                    log.warning("CORE failed: %s", e)
                    return []
        else:
            try:
                r = await client.get("https://api.core.ac.uk/v3/search/works",
                                     params=params, headers=headers, timeout=20.0)
                r.raise_for_status()
                data = r.json()
            except Exception as e:
                log.warning("CORE failed: %s", e)
                return []
    papers = []
    for item in data.get("results", []):
        title = item.get("title") or ""
        if not title:
            continue
        authors = []
        for a in item.get("authors") or []:
            name = a.get("name") or ""
            if name:
                authors.append(Author(name=name))
        year = item.get("yearPublished")
        doi = item.get("doi")
        pdf_url = item.get("downloadUrl")
        papers.append(Paper(
            title=title,
            year=year,
            authors=authors,
            abstract=item.get("abstract"),
            doi=doi,
            pdf_url=pdf_url,
            url=item.get("sourceFulltextUrls", [None])[0] if item.get("sourceFulltextUrls") else None,
            sources=["core"],
        ))
    return papers


# ─── ACM Digital Library ──────────────────────────────────────────────────────

async def _search_acm(terms: list[str], max_results: int,
                       client: httpx.AsyncClient, cache: Optional[Cache],
                       sem: asyncio.Semaphore) -> List[Paper]:
    """ACM DL via CrossRef filter (type=journal-article, publisher=ACM)."""
    query = " ".join(terms[:4])
    params = {
        "query": query,
        "filter": "member:320",  # ACM CrossRef member ID
        "rows": min(max_results, 10),
    }
    if CROSSREF_EMAIL:
        params["mailto"] = CROSSREF_EMAIL
    async with sem:
        data = await _get(client, "https://api.crossref.org/works", params, cache, sleep=0.3)
    if not data:
        return []
    papers = []
    for item in (data.get("message") or {}).get("items", []):
        title_list = item.get("title") or []
        title = title_list[0] if title_list else ""
        if not title:
            continue
        year = None
        for date_field in ("published-print", "published-online", "created"):
            dp = item.get(date_field) or {}
            parts = dp.get("date-parts") or [[]]
            if parts and parts[0]:
                year = parts[0][0]
                break
        venue_list = item.get("container-title") or []
        venue = venue_list[0] if venue_list else None
        authors = []
        for a in item.get("author") or []:
            name = f"{a.get('given','')} {a.get('family','')}".strip()
            if name:
                authors.append(Author(name=name))
        papers.append(Paper(
            title=title,
            year=year,
            authors=authors,
            doi=item.get("DOI"),
            venue=venue,
            publisher="ACM",
            url=item.get("URL"),
            citation_count=item.get("is-referenced-by-count", 0),
            sources=["acm"],
        ))
    return papers


# ─── multi_search ─────────────────────────────────────────────────────────────

ALL_SOURCES = ["openalex", "s2", "crossref", "arxiv", "google_books", "openlibrary", "core", "acm"]

_ADAPTERS = {
    "openalex": _search_openalex,
    "s2": _search_s2,
    "crossref": _search_crossref,
    "arxiv": _search_arxiv,
    "google_books": _search_google_books,
    "openlibrary": _search_openlibrary,
    "core": _search_core,
    "acm": _search_acm,
}

_SEMAPHORES: dict[str, asyncio.Semaphore] = {}


def _get_sem(name: str) -> asyncio.Semaphore:
    limits = {"s2": 2, "crossref": 5, "acm": 5}
    if name not in _SEMAPHORES:
        _SEMAPHORES[name] = asyncio.Semaphore(limits.get(name, 10))
    return _SEMAPHORES[name]


async def multi_search(
    terms: list[str],
    sources: Optional[list[str]] = None,
    max_per_source: int = 20,
    cache: Optional[Cache] = None,
) -> List[Paper]:
    """Concurrently search all (or selected) sources and return merged results."""
    active = sources if sources else ALL_SOURCES
    async with httpx.AsyncClient(headers={"User-Agent": UA}) as client:
        tasks = [
            _ADAPTERS[src](terms, max_per_source, client, cache, _get_sem(src))
            for src in active
            if src in _ADAPTERS
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    papers: List[Paper] = []
    for src, res in zip(active, results):
        if isinstance(res, Exception):
            log.warning("Source %s raised: %s", src, res)
        elif isinstance(res, list):
            papers.extend(res)
    return papers
