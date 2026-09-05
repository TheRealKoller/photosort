/**
 * Gemeinsamer Unterbau der beiden Ad-hoc-Werkzeuge (`npm run shot`, `npm run drive`).
 *
 * Ad-hoc-Nutzung ist ausdruecklich KEINE Testebene: Ausgaben landen unter `artifacts/`,
 * Ad-hoc-Skripte unter `scratch/`, beides gitignoriert, und nichts davon wird je als Testnachweis
 * gefuehrt. Der beabsichtigte Weg ist die andere Richtung - ein Skript, mit dem ein Fehler
 * reproduziert wurde, kann zu einem richtigen Spec reifen (dann aber mit Aufnahmekriterium,
 * Vorbedingungs-Assertion und Rot-Nachweis).
 *
 * Beide Werkzeuge benutzen denselben Sitzungsbaustein wie die Specs: die Mitschrift von Konsole,
 * Seitenfehlern und fehlgeschlagenen Netzwerkaufrufen passiert ohne Zutun des Aufrufers.
 */

import { existsSync, mkdirSync, writeFileSync } from 'node:fs'
import path from 'node:path'

import { chromium, type Browser, type BrowserContext, type Page } from '@playwright/test'

import { logIn } from './auth.ts'
import { BASE_URL } from './baseUrl.ts'
import { ARTIFACTS_DIR, AUTH_DIR, AUTH_STATE_FILE } from './paths.ts'
import { createSessionLog, formatSessionLog, instrumentContext, type SessionLog } from './session.ts'
import { VIEWPORTS, type ViewportName } from './viewports.ts'

export interface AdhocSession {
  context: BrowserContext
  page: Page
  log: SessionLog
}

/**
 * Meldet einmalig an und legt den Sitzungszustand ab, falls er fehlt. Schlaegt der Login fehl,
 * bricht `logIn` hart ab - kein Fallback auf einen anonymen Lauf (M7).
 */
export async function ensureAuthState(browser: Browser): Promise<void> {
  if (existsSync(AUTH_STATE_FILE)) {
    return
  }
  const context = await browser.newContext({ viewport: VIEWPORTS.desktop, baseURL: BASE_URL })
  try {
    const page = await context.newPage()
    await logIn(page)
    mkdirSync(AUTH_DIR, { recursive: true })
    await context.storageState({ path: AUTH_STATE_FILE })
  } finally {
    await context.close()
  }
}

export async function openSession(
  browser: Browser,
  viewport: ViewportName
): Promise<AdhocSession> {
  const context = await browser.newContext({
    viewport: VIEWPORTS[viewport],
    storageState: AUTH_STATE_FILE,
    baseURL: BASE_URL,
  })
  const log = createSessionLog()
  instrumentContext(context, log)
  const page = await context.newPage()
  return { context, page, log }
}

export async function withBrowser<T>(run: (browser: Browser) => Promise<T>): Promise<T> {
  const browser = await chromium.launch()
  try {
    return await run(browser)
  } finally {
    await browser.close()
  }
}

export function artifactPath(name: string): string {
  mkdirSync(ARTIFACTS_DIR, { recursive: true })
  return path.join(ARTIFACTS_DIR, name)
}

/** Dateisystem-sicherer, wiedererkennbarer Name aus einem Routenpfad oder Skriptnamen. */
export function slugify(value: string): string {
  const slug = value.replace(/[^a-zA-Z0-9]+/g, '-').replace(/^-+|-+$/g, '')
  return slug === '' ? 'root' : slug.toLowerCase()
}

export function writeSessionLog(fileName: string, log: SessionLog, heading: string): string {
  const target = artifactPath(fileName)
  writeFileSync(target, formatSessionLog(log, heading), 'utf8')
  return target
}
