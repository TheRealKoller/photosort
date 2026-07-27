import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { setToken } from '../auth/token'
import { apiFetch, apiFetchBlob, ApiError } from './client'

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('api/client', () => {
  beforeEach(() => {
    window.localStorage.clear()
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('does not attach an Authorization header when no token is stored', async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse(200, { ok: true }))

    await apiFetch('/projects')

    const [, init] = vi.mocked(fetch).mock.calls[0]
    const headers = init?.headers as Record<string, string>
    expect(headers.Authorization).toBeUndefined()
  })

  it('attaches the Authorization header when a token is stored', async () => {
    setToken('my-token')
    vi.mocked(fetch).mockResolvedValue(jsonResponse(200, { ok: true }))

    await apiFetch('/projects')

    const [, init] = vi.mocked(fetch).mock.calls[0]
    const headers = init?.headers as Record<string, string>
    expect(headers.Authorization).toBe('Bearer my-token')
  })

  it('resolves with the parsed JSON body on success', async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse(200, { id: 1, name: 'Costa Rica' }))

    const result = await apiFetch<{ id: number; name: string }>('/projects/1')

    expect(result).toEqual({ id: 1, name: 'Costa Rica' })
  })

  it('throws an ApiError with the backend detail message on 4xx', async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse(404, { detail: 'Projekt nicht gefunden.' }))

    await expect(apiFetch('/projects/999')).rejects.toMatchObject(
      new ApiError(404, 'Projekt nicht gefunden.')
    )
  })

  it('falls back to a generic message when the detail field is missing', async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse(500, {}))

    await expect(apiFetch('/projects')).rejects.toMatchObject({ status: 500 })
  })

  it('falls back to a generic message when the response body is not valid JSON', async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response('not json', { status: 500 })
    )

    const error = await apiFetch('/projects').catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(500)
    expect((error as ApiError).detail.length).toBeGreaterThan(0)
  })

  it('clears the token and dispatches photosort:unauthorized exactly once on 401', async () => {
    setToken('expired-token')
    vi.mocked(fetch).mockResolvedValue(jsonResponse(401, { detail: 'Nicht authentifiziert.' }))
    const listener = vi.fn()
    window.addEventListener('photosort:unauthorized', listener)

    await expect(apiFetch('/projects')).rejects.toBeInstanceOf(ApiError)

    expect(listener).toHaveBeenCalledTimes(1)
    expect(window.localStorage.getItem('photosort_token')).toBeNull()

    window.removeEventListener('photosort:unauthorized', listener)
  })

  it('fetches a blob with the Authorization header attached (apiFetchBlob)', async () => {
    setToken('my-token')
    vi.mocked(fetch).mockResolvedValue(
      new Response('fake-image-bytes', { status: 200, headers: { 'Content-Type': 'image/jpeg' } })
    )

    const result = await apiFetchBlob('/photos/1/image?variant=thumbnail')

    const [, init] = vi.mocked(fetch).mock.calls[0]
    const headers = init?.headers as Record<string, string>
    expect(headers.Authorization).toBe('Bearer my-token')
    expect(result.type).toBe('image/jpeg')
    expect(result.size).toBe(16)
  })

  it('apiFetchBlob throws an ApiError with the backend detail on a non-2xx response', async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse(404, { detail: 'Bild wird noch verarbeitet.' }))

    await expect(apiFetchBlob('/photos/1/image?variant=thumbnail')).rejects.toMatchObject(
      new ApiError(404, 'Bild wird noch verarbeitet.')
    )
  })

  it('apiFetchBlob clears the token and dispatches photosort:unauthorized on 401', async () => {
    setToken('expired-token')
    vi.mocked(fetch).mockResolvedValue(jsonResponse(401, { detail: 'Nicht authentifiziert.' }))
    const listener = vi.fn()
    window.addEventListener('photosort:unauthorized', listener)

    await expect(apiFetchBlob('/photos/1/image?variant=thumbnail')).rejects.toBeInstanceOf(ApiError)

    expect(listener).toHaveBeenCalledTimes(1)
    expect(window.localStorage.getItem('photosort_token')).toBeNull()

    window.removeEventListener('photosort:unauthorized', listener)
  })

  it('does not clear the token or dispatch photosort:unauthorized for a 401 from /auth/login', async () => {
    // /auth/login ist der einzige oeffentliche, unauthentifizierte Endpunkt - dessen eigener
    // 401 (falsches Passwort/unbekannter User) ist ein Login-Fehlschlag, keine
    // Session-Ablauf-Signalisierung. Wuerde apiFetch das generisch behandeln, wuerde ein
    // simpler Tippfehler beim Login den globalen "Sitzung abgelaufen"-Redirect ausloesen und
    // dabei state.from eines Tiefenlinks zerstoeren (siehe App.tsx).
    vi.mocked(fetch).mockResolvedValue(jsonResponse(401, { detail: 'Ungültige Anmeldedaten' }))
    const listener = vi.fn()
    window.addEventListener('photosort:unauthorized', listener)

    await expect(
      apiFetch('/auth/login', { method: 'POST', body: { username: 'x', password: 'y' } })
    ).rejects.toBeInstanceOf(ApiError)

    expect(listener).toHaveBeenCalledTimes(0)

    window.removeEventListener('photosort:unauthorized', listener)
  })
})
