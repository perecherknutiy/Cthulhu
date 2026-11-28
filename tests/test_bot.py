"""Хендлеры бота через настоящий Dispatcher aiogram; HTTP к Telegram подменён."""
from __future__ import annotations

from datetime import datetime, timezone
from itertools import count

import pytest
from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.types import CallbackQuery, Chat, Message, Update
from aiogram.types import User as TgUserObj

from app.bot.setup import create_dispatcher
from app.models import User
from app.services import deposits, withdrawals
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
            return TgUserObj(id=999, is_bot=True, first_name="Bot", username="ara_test_bot")
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


async def test_support_exists(tg):
    bot, s = tg
    await feed(bot, message=msg(702, "/support"))
    assert "Поддержка" in s.sent("SendMessage")[-1].text


async def test_deposit_command_shows_address_and_memo(tg, session, settings):
    bot, s = tg
    await feed(bot, message=msg(710, "/deposit"))
    u = await session.get(User, 710)
    text = s.sent("SendMessage")[-1].text
    assert "USDT" in text and str(u.public_id) in text and deposits.deposit_info(settings, u)["address"] in text
    kb = s.sent("SendMessage")[-1].reply_markup.inline_keyboard
    assert kb[0][0].url.startswith("https://app.tonkeeper.com/transfer/")


async def test_admin_credits_unmatched_deposit(tg, session, settings):
    bot, s = tg
    await make_user(session, ADMIN_ID)
    u = await make_user(session, 712)
    dep, _ = await deposits.credit_incoming(session, settings, tx_hash="abcdef123", lt=5, amount=2_000_000,
                                            comment=None, sender=None)
    await feed(bot, message=msg(ADMIN_ID, "/deposits"))
    assert f"№{dep.id}" in s.sent("SendMessage")[-1].text
    await feed(bot, message=msg(ADMIN_ID, f"/credit {dep.id} #{u.public_id}"))
    assert (await session.get(User, 712, populate_existing=True)).balance == 2_000_000
    assert any(m.chat_id == 712 and "+2.00 USDT" in m.text for m in s.sent("SendMessage"))


async def test_admin_commands_only_for_admins(tg, session):
    bot, s = tg
    await make_user(session, 720, balance=0)
    await feed(bot, message=msg(720, "/give 720 1000"))  # не админ — игнор
    assert (await session.get(User, 720, populate_existing=True)).balance == 0

    await make_user(session, ADMIN_ID)
    await feed(bot, message=msg(ADMIN_ID, "/give 720 1.5 бонус"))  # сумма в USDT
    assert (await session.get(User, 720, populate_existing=True)).balance == 1_500_000
    await feed(bot, message=msg(ADMIN_ID, "/stats"))
    assert "GGR" in s.sent("SendMessage")[-1].text
    await feed(bot, message=msg(ADMIN_ID, "/user 720"))
    assert "1.50 USDT" in s.sent("SendMessage")[-1].text
    await feed(bot, message=msg(ADMIN_ID, "/ban 720"))
    assert (await session.get(User, 720, populate_existing=True)).is_banned
    await feed(bot, message=msg(ADMIN_ID, "/give abc"))
    assert s.sent("SendMessage")[-1].text.startswith("⚠️")


async def test_admin_withdrawal_callback(tg, session, settings):
    bot, s = tg
    await make_user(session, ADMIN_ID)
    await make_user(session, 730, balance=500)
    w = await withdrawals.request_withdrawal(session, settings, 730, 200, "0:" + "33" * 32)
    admin_msg = Message(message_id=5, date=datetime.now(timezone.utc), chat=Chat(id=ADMIN_ID, type="private"),
                        text=f"Заявка #{w.id}")
    await feed(bot, callback_query=CallbackQuery(id="cb1", from_user=user_obj(ADMIN_ID), chat_instance="x",
                                                 data=f"wd:ok:{w.id}", message=admin_msg))
    assert "Отправлено 0.0002 USDT" in s.sent("EditMessageText")[-1].text
    assert any(m.chat_id == 730 and "отправлены на" in m.text for m in s.sent("SendMessage"))
    # повторное нажатие — ошибка статуса, деньги не двигаются
    await feed(bot, callback_query=CallbackQuery(id="cb2", from_user=user_obj(ADMIN_ID), chat_instance="x",
                                                 data=f"wd:no:{w.id}", message=admin_msg))
    assert s.sent("AnswerCallbackQuery")[-1].show_alert is True
    assert (await session.get(User, 730, populate_existing=True)).balance == 300
