"""Админка в боте. Доступ — только для ADMIN_IDS."""
from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import BaseFilter, Command, CommandObject
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.notify import notify_user, user_label, withdrawal_keyboard, withdrawal_text
from app.config import Settings, get_settings
from app.errors import AppError
from app.models import TxKind, User, Withdrawal, WithdrawalStatus
from app.services import payments, stats, wallet, withdrawals


class IsAdmin(BaseFilter):
    async def __call__(self, event: TelegramObject) -> bool:
        user = getattr(event, "from_user", None)
        return bool(user and user.id in get_settings().admin_ids)


router = Router(name="admin")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

HELP = """<b>Админка</b>
/stats — статистика
/user &lt;id&gt; — карточка игрока
/give &lt;id&gt; &lt;сумма&gt; [причина] — начислить (отрицательная сумма — списать)
/ban &lt;id&gt; • /unban &lt;id&gt;
/withdrawals — заявки на вывод
/refund &lt;charge_id&gt; [force] — вернуть платёж звёздами
/botbalance — баланс звёзд бота"""


def _args(command: CommandObject, n: int) -> list[str]:
    parts = (command.args or "").split(maxsplit=n)
    if len(parts) < n:
        raise AppError("usage", "Неверные аргументы, см. /admin")
    return parts


def _int(s: str) -> int:
    try:
        return int(s)
    except ValueError:
        raise AppError("usage", f"Ожидалось число, получено {s!r}") from None


@router.message(Command("admin"))
async def admin_help(message: Message):
    await message.answer(HELP)


@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession):
    day, total = await stats.today_and_total(session)

    def fmt(d: dict) -> str:
        return (f"Новых игроков: {d['users']}\nДепозиты: {d['deposits']} ⭐\nСтавок: {d['bets']} на {d['wagered']} ⭐\n"
                f"Выплачено в играх: {d['paid_out']} ⭐\nGGR: <b>{d['ggr']} ⭐</b>\nВыведено: {d['withdrawn']} ⭐")

    await message.answer(
        f"📊 <b>За 24 часа</b>\n{fmt(day)}\n\n📈 <b>Всего</b>\n{fmt(total)}\n\n"
        f"Балансы игроков (обязательства): {total['user_balances']} ⭐\n"
        f"Заявок на вывод в ожидании: {total['pending_withdrawals']}"
    )


@router.message(Command("user"))
async def cmd_user(message: Message, command: CommandObject, session: AsyncSession, settings: Settings):
    (uid,) = _args(command, 1)[:1]
    user = await session.get(User, _int(uid))
    if user is None:
        raise AppError("not_found", "Игрок не найден")
    left = withdrawals.wager_left(settings, user.total_deposited, user.total_wagered)
    await message.answer(
        f"👤 {user_label(user)}\n"
        f"Баланс: <b>{user.balance} ⭐</b>\n"
        f"Депозиты: {user.total_deposited} • Выводы: {user.total_withdrawn}\n"
        f"Ставки: {user.total_wagered} • Выигрыши: {user.total_won}\n"
        f"Отыгрыш до вывода: {left}\n"
        f"Реферер: {user.referrer_id or '—'} • Бан: {'да' if user.is_banned else 'нет'}\n"
        f"Регистрация: {user.created_at:%Y-%m-%d %H:%M}"
    )


@router.message(Command("give"))
async def cmd_give(message: Message, command: CommandObject, session: AsyncSession):
    parts = _args(command, 2)
    uid, amount = _int(parts[0]), _int(parts[1])
    note = parts[2] if len(parts) > 2 else f"admin {message.from_user.id}"
    user = await wallet.lock_user(session, uid, allow_banned=True)
    wallet.apply(session, user, TxKind.admin, amount, ref_type="admin", ref_id=message.from_user.id, note=note)
    await session.commit()
    await message.answer(f"Готово. Баланс {uid}: <b>{user.balance} ⭐</b>")


async def _set_ban(message: Message, command: CommandObject, session: AsyncSession, value: bool):
    (uid,) = _args(command, 1)[:1]
    user = await wallet.lock_user(session, _int(uid), allow_banned=True)
    user.is_banned = value
    await session.commit()
    await message.answer(f"{'Забанен' if value else 'Разбанен'}: {user_label(user)}")


@router.message(Command("ban"))
async def cmd_ban(message: Message, command: CommandObject, session: AsyncSession):
    await _set_ban(message, command, session, True)


@router.message(Command("unban"))
async def cmd_unban(message: Message, command: CommandObject, session: AsyncSession):
    await _set_ban(message, command, session, False)


@router.message(Command("withdrawals"))
async def cmd_withdrawals(message: Message, session: AsyncSession):
    rows = (await session.scalars(
        select(Withdrawal).where(Withdrawal.status.in_([WithdrawalStatus.pending, WithdrawalStatus.processing]))
        .order_by(Withdrawal.id).limit(20)
    )).all()
    if not rows:
        await message.answer("Заявок нет 🎉")
        return
    for w in rows:
        user = await session.get(User, w.user_id)
        markup = withdrawal_keyboard(w) if w.status == WithdrawalStatus.pending else None
        await message.answer(withdrawal_text(w, user), reply_markup=markup)


@router.callback_query(F.data.startswith("wd:"))
async def cb_withdrawal(call: CallbackQuery, session: AsyncSession, bot: Bot):
    _, action, wid = call.data.split(":")
    admin_id = call.from_user.id
    if action == "ok":
        await call.answer("Выплачиваю…")
        w, result = await withdrawals.approve(session, bot, int(wid), admin_id)
        status = f"✅ Выплачено {result.paid} ⭐" if not result.error else f"⚠️ {result.error} (выплачено {result.paid} ⭐)"
        if result.paid:
            await notify_user(bot, w.user_id, f"💸 Вывод #{w.id}: выплачено {result.paid} ⭐")
        if result.paid < w.amount:
            await notify_user(bot, w.user_id, f"Вывод #{w.id}: {w.amount - result.paid} ⭐ возвращены на баланс")
    else:
        w = await withdrawals.reject(session, int(wid), admin_id, reason="Отклонено администратором")
        status = "❌ Отклонено, средства возвращены"
        await notify_user(bot, w.user_id, f"Вывод #{w.id} отклонён, {w.amount} ⭐ возвращены на баланс")
        await call.answer("Отклонено")
    await call.message.edit_text(f"{call.message.html_text}\n\n<b>{status}</b> (admin {admin_id})")


@router.message(Command("refund"))
async def cmd_refund(message: Message, command: CommandObject, session: AsyncSession, bot: Bot):
    parts = _args(command, 1)
    force = len(parts) > 1 and parts[1].strip() == "force"
    p = await payments.refund_payment(session, bot, parts[0].split()[0], force=force)
    await message.answer(f"Возвращено {p.amount} ⭐ игроку {p.user_id}")


@router.message(Command("botbalance"))
async def cmd_botbalance(message: Message, bot: Bot):
    bal = await bot.get_my_star_balance()
    await message.answer(f"Баланс бота: <b>{bal.amount} ⭐</b>")
