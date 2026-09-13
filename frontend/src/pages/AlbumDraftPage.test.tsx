import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as motifsApi from '../api/motifs'
import * as photosApi from '../api/photos'
import * as projectsApi from '../api/projects'
import * as ratingsApi from '../api/ratings'
import type { EventOut, PhotoListOut, PhotoOut, ProjectOut, RankingOut } from '../api/types'
import { NOT_PROPOSED_BADGE_TEXT } from '../components/CurationPhotoTile'
import { PREVIOUSLY_IN_ALBUM_BADGE_TEXT } from '../components/DraftAlternativesDialog'
import { setToken } from '../auth/token'
import { MOTIF_SET } from '../test/motifSetFixture'
import {
  DRAFT_MOTIFS_NONE_TEXT,
  DRAFT_MOTIFS_UNASSESSED_TEXT,
  draftSizeText,
  formatDraftPhotoCount,
} from '../utils/albumDraft'
import {
  AlbumDraftPage,
  DRAFT_CLOUD_CONSENT_TEXT,
  DRAFT_EMPTY_EVENT_TEXT,
  DRAFT_EMPTY_TEXT,
} from './AlbumDraftPage'

vi.mock('../api/photos')
vi.mock('../api/projects')
vi.mock('../api/ratings')
vi.mock('../api/motifs')

function projectOut(overrides: Partial<ProjectOut> = {}): ProjectOut {
  return {
    id: 1,
    name: 'Costa Rica',
    opencloud_drive_id: 'drive-1',
    opencloud_path: '/CostaRica',
    created_at: '2026-07-01T10:00:00',
    last_scan: null,
    last_scoring_run: null,
    last_criterion_scoring_run: null,
    category_selection_enabled: false,
    cloud_vision_detection_enabled: true,
    cloud_vision_consent_at: '2026-07-01T10:00:00',
    selection_target: 1,
    effective_selection_target: 1,
    ...overrides,
  }
}

function makeToken(payload: unknown): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
  const body = btoa(JSON.stringify(payload))
  return `${header}.${body}.signature-irrelevant`
}

function ranking(overrides: Partial<RankingOut> = {}): RankingOut {
  return {
    event_id: 1,
    rank_score: 0.8,
    rank_position: 1,
    proposed: true,
    partition_size: 1,
    curation_position: 1,
    ...overrides,
  }
}

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
    ranking: ranking(),
    criterion_scores: [],
    fine_labels: [],
    cloud_vision_status: [],
    final_selection_decision: null,
    in_final_selection: false,
    contested: false,
    motif_assessment: {
      source: 'cloud' as const,
      provider: 'anthropic',
      excluded_document: false,
      computed_at: '2026-07-21T09:00:00',
    },
    // `present: false` als Grundzustand, NICHT aus `strength` abgeleitet: Die Motivmischung liest
    // ausschliesslich die Serveraussage, und ein Aufbau, der beide koppelt, sieht eine Oberflaeche
    // nicht, die doch selbst vergleicht.
    motifs: MOTIF_SET.items.map((item) => ({
      key: item.key,
      strength: 0.5,
      correction: null,
      present: false,
    })),
    album_suitability: { level: 4, reason: 'Alle schauen in die Kamera.' },
    event: eventOut(),
    ...overrides,
  }
}

/** Die eigene Bewertungszeile - die Ansicht liest sie ausschliesslich ueber `ownRatingStatus`. */
function ownRating(status: 'album_worthy' | 'rejected') {
  return { user_id: 7, username: 'daniel', status, favorite: false }
}

function listOut(items: PhotoOut[], total = items.length): PhotoListOut {
  return { items, total }
}

function renderPage(initialPath = '/projects/1/album') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return {
    ...render(
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/projects/:projectId/pipeline/:step" element={<p>Pipeline-Schritt</p>} />
          <Route path="/projects/:projectId/album" element={<AlbumDraftPage />} />
        </Routes>
      </MemoryRouter>,
      { wrapper },
    ),
    queryClient,
  }
}

/** Die Zahl der Abrufe der Entwurfsliste - Grundlage der Durchsatz-Zusicherung. */
function draftCalls(): number {
  return vi.mocked(photosApi.listPhotos).mock.calls.filter(([, params]) => params?.draft === true)
    .length
}

