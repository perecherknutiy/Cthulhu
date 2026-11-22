"""Модели БД. Все денежные поля — целые звёзды (BigInteger)."""
from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
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
    payment_refund = "payment_refund"
    referral = "referral"
    admin = "admin"
    bonus = "bonus"


class InvoiceStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    expired = "expired"


class PaymentStatus(str, enum.Enum):
    paid = "paid"
    refunded = "refunded"


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


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)  # telegram user id
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    language_code: Mapped[str | None] = mapped_column(String(16))

    balance: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    total_deposited: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    total_withdrawn: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    total_wagered: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    total_won: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")

    referrer_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Invoice(Base):
    """Наш счёт на пополнение. id уходит в payload инвойса Telegram."""

    __tablename__ = "invoices"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[InvoiceStatus] = mapped_column(_enum(InvoiceStatus), default=InvoiceStatus.pending)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Payment(Base):
    """Фактически полученный платёж в звёздах (successful_payment)."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    invoice_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("invoices.id"))
    amount: Mapped[int] = mapped_column(BigInteger)
    telegram_payment_charge_id: Mapped[str] = mapped_column(String(255), unique=True)
    status: Mapped[PaymentStatus] = mapped_column(_enum(PaymentStatus), default=PaymentStatus.paid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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
    amount: Mapped[int] = mapped_column(BigInteger)
    paid_amount: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[WithdrawalStatus] = mapped_column(_enum(WithdrawalStatus), default=WithdrawalStatus.pending, index=True)
    method: Mapped[str] = mapped_column(String(32))
    admin_id: Mapped[int | None] = mapped_column(BigInteger)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
