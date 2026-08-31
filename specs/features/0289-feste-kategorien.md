# 0289 - Feste Kategorien statt offenem Vokabular

**Status:** Implemented ([PR #293](https://github.com/TheRealKoller/photosort/pull/293))
**Erstellt:** 2026-08-30
**Bezug:** [Issue #289](https://github.com/TheRealKoller/photosort/issues/289)

## Ziel

Die inhaltliche Kategorisierung der Fotos ist heute unvorhersehbar und zu feingliedrig: Die Kategorien entstehen überwiegend aus frei gewählten Schlagworten der Vision-KI, sodass in jedem Projekt andere, beliebig geschnittene Kategorien auftauchen. Die Kuratierung gruppiert die Fotos aber genau nach diesen Kategorien — eine zersplitterte, projektabhängige Kategorienmenge macht damit den Kernmechanismus der Kuratierung schlechter statt besser. Daniel hat das konkret als störend erlebt.

Ziel ist eine feste, anwendungsweit einheitliche Kategorienliste, aus der jedes Foto genau eine Kategorie erhält — vorhersehbar, projektübergreifend gleich und damit als Gruppierungsachse für die Kuratierung tauglich. Frei formulierte Feinlabels bleiben erhalten, aber nur noch als Zusatzinformation am Foto, nicht mehr als Kategoriequelle.

Diese Spec kehrt die frühere bewusste Entscheidung für ein offenes Vokabular (ADR [`0032`](../decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md)) um. Das ist gewollt und im Ausgangs-Issue ausdrücklich so benannt.

## User Story

Als Betreiber der PhotoSort-Installation möchte ich, dass jedes Foto genau eine Kategorie aus einer festen, immer gleichen Kategorienliste erhält, damit die Kuratierung nach einer vorhersehbaren Struktur gruppiert statt nach beliebig feingliedrigen, projektabhängigen KI-Schlagworten.

## Akzeptanzkriterien

**Festes Kategorien-Set**

> Die Akzeptanzkriterien sind gegenüber dem Story-Wortlaut auf Testbarkeit geschärft (`test-engineer`, Schritt 3 des spec-writer-Ablaufs). Fachlich ist nichts hinzugekommen oder entfallen; ergänzt wurden nur prüfbare Formulierungen und die zuvor implizite Abgrenzung gegenüber der Laufhistorie.

- [ ] Es existiert ein festes, anwendungsweit einheitliches Kategorien-Set mit genau diesen zwölf Kategorien: Menschen, Tier, Pflanze, Landschaft, Gebäude & Bauwerk, Innenraum, Essen & Trinken, Fahrzeug, Gegenstand, Dokument & Screenshot, Kunst & Kreatives, Sport & Aktivität — zuzüglich des Catch-alls "Nicht erkannt" (13 Registry-Einträge insgesamt).
- [ ] Jeder von einem `score-criteria`-Lauf geschriebene `PhotoRanking.category_key` und jeder über die API ausgelieferte Kategoriewert liegt im festen Set; unbekannte Werte aus der Remote-Antwort werden verworfen und führen nie zu einer Kategorie außerhalb des Sets. Ausdrücklich ausgenommen: `PhotoRanking`-Zeilen aus Läufen **vor** dieser Änderung behalten ihre Altwerte — die Laufhistorie wird nicht migriert.
- [ ] Es gibt genau eine Kategorien-Registry; lokale und remote Kandidaten gehen als **eine** Menge in `resolve_category` ein. Die Herkunft eines Kandidaten beeinflusst das Ergebnis nicht: dieselbe Kandidatenmenge liefert dieselbe Kategorie, unabhängig davon, ob sie lokal oder remote entstanden ist.
- [ ] Jeder der 13 Registry-Einträge hat eine nichtleere Definition und eine nichtleere Negativabgrenzung (z.B. Blumenwiese als Weitwinkelszene → Landschaft, Blütennahaufnahme → Pflanze); beide erscheinen im generierten Klassifizierungs-Prompt. *(Die inhaltliche Trennschärfe der Formulierungen ist nicht automatisiert prüfbar — manueller Stichproben-Review nach dem ersten produktiven Lauf.)*

**Zuordnungsregeln**

- [ ] Der generierte Prompt enthält die Leitfrage "Was ist das dominante Bildmotiv?" und die Anweisung, Anlass-/Ereignisbegriffe (Geburtstag, Urlaub, Weihnachten, Hochzeit) ausschließlich als Feinlabel zu vergeben. Kein Eintrag der Registry ist ein Anlass-/Ereignisbegriff.
- [ ] Für Fotos mit mehreren in Frage kommenden Motiven gilt eine festgelegte, deterministische Vorrangreihenfolge, sodass dieselbe Bildsituation reproduzierbar dieselbe Kategorie ergibt: Dokument & Screenshot → Sport & Aktivität → Menschen → Tier → Essen & Trinken → Fahrzeug → Kunst & Kreatives → Pflanze → Gebäude & Bauwerk → Landschaft → Innenraum → Gegenstand.
- [ ] Ein Foto, für das sowohl `sport_aktivitaet` als auch `menschen` Kandidat ist, erhält `sport_aktivitaet`. *(Begründung: bei sportlichen Aktivitäten sind fast immer Personen bildbestimmend — ohne diesen Vorrang könnte die Kategorie faktisch nie gewinnen.)*
- [ ] "Nicht erkannt" ist keine bloß nachgelagerte Ausweichlösung, sondern eine reguläre Möglichkeit. Prüfbar heißt das:
  - [ ] `nicht_erkannt` ist im Klassifizierungs-Prompt als wählbare Option enthalten und darf vom Modell als Kandidat genannt werden.
  - [ ] Ist `nicht_erkannt` der einzige gültige Kandidat, ist es das Ergebnis.
  - [ ] Steht `nicht_erkannt` neben mindestens einer echten Kategorie, gewinnt die echte Kategorie.
  - [ ] Ist die Kandidatenmenge leer (auch nach dem Verwerfen unbekannter Werte), ist das Ergebnis `nicht_erkannt`.
  - [ ] `nicht_erkannt` ist in der manuellen Override-Auswahl wählbar.
- [ ] "Nicht erkannt" und "Gegenstand" sind klar voneinander abgegrenzt: `gegenstand` ist letzter Eintrag der Vorrangreihenfolge und wird nur bei einem tatsächlichen Kandidaten vergeben — ein Foto mit ausschließlich dem Kandidaten `gegenstand` erhält `gegenstand`, nie `nicht_erkannt`. `nicht_erkannt` steht außerhalb der Reihenfolge und bedeutet, dass gar kein Motiv sicher bestimmt werden konnte.

**Freie Feinlabels**

- [ ] Zusätzlich zur Pflicht-Kategorie werden bis zu zwei frei formulierte Feinlabels je Foto ermittelt und am Foto als Zusatzinformation angezeigt. Liefert das Modell mehr, werden nach der Validierung die ersten zwei übernommen; liefert es keine gültigen, hat das Foto keine Feinlabels (kein Platzhalter in der Oberfläche).
- [ ] Feinlabels gehen nicht in `resolve_category` ein; ein Lauf mit Feinlabels erzeugt in der Kuratierung keine zusätzlichen Gruppen gegenüber demselben Lauf ohne Feinlabels.
- [ ] Die Anlass-Dimension (Geburtstag, Urlaub, Weihnachten) wird ausschließlich über diese freien Feinlabels abgebildet — kein eigenes Feld, kein eigener Mechanismus.
- [ ] Feinlabels werden auch dann festgehalten, wenn die Kategorie "Nicht erkannt" lautet.
- [ ] `GET /projects/{id}/fine-labels` liefert je Feinlabel `photo_count`, absteigend sortiert, Tie-Break `canonical_key` aufsteigend; die Remote-Klassifizierungs-Sektion zeigt daraus die häufigsten Einträge, sodass erkennbar wird, welche Kategorie im festen Set gegebenenfalls fehlt (Änderungspfad für das Set, statt einer Einmal-Festlegung).

**Bestehendes Verhalten**

- [ ] Die manuelle Übersteuerung der Kategorie eines einzelnen Fotos bleibt erhalten und bietet alle 13 Einträge des Sets an, **unabhängig davon, was für dieses Foto erkannt wurde**. Ein Set-Key, der für dieses Foto kein Kandidat ist, wird jetzt akzeptiert (bisher `409`); ein Key außerhalb des Sets — auch ein Altwert wie `"unerkannt"` — wird mit `422` abgelehnt; ohne `PhotoRanking`-Zeile im aktuellen Lauf bleibt es bei `409`.
- [ ] Ist die Remote-Kategorisierung für ein Projekt nicht aktiviert, wird nur die lokal bestimmbare Teilmenge des Sets vergeben — genau `menschen`, `tier`, `essen_trinken`, `fahrzeug`, `gebaeude_bauwerk`, `landschaft`; alle übrigen Fotos erhalten `nicht_erkannt`. Keine der sechs übrigen Kategorien darf in einem Lauf ohne Remote-Klassifizierung auftauchen. (Annahme im Refinement getroffen, weil lokal nicht alle zwölf Kategorien erkennbar sind.)
- [ ] Die Oberfläche verwendet durchgängig die deutschen Bezeichnungen des Sets: Alle Anzeigenamen stammen aus `GET /categories`, das Frontend enthält keine eigene Übersetzungstabelle für Set-Keys; der generische Fallback greift ausschließlich für Altwerte aus der Laufhistorie.

## Datenmodell-Bezug

Neu: `PhotoCategoryClassification` (1:1 zu `Photo`, hält die remote ermittelte Kategorie samt Kandidatenliste). Umbenannt: `CategoryLabel` → `FineLabel`, `PhotoCategoryDetection` → `PhotoFineLabel` (ohne `confidence`). Betroffen: `PhotoScore.category_override`. Siehe [`docs/architecture.md`](../../docs/architecture.md).

## Architektur / Umsetzung

> Architekturentscheidung: ADR [`0049`](../decisions/0049-festes-kategorien-set-mit-vorrangreihenfolge-und-freien-feinlabels.md) — **löst ADR 0032 (offenes Vokabular) und ADR 0023 (Häufigkeits-Ableitung) ab**, revidiert ADR 0047 in den Punkten 2–4 (Punkte 1, 5, 6, 7 gelten weiter).

### Gewählter Ansatz

Die Kategorie eines Fotos entsteht künftig als **reine Pro-Foto-Funktion über ein geschlossenes Set** statt aus einer laufweiten Häufigkeitsaggregation. Lokale Detektoren und die Remote-Klassifizierung sind zwei Zulieferer **einer** Kandidatenmenge; welche davon gewinnt, entscheidet ausschließlich die feste Vorrangreihenfolge im Code:

```
kandidaten   = lokale_signale(criterion_values) | remote_kategorie(photo_category_classifications)
category_key = score.category_override or resolve_category(kandidaten)
```

Damit ist die Zuordnung unabhängig davon, welche anderen Fotos im Projekt liegen — genau die Vorhersehbarkeit, die die Story verlangt.

### Das feste Set (Prompt-Grundlage)

Leitfrage für jede Zuordnung, lokal wie remote: **„Was ist das dominante Bildmotiv?"** Anlass-/Ereignisbegriffe bilden keine Kategorie.

| # | `key` | Anzeigename | Definition | Negativabgrenzung |
|---|---|---|---|---|
| 1 | `menschen` | Menschen | Eine oder mehrere Personen sind das bildbestimmende Motiv (Porträt, Gruppenbild, Schnappschuss von Personen). | Nicht, wenn Personen nur klein/beiläufig im Bild sind, während ein anderes Motiv den Bildraum bestimmt (Passanten vor einem Bauwerk → Gebäude & Bauwerk). Nicht bei sportlicher/körperlicher Aktivität (→ Sport & Aktivität). Nicht, wenn am gedeckten Tisch das Essen bildbestimmend ist (→ Essen & Trinken). |
| 2 | `tier` | Tier | Ein oder mehrere Tiere sind das bildbestimmende Motiv (Haustier, Wildtier, Vogel, Insekt, Fisch). | Nicht bei Tierdarstellungen als Skulptur, Gemälde oder Plüschtier (→ Kunst & Kreatives bzw. Gegenstand). Nicht bei zubereitetem Fleisch/Fisch als Speise (→ Essen & Trinken). |
| 3 | `pflanze` | Pflanze | Eine einzelne Pflanze oder eine Pflanzengruppe in Nah-/Mitteldistanz ist bildbestimmend (Blüte, Blatt, Baum, Strauch, Zimmerpflanze, Blumenstrauß). | Nicht bei einer Weitwinkelszene, in der Vegetation nur Teil der Landschaft ist — Blumenwiese als Weitwinkelszene → Landschaft, Blütennahaufnahme → Pflanze. Nicht bei Obst/Gemüse als Nahrungsmittel (→ Essen & Trinken). |
| 4 | `landschaft` | Landschaft | Eine weiträumige Natur- oder Außenszene ist bildbestimmend (Berge, Küste, See, Wald, Feld, Wüste, Himmel, Panorama). | Nicht, wenn ein Bauwerk oder eine Bebauung die Bildfläche bestimmt und die Natur nur Hintergrund ist (→ Gebäude & Bauwerk). Nicht bei Nah-/Detailaufnahmen einzelner Naturelemente (→ Pflanze bzw. Gegenstand). |
| 5 | `gebaeude_bauwerk` | Gebäude & Bauwerk | Ein Bauwerk oder eine bebaute Außenansicht ist bildbestimmend (Haus, Kirche, Burg, Brücke, Turm, Denkmal, Stadtansicht, Sehenswürdigkeit). | Nicht bei Aufnahmen aus dem Inneren eines Gebäudes (→ Innenraum). Nicht, wenn Bauwerke nur kleiner Teil einer weiten Naturszene sind (→ Landschaft). |
| 6 | `innenraum` | Innenraum | Ein Innenraum als Ganzes ist bildbestimmend (Zimmer, Halle, Restaurantraum, Ladenlokal, Innenarchitektur). | Nicht, wenn im Innenraum ein anderes Motiv bildbestimmend ist (Personen im Wohnzimmer → Menschen, Teller auf dem Tisch → Essen & Trinken). Nicht bei Außenansichten von Gebäuden (→ Gebäude & Bauwerk). |
| 7 | `essen_trinken` | Essen & Trinken | Speisen, Getränke oder ein gedeckter Tisch sind bildbestimmend. | Nicht bei Lebensmitteln als unauffälligem Beiwerk einer Raum- oder Personenszene. Nicht bei lebenden Nutzpflanzen im Feld (→ Pflanze bzw. Landschaft). |
| 8 | `fahrzeug` | Fahrzeug | Ein Fahrzeug ist bildbestimmend (Auto, Fahrrad, Motorrad, Bus, Zug, Boot, Flugzeug). | Nicht bei Straßen-/Stadtszenen, in denen Fahrzeuge nur Teil des Stadtbilds sind (→ Gebäude & Bauwerk). Nicht, wenn Personen im/am Fahrzeug bildbestimmend sind (→ Menschen). |
| 9 | `gegenstand` | Gegenstand | Ein konkreter, erkannter Gegenstand ohne passendere spezifischere Kategorie ist bildbestimmend (Werkzeug, Kleidung, Möbelstück, Gerät, Spielzeug, Objekt-Detailaufnahme). | **Nicht** als Ersatz für eine unsichere Erkennung — ist kein Motiv sicher bestimmbar, gilt „Nicht erkannt". Nicht, wenn eine spezifischere Kategorie zutrifft. |
| 10 | `dokument_screenshot` | Dokument & Screenshot | Eine Text-, Bildschirm- oder Dokumentabbildung ist bildbestimmend (Screenshot, abfotografiertes Dokument/Formular/Beleg, Ticket, QR-Code, Schild, dessen Text der Bildzweck ist). | Nicht bei Fotos, auf denen Text nur beiläufig vorkommt (Ladenschild in einer Straßenszene → Gebäude & Bauwerk). Nicht bei kunstvoll gestalteten Schriftbildern als Kunstwerk (→ Kunst & Kreatives). |
| 11 | `kunst_kreatives` | Kunst & Kreatives | Ein Kunstwerk oder ein kreatives Erzeugnis ist bildbestimmend (Gemälde, Skulptur, Wandbild/Graffiti, Museumsexponat, Handarbeit, Bastelarbeit, Zeichnung). | Nicht bei Bauwerken mit kunstvoller Fassade (→ Gebäude & Bauwerk). Nicht bei kunstvoll angerichteten Speisen (→ Essen & Trinken). |
| 12 | `sport_aktivitaet` | Sport & Aktivität | Eine sportliche oder körperlich aktive Handlung ist bildbestimmend (Laufen, Radfahren, Schwimmen, Ski, Ballsport, Wandern, Klettern, Spielplatz-Aktivität). | Nicht bei bloßem Posieren mit Sportgerät ohne erkennbare Handlung (→ Menschen). Nicht bei einem abgestellten Sportgerät ohne handelnde Person (→ Gegenstand bzw. Fahrzeug). |
| — | `nicht_erkannt` | Nicht erkannt | Kein Bildmotiv ist sicher bestimmbar — unscharf, zu dunkel, stark abstrakt, oder die Erkennung ist zu unsicher. | Nicht zu verwenden, wenn ein Motiv erkennbar ist, aber keine spezifischere Kategorie passt — dann „Gegenstand". |

**Vorrangreihenfolge** (`precedence`, kleiner gewinnt): `dokument_screenshot` → `sport_aktivitaet` → `menschen` → `tier` → `essen_trinken` → `fahrzeug` → `kunst_kreatives` → `pflanze` → `gebaeude_bauwerk` → `landschaft` → `innenraum` → `gegenstand`. `nicht_erkannt` steht außerhalb der Reihenfolge: Es darf als Kandidat genannt werden, verliert aber gegen jede echte Kategorie und ist das Ergebnis genau dann, wenn keine echte Kategorie unter den Kandidaten ist (leere Menge oder ausschließlich `nicht_erkannt`). `sport_aktivitaet` steht bewusst vor `menschen`.

### Entwurfsentscheidungen

1. **Eigenes Modul `categories.py`, nicht `criteria.py`.** Kriterien sind Mess-Signale fürs Ranking, das Set ist eine Produkt-Taxonomie — die Vermischung beider in `criteria.py` war die Ursache der Skalen-/Namensraum-Probleme aus ADR 0032/0047.
2. **Registry-Dataclass statt `StrEnum`.** Definition und Negativabgrenzung sind fachlich Teil der Kategorie (Prompt-Grundlage + UI-Erklärung); ein Enum hätte sie in eine zweite, driftende Struktur gedrängt.
3. **Der Prompt wird aus der Registry erzeugt** (`build_classification_prompt()`) — Prompt und Set können nicht auseinanderlaufen.
4. **Das Modell nennt Kandidaten, der Code entscheidet.** Der Prompt fragt nach *allen in Frage kommenden* Kategorien (max. 3), nicht nach „der einen richtigen". Die Vorrangreihenfolge ist damit testbar und reproduzierbar statt Modell-Ermessen.
5. **Das Set kommt vom Server** (`GET /categories`), keine TypeScript-Spiegelung — eine zweite Liste wäre eine dauerhaft driftende Kopie, und die Override-Auswahl braucht das volle Set unabhängig von der Erkennung.
6. **Eine gepflegte Mapping-Tabelle ist hier kein Rückfall hinter ADR 0023.** ADR 0023 vermied eine Liste, weil die Menge offen war; das Set ist jetzt per Produktentscheidung geschlossen.
7. **Konfidenzen im Remote-Pfad entfallen ersatzlos** — sie dienten nur der entfallenen Score-Auswahl. Eine persistierte Zahl ohne Codepfad wäre irreführender Ballast.
8. **Feinlabel-Infrastruktur bleibt unangetastet** (`resolve_canonical_label`, `label_embedding.py`, ADR 0033) — nur der Zweck verschiebt sich von „Kategoriebildung" zu „Häufigkeitsauswertung".

### Umsetzungsschritte (Reihenfolge verbindlich)

**1 — `backend/src/photosort/categories.py` (neu, rein, ohne Abhängigkeiten).**
`CategoryDefinition` (`key`, `display_name`, `definition`, `delimitation`, `precedence`), `CATEGORY_REGISTRY` mit genau den 13 Einträgen oben in Anzeigereihenfolge, `CATEGORY_NOT_RECOGNIZED = "nicht_erkannt"`, `LOCAL_CATEGORY_SIGNALS` (siehe Schritt 2), sowie `resolve_category(candidates) -> str` (unbekannte Werte ignorieren; `nicht_erkannt` fällt weg, sobald eine echte Kategorie dabei ist; leere Menge → `nicht_erkannt`), `build_classification_prompt() -> str`, `is_known_category(key) -> bool`. Registry-Invariantentests: eindeutige Keys, eindeutige `precedence`-Werte, jedes in `LOCAL_CATEGORY_SIGNALS` referenzierte Kriterium ist `category_eligible=True` mit gesetzter Schwelle (und umgekehrt).

**2 — Lokale Signale: `classification.py` + `criteria.py`.**
- `detect_animals` → `detect_objects` verallgemeinern (`AnimalDetection` → `ObjectDetection`, gleiche Felder, kein Allow-Listen-Filter mehr); der COCO-Detektor läuft weiterhin **genau einmal pro Foto**.
- Neue Allow-Listen: `VEHICLE_CATEGORIES = {"bicycle","car","motorcycle","airplane","bus","train","truck","boat"}`, `FOOD_CATEGORIES = {"banana","apple","sandwich","orange","broccoli","carrot","hot dog","pizza","donut","cake","wine glass"}` — bewusst **ohne** `cup`/`bottle`/`bowl`/Besteck (zu häufig beiläufig). Schreibweise einmalig gegen die im `.tflite` mitgelieferte Label-Datei verifizieren (Pflicht wie bei `LANDSCAPE_SCENE_CATEGORIES`).
- `compute_tier_score(objects)` filtert jetzt selbst auf `ANIMAL_CATEGORIES`; neu `compute_fahrzeug_score(objects)`, `compute_essen_trinken_score(objects)` (Muster: Allow-Listen-gefiltertes Konfidenz-Maximum, wie `compute_gebaeude_score`).
- **Verhaltenserhalt, testpflichtig:** `compute_golden_ratio_score` bekommt weiterhin nur die Tier-Erkennungen als Subjekt-Kandidaten (Hilfsfunktion `animal_detections(objects)`) — kein Auto/Teller als Kompositions-Subjekt.
- Registry: `fahrzeug`/`essen_trinken` als `LOCAL_ML`, `category_eligible=True`, Presence-Schwelle `0.01`. `CriterionDefinition.category_specificity` **entfernen**.
- **Löschen:** `derive_active_categories`, `derive_category_key`, `CATEGORY_ACTIVE_THRESHOLD_FRACTION`, `CATEGORY_SPECIFIC_MIN_PHOTOS`, `DYNAMIC_LABEL_PRESENCE_THRESHOLD`, `CATEGORY_SPECIFICITY_CONTENT/_NAMED`, `_specificity_of`, `CATEGORY_UNRECOGNIZED`, `_RESERVED_CATEGORY_KEY_SUFFIX`. `is_landmark_candidate` bleibt unverändert.
- `LOCAL_CATEGORY_SIGNALS`: `menschen←content_people`, `tier←tier`, `essen_trinken←essen_trinken`, `fahrzeug←fahrzeug`, `gebaeude_bauwerk←gebaeude|landmark`, `landschaft←landschaft`. `landmark` verliert die eigene Kategorie (der Name bleibt am Foto sichtbar).

**3 — `models.py` + eine Alembic-Revision (vier Schritte).**
- (a) neue Tabelle `photo_category_classifications` (1:1 zu `Photo`: `photo_id` PK+FK, `category_key`, `detected_categories` JSON, `provider`, `computed_at`; `Photo.category_classification`, `cascade="all, delete-orphan"`).
- (b) `category_labels` → `fine_labels`, `photo_category_detections` → `photo_fine_labels`, Spalte `category_label_id` → `fine_label_id`, Constraint → `uq_fine_label_photo_label`; `confidence` in `photo_fine_labels` entfällt.
- (c) `DELETE FROM photo_fine_labels` (Zeilen stammen aus dem alten Prompt) — die Vokabular-Registry `fine_labels` **bleibt** erhalten.
- (d) `UPDATE photo_scores SET category_override = NULL` — **Pflichtschritt**, sonst erzeugt `run_criterion_scoring` weiter Kategorien außerhalb des Sets.
- Kein Eingriff in `PhotoRanking` (Laufhistorie, Vorher-Stand für `category_diff.py`).

**4 — `remote_classification.py`.**
`RemoteClassification` (`categories: tuple[str,...]`, `fine_labels: tuple[str,...]`) ersetzt `list[CategoryLabelDetection]`; `CategoryDetectionClientLike.classify` gibt sie zurück. `_PROMPT` → `categories.build_classification_prompt()`. `_classification_from_json`: strukturell hart (fehlendes/ungültiges `categories` → `RemoteCategoryClassificationApiError`, Foto best-effort übersprungen), inhaltlich tolerant (unbekannte Kategoriewerte verwerfen + `WARNING` mit Rohwert loggen, ADR-0034-Muster; auf `MAX_REMOTE_CATEGORIES_PER_PHOTO = 3` bzw. `MAX_FINE_LABELS_PER_PHOTO = 2` kürzen; `MAX_FINE_LABEL_LENGTH = 60`). `_MAX_RESPONSE_TOKENS` bleibt 256. **`COST_PER_IMAGE_USD` neu verifizieren** — der Prompt wächst um grob 500–700 Input-Tokens (Anthropic ≈ +$0,0005–0,0007/Bild); Herleitung als Kommentar fortschreiben (Pflicht wie ADR 0032 Punkt 8). `resolve_canonical_label`/`CATEGORY_LABEL_SIMILARITY_THRESHOLD` unverändert.

**5 — `worker.py`.**
`run_remote_category_classification`: pro Foto eine `photo_category_classifications`-Zeile (`category_key = resolve_category(remote_kandidaten)`, `detected_categories` = validierte Liste) plus 0–2 `photo_fine_labels`-Zeilen über `resolve_canonical_label`; Feinlabels auch bei `nicht_erkannt`. `select_remote_category_candidates`: Skip anhand der Klassifikations-Zeile. `run_criterion_scoring`: `_merge_remote_category_labels` **löschen**, stattdessen die Klassifikations-Zeilen der Kandidaten laden und je Foto `resolve_category(lokale ∪ remote)` aufrufen (Override weiterhin vorrangig). `reassign_photo_category` unverändert; die Rekonstruktion im `DELETE`-Override nutzt dieselbe neue Ableitung.

**6 — API.**
Neuer Router `api/categories.py` (`GET /categories`, Router-Level-Auth, `key`/`display_name`/`definition`/`locally_available`) in `main.py` einhängen. `api/photos.py`: `PUT /photos/{id}/category-override` validiert per `is_known_category` (`422` unbekannt, `409` weiterhin ohne `PhotoRanking`-Zeile), `_photo_category_candidate_keys` löschen; `PhotoOut.remote_category_labels` → `fine_labels: list[FineLabelOut]`, neu `remote_category: str | None`, `category_candidates` nur noch Set-Keys + `origin` (ohne `score`); `_cloud_vision_status_out` leitet den Remote-Erfolg aus der Klassifikations-Zeile ab. `api/projects.py`: `GET /projects/{id}/fine-labels` (nach `photo_count` absteigend, Tie-Break `canonical_key`).

**7 — Frontend.**
`api/types.ts` nachziehen; `useCategories`-Query (langlebiger Cache). `categoryLabels.ts`: `CATEGORY_DISPLAY_NAME_OVERRIDES` entfernen, `formatCategoryKey` schlägt im geladenen Set nach (generischer Fallback nur noch für Altwerte), `categoryAbbreviation` bildet das Kürzel aus dem Anzeigenamen (kollisionsfrei fürs Set). `CurateCategoriesPage.tsx`: `CATCH_ALL_CATEGORY_KEY = 'nicht_erkannt'`, `sortCategoryKeys` nach Registry-Reihenfolge (unbekannte Altwerte danach, `nicht_erkannt` immer zuletzt). `CriterionDetailsList.tsx`: Override-Auswahl über **alle** 13 Kategorien, Kandidatenliste bleibt daneben als Erklärung; Feinlabel-Chips. `RemoteCategoryClassificationSection.tsx`: Feinlabel-Häufigkeitsliste. Konkrete Bedienform der Auswahl → Abschnitt UI/UX.

**8 — Doku.** `docs/architecture.md` ist bereits im Rahmen dieser Spec fortgeschrieben (Komponenten Frontend/Backend/Worker, neue Datenmodell-Bullets, „Letzte Aktualisierung"). Bei Abweichungen der Umsetzung dort nachziehen. `docs/setup.md` unberührt (keine neue Umgebungsvariable, kein neuer Setup-Schritt).

### Betroffene Dateien

`backend/src/photosort/categories.py` (neu), `criteria.py`, `classification.py`, `remote_classification.py`, `worker.py`, `models.py`, `api/categories.py` (neu), `api/photos.py`, `api/projects.py`, `main.py`, `alembic/versions/<neu>.py`; `frontend/src/api/types.ts`, `hooks/` (neue Categories-Query), `utils/categoryLabels.ts`, `components/CategoryBadge.tsx`, `components/CriterionDetailsList.tsx`, `components/RemoteCategoryClassificationSection.tsx`, `pages/CurateCategoriesPage.tsx`, `pages/PhotoDetailPage.tsx` + zugehörige Tests. Unverändert: `ranking.py`, `category_diff.py`, `label_embedding.py`, `cloud_vision.py`, `landmark.py`.

### Bekannte Grenzen (bewusst akzeptiert)

- **Nur sechs der zwölf Kategorien sind lokal bestimmbar.** Ohne Remote-Lauf wird „Nicht erkannt" der größte Abschnitt — von der Story so vorgesehen, aber das größte Risiko dieser Entscheidung: der Nutzen hängt für sechs Kategorien vollständig an einem kostenpflichtigen Cloud-Lauf.
- **`pflanze` bewusst nicht lokal**: ImageNet-1k kennt nur einzelne Arten, und die schwierigste Abgrenzung des Sets (Weitwinkel vs. Nahaufnahme) hängt an der Aufnahmedistanz, die das Modell nicht liefert. Nachrüstbar als reine Listen-Änderung.
- **Bestehende manuelle Overrides gehen verloren** (Migration d) — unvermeidbar, durch „keine erhaltenswerten Bestände" gedeckt, gehört in die PR-Beschreibung.
- Bis zum ersten neuen `score-criteria`-Lauf zeigt die Kuratierung noch die alten Kategorien der Laufhistorie.

## UI/UX

Das Feature betrifft drei Frontend-Bereiche: die Kategorie-Override-Auswahl in Detailansicht/Popover, die Feinlabel-Darstellung am Foto und die Häufigkeitsliste in der Remote-Klassifizierungs-Sektion. Folgende Entscheidungen halten die Oberfläche konsistent mit dem bestehenden Design-System (insbesondere "Auffangkorb-Kategorie mit erklärend dezentem Signal", "Mehrfachkandidaten-Vergleich mit Override-Aktion").

**Bedienform der Kategorie-Override-Auswahl (CriterionDetailsList.tsx)**

Die bisherige Kandidaten-Übersicht bleibt strukturell erhalten; zusätzlich wird eine neue "Alle Kategorien"-Auswahl angeboten, die alle 13 Einträge des Sets (12 Kategorien + "Nicht erkannt") enthält — als eigene Komponente für bessere Wartbarkeit. Konkrete Umsetzung:

- **Desktop:** Inline-Dropdown (nativer `<select>` oder Combobox via shadcn/ui + Radix) mit allen 13 Einträgen, sortiert in der Anzeigereihenfolge der Registry (nicht alphabetisch, damit die Reihenfolge überall im Produkt identisch ist), "Nicht erkannt" steht immer zuletzt — über die exportierte Sortierfunktion `sortCategoryKeys`.
- **Mobil (PWA):** Modal-Dialog statt Dropdown, Kategorie-Liste mit Touch-freundlichen 44×44px-Tap-Zielen pro Zeile, dezente Überschrift "Alle Kategorien", "Abbrechen"-Schaltfläche am unteren Ende.
- **Beide Modi:** Vollständiger Anzeigename (nicht Kürzel) pro Kategorie. "Nicht erkannt" trägt einen kurzen Erklärtext (1–2 Zeilen, z.B. als Tooltip oder Untertitel in der Liste): "Verwendet, wenn kein Bildmotiv sicher bestimmbar ist."
- **Kandidaten-Kontext bleibt:** Die bisherige "Kategorie-Kandidaten"-Gruppe wird zur Erklärung um die neue "Alle Kategorien"-Auswahl ergänzt (nicht ersetzt), damit der Nutzer sieht, was das System erkannt hat, bevor er es übersteuert.

**„Nicht erkannt" als reguläre Option (Design-System-Konsistenz)**

"Nicht erkannt" trägt kein Fehler-Styling (konsistent mit dem Muster "Auffangkorb-Kategorie…" aus Spec 0217/ADR 0047), ist aber eindeutig identifizierbar:

- **Visuell:** Derselbe neutrale Badge-Ton wie bei den anderen Kategorien (nicht rot/warnungsähnlich).
- **Position:** Immer zuletzt in kategorialen Listen (Kandidaten, Override-Auswahl) via `sortCategoryKeys`.
- **Erklärtext:** Der Tooltip/Untertitel in der Override-Liste macht seine Rolle klar (s.o.).

**Feinlabel-Darstellung (CriterionDetailsList.tsx, PhotoDetailPage.tsx)**

Feinlabels (bis zu zwei pro Foto) sind Zusatzinformation, nicht Kategorien — visuelle Abgrenzung ist essentiell:

- **Chips/Badges:** Rendering als dezente `<Badge>`-Komponente (Radix + shadcn/ui), aber mit anderem Ton als die Kategorie-Badge (z.B. `tone="secondary"` oder ausdrücklich definierten `className` für Feinlabel-spezifisches Styling).
- **Position:** Unter oder neben der Kategorie-Anzeige, räumlich deutlich getrennt, kleiner/kompakter als die Kategorie.
- **Beschriftung:** Vollständiger Text oder gekürzt je nach Platz; kein Icon/Symbol (um sie nicht mit den foto-bewertungsspezifischen Farben/Symbolen zu verwechseln).
- **Auch bei „Nicht erkannt":** Feinlabels bleiben sichtbar (Spec-Anforderung), damit erkennbar ist, was das System auch bei unbekannter Hauptkategorie vermutete.

**Feinlabel-Häufigkeitsliste (RemoteCategoryClassificationSection.tsx)**

Neue Section `GET /projects/{id}/fine-labels` zeigt häufigste Feinlabels und wo sie fehlende Kategorien andeuten würden:

- **Layout:** Tabellarisch oder als Listenzeilen mit Label + Häufigkeit (z.B. "Blüte – 17 Mal").
- **Sortierung:** Nach `photo_count` absteigend, Tie-Break alphabetisch (`canonical_key`).
- **Begrenzung:** Maximal die häufigsten 10–15 Einträge, um Überinformation zu vermeiden.
- **Kontext:** Kurz danach oder als Kopfzeile: "Diese Feinlabels traten häufig auf — möglicherweise fehlt eine Kategorie im Set" (Hint für künftige Konfigurationsänderungen).
- **Zustände:** Während des Ladens Skeleton oder Spinner; Fehler inline als Alert mit Retry-Option; leer, wenn keine Feinlabels vorhanden ("Keine zusätzlichen Label ermittelt").

**Kategorie-Abkürzungen in Badges (CategoryBadge.tsx, categoryLabels.ts)**

Die bisherige `categoryAbbreviation()`-Funktion ändert sich funktional nicht, ist aber jetzt gegen das feste Set determiniert (statt generisch "erste 3 Zeichen"):

- **Regel:** Erste 3 Zeichen des Anzeigenamens (aus dem Server-Set), großgeschrieben.
- **Kollisionssicherheit:** Das feste 13er-Set ist kollisionsfrei im Präfix (z.B. "MEN" für Menschen, "TIE" für Tier, "NIC" für Nicht erkannt).
- **Altwerte (aus Laufhistorie):** Fallback auf generischen Fallback (Großbuchstabe + Rest), falls eine alte `category_key` nicht im geladenen Set vorkommt.

**Zustände während des kategorialen Ladens**

Die `useCategories`-Query lädt `GET /categories` zu Komponentenmount und cacht das Set (langlebig, Invalidierung nur bei Login-Wechsel). Während dieser Phase:

- **Laden:** Override-Button ggf. mit Inline-Skeleton/Spinner disabled ("wird geladen…").
- **Fehler:** Inline-Alert über der Auswahl-Komponente, z.B. "Kategorien konnten nicht geladen werden. Bitte aktualisieren Sie die Seite." mit einem "Erneut versuchen"-Button.
- **Erfolg:** Auswahl sofort bedienbar.

**Bekannte Grenzen & Design-Entscheidungen**

- Längere Namen wie "Dokument & Screenshot", "Gebäude & Bauwerk" passen in Badges als Kürzel ("DOK", "GEB"), nicht ausgeschrieben — vollständige Namen nur als `title`/`aria-label`.
- "Nicht erkannt" wird nicht als Platzhalterzustand missbraucht (z.B. "noch nicht geprüft"); es ist die echte Fachkategorie für unsichere Erkennung (Spec-Akzeptanzkriterium).
- Feinlabels entstehen ausschließlich im Remote-Lauf. Vorher — und in Projekten ohne aktivierte Remote-Kategorisierung — hat ein Foto schlicht keine Feinlabels; der Chip-Bereich entfällt dann ersatzlos, ohne Platzhalter oder Hinweis. Altbestände gibt es nicht, da die Migration `photo_fine_labels` leert.

## Teststrategie

**Einordnung.** Der fachliche Kern dieser Spec ist eine *reine Funktion über einer geschlossenen Datenstruktur* (`resolve_category` über `CATEGORY_REGISTRY`) — anders als bei den vorangegangenen Kategorie-Specs (0045/0055/0217) liegt der Testschwerpunkt deshalb **nicht** auf der Worker-Integration, sondern auf der Unit-Ebene in `backend/tests/test_categories.py` (neu). Die Integrationsebene beweist nur noch die *Verdrahtung* (wer ruft `resolve_category` mit welcher Kandidatenmenge auf, was landet in der DB/der API-Antwort), nicht mehr die Zuordnungslogik selbst. Vier Stellen sind ausdrücklich **Regressions-, nicht Neubau-Tests**: `compute_golden_ratio_score`, `compute_tier_score`, `PUT /photos/{id}/category-override` und die Kategorie-Rekonstruktion im `DELETE`-Override.

### 1 — `categories.py`: `resolve_category` (Unit, Schwerpunkt, `test_categories.py`)

Reine Funktion, keine DB, keine Fixtures. Pflichtfälle:

- **Vorrang paarweise und vollständig:** ein parametrisierter Test über **alle** Paare `(a, b)` der zwölf Kategorien — `resolve_category({a, b})` liefert den Eintrag mit der kleineren `precedence`, und zwar symmetrisch (die Eingabereihenfolge darf das Ergebnis nicht verändern; die Paare deshalb in beiden Richtungen prüfen). Die Erwartung wird aus der Registry abgeleitet, damit der Test bei einer künftigen Umsortierung mitwandert.
- **Die bewusste Regel als eigener, literaler Testfall:** `resolve_category({"menschen", "sport_aktivitaet"}) == "sport_aktivitaet"` — ausdrücklich zusätzlich zum generischen Paartest, weil dieses Paar eine Produktentscheidung ist und nicht stillschweigend mit einer Umsortierung der Registry kippen darf.
- **Drei und mehr Kandidaten:** `{"landschaft", "menschen", "dokument_screenshot"}` → `dokument_screenshot`; belegt, dass nicht nur paarweise verglichen wird.
- **Leere Kandidatenmenge → `nicht_erkannt`** (nicht `""`, nicht `None`, kein `KeyError`).
- **Unbekannte Werte werden ignoriert, nicht abgelehnt:** `{"einhorn"}` → `nicht_erkannt`; `{"einhorn", "tier"}` → `tier`; `{"", "  ", "TIER"}` → `nicht_erkannt` (kein Case-/Whitespace-Fallback — abweichende Groß-/Kleinschreibung ist kein gültiger Key).
- **`nicht_erkannt` als Kandidat:** `{"nicht_erkannt"}` → `nicht_erkannt`; `{"nicht_erkannt", "gegenstand"}` → `gegenstand` (die echte Kategorie verdrängt den Auffangwert, auch wenn sie in der Vorrangreihenfolge letzte ist); `{"nicht_erkannt", "einhorn"}` → `nicht_erkannt`.
- **`gegenstand` ≠ `nicht_erkannt`:** `{"gegenstand"}` → `gegenstand`, nie `nicht_erkannt` — Regressionsschutz gegen eine Implementierung, die den letzten Platz der Reihenfolge mit dem Auffangwert verwechselt.
- **Eingabetyp-Robustheit:** identisches Ergebnis für `set`, `frozenset`, `list` und `tuple` mit Duplikaten (`["tier", "tier", "menschen"]` → `menschen`); die Funktion darf ihre Eingabe nicht mutieren.

`is_known_category` bekommt eigene Fälle (jeder der 13 Keys `True`, inklusive `nicht_erkannt`; unbekannter Wert, leerer String, Wert mit abweichender Groß-/Kleinschreibung `False`) — es ist die Validierungsfunktion des Override-Endpunkts und darf nicht nur indirekt über die API abgedeckt sein.

### 2 — Registry-Invarianten (Unit, `test_categories.py` + `test_criteria.py`)

Fortführung des mit ADR 0023 etablierten Registry-Invariantenmusters, hier erstmals **modulübergreifend** (`categories.py` ↔ `criteria.py`):

1. **Eindeutige Keys** — `len(CATEGORY_REGISTRY) == len({d.key for d in ...})`, und der Dict-Schlüssel stimmt mit `definition.key` überein (Copy-Paste-Schutz).
2. **Eindeutige `precedence`** — alle `precedence`-Werte der zwölf Kategorien paarweise verschieden; zusätzlich: sie bilden lückenlos `1..12` (verhindert, dass ein Eintrag beim Einfügen einer neuen Kategorie stillschweigend dieselbe Stufe erbt).
3. **`nicht_erkannt` steht außerhalb der Reihenfolge** — eigener, expliziter Test (kein `precedence`-Wert bzw. ein ausdrücklich als „außerhalb" markierter Sentinel), damit die Sonderrolle strukturell gilt und nicht nur per Konvention.
4. **Nichtleere `definition` und `delimitation` für jeden der 13 Einträge** (parametrisiert über die Registry) — die Texte sind Prompt-Grundlage und UI-Erklärung, ein leeres Feld wäre sonst erst im produktiven Cloud-Lauf sichtbar.
5. **Ein bewusst redundanter, literaler Test „genau diese 13 Keys, genau in dieser Reihenfolge"** — eine rein aus der Registry abgeleitete Prüfung bliebe grün, wenn eine Kategorie versehentlich gelöscht oder umsortiert würde. Dieser eine Test ist der Nachweis des Akzeptanzkriteriums und darf im Review nicht als „redundant zur Registry" gestrichen werden (gleiche Verbindlichkeit wie der Ein-Aufruf-Spy aus ADR 0047 Punkt 2).
6. **Konsistenz `LOCAL_CATEGORY_SIGNALS` ↔ `criteria.py`**, in beide Richtungen:
   - jeder dort referenzierte Kategorie-Key existiert in `CATEGORY_REGISTRY` und ist nicht `nicht_erkannt`;
   - jedes dort referenzierte Kriterium existiert in `CRITERIA_REGISTRY`, hat `category_eligible=True` und eine gesetzte `category_presence_threshold`;
   - **und umgekehrt:** jedes `category_eligible=True`-Kriterium taucht in mindestens einem `LOCAL_CATEGORY_SIGNALS`-Eintrag auf. Ohne diese Gegenrichtung entstünde unbemerkt genau der Zustand, den Schritt 2 für `landmark` bewusst herstellt (kategorie-fähig, aber keine eigene Kategorie mehr) — `landmark` gehört deshalb als **benannte, kommentierte Ausnahme** in den Test, nicht durch Weglassen der Gegenrichtung umgangen.
   - benannte Stichproben (nicht nur strukturell): die sechs lokal bestimmbaren Kategorien sind exakt `menschen`, `tier`, `essen_trinken`, `fahrzeug`, `gebaeude_bauwerk`, `landschaft` — literal geprüft, damit ein versehentlich zusätzlich verdrahtetes Signal auffällt.
7. **`category_specificity` ist restlos entfernt** — ein Test, der `CriterionDefinition` auf das erwartete Feld-Set prüft, plus repo-weite Fundstellensuche vor der Umsetzung (siehe Abschnitt 9).

### 3 — `build_classification_prompt()` (Unit, `test_categories.py`)

**Keine Assertion auf den vollständigen Prompt-Wortlaut** (bräche bei jeder Formulierungs-Nachjustierung und hätte keinen Aussagewert). Stattdessen strukturelle Eigenschaften:

- Für **jeden** Registry-Eintrag (parametrisiert) kommen `display_name`, `definition` und `delimitation` im erzeugten Prompt vor — das ist der Testnachweis für Entwurfsentscheidung 3 („Prompt und Set können nicht auseinanderlaufen").
- Ein Test, der die Registry temporär um einen Fake-Eintrag erweitert (monkeypatch) und prüft, dass dieser im Prompt erscheint — belegt, dass der Prompt tatsächlich generiert und nicht als Literal danebengelegt wird.
- Der Prompt enthält die Leitfrage („dominantes Bildmotiv"), die Obergrenzen (max. 3 Kategorien, max. 2 Feinlabels) und die Anweisung, Anlass-/Ereignisbegriffe nur als Feinlabel zu vergeben — jeweils als gezielte Teilstring-/Zahlprüfung gegen die Konstanten `MAX_REMOTE_CATEGORIES_PER_PHOTO`/`MAX_FINE_LABELS_PER_PHOTO` statt gegen hartkodierte Zahlen.
- `nicht_erkannt` ist im Prompt als wählbare Option enthalten (Akzeptanzkriterium „explizit Teil der auswählbaren Möglichkeiten").

### 4 — Lokale Signale: `detect_objects`, `compute_tier_score`, `compute_golden_ratio_score`

Die Verallgemeinerung `detect_animals` → `detect_objects` ist die **Gegenrichtung** zu ADR 0047 Punkt 1 (dort wanderte eine Schwelle aus einer geteilten Funktion in die Konsumenten; hier wandert ein Allow-Listen-*Filter* aus der geteilten Funktion in die Konsumenten). Dieselbe Regel gilt verschärft: jeder Bestands-Konsument braucht einen expliziten Test, dass er den Filter **selbst** durchsetzt, und einen, dass die neu geweitete Ausgabe **nicht** in einen unbeteiligten Konsumenten durchschlägt.

- **`detect_objects` (Unit, `test_classification.py`):** liefert jetzt auch Nicht-Tier-Klassen (`car`, `pizza`, `laptop`) zurück — der bestehende Fall „Nicht-Tier-Kategorie wird herausgefiltert" wird **umgestellt, nicht gelöscht**, und kehrt seine Erwartung um. Erhalten bleibt: die Konfidenzschwelle (`ANIMAL_DETECTION_CONFIDENCE_THRESHOLD`, ggf. umbenannt) wirkt weiterhin und gilt jetzt für *alle* Klassen (Grenzfall exakt auf der Schwelle inklusiv, knapp darunter verworfen); nur die höchstbewertete Kategorie pro Erkennung zählt; leere `categories`-Liste und leeres Detektor-Ergebnis bleiben `[]`; Bounding-Box-Normierung unverändert.
- **`compute_tier_score` (Unit, `test_criteria.py`):** bekommt jetzt die *ungefilterte* Objektliste und muss selbst auf `ANIMAL_CATEGORIES` filtern. Pflichtfälle: nur Nicht-Tiere in der Liste → `0.0` (nicht die Konfidenz des Autos!); gemischte Liste, in der das **flächengrößte** Objekt ein Nicht-Tier ist → der Score stammt vom flächengrößten *Tier*, nicht vom größten Objekt insgesamt; leere Liste → `0.0`. Der erste dieser Fälle ist der eigentliche Regressionsschutz dieser Spec-Änderung.
- **`compute_golden_ratio_score` / `animal_detections()` (Unit, `test_criteria.py`) — ausdrücklich testpflichtiger Verhaltenserhalt:** eine Objektliste mit genau *einem* Auto und *keinem* Tier, `faces=[]` → Score identisch zum Fall „gar keine Erkennungen" (kein Auto als Kompositions-Subjekt); eine Liste mit einem kleinen Tier und einem großflächigen Auto → das Tier ist Subjekt, das Auto beeinflusst die Auswahl nicht. `animal_detections()` bekommt zusätzlich einen eigenen kleinen Unit-Test (filtert auf `ANIMAL_CATEGORIES`, Reihenfolge bleibt erhalten), damit der Verhaltenserhalt an einer benannten Funktion hängt und nicht nur am Ergebnis.
- **`compute_fahrzeug_score` / `compute_essen_trinken_score` (Unit, `test_criteria.py`):** Muster wie `compute_gebaeude_score` — Allow-Listen-gefiltertes Konfidenz-Maximum; Pflichtfälle: Treffer, Nicht-Treffer → `0.0`, mehrere Treffer → Maximum, leere Liste → `0.0`, und je ein Fall für eine bewusst **nicht** in der Liste stehende Klasse (`cup`/`bottle`/`bowl` → `0.0` für `essen_trinken`) — das ist die einzige automatisierte Absicherung der in Schritt 2 begründeten Listen-Auswahl.
- **Verifikation der Label-Schreibweisen** gegen die im `.tflite` mitgelieferte Label-Datei ist Pflicht (wie bei `LANDSCAPE_SCENE_CATEGORIES`), aber **kein automatisierter Test** — die Modelldatei liegt im Repo, ein Test dagegen prüfte nur die Datei gegen sich selbst. Nachweis ist ein Kommentar mit dem Befund im Code, wie bei `LANDSCAPE_SCENE_CATEGORIES` bereits vorgemacht.

### 5 — Remote-Antwort: `_classification_from_json` (Unit, `test_remote_classification.py`)

Die bestehende `TestCategoryLabelsFromJson`-Klasse wird umgebaut, nicht ergänzt: die bisherige Konvention „Anzahl außerhalb 1–3 ist ein Fehler" **entfällt** zugunsten von „strukturell hart, inhaltlich tolerant". Diese Umkehr ist bewusst und im Review als solche zu prüfen.

**Verbindliche Verarbeitungsreihenfolge** (technische Detailentscheidung dieser Teststrategie, weil sie ohne Festlegung implementierungsabhängig und damit untestbar wäre): trimmen → leere/zu lange Werte verwerfen → unbekannte Kategoriewerte verwerfen → deduplizieren unter Erhalt der Erstnennungs-Reihenfolge → **zuletzt** auf `MAX_REMOTE_CATEGORIES_PER_PHOTO = 3` bzw. `MAX_FINE_LABELS_PER_PHOTO = 2` kürzen. Zuerst zu kürzen würde gültige Werte hinter ungültigen verlieren.

- **Strukturell hart:** fehlender `categories`-Schlüssel, `categories` kein Array, Antwort kein JSON-Objekt, `fine_labels` vorhanden aber kein Array → jeweils `RemoteCategoryClassificationApiError`; auf Worker-Ebene wird das Foto best-effort übersprungen (siehe Abschnitt 7).
- **Inhaltlich tolerant, je eigener Testfall:** unbekannter Kategoriewert wird verworfen **und** löst genau ein `WARNING` mit dem Rohwert aus (`caplog`-Muster aus ADR 0034, Roh-Payload nie im Log); fünf gültige Kategorien → die ersten drei; drei gültige plus zwei unbekannte in gemischter Reihenfolge → genau die drei gültigen (Nachweis der Reihenfolge oben); Duplikate (`["tier","tier","menschen"]`) → `("tier","menschen")`; drei Feinlabels → die ersten zwei; Feinlabel länger als `MAX_FINE_LABEL_LENGTH = 60` → **verworfen, nicht gekürzt** (ein auf 60 Zeichen abgeschnittenes Label erzeugte sonst dauerhaft einen unbrauchbaren `canonical_key` in der projektübergreifenden Registry); leeres/nur-Whitespace-Feinlabel → verworfen; fehlender `fine_labels`-Schlüssel → leeres Tupel, **kein** Fehler (Feinlabels sind optional, Kategorien nicht).
- **Der wichtigste Grenzfall, eigener benannter Test:** `categories` ist ein Array, aber **alle** Werte sind unbekannt → **kein** Fehler, sondern leeres Kategorien-Tupel, das über `resolve_category` zu `nicht_erkannt` wird; die Feinlabels desselben Fotos bleiben erhalten. Ohne diesen Test entscheidet der Zufall der Implementierung, ob das Foto übersprungen wird oder `nicht_erkannt` bekommt.
- **`COST_PER_IMAGE_USD`:** der bestehende Test („dokumentierter positiver Preis je Provider") bleibt; die Neuverifikation der Bandbreite wegen des gewachsenen Prompts ist eine Kommentar-/Herleitungspflicht, kein Testfall (siehe Abschnitt 11).
- Die HTTP-Client-Tests (`TestAnthropicCategoryClient`/`TestMistralCategoryClient`, `httpx.MockTransport`) bleiben strukturell unverändert; angepasst werden nur der geparste Antwort-Payload und die Assertion auf `RemoteClassification` statt `list[CategoryLabelDetection]`. Der bestehende Test „Fehlermeldung enthält nie API-Key oder Bildbytes" bleibt unangetastet gültig.

### 6 — Alembic-Migration (Unit, `test_migration_feste_kategorien.py`, neu)

Muster von `test_migration_remote_category_classification.py` übernehmen (Revision isoliert per `importlib` laden, Vor-Schema minimal in einer Datei-SQLite in `tmp_path` nachbauen, `upgrade()`/`downgrade()` über `Operations.context`). **Neu und für dieses Projekt erstmalig: die Revision enthält datenverändernde Schritte, nicht nur Schemaänderungen** — Schema-Assertions allein reichen hier nicht.

- **Schema (a)/(b):** `photo_category_classifications` existiert mit exakt dem erwarteten Spalten-Set; `category_labels`→`fine_labels` und `photo_category_detections`→`photo_fine_labels` umbenannt, Spalte `category_label_id`→`fine_label_id`, Constraint `uq_fine_label_photo_label` vorhanden, `confidence` in `photo_fine_labels` **weg**; die alten Tabellen-/Spaltennamen existieren nicht mehr.
- **Namens-Migration erhält Werte:** eine Zeile mit alten Spaltennamen vor der Migration einfügen, nach der Migration unter den neuen Namen dieselben Werte lesen (bestehendes Zwei-Revisionen-Muster) — gilt für die `fine_labels`-Registry-Zeile, die ausdrücklich **erhalten bleibt**.
- **Datenschritt (c), eigener Test:** vor der Migration je eine Zeile in `photo_fine_labels` **und** in `fine_labels` einfügen; danach ist `photo_fine_labels` leer, `fine_labels` aber unverändert vorhanden. Der zweite Teil ist der eigentliche Punkt — ein versehentliches `DELETE FROM fine_labels` würde die projektübergreifende Vokabular-Registry vernichten und fiele ohne diesen Test nicht auf.
- **Datenschritt (d), eigener Test:** zwei `photo_scores`-Zeilen einfügen, eine mit gesetztem `category_override`, eine mit `NULL`; nach der Migration sind beide `NULL`, und **alle übrigen Spalten beider Zeilen sind unverändert** (Nachweis, dass das `UPDATE` nicht mehr anfasst als eine Spalte).
- **Downgrade:** stellt das Schema wieder her (Tabellen/Spalten zurückbenannt, `photo_category_classifications` gelöscht) — und ein eigener, benannter Test hält fest, dass die in (c)/(d) gelöschten **Daten nicht zurückkehren**. Das ist keine Schwäche, sondern die von der Spec akzeptierte Einbahnstraße; sie gehört als Test festgehalten, damit niemand sie später für einen Bug hält.
- Nicht getestet: das Verhalten gegen echtes Postgres — das Projekt hat kein Postgres-Testsetup, die Migrationstests laufen wie alle bestehenden gegen SQLite.

### 7 — Worker (Integration, In-Memory-SQLite)

- **`run_remote_category_classification` (`test_worker_remote_category_classification.py`):** pro Foto genau **eine** `photo_category_classifications`-Zeile mit `category_key == resolve_category(remote_kandidaten)` und `detected_categories` = der *validierten* Liste (nicht der Rohantwort); 0–2 `photo_fine_labels`-Zeilen über `resolve_canonical_label`; **Feinlabels werden auch bei `category_key == "nicht_erkannt"` geschrieben** (eigener, benannter Testfall — direktes Akzeptanzkriterium); ein Foto mit strukturell ungültiger Antwort wird übersprungen, ohne den Lauf zu beenden, die übrigen Fotos werden weiterverarbeitet (Best-effort, bestehendes Muster); ein zweiter Lauf über dasselbe Foto erzeugt keine zweite Klassifikations-Zeile (1:1-Constraint).
- **`select_remote_category_candidates`:** ein Foto mit vorhandener Klassifikations-Zeile wird übersprungen, eines ohne nicht — mit Aufrufzähler auf dem Fake-Client, nicht nur über das Endergebnis erschlossen (Kostenrelevanz, Pflichtmuster nach ADR 0047 Punkt 2).
- **`run_criterion_scoring` (`test_worker_criterion_scoring.py`):**
  - Der bestehende Ein-Aufruf-Spy-Test (`detect_person`/`detect_objects` je höchstens einmal pro Foto) bleibt **verbindlich** und wird nur auf den neuen Funktionsnamen umgestellt — der COCO-Detektor läuft weiterhin genau einmal, obwohl jetzt drei Kriterien (`tier`, `fahrzeug`, `essen_trinken`) plus `goldener_schnitt` an seiner Ausgabe hängen.
  - **Fehlerfall-Tests in beide Richtungen** (Verschärfung aus ADR 0047 Punkt 3, jetzt mit drei Konsumenten): scheitert die Score-Berechnung eines der drei Objekt-Kriterien, werden die anderen beiden trotzdem geschrieben; scheitert `detect_objects` selbst, fehlen alle drei plus `goldener_schnitt`, während `gebaeude`/`landschaft`/`content_people` weiterhin geschrieben werden und der Lauf regulär endet.
  - **Vereinigung lokal ∪ remote:** ein Foto mit lokalem Signal `tier` und remote `menschen` → `menschen` (kleinere `precedence`); dasselbe Foto ohne Klassifikations-Zeile → `tier`. Das ist der Nachweis für „ein gemeinsames Set, keine zwei Kategoriewelten".
  - **Herkunftsneutralität:** dieselbe Kandidatenmenge, einmal rein lokal, einmal rein remote erzeugt, führt zur selben Kategorie — expliziter Testfall zum Akzeptanzkriterium.
  - **Override bleibt vorrangig:** ein gesetztes `category_override` überlebt den Lauf, auch wenn die abgeleitete Kategorie eine andere wäre (Bestandstest, nur Werte umgestellt).
  - **Projekt ohne Remote-Lauf:** ein Lauf ohne Klassifikations-Zeilen vergibt ausschließlich Keys aus der lokal bestimmbaren Sechser-Teilmenge oder `nicht_erkannt` — als Assertion über *alle* geschriebenen `PhotoRanking.category_key` eines Laufs, nicht über ein einzelnes Foto.
  - **Kein Kategoriewert außerhalb des Sets:** ein lauf-weiter Test, der alle geschriebenen `category_key`-Werte gegen `is_known_category` prüft — die kompakteste Absicherung des Kernakzeptanzkriteriums.
  - **Leerer Kandidatenpool** (0 Fotos nach Ausschuss-Filter): kein Crash, Lauf endet regulär (Bestandsfall, mitzuführen).
- **`_merge_remote_category_labels` ist gelöscht:** die zugehörigen Bestandstests werden gelöscht, nicht auskommentiert; die Fälle, die dabei *Verhalten* absicherten (Kandidaten-Vereinigung), sind durch die neuen Vereinigungstests oben ersetzt — im Review explizit gegeneinander abgleichen, damit kein Fall ersatzlos verschwindet.

### 8 — API (Integration, `httpx.ASGITransport` + In-Memory-SQLite)

- **`GET /categories` (`test_api_categories.py`, neu):** ohne Token `401` (Router-Level-Auth, bestehendes Muster aus `test_api_auth.py`); mit Token genau 13 Einträge in Registry-Reihenfolge mit `key`/`display_name`/`definition`/`locally_available`; `locally_available` ist genau für die sechs lokalen Keys `true` und wird **aus `LOCAL_CATEGORY_SIGNALS` abgeleitet**, nicht literal gepflegt (ein Test, der beides gegeneinander prüft).
- **`PUT /photos/{id}/category-override` (`test_api_category_override.py`) — Verhaltensumkehr, ausdrücklich:** die beiden Bestandstests `test_returns_409_for_a_category_key_that_is_not_a_candidate_for_this_photo` und `test_returns_409_for_a_canonical_key_detected_on_a_different_photo` beschreiben Verhalten, das diese Spec **abschafft**. Sie werden in positive Fälle umgeschrieben (Set-Key, der für dieses Foto kein Kandidat ist → `200`, Kategorie wird gesetzt), nicht gelöscht — sonst bliebe die Aufhebung der Kandidaten-Bindung untestiert, und eine Implementierung, die die alte Prüfung stehen lässt, fiele nicht auf. Weiterhin: `422` für einen Key außerhalb des Sets (inkl. Altwert `"unerkannt"` als benannter Fall), `409` ohne `PhotoRanking`-Zeile im aktuellen Lauf, `404` für unbekanntes Foto, `401` ohne Token, `nicht_erkannt` ist ein gültiger Override-Wert.
- **`DELETE /photos/{id}/category-override`:** die Rekonstruktion nutzt dieselbe neue Ableitung — Bestandstest „stellt die automatisch abgeleitete Kategorie wieder her" auf Set-Keys umstellen; `test_reset_without_any_recognised_content_falls_back_to_unrecognized` wird zum `nicht_erkannt`-Fall; die Idempotenz-Fälle bleiben.
- **`GET /photos` / `GET /photos/{id}` (`test_api_photos.py`):** `fine_labels` ersetzt `remote_category_labels` (Feld-Umbenennung inkl. Wegfall von `confidence`); `remote_category` ist bei vorhandener Klassifikations-Zeile deren `category_key`, sonst `null`; `category_candidates` enthält nur noch Set-Keys mit `origin` und **kein** `score`-Feld (negative Assertion auf die Schlüsselmenge, nicht nur auf die Werte); ein Foto ohne Feinlabels liefert eine leere Liste, nicht `null`; `_cloud_vision_status_out` leitet den Remote-Erfolg aus der Klassifikations-Zeile ab (Foto mit Zeile → Erfolg, ohne → weiterhin ausstehend/Fehler, Bestands-Fehlerfälle aus ADR 0035 unverändert grün).
- **`GET /projects/{id}/fine-labels` (`test_api_projects.py`):** absteigend nach `photo_count`, Tie-Break `canonical_key` aufsteigend — mit einem Datensatz, der **beide** Sortierstufen ausübt (mindestens zwei Labels mit identischem `photo_count`); leeres Projekt → leere Liste, `200` statt `404`; Feinlabels aus einem anderen Projekt tauchen nicht auf (die Registry ist projektübergreifend, die Zählung nicht — eigener, benannter Test); `401` ohne Token; unbekanntes Projekt → `404`.

### 9 — Frontend (`vitest` + Testing Library)

Neues, hier erstmals auftretendes Muster: **die Anzeigetabelle kommt zur Laufzeit vom Server.** Damit die Anzeigehelfer unit-testbar bleiben, sind `formatCategoryKey`, `categoryAbbreviation` und `sortCategoryKeys` als **reine Funktionen mit dem geladenen Set als explizitem Parameter** zu schreiben (keine modul-globale, vom Query-Cache befüllte Variable) — sonst wären sie nur noch mit `QueryClientProvider` testbar und ihre Tests hingen von Query-Zustand ab. Diese Trennung ist Testvorgabe, nicht Stilfrage.

- **`utils/categoryLabels.test.ts` (Unit):** `formatCategoryKey` liefert den Anzeigenamen aus dem übergebenen Set; für einen Altwert aus der Laufhistorie (`"unerkannt"`, `"detail"`) greift der generische Fallback; leerer String bleibt leer; der bestehende `Object.hasOwn`-Prototype-Regressionstest (`"toString"`, `"constructor"`) wird **auf die neue Signatur umgestellt, nicht gelöscht**. `categoryAbbreviation` bildet drei Großbuchstaben aus dem *Anzeigenamen* (`Menschen`→`MEN`, `Nicht erkannt`→`NIC`, `Gebäude & Bauwerk`→`GEB`) und ist über das gesamte Set **kollisionsfrei** — als parametrisierter Test über alle 13 Anzeigenamen, nicht als Stichprobe.
- **`sortCategoryKeys` (Unit, `CurateCategoriesPage`):** Registry-Reihenfolge statt alphabetisch; `nicht_erkannt` immer zuletzt; unbekannte Altwerte danach, aber vor `nicht_erkannt`; stabile, deterministische Reihenfolge bei mehreren Altwerten (Tie-Break benennen und testen, sonst hängt die Anzeige von der `Object.keys`-Reihenfolge ab).
- **`useCategories` (Hook-Test):** lädt einmal und cacht; ein zweiter Konsument löst keinen zweiten Request aus (`vi.mock` auf Modulebene von `api/categories.ts`, Aufrufzähler) — das ist der Nachweis für „langlebiger Cache" aus dem UI/UX-Abschnitt.
- **`CriterionDetailsList.test.tsx`:** die Override-Auswahl bietet alle 13 Einträge an (nicht nur die Kandidaten); die Kandidatenliste bleibt daneben sichtbar; eine Auswahl löst den Mutations-Callback mit dem richtigen Key aus; `nicht_erkannt` ist wählbar und trägt den Erklärtext; Feinlabel-Chips werden gerendert, auch wenn die Kategorie `nicht_erkannt` ist; ohne Feinlabels wird **kein** Platzhalter gerendert (`queryBy…` → `null`). Alle Selektoren über `getByRole`/`getByLabelText`, nie über Klassennamen (bestehende Konvention).
- **Ladezustände:** Auswahl während des Ladens deaktiviert; Fehlerfall zeigt den Inline-Alert mit „Erneut versuchen"-Schaltfläche, deren Klick einen erneuten Request auslöst.
- **`RemoteCategoryClassificationSection.test.tsx`:** Feinlabel-Häufigkeitsliste in gelieferter Reihenfolge, Begrenzung auf die häufigsten Einträge, Leerzustand („Keine zusätzlichen Label ermittelt"), Lade- und Fehlerzustand.
- **`CategoryBadge.test.tsx` / `CurateCategoriesPage.test.tsx`:** deutsche Anzeigenamen, `title`/`aria-label` mit dem vollständigen Namen bei abgekürztem Badge, `nicht_erkannt` ohne Fehler-Styling (über semantische Rolle/`data-*`-Attribute, nicht über Klassennamen).
- **Repo-weite Fundstellensuche vor der Umsetzung** (Regel aus ADR 0047 Punkt 5, hier mehrfach einschlägig): `grep -rn` über `backend/src`, `backend/tests`, `frontend/src` nach `unerkannt`, `remote_category_labels`, `category_labels`, `photo_category_detections`, `category_specificity` — die alten Keys/Feldnamen stecken als String-Literale in Tests und Fixtures und fallen weder durch `tsc` noch durch `mypy` auf.

### 10 — Edge Cases, die sonst durchrutschen

1. Remote-Antwort mit ausschließlich unbekannten Kategoriewerten → `nicht_erkannt`, Feinlabels bleiben (siehe 5).
2. Remote liefert `nicht_erkannt` **zusammen mit** einer echten Kategorie → echte Kategorie gewinnt.
3. Remote liefert Duplikate → Deduplizierung vor der Kürzung, sonst verdrängt ein Duplikat einen gültigen dritten Kandidaten.
4. Kandidat nur `gegenstand` → `gegenstand`, nie `nicht_erkannt`.
5. `sport_aktivitaet` + `menschen` → `sport_aktivitaet` (die einzige kontraintuitive Regel des Sets).
6. Nicht-Tier-Objekt als flächengrößte Erkennung → weder Tier-Score noch Kompositions-Subjekt.
7. `photo_scores`-Zeilen ohne `category_override` überstehen die Migration unverändert (das `UPDATE` darf keine Nebenwirkung auf andere Spalten haben).
8. `fine_labels`-Registry überlebt die Migration, `photo_fine_labels` nicht.
9. Override auf einen Set-Key, den dieses Foto nie als Kandidat hatte → jetzt erlaubt (Umkehr des Bestandsverhaltens).
10. Override auf einen Altwert aus der Laufhistorie (`"unerkannt"`) → `422`, nicht stillschweigend akzeptiert.
11. Foto mit Klassifikations-Zeile, aber ohne `PhotoRanking`-Zeile → Override weiterhin `409`.
12. Frontend zeigt Altwerte aus der Laufhistorie (vor dem ersten neuen `score-criteria`-Lauf) über den generischen Fallback an, ohne Absturz und ohne leeres Badge.
13. Zwei Feinlabels mit identischem `photo_count` → deterministische Sortierung.
14. Projekt ohne aktivierte Remote-Kategorisierung → nur die sechs lokalen Keys plus `nicht_erkannt`, nie einer der übrigen sechs.
15. `landmark` bleibt als Kriterium kategorie-fähig, bildet aber **keine** Kategorie mehr — der erkannte Name bleibt am Foto sichtbar (Regressionstest, sonst verschwindet er unbemerkt mit dem `LOCAL_CATEGORY_SIGNALS`-Umbau).

### 11 — Bewusst nicht automatisiert abgesichert

- **Inhaltliche Erkennungsgüte des Zwölfer-Sets** (trifft das Modell die richtige Kategorie? ist die Negativabgrenzung für das Modell trennscharf genug?) — kein Ground-Truth-Fotokorpus im Repo, und einer ist auch nicht anlegbar: `CLAUDE.md` verbietet Bilddaten der Familie im Repository. Identisches, bereits etabliertes Muster wie bei `landmark`/`LANDSCAPE_SCENE_CATEGORIES`/`CATEGORY_LABEL_SIMILARITY_THRESHOLD`. Ersatzverfahren: manueller Stichproben-Review durch Daniel nach dem ersten produktiven Remote-Lauf, mit besonderem Blick auf die zwei schwierigsten Abgrenzungen der Spec (Weitwinkel-Vegetation → `landschaft` vs. Nahaufnahme → `pflanze`; `gegenstand` vs. `nicht_erkannt`). Als bekannte Lücke im Testkonzept vermerkt.
- **`COST_PER_IMAGE_USD` nach dem Prompt-Wachstum** — die Neuverifikation ist eine Herleitungs-/Kommentarpflicht, kein Testfall (bestehende Lücke, hier nur größer geworden: der Prompt wächst um grob 500–700 Input-Tokens).
- **Migrationsverhalten gegen echtes Postgres** — kein Postgres-Testsetup im Projekt.
- **Reine UI-Kosmetik** (Badge-Töne, Abstände, 44×44px-Tap-Ziele) — Design-System-Konformität ist Review-Aufgabe (`review-ux`), nicht automatisiert testbar.

### 12 — Coverage-Gate und `mypy --strict`

Das Backend-Gate (`--cov-fail-under=80`) ist durch diese Spec nicht gefährdet, aber zwei Stellen brauchen Aufmerksamkeit: (a) `categories.py` ist überwiegend Daten — die Registry zählt als abgedeckt, sobald sie importiert wird, das darf nicht mit „getestet" verwechselt werden (deshalb die expliziten Invariantentests oben statt Verlass auf die Coverage-Zahl); (b) mit `derive_active_categories`/`derive_category_key`/`_specificity_of`/`_merge_remote_category_labels` verschwinden gut abgedeckte Zeilen **samt** ihren Tests — der Gate-Wert bleibt dadurch etwa neutral, kaschiert aber, wenn neue Zweige (Remote-Toleranzpfade, Fehlerfälle im Worker) ungetestet blieben. Der Nachweis läuft deshalb über die oben benannten Pflichtfälle, nicht über die Coverage-Zahl. `mypy --strict` betrifft vor allem `resolve_category` (Signatur über `Iterable[str]`/`Collection[str]` statt `set[str]`, damit Aufrufer keine unnötige Konvertierung brauchen) und `RemoteClassification` mit `tuple[str, ...]`-Feldern — beides in den Unit-Tests mit verschiedenen Eingabetypen ausgeübt, damit die Signatur nicht nur formal weit, sondern auch tatsächlich benutzt ist.

### Auswirkung auf das Testkonzept

`specs/architecture/0002-testkonzept.md` **wird ergänzt** (im Rahmen dieser Konsultation bereits erfolgt): neue Backend-Sektion zu (1) Alembic-Revisionen mit datenverändernden Schritten, (2) geschlossener Produkt-Taxonomie mit Vorrang-Totalordnung inkl. der Regel „ein bewusst redundanter literaler Set-Test", (3) generierten LLM-Prompts (Struktur- statt Wortlauttest), (4) dem Entfernen eines Allow-Listen-Filters aus einer geteilten Erkennungsfunktion als Gegenrichtung zu ADR 0047 Punkt 1, (5) der Reihenfolge-Festlegung bei „strukturell hart, inhaltlich tolerant"; neue Frontend-Untersektion zu server-gelieferten Anzeigetabellen; zwei neue Einträge unter „Bekannte Lücken".

## Security

**Einordnung: sicherheitsrelevant, kein Blocker.** Das Feature verschärft an einer Stelle (Override-Validierung) und erweitert an drei Stellen die Angriffsfläche: zwei neue Endpunkte, erstmalige *Anzeige* von freiem, extern erzeugtem LLM-Text in der Oberfläche, und ein deutlich größerer Klassifizierungs-Prompt. Keine neuen Secrets, keine neue Umgebungsvariable, kein zusätzlicher Datenfluss Richtung Cloud.

### 1. Neue Endpunkte — Auth-Durchsetzung und Projekt-Skopierung

- **`GET /categories`** (neuer Router `api/categories.py`): auth-pflichtig über `dependencies=[Depends(get_current_user)]` **am Router**, nicht pro Endpunkt (Muster `api/projects.py`/`api/opencloud.py`; die Abweichung in `api/photos.py` existiert nur, weil dort jeder Endpunkt das `User`-Objekt selbst braucht — hier nicht der Fall). Der Router muss in `main.py` eingehängt **und** der Auth-Zwang testseitig belegt sein (401 ohne Token), nicht nur behauptet. Inhaltlich exponiert der Endpunkt ausschließlich statische Registry-Daten (keine Foto-, Projekt- oder Nutzerdaten) — er ist kein Informationsleck, bleibt aber bewusst hinter Auth, damit die Linie „jeder Endpunkt ist auth-pflichtig, einzige Ausnahme `POST /auth/login`" ohne Sonderfall bestehen bleibt.
- **`GET /projects/{id}/fine-labels`**: hängt am bereits router-weiten Torwächter in `api/projects.py`, kein zusätzlicher `Depends`. **Muss-Kriterium — Projekt-Skopierung:** `fine_labels` ist bewusst eine *projektübergreifende* Vokabular-Registry (Docstring `models.py::CategoryLabel`, ADR 0032). Die Häufigkeitsabfrage muss deshalb zwingend über `photo_fine_labels → photos.project_id == id` joinen und zählen; ein globales `SELECT ... FROM fine_labels` würde Label-Häufigkeiten *anderer* Projekte ausliefern. Vokabular-Einträge ohne Foto im angefragten Projekt dürfen nicht in der Antwort erscheinen (über den Join implizit `photo_count > 0`).
- **Keine Objekt-ID-Enumeration:** eine nicht existierende `project_id` läuft über die bestehende `_get_project_or_404`-Hilfsfunktion in ein 404, nicht in ein leeres `200`. Ein Berechtigungsvergleich „gehört dieses Projekt dem aufrufenden Nutzer" ist bewusst **nicht** zu implementieren: das Auth-Modell ([`decisions/0003-auth-model.md`](../decisions/0003-auth-model.md)) kennt kein Rollen-/Eigentümermodell, beide Nutzer sehen dieselben Projekte (kein Innentäter-Modell, siehe Sicherheitskonzept). Ein hier neu erfundener Ownership-Check wäre eine stillschweigende Änderung des Auth-Modells.

### 2. Override-Validierung: Verschärfung, die ein bestehendes Muss-Kriterium ablöst

`PUT /photos/{id}/category-override` validiert `category_key` künftig gegen `is_known_category` (13 feste Werte) statt gegen `_photo_category_candidate_keys`. Das ist gegenüber heute **strikt stärker** (geschlossene 13er-Menge statt „irgendein für dieses Foto persistierter `canonical_key`"), löst aber ein wörtlich festgehaltenes Muss-Kriterium aus Spec 0055/ADR 0032 Punkt 6.3 ab („Injection-Freiheit beruht auf der foto-skopierten Existenzprüfung", „Cross-Photo-Isolation, kein IDOR"). Muss-Kriterien:

- Beim Löschen von `_photo_category_candidate_keys` sind die Docstrings/Kommentare, die sich auf diese Prüfung als Sicherheitsgarantie berufen, mit zu entfernen bzw. auf die neue Begründung umzuschreiben (`api/photos.py::CategoryOverrideIn`, `_category_candidates_out`, `set_category_override`). Eine stehen bleibende Beschreibung einer nicht mehr existierenden Garantie ist ein Wartungs- und Review-Risiko.
- Reine Whitelist-Prüfung gegen `CATEGORY_REGISTRY` (Mitgliedschaftsprüfung auf `key`) — kein Präfix-/Regex-/`startswith`-Vergleich, keine Normalisierung des Eingabewerts vor der Prüfung (kein `strip()`/`casefold()`: der Client schickt den Key exakt so zurück, wie `GET /categories` ihn geliefert hat). `422` bei unbekanntem Wert; der bestehende `409` ohne `PhotoRanking`-Zeile bleibt unverändert.
- Die Prüfung greift **vor jeder Schreibaktion** (vor `reassign_photo_category` und vor dem Setzen von `score.category_override`), nicht erst beim Bauen der Antwort.
- **Lesepfad bleibt tolerant (Defense in Depth):** ein `category_override`-Altwert außerhalb des Sets darf im Lesepfad (`PhotoOut`, Kuratierung, `formatCategoryKey`) keinen 500er/Absturz erzeugen, sondern wird als unbekannter Altwert dargestellt (Frontend-Fallback ist im UI/UX-Abschnitt bereits vorgesehen). Grund: der Schreibpfad ist ab dieser Spec geschlossen, der Datenbestand erst nach Migrationsschritt (d) — die Toleranz fängt einen vergessenen oder teilweise fehlgeschlagenen Migrationslauf ab.

### 3. Freie Feinlabels aus fremder Quelle — erstmals gerenderter LLM-Freitext

`FineLabel.display_name`/`PhotoFineLabel.raw_label` sind ungefilterter, vom externen Vision-LLM formulierter Text. Dieser Text wurde zwar bereits bisher gespeichert und über `PhotoOut.remote_category_labels` ausgeliefert, aber **von keiner Frontend-Komponente gerendert** — sichtbar war ausschließlich der `_slugify`-Ausgabe-Zeichenraum `[a-z0-9_]` (so auch im Sicherheitskonzept festgehalten). Mit dieser Spec erscheinen Feinlabels als Chips am Foto und in der Häufigkeitsliste: **die erste Stelle, an der freier Fremdtext tatsächlich in der Oberfläche landet.** Muss-Kriterien:

- **Rendering ausschließlich als regulärer React-Textknoten** — nie `dangerouslySetInnerHTML`, nie als HTML-String-Prop einer Radix-/shadcn-Komponente, nie in `href`/`src`/`style`. `title`/`aria-label` als Attribut ist zulässig (React escaped auch dort). Das ist keine bloße Konvention, sondern die tragende Voraussetzung der `localStorage`-Token-Entscheidung (ADR 0005). Ein Test analog `CloudVisionStatusList.test.tsx` („never renders … via dangerouslySetInnerHTML") gehört dazu.
- **Zeichensanitisierung beim Übernehmen der Modellantwort** (`remote_classification.py`, vor `resolve_canonical_label`): Unicode-Steuer- und Formatzeichen (Kategorien `Cc`/`Cf` — insbesondere Zeilenumbrüche, `\x00`, Zero-Width- und Bidi-Override-Zeichen wie `U+202E`) werden entfernt, Whitespace-Folgen zu einem einzelnen Leerzeichen zusammengezogen. Ein danach leeres Label wird verworfen (toleranter Pfad, kein Fehler). Begründung: escapetes Rendering schützt gegen XSS, aber weder gegen optische Verfälschung der UI durch Bidi-/Zero-Width-Zeichen noch gegen mehrzeilige Logeinträge (siehe Punkt 4).
- `MAX_FINE_LABEL_LENGTH = 60` und `MAX_FINE_LABELS_PER_PHOTO = 2` sind **Degenerations-/Storage-Grenzen, keine Sanitisierungsmaßnahme** (dieselbe Einordnung wie die 500-Zeichen-Kappung aus Spec 0058). Sie greifen **vor** `resolve_canonical_label`/`_slugify`, damit kein entarteter Rohwert in die projektübergreifende Registry gelangt. Ein zu langes Label wird **verworfen, nicht abgeschnitten** (bestehendes Verhalten von `_category_labels_from_json` beibehalten — ein Abschneiden würde zwei verschiedene Labels auf denselben Slug abbilden).
- Der `_slugify`-Hash-Fallback für rein nicht-lateinische Labels bleibt erhalten: er ist ein Verfügbarkeitsschutz gegen einen `UniqueConstraint`-Bruch, der sonst den ganzen Lauf abbräche statt nur ein Foto zu überspringen.

### 4. Logging der Rohwerte unbekannter Kategorien

`_classification_from_json` verwirft unbekannte Kategoriewerte und loggt sie auf `WARNING` inklusive Rohwert (ADR-0034-Muster). Muss-Kriterien:

- Der Rohwert wird **über `%r` (repr) und längenbegrenzt** geloggt, nie roh über `%s`. Sonst kann ein mehrzeiliger Modellwert gefälschte Logzeilen erzeugen (Log-Injection); `repr` escaped Zeilenumbrüche und Steuerzeichen sichtbar. (Die Sanitisierung aus Punkt 3 greift für Feinlabels; ein verworfener Kategoriewert wird dagegen gerade *nicht* weiterverarbeitet — hier ist `repr` die Absicherung.)
- Geloggt wird ausschließlich der einzelne verworfene Wert plus `photo_id` — **nie die vollständige API-Antwort**, nie der Request-Body, nie Base64-Bilddaten, nie der API-Key. Das bestehende Muss-Kriterium aus ADR 0025/0031/0032/0034 gilt unverändert; `cloud_vision.py::raise_for_vision_api_status`/`*_response_to_json` bleiben die einzige Sanitisierungsstelle für Fehlermeldungen.
- Format analog `worker.py::_log_cloud_vision_failure` (eine Zeile, kein `exc_info`/Traceback); Level `WARNING` passt zur bestehenden ADR-0034-Linie (erwartetes Best-effort-Verhalten, der Lauf bleibt `SUCCESS`).
- Kein Log-Flooding möglich: pro Foto können höchstens `MAX_REMOTE_CATEGORIES_PER_PHOTO` Werte verworfen werden.

### 5. Prompt-Injection über Bildinhalte

Das Bild ist die eigentliche Eingabe der externen Klassifizierung — und mit `Dokument & Screenshot` nimmt das Set **ausdrücklich** Fotos von Texten, Bildschirmen, Schildern und Formularen in den Fokus. Bildinhalt, der Anweisungstext enthält, ist damit kein Randfall mehr, sondern eine erwartete Eingabeklasse. Das realistische Angriffsszenario bleibt bei einem privaten Familienarchiv gering (die Fotos stammen aus Daniels eigener OpenCloud, es gibt keinen fremden Uploadpfad), der Blast-Radius wird aber strukturell klein gehalten:

- **Der Code entscheidet, nicht das Modell** (Entwurfsentscheidung 4): `resolve_category` verwirft unbekannte Werte und bildet das Ergebnis ausschließlich aus `CATEGORY_REGISTRY` plus fester Vorrangreihenfolge. Eine gesteuerte Modellantwort kann damit höchstens eine *falsche, aber gültige* Kategorie erzwingen — keinen Wert außerhalb des Sets, keine Code-/Query-Injection.
- **Muss-Kriterium:** In `photo_category_classifications.detected_categories` (JSON, wird über `PhotoOut.category_candidates` ausgeliefert) werden **nur bereits validierte Set-Keys** persistiert, nie die Rohliste des Modells — sonst wandert unvalidierter Fremdtext über einen zweiten Kanal in API-Antwort und UI.
- **Muss-Kriterium:** Feinlabels steuern keinen Kontrollfluss. Sie fließen weder in die Kategorieableitung noch in Sortier-/Filterlogik noch in einen späteren Prompt ein; ihre einzige Weiterverarbeitung sind `resolve_canonical_label` (Embedding-Vergleich) und die Anzeige.
- **Muss-Kriterium:** `build_classification_prompt()` erzeugt den Prompt ausschließlich aus `CATEGORY_REGISTRY` — nie aus Datenbankinhalten, nie aus vorherigen Modellantworten. Es darf keinen Rückkopplungspfad geben, über den eine Antwort den nächsten Prompt beeinflusst (relevant, weil das Akzeptanzkriterium „Wiederkehrende Feinlabels sind auswertbar" den Gedanken nahelegt, häufige Feinlabels später automatisch in den Prompt aufzunehmen — das wäre eine neue Angriffsfläche und ist hier ausdrücklich nicht Teil der Umsetzung).
- **Muss-Kriterium (strukturelle Härte bleibt):** fehlendes/nicht-listenförmiges `categories`, ungültiges JSON oder eine durch `_MAX_RESPONSE_TOKENS = 256` abgeschnittene Antwort führen auf den bestehenden `RemoteCategoryClassificationApiError`-Pfad (Foto best-effort übersprungen), nie auf einen teilweise geparsten Datensatz. Der größere Prompt wächst nur auf der Eingabeseite; dass 256 Ausgabe-Tokens für 3 Kategorien + 2 Feinlabels weiterhin reichen, ist bei der Implementierung an einer echten Antwort zu verifizieren, nicht anzunehmen.

### 6. Datenexposition Richtung Cloud — Regressionsschutz beim Umbau

`remote_classification.py` wird substanziell umgebaut; die bestehende Expositionsgrenze darf dabei nicht verloren gehen (**Muss-Kriterium, per Test abzusichern**): versendet wird weiterhin ausschließlich die auf 2048 px begrenzte `display`-Cache-Variante, nie das OpenCloud-Original, kein EXIF/GPS, kein Dateiname und kein Pfad im Request. `Project.cloud_vision_detection_enabled` bleibt die einzige Freigabe; diese Spec führt weder einen zusätzlichen Cloud-Aufruf noch einen zweiten Datenfluss ein.

### 7. Migration — der Pflichtschritt ist eine Sicherheitsbedingung, kein Aufräumen

Schritt (d) `UPDATE photo_scores SET category_override = NULL` ist die einzige Stelle, die verhindert, dass Altwerte außerhalb des Sets die neue Validierung dauerhaft umgehen (der Override hat im Lesepfad Vorrang vor `resolve_category`). Er ist deshalb als Pflichtschritt zu behandeln und testseitig zu belegen, nicht als optionales Aufräumen. Beide destruktiven Schritte ((c) und (d)) liegen in derselben Alembic-Revision und laufen damit in einer Transaktion; `downgrade()` kann die gelöschten Daten nicht rekonstruieren und muss das im Docstring ausdrücklich festhalten, statt einen Rollback zu suggerieren. Der Datenverlust selbst ist durch „keine erhaltenswerten Bestände" (Out of Scope) gedeckt und gehört laut Spec in die PR-Beschreibung.

### 8. Kosten und informierte Einwilligung

Der aus der Registry erzeugte Prompt wächst um grob 500–700 Input-Tokens pro Bild. `COST_PER_IMAGE_USD` speist die Kostenschätzung, auf deren Basis Daniel den kostenpflichtigen Lauf freigibt — eine veraltete Konstante untergräbt genau diese informierte Entscheidung. Deshalb: `COST_PER_IMAGE_USD` gegen die **zum Implementierungszeitpunkt aktuelle** Preisliste des jeweiligen Anbieters neu herleiten (Herleitung als Kommentar fortschreiben, Pflicht bereits aus ADR 0032 Punkt 8), nicht den alten Wert fortschreiben. Das bestehende, akzeptierte Restrisiko „ein gestohlenes JWT kann einen kostenpflichtigen Remote-Lauf auslösen" steigt dadurch geringfügig in der Schadenshöhe pro Missbrauchsfall, nicht in der Eintrittswahrscheinlichkeit — weiterhin kein Blocker, kein Kosten-Cap in dieser Spec.

### 9. Ausdrücklich nicht sicherheitsrelevant

Keine neuen Secrets, keine neue Umgebungsvariable, kein neuer externer Dienst, keine Änderung an Auth-Modell, CORS oder Docker-Compose-Exposition. Die Umbenennungen (`CategoryLabel` → `FineLabel`, `PhotoCategoryDetection` → `PhotoFineLabel`), der Wegfall der Konfidenzen und die Frontend-Sortier-/Kürzel-Änderungen sind reine Struktur-/Darstellungsänderungen ohne Sicherheitsbezug.

### Sicherheitskonzept

[`specs/architecture/0003-securitykonzept.md`](../architecture/0003-securitykonzept.md) wurde im Rahmen dieser Spec ergänzt: neuer Abschnitt „Geschlossenes Kategorien-Set + freie LLM-Feinlabels in der Oberfläche" unter „Angriffsflächen" (Ablösung des `_photo_category_candidate_keys`-Muss-Kriteriums, erstmalige Anzeige von LLM-Freitext, Log-Injection, Prompt-Injection über Dokument-/Screenshot-Fotos, Projekt-Skopierung der Feinlabel-Häufigkeiten) sowie eine Präzisierung am `localStorage`-Token-Bullet im Frontend-Abschnitt.

### Offener Punkt (dokumentiert statt live gefragt)

In dieser Konsultation stand kein `AskUserQuestion`-Werkzeug zur Verfügung; die einzige Frage mit Stakeholder-Bezug ist deshalb hier festgehalten. Das Sicherheitskonzept verlangt beim `localStorage`-Token-Restrisiko, dass jede Änderung an der Voraussetzung „es gibt keinen nutzergenerierten HTML-Inhalt" erneut mit Daniel bewertet wird. **Bewertung dieser Konsultation: Die Voraussetzung bleibt gewahrt** — Feinlabels sind escapeter *Text*, kein HTML, und werden zusätzlich zeichensaniert (Punkt 3); daraus entsteht kein Blocker und keine Neubewertung von ADR 0005. Offen bleibt allein die Produktseite: Ist es für Daniel akzeptabel, dass frei formulierter, prinzipiell über Bildinhalte (Screenshots/Dokumente) beeinflussbarer Fremdtext dauerhaft in der Oberfläche und in der projektübergreifenden Vokabular-Registry sichtbar ist? Falls nein, wäre die naheliegende Verschärfung eine Zeichen-**Whitelist** (Unicode-Buchstaben/Ziffern/Leerzeichen/Bindestrich) statt der hier vorgesehenen Steuerzeichen-Blacklist — eine kleine, an genau einer Stelle nachrüstbare Änderung, die keine Spec-Struktur berührt.

## Entscheidungen

**Konsultationen im spec-writer-Ablauf:** Alle vier Fachrollen wurden konsultiert, keine Skip-Entscheidung — `architect` (Schritt 1, ADR 0049), `ux-ui-designer` (Schritt 2), `test-engineer` und `security-engineer` (Schritt 3).

**Fachliche und technische Festlegungen, die in diesem Ablauf getroffen wurden:**

1. **Feinlabel-Sanitisierung: Steuerzeichen-Blacklist, keine Zeichen-Whitelist.** Der `security-engineer` hat beides zur Wahl gestellt. Entschieden wurde die Blacklist (`Cc`/`Cf`, Bidi-, Zero-Width-Zeichen entfernen), weil Feinlabels freier deutscher Text sind: Eine Whitelist aus Buchstaben/Ziffern/Leerzeichen/Bindestrich würde legitime Labels beschädigen, während die Blacklist genau die Klasse optischer Verfälschung trifft, um die es geht. Nachrüstbar an genau einer Stelle, falls sich das als zu schwach erweist.
2. **Der Label-Embedder (ADR 0033) bleibt unangetastet.** Sein ursprünglicher Zweck — freie Labels über die Häufigkeitsschwelle zu heben — entfällt mit dieser Spec; er nützt jetzt nur noch der Feinlabel-Häufigkeitsauswertung, macht die aber deutlich belastbarer („Hund"/„Hunde"/„dog" als ein Eintrag). Weder Rückbau noch Ausbau in dieser Spec. Ein Rückbau (`onnxruntime`, `tokenizers`, 113-MiB-Modell) wäre ein spürbarer Vereinfachungsgewinn bei Docker-Build/CI/Setup und bleibt eine eigene, kleine ADR ohne Auswirkung auf das hier festgelegte Datenmodell.
3. **Die lokal bestimmbare Teilmenge umfasst sechs statt vier Kategorien.** `fahrzeug` und `essen_trinken` werden zusätzlich lokal ermittelt — aus der COCO-Detektorausgabe, die heute bereits berechnet und verworfen wird, also ohne zusätzliche Laufzeit- oder Cloud-Kosten. Ohne sie wären ohne Remote-Lauf nur vier der zwölf Kategorien erreichbar.
4. **Verarbeitungsreihenfolge der Remote-Antwort ist festgelegt:** trimmen → leere/zu lange verwerfen → unbekannte verwerfen → deduplizieren (Erstnennung gewinnt) → **zuletzt** kürzen. Ohne diese Festlegung wäre der Fall „drei gültige plus zwei unbekannte Werte" implementierungsabhängig.
5. **Ein zu langes Feinlabel wird verworfen, nicht auf 60 Zeichen gekürzt.** Ein abgeschnittenes Label erzeugt sonst dauerhaft einen unbrauchbaren `canonical_key` in der projektübergreifenden Vokabular-Registry.
6. **Die Akzeptanzkriterien wurden auf Testbarkeit geschärft**, ohne fachliche Änderung. Ausdrücklich ergänzt wurde die zuvor implizite Abgrenzung, dass die Laufhistorie (`PhotoRanking`) nicht migriert wird und dort Altwerte außerhalb des Sets stehen bleiben.
7. **Die manuelle Übersteuerung wird bewusst freizügiger:** Bisher waren nur erkannte Kandidaten wählbar (`409` sonst), künftig sind alle 13 Set-Einträge wählbar. Die frühere Beschränkung war eine Isolationsgarantie gegen fremde Foto-IDs; sie wird durch die stärkere Set-Whitelist ersetzt. Die Code-Kommentare, die sich auf die alte Garantie berufen, müssen mit entfernt werden, damit der Code keine Garantie mehr beschreibt, die es nicht mehr gibt.

## Offene Fragen

Keine — die Story wurde über `refinement` geschärft und liegt als abgenommene Story auf Issue #289.

## Out of Scope

- Konfigurierbarkeit des Kategorien-Sets pro Projekt — das Set ist global und wird nur über eine Code-Änderung angepasst.
- Ein eigenes Feld bzw. eine eigene Taxonomie für Anlass/Ereignis.
- Rückwirkende Migration oder Neuberechnung bestehender Kategoriedaten — es gibt keine erhaltenswerten Bestände.
