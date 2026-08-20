# 0051 - GPS-/Zeit-/Sehenswürdigkeit-basierte Clusterbildung mit gegenseitiger Herleitung

**Status:** Accepted
**Erstellt:** 2026-08-20
**Bezug:** [`inbox/0022-gps-zeit-clusterbildung-benannte-cluster.md`](../inbox/0022-gps-zeit-clusterbildung-benannte-cluster.md) (Ursprung, nach Anlage dieser Spec gelöscht), ADR [`decisions/0029-gps-landmark-cluster-bildung.md`](../decisions/0029-gps-landmark-cluster-bildung.md), [`features/0039-kuratierung-tage-und-benannte-cluster.md`](./0039-kuratierung-tage-und-benannte-cluster.md) (bestehende Tageszeit-Cluster-Anzeige, deren Out-of-Scope-Grenze hier gezielt aufgehoben wird), [`features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md`](./0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md) (Landmark-Erkennung, Accepted, noch nicht implementiert — diese Spec baut darauf auf), [`decisions/0021-kriterien-datenmodell-kuratierungs-pipeline.md`](../decisions/0021-kriterien-datenmodell-kuratierungs-pipeline.md) (gateführte Zwei-Phasen-Pipeline), Idea-Sharpening-Gespräch mit Daniel am 2026-08-20.

## Ziel

Die bestehende Cluster-Bildung auf `/curate` (Spec 0039) gruppiert Fotos ausschließlich nach Zeitfenstern (1h-Lücke). Das führt zu falsch zusammengefassten Clustern, wenn innerhalb einer Stunde tatsächlich mehrere Orte besucht wurden (z.B. zwei Sehenswürdigkeiten kurz hintereinander), und lässt eine mögliche Orts-Information ungenutzt, obwohl sie oft in den Fotos selbst (EXIF-GPS) oder über die Landmark-Erkennung (Spec 0047) bereits vorliegt.

Diese Spec erweitert die Cluster-BILDUNG selbst (nicht nur ihre Anzeige) um GPS-Nähe und erkannte Sehenswürdigkeiten als zusätzliche Signale, inklusive gegenseitiger Herleitung: Fotos ohne eigene GPS-Daten können anhand zeitlich benachbarter Fotos mit GPS im selben Cluster einen Ort für die Anzeige zugewiesen bekommen. Rein vorausschauende Erweiterung ohne konkret erlebten Auslöser — im Sharpening-Gespräch bewusst in voller Ausbaustufe bestätigt (siehe Entscheidungen).

## User Story

Als Nutzer (Daniel oder seine Frau) möchte ich, dass Fotos beim Kuratieren nicht nur nach Zeit, sondern auch nach Ort gruppiert werden, damit zeitlich nah beieinanderliegende, aber räumlich unterschiedliche Aufnahmen (z.B. zwei Sehenswürdigkeiten in einer Stunde) nicht fälschlich in einem Cluster landen, und die Cluster-Überschrift mir zeigt, wo ein Cluster entstanden ist.

## Akzeptanzkriterien

**GPS-Extraktion:**
- [ ] Beim Scan wird `Photo.gps_lat`/`Photo.gps_lon` als Dezimalgrad befüllt (inkl. korrekter Süd-/West-Vorzeichenumkehr aus `GPSLatitudeRef`/`GPSLongitudeRef`), wenn ein lesbares `GPSInfo`-EXIF-IFD vorhanden ist. Fehlt es oder ist es unlesbar, bleiben beide Felder `None` — ein einzelnes unlesbares Foto darf den Scan-Lauf nie abbrechen (`extract_gps`, analog `extract_taken_at`).

**Cluster-Bildung (Phase A, Zeit + GPS):**
- [ ] Zwei zeitlich aufeinanderfolgende Fotos mit je eigener GPS-Koordinate und Haversine-Distanz > `GPS_CLUSTER_SPLIT_DISTANCE_METERS` starten ein neues Cluster, auch wenn die Zeitlücke `TIME_CLUSTER_GAP` nicht überschritten ist.
- [ ] Ein Foto ohne eigene GPS-Koordinate löst nie selbst einen Split aus und wird beim Distanzvergleich übersprungen.
- [ ] `GPS_CLUSTER_SPLIT_DISTANCE_METERS` ist eine dokumentierte Modulkonstante in `scoring.py` (kein Settings-/Env-Wert, konsistent mit `TIME_CLUSTER_GAP`/`SHARPNESS_REJECT_THRESHOLD`).
- [ ] **Backward Compatibility:** Ohne jede GPS-Koordinate im Lauf ist das Ergebnis von `assign_clusters` `dict`-identisch zum bisherigen `assign_time_clusters`.

