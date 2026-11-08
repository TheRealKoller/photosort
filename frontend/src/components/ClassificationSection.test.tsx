import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as projectsApi from '../api/projects'
import type {
  CriterionScoringRunSummary,
  ProjectModelChoiceOut,
  ProjectOut,
  ScoringRunSummary,
} from '../api/types'
import { ClassificationSection } from './ClassificationSection'
import { RUN_STEP_TEXTS } from '../utils/stepActionTexts'

// specs/features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md - traegt die vollstaendige
// Verhaltensmatrix des einen Ausloesers. Loest die frueheren, getrennten Testfaelle in
// KriterienStepPage.test.tsx (Kriterien-Bewertung) und RemoteCategoryClassificationSection.test.tsx
// (Remote-Kategorisierung, samt Komponente geloescht) ab.

vi.mock('../api/projects')

function project(overrides: Partial<ProjectOut> = {}): ProjectOut {
  return {
    id: 1,
    name: 'Costa Rica',
    opencloud_drive_id: 'drive-1',
    opencloud_path: 'CostaRica',
    created_at: '2026-07-20T10:00:00Z',
    last_scan: null,
    last_scoring_run: scoringRun(),
    last_criterion_scoring_run: null,
    last_export_run: null,
    category_selection_enabled: true,
    cloud_vision_detection_enabled: false,
    cloud_vision_consent_at: null,
    model_choice: {
      category_method: 'cloud',
      category_provider: 'mistral',
      category_model: 'ministral-3b-2512',
      landmark_provider: 'anthropic',
      landmark_model: 'claude-haiku-4-5',
    },
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
    id: 42,
    status: 'success',
    started_at: '2026-07-20T10:00:00Z',
    finished_at: '2026-07-20T10:05:00Z',
    photos_total: 10,
    photos_processed: 10,
    suggestions_found: 0,
    error_message: null,
    gate_confirmed_at: '2026-07-20T10:05:00Z',
    ...overrides,
  }
}

function classificationRun(
  overrides: Partial<CriterionScoringRunSummary> = {},
): CriterionScoringRunSummary {
  return {
    status: 'running',
    started_at: '2026-07-20T10:06:00Z',
    finished_at: null,
    photos_total: 0,
    photos_processed: 0,
    error_message: null,
    phase: 'criteria',
    cloud_requested: false,
    cloud_error_message: null,
    cloud_phases: [],
    estimated_cost_usd: null,
    cloud_cost_total_usd: null,
    phase_remaining_seconds: null,
    persons_photos_total: null,
    persons_photos_processed: null,
    mode: null,
    eye_photos_total: null,
    eye_photos_processed: null,
    ...overrides,
  }
}

function renderSection(
  initialProject: ProjectOut,
  refetchProject = vi.fn(),
  locationState: unknown = null,
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return render(
    <MemoryRouter initialEntries={[{ pathname: '/', state: locationState }]}>
      <Routes>
        <Route
          path="/"
          element={
            <ClassificationSection project={initialProject} refetchProject={refetchProject} />
          }
        />
      </Routes>
    </MemoryRouter>,
    { wrapper },
  )
}

function leiste(): HTMLElement {
  return screen.getByRole('group', { name: 'Nächste Aktion' })
}

const TRIGGER = { name: 'Klassifizierung starten' }
const RERUN = RUN_STEP_TEXTS.kriterien.rerun
const ERFOLG = { status: 'success' as const, phase: null, finished_at: '2026-07-20T10:07:00Z' }
// Die ZWEI Wege der Laufwahl (Spec 0383). Die Zugaenglichkeitsnamen beginnen mit dem Weg-Label;
// die Nebenangabe darunter ist Teil desselben `<label>` und deshalb Teil des Namens.
const PROJECT_WAY = { name: /^wie im projekt eingestellt/i }
const LOCAL_WAY = { name: /^nur lokal/i }

/** Die Palette einer Eye-Kategorisierung - was der Server nach einem `PUT` zurueckgibt. */
const EYE_CHOICE: ProjectModelChoiceOut = {
  category_method: 'eye',
  category_provider: null,
  category_model: null,
  landmark_provider: 'anthropic',
  landmark_model: 'claude-haiku-4-5',
}
const CLOUD_CHOICE: ProjectModelChoiceOut = {
  category_method: 'cloud',
  category_provider: 'mistral',
  category_model: 'ministral-3b-2512',
  landmark_provider: 'anthropic',
  landmark_model: 'claude-haiku-4-5',
}

async function chooseWay(
  user: ReturnType<typeof userEvent.setup>,
  name: { name: RegExp },
): Promise<void> {
  await user.click(screen.getByRole('radio', name))
}

