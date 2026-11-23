// @vitest-environment node
/*
 * Design-Vertrag "Dark Utility Register" - Teil: Streichliste, Positivprobe und Fokusdarstellung.
 * Rahmen, Begruendung und Selbstausschluss: src/test/designSystemScan.ts .
 */

import { describe, expect, it } from 'vitest'

import {
  escapeForRegExp,
  findOccurrences,
  hexOf,
  indexCss,
  indexHtml,
  rootTokens,
  viteConfig,
} from './test/designSystemScan'

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
  {
    needle: 'fonts.googleapis.com',
    why: 'Schriften sind self-gehostet (Offline-Anspruch, Datenschutz)',
  },
  {
    needle: 'fonts.gstatic.com',
    why: 'Schriften sind self-gehostet (Offline-Anspruch, Datenschutz)',
  },
  { needle: '@fontsource/caprasimo', why: 'Display-Schrift des Organic-Systems' },
  { needle: '@fontsource/figtree', why: 'Fliesstextschrift des Organic-Systems' },
]

/** Die Farbwelt des Organic-Systems, vollstaendig. Findet sich einer dieser Werte noch irgendwo in
 * `frontend/`, ist die Umstellung nicht vollstaendig. */
const ORGANIC_HEX_VALUES = [
  '#f5ead8',
  '#ebddc5',
  '#201e1d',
  '#645c50',
  '#f9f4ed',
  '#eee7db',
  '#dcd3c4',
  '#c0b6a5',
  '#a19786',
  '#82796a',
  '#474238',
  '#2e2b25',
  '#c67139',
  '#8c491a',
  '#fff2eb',
  '#ffe1d0',
  '#ffc6a5',
  '#f6a06b',
  '#d67f48',
  '#b2622d',
  '#643312',
  '#402310',
  '#7a8a5e',
  '#56633f',
  '#f0fae1',
  '#e1eecc',
  '#ccdbb2',
  '#aebf92',
  '#8fa073',
  '#728157',
  '#3d472b',
  '#272e1b',
  '#c9962c',
  '#a8442c',
  '#e0b455',
  '#e08a6f',
  '#f6ddd4',
  '#7d2f1c',
  '#f3b5a0',
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
    expect(indexCss).toMatch(
      /:focus-visible\s*\{[^}]*outline:\s*2px\s+solid\s+var\(--accent\)[^}]*\}/,
    )
    expect(indexCss).toMatch(/:focus-visible\s*\{[^}]*outline-offset:\s*2px[^}]*\}/)
  })
})
