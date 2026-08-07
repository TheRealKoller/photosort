# 0024 - Top-Fotos auswählen mit Kategorie-Mix (lokal)

**Status:** Accepted
**Erstellt:** 2026-08-07
**Bezug:** Inbox-Notiz `specs/inbox/0011-beste-fotos-vorschlagen-neu-denken.md` (Daniel selbst, interaktive Session; nach Aufnahme in diese Spec gelöscht), [`decisions/0002-hybrid-ai-scoring.md`](../decisions/0002-hybrid-ai-scoring.md), [`decisions/0006-local-scoring-datamodel.md`](../decisions/0006-local-scoring-datamodel.md), [`decisions/0015-lokale-kategorie-klassifikation.md`](../decisions/0015-lokale-kategorie-klassifikation.md), [`features/0003-automatic-best-photo-selection.md`](./0003-automatic-best-photo-selection.md), Idea-Sharpening-Gespräch mit Daniel am 2026-08-07

## Ziel

Spec 0003 ("Phase A") spricht bewusst nie eine positive Empfehlung aus — sie sortiert nur offensichtlichen Ausschuss (unscharf, Duplikate) aus. Der Button-Text "Beste Fotos automatisch vorschlagen" versprach dabei aber mehr, als das System lieferte — genau das hat Daniel als irreführend benannt. Diese Spec ergänzt eine echte, positive Top-Auswahl: pro Zeit-/Ähnlichkeits-Cluster (typischerweise ein Foto-Moment auf einer Reise) wählt PhotoSort bis zu einer vom Nutzer angegebenen Anzahl N der besten Fotos aus, unter Berücksichtigung einer angestrebten Mischung aus Landschaft, Detailaufnahme und Menschen. Läuft vollständig lokal (kein Cloud-Vision-Aufruf) — ein ursprünglich angedachter Cloud-Ansatz wurde im Sharpening-Gespräch bewusst verworfen, siehe ADR 0015 und Abschnitt "Entscheidungen".

## User Story

Als Nutzer (Daniel oder seine Frau) möchte ich für die Fotos eines Zeit-/Ähnlichkeits-Clusters eine von mir festgelegte Anzahl der besten Fotos als echte positive Empfehlung vorgeschlagen bekommen — unter Berücksichtigung einer guten Mischung aus Landschaft, Detailaufnahmen und Menschen — damit ich beim Zusammenstellen eines Reisealbums nicht mehr nur die schlechtesten Fotos aussortiert bekomme, sondern eine tatsächliche Vorauswahl der besten Kandidaten pro Anlass erhalte.

## Akzeptanzkriterien

