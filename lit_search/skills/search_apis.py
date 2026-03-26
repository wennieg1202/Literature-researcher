"""API adapters for all 8 literature sources.

Each adapter:
  - Is an async function: search_{source}(terms, client, cache, sem) -> list[Paper]
  - Checks cache before HTTP, writes to cache on success
  - Returns [] on any error (partial results are acceptable)
  - Maps source JSON → unified Paper dataclass

multi_search() runs all adapters concurrently via asyncio.gather().
"""

from __future__ import annotations

import asyncio
import json
import time
import xml.etree.ElementTree as ET
from typing import Optional

import httpx

from ..cache import Cache
from .. import config
from ..models import Author, Paper


# ── helpers ────────────────────────────────────────────────────────────────────

async def _get(
    client: httpx.AsyncClient,
    url: str,
    params: dict,
    cache: Optional[Cache],
    sleep_after: float = 0.0,
) -> Optional[dict | str]:
    """GET with cache check. Returns parsed JSON dict, raw text, or None on error."""
    if cache:
        cached = cache.get(url, params)
        if cached is not None:
            return cached

    try:
        r = await client.get(url, params=params, timeout=20.0)
        r.raise_for_status()
    except Exception:
        return None

    if sleep_after:
        await asyncio.sleep(sleep_after)

    ct = r.headers.get("content-type", "")
    if "json" in ct:
        try:
            data = r.json()
            if cache:
                cache.set(url, params, data)
            return data
        except Exception:
            return None
    else:
        text = r.text
        if cache:
            cache.set(url, params, text)
        return text


def _authors_from_list(raw: list) -> list[Author]:
    authors = []
    for a in raw or []:
        if isinstance(a, str):
            authors.append(Author(name=a))
        elif isinstance(a, dict):
            name = (
                a.get("display_name")
                or a.get("name")
                or f"{a.get('given', '')} {a.get('family', '')}".strip()
                or "Unknown"
            )
            authors.append(Author(name=name, orcid=a.get("orcid")))
    return authors


# ── OpenAlex ───────────────────────────────────────────────────────────────────

async def search_openalex(
    terms: list[str],
    client: httpx.AsyncClient,
    cache: Optional[Cache],
    sem: asyncio.Semaphore,
) -> list[Paper]:
    papers: list[Paper] = []
    for term in terms:
        async with sem:
            data = await _get(
                client,
                config.OPENALEX_BASE,
                {
                    "search": term,
                    "per-page": config.RESULTS_PER_API,
                    "select": "id,doi,title,authorships,publication_year,primary_location,"
                              "cited_by_count,abstract_inverted_index,biblio,type",
                    "mailto": config.CROSSREF_EMAIL or "user@example.com",
                },
                cache,
            )
        if not isinstance(data, dict):
            continue
        for w in data.get("results", []):
            paper = _openalex_to_paper(w)
            if paper:
                papers.append(paper)
    return papers


def _openalex_to_paper(w: dict) -> Optional[Paper]:
    title = w.get("title")
    if not title:
        return None

    # Reconstruct abstract from inverted index
    abstract = None
    inv = w.get("abstract_inverted_index")
    if inv:
        try:
            max_pos = max(pos for positions in inv.values() for pos in positions)
            words = [""] * (max_pos + 1)
            for word, positions in inv.items():
                for pos in positions:
                    words[pos] = word
            abstract = " ".join(words).strip() or None
        except Exception:
            abstract = None

    authors = []
    for a in w.get("authorships", []):
        auth = a.get("author", {})
        name = auth.get("display_name", "")
        if name:
            authors.append(Author(name=name, orcid=auth.get("orcid")))

    loc = w.get("primary_location") or {}
    source = loc.get("source") or {}
    venue = source.get("display_name")

    biblio = w.get("biblio") or {}
    doi_raw = w.get("doi")

    return Paper(
        title=title,
        year=w.get("publication_year"),
        doi=doi_raw,
        openalex_id=w.get("id", "").split("/")[-1] if w.get("id") else None,
        authors=authors,
        venue=venue,
        volume=biblio.get("volume"),
        issue=biblio.get("issue"),
        pages=(
            f"{biblio['first_page']}--{biblio['last_page']}"
            if biblio.get("first_page") and biblio.get("last_page")
            else biblio.get("first_page")
        ),
        abstract=abstract,
        citation_count=w.get("cited_by_count", 0),
        sources=["openalex"],
    )


# ── Semantic Scholar ──────────────────────────────────────────────────────────

_S2_FIELDS = (
    "paperId,externalIds,title,authors,year,abstract,"
    "citationCount,venue,journal,publicationTypes,openAccessPdf"
)


