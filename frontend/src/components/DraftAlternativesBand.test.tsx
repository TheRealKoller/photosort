import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as photosApi from '../api/photos'
import type { DraftAlternativesOut, EventOut, PhotoOut } from '../api/types'
import { ALBUM_STATE_LABELS } from '../utils/albumStateLabels'
import {
  ALTERNATIVES_ORDER_TEXT,
  BAND_SIZE,
  CANDIDATES_NONE_TEXT,
  DraftAddPanel,
  DraftAlternativesBand,
} from './DraftAlternativesBand'

vi.mock('../api/photos')

const USERNAME = 'daniel'

const EVENT: EventOut = {
  id: 42,
  position: 1,
  started_at: '2026-07-20T10:00:00',
  ended_at: '2026-07-20T11:00:00',
  place: null,
  place_name: null,
}

function photo(id: number, overrides: Partial<PhotoOut> = {}): PhotoOut {
  return {
    id,
    relative_path: `dir/${id}.jpg`,
    taken_at: '2026-07-20T10:00:00',
    taken_at_original: '2026-07-20T10:00:00',
    time_offset_minutes: 0,
    camera: null,
    ratings: [],
    suggestion: null,
    ranking: {
      event_id: EVENT.id,
      rank_score: 0.8,
      rank_position: 1,
      proposed: false,
      partition_size: 5,
      curation_position: null,
    },
    criterion_scores: [],
    fine_labels: [],
    cloud_vision_status: [],
    final_selection_decision: null,
    in_final_selection: false,
    contested: false,
    persons: [],
    event: EVENT,
    ...overrides,
  }
}

function answer(
  ids: number[],
  {
    offset = 0,
    referenceIndex = null,
    total = ids.length,
  }: {
    offset?: number
    referenceIndex?: number | null
    total?: number
  } = {},
): DraftAlternativesOut {
  return { items: ids.map((id) => photo(id)), total, offset, reference_index: referenceIndex }
}

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

function renderBand(excludedIds: ReadonlySet<number> = new Set()) {
  return render(
    <ul>
      <DraftAlternativesBand
        id="band"
        projectId={1}
        photo={photo(9)}
        username={USERNAME}
        excludedIds={excludedIds}
        onExchange={() => {}}
        busyIds={new Set()}
        error={null}
        onOpenAll={() => {}}
        onClose={() => {}}
      />
    </ul>,
    { wrapper },
  )
}

/** Die Zellen der geordneten Reihe: Kandidaten über ihre Aktion, die Marke über ihren Namen. */
function rowCells(): (string | null)[] {
  const list = screen.getByRole('list', { name: 'Alternativen, zeitlich geordnet' })
  return Array.from(list.children).map(
    (cell) =>
      cell.getAttribute('aria-label') ??
      cell.querySelector('button')?.getAttribute('aria-label') ??
      null,
  )
}

