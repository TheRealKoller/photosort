import { describe, expect, it } from 'vitest'

import type { EventOut, EventPlace } from '../api/types'

import {
  dayKeyOf,
  formatDayHeading,
  formatEventHeading,
  formatTimeRange,
  hourOf,
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

describe('formatTimeRange', () => {
  it('formats a range across two different minutes', () => {
    expect(formatTimeRange('2026-07-20T12:00:00', '2026-07-20T14:00:00')).toBe('12:00–14:00 Uhr')
  })

  it('collapses to a single timestamp when both share the same minute', () => {
    expect(formatTimeRange('2026-07-20T14:32:10', '2026-07-20T14:32:45')).toBe('14:32 Uhr')
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

// Spec 0425, ADR 0087 Entscheidung 6: die Ueberschrift entsteht aus EINEM Event, nicht mehr aus
// aggregierten Foto-Metadaten. Zwei Formen, sonst nichts: der erkannte Name oder "Position N" -
// eine Koordinate erscheint NICHT mehr als Name, und die Tageszeit-Kategorien entfallen.

function eventOut(overrides: Partial<EventOut> = {}): EventOut {
  return {
    id: 7,
    position: 3,
    started_at: '2026-07-20T10:30:00',
    ended_at: '2026-07-20T11:45:00',
    place: null,
    ...overrides,
  }
}

function place(overrides: Partial<EventPlace> = {}): EventPlace {
  return { kind: 'coordinate', landmark_name: null, lat: 48.86, lon: 2.29, ...overrides }
}

describe('formatEventHeading', () => {
  it('nutzt den erkannten Sehenswuerdigkeit-Namen mit der Zeitspanne', () => {
    const result = formatEventHeading(
      eventOut({ place: place({ kind: 'landmark', landmark_name: 'Eiffelturm' }) }),
    )

    expect(result.heading).toBe('Eiffelturm (10:30–11:45 Uhr)')
  })

  it('faellt ohne Ortsbezug auf die Position zurueck', () => {
    expect(formatEventHeading(eventOut()).heading).toBe('Position 3 (10:30–11:45 Uhr)')
  })

  it('zeigt eine Koordinate NICHT als Namen', () => {
    // Die Koordinate bleibt in der Antwort (kuenftiges Reverse-Geocoding), erscheint aber nicht
    // mehr in der Ueberschrift.
    const result = formatEventHeading(eventOut({ place: place({ lat: 48.86, lon: 2.29 }) }))

    expect(result.heading).toBe('Position 3 (10:30–11:45 Uhr)')
    expect(result.heading).not.toContain('48.86')
  })

  it('zeigt "mehrere Orte" nicht als Namen', () => {
    const result = formatEventHeading(
      eventOut({ place: place({ kind: 'multiple', lat: null, lon: null }) }),
    )

    expect(result.heading).toBe('Position 3 (10:30–11:45 Uhr)')
  })

  it('verwirft einen "landmark" ohne Namen, statt "null" zu schreiben', () => {
    const result = formatEventHeading(
      eventOut({ place: place({ kind: 'landmark', landmark_name: null }) }),
    )

    expect(result.heading).toBe('Position 3 (10:30–11:45 Uhr)')
  })

  it('kollabiert die Zeitspanne eines Events innerhalb einer Minute', () => {
    const result = formatEventHeading(
      eventOut({ started_at: '2026-07-20T10:30:10', ended_at: '2026-07-20T10:30:50' }),
    )

    expect(result.heading).toBe('Position 3 (10:30 Uhr)')
  })

  it('liefert den Kalendertag des EVENT-ANFANGS', () => {
    const result = formatEventHeading(
      eventOut({ started_at: '2026-07-20T23:50:00', ended_at: '2026-07-20T23:59:00' }),
    )

    expect(result.dayKey).toBe('2026-07-20')
  })

  it('liest die Zeitspanne per String-Slicing, nicht ueber Date-Getter', () => {
    // `started_at`/`ended_at` sind zonenlos. Ein `Date`-Getter haenge an der Zeitzone des
    // ausfuehrenden Browsers/Testrunners; ein `Z`-Suffix darf das Ergebnis nicht verschieben.
    const result = formatEventHeading(
      eventOut({ started_at: '2026-07-20T00:05:00', ended_at: '2026-07-20T00:55:00' }),
    )

    expect(result.heading).toBe('Position 3 (00:05–00:55 Uhr)')
  })

  it('ist eine reine Funktion ueber EINEM Event - die Fotoanzahl geht nicht ein', () => {
    const single = formatEventHeading(eventOut())
    const again = formatEventHeading(eventOut())

    expect(single).toEqual(again)
  })

  it('gibt einen HTML-artigen Sehenswuerdigkeit-Namen unveraendert als Text zurueck', () => {
    // `landmark_name` ist der Rohausgabe-Text eines externen Modells. Die Funktion baut einen
    // einfachen String zusammen und interpretiert nichts - das Escaping leistet React an der
    // Rendering-Stelle (siehe CurateCategoriesPage.test.tsx).
    const result = formatEventHeading(
      eventOut({
        place: place({
          kind: 'landmark',
          landmark_name: '<img src=x onerror="window.__pwned = true">',
        }),
      }),
    )

    expect(result.heading).toBe('<img src=x onerror="window.__pwned = true"> (10:30–11:45 Uhr)')
  })
})
