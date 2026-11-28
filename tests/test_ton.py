"""USDT в сети TON: суммы, адреса, разбор переводов, сторож пополнений, клиент toncenter."""
from __future__ import annotations

import base64

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from pytoniq_core import Address, begin_cell
from sqlalchemy import func, select

from app.config import Settings
from app.db import get_sessionmaker
from app.errors import AppError
from app.models import KV, DepositStatus, TonDeposit, Transaction, User
from app.money import fmt, to_units, usdt
from app.ton import address
from app.ton.cells import parse_transfer_notification
from app.ton.toncenter import Toncenter
from app.ton.watcher import CURSOR_KEY, DepositWatcher
from tests.conftest import make_user

CASINO = "0:" + "11" * 32
JETTON_WALLET = "0:" + "22" * 32  # настоящий USDT-кошелёк казино (в тестах задан в TON_USDT_JETTON_WALLET)
FAKE_JETTON_WALLET = "0:" + "66" * 32
PLAYER = "0:" + "33" * 32


# ---------------------------------------------------------------- суммы
def test_units_and_format():
    assert to_units("0.1") == 100_000 and to_units(25) == 25_000_000 and to_units("1,5") == 1_500_000
    with pytest.raises(ValueError):
        to_units("0.0000001")
    assert fmt(12_500_000) == "12.50" and fmt(198_000) == "0.198" and fmt(0) == "0.00"
    assert fmt(1_234_567_000_000) == "1 234 567.00" and fmt(-1_000_000) == "−1.00" and fmt(5, sign=True) == "+0.000005"
    assert usdt(2_000_000) == "2.00 USDT"


def test_default_limits_in_usdt():
    s = Settings(_env_file=None, bot_token="1:x", min_bet="0.1", max_bet="1000", max_payout="10000",
                 withdraw_min="5", withdraw_max="5000", min_deposit="1", deposit_presets="5,10,25")
    assert s.min_bet == 100_000 and s.max_payout == 10_000 * 10**6 and s.deposit_presets == [5 * 10**6, 10**7, 25 * 10**6]
    fresh = Settings.model_fields
    assert fresh["min_bet"].default == "0.1" and fresh["withdraw_min"].default == "5"


# ---------------------------------------------------------------- адреса
def test_addresses():
    friendly = "UQAzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzM-lI"
    assert address.raw(address.parse(friendly)) == PLAYER
    assert address.friendly(PLAYER) == friendly
    assert address.same("0:" + "33" * 32, friendly) and address.same(PLAYER.upper(), friendly)
    assert not address.same(PLAYER, CASINO) and not address.same(None, PLAYER) and not address.same("junk", PLAYER)
    testnet = Address(PLAYER).to_str(is_test_only=True)
    for bad in ("", "abc", friendly[:-1] + "A", testnet, "Ef8zMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzM0vF"):
        with pytest.raises(AppError):
            address.parse(bad)


def test_transfer_link():
    link = address.jetton_transfer_link("UQabc", "EQmaster", 1_500_000, "ARA Casino #7")
    assert link == "ton://transfer/UQabc?jetton=EQmaster&amount=1500000&text=ARA%20Casino%20%237"


# ---------------------------------------------------------------- transfer_notification
def notification(amount: int, comment: str | None, *, in_ref: bool = False, op: int = 0x7362D09C,
                 sender: str = PLAYER) -> str:
    b = begin_cell().store_uint(op, 32).store_uint(42, 64).store_coins(amount).store_address(Address(sender))
    if comment is None:
        b = b.store_bit(0)
    else:
        payload = begin_cell().store_uint(0, 32).store_snake_string(comment).end_cell()
        b = b.store_bit(1).store_ref(payload) if in_ref else b.store_bit(0).store_cell(payload)
    return base64.b64encode(b.end_cell().to_boc()).decode()


def test_parse_notification():
    n = parse_transfer_notification(notification(2_500_000, "100042"))
    assert (n.amount, n.comment, n.sender, n.query_id) == (2_500_000, "100042", PLAYER, 42)
    assert parse_transfer_notification(notification(1, "ID 100043", in_ref=True)).comment == "ID 100043"
    long = "x" * 200 + " 100044"  # длинный комментарий переносится в следующие ячейки
    assert parse_transfer_notification(notification(1, long, in_ref=True)).comment == long
    assert parse_transfer_notification(notification(7, None)).comment is None
    assert parse_transfer_notification(notification(7, "hi", op=0x0F8A7EA5)) is None  # не уведомление
    assert parse_transfer_notification("bm90IGEgYm9j") is None and parse_transfer_notification(None) is None


# ---------------------------------------------------------------- сторож пополнений
class FakeToncenter:
    def __init__(self):
        self.txs: list[dict] = []
        self.calls = 0

    def add(self, lt: int, *, source=JETTON_WALLET, amount=1_000_000, comment=None, body=None, h=None):
        self.txs.append({"hash": h or f"h{lt}", "lt": str(lt), "now": 1, "description": {"aborted": False},
                         "in_msg": {"source": source.upper(), "destination": CASINO.upper(),
                                    "message_content": {"body": body or notification(amount, comment)}}})

    async def transactions(self, account, *, start_lt=None, limit=100, sort="asc"):
        self.calls += 1
        assert address.same(account, CASINO) and sort == "asc"
        return [t for t in sorted(self.txs, key=lambda t: int(t["lt"])) if int(t["lt"]) >= (start_lt or 0)][:limit]

    async def latest_lt(self, account):
        return max((int(t["lt"]) for t in self.txs), default=0)

    async def jetton_wallet_address(self, master, owner):  # pragma: no cover — в тестах адрес задан настройкой
        return JETTON_WALLET


