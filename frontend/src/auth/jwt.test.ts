import { describe, expect, it } from 'vitest'

import { decodeUsername } from './jwt'

function makeToken(payload: unknown): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
  const body = btoa(JSON.stringify(payload))
  return `${header}.${body}.signature-irrelevant-for-this-helper`
}

describe('decodeUsername', () => {
  it('extracts the username claim from a well-formed token', () => {
    const token = makeToken({ sub: '1', username: 'daniel', exp: 9999999999 })

    expect(decodeUsername(token)).toBe('daniel')
  })

  it('returns null for a malformed token', () => {
    expect(decodeUsername('not-a-jwt')).toBeNull()
  })

  it('returns null when the payload has no username claim', () => {
    const token = makeToken({ sub: '1' })

    expect(decodeUsername(token)).toBeNull()
  })
})
