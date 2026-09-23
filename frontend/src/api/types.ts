export type ScanStatus = 'running' | 'success' | 'failed'

export interface ScanSummary {
  status: ScanStatus
  started_at: string
  finished_at: string | null
  files_found: number
  // null solange die Enumerationsphase noch nicht abgeschlossen ist - unterscheidet sich
  // bewusst von 0 (leeres Projekt). Immer explizit `!== null`/`=== null` prüfen, nie truthy.
  total_files: number | null
  photos_added: number
  photos_updated: number
  photos_removed: number
  files_skipped: number
  error_message: string | null
}

export interface ScoringRunSummary {
  // Wird als scoring_run_id an POST /classify weitergereicht - Staleness-Guard bei einem
  // zwischenzeitlichen Re-Scan/Re-Scoring.
  id: number
  status: ScanStatus
  started_at: string
  finished_at: string | null
  photos_total: number
  photos_processed: number
  suggestions_found: number
  error_message: string | null
  // Ausschuss-Gate: null = noch nicht bestätigt.
  gate_confirmed_at: string | null
}

// Die VIER Teilschritte eines verketteten Klassifizierungslaufs, in genau dieser Reihenfolge.
//
// 'landmark' ist die Sehenswürdigkeits-Erkennung. 'ranking' (Kategorieableitung und Rangfolge)
// gehört fachlich zur Kriterien-Phase, läuft aber DANACH.
export type ClassificationPhase = 'remote_categories' | 'criteria' | 'landmark' | 'ranking'

// Ein Cloud-Teilschritt EINES Klassifizierungslaufs: während des Laufs die Fortschrittsanzeige,
// danach die Bilanz.
//
// Die Felder sind DURCHGÄNGIG `| null` und nicht optional (`?`): eine Auslassung an der
// Anzeigestelle soll ein Typfehler sein, kein stilles `undefined`. `null` heißt überall "nicht
// erfasst"/"unbekannt" - nie `0` und nie "kostenlos"; ein `?? 0` irgendwo im Pfad behauptete
// Kostenfreiheit für einen Lauf, der Geld ausgegeben hat.
export interface CloudPhaseSummaryOut {
  purpose: CloudVisionPhase
  photos_total: number | null
  // Abgesetzte Aufrufe (Erfolge UND Fehlschlaege) - bewegt sich waehrend des Laufs.
  photos_processed: number | null
  // Fehlgeschlagene Einzelaufrufe - bewegt sich ebenfalls waehrend des Laufs.
  failed_calls: number | null
  // Verwertete Antworten; steht erst am Phasenende fest, wie Tokens und Betrag.
  responses_used: number | null
  input_tokens: number | null
  output_tokens: number | null
  cost_usd: number | null
  model: string | null
  // Aus `model` abgeleitet; null = Modell nicht (mehr) in der Registry. Die Oberflaeche zeigt
  // dann die Modell-ID ALLEIN - nie einen geratenen Anbieter und nie einen
  // Konfigurationshinweis.
  provider: string | null
}

// Bewusst kein candidates_total/suggestions_found: der Job berechnet immer den vollen
// Rangfolge-Pool je Partition, und welche Fotos davon im Vorschlag stehen, sagt
// `selection_position` an der Rangzeile.
export interface CriterionScoringRunSummary {
  status: ScanStatus
  started_at: string
  finished_at: string | null
  photos_total: number
  photos_processed: number
  error_message: string | null
  // Diese Zusammenfassung beschreibt den GESAMTEN Klassifizierungslauf, nicht nur seine
  // Kriterien-Phase.
  //
  // `phase`: der gerade laufende Teilschritt; null = läuft nicht mehr (beendet, oder
  // Altlauf). Die Fortschrittszahlen der beiden Cloud-Teilschritte stehen in
  // `cloud_phases`, die der Kriterien-Phase hier.
  phase: ClassificationPhase | null
  // War die Cloud-Nutzung fuer DIESEN Lauf angefordert? false heisst "das Ergebnis kann keine
  // Cloud-Anreicherung enthalten" - Grundlage des entsprechenden Hinweises in der Oberflaeche.
  cloud_requested: boolean
  // Laufweite Zusammenfassung der Cloud-Probleme, null = keine. Ein gesetzter Wert heisst NICHT,
  // dass der Lauf fehlgeschlagen ist: der lokale Bewertungsanteil laeuft trotzdem vollstaendig
  // durch, das Ergebnis ist nur nicht (vollstaendig) angereichert.
  cloud_error_message: string | null
  // Die Bilanz DIESES Durchlaufs.
  //
  // `cloud_phases` in Ausfuehrungsreihenfolge (remote_category, dann landmark); ein Eintrag
  // entsteht, sobald die Phase betreten wurde. Eine LEERE LISTE heisst "dieser Durchlauf hatte
  // keinen Cloud-Teilschritt" - daran haengt die entsprechende Aussage der Bilanz.
  //
  // `estimated_cost_usd` ist die Schaetzung, mit der der Lauf gestartet wurde;
  // `cloud_cost_total_usd` die Summe der Ist-Betraege, serverseitig `null`, sobald ein Anteil
  // `null` ist.
  cloud_phases: CloudPhaseSummaryOut[]
  estimated_cost_usd: number | null
  cloud_cost_total_usd: number | null
  // Die geschaetzte Restdauer GENAU DES Teilschritts, den `phase` nennt - in Sekunden. Ein Feld,
  // keines je Teilschritt: es laeuft immer genau einer.
  //
  // `null` heisst "noch nicht abschaetzbar", NIE "keine Restdauer" und nie "sofort fertig" - die
  // Oberflaeche schreibt dort sichtbar hin, dass die Angabe noch fehlt, statt ein leeres Feld zu
  // zeigen. `null` steht auch immer bei `ranking` (keine gezaehlte Menge) und bei jedem beendeten
  // Lauf. Die Spanne entsteht aus dieser Zahl erst hier im Frontend (utils/classificationEta.ts).
  //
  // PFLICHTFELD ohne Vorgabewert - dann erzwingt `tsc` die Ergaenzung jeder lokalen Testfabrik,
  // und es braucht keinen Test ueber deren Vollzaehligkeit.
  phase_remaining_seconds: number | null
}

