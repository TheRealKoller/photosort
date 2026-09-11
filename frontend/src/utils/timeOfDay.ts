// `taken_at` ist ein naives Datetime (EXIF DateTimeOriginal, keine Zeitzone), serialisiert ohne
// `Z`/Offset (z.B. "2026-07-20T10:00:00"). Zeit-/Datumsextraktion deshalb per String-Slicing der
// ISO-Zeichenkette statt ueber `Date`-Getter (`getHours()`/`getUTCHours()`) - deren Ergebnis
// hinge vom An-/Abwesenheitszustand eines `Z`-Suffix und der Zeitzone des ausfuehrenden
// Browsers/Testrunners ab. Min/Max-Zeitpunkt-Vergleich ebenfalls per reinem String-Vergleich
// (ISO-8601 sortiert lexikographisch = chronologisch), kein `Date`-Parsing noetig.

import type { ClusterPlace } from '../api/types'

/** Kalendertag als `YYYY-MM-DD`, reines String-Slicing. */
export function dayKeyOf(iso: string): string {
  return iso.slice(0, 10)
}

/** Stunde (0-23) der Aufnahme, reines String-Slicing. */
export function hourOf(iso: string): number {
  return Number(iso.slice(11, 13))
}

// Tageszeit-Bucket-Tabelle: untere Grenze inklusive, obere
// Grenze exklusiv, lueckenlos. Aufsteigend nach `startHour` sortiert - Nachts deckt sowohl
// [22,24) als auch [0,5) ab und ist deshalb der Fallback-Wert, falls keine andere Startstunde
// erreicht wird (siehe timeOfDayBucketLabel).
const TIME_OF_DAY_BUCKETS: readonly { startHour: number; label: string }[] = [
  { startHour: 5, label: 'Morgens' },
  { startHour: 8, label: 'Vormittags' },
  { startHour: 11, label: 'Mittags' },
  { startHour: 13, label: 'Nachmittags' },
  { startHour: 18, label: 'Abends' },
  { startHour: 22, label: 'Nachts' },
]

/** Sprechende Tageszeit-Bezeichnung fuer eine Stunde (0-23), siehe Bucket-Tabelle oben. */
export function timeOfDayBucketLabel(hour: number): string {
  let label = 'Nachts'
  for (const bucket of TIME_OF_DAY_BUCKETS) {
    if (hour >= bucket.startHour) {
      label = bucket.label
    }
  }
  return label
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
 * Formatiert eine bereits serverseitig gerundete Koordinate auf genau zwei Nachkommastellen.
 *
 * REINE FORMATIERUNG: die Rundungskonvention selbst liegt im Backend, weil dort dieselbe Zahl
 * ueber `"coordinate"` vs. `"multiple"` entscheidet - hier wird nur noch die Stellenzahl
 * vereinheitlicht (`48.9` -> `48.90`, damit die Anzeige ueber alle Cluster hinweg dieselbe Breite
 * hat).
 *
 * `-0` wird zu `0.00`: `(-0).toFixed(2)` liefert in JavaScript zwar bereits `"0.00"`, aber jeder
 * Wert knapp unterhalb von null (`-0.001`) ergaebe `"-0.00"` - eine Himmelsrichtung, die es nicht
 * gibt.
 */
function formatCoordinate(value: number): string {
  const formatted = value.toFixed(2)
  return formatted === '-0.00' ? '0.00' : formatted
}

/**
 * Der Ortsteil der Cluster-Ueberschrift, oder `null`, wenn es keinen gibt.
 *
 * Das Frontend bildet die RANGFOLGE NICHT NACH - der Server liefert mit `kind` bereits den
 * aufgeloesten Zustand, und nur er kennt den vollstaendigen Cluster (die Ansicht sieht je Partition
 * nur die Top-N). Hier steht deshalb ein reines `switch`, keine Priorisierung.
 *
 * Die `null`-Rueckfaelle bei fehlendem Namen bzw. fehlenden Zahlen sind defensiv: der Server
 * liefert diese Kombinationen nicht, aber `"null, null"` in einer Ueberschrift waere schlimmer als
 * gar kein Ortsteil.
 */
function clusterPlaceLabel(place: ClusterPlace | null | undefined): string | null {
  if (!place) {
    return null
  }
  switch (place.kind) {
    case 'landmark':
      return place.landmark_name || null
    case 'coordinate':
      return place.lat === null || place.lon === null
        ? null
        : `${formatCoordinate(place.lat)}, ${formatCoordinate(place.lon)}`
    case 'multiple':
      // Traegt bewusst NIE eine stellvertretende Koordinate - den einen Ort, den sie
      // repraesentieren muesste, gibt es gerade nicht.
      return 'Mehrere Orte'
  }
}

/**
 * Ermittelt Tag und fertige Cluster-Ueberschrift aus den sichtbaren Fotos eines Clusters.
 * Früheste-Foto-Regel: sowohl Tag als auch Tageszeit-Bucket werden vom chronologisch fruehesten
 * Foto abgeleitet, die angezeigte Spanne bleibt die exakte Min/Max-Spanne aller uebergebenen
 * (sichtbaren) Fotos. Erwartet ein nicht-leeres Array.
 *
 * Ein optionaler ORTSTEIL steht davor: `"<Ort> · <Tageszeit> (<Zeitspanne>)"`. Der Ort
 * ERGÄNZT die Tageszeit, er ersetzt sie nie.
 *
 * Der Ortsteil wird vom ERSTEN Foto mit gesetztem `cluster_place` uebernommen und nicht selbst
 * aggregiert: der Server sichert zu, dass der Wert auf jedem Foto desselben Clusters identisch
 * ist. Genau daraus folgt die TEILMENGEN-INVARIANZ - der Ortsteil haengt nicht davon ab, wie
 * viele Fotos des Clusters gerade sichtbar sind (Tag, Tageszeit und Zeitspanne tun das
 * unveraendert schon).
 *
 * Das Trennzeichen ist ein Mittelpunkt und bewusst kein Komma: das waere mit dem Dezimaltrenner
 * der Koordinate zu verwechseln.
 */
export function formatClusterHeading(
  photos: { taken_at: string; cluster_place?: ClusterPlace | null }[],
): {
  dayKey: string
  heading: string
  // Roher (nicht formatierter) Zeitstempel des chronologisch frühesten Fotos - die einzige
  // Quelle für die chronologische Cluster-Sortierung, im Aufrufer nicht neu berechnen.
  earliestIso: string
} {
  // Expliziter Guard statt eines unklaren "cannot read properties of undefined" beim
  // Zeilenzugriff auf photos[0]: der Vertrag "nicht-leeres Array" gilt zur Laufzeit, nicht
  // nur im Docstring.
  if (photos.length === 0) {
    throw new Error('formatClusterHeading() erwartet ein nicht-leeres Array')
  }
  let minIso = photos[0].taken_at
  let maxIso = photos[0].taken_at
  for (const photo of photos) {
    if (photo.taken_at < minIso) {
      minIso = photo.taken_at
    }
    if (photo.taken_at > maxIso) {
      maxIso = photo.taken_at
    }
  }
  const dayKey = dayKeyOf(minIso)
  const bucketLabel = timeOfDayBucketLabel(hourOf(minIso))
  const timeRange = formatTimeRange(minIso, maxIso)
  const timePart = `${bucketLabel} (${timeRange})`
  const placeLabel = clusterPlaceLabel(photos.find((photo) => photo.cluster_place)?.cluster_place)
  return {
    dayKey,
    heading: placeLabel === null ? timePart : `${placeLabel} · ${timePart}`,
    earliestIso: minIso,
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