- [ ] Der Nutzer kann vor dem Start eine Zielanzahl N **pro Cluster** angeben (nicht global über die gesamte Fotomenge) — `POST /projects/{id}/select-top` (Body `{"top_n_per_cluster": int}`), serverseitig validiert (`Field(ge=1, le=10)`, nicht nur clientseitig begrenzt).
- [ ] `POST /projects/{id}/select-top` legt einen `TopSelectionRun` (Status `running`) an und enqueued den `select_top_photos`-Job; Antwort `202 Accepted`. Ohne gültiges Token: `401`. Existiert kein `ScoringRun` mit `status=success` für das Projekt: `409`. Ist `settings.category_selection_enabled == False`: `403`.
- [ ] `TopSelectionRun.photos_processed`/`photos_total` werden während der Verarbeitung periodisch zwischen-committet (Live-Fortschritt, analog `ScoringRun`); `ProjectOut` bekommt `last_top_selection_run`, analog `last_scoring_run`.
- [ ] Pro Cluster wird ein begrenzter Kandidatenpool gebildet (`min(cluster_size, max(top_n_per_cluster * 3, 6))`, sortiert nach `local_quality_score`), nur für Fotos mit `suggested_status IS NULL` (Phase-A-Überlebende — weder Duplikat-Verlierer noch zu unscharf).
- [ ] Jedes Kandidatenfoto wird lokal klassifiziert (`classification.py::classify_category`, deterministische Prioritätskette): Gesicht erkannt (mediapipe Face Detector, lokal/CPU-only) → `PEOPLE`; sonst hoher "Uniform-Flächen-Anteil" (Pillow-Heuristik, Laplace-Varianz-Raster) → `LANDSCAPE`; sonst → `DETAIL` (Fallback). Ergebnis landet in `PhotoScore.category`, bei jedem Lauf neu berechnet.
- [ ] Innerhalb eines Clusters wird N per `divmod` auf die dort tatsächlich vorhandenen Kategorien verteilt (feste Reihenfolge `LANDSCAPE`, `DETAIL`, `PEOPLE`), pro Kategorie werden bis zur Quote die Fotos mit dem höchsten `local_quality_score` gewählt (Tie-Break: niedrigere `photo_id`). Treffer bekommen `suggested_status = ALBUM_WORTHY`, `SuggestionOut.reason = "top_pick"`.
- [ ] Reicht eine Kategorie innerhalb eines Clusters nicht für ihre Quote, wird **nicht** aus anderen Kategorien nachgezogen — die tatsächliche Trefferzahl kann unter N bleiben, kein künstliches Auffüllen.
- [ ] Ort/Standort fließt nicht in die Auswahl ein (kein GPS-Feld im System, siehe Out of Scope).
- [ ] Bestätigungsmuster wie Phase A: ein Vorschlag ist unverbindlich, bis er über den bestehenden `PUT /photos/{id}/rating` aktiv bestätigt wird; kein Codepfad in `select_top_photos`/`classify_category`/`select_top_n_with_category_mix` schreibt eine `Rating`-Zeile.
- [ ] Ein einzelner fehlgeschlagener Klassifikationsversuch (z.B. defekte Cache-Datei) bricht den Lauf nicht ab (best-effort pro Foto, analog `scoring.py`) — das betroffene Foto bleibt ohne `category` und fließt nicht in `select_top_n_with_category_mix` ein.
- [ ] Ein erneuter Phase-A-Lauf (`run_project_scoring`) setzt `suggested_status` aller verarbeiteten Fotos zurück, bevor er ggf. neue `REJECTED`-Werte setzt — löscht dadurch auch alte `ALBUM_WORTHY`-Markierungen aus dieser Spec. Beabsichtigt: `cluster_key` wird bei jedem Phase-A-Lauf neu vergeben, eine alte Top-Auswahl bezieht sich sonst auf nicht mehr gültige Cluster.
- [ ] Trigger "Top-Fotos auswählen" auf der Projekt-Detailseite, klar getrennt vom (umbenannten) Phase-A-Trigger "Ausschuss aussortieren" — kein Kostenschätzungs-Zwischenschritt, da rein lokal und kostenlos.
- [ ] Kategorie wird als zweiter, von der Bewertungs-Badge getrennter Chip (Kürzel L/D/M) auf Grid-Kachel **und** in der Detailansicht gezeigt. Eine grobe, verständliche Qualitäts-Einordnung (3 Stufen, aus `local_quality_score` abgeleitet, kein Rohwert) wird zusätzlich in der Detailansicht gezeigt, nicht auf der Grid-Kachel.

## Datenmodell-Bezug

`PhotoScore` bekommt additiv `category: PhotoCategory | None` (neues Enum: `LANDSCAPE`/`DETAIL`/`PEOPLE`). Neue Tabelle `TopSelectionRun` (analog `ScoringRun`): `project_id`, `status`, `started_at`/`finished_at`, `top_n_per_cluster`, `candidates_total`/`candidates_processed`, `suggestions_found`, `error_message`. Kein neues Ästhetik-Feld — das Ranking innerhalb einer Kategorie nutzt den bereits vorhandenen `local_quality_score` aus Phase A (Spec 0003). `suggested_status` (wiederverwendet `RatingStatus`) bekommt mit `ALBUM_WORTHY` erstmals einen produktiv gesetzten positiven Wert (Phase A setzt praktisch nur `REJECTED`). Das bestehende `Rating`-Modell bleibt vollständig unangetastet, siehe [`docs/architecture.md`](../../docs/architecture.md).