export interface ProjectOut {
  id: number
  name: string
  opencloud_drive_id: string
  opencloud_path: string
  created_at: string
  last_scan: ScanSummary | null
  last_scoring_run: ScoringRunSummary | null
  last_criterion_scoring_run: CriterionScoringRunSummary | null
  // Globales Feature-Flag, nicht projektspezifisch.
  category_selection_enabled: boolean
  // Projektweiter Einwilligungs-Schalter für produktive Cloud-Vision-Datenflüsse - Default
  // false, consent_at null solange nicht aktiviert. Er gated BEIDE Cloud-Anteile.
  cloud_vision_detection_enabled: boolean
  cloud_vision_consent_at: string | null
  // Der Richtwert des Auswahlvorschlags. `null` heißt "nicht selbst eingestellt", NICHT "kein
  // Richtwert" - wirksam ist dann `effective_selection_target`. Das Frontend leitet die wirksame
  // Zahl nie selbst ab; sie kommt fertig vom Server, weil die Ableitung dort an genau einer
  // Stelle lebt und mit dem Bildbestand mitwächst.
  selection_target: number | null
  effective_selection_target: number
  // Bestandszahlen des Projekts (ADR 0103). PFLICHTFELDER ohne Vorgabewert: dann erzwingt `tsc`
  // die Ergaenzung jeder lokalen `project()`-Testfabrik, und es braucht keinen Test ueber deren
  // Vollzaehligkeit.
  //
  // `photo_count === 0` ist eine Aussage ("keine Fotos"), die beiden `null` sind ihre Abwesenheit
  // ("kein Zeitraum bekannt"). Die Anzeige unterscheidet sichtbar: "0 Fotos" gegen den Strich
  // `NOT_AVAILABLE`. Nie ein `?? 0` im Pfad.
  photo_count: number
  taken_at_earliest: string | null
  taken_at_latest: string | null
}

// Kostenschätzung vor dem Lauf, über ALLE Cloud-Anteile, die die Checkbox am Auslöser
// freigibt. `candidate_count` ist die Summe der beiden Einzelanteile und bleibt die eine
// anzuzeigende Zahl. Je Einzelanteil gilt: `candidate_count === null` heißt "nicht
// verlässlich schätzbar" (Landmark-Anteil vor dem ersten erfolgreichen Durchlauf), NIE
// "null Fotos"; `estimated_cost_usd === null` heißt "kein Preis hinterlegt ODER Anteil
// unbekannt", nie "kostenlos".
export interface ClassificationEstimatePartOut {
  candidate_count: number | null
  estimated_cost_usd: number | null
}

export interface ClassificationEstimateOut {
  // Summe der BEKANNTEN Anteile - bei unbekanntem Landmark-Anteil eine untere Schranke.
  candidate_count: number
  remote_categories: ClassificationEstimatePartOut
  landmark: ClassificationEstimatePartOut
  provider: string
  // Das Modell, auf das sich die Schätzung bezieht - `provider` allein benennt die
  // Preisgrundlage nicht eindeutig.
  model: string
  // `| null` heißt "für das eingestellte Modell ist kein Preis hinterlegt", NIE 0. Ein
  // `?? 0` an dieser Stelle behauptete Kostenfreiheit - `tsc` erzwingt die Behandlung an der
  // Anzeigestelle.
  price_per_image_usd: number | null
  estimated_cost_usd: number | null
}

export interface BrowseEntry {
  name: string
  path: string
}

// Rekursive Bilddatei-Anzahl (mit Obergrenze) pro direktem Unterordner, wie von
// GET /opencloud/folder-counts geliefert. SICHERHEIT: bewusst kein Freitext-/Meldungsfeld -
// error=true transportiert kein str(exc) vom Backend.
export interface FolderCountOut {
  path: string
  count: number
  at_limit: boolean
  error: boolean
}

/**
 * Die ALBUMENTSCHEIDUNG eines Nutzers - zwei Werte, kein dritter. Sie sagt, ob das Bild ins
 * Album soll, und ist keine Aussage über seine Güte.
 *
 * `favorite` gehört ausdrücklich nicht mehr dazu (ADR 0098): Die Auszeichnung ist eine eigene,
 * unabhängige Angabe und kann gleichzeitig mit einer Albumentscheidung gesetzt sein.
 */
export type RatingStatus = 'album_worthy' | 'rejected'
/** Die Einträge des Rasterfilters. `favorite` filtert auf das eigene Kennzeichen, nicht auf
 * einen Status; `unrated` heißt "keine Albumentscheidung". */
export type RatingFilter = 'unrated' | 'suggested' | 'favorite' | RatingStatus
export type PhotoVariant = 'thumbnail' | 'display'

export interface RatingOut {
  user_id: number
  username: string
  /** `null` heißt "keine Albumentscheidung" - auch bei vorhandener Zeile, die nur das
   * Favoriten-Kennzeichen trägt. */
  status: RatingStatus | null
  favorite: boolean
}

/**
 * Die Antwort der beiden schreibenden Bewertungs-Endpunkte - der Zustand der EIGENEN Zeile nach
 * dem Schreibvorgang, nicht ein Eintrag aus `PhotoOut.ratings[]`.
 *
 * `updated_at` ist `null`, wenn die Zeile dabei geleert und damit gelöscht wurde.
 */
export interface RatingWriteOut {
  photo_id: number
  /** Der Nutzer, für den geschrieben wurde — serverseitig aus dem Token, nie aus der Anfrage.
   * Er trägt das Fortschreiben des betroffenen Eintrags im Cache der Entwurfsabfrage: ein
   * Eintrag von `PhotoOut.ratings[]` trägt `user_id`, und ohne dieses Feld müsste der Client
   * eine Id erfinden. */
  user_id: number
  status: RatingStatus | null
  favorite: boolean
  updated_at: string | null
}

export type SuggestionReason = 'duplicate' | 'low_quality'

// Automatischer Vorschlag aus PhotoScore, bewusst getrennt von RatingOut/ratings[] - ein
// Vorschlag ist strukturell nie eine Bewertung, sondern wird erst durch aktive Bestätigung
// (PUT /photos/{id}/rating) zu einer. Der Kontext der Rangfolge lebt im eigenständigen
// `PhotoOut.ranking`-Feld, nicht hier.
export interface SuggestionOut {
  status: RatingStatus
  reason: SuggestionReason
  duplicate_of: number | null
  sharpness: number
  exposure: number
  cluster_key: string | null
  computed_at: string
}

/**
 * Die Entscheidung des PROJEKTS über EINE Aufnahme des Ausschusses (ADR 0104).
 *
 * AUSDRÜCKLICH KEIN `RatingStatus`: Jenes ist die Albumentscheidung eines Nutzers. Hier steht die
 * andere Frage — ob die Aufnahme den Ausschuss-Schritt überlebt. Ein geteilter Wertevorrat machte
 * die beiden an jeder Lesestelle verwechselbar.
 *
 * Es gibt keinen dritten Wert: Die Ansicht zeigt seit ADR 0111 die Auswertung des
 * Überlebens-Prädikats, nicht die Entscheidungszeile — „noch nicht entschieden" ist kein
 * darstellbarer Zustand mehr.
 */
