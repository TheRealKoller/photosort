import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as categoriesApi from '../api/categories'
import { ApiError } from '../api/client'
import * as photosApi from '../api/photos'
import * as ratingsApi from '../api/ratings'
import type { CriterionScoreOut, PhotoListOut, PhotoOut, RankingOut } from '../api/types'
import { setToken } from '../auth/token'
import { CANDIDATES_ALL_FILTERED_TEXT } from '../components/CurationCandidates'
import { CATEGORY_SET } from '../test/categorySetFixture'
import { DEFAULT_TOP_N } from '../utils/curationTopN'
import { PHOTOS_PAGE_SIZE } from '../hooks/usePhotos'
import {
  candidateCountOfCategory,
  candidateCountOfCluster,
  countPhotosInDay,
  CurateCategoriesPage,
  filterLowConfidence,
  formatCandidateCount,
  LOW_CONFIDENCE_EMPTY_TEXT,
  LOW_CONFIDENCE_THRESHOLD,
  toggleDayCollapse,
} from './CurateCategoriesPage'

vi.mock('../api/photos')
vi.mock('../api/ratings')
// specs/features/0289-feste-kategorien.md: die Anzeigenamen kommen zur Laufzeit ueber
// `GET /categories` - ohne Mock liefe die Seite im generischen Fallback und die deutschen
// Anzeigenamen des Sets waeren hier gar nicht pruefbar.
vi.mock('../api/categories')

function makeToken(payload: unknown): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
  const body = btoa(JSON.stringify(payload))
  return `${header}.${body}.signature-irrelevant`
}

/* specs/features/0300-nebenkategorien.md: `is_primary` und `curation_position` sind pflichtig.
 * Die Kuratierung zeigt eine Zugehoerigkeit genau dann, wenn `curation_position !== null` - der
 * Default `1` haelt damit alle Bestandsfaelle bei ihrer bisherigen Bedeutung (ein Foto, eine
 * Hauptzugehoerigkeit, in der Auswahl). */
function ranking(overrides: Partial<RankingOut> = {}): RankingOut {
  return {
    cluster_key: 'cluster-0',
    category_key: 'landscape',
    rank_score: 0.8,
    rank_position: 1,
    partition_size: 1,
    is_primary: true,
    curation_position: 1,
    ...overrides,
  }
}

/** Ein gerendertes Kachel-Vorkommen fuer die Unit-Tests von `countPhotosInDay`. */
function entry(photoOverrides: Partial<PhotoOut> = {}, rankingOverrides: Partial<RankingOut> = {}) {
  return { photo: photo(photoOverrides), ranking: ranking(rankingOverrides) }
}

function criterionScore(overrides: Partial<CriterionScoreOut> = {}): CriterionScoreOut {
  return {
    criterion_key: 'sharpness',
    display_name: 'Schärfe',
    value: 0.8,
    source: 'local_heuristic',
    // Default-Key ist `sharpness` (nicht kategoriefaehig) - der Default muss dazu passen,
    // damit kein Bestandstest unbemerkt in den Kategorien-Block rutscht (Spec 0209).
    category_eligible: false,
    ...overrides,
  }
}

function photo(overrides: Partial<PhotoOut> = {}): PhotoOut {
  return {
    id: 1,
    relative_path: 'a.jpg',
    // taken_at ist ein naives, zeitzonenloses Backend-Datetime ohne `Z`-Suffix (Spec 0039,
    // specs/architecture/0002-testkonzept.md) - die Fixture spiegelte das reale Format zuvor
    // fälschlich mit `Z` wider.
    taken_at: '2026-07-20T10:00:00',
    ratings: [],
    suggestion: null,
    rankings: [ranking()],
    criterion_scores: [],
    fine_labels: [],
    remote_category: null,
    // specs/features/0299-kategorie-konfidenz-anzeigen.md: Basiswert "keine Angabe".
    category_confidence: null,
    category_override: null,
    category_candidates: [],
    cloud_vision_status: [],
    ...overrides,
  }
}

describe('countPhotosInDay', () => {
  it('returns 0 for a day with no clusters', () => {
    expect(countPhotosInDay({})).toBe(0)
  })

  it('sums photos across every cluster and category of the day', () => {
    const clustersForDay = {
      'cluster-a': {
        landscape: [entry({ id: 1 }), entry({ id: 2 })],
        people: [entry({ id: 3 })],
      },
      'cluster-b': {
        landscape: [entry({ id: 4 })],
      },
    }

    expect(countPhotosInDay(clustersForDay)).toBe(4)
  })

  it('ignores categories whose pool is already exhausted (no entries)', () => {
    const clustersForDay = {
      'cluster-a': {
        landscape: [],
        people: [entry({ id: 1 })],
      },
    }

    expect(countPhotosInDay(clustersForDay)).toBe(1)
  })

  it('counts a photo that appears in two categories of the day only once', () => {
    /* specs/features/0300-nebenkategorien.md, Akzeptanzkriterium 26: die Beschriftung lautet
     * "N Fotos" - gezaehlt werden EINDEUTIGE FOTOS, nicht Zugehoerigkeiten. Ohne diese Zusage
     * stuende an einem Tag mit einem einzigen, doppelt gezeigten Foto "2 Fotos". */
    const clustersForDay = {
      'cluster-a': {
        landscape: [entry({ id: 1 }, { category_key: 'landscape' })],
        people: [entry({ id: 1 }, { category_key: 'people', is_primary: false })],
      },
    }

    expect(countPhotosInDay(clustersForDay)).toBe(1)
  })
})

// specs/features/0289-feste-kategorien.md: `sortCategoryKeys` ist nach `utils/categoryLabels.ts`
// gewandert (sie wird jetzt auch von der "Alle Kategorien"-Override-Auswahl gebraucht, nicht mehr
// nur von dieser Seite) - ihre Unit-Tests stehen entsprechend in `utils/categoryLabels.test.ts`.

describe('toggleDayCollapse', () => {
  it('adds a dayKey that is not yet in the set (collapses it)', () => {
    const result = toggleDayCollapse(new Set(), '2026-07-20')

    expect(result.has('2026-07-20')).toBe(true)
  })

  it('removes a dayKey that is already in the set (expands it)', () => {
    const result = toggleDayCollapse(new Set(['2026-07-20']), '2026-07-20')

    expect(result.has('2026-07-20')).toBe(false)
  })

  it('leaves other dayKeys in the set untouched', () => {
    const result = toggleDayCollapse(new Set(['2026-07-19', '2026-07-20']), '2026-07-20')

    expect(result.has('2026-07-19')).toBe(true)
    expect(result.has('2026-07-20')).toBe(false)
  })

  it('returns a new Set instance instead of mutating the argument', () => {
    const original = new Set<string>()

    const result = toggleDayCollapse(original, '2026-07-20')

    expect(result).not.toBe(original)
    expect(original.has('2026-07-20')).toBe(false)
  })
})

function renderPage(initialPath = '/projects/1/curate?topN=3') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  // `queryClient` wird mit zurueckgegeben (Erweiterung fuer Spec 0043): einzelne Tests loesen
  // damit gezielt einen Refetch aus (`queryClient.invalidateQueries(...)`), ohne denselben Pfad
  // wie eine echte Verwerfen-Mutation ueber die UI nachstellen zu muessen.
  return { ...render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/projects/:projectId" element={<p>Projekt-Detailseite</p>} />
        <Route path="/projects/:projectId/curate" element={<CurateCategoriesPage />} />
      </Routes>
    </MemoryRouter>,
    { wrapper }
  ), queryClient }
}

