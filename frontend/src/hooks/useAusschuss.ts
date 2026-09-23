import { useInfiniteQuery, useQuery } from '@tanstack/react-query'

import { listAusschuss } from '../api/ausschuss'
import type { AusschussOut } from '../api/types'

/**
 * Seitengröße der Ausschuss-Übersicht — dieselbe Zahl wie in der Fotoliste und als Vorgabe des
 * Endpunkts. Sie steht hier EINMAL: Ein zweiter Wert an der Aufrufstelle wäre eine zweite Fassung
 * derselben Seitengröße, und die Grenzen des Servers (`ge=1, le=200`) sind nicht der Ort, an dem
 * eine Oberfläche ihre Seitengröße erfährt.
 */
export const AUSSCHUSS_PAGE_SIZE = 60

/**
 * Der Schlüssel der Übersicht — unter demselben breiten `['photos', projectId, ...]`-Präfix wie
 * Raster, Einzelbild, Entwurf und Gruppenabfrage. Eine Entscheidung, die anderswo geschrieben
 * wird, invalidiert den Ausschuss-Bestand damit mit.
 *
 * `'liste'` als eigenes Segment, NICHT die nackte Projekt-Id: Die Detailabfrage liegt darunter
 * (`…, 'photo', <id>`), und ein Eintrag an derselben Stelle ließe eine Detailabfrage den
 * Seitenstapel der Übersicht als ihren Eintrag lesen — die beiden haben verschiedene Formen.
 */
function ausschussQueryKey(projectId: number) {
  return ['photos', projectId, 'ausschuss', 'liste'] as const
}

/**
 * DIE AUFNAHME GEHÖRT IN DEN SCHLÜSSEL: Zwei Deep-Links auf zwei Aufnahmen teilten sich sonst
 * einen Eintrag, und die zweite Ansicht zeigte die erste Aufnahme.
 */
function ausschussEntryQueryKey(projectId: number, photoId: number) {
  return ['photos', projectId, 'ausschuss', 'photo', photoId] as const
}

/**
 * Der Ausschuss-Bestand, seitenweise.
 *
 * `enabled` stellt der Aufrufer: Ohne erfolgreichen Erkennungslauf gibt es keine Vorschläge und
 * damit keinen Bestand — eine Anfrage je Schrittaufruf beantwortete nichts.
 *
 * Der nächste Offset ist die Zahl der bereits GELADENEN Einträge und `total` die Größe des ganzen
 * Bestands — dieselbe Ableitung wie in der Fotoliste, nicht die Seitengröße.
 */
export function useAusschussQuery(projectId: number, options: { enabled: boolean }) {
  return useInfiniteQuery({
    queryKey: ausschussQueryKey(projectId),
    queryFn: ({ pageParam }: { pageParam: number }) =>
      listAusschuss(projectId, { limit: AUSSCHUSS_PAGE_SIZE, offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (lastPage: AusschussOut, allPages: AusschussOut[]) => {
      const loaded = allPages.reduce((sum, page) => sum + page.items.length, 0)
      return loaded < lastPage.total ? loaded : undefined
    },
    enabled: options.enabled,
  })
}

/**
 * GENAU der Eintrag der Detailansicht, über den `photo_id`-Filter des Endpunkts.
 *
 * Ausdrücklich NICHT aus der geladenen Seite gesucht: Der Aufruf steht als Deep-Link `?photo=<id>`
 * im Browserverlauf und kann auf eine Aufnahme zeigen, die nicht in den geladenen Seiten liegt —
 * oder gar nicht mehr im Bestand ist. Beides ist ein regulärer Zustand mit definierter Antwort,
 * und keine davon ist ein Fehler.
 *
 * Der Aufrufer setzt das Ergebnis zusammen: Die Antwort trägt `items` als Liste, weil es dieselbe
 * Antwortform wie die Übersicht ist.
 */
export function useAusschussEntryQuery(projectId: number, photoId: number) {
  return useQuery({
    queryKey: ausschussEntryQueryKey(projectId, photoId),
    queryFn: () => listAusschuss(projectId, { limit: AUSSCHUSS_PAGE_SIZE, offset: 0, photoId }),
  })
}
