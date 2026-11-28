"""Внутренний ID и ник игрока, фото, ежедневный бонус.

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS users_public_id_seq START WITH 100001")
    # nextval как DEFAULT заполнит существующие строки при добавлении колонки
    op.add_column("users", sa.Column("public_id", sa.BigInteger(), server_default=sa.text("nextval('users_public_id_seq')"),
                                     nullable=False))
    op.create_unique_constraint("users_public_id_key", "users", ["public_id"])
    op.add_column("users", sa.Column("nickname", sa.String(length=20), nullable=True))
    op.add_column("users", sa.Column("photo_url", sa.String(length=512), nullable=True))
    op.add_column("users", sa.Column("total_bonus", sa.BigInteger(), server_default="0", nullable=False))
    op.add_column("users", sa.Column("bonus_claimed_on", sa.Date(), nullable=True))
    op.create_index("uq_users_nickname_lower", "users", [sa.text("lower(nickname)")], unique=True)


def downgrade() -> None:
    op.drop_index("uq_users_nickname_lower", table_name="users")
    op.drop_column("users", "bonus_claimed_on")
    op.drop_column("users", "total_bonus")
    op.drop_column("users", "photo_url")
    op.drop_column("users", "nickname")
    op.drop_constraint("users_public_id_key", "users", type_="unique")
    op.drop_column("users", "public_id")
    op.execute("DROP SEQUENCE IF EXISTS users_public_id_seq")
