# Setup

Anleitung zum lokalen Entwickeln und Ausprobieren von PhotoSort.

## Quick Start (Entwicklung)

```bash
cp .env.example .env
docker compose up --build
```

- Backend: http://localhost:8000 (`/health`)
- Frontend: http://localhost:8080 (per `docker compose up`, statisch über nginx gebaut; der Vite-Dev-Server aus `npm run dev` läuft dagegen auf http://localhost:5173 — beide Origins sind in `CORS_ALLOWED_ORIGINS`/`VITE_API_BASE_URL` in `.env.example` standardmäßig berücksichtigt)

Bis auf `/health` und `POST /auth/login` verlangt die API ein gültiges Login (siehe [`specs/decisions/0005-auth-implementation.md`](../specs/decisions/0005-auth-implementation.md)). Die beiden Konten werden beim ersten Start per Alembic-Seed-Migration aus `AUTH_SEED_USER1_*`/`AUTH_SEED_USER2_*` (siehe `.env.example`) angelegt.

Das Frontend ruft die API cross-origin auf und braucht dafür zwei zusammenspielende Einstellungen aus `.env.example`: `VITE_API_BASE_URL` (Basis-URL der API aus Sicht des Browsers, wird zur Build-Zeit ins statische Frontend-Bundle eingebacken) und `CORS_ALLOWED_ORIGINS` (welche Frontend-Origin(s) das Backend akzeptiert). Die Defaults passen zueinander und funktionieren ohne weitere Anpassung für `docker compose up --build` auf `localhost`; für einen Deploy hinter einem eigenen Reverse-Proxy (TLS-Terminierung liegt außerhalb dieses Repos, siehe [`architecture.md`](./architecture.md)) beide Werte auf die tatsächlich öffentlich erreichbaren Origins anpassen.

### Tests

```bash
cd backend && pytest
cd frontend && npm test
```

## GitHub-CLI (`gh`)

Der gesamte Story-Lebenszyklus des Projekts — Story-Issue anlegen, Issue-Body schreiben,
Board-Status setzen, eine Feature-Spec finalisieren — läuft über
[`scripts/gh-board.py`](../scripts/gh-board.py) und damit über die GitHub-CLI `gh`. Ohne sie ist
keiner dieser Schritte ausführbar: `python3 scripts/gh-board.py doctor` meldet dann `gh_binary`
als fehlgeschlagen und führt die davon blockierten Lebenszyklus-Schritte einzeln auf. `gh` ist
also nicht optionales Komfortwerkzeug, sondern Voraussetzung des Entwicklungsablaufs (siehe
[`ai-workflow.md`](./ai-workflow.md)).

**Mindestversion:** gepflegt als Konstante `MIN_GH_VERSION` in `scripts/gh-board.py`. Das ist der
autoritative Wert — hier steht bewusst keine zweite Zahl im Text, die davon abweichen könnte.

**Warum die Distributions-Paketquelle nicht genügt:** Ubuntu liefert `gh` 2.45.x. Das Feld
`closingIssuesReferences` in `gh pr view --json` — die Vorbedingung, an der `finalize` laut
[ADR 0046](../specs/decisions/0046-pr-issue-verknuepfung-closing-keyword.md) die
PR-Issue-Verknüpfung prüft — kennt `gh` erst ab der in `MIN_GH_VERSION` festgehaltenen Version.
`apt install gh` verdeckt das Problem deshalb, statt es zu lösen: `gh` ist vorhanden, `finalize`
bricht trotzdem ab. Zu beziehen ist `gh` daher immer als Release-Artefakt des Herausgebers, nicht
aus der Paketquelle der Distribution.

