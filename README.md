# Polymarket Market Discovery

Der Service entdeckt Märkte über austauschbare Strategien, pflegt daraus ein
kanonisches Market-Universum und sammelt Orderbook-Historie für alle aktuell
handelbaren Outcome-Tokens.

Der Service nutzt ausschließlich öffentliche Read-Endpunkte und platziert keine
Orders, führt keine Trades aus und bewegt keine Funds.

## Pipeline

1. **Discovery** speichert jeden Discovery-Run und jede Position append-only. Die
   erste Strategie nimmt die Schnittmenge der Top-25 DAY/OVERALL Leaderboards für
   PnL und Volume.
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
nicht migriert. Der neue Compose-Stack verwendet deshalb ein eigenes Volume.

## CI und lokale Checks

Pull Requests auf `dev` sowie Pull Requests von `dev` auf `main` durchlaufen die
GitHub-Actions-Pipeline `Pull request CI`. Draft-PRs werden erst beim Wechsel auf
„Ready for review“ geprüft. Ein anderer Quellbranch für `main` scheitert bereits
an der Quellbranch-Prüfung. Der Workflow benötigt keine Secrets und veröffentlicht
weder Packages noch Container-Images.

Die Python-Prüfungen lassen sich lokal mit Python 3.12 ausführen:

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install pip==26.1.2
python -m pip install ".[dev,ci]"
pytest
ruff check .
ruff format --check .
python -m build
python -m twine check dist/*
python -m venv /tmp/polymarket-package-smoke
/tmp/polymarket-package-smoke/bin/python -m pip install pip==26.1.2
/tmp/polymarket-package-smoke/bin/python -m pip install dist/*.whl
/tmp/polymarket-package-smoke/bin/polymarket-market-discovery --help
python -m pip_audit .
```

Die Docker-Prüfungen bauen und starten ausschließlich lokale Images. Der Smoke-Test
deaktiviert das Netzwerk und verwendet ein schreibgeschütztes Root-Dateisystem:

```bash
docker compose config --quiet
docker build --tag polymarket-market-discovery:ci .
docker compose build scheduler cli
docker run --rm --network none --read-only --cap-drop ALL \
  --security-opt no-new-privileges \
  --entrypoint polymarket-market-discovery \
  polymarket-market-discovery:ci --help
trivy image --exit-code 1 --ignore-unfixed \
  --severity HIGH,CRITICAL polymarket-market-discovery:ci
```

Für `dev` und `main` muss die Repository-Ruleset bzw. Branch Protection den Check
`Pull request CI / CI` als Required Status Check verlangen. Für beide Branches
werden Pull Requests erzwungen und Bypasses deaktiviert. Auf `main` sind direkte
Pushes gesperrt; der Required Check akzeptiert wegen der Quellbranch-Prüfung nur
`dev` als PR-Quelle. Beim erstmaligen Rollout wird der Workflow zuerst nach `dev`
gemergt, anschließend einmal per `dev`-PR nach `main` übernommen und erst danach
auf beiden Branches als Required Status Check aktiviert.
