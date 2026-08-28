import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as photosApi from '../api/photos'
import * as ratingsApi from '../api/ratings'
import type {
  CloudVisionStatusOut,
  CriterionScoreOut,
  PhotoListOut,
  PhotoOut,
  SuggestionOut,
} from '../api/types'
import { setToken } from '../auth/token'
import { PhotoDetailPage } from './PhotoDetailPage'

vi.mock('../api/photos')
vi.mock('../api/ratings')

function makeToken(payload: unknown): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
  const body = btoa(JSON.stringify(payload))
  return `${header}.${body}.signature-irrelevant`
}

function photo(overrides: Partial<PhotoOut> = {}): PhotoOut {
  return {
    id: 1,
    relative_path: 'a.jpg',
    taken_at: '2026-07-20T10:00:00Z',
    ratings: [],
    suggestion: null,
    ranking: null,
    criterion_scores: [],
    remote_category_labels: [],
    category_override: null,
    category_candidates: [],
    cloud_vision_status: [],
    ...overrides,
  }
}

function criterionScore(overrides: Partial<CriterionScoreOut> = {}): CriterionScoreOut {
  return {
    criterion_key: 'sharpness',
    display_name: 'Schärfe',
    value: 0.8,
    source: 'local_heuristic',
    ...overrides,
  }
}

function suggestion(overrides: Partial<SuggestionOut> = {}): SuggestionOut {
  return {
    status: 'rejected',
    reason: 'low_quality',
    duplicate_of: null,
    sharpness: 1.0,
    exposure: 0.5,
    cluster_key: null,
    computed_at: '2026-07-20T10:00:00Z',
    ...overrides,
  }
}

function cloudVisionStatusEntry(
  overrides: Partial<CloudVisionStatusOut> = {}
): CloudVisionStatusOut {
  return {
    phase: 'landmark',
    status: 'not_run',
    error_message: null,
    attempted_at: null,
    ...overrides,
  }
}

function renderPage(initialPath: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/projects/:projectId/photos" element={<p>Grid-Seite</p>} />
        <Route path="/projects/:projectId/photos/:photoId" element={<PhotoDetailPage />} />
      </Routes>
    </MemoryRouter>,
    { wrapper }
  )
}

