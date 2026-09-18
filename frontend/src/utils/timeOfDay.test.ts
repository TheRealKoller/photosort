import { describe, expect, it } from 'vitest'

import type { EventOut, EventPlace } from '../api/types'

import {
  dayKeyOf,
  eventPlaceName,
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
    place_name: null,
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

  // Spec 0434: die DRITTE Stufe zwischen Sehenswuerdigkeit und Nummer. Die Zeitspanne bleibt in
  // jedem Fall Teil der Ueberschrift - sie traegt die Unterscheidbarkeit, wenn mehrere Events
  // denselben Namen tragen und kein Viertel vorliegt.
  it('nutzt den aufgeloesten Ortsnamen, wenn keine Sehenswuerdigkeit erkannt wurde', () => {
    const result = formatEventHeading(eventOut({ place_name: 'Garmisch-Partenkirchen' }))

    expect(result.heading).toBe('Garmisch-Partenkirchen (10:30–11:45 Uhr)')
  })

  it('laesst der Sehenswuerdigkeit den Vorrang, wenn beide vorliegen', () => {
    const result = formatEventHeading(
      eventOut({
        place: place({ kind: 'landmark', landmark_name: 'Eiffelturm' }),
        place_name: 'Paris, Gros-Caillou',
      }),
    )

    expect(result.heading).toBe('Eiffelturm (10:30–11:45 Uhr)')
  })

  it('nimmt den Ortsnamen, wenn ein "landmark" ohne Namen danebensteht', () => {
    // Die Rangfolge ist sequenziell: faellt die erste Stufe aus, gewinnt die zweite - nicht
    // sofort die Nummer.
    const result = formatEventHeading(
      eventOut({
        place: place({ kind: 'landmark', landmark_name: null }),
        place_name: 'Split',
      }),
    )

    expect(result.heading).toBe('Split (10:30–11:45 Uhr)')
  })

  it('nutzt den Ortsnamen auch ohne jeden Ortsbezug in "place"', () => {
    const result = formatEventHeading(eventOut({ place: null, place_name: 'Split' }))

    expect(result.heading).toBe('Split (10:30–11:45 Uhr)')
  })

  it('faellt bei einem leeren Ortsnamen auf die Position zurueck', () => {
    expect(formatEventHeading(eventOut({ place_name: '' })).heading).toBe(
      'Position 3 (10:30–11:45 Uhr)',
    )
  })

  it('gibt die zusammengesetzte Form unveraendert weiter', () => {
    // "Ort, Viertel" entsteht AUSSCHLIESSLICH auf dem Server (ADR 0102 Punkt 4) - das Frontend
    // setzt nichts zusammen und zerlegt nichts.
    const result = formatEventHeading(eventOut({ place_name: 'Berlin, Kreuzberg' }))

    expect(result.heading).toBe('Berlin, Kreuzberg (10:30–11:45 Uhr)')
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

/* Spec 0497: Die dreistufige Namenswahl ist aus `formatEventHeading` herausgezogen, weil die
   Bilddetailansicht den Ortsnamen OHNE Zeitspanne zeigt - die Aufnahmezeit steht dort direkt
   darüber. Entstünde die Rangfolge dort ein zweites Mal, liefe sie mit dieser auseinander. */
describe('eventPlaceName', () => {
  it('nimmt die erkannte Sehenswürdigkeit zuerst', () => {
    expect(
      eventPlaceName(
        eventOut({
          place: place({ kind: 'landmark', landmark_name: 'Eiffelturm' }),
          place_name: 'Paris, 7. Arrondissement',
        }),
      ),
    ).toBe('Eiffelturm')
  })

  it('nimmt den aufgelösten Ortsnamen als zweite Stufe', () => {
    expect(eventPlaceName(eventOut({ place_name: 'Berlin, Kreuzberg' }))).toBe('Berlin, Kreuzberg')
  })

  it('liefert ohne jede Ortsangabe null', () => {
    expect(eventPlaceName(eventOut())).toBeNull()
  })

  /* Eine Koordinate erscheint AUSDRÜCKLICH NICHT als Name - sie bleibt in `place`. */
  it('zeigt eine Koordinate nicht als Namen', () => {
    expect(eventPlaceName(eventOut({ place: place({ kind: 'coordinate' }) }))).toBeNull()
  })

  /* Fällt eine Stufe aus, gewinnt die NÄCHSTE - nicht sofort `null`. Leerer String und `null`
     gelten dabei gleich: `""` als Ortsname wäre eine Lücke, kein Name. */
  it.each([
    { name: 'landmark null', landmark: null, placeName: 'Berlin', erwartet: 'Berlin' },
    { name: 'landmark leer', landmark: '', placeName: 'Berlin', erwartet: 'Berlin' },
    { name: 'place_name leer', landmark: null, placeName: '', erwartet: null },
  ])('fällt bei $name auf die nächste Stufe', ({ landmark, placeName, erwartet }) => {
    expect(
      eventPlaceName(
        eventOut({
          place: place({ kind: 'landmark', landmark_name: landmark }),
          place_name: placeName,
        }),
      ),
    ).toBe(erwartet)
  })

  /* REINE FUNKTION ÜBER DER EVENT-ZEILE (S2): Sie setzt nichts zusammen und interpretiert nichts -
     die Form "Ort, Viertel" kommt fertig vom Server. Der XSS-Nachweis gehört an die RENDERSTELLE,
     nicht hierher; dass die Funktion nichts interpretiert, sagt nichts darüber, was das Markup
     daraus macht. Hier steht deshalb nur: der Text kommt unverändert zurück. */
  it('gibt einen HTML-artigen Namen unverändert zurück, ohne ihn zusammenzusetzen', () => {
    const payload = '<img src=x onerror="window.__pwned = true">'

    expect(
      eventPlaceName(eventOut({ place: place({ kind: 'landmark', landmark_name: payload }) })),
    ).toBe(payload)
  })

  /* Die Rangfolge ist DIESELBE, die die Überschrift benutzt - beide lesen diese eine Funktion. */
  it('trägt dieselbe Namenswahl wie die Ereignis-Überschrift', () => {
    const event = eventOut({ place_name: 'Berlin, Kreuzberg' })

    expect(formatEventHeading(event).heading).toBe(`${eventPlaceName(event)} (10:30–11:45 Uhr)`)
  })
})
