# Telegram Cleaner

A terminal tool to **bulk leave Telegram channels and groups, and delete DMs and bots** from your account — through a real TUI with column headers, live search, and keyboard shortcuts.

For the day you realize you're sitting in 200 channels you stopped reading three years ago.

## Table of contents

- [Features](#features)
- [How it works (in plain English)](#how-it-works-in-plain-english)
- [Prerequisites](#prerequisites)
- [Step 1 — Make a Telegram account](#step-1--make-a-telegram-account-skip-if-you-have-one)
- [Step 2 — Create a Telegram API app](#step-2--create-a-telegram-api-app)
- [Step 3 — Install the tool](#step-3--install-the-tool)
- [Step 4 — Log in](#step-4--log-in)
- [Step 5 — Use the TUI](#step-5--use-the-tui)
- [What "delete" means for each type](#what-delete-means-for-each-type)
- [Safety](#safety)
- [Troubleshooting](#troubleshooting)
- [Configuration](#configuration)
- [Limitations](#limitations)
- [Contributing](#contributing)
- [License](#license)

## Features

- **Real TUI** with column headers, live search, and keyboard shortcuts (no scrolling-checkbox hell)
- **Filter by category**: channels / groups / DMs / bots / muted / stale (90d+) / all
- **Live search** across name, `@username`, phone number, and channel title
- **Bulk shortcuts**: select all visible (Ctrl+A), invert (Ctrl+I), clear (Ctrl+D)
- **Dry-run by default** — review what would be deleted before touching the API
- **Two-step channel removal**: leave (opt-out) first, then clean from the chat list — even if step 2 fails, you've stopped receiving messages
- **Loop mode** — clean a category, then continue with another batch without restarting
- **Resilient**: auto-retries on `FloodWait` and connection drops with exponential backoff
- **QR or phone login** — no SMS dependency
- **Free**: uses Telegram's official MTProto API; no third-party services
- **Saved Messages protected** from accidental deletion

## How it works (in plain English)

Telegram exposes a free official API called **MTProto** — the same one the official Telegram apps use. Anyone can get free credentials for it on `my.telegram.org` and write a program that acts as their own user.

This tool is one such program. It logs in as you, asks Telegram for your full chat list, displays it as an interactive table, lets you tick off what you want gone, and then tells Telegram to remove those chats. Nothing leaves your machine except the API calls to Telegram.

There's no third-party server, no account scraping, no bot, no money. Your credentials sit in a local file. Your login session is cached so you only authenticate once.

## Prerequisites

You need:

| What | Why | How |
|---|---|---|
| **A computer with a terminal** | macOS, Linux, or Windows | Just have one |
| **Python 3.9 or newer** | The tool is written in Python | `python3 --version` to check; install from [python.org](https://www.python.org/downloads/) if missing |
| **A Telegram account** | The tool runs *as you* | See Step 1 below |
| **A phone with the Telegram app** | To approve login (you'll get the login code there) | Install [Telegram](https://telegram.org/) on your phone |
| **Internet connection** | To talk to Telegram's servers | Standard |

You don't need:
- A paid plan
- A bot token
- A premium subscription
- Any third-party SaaS

## Step 1 — Make a Telegram account (skip if you have one)

1. Install the Telegram app on your phone — [iOS](https://apps.apple.com/app/telegram-messenger/id686449807) or [Android](https://play.google.com/store/apps/details?id=org.telegram.messenger)
2. Open it. Tap **Start Messaging**
3. Enter your phone number with country code (e.g. `+91 9876543210`)
4. Telegram sends a 5-digit verification code via SMS — enter it
5. Set your first name (last name optional). Done — you have an account

Keep this app installed and logged in on your phone. The cleaner uses it as your second-factor.

## Step 2 — Create a Telegram API app

This is a one-time, free step. You're registering "an application" with Telegram so it gives you keys to use its API.

1. Open https://my.telegram.org in a browser
2. Log in with your phone number (Telegram sends a code to your **phone's Telegram app**, not via SMS — check the chat from the official "Telegram" account, blue checkmark)
3. Once logged in, click **API development tools**
4. Fill in the form:

   | Field | What to put |
   |---|---|
   | **App title** | `tg-cleaner` (anything — just a label for you) |
   | **Short name** | `tgcleaner` (5–32 chars, letters/numbers only) |
   | **URL** | leave blank |
   | **Platform** | **Desktop** |
   | **Description** | leave blank or "personal cleanup" |

5. Click **Create application**
6. The next page shows two values:
   - **App api_id** — a number like `1234567`
   - **App api_hash** — a 32-character string like `abc123def456abc123def456abc12345`
7. Keep this tab open or copy both values somewhere safe. The `api_hash` is shown only on this page (you can come back to view it again, but **never share it publicly** — treat it like a password)

Each Telegram account is allowed one app. That's fine — you can reuse it for any future Telegram scripts.

## Step 3 — Install the tool

```bash
git clone https://github.com/threatner/Telegram-Cleaner.git
cd Telegram-Cleaner
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

That installs the dependencies in a project-local virtual environment so they don't clutter your system Python.

On Windows, use `.venv\Scripts\python` and `.venv\Scripts\pip` instead.

## Step 4 — Log in

Run the tool:

```bash
.venv/bin/python cleaner.py
```

### First run: enter your API credentials

You'll see a setup panel. It'll ask for the `api_id` and `api_hash` you got from Step 2. By default it offers to save them to a local `.env` file (with permission `0600`, gitignored) so you don't have to re-enter them next time.

If you'd rather not have them on disk, set them as environment variables instead:

```bash
export TG_API_ID=1234567
export TG_API_HASH=abc123def456abc123def456abc12345
.venv/bin/python cleaner.py
```

### Pick a login method

The tool then asks you to choose:

#### Option A — Phone + code (easiest)

1. Enter your phone number with country code (e.g. `+919876543210`)
2. Look on your phone's **Telegram app** — there's a chat at the top from the official "Telegram" account (blue checkmark) with a 5-digit code
3. Type that code into the terminal

> **Important:** the code is **NOT sent via SMS** when you have an active Telegram session elsewhere. It arrives inside Telegram itself. People miss this and stare at their SMS inbox forever. SMS is only the fallback if you have no other devices logged in.

If your account has 2FA password set, it'll prompt for that next.

#### Option B — QR code

1. The tool generates a QR code, **saves it as `login_qr.png` in the project folder, and tries to auto-open it** in your default image viewer (Preview on macOS, your file manager's image viewer on Linux, etc.)
2. It also prints an ASCII version of the QR right in the terminal as a fallback
3. On your phone: open Telegram → **Settings → Devices → Link Desktop Device** → scan the QR (image or terminal — whichever scans cleanly)

If the auto-open fails or you're on a headless box, manually open the file:
```bash
open login_qr.png         # macOS
xdg-open login_qr.png     # Linux
start login_qr.png        # Windows
```

Or set `TG_NO_AUTO_OPEN=1` to disable auto-open (useful over SSH).

After successful login, the QR file is auto-deleted and your session is cached in `cleaner.session`. **Future runs skip authentication entirely** unless you delete that file or revoke the session from Telegram → Settings → Devices.

## Step 5 — Use the TUI

After login, the tool fetches your full dialog list (this can take 30–60 seconds for large accounts — Telegram's pace, not ours), shows a stats panel, and asks which category you want to start with.

Then a full-screen TUI opens:

```
┌── Telegram Cleaner — Bulk-remove channels, groups, DMs ─────────────┐
├──────────────────────────────────────────────────────────────────────┤
│ [Channels ▾]   [Search by name, @username, phone…]   3 sel · 156 sh │
├──────────────────────────────────────────────────────────────────────┤
│ ✓  │ Type    │ Mute │ Last Active   │ Unread │ Name                 │
├──────────────────────────────────────────────────────────────────────┤
│ ✓  │ CHANNEL │      │   145d ago    │   12   │ Crypto News          │
│    │ CHANNEL │  ✱   │     2d ago    │        │ Tech Updates         │
│ ✓  │ CHANNEL │      │    87d ago    │   3    │ Old Project Updates  │
│ ...                                                                  │
├──────────────────────────────────────────────────────────────────────┤
│        [ Submit (Ctrl+S) ]   [ Cancel (Esc) ]                       │
├──────────────────────────────────────────────────────────────────────┤
│ space Toggle ctrl+a Select all ctrl+i Invert ctrl+d Clear / Search …│
└──────────────────────────────────────────────────────────────────────┘
```

### Columns

| Column | Meaning |
|---|---|
| **✓** | Whether this row is selected for removal |
| **Type** | `CHANNEL` / `GROUP` / `DM` / `BOT` (color-coded) |
| **Mute** | `✱` if you've muted notifications for this dialog |
| **Last Active** | Days since the last message in the dialog |
| **Unread** | Number of unread messages |
| **Name** | Display name of the channel/contact/group (falls back to `@username`, then `+phone`, then `<no name>`) |

### Keyboard shortcuts

| Key | Action |
|---|---|
| `↑` `↓` | Move cursor between rows |
| `Space` | Toggle current row selection |
| `Enter` | Toggle current row (alternate) |
| `/` | Jump focus to the search box |
| *(letters in search box)* | Filter rows by name / `@username` / phone / title |
| `Tab` | Cycle focus: filter dropdown → search → table → buttons |
| `Ctrl+A` | Select **all currently visible** rows (after filtering) |
| `Ctrl+I` | Invert selection (visible rows only) |
| `Ctrl+D` | Deselect all visible rows |
| `Ctrl+S` | Submit selection — moves to confirmation step |
| `Esc` | Cancel without changes |
| `?` | Show keybinding cheat sheet |

### Workflow examples

**Delete every "crypto" channel:**
1. In the upfront prompt, pick **Channels**
2. Press `/` and type `crypto`
3. Press `Ctrl+A` to select all matches
4. Press `Ctrl+S` to submit
5. Confirm in the dry-run summary, then say **Yes** to "Run for real now?"

**Cherry-pick a few DMs:**
1. Pick **DMs** at the prompt
2. Use ↑/↓ + space on each one you want gone
3. `Ctrl+S`

**Wipe everything you haven't touched in 3 months:**
1. Pick **Stale (90d+)** at the prompt
2. `Ctrl+A` → `Ctrl+S`

The selection counter at the top-right shows `X selected · Y shown` so you always know what's about to happen.

### After submission

1. **Confirmation table**: shows count by type (CHANNELS/GROUPS/DMs/BOTS) — last chance to bail
2. **DM revoke prompt** (only if DMs are selected): "delete on the other side too?" — defaults to No
3. **Dry-run prompt**: defaults to Yes. The dry-run prints what *would* be deleted without doing it
4. **Confirmation**: "Run for real now?" — defaults to No. Only after you say Yes does anything actually happen
5. **Progress**: spinner + bar + per-item ✓/✗ logs
6. **Results panel**: succeeded/failed counts
7. **"Clean up another batch?"**: lets you go again on a different category without restarting (re-fetches the list — already-removed items won't show)

Press Ctrl+C at any time for a clean exit.

## What "delete" means for each type

- **Channel** (broadcast or supergroup): two-step — leave (opt-out) first, then clean the dialog from your chat list. The leave is what stops messages, so even if step 2 fails you're already off the channel
- **Group** (legacy): leaves the group and removes the dialog
- **DM**: deletes the chat from your side. Optionally `revoke=True` also deletes it on the other person's side (asked per-batch, defaults off)
- **Bot**: same as DM but `revoke` is forced off (it's meaningless for bots)

You can re-join channels/groups later if you have an invite link. There's no undo for revoked DM history on the other side.

## Safety

- **Dry-run by default** on every batch. You explicitly opt in to the destructive run
- **Sequential, paced** removal (1 second between operations) to stay under Telegram's rate limits
- **FloodWait-aware**: if Telegram tells you to slow down, the script sleeps and continues
- **Auto-retry** with exponential backoff on connection drops
- **Saved Messages protected**: cannot be selected (it's your private storage)
- The session file (`cleaner.session`) is treated as a credential — `.gitignore`d
- The `.env` file (api_id/api_hash) is also `.gitignore`d and `chmod 0600` on POSIX

## Troubleshooting

### "OTP code never arrives via SMS"
That's expected if you have any other Telegram session active. **Look inside the Telegram app** — the code arrives as a message from "Telegram" (blue checkmark) at the top of your chat list. SMS is only the fallback when you have zero other devices.

### "Server closed the connection: Connection reset by peer"
Transient. The script auto-retries with backoff (2s, 4s, 8s, 16s). If it still fails, just re-run — your session is cached, no re-login needed. Already-removed items won't appear.

### "FloodWait of N seconds"
Telegram is throttling you because you've been doing too many actions too fast. The script sleeps the requested duration and continues automatically. Don't fight it.

### QR doesn't scan from the terminal
Open `login_qr.png` from the project folder — it's higher resolution. The tool tries to open it for you automatically. If that didn't work, run `open login_qr.png` (macOS), `xdg-open login_qr.png` (Linux), or `start login_qr.png` (Windows).

### "Wrong code" when entering phone code
Check inside Telegram (not SMS), make sure you're entering the latest code (Telegram sometimes sends two), and re-run the script if needed. Codes expire after a few minutes.

### "Phone number isn't valid"
Include the country code with `+`, no spaces. Examples: `+919876543210`, `+14155552671`.

### "Session expired" or "AuthKeyUnregisteredError"
Delete `cleaner.session` and run again — you'll need to re-authenticate. This happens if you logged out from another device's Settings → Devices.

### TUI looks broken
Make a wider terminal window (at least 100 columns recommended). Make sure your terminal supports 256 colors — most modern ones do (iTerm2, Terminal.app, Alacritty, Windows Terminal, etc.).

## Configuration

Environment variables (all optional):

| Variable | Default | Effect |
|---|---|---|
| `TG_API_ID` | (prompted) | Your numeric api_id from my.telegram.org |
| `TG_API_HASH` | (prompted) | Your api_hash from my.telegram.org |
| `TG_NO_AUTO_OPEN` | unset | If set to anything truthy, don't auto-open the QR PNG (useful for SSH/headless) |

Files created in the project folder:

| File | What it is | Gitignored? |
|---|---|---|
| `cleaner.session` | Cached login (Telethon) | Yes |
| `cleaner.session-journal` | Telethon temp file | Yes |
| `.env` | Your api_id/api_hash (if you opted to save) | Yes |
| `login_qr.png` | QR image during login (auto-deleted after) | Yes |

## Limitations

- One account per session file. If you want to clean a second account, delete `cleaner.session` and re-login (or copy this folder elsewhere)
- No undo. Once a leave/delete is committed server-side, it's done. Use the dry-run
- Doesn't archive or mute in bulk — only removes. Open an issue if that's useful
- Doesn't keep a log of what was deleted; redirect output to a file if you need one: `python cleaner.py | tee cleanup.log`

## Contributing

PRs welcome. Keep it a single-file script — that's part of the appeal.

```bash
.venv/bin/python -m py_compile cleaner.py   # quick syntax check
```

Areas where help is wanted:
- Mass-mute / mass-archive features (instead of just deleting)
- Better tests (currently only smoke checks)
- Distributing as `pip install`-able package with a `tgcleaner` console script

## License

MIT — see [LICENSE](LICENSE).

This is unofficial software not affiliated with Telegram. Use it on your own account, at your own risk, and within Telegram's [Terms of Service](https://telegram.org/tos).
