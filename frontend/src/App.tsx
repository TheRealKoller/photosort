import type { ReactElement } from 'react'
import { Link, Navigate, Outlet, Route, Routes, matchPath, useLocation, useNavigate, useParams } from 'react-router'

import { ProtectedRoute } from './auth/ProtectedRoute'
import { decodeUsername } from './auth/jwt'
import { clearToken, getToken } from './auth/token'
import { useUnauthorizedRedirect } from './auth/useUnauthorizedRedirect'
import { Button } from './components/ui/button'
import { CurateCategoriesPage } from './pages/CurateCategoriesPage'
import { LoginPage } from './pages/LoginPage'
import { PhotoComparePage } from './pages/PhotoComparePage'
import { PhotoDetailPage } from './pages/PhotoDetailPage'
import { PhotoGridPage } from './pages/PhotoGridPage'
import { PipelineStepView } from './pages/pipeline/PipelineStepView'
import { ProjectPipelineLayout } from './pages/pipeline/ProjectPipelineLayout'
import { ProjectCreatePage } from './pages/ProjectCreatePage'
import { ProjectListPage } from './pages/ProjectListPage'
import { ProjectSettingsPage } from './pages/ProjectSettingsPage'

/**
 * Reiner Redirect (specs/features/0042-automatisierter-flow-stepper-detailseiten.md,
 * Akzeptanzkriterium 1): ersetzt die bisherige, jetzt entfernte ProjectDetailPage.tsx als Ziel
 * dieser Route - Bestandsschutz fuer bestehende Links/Bookmarks auf /projects/:projectId. Bewusst
 * absoluter Template-String statt relativem `to="pipeline"`, konsistent mit dem im Projekt
 * durchgehend etablierten Muster expliziter absoluter Pfade (Architektur-Abschnitt der Spec).
 */
function ProjectDetailRedirect() {
  const { projectId } = useParams()
  return <Navigate to={`/projects/${projectId}/pipeline`} replace />
}

// Einzige Quelle der Wahrheit fuer die flachen Routen mit Projektkontext (specs/features/
// 0033-sticky-titelleiste-projekt-link.md): speist sowohl die <Route>-Erzeugung unten als auch
// den matchPath-Aufruf in useProjectIdFromRoute - verhindert, dass eine kuenftige
// :projectId-Route nur in <Routes> ergaenzt wird, aber stillschweigend keinen Header-Link
// bekommt. Explizite Aufzaehlung statt eines Wildcards wie "/projects/:projectId/*", da ein
// Wildcard "/projects/new" faelschlich als Projektkontext mit projectId="new" matchen wuerde
// (AK3). /projects/:projectId/curate ist bewusst NICHT enthalten (Spec-Entscheidung, nur die
// hier bzw. in PIPELINE_BASE_ROUTE_PATH/PIPELINE_STEP_ROUTE_PATH genannten Routen). `element` ist als `ReactElement`
// typisiert statt des woertlich in der Spec genannten globalen `JSX.Element` - unter diesem
// tsconfig (moduleDetection: "force", kein globaler JSX-Namespace importiert) loest `JSX.Element`
// TS2503 ("Cannot find namespace 'JSX'") aus; `ReactElement` aus `react` ist das Modul-basierte
// Aequivalent und typprueft sauber.
//
// Die neue, verschachtelte Pipeline-Route (specs/features/0042, erste Verwendung von
// React-Router-Nested-Routes im Projekt) kann NICHT ueber dieses flache PROJECT_ROUTES.map()
// erzeugt werden (Layout + eigene Kind-Route noetig fuer den Outlet-Context) - ihr Pfad wird
// deshalb separat als PIPELINE_BASE_ROUTE_PATH/PIPELINE_STEP_ROUTE_PATH gefuehrt, aber ausdruecklich
// an DERSELBEN Stelle wie PROJECT_ROUTES fuer matchPath ergaenzt (siehe useProjectIdFromRoute unten),
// damit sie nicht denselben stillschweigenden Header-Link-Bug reproduziert, den der obige Kommentar
// verhindern soll. Beide Pfade sind noetig: die Basis-Route ohne :step ist ein real erreichbarer
// Zwischenzustand (ProjectDetailRedirect sowie PhotoGridPage navigieren gezielt dorthin, bevor der
// Redirect-Guard in ProjectPipelineLayout auf einen konkreten Schritt weiterspringt) - Copilot-Review-
// Fund auf PR #101 (Spec 0042): ohne PIPELINE_BASE_ROUTE_PATH fehlte der Projekt-Kontext-Link im
// Sticky-Header genau waehrend dieses kurzen Zwischenzustands.
const PROJECT_ROUTES: { path: string; element: ReactElement }[] = [
  { path: '/projects/:projectId', element: <ProjectDetailRedirect /> },
  { path: '/projects/:projectId/photos', element: <PhotoGridPage /> },
  { path: '/projects/:projectId/photos/:photoId', element: <PhotoDetailPage /> },
  { path: '/projects/:projectId/compare', element: <PhotoComparePage /> },
  // specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md: erste dedizierte
  // Projekteinstellungs-Route - hier statt separat ergaenzt, damit sie automatisch denselben
  // Sticky-Header-"Projekt"-Link bekommt (siehe Kommentar oben).
  { path: '/projects/:projectId/settings', element: <ProjectSettingsPage /> },
]

const PIPELINE_BASE_ROUTE_PATH = '/projects/:projectId/pipeline'
const PIPELINE_STEP_ROUTE_PATH = '/projects/:projectId/pipeline/:step'

