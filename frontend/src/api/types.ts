export type ScanStatus = 'running' | 'success' | 'failed'

export interface ScanSummary {
  status: ScanStatus
  started_at: string
  finished_at: string | null
  files_found: number
  // specs/features/0036-scan-performance-zweiphasig-parallel.md: null solange die
  // Enumerationsphase noch nicht abgeschlossen ist - unterscheidet sich bewusst von 0 (leeres
  // Projekt). Immer explizit `!== null`/`=== null` pruefen, nie truthy.
  total_files: number | null
  photos_added: number
  photos_updated: number
  photos_removed: number
  files_skipped: number
  error_message: string | null
}

// Wiederverwendet ScanStatus (running/success/failed) statt eines eigenen Typs - identische
// Semantik fuer einen asynchron laufenden Worker-Job, siehe backend models.py::ScoringRun.
export interface ScoringRunSummary {
  // Additiv (specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md): wird als
  // scoring_run_id an POST /classify weitergereicht (Staleness-Guard bei einem zwischenzeitlichen
  // Re-Scan/Re-Scoring; bis specs/features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md an
  // POST /score-criteria).
  id: number
  status: ScanStatus
  started_at: string
  finished_at: string | null
  photos_total: number
  photos_processed: number
  suggestions_found: number
  error_message: string | null
  // Ausschuss-Gate (specs/features/0037): null = noch nicht bestaetigt.
  gate_confirmed_at: string | null
}

// specs/features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md, erweitert von
// specs/features/0348-klassifizierungs-transparenz.md: die VIER Teilschritte eines verketteten
// Klassifizierungslaufs, in genau dieser Reihenfolge.
//
// 'landmark' ist die Sehenswuerdigkeits-Erkennung - bis Spec 0348 ein unsichtbarer Teil der
// Kriterien-Phase, in der sich der Fortschritt nicht mehr bewegte. 'ranking' (Kategorieableitung
// und Rangfolge) gehoert fachlich zur Kriterien-Phase, laeuft aber DANACH; ohne eigenen Namen
// bliebe die Anzeige dort auf 'landmark' bei 100 % stehen.
export type ClassificationPhase = 'remote_categories' | 'criteria' | 'landmark' | 'ranking'

// Ein Cloud-Teilschritt EINES Klassifizierungslaufs (specs/features/0348-klassifizierungs-
// transparenz.md): waehrend des Laufs die Fortschrittsanzeige, danach die Bilanz - derselbe
// Datensatz zu zwei Zeitpunkten.
//
// Die Felder sind DURCHGAENGIG `| null` und nicht optional (`?`): eine Auslassung an der
// Anzeigestelle soll ein Typfehler sein, kein stiller `undefined`. `null` heisst ueberall
// "nicht erfasst"/"unbekannt" - nie `0` und nie "kostenlos"; ein `?? 0` irgendwo im Pfad
// behauptete Kostenfreiheit fuer einen Lauf, der Geld ausgegeben hat.
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

// Ersetzt TopSelectionRunSummary (specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-
// backfill.md) - kein top_n_per_cluster/candidates_total/suggestions_found mehr: N wird erst
// beim Lesen angewendet (GET /photos?top_n_per_category=N), der Job berechnet immer den vollen
// Rangfolge-Pool je Partition statt eine Top-N-Auswahl zu treffen.
export interface CriterionScoringRunSummary {
  status: ScanStatus
  started_at: string
  finished_at: string | null
  photos_total: number
  photos_processed: number
  error_message: string | null
  // specs/features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md: diese Zusammenfassung
  // beschreibt seit Spec 0296 den GESAMTEN Klassifizierungslauf, nicht mehr nur seine
  // Kriterien-Phase.
  //
  // `phase`: der gerade laufende Teilschritt; null = laeuft nicht mehr (beendet, oder Altlauf aus
  // der Zeit der getrennten Ausloesung). Die Fortschrittszahlen der beiden Cloud-Teilschritte
  // stehen seit Spec 0348 in `cloud_phases`, die der Kriterien-Phase hier.
  phase: ClassificationPhase | null
  // War die Cloud-Nutzung fuer DIESEN Lauf angefordert? false heisst "das Ergebnis kann keine
  // Cloud-Anreicherung enthalten" - Grundlage des entsprechenden Hinweises in der Oberflaeche.
  cloud_requested: boolean
  // Laufweite Zusammenfassung der Cloud-Probleme, null = keine. Ein gesetzter Wert heisst NICHT,
  // dass der Lauf fehlgeschlagen ist: der lokale Bewertungsanteil laeuft trotzdem vollstaendig
  // durch, das Ergebnis ist nur nicht (vollstaendig) angereichert.
  cloud_error_message: string | null
  // specs/features/0348-klassifizierungs-transparenz.md: die Bilanz DIESES Durchlaufs.
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
  // specs/features/0348-klassifizierungs-transparenz.md: `last_remote_category_classification_run`
  // ist ERSATZLOS entfallen. Sein einziger Leser war die Fortschrittsanzeige, und die liest jetzt
  // `last_criterion_scoring_run.cloud_phases` - also den Remote-Lauf DIESES Durchlaufs statt den
  // juengsten des Projekts.
  // Globales Feature-Flag (specs/features/0024-top-photo-selection-category-mix.md, weiterhin
  // verwendet fuer POST /classify seit Spec 0296), auf ProjectOut statt einem eigenen
  // Endpunkt exponiert - siehe backend api/projects.py-Kommentar.
  category_selection_enabled: boolean
  // Projektweiter Einwilligungs-Schalter fuer produktive Cloud-Vision-Datenfluesse (urspruenglich
  // nur die Cloud-Sehenswuerdigkeit-Erkennung, specs/features/0047-sehenswuerdigkeit-erkennung-
  // cloud-vision-api.md) - Default false, consent_at null solange nicht aktiviert. Gated seit
  // specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md zusaetzlich die
  // Remote-Kategorie-Klassifizierung.
  cloud_vision_detection_enabled: boolean
  cloud_vision_consent_at: string | null
}

// specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, ADR 0032 Punkt
// 6.1, fortgeschrieben von specs/features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md
// (ADR 0050 Punkt 5): Kostenschaetzung vor dem Lauf, jetzt ueber ALLE Cloud-Anteile, die die
// Checkbox am Ausloeser freigibt. `candidate_count` ist die Summe der beiden Einzelanteile und
// bleibt die eine anzuzeigende Zahl.
// specs/features/0348-klassifizierungs-transparenz.md: ein einzelner Cloud-Anteil der
// Schaetzung. `candidate_count === null` heisst "nicht verlaesslich schaetzbar" (Landmark-Anteil
// vor dem ersten erfolgreichen Durchlauf), NIE "null Fotos"; `estimated_cost_usd === null` heisst
// "kein Preis hinterlegt ODER Anteil unbekannt", nie "kostenlos".
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
  // specs/features/0304-cloud-modell-je-anbieter-waehlbar.md: das Modell, auf das sich die
  // Schaetzung bezieht - seit die Modellwahl eine Betriebseinstellung ist, benennt `provider`
  // allein die Preisgrundlage nicht mehr eindeutig.
  model: string
  // `| null` heisst "fuer das eingestellte Modell ist kein Preis hinterlegt", NIE 0. Ein
  // `?? 0` an dieser Stelle behauptete Kostenfreiheit und fuehrte den mit Spec 0304 behobenen
  // Defekt auf dem Rueckweg wieder ein - `tsc` erzwingt die Behandlung an der Anzeigestelle.
  price_per_image_usd: number | null
  estimated_cost_usd: number | null
}

export interface BrowseEntry {
  name: string
  path: string
}

// specs/features/0050-dateianzahl-im-ordner-browser.md: rekursive Bilddatei-Anzahl (mit
// Obergrenze) pro direktem Unterordner, wie von GET /opencloud/folder-counts geliefert. Bewusst
// kein Freitext-/Meldungsfeld (Security-Abschnitt der Spec) - error=true transportiert kein
// str(exc) vom Backend.
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

// Automatischer Vorschlag aus PhotoScore, bewusst getrennt von RatingOut/ratings[] (ADR 0006,
// specs/decisions/0006-local-scoring-datamodel.md) - ein Vorschlag ist strukturell nie eine
// Bewertung, sondern wird erst durch aktive Bestaetigung (PUT /photos/{id}/rating) zu einer.
//
// "top_pick"/`category` (Spec 0024) sind mit specs/features/0037-gatefuehrte-bewertungs-
// pipeline-mit-backfill.md entfallen - der fruehere Top-Pick-Mechanismus ist durch die neue
// Kriterien-/Rangfolgen-Pipeline (PhotoRanking) ersetzt, deren Kontext jetzt im eigenstaendigen
// `PhotoOut.ranking`-Feld lebt statt in SuggestionOut (siehe backend api/photos.py::
// SuggestionOut-Docstring fuer die Begruendung dieser Trennung).
export interface SuggestionOut {
  status: RatingStatus
  reason: SuggestionReason
  duplicate_of: number | null
  sharpness: number
  exposure: number
  cluster_key: string | null
  computed_at: string
}