**Cluster-Verfeinerung (Phase 2, Landmark):**
- [ ] Ein Phase-A-Cluster mit ≥2 unterschiedlichen, nicht-null `landmark_name`-Werten (aus Spec 0047, sobald implementiert) wird in `PhotoRanking.cluster_key` weiter aufgeteilt (`refine_clusters_by_landmark`), exakter String-Vergleich, kein Fuzzy-Matching. `PhotoScore.cluster_key` wird dabei **nie** mutiert — bewusste, dokumentierte Divergenz beider Felder (analog `category_key`, ADR 0021).
- [ ] **Backward Compatibility:** Ohne Landmark-Daten ist `PhotoRanking.cluster_key` für jedes Foto `dict`-identisch zu `PhotoScore.cluster_key` (reiner Passthrough).
- [ ] Landmark-Verfeinerung ist strukturell blockiert, bis Spec 0047 implementiert ist — die reine Funktion `refine_clusters_by_landmark` selbst ist unabhängig davon entwickel- und testbar.

**Gegenseitige Herleitung (Anzeige, nicht persistiert):**
- [ ] Ein GPS-loses Foto bekommt für die Anzeige die Koordinate des zeitlich nächsten GPS-tragenden Fotos im selben finalen Cluster zugewiesen, sofern eines existiert; sonst bleibt kein Ort hergeleitet.

**Cluster-Anzeige (`/curate`):**
- [ ] Cluster-Überschrift zeigt Ort **und** Tageszeit gemeinsam (Ort ergänzt, ersetzt nicht): `"<Ort> · <Tageszeit> (<Zeitspanne>)"`.
- [ ] Priorität der Ortsdarstellung: (1) Landmark-Name, falls vorhanden → (2) grobe GPS-Koordinate (2 Nachkommastellen, eigene oder hergeleitete) → (3) kein Ort, reine Tageszeit-Bezeichnung wie bisher (Spec 0039, unverändert).
- [ ] **"Mehrere Orte"**-Anzeige (Sonderfall der GPS-Fallback-Stufe, siehe Entscheidungen): tritt auf, wenn ein Cluster keinen Landmark-Namen hat, aber Fotos mit unterschiedlichen, nicht auf dieselbe gerundete 2-Nachkommastellen-Koordinate fallenden GPS-Werten (eigene oder hergeleitete) enthält.
- [ ] API (`PhotoOut`/`RankingOut`) liefert `gps_lat`/`gps_lon` in voller EXIF-Präzision, keine serverseitige Rundung (siehe Entscheidungen) — Rundung auf 2 Nachkommastellen ist reine Frontend-Anzeigeableitung.

## Datenmodell-Bezug

Additive Migration: zwei neue `Photo`-Spalten `gps_lat: float | None`, `gps_lon: float | None`. `PhotoRanking.cluster_key` kann ab jetzt feiner unterteilt sein als `PhotoScore.cluster_key` (bewusste Divergenz, siehe ADR 0029/0021). Siehe [`docs/architecture.md`](../../docs/architecture.md) (wird von `architect` bei Umsetzung ergänzt).

## Architektur / Umsetzung

Siehe [`decisions/0029-gps-landmark-cluster-bildung.md`](../decisions/0029-gps-landmark-cluster-bildung.md) (Accepted) für die vollständige Begründung. Zusammenfassung:

