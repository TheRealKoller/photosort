// `taken_at`, `started_at` und `ended_at` sind naive Datetimes (keine Zeitzone), serialisiert
// ohne `Z`/Offset (z.B. "2026-07-20T10:00:00"). Zeit-/Datumsextraktion deshalb per String-Slicing
// der ISO-Zeichenkette statt ueber `Date`-Getter (`getHours()`/`getUTCHours()`) - deren Ergebnis
// hinge vom An-/Abwesenheitszustand eines `Z`-Suffix und der Zeitzone des ausfuehrenden
// Browsers/Testrunners ab.

import type { EventOut } from '../api/types'

/** Kalendertag als `YYYY-MM-DD`, reines String-Slicing. */
export function dayKeyOf(iso: string): string {
  return iso.slice(0, 10)
}

/** Stunde (0-23) der Aufnahme, reines String-Slicing. */
export function hourOf(iso: string): number {
  return Number(iso.slice(11, 13))
}

/**
 * Formatiert die Uhrzeitspanne zweier ISO-Zeitstempel, kollabiert bei identischer Minute auf
 * einen einzelnen Zeitpunkt.
 */
export function formatTimeRange(minIso: string, maxIso: string): string {
  const minTime = minIso.slice(11, 16)
  const maxTime = maxIso.slice(11, 16)
  if (minTime === maxTime) {
    return `${minTime} Uhr`
  }
  return `${minTime}–${maxTime} Uhr`
}

/**
 * Tag und fertige Ueberschrift EINES Events - eine reine Funktion ueber der `events`-Zeile.
 *
 * DREI STUFEN, sequenziell: die erkannte Sehenswuerdigkeit (`Eiffelturm (10:30–11:45 Uhr)`), der
 * aufgeloeste Ortsname (`Berlin, Kreuzberg (10:30–11:45 Uhr)`), sonst die Nummer
 * (`Position 3 (10:30–11:45 Uhr)`). Die Zeitspanne bleibt in JEDEM Fall Teil der Ueberschrift -
 * sie traegt die Unterscheidbarkeit, wenn mehrere Events denselben Namen tragen und kein Viertel
 * vorliegt.
 *
 * Eine Koordinate erscheint ausdruecklich NICHT als Name - sie bleibt in `place`.
 *
 * Die zusammengesetzte Form "Ort, Viertel" kommt FERTIG vom Server (ADR 0102 Punkt 4): Sie ist
 * eine Aussage ueber alle Events eines Laufs, die das Frontend gar nicht treffen koennte. Hier
 * wird nichts zusammengesetzt und nichts zerlegt.
 *
 * Anders als die frueher hier stehende Cluster-Ueberschrift haengt nichts davon ab, welche Fotos
 * gerade sichtbar sind: Nummer, Zeitspanne und Name stehen in der Zeile des Events.
 */
export function formatEventHeading(event: EventOut): { dayKey: string; heading: string } {
  const timeRange = formatTimeRange(event.started_at, event.ended_at)
  const name = eventPlaceName(event)
  return {
    dayKey: dayKeyOf(event.started_at),
    heading: name === null ? `Position ${event.position} (${timeRange})` : `${name} (${timeRange})`,
  }
}

/**
 * Der Name des Ortes EINES Events - die ersten zwei der drei Stufen aus `formatEventHeading`,
 * ohne die Zeitspanne und ohne den Rückfall auf die Nummer. `null` heißt "kein Ortsname".
 *
 * ZWEI STUFEN, sequenziell: die erkannte Sehenswürdigkeit (`place.landmark_name`, Modellantwort),
 * sonst der aufgelöste Ortsname (`place_name`, Ortsdatensatz Dritter). Eine Koordinate erscheint
 * ausdrücklich NICHT als Name - sie bleibt in `place`.
 *
 * Der `null`/`''`-Rückfall je Stufe ist defensiv: Der Server liefert diese Kombinationen nicht,
 * aber `"null"` als Ortsangabe wäre schlimmer als gar keine. Fällt eine Stufe aus, gewinnt die
 * NÄCHSTE - nicht sofort `null`.
 *
 * EINE FUNKTION FÜR BEIDE AUFRUFSTELLEN (Ereignis-Überschrift und Bilddetailansicht): Entstünde die
 * Rangfolge ein zweites Mal, liefe sie mit dieser auseinander. Der strukturelle Wächter
 * `photoDetail.structure.test.ts` bindet das fest.
 *
 * S2 — REINE FUNKTION ÜBER DER EVENT-ZEILE: Sie setzt nichts zusammen und interpretiert nichts;
 * die Form "Ort, Viertel" kommt fertig vom Server. Beide gelesenen Felder tragen S1 (extern
 * erzeugter Text, ausschließlich als regulärer React-Textknoten rendern). Der Nachweis dafür gehört
 * an die Renderstelle, nicht in den Test dieser Funktion.
 */
export function eventPlaceName(event: EventOut): string | null {
  const landmark = event.place?.kind === 'landmark' ? (event.place.landmark_name ?? null) : null
  return usableName(landmark) ?? usableName(event.place_name)
}

function usableName(value: string | null | undefined): string | null {
  return value === null || value === undefined || value === '' ? null : value
}

const WEEKDAY_LABELS = [
  'Sonntag',
  'Montag',
  'Dienstag',
  'Mittwoch',
  'Donnerstag',
  'Freitag',
  'Samstag',
]

/** Formatiert einen `dayKeyOf(...)`-Kalendertag als "Wochentag TT.MM.JJJJ", z.B. "Montag 20.07.2026". */
export function formatDayHeading(dayKey: string): string {
  const [year, month, day] = dayKey.split('-').map(Number)
  // Bewusst `T00:00:00` (lokale Mitternacht) statt eines bloßen Datums-Strings an `new Date()`
  // uebergeben: `new Date("2026-07-20")` waere UTC-Mitternacht, `new Date("2026-07-20T00:00:00")`
  // dagegen lokale Mitternacht - in Zeitzonen westlich von UTC wuerde die erste Variante sonst
  // teils den falschen (vorherigen) Wochentag liefern.
  const date = new Date(`${dayKey}T00:00:00`)
  const weekday = WEEKDAY_LABELS[date.getDay()]
  const dd = String(day).padStart(2, '0')
  const mm = String(month).padStart(2, '0')
  return `${weekday} ${dd}.${mm}.${year}`
}
