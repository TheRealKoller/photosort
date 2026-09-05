/**
 * `npm run drive -- <skript> [viewport]`
 *
 * Fuehrt eine BELIEBIGE Interaktionsfolge aus - klicken, tippen, navigieren - und erreicht damit
 * Zustaende, die erst durch Bedienung entstehen: geoeffnete Popover, ausgeklappte Bereiche,
 * abgeschickte Formulare, Bestaetigungsdialoge. Gleiche Instrumentierung und gleiche Ausgabe wie
 * `shot`, nur mit frei geschriebenem Ablauf.
 *
 * Das Skript liegt ueblicherweise unter `scratch/` (gitignoriert) und exportiert eine Funktion
 * als Default-Export:
 *
 *   // e2e/scratch/popover.ts
 *   import type { DriveScript } from '../bin/drive.ts'
 *   const run: DriveScript = async ({ page, shot }) => {
 *     await page.goto('/projects/3/photos')
 *     await page.getByRole('button', { name: 'Details' }).first().click()
 *     await shot('popover-offen')
 *   }
 *   export default run
 *
 * Bewusst kein deklaratives Mini-Kommando-Vokabular (--click ... --type ...): fuer den einfachen
 * Fall gibt es `shot`, fuer den interessanten waere jede solche Syntax zu eng und muesste selbst
 * gewartet werden - neben der bereits vorhandenen von Playwright.
 */

import { writeFileSync } from 'node:fs'
import path from 'node:path'
import { pathToFileURL } from 'node:url'

import type { BrowserContext, Page } from '@playwright/test'

import {
  artifactPath,
  ensureAuthState,
  openSession,
  slugify,
  withBrowser,
  writeSessionLog,
} from '../lib/adhoc.ts'
import type { SessionLog } from '../lib/session.ts'
import { VIEWPORT_NAMES, isViewportName, type ViewportName } from '../lib/viewports.ts'

export interface DriveContext {
  page: Page
  context: BrowserContext
  log: SessionLog
  /** Legt einen Zwischen-Screenshot unter `artifacts/` ab und liefert den Pfad zurueck. */
  shot: (name: string) => Promise<string>
}

export type DriveScript = (driveContext: DriveContext) => Promise<void>

function usage(): never {
  console.error('Aufruf: npm run drive -- <skript.ts> [' + VIEWPORT_NAMES.join('|') + ']')
  process.exit(2)
}

const [rawScript, rawViewport] = process.argv.slice(2)
if (rawScript === undefined || rawScript === '') {
  usage()
}
if (rawViewport !== undefined && !isViewportName(rawViewport)) {
  usage()
}

const scriptPath = path.resolve(process.cwd(), rawScript)
const viewport: ViewportName = rawViewport ?? 'desktop'
const slug = slugify(path.basename(scriptPath, path.extname(scriptPath)))

const module_ = (await import(pathToFileURL(scriptPath).href)) as { default?: unknown }
const run = module_.default
if (typeof run !== 'function') {
  console.error(`${rawScript} exportiert keine Funktion als Default-Export.`)
  process.exit(2)
}

await withBrowser(async (browser) => {
  await ensureAuthState(browser)
  const { context, page, log } = await openSession(browser, viewport)
  try {
    await (run as DriveScript)({
      page,
      context,
      log,
      shot: async (name: string) => {
        const target = artifactPath(`drive-${slug}-${slugify(name)}-${viewport}.png`)
        writeFileSync(target, await page.screenshot({ fullPage: true }))
        console.log(`Screenshot: ${target}`)
        return target
      },
    })
  } finally {
    const logFile = writeSessionLog(
      `drive-${slug}-${viewport}.log.txt`,
      log,
      `Skript: ${rawScript} (${viewport})`
    )
    console.log(`Protokoll:  ${logFile}`)
    console.log(
      `  Konsole: ${log.console.length}, Seitenfehler: ${log.pageErrors.length}, ` +
        `fehlgeschlagene Aufrufe: ${log.failedRequests.length}`
    )
    await context.close()
  }
})
