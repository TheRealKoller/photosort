/**
 * Zugriff auf den geseedeten Demo-Datenbestand (`backend/src/photosort/demo_state.py`).
 *
 * WARUM DIE PROJEKT-ID NICHT HARTKODIERT WIRD: Der Seeder ist zielzustands-idempotent - er
 * LOESCHT seine eigenen Projekte und legt sie neu an. Postgres setzt die Sequenz dabei nicht
 * zurueck, ein zweiter Seed-Lauf gegen dieselbe Datenbank vergibt also die IDs 5-8 statt 1-4. Ein
 * Spec mit `/projects/2/photos` waere damit exakt einmal gruen und danach dauerhaft rot - und
 * zwar mit einer Fehlermeldung ueber ein fehlendes Element statt ueber die falsche ID.
 *
 * Aufgeloest wird stattdessen ueber den Projektnamen in der Projektliste. Der Name ist die
 * Eigenschaft, die der Seeder zusichert (er ist zugleich der Anker seiner Loesch-Sperre), die ID
 * ist es nicht.
 */

import { expect, type Page } from '@playwright/test'

/**
 * Die vier Demo-Projekte, benannt nach ihrer PRUEFRELEVANTEN Eigenschaft. Muss zu den Konstanten
 * in `demo_state.py` passen; ein Auseinanderlaufen faellt sofort als fehlender Projektlink auf.
 */
export const DEMO_PROJECTS = {
  /** 0 Fotos - Leerzustand. */
  empty: 'Demo — Leeres Projekt',
  /** 60-80 Fotos - genug fuer Scrollen, Grid-Zeilen und Listendichte. */
  large: 'Demo — Große Sammlung',
  /** Alle Bewertungsstatus, Kriterien-Lauf, alle Kategorie-Schluessel. */
  rated: 'Demo — Bewertet',
  /** Fehlgeschlagener Lauf, Foto ohne Cache-Datei, Cloud-Vision-Fehlerzeile. */
  error: 'Demo — Fehlerzustand',
} as const

/**
 * Liefert die Projekt-ID des benannten Demo-Projekts, aufgeloest ueber die Projektliste.
 *
 * Die `toHaveCount(1)`-Zusicherung ist keine Formalie: sie schliesst sowohl den Fall "Seeder lief
 * nicht" (0 Treffer, der Spec waere sonst mit einer irrefuehrenden Folgemeldung rot) als auch den
 * Fall "Reste eines frueheren Laufs" (mehrere Treffer, der Spec liefe gegen ein zufaelliges
 * Projekt) aus.
 */
export async function demoProjectId(page: Page, projectName: string): Promise<number> {
  await page.goto('/')
  const link = page.getByRole('link').filter({ hasText: projectName })
  await expect(link, `Projektlink "${projectName}" in der Projektliste`).toHaveCount(1)

  const href = await link.getAttribute('href')
  const match = /^\/projects\/(\d+)$/.exec(href ?? '')
  expect(match, `Projektlink "${projectName}" zeigt auf /projects/<id>, gefunden: ${href}`).not.toBeNull()
  return Number(match?.[1])
}

/**
 * Kacheln des Foto-Grids. Lokalisiert ueber Rolle + Ziel-Link, NICHT ueber Klassennamen
 * (Selektor-Konvention des Testkonzepts) - das Grid ueberlebt damit eine Umgestaltung seiner
 * Utility-Klassen, und genau deren Wirkung soll ja gemessen werden.
 */
export function photoTiles(page: Page) {
  return page.getByRole('listitem').filter({ has: page.locator('a[href*="/photos/"]') })
}

export interface Box {
  x: number
  y: number
  width: number
  height: number
}
