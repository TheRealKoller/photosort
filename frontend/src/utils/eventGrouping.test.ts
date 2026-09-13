import { describe, expect, it } from 'vitest'

import type { EventOut, PhotoOut, RankingOut } from '../api/types'
import { groupPhotosByDay } from './eventGrouping'

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

describe('groupPhotosByDay', () => {
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

    const days = groupPhotosByDay(items)

    expect(days.map((day) => day.dayKey)).toEqual(['2026-07-20', '2026-07-21'])
    expect(days[0].events.map((group) => group.eventId)).toEqual([10, 11])
    expect(days[0].events[0].photos.map((item) => item.id)).toEqual([30, 10])
    expect(days[1].events[0].photos.map((item) => item.id)).toEqual([5])
  })

  it('gives each event group the heading of its event', () => {
    const days = groupPhotosByDay([photo({ id: 1, event: morning })])

    expect(days[0].events[0].heading).toContain('Position 1')
  })

  it('skips a photo without an event instead of inventing a group', () => {
    // Der Server liefert das Event auf jedem Foto des Entwurfs - die Ausfallrichtung ist
    // "nicht zeigen", nie eine erfundene Gruppe.
    const days = groupPhotosByDay([photo({ id: 1, event: null }), photo({ id: 2, event: morning })])

    expect(days).toHaveLength(1)
    expect(days[0].events[0].photos.map((item) => item.id)).toEqual([2])
  })

  it('returns nothing for an empty draft', () => {
    expect(groupPhotosByDay([])).toEqual([])
  })
})
