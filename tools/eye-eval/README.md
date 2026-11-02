# eye-eval — Eye gegen die Cloud-Bewertung (Spec 0606)

Einmaliges Messwerkzeug, **kein Produktcode**. Es liest die bestehende Cloud-Bewertung
schreibgeschützt aus Postgres, lässt `@desert-ant-labs/eye@4.2.3` lokal über dieselben
Cache-Bilder laufen und stellt beide Ergebnisse in einer Wegwerf-Seite gegenüber, die du
paarweise bewertest. Der Werkzeugbaum hängt in keinem Image und nicht in `scripts/check.sh`
(S22). In der CI läuft allein der Job `eye-eval`: signaturgeprüfte Installation und `npm test`,
keine Auswertung.

**Powered by Desert Ant Labs** — Lizenz §9 verlangt die Namensnennung. Die Lizenzprüfung des
SDK bleibt unverändert (S1–S5): nicht deaktivieren, nicht blockieren, nicht umleiten, nichts
fälschen. Gesetzt wird ausschließlich `DAL_APP_ID=photosort-eye-eval`. Das SDK kontaktiert nur
`events.desertant.com` (Metadaten, keine Bilder); im Container ist das nicht erzwungen (siehe
„Grenzen“). Ein gesetztes
`DAL_LICENSE_ENDPOINT` oder `HF_TOKEN` bricht den Lauf ab.

## Was hier bewusst nicht passiert

- Kein Schreibzugriff auf die Anwendung oder die Datenbank (S13: `default_transaction_read_only=on`,
  per `SHOW` geprüft; ein Schreibversuch scheitert im Test).
- Keine Bilddaten, Namen oder Pfade im Repository; Arbeitsdaten liegen unter
  `~/photosort-eye-eval/` (S9) und werden nach der Auswertung mit dem Verzeichnis gelöscht.
- Kein Cloud-Aufruf des Werkzeugs. Fehlende Cloud-Basis erzeugst du bei Bedarf in der
  Anwendung selbst (`POST /projects/{id}/classify` mit Kostenvorschau).

## Voraussetzungen

- Node 22 (im Container), `photo_cache` schreibgeschützt, Arbeitsverzeichnis außerhalb des Repos.
- `EYE_EVAL_DATABASE_URL` als **einziger** Wert aus der `.env`, über eine temporäre Env-Datei
  mit Rechten 600 (S15). `--env-file .env` ist verboten — damit gingen App-Token und
  Anbieter-Keys an Fremdcode.
- Projektarten: die Datenbank kennt keine Projektart. Lege `<work>/projects.json` an:

  ```json
  [
    { "projectId": 3, "kind": "familie" },
    { "projectId": 5, "kind": "reise" }
  ]
  ```

  Mindestens zwei Projekte, Arten nicht leer und paarweise verschieden — sonst bricht der Lauf ab.

## Einmalig: Gewichte und Pins (S20)

```bash
mkdir -p ~/photosort-eye-eval/models
cd ~/photosort-eye-eval/models
# Revision v1.0.0, Commit-SHA festhalten
curl -L -o eye.tflite     https://huggingface.co/desert-ant-labs/eye/resolve/v1.0.0/eye.tflite
curl -L -o eye_meta.json  https://huggingface.co/desert-ant-labs/eye/resolve/v1.0.0/eye_meta.json
sha256sum eye.tflite eye_meta.json
git -C /tmp ls-remote https://huggingface.co/desert-ant-labs/eye refs/tags/v1.0.0   # Commit-SHA
```

`pins.json` daneben schreiben, mit dem Commit-SHA der Revision und den beiden SHA-256:

```json
{
  "revision": "v1.0.0",
  "commit": "<commit-sha-der-revision>",
  "files": {
    "eye.tflite": "<sha256>",
    "eye_meta.json": "<sha256>"
  }
}
```

`analyze` prüft beide Dateien vor dem Laden und bricht bei Abweichung ab; im Lauf findet kein
Download statt. Vor dem ersten Lauf die Szenen-Tags in `src/mapping.js` gegen `eye_meta.json`
abgleichen (die Tabelle ist danach durch ihren Hash eingefroren).

## Container

Der Container sieht nie das Repository, sondern nur eine Kopie des Werkzeugbaums im
Arbeitsverzeichnis (S16). Jede Codeänderung braucht deshalb zuerst eine neue Kopie — sonst läuft
der alte Stand:

