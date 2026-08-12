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
- Code mit `pytest` testen und mit `ruff check .` linten. Nicht ausgeführte Checks kurz begründen.
- Vor Abschluss den Diff prüfen und offene Arbeiten oder Risiken benennen.
- Kein verbose Output ohne explizite Aufforderung; nur relevante Ergebnisse berichten.
- Die Final Response enthält `Geändert`, `Offen`, `Risiken` und, falls vorhanden, `Commit`.

## Gitflow

Wenn das Arbeitsverzeichnis ein Git-Repository ist:

- Nicht direkt auf `main` arbeiten oder pushen.
- Vor Änderungen Git-Status prüfen.
- `dev` ist ausschließlich Integrations- und Startbasis, keine Arbeitsbranch für Codeänderungen.
- Standard-Arbeitsbasis ist immer `dev`: neue Arbeitsbranches entstehen von `dev`.
- Wenn der Checkout nicht auf `dev` ist, vor neuen Änderungen nach `dev` wechseln, sofern das ohne Verlust oder Konflikt mit lokalen Änderungen möglich ist.
- Wenn lokale Änderungen einen sicheren Wechsel nach `dev` verhindern, stoppen, den Zustand erklären und Flacko entscheiden lassen.
- Jede Arbeitsbranch hat genau einen fachlichen Zweck.
- Eine Branch darf nur Änderungen enthalten, die direkt zu diesem Zweck gehören.
- Keine gemischten Änderungen: keine Nebenfixes, Refactors, Docs-Änderungen oder Cleanup, wenn sie nicht direkt zur Aufgabe gehören.
- Vor jeder Änderung prüfen:
  1. Auf welcher Branch bin ich?
  2. Passt der Branch-Name eindeutig zur Aufgabe?
  3. Sind vorhandene uncommitted Änderungen fachlich Teil derselben Aufgabe?
- Wenn eine dieser Fragen mit Nein oder Unklar beantwortet wird, stoppen und Flacko fragen.
- Vor Branch-Entscheidungen prüfen, ob eine bestehende Branch fachlich zur Aufgabe passt.
- Eine bestehende Branch darf nur weiterverwendet werden, wenn ihr Zweck eindeutig zur aktuellen Aufgabe passt und keine fachfremden Änderungen enthält.
- Wenn eine passende Branch existiert und der aktuelle Commit-/Working-Tree-Stand konfliktfrei dazu passt, diese Branch verwenden.
- Wenn keine passende Branch existiert, eine neue Branch erstellen.
- Der Branch-Typ wird anhand des Prompts gewählt, z. B. `feature/*`, `refactor/*`, `fix/*` oder `docs/*`.
- Branch-Namen müssen den Zweck ausdrücken, z. B. `feature/pool-rebalance-config`, `fix/order-size-validation`, `refactor/exchange-client-boundary` oder `docs/agent-gitflow`.
- Vor neuen Codeänderungen von `dev` aus eine passende Arbeitsbranch verwenden oder erstellen.
- Änderungen, die mehrere Files umfassen, müssen auf einer passenden bestehenden oder neuen Arbeitsbranch umgesetzt werden.
- Direkt auf `dev` sind nur kleine Single-file-Docs-/Guideline-Änderungen erlaubt, die kein Codeverhalten ändern.
- Kleine Änderungen dürfen auf der aktuellen Branch passieren, wenn dadurch kein Commit-Stand vermischt wird und keine Konflikte entstehen.
- Falls andere Branches oder lokale Änderungen noch uncommitted Änderungen enthalten, prüfen, ob sie mit der aktuellen Aufgabe interferieren.
- Wenn diese Änderungen nicht interferieren, kann von `dev` eine neue Branch erstellt werden.
- Wenn sie interferieren könnten oder die Lage unklar ist, stoppen und Flacko um Clarification bitten.
- Wenn während der Arbeit ein unabhängiges Problem auffällt, nicht nebenbei fixen. Stattdessen notieren und separat auf neuer Branch bearbeiten.
- Abgeschlossene Änderungen standardmäßig committen, außer Flacko sagt explizit, dass nicht committet werden soll.
- Commit-Messages beschreiben die Änderung nach Funktionalität, nicht nach Dateinamen.
- Pushen ist nur erlaubt, wenn die relevanten Tests vorher erfolgreich gelaufen sind.
- Änderungen klein und thematisch halten.
- Konflikte mit fremden Branches vermeiden; bei Unsicherheit stoppen und fragen.

## Safety

Keine Live-Trades, keine echten Orders und keine Funds-Bewegung ohne explizite Freigabe von Flacko.
Docker-Builds nur ausführen, wenn ausdrücklich aktiv danach gefragt wird.
