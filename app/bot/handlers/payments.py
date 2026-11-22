from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import Message, PreCheckoutQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.services import payments
from app.services.users import TgUser

log = logging.getLogger(__name__)
router = Router(name="payments")


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery, session: AsyncSession):
    # На ответ у бота 10 секунд
    error = await payments.check_pre_checkout(session, query.from_user.id, query.invoice_payload,
                                              query.currency, query.total_amount)
    if error:
        await query.answer(ok=False, error_message=error)
    else:
        await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message, session: AsyncSession, settings: Settings):
    sp = message.successful_payment
    u = message.from_user
    credited = await payments.process_successful_payment(
        session, settings,
        TgUser(id=u.id, username=u.username, first_name=u.first_name, language_code=u.language_code),
        payload=sp.invoice_payload, charge_id=sp.telegram_payment_charge_id,
        currency=sp.currency, total_amount=sp.total_amount,
    )
    if credited:
        await message.answer(f"✅ Зачислено <b>{sp.total_amount} ⭐</b>. Удачной игры!")


@router.message(F.refunded_payment)
async def refunded_payment(message: Message, session: AsyncSession):
    rp = message.refunded_payment
    changed = await payments.on_refunded_payment(session, message.from_user.id,
                                                 rp.telegram_payment_charge_id, rp.total_amount)
    if changed:
        log.warning("External refund %s for user %s", rp.telegram_payment_charge_id, message.from_user.id)
