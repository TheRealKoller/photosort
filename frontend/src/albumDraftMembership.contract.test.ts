// @vitest-environment node
/*
 * DIESELBE Falltabelle wie `backend/tests/test_api_photos.py::TestTheAlbumDraft`: Der Server ist
 * die Autorität, `draftMembership` bildet sein Prädikat nach. Laufen beide auseinander, zeigte die
 * Ansicht nach einem Handgriff etwas anderes als nach dem Neuladen. Node-Umgebung, weil die Tabelle
 * aus dem Backend-Baum gelesen wird (TS-Projekt `tsconfig.contract.json`).
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import type { PhotoOut, RatingOut, RatingStatus } from './api/types'
import { draftMembership } from './utils/albumDraft'

interface MembershipRow {
  ranking: 'none' | 'not_proposed' | 'proposed'
  own: RatingStatus | null
  other: RatingStatus
  membership: 'out' | 'album' | 'struck'
}

// Eingecheckte Testdaten des eigenen Repositoriums - kein Fremdinhalt, der zu validieren waere.
const MEMBERSHIP_FILE: { rows: MembershipRow[] } = JSON.parse(
  readFileSync(
    fileURLToPath(new URL('../../backend/tests/data/album_draft_membership.json', import.meta.url)),
    'utf-8',
  ),
)
const MEMBERSHIP_TABLE = MEMBERSHIP_FILE.rows

function rated(own: RatingStatus | null, other: RatingStatus): RatingOut[] {
  return [
    ...(own === null ? [] : [{ user_id: 1, username: 'daniel', status: own, favorite: false }]),
    { user_id: 2, username: 'anna', status: other, favorite: false },
  ]
}

function photo(form: MembershipRow['ranking'], ratings: RatingOut[]): PhotoOut {
  return {
    id: 1,
    relative_path: 'a.jpg',
    taken_at: '2026-07-20T10:00:00',
    taken_at_original: '2026-07-20T10:00:00',
    time_offset_minutes: 0,
    camera: null,
    ratings,
    suggestion: null,
    ranking:
      form === 'none'
        ? null
        : {
            event_id: 1,
            rank_score: 0.5,
            rank_position: 1,
            proposed: form === 'proposed',
            partition_size: 1,
            curation_position: null,
          },
    criterion_scores: [],
    fine_labels: [],
    cloud_vision_status: [],
    final_selection_decision: null,
    in_final_selection: false,
    contested: false,
    persons: [],
  }
}

describe('draftMembership gegen die Falltabelle des Servers', () => {
  it('covers the full cross product of ranking form and own status', () => {
    const keys = MEMBERSHIP_TABLE.map((row) => `${row.ranking}/${String(row.own)}`)
    expect(new Set(keys).size).toBe(9)
    for (const form of ['none', 'not_proposed', 'proposed']) {
      for (const own of ['null', 'album_worthy', 'rejected']) {
        expect(keys).toContain(`${form}/${own}`)
      }
    }
  })

  it.each(MEMBERSHIP_TABLE)(
    'ranking $ranking, own $own (other $other) is $membership',
    ({ ranking, own, other, membership }) => {
      // Die Gegenbewertung des anderen Nutzers steht in `ratings[]` und darf nichts entscheiden.
      expect(draftMembership(photo(ranking, rated(own, other)), own)).toBe(membership)
    },
  )
})
