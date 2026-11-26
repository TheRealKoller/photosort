import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { setToken } from '../auth/token'
import { apiFetch, apiFetchBlob, ApiError } from './client'

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function letzteUrl(): string {
  const [url] = vi.mocked(fetch).mock.calls[0] ?? []
  return typeof url === 'string' ? url : String(url)
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

    const result = await apiFetch('/projects/{project_id}', { pathParams: { project_id: 1 } })

    expect(result).toEqual({ id: 1, name: 'Costa Rica' })
  })

  it('throws an ApiError with the backend detail message on 4xx', async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse(404, { detail: 'Projekt nicht gefunden.' }))

    await expect(
      apiFetch('/projects/{project_id}', { pathParams: { project_id: 999 } }),
    ).rejects.toMatchObject(new ApiError(404, 'Projekt nicht gefunden.'))
  })

  it('falls back to a generic message when the detail field is missing', async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse(500, {}))

    await expect(apiFetch('/projects')).rejects.toMatchObject({ status: 500 })
  })

  it('falls back to a generic message when the response body is not valid JSON', async () => {
    vi.mocked(fetch).mockResolvedValue(new Response('not json', { status: 500 }))

    const error = await apiFetch('/projects').catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(500)
    expect((error as ApiError).detail.length).toBeGreaterThan(0)
  })

  it('resolves 204 with undefined, without parsing a body', async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }))

    const result = await apiFetch('/projects/{project_id}/overview-seen', {
      method: 'PUT',
      pathParams: { project_id: 1 },
    })

    expect(result).toBeUndefined()
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
      new Response('fake-image-bytes', { status: 200, headers: { 'Content-Type': 'image/jpeg' } }),
    )

    const result = await apiFetchBlob('/photos/{photo_id}/image', {
      pathParams: { photo_id: 1 },
      query: { variant: 'thumbnail' },
    })

    const [, init] = vi.mocked(fetch).mock.calls[0]
    const headers = init?.headers as Record<string, string>
    expect(headers.Authorization).toBe('Bearer my-token')
    expect(result.type).toBe('image/jpeg')
    expect(result.size).toBe(16)
  })

  it('apiFetchBlob throws an ApiError with the backend detail on a non-2xx response', async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse(404, { detail: 'Bild wird noch verarbeitet.' }))

    await expect(
      apiFetchBlob('/photos/{photo_id}/image', {
        pathParams: { photo_id: 1 },
        query: { variant: 'thumbnail' },
      }),
    ).rejects.toMatchObject(new ApiError(404, 'Bild wird noch verarbeitet.'))
  })

  it('apiFetchBlob clears the token and dispatches photosort:unauthorized on 401', async () => {
    setToken('expired-token')
    vi.mocked(fetch).mockResolvedValue(jsonResponse(401, { detail: 'Nicht authentifiziert.' }))
    const listener = vi.fn()
    window.addEventListener('photosort:unauthorized', listener)

    await expect(
      apiFetchBlob('/photos/{photo_id}/image', {
        pathParams: { photo_id: 1 },
        query: { variant: 'thumbnail' },
      }),
    ).rejects.toBeInstanceOf(ApiError)

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
      apiFetch('/auth/login', { method: 'POST', body: { username: 'x', password: 'y' } }),
    ).rejects.toBeInstanceOf(ApiError)

    expect(listener).toHaveBeenCalledTimes(0)

    window.removeEventListener('photosort:unauthorized', listener)
  })

  it('treats /auth/login as an exact match, never as a prefix', async () => {
    // Ein Praefix-Vergleich liesse auch einen anderen Endpunkt mit demselben Anfang als
    // "öffentlich" durchgehen - dann bliebe ein dortiger 401 ohne globale Abmeldung.
    setToken('expired-token')
    vi.mocked(fetch).mockResolvedValue(jsonResponse(401, { detail: 'Nicht authentifiziert.' }))
    const listener = vi.fn()
    window.addEventListener('photosort:unauthorized', listener)

    await expect(apiFetch('/persons')).rejects.toBeInstanceOf(ApiError)

    expect(listener).toHaveBeenCalledTimes(1)

    window.removeEventListener('photosort:unauthorized', listener)
  })

  it('encodes every path parameter and keeps integers canonical', async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse(200, { photo_id: 3, motif_key: 'x', applies: true }),
    )

    await apiFetch('/photos/{photo_id}/motif-corrections/{motif_key}', {
      method: 'PUT',
      pathParams: { photo_id: 3, motif_key: 'a/b?c#d e' },
      body: { applies: true },
    })

    expect(letzteUrl()).toBe('/photos/3/motif-corrections/a%2Fb%3Fc%23d%20e')
  })

  it('encodes a traversal attempt instead of letting it change the request target', async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse(200, { photo_id: 1, motif_key: 'x', applies: true }),
    )

    await apiFetch('/photos/{photo_id}/motif-corrections/{motif_key}', {
      method: 'PUT',
      pathParams: { photo_id: 1, motif_key: '../x' },
      body: { applies: true },
    })

    expect(letzteUrl()).toBe('/photos/1/motif-corrections/..%2Fx')
  })

  it('serialises query values through URLSearchParams', async () => {
    // Liste als wiederholter Schluessel, `undefined` entfaellt, Boolean als true/false.
    vi.mocked(fetch).mockResolvedValue(jsonResponse(200, { items: [], total: 0 }))

    await apiFetch('/projects/{project_id}/photos', {
      pathParams: { project_id: 1 },
      query: { person_id: [7, 8], limit: undefined, offset: 0 },
    })

    expect(letzteUrl()).toBe('/projects/1/photos?person_id=7&person_id=8&offset=0')
  })

  it('writes a boolean query value as true or false', async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse(200, { items: [], total: 0, open_count: 0, auto_decided_group_count: 0 }),
    )

    await apiFetch('/projects/{project_id}/ausschuss', {
      pathParams: { project_id: 1 },
      query: { auto_decided: true },
    })

    expect(letzteUrl()).toBe('/projects/1/ausschuss?auto_decided=true')
  })

  it('throws instead of sending a template with an unfilled placeholder', async () => {
    // Der Verteidigungspunkt: ein fehlender Wert darf nie als Platzhalter in der URL landen.
    vi.mocked(fetch).mockResolvedValue(jsonResponse(200, {}))

    const unvollstaendig = {} as { photo_id: number }

    await expect(
      apiFetch('/photos/{photo_id}/faces', { pathParams: unvollstaendig }),
    ).rejects.toThrow(/photo_id/)
    expect(fetch).not.toHaveBeenCalled()
  })

  it('rejects a concrete path, a missing path parameter, a body without endpoint and an unknown method', () => {
    // Typgrenze als `@ts-expect-error`-Proben: sie laufen ueber `tsc`, nicht zur Laufzeit.
    // `if (false)`: der Block wird geprueft, aber nie ausgefuehrt - ein ausgefuehrter Aufruf
    // liefe gegen den fetch-Mock und erzeugte nur eine unhandled rejection.
    // Jede Probe wird rot, sobald die Grenze aufgeweicht wird.
    if (false) {
      // @ts-expect-error - ein konkreter Pfad ist kein Endpunkt
      void apiFetch('/projects/1')
      // @ts-expect-error - fehlender Pfadparameter
      void apiFetch('/projects/{project_id}')
      // @ts-expect-error - kein `body` an einem koerperlosen Endpunkt
      void apiFetch('/projects/{project_id}', { pathParams: { project_id: 1 }, body: {} })
      // @ts-expect-error - diese Methode fuehrt der Endpunkt nicht
      void apiFetch('/projects/{project_id}', { method: 'patch', pathParams: { project_id: 1 } })
    }
  })
})
