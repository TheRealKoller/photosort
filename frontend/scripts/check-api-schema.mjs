#!/usr/bin/env node
/**
 * Prüft, ob `src/api/generated/schema.d.ts` aus `backend/openapi.json` erzeugt ist.
 *
 * Erzeugt die Typen in eine temporäre Datei außerhalb von `src/` und vergleicht sie byte-gleich
 * mit dem eingecheckten Stand. Bei Abweichung nennt die Meldung die Datei und den
 * Nachführbefehl; die temporäre Datei wird in jedem Fall entfernt.
 *
 * Läuft als Teil von `npm run typecheck` - ohne eigenen CI-Job und ohne Backend-Abhängigkeit:
 * gelesen wird nur das eingecheckte JSON-Artefakt.
 */
import { execFileSync } from 'node:child_process'
import { existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const HIER = path.dirname(fileURLToPath(import.meta.url))
const FRONTEND = path.resolve(HIER, '..')
const EINGABE = path.resolve(FRONTEND, '..', 'backend', 'openapi.json')
const ZIEL = path.join(FRONTEND, 'src', 'api', 'generated', 'schema.d.ts')
const BEFEHL = 'npm --prefix frontend run api:generate'
const AUSGABE = 'frontend/src/api/generated/schema.d.ts'
const CLI = path.join(FRONTEND, 'node_modules', 'openapi-typescript', 'bin', 'cli.js')

function scheitern(meldung) {
  process.stderr.write(`${meldung}\n`)
  process.exit(1)
}

if (!existsSync(EINGABE)) {
  scheitern(
    `backend/openapi.json fehlt. Anlegen mit \`python backend/scripts/export_openapi.py\`, ` +
      `danach \`${BEFEHL}\`.`,
  )
}

const verzeichnis = mkdtempSync(path.join(tmpdir(), 'photosort-api-check-'))
const erzeugt = path.join(verzeichnis, 'schema.d.ts')
try {
  execFileSync(process.execPath, [CLI, EINGABE, '--output', erzeugt], { stdio: 'pipe' })
  if (!existsSync(ZIEL)) {
    scheitern(`${AUSGABE} fehlt. Nachführen: ${BEFEHL}`)
  }
  if (!readFileSync(ZIEL).equals(readFileSync(erzeugt))) {
    scheitern(
      `${AUSGABE} ist nicht aus backend/openapi.json erzeugt (Inhalt weicht ab). ` +
        `Nachführen: ${BEFEHL}`,
    )
  }
} finally {
  rmSync(verzeichnis, { recursive: true, force: true })
}
