---
name: browse-app
description: Startet die PhotoSort-Anwendung lokal mit synthetischen Demo-Daten, macht Screenshots einer beliebigen Route in zwei Viewports, bedient die Oberfläche (klicken, tippen, navigieren) und räumt danach wieder auf. Nutze diesen Skill, wenn tatsächlich hingesehen werden soll statt geraten — z.B. "sieh dir die Statistikseite mal an", "wie sieht das auf dem Handy aus", "mach einen Screenshot von X", "reproduzier den Fehler im Browser", "klick dich mal durch die Pipeline", oder wenn ein Layout-/Darstellungs-/Interaktionsproblem gemeldet wird, das nur im echten Browser sichtbar ist. Nicht nutzen, um den automatisierten Prüfsatz laufen zu lassen (das macht der CI-Job `e2e`), und nicht gegen Daniels echte Instanz oder echte Fotos.
---

# browse-app — die laufende Anwendung ansehen und bedienen

**GitHub-Erlaubnisstufe:** kein GitHub-Zugriff — weder lesend noch schreibend, gleich über welchen Weg und gleich mit welchem Werkzeug. Jeder Zugriff auf Issues, Board und Pull Requests dieses Repositories läuft über die Operationen des Skills `github-access` und bleibt den dort lesend bzw. schreibend eingestuften Ablauf-Skills der Hauptsession vorbehalten. Lokales `git` ist davon unberührt.

Ad hoc auf Zuruf, nie automatisch Teil eines anderen Ablaufs. Vier Schritte: **Stack starten → seeden → ansehen/bedienen → aufräumen.**

## Was dieser Stack ist — und was er nicht ist

Der Prüfstack besteht aus `postgres`, `redis`, `backend` und `frontend`. **Kein OpenCloud, kein Worker.** Alle Zustände kommen aus einem deterministischen Seeder, der die Datenbank und den Thumbnail-Cache direkt füllt; die Bilder sind synthetisch erzeugt.

Daraus folgt für die Deutung dessen, was zu sehen ist:

- Der **Ordner-Browser** (`/projects/new`) zeigt hier eine Fehlermeldung. Das ist der korrekte Zustand dieses Stacks, kein Fund. Wer den Normalfall sehen will, braucht das Demo-Overlay `docker-compose.demo.yml` mit echter OpenCloud-Instanz.
- **Nichts läuft im Hintergrund.** Ein Scan, ein Scoring-Lauf oder eine Kategorie-Klassifizierung, die man in der Oberfläche anstößt, wird nie fertig — die dargestellten Lauf-Ergebnisse hat der Seeder geschrieben.
- **Kein Blick auf Daniels lokalen Datenbestand.** Der Prüfstack hat einen eigenen Compose-Projektnamen und damit eigene Volumes; er sieht dessen Datenbank und Cache nicht. Das ist Absicht und wird nicht umgangen.

## 1. Stack starten

```bash
docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d --build
```

Erreichbar unter `http://localhost:8080` (Oberfläche) und `http://localhost:8000` (API), beide **nur lokal** gebunden. Sind diese Ports durch einen bereits laufenden PhotoSort-Stack belegt, ist das kein Grund, den anderen Stack abzuschießen — stattdessen ein eigenes, temporäres Overlay mit anderen Host-Ports schreiben und dabei `CORS_ALLOWED_ORIGINS` (Backend) sowie `VITE_API_BASE_URL` (Frontend-Build-Argument) auf dieselben Ports ziehen; sonst blockiert der Browser jeden API-Aufruf als fremde Origin. Der abweichende Ort wird den Werkzeugen dann über `PHOTOSORT_E2E_BASE_URL=http://localhost:<port>` mitgegeben.

Warten, bis das Backend antwortet:

```bash
curl -fsS http://localhost:8000/health
```

## 2. Demo-Daten seeden

```bash
docker compose -f docker-compose.yml -f docker-compose.e2e.yml exec -T \
  -e PHOTOSORT_DEMO_STATE_CONFIRM=yes-wipe-and-seed-demo-data \
  backend python -m photosort.demo_state
```

Der Seeder ist zielzustands-idempotent: er löscht seine eigenen Demo-Projekte und legt sie neu an. Er **bricht ab**, wenn die Datenbank irgendein Projekt ohne den Präfix `Demo — ` enthält oder eine echte OpenCloud-Adresse konfiguriert ist. Läuft er nicht an, ist das kein Hindernis, das man beiseiteräumt — dann zeigt der Aufruf auf die falsche Datenbank.

Danach existieren vier Projekte, jedes für einen anderen Zweck:

| Projekt | wofür es da ist |
|---|---|
| `Demo — Leeres Projekt` | Leerzustände |
| `Demo — Große Sammlung` | Scrollen, Grid-Zeilen, Listendichte (~70 Fotos) |
| `Demo — Bewertet` | alle Bewertungsstatus, Kriterien-Lauf, alle Kategorie-Schlüssel |
| `Demo — Fehlerzustand` | fehlgeschlagener Lauf, Foto ohne Cache-Datei, Cloud-Vision-Fehlerzeile |

