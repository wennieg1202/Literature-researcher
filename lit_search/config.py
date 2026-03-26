"""All constants and environment-variable configuration in one place."""

import os

# ── API endpoints ─────────────────────────────────────────────────────────────
OPENALEX_BASE   = "https://api.openalex.org/works"
S2_SEARCH_BASE  = "https://api.semanticscholar.org/graph/v1/paper/search"
S2_PAPER_BASE   = "https://api.semanticscholar.org/graph/v1/paper"
CROSSREF_BASE   = "https://api.crossref.org/works"
ARXIV_BASE      = "http://export.arxiv.org/api/query"
GBOOKS_BASE     = "https://www.googleapis.com/books/v1/volumes"
OPENLIBRARY_BASE = "https://openlibrary.org/search.json"
ACM_SEARCH_BASE  = "https://dl.acm.org/action/doSearch"

# ── Rate-limit concurrency (asyncio.Semaphore values) ──────────────────────────
SEM_OPENALEX    = 10
SEM_S2          = 1     # 1 req/s unauthenticated
SEM_CROSSREF    = 5
SEM_ARXIV       = 1     # ArXiv asks for ≥3s between requests
SEM_GBOOKS      = 5
SEM_OPENLIBRARY = 3
SEM_ACM         = 1

# Sleep delays (seconds) after each request for rate-limited APIs
SLEEP_S2     = 1.0
SLEEP_ARXIV  = 3.0
SLEEP_ACM    = 2.0

# ── Search parameters ──────────────────────────────────────────────────────────
RESULTS_PER_API       = 25   # results per expanded term per API
TOP_SNOWBALL_COUNT    = 20   # top-N papers to feed into snowball step
DEDUP_TITLE_THRESHOLD = 88   # rapidfuzz ratio (0–100)
MAX_PAPERS_DEFAULT    = 150

# ── Claude ─────────────────────────────────────────────────────────────────────
CLAUDE_MODEL          = "claude-sonnet-4-6"
MAX_TOKENS_EXPAND     = 600
MAX_TOKENS_SUMMARIZE  = 1200

# ── Credentials (from environment) ────────────────────────────────────────────
ANTHROPIC_API_KEY    = os.getenv("ANTHROPIC_API_KEY", "")
CROSSREF_EMAIL       = os.getenv("CROSSREF_EMAIL", "")
GOOGLE_BOOKS_API_KEY = os.getenv("GOOGLE_BOOKS_API_KEY", "")
NOTION_API_KEY       = os.getenv("NOTION_API_KEY", "")
NOTION_DATABASE_ID   = os.getenv("NOTION_DATABASE_ID", "")

# ── HTTP headers ───────────────────────────────────────────────────────────────
_contact = f" (mailto:{CROSSREF_EMAIL})" if CROSSREF_EMAIL else ""
USER_AGENT = f"lit-search/0.1{_contact}"

# ── Cache ──────────────────────────────────────────────────────────────────────
CACHE_DIR      = os.path.expanduser("~/.cache/lit_search")
CACHE_DB_PATH  = os.path.join(CACHE_DIR, "cache.db")
CACHE_TTL_HOURS = 24
