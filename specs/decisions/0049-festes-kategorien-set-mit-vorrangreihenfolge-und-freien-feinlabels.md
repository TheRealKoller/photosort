# 0049 - Festes, anwendungsweit einheitliches Kategorien-Set mit deterministischer Vorrangreihenfolge; freie Schlagworte nur noch als Feinlabels

**Status:** Accepted
**Datum:** 2026-08-30
**Bezug:** [GitHub-Issue #289](https://github.com/TheRealKoller/photosort/issues/289), `specs/features/0289-feste-kategorien.md` (im Anschluss an diese Architektur-Konsultation anzulegen).

**Löst ab (Superseded):**
- [`decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md`](./0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md) — dessen Punkt 1 (offenes Vokabular, `remote:`-Pseudo-Kriterien-Keys, Kategoriebildung aus zur Laufzeit entdeckten Schlagworten) ist die Entscheidung, die diese ADR ausdrücklich umkehrt. Die Punkte 3 (Provider-Dispatch/`cloud_vision.py`), 4 (Label-Normalisierung + Embedding-Ähnlichkeit), 5 (eigener Job), 6 (Endpunkte), 7 (`reassign_photo_category`) und 8 (Kostenschätzung) bleiben als Mechanik erhalten, aber mit geändertem Inhalt — sie sind unten jeweils neu gefasst, damit ADR 0049 als Ganzes lesbar ist und nicht gegen eine abgelöste ADR gelesen werden muss.
- [`decisions/0023-dynamische-kategorie-ableitung-aus-kriterien-haeufigkeit.md`](./0023-dynamische-kategorie-ableitung-aus-kriterien-haeufigkeit.md) — die Kernaussage ("Kategorien ergeben sich projektweit aus der Häufigkeit eines Kriteriums im Lauf") entfällt vollständig: `derive_active_categories`, `CATEGORY_ACTIVE_THRESHOLD_FRACTION` und die generische Key-Ableitung aus dem `criterion_key` werden ersatzlos gelöscht. Erhalten bleibt allein das Registry-Attribut `CriterionDefinition.category_eligible`/`.category_presence_threshold` — unten in Punkt 4 neu begründet.

**Revidiert (nicht abgelöst):** [`decisions/0047-inhaltsbasierte-landschaft-spezifitaets-vorrang-nicht-erkannt.md`](./0047-inhaltsbasierte-landschaft-spezifitaets-vorrang-nicht-erkannt.md) in den Punkten **2** (Spezifitäts-Vorrang — ersetzt durch die feste Vorrangreihenfolge), **3** (spezifitätsabhängige Aktivierungsschwelle — entfällt mit der Häufigkeitsmechanik) und **4** (Catch-all-Key `"unerkannt"` — wird zum regulären Set-Mitglied `nicht_erkannt`). Die Punkte **1** (`landschaft`-Kriterium aus der ohnehin berechneten Szenen-Klassifikation, `content_landscape` als reines Ranking-Signal), **5** (`is_landmark_candidate` prüft `landschaft`/`gebaeude`), **6** (kein rückwirkender Eingriff in ältere `PhotoRanking`-Zeilen) und **7** (`category_diff.py` als Vorher/Nachher-Werkzeug) bleiben unverändert gültig und werden hier fortgeführt.

**Berührt außerdem:** [`decisions/0022-lokale-modellwahl-tier-gebaeude-aesthetik-kriterien.md`](./0022-lokale-modellwahl-tier-gebaeude-aesthetik-kriterien.md) Punkt 1 (COCO-Objekterkennung — hier ein zweites und drittes Mal ausgewertet statt neu berechnet), [`decisions/0033-modell-asset-download-statt-commit-label-embedder.md`](./0033-modell-asset-download-statt-commit-label-embedder.md) (bleibt unverändert gültig, das Embedding-Modell wird weiterverwendet — jetzt für Feinlabels statt für Kategorien), [`decisions/0021-kriterien-datenmodell-kuratierungs-pipeline.md`](./0021-kriterien-datenmodell-kuratierungs-pipeline.md) (`PhotoRanking`-Partitionierung `cluster_key × category_key` unverändert).

## Kontext

ADR 0032 hat auf ausdrückliche Kurskorrektur hin ein **offenes Vokabular** eingeführt: Das Vision-LLM liefert 1-3 frei formulierte Schlagworte, aus denen sich Kategorien über eine Häufigkeitsschwelle (ADR 0023) und einen Spezifitäts-Vorrang (ADR 0047) *ergeben*. Die Begründung damals: "Kategorien sollen sich aus den Ergebnissen ergeben, nicht vorher feststehen."

Der reale Betrieb hat gezeigt, dass genau diese Eigenschaft den Kernmechanismus der Kuratierung beschädigt. Die Kuratierungsansicht gruppiert Fotos nach `PhotoRanking.category_key`; ein offenes Vokabular erzeugt dort projektabhängige, beliebig geschnittene Abschnitte. Drei strukturelle Ursachen, keine Schwellwert-Frage:

1. **Unvorhersehbarkeit.** Dieselbe Fotosammlung ergibt bei zwei Läufen bzw. in zwei Projekten unterschiedliche Kategorien, weil die Kategoriemenge aus einer Häufigkeitsaggregation über den jeweiligen Kandidatenpool entsteht. Der Nutzer kann keine Erwartung aufbauen, welche Abschnitte er sieht — die Kuratierung wird jedes Mal neu erlernt statt routiniert abgearbeitet.
2. **Zersplitterung.** Bis zu drei freie Schlagworte pro Foto erzeugen eine große Label-Menge. Die Ähnlichkeits-Zusammenfassung (ADR 0032 Punkt 4) fasst Schreibvarianten zusammen, aber nicht *Konzepte* unterschiedlicher Granularität ("Hund", "Welpe", "Haustier", "Spaziergang"). Die Kuratierung zerfällt in viele kleine Abschnitte statt in wenige, gleich bleibende.
3. **Zwei parallele Kategoriewelten.** Lokale Kriterien (`content_people`/`tier`/`gebaeude`/`landschaft`) und Remote-Labels leben zwar in derselben Auswahlfunktion, aber in getrennten Namensräumen mit unterschiedlichen Wertskalen — ADR 0047 musste dafür eigens eine Spezifitätsstufe einführen, damit die Skalen nicht direkt gegeneinander verglichen werden. Ein Foto konnte lokal `"people"` und remote `"menschen"` sein (in ADR 0032 Punkt 1 als bewusst offene Lücke dokumentiert).

Die Anlass-Dimension ("Geburtstag", "Urlaub", "Weihnachten") ist zusätzlich ein Kategorisierungsfehler eigener Art: sie beantwortet eine andere Frage als "was ist auf dem Bild zu sehen" und konkurriert deshalb mit jeder Motiv-Kategorie, statt sie zu ergänzen.

Die Produktentscheidung, die diese ADR umsetzt, kehrt die Richtung um: **das Vokabular wird geschlossen und global; frei formulierte Begriffe bleiben erhalten, aber ausschließlich als Zusatzinformation am Foto** (Feinlabels), ohne Wirkung auf die Gruppierung. Die Rückkehr zu einem festen Set ist keine Rücknahme der Erkenntnis von ADR 0032, sondern eine Verschiebung der Zuständigkeit: das LLM liefert weiterhin freie Sprache, aber sie ist nicht mehr die Kategoriequelle.

## Entscheidung

### 1. Neues Modul `categories.py` als einzige Quelle der Wahrheit für Set, Definitionen, Vorrang und Prompt

Das feste Set lebt vollständig in einem neuen Backend-Modul `backend/src/photosort/categories.py` — bewusst **nicht** in `criteria.py`: die Kriterien-Registry beschreibt Mess-Signale für das Ranking, das Kategorien-Set beschreibt eine Produkt-Taxonomie. Beide ändern sich aus unterschiedlichen Gründen; ADR 0032/0047 haben beide Konzepte in `criteria.py` vermischt, und genau daraus stammt die Skalen-/Namensraum-Vermischung aus Kontext-Punkt 3.

```python
@dataclass(frozen=True)
class CategoryDefinition:
    key: str                  # slug, [a-z_], z.B. "gebaeude_bauwerk"
    display_name: str         # deutsche Bezeichnung, z.B. "Gebäude & Bauwerk"
    definition: str           # kurze, positive Beschreibung
    delimitation: str         # Negativabgrenzung
    precedence: int           # Rang der Vorrangreihenfolge, kleiner = stärker
```

`CATEGORY_REGISTRY: dict[str, CategoryDefinition]` enthält **genau** die dreizehn Einträge (zwölf Kategorien + Catch-all), in Deklarationsreihenfolge = Anzeigereihenfolge. Es gibt keinen Codepfad, der einen `category_key` außerhalb dieses Mappings erzeugt.

Drei abgeleitete, reine Funktionen im selben Modul:

- `resolve_category(candidates: Iterable[str]) -> str` — wählt aus einer Kandidatenmenge deterministisch **nach `precedence`**, ignoriert unbekannte Werte, ignoriert `CATEGORY_NOT_RECOGNIZED`, sobald mindestens eine echte Kategorie enthalten ist, und liefert `CATEGORY_NOT_RECOGNIZED` bei leerer Menge. Das ist die einzige Stelle im Code, an der eine Kategorie zugewiesen wird.
- `build_classification_prompt() -> str` — erzeugt den Vision-Prompt **aus** `CATEGORY_REGISTRY` (Leitfrage + Tabelle aus `display_name`/`definition`/`delimitation` + Antwortschema). Der Prompt kann damit nicht gegen das Set driften, und eine Set-Änderung ist eine Ein-Zeilen-Änderung an genau einer Stelle.
- `is_known_category(key: str) -> bool` — gemeinsame Validierung für Remote-Antwort und Override-Endpunkt.

**Verworfen:** ein `StrEnum` statt eines Dataclass-Registries. Die Definitions-/Negativabgrenzungstexte sind fachlich Teil der Kategorie (sie sind die Prompt-Grundlage und die Erklärung in der UI) — ein Enum hätte sie in eine zweite, parallel zu pflegende Struktur gedrängt. Das Registry-Muster ist im Projekt bereits etabliert (`CRITERIA_REGISTRY`).

### 2. Das feste Set: zwölf Kategorien + Catch-all, mit Definition und Negativabgrenzung

Leitfrage für jede Zuordnung, lokal wie remote: **"Was ist das dominante Bildmotiv?"** Anlass-/Ereignisbegriffe (Geburtstag, Urlaub, Weihnachten, Hochzeit) bilden ausdrücklich keine Kategorie — sie gehören in die Feinlabels (Punkt 6).

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
| 9 | `gegenstand` | Gegenstand | Ein konkreter, erkannter Gegenstand ohne passendere spezifischere Kategorie ist bildbestimmend (Werkzeug, Kleidung, Möbelstück, Gerät, Spielzeug, Objekt-Detailaufnahme). | **Nicht** als Ersatz für eine unsichere Erkennung — ist kein Motiv sicher bestimmbar, gilt "Nicht erkannt". Nicht, wenn eine der spezifischeren Kategorien zutrifft. |
| 10 | `dokument_screenshot` | Dokument & Screenshot | Eine Text-, Bildschirm- oder Dokumentabbildung ist bildbestimmend (Screenshot, abfotografiertes Dokument/Formular/Beleg, Ticket, QR-Code, Schild, dessen Text der Bildzweck ist). | Nicht bei Fotos, auf denen Text nur beiläufig vorkommt (Ladenschild in einer Straßenszene → Gebäude & Bauwerk). Nicht bei kunstvoll gestalteten Schriftbildern als Kunstwerk (→ Kunst & Kreatives). |
| 11 | `kunst_kreatives` | Kunst & Kreatives | Ein Kunstwerk oder ein kreatives Erzeugnis ist bildbestimmend (Gemälde, Skulptur, Wandbild/Graffiti, Museumsexponat, Handarbeit, Bastelarbeit, Zeichnung). | Nicht bei Bauwerken mit kunstvoller Fassade (→ Gebäude & Bauwerk). Nicht bei kunstvoll angerichteten Speisen (→ Essen & Trinken). |
| 12 | `sport_aktivitaet` | Sport & Aktivität | Eine sportliche oder körperlich aktive Handlung ist bildbestimmend (Laufen, Radfahren, Schwimmen, Ski, Ballsport, Wandern, Klettern, Spielplatz-Aktivität). | Nicht bei bloßem Posieren mit Sportgerät ohne erkennbare Handlung (→ Menschen). Nicht bei einem abgestellten Sportgerät ohne handelnde Person (→ Gegenstand bzw. Fahrzeug). |
| — | `nicht_erkannt` | Nicht erkannt | Kein Bildmotiv ist sicher bestimmbar — unscharf, zu dunkel, stark abstrakt, oder die Erkennung ist zu unsicher. | Nicht zu verwenden, wenn ein Motiv erkennbar ist, aber keine spezifischere Kategorie passt — dann "Gegenstand". |

**Vorrangreihenfolge** (`precedence`, kleiner gewinnt), verbindlich aus der Story übernommen:

`dokument_screenshot` → `sport_aktivitaet` → `menschen` → `tier` → `essen_trinken` → `fahrzeug` → `kunst_kreatives` → `pflanze` → `gebaeude_bauwerk` → `landschaft` → `innenraum` → `gegenstand`; `nicht_erkannt` steht außerhalb der Reihenfolge und greift ausschließlich bei leerer Kandidatenmenge.

`sport_aktivitaet` steht bewusst **vor** `menschen`: bei sportlichen Aktivitäten sind fast immer Personen bildbestimmend, die Kategorie könnte sonst faktisch nie gewinnen.

**Wesentlich:** Die Reihenfolge wird ausschließlich in `resolve_category` durchgesetzt, nie im Modell-Ermessen. Der Prompt fragt deshalb nach **allen in Frage kommenden** Kategorien, nicht nach "der einen richtigen" (Punkt 5) — die Entscheidung, welche davon gewinnt, ist Code und damit testbar und reproduzierbar.

`nicht_erkannt` ist trotzdem **explizit Teil der auswählbaren Möglichkeiten** im Prompt (nicht nur ein nachgelagerter Fallback): das Modell soll aktiv "kein Motiv sicher bestimmbar" sagen können, statt in eine Verlegenheitskategorie gedrängt zu werden. Beide Wege führen zum selben Ergebnis, aber der explizite Weg macht die Unterscheidung zu `gegenstand` im Prompt überhaupt formulierbar.

### 3. Ein Kandidatenpool aus lokalen und remoten Signalen — keine zwei Kategoriewelten mehr

Die Kategorie eines Fotos entsteht in `worker.py::run_criterion_scoring` (unverändert der Ort, an dem `PhotoRanking` geschrieben wird) aus **einer** Kandidatenmenge:

```
kandidaten = lokale_kandidaten(criterion_values) | remote_kandidaten(photo_category_classifications)
category_key = score.category_override or resolve_category(kandidaten)
```

Die frühere zweistufige Mechanik (`derive_active_categories` über den ganzen Lauf, dann `derive_category_key` je Foto) entfällt vollständig. Die Zuweisung ist damit eine **reine Pro-Foto-Funktion ohne Laufkontext** — dieselben Bildsignale ergeben immer dieselbe Kategorie, unabhängig davon, welche anderen Fotos im Projekt liegen. Genau das ist die Vorhersehbarkeit, die die Story verlangt.

Ersatzlos gelöscht: `derive_active_categories`, `derive_category_key`, `CATEGORY_ACTIVE_THRESHOLD_FRACTION`, `CATEGORY_SPECIFIC_MIN_PHOTOS`, `DYNAMIC_LABEL_PRESENCE_THRESHOLD`, `CATEGORY_SPECIFICITY_CONTENT`/`_NAMED`, `_specificity_of`, `CriterionDefinition.category_specificity`, `CATEGORY_UNRECOGNIZED`, `_RESERVED_CATEGORY_KEY_SUFFIX`, `worker.py::_merge_remote_category_labels` und der gesamte `remote:`-Pseudo-Key-Namensraum.

Der reservierte Catch-all-Key braucht keine Kollisionsabsicherung mehr (`_RESERVED_CATEGORY_KEY_SUFFIX`, Security-Punkt der Spec 0217): ein `category_key` kann nur noch aus `CATEGORY_REGISTRY` stammen, ein frei formulierter LLM-Text erreicht diesen Namensraum konstruktionsbedingt nicht mehr. Das ist eine strukturelle Härtung, kein Wegfall einer Schutzmaßnahme.

### 4. Lokal bestimmbare Teilmenge: sechs der zwölf Kategorien, ohne eine einzige zusätzliche Inferenz

`categories.py` hält die Zuordnung lokaler Signale zu Set-Kategorien als explizite Tabelle:

```python
LOCAL_CATEGORY_SIGNALS: dict[str, tuple[str, ...]] = {
    "menschen":         ("content_people",),
    "tier":             ("tier",),
    "essen_trinken":    ("essen_trinken",),
    "fahrzeug":         ("fahrzeug",),
    "gebaeude_bauwerk": ("gebaeude", "landmark"),
    "landschaft":       ("landschaft",),
}
```

Ein lokaler Kandidat liegt vor, wenn mindestens eines der genannten Kriterien seine in `CRITERIA_REGISTRY` registrierte `category_presence_threshold` erreicht. Die Schwellen bleiben damit **dort**, wo sie fachlich hingehören (beim Mess-Signal), und werden nicht ein zweites Mal gepflegt. Registry-Invariante (Test-erzwungen, analog der bestehenden `category_eligible`-Invariante): jedes in `LOCAL_CATEGORY_SIGNALS` referenzierte Kriterium ist `category_eligible=True` mit gesetzter Schwelle — und umgekehrt.

**Eine gepflegte Mapping-Tabelle ist hier kein Rückfall hinter ADR 0023.** ADR 0023 hat eine gepflegte Prioritätsliste vermieden, weil die Kriterien-/Kategoriemenge *offen und wachsend* war. Diese ADR schließt die Kategoriemenge per Produktentscheidung — bei einem geschlossenen Set von dreizehn Werten ist eine explizite, an einer Stelle lesbare Zuordnung die klarere Lösung, nicht die teurere. `CriterionDefinition.category_eligible`/`.category_presence_threshold` bleiben erhalten (sie tragen weiterhin die "Motiv erkannt"-Schwelle und die Blocktrennung Qualität/Inhalt in den Bewertungsdetails, Spec 0209); nur `category_specificity` entfällt.

**Zwei neue lokale Kriterien, beide aus einer bereits berechneten Modellausgabe** — dasselbe Muster, mit dem ADR 0047 `landschaft` aus der ohnehin laufenden Szenen-Klassifikation gewonnen hat:

- `classification.py::detect_animals` wird zu `detect_objects` verallgemeinert (Rückgabetyp `AnimalDetection` → `ObjectDetection`, gleiche Felder): der COCO-Detektor (`efficientdet_lite0.tflite`, ADR 0022 Punkt 1) läuft weiterhin **genau einmal pro Foto**, wirft aber seine nicht-tierischen Erkennungen nicht mehr weg.
- Neue reine Funktionen in `criteria.py`, jeweils Allow-Listen-gefiltertes Maximum der Konfidenz — exakt das Muster von `compute_gebaeude_score`/`compute_landschaft_score`: `compute_tier_score` (filtert jetzt selbst auf `ANIMAL_CATEGORIES`, statt eine vorgefilterte Liste zu erwarten), `compute_fahrzeug_score` (`VEHICLE_CATEGORIES`), `compute_essen_trinken_score` (`FOOD_CATEGORIES`).
- **Verhaltenserhalt (verpflichtend, sonst stille Änderung):** `compute_golden_ratio_score` bekommt weiterhin **nur** die Tier-Erkennungen als Subjekt-Kandidaten (`animal_detections(objects)`-Hilfsfunktion) — ein Auto oder ein Teller darf nicht plötzlich zum Kompositions-Subjekt werden.

Allow-Listen (COCO-80; die exakte Schreibweise ist einmalig gegen die im `.tflite` mitgelieferte Label-Datei zu verifizieren, gleiche Pflicht wie bei `LANDSCAPE_SCENE_CATEGORIES`, ADR 0047 Punkt 1):

- `VEHICLE_CATEGORIES = {"bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat"}`
- `FOOD_CATEGORIES = {"banana", "apple", "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "wine glass"}` — **bewusst ohne** Geschirr/Besteck (`cup`, `bottle`, `bowl`, `fork`, `knife`, `spoon`): diese Objekte kommen in Raum- und Personenszenen zu häufig beiläufig vor und würden "Essen & Trinken" systematisch falsch auslösen. Präzision vor Recall — ein falsch zugeordnetes Foto kostet den Kuratierungsvorteil, ein "Nicht erkannt" nicht (Fortführung der Haltung aus ADR 0047 Punkt 4).

`landmark` (Cloud-Sehenswürdigkeit, ADR 0025) verliert seine eigene Kategorie und wird zum Signal für `gebaeude_bauwerk` — im festen Set gibt es keine Kategorie "Sehenswürdigkeit", und ein erkanntes Wahrzeichen ist fachlich ein Bauwerk. Der erkannte Name bleibt am Foto sichtbar wie bisher (`PhotoLandmarkDetection`), er wird nur nicht mehr zur Gruppierungsachse.

**Dokumentierte, akzeptierte Lücken der lokalen Teilmenge** (dieselbe Klasse wie die ImageNet-Innenraum-Lücke aus ADR 0022 und die Wald/Wiese/Feld-Lücke aus ADR 0047): `pflanze`, `innenraum`, `dokument_screenshot`, `kunst_kreatives`, `sport_aktivitaet` und `gegenstand` sind **rein remote** bestimmbar. Ohne eingeschaltete Remote-Kategorisierung fallen entsprechende Fotos in "Nicht erkannt" — das ist die von der Story ausdrücklich vorgesehene Konsequenz ("nur die lokal bestimmbare Teilmenge; alle übrigen Fotos erhalten Nicht erkannt"). Für `pflanze` wäre eine ImageNet-Allow-Liste technisch möglich (`daisy`, `rapeseed`, `corn`, …), wird aber **bewusst nicht** gebaut: ImageNet-1k kennt nur einzelne Arten, und ausgerechnet die schwierigste Abgrenzung des Sets (Blumenwiese-Weitwinkel → Landschaft vs. Blütennahaufnahme → Pflanze) hängt an der Aufnahmedistanz, die das Modell nicht liefert. Nachrüstbar als reine Listen-Änderung, ohne Architektur-Eingriff.

### 5. Remote-Klassifizierung: geschlossenes Antwortschema, strukturell wie inhaltlich validiert

`remote_classification.py` behält Provider-Dispatch, Client-Protokoll, Fehlerklasse und Best-effort-Semantik unverändert (ADR 0032 Punkt 3/5, ADR 0025/0031). Geändert wird das Antwortschema:

```json
{"categories": ["menschen", "sport_aktivitaet"], "labels": ["Geburtstag", "Kuchen"]}
```

- `_PROMPT` wird zu einem Aufruf von `categories.build_classification_prompt()` (Punkt 1) — die Kategorie-Definitionen samt Negativabgrenzung stehen wörtlich im Prompt, weil genau sie die Zuordnung für das Modell eindeutig machen. Der Prompt fordert ausdrücklich **alle in Frage kommenden** Kategorien (maximal drei), nicht eine Rangfolge.
- `RemoteClassification` (`@dataclass(frozen=True)`: `categories: tuple[str, ...]`, `fine_labels: tuple[str, ...]`) ersetzt `list[CategoryLabelDetection]`. **Konfidenzen entfallen ersatzlos** — sie wurden ausschließlich für die Häufigkeits-/Score-Auswahl gebraucht, die es nicht mehr gibt. Eine Zahl zu persistieren, die keinen Codepfad mehr beeinflusst, wäre irreführender Ballast.
- Validierung (`_classification_from_json`), zweistufig:
  - **Strukturell, hart:** fehlt `categories` oder ist es keine Liste → `RemoteCategoryClassificationApiError`, Foto best-effort übersprungen (unverändertes Verhalten).
  - **Inhaltlich, tolerant:** unbekannte Kategoriewerte werden **verworfen** und einmal je Vorkommen auf `WARNING` geloggt (`logging_config.py`-Muster, ADR 0034 — Rohwert ja, keine Bilddaten/Secrets). Ein gelegentliches Synonym des Modells darf das Foto nicht scheitern lassen, und das Verwerfen ist zugleich die Garantie für "Kategorien außerhalb des Sets können nicht mehr entstehen". Mehr als `MAX_REMOTE_CATEGORIES_PER_PHOTO = 3` Einträge werden abgeschnitten.
  - `labels`: optional (fehlend = leer), jedes Element getrimmt, nicht leer, höchstens `MAX_FINE_LABEL_LENGTH = 60` Zeichen; auf `MAX_FINE_LABELS_PER_PHOTO = 2` abgeschnitten. Verletzungen einzelner Einträge verwerfen den Eintrag, nicht das Foto.
- `_MAX_RESPONSE_TOKENS` bleibt `256`.
- **`COST_PER_IMAGE_USD` muss neu verifiziert werden:** der Prompt wächst durch die dreizehn Definitionen samt Negativabgrenzung um grob 500-700 Input-Tokens (Anthropic: +$0,0005-0,0007/Bild bei $1/MTok Input). Der `developer` rechnet den Wert wie bei ADR 0032 Punkt 8 gegen die aktuelle Preisliste nach und schreibt die Herleitung als Kommentar fort, statt die Konstante unverändert zu lassen.

### 6. Feinlabels: bestehende Label-Registry weiterverwenden, Zweck verschoben

Die freien Schlagworte bleiben — als reine Zusatzinformation am Foto (maximal zwei), ohne jede Wirkung auf `PhotoRanking.category_key`. Die dafür bereits gebaute, getestete und bezahlte Infrastruktur aus ADR 0032 Punkt 4 (Normalisierung, exakter Fast-Path, Kosinus-Ähnlichkeit gegen eine kanonische Registry, `label_embedding.py` mit ONNX-Asset nach ADR 0033) wird **unverändert weiterverwendet**, nur mit verschobenem Zweck:

- **Vorher:** Zusammenfassung ähnlicher Label war notwendig, damit eine Kategorie die 15-%-Schwelle erreicht.
- **Jetzt:** Zusammenfassung ähnlicher Label macht die Auswertung "welche Kategorie fehlt im Set?" belastbar — ohne sie stünden "Hund", "Hunde" und "dog" als drei getrennte Einträge in der Häufigkeitsliste und würden das Signal genau dort verwässern, wo es gebraucht wird.

Tabellen werden zur neuen Bedeutung umbenannt (`category_labels` → `fine_labels`, `photo_category_detections` → `photo_fine_labels`, `category_label_id` → `fine_label_id`); `raw_label`/`provider`/`computed_at` und der `UniqueConstraint(photo_id, fine_label_id)` bleiben. `CATEGORY_LABEL_SIMILARITY_THRESHOLD = 0.78` und die kalibrierte Stichprobe bleiben gültig.

**Ausdrücklich erwogen und nicht entschieden:** das Embedding-Modell samt `onnxruntime`/`tokenizers` und dem 113-MiB-Download (ADR 0033) ersatzlos zu streichen und Feinlabels nur noch nach NFKC+casefold zu gruppieren. Das wäre ein spürbarer Vereinfachungsgewinn (Docker-Build, CI, Setup) gegen einen Qualitätsverlust in genau der einen Auswertung, die die Story als Änderungspfad für das Set benennt. Weil diese Abwägung Kosten-/Wartungsfolgen hat und nicht rein technisch ist, wird sie **nicht** in dieser ADR entschieden: der Status quo bleibt (kein Abbau, kein Ausbau), eine spätere Streichung ist eine eigene, kleine ADR ohne Auswirkung auf das hier festgelegte Datenmodell (die Ähnlichkeitsauflösung ist hinter `resolve_canonical_label` gekapselt).

**Anlass-Dimension:** ausschließlich über Feinlabels, kein eigenes Feld, kein eigener Mechanismus. Der Prompt fordert explizit, einen erkennbaren Anlass als Feinlabel zu nennen. Feinlabels werden auch dann festgehalten, wenn die Kategorie `nicht_erkannt` lautet (kein Sonderfall im Code — Kategorie und Labels werden unabhängig voneinander persistiert).

**Sichtbarkeit/Auswertbarkeit:** neuer, rein lesender Endpunkt `GET /projects/{id}/fine-labels` → absteigend nach Häufigkeit sortierte Liste (`canonical_key`, `display_name`, `photo_count`) über die Fotos des Projekts, dargestellt als kompakte Liste in der bestehenden `RemoteCategoryClassificationSection`. Bewusst ein Endpunkt und keine CLI (anders als `category_diff.py`, ADR 0047 Punkt 7): das hier ist keine einmalige Verifikationshilfe, sondern der dauerhafte Änderungspfad für das Set und gehört dorthin, wo der Nutzer den Lauf ohnehin auslöst.

### 7. Datenmodell und Migration

Eine einzige Alembic-Revision, vier Schritte:

- **a) Neue Tabelle `photo_category_classifications`** — 1:1 zu `Photo` (`photo_id` als Primary Key und FK, `cascade="all, delete-orphan"` über `Photo.category_classification`): `category_key: str` (das Ergebnis von `resolve_category` über die *remote* gelieferten Kandidaten), `detected_categories: JSON` (die validierte Kandidatenliste als Audit-Spur — nach der Vorrangauflösung ist "warum landete das Foto hier?" die wahrscheinlichste Frage, und die Antwort ist sonst unwiederbringlich verloren), `provider: str`, `computed_at: datetime`. 1:1 statt 1:N, weil pro Foto genau eine Kategorie entsteht — das ist die Kernaussage der Story, und das Schema soll sie erzwingen statt sie nur zu befolgen.
- **b) Umbenennungen** (Punkt 6): `category_labels` → `fine_labels`, `photo_category_detections` → `photo_fine_labels`, Spalte `category_label_id` → `fine_label_id`, Constraint `uq_category_detection_photo_label` → `uq_fine_label_photo_label`. Reine `RENAME`-Operationen, keine Wertänderung.
- **c) `DELETE FROM photo_fine_labels`** — die bestehenden Zeilen stammen aus dem alten Prompt (bis zu drei Label, andere Fragestellung) und würden die neue Häufigkeitsauswertung mit einer nicht vergleichbaren Grundgesamtheit verwässern. Die Vokabular-Registry `fine_labels` selbst **bleibt erhalten** (reine Wortliste mit teuer berechneten Embeddings, wiederverwendbar). Gedeckt durch "Out of Scope: keine rückwirkende Migration bestehender Kategoriedaten — es gibt keine erhaltenswerten Bestände".
- **d) `UPDATE photo_scores SET category_override = NULL`** — Pflichtschritt, keine Bequemlichkeit: bestehende Overrides tragen Werte des alten offenen Vokabulars (`"landscape"`, `"detail"`, beliebige `canonical_key`s). Ohne diesen Schritt würde `run_criterion_scoring` weiterhin `score.category_override or …` anwenden und damit Kategorien außerhalb des festen Sets erzeugen — ein direkter Verstoß gegen das Akzeptanzkriterium.

