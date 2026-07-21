import { useEffect } from 'react'
import { useNavigate } from 'react-router'

import { UNAUTHORIZED_EVENT } from '../api/client'

/**
 * Reagiert auf das globale photosort:unauthorized-Event (ausgeloest von api/client.ts bei
 * einem 401 auf einem geschuetzten Endpunkt - siehe specs/features/0006-auth.md) und navigiert
 * zu /login mit state.reason = "expired", damit LoginPage einen neutralen
 * Sitzungs-abgelaufen-Hinweis statt eines Fehlerbanners zeigen kann.
 */
export function useUnauthorizedRedirect(): void {
  const navigate = useNavigate()

  useEffect(() => {
    function handleUnauthorized(): void {
      navigate('/login', { state: { reason: 'expired' } })
    }

    window.addEventListener(UNAUTHORIZED_EVENT, handleUnauthorized)
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, handleUnauthorized)
  }, [navigate])
}
