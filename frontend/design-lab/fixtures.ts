/*
 * TEMPORAER (specs/features/0287-design-richtungen-vergleich.md): die EINE Inhaltsquelle des
 * Design-Labors.
 *
 * Alle fuenf Richtungen zeigen exakt dieselben Beispielinhalte - dieselben 12 Fotos in derselben
 * Reihenfolge, dieselben Bewertungen/Vorschlaege, denselben Override, dieselben Kriterien-
 * Prozentwerte, dieselbe Schrittzustands-Mischung (Akzeptanzkriterium 5). Das ist hier
 * strukturell garantiert statt per Test: drei geteilte Ansichtskomponenten lesen ausschliesslich
 * aus dieser Datei.
 *
 * Die Werte bilden den heutigen realen Inhalt der App ab (Kategorien-Set aus
 * backend/src/photosort/categories.py, Kriterien aus criteria.py, Schrittnamen aus
 * frontend/src/utils/pipelineSteps.ts) - bewusst als KOPIE, weil das Labor keine Kante nach
 * frontend/src/ haben darf (Schutzgelaender G1c).
 */
import type { AspectId, MotifId } from './photoSvg'

export type RatingStatus = 'favorite' | 'album_worthy' | 'rejected'
export type BadgeState = RatingStatus | 'unrated'

export interface CriterionScore {
  key: string
  displayName: string
  /** Normiert auf [0, 1] - die Ansicht zeigt kaufmaennisch gerundete Prozent. */
  value: number
  /** Steuert die Blockzuordnung "Qualitaet" vs. "Kategorien" (wie in der echten App). */
  categoryEligible: boolean
}

export interface CategoryCandidate {
  categoryKey: string
  /** Herkunfts-Chip: "Lokal erkannt" bzw. der Provider-Anzeigename. */
  originLabel: string
}

export interface CloudVisionEntry {
  phaseLabel: string
  statusLabel: string
  /** Steuert nur das dekorative, aria-hidden Symbol - der Statustext traegt die Information. */
  tone: 'idle' | 'success' | 'failed'
}

export interface LabPhoto {
  id: number
  fileName: string
  takenAt: string
  motif: MotifId
  aspect: AspectId
  /** Eigene Bewertung; `null`, solange das Foto unbewertet ist. */
  ownRating: RatingStatus | null
  /** Offener maschineller Vorschlag - nur gesetzt, solange keine eigene Bewertung existiert. */
  suggestion: { status: RatingStatus; reason: string } | null
  categoryKey: string
  /** Manuell uebersteuerte Kategorie (Marker ✎ auf der Kachel). */
  categoryOverride: string | null
  fineLabels: string[]
  criterionScores: CriterionScore[]
  ranking: { rankPosition: number; partitionSize: number; rankScore: number }
}

export interface LabCategory {
  key: string
  displayName: string
  /** Drei Grossbuchstaben des Anzeigenamens - identisch zur Regel der echten App. */
  abbreviation: string
}

/** Auffangkorb-Kategorie: steht immer zuletzt und traegt KEINE Fehler-Optik. */
export const CATCH_ALL_CATEGORY_KEY = 'nicht_erkannt'

export const CATCH_ALL_EXPLANATION = 'Für diese Fotos war kein Bildmotiv sicher bestimmbar.'

export const CATEGORIES: readonly LabCategory[] = [
  { key: 'menschen', displayName: 'Menschen', abbreviation: 'MEN' },
  { key: 'landschaft', displayName: 'Landschaft', abbreviation: 'LAN' },
  { key: 'essen_trinken', displayName: 'Essen & Trinken', abbreviation: 'ESS' },
  { key: 'gebaeude_bauwerk', displayName: 'Gebäude & Bauwerk', abbreviation: 'GEB' },
  { key: CATCH_ALL_CATEGORY_KEY, displayName: 'Nicht erkannt', abbreviation: 'NIC' },
]

export function categoryName(key: string): string {
  return CATEGORIES.find((entry) => entry.key === key)?.displayName ?? key
}

export function categoryAbbreviation(key: string): string {
  return CATEGORIES.find((entry) => entry.key === key)?.abbreviation ?? key.slice(0, 3).toUpperCase()
}

/** Beschriftungen der sechs Filter-Pillen, woertlich wie in der App. */
export const FILTERS: readonly { id: string; label: string }[] = [
  { id: 'all', label: 'Alle' },
  { id: 'unrated', label: 'Unbewertet' },
  { id: 'suggested', label: 'Vorgeschlagen' },
  { id: 'favorite', label: 'Favorit' },
  { id: 'album_worthy', label: 'Album-würdig' },
  { id: 'rejected', label: 'Verworfen' },
]

