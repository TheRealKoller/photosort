import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router'

import { login } from '../api/auth'
import { ApiError } from '../api/client'
import { getToken, setToken } from '../auth/token'
import { BrandMark } from '../components/BrandMark'
import { Alert } from '../components/ui/alert'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'

interface LocationState {
  from?: { pathname: string }
  reason?: 'expired'
}

export function LoginPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const state = (location.state ?? {}) as LocationState
  const redirectTarget = state.from?.pathname ?? '/'

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  const mutation = useMutation({
    mutationFn: login,
    onSuccess: (data) => {
      setToken(data.access_token)
      navigate(redirectTarget, { replace: true })
    },
    onError: () => {
      setPassword('')
    },
  })

  // Direkter Aufruf von /login bei bereits vorhandenem Token: sofortiger Redirect ohne
  // Formular anzuzeigen (siehe specs/features/0006-auth.md).
  if (getToken()) {
    return <Navigate to={redirectTarget} replace />
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault()
    mutation.mutate({ username, password })
  }

  const errorDetail =
    mutation.isError && mutation.error instanceof ApiError ? mutation.error.detail : null

  return (
    /*
     * Anmeldung ohne umschliessende Karte und linksbuendig statt zentriert (Vorlage, Artboard 1):
     * das Formular IST die Seite, eine Karte darauf waere eine Flaeche ohne Gegenueber. Die
     * Vorlage begruendet die Kargheit ausdruecklich - der Bildschirm wird zweimal im Jahr
     * gesehen, danach bleibt die PWA angemeldet.
     */
    <main className="flex min-h-screen flex-col justify-center bg-bg px-8 py-10 sm:px-10">
      <div className="mx-auto w-full max-w-sm">
        <BrandMark className="mb-7" />
        <h1 className="mb-1 text-3xl">PhotoSort</h1>
        <p className="mb-7 text-sm text-text">Melde dich an, um deine Ordner zu sortieren.</p>

        {state.reason === 'expired' && !errorDetail && (
          <p className="mb-4 text-sm text-text">Sitzung abgelaufen — bitte erneut anmelden.</p>
        )}
        {errorDetail && (
          <div className="mb-4">
            <Alert>{errorDetail}</Alert>
          </div>
        )}
        <form onSubmit={handleSubmit} className="flex flex-col gap-3.5">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="login-username" className="text-xs text-text">
              Benutzername
            </label>
            {/* 48px hohe Felder statt der Standard-44px: die Vorlage begruendet das mit der
                einhaendigen Bedienung am Telefon. */}
            <Input
              id="login-username"
              name="username"
              type="text"
              autoComplete="username"
              required
              autoFocus
              disabled={mutation.isPending}
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              className="h-12"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="login-password" className="text-xs text-text">
              Passwort
            </label>
            <Input
              id="login-password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              disabled={mutation.isPending}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="h-12"
            />
          </div>
          <Button type="submit" busy={mutation.isPending} className="mt-3 h-[50px] w-full text-base">
            {mutation.isPending ? 'Anmelden…' : 'Anmelden'}
          </Button>
        </form>

        {/* Verortungszeile der Vorlage: sagt in einem Satz, wo die Daten liegen. */}
        <p className="mt-6 text-center text-xs text-text">
          Läuft auf unserem eigenen Server. Nichts verlässt das Haus, solange die Erkennung nicht
          eingeschaltet ist.
        </p>
      </div>
    </main>
  )
}