export type DuplicateDecision = 'keep' | 'discard'

/**
 * Ein Mitglied der Duplikat-Gruppe. Der Zustand reist NEBEN dem Foto, nicht an ihm: `PhotoOut`
 * trägt kein Feld dafür, weil er außerhalb dieser Ansicht keine Rolle hat.
 *
 * `effective_decision` ist das, was ohne weiteres Zutun eintritt — nicht die gespeicherte Zeile.
 * Ob ein Zustand vom System oder vom Nutzer stammt, geht daraus nicht hervor und wird nicht
 * angezeigt.
 *
 * **Dieser Wert wird nie aus `PhotoOut.suggestion` abgeleitet** (ADR 0111 Punkt 1, untersagt):
 * Jenes Feld fällt bei eigener Albumbewertung und bei getroffener Entscheidung auf `null`, und
 * eine TypeScript-Fassung des Prädikats sieht der Wächter über die Verwendungsstellen nicht — er
 * liest nur `backend/src`. Bei Verletzung zeigt die Ansicht einen anderen Zustand, als der
 * Ausschuss-Schritt anwendet, ohne Fehler und ohne Meldung.
 *
 * `keep_possible === false` heißt: Kein Wert der Entscheidungszeile ändert diesen Zustand. Der
 * Grund reist nicht mit — er folgt aus der Bedingung selbst, und die Oberfläche rendert dort einen
 * festen Text.
 */
export interface DuplicateGroupItem {
  photo: PhotoOut
  effective_decision: DuplicateDecision
  keep_possible: boolean
}

/**
 * Die Antwortform ALLER DREI Endpunkte der Vergleichsansicht — Lesepfad wie beide Schreibwege.
 * Ein Schreibvorgang liefert damit denselben vollständigen Stand zurück, den ein erneutes Laden
 * liefern würde.
 *
 * `position`/`total` sind 1-basiert mit `1 <= position <= total` und beziehen sich auf ALLE
 * Duplikat-Gruppen des Projekts — eine vollständig entschiedene zählt weiter mit.
 *
 * `previous_photo_id`/`next_photo_id` tragen die Repräsentanten-Id der jeweils benachbarten
 * Gruppe, `null` am Rand. Die Ansicht schaltet dort auf `disabled`, statt die Schaltfläche
 * wegzulassen.
 */
export interface DuplicateGroupOut {
  items: DuplicateGroupItem[]
  position: number
  total: number
  previous_photo_id: number | null
  next_photo_id: number | null
}

/**
 * Die Auskunft für den Einstieg in den Durchgang.
 *
 * `first_photo_id` ist `null`, wenn es keine Gruppe gibt — der Einstieg wird dann gar nicht
 * gerendert, statt auf eine leere Ansicht zu führen.
 */
export interface DuplicateGroupIndexOut {
  total: number
  first_photo_id: number | null
}

/**
 * EIN Eintrag der Ausschuss-Übersicht (Spec 0525, `api/photos.py::AusschussEntryOut`).
 *
 * `reason` ist der Grund der Markierung und kommt vom Server, nicht aus einer TypeScript-Ableitung
 * (Auflage S7): `duplicate` genau dann, wenn das Foto ein Duplikat ist, sonst `low_quality`. Der
 * Grund ist damit unterscheidbar, statt ein Sammelzustand zu sein (AK4) — Grund und Entscheidung
 * sind zwei verschiedene Aussagen über dieselbe Aufnahme.
 *
 * `decision` ist der GESPEICHERTE Zeilenwert aus `photo_duplicate_decisions`, ausdrücklich NICHT
 * die Auswertung des Überlebens-Prädikats (ADR 0111 Punkt 1): Diese Übersicht zeigt den
 * Sichtungsfortschritt, und ein unwirksames `keep` (Unschärfe-Ablehnung ohne Gruppe) bleibt als
 * gespeicherte Handlung sichtbar. `null` heißt „noch nicht entschieden" — der einzige der drei
 * Zustände, in dem es keinen Rückweg gibt, weil er noch nie verlassen wurde.
 *
 * `group_anchor_photo_id` ist der Anker der Duplikat-Gruppe, in der diese Aufnahme liegt, oder
 * `null`. Die Detailansicht löst die Serie darüber auf — nicht über das angeklickte Foto, damit
 * die Gruppe dieselbe bleibt, egal welches Mitglied man geöffnet hat.
 *
 * `keep_possible` ist die WIRKSAMKEIT des angebotenen „behalten" und kommt vom Server
 * (`duplicates.py::keep_possible_for`, Auflage S7). Aus `reason` ist sie **nicht** ableitbar: Ein
 * Eintrag, dessen Entscheidungszeile einen Lauf überlebt hat, in dem `suggested_status` und
 * `duplicate_of` zurückgesetzt wurden, trägt `low_quality` und trotzdem `true`. Eine zweite
 * Ableitung hier nähme dem Nutzer dort die einzige Handlung, die die Aufnahme zurückholt.
 */
export interface AusschussEntryOut {
  photo: PhotoOut
  reason: SuggestionReason
  decision: DuplicateDecision | null
  group_anchor_photo_id: number | null
  keep_possible: boolean
}

/**
 * Die Antwort des Ausschuss-Lesepfads: der Bestand, seine Größe und die Zahl der offenen
 * Vorschläge.
 *
 * `total` ist die Größe des Gesamtbestands, nicht der geladenen Seite; `open_count` ist
 * projektweit und von `limit`/`offset` unabhängig — es ist die Zahl, die der Bestätigungsbutton
 * trägt. Beide bleiben auch im Filterzweig (`photo_id`) projektweit, `items` trägt dann genau den
 * gefilterten Eintrag oder nichts.
 */
export interface AusschussOut {
  items: AusschussEntryOut[]
  total: number
  open_count: number
}

// Das Motivset (specs/features/0427-motive-mit-staerke.md). Die Menge ist fachlich
// GESCHLOSSEN (acht Einträge, backend motifs.py::MOTIF_REGISTRY), der TypeScript-Typ bleibt
// aber bewusst `string`: das Set kommt zur Laufzeit über `GET /motifs` vom Server, eine hier
// gespiegelte Union wäre eine dauerhaft driftende zweite Liste. Ein unbekannter Schlüssel wird
// über den generischen Fallback von `utils/motifLabels.ts` dargestellt, ohne Absturz.
export type MotifKey = string