async def search_s2(
    terms: list[str],
    client: httpx.AsyncClient,
    cache: Optional[Cache],
    sem: asyncio.Semaphore,
) -> list[Paper]:
    papers: list[Paper] = []
    for term in terms:
        async with sem:
            data = await _get(
                client,
                config.S2_SEARCH_BASE,
                {"query": term, "limit": config.RESULTS_PER_API, "fields": _S2_FIELDS},
                cache,
                sleep_after=config.SLEEP_S2,
            )
        if not isinstance(data, dict):
            continue
        for item in data.get("data", []):
            paper = _s2_to_paper(item)
            if paper:
                papers.append(paper)
    return papers


def _s2_to_paper(item: dict) -> Optional[Paper]:
    title = item.get("title")
    if not title:
        return None

    ext = item.get("externalIds") or {}
    doi = ext.get("DOI")
    arxiv_id = ext.get("ArXiv")

    authors = [Author(name=a.get("name", "")) for a in item.get("authors", []) if a.get("name")]

    journal = item.get("journal") or {}
    venue = item.get("venue") or journal.get("name")

    # Tag SSRN papers
    sources = ["s2"]
    if ext.get("SSRN"):
        sources.append("ssrn")

    url = None
    pdf = item.get("openAccessPdf")
    if pdf and isinstance(pdf, dict):
        url = pdf.get("url")

    return Paper(
        title=title,
        year=item.get("year"),
        doi=doi,
        arxiv_id=arxiv_id,
        s2_id=item.get("paperId"),
        authors=authors,
        venue=venue,
        volume=journal.get("volume"),
        pages=journal.get("pages"),
        abstract=item.get("abstract"),
        citation_count=item.get("citationCount", 0),
        url=url,
        sources=sources,
    )


# ── CrossRef ──────────────────────────────────────────────────────────────────

async def search_crossref(
    terms: list[str],
    client: httpx.AsyncClient,
    cache: Optional[Cache],
    sem: asyncio.Semaphore,
) -> list[Paper]:
    papers: list[Paper] = []
    for term in terms:
        async with sem:
            data = await _get(
                client,
                config.CROSSREF_BASE,
                {"query": term, "rows": config.RESULTS_PER_API, "select": (
                    "DOI,title,author,published,container-title,"
                    "volume,issue,page,publisher,abstract,is-referenced-by-count,URL,type"
                )},
                cache,
            )
        if not isinstance(data, dict):
            continue
        for item in (data.get("message") or {}).get("items", []):
            paper = _crossref_to_paper(item)
            if paper:
                papers.append(paper)
    return papers


def _crossref_to_paper(item: dict) -> Optional[Paper]:
    titles = item.get("title", [])
    title = titles[0] if titles else None
    if not title:
        return None

    # Year from published.date-parts
    year = None
    pub = item.get("published") or item.get("published-print") or item.get("published-online")
    if pub:
        dp = pub.get("date-parts", [[]])
        if dp and dp[0]:
            year = dp[0][0]

    authors = []
    for a in item.get("author", []):
        given = a.get("given", "")
        family = a.get("family", "")
        name = f"{given} {family}".strip() if given or family else ""
        if name:
            authors.append(Author(name=name, orcid=a.get("ORCID")))

    containers = item.get("container-title", [])
    venue = containers[0] if containers else None

    tp = item.get("type", "")
    hint = None
    if "book" in tp:
        hint = "book"
    elif "proceedings" in tp:
        hint = "inproceedings"
    elif "journal" in tp:
        hint = "article"

    return Paper(
        title=title,
        year=year,
        doi=item.get("DOI"),
        authors=authors,
        venue=venue,
        volume=item.get("volume"),
        issue=item.get("issue"),
        pages=item.get("page"),
        publisher=item.get("publisher"),
        url=item.get("URL"),
        abstract=item.get("abstract"),
        citation_count=item.get("is-referenced-by-count", 0),
        entry_type_hint=hint,
        sources=["crossref"],
    )


# ── arXiv ─────────────────────────────────────────────────────────────────────

_ARXIV_NS = "http://www.w3.org/2005/Atom"


async def search_arxiv(
    terms: list[str],
    client: httpx.AsyncClient,
    cache: Optional[Cache],
    sem: asyncio.Semaphore,
) -> list[Paper]:
    papers: list[Paper] = []
    for term in terms:
        async with sem:
            data = await _get(
                client,
                config.ARXIV_BASE,
                {"search_query": f"all:{term}", "max_results": config.RESULTS_PER_API},
                cache,
                sleep_after=config.SLEEP_ARXIV,
            )
        if not isinstance(data, str):
            continue
        try:
            root = ET.fromstring(data)
        except ET.ParseError:
            continue
        ns = {"a": _ARXIV_NS}
        for entry in root.findall("a:entry", ns):
            paper = _arxiv_entry_to_paper(entry, ns)
            if paper:
                papers.append(paper)
    return papers


