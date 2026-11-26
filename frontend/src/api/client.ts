import { clearToken, getToken } from '../auth/token'
import type {
  ApiAntwort,
  ApiFetchOptions,
  ApiMethode,
  ApiPfadMitParametern,
  ApiPfadOhneParameter,
} from './types'
import type { paths } from './generated/schema'

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

const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? ''

/** Die Laufzeitform der Optionen - geprüft wird sie von den Signaturen darunter, nicht hier. */
type LaufzeitOptionen = {
  method?: string
  pathParams?: Record<string, unknown>
  query?: Record<string, unknown>
  body?: unknown
}

async function extractDetail(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (body !== null && typeof body === 'object' && 'detail' in body) {
      const detail = body.detail
      if (typeof detail === 'string') {
        return detail
      }
    }
  } catch {
    // Body ist kein (gueltiges) JSON - Fallback unten greift.
  }
  return `Unerwarteter Fehler (${response.status})`
}

/**
 * Ein Pfadparameter, fertig für die URL: ganzzahlige Werte erscheinen kanonisch, alle anderen
 * werden prozentkodiert. Ungeprüft wäre ein `/`, `?`, `#` oder `..` im Wert ein anderes
 * Request-Ziel.
 */
function kodiere(wert: unknown): string {
  if (typeof wert === 'number' && Number.isInteger(wert)) {
    return String(Math.trunc(wert))
  }
  return encodeURIComponent(String(wert))
}

/** Die Endpunktvorlage mit eingesetzten Pfadparametern - ein Literal aus `paths`, nie Freitext. */
function pfadBauen(vorlage: string, pathParams: Record<string, unknown> | undefined): string {
  return vorlage.replace(/\{([^}]+)\}/g, (_treffer, name: string) => {
    const wert = pathParams?.[name]
    if (wert === undefined || wert === null) {
      throw new Error(`Fehlender Pfadparameter "${name}" für ${vorlage}.`)
    }
    return kodiere(wert)
  })
}

/**
 * Query-Werte als `URLSearchParams`: Liste als wiederholter Schlüssel, `undefined` entfällt,
 * Boolean als `true`/`false`. Nie Zeichenketten-Verkettung - ein `&` oder `=` im Wert bliebe
 * sonst Struktur.
 */
function queryString(query: Record<string, unknown> | undefined): string {
  if (!query) {
    return ''
  }
  const params = new URLSearchParams()
  for (const [schluessel, wert] of Object.entries(query)) {
    if (wert === undefined) {
      continue
    }
    if (Array.isArray(wert)) {
      for (const eintrag of wert) {
        if (eintrag !== undefined) {
          params.append(schluessel, serialisiere(eintrag))
        }
      }
      continue
    }
    params.set(schluessel, serialisiere(wert))
  }
  const text = params.toString()
  return text ? `?${text}` : ''
}

function serialisiere(wert: unknown): string {
  if (typeof wert === 'boolean') {
    return wert ? 'true' : 'false'
  }
  return String(wert)
}

/**
 * Dünner Fetch-Wrapper, der einzige Ort, der tatsächlich HTTP-Requests an das Backend baut.
 *
 * Der erste Parameter ist die Endpunktvorlage aus `paths` (`"/photos/{photo_id}/image"`), die
 * Pfadparameter kommen getrennt - ein konkreter Pfad ist kein gültiger Aufruf. Hängt bei
 * vorhandenem Token automatisch den Authorization-Header an; löscht das Token und dispatcht
 * UNAUTHORIZED_EVENT bei 401.
 */
export function apiFetch<E extends ApiPfadMitParametern<'get'>>(
  endpunkt: E,
  optionen: ApiFetchOptions<E, 'get'> & { method?: 'get' },
): Promise<ApiAntwort<E, 'get'>>
export function apiFetch<E extends ApiPfadOhneParameter<'get'>>(
  endpunkt: E,
  optionen?: ApiFetchOptions<E, 'get'> & { method?: 'get' },
): Promise<ApiAntwort<E, 'get'>>
export function apiFetch<E extends keyof paths, M extends ApiMethode<E>>(
  endpunkt: E,
  optionen: ApiFetchOptions<E, M> & { method: M },
): Promise<ApiAntwort<E, M>>
/**
 * Die Variante für die gemockte Grenze der API-Modultests: sie liefert `Promise<unknown>` und kann
 * damit keine Typaussage behaupten. Erreichbar ist sie ausschließlich über `vi.mocked(apiFetch)`;
 * ein Produktivaufruf trifft sie nie (kein Wert ist `never`).
 */
export function apiFetch(endpunkt: never, optionen?: never): Promise<unknown>
export async function apiFetch(
  endpunkt: string,
  optionen: LaufzeitOptionen = {},
): Promise<unknown> {
  const pfad = `${pfadBauen(endpunkt, optionen.pathParams)}${queryString(optionen.query)}`
  const token = getToken()
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  const response = await fetch(`${API_BASE_URL}${pfad}`, {
    method: (optionen.method ?? 'get').toUpperCase(),
    headers,
    body: optionen.body !== undefined ? JSON.stringify(optionen.body) : undefined,
  })

  // /auth/login ist der einzige oeffentliche, unauthentifizierte Endpunkt - dessen eigener 401
  // (falsches Passwort/unbekannter User) ist ein regulaerer Login-Fehlschlag, keine
  // Session-Ablauf-Signalisierung. Die generische Behandlung wuerde sonst bei jedem
  // Tippfehler den globalen "Sitzung abgelaufen"-Redirect ausloesen und dabei ein evtl.
  // gesetztes state.from (Tiefenlink) zerstoeren (siehe App.tsx).
  const isLoginRequest = endpunkt === '/auth/login'
  if (response.status === 401 && !isLoginRequest) {
    clearToken()
    window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT))
    throw new ApiError(401, await extractDetail(response))
  }

  if (!response.ok) {
    throw new ApiError(response.status, await extractDetail(response))
  }

  if (response.status === 204) {
    return undefined
  }

  return await response.json()
}

/**
 * Wie apiFetch, aber liefert den rohen Response-Body als Blob statt JSON zu parsen - für
 * Foto-Bilddaten und Exportdateien (siehe api/photos.ts::fetchPhotoImageBlobUrl). Ein
 * <img src="..."> hängt keinen Authorization-Header an; solche Anfragen müssen deshalb über
 * fetch() mit Header laufen und das Ergebnis als Object-URL bereitstellen.
 */
export function apiFetchBlob<E extends ApiPfadMitParametern<'get'>>(
  endpunkt: E,
  optionen: ApiFetchOptions<E, 'get'>,
): Promise<Blob>
export function apiFetchBlob<E extends ApiPfadOhneParameter<'get'>>(
  endpunkt: E,
  optionen?: ApiFetchOptions<E, 'get'>,
): Promise<Blob>
export function apiFetchBlob(endpunkt: never, optionen?: never): Promise<Blob>
export async function apiFetchBlob(
  endpunkt: string,
  optionen: LaufzeitOptionen = {},
): Promise<Blob> {
  const pfad = `${pfadBauen(endpunkt, optionen.pathParams)}${queryString(optionen.query)}`
  const token = getToken()
  const headers: Record<string, string> = {}
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  const response = await fetch(`${API_BASE_URL}${pfad}`, { headers })

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
