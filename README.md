# Telegram Cleaner

> Bulk leave channels, leave groups, and delete DMs/bots from Telegram — through a terminal UI with column headers, live search, and keyboard shortcuts.

[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Built with Telethon](https://img.shields.io/badge/built%20with-Telethon-26A5E4.svg)](https://github.com/LonamiWebs/Telethon)

For the day you realize you're sitting in 200 channels you stopped reading three years ago.

```text
┌── Telegram Cleaner — Bulk-remove channels, groups, DMs ─────────────┐
│ [Channels ▾]  [Search: crypto                ]   12 selected · 38 sh│
├──────────────────────────────────────────────────────────────────────┤
│ ✓  │ Type    │ Mute │ Last Active   │ Unread │ Name                 │
├──────────────────────────────────────────────────────────────────────┤
│ ✓  │ CHANNEL │      │   145d ago    │   12   │ Crypto News          │
│    │ CHANNEL │  ✱   │     2d ago    │        │ Crypto Daily         │
│ ✓  │ CHANNEL │      │    87d ago    │   3    │ Old Crypto Group     │
│ ...                                                                  │
├──────────────────────────────────────────────────────────────────────┤
│        [ Submit (Ctrl+S) ]   [ Cancel (Esc) ]                       │
├──────────────────────────────────────────────────────────────────────┤
│ space Toggle  ctrl+a Select all  ctrl+i Invert  /Search  …          │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Quick start

Already have a Telegram account, Python 3.9+, and your `api_id` / `api_hash` from [my.telegram.org](https://my.telegram.org)?

```bash
git clone https://github.com/threatner/Telegram-Cleaner.git
cd Telegram-Cleaner
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/tgcleaner
```

First run prompts for credentials (or set `TG_API_ID` / `TG_API_HASH` env vars). After login, you're in the TUI.

New to Telegram or `my.telegram.org`? See the [full guide](#full-guide) below.

---

## Features

- **Real TUI** — column headers, live search, keyboard shortcuts. Not a scrolling checkbox.
- **Filters** — channels / groups / DMs / bots / muted / stale (90d+) / all
- **Search** across name, `@username`, phone number, and channel title
- **Bulk select** — `Ctrl+A` (all visible), `Ctrl+I` (invert), `Ctrl+D` (clear)
- **Dry-run by default** — review what would be deleted before touching the API
- **Two-step channel removal** — leave (opt-out) first, then clean from list. Even if step 2 fails, messages have already stopped
- **Loop mode** — clean one category, then another, without restarting
- **Resilient** — auto-retry on `FloodWait` and connection drops
- **QR or phone login** — no SMS dependency
- **Free** — uses Telegram's official MTProto API; no third-party services
- **Saved Messages protected** from accidental deletion

---

## Full guide

### Prerequisites

| What | Why |
|---|---|
| **Python 3.9+** | The tool is written in Python. Check with `python3 --version` |
| **Telegram account** | The tool runs *as you* via official APIs |
| **Phone with Telegram app** | To approve login (the code arrives in-app, not SMS) |

You **don't** need: a paid plan, a bot token, Premium, or any third-party SaaS.

### Step 1 — Get a Telegram account

Skip this if you already have one. Otherwise: install [Telegram for iOS](https://apps.apple.com/app/telegram-messenger/id686449807) or [Android](https://play.google.com/store/apps/details?id=org.telegram.messenger), open it, enter your phone number with country code, and verify with the SMS code.

### Step 2 — Get API credentials from `my.telegram.org`

This is a free, one-time step. You're registering an "application" so Telegram gives you API keys.

1. Open [https://my.telegram.org](https://my.telegram.org)
2. Log in with your phone — the verification code arrives **inside the Telegram app** (chat from "Telegram", blue checkmark), not via SMS
3. Click **API development tools**
4. Fill the form:

| Field | Value |
|---|---|
| App title | `tg-cleaner` (any label) |
| Short name | `tgcleaner` (5–32 chars, alphanumeric) |
| URL | leave blank |
| Platform | **Desktop** |
| Description | leave blank or "personal cleanup" |

5. Click **Create application** → copy the **api_id** (number) and **api_hash** (32-char string)

> The `api_hash` is shown only on this page. Treat it like a password. You can revisit the page later to view it again, but **never share it publicly**.

### Step 3 — Install

Recommended (gives you a `tgcleaner` command):

```bash
git clone https://github.com/threatner/Telegram-Cleaner.git
cd Telegram-Cleaner
python3 -m venv .venv
.venv/bin/pip install -e .
```

On Windows: `python -m venv .venv && .venv\Scripts\pip install -e .`

<details>
<summary>Alternative: install dependencies only (no console command)</summary>

```bash
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m tgcleaner   # or python cleaner.py for the legacy entry
```
</details>

### Step 4 — First run + login

```bash
.venv/bin/tgcleaner
```

The first run prompts for `api_id` and `api_hash`. By default it offers to save them to a local `.env` file (mode `0600`, gitignored) so you don't re-enter them. To skip the prompt, export them as env vars:

```bash
export TG_API_ID=1234567
export TG_API_HASH=abc123def456abc123def456abc12345
```

Then pick a login method:

<details>
<summary><b>Phone + code (easiest)</b></summary>

1. Enter your phone number with country code (e.g. `+919876543210`)
2. **The code arrives INSIDE Telegram itself** — open your Telegram app and look for a chat from "Telegram" (blue checkmark) at the top of your chat list
3. Type the 5-digit code into the terminal

> The code is **not sent via SMS** when you have any other Telegram session active (your phone counts). People miss this and stare at their SMS inbox forever.

If you have a 2FA password set, it'll prompt for that next.
</details>

<details>
<summary><b>QR code (no typing)</b></summary>

1. The tool saves a QR as `login_qr.png` and tries to **auto-open it** in your default image viewer
2. It also prints an ASCII QR in the terminal as a fallback
3. On your phone: Telegram → **Settings → Devices → Link Desktop Device** → scan the QR
4. After login, the QR file is auto-deleted

Set `TG_NO_AUTO_OPEN=1` to disable auto-open (useful over SSH).
</details>

After successful login the session is cached in `cleaner.session`. **Future runs skip authentication entirely** unless you delete that file or revoke the session in Telegram → Settings → Devices.

### Step 5 — Use the TUI

After login, the tool fetches your full dialog list (30–60 seconds for large accounts), shows a stats panel, and asks which category to start with. Then the selection TUI opens.

#### Columns

| Column | What it shows |
|---|---|
| **✓** | Whether this row is selected for removal |
| **Type** | `CHANNEL` / `GROUP` / `DM` / `BOT` (color-coded) |
| **Mute** | `✱` if muted |
| **Last Active** | Days since the last message |
| **Unread** | Unread message count |
| **Name** | Display name (falls back to `@username`, then `+phone`, then `<no name>`) |

#### Keyboard shortcuts

| Key | Action |
|---|---|
| `↑` `↓` | Move cursor |
| `Space` / `Enter` | Toggle current row |
| `/` | Focus the search box |
| (letters) | Live-filter rows by name / `@username` / phone / title |
| `Tab` | Cycle focus: filter → search → table → buttons |
| `Ctrl+A` | Select all visible rows |
| `Ctrl+I` | Invert selection (visible) |
| `Ctrl+D` | Deselect all visible |
| `Ctrl+S` | Submit selection |
| `Esc` | Cancel without changes |
| `?` | Show shortcut cheat sheet |

#### Workflow examples

**Delete every "crypto" channel:**
1. Pick **Channels** at the prompt
2. Press `/` and type `crypto`
3. `Ctrl+A` to select all matches
4. `Ctrl+S` → confirm dry-run → say Yes to "Run for real now?"

**Cherry-pick a few DMs:**
1. Pick **DMs** at the prompt
2. ↑/↓ + space on each one
3. `Ctrl+S`

**Wipe everything you haven't touched in 3 months:**
1. Pick **Stale (90d+)** at the prompt
2. `Ctrl+A` → `Ctrl+S`

After submission: confirmation table → DM-revoke prompt (only for DMs) → dry-run prompt → "Run for real now?" → progress bar → results panel → "Clean up another batch?"

---

## Reference

### What "delete" means per type

- **Channel / Supergroup**: leaves you as a participant first (you stop receiving messages immediately), then removes the dialog from your chat list
- **Group (legacy)**: leaves and removes the dialog
- **DM**: deletes the chat from your side. Optionally `revoke=True` deletes it on the other person's side too (asked per-batch, defaults off)
- **Bot**: same as DM. `revoke` is forced off — meaningless for bots

You can re-join channels/groups later if you have an invite link. There's no undo for revoked DM history.

### Configuration

| Env var | Effect |
|---|---|
| `TG_API_ID` | Your numeric api_id (skip the prompt) |
| `TG_API_HASH` | Your api_hash (skip the prompt) |
| `TG_NO_AUTO_OPEN` | If set, don't auto-open the QR PNG (useful for SSH/headless) |
| `TG_DATA_DIR` | Where to put `cleaner.session`, `.env`, `login_qr.png` (defaults to current directory) |

### Files created

| File | Purpose | Gitignored? |
|---|---|---|
| `cleaner.session` | Cached login (Telethon) | Yes |
| `cleaner.session-journal` | Telethon temp file | Yes |
| `.env` | Saved api_id/api_hash (if you opted in) | Yes |
| `login_qr.png` | QR image during login (auto-deleted) | Yes |

### Safety

- **Dry-run by default.** You opt in to the destructive run explicitly
- Sequential, paced (1s between ops) and `FloodWait`-aware
- Auto-retry with exponential backoff on connection drops
- Saved Messages cannot be selected
- Session file treated as a credential — `.gitignore`d
- `.env` is `.gitignore`d and `chmod 0600` on POSIX

---

## Troubleshooting

<details>
<summary><b>OTP code never arrives via SMS</b></summary>

Expected when you have any other Telegram session active. The code arrives **inside the Telegram app** as a message from "Telegram" (blue checkmark). SMS is only the fallback when you have zero other devices logged in.
</details>

<details>
<summary><b>"Server closed the connection: Connection reset by peer"</b></summary>

Transient. Auto-retries with backoff (2s, 4s, 8s, 16s). If it eventually gives up, just re-run — already-removed items won't reappear.
</details>

<details>
<summary><b>"FloodWait of N seconds"</b></summary>

Telegram is throttling you. The script sleeps and continues automatically. Don't fight it.
</details>

<details>
<summary><b>QR doesn't scan from terminal</b></summary>

The tool saves a higher-resolution PNG to `login_qr.png` and auto-opens it. If auto-open didn't work, run `open login_qr.png` (macOS), `xdg-open login_qr.png` (Linux), or `start login_qr.png` (Windows).
</details>

<details>
<summary><b>"Wrong code" / "Code expired"</b></summary>

Codes expire in a few minutes. Telegram sometimes sends two — use the latest. Re-run to request a new one.
</details>

<details>
<summary><b>"Phone number isn't valid"</b></summary>

Include country code with `+`, no spaces: `+919876543210`, `+14155552671`.
</details>

<details>
<summary><b>"Session expired" / "AuthKeyUnregisteredError"</b></summary>

Delete `cleaner.session` and re-run. Happens if you logged out from another device's Settings → Devices.
</details>

<details>
<summary><b>TUI looks broken</b></summary>

Use a terminal at least 100 columns wide with 256-color support (iTerm2, Terminal.app, Alacritty, Windows Terminal — all good).
</details>

---

## Uninstalling and cleaning up

When you're done with the tool:

```bash
# 1. Delete local session and credential files
cd /path/to/Telegram-Cleaner
rm -f cleaner.session cleaner.session-journal .env login_qr.png

# 2. Unset env vars in current shell (closing the terminal also clears them)
unset TG_API_ID TG_API_HASH

# 3. Remove the package install
.venv/bin/pip uninstall tgcleaner -y

# 4. (Optional) delete the whole project folder
cd .. && rm -rf Telegram-Cleaner
```

**Important — revoke the session on Telegram's side too:**

1. Open Telegram on your phone
2. **Settings → Devices**
3. Find the session created by this tool (often labeled "Telethon")
4. Tap it → **Terminate Session**

Once revoked, even leaked credentials can't be used to access your account without going through phone+code login again.

> **Note:** Telegram doesn't let you delete the application itself from `my.telegram.org` — there's no delete button. It just sits there. With the session revoked locally and remotely, it's harmless.

---

## Project layout

```
Telegram-Cleaner/
├── cleaner.py          # legacy 4-line entry point (still works)
├── pyproject.toml      # makes it pip-installable as `tgcleaner`
├── requirements.txt    # for non-package install
├── README.md / LICENSE
└── tgcleaner/          # the package
    ├── __init__.py
    ├── __main__.py     # python -m tgcleaner
    ├── cli.py          # main flow + loop
    ├── config.py       # paths, env, credentials
    ├── console.py      # shared Rich console + style/filter constants
    ├── auth.py         # login_qr / login_phone / login
    ├── qr.py           # QR rendering + OS auto-open
    ├── dialogs.py      # entity helpers + fetch
    ├── panels.py       # Rich panels (stats / summary / labels)
    ├── removal.py      # remove_dialog / retry / execute_removals
    └── tui.py          # CleanerApp (Textual)
```

---

## Limitations

- One account per session file. To clean a second account, delete `cleaner.session` and re-login (or copy the folder elsewhere)
- No undo. Once a leave/delete is committed server-side, it's done. Use the dry-run
- Doesn't archive or mute in bulk — only removes
- Doesn't keep a log of deletions; redirect output if you need one: `tgcleaner | tee cleanup.log`

---

## Contributing

PRs welcome.

```bash
# Quick syntax check across the package
.venv/bin/python -c "import ast, pathlib; \
  [ast.parse(p.read_text()) for p in pathlib.Path('tgcleaner').glob('*.py')]; \
  print('syntax OK')"
```

Areas where help is wanted:
- Mass-mute / mass-archive features (instead of just deleting)
- Real test suite
- Publishing to PyPI

---

## License

[MIT](LICENSE).

This is unofficial software not affiliated with Telegram. Use it on your own account, at your own risk, and within Telegram's [Terms of Service](https://telegram.org/tos).
