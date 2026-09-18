// @vitest-environment node
/*
 * Struktureller Wächter der Bilddetailansicht (specs/features/0497-bilddetail-urteil-zuerst.md,
 * Teststrategie).
 *
 * WARUM DIESE EBENE: Alle drei Zusagen brechen ohne eigenen Testfall STILL - sie sind Aussagen
 * über den BESTAND der Quellen, nicht über das Verhalten einer Komponente, und sähen in jedem
 * Komponententest richtig aus.
 *
 * SELBSTAUSSCHLUSS: Diese Datei enthält die gesuchten Namen als SUCHBEGRIFFE und schließt sich
 * deshalb aus der baumweiten Suche aus.
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

function relativePath(path: string): string {
  return path.slice(SRC_DIR.length)
}

/**
 * Quelltext ohne Kommentare.
 *
 * GEPRÜFT WIRD DER ZUGRIFF, NICHT DAS WORT (Bauform wie `photoGridTile.structure.test.ts`): Die
 * Doku-Blöcke der Seite und der Bausteine nennen die Feldnamen bewusst - `PhotoDetailPage.tsx`
 * führt die Sicherheitsauflage S2 wörtlich mit beiden Ortsfeldern, und das muss sie weiter dürfen.
 * Eine Suche über den rohen Text machte jede dieser Erklärungen zum Befund und lüde damit dazu
 * ein, die Erklärung zu streichen statt die Regel einzuhalten.
 */
function withoutComments(content: string): string {
  return content.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '')
}

/** Importiert die Datei die Aufschlüsselung - unabhängig davon, wie ihr Doku-Block sie erwähnt? */
function importsCriterionDetailsList(content: string): boolean {
  return /import\s*\{[^}]*\bCriterionDetailsList\b[^}]*\}\s*from\s*'[^']*CriterionDetailsList'/.test(
    content,
  )
}

describe('Die Aufschlüsselung behält genau ihre eine Aufrufstelle', () => {
  /*
   * GLEICHHEIT, NICHT "ENTHÄLT NICHT": Ein späterer Rück-Import in die Detailseite zeigte die
   * Aufschlüsselung DOPPELT in zwei Idiomen - einmal kompakt als Popover-Darstellung, einmal als
   * Seitenraster - und sähe in jedem Komponententest richtig aus. Kompaktes Popover und großes
   * Seitenurteil sind zwei Darstellungen, keine Variante voneinander.
   */
  it('lässt CriterionDetailsList genau die Popover-Aufrufstelle', () => {
    const callers = productionSources()
      .filter((file) => importsCriterionDetailsList(file.content))
      .map((file) => relativePath(file.path))
      .sort()

    expect(callers).toEqual(['components/CriterionDetailsPopover.tsx'])
  })

  it('lässt die Detailseite die Aufschlüsselung nicht mehr einbinden', () => {
    const page = readFileSync(join(SRC_DIR, 'pages/PhotoDetailPage.tsx'), 'utf8')

    expect(importsCriterionDetailsList(page)).toBe(false)
    expect(page).not.toMatch(/<CriterionDetailsList[\s/>]/)
    // Positiv-Gegenprobe: Die Seite bindet stattdessen tatsächlich das Raster ein - ohne sie
    // bestünde die Zusage auch auf einer Seite, die gar keine Einzelwerte mehr zeigt.
    expect(page).toContain('CriterionScoreGrid')
  })
})

describe('Die Aufteilung nach has_presence_threshold steht an genau einer Stelle', () => {
  /*
   * Eine zweite, inline nachgebaute Aufteilung bricht STILL: Sie sähe in ihrem eigenen Test
   * richtig aus, schnitte Qualität und Bildinhalt aber verschieden - und die Abweichung fiele
   * erst am unterschiedlich befüllten Raster auf.
   *
   * `api/types.ts` ist der Deklarationsort des Feldes und gehört deshalb dazu.
   */
  it('nennt den Feldnamen nur im Typ und in der geteilten Funktion', () => {
    const treffer = productionSources()
      .filter((file) => withoutComments(file.content).includes('has_presence_threshold'))
      .map((file) => relativePath(file.path))
      .sort()

    expect(treffer).toEqual(['api/types.ts', 'utils/criterionScores.ts'])
  })

  /* Positiv-Gegenprobe: Der Erkenner läuft nicht gegen eine leere Menge. */
  it('findet den Feldnamen überhaupt', () => {
    const util = readFileSync(join(SRC_DIR, 'utils/criterionScores.ts'), 'utf8')

    expect(util).toContain('has_presence_threshold')
  })

  /* Beide Darstellungen lesen dieselbe Funktion - sonst wäre die Mengengleichheit oben zwar
     erfüllt, die Aufteilung aber trotzdem nur an einer der beiden Stellen im Einsatz. */
  it('lässt beide Darstellungen dieselbe Funktion lesen', () => {
    for (const datei of [
      'components/CriterionDetailsList.tsx',
      'components/CriterionScoreGrid.tsx',
    ]) {
      const inhalt = readFileSync(join(SRC_DIR, datei), 'utf8')
      expect(inhalt, datei).toMatch(
        /import\s*\{[^}]*\bpartitionByPresenceThreshold\b[^}]*\}\s*from\s*'[^']*criterionScores'/,
      )
    }
  })
})

describe('Die dreistufige Ortsnamen-Wahl steht in genau einer Funktion', () => {
  /*
   * Entstünde die Rangfolge (Sehenswürdigkeit → aufgelöster Ortsname → keiner) ein zweites Mal,
   * liefe sie mit der Ereignis-Überschrift auseinander - und zwar still: Beide Stellen sähen für
   * sich betrachtet richtig aus, zeigten aber für dasselbe Ereignis verschiedene Namen.
   *
   * Gemessen am LESEN von `landmark_name`: Wer die Rangfolge nachbaut, muss dieses Feld anfassen.
   */
  it('liest landmark_name nur im Typ und in der geteilten Funktion', () => {
    const treffer = productionSources()
      .filter((file) => withoutComments(file.content).includes('landmark_name'))
      .map((file) => relativePath(file.path))
      .sort()

    expect(treffer).toEqual(['api/types.ts', 'utils/timeOfDay.ts'])
  })

  it('lässt beide Aufrufstellen die Funktion importieren', () => {
    const seite = readFileSync(join(SRC_DIR, 'pages/PhotoDetailPage.tsx'), 'utf8')
    const quelle = readFileSync(join(SRC_DIR, 'utils/timeOfDay.ts'), 'utf8')

    expect(seite).toMatch(/import\s*\{[^}]*\beventPlaceName\b[^}]*\}\s*from\s*'[^']*timeOfDay'/)
    // Die Ereignis-Überschrift liest dieselbe Funktion, statt die Rangfolge zu wiederholen.
    expect(quelle).toMatch(/const name = eventPlaceName\(event\)/)
  })
})
