"""Textual TUI: column-headed table of dialogs with filter, search, multi-select."""

from __future__ import annotations

from typing import Iterator, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import (Button, DataTable, Footer, Header, Input, Select,
                             Static)

from .console import KIND_FILTERS, KIND_STYLE
from .dialogs import (days_since, kind_of, matches_filter, safe_name,
                      searchable_text)


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
