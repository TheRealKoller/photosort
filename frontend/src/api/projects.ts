import { apiFetch } from './client'
import type {
  ClassificationEstimateOut,
  ClassificationWay,
  FineLabelCountOut,
  ModelChoiceOut,
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
 * ScoringRunSummary.id). `mode` waehlt seit Spec 0383 nur noch "wie im Projekt eingestellt"
 * (`project`) oder "nur lokal" (`local`) und hat KEINEN Vorgabewert. Den wirksamen Weg, die
 * Modelle und die Einwilligung entscheidet der Server aus der Projektwahl: ohne Einwilligung
 * wird der wirksame Cloud-Weg mit 403 abgewiesen, ein abgeschaltetes Eye ebenso, ein nicht
 * erreichbares mit 503.
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

// Die Schaetzung gilt JE WAHL (`?mode=project|local`): `project` nimmt die im Projekt
// gespeicherte Wahl (Cloud-Kategorisierung, Eye-Kategorisierung oder Eye + Landmark mit
// Einwilligung), `local` keinen Anteil. Funktioniert unabhaengig vom Consent-Schalter (auch bei
// deaktiviertem Consent 200) - die Kosten sollen vor einer Consent-Entscheidung sichtbar sein.

/**
 * Katalog und gespeicherte Wahl des Projekts (Spec 0383) - die Quelle fuer den Abschnitt
 * "Modellwahl" in den Einstellungen und fuer die Kurzfassung an der Laufwahl.
 */
export function getModelChoice(id: number): Promise<ModelChoiceOut> {
  return apiFetch<ModelChoiceOut>(`/projects/${id}/model-choice`)
}

export interface ModelChoicePayload {
  category_method: 'cloud' | 'eye'
  category_model: string | null
  landmark_model: string | null
}

/**
 * Setzt die Wahl je Taetigkeit - alle drei Spalten in EINEM Commit. Bei einem Fehler aendert sich
 * nichts; `409` heisst "es laeuft gerade eine Klassifizierung".
 */
export function putModelChoice(id: number, payload: ModelChoicePayload): Promise<ModelChoiceOut> {
  return apiFetch<ModelChoiceOut>(`/projects/${id}/model-choice`, {
    method: 'PUT',
    body: payload,
  })
}
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
