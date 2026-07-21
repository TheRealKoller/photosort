import { beforeEach, describe, expect, it } from 'vitest'

import { clearToken, getToken, setToken } from './token'

describe('auth/token', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('returns null when no token is stored', () => {
    expect(getToken()).toBeNull()
  })

  it('stores and retrieves a token', () => {
    setToken('abc.def.ghi')

    expect(getToken()).toBe('abc.def.ghi')
  })

  it('removes the token on clearToken', () => {
    setToken('abc.def.ghi')

    clearToken()

    expect(getToken()).toBeNull()
  })
})
