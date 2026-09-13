import { describe, expect, it } from 'vitest'

import type { EventOut, PhotoOut, RankingOut, RatingStatus } from '../api/types'
import {
  draftSizeText,
  formatDraftPhotoCount,
  groupDraftByDay,
  isInAlbum,
  isTakenWithoutProposal,
} from './albumDraft'

function ranking(overrides: Partial<RankingOut> = {}): RankingOut {
  return {
    event_id: 1,
    rank_score: 0.8,
    rank_position: 1,
    proposed: true,
    partition_size: 3,
    curation_position: 1,
    ...overrides,
  }
}

function event(overrides: Partial<EventOut> = {}): EventOut {
  return {
    id: 1,
    position: 1,
    started_at: '2026-07-20T10:00:00',
    ended_at: '2026-07-20T11:00:00',
    place: null,
    ...overrides,
  }
}

function photo(overrides: Partial<PhotoOut> = {}): PhotoOut {
  return {
    id: 1,
    relative_path: 'a.jpg',
    taken_at: '2026-07-20T10:00:00',
    taken_at_original: '2026-07-20T10:00:00',
    time_offset_minutes: 0,
    camera: null,
    ratings: [],
    suggestion: null,
    ranking: ranking(),
    criterion_scores: [],
    fine_labels: [],
    cloud_vision_status: [],
    event: event(),
    ...overrides,
  }
}

describe('isInAlbum', () => {
  const cases: { ownStatus: RatingStatus | null; expected: boolean }[] = [
    { ownStatus: null, expected: true },
    { ownStatus: 'album_worthy', expected: true },
    { ownStatus: 'rejected', expected: false },
  ]

  it.each(cases)('is $expected for the own status $ownStatus', ({ ownStatus, expected }) => {
    expect(isInAlbum(ownStatus)).toBe(expected)
  })
})

describe('isTakenWithoutProposal', () => {
  it('holds for a photo the run dropped from the candidate pool (ranking: null)', () => {
    expect(isTakenWithoutProposal(photo({ ranking: null }), 'album_worthy')).toBe(true)
  })

  it('holds for a candidate the run did not propose (ranking.proposed: false)', () => {
    expect(
      isTakenWithoutProposal(photo({ ranking: ranking({ proposed: false }) }), 'album_worthy'),
    ).toBe(true)
  })

  it('answers identically for both data forms - one display state, two data shapes', () => {
    // Zusicherung 23: Die beiden Formen bedeuten dasselbe. Eine Pruefung, die nur eine von beiden
    // kennt, laesst die andere unmarkiert durch, und dieselbe Lage saehe je nach Datenform anders
    // aus.
    const dropped = isTakenWithoutProposal(photo({ ranking: null }), 'album_worthy')
    const notChosen = isTakenWithoutProposal(
      photo({ ranking: ranking({ proposed: false }) }),
      'album_worthy',
    )

    expect(dropped).toBe(notChosen)
  })

  it('does not hold for a photo the run proposes', () => {
    expect(isTakenWithoutProposal(photo(), 'album_worthy')).toBe(false)
  })

  it('does not hold without an own decision - then the proposal carries the photo', () => {
    expect(isTakenWithoutProposal(photo({ ranking: null }), null)).toBe(false)
  })

  it('does not hold for a struck photo', () => {
    expect(isTakenWithoutProposal(photo({ ranking: null }), 'rejected')).toBe(false)
  })
})

describe('groupDraftByDay', () => {
  const morning = event({ id: 10, position: 1, started_at: '2026-07-20T09:00:00' })
  const afternoon = event({ id: 11, position: 2, started_at: '2026-07-20T15:00:00' })
  const nextDay = event({ id: 12, position: 3, started_at: '2026-07-21T09:00:00' })

  it('keeps the answer order of the server instead of sorting again', () => {
    // Die Reihenfolge ist eine Zusage des Servers (events.position, taken_at, photo_id). Eine
    // zweite Sortierung im Frontend waere eine zweite Wahrheit - der Aufbau steht deshalb
    // absichtlich quer zur `photo.id`-Folge.
    const items = [
      photo({ id: 30, event: morning }),
      photo({ id: 10, event: morning }),
      photo({ id: 20, event: afternoon }),
      photo({ id: 5, event: nextDay }),
    ]

    const days = groupDraftByDay(items)

    expect(days.map((day) => day.dayKey)).toEqual(['2026-07-20', '2026-07-21'])
    expect(days[0].events.map((group) => group.eventId)).toEqual([10, 11])
    expect(days[0].events[0].photos.map((item) => item.id)).toEqual([30, 10])
    expect(days[1].events[0].photos.map((item) => item.id)).toEqual([5])
  })

  it('gives each event group the heading of its event', () => {
    const days = groupDraftByDay([photo({ id: 1, event: morning })])

    expect(days[0].events[0].heading).toContain('Position 1')
  })

  it('skips a photo without an event instead of inventing a group', () => {
    // Der Server liefert das Event auf jedem Foto des Entwurfs - die Ausfallrichtung ist
    // "nicht zeigen", nie eine erfundene Gruppe.
    const days = groupDraftByDay([photo({ id: 1, event: null }), photo({ id: 2, event: morning })])

    expect(days).toHaveLength(1)
    expect(days[0].events[0].photos.map((item) => item.id)).toEqual([2])
  })

  it('returns nothing for an empty draft', () => {
    expect(groupDraftByDay([])).toEqual([])
  })
})

describe('draftSizeText', () => {
  it('names the actual count and the target next to each other', () => {
    expect(draftSizeText(142, 130)).toBe('142 von etwa 130 Bildern')
  })

  it('says the same thing in both directions of deviation', () => {
    // Eine Abweichung nach oben wie nach unten ist ein neutraler Hinweis - derselbe Satzbau, kein
    // zweiter Ton, kein Wort wie "zu wenig" oder "zu viel".
    expect(draftSizeText(100, 130)).toBe('100 von etwa 130 Bildern')
    expect(draftSizeText(130, 130)).toBe('130 von etwa 130 Bildern')
  })

  it('carries no digit beyond the two counts', () => {
    expect(draftSizeText(7, 9).match(/\d+/g)).toEqual(['7', '9'])
  })
})

describe('formatDraftPhotoCount', () => {
  it.each([
    { count: 1, expected: '1 Bild' },
    { count: 2, expected: '2 Bilder' },
    { count: 0, expected: '0 Bilder' },
  ])('formats $count as "$expected"', ({ count, expected }) => {
    expect(formatDraftPhotoCount(count)).toBe(expected)
  })
})
