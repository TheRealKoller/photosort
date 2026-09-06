import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as projectsApi from '../api/projects'
import type { CriterionScoringRunSummary, ProjectOut, ScoringRunSummary } from '../api/types'
import { ClassificationSection } from './ClassificationSection'

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
    last_remote_category_classification_run: null,
    category_selection_enabled: true,
    cloud_vision_detection_enabled: false,
    cloud_vision_consent_at: null,
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
  overrides: Partial<CriterionScoringRunSummary> = {}
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
    ...overrides,
  }
}

function remoteRun(
  overrides: Partial<NonNullable<ProjectOut['last_remote_category_classification_run']>> = {}
): NonNullable<ProjectOut['last_remote_category_classification_run']> {
  return {
    status: 'running',
    started_at: '2026-07-20T10:06:00Z',
    finished_at: null,
    photos_total: 8,
    photos_processed: 3,
    error_message: null,
    ...overrides,
  }
}

function renderSection(initialProject: ProjectOut, refetchProject = vi.fn()) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return render(
    <MemoryRouter>
      <ClassificationSection project={initialProject} refetchProject={refetchProject} />
    </MemoryRouter>,
    { wrapper }
  )
}

const TRIGGER = { name: 'Klassifizierung starten' }
const CHECKBOX = { name: /cloud-bilderkennung für diesen durchlauf nutzen/i }

beforeEach(() => {
  vi.mocked(projectsApi.triggerClassification).mockReset()
  vi.mocked(projectsApi.getClassificationEstimate).mockReset()
  vi.mocked(projectsApi.getClassificationEstimate).mockResolvedValue({
    candidate_count: 5,
    remote_category_candidate_count: 4,
    landmark_candidate_count: 1,
    provider: 'anthropic',
    model: 'claude-haiku-4-5',
    price_per_image_usd: 0.0052,
    estimated_cost_usd: 0.026,
  })
  vi.mocked(projectsApi.listFineLabels).mockReset()
  vi.mocked(projectsApi.listFineLabels).mockResolvedValue([])
})

describe('ein Auslöser', () => {
  it('renders exactly one trigger button', () => {
    renderSection(project())

    expect(screen.getAllByRole('button', TRIGGER)).toHaveLength(1)
    // Regressionsschutz gegen ein Wiederauftauchen der zweiten Auslösung.
    expect(
      screen.queryByRole('button', { name: /remote-kategorisierung starten/i })
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /kriterien-bewertung starten/i })
    ).not.toBeInTheDocument()
  })

  it('sends the scoring_run_id of last_scoring_run when triggered', async () => {
    vi.mocked(projectsApi.triggerClassification).mockReturnValue(new Promise(() => {}))
    const user = userEvent.setup()
    renderSection(project())

    await user.click(screen.getByRole('button', TRIGGER))

    expect(projectsApi.triggerClassification).toHaveBeenCalledWith(1, 42, false)
  })

  it('disables the button synchronously on click and sends exactly one request on a double click', async () => {
    vi.mocked(projectsApi.triggerClassification).mockReturnValue(new Promise(() => {}))
    const user = userEvent.setup()
    renderSection(project())

    const button = screen.getByRole('button', TRIGGER)
    await user.click(button)
    await user.click(button)

    expect(button).toBeDisabled()
    expect(projectsApi.triggerClassification).toHaveBeenCalledTimes(1)
  })

  it('re-enables the button and shows an error when the trigger request itself fails', async () => {
    vi.mocked(projectsApi.triggerClassification).mockRejectedValue(
      new ApiError(500, 'Serverfehler')
    )
    const user = userEvent.setup()
    renderSection(project())

    await user.click(screen.getByRole('button', TRIGGER))

    await waitFor(() => expect(screen.getByRole('button', TRIGGER)).toBeEnabled())
    expect(await screen.findByRole('alert')).toHaveTextContent('Serverfehler')
  })

  it('never repeats the withdrawn "results only take effect on a later run" hint', () => {
    renderSection(
      project({
        cloud_vision_detection_enabled: true,
        last_criterion_scoring_run: classificationRun({
          status: 'success',
          cloud_requested: true,
        }),
      })
    )

    // Der Hinweis aus Spec 0218 ist durch die Verkettung gegenstandslos geworden.
    expect(screen.queryByText(/fließen erst durch einen/i)).not.toBeInTheDocument()
  })
})

