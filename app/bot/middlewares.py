from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.config import get_settings
from app.db import get_sessionmaker


class DbSessionMiddleware(BaseMiddleware):
    """Кладёт в хендлер `session` (AsyncSession) и `settings`."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with get_sessionmaker()() as session:
            data["session"] = session
            data["settings"] = get_settings()
            return await handler(event, data)
