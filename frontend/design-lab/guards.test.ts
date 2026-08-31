/*
 * TEMPORAER (specs/features/0287-design-richtungen-vergleich.md): Schutzgelaender des
 * Design-Labors.
 *
 * Fuer das Labor werden bewusst KEINE Komponenten-, Render- oder Interaktionstests geschrieben
 * (Begruendung: specs/architecture/0002-testkonzept.md, Sektion "Befristete Wegwerf-Artefakte:
 * Schutzgelaender statt Testabdeckung"). Stattdessen sichern dateilesende Strukturtests genau die
 * Eigenschaften ab, die die Akzeptanzkriterien strukturell zusagen:
 *
 *   G1 - Trennung von der laufenden Anwendung (keine Import-Kante, kein zweiter Build-Einstieg)
 *   G2 - Richtungs-Isolation (jede Regel auf ihr eigenes [data-direction] gescopt)
 *   G3 - Umsetzbarkeits-Vorbehalt (vollstaendiger Tokensatz in beiden Modi, var()-selbstgenuegsam)
 *   G4 - Kontrast-Untergrenze der Text-/Symbolpaarungen
 *   A2 - kein Rasterbild/Video unterhalb frontend/design-lab im Git-Index
 *
 * Diese Datei liegt bewusst im tsconfig.node.json-Projekt (`node:fs`) und ist im App-Projekt per
 * `exclude` ausgenommen - siehe frontend/tsconfig.app.json / frontend/tsconfig.node.json.
 *
 * AUSNAHME zu G1(c): dieser Test liest ../src/index.css per readFileSync als TEXT. Das ist keine
 * Modulkante und landet in keinem Bundle; die Einbahnstrassenregel gilt fuer Imports, nicht fuer
 * Dateizugriffe des Testcodes.
 *
 * PFADANKER: `fileURLToPath(import.meta.url)` + `node:path` statt `process.cwd()` (haengt vom
 * Startverzeichnis ab) UND statt `new URL('./x', import.meta.url)`: dieses Literal-Muster schreibt
 * Vite beim Transformieren in eine Asset-URL um (hier gemessen: es wurde zu
 * `http://localhost:3000/design-lab/...` aufgeloest), es ist in einem Vite-transformierten Test
 * also nicht brauchbar.
 */
import { execFileSync } from 'node:child_process'
import { readdirSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const LAB_DIR = dirname(fileURLToPath(import.meta.url))
const FRONTEND_DIR = dirname(LAB_DIR)
const REPO_ROOT = dirname(FRONTEND_DIR)
const SRC_DIR = join(FRONTEND_DIR, 'src')
const APP_INDEX_CSS = join(SRC_DIR, 'index.css')

/** Nur Textdateien werden auf Import-Kanten geprueft - `photos-local/` kann Binaerdateien fuehren. */
const TEXT_EXTENSIONS = ['.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.css', '.html', '.json']

interface ScannedFile {
  /** Lesbarer Relativpfad fuer Fehlermeldungen, z.B. `src/pages/PhotoGridPage.tsx`. */
  label: string
  path: string
}

function listTextFiles(directory: string, labelPrefix: string): ScannedFile[] {
  const files: ScannedFile[] = []
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const childPath = join(directory, entry.name)
    const label = `${labelPrefix}${entry.name}`
    if (entry.isDirectory()) {
      files.push(...listTextFiles(childPath, `${label}/`))
      continue
    }
    if (TEXT_EXTENSIONS.some((extension) => entry.name.endsWith(extension))) {
      files.push({ label, path: childPath })
    }
  }
  return files
}

interface ModuleSpecifier {
  specifier: string
  line: number
}

/*
 * Modul-/Stylesheet-Spezifizierer einer Textdatei: `from '…'`, `import '…'`, `import('…')`,
 * `require('…')` und `@import '…'`/`@import url('…')`. Bewusst eine Naeherung statt eines Parsers
 * - fuer die eine Frage "gibt es eine Kante zwischen App und Labor?" genuegt sie, und eine
 * Parser-Abhaengigkeit fuer ein Wegwerf-Artefakt waere unverhaeltnismaessig.
 */
