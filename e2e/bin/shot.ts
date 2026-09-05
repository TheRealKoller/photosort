/**
 * `npm run shot -- <pfad> [viewport]`
 *
 * Ruft einen BELIEBIGEN Pfad der laufenden Anwendung auf, fotografiert ihn in beiden Viewports ab
 * (oder nur im genannten) und schreibt je Viewport ein Protokoll mit Konsolenmeldungen,
 * unbehandelten Seitenfehlern und Netzwerkaufrufen mit Status >= 400.
 *
 * Der haeufigste Fall, ohne dass eine Zeile Code geschrieben werden muss:
 *
 *   npm run shot -- /projects/2/photos
 *   npm run shot -- /projects/2/photos mobile
 */

import { writeFileSync } from 'node:fs'

import {
  artifactPath,
  ensureAuthState,
  openSession,
  slugify,
  withBrowser,
  writeSessionLog,
} from '../lib/adhoc.ts'
import { BASE_URL } from '../lib/baseUrl.ts'
import { VIEWPORT_NAMES, isViewportName, type ViewportName } from '../lib/viewports.ts'

function usage(): never {
  console.error('Aufruf: npm run shot -- <pfad> [' + VIEWPORT_NAMES.join('|') + ']')
  process.exit(2)
}

const [rawPath, rawViewport] = process.argv.slice(2)
if (rawPath === undefined || rawPath === '') {
  usage()
}
if (rawViewport !== undefined && !isViewportName(rawViewport)) {
  usage()
}

const targetPath = rawPath.startsWith('/') ? rawPath : `/${rawPath}`
const viewports: ViewportName[] = rawViewport === undefined ? VIEWPORT_NAMES : [rawViewport]
const slug = slugify(targetPath)

await withBrowser(async (browser) => {
  await ensureAuthState(browser)

  for (const viewport of viewports) {
    const { context, page, log } = await openSession(browser, viewport)
    try {
      await page.goto(targetPath)
      // Zielzustand statt fester Wartezeit - die Seite gilt als fertig, wenn keine Anfragen mehr
      // laufen (fuer den Ad-hoc-Blick genau richtig, im Pruefsatz gilt die schaerfere Regel).
      await page.waitForLoadState('networkidle')

      const screenshot = artifactPath(`shot-${slug}-${viewport}.png`)
      writeFileSync(screenshot, await page.screenshot({ fullPage: true }))
      const logFile = writeSessionLog(
        `shot-${slug}-${viewport}.log.txt`,
        log,
        `Aufruf: ${BASE_URL}${targetPath} (${viewport})`
      )

      console.log(`Screenshot: ${screenshot}`)
      console.log(`Protokoll:  ${logFile}`)
      console.log(
        `  Konsole: ${log.console.length}, Seitenfehler: ${log.pageErrors.length}, ` +
          `fehlgeschlagene Aufrufe: ${log.failedRequests.length}`
      )
    } finally {
      await context.close()
    }
  }
})
