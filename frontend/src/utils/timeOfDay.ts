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
 * Zwei Formen, sonst keine: der erkannte Name (`Eiffelturm (10:30–11:45 Uhr)`) oder der
 * Rueckfall auf die Nummer (`Position 3 (10:30–11:45 Uhr)`). Eine Koordinate erscheint
 * ausdruecklich NICHT als Name - sie bleibt in `place` und wird spaeter ueber Reverse-Geocoding
 * wieder einer.
 *
 * Anders als die frueher hier stehende Cluster-Ueberschrift haengt nichts davon ab, welche Fotos
 * gerade sichtbar sind: Nummer und Zeitspanne stehen in der Zeile des Events.
 */
export function formatEventHeading(event: EventOut): { dayKey: string; heading: string } {
  const timeRange = formatTimeRange(event.started_at, event.ended_at)
  const name = event.place?.kind === 'landmark' ? (event.place.landmark_name ?? null) : null
  return {
    dayKey: dayKeyOf(event.started_at),
    // Der `null`-Rueckfall bei einem `landmark` ohne Namen ist defensiv: der Server liefert diese
    // Kombination nicht, aber `"null"` in einer Ueberschrift waere schlimmer als die Nummer.
    heading:
      name === null || name === ''
        ? `Position ${event.position} (${timeRange})`
        : `${name} (${timeRange})`,
  }
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