const SPECIFIER_PATTERN =
  /(?:\bfrom\s*|\bimport\s*\(\s*|\brequire\s*\(\s*|\bimport\s+|@import\s+(?:url\(\s*)?)(['"])([^'"]+)\1/g

function extractSpecifiers(source: string): ModuleSpecifier[] {
  const found: ModuleSpecifier[] = []
  for (const match of source.matchAll(SPECIFIER_PATTERN)) {
    const line = source.slice(0, match.index).split('\n').length
    found.push({ specifier: match[2], line })
  }
  return found
}

describe('G1 - Trennung von der laufenden Anwendung', () => {
  it('keine Datei unter src/** importiert aus dem Design-Labor', () => {
    const offenders: string[] = []
    for (const file of listTextFiles(SRC_DIR, 'src/')) {
      const source = readFileSync(file.path, 'utf8')
      for (const { specifier, line } of extractSpecifiers(source)) {
        if (specifier.includes('design-lab')) {
          offenders.push(
            `${file.label}:${line} importiert aus dem Design-Labor ('${specifier}'). Das Labor ` +
              'ist ein Wegwerf-Artefakt und darf keine Kante in die laufende Anwendung haben ' +
              '(AK "getrennt von der laufenden Anwendung").'
          )
        }
      }
    }
    expect(offenders).toEqual([])
  })

  it('vite.config.ts und index.html erwaehnen das Labor gar nicht', () => {
    const offenders: string[] = []
    const targets: readonly [string, string][] = [
      ['frontend/vite.config.ts', join(FRONTEND_DIR, 'vite.config.ts')],
      ['frontend/index.html', join(FRONTEND_DIR, 'index.html')],
    ]
    for (const [label, path] of targets) {
      readFileSync(path, 'utf8')
        .split('\n')
        .forEach((text, index) => {
          if (text.includes('design-lab')) {
            offenders.push(
              `${label} erwaehnt 'design-lab' (Zeile ${index + 1}). Ein zweiter Rollup-Input zoege ` +
                'das Labor in dist/ und ins nginx-Image.'
            )
          }
        })
    }
    expect(offenders).toEqual([])
  })

  it('src/index.css fordert die Tailwind-Quellsuche-Ausnahme ein', () => {
    // Einzige erlaubte Erwaehnung von 'design-lab' unter src/** - und zwar nicht nur erlaubt,
    // sondern eingefordert: ohne sie koennte das Labor die generierte Produktiv-CSS anfassen.
    const lines = readFileSync(APP_INDEX_CSS, 'utf8').split('\n')
    const matching = lines.filter((line) =>
      /^\s*@source\s+not\s+['"]\.\.\/design-lab['"];/.test(line)
    )
    expect(matching).toHaveLength(1)
  })

  it('keine Datei unter design-lab/** importiert aus ../src', () => {
    const offenders: string[] = []
    for (const file of listTextFiles(LAB_DIR, 'design-lab/')) {
      if (file.label === 'design-lab/guards.test.ts') {
        continue
      }
      const source = readFileSync(file.path, 'utf8')
      for (const { specifier, line } of extractSpecifiers(source)) {
        if (specifier.includes('../src')) {
          offenders.push(
            `${file.label}:${line} importiert aus der laufenden Anwendung ('${specifier}'). Die ` +
              'Einbahnstrasse gilt in beide Richtungen: das Labor haengt an nichts aus src/.'
          )
        }
      }
    }
    expect(offenders).toEqual([])
  })
})

describe('A2 - keine privaten Bilddaten im Git-Index', () => {
  it('git ls-files fuehrt unterhalb frontend/design-lab kein Raster-/Videoformat', () => {
    /*
     * Zustandspruefung statt Praevention: `.gitignore` schuetzt nur `photos-local/` selbst - eine
     * Bilddatei DANEBEN wird von `git add -A` kommentarlos gestaged, `git add -f` umgeht ihn, und
     * auf bereits getrackte Pfade wirkt er gar nicht (specs/architecture/0003-securitykonzept.md).
     *
     * Bewusst auf `frontend/design-lab` begrenzt, damit die bestehenden scripts/demo_photos/*.jpg
     * nicht faelschlich anschlagen. Schlaegt der git-Aufruf fehl, ist der Test ROT statt
     * uebersprungen - ein still uebersprungener Waechter ist kein Waechter.
     *
     * Fehlendes/leeres photos-local/ ist der Normalfall (Git fuehrt keine leeren Verzeichnisse)
     * und muss gruen sein: ein Test, der ohne lokale Fotos rot ist, erzeugt genau den Anreiz,
     * "Beispielfotos" einzuchecken.
     */
    const output = execFileSync('git', ['ls-files', '--', 'frontend/design-lab'], {
      cwd: REPO_ROOT,
      encoding: 'utf8',
    })
    const mediaFiles = output
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => line.length > 0)
      .filter((line) => /\.(jpe?g|png|heic|heif|webp|tiff?|mp4|mov)$/i.test(line))
    expect(mediaFiles).toEqual([])
  })
})
