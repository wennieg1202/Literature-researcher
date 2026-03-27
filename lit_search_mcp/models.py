from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
import re


@dataclass
class Author:
    name: str
    orcid: Optional[str] = None

    def __str__(self) -> str:
        return self.name


@dataclass
class Paper:
    title: str
    year: Optional[int] = None
    authors: List[Author] = field(default_factory=list)
    abstract: Optional[str] = None
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    s2_id: Optional[str] = None
    openalex_id: Optional[str] = None
    venue: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None
    publisher: Optional[str] = None
    url: Optional[str] = None
    pdf_url: Optional[str] = None
    citation_count: int = 0
    sources: List[str] = field(default_factory=list)
    relevance_score: float = 0.0

    @property
    def bibtex_key(self) -> str:
        first_author = self.authors[0].name.split()[-1] if self.authors else "Unknown"
        first_author = re.sub(r"[^a-zA-Z]", "", first_author)
        year = str(self.year) if self.year else "0000"
        title_word = re.sub(r"[^a-zA-Z]", "", (self.title or "").split()[0]) if self.title else "untitled"
        return f"{first_author}{year}{title_word}"

    @property
    def entry_type(self) -> str:
        venue = (self.venue or "").lower()
        if any(k in venue for k in ["proceedings", "conference", "workshop", "symposium"]):
            return "inproceedings"
        if any(k in venue for k in ["book", "press", "publisher"]):
            return "book"
        if self.arxiv_id:
            return "misc"
        return "article"

    def to_bibtex(self) -> str:
        key = self.bibtex_key
        entry_type = self.entry_type
        lines = [f"@{entry_type}{{{key},"]
        lines.append(f"  title = {{{self.title or ''}}},")
        if self.authors:
            author_str = " and ".join(str(a) for a in self.authors)
            lines.append(f"  author = {{{author_str}}},")
        if self.year:
            lines.append(f"  year = {{{self.year}}},")
        if self.venue:
            field_name = "booktitle" if entry_type == "inproceedings" else "journal"
            lines.append(f"  {field_name} = {{{self.venue}}},")
        if self.volume:
            lines.append(f"  volume = {{{self.volume}}},")
        if self.issue:
            lines.append(f"  number = {{{self.issue}}},")
        if self.pages:
            lines.append(f"  pages = {{{self.pages}}},")
        if self.publisher:
            lines.append(f"  publisher = {{{self.publisher}}},")
        if self.doi:
            lines.append(f"  doi = {{{self.doi}}},")
        if self.url:
            lines.append(f"  url = {{{self.url}}},")
        lines.append("}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "year": self.year,
            "authors": [str(a) for a in self.authors],
            "abstract": self.abstract,
            "doi": self.doi,
            "arxiv_id": self.arxiv_id,
            "s2_id": self.s2_id,
            "openalex_id": self.openalex_id,
            "venue": self.venue,
            "url": self.url,
            "pdf_url": self.pdf_url,
            "citation_count": self.citation_count,
            "sources": self.sources,
            "relevance_score": self.relevance_score,
            "bibtex_key": self.bibtex_key,
        }
