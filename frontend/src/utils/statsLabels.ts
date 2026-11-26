import type { CloudVisionPurpose, StatsCostPurpose } from '../api/types'

export const PURPOSE_LABELS: Record<CloudVisionPurpose, string> = {
  landmark: 'Sehenswürdigkeiten-Erkennung',
  remote_category: 'Kategorie-Klassifizierung',
}

/**
 * Die Beschriftung der KOSTENPOSTEN: die beiden Cloud-Zwecke plus der Posten der
 * Klassifizierungspruefung. `PURPOSE_LABELS` bleibt auf die beiden Cloud-Zwecke verengt - es
 * beschriftet auch die Fehlschlag-Zeilen je Cloud-Zweck, wo `review` nie vorkommt.
 */
export const COST_PURPOSE_LABELS: Record<StatsCostPurpose, string> = {
  ...PURPOSE_LABELS,
  review: 'Prüfungen',
}
