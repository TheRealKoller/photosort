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
const DIRECTIONS_DIR = join(LAB_DIR, 'directions')
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

/* ==========================================================================================
 * Gemeinsamer CSS-Scanner fuer G2/G3/G4
 *
 * Kein Regex ueber die ganze Datei, sondern ein Zeichen-Scanner: (1) Kommentare werden
 * laengentreu durch Leerzeichen ersetzt, damit Zeilennummern und Offsets erhalten bleiben,
 * (2) zeichenweiser Lauf mit einem Stack der offenen Bloecke, (3) ein Prelude, der mit `@`
 * beginnt, ist At-Rule statt Selektor - Regeln INNERHALB von @media/@supports werden ganz normal
 * weitergeprueft, Zeilen innerhalb von @keyframes (`0%`, `from`, `to`) dagegen uebersprungen,
 * (4) Selektorlisten werden nur an Kommata auf Klammertiefe 0 getrennt, damit `:is(a, b)`/
 * `:where(…)` nicht zerfallen.
 *
 * Bewusst keine Parser-Abhaengigkeit fuer ein Wegwerf-Artefakt.
 * ========================================================================================== */

/** Ersetzt Kommentarinhalte laengentreu durch Leerzeichen (Zeilenumbrueche bleiben erhalten). */
function stripComments(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\//g, (match) => match.replace(/[^\n]/g, ' '))
}

function lineIndexer(source: string): (offset: number) => number {
  const lineStarts: number[] = [0]
  for (let index = 0; index < source.length; index += 1) {
    if (source[index] === '\n') {
      lineStarts.push(index + 1)
    }
  }
  return (offset: number) => {
    let low = 0
    let high = lineStarts.length - 1
    while (low < high) {
      const middle = Math.ceil((low + high) / 2)
      if (lineStarts[middle] <= offset) {
        low = middle
      } else {
        high = middle - 1
      }
    }
    return low + 1
  }
}

/** Trennt eine Selektorliste an Kommata auf Klammertiefe 0 (`:is(a, b)` bleibt heil). */
function splitSelectorList(prelude: string): string[] {
  const parts: string[] = []
  let depth = 0
  let quote: string | null = null
  let current = ''
  for (const character of prelude) {
    if (quote !== null) {
      current += character
      if (character === quote) {
        quote = null
      }
      continue
    }
    if (character === '"' || character === "'") {
      quote = character
      current += character
      continue
    }
    if (character === '(' || character === '[') {
      depth += 1
    } else if (character === ')' || character === ']') {
      depth -= 1
    }
    if (character === ',' && depth === 0) {
      parts.push(current.trim())
      current = ''
      continue
    }
    current += character
  }
  if (current.trim().length > 0) {
    parts.push(current.trim())
  }
  return parts
}

interface CssDeclaration {
  property: string
  value: string
  line: number
}

interface CssRule {
  selectors: string[]
  line: number
  declarations: CssDeclaration[]
  /** Prozentzeilen innerhalb von @keyframes sind keine Selektoren und werden nicht geprueft. */
  insideKeyframes: boolean
}

interface CssAtRule {
  name: string
  prelude: string
  line: number
}

interface CssScan {
  rules: CssRule[]
  /** Deklarationen ausserhalb jeder Regel - in einer Richtungsdatei immer ein Fehler. */
  strayDeclarations: CssDeclaration[]
  atRules: CssAtRule[]
  keyframeNames: { name: string; line: number }[]
  /** Alle per `var(--x)` referenzierten Namen. */
  varUsages: { name: string; line: number }[]
}

type Frame = { kind: 'rule'; rule: CssRule } | { kind: 'at'; name: string }

