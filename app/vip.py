"""Уровни привилегий по сумме ставок (Бронза → Бриллиант). Пороги — в микро-USDT."""
from __future__ import annotations

from app.money import UNIT

VIP_LEVELS = [
    {"level": 0, "key": "bronze", "min": 0, "cashback": 0},
    {"level": 1, "key": "silver", "min": 100 * UNIT, "cashback": 1},
    {"level": 2, "key": "gold", "min": 1_000 * UNIT, "cashback": 2},
    {"level": 3, "key": "sapphire", "min": 5_000 * UNIT, "cashback": 3},
    {"level": 4, "key": "diamond", "min": 25_000 * UNIT, "cashback": 5},
]


def vip_for(wagered: int) -> dict:
    cur = VIP_LEVELS[0]
    for lvl in VIP_LEVELS:
        if wagered >= lvl["min"]:
            cur = lvl
    nxt = VIP_LEVELS[cur["level"] + 1] if cur["level"] + 1 < len(VIP_LEVELS) else None
    return {"level": cur["level"], "key": cur["key"], "cashback": cur["cashback"], "wagered": wagered,
            "current_min": cur["min"], "next_min": nxt["min"] if nxt else None, "next_key": nxt["key"] if nxt else None}
