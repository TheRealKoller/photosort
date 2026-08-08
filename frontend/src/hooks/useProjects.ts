import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createProject,
  getProject,
  listProjects,
  triggerScan,
  triggerScore,
  triggerSelectTop,
  type CreateProjectPayload,
} from '../api/projects'
import type { ProjectOut } from '../api/types'

export const POLL_INTERVAL_MS = 2000

export function useProjectsQuery() {
  return useQuery({ queryKey: ['projects'], queryFn: listProjects })
}

/**
 * Pollt, solange der letzte Scan, der letzte Scoring-Lauf ODER der letzte Top-Auswahl-Lauf laeuft
 * (`status === "running"`), und stoppt automatisch, sobald alle fertig sind - siehe
 * specs/features/0005-minimal-project-frontend.md, decisions/0004-frontend-app-shell.md,
 * specs/features/0003-automatic-best-photo-selection.md und
 * specs/features/0024-top-photo-selection-category-mix.md (dritte Anwendung desselben
 * granularen Live-Fortschritt-Polling-Musters).
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
        data?.last_top_selection_run?.status === 'running'
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

export function useTriggerSelectTopMutation(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (topNPerCluster: number) => triggerSelectTop(id, topNPerCluster),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['project', id] })
    },
  })
}
