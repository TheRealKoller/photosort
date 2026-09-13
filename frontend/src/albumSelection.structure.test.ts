// @vitest-environment node
/*
 * Struktureller Wächter der Endauswahl (specs/features/0431-endauswahl-gemeinsam.md,
 * Nachweisstelle 7 und Zusicherung 26).
 *
 * WARUM DIESE EBENE: Die beiden Zusagen, die hier stehen, brechen ohne eigenen Testfall STILL.
 * Die drei neuen Felder stehen am `PhotoOut` JEDES Lesepfads und liegen damit auch im
 * Entwurfszweig griffbereit - ein Renderaufruf genügt, und der Einzelentwurf hätte die zweite
 * Auswahlebene, deren Abwesenheit Story 6 zusichert. Umgekehrt sähe eine Endauswahl, die ihre
 * Zugehörigkeit über `isInAlbum` selbst herleitete, in jedem Komponententest richtig aus: Ihre
 * Antwortmenge enthält Fotos, die in keinem der beiden Entwürfe stehen, und für die ist
 * `status !== 'rejected'` schlicht keine Aussage.
 *
 * SELBSTAUSSCHLUSS: Diese Datei enthält die Feldnamen als SUCHBEGRIFFE. Sie prüft deshalb
 * ausschließlich namentlich genannte Dateien und nie den Baum als Ganzes; die eine baumweite
 * Prüfung unten sucht einen Satz, den diese Datei nur als importierte Konstante kennt.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { DRAFT_EMPTY_TEXT } from './pages/AlbumDraftPage'

const SRC_DIR = fileURLToPath(new URL('.', import.meta.url))

function read(relativePath: string): string {
  return readFileSync(join(SRC_DIR, relativePath), 'utf8')
}

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

/** Die drei Felder, die die Endauswahl an `PhotoOut` hängt. */
const SELECTION_FIELDS = ['final_selection_decision', 'in_final_selection', 'contested'] as const

/** Die Dateien des EINZELENTWURFS - sie dürfen keines der drei Felder lesen. */
const DRAFT_FILES = ['pages/AlbumDraftPage.tsx', 'components/CurationPhotoTile.tsx'] as const

/** Die Dateien der ENDAUSWAHL - sie dürfen `isInAlbum` nicht importieren. */
const SELECTION_FILES = [
  'pages/AlbumSelectionPage.tsx',
  'components/SelectionPhotoTile.tsx',
] as const

describe('Der Einzelentwurf bleibt von der Endauswahl unberührt', () => {
  it.each(DRAFT_FILES)('%s nennt keines der drei Endauswahl-Felder', (file) => {
    const content = read(file)
    const found = SELECTION_FIELDS.filter((field) => content.includes(field))

    // Gleichheit der Fundmenge, nicht "enthält nicht": Ein neues viertes Feld fiele bei einer
    // Enthaltensprüfung durch, hier steht die Menge vollständig da.
    expect(found).toEqual([])
  })

  it('findet die Felder dort, wo sie stehen - die Suche ist nicht blind', () => {
    // Positiv-Gegenprobe gegen die leere Fundmenge: Ohne sie bestünde der Wächter oben auch dann,
    // wenn die Suchbegriffe an KEINER Stelle des Produkts mehr vorkämen.
    const content = read('pages/AlbumSelectionPage.tsx')
    const found = SELECTION_FIELDS.filter((field) => content.includes(field))

    expect(found.length).toBeGreaterThan(0)
  })
})

describe('Die Endauswahl leitet die Zugehörigkeit nie selbst her', () => {
  it.each(SELECTION_FILES)('%s importiert `isInAlbum` nicht', (file) => {
    expect(read(file)).not.toMatch(/^\s*import\b.*\bisInAlbum\b/m)
  })

  it('erkennt einen solchen Import, wo er steht - die Suche ist nicht blind', () => {
    // Gegenprobe am Bestand: `CurationPhotoTile` importiert `isInAlbum` tatsächlich.
    expect(read('components/CurationPhotoTile.tsx')).toMatch(/^\s*import\b.*\bisInAlbum\b/m)
  })

  it('unterscheidet den Import vom bloßen Nennen des Namens in einem Kommentar', () => {
    // Beide Endauswahl-Dateien SPRECHEN über `isInAlbum` (sie begründen, warum sie es nicht
    // benutzen). Ein Wächter, der schon daran anschlägt, wäre dauerhaft rot und würde entfernt.
    for (const file of SELECTION_FILES) {
      expect(read(file)).toContain('isInAlbum')
    }
  })
})

describe('Ein Textbaustein, der an zwei Orten gilt, steht nur an einem', () => {
  it('führt den Satz des fehlenden Auswahlvorschlags genau einmal als Literal', () => {
    // Zusicherung 26: Eine Zeichenkettengleichheit bestünde auch gegen eine Kopie - deshalb wird
    // die Anzahl der Fundstellen gezählt und nicht der angezeigte Text verglichen. Diese Datei
    // kennt den Satz ausschließlich als importierte Konstante und zählt damit nicht mit.
    const occurrences = walk(SRC_DIR)
      .filter((path) => path.endsWith('.ts') || path.endsWith('.tsx'))
      .filter((path) => readFileSync(path, 'utf8').includes(DRAFT_EMPTY_TEXT))
      .map((path) => `src/${path.slice(SRC_DIR.length)}`)

    expect(occurrences).toEqual(['src/pages/AlbumDraftPage.tsx'])
  })
})
