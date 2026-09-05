/**
 * Verlaesslichkeitsregime als Konfiguration (ADR 0057 Punkt 7, Akzeptanzkriterium "ein Fehlschlag
 * ist ein verlaessliches Signal"). Die drei entscheidenden Werte - `retries: 0`, `forbidOnly:
 * true`, `workers: 1` - sind zusaetzlich per Assertion in `tests/toolchain.spec.ts` gebunden,
 * damit ein spaeteres "die Flakes wegkonfigurieren" laut scheitert statt still zu gelingen.
 */

import { defineConfig } from '@playwright/test'

import { BASE_URL } from './lib/baseUrl.ts'
import { ARTIFACTS_DIR, AUTH_STATE_FILE } from './lib/paths.ts'
import { VIEWPORTS } from './lib/viewports.ts'

// Nur bei 360px sinnvoll bzw. nur einmal noetig - siehe Kommentare an den jeweiligen Specs.
const MOBILE_ONLY = [/tap-targets\.spec\.ts/, /no-horizontal-scroll\.spec\.ts/]
const DESKTOP_ONLY = [/grid-columns\.spec\.ts/, /login\.spec\.ts/, /toolchain\.spec\.ts/]

export default defineConfig({
  testDir: './tests',
  outputDir: `${ARTIFACTS_DIR}/test-results`,

  // Kein Wiederholen, auch nicht in CI: Playwrights Vorlage setzt dort 2 - ausdruecklich
  // abgewaehlt, weil Wiederholen aus einem sprunghaften Test einen UNSICHTBAR sprunghaften macht.
  retries: 0,
  // Unbedingt, nicht nur in CI: ein vergessenes test.only wuerde den Pruefsatz still auf einen
  // einzigen Fall zusammenschrumpfen lassen.
  forbidOnly: true,
  // Alle Specs teilen sich EINEN geseedeten Datenbestand.
  workers: 1,
  fullyParallel: false,

  reporter: [['list'], ['html', { outputFolder: `${ARTIFACTS_DIR}/report`, open: 'never' }]],

  use: {
    baseURL: BASE_URL,
    // Artefakte nur im Fehlerfall - ein roter Lauf ohne Bild waere fuer einen Entwickler ohne
    // Augen genauso blind wie der Zustand vor dieser Ebene.
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'off',
  },

  projects: [
    {
      name: 'setup',
      testDir: './setup',
      testMatch: /auth\.setup\.ts/,
      use: { viewport: VIEWPORTS.desktop },
    },
    {
      name: 'mobile',
      dependencies: ['setup'],
      testIgnore: DESKTOP_ONLY,
      use: { viewport: VIEWPORTS.mobile, storageState: AUTH_STATE_FILE },
    },
    {
      name: 'desktop',
      dependencies: ['setup'],
      testIgnore: MOBILE_ONLY,
      use: { viewport: VIEWPORTS.desktop, storageState: AUTH_STATE_FILE },
    },
  ],
})
