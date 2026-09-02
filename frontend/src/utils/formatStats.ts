/**
 * Zahlenformatierung der Projekt-Statistikseite (specs/features/0207-projekt-statistikseite.md,
 * Akzeptanzkriterien S1/K1/K4). Reine Funktionen mit eigenen Unit-Tests - die Seite selbst
 * enthaelt keine Formatierungslogik.
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

/** Basis 1024 (Akzeptanzkriterium S1) - dieselbe Zaehlweise wie `du`/der Dateimanager. */
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
 * Ein Betrag groesser 0, der auf 0,00 runden wuerde, wird als "< 0,01 USD" ausgewiesen
 * (Akzeptanzkriterium K4): auf einer Seite zur Kostenkontrolle darf ein tatsaechlich angefallener
 * Betrag nicht als "nichts ausgegeben" erscheinen.
 *
 * Bewusst NICHT dieselbe Funktion wie die `$0.0052`-Darstellung der Vorab-Schaetzung in
 * `components/ClassificationSection.tsx`: die Schaetzung braucht vier Nachkommastellen (ihre
 * Betraege liegen pro Bild im Zehntelcent-Bereich), die Ist-Summe hier zwei plus die
 * Waehrungskennzeichnung. Zwei bewusst verschiedene Darstellungen fuer zwei verschiedene Groessen.
 */
export function formatUsd(amountUsd: number): string {
  if (amountUsd > 0 && Math.round(amountUsd * 100) === 0) {
    return '< 0,01 USD'
  }
  return `${DECIMAL_TWO.format(amountUsd)} USD`
}

/**
 * Anteil als Prozentwert. Eingabe ist ein Bruch zwischen 0 und 1 (so liefert ihn der Server),
 * nicht bereits ein Prozentwert. Exakt 0 ohne Nachkommastelle - analog `formatBytes`.
 */
export function formatPercent(share: number): string {
  if (share === 0) {
    return '0 %'
  }
  return `${DECIMAL_ONE.format(share * 100)} %`
}

/** Ganze Zahl mit deutschem Tausenderpunkt - die Fotoanzahlen dieser Seite werden fuenfstellig. */
export function formatCount(value: number): string {
  return INTEGER.format(value)
}
