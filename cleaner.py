"""Telegram Cleaner — bulk leave channels/groups and delete DMs.

Two-step removal for channels: leave (opt-out) first, then clean from chat list.
Login via QR scan or phone number + in-app code (no SMS needed).
Login is cached in cleaner.session — only required once.

Usage:
    python cleaner.py

First-run will prompt for api_id and api_hash from https://my.telegram.org and
save them to .env (which is .gitignored).
"""

from __future__ import annotations

import asyncio
import os
import platform
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

import qrcode
import questionary
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.progress import (BarColumn, MofNCompleteColumn, Progress, SpinnerColumn,
                           TextColumn, TimeElapsedColumn)
from rich.table import Table
from telethon import TelegramClient, errors
from telethon.tl.functions.channels import LeaveChannelRequest
from telethon.tl.types import Channel, Chat, User
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import (Button, DataTable, Footer, Header, Input, Select,
                             Static)

# ─── paths / constants ──────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
SESSION_PATH = SCRIPT_DIR / "cleaner.session"
ENV_PATH = SCRIPT_DIR / ".env"
QR_PNG_PATH = SCRIPT_DIR / "login_qr.png"

console = Console()

KIND_STYLE = {
    "CHANNEL": "cyan",
    "GROUP":   "magenta",
    "DM":      "green",
    "BOT":     "yellow",
    "OTHER":   "white",
}

KIND_FILTERS = [
    ("All",          "all"),
    ("Channels",     "channels"),
    ("Groups",       "groups"),
    ("DMs",          "dms"),
    ("Bots",         "bots"),
    ("Muted",        "muted"),
    ("Stale (90d+)", "stale"),
]

# ─── env / credentials ──────────────────────────────────────────────────────


def load_dotenv() -> None:
    """Load KEY=VAL lines from ./.env into os.environ (without overwriting)."""
    if not ENV_PATH.exists():
        return
    for raw in ENV_PATH.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


async def ensure_credentials() -> tuple[int, str]:
    """Return (api_id, api_hash). Prompt + save to .env on first run."""
    api_id = os.environ.get("TG_API_ID")
    api_hash = os.environ.get("TG_API_HASH")
    if api_id and api_hash:
        try:
            return int(api_id), api_hash
        except ValueError:
            console.print("[red]TG_API_ID is not a number — re-prompting.[/]")

    console.print(Panel(
        "[bold]First-run setup[/]\n\n"
        "Get free API credentials from [link]https://my.telegram.org[/]\n"
        "  → log in with your phone\n"
        "  → click [bold]API development tools[/]\n"
        "  → create an application (any title works, platform: Desktop)\n"
        "  → copy the [bold]api_id[/] (number) and [bold]api_hash[/] (32-char string)\n",
        border_style="cyan", title="Setup"))

    if not await questionary.confirm(
        "Do you have your api_id and api_hash ready?", default=True
    ).unsafe_ask_async():
        console.print("[yellow]Open https://my.telegram.org, get them, then re-run.[/]")
        sys.exit(0)

    while True:
        raw_id = (await questionary.text("api_id (number):").unsafe_ask_async() or "").strip()
        if raw_id.isdigit():
            break
        console.print("[red]api_id must be a number.[/]")
    api_hash = (await questionary.password("api_hash:").unsafe_ask_async() or "").strip()
    if not api_hash:
        console.print("[red]api_hash is required.[/]")
        sys.exit(1)

    if await questionary.confirm(
        f"Save to {ENV_PATH.name} so you don't re-enter next time?",
        default=True,
    ).unsafe_ask_async():
        ENV_PATH.write_text(f"TG_API_ID={raw_id}\nTG_API_HASH={api_hash}\n")
        try:
            ENV_PATH.chmod(0o600)
        except OSError:
            pass
        console.print(f"[green]Saved to {ENV_PATH}[/] [dim](mode 0600, gitignored)[/]")

    return int(raw_id), api_hash


# ─── helpers ────────────────────────────────────────────────────────────────


