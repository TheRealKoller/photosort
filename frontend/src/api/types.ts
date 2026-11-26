/**
 * Die eine Importquelle der Oberfläche für Serverstrukturen.
 *
 * Zwei Abschnitte, beide mechanisch geprüft (`scripts/tests/test_frontend_typen.py`):
 *
 * - **Erzeugt**: je Serverstruktur ein Alias auf `components["schemas"]`. Die Struktur kommt
 *   unverändert aus `backend/openapi.json`; der Alias darf einen Oberflächennamen tragen.
 * - **Oberflächen-eigen**: Typen ohne Servergegenstück (Anzeige-Ableitungen, camelCase-
 *   Parameterobjekte der API-Module, die Aufrufgrenze). Wo ein Serverfeld die Aussage trägt,
 *   leiten sie sich aus einem erzeugten Typ ab, statt eine zweite Liste zu führen.
 */
import type { components, paths } from './generated/schema'

/* ===== Erzeugt ===== */

/** Die Statuswerte eines Laufs. `queued` heißt angenommen, aber noch nicht begonnen. */
export type ScanStatus = components['schemas']['ScanStatus']

/** Der Statuswert eines Export-Laufs - ein eigenes Vokabular, siehe `ExportRunStatus`. */
export type ExportRunStatus = components['schemas']['ExportRunStatus']

export type ScanSummary = components['schemas']['ScanSummary']
export type ScoringRunSummary = components['schemas']['ScoringRunSummary']
export type ClassificationPhase = components['schemas']['ClassificationPhase']
export type CloudPhaseSummaryOut = components['schemas']['CloudPhaseSummaryOut']
export type CriterionScoringRunSummary = components['schemas']['CriterionScoringRunSummary']

export type ExportRunSummary = components['schemas']['ExportRunSummary']
export type ExportPhotoErrorOut = components['schemas']['ExportPhotoErrorOut']
export type ExportRunDetailOut = components['schemas']['ExportRunDetailOut']
export type ExportPreviewOut = components['schemas']['ExportPreviewOut']

export type OperationKind = components['schemas']['OperationKind']
export type OperationOut = components['schemas']['OperationOut']
export type OperationsOut = components['schemas']['OperationsOut']
export type CancelOutcome = components['schemas']['CancelOutcome']
export type CancelOperationOut = components['schemas']['CancelOut']
export type CancelAllOperationsOut = components['schemas']['CancelAllOut']

export type TriggerQueuedOut = components['schemas']['TriggerQueuedOut']
export type AusschussGateConfirmedOut = components['schemas']['AusschussGateConfirmedOut']

export type ProjectOut = components['schemas']['ProjectOut']
export type ProjectModelChoiceOut = components['schemas']['ProjectModelChoiceOut']
export type CreateProjectPayload = components['schemas']['ProjectCreate']
export type ModelChoicePayload = components['schemas']['ModelChoiceIn']

export type ClassificationEstimatePartOut = components['schemas']['ClassificationEstimatePartOut']
export type ClassificationEstimateOut = components['schemas']['ClassificationEstimateOut']
export type CloudModelOut = components['schemas']['CloudModelOut']
export type ModelChoiceOut = components['schemas']['ModelChoiceOut']
export type CloudVisionConsentOut = components['schemas']['CloudVisionConsentOut']

export type BrowseEntry = components['schemas']['BrowseEntry']
export type FolderCountOut = components['schemas']['FolderCountOut']

export type LoginRequest = components['schemas']['LoginRequest']
export type TokenResponse = components['schemas']['TokenResponse']

export type RatingStatus = components['schemas']['RatingStatus']
export type RatingFilter = components['schemas']['RatingFilter']
export type RatingOut = components['schemas']['RatingOut']
export type RatingWriteOut = components['schemas']['RatingWriteOut']

export type SuggestionOut = components['schemas']['SuggestionOut']
export type DuplicateDecision = components['schemas']['DuplicateDecision']
export type DuplicateGroupItem = components['schemas']['DuplicateGroupPhotoOut']
export type DuplicateGroupOut = components['schemas']['DuplicateGroupOut']
export type DuplicateGroupIndexOut = components['schemas']['DuplicateGroupIndexOut']
export type AusschussPhotoEntry = components['schemas']['AusschussPhotoEntryOut']
export type AusschussGroupEntry = components['schemas']['AusschussGroupEntryOut']
export type AusschussOut = components['schemas']['AusschussOut']

