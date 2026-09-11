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

// Wiederverwendet ScanStatus (running/success/failed) statt eines eigenen Typs - identische
// Semantik für einen asynchron laufenden Worker-Job, siehe backend models.py::ScoringRun.
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
// 'landmark' ist die Sehenswürdigkeits-Erkennung. 'ranking' (Kategorieableitung und
// Rangfolge) gehört fachlich zur Kriterien-Phase, läuft aber DANACH; ohne eigenen Namen
// bliebe die Anzeige dort auf 'landmark' bei 100 % stehen.
export type ClassificationPhase = 'remote_categories' | 'criteria' | 'landmark' | 'ranking'

// Ein Cloud-Teilschritt EINES Klassifizierungslaufs: während des Laufs die
// Fortschrittsanzeige, danach die Bilanz - derselbe Datensatz zu zwei Zeitpunkten.
//
// Die Felder sind DURCHGÄNGIG `| null` und nicht optional (`?`): eine Auslassung an der
// Anzeigestelle soll ein Typfehler sein, kein stilles `undefined`. `null` heißt überall
// "nicht erfasst"/"unbekannt" - nie `0` und nie "kostenlos"; ein `?? 0` irgendwo im Pfad
// behauptete Kostenfreiheit für einen Lauf, der Geld ausgegeben hat.
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
// angewendet (GET /photos?top_n_per_category=N), der Job berechnet immer den vollen
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
  // Globales Feature-Flag, auf ProjectOut statt einem eigenen Endpunkt exponiert - siehe den
  // Kommentar in backend api/projects.py.
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
  // Das Modell, auf das sich die Schätzung bezieht - da die Modellwahl eine
  // Betriebseinstellung ist, benennt `provider` allein die Preisgrundlage nicht eindeutig.
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
// `PhotoOut.rankings`-Feld, nicht hier.
export interface SuggestionOut {
  status: RatingStatus
  reason: SuggestionReason
  duplicate_of: number | null
  sharpness: number
  exposure: number
  cluster_key: string | null
  computed_at: string
}

// Kategorie-Schlüssel. Die Menge ist fachlich GESCHLOSSEN (13 Einträge, backend
// categories.py::CATEGORY_REGISTRY), der TypeScript-Typ bleibt aber bewusst `string`: das
// Set kommt zur Laufzeit über `GET /categories` vom Server, eine hier gespiegelte Union wäre
// eine dauerhaft driftende zweite Liste. Zusätzlich können aus der LAUFHISTORIE
// (`PhotoRanking.category_key` früherer Läufe) Altwerte außerhalb des Sets auftauchen
// ("unerkannt", "landscape", "people") - das Frontend muss sie über den generischen Fallback
// darstellen können, ohne Absturz.
export type CategoryKey = string

// Ein Eintrag des festen Sets, wie ihn GET /categories liefert - in ANZEIGEREIHENFOLGE der
// Server-Registry (nicht alphabetisch). `locally_available` markiert die sechs ohne
// Remote-Lauf erreichbaren Kategorien.
export interface CategoryOut {
  key: CategoryKey
  display_name: string
  definition: string
  locally_available: boolean
}