// Ein Eintrag des festen Achter-Sets, wie ihn GET /motifs liefert - in ANZEIGEREIHENFOLGE der
// Server-Registry, auf jedem Foto dieselbe. KEIN Ordnungsfeld: eine Zahl daneben wäre die
// abgeschaffte Vorrangreihenfolge zurück.
export interface MotifOut {
  key: MotifKey
  display_name: string
  definition: string
  delimitation: string
  /** Ob dieses Motiv OHNE Cloud-Aussage überhaupt beurteilbar ist. Kommt vom Server, damit die
   * Oberfläche „0 weil nicht zu sehen" von „0 weil nicht angesehen" unterscheiden kann, ohne die
   * Signalliste des Backends zu spiegeln. */
  locally_assessable: boolean
}

/** Die beiden Anzeigebänder der STATISTIK, inklusiv verglichen. Kommen vom Server, damit das
 * Frontend sie nicht hinterlegt. Ausdrücklich KEINE Zugehörigkeitsschwelle - außerhalb der
 * Statistiktabelle erscheint kein Bandwort. */
export interface MotifStrengthBandsOut {
  strong: number
  medium: number
}

export interface MotifSetOut {
  items: MotifOut[]
  strength_bands: MotifStrengthBandsOut
}

/** Die Kopfzeile des Stärkevektors eines Fotos. `null` an `PhotoOut.motif_assessment` heißt „noch
 * nicht klassifiziert" - unterscheidbar von „nichts erkannt" (Kopfzeile vorhanden, alle acht
 * Stärken niedrig). `provider` ist `null` bei `source === 'local'`. `excluded_document` lässt sich
 * von Hand NICHT korrigieren. */
export interface MotifAssessmentOut {
  source: 'cloud' | 'local'
  provider: string | null
  excluded_document: boolean
  computed_at: string
}

/** Die WIRKSAME Stärke eines Motivs samt Korrekturzustand. `strength` trägt die Korrektur bereits
 * eingerechnet - das Frontend rechnet nichts nach. `correction` ist `null` ohne Korrekturzeile;
 * auf `!== null` prüfen, nie auf Falsyness (`false` ist eine Aussage). */
export interface MotifStrengthOut {
  /** `key` wie in `MotifOut` - dieselbe Sache heißt an beiden Stellen gleich. */
  key: MotifKey
  strength: number
  correction: boolean | null
  /** Trägt das Foto dieses Motiv? Die AUSSAGE DES SERVERS; die Grenze wohnt in
   * `selection.py::motif_is_present` und verlässt das Backend nie als Zahl. Für diese Frage wird
   * `strength` NICHT gelesen — ein eigener Vergleich hier wäre die zweite Stelle, an der über
   * Zugehörigkeit entschieden wird, und liefe bei der nächsten Kalibrierung auseinander. */
  present: boolean
}

// Antwort von PUT /photos/{id}/motif-corrections/{motif_key} - der gesetzte Wert wird direkt
// zurückgegeben, analog PUT /photos/{id}/rating.
export interface MotifCorrectionOut {
  photo_id: number
  motif_key: MotifKey
  applies: boolean
}

/**
 * Der geschriebene Zustand BEIDER Bewertungszeilen eines Austauschs (Spec 0432).
 *
 * Beide, damit die Entwurfsansicht wie bisher in ihre bereits geladene Liste fortschreibt statt
 * neu zu laden — ein Neuladen risse die gerade getauschte Kachel aus der Liste.
 */
export interface DraftExchangeOut {
  /** Das aufgenommene Bild. */
  taken: RatingWriteOut
  /** Das ersetzte, damit gestrichene Bild. */
  struck: RatingWriteOut
}

// Die Rangzeile eines Fotos aus der Kriterien-/Rangfolgen-Pipeline. Ein Foto hat je Lauf
// GENAU EINE davon - die Partition ist allein das Event.
export interface RankingOut {
  event_id: number
  /** Der QUALITÄTSWERT des Fotos auf [0, 1] - `null` heißt „kein Modellurteil, also kein Wert"
   * (Cloud-Freigabe fehlt projektweit, oder der Aufruf für dieses Foto ist fehlgeschlagen). Auf
   * `!== null` prüfen, NIE auf Falsyness: `0` ist ein gültiger Wert, und ein `?? 0` oder ein
   * Falsyness-Filter verliert ihn lautlos. Es gibt keinen Rückfall auf einen lokal gebildeten
   * Wert. */
  rank_score: number | null
  /** `null` gemeinsam mit `rank_score` - ein Foto ohne Qualitätswert hat keinen Rang. Die Zeile
   * „Rang M von N" entfällt dann vollständig; „Rang – von 12" wäre eine Rangaussage über ein
   * Foto ohne Rang. */
  rank_position: number | null
  /** Trägt der LAUF dieses Foto vor? Lauf-global, ohne jeden Nutzerbezug, auf allen Lesepfaden
   * gesetzt. `false` bei gleichzeitiger eigener Entscheidung „Im Album" ist der Zustand
   * „aufgenommen, vom aktuellen Vorschlag nicht getragen". */
  proposed: boolean
  // Größe der GESAMTEN Event-Partition (nicht nur des Vorschlags), für "Rang M von N"
  // im Info-Popover.
  partition_size: number
  /** Der Platz dieses Fotos in der angezeigten Auswahl seines Events. `null` heisst: gehoert
   * nicht zur angeforderten Auswahl, oder es wurde gar keine angefordert. AUSDRUECKLICH NICHT
   * `rank_position` - jene ist die lauf-globale Rangaussage des Info-Popovers. Auf `!== null`
   * pruefen, nie auf Falsyness. */
  curation_position: number | null
}

// Herkunft eines Kriterien-Werts (backend models.py::CriterionSource) - aktuell nur zur Anzeige
// im Info-Popover, kein Frontend-Verhalten haengt vom konkreten Wert ab.
export type CriterionSource = 'local_heuristic' | 'local_ml' | 'cloud'

// Ein einzelner, bereits normierter Kriterien-Wert eines Fotos. Best-effort: nur Kriterien,
// für die tatsächlich ein Wert berechnet wurde, sind enthalten - kein 0/Platzhalter für
// fehlende.
export interface CriterionScoreOut {
  criterion_key: string
  display_name: string
  value: number
  source: CriterionSource
  // `presence_threshold is not None` der Backend-Registry und die ALLEINIGE Grundlage der
  // Gliederung in die Blöcke "Qualität" (false) / "Bildinhalt" (true) - im Frontend wird dazu
  // bewusst keine Merkmalsliste gepflegt. Die Schwelle selbst kommt nicht mit: sie ist die
  // Vorfilter-Grenze des Cloud-Aufrufs und hat in der Oberfläche nichts zu entscheiden.
  has_presence_threshold: boolean
}

