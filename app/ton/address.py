"""Адреса TON: проверка (контрольная сумма), сравнение, удобная форма."""
from __future__ import annotations

from urllib.parse import quote

from pytoniq_core import Address

from app.errors import AppError


def parse(addr: str) -> Address:
    """Адрес в любой форме (EQ…/UQ…/0:hex). Только основная сеть и базовый воркчейн."""
    s = (addr or "").strip()
    if not s or len(s) > 80:
        raise AppError("bad_address", "Укажите адрес кошелька TON")
    try:
        a = Address(s)
    except Exception:  # noqa: BLE001 — неверная длина, символы или контрольная сумма
        raise AppError("bad_address", "Неверный адрес TON — скопируйте его из кошелька целиком") from None
    if a.wc != 0:
        raise AppError("bad_address", "Нужен адрес в основной сети (workchain 0)")
    if getattr(a, "is_test_only", False):
        raise AppError("bad_address", "Это адрес тестовой сети — нужен адрес основной сети TON")
    return a


def raw(addr: str | Address) -> str:
    a = addr if isinstance(addr, Address) else Address(addr)
    return a.to_str(is_user_friendly=False).lower()


def friendly(addr: str | Address, *, bounceable: bool = False) -> str:
    a = addr if isinstance(addr, Address) else Address(addr)
    return a.to_str(is_user_friendly=True, is_bounceable=bounceable, is_url_safe=True)


def same(a: str | Address | None, b: str | Address | None) -> bool:
    if not a or not b:
        return False
    try:
        return raw(a) == raw(b)
    except Exception:  # noqa: BLE001
        return False


def jetton_transfer_link(to: str, jetton_master: str, amount_units: int | None = None, text: str | None = None,
                         prefix: str = "ton://") -> str:
    """Ссылка «открыть перевод в кошельке» (стандарт TON: ton://transfer/<адрес>?jetton=…&amount=…&text=…).

    prefix="https://app.tonkeeper.com/" — веб-вариант, его можно ставить в кнопки Telegram.
    """
    q = [f"jetton={jetton_master}"]
    if amount_units:
        q.append(f"amount={int(amount_units)}")
    if text:
        q.append(f"text={quote(text)}")
    return f"{prefix}transfer/{to}?{'&'.join(q)}"
