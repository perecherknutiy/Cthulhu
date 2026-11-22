from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from aiogram import Bot
from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_sessionmaker
from app.errors import AppError, Forbidden
from app.models import User
from app.services.games import GameService
from app.services.users import parse_ref, upsert_user
from app.telegram_auth import InitDataError, WebAppInit, validate_init_data


async def get_session() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        yield session


def get_bot(request: Request) -> Bot:
    return request.app.state.bot


def get_games(request: Request) -> GameService:
    return request.app.state.games


SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
BotDep = Annotated[Bot, Depends(get_bot)]
GamesDep = Annotated[GameService, Depends(get_games)]


def get_init_data(
    settings: SettingsDep,
    authorization: Annotated[str | None, Header()] = None,
    x_init_data: Annotated[str | None, Header()] = None,
) -> WebAppInit:
    """Мини-апп шлёт `Authorization: tma <Telegram.WebApp.initData>`."""
    raw = None
    if authorization and authorization.lower().startswith("tma "):
        raw = authorization[4:]
    elif x_init_data:
        raw = x_init_data
    if not raw:
        raise AppError("unauthorized", "Нет initData", status_code=401)
    try:
        return validate_init_data(raw, settings.bot_token, settings.initdata_ttl)
    except InitDataError as e:
        raise AppError("unauthorized", f"Неверная initData: {e}", status_code=401) from None


InitDep = Annotated[WebAppInit, Depends(get_init_data)]


async def current_user(init: InitDep, session: SessionDep) -> User:
    user = await session.get(User, init.user.id)
    if user is None:
        user, _ = await upsert_user(session, init.user, referrer_id=parse_ref(init.start_param))
        await session.commit()
    if user.is_banned:
        raise Forbidden("Аккаунт заблокирован")
    return user


UserDep = Annotated[User, Depends(current_user)]
