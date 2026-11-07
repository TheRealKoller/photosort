import type {
  ClassificationReviewCaseSideOut,
  ClassificationReviewListItemOut,
  ClassificationReviewPhase,
  ClassificationReviewPurpose,
  ClassificationReviewSideKind,
  ClassificationReviewUnit,
  ClassificationVerdict,
} from '../api/types'
import { formatAlbumSuitabilityLevel } from './albumSuitability'
import { formatProviderLabel, formatUsd, NOT_AVAILABLE } from './formatStats'
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
  failedLatest: 'Die letzte Prüfung ist fehlgeschlagen. Sie wird nicht automatisch wiederholt.',
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

/**
 * Die Taste je Urteil. Bewusst Buchstaben und keine Ziffern: 1/2/3 sind im Produkt die
 * Bewertungstasten, und "gleiche Taste macht immer dasselbe" gilt seitenuebergreifend.
 */
export const VERDICT_KEYS = {
  a_better: 'A',
  b_better: 'B',
  both_ok: 'O',
  both_wrong: 'F',
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

/** Die Zeilengruppe einer Einheit in der Abweichungstabelle. */
export const UNIT_GROUP_LABELS = {
  photo: 'Zwecke',
  pair: 'Merkmale (Foto × Motiv)',
} as const satisfies Record<ClassificationReviewUnit, string>

/** Der sichtbare Teilschritt einer laufenden Pruefung. */
export const PHASE_LABELS = {
  side_a: 'Seite A wird klassifiziert',
  side_b: 'Seite B wird klassifiziert',
  cases: 'Fälle werden gezogen',
} as const satisfies Record<ClassificationReviewPhase, string>

/** Die dauerhaften Saetze und Beschriftungen der Detailseite. */
export const REVIEW_DETAIL_TEXTS = {
  backToList: 'Zur Liste der Prüfungen',
  originRegion: 'Herkunft der Seiten',
  loading: 'Prüfung wird geladen…',
  loadError: 'Fehler beim Laden der Prüfung.',
  casesLoadError: 'Fehler beim Laden der Fälle.',
  failedFallback: 'Die Prüfung ist fehlgeschlagen.',
  allJudged: 'Alle Fälle sind beurteilt. Der Export bleibt verfügbar.',
  noCases: 'Diese Prüfung hat keinen Fall vorgelegt.',
  previousPhoto: 'Vorheriges Foto',
  nextPhoto: 'Nächstes Foto',
  nextOpenPhoto: 'Nächstes offenes Foto',
  casesOfPhoto: 'Fälle dieses Fotos',
  saveError: 'Das Urteil konnte nicht gespeichert werden.',
  overviewTitle: 'Übersicht',
  deviationsCaption: 'Abweichungen',
  verdictsCaption: 'Urteile',
  purposeColumn: 'Zweck',
  matching: 'übereinstimmend',
  deviating: 'abweichend',
  presented: 'vorgelegt',
  open: 'offen',
  total: 'gesamt',
  exportTitle: 'Export',
  exportButton: 'Für die KI exportieren',
  exportContents:
    'Die Datei enthält keine Bilddaten, keine Dateinamen, keine Orte und keine Namen - je Fall nur die Fotonummer, den Zweck, beide Rohwerte und das Urteil.',
  exportBlockedRunning: 'Der Export ist erst nach Abschluss der Prüfung möglich.',
  exportBlockedFailed: 'Eine fehlgeschlagene Prüfung lässt sich nicht exportieren.',
  exportError: 'Der Export konnte nicht geladen werden.',
} as const

/** "{n} offen von {m}" - die Faelle ohne Urteil gegen alle vorgelegten Faelle. */
export function reviewProgressText(open: number, total: number): string {
  return `${open} offen von ${total}`
}

/** Der Satz zu den Fotos ohne Ergebnis auf mindestens einer Seite; nur fuer `count > 0`. */
export function unclassifiableText(count: number): string {
  return count === 1
    ? '1 Foto ließ sich nicht klassifizieren und wurde für keinen Zweck verglichen.'
    : `${count} Fotos ließen sich nicht klassifizieren und wurden für keinen Zweck verglichen.`
}

/** Der Fortschritt einer laufenden Pruefung nach Teilschritt. */
export function reviewPhaseText(
  phase: ClassificationReviewPhase | null,
  processed: number,
  photoCount: number,
): string {
  const step = phase === null ? 'Prüfung läuft' : PHASE_LABELS[phase]
  return `${step}… ${processed} von ${photoCount} Fotos`
}

/** Die Beschriftung des Fotowechslers; `position` ist die laufende Nummer der Pruefmenge. */
export function photoPositionLabel(position: number, photoCount: number): string {
  return `Foto ${position} von ${photoCount}`
}

/** Der Hinweis, wenn KEIN Foto auf beiden Seiten ein Ergebnis hat (alle einzeln gescheitert). */
export function noPhotosComparedText(failedPhotos: number): string {
  return `keine Fotos verglichen - ${failedPhotos} ${failedPhotos === 1 ? 'Foto' : 'Fotos'} fehlgeschlagen`
}

/** Ein Zweck ohne gemeinsame Aussage, mit der Seite, die schweigt. */
export function notComparedText(side: 'a' | 'b'): string {
  return `nicht verglichen — ${SIDE_LABELS[side]} trifft dazu keine Aussage`
}

/** Ein Zweck ohne gemeinsame Aussage, obwohl beide Seiten dazu etwas sagen koennten. */
export const NO_SHARED_STATEMENT_TEXT = 'nicht verglichen — keine gemeinsame Aussage'

/**
 * Die Seite, die zu einem Zweck strukturell keine Aussage trifft: die lokale Seite kennt weder
 * Dokument-Ausschluss noch Albumstufe (der Lauf speichert beide als `NULL`). Eye und Cloud sagen
 * zu allen Zwecken etwas. `null` heisst: beide Seiten koennen etwas sagen.
 */
export function silentSide(
  purpose: ClassificationReviewPurpose,
  kinds: { a: ClassificationReviewSideKind; b: ClassificationReviewSideKind },
): 'a' | 'b' | null {
  if (purpose !== 'excluded_document' && purpose !== 'album_level') {
    return null
  }
  if (kinds.a === 'local') {
    return 'a'
  }
  return kinds.b === 'local' ? 'b' : null
}

/** Der Schreiber eines gesetzten Urteils. */
export function verdictWriterText(username: string): string {
  return `von ${username}`
}

/** Der zugaengliche Name der Urteilsgruppe EINES Falls. */
export function verdictGroupLabel(caseTitle: string): string {
  return `${TERMS.verdict} zu ${caseTitle}`
}

/**
 * Das Wort fuer eine fehlende Aussage. `null` einer Seite ist genau das und nie `false` oder `0` -
 * ein `?? 0` an der Anzeigestelle behauptete eine Aussage, die niemand getroffen hat.
 */
export const NO_STATEMENT_TEXT = 'keine Aussage'

/** Wahrheitswerte der Rohwerte - Motive, Merkmale und Dokument-Ausschluss. */
export const YES_NO_TEXTS = { yes: 'ja', no: 'nein' } as const

/** Die leere Praesenzmenge eines Fotos: eine Aussage ("kein Motiv"), nicht "keine Aussage". */
export const NO_MOTIF_TEXT = 'kein Motiv'

/**
 * Der Rohwert EINER Seite in einem Fall, als Text. `null` ist "keine Aussage", nie `nein` oder
 * eine Stufe 0. Bei `motifs` ist die Praesenzmenge der Rohwert und steht als Motivnamen da.
 */
export function caseSideValueText(
  purpose: ClassificationReviewPurpose,
  side: ClassificationReviewCaseSideOut,
  motifs: MotifSet,
): string {
  switch (purpose) {
    case 'motifs':
      if (side.motifs === null) {
        return NO_STATEMENT_TEXT
      }
      return side.motifs.length === 0
        ? NO_MOTIF_TEXT
        : side.motifs.map((key) => formatMotifKey(key, motifs)).join(', ')
    case 'motif_feature':
      return side.present === null ? NO_STATEMENT_TEXT : yesNo(side.present)
    case 'excluded_document':
      return side.excluded_document === null ? NO_STATEMENT_TEXT : yesNo(side.excluded_document)
    case 'album_level':
      return side.album_level === null
        ? NO_STATEMENT_TEXT
        : formatAlbumSuitabilityLevel(side.album_level)
  }
}

function yesNo(value: boolean): string {
  return value ? YES_NO_TEXTS.yes : YES_NO_TEXTS.no
}

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

/**
 * Der Hinweis unter dem Stand einer abgeschlossenen Pruefung OHNE Fall.
 *
 * "keine Abweichungen" ist nur dann eine Aussage ueber die Verfahren, wenn wirklich etwas
 * verglichen wurde. Ist `unclassifiable_photo_count` gleich der Pruefmenge, hat KEIN Foto auf
 * beiden Seiten ein Ergebnis - dann nennt der Hinweis die fehlgeschlagenen Fotos statt einer
 * Uebereinstimmung (Spec 0616, Edge Case 4 / AK 9).
 */
export function reviewNoCaseText(
  review: Pick<ClassificationReviewListItemOut, 'photo_count' | 'unclassifiable_photo_count'>,
): string {
  return review.unclassifiable_photo_count === review.photo_count
    ? noPhotosComparedText(review.unclassifiable_photo_count)
    : NO_DEVIATION_TEXT
}

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
  notRecorded: 'nicht erfasst',
} as const

/**
 * Die Kostenzeile EINER Seite der Pruefung (AK 9/AK 12): Ist-Kosten mit dem beim Anlegen
 * eingefrorenen Schaetzwert in der Klammer. Eye und lokal sind kostenfrei und tragen das Wort,
 * nie "0,00 USD"; ein Cloud-Lauf ohne Ist-Wert heisst "nicht erfasst". Ein bereits geschriebener
 * Ist-Wert bleibt nach einem Abbruch stehen - die bis dahin angefallenen Kosten sind die einzige
 * Auskunft ueber den gescheiterten Lauf.
 */
export function sideCostText(side: {
  kind: ClassificationReviewSideKind
  estimated_cost_usd: number | null
  cost_usd: number | null
}): string {
  if (side.kind !== 'cloud') {
    return SIDE_COST_LABELS.free
  }
  if (side.cost_usd === null) {
    return SIDE_COST_LABELS.notRecorded
  }
  const estimate =
    side.estimated_cost_usd === null
      ? SIDE_COST_LABELS.notRecorded
      : formatUsd(side.estimated_cost_usd)
  return `Ist ${formatUsd(side.cost_usd)} (vor dem Start geschätzt: ${estimate})`
}

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
