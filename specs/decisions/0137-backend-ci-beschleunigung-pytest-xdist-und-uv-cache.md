# 0137 - Backend-CI-Beschleunigung: Testparallelisierung mit `pytest-xdist` im bestehenden Job, dazu ein `uv`-Wheel-Cache

**Status:** Accepted
**Datum:** 2026-11-01
**Bezug:** [GitHub-Issue #603](https://github.com/TheRealKoller/photosort/issues/603), Spec [`../features/0603-backend-ci-beschleunigen.md`](../features/0603-backend-ci-beschleunigen.md)

## Kontext

Der Job `backend` in `.github/workflows/ci.yml` trägt fünf Prüfschritte in fester Reihenfolge
(Formatierung, Lint, mypy, pytest mit Coverage-Gate 80 %) und ist zu lang. Die Kosten zerfallen in
zwei Buckets: (a) Fixkosten vor den Prüfungen — Systempakete für mediapipe/opencv,
`uv pip install --system -e ".[dev]"` (tensorflow, mediapipe, opencv-contrib, onnxruntime) und der
Modell-Asset-Download; (b) die Prüfschritte selbst, deren langer Pol `pytest` mit rund 1540
Testfunktionen in 140 Dateien ist.

Der Testbestand ist parallelisierungstauglich: je Test ein eigenes `tmp_path`, je Test eine eigene
In-Memory-SQLite (`sqlite+aiosqlite:///:memory:`), kein geteilter Dateisystemzustand, keine festen
Ports (der einzige Socket bindet Port 0), Netz- und Gesichtsmodell-Sperren wirken je Prozess. Es
gibt kein `uv.lock`.

## Entscheidung

### 1. Die Beschleunigung trägt die Testparallelisierung im bestehenden Job, nicht eine Job-Aufspaltung

`pytest-xdist` wird als dev-Dependency ergänzt, und der Testschritt wird auf
`pytest -n auto --cov=photosort --cov-report=term-missing --cov-fail-under=80` umgestellt. Alle
übrigen Schritte bleiben unverändert an ihrer Stelle; kein Schritt wird übersprungen oder
abgeschwächt.

**Verworfen: Aufspaltung des `backend`-Jobs** in mehrere Jobs (z.B. je Testgruppe). Ein neuer
Job-Name müsste von Hand in `required_status_checks.contexts` der Branch Protection nachgetragen
werden und blockiert bis dahin nichts (ADR [`0064`](./0064-pr-titel-pruefung-eigener-blockierender-workflow.md)
Abschnitt 6); und der `ruff`-Format-Check liegt bewusst im `backend`-Job (ADR
[`0080`](./0080-maschinelle-formatierung-ruff-format-und-prettier.md) Abschnitt 11). Eine
Aufspaltung brächte damit entweder einen nicht blockierenden oder einen manuell nachzutragenden
Check — beides schlechter als Parallelisierung im selben Job. `-n auto` beschränkt sich auf die
Kerne des Runners (zwei beim Standard-`ubuntu-latest`) und überzeichnet den Runner nicht.

### 2. Das Coverage-Gate bleibt dasselbe

`--cov=photosort` und `--cov-fail-under=80` bleiben unverändert. `pytest-cov` (hier ≥6.0) sammelt
die Coverage je Worker und bewertet das Gate auf dem zusammengeführten Gesamtstand, nicht je
Worker — ein Fehler oder eine Unterschreitung bleibt rot. Es wird kein Test entfernt; die
80 %-Schwelle und die volle Testmenge bleiben unangetastet.

### 3. Die Fixkosten bekommen einen eigenen, risikolosen Hebel: der `uv`-Wheel-Cache

Der dominante Fixkosten-Anteil ist `uv pip install` (tensorflow/mediapipe/opencv werden je Lauf
neu geladen). Der bestehende `actions/cache@v4`-Schritt (schon für die Modell-Assets im Einsatz)
bekommt einen zweiten Eintrag auf `~/.cache/uv`, Schlüssel
`uv-cache-${{ hashFiles('backend/pyproject.toml') }}`. `uv`s Cache ist inhaltsadressiert: ein
abweichender Auflösungsstand führt zu einem Teil-Treffer, nie zu einer falschen Installation. Der
Modell-Asset-Cache bleibt unverändert; die apt-Systempakete bleiben ungecacht (klein, ein eigener
Cache lohnt nicht).

### 4. Vorher/Nachher-Messung

Gemessen werden (a) die Dauer des Schritts `Test (pytest, coverage gate 80%)` und (b) die
Gesamtdauer des `backend`-Jobs, jeweils aus dem GitHub-Actions-Laufprotokoll derselben
Runner-Klasse (`ubuntu-latest`), bei warmem Modell-Asset-Cache. (a) belegt den xdist-Effekt
isoliert, (b) den kombinierten Effekt inklusive `uv`-Cache. Beide Zahlen stehen im PR-Body.

## Begründung

- **`pytest-xdist` statt Job-Aufspaltung:** der einzige Hebel, der den längsten Schritt
  beschleunigt, ohne neuen Job-Namen und ohne manuellen Branch-Protection-Schritt. Der Testbestand
  ist dafür gebaut (je Test isolierte DB und `tmp_path`).
- **Kein Testabbau:** Testentfernung zur Beschleunigung tauscht Aussagekraft gegen eine Konstante;
  xdist erfasst denselben Gewinn multiplikativ, ohne das Coverage-Gate zu berühren. Es fehlt zudem
  jedes Werkzeug, „überflüssig" zuverlässig zu belegen.
- **`uv`-Cache:** greift denselben Lauf an, schwächt keinen Prüfschritt und nutzt den bereits
  vorhandenen `actions/cache`. Die Inhaltsadressierung macht ihn falschheitssicher.

## Konsequenzen

- Neue dev-Dependency `pytest-xdist` in `backend/pyproject.toml`
  (`[project.optional-dependencies] dev`), eine geänderte Testzeile und ein zweiter
  `actions/cache`-Eintrag in `.github/workflows/ci.yml`. Kein neuer Job, kein neuer Required
  Status Check, kein neuer Action-Anbieter.
- Der Coverage-Nachweis bleibt auf dem zusammengeführten Stand wirksam; der Testschritt heißt
  weiterhin `Test (pytest, coverage gate 80%)`.
- `docs/architecture.md` bleibt unberührt (keine Systemarchitektur- oder Datenmodell-Änderung).
  `docs/setup.md` bekommt den Hinweis auf den lokalen Parallel-Lauf, sofern der Testschritt lokal
  nachvollzogen werden soll.
