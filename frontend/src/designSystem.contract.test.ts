// @vitest-environment node
/*
 * Design-Vertrag "Dark Utility Register" (specs/features/0320-dark-utility-register.md,
 * Teststrategie; Werte in decisions/0055-dark-utility-register-fundament.md und
 * specs/architecture/0005-board-dark-utility-register.md).
 *
 * WARUM DIESE EBENE UEBERHAUPT EXISTIERT: Die uebrigen Frontend-Tests selektieren
 * konventionsgemaess ueber Rollen, `aria-*` und semantische `data-*` und sind gegenueber einer
 * reinen Umgestaltung blind - von der gesamten Suite brechen durch die Umstellung nur fuenf
 * Assertions. Komponententests bekommen bewusst KEINE CSS-Assertions (sie wuerden Stufe 2,
 * Issue #321, nicht ueberleben). Alles, was am Design-System eine ausgerechnete Zusage traegt
 * oder eine Streichung belegen soll, wird stattdessen hier gepruefte Datei-Ebene.
 *
 * SELBSTAUSSCHLUSS: Diese Datei enthaelt die gestrichenen Tokens und die alten Hexwerte als
 * SUCHBEGRIFFE. Sie ist deshalb aus dem eigenen Streich-Scan ausgenommen - andernfalls fiele der
 * Test ueber seine eigenen Suchmuster.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { compile } from '@tailwindcss/node'
import { describe, expect, it } from 'vitest'

const SRC_DIR = fileURLToPath(new URL('.', import.meta.url))
const FRONTEND_DIR = fileURLToPath(new URL('..', import.meta.url))

const INDEX_CSS_PATH = join(SRC_DIR, 'index.css')
const INDEX_HTML_PATH = join(FRONTEND_DIR, 'index.html')
const VITE_CONFIG_PATH = join(FRONTEND_DIR, 'vite.config.ts')

const SELF_FILE = 'designSystem.contract.test.ts'

const indexCss = readFileSync(INDEX_CSS_PATH, 'utf8')
const indexHtml = readFileSync(INDEX_HTML_PATH, 'utf8')
const viteConfig = readFileSync(VITE_CONFIG_PATH, 'utf8')

// ---------------------------------------------------------------------------------------------
// Dateizugriff
// ---------------------------------------------------------------------------------------------

function walk(dir: string): string[] {
  const found: string[] = []
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry)
    if (statSync(full).isDirectory()) {
      found.push(...walk(full))
    } else {
      found.push(full)
    }
  }
  return found
}

/** Alle Dateien unter `frontend/src/**` plus `index.html` und `vite.config.ts` - der Scan darf
 * NICHT auf `index.css` beschraenkt bleiben, sonst blitzt beim PWA-Start weiterhin die alte
 * Manifest-Farbe auf und die CI bliebe gruen. Diese Datei selbst ist ausgenommen (s.o.). */
const scannedFiles: { path: string; label: string; content: string }[] = [
  ...walk(SRC_DIR)
    .filter((path) => !path.endsWith(SELF_FILE))
    .map((path) => ({ path, label: `src/${path.slice(SRC_DIR.length)}`, content: readFileSync(path, 'utf8') })),
  { path: INDEX_HTML_PATH, label: 'index.html', content: indexHtml },
  { path: VITE_CONFIG_PATH, label: 'vite.config.ts', content: viteConfig },
]

const sourceFiles = scannedFiles.filter(
  (file) => file.label.endsWith('.tsx') || (file.label.endsWith('.ts') && file.label.startsWith('src/'))
)

function findOccurrences(needle: string | RegExp): string[] {
  const pattern = typeof needle === 'string' ? null : new RegExp(needle.source, needle.flags.replace('g', '') + 'g')
  const hits: string[] = []
  for (const file of scannedFiles) {
    const lines = file.content.split('\n')
    lines.forEach((line, index) => {
      const match = pattern === null ? line.includes(needle as string) : pattern.test(line)
      if (pattern !== null) pattern.lastIndex = 0
      if (match) hits.push(`${file.label}:${index + 1}: ${line.trim()}`)
    })
  }
  return hits
}

// ---------------------------------------------------------------------------------------------
// :root-Parser
// ---------------------------------------------------------------------------------------------

/** Tokens ohne Farbwert - jedes andere `:root`-Token MUSS ein 6-stelliger Hexwert sein, damit die
 * Kontrastmatrix es rechnen kann. Ein `var()`- oder `color-mix()`-Wert waere ein Loch mit gruener
 * CI: er liesse sich nicht nachrechnen. */
const NON_COLOR_TOKENS = new Set(['--sans', '--mono'])

