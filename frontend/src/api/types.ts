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

// Bewusst kein top_n_per_cluster/candidates_total/suggestions_found: N wird erst beim Lesen
// angewendet (GET /photos?top_n_per_event=N), der Job berechnet immer den vollen
// Rangfolge-Pool je Partition statt eine Top-N-Auswahl zu treffen.
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

export type RatingStatus = 'favorite' | 'album_worthy' | 'rejected'
export type RatingFilter = 'unrated' | 'suggested' | RatingStatus
export type PhotoVariant = 'thumbnail' | 'display'

export interface RatingOut {
  user_id: number
  username: string
  status: RatingStatus
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
}

// Antwort von PUT /photos/{id}/motif-corrections/{motif_key} - der gesetzte Wert wird direkt
// zurückgegeben, analog PUT /photos/{id}/rating.
export interface MotifCorrectionOut {
  photo_id: number
  motif_key: MotifKey
  applies: boolean
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
  // Größe der GESAMTEN Event-Partition (nicht nur der angeforderten top_n), für "Rang M von N"
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
 * In der Überschrift erscheint allein `kind: 'landmark'`; Koordinate und "mehrere Orte" fallen
 * auf "Position N" zurück. Die Werte bleiben trotzdem in der Antwort - aus ihnen wird mit
 * Reverse-Geocoding später wieder ein Name.
 *
 * `landmark_name` ist freier, extern erzeugter LLM-Text: ausschließlich als regulärer
 * React-Textknoten rendern - nie `dangerouslySetInnerHTML`, nie als HTML-String-Prop, nie in
 * `href`/`src`/`style`, nie als React-`key` (dieselbe Auflage wie bei
 * `FineLabelOut.raw_label`). */
export interface EventPlace {
  kind: 'landmark' | 'coordinate' | 'multiple'
  landmark_name: string | null
  lat: number | null
  lon: number | null
}

/** Das Event, zu dem dieses Foto im letzten erfolgreichen Lauf gehört.
 *
 * Nummer und Zeitspanne stehen in der Zeile des Events und hängen damit NICHT davon ab, welche
 * Fotos eine Antwort gerade enthält - anders als bei der früheren Cluster-Überschrift, die aus
 * den sichtbaren Fotos aggregiert wurde. */
export interface EventOut {
  id: number
  position: number
  started_at: string
  ended_at: string
  place: EventPlace | null
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

/** Ausschliesslich die Bewertungen des ANGEMELDETEN Nutzers; die vier Werte summieren sich exakt
 * zur Fotoanzahl. */
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
