/**
 * Playwright-Fixture auf dem Sitzungsbaustein: sie instrumentiert JEDEN Test-Kontext und setzt
 * danach zwei Zusicherungen fuer ALLE Specs zentral durch - keine unbehandelten Seitenfehler,
 * keine 5xx-Antworten.
 *
 * Randfall E3 (bewusst hier geloest): Der Pruefstack laeuft ohne OpenCloud, der Ordner-Browser
 * erzeugt dort also ERWARTETE Fehler. Zulaessig ist dafuer ausschliesslich eine eng umrissene, im
 * jeweiligen Spec sichtbare Erwartung (dieser Endpunkt, dieser Statuscode) ueber die Option
 * `expectedServerErrors` - keine globale Ausnahmeliste hier, kein Herabsetzen der Schwelle von
 * 5xx auf "egal". Ohne diese Grenze waere die zentrale Zusage praktisch abgeschaltet.
 */

import { test as base, expect } from '@playwright/test'

import { createSessionLog, instrumentContext, serverErrors, type SessionLog } from './session.ts'

export interface ExpectedServerError {
  /** Muss auf die vollstaendige Anfrage-URL passen. */
  urlPattern: RegExp
  status: number
}

interface Fixtures {
  sessionLog: SessionLog
}

interface Options {
  expectedServerErrors: ExpectedServerError[]
}

export const test = base.extend<Fixtures & Options>({
  expectedServerErrors: [[], { option: true }],

  sessionLog: [
    async ({ context, expectedServerErrors }, use) => {
      const log = createSessionLog()
      instrumentContext(context, log)

      await use(log)

      expect(
        log.pageErrors.map((error) => error.message),
        'unbehandelte Seitenfehler im Browser'
      ).toEqual([])

      const unexpected = serverErrors(log).filter(
        (request) =>
          !expectedServerErrors.some(
            (expected) =>
              expected.status === request.status && expected.urlPattern.test(request.url)
          )
      )
      expect(
        unexpected.map((request) => `${request.method} ${request.url} -> ${request.status}`),
        'unerwartete 5xx-Antworten'
      ).toEqual([])
    },
    // "auto": die Zusage darf nicht davon abhaengen, dass ein Spec die Fixture anfordert.
    { auto: true },
  ],
})

export { expect }
