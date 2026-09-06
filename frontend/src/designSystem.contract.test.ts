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

/**
 * `--separator` ist die LINIE AUF DEM GRUND (Spec 0321): sichtbare Trennlinie oder dekorative
 * Flaeche unmittelbar auf `--bg`/`--surface`. `--border` (1.04-1.45:1) verschwindet dort
 * praktisch. Zugesichert wird der Korridor gegen die beiden Flaechen, auf denen das Token
 * ueberhaupt gilt; auf `--elevated`/`--overlay` gilt es nicht, die Werte dort sind nachrichtlich
 * und tragen keine Schwelle.
 */
const SEPARATOR_MIN = 2.0
const SEPARATOR_MAX = 2.5

const separatorRows: ContrastRow[] = [
  { foreground: '--separator', background: '--bg', threshold: SEPARATOR_MIN },
  { foreground: '--separator', background: '--surface', threshold: SEPARATOR_MIN },
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
  ...separatorRows,
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
  /^--separator$/,
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

  it('haelt --separator im Zielkorridor und ueber --border, auf allen vier Flaechen', () => {
    // Die Untergrenze steht bereits als Matrixzeile. Hier zusaetzlich die OBERgrenze (darueber
    // waere es keine dekorative Linie mehr, sondern ein zweiter Grauton), und die eigentliche
    // Aussage der Umstellung: --separator ist auf JEDER Flaeche sichtbarer als --border. Ohne
    // diesen Vergleich bliebe ein Wertewechsel, der die Linie wieder verschwinden laesst,
    // unbemerkt, solange er nur ueber 2.0 landet.
    for (const surface of ['--bg', '--surface'] as const) {
      expect(contrastRatio(hexOf('--separator'), hexOf(surface))).toBeLessThanOrEqual(SEPARATOR_MAX)
    }
    for (const surface of SURFACES) {
      const separator = contrastRatio(hexOf('--separator'), hexOf(surface))
      const border = contrastRatio(hexOf('--border'), hexOf(surface))
      expect(separator, `${surface}: separator ${separator.toFixed(2)} vs border ${border.toFixed(2)}`).toBeGreaterThan(border)
    }
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

/**
 * Maskiert Regex-Metazeichen in einem Suchbegriff. Die Hexwerte unten enthalten heute keine - die
 * Absicht war trotzdem Maskierung, und sie stand vorher als `hex.replace('#', '#')` da: ein
 * No-Op, der aussah, als taete er etwas (CodeQL-Alert im PR #322). Entweder richtig maskieren
 * oder gar nicht - hier richtig, damit ein spaeter ergaenzter Suchbegriff mit Sonderzeichen nicht
 * still zu einem anderen Muster wird.
 */
function escapeForRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

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
    expect(findOccurrences(new RegExp(escapeForRegExp(hex), 'i'))).toEqual([])
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

/**
 * Entfernt Kommentarinhalt ZEILENTREU: Kommentartext wird durch Leerzeichen ersetzt, Zeilenumbrueche
 * bleiben erhalten. Ohne die Zeilentreue verschoebe ein mehrzeiliger Blockkommentar alle folgenden
 * Zeilennummern, und die Fundstellen-Meldungen des Helfers unten zeigten auf die falsche Zeile.
 */
function stripComments(source: string): string {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, (comment) => comment.replace(/[^\n]/g, ' '))
    .replace(/^\s*\/\/.*$/gm, (comment) => ' '.repeat(comment.length))
}

// ---------------------------------------------------------------------------------------------
// Fundstellengenaue Freigabelisten
// ---------------------------------------------------------------------------------------------

interface ScannedFile {
  label: string
  content: string
}

/** Eine Freigabe gilt fuer GENAU EINE Zeile einer Datei, nicht fuer die ganze Datei. */
interface AllowlistEntry {
  file: string
  /** Teilzeichenkette der freigegebenen Zeile. Darf nicht nur aus dem Suchbegriff bestehen. */
  snippet: string
  reason: string
}

interface Occurrence {
  label: string
  line: number
  text: string
  match: string
}

/**
 * Suchbegriff einer fundstellengenauen Regel. Drei Formen, in aufsteigender Ausdrucksstaerke:
 * feste Zeichenkette, regulaerer Ausdruck, oder ein ERKENNER - eine reine Funktion, die die
 * Treffer einer Zeile liefert. Die dritte Form gibt es, weil sich "Abstandsstufe ausserhalb der
 * Skala" nicht sinnvoll als ein einziger regulaerer Ausdruck schreiben laesst; als eigene Funktion
 * ist der Erkenner ausserdem tabellengetrieben gegen synthetische Zeilen pruefbar, statt inline in
 * einer Assertion vergraben zu sein.
 */
type Needle = string | RegExp | ((line: string) => string[])

/**
 * Alle Fundstellen eines Suchbegriffs, zeilengenau und ohne Kommentare. Bei einem regulaeren
 * Ausdruck bzw. einem Erkenner traegt jede Fundstelle zusaetzlich den tatsaechlich getroffenen Text.
 */
function findMatches(needle: Needle, files: ScannedFile[]): Occurrence[] {
  const found: Occurrence[] = []
  for (const file of files) {
    stripComments(file.content)
      .split('\n')
      .forEach((line, index) => {
        const base = { label: file.label, line: index + 1, text: line.trim() }
        if (typeof needle === 'string') {
          if (line.includes(needle)) found.push({ ...base, match: needle })
          return
        }
        if (typeof needle === 'function') {
          for (const match of new Set(needle(line))) {
            found.push({ ...base, match })
          }
          return
        }
        const pattern = new RegExp(needle.source, needle.flags.includes('g') ? needle.flags : `${needle.flags}g`)
        const seen = new Set<string>()
        let match: RegExpExecArray | null
        while ((match = pattern.exec(line)) !== null) {
          if (match[0].length === 0) {
            pattern.lastIndex += 1
            continue
          }
          // Mehrfachtreffer desselben Textes in einer Zeile sind EINE Fundstelle - sonst
          // meldete `gap-1.5 sm:gap-1.5` zweimal dasselbe.
          if (!seen.has(match[0])) {
            seen.add(match[0])
            found.push({ ...base, match: match[0] })
          }
        }
      })
  }
  return found
}

/** Deckt der Suchbegriff den ganzen Ausschnitt ab, ist der Ausschnitt nur der Suchbegriff. */
function isBareNeedle(snippet: string, needle: Needle): boolean {
  const trimmed = snippet.trim()
  if (typeof needle === 'string') {
    return trimmed === needle
  }
  if (typeof needle === 'function') {
    return needle(trimmed).includes(trimmed)
  }
  const match = new RegExp(needle.source, needle.flags.replace('g', '')).exec(trimmed)
  return match !== null && match[0] === trimmed
}

/**
 * Gleicht jede Fundstelle eines Suchbegriffs gegen eine fundstellengenaue Freigabeliste ab und
 * meldet DREI Fehlerklassen statt einer:
 *
 *  (a) Fundstelle ohne passenden Eintrag - die eigentliche Regel.
 *  (b) Eintrag ohne Fundstelle - verwaiste Freigabe. Genau daran verrotten solche Listen: die
 *      Zeile verschwindet, die Freigabe bleibt und deckt spaeter still etwas anderes.
 *  (c) Ausschnitt, der nur aus dem Suchbegriff selbst besteht - sonst liesse sich die alte,
 *      dateiweise Granularitaet still wiederherstellen.
 *
 * Die zu durchsuchenden Dateien sind Parameter, damit der Helfer gegen synthetische Eingaben
 * testbar ist, ohne das Dateisystem anzufassen.
 */
function allowlistedOccurrences(
  needle: Needle,
  entries: AllowlistEntry[],
  files: ScannedFile[] = tsxFiles()
): string[] {
  const problems: string[] = []
  const matched = new Set<number>()

  for (const occurrence of findMatches(needle, files)) {
    const index = entries.findIndex(
      (entry) => entry.file === occurrence.label && occurrence.text.includes(entry.snippet)
    )
    if (index === -1) {
      problems.push(`nicht freigegeben: ${occurrence.label}:${occurrence.line}: ${occurrence.text}`)
    } else {
      matched.add(index)
    }
  }

  entries.forEach((entry, index) => {
    if (!matched.has(index)) {
      problems.push(`verwaiste Freigabe ohne Fundstelle: ${entry.file} :: ${entry.snippet}`)
    }
    if (isBareNeedle(entry.snippet, needle)) {
      problems.push(`Ausschnitt ist nur der Suchbegriff selbst: ${entry.file} :: ${entry.snippet}`)
    }
  })

  return problems
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

describe('Design-Vertrag: Selbsttest des Fundstellen-Helfers', () => {
  /*
   * Der Helfer traegt vier statische Regeln. Im gruenen Produktivlauf liefern alle drei
   * Fehlerklassen die leere Menge - die Produktivnutzung belegt also NICHTS ueber seine
   * Fehlererkennung. Deshalb diese Selbsttests, ausschliesslich gegen synthetische, hier literal
   * geschriebene Dateilisten: kein Dateisystem, keine Fixture-Dateien, keine temporaeren
   * Verzeichnisse.
   */
  const needle = 'rounded-full'

  function file(label: string, ...lines: string[]): ScannedFile {
    return { label, content: lines.join('\n') }
  }

  it('meldet eine Fundstelle ohne passenden Eintrag mit Datei und Zeilennummer', () => {
    const problems = allowlistedOccurrences(needle, [], [file('src/a.tsx', 'const x = 1', 'className="rounded-full"')])

    expect(problems).toHaveLength(1)
    expect(problems[0]).toContain('src/a.tsx')
    expect(problems[0]).toContain(':2:')
  })

  it('meldet eine Fundstelle mit passendem Eintrag nicht', () => {
    const problems = allowlistedOccurrences(
      needle,
      [{ file: 'src/a.tsx', snippet: 'size-2.5 shrink-0 rounded-full', reason: 'Statuspunkt' }],
      [file('src/a.tsx', '<span className="size-2.5 shrink-0 rounded-full bg-accent" />')]
    )

    expect(problems).toEqual([])
  })

  /*
   * Der eigentliche Zweck des Umbaus und zugleich sein permanenter Rot-Nachweis: Die frueher
   * dateiweise Pruefung waere hier gruen gewesen, weil die Datei bereits gelistet ist.
   */
  it('meldet eine zweite Fundstelle in einer bereits gelisteten Datei', () => {
    const problems = allowlistedOccurrences(
      needle,
      [{ file: 'src/a.tsx', snippet: 'Spinner rounded-full', reason: 'Lade-Spinner' }],
      [file('src/a.tsx', '<i className="Spinner rounded-full" />', '<button className="rounded-full" />')]
    )

    expect(problems).toHaveLength(1)
    expect(problems[0]).toContain(':2:')
  })

  it('meldet einen Eintrag ohne jede Fundstelle als verwaiste Freigabe', () => {
    const problems = allowlistedOccurrences(
      needle,
      [{ file: 'src/weg.tsx', snippet: 'einst rounded-full', reason: 'laengst entfernt' }],
      [file('src/a.tsx', 'const x = 1')]
    )

    expect(problems).toHaveLength(1)
    expect(problems[0]).toContain('verwaiste Freigabe')
  })

  it('meldet einen Ausschnitt, der nur aus dem Suchbegriff besteht, auch bei passenden Fundstellen', () => {
    const problems = allowlistedOccurrences(
      needle,
      [{ file: 'src/a.tsx', snippet: 'rounded-full', reason: 'zu grob' }],
      [file('src/a.tsx', '<i className="rounded-full" />')]
    )

    expect(problems).toHaveLength(1)
    expect(problems[0]).toContain('nur der Suchbegriff')
  })

  it('meldet eine Fundstelle nicht, die nur in einem Zeilenkommentar steht', () => {
    const problems = allowlistedOccurrences(needle, [], [file('src/a.tsx', '// frueher rounded-full, heute nicht mehr')])

    expect(problems).toEqual([])
  })

  it('meldet eine Fundstelle nach einem mehrzeiligen Blockkommentar mit ihrer tatsaechlichen Zeile', () => {
    const problems = allowlistedOccurrences(
      needle,
      [],
      [file('src/a.tsx', '/* Zeile 1', '   Zeile 2', '   Zeile 3 */', '<i className="rounded-full" />')]
    )

    expect(problems).toHaveLength(1)
    expect(problems[0]).toContain(':4:')
  })

  it('haelt die Zeilenanzahl in stripComments unveraendert', () => {
    const source = ['/* a', 'b', 'c */', 'code', '// d'].join('\n')

    expect(stripComments(source).split('\n')).toHaveLength(source.split('\n').length)
  })

  it('meldet bei leerer Eingabemenge nichts', () => {
    expect(allowlistedOccurrences(needle, [], [])).toEqual([])
  })

  /*
   * Gegenprobe zur leeren Eingabemenge: Eine Regel, die gegen eine leere Kandidatenmenge laeuft,
   * bestuende still. Jede Produktivnutzung des Helfers unten prueft deshalb zusaetzlich, dass sie
   * ueberhaupt Kandidaten sieht - hier festgehalten, damit die Vorkehrung nicht wegoptimiert wird.
   */
  it('findet in einer nicht leeren Eingabemenge auch Fundstellen', () => {
    expect(findMatches(needle, [file('src/a.tsx', '<i className="rounded-full" />')])).toHaveLength(1)
  })
})

function tsxFiles(): typeof sourceFiles {
  return sourceFiles.filter((file) => file.label.endsWith('.tsx'))
}

/**
 * Nur die Produktivdateien. Die Skalenregeln unten gelten fuer das MARKUP des Produkts, nicht fuer
 * Testdateien: dort stehen Klassennamen als Zeichenketten in Assertionen (z.B. `input.test.tsx`
 * haelt `focus:border-[1.5px]` fest), und eine Regel, die dort anschlaegt, zwingt dazu, genau die
 * Zusicherung zu loeschen, die sie absichern soll.
 */
function productionTsxFiles(): typeof sourceFiles {
  return tsxFiles().filter((file) => !file.label.endsWith('.test.tsx'))
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
  const ROUNDED_FULL_ALLOWLIST: AllowlistEntry[] = [
    {
      file: 'src/components/ui/switch.tsx',
      snippet: 'inline-flex h-6 w-12 shrink-0 items-center rounded-full border',
      reason: 'Schalter-Spur (Board-Geometrie, vollrund)',
    },
    {
      file: 'src/components/ui/switch.tsx',
      snippet: 'inline-block size-5 translate-x-0.5 transform rounded-full',
      reason: 'Schalter-Knauf (Board-Geometrie, vollrund)',
    },
    {
      file: 'src/components/ui/button.tsx',
      snippet: 'animate-spin motion-reduce:animate-none rounded-full border-2',
      reason: 'Lade-Spinner im Button',
    },
    {
      file: 'src/components/StatusTag.tsx',
      snippet: 'inline-block size-2.5 shrink-0 rounded-full border-2',
      reason: 'Lade-Spinner in der Status-Pille',
    },
    {
      file: 'src/components/FolderBrowser.tsx',
      snippet: 'animate-spin motion-reduce:animate-none rounded-full border-2',
      reason: 'Lade-Spinner im Ordner-Browser',
    },
    {
      file: 'src/components/StatusDot.tsx',
      snippet: 'size-2.5 shrink-0 rounded-full',
      reason: 'Prozess-Status-Punkt',
    },
    {
      file: 'src/components/CriterionDetailsPopover.tsx',
      snippet: 'rounded-full border border-border-control bg-bg/85',
      reason: 'runder Backdrop des Popover-Triggers ueber der Fotokachel',
    },
    {
      file: 'src/components/CategoryOverrideMarker.tsx',
      snippet: 'items-center justify-center rounded-full bg-bg/85',
      reason: 'runder Backdrop des Uebersteuerungs-Markers ueber der Fotokachel',
    },
  ]

  it('verwendet rounded-full nur noch an der abschliessenden Liste, fundstellengenau', () => {
    // Fundstellen- statt dateiweise Pruefung: Zuvor war jede weitere `rounded-full`-Zeile in einer
    // bereits gelisteten Datei unsichtbar - `ui/button.tsx` ist wegen des Lade-Spinners freigegeben
    // und haette damit unbemerkt eine vollrunde Schaltflaeche bekommen koennen.
    expect(allowlistedOccurrences('rounded-full', ROUNDED_FULL_ALLOWLIST)).toEqual([])
    // Positiv-Gegenprobe: Die Kandidatenmenge ist nachweislich nicht leer.
    expect(findMatches('rounded-full', tsxFiles()).length).toBeGreaterThan(0)
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

// ---------------------------------------------------------------------------------------------
// Abstands- und Wertskalen (specs/features/0321-dark-utility-register-ansichten.md, "Das Netz")
// ---------------------------------------------------------------------------------------------

/**
 * Zerlegt eine Quellzeile in Utility-Kandidaten. Bewusst tokenweise statt ueber einen einzigen
 * grossen regulaeren Ausdruck: Klassenlisten stehen in Zeichenketten, Template-Teilen und
 * `cn()`-Argumenten, und ein Ausdruck mit Wortgrenzen faengt dort zuverlaessig Fehlalarme
 * (`max-w-5xl` als `w-5`) statt Treffer.
 */
function classTokens(line: string): string[] {
  // Bewusst NICHT an Klammern, Kommas oder Schraegstrichen getrennt: `w-[min(32rem,calc(100vw-
  // 2rem))]`, `aspect-[4/3]` und `bg-bg/95` sind je EIN Token. Getrennt wird an dem, was eine
  // Klassenliste im Quelltext tatsaechlich begrenzt.
  return line.split(/[\s'"`{}=;<>]+/).filter((token) => token.length > 0)
}

/**
 * Entfernt die Variantenpraefixe eines Utility-Tokens und liefert die reine Utility. Arbiträre
 * VARIANTEN (`[&::-webkit-progress-bar]:`, `data-[state=open]:`, `has-[:disabled]:`) tragen
 * ebenfalls eckige Klammern, sind aber KEINE willkuerlichen Werte - ohne dieses Abstreifen waeren
 * sie dauerhafte Fehlalarme der Regel "keine willkuerlichen Werte".
 */
function utilityBase(token: string): string {
  let rest = token
  for (;;) {
    const match = /^(?:\[[^\]]*\]|[a-z0-9-]+(?:\[[^\]]*\])?):([\s\S]*)$/.exec(rest)
    if (match === null) {
      return rest
    }
    rest = match[1]
  }
}

/*
 * REGEL 1 - ABSTANDSSKALA. Die acht Stufen des 8-Punkt-Rasters plus die Null. `auto` bleibt
 * zulaessig: es ist ein Schluesselwort (`m-auto` zentriert den Dialog), keine Abstandsstufe.
 *
 * DIES IST EINE ABSTANDS-, KEINE GROESSENREGEL. `h-11`, `size-8`, `h-0.5`, `min-w-6`, `w-full` und
 * `max-w-5xl` sind ausdruecklich nicht betroffen - ein Fehlalarm dort zwingt die Umsetzung dazu,
 * die Regel wieder aufzuweichen.
 */
const SPACING_UTILITIES = [
  'gap-x',
  'gap-y',
  'space-x',
  'space-y',
  'gap',
  'px',
  'py',
  'pt',
  'pr',
  'pb',
  'pl',
  'p',
  'mx',
  'my',
  'mt',
  'mr',
  'mb',
  'ml',
  'm',
]
const SPACING_SCALE = new Set(['0', '1', '2', '3', '4', '6', '8', '12', '16', 'auto'])
const SPACING_PATTERN = new RegExp(`^-?(${SPACING_UTILITIES.join('|')})-(.+)$`)

/** Alle Abstands-Utilities einer Zeile - Grundlage der Positiv-Gegenprobe. */
function spacingUtilities(line: string): string[] {
  return classTokens(line)
    .map((token) => utilityBase(token))
    .filter((base) => SPACING_PATTERN.test(base))
}

/** Abstands-Utilities einer Zeile, die NICHT auf der Skala liegen. */
function offendingSpacingUtilities(line: string): string[] {
  return spacingUtilities(line).filter((base) => {
    const value = SPACING_PATTERN.exec(base)?.[2] ?? ''
    return !SPACING_SCALE.has(value)
  })
}

/*
 * REGEL 2 - KEINE WILLKUERLICHEN WERTE. Ein willkuerlicher Wert umgeht jede Skala des
 * Design-Systems, ohne dass irgendetwas rot wird. Arbiträre VARIANTEN bleiben zulaessig (siehe
 * `utilityBase`).
 */
function arbitraryValues(line: string): string[] {
  return classTokens(line)
    .map((token) => utilityBase(token))
    .filter((base) => /^-?[a-z0-9-]+-\[[^\]]*\]$/.test(base))
}

/*
 * REGEL 3 - KEINE DECKKRAFT-MODIFIKATOREN AUF FARB-UTILITIES. Zwei Fehlerklassen in einer: Der
 * Kontrast einer abgedunkelten Farbe ist statisch nicht nachrechenbar, und genau so verschwinden
 * die Trennlinien auf dem Grund (`border-border/60` liegt bei 0.87:1).
 *
 * Der Erkenner ist an die FARB-NAMENSRAEUME gebunden, nicht an das Vorkommen eines Schraegstrichs -
 * `w-1/2`, `h-1/3` und `basis-1/2` sind Brueche, keine Deckkraft.
 */
const COLOR_UTILITY_ROOTS = [
  'bg',
  'text',
  'border',
  'fill',
  'stroke',
  'ring',
  'outline',
  'divide',
  'decoration',
  'placeholder',
  'caret',
  'shadow',
]
const COLOR_OPACITY_PATTERN = new RegExp(`^(${COLOR_UTILITY_ROOTS.join('|')})-[a-z0-9-]+/\\d+$`)

function colorOpacityModifiers(line: string): string[] {
  return classTokens(line)
    .map((token) => utilityBase(token))
    .filter((base) => COLOR_OPACITY_PATTERN.test(base))
}

describe('Design-Vertrag: Abstands- und Wertskalen', () => {
  /*
   * Jeder der vier Erkenner wird TABELLENGETRIEBEN gegen synthetische Zeilen geprueft, bevor er
   * produktiv laeuft. Eine statische Pruefung hat genau einen ernsten Fehlermodus: Sie findet
   * nichts und besteht deswegen. Ein kaputter regulaerer Ausdruck faellt hier auf, statt still
   * alles durchzuwinken.
   */
  it.each([
    'gap-1.5',
    'gap-2.5',
    'gap-3.5',
    'py-3.5',
    'px-5',
    'mt-5',
    'py-10',
    'px-10',
    'p-0.5',
    'mb-7',
    'sm:gap-1.5',
    'hover:py-3.5',
    '-mt-5',
  ])('erkennt %s als Abstand ausserhalb der Skala', (utility) => {
    expect(offendingSpacingUtilities(`className="${utility} flex"`)).not.toEqual([])
  })

  it.each([
    'p-0',
    'gap-1',
    'p-2',
    'gap-3',
    'p-4',
    'py-6',
    'px-8 py-8',
    'mb-12',
    'mt-16',
    'm-auto',
    'h-11',
    'size-8',
    'h-0.5',
    'min-w-6',
    'w-full',
    'max-w-5xl',
    'size-2.5',
    'translate-x-0.5',
    'text-2xl',
    'w-1/2',
  ])('erkennt %s NICHT als Abstandsverstoss', (utility) => {
    expect(offendingSpacingUtilities(`className="${utility} flex"`)).toEqual([])
  })

  it.each(['text-[10px]', 'text-[10.5px]', 'h-[50px]', 'w-[240px]', 'gap-[3px]', 'p-[7px]'])(
    'erkennt %s als willkuerlichen Wert',
    (utility) => {
      expect(arbitraryValues(`className="${utility}"`)).toEqual([utility])
    }
  )

  it.each([
    '[&::-webkit-progress-bar]:bg-accent',
    'indeterminate:[&::-moz-progress-bar]:bg-transparent',
    'data-[state=open]:flex',
    'has-[:disabled]:text-text-disabled',
    'text-xs',
    'aspect-square',
  ])('erkennt %s NICHT als willkuerlichen Wert', (utility) => {
    expect(arbitraryValues(`className="${utility}"`)).toEqual([])
  })

  it.each(['border-border/60', 'bg-border/60', 'text-text/70', 'bg-black/60', 'hover:bg-bg/95'])(
    'erkennt %s als Deckkraft-Modifikator auf einer Farb-Utility',
    (utility) => {
      expect(colorOpacityModifiers(`className="${utility}"`)).not.toEqual([])
    }
  )

  it.each(['w-1/2', 'h-1/3', 'basis-1/2', 'bg-border', 'aspect-[4/3]'])(
    'erkennt %s NICHT als Deckkraft-Modifikator',
    (utility) => {
      expect(colorOpacityModifiers(`className="${utility}"`)).toEqual([])
    }
  )

  // -----------------------------------------------------------------------------------------
  // Die Regeln selbst
  // -----------------------------------------------------------------------------------------

  it('haelt jede Abstands-Utility auf den acht Stufen des 8-Punkt-Rasters', () => {
    expect(allowlistedOccurrences(offendingSpacingUtilities, [], productionTsxFiles())).toEqual([])
    // Positiv-Gegenprobe: Die Kandidatenmenge ist nachweislich gross - die Regel laeuft nicht
    // gegen eine leere Menge und bestuende deshalb auch bei kaputtem Erkenner.
    expect(findMatches(spacingUtilities, productionTsxFiles()).length).toBeGreaterThan(100)
  })

  const ARBITRARY_VALUE_ALLOWLIST: AllowlistEntry[] = [
    {
      file: 'src/components/ui/popover.tsx',
      snippet: "'z-50 max-h-[60vh] w-72",
      reason: 'Hoehendeckel des Popover-Panels relativ zum Sichtfenster - keine Rasterstufe moeglich',
    },
    {
      file: 'src/components/ui/checkbox.tsx',
      snippet: "'size-[18px] shrink-0",
      reason: 'abgeleitetes Board-Mass des Kontrollkaestchens (zwischen size-4 und size-5)',
    },
    {
      file: 'src/components/ui/dialog.tsx',
      snippet: "'m-auto w-[min(32rem,calc(100vw-2rem))]",
      reason: 'Dialogbreite: Board-Mass, aber nie breiter als das Sichtfenster abzueglich Rand',
    },
    {
      file: 'src/components/ui/input.tsx',
      snippet: "'focus:border-[1.5px] focus:border-accent'",
      reason: 'Fokusstaerkung des Feldrands - 1.5px liegt auf keiner Tailwind-Randstufe',
    },
    {
      file: 'src/pages/PhotoDetailPage.tsx',
      snippet: "className=\"aspect-[4/3] w-full",
      reason: 'Seitenverhaeltnis der Detailbildflaeche - Tailwind kennt nur square und video',
    },
  ]

  it('verwendet willkuerliche Werte nur an der begruendeten Liste', () => {
    expect(allowlistedOccurrences(arbitraryValues, ARBITRARY_VALUE_ALLOWLIST, productionTsxFiles())).toEqual([])
    // Positiv-Gegenprobe: Die Regel laeuft nicht gegen eine leere Kandidatenmenge.
    expect(findMatches(arbitraryValues, productionTsxFiles()).length).toBeGreaterThan(0)
  })

  const COLOR_OPACITY_ALLOWLIST: AllowlistEntry[] = [
    {
      file: 'src/components/ui/dialog.tsx',
      snippet: "'backdrop:bg-black/60'",
      reason: 'Abdunklung des Hintergrunds hinter dem Modal - kein Vorder-/Hintergrundpaar',
    },
    {
      file: 'src/components/Stepper.tsx',
      snippet: 'border-b border-separator bg-bg/95',
      reason: 'durchscheinende sticky Kopfzeile der Schrittnavigation',
    },
    {
      file: 'src/components/CategoryOverrideMarker.tsx',
      snippet: 'rounded-full bg-bg/85',
      reason: 'Backdrop des Uebersteuerungs-Markers ueber einer Fotokachel',
    },
    {
      file: 'src/components/CriterionDetailsPopover.tsx',
      snippet: 'border-border-control bg-bg/85',
      reason: 'Backdrop des Info-Triggers ueber einer Fotokachel',
    },
  ]

  it('verwendet Deckkraft-Modifikatoren auf Farb-Utilities nur an der begruendeten Liste', () => {
    expect(
      allowlistedOccurrences(colorOpacityModifiers, COLOR_OPACITY_ALLOWLIST, productionTsxFiles())
    ).toEqual([])
    // Positiv-Gegenprobe: Die drei freigegebenen Abdunklungen werden tatsaechlich gefunden.
    expect(findMatches(colorOpacityModifiers, productionTsxFiles()).length).toBeGreaterThan(0)
  })

  /*
   * REGEL 4 - `opacity-*` FUNDSTELLENGENAU. Sie sichert die riskanteste Einzelentscheidung dieser
   * Stufe dauerhaft ab: Auf der aussortierten Karte wird ausschliesslich die BILDFLAECHE gedaempft,
   * nie der Kartenkoerper (ADR 0055 Abweichung 7). Ein spaeteres `opacity-40` am Koerper druecke
   * Kennzeichen und Dateinamen wieder unter die Kontrastschwelle, ohne dass sonst irgendetwas rot
   * wuerde - der Graustufen-Lauf ist ein einmaliger Ad-hoc-Lauf und traegt das nicht.
   */
  const OPACITY_ALLOWLIST: AllowlistEntry[] = [
    {
      file: 'src/components/ui/button.tsx',
      snippet: 'disabled:text-text-disabled disabled:opacity-40',
      reason: 'deaktivierte Schaltflaeche - WCAG nimmt inaktive Bedienelemente ausdruecklich aus',
    },
    {
      file: 'src/components/ui/button.tsx',
      snippet: 'bg-accent text-accent-fg hover:opacity-85 active:opacity-70',
      reason: 'Ueberfahren/Gedrueckt der primaeren Schaltflaeche - Flaeche bleibt, nur Deckkraft',
    },
    {
      file: 'src/components/ui/button.tsx',
      snippet: "'border border-border-control bg-overlay text-text-h hover:opacity-80",
      reason: 'Ueberfahren der sekundaeren Schaltflaeche (zwei Auspraegungen, gleiche Zeile)',
    },
    {
      file: 'src/components/ui/button.tsx',
      snippet: "isDisabledSlot && 'pointer-events-none opacity-40'",
      reason: 'deaktivierter asChild-Link - traegt kein natives disabled-Attribut',
    },
    {
      file: 'src/components/Stepper.tsx',
      snippet: "isBlocked && 'opacity-40'",
      reason: 'Beschriftung eines blockierten Schritts - das Schloss-Symbol bleibt voll deckend',
    },
    {
      file: 'src/components/RatingButtons.tsx',
      snippet: 'text-rating-favorite-fg hover:opacity-85 active:opacity-70',
      reason: 'aktiver Eintrag der Bewertungsleiste (Favorit)',
    },
    {
      file: 'src/components/RatingButtons.tsx',
      snippet: 'text-rating-album-worthy-fg hover:opacity-85 active:opacity-70',
      reason: 'aktiver Eintrag der Bewertungsleiste (Album-wuerdig)',
    },
    {
      file: 'src/components/RatingButtons.tsx',
      snippet: 'text-rating-rejected-fg hover:opacity-85 active:opacity-70',
      reason: 'aktiver Eintrag der Bewertungsleiste (Verwerfen)',
    },
    {
      file: 'src/components/PhotoCard.tsx',
      snippet: "aspect-square overflow-hidden rounded-md', isRejected && 'opacity-40'",
      reason:
        'gedaempfte BILDFLAECHE der aussortierten Karte - der Ausschnitt zeigt bewusst das Element, ' +
        'das den Kachel-Link traegt; am Kartenkoerper waere dieselbe Utility ein Kontrastverlust',
    },
  ]

  it('verwendet opacity-* nur an der begruendeten Liste, fundstellengenau', () => {
    expect(allowlistedOccurrences('opacity-', OPACITY_ALLOWLIST, productionTsxFiles())).toEqual([])
  })

  /*
   * `h-11`/`min-h-11` ist seit ADR 0055 Punkt 8 die AUSNAHME, nicht die Regel: Bedienelemente sind
   * sichtbar 32px hoch und beziehen ihre 44px aus der Aufspannung. Sichtbare 44px sind nur in drei
   * Faellen richtig - heisser Pfad, Zeilenhoehe zeilenweiser Listen, und Eingabefelder/
   * Kontrollkaestchen (ein ersetztes Element traegt keine Pseudo-Elemente und loest seine
   * Trefferflaeche ausschliesslich ueber die sichtbare Zeilenhoehe).
   */
  const TALL_CONTROL_ALLOWLIST: AllowlistEntry[] = [
    {
      file: 'src/components/RatingButtons.tsx',
      snippet: "const HOT_PATH_HEIGHT = 'h-11 sm:h-8'",
      reason: 'heisser Pfad: ein Fehlgriff schreibt hier einen falschen Datenwert',
    },
    {
      file: 'src/components/ui/input.tsx',
      snippet: "'h-11 w-full rounded-sm",
      reason: 'Eingabefeld: ersetztes Element ohne Pseudo-Element, Trefferflaeche = Zeilenhoehe',
    },
    {
      file: 'src/components/ui/checkbox.tsx',
      snippet: 'inline-flex min-h-11 cursor-pointer',
      reason: 'Kontrollkaestchen samt Beschriftung: dieselbe Begruendung wie beim Eingabefeld',
    },
    {
      file: 'src/components/CategorySelect.tsx',
      snippet: "className=\"h-11 rounded-sm border",
      reason: 'Auswahlfeld: ersetztes Element, zugleich heisser Pfad der Kategorie-Zuordnung',
    },
    {
      file: 'src/pages/CurateCategoriesPage.tsx',
      snippet: 'h-auto min-h-11 w-full justify-start',
      reason: 'Aufklapp-Zeile der Kuratierung: Zeilenhoehe einer zeilenweisen Liste',
    },
    {
      file: 'src/pages/LoginPage.tsx',
      snippet: "className=\"mt-2 h-11 w-full text-base\"",
      reason: 'Absende-Schaltflaeche der Anmeldung: einzige Aktion des Bildschirms, einhaendig bedient',
    },
  ]

  it('verwendet die sichtbaren 44px nur an den drei begruendeten Kategorien', () => {
    expect(
      allowlistedOccurrences(/\bmin-h-11\b|\bh-11\b/, TALL_CONTROL_ALLOWLIST, productionTsxFiles())
    ).toEqual([])
  })
})

describe('Design-Vertrag: unbestimmter Fortschritt', () => {
  /*
   * Spec 0321, UI/UX-Abschnitt 6: Der unbestimmte Balken folgt dem Board statt der
   * Browser-Voreinstellung - volle Flaeche in `--accent` mit dem bereits etablierten Puls, statt
   * eines wandernden Segments (das waere eine Positionsbewegung und ist im Design-System
   * verboten).
   *
   * Bewusst KEINE Zeichenkettensuche "behandelt die Datei den Zustand?" - das waere eine Zusage
   * ueber die Schreibweise. Genutzt wird der staerkste Mechanismus dieses Vertragstests: der
   * tatsaechliche Tailwind-Lauf. Eine unbekannte Variante ist in Tailwind KEIN Buildfehler und
   * bliebe sonst still wirkungslos.
   */
  it('erzeugt fuer die Zustandsbehandlung des Balkens tatsaechlich Regeln', async () => {
    // `build()` arbeitet inkrementell: einmal aufgenommene Kandidaten bleiben in der Ausgabe.
    // Jeder Kandidat bekommt deshalb einen EIGENEN Lauf, sonst faerbte der erste Treffer alle
    // folgenden gruen.
    async function producesRule(utility: string): Promise<boolean> {
      const compiled = await compile(indexCss, { base: SRC_DIR, onDependency: () => {} })
      const baseline = compiled.build([])
      return compiled.build([utility]) !== baseline
    }

    for (const utility of [
      'indeterminate:bg-accent',
      'indeterminate:animate-pulse',
      'motion-reduce:animate-none',
      'bg-separator',
    ]) {
      expect(await producesRule(utility), utility).toBe(true)
    }
    // Gegenprobe: eine erfundene Variante erzeugt keine Regel - sonst bestuende der Test auch
    // dann, wenn `build()` alles durchwinkte. Genau das ist der Fehlermodus, gegen den diese
    // Pruefung ueberhaupt steht: ein Tippfehler in einer Variante ist in Tailwind kein Buildfehler.
    expect(await producesRule('inderterminate:bg-accent')).toBe(false)
  }, 60_000)

  it('legt die Spur des Balkens nicht mehr auf das unsichtbare --border', () => {
    const progress = sourceFiles.filter((file) => file.label === 'src/components/ui/progress.tsx')
    expect(progress).toHaveLength(1)
    expect(findMatches('bg-border', progress)).toEqual([])
    // Positiv-Gegenprobe: die Datei faerbt die Spur ueberhaupt ein.
    expect(findMatches('bg-separator', progress).length).toBeGreaterThan(0)
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
