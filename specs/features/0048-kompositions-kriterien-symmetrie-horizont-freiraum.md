# 0048 - Drei Kompositions-Kriterien: Symmetrie, Horizont-Neigung, Freiraum/Fluchtrichtung

**Status:** Accepted
**Erstellt:** 2026-08-19
**Bezug:** [`inbox/0023-kriterium-bildkomposition.md`](../inbox/0023-kriterium-bildkomposition.md) (Ursprung, nach Anlage dieser Spec gelöscht), ADR [`decisions/0026-modellwahl-symmetrie-horizont-freiraum-kriterien.md`](../decisions/0026-modellwahl-symmetrie-horizont-freiraum-kriterien.md), [`decisions/0022-lokale-modellwahl-tier-gebaeude-aesthetik-kriterien.md`](../decisions/0022-lokale-modellwahl-tier-gebaeude-aesthetik-kriterien.md) (Vorbild-Muster), [`features/0038-vier-zusaetzliche-kriterien-tier-gebaeude-schnitt-aesthetik.md`](./0038-vier-zusaetzliche-kriterien-tier-gebaeude-schnitt-aesthetik.md) (`goldener_schnitt` als strukturelles Vorbild), Idea-Sharpening-Gespräch mit Daniel am 2026-08-19.

## Ziel

PhotoSort hat bereits ein Kompositions-Kriterium (`goldener_schnitt`, Spec 0038: Motivposition an den Drittel-Schnittpunkten). Diese Spec ergänzt drei weitere, davon unabhängige Kompositions-Signale, die die bestehende Kriterien-Bewertungs-Pipeline (Spec 0037) um subtilere Qualitätsaspekte erweitern:

1. **Symmetrie/Balance** — Gesamtverteilung/Ausgewogenheit im Bild (nicht nur Motivposition).
2. **Horizont-/Kamera-Neigung** — erkennt einen schiefen Horizont.
3. **Freiraum/Fluchtrichtung** — bei Personen: genug Raum in Blickrichtung statt Motiv am Bildrand gedrängt.

Alle drei sind reine, lokal berechnete Ranking-Signale (`category_eligible=False`), analog zu `goldener_schnitt`/`sharpness`/`exposure`/`aesthetics` — keine neuen Kuratierungs-Kategorien.

## User Story

Als Nutzer (Daniel oder seine Frau) möchte ich, dass die automatische Foto-Bewertung zusätzliche Kompositionsqualitäten (Balance, gerader Horizont, Freiraum in Blickrichtung) berücksichtigt, damit die kuratierte Top-Foto-Auswahl auch subtilere Kompositions-Schwächen (schiefer Horizont, gedrängtes Motiv, unausgewogener Bildaufbau) erkennt, die über die reine Motivposition hinausgehen.

## Akzeptanzkriterien

**Registrierung (alle drei):**
- [ ] Drei neue `CRITERIA_REGISTRY`-Einträge (`backend/src/photosort/criteria.py`): `symmetrie` (`source=local_heuristic`), `horizont` (`source=local_heuristic`), `freiraum` (`source=local_ml`) — alle `category_eligible=False`.
- [ ] Alle drei Compute-Funktionen geben `float ∈ [0, 1]` zurück (`clip(..., 0, 1)`).
- [ ] Best-effort: ein fehlgeschlagenes Kriterium bricht den `CriterionScoringRun` nicht ab, bleibt für das betroffene Foto ungeschrieben, die übrigen Kriterien bleiben unberührt.

