"""Mines — многошаговая игра: поле 5x5, игрок открывает клетки и может забрать выигрыш в любой момент."""
from __future__ import annotations

from decimal import Decimal
from fractions import Fraction

from pydantic import BaseModel, Field

from app.errors import AppError
from app.fairness import FairRng
from app.games.base import floor_dec

TILES = 25


class MinesParams(BaseModel):
    mines: int = Field(ge=1, le=24)


class RevealParams(BaseModel):
    tile: int = Field(ge=0, lt=TILES)


class Mines:
    name = "mines"
    title = "Mines"
    Params = MinesParams

    def __init__(self, house_edge: Decimal):
        self.rtp = Decimal(1) - house_edge

    def multiplier(self, mines: int, revealed: int) -> Decimal:
        """Множитель после revealed безопасных открытий: RTP / P(revealed подряд безопасных)."""
        if revealed == 0:
            return Decimal(0)
        prob = Fraction(1)
        for i in range(revealed):
            prob *= Fraction(TILES - mines - i, TILES - i)
        return floor_dec(self.rtp / (Decimal(prob.numerator) / Decimal(prob.denominator)))

    def new_state(self, rng: FairRng, p: MinesParams) -> dict:
        positions = rng.shuffle(list(range(TILES)))[: p.mines]
        return {"mines": sorted(positions), "revealed": []}

    @staticmethod
    def safe_tiles(mines: int) -> int:
        return TILES - mines

    def reveal(self, state: dict, tile: int) -> bool:
        """Открывает клетку, возвращает True если она безопасна."""
        if tile in state["revealed"]:
            raise AppError("already_revealed", "Клетка уже открыта")
        state["revealed"] = [*state["revealed"], tile]
        return tile not in state["mines"]

    def public_state(self, mines: int, state: dict, finished: bool) -> dict:
        revealed = [t for t in state["revealed"] if t not in state["mines"]]
        data = {
            "mines_count": mines,
            "revealed": revealed,
            "multiplier": float(self.multiplier(mines, len(revealed))),
            "next_multiplier": float(self.multiplier(mines, len(revealed) + 1))
            if len(revealed) < self.safe_tiles(mines) else None,
        }
        if finished:
            data["mines"] = state["mines"]
            data["picked"] = state["revealed"]
        return data

    def public_config(self) -> dict:
        return {"name": self.name, "title": self.title, "params_schema": MinesParams.model_json_schema(), "tiles": TILES}
