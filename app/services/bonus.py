"""Ежедневный бонус. Раз в сутки по UTC; сумма — DAILY_BONUS, 0 = выключено."""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.errors import AppError
from app.models import TxKind, User
from app.services import wallet


def _today():
    return datetime.now(timezone.utc).date()


def bonus_info(settings: Settings, user: User) -> dict:
    if settings.daily_bonus <= 0:
        return {"enabled": False}
    available = user.bonus_claimed_on != _today()
    next_at = datetime.combine(_today() + timedelta(days=1), time(0), tzinfo=timezone.utc)
    return {"enabled": True, "amount": settings.daily_bonus, "available": available,
            "next_at": None if available else next_at.isoformat()}


async def claim(session: AsyncSession, settings: Settings, user_id: int) -> User:
    if settings.daily_bonus <= 0:
        raise AppError("bonus_disabled", "Ежедневный бонус выключен")
    user = await wallet.lock_user(session, user_id)
    if user.bonus_claimed_on == _today():
        raise AppError("bonus_claimed", "Бонус уже получен сегодня — следующий после полуночи по UTC")
    wallet.apply(session, user, TxKind.bonus, settings.daily_bonus, ref_type="daily", ref_id=_today().isoformat())
    user.total_bonus += settings.daily_bonus
    user.bonus_claimed_on = _today()
    await session.commit()
    return user
