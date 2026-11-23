// @vitest-environment node
/*
 * Design-Vertrag "Dark Utility Register" - Teil: Kontrastmatrix (WCAG) ueber alle :root-Tokens.
 * Rahmen, Begruendung und Selbstausschluss: src/test/designSystemScan.ts .
 */

import { describe, expect, it } from 'vitest'

import { hexOf, rootTokens } from './test/designSystemScan'

/** Tokens ohne Farbwert - jedes andere `:root`-Token MUSS ein 6-stelliger Hexwert sein, damit die
 * Kontrastmatrix es rechnen kann. Ein `var()`- oder `color-mix()`-Wert waere ein Loch mit gruener
 * CI: er liesse sich nicht nachrechnen. */
const NON_COLOR_TOKENS = new Set(['--sans', '--mono'])

// ---------------------------------------------------------------------------------------------
// WCAG-Kontrast (selbst gerechnet, nie aus der ADR abgeschrieben)
// ---------------------------------------------------------------------------------------------

function relativeLuminance(hex: string): number {
  const channels = [1, 3, 5].map((offset) => parseInt(hex.slice(offset, offset + 2), 16) / 255)
  const linear = channels.map((c) =>
    c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4),
  )
  return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]
}

function contrastRatio(a: string, b: string): number {
  const [lighter, darker] = [relativeLuminance(a), relativeLuminance(b)].sort((x, y) => y - x)
  return (lighter + 0.05) / (darker + 0.05)
}

const TEXT_THRESHOLD = 4.5
const GRAPHIC_THRESHOLD = 3

const SURFACES = ['--bg', '--surface', '--elevated', '--overlay'] as const

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
 * praktisch. Zugesichert wird der Korridor gegen die beiden Flaechen, auf denen der KORRIDOR
 * kalibriert ist; auf `--elevated`/`--overlay` sind die Werte nachrichtlich und tragen keine
 * Schwelle.
 *
 * AUSNAHME: GRUPPENTRENNER AUF `--elevated`/`--overlay` (Spec 0347). Innerhalb von Panels und
 * Popovern verwenden Gruppengrenzen `--separator` (nicht `--border`), da die Flaechenstufe selbst
 * nicht zur Trennung ausreicht und die Regel speziell Kanten ZWISCHEN verschiedenen Flaechen
 * adressiert, nicht Unterteilungen INNERHALB einer Flaeche. Fuer diese Verwendung gilt der
 * Korridor 2.0-2.5 nicht - er ist auf die beiden Grundflaechen kalibriert. Tragend ist stattdessen
 * die Zusicherung weiter unten, dass `--separator` auf JEDER der vier Flaechen sichtbarer bleibt
 * als `--border`; sie stuetzt die Ausnahme, statt von ihr beruehrt zu werden.
 */
const SEPARATOR_MIN = 2.0
const SEPARATOR_MAX = 2.5

const separatorRows: ContrastRow[] = [
  { foreground: '--separator', background: '--bg', threshold: SEPARATOR_MIN },
  { foreground: '--separator', background: '--surface', threshold: SEPARATOR_MIN },
]

/**
 * Die beiden Flaechen der Ausnahme. Sie stehen bewusst NICHT in der Matrix - eine Schwellenzeile
 * dort waere die stille Ausweitung des Korridors auf einen Fall, fuer den er nicht gerechnet
 * wurde.
 */
const SEPARATOR_INFORMATIONAL_SURFACES = ['--elevated', '--overlay'] as const

/**
 * Die FUELLUNG der Fortschritts-/Staerkeanzeige gegen ihre SPUR (Spec 0427). Beide Toene stehen
 * hier, nicht nur der neue: die Spur ist in beiden `--separator`, und ohne den Akzent-Eintrag
 * waere der bestehende Ton der ungeprueften Haelfte eines Paars.
 *
 * Grafische Schwelle (3:1): der Balken ist ein Bedienelement-/Grafikumriss, kein Text - er traegt
 * `aria-hidden`, und der eigentliche Text ist die Prozentzahl daneben.
 */
const progressFillRows: ContrastRow[] = [
  { foreground: '--accent', background: '--separator', threshold: GRAPHIC_THRESHOLD },
  { foreground: '--text-h', background: '--separator', threshold: GRAPHIC_THRESHOLD },
]