def _arxiv_entry_to_paper(entry: ET.Element, ns: dict) -> Optional[Paper]:
    title_el = entry.find("a:title", ns)
    title = title_el.text.strip().replace("\n", " ") if title_el is not None else None
    if not title or title == "Error":
        return None

    abs_el = entry.find("a:summary", ns)
    abstract = abs_el.text.strip().replace("\n", " ") if abs_el is not None else None

    published_el = entry.find("a:published", ns)
    year = None
    if published_el is not None and published_el.text:
        try:
            year = int(published_el.text[:4])
        except ValueError:
            pass

    authors = []
    for a in entry.findall("a:author", ns):
        name_el = a.find("a:name", ns)
        if name_el is not None and name_el.text:
            authors.append(Author(name=name_el.text.strip()))

    arxiv_id = None
    id_el = entry.find("a:id", ns)
    if id_el is not None and id_el.text:
        # "http://arxiv.org/abs/2301.07041v1" → "2301.07041"
        arxiv_id = id_el.text.split("/abs/")[-1].split("v")[0]

    # Check for DOI link
    doi = None
    for link in entry.findall("a:link", ns):
        if link.get("title") == "doi":
            doi = link.get("href", "").split("doi.org/")[-1] or None
            break

    url = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else None

    return Paper(
        title=title,
        year=year,
        doi=doi,
        arxiv_id=arxiv_id,
        authors=authors,
        venue="arXiv",
        abstract=abstract,
        url=url,
        entry_type_hint="misc",
        sources=["arxiv"],
    )


# ── Google Books ──────────────────────────────────────────────────────────────

async def search_google_books(
    terms: list[str],
    client: httpx.AsyncClient,
    cache: Optional[Cache],
    sem: asyncio.Semaphore,
) -> list[Paper]:
    papers: list[Paper] = []
    for term in terms:
        params: dict = {"q": term, "maxResults": min(config.RESULTS_PER_API, 40)}
        if config.GOOGLE_BOOKS_API_KEY:
            params["key"] = config.GOOGLE_BOOKS_API_KEY
        async with sem:
            data = await _get(client, config.GBOOKS_BASE, params, cache)
        if not isinstance(data, dict):
            continue
        for item in data.get("items", []):
            paper = _gbooks_to_paper(item)
            if paper:
                papers.append(paper)
    return papers


def _gbooks_to_paper(item: dict) -> Optional[Paper]:
    vi = item.get("volumeInfo", {})
    title = vi.get("title")
    if not title:
        return None

    # Full title including subtitle
    subtitle = vi.get("subtitle")
    if subtitle:
        title = f"{title}: {subtitle}"

    authors = [Author(name=a) for a in vi.get("authors", [])]

    year = None
    pub_date = vi.get("publishedDate", "")
    if pub_date:
        try:
            year = int(pub_date[:4])
        except ValueError:
            pass

    # ISBN → use as pseudo-DOI for dedup
    isbn = None
    for id_obj in vi.get("industryIdentifiers", []):
        if id_obj.get("type") in ("ISBN_13", "ISBN_10"):
            isbn = id_obj.get("identifier")
            break

    doi_like = f"isbn:{isbn}" if isbn else None

    return Paper(
        title=title,
        year=year,
        doi=doi_like,
        authors=authors,
        publisher=vi.get("publisher"),
        abstract=vi.get("description"),
        url=vi.get("infoLink"),
        entry_type_hint="book",
        sources=["google_books"],
    )


# ── OpenLibrary ───────────────────────────────────────────────────────────────

async def search_openlibrary(
    terms: list[str],
    client: httpx.AsyncClient,
    cache: Optional[Cache],
    sem: asyncio.Semaphore,
) -> list[Paper]:
    papers: list[Paper] = []
    for term in terms:
        async with sem:
            data = await _get(
                client,
                config.OPENLIBRARY_BASE,
                {"q": term, "limit": config.RESULTS_PER_API, "fields": (
                    "title,author_name,first_publish_year,isbn,"
                    "publisher,subject,key"
                )},
                cache,
            )
        if not isinstance(data, dict):
            continue
        for doc in data.get("docs", []):
            paper = _openlibrary_to_paper(doc)
            if paper:
                papers.append(paper)
    return papers


