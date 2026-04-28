"""Shared Rich console and the kind/filter constants used across modules."""

from rich.console import Console

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
