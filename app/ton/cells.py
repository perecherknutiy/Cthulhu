"""Разбор сообщения transfer_notification (TEP-74), которое USDT-кошелёк казино шлёт владельцу при поступлении."""
from __future__ import annotations

import base64
from dataclasses import dataclass

from pytoniq_core import Cell

TRANSFER_NOTIFICATION = 0x7362D09C


@dataclass
class JettonIncoming:
    query_id: int
    amount: int  # в минимальных единицах токена (у USDT — микро-USDT)
    sender: str | None  # адрес отправителя (владельца), raw
    comment: str | None


def _comment(slice_) -> str | None:
    try:
        if slice_.remaining_bits < 32:
            return None
        if slice_.load_uint(32) != 0:  # 0 — текстовый комментарий, остальное нам неинтересно
            return None
        return slice_.load_snake_string().strip() or None
    except Exception:  # noqa: BLE001
        return None


def parse_transfer_notification(body_b64: str | None) -> JettonIncoming | None:
    if not body_b64:
        return None
    try:
        s = Cell.one_from_boc(base64.b64decode(body_b64)).begin_parse()
        if s.remaining_bits < 32 or s.load_uint(32) != TRANSFER_NOTIFICATION:
            return None
        query_id = s.load_uint(64)
        amount = s.load_coins()
        sender = s.load_address()
    except Exception:  # noqa: BLE001 — не наше сообщение или битое
        return None
    comment = None
    try:
        # forward_payload: Either Cell ^Cell — 0: данные дальше в этой же ячейке, 1: в ссылке
        if s.remaining_bits >= 1:
            in_ref = s.load_bit()
            payload = s.load_ref().begin_parse() if in_ref else s
            comment = _comment(payload)
        elif s.remaining_refs:
            comment = _comment(s.load_ref().begin_parse())
    except Exception:  # noqa: BLE001
        comment = None
    sender_raw = sender.to_str(is_user_friendly=False).lower() if sender is not None else None
    return JettonIncoming(query_id=query_id, amount=int(amount), sender=sender_raw, comment=comment)
