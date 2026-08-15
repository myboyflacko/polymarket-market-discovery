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

Ein Pipeline Coordinator führt den initialen Lauf sequenziell als Discovery →
Market Registry → Orderbooks aus. Danach laufen Discovery und Registry auf
festen 15-Minuten-Deadlines, Orderbooks alle 5 Minuten. Erfolgreiche Läufe
kaskadieren in den jeweils nachgelagerten Layer, ohne feste Deadlines zu verschieben.

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

polymarket-market-discovery schedule
```

`--strategy` ist wiederholbar; ohne Angabe laufen alle registrierten Strategien.
`run all` arbeitet sequenziell und fasst Layer-Fehler in einem Pipeline-Ergebnis
zusammen. Der Scheduler nutzt standardmäßig Intervalle von 900, 900 und 300
Sekunden; verpasste Ticks werden einmal zusammengefasst, ohne Catch-up-Bursts.
Orderbooks verwenden die kanonischen Tabellen `polymarket_markets` und
`polymarket_tokens`. Der letzte erfolgreiche Registry-Sync darf höchstens zweimal
so alt wie das Registry-Intervall sein. Manuelle Runs nutzen standardmäßig 1800
Sekunden; `--market-registry-max-age-seconds` überschreibt diesen Wert. Eine
frische persistierte Registry bleibt bei vorgelagerten Fehlern nutzbar.
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
