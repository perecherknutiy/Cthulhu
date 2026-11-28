from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.money import usdt
from app.services.deposits import deposit_info
from app.services.users import TgUser, parse_ref, upsert_user

router = Router(name="user")
router.message.filter(F.chat.type == "private")


def tg_user(message: Message) -> TgUser:
    u = message.from_user
    return TgUser(id=u.id, username=u.username, first_name=u.first_name, language_code=u.language_code)


def play_keyboard(settings: Settings) -> InlineKeyboardMarkup | None:
    if not settings.webapp_url.startswith("https://"):
        return None  # Telegram принимает только HTTPS
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💎 Открыть ARA Casino", web_app=WebAppInfo(url=settings.webapp_url)),
    ]])


@router.message(CommandStart())
async def start(message: Message, command: CommandObject, session: AsyncSession, settings: Settings):
    user, created = await upsert_user(session, tg_user(message), referrer_id=parse_ref(command.args))
    await session.commit()
    hello = "Добро пожаловать" if created else "С возвращением"
    await message.answer(
        f"💎 <b>{hello} в ARA Casino, {html.escape(user.nickname or message.from_user.first_name or '')}!</b>\n\n"
        f"Баланс: <b>{usdt(user.balance)}</b>\n\n"
        "Открывайте казино кнопкой ниже: слоты, рулетка, Crash, Mines и ещё пять игр. "
        "Валюта — USDT, пополнение и вывод в сети TON.\n"
        "/balance — баланс • /deposit — как пополнить • /support — помощь",
        reply_markup=play_keyboard(settings),
    )


@router.message(Command("balance"))
async def balance(message: Message, session: AsyncSession):
    user, _ = await upsert_user(session, tg_user(message))
    await session.commit()
    await message.answer(f"Баланс: <b>{usdt(user.balance)}</b>")


@router.message(Command("deposit"))
async def deposit(message: Message, session: AsyncSession, settings: Settings):
    user, _ = await upsert_user(session, tg_user(message))
    await session.commit()
    info = deposit_info(settings, user)
    if not info["enabled"]:
        await message.answer("Пополнение временно недоступно.")
        return
    await message.answer(
        "💵 <b>Пополнение USDT (сеть TON)</b>\n\n"
        f"1. Переведите USDT на адрес:\n<code>{info['address']}</code>\n\n"
        f"2. В комментарии к переводу укажите ваш ID: <code>{info['memo']}</code>\n"
        "Без комментария мы не поймём, чей это перевод, — зачисление задержится.\n\n"
        "Деньги появятся на балансе примерно через минуту после подтверждения в сети. "
        "Отправляйте только USDT в сети TON: другие токены и сети не зачисляются.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Открыть в Tonkeeper", url=info["links"]["tonkeeper"]),
        ]]),
    )


@router.message(Command("support", "paysupport"))
async def support(message: Message):
    await message.answer(
        "🛟 <b>Поддержка</b>\n\n"
        "Опишите проблему одним сообщением: дату, сумму, хэш перевода (если речь о пополнении или выводе) "
        "и что пошло не так. Мы ответим в течение 24 часов."
    )


@router.message(Command("terms"))
async def terms(message: Message):
    await message.answer(
        "📜 <b>Условия ARA Casino</b>\n\n"
        "• Только для совершеннолетних.\n"
        "• Все игры provably fair — исход можно проверить в разделе «Честная игра».\n"
        "• Баланс — в USDT; пополнение и вывод — USDT в сети TON, по правилам раздела «Кошелёк».\n"
        "<i>Замените этот текст на свои условия.</i>"
    )
