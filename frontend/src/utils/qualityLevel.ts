export type QualityLevel = 'low' | 'medium' | 'high'

// Grobe, verstaendliche 3-Stufen-Einordnung statt eines Rohwerts - aus PhotoRanking.rank_score
// abgeleitet, der seit Spec 0428 der QUALITAETSWERT ist: die normierte Modellstufe der
// Albumtauglichkeit plus ein lokales Korrekturband von +-0,1 (backend quality.py).
//
// DIE SCHWELLEN LIEGEN AUF DEN STUFENMITTEN (0,375 = Mitte zwischen Stufe 2 und 3, 0,625 =
// Mitte zwischen 3 und 4). Damit ist diese Anzeige eine DETERMINISTISCHE VERGROEBERUNG der
// Modellstufe: Stufe 1-2 -> niedrig, 3 -> mittel, 4-5 -> hoch, fuer JEDEN zulaessigen lokalen
// Korrekturbetrag. Das gilt, solange `quality.py::LOCAL_CORRECTION_SPAN < 0,125` ist - ein
// groesserer Wert liesse dieselbe Modellstufe in zwei Anzeigestufen erscheinen, und die
// Zuordnung oben waere falsch. Der Backend-Test dazu prueft die Grenze STRIKT.
//
// Beide Schwellen sind INKLUSIV verglichen (`>=`) und exportiert - der Test nagelt sie als
// Literale fest, statt sie aus der Funktion abzulesen.
export const LOW_MEDIUM_THRESHOLD = 0.375
export const MEDIUM_HIGH_THRESHOLD = 0.625

/**
 * Die Anzeigestufe eines Qualitätswerts. `null` heißt „noch nicht bewertet" - der Zustand ohne
 * Modellurteil. Auf `=== null` geprüft und NIE auf Falsyness: `0` ist ein gültiger
 * Qualitätswert (schlechteste Modellstufe, schlechteste lokale Messung), und ein
 * Falsyness-Filter verlöre ihn lautlos.
 */
export function qualityLevel(rankScore: number | null): QualityLevel | null {
  if (rankScore === null) {
    return null
  }
  if (rankScore >= MEDIUM_HIGH_THRESHOLD) {
    return 'high'
  }
  return rankScore >= LOW_MEDIUM_THRESHOLD ? 'medium' : 'low'
}

// Die Beschriftungen benennen die ALBUMTAUGLICHKEIT und nicht mehr die Bildqualität: der Wert
// misst keine Bildgüte mehr, und ein gestochen scharfes, aber langweiliges Foto trüge sonst die
// Beschriftung „Einfache Bildqualität". Dieselbe Vokabel gilt in Datenmodell, API und Oberfläche.
export const QUALITY_LEVEL_LABELS: Record<QualityLevel, string> = {
  low: 'Wenig albumtauglich',
  medium: 'Bedingt albumtauglich',
  high: 'Gut albumtauglich',
}
