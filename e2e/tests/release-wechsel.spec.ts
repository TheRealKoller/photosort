/**
 * Release-Wechsel mit Service Worker (specs/features/0565-neue-version-ohne-hard-reload.md).
 *
 * "Neue Version" heisst: Das geladene Einstiegs-Bundle ist dasjenige, auf das die aktuell vom
 * Server ausgelieferte index.html verweist. Geprueft wird mit zwei echten Builds: A ist das, was
 * der Pruefstack ohnehin ausliefert; B entsteht aus demselben Dockerfile mit einem Build-Marker,
 * der nur den Hash des Einstiegs-Bundles aendert. Der Tausch im Frontend-Container entfernt die
 * Dateien von A wie ein realer Deploy und wird nach jedem Test auf A zurueckgesetzt.
 *
 * Gewartet wird nur auf Zustaende des Service Workers (`ready`, `controllerchange`), nie auf Zeit.
 * Die Netz-Zeitgrenze der Navigationsroute ist hier nicht abgedeckt: `setOffline` laesst den Fetch
 * sofort scheitern. Sie ist im Build-Check von frontend/ als Konfigurationswert belegt.
 */

import { execFileSync } from 'node:child_process'
import { mkdtempSync, readdirSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'

import type { Page } from '@playwright/test'

import { TOKEN_STORAGE_KEY } from '../lib/authState.ts'
import { expect, test } from '../lib/fixtures.ts'
import { PACKAGE_ROOT } from '../lib/paths.ts'

const REPO_ROOT = path.join(PACKAGE_ROOT, '..')
const COMPOSE = ['compose', '-f', 'docker-compose.yml', '-f', 'docker-compose.e2e.yml']
const HTML_DIR = '/usr/share/nginx/html'
const RELEASE_B_IMAGE = 'photosort-e2e-release-b'
/** Deep-Link ohne Abhaengigkeit von geseedeten IDs, mit einem Eingabefeld fuer AK3. */
const DEEP_LINK = '/projects/new'

function docker(args: string[]): string {
  return execFileSync('docker', args, { cwd: REPO_ROOT, encoding: 'utf8', stdio: 'pipe' })
}

interface Release {
  dir: string
  /** Pfad des Einstiegsskripts laut index.html, z.B. /assets/index-AbC123.js. */
  entry: string
  /** Alle Dateien unter /assets/ dieses Builds, als Pfade ab Wurzel. */
  assets: string[]
}

function readRelease(dir: string): Release {
  const html = readFileSync(path.join(dir, 'index.html'), 'utf8')
  const entry = /<script type="module"[^>]*src="(\/assets\/[^"]+\.js)"/.exec(html)
  expect(entry, `Einstiegsskript in ${dir}/index.html`).not.toBeNull()
  const assets = readdirSync(path.join(dir, 'assets')).map((name) => `/assets/${name}`)
  return { dir, entry: entry![1]!, assets }
}

function deploy(release: Release): void {
  docker([...COMPOSE, 'exec', '-T', 'frontend', 'find', HTML_DIR, '-mindepth', '1', '-delete'])
  docker([...COMPOSE, 'cp', `${release.dir}/.`, `frontend:${HTML_DIR}`])
}

let workDir: string
let releaseA: Release
let releaseB: Release

test.beforeAll(async ({}, testInfo) => {
  // Der Bau von B laeuft durch das komplette Frontend-Dockerfile; die npm-ci-Schicht teilt er
  // sich ueber den Build-Cache mit dem Image des Pruefstacks.
  testInfo.setTimeout(600_000)
  workDir = mkdtempSync(path.join(tmpdir(), 'photosort-release-'))

  const dirA = path.join(workDir, 'a')
  docker([...COMPOSE, 'cp', `frontend:${HTML_DIR}`, dirA])
  releaseA = readRelease(dirA)

  docker([
    'build',
    '--target',
    'build',
    '--build-arg',
    'VITE_API_BASE_URL=/api',
    '--build-arg',
    'PHOTOSORT_BUILD_MARKER=release-b',
    '-t',
    RELEASE_B_IMAGE,
    'frontend',
  ])
  const container = docker(['create', RELEASE_B_IMAGE]).trim()
  try {
    docker(['cp', `${container}:/app/dist`, path.join(workDir, 'b')])
  } finally {
    docker(['rm', container])
  }
  releaseB = readRelease(path.join(workDir, 'b'))

  // Vorbedingung: Ohne verschiedene Einstiegs-Bundles bewiese kein Test unten einen Wechsel.
  expect(releaseB.entry, 'Einstiegs-Bundle von B unterscheidet sich von A').not.toBe(releaseA.entry)
})

test.afterEach(() => {
  deploy(releaseA)
})

test.afterAll(() => {
  if (workDir) rmSync(workDir, { recursive: true, force: true })
})

/** Wartet, bis ein aktiver Service Worker die Seite kontrolliert (Precache vollstaendig). */
async function waitForServiceWorkerControl(page: Page): Promise<void> {
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready
    if (navigator.serviceWorker.controller) return
    await new Promise<void>((resolve) =>
      navigator.serviceWorker.addEventListener('controllerchange', () => resolve(), { once: true }),
    )
  })
}