describe('CurateCategoriesPage', () => {
  beforeEach(() => {
    // window.matchMedia existiert in jsdom nicht (specs/architecture/0002-testkonzept.md) -
    // CriterionDetailsPopover fragt es beim Pointer-Enter des Info-Triggers ab, das auch
    // userEvent.click() vor dem eigentlichen Klick ausloest.
    vi.stubGlobal(
      'matchMedia',
      vi.fn().mockReturnValue({
        matches: false,
        media: '(hover: hover) and (pointer: fine)',
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })
    )
    vi.mocked(photosApi.listPhotos).mockReset()
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockReset()
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockResolvedValue('blob:fake-url')
    vi.mocked(ratingsApi.setRating).mockReset()
    vi.mocked(categoriesApi.listCategories).mockReset()
    vi.mocked(categoriesApi.listCategories).mockResolvedValue(CATEGORY_SET)
    setToken(makeToken({ sub: '1', username: 'testuser' }))
  })

  it('requests photos with the top-N from the query string', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [], total: 0 })

    renderPage('/projects/1/curate?topN=5')

    await waitFor(() =>
      expect(photosApi.listPhotos).toHaveBeenCalledWith(1, { topNPerCategory: 5 })
    )
  })

  it('defaults to the shared top-N when the query string is missing/invalid', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [], total: 0 })

    renderPage('/projects/1/curate')

    await waitFor(() =>
      // Die Konstante wird importiert, nicht abgeschrieben - den Zahlwert bindet GENAU EIN
      // Testfall, und der steht in utils/curationTopN.test.ts (Spec 0357, AK 3).
      expect(photosApi.listPhotos).toHaveBeenCalledWith(1, { topNPerCategory: DEFAULT_TOP_N })
    )
  })

  it('groups photos by day, then cluster, then category, showing day/cluster headings and the category chip/name', async () => {
    const list: PhotoListOut = {
      items: [
        photo({ id: 1, rankings: [ranking({ cluster_key: 'cluster-0', category_key: 'landscape' })] }),
        photo({ id: 2, rankings: [ranking({ cluster_key: 'cluster-0', category_key: 'people' })] }),
      ],
      total: 2,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

    renderPage()

    // Beide Fotos sind am 20.07.2026 (Montag) um 10:00 Uhr entstanden (Fixture-Default) - ein
    // Tag-Abschnitt, ein Cluster mit Tageszeit-Ueberschrift statt der technischen cluster_key-ID.
    expect(await screen.findByText('Montag 20.07.2026')).toBeInTheDocument()
    expect(screen.getByText('Vormittags (10:00 Uhr)')).toBeInTheDocument()
    expect(screen.queryByText('cluster-0')).not.toBeInTheDocument()
    expect(screen.getByText('Landscape')).toBeInTheDocument()
    expect(screen.getByText('People')).toBeInTheDocument()
    expect(screen.getAllByRole('listitem').length).toBeGreaterThanOrEqual(2)
  })

  it('groups photos into day sections sorted chronologically ascending (Akzeptanzkriterium 1)', async () => {
    const list: PhotoListOut = {
      items: [
        photo({
          id: 1,
          taken_at: '2026-07-21T10:00:00',
          rankings: [ranking({ cluster_key: 'cluster-b', category_key: 'landscape' })],
        }),
        photo({
          id: 2,
          taken_at: '2026-07-20T10:00:00',
          rankings: [ranking({ cluster_key: 'cluster-a', category_key: 'landscape' })],
        }),
      ],
      total: 2,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

    renderPage()

    // Die Tages-Kopfzeile ist seit Spec 0043 ein <button> innerhalb des <h2> (klappbarer
    // Trigger, dessen textContent zusätzlich das rein dekorative Auf-/Zuklapp-Symbol enthält) -
    // die Reihenfolge wird deshalb per Regex auf den Wochentag/Datum-Teil geprüft statt über
    // exakte Gleichheit des rohen h2-textContent.
    const headings = await screen.findAllByRole('heading', { level: 2 })
    const dayLabels = headings.map(
      (heading) => heading.textContent?.match(/(Montag|Dienstag) \d{2}\.\d{2}\.\d{4}/)?.[0]
    )
    expect(dayLabels).toEqual(['Montag 20.07.2026', 'Dienstag 21.07.2026'])
  })

  it(
    'sorts clusters within a day chronologically by earliest taken_at, not lexicographically ' +
      'by cluster_key (Akzeptanzkriterium 2, behebt "cluster-10" < "cluster-2")',
    async () => {
      const list: PhotoListOut = {
        items: [
          photo({
            id: 1,
            taken_at: '2026-07-20T14:00:00',
            rankings: [ranking({ cluster_key: 'cluster-10', category_key: 'landscape' })],
          }),
          photo({
            id: 2,
            taken_at: '2026-07-20T09:00:00',
            rankings: [ranking({ cluster_key: 'cluster-2', category_key: 'landscape' })],
          }),
        ],
        total: 2,
      }
      vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

      renderPage()

      const headings = await screen.findAllByRole('heading', { level: 3 })
      expect(headings.map((heading) => heading.textContent)).toEqual([
        'Vormittags (09:00 Uhr)',
        'Nachmittags (14:00 Uhr)',
      ])
    }
  )

  it(
    'derives day and time-of-day bucket from the earliest photo for a midnight-spanning ' +
      'cluster, while the displayed range covers all visible photos (Akzeptanzkriterium 6)',
    async () => {
      const list: PhotoListOut = {
        items: [
          photo({
            id: 1,
            taken_at: '2026-07-21T00:10:00',
            rankings: [ranking({ cluster_key: 'cluster-0', category_key: 'landscape' })],
          }),
          photo({
            id: 2,
            taken_at: '2026-07-20T23:50:00',
            rankings: [ranking({ cluster_key: 'cluster-0', category_key: 'people' })],
          }),
        ],
        total: 2,
      }
      vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

      renderPage()

      expect(await screen.findByText('Montag 20.07.2026')).toBeInTheDocument()
      expect(screen.getByText('Nachts (23:50–00:10 Uhr)')).toBeInTheDocument()
    }
  )

  it('shows an empty-pool placeholder when a category has fewer than N photos', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue({
      items: [photo({ id: 1 })],
      total: 1,
    })

    renderPage('/projects/1/curate?topN=3')

    expect(await screen.findByText('Kein weiteres Foto verfügbar')).toBeInTheDocument()
  })

  it('shows a loading skeleton while fetching', () => {
    vi.mocked(photosApi.listPhotos).mockReturnValue(new Promise(() => {}))

    renderPage()

    const status = screen.getByRole('status')
    expect(status.tagName).toBe('UL')
  })

  it('shows an inline error banner with a retry option on failure', async () => {
    vi.mocked(photosApi.listPhotos).mockRejectedValue(new ApiError(500, 'Serverfehler'))

    renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent('Serverfehler')
  })

  it('shows an explanatory empty state before any curation data exists', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [], total: 0 })

    renderPage()

    expect(
      await screen.findByText(/noch keine kategorie-kuratierung verfügbar/i)
    ).toBeInTheDocument()
  })

  it('rejects a photo and keeps its tile in place, marked as rejected', async () => {
    /* Nachfolger von `rejects a photo and shows a skeleton in its tile until the backfilled photo
     * arrives` (specs/features/0357-voller-bildvorrat-kuratierung.md, ADR 0071 Entscheidung 1/3):
     * derselbe Aufbau, umgekehrte Erwartung. Es rueckt nichts mehr nach, und der Skeleton-Tausch
     * ueberbrueckte einen Reflow, den es nicht mehr gibt. Die zuvor gemockte zweite Antwort OHNE
     * das Foto ist serverseitig unmoeglich geworden; sie traegt es jetzt samt seiner Bewertung. */
    vi.mocked(photosApi.listPhotos)
      .mockResolvedValueOnce({
        items: [photo({ id: 1, rankings: [ranking({ rank_position: 1 })] })],
        total: 1,
      })
      .mockResolvedValue({
        items: [
          photo({
            id: 1,
            ratings: [{ user_id: 1, username: 'testuser', status: 'rejected' }],
            rankings: [ranking({ rank_position: 1 })],
          }),
        ],
        total: 1,
      })
    vi.mocked(ratingsApi.setRating).mockResolvedValue({
      user_id: 1,
      username: 'testuser',
      status: 'rejected',
    })
    const user = userEvent.setup()

    renderPage()
    const rejectButton = await screen.findByRole('button', { name: 'Verwerfen: a.jpg' })
    await user.click(rejectButton)

    expect(ratingsApi.setRating).toHaveBeenCalledWith(1, 'rejected')
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Verworfen: a.jpg' })).toBeInTheDocument()
    )
    expect(screen.getByText('a.jpg')).toBeInTheDocument()
  })

  it(
    'keeps the day and cluster sections visible when a category override empties their only ' +
      'partition (Akzeptanzkriterium 7 der Spec 0043, umgehaengt auf den einzigen verbliebenen ' +
      'Ausloeser)',
    async () => {
      /* Dieser Fall stellte den Erschoepfungs-Leerzustand zuvor ueber eine zweite
       * `listPhotos`-Antwort OHNE das gerade abgelehnte Foto her. So antwortet der Server seit
       * specs/features/0357-voller-bildvorrat-kuratierung.md nie mehr - der Test haette eine
       * Fiktion geprueft und `knownGroupKeysRef` scheinbar abgedeckt. Er haengt deshalb am
       * Kategorie-Override, der die Partition eines Fotos tatsaechlich noch wechselt.
       *
       * Ausdruecklich mit erfasst: Ein TAG kann seit dieser Story gar nicht mehr leerlaufen - der
       * Override verschiebt das Foto innerhalb desselben Clusters. Die Negativ-Assertion auf
       * "Keine Fotos für diesen Tag" haelt genau das fest, statt es stillschweigend zu lassen. */
      vi.mocked(photosApi.listPhotos)
        .mockResolvedValueOnce({
          items: [
            photo({
              id: 1,
              criterion_scores: [criterionScore()],
              rankings: [ranking({ cluster_key: 'cluster-0', category_key: 'landscape' })],
              category_candidates: [
                { category_key: 'tier', origin: 'remote', provider: 'anthropic', confidence: null },
                { category_key: 'menschen', origin: 'local', provider: null, confidence: null },
              ],
            }),
          ],
          total: 1,
        })
        .mockResolvedValue({
          items: [
            photo({
              id: 1,
              category_override: 'tier',
              criterion_scores: [criterionScore()],
              rankings: [ranking({ cluster_key: 'cluster-0', category_key: 'tier' })],
              category_candidates: [
                { category_key: 'tier', origin: 'remote', provider: 'anthropic', confidence: null },
                { category_key: 'menschen', origin: 'local', provider: null, confidence: null },
              ],
            }),
          ],
          total: 1,
        })
      vi.mocked(photosApi.setCategoryOverride).mockResolvedValue({
        photo_id: 1,
        category_key: 'tier',
      })
      const user = userEvent.setup()

      renderPage('/projects/1/curate?topN=1')
      await screen.findByRole('button', { name: 'Bewertungsdetails anzeigen' })
      await user.click(screen.getByRole('button', { name: 'Bewertungsdetails anzeigen' }))
      const tierRow = screen.getByTestId('category-candidate-row-tier')
      await user.click(within(tierRow).getByRole('button', { name: /^übernehmen$/i }))

      await waitFor(() => expect(screen.getByText('Tier')).toBeInTheDocument())
      expect(screen.getByText('Montag 20.07.2026')).toBeInTheDocument()
      expect(screen.getByText('Vormittags (10:00 Uhr)')).toBeInTheDocument()
      // Die leergelaufene Kategorie bleibt sichtbar, statt spurlos zu verschwinden.
      expect(screen.getByText('Landscape')).toBeInTheDocument()
      expect(screen.getByText('Kein weiteres Foto verfügbar')).toBeInTheDocument()
      expect(screen.queryByText('Keine Fotos für diesen Tag')).not.toBeInTheDocument()
    }
  )

  it(
    'keeps a category section visible with the unchanged empty-pool placeholder once a category ' +
      'override empties it, while a sibling category in the same cluster still has photos ' +
      '(Akzeptanzkriterium 7, Kategorie-Ebene)',
    async () => {
      // Zweiter der drei auf den Kategorie-Override umgehaengten Faelle - siehe die Begruendung
      // im vorigen Testfall.
      vi.mocked(photosApi.listPhotos)
        .mockResolvedValueOnce({
          items: [
            photo({
              id: 1,
              criterion_scores: [criterionScore()],
              rankings: [ranking({ cluster_key: 'cluster-0', category_key: 'landscape' })],
              category_candidates: [
                { category_key: 'tier', origin: 'remote', provider: 'anthropic', confidence: null },
                { category_key: 'menschen', origin: 'local', provider: null, confidence: null },
              ],
            }),
            photo({
              id: 2,
              relative_path: 'b.jpg',
              rankings: [ranking({ cluster_key: 'cluster-0', category_key: 'people' })],
            }),
          ],
          total: 2,
        })
        .mockResolvedValue({
          items: [
            photo({
              id: 1,
              category_override: 'tier',
              criterion_scores: [criterionScore()],
              rankings: [ranking({ cluster_key: 'cluster-0', category_key: 'tier' })],
              category_candidates: [
                { category_key: 'tier', origin: 'remote', provider: 'anthropic', confidence: null },
                { category_key: 'menschen', origin: 'local', provider: null, confidence: null },
              ],
            }),
            photo({
              id: 2,
              relative_path: 'b.jpg',
              rankings: [ranking({ cluster_key: 'cluster-0', category_key: 'people' })],
            }),
          ],
          total: 2,
        })
      vi.mocked(photosApi.setCategoryOverride).mockResolvedValue({
        photo_id: 1,
        category_key: 'tier',
      })
      const user = userEvent.setup()

      renderPage('/projects/1/curate?topN=1')
      await screen.findByRole('button', { name: 'Bewertungsdetails anzeigen' })
      await user.click(screen.getByRole('button', { name: 'Bewertungsdetails anzeigen' }))
      const tierRow = screen.getByTestId('category-candidate-row-tier')
      await user.click(within(tierRow).getByRole('button', { name: /^übernehmen$/i }))

      await waitFor(() => expect(screen.getByText('Tier')).toBeInTheDocument())
      expect(screen.getByText('Montag 20.07.2026')).toBeInTheDocument()
      expect(screen.getByText('Vormittags (10:00 Uhr)')).toBeInTheDocument()
      expect(screen.getByText('Landscape')).toBeInTheDocument()
      expect(screen.getByText('People')).toBeInTheDocument()
      expect(screen.getByText('Kein weiteres Foto verfügbar')).toBeInTheDocument()
      expect(screen.queryByText('Keine Fotos in dieser Tageszeit')).not.toBeInTheDocument()
    }
  )

  it(
    'keeps every cluster heading of the day intact after a category override, including the one ' +
      'whose category ran empty (Regressionstest laut Architektur-Abschnitt der Spec)',
    async () => {
      // Dritter der drei umgehaengten Faelle. Die Cluster-Ueberschriften bleiben vollstaendig und
      // in chronologischer Reihenfolge - ein Cluster selbst kann seit dieser Story nicht mehr
      // leerlaufen (der Override verschiebt nur die Kategorie), sein Abschnitt darf aber auch
      // durch die Umsortierung der Kategorien nicht verlorengehen.
      vi.mocked(photosApi.listPhotos)
        .mockResolvedValueOnce({
          items: [
            photo({
              id: 1,
              taken_at: '2026-07-20T09:00:00',
              criterion_scores: [criterionScore()],
              rankings: [ranking({ cluster_key: 'cluster-a', category_key: 'landscape' })],
              category_candidates: [
                { category_key: 'tier', origin: 'remote', provider: 'anthropic', confidence: null },
                { category_key: 'menschen', origin: 'local', provider: null, confidence: null },
              ],
            }),
            photo({
              id: 2,
              relative_path: 'b.jpg',
              taken_at: '2026-07-20T14:00:00',
              rankings: [ranking({ cluster_key: 'cluster-b', category_key: 'landscape' })],
            }),
          ],
          total: 2,
        })
        .mockResolvedValue({
          items: [
            photo({
              id: 1,
              taken_at: '2026-07-20T09:00:00',
              category_override: 'tier',
              criterion_scores: [criterionScore()],
              rankings: [ranking({ cluster_key: 'cluster-a', category_key: 'tier' })],
              category_candidates: [
                { category_key: 'tier', origin: 'remote', provider: 'anthropic', confidence: null },
                { category_key: 'menschen', origin: 'local', provider: null, confidence: null },
              ],
            }),
            photo({
              id: 2,
              relative_path: 'b.jpg',
              taken_at: '2026-07-20T14:00:00',
              rankings: [ranking({ cluster_key: 'cluster-b', category_key: 'landscape' })],
            }),
          ],
          total: 2,
        })
      vi.mocked(photosApi.setCategoryOverride).mockResolvedValue({
        photo_id: 1,
        category_key: 'tier',
      })
      const user = userEvent.setup()

      renderPage('/projects/1/curate?topN=1')
      await screen.findByRole('button', { name: 'Bewertungsdetails anzeigen' })
      await user.click(screen.getByRole('button', { name: 'Bewertungsdetails anzeigen' }))
      const tierRow = screen.getByTestId('category-candidate-row-tier')
      await user.click(within(tierRow).getByRole('button', { name: /^übernehmen$/i }))

      await waitFor(() => expect(screen.getByText('Tier')).toBeInTheDocument())
      expect(screen.getByText('Montag 20.07.2026')).toBeInTheDocument()

      const clusterHeadings = screen.getAllByRole('heading', { level: 3 })
      expect(clusterHeadings.map((heading) => heading.textContent)).toEqual([
        'Vormittags (09:00 Uhr)',
        'Nachmittags (14:00 Uhr)',
      ])
    }
  )

  it('shows a quality meter derived from rank_score', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue({
      items: [photo({ id: 1, rankings: [ranking({ rank_score: 0.9 })] })],
      total: 1,
    })

    renderPage()

    expect(await screen.findByText('Hohe Bildqualität')).toBeInTheDocument()
  })

  // Spec 0040 (Bewertungsdetails-Info-Popover), Akzeptanzkriterien 1, 2.
  /*
   * specs/features/0298-projektnavigation-in-der-kopfzeile.md (AK10): "Zurück zum Projekt" am
   * Seitenende entfaellt ersatzlos - die Kopfzeile traegt die Projektnavigation jetzt auf jeder
   * Projektseite, und /curate hat damit zum ersten Mal ueberhaupt Projektkontext (AK2). Nach dem
   * etablierten Muster der gleichlautenden Regressionstests in PhotoGridPage/PhotoComparePage.
   */
  it('no longer renders its own "Zurück zum Projekt" link (AK10)', async () => {
    const list: PhotoListOut = {
      items: [photo({ id: 1, rankings: [ranking({ category_key: 'landscape' })] })],
      total: 1,
    }
    vi.mocked(photosApi.listPhotos).mockResolvedValue(list)

    renderPage()

    // Auf gerenderten Seiteninhalt warten, bevor die Abwesenheits-Assertion greift - sonst
    // bestuende der Test allein deshalb, weil die Seite noch laedt.
    expect(await screen.findByText('Montag 20.07.2026')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /zurück zum projekt/i })).not.toBeInTheDocument()
  })

  describe('info popover trigger', () => {
    it('shows the trigger when the photo has criterion_scores', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, criterion_scores: [criterionScore()] })],
        total: 1,
      })

      renderPage()

      expect(
        await screen.findByRole('button', { name: 'Bewertungsdetails anzeigen' })
      ).toBeInTheDocument()
    })

    it('does not show the trigger when criterion_scores is empty', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, criterion_scores: [] })],
        total: 1,
      })

      renderPage()

      await screen.findAllByRole('listitem')
      expect(
        screen.queryByRole('button', { name: 'Bewertungsdetails anzeigen' })
      ).not.toBeInTheDocument()
    })
  })

  // Spec 0043 (Kuratierung: Tage auf-/zuklappbar).
  describe('collapsible day sections (Spec 0043)', () => {
    function twoCategoryDayList(): PhotoListOut {
      return {
        items: [
          photo({ id: 1, rankings: [ranking({ cluster_key: 'cluster-0', category_key: 'landscape' })] }),
          photo({ id: 2, rankings: [ranking({ cluster_key: 'cluster-0', category_key: 'people' })] }),
        ],
        total: 2,
      }
    }

    it('renders every day header as an expanded trigger by default (Akzeptanzkriterium 2)', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue(twoCategoryDayList())

      renderPage()

      const trigger = await screen.findByRole('button', { name: 'Montag 20.07.2026' })
      expect(trigger).toHaveAttribute('aria-expanded', 'true')
      // Kein Kurzinfo-Text im aufgeklappten Zustand (Akzeptanzkriterium 5).
      expect(screen.queryByText(/\(\d+ Fotos\)/)).not.toBeInTheDocument()
      // Cluster-/Kategorie-Teilbaum ist sichtbar.
      expect(screen.getByText('Landscape')).toBeInTheDocument()
    })

    it(
      'collapses only the clicked day on trigger click, removes its subtree from the DOM and ' +
        'shows the (X Fotos) short info, leaving other days untouched (Akzeptanzkriterien 1, 3, 4, 5, 6)',
      async () => {
        const list: PhotoListOut = {
          items: [
            ...twoCategoryDayList().items,
            // Bewusst ein anderer Zeitstempel/Bucket (Nachmittags statt Vormittags) als der
            // Montags-Cluster, damit sich die beiden Tage per eindeutiger Cluster-Ueberschrift
            // unterscheiden lassen statt ueber die (in beiden Tagen gleich benannte)
            // Kategorie "Landscape".
            photo({
              id: 3,
              taken_at: '2026-07-21T14:00:00',
              rankings: [ranking({ cluster_key: 'cluster-1', category_key: 'landscape' })],
            }),
          ],
          total: 3,
        }
        vi.mocked(photosApi.listPhotos).mockResolvedValue(list)
        const user = userEvent.setup()

        renderPage()
        const mondayTrigger = await screen.findByRole('button', { name: 'Montag 20.07.2026' })
        const tuesdayTrigger = screen.getByRole('button', { name: 'Dienstag 21.07.2026' })
        expect(screen.getByText('Vormittags (10:00 Uhr)')).toBeInTheDocument()
        expect(screen.getByText('Nachmittags (14:00 Uhr)')).toBeInTheDocument()

        await user.click(mondayTrigger)

        expect(mondayTrigger).toHaveAttribute('aria-expanded', 'false')
        expect(screen.getByRole('button', { name: 'Montag 20.07.2026 (2 Fotos)' })).toBe(
          mondayTrigger
        )
        // Teilbaum ist nicht nur CSS-versteckt, sondern per conditional JSX gar nicht gerendert.
        expect(screen.queryByText('Vormittags (10:00 Uhr)')).not.toBeInTheDocument()
        expect(screen.queryByText('People')).not.toBeInTheDocument()
        // Der andere Tag bleibt unveraendert aufgeklappt.
        expect(tuesdayTrigger).toHaveAttribute('aria-expanded', 'true')
        expect(screen.getByText('Nachmittags (14:00 Uhr)')).toBeInTheDocument()
      }
    )

    it(
      'shows the correct (0 Fotos) short info for a collapsed empty day and hides its ' +
        'empty-state text (Akzeptanzkriterium 8)',
      async () => {
        vi.mocked(photosApi.listPhotos)
          .mockResolvedValueOnce({
            items: [photo({ id: 1, rankings: [ranking({ cluster_key: 'cluster-0' })] })],
            total: 1,
          })
          .mockResolvedValueOnce({ items: [], total: 0 })
        vi.mocked(ratingsApi.setRating).mockResolvedValue({
          user_id: 1,
          username: 'testuser',
          status: 'rejected',
        })
        const user = userEvent.setup()

        renderPage('/projects/1/curate?topN=1')
        const rejectButton = await screen.findByRole('button', { name: 'Verwerfen: a.jpg' })
        await user.click(rejectButton)
        await waitFor(() =>
          expect(screen.queryByRole('button', { name: 'Verwerfen: a.jpg' })).not.toBeInTheDocument()
        )
        expect(screen.getByText('Keine Fotos für diesen Tag')).toBeInTheDocument()

        const trigger = screen.getByRole('button', { name: 'Montag 20.07.2026' })
        await user.click(trigger)

        expect(trigger).toHaveAttribute('aria-expanded', 'false')
        expect(screen.getByRole('button', { name: 'Montag 20.07.2026 (0 Fotos)' })).toBeInTheDocument()
        expect(screen.queryByText('Keine Fotos für diesen Tag')).not.toBeInTheDocument()
      }
    )

    it(
      'sets aria-expanded/aria-controls correctly and links the trigger to an existing panel ' +
        'id while expanded (Akzeptanzkriterium 11)',
      async () => {
        vi.mocked(photosApi.listPhotos).mockResolvedValue(twoCategoryDayList())

        renderPage()

        const trigger = await screen.findByRole('button', { name: 'Montag 20.07.2026' })
        const controlsId = trigger.getAttribute('aria-controls')
        expect(controlsId).toBeTruthy()
        expect(trigger).toHaveAttribute('aria-expanded', 'true')
        // eslint-disable-next-line testing-library/no-node-access -- Verifiziert die aria-controls-Verknuepfung selbst per ID-Lookup, kein Ersatz fuer eine Rollen-Query.
        expect(document.getElementById(controlsId as string)).not.toBeNull()
      }
    )

    it(
      'renders two always-visible global "expand/collapse all" buttons above the day list that ' +
        'work with a single day in the project (Akzeptanzkriterium 7)',
      async () => {
        vi.mocked(photosApi.listPhotos).mockResolvedValue(twoCategoryDayList())
        const user = userEvent.setup()

        renderPage()
        const dayTrigger = await screen.findByRole('button', { name: 'Montag 20.07.2026' })
        const collapseAll = screen.getByRole('button', { name: 'Alle Tage zuklappen' })
        const expandAll = screen.getByRole('button', { name: 'Alle Tage aufklappen' })

        await user.click(collapseAll)
        expect(dayTrigger).toHaveAttribute('aria-expanded', 'false')

        await user.click(expandAll)
        expect(dayTrigger).toHaveAttribute('aria-expanded', 'true')
      }
    )

    it(
      'does not retroactively collapse a dayKey that appears only after "Alle Tage zuklappen" ' +
        'was clicked (Akzeptanzkriterium 10)',
      async () => {
        vi.mocked(photosApi.listPhotos)
          .mockResolvedValueOnce({
            items: [photo({ id: 1, rankings: [ranking({ cluster_key: 'cluster-0' })] })],
            total: 1,
          })
          .mockResolvedValueOnce({
            items: [
              photo({ id: 1, rankings: [ranking({ cluster_key: 'cluster-0' })] }),
              photo({
                id: 2,
                taken_at: '2026-07-21T10:00:00',
                rankings: [ranking({ cluster_key: 'cluster-1' })],
              }),
            ],
            total: 2,
          })
        const user = userEvent.setup()

        const { queryClient } = renderPage()
        await screen.findByRole('button', { name: 'Montag 20.07.2026' })
        await user.click(screen.getByRole('button', { name: 'Alle Tage zuklappen' }))
        expect(screen.getByRole('button', { name: /Montag 20\.07\.2026/ })).toHaveAttribute(
          'aria-expanded',
          'false'
        )

        // Der neue Tag "erscheint" ueber denselben Invalidierungs-/Refetch-Pfad, den auch eine
        // echte Verwerfen-Mutation ausloest (useSetRatingMutation:
        // `queryClient.invalidateQueries({ queryKey: ['photos', projectId] })`) - hier direkt
        // ausgeloest, um unabhaengig vom (im zugeklappten Zustand ohnehin unsichtbaren)
        // Verwerfen-Button ausschliesslich das Klapp-Verhalten des neuen Tages zu pruefen.
        await act(async () => {
          await queryClient.invalidateQueries({ queryKey: ['photos', 1] })
        })

        await screen.findByRole('button', { name: 'Dienstag 21.07.2026' })

        expect(screen.getByRole('button', { name: /Montag 20\.07\.2026/ })).toHaveAttribute(
          'aria-expanded',
          'false'
        )
        expect(screen.getByRole('button', { name: 'Dienstag 21.07.2026' })).toHaveAttribute(
          'aria-expanded',
          'true'
        )
      }
    )

    it(
      'live-updates the (X Fotos) short info of a collapsed day once its last visible photo ' +
        'resolves as rejected, without changing any collapse state (Akzeptanzkriterium 9)',
      async () => {
        let resolveRefetch: (value: PhotoListOut) => void = () => {}
        vi.mocked(photosApi.listPhotos)
          .mockResolvedValueOnce({
            items: [photo({ id: 1, rankings: [ranking({ cluster_key: 'cluster-0' })] })],
            total: 1,
          })
          .mockReturnValueOnce(
            new Promise((resolve) => {
              resolveRefetch = resolve
            })
          )
        vi.mocked(ratingsApi.setRating).mockResolvedValue({
          user_id: 1,
          username: 'testuser',
          status: 'rejected',
        })
        const user = userEvent.setup()

        renderPage('/projects/1/curate?topN=1')
        const rejectButton = await screen.findByRole('button', { name: 'Verwerfen: a.jpg' })
        await user.click(rejectButton)
        // Kurzinfo erscheint erst nach dem Zuklappen (Akzeptanzkriterium 5) - vorher traegt der
        // Trigger noch keine Fotoanzahl im Namen.
        const trigger = screen.getByRole('button', { name: 'Montag 20.07.2026' })
        await user.click(trigger)
        expect(trigger).toHaveAttribute('aria-expanded', 'false')
        expect(trigger).toHaveTextContent('(1 Fotos)')

        resolveRefetch({ items: [], total: 0 })

        await waitFor(() =>
          expect(
            screen.getByRole('button', { name: 'Montag 20.07.2026 (0 Fotos)' })
          ).toBeInTheDocument()
        )
        expect(
          screen.getByRole('button', { name: 'Montag 20.07.2026 (0 Fotos)' })
        ).toHaveAttribute('aria-expanded', 'false')
      }
    )

    it(
      'leaves no permanently hanging skeleton tile after collapsing and re-expanding a day ' +
        'while its reject mutation is still pending (Akzeptanzkriterium 12)',
      async () => {
        let resolveRefetch: (value: PhotoListOut) => void = () => {}
        vi.mocked(photosApi.listPhotos)
          .mockResolvedValueOnce({
            items: [photo({ id: 1, rankings: [ranking({ rank_position: 1 })] })],
            total: 1,
          })
          .mockReturnValueOnce(
            new Promise((resolve) => {
              resolveRefetch = resolve
            })
          )
        vi.mocked(ratingsApi.setRating).mockResolvedValue({
          user_id: 1,
          username: 'testuser',
          status: 'rejected',
        })
        const user = userEvent.setup()

        renderPage()
        const rejectButton = await screen.findByRole('button', { name: 'Verwerfen: a.jpg' })
        await user.click(rejectButton)

        // Kurzinfo erscheint erst nach dem Zuklappen (Akzeptanzkriterium 5), der Trigger wird
        // deshalb ueber seinen aufgeklappten Namen gefunden - `trigger` bleibt danach dieselbe
        // DOM-Referenz, unabhaengig vom sich aendernden zugaenglichen Namen.
        const trigger = screen.getByRole('button', { name: 'Montag 20.07.2026' })
        await user.click(trigger) // collapse while the mutation is still pending
        expect(trigger).toHaveTextContent('(1 Fotos)')
        await user.click(trigger) // expand again, still pending

        resolveRefetch({
          items: [photo({ id: 2, relative_path: 'b.jpg', rankings: [ranking({ rank_position: 2 })] })],
          total: 1,
        })

        await waitFor(() =>
          expect(screen.getByRole('button', { name: 'Verwerfen: b.jpg' })).toBeInTheDocument()
        )
        expect(screen.queryByRole('button', { name: 'Verwerfen: a.jpg' })).not.toBeInTheDocument()
        expect(screen.queryByTestId('button-spinner')).not.toBeInTheDocument()
      }
    )
  })

  // specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, UI/UX-Abschnitt.
  // Der Auffangkorb ist seit specs/features/0289-feste-kategorien.md ein regulaerer Eintrag des
  // festen Sets (`nicht_erkannt`) und kein Sonderwert mehr - der Altwert `"unerkannt"` aus der
  // Laufhistorie faellt hier bewusst NICHT mehr darunter (die Historie wird nicht migriert).
  describe('catch-all section "Nicht erkannt" (specs/features/0217)', () => {
    const EXPLANATION = 'Für diese Fotos war kein Bildmotiv sicher bestimmbar.'

    it('renders the catch-all section with its neutral explanation when every photo is unrecognized', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, rankings: [ranking({ category_key: 'nicht_erkannt' })] })],
        total: 1,
      })

      renderPage()

      expect(await screen.findByText('Nicht erkannt')).toBeInTheDocument()
      const explanation = screen.getByText(EXPLANATION)
      expect(explanation).toBeInTheDocument()
      // Kein Fehler, sondern ein fehlendes Erkennungsergebnis - keine Fehler-Semantik.
      expect(explanation).not.toHaveAttribute('role', 'alert')
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    })

    it('places the catch-all section after the regular categories of the same cluster', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [
          photo({
            id: 1,
            rankings: [ranking({ cluster_key: 'cluster-0', category_key: 'nicht_erkannt' })],
          }),
          photo({
            id: 2,
            rankings: [ranking({ cluster_key: 'cluster-0', category_key: 'tier' })],
          }),
        ],
        total: 2,
      })

      renderPage()

      const catchAll = await screen.findByText('Nicht erkannt')
      const regular = screen.getByText('Tier')
      // "Nicht erkannt" waere alphabetisch VOR "Tier" - der Auffang-Abschnitt steht trotzdem
      // hinten, weil `sortCategoryKeys` ihn immer zuletzt einsortiert.
      expect(regular.compareDocumentPosition(catchAll)).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
      expect(screen.getByText(EXPLANATION)).toBeInTheDocument()
    })

    it('shows no explanation at all when no photo is unrecognized', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, rankings: [ranking({ category_key: 'tier' })] })],
        total: 1,
      })

      renderPage()

      expect(await screen.findByText('Tier')).toBeInTheDocument()
      expect(screen.queryByText('Nicht erkannt')).not.toBeInTheDocument()
      expect(screen.queryByText(EXPLANATION)).not.toBeInTheDocument()
    })
  })

  describe('category override', () => {
    it('shows the override marker for a photo with an active override', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [photo({ id: 1, category_override: 'hund' })],
        total: 1,
      })

      renderPage()

      expect(await screen.findByLabelText('Kategorie manuell übersteuert')).toBeInTheDocument()
    })

    it('overrides the category from the info popover', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue({
        items: [
          photo({
            id: 1,
            criterion_scores: [criterionScore()],
            rankings: [ranking({ category_key: 'people' })],
            category_candidates: [
              { category_key: 'tier', origin: 'remote', provider: 'anthropic', confidence: null },
              { category_key: 'menschen', origin: 'local', provider: null, confidence: null },
            ],
          }),
        ],
        total: 1,
      })
      vi.mocked(photosApi.setCategoryOverride).mockResolvedValue({
        photo_id: 1,
        category_key: 'tier',
      })
      const user = userEvent.setup()

      renderPage()
      await screen.findByRole('button', { name: 'Bewertungsdetails anzeigen' })
      await user.click(screen.getByRole('button', { name: 'Bewertungsdetails anzeigen' }))
      // Gezielt die Zeile des Kandidaten "tier" - beide Kandidatenzeilen tragen eine
      // "Uebernehmen"-Schaltflaeche, eine rollenweite Suche waere mehrdeutig.
      const tierRow = screen.getByTestId('category-candidate-row-tier')
      await user.click(within(tierRow).getByRole('button', { name: /^übernehmen$/i }))

      await waitFor(() => expect(photosApi.setCategoryOverride).toHaveBeenCalledWith(1, 'tier'))
    })
  })
})