function parseRootTokens(css: string): Map<string, string> {
  const openIndex = css.indexOf(':root {')
  if (openIndex === -1) {
    throw new Error('Kein :root-Block in index.css gefunden.')
  }
  let depth = 0
  let end = -1
  const braceStart = css.indexOf('{', openIndex)
  for (let i = braceStart; i < css.length; i += 1) {
    if (css[i] === '{') depth += 1
    else if (css[i] === '}') {
      depth -= 1
      if (depth === 0) {
        end = i
        break
      }
    }
  }
  if (end === -1) {
    throw new Error(':root-Block in index.css ist nicht geschlossen.')
  }

  const body = css.slice(braceStart + 1, end).replace(/\/\*[\s\S]*?\*\//g, '')
  const tokens = new Map<string, string>()
  for (const raw of body.split(';')) {
    const declaration = raw.trim()
    if (declaration.length === 0) continue
    // Bewusst KEIN stilles Ueberspringen: eine unparsebare Zeile ist genau die Fehlerklasse,
    // gegen die dieser Test antritt (ein ungeprueftes Token mit gruener CI).
    const match = /^(--[a-z0-9-]+)\s*:\s*([^]+)$/.exec(declaration)
    if (match === null) {
      throw new Error(`Unparsebare Deklaration im :root-Block: "${declaration}"`)
    }
    tokens.set(match[1], match[2].trim())
  }
  return tokens
}

const rootTokens = parseRootTokens(indexCss)

function hexOf(token: string): string {
  const value = rootTokens.get(token)
  if (value === undefined) {
    throw new Error(`Token ${token} ist in index.css nicht deklariert.`)
  }
  if (!/^#[0-9a-fA-F]{6}$/.test(value)) {
    throw new Error(`Token ${token} traegt keinen 6-stelligen Hexwert, sondern "${value}".`)
  }
  return value
}

// ---------------------------------------------------------------------------------------------
// WCAG-Kontrast (selbst gerechnet, nie aus der ADR abgeschrieben)
// ---------------------------------------------------------------------------------------------

function relativeLuminance(hex: string): number {
  const channels = [1, 3, 5].map((offset) => parseInt(hex.slice(offset, offset + 2), 16) / 255)
  const linear = channels.map((c) => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)))
  return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]
}

function contrastRatio(a: string, b: string): number {
  const [lighter, darker] = [relativeLuminance(a), relativeLuminance(b)].sort((x, y) => y - x)
  return (lighter + 0.05) / (darker + 0.05)
}

const TEXT_THRESHOLD = 4.5
const GRAPHIC_THRESHOLD = 3

const SURFACES = ['--bg', '--surface', '--elevated', '--overlay'] as const

/** Das feste Kategorien-Set (backend `categories.py::CATEGORY_REGISTRY`, Anzeigereihenfolge).
 * Bewusst hier als unabhaengige Sollgroesse ausgeschrieben und NICHT aus der Chip-Tabelle des
 * Frontends importiert - sonst pruefte der Test die Tabelle gegen sich selbst. So kann eine
 * vierzehnte Kategorie weder in der CSS noch in `CategoryBadge` ungeprueft hinzukommen. */
const CATEGORY_KEYS = [
  'menschen',
  'tier',
  'pflanze',
  'landschaft',
  'gebaeude_bauwerk',
  'innenraum',
  'essen_trinken',
  'fahrzeug',
  'gegenstand',
  'dokument_screenshot',
  'kunst_kreatives',
  'sport_aktivitaet',
  'nicht_erkannt',
] as const

/** CSS-Tokennamen tragen Bindestriche statt Unterstriche, damit die daraus erzeugten Tailwind-
 * Utilities (`bg-chip-gebaeude-bauwerk-bg`) regulaere Utility-Namen bleiben. */
function chipSlug(categoryKey: string): string {
  return categoryKey.replace(/_/g, '-')
}

interface ContrastRow {
  foreground: string
  background: string
  threshold: number
}

function textRows(foreground: string): ContrastRow[] {
  return SURFACES.map((background) => ({ foreground, background, threshold: TEXT_THRESHOLD }))
}

function graphicRows(foreground: string): ContrastRow[] {
  return SURFACES.map((background) => ({ foreground, background, threshold: GRAPHIC_THRESHOLD }))
}

const chipRows: ContrastRow[] = CATEGORY_KEYS.map((key) => ({
  foreground: `--chip-${chipSlug(key)}-fg`,
  background: `--chip-${chipSlug(key)}-bg`,
  threshold: TEXT_THRESHOLD,
}))

const ratingRows: ContrastRow[] = ['favorite', 'album-worthy', 'rejected'].map((tone) => ({
  foreground: `--rating-${tone}-fg`,
  background: `--rating-${tone}`,
  threshold: TEXT_THRESHOLD,
}))

/** Status-Pillen tragen seit ADR 0055 Punkt 5 die Toast-Konstruktion des Boards: Flaeche
 * `--elevated`, farbiger Rand, farbige Beschriftung. Geprueft wird die Beschriftung. */
const statusPillRows: ContrastRow[] = ['running', 'success', 'failed', 'idle'].map((state) => ({
  foreground: `--status-${state}-strong`,
  background: '--elevated',
  threshold: TEXT_THRESHOLD,
}))

/**
 * ZUSTANDSFLAECHEN. `--border` ist nicht nur Dekorlinie, sondern auch die Flaeche, die eine
 * unaufdringliche oder sekundaere Schaltflaeche im GEDRUECKTEN Zustand annimmt (`active:bg-border`).
 * Sie steht damit real unter Text und gehoert in die Matrix - ohne diese Zeilen bleibt die
 * Kombination, die beim Tippen tatsaechlich auf dem Schirm steht, dauerhaft ungeprueft.
 *
 * Zulaessig sind dort nur `--text` (5.49) und `--text-h` (13.49). NICHT zulaessig und deshalb
 * bewusst nicht als Zeile aufgenommen: `--text-muted` (4.36) und `--danger-text` (4.33) - beide
 * verfehlen die Schwelle knapp. Die Regel weiter unten haelt das zusaetzlich statisch fest, damit
 * eine fehlende Matrixzeile nicht als Erlaubnis missverstanden wird.
 */
const stateSurfaceRows: ContrastRow[] = [
  { foreground: '--text', background: '--border', threshold: TEXT_THRESHOLD },
  { foreground: '--text-h', background: '--border', threshold: TEXT_THRESHOLD },
]

const inkRows: ContrastRow[] = [
  { foreground: '--accent-fg', background: '--accent', threshold: TEXT_THRESHOLD },
  { foreground: '--status-success-fg', background: '--status-success', threshold: TEXT_THRESHOLD },
]

