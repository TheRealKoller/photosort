import type { ProjectOut, ScanStatusLabel } from '../api/types'

export type { ScanStatusLabel }

/**
 * Leitet den Scan-Kurzstatus einer Projektkarte/-detailseite aus `last_scan` ab.
 *
 * Die Marke ist `ScanStatus | "never"` - eine Ableitung des Servervokabulars, keine zweite
 * Literalliste; `never` heisst "noch nie gelaufen".
 */
export function deriveScanStatus(project: Pick<ProjectOut, 'last_scan'>): ScanStatusLabel {
  return project.last_scan?.status ?? 'never'
}
