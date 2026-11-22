from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User

REF_PREFIX = "ref_"


@dataclass
class TgUser:
    id: int
    username: str | None = None
    first_name: str | None = None
    language_code: str | None = None


def parse_ref(start_param: str | None) -> int | None:
    """'ref_123456' -> 123456"""
    if not start_param or not start_param.startswith(REF_PREFIX):
        return None
    tail = start_param[len(REF_PREFIX):]
    return int(tail) if tail.isdigit() else None


async def upsert_user(session: AsyncSession, tg: TgUser, referrer_id: int | None = None) -> tuple[User, bool]:
    """Создать пользователя или обновить его профиль. Возвращает (user, created). Коммит — на вызывающем."""
    if referrer_id == tg.id:
        referrer_id = None
    if referrer_id is not None:
        exists = await session.scalar(select(User.id).where(User.id == referrer_id))
        if not exists:
            referrer_id = None

    stmt = (
        insert(User)
        .values(id=tg.id, username=tg.username, first_name=tg.first_name,
                language_code=tg.language_code, referrer_id=referrer_id)
        .on_conflict_do_nothing(index_elements=[User.id])
        .returning(User.id)
    )
    created = (await session.execute(stmt)).scalar() is not None
    if not created:
        await session.execute(
            update(User)
            .where(User.id == tg.id)
            .values(username=tg.username, first_name=tg.first_name,
                    language_code=tg.language_code, last_seen_at=func.now())
        )
    user = await session.scalar(select(User).where(User.id == tg.id).execution_options(populate_existing=True))
    assert user is not None
    return user, created
