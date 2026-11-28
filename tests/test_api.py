"""Сквозной сценарий через HTTP API мини-приложения."""
import pytest

from tests.conftest import ADMIN_ID, auth, make_user


async def test_unauthorized(client):
    r = await client.get("/api/me")
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthorized"
    r = await client.get("/api/me", headers={"Authorization": "tma user=1&hash=deadbeef&auth_date=1"})
    assert r.status_code == 401


async def test_health_and_static(client):
    assert (await client.get("/health")).json() == {"ok": True}
    r = await client.get("/")
    assert r.status_code == 200 and "telegram-web-app.js" in r.text


async def test_me_registers_with_referrer(client, session):
    await make_user(session, 500)
    r = await client.get("/api/me", headers=auth(501, start_param="ref_500"))
    assert r.status_code == 200
    me = r.json()
    assert me["id"] == 501 and me["balance"] == 0
    assert me["referral"]["link"] == f"https://t.me/ara_test_bot?startapp=ref_{me['public_id']}"
    r = await client.get("/api/me", headers=auth(500))
    assert r.json()["referral"]["invited"] == 1


async def test_self_referral_ignored(client):
    r = await client.get("/api/me", headers=auth(502, start_param="ref_502"))
    assert r.status_code == 200
    r = await client.get("/api/me", headers=auth(502))
    assert r.json()["referral"]["invited"] == 0


async def test_config(client):
    cfg = (await client.get("/api/config", headers=auth(1))).json()
    names = {g["name"] for g in cfg["games"]}
    assert names == {"dice", "coinflip", "limbo", "plinko", "roulette", "slots", "mines", "crash"}
    assert cfg["bot_username"] == "ara_test_bot"
    assert cfg["currency"] == {"code": "USDT", "decimals": 6, "network": "TON"}
    assert cfg["deposit"]["enabled"] and cfg["withdraw"]["method"] == "ton"


async def test_deposit_endpoint(client):
    me = (await client.get("/api/me", headers=auth(510))).json()
    d = (await client.get("/api/wallet/deposit", headers=auth(510))).json()
    assert d["enabled"] and d["memo"] == str(me["public_id"]) and d["token"] == "USDT" and d["network"] == "TON"
    assert d["address"] == "UQAREREREREREREREREREREREREREREREREREREREREREbvW"
    assert d["links"]["ton"].startswith("ton://transfer/")


