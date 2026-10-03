import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from '../App'
import { ApiError, apiFetch } from '../api/client'
import type { OverviewSeenOut, ProjectOut } from '../api/types'
import { setToken } from '../auth/token'
import { useProjectOverview } from '../hooks/useProjectOverview'
import { projectFixture, scanSummary } from '../test/projectStateSpace'
import { PROJECT_ROUTE_PATHS } from '../utils/projectRoutes'
import { ProjectOverviewHost } from './ProjectOverviewHost'

/*
 * Wann die Ablaufübersicht erscheint. Gespielt wird auf `apiFetch`, der einzigen
 * Stelle, die HTTP-Anfragen baut - damit ist jede Anfrage des Hosts sichtbar, auch eine, die über
 * einen ungeprüften Pfad liefe.
 */
vi.mock('../api/client', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api/client')>()),
  apiFetch: vi.fn(),
}))

const PROJECT = projectFixture({ id: 1 })

interface Answers {
  project?: () => Promise<ProjectOut>
  seen?: () => Promise<OverviewSeenOut>
  put?: () => Promise<void>
}

function answer({
  project = () => Promise.resolve(PROJECT),
  seen = () => Promise.resolve({ seen: false }),
  put = () => Promise.resolve(),
}: Answers = {}): void {
  vi.mocked(apiFetch).mockImplementation((path, options) => {
    if (path === '/projects/1/overview-seen') {
      return (options?.method === 'PUT' ? put() : seen()) as Promise<never>
    }
    if (path === '/projects/1') {
      return project() as Promise<never>
    }
    // Alles übrige (die Seiten unter dem Host) bleibt offen - Gegenstand ist der Host.
    return new Promise<never>(() => {})
  })
}

function calls(): string[] {
  return vi
    .mocked(apiFetch)
    .mock.calls.map(([path, options]) => `${options?.method ?? 'GET'} ${path}`)
}

function LocationProbe() {
  const location = useLocation()
  return <p data-testid="ort">{location.pathname}</p>
}

function OpenButton() {
  const { open } = useProjectOverview()
  return (
    <button type="button" onClick={open}>
      Ablauf
    </button>
  )
}

function BackButton() {
  const navigate = useNavigate()
  return (
    <button type="button" onClick={() => navigate(-1)}>
      Zurück
    </button>
  )
}

function renderHost(
  projectIdParam = '1',
  { queryClient = new QueryClient(), path = '/projects/1/photos/5' } = {},
) {
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return render(
    <MemoryRouter initialEntries={[path]}>
      <ProjectOverviewHost projectIdParam={projectIdParam}>
        <LocationProbe />
        <OpenButton />
        <BackButton />
      </ProjectOverviewHost>
    </MemoryRouter>,
    { wrapper },
  )
}

beforeEach(() => {
  vi.mocked(apiFetch).mockReset()
})

