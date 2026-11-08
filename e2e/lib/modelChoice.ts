/**
 * Lesen und Zurückschreiben der Modellwahl eines Demo-Projekts über die API (Spec 0383).
 *
 * Alle Specs teilen bei `workers: 1` einen geseedeten Bestand; ein schreibender Fall muss den
 * Ausgangszustand deshalb im `finally` zurücksetzen (Testkonzept-Muster 10 der Spec 0383). Der
 * Rückweg ist im schlüssellosen Prüfstack möglich, weil `cloud`/`null`/`null` die
 * Installationsvorgabe ist: ein `null` gilt als unverändert und braucht weder Registry-Eintrag
 * noch Anbieterschlüssel (ADR 0143 Punkt 6).
 *
 * Zurückgeschrieben wird der GESPEICHERTE Stand, nicht der wirksame: `GET …/model-choice` liefert
 * bei `NULL` bereits das aufgelöste Modell, und `*_is_default` sagt, ob die Spalte `NULL` war.
 */

import type { Page } from '@playwright/test'

import { TOKEN_STORAGE_KEY } from './authState.ts'

/** Der Pfadpräfix, unter dem das Frontend des Prüfstacks die API weiterreicht (nginx). */
const API_PREFIX = '/api'

/** Die wirksame Wahl - so, wie die Oberfläche sie markiert. */
export interface ModelChoiceState {
  category_method: 'cloud' | 'eye'
  category_model: string | null
  category_is_default: boolean
  landmark_model: string
  landmark_is_default: boolean
}

interface ModelChoiceResponse {
  current: ModelChoiceState
}

async function authHeader(page: Page): Promise<Record<string, string>> {
  const token = await page.evaluate((key) => window.localStorage.getItem(key), TOKEN_STORAGE_KEY)
  if (token === null) {
    throw new Error('Kein Anmelde-Token im Browser - die Modellwahl kann nicht gelesen werden.')
  }
  return { Authorization: `Bearer ${token}` }
}

/** Liest die WIRKSAME Wahl. Die Seite muss auf der App-Origin stehen. */
export async function readModelChoice(page: Page, projectId: number): Promise<ModelChoiceState> {
  const response = await page.request.get(`${API_PREFIX}/projects/${projectId}/model-choice`, {
    headers: await authHeader(page),
  })
  if (!response.ok()) {
    throw new Error(`model-choice antwortete ${response.status()}`)
  }
  const body = (await response.json()) as ModelChoiceResponse
  const {
    category_method,
    category_model,
    category_is_default,
    landmark_model,
    landmark_is_default,
  } = body.current
  return {
    category_method,
    category_model,
    category_is_default,
    landmark_model,
    landmark_is_default,
  }
}

/** Der Körper, der genau den gespeicherten Stand wiederherstellt - `NULL` bleibt `NULL`. */
function storedBody(state: ModelChoiceState): Record<string, string | null> {
  return {
    category_method: state.category_method,
    category_model: state.category_is_default ? null : state.category_model,
    landmark_model: state.landmark_is_default ? null : state.landmark_model,
  }
}

/**
 * Setzt den Ausgangszustand über die API zurück (nicht über die Oberfläche, die gerade versagt
 * haben kann). Wirft bei jeder Ablehnung - ein stiller Fehlschlag ließe den Bestand für alle
 * späteren Specs verdreht.
 */
export async function restoreModelChoice(
  page: Page,
  projectId: number,
  before: ModelChoiceState,
): Promise<void> {
  const response = await page.request.put(`${API_PREFIX}/projects/${projectId}/model-choice`, {
    headers: await authHeader(page),
    data: storedBody(before),
  })
  if (!response.ok()) {
    throw new Error(
      `Rücksetzung der Modellwahl antwortete ${response.status()}: ${await response.text()}`,
    )
  }
  const restored = await readModelChoice(page, projectId)
  if (JSON.stringify(restored) !== JSON.stringify(before)) {
    throw new Error(`Rücksetzung der Modellwahl ergab ${JSON.stringify(restored)}`)
  }
}
