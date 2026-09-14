import { apiFetch } from './client'
import type { FeedbackDiagnosisOut } from './types'

/**
 * Die laufende Diagnose der Modellfehler aus der Nacharbeit.
 *
 * OHNE PROJEKTBEZUG, und das ist keine Auslassung: Die Zahlen zählen die Korrekturen beider
 * Nutzer über alle Projekte hinweg, weil die Gewichte der Qualitätskriterien global gelten. Ein
 * Projektsegment im Pfad wäre der Weg, auf dem sie stillschweigend wieder projektweise würden.
 */
export function getFeedbackDiagnosis(): Promise<FeedbackDiagnosisOut> {
  return apiFetch<FeedbackDiagnosisOut>('/feedback/diagnosis')
}
