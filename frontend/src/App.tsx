import { Link, Navigate, Outlet, Route, Routes, useNavigate } from 'react-router'

import { ProtectedRoute } from './auth/ProtectedRoute'
import { decodeUsername } from './auth/jwt'
import { clearToken, getToken } from './auth/token'
import { useUnauthorizedRedirect } from './auth/useUnauthorizedRedirect'
import { LoginPage } from './pages/LoginPage'
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
    <>
      <header>
        <Link to="/">PhotoSort</Link>
        {username && <span>Angemeldet als {username}</span>}
        <button type="button" onClick={handleLogout}>
          Abmelden
        </button>
      </header>
      <main>
        <Outlet />
      </main>
    </>
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
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
