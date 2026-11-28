from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError
from app.models import User

REF_PREFIX = "ref_"

NICK_RE = re.compile(r"^[A-Za-zА-Яа-яЁё0-9_ .-]{3,20}$")
# нельзя выдавать себя за администрацию (тот же список — в webapp/demo-api.js)
RESERVED_PARTS = ("admin", "support", "moder", "official", "админ", "поддерж", "модер", "официал")
RESERVED_EXACT = ("ara", "ара", "aracasino", "араказино", "telegram", "телеграм", "system", "система")


@dataclass
class TgUser:
    id: int
    username: str | None = None
    first_name: str | None = None
    language_code: str | None = None
    photo_url: str | None = None


def parse_ref(start_param: str | None) -> int | None:
    """'ref_104233' -> 104233 (внутренний ID пригласившего; старые ссылки с Telegram ID тоже работают)"""
    if not start_param or not start_param.startswith(REF_PREFIX):
        return None
    tail = start_param[len(REF_PREFIX):]
    return int(tail) if tail.isdigit() else None


async def upsert_user(session: AsyncSession, tg: TgUser, referrer_id: int | None = None) -> tuple[User, bool]:
    """Создать пользователя или обновить его профиль. Возвращает (user, created). Коммит — на вызывающем.

    referrer_id — значение из реф-ссылки: сначала ищем по внутреннему ID, потом по Telegram ID.
    """
    if referrer_id is not None:
        referrer_id = await session.scalar(
            select(User.id).where(or_(User.public_id == referrer_id, User.id == referrer_id))
            .order_by((User.public_id == referrer_id).desc()).limit(1)
        )
    if referrer_id == tg.id:
        referrer_id = None

    photo = tg.photo_url[:512] if tg.photo_url else None
    stmt = (
        insert(User)
        .values(id=tg.id, username=tg.username, first_name=tg.first_name, language_code=tg.language_code,
                photo_url=photo, referrer_id=referrer_id)
        .on_conflict_do_nothing(index_elements=[User.id])
        .returning(User.id)
    )
    created = (await session.execute(stmt)).scalar() is not None
    if not created:
        values = dict(username=tg.username, first_name=tg.first_name, language_code=tg.language_code,
                      last_seen_at=func.now())
        if photo:
            values["photo_url"] = photo
        await session.execute(update(User).where(User.id == tg.id).values(**values))
    user = await session.scalar(select(User).where(User.id == tg.id).execution_options(populate_existing=True))
    assert user is not None
    return user, created


def check_nickname(raw: str) -> str:
    nick = re.sub(r"\s+", " ", str(raw or "")).strip()
    if not NICK_RE.match(nick):
        raise AppError("bad_nickname", "Ник: 3–20 символов — буквы, цифры, пробел, _ . -")
    low = re.sub(r"[\s_.-]", "", nick.lower())
    if any(w in low for w in RESERVED_PARTS) or low in RESERVED_EXACT:
        raise AppError("nickname_reserved", "Такой ник выбрать нельзя")
    return nick


async def set_nickname(session: AsyncSession, user_id: int, raw: str) -> User:
    nick = check_nickname(raw)
    taken = await session.scalar(
        select(User.id).where(func.lower(User.nickname) == nick.lower(), User.id != user_id)
    )
    if taken:
        raise AppError("nickname_taken", "Этот ник уже занят")
    try:
        await session.execute(update(User).where(User.id == user_id).values(nickname=nick))
        await session.commit()
    except IntegrityError:  # гонка двух одинаковых ников — уникальный индекс решит
        await session.rollback()
        raise AppError("nickname_taken", "Этот ник уже занят") from None
    user = await session.get(User, user_id, populate_existing=True)
    assert user is not None
    return user


def display_name(user: User) -> str:
    return user.nickname or f"Player {user.public_id}"