// Ein frei formuliertes, auf einen kanonischen Eintrag aufgelöstes Feinlabel - immer eine
// Liste (0-2 Einträge), nie null. Reine ZUSATZINFORMATION am Foto, keine Kategoriequelle.
//
// SICHERHEITSHINWEIS: `display_name`/`raw_label` sind freier, extern erzeugter LLM-Text
// (backend zeichensaniert). Sie dürfen ausschließlich als regulärer React-Textknoten
// gerendert werden - nie über dangerouslySetInnerHTML, nie als HTML-String-Prop, nie in
// href/src/style.
export interface FineLabelOut {
  canonical_key: string
  display_name: string
  raw_label: string
  provider: string
}

// Häufigkeit eines Feinlabels IN EINEM PROJEKT (GET /projects/{id}/fine-labels), absteigend
// sortiert - macht sichtbar, welche Kategorie im festen Set gegebenenfalls fehlt.
export interface FineLabelCountOut {
  canonical_key: string
  display_name: string
  photo_count: number
}

// Die beiden unabhängigen Cloud-Vision-Läufe, für die pro Foto genau einer von sechs Zuständen
// angezeigt wird. Derselbe Typ schlüsselt auch die Cloud-Teilschritte eines Laufs
// (`CloudPhaseSummaryOut.purpose`).
export type CloudVisionPhase = 'landmark' | 'remote_category'

// Read-time aus bereits vorhandenen Signalen abgeleitet (backend api/photos.py::
// _cloud_vision_status_out) - kein voller Status pro Foto persistiert. `no_result` tritt nur
// bei `phase === 'landmark'` auf: Remote-Kategorie kennt keinen "nichts gefunden"-Fall,
// ein Erfolg schreibt immer 1-3 Zeilen.
export type CloudVisionStatus =
  'not_run' | 'not_candidate' | 'consent_disabled' | 'error' | 'no_result' | 'result'

// Ein Eintrag von `PhotoOut.cloud_vision_status` - immer genau zwei (einer je CloudVisionPhase),
// feste Reihenfolge [landmark, remote_category].
export interface CloudVisionStatusOut {
  phase: CloudVisionPhase
  status: CloudVisionStatus
  // Nur bei status === 'error' gesetzt.
  error_message: string | null
  // Nur bei status in {'error', 'no_result', 'result'} gesetzt.
  attempted_at: string | null
}

/** Der Ort DIESES Fotos, in voller EXIF-Präzision (keine serverseitige Rundung).
 *
 * `source` ist ein SICHERHEITSMERKMAL, kein Anzeigedetail: der Trennabstand der
 * Clusterbildung begrenzt den SCHRITT zwischen zwei aufeinanderfolgenden Fotos, nicht den
 * DURCHMESSER eines Clusters - eine `"derived"`-Koordinate kann beliebig weit von der
 * tatsächlichen Aufnahmestelle entfernt liegen. Sie ist eine Schätzung, nie eine Messung;
 * kein künftiger Verbraucher (Kartenansicht, Export) darf `derived` wie `exif` behandeln. */
export interface PhotoLocation {
  lat: number
  lon: number
  source: 'exif' | 'derived'
}

/** Der bereits AUFGELÖSTE Ort des EVENTS - auf jedem Foto desselben Events identisch, `null`
 * ohne jede Ortsinformation.
 *
 * Der Server liefert den fertigen ZUSTAND, nicht die Rohdaten für eine Rangfolge. Das
 * Frontend bildet die Rangfolge (Sehenswürdigkeit -> Koordinate -> mehrere Orte) NICHT nach.
 * `kind: 'multiple'` trägt strukturell keine Koordinate.
 *
 * `kind` benennt die STUFE, nicht den einzigen Text des Events: Seit Spec 0514 steht
 * `landmark_name` NEBEN `place_name`, statt ihn zu verdrängen -
 * `utils/timeOfDay.ts::eventPlaceName` setzt beide zur Form "<Name>, <Ort>" zusammen. Verdrängt
 * bleibt allein die KOORDINATENSTUFE: `kind: 'coordinate'` erscheint nie als Name, und ohne
 * Ortsnamen fällt ein Event auf "Position N" zurück. `kind` bleibt `'landmark'` auch dann, wenn
 * daneben ein Ortsname steht.
 *
 * `landmark_name` ist freier, extern erzeugter LLM-Text: ausschließlich als regulärer
 * React-Textknoten rendern - nie `dangerouslySetInnerHTML`, nie als HTML-String-Prop, nie in
 * `href`/`src`/`style`, nie als React-`key` (dieselbe Auflage wie bei
 * `FineLabelOut.raw_label`). Seit Spec 0514 trägt ihn ein Event nur, wenn ihn mindestens ein
 * Zehntel seiner Fotos bezeugt (Backend `events.LANDMARK_MIN_SHARE`); ein zu schwach gestützter
 * Name ist von "nie erkannt" nicht zu unterscheiden und hat keinen eigenen Anzeigezustand. */
export interface EventPlace {
  kind: 'landmark' | 'coordinate' | 'multiple'
  landmark_name: string | null
  lat: number | null
  lon: number | null
}

/** Das Event, zu dem dieses Foto im letzten erfolgreichen Lauf gehört.
 *
 * Nummer, Zeitspanne und Name stehen in der Zeile des Events und hängen damit NICHT davon ab,
 * welche Fotos eine Antwort gerade enthält - anders als bei der früheren Cluster-Überschrift, die
 * aus den sichtbaren Fotos aggregiert wurde.
 *
 * `place_name` ist der aufgelöste Ortsname dieses Events, `null` heißt "keiner". Er steht bewusst
 * NEBEN `place` und nicht darin: `place` ist `null`, sobald der Server die Ortsstufe nicht kennt,
 * und der Name fiele dort still mit. Die Form "Ort, Viertel" kommt FERTIG vom Server.
 *
 * Und er steht seit Spec 0514 auch NEBEN dem Sehenswürdigkeitsnamen: Der Server setzt die
 * Überschrift NICHT zusammen - `utils/timeOfDay.ts::eventPlaceName` verbindet beide Teile. Eine
 * zweite Quelle derselben Form liefe mit ihr auseinander.
 *
 * Es ist freier, extern erzeugter Text und trägt dieselbe Auflage wie `landmark_name`:
 * ausschließlich als regulärer React-Textknoten rendern - nie `dangerouslySetInnerHTML`, nie als
 * HTML-String-Prop, nie in `href`/`src`/`style`, nie als React-`key`. Die Schlüssel-Auflage ist
 * hier nicht nur XSS-Hygiene: Gleichnamigkeit ist der Normalfall dieser Überschrift, und ein
 * doppelter Schlüssel bringt die Listenabgleichung durcheinander. */
