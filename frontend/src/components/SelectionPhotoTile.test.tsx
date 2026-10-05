import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { AlbumParticipantOut, PhotoOut, RankingOut, RatingOut } from '../api/types'
import { ALBUM_STATE_LABELS, NOT_IN_DRAFT_LABEL } from '../utils/albumStateLabels'
import { HANDLES_FULL_WIDTH_PX } from '../utils/curationLayout'
import { SELECTION_DECIDED_BADGE_TEXT, SelectionPhotoTile } from './SelectionPhotoTile'

vi.mock('./PhotoImage', () => ({
  PhotoImage: ({ alt }: { alt: string }) => <img alt={alt} />,
}))

const DANIEL: AlbumParticipantOut = { user_id: 1, username: 'daniel' }
const NORA: AlbumParticipantOut = { user_id: 2, username: 'nora' }
const PARTICIPANTS = [DANIEL, NORA]

function photo(overrides: Partial<PhotoOut> = {}): PhotoOut {
  return {
    id: 1,
    relative_path: 'reise/a.jpg',
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
    persons: [],
    ...overrides,
  }
}

function renderTile(
  overrides: Partial<PhotoOut> = {},
  props: {
    onDecide?: () => void
    largeTriggerRef?: (element: HTMLElement | null) => void
    width?: number
  } = {},
) {
  const onDecide = props.onDecide ?? vi.fn()
  const onOpenLarge = vi.fn()
  const { unmount, container } = render(
    <ul>
      <SelectionPhotoTile
        photo={photo(overrides)}
        width={props.width ?? 300}
        imageHeight={200}
        participants={PARTICIPANTS}
        decidingIncluded={null}
        onDecide={onDecide}
        onOpenLarge={onOpenLarge}
        largeTriggerRef={props.largeTriggerRef ?? (() => {})}
      />
    </ul>,
  )
  return { onDecide, onOpenLarge, unmount, container }
}

/** Die Entscheidungsflaechen der Kachel - ohne den Bild-Ausloeser der Grossansicht. */
function decisionButtons(): HTMLElement[] {
  return screen.getAllByRole('button', { name: /^(Aufnehmen|Nicht aufnehmen|Herausnehmen): / })
}

/** Die Haltungsliste EINER Kachel - sie trägt den Dateinamen, damit sie je Kachel eindeutig ist. */
function stanceList(relativePath = 'reise/a.jpg') {
  return screen.getByRole('list', { name: `Haltung zu ${relativePath}` })
}

function stanceRow(username: string) {
  const row = within(stanceList())
    .getAllByRole('listitem')
    .find((item) => item.textContent?.startsWith(`${username}:`))
  expect(row, `Haltungszeile von ${username}`).toBeDefined()
  return row!
}

/**
 * DER AUFBAU (Zusicherung 23): `ratings[]` steht genau UMGEKEHRT zu `participants`, und nur der
 * ZWEITE Teilnehmer trägt eine Albumentscheidung. `ratings[0]` und `some()` bestehen jeden
 * natürlich gebauten Fall - dieser trennt sie.
 */
const REVERSED_RATINGS: RatingOut[] = [
  { user_id: 2, username: 'nora', status: 'album_worthy', favorite: false },
  { user_id: 1, username: 'daniel', status: null, favorite: true },
]

describe('SelectionPhotoTile - Zuordnung der Haltungen', () => {
  it('assigns each stance to its participant BY NAME, never by the order of ratings[]', () => {
    renderTile({ ratings: REVERSED_RATINGS, contested: true })

    // Innerhalb der jeweiligen Zeile assertiert, nie kachelweit: eine tileweite Textsuche bestuende
    // auch dann, wenn beide Zeilen dieselbe Haltung zeigten.
    expect(within(stanceRow('daniel')).getByLabelText(NOT_IN_DRAFT_LABEL)).toBeInTheDocument()
    expect(within(stanceRow('nora')).getByLabelText(ALBUM_STATE_LABELS.taken)).toBeInTheDocument()
    expect(within(stanceRow('daniel')).queryByLabelText(ALBUM_STATE_LABELS.taken)).toBeNull()
  })

  it('shows the struck stance with its own symbol and accessible name', () => {
    renderTile({
      ratings: [{ user_id: 1, username: 'daniel', status: 'rejected', favorite: false }],
      contested: true,
      persons: [],
    })

    const row = stanceRow('daniel')
    expect(within(row).getByLabelText(ALBUM_STATE_LABELS.struck)).toBeInTheDocument()
    expect(
      within(row).getByLabelText(ALBUM_STATE_LABELS.struck).querySelector('[data-icon="x-circle"]'),
    ).not.toBeNull()
  })

  it('shows the taken stance with the book symbol, never with a check', () => {
    renderTile({
      ratings: [{ user_id: 1, username: 'daniel', status: 'album_worthy', favorite: false }],
      contested: true,
      persons: [],
    })

    const badge = within(stanceRow('daniel')).getByLabelText(ALBUM_STATE_LABELS.taken)
    expect(badge.querySelector('[data-icon="book"]')).not.toBeNull()
  })
})

