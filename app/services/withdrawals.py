"""Вывод USDT на кошелёк игрока в сети TON.

request → баланс сразу списывается, заявка pending → админу приходит заявка с кнопкой «Открыть перевод
в Tonkeeper» (адрес, сумма и комментарий уже подставлены):
   «✅ Отправил»  → completed
   «❌ Отклонить» → rejected, сумма возвращается на баланс
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.errors import AppError, NotFound
from app.models import TxKind, Withdrawal, WithdrawalStatus
from app.money import usdt
from app.services import wallet
from app.ton import address as ton_address

OPEN_STATUSES = (WithdrawalStatus.pending, WithdrawalStatus.processing)


def wager_left(settings: Settings, total_deposited: int, total_wagered: int, total_bonus: int = 0) -> int:
    """Сколько ещё нужно проставить до разблокировки вывода (пополнения и бонусы × коэффициент)."""
    need = int((total_deposited + total_bonus) * settings.withdraw_wager_ratio)
    return max(0, need - total_wagered)


def payout_comment(w: Withdrawal) -> str:
    return f"ARA Casino #{w.id}"


async def request_withdrawal(session: AsyncSession, settings: Settings, user_id: int, amount: int,
                             to_address: str) -> Withdrawal:
    if not (settings.withdraw_min <= amount <= settings.withdraw_max):
        raise AppError("bad_amount", f"Сумма вывода: от {usdt(settings.withdraw_min)} до {usdt(settings.withdraw_max)}")
    addr = ton_address.parse(to_address)
    if settings.ton_wallet_address and ton_address.same(addr, settings.ton_wallet_address):
        raise AppError("bad_address", "Это адрес казино — укажите свой кошелёк")
    user = await wallet.lock_user(session, user_id)
    left = wager_left(settings, user.total_deposited, user.total_wagered, user.total_bonus)
    if left > 0:
        raise AppError("wager_required", f"Для вывода нужно сделать ставок ещё на {usdt(left)}")
    has_open = await session.scalar(
        select(Withdrawal.id).where(Withdrawal.user_id == user_id, Withdrawal.status.in_(OPEN_STATUSES))
    )
    if has_open:
        raise AppError("withdrawal_pending", "У вас уже есть заявка на вывод в обработке")

    w = Withdrawal(user_id=user_id, amount=amount, fee=min(settings.withdraw_fee, amount), method="ton",
                   address=ton_address.friendly(addr, bounceable=False), status=WithdrawalStatus.pending)
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
    w.processed_at = datetime.now(UTC)
    await session.commit()
    return w


async def mark_paid(session: AsyncSession, withdrawal_id: int, admin_id: int, tx_hash: str | None = None) -> Withdrawal:
    """Админ отправил USDT со своего кошелька и подтверждает это."""
    w = await _lock_withdrawal(session, withdrawal_id)
    if w.status != WithdrawalStatus.pending:
        raise AppError("bad_status", f"Заявка в статусе {w.status.value}")
    user = await wallet.lock_user(session, w.user_id, allow_banned=True)
    w.status = WithdrawalStatus.completed
    w.paid_amount = w.amount - w.fee
    w.admin_id = admin_id
    w.tx_hash = (tx_hash or "").strip()[:128] or None
    w.processed_at = datetime.now(UTC)
    user.total_withdrawn += w.amount
    await session.commit()
    return w