- **Zweiphasige Cluster-Bildung statt Pipeline-Umbau, kein neuer Job:**
  - **Phase A** (`run_project_scoring`, unverändert früher Zeitpunkt): `scoring.py::assign_time_clusters` → erweitert zu `assign_clusters` — Split bei Zeitlücke `TIME_CLUSTER_GAP` **oder** GPS-Sprung > `GPS_CLUSTER_SPLIT_DISTANCE_METERS` (Haversine, Stdlib `math`, keine neue Abhängigkeit). Schreibt wie bisher nach `PhotoScore.cluster_key` — die Phase-A-Ownership-Grenze aus ADR 0021 bleibt unangetastet.
  - **Phase 2** (`run_criterion_scoring`, unverändert später Zeitpunkt, nach dem Ausschuss-Gate, an derselben Stelle wie `derive_active_categories`, Präzedenzfall ADR 0023): neue reine Funktion `refine_clusters_by_landmark(base_cluster_key_by_photo, landmark_name_by_photo)` ersetzt den bestehenden Passthrough beim Aufbau von `PhotoRanking.cluster_key`.
- **GPS-Extraktion:** neues `opencloud/exif.py::extract_gps` (Pendant zu `extract_taken_at`), liest aus demselben bereits per Range-Read geladenen EXIF-Fenster — kein zusätzlicher Netzwerk-Overhead.
- **Distanzberechnung:** Haversine, Stdlib `math`, keine neue Abhängigkeit.
- **Reverse-Geocoding (Koordinaten → Ortsname wie "Paris") ist explizit Out-of-Scope** — eigene, künftige Spec mit eigener Security-Konsultation (neue externe Abhängigkeit, sensiblere Datenexposition).

**Betroffene/neue Dateien:** `backend/src/photosort/models.py` (+ Alembic-Migration), `backend/src/photosort/opencloud/exif.py` (`extract_gps`), `backend/src/photosort/worker.py` (`_fetch_and_thumbnail`, `run_project_scoring`, `run_criterion_scoring`), `backend/src/photosort/scoring.py` (`assign_time_clusters`/`TimeClusterCandidate` → `assign_clusters`/`ClusterCandidate`, Haversine-Hilfsfunktion, `refine_clusters_by_landmark`), `backend/src/photosort/api/photos.py` (`PhotoOut`/`RankingOut`-Erweiterung), `frontend/src/utils/timeOfDay.ts` (`formatClusterHeading`), `frontend/src/pages/CurateCategoriesPage.tsx`, `docs/architecture.md` (Ergänzung nach Umsetzung).

**Reihenfolge der Umsetzung (Empfehlung des `architect`):** GPS-Anteil (Migration, `extract_gps`, `assign_clusters`, Haversine) ist vollständig unabhängig von Spec 0047 umsetzbar und deckt AK1/AK2/AK4/AK6/AK7 (GPS-Anteil) bereits ab. Landmark-Verfeinerung (`refine_clusters_by_landmark`, Verdrahtung) ist strukturell blockiert, bis Spec 0047 implementiert ist — die reine Funktion selbst kann isoliert vorher entwickelt/getestet werden.

## UI/UX

Sichtbare Oberfläche vorhanden (`ux-ui-designer`-Konsultation, 2026-08-20) — die Cluster-Überschrift (`<h3>`) auf `/curate` wird um optionale Orts-/Landmark-Information ergänzt.

**Neue Cluster-Überschrift mit Orts-Kontext**, Format `"<Ort> · <Tageszeit> (<Zeitspanne>)"`, Tageszeit bleibt immer sichtbar (ergänzt, nicht ersetzt):
- Mit Landmark (höchste Priorität): `"Eiffelturm · Nachmittags (12:00–14:00 Uhr)"`
- Mit nur GPS verfügbar (2 Nachkommastellen): `"48.86, 2.29 · Nachmittags (12:00–14:00 Uhr)"`
- Mehrere unterschiedliche, nicht auf dieselbe gerundete Koordinate fallende GPS-Werte im selben Cluster ohne Landmark (Grenzfall, siehe Entscheidungen): `"Mehrere Orte · Nachmittags (12:00–14:00 Uhr)"`
- Keine Orts-Info vorhanden (Fallback, unverändert): `"Nachmittags (12:00–14:00 Uhr)"`

**Umsetzungsort:** `formatClusterHeading()` in `frontend/src/utils/timeOfDay.ts` wird erweitert — liefert künftig zusätzlich zur Tageszeit-Info die Orts-Information (bestimmt vom Backend-Cluster nach obiger Priorität), damit `CurateCategoriesPage.tsx` sie in die `<h3>` rendern kann. Die Tageszeit-Berechnung selbst bleibt unverändert.

