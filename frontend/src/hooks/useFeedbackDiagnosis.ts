import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { adoptFeedbackWeights, getFeedbackDiagnosis, revertFeedbackWeights } from '../api/feedback'

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

/**
 * Die Übernahme der abgeleiteten Gewichte.
 *
 * SIE SCHREIBT NICHTS IN DEN ZWISCHENSPEICHER FORT, sondern lädt die Diagnose neu. Der Grund ist
 * nicht Bequemlichkeit: Der Server rechnet den Vorschlag selbst und antwortet `409`, wenn seither
 * Korrekturen hinzugekommen sind - ein optimistisch fortgeschriebener Stand zeigte im
 * Konfliktfall eine Fassung, die es nicht gibt. Nach dem Erfolg ist zudem alles andere als der
 * Vorschlag betroffen: Das geltende Gewicht ist ein anderes, die Abweichung wieder null, die
 * Rücknahme möglich.
 *
 * Die Rangzeilen bleiben unberührt - die Änderung wirkt erst beim nächsten Durchlauf. Es wird
 * deshalb ausdrücklich KEIN Fotoschlüssel invalidiert.
 */
export function useAdoptFeedbackWeightsMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (basedOnEventId: number) => adoptFeedbackWeights(basedOnEventId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: feedbackDiagnosisQueryKey() })
    },
  })
}

/** Die Rücknahme der geltenden Fassung - dieselbe Begründung wie bei der Übernahme. */
export function useRevertFeedbackWeightsMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (revertsSetId: number) => revertFeedbackWeights(revertsSetId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: feedbackDiagnosisQueryKey() })
    },
  })
}
