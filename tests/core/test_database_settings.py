import pytest

from polymarket_market_discovery.settings import DatabaseSettings


def test_database_settings_builds_postgres_url() -> None:
    settings = DatabaseSettings(
        name="polymarket_market_discovery",
        user="tracker",
        password="secret",
        host="postgres",
        port=5432,
    )

    assert (
        settings.database_url
        == "postgresql+psycopg://tracker:secret@postgres:5432/polymarket_market_discovery"
    )


def test_database_settings_reads_discovery_postgres_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POLYMARKET_DISCOVERY_POSTGRES_DB", "env_db")
    monkeypatch.setenv("POLYMARKET_DISCOVERY_POSTGRES_USER", "env_user")
    monkeypatch.setenv("POLYMARKET_DISCOVERY_POSTGRES_PASSWORD", "env_secret")
    monkeypatch.setenv("POLYMARKET_DISCOVERY_POSTGRES_HOST", "env_postgres")
    monkeypatch.setenv("POLYMARKET_DISCOVERY_POSTGRES_PORT", "5544")

    settings = DatabaseSettings()

    assert settings.name == "env_db"
    assert settings.user == "env_user"
    assert settings.password == "env_secret"
    assert settings.host == "env_postgres"
    assert settings.port == 5544
