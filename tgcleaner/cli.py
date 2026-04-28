"""Top-level CLI flow: login → fetch → select (TUI) → confirm → execute → loop."""

from __future__ import annotations

import asyncio
import sys
from typing import Optional

import questionary
from rich.panel import Panel
from telethon import TelegramClient
from telethon.tl.types import User

from .auth import login
from .config import SESSION_PATH, ensure_credentials, load_dotenv
from .console import console
from .dialogs import fetch_dialogs
from .panels import selection_summary, show_stats
from .removal import execute_removals
from .tui import CleanerApp


async def pick_initial_filter() -> Optional[str]:
    return await questionary.select(
        "Start with which category? (you can switch inside the selector)",
        choices=[
            questionary.Choice("Channels  (broadcasts you've joined)", "channels"),
            questionary.Choice("Groups",                                "groups"),
            questionary.Choice("DMs       (1-on-1 chats with people)", "dms"),
            questionary.Choice("Bots",                                  "bots"),
            questionary.Choice("Muted dialogs",                         "muted"),
            questionary.Choice("Stale     (no activity in 90+ days)",  "stale"),
            questionary.Choice("All dialogs",                           "all"),
        ],
    ).unsafe_ask_async()


async def ask_continue(prompt: str = "Clean up another batch?") -> bool:
    return await questionary.confirm(prompt, default=False).unsafe_ask_async()


async def one_round(client: TelegramClient) -> bool:
    """Run one fetch → select → confirm → execute cycle.
    Returns True if user wants another round, False to exit.
    """
    with console.status("[cyan]Loading dialogs...", spinner="dots"):
        dialogs = await fetch_dialogs(client)

    if not dialogs:
        console.print("[yellow]No dialogs found. Nothing to clean.[/]")
        return False

    show_stats(dialogs)

    initial = await pick_initial_filter()
    if not initial:
        return False

    console.print("\n[dim]Launching selector — press [bold]?[/] inside for help.[/]\n")
    app = CleanerApp(dialogs, initial_filter=initial)
    selected = await app.run_async()

    if not selected:
        console.print("[yellow]Nothing selected.[/]")
        return await ask_continue("Pick a different category?")

    console.print()
    console.print(selection_summary(selected))

    revoke_dms = False
    if any(isinstance(d.entity, User) and not getattr(d.entity, "bot", False)
           for d in selected):
        revoke_dms = await questionary.confirm(
            "Also delete DM history on the OTHER person's side? "
            "(revoke=True; default no — keeps it on their side)",
            default=False,
        ).unsafe_ask_async()

    dry_run = await questionary.confirm(
        "Dry-run first? (recommended — shows what would happen, no changes)",
        default=True,
    ).unsafe_ask_async()

    await execute_removals(client, selected, dry_run=dry_run, revoke_dms=revoke_dms)

    if dry_run:
        if await questionary.confirm("Run for real now?",
                                     default=False).unsafe_ask_async():
            await execute_removals(client, selected, dry_run=False,
                                   revoke_dms=revoke_dms)

    return await ask_continue()


async def main() -> None:
    load_dotenv()
    api_id, api_hash = await ensure_credentials()

    client = TelegramClient(str(SESSION_PATH), api_id, api_hash)
    console.print(Panel.fit(
        "[bold cyan]Telegram Cleaner[/]\n"
        "[dim]Bulk leave channels/groups and delete DMs[/]",
        border_style="cyan"))

    try:
        await login(client)
        while True:
            again = await one_round(client)
            if not again:
                break
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

    console.print("\n[bold green]Bye.[/]")


def run() -> None:
    """Synchronous entry point for the `tgcleaner` console script."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled.[/]")
        sys.exit(130)


if __name__ == "__main__":
    run()