def kind_of(entity) -> str:
    if isinstance(entity, Channel):
        return "CHANNEL" if entity.broadcast else "GROUP"
    if isinstance(entity, Chat):
        return "GROUP"
    if isinstance(entity, User):
        return "BOT" if getattr(entity, "bot", False) else "DM"
    return "OTHER"


def days_since(dt) -> int:
    if not dt:
        return 99999
    return max(0, (datetime.now(timezone.utc) - dt).days)


def matches_filter(d, kind_filter: str) -> bool:
    if kind_filter == "all":
        return True
    k = kind_of(d.entity)
    if kind_filter == "channels": return k == "CHANNEL"
    if kind_filter == "groups":   return k == "GROUP"
    if kind_filter == "dms":      return k == "DM"
    if kind_filter == "bots":     return k == "BOT"
    if kind_filter == "muted":    return bool(d.dialog.notify_settings.mute_until)
    if kind_filter == "stale":    return days_since(d.date) >= 90
    return True


def display_name(d) -> str:
    """Best-effort human-readable label. Falls back to @username, phone, or '<no name>'."""
    if d.name:
        return d.name
    e = d.entity
    username = getattr(e, "username", None)
    if username:
        return f"@{username}"
    if isinstance(e, User):
        phone = getattr(e, "phone", None)
        if phone:
            return f"+{phone}"
        if getattr(e, "is_self", False):
            return "Saved Messages"
    return "<no name>"


def safe_name(d) -> str:
    """Dialog name with Rich markup escaped — never trust user-provided strings."""
    return escape(display_name(d))


def searchable_text(d) -> str:
    """All text fields a user might type to find this dialog (lowercased)."""
    parts: list[str] = []
    if d.name:
        parts.append(d.name)
    e = d.entity
    username = getattr(e, "username", None)
    if username:
        parts.append("@" + username)
    if isinstance(e, User):
        for attr in ("first_name", "last_name", "phone"):
            v = getattr(e, attr, None)
            if v:
                parts.append(str(v))
    elif isinstance(e, (Channel, Chat)):
        title = getattr(e, "title", None)
        if title:
            parts.append(title)
    return " ".join(parts).lower()


# ─── stats / summary panels ────────────────────────────────────────────────


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


# ─── login ──────────────────────────────────────────────────────────────────


