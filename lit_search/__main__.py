"""CLI entry point for the literature search agent.

Usage:
    python -m lit_search "social capital in education"
    python -m lit_search "Why do elite networks reproduce inequality?" --mode classic --perspective organization
    python -m lit_search "What role does ritual play in organizational culture?" --mode frontier --perspective symbolic
    lit-search "credentialism and labor markets" --perspective profession --max-papers 80

Search modes:
    balanced   Default. Weights citation count + source coverage.
    classic    Prioritises highly cited foundational works.
    frontier   Prioritises papers published 2020+.

Sociological perspectives:
    profession      Sociology of professions & expertise (Abbott, Freidson, Larson)
    organization    Neo-institutional theory & org fields (DiMaggio, Powell, Meyer)
    symbolic        Symbolic interaction & cultural sociology (Goffman, Bourdieu, Collins)
    stratification  Social stratification & inequality (Tilly, Lareau, Lamont)
    network         Social network analysis (Granovetter, Burt, Lin)
    culture         Sociology of knowledge & culture (Mannheim, Latour, Knorr Cetina)

Environment variables:
    ANTHROPIC_API_KEY     Required for query expansion + summary (degrades gracefully if absent)
    CROSSREF_EMAIL        Enables CrossRef polite pool (recommended)
    GOOGLE_BOOKS_API_KEY  Raises Google Books daily quota
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
import time
from pathlib import Path

from rich.console import Console

from . import agent
from . import sociology

_VALID_PERSPECTIVES = list(sociology.PERSPECTIVES.keys())
_VALID_MODES = ["balanced", "classic", "frontier"]


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="lit-search",
        description="AI-powered academic literature search — like Google Scholar in your terminal.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "query",
        help=(
            "Research query or question. Can be keywords, a boolean string, "
            "or a full research question (e.g. 'Why do elite networks reproduce inequality?')"
        ),
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        metavar="FILE",
        help="Output .bib file path (default: auto-generated from query + timestamp)",
    )
    parser.add_argument(
        "--max-papers", "-n",
        type=int,
        default=150,
        metavar="N",
        help="Maximum number of papers in the output (default: 150)",
    )
    parser.add_argument(
        "--top-snowball",
        type=int,
        default=20,
        metavar="N",
        help="Number of top papers to use as snowball seeds (default: 20)",
    )
    parser.add_argument(
        "--mode",
        choices=_VALID_MODES,
        default="balanced",
        help=(
            "Search goal: 'balanced' (default) | 'classic' (foundational, high-citation) | "
            "'frontier' (latest 2020+ research)"
        ),
    )
    parser.add_argument(
        "--perspective",
        choices=_VALID_PERSPECTIVES,
        default=None,
        metavar="PERSPECTIVE",
        help=(
            "Sociological lens to apply: "
            + " | ".join(_VALID_PERSPECTIVES)
            + "  (see --list-perspectives for details)"
        ),
    )
    parser.add_argument(
        "--list-perspectives",
        action="store_true",
        help="Print available sociological perspectives and exit",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable HTTP response cache (always fetch fresh results)",
    )
    parser.add_argument(
        "--include-abstract",
        action="store_true",
        help="Include abstract field in BibTeX output",
    )

    # Handle --list-perspectives before full parse (no query needed)
    if "--list-perspectives" in sys.argv:
        _print_perspectives()
        sys.exit(0)

    args = parser.parse_args()

    output_path = args.output or _default_output(args.query)

    console = Console()
    try:
        asyncio.run(
            agent.run(
                query=args.query,
                output_path=output_path,
                max_papers=args.max_papers,
                top_snowball=args.top_snowball,
                use_cache=not args.no_cache,
                include_abstract=args.include_abstract,
                mode=args.mode,
                perspective=args.perspective,
            )
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        sys.exit(0)
    except Exception as exc:
        console.print(f"\n[bold red]Error:[/bold red] {exc}")
        sys.exit(1)


def _default_output(query: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", query.lower()).strip("_")[:40]
    ts = time.strftime("%Y%m%d_%H%M%S")
    return str(Path.cwd() / f"{slug}_{ts}.bib")


def _print_perspectives() -> None:
    console = Console()
    console.print("\n[bold]Available sociological perspectives:[/bold]\n")
    for key, label in sociology.list_perspectives():
        p = sociology.get_perspective(key)
        theorists = ", ".join(p["key_theorists"][:4])
        console.print(f"  [cyan]{key:<16}[/cyan] {label}")
        console.print(f"  {'':16} Key theorists: {theorists}")
        console.print()


if __name__ == "__main__":
    main()
