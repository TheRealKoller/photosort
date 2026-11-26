import { apiFetch } from './client'
import type { ExportPreviewOut, ExportRunDetailOut, TriggerQueuedOut } from './types'

/**
 * Die Anzahl der Endauswahl-Fotos vor dem Auslösen - server-autoritativ: exakt die Menge, die der
 * Export gleich nimmt (`backend final_selection.py::included_photos`). Das Frontend zählt die
 * Anzahl nie selbst aus der geladenen Endauswahl-Antwort.
 */
export function getExportPreview(projectId: number): Promise<ExportPreviewOut> {
  return apiFetch('/projects/{project_id}/export-preview', {
    pathParams: { project_id: projectId },
  })
}

/**
 * Der Auslöser. Antwortet 202; der Lauf selbst ist ein Hintergrund-Job, dessen Zustand über
 * `ProjectOut.last_export_run` gepollt wird. Kein Body: es wird immer die ganze Endauswahl
 * exportiert, nie eine Auswahl einzelner Fotos.
 */
export function triggerExport(projectId: number): Promise<TriggerQueuedOut> {
  return apiFetch('/projects/{project_id}/export', {
    method: 'POST',
    pathParams: { project_id: projectId },
  })
}

/**
 * Der Lauf samt Fehlerliste je Foto - die Bestätigung DANACH (Anzahl, Zielpfad, Teilfehler).
 */
export function getExportRun(projectId: number, runId: number): Promise<ExportRunDetailOut> {
  return apiFetch('/projects/{project_id}/exports/{run_id}', {
    pathParams: { project_id: projectId, run_id: runId },
  })
}
