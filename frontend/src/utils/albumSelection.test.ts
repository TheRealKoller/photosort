import { describe, expect, it } from 'vitest'

import type {
  AlbumDecisionOut,
  AlbumParticipantOut,
  AlbumSelectionOut,
  PhotoOut,
  RatingOut,
} from '../api/types'
import {
  applyAlbumDecision,
  participantStance,
  SELECTION_NOTHING_CONTESTED_TEXT,
  SELECTION_VIEW_LABELS,
} from './albumSelection'

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
    ranking: null,
    criterion_scores: [],
    fine_labels: [],
    cloud_vision_status: [],
    final_selection_decision: null,
    in_final_selection: false,
    contested: false,
    ...overrides,
  }
}

function selection(items: PhotoOut[]): AlbumSelectionOut {
  return {
    participants: [
      { user_id: 1, username: 'daniel' },
      { user_id: 2, username: 'nora' },
    ],
    has_proposal: true,
    items,
  }
}

const DANIEL: AlbumParticipantOut = { user_id: 1, username: 'daniel' }
const NORA: AlbumParticipantOut = { user_id: 2, username: 'nora' }

/**
 * DER AUFBAU DER ZUORDNUNGSFAELLE (Zusicherung 23): `ratings[]` steht genau UMGEKEHRT zu
 * `participants`, und nur der ZWEITE Teilnehmer traegt eine Albumentscheidung. Der erste hat eine
 * Zeile, die ausschliesslich das Favoriten-Kennzeichen traegt - seit ADR 0098 ist das
 * Vorhandensein der Zeile keine Aussage mehr ueber den Bewertungsstand.
 *
 * `ratings[0]` und `ratings.some(...)` bestehen jeden natuerlich gebauten Fall und scheitern
 * genau an diesem.
 */
const REVERSED_RATINGS: RatingOut[] = [
  { user_id: 2, username: 'nora', status: 'rejected', favorite: false },
  { user_id: 1, username: 'daniel', status: null, favorite: true },
]

describe('participantStance', () => {
  it('assigns the stance via user_id, never via the position in ratings[]', () => {
    const item = photo({ ratings: REVERSED_RATINGS })

    expect(participantStance(item, DANIEL)).toBe('untouched')
    expect(participantStance(item, NORA)).toBe('struck')
  })

  it('reads Rating.status, not the existence of the row', () => {
    // Die Zeile des ersten Teilnehmers traegt ausschliesslich den Favoriten - das ist keine
    // Albumentscheidung.
    const item = photo({ ratings: REVERSED_RATINGS })

    expect(participantStance(item, DANIEL)).toBe('untouched')
  })

  it('is "taken" for an own album decision', () => {
    const item = photo({
      ratings: [{ user_id: 2, username: 'nora', status: 'album_worthy', favorite: false }],
    })

    expect(participantStance(item, NORA)).toBe('taken')
  })

  it('is "untouched" for a participant without any row at all', () => {
    // Genau der Nutzer, den die Story ausdruecklich als "kein Sonderfall" benennt.
    expect(participantStance(photo(), DANIEL)).toBe('untouched')
    expect(participantStance(photo(), NORA)).toBe('untouched')
  })

  it('never reads a same-named entry of another user id', () => {
    // Der `username` ist fremdbestimmter Text und taugt hier nicht als Schluessel: Die Zuordnung
    // laeuft ueber `user_id`, die vom Server stammt.
    const item = photo({
      ratings: [{ user_id: 99, username: 'daniel', status: 'album_worthy', favorite: false }],
    })

    expect(participantStance(item, DANIEL)).toBe('untouched')
  })
})

describe('applyAlbumDecision', () => {
  const written = (overrides: Partial<AlbumDecisionOut> = {}): AlbumDecisionOut => ({
    photo_id: 1,
    included: true,
    updated_at: '2026-09-13T10:00:00',
    ...overrides,
  })

  it('writes all three fields together from the SERVER answer', () => {
    // Zusicherung 22: `applyAlbumDecision` ist der einzige lokal ausgewertete Teil der Regel -
    // und er ist exakt, weil eine Entscheidung immer ueberschreibt.
    const current = selection([photo({ id: 1, contested: true, in_final_selection: false })])

    const next = applyAlbumDecision(current, written({ included: true }))

    expect(next.items[0].final_selection_decision).toBe(true)
    expect(next.items[0].in_final_selection).toBe(true)
    expect(next.items[0].contested).toBe(false)
  })

  it('takes a photo out of the selection in the same one step', () => {
    const current = selection([
      photo({ id: 1, in_final_selection: true, final_selection_decision: null }),
    ])

    const next = applyAlbumDecision(current, written({ included: false }))

    expect(next.items[0].final_selection_decision).toBe(false)
    expect(next.items[0].in_final_selection).toBe(false)
    expect(next.items[0].contested).toBe(false)
  })

  it('follows the server value, not a locally intended one (Auflage S5)', () => {
    // Ein verlorener Wettlauf antwortet mit dem ANDEREN Wert - genau ihn zeigt die Ansicht danach.
    const current = selection([photo({ id: 1, contested: true })])

    const next = applyAlbumDecision(current, written({ included: false }))

    expect(next.items[0].in_final_selection).toBe(false)
  })

  it('keeps a photo the decision does not concern at its OBJECT REFERENCE', () => {
    // Sonst renderten alle Kacheln nach jedem Handgriff neu, und die Ergebnissicht ruckte.
    const untouched = photo({ id: 2 })
    const current = selection([photo({ id: 1, contested: true }), untouched])

    const next = applyAlbumDecision(current, written({ photo_id: 1 }))

    expect(next.items[1]).toBe(untouched)
  })

  it('keeps the answer ORDER and the participants unchanged', () => {
    // Die Ergebnissicht darf sich nach einer Entscheidung nicht umordnen.
    const current = selection([photo({ id: 5 }), photo({ id: 3 }), photo({ id: 9 })])

    const next = applyAlbumDecision(current, written({ photo_id: 3 }))

    expect(next.items.map((item) => item.id)).toEqual([5, 3, 9])
    expect(next.participants).toEqual(current.participants)
    expect(next.has_proposal).toBe(true)
  })

  it('leaves a selection whose photo it does not find untouched', () => {
    const current = selection([photo({ id: 1 })])

    const next = applyAlbumDecision(current, written({ photo_id: 404 }))

    expect(next.items[0]).toBe(current.items[0])
  })
})

describe('Textbausteine', () => {
  it('names the two views with the words of the switch', () => {
    expect(SELECTION_VIEW_LABELS.contested).toBe('Unterschiede')
    expect(SELECTION_VIEW_LABELS.all).toBe('Endauswahl')
  })

  it('says explicitly that nothing is open instead of leaving the working view empty', () => {
    expect(SELECTION_NOTHING_CONTESTED_TEXT).not.toBe('')
    expect(SELECTION_NOTHING_CONTESTED_TEXT).toContain('Endauswahl')
  })
})
