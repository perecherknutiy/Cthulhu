"""Минимальный клиент toncenter.com (индексатор TON). Без ключа — 1 запрос в секунду."""
from __future__ import annotations

import base64

import aiohttp
from pytoniq_core import Address, Cell, begin_cell


class ToncenterError(Exception):
    pass


class Toncenter:
    def __init__(self, base_url: str = "https://toncenter.com", api_key: str = "", timeout: float = 15.0):
        self.base = base_url.rstrip("/")
        self.headers = {"X-API-Key": api_key} if api_key else {}
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: aiohttp.ClientSession | None = None

    async def _http(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self.headers, timeout=self.timeout)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _get(self, path: str, params: dict) -> dict:
        http = await self._http()
        async with http.get(self.base + path, params={k: v for k, v in params.items() if v is not None}) as r:
            data = await r.json(content_type=None)
            if r.status != 200:
                raise ToncenterError(f"{path}: HTTP {r.status} {str(data)[:200]}")
            return data

    async def _post(self, path: str, body: dict) -> dict:
        http = await self._http()
        async with http.post(self.base + path, json=body) as r:
            data = await r.json(content_type=None)
            if r.status != 200:
                raise ToncenterError(f"{path}: HTTP {r.status} {str(data)[:200]}")
            return data

    async def transactions(self, account: str, *, start_lt: int | None = None, limit: int = 100,
                           sort: str = "asc") -> list[dict]:
        data = await self._get("/api/v3/transactions",
                               {"account": account, "start_lt": start_lt, "limit": limit, "sort": sort})
        return data.get("transactions") or []

    async def latest_lt(self, account: str) -> int:
        txs = await self.transactions(account, limit=1, sort="desc")
        return int(txs[0]["lt"]) if txs else 0

    async def jetton_wallet_address(self, master: str, owner: str) -> str:
        """Адрес jetton-кошелька владельца — спрашиваем у самого контракта токена (get_wallet_address).

        Подделать ответ контракта нельзя, в отличие от списков индексатора.
        """
        arg = base64.b64encode(begin_cell().store_address(Address(owner)).end_cell().to_boc()).decode()
        errors = []
        try:  # API v2
            data = await self._post("/api/v2/runGetMethod",
                                    {"address": master, "method": "get_wallet_address", "stack": [["tvm.Slice", arg]]})
            res = data.get("result") or {}
            if res.get("exit_code", 0) == 0 and res.get("stack"):
                item = res["stack"][0][1]
                boc = item.get("bytes") if isinstance(item, dict) else item
                return Cell.one_from_boc(base64.b64decode(boc)).begin_parse().load_address().to_str(False).lower()
            errors.append(f"v2: {str(data)[:200]}")
        except Exception as e:  # noqa: BLE001
            errors.append(f"v2: {e}")
        try:  # API v3
            data = await self._post("/api/v3/runGetMethod",
                                    {"address": master, "method": "get_wallet_address",
                                     "stack": [{"type": "slice", "value": arg}]})
            if int(data.get("exit_code", 0)) == 0 and data.get("stack"):
                boc = data["stack"][0]["value"]
                return Cell.one_from_boc(base64.b64decode(boc)).begin_parse().load_address().to_str(False).lower()
            errors.append(f"v3: {str(data)[:200]}")
        except Exception as e:  # noqa: BLE001
            errors.append(f"v3: {e}")
        raise ToncenterError("get_wallet_address: " + " | ".join(errors))