**Kein Eingriff in `PhotoRanking`.** Ältere Zeilen behalten ihre alten `category_key`-Werte (ADR 0047 Punkt 6, unverändert fortgeführt): sie sind Laufhistorie, die Kuratierungsansicht liest den jeweils letzten erfolgreichen Lauf, und `category_diff.py` braucht den Vorher-Stand für den Umstellungsvergleich. Bis zum ersten neuen `score-criteria`-Lauf zeigt die Ansicht deshalb noch alte Kategorien — erwartetes, dokumentiertes Verhalten.

### 8. API: das Set kommt vom Server, der Override validiert gegen ein geschlossenes Vokabular

- **Neuer Endpunkt `GET /categories`** (eigener kleiner Router `api/categories.py`, Router-Level-Auth wie `/projects`): liefert das Set in Registry-Reihenfolge (`key`, `display_name`, `definition`, `locally_available: bool`). **Bewusst keine Frontend-Spiegelung des Sets.** Eine zweite, im TypeScript gepflegte Liste wäre eine dauerhaft driftende Kopie; die deutschen Anzeigenamen kommen im Projekt bereits vom Server (`CriterionScoreOut.display_name`), und die Override-Auswahl braucht das vollständige Set unabhängig davon, was für ein Foto erkannt wurde. Das ist der einzige neue Endpunkt, den diese ADR einführt.
- **`PUT /photos/{id}/category-override`** validiert jetzt gegen `is_known_category(payload.category_key)` statt gegen die foto-skopierte Erkennungsmenge. `_photo_category_candidate_keys` entfällt ersatzlos. **Sicherheitsbewertung:** das ist eine Verschärfung, keine Lockerung — vorher war der Wertebereich ein offenes, zur Laufzeit wachsendes Vokabular mit einer Existenzprüfung, jetzt ist er ein geschlossenes, im Code definiertes Set von dreizehn Werten. Die frühere Cross-Photo-Isolation (IDOR-Schutz, ADR 0032 Punkt 6.3) wird damit gegenstandslos: es gibt keinen fotobezogenen Wert mehr, der isoliert werden müsste. `409` bleibt für "keine `PhotoRanking`-Zeile im aktuellen Lauf", `422` für einen unbekannten `category_key`.
- **`PhotoOut`:** `remote_category_labels` → `fine_labels: list[FineLabelOut]` (`canonical_key`, `display_name`, `raw_label`, `provider`), neu `remote_category: str | None` (die remote ermittelte Kategorie, für die Nachvollziehbarkeit am Foto). `category_candidates: list[CategoryCandidateOut]` bleibt, führt aber jetzt ausschließlich Set-Keys (`category_key`, `origin: "local" | "remote"`) — die Liste erklärt, *warum* die Kategorie so ausfiel, sie steuert die Override-Auswahl nicht mehr. `score` entfällt dort ersatzlos (siehe Punkt 5: keine Konfidenzen mehr im Remote-Pfad; für lokale Kandidaten allein wäre die Spalte irreführend halb gefüllt).
- **`_cloud_vision_status_out`** leitet den Remote-Erfolg jetzt aus der Existenz der `photo_category_classifications`-Zeile ab statt aus "mindestens ein Label" — präziser als vorher, weil ein erfolgreich klassifiziertes Foto ohne Feinlabel nicht mehr fälschlich als "nicht gelaufen" erscheint. Ebenso das Skip-Kriterium in `select_remote_category_candidates`.
- Unverändert: `GET /projects/{id}/classify-categories-remote/estimate`, `POST /projects/{id}/classify-categories-remote`, `DELETE /photos/{id}/category-override`, der `cloud_vision`-Consent-Schalter, `remote_category_classification_runs`, `reassign_photo_category`.

