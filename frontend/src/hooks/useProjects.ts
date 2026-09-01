import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  confirmAusschussGate,
  createProject,
  getClassificationEstimate,
  getProject,
  listFineLabels,
  listProjects,
  setCloudVisionConsent,
  triggerClassification,
  triggerScan,
  triggerScore,
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

/**
 * Der EINE Ausloeser der Klassifizierung (specs/features/0296-klassifizierung-ein-ausloeser-cloud-
 * checkbox.md) - ersetzt useTriggerScoreCriteriaMutation UND
 * useTriggerClassifyCategoriesRemoteMutation.
 *
 * Invalidiert neben dem Projekt auch Schaetzung und Feinlabel-Liste: beide haengen am Ergebnis der
 * Remote-Phase, die dieser Lauf mit ausfuehren kann.
 */
export function useTriggerClassificationMutation(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ scoringRunId, useCloud }: { scoringRunId: number; useCloud: boolean }) =>
      triggerClassification(id, scoringRunId, useCloud),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['project', id] })
      // Die Schaetzung aendert sich durch das Ausloesen nicht sofort (der Job laeuft erst im
      // Hintergrund), aber ein erneuter Abruf nach Abschluss soll wieder den aktuellen
      // Kandidatenstand zeigen - Invalidierung hier ist die einfachste Variante, ohne einen
      // eigenen Polling-Pfad fuer die Schaetzung selbst einzufuehren.
      void queryClient.invalidateQueries({ queryKey: classificationEstimateQueryKey(id) })
      // Ein Lauf mit Cloud-Nutzung ist die EINZIGE Quelle neuer Feinlabels - die
      // Haeufigkeitsliste muss danach neu geladen werden, sonst zeigt sie dauerhaft den Stand
      // vor dem Lauf.
      void queryClient.invalidateQueries({ queryKey: fineLabelsQueryKey(id) })
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

function classificationEstimateQueryKey(id: number) {
  return ['classification-estimate', id] as const
}

// specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, UI/UX-Abschnitt:
// "Eager-Schätzung" - beim Seitenaufruf geladen, analog dem bestehenden Eager-Zaehler-Muster.
// Funktioniert unabhaengig vom Consent-Schalter. Seit specs/features/0296-klassifizierung-ein-
// ausloeser-cloud-checkbox.md steht sie nicht mehr in einem Bestaetigungsdialog, sondern dauerhaft
// an der Cloud-Checkbox - das Eager-Laden ist damit nicht mehr nur eine Optimierung, sondern
// Voraussetzung dafuer, dass die Kosten VOR dem Start sichtbar sind.
export function useClassificationEstimateQuery(id: number) {
  return useQuery({
    queryKey: classificationEstimateQueryKey(id),
    queryFn: () => getClassificationEstimate(id),
  })
}

function fineLabelsQueryKey(id: number) {
  return ['fine-labels', id] as const
}

/**
 * Haeufigste Feinlabels des Projekts (specs/features/0289-feste-kategorien.md, UI/UX-Abschnitt) -
 * bewusst eine eigene Query statt eines Feldes an `ProjectOut`: die Liste haengt am Ergebnis des
 * Remote-Laufs, nicht am Projektstammsatz, und wuerde sonst bei jedem `useProjectQuery`-Poll
 * (POLL_INTERVAL_MS) mitgeladen.
 */
export function useFineLabelsQuery(id: number) {
  return useQuery({
    queryKey: fineLabelsQueryKey(id),
    queryFn: () => listFineLabels(id),
  })
}

