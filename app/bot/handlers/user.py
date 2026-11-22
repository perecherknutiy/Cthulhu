from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.services import payments
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
        InlineKeyboardButton(text="🎰 Играть", web_app=WebAppInfo(url=settings.webapp_url)),
    ]])


@router.message(CommandStart())
async def start(message: Message, command: CommandObject, session: AsyncSession, settings: Settings):
    user, created = await upsert_user(session, tg_user(message), referrer_id=parse_ref(command.args))
    await session.commit()
    hello = "Добро пожаловать" if created else "С возвращением"
    await message.answer(
        f"🐙 <b>{hello}, {message.from_user.first_name}!</b>\n\n"
        f"Баланс: <b>{user.balance} ⭐</b>\n\n"
        "Открывайте казино кнопкой ниже. Пополнение — звёздами Telegram.\n"
        "/balance — баланс • /deposit 100 — пополнить • /paysupport — помощь по платежам",
        reply_markup=play_keyboard(settings),
    )


@router.message(Command("balance"))
async def balance(message: Message, session: AsyncSession):
    user, _ = await upsert_user(session, tg_user(message))
    await session.commit()
    await message.answer(f"Баланс: <b>{user.balance} ⭐</b>")


@router.message(Command("deposit"))
async def deposit(message: Message, command: CommandObject, session: AsyncSession, settings: Settings):
    await upsert_user(session, tg_user(message))
    await session.commit()
    if not command.args or not command.args.strip().isdigit():
        presets = ", ".join(map(str, settings.deposit_presets))
        await message.answer(f"Укажите сумму: <code>/deposit 100</code>\nПопулярные: {presets}")
        return
    await payments.send_invoice_message(session, message.bot, settings, message.chat.id, int(command.args))


@router.message(Command("paysupport"))
async def paysupport(message: Message):
    # Обязательная команда для ботов, принимающих платежи (Bot Developer Terms)
    await message.answer(
        "🛟 <b>Поддержка по платежам</b>\n\n"
        "Опишите проблему одним сообщением: дату, сумму и что пошло не так. "
        "Мы ответим в течение 24 часов.\n\n"
        "Важно: поддержка Telegram не рассматривает вопросы по покупкам в этом боте."
    )


@router.message(Command("terms"))
async def terms(message: Message):
    await message.answer(
        "📜 <b>Условия</b>\n\n"
        "• Только для совершеннолетних.\n"
        "• Все игры provably fair — исход можно проверить в разделе «Честность».\n"
        "• Звёзды на балансе — игровые единицы; вывод по правилам раздела «Вывод».\n"
        "<i>Замените этот текст на свои условия.</i>"
    )
