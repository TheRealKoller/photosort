import { apiFetch } from './client'
import type { LoginRequest, TokenResponse } from './types'

export function login(payload: LoginRequest): Promise<TokenResponse> {
  return apiFetch('/auth/login', { method: 'POST', body: payload })
}
