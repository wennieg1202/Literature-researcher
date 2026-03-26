"""Main orchestrator — wires all skills together in sequence.

Pipeline:
  1. query_expand   → structured search terms (Claude)
  2. multi_search   → raw papers from all 8 APIs (parallel)
  3. dedup + rank   → clean, scored paper list
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

from . import config
from .cache import get_cache
from .models import Paper
from .skills import query_expand, search_apis
from .skills.dedup import deduplicate, rank
from .skills.snowball import snowball
from .skills.export import export_bibtex, summarize


async def run(
    query: str,
    output_path: str,
    max_papers: int = config.MAX_PAPERS_DEFAULT,
    top_snowball: int = config.TOP_SNOWBALL_COUNT,
    use_cache: bool = True,
    include_abstract: bool = False,
) -> None:
    console = Console()
    cache = get_cache(enabled=use_cache)

    console.rule("[bold blue]Literature Search Agent[/bold blue]")
    console.print(f"[bold]Query:[/bold] {query}")
    console.print(f"[bold]Output:[/bold] {output_path}")
    console.print()

    # ── Step 1: Query expansion ───────────────────────────────────────────────
    with _spinner(console, "Expanding query with Claude..."):
        expanded = query_expand.expand(query)

    terms = query_expand.all_terms(expanded)
    console.print(f"[cyan]Expanded to {len(terms)} search terms:[/cyan]")
    for t in terms:
        console.print(f"  • {t}")
    if expanded.get("scope_note"):
        console.print(f"  [dim]{expanded['scope_note']}[/dim]")
    console.print()

    # ── Step 2: Multi-source search ───────────────────────────────────────────
    console.print("[bold]Searching all sources...[/bold]")
    raw_papers = await search_apis.multi_search(terms, cache=cache, console=console)
    console.print(f"\n[cyan]Raw results: {len(raw_papers)} papers[/cyan]\n")

    # ── Step 3: Dedup & rank ───────────────────────────────────────────────────
    with _spinner(console, "Deduplicating..."):
        papers = deduplicate(raw_papers)
        papers = rank(papers)

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
            papers = rank(papers)
        console.print(f"[cyan]Corpus after snowball: {len(papers)} papers[/cyan]\n")

    # ── Step 6: Trim to max ────────────────────────────────────────────────────
    if len(papers) > max_papers:
        papers = papers[:max_papers]
        console.print(f"[dim]Trimmed to top {max_papers} papers by relevance score.[/dim]\n")

    # ── Step 7: Claude summary ─────────────────────────────────────────────────
    summary: Optional[str] = None
    if config.ANTHROPIC_API_KEY:
        with _spinner(console, "Generating literature landscape summary..."):
            summary = summarize(papers, query)
    else:
        console.print("[yellow]⚠ ANTHROPIC_API_KEY not set — skipping summary.[/yellow]")

    # ── Step 8: Export ─────────────────────────────────────────────────────────
    with _spinner(console, f"Writing {output_path}..."):
        n = export_bibtex(
            papers,
            output_path,
            include_abstract=include_abstract,
            query=query,
            summary=summary,
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