## Architektur / Umsetzung

**Bezug:** [`decisions/0002-hybrid-ai-scoring.md`](../decisions/0002-hybrid-ai-scoring.md), [`decisions/0006-local-scoring-datamodel.md`](../decisions/0006-local-scoring-datamodel.md), [`decisions/0015-lokale-kategorie-klassifikation.md`](../decisions/0015-lokale-kategorie-klassifikation.md), [`features/0003-automatic-best-photo-selection.md`](./0003-automatic-best-photo-selection.md)

### Datenmodell

- **`PhotoScore`**: additive Migration, nur `category: PhotoCategory | None` neu.
- **`TopSelectionRun`** (neu, analog `ScoringRun`, wiederverwendet `ScanStatus`): `project_id`, `status`, `started_at`, `finished_at`, `top_n_per_cluster`, `candidates_total`/`candidates_processed` (Live-Fortschritt — mediapipe-Inferenz hat spürbare Laufzeit pro Foto, deshalb weiterhin ein eigener, asynchroner Job statt synchroner Verarbeitung), `suggestions_found`, `error_message`.
- **`category` wird nicht in Phase A mitberechnet**, sondern erst im neuen `select-top`-Job, nur für den bereits begrenzten Kandidatenpool pro Cluster — sonst würde mediapipe für jedes gescannte Foto laufen (auch für nie betrachtete Duplikat-Verlierer), was Phase As dokumentierte Schnelligkeit unnötig belasten würde. `category` wird bei jedem `select-top`-Lauf neu berechnet (kein Reuse-Tracking nötig, da kostenlos).
- Interaktion mit Phase-A-Rescoring wie im Akzeptanzkriterium beschrieben: ein erneuter Phase-A-Lauf setzt `suggested_status` (inkl. `ALBUM_WORTHY`) zurück, da `cluster_key` neu vergeben wird.

### Backend / Worker

- **Neues Modul `backend/src/photosort/classification.py`** (bewusst getrennt von `scoring.py`, damit die `mediapipe`-Abhängigkeit nicht in den leichten Phase-A-Importpfad einsickert):
  - `detect_person(image, detector) -> bool` — mediapipe Face Detector Task-API (`mediapipe.tasks.python.vision.FaceDetector`, nicht die veraltete Solutions-API) auf der bereits gecachten `display`-Variante, dokumentierter Konfidenz-Schwellwert.
  - `compute_uniform_area_fraction(image) -> float` — Kachel-Raster (8×8) + Laplace-Kernel-Varianz pro Kachel (reuse der Technik aus `scoring.py::compute_sharpness`), Anteil der Kacheln unterhalb eines niedrigen Schwellwerts.
  - `classify_category(image, detect_person=detect_person) -> PhotoCategory` — deterministische Prioritätskette: Gesicht → `PEOPLE`; sonst hoher Uniform-Flächen-Anteil → `LANDSCAPE`; sonst → `DETAIL` (Default-Fallback). `detect_person` als injizierbarer Parameter für Testbarkeit ohne echtes mediapipe-Modell.
  - `select_top_n_with_category_mix(candidates, n) -> list[int]` — pure, DB-freie Funktion (analog `assign_time_clusters`): Kategorie-Quotenverfahren wie in den Akzeptanzkriterien beschrieben.
- **Neuer Job `select_top_photos(ctx, project_id, top_n_per_cluster)`** in `worker.py`: Guard (letzter `ScoringRun` muss `success` sein), lädt `PhotoScore`-Zeilen mit `suggested_status IS NULL`, gruppiert nach `cluster_key`, bildet Kandidatenpool pro Cluster, klassifiziert jeden Kandidaten (best-effort pro Foto), wendet `select_top_n_with_category_mix` pro Cluster an, setzt `ALBUM_WORTHY`.

### API