// specs/features/0299-kategorie-konfidenz-anzeigen.md, Akzeptanzkriterium 5
describe('LOW_CONFIDENCE_THRESHOLD / filterLowConfidence', () => {
  it('haelt die Schwelle bei 60 %', () => {
    expect(LOW_CONFIDENCE_THRESHOLD).toBe(0.6)
  })

  it('behaelt nur Fotos mit einer Sicherheit ECHT unter der Schwelle', () => {
    // Die Schwelle ist exklusiv: `0.6` selbst gilt nicht als niedrig.
    const items = [
      photo({ id: 1, category_confidence: 0.599 }),
      photo({ id: 2, category_confidence: 0.6 }),
      photo({ id: 3, category_confidence: 0.9 }),
      photo({ id: 4, category_confidence: 0 }),
    ]

    expect(filterLowConfidence(items).map((p) => p.id)).toEqual([1, 4])
  })

  it('verwirft Fotos OHNE Angabe', () => {
    // Produktentscheidung: ein Foto ohne Zahl ist keine unsichere Zuordnung, sondern eine
    // unbekannte - `null` darf nicht wie `0` behandelt werden.
    const items = [photo({ id: 1, category_confidence: null }), photo({ id: 2, category_confidence: 0.1 })]

    expect(filterLowConfidence(items).map((p) => p.id)).toEqual([2])
  })

  it('mutiert die uebergebene Liste nicht', () => {
    const items = [photo({ id: 1, category_confidence: 0.9 })]

    filterLowConfidence(items)

    expect(items).toHaveLength(1)
  })
})

