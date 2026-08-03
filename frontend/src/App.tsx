import { Link, Navigate, Outlet, Route, Routes, useNavigate } from 'react-router'

import { ProtectedRoute } from './auth/ProtectedRoute'
import { decodeUsername } from './auth/jwt'
import { clearToken, getToken } from './auth/token'
import { useUnauthorizedRedirect } from './auth/useUnauthorizedRedirect'
import { Button } from './components/ui/button'
import { LoginPage } from './pages/LoginPage'
import { PhotoComparePage } from './pages/PhotoComparePage'
import { PhotoDetailPage } from './pages/PhotoDetailPage'
import { PhotoGridPage } from './pages/PhotoGridPage'
import { ProjectCreatePage } from './pages/ProjectCreatePage'
import { ProjectDetailPage } from './pages/ProjectDetailPage'
import { ProjectListPage } from './pages/ProjectListPage'

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
        <Link to="/" className="text-lg font-semibold text-text-h">
          PhotoSort
        </Link>
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
          <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
          <Route path="/projects/:projectId/photos" element={<PhotoGridPage />} />
          <Route path="/projects/:projectId/photos/:photoId" element={<PhotoDetailPage />} />
          <Route path="/projects/:projectId/compare" element={<PhotoComparePage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
