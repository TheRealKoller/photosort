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
  ProjectOut,
  ScanSummary,
  ScoringRunSummary,
} from '../api/types'
import { POLL_INTERVAL_MS } from '../hooks/useProjects'
import { ProjectDetailPage } from './ProjectDetailPage'

vi.mock('../api/projects')

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
    ...overrides,
  }
}

function scan(overrides: Partial<ScanSummary> = {}): ScanSummary {
  return {
    status: 'running',
    started_at: '2026-07-20T10:00:00Z',
    finished_at: null,
    files_found: 0,
    // specs/features/0036-scan-performance-zweiphasig-parallel.md: null = Enumerationsphase noch
    // nicht abgeschlossen (Default hier, wie beim frisch gestarteten Scan) - Tests fuer die
    // Verarbeitungsphase setzen total_files explizit.
    total_files: null,
    photos_added: 0,
    photos_updated: 0,
    photos_removed: 0,
    files_skipped: 0,
    error_message: null,
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

function criterionScoringRun(
  overrides: Partial<CriterionScoringRunSummary> = {}
): CriterionScoringRunSummary {
  return {
    status: 'running',
    started_at: '2026-07-20T10:00:00Z',
    finished_at: null,
    photos_total: 0,
    photos_processed: 0,
    error_message: null,
    ...overrides,
  }
}

function renderPage(initialPath = '/projects/1') {
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
          <Route path="/" element={<p>Projektliste-Seite</p>} />
          <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
        </Routes>
      </MemoryRouter>,
      { wrapper }
    ),
    queryClient,
  }
}