export const ACTIVE_FILTER_ID = 'all'

export const RATING_LABELS: Record<RatingStatus, string> = {
  favorite: 'Favorit',
  album_worthy: 'Album-würdig',
  rejected: 'Verworfen',
}

/** Symbole der Bewertungsstufen - in JEDER Richtung identisch, nie durch reine Farbe ersetzt. */
export const RATING_SYMBOLS: Record<BadgeState, string> = {
  favorite: '★',
  album_worthy: '✓',
  rejected: '✕',
  unrated: '–',
}

/** Praefix vor dem Stufensymbol bei einem unbestaetigten maschinellen Vorschlag. */
export const SUGGESTION_PREFIX = '⚙'

/** Beschriftungen der drei Bewertungsknoepfe der Detailansicht (letzter Eintrag heisst "Verwerfen"). */
export const RATING_BUTTONS: readonly { status: RatingStatus; label: string }[] = [
  { status: 'favorite', label: 'Favorit' },
  { status: 'album_worthy', label: 'Album-würdig' },
  { status: 'rejected', label: 'Verwerfen' },
]

export const SHORTCUT_HINT = 'Shortcuts: 1 Favorit, 2 Album-würdig, 3 Verwerfen, ←/→ navigieren'

/**
 * Kriterienwerte eines Fotos - deterministisch aus einem Startwert abgeleitet, damit alle zwoelf
 * Fotos eigene, aber reproduzierbare Zahlen tragen. Reihenfolge und Blockzuordnung entsprechen der
 * Registry der echten App (Qualitaets-Kriterien zuerst, kategoriefaehige danach).
 */
function scoresFor(seed: number): CriterionScore[] {
  const shift = (offset: number): number => {
    const raw = seed + offset
    return Math.round(Math.min(0.98, Math.max(0.08, raw)) * 100) / 100
  }
  return [
    { key: 'sharpness', displayName: 'Schärfe', value: shift(0.09), categoryEligible: false },
    { key: 'exposure', displayName: 'Belichtung', value: shift(-0.04), categoryEligible: false },
    { key: 'aesthetics', displayName: 'Ästhetik', value: shift(0.02), categoryEligible: false },
    { key: 'symmetrie', displayName: 'Symmetrie', value: shift(-0.13), categoryEligible: false },
    {
      key: 'goldener_schnitt',
      displayName: 'Goldener Schnitt',
      value: shift(-0.19),
      categoryEligible: false,
    },
    {
      key: 'landschaft',
      displayName: 'Landschaft erkannt',
      value: shift(0.05),
      categoryEligible: true,
    },
    {
      key: 'content_people',
      displayName: 'Menschen erkannt',
      value: shift(-0.31),
      categoryEligible: true,
    },
  ]
}