export type MotifOut = components['schemas']['MotifOut']
export type MotifStrengthBandsOut = components['schemas']['StrengthBandsOut']
export type MotifSetOut = components['schemas']['MotifSetOut']
export type MotifAssessmentOut = components['schemas']['MotifAssessmentOut']
export type EyeResultOut = components['schemas']['EyeResultOut']
export type MotifStrengthOut = components['schemas']['MotifStrengthOut']
export type MotifCorrectionOut = components['schemas']['MotifCorrectionOut']

export type DraftExchangeOut = components['schemas']['DraftExchangeOut']
export type DraftExchangeUndoIn = components['schemas']['DraftExchangeUndoIn']
export type DraftExchangeUndoOut = components['schemas']['DraftExchangeUndoOut']

export type RankingOut = components['schemas']['RankingOut']
export type CriterionSource = components['schemas']['CriterionSource']
export type CriterionScoreOut = components['schemas']['CriterionScoreOut']
export type FineLabelOut = components['schemas']['FineLabelOut']
export type FineLabelCountOut = components['schemas']['FineLabelCountOut']

export type CloudVisionPhase = components['schemas']['CloudVisionPhase']
export type CloudVisionStatus = components['schemas']['CloudVisionStatus']
export type CloudVisionStatusOut = components['schemas']['CloudVisionStatusOut']

export type PhotoLocation = components['schemas']['PhotoLocationOut']
export type EventPlace = components['schemas']['EventPlaceOut']
export type EventOut = components['schemas']['EventOut']
export type CameraOut = components['schemas']['CameraOut']
export type ProjectCameraOut = components['schemas']['ProjectCameraOut']
export type CameraTimeOffsetSuggestionOut = components['schemas']['CameraTimeOffsetSuggestionOut']
export type PhotoOut = components['schemas']['PhotoOut']

/** Herkunft einer Zuordnung: `recognized` = erkannt, `corrected` = von Hand zugeordnet. */
export type PersonOrigin = components['schemas']['PhotoPersonOut']['origin']
export type PhotoPersonOut = components['schemas']['PhotoPersonOut']
export type FaceAssignmentOut = components['schemas']['FaceAssignmentOut']
export type UnnamedFaceOut = components['schemas']['UnnamedFaceOut']
export type UnnamedFacesPageOut = components['schemas']['UnnamedFacesPageOut']
export type PersonOut = components['schemas']['PersonOut']
export type FaceOut = components['schemas']['FaceOut']

export type AlbumParticipantOut = components['schemas']['AlbumParticipantOut']
export type AlbumSelectionOut = components['schemas']['AlbumSelectionOut']
export type AlbumDecisionOut = components['schemas']['AlbumDecisionOut']
export type AlbumSuitabilityOut = components['schemas']['AlbumSuitabilityOut']
export type PhotoListOut = components['schemas']['PhotoListOut']
export type DraftAlternativesOut = components['schemas']['DraftAlternativesOut']
export type AlbumDraftOut = components['schemas']['AlbumDraftOut']

export type ProjectStatsStorage = components['schemas']['StorageOut']
export type ProjectStatsMotifEntry = components['schemas']['MotifEntryOut']
export type ProjectStatsCostByPurpose = components['schemas']['CostByPurposeOut']
export type ProjectStatsCost = components['schemas']['CostOut']
export type ProjectStatsProgress = components['schemas']['ProgressOut']
export type ProjectStatsRatings = components['schemas']['RatingsOut']
export type ProjectStatsLastSuccessfulRuns = components['schemas']['LastSuccessfulRunsOut']
export type ProjectStatsRemoteFailure = components['schemas']['RemoteFailureOut']
export type OverviewSeenOut = components['schemas']['OverviewSeenOut']
export type ProjectStatsDiagnostics = components['schemas']['DiagnosticsOut']
export type ProjectStatsOut = components['schemas']['ProjectStatsOut']

