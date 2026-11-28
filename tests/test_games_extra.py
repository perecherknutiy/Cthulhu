"""Рулетка, слоты, Crash, ник и внутренний ID, рейтинг, ежедневный бонус."""
from __future__ import annotations

from decimal import Decimal
from fractions import Fraction

import pytest
from sqlalchemy import func, select

from app.fairness import FairRng
from app.games.crash import MAX_POINT, crash_point, elapsed_for, multiplier_at
from app.games.extra import RED, SLOT_LINES, SLOT_WEIGHTS, Roulette, Slots
from app.models import Bet, Transaction, User
from tests.conftest import auth, make_user

EDGE = Decimal("0.03")


@pytest.fixture(autouse=True)
def _no_rate_limit(app):
    from app.ratelimit import RateLimiter
    app.state.bet_limiter = RateLimiter(1e9)


async def ledger_ok(session, user_id):
    s = await session.scalar(select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.user_id == user_id))
    u = await session.get(User, user_id, populate_existing=True)
    assert s == u.balance
    return u


# ================================================================ roulette
def test_roulette_rules():
    g = Roulette(EDGE)
    assert len(RED) == 18 and 0 not in RED
    # RTP каждой ставки европейской рулетки = 36/37
    for bet, wins in (("red", 18), ("black", 18), ("even", 18), ("odd", 18), ("zero", 1), (17, 1)):
        p = g.parse_params({"bet": bet})
        assert Fraction(str(g.max_multiplier(p))) * Fraction(wins, 37) == Fraction(36, 37)
    for bad in (37, -1, "blue", True, None):
        with pytest.raises(Exception):
            g.parse_params({"bet": bad})


def test_roulette_outcomes_consistent():
    g = Roulette(EDGE)
    seen = set()
    for nonce in range(2000):
        for bet in ("red", "black", "even", "odd", "zero", 7):
            o = g.play(FairRng("s", "c", nonce), g.parse_params({"bet": bet}))
            n = o.result["number"]
            seen.add(n)
            expect = {"red": n in RED, "black": n != 0 and n not in RED, "even": n != 0 and n % 2 == 0,
                      "odd": n % 2 == 1, "zero": n == 0, 7: n == 7}[bet]
            assert (o.multiplier > 0) == expect
    assert seen == set(range(37))


# ================================================================ slots
def test_slots_rtp_exact():
    g = Slots(EDGE)
    rtp = sum(Fraction(w, 100) ** 3 * Fraction(str(p)) for w, p in zip(SLOT_WEIGHTS, g.pays))
    assert Fraction(9690, 10000) < rtp <= Fraction(97, 100), float(rtp)
    assert g.pays == sorted(g.pays) and len(SLOT_LINES) == 5


def test_slots_play():
    g = Slots(EDGE)
    total = Decimal(0)
    for nonce in range(3000):
        o = g.play(FairRng("s", "c", nonce), g.parse_params({"slot": "royal"}))
        grid = o.result["grid"]
        assert len(grid) == 9 and all(0 <= x < 6 for x in grid)
        expected = sum((g.pays[grid[a]] for a, b, c in SLOT_LINES if grid[a] == grid[b] == grid[c]), Decimal(0)) / 5
        assert o.multiplier == expected.quantize(Decimal("0.0001"), rounding="ROUND_DOWN")
        total += o.multiplier
    assert Decimal("0.8") < total / 3000 < Decimal("1.15")  # грубая проверка; точная — выше
    with pytest.raises(Exception):
        g.parse_params({"slot": "fruits"})


