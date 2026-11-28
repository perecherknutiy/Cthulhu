from decimal import Decimal
from functools import lru_cache

from app.games.base import InstantGame, Outcome
from app.games.crash import Crash
from app.games.extra import Roulette, Slots
from app.games.instant import Coinflip, Dice, Limbo, Plinko
from app.games.mines import Mines

INSTANT_GAMES: list[type[InstantGame]] = [Dice, Coinflip, Limbo, Plinko, Roulette, Slots]


@lru_cache
def get_instant_games(house_edge: Decimal) -> dict[str, InstantGame]:
    return {cls.name: cls(house_edge) for cls in INSTANT_GAMES}


@lru_cache
def get_mines(house_edge: Decimal) -> Mines:
    return Mines(house_edge)


@lru_cache
def get_crash(house_edge: Decimal) -> Crash:
    return Crash(house_edge)


__all__ = ["InstantGame", "Outcome", "Mines", "Crash", "get_instant_games", "get_mines", "get_crash", "INSTANT_GAMES"]
