"""Мгновенные игры: dice, coinflip, limbo, plinko."""
from __future__ import annotations

from decimal import Decimal
from fractions import Fraction
from functools import cached_property
from math import comb
from typing import Literal

from pydantic import BaseModel, Field

from app.errors import AppError
from app.fairness import FairRng
from app.games.base import Q2, InstantGame, Outcome, floor_dec


# ---------------------------------------------------------------- Dice
class DiceParams(BaseModel):
    target: Decimal = Field(ge=Decimal("1.00"), le=Decimal("99.00"), decimal_places=2)
    direction: Literal["under", "over"] = "under"


class Dice(InstantGame):
    """Выпадает число 0.00–99.99. under: выигрыш если roll < target; over: если roll >= target."""

    name = "dice"
    title = "Dice"
    Params = DiceParams
    MIN_CHANCE = Decimal("0.01")
    MAX_CHANCE = Decimal("0.98")

    def chance(self, p: DiceParams) -> Decimal:
        c = p.target / 100 if p.direction == "under" else (100 - p.target) / 100
        if not (self.MIN_CHANCE <= c <= self.MAX_CHANCE):
            raise AppError("bad_params", "Шанс выигрыша должен быть от 1% до 98%")
        return c

    def multiplier(self, p: DiceParams) -> Decimal:
        return floor_dec(self.rtp / self.chance(p))

    def max_multiplier(self, p: DiceParams) -> Decimal:
        return self.multiplier(p)

    def play(self, rng: FairRng, p: DiceParams) -> Outcome:
        mult = self.multiplier(p)
        roll = Decimal(int(rng.float() * 10000)) / 100
        win = roll < p.target if p.direction == "under" else roll >= p.target
        return Outcome(mult if win else Decimal(0), {"roll": float(roll), "target": float(p.target),
                                                     "direction": p.direction, "payout_multiplier": float(mult)})


# ---------------------------------------------------------------- Coinflip
class CoinflipParams(BaseModel):
    side: Literal["heads", "tails"]


class Coinflip(InstantGame):
    name = "coinflip"
    title = "Монетка"
    Params = CoinflipParams

    def max_multiplier(self, p: CoinflipParams) -> Decimal:
        return floor_dec(self.rtp * 2)

    def play(self, rng: FairRng, p: CoinflipParams) -> Outcome:
        side = "heads" if rng.float() < 0.5 else "tails"
        mult = self.max_multiplier(p) if side == p.side else Decimal(0)
        return Outcome(mult, {"side": side, "chosen": p.side})


# ---------------------------------------------------------------- Limbo
class LimboParams(BaseModel):
    target: Decimal = Field(ge=Decimal("1.01"), le=Decimal("1000000"), decimal_places=2)


class Limbo(InstantGame):
    """Выпадает множитель X с P(X >= M) = RTP / M. Выигрыш если X >= target."""

    name = "limbo"
    title = "Limbo"
    Params = LimboParams
    CAP = Decimal("1000000")

    def max_multiplier(self, p: LimboParams) -> Decimal:
        return p.target

    def play(self, rng: FairRng, p: LimboParams) -> Outcome:
        f = rng.float()
        raw = self.rtp / Decimal(1 - f)  # 1 - f ∈ (0, 1]
        point = min(max(Decimal(1), floor_dec(raw, Q2)), self.CAP)
        win = point >= p.target
        return Outcome(p.target if win else Decimal(0), {"point": float(point), "target": float(p.target)})


# ---------------------------------------------------------------- Plinko
class PlinkoParams(BaseModel):
    rows: int = Field(ge=8, le=16)
    risk: Literal["low", "medium", "high"] = "medium"


class Plinko(InstantGame):
    """Шарик проходит rows рядов, в каждом уходит вправо с вероятностью 1/2.

    Таблицы множителей не захардкожены, а подбираются так, чтобы RTP был
    максимально близок к (1 - house_edge), но не выше его.
    """

    name = "plinko"
    title = "Plinko"
    Params = PlinkoParams
    # (коэффициент края на ряд, кривизна)
    SHAPES = {"low": (1.5, 1.0), "medium": (6.0, 1.15), "high": (40.0, 1.3)}

    @cached_property
    def tables(self) -> dict[str, dict[int, list[Decimal]]]:
        return {risk: {n: self._build_table(n, risk) for n in range(8, 17)} for risk in self.SHAPES}

    def _build_table(self, n: int, risk: str) -> list[Decimal]:
        k_edge, curve = self.SHAPES[risk]
        edge_mult = k_edge * n
        half = n / 2
        raw = [Fraction(edge_mult ** ((abs(k - half) / half) ** curve)) for k in range(n + 1)]
        probs = [Fraction(comb(n, k), 2**n) for k in range(n + 1)]
        target = Fraction(self.rtp)

        def floored(scale: Fraction) -> list[Fraction]:
            return [Fraction(int(r * scale * 100), 100) for r in raw]

        def ev(scale: Fraction) -> Fraction:
            return sum((m * p for m, p in zip(floored(scale), probs)), Fraction(0))

        lo, hi = Fraction(0), Fraction(4)
        for _ in range(50):  # бинпоиск максимального масштаба с EV <= RTP
            mid = (lo + hi) / 2
            if ev(mid) <= target:
                lo = mid
            else:
                hi = mid
        return [Decimal(m.numerator) / Decimal(m.denominator) for m in floored(lo)]

    def table(self, p: PlinkoParams) -> list[Decimal]:
        return self.tables[p.risk][p.rows]

    def max_multiplier(self, p: PlinkoParams) -> Decimal:
        return max(self.table(p))

    def play(self, rng: FairRng, p: PlinkoParams) -> Outcome:
        path = [1 if f >= 0.5 else 0 for f in rng.floats(p.rows)]  # 1 = вправо
        bucket = sum(path)
        mult = self.table(p)[bucket]
        return Outcome(mult, {"path": path, "bucket": bucket, "multiplier": float(mult)})

    def public_config(self) -> dict:
        cfg = super().public_config()
        cfg["tables"] = {r: {n: [float(x) for x in t] for n, t in rows.items()} for r, rows in self.tables.items()}
        return cfg
