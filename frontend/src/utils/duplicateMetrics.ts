/*
 * Messwerte und Serienspanne der Vergleichsansicht — Formatierung und Auszeichnung, rein.
 *
 * DIE AUSZEICHNUNG „BESTE JE MESSWERT" ENTSTEHT ÜBER DEN ANGEZEIGTEN, GERUNDETEN WERTEN, nie über
 * den Rohwerten: Zwei Aufnahmen, die beide als „413" erscheinen, tragen sie beide. Über Rohwerten
 * gebildet, trüge nur eine sie, und der Nutzer sähe zwei gleiche Zahlen mit verschiedenem Urteil.
 * Rundung und Anzeige kommen deshalb aus derselben Funktion.
 */

const SCHAERFE_FORMAT = new Intl.NumberFormat('de-DE', { maximumSignificantDigits: 3 })
const BELICHTUNG_FORMAT = new Intl.NumberFormat('de-DE', { maximumFractionDigits: 1 })

/** Schärfe mit drei signifikanten Stellen — die Zahl, die angezeigt UND verglichen wird. */
function roundedSharpness(value: number): number {
  return Number(value.toPrecision(3))
}

/** Belichtung als Prozentwert (Anteil × 100) mit höchstens einer Nachkommastelle. */
function roundedExposurePercent(value: number): number {
  return Math.round(value * 1000) / 10
}

export function formatSharpness(value: number | null): string {
  return value === null ? 'nicht gemessen' : SCHAERFE_FORMAT.format(roundedSharpness(value))
}

export function formatExposure(value: number): string {
  return `${BELICHTUNG_FORMAT.format(roundedExposurePercent(value))} % ohne Zeichnung`
}

function einheit(anzahl: number, einzahl: string, mehrzahl: string): string {
  return `${anzahl} ${anzahl === 1 ? einzahl : mehrzahl}`
}

/** Die Serienspanne in ganzen Sekunden, abgerundet auf die jeweils gröbste Einheit. */
export function formatSpan(seconds: number): string {
  if (seconds <= 0) {
    return 'unter einer Sekunde'
  }
  if (seconds < 60) {
    return einheit(seconds, 'Sekunde', 'Sekunden')
  }
  const minuten = Math.floor(seconds / 60)
  if (seconds < 3600) {
    return einheit(minuten, 'Minute', 'Minuten')
  }
  const stunden = Math.floor(seconds / 3600)
  const restMinuten = minuten % 60
  const teilStunden = einheit(stunden, 'Stunde', 'Stunden')
  return restMinuten === 0
    ? teilStunden
    : `${teilStunden} ${einheit(restMinuten, 'Minute', 'Minuten')}`
}

/**
 * Die Indizes mit dem besten angezeigten Wert. Leer bei weniger als zwei Werten oder wenn alle
 * angezeigten Werte gleich sind; `null` fällt aus der Wertung und trägt nie eine Auszeichnung.
 */
function bestIndices(
  displayed: (number | null)[],
  best: (values: number[]) => number,
): Set<number> {
  const vorhanden = displayed.filter((value): value is number => value !== null)
  if (vorhanden.length < 2 || vorhanden.every((value) => value === vorhanden[0])) {
    return new Set()
  }
  const bester = best(vorhanden)
  return new Set(
    displayed.flatMap((value, index) => (value !== null && value === bester ? [index] : [])),
  )
}

/** „— schärfste": das Maximum der angezeigten Schärfe (höher = schärfer). */
export function bestSharpnessIndices(values: (number | null)[]): Set<number> {
  return bestIndices(
    values.map((value) => (value === null ? null : roundedSharpness(value))),
    (vorhanden) => Math.max(...vorhanden),
  )
}

/** „— beste Belichtung": das Minimum der angezeigten Belichtung (weniger ohne Zeichnung). */
export function bestExposureIndices(values: (number | null)[]): Set<number> {
  return bestIndices(
    values.map((value) => (value === null ? null : roundedExposurePercent(value))),
    (vorhanden) => Math.min(...vorhanden),
  )
}