export type MotifErrorCase = components['schemas']['MotifErrorCase']
export type ExchangeKind = components['schemas']['ExchangeKind']
export type FeedbackMotifError = components['schemas']['MotifErrorOut']
export type FeedbackExchangeStats = components['schemas']['ExchangeStatsOut']
export type FeedbackCriterionAgreement = components['schemas']['CriterionAgreementOut']
export type FeedbackCurrentWeight = components['schemas']['CriterionWeightOut']
export type FeedbackProposedWeight = components['schemas']['ProposedWeightOut']
export type FeedbackWeightPreview = components['schemas']['WeightPreviewOut']
export type FeedbackDiagnosisOut = components['schemas']['FeedbackDiagnosisOut']

export type ClassificationReviewSideKind = components['schemas']['ClassificationReviewSideKind']
export type ClassificationReviewPurpose = components['schemas']['ClassificationReviewPurpose']
export type ClassificationReviewPhase = components['schemas']['ReviewPhase']
export type ClassificationVerdict = components['schemas']['ClassificationVerdict']
export type ClassificationReviewVerdictIn = components['schemas']['ReviewVerdictIn']
export type ClassificationReviewUserOut = components['schemas']['ReviewUserOut']
export type ClassificationReviewSampleSizeOut = components['schemas']['ReviewSampleSizeOut']
export type ClassificationReviewKindOptionOut = components['schemas']['ReviewKindOptionOut']
export type ClassificationReviewCloudModelOptionOut =
  components['schemas']['ReviewCloudModelOptionOut']
export type ClassificationReviewEyeMappingOptionOut =
  components['schemas']['ReviewEyeMappingOptionOut']
export type ClassificationReviewOptionsOut = components['schemas']['ClassificationReviewOptionsOut']
export type ClassificationReviewSideEstimateOut = components['schemas']['ReviewSideEstimateOut']
export type ClassificationReviewEstimateOut =
  components['schemas']['ClassificationReviewEstimateOut']
export type ClassificationReviewSideIn = components['schemas']['ReviewSideIn']
export type ClassificationReviewCreateBody = components['schemas']['ReviewCreate']
export type ClassificationReviewCreatedOut = components['schemas']['ReviewCreatedOut']
export type ClassificationReviewSideOut = components['schemas']['ReviewSideOut']
export type ClassificationReviewSidesOut = components['schemas']['ReviewSidesOut']
export type ClassificationReviewPurposeCountsOut = components['schemas']['ReviewPurposeCountsOut']
export type ClassificationReviewVerdictCountsOut = components['schemas']['ReviewVerdictCountsOut']
export type ClassificationReviewListItemOut = components['schemas']['ReviewListItemOut']
export type ClassificationReviewDetailOut = components['schemas']['ReviewDetailOut']
export type ClassificationReviewCaseSideOut = components['schemas']['ReviewCaseSideOut']
export type ClassificationReviewCaseOut = components['schemas']['ReviewCaseOut']
export type ClassificationReviewCasesOut = components['schemas']['ReviewCasesOut']
export type ClassificationReviewVerdictOut = components['schemas']['ReviewVerdictOut']

/* ===== Oberflächen-eigen ===== */

/**
 * Die Wahl des Nutzers beim Auslösen: "wie im Projekt eingestellt" oder "nur lokal".
 *
 * Der Name ist derselbe wie im Anfragekörper, damit Anfrage und Antwort nicht zwei Vokabulare
 * führen. Cloud und Eye sind keine Anfragewege, sondern Ergebnisse der im Projekt gespeicherten
 * Wahl (`ClassificationPath`).
 */
export type ClassificationWay = 'project' | 'local'

/**
 * Der WIRKSAME Weg eines Laufs - vom `ClassificationWay` bewusst getrennt: ein Feld, das beide
 * Zustände mischte, machte "so eingestellt, aber lokal gelaufen" unlesbar.
 */
export type ClassificationPath = NonNullable<
  components['schemas']['CriterionScoringRunSummary']['mode']
>

/**
 * Das Statusvokabular der Scan-Läufe plus `never` ("nie gelaufen"). Eine Ableitung, keine zweite
 * Literalliste: ein zusätzlicher Serverwert wird an der behandelnden Stelle zum Typfehler.
 */
export type ScanStatusLabel = components['schemas']['ScanStatus'] | 'never'

