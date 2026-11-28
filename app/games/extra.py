"""Европейская рулетка и слоты 3×3."""
from __future__ import annotations

from decimal import Decimal
from fractions import Fraction
from functools import cached_property
from typing import Literal, Union

from pydantic import BaseModel, Field, field_validator

from app.fairness import FairRng
from app.games.base import InstantGame, Outcome, floor_dec

# ---------------------------------------------------------------- Roulette
RED = frozenset({1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36})


class RouletteParams(BaseModel):
    # red / black / even / odd / zero или конкретное число 0–36
    bet: Union[Literal["red", "black", "even", "odd", "zero"], int] = Field(...)

    @field_validator("bet", mode="before")
    @classmethod
    def _no_bool(cls, v):
        if isinstance(v, bool):
            raise ValueError("ставка: red, black, even, odd, zero или число 0–36")
        return v

    @field_validator("bet")
    @classmethod
    def _number_range(cls, v):
        if isinstance(v, int) and not 0 <= v <= 36:
            raise ValueError("число от 0 до 36")
        return v


class Roulette(InstantGame):
    """Европейская рулетка (одно зеро). Выплаты классические: цвет/чётность ×2, число и зеро ×36.

    Преимущество казино фиксировано правилами — 1/37 ≈ 2,7%, от HOUSE_EDGE не зависит.
    """

    name = "roulette"
    title = "Roulette"
    Params = RouletteParams

    @staticmethod
    def color(n: int) -> str:
        return "green" if n == 0 else "red" if n in RED else "black"

    @staticmethod
    def multiplier_for(bet) -> Decimal:
        return Decimal(36) if isinstance(bet, int) or bet == "zero" else Decimal(2)

    def max_multiplier(self, p: RouletteParams) -> Decimal:
        return self.multiplier_for(p.bet)

    def play(self, rng: FairRng, p: RouletteParams) -> Outcome:
        n = rng.int_below(37)
        b = p.bet
        win = (
            (isinstance(b, int) and b == n)
            or (b == "zero" and n == 0)
            or (b in ("red", "black") and self.color(n) == b)
            or (b == "even" and n != 0 and n % 2 == 0)
            or (b == "odd" and n % 2 == 1)
        )
        return Outcome(self.multiplier_for(b) if win else Decimal(0), {"number": n, "color": self.color(n), "bet": b})


# ---------------------------------------------------------------- Slots
SLOT_WEIGHTS = (32, 26, 20, 12, 7, 3)  # вероятность символа в клетке, %
SLOT_BASE = (2, 4, 8, 30, 120, 600)  # форма таблицы выплат до подгонки под RTP
SLOT_LINES = ((0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 4, 8), (6, 4, 2))
SLOT_THEMES = ("classic", "treasury", "royal")


class SlotsParams(BaseModel):
    slot: Literal["classic", "treasury", "royal"]


class Slots(InstantGame):
    """Сетка 3×3, 5 линий. Клетки независимы: символ выбирается по весам из одного числа RNG.

    Линия (3 одинаковых символа) платит pays[i] ставок на линию; ставка на линию = ставка / 5.
    RTP = Σ p_i³ · pays_i — таблица подгоняется под 1 − house_edge и округляется вниз до 0,01.
    Выигрыш режется лимитом max_payout (ставку заранее не отклоняем).
    """

    name = "slots"
    title = "Slots"
    Params = SlotsParams
    cap_payout = True

    @cached_property
    def pays(self) -> list[Decimal]:
        rtp = Fraction(self.rtp)
        ev = sum((Fraction(w, 100) ** 3 * b for w, b in zip(SLOT_WEIGHTS, SLOT_BASE)), Fraction(0))
        scale = rtp / ev
        return [Decimal(int(b * scale * 100)) / 100 for b in SLOT_BASE]

    def max_multiplier(self, p: SlotsParams) -> None:
        return None

    def play(self, rng: FairRng, p: SlotsParams) -> Outcome:
        cum, acc = [], 0
        for w in SLOT_WEIGHTS:
            acc += w
            cum.append(acc)
        grid = []
        for f in rng.floats(9):
            v = int(f * 100)
            grid.append(next(i for i, c in enumerate(cum) if v < c))
        wins = []
        for i, (a, b, c) in enumerate(SLOT_LINES):
            if grid[a] == grid[b] == grid[c]:
                wins.append({"line": i, "symbol": grid[a], "pay": float(self.pays[grid[a]])})
        mult = floor_dec(sum((self.pays[w["symbol"]] for w in wins), Decimal(0)) / len(SLOT_LINES))
        return Outcome(mult, {"slot": p.slot, "grid": grid, "wins": wins, "multiplier": float(mult)})

    def public_config(self) -> dict:
        cfg = super().public_config()
        cfg.update(themes=[{"id": t} for t in SLOT_THEMES], weights=list(SLOT_WEIGHTS),
                   pays=[float(x) for x in self.pays], lines=[list(x) for x in SLOT_LINES])
        return cfg