### 9. Frontend

Die Oberfläche verwendet durchgängig die deutschen Bezeichnungen des Sets — sie kommen aus `GET /categories` (react-query, langlebiger Cache: das Set ändert sich nur per Deployment).

- `categoryLabels.ts`: `CATEGORY_DISPLAY_NAME_OVERRIDES` entfällt; `formatCategoryKey` schlägt im geladenen Set nach und behält den bisherigen generischen Fallback (Großschreibung) **nur** für Altwerte aus historischen `PhotoRanking`-Zeilen. `categoryAbbreviation` bildet das Kürzel künftig aus dem Anzeigenamen statt aus dem Key (`Gebäude & Bauwerk` → `GEB`, `Nicht erkannt` → `NIC`; für das feste Set kollisionsfrei geprüft).
- `CurateCategoriesPage.tsx::sortCategoryKeys`: sortiert nach der Registry-Reihenfolge aus `GET /categories` statt alphabetisch; `nicht_erkannt` bleibt immer zuletzt, unbekannte Altwerte davor. `CATCH_ALL_CATEGORY_KEY` wird `'nicht_erkannt'`.
- Override-Bedienung: statt "Übernehmen"-Buttons je erkanntem Kandidaten eine Auswahl über **alle** dreizehn Kategorien (die konkrete Bedienform legt der `ux-ui-designer` im UI/UX-Abschnitt der Spec fest — architektonisch verbindlich ist nur: die Auswahl umfasst genau das Set, und die Kandidatenliste bleibt daneben als Erklärung sichtbar).
- Feinlabels als Chips am Foto (Detailansicht/Bewertungsdetails), Häufigkeitsliste in `RemoteCategoryClassificationSection`.

