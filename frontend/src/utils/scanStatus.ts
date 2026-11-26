import type { ProjectOut } from '../api/types'

/**
 * Die Wortlaute der Statusmarke. `queued`/`cancelled` sind KEINE Fehler: beide
 * tragen den neutralen Ton `never`, nur das Wort daneben unterscheidet sie.
 */
export type ScanStatusLabel = 'never' | 'queued' | 'running' | 'success' | 'failed' | 'cancelled'

/** Leitet den Scan-Kurzstatus einer Projektkarte/-detailseite aus `last_scan` ab. */
export function deriveScanStatus(project: Pick<ProjectOut, 'last_scan'>): ScanStatusLabel {
  return project.last_scan?.status ?? 'never'
}