**Typografie & Layout:** unverändert (`<h3>`, `text-lg`, `text-text-h`). Trennzeichen zwischen Ort und Zeit: Mittelpunkt " · " (nicht Komma, um Verwechslung mit Koordinaten-Dezimaltrennern zu vermeiden). Orts-Info ist Textpräfix, keine separate Zeile/Badge.

**Barrierefreiheit:** unverändert (semantisches HTML, keine speziellen `aria-label`-Anpassungen nötig).

**Design-System (`specs/architecture/0004-design-system.md`):** keine Ergänzung nötig — spezifische Seitenänderung, kein wiederverwendbares abstraktes UI-Muster (im Unterschied zu Busy Button/Leerer Zustand).

## Security

Sicherheitsrelevant, ja (`security-engineer`-Konsultation, 2026-08-20) — erstmalige Speicherung/API-Exposition von Standortdaten (GPS aus EXIF) im Projekt. Verifiziert: `thumbnails.py::generate_variants` verwirft beim Neuschreiben der Thumbnail-/Display-Varianten alle EXIF-Metadaten inkl. GPS — `GET /photos/{id}/image` liefert heute **keine** GPS-Daten. Die neuen `Photo.gps_lat`/`.gps_lon`-Felder und ihre API-Exposition sind damit der **erste** Kanal, über den Standortdaten aus Familienfotos das System überhaupt verlassen. Vollständige Herleitung siehe `specs/architecture/0003-securitykonzept.md`.

**EXIF-GPS-Parsing-Robustheit (Muss-Kriterium):** `extract_gps` muss denselben best-effort/breiten-`except Exception`-Vertrag wie `extract_taken_at` einhalten — GPS-IFD-Parsing ist strukturell fehleranfälliger (verschachteltes `IFD.GPSInfo`, `IFDRational`-Werte mit potenziellem Nenner 0, fehlende `GPSLatitudeRef`/`GPSLongitudeRef`, unvollständiges Range-Read-Fenster). Ein einzelnes unlesbares Foto darf einen Scan-Lauf nie abbrechen.

**Kein neuer Auth-/Endpunkt-Pfad:** reine Feld-Erweiterung von `PhotoOut`/`RankingOut` am bestehenden, router-weit `get_current_user`-geschützten `GET /projects/{id}/photos`. Keine neue Nutzereingabe, keine Injection-Fläche, keine neue Sichtbarkeitsasymmetrie zwischen den beiden Nutzern (konsistent mit dem "kein Innentäter-Modell"-Grundsatz).

**Kein SSRF, keine neue Netzwerkverbindung:** GPS teilt sich das bereits geladene Range-Read-Fenster mit `taken_at`, Haversine läuft rein lokal.

**Explizit geprüft: keine Kombination mit der Cloud-Vision-API (Spec 0047).** GPS/EXIF wird nie an Anthropic übertragen (ADR 0029/0025) — die befürchtete Re-Identifikationskette "GPS + Landmark + Cloud-Transfer" tritt strukturell nicht ein.

**API-Präzision (Rückfrage an Daniel, im Sharpening-Gespräch beantwortet):** `security-engineer` hatte als offenen Punkt markiert, ob die API-Antwort selbst auf ~1km-Präzision begrenzt werden sollte (Defense in Depth gegen ein gestohlenes JWT) oder volle EXIF-Präzision liefert (Rundung bleibt reine Frontend-Anzeige). Daniel hat sich für **volle Präzision über die API** entschieden — mehr Flexibilität für mögliche künftige Features (z.B. echte Kartenansicht), das bestehende, bereits akzeptierte JWT-Diebstahl-Restrisiko wird dadurch in der Datenschutz-Dimension verschärft (zusätzlich zum Fotozugriff auch exakte Standortdaten, potenziell die Wohnadresse) — analog zur bereits dokumentierten Kostenkontroll-Eskalation bei Spec 0047, hier bewusst akzeptiert statt serverseitig gehärtet.

`specs/architecture/0003-securitykonzept.md` wurde im Rahmen dieser Konsultation bereits um einen Vorausschau-Abschnitt "Standortdaten (GPS aus EXIF, `exif.py::extract_gps`)" ergänzt.

## Teststrategie

