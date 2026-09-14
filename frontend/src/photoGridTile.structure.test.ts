// @vitest-environment node
/*
 * Struktureller Wächter der Rasterkachel (specs/features/0489-fotouebersicht-ohne-beschnitt.md,
 * AK13; ADR 0110 Punkt 5).
 *
 * WARUM DIESE EBENE: Beide Zusagen brechen ohne eigenen Testfall STILL. `PhotoCard` bleibt
 * unverändert und behält genau ihre drei Aufrufstellen (Kuratierung, gemeinsame Endauswahl,
 * Duplikatsvergleich) — eine vierte Aufrufstelle wäre in jedem Komponententest unauffällig,
 * machte aber die Aussage „die Rasteransicht benutzt die Fotokarte nicht mehr" falsch. Umgekehrt
 * sähe eine Rasterkachel, die `PhotoCard` intern wiederverwendet, in ihren eigenen Tests völlig
 * richtig aus und zöge trotzdem Kartenkörper, Statuszeile und feste Bildform mit.
 *
 * SELBSTAUSSCHLUSS: Diese Datei enthält die Dateinamen als SUCHBEGRIFFE und prüft deshalb
 * ausschließlich namentlich genannte Dateien bzw. schließt sich aus der baumweiten Suche aus.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const SRC_DIR = fileURLToPath(new URL('.', import.meta.url))

function walk(dir: string): string[] {
  const found: string[] = []
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry)
    if (statSync(full).isDirectory()) {
      found.push(...walk(full))
    } else {
      found.push(full)
    }
  }
  return found
}

/** Alle Produktivquellen - ohne Tests und ohne diese Datei selbst (Selbstausschluss). */
function productionSources(): { path: string; content: string }[] {
  return walk(SRC_DIR)
    .filter((path) => /\.tsx?$/.test(path))
    .filter((path) => !/\.test\.tsx?$/.test(path))
    .map((path) => ({ path, content: readFileSync(path, 'utf8') }))
}

/** Importiert die Datei die Fotokarte — unabhängig davon, wie ihr Doku-Block sie erwähnt? */
function importsPhotoCard(content: string): boolean {
  return /import\s*\{[^}]*\bPhotoCard\b[^}]*\}\s*from\s*'[^']*PhotoCard'/.test(content)
}

describe('Rasterkachel und Fotokarte stehen nebeneinander', () => {
  it('lässt PhotoCard genau ihre verbliebenen Aufrufstellen', () => {
    /*
     * ABWEICHUNG VON DER AUFZÄHLUNG IN ADR 0110 PUNKT 5 / AK13, gemessen statt übernommen: Dort
     * heißen die verbleibenden Aufrufstellen „Kuratierung, gemeinsame Endauswahl,
     * Duplikatsvergleich". Der Duplikatsvergleich benutzt die Fotokarte jedoch nachweislich
     * nicht — `components/DuplicatePhotoTile.tsx` schließt das in seinem eigenen Doku-Block
     * ausdrücklich aus („KEIN Aufbau auf `PhotoCard`/`CurationPhotoTile`/`RatingBadge`"), weil
     * deren Vokabular die Albumentscheidung eines Nutzers ist und dort die andere Frage steht.
     * Auf `main` sind es deshalb drei Aufrufstellen inklusive der Rasteransicht, nach deren
     * Wegfall zwei.
     *
     * Die TRAGENDE Zusage ist unberührt: Die Fotokarte bleibt unverändert, die Rasteransicht
     * benutzt sie nicht mehr, und keine weitere Ansicht kommt hinzu. Genau das steht hier.
     */
    const callers = productionSources()
      .filter((file) => importsPhotoCard(file.content))
      .map((file) => file.path.slice(SRC_DIR.length))
      .sort()

    expect(callers).toEqual([
      'components/CurationPhotoTile.tsx',
      'components/SelectionPhotoTile.tsx',
    ])
  })

  it('lässt die Rasterkachel die Fotokarte nicht importieren', () => {
    // Geprüft wird der IMPORT, nicht das Wort: Der Doku-Block der Kachel nennt die Fotokarte
    // bewusst („eine eigene Komponente NEBEN `PhotoCard`") und muss das weiter dürfen.
    const tile = readFileSync(join(SRC_DIR, 'components/PhotoGridTile.tsx'), 'utf8')

    expect(importsPhotoCard(tile)).toBe(false)
    expect(tile).not.toMatch(/<PhotoCard[\s/>]/)
  })

  it('lässt die Fotoübersicht die Fotokarte nicht mehr benutzen', () => {
    const page = readFileSync(join(SRC_DIR, 'pages/PhotoGridPage.tsx'), 'utf8')

    expect(importsPhotoCard(page)).toBe(false)
    expect(page).toContain('PhotoGridTile')
  })
})