async def balance(user_id):
    async with get_sessionmaker()() as s:
        u = await s.get(User, user_id)
        ledger = await s.scalar(select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.user_id == user_id))
        assert ledger == u.balance
        return u.balance


async def test_watcher_credits_only_real_usdt(settings, session):
    u = await make_user(session, 800)
    ton = FakeToncenter()
    ton.add(100, comment=str(u.public_id))  # история до запуска — не трогаем
    notified = []

    async def notify(dep, user):
        notified.append((dep.amount, user.id if user else None))

    w = DepositWatcher(settings, get_sessionmaker(), ton, notify)
    assert w.jetton_wallet_raw == JETTON_WALLET
    assert await w.tick() == 0 and await balance(800) == 0  # первый запуск: только запомнили позицию

    ton.add(101, amount=2_000_000, comment=str(u.public_id))
    ton.add(102, amount=9_000_000, comment=str(u.public_id), source=FAKE_JETTON_WALLET)  # поддельный «USDT»
    ton.add(103, amount=3_000_000, comment="привет")  # без ID
    ton.add(104, amount=500_000, comment=f"ID {u.public_id}", body=None)
    ton.txs.append({"hash": "h105", "lt": "105", "in_msg": None})  # внешнее сообщение (исходящий перевод админа)
    assert await w.tick() == 3
    assert await balance(800) == 2_500_000
    assert notified == [(2_000_000, 800), (3_000_000, None), (500_000, 800)]

    async with get_sessionmaker()() as s:
        assert await s.scalar(select(KV.value).where(KV.key == CURSOR_KEY)) == "105"
        statuses = dict((await s.execute(select(TonDeposit.tx_hash, TonDeposit.status))).all())
    assert statuses == {"h101": DepositStatus.credited, "h103": DepositStatus.unmatched, "h104": DepositStatus.credited}

    # повторная обработка той же истории (сбросили позицию) ничего не начисляет второй раз
    async with get_sessionmaker()() as s:
        await w._save_cursor(s, 100)
    assert await w.tick() == 0 and await balance(800) == 2_500_000


async def test_watcher_pages_through_many(settings, session):
    u = await make_user(session, 801)
    ton = FakeToncenter()
    w = DepositWatcher(settings, get_sessionmaker(), ton)
    await w.tick()
    for lt in range(1, 251):
        ton.add(lt, amount=1, comment=str(u.public_id))
    assert await w.tick() == 250 and await balance(801) == 250
    assert ton.calls >= 3


# ---------------------------------------------------------------- клиент toncenter (локальный сервер вместо сети)
async def test_toncenter_client():
    seen = {}

    async def transactions(request):
        seen["tx"] = dict(request.query)
        seen["key"] = request.headers.get("X-API-Key")
        return web.json_response({"transactions": [{"hash": "h", "lt": "9"}], "address_book": {}})

    async def run_get_v2(request):
        body = await request.json()
        seen["v2"] = body
        cell = begin_cell().store_address(Address(JETTON_WALLET)).end_cell()
        if seen.get("v2_fail"):
            return web.json_response({"ok": False, "error": "boom"}, status=500)
        return web.json_response({"ok": True, "result": {"exit_code": 0, "stack": [
            ["cell", {"bytes": base64.b64encode(cell.to_boc()).decode(), "object": {}}]]}})

    async def run_get_v3(request):
        cell = begin_cell().store_address(Address(JETTON_WALLET)).end_cell()
        return web.json_response({"exit_code": 0, "stack": [{"type": "slice",
                                                             "value": base64.b64encode(cell.to_boc()).decode()}]})

    app = web.Application()
    app.router.add_get("/api/v3/transactions", transactions)
    app.router.add_post("/api/v2/runGetMethod", run_get_v2)
    app.router.add_post("/api/v3/runGetMethod", run_get_v3)
    server = TestServer(app)
    await server.start_server()
    try:
        client = Toncenter(str(server.make_url("/")), api_key="KEY")
        txs = await client.transactions(CASINO, start_lt=5, limit=100)
        assert txs[0]["lt"] == "9" and seen["key"] == "KEY"
        assert seen["tx"] == {"account": CASINO, "start_lt": "5", "limit": "100", "sort": "asc"}
        assert await client.latest_lt(CASINO) == 9

        jw = await client.jetton_wallet_address("EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs", CASINO)
        assert jw == JETTON_WALLET
        assert seen["v2"]["method"] == "get_wallet_address" and seen["v2"]["stack"][0][0] == "tvm.Slice"
        seen["v2_fail"] = True  # v2 недоступен — берём v3
        assert await client.jetton_wallet_address("EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs", CASINO) == JETTON_WALLET
        await client.close()
    finally:
        await server.close()
