# 0603 - Backend-CI-Beschleunigung

**Status:** Accepted
**Erstellt:** 2026-11-01
**Bezug:** [GitHub-Issue #603](https://github.com/TheRealKoller/photosort/issues/603)

## Ziel

Der CI-Lauf „ci / backend (pull_request)" dauert bei jedem Pull Request spürbar zu lange, sodass
jeder Merge unnötig lange auf sein Ergebnis wartet. Der Lauf soll messbar beschleunigt werden,
ohne dass die Aussagekraft der Prüfungen darunter leidet.

## User Story

Als Entwickler an PhotoSort möchte ich, dass der Backend-CI-Lauf spürbar schneller abgeschlossen
ist, damit ich auf jedem Pull Request kürzer auf das Ergebnis warte und schneller Rückmeldung zu
meinen Änderungen erhalte.

## Akzeptanzkriterien

- [ ] Der Backend-CI-Lauf ist nach der Änderung messbar kürzer als vorher — belegt durch einen
      Vorher/Nachher-Vergleich der Laufzeit unter vergleichbaren Bedingungen. Gemessen werden
      zwei Größen aus dem GitHub-Actions-Laufprotokoll auf derselben Runner-Klasse
      (`ubuntu-latest`) bei warmem Modell-Asset-Cache: (a) Dauer des Schritts
      `Test (pytest, coverage gate 80%)`, (b) Gesamtdauer des `backend`-Jobs. „Kürzer" = beide
      Größen strikt kleiner als auf `origin/main`. Beide Zahlen stehen im PR-Body.
- [ ] Das Coverage-Gate (80 %) bleibt unverändert in Kraft; es wird kein Test entfernt, der
      nötig ist, um diese Schwelle zu halten. Der Testschritt trägt unverändert
      `--cov=photosort --cov-report=term-missing --cov-fail-under=80`; pytest-cov bewertet die
      Schwelle auf dem zusammengeführten Gesamtstand aller Worker.
- [ ] Überflüssige oder doppelte Tests dürfen nur entfernt werden, wenn die betroffene
      Funktionalität weiterhin durch mindestens einen verbleibenden Test abgedeckt bleibt. Für
      diese Story wird kein Test entfernt oder geändert („kein Testdiff").
- [ ] Alle Prüfschritte (Formatierung, Lint, Typprüfung, Tests) laufen weiterhin vollständig
      durch und liefern dasselbe Ergebnis; kein Prüfschritt wird übersprungen oder abgeschwächt,
      um schneller zu werden.
- [ ] Ein grüner Backend-CI-Lauf bedeutet weiterhin, dass sämtliche Backend-Tests erfolgreich
      waren und die Abdeckung mindestens 80 % beträgt; ein Testfehler oder eine Unterschreitung
      lässt den Lauf weiterhin zuverlässig rot werden.

## Datenmodell-Bezug

Keiner. Reine CI-/Build-Konfigurationsänderung ohne Produktcode, Datenmodell oder Architektur.

## Architektur / Umsetzung

**Mechanismus: Testparallelisierung im bestehenden `backend`-Job, nicht Job-Aufspaltung.**
Der lange Pol des Laufs ist der Testschritt (`pytest`, rund 1540 Testfunktionen in 140 Dateien).
Er wird über `pytest-xdist` auf die Kerne des Runners parallelisiert; der Schritt lautet neu

    pytest -n auto --cov=photosort --cov-report=term-missing --cov-fail-under=80

Eine Aufspaltung des Jobs in mehrere Jobs (z.B. je Testgruppe) wird verworfen: neue Job-Namen
müssten von Hand in `required_status_checks.contexts` der Branch Protection nachgetragen werden und
blockierten bis dahin nichts (ADR 0064 Abschnitt 6), und der `ruff`-Format-Check liegt bewusst im
`backend`-Job (ADR 0080 Abschnitt 11). `-n auto` beschränkt sich auf die zwei Kerne des
Standard-Runners und überzeichnet ihn nicht. Alle Prüfschritte (Formatierung, Lint, mypy, Tests)
laufen unverändert und vollständig durch; nur die Test**ausführung** wird parallelisiert, kein
Schritt wird übersprungen oder abgeschwächt. Träger: ADR
[`0137`](../decisions/0137-backend-ci-beschleunigung-pytest-xdist-und-uv-cache.md).

**Coverage-Gate bleibt unverändert in Kraft.** `--cov=photosort` und `--cov-fail-under=80` bleiben
identisch. `pytest-cov` (≥6.0) führt die Coverage der Worker zusammen und bewertet die 80 %-Schwelle
auf dem zusammengeführten Gesamtstand, nicht je Worker — ein Fehler oder eine Unterschreitung lässt
den Lauf weiterhin rot werden. Es wird kein Test entfernt.

**Überflüssige/doppelte Tests werden nicht entfernt.** Das Akzeptanzkriterium erlaubt Entfernung
nur bei fortbestehender Abdeckung; die Beschleunigung wird hier vollständig über Parallelisierung
erreicht, sodass diese Erlaubnis ungenutzt bleibt. Testabbau tauschte Aussagekraft gegen eine
Konstante, die xdist ohnehin multiplikativ erfasst, und es fehlt jedes Werkzeug, „überflüssig"
zuverlässig zu belegen.

**Fixkosten (mediapipe/tensorflow-Install, Model-Download) sind ein eigenes, sekundäres Ziel.**
Der dominante Fixkosten-Anteil ist `uv pip install` (tensorflow/mediapipe/opencv werden je Lauf neu
geladen). Der bestehende `actions/cache@v4`-Schritt bekommt einen zweiten Eintrag auf `~/.cache/uv`
(Schlüssel `uv-cache-${{ hashFiles('backend/pyproject.toml') }}`, direkt vor `Install
dependencies`). `uv`s Cache ist inhaltsadressiert: ein abweichender Auflösungsstand ergibt einen
Teil-Treffer, nie eine falsche Installation. Der Modell-Asset-Cache bleibt unverändert; die
apt-Systempakete bleiben ungecacht (klein, eigener Cache lohnt nicht).

**Messbare Vorher/Nachher-Messung.** Gemessen werden (a) die Dauer des Schritts
`Test (pytest, coverage gate 80%)` und (b) die Gesamtdauer des `backend`-Jobs, jeweils aus dem
GitHub-Actions-Laufprotokoll derselben Runner-Klasse (`ubuntu-latest`) bei warmem
Modell-Asset-Cache. (a) belegt den xdist-Effekt isoliert, (b) den kombinierten Effekt inklusive
`uv`-Cache; beide Zahlen gehen in den PR-Body.

**Betroffene Dateien.**
- `.github/workflows/ci.yml` — Testzeile um `-n auto` erweitert; zweiter `actions/cache`-Eintrag
  (`~/.cache/uv`). Kein neuer Job, kein neuer Required Status Check.
- `backend/pyproject.toml` — `pytest-xdist` in `[project.optional-dependencies] dev`.
- `docs/setup.md` — Hinweis auf den lokalen Parallel-Lauf (`pytest -n auto`).

## UI/UX

nicht relevant — reine CI-/Build-Konfigurationsänderung ohne sichtbare Oberfläche; kein
Frontend-Bezug, keine Anzeige, keine Eingabe (Skip, Schritt 2).

## Security

nicht relevant — keine Auth-, Secret-, Eingabe-, Berechtigungs-, Datenmodell- oder
Datensichtbarkeits-Berührung. `pytest-xdist` und der `uv`-Cache sind reine Build-/Test-Tooling-Änderungen
ohne Laufzeit- oder Netzwerk-Sicherheitsbezug (Skip, Schritt 3).

## Offene Fragen

Keine.

## Out of Scope

- Job-Aufspaltung des `backend`-Jobs (ADR 0064/0080: neue Job-Namen müssten in
  `required_status_checks.contexts` nachgetragen werden).
- Testabbau oder -änderung zur Beschleunigung.
- Beschleunigung des `frontend`-, `demo-scripts`-, `docker-compose-check`- oder `e2e`-Jobs.
- Ein Wall-Clock-Zeitbudget als automatisiertes CI-Gate (die Beschleunigung ist eine Messung,
  kein rot/grün-Gate).

## Entscheidungen

- `architect` konsultiert (Schritt 1): konkreter Bezug zu `.github/workflows/ci.yml`, dem
  Backend-Testbestand und der dev-Dependency `pytest-xdist`. Ansatz: xdist im bestehenden Job +
  `uv`-Cache; neue ADR 0137 angelegt.
- `ux-ui-designer` nicht konsultiert (Schritt 2): kein Frontend-/Oberflächenbezug, kein
  `## Design`-Abschnitt im Issue-Body.
- `security-engineer` nicht konsultiert (Schritt 3): keine Auth-/Secret-/Eingabe-/Datenmodell-/
  Datensichtbarkeits-Berührung.
- `test-engineer` konsultiert (Schritt 3): konkreter Bezug zu testbarem Verhalten (Coverage-Gate,
  Testbestands-Unversehrtheit). Teststrategie unten.

**Teststrategie:** Kein neues Produktverhalten — die Beschleunigung ist eine Vorher/Nachher-Messung
aus dem Actions-Protokoll (Testschritt-Dauer und Gesamtdauer des `backend`-Jobs, gleiche
Runner-Klasse, warmer Modell-Cache; beide Zahlen in den PR-Body). Der TDD-Zwang wird getragen von
einem **statischen Repo-Konsistenztest** in `scripts/tests/` (echter Rot-Grün-Zyklus auf die
`ci.yml`-Form und den `pytest-xdist`-dev-Eintrag: `-n auto` + unveränderte `--cov`-Optionen,
`~/.cache/uv`-Cache-Eintrag, unveränderte Job-Schlüsselmenge und Schrittfolge) plus den drei
Gleichheitsgrößen aus „Nachweis ohne Rot-Grün" (kein Testdiff, identische Testknoten-Menge,
`Stmts`/`Cover` unverändert). Die Unversehrtheit des Coverage-Gates belegen der grüne CI-Lauf und
der lokale Parallel-Lauf (`pytest -n auto … --cov-fail-under=80`), der denselben Testknoten-Satz
und ≥80 % Gesamt-Coverage liefert. Es wird kein Test entfernt oder geändert.
