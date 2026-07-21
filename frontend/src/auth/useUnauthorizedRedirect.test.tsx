import { act, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it } from 'vitest'

import { UNAUTHORIZED_EVENT } from '../api/client'
import { useUnauthorizedRedirect } from './useUnauthorizedRedirect'

function Probe() {
  useUnauthorizedRedirect()
  return <p>Geschuetzter Bereich</p>
}

function LoginStub() {
  return <p>Login-Seite</p>
}

function renderProbe() {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="/" element={<Probe />} />
        <Route path="/login" element={<LoginStub />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('useUnauthorizedRedirect', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('navigates to /login with state.reason "expired" on the global unauthorized event', () => {
    renderProbe()
    expect(screen.getByText('Geschuetzter Bereich')).toBeInTheDocument()

    act(() => {
      window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT))
    })

    expect(screen.getByText('Login-Seite')).toBeInTheDocument()
  })
})
