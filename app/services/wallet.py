"""Кошелёк. Единственное место, где меняется users.balance.

Правило: любая операция с деньгами
  1) берёт блокировку строки пользователя (lock_user → SELECT ... FOR UPDATE),
  2) меняет баланс через apply(), который пишет запись в леджер,
  3) коммитится одной транзакцией вместе с остальными изменениями (ставка, платёж и т.п.).
Так параллельные запросы одного пользователя выстраиваются в очередь и баланс не уходит в минус.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import Forbidden, InsufficientFunds, NotFound
from app.models import Transaction, TxKind, User


async def lock_user(session: AsyncSession, user_id: int, *, allow_banned: bool = False) -> User:
    user = await session.scalar(
        select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True)
    )
    if user is None:
        raise NotFound("Пользователь")
    if user.is_banned and not allow_banned:
        raise Forbidden("Аккаунт заблокирован")
    return user


def apply(
    session: AsyncSession,
    user: User,
    kind: TxKind,
    amount: int,
    *,
    ref_type: str | None = None,
    ref_id: str | int | None = None,
    note: str | None = None,
    allow_negative: bool = False,
) -> Transaction:
    """Изменить баланс заблокированного пользователя и записать это в леджер."""
    if amount == 0:
        raise ValueError("amount must be non-zero")
    new_balance = user.balance + amount
    if new_balance < 0 and not allow_negative:
        raise InsufficientFunds()
    user.balance = new_balance
    tx = Transaction(
        user_id=user.id,
        kind=kind,
        amount=amount,
        balance_after=new_balance,
        ref_type=ref_type,
        ref_id=str(ref_id) if ref_id is not None else None,
        note=note,
    )
    session.add(tx)
    return tx
