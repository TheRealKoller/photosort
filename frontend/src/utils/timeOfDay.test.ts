import { describe, expect, it } from 'vitest'

import type { ClusterPlace } from '../api/types'

import {
  dayKeyOf,
  formatClusterHeading,
  formatDayHeading,
  formatTimeRange,
  hourOf,
  timeOfDayBucketLabel,
} from './timeOfDay'

describe('dayKeyOf', () => {
  it('extracts the calendar day from a naive ISO datetime', () => {
    expect(dayKeyOf('2026-07-20T10:00:00')).toBe('2026-07-20')
  })
})

describe('hourOf', () => {
  it('extracts the hour from a naive ISO datetime', () => {
    expect(hourOf('2026-07-20T14:32:00')).toBe(14)
  })

  it('extracts a single-digit hour without losing the leading zero', () => {
    expect(hourOf('2026-07-20T05:00:00')).toBe(5)
  })
})

describe('timeOfDayBucketLabel', () => {
  it.each([
    [4, 'Nachts'],
    [0, 'Nachts'],
    [5, 'Morgens'],
    [7, 'Morgens'],
    [8, 'Vormittags'],
    [10, 'Vormittags'],
    [11, 'Mittags'],
    [12, 'Mittags'],
    [13, 'Nachmittags'],
    [17, 'Nachmittags'],
    [18, 'Abends'],
    [21, 'Abends'],
    [22, 'Nachts'],
    [23, 'Nachts'],
  ])('maps hour %i to bucket %s', (hour, expected) => {
    expect(timeOfDayBucketLabel(hour)).toBe(expected)
  })
})

describe('formatTimeRange', () => {
  it('formats a range across two different minutes', () => {
    expect(formatTimeRange('2026-07-20T12:00:00', '2026-07-20T14:00:00')).toBe('12:00–14:00 Uhr')
  })

  it('collapses to a single timestamp when both share the same minute', () => {
    expect(formatTimeRange('2026-07-20T14:32:10', '2026-07-20T14:32:45')).toBe('14:32 Uhr')
  })
})

describe('formatClusterHeading', () => {
  it('throws a clear error instead of accessing photos[0] on an empty array', () => {
    // Copilot-Review-Fund (PR #91): ohne expliziten Guard waere der Fehler beim Aufruf mit einem
    // leeren Array ein unklares "cannot read properties of undefined" statt einer nachvollziehbaren
    // Meldung, die auf den verletzten Vertrag (nicht-leeres Array) hinweist.
    expect(() => formatClusterHeading([])).toThrow(
      'formatClusterHeading() erwartet ein nicht-leeres Array',
    )
  })

  it('derives day and bucket from the single photo of a one-photo cluster', () => {
    const result = formatClusterHeading([{ taken_at: '2026-07-20T14:32:00' }])
    expect(result.dayKey).toBe('2026-07-20')
    expect(result.heading).toBe('Nachmittags (14:32 Uhr)')
    expect(result.earliestIso).toBe('2026-07-20T14:32:00')
  })

  it('derives the exact min/max range across multiple photos of the same cluster', () => {
    const result = formatClusterHeading([
      { taken_at: '2026-07-20T13:10:00' },
      { taken_at: '2026-07-20T12:00:00' },
      { taken_at: '2026-07-20T14:00:00' },
    ])
    expect(result.dayKey).toBe('2026-07-20')
    // 12:00 Uhr (fruehestes Foto) faellt in den Mittags-Bucket [11:00, 13:00), auch wenn die
    // Spanne selbst den Nachmittags-Bucket ueberschreitet (Akzeptanzkriterium 6).
    expect(result.heading).toBe('Mittags (12:00–14:00 Uhr)')
    // earliestIso ist der rohe (nicht formatierte) Zeitstempel des fruehesten Fotos - genutzt fuer
    // die chronologische Cluster-Sortierung in CurateCategoriesPage.tsx (Akzeptanzkriterium 2).
    expect(result.earliestIso).toBe('2026-07-20T12:00:00')
  })

  it('resolves day and bucket from the earliest photo for a midnight-spanning cluster', () => {
    const result = formatClusterHeading([
      { taken_at: '2026-07-21T00:10:00' },
      { taken_at: '2026-07-20T23:50:00' },
    ])
    expect(result.dayKey).toBe('2026-07-20')
    expect(result.heading).toBe('Nachts (23:50–00:10 Uhr)')
    expect(result.earliestIso).toBe('2026-07-20T23:50:00')
  })
})

describe('formatDayHeading', () => {
  it('formats a known Monday with the German weekday name', () => {
    // 20.07.2026 ist ein Montag.
    expect(formatDayHeading('2026-07-20')).toBe('Montag 20.07.2026')
  })

  it('pads single-digit day and month', () => {
    // 01.02.2026 ist ein Sonntag.
    expect(formatDayHeading('2026-02-01')).toBe('Sonntag 01.02.2026')
  })
})

