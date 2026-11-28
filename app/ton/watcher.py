"""Сторож пополнений: раз в TON_POLL_SECONDS читает новые транзакции кошелька казино в toncenter.

Зачисляем только transfer_notification, пришедшие от НАСТОЯЩЕГО USDT-кошелька казино. Его адрес
вычисляет сам контракт USDT (get_wallet_address), поэтому поддельный токен «USDT» не пройдёт:
у него будет другой jetton-кошелёк.
"""
from __future__ import annotations

import asyncio
import html
import logging
from collections.abc import Awaitable, Callable

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.models import KV, TonDeposit, User
from app.money import usdt
from app.services.deposits import credit_incoming
from app.ton import address
from app.ton.cells import parse_transfer_notification
from app.ton.toncenter import Toncenter

log = logging.getLogger(__name__)
CURSOR_KEY = "ton_last_lt"

Notifier = Callable[[TonDeposit, User | None], Awaitable[None]]


class DepositWatcher:
    def __init__(self, settings: Settings, sessionmaker: async_sessionmaker[AsyncSession], client: Toncenter,
                 notify: Notifier | None = None):
        self.s = settings
        self.sessionmaker = sessionmaker
        self.client = client
        self.notify = notify
        self.wallet_raw = address.raw(address.parse(settings.ton_wallet_address))
        self.jetton_wallet_raw: str | None = (address.raw(address.parse(settings.ton_usdt_jetton_wallet))
                                              if settings.ton_usdt_jetton_wallet else None)

    async def setup(self) -> None:
        if self.jetton_wallet_raw is None:
            self.jetton_wallet_raw = await self.client.jetton_wallet_address(self.s.ton_usdt_master, self.wallet_raw)
        log.info("USDT-кошелёк казино: %s", address.friendly(self.jetton_wallet_raw, bounceable=True))

    async def _cursor(self, session: AsyncSession) -> int | None:
        v = await session.scalar(select(KV.value).where(KV.key == CURSOR_KEY))
        return int(v) if v is not None else None

    async def _save_cursor(self, session: AsyncSession, lt: int) -> None:
        await session.execute(insert(KV).values(key=CURSOR_KEY, value=str(lt))
                              .on_conflict_do_update(index_elements=[KV.key], set_={"value": str(lt)}))
        await session.commit()

    def incoming(self, tx: dict):
        """Входящий USDT из транзакции кошелька казино или None."""
        msg = tx.get("in_msg") or {}
        if not address.same(msg.get("source"), self.jetton_wallet_raw):
            return None
        body = (msg.get("message_content") or {}).get("body")
        n = parse_transfer_notification(body)
        return n if n and n.amount > 0 else None

    async def tick(self) -> int:
        """Обработать новые транзакции. Возвращает число новых пополнений."""
        if self.jetton_wallet_raw is None:
            await self.setup()
        async with self.sessionmaker() as session:
            cursor = await self._cursor(session)
            if cursor is None:  # первый запуск: старую историю кошелька не трогаем
                await self._save_cursor(session, await self.client.latest_lt(self.wallet_raw))
                return 0
        found = 0
        while True:
            txs = await self.client.transactions(self.wallet_raw, start_lt=cursor + 1, limit=100, sort="asc")
            for tx in txs:
                lt = int(tx["lt"])
                n = self.incoming(tx)
                async with self.sessionmaker() as session:
                    if n is not None:
                        dep, user = await credit_incoming(session, self.s, tx_hash=tx["hash"], lt=lt, amount=n.amount,
                                                          comment=n.comment, sender=n.sender)
                        if dep is not None:
                            found += 1
                            log.info("Пополнение %s от %s, комментарий %r → %s", usdt(dep.amount), n.sender,
                                     n.comment, user.public_id if user else "не найден")
                            if self.notify:
                                try:
                                    await self.notify(dep, user)
                                except Exception:
                                    log.warning("Не удалось отправить уведомление о пополнении", exc_info=True)
                    await self._save_cursor(session, lt)
                cursor = lt
            if len(txs) < 100:
                return found

    async def run(self) -> None:
        delay = self.s.ton_poll_seconds
        while True:
            try:
                await self.tick()
                delay = self.s.ton_poll_seconds
            except asyncio.CancelledError:
                raise
            except Exception:
                log.warning("Сторож пополнений: ошибка, повтор через %.0f с", delay, exc_info=True)
                delay = min(delay * 2, 300)
            await asyncio.sleep(delay)


def bot_notifier(bot: Bot, settings: Settings) -> Notifier:
    from app.bot.notify import notify_admins, notify_user, user_label

    async def notify(dep: TonDeposit, user: User | None) -> None:
        if user is not None:
            await notify_user(bot, user.id, f"✅ Пополнение зачислено: <b>+{usdt(dep.amount)}</b>\n"
                                            f"Баланс: <b>{usdt(user.balance)}</b>")
            await notify_admins(bot, settings, f"💰 Пополнение {usdt(dep.amount)} — {user_label(user)}")
        else:
            await notify_admins(bot, settings,
                                f"⚠️ <b>Перевод без ID игрока</b> №{dep.id}: {usdt(dep.amount)}\n"
                                f"Комментарий: <code>{html.escape((dep.comment or '—')[:64])}</code>\n"
                                f"Хэш: <code>{dep.tx_hash}</code>\n"
                                f"Зачислить: <code>/credit {dep.id} #ID_игрока</code>")
    return notify
