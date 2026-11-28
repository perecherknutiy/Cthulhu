"""Деньги: гонки ставок, пополнения USDT (TON), рефералка, выводы."""
import asyncio

import pytest
from sqlalchemy import func, select

from app.db import get_sessionmaker
from app.errors import AppError, InsufficientFunds
from app.models import Bet, DepositStatus, Transaction, TxKind, User, WithdrawalStatus
from app.services import deposits, withdrawals
from app.services.games import GameService
from tests.conftest import make_user

USER_WALLET = "UQAzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzM-lI"


async def ledger_ok(session, user_id):
    s = await session.scalar(select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.user_id == user_id))
    u = await session.get(User, user_id, populate_existing=True)
    assert s == u.balance, "сумма леджера должна совпадать с балансом"
    return u


async def deposit(session, settings, user: User | None, amount: int, tx: str, comment: str | None = None):
    return await deposits.credit_incoming(session, settings, tx_hash=tx, lt=1, amount=amount,
                                          comment=comment if comment is not None else (str(user.public_id) if user else None),
                                          sender="0:" + "33" * 32)


# ---------------------------------------------------------------- concurrency
async def test_parallel_bets_never_overdraw(settings):
    async with get_sessionmaker()() as s:
        await make_user(s, 10, balance=100)
    svc = GameService(settings)

    async def one():
        async with get_sessionmaker()() as s:
            try:
                await svc.play_instant(s, 10, "dice", 10, {"target": "1.00", "direction": "under"})  # почти всегда проигрыш
                return True
            except InsufficientFunds:
                return False

    results = await asyncio.gather(*[one() for _ in range(30)])
    async with get_sessionmaker()() as s:
        u = await ledger_ok(s, 10)
        assert u.balance >= 0
        bets = (await s.scalars(select(Bet).where(Bet.user_id == 10).order_by(Bet.nonce))).all()
        assert len(bets) == sum(results)
        assert [b.nonce for b in bets] == list(range(len(bets))), "nonce без дыр и повторов"
        assert u.total_wagered == 10 * len(bets)


async def test_bet_limits(session, settings):
    await make_user(session, 11, balance=1_000_000)
    svc = GameService(settings)
    with pytest.raises(AppError, match="Ставка"):
        await svc.play_instant(session, 11, "dice", settings.min_bet - 1, {"target": "50"})
    with pytest.raises(AppError, match="лимит"):
        await svc.play_instant(session, 11, "limbo", settings.max_bet, {"target": "1000000"})
    with pytest.raises(AppError, match="параметр"):
        await svc.play_instant(session, 11, "dice", 10, {"target": "abc"})


async def test_banned_cannot_bet(session, settings):
    await make_user(session, 12, balance=100, is_banned=True)
    with pytest.raises(AppError, match="заблокирован"):
        await GameService(settings).play_instant(session, 12, "coinflip", 10, {"side": "heads"})


# ---------------------------------------------------------------- пополнения USDT
async def test_deposit_credited_once(session, settings):
    u = await make_user(session, 20)
    dep, who = await deposit(session, settings, u, 1_500_000, "tx-1")
    assert dep.status == DepositStatus.credited and who.id == 20
    # тот же перевод ещё раз (повторный опрос, второй экземпляр сторожа) — не зачисляется
    assert await deposit(session, settings, u, 1_500_000, "tx-1") == (None, None)
    u = await ledger_ok(session, 20)
    assert u.balance == 1_500_000 and u.total_deposited == 1_500_000


async def test_parallel_duplicate_deposits(settings):
    async with get_sessionmaker()() as s:
        u = await make_user(s, 22)

    async def deliver():
        async with get_sessionmaker()() as s:
            dep, _ = await deposit(s, settings, u, 50, "dup")
            return dep is not None

    res = await asyncio.gather(*[deliver() for _ in range(5)])
    assert sum(res) == 1
    async with get_sessionmaker()() as s:
        assert (await ledger_ok(s, 22)).balance == 50


@pytest.mark.parametrize("comment, ok", [("100001", True), ("ID 100001", True), ("ara100001!", True),
                                         ("", False), ("hello", False), ("100001 100002", False), ("12345", False)])
def test_parse_memo(comment, ok):
    assert (deposits.parse_memo(comment) == 100001) is ok


async def test_unmatched_deposit_admin_assigns(session, settings):
    u = await make_user(session, 24)
    dep, who = await deposit(session, settings, None, 700, "tx-nomemo", comment="за фишки")
    assert who is None and dep.status == DepositStatus.unmatched
    dep2, _ = await deposit(session, settings, None, 300, "tx-wrong", comment="999999")  # нет такого игрока
    assert dep2.status == DepositStatus.unmatched
    dep, who = await deposits.assign(session, settings, str(dep.id), 24)
    assert dep.status == DepositStatus.credited and dep.user_id == 24
    with pytest.raises(AppError, match="уже обработан"):
        await deposits.assign(session, settings, str(dep.id), 24)
    await deposits.assign(session, settings, "tx-wr", u.id)  # по началу хэша
    assert (await ledger_ok(session, 24)).balance == 1000


