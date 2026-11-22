"""Деньги: гонки ставок, платежи, возвраты, рефералка, выводы."""
import asyncio

import pytest
from sqlalchemy import func, select

from app.db import get_sessionmaker
from app.errors import AppError, InsufficientFunds
from app.models import Bet, Invoice, InvoiceStatus, Payment, PaymentStatus, Transaction, TxKind, User, WithdrawalStatus
from app.payouts import plan_gifts
from app.services import payments, withdrawals
from app.services.games import GameService
from app.services.users import TgUser
from tests.conftest import make_user


async def ledger_ok(session, user_id):
    s = await session.scalar(select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.user_id == user_id))
    u = await session.get(User, user_id, populate_existing=True)
    assert s == u.balance, "сумма леджера должна совпадать с балансом"
    return u


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


# ---------------------------------------------------------------- payments
async def test_deposit_flow_idempotent(session, settings, bot):
    await make_user(session, 20)
    inv, link = await payments.create_invoice(session, bot, settings, 20, 100)
    call = bot.called("create_invoice_link")[0]
    assert call["currency"] == "XTR" and call["prices"][0].amount == 100 and call["payload"] == inv.id

    assert await payments.check_pre_checkout(session, 20, inv.id, "XTR", 100) is None
    assert await payments.check_pre_checkout(session, 20, inv.id, "XTR", 99) is not None
    assert await payments.check_pre_checkout(session, 21, inv.id, "XTR", 100) is not None
    assert await payments.check_pre_checkout(session, 20, "nope", "XTR", 100) is not None

    tg, inv_id = TgUser(id=20), inv.id
    assert await payments.process_successful_payment(session, settings, tg, inv_id, "charge-1", "XTR", 100)
    # повтор того же апдейта (Telegram может прислать дважды) — не зачисляется
    assert not await payments.process_successful_payment(session, settings, tg, inv_id, "charge-1", "XTR", 100)
    u = await ledger_ok(session, 20)
    assert u.balance == 100 and u.total_deposited == 100
    assert (await session.get(Invoice, inv_id, populate_existing=True)).status == InvoiceStatus.paid
    assert await payments.check_pre_checkout(session, 20, inv_id, "XTR", 100) == "Этот счёт уже оплачен"


async def test_parallel_duplicate_payment_updates(settings):
    async with get_sessionmaker()() as s:
        await make_user(s, 22)

    async def deliver():
        async with get_sessionmaker()() as s:
            return await payments.process_successful_payment(s, settings, TgUser(id=22), "x", "dup", "XTR", 50)

    res = await asyncio.gather(*[deliver() for _ in range(5)])
    assert sum(res) == 1
    async with get_sessionmaker()() as s:
        assert (await ledger_ok(s, 22)).balance == 50


async def test_deposit_bounds(session, settings, bot):
    await make_user(session, 23)
    with pytest.raises(AppError):
        await payments.create_invoice(session, bot, settings, 23, settings.min_deposit - 1)


async def test_referral_bonus(session, settings, bot):
    settings.referral_deposit_percent = 10
    try:
        await make_user(session, 30)
        await make_user(session, 31, referrer_id=30)
        await payments.process_successful_payment(session, settings, TgUser(id=31), "p", "c-ref", "XTR", 255)
        assert (await ledger_ok(session, 30)).balance == 25
        assert (await ledger_ok(session, 31)).balance == 255
    finally:
        settings.referral_deposit_percent = 0


async def test_admin_refund(session, settings, bot):
    await make_user(session, 40)
    await payments.process_successful_payment(session, settings, TgUser(id=40), "p", "c-40", "XTR", 100)
    p = await payments.refund_payment(session, bot, "c-40")
    assert p.status == PaymentStatus.refunded
    assert bot.called("refund_star_payment") == [{"user_id": 40, "telegram_payment_charge_id": "c-40"}]
    assert (await ledger_ok(session, 40)).balance == 0
    with pytest.raises(AppError):
        await payments.refund_payment(session, bot, "c-40")
    # повторное событие refunded_payment от Telegram ничего не меняет
    assert not await payments.on_refunded_payment(session, 40, "c-40", 100)


async def test_refund_blocked_when_balance_spent(session, settings, bot):
    await make_user(session, 41)
    await payments.process_successful_payment(session, settings, TgUser(id=41), "p", "c-41", "XTR", 100)
    await GameService(settings).play_instant(session, 41, "dice", 100, {"target": "1.00"})
    u = await session.get(User, 41, populate_existing=True)
    if u.balance < 100:
        with pytest.raises(InsufficientFunds):
            await payments.refund_payment(session, bot, "c-41")
        await session.rollback()
        assert (await session.scalar(select(Payment.status).where(Payment.telegram_payment_charge_id == "c-41"))) \
            == PaymentStatus.paid
        assert not bot.called("refund_star_payment")


