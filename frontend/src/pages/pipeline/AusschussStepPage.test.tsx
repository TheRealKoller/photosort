import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Outlet, Route, Routes, useLocation, useNavigate } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as ausschussApi from '../../api/ausschuss'
import { ApiError } from '../../api/client'
import * as duplicatesApi from '../../api/duplicates'
import * as projectsApi from '../../api/projects'
import type {
  AusschussGroupEntry,
  AusschussOut,
  AusschussPhotoEntry,
  DuplicateDecision,
  DuplicateGroupOut,
  PhotoOut,
  ProjectOut,
  ScoringRunSummary,
  SuggestionReason,
} from '../../api/types'
import {
  AUSSCHUSS_EMPTY_TEXT,
  AUSSCHUSS_MISSING_ENTRY_TEXT,
  AusschussStepPage,
} from './AusschussStepPage'
import type { PipelineOutletContext } from './ProjectPipelineLayout'
import {
  AUSSCHUSS_CONFIRM_LABEL,
  AUSSCHUSS_NOTHING_SORTED_TEXT,
  NEXT_UNAVAILABLE_TEXT,
  RUN_STEP_TEXTS,
} from '../../utils/stepActionTexts'

const START = RUN_STEP_TEXTS.ausschuss.start
const RERUN = RUN_STEP_TEXTS.ausschuss.rerun
const BESTAETIGT = '2026-07-20T11:00:00Z'

/** Ein zurückgehaltenes Promise (die `lib`-Einstellung kennt `Promise.withResolvers` nicht). */
function zurueckgehalten<T>(): { promise: Promise<T>; resolve: (value: T) => void } {
  let resolve: (value: T) => void = () => {}
  const promise = new Promise<T>((inner) => {
    resolve = inner
  })
  return { promise, resolve }
}

vi.mock('../../api/projects')
vi.mock('../../api/duplicates')
vi.mock('../../api/ausschuss')
vi.mock('../../components/PhotoImage', () => ({
  PhotoImage: ({ alt }: { alt: string }) => <img alt={alt} />,
}))

function photo(id: number): PhotoOut {
  return {
    id,
    relative_path: `Reise/serie-${id}.jpg`,
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
    persons: [],
  }
}

function entry(
  id: number,
  {
    reason = 'low_quality',
    decision = null,
    groupAnchorPhotoId = null,
    keepPossible = reason === 'duplicate',
  }: {
    reason?: SuggestionReason
    decision?: DuplicateDecision | null
    groupAnchorPhotoId?: number | null
    keepPossible?: boolean
  } = {},
): AusschussPhotoEntry {
  // `keepPossible` ist der SERVERWERT (`duplicates.py::keep_possible_for`). Der Vorgabewert bildet
  // nur den Regelfall ab - ein Duplikat hat eine Gruppe, eine Unscharfe-Ablehnung nicht - und darf
  // nicht als Ableitungsregel gelesen werden: Der Fall "Entscheidungszeile ohne offenen Vorschlag"
  // traegt `true` bei `reason === 'low_quality'` (siehe der Test dazu).
  return {
    kind: 'photo',
    photo: photo(id),
    reason,
    decision,
    group_anchor_photo_id: groupAnchorPhotoId,
    keep_possible: keepPossible,
  }
}

function stapel(anchor: number, cover: number, groupSize = 3): AusschussGroupEntry {
  return {
    kind: 'group',
    group_anchor_photo_id: anchor,
    cover: photo(cover),
    member_count: 2,
    group_size: groupSize,
    decision_counts: { undecided: 2, keep: 0, discard: 0 },
  }
}

function stand(
  items: AusschussOut['items'],
  { total, openCount }: { total?: number; openCount?: number } = {},
): AusschussOut {
  return {
    items,
    total: total ?? items.length,
    open_count:
      openCount ??
      items.filter((eintrag) => eintrag.kind === 'photo' && eintrag.decision === null).length,
  }
}

function group(ids: number[], decisions: DuplicateDecision[] = []): DuplicateGroupOut {
  return {
    items: ids.map((id, index) => ({
      photo: photo(id),
      effective_decision: decisions[index] ?? 'keep',
      keep_possible: true,
      sharpness: null,
      exposure: null,
    })),
    position: 1,
    total: 1,
    previous_photo_id: null,
    next_photo_id: null,
    span_seconds: 0,
  }
}

function project(overrides: Partial<ProjectOut> = {}): ProjectOut {
  return {
    id: 1,
    name: 'Costa Rica',
    opencloud_drive_id: 'drive-1',
    opencloud_path: 'CostaRica',
    created_at: '2026-07-20T10:00:00Z',
    last_scan: null,
    last_scoring_run: null,
    last_criterion_scoring_run: null,
    category_selection_enabled: true,
    cloud_vision_detection_enabled: false,
    cloud_vision_consent_at: null,
    selection_target: null,
    effective_selection_target: 1,
    has_selection_proposal: false,
    photo_count: 0,
    taken_at_earliest: null,
    taken_at_latest: null,
    ...overrides,
  }
}

function scoringRun(overrides: Partial<ScoringRunSummary> = {}): ScoringRunSummary {
  return {
    id: 1,
    status: 'running',
    started_at: '2026-07-20T10:00:00Z',
    finished_at: null,
    photos_total: 0,
    photos_processed: 0,
    suggestions_found: 0,
    error_message: null,
    gate_confirmed_at: null,
    ...overrides,
  }
}

