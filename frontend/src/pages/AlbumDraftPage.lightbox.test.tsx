/*
 * Entwurfsseite - Teil: Grossansicht und Leerzustaende (Spec 0651; gemeinsamer Unterbau in src/test/albumDraftPage.tsx).
 */
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import type { InitialEntry, Location, NavigateFunction } from 'react-router'
import { Route, Routes, useLocation, useNavigate } from 'react-router'
import { ApiError } from '../api/client'
import * as photosApi from '../api/photos'
import * as projectsApi from '../api/projects'
import * as ratingsApi from '../api/ratings'
import type { AlbumDraftOut, ModelChoiceOut, ProjectOut } from '../api/types'
import {
  DRAFT_CLOUD_CONSENT_TEXT,
  DRAFT_EMPTY_TEXT,
  DRAFT_EYE_DISABLED_TEXT,
  SETTINGS_LINK_LABEL,
} from '../utils/albumDraftTexts'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  projectOut,
  EVENT_A,
  photo,
  PLENTY_OF_CANDIDATES,
  renderPage,
  noObserver,
  resetAlbumDraftMocks,
} from '../test/albumDraftPage'
import { makeQueryClient, withProviders } from '../test/render'
import { AlbumDraftPage } from './AlbumDraftPage'

vi.mock('../api/photos')
vi.mock('../api/projects')
vi.mock('../api/ratings')
vi.mock('../api/motifs')
vi.mock('../api/persons')

beforeEach(() => {
  resetAlbumDraftMocks()
})

/*
 * specs/features/0531-kuratierung-grossansicht.md - die Großansicht in der Seite. Vor der Seite
 * liegt eine Stub-Route als Verlaufssonde: Jeder Fall endet mit einem
 * Zurück, das dort ankommen muss - so fällt ein verwaister oder überzähliger Verlaufseintrag auf.
 * Geöffnet wird über `fireEvent.click`, das (wie Safari) den Button NICHT fokussiert.
 */
