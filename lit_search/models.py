"""Unified Paper dataclass — canonical schema for all API adapters."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Author:
    name: str
    orcid: Optional[str] = None


@dataclass
class Paper:
    # Identity
    title: str
    year: Optional[int] = None
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    s2_id: Optional[str] = None
    openalex_id: Optional[str] = None

    # Bibliographic
    authors: list[Author] = field(default_factory=list)
    venue: Optional[str] = None       # journal or conference name
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None
    publisher: Optional[str] = None
    url: Optional[str] = None
    entry_type_hint: Optional[str] = None  # "article" | "book" | "inproceedings" | "misc"

    # Content
    abstract: Optional[str] = None

    # Metrics
    citation_count: int = 0

    # Pipeline metadata
    sources: list[str] = field(default_factory=list)  # e.g. ["openalex", "s2"]
    relevance_score: float = 0.0

    def __post_init__(self) -> None:
        self.doi = _normalize_doi(self.doi)
        if self.title:
            self.title = self.title.strip()

    @property
    def entry_type(self) -> str:
        if self.entry_type_hint:
            return self.entry_type_hint
        if "book" in (self.venue or "").lower():
            return "book"
        if self.venue and any(
            kw in self.venue.lower()
            for kw in ("proceedings", "conference", "symposium", "workshop")
        ):
            return "inproceedings"
        if self.venue:
            return "article"
        if self.arxiv_id:
            return "misc"
        return "misc"

    @property
    def bibtex_key(self) -> str:
        """Generate cite key: FirstAuthorLastname + Year + FirstSignificantTitleWord."""
        last = ""
        if self.authors:
            name = self.authors[0].name
            parts = name.strip().split()
            last = _ascii_only(parts[-1]) if parts else "Unknown"
        year = str(self.year) if self.year else "XXXX"
        # First significant word of title (skip articles/prepositions)
        _stop = {"a", "an", "the", "of", "in", "on", "at", "to", "and", "or", "for"}
        title_word = ""
        for w in re.split(r"\W+", self.title or ""):
            if w.lower() not in _stop and len(w) > 1:
                title_word = _ascii_only(w).capitalize()
                break
        return f"{last}{year}{title_word}" or "Unknown"


def _normalize_doi(doi: Optional[str]) -> Optional[str]:
    if not doi:
        return None
    doi = doi.strip()
    # Strip URL prefix
    for prefix in ("https://doi.org/", "http://doi.org/", "doi.org/"):
        if doi.lower().startswith(prefix):
            doi = doi[len(prefix):]
            break
    return doi.lower() or None


def _ascii_only(s: str) -> str:
    """Keep only ASCII letters and digits."""
    return re.sub(r"[^A-Za-z0-9]", "", s)
