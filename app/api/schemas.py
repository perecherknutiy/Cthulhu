from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models import Bet, Transaction, Withdrawal


class MeOut(BaseModel):
    id: int
    username: str | None
    first_name: str | None
    balance: int
    total_deposited: int
    total_withdrawn: int
    total_wagered: int
    total_won: int
    wager_left: int
    referral_link: str
    referrals: int


class InvoiceIn(BaseModel):
    amount: int = Field(gt=0)


class InvoiceOut(BaseModel):
    invoice_id: str
    invoice_link: str


class WithdrawIn(BaseModel):
    amount: int = Field(gt=0)


class WithdrawalOut(BaseModel):
    id: int
    amount: int
    paid_amount: int
    status: str
    method: str
    created_at: datetime
    processed_at: datetime | None

    @classmethod
    def of(cls, w: Withdrawal) -> WithdrawalOut:
        return cls(id=w.id, amount=w.amount, paid_amount=w.paid_amount, status=w.status.value, method=w.method,
                   created_at=w.created_at, processed_at=w.processed_at)


class TransactionOut(BaseModel):
    id: int
    kind: str
    amount: int
    balance_after: int
    ref_type: str | None
    ref_id: str | None
    created_at: datetime

    @classmethod
    def of(cls, t: Transaction) -> TransactionOut:
        return cls(id=t.id, kind=t.kind.value, amount=t.amount, balance_after=t.balance_after,
                   ref_type=t.ref_type, ref_id=t.ref_id, created_at=t.created_at)


class PlayIn(BaseModel):
    amount: int = Field(gt=0)
    params: dict[str, Any] = Field(default_factory=dict)


class RevealIn(BaseModel):
    tile: int


class BetOut(BaseModel):
    id: int
    game: str
    amount: int
    payout: int
    multiplier: float
    status: str
    params: dict[str, Any]
    result: dict[str, Any] | None
    client_seed: str
    nonce: int
    server_seed_hash: str
    server_seed: str | None  # только после ротации
    created_at: datetime

    @classmethod
    def of(cls, b: Bet) -> BetOut:
        revealed = b.seed is not None and not b.seed.is_active
        return cls(id=b.id, game=b.game, amount=b.amount, payout=b.payout, multiplier=float(b.multiplier),
                   status=b.status.value, params=b.params, result=b.result if b.status.value != "active" else None,
                   client_seed=b.client_seed, nonce=b.nonce, server_seed_hash=b.seed.server_seed_hash,
                   server_seed=b.seed.server_seed if revealed else None, created_at=b.created_at)


class PlayOut(BaseModel):
    bet: BetOut
    balance: int
    result: dict[str, Any]


class SeedOut(BaseModel):
    server_seed_hash: str
    client_seed: str
    nonce: int


class RotateIn(BaseModel):
    client_seed: str | None = None


class RotateOut(BaseModel):
    previous_server_seed: str
    previous_server_seed_hash: str
    previous_client_seed: str
    previous_nonce: int
    current: SeedOut


class VerifyIn(BaseModel):
    game: str
    server_seed: str
    client_seed: str
    nonce: int = Field(ge=0)
    params: dict[str, Any] = Field(default_factory=dict)
