# 0047 - Inhaltsbasierte Landschafts-Erkennung, Spezifitäts-Vorrang bei der Kategorie-Vergabe und expliziter "nicht erkannt"-Zustand

**Status:** Accepted — **teilweise revidiert** durch ADR [`0049`](./0049-festes-kategorien-set-mit-vorrangreihenfolge-und-freien-feinlabels.md) (festes Kategorien-Set): die Punkte 2 (Spezifitäts-Vorrang), 3 (spezifitätsabhängige Aktivierungsschwelle) und 4 (Catch-all-Key `"unerkannt"`) sind dort ersetzt; die Punkte 1 (`landschaft`-Kriterium aus der Szenen-Klassifikation, `content_landscape` als reines Ranking-Signal), 5 (`is_landmark_candidate`), 6 (kein rückwirkender Eingriff in ältere `PhotoRanking`-Zeilen) und 7 (`category_diff.py`) gelten unverändert weiter.
**Datum:** 2026-08-30
**Bezug:** [GitHub-Issue #217](https://github.com/TheRealKoller/photosort/issues/217), künftige `features/0217-...md` (im Anschluss an diese Architektur-Konsultation anzulegen). **Revidiert [`decisions/0023-dynamische-kategorie-ableitung-aus-kriterien-haeufigkeit.md`](./0023-dynamische-kategorie-ableitung-aus-kriterien-haeufigkeit.md) in den Punkten 2 (einheitliche Häufigkeitsschwelle) und 3 (Prioritätsregel "höchster Score gewinnt" + Catch-all `"detail"`)** — die Punkte 1 (Kategorie-Fähigkeit als Registry-Attribut) und 4 (generische Ableitung des `category_key` aus dem `criterion_key`) von ADR 0023 bleiben unverändert gültig und werden hier ausdrücklich fortgeführt, ADR 0023 wird deshalb **nicht** als Superseded markiert (gleiches Muster wie ADR 0023 gegenüber ADR 0021 Punkt 2). Berührt außerdem: [`decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md`](./0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md) Punkt 1 (`remote:`-Pseudo-Keys, hier um eine Spezifitäts-Einstufung ergänzt, Mechanik unverändert), [`decisions/0022-lokale-modellwahl-tier-gebaeude-aesthetik-kriterien.md`](./0022-lokale-modellwahl-tier-gebaeude-aesthetik-kriterien.md) Punkt 2 (Szenen-Klassifikator + Allow-Liste, hier ein zweites Mal wiederverwendet), [`decisions/0025-cloud-landmark-erkennung.md`](./0025-cloud-landmark-erkennung.md) Punkt 3 / [`decisions/0035-cloud-vision-attempt-fehler-persistierung.md`](./0035-cloud-vision-attempt-fehler-persistierung.md) Punkt 4 (`is_landmark_candidate`-Vorfilterung, hier auf die neue Landschafts-Erkennung umgestellt), [`decisions/0015-lokale-kategorie-klassifikation.md`](./0015-lokale-kategorie-klassifikation.md) (Ursprung der Uniform-Flächen-Heuristik).

## Kontext

Beim Kuratieren landen zu viele Fotos in "Landschaft" und "Detail", ohne dass darauf eine Landschaft oder eine Detailaufnahme zu sehen wäre. Die Vorsortierung — der eigentliche Nutzen der Kuratierungsansicht — muss dadurch Foto für Foto von Hand korrigiert werden. Drei Ursachen im heutigen Code, alle drei strukturell, keine Schwellwert-Frage:

1. **`content_landscape` misst keine Landschaft.** `classification.py::compute_uniform_area_fraction` liefert den Anteil texturarmer Kacheln eines 8×8-Rasters. Eine glatte Wand, ein unscharfer Hintergrund oder eine dunkle Aufnahme erreichen denselben Wert wie ein Bergpanorama. Das Kriterium ist als *Ranking*-Signal ("Flächigkeit") legitim, als *Kategorie*-Aussage ("da ist eine Landschaft") war es nie belegt — Spec 0024/ADR 0015 hatten es ausdrücklich als Heuristik für die damalige, feste Prioritätskette eingeführt, nicht als Inhaltserkennung.

2. **`"detail"` ist eine Erkennung, die es nicht gibt.** `criteria.py::CATEGORY_DETAIL` ist der Auffangkorb für "kein aktives Kriterium erfüllt" (ADR 0023 Punkt 3). Das Ergebnis wird in der Kuratierungsansicht aber wie jede andere Kategorie als Abschnittsüberschrift dargestellt — eine Aussage über den Bildinhalt, die die Software gar nicht getroffen hat.

3. **Die Remote-Kategorisierung verpufft**, obwohl sie kostenpflichtig gelaufen ist. Zwei unabhängige Mechanismen aus ADR 0023 sorgen dafür:
   - *Häufigkeitsschwelle:* ein `remote:`-Pseudo-Key wird nur aktiv, wenn er auf ≥ 15 % der Kandidaten-Fotos des Laufs vorkommt (ADR 0023 Punkt 2, für dynamische Keys durch ADR 0032 Punkt 1 unverändert übernommen). Ein präzise erkanntes, aber seltenes Motiv ("Elefant" auf 20 von 500 Fotos = 4 %) bildet nie eine Kategorie.
   - *"Höchster Score gewinnt":* `derive_category_key` vergleicht Werte unterschiedlicher Skalen miteinander — einen Uniform-Flächen-Anteil (0,9 auf einem unscharfen Foto) gegen eine LLM-Konfidenz (0,85 für "Elefant"). Die unspezifischere Zahl gewinnt regelmäßig. ADR 0023 Punkt 3 hatte diese Regel bewusst gewählt ("die einzige Regel, die ohne Wartungsaufwand mit einer offenen Kriterien-Menge skaliert") und ihre Approximationsgüte am damaligen Stand begründet — mit dem Hinzukommen offener Remote-Label (ADR 0032) trägt diese Begründung nicht mehr.

Das Ziel der Story ist ausdrücklich eine inhaltlich bessere Erkennung, kein Nachjustieren von Schwellwerten, und ausdrücklich **ohne** zusätzliche laufende Kosten pro Foto, solange die Remote-Kategorisierung nicht ohnehin eingeschaltet ist.

Ein für diese Entscheidung wesentlicher Bestandsfakt: `worker.py::_compute_content_criteria` ruft für das `gebaeude`-Kriterium bereits heute pro Foto `classification.py::classify_scene` auf (mediapipe Image Classifier, EfficientNet-Lite0, ImageNet-1k, ADR 0022 Punkt 2) und wirft alle nicht-architekturbezogenen Labels weg. Die für eine echte Landschafts-Erkennung nötige Modellausgabe wird also bereits berechnet und bezahlt — sie wird nur nicht ausgewertet.

## Entscheidung

### 1. Neues Inhalts-Kriterium `landschaft` aus der bereits vorhandenen Szenen-Klassifikation; `content_landscape` verliert die Kategorie-Fähigkeit

Neues Registry-Kriterium, exakt nach dem Vorbild von `gebaeude`/`ARCHITECTURE_CATEGORIES` (ADR 0022 Punkt 2) — **keine neue Abhängigkeit, kein neues Modell-Asset, kein zusätzlicher Inferenz-Aufruf pro Foto:**

```python
def compute_landschaft_score(labels: Sequence[SceneLabel]) -> float: ...
```

Score = Konfidenz des besten Treffers innerhalb einer kuratierten `LANDSCAPE_SCENE_CATEGORIES`-Allow-Liste natürlicher ImageNet-1k-Szenenklassen (`alp`, `valley`, `seashore`, `lakeside`, `cliff`, `promontory`, `volcano`, `sandbar`, `coral_reef`, `geyser` u.ä. — exakte Schreibweise gegen die Label-Liste des gebündelten `efficientnet_lite0.tflite` zu verifizieren), 0.0 falls keiner der übergebenen Labels in der Allow-Liste liegt. `_compute_content_criteria` ruft `classify_scene` weiterhin **genau einmal** pro Foto auf und reicht dieselbe Label-Liste an `compute_gebaeude_score` *und* `compute_landschaft_score` weiter — dasselbe Wiederverwendungsmuster wie `detect_person` → `content_people` + `goldener_schnitt` (Spec 0038). Damit ist das Kosten-Akzeptanzkriterium strukturell erfüllt: die Verbesserung kostet keine zusätzliche Inferenz und keinen Cloud-Aufruf.

`content_landscape` wird auf `category_eligible=False` gesetzt (die Invariante aus ADR 0023 Punkt 1 erzwingt damit `category_presence_threshold=None`) und bleibt als reines Ranking-Signal erhalten — unverändert berechnet, unverändert in `DEFAULT_CRITERION_WEIGHTS`. Sein `display_name` wird von "Landschaft/Flächig" auf "Flächigkeit" korrigiert: der bisherige Name behauptet eine Inhaltsaussage, die die Kennzahl nicht trägt. Als Nebeneffekt wandert das Kriterium in den Bewertungsdetails automatisch vom Block "Kategorien" in den Block "Qualität" (Spec 0209 partitioniert ausschließlich nach dem Registry-Flag `category_eligible`) — genau die richtige Einordnung, ohne Frontend-Sonderfall.

**Konfidenz-Untergrenze:** `classify_scene` filtert heute hart bei `SCENE_CLASSIFICATION_CONFIDENCE_THRESHOLD = 0.5` — für Architektur-Klassen bewährt, für natürliche Szenen zu streng (ein Landschaftsfoto verteilt seine Modellkonfidenz typischerweise über mehrere benachbarte Szenenklassen). Da die bisherige Landschafts-"Erkennung" faktisch fast jede flächige Aufnahme erfasst hat, ist ein Recall-Einbruch das größte Risiko dieser Entscheidung (Akzeptanzkriterium: "der bisher gut funktionierende Fall darf sich nicht verschlechtern"). Deshalb: `build_scene_classifier`/`classify_scene` bekommen eine **niedrigere gemeinsame Untergrenze** `SCENE_LABEL_MIN_CONFIDENCE = 0.2` (plus `max_results=5`, damit die Label-Liste pro Foto beschränkt bleibt), und die inhaltliche Konfidenzschwelle wandert in die jeweilige Kriterien-Funktion:

- `compute_gebaeude_score` filtert **explizit** weiterhin bei `SCENE_CLASSIFICATION_CONFIDENCE_THRESHOLD` (0.5) — Verhalten identisch zu heute, testpflichtig.
- `compute_landschaft_score` filtert bei `LANDSCHAFT_LABEL_MIN_CONFIDENCE = 0.25`.

Die `category_presence_threshold` von `landschaft` ist wie bei `tier`/`gebaeude` eine reine "nichts erkannt vs. irgendetwas erkannt"-Trennung (`0.01`), keine zweite Konfidenzkalibrierung.

**Bewusst nicht gewählt:** ein szenenspezifisches Modell (Places365 o.ä.) — bräuchte ein drittes schweres ML-Framework im Backend-Image; ADR 0022 hat diese Grenze bereits gezogen, und die Story verlangt keine perfekte, sondern eine *belegte* Erkennung. **Dokumentierte, akzeptierte Lücke** (gleiche Klasse wie die ImageNet-Innenraum-Lücke aus ADR 0022): ImageNet-1k kennt keine Klassen für Wald, Wiese oder Feld — solche Landschaften werden strukturell nicht als `landschaft` erkannt und landen im "nicht erkannt"-Zustand (Punkt 4). Das ist ehrlicher als die heutige Falschzuordnung, aber eine echte Einschränkung.

### 2. Spezifitäts-Vorrang ersetzt "höchster Score gewinnt" als *primäre* Regel

`CriterionDefinition` bekommt ein drittes Kategorie-Attribut — Spezifität bleibt damit, wie schon die Kategorie-Fähigkeit selbst (ADR 0023 Punkt 1), ein Registry-Attribut statt einer im Ableitungscode gepflegten Liste:

```python
CATEGORY_SPECIFICITY_CONTENT = 10   # lokale Inhaltserkennung: "da ist ein Gesicht/Tier/Gebäude/eine Landschaft"
CATEGORY_SPECIFICITY_NAMED = 20     # benannter, konkreter Inhalt: Sehenswürdigkeit, Remote-Schlagwort

@dataclass(frozen=True)
class CriterionDefinition:
    ...
    category_specificity: int = CATEGORY_SPECIFICITY_CONTENT
```

`landmark` bekommt `CATEGORY_SPECIFICITY_NAMED`, alle übrigen kategorie-fähigen Kriterien behalten den Default. `remote:`-Pseudo-Keys (ADR 0032 Punkt 1) haben keine `CriterionDefinition` und gelten **immer** als `CATEGORY_SPECIFICITY_NAMED`.

`derive_category_key` wählt unter den erfüllten aktiven Kriterien nach dem Schlüssel `(-specificity, -score, key)`: **höchste Spezifität zuerst, erst innerhalb derselben Spezifitätsstufe der höchste normierte Score, dann alphabetisch nach vollem `criterion_key`** (Tie-Break unverändert deterministisch, ADR 0023 Punkt 3). Damit setzt sich ein benannter, konkret erkannter Inhalt ("Wasserfall", "Kölner Dom") gegen die grobe lokale Einordnung durch, statt an einem zufällig höheren Zahlenwert einer anderen Skala zu scheitern. Innerhalb einer Stufe bleibt die bisherige, vertraute Regel unverändert — insbesondere gewinnt `content_people` (binär 1.0) weiterhin gegen `tier`/`gebaeude`/`landschaft`.

Zwei Stufen statt einer feineren Rangordnung ist Absicht: die einzige Unterscheidung, die die Story trägt, ist "benannter Inhalt vs. grobe Inhaltsklasse". Eine Feinsortierung *innerhalb* der lokalen Kriterien wäre wieder die gepflegte Prioritätsliste, die ADR 0023 zu Recht vermieden hat.

**Bewusste Folge (vom Stakeholder am 2026-08-30 bestätigt):** ein Foto mit erkannten Gesichtern *und* einem Remote-Schlagwort ("Hochzeit") landet künftig unter dem Remote-Schlagwort, nicht mehr unter "People". Das ist die konsequente Lesart des Akzeptanzkriteriums "ein genauer erkannter Bildinhalt setzt sich gegenüber einer unspezifischen Einordnung durch" — "Menschen erkannt" ist die unspezifischere Aussage. Betroffen sind ausschließlich Projekte, für die die Remote-Kategorisierung bewusst eingeschaltet und bezahlt wurde.

### 3. Aktivierungsschwelle wird spezifitätsabhängig

`derive_active_categories` bleibt strukturell unverändert (eine Aggregation pro Lauf, projektweit, reine Funktion, ADR 0023 Punkt 2), bekommt aber eine zweite, alternative Aktivierungsbedingung für die Stufe `CATEGORY_SPECIFICITY_NAMED`:

- `CATEGORY_SPECIFICITY_CONTENT`: unverändert `Anteil >= CATEGORY_ACTIVE_THRESHOLD_FRACTION` (15 %).
- `CATEGORY_SPECIFICITY_NAMED`: aktiv, wenn `Trefferzahl >= CATEGORY_SPECIFIC_MIN_PHOTOS` **oder** `Anteil >= CATEGORY_ACTIVE_THRESHOLD_FRACTION`. Die `oder`-Verknüpfung ist nötig, damit sehr kleine Projekte (< 20 Kandidaten) nicht schlechter gestellt werden als heute.

**`CATEGORY_SPECIFIC_MIN_PHOTOS = 3`** — eine absolute Mindestzahl statt eines Anteils, weil genau die Anteils-Mechanik das Problem verursacht: ein präzise erkanntes Motiv soll nicht daran scheitern, dass das Projekt groß ist. Der Wert ist eine dokumentierte, nicht gegen einen Fotokorpus kalibrierte Setzung derselben Klasse wie `CATEGORY_ACTIVE_THRESHOLD_FRACTION` und beantwortet einen echten Zielkonflikt: bei `1` bekäme jede Einzelerkennung einen eigenen Abschnitt in der Kuratierungsansicht (bei bis zu drei freien Schlagworten pro Foto potenziell dutzende Ein-Foto-Abschnitte — die Zersplitterung würde denselben Kuratierungsschritt entwerten, den diese Entscheidung reparieren soll); bei `3` kommen seltene Motive durch ("wenige Fotos" im Sinne der Story), echte Einzeltreffer bleiben im "nicht erkannt"-Zustand sichtbar und dort weiterhin per Hand übernehmbar (die Kandidatenliste am Foto zeigt die Erkennung unverändert an, `_category_candidates_out`). Austauschbar ohne Architektur-Änderung.

### 4. Expliziter "nicht erkannt"-Zustand statt des Auffangkorbs "detail"

`CATEGORY_DETAIL = "detail"` entfällt und wird durch `CATEGORY_UNRECOGNIZED = "unerkannt"` ersetzt (Anzeigename "Nicht erkannt" über das bestehende `CATEGORY_DISPLAY_NAME_OVERRIDES`-Mapping in `frontend/src/utils/categoryLabels.ts`). Fotos ohne erfülltes aktives Kriterium landen weiterhin dort — sie fallen also **nicht** aus der automatischen Auswahl heraus (bewusste Fortführung der Entscheidung aus Spec 0045: Auffangkategorie statt Ausschluss, damit die Partitionierung `cluster_key × category_key` und die Top-N-Logik unverändert funktionieren), sind aber als das erkennbar, was sie sind: ein fehlendes Erkennungsergebnis, keine Inhaltsaussage.

`"detail"` wird damit **nicht** mehr automatisch vergeben. Die Bezeichnung bleibt möglich, wenn sie tatsächlich zutrifft — als Remote-Schlagwort ("Detailaufnahme" → `canonical_key`) oder als manuelle Übernahme. Ein eigener lokaler Detail-/Makro-Detektor wird bewusst **nicht** gebaut: es gibt kein belastbares lokales Signal dafür (die vorhandenen Modelle liefern keines, EXIF-Fokusdaten sind nicht erfasst), und die Story verlangt ausdrücklich, die Bezeichnung nur noch dort zu verwenden, wo sie zutrifft — nicht, einen Ersatzdetektor zu erfinden.

### 5. Landmark-Vorfilterung folgt der neuen Landschafts-Erkennung

`criteria.py::is_landmark_candidate` prüft heute `content_landscape` **oder** `gebaeude` gegen deren registrierte Presence-Schwellen. Da `content_landscape` seine Schwelle verliert (Punkt 1), wird die Vorfilterung auf `landschaft` **oder** `gebaeude` umgestellt — inhaltlich exakt das, was der Filter immer ausdrücken sollte ("auf dem Foto ist eine Landschaft oder ein Gebäude zu sehen"). Die Kandidatenmenge für den kostenpflichtigen Landmark-Cloud-Aufruf wird dadurch kleiner und präziser (keine Cloud-Aufrufe mehr für unscharfe oder dunkle Fotos) — eine Kosten*senkung*, keine Kostenerhöhung. Beide Nutzer dieser Funktion (`worker.py::_select_landmark_candidates` im Lauf, `api/photos.py::_cloud_vision_status_out` als Read-Time-Ableitung) bleiben unverändert an derselben gemeinsamen Funktion (ADR 0035 Punkt 4).

### 6. Keine Migration, Bestandsdaten bleiben unangetastet

Kein Schema-Eingriff: `PhotoRanking.category_key` und `PhotoCriterionScore.criterion_key` sind freie Strings, die neuen Registry-Felder sind reine In-Code-Metadaten. Die neue Logik gilt — wie schon bei ADR 0023 — **erst für künftige `CriterionScoringRun`-Läufe**; bereits geschriebene `PhotoRanking`-Zeilen älterer Läufe werden nicht rückwirkend neu berechnet (und dürfen es nicht, siehe Punkt 7).

`PhotoScore.category_override` wird von dieser Entscheidung **nicht berührt**: der Override ist ein freier String und wird in `run_criterion_scoring` *vor* jeder Ableitung angewendet (`category_override or derive_category_key(...)`), überlebt also jeden Re-Scoring-Lauf unverändert — auch mit einem Wert, den die neue Ableitung selbst nie mehr erzeugen würde (`"landscape"`, `"detail"`). Ein solcher Override ist danach ein "verwaister" Kandidat; dafür existiert bereits eine bewusst gebaute Darstellung (`CriterionDetailsList`, `isOrphan`-Zeile) und ein Rücknahme-Pfad (`DELETE /photos/{id}/category-override`). Kein Sonderfallcode, kein Datenmigrationsschritt.

### 7. Vorher/Nachher-Vergleich als read-only Diff-Werkzeug über zwei Scoring-Läufe

Die Verifikation an einem echten Fotobestand (Akzeptanzkriterium) braucht kein neues Datenmodell und keine API-Erweiterung: `PhotoRanking`-Zeilen werden pro `criterion_scoring_run_id` geschrieben und **nie gelöscht** — die Kategorie-Zuordnung des letzten Laufs *vor* der Umstellung liegt bereits in der Datenbank. Ein neues, rein lesendes CLI-Modul `backend/src/photosort/category_diff.py` (Aufruf: `docker compose exec backend python -m photosort.category_diff --project-id N`) vergleicht zwei Läufe eines Projekts (Default: die beiden jüngsten erfolgreichen) und gibt eine Übergangsmatrix (alte Kategorie → neue Kategorie, mit Anzahlen) sowie die Foto-Einzelliste (`relative_path`, alt, neu) aus.

Bewusst ein CLI-Werkzeug und kein Endpunkt/keine UI: eine einmalige Verifikations- und Kalibrierungshilfe für zwei bekannte Betreiber, die keine dauerhaft zu pflegende Produktoberfläche rechtfertigt. Aufgeteilt in eine reine, vollständig unit-testbare Diff-/Rendering-Funktion und eine dünne DB-Leseschicht (Muster analog `criteria.py`/`ranking.py`: Logik rein, I/O außen).

## Begründung

- **Behebt die Ursachen, nicht die Symptome.** Jede der drei Beschwerden aus der Story wird an ihrer strukturellen Ursache adressiert: eine Textur-Kennzahl, die als Inhaltsaussage verkauft wurde (Punkt 1); ein Auffangkorb, der als Erkennung dargestellt wurde (Punkt 4); ein Skalen-Vergleich zwischen unvergleichbaren Zahlen plus eine Häufigkeitsregel, die seltene Präzision bestraft (Punkte 2/3). Kein Punkt ist ein Nachjustieren eines Schwellwerts.
- **Führt ADR 0023 fort, statt sie zu ersetzen.** Kategorie-Fähigkeit und Spezifität sind beide Registry-Attribute; ein künftiges Inhalts-Kriterium wird weiterhin allein durch seinen Registry-Eintrag kategorie-fähig, und der `category_key` wird weiterhin generisch aus dem `criterion_key` abgeleitet. Die Kernaussage von ADR 0023 ("keine im Ableitungscode gepflegte Liste") bleibt unangetastet — Punkt 2 dieser ADR macht die Spezifität ausdrücklich zu einem *Attribut*, nicht zu einer Prioritätsliste.
- **Kein neuer Kostentreiber.** Die bessere Erkennung entsteht durch das Auswerten einer bereits berechneten Modellausgabe. Ohne eingeschaltete Remote-Kategorisierung ändert sich weder die Anzahl der Inferenzen pro Foto noch die Anzahl der Cloud-Aufrufe — letztere sinkt sogar (Punkt 5).
- **Ehrlichkeit vor Vollständigkeit.** Ein sichtbarer "Nicht erkannt"-Abschnitt ist für den Kuratierungs-Durchsatz wertvoller als eine erfundene Kategorie: der Nutzer weiß sofort, wo er selbst hinschauen muss, statt jede Kategorie gegen die Realität prüfen zu müssen.

## Konsequenzen

- **Sichtbare Verhaltensänderung für Bestandsprojekte beim nächsten Kriterien-Lauf:** die Kategorie `"landscape"` verschwindet zugunsten von `"landschaft"` (nur noch mit echtem Landschaftsmotiv), `"detail"` verschwindet aus der automatischen Vergabe zugunsten von `"unerkannt"`. Der "Nicht erkannt"-Abschnitt wird anfangs spürbar größer als der bisherige "Detail"-Abschnitt — das ist die beabsichtigte, ehrliche Darstellung des tatsächlichen Erkennungsstands, kein Rückschritt.
- **Recall-Risiko bei Landschaften** (Wald/Wiese/Feld, siehe Punkt 1): der einzige Punkt dieser ADR, der ein Akzeptanzkriterium ("der bisher gut funktionierende Fall darf sich nicht verschlechtern") verfehlen kann. Genau dafür existiert das Diff-Werkzeug aus Punkt 7; die Allow-Liste und `LANDSCHAFT_LABEL_MIN_CONFIDENCE` sind bewusst so gebaut, dass eine Nachkalibrierung eine reine Konstanten-/Listen-Änderung bleibt (keine Architektur-Änderung, keine neue ADR).
- **Zwei produktseitig spürbare Setzungen wurden vom Stakeholder am 2026-08-30 bestätigt:** (a) `CATEGORY_SPECIFIC_MIN_PHOTOS = 3` (Punkt 3, Zielkonflikt Treue vs. Zersplitterung der Ansicht — bewusst gegen `1` und `5` entschieden), (b) der Vorrang eines Remote-Schlagworts gegenüber `content_people` (Punkt 2 — bewusst gegen den Fortbestand des `content_people`-Vorrangs entschieden). Beides bleibt kalibrierbar: technisch jeweils eine Zeile, ohne Architektur-Änderung.
- **`landschaft` geht automatisch in `DEFAULT_CRITERION_WEIGHTS` ein** (`{key: 1.0 for key in CRITERIA_REGISTRY}`) und verschiebt damit die Rangfolge innerhalb einer Partition minimal — dasselbe, bereits akzeptierte Verhalten wie bei jedem bisher hinzugefügten Kriterium (Specs 0038/0048).
- **`docs/architecture.md`** (Owner: `architect`) wird **im Umsetzungs-PR** um das neue Kriterium `landschaft`, das Registry-Feld `category_specificity`, die geänderte Aktivierungs-/Auswahlregel und den neuen Catch-all-Key ergänzt — analog dem bei ADR 0021/0023 etablierten Muster (das Dokument beschreibt den umgesetzten Stand, nicht den geplanten). Datenmodell-Abschnitt: nur redaktionell (kein Schema-Eingriff).
- **Ein späterer Wechsel des Auswahlprinzips** (mehr als zwei Spezifitätsstufen, Mehrfachzuordnung eines Fotos zu mehreren Kategorien, Projekt-spezifische Schwellwerte statt globaler Konstanten) bleibt architekturrelevant und braucht eine neue ADR, die diese hier als "Superseded" markiert.