const ERFOLGREICHER_LAUF = scoringRun({
  status: 'success',
  finished_at: '2026-07-20T10:05:00Z',
  photos_total: 10,
  photos_processed: 10,
  suggestions_found: 3,
})

function OutletHost({ project: contextProject, refetchProject }: PipelineOutletContext) {
  return (
    <Outlet context={{ project: contextProject, refetchProject } satisfies PipelineOutletContext} />
  )
}

/** Die tatsaechlich besuchte Adresse samt Abfrage: Die Detailansicht ist derselbe Schritt mit
 * gesetztem `photo`-Parameter, und genau das muss pruefbar sein. */
function Adressspiegel() {
  const ort = useLocation()
  const zurueck = useNavigate()
  return (
    <>
      <span data-testid="adresse">{`${ort.pathname}${ort.search}`}</span>
      <span data-testid="zustand">{JSON.stringify(ort.state ?? null)}</span>
      <button type="button" onClick={() => void zurueck(-1)}>
        Sonde zurück
      </button>
      <button type="button" onClick={() => void zurueck('/woanders')}>
        Sonde weg
      </button>
    </>
  )
}

function renderPage(
  initialProject: ProjectOut,
  initialEntry = '/x',
  refetchProject: PipelineOutletContext['refetchProject'] = vi
    .fn()
    .mockResolvedValue({ data: undefined }),
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return {
    ...render(
      <MemoryRouter initialEntries={[initialEntry]}>
        <Adressspiegel />
        <Routes>
          <Route element={<OutletHost project={initialProject} refetchProject={refetchProject} />}>
            <Route path="/x" element={<AusschussStepPage />} />
            <Route path="/projects/1/pipeline/ausschuss" element={<AusschussStepPage />} />
          </Route>
          <Route path="/projects/1/pipeline/kriterien" element={<p>Klassifizierungsseite</p>} />
          <Route path="/woanders" element={<p>Woanders</p>} />
        </Routes>
      </MemoryRouter>,
      { wrapper },
    ),
    refetchProject,
  }
}

/** Der Pfad ohne Abfrage. */
function pfad(): string {
  return screen.getByTestId('adresse').textContent?.split('?')[0] ?? ''
}

function leiste(): HTMLElement {
  return screen.getByRole('group', { name: 'Nächste Aktion' })
}

/** Die Adresse ohne den umgebenden Pfad - nur die Abfrage ist hier von Belang. */
function abfrage(): string {
  return screen.getByTestId('adresse').textContent?.split('?')[1] ?? ''
}

beforeEach(() => {
  vi.mocked(projectsApi.triggerScore).mockReset()
  vi.mocked(projectsApi.confirmAusschussGate).mockReset()
  vi.mocked(projectsApi.confirmAusschussGate).mockResolvedValue({ status: 'confirmed' })
  vi.mocked(duplicatesApi.getDuplicateGroup).mockReset()
  vi.mocked(duplicatesApi.setDuplicateDecision).mockReset()
  vi.mocked(ausschussApi.listAusschuss).mockReset()
  vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([]))
})

