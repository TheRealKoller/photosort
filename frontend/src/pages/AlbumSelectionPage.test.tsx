import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as albumSelectionApi from '../api/albumSelection'
import { ApiError } from '../api/client'
import type { AlbumSelectionOut, EventOut, PhotoOut } from '../api/types'
import { SELECTION_DECIDED_BADGE_TEXT } from '../components/SelectionPhotoTile'
import { SELECTION_NOTHING_CONTESTED_TEXT } from '../utils/albumSelection'
import { DRAFT_EMPTY_TEXT } from './AlbumDraftPage'
import { AlbumSelectionPage } from './AlbumSelectionPage'

vi.mock('../api/albumSelection')
vi.mock('../components/PhotoImage', () => ({
  PhotoImage: ({ alt }: { alt: string }) => <img alt={alt} />,
}))

function eventOut(overrides: Partial<EventOut> = {}): EventOut {
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
    ranking: null,
    criterion_scores: [],
    fine_labels: [],
    cloud_vision_status: [],
    final_selection_decision: null,
    in_final_selection: false,
    contested: false,
    event: eventOut(),
    ...overrides,
  }
}

function selection(overrides: Partial<AlbumSelectionOut> = {}): AlbumSelectionOut {
  return {
    participants: [
      { user_id: 1, username: 'daniel' },
      { user_id: 2, username: 'nora' },
    ],
    has_proposal: true,
    items: [],
    ...overrides,
  }
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  render(
    <MemoryRouter initialEntries={['/projects/1/selection']}>
      <Routes>
        <Route path="/projects/:projectId/selection" element={<AlbumSelectionPage />} />
      </Routes>
    </MemoryRouter>,
    { wrapper },
  )
}

/** Die Schaltflächen des Umschalters - sie tragen ihren Zustand über `aria-pressed`. */
function viewSwitch(label: 'Unterschiede' | 'Endauswahl') {
  return screen.getByRole('button', { name: label, exact: true })
}

/**
 * Die Folge der gerade sichtbaren Kacheln, abgelesen an den Haltungslisten.
 *
 * `queryAllByRole` und nicht `getAllByRole`: Die leere Sicht ist ein erwartetes Ergebnis dieser
 * Seite (Leerzustand B), und `getAllByRole` wuerfe dort, statt die leere Folge zu liefern.
 */
function visibleTileNames(): string[] {
  return screen
    .queryAllByRole('list')
    .filter((list) => list.getAttribute('aria-label')?.startsWith('Haltung zu '))
    .map((list) => list.getAttribute('aria-label')!.replace('Haltung zu ', ''))
}

beforeEach(() => {
  vi.mocked(albumSelectionApi.getAlbumSelection).mockReset()
  vi.mocked(albumSelectionApi.setAlbumDecision).mockReset()
})

