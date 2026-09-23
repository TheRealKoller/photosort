import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Outlet, Route, Routes, useLocation } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as ausschussApi from '../../api/ausschuss'
import { ApiError } from '../../api/client'
import * as duplicatesApi from '../../api/duplicates'
import * as projectsApi from '../../api/projects'
import type {
  AusschussOut,
  DuplicateDecision,
  DuplicateGroupOut,
  PhotoOut,
  ProjectOut,
  ScoringRunSummary,
  SuggestionReason,
} from '../../api/types'
import {
  AUSSCHUSS_ALL_DECIDED_TEXT,
  AUSSCHUSS_EMPTY_TEXT,
  AUSSCHUSS_MISSING_ENTRY_TEXT,
  AUSSCHUSS_NOTHING_TO_CONFIRM_TEXT,
  AusschussStepPage,
} from './AusschussStepPage'
import type { PipelineOutletContext } from './ProjectPipelineLayout'

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
  }
}

function entry(
  id: number,
  {
    reason = 'duplicate',
    decision = null,
    groupAnchorPhotoId = id,
    keepPossible = reason === 'duplicate',
  }: {
    reason?: SuggestionReason
    decision?: DuplicateDecision | null
    groupAnchorPhotoId?: number | null
    keepPossible?: boolean
  } = {},
): AusschussOut['items'][number] {
  // `keepPossible` ist der SERVERWERT (`duplicates.py::keep_possible_for`). Der Vorgabewert bildet
  // nur den Regelfall ab - ein Duplikat hat eine Gruppe, eine Unscharfe-Ablehnung nicht - und darf
  // nicht als Ableitungsregel gelesen werden: Der Fall "Entscheidungszeile ohne offenen Vorschlag"
  // traegt `true` bei `reason === 'low_quality'` (siehe der Test dazu).
  return {
    photo: photo(id),
    reason,
    decision,
    group_anchor_photo_id: groupAnchorPhotoId,
    keep_possible: keepPossible,
  }
}

function stand(
  items: AusschussOut['items'],
  { total, openCount }: { total?: number; openCount?: number } = {},
): AusschussOut {
  return {
    items,
    total: total ?? items.length,
    open_count: openCount ?? items.filter((eintrag) => eintrag.decision === null).length,
  }
}

function group(ids: number[], decisions: DuplicateDecision[] = []): DuplicateGroupOut {
  return {
    items: ids.map((id, index) => ({
      photo: photo(id),
      effective_decision: decisions[index] ?? 'keep',
      keep_possible: true,
    })),
    position: 1,
    total: 1,
    previous_photo_id: null,
    next_photo_id: null,
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
  return <span data-testid="adresse">{`${ort.pathname}${ort.search}`}</span>
}

function renderPage(initialProject: ProjectOut, initialEntry = '/x', refetchProject = vi.fn()) {
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
          </Route>
        </Routes>
      </MemoryRouter>,
      { wrapper },
    ),
    refetchProject,
  }
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
  // Vorgabe: keine Gruppe. Der Endpunkt antwortet auf eine Aufnahme ohne Duplikat mit einem leeren
  // Stand - die Gruppen-Tests setzen ihre eigene Antwort.
  vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(group([]))
  vi.mocked(duplicatesApi.setDuplicateDecision).mockReset()
  vi.mocked(ausschussApi.listAusschuss).mockReset()
  vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([]))
})