/** Die beiden Bildvarianten, die `GET /photos/{photo_id}/image` ausliefert. */
export type PhotoVariant = 'thumbnail' | 'display'

/** Die beiden Cloud-Zwecke (Anzeige-Ableitung von `CloudVisionPhase`). */
export type CloudVisionPurpose = components['schemas']['CloudVisionPhase']

/**
 * Die Kostenzwecke der Statistik: die beiden Cloud-Zwecke plus `review`. Eigener Name, weil
 * `review` kein Cloud-Aufruf ist und `CloudVisionPhase` an allen Aufrufstellen der Cloud-Läufe
 * unangetastet bleiben muss.
 */
export type StatsCostPurpose = components['schemas']['CostPurpose']

/**
 * Das Motivset. Die Menge ist fachlich geschlossen, der Typ bleibt aber bewusst `string`: das Set
 * kommt zur Laufzeit über `GET /motifs` vom Server, eine hier gespiegelte Union wäre eine dauerhaft
 * driftende zweite Liste. Ein unbekannter Schlüssel wird über den generischen Fallback von
 * `utils/motifLabels.ts` dargestellt, ohne Absturz.
 */
export type MotifKey = string

/** Der Grund eines Vorschlags - der Server schreibt ausschließlich diese beiden Werte. */
export type SuggestionReason = components['schemas']['SuggestionOut']['reason']

/**
 * Der Grund eines Ausschuss-Eintrags. Der dritte Wert steht NUR am Ausschuss-Eintrag: Ein Lauf,
 * der `suggested_status` und `duplicate_of` zurücksetzt, lässt die Entscheidungszeile stehen.
 */
export type AusschussReason = components['schemas']['AusschussPhotoEntryOut']['reason']

/** Ein Eintrag der Ausschuss-Übersicht: Einzelaufnahme oder Stapel. */
export type AusschussEntryOut = components['schemas']['AusschussOut']['items'][number]

/** Das an den Namen gebundene Gesicht: gezeigt, gewählt-aber-nicht-gelernt, oder keine Angabe. */
export type PersonFace = components['schemas']['PhotoPersonOut']['face']

/** Die geschlossenen Sperrgründe einer Prüfungswahl; `no_consent` steht vor `no_api_key`. */
export type ClassificationReviewUnavailableReason =
  components['schemas']['ReviewKindOptionOut']['unavailable_reasons'][number]

/** Die Einheit einer Prüfungszählung, vom Server mitgeliefert. */
export type ClassificationReviewUnit = components['schemas']['ReviewPurposeCountsOut']['unit']

/**
 * Die camelCase-Parameter der Fotoliste. `personIds` wird als wiederholter Query-Schlüssel
 * `person_id` serialisiert; die Grenzen führt der Server.
 */
export type ListPhotosParams = {
  ratingStatus?: RatingFilter
  limit?: number
  offset?: number
  cameraId?: number
  personIds?: readonly number[]
}

/** Die camelCase-Parameter des Alternativen-Endpunkts. */
export type ListDraftAlternativesParams = {
  eventId: number
  photoId?: number
  limit?: number
  offset?: number
  /** Das Band: die Aufnahmeserie um das Bezugsbild, Fenster vom Server geschnitten. */
  series?: true
}

/** Die camelCase-Parameter des Ausschuss-Lesepfads. */
export type ListAusschussParams = {
  limit?: number
  offset?: number
  photoId?: number
  autoDecided?: boolean
}

/* --- Die Aufrufgrenze: Endpunktvorlage + getrennte Pfadparameter ------------------------------ */

type HttpMethode = 'get' | 'post' | 'put' | 'patch' | 'delete'
type Endpunkt = keyof paths
type Vorgang<E extends Endpunkt, M extends HttpMethode> = NonNullable<paths[E][M]>

type VorgangsParameter<E extends Endpunkt, M extends HttpMethode> =
  Vorgang<E, M> extends { parameters: infer P } ? P : never

/** `undefined` (aus einem optionalen `?: never`) gilt wie "nicht vorhanden". */
type Vorhanden<X> = [X] extends [undefined] ? never : X

type ParameterArt<
  E extends Endpunkt,
  M extends HttpMethode,
  Art extends 'path' | 'query',
