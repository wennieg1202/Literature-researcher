"""BibTeX export and Claude literature summary.

export_bibtex() writes a .bib file.
summarize() appends a Claude-generated landscape as BibTeX comments.
"""

from __future__ import annotations

import re
import textwrap
from pathlib import Path
from typing import Optional

from .. import config
from ..models import Paper


# ── BibTeX writer ──────────────────────────────────────────────────────────────

def export_bibtex(
    papers: list[Paper],
    output_path: str,
    include_abstract: bool = False,
    query: str = "",
    summary: Optional[str] = None,
    mode: str = "balanced",
    perspective: Optional[str] = None,
    extra_header: Optional[str] = None,
) -> int:
    """Write papers to a .bib file. Returns number of entries written."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []

    # Extra header (e.g. AI-generated warning)
    if extra_header:
        lines.append(extra_header.rstrip())
        lines.append("")

    # Header comment
    lines.append(f"% Literature search results")
    if query:
        lines.append(f"% Query: {query}")
    if mode != "balanced":
        lines.append(f"% Mode: {mode}")
    if perspective:
        lines.append(f"% Perspective: {perspective}")
    lines.append(f"% Total entries: {len(papers)}")
    lines.append(f"% Sources: {_source_summary(papers)}")
    lines.append("")

    # Deduplicate cite keys
    seen_keys: dict[str, int] = {}
    for paper in papers:
        key = paper.bibtex_key
        if key in seen_keys:
            seen_keys[key] += 1
            key = f"{key}{seen_keys[key]}"
        else:
            seen_keys[key] = 0
        lines.append(_paper_to_bibtex(paper, key, include_abstract))
        lines.append("")

    # Append Claude summary as comment block
    if summary:
        lines.append("%" * 70)
        lines.append("% LITERATURE LANDSCAPE (AI-generated summary)")
        lines.append("%" * 70)
        for line in summary.splitlines():
            lines.append(f"% {line}")
        lines.append("")

    Path(output_path).write_text("\n".join(lines), encoding="utf-8")
    return len(papers)


def _paper_to_bibtex(paper: Paper, key: str, include_abstract: bool) -> str:
    entry_type = paper.entry_type
    fields: list[tuple[str, str]] = []

    def add(bib_field: str, value: Optional[str]) -> None:
        if value:
            fields.append((bib_field, _escape_bibtex(value)))

    add("title", paper.title)

    if paper.authors:
        add("author", " and ".join(a.name for a in paper.authors))

    add("year", str(paper.year) if paper.year else None)

    if entry_type == "inproceedings":
        add("booktitle", paper.venue)
    elif entry_type == "book":
        add("publisher", paper.publisher)
    else:
        add("journal", paper.venue)
        add("volume", paper.volume)
        add("number", paper.issue)
        add("pages", paper.pages)
        add("publisher", paper.publisher)

    add("doi", paper.doi if paper.doi and not paper.doi.startswith("isbn:") else None)
    add("url", paper.url)

    if include_abstract:
        add("abstract", paper.abstract)

    # Source metadata as note
    if paper.sources:
        add("note", f"Sources: {', '.join(paper.sources)}")

    field_lines = "\n".join(f"  {f} = {{{v}}}," for f, v in fields)
    return f"@{entry_type}{{{key},\n{field_lines}\n}}"


def _escape_bibtex(s: str) -> str:
    """Escape string for use inside BibTeX {value} delimiters."""
    # Remove control characters
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s)
    # Escape LaTeX-active characters that are dangerous inside BibTeX values
    # Order matters: backslash first
    s = s.replace("\\", "\\textbackslash{}")
    s = s.replace("%", "\\%")
    s = s.replace("&", "\\&")
    s = s.replace("_", "\\_")
    s = s.replace("#", "\\#")
    s = s.replace("$", "\\$")
    s = s.replace("^", "\\^{}")
    s = s.replace("~", "\\~{}")
    # Trim to reasonable length
    if len(s) > 2000:
        s = s[:2000] + "..."
    return s


def _source_summary(papers: list[Paper]) -> str:
    counts: dict[str, int] = {}
    for p in papers:
        for s in p.sources:
            counts[s] = counts.get(s, 0) + 1
    return ", ".join(f"{s}:{n}" for s, n in sorted(counts.items()))


# ── Claude summary ─────────────────────────────────────────────────────────────

def summarize(
    papers: list[Paper],
    query: str,
    mode: str = "balanced",
    perspective: Optional[str] = None,
) -> Optional[str]:
    """Generate a literature landscape via Claude. Returns None if unavailable."""
    if not config.ANTHROPIC_API_KEY:
        return None

    top = papers[:10]
    abstracts = []
    for i, p in enumerate(top, 1):
        authors = ", ".join(a.name for a in p.authors[:3])
        if len(p.authors) > 3:
            authors += " et al."
        snippet = (p.abstract or "No abstract available.")[:400]
        abstracts.append(
            f"[{i}] {p.title} ({authors}, {p.year}, citations: {p.citation_count})\n{snippet}"
        )

    context = "\n\n".join(abstracts)

    # Mode-specific framing
    mode_instruction = {
        "classic": (
            "Focus on the foundational contributions, theoretical lineages, and how "
            "these seminal works shaped subsequent scholarship. Identify the key debates "
            "that have defined this field."
        ),
        "frontier": (
            "Focus on the emerging trends, recent theoretical innovations, and open questions. "
            "Highlight how recent work extends, challenges, or departs from earlier traditions. "
            "Identify the most active research fronts."
        ),
        "balanced": (
            "Synthesise key themes, debates, and gaps across both foundational and recent papers. "
            "Be analytical, not merely descriptive."
        ),
    }.get(mode, "")

    # Perspective-specific framing
    perspective_instruction = ""
    if perspective:
        try:
            from .. import sociology
            p_info = sociology.get_perspective(perspective)
            if p_info:
                perspective_instruction = (
                    f"\n\nRead these papers through the lens of {p_info['label']}. "
                    f"Connect findings to key concepts such as: "
                    f"{', '.join(p_info['core_concepts'][:5])}. "
                    f"Where relevant, note how the work relates to "
                    f"{', '.join(p_info['key_theorists'][:4])}."
                )
        except Exception:
            pass

    prompt = (
        f'Research query: "{query}"\n\n'
        f"Top papers found (with abstracts):\n\n{context}\n\n"
        f"Write a 280-360 word literature landscape. {mode_instruction}"
        f"{perspective_instruction}\n\n"
        "Reference papers by author and year. End with one sentence identifying the key open question."
    )

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=config.MAX_TOKENS_SUMMARIZE,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except Exception:
        return None
