"""Точка входа: FastAPI (API мини-аппа + вебхук бота) и aiogram в одном процессе.

Запуск:  uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import account, games
from app.bot.setup import configure_bot, create_bot, create_dispatcher
from app.config import Settings, get_settings
from app.db import dispose_engine, get_sessionmaker, init_engine
from app.errors import AppError
from app.ratelimit import RateLimiter
from app.services.games import GameService

log = logging.getLogger("app")
WEBAPP_DIR = Path(__file__).resolve().parent.parent / "webapp"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=logging.DEBUG if settings.debug else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_engine(settings.database_url)
        bot, dp = app.state.bot, app.state.dp
        polling: asyncio.Task | None = None
        if settings.bot_mode != "none":
            await configure_bot(bot, settings)
        if settings.bot_mode == "polling":
            await bot.delete_webhook(drop_pending_updates=False)
            polling = asyncio.create_task(dp.start_polling(
                bot, handle_signals=False, allowed_updates=dp.resolve_used_update_types()))
            log.info("Bot started in polling mode")
        elif settings.bot_mode == "webhook":
            await bot.set_webhook(settings.webhook_url, secret_token=settings.webhook_secret or None,
                                  allowed_updates=dp.resolve_used_update_types())
            log.info("Webhook set to %s", settings.webhook_url)
        watcher_task: asyncio.Task | None = None
        if settings.ton_wallet_address and settings.deposit_watcher:
            from app.ton.toncenter import Toncenter
            from app.ton.watcher import DepositWatcher, bot_notifier

            client = Toncenter(settings.toncenter_url, settings.toncenter_api_key)
            watcher = DepositWatcher(settings, get_sessionmaker(), client, bot_notifier(bot, settings))
            watcher_task = asyncio.create_task(watcher.run())
            log.info("Слежу за пополнениями USDT на %s", settings.ton_wallet_address)
        elif not settings.ton_wallet_address:
            log.warning("TON_WALLET_ADDRESS не задан — пополнение выключено")
        try:
            yield
        finally:
            if watcher_task:
                watcher_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await watcher_task
                await client.close()
            if polling:
                with contextlib.suppress(Exception):
                    await dp.stop_polling()
                polling.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await polling
            await bot.session.close()
            await dispose_engine()

    app = FastAPI(title="ARA Casino API", lifespan=lifespan, docs_url="/docs" if settings.debug else None)
    app.state.settings = settings
    app.state.bot = create_bot(settings)
    app.state.dp = create_dispatcher()
    app.state.games = GameService(settings)
    app.state.bet_limiter = RateLimiter(settings.bets_per_second)

    if settings.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"],
                           allow_headers=["*"])

    @app.exception_handler(AppError)
    async def app_error(_: Request, exc: AppError):
        return JSONResponse({"error": {"code": exc.code, "message": exc.message}}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(x) for x in first.get("loc", []))
        return JSONResponse({"error": {"code": "validation", "message": f"{loc}: {first.get('msg', 'invalid')}"}},
                            status_code=422)

    @app.get("/health")
    async def health():
        return {"ok": True}

    @app.post("/tg/webhook", include_in_schema=False)
    async def tg_webhook(request: Request,
                         x_telegram_bot_api_secret_token: str | None = Header(default=None)):
        if settings.webhook_secret and x_telegram_bot_api_secret_token != settings.webhook_secret:
            return JSONResponse({"ok": False}, status_code=403)
        await app.state.dp.feed_webhook_update(app.state.bot, await request.json())
        return {"ok": True}

    app.include_router(account.router)
    app.include_router(games.router)

    if WEBAPP_DIR.exists():
        app.mount("/", StaticFiles(directory=WEBAPP_DIR, html=True), name="webapp")
    return app