describe('Cloud-Nutzung pro Durchlauf', () => {
  it('pre-checks the checkbox when the project consent is granted', () => {
    renderSection(project({ cloud_vision_detection_enabled: true }))

    const checkbox = screen.getByRole('checkbox', CHECKBOX)
    expect(checkbox).toBeChecked()
    expect(checkbox).toBeEnabled()
  })

  it('leaves the checkbox unchecked and unsettable without consent, pointing at the settings', () => {
    renderSection(project({ cloud_vision_detection_enabled: false }))

    const checkbox = screen.getByRole('checkbox', CHECKBOX)
    expect(checkbox).not.toBeChecked()
    expect(checkbox).toBeDisabled()
    expect(
      screen.getByRole('link', { name: /in den projekteinstellungen aktivieren/i })
    ).toHaveAttribute('href', '/projects/1/settings')
  })

  it('sends use_cloud=true when the checkbox stays checked', async () => {
    vi.mocked(projectsApi.triggerClassification).mockReturnValue(new Promise(() => {}))
    const user = userEvent.setup()
    renderSection(project({ cloud_vision_detection_enabled: true }))
    await screen.findByTestId('classification-estimate')

    await user.click(screen.getByRole('button', TRIGGER))

    expect(projectsApi.triggerClassification).toHaveBeenCalledWith(1, 42, true)
  })

  it('sends use_cloud=false once the checkbox is unchecked', async () => {
    vi.mocked(projectsApi.triggerClassification).mockReturnValue(new Promise(() => {}))
    const user = userEvent.setup()
    renderSection(project({ cloud_vision_detection_enabled: true }))

    await user.click(screen.getByRole('checkbox', CHECKBOX))
    await user.click(screen.getByRole('button', TRIGGER))

    expect(projectsApi.triggerClassification).toHaveBeenCalledWith(1, 42, false)
  })

  it('states the local-only guarantee only while the cloud is unchecked', async () => {
    const user = userEvent.setup()
    renderSection(project({ cloud_vision_detection_enabled: true }))

    // Vorausgewaehlt aktiv -> die Zusicherung darf NICHT dastehen (sie waere unwahr).
    expect(screen.getByTestId('classification-scope-text')).toHaveTextContent(/sendet fotos an/i)

    await user.click(screen.getByRole('checkbox', CHECKBOX))

    expect(screen.getByTestId('classification-scope-text')).toHaveTextContent(
      /läuft vollständig lokal auf diesem server/i
    )
  })
})

