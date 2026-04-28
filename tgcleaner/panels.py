"""Rich-rendered panels and labels: stats overview, selection summary, dry-run lines."""

from __future__ import annotations

from collections import Counter

from rich.panel import Panel
from rich.table import Table

from .console import KIND_STYLE, console
from .dialogs import days_since, kind_of, safe_name


def show_stats(dialogs) -> None:
    counts = Counter(kind_of(d.entity) for d in dialogs)
    unread = sum(d.unread_count for d in dialogs)
    muted = sum(1 for d in dialogs if d.dialog.notify_settings.mute_until)
    stale = sum(1 for d in dialogs if days_since(d.date) >= 90)

    t = Table.grid(padding=(0, 2))
    t.add_column(style="bold")
    t.add_column()
    t.add_row("Total dialogs:", f"{len(dialogs)}")
    t.add_row("Channels:",      f"[cyan]{counts.get('CHANNEL', 0)}[/]")
    t.add_row("Groups:",        f"[magenta]{counts.get('GROUP', 0)}[/]")
    t.add_row("DMs:",           f"[green]{counts.get('DM', 0)}[/]")
    t.add_row("Bots:",          f"[yellow]{counts.get('BOT', 0)}[/]")
    t.add_row("Muted:",         f"{muted}")
    t.add_row("Stale (90d+):",  f"{stale}")
    t.add_row("Unread total:",  f"{unread}")
    console.print(Panel(t, title="[bold]Your Telegram[/]",
                        border_style="blue", expand=False))


def selection_summary(selected) -> Table:
    counts = Counter(kind_of(d.entity) for d in selected)
    t = Table(title=f"About to remove {len(selected)} dialog(s)",
              title_style="bold red", border_style="red", show_header=True,
              header_style="bold")
    t.add_column("Kind")
    t.add_column("Count", justify="right")
    for k, n in counts.most_common():
        t.add_row(f"[{KIND_STYLE.get(k, 'white')}]{k}[/]", str(n))
    return t


def format_label(d) -> str:
    """One-line label used in dry-run / progress logs."""
    k = kind_of(d.entity)
    age = days_since(d.date)
    age_str = f"{age:>4}d ago" if age < 99999 else "  ?  "
    unread = f"●{d.unread_count}" if d.unread_count else " "
    muted = "M" if d.dialog.notify_settings.mute_until else " "
    name = safe_name(d)[:60]
    return (f"[{KIND_STYLE.get(k, 'white')}]{k:<7}[/] {muted} {age_str} "
            f"{unread:>4}  {name}")
