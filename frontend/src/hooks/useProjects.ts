import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  confirmAusschussGate,
  createProject,
  getClassifyCategoriesRemoteEstimate,
  getProject,
  listProjects,
  setCloudVisionConsent,
  triggerClassifyCategoriesRemote,
  triggerScan,
  triggerScore,
  triggerScoreCriteria,
  type CreateProjectPayload,
} from '../api/projects'
import type { ProjectOut } from '../api/types'

export const POLL_INTERVAL_MS = 2000

export function useProjectsQuery() {
  return useQuery({ queryKey: ['projects'], queryFn: listProjects })
}

/**
 * Pollt, solange der letzte Scan, der letzte Scoring-Lauf ODER der letzte Kriterien-Scoring-Lauf
 * laeuft (`status === "running"`), und stoppt automatisch, sobald alle fertig sind - siehe
 * specs/features/0005-minimal-project-frontend.md, decisions/0004-frontend-app-shell.md,
 * specs/features/0003-automatic-best-photo-selection.md und
 * specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md (dritte Anwendung
 * desselben granularen Live-Fortschritt-Polling-Musters, ersetzt last_top_selection_run).
 */
export function useProjectQuery(id: number) {
  return useQuery({
    queryKey: ['project', id],
    queryFn: () => getProject(id),
    refetchInterval: (query) => {
      const data = query.state.data as ProjectOut | undefined
      const isRunning =
        data?.last_scan?.status === 'running' ||
        data?.last_scoring_run?.status === 'running' ||
        data?.last_criterion_scoring_run?.status === 'running' ||
        data?.last_remote_category_classification_run?.status === 'running'
      return isRunning ? POLL_INTERVAL_MS : false
    },
  })
}

export function useCreateProjectMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: CreateProjectPayload) => createProject(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}

export function useTriggerScanMutation(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => triggerScan(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['project', id] })
    },
  })
}

export function useTriggerScoreMutation(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => triggerScore(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['project', id] })
    },
  })
}

export function useConfirmAusschussGateMutation(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => confirmAusschussGate(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['project', id] })
    },
  })
}

export function useTriggerScoreCriteriaMutation(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (scoringRunId: number) => triggerScoreCriteria(id, scoringRunId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['project', id] })
    },
  })
}

// specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md
export function useSetCloudVisionConsentMutation(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (enabled: boolean) => setCloudVisionConsent(id, enabled),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['project', id] })
    },
  })
}

function classifyCategoriesRemoteEstimateQueryKey(id: number) {
  return ['classify-categories-remote-estimate', id] as const
}

// specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, UI/UX-Abschnitt:
// "Eager-Schätzung" - beim Seitenaufruf geladen (nicht erst beim Oeffnen des Bestaetigungsdialogs),
// analog dem bestehenden Eager-Zaehler-Muster. Funktioniert unabhaengig vom Consent-Schalter.
export function useClassifyCategoriesRemoteEstimateQuery(id: number) {
  return useQuery({
    queryKey: classifyCategoriesRemoteEstimateQueryKey(id),
    queryFn: () => getClassifyCategoriesRemoteEstimate(id),
  })
}

export function useTriggerClassifyCategoriesRemoteMutation(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => triggerClassifyCategoriesRemote(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['project', id] })
      // Die Schaetzung selbst aendert sich durch das Ausloesen nicht sofort (der Job laeuft erst
      // im Hintergrund), aber ein erneuter Abruf nach Abschluss (ueber das Polling von
      // useProjectQuery ausgeloeste Neu-Rendering) soll wieder den aktuellen Kandidatenstand
      // zeigen - Invalidierung hier ist die einfachste Variante, ohne einen eigenen Polling-Pfad
      // fuer die Schaetzung selbst einzufuehren.
      void queryClient.invalidateQueries({ queryKey: classifyCategoriesRemoteEstimateQueryKey(id) })
    },
  })
}
