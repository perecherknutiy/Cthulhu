"""Вывод средств.

request → (баланс сразу списывается, статус pending) → админ:
   approve → processing → выплата через PayoutMethod → completed / failed (невыплаченный остаток возвращается)
   reject  → rejected (вся сумма возвращается на баланс)
"""
from __future__ import annotations

from datetime import datetime, timezone

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.errors import AppError, NotFound
from app.models import TxKind, Withdrawal, WithdrawalStatus
from app.payouts import PayoutResult, get_payout_method
from app.services import wallet

OPEN_STATUSES = (WithdrawalStatus.pending, WithdrawalStatus.processing)


def wager_left(settings: Settings, total_deposited: int, total_wagered: int) -> int:
    """Сколько ещё нужно проставить до разблокировки вывода."""
    need = int(total_deposited * settings.withdraw_wager_ratio)
    return max(0, need - total_wagered)


async def request_withdrawal(session: AsyncSession, settings: Settings, user_id: int, amount: int) -> Withdrawal:
    if not (settings.withdraw_min <= amount <= settings.withdraw_max):
        raise AppError("bad_amount", f"Сумма вывода: от {settings.withdraw_min} до {settings.withdraw_max} ⭐")
    user = await wallet.lock_user(session, user_id)
    left = wager_left(settings, user.total_deposited, user.total_wagered)
    if left > 0:
        raise AppError("wager_required", f"Для вывода нужно сделать ставок ещё на {left} ⭐")
    has_open = await session.scalar(
        select(Withdrawal.id).where(Withdrawal.user_id == user_id, Withdrawal.status.in_(OPEN_STATUSES))
    )
    if has_open:
        raise AppError("withdrawal_pending", "У вас уже есть заявка на вывод в обработке")

    w = Withdrawal(user_id=user_id, amount=amount, method=settings.payout_method, status=WithdrawalStatus.pending)
    session.add(w)
    await session.flush()
    wallet.apply(session, user, TxKind.withdrawal, -amount, ref_type="withdrawal", ref_id=w.id)
    await session.commit()
    return w


async def _lock_withdrawal(session: AsyncSession, withdrawal_id: int) -> Withdrawal:
    w = await session.get(Withdrawal, withdrawal_id, with_for_update=True, populate_existing=True)
    if w is None:
        raise NotFound("Заявка")
    return w


async def reject(session: AsyncSession, withdrawal_id: int, admin_id: int, reason: str | None = None) -> Withdrawal:
    w = await _lock_withdrawal(session, withdrawal_id)
    if w.status != WithdrawalStatus.pending:
        raise AppError("bad_status", f"Заявка в статусе {w.status.value}")
    user = await wallet.lock_user(session, w.user_id, allow_banned=True)
    wallet.apply(session, user, TxKind.withdrawal_refund, w.amount, ref_type="withdrawal", ref_id=w.id, note=reason)
    w.status = WithdrawalStatus.rejected
    w.admin_id = admin_id
    w.note = reason
    w.processed_at = datetime.now(timezone.utc)
    await session.commit()
    return w


async def approve(session: AsyncSession, bot: Bot, withdrawal_id: int, admin_id: int) -> tuple[Withdrawal, PayoutResult]:
    # 1. pending -> processing (короткая транзакция, чтобы не держать блокировки во время выплаты)
    w = await _lock_withdrawal(session, withdrawal_id)
    if w.status != WithdrawalStatus.pending:
        raise AppError("bad_status", f"Заявка в статусе {w.status.value}")
    w.status = WithdrawalStatus.processing
    w.admin_id = admin_id
    await session.commit()

    # 2. выплата
    method = get_payout_method(w.method)
    try:
        result = await method.pay(bot, w.user_id, w.amount, w.id)
    except Exception as e:  # noqa: BLE001
        result = PayoutResult(paid=0, error=str(e))

    # 3. фиксация результата
    w = await _lock_withdrawal(session, withdrawal_id)
    w.paid_amount = result.paid
    w.processed_at = datetime.now(timezone.utc)
    w.note = "; ".join(result.details + ([result.error] if result.error else [])) or None
    user = await wallet.lock_user(session, w.user_id, allow_banned=True)
    remainder = w.amount - result.paid
    if remainder > 0:
        wallet.apply(session, user, TxKind.withdrawal_refund, remainder, ref_type="withdrawal", ref_id=w.id,
                     note="Невыплаченный остаток")
    user.total_withdrawn += result.paid
    w.status = WithdrawalStatus.failed if (result.error and result.paid == 0) else WithdrawalStatus.completed
    await session.commit()
    return w, result
