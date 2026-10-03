// @vitest-environment node
/*
 * Build-Check des erzeugten Service Workers (specs/features/0565-neue-version-ohne-hard-reload.md).
 *
 * Zusage: Navigationen kommen online immer aus dem Netz (NetworkOnly mit Zeitgrenze) und nur
 * offline bzw. nach Ablauf der Zeitgrenze aus dem Precache - nie umgekehrt. Bricht das, liefert
 * F5 nach einem Release wieder die alte index.html mit alten Asset-Hashes aus.
 * Security-Auflage: Die einzige Laufzeitroute trifft ausschliesslich Navigationen, schreibt in
 * keinen Runtime-Cache und trifft nie /api - sonst laegen nutzerbezogene API-Antworten im
 * profilweiten SW-Cache, den zwei Personen am selben Geraet teilen.
 *
 * Geprueft wird das echte, mit `vite.config.ts` gebaute `sw.js`, nicht die Konfiguration: Nur das
 * erzeugte Artefakt zeigt, was der Browser tatsaechlich ausfuehrt.
 *
 * SELBSTAUSSCHLUSS: Diese Datei enthaelt die verbotenen Namen als Suchbegriffe und schliesst sich
 * deshalb aus der Suche ueber src/ aus.
 */
import { mkdtempSync, readFileSync, readdirSync, rmSync, statSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { build } from 'vite'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'

const FRONTEND_DIR = fileURLToPath(new URL('..', import.meta.url))
const SRC_DIR = fileURLToPath(new URL('.', import.meta.url))
const SELF = fileURLToPath(import.meta.url)

let outDir: string
let sw: string

beforeAll(async () => {
  outDir = mkdtempSync(join(tmpdir(), 'photosort-sw-'))
  // Unter vitest gilt NODE_ENV=test; Workbox erzeugte dann ein anderes (unminifiziertes) sw.js
  // als der Produktiv-Build. Gebaut wird deshalb wie `npm run build`.
  const previousNodeEnv = process.env.NODE_ENV
  process.env.NODE_ENV = 'production'
  try {
    await build({
      root: FRONTEND_DIR,
      configFile: join(FRONTEND_DIR, 'vite.config.ts'),
      mode: 'production',
      logLevel: 'silent',
      build: { outDir, emptyOutDir: true },
    })
  } finally {
    process.env.NODE_ENV = previousNodeEnv
  }
  sw = readFileSync(join(outDir, 'sw.js'), 'utf8')
}, 180_000)

afterAll(() => {
  if (outDir) rmSync(outDir, { recursive: true, force: true })
})

function precacheUrls(): string[] {
  const manifest = /precacheAndRoute\(\[(.*?)\]/s.exec(sw)
  expect(manifest, 'Precache-Manifest im sw.js').not.toBeNull()
  return [...manifest![1].matchAll(/url:"([^"]+)"/g)].map((m) => m[1])
}

/** Alles hinter dem Precache-Manifest: dort stehen die Routen. */
function routeSection(): string {
  const start = sw.indexOf('precacheAndRoute(')
  expect(start).toBeGreaterThan(-1)
  return sw.slice(sw.indexOf(']', start))
}

describe('erzeugtes sw.js', () => {
  it('beantwortet Navigationen mit NetworkOnly, Zeitgrenze und Precache-Fallback', () => {
    const routes = routeSection()
    const navigation =
      /registerRoute\(\(\{request:(\w+)\}\)=>"navigate"===\1\.mode,new \w+\.NetworkOnly\(\{(.*?)\}\),"GET"\)/s.exec(
        routes,
      )
    expect(navigation, 'Navigationsroute mit NetworkOnly').not.toBeNull()
    const options = navigation![2]
    // Zeitgrenze per Plugin: Abbruch nach 3 s (der Minifier schreibt 3000 als 3e3), Timer bei
    // Erfolg und Fehlschlag geloescht.
    expect(options).toMatch(/requestWillFetch:/)
    expect(options).toMatch(/new AbortController\b/)
    expect(options).toMatch(/setTimeout\(\(\)=>\w+\.abort\(\),(?:3e3|3000)\)/)
    expect(options).toMatch(/fetchDidSucceed:async\([^)]*\)=>[({]clearTimeout\(/)
    expect(options).toMatch(/fetchDidFail:async\([^)]*\)=>[({]clearTimeout\(/)
    const fallback = /PrecacheFallbackPlugin\(\{fallbackURL:"([^"]+)"\}\)/.exec(options)
    expect(fallback, 'precacheFallback der Navigationsroute').not.toBeNull()
    expect(precacheUrls()).toContain(fallback![1])
  })

  it('hat genau eine Laufzeitroute, ohne Runtime-Cache und ohne Precache-Navigation', () => {
    const routes = routeSection()
    expect(routes.match(/registerRoute\(/g)).toHaveLength(1)
    for (const forbidden of [
      'NavigationRoute',
      'createHandlerBoundToURL',
      'CacheFirst',
      'StaleWhileRevalidate',
      'NetworkFirst',
      'cacheName',
      '/api',
    ]) {
      expect(routes, `sw.js-Routen enthalten "${forbidden}"`).not.toContain(forbidden)
    }
  })
})

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry)
    return statSync(full).isDirectory() ? walk(full) : [full]
  })
}

describe('Quellen unter src/', () => {
  it('enthalten keinen Update-Prompt- oder Reload-Pfad', () => {
    const sources = walk(SRC_DIR).filter((path) => /\.tsx?$/.test(path) && path !== SELF)
    expect(sources.length).toBeGreaterThan(0)
    for (const path of sources) {
      const content = readFileSync(path, 'utf8')
      for (const forbidden of ['virtual:pwa-register', 'onNeedRefresh', 'location.reload']) {
        expect(content, `${path} enthaelt "${forbidden}"`).not.toContain(forbidden)
      }
    }
  })
})