describe('AlbumDraftPage: Großansicht', () => {
  const probe: { location?: Location; navigate?: NavigateFunction } = {}

  function Probe() {
    probe.location = useLocation()
    probe.navigate = useNavigate()
    return null
  }

  function renderWithHistory(
    draft: AlbumDraftOut | null,
    entry: InitialEntry = '/projects/1/album',
  ) {
    if (draft !== null) {
      vi.mocked(photosApi.getAlbumDraft).mockResolvedValue(draft)
    }
    const queryClient = makeQueryClient()
    render(
      withProviders(
        <>
          <Probe />
          <Routes>
            <Route path="/stub" element={<p>Stub</p>} />
            <Route
              path="/projects/:projectId/album"
              element={<AlbumDraftPage createPositionObserver={noObserver} />}
            />
          </Routes>
        </>,
        { queryClient, initialEntries: ['/stub', entry], initialIndex: 1 },
      ),
    )
    return queryClient
  }

  function back(): void {
    act(() => {
      void probe.navigate!(-1)
    })
  }

  function writeCalls(): number {
    return (
      vi.mocked(ratingsApi.setRating).mock.calls.length +
      vi.mocked(ratingsApi.deleteRating).mock.calls.length +
      vi.mocked(ratingsApi.setFavorite).mock.calls.length +
      vi.mocked(photosApi.exchangeDraftPhoto).mock.calls.length +
      vi.mocked(photosApi.undoDraftExchange).mock.calls.length +
      vi.mocked(photosApi.setMotifCorrection).mock.calls.length +
      vi.mocked(photosApi.deleteMotifCorrection).mock.calls.length
    )
  }

  const twoPhotos: AlbumDraftOut = {
    events: [EVENT_A],
    items: [photo(1, { relative_path: 'reise/a.jpg' }), photo(2, { relative_path: 'reise/b.jpg' })],
    eligible_candidate_count: PLENTY_OF_CANDIDATES,
  }

  const closeWays: [string, () => void][] = [
    ['Schließen', () => fireEvent.click(screen.getByRole('button', { name: 'Schließen' }))],
    ['Escape', () => fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })],
    [
      'Klick neben das Bild',
      () => {
        const stage = screen.getByTestId('lightbox-stage')
        fireEvent.pointerDown(stage)
        fireEvent.click(stage)
      },
    ],
    ['Browser-Zurück', back],
  ]

  it.each(closeWays)(
    'opens exactly the clicked photo and closes via %s back to the same place',
    async (_, closeLightbox) => {
      renderWithHistory(twoPhotos)
      const trigger = await screen.findByRole('button', { name: 'Großansicht: reise/b.jpg' })

      fireEvent.click(trigger)

      expect(screen.getByRole('dialog', { name: 'b.jpg' })).toBeInTheDocument()
      expect(probe.location).toMatchObject({
        pathname: '/projects/1/album',
        state: { grossansicht: 2 },
      })

      closeLightbox()

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      expect(trigger).toHaveFocus()
      expect(trigger.isConnected).toBe(true)
      expect(screen.getByRole('button', { name: 'Streichen: reise/b.jpg' })).toBeInTheDocument()
      expect(photosApi.getAlbumDraft).toHaveBeenCalledTimes(1)
      expect(writeCalls()).toBe(0)
      expect(probe.location).toMatchObject({ pathname: '/projects/1/album', state: null })
      back()
      expect(probe.location?.pathname).toBe('/stub')
    },
  )

  it('starts with collapsed details on every opening', async () => {
    renderWithHistory(twoPhotos)

    fireEvent.click(await screen.findByRole('button', { name: 'Großansicht: reise/a.jpg' }))
    fireEvent.click(screen.getByRole('button', { name: 'Details' }))
    fireEvent.click(screen.getByRole('button', { name: 'Schließen' }))
    fireEvent.click(screen.getByRole('button', { name: 'Großansicht: reise/b.jpg' }))

    expect(screen.getByRole('button', { name: 'Details' })).toHaveAttribute(
      'aria-expanded',
      'false',
    )
  })

  it('reopens the photo after a reload once the draft has loaded', async () => {
    let resolveDraft: (draft: AlbumDraftOut) => void = () => {}
    vi.mocked(photosApi.getAlbumDraft).mockReturnValue(
      new Promise((resolve) => {
        resolveDraft = resolve
      }),
    )
    renderWithHistory(null, { pathname: '/projects/1/album', state: { grossansicht: 2 } })

    await screen.findByRole('status', { name: 'Fotos werden geladen…' })
    expect(probe.location?.state).toEqual({ grossansicht: 2 })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    await act(async () => {
      resolveDraft(twoPhotos)
    })

    expect(await screen.findByRole('dialog', { name: 'b.jpg' })).toBeInTheDocument()
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })
    expect(screen.getByRole('button', { name: 'Großansicht: reise/b.jpg' })).toHaveFocus()
    expect(probe.location?.state).toBeNull()
    back()
    expect(probe.location?.pathname).toBe('/stub')
  })

  it('shows nothing and clears the entry when the reloaded photo is not in the draft', async () => {
    renderWithHistory(twoPhotos, { pathname: '/projects/1/album', state: { grossansicht: 99 } })

    await screen.findByRole('button', { name: 'Großansicht: reise/a.jpg' })

    await waitFor(() => expect(probe.location?.state).toBeNull())
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(photosApi.fetchPhotoImageBlobUrl).not.toHaveBeenCalledWith(99, 'display')
    back()
    expect(probe.location?.pathname).toBe('/stub')
  })

  it('closes without a leftover entry and focuses the heading when the photo disappears', async () => {
    const queryClient = renderWithHistory(twoPhotos)
    fireEvent.click(await screen.findByRole('button', { name: 'Großansicht: reise/b.jpg' }))
    expect(screen.getByRole('dialog', { name: 'b.jpg' })).toBeInTheDocument()

    vi.mocked(photosApi.getAlbumDraft).mockResolvedValue({
      events: [EVENT_A],
      items: [photo(1, { relative_path: 'reise/a.jpg' })],
      eligible_candidate_count: PLENTY_OF_CANDIDATES,
    })
    await act(async () => {
      await queryClient.invalidateQueries({ queryKey: ['photos', 1] })
    })

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await waitFor(() =>
      expect(screen.getByRole('heading', { level: 1, name: 'Album-Entwurf' })).toHaveFocus(),
    )
    expect(probe.location?.state).toBeNull()
    back()
    expect(probe.location?.pathname).toBe('/stub')
  })

  it('has no link in the large view', async () => {
    renderWithHistory(twoPhotos)

    fireEvent.click(await screen.findByRole('button', { name: 'Großansicht: reise/a.jpg' }))

    expect(within(screen.getByRole('dialog')).queryAllByRole('link')).toEqual([])
  })
})

/**
 * Spec 0621: Die Leerzustände der Entwurfsseite in ihrer Vorrang-Reihenfolge. Höchstens einer
 * steht zugleich; die Fälle unten gehen alle sechs durch.
 */
