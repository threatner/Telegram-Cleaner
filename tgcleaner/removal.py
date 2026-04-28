"""Two-step channel leave + delete, retry-on-flood/connection, batch executor."""

from __future__ import annotations

import asyncio
from typing import Optional

from rich.markup import escape
from rich.panel import Panel
from rich.progress import (BarColumn, MofNCompleteColumn, Progress,
                           SpinnerColumn, TextColumn, TimeElapsedColumn)
from rich.table import Table
from telethon import TelegramClient, errors
from telethon.tl.functions.channels import LeaveChannelRequest
from telethon.tl.types import Channel, User

from .console import console
from .panels import format_label


async def remove_dialog(client: TelegramClient, d, revoke_dms: bool) -> None:
    """Channels: leave (opt-out) first, then clean from chat list.
    DMs: optionally revoke on the other side (skipped for bots).
    Basic groups: single delete_dialog call.
    """
    entity = d.entity
    if isinstance(entity, User):
        is_bot = getattr(entity, "bot", False)
        await client.delete_dialog(entity, revoke=revoke_dms and not is_bot)
        return
    if isinstance(entity, Channel):
        # Step 1: leave (opt-out). Idempotent; tolerate "already gone" states.
        try:
            await client(LeaveChannelRequest(entity))
        except errors.UserNotParticipantError:
            pass
        except errors.RPCError as e:
            console.print(f"   [dim]leave step note: {escape(str(e))}[/]")
        await asyncio.sleep(0.3)  # let the server propagate the leave
        try:
            await client.delete_dialog(entity)
        except Exception:
            # leave already succeeded; list cleanup may already be done
            pass
        return
    await client.delete_dialog(entity)  # legacy basic Chat


async def remove_with_retry(client: TelegramClient, d, revoke_dms: bool,
                            max_attempts: int = 4) -> None:
    last_err: Optional[BaseException] = None
    for attempt in range(1, max_attempts + 1):
        try:
            await remove_dialog(client, d, revoke_dms=revoke_dms)
            return
        except errors.FloodWaitError as e:
            console.print(f"   [yellow]flood wait {e.seconds}s — sleeping...[/]")
            await asyncio.sleep(e.seconds + 1)
            last_err = e
        except (ConnectionError, OSError) as e:
            backoff = min(2 ** attempt, 30)
            console.print(f"   [yellow]connection issue ([dim]{e}[/]); "
                          f"retry in {backoff}s ({attempt}/{max_attempts})[/]")
            last_err = e
            await asyncio.sleep(backoff)
            try:
                if not client.is_connected():
                    await client.connect()
            except Exception:
                pass
    raise RuntimeError(f"giving up after {max_attempts} attempts: {last_err}")


async def execute_removals(client: TelegramClient, selected, dry_run: bool,
                           revoke_dms: bool) -> tuple[int, int]:
    if dry_run:
        console.print(Panel(
            f"[bold yellow]DRY RUN[/] — would remove {len(selected)} dialog(s).\n"
            "[dim]Nothing will be changed on Telegram.[/]",
            border_style="yellow", expand=False))
        for d in selected:
            console.print(f"  [dim]would remove[/]  {format_label(d)}")
        return 0, 0

    ok = fail = 0
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold]{task.description}"),
        BarColumn(bar_width=30),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    )
    with progress:
        task = progress.add_task("Removing", total=len(selected))
        for d in selected:
            label = format_label(d)
            try:
                await remove_with_retry(client, d, revoke_dms=revoke_dms)
                console.print(f"  [green]✓[/] {label}")
                ok += 1
                await asyncio.sleep(1.0)  # be polite to the API
            except Exception as e:
                console.print(f"  [red]✗[/] {label}  [dim]({escape(str(e))})[/]")
                fail += 1
            progress.advance(task)

    result = Table.grid(padding=(0, 2))
    result.add_column(style="bold")
    result.add_column()
    result.add_row("Succeeded:", f"[green]{ok}[/]")
    result.add_row("Failed:",    f"[red]{fail}[/]" if fail else "0")
    console.print(Panel(result, title="Done", border_style="green", expand=False))
    return ok, fail
