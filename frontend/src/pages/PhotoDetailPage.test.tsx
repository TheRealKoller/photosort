import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as photosApi from '../api/photos'
import * as ratingsApi from '../api/ratings'
import * as motifsApi from '../api/motifs'
import type {
  CloudVisionStatusOut,
  CriterionScoreOut,
  MotifAssessmentOut,
  MotifStrengthOut,
  PhotoListOut,
  PhotoOut,
  SuggestionOut,
} from '../api/types'
import { setToken } from '../auth/token'
import { MOTIF_KEYS, MOTIF_SET } from '../test/motifSetFixture'
import { PhotoDetailPage } from './PhotoDetailPage'

// (`useCategoriesQuery`) - ohne Mock liefe diese Query in einen echten Request und die Seite
// stuende dauerhaft im Fallback-Zustand, statt in einem bewusst gewaehlten.
// specs/features/0427-motive-mit-staerke.md: dasselbe fuer das Motivset (`useMotifsQuery`) - ohne
// Mock stuende die Staerkeliste dauerhaft im Skeleton-Zustand.
vi.mock('../api/motifs')
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
    taken_at_original: '2026-07-20T10:00:00Z',
    time_offset_minutes: 0,
    camera: null,
    ratings: [],
    suggestion: null,
    ranking: null,
    criterion_scores: [],
    fine_labels: [],
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
    // Default-Key ist `sharpness` (ohne Praesenz-Schwelle) - der Default muss dazu passen,
    // damit kein Bestandstest unbemerkt in den Bildinhalt-Block rutscht.
    has_presence_threshold: false,
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

// specs/features/0427-motive-mit-staerke.md: die Kopfzeile des Regelfalls (Cloud-Grundlage, nicht
// ausgeschlossen) und ein vollbesetzter Achter-Vektor.
const CLOUD_ASSESSMENT: MotifAssessmentOut = {
  source: 'cloud',
  provider: 'anthropic',
  excluded_document: false,
  computed_at: '2026-09-12T10:00:00',
}

function motifStrengths(
  overrides: Record<string, Partial<MotifStrengthOut>> = {},
): MotifStrengthOut[] {
  return MOTIF_KEYS.map((key) => ({
    key,
    strength: 0,
    correction: null,
    // Bewusst NICHT aus `strength` abgeleitet: `present` ist die Aussage des Servers, und eine
    // Kopplung hier machte jeden Fall blind fuer eine Oberflaeche, die doch selbst vergleicht.
    present: false,
    ...(overrides[key] ?? {}),
  }))
}

function cloudVisionStatusEntry(
  overrides: Partial<CloudVisionStatusOut> = {},
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
    { wrapper },
  )
}

