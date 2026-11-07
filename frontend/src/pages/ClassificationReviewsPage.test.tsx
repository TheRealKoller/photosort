import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as reviewApi from '../api/classificationReviews'
import type {
  ClassificationReviewListItemOut,
  ClassificationReviewOptionsOut,
  ClassificationReviewSideOut,
} from '../api/types'
import { PROJECT_ROUTE_PATHS } from '../utils/projectRoutes'
import { ClassificationReviewsPage } from './ClassificationReviewsPage'

vi.mock('../api/classificationReviews')

/*
 * Seite 1 der Pruefung (Spec 0616, UI/UX): Liste und Anlegen. Geprueft werden Kopf und
 * Umschalter, der leere Zustand mit offenem Panel, die Reihenfolge und der Stand jeder Zeile,
 * das Linkziel und die 44-px-Trefferflaeche der ganzen Zeile.
 */

const LOCAL: ClassificationReviewSideOut = {
  kind: 'local',
  provider: null,
  model: null,
  eye_model_revision: null,
  eye_mapping_version: null,
  estimated_cost_usd: 0,
  cost_usd: 0,
}

const CLOUD: ClassificationReviewSideOut = {
  kind: 'cloud',
  provider: 'anthropic',
  model: 'claude-sonnet-4-5',
  eye_model_revision: null,
  eye_mapping_version: null,
  estimated_cost_usd: 1.2,
  cost_usd: 1.1,
}

const EYE: ClassificationReviewSideOut = {
  kind: 'eye',
  provider: null,
  model: null,
  eye_model_revision: 'eye-4.2.3',
  eye_mapping_version: 'v1',
  estimated_cost_usd: 0,
  cost_usd: 0,
}

const OPTIONS: ClassificationReviewOptionsOut = {
  sample_size: { default: 30, min: 1, max: 200 },
  kinds: [
    { kind: 'cloud', available: true, unavailable_reasons: [] },
    { kind: 'eye', available: true, unavailable_reasons: [] },
    { kind: 'local', available: true, unavailable_reasons: [] },
  ],
  cloud_models: [
    { provider: 'anthropic', model: 'claude-sonnet-4-5', available: true, unavailable_reasons: [] },
  ],
  eye_mappings: [
    {
      eye_model_revision: 'eye-4.2.3',
      eye_mapping_version: 'v1',
      available: true,
      unavailable_reasons: [],
    },
  ],
}

function listItem(
  id: number,
  overrides: Partial<ClassificationReviewListItemOut> = {},
): ClassificationReviewListItemOut {
  return {
    id,
    created_at: '2026-11-07T10:30:00',
    created_by: { user_id: 1, username: 'daniel' },
    status: 'success',
    phase: null,
    sides: { a: LOCAL, b: CLOUD },
    case_count: 8,
    case_open: 3,
    photo_count: 12,
    unclassifiable_photo_count: 0,
    ...overrides,
  }
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  render(
    <MemoryRouter initialEntries={['/projects/7/klassifizierung-pruefen']}>
      <Routes>
        <Route
          path={PROJECT_ROUTE_PATHS.classificationReviews}
          element={<ClassificationReviewsPage />}
        />
        <Route
          path={PROJECT_ROUTE_PATHS.classificationReviewDetail}
          element={<p>Fallansicht der Prüfung</p>}
        />
      </Routes>
    </MemoryRouter>,
    { wrapper },
  )
}

/** Alle Zeilen-Links in DOM-Reihenfolge. */
function rowLinks() {
  return screen
    .getAllByRole('link')
    .filter((link) => /\/klassifizierung-pruefen\/\d+$/.test(link.getAttribute('href') ?? ''))
}

