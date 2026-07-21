import { render, screen } from '@testing-library/react'
import { type Location, MemoryRouter, Route, Routes, useLocation } from 'react-router'
import { beforeEach, describe, expect, it } from 'vitest'

import { setToken } from './token'
import { ProtectedRoute } from './ProtectedRoute'

function ProtectedContent() {
  return <p>Geschuetzter Inhalt</p>
}

let capturedLoginLocation: Location | undefined

function LoginStub() {
  capturedLoginLocation = useLocation()
  return <p>Login-Seite</p>
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/login" element={<LoginStub />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/projects/:id" element={<ProtectedContent />} />
        </Route>
      </Routes>
    </MemoryRouter>
  )
}

describe('ProtectedRoute', () => {
  beforeEach(() => {
    window.localStorage.clear()
    capturedLoginLocation = undefined
  })

  it('redirects to /login when no token is present', () => {
    renderAt('/projects/42')

    expect(screen.getByText('Login-Seite')).toBeInTheDocument()
    expect(screen.queryByText('Geschuetzter Inhalt')).not.toBeInTheDocument()
  })

  it('sets state.from to the originally requested route on redirect', () => {
    renderAt('/projects/42')

    expect(capturedLoginLocation?.state?.from?.pathname).toBe('/projects/42')
  })

  it('renders the outlet when a token is present', () => {
    setToken('valid-token')

    renderAt('/projects/42')

    expect(screen.getByText('Geschuetzter Inhalt')).toBeInTheDocument()
  })
})
