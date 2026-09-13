import { describe, expect, it } from 'vitest'

import type {
  EventOut,
  MotifStrengthOut,
  PhotoOut,
  RankingOut,
  RatingOut,
  RatingStatus,
} from '../api/types'
import { MOTIF_SET } from '../test/motifSetFixture'
import {
  DRAFT_MOTIFS_NONE_TEXT,
  DRAFT_MOTIFS_UNASSESSED_TEXT,
  draftMotifText,
  draftSizeText,
  formatDraftPhotoCount,
  insertDraftPhoto,
  isInAlbum,
  isTakenWithoutProposal,
  wasInAlbum,
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
    final_selection_decision: null,
    in_final_selection: false,
    contested: false,
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

describe('draftMotifText', () => {
  const USERNAME = 'daniel'

  /** Der Achter-Vektor eines Fotos - `present` kommt vom Server, `strength` ist Beiwerk. */
  function motifs(present: Record<string, boolean>, strength = 0.5): MotifStrengthOut[] {
    return MOTIF_SET.items.map((item) => ({
      key: item.key,
      strength,
      correction: null,
      present: present[item.key] ?? false,
    }))
  }

  function ownRating(status: RatingStatus): RatingOut {
    return { user_id: 7, username: USERNAME, status, favorite: false }
  }

  /** Ein Foto MIT Kopfzeile - ohne sie ist `motifs` leer (der Server liefert dann keine Zeile). */
  function assessed(overrides: Partial<PhotoOut> = {}): PhotoOut {
    return photo({
      motif_assessment: {
        source: 'cloud',
        provider: 'anthropic',
        excluded_document: false,
        computed_at: '2026-07-21T09:00:00',
      },
      motifs: motifs({}),
      ...overrides,
    })
  }

  it('names the motifs of the photos in the album, alphabetically by display name', () => {
    // Die Sollreihenfolge entspricht WEDER der Registry- noch der Antwortreihenfolge: „Bauwerk und
    // Sehenswürdigkeit" steht in der Registry hinter „Menschen" und wird hier als letztes Foto
    // geliefert, gehört alphabetisch aber nach vorn.
    const items = [
      assessed({ id: 1, motifs: motifs({ menschen: true }) }),
      assessed({ id: 2, motifs: motifs({ tiere: true }) }),
      assessed({ id: 3, motifs: motifs({ bauwerk_sehenswuerdigkeit: true }) }),
    ]

    expect(draftMotifText(items, USERNAME, MOTIF_SET.items)).toBe(
      'Bauwerk und Sehenswürdigkeit, Menschen, Tiere',
    )
  })

  it('names a motif once, however many photos carry it', () => {
    const items = [
      assessed({ id: 1, motifs: motifs({ menschen: true }) }),
      assessed({ id: 2, motifs: motifs({ menschen: true, tiere: true }) }),
    ]

    expect(draftMotifText(items, USERNAME, MOTIF_SET.items)).toBe('Menschen, Tiere')
  })

  it('carries no number at all', () => {
    // Die Rangfolge-Eindaemmung im Frontend: keine Staerke, keine Anzahl, keine Reihung nach
    // Staerke - ein Vergleich von Motivstaerken findet an keiner Stelle der Oberflaeche statt.
    const items = [assessed({ id: 1, motifs: motifs({ menschen: true, tiere: true }) })]

    expect(draftMotifText(items, USERNAME, MOTIF_SET.items)).not.toMatch(/\d/)
  })

  it('follows `present`, never `strength`', () => {
    // Zusicherung 28: zwei bewusst WIDERSPRUECHLICHE Aufbauten. Eine Implementierung, die im
    // Frontend doch vergleicht, besteht jeden natuerlich gebauten Fall - diesen hier nicht.
    const items = [
      assessed({
        id: 1,
        motifs: [
          { key: 'menschen', strength: 0.9, correction: null, present: false },
          { key: 'tiere', strength: 0.1, correction: null, present: true },
        ],
      }),
    ]

    const text = draftMotifText(items, USERNAME, MOTIF_SET.items)

    expect(text).toBe('Tiere')
    expect(text).not.toContain('Menschen')
  })

  it('leaves out the motifs of a struck photo', () => {
    // Ein gestrichenes Bild bleibt sichtbar, gehoert aber nicht zum Entwurf (ADR 0098 Punkt 1) -
    // seine Motive also nicht in die Mischung.
    const items = [
      assessed({ id: 1, motifs: motifs({ menschen: true }) }),
      assessed({
        id: 2,
        motifs: motifs({ tiere: true }),
        ratings: [ownRating('rejected')],
      }),
    ]

    expect(draftMotifText(items, USERNAME, MOTIF_SET.items)).toBe('Menschen')
  })

  it('returns null when no photo of the group is in the album', () => {
    const items = [
      assessed({ id: 1, motifs: motifs({ menschen: true }), ratings: [ownRating('rejected')] }),
    ]

    expect(draftMotifText(items, USERNAME, MOTIF_SET.items)).toBeNull()
  })

  it('says "not yet assessed" when no photo of the album carries a header', () => {
    const items = [photo({ id: 1, motif_assessment: null, motifs: [] })]

    expect(draftMotifText(items, USERNAME, MOTIF_SET.items)).toBe(DRAFT_MOTIFS_UNASSESSED_TEXT)
  })

  it('says "none recognised" for a header without a single present motif', () => {
    // Der Unterschied zum Fall darueber ist die eigentliche Zusage: "nicht angesehen" und "nichts
    // erkannt" sind zwei Zustaende, und ein Text fuer beide verwischte sie.
    const items = [assessed({ id: 1, motifs: motifs({}) })]

    expect(draftMotifText(items, USERNAME, MOTIF_SET.items)).toBe(DRAFT_MOTIFS_NONE_TEXT)
  })

  it('falls back to the generic name while the motif set is still loading', () => {
    const items = [assessed({ id: 1, motifs: motifs({ menschen: true }) })]

    expect(draftMotifText(items, USERNAME, [])).toBe('Menschen')
  })
})

describe('wasInAlbum', () => {
  const cases: { ownStatus: RatingStatus | null; expected: boolean }[] = [
    { ownStatus: 'rejected', expected: true },
    { ownStatus: 'album_worthy', expected: false },
    { ownStatus: null, expected: false },
  ]

  it.each(cases)('is $expected for the own status $ownStatus', ({ ownStatus, expected }) => {
    // Das Abzeichen „zuvor im Album" hängt an der EIGENEN Streichung. Ein nie bewertetes Foto
    // unter den Alternativen war nie im Album - es trägt kein Abzeichen.
    expect(wasInAlbum(ownStatus)).toBe(expected)
  })
})

describe('insertDraftPhoto', () => {
  function list(items: PhotoOut[]) {
    return { items, total: items.length }
  }

  it('inserts by (event position, taken_at, id) - the sort key of the server', () => {
    // Nicht ans Ende und nicht neben das ersetzte Bild: derselbe Schlüssel wie der Server, damit
    // die Liste nach dem nächsten vollständigen Laden dieselbe Reihenfolge hat.
    const first = photo({ id: 1, taken_at: '2026-07-20T10:00:00' })
    const third = photo({ id: 3, taken_at: '2026-07-20T12:00:00' })
    const second = photo({ id: 2, taken_at: '2026-07-20T11:00:00' })

    const result = insertDraftPhoto(list([first, third]), second)

    expect(result.items.map((item) => item.id)).toEqual([1, 2, 3])
    expect(result.total).toBe(3)
  })

  it('sorts a later event behind an earlier one, regardless of the time', () => {
    // Die Eventposition schlägt die Zeit: ein Foto mit früherer Aufnahmezeit gehört trotzdem in
    // seine eigene Eventgruppe, nicht vor die erste.
    const early = photo({ id: 1, taken_at: '2026-07-20T10:00:00', event: event({ position: 1 }) })
    const late = photo({
      id: 2,
      taken_at: '2026-07-19T08:00:00',
      event: event({ id: 2, position: 2 }),
    })

    expect(insertDraftPhoto(list([early]), late).items.map((item) => item.id)).toEqual([1, 2])
  })

  it('breaks a tie in taken_at over the smaller id', () => {
    const existing = photo({ id: 5, taken_at: '2026-07-20T10:00:00' })
    const inserted = photo({ id: 2, taken_at: '2026-07-20T10:00:00' })

    expect(insertDraftPhoto(list([existing]), inserted).items.map((item) => item.id)).toEqual([
      2, 5,
    ])
  })

  it('leaves the list untouched when the photo already stands in it', () => {
    // Ein zweites Vorkommen desselben Fotos wäre eine Kachel, die zweimal dasteht und deren beide
    // Hälften auseinanderlaufen.
    const existing = photo({ id: 1 })
    const before = list([existing])

    expect(insertDraftPhoto(before, photo({ id: 1 }))).toBe(before)
  })

  it('leaves the list untouched for a photo without an event', () => {
    // Ausfallrichtung „nicht zeigen": ohne Event gehört das Foto in keine Gruppe, und
    // `groupDraftByDay` übergeht es ohnehin - sichtbar wäre allein die falsche Ist-Anzahl.
    const before = list([photo({ id: 1 })])

    expect(insertDraftPhoto(before, photo({ id: 2, event: null }))).toBe(before)
  })

  it('keeps the object reference of every untouched photo', () => {
    // Wie `applyWrittenRating`: unberührte Kacheln rendern dadurch nicht neu.
    const first = photo({ id: 1, taken_at: '2026-07-20T10:00:00' })
    const result = insertDraftPhoto(
      list([first]),
      photo({ id: 2, taken_at: '2026-07-20T11:00:00' }),
    )

    expect(result.items[0]).toBe(first)
  })
})
