import { apiFetch } from './client'
import type {
  ClassificationEstimateOut,
  FineLabelCountOut,
  ProjectOut,
  ProjectStatsOut,
} from './types'

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

/**
 * Loescht ein Projekt und alle PhotoSort-Daten daran. Die Original-Fotos auf OpenCloud bleiben
 * unangetastet.
 *
 * `confirmName` ist der vom Nutzer eingetippte Projektname. Der Server prueft ihn ein zweites Mal
 * (`400` bei Abweichung) - eine rein clientseitige Bestaetigung waere gegen direkte API-Nutzung
 * wirkungslos. `apiFetch` traegt bei jeder Methode einen JSON-Body und behandelt `204` bereits.
 */
export function deleteProject(id: number, confirmName: string): Promise<void> {
  return apiFetch<void>(`/projects/${id}`, {
    method: 'DELETE',
    body: { confirm_name: confirmName },
  })
}

export function triggerScan(id: number): Promise<TriggerScanResponse> {
  return apiFetch<TriggerScanResponse>(`/projects/${id}/scan`, { method: 'POST' })
}

export function triggerScore(id: number): Promise<TriggerScanResponse> {
  return apiFetch<TriggerScanResponse>(`/projects/${id}/score`, { method: 'POST' })
}

// Ausschuss-Gate - synchron (kein Job-Trigger, kein 202), setzt gate_confirmed_at direkt.
export function confirmAusschussGate(id: number): Promise<TriggerScanResponse> {
  return apiFetch<TriggerScanResponse>(`/projects/${id}/confirm-ausschuss-gate`, {
    method: 'POST',
  })
}

/**
 * Der EINE Ausloeser der Klassifizierung - ersetzt triggerScoreCriteria UND
 * triggerClassifyCategoriesRemote. Der Server verkettet beide Phasen; die frueher noetige
 * Reihenfolge-Kenntnis entfaellt.
 *
 * `scoringRunId`: Staleness-Guard bei einem zwischenzeitlichen Re-Scan/Re-Scoring (siehe
 * ScoringRunSummary.id). `useCloud`: laufbezogene Cloud-Freigabe - erteilt KEINE Einwilligung
 * (die bleibt die Projekteinstellung), sondern entscheidet nur ueber die Nutzung der bereits
 * erteilten fuer genau diesen Lauf. Ohne Einwilligung antwortet der Server mit 403.
 */
export function triggerClassification(
  id: number,
  scoringRunId: number,
  useCloud: boolean,
): Promise<TriggerScanResponse> {
  return apiFetch<TriggerScanResponse>(`/projects/${id}/classify`, {
    method: 'POST',
    body: { scoring_run_id: scoringRunId, use_cloud: useCloud },
  })
}

// PUT statt POST, da ein Zustand gesetzt wird statt ein Job ausgeloest (siehe backend
// api/projects.py-Kommentar).
export function setCloudVisionConsent(
  id: number,
  enabled: boolean,
): Promise<CloudVisionConsentOut> {
  return apiFetch<CloudVisionConsentOut>(`/projects/${id}/cloud-vision-consent`, {
    method: 'PUT',
    body: { enabled },
  })
}

// Die Schaetzung deckt beide Cloud-Anteile ab. Funktioniert unabhaengig vom Consent-Schalter (auch
// bei deaktiviertem Consent 200) - die Kosten sollen vor einer Consent-Entscheidung sichtbar sein.
export function getClassificationEstimate(id: number): Promise<ClassificationEstimateOut> {
  return apiFetch<ClassificationEstimateOut>(`/projects/${id}/classify/estimate`)
}

/**
 * Haeufigste Feinlabels dieses Projekts - absteigend nach `photo_count`, Tie-Break `canonical_key`
 * aufsteigend, bereits vom Server sortiert. Die Reihenfolge wird im Frontend uebernommen, nicht neu
 * sortiert.
 *
 * Die Zaehlung ist projekt-skopiert (das Vokabular selbst ist projektuebergreifend) - ein leeres
 * Projekt liefert eine leere Liste mit `200`.
 */
export function listFineLabels(id: number): Promise<FineLabelCountOut[]> {
  return apiFetch<FineLabelCountOut[]>(`/projects/${id}/fine-labels`)
}

/**
 * Momentaufnahme des Projektzustands - Umfang, Speicher, Kategorien, Ist-Kosten,
 * Bearbeitungs-/Bewertungsstand, Diagnose.
 *
 * Als Projekt-Unterressource hier gefuehrt (konsistent mit `listFineLabels`/
 * `getClassificationEstimate`), obwohl sie backend-seitig aus einem eigenen Router kommt: der
 * Schnitt der Frontend-API-Module folgt der Ressource, nicht dem Server-Modul.
 */
export function getProjectStats(id: number): Promise<ProjectStatsOut> {
  return apiFetch<ProjectStatsOut>(`/projects/${id}/stats`)
}