describe('AusschussStepPage - Erkennung', () => {
  it('shows a short explanation line that says nothing is sorted out yet', () => {
    renderPage(project({ last_scoring_run: null }))

    expect(screen.getByText(/erkennt automatisch unscharfe/i)).toBeInTheDocument()
    expect(screen.getByText(AUSSCHUSS_NOTHING_SORTED_TEXT)).toBeInTheDocument()
  })

  it('zeigt vor dem ersten Lauf den Startknopf als Hauptaktion in der Leiste, ohne "Erneut …"', () => {
    renderPage(project({ last_scoring_run: null }))

    const start = within(leiste()).getByRole('button', { name: START })
    expect(start).toBeEnabled()
    expect(start).toHaveClass('bg-accent')
    expect(within(leiste()).getByText(/noch nicht vorgeschlagen/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^erneut/i })).not.toBeInTheDocument()
  })

  it(
    'keeps the button reachable even when scan has never run (Regressionsschutz: bewusst ' +
      'ungegatet, Akzeptanzkriterium 3)',
    () => {
      renderPage(project({ last_scan: null, last_scoring_run: null }))

      expect(screen.getByRole('button', { name: START })).toBeEnabled()
    },
  )

  it('zeigt nach dem Klick sofort die Verlaufsform und sendet bei Doppelklick genau eine Anfrage', async () => {
    vi.mocked(projectsApi.triggerScore).mockReturnValue(new Promise(() => {}))
    const user = userEvent.setup()
    renderPage(project({ last_scoring_run: null }))

    const button = screen.getByRole('button', { name: START })
    await user.click(button)
    await user.click(button)

    expect(button).toBeDisabled()
    expect(button).toHaveAccessibleName(RUN_STEP_TEXTS.ausschuss.running)
    expect(projectsApi.triggerScore).toHaveBeenCalledTimes(1)
  })

  it('re-enables the button and shows an error when the trigger request itself fails', async () => {
    vi.mocked(projectsApi.triggerScore).mockRejectedValue(new ApiError(500, 'Serverfehler'))
    const user = userEvent.setup()
    renderPage(project({ last_scoring_run: null }))

    await user.click(screen.getByRole('button', { name: START }))

    await waitFor(() => expect(screen.getByRole('button', { name: START })).toBeEnabled())
    expect(await screen.findByRole('alert')).toHaveTextContent('Serverfehler')
  })

  it('zeigt den Fortschritt "X von Y" mit nativem Balken in der Leiste', () => {
    renderPage(project({ last_scoring_run: scoringRun({ photos_total: 10, photos_processed: 4 }) }))

    expect(within(leiste()).getByText(/4 von 10 fotos verarbeitet/i)).toBeInTheDocument()
    const progress = leiste().querySelector('progress') as HTMLProgressElement
    expect(progress.max).toBe(10)
    expect(progress.value).toBe(4)
    expect(
      within(leiste()).getByRole('button', { name: RUN_STEP_TEXTS.ausschuss.running }),
    ).toBeDisabled()
  })

  it(
    'shows an indeterminate progress bar instead of an invalid max=0 during the brief ' +
      'photos_total=0 window right after the trigger',
    () => {
      renderPage(
        project({ last_scoring_run: scoringRun({ photos_total: 0, photos_processed: 0 }) }),
      )

      const progress = leiste().querySelector('progress') as HTMLProgressElement
      expect(progress.hasAttribute('value')).toBe(false)
      expect(progress.hasAttribute('max')).toBe(false)
    },
  )

  it('shows a summary with the plural suggestion count once scoring succeeded', () => {
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }))

    expect(screen.getByText('3 Vorschläge gefunden')).toBeInTheDocument()
  })

  it('shows a singular suggestion count when exactly one suggestion was found', () => {
    renderPage(project({ last_scoring_run: { ...ERFOLGREICHER_LAUF, suggestions_found: 1 } }))

    expect(screen.getByText('1 Vorschlag gefunden')).toBeInTheDocument()
  })

  it('bietet bei einem Fehlschlag genau eine Wiederholung: den Startknopf der Leiste', async () => {
    vi.mocked(projectsApi.triggerScore).mockResolvedValue({ status: 'queued' })
    const user = userEvent.setup()
    renderPage(
      project({
        last_scoring_run: scoringRun({ status: 'failed', error_message: 'Unerwarteter Fehler' }),
      }),
    )

    expect(await screen.findByRole('alert')).toHaveTextContent('Unerwarteter Fehler')
    expect(screen.queryByRole('button', { name: /erneut versuchen/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^erneut/i })).not.toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: START })).toHaveLength(1)

    await user.click(within(leiste()).getByRole('button', { name: START }))

    expect(projectsApi.triggerScore).toHaveBeenCalledWith(1)
  })

  it('zeigt nach einem erfolgreichen Lauf "Erneut erkennen" nachrangig samt Erklärsatz', async () => {
    vi.mocked(projectsApi.triggerScore).mockResolvedValue({ status: 'queued' })
    const user = userEvent.setup()
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }))

    const block = screen.getByTestId('rerun-block')
    expect(within(block).getByText(RERUN.explanation)).toBeVisible()
    const rerun = within(block).getByRole('button', { name: RERUN.label })
    expect(rerun).not.toHaveClass('bg-accent')
    expect(leiste()).not.toContainElement(rerun)

    await user.click(rerun)

    expect(projectsApi.triggerScore).toHaveBeenCalledWith(1)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('zeigt nach dem Auslösen sofort den laufenden Statuspunkt und ein Ladezeichen am Erneut-Knopf', async () => {
    vi.mocked(projectsApi.triggerScore).mockReturnValue(new Promise(() => {}))
    const user = userEvent.setup()
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }))

    const rerun = screen.getByRole('button', { name: RERUN.label })
    await user.click(rerun)

    const dot = leiste().querySelector('[aria-live] > span[aria-hidden="true"]')
    expect(dot).toHaveClass('bg-status-running')
    expect(dot).not.toHaveClass('bg-status-success')
    expect(rerun).toBeDisabled()
    expect(within(rerun).getByTestId('button-spinner')).toBeInTheDocument()
  })

  it('liest den Bestand nicht, solange kein Lauf erfolgreich war', () => {
    // Ohne erfolgreichen Lauf gibt es keine Vorschlaege und damit keinen Bestand - eine Anfrage
    // waere eine Anfrage je Schrittaufruf ohne moegliche Antwort.
    renderPage(project({ last_scoring_run: null }))

    expect(ausschussApi.listAusschuss).not.toHaveBeenCalled()
  })

  it('fuehrt nach der Erkennung unmittelbar in die Uebersicht - ohne Umweg ueber die Fotoliste', async () => {
    // AK2/AK3: Der Schritt stoesst das Aussortieren an UND zeigt danach den Bestand. Die beiden
    // Einstiege in die Fotoliste bzw. in den Durchgang entfallen mit der Zusammenlegung.
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([entry(42)]))
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }))

    expect(await screen.findByRole('button', { name: /serie-42\.jpg öffnen/i })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /aussortierung ansehen/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /durchgehen/i })).not.toBeInTheDocument()
  })
})

