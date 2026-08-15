import { describe, expect, it } from 'vitest'

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