beforeEach(() => {
  vi.mocked(projectsApi.triggerClassification).mockReset()
  vi.mocked(projectsApi.getClassificationEstimate).mockReset()
  // Je Weg eine passende Antwort: der Server rechnet die Anteile des gewaehlten Wegs, und die
  // Anzeige folgt `mode` aus der Antwort - nicht dem Zustand der Oberflaeche.
  vi.mocked(projectsApi.getClassificationEstimate).mockImplementation((_id, mode) =>
    Promise.resolve(
      mode === 'project'
        ? {
            mode,
            candidate_count: 5,
            categorization: {
              kind: 'cloud',
              provider: 'mistral',
              model: 'ministral-3b-2512',
              price_per_image_usd: 0.000305,
              candidate_count: 4,
              estimated_cost_usd: 0.0208,
            },
            landmark: {
              kind: 'cloud',
              provider: 'anthropic',
              model: 'claude-haiku-4-5',
              price_per_image_usd: 0.0052,
              candidate_count: 1,
              estimated_cost_usd: 0.0052,
            },
            estimated_cost_usd: 0.026,
          }
        : {
            mode,
            candidate_count: 0,
            categorization: null,
            landmark: null,
            estimated_cost_usd: 0,
          },
    ),
  )
  vi.mocked(projectsApi.listFineLabels).mockReset()
  vi.mocked(projectsApi.listFineLabels).mockResolvedValue([])
})

describe('ein Auslöser', () => {
  it('renders exactly one trigger button', () => {
    renderSection(project())

    expect(screen.getAllByRole('button', TRIGGER)).toHaveLength(1)
    // Regressionsschutz gegen ein Wiederauftauchen der zweiten Auslösung.
    expect(
      screen.queryByRole('button', { name: /remote-kategorisierung starten/i }),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /kriterien-bewertung starten/i }),
    ).not.toBeInTheDocument()
  })

  it('sends the scoring_run_id of last_scoring_run when triggered', async () => {
    vi.mocked(projectsApi.triggerClassification).mockReturnValue(new Promise(() => {}))
    const user = userEvent.setup()
    renderSection(project())

    await chooseWay(user, LOCAL_WAY)
    await user.click(screen.getByRole('button', TRIGGER))

    expect(projectsApi.triggerClassification).toHaveBeenCalledWith(1, 42, 'local')
  })

  it('disables the button synchronously on click and sends exactly one request on a double click', async () => {
    vi.mocked(projectsApi.triggerClassification).mockReturnValue(new Promise(() => {}))
    const user = userEvent.setup()
    renderSection(project())
    await chooseWay(user, LOCAL_WAY)

    const button = screen.getByRole('button', TRIGGER)
    await user.click(button)
    await user.click(button)

    expect(button).toBeDisabled()
    expect(projectsApi.triggerClassification).toHaveBeenCalledTimes(1)
  })

  it('re-enables the button and shows an error when the trigger request itself fails', async () => {
    vi.mocked(projectsApi.triggerClassification).mockRejectedValue(
      new ApiError(500, 'Serverfehler'),
    )
    const user = userEvent.setup()
    renderSection(project())
    await chooseWay(user, LOCAL_WAY)

    await user.click(screen.getByRole('button', TRIGGER))

    await waitFor(() => expect(screen.getByRole('button', TRIGGER)).toBeEnabled())
    expect(await screen.findByRole('alert')).toHaveTextContent('Serverfehler')
  })

  it('bietet nach einem 503 "Erneut versuchen" und wiederholt genau einen Aufruf', async () => {
    vi.mocked(projectsApi.triggerClassification)
      .mockRejectedValueOnce(new ApiError(503, 'Eye ist nicht erreichbar.'))
      .mockRejectedValueOnce(new ApiError(503, 'Eye ist nicht erreichbar.'))
    const user = userEvent.setup()
    renderSection(project({ model_choice: EYE_CHOICE }))
    await chooseWay(user, PROJECT_WAY)

    await user.click(screen.getByRole('button', TRIGGER))

    // 503 heisst "nicht verfuegbar, spaeter erneut" - der Fehler ist voruebergehend und die
    // Wiederholung deshalb Teil der Meldung, nicht ein zweiter Ausloeser im Formular.
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Eye ist nicht erreichbar.')
    await user.click(within(alert).getByRole('button', { name: 'Erneut versuchen' }))

    await waitFor(() => expect(projectsApi.triggerClassification).toHaveBeenCalledTimes(2))
    expect(projectsApi.triggerClassification).toHaveBeenLastCalledWith(1, 42, 'project')
  })

  it('bietet nach einem 403 KEIN "Erneut versuchen" - die Ablehnung bleibt bestehen', async () => {
    vi.mocked(projectsApi.triggerClassification).mockRejectedValue(
      new ApiError(403, 'Diese Funktion ist derzeit nicht aktiviert.'),
    )
    const user = userEvent.setup()
    renderSection(project({ model_choice: EYE_CHOICE }))
    await chooseWay(user, PROJECT_WAY)

    await user.click(screen.getByRole('button', TRIGGER))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Diese Funktion ist derzeit nicht aktiviert.')
    expect(within(alert).queryByRole('button', { name: 'Erneut versuchen' })).toBeNull()
  })

  it('laesst die Projekt-Wahl nach einem 503 gewaehlt', async () => {
    vi.mocked(projectsApi.triggerClassification).mockRejectedValue(
      new ApiError(503, 'Eye ist nicht erreichbar.'),
    )
    const user = userEvent.setup()
    renderSection(project({ model_choice: EYE_CHOICE }))
    await chooseWay(user, PROJECT_WAY)

    await user.click(screen.getByRole('button', TRIGGER))

    await screen.findByRole('alert')
    // Der Fehlschlag ist keine neue Wahl: ein stiller Rueckfall auf einen anderen Weg waere
    // schlimmer als die sichtbare Ablehnung, und die Wahl gehoert der Person.
    expect(screen.getByRole('radio', PROJECT_WAY)).toBeChecked()
  })

  it('never repeats the withdrawn "results only take effect on a later run" hint', () => {
    renderSection(
      project({
        cloud_vision_detection_enabled: true,
        last_criterion_scoring_run: classificationRun({
          status: 'success',
          cloud_requested: true,
        }),
      }),
    )

    // Der Hinweis aus Spec 0218 ist durch die Verkettung gegenstandslos geworden.
    expect(screen.queryByText(/fließen erst durch einen/i)).not.toBeInTheDocument()
  })
})

