import { useQuery } from '@tanstack/react-query'

import { getFeedbackDiagnosis } from '../api/feedback'

/**
 * Der Schlüssel trägt WEDER PROJEKT NOCH NUTZER.
 *
 * Er weicht damit bewusst von `projectStatsQueryKey` ab, der den angemeldeten Nutzer führt: Die
 * Diagnose ist in Menge und in jedem Feld nutzerunabhängig und zählt über alle Projekte. Ein
 * Segment für eines von beidem behauptete eine Trennung, die es nicht gibt, und lüde denselben
 * Stand mehrfach.
 */
export function feedbackDiagnosisQueryKey() {
  return ['feedback-diagnosis'] as const
}

/**
 * Die laufende Diagnose - eigene Abfrage neben der Projektstatistik, nicht in ihr.
 *
 * Sie rechnet über das gesamte Ereignis-Log und ist damit spürbar teurer als die Projektzahlen;
 * eingebettet zwänge sie die ganze Statistikseite in ihren Ladezustand. Wie die Statistikseite
 * ist sie eine Momentaufnahme: kein `refetchInterval`, kein erneutes Laden beim Tab-Wechsel.
 */
export function useFeedbackDiagnosisQuery() {
  return useQuery({
    queryKey: feedbackDiagnosisQueryKey(),
    queryFn: () => getFeedbackDiagnosis(),
    refetchOnWindowFocus: false,
  })
}
