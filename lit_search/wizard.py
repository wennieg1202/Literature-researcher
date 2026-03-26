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
            "[bold blue]文献搜索助手[/bold blue]\n"
            "[dim]用方向键选择，Enter 确认，Ctrl-C 退出[/dim]"
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
        "搜索目标：",
        choices=[
            questionary.Choice("均衡  —  兼顾经典与近期文献（默认）", value="balanced"),
            questionary.Choice("经典  —  高被引奠基文献（2015年前为主）", value="classic"),
            questionary.Choice("前沿  —  最新研究（2020年后发表）", value="frontier"),
        ],
        style=custom_style,
    ).ask()

    if mode_choice is None:
        sys.exit(0)

    # ── Step 3: Sociological perspective ─────────────────────────────────────
    perspective_choices = [
        questionary.Choice("无  —  不限定理论视角", value=None),
    ]
    for key, label in sociology.list_perspectives():
        perspective_choices.append(
            questionary.Choice(label, value=key)
        )

    perspective_choice = questionary.select(
        "社会学理论视角（可选）：",
        choices=perspective_choices,
        style=custom_style,
    ).ask()

    if perspective_choice is False:
        sys.exit(0)

    # ── Step 4: Max papers ────────────────────────────────────────────────────
    max_papers_choice = questionary.select(
        "最多返回篇数：",
        choices=[
            questionary.Choice("30   —  快速了解", value=30),
            questionary.Choice("50   —  标准搜索（默认）", value=50),
            questionary.Choice("100  —  深度搜索", value=100),
            questionary.Choice("150  —  全面搜索", value=150),
        ],
        default=questionary.Choice("50   —  标准搜索（默认）", value=50),
        style=custom_style,
    ).ask()

    if max_papers_choice is None:
        sys.exit(0)

    # ── Step 5: Include abstracts ─────────────────────────────────────────────
    include_abstract = questionary.confirm(
        "BibTeX 中包含摘要？",
        default=False,
        style=custom_style,
    ).ask()

    # ── Step 6: Notion ────────────────────────────────────────────────────────
    save_notion = False
    if config.NOTION_API_KEY and config.NOTION_DATABASE_ID:
        save_notion = questionary.confirm(
            "搜索结果保存到 Notion？",
            default=True,
            style=custom_style,
        ).ask()
    elif _notion_partially_configured():
        console.print(
            "[dim]ℹ Notion：需同时设置 NOTION_API_KEY 和 NOTION_DATABASE_ID。[/dim]"
        )

    # ── Step 7: Confirm ───────────────────────────────────────────────────────
    console.print()
    _print_summary(console, query, mode_choice, perspective_choice, max_papers_choice,
                   include_abstract, save_notion)

    confirmed = questionary.confirm(
        "确认开始搜索？",
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
    mode_labels = {"balanced": "均衡", "classic": "经典", "frontier": "前沿"}
    lines = [
        f"  [bold]主题：[/bold]   {query}",
        f"  [bold]模式：[/bold]   {mode_labels.get(mode, mode)}",
        f"  [bold]视角：[/bold]   {perspective or '无'}",
        f"  [bold]篇数：[/bold]   {max_papers}",
        f"  [bold]摘要：[/bold]   {'是' if include_abstract else '否'}",
        f"  [bold]Notion：[/bold] {'是' if save_notion else '否'}",
    ]
    console.print(Panel(
        "\n".join(lines),
        title="[bold]搜索参数确认[/bold]",
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
