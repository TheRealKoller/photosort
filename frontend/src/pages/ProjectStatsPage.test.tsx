import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as projectsApi from '../api/projects'
import type { ProjectStatsOut } from '../api/types'
import { ProjectStatsPage } from './ProjectStatsPage'

vi.mock('../api/projects')

// specs/features/0207-projekt-statistikseite.md: reine Anzeigeseite, eine Momentaufnahme ohne
// Bedienelemente. Die Negativ-Assertions am Ende sind so wichtig wie die positiven - die Spec
// grenzt die Seite ausdruecklich gegen Filter, Sortierung, Export und Ausloeser ab.

const CATEGORY_KEYS = [
  'menschen',
  'tier',
  'pflanze',
  'landschaft',
  'gebaeude_bauwerk',
  'innenraum',
  'essen_trinken',
  'fahrzeug',
  'gegenstand',
  'dokument_screenshot',
  'kunst_kreatives',
  'sport_aktivitaet',
  'nicht_erkannt',
]

function emptyStats(): ProjectStatsOut {
  return {
    photo_count: 0,
    storage: { opencloud_bytes: 0, local_cache_bytes: 0, local_database_bytes_estimate: null },
    taken_at_earliest: null,
    taken_at_latest: null,
    categories: {
      classified_photo_count: 0,
      unclassified_photo_count: 0,
      entries: CATEGORY_KEYS.map((key) => ({
        category_key: key,
        display_name: `Server-Name ${key}`,
        photo_count: 0,
        share: 0,
      })),
    },
    manual_category_override_count: 0,
    cost: {
      currency: 'USD',
      total_usd: 0,
      by_purpose: [
        { purpose: 'landmark', cost_usd: 0, has_unrecorded_runs: false },
        { purpose: 'remote_category', cost_usd: 0, has_unrecorded_runs: false },
      ],
    },
    progress: {
      scanned: 0,
      thumbnails_ready: 0,
      ausschuss_scored: 0,
      ranked: 0,
      remote_classified: 0,
    },
    ratings: { favorite: 0, album_worthy: 0, rejected: 0, unrated: 0 },
    last_successful_runs: {
      scan: null,
      scoring: null,
      classification: null,
      remote_category_classification: null,
    },
    diagnostics: {
      last_scan_files_skipped: null,
      duplicate_photo_count: 0,
      remote_failures: [
        { purpose: 'landmark', photo_count: 0 },
        { purpose: 'remote_category', photo_count: 0 },
      ],
    },
  }
}