- `POST /projects/{id}/select-top` (Body `{"top_n_per_cluster": int}`) — `403` wenn `settings.category_selection_enabled == False`, `409` ohne erfolgreichen `ScoringRun`, sonst `TopSelectionRun` anlegen + Job enqueuen, `202`.
- `GET /projects/{id}` (`ProjectOut`) bekommt `last_top_selection_run: TopSelectionRunSummary | None`, analog `last_scoring_run`.
- `SuggestionOut` (`api/photos.py`) bekommt `category: PhotoCategory | None`; `reason`-Literal um `"top_pick"` erweitert (additiv).

### Konfiguration

- Neu: `settings.category_selection_enabled: bool = True` (Default **an** — rein lokal/kostenlos, kein Grund für einen restriktiven Default wie bei einem Cloud-Feature).
- `mediapipe`-Python-Paket als neue Backend-Abhängigkeit (`backend/pyproject.toml`). Das benötigte `.tflite`-Face-Detector-Modell wird zur Build-Zeit ins Docker-Image gebündelt (gepinnte Version), kein Laufzeit-Download vom Worker aus (siehe Security-Abschnitt).
- **Vor der Umsetzung zu verifizieren** (siehe ADR 0015, Konsequenzen): `mediapipe` muss auf der tatsächlichen Ziel-Architektur des Homeservers installierbar sein; Fallback-Option (OpenCV-Haar-Kaskaden) ist dokumentiert, falls nicht.

## UI/UX

Design-System: [`architecture/0004-design-system.md`](../architecture/0004-design-system.md) — für diese Spec ergänzt um die Muster "Nicht verfügbare Aktion (Feature-Flag/Vorbedingung)", "Kategorie-Kennzeichnung" (3 Kategorien) und "Grobe Qualitäts-Einordnung statt Rohwert" (Details siehe dort).