describe('CurateCategoriesPage: Filter "Nur unsichere Zuordnungen"', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn().mockReturnValue({
        matches: false,
        media: '(hover: hover) and (pointer: fine)',
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })
    )
    vi.mocked(photosApi.listPhotos).mockReset()
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockReset()
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockResolvedValue('blob:fake-url')
    vi.mocked(categoriesApi.listCategories).mockReset()
    vi.mocked(categoriesApi.listCategories).mockResolvedValue(CATEGORY_SET)
    setToken(makeToken({ sub: '1', username: 'daniel', exp: 4102444800 }))
  })

  const LIST: PhotoListOut = {
    items: [
      photo({
        id: 1,
        relative_path: 'sicher.jpg',
        category_confidence: 0.9,
        rankings: [ranking({ cluster_key: 'cluster-0', category_key: 'landscape' })],
      }),
      photo({
        id: 2,
        relative_path: 'wacklig.jpg',
        category_confidence: 0.3,
        rankings: [ranking({ cluster_key: 'cluster-0', category_key: 'people' })],
      }),
    ],
    total: 2,
  }

  it('ist standardmaessig ausgeschaltet und zeigt alle Fotos', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue(LIST)

    renderPage()

    const toggle = await screen.findByRole('checkbox', { name: /nur unsichere zuordnungen/i })
    expect(toggle).not.toBeChecked()
    expect(screen.getByText('Landscape')).toBeInTheDocument()
    expect(screen.getByText('People')).toBeInTheDocument()
  })

  it('zeigt eingeschaltet nur noch die Fotos unter der Schwelle', async () => {
    const user = userEvent.setup()
    vi.mocked(photosApi.listPhotos).mockResolvedValue(LIST)

    renderPage()
    await user.click(await screen.findByRole('checkbox', { name: /nur unsichere zuordnungen/i }))

    expect(screen.getByLabelText('Verwerfen: wacklig.jpg')).toBeInTheDocument()
    expect(screen.queryByLabelText('Verwerfen: sicher.jpg')).not.toBeInTheDocument()
  })

  it('loest keine neue Anfrage aus', async () => {
    // Der Filter arbeitet auf den bereits geladenen Daten (Akzeptanzkriterium 5) - ein neuer
    // Request waere ein zweiter Ladezustand fuer eine reine Sicht-Aenderung.
    const user = userEvent.setup()
    vi.mocked(photosApi.listPhotos).mockResolvedValue(LIST)

    renderPage()
    await screen.findByRole('checkbox', { name: /nur unsichere zuordnungen/i })
    const callsBefore = vi.mocked(photosApi.listPhotos).mock.calls.length

    await user.click(screen.getByRole('checkbox', { name: /nur unsichere zuordnungen/i }))

    expect(vi.mocked(photosApi.listPhotos).mock.calls).toHaveLength(callsBefore)
  })

  it('haelt eine leer gefilterte Gruppe sichtbar - mit eigenem, vom Erschoepfungshinweis unterscheidbarem Text', async () => {
    const user = userEvent.setup()
    vi.mocked(photosApi.listPhotos).mockResolvedValue(LIST)

    renderPage()
    await user.click(await screen.findByRole('checkbox', { name: /nur unsichere zuordnungen/i }))

    // Die Partition "Landscape" ist leer gefiltert, bleibt aber sichtbar.
    expect(screen.getByText('Landscape')).toBeInTheDocument()
    expect(screen.getByText(LOW_CONFIDENCE_EMPTY_TEXT)).toBeInTheDocument()
    // Und sie wird NICHT als erschoepfter Pool ausgegeben.
    expect(screen.queryByText('Kein weiteres Foto verfügbar')).not.toBeInTheDocument()
  })

  it('stellt beim Ausschalten exakt den vorherigen Sichtstand wieder her', async () => {
    const user = userEvent.setup()
    vi.mocked(photosApi.listPhotos).mockResolvedValue(LIST)

    renderPage()
    const toggle = await screen.findByRole('checkbox', { name: /nur unsichere zuordnungen/i })

    await user.click(toggle)
    await user.click(toggle)

    expect(toggle).not.toBeChecked()
    expect(screen.getByLabelText('Verwerfen: sicher.jpg')).toBeInTheDocument()
    expect(screen.getByLabelText('Verwerfen: wacklig.jpg')).toBeInTheDocument()
    expect(screen.queryByText(LOW_CONFIDENCE_EMPTY_TEXT)).not.toBeInTheDocument()
  })

  it('laesst die Gruppierung nach Tag/Cluster/Kategorie unveraendert', async () => {
    const user = userEvent.setup()
    vi.mocked(photosApi.listPhotos).mockResolvedValue(LIST)

    renderPage()
    await user.click(await screen.findByRole('checkbox', { name: /nur unsichere zuordnungen/i }))

    expect(screen.getByText('Montag 20.07.2026')).toBeInTheDocument()
    expect(screen.getByText('Vormittags (10:00 Uhr)')).toBeInTheDocument()
  })

  it('gibt dem Kategorie-Chip der Gruppenueberschrift KEINE Zahl', async () => {
    // Akzeptanzkriterium 4: die Ueberschrift benennt eine Partition, nicht ein Foto.
    vi.mocked(photosApi.listPhotos).mockResolvedValue(LIST)

    renderPage()
    await screen.findByText('People')

    const heading = screen.getByText('People').closest('h4')
    expect(heading).not.toBeNull()
    expect(heading).not.toHaveTextContent('%')
  })
})

