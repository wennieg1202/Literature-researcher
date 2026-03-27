import sqlite3
import json
import hashlib
import time
from pathlib import Path
from typing import Any, Optional

CACHE_DIR = Path.home() / ".cache" / "lit_search"
CACHE_TTL = 86400  # 24 hours


class Cache:
    def __init__(self, path: Optional[Path] = None):
        self.path = path or CACHE_DIR / "http_cache.db"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS cache "
                "(key TEXT PRIMARY KEY, value TEXT, ts REAL)"
            )

    def _key(self, url: str, params: dict) -> str:
        raw = json.dumps({"url": url, "params": params}, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, url: str, params: dict) -> Optional[Any]:
        k = self._key(url, params)
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                "SELECT value, ts FROM cache WHERE key=?", (k,)
            ).fetchone()
        if row and (time.time() - row[1]) < CACHE_TTL:
            return json.loads(row[0])
        return None

    def set(self, url: str, params: dict, value: Any):
        k = self._key(url, params)
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache (key, value, ts) VALUES (?,?,?)",
                (k, json.dumps(value), time.time()),
            )