Vollständig in `specs/architecture/0002-testkonzept.md` als neue Sektion **"GPS-Cluster-Split (Haversine) + isoliert entwickelte Landmark-Verfeinerung + `cluster_key`-Divergenz-Regressionstest"** festgehalten (`test-engineer`-Konsultation, 2026-08-20). Kernpunkte:

- **Unit (Schwerpunkt, `backend/tests/test_scoring.py`):** `assign_clusters` (GPS-Erweiterung der bestehenden `TestAssignTimeClusters`), private Haversine-Hilfsfunktion einzeln, `refine_clusters_by_landmark` komplett isoliert mit `dict[int, str | None]`-Fixtures (kein DB-/Spec-0047-Bezug nötig — reine Funktion vor einer noch nicht implementierten Spec entwickelt/getestet).
- **Unit (`backend/tests/test_exif.py`):** `extract_gps` analog `extract_taken_at` — Vorzeichen, fehlendes IFD, unlesbare Bytes, DMS→Dezimalgrad-Umrechnung an Referenzwert.
- **Integration (`backend/tests/test_worker_criterion_scoring.py`):** Divergenz-Regressionstest als Pflichtfall (`PhotoRanking.cluster_key` ≠ `PhotoScore.cluster_key` nach Landmark-Split, `PhotoScore.cluster_key` explizit unverändert geprüft), Passthrough-Regressionstest ohne Landmark-Daten.
- **Frontend (`vitest`):** `formatClusterHeading()`/`timeOfDay.ts` — reine Erweiterung des bestehenden Fixture-basierten Testansatzes aus Spec 0039, inkl. aller vier Anzeigezustände und dem "Mehrere Orte"-Grenzfall.
- **E2E/Smoke:** keiner (Projektkonvention) — Kalibrierung von `GPS_CLUSTER_SPLIT_DISTANCE_METERS` bleibt manueller Stichproben-Review durch Daniel.

**Relevante Edge Cases:** Haversine-Grenzfälle (Datumsgrenze/180°-Meridian, Antipoden, exakt auf der Schwelle), kombinierter Mitternacht+GPS-Sprung-Grenzfall, leere/fehlende GPS-Daten, `PhotoScore.cluster_key`-vs-`PhotoRanking.cluster_key`-Divergenz.

**Nicht automatisiert testbar (bekannte Lücke, dokumentiert):** `GPS_CLUSTER_SPLIT_DISTANCE_METERS` ist unkalibriert (gleiches etabliertes Muster wie `SHARPNESS_REJECT_THRESHOLD`/`HORIZON_*`); die volle Landmark-Integration kann bis zur Umsetzung von Spec 0047 nur auf Unit-Ebene mit synthetischen Landmark-Namen verifiziert werden, nicht End-to-End.

**Testkonzept ergänzt:** `specs/architecture/0002-testkonzept.md`, neue Sektion (siehe oben) plus neuer Eintrag unter "Bekannte Lücken".

## Entscheidungen (2026-08-20, im Idea-Sharpening-Gespräch mit Daniel geklärt)

