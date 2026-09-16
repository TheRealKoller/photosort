/**
 * Zahlenformatierung der Projekt-Statistikseite. Reine Funktionen mit eigenen Unit-Tests - die
 * Seite selbst enthaelt keine Formatierungslogik.
 *
 * Durchgehend deutsches Zahlenformat (Dezimalkomma, Tausenderpunkt): die Anwendung hat genau zwei
 * deutschsprachige Nutzer, es gibt keine Lokalisierungsschicht und soll auch keine geben.
 */

const DECIMAL_ONE = new Intl.NumberFormat('de-DE', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})
const DECIMAL_TWO = new Intl.NumberFormat('de-DE', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})
const INTEGER = new Intl.NumberFormat('de-DE', { maximumFractionDigits: 0 })

/** Basis 1024 - dieselbe Zaehlweise wie `du`/der Dateimanager. */
const MEBIBYTE = 1024 * 1024
const GIBIBYTE = 1024 * MEBIBYTE

/** Wert nicht ermittelbar. Bewusst NICHT fuer den Zahlwert 0 verwenden: "nichts belegt" ist eine
 * Aussage, "nicht ermittelbar" die Abwesenheit einer Aussage. */
export const NOT_AVAILABLE = '—'

/**
 * Speichergroesse in MB (unterhalb 1 GB) bzw. GB (ab 1 GB), je eine Nachkommastelle.
 *
 * Die exakte Null bekommt bewusst KEINE Nachkommastelle ("0 MB", nicht "0,0 MB"): sie ist eine
 * harte Aussage, waehrend "0,0 MB" heisst "etwas ist da, aber weniger als die angezeigte
 * Genauigkeit". `null` heisst "nicht ermittelbar" und wird als Strich dargestellt.
 */
export function formatBytes(bytes: number | null): string {
  if (bytes === null) {
    return NOT_AVAILABLE
  }
  if (bytes === 0) {
    return '0 MB'
  }
  if (bytes >= GIBIBYTE) {
    return `${DECIMAL_ONE.format(bytes / GIBIBYTE)} GB`
  }
  return `${DECIMAL_ONE.format(bytes / MEBIBYTE)} MB`
}

/**
 * Geldbetrag mit zwei Nachkommastellen und der Kennzeichnung "USD" (der Abrechnungswaehrung
 * beider Provider - es wird bewusst nicht umgerechnet).
 *
 * Ein Betrag groesser 0, der auf 0,00 runden wuerde, wird als "< 0,01 USD" ausgewiesen: auf einer
 * Seite zur Kostenkontrolle darf ein tatsaechlich angefallener Betrag nicht als "nichts
 * ausgegeben" erscheinen.
 *
 * Bewusst NICHT dieselbe Funktion wie die `$0.0052`-Darstellung der Vorab-Schaetzung in
 * `components/ClassificationSection.tsx`: die Schaetzung braucht vier Nachkommastellen (ihre
 * Betraege liegen pro Bild im Zehntelcent-Bereich), die Ist-Summe hier zwei plus die
 * Waehrungskennzeichnung.
 */
export function formatUsd(amountUsd: number): string {
  if (amountUsd > 0 && Math.round(amountUsd * 100) === 0) {
    return '< 0,01 USD'
  }
  return `${DECIMAL_TWO.format(amountUsd)} USD`
}

/**
 * Kaufmaennisch gerundete Prozentzahl OHNE Nachkommastelle und ohne Leerzeichen vor dem
 * Prozentzeichen (`92%`) - vermeidet eine Scheingenauigkeit, die die zugrundeliegenden, teils
 * heuristischen Werte nicht hergeben.
 *
 * Kandidatenliste und Konfidenzblock der Statistikseite teilen sich diese eine Darstellung; eine
 * zweite Kopie liefe unweigerlich auseinander.
 *
 * BEWUSST OHNE Nachkommastelle, Leerzeichen und deutsches Dezimalkomma (anders als die Betrags-
 * und Speicherangaben dieser Seite): dieselbe Zahl erscheint am Foto und in der Statistik, und
 * zwei Formen fuer eine Zahl liesse den Leser nach dem Unterschied suchen.
 *
 * Und bewusst OHNE die `< 0,01`-Sonderregel von `formatUsd`: ein kleiner Wert ungleich null wird
 * als `0%` gezeigt. Bei einem Geldbetrag darf ein tatsaechlich angefallener Betrag nicht als
 * "nichts ausgegeben" erscheinen; eine Modell-Selbsteinschaetzung von 0,4 % ist dagegen sachlich
 * "0 %" - und "< 1 %" laese sich hier als Alarmzeichen statt als Rundungshinweis.
 *
 * Die Eingabe ist immer bereits auf [0, 1] normiert (Kriterienwerte aus criteria.py, Konfidenzen
 * am Parser-Rand geprueft), also nie negativ - `Math.round` rundet in diesem Bereich identisch zu
 * "kaufmaennisch" (0.5 aufwaerts).
 */