**Symmetrie (`classification.py::compute_symmetry_score`):**
- [ ] Quadranten-Energie-Vergleich auf der bereits vorhandenen Laplace-Kantenkarte (`_laplace_edges_without_border_artifact`), `score = clip(1.0 - (horizontal_diff + vertical_diff) / 2, 0, 1)`.
- [ ] Komplett flächiges Bild (Gesamtenergie 0) → `score == 1.0` (dokumentiert, kein Bug).
- [ ] Extrem asymmetrisches Bild (Energie nur in einem Quadranten) → `score` deutlich unter 0.5.
- [ ] Perfekt symmetrisches, texturiertes Bild → `score == 1.0`.
- [ ] Ungerade Bildmaße (Breite/Höhe nicht durch 2 teilbar): gleiche Rundungsregel wie `compute_uniform_area_fraction`s Kachelraster (`width // 2`, letzter Bereich nimmt den Rest), durch Testfall gepinnt.
- [ ] Keine neue Abhängigkeit.

**Horizont (`horizon.py::compute_horizon_tilt_score`, neues Modul):**
- [ ] `cv2.Canny` + `cv2.HoughLinesP` auf der Graustufen-Variante des bereits via Pillow geladenen Bildes — kein `cv2.imread`/`cv2.imdecode`, Pillow bleibt alleinige Bild-I/O-Bibliothek.
- [ ] Kandidatenlinien gefiltert auf `±HORIZON_MAX_CANDIDATE_ANGLE`, längste Kandidatenlinie gewinnt; `score = clip(1.0 - |Winkelabweichung| / HORIZON_MAX_PENALIZED_ANGLE_DEGREES, 0, 1)`.
- [ ] Exakt horizontale, dominante Linie → `score == 1.0`.
- [ ] Linie exakt bei `HORIZON_MAX_PENALIZED_ANGLE_DEGREES` → `score == 0.0` (nicht negativ).
- [ ] Linie jenseits `HORIZON_MAX_PENALIZED_ANGLE_DEGREES`, aber innerhalb `HORIZON_MAX_CANDIDATE_ANGLE` → `score` auf 0.0 geklemmt, zählt trotzdem als Kandidat/Gewinner falls längste.
- [ ] **Kein erkannter Kandidat (z.B. Portrait-Nahaufnahme ohne Linienstruktur) → `score == 0.5` (neutral, bewusst nicht niedrig)** — Abwesenheit einer geraden Struktur ist kein Hinweis auf eine schiefe Aufnahme, ein niedriger Fallback würde eine ganze Klasse legitimer Fotos abwerten. Im Code zu kommentieren.
- [ ] Neue explizite `opencv-contrib-python`-Zeile in `backend/pyproject.toml` (Paket bereits transitiv über `mediapipe` im Image vorhanden, siehe Architektur-Abschnitt — kein neuer Netto-Footprint).
- [ ] Kein Modell-Asset, kein SHA-256-Test nötig — deterministischer klassischer CV-Algorithmus ohne trainiertes Gewicht.

**Freiraum (`classification.py::detect_face_orientation` + `criteria.py::compute_freiraum_score`):**
- [ ] Neues mediapipe FaceLandmarker Task-API-Paar (`build_face_landmarker()`-Factory + `FaceLandmarkerLike`-Protocol, `build_face_landmarker()` nie in einem automatisierten Test aufgerufen — analog `build_face_detector`), `num_faces=1`, `output_facial_transformation_matrixes=True`, `output_face_blendshapes=False`.
- [ ] Blickrichtung (Yaw-Winkel) aus der von mediapipe gelieferten 4×4-Kopfpose-Rotationsmatrix abgeleitet — nicht aus einem selbst konstruierten Landmark-Vektor.
- [ ] Eigenständiger, zusätzlicher Modellaufruf neben dem bestehenden `FaceDetector` — kein Ersatz, `content_people`/`goldener_schnitt` bleiben unverändert auf dem bestehenden Detektor.
- [ ] Kein Gesicht erkannt → `score == 0.0` (analog `goldener_schnitt`: kein Subjekt = kein Kompositionswert).
- [ ] `|Yaw| < FREIRAUM_YAW_DEADZONE_DEGREES` (frontaler Blick) → `score == 0.5` (kein klares Richtungssignal). Yaw exakt an der Deadzone-Grenze zählt als **außerhalb** (`<`, nicht `<=`) → gerichteter Score, nicht 0.5 — Grenzfall durch Test gepinnt.
- [ ] Sonst: `score = clip(looking_space / (looking_space + opposite_space), 0, 1)`.
- [ ] **Zusätzlicher Fallback:** `looking_space + opposite_space == 0` (Gesicht füllt die volle Bildbreite) → `score == 0.5` (0-Schutz, gleiche Argumentationsklasse wie die Deadzone).
- [ ] Neues gepinntes Modell-Asset `backend/src/photosort/assets/face_landmarker.task` mit `FACE_LANDMARKER_MODEL_SHA256`-Konstante und dediziertem SHA-256-Verifikationstest (`test_committed_task_model_matches_the_documented_sha256`, analog den drei bestehenden `.tflite`-Assets) — **Muss-Kriterium, keine Kann-Ergänzung.**
- [ ] Dokumentierte Lücke: deckt nur Personen ab, kein lokales Tier-Pose-/Blickrichtungs-Modell — Tier-Bewegungsrichtung ist Out-of-Scope.