// Technische Korrektur gegenueber dem woertlichen Codebeispiel der Spec (Architektur-Abschnitt):
// matchPath('/projects/:projectId', ...) kennt die als Geschwister-Route registrierte, literale
// "/projects/new" nicht - anders als React Routers eigentliches Routing (das statische Segmente
// vor dynamischen bevorzugt) matcht ein isolierter matchPath-Aufruf "/projects/new" trotzdem mit
// projectId="new", was AK3 direkt verletzen wuerde. "new" ist der einzige aktuell reservierte
// literale Sibling-Segment-Name unter /projects/ - wird ausgeschlossen, waehrend echte (auch
// nicht-numerische, z.B. "abc") projectId-Werte weiterhin funktionieren.
// ACHTUNG: anders als PROJECT_ROUTES ist dies KEINE automatisch aus den Routen abgeleitete Liste -
// eine kuenftige neue literale Sibling-Route unter /projects/ (z.B. "/projects/import") muss hier
// manuell ergaenzt werden, sonst matcht sie faelschlich als Projektkontext.
const RESERVED_PROJECT_ID_SEGMENTS = new Set(['new'])

function useProjectIdFromRoute(): string | null {
  const location = useLocation()
  for (const path of [
    ...PROJECT_ROUTES.map((route) => route.path),
    PIPELINE_BASE_ROUTE_PATH,
    PIPELINE_STEP_ROUTE_PATH,
  ]) {
    const match = matchPath(path, location.pathname)
    const projectId = match?.params.projectId
    if (projectId && !RESERVED_PROJECT_ID_SEGMENTS.has(projectId)) {
      return projectId
    }
  }
  return null
}

function AppShell() {
  const navigate = useNavigate()
  const token = getToken()
  const username = token ? decodeUsername(token) : null
  const projectId = useProjectIdFromRoute()

  function handleLogout(): void {
    // Bestaetigungslose Aktion (siehe specs/features/0006-auth.md) - kein Backend-Aufruf, da es
    // ohne Server-Session-Store nichts zu invalidieren gaebe.
    clearToken()
    navigate('/login')
  }

  return (
    <div className="flex min-h-screen flex-col bg-bg text-text">
      {/* Sticky Header (specs/features/0033-sticky-titelleiste-projekt-link.md, AK1): bleibt beim
          Scrollen einer Seite am oberen Viewport-Rand sichtbar. z-10 ist der erste Eintrag einer
          projektweiten Z-Index-Konvention - bleibt unter Radix-Portal-Overlays (Dialoge/Tooltips
          landen per Portal mit eigenen, hoeheren Werten ausserhalb des normalen Baums). bg-bg wird
          hier jetzt explizit gesetzt (bisher trug nur der aeussere Wrapper die Hintergrundfarbe),
          damit scrollender Inhalt im Sticky-Zustand nicht sichtbar durchscheinen kann, falls eine
          kuenftige Seite einen abweichenden Hintergrund einfuehrt. CSS-Sticky-Verhalten ist in
          jsdom nicht automatisiert pruefbar - manueller Smoke-Test vor Merge (Scrollen durch eine
          Fotoliste, kein Layout-Overlap, Light/Dark). */}
      <header className="sticky top-0 z-10 flex flex-wrap items-center justify-between gap-3 border-b border-border bg-bg px-4 py-3 sm:px-6">
        {/* Requirements-Review-Fund (Branch feature/0012-visual-redesign-views): als einziges
            interaktives Element im Header nicht ueber die Button-Komponente verdrahtet, dadurch
            unter dem 44x44px-Touch-Ziel (AK "tatsaechlich messbar") - jetzt per Button asChild
            konsistent zu "Abmelden" gehalten, mit ueberschriebener Groesse/Optik fuers Wortmarke. */}
        <div className="flex items-center gap-1">
          <Button
            asChild
            variant="ghost"
            className="h-11 justify-start px-2 text-lg font-semibold text-text-h hover:bg-transparent"
          >
            <Link to="/">PhotoSort</Link>
          </Button>
          {/* Projekt-Kontext-Link (specs/features/0033-sticky-titelleiste-projekt-link.md, AK2-AK4,
              AK8): rendert nur mit Projektkontext, zeigt immer auf die Projekt-Detailseite selbst -
              auch auf der Projekt-Detailseite selbst (Self-Link, bewusst keine Ausblendung/
              Deaktivierung, AK8). Gleiches Button-asChild+Link-Muster wie die Wortmarke (AK5).
              Chevron rein dekorativ/aria-hidden (AK6) - der zugaengliche Name ist ausschliesslich
              der Text "Projekt". */}
          {projectId !== null && (
            <Button
              asChild
              variant="ghost"
              className="h-11 px-2 text-text-h hover:bg-transparent"
            >
              <Link to={`/projects/${projectId}`}>
                <span aria-hidden="true">‹</span> Projekt
              </Link>
            </Button>
          )}
        </div>
        <div className="flex items-center gap-3">
          {username && <span className="text-sm text-text">Angemeldet als {username}</span>}
          <Button type="button" variant="outline" size="sm" onClick={handleLogout}>
            Abmelden
          </Button>
        </div>
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-6 sm:px-6">
        <Outlet />
      </main>
    </div>
  )
}

function App() {
  useUnauthorizedRedirect()

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route path="/" element={<ProjectListPage />} />
          <Route path="/projects/new" element={<ProjectCreatePage />} />
          {PROJECT_ROUTES.map(({ path, element }) => (
            <Route key={path} path={path} element={element} />
          ))}
          <Route path="/projects/:projectId/pipeline" element={<ProjectPipelineLayout />}>
            <Route path=":step" element={<PipelineStepView />} />
          </Route>
          <Route path="/projects/:projectId/curate" element={<CurateCategoriesPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
