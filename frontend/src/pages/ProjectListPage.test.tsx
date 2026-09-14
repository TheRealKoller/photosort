import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as projectsApi from '../api/projects'
import { ApiError } from '../api/client'
import type { ProjectOut } from '../api/types'
import { ProjectListPage } from './ProjectListPage'

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

/** Ein gescanntes Projekt mit Bestand - der Normalfall der Uebersicht. */
function scannedProject(overrides: Partial<ProjectOut> = {}): ProjectOut {
  return project({
    last_scan: { status: 'success' } as ProjectOut['last_scan'],
    photo_count: 1284,
    taken_at_earliest: '2019-04-02T10:12:00',
    taken_at_latest: '2019-08-17T14:30:00',
    ...overrides,
  })
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="/" element={<ProjectListPage />} />
        <Route path="/projects/new" element={<p>Neues Projekt Seite</p>} />
        <Route path="/projects/:id" element={<p>Projekt-Detail-Seite</p>} />
      </Routes>
    </MemoryRouter>,
    { wrapper },
  )
}

describe('ProjectListPage', () => {
  beforeEach(() => {
    vi.mocked(projectsApi.listProjects).mockReset()
  })

  /*
   * Akzeptanzkriterium D1: die vier Zustaende schliessen einander aus, und der Kopfbereich mit
   * "Neues Projekt anlegen" ist in ALLEN vieren bedienbar - ein Projekt anlegen zu koennen haengt
   * nicht daran, ob die Liste laedt oder scheitert. Nur die Zaehlzeile entfaellt, solange keine
   * Zahl bekannt ist.
   */
  describe('die vier Zustaende', () => {
    it('zeigt im Ladezustand weder Leerzustand noch Karte', async () => {
      vi.mocked(projectsApi.listProjects).mockReturnValue(new Promise(() => {}))

      renderPage()

      expect(await screen.findByRole('status')).toBeInTheDocument()
      expect(screen.queryByText(/noch nichts sortiert/i)).not.toBeInTheDocument()
      expect(screen.queryByTestId(/project-stand-/)).not.toBeInTheDocument()
      expect(screen.queryByText(/^\d+ Projekte?$/)).not.toBeInTheDocument()
    })

    it('zeigt im Fehlerzustand weder Leerzustand noch Karte noch Zaehlzeile', async () => {
      vi.mocked(projectsApi.listProjects).mockRejectedValue(new ApiError(500, 'Serverfehler'))

      renderPage()

      await screen.findByRole('alert')
      expect(screen.queryByText(/noch nichts sortiert/i)).not.toBeInTheDocument()
      expect(screen.queryByTestId(/project-stand-/)).not.toBeInTheDocument()
      expect(screen.queryByRole('status')).not.toBeInTheDocument()
    })

    it('zeigt im Leerzustand keine Zaehlzeile', async () => {
      vi.mocked(projectsApi.listProjects).mockResolvedValue([])

      renderPage()

      expect(await screen.findByText(/noch nichts sortiert/i)).toBeInTheDocument()
      expect(screen.queryByText(/^\d+ Projekte?$/)).not.toBeInTheDocument()
    })

    it('benennt die Zaehlzeile nach dem, was in der Liste steht', async () => {
      vi.mocked(projectsApi.listProjects).mockResolvedValue([
        scannedProject({ id: 1 }),
        scannedProject({ id: 2, name: 'Island', opencloud_path: 'Island' }),
      ])

      renderPage()

      expect(await screen.findByText('2 Projekte')).toBeInTheDocument()
    })

    it.each([
      ['ladend', () => vi.mocked(projectsApi.listProjects).mockReturnValue(new Promise(() => {}))],
      [
        'fehler',
        () =>
          vi.mocked(projectsApi.listProjects).mockRejectedValue(new ApiError(500, 'Serverfehler')),
      ],
      ['leer', () => vi.mocked(projectsApi.listProjects).mockResolvedValue([])],
      ['gefuellt', () => vi.mocked(projectsApi.listProjects).mockResolvedValue([scannedProject()])],
    ])('haelt den Kopfbereich im Zustand %s bedienbar', async (_name, arrange) => {
      arrange()

      renderPage()

      expect(
        await screen.findByRole('link', { name: /neues projekt anlegen/i }),
      ).toBeInTheDocument()
    })
  })

  /* Akzeptanzkriterium D2 - Waechter gegen den Verlust beim Umbau auf das Raster. */
  describe('der Ladezustand', () => {
    it('ist fuer Screenreader erkennbar und seine Platzhalter sind es nicht', async () => {
      vi.mocked(projectsApi.listProjects).mockReturnValue(new Promise(() => {}))

      renderPage()

      const region = await screen.findByRole('status')
      expect(region).toHaveAccessibleName(/geladen/i)
      const placeholders = within(region).getAllByRole('listitem', { hidden: true })
      expect(placeholders.length).toBeGreaterThan(0)
      for (const placeholder of placeholders) {
        expect(placeholder).toHaveAttribute('aria-hidden', 'true')
      }
    })
  })

  /* Akzeptanzkriterium X1 und Sicherheitsauflage S4: der Beitext ist der woertliche `detail`. */
  describe('der Fehlerzustand', () => {
    it('traegt einen kuratierten Titel und den woertlichen Servertext als Beitext', async () => {
      vi.mocked(projectsApi.listProjects).mockRejectedValue(
        new ApiError(500, 'Unerwarteter Fehler (500)'),
      )

      renderPage()

      const alert = await screen.findByRole('alert')
      expect(alert).toHaveTextContent('Projekte konnten nicht geladen werden')
      expect(alert).toHaveTextContent('Unerwarteter Fehler (500)')
      expect(alert).not.toHaveTextContent(/^Fehler$/)
    })

    it('laesst die Liste erneut laden', async () => {
      vi.mocked(projectsApi.listProjects)
        .mockRejectedValueOnce(new ApiError(500, 'Serverfehler'))
        .mockResolvedValueOnce([scannedProject()])
      const user = userEvent.setup()

      renderPage()

      await screen.findByRole('alert')
      await user.click(screen.getByRole('button', { name: /erneut versuchen/i }))

      expect(await screen.findByText('Costa Rica')).toBeInTheDocument()
    })
  })

  /*
   * Akzeptanzkriterien A1/A2/A3: drei einzeln lokalisierbare Textbereiche je Karte, jeder mit
   * seiner Wortmarke BEI SICH. Es gibt keine Spaltenkopfzeile, aus der ein Wert seine Bedeutung
   * bezoege - und damit keinen Text, den es nur in einer Breite gibt.
   */
  describe('die drei Angaben je Karte', () => {
    it('zeigt Name, Pfad, Fotoanzahl, Zeitraum und Stand', async () => {
      vi.mocked(projectsApi.listProjects).mockResolvedValue([scannedProject({ id: 4 })])

      renderPage()

      expect(await screen.findByText('Costa Rica')).toBeInTheDocument()
      expect(screen.getByText('CostaRica')).toBeInTheDocument()
      expect(screen.getByTestId('project-photo-count-4')).toHaveTextContent('1.284 Fotos')
      expect(screen.getByTestId('project-taken-at-4')).toHaveTextContent(
        'Aufnahmen 02.04.2019 – 17.08.2019',
      )
      expect(screen.getByTestId('project-stand-4')).toHaveTextContent('Weiter: Ausschuss-Erkennung')
    })

    it('zeigt "0 Fotos" neben "Aufnahmen —" am ungescannten Projekt', async () => {
      // `0` ist eine Aussage, der Strich die Abwesenheit einer Aussage - nie das eine fuer das
      // andere, und die Karte zeigt hier beides nebeneinander.
      vi.mocked(projectsApi.listProjects).mockResolvedValue([project({ id: 5 })])

      renderPage()

      expect(await screen.findByTestId('project-photo-count-5')).toHaveTextContent('0 Fotos')
      expect(screen.getByTestId('project-taken-at-5')).toHaveTextContent('Aufnahmen —')
      expect(screen.getByTestId('project-stand-5')).toHaveTextContent('Noch nicht gescannt')
    })

    it.each([
      [999, '999 Fotos'],
      [1000, '1.000 Fotos'],
    ])('setzt bei %s den deutschen Tausenderpunkt richtig', async (count, expected) => {
      vi.mocked(projectsApi.listProjects).mockResolvedValue([
        scannedProject({ id: 3, photo_count: count }),
      ])

      renderPage()

      expect(await screen.findByTestId('project-photo-count-3')).toHaveTextContent(expected)
    })

    it('nennt einen eintaegigen Zeitraum nur einmal', async () => {
      vi.mocked(projectsApi.listProjects).mockResolvedValue([
        scannedProject({
          id: 3,
          taken_at_earliest: '2019-04-02T09:15:00',
          taken_at_latest: '2019-04-02T18:44:00',
        }),
      ])

      renderPage()

      expect(await screen.findByTestId('project-taken-at-3')).toHaveTextContent(
        'Aufnahmen 02.04.2019',
      )
    })

    /*
     * Akzeptanzkriterium A5: laufende und fehlgeschlagene Laeufe behalten ihre Kennzeichen-Optik.
     * Zugesichert wird der SEMANTISCHE Haken, nicht die CSS-Klasse.
     */
    it('behaelt am laufenden Lauf Kennzeichen und Ringindikator', async () => {
      vi.mocked(projectsApi.listProjects).mockResolvedValue([
        project({ id: 6, last_scan: { status: 'running' } as ProjectOut['last_scan'] }),
      ])

      renderPage()

      const stand = await screen.findByTestId('project-stand-6')
      expect(within(stand).getByText('Scan läuft…')).toHaveAttribute('data-status', 'running')
      expect(within(stand).getByTestId('status-tag-spinner')).toBeInTheDocument()
    })

    it('behaelt am fehlgeschlagenen Lauf das Kennzeichen', async () => {
      vi.mocked(projectsApi.listProjects).mockResolvedValue([
        project({ id: 7, last_scan: { status: 'failed' } as ProjectOut['last_scan'] }),
      ])

      renderPage()

      const stand = await screen.findByTestId('project-stand-7')
      expect(within(stand).getByText('Scan fehlgeschlagen')).toHaveAttribute(
        'data-status',
        'failed',
      )
    })
  })

  /*
   * Akzeptanzkriterium D3, jsdom-Haelfte: EIN DOM-Baum, kein zweiter Zweig. Die Geometrie der
   * gemeinsamen vertikalen Flucht ist in jsdom nicht pruefbar und wird im Browser gemessen
   * (e2e/tests/projektuebersicht-raster.spec.ts).
   */
  describe('ein DOM-Baum fuer beide Breiten', () => {
    it('haelt jeden Text genau einmal im DOM - kein hidden/lg:hidden-Zwilling', async () => {
      vi.mocked(projectsApi.listProjects).mockResolvedValue([scannedProject({ id: 8 })])

      renderPage()

      await screen.findByText('Costa Rica')
      for (const text of ['Costa Rica', 'CostaRica']) {
        expect(screen.getAllByText(text)).toHaveLength(1)
      }
      for (const testId of ['project-photo-count-8', 'project-taken-at-8', 'project-stand-8']) {
        expect(screen.getAllByTestId(testId)).toHaveLength(1)
      }
    })
  })

  describe('die Zeile als Trefferflaeche', () => {
    it('fuehrt mit einem Klick auf die Detailseite', async () => {
      vi.mocked(projectsApi.listProjects).mockResolvedValue([scannedProject()])
      const user = userEvent.setup()

      renderPage()

      await user.click(await screen.findByRole('link', { name: /costa rica/i }))

      expect(await screen.findByText('Projekt-Detail-Seite')).toBeInTheDocument()
    })

    it('spannt je Karte GENAU EINEN Link auf, nicht mehrere nebeneinander', async () => {
      vi.mocked(projectsApi.listProjects).mockResolvedValue([scannedProject({ id: 9 })])

      renderPage()

      const card = (await screen.findByTestId('project-stand-9')).closest('li')
      expect(card).not.toBeNull()
      expect(within(card as HTMLElement).getAllByRole('link')).toHaveLength(1)
    })
  })

  /* Akzeptanzkriterium D4: der vollstaendige Name steht als Textknoten im DOM. Dass er umbricht
   * statt zu ueberlaufen, ist Geometrie und wird im Browser gemessen. */
  it('kuerzt den Projektnamen nicht', async () => {
    const longName = 'Sommerurlaub Costa Rica und Nicaragua mit den Grosseltern 2019'
    vi.mocked(projectsApi.listProjects).mockResolvedValue([scannedProject({ name: longName })])

    renderPage()

    expect(await screen.findByText(longName)).toBeInTheDocument()
  })
})
