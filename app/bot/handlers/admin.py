"""Админка в боте. Доступ — только для ADMIN_IDS."""
from __future__ import annotations

import html

from aiogram import Bot, F, Router
from aiogram.filters import BaseFilter, Command, CommandObject
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.notify import notify_user, user_label, withdrawal_keyboard, withdrawal_text
from app.config import Settings, get_settings
from app.errors import AppError
from app.models import DepositStatus, TonDeposit, TxKind, User, Withdrawal, WithdrawalStatus
from app.money import to_units, usdt
from app.services import deposits, stats, wallet, withdrawals


class IsAdmin(BaseFilter):
    async def __call__(self, event: TelegramObject) -> bool:
        user = getattr(event, "from_user", None)
        return bool(user and user.id in get_settings().admin_ids)


router = Router(name="admin")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

HELP = """<b>Админка</b>
/stats — статистика
&lt;id&gt; — Telegram ID или #ID игрока из профиля (например, #100042)
/user &lt;id&gt; — карточка игрока
/give &lt;id&gt; &lt;сумма USDT&gt; [причина] — начислить, например <code>/give #100042 2.5</code> (минус — списать)
/ban &lt;id&gt; • /unban &lt;id&gt;
/withdrawals — заявки на вывод
/paid &lt;номер&gt; &lt;хэш&gt; — отметить вывод отправленным и сохранить хэш перевода
/deposits — переводы USDT без ID игрока в комментарии
/credit &lt;номер перевода&gt; &lt;id&gt; — зачислить такой перевод игроку"""


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


async def _uid(session: AsyncSession, s: str) -> int:
    """'#100042' — внутренний ID игрока, иначе Telegram ID."""
    if s.startswith("#"):
        uid = await session.scalar(select(User.id).where(User.public_id == _int(s[1:])))
        if uid is None:
            raise AppError("not_found", "Игрок не найден")
        return uid
    return _int(s)


@router.message(Command("admin"))
async def admin_help(message: Message):
    await message.answer(HELP)


@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession):
    day, total = await stats.today_and_total(session)

    def fmt(d: dict) -> str:
        return (f"Новых игроков: {d['users']}\nДепозиты: {usdt(d['deposits'])}\n"
                f"Ставок: {d['bets']} на {usdt(d['wagered'])}\nВыплачено в играх: {usdt(d['paid_out'])}\n"
                f"GGR: <b>{usdt(d['ggr'])}</b>\nВыведено: {usdt(d['withdrawn'])}")

    await message.answer(
        f"📊 <b>За 24 часа</b>\n{fmt(day)}\n\n📈 <b>Всего</b>\n{fmt(total)}\n\n"
        f"Балансы игроков (обязательства): {usdt(total['user_balances'])}\n"
        f"Заявок на вывод в ожидании: {total['pending_withdrawals']}\n"
        f"Переводов без ID игрока: {total['unmatched_deposits']}"
    )


@router.message(Command("user"))
async def cmd_user(message: Message, command: CommandObject, session: AsyncSession, settings: Settings):
    (uid,) = _args(command, 1)[:1]
    user = await session.get(User, await _uid(session, uid))
    if user is None:
        raise AppError("not_found", "Игрок не найден")
    left = withdrawals.wager_left(settings, user.total_deposited, user.total_wagered, user.total_bonus)
    await message.answer(
        f"👤 {user_label(user)}\n"
        f"Баланс: <b>{usdt(user.balance)}</b>\n"
        f"Депозиты: {usdt(user.total_deposited)} • Выводы: {usdt(user.total_withdrawn)}\n"
        f"Ставки: {usdt(user.total_wagered)} • Выигрыши: {usdt(user.total_won)} • Бонусы: {usdt(user.total_bonus)}\n"
        f"Отыгрыш до вывода: {usdt(left)}\n"
        f"Реферер: {user.referrer_id or '—'} • Бан: {'да' if user.is_banned else 'нет'}\n"
        f"Регистрация: {user.created_at:%Y-%m-%d %H:%M}"
    )