describe('AusschussStepPage - Uebersicht', () => {
  it('zeigt Platzhalter mit role=status, solange der Bestand laedt', () => {
    vi.mocked(ausschussApi.listAusschuss).mockReturnValue(new Promise(() => {}))
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }))

    expect(screen.getByRole('status', { name: /ausschnitt wird geladen/i })).toBeInTheDocument()
  })

  it('zeigt bei einem Fehler der Uebersicht einen Alert mit "Erneut versuchen"', async () => {
    vi.mocked(ausschussApi.listAusschuss).mockRejectedValue(new ApiError(500, 'Serverfehler'))
    const user = userEvent.setup()
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Serverfehler')
    vi.mocked(ausschussApi.listAusschuss).mockClear()
    await user.click(screen.getByRole('button', { name: /erneut versuchen/i }))

    expect(ausschussApi.listAusschuss).toHaveBeenCalled()
  })

  it('zeigt bei leerem Bestand eine dauerhaft sichtbare, erklaerende Zeile', async () => {
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([]))
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }))

    expect(await screen.findByText(AUSSCHUSS_EMPTY_TEXT)).toBeInTheDocument()
  })

  it('nennt den Grund je Kachel mit Zeichen UND Wort, unterscheidbar nach Art', async () => {
    // AK4: Duplikat gegen geringe Qualitaet - kein Sammelzustand. Die Farbe traegt die Aussage
    // nie allein, das Wort steht daneben.
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([stapel(40, 41), entry(43)]))
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }))

    expect(await screen.findByText('Duplikat')).toBeInTheDocument()
    expect(screen.getByText('Geringe Bildqualität')).toBeInTheDocument()
  })

  it('mischt Einzelkacheln und Stapel im selben Raster', async () => {
    // B3/B4: Eine Einzelaufnahme oeffnet die Detailansicht, ein Stapel die Vergleichsansicht am
    // Anker - fuer ein Gruppenmitglied gibt es in der Uebersicht keinen "oeffnen"-Knopf.
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([stapel(40, 41), entry(43)]))
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }))

    expect(await screen.findByRole('button', { name: /serie-43\.jpg öffnen/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /serie-41\.jpg öffnen/i })).not.toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: /^Duplikat-Gruppe mit 3 Aufnahmen vergleichen/ }),
    ).toHaveAttribute('href', '/projects/1/photos/40/duplicates?from=ausschuss')
  })

  it('trennt die Entscheidungszeile vom Grund: vorgeschlagen, Ausschuss, behalten', async () => {
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(
      stand([
        entry(42, { decision: null }),
        entry(43, { decision: 'discard' }),
        entry(44, { decision: 'keep' }),
      ]),
    )
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }))

    // Die Entscheidungszeile steht NEBEN dem Grund, nicht statt seiner: Der Grund sagt, warum die
    // Aufnahme markiert ist, die Zeile sagt, was mit ihr geschehen ist.
    const zeilen = await screen.findAllByTestId('ausschuss-decision')
    expect(zeilen.map((zeile) => zeile.textContent)).toEqual([
      'Vorgeschlagen',
      'Ausschuss',
      'Behalten',
    ])
  })

  it('beschriftet die Abschluss-Aktion mit der Zahl der offenen Vorschläge', async () => {
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(
      stand([entry(42), entry(43, { decision: 'keep' })], { openCount: 40 }),
    )
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }))

    const button = await within(leiste()).findByRole('button', {
      name: '40 Vorschläge als Ausschuss übernehmen und abschließen',
    })
    expect(button).toBeEnabled()
    expect(button).toHaveClass('bg-accent')
    expect(within(leiste()).getByText('40 Vorschläge offen')).toBeInTheDocument()
  })

  it('nennt die Anzahl erst, wenn der Bestand geladen ist', async () => {
    const { promise, resolve } = zurueckgehalten<AusschussOut>()
    vi.mocked(ausschussApi.listAusschuss).mockReturnValue(promise)
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }))

    expect(within(leiste()).getByRole('button', { name: AUSSCHUSS_CONFIRM_LABEL })).toBeEnabled()

    await act(async () => resolve(stand([entry(42)], { openCount: 1 })))

    expect(
      await within(leiste()).findByRole('button', {
        name: '1 Vorschlag als Ausschuss übernehmen und abschließen',
      }),
    ).toBeInTheDocument()
  })

  it('bestaetigt den Abschluss in einem Aufruf, ohne Id-Liste im Body', async () => {
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([entry(42)], { openCount: 1 }))
    const user = userEvent.setup()
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }))

    await user.click(await screen.findByRole('button', { name: /^1 Vorschlag als Ausschuss/ }))

    expect(projectsApi.confirmAusschussGate).toHaveBeenCalledWith(1)
  })

  it('zeigt einen Alert über der Leiste, wenn der Abschluss scheitert, und bleibt auf der Seite', async () => {
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([entry(42)], { openCount: 1 }))
    vi.mocked(projectsApi.confirmAusschussGate).mockRejectedValue(
      new ApiError(409, 'Der Ausschuss wurde zwischenzeitlich geändert.'),
    )
    const user = userEvent.setup()
    const { refetchProject } = renderPage(
      project({ last_scoring_run: ERFOLGREICHER_LAUF }),
      '/projects/1/pipeline/ausschuss',
    )

    const button = await screen.findByRole('button', { name: /^1 Vorschlag als Ausschuss/ })
    await user.click(button)

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Der Ausschuss wurde zwischenzeitlich geändert.')
    expect(alert.nextElementSibling).toBe(leiste())
    expect(pfad()).toBe('/projects/1/pipeline/ausschuss')
    expect(refetchProject).not.toHaveBeenCalled()
    expect(button).toHaveFocus()
  })

  it('bietet den Abschluss an, wenn alle Vorschlaege einzeln entschieden sind, aber nicht bestaetigt', async () => {
    // DIE SACKGASSE, DIE ES NICHT GEBEN DARF: Ein erfolgreicher Lauf meldet Vorschlaege, der
    // Nutzer entscheidet sie ALLE einzeln, danach ist `open_count` 0 und `gate_confirmed_at`
    // weiterhin null. Allein `gate_confirmed_at` gibt den naechsten Schritt frei.
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(
      stand([entry(42, { decision: 'keep' }), entry(43, { decision: 'discard' })], {
        openCount: 0,
      }),
    )
    const user = userEvent.setup()
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }))

    await within(leiste()).findByText('Alle Vorschläge entschieden')
    const button = within(leiste()).getByRole('button', { name: AUSSCHUSS_CONFIRM_LABEL })
    expect(button).toBeEnabled()

    await user.click(button)

    expect(projectsApi.confirmAusschussGate).toHaveBeenCalledWith(1)
  })

  it('führt nach bestätigtem Abschluss ohne offene Vorschläge per Link weiter, ohne Schreibanfrage', async () => {
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(
      stand([entry(42, { decision: 'keep' })], { openCount: 0 }),
    )
    const user = userEvent.setup()
    renderPage(
      project({ last_scoring_run: { ...ERFOLGREICHER_LAUF, gate_confirmed_at: BESTAETIGT } }),
      '/projects/1/pipeline/ausschuss',
    )

    const link = await within(leiste()).findByRole('link', { name: 'Weiter zur Klassifizierung' })
    expect(link).toHaveAttribute('href', '/projects/1/pipeline/kriterien')
    expect(within(leiste()).queryByRole('button')).not.toBeInTheDocument()
    expect(screen.getByText(/bestätigt am/i)).toBeInTheDocument()

    await user.click(link)

    expect(pfad()).toBe('/projects/1/pipeline/kriterien')
    expect(projectsApi.confirmAusschussGate).not.toHaveBeenCalled()
    expect(projectsApi.triggerScore).not.toHaveBeenCalled()
  })

  it('bleibt nach der Bestaetigung aufrufbar: Zeitstempel und "Erneut erkennen"', async () => {
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([entry(42)], { openCount: 0 }))
    renderPage(
      project({ last_scoring_run: { ...ERFOLGREICHER_LAUF, gate_confirmed_at: BESTAETIGT } }),
    )

    expect(await screen.findByText(/bestätigt am/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: RERUN.label })).toBeEnabled()
  })

  it('laesst offene Vorschlaege auch nach der Bestaetigung erneut abschliessen', async () => {
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([entry(42)], { openCount: 1 }))
    renderPage(
      project({ last_scoring_run: { ...ERFOLGREICHER_LAUF, gate_confirmed_at: BESTAETIGT } }),
    )

    expect(
      await within(leiste()).findByRole('button', { name: /^1 Vorschlag als Ausschuss/ }),
    ).toBeEnabled()
  })

  it('behält bei null Vorschlägen mit Auto-Abschluss den Leertext und führt weiter', async () => {
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([]))
    renderPage(
      project({
        last_scoring_run: {
          ...ERFOLGREICHER_LAUF,
          suggestions_found: 0,
          gate_confirmed_at: BESTAETIGT,
        },
      }),
    )

    expect(await screen.findByText(AUSSCHUSS_EMPTY_TEXT)).toBeInTheDocument()
    expect(
      await within(leiste()).findByRole('link', { name: 'Weiter zur Klassifizierung' }),
    ).toBeInTheDocument()
  })

  it('nennt bei abgeschalteter Klassifizierung einen neutralen Text ohne Weiter-Link', async () => {
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([]))
    renderPage(
      project({
        category_selection_enabled: false,
        last_scoring_run: { ...ERFOLGREICHER_LAUF, gate_confirmed_at: BESTAETIGT },
      }),
    )

    expect(await within(leiste()).findByText(NEXT_UNAVAILABLE_TEXT)).toBeInTheDocument()
    expect(within(leiste()).queryByRole('link')).not.toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('laedt bei mehr Bestand als einer Seite nach', async () => {
    const viele = Array.from({ length: 60 }, (_, index) => entry(100 + index))
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValueOnce(stand(viele, { total: 61 }))
    const user = userEvent.setup()
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }))

    await screen.findByText('60 von 61 Einträgen geladen')
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValueOnce(stand([entry(200)], { total: 61 }))
    await user.click(screen.getByRole('button', { name: /mehr laden/i }))

    await waitFor(() =>
      expect(ausschussApi.listAusschuss).toHaveBeenLastCalledWith(1, {
        limit: 60,
        offset: 60,
      }),
    )
  })
})

