export type QualityLevel = 'low' | 'medium' | 'high'

// Grobe, verstaendliche 3-Stufen-Einordnung statt eines Rohwerts
// (specs/features/0024-top-photo-selection-category-mix.md, UI/UX-Abschnitt "Grobe
// Qualitaets-Einordnung statt Rohwert") - abgeleitet aus dem bestehenden, unbeschraenkten
// local_quality_score (Schaerfe * (1 - Belichtungs-Clipping-Anteil), backend scoring.py). Feste,
// dokumentierte Schwellwerte statt Nutzer-Konfigurierbarkeit (Out-of-Scope laut Spec) - technische
// Detailentscheidung der Umsetzung, nicht gegen einen echten Fotokorpus kalibriert (gleicher
// Kalibrierungs-Vorbehalt wie backend/src/photosort/scoring.py::SHARPNESS_REJECT_THRESHOLD).
const LOW_MEDIUM_THRESHOLD = 30
const MEDIUM_HIGH_THRESHOLD = 80

export function qualityLevel(localQualityScore: number | null): QualityLevel | null {
  if (localQualityScore === null) {
    return null
  }
  if (localQualityScore < LOW_MEDIUM_THRESHOLD) {
    return 'low'
  }
  if (localQualityScore < MEDIUM_HIGH_THRESHOLD) {
    return 'medium'
  }
  return 'high'
}

export const QUALITY_LEVEL_LABELS: Record<QualityLevel, string> = {
  low: 'Einfache Bildqualität',
  medium: 'Gute Bildqualität',
  high: 'Hohe Bildqualität',
}
