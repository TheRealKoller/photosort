import { apiFetch } from './client'
import type { FeedbackDiagnosisOut, FeedbackWeightPreview } from './types'

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

/**
 * Übernimmt die abgeleiteten Gewichte als neue, global geltende Fassung.
 *
 * DER BODY TRÄGT KEINE GEWICHTE, nur den Anker auf den Ereignisstand, der angezeigt wurde. Der
 * Server rechnet den Vorschlag neu und antwortet `409`, wenn seither Korrekturen hinzugekommen
 * sind - in welchem Projekt auch immer.
 */
export function adoptFeedbackWeights(basedOnEventId: number): Promise<FeedbackWeightPreview> {
  return apiFetch<FeedbackWeightPreview>('/feedback/weights', {
    method: 'POST',
    body: { based_on_event_id: basedOnEventId },
  })
}

/**
 * Nimmt die geltende Fassung zurück - als NEUE Fassung mit den Werten ihrer Vorgängerin.
 *
 * Der Aufruf nennt die Fassung, die zurückgenommen werden soll; der Server antwortet `409`, wenn
 * sie nicht mehr die geltende ist. Ohne diesen Wächter legten zwei Aufrufe kurz hintereinander
 * erst die Rücknahme und dann deren Rücknahme an.
 */
export function revertFeedbackWeights(revertsSetId: number): Promise<FeedbackWeightPreview> {
  return apiFetch<FeedbackWeightPreview>('/feedback/weights/revert', {
    method: 'POST',
    body: { reverts_set_id: revertsSetId },
  })
}