async def test_slots_api_verify_and_cap(client, session, app):
    await make_user(session, 700, balance=100_000)
    h = auth(700)
    r = await client.post("/api/games/slots/play", json={"amount": 50, "params": {"slot": "classic"}}, headers=h)
    assert r.status_code == 200, r.text
    bet = r.json()["bet"]
    rot = (await client.post("/api/fair/rotate", json={}, headers=h)).json()
    v = (await client.post("/api/fair/verify", json={"game": "slots", "server_seed": rot["previous_server_seed"],
                                                     "client_seed": bet["client_seed"], "nonce": 0,
                                                     "params": bet["params"]})).json()
    assert v["grid"] == bet["result"]["grid"] and v["multiplier"] == bet["multiplier"]

    # огромная ставка не отклоняется заранее, но выигрыш режется лимитом
    games = app.state.games
    old = games.s.max_payout
    games.s.max_payout = 60
    try:
        for _ in range(60):
            r = (await client.post("/api/games/slots/play", json={"amount": 100, "params": {"slot": "treasury"}},
                                   headers=h)).json()
            assert "bet" in r, r
            assert r["bet"]["payout"] <= 60
    finally:
        games.s.max_payout = old
    await ledger_ok(session, 700)


# ================================================================ crash
def test_crash_point_distribution():
    rtp = Decimal("0.97")
    pts = [crash_point(FairRng("s", "c", n), rtp) for n in range(20000)]
    assert all(Decimal(1) <= p <= MAX_POINT for p in pts)
    for m in (Decimal(2), Decimal(10)):
        share = sum(p >= m for p in pts) / len(pts)
        assert abs(share - float(rtp / m)) < 0.015, (m, share)
    assert multiplier_at(0) == Decimal(1)
    assert multiplier_at(elapsed_for(Decimal("2.5")) + 1e-9) == Decimal("2.5")


