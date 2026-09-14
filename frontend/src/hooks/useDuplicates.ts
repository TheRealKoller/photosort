import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  getDuplicateGroup,
  setDuplicateDecision,
  setDuplicateGroupDecision,
} from '../api/duplicates'
import type { DuplicateDecision, DuplicateGroupOut } from '../api/types'

/**
 * Der Schlüssel der Gruppenabfrage — unter demselben breiten `['photos', projectId, ...]`-Präfix
 * wie Raster, Einzelbild, Entwurf und Endauswahl. Eine Bewertung, die anderswo geschrieben wird,
 * invalidiert die Gruppe damit mit.
 *
 * DAS FOTO GEHÖRT IN DEN SCHLÜSSEL: Zwei Gruppen desselben Projekts teilten sich sonst denselben
 * Eintrag, und die zweite Ansicht zeigte die Mitglieder der ersten. Der Wert ist der ANKER der
 * Gruppe (irgendein Mitglied), nicht ihre Identität — eine solche gibt es nicht.
 */
function duplicateGroupQueryKey(projectId: number, photoId: number) {
  return ['photos', projectId, 'duplicates', photoId] as const
}

export function useDuplicateGroupQuery(projectId: number, photoId: number) {
  return useQuery({
    queryKey: duplicateGroupQueryKey(projectId, photoId),
    queryFn: () => getDuplicateGroup(projectId, photoId),
  })
}

/**
 * Nach jeder Entscheidung: den zurückgelieferten Stand fortschreiben UND breit invalidieren.
 *
 * Beides zusammen, nicht eines davon. Die Fortschreibung nimmt der Ansicht das Flackern (die
 * Antwort ist bereits der vollständige neue Stand der Gruppe); die breite Invalidierung trifft
 * die Fotoliste mit Filter `suggested` und damit zugleich die Zahl am Ausschuss-Gate — ohne sie
 * zeigte die Liste die entschiedenen Aufnahmen weiter, und kein Rendering-Test sähe es.
 *
 * ANDERS ALS BEIM ALBUM-ENTWURF wird der eigene Schlüssel NICHT ausgenommen: Eine Entscheidung
 * ändert die Mitgliedschaft der Gruppe nicht, es kann also keine Kachel unter dem Finger
 * wegspringen.
 */
function applyGroup(
  queryClient: ReturnType<typeof useQueryClient>,
  projectId: number,
  photoId: number,
  written: DuplicateGroupOut,
): void {
  queryClient.setQueryData<DuplicateGroupOut>(duplicateGroupQueryKey(projectId, photoId), written)
  void queryClient.invalidateQueries({ queryKey: ['photos', projectId] })
}

/**
 * Die Entscheidung über EIN Mitglied. `photoId` des Hooks ist der Anker der Gruppe, `photoId` der
 * Mutation das tatsächlich entschiedene Foto — die beiden sind verschieden, sobald man ein
 * anderes Mitglied als das aufgerufene entscheidet.
 */
export function useDuplicateDecisionMutation(projectId: number, photoId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (variables: { photoId: number; decision: DuplicateDecision }) =>
      setDuplicateDecision(projectId, variables.photoId, variables.decision),
    onSuccess: (written) => applyGroup(queryClient, projectId, photoId, written),
  })
}

/**
 * Die gruppenweite Abkürzung — GENAU EIN Aufruf, unabhängig von der Mitgliederzahl (AK9).
 *
 * Welche Fotos betroffen sind, bestimmt der Server aus dem Stern; die Oberfläche schickt keine
 * Id-Liste. Eine Schleife über die Kacheln sähe im Ergebnis gleich aus und wäre n einzelne
 * Transaktionen — eine davon könnte scheitern und die Gruppe halb entschieden zurücklassen.
 */
export function useDuplicateGroupDecisionMutation(projectId: number, photoId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (decision: DuplicateDecision) =>
      setDuplicateGroupDecision(projectId, photoId, decision),
    onSuccess: (written) => applyGroup(queryClient, projectId, photoId, written),
  })
}
