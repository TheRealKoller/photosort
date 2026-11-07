import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import * as reviewApi from '../api/classificationReviews'
import * as motifsApi from '../api/motifs'
import * as photosApi from '../api/photos'
import type {
  ClassificationReviewCaseOut,
  ClassificationReviewDetailOut,
  ClassificationReviewSideOut,
  ClassificationReviewVerdictOut,
  ClassificationVerdict,
} from '../api/types'
import { MOTIF_SET } from '../test/motifSetFixture'
import { PROJECT_ROUTE_PATHS } from '../utils/projectRoutes'
import { ClassificationReviewDetailPage } from './ClassificationReviewDetailPage'

vi.mock('../api/classificationReviews')
vi.mock('../api/motifs')
vi.mock('../api/photos')

/*
 * Seite 2 der Pruefung (Spec 0616, UI/UX und Edge Case 8): Kopf, Fallansicht mit Urteilen und
 * Tastatur, `?foto=`, Uebersicht und Export. Geprueft wird ueber Rollen und `aria-*`, nicht ueber
 * Klassen - die Geometrie gehoert den E2E-Specs.
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

const NO_SIDE = {
  motifs: null,
  present: null,
  strength: null,
  excluded_document: null,
  album_level: null,
}

const ZERO_VERDICTS = { a_better: 0, b_better: 0, both_ok: 0, both_wrong: 0, open: 0 }

function caseRow(
  id: number,
  overrides: Partial<ClassificationReviewCaseOut> = {},
): ClassificationReviewCaseOut {
  return {
    id,
    photo_id: 500 + id,
    photo_position: 1,
    purpose: 'motifs',
    motif_key: null,
    a: { ...NO_SIDE, motifs: ['menschen'] },
    b: { ...NO_SIDE, motifs: ['menschen', 'landschaft'] },
    verdict: null,
    updated_by: null,
    updated_at: null,
    ...overrides,
  }
}

/** Foto 1: drei Faelle (Motive, Merkmal, Album), Foto 3: ein Fall. Foto 2 hat keinen Fall. */
const CASES: ClassificationReviewCaseOut[] = [
  caseRow(11),
  caseRow(12, {
    purpose: 'motif_feature',
    motif_key: 'landschaft',
    a: { ...NO_SIDE, present: false },
    b: { ...NO_SIDE, present: true, strength: 0.71 },
  }),
  caseRow(13, {
    purpose: 'album_level',
    a: { ...NO_SIDE, album_level: 2 },
    b: NO_SIDE,
  }),
  caseRow(31, {
    photo_id: 900,
    photo_position: 3,
    purpose: 'excluded_document',
    a: { ...NO_SIDE, excluded_document: true },
    b: { ...NO_SIDE, excluded_document: false },
  }),
]

function detailOut(
  overrides: Partial<ClassificationReviewDetailOut> = {},
): ClassificationReviewDetailOut {
  return {
    id: 99,
    created_at: '2026-11-07T10:30:00',
    created_by: { user_id: 1, username: 'daniel' },
    status: 'success',
    phase: null,
    sample_size: 30,
    seed: 12345,
    photo_count: 3,
    photos_processed: 3,
    unclassifiable_photo_count: 0,
    finished_at: '2026-11-07T11:00:00',
    error_message: null,
    sides: { a: EYE, b: CLOUD },
    counts_by_purpose: {
      motifs: { unit: 'photo', compared: 3, matching: 1, deviating: 2, presented: 2 },
      motif_feature: { unit: 'pair', compared: 24, matching: 23, deviating: 1, presented: 1 },
      excluded_document: { unit: 'photo', compared: 3, matching: 2, deviating: 1, presented: 1 },
      album_level: { unit: 'photo', compared: 3, matching: 2, deviating: 1, presented: 1 },
    },
    verdict_counts: { ...ZERO_VERDICTS, open: 4 },
    verdicts_by_purpose: {
      motifs: { ...ZERO_VERDICTS, open: 1 },
      motif_feature: { ...ZERO_VERDICTS, open: 1 },
      excluded_document: { ...ZERO_VERDICTS, open: 1 },
      album_level: { ...ZERO_VERDICTS, open: 1 },
    },
    ...overrides,
  }
}