async def test_external_refund_event(session, settings):
    await make_user(session, 42)
    await payments.process_successful_payment(session, settings, TgUser(id=42), "p", "c-42", "XTR", 100)
    await GameService(settings).play_instant(session, 42, "dice", 60, {"target": "1.00"})
    assert await payments.on_refunded_payment(session, 42, "c-42", 100)
    u = await ledger_ok(session, 42)
    assert u.total_deposited == 0


# ---------------------------------------------------------------- withdrawals
def test_plan_gifts():
    d = {15: "a", 25: "b", 50: "c", 100: "d"}
    ids, total = plan_gifts(190, d)
    assert total == 190 and len(ids) == 4  # 100+50+25+15
    ids, total = plan_gifts(14, d)
    assert total == 0 and ids == []
    ids, total = plan_gifts(41, d)
    assert total == 40  # 25+15


async def test_wager_requirement(session, settings):
    await make_user(session, 50, balance=500, total_deposited=500, total_wagered=100)
    with pytest.raises(AppError, match="ставок ещё на 400"):
        await withdrawals.request_withdrawal(session, settings, 50, 200)


async def test_withdraw_reject_returns_money(session, settings):
    await make_user(session, 51, balance=500)
    w = await withdrawals.request_withdrawal(session, settings, 51, 300)
    assert (await ledger_ok(session, 51)).balance == 200
    with pytest.raises(AppError, match="уже есть заявка"):
        await withdrawals.request_withdrawal(session, settings, 51, 100)
    w = await withdrawals.reject(session, w.id, 1, "nope")
    assert w.status == WithdrawalStatus.rejected
    assert (await ledger_ok(session, 51)).balance == 500
    with pytest.raises(AppError):
        await withdrawals.reject(session, w.id, 1)


async def test_withdraw_manual_approve(session, settings, bot):
    await make_user(session, 52, balance=500)
    w = await withdrawals.request_withdrawal(session, settings, 52, 300)
    w, res = await withdrawals.approve(session, bot, w.id, 1)
    assert w.status == WithdrawalStatus.completed and w.paid_amount == 300
    u = await ledger_ok(session, 52)
    assert u.balance == 200 and u.total_withdrawn == 300


async def test_withdraw_gifts_with_remainder(session, settings, bot):
    await make_user(session, 53, balance=500)
    settings.payout_method = "gifts"
    try:
        w = await withdrawals.request_withdrawal(session, settings, 53, 199)
        w, res = await withdrawals.approve(session, bot, w.id, 1)
    finally:
        settings.payout_method = "manual"
    assert w.status == WithdrawalStatus.completed
    assert w.paid_amount == 195  # максимум ≤ 199 из номиналов 15/25/50/100, остаток 4 вернулся
    assert all(c["gift_id"] != "limited" for c in bot.called("send_gift"))
    u = await ledger_ok(session, 53)
    assert u.balance == 500 - 195 and u.total_withdrawn == 195


async def test_withdraw_gifts_bot_has_no_stars(session, settings, bot):
    await make_user(session, 54, balance=500)
    bot.star_balance = 10
    settings.payout_method = "gifts"
    try:
        w = await withdrawals.request_withdrawal(session, settings, 54, 200)
        w, res = await withdrawals.approve(session, bot, w.id, 1)
    finally:
        settings.payout_method = "manual"
    assert w.status == WithdrawalStatus.failed and res.error
    assert (await ledger_ok(session, 54)).balance == 500


async def test_withdraw_gifts_partial_failure(session, settings, bot):
    await make_user(session, 55, balance=500)
    bot.fail_gift_after = 1
    settings.payout_method = "gifts"
    try:
        w = await withdrawals.request_withdrawal(session, settings, 55, 150)
        w, res = await withdrawals.approve(session, bot, w.id, 1)
    finally:
        settings.payout_method = "manual"
    assert w.status == WithdrawalStatus.completed and w.paid_amount == 100 and res.error
    assert (await ledger_ok(session, 55)).balance == 400


async def test_ledger_kinds_cover_everything(session):
    kinds = {k.value for k in TxKind}
    assert {"deposit", "bet", "win", "withdrawal", "withdrawal_refund", "payment_refund", "referral", "admin"} <= kinds
