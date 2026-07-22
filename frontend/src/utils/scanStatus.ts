import type { ProjectOut } from '../api/types'

export type ScanStatusLabel = 'never' | 'running' | 'success' | 'failed'

/** Leitet den Scan-Kurzstatus einer Projektkarte/-detailseite aus `last_scan` ab. */
export function deriveScanStatus(project: Pick<ProjectOut, 'last_scan'>): ScanStatusLabel {
  return project.last_scan?.status ?? 'never'
}