const contrastRows: ContrastRow[] = [
  ...textRows('--text-h'),
  ...textRows('--text'),
  ...textRows('--text-muted'),
  ...textRows('--accent'),
  ...textRows('--accent-strong'),
  ...textRows('--accent-2'),
  ...textRows('--accent-2-strong'),
  ...textRows('--info'),
  ...textRows('--danger-text'),
  ...graphicRows('--danger'),
  // Die Bewertungstoene tragen auf der Toast-/Vorschlags-Konstruktion (gedaempfte Flaeche,
  // farbiger Rand, farbige Beschriftung) auch Text. Favorit und Album-wuerdig halten AA auf allen
  // vier Flaechen; Aussortiert erreicht nur 3.96 auf --overlay und ist deshalb ausschliesslich
  // grafisch zulaessig - fuer Text in dieser Farbe gibt es --danger-text.
  ...textRows('--rating-favorite'),
  ...textRows('--rating-album-worthy'),
  ...graphicRows('--rating-rejected'),
  ...graphicRows('--border-control'),
  ...graphicRows('--status-running'),
  ...graphicRows('--status-success'),
  ...graphicRows('--status-failed'),
  ...inkRows,
  ...stateSurfaceRows,
  ...ratingRows,
  ...statusPillRows,
  ...chipRows,
]

/**
 * Zwei begruendete Ausnahmen von der Kontrastpflicht:
 * - `--text-disabled`: WCAG 1.4.3/1.4.11 nehmen inaktive Bedienelemente ausdruecklich aus. Die
 *   Ausnahme haengt an der Verwendungsregel weiter unten (nur als `disabled:`-Variante).
 * - `--border`: rein dekorative Trenn-/Panellinie, nie einziger Umriss eines Bedienelements -
 *   dafuer gibt es `--border-control`.
 */
const CONTRAST_EXEMPT = new Set(['--text-disabled', '--border'])

/** Namensfamilien, die eine Vordergrundrolle tragen (Text, Symbol, Bedienelement-Umriss). Bewusst
 * als Regelmenge statt als abgeschriebene Namensliste: ein NEUES Token aus einer dieser Familien
 * muss zwingend in einer Matrixzeile auftauchen, sonst schlaegt der Deckungstest fehl. */
const FOREGROUND_PATTERNS: RegExp[] = [
  /^--text(-.+)?$/,
  /^--accent(-strong|-fg|-2|-2-strong)?$/,
  /^--info$/,
  /^--danger(-text)?$/,
  /^--border(-control)?$/,
  /^--rating-[a-z-]+$/,
  /^--status-(running|success|failed)$/,
  /^--status-.+-(strong|fg)$/,
  /^--chip-.+-fg$/,
]

