"""Конфигурация приложения. Все параметры читаются из переменных окружения / .env."""
from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from typing_extensions import Annotated


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

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

    # --- Экономика (все суммы — в звёздах, целые) ---
    house_edge: Decimal = Decimal("0.03")
    min_bet: int = 10
    max_bet: int = 10_000
    max_payout: int = 500_000  # максимальный выигрыш с одной ставки
    min_deposit: int = 50
    max_deposit: int = 10_000  # держите в пределах лимита Telegram на один платёж в XTR
    deposit_presets: Annotated[list[int], NoDecode] = Field(default_factory=lambda: [50, 100, 250, 500, 1000, 2500])

    # --- Вывод ---
    withdraw_min: int = 100
    withdraw_max: int = 100_000
    withdraw_wager_ratio: Decimal = Decimal("1.0")  # нужно проставить депозиты x N перед выводом
    payout_method: Literal["manual", "gifts"] = "manual"

    # --- Рефералка ---
    referral_deposit_percent: Decimal = Decimal("0")  # % от депозитов реферала, 0 = выключено

    # --- Антиспам ---
    bets_per_second: float = 5.0

    @field_validator("admin_ids", "deposit_presets", mode="before")
    @classmethod
    def _split_ints(cls, v):
        if isinstance(v, str):
            return [int(x) for x in v.replace(" ", "").split(",") if x]
        if isinstance(v, int):
            return [v]
        return v

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
