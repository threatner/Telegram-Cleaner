"""Login flows: QR scan and phone-number + in-app code."""

from __future__ import annotations

import asyncio

import questionary
from telethon import TelegramClient, errors

from .console import console
from .qr import cleanup_qr_png, render_qr


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
    """Connect and authenticate if needed. Cached sessions skip re-auth."""
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