describe('AusschussStepPage - Erkennung', () => {
  it('shows a short explanation line (UI/UX-Abschnitt der Spec 0042)', () => {
    renderPage(project({ last_scoring_run: null }))

    expect(screen.getByText(/erkennt automatisch unscharfe/i)).toBeInTheDocument()
  })

  it('shows an active button and a hint when never scored', () => {
    renderPage(project({ last_scoring_run: null }))

    expect(screen.getByRole('button', { name: /ausschuss aussortieren/i })).toBeEnabled()
    expect(screen.getByText(/noch nicht vorgeschlagen/i)).toBeInTheDocument()
  })

  it(
    'keeps the button reachable even when scan has never run (Regressionsschutz: bewusst ' +
      'ungegatet, Akzeptanzkriterium 3)',
    () => {
      renderPage(project({ last_scan: null, last_scoring_run: null }))

      expect(screen.getByRole('button', { name: /ausschuss aussortieren/i })).toBeEnabled()
    },
  )

  it('disables the button synchronously on click and sends exactly one request on a double click', async () => {
    vi.mocked(projectsApi.triggerScore).mockReturnValue(new Promise(() => {}))
    const user = userEvent.setup()
    renderPage(project({ last_scoring_run: null }))

    const button = screen.getByRole('button', { name: /ausschuss aussortieren/i })
    await user.click(button)
    await user.click(button)

    expect(button).toBeDisabled()
    expect(projectsApi.triggerScore).toHaveBeenCalledTimes(1)
  })

  it('re-enables the button and shows an error when the trigger request itself fails', async () => {
    vi.mocked(projectsApi.triggerScore).mockRejectedValue(new ApiError(500, 'Serverfehler'))
    const user = userEvent.setup()
    renderPage(project({ last_scoring_run: null }))

    await user.click(screen.getByRole('button', { name: /ausschuss aussortieren/i }))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /ausschuss aussortieren/i })).toBeEnabled(),
    )
    expect(await screen.findByRole('alert')).toHaveTextContent('Serverfehler')
  })

  it('shows granular "X von Y" progress with a native progress element while running', () => {
    renderPage(project({ last_scoring_run: scoringRun({ photos_total: 10, photos_processed: 4 }) }))

    expect(screen.getByText(/4 von 10 fotos verarbeitet/i)).toBeInTheDocument()
    const progress = screen.getByRole('progressbar') as HTMLProgressElement
    expect(progress.max).toBe(10)
    expect(progress.value).toBe(4)
  })

  it(
    'shows an indeterminate progress bar instead of an invalid max=0 during the brief ' +
      'photos_total=0 window right after the trigger',
    () => {
      renderPage(
        project({ last_scoring_run: scoringRun({ photos_total: 0, photos_processed: 0 }) }),
      )

      const progress = screen.getByRole('progressbar') as HTMLProgressElement
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

  it('shows an inline error banner with a retry button on a failed scoring run', async () => {
    vi.mocked(projectsApi.triggerScore).mockResolvedValue({ status: 'queued' })
    const user = userEvent.setup()
    renderPage(
      project({
        last_scoring_run: scoringRun({ status: 'failed', error_message: 'Unerwarteter Fehler' }),
      }),
    )

    expect(await screen.findByRole('alert')).toHaveTextContent('Unerwarteter Fehler')
    await user.click(screen.getByRole('button', { name: /erneut versuchen/i }))

    expect(projectsApi.triggerScore).toHaveBeenCalledWith(1)
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
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(
      stand([entry(42), entry(43, { reason: 'low_quality', groupAnchorPhotoId: null })]),
    )
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }))

    expect(await screen.findByText('Duplikat')).toBeInTheDocument()
    expect(screen.getByText('Geringe Bildqualität')).toBeInTheDocument()
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

  it('beschriftet den Bestaetigungsbutton mit der Zahl der offenen Vorschlaege', async () => {
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(
      stand([entry(42), entry(43, { decision: 'keep' })], { openCount: 40 }),
    )
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }))

    const button = await screen.findByRole('button', {
      name: /ausschuss gesichtet, weiter \(40\)/i,
    })
    expect(button).toBeEnabled()
  })

  it('bestaetigt den Abschluss in einem Aufruf, ohne Id-Liste im Body', async () => {
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([entry(42)], { openCount: 1 }))
    const user = userEvent.setup()
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }))

    await user.click(
      await screen.findByRole('button', { name: /ausschuss gesichtet, weiter \(1\)/i }),
    )

    expect(projectsApi.confirmAusschussGate).toHaveBeenCalledWith(1)
  })

  it('zeigt einen Alert, wenn der Abschluss scheitert', async () => {
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([entry(42)], { openCount: 1 }))
    vi.mocked(projectsApi.confirmAusschussGate).mockRejectedValue(
      new ApiError(409, 'Der Ausschuss wurde zwischenzeitlich geändert.'),
    )
    const user = userEvent.setup()
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }))

    await user.click(
      await screen.findByRole('button', { name: /ausschuss gesichtet, weiter \(1\)/i }),
    )

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Der Ausschuss wurde zwischenzeitlich geändert.',
    )
  })

  it('bietet den Abschluss an, wenn alle Vorschlaege einzeln entschieden sind, aber nicht bestaetigt', async () => {
    // DIE SACKGASSE, DIE ES NICHT GEBEN DARF: Ein erfolgreicher Lauf meldet Vorschlaege, der
    // Nutzer entscheidet sie ALLE einzeln (AK6 erlaubt das, AK12 verlangt es nicht), danach ist
    // `open_count` 0 und `gate_confirmed_at` weiterhin null. Ein an `open_count` gebundener
    // gesperrter Button liesse den Schritt nie abschliessen - und weil allein `gate_confirmed_at`
    // den naechsten Schritt freigibt (AK13), stuende die ganze Pipeline still.
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(
      stand([entry(42, { decision: 'keep' }), entry(43, { decision: 'discard' })], {
        openCount: 0,
      }),
    )
    const user = userEvent.setup()
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }))

    const button = await screen.findByRole('button', { name: /ausschuss gesichtet, weiter/i })
    expect(button).toBeEnabled()
    expect(screen.getByText(AUSSCHUSS_ALL_DECIDED_TEXT)).toBeInTheDocument()
    expect(screen.queryByText(AUSSCHUSS_NOTHING_TO_CONFIRM_TEXT)).not.toBeInTheDocument()

    await user.click(button)

    expect(projectsApi.confirmAusschussGate).toHaveBeenCalledWith(1)
  })

  it('sperrt den Button mit neutralem Erklaertext erst nach bestaetigtem Abschluss ohne offene Vorschlaege', async () => {
    // Der einzige Zustand, in dem es wirklich nichts zu tun gibt: Der Abschluss steht, und offen
    // ist nichts. Hier bleibt der neutrale Erklaertext richtig - vorher sagte er dasselbe ueber
    // einen Zustand, in dem sehr wohl etwas zu tun war (siehe der Test darueber).
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(
      stand([entry(42, { decision: 'keep' })], { openCount: 0 }),
    )
    renderPage(
      project({
        last_scoring_run: { ...ERFOLGREICHER_LAUF, gate_confirmed_at: '2026-07-20T11:00:00Z' },
      }),
    )

    const button = await screen.findByRole('button', { name: /ausschuss gesichtet, weiter/i })
    expect(button).toBeDisabled()
    expect(screen.getByText(AUSSCHUSS_NOTHING_TO_CONFIRM_TEXT)).toBeInTheDocument()
    expect(projectsApi.confirmAusschussGate).not.toHaveBeenCalled()
  })

  it('bleibt nach der Bestaetigung aufrufbar und nennt den Zeitstempel', async () => {
    // AK11: Nach der Bestaetigung bleibt der Schritt aufrufbar; weitere Anpassungen sind moeglich.
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([entry(42)], { openCount: 0 }))
    renderPage(
      project({
        last_scoring_run: { ...ERFOLGREICHER_LAUF, gate_confirmed_at: '2026-07-20T11:00:00Z' },
      }),
    )

    expect(await screen.findByText(/bestätigt am/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /ausschuss gesichtet, weiter/i })).toBeInTheDocument()
  })

  it('laesst offene Vorschlaege auch nach der Bestaetigung erneut abschliessen', async () => {
    // AK11, die andere Haelfte: Ein neuer Lauf nach der Bestaetigung findet neue Vorschlaege -
    // der Abschluss bleibt bedienbar und nennt weiter die Zahl der offenen.
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([entry(42)], { openCount: 1 }))
    renderPage(
      project({
        last_scoring_run: { ...ERFOLGREICHER_LAUF, gate_confirmed_at: '2026-07-20T11:00:00Z' },
      }),
    )

    expect(
      await screen.findByRole('button', { name: /ausschuss gesichtet, weiter \(1\)/i }),
    ).toBeEnabled()
  })

  it('laedt bei mehr Bestand als einer Seite nach', async () => {
    const viele = Array.from({ length: 60 }, (_, index) => entry(100 + index))
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValueOnce(stand(viele, { total: 61 }))
    const user = userEvent.setup()
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }))

    await screen.findByText(/60 von 61 geladen/i)
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

  it('zeigt beim Duplikat die ganze Gruppe ueber den Gruppenanker', async () => {
    // AK8: kein separater Seitenwechsel - die Serie steht in der Detailansicht, aufgeloest ueber
    // den Anker aus dem Eintrag (nicht ueber das angeklickte Foto).
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(
      stand([entry(42, { groupAnchorPhotoId: 41 })]),
    )
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(group([41, 42]))
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }), '/x?photo=42')

    await screen.findByRole('img', { name: 'Reise/serie-42.jpg' })

    await waitFor(() => expect(duplicatesApi.getDuplicateGroup).toHaveBeenCalledWith(1, 41))
    expect(screen.getAllByTestId('duplicate-image')).toHaveLength(2)
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
})