const inkRows: ContrastRow[] = [
  { foreground: '--accent-fg', background: '--accent', threshold: TEXT_THRESHOLD },
  { foreground: '--status-success-fg', background: '--status-success', threshold: TEXT_THRESHOLD },
  // Die Tinte der zerstoererischen Schaltflaeche (Spec 0044) - derselbe Wert wie --accent-fg und
  // die drei --rating-*-fg, aber ein eigener Name: eine Loeschaktion ist keine Bewertungsstufe.
  { foreground: '--danger-fg', background: '--danger', threshold: TEXT_THRESHOLD },
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
  ...progressFillRows,
  ...separatorRows,
  ...stateSurfaceRows,
  ...ratingRows,
  ...statusPillRows,
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
  /^--danger(-text|-fg)?$/,
  /^--border(-control)?$/,
  /^--separator$/,
  /^--rating-[a-z-]+$/,
  /^--status-(running|success|failed)$/,
  /^--status-.+-(strong|fg)$/,
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

  it('deklariert kein einziges Kategorie-Chip-Token mehr', () => {
    /* Die dreizehn Chip-Farbpaare fallen mit den Kategorien (Spec 0427, PR 3): sie hatten
     * ausschliesslich `CategoryBadge` als Leser. Ein stehengebliebenes Token waere von jeder
     * Kontrastzeile unbemerkt - es stuende in keiner Matrixzeile mehr, weil die Chip-Zeilen mit
     * ihm entfallen sind, und die Formregel (getoent gegen gefuellt, Radius 16 gegen 6,
     * Gegenecke) beschriebe ein Bedienmerkmal, das es nicht mehr gibt. */
    expect([...rootTokens.keys()].filter((name) => name.startsWith('--chip-'))).toEqual([])
  })

  it('deklariert genau 3 Bewertungspaare und 4 Status-Pillen', () => {
    expect([...rootTokens.keys()].filter((name) => /^--rating-.+-fg$/.test(name))).toHaveLength(3)
    expect([...rootTokens.keys()].filter((name) => /^--status-.+-strong$/.test(name))).toHaveLength(
      4,
    )
    expect([...rootTokens.keys()].filter((name) => /^--status-.+-tint$/.test(name))).toHaveLength(4)
  })

  it.each(contrastRows)(
    '$foreground auf $background erreicht $threshold:1',
    ({ foreground, background, threshold }) => {
      const ratio = contrastRatio(hexOf(foreground), hexOf(background))
      expect(
        ratio,
        `${foreground} (${hexOf(foreground)}) auf ${background} (${hexOf(background)}) = ${ratio.toFixed(2)}:1`,
      ).toBeGreaterThanOrEqual(threshold)
    },
  )

  /*
   * NACHRICHTLICH, MIT EINER ECHTEN ZUSICHERUNG (Spec 0347): Die Werte fuer `--elevated`/
   * `--overlay` stehen hier ausgerechnet, damit sie nicht erneut mit den 2.38:1 gegen `--bg`
   * verwechselt werden - genau diese Verwechslung stand am Anfang der Klaerung zur Ausnahme
   * "Gruppentrenner auf --elevated/--overlay".
   *
   * Zugesichert wird dabei nicht der Wert (er traegt bewusst keine Schwelle), sondern dass fuer
   * diese beiden Flaechen KEINE Schwellenzeile in der Matrix steht. Wer eine hinzufuegt, weitet
   * den auf `--bg`/`--surface` kalibrierten Korridor still auf einen Fall aus, fuer den er nicht
   * gerechnet wurde - und muss die Ausnahme dann bewusst anfassen statt sie zu unterlaufen.
   */
  it.each(SEPARATOR_INFORMATIONAL_SURFACES)(
    'rechnet --separator auf %s nachrichtlich, ohne Schwelle',
    (surface) => {
      const separator = contrastRatio(hexOf('--separator'), hexOf(surface))
      const border = contrastRatio(hexOf('--border'), hexOf(surface))

      expect(
        contrastRows.filter(
          (row) => row.foreground === '--separator' && row.background === surface,
        ),
        `--separator auf ${surface} traegt bewusst keine Schwelle ` +
          `(gemessen ${separator.toFixed(2)}:1, --border dort ${border.toFixed(2)}:1)`,
      ).toEqual([])
    },
  )

  it('haelt --separator im Zielkorridor und ueber --border, auf allen vier Flaechen', () => {
    // Die Untergrenze steht bereits als Matrixzeile. Hier zusaetzlich die OBERgrenze (darueber
    // waere es keine dekorative Linie mehr, sondern ein zweiter Grauton), und die eigentliche
    // Aussage der Umstellung: --separator ist auf JEDER Flaeche sichtbarer als --border. Ohne
    // diesen Vergleich bliebe ein Wertewechsel, der die Linie wieder verschwinden laesst,
    // unbemerkt, solange er nur ueber 2.0 landet.
    //
    // "AUF JEDER FLAECHE" IST SEIT SPEC 0347 DIE TRAGENDE ZUSICHERUNG DER AUSNAHME
    // "Gruppentrenner auf --elevated/--overlay": dort gilt der Korridor nicht, aber der Vergleich
    // gegen --border schon - und genau er belegt, dass die Linie in einem Panel ueberhaupt
    // sichtbar ist. Die Obergrenze bleibt bewusst auf die beiden Grundflaechen beschraenkt.
    for (const surface of ['--bg', '--surface'] as const) {
      expect(contrastRatio(hexOf('--separator'), hexOf(surface))).toBeLessThanOrEqual(SEPARATOR_MAX)
    }
    for (const surface of SURFACES) {
      const separator = contrastRatio(hexOf('--separator'), hexOf(surface))
      const border = contrastRatio(hexOf('--border'), hexOf(surface))
      expect(
        separator,
        `${surface}: separator ${separator.toFixed(2)} vs border ${border.toFixed(2)}`,
      ).toBeGreaterThan(border)
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
