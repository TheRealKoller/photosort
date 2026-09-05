/**
 * Vorgelagertes Setup-Projekt: einmal anmelden, Sitzungszustand speichern, alle uebrigen Specs
 * starten angemeldet (ADR 0058 Punkt 7 - kein wiederholtes Anmelden pro Test).
 *
 * Der Token liegt im localStorage (`photosort_token`), `storageState` traegt ihn mit. Genau EIN
 * Spec (`tests/login.spec.ts`) prueft das Anmeldeformular selbst - der einzige Pfad, den dieses
 * Setup-Projekt sonst verdeckte.
 */

import { mkdirSync } from 'node:fs'
import { test as setup, expect } from '@playwright/test'

import { logIn } from '../lib/auth.ts'
import { TOKEN_STORAGE_KEY } from '../lib/authState.ts'
import { AUTH_DIR, AUTH_STATE_FILE } from '../lib/paths.ts'

setup('anmelden und Sitzungszustand speichern', async ({ page }) => {
  await logIn(page)

  const token = await page.evaluate(
    (schluessel) => window.localStorage.getItem(schluessel),
    TOKEN_STORAGE_KEY
  )
  // Ohne diese Zusicherung koennte ein leerer storageState gespeichert werden und jeder
  // Folge-Spec liefe still abgemeldet gegen die Login-Weiterleitung.
  expect(token, 'Anmelde-Token im localStorage').not.toBeNull()

  mkdirSync(AUTH_DIR, { recursive: true })
  await page.context().storageState({ path: AUTH_STATE_FILE })
})
