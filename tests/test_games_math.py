"""Математика игр: RTP не выше заявленного и близок к нему."""
from decimal import Decimal
from fractions import Fraction
from math import comb

import pytest

from app.errors import AppError
from app.fairness import FairRng
from app.games import get_instant_games, get_mines
from app.games.instant import DiceParams, LimboParams, PlinkoParams

EDGE = Decimal("0.03")
RTP = Decimal(1) - EDGE
G = get_instant_games(EDGE)


def rng(n):
    return FairRng("server-seed-for-tests", "client", n)


@pytest.mark.parametrize("target", ["1.00", "2.50", "49.50", "50", "75.25", "98"])
@pytest.mark.parametrize("direction", ["under", "over"])
def test_dice_rtp_analytic(target, direction):
    dice = G["dice"]
    p = DiceParams(target=Decimal(target), direction=direction)
    try:
        chance = dice.chance(p)
    except AppError:
        pytest.skip("out of range")
    ev = chance * dice.multiplier(p)
    assert RTP - Decimal("0.001") <= ev <= RTP


def test_dice_chance_bounds():
    with pytest.raises(AppError):
        G["dice"].chance(DiceParams(target=Decimal("99"), direction="under"))
    with pytest.raises(AppError):
        G["dice"].chance(DiceParams(target=Decimal("1"), direction="over"))


def test_dice_win_rate_simulation():
    dice, p = G["dice"], DiceParams(target=Decimal("30"), direction="under")
    wins = sum(dice.play(rng(i), p).won for i in range(40_000))
    assert abs(wins / 40_000 - 0.30) < 0.01


def test_coinflip():
    cf = G["coinflip"]
    p = cf.parse_params({"side": "heads"})
    assert cf.max_multiplier(p) == Decimal("1.94")
    wins = sum(cf.play(rng(i), p).won for i in range(40_000))
    assert abs(wins / 40_000 - 0.5) < 0.01


@pytest.mark.parametrize("target", ["1.01", "2", "10", "100"])
def test_limbo_win_rate(target):
    limbo, p = G["limbo"], LimboParams(target=Decimal(target))
    n = 60_000
    wins = sum(limbo.play(rng(i), p).won for i in range(n))
    expected = float(RTP / Decimal(target))
    tol = 4 * (expected * (1 - expected) / n) ** 0.5 + 1e-3
    assert abs(wins / n - expected) < tol


def test_limbo_point_at_least_one():
    limbo, p = G["limbo"], LimboParams(target=Decimal("2"))
    assert all(limbo.play(rng(i), p).result["point"] >= 1 for i in range(2000))


@pytest.mark.parametrize("risk", ["low", "medium", "high"])
@pytest.mark.parametrize("rows", range(8, 17))
def test_plinko_rtp(risk, rows):
    table = G["plinko"].table(PlinkoParams(rows=rows, risk=risk))
    assert len(table) == rows + 1
    assert table == table[::-1], "таблица должна быть симметричной"
    ev = sum(Fraction(m) * Fraction(comb(rows, k), 2**rows) for k, m in enumerate(table))
    assert Fraction(RTP) - Fraction(1, 100) <= ev <= Fraction(RTP)


def test_plinko_play_matches_path():
    pl, p = G["plinko"], PlinkoParams(rows=12, risk="high")
    for i in range(500):
        o = pl.play(rng(i), p)
        assert o.result["bucket"] == sum(o.result["path"])
        assert o.multiplier == pl.table(p)[o.result["bucket"]]


@pytest.mark.parametrize("mines", [1, 3, 5, 10, 24])
def test_mines_multiplier_rtp(mines):
    m = get_mines(EDGE)
    for k in range(1, 25 - mines + 1):
        prob = Fraction(1)
        for i in range(k):
            prob *= Fraction(25 - mines - i, 25 - i)
        ev = Fraction(m.multiplier(mines, k)) * prob
        assert ev <= Fraction(RTP)
        assert ev >= Fraction(RTP) * Fraction(9999, 10000) - Fraction(1, 10000)


def test_mines_state_deterministic():
    m = get_mines(EDGE)
    from app.games.mines import MinesParams

    a = m.new_state(rng(3), MinesParams(mines=5))
    b = m.new_state(rng(3), MinesParams(mines=5))
    assert a == b and len(set(a["mines"])) == 5
