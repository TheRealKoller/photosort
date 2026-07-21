import { Navigate, Outlet, useLocation } from 'react-router'

import { getToken } from './token'

/**
 * Prueft ausschliesslich die Praesenz eines Tokens (kein Server-Roundtrip, keine
 * clientseitige Ablaufpruefung) - siehe specs/features/0006-auth.md. "Token vorhanden, aber
 * ungueltig/abgelaufen" faengt der globale 401-Handler in api/client.ts reaktiv ab.
 */
export function ProtectedRoute() {
  const location = useLocation()
  const token = getToken()

  if (!token) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }

  return <Outlet />
}