describe('Weg für diesen Durchlauf', () => {
  it('zeigt KEINE Vorbelegung - auch nicht bei erteilter Cloud-Einwilligung', () => {
    renderSection(project({ cloud_vision_detection_enabled: true }))

    // Jeder Durchlauf beginnt mit einer bewussten Entscheidung; die Einwilligung ist eine
    // Vorbedingung, keine Wahl.
    for (const radio of screen.getAllByRole('radio')) {
      expect(radio).not.toBeChecked()
    }
    expect(screen.getByRole('button', TRIGGER)).toBeDisabled()
    expect(screen.getByTestId('classification-disabled-reason')).toHaveTextContent(
      /ohne wahl startet kein lauf/i,
    )
  })

  it('bietet GENAU ZWEI Wege - Cloud und Eye sind keine Anfragewege mehr', () => {
    renderSection(project({ model_choice: EYE_CHOICE }))

    const radios = screen.getAllByRole('radio')
    expect(radios).toHaveLength(2)
    expect(screen.getByRole('radio', PROJECT_WAY)).toBeInTheDocument()
    expect(screen.getByRole('radio', LOCAL_WAY)).toBeInTheDocument()
    expect(screen.queryByRole('radio', { name: /^cloud/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('radio', { name: /^eye/i })).not.toBeInTheDocument()
  })

  it('nennt die Gruppe ueber eine legend', () => {
    renderSection(project())

    expect(screen.getByRole('group', { name: 'Weg für diesen Durchlauf' })).toBeInTheDocument()
  })

  it('fasst die Projektwahl in der Zeile zusammen', () => {
    renderSection(project({ model_choice: CLOUD_CHOICE, cloud_vision_detection_enabled: true }))

    const meta = screen.getByTestId('way-project-meta')
    expect(meta).toHaveTextContent(/Kategorisierung: Mistral, ministral-3b-2512/)
    expect(meta).toHaveTextContent(/Sehenswürdigkeits-Erkennung: Anthropic, claude-haiku-4-5/)
  })

  it('sagt bei Eye-Kategorisierung ohne Einwilligung, dass die Erkennung entfaellt', () => {
    renderSection(project({ model_choice: EYE_CHOICE }))

    const meta = screen.getByTestId('way-project-meta')
    expect(meta).toHaveTextContent(/Kategorisierung: Eye/)
    expect(meta).toHaveTextContent(/entfällt — keine Cloud-Einwilligung/)
  })

  it('verlinkt die Aenderung AUSSERHALB des Labels in die Einstellungen', () => {
    renderSection(project())

    const link = screen.getByRole('link', { name: 'In den Projekteinstellungen ändern' })
    expect(link).toHaveAttribute('href', '/projects/1/settings')
    // Ein Link IM <label> setzte beim Klick zusaetzlich die Wahl - er steht deshalb daneben.
    expect(link.closest('label')).toBeNull()
  })

  it('sperrt den Cloud-Weg ohne Einwilligung und verweist auf die Einstellungen', async () => {
    const user = userEvent.setup()
    renderSection(project({ cloud_vision_detection_enabled: false }))

    await chooseWay(user, PROJECT_WAY)

    expect(screen.getByRole('button', TRIGGER)).toBeDisabled()
    expect(screen.getByTestId('classification-disabled-reason')).toHaveTextContent(
      /nicht aktiviert/i,
    )
    expect(
      screen.getByRole('link', { name: /in den projekteinstellungen aktivieren/i }),
    ).toHaveAttribute('href', '/projects/1/settings')
    // "Nur lokal" bleibt startklar, auch wenn der wirksame Weg gesperrt ist.
    expect(screen.getByRole('radio', LOCAL_WAY)).toBeEnabled()
  })

  it('sendet mode=project, wenn "wie im Projekt eingestellt" gewaehlt ist', async () => {
    vi.mocked(projectsApi.triggerClassification).mockReturnValue(new Promise(() => {}))
    const user = userEvent.setup()
    renderSection(project({ cloud_vision_detection_enabled: true }))
    await chooseWay(user, PROJECT_WAY)
    await screen.findByTestId('classification-estimate')

    await user.click(screen.getByRole('button', TRIGGER))

    expect(projectsApi.triggerClassification).toHaveBeenCalledWith(1, 42, 'project')
  })

  it('sendet mode=project auch bei Eye-Kategorisierung - den Weg entscheidet der Server', async () => {
    vi.mocked(projectsApi.getClassificationEstimate).mockResolvedValue({
      mode: 'project',
      candidate_count: 0,
      categorization: {
        kind: 'eye',
        provider: null,
        model: null,
        price_per_image_usd: 0,
        candidate_count: 0,
        estimated_cost_usd: 0,
      },
      landmark: null,
      estimated_cost_usd: 0,
    })
    vi.mocked(projectsApi.triggerClassification).mockReturnValue(new Promise(() => {}))
    const user = userEvent.setup()
    renderSection(project({ model_choice: EYE_CHOICE }))
    await chooseWay(user, PROJECT_WAY)
    await screen.findByTestId('classification-estimate')

    await user.click(screen.getByRole('button', TRIGGER))

    expect(projectsApi.triggerClassification).toHaveBeenCalledWith(1, 42, 'project')
  })

  it('fragt die Schaetzung je Wahl ab', async () => {
    const user = userEvent.setup()
    renderSection(project({ cloud_vision_detection_enabled: true }))

    // Vor der Wahl laedt NICHTS - es gibt keinen Durchlauf, dessen Kosten sie beschriebe.
    expect(projectsApi.getClassificationEstimate).not.toHaveBeenCalled()

    await chooseWay(user, PROJECT_WAY)
    await waitFor(() => {
      expect(projectsApi.getClassificationEstimate).toHaveBeenCalledWith(1, 'project')
    })
  })

  it('setzt die Wahl nach dem Start zurueck - der naechste Lauf beginnt ohne sie', async () => {
    vi.mocked(projectsApi.triggerClassification).mockResolvedValue({ status: 'queued' })
    const user = userEvent.setup()
    renderSection(project({ last_criterion_scoring_run: classificationRun(ERFOLG) }))
    await chooseWay(user, LOCAL_WAY)

    await user.click(screen.getByRole('button', { name: RERUN.label }))

    await waitFor(() => {
      expect(screen.getByRole('radio', LOCAL_WAY)).not.toBeChecked()
    })
  })

  // Spec 0383: an der Wahl haengt die Aussage ueber den Datenfluss, und die nennt die Anbieter JE
  // TAETIGKEIT aus `project.model_choice`.
  it('sagt bei Eye-Kategorisierung, dass kein Foto den Server verlaesst', async () => {
    const user = userEvent.setup()
    renderSection(project({ model_choice: EYE_CHOICE }))
    await chooseWay(user, PROJECT_WAY)

    const text = screen.getByTestId('classification-scope-text')
    expect(text).toHaveTextContent(/verlässt kein foto diesen server/i)
    expect(text).toHaveTextContent(/lizenzmeldung mit einer zählkennung/i)
    expect(text).toHaveTextContent(/lässt sich nicht abschalten/i)
    // Ohne Einwilligung laeuft keine Cloud-Phase - der Ortshinweis gehoert dann nicht hierher.
    expect(text).not.toHaveTextContent(/ortsname/i)
  })

  it('nennt bei Eye-Kategorisierung mit Einwilligung die Sehenswuerdigkeits-Erkennung samt Ortsangabe', async () => {
    const user = userEvent.setup()
    renderSection(project({ model_choice: EYE_CHOICE, cloud_vision_detection_enabled: true }))
    await chooseWay(user, PROJECT_WAY)

    const text = screen.getByTestId('classification-scope-text')
    expect(text).toHaveTextContent(/sehenswürdigkeits-erkennung/i)
    expect(text).toHaveTextContent(/ortsname/i)
    expect(text).toHaveTextContent(/koordinate/i)
    // Die Lizenzmeldung steht auch dann - sie haengt an der Kategorisierung, nicht an der Einwilligung.
    expect(text).toHaveTextContent(/lässt sich nicht abschalten/i)
  })

  it('nennt die Anbieter beider Taetigkeiten, wenn sie sich unterscheiden', async () => {
    const user = userEvent.setup()
    renderSection(project({ model_choice: CLOUD_CHOICE, cloud_vision_detection_enabled: true }))
    await chooseWay(user, PROJECT_WAY)

    const text = screen.getByTestId('classification-scope-text')
    expect(text).toHaveTextContent(/an Mistral — für Kategorie-Vorschläge/)
    expect(text).toHaveTextContent(/an Anthropic\./)
  })

  it('sagt beim lokalen Weg, dass kein Foto den Server verlaesst - ohne Lizenzmeldung', async () => {
    const user = userEvent.setup()
    renderSection(project({ model_choice: EYE_CHOICE }))
    await chooseWay(user, LOCAL_WAY)

    const text = screen.getByTestId('classification-scope-text')
    expect(text).toHaveTextContent(/läuft vollständig lokal auf diesem server/i)
    expect(text).not.toHaveTextContent(/desert ant labs/i)
    expect(text).not.toHaveTextContent(/ortsname/i)
  })
})

describe('Kosten sichtbar vor dem Start', () => {
  it('stellt die Schätzung beim Start als letztes Inhaltselement direkt über die Leiste', async () => {
    // Der INHALT der Kostenvorschau wird in ClassificationEstimate.test.tsx geprüft.
    const user = userEvent.setup()
    renderSection(project({ cloud_vision_detection_enabled: true }))
    await chooseWay(user, PROJECT_WAY)

    const estimate = await screen.findByTestId('classification-estimate')
    expect(estimate.nextElementSibling).toBe(leiste())
  })

  it('stellt die Schätzung beim erneuten Auslösen in den Erneut-Block', async () => {
    const user = userEvent.setup()
    renderSection(
      project({
        cloud_vision_detection_enabled: true,
        last_criterion_scoring_run: classificationRun(ERFOLG),
      }),
    )
    await chooseWay(user, PROJECT_WAY)

    const block = screen.getByTestId('rerun-block')
    expect(await within(block).findByTestId('classification-estimate')).toBeInTheDocument()
    expect(screen.getAllByTestId('classification-estimate')).toHaveLength(1)
  })

  it.each([
    ['Start', null],
    ['Wiederholung', classificationRun({ status: 'failed', phase: null })],
    ['Erneut', classificationRun(ERFOLG)],
  ])('sperrt "%s" ohne ladbare Schätzung bei Cloud-Nutzung', async (_, run) => {
    vi.mocked(projectsApi.getClassificationEstimate).mockRejectedValue(
      new ApiError(500, 'Serverfehler'),
    )
    const user = userEvent.setup()
    renderSection(
      project({ cloud_vision_detection_enabled: true, last_criterion_scoring_run: run }),
    )
    await chooseWay(user, PROJECT_WAY)

    const name = run?.status === 'success' ? RERUN.label : TRIGGER.name
    await waitFor(() => expect(screen.getByRole('button', { name })).toBeDisabled())
  })

  it('zeigt vor der Wahl keine Schaetzung', () => {
    renderSection(project({ cloud_vision_detection_enabled: true }))

    expect(screen.queryByTestId('classification-estimate')).not.toBeInTheDocument()
  })

  it('zeigt fuer den lokalen Weg die kostenfreie Zeile statt Cloud-Betraegen', async () => {
    const user = userEvent.setup()
    renderSection(project({ cloud_vision_detection_enabled: true }))

    await chooseWay(user, LOCAL_WAY)

    // Die Antwort des Servers traegt `mode`; die Anzeige folgt IHR, nicht einer Annahme der
    // Oberflaeche.
    const estimate = await screen.findByTestId('classification-estimate')
    expect(estimate).toHaveTextContent('Dieser Durchlauf ist kostenfrei.')
    expect(estimate.textContent).not.toMatch(/USD/)
  })

  it('never opens a confirmation dialog before the paid action', async () => {
    vi.mocked(projectsApi.triggerClassification).mockReturnValue(new Promise(() => {}))
    const user = userEvent.setup()
    renderSection(project({ cloud_vision_detection_enabled: true }))
    await chooseWay(user, PROJECT_WAY)
    await screen.findByTestId('classification-estimate')

    await user.click(screen.getByRole('button', TRIGGER))

    // Das Design-System-Muster "Bestaetigungsdialog vor kostenpflichtiger Aktion" ist mit dieser
    // Spec ausdruecklich zurueckgenommen - die Schaetzung an der Laufwahl tritt an seine Stelle.
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(projectsApi.triggerClassification).toHaveBeenCalledWith(1, 42, 'project')
  })

  it('blocks the cloud run while the estimate cannot be loaded, but allows the local one', async () => {
    vi.mocked(projectsApi.getClassificationEstimate).mockRejectedValue(
      new ApiError(500, 'Serverfehler'),
    )
    const user = userEvent.setup()
    renderSection(project({ cloud_vision_detection_enabled: true }))

    await chooseWay(user, PROJECT_WAY)

    // "Kein Bypass": keine kostenpflichtige Aktion ohne sichtbare Schaetzung.
    await waitFor(() => expect(screen.getByRole('button', TRIGGER)).toBeDisabled())

    await chooseWay(user, LOCAL_WAY)

    // Ohne Kosten ist die Schaetzung keine Vorbedingung - der lokale Weg bleibt bedienbar.
    await waitFor(() => expect(screen.getByRole('button', TRIGGER)).toBeEnabled())
  })
})

describe('genau einer der beiden Zustandsblöcke', () => {
  // specs/features/0348-klassifizierungs-transparenz.md: die prüfbare Form des
  // Akzeptanzkriteriums "überfrachtet die Seite nicht". Der Inhalt der beiden Blöcke wird in
  // ClassificationProgress.test.tsx bzw. ClassificationBalance.test.tsx geprüft.
  function isProgressShown(): boolean {
    return screen.queryByRole('list', { name: /teilschritte der klassifizierung/i }) !== null
  }
  function isBalanceShown(): boolean {
    return screen.queryByTestId('classification-balance') !== null
  }

  it.each([
    ['kein Lauf', null, false, false],
    ['laufend', 'running' as const, true, false],
    ['erfolgreich', 'success' as const, false, true],
    ['fehlgeschlagen', 'failed' as const, false, true],
  ])('rendert bei "%s" genau den erwarteten Block', (_name, status, progress, balance) => {
    renderSection(
      project({
        last_criterion_scoring_run:
          status === null
            ? null
            : classificationRun({ status, phase: status === 'running' ? 'criteria' : null }),
      }),
    )

    expect(isProgressShown()).toBe(progress)
    expect(isBalanceShown()).toBe(balance)
    // Nie beide gleichzeitig - das ist die eigentliche Zusage.
    expect(isProgressShown() && isBalanceShown()).toBe(false)
  })

  // Die Statuszeile nennt den ganzen Schritt in JEDER Phase gleich - die Teilschritte
  // unterscheidet die Fortschrittsliste darunter.
  it.each(['remote_categories', 'criteria', 'landmark', 'ranking', 'persons'] as const)(
    'zeigt waehrend der Phase "%s" die Statuszeile "Klassifizierung läuft…"',
    (phase) => {
      renderSection(
        project({ last_criterion_scoring_run: classificationRun({ status: 'running', phase }) }),
      )

      expect(leiste().querySelector('[aria-live]')).toHaveTextContent('Klassifizierung läuft…')
      expect(
        within(leiste()).getByRole('button', { name: RUN_STEP_TEXTS.kriterien.running }),
      ).toBeDisabled()
      expect(screen.queryByText(/Remote-Kategorisierung läuft/)).toBeNull()
    },
  )

  it('ersetzt die Bilanz wieder durch die Fortschrittsliste, sobald ein neuer Lauf startet', () => {
    const { rerender } = renderSection(
      project({
        last_criterion_scoring_run: classificationRun({ status: 'success', phase: null }),
      }),
    )
    expect(isBalanceShown()).toBe(true)

    rerender(
      <MemoryRouter>
        <ClassificationSection
          project={project({
            last_criterion_scoring_run: classificationRun({
              status: 'running',
              phase: 'remote_categories',
            }),
          })}
          refetchProject={vi.fn()}
        />
      </MemoryRouter>,
    )

    expect(isProgressShown()).toBe(true)
    expect(isBalanceShown()).toBe(false)
  })

  it('kündigt den Abschluss an und führt per Link zur Kuratierung weiter', async () => {
    const user = userEvent.setup()
    renderSection(
      project({
        cloud_vision_detection_enabled: true,
        last_criterion_scoring_run: classificationRun({
          ...ERFOLG,
          cloud_requested: true,
          photos_total: 10,
          photos_processed: 10,
        }),
      }),
    )

    expect(within(leiste()).getByText('Klassifizierung abgeschlossen')).toBeInTheDocument()
    expect(within(leiste()).getByRole('link', { name: 'Weiter zur Kuratierung' })).toHaveAttribute(
      'href',
      '/projects/1/pipeline/kuratierung',
    )
    expect(screen.queryByRole('button', TRIGGER)).not.toBeInTheDocument()
    // Bei gewähltem Cloud-Weg erst bedienbar, sobald die Schätzung vorliegt.
    await chooseWay(user, PROJECT_WAY)
    await screen.findByTestId('classification-estimate')
    expect(screen.getByRole('button', { name: RERUN.label })).toBeEnabled()
    expect(screen.getByText(RERUN.explanation)).toBeVisible()
  })

  it('bietet bei einem Fehlschlag genau eine Wiederholung: den Startknopf der Leiste', async () => {
    vi.mocked(projectsApi.triggerClassification).mockResolvedValue({ status: 'queued' })
    const user = userEvent.setup()
    renderSection(
      project({
        last_criterion_scoring_run: classificationRun({
          status: 'failed',
          phase: null,
          error_message: 'Unerwarteter Fehler',
        }),
      }),
    )

    expect(await screen.findByRole('alert')).toHaveTextContent('Unerwarteter Fehler')
    expect(screen.queryByRole('button', { name: /erneut/i })).not.toBeInTheDocument()
    expect(screen.getAllByRole('button', TRIGGER)).toHaveLength(1)
    await chooseWay(user, LOCAL_WAY)
    await user.click(within(leiste()).getByRole('button', TRIGGER))

    expect(projectsApi.triggerClassification).toHaveBeenCalledWith(1, 42, 'local')
  })

  it('setzt den Fokus nach dem automatischen Wechsel auf die Überschrift', () => {
    renderSection(project(), vi.fn(), { focusHeading: true })

    expect(screen.getByRole('heading', { level: 2, name: 'Klassifizierung' })).toHaveFocus()
  })

  it('zeigt nach dem Auslösen sofort den laufenden Statuspunkt und ein Ladezeichen am Erneut-Knopf', async () => {
    vi.mocked(projectsApi.triggerClassification).mockReturnValue(new Promise(() => {}))
    const user = userEvent.setup()
    renderSection(project({ last_criterion_scoring_run: classificationRun(ERFOLG) }))

    await chooseWay(user, LOCAL_WAY)
    const rerun = screen.getByRole('button', { name: RERUN.label })
    await user.click(rerun)

    const dot = leiste().querySelector('[aria-live] > span[aria-hidden="true"]')
    expect(dot).toHaveClass('bg-status-running')
    expect(dot).not.toHaveClass('bg-status-success')
    expect(rerun).toBeDisabled()
    expect(within(rerun).getByTestId('button-spinner')).toBeInTheDocument()
  })

  it('setzt den Fokus bei einem normalen Aufruf nicht', () => {
    renderSection(project())

    expect(screen.getByRole('heading', { level: 2, name: 'Klassifizierung' })).not.toHaveFocus()
  })
})

describe('Fehlerverhalten und Herkunft des Ergebnisses', () => {
  it('reports a failed cloud share and marks the result as unenriched', async () => {
    renderSection(
      project({
        cloud_vision_detection_enabled: true,
        last_criterion_scoring_run: classificationRun({
          status: 'success',
          phase: null,
          cloud_requested: true,
          cloud_error_message: 'Remote-Kategorisierung fehlgeschlagen: Zeitüberschreitung',
        }),
      }),
    )

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Remote-Kategorisierung fehlgeschlagen: Zeitüberschreitung')
    expect(alert).toHaveTextContent(/ohne \(vollständige\) cloud-anreicherung entstanden/i)
    // Der Lauf selbst ist erfolgreich - der lokale Bewertungsanteil lief vollstaendig durch.
    expect(screen.getByText('Klassifizierung abgeschlossen')).toBeInTheDocument()
  })

  it('notes a purely local run without any error styling', () => {
    renderSection(
      project({
        cloud_vision_detection_enabled: true,
        last_criterion_scoring_run: classificationRun({
          status: 'success',
          phase: null,
          cloud_requested: false,
        }),
      }),
    )

    expect(screen.getByText(/ohne cloud-anreicherung durchgeführt/i)).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('stays silent about enrichment after a clean cloud run', () => {
    renderSection(
      project({
        cloud_vision_detection_enabled: true,
        last_criterion_scoring_run: classificationRun({
          status: 'success',
          phase: null,
          cloud_requested: true,
          cloud_error_message: null,
        }),
      }),
    )

    expect(screen.queryByText(/ohne cloud-anreicherung durchgeführt/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})

describe('Feinlabel-Häufigkeiten', () => {
  it('lists the fine labels with their counts', async () => {
    vi.mocked(projectsApi.listFineLabels).mockResolvedValue([
      { canonical_key: 'hund', display_name: 'Hund', photo_count: 7 },
    ])
    renderSection(project())

    expect(await screen.findByText('Hund')).toBeInTheDocument()
    expect(screen.getByText('7 Mal')).toBeInTheDocument()
  })

  it('shows an empty state instead of the context sentence when there are none', async () => {
    renderSection(project())

    expect(await screen.findByText(/keine zusätzlichen label ermittelt/i)).toBeInTheDocument()
    expect(screen.queryByText(/traten häufig auf/i)).not.toBeInTheDocument()
  })

  it('shows a retryable error when the fine labels cannot be loaded', async () => {
    vi.mocked(projectsApi.listFineLabels).mockRejectedValue(new ApiError(500, 'Serverfehler'))
    renderSection(project())

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /feinlabels konnten nicht geladen werden/i,
    )
  })
})

// specs/features/0304-cloud-modell-je-anbieter-waehlbar.md, ADR 0059 Punkt 4: fuer das
// eingestellte Modell ist kein Preis hinterlegt - die Schaetzung weist das aus, statt einen
// falschen (oder gar keinen) Betrag zu zeigen.
describe('Kostenschätzung ohne hinterlegten Preis', () => {
  // specs/features/0304-cloud-modell-je-anbieter-waehlbar.md, ADR 0059 Punkt 4. Die DARSTELLUNG
  // des Falls prüft ClassificationEstimate.test.tsx; hier steht die Zusage des Containers.
  const withoutPrice = {
    mode: 'project' as const,
    candidate_count: 5,
    categorization: {
      kind: 'cloud' as const,
      provider: 'anthropic',
      model: 'ein-nie-bepreistes-modell',
      price_per_image_usd: null,
      candidate_count: 4,
      estimated_cost_usd: null,
    },
    landmark: {
      kind: 'cloud' as const,
      provider: 'anthropic',
      model: 'ein-nie-bepreistes-modell',
      price_per_image_usd: null,
      candidate_count: 1,
      estimated_cost_usd: null,
    },
    estimated_cost_usd: null,
  }

  it('keeps the start button usable when no price is known', async () => {
    vi.mocked(projectsApi.getClassificationEstimate).mockResolvedValue(withoutPrice)
    const user = userEvent.setup()
    renderSection(project({ cloud_vision_detection_enabled: true }))
    await chooseWay(user, PROJECT_WAY)

    await screen.findByTestId('classification-estimate')

    // Regressionsschutz: die Sperre hängt an der fehlenden SCHÄTZUNG (Ladefehler), nicht am
    // fehlenden Betrag - ein Guard auf `estimated_cost_usd === null` machte das Produkt bei einem
    // reinen Preispflege-Versäumnis unbenutzbar.
    expect(screen.getByRole('button', TRIGGER)).toBeEnabled()
  })
})

// specs/features/0567-richtwert-vor-klassifizierung.md: der Richtwert ist schon vor dem ersten
// Lauf einstellbar, mit DERSELBEN Komponente wie in der Kuratierung.
describe('Richtwert vor der Klassifizierung', () => {
  it('renders the target field above the trigger even without any previous run', () => {
    renderSection(project({ last_criterion_scoring_run: null, effective_selection_target: 42 }))

    const field = screen.getByLabelText(/richtwert \(bilder\)/i)
    const trigger = screen.getByRole('button', TRIGGER)
    expect(field).toBeEnabled()
    expect(field).toHaveAccessibleDescription('Standard: 42 Bilder.')
    expect(field.compareDocumentPosition(trigger) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.getByText(/ziel, keine obergrenze/i)).toBeInTheDocument()
    // Der Satz zur Motivmischung bleibt der Kuratierung vorbehalten.
    expect(screen.queryByText(/mischt in jedem die vorkommenden motive/i)).not.toBeInTheDocument()
  })

  it('saves a target before the first run', async () => {
    const user = userEvent.setup()
    vi.mocked(projectsApi.setSelectionTarget).mockResolvedValue(project({ selection_target: 80 }))
    renderSection(project({ last_criterion_scoring_run: null }))

    await user.type(screen.getByLabelText(/richtwert \(bilder\)/i), '80')
    await user.tab()

    await waitFor(() => {
      expect(projectsApi.setSelectionTarget).toHaveBeenCalledWith(1, 80)
    })
  })

  it('locks the field while the classification runs', () => {
    renderSection(
      project({
        last_criterion_scoring_run: classificationRun({ status: 'running', finished_at: null }),
      }),
    )

    expect(screen.getByLabelText(/richtwert \(bilder\)/i)).toBeDisabled()
    expect(
      screen.getByText('Während die Klassifizierung läuft, lässt sich der Richtwert nicht ändern.'),
    ).toBeInTheDocument()
  })
})