/** Die permanente Motivsektion - von mehreren Beschreibungsbloecken gebraucht. */
function motifSection(): HTMLElement {
  return screen.getByTestId('motifs-section')
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
    vi.mocked(ratingsApi.setFavorite).mockReset()
    vi.mocked(motifsApi.listMotifs).mockReset()
    vi.mocked(motifsApi.listMotifs).mockResolvedValue(MOTIF_SET)
    vi.mocked(photosApi.setMotifCorrection).mockReset()
    vi.mocked(photosApi.deleteMotifCorrection).mockReset()
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
        photo({
          id: 1,
          ratings: [{ user_id: 1, username: 'testuser', status: 'album_worthy', favorite: true }],
        }),
        photo({ id: 2 }),
      ],
      total: 2,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

    renderPage('/projects/1/photos/1')

    expect(await screen.findByText('1/2')).toBeInTheDocument()
    // BEIDE gedrueckt zugleich - der sichtbare Beweis der Trennung (ADR 0098 Punkt 2).
    expect(screen.getByRole('button', { name: /album-würdig/i })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
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
      expect.objectContaining({ ratingStatus: undefined }),
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
      photo_id: 1,
      user_id: 1,
      status: 'album_worthy',
      favorite: false,
      updated_at: '2026-09-13T10:00:00',
    })
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1')
    await screen.findByText('1/3')

    await user.click(screen.getByRole('button', { name: /album-würdig/i }))

    expect(ratingsApi.setRating).toHaveBeenCalledWith(1, 'album_worthy')
    await screen.findByText('2/3')
  })

  it('does not auto-advance and does not touch the album decision when the favorite is set', async () => {
    // Die Auszeichnung ist keine Entscheidung UEBER dieses Foto, sondern eine Notiz daneben -
    // weiterzuspringen naehme dem Nutzer die Moeglichkeit, im selben Atemzug noch zu
    // entscheiden. Und sie geht ueber den EIGENEN Endpunkt: ein gemeinsamer Schreibweg setzte
    // die Albumentscheidung hier still zurueck.
    const list: PhotoListOut = { items: [photo({ id: 1 }), photo({ id: 2 })], total: 2 }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
    vi.mocked(ratingsApi.setFavorite).mockResolvedValue({
      photo_id: 1,
      user_id: 1,
      status: null,
      favorite: true,
      updated_at: '2026-09-13T10:00:00',
    })
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1')
    await screen.findByText('1/2')

    await user.click(screen.getByRole('button', { name: /favorit/i }))

    expect(ratingsApi.setFavorite).toHaveBeenCalledWith(1, true)
    expect(ratingsApi.setRating).not.toHaveBeenCalled()
    expect(ratingsApi.deleteRating).not.toHaveBeenCalled()
    expect(screen.getByText('1/2')).toBeInTheDocument()
  })

  it('clears the favorite marker on a second press without touching the album decision', async () => {
    const list: PhotoListOut = {
      items: [
        photo({
          id: 1,
          ratings: [{ user_id: 1, username: 'testuser', status: 'rejected', favorite: true }],
        }),
      ],
      total: 1,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
    vi.mocked(ratingsApi.setFavorite).mockResolvedValue({
      photo_id: 1,
      user_id: 1,
      status: 'rejected',
      favorite: false,
      updated_at: '2026-09-13T10:00:00',
    })
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1')
    await screen.findByText('1/1')

    await user.click(screen.getByRole('button', { name: /favorit/i }))

    expect(ratingsApi.setFavorite).toHaveBeenCalledWith(1, false)
    expect(ratingsApi.deleteRating).not.toHaveBeenCalled()
  })

  it('still treats a photo that carries only the favorite marker as undecided', async () => {
    // Auto-Advance sucht das naechste Foto OHNE Albumentscheidung. Auf das Vorhandensein der
    // Zeile gepruefte Abwesenheit uebersprAenge ein nur als Favorit markiertes Foto still.
    const list: PhotoListOut = {
      items: [
        photo({ id: 1 }),
        photo({
          id: 2,
          ratings: [{ user_id: 1, username: 'testuser', status: null, favorite: true }],
        }),
        photo({ id: 3 }),
      ],
      total: 3,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
    vi.mocked(ratingsApi.setRating).mockResolvedValue({
      photo_id: 1,
      user_id: 1,
      status: 'album_worthy',
      favorite: false,
      updated_at: '2026-09-13T10:00:00',
    })
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1')
    await screen.findByText('1/3')

    await user.click(screen.getByRole('button', { name: /album-würdig/i }))

    await screen.findByText('2/3')
  })

  /*
   * specs/features/0321-dark-utility-register-ansichten.md, Etappe 3: NEUE FEHLERKLASSE, die diese
   * Spec erst erzeugt - EIN KAESTCHEN, DAS LUEGT. Die sichtbare Ziffer steht seit dem Umbau in
   * `RatingButtons`, die Tastenbelegung hier in `PhotoDetailPage`; beide koennen auseinanderlaufen,
   * ohne dass irgendein anderer Test etwas merkt.
   *
   * Deshalb Tabelle ueber ALLE DREI Tasten, und je Zeile die zusaetzliche Zusicherung, dass die
   * Schaltflaeche des ausgeloesten Status genau diese Ziffer sichtbar traegt. Ein Test, der nur die
   * Anwesenheit der Ziffern prueft, erfuellt das nicht.
   */
  it.each([
    ['2', 'album_worthy', 'Album-würdig'],
    ['3', 'rejected', 'Verwerfen'],
  ] as const)(
    'sets the rating of key "%s" and shows that very key on its button',
    async (key, status, label) => {
      const list: PhotoListOut = { items: [photo({ id: 1 }), photo({ id: 2 })], total: 2 }
      vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
      vi.mocked(ratingsApi.setRating).mockResolvedValue({
        photo_id: 1,
        user_id: 1,
        status,
        favorite: false,
        updated_at: '2026-09-13T10:00:00',
      })
      const user = userEvent.setup()

      renderPage('/projects/1/photos/1')
      await screen.findByText('1/2')

      await user.keyboard(key)

      expect(ratingsApi.setRating).toHaveBeenCalledWith(1, status)
      // Das Kennzeichen bleibt unberuehrt - die Taste schreibt genau ihr Feld.
      expect(ratingsApi.setFavorite).not.toHaveBeenCalled()
      expect(screen.getByRole('button', { name: label })).toHaveTextContent(key)
    },
  )

  it('routes key "1" to the favorite endpoint and shows that very key on its button', async () => {
    // Die dritte Zeile derselben Tabelle, aber mit ANDEREM Ziel: Die Belegung 1/2/3 bleibt, Taste
    // 1 schreibt seit ADR 0098 das unabhaengige Kennzeichen. Getrennt geschrieben, weil sonst
    // genau die Zusage "die Taste fasst das jeweils andere Feld nicht an" im Rauschen unterginge.
    const list: PhotoListOut = { items: [photo({ id: 1 }), photo({ id: 2 })], total: 2 }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
    vi.mocked(ratingsApi.setFavorite).mockResolvedValue({
      photo_id: 1,
      user_id: 1,
      status: null,
      favorite: true,
      updated_at: '2026-09-13T10:00:00',
    })
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1')
    await screen.findByText('1/2')

    await user.keyboard('1')

    expect(ratingsApi.setFavorite).toHaveBeenCalledWith(1, true)
    expect(ratingsApi.setRating).not.toHaveBeenCalled()
    expect(ratingsApi.deleteRating).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Favorit' })).toHaveTextContent('1')
  })

  it('toggles an existing rating back to unrated when the same button is clicked again', async () => {
    const list: PhotoListOut = {
      items: [
        photo({
          id: 1,
          ratings: [{ user_id: 1, username: 'testuser', status: 'album_worthy', favorite: false }],
        }),
        photo({ id: 2 }),
      ],
      total: 2,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
    vi.mocked(ratingsApi.deleteRating).mockResolvedValue(undefined)
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1')
    await screen.findByText('1/2')

    await user.click(screen.getByRole('button', { name: /album-würdig/i }))

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
      photo_id: 1,
      user_id: 1,
      status: 'album_worthy',
      favorite: false,
      updated_at: '2026-09-13T10:00:00',
    })
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1')
    await screen.findByText('1/1')

    await user.click(screen.getByRole('button', { name: /album-würdig/i }))

    expect(await screen.findByRole('status')).toHaveTextContent(
      /keine weiteren unbewerteten fotos/i,
    )
  })

  /*
   * specs/features/0298-projektnavigation-in-der-kopfzeile.md (AK14, Bestandsschutz): Beide Links
   * bleiben trotz der neuen Kopfzeilengruppe ausdruecklich erhalten - "Zur Vergleichsansicht" ist
   * hier eine Handlungsaufforderung fuer den naechsten Arbeitsschritt (nur im Abschlusszustand),
   * "Zurück zum Grid" fuehrt zu einem ANDEREN Ziel als die Kopfzeile, weil es den aktiven Filter
   * der Fotoliste bewahrt. Eine Anwesenheits-, keine Abwesenheitspruefung: die Kopfzeilengruppe
   * darf sie nicht mitreissen.
   */
  it('keeps "Zurück zum Grid" and "Zur Vergleichsansicht" in the completion state (AK14)', async () => {
    const list: PhotoListOut = { items: [photo({ id: 1 })], total: 1 }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
    vi.mocked(ratingsApi.setRating).mockResolvedValue({
      photo_id: 1,
      user_id: 1,
      status: 'album_worthy',
      favorite: false,
      updated_at: '2026-09-13T10:00:00',
    })
    const user = userEvent.setup()

    renderPage('/projects/1/photos/1?filter=unrated')
    await screen.findByText('1/1')

    await user.click(screen.getByRole('button', { name: /album-würdig/i }))
    expect(await screen.findByRole('status')).toHaveTextContent(
      /keine weiteren unbewerteten fotos/i,
    )

    // Der Grid-Link bewahrt den aktiven Filter - genau das unterscheidet ihn vom Kopfzeilenziel
    // "Fotos", das immer auf die ungefilterte Liste zeigt.
    expect(screen.getByRole('link', { name: 'Zurück zum Grid' })).toHaveAttribute(
      'href',
      '/projects/1/photos?filter=unrated',
    )
    expect(screen.getByRole('link', { name: 'Zur Vergleichsansicht' })).toHaveAttribute(
      'href',
      '/projects/1/compare',
    )
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
          ratings: [{ user_id: 1, username: 'testuser', status: 'rejected', favorite: false }],
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
      photo_id: 1,
      user_id: 1,
      status: 'rejected',
      favorite: false,
      updated_at: '2026-09-13T10:00:00',
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
    it('shows criteria and the rank directly under the photo when the photo has criterion_scores', async () => {
      const list: PhotoListOut = {
        items: [
          photo({
            id: 1,
            criterion_scores: [criterionScore({ display_name: 'Schärfe', value: 0.734 })],
            ranking: {
              event_id: 1,
              rank_score: 0.8,
              rank_position: 2,
              proposed: true,
              partition_size: 5,
              curation_position: null,
            },
          }),
        ],
        total: 1,
      }
      vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

      renderPage('/projects/1/photos/1')

      expect(await screen.findByText('Schärfe')).toBeInTheDocument()
      expect(screen.getByText('73%')).toBeInTheDocument()
      expect(screen.getByText('Rang 2 von 5')).toBeInTheDocument()
    })

    // specs/features/0209-bewertungsdetails-bloecke-qualitaet-kategorien.md, Akzeptanzkriterium 1:
    // genau EIN Oberflaechennachweis, dass die beiden beschrifteten Bloecke auch in der
    // permanenten Sektion ankommen - die Blockbildungs-Logik selbst liegt vollstaendig in
    // CriterionDetailsList.test.tsx (specs/architecture/0002-testkonzept.md, useId-Sektion
    // Punkt 5: keine Doppelabdeckung derselben Logik auf zwei Ebenen).
    it('shows both block headings in the permanent section', async () => {
      const list: PhotoListOut = {
        items: [
          photo({
            id: 1,
            criterion_scores: [
              criterionScore({ criterion_key: 'sharpness', display_name: 'Schärfe' }),
              criterionScore({
                criterion_key: 'content_people',
                display_name: 'Menschen erkannt',
                has_presence_threshold: true,
              }),
            ],
          }),
        ],
        total: 1,
      }
      vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

      renderPage('/projects/1/photos/1')

      const section = await screen.findByTestId('criterion-details-section')
      expect(
        within(section).getByRole('heading', { name: 'Qualität', level: 3 }),
      ).toBeInTheDocument()
      expect(
        within(section).getByRole('heading', { name: 'Bildinhalt', level: 3 }),
      ).toBeInTheDocument()
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
        screen.queryByRole('button', { name: 'Bewertungsdetails anzeigen' }),
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
  describe('Reihenfolge: Bedienelemente zuerst', () => {
    /** Foto mit JEDEM Bereich der Seite gleichzeitig - ein fehlender Bereich koennte in der
     * Soll-Folge nicht auffallen. */
    function fullPhoto(overrides: Partial<PhotoOut> = {}): PhotoOut {
      return photo({
        id: 1,
        criterion_scores: [
          criterionScore({ criterion_key: 'sharpness', display_name: 'Schärfe' }),
          criterionScore({
            criterion_key: 'content_people',
            display_name: 'Menschen erkannt',
            has_presence_threshold: true,
          }),
        ],
        ranking: {
          event_id: 1,
          rank_score: 0.8,
          rank_position: 2,
          proposed: true,
          partition_size: 5,
          curation_position: null,
        },
        fine_labels: [
          {
            canonical_key: 'urlaub',
            display_name: 'Urlaub',
            raw_label: 'Urlaub',
            provider: 'anthropic',
          },
        ],
        cloud_vision_status: [cloudVisionStatusEntry({ phase: 'landmark', status: 'not_run' })],
        suggestion: suggestion({ reason: 'low_quality' }),
        // Mit Kopfzeile UND Staerkevektor: sonst zeigte die Motivsektion nur den Satz "noch
        // nicht klassifiziert", und der Abschnitt waere nicht vollstaendig.
        motif_assessment: CLOUD_ASSESSMENT,
        motifs: motifStrengths(),
        ...overrides,
      })
    }

    /** Dokumentreihenfolge der uebergebenen Handles. `compareDocumentPosition` wird gegen die
     * BITMASKE geprueft, nie per Gleichheit: liegen zwei Elemente ineinander, liefert der Aufruf
     * `20` (CONTAINED_BY | FOLLOWING), und ein Gleichheitsvergleich waere falsch-rot. */
    function inDocumentOrder(handles: { name: string; element: HTMLElement }[]): string[] {
      return [...handles]
        .sort((a, b) =>
          (a.element.compareDocumentPosition(b.element) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0
            ? -1
            : 1,
        )
        .map((handle) => handle.name)
    }

    async function collectSectionHandles(): Promise<{ name: string; element: HTMLElement }[]> {
      return [
        { name: 'Shortcut-Zeile', element: screen.getByText(/^Shortcuts:/) },
        { name: 'Zähler', element: screen.getByText('1/1') },
        { name: 'Foto', element: await screen.findByAltText('a.jpg') },
        { name: 'Bewertungsleiste', element: screen.getByRole('group', { name: 'Bewertung' }) },
        { name: 'Navigation', element: screen.getByRole('button', { name: 'Vorheriges Foto' }) },
        { name: 'Cloud-Vision-Status', element: screen.getByTestId('cloud-vision-status-section') },
        { name: 'Informationsteil', element: screen.getByTestId('criterion-details-section') },
        { name: 'Zurück zum Grid', element: screen.getByRole('link', { name: 'Zurück zum Grid' }) },
      ]
    }

    it('stellt alle Bedienelemente vor jede reine Informationsanzeige (mit Vorschlag)', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [fullPhoto()], total: 1 })

      renderPage('/projects/1/photos/1')
      await screen.findByText('1/1')

      const handles = await collectSectionHandles()
      handles.push({
        name: 'Automatischer Vorschlag',
        element: screen.getByText(/^Automatischer Vorschlag/),
      })

      expect(inDocumentOrder(handles)).toEqual([
        'Shortcut-Zeile',
        'Zähler',
        'Foto',
        'Bewertungsleiste',
        'Navigation',
        'Automatischer Vorschlag',
        'Cloud-Vision-Status',
        'Informationsteil',
        'Zurück zum Grid',
      ])
    })

    /* Zweite Variante ohne den optionalen Vorschlagskasten, damit die Zusage nicht an einem
     * Bereich haengt, den es nicht immer gibt. */
    it('hält dieselbe Reihenfolge ohne Vorschlagskasten', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [fullPhoto({ suggestion: null })],
        total: 1,
      })

      renderPage('/projects/1/photos/1')
      await screen.findByText('1/1')

      expect(screen.queryByText(/^Automatischer Vorschlag/)).not.toBeInTheDocument()
      expect(inDocumentOrder(await collectSectionHandles())).toEqual([
        'Shortcut-Zeile',
        'Zähler',
        'Foto',
        'Bewertungsleiste',
        'Navigation',
        'Cloud-Vision-Status',
        'Informationsteil',
        'Zurück zum Grid',
      ])
    })

    /* Akzeptanzkriterium 3: die Informationsanzeigen sind ohne jede Bedienhandlung vollstaendig
     * sichtbar. Abwesenheitszusage INNERHALB des Abschnitts - seitenweit waere sie falsch, weil
     * das Glossar der Motivliste bewusst ein <details> in ihrem eigenen Abschnitt bleibt. */
    it('lässt die Aufschlüsselung ohne aufklappbares Element und ohne Trigger', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [fullPhoto()], total: 1 })

      renderPage('/projects/1/photos/1')

      const info = await screen.findByTestId('criterion-details-section')
      expect(info.querySelector('details')).toBeNull()
      expect(info.querySelector('summary')).toBeNull()
      expect(info.querySelector('[aria-expanded]')).toBeNull()
      expect(info.querySelector('[aria-haspopup]')).toBeNull()
      expect(within(info).queryByRole('button')).not.toBeInTheDocument()
      // Gegenprobe: das <details> der Motivsektion steht unveraendert weiter.
      expect(motifSection().querySelector('details')).not.toBeNull()
    })

    it('zeigt die Feinlabel-Chips in der Aufschlüsselung, nicht in der Motivsektion', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [fullPhoto()], total: 1 })

      renderPage('/projects/1/photos/1')

      const info = await screen.findByTestId('criterion-details-section')
      expect(within(info).getByText('Urlaub')).toBeInTheDocument()
      expect(within(motifSection()).queryByText('Urlaub')).not.toBeInTheDocument()
    })

    /* Akzeptanzkriterium 6: kein leerer Platzhalter. Ohne Kriterien erscheint KEINER der beiden
     * Bereiche, der Cloud-Vision-Status bleibt unveraendert immer sichtbar. */
    it('rendert ohne criterion_scores gar keine Aufschlüsselung', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, criterion_scores: [] })],
        total: 1,
      })

      renderPage('/projects/1/photos/1')
      await screen.findByText('1/1')

      expect(screen.queryByTestId('criterion-details-section')).not.toBeInTheDocument()
      expect(screen.getByTestId('cloud-vision-status-section')).toBeInTheDocument()
    })

    it('rendert ohne Ranking keinen Bedienteil, den Informationsteil aber schon', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, criterion_scores: [criterionScore()], ranking: null })],
        total: 1,
      })

      renderPage('/projects/1/photos/1')
      await screen.findByText('1/1')

      expect(screen.queryByTestId('category-controls-section')).not.toBeInTheDocument()
      expect(screen.getByTestId('criterion-details-section')).toBeInTheDocument()
    })
  })

  /* Verdrahtung der ZWEITEN Einbindung (Bedienteil) - die Logik selbst liegt auf
   * Komponentenebene, hier wird nur geprueft, dass die Props tatsaechlich ankommen. */
  /* Akzeptanzkriterium 5: Tastenkuerzel und Wischgesten wirken unveraendert. ArrowLeft und die
   * Wischgesten hatten bis zu dieser Spec keinen Test - ohne sie waere "unveraendert" beim
   * Umbau der Seite eine unbelegte Behauptung. */
  describe('Blättern per Tastatur und Wischgeste', () => {
    function twoPhotos(): PhotoListOut {
      return { items: [photo({ id: 1 }), photo({ id: 2, relative_path: 'b.jpg' })], total: 2 }
    }

    it('navigates to the previous photo on ArrowLeft', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue(twoPhotos())
      const user = userEvent.setup()

      renderPage('/projects/1/photos/2')
      await screen.findByText('2/2')

      await user.keyboard('{ArrowLeft}')

      await screen.findByText('1/2')
    })

    it('blättert bei einer Wischgeste nach links zum nächsten Foto', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue(twoPhotos())

      renderPage('/projects/1/photos/1')
      const image = await screen.findByAltText('a.jpg')

      fireEvent.touchStart(image, { touches: [{ clientX: 200 }] })
      fireEvent.touchEnd(image, { changedTouches: [{ clientX: 100 }] })

      await screen.findByText('2/2')
    })

    it('blättert bei einer Wischgeste nach rechts zum vorherigen Foto', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue(twoPhotos())

      renderPage('/projects/1/photos/2')
      const image = await screen.findByAltText('b.jpg')

      fireEvent.touchStart(image, { touches: [{ clientX: 100 }] })
      fireEvent.touchEnd(image, { changedTouches: [{ clientX: 200 }] })

      await screen.findByText('1/2')
    })

    /* Ohne diesen Fall bestuende auch ein Vergleich, der JEDE Beruehrung als Wisch liest - die
     * 50-px-Schwelle waere eine Zahl ohne Zusage. */
    it('navigiert unterhalb der 50-px-Schwelle nicht', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue(twoPhotos())

      renderPage('/projects/1/photos/1')
      const image = await screen.findByAltText('a.jpg')

      fireEvent.touchStart(image, { touches: [{ clientX: 200 }] })
      fireEvent.touchEnd(image, { changedTouches: [{ clientX: 170 }] })

      expect(screen.getByText('1/2')).toBeInTheDocument()
    })
  })

  // specs/features/0426-zeitversatz-je-kamera.md, UI/UX Punkt 3: eine NEUE Anzeigestelle - eine
  // Aufnahmezeit je Foto wurde zuvor nirgends gezeigt.
  describe('Abschnitt "Aufnahmezeit"', () => {
    const RECORDED = '2026-08-12T14:32:00'
    const EFFECTIVE = '2026-08-12T12:32:00'

    function takenAtSection(): HTMLElement {
      return screen.getByTestId('taken-at-section')
    }

    it('zeigt die WIRKSAME Zeit', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, taken_at: EFFECTIVE, taken_at_original: RECORDED })],
        total: 1,
      })

      renderPage('/projects/1/photos/1')

      await screen.findByAltText('a.jpg')
      expect(takenAtSection()).toHaveTextContent('12.08.2026, 12:32')
    })

    it('traegt die Marke "korrigiert" nur im Korrekturfall', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [
          photo({
            id: 1,
            taken_at: EFFECTIVE,
            taken_at_original: RECORDED,
            time_offset_minutes: -120,
          }),
        ],
        total: 1,
      })

      renderPage('/projects/1/photos/1')

      await screen.findByAltText('a.jpg')
      expect(within(takenAtSection()).getByText('korrigiert')).toBeInTheDocument()
    })

    it('traegt die Marke NICHT bei Versatz null', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, time_offset_minutes: 0 })],
        total: 1,
      })

      renderPage('/projects/1/photos/1')

      await screen.findByAltText('a.jpg')
      expect(within(takenAtSection()).queryByText('korrigiert')).toBeNull()
    })

    it('zeigt die aufgezeichnete Zeile samt Versatz nur im Korrekturfall', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [
          photo({
            id: 1,
            taken_at: EFFECTIVE,
            taken_at_original: RECORDED,
            time_offset_minutes: -120,
          }),
        ],
        total: 1,
      })

      renderPage('/projects/1/photos/1')

      await screen.findByAltText('a.jpg')
      const section = takenAtSection()
      expect(section).toHaveTextContent(/aufgezeichnet/)
      expect(section).toHaveTextContent('14:32')
      expect(section).toHaveTextContent('−2:00')
    })

    it('zeigt die aufgezeichnete Zeile NICHT bei Versatz null', async () => {
      // Bei gleichem Wert waere sie eine Wiederholung derselben Zeit - eine Aussage ohne Inhalt.
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, time_offset_minutes: 0 })],
        total: 1,
      })

      renderPage('/projects/1/photos/1')

      await screen.findByAltText('a.jpg')
      expect(takenAtSection()).not.toHaveTextContent(/aufgezeichnet/)
    })

    it('nennt die Kamera, wenn sie bestimmbar ist', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, camera: { id: 7, label: 'Canon EOS 5D' } })],
        total: 1,
      })

      renderPage('/projects/1/photos/1')

      await screen.findByAltText('a.jpg')
      expect(within(takenAtSection()).getByText('Canon EOS 5D')).toBeInTheDocument()
    })

    it('sagt als RUHIGER Satz, wenn keine Kamera bestimmbar ist', async () => {
      // Kein Fehlerton: `camera = null` ist ein regulaerer Zustand, kein Fehlen.
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, camera: null })],
        total: 1,
      })

      renderPage('/projects/1/photos/1')

      await screen.findByAltText('a.jpg')
      expect(
        within(takenAtSection()).getByText('Die Kamera dieses Fotos ist nicht bestimmbar.'),
      ).toBeInTheDocument()
      expect(within(takenAtSection()).queryByRole('alert')).toBeNull()
    })
  })

  // specs/features/0427-motive-mit-staerke.md, UI/UX-Abschnitt "Einzelbildansicht": die
  // permanente Sektion "Motive", nach dem Vorschlagskasten und VOR der Trennlinie. Seit PR 3 ist
  // sie der EINZIGE Bedienblock der Bewertungsdetails.
  describe('Sektion "Motive"', () => {
    it('zeigt die Sektion permanent, auch ohne Kopfzeile', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1 })],
        total: 1,
      })

      renderPage('/projects/1/photos/1')

      await screen.findByAltText('a.jpg')
      expect(within(motifSection()).getByRole('heading', { name: 'Motive' })).toBeInTheDocument()
    })

    it('zeigt den Satz statt der Liste, solange das Foto keinen Lauf gesehen hat', async () => {
      // Die KARDINALITAET Null, nicht eine Textsuche: der Satz kann ueber acht Nullzeilen stehen.
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, motif_assessment: null, motifs: [] })],
        total: 1,
      })

      renderPage('/projects/1/photos/1')

      await screen.findByAltText('a.jpg')
      expect(motifSection().querySelectorAll('[data-motif-key]')).toHaveLength(0)
      expect(within(motifSection()).getByText(/Noch nicht klassifiziert/)).toBeInTheDocument()
    })

    it('zeigt die acht Zeilen in Registry-Reihenfolge, sobald eine Kopfzeile vorliegt', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, motif_assessment: CLOUD_ASSESSMENT, motifs: motifStrengths() })],
        total: 1,
      })

      renderPage('/projects/1/photos/1')

      await screen.findByAltText('a.jpg')
      const keys = [...motifSection().querySelectorAll('[data-motif-key]')].map((node) =>
        node.getAttribute('data-motif-key'),
      )
      expect(keys).toEqual(MOTIF_KEYS)
    })

    it('steht nach dem Vorschlagskasten und vor der Trennlinie', async () => {
      // Letzter Bedienblock vor dem Informationsteil - damit Bewertungsleiste und Zurueck/Weiter
      // ohne Scrollen erreichbar bleiben.
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [
          photo({
            id: 1,
            suggestion: suggestion(),
            motif_assessment: CLOUD_ASSESSMENT,
            motifs: motifStrengths(),
          }),
        ],
        total: 1,
      })

      renderPage('/projects/1/photos/1')

      await screen.findByAltText('a.jpg')
      const suggestionBox = screen.getByText(/Automatischer Vorschlag/)
      const takenAt = screen.getByTestId('taken-at-section')
      const section = motifSection()
      expect(suggestionBox.compareDocumentPosition(section)).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
      expect(section.compareDocumentPosition(takenAt)).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
    })

    it('ist bedienbar: eine Korrektur geht an den Endpunkt', async () => {
      const user = userEvent.setup()
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, motif_assessment: CLOUD_ASSESSMENT, motifs: motifStrengths() })],
        total: 1,
      })
      vi.mocked(photosApi.setMotifCorrection).mockResolvedValue({
        photo_id: 1,
        motif_key: 'menschen',
        applies: false,
      })

      renderPage('/projects/1/photos/1')
      await screen.findByAltText('a.jpg')
      await user.click(
        within(motifSection()).getByRole('button', { name: 'Trifft nicht zu: Menschen' }),
      )

      await waitFor(() =>
        expect(photosApi.setMotifCorrection).toHaveBeenCalledWith(1, 'menschen', false),
      )
    })

    it('nimmt eine bestehende Korrektur zurueck', async () => {
      const user = userEvent.setup()
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [
          photo({
            id: 1,
            motif_assessment: CLOUD_ASSESSMENT,
            motifs: motifStrengths({ menschen: { strength: 0, correction: false } }),
          }),
        ],
        total: 1,
      })
      vi.mocked(photosApi.deleteMotifCorrection).mockResolvedValue(undefined)

      renderPage('/projects/1/photos/1')
      await screen.findByAltText('a.jpg')
      await user.click(
        within(motifSection()).getByRole('button', { name: 'Zurücknehmen: Menschen' }),
      )

      await waitFor(() =>
        expect(photosApi.deleteMotifCorrection).toHaveBeenCalledWith(1, 'menschen'),
      )
    })

    it('bietet fuer ein ausgeschlossenes Foto keinen Korrekturschalter an', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [
          photo({
            id: 1,
            motif_assessment: { ...CLOUD_ASSESSMENT, excluded_document: true },
            motifs: motifStrengths(),
          }),
        ],
        total: 1,
      })

      renderPage('/projects/1/photos/1')

      await screen.findByAltText('a.jpg')
      expect(
        within(motifSection()).getByText(/Als Dokument oder Bildschirmabbildung erkannt/),
      ).toBeInTheDocument()
      expect(within(motifSection()).queryByRole('button', { name: /Trifft/ })).toBeNull()
    })

    it('ist der EINZIGE Bedienblock der Bewertungsdetails', async () => {
      /* specs/features/0427-motive-mit-staerke.md, PR 3: mit den Kategorien sind die
       * Bedienelemente aus der Aufschlüsselung verschwunden. Als eigener Fall samt NEGATIVER
       * Assertion, weil ein stehengebliebener Bedienteil ohne Datengrundlage still leer bliebe
       * und damit von jedem Positivtest der Motivsektion unbemerkt. */
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [
          photo({
            id: 1,
            motif_assessment: CLOUD_ASSESSMENT,
            motifs: motifStrengths(),
            criterion_scores: [
              criterionScore({ criterion_key: 'landschaft', has_presence_threshold: true }),
            ],
            ranking: {
              event_id: 1,
              rank_score: 0.8,
              rank_position: 1,
              proposed: true,
              partition_size: 3,
              curation_position: null,
            },
          }),
        ],
        total: 1,
      })

      renderPage('/projects/1/photos/1')

      await screen.findByAltText('a.jpg')
      expect(screen.queryByTestId('category-controls-section')).toBeNull()
      expect(motifSection()).toBeInTheDocument()
      // Die Korrekturschalter der Motivliste sind die einzigen Bedienelemente der
      // Bewertungsdetails.
      expect(
        within(motifSection()).getAllByRole('button', { name: /^Trifft zu/ }).length,
      ).toBeGreaterThan(0)
    })
  })
})