function renderPage(search = '?foto=1') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const router = createMemoryRouter(
    [
      {
        path: PROJECT_ROUTE_PATHS.classificationReviewDetail,
        element: (
          <QueryClientProvider client={queryClient}>
            <ClassificationReviewDetailPage />
            {/* Ein echtes Textfeld neben der Seite - der Tastenschutz prueft den Fokus darin. */}
            <input aria-label="Notizfeld" />
          </QueryClientProvider>
        ),
      },
    ],
    { initialEntries: [`/projects/7/klassifizierung-pruefen/99${search}`] },
  )
  render(<RouterProvider router={router} />)
  return router
}

function verdictGroup(caseId: number) {
  return within(screen.getByTestId(`review-case-${caseId}`)).getByRole('group')
}

function verdictButton(caseId: number, name: RegExp) {
  return within(verdictGroup(caseId)).getByRole('button', { name })
}

function pressedStates(caseId: number) {
  return within(verdictGroup(caseId))
    .getAllByRole('button')
    .map((button) => button.getAttribute('aria-pressed'))
}

function written(verdict: ClassificationVerdict, caseId: number): ClassificationReviewVerdictOut {
  return {
    case_id: caseId,
    verdict,
    updated_by: { user_id: 2, username: 'anna' },
    updated_at: '2026-11-07T12:00:00',
  }
}

beforeEach(() => {
  vi.mocked(reviewApi.getClassificationReview).mockReset()
  vi.mocked(reviewApi.getClassificationReview).mockResolvedValue(detailOut())
  vi.mocked(reviewApi.listClassificationReviewCases).mockReset()
  vi.mocked(reviewApi.listClassificationReviewCases).mockResolvedValue({ cases: CASES })
  vi.mocked(reviewApi.setClassificationReviewVerdict).mockReset()
  vi.mocked(reviewApi.setClassificationReviewVerdict).mockImplementation(
    (_projectId, _reviewId, caseId, verdict) => Promise.resolve(written(verdict, caseId)),
  )
  vi.mocked(reviewApi.exportClassificationReview).mockReset()
  vi.mocked(motifsApi.listMotifs).mockResolvedValue(MOTIF_SET)
  vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockResolvedValue('blob:foto')
})