// EINE Zugehörigkeit eines Fotos zu einer Kategorie aus der Kriterien-/Rangfolgen-Pipeline.
// Ein Foto hat mehrere davon - siehe `PhotoOut.rankings`.
export interface RankingOut {
  cluster_key: string
  category_key: CategoryKey
  rank_score: number
  rank_position: number
  // Größe der GESAMTEN Cluster x Kategorie-Partition (nicht nur der angeforderten top_n),
  // für "Rang M von N" im Info-Popover. Zählt Haupt- UND Nebenzeilen der Partition.
  partition_size: number
  /** Ob dies die HAUPTkategorie des Fotos ist. Genau eine Zugehörigkeit je Foto trägt
   * `true`. Die Rolle kommt ausschließlich aus diesem Feld - im Frontend wird KEINE
   * Konfidenz-Schwelle nachgebildet. */
  is_primary: boolean
  /** Der Platz dieser Zugehoerigkeit in der um die eigenen Ablehnungen bereinigten Auswahl ihrer
   * Kategorie. `null` heisst: gehoert nicht zur angeforderten Auswahl, oder es wurde gar keine
   * angefordert. AUSDRUECKLICH NICHT `rank_position` - jene ist die lauf-globale, ungefilterte
   * Rangaussage des Info-Popovers. Auf `!== null` pruefen, nie auf Falsyness. */
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
  // Spiegelt `CriterionDefinition.category_eligible` der Backend-Registry und ist die
  // ALLEINIGE Grundlage der Gliederung in die Blöcke "Qualität" (false) / "Kategorien"
  // (true) - im Frontend wird dazu bewusst keine Merkmalsliste gepflegt. Pflichtfeld statt
  // optional, damit `tsc` alle Test-Fixtures erzwingt, statt stillschweigend `undefined` in
  // die Blockbildung durchzureichen.
  category_eligible: boolean
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

// Die für DIESES Foto tatsächlich gültige Kategorie-Kandidatenmenge (lokal qualifizierende
// Kriterien + Remote-Erkennungen zusammen) - verhindert, dass das Frontend die
// Präsenz-Schwellenlogik (backend criteria.py::CRITERIA_REGISTRY) selbst nachbilden muss.
// `category_key` ist IMMER ein Key des festen Sets; die Auswahl entscheidet die feste
// Vorrangreihenfolge im Backend, nicht ein Zahlenvergleich. `provider` ist nur bei
// `origin === 'remote'` gesetzt. Die Liste ist reine ERKLÄRUNG ("das hat das System
// erkannt") - sie beschränkt NICHT, was manuell übersteuert werden darf.
export interface CategoryCandidateOut {
  category_key: CategoryKey
  origin: 'local' | 'remote'
  provider: string | null
  /** Die Selbsteinschätzung des Erkennungsmodells zu DIESEM Schlüssel, ein Bruchteil
   * zwischen 0 und 1 - keine gemessene Trefferquote. Die Zahl beeinflusst weder Auswahl
   * noch Sortierung.
   *
   * `null` heißt "keine Modellaussage" (z.B. ein rein lokal erkannter Kandidat oder eine
   * Klassifizierungszeile aus der Zeit vor der Migration) - NIE als `0` behandeln und immer
   * explizit `=== null` prüfen: `0` ist ein gültiger Wert und heißt "das Modell war sich zu
   * 0 % sicher". Fehlt die Zahl, wird KEIN Platzhalter gerendert. */
  confidence: number | null
}

// Die beiden unabhängigen Cloud-Vision-Läufe, für die pro Foto genau einer von sechs
// Zuständen angezeigt wird. Derselbe Typ schlüsselt auch die Cloud-Teilschritte eines Laufs
// (`CloudPhaseSummaryOut.purpose`) - dieselben zwei Zwecke, eine Definition.
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

/** Der bereits AUFGELÖSTE Ort des CLUSTERS - auf jedem Foto desselben Clusters identisch,
 * `null` ohne jede Ortsinformation.
 *
 * Der Server liefert den fertigen ZUSTAND, nicht die Rohdaten für eine Rangfolge. Das
 * Frontend bildet die Rangfolge (Sehenswürdigkeit -> Koordinate -> mehrere Orte) NICHT nach,
 * es verzweigt über `kind` und formatiert - denn der Cluster reicht über die geladenen Fotos
 * hinaus (Top-N-Auswahl), und eine Aggregation hier wäre dauerhaft eine Aussage über die
 * Top-N. `kind: 'multiple'` trägt strukturell keine Koordinate.
 *
 * `landmark_name` ist freier, extern erzeugter LLM-Text: ausschließlich als regulärer
 * React-Textknoten rendern - nie `dangerouslySetInnerHTML`, nie als HTML-String-Prop, nie in
 * `href`/`src`/`style`, nie als React-`key` (dieselbe Auflage wie bei
 * `FineLabelOut.raw_label`). */
export interface ClusterPlace {
  kind: 'landmark' | 'coordinate' | 'multiple'
  landmark_name: string | null
  lat: number | null
  lon: number | null
}

export interface PhotoOut {
  id: number
  relative_path: string
  taken_at: string
  ratings: RatingOut[]
  suggestion: SuggestionOut | null
  /** ALLE Zugehörigkeiten des Fotos im letzten erfolgreichen Lauf, in beiden Query-Modi.
   * Immer eine Liste, nie `null` - leer, solange kein erfolgreicher Lauf existiert.
   * Reihenfolge: Hauptzeile zuerst, danach die Nebenzeilen in Registry-Anzeigereihenfolge.
   *
   * Nie `rankings[0]` als "die Hauptzeile" lesen - dafür gibt es
   * `utils/rankings.ts::primaryRanking`. */
  rankings: RankingOut[]
  criterion_scores: CriterionScoreOut[]
  // Immer eine Liste (0-2 Einträge), nie null.
  fine_labels: FineLabelOut[]
  // Die remote ermittelte Kategorie dieses Fotos, null ohne Remote-Klassifizierung. Bewusst
  // getrennt von `rankings[].category_key` (dort steht die im Lauf tatsaechlich vergebene
  // Kategorie).
  remote_category: CategoryKey | null
  /** Die Konfidenz zu `remote_category`. Eigenes Feld statt einer Ableitung aus
   * `category_candidates` - `remote_category` kann `nicht_erkannt` sein und steht dann gar
   * nicht in der Kandidatenliste. Trägt den Kuratierungsfilter "Nur unsichere Zuordnungen".
   * `null` heißt "keine Angabe", nie 0. */
  category_confidence: number | null
  // Dauerhafte manuelle Uebersteuerung (PhotoScore.category_override), null ohne aktiven
  // Override.
  category_override: CategoryKey | null
  // Sortiert in Registry-Anzeigereihenfolge (dieselbe Reihenfolge wie GET /categories).
  category_candidates: CategoryCandidateOut[]
  // Immer genau 2 Einträge, feste Reihenfolge [landmark, remote_category].
  cloud_vision_status: CloudVisionStatusOut[]
  /** Beide Felder liefert die API IMMER (auf allen Lesepfaden, `null` ohne
   * Ortsinformation). Hier trotzdem OPTIONAL deklariert, damit die bestehenden
   * Fixture-Literale der Testsuite unverändert gültig bleiben - `undefined` und `null`
   * bedeuten an jeder Lesestelle dasselbe: kein Ort. */
  location?: PhotoLocation | null
  cluster_place?: ClusterPlace | null
}

export interface PhotoListOut {
  items: PhotoOut[]
  total: number
}

// Antwort von PUT /photos/{id}/category-override - der gesetzte Wert wird direkt
// zurückgegeben, analog PUT /photos/{id}/rating.
export interface CategoryOverrideOut {
  photo_id: number
  category_key: CategoryKey
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

export interface ProjectStatsCategoryEntry {
  category_key: string
  // Der Anzeigename kommt vom Server - es gibt bewusst KEINE Übersetzungstabelle für
  // Set-Keys im Frontend, sonst liefen beide Listen auseinander.
  display_name: string
  photo_count: number
  /** Bruchteil zwischen 0 und 1, bezogen auf die KLASSIFIZIERTEN Fotos. */
  share: number
}

export interface ProjectStatsCategories {
  classified_photo_count: number
  unclassified_photo_count: number
  /** Immer alle Kategorien des festen Sets inkl. `nicht_erkannt`, in Anzeigereihenfolge. */
  entries: ProjectStatsCategoryEntry[]
}

/** Ein Eintrag des Konfidenzblocks. */
export interface ProjectStatsCategoryConfidenceEntry {
  category_key: string
  /** Anzeigename vom Server, wie bei `ProjectStatsCategoryEntry`. */
  display_name: string
  /** Fotos DIESER Modell-Kategorie mit einer Angabe - nicht alle Fotos der Kategorie. */
  photo_count: number
  /** Arithmetisches Mittel genau dieser Angaben, Bruchteil zwischen 0 und 1. `null` bei
   * `photo_count === 0` - immer explizit `=== null` pruefen, nie truthy: `0` ist ein gueltiger
   * Mittelwert und eine voellig andere Aussage als "keine Angabe". */
  average_confidence: number | null
}

/** Gruppiert über die MODELL-Kategorie, ausdrücklich nicht über die wirksame Kategorie der
 * Rangfolge - ein übersteuertes Foto zählt hier weiterhin zu seiner Modell-Kategorie.
 * Deshalb ein eigener Block neben `ProjectStatsCategories` und keine zusätzliche Spalte
 * dort: beide Zahlen stimmen, beziehen sich aber auf verschiedene Mengen.
 *
 * Die beiden Zähler sind die BEZUGSBASIS und beziehen sich auf die klassifizierten Fotos
 * des Projekts; ihre Summe ist die Zahl der Klassifizierungszeilen, nicht die
 * Fotoanzahl. */
export interface ProjectStatsCategoryConfidence {
  /** Immer alle Kategorien des festen Sets inkl. `nicht_erkannt`, in Anzeigereihenfolge. */
  entries: ProjectStatsCategoryConfidenceEntry[]
  photos_with_confidence: number
  photos_without_confidence: number
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
  categories: ProjectStatsCategories
  category_confidence: ProjectStatsCategoryConfidence
  manual_category_override_count: number
  cost: ProjectStatsCost
  progress: ProjectStatsProgress
  ratings: ProjectStatsRatings
  last_successful_runs: ProjectStatsLastSuccessfulRuns
  diagnostics: ProjectStatsDiagnostics
}
