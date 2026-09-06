import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import { apiFetch } from './api/client'
import * as photosApi from './api/photos'
import * as projectsApi from './api/projects'
import type { ProjectOut, ProjectStatsOut } from './api/types'
import { getToken, setToken } from './auth/token'

vi.mock('./api/projects')
vi.mock('./api/photos')

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
    last_remote_category_classification_run: null,
    category_selection_enabled: true,
    cloud_vision_detection_enabled: false,
    cloud_vision_consent_at: null,
    ...overrides,
  }
}

/** Minimale, aber vollstaendige Statistik-Antwort (specs/features/0207-projekt-
 * statistikseite.md) - hier interessiert nur, dass die Route rendert. */
function emptyStats(): ProjectStatsOut {
  return {
    photo_count: 0,
    storage: { opencloud_bytes: 0, local_cache_bytes: 0, local_database_bytes_estimate: null },
    taken_at_earliest: null,
    taken_at_latest: null,
    categories: { classified_photo_count: 0, unclassified_photo_count: 0, entries: [] },
    manual_category_override_count: 0,
    cost: { currency: 'USD', total_usd: 0, by_purpose: [] },
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
      remote_failures: [],
    },
  }
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function makeToken(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
  const body = btoa(JSON.stringify(payload))
  return `${header}.${body}.sig`
}

function renderApp(initialEntries: string[] = ['/']) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )

  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <App />
    </MemoryRouter>,
    { wrapper }
  )
}

