import type {
  ExchangeKind,
  FeedbackDiagnosisOut,
  FeedbackExchangeStats,
  MotifErrorCase,
} from '../api/types'

/**
 * Die Beschriftungen der drei Motiv-Fehlerfälle - ohne Fachjargon, in der Sprache derer, die
 * korrigiert haben.
 */
export const MOTIF_ERROR_CASE_LABELS: Record<MotifErrorCase, string> = {
  too_weak: 'Zu schwach erkannt',
  missing: 'Gar nicht erkannt',
  overcalled: 'Vom Modell genannt, von uns weggenommen',
}

/**
 * Die Beschriftungen der drei Tauschklassen.
 *
 * DIE UNBESTIMMTE HAT EINEN EIGENEN NAMEN und heißt nicht „sonstige": Sie ist eine ausgewiesene
 * Klasse und kein Restposten, und die drei Zahlen stehen nirgends summiert nebeneinander.
 */
export const EXCHANGE_KIND_LABELS: Record<ExchangeKind, string> = {
  within_level: 'Innerhalb derselben Modellstufe',
  across_level: 'Über Modellstufen hinweg',
  undetermined: 'Modellstufe unbekannt',
}

/**
 * Ob überhaupt schon korrigiert wurde.
 *
 * ALLEIN AN DER ZAHL DER KORREKTUREN, nie an leeren Fehlerlisten: Die Antwort trägt alle
 * Fehlerfälle und Tauschklassen auch bei null Korrekturen. „N Korrekturen, 0 Fehler" ist eine
 * Aussage über das Modell, „noch keine Korrekturen" ist keine - und beide dürfen nicht gleich
 * aussehen.
 */
export function hasCorrections(diagnosis: FeedbackDiagnosisOut): boolean {
  return diagnosis.correction_count > 0
}

/**
 * Der Zusatz zur Qualität einer Tauschklasse, oder `null`, wenn es dazu nichts zu sagen gibt.
 *
 * Die unvergleichbaren Paare (gleicher oder fehlender eingefrorener Qualitätswert) stehen als
 * EIGENE Angabe und werden weder den vorgezogenen schlechteren noch den besseren zugeschlagen.
 * Ohne sie ließe sich ein gestiegener Anteil „schlechteres Bild vorgezogen" nicht von einem
 * gewachsenen Anteil unvergleichbarer Paare unterscheiden.
 */
export function exchangeQualityNote(stats: FeedbackExchangeStats): string | null {
  if (stats.count === 0) {
    return null
  }
  const parts: string[] = []
  if (stats.preferred_lower_rated_count > 0) {
    parts.push(`${stats.preferred_lower_rated_count}× ein schlechter bewertetes Bild vorgezogen`)
  }
  if (stats.quality_incomparable_count > 0) {
    parts.push(`${stats.quality_incomparable_count}× ohne vergleichbare Bewertung`)
  }
  return parts.length === 0 ? null : `davon ${parts.join(', ')}`
}
