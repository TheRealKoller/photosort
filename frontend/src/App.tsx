import { useEffect } from 'react'
import { Link, Navigate, Outlet, Route, Routes, useNavigate } from 'react-router'

import { UNAUTHORIZED_EVENT } from './api/client'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { decodeUsername } from './auth/jwt'
import { clearToken, getToken } from './auth/token'
import { LoginPage } from './pages/LoginPage'

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
      <Outlet />
    </>
  )
}

function Placeholder() {
  return <p>Projekt-Grundgerüst — Funktionalität folgt aus den Specs in specs/features/.</p>
}

function App() {
  const navigate = useNavigate()

  useEffect(() => {
    function handleUnauthorized(): void {
      navigate('/login', { state: { reason: 'expired' } })
    }

    window.addEventListener(UNAUTHORIZED_EVENT, handleUnauthorized)
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, handleUnauthorized)
  }, [navigate])

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route path="/" element={<Placeholder />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
