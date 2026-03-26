"""SQLite HTTP response cache with TTL.

Keyed by (url, sha256(sorted params)), stores JSON-serialised responses.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from typing import Any, Optional

from . import config


class Cache:
    _CREATE = """
    CREATE TABLE IF NOT EXISTS http_cache (
        url         TEXT NOT NULL,
        params_hash TEXT NOT NULL,
        body        TEXT NOT NULL,
        fetched_at  REAL NOT NULL,
        PRIMARY KEY (url, params_hash)
    )
    """

    def __init__(self, db_path: str = config.CACHE_DB_PATH) -> None:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(self._CREATE)
        self._conn.commit()
        self._ttl = config.CACHE_TTL_HOURS * 3600

    def _hash(self, params: Any) -> str:
        s = json.dumps(params, sort_keys=True, default=str)
        return hashlib.sha256(s.encode()).hexdigest()

    def get(self, url: str, params: Any = None) -> Optional[Any]:
        h = self._hash(params)
        row = self._conn.execute(
            "SELECT body, fetched_at FROM http_cache WHERE url=? AND params_hash=?",
            (url, h),
        ).fetchone()
        if row is None:
            return None
        body, fetched_at = row
        if time.time() - fetched_at > self._ttl:
            return None
        return json.loads(body)

    def set(self, url: str, params: Any, response: Any) -> None:
        h = self._hash(params)
        self._conn.execute(
            "INSERT OR REPLACE INTO http_cache (url, params_hash, body, fetched_at) VALUES (?,?,?,?)",
            (url, h, json.dumps(response, default=str), time.time()),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


# Module-level singleton used by adapters (created lazily)
_instance: Optional[Cache] = None


def get_cache(enabled: bool = True) -> Optional[Cache]:
    global _instance
    if not enabled:
        return None
    if _instance is None:
        _instance = Cache()
    return _instance
