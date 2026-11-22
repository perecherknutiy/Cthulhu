"""Проверка initData мини-приложения.

https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)
hash       = hex(HMAC_SHA256(key=secret_key, msg=data_check_string))
data_check_string — все поля кроме hash, отсортированные по ключу, в виде "key=value", через \\n.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl

from app.services.users import TgUser


class InitDataError(Exception):
    pass


@dataclass
class WebAppInit:
    user: TgUser
    auth_date: int
    start_param: str | None
    raw: dict[str, str]


def _secret_key(bot_token: str) -> bytes:
    return hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()


def sign_init_data(fields: dict[str, str], bot_token: str) -> str:
    """Подписать initData (для тестов и локальной отладки без Telegram)."""
    from urllib.parse import urlencode

    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    h = hmac.new(_secret_key(bot_token), check.encode(), hashlib.sha256).hexdigest()
    return urlencode({**fields, "hash": h})


def validate_init_data(init_data: str, bot_token: str, max_age: int, now: int | None = None) -> WebAppInit:
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    except ValueError as e:
        raise InitDataError("malformed init data") from e

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise InitDataError("hash is missing")
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    expected = hmac.new(_secret_key(bot_token), check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise InitDataError("bad signature")

    try:
        auth_date = int(pairs.get("auth_date", "0"))
    except ValueError as e:
        raise InitDataError("bad auth_date") from e
    now = now or int(time.time())
    if max_age > 0 and now - auth_date > max_age:
        raise InitDataError("init data expired")

    try:
        u = json.loads(pairs["user"])
        user = TgUser(id=int(u["id"]), username=u.get("username"), first_name=u.get("first_name"),
                      language_code=u.get("language_code"))
    except (KeyError, ValueError, TypeError) as e:
        raise InitDataError("user is missing") from e

    return WebAppInit(user=user, auth_date=auth_date, start_param=pairs.get("start_param"), raw=pairs)
