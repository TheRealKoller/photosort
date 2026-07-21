import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router'

import { login } from '../api/auth'
import { ApiError } from '../api/client'
import { getToken, setToken } from '../auth/token'

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
    <main>
      <h1>PhotoSort</h1>
      {state.reason === 'expired' && !errorDetail && <p>Sitzung abgelaufen — bitte erneut anmelden.</p>}
      {errorDetail && <p role="alert">{errorDetail}</p>}
      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="login-username">Benutzername</label>
          <input
            id="login-username"
            name="username"
            type="text"
            autoComplete="username"
            required
            autoFocus
            disabled={mutation.isPending}
            value={username}
            onChange={(event) => setUsername(event.target.value)}
          />
        </div>
        <div>
          <label htmlFor="login-password">Passwort</label>
          <input
            id="login-password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            disabled={mutation.isPending}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </div>
        <button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? 'Anmelden…' : 'Anmelden'}
        </button>
      </form>
    </main>
  )
}
