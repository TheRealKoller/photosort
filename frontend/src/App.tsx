import { Link, Navigate, Outlet, Route, Routes, matchPath, useLocation, useNavigate } from 'react-router'

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
import { ProjectCreatePage } from './pages/ProjectCreatePage'
import { ProjectDetailPage } from './pages/ProjectDetailPage'
import { ProjectListPage } from './pages/ProjectListPage'

// Einzige Quelle der Wahrheit fuer die vier Routen mit Projektkontext (specs/features/
// 0033-sticky-titelleiste-projekt-link.md): speist sowohl die <Route>-Erzeugung unten als auch
// den matchPath-Aufruf in useProjectIdFromRoute - verhindert, dass eine kuenftige
// :projectId-Route nur in <Routes> ergaenzt wird, aber stillschweigend keinen Header-Link
// bekommt. Explizite Aufzaehlung statt eines Wildcards wie "/projects/:projectId/*", da ein
// Wildcard "/projects/new" faelschlich als Projektkontext mit projectId="new" matchen wuerde
// (AK3). /projects/:projectId/curate ist bewusst NICHT enthalten (Spec-Entscheidung, nur die
// vier explizit genannten Routen).
const PROJECT_ROUTES: { path: string; element: JSX.Element }[] = [
  { path: '/projects/:projectId', element: <ProjectDetailPage /> },
  { path: '/projects/:projectId/photos', element: <PhotoGridPage /> },
  { path: '/projects/:projectId/photos/:photoId', element: <PhotoDetailPage /> },
  { path: '/projects/:projectId/compare', element: <PhotoComparePage /> },
]

function useProjectIdFromRoute(): string | null {
  const location = useLocation()
  for (const { path } of PROJECT_ROUTES) {
    const match = matchPath(path, location.pathname)
    if (match?.params.projectId) {
      return match.params.projectId
    }
  }
  return null
}

function AppShell() {
  const navigate = useNavigate()
  const token = getToken()
  const username = token ? decodeUsername(token) : null

  function handleLogout(): void {
    // Bestaetigungslose Aktion (siehe specs/features/0006-auth.md) - kein Backend-Aufruf, da es
    // ohne Server-Session-Store nichts zu invalidieren gaebe.
    clearToken()
    navigate('/login')
  }

  return (
    <div className="flex min-h-screen flex-col bg-bg text-text">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3 sm:px-6">
        {/* Requirements-Review-Fund (Branch feature/0012-visual-redesign-views): als einziges
            interaktives Element im Header nicht ueber die Button-Komponente verdrahtet, dadurch
            unter dem 44x44px-Touch-Ziel (AK "tatsaechlich messbar") - jetzt per Button asChild
            konsistent zu "Abmelden" gehalten, mit ueberschriebener Groesse/Optik fuers Wortmarke. */}
        <Button
          asChild
          variant="ghost"
          className="h-11 justify-start px-2 text-lg font-semibold text-text-h hover:bg-transparent"
        >
          <Link to="/">PhotoSort</Link>
        </Button>
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
          <Route path="/projects/:projectId/curate" element={<CurateCategoriesPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