- **Benennung/Anordnung (`ProjectDetailPage.tsx`):** bestehender Phase-A-Trigger wird umbenannt ("Beste Fotos automatisch vorschlagen" → **"Ausschuss aussortieren"**, Busy-Label "Wird aussortiert…"). Neue, eigenständige Section darunter mit Button **"Top-Fotos auswählen"** (Busy-Label "Wird ausgewählt…") — bewusst nicht "Phase B"/"Cloud" genannt (läuft vollständig lokal). Kurzer Beschreibungstext: "Ordnet Fotos automatisch einer Kategorie zu (Landschaft/Detail/Menschen) und wählt pro Foto-Moment bis zu N Top-Fotos aus — läuft vollständig lokal auf diesem Server."
- **Verfügbarkeitsgate:** `category_selection_enabled === false` → Eingabe/Button dauerhaft `disabled`, Text "Diese Funktion ist derzeit nicht aktiviert." `last_scoring_run?.status !== 'success'` → ebenfalls `disabled`, Text "Führe zuerst die lokale Vorauswahl oben aus." Bereich bleibt in beiden Fällen an derselben Stelle sichtbar (kein verschwindender UI-Teil), proaktiv aus bereits geladenen Projektdaten abgeleitet statt erst nach einem 403/409.
- **Ablauf (kein Kostenschätzungs-Schritt, da nichts kostenpflichtig):** Zahlenfeld "Top-Fotos pro Foto-Moment" (`min=1`, `max=10`, Default 3) mit Hilfetext, der ein mögliches Unterschreiten von N proaktiv erklärt ("Pro Foto-Moment werden bis zu N Top-Fotos vorgeschlagen (weniger, falls nicht genug passende Motive vorhanden sind)."), direkt daneben Button "Auswahl starten" — ein Klick löst den Lauf unmittelbar aus.
- **Lauf + Fortschritt:** bestehendes Muster "Determinierter Fortschritt bei hochfrequenten Zählern" (`<progress>` + "X von Y Fotos verarbeitet" + auf 10%-Schritte gedrosseltes `aria-live`), analog zur bestehenden Scoring-Fortschrittsanzeige in derselben Datei/Section.
- **Ergebnis:** "{n} Top-Fotos ausgewählt" — kein Vergleich zur angeforderten Ziel-Anzahl N, damit ein Unterschreiten (fehlende Kategorie-Vielfalt im Cluster) wie ein normales Ergebnis wirkt, nicht wie ein Fehler.
- **Fehler:** `status === 'failed'` → bestehendes `Alert`-mit-Retry-Muster, unverändert.
- **Kategorie (Grid + Detail):** zweiter, von `RatingBadge` getrennter Chip (`Badge tone="neutral"`) für die 3 Kategorien — Kürzel **L/D/M** (Landschaft/Detail/Menschen). Auf der Grid-Kachel (`PhotoGridPage.tsx`) als Kürzel in der Gegenecke zur `RatingBadge`, ausgeschriebener Name nur via `aria-label`/`title`; in `PhotoDetailPage.tsx` ausgeschrieben als Teil der bestehenden Vorschlags-Kurzbegründung. Folgt derselben Sichtbarkeitsregel wie die Vorschlags-Badge (verschwindet nach Bestätigung).
- **Bildqualität (nur Detailansicht, neues Muster):** kein Rohwert, sondern eine grobe, verständliche 3-Stufen-Einordnung ("Einfache"/"Gute"/"Hohe Bildqualität"), abgeleitet aus `local_quality_score` über feste, dokumentierte Schwellwerte. Darstellung: neutrales Drei-Punkte-Meter (`●●●`/`●●○`/`●○○`, `aria-hidden`) + ausgeschriebener, screenreader-sichtbarer Stufenname — bewusst kein Stern (Kollision mit `favorite`-★), keine Prozess-Status-Farbe. Teil derselben Kurzbegründungszeile wie die Kategorie, z.B. "Automatischer Vorschlag: Album-würdig — Kategorie: Landschaft · Bildqualität: hoch". Nicht auf der Grid-Kachel.
- **Zustände:** *Nicht verfügbar* (Flag aus/Vorbedingung fehlt) · *Eingabe* · *Ladend* (Live-Fortschritt) · *Erfolg* (inkl. "N unterschritten"-Fall ohne Fehler-Optik) · *Fehler* (Retry).
- **Responsivität/PWA:** Kategorie-Chip und Qualitäts-Meter erfüllen dieselbe 44×44px-Touch-Ziel-Vorgabe bzw. brechen auf Schmalbildschirm ohne horizontales Scrollen um.

## Security

**Sicherheitsrelevant:** Ja, aber schlank — kein Datenversand, kein neues Secret, keine neue Vertrauensgrenze (siehe ADR `decisions/0015-lokale-kategorie-klassifikation.md`: Klassifikation läuft vollständig lokal, keine Bilddaten verlassen den Server).

- **Autorisierung:** `POST /projects/{id}/select-top` hängt am selben Router-Torwächter (`dependencies=[Depends(get_current_user)]`) wie `/scan`/`/score` — Muss-Kriterium, kein neuer Auth-Pfad.
- **Neue Abhängigkeit `mediapipe`:** Apache-2.0, aktiv gepflegt, keine bekannten kritischen offenen CVEs zum jetzigen Stand. **Modell-Asset-Bezug (Muss-Kriterium):** Das `.tflite`-Face-Detector-Modell wird zur Build-Zeit ins Docker-Image gebündelt (gepinnte Version), kein Laufzeit-Download vom Worker aus einer externen CDN-URL — vermeidet eine neue Laufzeit-Außenverbindung und ein Integritätsrisiko durch fehlende Prüfsummen-Verifikation bei einem Laufzeit-Download.
- **Lokale Bildverarbeitung (bestehendes projektweites Prinzip):** mediapipe-Inferenz und die neue Pillow-Heuristik laufen wie die bestehenden Phase-A-Berechnungen auf der bereits gecachten `display`-Variante, pro Foto in einem best-effort-`except Exception`-Block — kein neues Muster, nur eine weitere Anwendung des bestehenden Grundsatzes aus `architecture/0003-securitykonzept.md`.
- **Keine neue Angriffsfläche für Datenversand/Secrets:** kein API-Key, keine externe Schnittstelle, keine Kostenanzeige.