export function formatCriterionPercent(value: number): string {
  return `${criterionPercentValue(value)}%`
}

/**
 * Derselbe gerundete Prozentwert als ZAHL - fuer Stellen, die ihn zusaetzlich als Geometrie
 * brauchen (die Fuellhoehe eines Motivsymbols).
 *
 * EINE Rundungsstelle fuer Text und Geometrie: Runden beide getrennt, koennen angezeigte Zahl und
 * gezeigte Hoehe auseinanderlaufen, und die Anzeige behauptete eine Staerke, die die Zahl nicht
 * nennt.
 */
export function criterionPercentValue(value: number): number {
  return Math.round(value * 100)
}

/** Ganze Zahl mit deutschem Tausenderpunkt - die Fotoanzahlen dieser Seite werden fuenfstellig. */
export function formatCount(value: number): string {
  return INTEGER.format(value)
}

const DATE = new Intl.DateTimeFormat('de-DE', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
})
const DATE_TIME = new Intl.DateTimeFormat('de-DE', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

/** Reines Datum (fuer den Aufnahmezeitraum - die Uhrzeit eines Fotos ist hier ohne Aussage). */
export function formatDate(isoDate: string): string {
  return DATE.format(new Date(isoDate))
}

/** Datum mit Uhrzeit (fuer Lauf-Zeitpunkte - dort ist die Uhrzeit die eigentliche Information). */
export function formatDateTime(isoDate: string): string {
  return DATE_TIME.format(new Date(isoDate))
}

/**
 * Der Aufnahmezeitraum eines Projekts - geteilt zwischen Projektkarte und Statistikseite.
 *
 * Vier entscheidbare Faelle:
 * 1. beide gesetzt, VERSCHIEDENE Kalendertage -> "02.04.2019 – 17.08.2019" (Gedankenstrich
 *    U+2013, je ein Leerzeichen),
 * 2. beide gesetzt, DERSELBE Kalendertag -> das Datum EINMAL,
 * 3./4. mindestens einer `null` -> `NOT_AVAILABLE`.
 *
 * Der Ein-Tages-Fall wird am FORMATIERTEN Datum entschieden, nicht am rohen Zeitstempel: zwei
 * Aufnahmen desselben Tages sind praktisch nie zeitstempelgleich, und "02.04.2019 – 02.04.2019"
 * liest sich als Fehler statt als Aussage.
 *
 * Genau EIN `null` ist heute unmoeglich (`MIN`/`MAX` derselben Abfrage sind entweder beide `NULL`
 * oder beide gesetzt) und faellt trotzdem auf den Strich: die Zeile soll bei einer kuenftigen
 * Aenderung nichts Halbes behaupten.
 */
export function formatTakenAtRange(earliest: string | null, latest: string | null): string {
  if (earliest === null || latest === null) {
    return NOT_AVAILABLE
  }
  const from = formatDate(earliest)
  const to = formatDate(latest)
  return from === to ? from : `${from} – ${to}`
}

// Anzeigename eines Cloud-Vision-Providers (backend `provider`-Feld, aktuell "anthropic"/
// "mistral") - geteilt zwischen der Klassifizierungs-Sektion, der Fortschrittsanzeige, der
// Kostenschaetzung und der Grundlagenzeile der Motivstaerken. Fallback auf den rohen Wert fuer
// einen kuenftigen, hier noch nicht gepflegten Provider - kein Absturz.
//
// Liegt seit Spec 0427 hier und nicht mehr in `categoryLabels.ts`: ein Anbietername ist keine
// Kategorie, und jene Datei ist mit der Kategorie-Welt entfallen.
const PROVIDER_DISPLAY_NAMES: Readonly<Record<string, string>> = {
  anthropic: 'Anthropic',
  mistral: 'Mistral',
}

export function formatProviderLabel(provider: string): string {
  if (Object.hasOwn(PROVIDER_DISPLAY_NAMES, provider)) {
    return PROVIDER_DISPLAY_NAMES[provider]
  }
  return provider
}