function fullStats(): ProjectStatsOut {
  const base = emptyStats()
  return {
    ...base,
    photo_count: 12043,
    storage: {
      opencloud_bytes: Math.round(2.3 * 1024 ** 3),
      local_cache_bytes: Math.round(120 * 1024 ** 2),
      local_database_bytes_estimate: Math.round(40 * 1024 ** 2),
    },
    taken_at_earliest: '2019-04-02T10:12:00',
    taken_at_latest: '2019-04-19T18:44:00',
    categories: {
      classified_photo_count: 9800,
      unclassified_photo_count: 2243,
      entries: base.categories.entries.map((entry) =>
        entry.category_key === 'landschaft'
          ? { ...entry, photo_count: 9800, share: 1 }
          : entry
      ),
    },
    manual_category_override_count: 37,
    cost: {
      currency: 'USD',
      total_usd: 42.13,
      by_purpose: [
        { purpose: 'landmark', cost_usd: 12.1, has_unrecorded_runs: true },
        { purpose: 'remote_category', cost_usd: 30.03, has_unrecorded_runs: false },
      ],
    },
    progress: {
      scanned: 12043,
      thumbnails_ready: 12040,
      ausschuss_scored: 12043,
      ranked: 9800,
      remote_classified: 9800,
    },
    ratings: { favorite: 210, album_worthy: 430, rejected: 1200, unrated: 10203 },
    last_successful_runs: {
      scan: '2026-08-01T10:00:00',
      scoring: '2026-08-01T11:00:00',
      classification: '2026-08-01T12:00:00',
      remote_category_classification: null,
    },
    diagnostics: {
      last_scan_files_skipped: 12,
      duplicate_photo_count: 341,
      remote_failures: [
        { purpose: 'landmark', photo_count: 3 },
        { purpose: 'remote_category', photo_count: 1 },
      ],
    },
  }
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/projects/1/stats']}>
        <Routes>
          <Route path="/projects/:projectId/stats" element={<ProjectStatsPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('ProjectStatsPage', () => {
  beforeEach(() => {
    vi.mocked(projectsApi.getProjectStats).mockReset()
  })

  describe('Zustaende', () => {
    it('zeigt einen Ladezustand, solange die Statistik geladen wird', () => {
      vi.mocked(projectsApi.getProjectStats).mockReturnValue(new Promise(() => {}))

      renderPage()

      expect(screen.getByRole('status')).toBeInTheDocument()
    })

    it('zeigt bei einem unbekannten Projekt nur einen Kurztext, keine Statistikbloecke', async () => {
      vi.mocked(projectsApi.getProjectStats).mockRejectedValue(
        new ApiError(404, 'Projekt nicht gefunden.')
      )

      renderPage()

      expect(await screen.findByText('Projekt nicht gefunden.')).toBeInTheDocument()
      expect(screen.queryByRole('table')).not.toBeInTheDocument()
    })

    it('zeigt die Server-Fehlermeldung woertlich in einem Alert', async () => {
      vi.mocked(projectsApi.getProjectStats).mockRejectedValue(
        new ApiError(500, 'Interner Serverfehler beim Aggregieren.')
      )

      renderPage()

      expect(
        await screen.findByText('Interner Serverfehler beim Aggregieren.')
      ).toBeInTheDocument()
    })
  })

  describe('leeres Projekt', () => {
    beforeEach(() => {
      vi.mocked(projectsApi.getProjectStats).mockResolvedValue(emptyStats())
    })

    it('rendert die Seite vollstaendig mit Nullwerten, ohne NaN oder Infinity', async () => {
      const { container } = renderPage()

      expect(await screen.findByRole('heading', { name: 'Statistik' })).toBeInTheDocument()
      expect(container.textContent).not.toMatch(/NaN|Infinity|undefined|null/)
    })

    it('stellt 0 Bytes als "0 MB" dar, nicht als Strich', async () => {
      renderPage()

      const scope = await screen.findByRole('region', { name: 'Umfang und Speicher' })
      expect(within(scope).getAllByText('0 MB').length).toBeGreaterThan(0)
    })

    it('zeigt einen leeren Aufnahmezeitraum mit Erlaeuterung', async () => {
      renderPage()

      expect(await screen.findByText('Noch keine Fotos im Projekt.')).toBeInTheDocument()
    })

    it('zeigt "noch nie gelaufen" statt eines Zeitpunkts', async () => {
      renderPage()

      expect((await screen.findAllByText('noch nie gelaufen')).length).toBe(4)
    })

    it('zeigt "noch nie gescannt" statt 0 uebersprungener Dateien', async () => {
      renderPage()

      expect(await screen.findByText('noch nie gescannt')).toBeInTheDocument()
    })

    it('listet trotzdem alle Kategorien mit 0 und Anteil 0 %', async () => {
      renderPage()

      const table = await screen.findByRole('table')
      const rows = within(table).getAllByRole('row').slice(1)
      expect(rows).toHaveLength(CATEGORY_KEYS.length)
      expect(within(table).getAllByText('0 %')).toHaveLength(CATEGORY_KEYS.length)
    })

    it('zeigt eine Kostensumme von 0,00 USD ohne Unvollstaendigkeits-Hinweis', async () => {
      renderPage()

      const scope = await screen.findByRole('region', { name: 'Kosten für Remote-Berechnungen' })
      expect(within(scope).getAllByText('0,00 USD').length).toBeGreaterThan(0)
      expect(within(scope).queryByText('Summe unvollständig erfasst')).not.toBeInTheDocument()
    })
  })

  describe('gefuelltes Projekt', () => {
    beforeEach(() => {
      vi.mocked(projectsApi.getProjectStats).mockResolvedValue(fullStats())
    })

    it('zeigt Fotoanzahl und Speicherwerte im deutschen Format', async () => {
      renderPage()

      expect(await screen.findByText('12.043')).toBeInTheDocument()
      expect(screen.getByText('2,3 GB')).toBeInTheDocument()
      // Der lokale Gesamtwert ist die Summe der beiden bekannten Anteile (120 MB Cache + 40 MB
      // geschaetzter Datenbank-Anteil); die Anteile selbst stehen kleiner darunter.
      expect(screen.getByText('160,0 MB')).toBeInTheDocument()
    })

    it('beschriftet die beiden Speicherwerte unterschiedlich und woertlich', async () => {
      renderPage()

      expect(await screen.findByText('Originaldateien in OpenCloud')).toBeInTheDocument()
      expect(
        screen.getByText('Lokal belegt (Thumbnail-Cache + Datenbestand)')
      ).toBeInTheDocument()
    })

    it('weist den geschaetzten Datenbank-Anteil getrennt vom Cache aus', async () => {
      renderPage()

      const scope = await screen.findByRole('region', { name: 'Umfang und Speicher' })
      expect(within(scope).getByText(/Thumbnail-Cache: 120,0 MB/)).toBeInTheDocument()
      expect(within(scope).getByText(/Datenbank \(geschätzt\): 40,0 MB/)).toBeInTheDocument()
    })

    it('zeigt den Aufnahmezeitraum als Spanne', async () => {
      renderPage()

      expect(await screen.findByText(/02\.04\.2019.*19\.04\.2019/)).toBeInTheDocument()
    })

    it('rendert die Kategorientabelle mit allen Set-Keys in Server-Reihenfolge', async () => {
      renderPage()

      const table = await screen.findByRole('table')
      const rowHeaders = within(table)
        .getAllByRole('rowheader')
        .map((cell) => cell.textContent)
      expect(rowHeaders).toEqual(CATEGORY_KEYS.map((key) => `Server-Name ${key}`))
    })

    it('nutzt ausschliesslich die vom Server gelieferten Anzeigenamen', async () => {
      renderPage()

      const table = await screen.findByRole('table')
      // Regressionsschutz gegen eine zweite Label-Tabelle im Client (ADR 0049): stuende im
      // Frontend eine eigene Uebersetzung, erschiene hier "Landschaft" statt des Servernamens.
      expect(within(table).queryByText('Landschaft')).not.toBeInTheDocument()
      expect(within(table).getByText('Server-Name landschaft')).toBeInTheDocument()
    })

    it('weist "nicht klassifiziert" getrennt von der Kategorie "nicht erkannt" aus', async () => {
      renderPage()

      const scope = await screen.findByRole('region', { name: 'Kategorienverteilung' })
      expect(within(scope).getByText('Nicht klassifiziert')).toBeInTheDocument()
      expect(within(scope).getByText('2.243')).toBeInTheDocument()
    })

    it('zeigt die Zahl der manuell korrigierten Kategorien unter der Tabelle', async () => {
      renderPage()

      const scope = await screen.findByRole('region', { name: 'Kategorienverteilung' })
      expect(within(scope).getByText('Manuell korrigiert')).toBeInTheDocument()
      expect(within(scope).getByText('37')).toBeInTheDocument()
    })

    it('zeigt die Kosten je Zweck und die Gesamtsumme', async () => {
      renderPage()

      const scope = await screen.findByRole('region', { name: 'Kosten für Remote-Berechnungen' })
      expect(within(scope).getByText('42,13 USD')).toBeInTheDocument()
      expect(within(scope).getByText('12,10 USD')).toBeInTheDocument()
      expect(within(scope).getByText('30,03 USD')).toBeInTheDocument()
    })

    it('zeigt den Unvollstaendigkeits-Hinweis genau bei dem betroffenen Zweck', async () => {
      renderPage()

      const scope = await screen.findByRole('region', { name: 'Kosten für Remote-Berechnungen' })
      const hints = within(scope).getAllByText('Summe unvollständig erfasst')
      expect(hints).toHaveLength(1)
    })

    it('zeigt den Bearbeitungsstand als "x von y Fotos"', async () => {
      renderPage()

      const scope = await screen.findByRole('region', {
        name: 'Bearbeitungs- und Bewertungsstand',
      })
      expect(within(scope).getByText('12.040 von 12.043')).toBeInTheDocument()
      // "Eingeordnet" und "Remote klassifiziert" stehen beide bei 9.800.
      expect(within(scope).getAllByText('9.800 von 12.043')).toHaveLength(2)
    })

    it('beschriftet den Bewertungsstand als die eigene Bewertung', async () => {
      renderPage()

      expect(await screen.findByText(/Deine Bewertungen/)).toBeInTheDocument()
    })

    it('zeigt fuer einen nie gelaufenen Lauf "noch nie gelaufen", sonst den Zeitpunkt', async () => {
      renderPage()

      const scope = await screen.findByRole('region', { name: 'Vertrauen und Fehlersuche' })
      expect(within(scope).getAllByText('noch nie gelaufen')).toHaveLength(1)
      expect(within(scope).getAllByText(/01\.08\.2026/)).toHaveLength(3)
    })

    it('zeigt die Remote-Fehlschlaege je Zweck und die Duplikate', async () => {
      renderPage()

      const scope = await screen.findByRole('region', { name: 'Vertrauen und Fehlersuche' })
      expect(within(scope).getByText('341')).toBeInTheDocument()
      expect(within(scope).getByText('12')).toBeInTheDocument()
    })
  })

  describe('nicht ermittelbare Werte', () => {
    it('zeigt "nicht ermittelbar" statt "0 MB", wenn der Datenbank-Anteil fehlt', async () => {
      vi.mocked(projectsApi.getProjectStats).mockResolvedValue({
        ...fullStats(),
        storage: {
          opencloud_bytes: 1024 ** 3,
          local_cache_bytes: 1024 ** 2,
          local_database_bytes_estimate: null,
        },
      })

      renderPage()

      const scope = await screen.findByRole('region', { name: 'Umfang und Speicher' })
      expect(within(scope).getByText(/Datenbank \(geschätzt\): nicht ermittelbar/)).toBeInTheDocument()
    })
  })

  describe('Abgrenzung (Negativ-Assertions)', () => {
    beforeEach(() => {
      vi.mocked(projectsApi.getProjectStats).mockResolvedValue(fullStats())
    })

    it('enthaelt keine Foto-Vorschauen', async () => {
      const { container } = renderPage()

      await screen.findByRole('heading', { name: 'Statistik' })
      expect(container.querySelectorAll('img')).toHaveLength(0)
    })

    it('enthaelt keine Filter-, Sortier-, Export- oder Ausloese-Bedienelemente', async () => {
      renderPage()

      await screen.findByRole('heading', { name: 'Statistik' })
      expect(screen.queryAllByRole('textbox')).toHaveLength(0)
      expect(screen.queryAllByRole('combobox')).toHaveLength(0)
      expect(screen.queryAllByRole('checkbox')).toHaveLength(0)
      expect(screen.queryAllByRole('switch')).toHaveLength(0)
      expect(screen.queryAllByRole('link')).toHaveLength(0)
      // Die einzigen Buttons sind die Erlaeuterungs-Auslöser (Info-Popover).
      for (const button of screen.queryAllByRole('button')) {
        expect(button).toHaveAccessibleName(/Erkläre/)
      }
    })

    it('laedt die Daten genau einmal und aktualisiert sie nicht selbsttaetig', async () => {
      renderPage()

      await screen.findByRole('heading', { name: 'Statistik' })
      expect(vi.mocked(projectsApi.getProjectStats).mock.calls).toHaveLength(1)
    })
  })
})