`architecture/0003-securitykonzept.md` wird durch diese Spec nicht ergänzt — keine neue Angriffsflächen-Klasse, nur Anwendung bestehender Prinzipien plus der Modell-Bundling-Hinweis oben, der beim Implementierungs-Review zu bestätigen ist.

## Teststrategie

- *Unit-Ebene* (`backend/tests/test_classification.py`, analog `test_scoring.py`): `compute_uniform_area_fraction` gegen synthetische Pillow-Bilder (uniform → Anteil nahe 1.0, texturiert/Noise → nahe 0.0, halb/halb → ≈0.5); `classify_category` mit `detect_person` als injiziertem Fake (`lambda img: True/False`) für alle drei Prioritätszweige, ohne echtes mediapipe-Modell; `detect_person`s eigene Entscheidungslogik (Konfidenz-Schwellwert) separat mit einem `FakeFaceDetector` getestet — die echte Modellkonstruktion läuft in keinem automatisierten Test (Infrastruktur-/CI-Risiko). `select_top_n_with_category_mix`: `divmod`-Verteilung über 3 Kategorien (feste Reihenfolge LANDSCAPE/DETAIL/PEOPLE), Tie-Break, "nur 1 Kategorie vorhanden", "Quote reicht rechnerisch, Kategorie hat zu wenige Fotos → kein Nachziehen" (Kernfall), `N > Clustergröße`, Cluster mit 1 Foto.
- *Integrations-Ebene* (`backend/tests/test_worker_top_selection.py`, echte In-Memory-SQLite, echte Cache-Dateien): Guard bei fehlendem erfolgreichen `ScoringRun`; best-effort bei einzelnem Klassifikationsfehler (Job läuft trotzdem bis `success`, betroffenes Foto bleibt ohne `category`); Zurücksetzen von `ALBUM_WORTHY` durch erneutes Phase-A-Rescoring; `category` wird bei jedem Lauf neu berechnet (kein Skip-Mechanismus).
- *API-Ebene* (`backend/tests/test_api_top_selection.py`): `403` bei `category_selection_enabled=False` **und** expliziter Test des Defaults `True`; `409` ohne erfolgreichen `ScoringRun`; `202`/`401` wie gehabt; `top_n_per_cluster` außerhalb 1–10 → `422`. `SuggestionOut`-Serialisierung (`category`, `reason="top_pick"`).
- *Frontend:* neuer Trigger-Bereich getrennt von Phase A (Zahleneingabe-Validierung, Start/Fortschritt/Ergebnis ohne Kostenschritt), Verfügbarkeitsgate (`disabled` + Erklärtext statt Fehler-Toast), Kategorie-Chip (Grid + Detail), Qualitäts-Meter nur in Detailansicht (Negativ-Assertion für Grid-Kachel).
- **Bewusst nicht getestet:** reale Erkennungsgüte von mediapipe (Falsch-Negative auf echten Gesichtern) — akzeptierte Fehlerrate, bleibt manueller Smoke-Test vor Merge mit ein paar echten (nicht eingecheckten) Testfotos, kein Foto-Korpus im Repo (konsistent mit dem Kalibrierungs-Vorbehalt aus Spec 0003).
- `specs/architecture/0002-testkonzept.md` wird nach der Umsetzung um einen neuen Abschnitt "Lokale ML-Inferenz (mediapipe) in Tests" ergänzt (Collaborator-Funktion als Parameter injizieren statt echtes Modell, reale Modellkonstruktion nie in `pytest` aufgerufen).

## Entscheidungen (2026-08-07, im Idea-Sharpening-Gespräch mit Daniel geklärt)

