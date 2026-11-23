// @vitest-environment node
/*
 * Design-Vertrag "Dark Utility Register" - Teil: Formsprache (Radien, Raster).
 * Rahmen, Begruendung und Selbstausschluss: src/test/designSystemScan.ts (Spec 0320, Spec 0651).
 */

import { describe, expect, it } from 'vitest'

import {
  allowlistedOccurrences,
  type AllowlistEntry,
  findMatches,
  indexCss,
  stripComments,
  tsxFiles,
} from './test/designSystemScan'

describe('Design-Vertrag: Formsprache und Skalen', () => {
  /*
   * Das Board kennt keine vollrunden Pillen mehr. Diese Liste ist abschliessend: jede weitere
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
      file: 'src/components/PhotoGridTile.tsx',
      snippet: "'block size-3 rounded-full border-2'",
      reason:
        'der PUNKT der Rasterkachel - eines der genau zwei Zeichen der Fotouebersicht. Die ' +
        'Kreisform traegt hier Bedeutung und nicht Geometrie: Unter Graustufen sind Favorit und ' +
        'Album-wuerdig als Flaechen nicht unterscheidbar, die Unterscheidung laeuft ueber die ' +
        'SILHOUETTE (Stern gegen Kreis). Die Fuellung unterscheidet zusaetzlich die eigene ' +
        'Entscheidung vom offenen Vorschlag',
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