// Kategorie-Schluessel. Seit specs/features/0289-feste-kategorien.md ist die Menge fachlich
// GESCHLOSSEN (13 Eintraege, backend categories.py::CATEGORY_REGISTRY) - der TypeScript-Typ bleibt
// aber bewusst `string`: das Set kommt zur Laufzeit ueber `GET /categories` vom Server (ADR 0049,
// Entwurfsentscheidung 5), eine hier gespiegelte Union waere eine dauerhaft driftende zweite
// Liste. Zusaetzlich koennen aus der LAUFHISTORIE (`PhotoRanking.category_key` frueherer Laeufe)
// weiterhin Altwerte ausserhalb des Sets auftauchen ("unerkannt", "landscape", "people") - das
// Frontend muss sie ueber den generischen Fallback darstellen koennen, ohne Absturz.
export type CategoryKey = string

// specs/features/0289-feste-kategorien.md: ein Eintrag des festen Sets, wie ihn GET /categories
// liefert - in ANZEIGEREIHENFOLGE der Server-Registry (nicht alphabetisch). `locally_available`
// markiert die sechs ohne Remote-Lauf erreichbaren Kategorien.
export interface CategoryOut {
  key: CategoryKey
  display_name: string
  definition: string
  locally_available: boolean
}

// EINE Zugehoerigkeit eines Fotos zu einer Kategorie aus der Kriterien-/Rangfolgen-Pipeline
// (specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md). Seit
// specs/features/0040-bewertungsdetails-info-popover.md auch im Standard-Listing befuellt (nicht
// mehr nur bei `top_n_per_category`). Seit specs/features/0300-nebenkategorien.md hat ein Foto
// mehrere davon - siehe `PhotoOut.rankings`.
export interface RankingOut {
  cluster_key: string
  category_key: CategoryKey
  rank_score: number
  rank_position: number
  // Groesse der GESAMTEN Cluster x Kategorie-Partition (nicht nur der angeforderten top_n), fuer
  // "Rang M von N" im Info-Popover (specs/features/0040-bewertungsdetails-info-popover.md).
  // Zaehlt seit Spec 0300 Haupt- UND Nebenzeilen der Partition.
  partition_size: number
  /** specs/features/0300-nebenkategorien.md: ob dies die HAUPTkategorie des Fotos ist. Genau eine
   * Zugehoerigkeit je Foto traegt `true`. Die Rolle kommt ausschliesslich aus diesem Feld - im
   * Frontend wird KEINE Konfidenz-Schwelle nachgebildet. */
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

// Ein einzelner, bereits normierter Kriterien-Wert eines Fotos
// (specs/features/0040-bewertungsdetails-info-popover.md) - exponiert die seit Spec 0037
// vorhandene PhotoCriterionScore-Tabelle. Best-effort: nur Kriterien, fuer die tatsaechlich ein
// Wert berechnet wurde, sind enthalten (kein 0/Platzhalter fuer fehlende).
export interface CriterionScoreOut {
  criterion_key: string
  display_name: string
  value: number
  source: CriterionSource
  // specs/features/0209-bewertungsdetails-bloecke-qualitaet-kategorien.md,
  // Architektur-Entscheidung 1/2: spiegelt `CriterionDefinition.category_eligible` der
  // Backend-Registry und ist die ALLEINIGE Grundlage der Gliederung in die Bloecke
  // "Qualitaet" (false) / "Kategorien" (true) - im Frontend wird dazu bewusst keine
  // Merkmalsliste gepflegt. Pflichtfeld statt optional, damit `tsc` alle Test-Fixtures
  // erzwingt, statt stillschweigend `undefined` in die Blockbildung durchzureichen.
  category_eligible: boolean
}

// specs/features/0289-feste-kategorien.md: ein frei formuliertes, auf einen kanonischen Eintrag
// aufgeloestes Feinlabel - immer eine Liste (0-2 Eintraege), nie null. Reine ZUSATZINFORMATION am
// Foto, keine Kategoriequelle; `confidence` ist mit dieser Spec ersatzlos entfallen.
//
// SICHERHEITSHINWEIS: `display_name`/`raw_label` sind freier, extern erzeugter LLM-Text (backend
// zeichensaniert). Sie duerfen ausschliesslich als regulaerer React-Textknoten gerendert werden -
// nie ueber dangerouslySetInnerHTML, nie als HTML-String-Prop, nie in href/src/style.
export interface FineLabelOut {
  canonical_key: string
  display_name: string
  raw_label: string
  provider: string
}

// specs/features/0289-feste-kategorien.md: Haeufigkeit eines Feinlabels IN EINEM PROJEKT
// (GET /projects/{id}/fine-labels), absteigend sortiert - macht sichtbar, welche Kategorie im
// festen Set gegebenenfalls fehlt.
export interface FineLabelCountOut {
  canonical_key: string
  display_name: string
  photo_count: number
}

// specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, UI/UX-Abschnitt
// "Datenbedarf": die fuer DIESES Foto tatsaechlich gueltige Kategorie-Kandidatenmenge (lokal
// qualifizierende Kriterien + Remote-Erkennungen zusammen) - verhindert, dass das Frontend die
// Praesenz-Schwellenlogik (backend criteria.py::CRITERIA_REGISTRY) selbst nachbilden muss.
// `category_key` ist seit specs/features/0289-feste-kategorien.md IMMER ein Key des festen Sets;
// das frueher mitgelieferte `score`-Feld ist ersatzlos entfallen (die Auswahl entscheidet die
// feste Vorrangreihenfolge im Backend, nicht ein Zahlenvergleich). `provider` ist nur bei
// `origin === 'remote'` gesetzt. Die Liste ist reine ERKLAERUNG ("das hat das System erkannt") -
// sie beschraenkt NICHT mehr, was manuell uebersteuert werden darf.
export interface CategoryCandidateOut {
  category_key: CategoryKey
  origin: 'local' | 'remote'
  provider: string | null
  /** specs/features/0299-kategorie-konfidenz-anzeigen.md: die Selbsteinschaetzung des
   * Erkennungsmodells zu DIESEM Schluessel, ein Bruchteil zwischen 0 und 1 - keine gemessene
   * Trefferquote und ausdruecklich keine Wiederkehr des mit Spec 0289 entfallenen `score`-Felds:
   * die Zahl beeinflusst weder Auswahl noch Sortierung.
   *
   * `null` heisst "keine Modellaussage" (z.B. ein rein lokal erkannter Kandidat oder eine
   * Klassifizierungszeile aus der Zeit vor der Migration) - NIE als `0` behandeln und immer
   * explizit `=== null` pruefen: `0` ist ein gueltiger Wert und heisst "das Modell war sich zu
   * 0 % sicher". Fehlt die Zahl, wird KEIN Platzhalter gerendert. */
  confidence: number | null
}

// specs/features/0058-cloud-vision-status-transparenz.md, decisions/0035-cloud-vision-attempt-
// fehler-persistierung.md: die beiden unabhaengigen Cloud-Vision-Laeufe, fuer die pro Foto genau
// einer von sechs Zustaenden angezeigt wird. Seit specs/features/0348-klassifizierungs-
// transparenz.md schluesselt derselbe Typ auch die Cloud-Teilschritte eines Laufs
// (`CloudPhaseSummaryOut.purpose`) - dieselben zwei Zwecke, eine Definition.
export type CloudVisionPhase = 'landmark' | 'remote_category'

// Read-time aus bereits vorhandenen Signalen abgeleitet (backend api/photos.py::
// _cloud_vision_status_out) - kein voller Status pro Foto persistiert. `no_result` tritt nur bei
// `phase === 'landmark'` auf (ADR 0032 Punkt 3: Remote-Kategorie kennt keinen "nichts
// gefunden"-Fall, Erfolg schreibt immer 1-3 Zeilen).
export type CloudVisionStatus =
  | 'not_run'
  | 'not_candidate'
  | 'consent_disabled'
  | 'error'
  | 'no_result'
  | 'result'

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

export interface PhotoOut {
  id: number
  relative_path: string
  taken_at: string
  ratings: RatingOut[]
  suggestion: SuggestionOut | null
  /** ALLE Zugehoerigkeiten des Fotos im letzten erfolgreichen Lauf, in beiden Query-Modi
   * (specs/features/0300-nebenkategorien.md). Immer eine Liste, nie `null` - leer, solange kein
   * erfolgreicher Lauf existiert. Reihenfolge: Hauptzeile zuerst, danach die Nebenzeilen in
   * Registry-Anzeigereihenfolge.
   *
   * Ersetzt das entfallene `ranking`. Nie `rankings[0]` als "die Hauptzeile" lesen - dafuer gibt es
   * `utils/rankings.ts::primaryRanking`. */
  rankings: RankingOut[]
  criterion_scores: CriterionScoreOut[]
  // specs/features/0289-feste-kategorien.md: immer eine Liste (0-2 Eintraege), nie null.
  fine_labels: FineLabelOut[]
  // Die remote ermittelte Kategorie dieses Fotos, null ohne Remote-Klassifizierung. Bewusst
  // getrennt von `rankings[].category_key` (dort steht die im Lauf tatsaechlich vergebene
  // Kategorie).
  remote_category: CategoryKey | null
  /** specs/features/0299-kategorie-konfidenz-anzeigen.md: die Konfidenz zu `remote_category`.
   * Eigenes Feld statt einer Ableitung aus `category_candidates` - `remote_category` kann
   * `nicht_erkannt` sein und steht dann gar nicht in der Kandidatenliste. Traegt den
   * Kuratierungsfilter "Nur unsichere Zuordnungen". `null` heisst "keine Angabe", nie 0. */
  category_confidence: number | null
  // Dauerhafte manuelle Uebersteuerung (PhotoScore.category_override), null ohne aktiven
  // Override.
  category_override: CategoryKey | null
  // Sortiert in Registry-Anzeigereihenfolge (dieselbe Reihenfolge wie GET /categories).
  category_candidates: CategoryCandidateOut[]
  // specs/features/0058-cloud-vision-status-transparenz.md: immer genau 2 Eintraege, feste
  // Reihenfolge [landmark, remote_category].
  cloud_vision_status: CloudVisionStatusOut[]
}

export interface PhotoListOut {
  items: PhotoOut[]
  total: number
}

// specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, ADR 0032 Punkt
// 6.3: Antwort von PUT /photos/{id}/category-override (der gesetzte Wert wird direkt
// zurueckgegeben, analog PUT /photos/{id}/rating).
export interface CategoryOverrideOut {
  photo_id: number
  category_key: CategoryKey
}

// specs/features/0207-projekt-statistikseite.md, decisions/0051-ist-kostenerfassung-remote-
// laeufe.md ab hier: die Momentaufnahme eines Projekts (GET /projects/{id}/stats). Reine
// Anzeigedaten - die Seite loest nichts aus und schreibt nichts.

export interface ProjectStatsStorage {
  opencloud_bytes: number
  // null = nicht ermittelbar (keine PostgreSQL-Datenbank). Immer explizit `=== null` pruefen,
  // nie truthy: 0 ist ein gueltiger, informativer Wert und heisst etwas anderes.
  local_cache_bytes: number
  local_database_bytes_estimate: number | null
}

export interface ProjectStatsCategoryEntry {
  category_key: string
  // Der Anzeigename kommt vom Server (ADR 0049) - es gibt bewusst KEINE Uebersetzungstabelle fuer
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

/** specs/features/0299-kategorie-konfidenz-anzeigen.md: ein Eintrag des Konfidenzblocks. */
export interface ProjectStatsCategoryConfidenceEntry {
  category_key: string
  /** Anzeigename vom Server (ADR 0049), wie bei `ProjectStatsCategoryEntry`. */
  display_name: string
  /** Fotos DIESER Modell-Kategorie mit einer Angabe - nicht alle Fotos der Kategorie. */
  photo_count: number
  /** Arithmetisches Mittel genau dieser Angaben, Bruchteil zwischen 0 und 1. `null` bei
   * `photo_count === 0` - immer explizit `=== null` pruefen, nie truthy: `0` ist ein gueltiger
   * Mittelwert und eine voellig andere Aussage als "keine Angabe". */
  average_confidence: number | null
}

/** Gruppiert ueber die MODELL-Kategorie, ausdruecklich nicht ueber die wirksame Kategorie der
 * Rangfolge (ADR 0067 Punkt 5) - ein uebersteuertes Foto zaehlt hier weiterhin zu seiner
 * Modell-Kategorie. Deshalb ein eigener Block neben `ProjectStatsCategories` und keine zusaetzliche
 * Spalte dort: beide Zahlen stimmen, beziehen sich aber auf verschiedene Mengen.
 *
 * Die beiden Zaehler sind die BEZUGSBASIS und beziehen sich auf die klassifizierten Fotos des
 * Projekts; ihre Summe ist die Zahl der Klassifizierungszeilen, nicht die Fotoanzahl. */
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
  /** true = fuer mindestens einen Lauf dieses Zwecks fehlen Verbrauchsdaten (ADR 0051 Punkt 5).
   * Es wird bewusst nichts geschaetzt - der Betrag bleibt die Summe des tatsaechlich Erfassten. */
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