**Lokale Installation:** über die offizielle Bezugsquelle des Herausgebers —
[Installationswege](https://github.com/cli/cli#installation) bzw. direkt die
[Releases](https://github.com/cli/cli/releases). Danach einmalig `gh auth login`; `gh --version`
zeigt die installierte Version, `python3 scripts/gh-board.py doctor` prüft sie gegen
`MIN_GH_VERSION` mit.

**Remote-/Cloud-Umgebungen:** dort brachte eine frisch gestartete Session `gh` bisher nicht mit
(`command not found`, alle `doctor`-Prüfungen scheitern an dieser einen Ursache). Die
Bereitstellung liegt bewusst **nicht** im Repository, sondern im **Setup-Script der
Cloud-Umgebung**: gepflegt in deren Weboberfläche, einmalig beim Einrichten der Umgebung
ausgeführt, Ergebnis als Filesystem-Snapshot gecacht (Begründung und Abwägung in
[ADR 0053](../specs/decisions/0053-gh-bereitstellung-per-umgebungs-setup-script.md)). Der Block
unten ist der Wortlaut, der dort einzutragen ist; **danach die Umgebung neu aufbauen**, damit der
Snapshot den Zustand aufnimmt. An lokalen Arbeitsplätzen ändert sich dadurch nichts — es gibt
keine eingecheckte Datei, die Sessionverhalten steuert, und keinen Eingriff in eine vorhandene
Installation.

> **Referenztext — wird nicht ausgeführt.** Dieser Block ist die dokumentierte Fassung eines
> Artefakts, das ausschließlich in der Weboberfläche der Cloud-Umgebung lebt. Er wird von
> niemandem aus dem Repository heraus ausgeführt: nicht von einem Skript, nicht von der Umgebung
> beim Provisionieren und auch nicht von einem Agenten, der diese Datei liest. Er ist hier
> festgehalten, damit eine neu angelegte Umgebung ohne Rekonstruktion aus dem Gedächtnis wieder
> einzurichten ist.

```bash
set -euo pipefail

# Muss zu MIN_GH_VERSION in scripts/gh-board.py passen (siehe docs/setup.md).
GH_VERSION="2.72.0"

SUDO=""; [ "$(id -u)" -eq 0 ] || SUDO="sudo"

need_install=1
if command -v gh >/dev/null 2>&1; then
  have="$(gh --version | head -n1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -n1)"
  # sort -V vergleicht numerisch: 2.9.0 ist aelter als 2.72.0, ein String-Vergleich sagt das Gegenteil.
  if [ -n "$have" ] && [ "$(printf '%s\n%s\n' "$GH_VERSION" "$have" | sort -V | head -n1)" = "$GH_VERSION" ]; then
    need_install=0
    echo "gh $have liegt bereits vor (>= $GH_VERSION), keine Installation."
  fi
fi

if [ "$need_install" -eq 1 ]; then
  case "$(uname -m)" in
    x86_64) arch=amd64 ;;
    aarch64|arm64) arch=arm64 ;;
    *) echo "Nicht unterstuetzte Architektur: $(uname -m)" >&2; exit 1 ;;
  esac

  asset="gh_${GH_VERSION}_linux_${arch}.tar.gz"
  base="https://github.com/cli/cli/releases/download/v${GH_VERSION}"
  tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT

  curl -fsSL --proto '=https' --proto-redir '=https' --tlsv1.2 --max-time 180 -o "$tmp/$asset" "$base/$asset"
  curl -fsSL --proto '=https' --proto-redir '=https' --tlsv1.2 --max-time 60 -o "$tmp/checksums.txt" \
    "$base/gh_${GH_VERSION}_checksums.txt"
  ( cd "$tmp" && awk -v a="$asset" '$2 == a' checksums.txt | sha256sum -c - )

  tar -xzf "$tmp/$asset" -C "$tmp" "gh_${GH_VERSION}_linux_${arch}/bin/gh"
  $SUDO install -m 0755 "$tmp/gh_${GH_VERSION}_linux_${arch}/bin/gh" /usr/local/bin/gh
fi

gh --version
```

**Pflichtschritt bei jeder Anhebung von `MIN_GH_VERSION`:** den Block hier **und** das
Setup-Script in der Weboberfläche nachziehen. Die Zielversion existiert zwangsläufig an zwei
Orten — als Konstante im Code und als `GH_VERSION` in der Umgebungs-Konfiguration —, weil das
Setup-Script in sich abgeschlossen ist und `scripts/gh-board.py` nicht lesen kann.
**Maßgeblich ist `MIN_GH_VERSION`.** Den Übergang Code → Doku sichert ein Test in CI
(`scripts/tests/test_setup_docs.py`): Er liest `GH_VERSION` aus dem Block oben und stellt ihn
gegen die Konstante, der Lauf wird bei Abweichung sofort rot. Ungesichert bleibt allein der letzte
Schritt, die Übertragung Doku → Weboberfläche.

**Woran ein Auseinanderlaufen auffällt,** wenn dieser letzte Schritt einmal vergessen wird:
`python3 scripts/gh-board.py doctor` meldet die Prüfung `gh_version` als fehlgeschlagen und nennt
beide Zahlen (gefundene Version und `MIN_GH_VERSION`), `abschluss-finalisieren` erscheint unter
`blocked_lifecycle_steps`, und `finalize` selbst bricht mit einer Meldung ab, die die
Mindestversion ausdrücklich nennt — und zwar **vor** jedem Schreibzugriff auf Spec-Datei und
Board, es ist also nichts zurückzunehmen. Die Board-Werkzeuge installieren dabei nichts nach: sie
melden den Zustand und reparieren ihn nicht.

## Cloud-Bilderkennung (optional)

Zwei Kriterien/Funktionen verlassen den Homeserver — beide über denselben, projektweiten
Einwilligungs-Schalter gegated (`Project.cloud_vision_detection_enabled`, Settings-Seite
`/projects/:id/settings`): das Kriterium "Sehenswürdigkeit" (`landmark`, siehe
[`specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md`](../specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md),
[`specs/decisions/0025-cloud-landmark-erkennung.md`](../specs/decisions/0025-cloud-landmark-erkennung.md))
und die optionale Remote-Kategorie-Klassifizierung (offene Schlagworte statt eines festen
Kategorie-Enums, siehe [`specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md`](../specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md),
[`specs/decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md`](../specs/decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md)).
Beide sind ein direkter `httpx`-Aufruf gegen die Anthropic Messages API (Default) oder wahlweise
gegen die Mistral Chat Completions API ([`specs/features/0054-mistral-provider-option-cloud-landmark.md`](../specs/features/0054-mistral-provider-option-cloud-landmark.md),
[`specs/decisions/0031-mistral-provider-option-cloud-landmark.md`](../specs/decisions/0031-mistral-provider-option-cloud-landmark.md)).
Für den Quick-Start/Demo-Stack **nicht nötig**: der Schalter ist projektweit per Default
deaktiviert (`PUT /projects/{id}/cloud-vision-consent`), ohne aktivierte Einwilligung wird kein
API-Key verwendet und kein Netzwerkaufruf ausgeführt (die Env-Variablen selbst werden wie jede
andere `Settings`-Konfiguration bereits beim Prozessstart eingelesen, das ist unabhängig von
Einwilligung/Provider). Die Remote-Kategorie-Klassifizierung braucht zusätzlich ein lokales,
gepinntes Text-Embedding-Modell (`onnxruntime`+`tokenizers`, keine Cloud-Abhängigkeit zur
Laufzeit). Das ONNX-Modell-Asset selbst überschreitet GitHubs 100-MB-Push-Limit und ist daher
**nicht** im Repository eingecheckt (siehe [`specs/decisions/0033-modell-asset-download-statt-commit-label-embedder.md`](../specs/decisions/0033-modell-asset-download-statt-commit-label-embedder.md)) —
`docker compose up --build` lädt es automatisch beim Image-Build (`backend/Dockerfile` ruft
`scripts/fetch-label-embedder-model.sh` auf, SHA256-verifiziert). Nur für ein Bare-Metal-Dev-Setup
ohne Docker (`pip install -e .` direkt im `backend/`-Ordner) einmalig manuell nötig:

```bash
scripts/fetch-label-embedder-model.sh
```

Um beide Funktionen tatsächlich zu nutzen, in `.env`:

- `LANDMARK_PROVIDER` wählt den Cloud-Provider (für beide Funktionen gemeinsam, kein separates
  Setting) — `anthropic` (Default, USA, DPA-/Datenschutzlage geklärt siehe ADR 0025) oder
  `mistral` (EU-hosted Alternative, Sitz Frankreich; DPA-/Zero-Data-Retention-Lage für
  Privatkonten laut Recherche unklar, bewusst akzeptiertes Restrisiko siehe ADR 0031). Eine reine
  Betreiber-/Deployment-Entscheidung, kein Feld pro Projekt.
- Je nach gewähltem Provider `ANTHROPIC_API_KEY` bzw. `MISTRAL_API_KEY` auf einen echten API-Key
  setzen (leer = beide Funktionen bleiben für alle Projekte unbenutzbar, auch bei aktivierter
  Einwilligung schlägt der Aufruf dann fehl).
- Optional `LANDMARK_API_CONCURRENCY` (Default `2`) anpassen — Obergrenze der parallelen Anfragen
  für `landmark`.
- Optional `REMOTE_CATEGORY_CLASSIFICATION_CONCURRENCY` (Default `2`) anpassen — eigenständige
  Obergrenze für die Remote-Kategorie-Klassifizierung (unabhängig von `LANDMARK_API_CONCURRENCY`,
  da dieser Job auf einem größeren, ungefilterten Kandidatenpool läuft).

Danach die Einwilligung für das jeweilige Projekt einmalig über die Settings-Seite
(`/projects/:id/settings`) aktivieren.

## Lokal ausprobieren ohne echten OpenCloud-Server

Für einen ersten Eindruck (Ordner-Browsing, Foto-Scan, automatische Bewertung) braucht es keinen
echten OpenCloud-Server und keine echten Zugangsdaten — ein optionales Compose-Overlay startet
zusätzlich einen echten [OpenCloud](https://opencloud.eu)-Single-Container
(`opencloudeu/opencloud-rolling`) mit fertigen Demo-Nutzern und befüllt ihn mit ein paar
mitgelieferten Beispielfotos (siehe [`specs/features/0009-local-opencloud-demo-stack.md`](../specs/features/0009-local-opencloud-demo-stack.md),
[`specs/decisions/0009-local-opencloud-demo-stack.md`](../specs/decisions/0009-local-opencloud-demo-stack.md)).
Reine Entwicklungs-/Ausprobier-Infrastruktur — kein selbstgebauter Mock, sondern derselbe
Server/Codepfad (Graph-API + WebDAV) wie im echten Betrieb, nur mit `OPENCLOUD_*`-Werten, die auf
den lokalen Container statt auf eine echte Instanz zeigen.

**Nur lokal starten:** Der Demo-Container ist bewusst schwach abgesichert (Basic-Auth mit
öffentlich bekannten Demo-Zugangsdaten, kein TLS) — niemals auf einem gemeinsam genutzten oder
öffentlich erreichbaren Host verwenden.

```bash
cp .env.demo.example .env
docker compose -f docker-compose.yml -f docker-compose.demo.yml up --build -d
docker compose -f docker-compose.yml -f docker-compose.demo.yml --profile seed run --rm seed
```

- Der erste Befehl startet den kompletten Stack (Postgres, Redis, Backend, Worker, Frontend) plus
  den `opencloud-demo`-Container, dessen Port explizit auf `127.0.0.1` gebunden ist.
- Der zweite Befehl seedet den Demo-Space mit Beispielfotos: `scripts/seed-opencloud-demo.py`
  wartet aktiv, bis der Container bereit ist, legt einen Ordner an und lädt die Fotos per WebDAV
  hoch — idempotent, ein erneuter Lauf erzeugt keine Duplikate. Läuft als eigener, einmaliger
  Compose-Service im selben Docker-Netzwerk wie `opencloud-demo` (siehe
  [`specs/decisions/0010-demo-seed-script-as-compose-service.md`](../specs/decisions/0010-demo-seed-script-as-compose-service.md)),
  braucht also kein lokales Python.
- Danach: Frontend unter http://localhost:8080 öffnen, mit den `AUTH_SEED_USER1_*`-Werten aus
  `.env.demo.example` einloggen (Standard: `demo`/`demo-password-1`), ein Projekt gegen den
  Demo-Space anlegen und Scan/Bewertung ausprobieren — ohne Codeänderung, nur die andere `.env`.