## Datenmodell-Bezug

Additiv: drei neue `PhotoCriterionScore`-Zeilen pro Foto (`criterion_key` ∈ `{symmetrie, horizont, freiraum}`), bestehende Tabelle, bestehendes Muster (wie `tier`/`gebaeude`, Spec 0038). Keine Migration außer den bereits durch die Registry vorgesehenen generischen Kriterien-Zeilen. Kein neues DB-Feld.

## Architektur / Umsetzung

Siehe [`decisions/0026-modellwahl-symmetrie-horizont-freiraum-kriterien.md`](../decisions/0026-modellwahl-symmetrie-horizont-freiraum-kriterien.md) (Accepted) für die vollständige Begründung. Zusammenfassung:

**Zentraler Befund der Architektur-Konsultation (direkt am vorhandenen `backend/.venv` verifiziert, nicht geschätzt):** `mediapipe` deklariert `opencv-contrib-python` bereits als eigene Laufzeit-Abhängigkeit — `cv2` ist dadurch **bereits heute** im Backend-Image vorhanden (~207 MB, seit Spec 0024). Das Horizont-Kriterium führt dadurch **keine neue, kostenträchtige Abhängigkeit** ein, anders als der Devil's-Advocate-Schritt zunächst befürchtete ("ähnliche Größenordnung wie Spec 0038", ~2,9 GB).

**Drei unterschiedliche Integrationsmuster:**
1. **`symmetrie`**: reine `classification.py`-Erweiterung, keine neue Abhängigkeit.
2. **`horizont`**: neues, eigenständiges Modul `horizon.py`, lokaler `cv2`-Import (analog dem lokalen `tensorflow`-Import in `aesthetics.py`), `cv2.Canny`+`cv2.HoughLinesP` ausschließlich auf bereits Pillow-dekodierten Pixeldaten — nie auf den historisch CVE-trächtigen OpenCV-Decoder-Codepfaden (`cv2.imread`/`imdecode`).
3. **`freiraum`**: viertes mediapipe-Task-API-Paar in `classification.py`, neues gepinntes Modell-Asset, größter Integrationsaufwand der drei.

Alle drei `category_eligible=False`. Keine Abhängigkeiten der drei Kriterien untereinander; `symmetrie`/`horizont` unconditional aufgerufen (wie `content_landscape`), `freiraum` mit eigenem Best-effort-`try`/`except` und eigenem `_try_build`-Aufruf.

**Empfohlene Implementierungsreihenfolge** (aufsteigend nach Integrationsaufwand/Risiko, konsistent mit ADR 0022): (1) Symmetrie, (2) Horizont, (3) Freiraum.

