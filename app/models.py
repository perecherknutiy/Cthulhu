"""Модели БД. Все денежные поля — целые микро-USDT (BigInteger, 1 USDT = 1 000 000), см. app/money.py."""
from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Sequence,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _enum(e: type[enum.Enum]) -> Enum:
    # native_enum=False — хранится как VARCHAR, новые значения не требуют ALTER TYPE
    return Enum(e, native_enum=False, length=32, values_callable=lambda x: [i.value for i in x])


class TxKind(str, enum.Enum):
    deposit = "deposit"
    bet = "bet"
    win = "win"
    withdrawal = "withdrawal"
    withdrawal_refund = "withdrawal_refund"
    referral = "referral"
    admin = "admin"
    bonus = "bonus"


class DepositStatus(str, enum.Enum):
    credited = "credited"  # зачислено игроку
    unmatched = "unmatched"  # комментарий не подошёл — ждёт ручного зачисления (/credit)
    ignored = "ignored"  # админ решил не зачислять


class BetStatus(str, enum.Enum):
    active = "active"  # многошаговая игра в процессе (mines)
    won = "won"
    lost = "lost"


class WithdrawalStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    rejected = "rejected"
    failed = "failed"


PUBLIC_ID_SEQ = Sequence("users_public_id_seq", start=100001)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)  # telegram user id
    # внутренний ID игрока: его видно в профиле и в реферальной ссылке вместо Telegram ID
    public_id: Mapped[int] = mapped_column(BigInteger, PUBLIC_ID_SEQ, server_default=PUBLIC_ID_SEQ.next_value(),
                                           unique=True)
    nickname: Mapped[str | None] = mapped_column(String(20))  # None — ещё не выбран
    photo_url: Mapped[str | None] = mapped_column(String(512))
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    language_code: Mapped[str | None] = mapped_column(String(16))

    balance: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    total_deposited: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    total_withdrawn: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    total_wagered: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    total_won: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    total_bonus: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")  # ежедневные бонусы
    bonus_claimed_on: Mapped[date | None] = mapped_column(Date)  # дата (UTC) последнего бонуса

    referrer_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        # ник уникален без учёта регистра
        Index("uq_users_nickname_lower", text("lower(nickname)"), unique=True),
    )


class TonDeposit(Base):
    """Входящий перевод USDT на кошелёк казино (сеть TON). Один перевод = одна строка, повторно не зачисляется."""

    __tablename__ = "ton_deposits"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tx_hash: Mapped[str] = mapped_column(String(96), unique=True)  # хэш транзакции кошелька казино
    lt: Mapped[int] = mapped_column(BigInteger, index=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    comment: Mapped[str | None] = mapped_column(String(256))
    sender: Mapped[str | None] = mapped_column(String(80))  # адрес отправителя, raw
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    status: Mapped[DepositStatus] = mapped_column(_enum(DepositStatus), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    credited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class KV(Base):
    """Служебные значения (например, до какой транзакции кошелька мы уже дочитали)."""

    __tablename__ = "kv"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Transaction(Base):
    """Леджер: любая смена баланса = одна запись. sum(amount) по юзеру == users.balance."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    kind: Mapped[TxKind] = mapped_column(_enum(TxKind))
    amount: Mapped[int] = mapped_column(BigInteger)  # со знаком
    balance_after: Mapped[int] = mapped_column(BigInteger)
    ref_type: Mapped[str | None] = mapped_column(String(32))
    ref_id: Mapped[str | None] = mapped_column(String(64))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_transactions_user_id_id", "user_id", "id"),)


class Seed(Base):
    """Пара сидов provably fair. Хэш server_seed показывается заранее, сам сид — после ротации."""

    __tablename__ = "seeds"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    server_seed: Mapped[str] = mapped_column(String(64))
    server_seed_hash: Mapped[str] = mapped_column(String(64))
    client_seed: Mapped[str] = mapped_column(String(64))
    nonce: Mapped[int] = mapped_column(Integer, default=0)  # следующий неиспользованный nonce
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("uq_seeds_active_user", "user_id", unique=True, postgresql_where=text("is_active")),
    )


class Bet(Base):
    __tablename__ = "bets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    game: Mapped[str] = mapped_column(String(32))
    amount: Mapped[int] = mapped_column(BigInteger)
    payout: Mapped[int] = mapped_column(BigInteger, default=0)
    multiplier: Mapped[Decimal] = mapped_column(Numeric(20, 6), default=Decimal(0))
    status: Mapped[BetStatus] = mapped_column(_enum(BetStatus))
    params: Mapped[dict] = mapped_column(JSONB, default=dict)
    state: Mapped[dict | None] = mapped_column(JSONB)  # скрытое состояние (позиции мин и т.п.)
    result: Mapped[dict | None] = mapped_column(JSONB)

    seed_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("seeds.id"))
    client_seed: Mapped[str] = mapped_column(String(64))
    nonce: Mapped[int] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    seed: Mapped[Seed] = relationship(lazy="joined")

    __table_args__ = (
        Index("ix_bets_user_id_id", "user_id", "id"),
        # не больше одной активной многошаговой игры каждого типа на юзера
        Index("uq_bets_active_user_game", "user_id", "game", unique=True, postgresql_where=text("status = 'active'")),
    )


class Withdrawal(Base):
    __tablename__ = "withdrawals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    amount: Mapped[int] = mapped_column(BigInteger)  # списано с баланса
    fee: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")  # к отправке = amount - fee
    paid_amount: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[WithdrawalStatus] = mapped_column(_enum(WithdrawalStatus), default=WithdrawalStatus.pending, index=True)
    method: Mapped[str] = mapped_column(String(32), default="ton")
    address: Mapped[str | None] = mapped_column(String(80))  # куда отправить USDT (TON, user-friendly)
    tx_hash: Mapped[str | None] = mapped_column(String(128))  # хэш отправки, если админ его указал
    admin_id: Mapped[int | None] = mapped_column(BigInteger)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
