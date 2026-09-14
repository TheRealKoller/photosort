/**
 * Das justierte Zeilenraster der Fotouebersicht als REINE Funktion: Seitenverhaeltnisse plus
 * Containerbreite hinein, Zeilen mit je Bild einer ganzen Pixelbreite und einer gemeinsamen
 * Zeilenhoehe heraus. Kein DOM, keine Messung, keine Bibliothek (ADR 0110 Punkt 4).
 *
 * VIER ZUSAGEN, die diese Datei allein traegt:
 *
 * 1. KEIN BESCHNITT. Jedes Bild bekommt seine Breite aus seinem EIGENEN Verhaeltnis; es wird nie
 *    auf eine feste Form gezwungen.
 * 2. GEMEINSAME ZEILENHOEHE. Alle Bilder einer Zeile tragen dieselbe Hoehe.
 * 3. BUENDIGES ZEILENENDE. Die Summe der Bildbreiten und der Zwischenraeume einer VOLLEN Zeile
 *    ergibt EXAKT die Containerbreite - der Rundungsrest liegt auf dem letzten Bild der Zeile.
 * 4. DIE LETZTE, UNVOLLSTAENDIGE ZEILE WIRD NICHT AUFGEZOGEN. Sie behaelt die Zielzeilenhoehe und
 *    steht linksbuendig. Eine auf volle Breite gestreckte Einzelaufnahme waere um ein Vielfaches
 *    hoeher als jede Zeile ueber ihr.
 */

/**
 * Die Ausfallrichtung fuer ein Bild ohne bekanntes Verhaeltnis (`aspect_ratio: null`, ADR 0110
 * Punkt 4). Es wird mit 3:2 eingeplant und in seinem Feld eingepasst (`object-contain`) und
 * bekommt dadurch einen Rand - das ist bewusst: Beschneiden ist ausgeschlossen, und ein Rand an
 * einem einzelnen Bild ist sichtbar falsch statt still falsch.
 */
export const FALLBACK_ASPECT_RATIO = 3 / 2

/**
 * Der Zwischenraum zwischen zwei Kacheln in Pixeln.
 *
 * ZWEI WAHRHEITEN DESSELBEN WERTS: Dieselbe Zahl steht als Utility `gap-3` (12px auf der
 * 8-Punkt-Skala) am Listenelement des Rasters - der Vertragstest weist ein gerechnetes Mass als
 * willkuerliche Klasse (`gap-[12px]`) zurueck. Laufen die beiden auseinander, rechnet die Funktion
 * mit einem anderen Abstand als der Browser setzt, und jede Zeile bricht einen Pixel zu frueh oder
 * zu spaet um. `justifiedRows.test.ts` und `designSystem.contract.test.ts` halten sie aneinander.
 */
export const GRID_GAP_PX = 12

/** Die angestrebte Hoehe einer vollen Zeile. Zugleich die Hoehe der letzten, ungestreckten. */
export const TARGET_ROW_HEIGHT_PX = 220

/**
 * Die Untergrenze der Zeilenhoehe. Wuerde ein weiteres Bild die Zeile darunter druecken, bricht
 * sie VORHER um. Ohne diese Grenze zoege eine einzelne Panoramaaufnahme die ganze Zeile auf eine
 * unbrauchbare Hoehe - nicht nur sich selbst.
 *
 * Sie gilt ausdruecklich nur fuer Zeilen mit MEHR ALS EINEM Bild: Ein Bild allein hat keine
 * Nachbarn, die es hochziehen koennten, und fiele sonst aus der Liste, statt bloss flach zu sein.
 */
export const MIN_ROW_HEIGHT_PX = 150

export interface JustifiedRowsInput {
  /** Die Seitenverhaeltnisse in Anzeigereihenfolge. `null` = unbekannt (siehe Ausfallrichtung). */
  ratios: readonly (number | null)[]
  containerWidth: number
  gap: number
  targetRowHeight: number
  minRowHeight: number
}

export interface JustifiedTile {
  /** Der Index in der uebergebenen Liste - die Zuordnung zum Foto bleibt beim Aufrufer. */
  index: number
  width: number
  height: number
}

export interface JustifiedRow {
  height: number
  tiles: JustifiedTile[]
}

/** Ein unbrauchbares Verhaeltnis wird wie ein unbekanntes behandelt, nie durchgereicht. */
function usableRatio(ratio: number | null | undefined): number {
  if (typeof ratio !== 'number' || !Number.isFinite(ratio) || ratio <= 0) {
    return FALLBACK_ASPECT_RATIO
  }
  return ratio
}

export function justifiedRows({
  ratios,
  containerWidth,
  gap,
  targetRowHeight,
  minRowHeight,
}: JustifiedRowsInput): JustifiedRow[] {
  if (ratios.length === 0 || containerWidth <= 0 || targetRowHeight <= 0) {
    return []
  }

  const usable = ratios.map(usableRatio)

  /**
   * Die Hoehe, die eine Zeile aus genau diesen Bildern haette, wenn sie die Breite buendig
   * ausfuellte. Sie FAELLT monoton, je mehr Bilder dazukommen - darauf beruhen beide Abbrueche
   * unten. Bleibt fuer den Zwischenraum kein Platz mehr, ist sie 0 und die Zeile schliesst
   * sofort, statt ins Negative zu laufen.
   */
  const heightOf = (indices: readonly number[]): number => {
    const inner = containerWidth - gap * (indices.length - 1)
    if (inner <= 0) {
      return 0
    }
    const sum = indices.reduce((total, index) => total + usable[index], 0)
    return inner / sum
  }

  const fullRows: number[][] = []
  let current: number[] = []
  for (let index = 0; index < usable.length; index += 1) {
    if (current.length > 0 && heightOf([...current, index]) < minRowHeight) {
      // Frueherer Umbruch: dieses Bild wuerde die Zeile unter die Untergrenze druecken.
      fullRows.push(current)
      current = []
    }
    current.push(index)
    if (heightOf(current) <= targetRowHeight) {
      fullRows.push(current)
      current = []
    }
  }

  const rows = fullRows.map((indices) => justify(indices, heightOf(indices)))
  if (current.length > 0) {
    // Die letzte, unvollstaendige Zeile: Zielhoehe, natuerliche Breiten, kein Aufziehen.
    rows.push({
      height: targetRowHeight,
      tiles: current.map((index) => ({
        index,
        width: Math.max(1, Math.round(usable[index] * targetRowHeight)),
        height: targetRowHeight,
      })),
    })
  }
  return rows

  /**
   * Eine VOLLE Zeile. Die Breiten entstehen aus der ungerundeten Zeilenhoehe, und das letzte Bild
   * bekommt den Rest auf die Containerbreite - erst dadurch ist die Summe EXAKT, statt um die
   * aufsummierten Rundungsfehler danebenzuliegen.
   */
  function justify(indices: readonly number[], exactHeight: number): JustifiedRow {
    const height = Math.max(1, Math.round(exactHeight))
    const available = containerWidth - gap * (indices.length - 1)
    const tiles: JustifiedTile[] = []
    let used = 0
    indices.forEach((index, position) => {
      const isLast = position === indices.length - 1
      const width = isLast
        ? Math.max(1, available - used)
        : Math.max(1, Math.round(usable[index] * exactHeight))
      used += width
      tiles.push({ index, width, height })
    })
    return { height, tiles }
  }
}