describe('AlbumDraftPage: Leerzustände in Vorrang-Reihenfolge', () => {
  function eyeProject(overrides: Partial<ProjectOut> = {}): ProjectOut {
    return projectOut({
      cloud_vision_detection_enabled: false,
      model_choice: {
        category_method: 'eye',
        category_provider: null,
        category_model: null,
        landmark_provider: null,
        landmark_model: 'claude-haiku-4-5',
      },
      ...overrides,
    })
  }

  function modelChoice(overrides: Partial<ModelChoiceOut> = {}): ModelChoiceOut {
    return {
      current: {
        category_method: 'eye',
        category_model: null,
        category_provider: null,
        category_is_default: true,
        landmark_model: 'claude-haiku-4-5',
        landmark_provider: 'anthropic',
        landmark_is_default: true,
      },
      cloud_models: [],
      eye: { available: true, unavailable_reasons: [] },
      ...overrides,
    }
  }

  it('1. hält das Skeleton, solange die Modellwahl-Antwort aussteht', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(eyeProject())
    vi.mocked(projectsApi.getModelChoice).mockReturnValue(new Promise(() => {}))

    renderPage({ events: [], items: [] }, noObserver)

    expect(await screen.findByRole('status', { name: 'Fotos werden geladen…' })).toBeInTheDocument()
    expect(screen.queryByText(DRAFT_EMPTY_TEXT)).toBeNull()
    expect(screen.queryByText(DRAFT_EYE_DISABLED_TEXT)).toBeNull()
  })

  it('2. zeigt bestehende Alerts für Entwurf und Projekt', async () => {
    vi.mocked(photosApi.getAlbumDraft).mockRejectedValue(new ApiError(500, 'Entwurf weg.'))
    vi.mocked(projectsApi.getProject).mockRejectedValue(new ApiError(500, 'Projekt weg.'))

    renderPage(null, noObserver)

    expect(await screen.findByText('Entwurf weg.')).toBeInTheDocument()
    expect(await screen.findByText('Projekt weg.')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Erneut versuchen' })).toHaveLength(2)
  })

  it('2b. fällt bei gescheiterter Modellwahl auf den Leerzustand 5 zurück, ohne Alert', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(eyeProject())
    vi.mocked(projectsApi.getModelChoice).mockRejectedValue(new ApiError(500, 'Wahl weg.'))

    renderPage({ events: [], items: [] }, noObserver)

    expect(await screen.findByText(DRAFT_EMPTY_TEXT)).toBeInTheDocument()
    expect(screen.queryByText('Wahl weg.')).toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('3. verlangt die Cloud-Freigabe nur im Cloud-Projekt', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(
      projectOut({ cloud_vision_detection_enabled: false }),
    )
    const cloud = renderPage({ events: [], items: [] }, noObserver)

    expect(await screen.findByText(DRAFT_CLOUD_CONSENT_TEXT)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: SETTINGS_LINK_LABEL })).toHaveAttribute(
      'href',
      '/projects/1/settings',
    )
    expect(screen.queryByText(DRAFT_EMPTY_TEXT)).toBeNull()
    cloud.unmount()

    // Im Eye-Projekt nie - auch nicht ohne Einwilligung.
    vi.mocked(projectsApi.getProject).mockResolvedValue(eyeProject())
    vi.mocked(projectsApi.getModelChoice).mockResolvedValue(modelChoice())
    renderPage({ events: [], items: [] }, noObserver)

    expect(await screen.findByText(DRAFT_EMPTY_TEXT)).toBeInTheDocument()
    expect(screen.queryByText(DRAFT_CLOUD_CONSENT_TEXT)).toBeNull()
  })

  it('3a. zeigt den Freigabe-Hinweis nicht, solange der Entwurf lädt', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(
      projectOut({ cloud_vision_detection_enabled: false }),
    )
    vi.mocked(photosApi.getAlbumDraft).mockReturnValue(new Promise(() => {}))

    renderPage(null, noObserver)
    expect(await screen.findByRole('status', { name: 'Fotos werden geladen…' })).toBeInTheDocument()

    // Die Projektdaten eintreffen lassen: sonst wäre die Abwesenheit des Hinweises nur die
    // Abwesenheit der Projektdaten und bewiese nichts.
    await act(async () => {
      await Promise.resolve()
    })

    expect(screen.getByRole('status', { name: 'Fotos werden geladen…' })).toBeInTheDocument()
    expect(screen.queryByText(DRAFT_CLOUD_CONSENT_TEXT)).toBeNull()
  })

  it('3b. zeigt den Freigabe-Hinweis nicht, wenn die Entwurf-Abfrage scheitert', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(
      projectOut({ cloud_vision_detection_enabled: false }),
    )
    vi.mocked(photosApi.getAlbumDraft).mockRejectedValue(new ApiError(500, 'Entwurf weg.'))

    renderPage(null, noObserver)

    expect(await screen.findByText('Entwurf weg.')).toBeInTheDocument()
    expect(screen.queryByText(DRAFT_CLOUD_CONSENT_TEXT)).toBeNull()
  })

  it('4. nennt im Eye-Projekt den abgeschalteten Dienst statt eines leeren Entwurfs', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(eyeProject())
    vi.mocked(projectsApi.getModelChoice).mockResolvedValue(
      modelChoice({ eye: { available: false, unavailable_reasons: ['eye_disabled'] } }),
    )

    renderPage({ events: [], items: [] }, noObserver)

    expect(await screen.findByText(DRAFT_EYE_DISABLED_TEXT)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: SETTINGS_LINK_LABEL })).toHaveAttribute(
      'href',
      '/projects/1/settings',
    )
    expect(screen.queryByText(DRAFT_EMPTY_TEXT)).toBeNull()
    expect(screen.queryByText(DRAFT_CLOUD_CONSENT_TEXT)).toBeNull()
  })

  it('5. zeigt ohne Events den Weg zur Klassifizierung', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(eyeProject())
    vi.mocked(projectsApi.getModelChoice).mockResolvedValue(modelChoice())

    renderPage({ events: [], items: [] }, noObserver)

    expect(await screen.findByText(DRAFT_EMPTY_TEXT)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Zur Klassifizierung' })).toHaveAttribute(
      'href',
      '/projects/1/pipeline/kriterien',
    )
    expect(screen.queryByText(DRAFT_EYE_DISABLED_TEXT)).toBeNull()
  })

  it('6. lässt einen vorhandenen Entwurf ohne jeden Hinweis stehen', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(eyeProject())

    renderPage(
      {
        events: [EVENT_A],
        items: [photo(1, { album_suitability: { level: 4, reason: null, source: 'eye' } })],
      },
      noObserver,
    )

    expect(await screen.findByRole('button', { name: 'Streichen: 1.jpg' })).toBeInTheDocument()
    for (const text of [DRAFT_CLOUD_CONSENT_TEXT, DRAFT_EMPTY_TEXT, DRAFT_EYE_DISABLED_TEXT]) {
      expect(screen.queryByText(text)).toBeNull()
    }
  })

  it('(a) zeigt auch bei abgeschaltetem Eye mit Events den Entwurf ohne Hinweis', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(eyeProject())
    vi.mocked(projectsApi.getModelChoice).mockResolvedValue(
      modelChoice({ eye: { available: false, unavailable_reasons: ['eye_disabled'] } }),
    )

    renderPage(
      {
        events: [EVENT_A],
        items: [photo(1, { album_suitability: { level: 3, reason: null, source: 'eye' } })],
      },
      noObserver,
    )

    expect(await screen.findByRole('button', { name: 'Streichen: 1.jpg' })).toBeInTheDocument()
    expect(screen.queryByText(DRAFT_EYE_DISABLED_TEXT)).toBeNull()
  })

  it('(c) ruft im Cloud-Projekt die Modellwahl nie ab', async () => {
    renderPage({ events: [EVENT_A], items: [photo(1)] }, noObserver)

    expect(await screen.findByRole('button', { name: 'Streichen: 1.jpg' })).toBeInTheDocument()
    expect(vi.mocked(projectsApi.getModelChoice)).not.toHaveBeenCalled()
  })

  it('(d) hält das Skeleton auch dann, wenn nur der Entwurf schon da ist', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(eyeProject())
    vi.mocked(projectsApi.getModelChoice).mockReturnValue(new Promise(() => {}))

    renderPage({ events: [], items: [] }, noObserver)

    await waitFor(() => expect(vi.mocked(photosApi.getAlbumDraft)).toHaveBeenCalled())
    expect(screen.getByRole('status', { name: 'Fotos werden geladen…' })).toBeInTheDocument()
    expect(screen.queryByText(DRAFT_EMPTY_TEXT)).toBeNull()
  })

  it('(Eye) nennt Eye einmal je Ansicht, sobald eine Eye-Stufe erscheint', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(eyeProject())

    renderPage(
      {
        events: [EVENT_A],
        items: [
          photo(1, { album_suitability: { level: 4, reason: null, source: 'eye' } }),
          photo(2, { album_suitability: { level: 2, reason: null, source: 'eye' } }),
        ],
      },
      noObserver,
    )

    await screen.findByRole('button', { name: 'Streichen: 1.jpg' })
    const attribution = screen.getAllByTestId('eye-attribution')
    expect(attribution).toHaveLength(1)
    expect(attribution[0].closest('header')).not.toBeNull()
  })

  it('(Eye) nennt Eye gar nicht, wenn keine Stufe von dort stammt', async () => {
    renderPage(
      {
        events: [EVENT_A],
        items: [photo(1, { album_suitability: { level: 4, reason: 'Gut.', source: 'cloud' } })],
      },
      noObserver,
    )

    await screen.findByRole('button', { name: 'Streichen: 1.jpg' })
    expect(screen.queryAllByTestId('eye-attribution')).toHaveLength(0)
  })
})
