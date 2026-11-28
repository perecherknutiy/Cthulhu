from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Bet, BetStatus, DepositStatus, TonDeposit, User, Withdrawal, WithdrawalStatus


async def summary(session: AsyncSession, since: datetime | None = None) -> dict[str, int]:
    def period(col):
        return [col >= since] if since else []

    users = await session.scalar(select(func.count(User.id)).where(*period(User.created_at)))
    deposits = await session.scalar(
        select(func.coalesce(func.sum(TonDeposit.amount), 0))
        .where(TonDeposit.status == DepositStatus.credited, *period(TonDeposit.created_at))
    )
    bets = (await session.execute(
        select(func.count(Bet.id), func.coalesce(func.sum(Bet.amount), 0), func.coalesce(func.sum(Bet.payout), 0))
        .where(Bet.status != BetStatus.active, *period(Bet.created_at))
    )).one()
    withdrawn = await session.scalar(
        select(func.coalesce(func.sum(Withdrawal.paid_amount), 0))
        .where(Withdrawal.status == WithdrawalStatus.completed, *period(Withdrawal.created_at))
    )
    pending_wd = await session.scalar(
        select(func.count(Withdrawal.id)).where(Withdrawal.status == WithdrawalStatus.pending)
    )
    liabilities = await session.scalar(select(func.coalesce(func.sum(User.balance), 0)))
    unmatched = await session.scalar(
        select(func.count(TonDeposit.id)).where(TonDeposit.status == DepositStatus.unmatched)
    )
    return {
        "users": users or 0,
        "deposits": int(deposits),
        "bets": bets[0],
        "wagered": int(bets[1]),
        "paid_out": int(bets[2]),
        "ggr": int(bets[1]) - int(bets[2]),
        "withdrawn": int(withdrawn),
        "pending_withdrawals": pending_wd or 0,
        "user_balances": int(liabilities),
        "unmatched_deposits": unmatched or 0,
    }


async def today_and_total(session: AsyncSession) -> tuple[dict[str, int], dict[str, int]]:
    start = datetime.now(timezone.utc) - timedelta(days=1)
    return await summary(session, start), await summary(session)
