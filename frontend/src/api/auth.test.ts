import { describe, expect, it, vi } from 'vitest'

import { apiFetch } from './client'
import { login } from './auth'

vi.mock('./client', () => ({
  apiFetch: vi.fn(),
}))

describe('api/auth', () => {
  it('posts username/password to /auth/login and returns the token response', async () => {
    vi.mocked(apiFetch).mockResolvedValue({ access_token: 'token-123', token_type: 'bearer' })

    const result = await login({ username: 'daniel', password: 'secret' })

    expect(apiFetch).toHaveBeenCalledWith('/auth/login', {
      method: 'POST',
      body: { username: 'daniel', password: 'secret' },
    })
    expect(result).toEqual({ access_token: 'token-123', token_type: 'bearer' })
  })
})