```bash
# 1. Kopie des Werkzeugbaums ins Arbeitsverzeichnis (nicht das Repo selbst mounten)
rsync -a --delete tools/eye-eval/ "$HOME/photosort-eye-eval/tool/"

# 2. npm ci läuft IM Container, nie auf dem Host (S17); nicht als root
#    --network: das Compose-Netz, in dem der Postgres-Dienst läuft (Name z. B. aus
#    `docker compose ps --format '{{.Networks}}'`, meist photosort_default). Ohne dieses Netz
#    ist der Dienstname `postgres` aus der Env-Datei nicht auflösbar.
docker run --rm -it \
  --user "$(id -u):$(id -g)" \
  --network photosort_default \
  -e HOME=/tmp -e npm_config_cache=/tmp/npm-cache \
  -e DAL_APP_ID=photosort-eye-eval \
  -v "$HOME/photosort-eye-eval/tool:/app" -w /app \
  -v "$HOME/photosort-eye-eval:/work" \
  -v photosort_photo_cache:/cache:ro \
  --env-file /tmp/eye-eval.env \
  node:22-bookworm \
  bash -lc 'npm ci --ignore-scripts && node src/cli.js --help'
```

Kein Docker-Socket, kein veröffentlichter Port, `--rm` (S16); `HOME`/`npm_config_cache` liegen im
Container auf `/tmp`, damit `npm ci` auch als nicht-root schreiben kann.

Der Container **erzwingt** keinen Egress-Filter. Das SDK kontaktiert ausschließlich
`events.desertant.com` (Lizenzprüfung, keine Bilder, S1–S5); wer das Netz hart begrenzen will,
setzt es auf dem Host durch (eigene Docker-Netzwerk-Bridge ohne Default-Route bzw. Egress-Regel der
Firewall, die nur diese Namensauflösung und TCP 443 zu dieser Adresse zulässt) und lässt den
Container mit `--network <eigenes-netz>` laufen.

## Ablauf

```bash
# Im Container (`--work-dir /work`):
node src/cli.js prepare --work-dir /work --photo-cache /cache   # Stichprobe + Basis, Bildkopien nach /work/images
node src/cli.js analyze --work-dir /work                       # Gewichte prüfen, Bilder analysieren
node src/cli.js pages   --work-dir /work                       # Vergleichsseiten je Zweck
node src/cli.js summary --work-dir /work                       # Zählungen, Ersparnis, /work/abschluss.html
node src/cli.js report-check <markdown>

# Auf dem Host, nicht im Container (siehe „serve“ unten):
node tools/eye-eval/src/cli.js serve --work-dir "$HOME/photosort-eye-eval"
```

`EYE_EVAL_DATABASE_URL` kommt ausschließlich über die gefilterte Env-Datei (S15: nur dieser eine
Eintrag, Rechte 600, kein `--env-file .env`) — nie über die Kommandozeile. Sie zeigt im Container
auf den Compose-Dienst statt auf `localhost`: `postgresql://photosort:photosort@postgres:5432/photosort`
(Dienstname `postgres`, Port 5432; im Default-Bridge-Netz wäre beides nicht erreichbar).
`--photo-cache` ist im Container immer `/cache` (das schreibgeschützt eingebundene Volume); fehlen
`--photo-cache` und die Variable, bricht `prepare` mit „Bildcache fehlt: --photo-cache übergeben
oder EYE_EVAL_PHOTO_CACHE_DIR setzen (im Container /cache).“ ab.

`DAL_APP_ID=photosort-eye-eval` steht bewusst als Literal auf der Kommandozeile, nicht in der
Env-Datei: die Datei trägt weiterhin nur die Datenbank-URL, und `analyze` bricht ohne exakt diesen
Wert ab (S3). Kein weiterer Lizenzwert gehört in den Container.

`prepare`, `analyze`, `pages`, `summary` und `report-check` laufen im Container unter `/app`
(Schritt 2 oben), mit `--work-dir /work`; der Host braucht dafür kein `npm ci`.

`serve` läuft dagegen **auf dem Host**, im Repo-Checkout (oder in einer Kopie), weil der Server
nur an 127.0.0.1 im jeweiligen Netzwerk bindet und ein veröffentlichter Port durch S12/S16
ausgeschlossen ist — aus dem Container käme der Browser nie an die Seite:

```bash
node tools/eye-eval/src/cli.js serve --work-dir "$HOME/photosort-eye-eval"
# Browser: http://127.0.0.1:<port>/
```

Der `serve`-Pfad braucht weder SDK noch Datenbank und lädt ausschließlich Node-Bordmittel; ein
`npm ci` auf dem Host ist nicht nötig (nach einer Codeänderung die Containerkopie erneuern, nicht
das Repo). Es wird kein Port veröffentlicht und nicht an 0.0.0.0 gebunden.

Optionen: `--work-dir`, `--database-url`, `--photo-cache`, `--model-dir`, `--seed`,
`--per-project`, `--purpose`, `--port`, `--resume`, `--force` (`--help` zeigt alles).