## Begründung

- **Die Vorhersehbarkeit entsteht strukturell, nicht durch Kalibrierung.** Die Kategoriezuweisung wird von einer laufweiten Aggregation zu einer reinen Pro-Foto-Funktion über ein geschlossenes Set. Kein Schwellwert, keine Projektgröße und keine Zusammensetzung des Kandidatenpools kann das Ergebnis mehr verschieben — das war die eigentliche Beschwerde.
- **Die Vorrangreihenfolge gehört in den Code, nicht ins Modell.** Ein LLM, das "die eine dominante Kategorie" wählen soll, trifft diese Entscheidung bei jedem Aufruf neu und nicht reproduzierbar. Das Modell beantwortet deshalb nur die Wahrnehmungsfrage ("was kommt in Frage"), die Regel-Frage ("was gewinnt") beantwortet eine getestete Funktion.
- **Ein Set statt zweier Welten löst eine Lücke auf, die ADR 0032 selbst dokumentiert hatte** (lokales `"people"` vs. remotes `"menschen"`). Lokale und remote Signale sind jetzt zwei Zulieferer derselben Kandidatenmenge — der Grund für die Spezifitätsstufen aus ADR 0047 Punkt 2 (unvergleichbare Skalen) entfällt mitsamt dem Mechanismus.
- **Der Umbau kostet keine zusätzliche Inferenz und keinen zusätzlichen Cloud-Aufruf.** Die beiden neuen lokalen Kategorien entstehen aus einer Modellausgabe, die bereits berechnet und verworfen wurde — dasselbe Vorgehen, mit dem ADR 0047 die Landschafts-Erkennung gewonnen hat. Der einzige Kostenzuwachs ist der längere Prompt (Punkt 5), und der ist der Preis dafür, dass die Zuordnung überhaupt eindeutig genug beschrieben ist.
- **Freie Sprache geht nicht verloren, sie wird nur entmachtet.** Feinlabels behalten die vollständige Ausdruckskraft des offenen Vokabulars aus ADR 0032 — inklusive der Anlass-Dimension, die als Kategorie immer ein Fremdkörper war — und liefern zusätzlich den Änderungspfad für das Set selbst. Das ist der Teil von ADR 0032, der sich bewährt hat, und er bleibt.