describe('PhotoDetailPage', () => {
  beforeEach(() => {
    // Kein window.matchMedia-Stub mehr noetig (anders als vor Spec 0041) - CriterionDetailsPopover
    // wird auf dieser Seite seit der permanenten Sektion nicht mehr eingebunden, die neue
    // CriterionDetailsList ist eine reine Praesentationskomponente ohne matchMedia-Zugriff.
    vi.mocked(photosApi.listPhotos).mockReset()
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockReset()
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockResolvedValue('blob:fake-url')
    vi.mocked(ratingsApi.setRating).mockReset()
    vi.mocked(ratingsApi.deleteRating).mockReset()
    setToken(makeToken({ sub: '1', username: 'testuser' }))
  })

  afterEach(() => {
    window.localStorage.clear()
  })

  it('shows a loading state before the sequence arrives', () => {
    vi.mocked(photosApi.listPhotos).mockReturnValue(new Promise(() => {}))

    renderPage('/projects/1/photos/1')

    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('renders the photo with progress "index/total" and the own rating highlighted', async () => {
    const list: PhotoListOut = {
      items: [
        photo({ id: 1, ratings: [{ user_id: 1, username: 'testuser', status: 'favorite' }] }),
        photo({ id: 2 }),
      ],
      total: 2,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

    renderPage('/projects/1/photos/1')

    expect(await screen.findByText('1/2')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /favorit/i })).toHaveAttribute('aria-pressed', 'true')
    expect(photosApi.fetchPhotoImageBlobUrl).toHaveBeenCalledWith(1, 'display')
  })

  it('disables the previous button on the first photo and the next button on the last', async () => {
    const list: PhotoListOut = { items: [photo({ id: 1 }), photo({ id: 2 })], total: 2 }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

    renderPage('/projects/1/photos/1')
    await screen.findByText('1/2')

    expect(screen.getByRole('button', { name: /zurück|vorherig/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /weiter|nächst/i })).toBeEnabled()
  })

  it('navigates to the next photo on next-button click, preserving the filter', async () => {
    const list: PhotoListOut = { items: [photo({ id: 1 }), photo({ id: 2 })], total: 2 }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1?filter=unrated')
    await screen.findByText('1/2')

    await user.click(screen.getByRole('button', { name: /weiter|nächst/i }))

    await screen.findByText('2/2')
  })

  it('ignores an unknown/tampered filter value in the URL instead of forwarding it to the API', async () => {
    const list: PhotoListOut = { items: [photo({ id: 1 })], total: 1 }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

    renderPage('/projects/1/photos/1?filter=not-a-real-filter')
    await screen.findByText('1/1')

    expect(photosApi.listPhotos).toHaveBeenCalledWith(
      1,
      expect.objectContaining({ ratingStatus: undefined })
    )
  })

  it('navigates to the next photo on ArrowRight', async () => {
    const list: PhotoListOut = { items: [photo({ id: 1 }), photo({ id: 2 })], total: 2 }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1')
    await screen.findByText('1/2')

    await user.keyboard('{ArrowRight}')

    await screen.findByText('2/2')
  })

  it('sets a rating and auto-advances to the next unrated photo', async () => {
    const list: PhotoListOut = {
      items: [photo({ id: 1 }), photo({ id: 2 }), photo({ id: 3 })],
      total: 3,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
    vi.mocked(ratingsApi.setRating).mockResolvedValue({
      user_id: 1,
      username: 'testuser',
      status: 'favorite',
    })
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1')
    await screen.findByText('1/3')

    await user.click(screen.getByRole('button', { name: /favorit/i }))

    expect(ratingsApi.setRating).toHaveBeenCalledWith(1, 'favorite')
    await screen.findByText('2/3')
  })

  it('sets a rating via keyboard shortcut "1"', async () => {
    const list: PhotoListOut = { items: [photo({ id: 1 }), photo({ id: 2 })], total: 2 }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
    vi.mocked(ratingsApi.setRating).mockResolvedValue({
      user_id: 1,
      username: 'testuser',
      status: 'favorite',
    })
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1')
    await screen.findByText('1/2')

    await user.keyboard('1')

    expect(ratingsApi.setRating).toHaveBeenCalledWith(1, 'favorite')
  })

  it('toggles an existing rating back to unrated when the same button is clicked again', async () => {
    const list: PhotoListOut = {
      items: [
        photo({ id: 1, ratings: [{ user_id: 1, username: 'testuser', status: 'favorite' }] }),
        photo({ id: 2 }),
      ],
      total: 2,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
    vi.mocked(ratingsApi.deleteRating).mockResolvedValue(undefined)
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1')
    await screen.findByText('1/2')

    await user.click(screen.getByRole('button', { name: /favorit/i }))

    expect(ratingsApi.deleteRating).toHaveBeenCalledWith(1)
    expect(ratingsApi.setRating).not.toHaveBeenCalled()
    // Anders als beim Setzen einer Bewertung (spec: "Nach dem Setzen einer Bewertung springt...")
    // ist ein Toggle-zurueck-auf-unbewertet eine Korrektur, kein "fertig mit diesem Foto" -
    // Auto-Advance waere hier ueberraschend (Nutzer klickt erneut, um einen Fehlklick
    // rueckgaengig zu machen, nicht um weiterzuspringen).
    await waitFor(() => expect(ratingsApi.deleteRating).toHaveBeenCalled())
    expect(screen.getByText('1/2')).toBeInTheDocument()
  })

  it('shows a completion message instead of a fatal error once no unrated photo is left', async () => {
    const list: PhotoListOut = { items: [photo({ id: 1 })], total: 1 }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
    vi.mocked(ratingsApi.setRating).mockResolvedValue({
      user_id: 1,
      username: 'testuser',
      status: 'favorite',
    })
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1')
    await screen.findByText('1/1')

    await user.click(screen.getByRole('button', { name: /favorit/i }))

    expect(await screen.findByRole('status')).toHaveTextContent(/keine weiteren unbewerteten fotos/i)
  })

  it('shows an inline error banner with a retry option on failure', async () => {
    vi.mocked(photosApi.listPhotos).mockRejectedValue(new ApiError(500, 'Serverfehler'))
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1')
    expect(await screen.findByRole('alert')).toHaveTextContent('Serverfehler')

    vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [photo({ id: 1 })], total: 1 })
    await user.click(screen.getByRole('button', { name: /erneut versuchen/i }))

    await screen.findByText('1/1')
  })

  it('ignores keyboard shortcuts while a text input is focused elsewhere on the page', async () => {
    const list: PhotoListOut = { items: [photo({ id: 1 }), photo({ id: 2 })], total: 2 }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
    const input = document.createElement('input')
    document.body.appendChild(input)
    input.focus()

    renderPage('/projects/1/photos/1')
    await screen.findByText('1/2')

    await userEvent.keyboard('1')

    await waitFor(() => expect(ratingsApi.setRating).not.toHaveBeenCalled())
    document.body.removeChild(input)
  })

  it('shows the suggestion reason and a confirm button for a low-quality suggestion', async () => {
    const list: PhotoListOut = {
      items: [photo({ id: 1, ratings: [], suggestion: suggestion({ reason: 'low_quality' }) })],
      total: 1,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

    renderPage('/projects/1/photos/1')

    expect(await screen.findByText(/automatischer vorschlag: verworfen/i)).toBeInTheDocument()
    expect(screen.getByText(/geringe bildqualität/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /vorschlag übernehmen/i })).toBeInTheDocument()
  })

  it('shows the duplicate-of reason for a duplicate suggestion', async () => {
    const list: PhotoListOut = {
      items: [
        photo({
          id: 1,
          ratings: [],
          suggestion: suggestion({ reason: 'duplicate', duplicate_of: 42 }),
        }),
      ],
      total: 1,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

    renderPage('/projects/1/photos/1')

    expect(await screen.findByText(/duplikat von foto #42/i)).toBeInTheDocument()
  })

  it('does not show a suggestion once an own rating exists', async () => {
    const list: PhotoListOut = {
      items: [
        photo({
          id: 1,
          ratings: [{ user_id: 1, username: 'testuser', status: 'rejected' }],
          suggestion: null,
        }),
      ],
      total: 1,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

    renderPage('/projects/1/photos/1')

    await screen.findByText('1/1')
    expect(screen.queryByText(/automatischer vorschlag/i)).not.toBeInTheDocument()
  })

  it('confirms a suggestion via the same mutation path as a manual rating and auto-advances', async () => {
    const list: PhotoListOut = {
      items: [
        photo({ id: 1, ratings: [], suggestion: suggestion({ status: 'rejected' }) }),
        photo({ id: 2, ratings: [] }),
      ],
      total: 2,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
    vi.mocked(ratingsApi.setRating).mockResolvedValue({
      user_id: 1,
      username: 'testuser',
      status: 'rejected',
    })
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1')
    const confirmButton = await screen.findByRole('button', { name: /vorschlag übernehmen/i })
    await user.click(confirmButton)

    expect(ratingsApi.setRating).toHaveBeenCalledWith(1, 'rejected')
    await screen.findByText('2/2')
  })

  // Spec 0041 (Bewertungsdetails permanent in der Detailansicht), Akzeptanzkriterien 1-4, 12.
  describe('permanent Bewertungsdetails section', () => {
    it('shows criteria and category/rank directly under the photo when the photo has criterion_scores', async () => {
      const list: PhotoListOut = {
        items: [
          photo({
            id: 1,
            criterion_scores: [criterionScore({ display_name: 'Schärfe', value: 0.734 })],
            ranking: {
              cluster_key: 'cluster-0',
              category_key: 'landscape',
              rank_score: 0.8,
              rank_position: 2,
              partition_size: 5,
            },
          }),
        ],
        total: 1,
      }
      vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

      renderPage('/projects/1/photos/1')

      expect(await screen.findByText('Schärfe')).toBeInTheDocument()
      expect(screen.getByText('73%')).toBeInTheDocument()
      expect(screen.getByText('Landscape')).toBeInTheDocument()
      expect(screen.getByText('Rang 2 von 5')).toBeInTheDocument()
    })

    // Akzeptanzkriterium 2: kein leerer Bereich, wenn criterion_scores leer ist (gleiche Regel wie
    // die bisherige Icon-Sichtbarkeit, Spec 0040 AK1). Die neue Cloud-Vision-Status-Sektion
    // (specs/features/0058) bleibt davon unberuehrt - sie ist IMMER sichtbar (eigener describe-
    // Block unten) und rendert deshalb weiterhin ein eigenes <dl>, nur das der
    // CriterionDetailsList entfaellt.
    it('renders no criterion-details dl when criterion_scores is empty', async () => {
      const list: PhotoListOut = { items: [photo({ id: 1, criterion_scores: [] })], total: 1 }
      vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

      renderPage('/projects/1/photos/1')

      await screen.findByText('1/1')
      expect(screen.queryByTestId('criterion-details-section')).not.toBeInTheDocument()
    })

    // Akzeptanzkriterium 3: das Info-Icon/Popover entfaellt in der Detailansicht vollstaendig.
    it('does not render the info-icon trigger/popover anymore', async () => {
      const list: PhotoListOut = {
        items: [photo({ id: 1, criterion_scores: [criterionScore()] })],
        total: 1,
      }
      vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

      renderPage('/projects/1/photos/1')

      await screen.findByText('Schärfe')
      expect(
        screen.queryByRole('button', { name: 'Bewertungsdetails anzeigen' })
      ).not.toBeInTheDocument()
    })

    // Akzeptanzkriterium 6/showSuggestion=false: die permanente Sektion reicht suggestion nicht
    // durch, auch wenn eine Suggestion vorhanden ist - die Ausschuss-Gruppe der CriterionDetailsList
    // ("Ausschuss-Vorschlag"/"Grund") darf dort nicht erscheinen, unabhaengig vom separaten
    // "Automatischer Vorschlag"-Kasten weiter unten auf der Seite.
    it('does not pass suggestion into the permanent section, even when a suggestion exists', async () => {
      const list: PhotoListOut = {
        items: [
          photo({
            id: 1,
            criterion_scores: [criterionScore()],
            ratings: [],
            suggestion: suggestion({ reason: 'low_quality' }),
          }),
        ],
        total: 1,
      }
      vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

      renderPage('/projects/1/photos/1')

      await screen.findByText('Schärfe')
      expect(screen.queryByText('Ausschuss-Vorschlag')).not.toBeInTheDocument()
    })
  })

  // specs/features/0058-cloud-vision-status-transparenz.md: neue, permanente Sektion, immer
  // sichtbar (bewusste Stakeholder-Entscheidung, kein Ausblenden bei not_candidate/not_run).
  describe('permanent Cloud-Vision-Status section', () => {
    it('is visible even when criterion_scores is empty', async () => {
      const list: PhotoListOut = {
        items: [
          photo({
            id: 1,
            criterion_scores: [],
            cloud_vision_status: [
              cloudVisionStatusEntry({ phase: 'landmark', status: 'not_candidate' }),
              cloudVisionStatusEntry({ phase: 'remote_category', status: 'consent_disabled' }),
            ],
          }),
        ],
        total: 1,
      }
      vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

      renderPage('/projects/1/photos/1')

      expect(await screen.findByText('Nicht als Kandidat qualifiziert')).toBeInTheDocument()
      expect(screen.getByText('Cloud-Erkennung deaktiviert')).toBeInTheDocument()
    })

    it('shows a mixed state for both phases simultaneously', async () => {
      const list: PhotoListOut = {
        items: [
          photo({
            id: 1,
            cloud_vision_status: [
              cloudVisionStatusEntry({
                phase: 'landmark',
                status: 'result',
                attempted_at: '2026-08-24T10:00:00Z',
              }),
              cloudVisionStatusEntry({
                phase: 'remote_category',
                status: 'error',
                error_message: 'Fehler beim Klassifizieren',
                attempted_at: '2026-08-24T10:00:00Z',
              }),
            ],
          }),
        ],
        total: 1,
      }
      vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

      renderPage('/projects/1/photos/1')

      expect(await screen.findByText('Ergebnis vorhanden')).toBeInTheDocument()
      expect(screen.getByText('Fehler beim Versuch')).toBeInTheDocument()
      expect(screen.getByText('Fehler beim Klassifizieren')).toBeInTheDocument()
    })
  })

  // specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, UI/UX-Abschnitt.
  describe('category override', () => {
    it('overrides the category from the permanent details section', async () => {
      const list: PhotoListOut = {
        items: [
          photo({
            id: 1,
            criterion_scores: [criterionScore()],
            ranking: {
              cluster_key: 'cluster-0',
              category_key: 'people',
              rank_score: 0.5,
              rank_position: 1,
              partition_size: 1,
            },
            category_candidates: [
              { category_key: 'hund', origin: 'remote', score: 0.9, provider: 'anthropic' },
              { category_key: 'people', origin: 'local', score: 0.4, provider: null },
            ],
          }),
        ],
        total: 1,
      }
      vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
      vi.mocked(photosApi.setCategoryOverride).mockResolvedValue({
        photo_id: 1,
        category_key: 'hund',
      })
      const user = userEvent.setup()

      renderPage('/projects/1/photos/1')

      await screen.findByText('Kategorie-Kandidaten')
      await user.click(screen.getByRole('button', { name: /^übernehmen$/i }))

      await waitFor(() => expect(photosApi.setCategoryOverride).toHaveBeenCalledWith(1, 'hund'))
    })
  })
})