function scanCss(source: string): CssScan {
  const clean = stripComments(source)
  const lineOf = lineIndexer(clean)
  const scan: CssScan = {
    rules: [],
    strayDeclarations: [],
    atRules: [],
    keyframeNames: [],
    varUsages: [],
  }

  const stack: Frame[] = []
  let buffer = ''
  let bufferStart = 0

  function bufferLine(): number {
    const leading = buffer.length - buffer.trimStart().length
    return lineOf(bufferStart + leading)
  }

  function insideKeyframes(): boolean {
    return stack.some((frame) => frame.kind === 'at' && frame.name === 'keyframes')
  }

  function currentRule(): CssRule | null {
    const top = stack[stack.length - 1]
    return top !== undefined && top.kind === 'rule' ? top.rule : null
  }

  for (let index = 0; index < clean.length; index += 1) {
    const character = clean[index]
    if (character === '{') {
      const prelude = buffer.trim()
      const line = bufferLine()
      if (prelude.startsWith('@')) {
        const name = /^@([a-zA-Z-]+)/.exec(prelude)?.[1] ?? ''
        scan.atRules.push({ name, prelude, line })
        if (name === 'keyframes') {
          scan.keyframeNames.push({ name: prelude.replace(/^@keyframes\s+/, '').trim(), line })
        }
        stack.push({ kind: 'at', name })
      } else {
        const rule: CssRule = {
          selectors: splitSelectorList(prelude),
          line,
          declarations: [],
          insideKeyframes: insideKeyframes(),
        }
        scan.rules.push(rule)
        stack.push({ kind: 'rule', rule })
      }
      buffer = ''
      bufferStart = index + 1
      continue
    }
    if (character === '}') {
      stack.pop()
      buffer = ''
      bufferStart = index + 1
      continue
    }
    if (character === ';') {
      const text = buffer.trim()
      const line = bufferLine()
      if (text.length > 0) {
        if (text.startsWith('@')) {
          // Anweisungsform einer At-Rule, z.B. `@import '…';`
          const name = /^@([a-zA-Z-]+)/.exec(text)?.[1] ?? ''
          scan.atRules.push({ name, prelude: text, line })
        } else {
          const separator = text.indexOf(':')
          const declaration: CssDeclaration = {
            property: separator >= 0 ? text.slice(0, separator).trim() : text,
            value: separator >= 0 ? text.slice(separator + 1).trim() : '',
            line,
          }
          const rule = currentRule()
          if (rule !== null) {
            rule.declarations.push(declaration)
          } else {
            scan.strayDeclarations.push(declaration)
          }
        }
      }
      buffer = ''
      bufferStart = index + 1
      continue
    }
    buffer += character
  }

  for (const match of clean.matchAll(/var\(\s*(--[\w-]+)/g)) {
    scan.varUsages.push({ name: match[1], line: lineOf(match.index) })
  }

  return scan
}

/**
 * Die fuenf Richtungs-Ids sind hier bewusst HART hinterlegt - keine Doppelpflege, sondern die
 * woertliche Wiedergabe von Akzeptanzkriterium 2 und zugleich der Motor der Rot-Gruen-Zyklen:
 * solange eine Richtungsdatei fehlt oder unvollstaendig ist, ist die Suite rot.
 */
const DIRECTION_IDS = ['organic', 'klar', 'verspielt', 'minimal', 'kreativ'] as const

const MODES = ['light', 'dark'] as const

function readDirectionCss(id: string): string {
  return readFileSync(join(DIRECTIONS_DIR, `${id}.css`), 'utf8')
}

/** Entfernt Anfuehrungszeichen und Leerraum, damit Selektoren vergleichbar werden. */
function normalizeSelector(selector: string): string {
  return selector.replace(/['"]/g, '').replace(/\s+/g, '')
}

function isScopedTo(selector: string, id: string): boolean {
  // Am Anfang verankert, damit `.dl-tile [data-direction='minimal']` (Nachfahre statt Wurzel)
  // nicht durchrutscht.
  return new RegExp(`^\\[data-direction=(['"]?)${id}\\1\\]`).test(selector.trim())
}

/* ==========================================================================================
 * G2 - Richtungs-Isolation
 * ========================================================================================== */

describe('G2 - Richtungs-Isolation', () => {
  it.each(DIRECTION_IDS)('directions/%s.css ist vollstaendig auf sich selbst gescopt', (id) => {
    const scan = scanCss(readDirectionCss(id))
    const offenders: string[] = []

    // (a) Jeder Selektor jeder Regel beginnt mit [data-direction='<eigener Dateiname>'].
    for (const rule of scan.rules) {
      if (rule.insideKeyframes) {
        continue
      }
      for (const selector of rule.selectors) {
        if (!isScopedTo(selector, id)) {
          offenders.push(
            `directions/${id}.css:${rule.line} – Selektor "${selector}" ist nicht auf ` +
              `[data-direction='${id}'] gescopt. Fuenf Stylesheets sind gleichzeitig geladen; ` +
              'diese Regel schlaegt in die anderen vier Richtungen durch und macht den Vergleich ' +
              `ungueltig. Erwartet: [data-direction='${id}'] ${selector}`
          )
        }
      }
    }

    // (b) Keine Deklaration ausserhalb einer Regel.
    for (const declaration of scan.strayDeclarations) {
      offenders.push(
        `directions/${id}.css:${declaration.line} – Deklaration "${declaration.property}" steht ` +
          'ausserhalb jeder Regel und waere damit ungescopt.'
      )
    }

    // (c) Verbotene At-Rules: @import, @font-face, @media (prefers-color-scheme: …).
    for (const atRule of scan.atRules) {
      if (atRule.name === 'import' || atRule.name === 'font-face') {
        offenders.push(
          `directions/${id}.css:${atRule.line} – @${atRule.name} ist verboten: eine Richtung, die ` +
            'sich eine Schrift oder ein Stylesheet von aussen zieht, verletzt den Umsetzbarkeits-' +
            'Vorbehalt und waere offline nicht durchklickbar.'
        )
      }
      if (atRule.name === 'media' && atRule.prelude.includes('prefers-color-scheme')) {
        offenders.push(
          `directions/${id}.css:${atRule.line} – prefers-color-scheme ist verboten: der Modus wird ` +
            'im Labor ausschliesslich ueber data-mode gesteuert, ein Media-Query wuerde die Ansicht ' +
            '"Beide Modi" unterlaufen.'
        )
      }
    }

    const lines = readDirectionCss(id).split('\n')
    lines.forEach((text, index) => {
      // (d) Kein url() auf eine externe Ressource.
      if (/url\(\s*['"]?(https?:)?\/\//i.test(text)) {
        offenders.push(
          `directions/${id}.css:${index + 1} – externe Ressource in url(): das Labor muss offline ` +
            'durchklickbar bleiben und darf keine neue externe Abhaengigkeit einfuehren.'
        )
      }
    })

    // (e) @keyframes-Namen sind global und muessen deshalb mit der Richtungs-Id beginnen.
    for (const keyframe of scan.keyframeNames) {
      if (!keyframe.name.startsWith(id)) {
        offenders.push(
          `directions/${id}.css:${keyframe.line} – @keyframes "${keyframe.name}" beginnt nicht mit ` +
            `"${id}". Keyframe-Namen sind global und kollidieren zwischen fuenf gleichzeitig ` +
            'geladenen Stylesheets.'
        )
      }
    }

    for (const rule of scan.rules) {
      for (const declaration of rule.declarations) {
        // (f) content: nur leerer String oder none - sonst fuegt eine Richtung Inhalt hinzu, den
        // die anderen vier nicht zeigen.
        if (declaration.property === 'content') {
          const value = declaration.value.trim()
          if (value !== "''" && value !== '""' && value !== 'none') {
            offenders.push(
              `directions/${id}.css:${declaration.line} – content: ${value} fuegt Inhalt hinzu, den ` +
                'die anderen Richtungen nicht zeigen (AK "identische Beispielinhalte").'
            )
          }
        }
        // (g) Die Spaltenzahl des Rasters ist in jeder Richtung gleich (base.css).
        if (
          declaration.property === 'grid-template-columns' &&
          rule.selectors.some((selector) => selector.includes('.dl-grid'))
        ) {
          offenders.push(
            `directions/${id}.css:${declaration.line} – grid-template-columns auf .dl-grid ` +
              'veraendert die festgeschriebene Spaltenzahl 2/3/4; dann verglichen wir ' +
              'Informationsmenge statt Gestaltung.'
          )
        }
      }
    }

    expect(offenders).toEqual([])
  })
})

/* ==========================================================================================
 * G3 - Umsetzbarkeits-Vorbehalt: vollstaendiger Tokensatz in beiden Modi
 * ========================================================================================== */

/** Alle Custom Properties eines Regelsatzes, dessen Selektor `match` erfuellt. */
function customPropertiesOf(scan: CssScan, match: (selector: string) => boolean): Map<string, string> {
  const properties = new Map<string, string>()
  for (const rule of scan.rules) {
    if (!rule.selectors.some(match)) {
      continue
    }
    for (const declaration of rule.declarations) {
      if (declaration.property.startsWith('--')) {
        properties.set(declaration.property, declaration.value)
      }
    }
  }
  return properties
}

/**
 * Pflicht-Tokensatz, ABGELEITET aus frontend/src/index.css statt hier gepflegt: Vereinigung
 * beider `:root`-Bloecke (der Dunkelblock ist ein Delta und deklariert z.B. --sans gar nicht),
 * abzueglich der Tonleiter-Sprossen (alles, was auf eine dreistellige Hunderterstufe endet).
 * Aendert sich index.css, aendert sich der Sollwert automatisch mit.
 */
function requiredTokens(): string[] {
  const scan = scanCss(readFileSync(APP_INDEX_CSS, 'utf8'))
  const all = customPropertiesOf(scan, (selector) => normalizeSelector(selector) === ':root')
  return [...all.keys()].filter((name) => !/^--.*-[1-9]00$/.test(name)).sort()
}

describe('G3 - Umsetzbarkeits-Vorbehalt (Tokenvertrag)', () => {
  it('Richtungsdateien und Registry fuehren genau die fuenf erwarteten Ids', () => {
    // (a) Dateien
    const cssBasenames = readdirSync(DIRECTIONS_DIR)
      .filter((name) => name.endsWith('.css'))
      .map((name) => name.replace(/\.css$/, ''))
      .sort()
    expect(cssBasenames).toEqual([...DIRECTION_IDS].sort())

    // (b) Registry - eine Datei ohne Registry-Eintrag waere im Labor unsichtbar, ein
    // Registry-Eintrag ohne Datei ein Ladefehler.
    const registry = readFileSync(join(DIRECTIONS_DIR, 'index.ts'), 'utf8')
    const registeredIds = [...registry.matchAll(/\bid:\s*'([a-z-]+)'/g)].map((match) => match[1])
    expect([...registeredIds].sort()).toEqual([...DIRECTION_IDS].sort())
  })

  it('der Pflicht-Tokensatz wird aus frontend/src/index.css abgeleitet', () => {
    const tokens = requiredTokens()
    // Bewusst KEINE Behauptung einer festen Zahl - der Sollwert kommt aus index.css. Die Zahl
    // steht nur in der Ausgabe, damit ein Sprung auffaellt.
    expect(
      `Pflicht-Tokensatz aus frontend/src/index.css: ${tokens.length} Tokens`
    ).toContain('Tokens')
    expect(tokens.length).toBeGreaterThan(0)
    expect(tokens).toContain('--bg')
    expect(tokens).toContain('--mono')
    // Tonleiter-Sprossen sind ausgenommen.
    expect(tokens).not.toContain('--neutral-100')
    expect(tokens).not.toContain('--accent-2-600')
  })

  it.each(DIRECTION_IDS)(
    'directions/%s.css fuellt beide Modus-Bloecke vollstaendig und ist var()-selbstgenuegsam',
    (id) => {
      const source = readDirectionCss(id)
      const scan = scanCss(source)
      const tokens = requiredTokens()
      const offenders: string[] = []

      for (const mode of MODES) {
        const expected = `[data-direction=${id}][data-mode=${mode}]`
        const block = customPropertiesOf(
          scan,
          (selector) => normalizeSelector(selector) === expected
        )
        if (block.size === 0) {
          offenders.push(
            `directions/${id}.css: Block [data-direction='${id}'][data-mode='${mode}'] fehlt ` +
              'vollstaendig. Ein gemeinsamer Basisblock erfuellt die Pflicht nicht - die Ansicht ' +
              '"Beide Modi" zeigt beide Bloecke gleichzeitig.'
          )
          continue
        }
        // (c) Alle Pflicht-Tokens, in JEDEM der beiden Bloecke.
        const missing = tokens.filter((token) => !block.has(token))
        if (missing.length > 0) {
          offenders.push(
            `directions/${id}.css: Block [data-direction='${id}'][data-mode='${mode}'] definiert ` +
              `${tokens.length - missing.length} von ${tokens.length} Pflicht-Tokens. Fehlen: ` +
              `${missing.join(', ')}. Der Pflichtsatz stammt aus frontend/src/index.css ` +
              '(Vereinigung beider :root-Bloecke, ohne Tonleitern) - eine Richtung, die ihn nicht ' +
              'vollstaendig fuellt, ist nicht ohne Zusatzarbeit in die App uebernehmbar ' +
              '(AK "Umsetzbarkeits-Vorbehalt").'
          )
        }
        // (d) color-scheme passend zum Modus.
        const colorScheme = customPropertiesOfAny(scan, expected, 'color-scheme')
        if (colorScheme !== mode) {
          offenders.push(
            `directions/${id}.css: Block [data-direction='${id}'][data-mode='${mode}'] setzt ` +
              `color-scheme: ${colorScheme ?? '(fehlt)'} statt ${mode}. Ohne color-scheme ziehen ` +
              'native Bedienelemente (Zahlfeld, Scrollbalken) nicht mit.'
          )
        }
      }

      // (e) var()-Selbstgenuegsamkeit: das Labor laedt frontend/src/index.css nicht, mitkopierte
      // Verweise auf die Tonleitern (--accent-2-600, --neutral-800, …) waeren dort still leer.
      const declared = new Set<string>()
      for (const rule of scan.rules) {
        for (const declaration of rule.declarations) {
          if (declaration.property.startsWith('--')) {
            declared.add(declaration.property)
          }
        }
      }
      for (const usage of scan.varUsages) {
        if (!declared.has(usage.name)) {
          offenders.push(
            `directions/${id}.css:${usage.line} – var(${usage.name}) verweist auf ein Token, das in ` +
              'dieser Datei nicht definiert ist. Das Labor laedt frontend/src/index.css nicht; die ' +
              'Tonleitern existieren dort nicht. Wert auf seinen Hexwert aufloesen.'
          )
        }
      }

      expect(offenders).toEqual([])
    }
  )
})

/** Wert einer NICHT-Custom-Property (z.B. `color-scheme`) im Block mit exakt diesem Selektor. */
function customPropertiesOfAny(
  scan: CssScan,
  normalizedSelector: string,
  property: string
): string | null {
  for (const rule of scan.rules) {
    if (!rule.selectors.some((selector) => normalizeSelector(selector) === normalizedSelector)) {
      continue
    }
    for (const declaration of rule.declarations) {
      if (declaration.property === property) {
        return declaration.value.trim()
      }
    }
  }
  return null
}

/* ==========================================================================================
 * G4 - Kontrast-Untergrenze
 * ========================================================================================== */

interface Rgb {
  r: number
  g: number
  b: number
}

function parseHex(value: string): Rgb | null {
  const short = /^#([0-9a-f])([0-9a-f])([0-9a-f])$/i.exec(value)
  if (short !== null) {
    return {
      r: Number.parseInt(short[1] + short[1], 16),
      g: Number.parseInt(short[2] + short[2], 16),
      b: Number.parseInt(short[3] + short[3], 16),
    }
  }
  const long = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(value)
  if (long !== null) {
    return {
      r: Number.parseInt(long[1], 16),
      g: Number.parseInt(long[2], 16),
      b: Number.parseInt(long[3], 16),
    }
  }
  return null
}

/**
 * Loest einen Farbwert auf: `#rgb`/`#rrggbb` sowie `color-mix(in srgb, <hex> <p>%, <hex>)` (deckt
 * die Dunkelmodus-Tints ab). Alles andere - `transparent`, ein anderer Farbraum, eine nicht
 * aufloesbare Funktion - liefert `null` und wird im Test uebersprungen und GEZAEHLT: "gruen" darf
 * nicht "nichts geprueft" bedeuten koennen.
 */
function resolveColor(value: string): Rgb | null {
  const trimmed = value.trim()
  const direct = parseHex(trimmed)
  if (direct !== null) {
    return direct
  }
  const mix = /^color-mix\(\s*in\s+srgb\s*,\s*(#[0-9a-f]{3,8})\s+([\d.]+)%\s*,\s*(#[0-9a-f]{3,8})\s*\)$/i.exec(
    trimmed
  )
  if (mix === null) {
    return null
  }
  const first = parseHex(mix[1])
  const second = parseHex(mix[3])
  if (first === null || second === null) {
    return null
  }
  const weight = Number(mix[2]) / 100
  return {
    r: first.r * weight + second.r * (1 - weight),
    g: first.g * weight + second.g * (1 - weight),
    b: first.b * weight + second.b * (1 - weight),
  }
}

function relativeLuminance({ r, g, b }: Rgb): number {
  const channel = (raw: number): number => {
    const scaled = raw / 255
    return scaled <= 0.03928 ? scaled / 12.92 : ((scaled + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
}

function contrastRatio(foreground: Rgb, background: Rgb): number {
  const lighter = Math.max(relativeLuminance(foreground), relativeLuminance(background))
  const darker = Math.min(relativeLuminance(foreground), relativeLuminance(background))
  return (lighter + 0.05) / (darker + 0.05)
}

/**
 * Die zu pruefenden Paare werden aus der NAMENSKONVENTION abgeleitet (`X-fg` gehoert zu `X`,
 * `-strong` zu `-tint`), nicht aus der Kontrasttabelle des UI/UX-Abschnitts abgeschrieben.
 *
 * Bewusst ausgenommen: `--border` gegen `--bg` und `--accent` als Chrome (Schwelle 3:1 statt
 * 4.5:1). Der UI/UX-Abschnitt weist fuer `organic` ausdruecklich 1.37/1.69 aus - die bekannte
 * Rahmenluecke der heutigen App, die `organic.css` 1:1 uebernimmt und nicht "verbessern" darf.
 */
function contrastPairs(tokens: Map<string, string>): { foreground: string; background: string }[] {
  const pairs: { foreground: string; background: string }[] = []
  for (const background of ['--bg', '--surface']) {
    for (const foreground of ['--text', '--text-h']) {
      pairs.push({ foreground, background })
    }
  }
  for (const name of tokens.keys()) {
    if (name.endsWith('-fg')) {
      const background = name.slice(0, -'-fg'.length)
      if (tokens.has(background)) {
        pairs.push({ foreground: name, background })
      }
      continue
    }
    if (name.endsWith('-strong')) {
      const background = `${name.slice(0, -'-strong'.length)}-tint`
      if (tokens.has(background)) {
        pairs.push({ foreground: name, background })
      }
    }
  }
  return pairs
}

const MINIMUM_CONTRAST = 4.5

describe('G4 - Kontrast-Untergrenze', () => {
  it.each(DIRECTION_IDS)(
    'directions/%s.css haelt 4.5:1 fuer Text-/Symbolpaarungen in beiden Modi',
    (id) => {
      const scan = scanCss(readDirectionCss(id))
      const offenders: string[] = []
      const skipped: string[] = []
      let checked = 0

      for (const mode of MODES) {
        const expected = `[data-direction=${id}][data-mode=${mode}]`
        const tokens = customPropertiesOf(
          scan,
          (selector) => normalizeSelector(selector) === expected
        )
        for (const pair of contrastPairs(tokens)) {
          const foregroundValue = tokens.get(pair.foreground) ?? ''
          const backgroundValue = tokens.get(pair.background) ?? ''
          const foreground = resolveColor(foregroundValue)
          const background = resolveColor(backgroundValue)
          if (foreground === null || background === null) {
            skipped.push(
              `${mode}: ${pair.foreground} (${foregroundValue}) auf ${pair.background} ` +
                `(${backgroundValue})`
            )
            continue
          }
          checked += 1
          const ratio = contrastRatio(foreground, background)
          if (ratio < MINIMUM_CONTRAST) {
            offenders.push(
              `directions/${id}.css [data-mode='${mode}']: ${pair.foreground} ` +
                `(${foregroundValue}) auf ${pair.background} (${backgroundValue}) erreicht ` +
                `${ratio.toFixed(2)}:1, gefordert sind ${MINIMUM_CONTRAST}:1 (Symbol/Text auf ` +
                'gefuellter Flaeche, UI/UX-Abschnitt "Barrierefreiheit").'
            )
          }
        }
      }

      /*
       * "gruen" darf nicht "nichts geprueft" bedeuten. Uebersprungen werden darf ein Paar nur
       * dann, wenn ein Operand nicht statisch aufloesbar ist - praktisch nur `transparent`
       * (Kontrast ueber halbtransparenter Flaeche hat kein statisch bestimmbares Verhaeltnis).
       * Jeder andere Uebersprung ist ein Fehler und wird hier mit den Rohwerten sichtbar.
       */
      const unexplainedSkips = skipped.filter((entry) => !entry.includes('transparent'))
      expect(unexplainedSkips).toEqual([])
      expect(checked).toBeGreaterThan(0)
    }
  )
})