describe('SelectionPhotoTile - die vier Haltungen', () => {
  const proposedRanking: RankingOut = {
    event_id: 1,
    rank_score: 0.5,
    rank_position: 1,
    proposed: true,
    partition_size: 2,
    curation_position: null,
  }

  it.each([
    {
      name: 'aufgenommen',
      status: 'album_worthy' as const,
      ranking: null,
      label: ALBUM_STATE_LABELS.taken,
    },
    {
      name: 'gestrichen',
      status: 'rejected' as const,
      ranking: null,
      label: ALBUM_STATE_LABELS.struck,
    },
    {
      name: 'unberührt, vorgeschlagen',
      status: null,
      ranking: proposedRanking,
      label: ALBUM_STATE_LABELS.proposal,
    },
  ])('shows "$label" for $name', ({ status, ranking, label }) => {
    renderTile({
      ranking,
      ratings: status === null ? [] : [{ user_id: 1, username: 'daniel', status, favorite: false }],
      contested: true,
    })

    expect(within(stanceRow('daniel')).getByLabelText(label)).toBeInTheDocument()
  })

  it('shows "–" named "Nicht im Entwurf" for untouched and not proposed, in BOTH data forms', () => {
    for (const ranking of [null, { ...proposedRanking, proposed: false }]) {
      const { unmount } = render(
        <ul>
          <SelectionPhotoTile
            photo={photo({ ranking, contested: true })}
            width={300}
            imageHeight={200}
            participants={PARTICIPANTS}
            decidingIncluded={null}
            onDecide={vi.fn()}
            onOpenLarge={vi.fn()}
            largeTriggerRef={() => {}}
          />
        </ul>,
      )
      const badge = within(stanceRow('daniel')).getByLabelText(NOT_IN_DRAFT_LABEL)
      expect(badge).toHaveTextContent('–')
      unmount()
    }
  })
})

describe('SelectionPhotoTile - Kardinalität der Haltungszeilen', () => {
  it('carries ONE row per participant, even for a participant without any rating', () => {
    // Zusicherung 24: die Zahl der Zeilen ist die Kardinalitaet von `participants`, nie die von
    // `ratings[]`. Aus `ratings[]` abgeleitet fehlte genau der Nutzer, den die Story ausdruecklich
    // als "kein Sonderfall" benennt.
    renderTile({ ratings: [], contested: true })

    expect(within(stanceList()).getAllByRole('listitem')).toHaveLength(2)
    expect(stanceRow('daniel')).toBeInTheDocument()
    expect(stanceRow('nora')).toBeInTheDocument()
  })

  it('does not grow a row for a rating whose user is not a participant', () => {
    renderTile({
      ratings: [
        ...REVERSED_RATINGS,
        { user_id: 99, username: 'fremd', status: 'rejected', favorite: false },
      ],
      contested: true,
      persons: [],
    })

    expect(within(stanceList()).getAllByRole('listitem')).toHaveLength(2)
  })
})