describe('Kosten sichtbar vor dem Start', () => {
  it('shows the estimate right at the checkbox, marked as an estimate', async () => {
    renderSection(project({ cloud_vision_detection_enabled: true }))

    const estimate = await screen.findByTestId('classification-estimate')
    expect(estimate).toHaveTextContent('~5 Fotos')
    expect(estimate).toHaveTextContent('~$0.03')
    expect(estimate).toHaveTextContent(/schätzung, keine exakte abrechnung/i)
  })

  it('hides the estimate while the cloud is unchecked', async () => {
    const user = userEvent.setup()
    renderSection(project({ cloud_vision_detection_enabled: true }))
    await screen.findByTestId('classification-estimate')

    await user.click(screen.getByRole('checkbox', CHECKBOX))

    expect(screen.queryByTestId('classification-estimate')).not.toBeInTheDocument()
  })

  it('never opens a confirmation dialog before the paid action', async () => {
    vi.mocked(projectsApi.triggerClassification).mockReturnValue(new Promise(() => {}))
    const user = userEvent.setup()
    renderSection(project({ cloud_vision_detection_enabled: true }))
    await screen.findByTestId('classification-estimate')

    await user.click(screen.getByRole('button', TRIGGER))

    // Das Design-System-Muster "Bestaetigungsdialog vor kostenpflichtiger Aktion" ist mit dieser
    // Spec ausdruecklich zurueckgenommen - die Schaetzung an der Checkbox tritt an seine Stelle.
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(projectsApi.triggerClassification).toHaveBeenCalledWith(1, 42, true)
  })

  it('says so when nothing is left to classify', async () => {
    vi.mocked(projectsApi.getClassificationEstimate).mockResolvedValue({
      candidate_count: 0,
      remote_category_candidate_count: 0,
      landmark_candidate_count: 0,
      provider: 'anthropic',
      model: 'claude-haiku-4-5',
      price_per_image_usd: 0.0052,
      estimated_cost_usd: 0,
    })
    renderSection(project({ cloud_vision_detection_enabled: true }))

    expect(await screen.findByTestId('classification-estimate')).toHaveTextContent(
      /alle fotos bereits klassifiziert/i
    )
  })

  it('blocks the cloud run while the estimate cannot be loaded, but allows the local one', async () => {
    vi.mocked(projectsApi.getClassificationEstimate).mockRejectedValue(
      new ApiError(500, 'Serverfehler')
    )
    const user = userEvent.setup()
    renderSection(project({ cloud_vision_detection_enabled: true }))

    // "Kein Bypass": keine kostenpflichtige Aktion ohne sichtbare Schaetzung.
    await waitFor(() => expect(screen.getByRole('button', TRIGGER)).toBeDisabled())

    await user.click(screen.getByRole('checkbox', CHECKBOX))

    // Ohne Cloud-Nutzung entstehen keine Kosten - die Schaetzung ist dann keine Vorbedingung.
    expect(screen.getByRole('button', TRIGGER)).toBeEnabled()
  })
})

describe('Teilschritt-Fortschritt', () => {
  it('names the remote sub-step and shows its progress numbers', () => {
    renderSection(
      project({
        cloud_vision_detection_enabled: true,
        last_criterion_scoring_run: classificationRun({
          phase: 'remote_categories',
          cloud_requested: true,
          photos_total: 0,
          photos_processed: 0,
        }),
        last_remote_category_classification_run: remoteRun({
          photos_total: 8,
          photos_processed: 3,
        }),
      })
    )

    expect(screen.getByText(/remote-kategorisierung läuft/i)).toBeInTheDocument()
    expect(screen.getByText(/3 von 8 fotos verarbeitet/i)).toBeInTheDocument()
    const progress = screen.getByRole('progressbar') as HTMLProgressElement
    expect(progress.max).toBe(8)
    expect(progress.value).toBe(3)
  })

  it('names the criteria sub-step and shows its own progress numbers', () => {
    renderSection(
      project({
        last_criterion_scoring_run: classificationRun({
          phase: 'criteria',
          photos_total: 10,
          photos_processed: 4,
        }),
        last_remote_category_classification_run: remoteRun({
          status: 'success',
          photos_total: 8,
          photos_processed: 8,
        }),
      })
    )

    expect(screen.getByText(/kriterien-bewertung läuft/i)).toBeInTheDocument()
    expect(screen.getByText(/4 von 10 fotos verarbeitet/i)).toBeInTheDocument()
  })

  it(
    'shows an indeterminate progress bar instead of an invalid max=0 during the brief ' +
      'photos_total=0 window right after the trigger',
    () => {
      renderSection(
        project({
          last_criterion_scoring_run: classificationRun({
            photos_total: 0,
            photos_processed: 0,
          }),
        })
      )

      const progress = screen.getByRole('progressbar') as HTMLProgressElement
      expect(progress.hasAttribute('value')).toBe(false)
      expect(progress.hasAttribute('max')).toBe(false)
    }
  )

  it('shows a success status once the run succeeded', async () => {
    renderSection(
      project({
        cloud_vision_detection_enabled: true,
        last_criterion_scoring_run: classificationRun({
          status: 'success',
          finished_at: '2026-07-20T10:07:00Z',
          phase: null,
          cloud_requested: true,
          photos_total: 10,
          photos_processed: 10,
        }),
      })
    )

    expect(screen.getByText('Erfolgreich klassifiziert')).toBeInTheDocument()
    // Der Ausloeser ist bei angewaehlter Cloud-Nutzung erst wieder bedienbar, sobald die
    // Schaetzung vorliegt ("kein Bypass") - deshalb hier abwarten statt synchron zu pruefen.
    await screen.findByTestId('classification-estimate')
    expect(screen.getByRole('button', TRIGGER)).toBeEnabled()
  })

  it('shows an inline error banner with a retry button on a failed run', async () => {
    vi.mocked(projectsApi.triggerClassification).mockResolvedValue({ status: 'queued' })
    const user = userEvent.setup()
    renderSection(
      project({
        last_criterion_scoring_run: classificationRun({
          status: 'failed',
          phase: null,
          error_message: 'Unerwarteter Fehler',
        }),
      })
    )

    expect(await screen.findByRole('alert')).toHaveTextContent('Unerwarteter Fehler')
    await user.click(screen.getByRole('button', { name: /erneut versuchen/i }))

    expect(projectsApi.triggerClassification).toHaveBeenCalledWith(1, 42, false)
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
      })
    )

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Remote-Kategorisierung fehlgeschlagen: Zeitüberschreitung')
    expect(alert).toHaveTextContent(/ohne \(vollständige\) cloud-anreicherung entstanden/i)
    // Der Lauf selbst ist erfolgreich - der lokale Bewertungsanteil lief vollstaendig durch.
    expect(screen.getByText('Erfolgreich klassifiziert')).toBeInTheDocument()
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
      })
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
      })
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
      /feinlabels konnten nicht geladen werden/i
    )
  })
})

