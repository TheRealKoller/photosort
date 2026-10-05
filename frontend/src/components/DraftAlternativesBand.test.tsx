import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as photosApi from '../api/photos'
import type { DraftAlternativesOut, EventOut, PhotoOut } from '../api/types'
import { ALBUM_STATE_LABELS } from '../utils/albumStateLabels'
import {
  ALTERNATIVES_ORDER_TEXT,
  CANDIDATES_NONE_TEXT,
  DraftAddPanel,
  DraftAlternativesBand,
  REFERENCE_LATER_TEXT,
  SHOW_ALL_LABEL,
  SHOW_LESS_LABEL,
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
    seriesRest = 0,
  }: {
    offset?: number
    referenceIndex?: number | null
    total?: number
    seriesRest?: number
  } = {},
): DraftAlternativesOut {
  return {
    items: ids.map((id) => photo(id)),
    total,
    offset,
    reference_index: referenceIndex,
    series_rest: seriesRest,
  }
}

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

function renderBand(
  excludedIds: ReadonlySet<number> = new Set(),
  overrides: {
    onClose?: () => void
    onExchange?: (alternative: PhotoOut) => void
    onAdd?: (alternative: PhotoOut, neighborId: number | null) => void
    busyIds?: ReadonlySet<number>
    reference?: PhotoOut
  } = {},
) {
  return render(
    <ul>
      <DraftAlternativesBand
        id="band"
        projectId={1}
        photo={overrides.reference ?? photo(9)}
        username={USERNAME}
        excludedIds={excludedIds}
        onExchange={overrides.onExchange ?? (() => {})}
        onAdd={overrides.onAdd ?? (() => {})}
        busyIds={overrides.busyIds ?? new Set()}
        error={null}
        onClose={overrides.onClose ?? (() => {})}
      />
    </ul>,
    { wrapper },
  )
}

/** Die Serie (mit `series`) und die volle Reihe (seitenweise) getrennt beantworten. */
function mockSeriesAndRow(series: DraftAlternativesOut, ...rowPages: DraftAlternativesOut[]) {
  let rowCall = 0
  vi.mocked(photosApi.listDraftAlternatives).mockImplementation(async (_projectId, params) => {
    if (params.series === true) {
      return series
    }
    const page = rowPages[Math.min(rowCall, rowPages.length - 1)]
    rowCall += 1
    return page
  })
}

