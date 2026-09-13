import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
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
import { setToken } from '../auth/token'
import { MOTIF_SET } from '../test/motifSetFixture'
import {
  candidateCountOfEvent,
  countPhotosInDay,
  CURATION_CLOUD_CONSENT_TEXT,
  CURATION_EMPTY_TEXT,
  CuratePage,
  formatCandidateCount,
  toggleDayCollapse,
} from './CuratePage'

vi.mock('../api/photos')
vi.mock('../api/projects')
vi.mock('../api/ratings')
vi.mock('../api/motifs')

/** Der Regelfall der Bestandstests: Cloud freigegeben - sonst traegt jede Ansicht den Hinweis. */
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
    // Klein genug, dass der Regelfall der Bestandstests KEINEN "zu wenige Bilder"-Hinweis traegt.
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

/** Die Kuratierung zeigt ein Foto genau dann, wenn `curation_position !== null`. */
function ranking(overrides: Partial<RankingOut> = {}): RankingOut {
  return {
    event_id: 1,
    rank_score: 0.8,
    rank_position: 1,
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
    ended_at: '2026-07-20T10:00:00',
    place: null,
    ...overrides,
  }
}

function photo(overrides: Partial<PhotoOut> = {}): PhotoOut {
  const base = {
    id: 1,
    relative_path: 'a.jpg',
    // taken_at ist ein naives, zeitzonenloses Backend-Datetime ohne `Z`-Suffix.
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
    // Basiszustand: klassifiziert per Cloud-Grundlage, ohne Ausschluss.
    motif_assessment: {
      source: 'cloud' as const,
      provider: 'anthropic',
      excluded_document: false,
      computed_at: '2026-07-21T09:00:00',
    },
    motifs: MOTIF_SET.items.map((item) => ({
      key: item.key,
      strength: 0.5,
      correction: null,
    })),
    ...overrides,
  }
  // Das Event folgt der Rangzeile, solange ein Testfall es nicht ausdruecklich setzt: der Server
  // liefert es auf jedem Foto desselben Events feldgleich, und `position` ist je Lauf lueckenlos
  // vergeben.
  if ('event' in overrides) {
    return base
  }
  const eventId = base.ranking?.event_id
  return {
    ...base,
    event:
      eventId === undefined
        ? null
        : eventOut({
            id: eventId,
            position: eventId,
            started_at: base.taken_at,
            ended_at: base.taken_at,
          }),
  }
}

describe('countPhotosInDay', () => {
  it('returns 0 for a day with no events', () => {
    expect(countPhotosInDay({})).toBe(0)
  })

  it('sums photos across every event of the day', () => {
    expect(
      countPhotosInDay({
        '1': [photo({ id: 1 }), photo({ id: 2 })],
        '2': [photo({ id: 3 })],
      }),
    ).toBe(3)
  })

  it('ignores an event whose pool is already exhausted', () => {
    expect(countPhotosInDay({ '1': [], '2': [photo({ id: 1 })] })).toBe(1)
  })
})

describe('candidateCountOfEvent', () => {
  it('is the partition size of the first photo', () => {
    expect(candidateCountOfEvent([photo({ ranking: ranking({ partition_size: 7 }) })])).toBe(7)
  })

  it('is 0 for an exhausted event', () => {
    /* "0 Kandidaten" wäre eine Aussage über einen Bestand, den die Antwort nicht mehr
     * beschreibt - die Überschrift bekommt dann gar keine Zahl. */
    expect(candidateCountOfEvent([])).toBe(0)
  })

  it('is 0 for a photo without a ranking row', () => {
    expect(candidateCountOfEvent([photo({ ranking: null })])).toBe(0)
  })
})

describe('toggleDayCollapse', () => {
  it('adds a dayKey that is not yet in the set (collapses it)', () => {
    expect(toggleDayCollapse(new Set(), '2026-07-20').has('2026-07-20')).toBe(true)
  })

  it('removes a dayKey that is already in the set (expands it)', () => {
    expect(toggleDayCollapse(new Set(['2026-07-20']), '2026-07-20').has('2026-07-20')).toBe(false)
  })

  it('returns a new Set instance instead of mutating the argument', () => {
    const original = new Set<string>()

    const result = toggleDayCollapse(original, '2026-07-20')

    expect(result).not.toBe(original)
    expect(original.has('2026-07-20')).toBe(false)
  })
})

