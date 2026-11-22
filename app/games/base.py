"""Базовые классы игр.

Чтобы добавить новую мгновенную игру:
  1. унаследуйтесь от InstantGame, задайте name/title/Params;
  2. реализуйте play() и max_multiplier();
  3. добавьте класс в INSTANT_GAMES в app/games/__init__.py.
Всё остальное (баланс, сиды, история, лимиты) сделает GameService.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import ROUND_DOWN, Decimal
from typing import Any, ClassVar

from pydantic import BaseModel

from app.fairness import FairRng

Q4 = Decimal("0.0001")
Q2 = Decimal("0.01")


def floor_dec(x: Decimal, q: Decimal = Q4) -> Decimal:
    return x.quantize(q, rounding=ROUND_DOWN)


@dataclass
class Outcome:
    multiplier: Decimal  # 0 — проигрыш
    result: dict[str, Any] = field(default_factory=dict)  # публичные данные исхода для фронта

    @property
    def won(self) -> bool:
        return self.multiplier > 0


class InstantGame(ABC):
    name: ClassVar[str]
    title: ClassVar[str]
    Params: ClassVar[type[BaseModel]]

    def __init__(self, house_edge: Decimal):
        self.edge = house_edge
        self.rtp = Decimal(1) - house_edge

    def parse_params(self, raw: dict[str, Any]) -> BaseModel:
        return self.Params.model_validate(raw)

    @abstractmethod
    def play(self, rng: FairRng, params: Any) -> Outcome: ...

    @abstractmethod
    def max_multiplier(self, params: Any) -> Decimal:
        """Максимально возможный множитель при данных параметрах (для лимита выплаты)."""

    def public_config(self) -> dict[str, Any]:
        return {"name": self.name, "title": self.title, "params_schema": self.Params.model_json_schema()}
