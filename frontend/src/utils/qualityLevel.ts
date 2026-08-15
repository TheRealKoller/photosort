export type QualityLevel = 'low' | 'medium' | 'high'

// Grobe, verstaendliche 3-Stufen-Einordnung statt eines Rohwerts (urspruenglich specs/features/
// 0024-top-photo-selection-category-mix.md, UI/UX-Abschnitt "Grobe Qualitaets-Einordnung statt
// Rohwert") - seit specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md aus
// PhotoRanking.rank_score abgeleitet statt aus dem entfallenen local_quality_score. rank_score
// ist bereits auf [0, 1] normiert (gewichteter Mittelwert bereits normierter Kriterien-Werte,
// backend ranking.py::rank_photos), die Schwellwerte sind daher ebenfalls auf dieser Skala.
// Technische Detailentscheidung der Umsetzung, nicht gegen einen echten Fotokorpus kalibriert
// (gleicher Kalibrierungs-Vorbehalt wie backend/src/photosort/scoring.py::
// SHARPNESS_REJECT_THRESHOLD).
const LOW_MEDIUM_THRESHOLD = 0.4
const MEDIUM_HIGH_THRESHOLD = 0.7

export function qualityLevel(rankScore: number | null): QualityLevel | null {
  if (rankScore === null) {
    return null
  }
  if (rankScore < LOW_MEDIUM_THRESHOLD) {
    return 'low'
  }
  if (rankScore < MEDIUM_HIGH_THRESHOLD) {
    return 'medium'
  }
  return 'high'
}

export const QUALITY_LEVEL_LABELS: Record<QualityLevel, string> = {
  low: 'Einfache Bildqualität',
  medium: 'Gute Bildqualität',
  high: 'Hohe Bildqualität',
}