def _openlibrary_to_paper(doc: dict) -> Optional[Paper]:
    title = doc.get("title")
    if not title:
        return None

    authors = [Author(name=n) for n in doc.get("author_name", [])]

    year = doc.get("first_publish_year")
    if isinstance(year, str):
        try:
            year = int(year)
        except ValueError:
            year = None

    isbns = doc.get("isbn", [])
    isbn = isbns[0] if isbns else None
    doi_like = f"isbn:{isbn}" if isbn else None

    publishers = doc.get("publisher", [])
    publisher = publishers[0] if publishers else None

    ol_key = doc.get("key", "")
    url = f"https://openlibrary.org{ol_key}" if ol_key else None

    return Paper(
        title=title,
        year=year,
        doi=doi_like,
        authors=authors,
        publisher=publisher,
        url=url,
        entry_type_hint="book",
        sources=["openlibrary"],
    )


# ── ACM Digital Library ───────────────────────────────────────────────────────

async def search_acm(
    terms: list[str],
    client: httpx.AsyncClient,
    cache: Optional[Cache],
    sem: asyncio.Semaphore,
) -> list[Paper]:
    """Scrape ACM DL search results (HTML). Returns [] if blocked."""
    import re as _re

    papers: list[Paper] = []
    headers = {
        "User-Agent": config.USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
    }

    for term in terms:
        params = {
            "AllField": term,
            "pageSize": min(config.RESULTS_PER_API, 20),
            "startPage": "0",
        }
        async with sem:
            try:
                r = await client.get(
                    config.ACM_SEARCH_BASE,
                    params=params,
                    headers=headers,
                    timeout=20.0,
                )
            except Exception:
                continue
            await asyncio.sleep(config.SLEEP_ACM)

        if r.status_code != 200:
            continue

        html = r.text
        # Extract DOIs embedded in result links: /doi/10.xxxx/xxxxx
        doi_pattern = _re.compile(r'href="/doi/(10\.[^"?#\s]+)"')
        title_pattern = _re.compile(
            r'<span[^>]*class="[^"]*hlFld-Title[^"]*"[^>]*>(.*?)</span>',
            _re.DOTALL,
        )

        dois = doi_pattern.findall(html)
        titles = [
            _re.sub(r"<[^>]+>", "", t).strip()
            for t in title_pattern.findall(html)
        ]

        for i, doi in enumerate(dois[:config.RESULTS_PER_API]):
            title = titles[i] if i < len(titles) else None
            if not title:
                continue
            papers.append(
                Paper(
                    title=title,
                    doi=doi,
                    url=f"https://dl.acm.org/doi/{doi}",
                    entry_type_hint="inproceedings",
                    sources=["acm"],
                )
            )

    return papers


# ── multi_search ──────────────────────────────────────────────────────────────

async def multi_search(
    terms: list[str],
    cache=None,
    console=None,
) -> list[Paper]:
    """Run all 8 adapters concurrently; return combined list."""
    sem_oa  = asyncio.Semaphore(config.SEM_OPENALEX)
    sem_s2  = asyncio.Semaphore(config.SEM_S2)
    sem_cr  = asyncio.Semaphore(config.SEM_CROSSREF)
    sem_ax  = asyncio.Semaphore(config.SEM_ARXIV)
    sem_gb  = asyncio.Semaphore(config.SEM_GBOOKS)
    sem_ol  = asyncio.Semaphore(config.SEM_OPENLIBRARY)
    sem_acm = asyncio.Semaphore(config.SEM_ACM)

    headers = {"User-Agent": config.USER_AGENT}

    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        results = await asyncio.gather(
            search_openalex(terms, client, cache, sem_oa),
            search_s2(terms, client, cache, sem_s2),
            search_crossref(terms, client, cache, sem_cr),
            search_arxiv(terms, client, cache, sem_ax),
            search_google_books(terms, client, cache, sem_gb),
            search_openlibrary(terms, client, cache, sem_ol),
            search_acm(terms, client, cache, sem_acm),
            return_exceptions=True,
        )

    papers: list[Paper] = []
    source_names = [
        "OpenAlex", "Semantic Scholar", "CrossRef",
        "arXiv", "Google Books", "OpenLibrary", "ACM DL",
    ]
    for name, result in zip(source_names, results):
        if isinstance(result, Exception):
            if console:
                console.print(f"  [yellow]⚠ {name} error: {result}[/yellow]")
        elif isinstance(result, list):
            papers.extend(result)
            if console:
                console.print(f"  [green]✓ {name}:[/green] {len(result)} results")

    return papers
