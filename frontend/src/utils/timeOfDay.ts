// specs/features/0039-kuratierung-tage-und-benannte-cluster.md
//
// `taken_at` ist ein naives Datetime (EXIF DateTimeOriginal, keine Zeitzone), serialisiert ohne
// `Z`/Offset (z.B. "2026-07-20T10:00:00"). Zeit-/Datumsextraktion deshalb per String-Slicing der
// ISO-Zeichenkette statt ueber `Date`-Getter (`getHours()`/`getUTCHours()`) - deren Ergebnis
// hinge vom An-/Abwesenheitszustand eines `Z`-Suffix und der Zeitzone des ausfuehrenden
// Browsers/Testrunners ab (siehe specs/architecture/0002-testkonzept.md, Sektion "Naive
// Datums-/Uhrzeit-Strings"). Min/Max-Zeitpunkt-Vergleich ebenfalls per reinem String-Vergleich
// (ISO-8601 sortiert lexikographisch = chronologisch), kein `Date`-Parsing noetig.

/** Kalendertag als `YYYY-MM-DD`, reines String-Slicing. */
export function dayKeyOf(iso: string): string {
  return iso.slice(0, 10)
}

/** Stunde (0-23) der Aufnahme, reines String-Slicing. */
export function hourOf(iso: string): number {
  return Number(iso.slice(11, 13))
}

// Tageszeit-Bucket-Tabelle (Akzeptanzkriterium 5 der Spec): untere Grenze inklusive, obere
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
 * einen einzelnen Zeitpunkt (Akzeptanzkriterium 4 der Spec).
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
 * Ermittelt Tag und fertige Cluster-Ueberschrift aus den sichtbaren Fotos eines Clusters.
 * Frueheste-Foto-Regel (Akzeptanzkriterium 6): sowohl Tag als auch Tageszeit-Bucket werden vom
 * chronologisch fruehesten Foto abgeleitet, die angezeigte Spanne bleibt die exakte Min/Max-
 * Spanne aller uebergebenen (sichtbaren) Fotos. Erwartet ein nicht-leeres Array - der Aufrufer
 * (`groupByClusterAndCategory`) ruft diese Funktion nur fuer Cluster mit mindestens einem noch
 * sichtbaren Foto auf, fuer erschoepfte Cluster wird stattdessen der `clusterMetaRef`-Cache
 * gelesen.
 */
export function formatClusterHeading(photos: { taken_at: string }[]): {
  dayKey: string
  heading: string
  // Roher (nicht formatierter) Zeitstempel des chronologisch fruehesten Fotos - Review-Fund
  // architect: statt diesen Wert ein zweites Mal im Aufrufer (`CurateCategoriesPage.tsx`) zu
  // berechnen, liefert diese Funktion ihn als Single Source of Truth gleich mit, genutzt fuer die
  // chronologische Cluster-Sortierung (Akzeptanzkriterium 2).
  earliestIso: string
} {
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
  return { dayKey, heading: `${bucketLabel} (${timeRange})`, earliestIso: minIso }
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
  // teils den falschen (vorherigen) Wochentag liefern (siehe Testkonzept).
  const date = new Date(`${dayKey}T00:00:00`)
  const weekday = WEEKDAY_LABELS[date.getDay()]
  const dd = String(day).padStart(2, '0')
  const mm = String(month).padStart(2, '0')
  return `${weekday} ${dd}.${mm}.${year}`
}
