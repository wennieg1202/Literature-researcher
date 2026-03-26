"""Main orchestrator — wires all skills together in sequence.

Pipeline:
  1. query_expand   → structured search terms (Claude), mode + perspective aware
  2. multi_search   → raw papers from all 8 APIs (parallel)
  3. dedup + rank   → clean, scored paper list (mode-aware ranking)
  4. snowball       → 1-hop citation expansion on top-N
  5. dedup + rank   → re-score merged corpus
  6. export_bibtex  → write .bib file
  7. summarize      → Claude literature landscape (appended to .bib)
"""

from __future__ import annotations

import asyncio
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from . import config
from .cache import get_cache
from .models import Paper
from .skills import query_expand, search_apis
from .skills.dedup import deduplicate, rank
from .skills.snowball import snowball
from .skills.export import export_bibtex, summarize
from .skills.notion_export import export_to_notion
from . import sociology


async def run(
    query: str,
    output_path: str,
    max_papers: int = config.MAX_PAPERS_DEFAULT,
    top_snowball: int = config.TOP_SNOWBALL_COUNT,
    use_cache: bool = True,
    include_abstract: bool = False,
    mode: str = "balanced",
    perspective: Optional[str] = None,
    save_notion: bool = False,
) -> None:
    console = Console()
    cache = get_cache(enabled=use_cache)

    console.rule("[bold blue]Literature Search Agent[/bold blue]")
    console.print(f"[bold]Query:[/bold] {query}")
    console.print(f"[bold]Output:[/bold] {output_path}")

    # Print mode and perspective banners
    mode_labels = {
        "balanced": "Balanced (citations + recency)",
        "classic":  "Classic — high-citation foundational works",
        "frontier": "Frontier — latest published research",
    }
    console.print(f"[bold]Mode:[/bold] {mode_labels.get(mode, mode)}")

    if perspective:
        p_info = sociology.get_perspective(perspective)
        if p_info:
            console.print(f"[bold]Perspective:[/bold] {p_info['label']}")
            console.print(f"  [dim]{p_info['description']}[/dim]")
    console.print()

    # ── Step 1: Query expansion ───────────────────────────────────────────────
    with _spinner(console, "Expanding query with Claude..."):
        expanded = query_expand.expand(query, mode=mode, perspective=perspective)

    terms = query_expand.all_terms(expanded)

    # Show question reframe if applicable
    if expanded.get("_is_question") and expanded.get("question_reframe"):
        console.print(f"[cyan]Research question reframed as:[/cyan]")
        console.print(f"  [italic]{expanded['question_reframe']}[/italic]")

    console.print(f"[cyan]Expanded to {len(terms)} search terms:[/cyan]")
    for t in terms:
        console.print(f"  • {t}")
    if expanded.get("scope_note"):
        console.print(f"  [dim]{expanded['scope_note']}[/dim]")
    console.print()

    # Show perspective seed works if applicable
    if perspective:
        p_info = sociology.get_perspective(perspective)
        if p_info and p_info.get("canonical_works"):
            console.print(f"[cyan]Canonical works in this tradition:[/cyan]")
            for w in p_info["canonical_works"]:
                console.print(f"  [dim]→ {w}[/dim]")
            console.print()

    # ── Step 2: Multi-source search ───────────────────────────────────────────
    console.print("[bold]Searching all sources...[/bold]")
    raw_papers = await search_apis.multi_search(terms, cache=cache, console=console)
    console.print(f"\n[cyan]Raw results: {len(raw_papers)} papers[/cyan]\n")

    # ── Step 3: Dedup & rank ───────────────────────────────────────────────────
    with _spinner(console, "Deduplicating..."):
        papers = deduplicate(raw_papers)
        papers = rank(papers, mode=mode)

    console.print(f"[cyan]After dedup: {len(papers)} unique papers[/cyan]\n")

    # ── Step 4: Snowball ───────────────────────────────────────────────────────
    seeds = papers[:top_snowball]
    console.print(f"[bold]Snowballing from top {len(seeds)} papers...[/bold]")
    new_papers = await snowball(seeds, papers, cache=cache, console=console)
    console.print()

    # ── Step 5: Merge, dedup, rank again ──────────────────────────────────────
    if new_papers:
        with _spinner(console, "Merging snowball results..."):
            papers = deduplicate(papers + new_papers)
            papers = rank(papers, mode=mode)
        console.print(f"[cyan]Corpus after snowball: {len(papers)} papers[/cyan]\n")

    # ── Step 6: Frontier mode — enforce recency filter ────────────────────────
    if mode == "frontier":
        cutoff = 2020
        recent = [p for p in papers if p.year and p.year >= cutoff]
        older  = [p for p in papers if not p.year or p.year < cutoff]
        if recent:
            console.print(
                f"[dim]Frontier mode: {len(recent)} papers from {cutoff}+ "
                f"(+ {min(len(older), max(0, max_papers - len(recent)))} older for context)[/dim]\n"
            )
            # Keep recent papers first, pad with older if needed
            papers = recent + older

    # ── Step 7: Trim to max ────────────────────────────────────────────────────
    if len(papers) > max_papers:
        papers = papers[:max_papers]
        console.print(f"[dim]Trimmed to top {max_papers} papers by relevance score.[/dim]\n")

    # ── Step 8: Claude summary ─────────────────────────────────────────────────
    summary: Optional[str] = None
    if config.ANTHROPIC_API_KEY:
        with _spinner(console, "Generating literature landscape summary..."):
            summary = summarize(papers, query, mode=mode, perspective=perspective)
    else:
        console.print("[yellow]⚠ ANTHROPIC_API_KEY not set — skipping summary.[/yellow]")

    # ── Step 9: Export ─────────────────────────────────────────────────────────
    with _spinner(console, f"Writing {output_path}..."):
        n = export_bibtex(
            papers,
            output_path,
            include_abstract=include_abstract,
            query=query,
            summary=summary,
            mode=mode,
            perspective=perspective,
        )

    # ── Step 10: Notion export ────────────────────────────────────────────────
    if save_notion:
        console.print("[bold]Saving to Notion...[/bold]")
        await export_to_notion(
            papers, query, mode=mode, perspective=perspective, console=console
        )

    console.print()
    console.rule("[bold green]Done[/bold green]")
    console.print(f"[bold green]✓ {n} entries → {output_path}[/bold green]")

    if summary:
        console.print()
        console.print("[bold]Literature Landscape:[/bold]")
        console.print(summary)

    # Source breakdown
    _print_source_stats(console, papers)
    _print_year_distribution(console, papers)