## Konsequenzen

- **Sichtbare Verhaltensänderung beim nächsten `score-criteria`-Lauf.** Alle bisherigen Kategorien verschwinden zugunsten des festen Sets; ohne eingeschaltete Remote-Kategorisierung wird "Nicht erkannt" der mit Abstand größte Abschnitt (nur sechs der zwölf Kategorien sind lokal bestimmbar). Das ist die von der Story vorgesehene, ehrliche Darstellung — und zugleich das größte Risiko dieser Entscheidung: der Nutzen des Features hängt für die übrigen sechs Kategorien vollständig an einem kostenpflichtigen Cloud-Lauf. Für die Beurteilung der Umstellung steht `category_diff.py` (ADR 0047 Punkt 7) unverändert bereit.
- **Bestehende manuelle Overrides gehen verloren** (Migration d). Unvermeidbar, da ihre Werte außerhalb des neuen Sets liegen; durch "keine erhaltenswerten Bestände" gedeckt, aber eine reale, einmalige Datenlöschung, die in der Spec und im PR benannt gehört.
- **Ein Set-Wechsel bleibt eine Code-Änderung** (per Story ausdrücklich so gewollt, Konfigurierbarkeit pro Projekt ist Out of Scope). Eine neue Kategorie kostet: ein `CATEGORY_REGISTRY`-Eintrag mit Definition/Negativabgrenzung/Vorrang — Prompt, Override-Auswahl, Kuratierungs-Sortierung und Validierung ziehen automatisch nach. Optional ein `LOCAL_CATEGORY_SIGNALS`-Eintrag, falls ein lokales Signal existiert. Keine Migration.
- **Neue Abhängigkeiten: keine. Neue Secrets: keine. Neue Modell-Assets: keine.** Die `onnxruntime`/`tokenizers`-Abhängigkeit und der ONNX-Download (ADR 0033) bleiben unverändert bestehen — verschoben auf den Feinlabel-Zweck (Punkt 6).
- **`docs/architecture.md`** (Owner: `architect`) wird im Umsetzungs-PR fortgeschrieben: neues Modul `categories.py`, neue Tabelle `photo_category_classifications`, umbenannte Feinlabel-Tabellen, entfallene Ableitungsmechanik, neue Endpunkte. `docs/setup.md` bleibt unberührt (keine neue Umgebungsvariable, kein neuer Setup-Schritt).
- **Ein späterer Wechsel des Grundprinzips** — projektspezifische Sets, Mehrfachzuordnung eines Fotos zu mehreren Kategorien, eine über die Vorrangreihenfolge hinausgehende Konfliktlösung, oder die Rückkehr zu einem offenen Vokabular — bleibt architekturrelevant und braucht eine neue ADR, die diese hier als "Superseded" markiert.