describe('AusschussStepPage - Abschluss', () => {
  it('sperrt den Button waehrend des laufenden Abschlusses und sendet genau einen Aufruf', async () => {
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([entry(42)], { openCount: 1 }))
    vi.mocked(projectsApi.confirmAusschussGate).mockReturnValue(new Promise(() => {}))
    const user = userEvent.setup()
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }))

    const button = await screen.findByRole('button', { name: /ausschuss gesichtet, weiter/i })
    await user.click(button)

    expect(button).toBeDisabled()
    expect(projectsApi.confirmAusschussGate).toHaveBeenCalledTimes(1)
  })

  it('bleibt in der Uebersicht und laedt den Bestand nach dem Abschluss neu', async () => {
    // Der Abschluss ist eine projektweite Aktion, die einzelne Aufnahmen veraendert: Der Bestand
    // darf danach nicht den alten Stand zeigen - und die Seite wechselt dabei nicht.
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([entry(42)], { openCount: 1 }))
    const user = userEvent.setup()
    renderPage(project({ last_scoring_run: ERFOLGREICHER_LAUF }))

    await user.click(
      await screen.findByRole('button', { name: /ausschuss gesichtet, weiter \(1\)/i }),
    )
    await waitFor(() => expect(projectsApi.confirmAusschussGate).toHaveBeenCalledWith(1))

    // Der zweite Aufruf derselben Abfrage entsteht durch die Invalidierung, nicht durch einen
    // Seitenwechsel: die Adresse bleibt die Uebersicht.
    await waitFor(() =>
      expect(vi.mocked(ausschussApi.listAusschuss).mock.calls.length).toBeGreaterThan(1),
    )
    expect(abfrage()).toBe('')
  })
})