describe('SelectionPhotoTile - die Trefferfläche', () => {
  it('offers BOTH decisions on a contested photo, with the file name in each name', async () => {
    const { onDecide } = renderTile({ contested: true })

    const take = screen.getByRole('button', { name: 'Aufnehmen: reise/a.jpg' })
    const drop = screen.getByRole('button', { name: 'Nicht aufnehmen: reise/a.jpg' })
    await userEvent.click(take)
    expect(onDecide).toHaveBeenCalledWith(true)
    await userEvent.click(drop)
    expect(onDecide).toHaveBeenCalledWith(false)
  })

  it('offers exactly one button in the result view: taking a photo out', async () => {
    const { onDecide } = renderTile({ in_final_selection: true })

    expect(decisionButtons()).toHaveLength(1)
    await userEvent.click(screen.getByRole('button', { name: 'Herausnehmen: reise/a.jpg' }))
    expect(onDecide).toHaveBeenCalledWith(false)
  })

  it('offers exactly one button for a photo that was explicitly taken out', async () => {
    const { onDecide } = renderTile({ final_selection_decision: false, in_final_selection: false })

    expect(decisionButtons()).toHaveLength(1)
    await userEvent.click(screen.getByRole('button', { name: 'Aufnehmen: reise/a.jpg' }))
    expect(onDecide).toHaveBeenCalledWith(true)
  })

  it('marks ONLY the pressed button as busy while a decision runs', () => {
    render(
      <ul>
        <SelectionPhotoTile
          photo={photo({ contested: true })}
          width={300}
          imageHeight={200}
          participants={PARTICIPANTS}
          decidingIncluded={true}
          onDecide={vi.fn()}
          onOpenLarge={vi.fn()}
          largeTriggerRef={() => {}}
        />
      </ul>,
    )

    const take = screen.getByRole('button', { name: 'Aufnehmen: reise/a.jpg' })
    const drop = screen.getByRole('button', { name: 'Nicht aufnehmen: reise/a.jpg' })
    expect(within(take).getByTestId('button-spinner')).toBeInTheDocument()
    expect(within(drop).queryByTestId('button-spinner')).toBeNull()
  })

  it('puts the two decisions side by side, "Aufnehmen" (book) first, "Nicht aufnehmen" (x-circle)', () => {
    renderTile({ contested: true })

    const take = screen.getByRole('button', { name: 'Aufnehmen: reise/a.jpg' })
    const drop = screen.getByRole('button', { name: 'Nicht aufnehmen: reise/a.jpg' })
    expect(take.parentElement).toBe(drop.parentElement)
    expect(take.compareDocumentPosition(drop) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(take.querySelector('[data-icon="book"]')).not.toBeNull()
    expect(drop.querySelector('[data-icon="x-circle"]')).not.toBeNull()
  })

  it.each([
    [{ contested: true }, HANDLES_FULL_WIDTH_PX['selection-contested']],
    [{ in_final_selection: true }, HANDLES_FULL_WIDTH_PX['selection-single']],
  ])('switches %j to symbols strictly below %s px', (overrides, threshold) => {
    for (const [width, iconOnly] of [
      [threshold - 1, true],
      [threshold, false],
    ] as const) {
      const { unmount } = renderTile(overrides, { width })
      for (const control of decisionButtons()) {
        expect(control.querySelector('[data-tile-action-hint]') !== null, `${width}`).toBe(iconOnly)
      }
      unmount()
    }
  })

  it('shows "Herausnehmen" with x-circle', () => {
    renderTile({ in_final_selection: true })

    expect(
      screen
        .getByRole('button', { name: 'Herausnehmen: reise/a.jpg' })
        .querySelector('[data-icon="x-circle"]'),
    ).not.toBeNull()
  })
})

describe('SelectionPhotoTile - die drei Anzeigezustände', () => {
  it('carries no extra marker when the two simply agree', () => {
    // Einigkeit ist eine VORBELEGUNG - ohne sichtbaren Unterschied waere nicht erkennbar, ob
    // jemand das Bild schon angesehen hat.
    renderTile({ in_final_selection: true, final_selection_decision: null })

    expect(screen.queryByText(SELECTION_DECIDED_BADGE_TEXT)).toBeNull()
  })

  it('carries its OWN marker once it was decided jointly - not just another colour', () => {
    renderTile({ in_final_selection: true, final_selection_decision: true })

    expect(screen.getByText(SELECTION_DECIDED_BADGE_TEXT)).toBeInTheDocument()
  })

  it('marks an explicitly removed photo by its struck file name', () => {
    const { container } = render(
      <ul>
        <SelectionPhotoTile
          photo={photo({ final_selection_decision: false, in_final_selection: false })}
          width={300}
          imageHeight={200}
          participants={PARTICIPANTS}
          decidingIncluded={null}
          onDecide={vi.fn()}
          onOpenLarge={vi.fn()}
          largeTriggerRef={() => {}}
        />
      </ul>,
    )

    expect(container.querySelector('[data-struck="true"]')).not.toBeNull()
    expect(screen.getByRole('button', { name: 'Aufnehmen: reise/a.jpg' })).toBeInTheDocument()
  })
})

describe('SelectionPhotoTile - was hier nicht stehen darf', () => {
  const states: { label: string; overrides: Partial<PhotoOut> }[] = [
    { label: 'strittig', overrides: { contested: true } },
    { label: 'einig drin', overrides: { in_final_selection: true } },
    {
      label: 'gemeinsam entschieden, drin',
      overrides: { in_final_selection: true, final_selection_decision: true },
    },
    { label: 'gemeinsam entschieden, heraus', overrides: { final_selection_decision: false } },
  ]

  it.each(states)(
    'shows no check symbol in the state "$label" (it is the success message of the product)',
    ({ overrides }) => {
      // Zusicherung 27, als ABWESENHEIT im gerenderten DOM geprueft, nicht als Absichtserklaerung.
      const { container } = render(
        <ul>
          <SelectionPhotoTile
            photo={photo({ ...overrides, ratings: REVERSED_RATINGS })}
            width={300}
            imageHeight={200}
            participants={PARTICIPANTS}
            decidingIncluded={null}
            onDecide={vi.fn()}
            onOpenLarge={vi.fn()}
            largeTriggerRef={() => {}}
          />
        </ul>,
      )

      expect(container.querySelector('[data-icon="check"]')).toBeNull()
    },
  )

  it.each(states)('uses no destructive button variant in the state "$label"', ({ overrides }) => {
    // Die Kollisionsregel aus `ui/button.tsx`: gefuelltes --danger bei Radius 6px ist formgleich
    // mit dem Kennzeichen "Aussortiert", und diese Seite zeigt Bewertungs-Kennzeichen je
    // Teilnehmer.
    const { container } = render(
      <ul>
        <SelectionPhotoTile
          photo={photo({ ...overrides, ratings: REVERSED_RATINGS })}
          width={300}
          imageHeight={200}
          participants={PARTICIPANTS}
          decidingIncluded={null}
          onDecide={vi.fn()}
          onOpenLarge={vi.fn()}
          largeTriggerRef={() => {}}
        />
      </ul>,
    )

    expect(container.querySelector('button.bg-danger')).toBeNull()
  })

  it('carries no motif strength list and no info popover', () => {
    // Anders als `CurationPhotoTile`: die Kachel traegt die Haltungen und die eine Entscheidung,
    // sonst nichts.
    renderTile({ contested: true })

    expect(screen.queryByRole('button', { name: /Details/ })).toBeNull()
    expect(screen.queryByRole('list', { name: 'Motive' })).toBeNull()
  })
})

describe('SelectionPhotoTile - die Grossansicht (Spec 0531)', () => {
  it('opens the large view of exactly this photo from the image area, without deciding', () => {
    const { onDecide, onOpenLarge } = renderTile({ id: 17, contested: true })

    fireEvent.click(screen.getByRole('button', { name: 'Großansicht: reise/a.jpg' }))

    expect(onOpenLarge).toHaveBeenCalledTimes(1)
    expect(onOpenLarge).toHaveBeenCalledWith(17)
    expect(onDecide).not.toHaveBeenCalled()
  })

  it.each([
    [{ contested: true }, 'Aufnehmen'],
    [{ contested: true }, 'Nicht aufnehmen'],
    [{ in_final_selection: true }, 'Herausnehmen'],
  ])('does not open the large view from the decision %j / %s', (overrides, label) => {
    const { onOpenLarge } = renderTile(overrides)

    fireEvent.click(screen.getByRole('button', { name: `${label}: reise/a.jpg` }))

    expect(onOpenLarge).not.toHaveBeenCalled()
  })

  it('makes the image trigger the first tabbable element and hands it out', async () => {
    const largeTriggerRef = vi.fn()
    renderTile({ contested: true }, { largeTriggerRef })

    await userEvent.tab()

    const trigger = screen.getByRole('button', { name: 'Großansicht: reise/a.jpg' })
    expect(trigger).toHaveFocus()
    expect(largeTriggerRef).toHaveBeenLastCalledWith(trigger)
  })
})

describe('SelectionPhotoTile - Haltungszeichen und Leiste', () => {
  it('shows each stance as the symbol mark, its word only as accessible name', () => {
    renderTile({ ratings: REVERSED_RATINGS, contested: true })

    const mark = within(stanceRow('nora')).getByRole('img', { name: ALBUM_STATE_LABELS.taken })
    expect(mark.textContent).toBe('')
  })

  it('carries reason, suitability and file name in the strip, in that order', () => {
    const { container } = renderTile({
      contested: true,
      album_suitability: { level: 4, reason: 'Schönes Licht.' },
    })

    const strip = container.querySelector<HTMLElement>('[data-tile-details]')!
    expect(strip).toHaveTextContent(/Begründung des Modells.*Schönes Licht\..*a\.jpg$/)
  })

  it('strikes the file name of a photo taken out', () => {
    const { container } = renderTile({ final_selection_decision: false })

    const strip = container.querySelector<HTMLElement>('[data-tile-details]')!
    expect(within(strip).getByText('a.jpg')).toHaveAttribute('data-struck', 'true')
  })
})