**Betroffene Dateien:**
- `backend/src/photosort/classification.py` — `compute_symmetry_score`, `detect_face_orientation`/`FaceOrientation`/`FaceLandmarkerLike`/`build_face_landmarker`.
- `backend/src/photosort/horizon.py` (neu) — `compute_horizon_tilt_score`.
- `backend/src/photosort/criteria.py` — drei neue Registry-Einträge, `compute_symmetrie_score`-Delegate, `compute_freiraum_score`.
- `backend/src/photosort/worker.py` — `_compute_content_criteria`/`_IMAGE_ANALYSIS_CRITERION_KEYS`/`run_criterion_scoring` erweitert.
- `backend/src/photosort/assets/face_landmarker.task` (neues gepinntes Asset — Quelle/SHA-256 vor TDD-Einstieg gegen das offizielle mediapipe-Modell-Repository zu verifizieren).
- `backend/pyproject.toml` — neue explizite `opencv-contrib-python`-Zeile.
- `backend/Dockerfile` — voraussichtlich keine Änderung nötig (Systembibliotheken bereits vorhanden), bei `docker build`-Verifikation zu bestätigen.
- Docker-Image-Wachstum vor Umsetzung per echtem `docker build` zu verifizieren (Lehre aus ADR 0022) — geschätzt nahe 0 MB (`horizont`), gering/niedrige zweistellige MB (`freiraum`-Asset), 0 MB (`symmetrie`).
- `docs/architecture.md` — Aktualisierung durch `architect` erst nach tatsächlicher Umsetzung (etabliertes Muster).

## UI/UX

**Nicht relevant** (konsultiert, nicht strukturell geskippt — `ux-ui-designer`, 2026-08-19). Die bestehende, generische `CriterionDetailsList.tsx` (Specs 0040/0041) iteriert bereits über alle vom Backend gelieferten Kriterien-Scores und zeigt `display_name` direkt aus `CRITERIA_REGISTRY` an — kein Frontend-Code nötig, kein `categoryLabels.ts`-artiges Mapping erforderlich (anders als bei kategoriefähigen Kriterien). Alle drei neuen Kriterien erscheinen automatisch in der bestehenden Bewertungsdetails-Ansicht, sobald sie produktiv scoren — exakt derselbe Mechanismus, der bereits `goldener_schnitt`/`aesthetics` (Spec 0038) ohne eigene UI-Exposition abdeckt.

## Security

**Nicht sicherheitsrelevant im engeren Sinn** (`security-engineer`-Konsultation, 2026-08-19) — keine neue Auth-Logik, kein neuer Endpunkt, keine neue externe Schnittstelle, keine Secrets, keine geänderte Datensichtbarkeit zwischen den beiden Nutzern. Zwei Supply-Chain-Aspekte wurden dennoch geprüft (laut ADR 0014 grundsätzlich sicherheitsrelevante Signale):

1. **`opencv-contrib-python`:** wird in `backend/pyproject.toml` nur explizit deklariert, ist aber bereits seit Spec 0024 transitiv über `mediapipe` im Image vorhanden — kein neuer Footprint. Die aktive Nutzung beschränkt sich strukturell auf `cv2.Canny`/`cv2.HoughLinesP` auf bereits über Pillow dekodierten Pixeldaten, nie auf `cv2.imread`/`cv2.imdecode` — die historisch CVE-trächtigsten OpenCV-Codepfade (Bild-/Video-Decoder) werden dadurch strukturell nicht erreicht. Apache-2.0-Lizenz, unproblematisch. Empfehlung an `developer`: beim tatsächlichen `pyproject.toml`-Edit einen kurzen OSV-Check nachholen (analog ADR 0022s `tensorflow`-Audit) — kein Blocker.
2. **`face_landmarker.task`:** folgt demselben SHA-256-Pinning- und Build-Zeit-Bundling-Muster wie die drei bestehenden `.tflite`-Assets (kein Laufzeit-Download). Als FlatBuffer-/Zip-Bundle besteht keine dem `.hdf5`/`load_model()`-Fall vergleichbare Deserialisierungs-Codeausführungs-Gefahr.

