"""Уведомления из бизнес-логики в Telegram (админам и пользователям)."""
from __future__ import annotations

import html
import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.config import Settings, get_settings
from app.models import User, Withdrawal
from app.money import usdt
from app.ton.address import jetton_transfer_link

log = logging.getLogger(__name__)


def user_label(user: User) -> str:
    name = html.escape(user.nickname or user.first_name or "")
    uname = f" @{html.escape(user.username)}" if user.username else ""
    return (f'<a href="tg://user?id={user.id}">{name or user.id}</a>{uname} '
            f'(ID <code>{user.public_id}</code>, TG <code>{user.id}</code>)')


def withdrawal_keyboard(w: Withdrawal) -> InlineKeyboardMarkup:
    from app.services.withdrawals import payout_comment

    rows = []
    if w.address:  # перевод в Tonkeeper с уже подставленными адресом, суммой и комментарием
        link = jetton_transfer_link(w.address, get_settings().ton_usdt_master, w.amount - w.fee, payout_comment(w),
                                    prefix="https://app.tonkeeper.com/")
        rows.append([InlineKeyboardButton(text="📤 Открыть перевод в Tonkeeper", url=link)])
    rows.append([InlineKeyboardButton(text="✅ Отправил", callback_data=f"wd:ok:{w.id}"),
                 InlineKeyboardButton(text="❌ Отклонить", callback_data=f"wd:no:{w.id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def withdrawal_text(w: Withdrawal, user: User) -> str:
    return (
        f"💸 <b>Заявка на вывод #{w.id}</b>\n"
        f"Игрок: {user_label(user)}\n"
        f"К отправке: <b>{usdt(w.amount - w.fee)}</b> (USDT, сеть TON)"
        + (f"  •  комиссия {usdt(w.fee)}" if w.fee else "") + "\n"
        f"Адрес: <code>{html.escape(w.address or '—')}</code>\n"
        f"Депозиты: {usdt(user.total_deposited)}  •  ставки: {usdt(user.total_wagered)}  •  "
        f"выигрыши: {usdt(user.total_won)}\n"
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
