"""Валюта USDT (сеть TON) вместо звёзд Telegram.

- суммы теперь целые микро-USDT (1 USDT = 1 000 000) — колонки те же, меняется смысл;
- таблицы счетов и платежей в звёздах удалены, вместо них ton_deposits (входящие переводы USDT);
- у заявок на вывод появились адрес кошелька, комиссия и хэш перевода;
- kv — служебные значения (до какой транзакции кошелька дочитали).

ВАЖНО: если в базе уже были балансы в звёздах, они станут микро-USDT (1000 ⭐ → 0.001 USDT).
До запуска проще всего создать базу заново.

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("payments")
    op.drop_table("invoices")
    op.create_table(
        "ton_deposits",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("tx_hash", sa.String(length=96), nullable=False, unique=True),
        sa.Column("lt", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("comment", sa.String(length=256), nullable=True),
        sa.Column("sender", sa.String(length=80), nullable=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("credited_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ton_deposits_lt", "ton_deposits", ["lt"])
    op.create_index("ix_ton_deposits_user_id", "ton_deposits", ["user_id"])
    op.create_index("ix_ton_deposits_status", "ton_deposits", ["status"])
    op.create_table(
        "kv",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.add_column("withdrawals", sa.Column("fee", sa.BigInteger(), server_default="0", nullable=False))
    op.add_column("withdrawals", sa.Column("address", sa.String(length=80), nullable=True))
    op.add_column("withdrawals", sa.Column("tx_hash", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("withdrawals", "tx_hash")
    op.drop_column("withdrawals", "address")
    op.drop_column("withdrawals", "fee")
    op.drop_table("kv")
    op.drop_index("ix_ton_deposits_status", table_name="ton_deposits")
    op.drop_index("ix_ton_deposits_user_id", table_name="ton_deposits")
    op.drop_index("ix_ton_deposits_lt", table_name="ton_deposits")
    op.drop_table("ton_deposits")
    op.create_table(
        "invoices",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "payments",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("invoice_id", sa.String(length=32), sa.ForeignKey("invoices.id"), nullable=True),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("telegram_payment_charge_id", sa.String(length=255), nullable=False, unique=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
    )