export interface EventOut {
  id: number
  position: number
  started_at: string
  ended_at: string
  place: EventPlace | null
  place_name: string | null
}

/** Die Kamera eines Fotos. `label` kommt vom SERVER - eine Stelle entscheidet, wie eine Kamera
 * heißt, und der Wert ist dort bereits von unsichtbaren Zeichen befreit. Nie aus `make`/`model`
 * im Frontend zusammensetzen; die Felder gibt es hier gar nicht. */
export interface CameraOut {
  id: number
  label: string
}

/** Ein Eintrag der Kameraliste eines Projekts. `photo_count` zählt ausschließlich die Fotos
 * DIESES Projekts von dieser Kamera. */
export interface ProjectCameraOut {
  id: number
  label: string
  photo_count: number
  offset_minutes: number
}

/** Ein errechneter Versatz-Vorschlag. Er GILT NOCH NICHT - erst ein `PUT` auf den
 * Versatz-Endpunkt setzt ihn. */
export interface CameraTimeOffsetSuggestionOut {
  camera_id: number
  camera_label: string
  offset_minutes: number
  photo_taken_at_original: string
  reference_taken_at: string
}

export interface PhotoOut {
  id: number
  relative_path: string
  /** Die WIRKSAME (korrigierte) Aufnahmezeit - derselbe Feldname wie zuvor, neue Bedeutung:
   * seit Spec 0426 trägt er die um den Kamera-Versatz verschobene Zeit. Jede Anzeige einer
   * Aufnahmezeit liest diesen Wert. */
  taken_at: string
  /** Die AUFGEZEICHNETE Zeit. Nur im Korrekturfall anzuzeigen - bei `time_offset_minutes === 0`
   * ist sie gleich `taken_at` und eine zweite Zeile wäre eine Aussage ohne Inhalt. */
  taken_at_original: string
  /** Die Differenz der beiden Zeiten in ganzen Minuten. `0` heißt "nicht korrigiert" - dann
   * erscheint weder Kennzeichnung noch zweite Zeile. */
  time_offset_minutes: number
  /** `null` heißt "Kamera nicht bestimmbar" - ein regulärer Zustand, kein Fehler. */
  camera: CameraOut | null
  /** Breite geteilt durch Höhe des GEZEIGTEN Bildes (nach EXIF-Orientierung). `null` heißt "nicht
   * bekannt" und ist ein regulärer Zustand, kein Fehler - das Raster plant ein solches Foto mit
   * 3:2 ein und passt es in seinem Feld ein (`utils/justifiedRows.ts`). Optional deklariert wie
   * `ranking`/`location`: `undefined` und `null` bedeuten an jeder Lesestelle dasselbe. */
  aspect_ratio?: number | null
  ratings: RatingOut[]
  suggestion: SuggestionOut | null
  /** Die Rangzeile des Fotos im letzten erfolgreichen Lauf, in beiden Query-Modi - `null`,
   * solange kein erfolgreicher Lauf existiert oder das Foto darin keine Zeile hat.
   *
   * EIN Feld und keine Liste: ein Foto steht je Lauf in genau einer Zeile, seit die Partition
   * allein das Event ist. Optional deklariert wie `location`/`event`: `undefined` und `null`
   * bedeuten an jeder Lesestelle dasselbe. */
  ranking?: RankingOut | null
  criterion_scores: CriterionScoreOut[]
  // Immer eine Liste (0-2 Einträge), nie null.
  fine_labels: FineLabelOut[]
  // Immer genau 2 Einträge, feste Reihenfolge [landmark, remote_category].
  cloud_vision_status: CloudVisionStatusOut[]
  /** Beide Felder liefert die API IMMER (auf allen Lesepfaden, `null` ohne Ortsinformation).
   * Hier trotzdem OPTIONAL deklariert: `undefined` und `null` bedeuten an jeder Lesestelle
   * dasselbe - kein Ort. */
  location?: PhotoLocation | null
  event?: EventOut | null
  /** `null` heißt „noch nicht klassifiziert": dann ist `motifs` LEER und trägt ausdrücklich NICHT
   * acht Einträge mit Wert 0. Auf `=== null` prüfen und an der Stelle der Liste einen Satz
   * zeigen - acht Nullzeilen sind von „nichts erkannt" nicht zu unterscheiden. */
  motif_assessment?: MotifAssessmentOut | null
  /** Immer eine Liste, nie `null` (analog `ratings`): leer ohne Kopfzeile, sonst genau acht
   * Einträge in Registry-Reihenfolge - auch bei unvollständigen Stärkezeilen. Die Stärke wird je
   * Schlüssel nachgeschlagen, NIE über den Index der Antwortliste.
   *
   * Optional deklariert wie `location`/`event`: `undefined` und `[]` bedeuten an jeder Lesestelle
   * dasselbe. */
  motifs?: MotifStrengthOut[]
  /** Die Albumtauglichkeit des Modells - `null` heißt „noch nicht bewertet" und ist von der
   * niedrigsten Stufe unterscheidbar. Auf `=== null` prüfen, nie auf Falsyness. */
  album_suitability?: AlbumSuitabilityOut | null
  /**
   * Die persistierte GEMEINSAME Entscheidung des Projekts über dieses Foto; `null` = keine
   * getroffen. Sie ist keine Aussage eines Nutzers - `ratings[].status` heißt bereits
   * „album_decision", und die beiden zu verwechseln ist der Fehler, den diese Ansicht
   * ausschließt.
   */
  final_selection_decision: boolean | null
  /**
   * Gehört das Foto zur Endauswahl? DIE AUSSAGE DES SERVERS
   * (`backend album_selection.py::selection_state`). Die Oberfläche leitet die Zugehörigkeit
   * NIE selbst her - insbesondere nicht über `utils/albumDraft.ts::isInAlbum`, dessen Aussage
   * nur innerhalb der Antwortmenge des Entwurfszweigs gilt.
   */
  in_final_selection: boolean
  /** Sind sich die Nutzer über dieses Foto uneins und ist noch nicht gemeinsam entschieden? */
  contested: boolean
}

/*
 * DIE DREI FELDER OBEN SIND PFLICHTIG DEKLARIERT, anders als `ranking`/`location`/`event`
 * daneben - und das ist keine Stiltreue, sondern die Frontend-Hälfte der Auflage S9. Bei
 * `location` bedeuten `undefined` und `null` dasselbe; bei `in_final_selection` und `contested`
 * läse `undefined` sich als `false`, also als „gehört nicht zur Endauswahl" bzw. „ist nicht
 * strittig". Beides ist plausibel, wirft nichts und erscheint an keiner Stelle als Fehler; die
 * Endauswahl ist die Menge, die als Album gilt und die der Export nimmt. Ein optionales Feld
 * machte daraus ein leeres Album statt einen Typfehler.
 */