describe('CurateCategoriesPage — Nebenkategorien', () => {
  /* specs/features/0300-nebenkategorien.md: dasselbe Foto steht in zwei Kategorien - das ist der
   * Fall, den die Kuratierung vorher strukturell nicht kannte. */

  beforeEach(() => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn().mockReturnValue({
        matches: false,
        media: '(hover: hover) and (pointer: fine)',
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })
    )
    vi.mocked(photosApi.listPhotos).mockReset()
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockReset()
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockResolvedValue('blob:fake-url')
    vi.mocked(ratingsApi.setRating).mockReset()
    vi.mocked(categoriesApi.listCategories).mockReset()
    vi.mocked(categoriesApi.listCategories).mockResolvedValue(CATEGORY_SET)
    setToken(makeToken({ sub: '1', username: 'testuser' }))
  })

  const TWO_MEMBERSHIPS: PhotoListOut = {
    items: [
      photo({
        id: 1,
        rankings: [
          ranking({ category_key: 'landscape', is_primary: true, curation_position: 1 }),
          ranking({ category_key: 'people', is_primary: false, curation_position: 2 }),
        ],
      }),
    ],
    total: 1,
  }

  it('rendert dasselbe Foto in beiden Kategorien, in denen es ausgewaehlt ist', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue(TWO_MEMBERSHIPS)

    renderPage()

    expect(await screen.findByText('Landscape')).toBeInTheDocument()
    expect(screen.getByText('People')).toBeInTheDocument()
    // Zwei Kacheln fuer EIN Foto - der Dateiname erscheint zweimal.
    expect(screen.getAllByText('a.jpg')).toHaveLength(2)
  })

  it('zeigt den Nebenkategorie-Marker nur auf der Kachel der Nebenkategorie', async () => {
    /* Akzeptanzkriterium 14: die Rolle traegt eine Textalternative (`role="img"` +
     * `aria-label`), nie nur eine Farbe - und dieselbe Kachel unter ihrer Hauptkategorie traegt
     * ihn NICHT. */
    vi.mocked(photosApi.listPhotos).mockResolvedValue(TWO_MEMBERSHIPS)

    renderPage()

    const markers = await screen.findAllByLabelText('Nebenkategorie')
    expect(markers).toHaveLength(1)
    expect(markers[0]).toHaveAttribute('role', 'img')
  })

  it('zeigt Uebersteuerungs- und Nebenkategorie-Marker nebeneinander auf derselben Kachel', async () => {
    /* Marker-Kollision (UI/UX-Abschnitt der Spec): ein uebersteuertes Foto, das anderswo als
     * Nebenkategorie steht, braucht BEIDE - kein Stapeln, kein Verdraengen. */
    vi.mocked(photosApi.listPhotos).mockResolvedValue({
      items: [
        photo({
          id: 1,
          category_override: 'landschaft',
          rankings: [
            ranking({ category_key: 'landscape', is_primary: true, curation_position: 1 }),
            ranking({ category_key: 'people', is_primary: false, curation_position: 1 }),
          ],
        }),
      ],
      total: 1,
    })

    renderPage()

    const secondaryMarker = await screen.findByLabelText('Nebenkategorie')
    const container = secondaryMarker.parentElement
    expect(container).not.toBeNull()
    expect(within(container as HTMLElement).getByLabelText('Kategorie manuell übersteuert')).toBeInTheDocument()
    // Beide Kacheln des Fotos tragen den Uebersteuerungs-Marker, nur eine den Nebenkategorie-Marker.
    expect(screen.getAllByLabelText('Kategorie manuell übersteuert')).toHaveLength(2)
    expect(screen.getAllByLabelText('Nebenkategorie')).toHaveLength(1)
  })

  it('rendert weder Marker noch Rollenzeile, wenn ein Foto genau eine Zugehoerigkeit hat', async () => {
    /* Akzeptanzkriterium 24: ohne Nebenkategorien sieht die Oberflaeche exakt wie heute aus -
     * Negativ-Assertion auf die Textalternative UND auf den Rollen-Text. */
    vi.mocked(photosApi.listPhotos).mockResolvedValue({
      items: [photo({ id: 1, criterion_scores: [criterionScore()] })],
      total: 1,
    })

    renderPage()
    await screen.findByText('Landscape')

    expect(screen.queryByLabelText('Nebenkategorie')).not.toBeInTheDocument()
    expect(screen.queryByText('Kategorien dieses Fotos')).not.toBeInTheDocument()
  })

  it('blendet eine Zugehoerigkeit ohne Auswahlposition nicht ein', async () => {
    /* Die Kuratierung zeigt genau die Zugehoerigkeiten, die der SERVER ausgewaehlt hat
     * (`curation_position !== null`) - eine nicht ausgewaehlte Zugehoerigkeit ist im Popover
     * sichtbar, aber sie erzeugt keine Kachel. */
    vi.mocked(photosApi.listPhotos).mockResolvedValue({
      items: [
        photo({
          id: 1,
          rankings: [
            ranking({ category_key: 'landscape', is_primary: true, curation_position: 1 }),
            ranking({ category_key: 'people', is_primary: false, curation_position: null }),
          ],
        }),
      ],
      total: 1,
    })

    renderPage()

    expect(await screen.findByText('Landscape')).toBeInTheDocument()
    expect(screen.queryByText('People')).not.toBeInTheDocument()
    expect(screen.getAllByText('a.jpg')).toHaveLength(1)
  })

  it('zaehlt ein doppelt gezeigtes Foto in der Tagesueberschrift einmal, in der Cluster-Zahl zweimal', async () => {
    // Akzeptanzkriterium 26 der Spec 0300, hier durch die gerenderte Seite hindurch statt nur an
    // der Funktion - und seit specs/features/0357-voller-bildvorrat-kuratierung.md zusammen mit
    // der GEGENSAETZLICHEN Zaehlweise eine Ebene tiefer, in DEMSELBEN Testfall (Akzeptanzkriterium
    // 5/6). Zwei getrennte Positivtests blieben auch dann gruen, wenn beide Zahlen aus derselben
    // Quelle kaemen; die beiden Zahlen unterscheiden sich hier NUR an diesem einen Foto mit
    // Mehrfachzugehoerigkeit.
    const user = userEvent.setup()
    vi.mocked(photosApi.listPhotos).mockResolvedValue(TWO_MEMBERSHIPS)

    renderPage()
    await screen.findByText('Landscape')

    // Cluster-Zahl: zwei Zugehoerigkeiten desselben Fotos -> 2 Kandidaten.
    expect(screen.getByText('(2 Kandidaten)')).toBeInTheDocument()
    // Invariante statt abgeschriebener Zahlen: Cluster-Zahl == Summe der Kategorie-Zahlen.
    const categoryCounts = screen
      .getAllByRole('heading', { level: 4 })
      .map((heading) => Number(/(\d+) Kandidat/.exec(heading.textContent ?? '')?.[1] ?? 0))
    expect(categoryCounts).toEqual([1, 1])
    expect(categoryCounts.reduce((sum, count) => sum + count, 0)).toBe(2)

    // Tages-Zahl: EIN eindeutiges Foto.
    await user.click(screen.getByRole('button', { name: /montag 20\.07\.2026/i }))
    expect(screen.getByText('(1 Fotos)')).toBeInTheDocument()
  })
})

describe('candidateCountOfCategory / candidateCountOfCluster', () => {
  /* specs/features/0357-voller-bildvorrat-kuratierung.md, Akzeptanzkriterium 5: die Zahl einer
   * Kategorie ist ihre `partition_size` (alle Eintraege einer Partition tragen denselben Wert),
   * die Zahl eines Clusters die SUMME seiner Kategorie-Zahlen - ein Foto in zwei Kategorien
   * desselben Clusters zaehlt darin zweimal. */

  it('liest die Kategorie-Zahl aus der partition_size des ersten Eintrags', () => {
    expect(candidateCountOfCategory([entry({ id: 1 }, { partition_size: 7 })])).toBe(7)
  })

  it('liefert 0 fuer eine leergelaufene Kategorie', () => {
    // Akzeptanzkriterium 10: ohne Eintrag beschreibt die Antwort den Bestand gar nicht mehr.
    expect(candidateCountOfCategory([])).toBe(0)
  })

  it('summiert die Kategorie-Zahlen eines Clusters', () => {
    expect(
      candidateCountOfCluster({
        landscape: [entry({ id: 1 }, { category_key: 'landscape', partition_size: 3 })],
        people: [entry({ id: 2 }, { category_key: 'people', partition_size: 2 })],
      })
    ).toBe(5)
  })

  it('zaehlt ein Foto in zwei Kategorien desselben Clusters zweimal', () => {
    // Bewusste Produktentscheidung (ADR 0071 Entscheidung 4) - deshalb heisst die Zahl
    // "Kandidaten" und nicht "Fotos".
    expect(
      candidateCountOfCluster({
        landscape: [entry({ id: 1 }, { category_key: 'landscape', partition_size: 1 })],
        people: [entry({ id: 1 }, { category_key: 'people', partition_size: 1 })],
      })
    ).toBe(2)
  })

  it('ueberspringt leergelaufene Kategorien in der Summe', () => {
    expect(
      candidateCountOfCluster({
        landscape: [entry({ id: 1 }, { partition_size: 4 })],
        people: [],
      })
    ).toBe(4)
  })
})

