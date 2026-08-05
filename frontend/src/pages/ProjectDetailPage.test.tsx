import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as projectsApi from '../api/projects'
import type { ProjectOut, ScanSummary, ScoringRunSummary } from '../api/types'
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
    ...overrides,
  }
}

function scan(overrides: Partial<ScanSummary> = {}): ScanSummary {
  return {
    status: 'running',
    started_at: '2026-07-20T10:00:00Z',
    finished_at: null,
    files_found: 0,
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

  it('has a back link to the project list even in the generic (non-404) error state', async () => {
    vi.mocked(projectsApi.getProject).mockRejectedValue(new ApiError(500, 'Serverfehler'))

    renderPage()

    await screen.findByRole('alert')
    expect(screen.getByRole('link', { name: /zurück/i })).toHaveAttribute('href', '/')
  })

  it('has a back link to the project list', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(project())

    renderPage()

    await screen.findByText('Costa Rica')
    expect(screen.getByRole('link', { name: /zurück/i })).toHaveAttribute('href', '/')
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

      const callsAfterConfirmation = vi.mocked(projectsApi.getProject).mock.calls.length
      await new Promise((resolve) => setTimeout(resolve, 100))
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

  describe('Beste Fotos automatisch vorschlagen (scoring)', () => {
    it('shows an active trigger button and a hint when never scored', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(project({ last_scoring_run: null }))

      renderPage()

      expect(
        await screen.findByRole('button', { name: /beste fotos automatisch vorschlagen/i })
      ).toBeEnabled()
      expect(screen.getByText(/noch nicht vorgeschlagen/i)).toBeInTheDocument()
    })

    it('disables the score button synchronously on click, before the response arrives', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(project({ last_scoring_run: null }))
      vi.mocked(projectsApi.triggerScore).mockReturnValue(new Promise(() => {}))
      const user = userEvent.setup()

      renderPage()
      const button = await screen.findByRole('button', {
        name: /beste fotos automatisch vorschlagen/i,
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
        name: /beste fotos automatisch vorschlagen/i,
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
          name: /beste fotos automatisch vorschlagen/i,
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

    it('shows a summary once scoring succeeded', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(
        project({
          last_scoring_run: scoringRun({
            status: 'success',
            finished_at: '2026-07-20T10:05:00Z',
            photos_total: 10,
            photos_processed: 10,
          }),
        })
      )

      renderPage()

      expect(await screen.findByText(/vorschläge aktualisiert/i)).toBeInTheDocument()
      expect(
        screen.getByRole('button', { name: /beste fotos automatisch vorschlagen/i })
      ).toBeEnabled()
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
          }),
        })
      )

      renderPage()

      const summary = await screen.findByText(/vorschläge aktualisiert/i)
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
          name: /beste fotos automatisch vorschlagen/i,
        })
        await user.click(button)

        await waitFor(() =>
          expect(
            screen.getByRole('button', { name: /beste fotos automatisch vorschlagen/i })
          ).toBeEnabled()
        )

        const callsAfterConfirmation = vi.mocked(projectsApi.getProject).mock.calls.length
        await new Promise((resolve) => setTimeout(resolve, 100))
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
          name: /beste fotos automatisch vorschlagen/i,
        })
        await user.click(button)

        await waitFor(() =>
          expect(
            screen.getByRole('button', { name: /beste fotos automatisch vorschlagen/i })
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
        name: /beste fotos automatisch vorschlagen/i,
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
})