def _spinner(console: Console, msg: str):
    return Progress(
        SpinnerColumn(),
        TextColumn(msg),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    )


def _print_source_stats(console: Console, papers: list[Paper]) -> None:
    counts: dict[str, int] = {}
    for p in papers:
        for s in p.sources:
            counts[s] = counts.get(s, 0) + 1
    if not counts:
        return
    console.print()
    console.print("[bold]Source breakdown:[/bold]")
    for src, n in sorted(counts.items(), key=lambda x: -x[1]):
        console.print(f"  {src:<18} {n:>4} papers")


def _print_year_distribution(console: Console, papers: list[Paper]) -> None:
    """Show rough decade distribution of results."""
    buckets: dict[str, int] = {}
    for p in papers:
        if not p.year:
            buckets["unknown"] = buckets.get("unknown", 0) + 1
        elif p.year >= 2020:
            buckets["2020s"] = buckets.get("2020s", 0) + 1
        elif p.year >= 2010:
            buckets["2010s"] = buckets.get("2010s", 0) + 1
        elif p.year >= 2000:
            buckets["2000s"] = buckets.get("2000s", 0) + 1
        elif p.year >= 1990:
            buckets["1990s"] = buckets.get("1990s", 0) + 1
        else:
            buckets["pre-1990"] = buckets.get("pre-1990", 0) + 1

    if not buckets:
        return
    console.print()
    console.print("[bold]Year distribution:[/bold]")
    for era in ["2020s", "2010s", "2000s", "1990s", "pre-1990", "unknown"]:
        n = buckets.get(era, 0)
        if n:
            bar = "█" * min(n, 30)
            console.print(f"  {era:<10} {n:>4}  {bar}")
