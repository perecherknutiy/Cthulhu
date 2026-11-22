"""Игры, история ставок, provably fair."""
from __future__ import annotations

from fastapi import APIRouter, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.api.deps import GamesDep, SessionDep, UserDep
from app.api.schemas import BetOut, PlayIn, PlayOut, RevealIn, RotateIn, RotateOut, SeedOut, VerifyIn
from app.errors import NotFound
from app.fairness import hash_seed
from app.models import Bet, BetStatus
from app.services import seeds, wallet

router = APIRouter(prefix="/api", tags=["games"])


def _limit(request: Request, user_id: int) -> None:
    request.app.state.bet_limiter.hit(str(user_id))


async def _out(session, res) -> PlayOut:
    await session.refresh(res.bet, ["seed"])
    return PlayOut(bet=BetOut.of(res.bet), balance=res.balance, result=res.result)


# ---------------------------------------------------------------- mines (до /games/{game}/play!)
@router.get("/games/mines/active")
async def mines_active(user: UserDep, session: SessionDep, games: GamesDep):
    return {"game": await games.mines_get_active(session, user.id)}


@router.post("/games/mines/start", response_model=PlayOut)
async def mines_start(body: PlayIn, request: Request, user: UserDep, session: SessionDep, games: GamesDep):
    _limit(request, user.id)
    return await _out(session, await games.mines_start(session, user.id, body.amount, body.params))


@router.post("/games/mines/reveal", response_model=PlayOut)
async def mines_reveal(body: RevealIn, request: Request, user: UserDep, session: SessionDep, games: GamesDep):
    _limit(request, user.id)
    return await _out(session, await games.mines_reveal(session, user.id, body.model_dump()))


@router.post("/games/mines/cashout", response_model=PlayOut)
async def mines_cashout(request: Request, user: UserDep, session: SessionDep, games: GamesDep):
    _limit(request, user.id)
    return await _out(session, await games.mines_cashout(session, user.id))


# ---------------------------------------------------------------- instant games
@router.post("/games/{game}/play", response_model=PlayOut)
async def play(game: str, body: PlayIn, request: Request, user: UserDep, session: SessionDep, games: GamesDep):
    _limit(request, user.id)
    return await _out(session, await games.play_instant(session, user.id, game, body.amount, body.params))


# ---------------------------------------------------------------- history
@router.get("/bets", response_model=list[BetOut])
async def bets(user: UserDep, session: SessionDep, limit: int = Query(30, ge=1, le=100),
               before_id: int | None = None, game: str | None = None):
    q = select(Bet).options(joinedload(Bet.seed)).where(Bet.user_id == user.id, Bet.status != BetStatus.active)
    if before_id:
        q = q.where(Bet.id < before_id)
    if game:
        q = q.where(Bet.game == game)
    rows = await session.scalars(q.order_by(Bet.id.desc()).limit(limit))
    return [BetOut.of(b) for b in rows]


@router.get("/bets/{bet_id}", response_model=BetOut)
async def bet(bet_id: int, user: UserDep, session: SessionDep):
    b = await session.scalar(select(Bet).options(joinedload(Bet.seed)).where(Bet.id == bet_id, Bet.user_id == user.id))
    if b is None or b.status == BetStatus.active:
        raise NotFound("Ставка")
    return BetOut.of(b)


# ---------------------------------------------------------------- provably fair
@router.get("/fair", response_model=SeedOut)
async def fair(user: UserDep, session: SessionDep):
    seed = await seeds.get_active_seed(session, user.id)
    await session.commit()
    return SeedOut(server_seed_hash=seed.server_seed_hash, client_seed=seed.client_seed, nonce=seed.nonce)


@router.post("/fair/rotate", response_model=RotateOut)
async def rotate(body: RotateIn, user: UserDep, session: SessionDep):
    """Раскрыть текущий server seed и начать новую пару (можно сразу задать новый client seed)."""
    await wallet.lock_user(session, user.id)
    old, new = await seeds.rotate_seed(session, user.id, body.client_seed)
    await session.commit()
    return RotateOut(
        previous_server_seed=old.server_seed, previous_server_seed_hash=old.server_seed_hash,
        previous_client_seed=old.client_seed, previous_nonce=old.nonce,
        current=SeedOut(server_seed_hash=new.server_seed_hash, client_seed=new.client_seed, nonce=new.nonce),
    )


@router.post("/fair/verify")
async def verify(body: VerifyIn, games: GamesDep):
    """Публичная проверка: пересчитать исход по раскрытым сидам. Авторизация не нужна."""
    return {"server_seed_hash": hash_seed(body.server_seed),
            **games.verify(body.game, body.server_seed, body.client_seed, body.nonce, body.params)}