/**
 * EIN Teilnehmer der Endauswahl - genau `user_id` und `username`, mehr liefert der Server nicht
 * (Auflage S8). Die Länge der Liste ist zugleich der Nenner der Einigkeitsregel.
 *
 * SICHERHEIT: `username` ist fremdbestimmter Text und wird ausschließlich als regulärer
 * React-Textknoten gerendert - nie über `dangerouslySetInnerHTML`, nie in `href`, `src` oder
 * `style`, nie in eine URL (Auflage S10).
 */
export interface AlbumParticipantOut {
  user_id: number
  username: string
}

/**
 * Die Antwort von `GET /projects/{id}/album-selection` - die gemeinsame Endauswahl als GANZES.
 *
 * KEIN `total` und keine Seitenweise, wie beim Entwurfszweig: Die Menge wird vollständig
 * geliefert, und aus ihr entstehen LOKAL beide Sichten (Arbeitssicht `contested`, Ergebnissicht
 * `in_final_selection` samt der ausdrücklich Herausgenommenen). Der Umschalter lädt nichts nach.
 */
export interface AlbumSelectionOut {
  /** ALLE Nutzer, nach `user_id` sortiert - auch der, der noch nie etwas angefasst hat. */
  participants: AlbumParticipantOut[]
  /**
   * „Mindestens eine Rangzeile des letzten erfolgreichen Laufs trägt `selection_position`."
   * Trennt die beiden Leerzustände, die verschiedene Handlungen verlangen: „kein
   * Auswahlvorschlag" (einen Lauf starten) gegen „keine Unterschiede offen" (nichts tun).
   */
  has_proposal: boolean
  items: PhotoOut[]
}

/**
 * Die Antwort von `PUT /photos/{id}/album-decision` - der PERSISTIERTE Zustand nach dem
 * Schreibvorgang, nie die Rückspiegelung des Bodys (Auflage S5). `utils/albumSelection.ts::
 * applyAlbumDecision` schreibt genau diesen Wert fort, nie den lokal beabsichtigten.
 */
export interface AlbumDecisionOut {
  photo_id: number
  included: boolean
  updated_at: string
}

/** Die fünfstufige Modellaussage über die Albumtauglichkeit eines Fotos samt Begründung.
 *
 * SICHERHEITSHINWEIS: `reason` ist freier, extern erzeugter LLM-Text - ausschliesslich als
 * regulärer React-Textknoten rendern (nie `dangerouslySetInnerHTML`, nie als HTML-String-Prop,
 * nie als Markdown, nie in `href`/`src`/`style`). Das ist keine bloße Konvention, sondern die
 * tragende Voraussetzung dafür, dass das Session-Token in `localStorage` liegen darf. Er ist
 * erkennbar als Aussage des MODELLS auszuweisen, nicht als Aussage von PhotoSort: er stammt aus
 * einem Bild, das Text enthalten kann.
 *
 * `reason === null` heißt „keine Begründung" - die Zeile entfällt dann ersatzlos, kein
 * Platzhalter, kein „—". */
export interface AlbumSuitabilityOut {
  level: number
  reason: string | null
}

export interface PhotoListOut {
  items: PhotoOut[]
  total: number
}

// Ab hier: die Momentaufnahme eines Projekts (GET /projects/{id}/stats). Reine Anzeigedaten -
// die Seite löst nichts aus und schreibt nichts.

export interface ProjectStatsStorage {
  opencloud_bytes: number
  // null = nicht ermittelbar (keine PostgreSQL-Datenbank). Immer explizit `=== null` pruefen,
  // nie truthy: 0 ist ein gueltiger, informativer Wert und heisst etwas anderes.
  local_cache_bytes: number
  local_database_bytes_estimate: number | null
}

/** Eine Zeile der Motivverteilung. Der Anzeigename kommt vom Server - es gibt bewusst KEINE
 * Übersetzungstabelle für Motivschlüssel im Frontend, sonst liefen beide Listen auseinander.
 *
 * Die drei Bandzahlen sind DISJUNKT und ERSCHÖPFEND: ihre Summe je Motiv ist die Zahl der
 * beurteilten Fotos. Über alle Motive summiert übersteigt sie die Fotoanzahl - ein Foto trägt
 * alle acht Motive mit unterschiedlicher Stärke und zählt in mehreren Zeilen. Genau das ist der
 * Grund für den dauerhaft sichtbaren Erklärsatz über der Tabelle.
 *
 * Es gibt bewusst KEIN `share`-Feld: ein Anteil setzte eine Grundmenge voraus, zu der die Zahlen
 * sich summieren. */
export interface ProjectStatsMotifEntry {
  motif_key: string
  display_name: string
  strong_photo_count: number
  medium_photo_count: number
  weak_photo_count: number
  /** Arithmetisches Mittel der WIRKSAMEN Stärken, Bruchteil zwischen 0 und 1. `null` ohne ein
   * einziges beurteiltes Foto - immer explizit `=== null` prüfen, nie truthy: `0` ist ein
   * gültiger Mittelwert und eine völlig andere Aussage als „nicht erhoben". */
  average_strength: number | null
}

/** Die beiden Cloud-Zwecke (backend models.py::CloudVisionPhase) - immer beide, auch mit 0. */
export type CloudVisionPurpose = 'landmark' | 'remote_category'

export interface ProjectStatsCostByPurpose {
  purpose: CloudVisionPurpose
  cost_usd: number
  /** true = für mindestens einen Lauf dieses Zwecks fehlen Verbrauchsdaten. Es wird bewusst
   * nichts geschätzt - der Betrag bleibt die Summe des tatsächlich Erfassten. */
  has_unrecorded_runs: boolean
}

export interface ProjectStatsCost {
  currency: string
  /** Serverseitig UNGERUNDET - erst die Anzeige rundet, damit die Summe exakt der Summe der
   * angezeigten Einzelposten entspricht. */
  total_usd: number
  by_purpose: ProjectStatsCostByPurpose[]
}

export interface ProjectStatsProgress {
  scanned: number
  thumbnails_ready: number
  ausschuss_scored: number
  ranked: number
  remote_classified: number
}

/**
 * Ausschliesslich die Bewertungen des ANGEMELDETEN Nutzers.
 *
 * DIE VIER WERTE ZERLEGEN DEN BESTAND NICHT: `favorite` steht seit ADR 0098 NEBEN der
 * Albumentscheidung - dasselbe Foto zählt in `favorite` und in `album_worthy`. Erschöpfend und
 * überschneidungsfrei sind allein `album_worthy + rejected + unrated`. Die Anzeige darf keine
 * Aufteilung des Bestands über alle vier behaupten.
 */
