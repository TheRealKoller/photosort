# 0217 - Inhaltsbasierte Landschafts-Erkennung, Spezifitäts-Vorrang bei der Kategorie-Vergabe und expliziter "nicht erkannt"-Zustand

**Status:** Accepted
**Erstellt:** 2026-08-30
**Bezug:** [GitHub-Issue #217](https://github.com/TheRealKoller/photosort/issues/217), ADR [`decisions/0046-inhaltsbasierte-landschaft-spezifitaets-vorrang-nicht-erkannt.md`](../decisions/0046-inhaltsbasierte-landschaft-spezifitaets-vorrang-nicht-erkannt.md)

## Ziel

Beim Durchgehen der Kuratierungsansicht landen zu viele Fotos in den Kategorien "Landschaft" und "Detail", obwohl darauf erkennbar weder eine Landschaft noch eine Detailaufnahme zu sehen ist. Das entwertet genau den Schritt, für den kuratiert wird: Wer die Kategorien durchgeht, muss laufend von Hand korrigieren statt sich auf die Vorsortierung verlassen zu können.

Zwei Dinge verstärken sich dabei:

- "Landschaft" wird heute nicht daran festgemacht, ob eine Landschaft zu sehen ist, sondern daran, wie gleichmäßig/texturarm ein Bild ist. Eine glatte Wand, ein unscharfer Hintergrund oder eine dunkle Aufnahme erfüllen dieses Merkmal genauso wie ein Bergpanorama.
- "Detail" ist gar keine Erkennung, sondern der Auffangkorb für alles, wofür nichts erkannt wurde. Das Ergebnis wird dem Nutzer aber wie eine Aussage über den Bildinhalt präsentiert.

Verschärfend kommt hinzu: Auch wenn für ein Projekt die kostenpflichtige Remote-Kategorisierung gelaufen ist, schlagen sich deren Ergebnisse in der Kuratierungsansicht kaum nieder — die unspezifischen Kategorien setzen sich gegen die genaueren Erkennungen durch. Der bezahlte Erkennungsschritt verpufft damit weitgehend.

Betroffen ist der Standardnutzer der Kuratierung, also beide Nutzer des Systems, bei jedem Projekt.

## User Story

Als Nutzer, der ein Projekt kuratiert, möchte ich mich darauf verlassen können, dass ein Foto nur dann in einer Inhaltskategorie liegt, wenn dieser Inhalt darauf tatsächlich zu sehen ist, und dass ich sofort erkenne, wo die Erkennung nichts gefunden hat, damit ich die Vorsortierung als Arbeitsersparnis nutzen kann statt sie Foto für Foto nachzukorrigieren.

## Akzeptanzkriterien

- [ ] **AK1 — Landschaft ist inhaltsbasiert.** Ein Foto erhält den `category_key` `"landschaft"` nur, wenn `compute_landschaft_score` aus der Szenen-Klassifikation einen Treffer in `LANDSCAPE_SCENE_CATEGORIES` mit Konfidenz `>= LANDSCHAFT_LABEL_MIN_CONFIDENCE` liefert. Ein texturarmes Bild ohne Landschaftsmotiv (hoher `content_landscape`-Wert, kein Allow-Listen-Label) erhält Score `0.0` und wird keiner Landschafts-Kategorie zugeordnet. `content_landscape` ist `category_eligible=False` (Anzeigename "Flächigkeit") und kann strukturell keine Kategorie mehr bilden; der Key `"landscape"` wird von der automatischen Ableitung nie mehr erzeugt.
- [ ] **AK2 — Bestandsfall verschlechtert sich nicht.** Ein Projekt, dessen Kandidatenfotos überwiegend Allow-Listen-Landschaftslabels tragen, aktiviert die Kategorie `"landschaft"` (`Anteil >= CATEGORY_ACTIVE_THRESHOLD_FRACTION`), und die betroffenen Fotos landen dort. Zusätzlich darf die abgesenkte Modell-Untergrenze (`SCENE_LABEL_MIN_CONFIDENCE = 0.2`, `max_results=5`) das Ergebnis von `compute_gebaeude_score` nicht verändern: Labels zwischen `0.2` und `0.5` ergeben weiterhin `0.0`, exakt `0.5` weiterhin einen Treffer. Der Vorher/Nachher-Vergleich aus AK7 ist durchzuführen und sein Ergebnis im PR zu dokumentieren; zeigt er einen Recall-Einbruch bei echten Landschaften (bekannte ImageNet-Lücke Wald/Wiese/Feld, siehe ADR 0046), ist das **kein Merge-Blocker** — der Befund wird im PR festgehalten und die Nachkalibrierung (Allow-Liste, `LANDSCHAFT_LABEL_MIN_CONFIDENCE`) als Folge-Ticket erfasst (Stakeholder-Entscheidung vom 2026-08-30).
- [ ] **AK3 — Remote-Ergebnisse setzen sich durch.** Liegen für ein Projekt `remote:`-Pseudo-Keys vor, gewinnt ein solcher Key in `derive_category_key` gegen jedes lokale Inhalts-Kriterium desselben Fotos, unabhängig vom Zahlenwert der Scores (`CATEGORY_SPECIFICITY_NAMED = 20` vor `CATEGORY_SPECIFICITY_CONTENT = 10`) — ausdrücklich auch gegen `content_people` mit Score `1.0` (Stakeholder-Entscheidung vom 2026-08-30).
- [ ] **AK4 — Seltener, aber benannter Inhalt bildet eine Kategorie.** Ein `remote:`-Key oder `landmark` wird in `derive_active_categories` bereits aktiv, wenn er auf `>= CATEGORY_SPECIFIC_MIN_PHOTOS (3)` Kandidatenfotos vorkommt **oder** den Anteil von 15 % erreicht (`oder`-Verknüpfung, inklusive Vergleiche). Kriterien der Stufe CONTENT behalten unverändert die reine 15 %-Bedingung. Bei 2 Treffern und < 15 % Anteil bleibt der Key inaktiv.
- [ ] **AK5 — "Nicht erkannt" ist ein eigener, erkennbarer Zustand.** Fotos ohne erfülltes aktives Kriterium erhalten den `category_key` `"unerkannt"` (statt `"detail"`), bleiben in der automatischen Auswahl (Partitionierung `cluster_key × category_key` und Top-N unverändert), werden in der Kuratierungsansicht als "Nicht erkannt" beschriftet, stehen innerhalb ihres Clusters immer als letzter Kategorie-Abschnitt (übrige Abschnitte alphabetisch) und tragen einen neutralen Erklärtext ("Diese Fotos konnten nicht automatisch kategorisiert werden.") ohne Fehler-Optik. Die drei Zustände alle Fotos unerkannt / Mix / keine unerkannten Fotos sind abgedeckt.
- [ ] **AK6 — "Detail" wird nicht mehr automatisch vergeben.** `CATEGORY_DETAIL` existiert nicht mehr; kein Codepfad erzeugt `"detail"` als abgeleiteten `category_key`. Der Wert bleibt ausschließlich als Remote-Schlagwort (`canonical_key`) oder als manuell gesetzter `category_override` möglich und wird dann unverändert angezeigt.
- [ ] **AK7 — Verifikation am echten Fotobestand.** `python -m photosort.category_diff --project-id N` (optional `--before-run-id`/`--after-run-id`, Default: die beiden jüngsten erfolgreichen Läufe) gibt für ein reales Projekt eine Übergangsmatrix (alte Kategorie → neue Kategorie mit Anzahlen) und die Foto-Einzelliste (`relative_path`, alt, neu) aus, ohne Daten zu verändern. Das Werkzeug ist automatisiert getestet; der Vorher/Nachher-Lauf auf einem echten Projekt ist eine manuelle Verifikationspflicht des Umsetzers, sein Ergebnis wird im PR dokumentiert (Bewertung/Abnahme durch Daniel, aber kein Merge-Blocker — siehe AK2).
- [ ] **AK8 — Keine zusätzlichen Kosten pro Foto.** `classify_scene` wird pro Foto und Lauf genau einmal aufgerufen; dieselbe Label-Liste geht an `compute_gebaeude_score` und `compute_landschaft_score`. Es kommt kein weiteres Modell, kein weiteres Asset und kein zusätzlicher Cloud-Aufruf hinzu. Die Landmark-Vorfilterung (`is_landmark_candidate`) prüft `landschaft` oder `gebaeude`; ein Foto, das nur die weggefallene `content_landscape`-Bedingung erfüllte, löst keinen Cloud-Aufruf mehr aus.
- [ ] **AK9 — Manuelle Korrekturen überleben unverändert.** Ein gesetzter `PhotoScore.category_override` wird weiterhin vor jeder Ableitung angewendet und bleibt nach einem vollständigen Re-Scoring-Lauf bitgenau erhalten — auch mit einem Wert, den die neue Ableitung nie mehr erzeugt (`"landscape"`, `"detail"`); ein solcher Override wird als verwaister Kandidat dargestellt und bleibt über `DELETE /photos/{id}/category-override` zurücknehmbar. Keine Migration, kein Schema-Eingriff, bestehende `PhotoRanking`-Zeilen älterer Läufe werden nicht rückwirkend geändert.

## Datenmodell-Bezug

**Kein Schema-Eingriff, keine Migration.** `PhotoRanking.category_key` und `PhotoCriterionScore.criterion_key` sind freie Strings; die neuen Registry-Felder (`category_specificity`) sind reine In-Code-Metadaten. Berührte Entitäten (unverändert in Struktur): `PhotoCriterionScore` (neue Zeile `landschaft` pro Foto), `PhotoRanking` (neue Werte `"landschaft"`/`"unerkannt"` im bestehenden Feld), `PhotoScore.category_override` (unangetastet), `CriterionScoringRun` (Bezugspunkt des Diff-Werkzeugs).

`docs/architecture.md` wird im selben PR aktualisiert (siehe Abschnitt "Architektur / Umsetzung"): neues Kriterium `landschaft`, Degradierung von `content_landscape`, Registry-Feld `category_specificity`, geänderte Auswahl-/Aktivierungsregel, Catch-all-Key `"unerkannt"`, neues CLI-Modul `photosort.category_diff`. Datenmodell-Abschnitt nur redaktionell.

## Architektur / Umsetzung

`architect`-Konsultation, 2026-08-30. Vollständige Begründung: ADR [`decisions/0046-inhaltsbasierte-landschaft-spezifitaets-vorrang-nicht-erkannt.md`](../decisions/0046-inhaltsbasierte-landschaft-spezifitaets-vorrang-nicht-erkannt.md) (revidiert ADR [`0023`](../decisions/0023-dynamische-kategorie-ableitung-aus-kriterien-haeufigkeit.md) Punkte 2 und 3; Punkte 1/4 von ADR 0023 bleiben gültig).

**Gewählter Ansatz.** Alle drei Beschwerden der Story haben eine strukturelle Ursache im bestehenden Code, keine Schwellwert-Ursache: (a) `content_landscape` misst mit `compute_uniform_area_fraction` Texturarmut, keine Landschaft; (b) `CATEGORY_DETAIL` ist ein Auffangkorb, wird aber wie eine Erkennung dargestellt; (c) `derive_category_key` vergleicht mit "höchster Score gewinnt" einen Uniform-Flächen-Anteil (0,9) gegen eine LLM-Konfidenz (0,85) — Skalen, die nicht vergleichbar sind — und `derive_active_categories` lässt ein seltenes, präzises Remote-Label an der 15-%-Häufigkeitsschwelle scheitern. Entsprechend vier Eingriffe, alle innerhalb der bestehenden Registry-/Aggregations-Architektur, kein neues Muster:

1. **Echte Landschafts-Erkennung ohne Zusatzkosten.** Neues Kriterium `landschaft` (`LOCAL_ML`, `category_eligible=True`), gescort aus einer kuratierten Allow-Liste natürlicher ImageNet-1k-Klassen — exakt das Muster von `gebaeude`/`ARCHITECTURE_CATEGORIES` (ADR 0022 Punkt 2). Entscheidend: `_compute_content_criteria` ruft `classify_scene` weiterhin **genau einmal** pro Foto auf und reicht dieselbe Label-Liste an `compute_gebaeude_score` **und** `compute_landschaft_score` (Wiederverwendungsmuster wie `detect_person` → `content_people` + `goldener_schnitt`). Keine neue Abhängigkeit, kein neues Modell-Asset, keine zusätzliche Inferenz, kein Cloud-Aufruf → Akzeptanzkriterium AK8 strukturell erfüllt. `content_landscape` wird auf `category_eligible=False` gesetzt (bleibt Ranking-Signal) und heißt künftig "Flächigkeit".
2. **Spezifitäts-Vorrang statt roher Score-Vergleich.** Neues Registry-Attribut `category_specificity` (zwei Stufen: `CATEGORY_SPECIFICITY_CONTENT=10` für lokale Inhaltserkennung, `CATEGORY_SPECIFICITY_NAMED=20` für `landmark` und alle `remote:`-Pseudo-Keys). `derive_category_key` wählt nach `(-specificity, -score, key)` — innerhalb einer Stufe bleibt die vertraute Regel unverändert.
3. **Aktivierungsschwelle spezifitätsabhängig.** `CATEGORY_SPECIFICITY_CONTENT` behält die 15-%-Regel; `CATEGORY_SPECIFICITY_NAMED` ist aktiv bei `Trefferzahl >= CATEGORY_SPECIFIC_MIN_PHOTOS (3)` **oder** `Anteil >= 15 %` (die Oder-Verknüpfung schützt sehr kleine Projekte).
4. **Expliziter "nicht erkannt"-Zustand.** `CATEGORY_DETAIL = "detail"` → `CATEGORY_UNRECOGNIZED = "unerkannt"`, Anzeigename "Nicht erkannt". `"detail"` wird nicht mehr automatisch vergeben (bleibt möglich als Remote-Schlagwort oder manuelle Übernahme). Ein eigener Detail-/Makro-Detektor wird bewusst nicht gebaut — es gibt kein belastbares lokales Signal dafür.

**Betroffene Dateien**

*Backend*
- `backend/src/photosort/classification.py` — neue Untergrenze `SCENE_LABEL_MIN_CONFIDENCE = 0.2`; `classify_scene` filtert gegen diese statt gegen `SCENE_CLASSIFICATION_CONFIDENCE_THRESHOLD`; `build_scene_classifier` bekommt `score_threshold=SCENE_LABEL_MIN_CONFIDENCE` **und** `max_results=5`. `SCENE_CLASSIFICATION_CONFIDENCE_THRESHOLD` (0.5) bleibt bestehen und wird zur expliziten Gebäude-Konfidenzschwelle in `criteria.py`. `LANDSCAPE_UNIFORM_FRACTION_THRESHOLD` wird ersatzlos entfernt (nach der Umstellung ohne Verwendung; die zwei Kommentare in `criteria.py`, die es als Kalibrierungs-Beispiel nennen, auf `UNIFORM_TILE_VARIANCE_THRESHOLD` umschreiben).
- `backend/src/photosort/criteria.py` — Kern der Änderung:
  - `CriterionDefinition` + `category_specificity: int = CATEGORY_SPECIFICITY_CONTENT`; Registry-Invarianten-Test um "Spezifität nur bei `category_eligible=True` von Bedeutung" ergänzen.
  - Neue Konstanten: `CATEGORY_SPECIFICITY_CONTENT`/`CATEGORY_SPECIFICITY_NAMED`, `LANDSCAPE_SCENE_CATEGORIES` (Allow-Liste), `LANDSCHAFT_LABEL_MIN_CONFIDENCE = 0.25`, `_LANDSCHAFT_CATEGORY_PRESENCE_THRESHOLD = 0.01`, `CATEGORY_SPECIFIC_MIN_PHOTOS = 3`, `CATEGORY_UNRECOGNIZED = "unerkannt"` (ersetzt `CATEGORY_DETAIL`).
  - Registry: neuer Eintrag `landschaft` ("Landschaft erkannt", `LOCAL_ML`, eligible, Presence `0.01`); `content_landscape` → `category_eligible=False`, `category_presence_threshold=None`, `display_name="Flächigkeit"`; `landmark` → `category_specificity=CATEGORY_SPECIFICITY_NAMED`.
  - Neue reine Funktion `compute_landschaft_score(labels: Sequence[SceneLabel]) -> float` — höchste Konfidenz unter den Labels, die *sowohl* in `LANDSCAPE_SCENE_CATEGORIES` liegen *als auch* `>= LANDSCHAFT_LABEL_MIN_CONFIDENCE` sind, sonst `0.0`.
  - `compute_gebaeude_score` filtert **zusätzlich explizit** bei `SCENE_CLASSIFICATION_CONFIDENCE_THRESHOLD` (0.5) — verpflichtend, sonst ändert die abgesenkte Modell-Untergrenze das Gebäude-Verhalten still mit.
  - `is_landmark_candidate` prüft künftig `landschaft` **oder** `gebaeude` statt `content_landscape` oder `gebaeude` (`content_landscape` hat keine Registry-Schwelle mehr).
  - `derive_active_categories`: zusätzliche Aktivierungsbedingung für die NAMED-Stufe (inkl. aller `dynamic_keys`), neuer optionaler Parameter `specific_min_photos: int = CATEGORY_SPECIFIC_MIN_PHOTOS` (Testbarkeit, analog `threshold_fraction`).
  - `derive_category_key`: Auswahlschlüssel `(-specificity, -score, key)`; kleine Hilfsfunktion für "Spezifität eines Keys" (Registry-Eintrag bzw. NAMED für `dynamic_keys`), damit beide Funktionen dieselbe Regel teilen. Zusätzlich: `CATEGORY_UNRECOGNIZED` als reservierter Key behandeln (siehe Abschnitt "Security", Punkt 2).
- `backend/src/photosort/worker.py` — `_IMAGE_ANALYSIS_CRITERION_KEYS` um `"landschaft"` ergänzen (Upsert-Buchhaltung; `DEFAULT_CRITERION_WEIGHTS` zieht automatisch nach). In `_compute_content_criteria` den `classify_scene`-Aufruf **einmal** in ein eigenes `try` ziehen und aus derselben Label-Liste `gebaeude` und `landschaft` setzen, **je Kriterium in einem eigenen `try`** — Best-effort-Semantik pro Kriterium bleibt erhalten (ein Fehler in einer Score-Funktion darf das jeweils andere Kriterium nicht mitreißen; heute steht beides in einer Anweisung, `worker.py:1117`).
- `backend/src/photosort/category_diff.py` *(neu)* — read-only CLI für den Vorher/Nachher-Vergleich (AK7). Nutzt aus, dass `PhotoRanking`-Zeilen pro `criterion_scoring_run_id` geschrieben und nie gelöscht werden — der Stand *vor* der Umstellung liegt also bereits in der DB. Aufteilung: reine, unit-testbare Funktionen `diff_category_assignments(before: dict[int, str], after: dict[int, str]) -> ...` (Übergangsmatrix alt→neu + Einzelliste) und `render_report(...) -> str`; dünne DB-Schicht `async def collect_assignments(session, run_id) -> dict[int, str]` sowie `main()` (argparse: `--project-id`, optional `--before-run-id`/`--after-run-id`, Default = die zwei jüngsten erfolgreichen Läufe; klare Fehlermeldung bei < 2 Läufen). Aufruf: `docker compose exec backend python -m photosort.category_diff --project-id N`. Die Security-Vorgaben aus Abschnitt "Security" Punkt 3 (stdout-only, `type=int`, keine rohen SQLAlchemy-Tracebacks, Run-ID/Projekt-Konsistenz-Guard) sind verbindlicher Teil dieser Datei.
- `backend/src/photosort/api/photos.py` — **keine Code-Änderung nötig**: `_category_candidates_out` und `_photo_category_candidate_keys` iterieren über `category_presence_threshold is not None`, bieten also automatisch `landschaft` statt `landscape` an. Nur Testanpassung.

*Frontend*
- `frontend/src/utils/categoryLabels.ts` — `CATEGORY_DISPLAY_NAME_OVERRIDES` um `unerkannt: 'Nicht erkannt'` ergänzen. Kein Eintrag für `landschaft` nötig (generischer Fallback liefert bereits "Landschaft").
- `frontend/src/pages/CurateCategoriesPage.tsx` — die Kategorie-Abschnitte werden heute rein alphabetisch sortiert (`Object.keys(categories).sort()`); der Auffang-Abschnitt "Nicht erkannt" steht innerhalb eines Clusters **immer zuletzt** (Komparator: Catch-all-Key hinten, sonst alphabetisch), plus neutraler Erklärtext (Details siehe Abschnitt "UI/UX").

**Umsetzungsreihenfolge (TDD, jeweils Rot → Grün → Refactor)**
1. `classification.py`: abgesenkte Label-Untergrenze + `max_results`.
2. `criteria.py` Teil A — `compute_landschaft_score` + `LANDSCAPE_SCENE_CATEGORIES`; `compute_gebaeude_score` bekommt seinen expliziten 0.5-Filter (Regressionstest).
3. `criteria.py` Teil B — Registry: `landschaft` neu, `content_landscape` degradiert, `landmark` NAMED, `category_specificity`-Feld + Invariantentest.
4. `criteria.py` Teil C — `derive_active_categories` (spezifitätsabhängige Aktivierung) und `derive_category_key` (`(-specificity, -score, key)`), inkl. Regressionstests aus Spec 0045/0055 auf die neue Regel umgestellt.
5. `criteria.py` Teil D — `CATEGORY_UNRECOGNIZED` ersetzt `CATEGORY_DETAIL` (inkl. Reservierung gegen Remote-Key-Kollision); `is_landmark_candidate` auf `landschaft`/`gebaeude` umstellen.
6. `worker.py` — einmaliger `classify_scene`-Aufruf für zwei Kriterien mit getrennten `try`-Blöcken, `_IMAGE_ANALYSIS_CRITERION_KEYS`; Integrationstest inkl. "manueller Override überlebt den Lauf unverändert".
7. `category_diff.py` + Tests.
8. Frontend: `categoryLabels.ts`, Sortierung und Erklärtext des Catch-all-Abschnitts.
9. `docs/architecture.md` im selben PR aktualisieren, manueller Vorher/Nachher-Lauf nach AK7 (Ergebnis im PR dokumentieren), voller Qualitätscheck (`ruff`, `mypy --strict`, `pytest --cov-fail-under=80`, `vitest`, `oxlint`, `tsc`).

**Entwurfsentscheidungen (Kurzfassung, vollständig in ADR 0046)**
1. **ImageNet-Allow-Liste statt neues Szenenmodell** (Places365 o.ä.): ein drittes schweres ML-Framework ist durch ADR 0022 ausgeschlossen; die vorhandene Modellausgabe wird bereits berechnet und heute nur weggeworfen. **Dokumentierte, akzeptierte Lücke:** ImageNet-1k kennt keine Wald-/Wiesen-/Feld-Klassen — solche Landschaften landen künftig in "Nicht erkannt". Die exakte Schreibweise der Allow-Listen-Einträge ist einmalig gegen die Label-Liste des gebündelten `efficientnet_lite0.tflite` zu verifizieren und im Code-Kommentar festzuhalten (kein modellladender Test — gleiche Konvention wie bei `ARCHITECTURE_CATEGORIES`).
2. **Absenken der Modell-Untergrenze statt Absenken der Gebäude-Schwelle:** die Konfidenz-Entscheidung wandert aus den Modell-Optionen in die jeweilige Kriterien-Funktion. Gebäude bleibt dadurch bitgenau beim heutigen Verhalten, Landschaft bekommt den für natürliche Szenen nötigen Spielraum.
3. **Zwei Spezifitätsstufen, keine feinere Rangordnung:** eine Feinsortierung innerhalb der lokalen Kriterien wäre wieder die gepflegte Prioritätsliste, die ADR 0023 bewusst vermieden hat. Spezifität ist ein Registry-*Attribut*, kein Sonderfall im Ableitungscode.
4. **Landmark-Vorfilterung folgt `landschaft`/`gebaeude`:** semantisch das, was der Filter immer ausdrücken sollte; senkt die Zahl kostenpflichtiger Cloud-Aufrufe im Mittel (keine Aufrufe mehr für unscharfe/dunkle Fotos). Zur nicht-teilmengenartigen Verschiebung der Kandidatenmenge siehe Abschnitt "Security" Punkt 1.
5. **Diff-Werkzeug als CLI, nicht als Endpunkt/UI:** einmalige Verifikations-/Kalibrierungshilfe für zwei bekannte Betreiber; eine Produktoberfläche dafür wäre dauerhafte Wartungslast ohne dauerhaften Nutzen.

**Bestandsdaten / Migration:** keine Migration, kein Schema-Eingriff. Die neue Logik greift erst beim nächsten `CriterionScoringRun`; ältere `PhotoRanking`-Zeilen bleiben unverändert stehen (und werden vom Diff-Werkzeug als "Vorher"-Stand gebraucht). **Manuelle Kategorie-Korrekturen bleiben unangetastet:** `PhotoScore.category_override` wird in `run_criterion_scoring` weiterhin *vor* jeder Ableitung angewendet (`category_override or derive_category_key(...)`) und von keiner Änderung dieser Spec berührt — auch ein Override auf einen Wert, den die neue Ableitung nie mehr erzeugt (`"landscape"`, `"detail"`), bleibt wirksam; die Darstellung als "verwaister" Kandidat existiert bereits (`CriterionDetailsList`, `isOrphan`). Kein Backfill, kein Sonderfallcode.

**`docs/architecture.md` (Pflicht im selben PR):** neues Kriterium `landschaft` und die Degradierung von `content_landscape` zum reinen Ranking-Signal; neues Registry-Feld `category_specificity` samt geänderter Auswahlregel `(-specificity, -score, key)`; spezifitätsabhängige Aktivierung in `derive_active_categories`; neuer Catch-all-Key `"unerkannt"`; neues CLI-Modul `photosort.category_diff`. Datenmodell-Abschnitt nur redaktionell (kein Schema-Eingriff). Kopfzeile "Letzte Aktualisierung" auf diese Spec/ADR 0046 setzen.

## UI/UX

`ux-ui-designer`-Konsultation, 2026-08-30. **Sichtbare Oberfläche: ja** — die Kategorie-Kuratierungsansicht (`CurateCategoriesPage.tsx`) verändert sich sichtbar.

**Layout und Ablauf.** Die bestehende gruppierte Struktur (Tag → Cluster → Kategorie-Abschnitte mit Foto-Grid) bleibt unverändert. Der Unterschied ist rein inhaltlich und in der Sortierreihenfolge:

- **Neue Sortierregel innerhalb eines Clusters:** normale Kategorien zuerst, alphabetisch nach `category_key`; der Abschnitt `"unerkannt"` **immer zuletzt**, unabhängig von der alphabetischen Ordnung. Das macht visuell deutlich, dass "Nicht erkannt" ein Auffangzustand ist und keine gleichberechtigte Inhaltskategorie.

**Visuelle und semantische Behandlung von "Nicht erkannt".** Der Abschnitt wird **nicht** rot oder als Fehler markiert — es ist kein Fehler, sondern das Fehlen einer Erkennung:

- **Abschnittsüberschrift:** `formatCategoryKey("unerkannt")` liefert "Nicht erkannt" (Mapping in `categoryLabels.ts`).
- **Hinweistext direkt unter der Überschrift:** kurz und neutral, z.B. *"Diese Fotos konnten nicht automatisch kategorisiert werden."* — struktureller Text, kein zusätzliches Icon/Badge, um die Seite nicht zu überladen. Kein `role="alert"`, keine Fehler-Semantik.
- **Foto-Grid und "Verwerfen"-Button:** identisch zu normalen Kategorien, keine visuelle Unterscheidung auf Kachel-Ebene.

**Betroffene Zustände.** (a) Alle Fotos unerkannt: "Nicht erkannt"-Abschnitt gefüllt, andere Kategorien leer/nicht sichtbar. (b) Mix aus erkannten und unerkannten Fotos (Standardfall): normale Kategorien gefüllt, "Nicht erkannt" am Ende sichtbar. (c) Keine unerkannten Fotos: der Abschnitt existiert nicht in der Ausgabe (bestehendes Verhalten).

**Verwaiste manuelle Overrides.** Overrides auf alte Keys (`"detail"`, `"landscape"`) bleiben als verwaiste Kategorien sichtbar — bestehendes `isOrphan`-Muster in `CriterionDetailsList`, nichts Neues. Der neue Key `"unerkannt"` ist **nicht** verwaist, sondern ein regulär vom Backend erzeugter Key.

**Bezug zum Design-System.** Folgt dem bestehenden Grundsatz "kurzer erklärender Text statt stummer Zustand", angewendet auf eine Auffangkorb-Kategorie. In `specs/architecture/0004-design-system.md` ist unter "Wiederkehrende Muster" das Muster **"Auffangkorb-Kategorie mit erklärend dezentem Signal"** zu ergänzen: Kategorien mit Fallback-Charakter erhalten einen kurzen strukturellen Hinweistext unter der Überschrift, keine Fehler-Markierung, und stehen im Cluster immer zuletzt.

**Barrierefreiheit.** Der Hinweistext ist echter Text (nicht nur visuelles Signal), damit für Screenreader zugänglich. Die `aria-label` der Grid-Kacheln bleiben unverändert. Keine neue UI-Bibliothek, keine neue Abhängigkeit.

## Security

`security-engineer`-Konsultation, 2026-08-30: **sicherheitsrelevant an genau einer Stelle (Punkt 1), kein Blocker.** Kein neuer Endpunkt, keine Auth-Änderung, kein Schema-Eingriff, keine neue Abhängigkeit. Das Sicherheitskonzept (`specs/architecture/0003-securitykonzept.md`) ist bereits entsprechend ergänzt.

### 1. Verschobene Kandidatenmenge für den Cloud-Vision-Aufruf (`is_landmark_candidate`)

`criteria.py::is_landmark_candidate` ist die einzige Stelle dieser Story, die eine Vertrauensgrenze berührt: sie entscheidet, welche Familienfotos den Homeserver in Richtung eines externen Anbieters (Anthropic/Mistral) verlassen. Das Sicherheitskonzept führt genau diesen Vorfilter im Abschnitt "Cloud-Vision-API" als dokumentierte Datenexpositions-Grenze.

**Befund:** Die neue Kandidatenmenge (`landschaft` ODER `gebaeude`) steht zur alten (`content_landscape` ODER `gebaeude`) **in keinem Teilmengen-Verhältnis**. Die ADR-Formulierung "kleiner und präziser" gilt für den Kostenaspekt im Mittel, nicht als Datenschutz-Garantie: texturarme Fotos ohne Landschaftsmotiv fallen heraus, aber texturreiche tatsächliche Landschaftsaufnahmen — die den Uniform-Flächen-Schwellwert nie erreicht haben — kommen neu hinzu.

**Stakeholder-Entscheidung vom 2026-08-30:** Das bestehende projektweite Opt-in (`Project.cloud_vision_detection_enabled`) gilt unverändert weiter, der Consent-Zeitstempel wird **nicht** zurückgesetzt. Begründung: Empfänger, Zweck, Datenumfang pro Foto und Consent-Mechanik ändern sich nicht — ausschließlich die Auswahl der Fotos innerhalb derselben, bereits eingewilligten Verarbeitung. Kein zusätzlicher Code für einen erneuten Zustimmungsschritt.

**Muss-Kriterien für die Umsetzung:**
- Der Vorfilter bleibt **vor** jedem Cloud-Aufruf und rein lokal; die übrigen Grenzen gelten unverändert und dürfen nicht angefasst werden: ausschließlich die `display`-Cache-Variante (2048×2048), nie das Original, kein GPS-/EXIF-Zugriff, kein erneutes Senden bereits gescorter Fotos.
- `run_criterion_scoring` baut den Landmark-Client weiterhin nachweislich nur bei gesetztem `Project.cloud_vision_detection_enabled` (kein Client-Aufbau "auf Verdacht") — die Filter-Umstellung darf diese Reihenfolge nicht verändern.
- Beide Nutzer der Funktion (`worker.py::_select_landmark_candidates`, `api/photos.py::_cloud_vision_status_out`) bleiben an derselben gemeinsamen Funktion, damit die angezeigte Cloud-Vision-Status-Ableitung nicht von der real gesendeten Menge abweicht.
- Testpflichtig: ein Foto mit hohem `content_landscape`, aber ohne `landschaft`/`gebaeude`, ist **kein** Kandidat mehr; ein Foto mit `landschaft` über der Presence-Schwelle und niedrigem `content_landscape` ist neu Kandidat.

### 2. `remote:`-Pseudo-Keys als Kategorie-Überschrift — geprüft, eine kleine Härtung

Die neue Spezifitäts-Regel wertet Pseudo-Keys aus frei formulierten LLM-Ausgaben auf und macht sie häufiger zur sichtbaren Abschnittsüberschrift. Geprüft und ausreichend abgesichert:

- **Zeichenumfang:** Als `category_key` erscheint nie der LLM-Rohtext, sondern ausschließlich der `canonical_key` aus `remote_classification.py::_slugify` — Zeichenraum `[a-z0-9_]` bzw. der deterministische Hash-Fallback `label_<12 hex>` (`derive_category_key` gibt `winner.removeprefix("remote:")` zurück). Der Rohtext lebt nur in `CategoryLabel.display_name`/`PhotoCategoryDetection.raw_label`.
- **Rendering-Pfad:** `formatCategoryKey` liefert einen reinen String, ausgegeben als regulärer React-Textknoten. `dangerouslySetInnerHTML` existiert im Frontend nirgends — das bleibt Muss-Kriterium auch für den neuen Erklärtext im "Nicht erkannt"-Abschnitt.
- **Länge:** `MAX_REMOTE_LABEL_LENGTH = 60` greift vor der Normalisierung. Eine NFKC-bedingte Verlängerung in Randfällen ist rein kosmetisch — bewusst keine zusätzliche Kappung.
- **Injection über den Key in die API:** `PUT /photos/{id}/category-override` validiert gegen `_photo_category_candidate_keys` (Allow-Liste der tatsächlichen Erkennungen des Fotos) und nimmt keinen freien Client-String an. Unverändert lassen.

**Umzusetzende Härtung (niedrige Schwere, Integrität der Anzeige):** Der reservierte Catch-all-Key `CATEGORY_UNRECOGNIZED = "unerkannt"` liegt im selben Namensraum wie die frei slugifizierten Remote-Keys. Ein Remote-Label "Unerkannt" ergäbe `canonical_key == "unerkannt"` und würde — durch den neuen Spezifitäts-Vorrang jetzt bevorzugt — echte Erkennungen ununterscheidbar in den Auffang-Abschnitt mischen und dessen Aussage entwerten. Maßnahme: `derive_category_key` behandelt `CATEGORY_UNRECOGNIZED` als reservierten Key — ein Remote-Key, der darauf kollidieren würde, wird eindeutig abgesetzt (z.B. Suffix) statt zusammenzufallen. Test mit einem Remote-Label, das auf `"unerkannt"` slugifiziert, gehört dazu.

**Kein neues Risiko (bewusst festgehalten):** Durch den Spezifitäts-Vorrang bestimmt eine LLM-Antwort die Kategorie eines Fotos faktisch allein. Ein manipuliertes oder halluziniertes Label kann die Einordnung verfälschen — die Auswirkung bleibt auf die Sortierqualität beschränkt (max. 60 Zeichen, slug-sicher, kein ausgeführter Code, kein Datenzugriff). Akzeptiert, keine Maßnahme.

### 3. Neues CLI `photosort.category_diff` — geringe Relevanz, vier verbindliche Vorgaben

Rein lesend, kein Port, kein Endpunkt, läuft im Backend-Container, der ohnehin DB-Zugriff hat — dieselbe Vertrauenszone wie der Worker, keine neue Angriffsfläche. Trotzdem verbindlich:

- **Ausgabe-Hygiene:** Die Ausgabe enthält `relative_path`-Werte, also Dateinamen und Ordnerstruktur privater Familienfotos. Deshalb: Ausgabe **ausschließlich nach stdout**, keine Datei-Ausgabe-Option, kein Schreiben in ein Verzeichnis innerhalb des Repos, keine Ausgabe über den strukturierten Anwendungs-Logger (`logging_config.py`) und damit nicht in persistente Container-Logs. In Docstring und `--help`-Text festhalten: Ausgabe nicht unverändert in GitHub-Issues, PR-Beschreibungen, Specs oder Commit-Messages einfügen.
- **Argument-Verarbeitung:** `--project-id`/`--before-run-id`/`--after-run-id` als `argparse type=int` (keine freien Strings), Zugriff ausschließlich über SQLAlchemy-Core/ORM-Konstrukte mit Parameterbindung — kein `text()` mit f-String/`%`-Formatierung. Damit ist SQL-Injection strukturell ausgeschlossen, nicht nur unwahrscheinlich.
- **Fehlermeldungen:** Unbekannte IDs, zu wenige Läufe oder ein Verbindungsfehler ergeben eine kurze, eigene Meldung und einen Exit-Code ungleich 0 — kein durchgereichter SQLAlchemy-Traceback, der die `DATABASE_URL` inklusive Zugangsdaten in die Ausgabe schreiben könnte (Muster analog `OpenCloudError`).
- **Konsistenz-Guard (Korrektheit):** Explizit übergebene Run-IDs müssen zum angegebenen `--project-id` gehören; sonst Abbruch mit klarer Meldung, statt still Daten zweier Projekte zu vermischen.

### 4. Datensichtbarkeit zwischen den beiden Nutzern — unverändert

Kategorien (`PhotoRanking.category_key`, `PhotoScore.category_override`) sind projektweit und laufbezogen, nicht personenbezogen; personenbezogen ist ausschließlich `Rating`. Weder Auth-Verhalten noch Endpunkte noch Schema werden berührt.

## Teststrategie

`test-engineer`-Konsultation, 2026-08-30. Testebenen unverändert nach [`architecture/0002-testkonzept.md`](../architecture/0002-testkonzept.md); die projektweiten Regeln zu dieser Änderung sind dort bereits ergänzt. Kein E2E-Framework (unveränderte Projektentscheidung), keine neuen Werkzeuge.

**Backend — Unit**

- **`test_classification.py`** (`FakeSceneClassifier`, bestehendes Muster): `classify_scene` liefert Labels ab `SCENE_LABEL_MIN_CONFIDENCE` (Grenzfälle 0.19 raus / exakt 0.2 drin / 0.5 drin); `max_results=5` begrenzt die Liste, ohne einen stärkeren Treffer zu verdrängen; die rohe, ungefilterte Ausgabe bleibt erhalten (inhaltliche Filterung gehört in die Kriterien-Funktionen).
- **`test_criteria.py`**:
  - `compute_landschaft_score`: Allow-Listen-Treffer → Konfidenz; nicht gelistetes Label mit hoher Konfidenz → `0.0`; leere Label-Liste → `0.0`; mehrere Treffer → höchste Konfidenz; Grenzfälle an `LANDSCHAFT_LABEL_MIN_CONFIDENCE` (0.24 / exakt 0.25 / 0.26).
  - **Nicht-Regression `compute_gebaeude_score`:** Allow-Listen-Label mit 0.3 (zwischen alter und neuer Untergrenze) → weiterhin `0.0`; exakt 0.5 → Treffer.
  - Registry: `landschaft` (LOCAL_ML, eligible, Presence 0.01); `content_landscape` jetzt `category_eligible=False`/`threshold=None`, display_name "Flächigkeit"; die bestehende Mengen-Assertion der kategorie-fähigen Kriterien wird umgestellt, **nicht** auf einen Anzahl-Vergleich abgeschwächt.
  - Neue Registry-Invariante: `category_specificity` ∈ {CONTENT, NAMED}; NAMED genau für `landmark`, alle übrigen Default CONTENT.
  - `derive_category_key`: NAMED schlägt CONTENT bei niedrigerem Score; `remote:`-Key schlägt `content_people` mit 1.0; innerhalb einer Stufe gewinnt weiter der höchste Score; Tie-Break-Determinismus bei identischer Spezifität und identischem Score (alphabetisch nach vollem Key inkl. `remote:`-Präfix) sowie bei zwei NAMED-Keys; kein erfülltes Kriterium → `CATEGORY_UNRECOGNIZED`; Remote-Label, das auf `"unerkannt"` slugifiziert, kollidiert nicht mit dem reservierten Catch-all-Key.
  - `derive_active_categories`: NAMED aktiv bei genau 3 Treffern trotz < 15 % Anteil; inaktiv bei 2 Treffern und < 15 %; NAMED aktiv bei 2 Treffern, wenn der Anteil >= 15 % ist (kleines Projekt — die Oder-Verknüpfung darf niemanden schlechter stellen als bisher); CONTENT bleibt bei 15 % (3 von 100 → inaktiv); `specific_min_photos` überschreibbar; leerer Kandidatenpool ohne Division durch Null.
  - `is_landmark_candidate`: `landschaft` oder `gebaeude` an/über Schwelle → Kandidat; ein Foto mit nur hohem `content_landscape` → **kein** Kandidat mehr (Bestandstests werden umgestellt, nicht ergänzt).
- **`test_category_diff.py`** (neu): reine Funktionen `diff_category_assignments` (unveränderte Zuordnung, Wechsel, Foto nur im Vorher- bzw. nur im Nachher-Lauf, leere Eingabe) und `render_report` (Übergangsmatrix + Einzelliste, deterministische Sortierung); `collect_assignments` gegen die `db_session`-Fixture (liest genau die Zeilen der beiden Läufe, verändert nichts); `main(argv)` argv-injizierbar — Default zwei jüngste Läufe, explizite Run-IDs, Exit-Code ≠ 0 bei unbekanntem Projekt und bei < 2 Läufen, Ausgabe über `capsys`.

**Backend — Integration** (`test_worker_criterion_scoring.py`, In-Memory-DB)

- **AK8, Pflichttest:** Spy auf dem Szenen-Klassifikator — `call_count == 1` pro Foto, während `gebaeude` **und** `landschaft` beide als `PhotoCriterionScore` geschrieben werden.
- Best-effort in beide Richtungen: Fehler in `compute_landschaft_score` lässt `gebaeude` unberührt und umgekehrt; Fehler in `classify_scene` lässt beide fehlen, ohne den Lauf zu beenden; `landschaft` ist Teil von `_IMAGE_ANALYSIS_CRITERION_KEYS`.
- Ein Foto mit hohem `content_landscape`, aber ohne Landschaftslabel, landet unter `"unerkannt"`.
- Remote-Label mit niedrigem Score gewinnt gegen `content_people` mit 1.0 (End-to-End der Spezifitätsregel über `_merge_remote_category_labels`).
- **AK9:** ein Foto mit `category_override = "detail"` bzw. `"landscape"` behält den Wert nach einem vollen Lauf.
- Landmark-Vorfilterung: Foto mit nur `content_landscape` löst keinen Cloud-Aufruf mehr aus; Foto mit `landschaft` bzw. `gebaeude` weiterhin.

**Backend — API-Integration**

- `test_api_photos.py`: `_cloud_vision_status_out` leitet `is_candidate` aus den gespeicherten Kriterien-Werten ab — Foto mit `landschaft`-Zeile → Kandidat, Foto mit ausschließlich `content_landscape`-Zeile (Altlauf) → kein Kandidat. `content_landscape` erscheint in den Bewertungsdetails mit `category_eligible=false` und "Flächigkeit".
- `test_api_category_override.py`: Rücknahme ohne erkannten Inhalt liefert `"unerkannt"`; ein verwaister Override (`"detail"`) bleibt bis zur Rücknahme bestehen.

**Frontend — Unit + Komponente (`vitest`)**

- `categoryLabels.test.ts`: `unerkannt` → "Nicht erkannt"; unbekannte Keys weiterhin generisch; `categoryAbbreviation('unerkannt')`.
- `CurateCategoriesPage.test.tsx`: exportierte reine Sortierfunktion (Muster `countPhotosInDay`/`toggleDayCollapse`) — `"unerkannt"` immer zuletzt, übrige alphabetisch, auch wenn `"unerkannt"` alphabetisch nicht letzter wäre und bei nur einer Kategorie. Seitentests für die drei Zustände (alle unerkannt / Mix / keine unerkannten); Erklärtext nur im `"unerkannt"`-Abschnitt, ohne Fehler-Semantik (kein `role="alert"`).

**Manuelle Verifikation (nicht automatisierbar).** AK7 wird durch das automatisiert getestete Diff-Werkzeug *ermöglicht*, aber nicht *erfüllt*: der Lauf auf einem echten Projekt (ein Lauf vor, ein Lauf nach der Umstellung) und die Bewertung der Übergangsmatrix sind manuelle Pflicht des Umsetzers vor dem Merge, Ergebnis im PR dokumentiert. Ein dabei sichtbarer Recall-Einbruch bei Landschaften ist laut Stakeholder-Entscheidung dokumentations-, nicht blockierungspflichtig (siehe AK2).

**Fundstellen-Hinweis für die Umsetzung:** die Umbenennung des Catch-all-Keys ist ein repo-weiter Fall — String-Literale `"detail"` stehen auch in Bestandstests (u.a. `frontend/src/components/CriterionDetailsList.test.tsx`).

## Entscheidungen

- `architect` konsultiert (Schritt 1): technischer Ansatz festgelegt, ADR [`0046`](../decisions/0046-inhaltsbasierte-landschaft-spezifitaets-vorrang-nicht-erkannt.md) angelegt (revidiert ADR 0023 Punkte 2 und 3, ohne sie zu ersetzen).
- `ux-ui-designer` konsultiert (Schritt 2): sichtbare Oberfläche bejaht, Gestaltung des "Nicht erkannt"-Abschnitts festgelegt (eigener Abschnitt, immer zuletzt im Cluster, neutraler Erklärtext ohne Fehler-Optik).
- `test-engineer` konsultiert (Schritt 3): Akzeptanzkriterien auf Testbarkeit geschärft (AK1–AK9), Teststrategie festgelegt, `architecture/0002-testkonzept.md` um fünf projektweite Regeln und einen Eintrag unter "Bekannte Lücken" ergänzt.
- `security-engineer` konsultiert (Schritt 3): sicherheitsrelevant an genau einer Stelle (Landmark-Vorfilterung), kein Blocker; `architecture/0003-securitykonzept.md` im Abschnitt "Cloud-Vision-API" ergänzt.
- **Stakeholder-Entscheidung (Daniel, 2026-08-30):** `CATEGORY_SPECIFIC_MIN_PHOTOS = 3` — eine präzise Erkennung bildet ab drei Fotos eine eigene Kategorie. Bewusst gegen `1` (Zersplitterung der Kuratierungsansicht in Ein-Foto-Abschnitte) und gegen `5` (seltene korrekte Erkennungen fielen wieder in "Nicht erkannt") entschieden.
- **Stakeholder-Entscheidung (Daniel, 2026-08-30):** Ein Remote-Schlagwort setzt sich gegenüber `content_people` durch — ein Foto mit Gesichtern und Label "Hochzeit" landet künftig unter "Hochzeit". Konsequente Lesart des Akzeptanzkriteriums "ein genauer erkannter Bildinhalt setzt sich gegenüber einer unspezifischen Einordnung durch".
- **Stakeholder-Entscheidung (Daniel, 2026-08-30):** Ein im Vorher/Nachher-Vergleich sichtbarer Recall-Einbruch bei Landschaften (ImageNet-Lücke Wald/Wiese/Feld) ist **kein Merge-Blocker**; der Befund wird im PR dokumentiert und die Nachkalibrierung als Folge-Ticket erfasst. AK2 ist entsprechend formuliert.
- **Stakeholder-Entscheidung (Daniel, 2026-08-30):** Das bestehende projektweite Cloud-Vision-Opt-in gilt trotz verschobener Kandidatenmenge unverändert weiter; kein Consent-Reset, kein zusätzlicher Zustimmungsschritt. Begründung im Abschnitt "Security" Punkt 1.

## Offene Fragen

Keine — alle im Ablauf aufgeworfenen Produktentscheidungen sind unter "Entscheidungen" festgehalten.

## Out of Scope

- Rückwirkende Neuberechnung bereits abgeschlossener Scoring-Läufe (die neue Logik greift erst beim nächsten Lauf).
- Mehrfachzuordnung eines Fotos zu mehreren Kategorien gleichzeitig.
- Projektspezifisch konfigurierbare Schwellwerte statt globaler Konstanten.
- Ein lokaler Detail-/Makro-Detektor als Ersatz für den weggefallenen Auffangkorb "Detail".
- Ein zweites Szenenmodell (Places365 o.ä.) zum Schließen der ImageNet-Lücke bei Wald/Wiese/Feld.
- Eine Produktoberfläche für den Vorher/Nachher-Vergleich (bewusst nur CLI).
- Mehr als zwei Spezifitätsstufen oder eine Feinsortierung innerhalb der lokalen Kriterien.
