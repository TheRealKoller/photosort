/**
 * Aus der gelieferten Restdauer in Sekunden wird die angezeigte Spanne.
 *
 * Die Stufenleiter lebt HIER und nicht im Backend: Der Server misst, das Frontend entscheidet über
 * die gezeigte Genauigkeit (ADR 0116 Punkt 4). Eine serverseitig gerechnete Ober- und Untergrenze
 * behauptete eine Genauigkeitsaussage, die die Messung nicht hergibt.
 *
 * Es wird nie eine Einzelzahl gezeigt - auch an den beiden Rändern nicht. "noch ca. 30 Sekunden"
 * wäre genau eine.
 */

/** Woher die Angabe kommt - `null` gibt es nicht: ein Schritt ohne Angabe bekommt gar keine. */
export type EtaKind = 'measured' | 'unknown' | 'experience'

/**
 * Der eine feste Satz, solange keine belastbare Schätzung vorliegt. Für alle drei Ursachen
 * (zu wenige verarbeitete Einheiten, zu kurze Zeit seit Phasenbeginn, kein gespeicherter
 * Phasenbeginn) ununterscheidbar - `null` heißt "noch nicht abschätzbar", nie "keine Restdauer".
 */
export const ETA_UNKNOWN_TEXT = 'wird noch ermittelt'

/**
 * Der Erfahrungswert des Rangfolge-Teilschritts. Er trägt bewusst keine Ziffer und nie die Form
 * "noch ca. A–B": Er steht unmittelbar neben gemessenen Angaben und würde sonst als eine gelesen.
 */
export const ETA_EXPERIENCE_TEXT = 'erfahrungsgemäß kurz'

/** Die sieben Stufentexte in aufsteigender Reihenfolge - der vollständige Textvorrat (AK2). */
export const ETA_STEP_TEXTS = [
  'nur noch wenige Sekunden',
  'noch ca. 1–2 Minuten',
  'noch ca. 2–5 Minuten',
  'noch ca. 5–10 Minuten',
  'noch ca. 10–20 Minuten',
  'noch ca. 20–40 Minuten',
  'noch über 40 Minuten',
] as const

/**
 * Die Untergrenze jeder Stufe in Sekunden, EINSCHLIESSEND: Ein Wert genau auf der Grenze gehört
 * bereits zur höheren Stufe. Die erste Stufe hat keine eigene Grenze (alles darunter).
 */
const ETA_STEP_LOWER_BOUNDS_SECONDS = [60, 120, 300, 600, 1200, 2400] as const

function measuredText(seconds: number): string {
  let index = 0
  for (const bound of ETA_STEP_LOWER_BOUNDS_SECONDS) {
    if (seconds < bound) {
      break
    }
    index += 1
  }
  return ETA_STEP_TEXTS[index]
}

/**
 * Der anzuzeigende Text zu einer Art und der gelieferten Sekundenzahl.
 *
 * `measured` ohne Wert fällt auf `ETA_UNKNOWN_TEXT` zurück statt auf ein leeres Feld - AK4
 * schließt sowohl das leere Feld als auch eine Zahl aus, und eine dritte Möglichkeit gibt es an
 * dieser Stelle nicht.
 */
export function etaText(kind: EtaKind, seconds: number | null): string {
  if (kind === 'experience') {
    return ETA_EXPERIENCE_TEXT
  }
  if (kind === 'unknown' || seconds === null) {
    return ETA_UNKNOWN_TEXT
  }
  return measuredText(seconds)
}
