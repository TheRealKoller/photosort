import { apiFetch } from './client'
import type { ClassifyCategoriesRemoteEstimateOut, FineLabelCountOut, ProjectOut } from './types'

export interface CloudVisionConsentOut {
  cloud_vision_detection_enabled: boolean
  cloud_vision_consent_at: string | null
}

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

// specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md: PUT statt POST, da ein
// Zustand gesetzt wird statt ein Job ausgeloest (siehe backend api/projects.py-Kommentar).
export function setCloudVisionConsent(
  id: number,
  enabled: boolean
): Promise<CloudVisionConsentOut> {
  return apiFetch<CloudVisionConsentOut>(`/projects/${id}/cloud-vision-consent`, {
    method: 'PUT',
    body: { enabled },
  })
}

// specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, ADR 0032 Punkt
// 6.1: funktioniert unabhaengig vom Consent-Schalter (auch bei deaktiviertem Consent 200).
export function getClassifyCategoriesRemoteEstimate(
  id: number
): Promise<ClassifyCategoriesRemoteEstimateOut> {
  return apiFetch<ClassifyCategoriesRemoteEstimateOut>(
    `/projects/${id}/classify-categories-remote/estimate`
  )
}

export function triggerClassifyCategoriesRemote(id: number): Promise<TriggerScanResponse> {
  return apiFetch<TriggerScanResponse>(`/projects/${id}/classify-categories-remote`, {
    method: 'POST',
  })
}

/**
 * Haeufigste Feinlabels dieses Projekts (specs/features/0289-feste-kategorien.md) - absteigend
 * nach `photo_count`, Tie-Break `canonical_key` aufsteigend, bereits vom Server sortiert. Die
 * Reihenfolge wird im Frontend uebernommen, nicht neu sortiert.
 *
 * Die Zaehlung ist projekt-skopiert (das Vokabular selbst ist projektuebergreifend) - ein leeres
 * Projekt liefert eine leere Liste mit `200`.
 */
export function listFineLabels(id: number): Promise<FineLabelCountOut[]> {
  return apiFetch<FineLabelCountOut[]>(`/projects/${id}/fine-labels`)
}
