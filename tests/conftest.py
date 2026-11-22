"""Тесты гоняются на настоящем PostgreSQL (нужны FOR UPDATE, частичные индексы, ON CONFLICT).

TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/casino_test pytest
"""
from __future__ import annotations

import json
import os
import time
from types import SimpleNamespace

os.environ.setdefault("BOT_TOKEN", "123456:TEST-TOKEN")
os.environ["BOT_MODE"] = "none"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/casino_test")
os.environ.setdefault("ADMIN_IDS", "1")

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.config import Settings, get_settings  # noqa: E402
from app.db import dispose_engine, get_engine, get_sessionmaker, init_engine  # noqa: E402
from app.models import Base, User  # noqa: E402
from app.telegram_auth import sign_init_data  # noqa: E402

ADMIN_ID = 1


class FakeBot:
    """Заглушка aiogram.Bot для сервисов и API: записывает вызовы."""

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self.star_balance = 1_000_000
        self.gifts = [
            SimpleNamespace(id="g15", star_count=15, total_count=None, is_premium=False),
            SimpleNamespace(id="g25", star_count=25, total_count=None, is_premium=False),
            SimpleNamespace(id="g50", star_count=50, total_count=None, is_premium=False),
            SimpleNamespace(id="g100", star_count=100, total_count=None, is_premium=False),
            SimpleNamespace(id="limited", star_count=10, total_count=1000, is_premium=False),
        ]
        self.fail_gift_after: int | None = None
        self.session = SimpleNamespace(close=self._noop)

    async def _noop(self):
        return None

    def _rec(self, name, **kw):
        self.calls.append((name, kw))

    def called(self, name):
        return [kw for n, kw in self.calls if n == name]

    async def me(self):
        return SimpleNamespace(id=999, username="cthulhu_test_bot")

    async def create_invoice_link(self, **kw):
        self._rec("create_invoice_link", **kw)
        return f"https://t.me/$invoice_{kw['payload']}"

    async def send_invoice(self, **kw):
        self._rec("send_invoice", **kw)

    async def send_message(self, chat_id, text, **kw):
        self._rec("send_message", chat_id=chat_id, text=text, **kw)

    async def refund_star_payment(self, **kw):
        self._rec("refund_star_payment", **kw)
        return True

    async def get_available_gifts(self):
        return SimpleNamespace(gifts=self.gifts)

    async def get_my_star_balance(self):
        return SimpleNamespace(amount=self.star_balance, nanostar_amount=0)

    async def send_gift(self, **kw):
        if self.fail_gift_after is not None and len(self.called("send_gift")) >= self.fail_gift_after:
            raise RuntimeError("gift limit")
        self._rec("send_gift", **kw)
        self.star_balance -= int(kw["gift_id"][1:])
        return True


@pytest.fixture(scope="session")
def settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()


@pytest.fixture(scope="session", autouse=True)
async def _schema(settings):
    init_engine(settings.database_url)
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await dispose_engine()


@pytest.fixture(autouse=True)
async def _clean():
    tables = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
    async with get_engine().begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
async def session():
    async with get_sessionmaker()() as s:
        yield s


@pytest.fixture
def bot() -> FakeBot:
    return FakeBot()


@pytest.fixture
def app(settings, bot):
    from app.main import create_app

    application = create_app(settings)
    application.state.bot = bot
    return application


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def init_data(user_id: int, *, start_param: str | None = None, auth_date: int | None = None,
              token: str | None = None) -> str:
    fields = {
        "auth_date": str(auth_date or int(time.time())),
        "query_id": "AAH",
        "user": json.dumps({"id": user_id, "first_name": f"U{user_id}", "username": f"user{user_id}",
                            "language_code": "ru"}, separators=(",", ":")),
    }
    if start_param:
        fields["start_param"] = start_param
    return sign_init_data(fields, token or os.environ["BOT_TOKEN"])


def auth(user_id: int, **kw) -> dict[str, str]:
    return {"Authorization": "tma " + init_data(user_id, **kw)}


async def make_user(session, user_id: int, balance: int = 0, **fields) -> User:
    from app.models import TxKind
    from app.services import wallet
    from app.services.users import TgUser, upsert_user

    await upsert_user(session, TgUser(id=user_id, first_name=f"U{user_id}"))
    for k, v in fields.items():
        await session.execute(text(f"UPDATE users SET {k} = :v WHERE id = :id"), {"v": v, "id": user_id})
    if balance:
        u = await wallet.lock_user(session, user_id, allow_banned=True)
        wallet.apply(session, u, TxKind.admin, balance, note="test")
    await session.commit()
    return await session.get(User, user_id, populate_existing=True)
