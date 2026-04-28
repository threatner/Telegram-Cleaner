"""Paths, .env loading, and interactive credential setup."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import questionary
from rich.panel import Panel

from .console import console

# Files live next to where the user runs the command, not next to the package.
# Override with TG_DATA_DIR if you want a different location.
DATA_DIR = Path(os.environ.get("TG_DATA_DIR") or Path.cwd()).resolve()
SESSION_PATH = DATA_DIR / "cleaner.session"
ENV_PATH = DATA_DIR / ".env"
QR_PNG_PATH = DATA_DIR / "login_qr.png"


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
