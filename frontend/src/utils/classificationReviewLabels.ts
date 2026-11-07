import type {
  ClassificationReviewListItemOut,
  ClassificationReviewPurpose,
  ClassificationReviewSideKind,
  ClassificationReviewUnit,
  ClassificationVerdict,
} from '../api/types'
import { formatProviderLabel, NOT_AVAILABLE } from './formatStats'
import { formatMotifKey, type MotifSet } from './motifLabels'
import type { ScanStatusLabel } from './scanStatus'

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

/** Die dauerhaften Saetze und Beschriftungen der Pruefseiten. */
export const CLASSIFICATION_REVIEW_TEXTS = {
  intro:
    'Zwei Klassifizierungsverfahren am Foto gegenüberstellen und beurteilen. Die geltenden Ergebnisse der Fotos bleiben dabei unverändert.',
  createOpen: 'Neue Prüfung anlegen',
  sampleSizeLabel: 'Prüfgröße je Zweck',
  sampleSizeHint: 'Weichen mehr Fotos ab, wird zufällig ausgewählt.',
  estimateTitle: 'Kostenvorschau',
  start: 'Prüfung starten',
  // Der Satz gehoert an die Stelle des juengsten Fehlschlags; die Handlung daneben heisst
  // "Erneut anlegen", nie "Erneut versuchen": die gescheiterte Pruefung wird nicht wiederholt.
  failedLatest:
    'Die letzte Prüfung ist fehlgeschlagen. Sie wird nicht automatisch wiederholt.',
  retryCreate: 'Erneut anlegen',
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
 * Der Stand EINER Zeile: das Wort und der Tonwert, den `StatusTag` traegt. `case_open` zaehlt die
 * Faelle ohne Urteil; "keine Abweichungen" steht nur bei wirklich null Faellen, weil es eine
 * Aussage ueber die Verfahren ist und nicht ueber die Urteile.
 *
 * Der Tonwert "offene Faelle" ist neutral (`never`): eine offene Beurteilung ist weder Erfolg noch
 * Fehlschlag, und eine gruene Flaeche behauptete einen Abschluss.
 */
export function reviewListStand(
  review: Pick<ClassificationReviewListItemOut, 'status' | 'case_count' | 'case_open'>,
): { tone: ScanStatusLabel; label: string } {
  if (review.status === 'running') {
    return { tone: 'running', label: 'läuft…' }
  }
  if (review.status === 'failed') {
    return { tone: 'failed', label: 'fehlgeschlagen' }
  }
  if (review.case_count === 0) {
    return { tone: 'success', label: 'keine Abweichungen' }
  }
  if (review.case_open > 0) {
    return { tone: 'never', label: `${review.case_open} von ${review.case_count} Fällen offen` }
  }
  return { tone: 'success', label: 'alle beurteilt' }
}

/** Der Hinweis, wenn eine abgeschlossene Pruefung gar keinen Fall vorgelegt hat. */
export const NO_DEVIATION_TEXT = 'Die beiden Verfahren stimmen auf allen Fotos überein.'

/** Die Herkunftsmerkmale, die eine Seite traegt - eine Anzeige braucht die Rohwerte, nie Regeln. */
export interface ReviewSideOrigin {
  kind: ClassificationReviewSideKind
  provider: string | null
  model: string | null
  eye_model_revision: string | null
  eye_mapping_version: string | null
}

/**
 * Die Herkunftszeile einer Seite, IMMER vollstaendig: zwei Fassungen desselben Eye-Modells
 * unterscheiden sich oft erst am Ende, weshalb die Aufrufstelle sie umbrechen laesst statt
 * abzuschneiden. Fremdtext (Anbieter, Modell, Fassung) bleibt ein reiner Textknoten.
 */
export function sideOriginText(side: ReviewSideOrigin): string {
  switch (side.kind) {
    case 'cloud':
      return `Cloud · ${side.provider === null ? NOT_AVAILABLE : formatProviderLabel(side.provider)} · Modell ${side.model ?? NOT_AVAILABLE}`
    case 'eye':
      return `Eye · ${side.eye_model_revision ?? NOT_AVAILABLE} · Übersetzung ${side.eye_mapping_version ?? NOT_AVAILABLE}`
    case 'local':
      return 'Lokal · ohne Sehenswürdigkeits-Beitrag'
  }
}

/** Die Preisaussage einer Wahl als Wort - "kostenfrei" ist nie eine 0. */
export const SIDE_COST_LABELS = {
  free: 'kostenfrei',
  cloud: 'Cloud · kostenpflichtig',
} as const

/**
 * Die geschlossene Menge der Sperrgruende aus `GET …/options`, als Satz am Ort der Gruppe. Der
 * Server nennt Tokens; die Oberflaeche formuliert sie, sie leitet sie nicht ab.
 */
export const UNAVAILABLE_REASON_TEXTS = {
  no_consent: 'keine Cloud-Einwilligung im Projekt',
  no_api_key: 'für keinen Cloud-Anbieter ist ein API-Schlüssel hinterlegt',
  eye_disabled: 'Eye ist in dieser Installation abgeschaltet',
} as const satisfies Record<'no_consent' | 'no_api_key' | 'eye_disabled', string>

/** Der Sperrgrund EINES Anbieters, wenn andere Anbieter offen sind. */
export const PROVIDER_BLOCKED_TEXT = 'kein API-Schlüssel hinterlegt'
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