function renderPage(initialPath = '/projects/1/curate') {
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
          <Route path="/projects/:projectId" element={<p>Projekt-Detailseite</p>} />
          <Route path="/projects/:projectId/curate" element={<CuratePage />} />
        </Routes>
      </MemoryRouter>,
      { wrapper },
    ),
    queryClient,
  }
}

function listOut(items: PhotoOut[], total = items.length): PhotoListOut {
  return { items, total }
}

describe('CuratePage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    setToken(makeToken({ sub: 'daniel' }))
    // Die Kachel laedt ihr Bild ueber `fetchPhotoImageBlobUrl` - ohne Attrappe liefert der Mock
    // `undefined`, und `PhotoImage` bricht beim `.then(...)` ab, bevor irgendetwas gerendert ist.
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockResolvedValue('blob:fake-url')
    vi.mocked(motifsApi.listMotifs).mockResolvedValue(MOTIF_SET)
    vi.mocked(projectsApi.getProject).mockResolvedValue(projectOut())
    vi.mocked(photosApi.listCurationCandidates).mockResolvedValue(listOut([], 0))
    // Das Info-Popover fragt `matchMedia` zur Interaktionszeit ab; jsdom kennt es nicht.
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

  it('is called "Kuratierung", not "Kategorie-Kuratierung"', async () => {
    /* specs/features/0427-motive-mit-staerke.md: die Umbenennung an einer der drei sichtbaren
     * Stellen. Als NEGATIVE Assertion mit dazu: eine Überschrift, die das alte Wort noch trägt,
     * bestünde jede Positivprüfung auf „Kuratierung" als Teilzeichenkette. */
    vi.mocked(photosApi.listPhotos).mockResolvedValue(listOut([]))

    renderPage()

    const heading = await screen.findByRole('heading', { level: 1 })
    expect(heading).toHaveTextContent('Kuratierung')
    expect(heading.textContent).not.toContain('Kategorie')
  })

  it('groups the photos by day and event, without a category level', async () => {
    /* DIE tragende Strukturänderung: zwei Ebenen statt drei. Ein Foto steht je Lauf in genau
     * einer Gruppe, und der Kachel-Key ist wieder `photo.id`. */
    vi.mocked(photosApi.listPhotos).mockResolvedValue(
      listOut([
        photo({ id: 1, relative_path: 'a.jpg', ranking: ranking({ partition_size: 2 }) }),
        photo({
          id: 2,
          relative_path: 'b.jpg',
          ranking: ranking({ rank_position: 2, curation_position: 2, partition_size: 2 }),
        }),
      ]),
    )

    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 2 })).toBeInTheDocument()
    })
    // Genau EINE Zwischenüberschrift je Event (h3) - keine vierte Ebene für Kategorien (h4).
    expect(screen.getAllByRole('heading', { level: 3 })).toHaveLength(1)
    expect(screen.queryAllByRole('heading', { level: 4 })).toHaveLength(0)
    expect(screen.getByLabelText('Verwerfen: a.jpg')).toBeInTheDocument()
    expect(screen.getByLabelText('Verwerfen: b.jpg')).toBeInTheDocument()
  })

  it('shows the candidate count of the event next to its heading', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue(
      listOut([photo({ id: 1, ranking: ranking({ partition_size: 5 }) })]),
    )

    renderPage()

    expect(await screen.findByText(`(${formatCandidateCount(5)})`)).toBeInTheDocument()
  })

  it('offers no confidence filter any more', async () => {
    /* Der Filter „Nur unsichere Zuordnungen" entfällt mit `category_confidence`. Als eigener
     * Fall, weil ein stehengebliebenes Kontrollkästchen ohne Datengrundlage still nichts mehr
     * filtern würde - und damit von jedem Positivtest der Liste unbemerkt bliebe. */
    vi.mocked(photosApi.listPhotos).mockResolvedValue(listOut([photo({ id: 1 })]))

    renderPage()

    await screen.findByLabelText('Verwerfen: a.jpg')
    expect(screen.queryByLabelText(/unsicher/i)).toBeNull()
    expect(screen.queryByRole('checkbox')).toBeNull()
  })

  it('shows the empty state without the word "Kategorie"', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue(listOut([]))

    renderPage()

    const text = await screen.findByText(CURATION_EMPTY_TEXT)
    expect(text).toBeInTheDocument()
    expect(CURATION_EMPTY_TEXT).not.toContain('Kategorie')
  })

  describe('ohne Cloud-Freigabe', () => {
    it('names the missing approval and offers the way to it, with an empty photo list', async () => {
      /* BEIDES in einem Fall: der Hinweis erscheint UND die Liste ist leer. Ein Hinweis über
       * einer gefüllten Liste wäre eine Aussage, die der Rest der Seite widerlegt. */
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        projectOut({ cloud_vision_detection_enabled: false }),
      )
      vi.mocked(photosApi.listPhotos).mockResolvedValue(listOut([]))

      renderPage()

      expect(await screen.findByText(CURATION_CLOUD_CONSENT_TEXT)).toBeInTheDocument()
      const link = screen.getByRole('link', { name: 'Zu den Projekteinstellungen' })
      expect(link).toHaveAttribute('href', '/projects/1/settings')
      expect(screen.queryByLabelText(/^Verwerfen:/)).toBeNull()
    })

    it('is shown instead of the ordinary empty text', async () => {
      /* „führe eine Kriterien-Bewertung aus" wäre hier ein Rat, der nicht hilft. */
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        projectOut({ cloud_vision_detection_enabled: false }),
      )
      vi.mocked(photosApi.listPhotos).mockResolvedValue(listOut([]))

      renderPage()

      await screen.findByText(CURATION_CLOUD_CONSENT_TEXT)
      expect(screen.queryByText(CURATION_EMPTY_TEXT)).toBeNull()
    })

    it('is neither an alert nor an error', async () => {
      /* Eine fehlende Einwilligung ist kein Fehler: kein `Alert`, kein `role="alert"`, keine
       * Fehlerfarbe, kein Symbol. Geprüft über den Fehlerton der Design-Tokens, ohne den
       * Klassennamen als Literal zu schreiben - genau den hält der Design-Vertrag aus dem
       * Quelltext heraus. */
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        projectOut({ cloud_vision_detection_enabled: false }),
      )
      vi.mocked(photosApi.listPhotos).mockResolvedValue(listOut([]))

      const { container } = renderPage()

      const hint = await screen.findByText(CURATION_CLOUD_CONSENT_TEXT)
      expect(screen.queryByRole('alert')).toBeNull()
      expect(hint.className).not.toMatch(/danger|status-failed/)
      expect(container.querySelectorAll('[class*="danger"]')).toHaveLength(0)
      // Kein Symbol: der Hinweis ist ruhiger Text mit einem Weg, keine Meldung.
      expect(hint.querySelector('svg')).toBeNull()
    })

    it('does not repeat the consent text of the project settings', async () => {
      /* Der Zustimmungstext steht an genau EINER Stelle - zwei Fassungen driften, und eine
       * Einwilligung, die an zwei Orten verschieden beschrieben ist, ist keine. */
      expect(CURATION_CLOUD_CONSENT_TEXT).not.toMatch(/Bilddaten|übertragen|Anbieter/i)
    })

    it('stays away when the approval is given', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        projectOut({ cloud_vision_detection_enabled: true }),
      )
      vi.mocked(photosApi.listPhotos).mockResolvedValue(listOut([]))

      renderPage()

      await screen.findByText(CURATION_EMPTY_TEXT)
      expect(screen.queryByText(CURATION_CLOUD_CONSENT_TEXT)).toBeNull()
    })

    it('does not flash while the project is still loading', async () => {
      /* Der Hinweis erscheint erst, wenn Projekt UND Kuratierungsantwort geladen sind - sonst
       * blitzt er beim Laden eines freigegebenen Projekts kurz auf. */
      let resolveProject: ((value: ProjectOut) => void) | undefined
      vi.mocked(projectsApi.getProject).mockReturnValue(
        new Promise<ProjectOut>((resolve) => {
          resolveProject = resolve
        }),
      )
      vi.mocked(photosApi.listPhotos).mockResolvedValue(listOut([]))

      renderPage()

      await waitFor(() => expect(resolveProject).toBeDefined())
      expect(screen.queryByText(CURATION_CLOUD_CONSENT_TEXT)).toBeNull()
      expect(screen.queryByText(CURATION_EMPTY_TEXT)).toBeNull()

      resolveProject?.(projectOut({ cloud_vision_detection_enabled: true }))
      await screen.findByText(CURATION_EMPTY_TEXT)
    })
  })

  it('marks an unassessed photo on the tile and leaves an assessed one unmarked', async () => {
    /* Der EINZIGE Motiv-Marker der Kachel, als PAAR geprüft: eine Einzelprüfung bestünde auch
     * dann, wenn der Marker auf jeder Kachel stünde. */
    vi.mocked(photosApi.listPhotos).mockResolvedValue(
      listOut([
        photo({ id: 1, relative_path: 'a.jpg', motif_assessment: null, motifs: [] }),
        photo({
          id: 2,
          relative_path: 'b.jpg',
          ranking: ranking({ rank_position: 2, curation_position: 2, partition_size: 2 }),
        }),
      ]),
    )

    renderPage()

    await screen.findByLabelText('Verwerfen: a.jpg')
    expect(screen.getAllByRole('img', { name: 'Motive noch nicht bestimmt' })).toHaveLength(1)
  })

  it('shows an error alert with a retry when the listing fails', async () => {
    vi.mocked(photosApi.listPhotos).mockRejectedValue(new ApiError(500, 'Serverfehler'))

    renderPage()

    expect(await screen.findByText('Serverfehler')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Erneut versuchen' })).toBeInTheDocument()
  })

  it('collapses and expands a day', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue(listOut([photo({ id: 1 })]))

    renderPage()

    const trigger = await screen.findByRole('button', { expanded: true })
    await userEvent.click(trigger)

    expect(screen.getByRole('button', { expanded: false })).toBeInTheDocument()
    expect(screen.queryByLabelText('Verwerfen: a.jpg')).toBeNull()
  })

  it('rejects a photo and keeps it in place', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue(listOut([photo({ id: 1 })]))
    vi.mocked(ratingsApi.setRating).mockResolvedValue({
      user_id: 1,
      username: 'daniel',
      status: 'rejected',
    })

    renderPage()

    await userEvent.click(await screen.findByLabelText('Verwerfen: a.jpg'))

    await waitFor(() => {
      expect(ratingsApi.setRating).toHaveBeenCalledWith(1, 'rejected')
    })
    // Kein Nachrücken: das Foto bleibt an seiner Rasterposition.
    expect(screen.getByLabelText(/a\.jpg/)).toBeInTheDocument()
  })

  it('loads the further candidates of an event without a category key', async () => {
    /* Der Nachlade-Endpunkt adressiert seine Partition seit Spec 0427 allein über `event_id`. */
    vi.mocked(photosApi.listPhotos).mockResolvedValue(
      listOut([photo({ id: 1, ranking: ranking({ partition_size: 3 }) })]),
    )
    vi.mocked(photosApi.listCurationCandidates).mockResolvedValue(
      listOut([photo({ id: 9, relative_path: 'weiter.jpg' })], 2),
    )

    renderPage()

    await userEvent.click(await screen.findByRole('button', { name: /Weitere Kandidaten laden/ }))

    await waitFor(() => {
      expect(photosApi.listCurationCandidates).toHaveBeenCalledWith(1, {
        eventId: 1,
        afterRank: 1,
        limit: expect.any(Number),
        offset: 0,
      })
    })
    expect(await screen.findByLabelText('Verwerfen: weiter.jpg')).toBeInTheDocument()
  })

  it('shows the read-only motif strengths in the tile popover and points elsewhere', async () => {
    /* UI/UX-Abschnitt: das Info-Popover der Kachel rendert die Stärkeliste schreibgeschützt und
     * benennt, wo korrigiert wird. Die Abwesenheit der Korrekturschalter ist die eigentliche
     * Zusage - 24 Bedienelemente in einem Popover sind am Telefon nicht bedienbar. */
    vi.mocked(photosApi.listPhotos).mockResolvedValue(
      listOut([
        photo({
          id: 1,
          criterion_scores: [
            {
              criterion_key: 'sharpness',
              display_name: 'Schärfe',
              value: 0.8,
              source: 'local_heuristic',
              has_presence_threshold: false,
            },
          ],
        }),
      ]),
    )

    renderPage()

    await userEvent.click(await screen.findByRole('button', { name: 'Bewertungsdetails anzeigen' }))

    const list = await screen.findByRole('list', { name: 'Motive' })
    expect(within(list).getAllByRole('listitem')).toHaveLength(MOTIF_SET.items.length)
    expect(screen.getByText('Korrigieren in der Einzelbildansicht.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Trifft zu/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /^Trifft nicht zu/ })).toBeNull()
  })

  describe('der Auswahlvorschlag', () => {
    it('requests the selection instead of a top-N parameter', async () => {
      vi.mocked(photosApi.listPhotos).mockResolvedValue(listOut([]))

      renderPage()

      await waitFor(() => {
        expect(photosApi.listPhotos).toHaveBeenCalledWith(1, { selection: true })
      })
    })

    it('ignores an old topN search parameter instead of stumbling over it', async () => {
      /* Ein altes Lesezeichen bleibt gültig - die Route verliert ihren Suchparameter, aber ein
       * mitgeschickter stört nicht. */
      vi.mocked(photosApi.listPhotos).mockResolvedValue(listOut([photo({ id: 1 })]))

      renderPage('/projects/1/curate?topN=3')

      expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent('Kuratierung')
      await waitFor(() => {
        expect(photosApi.listPhotos).toHaveBeenCalledWith(1, { selection: true })
      })
    })

    it('says how small the draft is when the stock did not suffice', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        projectOut({ selection_target: 10, effective_selection_target: 10 }),
      )
      vi.mocked(photosApi.listPhotos).mockResolvedValue(listOut([photo({ id: 1 })]))

      renderPage()

      const hint = await screen.findByText(/reicht der bildbestand nicht/i)
      expect(hint).toHaveTextContent('1')
      expect(hint).toHaveTextContent('10')
    })

    it('gives the short-draft hint no error optics', async () => {
      /* Der Richtwert ist ein ZIEL und keine Obergrenze - ein kleinerer Vorschlag ist das
       * zugesagte Normalverhalten, kein Warnfall. Eine Warnoptik suggerierte Handlungsdruck, den
       * es nicht gibt. Als eigener Fall, weil der Positivtest darüber jede Hülle bestünde. */
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        projectOut({ selection_target: 10, effective_selection_target: 10 }),
      )
      vi.mocked(photosApi.listPhotos).mockResolvedValue(listOut([photo({ id: 1 })]))

      renderPage()

      const hint = await screen.findByText(/reicht der bildbestand nicht/i)
      expect(hint.closest('[role="alert"]')).toBeNull()
      expect(screen.queryByRole('alert')).toBeNull()
      expect(hint.querySelector('[data-icon]')).toBeNull()
    })

    it('says nothing when the draft is larger than the target', async () => {
      /* Dass jeder Foto-Moment vorkommt, ist die zugesagte Eigenschaft und kein
       * Überraschungsfall - der Gegenfall gehört dazu, ein reiner Positivtest bestünde auch bei
       * einem Hinweis in beide Richtungen. */
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        projectOut({ selection_target: 1, effective_selection_target: 1 }),
      )
      vi.mocked(photosApi.listPhotos).mockResolvedValue(
        listOut([
          photo({ id: 1 }),
          photo({ id: 2, ranking: ranking({ rank_position: 2, curation_position: 2 }) }),
        ]),
      )

      renderPage()

      await screen.findByRole('heading', { level: 2 })
      expect(screen.queryByText(/reicht der bildbestand nicht/i)).toBeNull()
    })

    it('says nothing about a short draft while the draft is empty', async () => {
      /* Der Leerzustand hat seinen eigenen Text; "0 von 10" daneben wäre eine zweite Erklärung
       * für denselben Zustand. */
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        projectOut({ selection_target: 10, effective_selection_target: 10 }),
      )
      vi.mocked(photosApi.listPhotos).mockResolvedValue(listOut([]))

      renderPage()

      expect(await screen.findByText(CURATION_EMPTY_TEXT)).toBeInTheDocument()
      expect(screen.queryByText(/reicht der bildbestand nicht/i)).toBeNull()
    })
  })
})
