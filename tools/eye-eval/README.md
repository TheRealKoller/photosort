# eye-eval — Eye gegen die Cloud-Bewertung (Spec 0606)

Einmaliges Messwerkzeug, **kein Produktcode**. Es liest die bestehende Cloud-Bewertung
schreibgeschützt aus Postgres, lässt `@desert-ant-labs/eye@4.2.3` lokal über dieselben
Cache-Bilder laufen und stellt beide Ergebnisse in einer Wegwerf-Seite gegenüber, die du
paarweise bewertest. Der Werkzeugbaum hängt in keinem Image, in keiner CI und in
`scripts/check.sh` (S22).

**Powered by Desert Ant Labs** — Lizenz §9 verlangt die Namensnennung. Die Lizenzprüfung des
SDK bleibt unverändert (S1–S5): nicht deaktivieren, nicht blockieren, nicht umleiten, nichts
fälschen. Gesetzt wird ausschließlich `DAL_APP_ID=photosort-eye-eval`. Ein ausgehender Kontakt
geht nur an `events.desertant.com` (Metadaten, keine Bilder). Ein gesetztes
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

```bash
# npm ci läuft IM Container, nie auf dem Host (S17)
docker run --rm -it \
  -v "$PWD/tools/eye-eval:/app" -w /app \
  -v "$HOME/photosort-eye-eval:/work" \
  -v photosort_photo_cache:/cache:ro \
  --env-file /tmp/eye-eval.env \
  node:22-bookworm \
  bash -lc 'npm ci --ignore-scripts && node src/cli.js --help'
```

Nicht als root, kein Docker-Socket, kein veröffentlichter Port, kein Repo im Container
(nur eine Kopie des Werkzeugbaums), `--rm` (S16).

## Ablauf

```bash
node src/cli.js prepare      # Stichprobe + Basis, Bildkopien nach <work>/images
node src/cli.js analyze      # Gewichte prüfen, Bilder analysieren
node src/cli.js pages        # Vergleichsseiten je Zweck
node src/cli.js serve        # http://127.0.0.1:<port>/ (nie 0.0.0.0, S12)
node src/cli.js summary      # Zählungen, Ersparnis, <work>/abschluss.html
node src/cli.js report-check <markdown>
```

Optionen: `--work-dir`, `--database-url`, `--photo-cache`, `--model-dir`, `--seed`,
`--per-project`, `--purpose`, `--port`, `--resume` (`--help` zeigt alles).

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
stiller Skip. CI und `scripts/check.sh` führen keinen der beiden Läufe aus — der Rot-Nachweis
steht im PR.

## Grenzen

- Eye liefert keine Landmarknamen; die Sehenswürdigkeit wird über Bauwerk-Szenen gemessen.
- Feinlabels haben ein anderes Vokabular als die Cloud — kein automatischer Treffervergleich.
- Die Aufrufzahlen der Ersparnis stammen aus den Laufzeilen des letzten Laufs je Projekt; Fotos
  ohne Cloud-Aufruf zählen dort naturgemäß null.
- Das native SDK ist ein vorgefertigtes Binary (S21); der Pin schützt gegen einen später
  getauschten Stand, nicht gegen den veröffentlichten.
