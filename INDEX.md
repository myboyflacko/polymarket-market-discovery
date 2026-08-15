# Project Index

| path | description |
| --- | --- |
| `src/polymarket_market_discovery/cli.py` | CLI-Einstieg für Runs, Scheduling und Datenbank-Setup |
| `src/polymarket_market_discovery/settings.py` | Service-Konfiguration |
| `src/polymarket_market_discovery/core/` | Logging, Datenbank und Migrationen |
| `src/polymarket_market_discovery/discovery/` | Discovery-Runs, Strategien und Beobachtungen |
| `src/polymarket_market_discovery/markets/` | Kanonische Market Registry |
| `src/polymarket_market_discovery/orderbooks/` | Orderbook-Abruf und Speicherung |
| `src/polymarket_market_discovery/pipeline/` | Sequenzielle Initialisierung, Kaskaden und feste Layer-Intervalle |
| `src/polymarket_market_discovery/polymarket/` | Externe Polymarket-API-Grenze |
| `tests/` | Nach den Source-Domains strukturierte Tests |
| `README.md` | Nutzung und Betrieb |
| `pyproject.toml` | Python-Projektkonfiguration und Abhängigkeiten |
| `alembic.ini` | Alembic-Migrationskonfiguration |
| `Dockerfile` | Container-Image des Services |
| `docker-compose.yml` | Lokale Service-Infrastruktur |
| `Makefile` | Lokale Entwicklungs- und Betriebskommandos |