async def test_banned_user_still_gets_deposit(session, settings):
    u = await make_user(session, 25, is_banned=True)
    _, who = await deposit(session, settings, u, 100, "tx-ban")
    assert who is not None and (await ledger_ok(session, 25)).balance == 100


async def test_referral_bonus(session, settings):
    settings.referral_deposit_percent = 10
    try:
        await make_user(session, 30)
        u = await make_user(session, 31, referrer_id=30)
        await deposit(session, settings, u, 255, "tx-ref")
        assert (await ledger_ok(session, 30)).balance == 25
        assert (await ledger_ok(session, 31)).balance == 255
    finally:
        settings.referral_deposit_percent = 0


def test_deposit_info(settings):
    info = deposits.deposit_info(settings, User(public_id=100777))
    assert info["enabled"] and info["memo"] == "100777" and info["address"].startswith("UQ")
    assert info["links"]["ton"].startswith("ton://transfer/" + info["address"] + "?jetton=" + settings.ton_usdt_master)
    assert "text=100777" in info["links"]["tonkeeper"] and info["links"]["tonkeeper"].startswith("https://")


# ---------------------------------------------------------------- withdrawals
async def test_wager_requirement(session, settings):
    await make_user(session, 50, balance=500, total_deposited=500, total_wagered=100)
    with pytest.raises(AppError, match="ставок ещё на 0.0004 USDT"):
        await withdrawals.request_withdrawal(session, settings, 50, 200, USER_WALLET)


async def test_withdraw_reject_returns_money(session, settings):
    await make_user(session, 51, balance=500)
    w = await withdrawals.request_withdrawal(session, settings, 51, 300, USER_WALLET)
    assert w.address == USER_WALLET and w.method == "ton"
    assert (await ledger_ok(session, 51)).balance == 200
    with pytest.raises(AppError, match="уже есть заявка"):
        await withdrawals.request_withdrawal(session, settings, 51, 100, USER_WALLET)
    w = await withdrawals.reject(session, w.id, 1, "nope")
    assert w.status == WithdrawalStatus.rejected
    assert (await ledger_ok(session, 51)).balance == 500
    with pytest.raises(AppError):
        await withdrawals.reject(session, w.id, 1)


async def test_withdraw_mark_paid(session, settings):
    await make_user(session, 52, balance=500)
    w = await withdrawals.request_withdrawal(session, settings, 52, 300, "0:" + "33" * 32)  # raw-адрес тоже можно
    assert w.address == USER_WALLET
    w = await withdrawals.mark_paid(session, w.id, 1, tx_hash="abc")
    assert w.status == WithdrawalStatus.completed and w.paid_amount == 300 and w.tx_hash == "abc"
    u = await ledger_ok(session, 52)
    assert u.balance == 200 and u.total_withdrawn == 300
    with pytest.raises(AppError):
        await withdrawals.mark_paid(session, w.id, 1)
    with pytest.raises(AppError):
        await withdrawals.reject(session, w.id, 1)


async def test_withdraw_fee(session, settings):
    await make_user(session, 53, balance=500)
    settings.withdraw_fee = 30
    try:
        w = await withdrawals.request_withdrawal(session, settings, 53, 300, USER_WALLET)
    finally:
        settings.withdraw_fee = 0
    w = await withdrawals.mark_paid(session, w.id, 1)
    assert w.fee == 30 and w.paid_amount == 270
    assert (await ledger_ok(session, 53)).balance == 200


@pytest.mark.parametrize("addr", ["", "hello", "UQAzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzM-lA",  # плохая контрольная сумма
                                  "Ef8zMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzM0vF",  # masterchain
                                  "UQAREREREREREREREREREREREREREREREREREREREREREbvW"])  # адрес самого казино
async def test_withdraw_bad_address(session, settings, addr):
    await make_user(session, 54, balance=500)
    with pytest.raises(AppError) as e:
        await withdrawals.request_withdrawal(session, settings, 54, 200, addr)
    assert e.value.code == "bad_address"
    assert (await ledger_ok(session, 54)).balance == 500


async def test_ledger_kinds_cover_everything(session):
    kinds = {k.value for k in TxKind}
    assert {"deposit", "bet", "win", "withdrawal", "withdrawal_refund", "referral", "admin", "bonus"} <= kinds