describe('ClassificationReviewDetailPage - Kopf', () => {
  it('zeigt beide Herkuenfte mit zugaenglicher Seitenmarke und den Fortschritt', async () => {
    renderPage()

    const origins = await screen.findByRole('list', { name: 'Herkunft der Seiten' })
    const items = within(origins).getAllByRole('listitem')
    expect(items[0]).toHaveTextContent('Seite A:Eye · eye-4.2.3 · Übersetzung v1')
    expect(items[1]).toHaveTextContent('Seite B:Cloud · Anthropic · Modell claude-sonnet-4-5')
    // Eye braucht seine Namensnennung an der Verwendungsstelle, Cloud nicht.
    expect(within(items[0]).getByTestId('eye-attribution')).toBeInTheDocument()
    expect(within(items[1]).queryByTestId('eye-attribution')).not.toBeInTheDocument()
    expect(screen.getByText('4 offen von 4')).toBeInTheDocument()
    expect(screen.queryByText(/ließ.* sich nicht klassifizieren/)).not.toBeInTheDocument()
  })

  it('nennt nicht klassifizierbare Fotos nur, wenn es welche gibt - als Satz', async () => {
    vi.mocked(reviewApi.getClassificationReview).mockResolvedValue(
      detailOut({ unclassifiable_photo_count: 2 }),
    )
    renderPage()

    expect(
      await screen.findByText(
        '2 Fotos ließen sich nicht klassifizieren und wurden für keinen Zweck verglichen.',
      ),
    ).toBeInTheDocument()
  })

  it('zeigt bei Fehlschlag den Alert mit der Meldung des Laufs', async () => {
    vi.mocked(reviewApi.getClassificationReview).mockResolvedValue(
      detailOut({ status: 'failed', error_message: 'Seite B lieferte kein Ergebnis.' }),
    )
    vi.mocked(reviewApi.listClassificationReviewCases).mockResolvedValue({ cases: [] })
    renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent('Seite B lieferte kein Ergebnis.')
  })

  it('meldet bei allen beurteilten Faellen den Abschluss, der Export bleibt bedienbar', async () => {
    vi.mocked(reviewApi.getClassificationReview).mockResolvedValue(
      detailOut({ verdict_counts: { ...ZERO_VERDICTS, both_ok: 4 } }),
    )
    renderPage()

    expect(
      await screen.findByText('Alle Fälle sind beurteilt. Der Export bleibt verfügbar.'),
    ).toBeInTheDocument()
    expect(screen.getByText('0 offen von 4')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Für die KI exportieren' })).toBeEnabled()
  })
})

describe('ClassificationReviewDetailPage - laufende Pruefung', () => {
  beforeEach(() => {
    vi.mocked(reviewApi.getClassificationReview).mockResolvedValue(
      detailOut({ status: 'running', phase: 'side_b', photos_processed: 1, finished_at: null }),
    )
  })

  it('zeigt den Teilschritt in einer aria-live-Region und laedt noch keine Faelle', async () => {
    renderPage()

    const stand = await screen.findByText('Seite B wird klassifiziert… 1 von 3 Fotos')
    expect(stand.closest('[aria-live]')).toHaveAttribute('aria-live', 'polite')
    expect(reviewApi.listClassificationReviewCases).not.toHaveBeenCalled()
    expect(screen.queryByRole('heading', { name: 'Übersicht' })).not.toBeInTheDocument()
  })

  it('sperrt den Export und nennt den Grund', async () => {
    renderPage()

    expect(await screen.findByRole('button', { name: 'Für die KI exportieren' })).toBeDisabled()
    expect(
      screen.getByText('Der Export ist erst nach Abschluss der Prüfung möglich.'),
    ).toBeInTheDocument()
  })
})

describe('ClassificationReviewDetailPage - gesperrte Urteile', () => {
  // Eine fehlgeschlagene Pruefung zeigt die bis dahin geschriebenen Faelle - aber gesperrt: der
  // Server nimmt Urteile nur an einer abgeschlossenen Pruefung an.
  it('sperrt alle Urteilsflaechen, und auch eine Taste schreibt nichts', async () => {
    vi.mocked(reviewApi.getClassificationReview).mockResolvedValue(
      detailOut({ status: 'failed', error_message: 'abgebrochen' }),
    )
    const user = userEvent.setup()
    renderPage()

    const group = await screen.findByRole('group', { name: 'Urteil zu Motive' })
    for (const button of within(group).getAllByRole('button')) {
      expect(button).toBeDisabled()
    }
    await user.keyboard('a')
    expect(reviewApi.setClassificationReviewVerdict).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Für die KI exportieren' })).toBeDisabled()
    expect(
      screen.getByText('Eine fehlgeschlagene Prüfung lässt sich nicht exportieren.'),
    ).toBeInTheDocument()
  })
})

describe('ClassificationReviewDetailPage - Fallansicht', () => {
  it('zeigt das Foto ohne Link und je Fall Zweck, Seitenmarken und Rohwerte', async () => {
    renderPage()

    expect(await screen.findByRole('heading', { name: 'Foto 1 von 3' })).toBeInTheDocument()
    const image = await screen.findByRole('img', { name: 'Foto 1 von 3' })
    expect(image.closest('a')).toBeNull()
    expect(photosApi.fetchPhotoImageBlobUrl).toHaveBeenCalledWith(511, 'display')

    const list = screen.getByRole('list', { name: 'Fälle dieses Fotos' })
    expect(
      within(list)
        .getAllByRole('heading')
        .map((heading) => heading.textContent),
    ).toEqual(['Motive', 'Merkmal: Landschaft', 'Albumtauglichkeit'])

    const motifs = within(screen.getByTestId('review-case-11'))
    expect(motifs.getByText('Seite A')).toBeInTheDocument()
    expect(motifs.getByText('Menschen')).toBeInTheDocument()
    expect(motifs.getByText('Menschen, Landschaft')).toBeInTheDocument()

    const feature = within(screen.getByTestId('review-case-12'))
    expect(feature.getByText('nein')).toBeInTheDocument()
    expect(feature.getByText('ja')).toBeInTheDocument()

    // Die Albumstufe als bestehender Text; die schweigende Seite als "keine Aussage", nie als 0.
    const album = within(screen.getByTestId('review-case-13'))
    expect(album.getByText('Stufe 2 von 5')).toBeInTheDocument()
    expect(album.getByText('keine Aussage')).toBeInTheDocument()
  })

  it('zeigt die vier Urteile in fester Reihenfolge mit der Taste im Kaestchen', async () => {
    renderPage()

    const group = await screen.findByRole('group', { name: 'Urteil zu Motive' })
    const buttons = within(group).getAllByRole('button')
    expect(buttons.map((button) => button.textContent)).toEqual([
      'A besserA',
      'B besserB',
      'beide okO',
      'beide falschF',
    ])
    expect(buttons.map((button) => button.getAttribute('aria-keyshortcuts'))).toEqual([
      'A',
      'B',
      'O',
      'F',
    ])
    expect(pressedStates(11)).toEqual(['false', 'false', 'false', 'false'])
  })

  it('zeigt ein gesetztes Urteil gedrueckt und nennt seinen Schreiber', async () => {
    vi.mocked(reviewApi.listClassificationReviewCases).mockResolvedValue({
      cases: [
        caseRow(11, {
          verdict: 'both_wrong',
          updated_by: { user_id: 2, username: 'anna' },
          updated_at: '2026-11-07T12:00:00',
        }),
      ],
    })
    renderPage()

    await screen.findByRole('group', { name: 'Urteil zu Motive' })
    expect(pressedStates(11)).toEqual(['false', 'false', 'false', 'true'])
    expect(verdictButton(11, /beide falsch/)).toHaveTextContent('von anna')
  })

  it.each([
    ['A besser', 'a_better', 0],
    ['B besser', 'b_better', 1],
    ['beide ok', 'both_ok', 2],
    ['beide falsch', 'both_wrong', 3],
  ] as const)(
    'schreibt mit "%s" genau dieses Urteil und laesst die uebrigen Faelle unberuehrt',
    async (label, verdict, index) => {
      const user = userEvent.setup()
      renderPage()

      await screen.findByRole('group', { name: 'Urteil zu Motive' })
      await user.click(verdictButton(11, new RegExp(`^${label}`)))

      expect(reviewApi.setClassificationReviewVerdict).toHaveBeenCalledTimes(1)
      expect(reviewApi.setClassificationReviewVerdict).toHaveBeenCalledWith(7, 99, 11, verdict)
      await waitFor(() => expect(pressedStates(11)[index]).toBe('true'))
      expect(pressedStates(11).filter((state) => state === 'true')).toHaveLength(1)
      expect(pressedStates(12)).toEqual(['false', 'false', 'false', 'false'])
      expect(pressedStates(13)).toEqual(['false', 'false', 'false', 'false'])
      expect(verdictButton(11, new RegExp(`^${label}`))).toHaveTextContent('von anna')
    },
  )

  it('meldet einen Speicherfehler, ohne das Urteil als gesetzt zu zeigen', async () => {
    vi.mocked(reviewApi.setClassificationReviewVerdict).mockRejectedValue(new Error('offline'))
    const user = userEvent.setup()
    renderPage()

    await screen.findByRole('group', { name: 'Urteil zu Motive' })
    await user.click(verdictButton(11, /^A besser/))

    expect(
      await screen.findByText('Das Urteil konnte nicht gespeichert werden.'),
    ).toBeInTheDocument()
    expect(pressedStates(11)).toEqual(['false', 'false', 'false', 'false'])
  })
})

describe('ClassificationReviewDetailPage - Tastatur', () => {
  it.each([
    ['a', 'a_better'],
    ['B', 'b_better'],
    ['o', 'both_ok'],
    ['f', 'both_wrong'],
  ] as const)('Taste %s schreibt %s am markierten Fall', async (key, verdict) => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('group', { name: 'Urteil zu Motive' })

    await user.keyboard(key)

    expect(reviewApi.setClassificationReviewVerdict).toHaveBeenCalledTimes(1)
    expect(reviewApi.setClassificationReviewVerdict).toHaveBeenCalledWith(7, 99, 11, verdict)
  })

  it.each([
    ['Strg+A', '{Control>}a{/Control}'],
    ['Strg+F', '{Control>}f{/Control}'],
    ['Meta+B', '{Meta>}b{/Meta}'],
    ['Alt+O', '{Alt>}o{/Alt}'],
  ])('%s schreibt nichts und sendet keinen Request', async (_name, keys) => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('group', { name: 'Urteil zu Motive' })

    await user.keyboard(keys)

    expect(reviewApi.setClassificationReviewVerdict).not.toHaveBeenCalled()
  })

  it('schreibt nichts, solange der Fokus in einem Textfeld liegt', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('group', { name: 'Urteil zu Motive' })

    await user.click(screen.getByRole('textbox', { name: 'Notizfeld' }))
    await user.keyboard('abof')

    expect(reviewApi.setClassificationReviewVerdict).not.toHaveBeenCalled()
    expect(screen.getByRole('textbox', { name: 'Notizfeld' })).toHaveValue('abof')
  })

  // Die Bewertungstasten des Bestands sind hier inert: weder Urteil noch Bewertung.
  it('laesst die Ziffern 1, 2 und 3 ohne jede Wirkung', async () => {
    const user = userEvent.setup()
    const router = renderPage()
    await screen.findByRole('group', { name: 'Urteil zu Motive' })

    await user.keyboard('123')

    expect(reviewApi.setClassificationReviewVerdict).not.toHaveBeenCalled()
    expect(pressedStates(11)).toEqual(['false', 'false', 'false', 'false'])
    expect(router.state.location.search).toBe('?foto=1')
  })

  it('springt nach einem Urteil zum naechsten offenen Fall desselben Fotos', async () => {
    const user = userEvent.setup()
    const router = renderPage()
    await screen.findByRole('group', { name: 'Urteil zu Motive' })
    expect(screen.getByTestId('review-case-11')).toHaveAttribute('aria-current', 'true')

    await user.keyboard('a')
    await waitFor(() =>
      expect(screen.getByTestId('review-case-12')).toHaveAttribute('aria-current', 'true'),
    )
    await user.keyboard('b')
    await waitFor(() =>
      expect(screen.getByTestId('review-case-13')).toHaveAttribute('aria-current', 'true'),
    )
    await user.keyboard('o')

    expect(vi.mocked(reviewApi.setClassificationReviewVerdict).mock.calls).toEqual([
      [7, 99, 11, 'a_better'],
      [7, 99, 12, 'b_better'],
      [7, 99, 13, 'both_ok'],
    ])
    // Der letzte offene Fall des Fotos ist beurteilt - das Foto wechselt trotzdem nicht.
    await waitFor(() => expect(pressedStates(13)[2]).toBe('true'))
    expect(router.state.location.search).toBe('?foto=1')
  })

  it('sendet bei einem zweiten Tastendruck waehrend des Speicherns keinen zweiten Request', async () => {
    // Executor-Form, weil das Projekt-`lib` ES2023 ist (`Promise.withResolvers` erst ab ES2024).
    let resolve: (value: ClassificationReviewVerdictOut) => void = () => {}
    vi.mocked(reviewApi.setClassificationReviewVerdict).mockReturnValue(
      new Promise((done) => {
        resolve = done
      }),
    )
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('group', { name: 'Urteil zu Motive' })

    await user.keyboard('ab')

    expect(reviewApi.setClassificationReviewVerdict).toHaveBeenCalledTimes(1)
    resolve(written('a_better', 11))
    await waitFor(() => expect(pressedStates(11)[0]).toBe('true'))
  })

  it('markiert per Klick einen anderen Fall, dessen Urteil die Taste dann setzt', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('group', { name: 'Urteil zu Motive' })

    await user.click(screen.getByRole('heading', { name: 'Albumtauglichkeit' }))
    await user.keyboard('f')

    expect(reviewApi.setClassificationReviewVerdict).toHaveBeenCalledWith(7, 99, 13, 'both_wrong')
  })

  it('wechselt mit den Pfeiltasten das Foto und setzt den Fokus auf die Fotoueberschrift', async () => {
    const user = userEvent.setup()
    const router = renderPage()
    await screen.findByRole('heading', { name: 'Foto 1 von 3' })

    await user.keyboard('{ArrowRight}')

    const heading = await screen.findByRole('heading', { name: 'Foto 3 von 3' })
    expect(heading).toHaveFocus()
    expect(router.state.location.search).toBe('?foto=3')

    await user.keyboard('{ArrowLeft}')
    expect(await screen.findByRole('heading', { name: 'Foto 1 von 3' })).toHaveFocus()
  })
})

