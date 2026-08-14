# Polymarket Market Discovery

Der Service entdeckt Märkte über austauschbare Strategien, pflegt daraus ein
kanonisches Market-Universum und sammelt Orderbook-Historie für alle aktuell
handelbaren Outcome-Tokens.

Der Service nutzt ausschließlich öffentliche Read-Endpunkte und platziert keine
Orders, führt keine Trades aus und bewegt keine Funds.

## Pipeline

1. **Discovery** speichert jeden Discovery-Run und jede von einer Strategie
   beobachtete Market-Evidenz append-only. Mehrere Evidenztreffer derselben
   Strategie werden pro Market aggregiert. Die erste Strategie nimmt die
   Schnittmenge der Top-25 DAY/OVERALL Leaderboards für PnL und Volume.
2. **Market Registry** dedupliziert über `condition_id` und aktualisiert Status,
   Enddatum sowie beide Outcome-Tokens über Gamma. Neue, unbekannte und alle noch
   nicht terminalen Märkte werden erneut geprüft.
3. **Orderbooks** sammeln beide Tokens aller kanonischen Märkte mit
   `active=true`, `closed=false`, `archived=false` und `enable_order_book=true`.

Discovery-Historie wird nie als Collection-Universum interpretiert. Ein einmal
entdeckter Markt bleibt in der Registry, bis Gamma seinen aktuellen Status ändert.

## Start

```bash
cp .env.example .env
docker compose up -d postgres
docker compose --profile tools run --rm cli init-db
docker compose up -d scheduler
```

Einzelne oder alle Layer lassen sich über dieselbe CLI starten:

```bash
polymarket-market-discovery run discovery
polymarket-market-discovery run markets
polymarket-market-discovery run orderbooks
polymarket-market-discovery run all

polymarket-market-discovery schedule discovery
polymarket-market-discovery schedule markets
polymarket-market-discovery schedule orderbooks
polymarket-market-discovery schedule all
```

`--strategy` ist wiederholbar; ohne Angabe laufen alle registrierten Strategien.
`run all` arbeitet fail-fast in der Reihenfolge Discovery, Markets, Orderbooks.
Alle Layer teilen einen PostgreSQL Advisory Lock, damit Discovery/Registry und
Orderbook-Sammlung nicht gleichzeitig schreiben.

## Tabellen

| Bereich | Tabellen |
| --- | --- |
| Discovery | `market_discovery_runs`, `market_discovery_observations` |
| Registry | `market_registry_sync_runs`, `polymarket_markets`, `polymarket_tokens`, `market_status_snapshots` |
| Orderbooks | `orderbook_collection_runs`, `orderbook_collection_items`, `orderbook_snapshots` |

Dies ist eine neue Datenbank-Baseline. Alte Watchlist-Tabellen oder Views werden
nicht migriert. Bestehende Datenbanken und Compose-Volumes müssen deshalb vor der
Initialisierung neu erstellt werden.
