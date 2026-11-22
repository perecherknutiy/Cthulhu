"""Профиль, конфиг, пополнение, история, вывод."""
from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import BotDep, GamesDep, InitDep, SessionDep, SettingsDep, UserDep
from app.api.schemas import InvoiceIn, InvoiceOut, MeOut, TransactionOut, WithdrawalOut, WithdrawIn
from app.bot.notify import notify_admins, withdrawal_keyboard, withdrawal_text
from app.errors import Forbidden
from app.models import Transaction, User, Withdrawal
from app.services import payments, withdrawals
from app.services.users import REF_PREFIX, parse_ref, upsert_user

router = APIRouter(prefix="/api", tags=["account"])


@router.get("/config")
async def config(settings: SettingsDep, games: GamesDep, bot: BotDep):
    me = await bot.me()
    return {
        **games.public_config(),
        "bot_username": me.username,
        "deposit": {"min": settings.min_deposit, "max": settings.max_deposit, "presets": settings.deposit_presets},
        "withdraw": {"min": settings.withdraw_min, "max": settings.withdraw_max, "method": settings.payout_method,
                     "wager_ratio": float(settings.withdraw_wager_ratio)},
        "referral_deposit_percent": float(settings.referral_deposit_percent),
    }


@router.get("/me", response_model=MeOut)
async def me(init: InitDep, session: SessionDep, settings: SettingsDep, bot: BotDep):
    # при открытии мини-аппа обновляем профиль; реферер ставится только новым юзерам
    user, _ = await upsert_user(session, init.user, referrer_id=parse_ref(init.start_param))
    await session.commit()
    if user.is_banned:
        raise Forbidden("Аккаунт заблокирован")
    refs = await session.scalar(select(func.count(User.id)).where(User.referrer_id == user.id))
    bot_me = await bot.me()
    return MeOut(
        id=user.id, username=user.username, first_name=user.first_name, balance=user.balance,
        total_deposited=user.total_deposited, total_withdrawn=user.total_withdrawn,
        total_wagered=user.total_wagered, total_won=user.total_won,
        wager_left=withdrawals.wager_left(settings, user.total_deposited, user.total_wagered),
        referral_link=f"https://t.me/{bot_me.username}?startapp={REF_PREFIX}{user.id}",
        referrals=refs or 0,
    )


@router.post("/wallet/invoice", response_model=InvoiceOut)
async def create_invoice(body: InvoiceIn, user: UserDep, session: SessionDep, bot: BotDep, settings: SettingsDep):
    invoice, link = await payments.create_invoice(session, bot, settings, user.id, body.amount)
    return InvoiceOut(invoice_id=invoice.id, invoice_link=link)


@router.get("/wallet/transactions", response_model=list[TransactionOut])
async def transactions(user: UserDep, session: SessionDep,
                       limit: int = Query(30, ge=1, le=100), before_id: int | None = None):
    q = select(Transaction).where(Transaction.user_id == user.id)
    if before_id:
        q = q.where(Transaction.id < before_id)
    rows = await session.scalars(q.order_by(Transaction.id.desc()).limit(limit))
    return [TransactionOut.of(t) for t in rows]


@router.post("/wallet/withdraw", response_model=WithdrawalOut)
async def withdraw(body: WithdrawIn, user: UserDep, session: SessionDep, bot: BotDep, settings: SettingsDep):
    w = await withdrawals.request_withdrawal(session, settings, user.id, body.amount)
    fresh = await session.get(User, user.id, populate_existing=True)
    await notify_admins(bot, settings, withdrawal_text(w, fresh), withdrawal_keyboard(w))
    return WithdrawalOut.of(w)


@router.get("/wallet/withdrawals", response_model=list[WithdrawalOut])
async def my_withdrawals(user: UserDep, session: SessionDep, limit: int = Query(20, ge=1, le=100)):
    rows = await session.scalars(
        select(Withdrawal).where(Withdrawal.user_id == user.id).order_by(Withdrawal.id.desc()).limit(limit)
    )
    return [WithdrawalOut.of(w) for w in rows]