export const PHOTOS: readonly LabPhoto[] = [
  {
    id: 1,
    fileName: 'IMG_2041.jpg',
    takenAt: '2025-07-18T09:12:00',
    motif: 'kueste',
    aspect: 'landscape',
    ownRating: 'favorite',
    suggestion: null,
    categoryKey: 'landschaft',
    categoryOverride: null,
    fineLabels: ['Steilküste'],
    criterionScores: scoresFor(0.78),
    ranking: { rankPosition: 1, partitionSize: 4, rankScore: 0.86 },
  },
  {
    id: 2,
    fileName: 'IMG_2043.jpg',
    takenAt: '2025-07-18T09:20:00',
    motif: 'gruppe',
    aspect: 'portrait',
    ownRating: 'album_worthy',
    suggestion: null,
    categoryKey: 'menschen',
    categoryOverride: null,
    fineLabels: ['Familienbild'],
    criterionScores: scoresFor(0.66),
    ranking: { rankPosition: 1, partitionSize: 3, rankScore: 0.74 },
  },
  {
    id: 3,
    fileName: 'IMG_2048.jpg',
    takenAt: '2025-07-18T09:41:00',
    motif: 'bergkamm',
    aspect: 'landscape',
    ownRating: null,
    suggestion: { status: 'rejected', reason: 'Geringe Bildqualität' },
    categoryKey: 'landschaft',
    categoryOverride: null,
    fineLabels: ['Bergpanorama', 'Wanderweg'],
    criterionScores: scoresFor(0.36),
    ranking: { rankPosition: 4, partitionSize: 4, rankScore: 0.31 },
  },
  {
    id: 4,
    fileName: 'IMG_2052.jpg',
    takenAt: '2025-07-18T10:05:00',
    motif: 'gasse',
    aspect: 'portraitTall',
    ownRating: null,
    suggestion: null,
    categoryKey: 'gebaeude_bauwerk',
    categoryOverride: null,
    fineLabels: ['Altstadtgasse'],
    criterionScores: scoresFor(0.58),
    ranking: { rankPosition: 1, partitionSize: 2, rankScore: 0.62 },
  },
  {
    id: 5,
    fileName: 'IMG_2057.jpg',
    takenAt: '2025-07-18T10:30:00',
    motif: 'wald',
    aspect: 'landscape',
    ownRating: 'rejected',
    suggestion: null,
    categoryKey: CATCH_ALL_CATEGORY_KEY,
    categoryOverride: null,
    fineLabels: [],
    criterionScores: scoresFor(0.29),
    ranking: { rankPosition: 2, partitionSize: 2, rankScore: 0.28 },
  },
  {
    id: 6,
    fileName: 'IMG_2061.jpg',
    takenAt: '2025-07-18T11:02:00',
    motif: 'tisch',
    aspect: 'landscape',
    ownRating: null,
    suggestion: { status: 'rejected', reason: 'Duplikat von Foto #3' },
    categoryKey: 'essen_trinken',
    categoryOverride: null,
    fineLabels: ['Frühstückstisch'],
    criterionScores: scoresFor(0.44),
    ranking: { rankPosition: 2, partitionSize: 3, rankScore: 0.44 },
  },
  {
    id: 7,
    fileName: 'IMG_2068.jpg',
    takenAt: '2025-07-18T14:05:00',
    motif: 'kueste',
    aspect: 'portrait',
    ownRating: 'favorite',
    suggestion: null,
    categoryKey: 'landschaft',
    categoryOverride: null,
    fineLabels: ['Bucht'],
    criterionScores: scoresFor(0.72),
    ranking: { rankPosition: 2, partitionSize: 4, rankScore: 0.79 },
  },
  {
    id: 8,
    fileName: 'IMG_2073.jpg',
    takenAt: '2025-07-18T14:26:00',
    motif: 'gasse',
    aspect: 'portrait',
    ownRating: null,
    suggestion: null,
    categoryKey: 'gebaeude_bauwerk',
    // Der eine Override im Datensatz: automatisch als "Landschaft" eingeordnet, manuell auf
    // "Gebäude & Bauwerk" gezogen - die Kachel traegt deshalb den ✎-Marker.
    categoryOverride: 'gebaeude_bauwerk',
    fineLabels: ['Kirchturm'],
    criterionScores: scoresFor(0.54),
    ranking: { rankPosition: 2, partitionSize: 2, rankScore: 0.57 },
  },
  {
    id: 9,
    fileName: 'IMG_2079.jpg',
    takenAt: '2025-07-18T14:52:00',
    motif: 'gruppe',
    aspect: 'landscape',
    ownRating: 'album_worthy',
    suggestion: null,
    categoryKey: 'menschen',
    categoryOverride: null,
    fineLabels: ['Strandspaziergang'],
    criterionScores: scoresFor(0.63),
    ranking: { rankPosition: 2, partitionSize: 3, rankScore: 0.68 },
  },
  {
    id: 10,
    fileName: 'IMG_2084.jpg',
    takenAt: '2025-07-18T15:10:00',
    motif: 'tisch',
    aspect: 'portrait',
    ownRating: null,
    suggestion: null,
    categoryKey: 'essen_trinken',
    categoryOverride: null,
    fineLabels: ['Eisdiele'],
    criterionScores: scoresFor(0.51),
    ranking: { rankPosition: 1, partitionSize: 3, rankScore: 0.55 },
  },
  {
    id: 11,
    fileName: 'IMG_2088.jpg',
    takenAt: '2025-07-18T15:28:00',
    motif: 'wald',
    aspect: 'portraitTall',
    ownRating: null,
    suggestion: { status: 'rejected', reason: 'Geringe Bildqualität' },
    categoryKey: CATCH_ALL_CATEGORY_KEY,
    categoryOverride: null,
    fineLabels: [],
    criterionScores: scoresFor(0.33),
    ranking: { rankPosition: 1, partitionSize: 2, rankScore: 0.34 },
  },
  {
    id: 12,
    fileName: 'IMG_2091.jpg',
    takenAt: '2025-07-18T15:40:00',
    motif: 'bergkamm',
    aspect: 'landscape',
    ownRating: null,
    suggestion: null,
    categoryKey: 'landschaft',
    categoryOverride: null,
    fineLabels: ['Passhöhe'],
    criterionScores: scoresFor(0.69),
    ranking: { rankPosition: 3, partitionSize: 4, rankScore: 0.72 },
  },
]