Alle drei Kriterien verarbeiten ausschließlich die bereits auf 2048×2048 begrenzte `display`-Cache-Variante, konsistent mit dem im Sicherheitskonzept verankerten Grundsatz "Lokale Bildverarbeitung". Keine Ergänzung des Sicherheitskonzepts erforderlich — kein neue Angriffsflächen-Klasse, viertes/fünftes Auftreten des bereits etablierten "gepinnte lokale Modell-Assets"-Musters.

## Teststrategie

Vollständig in `specs/architecture/0002-testkonzept.md` als neue Sektion **"`cv2`-Synthetische-Bild-Unit-Tests + viertes mediapipe-Task-API-Paar + Kopfpose aus Rotationsmatrizen"** festgehalten (`test-engineer`-Konsultation, 2026-08-19). Kernpunkte:

- **`symmetrie`**: Unit-Tests mit synthetischen Pillow-Bildern, kein Test-Double nötig.
- **`horizont`**: neue Datei `test_horizon.py`, **direkte Aufrufe von `cv2.Canny`/`cv2.HoughLinesP`** gegen mit `PIL.ImageDraw.line(...)` gezeichnete synthetische Bilder — kein Mocking von `cv2`, da beide Funktionen deterministisch und ohne trainierte Gewichte sind.
- **`freiraum`**: neues `FaceLandmarkerLike`-Protocol-Trio + `FakeFaceLandmarker` (analog `FaceDetectorLike`), `build_face_landmarker()` nie in einem automatisierten Test; Rotationsmatrix-zu-Yaw-Extraktion isoliert mit synthetischen 4×4-`numpy`-Matrizen getestet (deckt die offene Achsen-/Vorzeichenkonvention ab); Integrationstest mit Aufrufzähler-Nachweis in `test_worker_criterion_scoring.py`.
- Registry-Invarianten-Test (`category_eligible == (threshold is not None)`) deckt die drei neuen Einträge automatisch mit ab, kein neuer Testfall nötig.

**Relevante Edge Cases** (Details siehe Akzeptanzkriterien): einfarbiges Bild/ungerade Bildmaße (`symmetrie`); kantenloses Bild, Winkel-Grenzfälle, Tie-Break bei gleich langen Kandidatenlinien, Portrait-Nahaufnahme (`horizont`); mehrere Gesichter trotz `num_faces=1`, Yaw-Deadzone-Grenze, Gesicht am Bildrand (0-Division), Tier statt Person (`freiraum`).

**Testkonzept ergänzt:** `specs/architecture/0002-testkonzept.md`, neue Sektion (siehe oben) plus neuer Eintrag unter "Bekannte Lücken" (unkalibrierte `horizont`/`freiraum`-Schwellenwerte — gleiches Prinzip wie die bestehende `SHARPNESS_REJECT_THRESHOLD`-Lücke).

## Entscheidungen (2026-08-19, im Idea-Sharpening-Gespräch mit Daniel geklärt)