describe('ClassificationReviewsPage', () => {
  beforeEach(() => {
    vi.mocked(reviewApi.listClassificationReviews).mockReset()
    vi.mocked(reviewApi.getClassificationReviewOptions).mockReset()
    vi.mocked(reviewApi.getClassificationReviewEstimate).mockReset()
    vi.mocked(reviewApi.createClassificationReview).mockReset()
    vi.mocked(reviewApi.getClassificationReviewOptions).mockResolvedValue(OPTIONS)
    vi.mocked(reviewApi.listClassificationReviews).mockResolvedValue([
      listItem(12, { created_at: '2026-11-07T10:30:00' }),
      listItem(11, { created_at: '2026-11-06T09:15:00', sides: { a: EYE, b: LOCAL } }),
    ])
  })

  it('traegt Kopf, dauerhaften Satz und den Umschalter des Anlege-Panels', async () => {
    renderPage()

    expect(
      screen.getByRole('heading', { level: 1, name: 'Klassifizierung prüfen' }),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        'Zwei Klassifizierungsverfahren am Foto gegenüberstellen und beurteilen. Die geltenden Ergebnisse der Fotos bleiben dabei unverändert.',
      ),
    ).toBeInTheDocument()

    const toggle = screen.getByRole('button', { name: 'Neue Prüfung anlegen' })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    const panelId = toggle.getAttribute('aria-controls')
    expect(panelId).not.toBeNull()

    await userEvent.setup().click(toggle)

    const panel = screen.getByRole('region', { name: 'Neue Prüfung anlegen' })
    expect(panel).toHaveAttribute('id', panelId)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
  })

  it('zeigt bei leerer Liste das Panel von Anfang an offen', async () => {
    vi.mocked(reviewApi.listClassificationReviews).mockResolvedValue([])

    renderPage()

    expect(
      await screen.findByRole('button', { name: 'Neue Prüfung anlegen', expanded: true }),
    ).toBeEnabled()
    expect(screen.getByRole('region', { name: 'Neue Prüfung anlegen' })).toBeInTheDocument()
    expect(screen.getByText('Noch keine Prüfung angelegt.')).toBeInTheDocument()
  })

  it('haelt die Serverreihenfolge ein: neueste Pruefung zuerst', async () => {
    renderPage()

    await screen.findByRole('link', { name: /07\.11\.2026, 10:30/ })

    expect(rowLinks().map((link) => link.getAttribute('href'))).toEqual([
      '/projects/7/klassifizierung-pruefen/12',
      '/projects/7/klassifizierung-pruefen/11',
    ])
  })

  it('zeigt je Zeile Datum, Anleger und die Herkunft beider Seiten', async () => {
    renderPage()

    const first = await screen.findByRole('link', { name: /07\.11\.2026, 10:30/ })

    expect(first).toHaveTextContent('angelegt von daniel')
    expect(first).toHaveTextContent('Lokal · ohne Sehenswürdigkeits-Beitrag')
    expect(first).toHaveTextContent('Cloud · Anthropic · Modell claude-sonnet-4-5')
    expect(within(first).getByText('A')).toBeInTheDocument()
    expect(within(first).getByText('B')).toBeInTheDocument()
  })

  it('nennt den Stand jeder Pruefung', async () => {
    vi.mocked(reviewApi.listClassificationReviews).mockResolvedValue([
      listItem(5, { status: 'running', case_count: 0, case_open: 0 }),
      listItem(4, { status: 'failed', case_count: 0, case_open: 0 }),
      listItem(3, { case_count: 4, case_open: 2 }),
      listItem(2, { case_count: 4, case_open: 0 }),
      listItem(1, { case_count: 0, case_open: 0 }),
    ])

    renderPage()

    expect(await screen.findByText('läuft…')).toBeInTheDocument()
    expect(screen.getByText('fehlgeschlagen')).toBeInTheDocument()
    expect(screen.getByText('2 von 4 Fällen offen')).toBeInTheDocument()
    expect(screen.getByText('alle beurteilt')).toBeInTheDocument()
    expect(screen.getByText('keine Abweichungen')).toBeInTheDocument()
    expect(
      screen.getByText('Die beiden Verfahren stimmen auf allen Fotos überein.'),
    ).toBeInTheDocument()
  })

  // Edge Case 4: scheitern alle Fotos einzeln, steht in der Zeile KEINE Uebereinstimmung, sondern
  // die Zahl der fehlgeschlagenen Fotos (AK 9).
  it('behauptet keine Uebereinstimmung, wenn kein Foto verglichen wurde', async () => {
    vi.mocked(reviewApi.listClassificationReviews).mockResolvedValue([
      listItem(2, {
        case_count: 0,
        case_open: 0,
        photo_count: 12,
        unclassifiable_photo_count: 12,
      }),
      listItem(1, {
        case_count: 0,
        case_open: 0,
        photo_count: 12,
        unclassifiable_photo_count: 0,
      }),
    ])

    renderPage()

    expect(
      await screen.findByText('keine Fotos verglichen - 12 Fotos fehlgeschlagen'),
    ).toBeInTheDocument()
    // Die andere Zeile ohne Fall behaelt die Uebereinstimmung - genau EINMAL.
    expect(
      screen.getAllByText('Die beiden Verfahren stimmen auf allen Fotos überein.'),
    ).toHaveLength(1)
  })

  it('macht die ganze Zeile zur Trefferflaeche von mindestens 44 px', async () => {
    renderPage()

    const first = await screen.findByRole('link', { name: /07\.11\.2026, 10:30/ })

    expect(first).toHaveClass('min-h-11')
    expect(first).toHaveAttribute('href', '/projects/7/klassifizierung-pruefen/12')
  })

  it('meldet eine gescheiterte juengste Pruefung und legt von dort erneut an', async () => {
    vi.mocked(reviewApi.listClassificationReviews).mockResolvedValue([
      listItem(9, { status: 'failed', case_count: 0, case_open: 0 }),
    ])

    renderPage()

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(
      'Die letzte Prüfung ist fehlgeschlagen. Sie wird nicht automatisch wiederholt.',
    )

    await userEvent.setup().click(within(alert).getByRole('button', { name: 'Erneut anlegen' }))

    expect(screen.getByRole('region', { name: 'Neue Prüfung anlegen' })).toBeInTheDocument()
  })

  it('fuehrt nach erfolgreichem Anlegen zur Uebersicht der neuen Pruefung', async () => {
    vi.mocked(reviewApi.listClassificationReviews).mockResolvedValue([])
    vi.mocked(reviewApi.getClassificationReviewEstimate).mockResolvedValue({
      photo_count: 10,
      a: {
        kind: 'local',
        provider: null,
        model: null,
        photo_count: 10,
        price_per_image_usd: 0,
        estimated_cost_usd: 0,
      },
      b: {
        kind: 'eye',
        provider: null,
        model: null,
        photo_count: 10,
        price_per_image_usd: 0,
        estimated_cost_usd: 0,
      },
    })
    vi.mocked(reviewApi.createClassificationReview).mockResolvedValue({ id: 21, status: 'running' })
    const user = userEvent.setup()

    renderPage()
    const sideA = within(await screen.findByRole('group', { name: 'Seite A' }))
    await user.click(sideA.getByRole('radio', { name: /Lokal/ }))
    const sideB = within(screen.getByRole('group', { name: 'Seite B' }))
    await user.click(sideB.getByRole('radio', { name: /Eye · eye-4.2.3/ }))
    await user.click(screen.getByRole('button', { name: 'Prüfung starten' }))

    expect(await screen.findByText('Fallansicht der Prüfung')).toBeInTheDocument()
    expect(reviewApi.createClassificationReview).toHaveBeenCalledWith(7, {
      a: { kind: 'local' },
      b: { kind: 'eye', eye_mapping_version: 'v1' },
      sample_size: 30,
    })
  })

  it('meldet einen Ladefehler der Liste mit Servermeldung und Wiederholung', async () => {
    vi.mocked(reviewApi.listClassificationReviews)
      .mockRejectedValueOnce(new Error('Server weg'))
      .mockResolvedValueOnce([listItem(12)])

    renderPage()

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Fehler beim Laden der Prüfungen.')

    await userEvent.setup().click(within(alert).getByRole('button', { name: 'Erneut versuchen' }))

    expect(await screen.findByRole('link', { name: /07\.11\.2026/ })).toBeInTheDocument()
  })
})