function rowCalls() {
  return vi
    .mocked(photosApi.listDraftAlternatives)
    .mock.calls.filter(([, params]) => params.series !== true)
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

  it('asks the server for the series window around THIS photo', async () => {
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(answer([2]))

    renderBand()

    await screen.findByRole('button', { name: 'Tauschen: dir/2.jpg' })
    expect(photosApi.listDraftAlternatives).toHaveBeenCalledTimes(1)
    expect(photosApi.listDraftAlternatives).toHaveBeenCalledWith(1, {
      eventId: EVENT.id,
      photoId: 9,
      series: true,
    })
  })

  it('offers "Tauschen" then "Hinzufügen" at every alternative and none at the marker', async () => {
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(
      answer([2, 3], { referenceIndex: 1 }),
    )

    renderBand()

    await screen.findByRole('button', { name: 'Tauschen: dir/2.jpg' })
    const list = screen.getByRole('list', { name: 'Alternativen, zeitlich geordnet' })
    const names = within(list)
      .getAllByRole('button')
      .map((button) => button.getAttribute('aria-label'))
    expect(names).toEqual([
      'Tauschen: dir/2.jpg',
      'Hinzufügen: dir/2.jpg',
      'Tauschen: dir/3.jpg',
      'Hinzufügen: dir/3.jpg',
    ])
    const marker = screen.getByRole('listitem', { name: 'Wird ersetzt: dir/9.jpg' })
    expect(within(marker).queryByRole('button')).toBeNull()
    expect(screen.getByRole('button', { name: 'Tauschen: dir/2.jpg' })).toHaveTextContent(
      /^Tauschen$/,
    )
    expect(screen.getByRole('button', { name: 'Hinzufügen: dir/2.jpg' })).toHaveTextContent(
      /^Hinzufügen$/,
    )
    expect(screen.getByRole('button', { name: 'Hinzufügen: dir/2.jpg' })).toHaveAttribute(
      'data-focus-key',
      'add-2',
    )
    expect(within(list).queryByText('+')).toBeNull()
  })

  it('passes the alternative and its neighbour to "Hinzufügen", the alternative to "Tauschen"', async () => {
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(answer([2, 3]))
    const onAdd = vi.fn()
    const onExchange = vi.fn()
    const user = userEvent.setup()

    renderBand(new Set(), { onAdd, onExchange })

    await user.click(await screen.findByRole('button', { name: 'Hinzufügen: dir/2.jpg' }))
    await user.click(screen.getByRole('button', { name: 'Tauschen: dir/3.jpg' }))

    expect(onAdd).toHaveBeenCalledWith(expect.objectContaining({ id: 2 }), 3)
    expect(onExchange).toHaveBeenCalledWith(expect.objectContaining({ id: 3 }))
  })

  it('locks both actions of a busy alternative and leaves the others usable', async () => {
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(answer([2, 3]))
    const onAdd = vi.fn()
    const user = userEvent.setup()

    renderBand(new Set(), { busyIds: new Set([2]), onAdd })

    const add = await screen.findByRole('button', { name: 'Hinzufügen: dir/2.jpg' })
    expect(add).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Tauschen: dir/2.jpg' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Hinzufügen: dir/3.jpg' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Tauschen: dir/3.jpg' })).toBeEnabled()
    await user.click(add)
    expect(onAdd).not.toHaveBeenCalled()
  })

  it('keeps a hostile file name as plain text in the names and creates no element', async () => {
    const hostile = '<img src=x onerror=alert(1)>.jpg'
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue({
      ...answer([]),
      items: [photo(2, { relative_path: hostile })],
      total: 1,
    })

    const { container } = renderBand()

    expect(await screen.findByRole('button', { name: `Tauschen: ${hostile}` })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: `Hinzufügen: ${hostile}` })).toBeInTheDocument()
    expect(container.querySelector('img[src="x"]')).toBeNull()
  })

  it('names the rest of the series only when there is one, singular and plural', async () => {
    const singular = '1 weitere Aufnahme dieser Serie unter „Alle Fotos des Events“.'
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(answer([2, 3]))
    const { unmount } = renderBand()
    await screen.findByRole('button', { name: 'Tauschen: dir/2.jpg' })
    expect(screen.queryByText(/weitere Aufnahme/)).toBeNull()
    unmount()

    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(answer([2, 3], { seriesRest: 1 }))
    const second = renderBand()
    expect(await screen.findByText(singular)).toBeInTheDocument()
    second.unmount()

    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(answer([2, 3], { seriesRest: 7 }))
    renderBand()
    expect(
      await screen.findByText('7 weitere Aufnahmen dieser Serie unter „Alle Fotos des Events“.'),
    ).toBeInTheDocument()
  })

  it('shows no rest hint for a value that is not a positive integer', async () => {
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(
      answer([2, 3], { seriesRest: 1.5 }),
    )

    renderBand()

    await screen.findByRole('button', { name: 'Tauschen: dir/2.jpg' })
    expect(screen.queryByText(/weitere Aufnahme/)).toBeNull()
  })

  it('has no toggle while the series loads and none for an empty series', async () => {
    let resolve: (value: DraftAlternativesOut) => void = () => {}
    vi.mocked(photosApi.listDraftAlternatives).mockReturnValue(
      new Promise((done) => {
        resolve = done
      }),
    )

    renderBand()

    expect(screen.getByRole('status', { name: 'Fotos werden geladen…' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: SHOW_ALL_LABEL })).toBeNull()
    resolve(answer([], { referenceIndex: 0 }))
    expect(await screen.findByText(CANDIDATES_NONE_TEXT)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: SHOW_ALL_LABEL })).toBeNull()
  })

  it('keeps the toggle when the series fails to load', async () => {
    vi.mocked(photosApi.listDraftAlternatives).mockRejectedValue(new Error('kaputt'))

    renderBand()

    expect(await screen.findByRole('button', { name: 'Erneut versuchen' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: SHOW_ALL_LABEL })).toBeInTheDocument()
  })

  it('expands the full row in place: lazily, without a dialog, scrolling or losing focus', async () => {
    mockSeriesAndRow(
      answer([3, 4], { offset: 1, referenceIndex: 2, total: 5, seriesRest: 2 }),
      answer([2, 3, 4, 5, 6], { referenceIndex: 2 }),
    )
    const scrollIntoView = vi.fn()
    const scrollTo = vi.fn()
    Element.prototype.scrollIntoView = scrollIntoView
    window.scrollTo = scrollTo
    const user = userEvent.setup()

    renderBand()

    const toggle = await screen.findByRole('button', { name: SHOW_ALL_LABEL })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(toggle).toHaveAttribute(
      'aria-controls',
      screen.getByRole('list', { name: 'Alternativen, zeitlich geordnet' }).id,
    )
    expect(rowCalls()).toHaveLength(0)

    await user.click(toggle)

    await screen.findByRole('button', { name: 'Tauschen: dir/6.jpg' })
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(toggle).toHaveTextContent(SHOW_LESS_LABEL)
    expect(toggle).toHaveFocus()
    expect(rowCalls()).toEqual([[1, { eventId: EVENT.id, photoId: 9, limit: 60, offset: 0 }]])
    expect(rowCells()).toEqual([
      'Tauschen: dir/2.jpg',
      'Tauschen: dir/3.jpg',
      'Wird ersetzt: dir/9.jpg',
      'Tauschen: dir/4.jpg',
      'Tauschen: dir/5.jpg',
      'Tauschen: dir/6.jpg',
    ])
    expect(screen.queryByText(/weitere Aufnahmen/)).toBeNull()
    expect(document.querySelector('[role="dialog"]')).toBeNull()

    await user.click(toggle)
    expect(toggle).toHaveTextContent(SHOW_ALL_LABEL)
    expect(toggle).toHaveFocus()
    expect(rowCells()).toEqual([
      'Tauschen: dir/3.jpg',
      'Wird ersetzt: dir/9.jpg',
      'Tauschen: dir/4.jpg',
    ])
    expect(screen.getByText(/2 weitere Aufnahmen/)).toBeInTheDocument()

    await user.click(toggle)
    await screen.findByRole('button', { name: 'Tauschen: dir/6.jpg' })
    expect(rowCalls()).toHaveLength(1)
    expect(
      vi.mocked(photosApi.listDraftAlternatives).mock.calls.filter(([, p]) => p.series === true),
    ).toHaveLength(1)
    expect(scrollIntoView).not.toHaveBeenCalled()
    expect(scrollTo).not.toHaveBeenCalled()
  })

  it('closes band and row together with Escape, also when expanded', async () => {
    mockSeriesAndRow(answer([3]), answer([2, 3]))
    const onClose = vi.fn()
    const user = userEvent.setup()

    renderBand(new Set(), { onClose })

    await user.click(await screen.findByRole('button', { name: SHOW_ALL_LABEL }))
    await screen.findByRole('button', { name: 'Tauschen: dir/2.jpg' })
    await user.keyboard('{Escape}')

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('loads the next page with "Weitere Fotos" and places the marker exactly once', async () => {
    // Grenzfall: `reference_index` faellt genau auf die Seitengrenze.
    // Solange eine weitere Seite folgt, steht die Marke NICHT am Ende von Seite 1.
    mockSeriesAndRow(
      answer([2], { referenceIndex: 1 }),
      answer([2], { referenceIndex: 1, total: 2 }),
      answer([3], { offset: 1, referenceIndex: 1, total: 2 }),
    )
    const user = userEvent.setup()

    renderBand()
    await user.click(await screen.findByRole('button', { name: SHOW_ALL_LABEL }))

    expect(await screen.findByText(REFERENCE_LATER_TEXT)).toBeInTheDocument()
    expect(screen.queryByRole('listitem', { name: /^Wird ersetzt/ })).toBeNull()

    await user.click(screen.getByRole('button', { name: 'Weitere Fotos' }))

    await screen.findByRole('button', { name: 'Tauschen: dir/3.jpg' })
    expect(rowCells()).toEqual([
      'Tauschen: dir/2.jpg',
      'Wird ersetzt: dir/9.jpg',
      'Tauschen: dir/3.jpg',
    ])
    expect(screen.queryByText(REFERENCE_LATER_TEXT)).toBeNull()
    expect(screen.queryByRole('button', { name: 'Weitere Fotos' })).toBeNull()
  })

  it('puts the marker on page one and at the end without a following page', async () => {
    mockSeriesAndRow(answer([2]), answer([2, 3], { referenceIndex: 1, total: 4 }))
    const user = userEvent.setup()

    renderBand()
    await user.click(await screen.findByRole('button', { name: SHOW_ALL_LABEL }))

    await screen.findByRole('button', { name: 'Tauschen: dir/3.jpg' })
    expect(rowCells()).toEqual([
      'Tauschen: dir/2.jpg',
      'Wird ersetzt: dir/9.jpg',
      'Tauschen: dir/3.jpg',
    ])
    expect(screen.getByRole('button', { name: 'Weitere Fotos' })).toBeInTheDocument()
  })

  it('puts the marker at the end of the last page', async () => {
    mockSeriesAndRow(answer([2]), answer([2, 3], { referenceIndex: 2 }))
    const user = userEvent.setup()

    renderBand()
    await user.click(await screen.findByRole('button', { name: SHOW_ALL_LABEL }))

    await screen.findByRole('button', { name: 'Tauschen: dir/3.jpg' })
    expect(rowCells()).toEqual([
      'Tauschen: dir/2.jpg',
      'Tauschen: dir/3.jpg',
      'Wird ersetzt: dir/9.jpg',
    ])
    expect(screen.queryByText(REFERENCE_LATER_TEXT)).toBeNull()
  })

  it('offers no "Weitere Fotos" in the series', async () => {
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(answer([2], { total: 30 }))

    renderBand()

    await screen.findByRole('button', { name: 'Tauschen: dir/2.jpg' })
    expect(screen.queryByRole('button', { name: 'Weitere Fotos' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Alle Alternativen' })).toBeNull()
  })

  it('names the order and puts the photo to be replaced between its neighbours', async () => {
    // Fenster ab `offset` 3, Bezugsbild an Stelle 5 der Reihe - also nach dem
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
    // Die Albumtauglichkeit steht an jedem Vorschlag als Text, das Kennzeichen „Gestrichen"
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
