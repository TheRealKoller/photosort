import type {
  ClassificationReviewPurpose,
  ClassificationReviewUnit,
  ClassificationVerdict,
} from '../api/types'
import { formatMotifKey, type MotifSet } from './motifLabels'

/*
 * Die EINE Begriffsquelle der Pruefseiten (Spec 0616, Abschnitt UI/UX): Seitentitel, die drei
 * Begriffe, Seitenmarken, vier Urteile, vier Zwecke und ihre Einheiten. Aufrufstellen lesen von
 * hier und schreiben kein Literal ab - sonst tragen zwei Stellen dieselbe Aussage und driften.
 *
 * ABGRENZUNG ZUR BEWERTUNG (Spec 0616): Hier steht weder "Vergleich" noch "Bewertung" allein. Das
 * Vokabular dieser Seiten ist "Pruefung", "Fall" und "Urteil"; eine Aufrufstelle, die eines der
 * beiden verbotenen Worte zeigt, faellt bei der Pruefung der sichtbaren Woerter auf.
 */

/** Der Seitentitel - wortgleich mit dem Nebenziel der Projektnavigation. */
export const CLASSIFICATION_REVIEW_TITLE = 'Klassifizierung prüfen'

/** Die drei Begriffe, die auf jeder Pruefseite stehen. */
export const TERMS = {
  review: 'Prüfung',
  case: 'Fall',
  verdict: 'Urteil',
} as const

/** Die dauerhaften Saetze der Pruefseiten. */
export const CLASSIFICATION_REVIEW_TEXTS = {
  intro:
    'Zwei Klassifizierungsverfahren am Foto gegenüberstellen und beurteilen. Die geltenden Ergebnisse der Fotos bleiben dabei unverändert.',
} as const

/** Die beiden Seiten - sichtbarer Name. */
export const SIDE_LABELS = {
  a: 'Seite A',
  b: 'Seite B',
} as const satisfies Record<'a' | 'b', string>

/** Die neutrale Buchstabenmarke; A und B unterscheiden sich NUR ueber den Buchstaben. */
export const SIDE_MARKS = {
  a: 'A',
  b: 'B',
} as const satisfies Record<'a' | 'b', string>

/** Anzeigereihenfolge der vier Urteile, zugleich die Reihenfolge der Schaltflaechen. */
export const VERDICT_ORDER = [
  'a_better',
  'b_better',
  'both_ok',
  'both_wrong',
] as const satisfies readonly ClassificationVerdict[]

/** Die vier Urteile. */
export const VERDICT_LABELS = {
  a_better: 'A besser',
  b_better: 'B besser',
  both_ok: 'beide ok',
  both_wrong: 'beide falsch',
} as const satisfies Record<ClassificationVerdict, string>

/** Die vier Pruefzwecke; `motifs`, `excluded_document` und `album_level` zaehlen Fotos,
 * `motif_feature` zaehlt Paare aus Foto und Motiv. */
export const PURPOSE_LABELS = {
  motifs: 'Motive',
  motif_feature: 'Merkmale',
  excluded_document: 'Dokument-Ausschluss',
  album_level: 'Albumtauglichkeit',
} as const satisfies Record<ClassificationReviewPurpose, string>

/** Die Einheit einer Zaehlung, wie der Server sie mitliefert - steht im Spaltenkopf. */
export const PURPOSE_UNIT_LABELS = {
  photo: 'Fotos',
  pair: 'Paare',
} as const satisfies Record<ClassificationReviewUnit, string>

/**
 * Das Wort fuer eine fehlende Aussage. `null` einer Seite ist genau das und nie `false` oder `0` -
 * ein `?? 0` an der Anzeigestelle behauptete eine Aussage, die niemand getroffen hat.
 */
export const NO_STATEMENT_TEXT = 'keine Aussage'

/**
 * Der Titel EINES Falls. Feine Merkmale nennen ihren Motivnamen ueber `formatMotifKey` - das Set
 * kommt zur Laufzeit vom Server, deshalb als expliziter Parameter wie in der uebrigen
 * Motivanzeige.
 */
export function reviewCaseTitle(
  purpose: ClassificationReviewPurpose,
  motifKey: string | null,
  motifs: MotifSet,
): string {
  if (purpose !== 'motif_feature') {
    return PURPOSE_LABELS[purpose]
  }
  if (motifKey === null || motifKey === '') {
    return PURPOSE_LABELS.motif_feature
  }
  return `Merkmal: ${formatMotifKey(motifKey, motifs)}`
}
