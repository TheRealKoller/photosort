import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  getDuplicateGroup,
  getDuplicateGroupIndex,
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
    /* BEIM BLÄTTERN BLEIBT DIE VORIGE GRUPPE STEHEN, bis die nächste da ist. Der Anker steht im
       Schlüssel; ohne das Vorhalten gibt es für den neuen Schlüssel keine Daten, die Seite fiele
       bei JEDEM Schritt des Durchgangs in den Ladezustand, und die Gruppennavigation verschwände
       mitsamt dem gerade gedrückten Knopf — genau der Sprung unter dem Finger, den `disabled`
       statt „fehlt" am Rand vermeidet.

       Beim ERSTEN Laden greift es nicht (es gibt keinen Vorgänger), der Skeleton-Zustand bleibt
       also erhalten. Ein Fehler ersetzt den vorgehaltenen Stand unverändert, `isError`/`isSuccess`
       laufen wie bisher — Leer- und Fehlerpfad der Seite bleiben davon unberührt. */
    placeholderData: keepPreviousData,
  })
}

/**
 * Die Auskunft für den Einstieg — unter demselben breiten `['photos', projectId, ...]`-Präfix,
 * damit die Invalidierung nach jeder Entscheidung sie mitnimmt.
 *
 * `'index'` statt einer Foto-Id an derselben Stelle: Der Einstieg kennt noch kein Mitglied, und
 * eine Zahl dort kollidierte mit dem Schlüssel einer echten Gruppe.
 *
 * `enabled` stellt der Aufrufer: An beiden Einstiegen gibt es eine Bedingung, unter der gar nicht
 * gefragt werden soll (kein erfolgreicher Lauf, falscher Filter).
 */
export function useDuplicateGroupIndexQuery(projectId: number, options: { enabled: boolean }) {
  return useQuery({
    queryKey: ['photos', projectId, 'duplicates', 'index'] as const,
    queryFn: () => getDuplicateGroupIndex(projectId),
    enabled: options.enabled,
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
