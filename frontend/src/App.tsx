import type { ReactElement } from 'react'
import { Link, Navigate, Outlet, Route, Routes, useLocation, useNavigate, useParams } from 'react-router'

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
import { ProjectStatsPage } from './pages/ProjectStatsPage'
import { matchProjectId, PROJECT_ROUTE_PATHS } from './utils/projectRoutes'

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

// Zuordnung Pfad -> Element fuer die flachen Routen mit Projektkontext. Die PFADE kommen seit
// specs/features/0298-projektnavigation-in-der-kopfzeile.md aus utils/projectRoutes.ts - dort
// liegt die einzige Quelle der Wahrheit dafuer, welche Routen Projektkontext haben; hier steht
// nur noch, welches Element eine davon rendert. Damit kann eine neue :projectId-Route nicht mehr
// still ohne Kopfzeilen-Navigation bleiben (Alt-Bug aus Spec 0042/PR #101, erneut bei Spec 0207).
// `element` ist als `ReactElement` typisiert statt des global nicht verfuegbaren `JSX.Element`
// (moduleDetection: "force", TS2503).
//
// Die verschachtelte Pipeline-Route (Layout + eigene Kind-Route fuer den Outlet-Context) kann
// NICHT ueber dieses flache PROJECT_ROUTES.map() erzeugt werden und steht deshalb unten separat -
// ihre Pfade stehen aber ebenfalls in PROJECT_ROUTE_PATHS. Die Kind-Route bleibt relativ
// (path=":step"), ihr absolutes Muster wird nur zum Matchen gebraucht.
const PROJECT_ROUTES: { path: string; element: ReactElement }[] = [
  { path: PROJECT_ROUTE_PATHS.detail, element: <ProjectDetailRedirect /> },
  { path: PROJECT_ROUTE_PATHS.photos, element: <PhotoGridPage /> },
  { path: PROJECT_ROUTE_PATHS.photoDetail, element: <PhotoDetailPage /> },
  { path: PROJECT_ROUTE_PATHS.compare, element: <PhotoComparePage /> },
  // specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md: erste dedizierte
  // Projekteinstellungs-Route.
  { path: PROJECT_ROUTE_PATHS.settings, element: <ProjectSettingsPage /> },
  // specs/features/0207-projekt-statistikseite.md: Querschnittsansicht wie die Einstellungsseite,
  // bewusst ausserhalb der Pipeline-Schritt-Routen (sie ist kein Schritt des Ablaufs).
  { path: PROJECT_ROUTE_PATHS.stats, element: <ProjectStatsPage /> },
]

function useProjectIdFromRoute(): string | null {
  return matchProjectId(useLocation().pathname)
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
      <header className="sticky top-0 z-10 flex flex-wrap items-center justify-between gap-3 border-b border-separator bg-bg px-4 py-3 sm:px-6">
        {/* Requirements-Review-Fund (Branch feature/0012-visual-redesign-views): als einziges
            interaktives Element im Header nicht ueber die Button-Komponente verdrahtet, dadurch
            unter dem 44x44px-Touch-Ziel (AK "tatsaechlich messbar") - jetzt per Button asChild
            konsistent zu "Abmelden" gehalten, mit ueberschriebener Groesse/Optik fuers Wortmarke. */}
        {/* gap-2 statt gap-1: 8px ist der Mindestabstand zwischen zwei fokussierbaren
            Elementen - die aufgespannten Trefferflaechen der beiden Links duerfen sich nicht
            ueberlappen, in einer Ueberlappung gewinnt das obenliegende Element. */}
        <div className="flex items-center gap-2">
          <Button
            asChild
            variant="ghost"
            // Kein `h-11` mehr: die Wortmarke ist weder heisser Pfad noch Zeile einer
            // zeilenweisen Liste. Sichtbar gilt das Board-Mass 32px, die 44px kommen aus der
            // Aufspannung, die das Button-Primitiv ohnehin mitbringt (Spec 0321).
            className="justify-start px-2 text-lg font-semibold text-text-h hover:bg-transparent"
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
              className="px-2 text-text-h hover:bg-transparent"
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
          <Route path={PROJECT_ROUTE_PATHS.pipelineBase} element={<ProjectPipelineLayout />}>
            <Route path=":step" element={<PipelineStepView />} />
          </Route>
          <Route path={PROJECT_ROUTE_PATHS.curate} element={<CurateCategoriesPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
