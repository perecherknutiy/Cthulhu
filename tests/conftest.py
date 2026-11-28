"""Тесты гоняются на настоящем PostgreSQL (нужны FOR UPDATE, частичные индексы, ON CONFLICT).

TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/casino_test pytest
"""
from __future__ import annotations

import json
import os
import time
from types import SimpleNamespace

os.environ["ENV_FILE"] = ""  # тесты не читают .env с боевым токеном
os.environ.setdefault("BOT_TOKEN", "123456:TEST-TOKEN")
os.environ["BOT_MODE"] = "none"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/casino_test")
os.environ.setdefault("ADMIN_IDS", "1")
# Суммы в тестах — целые микро-USDT. Лимиты маленькие, чтобы тесты игр работали с «круглыми» числами
# (ставка 10 = 0.00001 USDT): математика от масштаба не зависит. Настоящие значения по умолчанию — в test_ton.py.
for _k, _v in {"MIN_BET": "0.00001", "MAX_BET": "0.01", "MAX_PAYOUT": "0.5", "MIN_DEPOSIT": "0.00005",
               "WITHDRAW_MIN": "0.0001", "WITHDRAW_MAX": "0.1"}.items():
    os.environ[_k] = _v
os.environ["TON_WALLET_ADDRESS"] = "UQAREREREREREREREREREREREREREREREREREREREREREbvW"  # 0:1111…
os.environ["TON_USDT_JETTON_WALLET"] = "0:" + "22" * 32
os.environ["DEPOSIT_WATCHER"] = "false"

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
        self.session = SimpleNamespace(close=self._noop)

    async def _noop(self):
        return None

    def _rec(self, name, **kw):
        self.calls.append((name, kw))

    def called(self, name):
        return [kw for n, kw in self.calls if n == name]

    async def me(self):
        return SimpleNamespace(id=999, username="ara_test_bot")

    async def send_message(self, chat_id, text, **kw):
        self._rec("send_message", chat_id=chat_id, text=text, **kw)


@pytest.fixture(scope="session")
def settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()


@pytest.fixture(scope="session", autouse=True)
async def _schema(settings):
    init_engine(settings.database_url)
    async with get_engine().begin() as conn:
        # с нуля: в тестовой базе могли остаться таблицы от старых версий схемы
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
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