describe('formatCandidateCount', () => {
  it('nutzt bei genau einem Kandidaten die Einzahl', () => {
    // Akzeptanzkriterium 9 - kein Randfall: im Demo-Bestand hat jede Partition genau ein Foto.
    expect(formatCandidateCount(1)).toBe('1 Kandidat')
  })

  it('nutzt sonst die Mehrzahl', () => {
    expect(formatCandidateCount(2)).toBe('2 Kandidaten')
  })
})

describe('CurateCategoriesPage — Mengenangaben', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn().mockReturnValue({
        matches: false,
        media: '(hover: hover) and (pointer: fine)',
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })
    )
    vi.mocked(photosApi.listPhotos).mockReset()
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockReset()
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockResolvedValue('blob:fake-url')
    vi.mocked(photosApi.setCategoryOverride).mockReset()
    vi.mocked(ratingsApi.setRating).mockReset()
    vi.mocked(categoriesApi.listCategories).mockReset()
    vi.mocked(categoriesApi.listCategories).mockResolvedValue(CATEGORY_SET)
    setToken(makeToken({ sub: '1', username: 'testuser' }))
  })

  /** partition_size == Zahl der angezeigten Eintraege: kein Auslöser, widerspruchsfreier Bestand. */
  const EXACTLY_FULL: PhotoListOut = {
    items: [
      photo({
        id: 1,
        rankings: [ranking({ category_key: 'landscape', partition_size: 2, rank_position: 1 })],
      }),
      photo({
        id: 2,
        relative_path: 'b.jpg',
        rankings: [
          ranking({
            category_key: 'landscape',
            partition_size: 2,
            rank_position: 2,
            curation_position: 2,
          }),
        ],
      }),
    ],
    total: 2,
  }

  it('zeigt die Kategorie-Zahl in der Kategorie-Ueberschrift', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue(EXACTLY_FULL)

    renderPage()

    const heading = (await screen.findByText('Landscape')).closest('h4')
    expect(heading).toHaveTextContent('2 Kandidaten')
  })

  it('zeigt die Cluster-Zahl NEBEN der unveraenderten Cluster-Ueberschrift', async () => {
    // Akzeptanzkriterium 4 samt Negativ-Nachweis: der von formatClusterHeading() erzeugte Text
    // (Tageszeit + Zeitraum) steht UNVERAENDERT im Baum - die Zahl verdraengt ihn nicht und nimmt
    // der spaeter vorgesehenen Ortsangabe ihren Platz nicht weg.
    vi.mocked(photosApi.listPhotos).mockResolvedValue(EXACTLY_FULL)

    renderPage()
    await screen.findByText('Landscape')

    const clusterHeading = screen.getByRole('heading', { level: 3 })
    expect(clusterHeading.textContent).toBe('Vormittags (10:00 Uhr)')
    expect(screen.getByText('(2 Kandidaten)')).toBeInTheDocument()
  })

  it('beschriftet genau einen Kandidaten in der Einzahl', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue({
      items: [photo({ id: 1, rankings: [ranking({ category_key: 'landscape' })] })],
      total: 1,
    })

    renderPage()

    const heading = (await screen.findByText('Landscape')).closest('h4')
    expect(heading).toHaveTextContent('1 Kandidat')
    expect(heading?.textContent).not.toMatch(/1 Kandidaten/)
  })

  it('laesst beide Zahlen vom Konfidenzfilter unberuehrt', async () => {
    // Akzeptanzkriterium 7: die Zahlen kommen aus der UNGEFILTERTEN Gruppierung. Sonst
    // verschwaenden sie genau dort, wo der Filter eine Gruppe leer raeumt, obwohl der Bestand
    // unveraendert ist. Geprueft mit Filter AUS und AN, nicht nur eingeschaltet.
    const user = userEvent.setup()
    vi.mocked(photosApi.listPhotos).mockResolvedValue({
      items: [
        // "landscape" wird vom Filter komplett leer geraeumt (beide Fotos sind sicher genug) …
        photo({
          id: 1,
          category_confidence: 0.9,
          rankings: [ranking({ category_key: 'landscape', partition_size: 2, rank_position: 1 })],
        }),
        photo({
          id: 2,
          relative_path: 'b.jpg',
          category_confidence: 0.9,
          rankings: [
            ranking({
              category_key: 'landscape',
              partition_size: 2,
              rank_position: 2,
              curation_position: 2,
            }),
          ],
        }),
        // … "people" ueberlebt ihn, damit der Tag nicht als Ganzes zuklappt und die Ebenen mit
        // den Zahlen sichtbar bleiben.
        photo({
          id: 3,
          relative_path: 'c.jpg',
          category_confidence: 0.3,
          rankings: [ranking({ category_key: 'people', partition_size: 1, rank_position: 1 })],
        }),
      ],
      total: 3,
    })

    renderPage()
    await screen.findByText('Landscape')
    expect(screen.getByText('(3 Kandidaten)')).toBeInTheDocument()
    expect(screen.getByText('Landscape').closest('h4')).toHaveTextContent('2 Kandidaten')

    await user.click(screen.getByRole('checkbox', { name: /nur unsichere zuordnungen/i }))

    // Die Kategorie ist leer gefiltert - die Zahlen beschreiben trotzdem weiter den vollen
    // Bestand, und die Cluster-Summe verliert die weggefilterte Kategorie nicht.
    expect(screen.getByText(LOW_CONFIDENCE_EMPTY_TEXT)).toBeInTheDocument()
    expect(screen.getByText('(3 Kandidaten)')).toBeInTheDocument()
    expect(screen.getByText('Landscape').closest('h4')).toHaveTextContent('2 Kandidaten')
    expect(screen.getByText('People').closest('h4')).toHaveTextContent('1 Kandidat')
  })

  it('laesst beide Zahlen vom Verwerfen unberuehrt', async () => {
    // Akzeptanzkriterium 7: `partition_size` ist lauf-global und nicht nutzerspezifisch gefiltert.
    const user = userEvent.setup()
    vi.mocked(photosApi.listPhotos)
      .mockResolvedValueOnce(EXACTLY_FULL)
      .mockResolvedValueOnce({
        items: [
          photo({
            id: 1,
            ratings: [{ user_id: 1, username: 'testuser', status: 'rejected' }],
            rankings: [ranking({ category_key: 'landscape', partition_size: 2, rank_position: 1 })],
          }),
          EXACTLY_FULL.items[1],
        ],
        total: 2,
      })
    vi.mocked(ratingsApi.setRating).mockResolvedValue({
      user_id: 1,
      username: 'testuser',
      status: 'rejected',
    })

    renderPage()
    await user.click(await screen.findByRole('button', { name: 'Verwerfen: a.jpg' }))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Verworfen: a.jpg' })).toBeInTheDocument()
    )
    expect(screen.getByText('(2 Kandidaten)')).toBeInTheDocument()
    expect(screen.getByText('Landscape').closest('h4')).toHaveTextContent('2 Kandidaten')
  })

  it('gibt einer leergelaufenen Kategorie GAR KEINE Zahl', async () => {
    // Akzeptanzkriterium 10: kein "0 Kandidaten", kein "undefined"/"NaN" - eine leergelaufene
    // Partition wird von der Antwort gar nicht mehr beschrieben. Ausgeloest wird der Fall ueber
    // den Kategorie-Override, den einzigen verbliebenen Weg, eine Partition leer laufen zu lassen.
    const user = userEvent.setup()
    vi.mocked(photosApi.listPhotos)
      .mockResolvedValueOnce({
        items: [
          photo({
            id: 1,
            criterion_scores: [criterionScore()],
            rankings: [ranking({ category_key: 'landscape' })],
            category_candidates: [
              { category_key: 'tier', origin: 'remote', provider: 'anthropic', confidence: null },
              { category_key: 'menschen', origin: 'local', provider: null, confidence: null },
            ],
          }),
        ],
        total: 1,
      })
      .mockResolvedValue({
        items: [
          photo({
            id: 1,
            category_override: 'tier',
            criterion_scores: [criterionScore()],
            rankings: [ranking({ category_key: 'tier' })],
            category_candidates: [
              { category_key: 'tier', origin: 'remote', provider: 'anthropic', confidence: null },
              { category_key: 'menschen', origin: 'local', provider: null, confidence: null },
            ],
          }),
        ],
        total: 1,
      })
    vi.mocked(photosApi.setCategoryOverride).mockResolvedValue({ photo_id: 1, category_key: 'tier' })

    renderPage()
    await screen.findByRole('button', { name: 'Bewertungsdetails anzeigen' })
    await user.click(screen.getByRole('button', { name: 'Bewertungsdetails anzeigen' }))
    const tierRow = screen.getByTestId('category-candidate-row-tier')
    await user.click(within(tierRow).getByRole('button', { name: /^übernehmen$/i }))

    await waitFor(() => expect(screen.getByText('Tier')).toBeInTheDocument())
    const emptied = screen.getByText('Landscape').closest('h4')
    expect(emptied).not.toBeNull()
    expect(emptied?.textContent).not.toMatch(/Kandidat|undefined|NaN/)
  })
})