- **Ziel-Anzahl N ist pro Cluster, nicht global:** Daniel hat sich explizit für die Fortführung der ursprünglichen Roadmap-Vorentscheidung entschieden ("Top-Kandidaten pro Cluster, nutzereinstellbar"), obwohl der ursprüngliche Inbox-Rohtext eher nach einer globalen Gesamtzahl klang.
- **Kurswechsel weg von Cloud-Vision:** Ein erster Architektur-Entwurf sah einen Cloud-Vision-LLM-Aufruf (Anthropic) für Ästhetik-Bewertung und Kategorie-Klassifikation vor (siehe ursprünglicher ADR-0015-Entwurf, nie gemergt). Daniel hat das gestoppt, als der `security-engineer` nach dem Einwilligungsmechanismus für den Bilddatenversand gefragt hat: "vorerst keine remote Modelle verwenden. Der erste Ansatz sollte sein, es entweder ohne KI-Modelle zu schaffen, oder lokale Modelle zu verwenden." ADR 0015 wurde daraufhin vollständig neu geschrieben (lokal statt Cloud) statt als Superseded-Kette geführt, da der Cloud-Entwurf nie akzeptiert/committet war.
- **"Sehenswürdigkeit" für v1 gestrichen:** Von ursprünglich vier auf drei Kategorien reduziert (Landschaft/Detail/Menschen) — lokale Landmark-Erkennung ist ohne GPS (explizit out-of-scope) oder ein schweres, für private Reisefotos unzuverlässiges Modell nicht sinnvoll umsetzbar. Empfehlung des `architect`-Agenten, von Daniel bestätigt.
- **Ort/GPS explizit out-of-scope:** kein GPS-Feld im System, keine EXIF-GPS-Extraktion — diese Spec nutzt nur den Aufnahmezeitpunkt (über das bestehende Zeitfenster-Clustering aus Phase A). Separate Folge-Idee, sobald GPS-Daten verfügbar sind.
- **Kategorie-Mix darf die Zielanzahl unterschreiten lassen:** kein automatisches Nachziehen aus anderen Kategorien, wenn eine Kategorie zu wenige Fotos hat — lieber weniger Vorschläge als eine erzwungene, unpassende Mischung.
- **Ästhetik-/Qualitäts-Anzeige:** Ursprünglich hätte ein Cloud-LLM-Ästhetik-Score (0–10) angezeigt werden sollen. Nach dem Kurswechsel gibt es nur noch den intern vorhandenen `local_quality_score` (kein verständlicher Maßstab) — Daniel wollte weder den Rohwert noch gar keine Anzeige, sondern einen Kompromiss: eine grobe, verständliche Einordnung (3 Stufen) statt einer nackten Zahl, siehe UI/UX-Abschnitt.
- **Priorisierung:** Auf Nachfrage hat Daniel diese Spec in der Roadmap unter "Als Nächstes" eingeordnet, nach Spec 0008 (Automatisierte SemVer-Releases) — kein Verdrängen von bereits höher priorisierter Arbeit.
- **Keine Kostenanzeige/kein Kostenschätz-Endpunkt:** entfällt ersatzlos gegenüber der ursprünglichen Roadmap-Vorentscheidung für die (inzwischen überholte) Cloud-Variante — rein lokale Verarbeitung verursacht keine Geldkosten.

## Offene Fragen

Keine offenen Fragen mehr für den Scope dieser Spec. Vor der Umsetzung zu verifizieren (kein Blocker für die Spec-Freigabe, siehe Architektur-Abschnitt): `mediapipe`-Installierbarkeit auf der tatsächlichen Ziel-Architektur des Homeservers.

## Out of Scope

Ort/Standort-basierte Auswahlkriterien (kein GPS-Feld im System, separate Folge-Idee); Kategorie "Sehenswürdigkeit" (für v1 gestrichen, siehe Entscheidungen); eine künftige Cloud-Vision-Feinbewertung bleibt eine mögliche, spätere Option, falls sich die lokale Näherung als unzureichend erweist — dann eigene, neue Schärfungs-Session mit eigenem Security-/Einwilligungs-Abschnitt; globale Gesamtzahl statt pro-Cluster-Auswahl; Konfigurierbarkeit der Klassifikations-Schwellenwerte durch den Nutzer (feste, im Code dokumentierte Konstanten für dieses MVP).