async function loadedEntry(page: Page): Promise<string | null> {
  return page.locator('script[type="module"][src^="/assets/"]').getAttribute('src')
}

test('F5 nach einem Release laedt beim ersten Mal die neue Version, angemeldet (AK1, AK5, AK7)', async ({
  page,
}) => {
  await page.goto('/')
  await waitForServiceWorkerControl(page)
  expect(await loadedEntry(page), 'Ausgangsversion').toBe(releaseA.entry)
  const readToken = () => page.evaluate((key) => localStorage.getItem(key), TOKEN_STORAGE_KEY)
  const token = await readToken()
  expect(token, 'Token vor dem Release').not.toBeNull()

  const requested: string[] = []
  page.on('request', (request) => requested.push(new URL(request.url()).pathname))
  deploy(releaseB)

  await page.reload()
  await expect(page.getByRole('banner'), 'App-Huelle nach F5').toBeVisible()
  expect(await loadedEntry(page), 'Einstiegs-Bundle nach F5').toBe(releaseB.entry)
  expect(requested, 'Request an das Einstiegsskript von B').toContain(releaseB.entry)
  // Mit B identische Dateien (Schriften, ggf. CSS) sind kein Asset "von A".
  expect(
    requested.filter(
      (pathname) => releaseA.assets.includes(pathname) && !releaseB.assets.includes(pathname),
    ),
    'Requests an Assets von A',
  ).toEqual([])
  expect(page.url(), 'kein Umweg ueber /login').not.toContain('/login')
  expect(await readToken(), 'Token nach dem Wechsel').toBe(token)
})

test('ein Deep-Link nach einem Release laedt beim ersten Mal die neue Version (AK1)', async ({
  page,
}) => {
  await page.goto('/')
  await waitForServiceWorkerControl(page)
  deploy(releaseB)

  await page.goto(DEEP_LINK)
  await expect(page.locator('#project-name'), 'Deep-Link-Seite').toBeVisible()
  expect(await loadedEntry(page), 'Einstiegs-Bundle nach Deep-Link').toBe(releaseB.entry)
  expect(new URL(page.url()).pathname, 'Route bleibt der Deep-Link').toBe(DEEP_LINK)
})

test('eine laufende Sitzung laedt beim SW-Wechsel nicht neu (AK3, AK4)', async ({ page }) => {
  await page.goto(DEEP_LINK)
  await waitForServiceWorkerControl(page)
  await page.locator('#project-name').fill('Eingabe vor dem Release')
  // Ein Reload verwirft das Fenster-Objekt samt dieser Eigenschaft.
  await page.evaluate(() => {
    Reflect.set(window, 'releaseMarker', 'vor-dem-release')
    window.scrollTo(0, document.documentElement.scrollHeight)
  })
  const scrollY = await page.evaluate(() => window.scrollY)

  deploy(releaseB)
  await page.evaluate(async () => {
    const registration = await navigator.serviceWorker.ready
    const changed = new Promise<void>((resolve) =>
      navigator.serviceWorker.addEventListener('controllerchange', () => resolve(), { once: true }),
    )
    await registration.update()
    await changed
  })

  expect(
    await page.evaluate(() => Reflect.get(window, 'releaseMarker')),
    'Fenster-Marker nach controllerchange',
  ).toBe('vor-dem-release')
  await expect(page.locator('#project-name'), 'Eingabe nach controllerchange').toHaveValue(
    'Eingabe vor dem Release',
  )
  expect(new URL(page.url()).pathname, 'Route nach controllerchange').toBe(DEEP_LINK)
  expect(await page.evaluate(() => window.scrollY), 'Scrollposition').toBe(scrollY)
  expect(await loadedEntry(page), 'weiterhin die Ausgangsversion').toBe(releaseA.entry)
})

test('ohne Netz startet die zuletzt geladene Version, auch per Deep-Link (AK6)', async ({
  page,
  context,
}) => {
  await page.goto('/')
  await waitForServiceWorkerControl(page)

  await context.setOffline(true)
  try {
    for (const target of ['/', DEEP_LINK]) {
      await page.goto(target)
      await expect(page.getByRole('banner'), `App-Huelle offline auf ${target}`).toBeVisible()
      expect(await loadedEntry(page), `Einstiegs-Bundle offline auf ${target}`).toBe(releaseA.entry)
    }
  } finally {
    await context.setOffline(false)
  }
})

test('eine neu geoeffnete Seite nach Schliessen aller Seiten zeigt die neue Version (AK2-Ersatz)', async ({
  page,
  context,
}) => {
  await page.goto('/')
  await waitForServiceWorkerControl(page)
  deploy(releaseB)

  for (const open of context.pages()) await open.close()
  const restarted = await context.newPage()
  await restarted.goto('/')
  await expect(restarted.getByRole('banner'), 'App-Huelle nach Neustart').toBeVisible()
  expect(await loadedEntry(restarted), 'Einstiegs-Bundle nach Neustart').toBe(releaseB.entry)
})
