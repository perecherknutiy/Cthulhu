"""Валюта — USDT. Внутри все суммы целые: микро-USDT (1 USDT = 1 000 000), ровно как у токена USDT в сети TON.

Целые числа — чтобы баланс никогда не «плыл» от округлений float. В API суммы тоже целые микро-USDT;
фронт делит на 1 000 000 при показе.
"""
from __future__ import annotations

from decimal import ROUND_DOWN, Decimal, InvalidOperation

CODE = "USDT"
DECIMALS = 6
UNIT = 10**DECIMALS


def to_units(v) -> int:
    """'12.5' / 12.5 / Decimal → 12 500 000. Больше 6 знаков после точки — ошибка."""
    if isinstance(v, bool):
        raise ValueError("сумма не может быть bool")
    try:
        d = Decimal(str(v).strip().replace(",", "."))
    except InvalidOperation:
        raise ValueError(f"не число: {v!r}") from None
    units = d * UNIT
    if units != units.to_integral_value():
        raise ValueError(f"больше {DECIMALS} знаков после точки: {v!r}")
    return int(units)


def fmt(units: int, *, sign: bool = False) -> str:
    """12 500 000 → '12.50'; 198 000 → '0.198' (минимум 2 знака, лишние нули убираем)."""
    d = (Decimal(int(units)) / UNIT).quantize(Decimal("0.000001"), rounding=ROUND_DOWN)
    s = f"{abs(d):,.6f}".replace(",", " ").rstrip("0")
    whole, frac = s.split(".")
    s = f"{whole}.{frac.ljust(2, '0')}"
    if d < 0:
        return "−" + s
    return ("+" + s) if sign and d > 0 else s


def usdt(units: int, *, sign: bool = False) -> str:
    return f"{fmt(units, sign=sign)} {CODE}"
