import { apiFetch } from './client'
import type {
  ClassificationEstimateOut,
  ClassificationWay,
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
 * Der EINE Ausloeser der Klassifizierung - der Server verkettet die Phasen des gewaehlten Wegs,
 * der Aufrufer kennt ihre Reihenfolge nicht.
 *
 * `scoringRunId`: Staleness-Guard bei einem zwischenzeitlichen Re-Scan/Re-Scoring (siehe
 * ScoringRunSummary.id). `mode`: der Weg dieses Laufs (Spec 0609) - er ersetzt die fruehere
 * `use_cloud`-Checkbox und hat KEINEN Vorgabewert; `mode: 'cloud'` erteilt keine Einwilligung
 * (die bleibt die Projekteinstellung) und wird ohne sie mit 403 abgewiesen. `eye` wird mit 403
 * abgewiesen, wenn der Eye-Schalter aus ist, und mit 503, wenn der Dienst nicht antwortet.
 */
export function triggerClassification(
  id: number,
  scoringRunId: number,
  mode: ClassificationWay,
): Promise<TriggerScanResponse> {
  return apiFetch<TriggerScanResponse>(`/projects/${id}/classify`, {
    method: 'POST',
    body: { scoring_run_id: scoringRunId, mode },
  })
}

// PUT statt POST, da ein Zustand gesetzt wird statt ein Job ausgeloest.
export function setCloudVisionConsent(
  id: number,
  enabled: boolean,
): Promise<CloudVisionConsentOut> {
  return apiFetch<CloudVisionConsentOut>(`/projects/${id}/cloud-vision-consent`, {
    method: 'PUT',
    body: { enabled },
  })
}

/**
 * Setzt den Richtwert des Auswahlvorschlags und liefert das Projekt samt neuem wirksamem Wert
 * zurueck. `null` setzt auf die Vorbelegung zurueck - ein `0` gibt es dafuer nicht, der Server
 * weist ihn mit `422` ab.
 *
 * Der Aufruf rechnet serverseitig den gesamten Vorschlag neu; er gehoert deshalb an das Verlassen
 * des Feldes, nicht an jeden Tastendruck.
 */
export function setSelectionTarget(id: number, target: number | null): Promise<ProjectOut> {
  return apiFetch<ProjectOut>(`/projects/${id}/selection-target`, {
    method: 'PUT',
    body: { target },
  })
}

// Die Schaetzung gilt JE WEG (`?mode=`): Cloud beide Anteile, Eye nur die
// Sehenswuerdigkeits-Erkennung (und nur mit Einwilligung), lokal keinen. Funktioniert unabhaengig
// vom Consent-Schalter (auch bei deaktiviertem Consent 200) - die Kosten sollen vor einer
// Consent-Entscheidung sichtbar sein.
export function getClassificationEstimate(
  id: number,
  mode: ClassificationWay,
): Promise<ClassificationEstimateOut> {
  return apiFetch<ClassificationEstimateOut>(
    `/projects/${id}/classify/estimate?mode=${encodeURIComponent(mode)}`,
  )
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
