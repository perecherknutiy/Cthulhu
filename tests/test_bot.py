"""Хендлеры бота через настоящий Dispatcher aiogram; HTTP к Telegram подменён."""
from __future__ import annotations

from datetime import datetime, timezone
from itertools import count

import pytest
from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.types import (
    CallbackQuery,
    Chat,
    Message,
    PreCheckoutQuery,
    RefundedPayment,
    SuccessfulPayment,
    Update,
)
from aiogram.types import User as TgUserObj

from app.bot.setup import create_dispatcher
from app.models import Invoice, User
from app.services import withdrawals
from tests.conftest import ADMIN_ID, make_user

_ids = count(1)


class MockSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.requests = []

    async def make_request(self, bot, method, timeout=None):
        self.requests.append(method)
        name = type(method).__name__
        if name == "GetMe":
            return TgUserObj(id=999, is_bot=True, first_name="Bot", username="cthulhu_test_bot")
        if name in {"SendMessage", "SendInvoice", "EditMessageText"}:
            return Message(message_id=next(_ids), date=datetime.now(timezone.utc),
                           chat=Chat(id=getattr(method, "chat_id", 1) or 1, type="private"),
                           text=getattr(method, "text", None) or "")
        return True

    async def stream_content(self, *a, **kw):  # pragma: no cover
        raise NotImplementedError

    async def close(self):
        pass

    def sent(self, name):
        return [m for m in self.requests if type(m).__name__ == name]


@pytest.fixture
def tg():
    session = MockSession()
    return Bot("123456:TEST-TOKEN", session=session), session


def user_obj(uid):
    return TgUserObj(id=uid, is_bot=False, first_name=f"U{uid}", username=f"user{uid}")


def msg(uid, text=None, **kw):
    return Message(message_id=next(_ids), date=datetime.now(timezone.utc), chat=Chat(id=uid, type="private"),
                   from_user=user_obj(uid), text=text, **kw)


async def feed(bot, **kw):
    await create_dispatcher().feed_update(bot, Update(update_id=next(_ids), **kw))


async def test_start_with_referral(tg, session):
    bot, s = tg
    await make_user(session, 700)
    await feed(bot, message=msg(701, "/start ref_700"))
    u = await session.get(User, 701)
    assert u.referrer_id == 700
    reply = s.sent("SendMessage")[-1]
    assert "Добро пожаловать" in reply.text
    assert reply.reply_markup.inline_keyboard[0][0].web_app.url == "https://example.com"


async def test_paysupport_exists(tg):
    bot, s = tg
    await feed(bot, message=msg(702, "/paysupport"))
    assert "Поддержка по платежам" in s.sent("SendMessage")[-1].text


async def test_deposit_command_payment_cycle(tg, session):
    bot, s = tg
    await feed(bot, message=msg(710, "/deposit 100"))
    inv_msg = s.sent("SendInvoice")[-1]
    assert inv_msg.currency == "XTR" and inv_msg.prices[0].amount == 100
    payload = inv_msg.payload
    assert (await session.get(Invoice, payload)).amount == 100

    # неверная сумма — отказ
    await feed(bot, pre_checkout_query=PreCheckoutQuery(
        id="q0", from_user=user_obj(710), currency="XTR", total_amount=50, invoice_payload=payload))
    assert s.sent("AnswerPreCheckoutQuery")[-1].ok is False
    # корректная — ок
    await feed(bot, pre_checkout_query=PreCheckoutQuery(
        id="q1", from_user=user_obj(710), currency="XTR", total_amount=100, invoice_payload=payload))
    assert s.sent("AnswerPreCheckoutQuery")[-1].ok is True

    sp = SuccessfulPayment(currency="XTR", total_amount=100, invoice_payload=payload,
                           telegram_payment_charge_id="tg-ch-1", provider_payment_charge_id="")
    await feed(bot, message=msg(710, successful_payment=sp))
    await feed(bot, message=msg(710, successful_payment=sp))  # дубль
    u = await session.get(User, 710, populate_existing=True)
    assert u.balance == 100
    assert sum("Зачислено" in m.text for m in s.sent("SendMessage")) == 1

    rp = RefundedPayment(currency="XTR", total_amount=100, invoice_payload=payload,
                         telegram_payment_charge_id="tg-ch-1")
    await feed(bot, message=msg(710, refunded_payment=rp))
    assert (await session.get(User, 710, populate_existing=True)).balance == 0


async def test_deposit_bad_amount_shows_error(tg):
    bot, s = tg
    await feed(bot, message=msg(711, "/deposit 1"))
    assert s.sent("SendMessage")[-1].text.startswith("⚠️")


async def test_admin_commands_only_for_admins(tg, session):
    bot, s = tg
    await make_user(session, 720, balance=0)
    await feed(bot, message=msg(720, "/give 720 1000"))  # не админ — игнор
    assert (await session.get(User, 720, populate_existing=True)).balance == 0

    await make_user(session, ADMIN_ID)
    await feed(bot, message=msg(ADMIN_ID, "/give 720 1000 бонус"))
    assert (await session.get(User, 720, populate_existing=True)).balance == 1000
    await feed(bot, message=msg(ADMIN_ID, "/stats"))
    assert "GGR" in s.sent("SendMessage")[-1].text
    await feed(bot, message=msg(ADMIN_ID, "/user 720"))
    assert "1000" in s.sent("SendMessage")[-1].text
    await feed(bot, message=msg(ADMIN_ID, "/ban 720"))
    assert (await session.get(User, 720, populate_existing=True)).is_banned
    await feed(bot, message=msg(ADMIN_ID, "/give abc"))
    assert s.sent("SendMessage")[-1].text.startswith("⚠️")


async def test_admin_withdrawal_callback(tg, session, settings):
    bot, s = tg
    await make_user(session, ADMIN_ID)
    await make_user(session, 730, balance=500)
    w = await withdrawals.request_withdrawal(session, settings, 730, 200)
    admin_msg = Message(message_id=5, date=datetime.now(timezone.utc), chat=Chat(id=ADMIN_ID, type="private"),
                        text=f"Заявка #{w.id}")
    await feed(bot, callback_query=CallbackQuery(id="cb1", from_user=user_obj(ADMIN_ID), chat_instance="x",
                                                 data=f"wd:ok:{w.id}", message=admin_msg))
    assert "Выплачено 200" in s.sent("EditMessageText")[-1].text
    assert any(m.chat_id == 730 and "выплачено 200" in m.text for m in s.sent("SendMessage"))
    # повторное нажатие — ошибка статуса, деньги не двигаются
    await feed(bot, callback_query=CallbackQuery(id="cb2", from_user=user_obj(ADMIN_ID), chat_instance="x",
                                                 data=f"wd:no:{w.id}", message=admin_msg))
    assert s.sent("AnswerCallbackQuery")[-1].show_alert is True
    assert (await session.get(User, 730, populate_existing=True)).balance == 300