describe('AusschussStepPage - Detailansicht', () => {
  it('oeffnet das Grossbild ueber einen Klick auf die Kachel, ohne die Seite zu wechseln', async () => {
    // AK5: Ein Klick auf ein Bild oeffnet die Detailansicht mit dem Bild in gross - als dieselbe
    // Schritt-Route mit gesetztem `photo`-Parameter, nicht als eigene Seite und nicht als Dialog.
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([entry(42)]))
    const user = userEvent.setup()
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }))

    await user.click(await screen.findByRole('button', { name: /serie-42\.jpg öffnen/i }))

    expect(abfrage()).toBe('photo=42')
    expect(await screen.findByRole('img', { name: 'Reise/serie-42.jpg' })).toBeInTheDocument()
  })

  it('liest den Eintrag ueber den photo_id-Filter, nicht aus der geladenen Seite', async () => {
    // Der Deep-Link auf eine Aufnahme ausserhalb der geladenen Seite ist ein regulaerer Zustand
    // mit definierter Antwort - der Filterzweig des Endpunkts.
    vi.mocked(ausschussApi.listAusschuss).mockImplementation((_projectId, params) =>
      Promise.resolve(
        params?.photoId === undefined ? stand([entry(42)], { total: 200 }) : stand([entry(77)]),
      ),
    )
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }), '/x?photo=77')

    expect(await screen.findByRole('img', { name: 'Reise/serie-77.jpg' })).toBeInTheDocument()
    expect(ausschussApi.listAusschuss).toHaveBeenCalledWith(1, {
      limit: 60,
      offset: 0,
      photoId: 77,
    })
  })

  it('schliesst die Detailansicht ueber die Schaltflaeche und behaelt die Uebersicht', async () => {
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([entry(42)]))
    const user = userEvent.setup()
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }), '/x?photo=42')

    await user.click(await screen.findByRole('button', { name: /detailansicht schließen/i }))

    expect(abfrage()).toBe('')
    expect(await screen.findByRole('button', { name: /serie-42\.jpg öffnen/i })).toBeInTheDocument()
  })

  it('schliesst die Detailansicht auch mit Escape', async () => {
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([entry(42)]))
    const user = userEvent.setup()
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }), '/x?photo=42')
    await screen.findByRole('img', { name: 'Reise/serie-42.jpg' })

    await user.keyboard('{Escape}')

    expect(abfrage()).toBe('')
  })

  it('traegt die Entscheidung ueber die Aufnahme ein und bietet "Behalten" nur beim Duplikat', async () => {
    // AK6: Zustimmen und Aufheben wirken unmittelbar. "Aufheben" (`keep`) gibt es nur, wo es
    // wirksam ist - bei geringer Bildqualitaet ohne Gruppe erscheint es nicht (Auflage S4 der
    // Spec 0486: der Server weist den Wert trotzdem nicht ab, die Anzeige bietet ihn nur nicht an).
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(
      stand([entry(42, { reason: 'low_quality', groupAnchorPhotoId: null })]),
    )
    vi.mocked(duplicatesApi.setDuplicateDecision).mockResolvedValue(group([42]))
    const user = userEvent.setup()
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }), '/x?photo=42')

    await screen.findByRole('img', { name: 'Reise/serie-42.jpg' })
    expect(
      screen.queryByRole('button', { name: /^Behalten \(Detailansicht\):/i }),
    ).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /^Ausschuss \(Detailansicht\):/ }))

    expect(duplicatesApi.setDuplicateDecision).toHaveBeenCalledWith(1, 42, 'discard')
  })

  it('bietet "Behalten" nach dem Serverwert an, nicht nach dem Grund', async () => {
    // D1: `keep_possible` kommt vom Server (`duplicates.py::keep_possible_for`) und ist nicht aus
    // `reason` ableitbar. Beides faellt auseinander, wenn eine Entscheidungszeile einen Lauf
    // ueberlebt, in dem `suggested_status` UND `duplicate_of` zurueckgesetzt wurden (worker.py):
    // Der Grund ist dann `low_quality`, "behalten" wirkt aber. Eine TypeScript-Ableitung aus dem
    // Grund naehme dem Nutzer dort die EINZIGE Handlung, die die Aufnahme zurueckholt.
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(
      stand([
        entry(42, {
          reason: 'low_quality',
          decision: 'discard',
          groupAnchorPhotoId: null,
          keepPossible: true,
        }),
      ]),
    )
    vi.mocked(duplicatesApi.setDuplicateDecision).mockResolvedValue(group([42]))
    const user = userEvent.setup()
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }), '/x?photo=42')

    await screen.findByRole('img', { name: 'Reise/serie-42.jpg' })
    const behalten = screen.getByRole('button', { name: /^Behalten \(Detailansicht\):/i })

    await user.click(behalten)

    expect(duplicatesApi.setDuplicateDecision).toHaveBeenCalledWith(1, 42, 'keep')
  })

  it.each([
    ['Duplikat', 'duplicate' as const],
    ['Gewinner mit Schaerfe-Ablehnung', 'low_quality' as const],
  ])(
    'verweist beim Gruppenmitglied (%s) in die Vergleichsansicht, statt die Gruppe zu laden',
    async (_fall, reason) => {
      // A10: Die eingebettete Gruppe entfaellt. Der Link haengt am Anker, nicht am Grund.
      vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(
        stand([entry(42, { reason, groupAnchorPhotoId: 41 })]),
      )
      renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }), '/x?photo=42')

      const link = await screen.findByRole('link', { name: 'Duplikat-Gruppe vergleichen' })
      expect(link).toHaveAttribute('href', '/projects/1/photos/41/duplicates?from=ausschuss')
      expect(duplicatesApi.getDuplicateGroup).not.toHaveBeenCalled()
      expect(screen.queryByTestId('duplicate-image')).not.toBeInTheDocument()
    },
  )

  it('bietet ohne Anker keinen Weg in die Vergleichsansicht', async () => {
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([entry(42)]))
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }), '/x?photo=42')

    await screen.findByRole('img', { name: 'Reise/serie-42.jpg' })
    expect(
      screen.queryByRole('link', { name: 'Duplikat-Gruppe vergleichen' }),
    ).not.toBeInTheDocument()
  })

  it('zeigt einen benannten Zustand mit Rueckweg, wenn die Aufnahme nicht mehr im Bestand ist', async () => {
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([]))
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }), '/x?photo=42')

    expect(await screen.findByText(AUSSCHUSS_MISSING_ENTRY_TEXT)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /zurück zur übersicht/i })).toBeInTheDocument()
  })

  it('behandelt einen photo-Parameter ohne Zahl als regulaeren Zustand: die Uebersicht', async () => {
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([entry(42)]))
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }), '/x?photo=abc')

    expect(await screen.findByRole('button', { name: /serie-42\.jpg öffnen/i })).toBeInTheDocument()
    expect(ausschussApi.listAusschuss).toHaveBeenCalledWith(1, { limit: 60, offset: 0 })
  })

  it('zeigt die Detailansicht nur nach einem erfolgreichen Erkennungslauf', () => {
    renderPage(project({ last_scoring_run: null }), '/x?photo=42')

    expect(ausschussApi.listAusschuss).not.toHaveBeenCalled()
    expect(screen.queryByRole('img', { name: 'Reise/serie-42.jpg' })).not.toBeInTheDocument()
  })

  it('zeigt die Leiste mit der Abschluss-Aktion auch in der Detailansicht', async () => {
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([entry(42)], { openCount: 1 }))
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }), '/x?photo=42')

    await screen.findByRole('img', { name: 'Reise/serie-42.jpg' })
    expect(
      await within(leiste()).findByRole('button', { name: /^1 Vorschlag als Ausschuss/ }),
    ).toBeEnabled()
  })
})

