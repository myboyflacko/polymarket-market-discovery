# Projekt

`polymarket-market-discovery` ist ein Python-3.12-Service, der Polymarket-Märkte entdeckt, ein kanonisches Market-Universum pflegt und Orderbook-Historie sammelt. Der Service verwendet ausschließlich öffentliche Read-Endpunkte.

## Projektindex

Um das Repository zu erkunden oder sich schnell darin zu bewegen, verwende die `INDEX.md` im Repository-Root.
Wenn sich ein Einstiegspunkt, eine Top-Level-Domain oder ihre Verantwortung ändert, muss `INDEX.md` in derselben Änderung aktualisiert werden.

## Additional Context / Source of Truth

Für projektspezifisches oder nicht allgemein bekanntes Wissen immer das Wiki verwenden: bei `wiki/index.md` starten und den relevanten aktiven Seiten folgen. `wiki/raw/` ist nur Evidenz. Das Wiki nur auf ausdrückliche Anfrage aktualisieren und neue Seiten gemäß `wiki/SCHEMA.md` anlegen.

## Arbeitsstandard

- Nur ändern, was direkt zur Aufgabe gehört; keine Nebenbei-Refactors oder spekulativen Features.
- Package Manager: `uv`; Projektbefehle mit `uv run` ausführen.
- Tests: `pytest`. Neue Tests nur auf ausdrückliche Anfrage schreiben und anschließend ausführen. Die vollständige Testsuite nur auf ausdrückliche Anfrage starten.
- Linter: `ruff`. Nur geänderte Python-Dateien mit `uv run ruff check <Dateien>` prüfen.
- Zur Verifikation automatisch die kleinste aussagekräftige Prüfung ausführen: relevante bestehende `pytest`-Tests, andernfalls einen sicheren Smoke-Check. Fehlt beides, als Risiko melden.
- Builds wie `uv build` oder Docker nur auf ausdrückliche Anfrage starten.
- Ausgaben kurz und auf relevante Ergebnisse beschränkt halten.

## Workflow

Implementieren → verifizieren → linten → Diff prüfen → nach erfolgreichen relevanten Checks committen.

## Final Response

Die Final Response verwendet immer diese Abschnitte; leere Abschnitte werden mit `None` angegeben:

- `### Changed`: geänderte Dateien und deren Änderung
- `### Open`: offene Arbeiten
- `### Risks`: verbleibende Risiken
- `### Git`: Branch, Commit und PR-Status

## Gitflow

Wenn das Arbeitsverzeichnis ein Git-Repository ist:

- Nie auf `main` arbeiten oder direkt dorthin pushen. `dev` ist die saubere Startbasis, keine Arbeitsbranch.
- Zu Beginn Status und Branches prüfen. Passt eine bestehende saubere Arbeitsbranch eindeutig zur Aufgabe, dort direkt weiterarbeiten.
- Andernfalls von `dev` eine Branch mit genau einem fachlichen Zweck anlegen: `feature/*`, `fix/*`, `refactor/*` oder `docs/*`. Für sequenzielle und kleine Aufgaben im normalen Arbeitsverzeichnis arbeiten.
- Separate Worktrees nur verwenden, wenn mehrere Aufgaben oder Agenten parallel arbeiten.
- Ist `dev` oder die passende Arbeitsbranch nicht clean oder enthält fachfremde Änderungen, vor dem Bearbeiten Flacko fragen, was damit geschehen soll.
- Nur aufgabenbezogene Änderungen committen; unabhängige Funde lediglich als offene Arbeit melden. Abgeschlossene Änderungen standardmäßig lokal mit einer funktionalen Commit-Message committen.
- Working Branch pushen und PR erstellen oder aktualisieren nur auf ausdrückliche Anfrage und nach erfolgreichen relevanten Checks.

## Safety

Keine Live-Trades, keine echten Orders und keine Funds-Bewegung ohne explizite Freigabe von Flacko.