describe('App', () => {
  beforeEach(() => {
    window.localStorage.clear()
    vi.mocked(projectsApi.listProjects).mockReset()
    vi.mocked(projectsApi.listProjects).mockResolvedValue([])
    vi.mocked(projectsApi.getProject).mockReset()
    vi.mocked(projectsApi.getProject).mockResolvedValue(project())
    vi.mocked(photosApi.listPhotos).mockReset()
    vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [], total: 0 })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('redirects to /login when no token is present', () => {
    renderApp(['/'])

    expect(screen.getByLabelText(/benutzername/i)).toBeInTheDocument()
  })

  it('shows the app shell with the username derived from the token when authenticated', () => {
    setToken(makeToken({ sub: '1', username: 'daniel' }))

    renderApp(['/'])

    expect(screen.getByText('PhotoSort')).toBeInTheDocument()
    expect(screen.getByText(/angemeldet als daniel/i)).toBeInTheDocument()
  })

  it('logs out without a backend call: clears the token and navigates to /login', async () => {
    setToken(makeToken({ sub: '1', username: 'daniel' }))
    const user = userEvent.setup()

    renderApp(['/'])

    await user.click(screen.getByRole('button', { name: /abmelden/i }))

    expect(getToken()).toBeNull()
    expect(screen.getByLabelText(/benutzername/i)).toBeInTheDocument()
  })

  it('navigates to /login with an expired-session hint when a real API call returns 401 mid-session', async () => {
    // Deckt den in architecture/0002-testkonzept.md geforderten Testfall "401 mitten in
    // laufender Session" ab: statt das Event manuell zu dispatchen, wird ein zweiter,
    // tatsaechlicher apiFetch-Aufruf simuliert (gueltiges Token beim Laden, die Anfrage selbst
    // liefert wegen zwischenzeitlichem Ablauf 401) - apiFetch loescht das Token und feuert das
    // Event dabei selbst, als echter Seiteneffekt, nicht als Testkonstruktion.
    setToken(makeToken({ sub: '1', username: 'daniel' }))
    vi.stubGlobal('fetch', vi.fn())
    vi.mocked(fetch).mockResolvedValue(jsonResponse(401, { detail: 'Nicht authentifiziert.' }))

    renderApp(['/'])
    expect(screen.getByText('PhotoSort')).toBeInTheDocument()

    await expect(apiFetch('/projects')).rejects.toBeInstanceOf(Error)

    await waitFor(() => expect(screen.getByLabelText(/benutzername/i)).toBeInTheDocument())
    expect(screen.getByText(/sitzung abgelaufen/i)).toBeInTheDocument()
    expect(getToken()).toBeNull()
  })

  it('routes /projects/:id/photos to the photo grid within the app shell', async () => {
    setToken(makeToken({ sub: '1', username: 'daniel' }))

    renderApp(['/projects/1/photos'])

    expect(screen.getByText('PhotoSort')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Fotos' })).toBeInTheDocument()
  })

  it('routes /projects/:id/compare to the comparison view within the app shell', async () => {
    setToken(makeToken({ sub: '1', username: 'daniel' }))

    renderApp(['/projects/1/compare'])

    expect(screen.getByText('PhotoSort')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Vergleich' })).toBeInTheDocument()
  })

  it('routes /projects/:id/stats to the project stats page within the app shell', async () => {
    // specs/features/0207-projekt-statistikseite.md: eigene Querschnittsansicht neben den
    // Einstellungen, bewusst ausserhalb der Pipeline-Schritt-Routen.
    vi.mocked(projectsApi.getProjectStats).mockResolvedValue(emptyStats())
    setToken(makeToken({ sub: '1', username: 'daniel' }))

    renderApp(['/projects/1/stats'])

    expect(screen.getByText('PhotoSort')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Statistik' })).toBeInTheDocument()
  })

  it('routes /projects/:id/settings to the project settings page within the app shell', async () => {
    // specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md: erste dedizierte
    // Projekteinstellungs-Route.
    vi.mocked(projectsApi.getProject).mockResolvedValue(project())
    setToken(makeToken({ sub: '1', username: 'daniel' }))

    renderApp(['/projects/1/settings'])

    expect(screen.getByText('PhotoSort')).toBeInTheDocument()
    expect(
      await screen.findByRole('heading', { name: 'Projekteinstellungen' })
    ).toBeInTheDocument()
  })
})


/*
 * specs/features/0298-projektnavigation-in-der-kopfzeile.md (AK1-AK4, AK8): Die Kopfzeile traegt
 * auf jeder Projektseite die Navigationsgruppe statt des bisherigen einzelnen "‹ Projekt"-Links.
 * Diese Gruppe ist NICHT geloescht, sondern aus der Spec-0033-Testgruppe hervorgegangen - der
 * zugaengliche Name "Projekt" bleibt, nur sein Sprungziel wechselt auf /pipeline.
 *
 * Hier steht ausschliesslich, was die VERDRAHTUNG von Kopfzeile und Routing betrifft. Die
 * Fallunterscheidungen des Routenwissens liegen in utils/projectRoutes.test.ts (dorthin sind mit
 * dieser Spec auch die Sonderfaelle Query-Parameter, nicht-numerische projectId und
 * verschachtelte :photoId-Route gewandert), das Verhalten der Komponente in ProjectNav.test.tsx.
 */
describe('App - Projekt-Navigationsgruppe in der Kopfzeile', () => {
  beforeEach(() => {
    window.localStorage.clear()
    vi.mocked(projectsApi.listProjects).mockReset()
    vi.mocked(projectsApi.listProjects).mockResolvedValue([])
    vi.mocked(projectsApi.getProject).mockReset()
    vi.mocked(projectsApi.getProject).mockResolvedValue(project())
    vi.mocked(photosApi.listPhotos).mockReset()
    vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [], total: 0 })
    vi.mocked(projectsApi.getProjectStats).mockReset()
    vi.mocked(projectsApi.getProjectStats).mockResolvedValue(emptyStats())
    setToken(makeToken({ sub: '1', username: 'daniel' }))
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  /**
   * Die neun Muster aus PROJECT_ROUTE_PATHS mit eingesetzten Parametern. Diese Liste ist zugleich
   * der SYNCHRONITAETS-WAECHTER der expliziten Routen-Aufzaehlung (specs/architecture/
   * 0002-testkonzept.md): jedes Muster muss real geroutet sein UND die Gruppe zeigen - der
   * bekannte Fehlermodus ist, dass eine neue Route nur in <Routes> landet und still ohne
   * Kopfzeilen-Navigation bleibt (Alt-Bug aus Spec 0042/PR #101, erneut bei Spec 0207).
   */
  const PROJECT_CONTEXT_PATHS = [
    '/projects/1',
    '/projects/1/pipeline',
    '/projects/1/pipeline/scan',
    '/projects/1/photos',
    '/projects/1/photos/42',
    '/projects/1/compare',
    '/projects/1/settings',
    '/projects/1/stats',
    // specs/features/0298 (AK2): zum ersten Mal ueberhaupt Projektkontext in der Kopfzeile -
    // Umkehrung der ausdruecklichen Gegenfestlegung aus Spec 0033.
    '/projects/1/curate',
  ]

  const EXPECTED_TARGETS = [
    { label: 'Projekt', href: '/projects/1/pipeline' },
    { label: 'Fotos', href: '/projects/1/photos' },
    { label: 'Vergleich', href: '/projects/1/compare' },
    { label: 'Einstellungen', href: '/projects/1/settings' },
  ]

  /** Der eine Landmark der Gruppe; das Panel liegt per Portal ausserhalb davon. */
  function group(): HTMLElement {
    return screen.getByRole('navigation', { name: 'Projektbereiche' })
  }

  it.each(PROJECT_CONTEXT_PATHS)(
    'zeigt die Gruppe mit allen vier Zielen auf %s (AK1/AK2)',
    async (path) => {
      renderApp([path])

      const links = within(await screen.findByRole('navigation', { name: 'Projektbereiche' }))
        .getAllByRole('link')
      expect(links.map((link) => link.textContent)).toEqual(
        EXPECTED_TARGETS.map((target) => target.label)
      )
      links.forEach((link, index) => {
        expect(link).toHaveAttribute('href', EXPECTED_TARGETS[index].href)
      })

      // Zweite Haelfte des Synchronitaets-Waechters: die Route ist real geroutet und nicht ueber
      // den Catch-all auf der Projektliste gelandet.
      expect(screen.queryByRole('heading', { name: 'Projekte' })).not.toBeInTheDocument()
    }
  )

  /*
   * QUERY-STRING AUF DER ROUTE (AK2/AK8a, edge case): Auf `main` gab es diesen Fall als
   * "targets /projects/{projectId} unaffected by query parameters" - er ist beim Umbau der Gruppe
   * abhandengekommen und hier in der Form zurueck, die zur neuen Verdrahtung passt (Copilot-Fund
   * auf PR #340). Er gehoert auf DIESE Ebene und nicht in den Unit-Test: geprueft wird, dass die
   * App den `pathname` sauber vom `search` trennt, bevor sie ihn an `matchProjectId` reicht - eine
   * Verdrahtungsfrage, keine Frage des reinen Moduls (das lehnt einen mitgegebenen Query-String
   * ausdruecklich ab, siehe utils/projectRoutes.test.ts).
   *
   * Nicht konstruiert: `/photos` traegt in der Praxis den Filter des Fotorasters, den
   * "Zurück zum Grid" auf der Detailansicht ausdruecklich bewahrt. Ginge die Trennung verloren,
   * verschwaende die Kopfzeilen-Navigation auf jeder gefilterten Fotoliste.
   */
  it('zeigt Gruppe und Markierung unveraendert bei gesetztem Query-Parameter (AK2/AK8a, edge case)', async () => {
    renderApp(['/projects/1/photos?filter=favorite'])

    await screen.findByRole('navigation', { name: 'Projektbereiche' })
    const links = within(group()).getAllByRole('link')
    expect(links.map((link) => link.textContent)).toEqual(
      EXPECTED_TARGETS.map((target) => target.label)
    )
    links.forEach((link, index) => {
      expect(link).toHaveAttribute('href', EXPECTED_TARGETS[index].href)
    })

    // Beide Haelften in einem Fall: Der Projektkontext ueberlebt den Query-String UND der Marker
    // steht auf dem richtigen Ziel. Die Sprungziele oben belegen zugleich, dass der Query-String
    // nicht in die projectId geraten ist - er wuerde sonst in jedem der vier `href` auftauchen.
    const marked = links.filter((link) => link.getAttribute('aria-current') === 'page')
    expect(marked).toHaveLength(1)
    expect(marked[0]).toHaveAccessibleName('Fotos')
  })

  it('fuehrt den Namen "Projekt" in der Kopfzeile genau einmal, mit dem Ziel /pipeline (AK3a)', async () => {
    renderApp(['/projects/1/photos'])

    const links = await screen.findAllByRole('link', { name: 'Projekt' })
    expect(links).toHaveLength(1)
    expect(links[0]).toHaveAttribute('href', '/projects/1/pipeline')
    // Der bisherige eigenstaendige Eintrag zeigte auf /projects/1 - dieses Ziel darf in der
    // Kopfzeile nicht mehr vorkommen.
    expect(screen.queryByRole('link', { name: 'Projekt' })).not.toHaveAttribute(
      'href',
      '/projects/1'
    )
  })

  it.each([
    ['/projects/1', 'Projekt'],
    ['/projects/1/pipeline', 'Projekt'],
    ['/projects/1/pipeline/scan', 'Projekt'],
    ['/projects/1/photos', 'Fotos'],
    ['/projects/1/photos/42', 'Fotos'],
    ['/projects/1/compare', 'Vergleich'],
    ['/projects/1/settings', 'Einstellungen'],
  ])('markiert auf %s genau "%s" als aktuelle Seite (AK8a)', async (path, expectedLabel) => {
    renderApp([path])

    await screen.findByRole('navigation', { name: 'Projektbereiche' })
    // Eingegrenzt auf die Leiste, nie dokumentweit (specs/architecture/0002-testkonzept.md):
    // bei geoeffnetem Panel laege die Markierung zwangslaeufig doppelt vor.
    const marked = within(group())
      .getAllByRole('link')
      .filter((link) => link.getAttribute('aria-current') === 'page')
    expect(marked).toHaveLength(1)
    expect(marked[0]).toHaveAccessibleName(expectedLabel)
  })

  it.each(['/projects/1/stats', '/projects/1/curate'])(
    'zeigt die Gruppe auf %s vollstaendig, aber ohne Markierung (AK8b)',
    async (path) => {
      renderApp([path])

      await screen.findByRole('navigation', { name: 'Projektbereiche' })
      const links = within(group()).getAllByRole('link')
      expect(links).toHaveLength(EXPECTED_TARGETS.length)
      expect(links.filter((link) => link.hasAttribute('aria-current'))).toEqual([])
    }
  )

  it('bleibt bei geoeffnetem Panel genau EIN navigation-Landmark "Projektbereiche" (AK3b)', async () => {
    const user = userEvent.setup()
    renderApp(['/projects/1/photos'])

    await user.click(await screen.findByRole('button', { name: 'Projektbereiche' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()

    expect(screen.getAllByRole('navigation', { name: 'Projektbereiche' })).toHaveLength(1)
  })

  /** Kein Ziel, kein Ausloeser, kein Landmark - alle drei Haelften von AK4 einzeln. */
  function expectNoGroup(): void {
    expect(
      screen.queryByRole('navigation', { name: 'Projektbereiche' })
    ).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Projektbereiche' })).not.toBeInTheDocument()
    for (const target of EXPECTED_TARGETS) {
      expect(screen.queryByRole('link', { name: target.label })).not.toBeInTheDocument()
    }
  }

  it('zeigt auf / kein Element der Gruppe (AK4)', async () => {
    renderApp(['/'])

    expect(screen.getByText('PhotoSort')).toBeInTheDocument()
    // Wartet auf ein garantiert vorhandenes Element der Zielseite, bevor die
    // Abwesenheits-Assertion greift - sonst koennte die Gruppe nur deshalb fehlen, weil die Seite
    // noch nicht fertig gerendert ist.
    await waitFor(() => expect(projectsApi.listProjects).toHaveBeenCalled())
    expectNoGroup()
  })

  // Der Umzug von RESERVED_PROJECT_ID_SEGMENTS in ein neues Modul ist genau die Gelegenheit, bei
  // der die Zeile still verlorengeht - deshalb hier als Rendering-Fall UND als Abweisungsfall im
  // Unit-Test von utils/projectRoutes.
  it('zeigt auf /projects/new kein Element der Gruppe (AK4, edge case)', async () => {
    renderApp(['/projects/new'])

    expect(await screen.findByRole('heading', { name: /neues projekt/i })).toBeInTheDocument()
    expectNoGroup()
  })

  it('zeigt auf /login kein Element der Gruppe (AK4)', () => {
    window.localStorage.clear()
    renderApp(['/login'])

    expect(screen.getByLabelText(/benutzername/i)).toBeInTheDocument()
    expectNoGroup()
  })

  it('zeigt nach der Catch-all-Weiterleitung eines unbekannten Pfads kein Element der Gruppe (AK4)', async () => {
    renderApp(['/some/unknown/path'])

    expect(await screen.findByText('PhotoSort')).toBeInTheDocument()
    await waitFor(() => expect(projectsApi.listProjects).toHaveBeenCalled())
    expectNoGroup()
  })

  it('bietet die Ziele als tastaturbedienbare native Links an (AK11a)', async () => {
    renderApp(['/projects/1/photos'])

    await screen.findByRole('navigation', { name: 'Projektbereiche' })
    const link = within(group()).getByRole('link', { name: 'Vergleich' })
    expect(link.tagName).toBe('A')
    link.focus()
    expect(link).toHaveFocus()
  })

  // Copilot-Review-Fund auf PR #101 (Spec 0042): die Pipeline-Basis-Route ohne :step ist ein real
  // erreichbarer Zwischenzustand - ProjectDetailRedirect und PhotoGridPage navigieren gezielt
  // dorthin, bevor ProjectPipelineLayouts eigener Redirect-Guard auf einen konkreten Schritt
  // weiterspringt. getProject bleibt hier bewusst unresolved, damit der Test die
  // Layout-Ladeanzeige faengt, bevor irgendein Redirect feuern kann. Die Gruppe haengt
  // ausschliesslich am pathname und erscheint deshalb auch waehrend des Ladens - genau dann ist
  // ein Weg heraus am wertvollsten.
  it('zeigt die Gruppe schon auf der Pipeline-Basis-Route, waehrend das Projekt noch laedt (edge case)', async () => {
    vi.mocked(projectsApi.getProject).mockReset()
    vi.mocked(projectsApi.getProject).mockReturnValue(new Promise(() => {}))

    renderApp(['/projects/1/pipeline'])

    expect(await screen.findByRole('status')).toHaveTextContent('Projekt wird geladen')
    const marked = within(group())
      .getAllByRole('link')
      .filter((link) => link.getAttribute('aria-current') === 'page')
    expect(marked).toHaveLength(1)
    expect(marked[0]).toHaveAccessibleName('Projekt')
  })
})
