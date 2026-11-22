from __future__ import annotations

import logging
from functools import lru_cache

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import ExceptionTypeFilter
from aiogram.types import BotCommand, BotCommandScopeChat, ErrorEvent, MenuButtonWebApp, WebAppInfo

from app.bot.handlers import admin, payments, user
from app.bot.middlewares import DbSessionMiddleware
from app.config import Settings
from app.errors import AppError

log = logging.getLogger(__name__)

USER_COMMANDS = [
    BotCommand(command="start", description="Открыть казино"),
    BotCommand(command="balance", description="Баланс"),
    BotCommand(command="deposit", description="Пополнить звёздами"),
    BotCommand(command="paysupport", description="Помощь по платежам"),
    BotCommand(command="terms", description="Условия"),
]
ADMIN_COMMANDS = USER_COMMANDS + [
    BotCommand(command="admin", description="Админка"),
    BotCommand(command="stats", description="Статистика"),
    BotCommand(command="withdrawals", description="Заявки на вывод"),
]

errors_router = Router(name="errors")


@errors_router.errors(ExceptionTypeFilter(AppError))
async def on_app_error(event: ErrorEvent):
    exc: AppError = event.exception  # type: ignore[assignment]
    upd = event.update
    if upd.message:
        await upd.message.answer(f"⚠️ {exc.message}")
    elif upd.callback_query:
        await upd.callback_query.answer(exc.message, show_alert=True)
    return True


def create_bot(settings: Settings) -> Bot:
    return Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


@lru_cache
def create_dispatcher() -> Dispatcher:
    # роутеры модульные и подключаются к диспетчеру один раз — поэтому диспетчер синглтон
    dp = Dispatcher()
    dp.update.outer_middleware(DbSessionMiddleware())
    dp.include_routers(errors_router, payments.router, admin.router, user.router)
    return dp


async def configure_bot(bot: Bot, settings: Settings) -> None:
    """Команды и кнопка меню. Ошибки не фатальны — бот продолжит работать."""
    try:
        await bot.set_my_commands(USER_COMMANDS)
        for admin_id in settings.admin_ids:
            await bot.set_my_commands(ADMIN_COMMANDS, scope=BotCommandScopeChat(chat_id=admin_id))
        if settings.webapp_url.startswith("https://"):
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(text="🎰 Играть", web_app=WebAppInfo(url=settings.webapp_url))
            )
    except Exception:  # noqa: BLE001
        log.warning("Не удалось настроить команды/меню бота", exc_info=True)
