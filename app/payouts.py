"""Способы выплаты выигрыша пользователю.

У Bot API нет прямого метода «перевести звёзды пользователю». Варианты:
  * manual — админ выплачивает сам (подарками из своего аккаунта, через Fragment и т.д.)
             и подтверждает выплату кнопкой в боте;
  * gifts  — бот отправляет пользователю обычные подарки (sendGift) за счёт своего баланса звёзд.
             Пользователь может обменять подарки на звёзды по курсу Telegram
             (обычно он ниже цены подарка — учитывайте это в условиях вывода).
Добавить свой способ: реализуйте PayoutMethod и зарегистрируйте в get_payout_method().
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from aiogram import Bot

log = logging.getLogger(__name__)


@dataclass
class PayoutResult:
    paid: int  # сколько фактически выплачено (в звёздах по цене отправки)
    details: list[str] = field(default_factory=list)
    error: str | None = None


class PayoutMethod(ABC):
    name: str
    automatic: bool  # True — бот платит сам, False — админ подтверждает вручную

    @abstractmethod
    async def pay(self, bot: Bot, user_id: int, amount: int, withdrawal_id: int) -> PayoutResult: ...


class ManualPayout(PayoutMethod):
    name = "manual"
    automatic = False

    async def pay(self, bot: Bot, user_id: int, amount: int, withdrawal_id: int) -> PayoutResult:
        return PayoutResult(paid=amount, details=["Выплачено вручную администратором"])


def plan_gifts(amount: int, denominations: dict[int, str]) -> tuple[list[str], int]:
    """Набрать сумму ≤ amount минимальным числом подарков (DP). Возвращает (gift_ids, сумма)."""
    if amount <= 0 or not denominations:
        return [], 0
    coins = sorted(denominations)
    best: list[int | None] = [None] * (amount + 1)  # best[s] = мин. число подарков для суммы s
    prev: list[int] = [0] * (amount + 1)
    best[0] = 0
    for s in range(1, amount + 1):
        for c in coins:
            if c > s:
                break
            b = best[s - c]
            if b is not None and (best[s] is None or b + 1 < best[s]):
                best[s] = b + 1
                prev[s] = c
    reach = max(s for s in range(amount + 1) if best[s] is not None)
    prices, s = [], reach
    while s > 0:
        prices.append(prev[s])
        s -= prev[s]
    prices.sort(reverse=True)  # сначала крупные — при сбое посередине выплачено больше
    return [denominations[p] for p in prices], reach


class GiftPayout(PayoutMethod):
    name = "gifts"
    automatic = True

    async def pay(self, bot: Bot, user_id: int, amount: int, withdrawal_id: int) -> PayoutResult:
        gifts = (await bot.get_available_gifts()).gifts
        # только безлимитные, без Premium-ограничения; на одну цену — один gift_id
        denoms: dict[int, str] = {}
        for g in gifts:
            if g.total_count is None and not g.is_premium:
                denoms.setdefault(g.star_count, g.id)
        ids, total = plan_gifts(amount, denoms)
        if total == 0:
            return PayoutResult(paid=0, error="Нет подходящих подарков для этой суммы")

        balance = (await bot.get_my_star_balance()).amount
        if balance < total:
            return PayoutResult(paid=0, error=f"На балансе бота {balance} ⭐, нужно {total} ⭐")

        paid, details = 0, []
        price_by_id = {v: k for k, v in denoms.items()}
        for gift_id in ids:
            try:
                await bot.send_gift(gift_id=gift_id, user_id=user_id, text=f"Вывод #{withdrawal_id}")
            except Exception as e:  # noqa: BLE001
                log.exception("sendGift failed for withdrawal %s", withdrawal_id)
                return PayoutResult(paid=paid, details=details, error=f"Ошибка отправки подарка: {e}")
            paid += price_by_id[gift_id]
            details.append(f"gift {gift_id} ({price_by_id[gift_id]} ⭐)")
        return PayoutResult(paid=paid, details=details)


def get_payout_method(name: str) -> PayoutMethod:
    methods: dict[str, PayoutMethod] = {"manual": ManualPayout(), "gifts": GiftPayout()}
    if name not in methods:
        raise ValueError(f"Unknown payout method {name}")
    return methods[name]