describe('AlbumSelectionPage - die zwei Sichten', () => {
  it('opens on the WORKING view - that is where the work starts', async () => {
    vi.mocked(albumSelectionApi.getAlbumSelection).mockResolvedValue(
      selection({
        items: [
          photo({ id: 1, relative_path: 'strittig.jpg', contested: true }),
          photo({ id: 2, relative_path: 'drin.jpg', in_final_selection: true }),
        ],
      }),
    )

    renderPage()

    await waitFor(() => expect(visibleTileNames()).toEqual(['strittig.jpg']))
    expect(viewSwitch('Unterschiede')).toHaveAttribute('aria-pressed', 'true')
    expect(viewSwitch('Endauswahl')).toHaveAttribute('aria-pressed', 'false')
  })

  it('shows the whole selection in the result view, contested or not', async () => {
    vi.mocked(albumSelectionApi.getAlbumSelection).mockResolvedValue(
      selection({
        items: [
          photo({ id: 1, relative_path: 'strittig.jpg', contested: true }),
          photo({ id: 2, relative_path: 'einig.jpg', in_final_selection: true }),
          photo({
            id: 3,
            relative_path: 'entschieden-drin.jpg',
            in_final_selection: true,
            final_selection_decision: true,
          }),
          photo({
            id: 4,
            relative_path: 'heraus.jpg',
            in_final_selection: false,
            final_selection_decision: false,
          }),
        ],
      }),
    )
    renderPage()
    await waitFor(() => expect(visibleTileNames()).toEqual(['strittig.jpg']))

    await userEvent.click(viewSwitch('Endauswahl'))

    // Ein ausdruecklich HERAUSGENOMMENES Bild bleibt sichtbar - sonst waere die Entscheidung
    // entgegen dem Akzeptanzkriterium nicht mehr aenderbar. Das strittige steht NICHT darin.
    expect(visibleTileNames()).toEqual(['einig.jpg', 'entschieden-drin.jpg', 'heraus.jpg'])
  })

  it('neither switching nor deciding loads anything (Zusicherung 25)', async () => {
    vi.mocked(albumSelectionApi.getAlbumSelection).mockResolvedValue(
      selection({
        items: [
          photo({ id: 1, relative_path: 'strittig.jpg', contested: true }),
          photo({ id: 2, relative_path: 'einig.jpg', in_final_selection: true }),
          photo({ id: 3, relative_path: 'auch-einig.jpg', in_final_selection: true }),
        ],
      }),
    )
    vi.mocked(albumSelectionApi.setAlbumDecision).mockResolvedValue({
      photo_id: 1,
      included: true,
      updated_at: '2026-09-13T10:00:00',
    })
    renderPage()
    await waitFor(() => expect(visibleTileNames()).toEqual(['strittig.jpg']))

    await userEvent.click(viewSwitch('Endauswahl'))
    const orderBefore = visibleTileNames()
    await userEvent.click(viewSwitch('Unterschiede'))
    await userEvent.click(screen.getByRole('button', { name: 'Aufnehmen: strittig.jpg' }))
    await waitFor(() => expect(visibleTileNames()).toEqual([]))
    await userEvent.click(viewSwitch('Endauswahl'))

    // GENAU EIN Abruf ueber Umschalten und eine Entscheidung hinweg.
    expect(vi.mocked(albumSelectionApi.getAlbumSelection).mock.calls).toHaveLength(1)
    // Die Ergebnissicht ordnet sich dabei nicht um - das entschiedene Bild tritt an seiner
    // chronologischen Stelle hinzu, die uebrigen bleiben in ihrer Folge.
    expect(visibleTileNames()).toEqual(['strittig.jpg', ...orderBefore])
  })

  it('lets a decided photo leave the working view immediately', async () => {
    vi.mocked(albumSelectionApi.getAlbumSelection).mockResolvedValue(
      selection({
        items: [
          photo({ id: 1, relative_path: 'eins.jpg', contested: true }),
          photo({ id: 2, relative_path: 'zwei.jpg', contested: true }),
        ],
      }),
    )
    vi.mocked(albumSelectionApi.setAlbumDecision).mockResolvedValue({
      photo_id: 1,
      included: false,
      updated_at: '2026-09-13T10:00:00',
    })
    renderPage()
    await waitFor(() => expect(visibleTileNames()).toEqual(['eins.jpg', 'zwei.jpg']))

    await userEvent.click(screen.getByRole('button', { name: 'Nicht aufnehmen: eins.jpg' }))

    await waitFor(() => expect(visibleTileNames()).toEqual(['zwei.jpg']))
    expect(albumSelectionApi.setAlbumDecision).toHaveBeenCalledWith(1, false)
  })

  it('keeps both switches operable at all times - nothing locks the access', async () => {
    vi.mocked(albumSelectionApi.getAlbumSelection).mockResolvedValue(selection())
    renderPage()

    await waitFor(() => expect(viewSwitch('Endauswahl')).toBeEnabled())
    expect(viewSwitch('Unterschiede')).toBeEnabled()
    expect(viewSwitch('Unterschiede')).not.toHaveAttribute('disabled')
    expect(viewSwitch('Endauswahl')).not.toHaveAttribute('disabled')
  })
})