describe('Design-Vertrag: Kontrastmatrix', () => {
  // Tautologie-Brecher: Die Formel wird gegen drei extern belegte Referenzpaare kalibriert, statt
  // die in der ADR ausgerechneten Zahlen als Erwartungswert abzuschreiben. Ohne die dritte,
  // FEHLSCHLAGENDE Gegenprobe koennte eine kaputte Formel (z.B. konstant 21) alles durchwinken.
  it('rechnet den WCAG-Kontrast korrekt (drei extern belegte Referenzpaare)', () => {
    expect(contrastRatio('#FFFFFF', '#000000')).toBeCloseTo(21.0, 2)
    expect(contrastRatio('#FFFFFF', '#0B0C10')).toBeCloseTo(19.55, 1)
    const knownFailure = contrastRatio('#FFFFFF', '#FF3D00')
    expect(knownFailure).toBeCloseTo(3.55, 1)
    expect(knownFailure).toBeLessThan(TEXT_THRESHOLD)
  })

  it('deklariert jedes :root-Token als 6-stelligen Hexwert', () => {
    const offenders = [...rootTokens.entries()]
      .filter(([name]) => !NON_COLOR_TOKENS.has(name))
      .filter(([, value]) => !/^#[0-9a-fA-F]{6}$/.test(value))
      .map(([name, value]) => `${name}: ${value}`)
    expect(offenders).toEqual([])
  })

  it('deklariert genau 13 Kategorie-Chip-Paare, deckungsgleich mit dem festen Kategorien-Set', () => {
    const declaredSlugs = [...rootTokens.keys()]
      .map((name) => /^--chip-(.+)-bg$/.exec(name))
      .filter((match): match is RegExpExecArray => match !== null)
      .map((match) => match[1])
      .sort()
    expect(declaredSlugs).toHaveLength(13)
    expect(declaredSlugs).toEqual([...CATEGORY_KEYS].map(chipSlug).sort())

    const declaredForegrounds = [...rootTokens.keys()].filter((name) => /^--chip-.+-fg$/.test(name))
    expect(declaredForegrounds).toHaveLength(13)
  })

  it('deklariert genau 3 Bewertungspaare und 4 Status-Pillen', () => {
    expect([...rootTokens.keys()].filter((name) => /^--rating-.+-fg$/.test(name))).toHaveLength(3)
    expect([...rootTokens.keys()].filter((name) => /^--status-.+-strong$/.test(name))).toHaveLength(4)
    expect([...rootTokens.keys()].filter((name) => /^--status-.+-tint$/.test(name))).toHaveLength(4)
  })

  it.each(contrastRows)('$foreground auf $background erreicht $threshold:1', ({ foreground, background, threshold }) => {
    const ratio = contrastRatio(hexOf(foreground), hexOf(background))
    expect(
      ratio,
      `${foreground} (${hexOf(foreground)}) auf ${background} (${hexOf(background)}) = ${ratio.toFixed(2)}:1`
    ).toBeGreaterThanOrEqual(threshold)
  })

  it('deckt jedes deklarierte Vordergrund-Token mit mindestens einer Matrixzeile ab', () => {
    const covered = new Set(contrastRows.map((row) => row.foreground))
    const uncovered = [...rootTokens.keys()]
      .filter((name) => FOREGROUND_PATTERNS.some((pattern) => pattern.test(name)))
      .filter((name) => !covered.has(name) && !CONTRAST_EXEMPT.has(name))
    expect(uncovered).toEqual([])
  })
})

// ---------------------------------------------------------------------------------------------
// Streich- und Positivpruefung
// ---------------------------------------------------------------------------------------------

/** Jedes gestrichene Token in BEIDEN Schreibweisen - CSS-Variable und Tailwind-Utility. Der
 * Bestand trug beide Formen an verschiedenen Stellen; eine Suche nur nach der CSS-Variablen haette
 * `text-neutral-500` in einer `.tsx` uebersehen. */
const STRUCK_TOKENS: { needle: string; why: string }[] = [
  { needle: '--neutral-', why: 'Organic-Tonleiter (das Board kennt keine Tonleitern)' },
  { needle: 'neutral-100', why: 'Organic-Tonleiter als Utility' },
  { needle: 'neutral-500', why: 'Organic-Tonleiter als Utility' },
  { needle: 'neutral-900', why: 'Organic-Tonleiter als Utility' },
  { needle: '--accent-100', why: 'Organic-Akzent-Tonleiter' },
  { needle: '--accent-700', why: 'Organic-Akzent-Tonleiter' },
  { needle: '--accent-2-100', why: 'Organic-Akzent-2-Tonleiter' },
  { needle: '--accent-2-700', why: 'Organic-Akzent-2-Tonleiter' },
  { needle: 'accent-200', why: 'Organic-Tonleiter als Utility' },
  { needle: 'accent-300', why: 'Organic-Tonleiter als Utility' },
  { needle: 'accent-2-200', why: 'Organic-Tonleiter als Utility' },
  { needle: 'accent-2-300', why: 'Organic-Tonleiter als Utility' },
  { needle: 'accent-2-700', why: 'Organic-Tonleiter als Utility' },
  { needle: 'accent-2-800', why: 'Organic-Tonleiter als Utility' },
  { needle: '--shadow', why: 'das Board arbeitet flach, Tiefe tragen die vier Flaechenstufen' },
  { needle: 'shadow-warm', why: 'Schatten-Utility des Organic-Systems' },
  { needle: '--heading', why: 'das Board hat keine Display-Schrift' },
  { needle: 'font-heading', why: 'Display-Schrift-Utility des Organic-Systems' },
  { needle: '--spacing-o', why: 'Organic-Dichte 1.10x' },
  { needle: 'washed', why: 'Bildwaesche des Organic-Systems' },
  { needle: 'accent-bg', why: 'Deckkraft-Tinte, statisch nicht kontrastpruefbar' },
  { needle: 'accent-border', why: 'Deckkraft-Tinte, statisch nicht kontrastpruefbar' },
  { needle: 'prefers-color-scheme', why: 'es gibt nur noch ein Farbschema' },
  { needle: 'color-scheme: light', why: 'es gibt nur noch ein Farbschema' },
  { needle: 'fonts.googleapis.com', why: 'Schriften sind self-gehostet (Offline-Anspruch, Datenschutz)' },
  { needle: 'fonts.gstatic.com', why: 'Schriften sind self-gehostet (Offline-Anspruch, Datenschutz)' },
  { needle: '@fontsource/caprasimo', why: 'Display-Schrift des Organic-Systems' },
  { needle: '@fontsource/figtree', why: 'Fliesstextschrift des Organic-Systems' },
]

/** Die Farbwelt des Organic-Systems, vollstaendig. Findet sich einer dieser Werte noch irgendwo in
 * `frontend/`, ist die Umstellung nicht vollstaendig. */
const ORGANIC_HEX_VALUES = [
  '#f5ead8', '#ebddc5', '#201e1d', '#645c50',
  '#f9f4ed', '#eee7db', '#dcd3c4', '#c0b6a5', '#a19786', '#82796a', '#474238', '#2e2b25',
  '#c67139', '#8c491a', '#fff2eb', '#ffe1d0', '#ffc6a5', '#f6a06b', '#d67f48', '#b2622d',
  '#643312', '#402310',
  '#7a8a5e', '#56633f', '#f0fae1', '#e1eecc', '#ccdbb2', '#aebf92', '#8fa073', '#728157',
  '#3d472b', '#272e1b',
  '#c9962c', '#a8442c', '#e0b455', '#e08a6f', '#f6ddd4', '#7d2f1c', '#f3b5a0',
  '#111111',
]

describe('Design-Vertrag: Streichliste', () => {
  it.each(STRUCK_TOKENS)('$needle kommt in frontend/ nicht mehr vor ($why)', ({ needle }) => {
    expect(findOccurrences(needle)).toEqual([])
  })

  it.each(ORGANIC_HEX_VALUES)('der Organic-Hexwert %s kommt in frontend/ nicht mehr vor', (hex) => {
    const pattern = new RegExp(hex.replace('#', '#'), 'i')
    expect(findOccurrences(pattern)).toEqual([])
  })
})

describe('Design-Vertrag: Positivprobe (sonst bestuende die Streichliste auch bei leerer CSS)', () => {
  it('setzt color-scheme: dark', () => {
    expect(indexCss).toMatch(/color-scheme:\s*dark/)
  })

  it('setzt die Grundflaeche auf html UND body (sonst bleibt der Ueberroll-Bereich hell)', () => {
    const htmlRule = /html\s*\{[^}]*background:\s*var\(--bg\)[^}]*\}/
    const bodyRule = /body\s*\{[^}]*background:\s*var\(--bg\)[^}]*\}/
    expect(indexCss).toMatch(htmlRule)
    expect(indexCss).toMatch(bodyRule)
  })

  it.each([
    '--bg',
    '--surface',
    '--elevated',
    '--overlay',
    '--accent',
    '--info',
    '--danger',
    '--danger-text',
    '--text-h',
    '--text',
    '--text-muted',
    '--text-disabled',
    '--border',
    '--border-control',
  ])('deklariert das neue Token %s', (token) => {
    expect(rootTokens.has(token)).toBe(true)
  })

  it.each([
    ['--bg', '#0B0C10'],
    ['--surface', '#14161F'],
    ['--elevated', '#1E2230'],
    ['--overlay', '#262B3D'],
    ['--accent', '#FFB000'],
    ['--info', '#00E5FF'],
    ['--danger', '#FF3D00'],
    ['--accent-2', '#00E676'],
  ])('bindet den Board-Kernwert %s an %s', (token, value) => {
    // Bewusst nur diese acht von rund 60 Werten an die Dokumentation gebunden - jeder weitere
    // waere Doppelpflege, die bei jeder Wertkorrektur zweimal angefasst werden muesste.
    expect(hexOf(token).toUpperCase()).toBe(value)
  })

  it('bindet index.html an die Board-Farben', () => {
    expect(indexHtml).toMatch(/<meta\s+name="theme-color"\s+content="#0B0C10"\s*\/?>/)
    expect(indexHtml).toMatch(/<meta\s+name="color-scheme"\s+content="dark"\s*\/?>/)
  })

  it('bindet das PWA-Manifest an die Board-Farben (sonst blitzt beim Start die alte Palette auf)', () => {
    expect(viteConfig).toMatch(/theme_color:\s*'#FFB000'/)
    expect(viteConfig).toMatch(/background_color:\s*'#0B0C10'/)
  })

  it('precacht die Schriftdateien (Offline-Anspruch der PWA)', () => {
    expect(viteConfig).toMatch(/globPatterns:\s*\[[^\]]*woff2/)
  })

  it('bindet die Schriften self-gehostet ueber @fontsource ein', () => {
    expect(indexCss).toMatch(/@import\s+'@fontsource\/inter\/400\.css'/)
    expect(indexCss).toMatch(/@import\s+'@fontsource\/inter\/500\.css'/)
    expect(indexCss).toMatch(/@import\s+'@fontsource\/inter\/600\.css'/)
    expect(indexCss).toMatch(/@import\s+'@fontsource\/inter\/700\.css'/)
    expect(indexCss).toMatch(/@import\s+'@fontsource\/jetbrains-mono\/400\.css'/)
  })
})

