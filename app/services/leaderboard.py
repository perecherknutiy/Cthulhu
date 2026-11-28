"""Рейтинг игроков по сумме ставок за период."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Bet, BetStatus, User
from app.services.users import display_name
from app.vip import vip_for


async def leaderboard(session: AsyncSession, me_id: int, *, days: int | None = 7, limit: int = 20) -> dict:
    conds = [Bet.status != BetStatus.active, User.is_banned.is_(False)]
    if days:
        conds.append(Bet.created_at >= datetime.now(timezone.utc) - timedelta(days=days))
    wagered = func.sum(Bet.amount).label("wagered")
    base = (
        select(User.id, User.public_id, User.nickname, User.photo_url, User.total_wagered, wagered,
               func.max(Bet.payout).label("best_win"))
        .join(Bet, Bet.user_id == User.id).where(*conds).group_by(User.id)
    )
    rows = (await session.execute(base.order_by(wagered.desc(), User.public_id).limit(limit))).all()

    def entry(rank: int, r) -> dict:
        u = User(public_id=r.public_id, nickname=r.nickname)
        return {"rank": rank, "public_id": r.public_id, "nickname": display_name(u), "photo_url": r.photo_url,
                "vip_level": vip_for(r.total_wagered)["level"], "wagered": int(r.wagered), "best_win": int(r.best_win)}

    top = [entry(i + 1, r) for i, r in enumerate(rows)]
    my_public = await session.scalar(select(User.public_id).where(User.id == me_id))
    me = next(({"rank": e["rank"], "wagered": e["wagered"]} for e in top if e["public_id"] == my_public), None)
    if me is None:
        sub = base.subquery()
        my = await session.scalar(select(sub.c.wagered).where(sub.c.id == me_id))
        if my:
            ahead = await session.scalar(select(func.count()).select_from(sub).where(sub.c.wagered > my))
            me = {"rank": int(ahead) + 1, "wagered": int(my)}
    return {"period_days": days, "top": top, "me": me}
