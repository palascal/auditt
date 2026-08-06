"""Telegram — project config tokens + scrapekit sender."""

from __future__ import annotations

import _bootstrap

_bootstrap.ensure_scrapekit()

from scrapekit.telegram import send_telegram_message as _send

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def send_telegram_message(message: str) -> None:
    _send(message, token=TELEGRAM_BOT_TOKEN, chat_id=TELEGRAM_CHAT_ID)
