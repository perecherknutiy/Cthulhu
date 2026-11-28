"""Пополнения USDT через свой кошелёк в сети TON.

Игрок переводит USDT на адрес казино и пишет в комментарии свой ID (тот, что в профиле). Сторож
(app/ton/watcher.py) находит перевод и вызывает credit_incoming(). Каждый перевод учитывается один раз —
по хэшу транзакции. Перевод без подходящего комментария сохраняется как unmatched: админ зачисляет его
командой /credit.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import ROUND_DOWN, Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.errors import AppError, NotFound
from app.models import DepositStatus, TonDeposit, TxKind, User
from app.services import wallet
from app.ton.address import friendly, jetton_transfer_link

MEMO_RE = re.compile(r"(?<!\d)(\d{6,12})(?!\d)")


def memo_for(user: User) -> str:
    return str(user.public_id)


def parse_memo(comment: str | None) -> int | None:
    """'100042', 'ID 100042', 'ara100042' → 100042. Ровно одно число из 6–12 цифр, иначе None."""
    found = MEMO_RE.findall(comment or "")
    return int(found[0]) if len(found) == 1 else None


def deposit_info(settings: Settings, user: User) -> dict:
    if not settings.ton_wallet_address:
        return {"enabled": False}
    addr = friendly(settings.ton_wallet_address, bounceable=False)
    memo = memo_for(user)
    return {
        "enabled": True, "network": "TON", "token": "USDT", "decimals": 6,
        "address": addr, "memo": memo, "jetton_master": settings.ton_usdt_master,
        "min": settings.min_deposit, "presets": settings.deposit_presets,
        "links": {
            "ton": jetton_transfer_link(addr, settings.ton_usdt_master, text=memo),
            "tonkeeper": jetton_transfer_link(addr, settings.ton_usdt_master, text=memo,
                                              prefix="https://app.tonkeeper.com/"),
        },
    }


async def _credit(session: AsyncSession, settings: Settings, dep: TonDeposit, user: User) -> None:
    wallet.apply(session, user, TxKind.deposit, dep.amount, ref_type="ton", ref_id=dep.tx_hash)
    user.total_deposited += dep.amount
    dep.user_id, dep.status, dep.credited_at = user.id, DepositStatus.credited, datetime.now(UTC)
    pct = settings.referral_deposit_percent
    if pct > 0 and user.referrer_id:
        bonus = int((Decimal(dep.amount) * pct / 100).to_integral_value(rounding=ROUND_DOWN))
        if bonus > 0:
            referrer = await wallet.lock_user(session, user.referrer_id, allow_banned=True)
            wallet.apply(session, referrer, TxKind.referral, bonus, ref_type="ton", ref_id=dep.tx_hash,
                         note=f"Реферал {user.public_id}")


async def credit_incoming(session: AsyncSession, settings: Settings, *, tx_hash: str, lt: int, amount: int,
                          comment: str | None, sender: str | None) -> tuple[TonDeposit | None, User | None]:
    """Записать входящий перевод и зачислить его игроку. (None, None) — этот перевод уже обработан."""
    public_id = parse_memo(comment)
    user = None
    if public_id is not None:
        uid = await session.scalar(select(User.id).where(User.public_id == public_id))
        if uid is not None:
            user = await wallet.lock_user(session, uid, allow_banned=True)  # деньги игрока зачисляем и при бане
    dep_id = (await session.execute(
        insert(TonDeposit).values(tx_hash=tx_hash, lt=lt, amount=amount, comment=(comment or None) and comment[:256],
                                  sender=sender, status=DepositStatus.unmatched)
        .on_conflict_do_nothing(index_elements=[TonDeposit.tx_hash]).returning(TonDeposit.id)
    )).scalar()
    if dep_id is None:
        await session.rollback()
        return None, None
    dep = await session.get(TonDeposit, dep_id)
    if user is not None:
        await _credit(session, settings, dep, user)
    await session.commit()
    return dep, user


async def assign(session: AsyncSession, settings: Settings, deposit_ref: str, user_id: int) -> tuple[TonDeposit, User]:
    """Админ зачисляет перевод без комментария: deposit_ref — номер или начало хэша."""
    q = select(TonDeposit).with_for_update()
    q = q.where(TonDeposit.id == int(deposit_ref)) if deposit_ref.isdigit() else \
        q.where(TonDeposit.tx_hash.startswith(deposit_ref))
    rows = (await session.scalars(q.limit(2))).all()
    if not rows:
        raise NotFound("Перевод")
    if len(rows) > 1:
        raise AppError("ambiguous", "Под это начало хэша подходит несколько переводов — укажите номер")
    dep = rows[0]
    if dep.status != DepositStatus.unmatched:
        raise AppError("bad_status", f"Перевод уже обработан ({dep.status.value})")
    user = await wallet.lock_user(session, user_id, allow_banned=True)
    await _credit(session, settings, dep, user)
    await session.commit()
    return dep, user