// ---------------------------------------------------------------------------------------------
// Fokus-Regel
// ---------------------------------------------------------------------------------------------

describe('Design-Vertrag: Fokusdarstellung', () => {
  it('hat genau EINE :focus-visible-Regel, global und mit abgesetzter Kontur', () => {
    // Zaehlend geprueft, nicht nur "enthaelt": mehrere Regeln waeren genau der Zustand, den die
    // Umstellung beseitigt - eine hartkodierte Ring-Versatzfarbe je Primitive erzeugt auf
    // --elevated/--overlay einen falsch getoenten Kranz.
    const matches = indexCss.match(/:focus-visible/g) ?? []
    expect(matches).toHaveLength(1)
    expect(indexCss).toMatch(/:focus-visible\s*\{[^}]*outline:\s*2px\s+solid\s+var\(--accent\)[^}]*\}/)
    expect(indexCss).toMatch(/:focus-visible\s*\{[^}]*outline-offset:\s*2px[^}]*\}/)
  })
})

// ---------------------------------------------------------------------------------------------
// Statische Verwendungsregeln
// ---------------------------------------------------------------------------------------------

const TAP_TARGET_UTILITY = 'tap-target'

/**
 * Utilities, die die eine globale Fokusdarstellung aushebeln. Der Name der outline-Utility ist
 * bewusst ZUSAMMENGESETZT statt als Literal geschrieben: Tailwind scannt auch diese Datei, und
 * ein Vorkommen hier allein wuerde die verbotene Regel in die gebaute CSS aufnehmen - ein
 * Artefakt, das beim Nachmessen am gebauten Stylesheet genau den Verdacht erzeugt, den dieser
 * Test ausraeumen soll.
 */
const FOCUS_SUPPRESSING_UTILITY = new RegExp(
  `ring-offset|focus-visible:|(^|[\\s'"\`([])(?:[a-z-]+:)*outline-${'none'}\\b`
)

function stripComments(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')
}

/** String-Literale einer Quelldatei. Template-Literale mit `${` werden uebersprungen - sonst
 * entstehen Fehlalarme aus zusammengesetzten Strings, die zur Laufzeit ganz anders aussehen. */
function stringLiterals(source: string): string[] {
  const stripped = stripComments(source)
  const literals: string[] = []
  const pattern = /'([^'\\\n]*)'|"([^"\\\n]*)"|`([^`\\]*)`/g
  let match: RegExpExecArray | null
  while ((match = pattern.exec(stripped)) !== null) {
    const value = match[1] ?? match[2] ?? match[3]
    if (value === undefined) continue
    if (value.includes('${')) continue
    literals.push(value)
  }
  return literals
}

function tsxFiles(): typeof sourceFiles {
  return sourceFiles.filter((file) => file.label.endsWith('.tsx'))
}

