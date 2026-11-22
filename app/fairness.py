"""Provably fair.

Схема (совместима с общепринятой у крипто-казино):
  * сервер заранее генерирует server_seed и показывает игроку sha256(server_seed);
  * игрок может задать свой client_seed;
  * каждая ставка использует nonce = 0, 1, 2, ...;
  * случайные байты: HMAC_SHA256(key=server_seed, msg=f"{client_seed}:{nonce}:{cursor}"), cursor = 0, 1, ...
  * из каждых 4 байт получаем float в [0, 1): b0/256 + b1/256^2 + b2/256^3 + b3/256^4.
После ротации сида игрок получает server_seed и может пересчитать любую свою ставку.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from collections.abc import Iterator


def new_server_seed() -> str:
    return secrets.token_hex(32)


def new_client_seed() -> str:
    return secrets.token_hex(8)


def hash_seed(server_seed: str) -> str:
    return hashlib.sha256(server_seed.encode()).hexdigest()


class FairRng:
    """Детерминированный генератор чисел для одной ставки."""

    def __init__(self, server_seed: str, client_seed: str, nonce: int):
        self.server_seed = server_seed
        self.client_seed = client_seed
        self.nonce = nonce
        self._floats = self._float_stream()

    def _bytes_stream(self) -> Iterator[int]:
        cursor = 0
        key = self.server_seed.encode()
        while True:
            msg = f"{self.client_seed}:{self.nonce}:{cursor}".encode()
            yield from hmac.new(key, msg, hashlib.sha256).digest()
            cursor += 1

    def _float_stream(self) -> Iterator[float]:
        stream = self._bytes_stream()
        while True:
            b = [next(stream) for _ in range(4)]
            yield b[0] / 256 + b[1] / 256**2 + b[2] / 256**3 + b[3] / 256**4

    def float(self) -> float:
        """Следующее число в [0, 1)."""
        return next(self._floats)

    def floats(self, n: int) -> list[float]:
        return [self.float() for _ in range(n)]

    def int_below(self, n: int) -> int:
        """Целое в [0, n)."""
        return int(self.float() * n)

    def shuffle(self, items: list) -> list:
        """Детерминированная перестановка (Fisher–Yates «с выбором без возвращения»)."""
        pool = list(items)
        out = []
        while pool:
            out.append(pool.pop(self.int_below(len(pool))))
        return out
