"""Оркестрация ставок: лимиты → блокировка баланса → nonce → исход → выплата → запись ставки."""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_DOWN, Decimal
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.errors import AppError, InsufficientFunds, NotFound
from app.fairness import FairRng
from app.games import get_crash, get_instant_games, get_mines
from app.games.crash import CrashParams, crash_point, multiplier_at
from app.games.mines import MinesParams, RevealParams
from app.money import usdt
from app.models import Bet, BetStatus, TxKind, User
from app.services import seeds, wallet


def payout_for(amount: int, multiplier: Decimal) -> int:
    return int((Decimal(amount) * multiplier).to_integral_value(rounding=ROUND_DOWN))


def _validate(model, raw: dict[str, Any]):
    try:
        return model.model_validate(raw)
    except ValidationError as e:
        first = e.errors()[0]
        loc = ".".join(str(x) for x in first["loc"])
        raise AppError("bad_params", f"Неверный параметр {loc}: {first['msg']}") from None


@dataclass
class BetResult:
    bet: Bet
    balance: int
    result: dict[str, Any]


class GameService:
    def __init__(self, settings: Settings):
        self.s = settings
        self.games = get_instant_games(settings.house_edge)
        self.mines = get_mines(settings.house_edge)
        self.crash = get_crash(settings.house_edge)
        self.clock = time.time  # подменяется в тестах

    # ------------------------------------------------------------ helpers
    def _check_amount(self, amount: int) -> None:
        if amount < self.s.min_bet or amount > self.s.max_bet:
            raise AppError("bad_amount", f"Ставка должна быть от {usdt(self.s.min_bet)} до {usdt(self.s.max_bet)}")

    async def _take_bet(self, session: AsyncSession, user_id: int, amount: int):
        """Блокирует юзера, берёт nonce, списывает ставку. Возвращает (user, seed, nonce)."""
        user = await wallet.lock_user(session, user_id)
        if user.balance < amount:
            raise InsufficientFunds()
        seed = await seeds.get_active_seed(session, user_id, lock=True)
        nonce = seed.nonce
        seed.nonce = nonce + 1
        return user, seed, nonce

    def _settle(self, session: AsyncSession, user: User, bet: Bet, multiplier: Decimal, cap: bool = False) -> None:
        payout = payout_for(bet.amount, multiplier)
        if cap:
            payout = min(payout, self.s.max_payout)
        bet.multiplier = multiplier
        bet.payout = payout
        bet.status = BetStatus.won if payout > 0 else BetStatus.lost
        bet.finished_at = datetime.now(timezone.utc)
        if payout > 0:
            wallet.apply(session, user, TxKind.win, payout, ref_type="bet", ref_id=bet.id)
            user.total_won += payout

    # ------------------------------------------------------------ instant games
    async def play_instant(self, session: AsyncSession, user_id: int, game_name: str, amount: int,
                           raw_params: dict[str, Any]) -> BetResult:
        game = self.games.get(game_name)
        if game is None:
            raise NotFound("Игра")
        self._check_amount(amount)
        params = _validate(game.Params, raw_params)
        max_mult = game.max_multiplier(params)  # None — выигрыш режется лимитом при расчёте (слоты)
        if max_mult is not None and payout_for(amount, max_mult) > self.s.max_payout:
            raise AppError("max_payout", f"Возможный выигрыш превышает лимит {usdt(self.s.max_payout)}")

        user, seed, nonce = await self._take_bet(session, user_id, amount)
        outcome = game.play(FairRng(seed.server_seed, seed.client_seed, nonce), params)

        bet = Bet(user_id=user_id, game=game.name, amount=amount, status=BetStatus.lost,
                  params=params.model_dump(mode="json"), result=outcome.result,
                  seed_id=seed.id, client_seed=seed.client_seed, nonce=nonce)
        session.add(bet)
        await session.flush()

        wallet.apply(session, user, TxKind.bet, -amount, ref_type="bet", ref_id=bet.id)
        user.total_wagered += amount
        self._settle(session, user, bet, outcome.multiplier, cap=getattr(game, "cap_payout", False))
        await session.commit()
        return BetResult(bet=bet, balance=user.balance, result=outcome.result)

    # ------------------------------------------------------------ mines
    async def _active_mines(self, session: AsyncSession, user_id: int, *, lock: bool) -> Bet | None:
        q = select(Bet).where(Bet.user_id == user_id, Bet.game == self.mines.name, Bet.status == BetStatus.active)
        if lock:
            q = q.with_for_update(of=Bet)
        return await session.scalar(q)

    def mines_view(self, bet: Bet) -> dict[str, Any]:
        finished = bet.status != BetStatus.active
        data = self.mines.public_state(bet.params["mines"], bet.state or {}, finished)
        data.update(bet_id=bet.id, amount=bet.amount, status=bet.status.value, payout=bet.payout)
        return data

    async def mines_get_active(self, session: AsyncSession, user_id: int) -> dict[str, Any] | None:
        bet = await self._active_mines(session, user_id, lock=False)
        return self.mines_view(bet) if bet else None

    async def mines_start(self, session: AsyncSession, user_id: int, amount: int, raw_params: dict) -> BetResult:
        self._check_amount(amount)
        params: MinesParams = _validate(MinesParams, raw_params)
        user, seed, nonce = await self._take_bet(session, user_id, amount)
        if await self._active_mines(session, user_id, lock=False):
            raise AppError("active_game", "У вас уже есть активная игра Mines")

        state = self.mines.new_state(FairRng(seed.server_seed, seed.client_seed, nonce), params)
        bet = Bet(user_id=user_id, game=self.mines.name, amount=amount, status=BetStatus.active,
                  params=params.model_dump(mode="json"), state=state,
                  seed_id=seed.id, client_seed=seed.client_seed, nonce=nonce)
        session.add(bet)
        await session.flush()
        wallet.apply(session, user, TxKind.bet, -amount, ref_type="bet", ref_id=bet.id)
        user.total_wagered += amount
        await session.commit()
        view = self.mines_view(bet)
        return BetResult(bet=bet, balance=user.balance, result=view)

    async def mines_reveal(self, session: AsyncSession, user_id: int, raw_params: dict) -> BetResult:
        params: RevealParams = _validate(RevealParams, raw_params)
        user = await wallet.lock_user(session, user_id)
        bet = await self._active_mines(session, user_id, lock=True)
        if bet is None:
            raise AppError("no_active_game", "Нет активной игры")

        state = dict(bet.state or {})
        safe = self.mines.reveal(state, params.tile)
        bet.state = state  # переприсваиваем, чтобы SQLAlchemy увидел изменение JSONB
        mines_count = bet.params["mines"]
        opened = len(state["revealed"])

        if not safe:
            self._settle(session, user, bet, Decimal(0))
        else:
            mult = self.mines.multiplier(mines_count, opened)
            all_open = opened >= self.mines.safe_tiles(mines_count)
            hit_cap = payout_for(bet.amount, mult) >= self.s.max_payout
            if all_open or hit_cap:
                self._settle(session, user, bet, mult, cap=True)  # авто-кэшаут
        if bet.status != BetStatus.active:
            bet.result = self.mines.public_state(mines_count, state, finished=True)
        await session.commit()
        return BetResult(bet=bet, balance=user.balance, result=self.mines_view(bet))

    async def mines_cashout(self, session: AsyncSession, user_id: int) -> BetResult:
        user = await wallet.lock_user(session, user_id)
        bet = await self._active_mines(session, user_id, lock=True)
        if bet is None:
            raise AppError("no_active_game", "Нет активной игры")
        state = bet.state or {"revealed": []}
        if not state["revealed"]:
            raise AppError("nothing_revealed", "Откройте хотя бы одну клетку")
        mult = self.mines.multiplier(bet.params["mines"], len(state["revealed"]))
        self._settle(session, user, bet, mult, cap=True)
        bet.result = self.mines.public_state(bet.params["mines"], state, finished=True)
        await session.commit()
        return BetResult(bet=bet, balance=user.balance, result=self.mines_view(bet))

    # ------------------------------------------------------------ crash
    async def _active_crash(self, session: AsyncSession, user_id: int, *, lock: bool) -> Bet | None:
        q = select(Bet).where(Bet.user_id == user_id, Bet.game == self.crash.name, Bet.status == BetStatus.active)
        if lock:
            q = q.with_for_update(of=Bet)
        return await session.scalar(q)

    def crash_view(self, bet: Bet, now: float | None = None) -> dict[str, Any]:
        now = self.clock() if now is None else now
        st = bet.state or {}
        data = {"bet_id": bet.id, "amount": bet.amount, "status": bet.status.value, "payout": bet.payout,
                "started_at": st.get("started_at"), "server_now": now,
                "auto_cashout": float(Decimal(st["auto_user"])) if st.get("auto_user") else None,
                # раунд закончится выигрышем на этом множителе (авто-вывод или лимит выплаты), если не крах раньше
                "auto_target": float(Decimal(st["auto"])), "max_multiplier": float(Decimal(st["cap"]))}
        if bet.status == BetStatus.active:
            data["multiplier"] = float(multiplier_at(now - st["started_at"]))
        else:
            data.update(crash_point=float(Decimal(st["point"])), multiplier=float(bet.multiplier),
                        cashout=bet.result.get("cashout") if bet.result else None)
        return data

    def _finish_crash(self, session: AsyncSession, user: User, bet: Bet, status: str, mult: Decimal, kind: str | None):
        st = bet.state
        self._settle(session, user, bet, mult if status == "won" else Decimal(0), cap=True)
        bet.result = {"crash_point": float(Decimal(st["point"])), "cashout": kind,
                      "multiplier": float(mult) if status == "won" else 0}

    async def settle_crash(self, session: AsyncSession, user_id: int) -> bool:
        """Досчитать раунд, который закончился сам (авто-вывод или крах). True — если что-то изменилось."""
        bet = await self._active_crash(session, user_id, lock=False)
        if bet is None or self.crash.resolve(bet.state, self.clock()) is None:
            return False
        user = await wallet.lock_user(session, user_id, allow_banned=True)
        bet = await self._active_crash(session, user_id, lock=True)
        if bet is None:
            return False
        res = self.crash.resolve(bet.state, self.clock())
        if res is None:
            return False
        status, mult = res
        self._finish_crash(session, user, bet, status, mult, "auto" if status == "won" else None)
        await session.commit()
        return True

    async def crash_get_active(self, session: AsyncSession, user_id: int) -> dict[str, Any] | None:
        await self.settle_crash(session, user_id)
        bet = await self._active_crash(session, user_id, lock=False)
        return self.crash_view(bet) if bet else None

    async def crash_start(self, session: AsyncSession, user_id: int, amount: int, raw_params: dict) -> BetResult:
        self._check_amount(amount)
        params: CrashParams = _validate(CrashParams, raw_params)
        await self.settle_crash(session, user_id)
        user, seed, nonce = await self._take_bet(session, user_id, amount)
        if await self._active_crash(session, user_id, lock=False):
            raise AppError("active_game", "У вас уже идёт раунд Crash")
        # потолок множителя: не больше 1000× и не больше лимита выплаты
        cap = min(Decimal(1000), (Decimal(self.s.max_payout) / amount).quantize(Decimal("0.01"), rounding=ROUND_DOWN))
        cap = max(cap, Decimal("1.01"))
        state = self.crash.new_state(FairRng(seed.server_seed, seed.client_seed, nonce), params, self.clock(), cap)
        bet = Bet(user_id=user_id, game=self.crash.name, amount=amount, status=BetStatus.active,
                  params=params.model_dump(mode="json"), state=state,
                  seed_id=seed.id, client_seed=seed.client_seed, nonce=nonce)
        session.add(bet)
        await session.flush()
        wallet.apply(session, user, TxKind.bet, -amount, ref_type="bet", ref_id=bet.id)
        user.total_wagered += amount
        res = self.crash.resolve(state, self.clock())  # точка 1.00× — крах сразу
        if res:
            self._finish_crash(session, user, bet, res[0], res[1], None)
        await session.commit()
        return BetResult(bet=bet, balance=user.balance, result=self.crash_view(bet))

    async def crash_cashout(self, session: AsyncSession, user_id: int) -> BetResult:
        now = self.clock()  # время нажатия фиксируем до блокировок
        user = await wallet.lock_user(session, user_id)
        bet = await self._active_crash(session, user_id, lock=True)
        if bet is None:
            raise AppError("no_active_game", "Нет активного раунда")
        res = self.crash.resolve(bet.state, now)
        if res:  # не успели: раунд уже закончился (крах или авто-вывод)
            self._finish_crash(session, user, bet, res[0], res[1], "auto" if res[0] == "won" else None)
        else:
            self._finish_crash(session, user, bet, "won", multiplier_at(now - bet.state["started_at"]), "manual")
        await session.commit()
        return BetResult(bet=bet, balance=user.balance, result=self.crash_view(bet, now))

    # ------------------------------------------------------------ verification
    def verify(self, game_name: str, server_seed: str, client_seed: str, nonce: int,
               raw_params: dict[str, Any]) -> dict[str, Any]:
        """Пересчитать исход ставки по раскрытым сидам (публичный эндпоинт)."""
        rng = FairRng(server_seed, client_seed, nonce)
        if game_name == self.crash.name:
            return {"crash_point": float(crash_point(rng, self.crash.rtp))}
        if game_name == self.mines.name:
            params = _validate(MinesParams, raw_params)
            return {"mines": self.mines.new_state(rng, params)["mines"]}
        game = self.games.get(game_name)
        if game is None:
            raise NotFound("Игра")
        outcome = game.play(rng, _validate(game.Params, raw_params))
        return {"multiplier": float(outcome.multiplier), **outcome.result}

    def public_config(self) -> dict[str, Any]:
        return {
            "house_edge": float(self.s.house_edge),
            "min_bet": self.s.min_bet,
            "max_bet": self.s.max_bet,
            "max_payout": self.s.max_payout,
            "games": [g.public_config() for g in self.games.values()] + [self.mines.public_config(),
                                                                          self.crash.public_config()],
        }
