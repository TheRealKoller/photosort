/**
 * Zieladresse des Pruefstacks - fest hinterlegt, nur gegen eine enge Allowlist ueberschreibbar.
 *
 * Security-Muss-Kriterium M7 der Spec 0174: Die Werkzeuge sprechen die im Playwright-Config fest
 * hinterlegte lokale Adresse an; eine frei ueberschreibbare Basis-URL ist ausdruecklich nicht
 * vorgesehen. Die hier erlaubte Ausnahme ist die dort genannte: eine Allowlist analog
 * `scripts/seed-opencloud-demo.py::validate_demo_base_url`, inklusive der dortigen Port-Pflicht.
 * Praktischer Anlass: laeuft auf demselben Rechner bereits ein normaler PhotoSort-Stack, sind
 * 8000/8080 belegt und der Pruefstack braucht andere Host-Ports.
 *
 * BEWUSST "localhost" UND NICHT "127.0.0.1" ALS DEFAULT (Edge Case E5): Die Origin des Browsers
 * muss zu CORS_ALLOWED_ORIGINS des Backends passen, und die beiden Schreibweisen sind CORS-seitig
 * VERSCHIEDENE Origins. Die 127.0.0.1-Bindung der Container-Ports betrifft nur, wer von aussen
 * verbinden darf - nicht die im Browser verwendete Adresse.
 */

export const DEFAULT_BASE_URL = 'http://localhost:8080'
export const BASE_URL_ENV_VAR = 'PHOTOSORT_E2E_BASE_URL'

const ALLOWED_HOSTS = new Set(['localhost', '127.0.0.1'])

export function resolveBaseUrl(raw: string | undefined): string {
  if (raw === undefined || raw.trim() === '') {
    return DEFAULT_BASE_URL
  }
  let parsed: URL
  try {
    parsed = new URL(raw)
  } catch {
    throw new Error(
      `${BASE_URL_ENV_VAR} ist keine gueltige URL. Erwartet: http://<localhost|127.0.0.1>:<port>.`
    )
  }
  // Port explizit verlangt (gleicher Copilot-Review-Fund wie im Python-Pendant): "http://localhost"
  // mit implizitem Port 80 koennte einen ganz anderen lokalen Dienst treffen.
  if (parsed.protocol !== 'http:' || !ALLOWED_HOSTS.has(parsed.hostname) || parsed.port === '') {
    throw new Error(
      `${BASE_URL_ENV_VAR} zeigt nicht auf einen lokalen Pruefstack. Erwartet: ` +
        'http://<localhost|127.0.0.1>:<port>, Port explizit angegeben. Abbruch, um nicht ' +
        'versehentlich gegen eine echte Instanz zu laufen.'
    )
  }
  return parsed.origin
}

export const BASE_URL = resolveBaseUrl(process.env[BASE_URL_ENV_VAR])
