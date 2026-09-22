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
 * SIE SETZT SELBST NICHTS ZUSAMMEN UND ZERLEGT NICHTS: Den Namen holt sie aus `eventPlaceName` -
 * der einen Stelle, an der Sehenswuerdigkeitsname und Ortsname zusammenkommen (Spec 0514,
 * ADR 0120) -, und haengt hier nur die Zeitspanne an. Vier Textformen entstehen so:
 * `Eiffelturm, Paris, Gros-Caillou (10:30–11:45 Uhr)`, `Eiffelturm (…)`, `Paris (…)` und
 * `Position 3 (…)`, wenn keine Ortsangabe aufloest.
 *
 * Die Zeitspanne bleibt in JEDEM Fall Teil der Ueberschrift - sie traegt die Unterscheidbarkeit,
 * wenn mehrere Events denselben Namen tragen.
 *
 * Eine Koordinate erscheint ausdruecklich NICHT als Name - sie bleibt in `place`.
 *
 * Die Form "Ort, Viertel" kommt FERTIG vom Server (ADR 0102 Punkt 4): Sie ist eine Aussage ueber
 * alle Events eines Laufs, die das Frontend gar nicht treffen koennte.
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
 * Der Ort EINES Events als Ueberschriftsname - ohne die Zeitspanne und ohne den Rückfall auf die
 * Nummer. `null` heißt "keine Ortsangabe".
 *
 * SEIT SPEC 0514 (ADR 0120) STEHEN DIE BEIDEN TEILE NEBENEINANDER, der Name zuerst:
 * `Eiffelturm, Paris, Gros-Caillou`. Der Sehenswürdigkeitsname (`place.landmark_name`,
 * Modellantwort) verdrängt den aufgelösten Ortsnamen (`place_name`, Ortsdatensatz Dritter) nicht
 * mehr; er tritt daneben. Vier Ausgänge: beide → `"<Name>, <Ort>"`, nur Name → `"<Name>"`, nur Ort
 * → `"<Ort>"`, keins → `null`. Eine Koordinate erscheint ausdrücklich NICHT als Name - sie bleibt
 * in `place` (verdrängt bleibt allein die KOORDINATENSTUFE).
 *
 * Das Komma steht hinter einem Leerzeichen und damit an einer Umbruchstelle; gekürzt wird nicht -
 * `MAX_PLACE_NAME_LENGTH` ist eine Servergrenze für die Serverform "Ort, Viertel".
 *
 * Der `null`/`''`-Rückfall gilt JE TEIL (`usableName`): Der Server liefert diese Kombinationen
 * nicht, aber `"null"` als Ortsangabe wäre schlimmer als gar keine. Fehlt ein Teil, steht der
 * andere ALLEIN - kein Trennzeichen ohne zweiten Teil, keine leere Klammer.
 *
 * EINE FUNKTION FÜR BEIDE AUFRUFSTELLEN (Ereignis-Überschrift und Bilddetailansicht): Entstünde die
 * Zusammensetzung ein zweites Mal, liefe sie mit dieser auseinander. Der strukturelle Wächter
 * `photoDetail.structure.test.ts` bindet das fest.
 *
 * S1/S2 — KEIN INTERPRETIEREN: Beide Teile sind fremderzeugter Text und treffen hier in EINEM Wert
 * zusammen. Sie werden ausschließlich zu einer Zeichenkette verbunden und nirgends ausgewertet -
 * das Escaping leistet React an der Renderstelle, und der Nachweis dafür gehört dorthin, nicht in
 * den Test dieser Funktion.
 */
export function eventPlaceName(event: EventOut): string | null {
  const landmark = event.place?.kind === 'landmark' ? (event.place.landmark_name ?? null) : null
  const name = usableName(landmark)
  const place = usableName(event.place_name)
  if (name === null) {
    return place
  }
  return place === null ? name : `${name}, ${place}`
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