describe('CurateCategoriesPage — Verwerfen ohne Nachruecken', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn().mockReturnValue({
        matches: false,
        media: '(hover: hover) and (pointer: fine)',
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })
    )
    vi.mocked(photosApi.listPhotos).mockReset()
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockReset()
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockResolvedValue('blob:fake-url')
    vi.mocked(ratingsApi.setRating).mockReset()
    vi.mocked(categoriesApi.listCategories).mockReset()
    vi.mocked(categoriesApi.listCategories).mockResolvedValue(CATEGORY_SET)
    setToken(makeToken({ sub: '1', username: 'testuser' }))
  })

  const TWO_TILES: PhotoListOut = {
    items: [
      photo({
        id: 1,
        rankings: [ranking({ category_key: 'landscape', partition_size: 2, rank_position: 1 })],
      }),
      photo({
        id: 2,
        relative_path: 'b.jpg',
        rankings: [
          ranking({
            category_key: 'landscape',
            partition_size: 2,
            rank_position: 2,
            curation_position: 2,
          }),
        ],
      }),
    ],
    total: 2,
  }

  function rejectedFirst(): PhotoListOut {
    return {
      items: [
        photo({
          id: 1,
          ratings: [{ user_id: 1, username: 'testuser', status: 'rejected' }],
          rankings: [ranking({ category_key: 'landscape', partition_size: 2, rank_position: 1 })],
        }),
        TWO_TILES.items[1],
      ],
      total: 2,
    }
  }

  /** Die vollstaendige Kachelliste in Reihenfolge - der Dateiname identifiziert die Kachel. */
  function tileNames(): string[] {
    return screen
      .getAllByRole('listitem')
      .map((item) => item.querySelector('.font-mono')?.textContent ?? '')
      .filter((name) => name !== '')
  }

  it('laesst die vollstaendige Kachelliste nach dem Verwerfen unveraendert', async () => {
    // Akzeptanzkriterium 11: geprueft als LISTENVERGLEICH, nicht als "das Foto ist noch da" - ein
    // Vorhandensein-Test bliebe auch dann gruen, wenn hinter dem Foto umsortiert wuerde.
    const user = userEvent.setup()
    vi.mocked(photosApi.listPhotos)
      .mockResolvedValueOnce(TWO_TILES)
      .mockResolvedValue(rejectedFirst())
    vi.mocked(ratingsApi.setRating).mockResolvedValue({
      user_id: 1,
      username: 'testuser',
      status: 'rejected',
    })

    renderPage()
    await screen.findByRole('button', { name: 'Verwerfen: a.jpg' })
    const before = tileNames()

    await user.click(screen.getByRole('button', { name: 'Verwerfen: a.jpg' }))
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Verworfen: a.jpg' })).toBeInTheDocument()
    )

    expect(tileNames()).toEqual(before)
    expect(before).toEqual(['a.jpg', 'b.jpg'])
  })

  it('markiert die verworfene Kachel und deaktiviert ihre Schaltflaeche an derselben Stelle', async () => {
    // Akzeptanzkriterium 12: PhotoCard status='rejected' (Badge "Verworfen", data-struck), die
    // Schaltflaeche bleibt an ihrer Stelle, ist deaktiviert und traegt den Dateinamen im
    // zugaenglichen Namen - sonst hiessen auf einer Seite mit vielen Kacheln alle gleich.
    const user = userEvent.setup()
    vi.mocked(photosApi.listPhotos)
      .mockResolvedValueOnce(TWO_TILES)
      .mockResolvedValue(rejectedFirst())
    vi.mocked(ratingsApi.setRating).mockResolvedValue({
      user_id: 1,
      username: 'testuser',
      status: 'rejected',
    })

    renderPage()
    await user.click(await screen.findByRole('button', { name: 'Verwerfen: a.jpg' }))

    const rejected = await screen.findByRole('button', { name: 'Verworfen: a.jpg' })
    expect(rejected).toBeDisabled()
    expect(rejected).toHaveTextContent('Verworfen')
    const tile = rejected.closest('li')
    expect(tile).toHaveAttribute('data-rating-status', 'rejected')
    expect(within(tile as HTMLElement).getByText('a.jpg')).toHaveAttribute('data-struck', 'true')
    // Die Nachbarkachel bleibt unberuehrt bedienbar.
    expect(screen.getByRole('button', { name: 'Verwerfen: b.jpg' })).toBeEnabled()
  })

  it('zeigt ein nur vom ANDEREN Nutzer verworfenes Foto nicht als verworfen', async () => {
    // Akzeptanzkriterium 16 und Security-Muss-Kriterium 5 der Spec: der eigene Zustand kommt
    // ausschliesslich aus `ownRatingStatus`, nie aus `ratings[]` insgesamt (etwa "erster
    // Eintrag") - sonst stellte die Ansicht den Zustand des anderen als eigenen dar.
    vi.mocked(photosApi.listPhotos).mockResolvedValue({
      items: [
        photo({
          id: 1,
          ratings: [{ user_id: 2, username: 'andere', status: 'rejected' }],
          rankings: [ranking({ category_key: 'landscape' })],
        }),
      ],
      total: 1,
    })

    renderPage()

    expect(await screen.findByRole('button', { name: 'Verwerfen: a.jpg' })).toBeEnabled()
    expect(screen.queryByRole('button', { name: 'Verworfen: a.jpg' })).not.toBeInTheDocument()
  })

  it('markiert beide Kacheln eines doppelt gezeigten Fotos', async () => {
    // Akzeptanzkriterium 15: steht dasselbe Foto in zwei Kategorien, tragen BEIDE Kacheln den
    // Zustand - der Zustand haengt am Foto, nicht am Vorkommen.
    vi.mocked(photosApi.listPhotos).mockResolvedValue({
      items: [
        photo({
          id: 1,
          ratings: [{ user_id: 1, username: 'testuser', status: 'rejected' }],
          rankings: [
            ranking({ category_key: 'landscape', curation_position: 1 }),
            ranking({ category_key: 'people', is_primary: false, curation_position: 1 }),
          ],
        }),
      ],
      total: 1,
    })

    renderPage()

    expect(await screen.findAllByRole('button', { name: 'Verworfen: a.jpg' })).toHaveLength(2)
  })

  it('beendet den Busy-Zustand, OBWOHL das Foto in der Liste bleibt', async () => {
    // Akzeptanzkriterium 17: der frueher dafuer zustaendige useEffect wartete auf das Verschwinden
    // des Fotos aus `items`. Ohne Nachruecken verschwindet es nie - die Schaltflaeche bliebe
    // dauerhaft busy, und das faellt in keinem Test auf, der nur die Liste betrachtet. Die hier
    // gemockte Antwort traegt die Bewertung bewusst NICHT: geprueft wird das Ende des
    // Busy-Zustands, nicht die Markierung.
    const user = userEvent.setup()
    vi.mocked(photosApi.listPhotos).mockResolvedValue(TWO_TILES)
    vi.mocked(ratingsApi.setRating).mockResolvedValue({
      user_id: 1,
      username: 'testuser',
      status: 'rejected',
    })

    renderPage()
    await user.click(await screen.findByRole('button', { name: 'Verwerfen: a.jpg' }))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Verwerfen: a.jpg' })).toBeEnabled()
    )
  })

  /**
   * Zwei Klicks OHNE zwischenzeitliches Neurendern - beide landen im selben React-Durchlauf,
   * die Schaltflaeche ist beim zweiten also noch nicht deaktiviert.
   *
   * `userEvent.click()` taugt dafuer NICHT: es spuelt zwischen den Klicks, und der zweite trifft
   * bereits die deaktivierte Schaltflaeche. Genau dieser Unterschied ist der Testgegenstand -
   * `disabled` ist eine Folge eines State-Updates und deshalb keine verlaessliche Sperre.
   */
  async function clickWithoutRerenderBetween(buttons: HTMLElement[]): Promise<void> {
    await act(async () => {
      for (const button of buttons) {
        fireEvent.click(button)
      }
    })
  }

  it('verwirft zwei Fotos bei zwei schnellen Klicks auf verschiedene Kacheln', async () => {
    // Akzeptanzkriterium 18: die seitenweite Einfach-Sperre (`rejectingPhotoId !== null`) ist
    // aufgegeben. Wo bisher ein zweiter Klick still verpuffte, ist sein Gelingen zuzusichern -
    // sonst ist von aussen nicht zu unterscheiden, ob die Sperre absichtlich fiel. Beide Klicks
    // laufen bewusst im selben Durchlauf: nur so belegt der Fall, dass die Sperre JE FOTO greift
    // und nicht bloss die Schaltflaechen-Deaktivierung den zweiten Klick durchliess.
    vi.mocked(photosApi.listPhotos).mockResolvedValue(TWO_TILES)
    const pending: (() => void)[] = []
    vi.mocked(ratingsApi.setRating).mockImplementation(
      () =>
        new Promise((resolve) => {
          pending.push(() => resolve({ user_id: 1, username: 'testuser', status: 'rejected' }))
        })
    )

    renderPage()
    await screen.findByRole('button', { name: 'Verwerfen: a.jpg' })
    await clickWithoutRerenderBetween([
      screen.getByRole('button', { name: 'Verwerfen: a.jpg' }),
      screen.getByRole('button', { name: 'Verwerfen: b.jpg' }),
    ])

    expect(ratingsApi.setRating).toHaveBeenCalledTimes(2)
    expect(ratingsApi.setRating).toHaveBeenNthCalledWith(1, 1, 'rejected')
    expect(ratingsApi.setRating).toHaveBeenNthCalledWith(2, 2, 'rejected')
    await act(async () => {
      for (const resolve of pending) {
        resolve()
      }
    })
  })

  it('loest bei zwei schnellen Klicks auf DIESELBE Kachel nur EINEN Vorgang aus', async () => {
    /* Die Kehrseite von Akzeptanzkriterium 18 (Copilot-Review-Fund): aufgegeben wurde die
     * SEITENWEITE Sperre, nicht der Schutz gegen einen zweiten Vorgang fuer DASSELBE Foto.
     * `Rating` traegt `UniqueConstraint(photo_id, user_id)` - zwei nebenlaeufige Anfragen, die
     * beide "noch keine Bewertung vorhanden" lesen, laufen in einen IntegrityError und damit in
     * eine 500. Das `disabled` der Schaltflaeche ist dagegen kein Schutz: es entsteht erst durch
     * ein State-Update, und beide Klicks dieses Falls liegen davor. */
    vi.mocked(photosApi.listPhotos).mockResolvedValue(TWO_TILES)
    vi.mocked(ratingsApi.setRating).mockImplementation(() => new Promise(() => {}))

    renderPage()
    await screen.findByRole('button', { name: 'Verwerfen: a.jpg' })
    const button = screen.getByRole('button', { name: 'Verwerfen: a.jpg' })
    await clickWithoutRerenderBetween([button, button])

    expect(ratingsApi.setRating).toHaveBeenCalledTimes(1)
    expect(ratingsApi.setRating).toHaveBeenCalledWith(1, 'rejected')
  })

  it('behandelt die zwei Kacheln DESSELBEN Fotos als ein Foto', async () => {
    /* Seit specs/features/0300-nebenkategorien.md kann dasselbe Foto in zwei Kategorien stehen
     * und hat dann ZWEI Kacheln mit je eigener Schaltflaeche. Ein schneller Klick auf beide ist
     * ein realistischer Bedienweg, kein konstruierter Doppelklick - und muss trotzdem genau
     * einen Vorgang ausloesen, weil es genau eine Bewertungszeile gibt. */
    vi.mocked(photosApi.listPhotos).mockResolvedValue({
      items: [
        photo({
          id: 1,
          rankings: [
            ranking({ category_key: 'landscape', curation_position: 1 }),
            ranking({ category_key: 'people', is_primary: false, curation_position: 1 }),
          ],
        }),
      ],
      total: 1,
    })
    vi.mocked(ratingsApi.setRating).mockImplementation(() => new Promise(() => {}))

    renderPage()
    await screen.findAllByRole('button', { name: 'Verwerfen: a.jpg' })
    const buttons = screen.getAllByRole('button', { name: 'Verwerfen: a.jpg' })
    expect(buttons).toHaveLength(2)

    await clickWithoutRerenderBetween(buttons)

    expect(ratingsApi.setRating).toHaveBeenCalledTimes(1)
  })
})