- **Kern der Idee (Rückfrage im Sharpening-Gespräch):** GPS/Zeit/Landmark verändern die Cluster-BILDUNG selbst, nicht nur eine kosmetische Namenserweiterung wie in Spec 0039 — Daniel hat sich explizit für den größeren Eingriff entschieden.
- **Abhängigkeit zu Spec 0047 (Rückfrage im Sharpening-Gespräch):** diese Spec baut bewusst auf der noch nicht implementierten Landmark-Erkennung auf, statt unabhängig nur mit rohen GPS-Koordinaten zu arbeiten — Landmark-Verfeinerung bleibt bis zur Umsetzung von 0047 strukturell blockiert (siehe Architektur-Abschnitt), der GPS-Anteil kann unabhängig davon starten.
- **Devil's-Advocate-Ergebnis:** kein konkret erlebtes Problem (rein vorausschauend), Abhängigkeit von 0047, in der Praxis oft fehlende GPS-Daten, und ein zunächst identifizierter Pipeline-Architektur-Konflikt (Cluster-Bildung in einer frühen Phase, Landmark-Erkennung in einer späten, separaten Phase) wurden Daniel offen vorgelegt — er hat sich bewusst für die volle Idee trotz dieser Punkte entschieden, statt auf eine reduzierte GPS-only-Variante oder eine Zurückstellung auszuweichen.
- **Pipeline-Konflikt-Auflösung (an `architect` delegiert, "Du entscheidest wie"):** zweiphasige Cluster-Bildung ohne neuen Job/ohne Pipeline-Umbau (siehe ADR 0029) — `PhotoScore.cluster_key` (früh, Zeit+GPS) und `PhotoRanking.cluster_key` (spät, zusätzlich Landmark-verfeinert) dürfen bewusst divergieren, analog zur bereits bestehenden `category_key`-Trennung aus ADR 0021.
- **Reverse-Geocoding (an `architect` delegiert):** bewusst Out-of-Scope für diese Spec — neue externe Abhängigkeit + sensiblere Datenexposition, verdient eigene künftige Spec mit eigener Security-Konsultation.
- **Cluster-Überschrift-Aufbau (Rückfrage im Sharpening-Gespräch):** Ort ergänzt die Tageszeit-Angabe, ersetzt sie nicht — die Zeit-Orientierung aus Spec 0039 bleibt immer erhalten.
- **GPS-Anzeige-Präzision (Rückfrage im Sharpening-Gespräch):** grob, 2 Nachkommastellen (~1km) für die Frontend-Anzeige.
- **"Mehrere Orte"-Trigger-Präzisierung (von `test-engineer` aufgedeckter Widerspruch, vom Hauptagenten als rein technische Frage ohne Produkt-Trade-off direkt aufgelöst, keine erneute Rückfrage an Daniel nötig):** ursprünglich als "unterschiedliche Landmark-Namen im selben Cluster" definiert — das ist mit der Architektur unvereinbar, da `refine_clusters_by_landmark` ein Cluster ja gerade bei abweichenden Landmark-Namen aufteilt; ein finales Cluster enthält danach nie mehr als einen nicht-null-Landmark-Namen. Der Zustand ist stattdessen ausschließlich in der GPS-Fallback-Stufe (keine Landmark-Info, aber abweichende gerundete GPS-Koordinaten im Cluster) erreichbar und wurde entsprechend umformuliert.
- **API-GPS-Präzision (Rückfrage von `security-engineer` an Daniel, im Sharpening-Gespräch beantwortet):** volle EXIF-Präzision über die API statt serverseitiger Rundung auf ~1km — mehr Flexibilität für künftige Features (z.B. Kartenansicht), bewusst akzeptierte Verschärfung des bestehenden JWT-Diebstahl-Restrisikos in der Datenschutz-Dimension (siehe Security-Abschnitt).
- **Priorität — Niedrig (nach Schärfung bestätigt, `requirements-engineer`-Vorschlag aus Schritt 2 übernommen):** rein vorausschauend, kein akuter, von Daniel im Alltag bemerkter Missstand; strukturell blockiert bis Spec 0047 implementiert ist (für den Landmark-Anteil); GPS-Verfügbarkeit in der Praxis gemischt. Kein Konflikt mit bereits Geplantem — Niedrig ist nach Fertigstellung von Spec 0050 unbesetzt (0050 war der einzige andere Niedrig-Eintrag zum Zeitpunkt der Schärfung und ist inzwischen Implemented).

## Offene Fragen

Keine offenen Fragen mehr für den Scope dieser Spec.

## Out of Scope

- Reverse-Geocoding (Koordinaten → Klartext-Ortsname wie "Paris") — eigene, künftige Spec mit eigener Security-Konsultation.
- Änderung der Landmark-Erkennung selbst (Spec 0047) — diese Spec konsumiert nur deren Ergebnis (`landmark_name`).
- Persistierung der gegenseitig hergeleiteten Orte — rein In-Memory zur Anzeigezeit berechnet, günstig neu berechenbar.
- Serverseitige Rundung/Härtung der GPS-Präzision über die API — bewusst nicht gewünscht (Daniels Entscheidung, siehe Security-Abschnitt).
- Karten-/Geo-Visualisierung der Fotos — reine Textanzeige in der Cluster-Überschrift, kein Kartenwidget.
- Konfigurierbarkeit der Schwellenwerte über UI/Settings — reine Modulkonstanten im Code.
