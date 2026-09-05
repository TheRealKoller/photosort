/**
 * Der gemeinsame Sitzungsbaustein: er erzeugt jeden Browser-Kontext-Mitschnitt und schreibt dabei
 * IMMER mit - Konsolenmeldungen, unbehandelte Seitenfehler und fehlgeschlagene bzw. mit Status
 * >= 400 beantwortete Netzwerkaufrufe.
 *
 * Das ist bewusst eine Eigenschaft des WERKZEUGS und keine Disziplinanforderung an den Aufrufer
 * (ADR 0058 Punkt 3): Das Akzeptanzkriterium "Laufzeitfehler werden wahrgenommen" darf nicht davon
 * abhaengen, dass bei jedem Ad-hoc-Skript jemand daran denkt, `page.on('console')` zu verdrahten.
 * Deshalb haengen die Zuhoerer am BrowserContext und nicht an einer einzelnen Page - auch eine
 * spaeter geoeffnete Seite ist damit automatisch instrumentiert.
 */

import type { BrowserContext } from '@playwright/test'

/** Ab diesem Status gilt eine Antwort als fehlgeschlagener Netzwerkaufruf (Akzeptanzkriterium). */
export const FAILED_REQUEST_STATUS_THRESHOLD = 400
/** Ab diesem Status gilt eine Antwort als Serverfehler - die zentrale Zusicherung der Fixture. */
export const SERVER_ERROR_STATUS_THRESHOLD = 500

export interface RecordedConsoleMessage {
  type: string
  text: string
  location: string
}

export interface RecordedPageError {
  message: string
}

export interface RecordedFailedRequest {
  method: string
  url: string
  /** `null`, wenn der Aufruf gar keine Antwort bekommen hat (Verbindungsfehler, Abbruch). */
  status: number | null
  failure: string | null
}

export interface SessionLog {
  console: RecordedConsoleMessage[]
  pageErrors: RecordedPageError[]
  failedRequests: RecordedFailedRequest[]
}

export function createSessionLog(): SessionLog {
  return { console: [], pageErrors: [], failedRequests: [] }
}

export function instrumentContext(context: BrowserContext, log: SessionLog): void {
  context.on('console', (message) => {
    const location = message.location()
    log.console.push({
      type: message.type(),
      text: message.text(),
      location: `${location.url}:${location.lineNumber}:${location.columnNumber}`,
    })
  })
  context.on('weberror', (error) => {
    log.pageErrors.push({ message: error.error().message })
  })
  context.on('response', (response) => {
    if (response.status() >= FAILED_REQUEST_STATUS_THRESHOLD) {
      log.failedRequests.push({
        method: response.request().method(),
        url: response.url(),
        status: response.status(),
        failure: null,
      })
    }
  })
  context.on('requestfailed', (request) => {
    log.failedRequests.push({
      method: request.method(),
      url: request.url(),
      status: null,
      failure: request.failure()?.errorText ?? 'unbekannter Netzwerkfehler',
    })
  })
}

export function consoleErrors(log: SessionLog): RecordedConsoleMessage[] {
  return log.console.filter((message) => message.type === 'error')
}

export function serverErrors(log: SessionLog): RecordedFailedRequest[] {
  return log.failedRequests.filter(
    (request) => request.status !== null && request.status >= SERVER_ERROR_STATUS_THRESHOLD
  )
}

export function formatSessionLog(log: SessionLog, heading: string): string {
  const lines = [heading, '']

  lines.push(`Konsolenmeldungen (${log.console.length}):`)
  lines.push(
    ...(log.console.length === 0
      ? ['  (keine)']
      : log.console.map((message) => `  [${message.type}] ${message.text}  @ ${message.location}`))
  )

  lines.push('', `Unbehandelte Seitenfehler (${log.pageErrors.length}):`)
  lines.push(
    ...(log.pageErrors.length === 0
      ? ['  (keine)']
      : log.pageErrors.map((error) => `  ${error.message}`))
  )

  lines.push('', `Fehlgeschlagene Netzwerkaufrufe (${log.failedRequests.length}):`)
  lines.push(
    ...(log.failedRequests.length === 0
      ? ['  (keine)']
      : log.failedRequests.map(
          (request) =>
            `  ${request.method} ${request.url} -> ${request.status ?? request.failure ?? '?'}`
        ))
  )

  return `${lines.join('\n')}\n`
}