`prepare` bricht ab, wenn im Arbeitsverzeichnis schon eine `run.json` liegt: ein zweiter Lauf würde
Stichprobe, Analysen und Wahlen mischen. `--force` legt stattdessen ein neues Verzeichnis
`<work>-lauf-<zeitstempel>` an und gibt es aus; die weiteren Befehle zielen dann dorthin.

stdout trägt nur Zählungen (S10); Namen und Pfade stehen ausschließlich in Dateien unter
`<work>/`. Die Vergleichsseite enthält nur „A“/„B“; die Zuordnung liegt in `<work>/ab-map.json`.

## Ergebnis

- `<work>/summary.json` — Zählungen je Zweck, Aufrufe, Ersparnis, Modelle (keine Namen).
- `<work>/abschluss.html` — Abschlussseite mit den Zählungen je Zweck.
- `<work>/report-check.txt` — Befunde des Report-Prüfers inklusive Fundstellen (nur lokal).
- `<work>/runtime.json` — Laufzeit je Foto, Modellrevision, geprüfte Hashes.

Als ersetzt gilt ein Zweck nur, wenn „gleich oder besser“ die Mehrheit der **entschiedenen** Paare
stellt **und** mindestens die Hälfte der Paare des Zwecks überhaupt entschieden ist
(`entschieden * 2 >= gesamt`). Sonst steht in der Zusammenfassung „zu wenige Entscheidungen in …“,
und es wird kein Aufruf als gespart gezählt — eine einzelne Stimme bei überwiegend übersprungenen
Paaren ersetzt nichts.

Die Abschlussseite zeigt die rohen Seitenzahlen (A, gleich, B). Für die Ersparnis übersetzt
`summary` sie über `<work>/ab-map.json` in Eye-Urteile: A heißt „links besser“, und links stand je
Foto mal die Cloud, mal Eye. Fehlt die Zuordnung oder eine Stimme darin, bricht `summary` ab, statt
die Seiten zu raten.

Der Bericht im öffentlichen Repository nennt nur Zählungen, Zwecke, Urteile und Prosa (S6–S8).
Der Prüfer findet Pfade, Dateiendungen, Projekt- und Landmarknamen, Bild-Einbettungen,
Install-IDs, Aufnahmezeiten, Koordinaten und A/B-Zuordnung; Personennamen im Fließtext bleiben
deine manuelle Prüfung (S11).

## Tests

```bash
npm test                                        # Unit, ohne SDK, ohne Socket, ohne Bilddaten
EYE_EVAL_TEST_DATABASE_URL=... \
EYE_EVAL_TEST_PHOTO_CACHE_DIR=... npm run test:db   # opt-in, nur auf dem Heimserver
```

Der DB-Test ist kein Teil von `npm test`; ein fehlendes Env ist ein lauter Fehlschlag, kein
stiller Skip. Der CI-Job `eye-eval` führt nur `npm test` aus; den DB-Test führt weder er noch
`scripts/check.sh` aus. Der Rot-Nachweis steht im PR.

## Grenzen

- Eye liefert keine Landmarknamen; die Sehenswürdigkeit wird über Bauwerk-Szenen gemessen.
- Feinlabels haben ein anderes Vokabular als die Cloud — kein automatischer Treffervergleich.
- Die Aufrufzahlen der Ersparnis stammen aus `remote_category_classification_runs.api_calls` bzw.
  `landmark_classification_runs.api_calls` des letzten Laufs je Projekt — der Aufrufzahl, nicht der
  Fotozahl, weil Wiederholungen und ausgesetzte Fotos sonst unterschlagen würden. Trägt eine
  Kategorie-Zeile keine Aufrufzahl, dient `photos_processed` als Rückfall; `summary.json` hält das
  unter `calls.source` (und `calls.fallbackProjects`) fest.
- Das native SDK ist ein vorgefertigtes Binary (S21); der Pin schützt gegen einen später
  getauschten Stand, nicht gegen den veröffentlichten.
- Eye v1.0.0 ist **Beta**; ein Modell-Update gilt unter der dann aktuellen Lizenz. Diese Auswertung
  ist an `@desert-ant-labs/eye` 4.2.3 und die Lizenz zum Zeitpunkt des Pins gebunden.
- Egress ist im Container nicht erzwungen: die Zusage „nur `events.desertant.com`“ beschreibt das
  SDK, nicht die Laufzeitumgebung. Ohne Host-Regel kann das Fremdpaket alles erreichen, was das
  Docker-Netz zulässt; die Durchsetzung ist Betreiberpflicht (siehe Abschnitt „Container“).
