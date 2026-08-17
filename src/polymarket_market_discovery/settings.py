from functools import lru_cache
from pathlib import Path

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class ApiSettings(BaseSettings):
    timeout_seconds: float = Field(default=10.0, gt=0)
    rate_limit_retry_attempts: int = Field(default=5, ge=0)
    rate_limit_backoff_seconds: float = Field(default=10.0, ge=0)

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        populate_by_name=True,
        extra="ignore",
    )


class PolymarketDataApiClientSettings(ApiSettings):
    base_url: str = Field(
        default="https://data-api.polymarket.com",
        alias="POLYMARKET_DATA_API_BASE_URL",
    )
    max_concurrent_requests: int = Field(
        default=4, ge=1, alias="POLYMARKET_DATA_API_MAX_CONCURRENT_REQUESTS"
    )
    timeout_seconds: float = Field(
        default=10.0, gt=0, alias="POLYMARKET_DATA_API_TIMEOUT_SECONDS"
    )
    rate_limit_retry_attempts: int = Field(
        default=5, ge=0, alias="POLYMARKET_DATA_API_RATE_LIMIT_RETRY_ATTEMPTS"
    )
    rate_limit_backoff_seconds: float = Field(
        default=60.0, ge=0, alias="POLYMARKET_DATA_API_RATE_LIMIT_BACKOFF_SECONDS"
    )
    positions_requests_per_second: float = Field(
        default=8, gt=0, alias="POLYMARKET_POSITIONS_REQUESTS_PER_SECOND"
    )
    leaderboard_requests_per_second: float = Field(
        default=3, gt=0, alias="POLYMARKET_LEADERBOARD_REQUESTS_PER_SECOND"
    )


class PolymarketGammaApiClientSettings(ApiSettings):
    base_url: str = Field(
        default="https://gamma-api.polymarket.com",
        alias="POLYMARKET_GAMMA_API_BASE_URL",
    )
    timeout_seconds: float = Field(
        default=10.0, gt=0, alias="POLYMARKET_GAMMA_API_TIMEOUT_SECONDS"
    )
    rate_limit_retry_attempts: int = Field(
        default=5, ge=0, alias="POLYMARKET_GAMMA_API_RATE_LIMIT_RETRY_ATTEMPTS"
    )
    rate_limit_backoff_seconds: float = Field(
        default=10.0, ge=0, alias="POLYMARKET_GAMMA_API_RATE_LIMIT_BACKOFF_SECONDS"
    )
    requests_per_second: float = Field(
        default=5, gt=0, alias="POLYMARKET_GAMMA_API_REQUESTS_PER_SECOND"
    )


class PolymarketClobApiClientSettings(ApiSettings):
    base_url: str = Field(
        default="https://clob.polymarket.com",
        alias="POLYMARKET_CLOB_API_BASE_URL",
    )
    timeout_seconds: float = Field(
        default=10.0, gt=0, alias="POLYMARKET_CLOB_API_TIMEOUT_SECONDS"
    )
    rate_limit_retry_attempts: int = Field(
        default=5, ge=0, alias="POLYMARKET_CLOB_API_RATE_LIMIT_RETRY_ATTEMPTS"
    )
    rate_limit_backoff_seconds: float = Field(
        default=10.0, ge=0, alias="POLYMARKET_CLOB_API_RATE_LIMIT_BACKOFF_SECONDS"
    )
    orderbook_requests_per_second: float = Field(
        default=5, gt=0, alias="POLYMARKET_ORDERBOOK_REQUESTS_PER_SECOND"
    )


class DatabaseSettings(BaseSettings):
    name: str = Field(
        default="polymarket_market_discovery",
        alias="POLYMARKET_DISCOVERY_POSTGRES_DB",
    )
    user: str = Field(
        default="polymarket_market_discovery",
        alias="POLYMARKET_DISCOVERY_POSTGRES_USER",
    )
    password: str = Field(
        default="polymarket_market_discovery",
        alias="POLYMARKET_DISCOVERY_POSTGRES_PASSWORD",
    )
    host: str = Field(default="postgres", alias="POLYMARKET_DISCOVERY_POSTGRES_HOST")
    port: int = Field(
        default=5432,
        ge=1,
        le=65535,
        alias="POLYMARKET_DISCOVERY_POSTGRES_PORT",
    )

    @computed_field
    @property
    def database_url(self) -> str:
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.name,
        ).render_as_string(hide_password=False)

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        populate_by_name=True,
        extra="ignore",
    )


class LoggingSettings(BaseSettings):
    level: str = Field(default="INFO", alias="POLYMARKET_DISCOVERY_LOG_LEVEL")

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


class Settings(BaseSettings):
    polymarket_data_api_client: PolymarketDataApiClientSettings = Field(
        default_factory=PolymarketDataApiClientSettings
    )
    polymarket_gamma_api_client: PolymarketGammaApiClientSettings = Field(
        default_factory=PolymarketGammaApiClientSettings
    )
    polymarket_clob_api_client: PolymarketClobApiClientSettings = Field(
        default_factory=PolymarketClobApiClientSettings
    )
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    @property
    def database(self) -> DatabaseSettings:
        return DatabaseSettings()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
