// @vitest-environment node
/*
 * Design-Vertrag "Dark Utility Register" - Teil: Selbsttest des Fundstellen-Helfers.
 * Rahmen, Begruendung und Selbstausschluss: src/test/designSystemScan.ts (Spec 0320, Spec 0651).
 */

import { describe, expect, it } from 'vitest'

import {
  allowlistedOccurrences,
  findMatches,
  type ScannedFile,
  stripComments,
} from './test/designSystemScan'

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
    const problems = allowlistedOccurrences(
      needle,
      [],
      [file('src/a.tsx', 'const x = 1', 'className="rounded-full"')],
    )

    expect(problems).toHaveLength(1)
    expect(problems[0]).toContain('src/a.tsx')
    expect(problems[0]).toContain(':2:')
  })

  it('meldet eine Fundstelle mit passendem Eintrag nicht', () => {
    const problems = allowlistedOccurrences(
      needle,
      [{ file: 'src/a.tsx', snippet: 'size-2.5 shrink-0 rounded-full', reason: 'Statuspunkt' }],
      [file('src/a.tsx', '<span className="size-2.5 shrink-0 rounded-full bg-accent" />')],
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
      [
        file(
          'src/a.tsx',
          '<i className="Spinner rounded-full" />',
          '<button className="rounded-full" />',
        ),
      ],
    )

    expect(problems).toHaveLength(1)
    expect(problems[0]).toContain(':2:')
  })

  it('meldet einen Eintrag ohne jede Fundstelle als verwaiste Freigabe', () => {
    const problems = allowlistedOccurrences(
      needle,
      [{ file: 'src/weg.tsx', snippet: 'einst rounded-full', reason: 'laengst entfernt' }],
      [file('src/a.tsx', 'const x = 1')],
    )

    expect(problems).toHaveLength(1)
    expect(problems[0]).toContain('verwaiste Freigabe')
  })

  it('meldet einen Ausschnitt, der nur aus dem Suchbegriff besteht, auch bei passenden Fundstellen', () => {
    const problems = allowlistedOccurrences(
      needle,
      [{ file: 'src/a.tsx', snippet: 'rounded-full', reason: 'zu grob' }],
      [file('src/a.tsx', '<i className="rounded-full" />')],
    )

    expect(problems).toHaveLength(1)
    expect(problems[0]).toContain('nur der Suchbegriff')
  })

  it('meldet eine Fundstelle nicht, die nur in einem Zeilenkommentar steht', () => {
    const problems = allowlistedOccurrences(
      needle,
      [],
      [file('src/a.tsx', '// frueher rounded-full, heute nicht mehr')],
    )

    expect(problems).toEqual([])
  })

  it('meldet eine Fundstelle nach einem mehrzeiligen Blockkommentar mit ihrer tatsaechlichen Zeile', () => {
    const problems = allowlistedOccurrences(
      needle,
      [],
      [
        file(
          'src/a.tsx',
          '/* Zeile 1',
          '   Zeile 2',
          '   Zeile 3 */',
          '<i className="rounded-full" />',
        ),
      ],
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
    expect(findMatches(needle, [file('src/a.tsx', '<i className="rounded-full" />')])).toHaveLength(
      1,
    )
  })
})
