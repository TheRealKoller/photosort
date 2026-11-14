import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getExportPreview, getExportRun, triggerExport } from '../api/export'
import { operationsQueryKey } from '../api/operations'
import type { ExportRunSummary } from '../api/types'
import { useProjectQuery } from './useProjects'
import { useTriggerConfirmation } from './useTriggerConfirmation'

/**
 * Der Export der Endauswahl: die drei Antworten der Story an derselben Stelle.
 *
 * - Anzahl VORHER: `getExportPreview` (server-autoritativ, exakt die Menge, die der Export nimmt).
 * - Laufzustand WAEHREND: `ProjectOut.last_export_run` ueber `useProjectQuery` (pollt bei
 *   `status === "running"`, Muster `last_scan`); `useTriggerConfirmation` ueberbrueckt das Fenster
 *   zwischen 202 und erstem bestaetigendem Poll.
 * - Bestaetigung DANACH: der letzte Lauf plus `getExportRun` fuer die Fehlerliste je Foto.
 */
export function useExport(projectId: number) {
  const queryClient = useQueryClient()

  const project = useProjectQuery(projectId)

  const preview = useQuery({
    queryKey: ['export-preview', projectId],
    queryFn: () => getExportPreview(projectId),
  })

  const lastRun: ExportRunSummary | null = project.data?.last_export_run ?? null
  const runId = lastRun?.id

  // VOR der Mutation: `setAwaiting` muss im `onError` der Mutation erreichbar sein. Ohne dieses
  // Zuruecksetzen bliebe `awaiting` nach einem fehlgeschlagenen Trigger dauerhaft `true` - der
  // Ausloeser waere permanent gesperrt (Muster ScanStepPage).
  const [awaiting, setAwaiting] = useTriggerConfirmation(
    lastRun?.status ?? null,
    lastRun?.started_at ?? null,
    () => project.refetch(),
  )

  const trigger = useMutation({
    mutationFn: () => triggerExport(projectId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['project', projectId] })
      // Spec 0641: Der angenommene Vorgang steht sofort in der Projektleiste.
      void queryClient.invalidateQueries({ queryKey: operationsQueryKey(projectId) })
    },
    onError: () => setAwaiting(false),
  })

  const runDetail = useQuery({
    queryKey: ['export-run', projectId, runId],
    queryFn: () => getExportRun(projectId, runId!),
    // Der Detailendpunkt liefert die Fehlerliste erst DANACH - waehrend des Laufs und solange er
    // wartet gibt es keine. `cancelled` ist beendet und wird geladen (letzter Stand).
    enabled:
      runId !== undefined &&
      lastRun !== null &&
      lastRun.status !== 'running' &&
      lastRun.status !== 'queued',
  })

  return { project, preview, trigger, lastRun, runDetail, awaiting, setAwaiting }
}
