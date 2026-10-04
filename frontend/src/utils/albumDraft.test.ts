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
import type { DraftCounts } from './albumDraft'
import {
  DRAFT_MOTIFS_NONE_TEXT,
  DRAFT_MOTIFS_UNASSESSED_TEXT,
  draftClosingTexts,
  draftCounts,
  draftMotifText,
  draftOverviewText,
  draftSizeText,
  formatDraftPhotoCount,
  insertDraftPhoto,
  isTakenWithoutProposal,
  reAddDecision,
  smallerProposalText,
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
    persons: [],
    event: event(),
    ...overrides,
  }
}

const OWN = 'daniel'

function rated(own: RatingStatus | null, other: RatingStatus | null = null): RatingOut[] {
  return [
    ...(own === null ? [] : [{ user_id: 1, username: OWN, status: own, favorite: false }]),
    ...(other === null ? [] : [{ user_id: 2, username: 'anna', status: other, favorite: false }]),
  ]
}

describe('draftCounts', () => {
  /*
   * Die Zählertabelle der Akzeptanzkriterien als Zustandsübergänge über EINE Fixture: vier Fotos
   * eines Events. Die Zahlen sind aus dem Zustand abgeleitet, nicht aus gezählten Handgriffen -
   * jeder Schritt setzt nur den eigenen Status und vergleicht.
   */
  const start = [
    photo({ id: 1 }),
    photo({ id: 2, ratings: rated('album_worthy') }),
    photo({ id: 3, ranking: ranking({ proposed: false }) }),
    photo({ id: 4, ranking: ranking({ proposed: false }), ratings: rated('rejected') }),
  ]

  function withOwn(items: PhotoOut[], id: number, own: RatingStatus | null): PhotoOut[] {
    return items.map((item) => (item.id === id ? { ...item, ratings: rated(own) } : item))
  }

  function delta(before: DraftCounts, after: DraftCounts): number[] {
    return [
      after.inAlbum - before.inAlbum,
      after.taken - before.taken,
      after.struck - before.struck,
    ]
  }

  const initial = draftCounts(start, OWN)

  it('counts the album, the taken and the struck photos of the state', () => {
    // Das unberührte Kandidatenfoto gehört nicht zur Antwortmenge und zählt nirgends.
    expect(initial).toEqual({ inAlbum: 2, taken: 1, struck: 1 })
  })

  it.each([
    { name: 'Streichen eines „Vorschlag“', id: 1, own: 'rejected', expected: [-1, 0, 1] },
    { name: 'Streichen eines „Aufgenommen“', id: 2, own: 'rejected', expected: [-1, -1, 1] },
    {
      name: 'Wieder aufnehmen, nicht vorgeschlagen',
      id: 4,
      own: 'album_worthy',
      expected: [1, 1, -1],
    },
    {
      name: 'Hinzufügen eines nicht gestrichenen Fotos',
      id: 3,
      own: 'album_worthy',
      expected: [1, 1, 0],
    },
    {
      name: 'Hinzufügen eines gestrichenen Fotos',
      id: 4,
      own: 'album_worthy',
      expected: [1, 1, -1],
    },
  ] as const)('$name', ({ id, own, expected }) => {
    expect(delta(initial, draftCounts(withOwn(start, id, own), OWN))).toEqual(expected)
  })

  it('Wieder aufnehmen, vorgeschlagen: the own decision goes, a stays', () => {
    const struck = withOwn(start, 1, 'rejected')

    expect(delta(draftCounts(struck, OWN), draftCounts(withOwn(struck, 1, null), OWN))).toEqual([
      1, 0, -1,
    ])
  })

  it.each([
    {
      name: 'Tausch „Vorschlag“ gegen unberührte Alternative',
      replaced: 1,
      chosen: 3,
      expected: [0, 1, 1],
    },
    {
      name: 'Tausch „Aufgenommen“ gegen unberührte Alternative',
      replaced: 2,
      chosen: 3,
      expected: [0, 0, 1],
    },
    {
      name: 'Tausch „Vorschlag“ gegen gestrichene Alternative',
      replaced: 1,
      chosen: 4,
      expected: [0, 1, 0],
    },
  ] as const)('$name, and undo restores the start', ({ replaced, chosen, expected }) => {
    const exchanged = withOwn(withOwn(start, replaced, 'rejected'), chosen, 'album_worthy')

    expect(delta(initial, draftCounts(exchanged, OWN))).toEqual(expected)
    // Rückgängig setzt den eigenen Status beider Fotos auf den Vorzustand - und damit die Zahlen.
    const previous = (id: number) => start.find((item) => item.id === id)?.ratings ?? []
    const undone = exchanged.map((item) =>
      item.id === replaced || item.id === chosen ? { ...item, ratings: previous(item.id) } : item,
    )
    expect(draftCounts(undone, OWN)).toEqual(initial)
  })

  it('ignores the decisions of the other user', () => {
    const others = start.map((item) => ({ ...item, ratings: rated(null, 'rejected') }))

    expect(draftCounts(others, OWN)).toEqual({ inAlbum: 2, taken: 0, struck: 0 })
  })
})