def open_in_default_viewer(path: Path) -> bool:
    """Best-effort: open `path` in the OS default app. Returns True if launched."""
    if os.environ.get("TG_NO_AUTO_OPEN"):
        return False
    try:
        system = platform.system()
        if system == "Darwin":
            subprocess.Popen(["open", str(path)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif system == "Linux":
            subprocess.Popen(["xdg-open", str(path)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif system == "Windows":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            return False
        return True
    except Exception:
        return False


def render_qr(url: str, ascii_inverted: bool = True) -> None:
    """Save the QR as PNG, try to auto-open it, and print ASCII QR as fallback."""
    qr = qrcode.QRCode(border=2)
    qr.add_data(url)
    qr.make()
    qr.make_image().save(QR_PNG_PATH)

    opened = open_in_default_viewer(QR_PNG_PATH)
    note = (
        f"\n[bold]QR ready.[/] Saved to [cyan]{QR_PNG_PATH}[/]\n"
        + ("  [dim](auto-opened in your default image viewer)[/]\n"
           if opened else
           f"  [dim](open it manually if needed: [bold]open {QR_PNG_PATH}[/])[/]\n")
        + "\n[dim]Terminal ASCII QR fallback below — try it if the image won't scan:[/]\n"
    )
    console.print(note)
    qr.print_ascii(invert=ascii_inverted)


def cleanup_qr_png() -> None:
    """Remove the saved QR after successful login — it's no longer useful."""
    try:
        QR_PNG_PATH.unlink(missing_ok=True)
    except Exception:
        pass


async def login_qr(client: TelegramClient) -> None:
    console.print("\n[bold]Scan from Telegram:[/]  Settings → Devices → Link Desktop Device\n")
    qr_login = await client.qr_login()
    try:
        while True:
            render_qr(qr_login.url)
            try:
                await qr_login.wait(timeout=60)
                return
            except asyncio.TimeoutError:
                console.print("[yellow]QR expired — regenerating...[/]")
                await qr_login.recreate()
            except errors.SessionPasswordNeededError:
                pwd = await questionary.password("2FA password:").unsafe_ask_async()
                await client.sign_in(password=pwd)
                return
    finally:
        cleanup_qr_png()


async def login_phone(client: TelegramClient) -> None:
    console.print(
        "\n[bold]Phone login.[/] Code is sent INSIDE Telegram (chat from "
        "'Telegram' official, blue check) if you're logged in elsewhere — "
        "otherwise SMS as fallback.\n")
    phone = (await questionary.text(
        "Phone number with country code (e.g. +911234567890):"
    ).unsafe_ask_async() or "").strip()
    if not phone:
        raise SystemExit("Phone number required.")
    try:
        sent = await client.send_code_request(phone)
    except errors.PhoneNumberInvalidError:
        console.print("[red]That phone number isn't valid. Include the country code "
                      "(e.g. +91 for India, +1 for US).[/]")
        raise SystemExit(1)
    except errors.PhoneNumberBannedError:
        console.print("[red]This number is banned by Telegram. Nothing this script "
                      "can do — contact Telegram support.[/]")
        raise SystemExit(1)
    except errors.FloodWaitError as e:
        console.print(f"[red]Telegram rate-limited the login. Wait {e.seconds}s, then re-run.[/]")
        raise SystemExit(1)

    console.print("[dim]Look for a chat from 'Telegram' (blue check).[/]")
    code = (await questionary.text("Code:").unsafe_ask_async() or "").strip()
    try:
        await client.sign_in(phone=phone, code=code,
                             phone_code_hash=sent.phone_code_hash)
    except errors.SessionPasswordNeededError:
        pwd = await questionary.password("2FA password:").unsafe_ask_async()
        try:
            await client.sign_in(password=pwd)
        except errors.PasswordHashInvalidError:
            console.print("[red]Wrong 2FA password. Re-run and try again.[/]")
            raise SystemExit(1)
    except errors.PhoneCodeInvalidError:
        console.print("[red]Wrong code. Re-run to try again.[/]")
        raise SystemExit(1)
    except errors.PhoneCodeExpiredError:
        console.print("[red]Code expired. Re-run to request a new one.[/]")
        raise SystemExit(1)


async def login(client: TelegramClient) -> None:
    await client.connect()
    if await client.is_user_authorized():
        return
    method = await questionary.select(
        "Log in with:",
        choices=[
            questionary.Choice("Phone + code (code shows up INSIDE Telegram)", "phone"),
            questionary.Choice("QR code (scan from your phone)", "qr"),
        ],
    ).unsafe_ask_async()
    if method == "qr":
        await login_qr(client)
    else:
        await login_phone(client)
    console.print("[green]Logged in.[/]\n")


# ─── removal logic ──────────────────────────────────────────────────────────


async def fetch_dialogs(client: TelegramClient) -> list:
    out = []
    async for d in client.iter_dialogs():
        out.append(d)
    out.sort(key=lambda d: d.date or datetime.min.replace(tzinfo=timezone.utc))
    return out


async def remove_dialog(client: TelegramClient, d, revoke_dms: bool) -> None:
    """Channels: leave (opt-out) first, then clean from chat list.
    DMs: optionally revoke on the other side.
    Basic groups: single delete_dialog call.
    """
    entity = d.entity
    if isinstance(entity, User):
        # Don't revoke for bots — meaningless and may error.
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
            # ChannelPrivate / ChannelInvalid / ChatAdminRequired etc.
            # Surface as a non-fatal: leave may already be effective server-side.
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


# ─── Textual TUI ────────────────────────────────────────────────────────────


class CleanerApp(App):
    """Pick which Telegram dialogs to remove."""

    TITLE = "Telegram Cleaner"
    SUB_TITLE = "Bulk-remove channels, groups, DMs, bots"

    CSS = """
    Screen { layout: vertical; }
    #toolbar {
        height: 3; padding: 0 1;
        background: $boost; border-bottom: solid $primary;
    }
    #toolbar Select { width: 22; margin-right: 1; }
    #toolbar Input  { width: 1fr; margin-right: 1; }
    #counter { width: 22; content-align: right middle; color: $accent; }
    DataTable { height: 1fr; }
    DataTable > .datatable--header { background: $primary 30%; text-style: bold; }
    DataTable > .datatable--cursor { background: $accent 50%; }
    #buttons { height: 3; padding: 0 1; align: right middle; background: $boost; }
    #buttons Button { margin: 0 1; min-width: 16; }
    """

    BINDINGS = [
        Binding("space",         "toggle_current",   "Toggle"),
        Binding("ctrl+a",        "select_visible",   "Select all"),
        Binding("ctrl+i",        "invert_visible",   "Invert"),
        Binding("ctrl+d",        "deselect_visible", "Clear"),
        Binding("slash",         "focus_search",     "/Search"),
        Binding("ctrl+s",        "submit",           "Submit"),
        Binding("escape",        "cancel",           "Cancel"),
        Binding("question_mark", "help",             "?Help", show=False),
    ]

    def __init__(self, dialogs, initial_filter: str = "all"):
        super().__init__()
        self.dialogs = dialogs
        # Precompute searchable text once — avoids recomputing on every keystroke.
        self._search_text: list[str] = [searchable_text(d) for d in dialogs]
        self.selected_ids: set[int] = set()
        self.kind_filter: str = initial_filter
        self.search: str = ""

    # ── compose ──────────────────────────────────────────────────────────
    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(id="toolbar"):
            yield Select(KIND_FILTERS, id="kind", value=self.kind_filter,
                         allow_blank=False)
            yield Input(placeholder="Search: name, @username, phone, title...",
                        id="search")
            yield Static("0 selected · 0 shown", id="counter")
        yield DataTable(id="table", cursor_type="row", zebra_stripes=True)
        with Horizontal(id="buttons"):
            yield Button("Submit (Ctrl+S)", id="submit", variant="success")
            yield Button("Cancel (Esc)",    id="cancel", variant="error")
        yield Footer()

    def on_mount(self) -> None:
        t = self.query_one(DataTable)
        t.add_column("✓",           key="check",  width=3)
        t.add_column("Type",        key="type",   width=9)
        t.add_column("Mute",        key="mute",   width=5)
        t.add_column("Last Active", key="age",    width=14)
        t.add_column("Unread",      key="unread", width=8)
        t.add_column("Name",        key="name")
        self.refresh_rows()
        t.focus()

    # ── data ─────────────────────────────────────────────────────────────
    def visible_indices(self) -> Iterator[tuple[int, object]]:
        s = self.search
        for i, d in enumerate(self.dialogs):
            if not matches_filter(d, self.kind_filter):
                continue
            if s and s not in self._search_text[i]:
                continue
            yield i, d

    def refresh_rows(self) -> None:
        t = self.query_one(DataTable)
        t.clear()
        n = 0
        for i, d in self.visible_indices():
            n += 1
            checked = i in self.selected_ids
            k = kind_of(d.entity)
            t.add_row(
                "[bold green]✓[/]" if checked else "",
                f"[{KIND_STYLE.get(k, 'white')}]{k:<7}[/]",
                "[red]✱[/]" if d.dialog.notify_settings.mute_until else "",
                f"{days_since(d.date):>4}d ago" if d.date else "?",
                f"[yellow]{d.unread_count}[/]" if d.unread_count else "",
                safe_name(d),
                key=f"d{i}",
            )
        self.update_counter(n)

    def update_counter(self, n_visible: Optional[int] = None) -> None:
        if n_visible is None:
            n_visible = sum(1 for _ in self.visible_indices())
        c = self.query_one("#counter", Static)
        c.update(f"[bold]{len(self.selected_ids)}[/] selected · {n_visible} shown")

    # ── toggling ─────────────────────────────────────────────────────────
    def _toggle(self, idx: int) -> None:
        d = self.dialogs[idx]
        if getattr(d.entity, "is_self", False) and idx not in self.selected_ids:
            self.notify("Saved Messages can't be selected (it's your own storage).",
                        severity="warning", timeout=4)
            return
        t = self.query_one(DataTable)
        key = f"d{idx}"
        if idx in self.selected_ids:
            self.selected_ids.remove(idx)
            cell = ""
        else:
            self.selected_ids.add(idx)
            cell = "[bold green]✓[/]"
        try:
            t.update_cell(key, "check", cell)
        except Exception:
            pass
        self.update_counter()

    def action_toggle_current(self) -> None:
        t = self.query_one(DataTable)
        if not t.has_focus or t.row_count == 0:
            return
        try:
            row_key = t.coordinate_to_cell_key((t.cursor_row, 0)).row_key.value
        except Exception:
            return
        if row_key and row_key.startswith("d"):
            self._toggle(int(row_key[1:]))

    def action_select_visible(self) -> None:
        for i, d in self.visible_indices():
            if getattr(d.entity, "is_self", False):
                continue
            self.selected_ids.add(i)
        self.refresh_rows()

    def action_deselect_visible(self) -> None:
        for i, _ in self.visible_indices():
            self.selected_ids.discard(i)
        self.refresh_rows()

    def action_invert_visible(self) -> None:
        for i, d in self.visible_indices():
            if getattr(d.entity, "is_self", False):
                continue
            if i in self.selected_ids:
                self.selected_ids.remove(i)
            else:
                self.selected_ids.add(i)
        self.refresh_rows()

    def action_focus_search(self) -> None:
        self.query_one("#search", Input).focus()

    def action_submit(self) -> None:
        if not self.selected_ids:
            self.notify(
                "Nothing selected. Tick rows with space, or press Esc to cancel.",
                severity="warning", timeout=4,
            )
            return
        self.exit([self.dialogs[i] for i in self.selected_ids])

    def action_cancel(self) -> None:
        self.exit(None)

    def action_help(self) -> None:
        self.notify(
            "space toggle  •  ctrl+a select all visible  •  ctrl+i invert  •  "
            "ctrl+d clear  •  / search  •  ctrl+s submit  •  esc cancel",
            timeout=6,
        )

    # ── widget events ────────────────────────────────────────────────────
    def on_data_table_row_selected(self, event) -> None:
        # Enter on a row also toggles
        key = event.row_key.value
        if key and key.startswith("d"):
            self._toggle(int(key[1:]))

    def on_input_changed(self, event) -> None:
        if event.input.id == "search":
            self.search = event.value.strip().lower()
            self.refresh_rows()

    def on_input_submitted(self, event) -> None:
        if event.input.id == "search":
            self.query_one(DataTable).focus()

    def on_select_changed(self, event) -> None:
        if event.select.id == "kind":
            self.kind_filter = event.value
            self.refresh_rows()
            self.query_one(DataTable).focus()

    def on_button_pressed(self, event) -> None:
        if event.button.id == "submit":
            self.action_submit()
        elif event.button.id == "cancel":
            self.action_cancel()


# ─── main loop ──────────────────────────────────────────────────────────────


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
        if await questionary.confirm("Run for real now?", default=False).unsafe_ask_async():
            await execute_removals(client, selected, dry_run=False,
                                   revoke_dms=revoke_dms)

    return await ask_continue()


async def ask_continue(prompt: str = "Clean up another batch?") -> bool:
    return await questionary.confirm(prompt, default=False).unsafe_ask_async()


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


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled.[/]")
        sys.exit(130)
