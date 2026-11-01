import { apiFetch } from './client'
import type { ExportPreviewOut, ExportRunDetailOut } from './types'

/**
 * Die Anzahl der Endauswahl-Fotos vor dem Auslösen - server-autoritativ: exakt die Menge, die der
 * Export gleich nimmt (`backend final_selection.py::included_photos`). Das Frontend zählt die
 * Anzahl nie selbst aus der geladenen Endauswahl-Antwort.
 */
export function getExportPreview(projectId: number): Promise<ExportPreviewOut> {
  return apiFetch<ExportPreviewOut>(`/projects/${projectId}/export-preview`)
}

/**
 * Der Auslöser. Antwortet 202; der Lauf selbst ist ein Hintergrund-Job, dessen Zustand über
 * `ProjectOut.last_export_run` gepollt wird. Kein Body: es wird immer die ganze Endauswahl
 * exportiert, nie eine Auswahl einzelner Fotos.
 */
export function triggerExport(projectId: number): Promise<{ status: string }> {
  return apiFetch<{ status: string }>(`/projects/${projectId}/export`, { method: 'POST' })
}

/**
 * Der Lauf samt Fehlerliste je Foto - die Bestätigung DANACH (Anzahl, Zielpfad, Teilfehler).
 */
export function getExportRun(projectId: number, runId: number): Promise<ExportRunDetailOut> {
  return apiFetch<ExportRunDetailOut>(`/projects/${projectId}/exports/${runId}`)
}