describe('Design-Vertrag: statische Verwendungsregeln', () => {
  it('verwendet text-text-disabled ausschliesslich als disabled:-Variante', () => {
    const offenders: string[] = []
    for (const file of sourceFiles) {
      for (const line of stripComments(file.content).split('\n')) {
        for (const word of line.split(/[\s'"`(){},]+/)) {
          if (!word.endsWith('text-text-disabled')) continue
          // Zulaessig ist jede Variante, die den deaktivierten Zustand traegt - `disabled:` am
          // Element selbst ebenso wie `has-[:disabled]:`/`group-disabled:` am umgebenden Element.
          const variants = word.slice(0, word.length - 'text-text-disabled'.length)
          if (!variants.includes('disabled')) {
            offenders.push(`${file.label}: ${line.trim()}`)
          }
        }
      }
    }
    expect(offenders).toEqual([])
  })

  it('verwendet --danger nie als Fliesstextfarbe (nur --danger-text haelt AA auf allen vier Flaechen)', () => {
    const offenders: string[] = []
    for (const file of sourceFiles) {
      for (const line of stripComments(file.content).split('\n')) {
        if (/\btext-danger\b(?!-text)/.test(line)) {
          offenders.push(`${file.label}: ${line.trim()}`)
        }
      }
    }
    expect(offenders).toEqual([])
  })

  it('setzt auf die gedrueckte Flaeche --border nur die dort gerechneten Vordergruende', () => {
    // `--text-muted` misst auf `--border` 4.36:1 und `--danger-text` 4.33:1 - beide verfehlen AA.
    // Der gedrueckte Zustand ist am Telefon der EINZIGE Zustand, den es gibt (Tailwind bindet
    // `hover:` an `@media (hover: hover)`); eine dort unlesbare Beschriftung ist deshalb kein
    // Randfall. Zulaessig sind `--text` (5.49) und `--text-h` (13.49).
    const forbiddenOnBorder = ['text-text-muted', 'text-danger-text']
    const offenders: string[] = []
    for (const file of tsxFiles()) {
      for (const literal of stringLiterals(file.content)) {
        const classes = literal.split(/\s+/)
        const usesBorderSurface = classes.some((cls) => /(^|:)bg-border$/.test(cls))
        if (!usesBorderSurface) continue
        const bad = classes.filter((cls) =>
          forbiddenOnBorder.some((name) => cls.endsWith(name))
        )
        if (bad.length > 0) {
          offenders.push(`${file.label}: ${bad.join(' ')} auf bg-border`)
        }
      }
    }
    expect(offenders).toEqual([])
  })

  it('umreisst Bedienelement-Primitive nie mit dem rein dekorativen --border', () => {
    // --border liegt bei 1.04-1.45:1 - als einziger Umriss eines Bedienelements auf dunklem Grund
    // ist der Button schlicht unsichtbar. Dafuer gibt es --border-control (>= 3:1 auf allen vier
    // Flaechen). Karten, Panels und Popover duerfen --border weiterhin als Trennlinie tragen.
    const controlPrimitives = ['ui/button.tsx', 'ui/input.tsx', 'ui/switch.tsx', 'ui/checkbox.tsx']
    const offenders: string[] = []
    for (const file of sourceFiles) {
      if (!controlPrimitives.some((name) => file.label.endsWith(name))) continue
      for (const line of stripComments(file.content).split('\n')) {
        for (const word of line.split(/[\s'"`(){},]+/)) {
          if (!word.endsWith('border-border')) continue
          // Ausnahme: der DEAKTIVIERTE Zustand. WCAG 1.4.11 nimmt inaktive Bedienelemente aus,
          // und das Board setzt dort ausdruecklich den dekorativen Rahmen ein.
          const variants = word.slice(0, word.length - 'border-border'.length)
          if (!variants.includes('disabled')) {
            offenders.push(`${file.label}: ${line.trim()}`)
          }
        }
      }
    }
    expect(offenders).toEqual([])
  })

  it('importiert lucide-react ausschliesslich benannt und ausschliesslich in ui/icon.tsx', () => {
    const importingFiles = sourceFiles.filter((file) => /from\s+'lucide-react'/.test(stripComments(file.content)))
    expect(importingFiles.map((file) => file.label)).toEqual(['src/components/ui/icon.tsx'])

    const iconSource = stripComments(importingFiles[0].content)
    const importStatements = iconSource.match(/import[^;]*from\s+'lucide-react'/g) ?? []
    expect(importStatements).toHaveLength(1)
    // Namespace-Import und berechneter Zugriff auf das Paket-Objekt hebeln das Tree-Shaking aus
    // und zoegen den vollen Lucide-Satz (~32 MB entpackt) ins Bundle.
    expect(importStatements[0]).not.toMatch(/import\s+\*/)
    expect(importStatements[0]).toMatch(/import\s*\{[^}]+\}\s*from\s+'lucide-react'/)
    expect(iconSource).not.toMatch(/require\(\s*'lucide-react'\s*\)/)
  })

  it.each(['ui/badge.tsx', 'ui/icon.tsx', 'CategoryBadge.tsx'])(
    'baut in %s keine Klassennamen zusammen (Tailwind erkennt nur statische, vollstaendige Strings)',
    (name) => {
      const file = sourceFiles.find((candidate) => candidate.label.endsWith(name))
      expect(file, `${name} nicht gefunden`).toBeDefined()
      expect(stripComments(file!.content)).not.toMatch(/`[^`]*\$\{/)
    }
  )

  it('hebelt die globale Fokusdarstellung nirgends in einer .tsx aus', () => {
    /*
     * Die eine globale :focus-visible-Regel ist die alleinige Fokusdarstellung (s.o.). Neben den
     * offensichtlichen Schreibweisen (`ring-offset`, `focus-visible:`) MUSS auch die
     * outline-unterdrueckende Utility verboten sein - und zwar in jeder Variante, mit und ohne
     * `focus:`-Praefix (der Name steht bewusst nirgends als Literal in dieser Datei, siehe
     * FOCUS_SUPPRESSING_UTILITY).
     *
     * Der Grund ist an der gebauten CSS gemessen, nicht hergeleitet: die globale Regel steht in
     * `@layer base`, die Utility in `@layer utilities`. Bei Cascade Layers gewinnt die SPAETERE
     * Ebene unabhaengig von der Spezifitaet - eine einzige solche Klasse an einem
     * Primitive nimmt der ganzen App an dieser Stelle die Fokuskontur, ohne dass irgendetwas
     * fehlschlaegt. Genau das ist hier passiert, waehrend diese Regel nur `ring-offset` und
     * `focus-visible:` kannte: der Test war gruen, die Zusage hielt nicht.
     */
    const offenders: string[] = []
    for (const file of tsxFiles()) {
      for (const line of stripComments(file.content).split('\n')) {
        if (FOCUS_SUPPRESSING_UTILITY.test(line)) {
          offenders.push(`${file.label}: ${line.trim()}`)
        }
      }
    }
    expect(offenders).toEqual([])
  })

  it('spannt die Trefferflaeche nie innerhalb eines beschneidenden Containers auf', () => {
    // Ein `overflow: hidden` auf DEMSELBEN Knoten beschneidet das Pseudo-Element still - die
    // Trefferflaeche faellt auf das sichtbare Mass zurueck, ohne dass etwas kaputt aussieht.
    const offenders: string[] = []
    for (const file of tsxFiles()) {
      for (const literal of stringLiterals(file.content)) {
        const classes = literal.split(/\s+/)
        if (classes.includes(TAP_TARGET_UTILITY) && classes.includes('overflow-hidden')) {
          offenders.push(`${file.label}: ${literal}`)
        }
      }
    }
    expect(offenders).toEqual([])
  })

  it('setzt die Trefferflaechen-Utility an allen aufspannenden Primitiven', () => {
    for (const name of ['ui/button.tsx', 'ui/switch.tsx', 'ui/checkbox.tsx']) {
      const file = sourceFiles.find((candidate) => candidate.label.endsWith(name))
      expect(file, `${name} nicht gefunden`).toBeDefined()
      expect(file!.content, `${name} ohne ${TAP_TARGET_UTILITY}`).toContain(TAP_TARGET_UTILITY)
    }
  })

  it('stellt jeder hover:-Variante der Primitive eine active:-Variante zur Seite', () => {
    // Tailwind bindet `hover:` an `@media (hover: hover)` - am Telefon faellt der Zustand ersatzlos
    // weg. Ohne `active:` erzeugt ein Fingertipp dort gar keine sichtbare Rueckmeldung.
    const offenders: string[] = []
    for (const file of sourceFiles) {
      if (!/\/ui\/[a-z]+\.tsx$/.test(file.label)) continue
      for (const literal of stringLiterals(file.content)) {
        if (literal.includes('hover:') && !literal.includes('active:')) {
          offenders.push(`${file.label}: ${literal}`)
        }
      }
    }
    expect(offenders).toEqual([])
  })
})

describe('Design-Vertrag: Formsprache und Skalen', () => {
  /*
   * Das Board kennt keine vollrunden Pillen mehr - ausser den Kategorie-Chips, und die tragen
   * Radius 16px (`rounded-xl`), nicht `rounded-full`. Diese Liste ist abschliessend: jede weitere
   * Fundstelle ist ein Fehler.
   */
  const ROUNDED_FULL_ALLOWLIST: Record<string, string> = {
    'src/components/ui/switch.tsx': 'Schalter-Spur und -Knauf (Board-Geometrie, vollrund)',
    'src/components/ui/button.tsx': 'Lade-Spinner im Button',
    'src/components/StatusTag.tsx': 'Lade-Spinner in der Status-Pille',
    'src/components/FolderBrowser.tsx': 'Lade-Spinner im Ordner-Browser',
    'src/components/StatusDot.tsx': 'Prozess-Status-Punkt',
    'src/components/CriterionDetailsPopover.tsx': 'runder Backdrop des Popover-Triggers ueber der Fotokachel',
    'src/components/CategoryOverrideMarker.tsx': 'runder Backdrop des Uebersteuerungs-Markers ueber der Fotokachel',
  }

  it('verwendet rounded-full nur noch an der abschliessenden Liste', () => {
    const offenders = tsxFiles()
      .filter((file) => stripComments(file.content).includes('rounded-full'))
      .map((file) => file.label)
      .filter((label) => !Object.hasOwn(ROUNDED_FULL_ALLOWLIST, label))
    expect(offenders).toEqual([])
  })

  it('haelt die Radienskala auf den fuenf Board-Werten', () => {
    for (const [utility, value] of [
      ['xs', '4px'],
      ['sm', '6px'],
      ['md', '8px'],
      ['lg', '12px'],
      ['xl', '16px'],
    ]) {
      expect(indexCss).toMatch(new RegExp(`--radius-${utility}:\\s*${value};`))
    }
  })

  it('verwendet das 12-Spalten-Raster mit 12px Zwischenraum an mindestens einer Stelle', () => {
    // Sonst waere es totes Inventar und nicht abnehmbar.
    const users = tsxFiles().filter((file) => {
      const source = stripComments(file.content)
      return source.includes('grid-cols-12') && /gap(-x)?-3\b/.test(source)
    })
    expect(users.length).toBeGreaterThan(0)
  })
})

describe('Design-Vertrag: Typoskala', () => {
  it('legt die Board-Groessen auf die bestehenden Tailwind-Stufen', () => {
    for (const [utility, value] of [
      ['xs', '12px'],
      ['sm', '14px'],
      ['base', '16px'],
      ['lg', '20px'],
      ['xl', '24px'],
      ['2xl', '40px'],
      ['3xl', '64px'],
    ]) {
      expect(indexCss).toMatch(new RegExp(`--text-${utility}:\\s*${value};`))
    }
  })

  it('erzeugt fuer text-4xl und groesser keine Regel mehr', async () => {
    const compiled = await compile(indexCss, { base: SRC_DIR, onDependency: () => {} })
    const baseline = compiled.build([])
    for (const utility of ['text-4xl', 'text-5xl', 'text-6xl', 'text-7xl', 'text-8xl', 'text-9xl']) {
      expect(compiled.build([utility]), utility).toBe(baseline)
    }
    // Gegenprobe: die verbliebenen Stufen erzeugen sehr wohl eine Regel - sonst bestuende der
    // Test auch bei einer voellig kaputten Skala.
    for (const utility of ['text-xs', 'text-3xl']) {
      expect(compiled.build([utility]), utility).not.toBe(baseline)
    }
  }, 30_000)

  it('laesst den Fehlerumriss am Eingabefeld auch im fokussierten Zustand stehen', async () => {
    // Fokussiert UND fehlerhaft duerfen sich nicht gegenseitig ausloeschen: der Fehlerumriss bleibt
    // AM Feld, die Fokusdarstellung liegt als abgesetzte Kontur aussen herum. Das haengt an der
    // Reihenfolge, in der Tailwind die beiden Varianten ausgibt - eine kuenftige Umsortierung im
    // Framework wuerde die Zusage still brechen, deshalb hier festgehalten statt angenommen.
    const compiled = await compile(indexCss, { base: SRC_DIR, onDependency: () => {} })
    const output = compiled.build(['focus:border-accent', 'aria-invalid:border-danger'])
    expect(output.indexOf('aria-invalid\\:border-danger')).toBeGreaterThan(
      output.indexOf('focus\\:border-accent')
    )
  }, 30_000)

  it('erzeugt fuer die Organic-Abstandsskala keine Regel mehr, wohl aber fuer das 8-Punkt-Raster', async () => {
    const compiled = await compile(indexCss, { base: SRC_DIR, onDependency: () => {} })
    const baseline = compiled.build([])
    for (const utility of ['p-o1', 'p-o4', 'p-o8']) {
      expect(compiled.build([utility]), utility).toBe(baseline)
    }
    // Die acht Stufen 4/8/12/16/24/32/48/64 kommen aus Tailwinds Default- --spacing.
    for (const utility of ['p-1', 'p-2', 'p-3', 'p-4', 'p-6', 'p-8', 'p-12', 'p-16']) {
      expect(compiled.build([utility]), utility).not.toBe(baseline)
    }
  }, 30_000)
})

// ---------------------------------------------------------------------------------------------
// Kompilier-Pruefung
// ---------------------------------------------------------------------------------------------

/** Namensraeume, deren Werte aus dem Design-System kommen. Nur hier kann eine gestrichene Utility
 * still keine Regel mehr erzeugen - `p-4`/`flex`/`gap-2` haengen nicht an unseren Tokens. */
const DESIGN_UTILITY_ROOTS = [
  'bg',
  'text',
  'border',
  'ring',
  'outline',
  'fill',
  'stroke',
  'caret',
  'decoration',
  'divide',
  'placeholder',
  'shadow',
  'font',
  'rounded',
]

/** Nicht-Utilities, die zufaellig wie welche aussehen (CSS-Schluesselwoerter in Prosa/Attributen). */
const NOT_A_UTILITY = new Set(['border-box', 'text-top', 'text-bottom', 'font-face'])

function utilityCandidates(): Map<string, string> {
  const candidates = new Map<string, string>()
  for (const file of sourceFiles) {
    for (const literal of stringLiterals(file.content)) {
      for (const word of literal.split(/\s+/)) {
        if (word.length === 0) continue
        if (!/^[a-z0-9[\]&:_.,()/#%>*+~-]+$/.test(word)) continue
        const base = word.split(':').pop() ?? word
        const root = base.replace(/^-/, '').split('-')[0]
        if (!DESIGN_UTILITY_ROOTS.includes(root)) continue
        if (NOT_A_UTILITY.has(base)) continue
        if (!candidates.has(word)) candidates.set(word, file.label)
      }
    }
  }
  return candidates
}

describe('Design-Vertrag: Kompilier-Pruefung', () => {
  it('erzeugt fuer jede verwendete Design-Utility beim echten Tailwind-Lauf eine Regel', async () => {
    // Schliesst die Fehlerart "gestrichene Utility erzeugt still keine Regel" - weder Build noch
    // Typpruefung noch Komponententest sehen sie, in Tailwind ist ein unbekannter Klassenname
    // KEIN Fehler. Startet bewusst gruen: heute gibt es keine verwaisten Utilities, der Test ist
    // Regressionsnetz und kein TDD-Treiber.
    const compiled = await compile(indexCss, { base: SRC_DIR, onDependency: () => {} })
    // `output.includes('@layer utilities')` waere FALSCH: die blosse Layer-Deklaration steht immer
    // in der Ausgabe, unabhaengig davon, ob der Kandidat eine Regel erzeugt hat.
    const baseline = compiled.build([])
    const candidates = utilityCandidates()
    const dead: string[] = []
    for (const [candidate, origin] of candidates) {
      if (compiled.build([candidate]) === baseline) {
        dead.push(`${candidate} (${origin})`)
      }
    }
    expect(candidates.size).toBeGreaterThan(50)
    expect(dead).toEqual([])
  }, 30_000)
})