// specs/features/0304-cloud-modell-je-anbieter-waehlbar.md, ADR 0059 Punkt 4: fuer das
// eingestellte Modell ist kein Preis hinterlegt - die Schaetzung weist das aus, statt einen
// falschen (oder gar keinen) Betrag zu zeigen.
describe('Kostenschätzung ohne hinterlegten Preis', () => {
  const withoutPrice = {
    candidate_count: 5,
    remote_category_candidate_count: 4,
    landmark_candidate_count: 1,
    provider: 'anthropic',
    model: 'ein-nie-bepreistes-modell',
    price_per_image_usd: null,
    estimated_cost_usd: null,
  }

  it('shows a hint instead of an amount, but keeps the photo count visible', async () => {
    vi.mocked(projectsApi.getClassificationEstimate).mockResolvedValue(withoutPrice)
    renderSection(project({ cloud_vision_detection_enabled: true }))

    const estimate = await screen.findByTestId('classification-estimate')

    expect(estimate).toHaveTextContent(/keine kostenangabe verfügbar/i)
    expect(estimate).toHaveTextContent(/kosten erzeugen/i)
    expect(estimate).toHaveTextContent('~5 Fotos')
    // Ein stilles "0,00 USD" waere die gefaehrlichste aller Anzeigen - es behauptete
    // Kostenfreiheit (Security-Muss-Kriterium der Spec).
    expect(estimate.textContent).not.toMatch(/\$|USD|NaN|undefined|null/)
  })

  it('keeps the start button usable when no price is known', async () => {
    vi.mocked(projectsApi.getClassificationEstimate).mockResolvedValue(withoutPrice)
    renderSection(project({ cloud_vision_detection_enabled: true }))

    await screen.findByTestId('classification-estimate')

    // Regressionsschutz: die Sperre haengt an der fehlenden SCHAETZUNG (Ladefehler), nicht am
    // fehlenden Betrag - ein Guard auf `estimated_cost_usd === null` machte das Produkt bei
    // einem reinen Preispflege-Versaeumnis unbenutzbar.
    expect(screen.getByRole('button', TRIGGER)).toBeEnabled()
  })

  it('prefers the "everything already classified" message over the missing-price hint', async () => {
    vi.mocked(projectsApi.getClassificationEstimate).mockResolvedValue({
      ...withoutPrice,
      candidate_count: 0,
      remote_category_candidate_count: 0,
      landmark_candidate_count: 0,
    })
    renderSection(project({ cloud_vision_detection_enabled: true }))

    expect(await screen.findByTestId('classification-estimate')).toHaveTextContent(
      /alle fotos bereits klassifiziert/i
    )
  })
})
