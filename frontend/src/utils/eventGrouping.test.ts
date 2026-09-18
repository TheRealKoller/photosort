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
    place_name: null,
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
    final_selection_decision: null,
    in_final_selection: false,
    contested: false,
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

  it('carries a resolved place name into the group heading', () => {
    // Die Gruppierung bildet die Ueberschrift NICHT selbst, sie geht durch `formatEventHeading` -
    // eine zweite Rangfolge hier waere eine zweite Wahrheit (Spec 0434).
    const days = groupPhotosByDay([
      photo({ id: 1, event: event({ ...morning, place_name: 'Berlin, Kreuzberg' }) }),
    ])

    expect(days[0].events[0].heading).toContain('Berlin, Kreuzberg')
    expect(days[0].events[0].heading).not.toContain('Position')
  })

  it('skips a photo without an event instead of inventing a group', () => {
    // Der Server liefert das Event auf jedem Foto des Entwurfs - die Ausfallrichtung ist
    // "nicht zeigen", nie eine erfundene Gruppe.
    const days = groupPhotosByDay([photo({ id: 1, event: null }), photo({ id: 2, event: morning })])

    expect(days).toHaveLength(1)
    expect(days[0].events[0].photos.map((item) => item.id)).toEqual([2])
  })

  it('keeps an event that runs across midnight in the section of its starting day', () => {
    // Seit Spec 0506 kann ein Event ueber Mitternacht laufen. `dayKey` kommt aus `started_at` -
    // ein Event, das sich auf zwei Abschnitte verteilte, zerrisse den Anlass in der Ansicht genau
    // dort wieder, wo die Gliederung ihn bewusst zusammenhaelt.
    const overnight = event({
      id: 20,
      position: 1,
      started_at: '2026-07-20T23:40:00',
      ended_at: '2026-07-21T01:15:00',
    })

    const days = groupPhotosByDay([
      photo({ id: 1, taken_at: '2026-07-20T23:40:00', event: overnight }),
      photo({ id: 2, taken_at: '2026-07-21T01:15:00', event: overnight }),
    ])

    expect(days.map((day) => day.dayKey)).toEqual(['2026-07-20'])
    expect(days[0].events).toHaveLength(1)
    expect(days[0].events[0].photos.map((item) => item.id)).toEqual([1, 2])
    expect(days[0].events[0].heading).toContain('23:40–01:15 Uhr')
  })

  it('returns nothing for an empty draft', () => {
    expect(groupPhotosByDay([])).toEqual([])
  })
})
