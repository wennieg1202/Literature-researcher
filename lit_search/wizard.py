"""Interactive terminal wizard for the literature search agent.

Guides the user through all search options via arrow-key menus.
Returns a SearchConfig dataclass ready to pass to agent.run().
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from . import sociology
from . import config


@dataclass
class SearchConfig:
    query: str
    mode: str = "balanced"
    perspective: Optional[str] = None
    max_papers: int = 50
    top_snowball: int = 10
    include_abstract: bool = False
    save_notion: bool = False
    use_cache: bool = True
    output: Optional[str] = None


def run_wizard() -> SearchConfig:
    """Run interactive wizard. Returns SearchConfig or raises SystemExit."""
    try:
        import questionary
        from questionary import Style
    except ImportError:
        Console().print("[red]questionary not installed. Run: pip install questionary[/red]")
        sys.exit(1)

    console = Console()
    console.print(Panel(
        Text.from_markup(
            "[bold blue]Literature Search Agent[/bold blue]\n"
            "[dim]Interactive search wizard — press Enter to confirm each choice[/dim]"
        ),
        expand=False,
        border_style="blue",
    ))
    console.print()

    custom_style = Style([
        ("qmark",        "fg:#00bfff bold"),
        ("question",     "bold"),
        ("answer",       "fg:#00bfff bold"),
        ("pointer",      "fg:#00bfff bold"),
        ("highlighted",  "fg:#00bfff bold"),
        ("selected",     "fg:#00bfff"),
        ("separator",    "fg:#6c6c6c"),
        ("instruction",  "fg:#6c6c6c"),
    ])

    # ── Step 1: Query ────────────────────────────────────────────────────────
    query = questionary.text(
        "研究主题或问题（输入中英文均可）",
        instruction="例如：'AI 对组织结构的影响' 或 'Why do elite networks reproduce inequality?'",
        style=custom_style,
    ).ask()

    if not query or not query.strip():
        console.print("[yellow]No query entered. Exiting.[/yellow]")
        sys.exit(0)
    query = query.strip()

    # Warn if user pasted a Boolean string
    if _looks_like_boolean(query):
        console.print(
            "\n[yellow]提示：检测到 Boolean 查询语法（AND/OR/引号）。[/yellow]\n"
            "  向导会自动把你的主题扩展成搜索词，\n"
            "  建议改用自然语言描述，例如：\n"
            "  [cyan]society of thought collective intelligence multi-agent sociology[/cyan]\n"
        )
        keep = questionary.confirm(
            "继续使用这个 Boolean 查询？",
            default=False,
            style=custom_style,
        ).ask()
        if not keep:
            query = questionary.text(
                "请重新输入（自然语言）",
                style=custom_style,
            ).ask()
            if not query or not query.strip():
                sys.exit(0)
            query = query.strip()

    # ── Step 2: Search mode ───────────────────────────────────────────────────
    mode_choice = questionary.select(
        "Search goal:",
        choices=[
            questionary.Choice(
                "Balanced  —  mix of foundational and recent works  (default)",
                value="balanced",
            ),
            questionary.Choice(
                "Classic   —  highly cited, foundational works  (pre-2015 emphasis)",
                value="classic",
            ),
            questionary.Choice(
                "Frontier  —  latest research, 2020+ publications  (emerging trends)",
                value="frontier",
            ),
        ],
        style=custom_style,
    ).ask()

    if mode_choice is None:
        sys.exit(0)

    # ── Step 3: Sociological perspective ─────────────────────────────────────
    perspective_choices = [
        questionary.Choice("None  —  no specific theoretical lens", value=None),
    ]
    for key, label in sociology.list_perspectives():
        p = sociology.get_perspective(key)
        theorists = ", ".join(p["key_theorists"][:3])
        perspective_choices.append(
            questionary.Choice(f"{label}  [{theorists}]", value=key)
        )

    perspective_choice = questionary.select(
        "Sociological perspective:",
        choices=perspective_choices,
        style=custom_style,
    ).ask()

    if perspective_choice is False:  # questionary returns False on Ctrl-C
        sys.exit(0)

    # ── Step 4: Max papers ────────────────────────────────────────────────────
    max_papers_choice = questionary.select(
        "Maximum number of papers to retrieve:",
        choices=[
            questionary.Choice("30   —  quick overview", value=30),
            questionary.Choice("50   —  standard search  (default)", value=50),
            questionary.Choice("100  —  comprehensive", value=100),
            questionary.Choice("150  —  exhaustive", value=150),
        ],
        default=questionary.Choice("50   —  standard search  (default)", value=50),
        style=custom_style,
    ).ask()

    if max_papers_choice is None:
        sys.exit(0)

    # ── Step 5: Include abstracts ─────────────────────────────────────────────
    include_abstract = questionary.confirm(
        "Include abstracts in BibTeX output?",
        default=False,
        style=custom_style,
    ).ask()

    # ── Step 6: Notion ────────────────────────────────────────────────────────
    save_notion = False
    if config.NOTION_API_KEY and config.NOTION_DATABASE_ID:
        save_notion = questionary.confirm(
            "Save results to Notion knowledge base?",
            default=True,
            style=custom_style,
        ).ask()
    elif _notion_partially_configured():
        console.print(
            "[dim]ℹ Notion: set both NOTION_API_KEY and NOTION_DATABASE_ID to enable.[/dim]"
        )

    # ── Step 7: Confirm ───────────────────────────────────────────────────────
    console.print()
    _print_summary(console, query, mode_choice, perspective_choice, max_papers_choice,
                   include_abstract, save_notion)

    confirmed = questionary.confirm(
        "Start search with these settings?",
        default=True,
        style=custom_style,
    ).ask()

    if not confirmed:
        console.print("[yellow]Cancelled.[/yellow]")
        sys.exit(0)

    console.print()

    return SearchConfig(
        query=query,
        mode=mode_choice,
        perspective=perspective_choice,
        max_papers=max_papers_choice,
        top_snowball=min(max_papers_choice // 3, 20),
        include_abstract=include_abstract,
        save_notion=save_notion,
    )


def _print_summary(
    console: Console,
    query: str,
    mode: str,
    perspective: Optional[str],
    max_papers: int,
    include_abstract: bool,
    save_notion: bool,
) -> None:
    lines = [
        f"  [bold]Query:[/bold]       {query}",
        f"  [bold]Mode:[/bold]        {mode}",
        f"  [bold]Perspective:[/bold] {perspective or 'none'}",
        f"  [bold]Max papers:[/bold]  {max_papers}",
        f"  [bold]Abstracts:[/bold]   {'yes' if include_abstract else 'no'}",
        f"  [bold]Notion:[/bold]      {'yes' if save_notion else 'no'}",
    ]
    console.print(Panel(
        "\n".join(lines),
        title="[bold]Search parameters[/bold]",
        expand=False,
        border_style="dim",
    ))
    console.print()


def _notion_partially_configured() -> bool:
    return bool(config.NOTION_API_KEY) != bool(config.NOTION_DATABASE_ID)


def _looks_like_boolean(query: str) -> bool:
    """Return True if the query looks like a Boolean search string."""
    import re
    q = query.upper()
    has_boolean = bool(re.search(r'\b(AND|OR|NOT)\b', q))
    has_quotes = query.count('"') >= 2
    has_parens = "(" in query and ")" in query
    return (has_boolean and (has_quotes or has_parens))