class Clock:
    def __init__(self, t: float = 1_000_000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def clock(app):
    c = Clock()
    app.state.games.clock = c
    return c


async def _point(session, user_id) -> Decimal:
    bet = await session.scalar(select(Bet).where(Bet.user_id == user_id, Bet.game == "crash").order_by(Bet.id.desc()))
    await session.refresh(bet)
    return Decimal(bet.state["point"])


async def _start_until(client, session, h, user_id, cond, params=None):
    """Играем раундами (проигрывая их), пока точка краха не удовлетворит cond. Детерминированно для теста."""
    for _ in range(200):
        r = await client.post("/api/games/crash/start", json={"amount": 10, "params": params or {}}, headers=h)
        assert r.status_code == 200, r.text
        if r.json()["result"]["status"] != "active":
            continue
        p = await _point(session, user_id)
        if cond(p):
            return r.json(), p
        # не подходит — ждём краха (время вперёд), раунд досчитается лениво
        client.clock.t += elapsed_for(p) + 0.01
    raise AssertionError("не нашли подходящую точку")


async def test_crash_manual_cashout(client, session, clock):
    client.clock = clock
    await make_user(session, 710, balance=100_000)
    h = auth(710)
    data, p = await _start_until(client, session, h, 710, lambda p: p >= 3)
    active = data["result"]
    assert "crash_point" not in active and active["multiplier"] == 1.0, "точка краха не должна утекать"
    assert (await client.post("/api/games/crash/start", json={"amount": 10}, headers=h)).json()["error"]["code"] \
        == "active_game"
    assert (await client.post("/api/fair/rotate", json={}, headers=h)).json()["error"]["code"] == "active_game"

    clock.t += elapsed_for(Decimal(2)) + 1e-6
    view = (await client.get("/api/games/crash/active", headers=h)).json()["game"]
    assert view["multiplier"] == 2.0
    r = (await client.post("/api/games/crash/cashout", headers=h)).json()
    assert r["result"]["status"] == "won" and r["result"]["cashout"] == "manual"
    assert r["bet"]["multiplier"] == 2.0 and r["bet"]["payout"] == 20
    assert r["result"]["crash_point"] == float(p), "после раунда точку показываем"
    assert (await client.get("/api/games/crash/active", headers=h)).json()["game"] is None
    await ledger_ok(session, 710)


async def test_crash_too_late_and_lazy_settlement(client, session, clock):
    client.clock = clock
    await make_user(session, 711, balance=100_000)
    h = auth(711)
    _, p = await _start_until(client, session, h, 711, lambda p: 1.2 < p < 5)
    clock.t += elapsed_for(p) + 0.001
    r = (await client.post("/api/games/crash/cashout", headers=h)).json()
    assert r["result"]["status"] == "lost" and r["bet"]["payout"] == 0

    # раунд, который никто не досчитал, попадает в историю при её запросе
    _, p = await _start_until(client, session, h, 711, lambda p: p < 50)
    clock.t += elapsed_for(p) + 1
    hist = (await client.get("/api/bets?game=crash", headers=h)).json()
    assert hist[0]["status"] == "lost" and hist[0]["result"]["crash_point"] == float(p)
    # и сид после этого можно раскрыть
    assert (await client.post("/api/fair/rotate", json={}, headers=h)).status_code == 200
    await ledger_ok(session, 711)


async def test_crash_auto_cashout(client, session, clock):
    client.clock = clock
    await make_user(session, 712, balance=100_000)
    h = auth(712)
    _, p = await _start_until(client, session, h, 712, lambda p: p >= Decimal("1.5"), {"auto_cashout": 1.5})
    clock.t += elapsed_for(Decimal("1.5")) + 0.001
    assert (await client.get("/api/games/crash/active", headers=h)).json()["game"] is None
    last = (await client.get("/api/bets?game=crash&limit=1", headers=h)).json()[0]
    assert last["status"] == "won" and last["multiplier"] == 1.5 and last["payout"] == 15
    assert last["result"]["cashout"] == "auto"
    # ручной вывод «после» авто-вывода не даёт больше
    _, p = await _start_until(client, session, h, 712, lambda p: p >= 4, {"auto_cashout": 1.5})
    clock.t += elapsed_for(Decimal(3))
    r = (await client.post("/api/games/crash/cashout", headers=h)).json()
    assert r["bet"]["multiplier"] == 1.5 and r["result"]["cashout"] == "auto"
    bad = await client.post("/api/games/crash/start", json={"amount": 10, "params": {"auto_cashout": 1}}, headers=h)
    assert bad.status_code == 400
    await ledger_ok(session, 712)


async def test_crash_cap_by_max_payout(client, session, clock, app):
    client.clock = clock
    await make_user(session, 713, balance=1_000_000)
    h = auth(713)
    amount = 10_000  # max_payout 500 000 → потолок 50×
    r = (await client.post("/api/games/crash/start", json={"amount": amount}, headers=h)).json()
    res = r["result"]
    if res["status"] == "active":
        assert res["max_multiplier"] == 50.0 and res["auto_target"] == 50.0
        clock.t += elapsed_for(Decimal(1000)) + 1
        await client.get("/api/games/crash/active", headers=h)
    last = (await client.get("/api/bets?game=crash&limit=1", headers=h)).json()[0]
    assert last["payout"] <= 500_000


async def test_crash_verify(client, session, clock):
    client.clock = clock
    await make_user(session, 714, balance=1000)
    h = auth(714)
    r = (await client.post("/api/games/crash/start", json={"amount": 10}, headers=h)).json()
    p = await _point(session, 714)
    clock.t += elapsed_for(p) + 1
    rot = (await client.post("/api/fair/rotate", json={}, headers=h)).json()
    v = (await client.post("/api/fair/verify", json={"game": "crash", "server_seed": rot["previous_server_seed"],
                                                     "client_seed": r["bet"]["client_seed"], "nonce": 0})).json()
    assert v["crash_point"] == float(p)


# ================================================================ profile: public id, nickname, referral
async def test_nickname(client, session):
    h1, h2 = auth(720), auth(721)
    me = (await client.get("/api/me", headers=h1)).json()
    assert me["nickname"] is None and me["public_id"] >= 100001 and me["vip"]["key"] == "bronze"
    r = await client.post("/api/me/nickname", json={"nickname": "  Golden   Fox "}, headers=h1)
    assert r.status_code == 200 and r.json()["nickname"] == "Golden Fox"
    await client.get("/api/me", headers=h2)
    r = await client.post("/api/me/nickname", json={"nickname": "golden fox"}, headers=h2)
    assert r.json()["error"]["code"] == "nickname_taken"
    for bad, code in (("ab", "bad_nickname"), ("x" * 21, "bad_nickname"), ("<script>", "bad_nickname"),
                      ("ARA Casino", "nickname_reserved"), ("ara", "nickname_reserved"), ("Super_Admin", "nickname_reserved"),
                      ("Под-держка", "nickname_reserved")):
        r = await client.post("/api/me/nickname", json={"nickname": bad}, headers=h2)
        assert r.json()["error"]["code"] == code, bad
    # свой ник можно сменить на тот же в другом регистре
    r = await client.post("/api/me/nickname", json={"nickname": "GOLDEN FOX"}, headers=h1)
    assert r.json()["nickname"] == "GOLDEN FOX"


async def test_referral_by_public_id(client, session):
    ref = (await client.get("/api/me", headers=auth(730))).json()
    await client.get("/api/me", headers=auth(731, start_param=f"ref_{ref['public_id']}"))
    await client.get("/api/me", headers=auth(732, start_param="ref_730"))  # старые ссылки с Telegram ID
    assert (await client.get("/api/me", headers=auth(730))).json()["referral"]["invited"] == 2


async def test_vip_levels(client, session):
    await make_user(session, 740, total_wagered=1_200_000_000)  # 1 200 USDT
    vip = (await client.get("/api/me", headers=auth(740))).json()["vip"]
    assert vip["key"] == "gold" and vip["next_key"] == "sapphire" and vip["next_min"] == 5_000_000_000
    cfg = (await client.get("/api/config", headers=auth(740))).json()
    assert [v["key"] for v in cfg["vip_levels"]] == ["bronze", "silver", "gold", "sapphire", "diamond"]


# ================================================================ leaderboard
async def test_leaderboard(client, session):
    for uid, n in ((750, 3), (751, 1), (752, 2)):
        await make_user(session, uid, balance=10_000)
        for _ in range(n):
            r = await client.post("/api/games/coinflip/play", json={"amount": 100, "params": {"side": "heads"}},
                                  headers=auth(uid))
            assert r.status_code == 200
    await client.post("/api/me/nickname", json={"nickname": "Leader"}, headers=auth(750))
    lb = (await client.get("/api/leaderboard", headers=auth(752))).json()
    assert [e["wagered"] for e in lb["top"]] == [300, 200, 100]
    assert lb["top"][0]["nickname"] == "Leader" and lb["top"][1]["nickname"].startswith("Player ")
    assert "id" not in lb["top"][0], "Telegram ID в рейтинге не светим"
    assert lb["me"]["rank"] == 2
    assert (await client.get("/api/leaderboard?period=all", headers=auth(753))).json()["me"] is None
    assert (await client.get("/api/leaderboard?period=year", headers=auth(753))).status_code == 422


# ================================================================ daily bonus
async def test_daily_bonus(client, session, app):
    h = auth(760)
    me = (await client.get("/api/me", headers=h)).json()
    assert me["bonus"] == {"enabled": False}
    assert (await client.post("/api/bonus/claim", headers=h)).json()["error"]["code"] == "bonus_disabled"

    s = app.state.settings if hasattr(app.state, "settings") else None
    from app.config import get_settings
    settings = s or get_settings()
    settings.daily_bonus = 25
    try:
        assert (await client.get("/api/me", headers=h)).json()["bonus"]["available"] is True
        r = (await client.post("/api/bonus/claim", headers=h)).json()
        assert r["balance"] == 25 and r["bonus"]["available"] is False and r["bonus"]["next_at"]
        assert (await client.post("/api/bonus/claim", headers=h)).json()["error"]["code"] == "bonus_claimed"
        me = (await client.get("/api/me", headers=h)).json()
        assert me["total_bonus"] == 25 and me["wager_left"] == 25, "бонус нужно отыграть перед выводом"
    finally:
        settings.daily_bonus = 0
    await ledger_ok(session, 760)