export interface ProjectStatsRatings {
  favorite: number
  album_worthy: number
  rejected: number
  unrated: number
}

/** Jeweils der Abschlusszeitpunkt des zuletzt ERFOLGREICHEN Laufs; null = noch nie gelaufen. */
export interface ProjectStatsLastSuccessfulRuns {
  scan: string | null
  scoring: string | null
  classification: string | null
  remote_category_classification: string | null
}

export interface ProjectStatsRemoteFailure {
  purpose: CloudVisionPurpose
  photo_count: number
}

export interface ProjectStatsDiagnostics {
  /** null = noch nie gescannt (ausdruecklich nicht 0). */
  last_scan_files_skipped: number | null
  duplicate_photo_count: number
  /** Ist-Zustand, keine Historie: ein erfolgreicher Retry senkt den Wert wieder. */
  remote_failures: ProjectStatsRemoteFailure[]
}

export interface ProjectStatsOut {
  photo_count: number
  storage: ProjectStatsStorage
  /** null bei leerem Projekt; bei genau einem Foto ist Anfang gleich Ende. */
  taken_at_earliest: string | null
  taken_at_latest: string | null
  /** Immer alle acht Motive in Registry-Anzeigereihenfolge, auch mit drei Nullen. */
  motifs: ProjectStatsMotifEntry[]
  /** Die Anzeigebänder der Tabelle - sie kommen vom Server, damit das Frontend sie nicht
   * hinterlegt. Sie sind KEINE Zugehörigkeitsschwelle, und außerhalb dieser Tabelle erscheint
   * kein Bandwort. */
  strength_bands: MotifStrengthBandsOut
  /** Fotos ganz ohne Kopfzeile. Sie fehlen in JEDER Zahl der Tabelle und stehen deshalb als
   * eigene Kennzahl daneben, nicht als achtes Nullband. */
  unassessed_photo_count: number
  /** Als Dokument/Screenshot ausgeschlossene Fotos - projektweit, weil das die einzige Stelle
   * ist, an der ein systematisch überschießendes Modell auffällt. */
  excluded_photo_count: number
  /** Korrektur-ZEILEN, nicht Fotos: ein Foto kann bis zu acht tragen. */
  motif_correction_count: number
  cost: ProjectStatsCost
  progress: ProjectStatsProgress
  ratings: ProjectStatsRatings
  last_successful_runs: ProjectStatsLastSuccessfulRuns
  diagnostics: ProjectStatsDiagnostics
}

/**
 * Die drei Arten, auf die das Modell bei einem Motiv danebenlag: zu schwach erkannt, gar nicht
 * erkannt, vom Modell genannt und von uns weggenommen.
 */
export type MotifErrorCase = 'too_weak' | 'missing' | 'overcalled'

/** Gleichstufig, über Modellstufen hinweg, oder mangels Stufe unbestimmt. */
export type ExchangeKind = 'within_level' | 'across_level' | 'undetermined'

/**
 * Die drei Fehlerfälle sind NICHT erschöpfend: Eine Korrektur ohne Modellfehler zählt in keinem
 * von ihnen. Ihre Bezugsgröße ist `correction_count`, nie ihre eigene Summe.
 */
export interface FeedbackMotifError {
  case: MotifErrorCase
  count: number
}

/**
 * `quality_incomparable_count` hält die Austausche mit gleichem UND die mit fehlendem
 * eingefrorenem Qualitätswert. Sie gehen in `preferred_lower_rated_count` nicht ein und werden
 * auch seinem Gegenstück nicht zugeschlagen.
 */
export interface FeedbackExchangeStats {
  kind: ExchangeKind
  count: number
  preferred_lower_rated_count: number
  quality_incomparable_count: number
}

/**
 * `case_count` ist die Zahl der tatsächlich auswertbaren Paare - beide Fotos tragen den Messwert.
 * Sie kann kleiner sein als die Zahl der gleichstufigen Austausche.
 */
export interface FeedbackCriterionAgreement {
  criterion_key: string
  /** Aus der Backend-Registry, wie bei `CriterionScoreOut` - im Frontend wird dazu bewusst keine
   * zweite Merkmalsliste gepflegt. */
  display_name: string
  case_count: number
  /** In `[-1, 1]`; bei null Stimmen `0`. */
  agreement: number
}

/** Das geltende Gewicht eines Kriteriums. */
export interface FeedbackCurrentWeight {
  criterion_key: string
  weight: number
}

/**
 * Das abgeleitete Gewicht samt seiner Abweichung vom GELTENDEN - genau der Unterschied zwischen
 * den beiden nebeneinander dargestellten Spalten.
 */
export interface FeedbackProposedWeight {
  criterion_key: string
  weight: number
  delta: number
}

/**
 * Die Gewichts-Vorschau.
 *
 * `based_on_event_id` ist ein ZUSTIMMUNGS-TOKEN, kein Objektverweis: Es wird unverändert an die
 * Übernahme zurückgereicht und ist das Einzige, was „übernommen wurde, was angezeigt war" wahr
 * macht. Bei leerem Log ist es `0`.
 *
 * `current_set_id` ist die geltende Fassung (`null` = es gilt der Startwertsatz) und zugleich das,
 * was die Rücknahme nennen muss. `can_revert` ist serverseitig genau `current_set_id !== null` und
 * steht daneben, damit die Oberfläche die Bedingung nicht selbst formuliert.
 */
export interface FeedbackWeightPreview {
  current: FeedbackCurrentWeight[]
  proposed: FeedbackProposedWeight[]
  based_on_event_id: number
  current_set_id: number | null
  can_revert: boolean
}

/**
 * Die laufende Diagnose der Modellfehler.
 *
 * DIE ZAHLEN GELTEN PROJEKTÜBERGREIFEND UND ÜBER BEIDE NUTZER, obwohl der Abschnitt auf der
 * Projekt-Statistikseite steht - der Endpunkt nimmt keinen Projektparameter entgegen.
 *
 * `correction_count` ist die UNGEWICHTETE Zahl aller festgehaltenen Korrekturen und zugleich das
 * einzige Unterscheidungsmerkmal des Leerzustands: Die drei Fehlerfälle, die drei Tauschklassen
 * und die Kriterien stehen auch bei null Korrekturen vollständig in der Antwort.
 */
export interface FeedbackDiagnosisOut {
  correction_count: number
  motif_errors: FeedbackMotifError[]
  exchanges: FeedbackExchangeStats[]
  criteria: FeedbackCriterionAgreement[]
  weights: FeedbackWeightPreview
}
