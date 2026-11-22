from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError
from app.fairness import hash_seed, new_client_seed, new_server_seed
from app.models import Bet, BetStatus, Seed

CLIENT_SEED_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


def _new_seed(user_id: int, client_seed: str | None = None) -> Seed:
    server_seed = new_server_seed()
    return Seed(
        user_id=user_id,
        server_seed=server_seed,
        server_seed_hash=hash_seed(server_seed),
        client_seed=client_seed or new_client_seed(),
        nonce=0,
        is_active=True,
    )


async def get_active_seed(session: AsyncSession, user_id: int, *, lock: bool = False) -> Seed:
    """Активная пара сидов юзера (создаётся при первом обращении).

    Вызывающий код должен уже держать блокировку пользователя, если собирается менять nonce.
    """
    q = select(Seed).where(Seed.user_id == user_id, Seed.is_active.is_(True))
    if lock:
        q = q.with_for_update()
    seed = await session.scalar(q)
    if seed is None:
        seed = _new_seed(user_id)
        session.add(seed)
        await session.flush()
    return seed


async def rotate_seed(session: AsyncSession, user_id: int, client_seed: str | None = None) -> tuple[Seed, Seed]:
    """Раскрыть текущий server_seed и выдать новую пару. Возвращает (старый, новый).

    Вызывающий код держит блокировку пользователя.
    """
    if client_seed is not None and not CLIENT_SEED_RE.match(client_seed):
        raise AppError("bad_client_seed", "Client seed: 1–64 символа, латиница, цифры, _ и -")

    active_game = await session.scalar(
        select(Bet.id).where(Bet.user_id == user_id, Bet.status == BetStatus.active)
    )
    if active_game:
        raise AppError("active_game", "Сначала завершите текущую игру")

    old = await get_active_seed(session, user_id, lock=True)
    old.is_active = False
    old.revealed_at = datetime.now(timezone.utc)
    await session.flush()  # снять is_active до вставки нового (уникальный индекс)

    new = _new_seed(user_id, client_seed or old.client_seed)
    session.add(new)
    await session.flush()
    return old, new