describe('AlbumSelectionPage - die beiden Leerzustände', () => {
  it('names the missing step with THE constant of the draft page, never a second sentence', async () => {
    // Zusicherung 26, ueber IDENTITAET mit der importierten Konstante geprueft: eine
    // Zeichenkettengleichheit bestuende auch gegen eine Kopie.
    vi.mocked(albumSelectionApi.getAlbumSelection).mockResolvedValue(
      selection({ has_proposal: false }),
    )

    renderPage()

    expect(await screen.findByText(DRAFT_EMPTY_TEXT)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Zur Kriterien-Bewertung' })).toHaveAttribute(
      'href',
      '/projects/1/pipeline/kriterien',
    )
    // Die beiden Leerzustaende sind GETRENNT und nie beide da.
    expect(screen.queryByText(SELECTION_NOTHING_CONTESTED_TEXT)).toBeNull()
  })

  it('says explicitly that nothing is open instead of leaving the working view blank', async () => {
    vi.mocked(albumSelectionApi.getAlbumSelection).mockResolvedValue(
      selection({ has_proposal: true, items: [photo({ id: 1, in_final_selection: true })] }),
    )

    renderPage()

    expect(await screen.findByText(SELECTION_NOTHING_CONTESTED_TEXT)).toBeInTheDocument()
    expect(screen.queryByText(DRAFT_EMPTY_TEXT)).toBeNull()
  })

  it('leads from "nothing open" to the result view', async () => {
    vi.mocked(albumSelectionApi.getAlbumSelection).mockResolvedValue(
      selection({
        has_proposal: true,
        items: [photo({ id: 1, relative_path: 'drin.jpg', in_final_selection: true })],
      }),
    )
    renderPage()
    await screen.findByText(SELECTION_NOTHING_CONTESTED_TEXT)

    await userEvent.click(screen.getByRole('button', { name: 'Zur Endauswahl' }))

    expect(visibleTileNames()).toEqual(['drin.jpg'])
    expect(screen.queryByText(SELECTION_NOTHING_CONTESTED_TEXT)).toBeNull()
  })
})

describe('AlbumSelectionPage - die drei Anzeigezustände der Ergebnissicht', () => {
  async function renderResultView(items: PhotoOut[]) {
    vi.mocked(albumSelectionApi.getAlbumSelection).mockResolvedValue(selection({ items }))
    renderPage()
    await waitFor(() => expect(viewSwitch('Endauswahl')).toBeEnabled())
    await userEvent.click(viewSwitch('Endauswahl'))
  }

  it('offers "Herausnehmen" and no extra marker when the two simply agree', async () => {
    await renderResultView([photo({ id: 1, relative_path: 'einig.jpg', in_final_selection: true })])

    expect(screen.getByRole('button', { name: 'Herausnehmen: einig.jpg' })).toBeInTheDocument()
    expect(screen.queryByText(SELECTION_DECIDED_BADGE_TEXT)).toBeNull()
  })

  it('marks a jointly decided photo and still offers "Herausnehmen"', async () => {
    // Einigkeit ist eine VORBELEGUNG, keine Sperre - auch ein entschiedenes Bild bleibt aenderbar.
    await renderResultView([
      photo({
        id: 1,
        relative_path: 'entschieden.jpg',
        in_final_selection: true,
        final_selection_decision: true,
      }),
    ])

    expect(screen.getByText(SELECTION_DECIDED_BADGE_TEXT)).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Herausnehmen: entschieden.jpg' }),
    ).toBeInTheDocument()
  })

  it('keeps a removed photo visible and offers "Aufnehmen"', async () => {
    await renderResultView([
      photo({
        id: 1,
        relative_path: 'heraus.jpg',
        in_final_selection: false,
        final_selection_decision: false,
      }),
    ])

    expect(screen.getByRole('button', { name: 'Aufnehmen: heraus.jpg' })).toBeInTheDocument()
  })

  it('takes an agreed photo out and puts it back - agreement is a default, not a lock', async () => {
    vi.mocked(albumSelectionApi.getAlbumSelection).mockResolvedValue(
      selection({
        items: [photo({ id: 1, relative_path: 'einig.jpg', in_final_selection: true })],
      }),
    )
    vi.mocked(albumSelectionApi.setAlbumDecision).mockResolvedValue({
      photo_id: 1,
      included: false,
      updated_at: '2026-09-13T10:00:00',
    })
    renderPage()
    await waitFor(() => expect(viewSwitch('Endauswahl')).toBeEnabled())
    await userEvent.click(viewSwitch('Endauswahl'))

    await userEvent.click(screen.getByRole('button', { name: 'Herausnehmen: einig.jpg' }))

    const back = await screen.findByRole('button', { name: 'Aufnehmen: einig.jpg' })
    vi.mocked(albumSelectionApi.setAlbumDecision).mockResolvedValue({
      photo_id: 1,
      included: true,
      updated_at: '2026-09-13T10:01:00',
    })
    await userEvent.click(back)

    expect(
      await screen.findByRole('button', { name: 'Herausnehmen: einig.jpg' }),
    ).toBeInTheDocument()
  })
})

