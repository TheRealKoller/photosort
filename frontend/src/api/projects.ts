import { apiFetch } from './client'
import type { ProjectOut } from './types'

export interface CreateProjectPayload {
  name: string
  opencloud_path: string
}

export interface TriggerScanResponse {
  status: string
}

export function listProjects(): Promise<ProjectOut[]> {
  return apiFetch<ProjectOut[]>('/projects')
}

export function createProject(payload: CreateProjectPayload): Promise<ProjectOut> {
  return apiFetch<ProjectOut>('/projects', { method: 'POST', body: payload })
}

export function getProject(id: number): Promise<ProjectOut> {
  return apiFetch<ProjectOut>(`/projects/${id}`)
}

export function triggerScan(id: number): Promise<TriggerScanResponse> {
  return apiFetch<TriggerScanResponse>(`/projects/${id}/scan`, { method: 'POST' })
}

export function triggerScore(id: number): Promise<TriggerScanResponse> {
  return apiFetch<TriggerScanResponse>(`/projects/${id}/score`, { method: 'POST' })
}

// Ausschuss-Gate (specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md) -
// synchron (kein Job-Trigger, kein 202), setzt gate_confirmed_at direkt.
export function confirmAusschussGate(id: number): Promise<TriggerScanResponse> {
  return apiFetch<TriggerScanResponse>(`/projects/${id}/confirm-ausschuss-gate`, {
    method: 'POST',
  })
}

// Ersetzt triggerSelectTop (specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md)
// - kein top_n_per_cluster-Parameter mehr, stattdessen scoring_run_id (Staleness-Guard bei einem
// zwischenzeitlichen Re-Scan/Re-Scoring, siehe ScoringRunSummary.id).
export function triggerScoreCriteria(
  id: number,
  scoringRunId: number
): Promise<TriggerScanResponse> {
  return apiFetch<TriggerScanResponse>(`/projects/${id}/score-criteria`, {
    method: 'POST',
    body: { scoring_run_id: scoringRunId },
  })
}
