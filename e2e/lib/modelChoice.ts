/**
 * Lesen der Modellwahl eines Demo-Projekts über die API (Spec 0383).
 *
 * NUR LESEND, und das mit Absicht: ein Zurückschreiben gibt es hier nicht. Wer ein Projekt auf
 * Eye stellt, kann es im Prüfstack nicht wieder auf Cloud stellen — der Schreibendpunkt verlangt
 * bei `cloud` ein Modell und lehnt einen geänderten Wert mit `422` ab („Für {Anbieter} ist kein
 * API-Schlüssel hinterlegt."), sobald es sich vom gespeicherten Wert unterscheidet; der
 * Prüfstack setzt beide Anbieterschlüssel bewusst leer (Teststrategie der Spec: der Cloud-Weg
 * ist auf dieser Ebene nicht prüfbar). `NULL` (Installationsvorgabe) nimmt der Endpunkt für
 * `cloud` ebenfalls nicht an. Der Vorzustand ist damit über die Schnittstelle nicht
 * wiederherstellbar; der dokumentierte Seed-Schritt ist der Ausgangspunkt jedes Laufs im
 * Prüfstack, und keine andere Spec liest die Laufwahl dieser Seite.
 */

import type { Page } from '@playwright/test'

import { TOKEN_STORAGE_KEY } from './authState.ts'

/** Der Pfadpräfix, unter dem das Frontend des Prüfstacks die API weiterreicht (nginx). */
const API_PREFIX = '/api'

/** Genau die drei Spalten, die `PUT …/model-choice` schreibt - nichts weiter. */
export interface ModelChoiceState {
  category_method: 'cloud' | 'eye'
  category_model: string | null
  landmark_model: string | null
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

/**
 * Liest die GESPEICHERTE Wahl. Die Seite muss auf der App-Origin stehen.
 *
 * Die Antwort trägt bei `NULL` bereits die aufgelöste Installationsvorgabe, damit ist der Wert
 * hier der wirksame, nicht der rohe Datenbankspaltenwert.
 */
export async function readModelChoice(page: Page, projectId: number): Promise<ModelChoiceState> {
  const response = await page.request.get(`${API_PREFIX}/projects/${projectId}/model-choice`, {
    headers: await authHeader(page),
  })
  if (!response.ok()) {
    throw new Error(`model-choice antwortete ${response.status()}`)
  }
  const body = (await response.json()) as ModelChoiceResponse
  const { category_method, category_model, landmark_model } = body.current
  return { category_method, category_model, landmark_model }
}