/** Position des in der Detailansicht gezeigten Fotos (1-basiert, wie der Positionszaehler). */
export const DETAIL_PHOTO_POSITION = 3

export const DETAIL_PHOTO: LabPhoto = PHOTOS[DETAIL_PHOTO_POSITION - 1]

/** Mehr als ein Kandidat - dadurch zeigt die Detailansicht die Kandidatenliste statt einer Zeile. */
export const DETAIL_CATEGORY_CANDIDATES: readonly CategoryCandidate[] = [
  { categoryKey: 'landschaft', originLabel: 'Lokal erkannt' },
  { categoryKey: 'gebaeude_bauwerk', originLabel: 'Anthropic' },
]

export const DETAIL_CLOUD_VISION: readonly CloudVisionEntry[] = [
  { phaseLabel: 'Landmark-Erkennung', statusLabel: 'Ergebnis vorhanden', tone: 'success' },
  { phaseLabel: 'Remote-Kategorie', statusLabel: 'Erfolgreich, keine Treffer', tone: 'success' },
]

export type StepState = 'done' | 'current' | 'pending' | 'blocked'

export interface PipelineStep {
  id: string
  label: string
  state: StepState
}

/** Gemischte Zustaende, damit alle vier Schritt-Darstellungen gleichzeitig sichtbar sind. */
export const PIPELINE_STEPS: readonly PipelineStep[] = [
  { id: 'scan', label: 'Scan', state: 'done' },
  { id: 'ausschuss', label: 'Ausschuss-Erkennung', state: 'done' },
  { id: 'gate', label: 'Ausschuss-Gate', state: 'current' },
  { id: 'kriterien', label: 'Kriterien-Bewertung', state: 'pending' },
  { id: 'kuratierung', label: 'Kategorie-Kuratierung', state: 'blocked' },
]

export type QualityLevel = 'low' | 'medium' | 'high'

export const QUALITY_LEVEL_LABELS: Record<QualityLevel, string> = {
  low: 'Einfache Bildqualität',
  medium: 'Gute Bildqualität',
  high: 'Hohe Bildqualität',
}

/** `●●○` als rein dekoratives Symbol - der ausgeschriebene Stufenname traegt die Information. */
export const QUALITY_LEVEL_DOTS: Record<QualityLevel, string> = {
  low: '●○○',
  medium: '●●○',
  high: '●●●',
}

export function qualityLevel(rankScore: number): QualityLevel {
  if (rankScore < 0.4) {
    return 'low'
  }
  if (rankScore < 0.7) {
    return 'medium'
  }
  return 'high'
}

/** Top-N-Eingabe der Kuratierung; steuert zugleich die Zahl der Platzhalterkacheln. */
export const CURATION_TOP_N = 3

export const CURATION_DAY_HEADING = 'Freitag 18.07.2025'
export const CURATION_CLUSTER_HEADING = 'Nachmittags (14:05–15:40 Uhr)'

export interface CurationSection {
  categoryKey: string
  photoIds: number[]
}

/**
 * Kategorie-Abschnitte der Kuratierung. Der Auffangkorb steht immer ZULETZT (Design-System-Muster
 * "Auffangkorb-Kategorie mit erklaerend dezentem Signal"); Abschnitte mit weniger als
 * `CURATION_TOP_N` Fotos zeigen die gestrichelte Platzhalterkachel.
 */
export const CURATION_SECTIONS: readonly CurationSection[] = [
  { categoryKey: 'landschaft', photoIds: [1, 7, 12] },
  { categoryKey: 'menschen', photoIds: [2, 9] },
  { categoryKey: CATCH_ALL_CATEGORY_KEY, photoIds: [5] },
]

export const CURATION_PLACEHOLDER_LABEL = 'Kein weiteres Foto verfügbar'

export function photoById(id: number): LabPhoto {
  const photo = PHOTOS.find((entry) => entry.id === id)
  if (photo === undefined) {
    throw new Error(`Design-Labor: Foto #${id} steht nicht in fixtures.ts`)
  }
  return photo
}

/** Kaufmaennisch gerundeter Prozentwert ohne Nachkommastelle, wie in der echten App. */
export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`
}
