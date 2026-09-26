"""Telegram — disabled for AudiTT (no AutoScout / listing alerts)."""

from __future__ import annotations


def send_telegram_message(message: str) -> None:
    # Intentionally no-op: AudiTT must not send Telegram notifications.
    return