// specs/features/0051-gps-landmark-cluster-bildung.md, ADR 0072 Entscheidung 1: der Ortsteil der
// Cluster-Ueberschrift kommt FERTIG AUFGELOEST als `PhotoOut.cluster_place` vom Server. Das
// Frontend bildet die Rangfolge (Sehenswuerdigkeit -> Koordinate -> mehrere Orte) NICHT nach, es
// verzweigt nur ueber `kind` und formatiert. Tag, Tageszeit und Zeitspanne entstehen unveraendert
// aus den SICHTBAREN Fotos (Spec 0039, Frueheste-Foto-Regel).

function clusterPlace(overrides: Partial<ClusterPlace> = {}): ClusterPlace {
  return { kind: 'coordinate', landmark_name: null, lat: 48.86, lon: 2.29, ...overrides }
}

describe('formatClusterHeading mit Ortsangabe', () => {
  it('stellt den Sehenswuerdigkeit-Namen vor die Tageszeit', () => {
    const result = formatClusterHeading([
      {
        taken_at: '2026-07-20T13:00:00',
        cluster_place: clusterPlace({ kind: 'landmark', landmark_name: 'Eiffelturm' }),
      },
      { taken_at: '2026-07-20T14:00:00', cluster_place: null },
    ])

    expect(result.heading).toBe('Eiffelturm · Nachmittags (13:00–14:00 Uhr)')
  })

  it('formatiert eine Koordinate mit genau zwei Nachkommastellen', () => {
    const result = formatClusterHeading([
      {
        taken_at: '2026-07-20T13:00:00',
        cluster_place: clusterPlace({ lat: 48.86, lon: 2.29 }),
      },
    ])

    expect(result.heading).toBe('48.86, 2.29 · Nachmittags (13:00 Uhr)')
  })

  it('haengt fehlende Nachkommastellen an, statt sie wegzulassen', () => {
    // `48.9` darf nicht als `48.9` erscheinen - die Anzeige soll ueber alle Cluster hinweg
    // dieselbe Breite haben.
    const result = formatClusterHeading([
      { taken_at: '2026-07-20T13:00:00', cluster_place: clusterPlace({ lat: 48.9, lon: 2 }) },
    ])

    expect(result.heading).toBe('48.90, 2.00 · Nachmittags (13:00 Uhr)')
  })

  it('zeigt ein negatives Vorzeichen, wo es hingehoert', () => {
    const result = formatClusterHeading([
      {
        taken_at: '2026-07-20T13:00:00',
        cluster_place: clusterPlace({ lat: -33.86, lon: 151.22 }),
      },
    ])

    expect(result.heading).toBe('-33.86, 151.22 · Nachmittags (13:00 Uhr)')
  })

  it('macht aus -0 niemals "-0.00"', () => {
    // Die Rundungskonvention selbst wird im Backend geprueft, wo sie entsteht - hier geht es
    // allein um die Formatierung: `-0.00` waere eine Himmelsrichtung, die es nicht gibt.
    const result = formatClusterHeading([
      { taken_at: '2026-07-20T13:00:00', cluster_place: clusterPlace({ lat: -0, lon: -0 }) },
    ])

    expect(result.heading).toBe('0.00, 0.00 · Nachmittags (13:00 Uhr)')
  })

  it('beschriftet mehrere Orte, ohne eine stellvertretende Koordinate zu zeigen', () => {
    const result = formatClusterHeading([
      {
        taken_at: '2026-07-20T13:00:00',
        // `kind="multiple"` kann strukturell keine Koordinate mitfuehren - selbst wenn ein
        // kuenftiger Server eine mitschickte, darf sie nicht erscheinen.
        cluster_place: clusterPlace({ kind: 'multiple', lat: 48.86, lon: 2.29 }),
      },
    ])

    expect(result.heading).toBe('Mehrere Orte · Nachmittags (13:00 Uhr)')
  })

  it('laesst die Ueberschrift ohne Ortsinformation zeichengleich wie bisher', () => {
    const withPlace = formatClusterHeading([
      { taken_at: '2026-07-20T13:00:00', cluster_place: null },
    ])
    const legacy = formatClusterHeading([{ taken_at: '2026-07-20T13:00:00' }])

    expect(withPlace.heading).toBe('Nachmittags (13:00 Uhr)')
    expect(legacy.heading).toBe('Nachmittags (13:00 Uhr)')
  })

  it('uebernimmt den Ortsteil vom ersten Foto mit gesetztem Wert', () => {
    // Der Server sichert zu, dass `cluster_place` auf JEDEM Foto eines Clusters identisch ist -
    // deshalb genuegt ein beliebiges. Defensiv wird der erste gesetzte Wert genommen, damit ein
    // fuehrendes `null` (etwa aus einem Altbestand) die Angabe nicht verschluckt.
    const result = formatClusterHeading([
      { taken_at: '2026-07-20T13:00:00', cluster_place: null },
      {
        taken_at: '2026-07-20T13:30:00',
        cluster_place: clusterPlace({ kind: 'landmark', landmark_name: 'Zugspitze' }),
      },
    ])

    expect(result.heading).toBe('Zugspitze · Nachmittags (13:00–13:30 Uhr)')
  })

  it('bleibt bei uneinheitlichen Werten im Eingabearray deterministisch', () => {
    const first = formatClusterHeading([
      {
        taken_at: '2026-07-20T13:00:00',
        cluster_place: clusterPlace({ kind: 'landmark', landmark_name: 'Zugspitze' }),
      },
      {
        taken_at: '2026-07-20T13:30:00',
        cluster_place: clusterPlace({ kind: 'landmark', landmark_name: 'Eiffelturm' }),
      },
    ])
    const again = formatClusterHeading([
      {
        taken_at: '2026-07-20T13:00:00',
        cluster_place: clusterPlace({ kind: 'landmark', landmark_name: 'Zugspitze' }),
      },
      {
        taken_at: '2026-07-20T13:30:00',
        cluster_place: clusterPlace({ kind: 'landmark', landmark_name: 'Eiffelturm' }),
      },
    ])

    expect(first.heading).toBe(again.heading)
    expect(first.heading).toContain('Zugspitze')
  })

  it('verwirft einen "landmark" ohne Namen, statt "null" zu schreiben', () => {
    const result = formatClusterHeading([
      {
        taken_at: '2026-07-20T13:00:00',
        cluster_place: clusterPlace({ kind: 'landmark', landmark_name: null }),
      },
    ])

    expect(result.heading).toBe('Nachmittags (13:00 Uhr)')
  })

  it('verwirft eine "coordinate" ohne Zahlen, statt "null, null" zu schreiben', () => {
    const result = formatClusterHeading([
      {
        taken_at: '2026-07-20T13:00:00',
        cluster_place: clusterPlace({ kind: 'coordinate', lat: null, lon: null }),
      },
    ])

    expect(result.heading).toBe('Nachmittags (13:00 Uhr)')
  })

  it('trennt Ort und Tageszeit mit einem Mittelpunkt, nicht mit einem Komma', () => {
    // Ein Komma waere mit dem Dezimaltrenner der Koordinate zu verwechseln.
    const result = formatClusterHeading([
      { taken_at: '2026-07-20T13:00:00', cluster_place: clusterPlace() },
    ])

    expect(result.heading).toContain(' · ')
    expect(result.heading.indexOf('48.86')).toBeLessThan(result.heading.indexOf('Nachmittags'))
  })

  it('liefert fuer dieselbe Cluster-Fixture mit 3 und mit 10 Fotos dieselbe Ueberschrift', () => {
    // TEILMENGEN-INVARIANZ (Pflichtfall der Teststrategie): der Ortsteil ist eine Aussage ueber
    // den CLUSTER, nicht ueber die sichtbaren Fotos. Frueheste und spaeteste Aufnahme sind in
    // beiden Mengen enthalten - Tageszeit und Zeitspanne bleiben damit unveraendert, und was
    // uebrig bleibt, ist genau die Frage, ob die Zahl der Fotos den Ortsteil beeinflusst.
    const place = clusterPlace({ kind: 'landmark', landmark_name: 'Eiffelturm' })
    const all = Array.from({ length: 10 }, (_, index) => ({
      taken_at: `2026-07-20T13:${String(index).padStart(2, '0')}:00`,
      cluster_place: place,
    }))
    const three = [all[0], all[4], all[9]]

    expect(formatClusterHeading(three).heading).toBe(formatClusterHeading(all).heading)
  })

  it('laesst dayKey und earliestIso von der Ortsangabe unberuehrt', () => {
    const result = formatClusterHeading([
      {
        taken_at: '2026-07-20T13:00:00',
        cluster_place: clusterPlace({ kind: 'landmark', landmark_name: 'Eiffelturm' }),
      },
    ])

    expect(result.dayKey).toBe('2026-07-20')
    expect(result.earliestIso).toBe('2026-07-20T13:00:00')
  })

  it('gibt einen HTML-artigen Sehenswuerdigkeit-Namen unveraendert als Text zurueck', () => {
    // `landmark_name` ist der Rohausgabe-Text eines externen Modells. `formatClusterHeading()`
    // baut einen einfachen String zusammen und interpretiert nichts - das Escaping selbst leistet
    // React an der Rendering-Stelle (siehe CurateCategoriesPage.test.tsx).
    const result = formatClusterHeading([
      {
        taken_at: '2026-07-20T13:00:00',
        cluster_place: clusterPlace({
          kind: 'landmark',
          landmark_name: '<img src=x onerror="window.__pwned = true">',
        }),
      },
    ])

    expect(result.heading).toBe(
      '<img src=x onerror="window.__pwned = true"> · Nachmittags (13:00 Uhr)',
    )
  })
})