describe('DraftAlternativesBand', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockResolvedValue('blob:fake-url')
  })

  it('asks the server for the nearest window around THIS photo', async () => {
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(answer([2]))

    renderBand()

    await screen.findByRole('button', { name: 'Tauschen: dir/2.jpg' })
    expect(photosApi.listDraftAlternatives).toHaveBeenCalledWith(1, {
      eventId: EVENT.id,
      photoId: 9,
      nearest: BAND_SIZE,
    })
  })

  it('names the order and puts the photo to be replaced between its neighbours', async () => {
    // AK3/AK4/AK5: Fenster ab `offset` 3, Bezugsbild an Stelle 5 der Reihe - also nach dem
    // zweiten Bild des Fensters. Die Reihenfolge ist die der Antwort.
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(
      answer([5, 2, 7, 3], { offset: 3, referenceIndex: 5, total: 10 }),
    )

    renderBand()

    await screen.findByRole('button', { name: 'Tauschen: dir/5.jpg' })
    expect(screen.getByText(ALTERNATIVES_ORDER_TEXT)).toBeInTheDocument()
    expect(rowCells()).toEqual([
      'Tauschen: dir/5.jpg',
      'Tauschen: dir/2.jpg',
      'Wird ersetzt: dir/9.jpg',
      'Tauschen: dir/7.jpg',
      'Tauschen: dir/3.jpg',
    ])
  })

  it('makes the marker no control: no action, no rating, a word and the file name', async () => {
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(answer([2], { referenceIndex: 0 }))

    renderBand()

    const marker = await screen.findByRole('listitem', { name: 'Wird ersetzt: dir/9.jpg' })
    expect(within(marker).queryByRole('button')).toBeNull()
    expect(within(marker).getByText('Wird ersetzt')).toBeInTheDocument()
    expect(within(marker).getByText('9.jpg')).toBeInTheDocument()
    expect(within(marker).queryByText(/albumtauglich/)).toBeNull()
    expect(rowCells()[0]).toBe('Wird ersetzt: dir/9.jpg')
  })

  it('puts the marker last when the photo is the latest of the row', async () => {
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(
      answer([2, 3], { referenceIndex: 2 }),
    )

    renderBand()

    await screen.findByRole('button', { name: 'Tauschen: dir/3.jpg' })
    expect(rowCells().at(-1)).toBe('Wird ersetzt: dir/9.jpg')
  })

  it('keeps the marker after its true predecessor when a photo was swapped out', async () => {
    // Die Position gilt der UNGEFILTERTEN Antwort: Fällt das Bild an der Markenstelle durch einen
    // optimistischen Tausch heraus, steht die Marke vor dem nächsten verbliebenen - und rutscht
    // nicht um eine Stelle. Nachgefüllt wird nicht.
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(
      answer([5, 2, 7, 3], { offset: 3, referenceIndex: 5, total: 10 }),
    )

    renderBand(new Set([7]))

    await screen.findByRole('button', { name: 'Tauschen: dir/5.jpg' })
    expect(rowCells()).toEqual([
      'Tauschen: dir/5.jpg',
      'Tauschen: dir/2.jpg',
      'Wird ersetzt: dir/9.jpg',
      'Tauschen: dir/3.jpg',
    ])
  })

  it('stays on the predecessor when a photo BEFORE the marker was swapped out', async () => {
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(
      answer([5, 2, 7, 3], { offset: 3, referenceIndex: 5, total: 10 }),
    )

    renderBand(new Set([5]))

    await screen.findByRole('button', { name: 'Tauschen: dir/2.jpg' })
    expect(rowCells()).toEqual([
      'Tauschen: dir/2.jpg',
      'Wird ersetzt: dir/9.jpg',
      'Tauschen: dir/7.jpg',
      'Tauschen: dir/3.jpg',
    ])
  })

  it('shows no marker and no order text in an empty row', async () => {
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(answer([], { referenceIndex: 0 }))

    renderBand()

    expect(await screen.findByText(CANDIDATES_NONE_TEXT)).toBeInTheDocument()
    expect(screen.queryByText(ALTERNATIVES_ORDER_TEXT)).toBeNull()
    expect(screen.queryByRole('listitem', { name: /^Wird ersetzt/ })).toBeNull()
  })

  it('guesses no position without a reference index', async () => {
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(answer([2, 3]))

    renderBand()

    await screen.findByRole('button', { name: 'Tauschen: dir/3.jpg' })
    expect(screen.queryByRole('listitem', { name: /^Wird ersetzt/ })).toBeNull()
  })

  it('keeps the system rating apart from the own decision', async () => {
    // AK10: Die Albumtauglichkeit steht an jedem Vorschlag als Text, das Kennzeichen „Gestrichen"
    // nur bei eigener Entscheidung.
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue({
      ...answer([3]),
      items: [
        photo(2, {
          ratings: [{ user_id: 7, username: USERNAME, status: 'rejected', favorite: false }],
        }),
        photo(3),
      ],
      total: 2,
    })

    renderBand()

    await screen.findByRole('button', { name: 'Tauschen: dir/3.jpg' })
    expect(screen.getAllByText('Gut albumtauglich')).toHaveLength(2)
    expect(screen.getAllByLabelText(ALBUM_STATE_LABELS.struck)).toHaveLength(1)
  })
})

describe('DraftAddPanel', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockResolvedValue('blob:fake-url')
  })

  it('stays unchanged: no order text, no marker, pages by quality without a reference', async () => {
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(answer([2, 3]))

    render(
      <ul>
        <DraftAddPanel
          id="panel"
          projectId={1}
          event={EVENT}
          eventName="Lyon"
          username={USERNAME}
          excludedIds={new Set()}
          onAdd={() => {}}
          busyIds={new Set()}
          error={null}
          onClose={() => {}}
        />
      </ul>,
      { wrapper },
    )

    await screen.findByRole('button', { name: 'Hinzufügen: dir/3.jpg' })
    expect(screen.queryByText(ALTERNATIVES_ORDER_TEXT)).toBeNull()
    expect(screen.queryByRole('list', { name: 'Alternativen, zeitlich geordnet' })).toBeNull()
    expect(photosApi.listDraftAlternatives).toHaveBeenCalledWith(1, {
      eventId: EVENT.id,
      limit: 8,
      offset: 0,
    })
  })
})
