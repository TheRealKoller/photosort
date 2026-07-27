import { clearToken, getToken } from '../auth/token'

export const UNAUTHORIZED_EVENT = 'photosort:unauthorized'

export class ApiError extends Error {
  readonly status: number
  readonly detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

interface ApiFetchOptions {
  method?: string
  body?: unknown
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

async function extractDetail(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (
      body !== null &&
      typeof body === 'object' &&
      'detail' in body &&
      typeof (body as { detail: unknown }).detail === 'string'
    ) {
      return (body as { detail: string }).detail
    }
  } catch {
    // Body ist kein (gueltiges) JSON - Fallback unten greift.
  }
  return `Unerwarteter Fehler (${response.status})`
}

/**
 * Duenner Fetch-Wrapper, der einzige Ort, der tatsaechlich HTTP-Requests an das Backend baut
 * (siehe decisions/0004-frontend-app-shell.md). Haengt bei vorhandenem Token automatisch den
 * Authorization-Header an; loescht das Token und dispatcht UNAUTHORIZED_EVENT bei 401.
 */
export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? 'GET',
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  })

  // /auth/login ist der einzige oeffentliche, unauthentifizierte Endpunkt - dessen eigener 401
  // (falsches Passwort/unbekannter User) ist ein regulaerer Login-Fehlschlag, keine
  // Session-Ablauf-Signalisierung. Die generische Behandlung wuerde sonst bei jedem
  // Tippfehler den globalen "Sitzung abgelaufen"-Redirect ausloesen und dabei ein evtl.
  // gesetztes state.from (Tiefenlink) zerstoeren (siehe App.tsx).
  const isLoginRequest = path === '/auth/login'
  if (response.status === 401 && !isLoginRequest) {
    clearToken()
    window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT))
    throw new ApiError(401, await extractDetail(response))
  }

  if (!response.ok) {
    throw new ApiError(response.status, await extractDetail(response))
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

/**
 * Wie apiFetch, aber liefert den rohen Response-Body als Blob statt JSON zu parsen - fuer
 * Foto-Bilddaten (siehe api/photos.ts::fetchPhotoImageBlobUrl). Ein <img src="..."> haengt
 * keinen Authorization-Header an; Bild-Anfragen muessen deshalb ueber fetch() mit Header laufen
 * und das Ergebnis als Object-URL bereitstellen (specs/features/0002-manual-categorization.md).
 */
export async function apiFetchBlob(path: string): Promise<Blob> {
  const token = getToken()
  const headers: Record<string, string> = {}
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { headers })

  if (response.status === 401) {
    clearToken()
    window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT))
    throw new ApiError(401, await extractDetail(response))
  }

  if (!response.ok) {
    throw new ApiError(response.status, await extractDetail(response))
  }

  return response.blob()
}
