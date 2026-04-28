"""QR code rendering: save PNG, auto-open in default viewer, ASCII fallback."""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path

import qrcode

from .config import QR_PNG_PATH
from .console import console


def open_in_default_viewer(path: Path) -> bool:
    """Best-effort: open `path` in the OS default app.
    Returns True if launched, False if unsupported, opted-out, or errored.
    Set TG_NO_AUTO_OPEN=1 to disable (useful for SSH/headless).
    """
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
