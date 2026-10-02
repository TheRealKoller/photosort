/**
 * Rücksetzung der EIGENEN Albumentscheidungen im Album-Entwurf eines Demo-Projekts
 * (specs/features/0558-..., „Erster schreibender E2E-Fall").
 *
 * Alle Specs teilen sich EINEN geseedeten Datenbestand (`workers: 1`). Ein Spec, der schreibt, muss
 * ihn deshalb in seinem `finally` zurückgeben - sonst hinge jeder nachfolgende Spec an der
 * Laufreihenfolge. Zurückgesetzt wird über die API, nicht über die Oberfläche: Die Rücksetzung muss
 * auch dann greifen, wenn genau die Oberfläche der Grund des Fehlschlags ist.
 *
 * Der Vorzustand ist die eigene Entscheidung je Foto der Antwortmenge von
 * `GET /projects/{id}/album-draft`. Ein Foto, das erst durch den Spec hineinkam, steht im Vorzustand
 * nicht und bekommt beim Zurücksetzen seine Entscheidung entfernt.
 */

import type { Page } from '@playwright/test'

import { DEMO_USERNAME } from './auth.ts'
import { TOKEN_STORAGE_KEY } from './authState.ts'

/** Der Pfadpräfix, unter dem das Frontend des Prüfstacks die API weiterreicht (nginx). */
const API_PREFIX = '/api'

type OwnStatus = 'album_worthy' | 'rejected' | null

interface DraftItem {
  id: number
  ratings: { username: string; status: OwnStatus }[]
}

/** Die eigene Entscheidung je Foto-Id. */
export type OwnDraftStates = Map<number, OwnStatus>

async function authHeader(page: Page): Promise<Record<string, string>> {
  const token = await page.evaluate((key) => window.localStorage.getItem(key), TOKEN_STORAGE_KEY)
  if (token === null) {
    throw new Error('Kein Anmelde-Token im Browser - die Rücksetzung kann nicht schreiben.')
  }
  return { Authorization: `Bearer ${token}` }
}

/** Liest die eigene Entscheidung zu jedem Foto des Entwurfs. Die Seite muss auf der App-Origin stehen. */
export async function readOwnDraftStates(page: Page, projectId: number): Promise<OwnDraftStates> {
  const response = await page.request.get(`${API_PREFIX}/projects/${projectId}/album-draft`, {
    headers: await authHeader(page),
  })
  if (!response.ok()) {
    throw new Error(`album-draft antwortete ${response.status()}`)
  }
  const body = (await response.json()) as { items: DraftItem[] }
  return new Map(
    body.items.map((item) => [
      item.id,
      item.ratings.find((rating) => rating.username === DEMO_USERNAME)?.status ?? null,
    ]),
  )
}

/** Schreibt jede abweichende eigene Entscheidung auf den Vorzustand zurück. */
export async function restoreOwnDraftStates(
  page: Page,
  projectId: number,
  before: OwnDraftStates,
): Promise<void> {
  const headers = await authHeader(page)
  const now = await readOwnDraftStates(page, projectId)
  for (const [photoId, status] of now) {
    const wanted = before.get(photoId) ?? null
    if (wanted === status) {
      continue
    }
    const path = `${API_PREFIX}/photos/${photoId}/rating`
    const response =
      wanted === null
        ? await page.request.delete(path, { headers })
        : await page.request.put(path, { headers, data: { status: wanted } })
    if (!response.ok()) {
      throw new Error(`Rücksetzung von Foto ${photoId} antwortete ${response.status()}`)
    }
  }
}
