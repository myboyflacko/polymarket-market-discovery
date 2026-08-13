# Projekt

`polymarket-market-discovery` ist ein Python-3.12-Service, der Polymarket-Märkte entdeckt, ein kanonisches Market-Universum pflegt und Orderbook-Historie sammelt. Der Service verwendet ausschließlich öffentliche Read-Endpunkte.

## Projektindex

- `src/polymarket_market_discovery/cli.py`: CLI-Einstieg für Runs, Scheduling und Datenbank-Setup
- `src/polymarket_market_discovery/settings.py` und `core/`: Konfiguration, Logging, Datenbank und Migrationen
- `src/polymarket_market_discovery/markets/discovery/`: Discovery-Runs, Strategien und Beobachtungen
- `src/polymarket_market_discovery/markets/`: kanonische Market Registry
- `src/polymarket_market_discovery/orderbooks/`: Orderbook-Abruf und Speicherung
- `src/polymarket_market_discovery/polymarket/`: externe Polymarket-API-Grenze
- `tests/`: nach den Source-Domains strukturierte Tests
- `README.md`, `pyproject.toml`, `docker-compose.yml` und `Makefile`: Betrieb, Abhängigkeiten und lokale Kommandos

Wenn sich ein Einstiegspunkt, eine Top-Level-Domain oder ihre Verantwortung ändert, muss der Projektindex in derselben Änderung aktualisiert werden.


## Arbeitsstandard

- Nur ändern, was direkt zur Aufgabe gehört; keine Nebenbei-Refactors oder spekulativen Features.
- Code mit `pytest` testen und mit `ruff check .` linten. Nicht ausgeführte Checks kurz begründen. Run Package mit `uv run`.
- Vor Abschluss den Diff prüfen und offene Arbeiten oder Risiken benennen.
- Kein verbose Output ohne explizite Aufforderung; nur relevante Ergebnisse berichten.
- Die Final Response enthält `Geändert`, `Offen`, `Risiken` und, falls vorhanden, `Commit`.

## Gitflow

Wenn das Arbeitsverzeichnis ein Git-Repository ist:

- Nie auf `main` arbeiten oder direkt dorthin pushen. `dev` ist die saubere Startbasis, keine Arbeitsbranch.
- Zu Beginn Status, Worktrees und Branches prüfen. Passt eine bestehende saubere Arbeitsbranch eindeutig zur Aufgabe, in ihrem Worktree direkt weiterarbeiten.
- Andernfalls von `dev` eine Branch mit genau einem fachlichen Zweck in einem separaten Worktree anlegen: `feature/*`, `fix/*`, `refactor/*` oder `docs/*`.
- Ist der `dev`- oder Ziel-Worktree nicht clean oder enthält fachfremde Änderungen, vor dem Bearbeiten Flacko fragen, was damit geschehen soll.
- Nur aufgabenbezogene Änderungen committen; unabhängige Funde lediglich als offene Arbeit melden. Abgeschlossene Änderungen standardmäßig lokal mit einer funktionalen Commit-Message committen.
- Working Branch pushen und PR erstellen oder aktualisieren nur auf ausdrückliche Anfrage und nach erfolgreichen relevanten Checks.

## Safety

Keine Live-Trades, keine echten Orders und keine Funds-Bewegung ohne explizite Freigabe von Flacko.
Docker-Builds nur ausführen, wenn ausdrücklich aktiv danach gefragt wird.
