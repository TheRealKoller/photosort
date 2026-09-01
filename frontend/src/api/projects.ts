import { apiFetch } from './client'
import type { ClassificationEstimateOut, FineLabelCountOut, ProjectOut } from './types'

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

/**
 * Der EINE Ausloeser der Klassifizierung (specs/features/0296-klassifizierung-ein-ausloeser-cloud-
 * checkbox.md) - ersetzt triggerScoreCriteria UND triggerClassifyCategoriesRemote. Der Server
 * verkettet beide Phasen; die frueher noetige Reihenfolge-Kenntnis entfaellt.
 *
 * `scoringRunId`: Staleness-Guard bei einem zwischenzeitlichen Re-Scan/Re-Scoring (siehe
 * ScoringRunSummary.id). `useCloud`: laufbezogene Cloud-Freigabe - erteilt KEINE Einwilligung
 * (die bleibt die Projekteinstellung), sondern entscheidet nur ueber die Nutzung der bereits
 * erteilten fuer genau diesen Lauf. Ohne Einwilligung antwortet der Server mit 403.
 */
export function triggerClassification(
  id: number,
  scoringRunId: number,
  useCloud: boolean
): Promise<TriggerScanResponse> {
  return apiFetch<TriggerScanResponse>(`/projects/${id}/classify`, {
    method: 'POST',
    body: { scoring_run_id: scoringRunId, use_cloud: useCloud },
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
// 6.1, fortgeschrieben von specs/features/0296: die Schaetzung deckt jetzt beide Cloud-Anteile ab.
// Funktioniert weiterhin unabhaengig vom Consent-Schalter (auch bei deaktiviertem Consent 200) -
// die Kosten sollen vor einer Consent-Entscheidung sichtbar sein.
export function getClassificationEstimate(id: number): Promise<ClassificationEstimateOut> {
  return apiFetch<ClassificationEstimateOut>(`/projects/${id}/classify/estimate`)
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