describe('AlbumSelectionPage - ladend und fehlgeschlagen', () => {
  it('shows skeleton tiles while loading, and the switch stays usable', () => {
    vi.mocked(albumSelectionApi.getAlbumSelection).mockReturnValue(new Promise(() => {}))

    renderPage()

    expect(screen.getByRole('status', { name: 'Fotos werden geladen…' })).toBeInTheDocument()
    expect(viewSwitch('Endauswahl')).toBeEnabled()
  })

  it('shows the server detail in an alert whose retry triggers exactly ONE new request', async () => {
    vi.mocked(albumSelectionApi.getAlbumSelection).mockRejectedValue(
      new ApiError(500, 'Endauswahl nicht lesbar.'),
    )
    renderPage()
    expect(await screen.findByText('Endauswahl nicht lesbar.')).toBeInTheDocument()
    const callsBefore = vi.mocked(albumSelectionApi.getAlbumSelection).mock.calls.length

    await userEvent.click(screen.getByRole('button', { name: 'Erneut versuchen' }))

    await waitFor(() =>
      expect(vi.mocked(albumSelectionApi.getAlbumSelection).mock.calls.length).toBe(
        callsBefore + 1,
      ),
    )
  })
})

describe('AlbumSelectionPage - was hier nicht stehen darf', () => {
  it('renders no check symbol and no destructive button in any state', async () => {
    // Zusicherung 27, als ABWESENHEIT im gerenderten DOM geprueft.
    vi.mocked(albumSelectionApi.getAlbumSelection).mockResolvedValue(
      selection({
        items: [
          photo({
            id: 1,
            relative_path: 'strittig.jpg',
            contested: true,
            ratings: [
              { user_id: 2, username: 'nora', status: 'album_worthy', favorite: false },
              { user_id: 1, username: 'daniel', status: 'rejected', favorite: false },
            ],
          }),
          photo({
            id: 2,
            relative_path: 'entschieden.jpg',
            in_final_selection: true,
            final_selection_decision: true,
          }),
          photo({ id: 3, relative_path: 'heraus.jpg', final_selection_decision: false }),
        ],
      }),
    )
    renderPage()
    await waitFor(() => expect(visibleTileNames()).toEqual(['strittig.jpg']))

    for (const label of ['Endauswahl', 'Unterschiede'] as const) {
      await userEvent.click(viewSwitch(label))
      expect(document.querySelector('[data-icon="check"]')).toBeNull()
      expect(document.querySelector('button.bg-danger')).toBeNull()
    }
  })

  it('shows every participant by name on each tile, also the one who never touched anything', async () => {
    vi.mocked(albumSelectionApi.getAlbumSelection).mockResolvedValue(
      selection({
        items: [
          photo({
            id: 1,
            relative_path: 'strittig.jpg',
            contested: true,
            ratings: [{ user_id: 2, username: 'nora', status: 'album_worthy', favorite: false }],
          }),
        ],
      }),
    )
    renderPage()
    await waitFor(() => expect(visibleTileNames()).toEqual(['strittig.jpg']))

    const stances = within(screen.getByRole('list', { name: 'Haltung zu strittig.jpg' }))
    expect(stances.getAllByRole('listitem')).toHaveLength(2)
    expect(stances.getByText('daniel:')).toBeInTheDocument()
    expect(stances.getByText('nora:')).toBeInTheDocument()
  })
})