**Die Projekt-IDs sind nicht stabil.** Ein zweiter Seed-Lauf gegen dieselbe Datenbank vergibt neue IDs (Postgres setzt die Sequenz nicht zurück). Die IDs deshalb immer aus der Projektliste (`http://localhost:8080/`) ablesen, statt sie aus einem früheren Lauf zu übernehmen.

## 3. Ansehen und bedienen

**Einmal hinsehen** — Screenshot je Viewport (`mobile` 360 × 740, `desktop` 1280 × 800) plus Protokoll:

```bash
cd e2e && npm ci     # nur beim ersten Mal
npx playwright install chromium   # nur beim ersten Mal, OHNE --with-deps
npm run shot -- /projects/2/photos
npm run shot -- /projects/2/photos mobile
```

Die PNG-Dateien landen unter `e2e/artifacts/` und werden anschließend **gelesen** — ein Screenshot, den niemand ansieht, ist keine Prüfung. Daneben liegt je eine `.log.txt` mit Konsolenmeldungen, unbehandelten Seitenfehlern und Netzwerkaufrufen ab Status 400. Diese Mitschrift passiert immer, ohne Zutun des Aufrufers; sie gehört mit in die Beurteilung, auch wenn das Bild unauffällig aussieht.

**Bedienen** (klicken, tippen, navigieren) — für alles, was erst durch Interaktion entsteht: geöffnete Popover, ausgeklappte Bereiche, abgeschickte Formulare, Bestätigungsdialoge. Dafür ein Wegwerf-Skript unter `e2e/scratch/` (gitignoriert) anlegen:

```ts
// e2e/scratch/popover.ts
import type { DriveScript } from '../bin/drive.ts'

const run: DriveScript = async ({ page, shot }) => {
  await page.goto('/projects/3/photos')
  await page.getByRole('button', { name: 'Bewertungsdetails anzeigen' }).first().click()
  await shot('popover-offen')
}

export default run
```

```bash
npm run drive -- scratch/popover.ts mobile
```

Die Playwright-API ist damit vollständig verfügbar (`page.getByRole(...)`, `fill`, `click`, `keyboard`, `evaluate` für Messungen im DOM). Lokalisiert wird über Rollen, `aria-*` und die etablierten `data-*`-Attribute, nie über CSS-Klassennamen.

**Wenn sich dabei ein echter Fehler zeigt:** Das Wegwerf-Skript ist der Anfang, nicht das Ergebnis. Der Weg vorwärts ist ein richtiger Spec unter `e2e/tests/` (mit exakter Kardinalität, einer Vorbedingung gegen den trivialen Grün-Fall und einem belegten roten Lauf) oder ein Test auf der billigeren Ebene — nicht ein Skript, das man aufhebt.

**Zwei Zahlengrenzen, die man kennen muss:** `POST /auth/login` ist auf 5 Anfragen pro Minute und IP begrenzt — mehrere Läufe kurz hintereinander laufen in eine 429-Antwort, die sich wie ein kaputter Login anfühlt. Und der gespeicherte Anmeldezustand unter `e2e/.auth/` wird nur einmal erzeugt und danach wiederverwendet.

## 4. Aufräumen

```bash
cd .. && docker compose -f docker-compose.yml -f docker-compose.e2e.yml down -v
rm -rf e2e/.auth
```

`down -v` entfernt auch die Volumes des Prüfstacks — sie enthalten nur Demo-Daten. `e2e/.auth/` enthält ein 30 Tage gültiges, nicht widerrufbares Anmelde-Token und wird deshalb nach dem Blick entfernt, nicht liegen gelassen.

`e2e/artifacts/` und `e2e/scratch/` sind gitignoriert und dürfen liegen bleiben; sie gehören unter keinen Umständen in einen Commit. Unter `e2e/` darf nie eine Bilddatei versioniert werden.

## Grenzen dieses Skills

- **Nie gegen eine echte Instanz oder echte Fotos.** Die Werkzeuge sprechen ausschließlich eine lokale Adresse an, und der Seeder ist gegen fremde Datenbanken gesperrt. Beides wird nicht aufgeweicht, auch nicht „nur für diese Session".
- **`npx playwright install --with-deps` ist hier nicht vorgesehen.** Es installiert als root per `apt-get` eine aus dem npm-Paket stammende Paketliste; das gehört in den CI-Container, nicht auf Daniels Fedora-Rechner (wo es ohnehin nicht greift). Fehlt eine Systembibliothek, wird sie benannt und einzeln nachinstalliert.
- **Kein Ersatz für den automatisierten Prüfsatz.** Was hier ad hoc gesehen wird, ist ein Blick; was dauerhaft gelten soll, gehört als Spec nach `e2e/tests/` und läuft im CI-Job `e2e` mit.