describe('ClassificationReviewDetailPage - ?foto=', () => {
  it('zeigt bei gueltigem Wert genau die Faelle dieses Fotos', async () => {
    renderPage('?foto=3')

    expect(await screen.findByRole('heading', { name: 'Foto 3 von 3' })).toBeInTheDocument()
    const list = screen.getByRole('list', { name: 'Fälle dieses Fotos' })
    expect(
      within(list)
        .getAllByRole('heading')
        .map((heading) => heading.textContent),
    ).toEqual(['Dokument-Ausschluss'])
    expect(within(list).getByText('ja')).toBeInTheDocument()
    expect(within(list).getByText('nein')).toBeInTheDocument()
  })

  it.each(['', '?foto=0', '?foto=4', '?foto=abc', '?foto=1.5', '?foto=-1', '?foto=%201'])(
    'ersetzt "%s" per replace auf das erste offene Foto, ohne weitere Serverrunde',
    async (search) => {
      vi.mocked(reviewApi.listClassificationReviewCases).mockResolvedValue({
        cases: CASES.map((reviewCase) =>
          reviewCase.photo_position === 1 ? { ...reviewCase, verdict: 'both_ok' } : reviewCase,
        ),
      })
      const router = renderPage(search)

      expect(await screen.findByRole('heading', { name: 'Foto 3 von 3' })).toBeInTheDocument()
      expect(router.state.location.search).toBe('?foto=3')
      expect(router.state.historyAction).toBe('REPLACE')
      expect(reviewApi.getClassificationReview).toHaveBeenCalledTimes(1)
      expect(reviewApi.listClassificationReviewCases).toHaveBeenCalledTimes(1)
    },
  )

  it('blaettert vor und zurueck nur ueber Fotos mit Fall und springt zum naechsten offenen', async () => {
    vi.mocked(reviewApi.getClassificationReview).mockResolvedValue(detailOut({ photo_count: 5 }))
    vi.mocked(reviewApi.listClassificationReviewCases).mockResolvedValue({
      cases: [
        caseRow(11, { verdict: 'both_ok' }),
        caseRow(31, { photo_position: 3, verdict: 'both_ok' }),
        caseRow(51, { photo_position: 5 }),
      ],
    })
    const user = userEvent.setup()
    const router = renderPage('?foto=1')

    await screen.findByRole('heading', { name: 'Foto 1 von 5' })
    expect(screen.getByRole('button', { name: 'Vorheriges Foto' })).toBeDisabled()

    await user.click(screen.getByRole('button', { name: 'Nächstes Foto' }))
    expect(await screen.findByRole('heading', { name: 'Foto 3 von 5' })).toBeInTheDocument()
    expect(router.state.historyAction).toBe('PUSH')

    await user.click(screen.getByRole('button', { name: 'Vorheriges Foto' }))
    expect(await screen.findByRole('heading', { name: 'Foto 1 von 5' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Nächstes offenes Foto' }))
    expect(await screen.findByRole('heading', { name: 'Foto 5 von 5' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Nächstes Foto' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Nächstes offenes Foto' })).toBeDisabled()
  })
})

describe('ClassificationReviewDetailPage - Uebersicht', () => {
  it('trennt Fotos und Paare und nennt die Einheit im Spaltenkopf', async () => {
    renderPage()

    const table = await screen.findByRole('table', { name: 'Abweichungen' })
    const [photoGroup, pairGroup] = within(table).getAllByRole('rowgroup')

    const photoHeads = within(photoGroup).getAllByRole('columnheader')
    expect(photoHeads.map((head) => head.textContent)).toEqual([
      'Zwecke',
      'übereinstimmendFotos',
      'abweichendFotos',
      'vorgelegtFotos',
    ])
    expect(
      within(photoGroup)
        .getAllByRole('rowheader')
        .map((head) => head.textContent),
    ).toEqual(['Motive', 'Dokument-Ausschluss', 'Albumtauglichkeit'])
    expect(within(photoGroup).getByRole('row', { name: /Motive/ })).toHaveTextContent('Motive122')

    const pairHeads = within(pairGroup).getAllByRole('columnheader')
    expect(pairHeads.map((head) => head.textContent)).toEqual([
      'Merkmale (Foto × Motiv)',
      'übereinstimmendPaare',
      'abweichendPaare',
      'vorgelegtPaare',
    ])
    expect(within(pairGroup).getByRole('row', { name: /^Merkmale 23/ })).toHaveTextContent(
      'Merkmale2311',
    )
  })

  it('zaehlt die Urteile je Zweck und gesamt - ohne Gesamturteil', async () => {
    vi.mocked(reviewApi.getClassificationReview).mockResolvedValue(
      detailOut({
        verdict_counts: { a_better: 2, b_better: 1, both_ok: 0, both_wrong: 0, open: 1 },
        verdicts_by_purpose: {
          motifs: { a_better: 1, b_better: 0, both_ok: 0, both_wrong: 0, open: 0 },
          motif_feature: { a_better: 0, b_better: 1, both_ok: 0, both_wrong: 0, open: 0 },
          excluded_document: { ...ZERO_VERDICTS, open: 1 },
          album_level: { a_better: 1, b_better: 0, both_ok: 0, both_wrong: 0, open: 0 },
        },
      }),
    )
    renderPage()

    const table = await screen.findByRole('table', { name: 'Urteile' })
    expect(
      within(table)
        .getAllByRole('columnheader')
        .map((head) => head.textContent),
    ).toEqual(['Zweck', 'A besser', 'B besser', 'beide ok', 'beide falsch', 'offen'])
    expect(within(table).getByRole('row', { name: /^Motive/ })).toHaveTextContent('Motive10000')
    expect(within(table).getByRole('row', { name: /^gesamt/ })).toHaveTextContent('gesamt21001')
    expect(screen.queryByText(/Empfehlung|besser geeignet|Sieger/)).not.toBeInTheDocument()
  })

  it('nennt einen Zweck ohne gemeinsame Aussage "nicht verglichen" mit der schweigenden Seite', async () => {
    vi.mocked(reviewApi.getClassificationReview).mockResolvedValue(
      detailOut({
        sides: { a: CLOUD, b: LOCAL },
        counts_by_purpose: {
          ...detailOut().counts_by_purpose,
          excluded_document: {
            unit: 'photo',
            compared: 0,
            matching: 0,
            deviating: 0,
            presented: 0,
          },
          album_level: { unit: 'photo', compared: 0, matching: 0, deviating: 0, presented: 0 },
        },
      }),
    )
    renderPage()

    const table = await screen.findByRole('table', { name: 'Abweichungen' })
    for (const purpose of ['Dokument-Ausschluss', 'Albumtauglichkeit']) {
      const row = within(table).getByRole('row', { name: new RegExp(`^${purpose}`) })
      expect(row).toHaveTextContent('nicht verglichen — Seite B trifft dazu keine Aussage')
      expect(within(row).queryAllByRole('cell')).toHaveLength(1)
    }
  })

  it('sagt "keine Fotos verglichen" mit der Zahl der fehlgeschlagenen Fotos', async () => {
    const none = { compared: 0, matching: 0, deviating: 0, presented: 0 }
    vi.mocked(reviewApi.getClassificationReview).mockResolvedValue(
      detailOut({
        sides: { a: LOCAL, b: CLOUD },
        unclassifiable_photo_count: 3,
        counts_by_purpose: {
          motifs: { unit: 'photo', ...none },
          motif_feature: { unit: 'pair', ...none },
          excluded_document: { unit: 'photo', ...none },
          album_level: { unit: 'photo', ...none },
        },
        verdict_counts: ZERO_VERDICTS,
        verdicts_by_purpose: {
          motifs: ZERO_VERDICTS,
          motif_feature: ZERO_VERDICTS,
          excluded_document: ZERO_VERDICTS,
          album_level: ZERO_VERDICTS,
        },
      }),
    )
    vi.mocked(reviewApi.listClassificationReviewCases).mockResolvedValue({ cases: [] })
    renderPage()

    const table = await screen.findByRole('table', { name: 'Abweichungen' })
    expect(
      within(table).getAllByText('keine Fotos verglichen - 3 Fotos fehlgeschlagen'),
    ).toHaveLength(4)
    expect(within(table).queryByText(/trifft dazu keine Aussage/)).not.toBeInTheDocument()
  })
})

describe('ClassificationReviewDetailPage - Export', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('laedt die Datei ueber den authentifizierten Blob-Weg und nennt, was sie nicht enthaelt', async () => {
    const blob = new Blob(['{}'], { type: 'application/json' })
    vi.mocked(reviewApi.exportClassificationReview).mockResolvedValue(blob)
    const createObjectURL = vi.fn(() => 'blob:export')
    const revokeObjectURL = vi.fn()
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL, revokeObjectURL }))
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const user = userEvent.setup()
    renderPage()

    const button = await screen.findByRole('button', { name: 'Für die KI exportieren' })
    expect(button).toHaveAccessibleDescription(
      /keine Bilddaten, keine Dateinamen, keine Orte und keine Namen/,
    )
    await user.click(button)

    await waitFor(() => expect(revokeObjectURL).toHaveBeenCalledWith('blob:export'))
    expect(reviewApi.exportClassificationReview).toHaveBeenCalledWith(7, 99)
    expect(createObjectURL).toHaveBeenCalledWith(blob)
    expect(click).toHaveBeenCalledTimes(1)
    const anchor = click.mock.contexts[0] as HTMLAnchorElement
    expect(anchor.download).toBe('klassifizierungspruefung-99.json')
    expect(anchor.isConnected).toBe(false)
  })

  it('meldet einen gescheiterten Export', async () => {
    vi.mocked(reviewApi.exportClassificationReview).mockRejectedValue(new Error('409'))
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole('button', { name: 'Für die KI exportieren' }))

    expect(await screen.findByText('Der Export konnte nicht geladen werden.')).toBeInTheDocument()
  })
})
