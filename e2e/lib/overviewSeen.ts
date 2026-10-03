/**
 * Markiert die Ablaufuebersicht (specs/features/0566-ablauf-uebersicht.md) fuer die angemeldete
 * Person in jedem Demo-Projekt als gesehen. Ohne das laege der modale Dialog beim ersten Oeffnen
 * jedes Projekts ueber der geprueften Seite, und jeder Treffertest traefe ihn statt der Seite.
 *
 * SICHERHEIT: Die Anfragen gehen ueber `page.request` RELATIV zur Seiten-Origin - das ist die
 * allowlist-gebundene `BASE_URL` (lib/baseUrl.ts); eine eigene API-Adresse gibt es nicht.
 * Markiert werden nur die Ids aus der Projektliste DERSELBEN Sitzung. Das Token wird weder
 * geloggt noch ausserhalb des bestehenden Sitzungszustands abgelegt. Jede Antwort ungleich 2xx
 * bricht hart ab; die Meldung nennt nur den Status.
 */

import type { Page } from '@playwright/test'

import { TOKEN_STORAGE_KEY } from './authState.ts'

const API_PREFIX = '/api'

/** Liefert die Zahl der markierten Projekte. Die Seite muss auf der App-Origin stehen. */
export async function markAllProjectsSeen(page: Page): Promise<number> {
  const token = await page.evaluate((key) => window.localStorage.getItem(key), TOKEN_STORAGE_KEY)
  if (token === null) {
    throw new Error(
      'Kein Anmelde-Token im Browser - die Ablaufuebersicht kann nicht gemerkt werden.',
    )
  }
  const headers = { Authorization: `Bearer ${token}` }

  const list = await page.request.get(`${API_PREFIX}/projects`, { headers })
  if (!list.ok()) {
    throw new Error(`GET /projects antwortete ${list.status()}`)
  }
  const ids = ((await list.json()) as { id: number }[]).map((project) => project.id)
  if (ids.length === 0) {
    throw new Error('Die Projektliste ist leer - der Pruefstack ist nicht demo-geseedet.')
  }

  for (const id of ids) {
    const put = await page.request.put(`${API_PREFIX}/projects/${id}/overview-seen`, { headers })
    if (!put.ok()) {
      throw new Error(`PUT overview-seen antwortete ${put.status()}`)
    }
  }

  // Zugesichert, nicht nur abgesetzt: Je Projekt muss der Server "gesehen" melden.
  let confirmed = 0
  for (const id of ids) {
    const read = await page.request.get(`${API_PREFIX}/projects/${id}/overview-seen`, { headers })
    if (!read.ok()) {
      throw new Error(`GET overview-seen antwortete ${read.status()}`)
    }
    if (((await read.json()) as { seen: boolean }).seen === true) {
      confirmed += 1
    }
  }
  if (confirmed !== ids.length) {
    throw new Error(`Ablaufuebersicht nur in ${confirmed} von ${ids.length} Projekten gemerkt.`)
  }
  return confirmed
}