> = Vorhanden<
  Art extends 'path'
    ? VorgangsParameter<E, M> extends { path?: infer X }
      ? X
      : never
    : VorgangsParameter<E, M> extends { query?: infer X }
      ? X
      : never
>

type AnfrageKoerper<E extends Endpunkt, M extends HttpMethode> = Vorhanden<
  Vorgang<E, M> extends { requestBody?: infer R }
    ? R extends { content: { 'application/json': infer B } }
      ? B
      : never
    : never
>

type Antworten<E extends Endpunkt, M extends HttpMethode> =
  Vorgang<E, M> extends { responses: infer R } ? R : never

type ErfolgsAntwort<E extends Endpunkt, M extends HttpMethode> = {
  [K in keyof Antworten<E, M>]: K extends 200 | 201 | 202 | 203 | 204 ? Antworten<E, M>[K] : never
}[keyof Antworten<E, M>]

type AntwortKoerper<A> = [A] extends [never]
  ? undefined
  : A extends { content: { 'application/json': infer J } }
    ? J
    : undefined

/**
 * Der Antwortkörper eines Endpunkts. Die eine Typaussage an der HTTP-Grenze leitet sich damit aus
 * `paths[Endpunkt][Methode]` ab; der Aufrufer kann sie nicht wählen.
 */
type Normalisiert<M extends string> = Lowercase<M> & HttpMethode

export type ApiAntwort<E extends Endpunkt, M extends string> = AntwortKoerper<
  ErfolgsAntwort<E, Normalisiert<M>>
>

/** Die Endpunkte, die eine Methode führen. Ein Endpunkt ohne die Methode ist kein Aufrufziel. */
export type ApiPfad<M extends HttpMethode> = {
  [E in Endpunkt]: [NonNullable<paths[E][M]>] extends [never] ? never : E
}[Endpunkt]

/**
 * Die Methoden, die ein Endpunkt führt. Eine fremde Methode ist ein Typfehler; die Schreibweise
 * (`put`/`PUT`) ist bedeutungslos - `paths` bleibt die Quelle der Menge.
 */
export type ApiMethode<E extends Endpunkt> = {
  [M in HttpMethode]: [NonNullable<paths[E][M]>] extends [never] ? never : M | Uppercase<M>
}[HttpMethode]

/** Endpunkte mit Pflicht-Pfadparametern - dort ist die Optionsangabe selbst Pflicht. */
export type ApiPfadMitParametern<M extends HttpMethode> = {
  [E in ApiPfad<M>]: [ParameterArt<E, M, 'path'>] extends [never] ? never : E
}[ApiPfad<M>]

/** Endpunkte ohne Pfadparameter - dort darf die Optionsangabe fehlen. */
export type ApiPfadOhneParameter<M extends HttpMethode> = {
  [E in ApiPfad<M>]: [ParameterArt<E, M, 'path'>] extends [never] ? E : never
}[ApiPfad<M>]

type PfadTeil<E extends Endpunkt, M extends HttpMethode> = [ParameterArt<E, M, 'path'>] extends [
  never,
]
  ? { pathParams?: never }
  : { pathParams: ParameterArt<E, M, 'path'> }

type AbfrageTeil<E extends Endpunkt, M extends HttpMethode> = [
  ParameterArt<E, M, 'query'>,
] extends [never]
  ? { query?: never }
  : VorgangsParameter<E, M> extends { query: unknown }
    ? { query: ParameterArt<E, M, 'query'> }
    : { query?: ParameterArt<E, M, 'query'> }

type KoerperTeil<E extends Endpunkt, M extends HttpMethode> = [AnfrageKoerper<E, M>] extends [never]
  ? { body?: never }
  : { body: AnfrageKoerper<E, M> }

/**
 * Die Optionen eines Aufrufs: Pfadparameter getrennt, Query und Anfragekörper typisiert. Ein
 * konkreter Pfad trifft keinen Endpunkt; ein fehlender Pfadparameter und ein `body` an einem
 * körperlosen Endpunkt sind Typfehler.
 */
export type ApiFetchOptions<E extends Endpunkt, M extends string> = PfadTeil<E, Normalisiert<M>> &
  AbfrageTeil<E, Normalisiert<M>> &
  KoerperTeil<E, Normalisiert<M>>