describe('ProjectDetailPage', () => {
  beforeEach(() => {
    vi.mocked(projectsApi.getProject).mockReset()
    vi.mocked(projectsApi.triggerScan).mockReset()
    vi.mocked(projectsApi.triggerScore).mockReset()
    vi.mocked(projectsApi.confirmAusschussGate).mockReset()
    vi.mocked(projectsApi.triggerScoreCriteria).mockReset()
  })

  it('shows a dedicated not-found state on a 404 instead of a broken page', async () => {
    vi.mocked(projectsApi.getProject).mockRejectedValue(new ApiError(404, 'Projekt nicht gefunden.'))

    renderPage()

    expect(await screen.findByText(/projekt nicht gefunden/i)).toBeInTheDocument()
  })

  it('shows project data and an active "Aktualisieren" button when never scanned', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(project({ last_scan: null }))

    renderPage()

    expect(await screen.findByText('Costa Rica')).toBeInTheDocument()
    expect(screen.getByText('CostaRica')).toBeInTheDocument()
    expect(screen.getByText(/noch nicht gescannt/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /aktualisieren/i })).toBeEnabled()
  })

  it('disables the button synchronously on click, before the response arrives', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(project({ last_scan: null }))
    let resolveTrigger: (value: { status: string }) => void = () => {}
    vi.mocked(projectsApi.triggerScan).mockReturnValue(
      new Promise((resolve) => {
        resolveTrigger = resolve
      })
    )
    const user = userEvent.setup()

    renderPage()
    const button = await screen.findByRole('button', { name: /aktualisieren/i })
    await user.click(button)

    expect(button).toBeDisabled()
    resolveTrigger({ status: 'queued' })
  })

  it('sends exactly one scan request on a rapid double click before the first response arrives', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(project({ last_scan: null }))
    vi.mocked(projectsApi.triggerScan).mockReturnValue(new Promise(() => {}))
    const user = userEvent.setup()

    renderPage()
    const button = await screen.findByRole('button', { name: /aktualisieren/i })
    await user.click(button)
    await user.click(button)

    expect(projectsApi.triggerScan).toHaveBeenCalledTimes(1)
  })

  it('re-enables the button and shows an error when the trigger request itself fails', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(project({ last_scan: null }))
    vi.mocked(projectsApi.triggerScan).mockRejectedValue(new ApiError(500, 'Serverfehler'))
    const user = userEvent.setup()

    renderPage()
    const button = await screen.findByRole('button', { name: /aktualisieren/i })
    await user.click(button)

    await waitFor(() => expect(button).toBeEnabled())
    expect(await screen.findByRole('alert')).toHaveTextContent('Serverfehler')
  })

  it('polls while running and stops exactly at the first success response, showing all counters', { timeout: 10000 }, async () => {
    vi.mocked(projectsApi.getProject)
      .mockResolvedValueOnce(project({ last_scan: null }))
      .mockResolvedValueOnce(project({ last_scan: scan({ status: 'running' }) }))
      .mockResolvedValue(
        project({
          last_scan: scan({
            status: 'success',
            finished_at: '2026-07-20T10:05:00Z',
            files_found: 12,
            photos_added: 10,
            photos_updated: 1,
            photos_removed: 0,
            files_skipped: 2,
          }),
        })
      )
    vi.mocked(projectsApi.triggerScan).mockResolvedValue({ status: 'queued' })
    const user = userEvent.setup()

    renderPage()
    const button = await screen.findByRole('button', { name: /aktualisieren/i })
    await user.click(button)

    await waitFor(() => expect(screen.getByRole('button', { name: /scan läuft/i })).toBeDisabled())

    await waitFor(() => expect(screen.getByText('10')).toBeInTheDocument(), { timeout: 8000 })
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getByText('1')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.getByText('0')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /aktualisieren/i })).toBeEnabled()
  })

  describe('Scan-Statistik: Layout und Hilfetext (specs/features/0030-scan-statistik-layout-und-hilfetext.md)', () => {
    function renderWithScan(overrides: Partial<ScanSummary> = {}) {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({
          last_scan: scan({
            status: 'success',
            finished_at: '2026-07-20T10:05:00Z',
            photos_added: 10,
            photos_updated: 1,
            photos_removed: 3,
            files_skipped: 2,
            files_found: 16,
            ...overrides,
          }),
        })
      )
      return renderPage()
    }

    it('groups each of the five label/value pairs in a shared parent element (layout fix)', async () => {
      renderWithScan()

      const pairs: Array<[string, string]> = [
        ['Hinzugefügt', '10'],
        ['Aktualisiert', '1'],
        ['Entfernt', '3'],
        ['Übersprungen', '2'],
        ['Dateien gefunden', '16'],
      ]

      for (const [label, value] of pairs) {
        const labelNode = await screen.findByText(label)
        const dt = labelNode.closest('dt')
        expect(dt).not.toBeNull()
        const dd = dt!.parentElement!.querySelector('dd')
        expect(dd).not.toBeNull()
        expect(dd).toHaveTextContent(value)
      }
    })

    it('renders "Entfernt" and "Übersprungen" as initially collapsed <details>/<summary> disclosures', async () => {
      renderWithScan()

      const removedDetails = (await screen.findByText('Entfernt')).closest('details')
      expect(removedDetails).not.toBeNull()
      expect(removedDetails).not.toHaveAttribute('open')

      const skippedDetails = (await screen.findByText('Übersprungen')).closest('details')
      expect(skippedDetails).not.toBeNull()
      expect(skippedDetails).not.toHaveAttribute('open')
    })

    it('toggles the "Entfernt" disclosure open and closed repeatedly on click', async () => {
      const user = userEvent.setup()
      renderWithScan()

      const summary = await screen.findByText('Entfernt')
      const details = summary.closest('details')!

      await user.click(summary)
      expect(details).toHaveAttribute('open')

      await user.click(summary)
      expect(details).not.toHaveAttribute('open')

      await user.click(summary)
      expect(details).toHaveAttribute('open')
    })

    it('shows the exact explanation text for "Entfernt" once expanded', async () => {
      const user = userEvent.setup()
      renderWithScan()

      await user.click(await screen.findByText('Entfernt'))

      expect(
        screen.getByText(
          'Datei wurde am Ursprungsort in OpenCloud nicht mehr gefunden und daher aus PhotoSort entfernt.'
        )
      ).toBeInTheDocument()
    })

    it('shows the exact explanation text for "Übersprungen" once expanded', async () => {
      const user = userEvent.setup()
      renderWithScan()

      await user.click(await screen.findByText('Übersprungen'))

      expect(
        screen.getByText('Dateiendung wird nicht unterstützt (unterstützt: JPG, PNG, HEIC, HEIF).')
      ).toBeInTheDocument()
    })

    it('toggles the two disclosures independently (no shared "name" accordion behavior)', async () => {
      const user = userEvent.setup()
      renderWithScan()

      const removedSummary = await screen.findByText('Entfernt')
      const skippedSummary = await screen.findByText('Übersprungen')
      const removedDetails = removedSummary.closest('details')!
      const skippedDetails = skippedSummary.closest('details')!

      await user.click(removedSummary)
      await user.click(skippedSummary)

      expect(removedDetails).toHaveAttribute('open')
      expect(skippedDetails).toHaveAttribute('open')
    })

    it('keeps both disclosures present and togglable even when their counters are 0', async () => {
      const user = userEvent.setup()
      renderWithScan({ photos_removed: 0, files_skipped: 0 })

      const removedDetails = (await screen.findByText('Entfernt')).closest('details')!
      const skippedDetails = (await screen.findByText('Übersprungen')).closest('details')!
      expect(removedDetails).not.toHaveAttribute('open')
      expect(skippedDetails).not.toHaveAttribute('open')

      await user.click(screen.getByText('Entfernt'))
      await user.click(screen.getByText('Übersprungen'))

      expect(removedDetails).toHaveAttribute('open')
      expect(skippedDetails).toHaveAttribute('open')
    })

    it('does not wrap the other three labels ("Hinzugefügt", "Aktualisiert", "Dateien gefunden") in a <details> ancestor', async () => {
      renderWithScan()

      for (const label of ['Hinzugefügt', 'Aktualisiert', 'Dateien gefunden']) {
        const labelNode = await screen.findByText(label)
        expect(labelNode.closest('details')).toBeNull()
      }
    })
  })

  describe('two-phase scan progress (specs/features/0022, 0036)', () => {
    it('shows "Dateien werden gezählt…" and an indeterminate progress bar during the enumeration phase (total_files === null)', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({ last_scan: scan({ status: 'running', total_files: null, files_found: 5 }) })
      )

      renderPage()

      const counterLine = await screen.findByText('Dateien werden gezählt…')
      const progress = screen.getByRole('progressbar') as HTMLProgressElement
      // Indeterminiert: kein value/max (Akzeptanzkriterium der Spec) - anders als bei der
      // frueheren, rein textuellen Rohzaehler-Anzeige gibt es jetzt zwar ein <progress>-Element,
      // aber ohne Nenner.
      expect(progress.hasAttribute('value')).toBe(false)
      expect(progress.hasAttribute('max')).toBe(false)

      const scanSection = counterLine.closest('section')
      expect(scanSection).not.toBeNull()
      expect(within(scanSection!).queryByText(/\bvon\b/i)).not.toBeInTheDocument()
    })

    it('shows no percent aria-live announcement during the enumeration phase - only the status line carries aria-live', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({ last_scan: scan({ status: 'running', total_files: null, files_found: 5 }) })
      )

      renderPage()

      const statusLine = await screen.findByText('Scan läuft…', { selector: 'p' })
      await screen.findByText('Dateien werden gezählt…')
      expect(statusLine).toHaveAttribute('aria-live', 'polite')
      expect(screen.queryByText(/%\s*verarbeitet/i)).not.toBeInTheDocument()

      const scanSection = statusLine.closest('section')
      expect(scanSection).not.toBeNull()
      expect(scanSection!.querySelectorAll('[aria-live]')).toHaveLength(1)
    })

    it('shows "X von Y Dateien verarbeitet" and a determinate progress bar during the processing phase (total_files known)', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({ last_scan: scan({ status: 'running', total_files: 12, files_found: 4 }) })
      )

      renderPage()

      expect(await screen.findByText('4 von 12 Dateien verarbeitet')).toBeInTheDocument()
      const progress = screen.getByRole('progressbar') as HTMLProgressElement
      expect(progress.max).toBe(12)
      expect(progress.value).toBe(4)
    })

    it('announces "0% verarbeitet" right at the start of the processing phase, before any file was processed', async () => {
      // ux-ui-designer-Review-Fund: dokumentiert explizit, dass die erste aria-live-Ansage beim
      // Eintritt in Phase 2 (files_found === 0) bereits "0%" lautet, statt bis zum ersten
      // Poll-Tick mit files_found > 0 stumm zu bleiben.
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({ last_scan: scan({ status: 'running', total_files: 10, files_found: 0 }) })
      )

      renderPage()

      const liveRegion = await screen.findByText('0% verarbeitet')
      expect(liveRegion).toHaveAttribute('aria-live', 'polite')
    })

    it('shows an indeterminate progress bar instead of an invalid max=0 for an empty project (total_files === 0)', async () => {
      // Sonderfall des Akzeptanzkriteriums: total_files === 0 ist bereits Phase 2 (Phase 1
      // abgeschlossen), nicht Phase 1 - der Text lautet also "0 von 0", aber <progress max={0}>
      // ist fuer native progress-Elemente ungueltig/mehrdeutig (identisches Muster wie beim
      // Scoring-Fortschritt, siehe Beschreibung "Ausschuss aussortieren" unten).
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({ last_scan: scan({ status: 'running', total_files: 0, files_found: 0 }) })
      )

      renderPage()

      expect(await screen.findByText('0 von 0 Dateien verarbeitet')).toBeInTheDocument()
      const progress = screen.getByRole('progressbar') as HTMLProgressElement
      expect(progress.hasAttribute('value')).toBe(false)
      expect(progress.hasAttribute('max')).toBe(false)
    })

    it('announces the percent value only during the processing phase, throttled to 10%-steps', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({ last_scan: scan({ status: 'running', total_files: 100, files_found: 34 }) })
      )

      renderPage()

      const liveRegion = await screen.findByText(/30% verarbeitet/i)
      expect(liveRegion).toHaveAttribute('aria-live', 'polite')
      // 34% wird NICHT direkt angesagt (kein "34%"-Text) - nur der gerundete 10%-Schritt.
      expect(screen.queryByText(/34% verarbeitet/i)).not.toBeInTheDocument()
    })

    it('grows monotonically across two consecutive polls during the processing phase', async () => {
      vi.mocked(projectsApi.getProject)
        .mockResolvedValueOnce(
          project({ last_scan: scan({ status: 'running', total_files: 10, files_found: 3 }) })
        )
        .mockResolvedValue(
          project({ last_scan: scan({ status: 'running', total_files: 10, files_found: 7 }) })
        )

      renderPage()

      expect(await screen.findByText('3 von 10 Dateien verarbeitet')).toBeInTheDocument()
      await waitFor(
        () => expect(screen.getByText('7 von 10 Dateien verarbeitet')).toBeInTheDocument(),
        { timeout: POLL_INTERVAL_MS + 1500 }
      )
      expect(screen.queryByText('3 von 10 Dateien verarbeitet')).not.toBeInTheDocument()
    })

    it('transitions from the enumeration to the processing phase across two polls', async () => {
      vi.mocked(projectsApi.getProject)
        .mockResolvedValueOnce(
          project({ last_scan: scan({ status: 'running', total_files: null, files_found: 9 }) })
        )
        .mockResolvedValue(
          project({ last_scan: scan({ status: 'running', total_files: 15, files_found: 0 }) })
        )

      renderPage()

      expect(await screen.findByText('Dateien werden gezählt…')).toBeInTheDocument()
      await waitFor(
        () => expect(screen.getByText('0 von 15 Dateien verarbeitet')).toBeInTheDocument(),
        { timeout: POLL_INTERVAL_MS + 1500 }
      )
      expect(screen.queryByText('Dateien werden gezählt…')).not.toBeInTheDocument()
    })

    it('removes the running progress block once the scan transitions to success, keeping the final "Dateien gefunden" stat', async () => {
      vi.mocked(projectsApi.getProject)
        .mockResolvedValueOnce(
          project({ last_scan: scan({ status: 'running', total_files: 12, files_found: 9 }) })
        )
        .mockResolvedValue(
          project({
            last_scan: scan({
              status: 'success',
              finished_at: '2026-07-20T10:05:00Z',
              files_found: 12,
              total_files: 12,
            }),
          })
        )

      renderPage()

      expect(await screen.findByText('9 von 12 Dateien verarbeitet')).toBeInTheDocument()
      await waitFor(
        () => expect(screen.getByText('Erfolgreich')).toBeInTheDocument(),
        { timeout: POLL_INTERVAL_MS + 1500 }
      )
      expect(screen.queryByText(/dateien verarbeitet/i)).not.toBeInTheDocument()
      expect(screen.queryByText('Dateien werden gezählt…')).not.toBeInTheDocument()
      expect(screen.getByText('Dateien gefunden').nextElementSibling).toHaveTextContent('12')
    })
  })

  it(
    'keeps the button disabled after a successful trigger response for a re-scan, until polling actually confirms "running"',
    { timeout: 10000 },
    async () => {
      // Regression fuer einen im Review gefundenen Bug: fuer ein Projekt, das schon einmal
      // gescannt wurde, ist last_scan VOR dem Klick bereits nicht-null (z.B. "failed" vom
      // vorherigen Lauf). Der Worker setzt status="running" erst asynchron
      // (backend/src/photosort/worker.py), nicht synchron mit der 202-Antwort - der
      // Invalidierungs-Refetch direkt nach dem Trigger kann also noch den ALTEN Status liefern.
      // Der Button darf trotzdem nicht vorzeitig wieder aktiv werden (specs/features/0005:
      // "bleibt es, bis entweder Polling running bestaetigt oder der Trigger selbst fehlschlaegt").
      const previousScan = scan({ status: 'failed', error_message: 'vorher fehlgeschlagen' })
      vi.mocked(projectsApi.getProject)
        .mockResolvedValueOnce(project({ last_scan: previousScan }))
        .mockResolvedValueOnce(project({ last_scan: previousScan }))
        .mockResolvedValue(project({ last_scan: scan({ status: 'running' }) }))
      vi.mocked(projectsApi.triggerScan).mockResolvedValue({ status: 'queued' })
      const user = userEvent.setup()

      renderPage()
      const button = await screen.findByRole('button', { name: /aktualisieren/i })
      await user.click(button)

      await waitFor(() => expect(projectsApi.getProject).toHaveBeenCalledTimes(2))
      // Der zweite (invalidierte) Fetch liefert noch immer "failed" - der Button muss trotzdem
      // deaktiviert bleiben, statt sich faelschlich zu reaktivieren.
      expect(screen.getByRole('button', { name: /scan läuft/i })).toBeDisabled()

      await waitFor(
        () => expect(screen.getByRole('button', { name: /scan läuft/i })).toBeDisabled(),
        { timeout: 8000 }
      )
      await waitFor(
        () =>
          expect(vi.mocked(projectsApi.getProject).mock.calls.length).toBeGreaterThanOrEqual(3),
        { timeout: 8000 }
      )
    }
  )

  it('shows the error message on a failed scan and re-enables the button immediately', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(
      project({
        last_scan: scan({
          status: 'failed',
          finished_at: '2026-07-20T10:01:00Z',
          error_message: 'OpenCloud nicht erreichbar',
        }),
      })
    )

    renderPage()

    expect(await screen.findByText('OpenCloud nicht erreichbar')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /aktualisieren/i })).toBeEnabled()
  })

  it('no longer renders its own "Zurück zur Projektliste" link in the generic (non-404) error state (specs/features/0033, AK7 - now covered by the sticky header/wordmark link)', async () => {
    vi.mocked(projectsApi.getProject).mockRejectedValue(new ApiError(500, 'Serverfehler'))

    renderPage()

    await screen.findByRole('alert')
    expect(screen.queryByRole('link', { name: /zurück/i })).not.toBeInTheDocument()
  })

  it('no longer renders its own "Zurück zur Projektliste" link on the not-found state (specs/features/0033, AK7 - now covered by the sticky header/wordmark link)', async () => {
    vi.mocked(projectsApi.getProject).mockRejectedValue(new ApiError(404, 'Projekt nicht gefunden.'))

    renderPage()

    await screen.findByText(/projekt nicht gefunden/i)
    expect(screen.queryByRole('link', { name: /zurück/i })).not.toBeInTheDocument()
  })

  it('no longer renders its own "Zurück zur Projektliste" link once loaded successfully (specs/features/0033, AK7 - now covered by the sticky header/wordmark link)', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(project())

    renderPage()

    await screen.findByText('Costa Rica')
    expect(screen.queryByRole('link', { name: /zurück/i })).not.toBeInTheDocument()
  })

  it('links to the photo grid and compare view of this project', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(project())

    renderPage()

    await screen.findByText('Costa Rica')
    expect(screen.getByRole('link', { name: /fotos ansehen/i })).toHaveAttribute(
      'href',
      '/projects/1/photos'
    )
    expect(screen.getByRole('link', { name: /vergleichen/i })).toHaveAttribute(
      'href',
      '/projects/1/compare'
    )
  })

  it(
    're-enables the button and stops polling when the scan status jumps directly to "success" without ever observing "running" (fast path, specs/features/0017)',
    { timeout: 10000 },
    async () => {
      // Regression fuer Spec 0017: laeuft der Job so schnell durch, dass der 2-Sekunden-Poll den
      // Zwischenzustand "running" nie beobachtet, sprang der Status bisher direkt auf "success",
      // ohne dass das interne awaitingConfirmation-Flag je zurueckgesetzt wurde - der Button blieb
      // dauerhaft im Busy-Zustand haengen und ein setInterval lief unbegrenzt weiter.
      vi.mocked(projectsApi.getProject)
        .mockResolvedValueOnce(project({ last_scan: null }))
        .mockResolvedValue(
          project({
            last_scan: scan({ status: 'success', finished_at: '2026-07-20T10:00:01Z' }),
          })
        )
      vi.mocked(projectsApi.triggerScan).mockResolvedValue({ status: 'queued' })
      const user = userEvent.setup()

      renderPage()
      const button = await screen.findByRole('button', { name: /aktualisieren/i })
      await user.click(button)

      await waitFor(() =>
        expect(screen.getByRole('button', { name: /aktualisieren/i })).toBeEnabled()
      )

      // Test-engineer-Review-Fund (Spec 0017): AC3 fordert einen Nachweis "ueber eine
      // Poll-Periode hinaus" - ein kurzer Wait unterhalb von POLL_INTERVAL_MS (2000ms) wuerde
      // einen tatsaechlich geleakten setInterval nicht zuverlaessig erkennen, da dessen naechster
      // Tick erst nach 2000ms faellig waere.
      const callsAfterConfirmation = vi.mocked(projectsApi.getProject).mock.calls.length
      await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS + 500))
      expect(vi.mocked(projectsApi.getProject).mock.calls.length).toBe(callsAfterConfirmation)
    }
  )

  it(
    're-enables the button and shows the error immediately when the scan status jumps directly to "failed" without ever observing "running" (fast path, specs/features/0017)',
    async () => {
      vi.mocked(projectsApi.getProject)
        .mockResolvedValueOnce(project({ last_scan: null }))
        .mockResolvedValue(
          project({
            last_scan: scan({ status: 'failed', error_message: 'Sehr schneller Fehler' }),
          })
        )
      vi.mocked(projectsApi.triggerScan).mockResolvedValue({ status: 'queued' })
      const user = userEvent.setup()

      renderPage()
      const button = await screen.findByRole('button', { name: /aktualisieren/i })
      await user.click(button)

      await waitFor(() =>
        expect(screen.getByRole('button', { name: /aktualisieren/i })).toBeEnabled()
      )
      expect(screen.getByText('Sehr schneller Fehler')).toBeInTheDocument()
    }
  )

  it('stops fetching after unmount while polling is active (no leaked interval)', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(
      project({ last_scan: scan({ status: 'running' }) })
    )

    const { unmount } = renderPage()
    await screen.findByText('Costa Rica')
    const callsBeforeUnmount = vi.mocked(projectsApi.getProject).mock.calls.length

    unmount()
    await new Promise((resolve) => setTimeout(resolve, 50))

    expect(vi.mocked(projectsApi.getProject).mock.calls.length).toBe(callsBeforeUnmount)
  })

  describe('Ausschuss aussortieren (scoring)', () => {
    it('shows an active trigger button and a hint when never scored', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(project({ last_scoring_run: null }))

      renderPage()

      expect(
        await screen.findByRole('button', { name: /ausschuss aussortieren/i })
      ).toBeEnabled()
      expect(screen.getByText(/noch nicht vorgeschlagen/i)).toBeInTheDocument()
    })

    it('disables the score button synchronously on click, before the response arrives', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(project({ last_scoring_run: null }))
      vi.mocked(projectsApi.triggerScore).mockReturnValue(new Promise(() => {}))
      const user = userEvent.setup()

      renderPage()
      const button = await screen.findByRole('button', {
        name: /ausschuss aussortieren/i,
      })
      await user.click(button)

      expect(button).toBeDisabled()
    })

    it('sends exactly one score request on a rapid double click', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(project({ last_scoring_run: null }))
      vi.mocked(projectsApi.triggerScore).mockReturnValue(new Promise(() => {}))
      const user = userEvent.setup()

      renderPage()
      const button = await screen.findByRole('button', {
        name: /ausschuss aussortieren/i,
      })
      await user.click(button)
      await user.click(button)

      expect(projectsApi.triggerScore).toHaveBeenCalledTimes(1)
    })

    it(
      'shows granular "X von Y" progress with a native progress element while running',
      { timeout: 10000 },
      async () => {
        vi.mocked(projectsApi.getProject)
          .mockResolvedValueOnce(project({ last_scoring_run: null }))
          .mockResolvedValue(
            project({ last_scoring_run: scoringRun({ photos_total: 10, photos_processed: 4 }) })
          )
        vi.mocked(projectsApi.triggerScore).mockResolvedValue({ status: 'queued' })
        const user = userEvent.setup()

        renderPage()
        const button = await screen.findByRole('button', {
          name: /ausschuss aussortieren/i,
        })
        await user.click(button)

        expect(await screen.findByText(/4 von 10 fotos verarbeitet/i)).toBeInTheDocument()
        const progress = screen.getByRole('progressbar') as HTMLProgressElement
        expect(progress.max).toBe(10)
        expect(progress.value).toBe(4)
      }
    )

    it('shows an indeterminate progress bar instead of an invalid max=0 during the brief photos_total=0 window', async () => {
      // Copilot-Review-Fund (PR #6): direkt nach dem Trigger ist last_scoring_run.status bereits
      // "running", aber photos_total kann noch kurz 0 sein (wird im Worker erst NACH dem Anlegen
      // des ScoringRun gesetzt, siehe backend/src/photosort/worker.py). <progress max={0}> ist
      // fuer native progress-Elemente ungueltig/mehrdeutig - stattdessen soll in diesem Fall ein
      // indeterminiertes <progress> (ohne value/max) gerendert werden.
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({ last_scoring_run: scoringRun({ photos_total: 0, photos_processed: 0 }) })
      )

      renderPage()

      const progress = (await screen.findByRole('progressbar')) as HTMLProgressElement
      expect(progress.hasAttribute('value')).toBe(false)
      expect(progress.hasAttribute('max')).toBe(false)
    })

    it('throttles the aria-live announcement to 10%-steps instead of every poll tick', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({ last_scoring_run: scoringRun({ photos_total: 100, photos_processed: 34 }) })
      )

      renderPage()

      const liveRegion = await screen.findByText(/30% verarbeitet/i)
      expect(liveRegion).toHaveAttribute('aria-live', 'polite')
      // 34% wird NICHT direkt angesagt (kein "34%"-Text) - nur der gerundete 10%-Schritt.
      expect(screen.queryByText(/34% verarbeitet/i)).not.toBeInTheDocument()
    })

    it('shows a summary with the plural suggestion count once scoring succeeded', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({
          last_scoring_run: scoringRun({
            status: 'success',
            finished_at: '2026-07-20T10:05:00Z',
            photos_total: 10,
            photos_processed: 10,
            suggestions_found: 3,
          }),
        })
      )

      renderPage()

      expect(await screen.findByText('3 Vorschläge gefunden')).toBeInTheDocument()
      expect(
        screen.getByRole('button', { name: /ausschuss aussortieren/i })
      ).toBeEnabled()
    })

    it('shows a singular suggestion count when exactly one suggestion was found', async () => {
      // Akzeptanzkriterium der Spec 0021: N=1 -> Singular "1 Vorschlag gefunden", nicht "1
      // Vorschläge gefunden".
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({
          last_scoring_run: scoringRun({
            status: 'success',
            finished_at: '2026-07-20T10:05:00Z',
            photos_total: 10,
            photos_processed: 10,
            suggestions_found: 1,
          }),
        })
      )

      renderPage()

      expect(await screen.findByText('1 Vorschlag gefunden')).toBeInTheDocument()
    })

    it('shows "0 Vorschläge gefunden" without an embellishing special-case text when nothing stood out', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({
          last_scoring_run: scoringRun({
            status: 'success',
            finished_at: '2026-07-20T10:05:00Z',
            photos_total: 10,
            photos_processed: 10,
            suggestions_found: 0,
          }),
        })
      )

      renderPage()

      expect(await screen.findByText('0 Vorschläge gefunden')).toBeInTheDocument()
    })

    it('shows a link to the suggested-filter photo view after a successful "Ausschuss aussortieren" run', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({
          last_scoring_run: scoringRun({
            status: 'success',
            finished_at: '2026-07-20T10:05:00Z',
            photos_total: 10,
            photos_processed: 10,
            suggestions_found: 3,
          }),
        })
      )

      renderPage()

      const link = await screen.findByRole('link', {
        name: 'Vorschläge aus der Ausschuss-Aussortierung ansehen',
      })
      expect(link).toHaveAttribute('href', '/projects/1/photos?filter=suggested')
      expect(link).toHaveTextContent('Vorschläge ansehen')
    })

    it('shows the suggested-filter link even when the run found zero suggestions', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({
          last_scoring_run: scoringRun({
            status: 'success',
            finished_at: '2026-07-20T10:05:00Z',
            photos_total: 10,
            photos_processed: 10,
            suggestions_found: 0,
          }),
        })
      )

      renderPage()

      await screen.findByText('0 Vorschläge gefunden')
      expect(
        screen.getByRole('link', { name: 'Vorschläge aus der Ausschuss-Aussortierung ansehen' })
      ).toBeInTheDocument()
    })

    it('announces completion/failure via aria-live, not just the granular running progress', async () => {
      // UI/UX-Review-Fund: die gedrosselte 10%-Ansage lag zuvor nur INNERHALB des
      // "running"-Blocks (der beim Abschluss unmountet) - ein Screenreader-Nutzer hoerte "10%...
      // 20%... 30%..." waehrend des Laufs, danach aber gar nichts mehr, wenn der Lauf fertig war
      // oder fehlschlug. Die aeussere Statuszeile braucht deshalb ebenfalls aria-live="polite",
      // analog zur bestehenden Scan-Statuszeile weiter oben in dieser Datei.
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({
          last_scoring_run: scoringRun({
            status: 'success',
            finished_at: '2026-07-20T10:05:00Z',
            photos_total: 10,
            photos_processed: 10,
            suggestions_found: 3,
          }),
        })
      )

      renderPage()

      const summary = await screen.findByText('3 Vorschläge gefunden')
      expect(summary).toHaveAttribute('aria-live', 'polite')
    })

    it('shows an inline error banner with a retry button on a failed scoring run, keeping suggestions usable', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({
          last_scoring_run: scoringRun({
            status: 'failed',
            error_message: 'Unerwarteter Fehler',
          }),
        })
      )

      renderPage()

      expect(await screen.findByRole('alert')).toHaveTextContent('Unerwarteter Fehler')
      expect(screen.getByRole('button', { name: /erneut versuchen/i })).toBeEnabled()
    })

    it('retries scoring when the "Erneut versuchen" button is clicked', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({ last_scoring_run: scoringRun({ status: 'failed' }) })
      )
      vi.mocked(projectsApi.triggerScore).mockResolvedValue({ status: 'queued' })
      const user = userEvent.setup()

      renderPage()
      const retryButton = await screen.findByRole('button', { name: /erneut versuchen/i })
      await user.click(retryButton)

      expect(projectsApi.triggerScore).toHaveBeenCalledWith(1)
    })

    it(
      're-enables the score button and stops polling when the scoring status jumps directly to "success" without ever observing "running" (fast path < 25 Fotos, specs/features/0017)',
      { timeout: 10000 },
      async () => {
        vi.mocked(projectsApi.getProject)
          .mockResolvedValueOnce(project({ last_scoring_run: null }))
          .mockResolvedValue(
            project({
              last_scoring_run: scoringRun({
                status: 'success',
                finished_at: '2026-07-20T10:00:01Z',
                photos_total: 10,
                photos_processed: 10,
              }),
            })
          )
        vi.mocked(projectsApi.triggerScore).mockResolvedValue({ status: 'queued' })
        const user = userEvent.setup()

        renderPage()
        const button = await screen.findByRole('button', {
          name: /ausschuss aussortieren/i,
        })
        await user.click(button)

        await waitFor(() =>
          expect(
            screen.getByRole('button', { name: /ausschuss aussortieren/i })
          ).toBeEnabled()
        )

        // Test-engineer-Review-Fund (Spec 0017): siehe analoger Kommentar beim Scan-Pendant
        // weiter oben in dieser Datei - Wait muss ueber POLL_INTERVAL_MS hinausgehen, um einen
        // tatsaechlichen Interval-Leak zuverlaessig zu erkennen.
        const callsAfterConfirmation = vi.mocked(projectsApi.getProject).mock.calls.length
        await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS + 500))
        expect(vi.mocked(projectsApi.getProject).mock.calls.length).toBe(callsAfterConfirmation)
      }
    )

    it(
      'shows the error alert with retry immediately when the scoring status jumps directly to "failed" without ever observing "running" (Nachweis, dass die entfernte !isScoreBusy-Gate-Bedingung die Anzeige nicht mehr verzoegert, specs/features/0017)',
      async () => {
        vi.mocked(projectsApi.getProject)
          .mockResolvedValueOnce(project({ last_scoring_run: null }))
          .mockResolvedValue(
            project({
              last_scoring_run: scoringRun({
                status: 'failed',
                error_message: 'Sehr schneller Scoring-Fehler',
              }),
            })
          )
        vi.mocked(projectsApi.triggerScore).mockResolvedValue({ status: 'queued' })
        const user = userEvent.setup()

        renderPage()
        const button = await screen.findByRole('button', {
          name: /ausschuss aussortieren/i,
        })
        await user.click(button)

        await waitFor(() =>
          expect(
            screen.getByRole('button', { name: /ausschuss aussortieren/i })
          ).toBeEnabled()
        )
        expect(await screen.findByRole('alert')).toHaveTextContent('Sehr schneller Scoring-Fehler')
        expect(screen.getByRole('button', { name: /erneut versuchen/i })).toBeEnabled()
      }
    )
  })

  it(
    'keeps the score button busy from its own independent awaitingScoreConfirmation state, unaffected by the scan status jumping directly to "success" (keine Cross-Contamination zwischen den beiden Hook-Instanzen, specs/features/0017)',
    async () => {
      vi.mocked(projectsApi.getProject)
        .mockResolvedValueOnce(project({ last_scan: null, last_scoring_run: null }))
        .mockResolvedValueOnce(
          project({ last_scan: scan({ status: 'success' }), last_scoring_run: null })
        )
        .mockResolvedValue(
          project({ last_scan: scan({ status: 'success' }), last_scoring_run: null })
        )
      vi.mocked(projectsApi.triggerScan).mockResolvedValue({ status: 'queued' })
      vi.mocked(projectsApi.triggerScore).mockResolvedValue({ status: 'queued' })
      const user = userEvent.setup()

      renderPage()
      const scanButton = await screen.findByRole('button', { name: /aktualisieren/i })
      await user.click(scanButton)
      await waitFor(() => expect(scanButton).toBeEnabled())

      const scoreButton = screen.getByRole('button', {
        name: /ausschuss aussortieren/i,
      })
      await user.click(scoreButton)
      await waitFor(() => expect(projectsApi.triggerScore).toHaveBeenCalledTimes(1))

      // Scoring beobachtet in diesem Test nie "running"/"success"/"failed" (last_scoring_run
      // bleibt dauerhaft null) - der Score-Button muss trotzdem busy bleiben, gesteuert nur durch
      // seine eigene awaitingScoreConfirmation-Instanz, unbeeinflusst davon, dass die Scan-Instanz
      // des Hooks ihr eigenes Flag bereits zurueckgesetzt hat.
      expect(scoreButton).toBeDisabled()
      await new Promise((resolve) => setTimeout(resolve, 100))
      expect(scoreButton).toBeDisabled()
    }
  )

  describe('Ausschuss-Gate (specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md)', () => {
    it('shows an explanatory text when the ausschuss detection has not succeeded yet', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({ last_scoring_run: scoringRun({ status: 'running' }) })
      )

      renderPage()

      expect(await screen.findByText(/sichte zuerst den ausschuss oben/i)).toBeInTheDocument()
    })

    it('shows "Ausstehend" and a link into the gate screen while unconfirmed', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({
          last_scoring_run: scoringRun({
            status: 'success',
            suggestions_found: 2,
            gate_confirmed_at: null,
          }),
        })
      )

      renderPage()

      expect(await screen.findByText('Ausstehend')).toBeInTheDocument()
      const link = screen.getByRole('link', { name: 'Ausschuss sichten' })
      expect(link).toHaveAttribute('href', '/projects/1/photos?filter=suggested&gate=1')
    })

    it('shows a persistent auto-confirmed status when no suggestions were found', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({
          last_scoring_run: scoringRun({
            status: 'success',
            suggestions_found: 0,
            gate_confirmed_at: '2026-07-20T10:05:00Z',
          }),
        })
      )

      renderPage()

      expect(
        await screen.findByText('Kein Ausschuss gefunden — automatisch bestätigt')
      ).toBeInTheDocument()
      expect(screen.queryByRole('link', { name: 'Ausschuss sichten' })).not.toBeInTheDocument()
    })

    it('shows the confirmation date once manually confirmed', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({
          last_scoring_run: scoringRun({
            status: 'success',
            suggestions_found: 3,
            gate_confirmed_at: '2026-07-20T10:05:00Z',
          }),
        })
      )

      renderPage()

      expect(await screen.findByText(/ausschuss gesichtet am/i)).toBeInTheDocument()
      expect(screen.queryByRole('link', { name: 'Ausschuss sichten' })).not.toBeInTheDocument()
    })
  })

  describe('Kriterien-Bewertung (ersetzt select-top, specs/features/0037)', () => {
    it('disables the button with an explanatory text when the feature flag is off', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({
          category_selection_enabled: false,
          last_scoring_run: scoringRun({
            status: 'success',
            gate_confirmed_at: '2026-07-20T10:05:00Z',
          }),
        })
      )

      renderPage()

      expect(await screen.findByText(/diese funktion ist derzeit nicht aktiviert/i)).toBeInTheDocument()
      expect(
        screen.getByRole('button', { name: 'Kriterien-Bewertung starten' })
      ).toBeDisabled()
    })

    it('disables the button with an explanatory text while the gate is unconfirmed', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({
          last_scoring_run: scoringRun({ status: 'success', gate_confirmed_at: null }),
        })
      )

      renderPage()

      expect(await screen.findByText(/bestätige zuerst den ausschuss oben/i)).toBeInTheDocument()
      expect(
        screen.getByRole('button', { name: 'Kriterien-Bewertung starten' })
      ).toBeDisabled()
    })

    it('enables the button once the gate is confirmed', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({
          last_scoring_run: scoringRun({
            status: 'success',
            gate_confirmed_at: '2026-07-20T10:05:00Z',
          }),
        })
      )

      renderPage()

      expect(
        await screen.findByRole('button', { name: 'Kriterien-Bewertung starten' })
      ).toBeEnabled()
    })

    it('sends the scoring_run_id of last_scoring_run when triggered', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({
          last_scoring_run: scoringRun({
            id: 42,
            status: 'success',
            gate_confirmed_at: '2026-07-20T10:05:00Z',
          }),
        })
      )
      vi.mocked(projectsApi.triggerScoreCriteria).mockReturnValue(new Promise(() => {}))
      const user = userEvent.setup()

      renderPage()
      await user.click(await screen.findByRole('button', { name: 'Kriterien-Bewertung starten' }))

      expect(projectsApi.triggerScoreCriteria).toHaveBeenCalledWith(1, 42)
    })

    it('disables the button synchronously on click, before the response arrives', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({
          last_scoring_run: scoringRun({
            status: 'success',
            gate_confirmed_at: '2026-07-20T10:05:00Z',
          }),
        })
      )
      vi.mocked(projectsApi.triggerScoreCriteria).mockReturnValue(new Promise(() => {}))
      const user = userEvent.setup()

      renderPage()
      const button = await screen.findByRole('button', { name: 'Kriterien-Bewertung starten' })
      await user.click(button)

      expect(button).toBeDisabled()
    })

    it('sends exactly one request on a rapid double click', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({
          last_scoring_run: scoringRun({
            status: 'success',
            gate_confirmed_at: '2026-07-20T10:05:00Z',
          }),
        })
      )
      vi.mocked(projectsApi.triggerScoreCriteria).mockReturnValue(new Promise(() => {}))
      const user = userEvent.setup()

      renderPage()
      const button = await screen.findByRole('button', { name: 'Kriterien-Bewertung starten' })
      await user.click(button)
      await user.click(button)

      expect(projectsApi.triggerScoreCriteria).toHaveBeenCalledTimes(1)
    })

    it(
      'shows granular "X von Y" progress with a native progress element while running',
      { timeout: 10000 },
      async () => {
        vi.mocked(projectsApi.getProject)
          .mockResolvedValueOnce(
            project({
              last_scoring_run: scoringRun({
                status: 'success',
                gate_confirmed_at: '2026-07-20T10:05:00Z',
              }),
              last_criterion_scoring_run: null,
            })
          )
          .mockResolvedValue(
            project({
              last_scoring_run: scoringRun({
                status: 'success',
                gate_confirmed_at: '2026-07-20T10:05:00Z',
              }),
              last_criterion_scoring_run: criterionScoringRun({
                photos_total: 10,
                photos_processed: 4,
              }),
            })
          )
        vi.mocked(projectsApi.triggerScoreCriteria).mockResolvedValue({ status: 'queued' })
        const user = userEvent.setup()

        renderPage()
        const button = await screen.findByRole('button', { name: 'Kriterien-Bewertung starten' })
        await user.click(button)

        expect(await screen.findByText(/4 von 10 fotos verarbeitet/i)).toBeInTheDocument()
        const progress = screen.getByRole('progressbar') as HTMLProgressElement
        expect(progress.max).toBe(10)
        expect(progress.value).toBe(4)
      }
    )

    it('throttles the aria-live announcement to 10%-steps instead of every poll tick', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({
          last_scoring_run: scoringRun({
            status: 'success',
            gate_confirmed_at: '2026-07-20T10:05:00Z',
          }),
          last_criterion_scoring_run: criterionScoringRun({
            photos_total: 100,
            photos_processed: 34,
          }),
        })
      )

      renderPage()

      const liveRegion = await screen.findByText(/30% verarbeitet/i)
      expect(liveRegion).toHaveAttribute('aria-live', 'polite')
      expect(screen.queryByText(/34% verarbeitet/i)).not.toBeInTheDocument()
    })

    it('shows an indeterminate progress bar during the brief photos_total=0 window', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({
          last_scoring_run: scoringRun({
            status: 'success',
            gate_confirmed_at: '2026-07-20T10:05:00Z',
          }),
          last_criterion_scoring_run: criterionScoringRun({
            photos_total: 0,
            photos_processed: 0,
          }),
        })
      )

      renderPage()

      const progress = (await screen.findByRole('progressbar')) as HTMLProgressElement
      expect(progress.hasAttribute('value')).toBe(false)
      expect(progress.hasAttribute('max')).toBe(false)
    })

    it('shows a success status once the run succeeded', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({
          last_scoring_run: scoringRun({
            status: 'success',
            gate_confirmed_at: '2026-07-20T10:05:00Z',
          }),
          last_criterion_scoring_run: criterionScoringRun({
            status: 'success',
            finished_at: '2026-07-20T10:05:00Z',
            photos_total: 10,
            photos_processed: 10,
          }),
        })
      )

      renderPage()

      expect(await screen.findByText('Erfolgreich bewertet')).toBeInTheDocument()
      expect(
        screen.getByRole('button', { name: 'Kriterien-Bewertung starten' })
      ).toBeEnabled()
    })

    it('shows an inline error banner with a retry button on a failed run', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({
          last_scoring_run: scoringRun({
            status: 'success',
            gate_confirmed_at: '2026-07-20T10:05:00Z',
          }),
          last_criterion_scoring_run: criterionScoringRun({
            status: 'failed',
            error_message: 'Unerwarteter Fehler',
          }),
        })
      )

      renderPage()

      expect(await screen.findByRole('alert')).toHaveTextContent('Unerwarteter Fehler')
      expect(screen.getByRole('button', { name: /erneut versuchen/i })).toBeEnabled()
    })

    it('retries the run when "Erneut versuchen" is clicked', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({
          last_scoring_run: scoringRun({
            id: 7,
            status: 'success',
            gate_confirmed_at: '2026-07-20T10:05:00Z',
          }),
          last_criterion_scoring_run: criterionScoringRun({ status: 'failed' }),
        })
      )
      vi.mocked(projectsApi.triggerScoreCriteria).mockResolvedValue({ status: 'queued' })
      const user = userEvent.setup()

      renderPage()
      const retryButton = await screen.findByRole('button', { name: /erneut versuchen/i })
      await user.click(retryButton)

      expect(projectsApi.triggerScoreCriteria).toHaveBeenCalledWith(1, 7)
    })
  })

  describe('Kategorie-Kuratierung (specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md)', () => {
    it('shows an explanatory text and a disabled button before criterion scoring succeeded', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({ last_criterion_scoring_run: null })
      )

      renderPage()

      expect(
        await screen.findByText(/führe zuerst die kriterien-bewertung oben aus/i)
      ).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Kuratierung öffnen' })).toBeDisabled()
      expect(
        screen.queryByRole('link', { name: 'Kuratierung öffnen' })
      ).not.toBeInTheDocument()
    })

    it('links to /curate with the default top-N of 3 once available', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({ last_criterion_scoring_run: criterionScoringRun({ status: 'success' }) })
      )

      renderPage()

      const link = await screen.findByRole('link', { name: 'Kuratierung öffnen' })
      expect(link).toHaveAttribute('href', '/projects/1/curate?topN=3')
      const input = screen.getByLabelText(/top-fotos pro kategorie/i) as HTMLInputElement
      expect(input.value).toBe('3')
    })

    it('reflects a typed top-N value in the curate link', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({ last_criterion_scoring_run: criterionScoringRun({ status: 'success' }) })
      )
      const user = userEvent.setup()

      renderPage()
      const input = await screen.findByLabelText(/top-fotos pro kategorie/i)
      await user.clear(input)
      await user.type(input, '5')

      expect(screen.getByRole('link', { name: 'Kuratierung öffnen' })).toHaveAttribute(
        'href',
        '/projects/1/curate?topN=5'
      )
    })

    it('clamps a typed value above the 1-10 range instead of forwarding it as-is', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({ last_criterion_scoring_run: criterionScoringRun({ status: 'success' }) })
      )
      const user = userEvent.setup()

      renderPage()
      const input = await screen.findByLabelText(/top-fotos pro kategorie/i)
      await user.clear(input)
      await user.type(input, '20')

      expect(screen.getByRole('link', { name: 'Kuratierung öffnen' })).toHaveAttribute(
        'href',
        '/projects/1/curate?topN=10'
      )
    })

    it('keeps the previous valid value instead of falling through to 0 when the field is cleared', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({ last_criterion_scoring_run: criterionScoringRun({ status: 'success' }) })
      )
      const user = userEvent.setup()

      renderPage()
      const input = (await screen.findByLabelText(
        /top-fotos pro kategorie/i
      )) as HTMLInputElement
      await user.clear(input)

      expect(screen.getByRole('link', { name: 'Kuratierung öffnen' })).toHaveAttribute(
        'href',
        '/projects/1/curate?topN=3'
      )
    })
  })
})