@router.message(Command("give"))
async def cmd_give(message: Message, command: CommandObject, session: AsyncSession):
    parts = _args(command, 2)
    uid = await _uid(session, parts[0])
    try:
        amount = to_units(parts[1])
    except ValueError:
        raise AppError("usage", f"Сумма в USDT, например 2.5 — получено {parts[1]!r}") from None
    note = parts[2] if len(parts) > 2 else f"admin {message.from_user.id}"
    user = await wallet.lock_user(session, uid, allow_banned=True)
    wallet.apply(session, user, TxKind.admin, amount, ref_type="admin", ref_id=message.from_user.id, note=note)
    await session.commit()
    await message.answer(f"Готово. Баланс {user_label(user)}: <b>{usdt(user.balance)}</b>")


async def _set_ban(message: Message, command: CommandObject, session: AsyncSession, value: bool):
    (uid,) = _args(command, 1)[:1]
    user = await wallet.lock_user(session, await _uid(session, uid), allow_banned=True)
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
        w = await withdrawals.mark_paid(session, int(wid), admin_id)
        status = f"✅ Отправлено {usdt(w.paid_amount)}"
        await notify_user(bot, w.user_id, f"💸 Вывод #{w.id}: {usdt(w.paid_amount)} отправлены на <code>{w.address}</code>")
        await call.answer("Отмечено как отправленное")
    else:
        w = await withdrawals.reject(session, int(wid), admin_id, reason="Отклонено администратором")
        status = "❌ Отклонено, средства возвращены"
        await notify_user(bot, w.user_id, f"Вывод #{w.id} отклонён, {usdt(w.amount)} возвращены на баланс")
        await call.answer("Отклонено")
    await call.message.edit_text(f"{call.message.html_text}\n\n<b>{status}</b> (admin {admin_id})")


@router.message(Command("paid"))
async def cmd_paid(message: Message, command: CommandObject, session: AsyncSession, bot: Bot):
    parts = _args(command, 1)
    w = await withdrawals.mark_paid(session, _int(parts[0]), message.from_user.id,
                                    tx_hash=parts[1] if len(parts) > 1 else None)
    await notify_user(bot, w.user_id, f"💸 Вывод #{w.id}: {usdt(w.paid_amount)} отправлены на <code>{w.address}</code>")
    await message.answer(f"Вывод #{w.id} отмечен отправленным ({usdt(w.paid_amount)})")


@router.message(Command("deposits"))
async def cmd_deposits(message: Message, session: AsyncSession):
    rows = (await session.scalars(
        select(TonDeposit).where(TonDeposit.status == DepositStatus.unmatched).order_by(TonDeposit.id).limit(30)
    )).all()
    if not rows:
        await message.answer("Все переводы зачислены 🎉")
        return
    lines = [f"№{d.id} • {usdt(d.amount)} • «{html.escape((d.comment or '—')[:40])}» • "
             f"<code>{d.tx_hash[:16]}…</code>" for d in rows]
    await message.answer("<b>Переводы без ID игрока</b>\n" + "\n".join(lines) +
                         "\n\nЗачислить: <code>/credit номер #ID_игрока</code>")


@router.message(Command("credit"))
async def cmd_credit(message: Message, command: CommandObject, session: AsyncSession, settings: Settings, bot: Bot):
    ref, who = _args(command, 2)[:2]
    dep, user = await deposits.assign(session, settings, ref.lstrip("№"), await _uid(session, who))
    await notify_user(bot, user.id, f"✅ Пополнение зачислено: <b>+{usdt(dep.amount)}</b>\nБаланс: <b>{usdt(user.balance)}</b>")
    await message.answer(f"Перевод №{dep.id} ({usdt(dep.amount)}) зачислен: {user_label(user)}")
