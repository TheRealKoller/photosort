import { apiFetch } from './client'
import type {
  CancelAllOperationsOut,
  CancelOperationOut,
  OperationKind,
  OperationsOut,
} from './types'

/*
 * Spec 0641: Die drei Endpunkte der Vorgangssteuerung. `kind` und `run_id` adressieren GENAU
 * einen Lauf - ein zweiter Lauf desselben Schritts wird nie mitgemeint.
 */

/** Der Query-Schluessel liegt hier, weil ihn zwei Hook-Dateien brauchen (Abfrage und Trigger). */
export function operationsQueryKey(projectId: number) {
  return ['operations', projectId] as const
}

function operationsPath(projectId: number): string {
  return `/projects/${projectId}/operations`
}

/** Alle laufenden und wartenden Vorgaenge des Projekts - die Quelle der Projektleiste. */
export function listOperations(projectId: number): Promise<OperationsOut> {
  return apiFetch<OperationsOut>(operationsPath(projectId))
}

/** Bittet um den Abbruch EINES Vorgangs; `already_finished` ist kein Fehler. */
export function cancelOperation(
  projectId: number,
  kind: OperationKind,
  runId: number,
): Promise<CancelOperationOut> {
  return apiFetch<CancelOperationOut>(`${operationsPath(projectId)}/${kind}/${runId}/cancel`, {
    method: 'POST',
  })
}

/** Bittet um den Abbruch aller laufenden und wartenden Vorgaenge des Projekts. */
export function cancelAllOperations(projectId: number): Promise<CancelAllOperationsOut> {
  return apiFetch<CancelAllOperationsOut>(`${operationsPath(projectId)}/cancel-all`, {
    method: 'POST',
  })
}
