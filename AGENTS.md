# Projekt

`polymarket-market-discovery` ist ein Python-3.12-Service, der Polymarket-Märkte entdeckt, ein kanonisches Market-Universum pflegt und Orderbook-Historie sammelt. Der Service verwendet ausschließlich öffentliche Read-Endpunkte.

## Projektindex

Zur ersten Orientierung im Repository die `INDEX.md` im Repository-Root verwenden.
Wenn sich ein Einstiegspunkt, eine Top-Level-Domain oder ihre Verantwortung ändert, muss `INDEX.md` in derselben Änderung aktualisiert werden.

## Additional Project Context

Code und Konfiguration sind für aktuelles Verhalten maßgeblich. Wenn nicht allgemein bekanntes Projektwissen oder frühere projektspezifische Entscheidungen, Systeme oder Verfahren die Aufgabe beeinflussen können, bei `wiki/index.md` starten und nur relevante aktive Seiten lesen. `wiki/raw/` ist Evidenz. Das Wiki nur auf ausdrückliche Anfrage ändern; davor `wiki/SCHEMA.md` lesen.

## Arbeitsstandard

- Nur ändern, was direkt zur Aufgabe gehört; keine Nebenbei-Refactors oder spekulativen Features.
- Package Manager: `uv`; Projektbefehle mit `uv run` ausführen.
- Tests: `pytest`. Neue Tests nur auf ausdrückliche Anfrage schreiben und anschließend ausführen. Die vollständige Testsuite nur auf ausdrückliche Anfrage starten.
- Linter: `ruff`. Nur geänderte Python-Dateien mit `uv run ruff check <Dateien>` prüfen.
- Zur Verifikation automatisch die kleinste aufgabengerechte Prüfung ausführen: relevante bestehende `pytest`-Tests bei Verhaltensänderungen, andernfalls einen sicheren aufgabenspezifischen Check. Fehlt eine ausführbare Prüfung, den Diff besonders prüfen, das Risiko melden und trotzdem lokal committen.
- Builds wie `uv build` oder Docker nur starten, wenn sie ausdrücklich angefragt sind oder die Aufgabe direkt Build- oder Packaging-Verhalten ändert.
- Ausgaben kurz und auf relevante Ergebnisse beschränkt halten.

## Workflow

Implementieren → verifizieren → linten → Diff prüfen → committen. Fehler beheben und ab der betroffenen Prüfung wiederholen.

## Final Response

Mit einem kurzen Ergebnissatz beginnen. Danach diese durch Leerzeilen getrennten Labels ohne Markdown-Überschriften verwenden:

- `**Changed**`: geänderte Dateien und deren Änderung
- `**Verification**`: ausgeführte Checks
- `**Open / Risks**`: nur bei offenen Arbeiten oder verbleibenden Risiken
- `**Git**`: Branch, Commit und PR-Status kompakt in einer Zeile

## Gitflow

Wenn das Arbeitsverzeichnis ein Git-Repository ist:

- Nie auf `main` arbeiten oder direkt dorthin pushen. `dev` ist die saubere Startbasis, keine Arbeitsbranch.
- Zu Beginn Status und Branches prüfen. Passt eine bestehende saubere Arbeitsbranch eindeutig zur Aufgabe, dort direkt weiterarbeiten.
- Andernfalls von `dev` eine Branch mit genau einem fachlichen Zweck anlegen: `feature/*`, `fix/*`, `refactor/*` oder `docs/*`. Für sequenzielle und kleine Aufgaben im normalen Arbeitsverzeichnis arbeiten.
- Separate Worktrees nur verwenden, wenn mehrere Aufgaben oder Agenten parallel arbeiten.
- Ist die zu verwendende Arbeitsbranch nicht clean oder `dev` beim Anlegen einer neuen Branch nicht clean, vor dem Bearbeiten Flacko fragen, was damit geschehen soll.
- Nur aufgabenbezogene Änderungen committen; unabhängige Funde lediglich als offene Arbeit melden. Abgeschlossene Änderungen standardmäßig lokal mit einer funktionalen Commit-Message committen.
- Working Branch pushen und PR erstellen oder aktualisieren nur auf ausdrückliche Anfrage und nach erfolgreichen relevanten Checks.

## Safety

Keine Live-Trades, keine echten Orders und keine Funds-Bewegung ohne explizite Freigabe von Flacko.
