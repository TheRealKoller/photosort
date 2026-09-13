import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getAlbumSelection, setAlbumDecision } from '../api/albumSelection'
import type { AlbumSelectionOut } from '../api/types'
import { applyAlbumDecision } from '../utils/albumSelection'

/**
 * Das Segment des Endauswahl-Schlüssels. Er liegt unter demselben breiten
 * `['photos', projectId, ...]`-Präfix wie Raster, Einzelbild und Entwurf - eine Bewertung, die
 * anderswo geschrieben wird, invalidiert ihn damit mit, und die Endauswahl zeigt danach den
 * neuen Stand beider Entwürfe.
 */
const SELECTION_QUERY_SEGMENT = 'selection'

function selectionQueryKey(projectId: number) {
  return ['photos', projectId, SELECTION_QUERY_SEGMENT] as const
}

/**
 * Die gemeinsame Endauswahl eines Projekts - EINE Abfrage für beide Sichten.
 *
 * KEIN Sichtparameter im Schlüssel: Arbeits- und Ergebnissicht sind lokale Filter über derselben
 * Antwort, und der Umschalter lädt nichts nach.
 */
export function useAlbumSelectionQuery(projectId: number) {
  return useQuery({
    queryKey: selectionQueryKey(projectId),
    queryFn: () => getAlbumSelection(projectId),
  })
}

/**
 * Die gemeinsame Entscheidung über ein Bild - sofort wirksam, ohne Bestätigungsschritt.
 *
 * Sie schreibt den betroffenen Eintrag im geladenen Stand FORT und nimmt den eigenen Schlüssel von
 * der Invalidierung aus (Muster `useDraftDecisionMutation`, ADR 0099 Punkt 6). Daraus folgt
 * beides zugleich: Das entschiedene Bild verlässt die Arbeitssicht sofort, und die Ergebnissicht
 * ordnet sich dabei nicht neu. Träfe die breite Invalidierung den eigenen Schlüssel mit, spränge
 * die gerade gedrückte Kachel unter dem Finger an eine andere Stelle - und der nächste Druck
 * landete auf einem anderen Bild.
 *
 * Fortgeschrieben wird ausschließlich die SERVERANTWORT, nie der lokal beabsichtigte Wert
 * (Auflage S5).
 */
export function useAlbumDecisionMutation(projectId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ photoId, included }: { photoId: number; included: boolean }) =>
      setAlbumDecision(photoId, included),
    onSuccess: (written) => {
      queryClient.setQueryData<AlbumSelectionOut>(selectionQueryKey(projectId), (current) =>
        current === undefined ? current : applyAlbumDecision(current, written),
      )
      void queryClient.invalidateQueries({
        queryKey: ['photos', projectId],
        predicate: (query) => query.queryKey[2] !== SELECTION_QUERY_SEGMENT,
      })
    },
  })
}
