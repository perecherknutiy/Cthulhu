"""Уведомления из бизнес-логики в Telegram (админам и пользователям)."""
from __future__ import annotations

import html
import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.config import Settings
from app.models import User, Withdrawal

log = logging.getLogger(__name__)


def user_label(user: User) -> str:
    name = html.escape(user.first_name or "")
    uname = f" @{html.escape(user.username)}" if user.username else ""
    return f'<a href="tg://user?id={user.id}">{name or user.id}</a>{uname} (<code>{user.id}</code>)'


def withdrawal_keyboard(w: Withdrawal) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Отправить подарками" if w.method == "gifts" else "✅ Я выплатил вручную",
                             callback_data=f"wd:ok:{w.id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"wd:no:{w.id}"),
    ]])


def withdrawal_text(w: Withdrawal, user: User) -> str:
    return (
        f"💸 <b>Заявка на вывод #{w.id}</b>\n"
        f"Игрок: {user_label(user)}\n"
        f"Сумма: <b>{w.amount} ⭐</b>  •  способ: {w.method}\n"
        f"Депозиты: {user.total_deposited} ⭐  •  ставки: {user.total_wagered} ⭐  •  выигрыши: {user.total_won} ⭐\n"
        f"Статус: {w.status.value}"
    )


async def notify_admins(bot: Bot, settings: Settings, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(admin_id, text, reply_markup=markup)
        except Exception:  # noqa: BLE001
            log.warning("Не удалось уведомить админа %s", admin_id, exc_info=True)


async def notify_user(bot: Bot, user_id: int, text: str) -> None:
    try:
        await bot.send_message(user_id, text)
    except Exception:  # noqa: BLE001
        log.info("Не удалось написать пользователю %s", user_id)
