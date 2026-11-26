import { apiFetch } from './client'
import type {
  AusschussGateConfirmedOut,
  ClassificationEstimateOut,
  ClassificationWay,
  CloudVisionConsentOut,
  CreateProjectPayload,
  FineLabelCountOut,
  ModelChoiceOut,
  ModelChoicePayload,
  ProjectOut,
  ProjectStatsOut,
  TriggerQueuedOut,
} from './types'

export function listProjects(): Promise<ProjectOut[]> {
  return apiFetch('/projects')
}

export function createProject(payload: CreateProjectPayload): Promise<ProjectOut> {
  return apiFetch('/projects', { method: 'POST', body: payload })
}

export function getProject(id: number): Promise<ProjectOut> {
  return apiFetch('/projects/{project_id}', { pathParams: { project_id: id } })
}

/**
 * Loescht ein Projekt und alle PhotoSort-Daten daran. Die Original-Fotos auf OpenCloud bleiben
 * unangetastet.
 *
 * `confirmName` ist der vom Nutzer eingetippte Projektname. Der Server prueft ihn ein zweites Mal
 * (`400` bei Abweichung) - eine rein clientseitige Bestaetigung waere gegen direkte API-Nutzung
 * wirkungslos.
 */
export function deleteProject(id: number, confirmName: string): Promise<void> {
  return apiFetch('/projects/{project_id}', {
    method: 'DELETE',
    pathParams: { project_id: id },
    body: { confirm_name: confirmName },
  })
}

export function triggerScan(id: number): Promise<TriggerQueuedOut> {
  return apiFetch('/projects/{project_id}/scan', {
    method: 'POST',
    pathParams: { project_id: id },
  })
}

export function triggerScore(id: number): Promise<TriggerQueuedOut> {
  return apiFetch('/projects/{project_id}/score', {
    method: 'POST',
    pathParams: { project_id: id },
  })
}

// Ausschuss-Gate - synchron (kein Job-Trigger, kein 202), setzt gate_confirmed_at direkt.
export function confirmAusschussGate(id: number): Promise<AusschussGateConfirmedOut> {
  return apiFetch('/projects/{project_id}/confirm-ausschuss-gate', {
    method: 'POST',
    pathParams: { project_id: id },
  })
}

/**
 * Der EINE Ausloeser der Klassifizierung - der Server verkettet die Phasen des gewaehlten Wegs,
 * der Aufrufer kennt ihre Reihenfolge nicht.
 *
 * `scoringRunId`: Staleness-Guard bei einem zwischenzeitlichen Re-Scan/Re-Scoring. `mode` waehlt
 * "wie im Projekt eingestellt" (`project`) oder "nur lokal" (`local`) und hat KEINEN Vorgabewert.
 */
export function triggerClassification(
  id: number,
  scoringRunId: number,
  mode: ClassificationWay,
): Promise<TriggerQueuedOut> {
  return apiFetch('/projects/{project_id}/classify', {
    method: 'POST',
    pathParams: { project_id: id },
    body: { scoring_run_id: scoringRunId, mode },
  })
}

// PUT statt POST, da ein Zustand gesetzt wird statt ein Job ausgeloest.
export function setCloudVisionConsent(
  id: number,
  enabled: boolean,
): Promise<CloudVisionConsentOut> {
  return apiFetch('/projects/{project_id}/cloud-vision-consent', {
    method: 'PUT',
    pathParams: { project_id: id },
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
  return apiFetch('/projects/{project_id}/selection-target', {
    method: 'PUT',
    pathParams: { project_id: id },
    body: { target },
  })
}

/**
 * Katalog und gespeicherte Wahl des Projekts - die Quelle fuer den Abschnitt
 * "Modellwahl" in den Einstellungen und fuer die Kurzfassung an der Laufwahl.
 */
export function getModelChoice(id: number): Promise<ModelChoiceOut> {
  return apiFetch('/projects/{project_id}/model-choice', { pathParams: { project_id: id } })
}

/**
 * Setzt die Wahl je Taetigkeit - alle drei Spalten in EINEM Commit. Bei einem Fehler aendert sich
 * nichts; `409` heisst "es laeuft gerade eine Klassifizierung".
 */
export function putModelChoice(id: number, payload: ModelChoicePayload): Promise<ModelChoiceOut> {
  return apiFetch('/projects/{project_id}/model-choice', {
    method: 'PUT',
    pathParams: { project_id: id },
    body: payload,
  })
}

// Die Schaetzung gilt JE WAHL (`?mode=project|local`): `project` nimmt die im Projekt gespeicherte
// Wahl, `local` keinen Anteil. Funktioniert unabhaengig vom Consent-Schalter (auch bei
// deaktiviertem Consent 200) - die Kosten sollen vor einer Consent-Entscheidung sichtbar sein.
export function getClassificationEstimate(
  id: number,
  mode: ClassificationWay,
): Promise<ClassificationEstimateOut> {
  return apiFetch('/projects/{project_id}/classify/estimate', {
    pathParams: { project_id: id },
    query: { mode },
  })
}

/**
 * Haeufigste Feinlabels dieses Projekts - absteigend nach `photo_count`, Tie-Break `canonical_key`
 * aufsteigend, bereits vom Server sortiert. Die Reihenfolge wird im Frontend uebernommen, nicht neu
 * sortiert.
 */
export function listFineLabels(id: number): Promise<FineLabelCountOut[]> {
  return apiFetch('/projects/{project_id}/fine-labels', { pathParams: { project_id: id } })
}

/**
 * Momentaufnahme des Projektzustands - Umfang, Speicher, Kategorien, Ist-Kosten,
 * Bearbeitungs-/Bewertungsstand, Diagnose. Als Projekt-Unterressource hier gefuehrt, obwohl sie
 * backend-seitig aus einem eigenen Router kommt: der Schnitt der Frontend-API-Module folgt der
 * Ressource, nicht dem Server-Modul.
 */
export function getProjectStats(id: number): Promise<ProjectStatsOut> {
  return apiFetch('/projects/{project_id}/stats', { pathParams: { project_id: id } })
}