@pytest.mark.parametrize("game,params", [
    ("dice", {"target": 50, "direction": "under"}),
    ("dice", {"target": 50, "direction": "over"}),
    ("coinflip", {"side": "tails"}),
    ("limbo", {"target": 2}),
    ("plinko", {"rows": 16, "risk": "high"}),
])
async def test_play_and_verify(client, session, game, params):
    await make_user(session, 520, balance=1000)
    h = auth(520)
    fair = (await client.get("/api/fair", headers=h)).json()

    r = await client.post(f"/api/games/{game}/play", json={"amount": 10, "params": params}, headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    bet = data["bet"]
    assert data["balance"] == 1000 - 10 + bet["payout"]
    assert bet["server_seed_hash"] == fair["server_seed_hash"] and bet["server_seed"] is None
    assert bet["nonce"] == 0

    # раскрываем сид и проверяем ставку публичным эндпоинтом
    rot = (await client.post("/api/fair/rotate", json={"client_seed": "my-seed"}, headers=h)).json()
    assert rot["previous_server_seed_hash"] == fair["server_seed_hash"] and rot["previous_nonce"] == 1
    assert rot["current"]["client_seed"] == "my-seed" and rot["current"]["nonce"] == 0
    v = (await client.post("/api/fair/verify", json={
        "game": game, "server_seed": rot["previous_server_seed"], "client_seed": bet["client_seed"],
        "nonce": bet["nonce"], "params": bet["params"],
    })).json()
    assert v["server_seed_hash"] == fair["server_seed_hash"]
    assert v["multiplier"] == bet["multiplier"]

    hist = (await client.get("/api/bets", headers=h)).json()
    assert hist[0]["id"] == bet["id"] and hist[0]["server_seed"] == rot["previous_server_seed"]
    txs = (await client.get("/api/wallet/transactions", headers=h)).json()
    assert sum(t["amount"] for t in txs) == data["balance"]


async def test_play_errors(client, session):
    h = auth(530)
    r = await client.post("/api/games/dice/play", json={"amount": 10, "params": {"target": 50}}, headers=h)
    assert r.status_code == 400 and r.json()["error"]["code"] == "insufficient_funds"
    r = await client.post("/api/games/nope/play", json={"amount": 10}, headers=h)
    assert r.status_code == 404
    r = await client.post("/api/games/dice/play", json={"amount": -5}, headers=h)
    assert r.status_code == 422


async def test_mines_flow(client, session):
    await make_user(session, 540, balance=1000)
    h = auth(540)
    r = await client.post("/api/games/mines/start", json={"amount": 100, "params": {"mines": 3}}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["balance"] == 900
    game = r.json()["result"]
    assert game["status"] == "active" and "mines" not in game, "позиции мин не должны утекать"

    r = await client.post("/api/games/mines/start", json={"amount": 100, "params": {"mines": 3}}, headers=h)
    assert r.json()["error"]["code"] == "active_game"
    r = await client.post("/api/fair/rotate", json={}, headers=h)
    assert r.json()["error"]["code"] == "active_game", "нельзя раскрыть сид во время игры"
    r = await client.post("/api/games/mines/cashout", headers=h)
    assert r.json()["error"]["code"] == "nothing_revealed"

    # узнаём безопасные клетки «читерски» через БД — только чтобы сценарий был детерминированным
    from sqlalchemy import select

    from app.models import Bet
    bet = await session.scalar(select(Bet).where(Bet.user_id == 540))
    safe = [t for t in range(25) if t not in bet.state["mines"]]

    for i, tile in enumerate(safe[:2], start=1):
        r = (await client.post("/api/games/mines/reveal", json={"tile": tile}, headers=h)).json()
        assert r["result"]["status"] == "active" and len(r["result"]["revealed"]) == i
    r = await client.post("/api/games/mines/reveal", json={"tile": safe[0]}, headers=h)
    assert r.json()["error"]["code"] == "already_revealed"

    active = (await client.get("/api/games/mines/active", headers=h)).json()["game"]
    assert active["multiplier"] > 1

    r = (await client.post("/api/games/mines/cashout", headers=h)).json()
    assert r["result"]["status"] == "won" and sorted(r["result"]["mines"]) == sorted(bet.state["mines"])
    expected = int(100 * active["multiplier"])
    assert r["bet"]["payout"] == expected and r["balance"] == 900 + expected
    assert (await client.get("/api/games/mines/active", headers=h)).json()["game"] is None


async def test_mines_lose(client, session):
    await make_user(session, 541, balance=1000)
    h = auth(541)
    await client.post("/api/games/mines/start", json={"amount": 100, "params": {"mines": 24}}, headers=h)
    from sqlalchemy import select

    from app.models import Bet
    bet = await session.scalar(select(Bet).where(Bet.user_id == 541))
    r = (await client.post("/api/games/mines/reveal", json={"tile": bet.state["mines"][0]}, headers=h)).json()
    assert r["result"]["status"] == "lost" and r["balance"] == 900 and r["bet"]["payout"] == 0


async def test_withdraw_notifies_admin(client, session, bot):
    await make_user(session, 550, balance=1000)
    r = await client.post("/api/wallet/withdraw", json={"amount": 300}, headers=auth(550))
    assert r.status_code == 422  # без адреса нельзя
    r = await client.post("/api/wallet/withdraw", json={"amount": 300, "address": "nope"}, headers=auth(550))
    assert r.json()["error"]["code"] == "bad_address"
    r = await client.post("/api/wallet/withdraw", json={"amount": 300, "address": "0:" + "44" * 32}, headers=auth(550))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "pending" and r.json()["address"].startswith("UQ")
    msgs = bot.called("send_message")
    assert msgs and msgs[0]["chat_id"] == ADMIN_ID and "#1" in msgs[0]["text"]
    kb = msgs[0]["reply_markup"].inline_keyboard
    assert kb[0][0].url.startswith("https://app.tonkeeper.com/transfer/" + r.json()["address"])
    assert "amount=300" in kb[0][0].url and kb[1][0].callback_data == "wd:ok:1"
    lst = (await client.get("/api/wallet/withdrawals", headers=auth(550))).json()
    assert lst[0]["amount"] == 300


async def test_rate_limit(client, session):
    await make_user(session, 560, balance=10_000)
    h = auth(560)
    codes = []
    for _ in range(20):
        r = await client.post("/api/games/coinflip/play", json={"amount": 10, "params": {"side": "heads"}}, headers=h)
        codes.append(r.status_code)
    assert 429 in codes and codes[0] == 200


async def test_banned_user(client, session):
    await make_user(session, 570, balance=100, is_banned=True)
    r = await client.get("/api/fair", headers=auth(570))
    assert r.status_code == 403
