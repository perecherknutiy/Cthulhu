"""Пополнение звёздами (XTR).

Поток:
  1. create_invoice()  — создаём Invoice в БД и ссылку через createInvoiceLink;
                         мини-апп открывает её через Telegram.WebApp.openInvoice(link).
  2. pre_checkout_query — check_pre_checkout(): инвойс существует, не оплачен, сумма/юзер совпадают.
  3. successful_payment — process_successful_payment(): идемпотентно (по telegram_payment_charge_id)
                         зачисляем баланс + реферальный бонус.
  4. Возвраты: refund_payment() (инициирует админ) и on_refunded_payment() (событие от Telegram).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import ROUND_DOWN, Decimal

from aiogram import Bot
from aiogram.types import LabeledPrice
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.errors import AppError, NotFound
from app.models import Invoice, InvoiceStatus, Payment, PaymentStatus, TxKind, User
from app.services import wallet
from app.services.users import TgUser, upsert_user

log = logging.getLogger(__name__)
CURRENCY = "XTR"


async def create_invoice(session: AsyncSession, bot: Bot, settings: Settings, user_id: int, amount: int) -> tuple[Invoice, str]:
    if not (settings.min_deposit <= amount <= settings.max_deposit):
        raise AppError("bad_amount", f"Сумма пополнения: от {settings.min_deposit} до {settings.max_deposit} ⭐")
    invoice = Invoice(id=uuid.uuid4().hex, user_id=user_id, amount=amount, status=InvoiceStatus.pending)
    session.add(invoice)
    await session.flush()
    link = await bot.create_invoice_link(
        title="Пополнение баланса",
        description=f"Пополнение игрового баланса на {amount} ⭐",
        payload=invoice.id,
        currency=CURRENCY,
        prices=[LabeledPrice(label=f"{amount} ⭐", amount=amount)],
    )
    await session.commit()
    return invoice, link


async def send_invoice_message(session: AsyncSession, bot: Bot, settings: Settings, chat_id: int, amount: int) -> None:
    """То же самое, но инвойс-сообщением в чат с ботом (команда /deposit)."""
    if not (settings.min_deposit <= amount <= settings.max_deposit):
        raise AppError("bad_amount", f"Сумма пополнения: от {settings.min_deposit} до {settings.max_deposit} ⭐")
    invoice = Invoice(id=uuid.uuid4().hex, user_id=chat_id, amount=amount, status=InvoiceStatus.pending)
    session.add(invoice)
    await session.flush()
    await bot.send_invoice(
        chat_id=chat_id,
        title="Пополнение баланса",
        description=f"Пополнение игрового баланса на {amount} ⭐",
        payload=invoice.id,
        currency=CURRENCY,
        prices=[LabeledPrice(label=f"{amount} ⭐", amount=amount)],
    )
    await session.commit()


async def check_pre_checkout(session: AsyncSession, user_id: int, payload: str, currency: str,
                             total_amount: int) -> str | None:
    """None — можно принимать платёж, иначе текст ошибки для пользователя."""
    if currency != CURRENCY:
        return "Неподдерживаемая валюта"
    invoice = await session.get(Invoice, payload)
    if invoice is None or invoice.user_id != user_id:
        return "Счёт не найден, создайте новый"
    if invoice.status != InvoiceStatus.pending:
        return "Этот счёт уже оплачен"
    if invoice.amount != total_amount:
        return "Сумма не совпадает со счётом"
    user = await session.get(User, user_id)
    if user is None or user.is_banned:
        return "Аккаунт недоступен"
    return None


async def process_successful_payment(
    session: AsyncSession, settings: Settings, tg_user: TgUser, payload: str, charge_id: str,
    currency: str, total_amount: int,
) -> bool:
    """Зачислить платёж. Возвращает False, если этот charge_id уже обработан (повтор апдейта)."""
    if currency != CURRENCY:
        log.error("Unexpected currency %s in payment %s", currency, charge_id)
        return False

    await upsert_user(session, tg_user)  # на случай, если юзер не открывал /start
    invoice = await session.get(Invoice, payload, with_for_update=True)

    inserted = await session.execute(
        insert(Payment)
        .values(user_id=tg_user.id, invoice_id=invoice.id if invoice else None, amount=total_amount,
                telegram_payment_charge_id=charge_id, status=PaymentStatus.paid)
        .on_conflict_do_nothing(index_elements=[Payment.telegram_payment_charge_id])
        .returning(Payment.id)
    )
    payment_id = inserted.scalar()
    if payment_id is None:
        await session.rollback()
        return False

    if invoice is not None:
        invoice.status = InvoiceStatus.paid
        invoice.paid_at = datetime.now(timezone.utc)
    else:
        log.warning("Payment %s without known invoice payload=%r — зачисляем всё равно", charge_id, payload)

    user = await wallet.lock_user(session, tg_user.id, allow_banned=True)
    wallet.apply(session, user, TxKind.deposit, total_amount, ref_type="payment", ref_id=payment_id)
    user.total_deposited += total_amount

    # реферальный бонус
    pct = settings.referral_deposit_percent
    if pct > 0 and user.referrer_id:
        bonus = int((Decimal(total_amount) * pct / 100).to_integral_value(rounding=ROUND_DOWN))
        if bonus > 0:
            referrer = await wallet.lock_user(session, user.referrer_id, allow_banned=True)
            wallet.apply(session, referrer, TxKind.referral, bonus, ref_type="payment", ref_id=payment_id,
                         note=f"Реферал {user.id}")
    await session.commit()
    return True


async def refund_payment(session: AsyncSession, bot: Bot, charge_id: str, *, force: bool = False) -> Payment:
    """Вернуть платёж пользователю (по инициативе админа).

    Списывает сумму с игрового баланса. Если звёзды уже проиграны, без force=True откажет.
    """
    payment = await session.scalar(
        select(Payment).where(Payment.telegram_payment_charge_id == charge_id).with_for_update()
    )
    if payment is None:
        raise NotFound("Платёж")
    if payment.status == PaymentStatus.refunded:
        raise AppError("already_refunded", "Платёж уже возвращён")
    user = await wallet.lock_user(session, payment.user_id, allow_banned=True)
    wallet.apply(session, user, TxKind.payment_refund, -payment.amount, ref_type="payment", ref_id=payment.id,
                 allow_negative=force)
    user.total_deposited -= payment.amount
    payment.status = PaymentStatus.refunded
    payment.refunded_at = datetime.now(timezone.utc)
    await session.flush()
    # API-вызов внутри транзакции: если Telegram откажет — всё откатится
    await bot.refund_star_payment(user_id=payment.user_id, telegram_payment_charge_id=charge_id)
    await session.commit()
    return payment


async def on_refunded_payment(session: AsyncSession, user_id: int, charge_id: str, amount: int) -> bool:
    """Telegram сообщил о возврате (refunded_payment). Если возврат сделали не мы — списываем баланс."""
    payment = await session.scalar(
        select(Payment).where(Payment.telegram_payment_charge_id == charge_id).with_for_update()
    )
    if payment is None or payment.status == PaymentStatus.refunded:
        await session.rollback()
        return False
    user = await wallet.lock_user(session, user_id, allow_banned=True)
    wallet.apply(session, user, TxKind.payment_refund, -amount, ref_type="payment", ref_id=payment.id,
                 allow_negative=True, note="Внешний возврат")
    user.total_deposited -= amount
    payment.status = PaymentStatus.refunded
    payment.refunded_at = datetime.now(timezone.utc)
    await session.commit()
    return True
