"""Crash: у каждого игрока свой полёт, время ведёт сервер.

Множитель растёт как m(t) = e^(0.18·t), t в секундах, округление вниз до 0,01.
Точка краха считается из сидов при ставке (как в Limbo): P(точка ≥ M) = RTP / M.
Игрок забирает выигрыш вручную или автоматически на заданном множителе.
Расчёт ленивый: при любом обращении сервер сравнивает время с моментом краха.
"""
from __future__ import annotations

import math
from decimal import ROUND_DOWN, Decimal

from pydantic import BaseModel, Field

from app.fairness import FairRng

GROWTH = 0.18  # в секунду
MAX_POINT = Decimal("1000")
Q2 = Decimal("0.01")


class CrashParams(BaseModel):
    auto_cashout: Decimal | None = Field(default=None, ge=Decimal("1.01"), le=Decimal("1000"), decimal_places=2)


def crash_point(rng: FairRng, rtp: Decimal) -> Decimal:
    raw = rtp / Decimal(1 - rng.float())
    return min(max(Decimal(1), raw.quantize(Q2, rounding=ROUND_DOWN)), MAX_POINT)


def multiplier_at(elapsed: float) -> Decimal:
    """Множитель через elapsed секунд полёта."""
    m = Decimal(str(math.exp(max(0.0, elapsed) * GROWTH))).quantize(Q2, rounding=ROUND_DOWN)
    return min(max(m, Decimal(1)), MAX_POINT)


def elapsed_for(mult: Decimal) -> float:
    """Через сколько секунд множитель достигнет mult."""
    return math.log(float(mult)) / GROWTH


class Crash:
    name = "crash"
    title = "Crash"
    Params = CrashParams

    def __init__(self, house_edge: Decimal):
        self.rtp = Decimal(1) - house_edge

    def new_state(self, rng: FairRng, p: CrashParams, started_at: float, cap: Decimal) -> dict:
        target = p.auto_cashout
        if target is None or target > cap:
            target = cap  # потолок выигрыша = авто-вывод на лимите max_payout
        return {"point": str(crash_point(rng, self.rtp)), "started_at": started_at, "cap": str(cap),
                "auto": str(target), "auto_user": str(p.auto_cashout) if p.auto_cashout else None}

    def resolve(self, state: dict, now: float) -> tuple[str, Decimal] | None:
        """Если раунд уже закончился к моменту now — ('won'|'lost', множитель), иначе None."""
        point, auto = Decimal(state["point"]), Decimal(state["auto"])
        elapsed = now - state["started_at"]
        if auto <= point and elapsed >= elapsed_for(auto):
            return "won", auto
        if elapsed >= elapsed_for(point):
            return "lost", Decimal(0)
        return None

    def public_config(self) -> dict:
        return {"name": self.name, "title": self.title, "growth": GROWTH, "max": float(MAX_POINT),
                "params_schema": CrashParams.model_json_schema()}