- **Abgrenzung zu `goldener_schnitt`:** der Rohtext ("Bildkomposition als Merkmal") überschnitt sich auf den ersten Blick mit dem bereits umgesetzten `goldener_schnitt`-Kriterium (Spec 0038). Auf Rückfrage hat Daniel drei konkrete, davon unabhängige Teilaspekte benannt: Horizont-/Kamera-Neigung, Symmetrie/Balance, Freiraum/Fluchtrichtung.
- **Drei separate Kriterien statt einem kombinierten** (Rückfrage im Sharpening-Gespräch): konsistent mit dem bestehenden Muster (ein Kriterium = ein unabhängiges, einzeln gewichtbares Signal).
- **Feasibility-Fund (Schritt 4, Code-Recherche):** von den drei Teilaspekten war ursprünglich nur `symmetrie` ohne neue Abhängigkeit umsetzbar; `horizont` bräuchte eine echte Liniendetektion (nicht mit reinem Pillow/numpy robust machbar), `freiraum` bräuchte Blickrichtungsdaten, die die aktuelle Gesichtserkennung nicht liefert. Auf Rückfrage hat Daniel sich bewusst für beide zusätzlichen Abhängigkeiten entschieden (OpenCV für `horizont`, mediapipe FaceLandmarker für `freiraum`) statt die beiden Kriterien zurückzustellen oder mit einer fragilen Heuristik zu bauen.
- **Devil's-Advocate-Ergebnis:** angesichts des zu diesem Zeitpunkt noch für hoch gehaltenen Aufwands (zwei neue Abhängigkeiten, ursprünglich befürchtet "ähnliche Größenordnung wie Spec 0038") hat Daniel bestätigt, alle drei Kriterien trotzdem umzusetzen. Die anschließende Architektur-Konsultation zeigte, dass der tatsächliche Aufwand deutlich geringer ausfällt als befürchtet (OpenCV bereits transitiv vorhanden) — bestätigt im Nachhinein, dass die Entscheidung richtig war, ändert aber nichts an der Tatsache, dass die Zusage vor dieser Erkenntnis erfolgte.
- **`ux-ui-designer` konsultiert, nicht strukturell geskippt** (Schritt 7): trotz "reines Ranking-Signal, keine Kategorie" war zu prüfen, ob die seit Spec 0040/0041 bestehende generische Bewertungsdetails-Ansicht einen Berührungspunkt schafft — Ergebnis: automatische Integration ohne Frontend-Code, "nicht relevant" bestätigt.
- **`security-engineer` konsultiert, nicht strukturell geskippt** (Schritt 8): trotz fehlendem Auth-/Schnittstellen-/Datenbezug wegen der zwei neuen Dependency-/Modell-Asset-Signale (Präzedenzfall: Supply-Chain-Trigger aus ADR 0014) — Ergebnis: nicht sicherheitsrelevant, mit dokumentierter Begründung statt kommentarlosem "nicht relevant".
- **Priorität — Niedrig** (nach Schärfung bestätigt, `requirements-engineer`-Vorschlag aus Schritt 2 übernommen): durchdachte, aber nicht dringende Erweiterung eines bereits gut funktionierenden Kriterien-Sets — kein akuter, von Daniel im Alltag bemerkter Missstand, reine Qualitätsverbesserung für die automatische Vorauswahl. **Kein Konflikt mit bereits Geplantem:** unabhängig von allen anderen offenen Specs (0004, 0031, 0044), verdrängt nichts.

## Offene Fragen

Keine offenen Fragen mehr für den Scope dieser Spec. Zwei technische Detailentscheidungen sind bewusst dem `developer`-Agenten beim TDD-Einstieg überlassen (dokumentiert im Testkonzept-Update): Tie-Break bei gleich langen Horizont-Kandidatenlinien; exakte Quelle/SHA-256-Verifikation von `face_landmarker.task` gegen das offizielle mediapipe-Modell-Repository.

## Out of Scope

- Tier-Bewegungsrichtung/-Blickrichtung für `freiraum` — kein lokales Tier-Pose-Modell verfügbar, gilt nur für Personen.
- Kalibrierung der `horizont`/`freiraum`-Schwellenwerte gegen einen echten Fotokorpus — wie bei `SHARPNESS_REJECT_THRESHOLD` unkalibriert dokumentiert, spätere Option.
- Kategorie-Fähigkeit (`category_eligible=True`) für eines der drei Kriterien — bewusst reine Ranking-Signale wie `goldener_schnitt`/`aesthetics`.
- UI-Anzeige über die bestehende generische Bewertungsdetails-Ansicht hinaus (z.B. eigene Badges/Chips) — kein Bedarf identifiziert.
- Dynamisches/dediziertes Retry bei einzelnen Modellfehlern — bestehendes Best-effort-Muster reicht.