describe('ProjectOverviewHost: von selbst', () => {
  it('erscheint beim ersten Öffnen, sobald Projekt und Merker geladen sind', async () => {
    answer()
    renderHost()

    expect(await screen.findByRole('dialog', { name: 'Ablauf im Überblick' })).toBeInTheDocument()
  })

  it('erscheint nicht, wenn die Person sie schon gesehen hat', async () => {
    answer({ seen: () => Promise.resolve({ seen: true }) })
    renderHost()

    await waitFor(() => expect(calls()).toContain('GET /projects/1/overview-seen'))
    await act(async () => {})
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('erscheint nicht, solange das Projekt lädt', async () => {
    answer({ project: () => new Promise(() => {}) })
    renderHost()

    await waitFor(() => expect(calls()).toContain('GET /projects/1/overview-seen'))
    await act(async () => {})
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('erscheint nicht, solange "gesehen" unbekannt ist, und blitzt bei später "gesehen" nie auf', async () => {
    // `Promise.withResolvers` liegt ausserhalb von `lib: ES2023` dieses TS-Projekts.
    let resolve: (value: OverviewSeenOut) => void = () => undefined
    const promise = new Promise<OverviewSeenOut>((settle) => {
      resolve = settle
    })
    answer({ seen: () => promise })
    // Ein Befund im Beobachter-Rückruf liefe ins Leere - festgehalten wird deshalb jeder Moment,
    // in dem ein Dialog im Dokument steht, und erst danach geprüft.
    let sawDialog = false
    const observer = new MutationObserver(() => {
      sawDialog ||= document.querySelector('dialog') !== null
    })
    observer.observe(document.body, { childList: true, subtree: true })
    renderHost()

    // Das Projekt ist geladen, der Merker noch unbekannt: Jetzt darf der Dialog nicht stehen.
    await waitFor(() => expect(calls()).toContain('GET /projects/1'))
    await act(async () => {})
    expect(screen.queryByRole('dialog')).toBeNull()

    await act(async () => {
      resolve({ seen: true })
      await promise
    })
    observer.disconnect()

    expect(sawDialog, 'ein Dialog stand zwischendurch im Dokument').toBe(false)
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('erscheint nicht bei einem unbekannten Projekt (404)', async () => {
    answer({
      project: () => Promise.reject(new ApiError(404, 'Projekt nicht gefunden.')),
      seen: () => Promise.reject(new ApiError(404, 'Projekt nicht gefunden.')),
    })
    renderHost()

    await waitFor(() => expect(calls()).toContain('GET /projects/1'))
    await act(async () => {})
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('erscheint bei einem Lesefehler - genau ein Aufruf, ohne Wiederholung', async () => {
    answer({ seen: () => Promise.reject(new ApiError(500, 'kaputt')) })
    renderHost()

    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    expect(calls().filter((call) => call === 'GET /projects/1/overview-seen')).toHaveLength(1)
  })

  it.each(['abc', '1/../..', '0', '-3', '1.5', ''])(
    'setzt für die Id %j keine einzige Anfrage ab',
    async (raw) => {
      answer()
      renderHost(raw)

      await act(async () => {})
      expect(apiFetch).not.toHaveBeenCalled()
      expect(screen.queryByRole('dialog')).toBeNull()
    },
  )

  it('schließt, wenn ein späterer Abruf das Projekt nicht mehr findet (404)', async () => {
    // Ohne Wiederholung des Projektabrufs - sonst wartete der Test die Rückoff-Pausen ab.
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    let gone = false
    answer({
      project: () =>
        gone
          ? Promise.reject(new ApiError(404, 'Projekt nicht gefunden.'))
          : Promise.resolve(PROJECT),
    })
    renderHost('1', { queryClient })
    expect(await screen.findByRole('dialog')).toBeInTheDocument()

    // Die andere Person löscht das Projekt; der nächste Abruf liefert 404, der Cache hält noch
    // die alten Daten.
    gone = true
    await act(async () => {
      await queryClient.refetchQueries({ queryKey: ['project', 1] })
    })

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })

  it('bleibt bei einem vorübergehenden Abruffehler offen', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    let broken = false
    answer({
      project: () =>
        broken ? Promise.reject(new ApiError(500, 'kaputt')) : Promise.resolve(PROJECT),
    })
    renderHost('1', { queryClient })
    expect(await screen.findByRole('dialog')).toBeInTheDocument()

    broken = true
    await act(async () => {
      await queryClient.refetchQueries({ queryKey: ['project', 1] })
    })

    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })
})

describe('ProjectOverviewHost: Schließen', () => {
  it.each(['Schließen', 'Esc'])(
    'merkt "gesehen" und führt mit %s zum nächsten Schritt, auch vom Foto-Lesezeichen',
    async (way) => {
      const user = userEvent.setup()
      answer()
      renderHost()
      await screen.findByRole('dialog')

      if (way === 'Esc') {
        await user.keyboard('{Escape}')
      } else {
        await user.click(screen.getByRole('button', { name: 'Schließen' }))
      }

      expect(screen.queryByRole('dialog')).toBeNull()
      // Frisches Projekt: Der nächste anstehende Schritt ist der Scan.
      expect(screen.getByTestId('ort').textContent).toBe('/projects/1/pipeline/scan')
      await waitFor(() => expect(calls()).toContain('PUT /projects/1/overview-seen'))
    },
  )

  it('zeigt sie nach "Zurück" nicht erneut', async () => {
    const user = userEvent.setup()
    answer()
    renderHost()
    await user.click(await screen.findByRole('button', { name: 'Schließen' }))

    await user.click(screen.getByRole('button', { name: 'Zurück' }))

    expect(screen.getByTestId('ort')).toHaveTextContent('/projects/1/photos/5')
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('merkt "gesehen" auch beim Klick auf einen Eintrag und führt zu dessen Ziel', async () => {
    const user = userEvent.setup()
    answer()
    renderHost()
    await user.click(await screen.findByRole('link', { name: 'Scan öffnen' }))

    expect(screen.queryByRole('dialog')).toBeNull()
    expect(screen.getByTestId('ort')).toHaveTextContent('/projects/1/pipeline/scan')
    await waitFor(() => expect(calls()).toContain('PUT /projects/1/overview-seen'))
  })

  it('bleibt bei einem Schreibfehler ohne Meldung und erscheint erst nach Neuladen wieder', async () => {
    const user = userEvent.setup()
    answer({ put: () => Promise.reject(new ApiError(500, 'kaputt')) })
    const first = renderHost()
    await user.click(await screen.findByRole('button', { name: 'Schließen' }))
    await waitFor(() => expect(calls()).toContain('PUT /projects/1/overview-seen'))
    await act(async () => {})

    expect(screen.getByTestId('ort').textContent).toBe('/projects/1/pipeline/scan')
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.queryByRole('status')).toBeNull()

    // Neuladen: frischer Abfrage-Cache, der Server kennt "gesehen" nicht.
    first.unmount()
    renderHost('1', { queryClient: new QueryClient() })
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
  })

  it('schreibt nichts außer dem einen PUT - auch nicht in den Browser-Speicher', async () => {
    const user = userEvent.setup()
    const setItem = vi.spyOn(Storage.prototype, 'setItem')
    answer()
    renderHost()
    await user.click(await screen.findByRole('button', { name: 'Schließen' }))
    await user.click(screen.getByRole('button', { name: 'Ablauf' }))
    await user.click(screen.getByRole('button', { name: 'Schließen' }))
    await act(async () => {})

    const writes = calls().filter((call) => !call.startsWith('GET '))
    expect(new Set(writes)).toEqual(new Set(['PUT /projects/1/overview-seen']))
    expect(setItem).not.toHaveBeenCalled()
    setItem.mockRestore()
  })
})

describe('ProjectOverviewHost: von Hand', () => {
  it('öffnet die Übersicht über useProjectOverview().open, auch wenn sie gesehen ist', async () => {
    const user = userEvent.setup()
    answer({ seen: () => Promise.resolve({ seen: true }) })
    renderHost()
    await waitFor(() => expect(calls()).toContain('GET /projects/1'))

    await user.click(screen.getByRole('button', { name: 'Ablauf' }))

    expect(await screen.findByRole('dialog')).toBeInTheDocument()
  })
})

/*
 * Jeder Einstiegsweg ins Projekt - App-Ebene, parametrisiert über ALLE Muster aus
 * PROJECT_ROUTE_PATHS. Die Fall-Liste ist als Menge gleich der Konstante; eine neue Route ohne
 * Fall macht den ersten Test rot.
 */
const ROUTE_CASES: Record<keyof typeof PROJECT_ROUTE_PATHS, string> = {
  detail: '/projects/1',
  pipelineBase: '/projects/1/pipeline',
  pipelineStep: '/projects/1/pipeline/scan',
  photos: '/projects/1/photos',
  photoDetail: '/projects/1/photos/5',
  photoDuplicates: '/projects/1/photos/5/duplicates',
  selection: '/projects/1/selection',
  settings: '/projects/1/settings',
  stats: '/projects/1/stats',
  album: '/projects/1/album',
  persons: '/projects/1/persons',
}

function renderApp(path: string) {
  setToken('header.eyJzdWIiOiIxIiwidXNlcm5hbWUiOiJkYW5pZWwifQ.sig')
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="*" element={<App />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ProjectOverviewHost: auf jedem Weg ins Projekt', () => {
  afterEach(() => {
    window.localStorage.clear()
  })

  it('führt für jedes Muster aus PROJECT_ROUTE_PATHS genau einen Fall', () => {
    expect(new Set(Object.keys(ROUTE_CASES))).toEqual(new Set(Object.keys(PROJECT_ROUTE_PATHS)))
  })

  it.each(Object.entries(ROUTE_CASES))('erscheint auf der Route %s (%s)', async (_name, path) => {
    answer()
    renderApp(path)

    expect(await screen.findByRole('dialog', { name: 'Ablauf im Überblick' })).toBeInTheDocument()
  })

  it.each(['/', '/projects/new', '/persons'])(
    'erscheint auf %s ohne Projektbezug nicht und liest nichts',
    async (path) => {
      answer()
      renderApp(path)

      await act(async () => {})
      expect(calls().filter((call) => call.includes('overview-seen'))).toEqual([])
      expect(screen.queryByRole('dialog', { name: 'Ablauf im Überblick' })).toBeNull()
    },
  )
})

describe('ProjectOverviewHost: Fokus nach dem Schließen', () => {
  afterEach(() => {
    window.localStorage.clear()
  })

  /*
   * Der Auslöser „Ablauf“ bekommt den Fokus zurück, auch wenn das Schließen auf einen ANDEREN
   * Schritt führt: Hier steht man auf dem Scan, der nächste anstehende Schritt ist der Ausschuss.
   * Ein Umweg über die Weiterleitung von `/pipeline` hängte das Layout samt Auslöser für einen
   * Render aus, und die Fokusrückgabe ginge an einen gelösten Knoten.
   */
  it.each(['Schließen', 'Esc'])(
    'gibt den Fokus nach %s an den Auslöser zurück und landet auf dem nächsten Schritt',
    async (way) => {
      const user = userEvent.setup()
      answer({
        project: () => Promise.resolve({ ...PROJECT, last_scan: scanSummary('success') }),
        seen: () => Promise.resolve({ seen: true }),
      })
      renderApp('/projects/1/pipeline/scan')
      const trigger = await screen.findByRole('button', { name: 'Ablauf' })

      await user.click(trigger)
      await screen.findByRole('dialog', { name: 'Ablauf im Überblick' })
      if (way === 'Esc') {
        await user.keyboard('{Escape}')
      } else {
        await user.click(screen.getByRole('button', { name: 'Schließen' }))
      }

      await waitFor(() =>
        expect(
          screen.getByRole('link', { name: /^Schritt 2 von 4: Ausschuss, aktuell$/ }),
        ).toHaveAttribute('aria-current', 'step'),
      )
      const nachher = screen.getByRole('button', { name: 'Ablauf' })
      expect(nachher, 'derselbe Knoten, nicht neu eingehängt').toBe(trigger)
      expect(nachher).toHaveFocus()
    },
  )
})
