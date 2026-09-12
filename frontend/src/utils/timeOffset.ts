/**
 * Formatierung, Umrechnung und Validierung des Kamera-Zeitversatzes - reine Funktionen mit
 * eigenen Unit-Tests an EINER Stelle. Keine dieser Rechnungen gehört in eine Komponente: der
 * Dialog bedient dieselbe Umrechnung wie die Liste und der Vorschlagsfluss, und drei Kopien
 * liefen auseinander.
 *
 * Durchgehend deutsche Darstellung - die Anwendung hat zwei deutschsprachige Nutzer und keine
 * Lokalisierungsschicht.
 */

/** ±100 Jahre in Minuten - derselbe Wert wie `backend/src/photosort/cameras.py`. Bewusst
 * gespiegelt statt vom Server geholt: die Eingabeprüfung muss ohne Anfrage auskommen, und der
 * Server weist einen abweichenden Wert ohnehin selbst zurück (dort liegt die Zusage). */
export const MAX_TIME_OFFSET_MINUTES = 52_560_000

/** Das Wort für "kein Versatz gesetzt". Eine "0:00" liest sich wie ein gesetzter Wert. */
export const NO_OFFSET_LABEL = 'kein Versatz'

const MINUTES_PER_HOUR = 60
const MINUTES_PER_DAY = 24 * MINUTES_PER_HOUR

/** Typografisches Minus (U+2212), nicht der Bindestrich: ein Bindestrich vor einer Uhrzeit liest
 * sich als Trennstrich. */
const MINUS = '−'

/** Welche Richtung die Kamerauhr falsch ging - im KLARTEXT statt als nacktes Vorzeichen.
 *
 * `ahead` = "Kamerauhr ging vor" -> die Zeiten werden ZURÜCKgestellt -> NEGATIVER Versatz.
 * `behind` = "Kamerauhr ging nach" -> die Zeiten werden VORgestellt -> POSITIVER Versatz.
 *
 * Ein nacktes `+`/`−` ist die Stelle, an der eine Fehlbedienung den Fehler verdoppelt statt ihn
 * zu beheben. */
export type ClockDirection = 'ahead' | 'behind'

/** Die vier Eingabefelder des Dialogs. Tage sind kein Zierrat: eine Kamera mit zurückgesetzter
 * Uhr steht Jahre daneben, nicht Stunden - eine Form, die nur Stunden kennt, kann den häufigsten
 * schweren Fall nicht abbilden. */
export interface OffsetFields {
  direction: ClockDirection
  days: number
  hours: number
  minutes: number
}

export interface OffsetProblem {
  field: 'days' | 'hours' | 'minutes'
  message: string
}

/** Der Versatz als lesbare Spanne, mit Vorzeichen. Tage erscheinen nur, wenn es welche gibt. */
export function formatTimeOffset(offsetMinutes: number): string {
  if (offsetMinutes === 0) {
    return NO_OFFSET_LABEL
  }
  const sign = offsetMinutes < 0 ? MINUS : '+'
  const total = Math.abs(offsetMinutes)
  const days = Math.floor(total / MINUTES_PER_DAY)
  const hours = Math.floor((total % MINUTES_PER_DAY) / MINUTES_PER_HOUR)
  const minutes = total % MINUTES_PER_HOUR
  const clock = `${hours}:${String(minutes).padStart(2, '0')}`
  if (days === 0) {
    return `${sign}${clock}`
  }
  return `${sign}${days} ${days === 1 ? 'Tag' : 'Tage'} ${clock}`
}

/** Felder -> Minuten. `behind` (Uhr ging nach) ergibt einen POSITIVEN Versatz.
 *
 * Die Addition von `0` normalisiert `-0` auf `0` (IEEE 754, dasselbe Mittel wie in
 * `events.py::_rounded`): Ohne sie liefert die zurückstellende Richtung bei lauter Nullen ein
 * `-0`, das sich durch jeden `=== 0`-Vergleich schmuggelt, aber in `Object.is` und in einem
 * Zustandsvergleich als eigener Wert auftritt. */
export function offsetFromFields(fields: OffsetFields): number {
  const magnitude = fields.days * MINUTES_PER_DAY + fields.hours * MINUTES_PER_HOUR + fields.minutes
  return (fields.direction === 'behind' ? magnitude : -magnitude) + 0
}

/** Minuten -> Felder. Die Null fällt auf `ahead`, damit der Dialog einen definierten
 * Anfangszustand hat - eine Richtung muss gewählt sein, auch wenn sie noch nichts bedeutet. */
export function offsetToFields(offsetMinutes: number): OffsetFields {
  const total = Math.abs(offsetMinutes)
  return {
    direction: offsetMinutes > 0 ? 'behind' : 'ahead',
    days: Math.floor(total / MINUTES_PER_DAY),
    hours: Math.floor((total % MINUTES_PER_DAY) / MINUTES_PER_HOUR),
    minutes: total % MINUTES_PER_HOUR,
  }
}

/** `null` heißt "gültig". Sonst das ERSTE beanstandete Feld samt Meldung für die Anzeige am
 * Feld - Stunden 0-23 und Minuten 0-59, damit eine Spanne genau eine Schreibweise hat. */
export function validateOffsetFields(fields: OffsetFields): OffsetProblem | null {
  if (!Number.isInteger(fields.days) || fields.days < 0) {
    return { field: 'days', message: 'Tage: ganze Zahl ab 0.' }
  }
  if (!Number.isInteger(fields.hours) || fields.hours < 0 || fields.hours > 23) {
    return { field: 'hours', message: 'Stunden: ganze Zahl von 0 bis 23.' }
  }
  if (!Number.isInteger(fields.minutes) || fields.minutes < 0 || fields.minutes > 59) {
    return { field: 'minutes', message: 'Minuten: ganze Zahl von 0 bis 59.' }
  }
  if (Math.abs(offsetFromFields(fields)) > MAX_TIME_OFFSET_MINUTES) {
    return { field: 'days', message: 'Der Versatz darf höchstens 100 Jahre betragen.' }
  }
  return null
}

/**
 * Eine ISO-Zeit um den Versatz verschoben, im Format der API (zonenlos, sekundengenau).
 *
 * Speist die lebende Vorschau des Dialogs an einem ECHTEN Foto - die tragende Maßnahme gegen ein
 * falsches Vorzeichen: der Nutzer prüft das Ergebnis, nicht die Rechnung.
 *
 * `null` bei einer unlesbaren Eingabe: ein "Invalid Date" in der Vorschau wäre schlimmer als
 * keine Vorschau.
 */
export function applyOffsetToIsoTime(isoTime: string, offsetMinutes: number): string | null {
  const parsed = new Date(isoTime)
  if (Number.isNaN(parsed.getTime())) {
    return null
  }
  const shifted = new Date(parsed.getTime() + offsetMinutes * 60_000)
  // `toISOString()` rechnet auf UTC um und hänge damit ein `Z` an einen zonenlosen Wert; die
  // Bestandteile werden deshalb einzeln gelesen - dieselbe Zone, in der der Wert hereinkam.
  const pad = (value: number): string => String(value).padStart(2, '0')
  return (
    `${shifted.getFullYear()}-${pad(shifted.getMonth() + 1)}-${pad(shifted.getDate())}` +
    `T${pad(shifted.getHours())}:${pad(shifted.getMinutes())}:${pad(shifted.getSeconds())}`
  )
}