describe('reAddDecision', () => {
  it('withdraws the own decision for a photo the proposal carries', () => {
    expect(reAddDecision(photo())).toBeNull()
  })

  it.each([
    { name: 'ranking: null', subject: photo({ ranking: null }) },
    { name: 'proposed: false', subject: photo({ ranking: ranking({ proposed: false }) }) },
  ])('takes the photo in when the proposal does not carry it ($name)', ({ subject }) => {
    expect(reAddDecision(subject)).toBe('album_worthy')
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
  it('names album, target, taken and struck in one sentence', () => {
    expect(draftSizeText({ inAlbum: 142, taken: 3, struck: 5 }, 130)).toBe(
      '142 im Album · Richtwert etwa 130 · 3 aufgenommen · 5 gestrichen',
    )
  })

  it('says the same thing below, at and above the target', () => {
    // Eine Abweichung nach oben wie nach unten ist ein neutraler Hinweis - derselbe Satzbau, kein
    // zweiter Ton, kein Wort wie "zu wenig" oder "zu viel".
    const shapes = [100, 130, 160].map((inAlbum) =>
      draftSizeText({ inAlbum, taken: 0, struck: 0 }, 130).replace(/\d+/g, '#'),
    )

    expect(new Set(shapes).size).toBe(1)
  })
})

describe('smallerProposalText', () => {
  /** `proposed` vorgeschlagene Fotos, dazu je ein nicht vorgeschlagenes. */
  function draftItems(proposed: number): PhotoOut[] {
    return Array.from({ length: proposed }, (_, index) =>
      photo({ id: index + 1, ranking: ranking({ proposed: true }) }),
    )
  }

  it('names a proposal that stays below the target because the candidates ran out', () => {
    expect(smallerProposalText(draftItems(5), 150, 5)).toBe(
      'Der Vorschlag umfasst 5 Fotos statt etwa 150 – mehr auswahlfähige Fotos gibt dieses Projekt nicht her.',
    )
  })

  it('counts eligible candidates only - an excluded document in the partition does not hide the line', () => {
    /* `partition_size` zählt das ausgeschlossene Dokument mit; die auswahlfähige Zahl nicht. */
    const items = draftItems(2).map((item) => ({
      ...item,
      ranking: ranking({ proposed: true, partition_size: 3 }),
    }))

    expect(smallerProposalText(items, 150, 2)).toMatch(/^Der Vorschlag umfasst 2 Fotos /)
  })

  it('stays silent below the target while candidates are left (old proposal in transition)', () => {
    /* Pflichtfall der Teststrategie: ein Bestandsvorschlag nach der alten Vorbelegung ist klein,
     * obwohl genug Fotos da sind - die Zeile behauptete sonst eine falsche Ursache. */
    expect(smallerProposalText(draftItems(3), 150, 70)).toBeNull()
  })

  it('stays silent at or above the target, coverage included', () => {
    expect(smallerProposalText(draftItems(4), 4, 10)).toBeNull()
    expect(smallerProposalText(draftItems(3), 2, 3)).toBeNull()
  })

  it('counts the proposal, not the own decisions, and ignores photos without a ranking', () => {
    const items = [
      ...draftItems(2),
      photo({ id: 99, ranking: null, ratings: rated('album_worthy') }),
    ]

    expect(smallerProposalText(items, 150, 2)).toMatch(/^Der Vorschlag umfasst 2 Fotos /)
  })

  it('says nothing without any proposal', () => {
    expect(smallerProposalText([], 150, 0)).toBeNull()
  })
})

describe('draftClosingTexts', () => {
  it('names the album, the interventions and that nothing needs confirming', () => {
    expect(draftClosingTexts({ inAlbum: 12, taken: 2, struck: 3 }, 10)).toEqual([
      '12 Fotos im Album, Richtwert etwa 10.',
      'Deine Eingriffe: 2 aufgenommen, 3 gestrichen.',
      'Nichts muss bestätigt werden; du kannst jederzeit weiterarbeiten.',
    ])
  })

  it('says the proposal stands unchanged without any intervention', () => {
    expect(draftClosingTexts({ inAlbum: 8, taken: 0, struck: 0 }, 10)[1]).toBe(
      'Keine Eingriffe – der Vorschlag gilt unverändert.',
    )
  })

  it.each([
    { taken: 1, struck: 0 },
    { taken: 0, struck: 1 },
  ])('keeps the intervention sentence for $taken/$struck', ({ taken, struck }) => {
    expect(draftClosingTexts({ inAlbum: 8, taken, struck }, 10)[1]).toBe(
      `Deine Eingriffe: ${taken} aufgenommen, ${struck} gestrichen.`,
    )
  })
})

describe('draftOverviewText', () => {
  it('names days and events', () => {
    expect(draftOverviewText(3, 17)).toBe('3 Tage · 17 Events')
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
    // Ein gestrichenes Bild steht in der Antwort, gehoert aber nicht zum Album - seine Motive
    // also nicht in die Mischung.
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

describe('insertDraftPhoto', () => {
  function list(items: PhotoOut[]) {
    return { events: [event()], items, eligible_candidate_count: items.length }
  }

  it('inserts by (event position, taken_at, id) - the sort key of the server', () => {
    // Nicht ans Ende und nicht neben das ersetzte Bild: derselbe Schlüssel wie der Server, damit
    // die Liste nach dem nächsten vollständigen Laden dieselbe Reihenfolge hat.
    const first = photo({ id: 1, taken_at: '2026-07-20T10:00:00' })
    const third = photo({ id: 3, taken_at: '2026-07-20T12:00:00' })
    const second = photo({ id: 2, taken_at: '2026-07-20T11:00:00' })

    const result = insertDraftPhoto(list([first, third]), second)

    expect(result.items.map((item) => item.id)).toEqual([1, 2, 3])
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
