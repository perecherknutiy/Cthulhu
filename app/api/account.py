"""Профиль, конфиг, пополнение (USDT в сети TON), история, вывод. Все суммы — целые микро-USDT."""
from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import BotDep, GamesDep, InitDep, SessionDep, SettingsDep, UserDep
from app.api.schemas import MeOut, NicknameIn, TransactionOut, WithdrawalOut, WithdrawIn
from app.bot.notify import notify_admins, withdrawal_keyboard, withdrawal_text
from app.errors import Forbidden
from app.models import Transaction, TxKind, User, Withdrawal
from app import money
from app.services import bonus, deposits, withdrawals
from app.services.leaderboard import leaderboard
from app.services.users import REF_PREFIX, parse_ref, set_nickname, upsert_user
from app.vip import VIP_LEVELS, vip_for

router = APIRouter(prefix="/api", tags=["account"])


@router.get("/config")
async def config(settings: SettingsDep, games: GamesDep, bot: BotDep):
    me = await bot.me()
    return {
        **games.public_config(),
        "bot_username": me.username,
        "currency": {"code": money.CODE, "decimals": money.DECIMALS, "network": "TON"},
        "deposit": {"enabled": bool(settings.ton_wallet_address), "min": settings.min_deposit,
                    "presets": settings.deposit_presets},
        "withdraw": {"min": settings.withdraw_min, "max": settings.withdraw_max, "fee": settings.withdraw_fee,
                     "method": "ton", "wager_ratio": float(settings.withdraw_wager_ratio)},
        "referral_deposit_percent": float(settings.referral_deposit_percent),
        "vip_levels": VIP_LEVELS,
        "daily_bonus": settings.daily_bonus,
    }


@router.get("/me", response_model=MeOut)
async def me(init: InitDep, session: SessionDep, settings: SettingsDep, bot: BotDep):
    # при открытии мини-аппа обновляем профиль; реферер ставится только новым юзерам
    user, _ = await upsert_user(session, init.user, referrer_id=parse_ref(init.start_param))
    await session.commit()
    if user.is_banned:
        raise Forbidden("Аккаунт заблокирован")
    return await _me_out(session, settings, bot, user)


async def _me_out(session, settings, bot, user: User) -> MeOut:
    refs = await session.scalar(select(func.count(User.id)).where(User.referrer_id == user.id))
    earned = await session.scalar(select(func.coalesce(func.sum(Transaction.amount), 0))
                                  .where(Transaction.user_id == user.id, Transaction.kind == TxKind.referral))
    bot_me = await bot.me()
    return MeOut(
        id=user.id, telegram_id=user.id, public_id=user.public_id, nickname=user.nickname, username=user.username,
        first_name=user.first_name, photo_url=user.photo_url, balance=user.balance,
        total_deposited=user.total_deposited, total_withdrawn=user.total_withdrawn,
        total_wagered=user.total_wagered, total_won=user.total_won, total_bonus=user.total_bonus,
        wager_left=withdrawals.wager_left(settings, user.total_deposited, user.total_wagered, user.total_bonus),
        vip=vip_for(user.total_wagered),
        referral={"link": f"https://t.me/{bot_me.username}?startapp={REF_PREFIX}{user.public_id}",
                  "invited": refs or 0, "earned": int(earned or 0),
                  "percent": float(settings.referral_deposit_percent)},
        bonus=bonus.bonus_info(settings, user), created_at=user.created_at,
    )


@router.post("/me/nickname", response_model=MeOut)
async def nickname(body: NicknameIn, user: UserDep, session: SessionDep, settings: SettingsDep, bot: BotDep):
    fresh = await set_nickname(session, user.id, body.nickname)
    return await _me_out(session, settings, bot, fresh)


@router.post("/bonus/claim")
async def claim_bonus(user: UserDep, session: SessionDep, settings: SettingsDep):
    fresh = await bonus.claim(session, settings, user.id)
    return {"balance": fresh.balance, "amount": settings.daily_bonus, "bonus": bonus.bonus_info(settings, fresh)}


@router.get("/leaderboard")
async def get_leaderboard(user: UserDep, session: SessionDep, period: str = Query("week", pattern="^(week|all)$")):
    return await leaderboard(session, user.id, days=7 if period == "week" else None)


@router.get("/wallet/deposit")
async def deposit(user: UserDep, settings: SettingsDep):
    """Куда и с каким комментарием переводить USDT. Зачисление — автоматически, после появления перевода в сети."""
    return deposits.deposit_info(settings, user)


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
    w = await withdrawals.request_withdrawal(session, settings, user.id, body.amount, body.address)
    fresh = await session.get(User, user.id, populate_existing=True)
    await notify_admins(bot, settings, withdrawal_text(w, fresh), withdrawal_keyboard(w))
    return WithdrawalOut.of(w)


@router.get("/wallet/withdrawals", response_model=list[WithdrawalOut])
async def my_withdrawals(user: UserDep, session: SessionDep, limit: int = Query(20, ge=1, le=100)):
    rows = await session.scalars(
        select(Withdrawal).where(Withdrawal.user_id == user.id).order_by(Withdrawal.id.desc()).limit(limit)
    )
    return [WithdrawalOut.of(w) for w in rows]