describe('AlbumDraftPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    setToken(makeToken({ sub: '7', username: 'daniel' }))
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockResolvedValue('blob:fake-url')
    vi.mocked(motifsApi.listMotifs).mockResolvedValue(MOTIF_SET)
    vi.mocked(projectsApi.getProject).mockResolvedValue(projectOut())
    vi.stubGlobal(
      'matchMedia',
      vi.fn().mockReturnValue({
        matches: false,
        media: '(hover: hover) and (pointer: fine)',
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      }),
    )
  })

  it('is called "Album-Entwurf"', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue(listOut([]))

    renderPage()

    const heading = await screen.findByRole('heading', { level: 1 })
    expect(heading).toHaveTextContent('Album-Entwurf')
    expect(heading.textContent).not.toContain('Kuratierung')
  })

  it('asks for the draft of the asking user', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue(listOut([]))

    renderPage()

    await waitFor(() => expect(photosApi.listPhotos).toHaveBeenCalledWith(1, { draft: true }))
  })

  it('groups the photos by day and event and counts each event', async () => {
    const morning = eventOut({ id: 10, position: 1, started_at: '2026-07-20T09:00:00' })
    const nextDay = eventOut({ id: 12, position: 2, started_at: '2026-07-21T09:00:00' })
    vi.mocked(photosApi.listPhotos).mockResolvedValue(
      listOut([
        photo({ id: 1, relative_path: 'a.jpg', event: morning }),
        photo({ id: 2, relative_path: 'b.jpg', event: morning }),
        photo({ id: 3, relative_path: 'c.jpg', event: nextDay }),
      ]),
    )

    renderPage()

    await waitFor(() => expect(screen.getAllByRole('heading', { level: 2 })).toHaveLength(2))
    expect(screen.getAllByRole('heading', { level: 3 })).toHaveLength(2)
    expect(screen.getByText(`(${formatDraftPhotoCount(2)})`)).toBeInTheDocument()
    expect(screen.getByLabelText('Im Album: a.jpg')).toBeInTheDocument()
    expect(screen.getByLabelText('Im Album: c.jpg')).toBeInTheDocument()
  })

  describe('der Kopfbereich', () => {
    it('names the actual count and the target next to each other', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        projectOut({ selection_target: 3, effective_selection_target: 3 }),
      )
      vi.mocked(photosApi.listPhotos).mockResolvedValue(listOut([photo({ id: 1 })]))

      renderPage()

      expect(await screen.findByText(draftSizeText(1, 3))).toBeInTheDocument()
    })

    it.each([
      { label: 'nach unten', target: 10, ids: [1] },
      { label: 'nach oben', target: 1, ids: [1, 2] },
    ])(
      'gives the deviation $label no error optics and no adjusting control',
      async ({ target, ids }) => {
        // Der Richtwert ist ein ZIEL und keine Obergrenze - in BEIDEN Richtungen ein neutraler
        // Hinweis. Ein Schalter, der die Anzahl angliche, machte daraus einen Fehlerzustand.
        vi.mocked(projectsApi.getProject).mockResolvedValue(
          projectOut({ selection_target: target, effective_selection_target: target }),
        )
        vi.mocked(photosApi.listPhotos).mockResolvedValue(
          listOut(ids.map((id) => photo({ id, relative_path: `${id}.jpg` }))),
        )

        const { container } = renderPage()

        const hint = await screen.findByText(draftSizeText(ids.length, target))
        expect(screen.queryByRole('alert')).toBeNull()
        expect(hint.closest('[role="alert"]')).toBeNull()
        expect(container.querySelectorAll('[class*="danger"]')).toHaveLength(0)
        expect(screen.queryByRole('button', { name: /angleichen|anpassen|auffüllen/i })).toBeNull()
        // Und keine ausgehende Anfrage, die den Vorschlag aendert.
        expect(projectsApi.setSelectionTarget).not.toHaveBeenCalled()
      },
    )

    it('names the effective target when none is set', async () => {
      // Nie eine leere Stelle: der wirksame Wert steht dort, auch ohne eingestellten Richtwert.
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        projectOut({ selection_target: null, effective_selection_target: 12 }),
      )
      vi.mocked(photosApi.listPhotos).mockResolvedValue(listOut([photo({ id: 1 })]))

      renderPage()

      expect(await screen.findByText(draftSizeText(1, 12))).toBeInTheDocument()
    })
  })

  describe('die Zustaende', () => {
    it('shows a skeleton grid while loading', () => {
      vi.mocked(photosApi.listPhotos).mockReturnValue(new Promise(() => {}))

      renderPage()

      expect(screen.getByRole('status')).toBeInTheDocument()
    })

    it('shows an error alert whose retry triggers exactly one new request', async () => {
      vi.mocked(photosApi.listPhotos).mockRejectedValue(new ApiError(500, 'Serverfehler'))

      renderPage()

      expect(await screen.findByText('Serverfehler')).toBeInTheDocument()
      const before = draftCalls()
      await userEvent.click(screen.getByRole('button', { name: 'Erneut versuchen' }))

      await waitFor(() => expect(draftCalls()).toBe(before + 1))
    })

    it('names the missing step and links it instead of staying empty', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue(listOut([]))

      renderPage()

      expect(await screen.findByText(DRAFT_EMPTY_TEXT)).toBeInTheDocument()
      expect(screen.getByRole('link', { name: /kriterien-bewertung/i })).toHaveAttribute(
        'href',
        '/projects/1/pipeline/kriterien',
      )
    })

    it('names the missing cloud approval instead of the missing run', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        projectOut({ cloud_vision_detection_enabled: false }),
      )
      vi.mocked(photosApi.listPhotos).mockResolvedValue(listOut([]))

      renderPage()

      expect(await screen.findByText(DRAFT_CLOUD_CONSENT_TEXT)).toBeInTheDocument()
      expect(screen.queryByText(DRAFT_EMPTY_TEXT)).toBeNull()
      expect(screen.queryByRole('alert')).toBeNull()
    })

    it('keeps an emptied event group standing with its heading', async () => {
      // Ein leergeraeumtes Event verschwindet nicht kommentarlos - die Gruppe bleibt mit ihrer
      // Bezeichnung stehen und sagt, dass gerade kein Bild darin ist.
      const first = eventOut({ id: 10, position: 1 })
      vi.mocked(photosApi.listPhotos)
        .mockResolvedValueOnce(listOut([photo({ id: 1, event: first })]))
        .mockResolvedValue(listOut([]))

      const { queryClient } = renderPage()
      await screen.findByLabelText('Im Album: a.jpg')

      await queryClient.refetchQueries({ queryKey: ['photos', 1, 'draft'] })

      expect(await screen.findByText(DRAFT_EMPTY_EVENT_TEXT)).toBeInTheDocument()
      expect(screen.getAllByRole('heading', { level: 3 })).toHaveLength(1)
    })
  })

  describe('die Entscheidung', () => {
    it('strikes a photo without reloading the draft and without moving the tiles', async () => {
      // Zusicherung 22: genau EIN Abruf der Entwurfsliste ueber den Klick hinweg, und die Id-Folge
      // der Kacheln ist vorher wie nachher dieselbe. Ohne das risse die breite Invalidierung das
      // gerade gestrichene Bild aus der Liste.
      vi.mocked(photosApi.listPhotos).mockResolvedValue(
        listOut([
          photo({ id: 1, relative_path: 'a.jpg' }),
          photo({ id: 2, relative_path: 'b.jpg' }),
        ]),
      )
      vi.mocked(ratingsApi.setRating).mockResolvedValue({
        photo_id: 1,
        user_id: 7,
        status: 'rejected',
        favorite: false,
        updated_at: '2026-09-13T10:00:00',
      })

      renderPage()
      await screen.findByLabelText('Im Album: a.jpg')
      const before = screen.getAllByRole('button', { name: /\.jpg$/ }).map((b) => b.textContent)
      const callsBefore = draftCalls()

      await userEvent.click(screen.getByLabelText('Im Album: a.jpg'))

      await waitFor(() => expect(ratingsApi.setRating).toHaveBeenCalledWith(1, 'rejected'))
      // Die Kachel bleibt an ihrer Stelle und wechselt nur ihren Zustand.
      expect(await screen.findByLabelText('Gestrichen: a.jpg')).toBeInTheDocument()
      expect(screen.getAllByRole('button', { name: /\.jpg$/ })).toHaveLength(before.length)
      expect(screen.getByLabelText('Im Album: b.jpg')).toBeInTheDocument()
      expect(draftCalls()).toBe(callsBefore)
    })

    it('takes a struck photo back into the album', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue(
        listOut([photo({ id: 1, ratings: [ownRating('rejected')] })]),
      )
      vi.mocked(ratingsApi.setRating).mockResolvedValue({
        photo_id: 1,
        user_id: 7,
        status: 'album_worthy',
        favorite: false,
        updated_at: '2026-09-13T10:00:00',
      })

      renderPage()

      await userEvent.click(await screen.findByLabelText('Gestrichen: a.jpg'))

      await waitFor(() => expect(ratingsApi.setRating).toHaveBeenCalledWith(1, 'album_worthy'))
      expect(await screen.findByLabelText('Im Album: a.jpg')).toBeInTheDocument()
    })

    it('decides each photo independently while another decision is still running', async () => {
      // Eine MENGE laufender Mutationen, nicht eine einzelne Id: ein zweiter Druck auf ein
      // ANDERES Foto darf nicht verpuffen, waehrend die erste Entscheidung noch laeuft.
      vi.mocked(photosApi.listPhotos).mockResolvedValue(
        listOut([
          photo({ id: 1, relative_path: 'a.jpg' }),
          photo({ id: 2, relative_path: 'b.jpg' }),
        ]),
      )
      vi.mocked(ratingsApi.setRating).mockImplementation((photoId) =>
        photoId === 1
          ? new Promise(() => {})
          : Promise.resolve({
              photo_id: photoId,
              user_id: 7,
              status: 'rejected' as const,
              favorite: false,
              updated_at: '2026-09-13T10:00:00',
            }),
      )

      renderPage()
      await userEvent.click(await screen.findByLabelText('Im Album: a.jpg'))
      await userEvent.click(screen.getByLabelText('Im Album: b.jpg'))

      await waitFor(() => expect(ratingsApi.setRating).toHaveBeenCalledWith(2, 'rejected'))
    })
  })

  describe('der Austausch', () => {
    /** Die Bewertungsantwort des Servers zu einem der beiden Schreibvorgänge. */
    function written(photoId: number, status: 'album_worthy' | 'rejected') {
      return {
        photo_id: photoId,
        user_id: 7,
        status,
        favorite: false,
        updated_at: '2026-09-13T10:00:00',
      }
    }

    /** Die Antwort des Austausch-Endpunkts: beide geschriebenen Zeilen in einer Antwort. */
    function exchangeAnswer(takenId: number, struckId: number) {
      return { taken: written(takenId, 'album_worthy'), struck: written(struckId, 'rejected') }
    }

    it('asks for alternatives only once the dialog is opened - never one query per tile', async () => {
      // Die Durchsatz-Zusage der Ansicht: Bei hundert Kacheln liefe sonst hundertmal derselbe
      // Endpunkt, bevor jemand auch nur einen Austausch angefangen hat.
      vi.mocked(photosApi.listPhotos).mockResolvedValue(
        listOut([
          photo({ id: 1, relative_path: 'a.jpg' }),
          photo({ id: 2, relative_path: 'b.jpg' }),
        ]),
      )
      vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(listOut([]))

      renderPage()
      await screen.findByLabelText('Alternativen: a.jpg')
      expect(photosApi.listDraftAlternatives).not.toHaveBeenCalled()

      await userEvent.click(screen.getByLabelText('Alternativen: a.jpg'))

      await waitFor(() => expect(photosApi.listDraftAlternatives).toHaveBeenCalledTimes(1))
      expect(photosApi.listDraftAlternatives).toHaveBeenCalledWith(1, {
        eventId: 1,
        photoId: 1,
        limit: expect.any(Number) as number,
        offset: 0,
      })
    })

    it('exchanges in ONE write, closes the dialog and shows BOTH photos', async () => {
      // Das Akzeptanzkriterium des Austauschs: das neue Bild als „Im Album", das ersetzte an
      // seiner Stelle als „Gestrichen". Es rückt nichts nach und es entsteht keine Lücke - und
      // die Entwurfsliste wird dabei NICHT neu geladen.
      //
      // Umgeschrieben mit Spec 0432: EIN Aufruf statt zweier. Die negative Assertion trägt den
      // Fall - ein stehengebliebener Doppelschreibweg sähe an der Oberfläche identisch aus und
      // erzeugte serverseitig drei Ereignisse statt einem.
      vi.mocked(photosApi.listPhotos).mockResolvedValue(
        listOut([photo({ id: 1, relative_path: 'a.jpg', taken_at: '2026-07-20T10:00:00' })]),
      )
      vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(
        listOut([photo({ id: 2, relative_path: 'b.jpg', taken_at: '2026-07-20T10:30:00' })]),
      )
      vi.mocked(photosApi.exchangeDraftPhoto).mockResolvedValue(exchangeAnswer(2, 1))

      renderPage()
      await userEvent.click(await screen.findByLabelText('Alternativen: a.jpg'))
      const callsBefore = draftCalls()

      await userEvent.click(await screen.findByLabelText('Austauschen gegen: b.jpg'))

      await waitFor(() =>
        expect(vi.mocked(photosApi.exchangeDraftPhoto).mock.calls).toEqual([[1, 2, 1]]),
      )
      expect(ratingsApi.setRating).not.toHaveBeenCalled()
      expect(await screen.findByLabelText('Gestrichen: a.jpg')).toBeInTheDocument()
      expect(screen.getByLabelText('Im Album: b.jpg')).toBeInTheDocument()
      expect(screen.queryByLabelText('Austauschen gegen: b.jpg')).toBeNull()
      expect(draftCalls()).toBe(callsBefore)
    })

    it('puts the focus onto the tile that now stands in that place', async () => {
      // Nicht zurück auf die auslösende Schaltfläche: Das Bild, das dort stand, ist gerade
      // gestrichen worden, und die Arbeit geht an der neuen Kachel weiter.
      vi.mocked(photosApi.listPhotos).mockResolvedValue(
        listOut([photo({ id: 1, relative_path: 'a.jpg' })]),
      )
      vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(
        listOut([photo({ id: 2, relative_path: 'b.jpg', taken_at: '2026-07-20T10:30:00' })]),
      )
      vi.mocked(photosApi.exchangeDraftPhoto).mockResolvedValue(exchangeAnswer(2, 1))

      renderPage()
      await userEvent.click(await screen.findByLabelText('Alternativen: a.jpg'))
      await userEvent.click(await screen.findByLabelText('Austauschen gegen: b.jpg'))

      await waitFor(() => expect(screen.getByLabelText('Im Album: b.jpg')).toHaveFocus())
    })

    it('is reversible: the replaced photo returns as "zuvor im Album" and both rows go back', async () => {
      // Kein eigener Rückgängig-Knopf und kein Verlauf: Das ersetzte Bild steht wieder unter den
      // Alternativen, und ein Druck darauf ist derselbe Austausch in die andere Richtung.
      const replaced = photo({ id: 1, relative_path: 'a.jpg', taken_at: '2026-07-20T10:00:00' })
      const chosen = photo({ id: 2, relative_path: 'b.jpg', taken_at: '2026-07-20T10:30:00' })
      vi.mocked(photosApi.listPhotos).mockResolvedValue(listOut([replaced]))
      vi.mocked(photosApi.listDraftAlternatives)
        .mockResolvedValueOnce(listOut([chosen]))
        .mockResolvedValue(listOut([{ ...replaced, ratings: [ownRating('rejected')] }]))
      vi.mocked(photosApi.exchangeDraftPhoto).mockImplementation((_projectId, takenId, struckId) =>
        Promise.resolve(exchangeAnswer(takenId, struckId)),
      )

      renderPage()
      await userEvent.click(await screen.findByLabelText('Alternativen: a.jpg'))
      await userEvent.click(await screen.findByLabelText('Austauschen gegen: b.jpg'))
      await screen.findByLabelText('Im Album: b.jpg')

      await userEvent.click(screen.getByLabelText('Alternativen: b.jpg'))
      expect(await screen.findByText(PREVIOUSLY_IN_ALBUM_BADGE_TEXT)).toBeInTheDocument()
      await userEvent.click(screen.getByLabelText('Austauschen gegen: a.jpg'))

      // Beide Zeilen zurück: das zurückgeholte Bild ist wieder im Album, das eingewechselte
      // gestrichen. Serverseitig ist die Umkehr ein ZWEITER Austausch mit eigenem Ereignis, der
      // den ersten nicht löscht (ADR 0100 Punkt 3) - hier zählen die zwei Aufrufe.
      expect(await screen.findByLabelText('Im Album: a.jpg')).toBeInTheDocument()
      expect(screen.getByLabelText('Gestrichen: b.jpg')).toBeInTheDocument()
      expect(vi.mocked(photosApi.exchangeDraftPhoto).mock.calls).toEqual([
        [1, 2, 1],
        [1, 1, 2],
      ])
    })
  })

  it('marks both data forms of "taken but no longer proposed" identically', async () => {
    // Zusicherung 23: `ranking: null` (aussortiert) und `ranking.proposed: false` (Kandidat, nicht
    // gewaehlt) bedeuten dasselbe - beide Kacheln tragen dieselbe Kennzeichnung.
    vi.mocked(photosApi.listPhotos).mockResolvedValue(
      listOut([
        photo({
          id: 1,
          relative_path: 'a.jpg',
          ranking: null,
          ratings: [ownRating('album_worthy')],
        }),
        photo({
          id: 2,
          relative_path: 'b.jpg',
          ranking: ranking({ proposed: false }),
          ratings: [ownRating('album_worthy')],
        }),
        photo({ id: 3, relative_path: 'c.jpg' }),
      ]),
    )

    renderPage()

    await screen.findByLabelText('Im Album: a.jpg')
    expect(screen.getAllByText(NOT_PROPOSED_BADGE_TEXT)).toHaveLength(2)
  })

  describe('die Motivmischung am Event', () => {
    /** Ein Achter-Vektor, in dem genau die genannten Motive getragen werden. */
    function motifsWith(present: string[]) {
      return MOTIF_SET.items.map((item) => ({
        key: item.key,
        strength: 0.5,
        correction: null,
        present: present.includes(item.key),
      }))
    }

    it('names the motifs of the group alphabetically and without a number', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue(
        listOut([
          photo({ id: 1, relative_path: 'a.jpg', motifs: motifsWith(['menschen']) }),
          photo({
            id: 2,
            relative_path: 'b.jpg',
            motifs: motifsWith(['bauwerk_sehenswuerdigkeit']),
          }),
        ]),
      )

      renderPage()

      const line = await screen.findByText('Bauwerk und Sehenswürdigkeit, Menschen')
      expect(line.textContent).not.toMatch(/\d/)
    })

    it('drops a motif as soon as its last carrier is struck - without reloading', async () => {
      // Zusicherung 22 in ihrer sichtbaren Folge: Die Zeile entsteht aus den bereits geladenen
      // Kacheln, nicht aus einer Serveraggregation - eine solche waere nach jedem Handgriff
      // veraltet und naennte ein Motiv, das kein Bild der Gruppe mehr traegt.
      vi.mocked(photosApi.listPhotos).mockResolvedValue(
        listOut([
          photo({ id: 1, relative_path: 'a.jpg', motifs: motifsWith(['menschen']) }),
          photo({ id: 2, relative_path: 'b.jpg', motifs: motifsWith(['tiere']) }),
        ]),
      )
      vi.mocked(ratingsApi.setRating).mockResolvedValue({
        photo_id: 2,
        user_id: 7,
        status: 'rejected',
        favorite: false,
        updated_at: '2026-09-13T10:00:00',
      })

      renderPage()
      await screen.findByText('Menschen, Tiere')
      const callsBefore = draftCalls()

      await userEvent.click(screen.getByLabelText('Im Album: b.jpg'))

      expect(await screen.findByText('Menschen')).toBeInTheDocument()
      expect(screen.queryByText('Menschen, Tiere')).toBeNull()
      expect(draftCalls()).toBe(callsBefore)
    })

    it('says "not yet assessed" for a group without any classified photo', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue(
        listOut([photo({ id: 1, motif_assessment: null, motifs: [] })]),
      )

      renderPage()

      expect(await screen.findByText(DRAFT_MOTIFS_UNASSESSED_TEXT)).toBeInTheDocument()
    })

    it('shows no motif line in an emptied event group', async () => {
      const first = eventOut({ id: 10, position: 1 })
      vi.mocked(photosApi.listPhotos)
        .mockResolvedValueOnce(listOut([photo({ id: 1, event: first })]))
        .mockResolvedValue(listOut([]))

      const { queryClient } = renderPage()
      await screen.findByLabelText('Im Album: a.jpg')

      await queryClient.refetchQueries({ queryKey: ['photos', 1, 'draft'] })

      expect(await screen.findByText(DRAFT_EMPTY_EVENT_TEXT)).toBeInTheDocument()
      expect(screen.queryByText(DRAFT_MOTIFS_UNASSESSED_TEXT)).toBeNull()
      expect(screen.queryByText(DRAFT_MOTIFS_NONE_TEXT)).toBeNull()
    })
  })

  it('collapses and expands a day', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue(listOut([photo({ id: 1 })]))

    renderPage()

    const trigger = await screen.findByRole('button', { expanded: true })
    await userEvent.click(trigger)

    expect(screen.getByRole('button', { expanded: false })).toBeInTheDocument()
    expect(screen.queryByLabelText('Im Album: a.jpg')).toBeNull()
  })
})
