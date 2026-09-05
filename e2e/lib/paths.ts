/**
 * Ablageorte des Pakets. Alle drei sind gitignoriert (Security-Muss-Kriterium M10): der
 * gespeicherte Anmeldezustand enthaelt ein 30 Tage gueltiges, nicht widerrufbares JWT, und die
 * Artefakte enthalten Bilddateien - unter `e2e/` darf keine davon je im Git-Index landen.
 */

import { fileURLToPath } from 'node:url'
import path from 'node:path'

export const PACKAGE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

/** Screenshots, Protokolle, Traces und der HTML-Report. */
export const ARTIFACTS_DIR = path.join(PACKAGE_ROOT, 'artifacts')

/** Ad-hoc-Skripte fuer `npm run drive` - Wegwerf-Code, nie Bestandteil des Pruefsatzes. */
export const SCRATCH_DIR = path.join(PACKAGE_ROOT, 'scratch')

/**
 * Gespeicherter Anmeldezustand. Eigenes Verzeichnis statt einer Datei unter `artifacts/`, damit
 * der CI-Artefakt-Upload (Pfad: ausschliesslich `e2e/artifacts/`) ihn strukturell nicht
 * mitnehmen kann.
 */
export const AUTH_DIR = path.join(PACKAGE_ROOT, '.auth')
export const AUTH_STATE_FILE = path.join(AUTH_DIR, 'user.json')
