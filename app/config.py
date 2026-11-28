"""Конфигурация приложения. Все параметры читаются из переменных окружения / .env."""
import os
from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic import BeforeValidator, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from typing_extensions import Annotated

from app.money import to_units

# сумма в USDT из .env ("0.1") → целые микро-USDT (100000)
Units = Annotated[int, BeforeValidator(to_units)]


class Settings(BaseSettings):
    # ENV_FILE="" — не читать .env (так делают тесты, чтобы боевые настройки не влияли на них)
    model_config = SettingsConfigDict(env_file=os.environ.get("ENV_FILE", ".env") or None, env_file_encoding="utf-8",
                                      extra="ignore")

    # --- Telegram ---
    bot_token: str = Field(..., description="Токен бота от @BotFather")
    webapp_url: str = Field("https://example.com", description="Публичный HTTPS URL мини-приложения")
    admin_ids: Annotated[list[int], NoDecode] = Field(default_factory=list)
    bot_mode: Literal["polling", "webhook", "none"] = "polling"
    webhook_url: str = ""  # https://domain/tg/webhook
    webhook_secret: str = ""  # X-Telegram-Bot-Api-Secret-Token

    # --- Infrastructure ---
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/casino"
    debug: bool = False
    initdata_ttl: int = 86400  # сколько секунд считать initData валидной
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # --- Экономика. Валюта — USDT: в .env пишите обычные суммы (0.1, 25, 1000), внутри они хранятся как целые
    #     микро-USDT (1 USDT = 1 000 000) ---
    house_edge: Decimal = Decimal("0.03")
    min_bet: Units = Field(default="0.1")
    max_bet: Units = Field(default="1000")
    max_payout: Units = Field(default="10000")  # максимальный выигрыш с одной ставки
    min_deposit: Units = Field(default="1")  # пополнения меньше — всё равно зачисляются, это подсказка для игрока
    deposit_presets: Annotated[list[int], NoDecode] = Field(default_factory=lambda: ["5", "10", "25", "50", "100", "250"])

    # --- Приём USDT в сети TON (свой кошелёк) ---
    ton_wallet_address: str = ""  # адрес кошелька казино (Tonkeeper и т.п.); пусто — пополнение выключено
    ton_usdt_master: str = "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs"  # официальный USDT в TON
    ton_usdt_jetton_wallet: str = ""  # USDT-кошелёк казино; пусто — бот узнает его у контракта USDT сам
    toncenter_url: str = "https://toncenter.com"
    toncenter_api_key: str = ""  # без ключа toncenter даёт 1 запрос в секунду — для одного кошелька хватает
    ton_poll_seconds: float = 10.0
    deposit_watcher: bool = True  # следить за пополнениями в этом процессе (запускайте ровно в одном экземпляре)

    # --- Вывод ---
    withdraw_min: Units = Field(default="5")
    withdraw_max: Units = Field(default="5000")
    withdraw_fee: Units = Field(default="0")  # комиссия с игрока за вывод (газ сети TON платит казино)
    withdraw_wager_ratio: Decimal = Decimal("1.0")  # нужно проставить депозиты x N перед выводом

    # --- Ежедневный бонус (по умолчанию выключен — это настоящие деньги) ---
    daily_bonus: Units = Field(default="0")  # сколько USDT раз в сутки (UTC); 0 = выключено. Входит в отыгрыш

    # --- Рефералка ---
    referral_deposit_percent: Decimal = Decimal("0")  # % от депозитов реферала, 0 = выключено

    # --- Антиспам ---
    bets_per_second: float = 5.0

    @field_validator("admin_ids", mode="before")
    @classmethod
    def _split_ints(cls, v):
        if isinstance(v, str):
            return [int(x) for x in v.replace(" ", "").split(",") if x]
        if isinstance(v, int):
            return [v]
        return v

    @field_validator("deposit_presets", mode="before")
    @classmethod
    def _split_amounts(cls, v):
        if isinstance(v, str):
            v = [x for x in v.replace(" ", "").split(",") if x]
        return [to_units(x) for x in v]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_strs(cls, v):
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    @property
    def rtp(self) -> Decimal:
        return Decimal(1) - self.house_edge


@lru_cache
def get_settings() -> Settings:
    return Settings()
