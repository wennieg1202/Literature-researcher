"""CLI entry point for the literature search agent.

Usage:
    python -m lit_search "social capital in education"
    python -m lit_search "network ties" --output results.bib --max-papers 100
    lit-search "civic engagement" --no-cache --include-abstract

Environment variables:
    ANTHROPIC_API_KEY     Required for query expansion + summary (optional, degrades gracefully)
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


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="lit-search",
        description="AI-powered academic literature search — like Google Scholar in your terminal.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "query",
        help="Natural language research query (e.g. 'social capital in education')",
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
        "--no-cache",
        action="store_true",
        help="Disable HTTP response cache (always fetch fresh results)",
    )
    parser.add_argument(
        "--include-abstract",
        action="store_true",
        help="Include abstract field in BibTeX output",
    )

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


if __name__ == "__main__":
    main()