/** Ein Projekt nach erfolgreicher Bestätigung, wie es der Refetch liefert. */
function bestaetigt(overrides: Partial<ProjectOut> = {}): ProjectOut {
  return project({
    last_scoring_run: { ...ERFOLGREICHER_LAUF, gate_confirmed_at: BESTAETIGT },
    ...overrides,
  })
}

describe('AusschussStepPage - Abschluss und Weiterführung', () => {
  it('sperrt die Abschluss-Aktion waehrend der Anfrage und sendet genau einen Aufruf', async () => {
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([entry(42)], { openCount: 1 }))
    vi.mocked(projectsApi.confirmAusschussGate).mockReturnValue(new Promise(() => {}))
    const user = userEvent.setup()
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }))

    const button = await screen.findByRole('button', { name: /^1 Vorschlag als Ausschuss/ })
    await user.click(button)

    expect(button).toBeDisabled()
    expect(projectsApi.confirmAusschussGate).toHaveBeenCalledTimes(1)
  })

  it('lädt das Projekt neu und wechselt erst danach per Push zur Klassifizierung', async () => {
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([entry(42)], { openCount: 1 }))
    const reihenfolge: string[] = []
    vi.mocked(projectsApi.confirmAusschussGate).mockImplementation(() => {
      reihenfolge.push('confirm')
      return Promise.resolve({ status: 'confirmed' })
    })
    const refetchProject = vi.fn(() => {
      reihenfolge.push(`refetch:${pfad()}`)
      return Promise.resolve({ data: bestaetigt() })
    }) as unknown as PipelineOutletContext['refetchProject']
    const user = userEvent.setup()
    renderPage(
      project({ last_scoring_run: ERFOLGREICHER_LAUF }),
      '/projects/1/pipeline/ausschuss',
      refetchProject,
    )

    await user.click(await screen.findByRole('button', { name: /^1 Vorschlag als Ausschuss/ }))

    await screen.findByText('Klassifizierungsseite')
    expect(reihenfolge).toEqual(['confirm', 'refetch:/projects/1/pipeline/ausschuss'])
    expect(pfad()).toBe('/projects/1/pipeline/kriterien')
    expect(screen.getByTestId('zustand')).toHaveTextContent('{"focusHeading":true}')

    await user.click(screen.getByRole('button', { name: 'Sonde zurück' }))

    expect(pfad()).toBe('/projects/1/pipeline/ausschuss')
  })

  it('führt aus der Detailansicht mit Browser-Zurück in dieselbe Detailansicht', async () => {
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([entry(42)], { openCount: 1 }))
    const refetchProject = vi.fn().mockResolvedValue({ data: bestaetigt() })
    const user = userEvent.setup()
    renderPage(
      project({ last_scoring_run: ERFOLGREICHER_LAUF }),
      '/projects/1/pipeline/ausschuss?photo=42',
      refetchProject,
    )

    await user.click(
      await within(leiste()).findByRole('button', { name: /^1 Vorschlag als Ausschuss/ }),
    )
    await screen.findByText('Klassifizierungsseite')
    await user.click(screen.getByRole('button', { name: 'Sonde zurück' }))

    expect(screen.getByTestId('adresse')).toHaveTextContent(
      '/projects/1/pipeline/ausschuss?photo=42',
    )
  })

  it('wechselt nicht, wenn der Refetch die Klassifizierung noch nicht freigibt', async () => {
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([entry(42)], { openCount: 1 }))
    const refetchProject = vi
      .fn()
      .mockResolvedValue({ data: project({ last_scoring_run: ERFOLGREICHER_LAUF }) })
    const user = userEvent.setup()
    renderPage(
      project({ last_scoring_run: ERFOLGREICHER_LAUF }),
      '/projects/1/pipeline/ausschuss',
      refetchProject,
    )

    await user.click(await screen.findByRole('button', { name: /^1 Vorschlag als Ausschuss/ }))

    await waitFor(() => expect(refetchProject).toHaveBeenCalled())
    expect(pfad()).toBe('/projects/1/pipeline/ausschuss')
  })

  it('wechselt nicht und stürzt nicht ab, wenn der Refetch scheitert', async () => {
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([entry(42)], { openCount: 1 }))
    const refetchProject = vi.fn().mockResolvedValue({ data: undefined, isError: true })
    const user = userEvent.setup()
    renderPage(
      project({ last_scoring_run: ERFOLGREICHER_LAUF }),
      '/projects/1/pipeline/ausschuss',
      refetchProject,
    )

    await user.click(await screen.findByRole('button', { name: /^1 Vorschlag als Ausschuss/ }))

    await waitFor(() => expect(refetchProject).toHaveBeenCalled())
    expect(pfad()).toBe('/projects/1/pipeline/ausschuss')
    expect(leiste()).toBeInTheDocument()
  })

  it('wechselt nicht, wenn die Klassifizierung abgeschaltet ist', async () => {
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([entry(42)], { openCount: 1 }))
    const refetchProject = vi
      .fn()
      .mockResolvedValue({ data: bestaetigt({ category_selection_enabled: false }) })
    const user = userEvent.setup()
    renderPage(
      project({ category_selection_enabled: false, last_scoring_run: ERFOLGREICHER_LAUF }),
      '/projects/1/pipeline/ausschuss',
      refetchProject,
    )

    await user.click(await screen.findByRole('button', { name: /^1 Vorschlag als Ausschuss/ }))

    await waitFor(() => expect(refetchProject).toHaveBeenCalled())
    expect(pfad()).toBe('/projects/1/pipeline/ausschuss')
  })

  it('wechselt nicht, wenn die Seite vor der Antwort verlassen wurde', async () => {
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([entry(42)], { openCount: 1 }))
    const antwort = zurueckgehalten<{ status: 'confirmed' }>()
    vi.mocked(projectsApi.confirmAusschussGate).mockReturnValue(antwort.promise)
    const refetchProject = vi.fn().mockResolvedValue({ data: bestaetigt() })
    const user = userEvent.setup()
    renderPage(
      project({ last_scoring_run: ERFOLGREICHER_LAUF }),
      '/projects/1/pipeline/ausschuss',
      refetchProject,
    )

    await user.click(await screen.findByRole('button', { name: /^1 Vorschlag als Ausschuss/ }))
    await user.click(screen.getByRole('button', { name: 'Sonde weg' }))
    await act(async () => antwort.resolve({ status: 'confirmed' }))

    expect(pfad()).toBe('/woanders')
    expect(refetchProject).not.toHaveBeenCalled()
  })

  it('wechselt nach einem erfolgreichen Hintergrundlauf nicht, sondern zeigt den Weiter-Link', async () => {
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([]))
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const refetchProject = vi.fn().mockResolvedValue({ data: undefined })
    function Host({ value }: { value: ProjectOut }) {
      return (
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={['/projects/1/pipeline/ausschuss']}>
            <Adressspiegel />
            <Routes>
              <Route element={<OutletHost project={value} refetchProject={refetchProject} />}>
                <Route path="/projects/1/pipeline/ausschuss" element={<AusschussStepPage />} />
              </Route>
            </Routes>
          </MemoryRouter>
        </QueryClientProvider>
      )
    }
    const { rerender } = render(<Host value={project({ last_scoring_run: scoringRun() })} />)
    expect(
      within(leiste()).getByRole('button', { name: RUN_STEP_TEXTS.ausschuss.running }),
    ).toBeDisabled()

    rerender(
      <Host
        value={bestaetigt({
          last_scoring_run: {
            ...ERFOLGREICHER_LAUF,
            suggestions_found: 0,
            gate_confirmed_at: BESTAETIGT,
          },
        })}
      />,
    )

    expect(
      await within(leiste()).findByRole('link', { name: 'Weiter zur Klassifizierung' }),
    ).toBeInTheDocument()
    expect(pfad()).toBe('/projects/1/pipeline/ausschuss')
  })

  it('lädt den Bestand nach dem Abschluss neu', async () => {
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([entry(42)], { openCount: 1 }))
    const user = userEvent.setup()
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }))

    await user.click(await screen.findByRole('button', { name: /^1 Vorschlag als Ausschuss/ }))
    await waitFor(() => expect(projectsApi.confirmAusschussGate).toHaveBeenCalledWith(1))

    await waitFor(() =>
      expect(vi.mocked(ausschussApi.listAusschuss).mock.calls.length).toBeGreaterThan(1),
    )
    expect(abfrage()).toBe('')
  })
})