describe('CurateCategoriesPage — weitere Kandidaten einsehen', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn().mockReturnValue({
        matches: false,
        media: '(hover: hover) and (pointer: fine)',
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })
    )
    vi.mocked(photosApi.listPhotos).mockReset()
    vi.mocked(photosApi.listCurationCandidates).mockReset()
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockReset()
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockResolvedValue('blob:fake-url')
    vi.mocked(ratingsApi.setRating).mockReset()
    vi.mocked(categoriesApi.listCategories).mockReset()
    vi.mocked(categoriesApi.listCategories).mockResolvedValue(CATEGORY_SET)
    setToken(makeToken({ sub: '1', username: 'testuser' }))
  })

  /** Ein Top-Foto, die Partition hat aber vier Kandidaten - drei stehen also noch aus. */
  const ONE_OF_FOUR: PhotoListOut = {
    items: [
      photo({
        id: 1,
        rankings: [ranking({ category_key: 'landscape', partition_size: 4, rank_position: 1 })],
      }),
    ],
    total: 1,
  }

  function candidate(id: number, rankPosition: number, overrides: Partial<PhotoOut> = {}) {
    return photo({
      id,
      relative_path: `k${id}.jpg`,
      rankings: [
        ranking({
          category_key: 'landscape',
          partition_size: 4,
          rank_position: rankPosition,
          curation_position: rankPosition,
        }),
      ],
      ...overrides,
    })
  }

  const TRIGGER = /weitere kandidaten laden/i
  const COLLAPSE = /weitere kandidaten ausblenden/i

  it('rendert den Auslöser genau dann, wenn es weitere Kandidaten gibt', async () => {
    // Akzeptanzkriterium 19, BEIDE Richtungen: `partition_size` groesser als die Zahl der
    // ungefilterten Eintraege -> Auslöser; gleich gross -> kein Auslöser.
    vi.mocked(photosApi.listPhotos).mockResolvedValue(ONE_OF_FOUR)

    const withMore = renderPage('/projects/1/curate?topN=1')
    expect(await screen.findByRole('button', { name: TRIGGER })).toBeInTheDocument()
    withMore.unmount()

    vi.mocked(photosApi.listPhotos).mockResolvedValue({
      items: [
        photo({
          id: 1,
          rankings: [ranking({ category_key: 'landscape', partition_size: 1, rank_position: 1 })],
        }),
      ],
      total: 1,
    })
    renderPage('/projects/1/curate?topN=1')

    await screen.findByText('Landscape')
    expect(screen.queryByRole('button', { name: TRIGGER })).not.toBeInTheDocument()
  })

  it('schliesst Auslöser und Erschoepfungshinweis gegenseitig aus', async () => {
    // Akzeptanzkriterium 25: beides sind Gegensaetze - "Kein weiteres Foto verfügbar" und "es
    // gibt noch weitere". Ein Ausschluss-Testfall statt zweier Positivtests, sonst fiele eine
    // falsch gesetzte Bedingung nirgends auf.
    vi.mocked(photosApi.listPhotos).mockResolvedValue(ONE_OF_FOUR)

    renderPage('/projects/1/curate?topN=3')

    expect(await screen.findByRole('button', { name: TRIGGER })).toBeInTheDocument()
    expect(screen.queryByText('Kein weiteres Foto verfügbar')).not.toBeInTheDocument()
  })

  it('nennt in der Beschriftung die ungefilterte Restmenge', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue(ONE_OF_FOUR)

    renderPage('/projects/1/curate?topN=1')

    // 4 Kandidaten in der Partition, 1 angezeigt -> 3 stehen aus.
    expect(await screen.findByRole('button', { name: TRIGGER })).toHaveTextContent('3')
  })

  it('ist standardmaessig zugeklappt und laedt erst beim Aufklappen', async () => {
    // Akzeptanzkriterium 20: `aria-expanded` wechselt false -> true, `aria-controls` zeigt auf
    // den eingeblendeten Bereich, und der Text wechselt.
    const user = userEvent.setup()
    vi.mocked(photosApi.listPhotos).mockResolvedValue(ONE_OF_FOUR)
    vi.mocked(photosApi.listCurationCandidates).mockResolvedValue({
      items: [candidate(2, 2)],
      total: 3,
    })

    renderPage('/projects/1/curate?topN=1')
    const trigger = await screen.findByRole('button', { name: TRIGGER })
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    expect(photosApi.listCurationCandidates).not.toHaveBeenCalled()

    await user.click(trigger)

    const expanded = await screen.findByRole('button', { name: COLLAPSE })
    expect(expanded).toHaveAttribute('aria-expanded', 'true')
    const panelId = expanded.getAttribute('aria-controls')
    expect(panelId).not.toBeNull()
    await waitFor(() =>
      expect(document.getElementById(panelId as string)).toBeInTheDocument()
    )
    expect(photosApi.listCurationCandidates).toHaveBeenCalledWith(1, {
      clusterKey: 'cluster-0',
      categoryKey: 'landscape',
      afterRank: 1,
      limit: PHOTOS_PAGE_SIZE,
      offset: 0,
    })
  })

  it('stellt die nachgeladenen Kandidaten HINTER die Top-Fotos, ohne Wiederholung', async () => {
    // Akzeptanzkriterium 21: aufsteigende Rangfolge, kein bereits gezeigtes Foto doppelt.
    const user = userEvent.setup()
    vi.mocked(photosApi.listPhotos).mockResolvedValue(ONE_OF_FOUR)
    vi.mocked(photosApi.listCurationCandidates).mockResolvedValue({
      items: [candidate(2, 2), candidate(3, 3)],
      total: 3,
    })

    renderPage('/projects/1/curate?topN=1')
    await user.click(await screen.findByRole('button', { name: TRIGGER }))

    await screen.findByText('k2.jpg')
    const names = screen
      .getAllByRole('listitem')
      .map((item) => item.querySelector('.font-mono')?.textContent ?? '')
      .filter((name) => name !== '')
    expect(names).toEqual(['a.jpg', 'k2.jpg', 'k3.jpg'])
  })

  it('laesst die Tages-Zahl beim Aufklappen unveraendert', async () => {
    // Akzeptanzkriterium 8: nachgeladene Kandidaten fliessen NICHT in die Gruppierung ein, aus
    // der `countPhotosInDay()` rechnet - eine Zahl, die beim Aufklappen spraenge, waere fuer den
    // Nutzer nicht zuzuordnen.
    const user = userEvent.setup()
    vi.mocked(photosApi.listPhotos).mockResolvedValue(ONE_OF_FOUR)
    vi.mocked(photosApi.listCurationCandidates).mockResolvedValue({
      items: [candidate(2, 2), candidate(3, 3)],
      total: 3,
    })

    renderPage('/projects/1/curate?topN=1')
    await user.click(await screen.findByRole('button', { name: /montag 20\.07\.2026/i }))
    expect(screen.getByText('(1 Fotos)')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /montag 20\.07\.2026/i }))

    await user.click(await screen.findByRole('button', { name: TRIGGER }))
    await screen.findByText('k2.jpg')
    await user.click(screen.getByRole('button', { name: /montag 20\.07\.2026/i }))

    expect(screen.getByText('(1 Fotos)')).toBeInTheDocument()
    // Und auch die beiden neuen Zahlen bleiben, wo sie waren (Akzeptanzkriterium 7).
    await user.click(screen.getByRole('button', { name: /montag 20\.07\.2026/i }))
    expect(screen.getByText('(4 Kandidaten)')).toBeInTheDocument()
  })

  it('entfernt die Kacheln beim Ausblenden wieder, ohne die Zahlen anzutasten', async () => {
    // Akzeptanzkriterium 23.
    const user = userEvent.setup()
    vi.mocked(photosApi.listPhotos).mockResolvedValue(ONE_OF_FOUR)
    vi.mocked(photosApi.listCurationCandidates).mockResolvedValue({
      items: [candidate(2, 2)],
      total: 3,
    })

    renderPage('/projects/1/curate?topN=1')
    await user.click(await screen.findByRole('button', { name: TRIGGER }))
    await screen.findByText('k2.jpg')

    await user.click(screen.getByRole('button', { name: COLLAPSE }))

    expect(screen.queryByText('k2.jpg')).not.toBeInTheDocument()
    expect(screen.getByText('(4 Kandidaten)')).toBeInTheDocument()
    expect(screen.getByText('Landscape').closest('h4')).toHaveTextContent('4 Kandidaten')
  })

  it('macht nachgeladene Kandidaten verwerfbar - auch nach Zu- und erneutem Aufklappen', async () => {
    // Akzeptanzkriterium 22: dasselbe Verhalten wie bei den Top-Fotos (AK 11/12).
    const user = userEvent.setup()
    vi.mocked(photosApi.listPhotos).mockResolvedValue(ONE_OF_FOUR)
    vi.mocked(photosApi.listCurationCandidates)
      .mockResolvedValueOnce({ items: [candidate(2, 2)], total: 3 })
      .mockResolvedValue({
        items: [
          candidate(2, 2, { ratings: [{ user_id: 1, username: 'testuser', status: 'rejected' }] }),
        ],
        total: 3,
      })
    vi.mocked(ratingsApi.setRating).mockResolvedValue({
      user_id: 1,
      username: 'testuser',
      status: 'rejected',
    })

    renderPage('/projects/1/curate?topN=1')
    await user.click(await screen.findByRole('button', { name: TRIGGER }))
    await user.click(await screen.findByRole('button', { name: 'Verwerfen: k2.jpg' }))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Verworfen: k2.jpg' })).toBeInTheDocument()
    )

    await user.click(screen.getByRole('button', { name: COLLAPSE }))
    await user.click(screen.getByRole('button', { name: TRIGGER }))

    expect(await screen.findByRole('button', { name: 'Verworfen: k2.jpg' })).toBeDisabled()
  })

  it('filtert auch nachgeladene Kandidaten und unterscheidet "alles weggefiltert" von "noch nichts geladen"', async () => {
    // Akzeptanzkriterium 24: der Filter hat EINE Bedeutung in der ganzen Ansicht.
    const user = userEvent.setup()
    vi.mocked(photosApi.listPhotos).mockResolvedValue({
      items: [
        photo({
          id: 1,
          category_confidence: 0.3,
          rankings: [ranking({ category_key: 'landscape', partition_size: 4, rank_position: 1 })],
        }),
      ],
      total: 1,
    })
    vi.mocked(photosApi.listCurationCandidates).mockResolvedValue({
      items: [candidate(2, 2, { category_confidence: 0.9 })],
      total: 3,
    })

    renderPage('/projects/1/curate?topN=1')
    await user.click(await screen.findByRole('checkbox', { name: /nur unsichere zuordnungen/i }))
    await user.click(await screen.findByRole('button', { name: TRIGGER }))

    // Der nachgeladene Kandidat ist sicher genug und faellt heraus …
    await waitFor(() => expect(photosApi.listCurationCandidates).toHaveBeenCalled())
    expect(screen.queryByText('k2.jpg')).not.toBeInTheDocument()
    // … und der Bereich sagt das ausdruecklich, statt so auszusehen wie "noch nichts geladen".
    expect(await screen.findByText(CANDIDATES_ALL_FILTERED_TEXT)).toBeInTheDocument()
  })

  it('zeigt einen Ladezustand und einen Fehlerzustand mit erfolgreichem zweitem Versuch', async () => {
    // Akzeptanzkriterium 26.
    const user = userEvent.setup()
    vi.mocked(photosApi.listPhotos).mockResolvedValue(ONE_OF_FOUR)
    vi.mocked(photosApi.listCurationCandidates)
      .mockRejectedValueOnce(new ApiError(500, 'Serverfehler'))
      .mockResolvedValue({ items: [candidate(2, 2)], total: 3 })

    renderPage('/projects/1/curate?topN=1')
    await user.click(await screen.findByRole('button', { name: TRIGGER }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Serverfehler')

    await user.click(within(alert).getByRole('button', { name: /erneut versuchen/i }))

    expect(await screen.findByText('k2.jpg')).toBeInTheDocument()
  })

  it('laedt die ZWEITE Seite mit dem richtigen Offset nach', async () => {
    // Akzeptanzkriterium 27: die erste Seite bestuende auch bei einem fest verdrahteten
    // `offset: 0` - der Pflichtfall ist die zweite.
    const user = userEvent.setup()
    vi.mocked(photosApi.listPhotos).mockResolvedValue({
      items: [
        photo({
          id: 1,
          rankings: [ranking({ category_key: 'landscape', partition_size: 130, rank_position: 1 })],
        }),
      ],
      total: 1,
    })
    vi.mocked(photosApi.listCurationCandidates)
      .mockResolvedValueOnce({ items: [candidate(2, 2)], total: 2 })
      .mockResolvedValueOnce({ items: [candidate(3, 3)], total: 2 })

    renderPage('/projects/1/curate?topN=1')
    await user.click(await screen.findByRole('button', { name: TRIGGER }))
    await screen.findByText('k2.jpg')

    await user.click(screen.getByRole('button', { name: /noch mehr kandidaten laden/i }))

    await screen.findByText('k3.jpg')
    expect(photosApi.listCurationCandidates).toHaveBeenLastCalledWith(1, {
      clusterKey: 'cluster-0',
      categoryKey: 'landscape',
      afterRank: 1,
      limit: PHOTOS_PAGE_SIZE,
      offset: 1,
    })
  })
})
