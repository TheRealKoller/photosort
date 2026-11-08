# 0622 - Eye-Übersetzung v3: definierende Signale statt Gegenstände

**Status:** Accepted
**Erstellt:** 2026-11-08
**Bezug:** Issue [#622](https://github.com/TheRealKoller/photosort/issues/622), ADR
[`0141`](../decisions/0141-eye-uebersetzung-v3-definierende-signale-support.md)

**Umfang:** über dem Richtwert von rund 200 Zeilen, weil fünf geänderte Motivtabellen, die
Support-Bedingung und die Messregel je einzeln nachprüfbar sein müssen; die Tag-Listen sind der
Gegenstand der Story, nicht ihr Beiwerk.

## Ziel

Eye erkennt Motive heute deutlich schlechter als die Cloud-Klassifizierung. In der
Klassifizierungsprüfung 1 (373 Fotos, Cloud Mistral `ministral-3b-2512` gegen Eye `v1.0.0` mit
Übersetzung `eye-4.2.3/v2`) war die Cloud bei den Motiven in 24 von 30 Fällen besser (Eye 6), bei
der Motivstärke in 19 von 30 (Eye 11). Wo die Cloud besser war, hatte Eye zusätzlich `aktivitaet`
(9), `stadt_strasse` (6), `detail_stimmung` (6), `tiere` (6) und `landschaft` (4); nur bei 37 von
373 Fotos stimmen die Motivmengen überein. `aktivitaet` stuft Eye regelmäßig hoch ein (0,54–0,93),
wo keine Tätigkeit zu sehen ist; sechsmal erkennt Eye Tiere, wo keine sind.

Ursache ist die Max-Regel über Tag-Listen, die auch Gegenstände und Umgebungssignale enthalten:
ein parkendes Rad belegt Tätigkeit, ein Auto im Grünen „Stadt/Straße“, Himmel belegt Landschaft.
Die neue Fassung `eye-4.2.3/v3` zählt deshalb nur **definierende** Signale je Motiv und verlangt
für `aktivitaet` zusätzlich ein Personensignal. Dokument-Ausschluss und Albumstufe bleiben
wertgleich mit v2.

## User Story

Als Nutzer von PhotoSort möchte ich, dass Eye die Motive meiner Fotos und deren Stärke mindestens
so gut erkennt wie die Cloud-Klassifizierung, damit ich künftig ohne Cloud auskommen kann — ohne
dass Fotos den Server verlassen und ohne Kosten.

## Akzeptanzkriterien

- [ ] Es gibt eine neue Eye-Übersetzungsfassung. Die bisherigen Fassungen bleiben aufrufbar, die
  Klassifizierungsprüfung bietet alle an, und bestehende Eye-Ergebnisse behalten ihre Fassung.
- [ ] Die neue Fassung vergibt weniger überzählige Motive als v2, gemessen auf denselben Fotos wie
  Prüfung 1 — für `aktivitaet`, `stadt_strasse`, `detail_stimmung`, `tiere` und `landschaft`
  jeweils einzeln. Ein Foto ohne erkennbare Tätigkeit erhält bei `aktivitaet` keine hohe Stärke.
- [ ] Die Verbesserungen gelten allgemein für Motive und nicht für einzelne, aus Prüfung 1
  bekannte Fotos.
- [ ] Dokument-Ausschluss und Album-Stufe liefern in der neuen Fassung für jedes Foto dieselben
  Werte wie in v2.
- [ ] Eine Bestätigungsprüfung vergleicht Eye mit der neuen Fassung gegen die Cloud mit demselben
  Modell wie in Prüfung 1 (`ministral-3b-2512`), und zwar im Projekt von Prüfung 1 und in einem
  zweiten Projekt, dessen Fotos nicht zur Entwicklung der neuen Fassung herangezogen wurden. Jeder
  vorgelegte Fall der Zwecke „Motive“ und „Motivstärke“ ist beurteilt, keiner bleibt offen.
- [ ] Erfolgsmaß: In beiden Projekten gilt für „Motive“ und für „Motivstärke“ jeweils einzeln,
  dass die Fälle „Eye besser“ mindestens so viele sind wie die Fälle „Cloud besser“. „Beide ok“ und
  „beide falsch“ zählen dabei nicht.
- [ ] Das Ergebnis ist nachvollziehbar festgehalten: Seiten beider Prüfungen, Urteilszählungen je
  Zweck und Projekt, Prüfung 1 als Ausgangswert, und ob das Erfolgsmaß erreicht wurde. Die Story
  ist auch dann abgeschlossen, wenn das Erfolgsmaß verfehlt wird; dann hält das Ergebnis fest, dass
  eine Kombination beider KIs als Folge-Story zu prüfen ist.
- [ ] Am laufenden Betrieb ändert sich nichts: Cloud-Ergebnisse, Album-Entwurf, Albumtauglichkeit
  und die Auswahl, welche Fotos an die Cloud gehen, bleiben unverändert; kein zusätzlicher
  Datenabfluss durch Eye.

## Datenmodell-Bezug

Kein Schemawechsel, keine Migration. `photo_eye_results.mapping_version` ist ein String ohne Enum
und trägt die neue Fassung; bestehende Zeilen behalten ihre. Kein neues Feld an einer Tabelle, kein
neuer Endpunkt. Siehe [`docs/architecture.md`](../../docs/architecture.md), „Eye-Sidecar“ und
„Klassifizierungsprüfung“.

## Architektur / Umsetzung

Entscheidung: ADR [`0141`](../decisions/0141-eye-uebersetzung-v3-definierende-signale-support.md).
Kein Schemawechsel, keine Migration, kein neuer Endpunkt; `selection.py`, der Sidecar und alle
Cloud-/Album-Pfade bleiben unverändert.

**Fassungen.** `eye_mapping.py` registriert v3 als dritten Eintrag; v2 bekommt die eigene Konstante,
die es bisher nicht brauchte, weil es die Lauf-Fassung war:

```python
MAPPING_VERSION_V1: Final = "eye-4.2.3/v1"
MAPPING_VERSION_V2: Final = "eye-4.2.3/v2"   # bisheriger Laufwert, bleibt wörtlich
MAPPING_VERSION: Final = "eye-4.2.3/v3"      # Lauf-Fassung

MAPPINGS = {v1: MAPPING_V1, v2: MAPPING_V2, v3: MAPPING_V3}
```

`MAPPING_V1` und `MAPPING_V2` bleiben wertgleich (Tabellen, Ausschluss, Feinlabel-Filter,
Albumbänder, `tag_confidence`). `MAPPING_V3` erbt `EXCLUDED_TYPES_V2`, `DOCUMENT_TYPES`,
`ALBUM_LEVELS`, `TAG_CONFIDENCE` und `motif_detections={"tiere": "pets"}`. `analyze(payload,
version)` behält den Pflichtparameter und `EyeMappingError` bei unbekannter Fassung;
`_RUN_MAPPING` bleibt `MAPPINGS[MAPPING_VERSION]`.

**Definierende Signale (v3).** Ein Tag belegt ein Motiv nur, wenn er das Motiv selbst benennt.
Gegenstände sind nie Beleg; Örtlichkeiten und Umfeld nur, wo das Gate die Person liefert;
Oberbegriffe ohne Art entfallen bei `tiere`. Unverändert bleiben `menschen`,
`bauwerk_sehenswuerdigkeit` und `essen_trinken` (dieselben Tupel wie v2):

```python
MOTIF_TAGS_V3: Final = {
    **MOTIF_TAGS_V2,
    "landschaft": (
        "beach", "field", "forest", "grassland", "hill", "lake", "landscape",
        "mountain", "mountain_range", "ocean", "river", "sea", "shore", "coast",
    ),
    "stadt_strasse": (
        "street", "road", "city", "town", "sidewalk", "traffic_light", "street_light",
        "traffic_sign", "pedestrian", "cityscape", "metropolis", "metropolitan_area",
        "urban_area", "neighbourhood", "skyline",
    ),
    "detail_stimmung": ("flower", "leaf", "blossom"),
    "tiere": (
        "antelope", "bear", "bee", "beetle", "bird", "black_cat", "border_collie",
        "bulldog", "butterfly", "cat", "cattle", "deer", "dog", "dolphin", "dragonfly",
        "duck", "eagle", "elephant", "english_cocker_spaniel", "falcon", "fish", "frog",
        "giraffe", "goat", "golden_retriever", "goose", "harbor_seal", "horse", "insect",
        "labrador_retriever", "lion", "lizard", "maine_coon", "marine_mammal", "monkey",
        "norwegian_forest_cat", "owl", "parrot", "penguin", "pig", "poodle", "pug",
        "rabbit", "reptile", "sea_lion", "sheep", "siamese", "snake", "spider",
        "squirrel", "swan", "tiger", "turtle",
    ),
    "aktivitaet": (
        "swimming", "ski", "surfing", "basketball_sport", "tennis", "hiking", "walking",
        "running", "cross_country_running", "ultramarathon",
        "track_and_field_athletics", "skiing", "snowboarding", "ice_skating",
        "water_skiing", "cycle_sport", "racing_bicycle", "dance", "playground", "sports",
        "volleyball_sport", "baseball_sport", "american_football", "golf", "hockey",
        "bowling", "canoe",
    ),
}
```

Alle Tags sind gegen `eye/node_modules/@desert-ant-labs/eye/tags.js` verifiziert; `dinosaur`,
`shellfish`/`crab` und `persian` bleiben draußen (Spielzeug, Lebensmittel, Mehrdeutigkeit).

**Support-Bedingung.** `EyeMapping` erhält als letztes Feld
`motif_support: Mapping[str, tuple[str, ...]]`; v1/v2 führen eine leere Abbildung, v3 genau:

```python
MOTIF_SUPPORT_V3: Final = {
    "aktivitaet": (
        "people", "person", "man", "woman", "boy", "girl", "child", "crowd",
        "human_face", "portrait", "group_shot", "selfie", "adolescent", "baby",
        "toddler", "senior_citizen",
    ),
}
```

In `motif_strengths` nach der Max-Regel, vor dem Schreiben des Werts:

```python
support = mapping.motif_support.get(motif_key)
if support is not None and not any(
    _confidence(tags.get(tag)) >= mapping.tag_confidence for tag in support
):
    strength = 0.0
```

**Was gilt:** Hat ein Motiv einen Eintrag, zählt es nur, wenn mindestens ein Support-Tag
`tag_confidence` erreicht; sonst `0.0`. Die Stärke bleibt das Maximum der Motivsignale (Tags und
`pets`), der Support hebt sie nicht an. Die Schwelle ist `tag_confidence` (inklusiv, gleicher
Operator wie `fine_labels`); eine eigene Support-Zahl gibt es nicht.
`EYE_PURPOSE_MAPPING["purposes"]["motivstaerken"]` erhält `"support"` und `"support_threshold"`;
`"signals"` bleibt `("tags", "pets")`. Die Präsenz entscheidet weiter allein
`selection.py::motif_is_present`.

**Fehlende und ungültige Werte.** Dieselbe Sicherheitsstufe wie v2: fehlende oder
nicht-mappingförmige `tags` → `{}` → alle acht Stärken `0.0`, Gate geschlossen. Ein Support-Wert,
der fehlt, Text, `bool`, NaN, ±unendlich oder eine Ganzzahl jenseits des float-Bereichs ist, ergibt
über `_confidence` 0 und schließt das Gate, ohne den Lauf abzubrechen; endliche Werte werden auf
[0, 1] geklemmt. Der Vergleich ist inklusiv (`0.5` öffnet bei `tag_confidence = 0.5`). Ein leerer
Support-Eintrag und ein Support-Schlüssel außerhalb `MOTIF_REGISTRY` sind unzulässig; je ein Test
hält das fest. Kein neuer Fehlertyp.

**Pins.** `eye/src/pins.json::mappingTags` ist die sortierte Vereinigung der `motif_tags` **und**
`motif_support`-Werte aller Fassungen; `_all_table_tags()` in `test_eye_mapping.py` zieht beide
Quellen ein. Ein umbenannter Support-Tag fiele sonst still aus und schlösse das Gate dauerhaft.

**Messbarkeit der Übervergabe (AK 2).** `deviating` ist richtungslos; die Richtung kommt additiv
in die Merkmalszählung:

```python
class MotifCounts(NamedTuple):
    compared: int
    matching: int
    deviating: int
    a_only: int     # nur Seite A hält das Motiv für vorhanden
    b_only: int     # nur Seite B
```

`Comparison.motif_counts` wird `Mapping[str, MotifCounts]`; die Richtung entsteht im selben
Durchlauf wie `motif_units` über `motif_present` (eine Herleitung). `PurposeCounts` und
`counts_by_purpose` bleiben unverändert; die Übersicht (`ReviewPurposeCountsOut`) führt die
Richtung nicht, das Frontend bleibt unberührt. Der Export führt je Merkmal sechs Schlüssel
(`compared`, `matching`, `deviating`, `a_only`, `b_only`, `presented`); `_EXPORT_KEYS` bekommt eine
eigene Menge `"motif_counts"`, `_guard_export_shape` prüft sie. Der Export rechnet aus den
**gespeicherten** Ergebnissen, damit wird auch der Export einer alten Prüfung nachträglich
richtungsscharf.

**Messweg (AK 2, AK 5–7).** 1. Export von Prüfung 1 (v2 gegen Cloud) neu abrufen: `a_only` bzw.
`b_only` der Eye-Seite ist v2-Über- bzw. Untervergabe je Motiv. 2. Bestätigungsprüfung im Projekt
von Prüfung 1 mit A = Eye v3, B = Cloud `ministral-3b-2512`; `a_only` ist v3-Übervergabe. 3. AK 2
gilt je Motiv, wenn v3-`a_only` ≤ v2-`a_only` für die fünf Motive auf demselben Fotobestand;
maßgeblich ist die eingefrorene Ergebnismenge von Prüfung 1, weicht der heutige
Ausschuss-Überlebendenbestand ab, wird auf die Schnittmenge eingeschränkt (einmalige Auswertung,
kein Endpunkt). Ein kostenfreier Lauf A = Eye v2, B = Eye v3 (ein Sidecar-Aufruf je Foto) zeigt die
Gesamtrichtung als Gegenprobe, trennt aber nicht Über- von Untervergabe.

Ausgangswert, aus den beurteilten Fällen des Exports von Prüfung 1 nachgerechnet (nur die Fälle, in
denen die Cloud besser war; Zahlen sind Fälle, nicht Fotos):

| Motiv | Eye zusätzlich (Motivmengen) | Eye zusätzlich (Stärke) | Cloud zusätzlich (Motivmengen) | Cloud zusätzlich (Stärke) |
|---|---|---|---|---|
| `aktivitaet` | 9 | 7 | 2 | 1 |
| `stadt_strasse` | 6 | 0 | 0 | 1 |
| `detail_stimmung` | 6 | 2 | 3 | 1 |
| `tiere` | 6 | 0 | 2 | 0 |
| `landschaft` | 4 | 4 | 0 | 0 |

Die Spalte „Motivmengen“ entsteht aus `a`/`b` der Zwecke-Fälle, „Stärke“ aus den
`motif_feature`-Fällen mit der Präsenzgrenze 0,5; beide Werte sind damit ohne Datenbank aus der
Exportdatei reproduzierbar. Der gezeigte Bestand ist der gedeckelte (je Zweck 30 Fälle); die
Gesamtrichtung über alle Fotos liefert erst der neue Zähler.

**Reihenfolge.** 1. `eye_mapping.py` (Konstanten, Tabellen, Feld, `motif_strengths`,
`EYE_PURPOSE_MAPPING`) mit `test_eye_mapping.py`. 2. `eye/src/pins.json` und `_all_table_tags()`;
`npm test` in `eye/`. 3. `classification_comparison.py` (`MotifCounts`, Richtung) und Export mit
`test_classification_comparison.py` und `test_api_classification_reviews.py`. 4. Prüfpfad- und
Worker-Tests (keine Produktionsänderung). 5. `docs/architecture.md`. 6. Messläufe (kein Code).

### Teststrategie

Alle Eye-Tests laufen mit synthetischen `toJSON()`-Payloads und Fake-Eye-Client; kein Test
erreicht ein Modell oder ein Netz (die Socket-Sperre aus `conftest.py` gilt unverändert). Weil die
Inferenz selbst ungeprüft bleibt, hängt die Aussagekraft an zwei Regeln, die die Gliederung
durchhält:

1. **Jede Fassung wird gegen ihre eigene Tabelle geprüft.** Ein Defekt-Test, dessen Tag in der
   geprüften Fassung gar nicht vorkommt, besteht aus dem falschen Grund — er belegt dann nichts.
2. **Test und Messlauf werden getrennt.** AK 2, 5, 6 und 7 sind Messungen an echten Fotobeständen
   und Urteilen; dafür gibt es oben den Abschnitt „Messweg“, und kein Testfall gibt vor, sie zu
   erledigen.

**`test_eye_mapping.py` (Unit — reine Funktionen von Payload und Fassung)**

- **Definierende Signale (`TestTheDefiningSignalsInV3`).** Je entfallenem Tag allein → 0 für sein
  Motiv (`bicycle`/`football`/`soccer`/`skateboard`; `car`/`bus`/`building`; `sky`/`cloud`/
  `sunset`/`water`; `furniture`; `animal`/`pet`/`wildlife`), je hinzugekommenem allein → > 0. Dazu
  die **Tabellendifferenz als geschlossene Menge**: je geändertem Motiv `set(V2) - set(V3)` und
  `set(V3) - set(V2)` gegen ein Literal. Die namentliche Prüfung fängt die falsche Zuordnung, die
  Mengendifferenz fängt den stillen Verlust eines Tags, den niemand namentlich erwartet (`hiking`
  fiele aus der Aktivität, alle benannten Tests blieben grün). Ein Sweep über **alle** Tags der
  v3-Tabellen hält jede Zeile lebendig — bei `aktivitaet` mit erfülltem Gate im selben Payload,
  sonst prüfte der Sweep die Support-Regel statt der Tabelle. `pets` trägt `tiere` in v3 weiterhin
  allein (0,7 ohne Tag) und wird nicht gegatet.
- **Support (`TestTheActivitySupportInV3`).** Aktivitätstag ohne Person → 0; Aktivitätstag 0,5 mit
  Person 0,9 → **0,5** (nicht 0,9: der Support hebt nicht an und die Person ist kein
  Motivsignal); Person bei 0,49 → 0, bei 0,5 → > 0 (inklusiv, derselbe Operator wie
  `fine_labels`); Support 1,4 öffnet (geklemmt), -0,4 schließt; defekte Support-Werte (`"hoch"`,
  `True`, NaN, ±inf, `10**400`) → 0 ohne Ausnahme, und ein defekter Eintrag verdeckt einen gültigen
  neben sich nicht; `tags` fehlt oder ist keine Abbildung → alle acht 0,0; `pets` erfüllt das Gate
  nicht; in v2 bleibt der Aktivitätstag allein > 0; `menschen` ist nicht gegatet.
- **Unverändertes (`TestTheUnchangedPartsOfV3`) — der AK-4-Nachweis.** Für `menschen`,
  `bauwerk_sehenswuerdigkeit` und `essen_trinken` sind die Tupel **dieselben Objekte** wie in v2
  (`is`, nicht nur `==`); `excluded_types`, `fine_label_excluded`, `album_levels` und
  `tag_confidence` ebenso. Diese Identität schließt den ganzen Payload-Raum, weil `is_excluded`,
  `album_level` und `fine_labels` reine Funktionen genau dieser Felder sind. Darüber die
  Differenzprüfung als Regressionsschutz gegen einen künftigen Fassungs-Zweig im Code: für jeden
  `kind` aus `DOCUMENT_TYPES` plus unbekannt/fehlend/nicht-textuell dasselbe Ausschlussergebnis,
  für `aesthetic` an jeder Bandgrenze (0,0/0,2/0,4/0,6/0,8/1,0, je knapp darunter), außerhalb der
  Skala und in den Fehlerfällen (fehlendes `scores`, nicht-numerisch → beide Fassungen werfen
  `EyeMappingError`) dieselbe Stufe, und ein Payload mit allen Tabellen-Tags liefert dieselben
  Feinlabels.
- **Struktur (`TestTheMotifStrengths`).** Die beiden Registry-Tests laufen über `motif_tags` **und**
  `motif_support`; ein Test verbietet leere Support-Listen und Support-Schlüssel außerhalb
  `MOTIF_REGISTRY`; ein Test verbietet, dass ein Support-Tag zugleich Motivtag desselben Motivs ist
  (das Gate wäre selbst-erfüllend); ein Test hält fest, dass v1 und v2 eine leere Support-Abbildung
  führen. `_all_table_tags()` zieht beide Quellen ein.
- **Fassungen (`TestTheWholeMapping`).** `MAPPING_VERSION == "eye-4.2.3/v3"`,
  `MAPPING_VERSION_V2 == "eye-4.2.3/v2"`, `list(MAPPINGS)` in Reihenfolge v1/v2/v3,
  `MAPPINGS[MAPPING_VERSION] is MAPPING_V3`; die veröffentlichte Beschreibung ist v3 samt
  `support` (dasselbe Objekt) und `support_threshold == MAPPING_V3.tag_confidence`, `signals`
  bleibt `("tags", "pets")`; `analyze` ohne Version wirft, unbekannte Fassung wirft.
  `TestTheVersionedMappings` nennt v2 dabei über `MAPPING_VERSION_V2`, nie über `MAPPING_VERSION` —
  sonst prüfte der Test nach der Umstellung v3 gegen v3.
- **Pins (`TestTheTagsAgainstTheSidecarPins`).** Die Vereinigung **beider** Quellen aller Fassungen
  gegen `eye/src/pins.json::mappingTags`, plus die Zusicherung, dass die Personensignale in den
  Pins stehen: würden Pins und Helfer gemeinsam nicht nachgezogen, wären beide Seiten gleich falsch
  und der Test bestünde leer. `eye/test/tags.test.js` prüft dieselbe Vereinigung gegen das
  SDK-Vokabular (keine Änderung dort).

**Anzupassende Bestandstests (Verschärfung, keine Abschwächung).** `_BOTH` bleibt v1/v2 und wird
**nicht** um v3 erweitert: `test_a_tag_that_two_motifs_share_counts_for_both` (`building`) und
`test_unknown_tags_and_non_numeric_values_do_not_leak_into_the_vector` (`sky`) tragen für v3
nicht mehr. Für v3 laufen die Regeltests über eine eigene Parametrisierung, deren Payload-Tags aus
der v3-Tabelle stammen (`mountain` statt `sky`). Jedes Literal, das die **Lauf**-Fassung festhält,
wandert auf v3; Literale, die eine **gespeicherte** Alt-Zeile festhalten, bleiben.

**`test_classification_comparison.py` (Unit — reine Zählfunktion):**
`TestTheDirectionOfAMotifDeviation` prüft `a_only`/`b_only` je Motiv mit **beiden Richtungen im
selben Foto** (eine verwechselte Summe bestünde die Invariante sonst); `a_only + b_only ==
deviating`; Übereinstimmung → 0/0; eine Schlüsselmenge, die nur eine Seite führt, zählt als
`a_only` (fehlende Zeile = „nicht vorhanden“, wie im Lesepfad); zwei Werte **unter** der
Präsenzgrenze (0,4/0,3) ergeben keine Abweichung und kein `a_only` — die Richtung entsteht aus
`motif_present`, nicht aus `strength > 0`; Grenzfall 0,5 gegen 0,4999 kippt die Richtung;
`PurposeCounts` bleibt das 3-Tupel.

**`test_api_classification_reviews.py` (API-Integration, echte In-Memory-DB):** Optionsliste
`[v1, v2, v3]` in Reihenfolge; eine Prüfung mit zwei Eye-Seiten **verschiedener** Fassung (v2 gegen
v3) → 201, während die gleiche Fassung zweimal weiterhin 422 ist; Export: `counts_by_purpose` vier
Schlüssel, `counts_by_motif` sechs, und die Merkmalsaufschlüsselung eines ohne Richtung angelegten
Bestands zeigt die Richtung — der Export rechnet aus den gespeicherten Stärken. Formwächter: lehnt
ein Merkmalsblock ohne `a_only`/`b_only` ab und ebenso einen Zwecksblock, der die beiden trägt;
`"motif_counts"` ist eine eigene Menge, `"counts"` bleibt vier Schlüssel.

**`test_worker_classification_review.py` (Worker-Integration, echte DB, Fake-Sidecar):** zwei
Eye-Seiten v2 und v3 auf einem Payload mit Aktivitätstag ohne Person → genau **ein** Dienstaufruf je
Foto, gespeicherte `aktivitaet`-Stärken 0,9 (v2) und 0,0 (v3). Dazu: ein Foto, das eine Fassung
nicht beantworten kann (fehlendes `scores`), hinterlässt **keine** Zeile auf einer der beiden
Seiten und zählt als `unclassifiable_photo_count`, nie als halbes Vergleichspaar.

**`test_worker_eye_phase.py`:** Schattenzeile trägt v3; ein neuer Lauf ersetzt eine v1-Zeile durch
die Lauf-Fassung — der Payload dieses Tests trägt dafür ein Signal, das v3 noch liest (`pet` ist
entfallen, eine benannte Art oder `pets` zeigt dieselbe Aussage); Ausschluss weiter über die
`kind`-Menge.

**`test_demo_state.py`:** die Demo-Eye-Zeile trägt die Lauf-Fassung — über die Konstante, nicht über
ein zweites Literal.

**Bewusst unverändert:** `test_api_photos.py` und `project_graph.py` (Literale sind gespeicherte
Alt-Ergebnisse), `test_migration_eye_mapping_version.py` (Migrationshistorie), die Auswahl-,
Album- und Cloud-Kandidatentests (AK 8: unberührte Pfade behalten ihre Testknoten unverändert und
grün), Frontend-Tests (Fixtures mit v1/v2; die Komponenten rendern jede gelieferte Option).

**Bekannte Grenzen.** (1) Ob die falschen Tierfunde aus den entfallenen Oberbegriffen oder aus
`pets` kamen, ist aus den gespeicherten Stärken nicht entscheidbar; bleibt die Übervergabe, ist
`pets` eine weitere Fassung. (2) Ein Vergleich zweier Eye-Fassungen belegt die Wertgleichheit von
Ausschluss und Albumstufe am beantworteten Bestand: ein Foto ohne gültiges `scores` fällt auf
beiden Seiten heraus und erscheint in dieser Zählung nicht. (3) Die Erfolgsaussage hängt an
menschlichen Urteilen; der Export kann `open == 0` belegen, nicht die Richtigkeit des Urteils.

## UI/UX

Sichtbare Oberfläche: **ja, aber ohne neue Darstellung.** v3 ist ein weiterer Wert in bereits
gerenderten Listen; keine Produktivdatei im Frontend ändert sich, kein neuer Baustein, kein Token,
keine Namens- oder Kürzeltabelle.

- **Anlegen-Panel:** `GET …/options` liefert v3 als dritten `eye_mappings`-Eintrag; er erscheint als
  weitere vollbreite Radio-Zeile im Muster „Wegwahl ohne Vorgabe“ (`min-h-11`, bestehende
  Herkunftszeile „Eye · eye-4.2.3 · Übersetzung eye-4.2.3/v3“, darunter „kostenfrei“). Die
  Reihenfolge bleibt die des Servers (v1, v2, v3 — angehängt statt umsortiert), es bleibt bei
  **keiner Vorauswahl** und ohne Kürzel; die Zeile bricht um (`break-words`) statt abzuschneiden,
  deshalb trägt sie die volle Fassungsangabe auch bei drei Optionen.
- **Prüf-Übersicht und Fallansicht:** unverändert — die A/B-Marke trennt Seiten, nicht Fassungen
  (neutraler Buchstabe, keine Seitenfarbe); die beim Anlegen eingefrorene Herkunftszeile zeigt v3
  als Rohwert. Keine „neu“-Marke, keine zusätzliche Fassungsspalte.
- **Eye-Band der Einzelbildansicht:** unverändert — `mapping_version` steht dort bereits als
  Rohwert („Übersetzung eye-4.2.3/v3“), eine Namenstabelle gibt es nicht.
- **Export:** `a_only`/`b_only` sind Dateiinhalt, keine Oberfläche; Export-Knopf und fester
  Begleitsatz bleiben wörtlich.
- **Design-System:** keine Ergänzung — „Wegwahl ohne Vorgabe“, die vollständige Herkunftszeile und
  „kostenfrei“ tragen den Fall. Die Zahl der Optionen ist kein Systemwert.

## Security

Sicherheitsrelevant an zwei Berührungspunkten, kein Blocker; **keine neue Vertrauensgrenze**: kein
neuer Endpunkt, Empfänger oder Dienstaufruf, kein Secret, kein Frontend-Code.

- **S1 — Das Gate schließt, es öffnet nicht.** `motif_support` liest nur Tag-Konfidenzen über
  dieselbe `_confidence` wie jeder Motivbeleg: fehlend, Text, `bool`, NaN, ±unendlich und
  Ganzzahlen jenseits des float-Bereichs ergeben 0, der Vergleich ist inklusiv, endliche Werte
  werden wie bisher geklemmt. Ein Fremdwert kann das Gate damit weder öffnen noch den Lauf
  abbrechen; der `except`-Kreis des Prüflaufs bleibt unverändert. **Bei Verletzung** öffnete ein
  `>=` auf dem ungeprüften Rohwert die Bedingung für Text und `bool`.
- **S2 — Die Support-Tabelle ist Code, nicht Eingabe.** Schlüssel und Tags sind Modulkonstanten
  über eine feste Liste, als `MappingProxyType` geführt; leere Einträge und Schlüssel außerhalb
  `MOTIF_REGISTRY` sind verboten, `pins.json` umfasst Motiv- **und** Support-Tags. **Bei
  Verletzung** schließt ein Tippfehler das Gate dauerhaft und still: `aktivitaet` fällt aus jedem
  Ergebnis und aus der Endauswahl.
- **S3 — Der Export bleibt Positivliste mit eigener Knotenform.** `a_only`/`b_only` sind zwei ganze
  Zahlen je Merkmal (`a_only + b_only == deviating`) und gröber als der Bestand, der je
  abweichendem Foto bereits beide Präsenzmengen trägt — kein Foto, keine Id, keine Person. **Bei
  Verletzung** ließe ein erweitertes `"counts"` den Zweck-Knoten sechs Schlüssel tragen; die
  **eigene** Menge `"motif_counts"` hält den Wächter scharf.

## Entscheidungen

- **Gate statt Schwelle, dritte Fassung neben v1/v2** (architect): `motif_support` als
  Konjunktion, Support-Schwelle = `tag_confidence`, Präsenz bleibt allein in `selection.py`;
  `MotifCounts` als eigener Typ statt Feldern an `PurposeCounts`. ADR
  [`0141`](../decisions/0141-eye-uebersetzung-v3-definierende-signale-support.md).
- **Tag-Auswahl** (architect, gegengeprüft): Gegenstände nie Beleg, Örtlichkeiten nur mit
  Personengate, Oberbegriffe bei `tiere` durch benannte Arten ersetzt; `playground`/`sports`
  bleiben. Alle 154 Tags gegen das gepinnte Vokabular (611 Tags) geprüft.
- **Sichtbare Oberfläche** (ux-ui-designer): ja, aber ohne neue Darstellung — dritte Radio-Zeile in
  Serverreihenfolge, keine Vorauswahl, keine „neu“-Marke, keine Änderung am Design-System.
- **Export-Richtung** (security-engineer): eigene Schlüsselmenge `"motif_counts"`, `"counts"`
  bleibt vier Schlüssel; `motif_support` als `MappingProxyType`; Pins und `_all_table_tags` sind
  sicherheitstragend. Keine neue Vertrauensgrenze; die Schlüsselliste im Sicherheitskonzept ist
  nachgezogen.
- **Tests** (test-engineer): wertgleiches Erbe über Objektidentität (nicht Stichproben),
  Tag-Tabellen als Mengendifferenz, Gate-Invarianten; AK 2/5/6/7 sind Messläufe, als benannte
  Lücke im Testkonzept geführt.
- **Ausgangswert** (eigene Entscheidung): die Prüfung-1-Zahlen je Motiv werden aus den beurteilten
  Fällen des Exports nachgerechnet und in dieser Spec festgehalten, damit AK 2 ohne Datenbank
  vergleichbar bleibt.
- Keine Produktentscheidung nötig, keine Konsultation übersprungen.

## Offene Fragen

Keine.

## Out of Scope

- Umstellung des laufenden Betriebs von Cloud auf Eye; Kombination beider KIs (nur als Folge-Story,
  falls das Erfolgsmaß verfehlt wird).
- Bewertung der Albumstufe und des Dokument-Ausschlusses; beide bleiben wertgleich mit v2 und sind
  eigene Stories ([#624](https://github.com/TheRealKoller/photosort/issues/624),
  [#625](https://github.com/TheRealKoller/photosort/issues/625)).
- Neubewertung bestehender Eye-Ergebnisse: sie behalten ihre Fassung, bis ein neuer Eye-Lauf
  darüberläuft.
- Feinlabels-Vergleich zwischen Eye und Cloud (Vokabulare sind nicht vergleichbar).
