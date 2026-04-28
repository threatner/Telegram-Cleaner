"""Helpers over Telethon Dialog/entity objects + dialog fetching."""

from __future__ import annotations

from datetime import datetime, timezone

from rich.markup import escape
from telethon import TelegramClient
from telethon.tl.types import Channel, Chat, User


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
    """Best-effort human-readable label.
    Falls back to @username, +phone, 'Saved Messages' for self, then '<no name>'.
    """
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
    """Display name with Rich markup escaped — never trust user-provided strings."""
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


async def fetch_dialogs(client: TelegramClient) -> list:
    """Return all dialogs sorted oldest-first by last activity."""
    out = []
    async for d in client.iter_dialogs():
        out.append(d)
    out.sort(key=lambda d: d.date or datetime.min.replace(tzinfo=timezone.utc))
    return out
