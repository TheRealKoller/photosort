# 0283 - Gebäude-Allow-Liste läuft nicht mehr ins Leere

**Status:** Accepted
**Erstellt:** 2026-09-25
**Bezug:** [Issue #283](https://github.com/TheRealKoller/photosort/issues/283)

## Ziel

Das Kriterium „Gebäude" übersieht seit seiner Einführung bestimmte Bauwerkstypen vollständig: Fotos
von Hängebrücken, Leuchttürmen, Glockentürmen und Triumphbögen werden nicht als Gebäude erkannt und
zählen damit nicht zum Motiv „Bauwerk und Sehenswürdigkeit". Der Grund liegt in der Liste, die
festlegt, welche vom Bilderkennungsmodell gelieferten Bezeichnungen als „Gebäude" gelten — vier
Einträge dieser Liste entsprechen keiner Bezeichnung, die das Modell tatsächlich ausgibt, und können
deshalb nie zutreffen. Bei dreien weicht nur die Schreibweise ab (Unterstrich statt Leerzeichen),
beim vierten trägt die Klasse einen anderen Namen (Leuchtturm: `beacon` statt `lighthouse`).

Bei der Gelegenheit fällt auf, dass die Liste auch Bauwerksarten auslässt, die sie nach ihrer eigenen
Logik enthalten müsste — Hängebrücken und Viadukte zählen als Gebäude, Stahlbogenbrücken dagegen
nicht. Die Liste wird deshalb nicht nur repariert, sondern einmal vollständig überarbeitet, und die
Fehlerklasse wird dauerhaft ausgeschlossen.

## User Story

Als jemand, der einen Urlaubsordner sortiert, möchte ich, dass Fotos von Bauwerken zuverlässig als
Gebäude erkannt werden — auch Leuchttürme, Brücken und ähnliche Bauwerke im Freien —, damit ich sie
in der Kuratierung dort wiederfinde, wo ich sie erwarte, statt sie einzeln von Hand nachziehen zu
müssen.

## Akzeptanzkriterien

- [ ] **AK1 — Die vier toten Einträge treffen.** `ARCHITECTURE_CATEGORIES` enthält `beacon`,
      `bell cote`, `triumphal arch` und `suspension bridge` statt `lighthouse`, `bell_cote`,
      `triumphal_arch` und `suspension_bridge`. Ersetzung, keine Streichung: Alle sechzehn
      bisherigen Bauwerksarten bleiben inhaltlich erhalten.
- [ ] **AK2 — Sechs Bauwerksarten kommen hinzu.** `steel arch bridge`, `water tower`, `dam`, `pier`,
      `fountain` und `planetarium` stehen in der Liste; jede ist in der Label-Datei des Assets
      nachgewiesen. Stand danach: 22 Einträge.
- [ ] **AK3 — Das Aufnahmekriterium steht schriftlich, jede Aufnahme ist daran begründet.** Maßstab:
      ein eigenständiges Bauwerk im Außenraum, das als Motiv für sich steht. Nicht aufgenommen
      werden Innenräume, Ladeneinrichtungen und einzelne Bauteile wie Dächer, Mauern oder Zäune. Im
      Zweifel wird eine Bauwerksart weggelassen statt aufgenommen. Die geprüften und verworfenen
      Kandidaten stehen namentlich mit Ablehnungsgrund im Kommentar über der Liste.
- [ ] **AK4 — Kein Eintrag einer kuratierten Allow-Liste läuft ins Leere, und das bleibt so.** Ein
      automatischer Test schlägt fehl, sobald ein Eintrag einer der fünf kuratierten Allow-Listen
      keiner Bezeichnung entspricht, die das zugehörige Modell-Asset in seiner Label-Datei führt. Er
      nennt dabei Liste, Eintrag und Asset. Die Prüfrichtung ist Liste ⊆ Label-Datei, nicht
      Gleichheit. Ein Wächter hält zusätzlich fest, dass eine künftig hinzukommende kuratierte Liste
      nicht ungeprüft bleibt.
- [ ] **AK5 — Die Innenraum-Lücke bleibt bestehen und wird nicht als behoben dargestellt.**
      `living_room`, `kitchen`, `office` werden von ImageNet-1k strukturell nicht erkannt; die
      Überarbeitung nimmt keine Innenraum-Klasse auf und führt die Lücke im Kommentar unverändert
      als bewusst akzeptiert.
- [ ] **AK6 — Die Verhaltensänderung ist auf Regel-Ebene belegt, bevor sie als fertig gilt.** Durch
      den Rot-Lauf des Tests aus AK4, der die vier unwirksamen Einträge namentlich nennt, wörtlich im
      Docstring der Prüfklasse. Er ist damit der einzige Beleg. Eine Messung an einem echten Projekt
      gehört **nicht** zur Abnahme: Sie ist auf der Zielinstanz nicht durchführbar, und ein
      Vorher-Wert fällt nach dem Merge nicht mehr an.
- [ ] **AK7 — Die Kostenfolge ist benannt, nicht begrenzt.** Festgehalten ist, dass mehr erkannte
      Gebäude bei eingeschalteter Cloud-Erkennung zu mehr kostenpflichtigen Abfragen führen — als
      bewusst in Kauf genommene Folge. Es entsteht keine neue Schwelle und kein Deckel.
- [ ] **AK8 — Die veralteten Feldbezeichnungen sind korrigiert, wo sie den heutigen Stand
      beschreiben.** Betroffen sind `cloud_landmark_detection_enabled`, `cloud_landmark_consent_at`
      und `PUT /projects/{id}/cloud-landmark-consent`. Stellen, die die Umbenennung selbst
      dokumentieren, bleiben unverändert — dort ist der alte Name historisch korrekt. Maßgeblich ist
      der Stand bei der Umsetzung, nicht die Fundstellen-Zahl zum Zeitpunkt der Schärfung: Vor dem
      Commit wird repo-weit gesucht und jeder Fund nach dieser Regel eingestuft.

## Datenmodell-Bezug

Keine Änderung. Kein Schemaeingriff, keine Migration, kein Backfill. `PhotoCriterionScore` bleibt
unverändert; die Änderung wirkt genau ab dem nächsten Kriterien-Lauf, ältere Zeilen bleiben stehen.
Siehe [`docs/architecture.md`](../../docs/architecture.md).

## Architektur / Umsetzung

### 1. Der Kernkonflikt: AK4 gegen die Konvention aus Spec 0217

Spec [`0217`](./0217-landschaft-erkennung-spezifitaets-vorrang.md) verlangt, die Schreibweise der
Allow-Listen-Einträge einmalig im Kommentar festzuhalten, „kein modellladender Test"; AK4 verlangt
eine automatische Prüfung. **Die Konvention wird nicht abgelöst, sondern präzisiert: Sie verbietet
das Modell im Test, nicht das Asset.** Beide Modell-Assets sind ZIP-Archive mit angehängten
Metadaten; `zipfile` aus der Standardbibliothek liest die Label-Datei heraus, ohne `mediapipe`, ohne
TensorFlow, ohne Modellinstanziierung, ohne Inferenz — derselbe Vorgang wie der bestehende
SHA-256-Integritätstest in `backend/tests/test_classification.py`, der dieselbe Datei liest. Die
Kommentar-Angabe bleibt zusätzlich stehen, trägt aber nicht mehr allein.

Festgelegt in ADR
[`0124`](../decisions/0124-allow-listen-werden-gegen-die-label-datei-des-assets-geprueft.md).

### 2. Umfang der Prüfung: alle fünf kuratierten Allow-Listen

Geprüft wird jede der fünf kuratierten Allow-Listen gegen die Label-Datei ihres Modell-Assets — jedes
Paar (Liste, Asset) einzeln:

| Liste | Modul | Modell-Asset |
|---|---|---|
| `ARCHITECTURE_CATEGORIES` | `photosort/criteria.py` | `efficientnet_lite0.tflite` (ImageNet-1k) |
| `LANDSCAPE_SCENE_CATEGORIES` | `photosort/criteria.py` | `efficientnet_lite0.tflite` (ImageNet-1k) |
| `VEHICLE_CATEGORIES` | `photosort/criteria.py` | `efficientdet_lite0.tflite` (COCO-80) |
| `FOOD_CATEGORIES` | `photosort/criteria.py` | `efficientdet_lite0.tflite` (COCO-80) |
| `ANIMAL_CATEGORIES` | `photosort/classification.py` | `efficientdet_lite0.tflite` (COCO-80) |

Die Paare liegen über **zwei** Modulpfade: vier Listen in `criteria.py`, die fünfte in
`classification.py` (dort definiert, gefiltert in `criteria.py::animal_detections` und
`compute_tier_score`). Der Test sammelt sie deshalb über beide Module, nicht über eines. Alle fünf
sind listenunabhängig von derselben Fehlerklasse betroffen; die Erweiterung ist eine Zeile Aufruf je
Liste, kein zweiter Mechanismus. Zum heutigen Stand sind die übrigen vier vollständig wirksam —
festgehalten war das nirgends.

**Der Dateiname der Label-Datei kommt aus dem ZIP-Inventar des Assets, nie hartkodiert** — sonst
wäre derselbe Fehler eine Ebene tiefer: Der Test liefe bei ausgetauschtem Asset ins Leere und wäre
grün, ohne etwas über die Liste zu sagen. Beleg, dass die Kommentar-Konvention allein nicht trägt:
`criteria.py` nennt die Label-Datei des Objekt-Detektors `labelmap.txt`; tatsächlich heißt sie
`labels.txt`.

Bewusst **nicht** im Umfang: `_INVISIBLE_CATEGORIES` (`cameras.py`) filtert Codepoints, keine
Modelllabels; die Mengen aus `event_inputs.py`/`event_probe.py` gehören zu keinem Modell-Asset. Die
Ausweitung betrifft die **Prüfung**, nicht das Verhalten: kein Score, keine Trefferzahl, keine andere
Liste ändert sich dadurch.

### 3. Die überarbeitete Liste (AK1, AK2, AK3)

**Aufnahmekriterium (AK3, wörtlich als Kommentar über der Liste zu führen):**

> Aufgenommen wird eine Bauwerksart, wenn sie ein **eigenständiges Bauwerk im Außenraum** ist, das
> **als Motiv für sich steht**. Nicht aufgenommen werden Innenräume, Ladeneinrichtungen und einzelne
> Bauteile wie Dächer, Mauern oder Zäune. Im Zweifel wird eine Bauwerksart weggelassen statt
> aufgenommen.

**Reparatur der vier toten Einträge (AK1) — Ersetzung, nicht Streichung:**

| bisher | künftig | Grund |
|---|---|---|
| `lighthouse` | `beacon` | Modellklasse trägt einen anderen Namen |
| `bell_cote` | `bell cote` | Label-Datei schreibt mit Leerzeichen |
| `triumphal_arch` | `triumphal arch` | Label-Datei schreibt mit Leerzeichen |
| `suspension_bridge` | `suspension bridge` | Label-Datei schreibt mit Leerzeichen |

**Neu aufgenommen (AK2) — jede im Asset nachgewiesen:**

| Eintrag | Aufnahme begründet |
|---|---|
| `steel arch bridge` | eigenständiges Brückenbauwerk; schließt die Lücke zur bereits aufgenommenen `suspension bridge` |
| `water tower` | eigenständiges Bauwerk im Außenraum, weithin sichtbares Einzelmotiv |
| `dam` | eigenständiges Großbauwerk im Außenraum |
| `pier` | Seebrücke, eigenständiges Bauwerk im Außenraum |
| `fountain` | eigenständiger Brunnen im Außenraum |
| `planetarium` | eigenständiger Gebäudebau |

Die sechzehn bisherigen Einträge bleiben. Drei Grenzfälle werden dabei ausdrücklich begründet statt
stillschweigend mitgeführt: `dome` (die ImageNet-Klasse meint den Kuppelbau als Ganzes, nicht das
Bauteil), `bell cote` (streng genommen ein Dachaufsatz, aber die einzige Klasse, die das Modell für
den in AK1 genannten Glockenturm anbietet) und `library` (kann Innenräume zeigen — das ist die in AK5
beschriebene, bewusst akzeptierte Lücke).

**Geprüft und verworfen** (Auswahl aus 161 nach Bildinhalten durchsuchten Label-Kandidaten; jeweils
mit dem Grund, der im Kommentar steht):

| Kandidat | Ablehnungsgrund |
|---|---|
| `breakwater`, `stone wall`, `picket fence`, `chainlink fence`, `worm fence`, `tile roof` | Mauern, Zäune, Dächer — einzelne Bauteile |
| `bakery`, `barbershop`, `bookshop`, `butcher shop`, `confectionery`, `grocery store`, `shoe shop`, `tobacco shop`, `toyshop`, `restaurant`, `cinema`, `prison` | Ladeneinrichtungen bzw. Innenräume; die Klassen zeigen überwiegend Interieurs |
| `greenhouse` | Klasse zeigt typischerweise den Innenraum unter Glas |
| `window screen`, `window shade`, `sliding door`, `pedestal`, `vault`, `turnstile`, `theater curtain` | Bauteile bzw. Innenraum |
| `megalith` | Grenzfall mit Fehltrefferrisiko (Findlinge, Naturformationen) — im Zweifel weggelassen |
| `cliff dwelling`, `drilling platform`, `lumbermill`, `dock`, `solar dish` | Grenzfälle (Stätte, Industrieanlage, Bauteil einer Anlage) — im Zweifel weggelassen |
| `yurt`, `mobile home`, `mountain tent` | Behausungen ohne ortsfestes Bauwerk |

### 4. Betroffene Dateien

| Datei | Änderung |
|---|---|
| `backend/src/photosort/criteria.py` | `ARCHITECTURE_CATEGORIES` korrigiert und erweitert; Kommentarblock 441-451 ersetzt durch Aufnahmekriterium und Aufnahme-/Ablehnungstabelle; Kommentar 377-384 korrigiert (`labels.txt` statt `labelmap.txt`); Verweis auf ADR 0124 |
| `backend/tests/test_criteria.py` | Prüfung jedes Paares (Liste, Asset) gegen die Label-Datei aus dem ZIP-Inventar; Vollständigkeits-Wächter über fünf Listen aus zwei Modulpfaden (`photosort.criteria`, `photosort.classification`); Gegenproben |
| `backend/src/photosort/criterion_probe.py` | **neu** — rein lesendes Messkommando für künftige Änderungen an einer Kriterienliste |
| `specs/decisions/0124-*.md` | **neu** (angelegt) |
| `specs/architecture/0002-testkonzept.md` | 0217-Konvention um das Asset-Lesen ergänzt; `category_diff.py`-Verweise auf `place_probe`/`event_probe` umgehängt |
| `specs/architecture/0003-securitykonzept.md` | Fortschreibung (siehe `## Security`) und die Namenskorrekturen aus Abschnitt 7 |
| `docs/architecture.md`, `.env.example` | veraltete Namen aus Abschnitt 7 |

**Nicht betroffen:** Datenmodell, Migrationen, API-Verträge, Frontend, `motifs.py`,
`album_selection.py`, `events.py`. `compute_gebaeude_score`, `is_landmark_candidate`,
`LANDMARK_CANDIDATE_CRITERION_KEYS` und die Schwellen `_GEBAEUDE_PRESENCE_THRESHOLD` (0.01) und
`SCENE_CLASSIFICATION_CONFIDENCE_THRESHOLD` (0.5) bleiben unverändert — die Änderung ist
ausschließlich Inhalt der Liste.

### 5. Umsetzung in Teilschritten

Der Issue nennt die Trennbarkeit von Reparatur und Überarbeitung ausdrücklich. Sie wird zu zwei in
sich grünen Schritten, weil ein Zwischenstand mit rotem CI kein Zwischenstand ist.

**Schritt 1 — Reparatur der vier Einträge, mit der Prüfung.**
`fix: Gebäude-Allow-Liste gegen die Modell-Labels korrigiert`

1. Den Prüftest aus Abschnitt 2 **zuerst** schreiben und den roten Lauf festhalten (er nennt die vier
   Einträge) — das ist der Vorher-Beleg auf Regel-Ebene und fällt als Nebenprodukt des TDD-Zyklus an.
   Die Ausgabe gehört in die PR-Beschreibung.
2. Die vier Einträge korrigieren. Der Test wird grün.

**Schritt 2 — Überarbeitung der Liste.**
`feat: Gebäude-Allow-Liste um weitere Bauwerkstypen erweitert`

Sechs Einträge gemäß Abschnitt 3, Aufnahmekriterium und Tabellen als Kommentar, die verworfenen
Kandidaten namentlich. Der Test aus Schritt 1 deckt die Erweiterung ohne Änderung mit ab.

**Schritt 3 — Messwerkzeug und Kostenfolge** (Abschnitt 6). Das rein lesende Messkommando
`criterion_probe.py` entsteht als Werkzeug künftiger Änderungen an einer Kriterienliste; diese
Erweiterung belegt es nicht.

**Schritt 4 — Sicherheitskonzept- und Doku-Namen** (Abschnitt 7), eigener `docs:`-Commit. Reine
Textänderung, getrennt gehalten, damit die Änderung am Gebäude-Kriterium einen unvermischten Diff
hat.

Reihenfolge-Begründung: erst die dauerhafte Zusicherung, dann die inhaltliche Erweiterung. Ein Test,
der nach der Erweiterung geschrieben wird, prüft nur die neue Liste; in dieser Reihenfolge belegt er
den Befund selbst.

### 6. Kostenfolge (AK7) und der Regel-Beleg (AK6)

**Wo die vergrößerte Trefferliste durchschlägt.** `compute_gebaeude_score` gibt entweder exakt `0.0`
oder einen Wert `>= 0.5` zurück; `is_landmark_candidate` vergleicht `gebaeude >= 0.01`. Beide Zahlen
zusammen bedeuten: **Jedes Foto mit einem Gebäude-Treffer ist bereits Landmark-Kandidat** — es gibt
keine zweite, dämpfende Stufe. Zwei Stellen lesen das:

- **Live-Lauf:** `worker.py::_select_landmark_candidates` — jeder zusätzliche Kandidat ist ein
  zusätzlicher Cloud-Vision-Aufruf, sofern Consent-Schalter und laufbezogenes Häkchen gesetzt sind.
- **Kostenschätzung:** `api/projects.py::_count_landmark_candidates` zählt über die gespeicherten
  `PhotoCriterionScore`-Werte für `LANDMARK_CANDIDATE_CRITERION_KEYS` und speist
  `landmark_candidate_count` in die Projekt-Antwort; die Umrechnung in Geld liegt in `pricing.py`.

**Keine neue Schwelle, kein Deckel.** Die Mehrkosten sind laut AK7 bewusst in Kauf genommen. Eine
Begrenzung der Kandidatenzahl oder eine zweite Kostenschwelle wäre eine eigene Produktentscheidung
und verschlechterte die Erkennung wieder. Der Preis wird benannt, nicht begrenzt.

**AK6 ist Regel-Ebene, und zwar ausschließlich.** Der Prüftest belegt exakt, welche Einträge vorher
unwirksam waren und welche hinzukommen. Die Aussage „12 von 16 wirksam, danach 22 von 22" ist damit
eine geprüfte, keine behauptete — unabhängig von jedem Fotobestand. **Eine Material-Messung ist
nicht Teil der Abnahme, weil sie strukturell nicht durchführbar ist.** Die Zielinstanz ist
ausschließlich über die Weboberfläche bedienbar — kein getipptes Kommando, keine Datei in einen
Container —, deployen lässt sich nur ein gemergter Stand, und ein Vorher-Wert existiert nur bis zum
nächsten Kriterien-Lauf: `PhotoCriterionScore` speichert allein den Score und überschreibt ihn
(`UniqueConstraint(photo_id, criterion_key)`, kein Laufbezug). Der Zuwachs dieser Erweiterung bleibt
deshalb unbeziffert, auch nachträglich; die Lücke ist ohne Träger in
[`specs/architecture/0002-testkonzept.md`](../architecture/0002-testkonzept.md) geführt.

**Werkzeug:** ein rein lesendes Messkommando `backend/src/photosort/criterion_probe.py` nach dem
Muster von `event_probe.py`/`place_probe.py` (read-only je Modul, eigener Wächterfall,
`main(argv, *, database_url)`), Aufruf `python -m photosort.criterion_probe --project-id N`. Es
liest nur die Datenbank, lädt kein Modell, schreibt nichts. Es belegt diese Änderung nicht, sondern
ist das Messwerkzeug jeder künftigen Änderung an einer Kriterienliste — nach Merge und Deploy über
die Container-Konsole aufrufbar. Ausgegeben werden ausschließlich Zahlen; die Auflagen aus
`## Security` gelten unverändert.

### 7. AK8 — die veralteten Namen: letzter, isolierter Schritt

Sachlich hat AK8 mit dem Gebäude-Kriterium nichts zu tun. Er wird dennoch nicht abgetrennt: Der AK
steht im Issue, seine Erfüllung ist an diese Story gebunden, und ein Abtrennen erzeugte eine zweite
Story, einen zweiten Branch und einen zweiten PR für eine Textänderung ohne technisches Risiko. Die
Trennung wird stattdessen innerhalb der Umsetzung hergestellt — eigener `docs:`-Commit am Ende.

**Regel für die Entscheidung je Fundstelle:** Korrigiert wird, was **den heutigen Stand beschreibt**.
Unverändert bleibt, was **die Umbenennung selbst dokumentiert** — dort ist der alte Name historisch
korrekt.

Geprüft im Bestand:

| Stelle | Einstufung |
|---|---|
| `0003-securitykonzept.md:318` | **bleibt** — dokumentiert die Umbenennung selbst |
| `0003-securitykonzept.md:332` | korrigieren (beschreibt Einwilligung und Endpunkt als heutigen Stand) |
| `0003-securitykonzept.md:340` | korrigieren (spricht vom „bestehenden Schalter") |
| `0003-securitykonzept.md:409` | korrigieren (beschreibt, woran der Abfluss heute hängt) |
| `0003-securitykonzept.md:520` | korrigieren (nennt den Schalter als heutigen Bezugspunkt) |
| `0003-securitykonzept.md:1386` | korrigieren (offene Frage, die den Schalter als heute geltende Grundlage benennt) |
| `docs/architecture.md:2320` | korrigieren — nennt `Default Project.cloud_landmark_detection_enabled=False` als heutigen Produktivpfad |
| `.env.example:47` | korrigieren — nennt den Endpunkt `PUT /projects/{id}/cloud-landmark-consent` als heutigen Stand |
| `docs/architecture.md:1210-1219` | **bleiben** — Änderungsnotiz, die die Umbenennung selbst dokumentiert |
| `specs/features/0047/0054/0055/0469`, `specs/decisions/0025/0029/0031/0032`, `specs/architecture/0002-testkonzept.md` (Sektionen zu diesen Specs), `alembic/versions/e1f2a3b4c5d6_*`, `b3c4d5e6f7a8_*`, `backend/tests/test_migration_*` | **bleiben** — historische Beschlüsse, Migrationsnamen und der Test darauf; der alte Name ist dort der Gegenstand |

Vor dem Commit wird repo-weit nach `cloud_landmark_detection_enabled`, `cloud_landmark_consent_at`
und `cloud-landmark-consent` gesucht und **jeder** Fund nach der obigen Regel eingestuft; die
Einstufung je Fundstelle kommt in die PR-Beschreibung. Nur so ist nachvollziehbar, dass die nicht
geänderten Stellen bewusst stehen bleiben. Treffer unterhalb von `.claude/worktrees/` bleiben außer
Betracht — das sind Arbeitskopien, keine Repository-Inhalte.

## UI/UX

**Nicht relevant.** Die Änderung betrifft ausschließlich den Inhalt einer Code-Konstante und einen
Prüftest; kein Frontend-Pfad, keine Anzeige und kein Eingabeelement wird berührt. Die einzige
sichtbare Zahl, `landmark_candidate_count`, existiert bereits und ändert nur ihren Wert — Darstellung
und Zustände bleiben unverändert. Der Issue-Body trägt keinen `## Design`-Abschnitt.

## Security

**Sicherheitsrelevant an genau einer Stelle (S1), kein Blocker** — dieselbe Einstufung wie Spec
[`0217`](./0217-landschaft-erkennung-spezifitaets-vorrang.md), und dieselbe Vertrauensgrenze. Kein
neuer Endpunkt, keine Auth-Änderung, kein angefasster API-Vertrag, kein Schemaeingriff, keine
Migration, keine neue Abhängigkeit, kein neues Modell-Asset, kein neues Secret, keine neue
Betriebseinstellung, keine neue Eingabe von außen.

- **S1 — Die Gebäude-Allow-Liste ist ein Regler an der Cloud-Grenze, und dieser Regler wird hier
  aufgedreht.** Zwischen Allow-Listen-Treffer und Cloud-Kandidatur liegt keine dämpfende Schwelle
  (Abschnitt 6): Jeder Gebäude-Treffer ist Landmark-Kandidat, jeder Kandidat ein Cloud-Vision-Aufruf
  mit der `display`-Variante des Fotos. Die wirksame Menge wächst von 12 auf 22 Einträge. Mehrere der
  neuen Klassen (`pier`, `dam`, `steel arch bridge`, `fountain`) feuern erfahrungsgemäß auch auf
  Wasser- und Weitwinkelszenen ohne erkennbares Bauwerk; die Zahl zusätzlich hinausgehender Fotos ist
  damit **nicht aus der Listenlänge ableitbar**.
  **Der Zuwachs bleibt unbeziffert — entschieden von Daniel, bewusst so angenommen.** Die Messung
  an einem echten Projekt ist strukturell nicht durchführbar: Die Zielinstanz ist ausschließlich
  über die Weboberfläche bedienbar, `criterion_probe.py` ist ein getipptes Kommando; deployen lässt
  sich nur ein gemergter Stand; und der Vorher-Wert fällt mit dem ersten Re-Scan weg, weil
  `PhotoCriterionScore` keinen Laufbezug trägt und überschrieben wird. Belegt ist die Änderung
  deshalb allein auf Regel-Ebene (AK6, der Rot-Lauf des Prüftests, der die vier toten Einträge
  namentlich nennt). **Die fehlende Zahl wird nicht ersetzt:** keine Schätzung, keine Hochrechnung
  aus der Listenlänge, keine `0` — unbeziffert heißt benannt-unbeziffert.
  **Was das trägt:** Die Vorab-Kostenvorschau zeigt `landmark_candidate_count` vor jedem
  kostenpflichtigen Lauf als „Sehenswürdigkeits-Erkennung: N Fotos" und speist sich aus derselben
  Funktion `is_landmark_candidate`, die der Live-Lauf benutzt — die Menge, die den Homeserver
  verlässt, steht vor dem Auslösen da, und ohne erfolgreichen Vorlauf steht dort „Menge noch
  unbekannt" statt einer Null. **Ungedeckt bleibt der Vergleich vorher/nachher:** Wie groß diese
  eine Öffnung war, ist nachträglich nicht mehr feststellbar. Geführt als eigener Punkt unter
  „Bewusst akzeptierte Restrisiken" im Sicherheitskonzept. **Für jede künftige Erweiterung einer
  Kriterien-Allow-Liste bleibt die Messung die Regel** — eine erneute Abweichung ist wieder eine
  ausgesprochene Produktentscheidung, nie eine Entscheidung des umsetzenden Laufs.
  **Die Einwilligung bleibt unberührt, aus derselben Begründung wie bei Spec 0217:** Empfänger,
  Zweck, Datenumfang pro Foto und Consent-Mechanik ändern sich nicht — ausschließlich die Auswahl der
  Fotos innerhalb derselben, bereits eingewilligten Verarbeitung. `cloud_vision_consent_at` wird
  **nicht** zurückgesetzt, es entsteht kein zweiter Zustimmungsschritt.
  **Unverändert Muss und von dieser Story nicht anzufassen:** der Vorfilter bleibt rein lokal und
  **vor** jedem Cloud-Aufruf; ausschließlich die `display`-Cache-Variante (2048×2048), nie das
  Original; kein GPS-/EXIF-Zugriff; kein erneutes Senden bereits gescorter Fotos;
  `run_criterion_scoring` baut den Landmark-Client nur bei gesetztem Consent-Schalter (kein
  Client-Aufbau „auf Verdacht"); Live-Lauf und Anzeige-/Schätzpfad bleiben an derselben einen
  Funktion, damit die angezeigte Zahl nicht von der real gesendeten Menge abweicht.
  Der bereits geführte Eskalationspunkt „gestohlenes JWT löst kostenpflichtige Läufe aus" wird
  quantitativ größer, nicht qualitativ anders — unverändert kein Blocker, kein Rate-Limiting nötig.

- **S2 — `criterion_probe.py` gibt Zahlen aus, und diese Zahlen landen dort, wo sie jemand hinstellt.**
  Das Werkzeug misst jede künftige Änderung an einer Kriterienliste; seine Ausgabe ist zum
  Weitergeben gedacht — in einen Pull Request, in einen Issue-Kommentar, in einen Bericht — also
  potenziell unwiderruflich und ohne Empfängerkreis veröffentlicht. Die Auflagen gelten deshalb an
  der Ausgabe selbst, nicht an einem einzelnen Anlass. Es gilt die schärfere Auflage von
  `event_probe.py`.
  **Muss:** Die Ausgabe trägt **keinen** `relative_path` und keinen Dateinamen, keinen
  OpenCloud-Pfad, keinen Projektnamen, keinen Zeitstempel, keine Koordinate, keinen Orts- oder
  Sehenswürdigkeitsnamen; ausgewiesen wird die Projekt-**Id**. Ausgegeben werden ausschließlich
  Anzahlen über den Lauf: Fotos mit Wert `0` bzw. `> 0` je Kriterium (`gebaeude`, `landschaft`), Zahl
  der Landmark-Kandidaten, `landmark_candidate_count`. **Nie eine Zeile je Foto.**
  **Klassennamen sind erlaubt, die Verbindung ist es nicht:** Die 22 Einträge stehen ohnehin im
  öffentlichen Repository, eine Trefferzahl je Klasse über den ganzen Lauf gibt darüber hinaus nichts
  her. Verboten ist die Verbindung **Klassenname ↔ einzelnes Foto** in jeder Form — keine Zeile
  „Foto X: `pier`", keine Beispielliste, kein Auszug, auch nicht gekürzt, auch nicht mit Foto-Id
  statt Pfad. Eine solche Zeile ist eine Aussage darüber, was auf einem bestimmten Familienfoto zu
  sehen ist; eine Auszählung ist es nicht. Kein `--namen`-Schalter, kein Beispielabschnitt.
  **Ausfallrichtung — „nicht gemessen" ist nicht „null":** Liegt kein erfolgreicher Kriterien-Lauf
  vor, meldet das Werkzeug `NICHT GEMESSEN`, nie `0` — dieselbe Regel, die `api/projects.py` mit
  `landmark_candidate_count: int | None` bereits durchsetzt. Eine `0`, die als Messergebnis gelesen
  wird, behauptet „nichts verlässt den Homeserver" für einen Anteil, der gleich Geld kostet, und
  trüge damit eine Entscheidung, die niemand getroffen hat.
  **Muss (rein lesend, wie die beiden Vorbilder dreifach abgesichert):** kein
  `INSERT`/`UPDATE`/`DELETE`, kein Aufrufpfad aus `main.py`/`worker.py`, kein Endpunkt, kein
  Compose-`command` — festgehalten über Import-Graph, Syntaxbaum-Wächter und einen echten
  `main()`-Lauf mit Tabellen-Schnappschuss davor und danach; kein Teil trägt allein.
  **Muss (Ausgabekanal und Eingabe):** Ausgabe ausschließlich nach stdout — keine Datei-Ausgabe,
  nichts über den strukturierten Anwendungs-Logger und damit nichts in persistente Container-Logs.
  `--project-id` ist `argparse type=int`, jeder Datenbankzugriff läuft über SQLAlchemy-Konstrukte mit
  Parameterbindung, nie über `text()` mit f-String. Ein unbekanntes Projekt oder ein
  Verbindungsfehler ergibt eine kurze eigene Meldung und Exit-Code ≠ 0 — **kein durchgereichter
  SQLAlchemy-Traceback**, der die `DATABASE_URL` samt Zugangsdaten in eine Ausgabe schreibt, die
  anschließend in einen Pull Request kopiert wird (Muster `OpenCloudError`).

- **S3 — Die neue Prüfung liest ein Asset, kein Modell.** Der Test nach ADR
  [`0124`](../decisions/0124-allow-listen-werden-gegen-die-label-datei-des-assets-geprueft.md) liest
  die Label-Datei aus dem ZIP-Inventar einer eingecheckten, SHA-256-gepinnten Datei mit `zipfile` aus
  der Standardbibliothek: keine neue Abhängigkeit, kein Netzwerkzugriff, kein Laufzeit-Download, kein
  Modell-Laden, keine Inferenz, kein Deserialisieren eines fremden Graphen. Die einzige bekannte
  Risikoklasse von `tflite` — das Laden einer zur Laufzeit von außen zugeführten Modelldatei — ist
  hier strukturell nicht erreichbar.
  **Muss:** gelesen wird über `ZipFile.read()` auf einem Inventar-Eintrag, **nie**
  `extract()`/`extractall()` in ein Verzeichnis — Zip-Slip und Pfad-Traversal entstehen erst beim
  Schreiben auf die Platte, und ein Auspacken hat hier keinen Zweck. Der bestehende
  SHA-256-Integritätstest je Asset bleibt die zweite Hälfte: der eine sichert, dass die Datei die
  geprüfte ist, der andere, dass die Liste zu ihren Labels passt.

- **S4 — Die Namenskorrekturen aus AK8 sind reine Dokumentation.** Die Umbenennung ist seit ADR 0032
  umgesetzt; korrigiert wird ausschließlich Text, der den heutigen Stand beschreibt und dabei die
  alten Namen führt. Kein Code, kein Endpunkt, kein Datenbankfeld, kein Consent-Verhalten wird
  angefasst. **Muss:** Stellen, die die Umbenennung selbst dokumentieren (`0003-securitykonzept.md`
  Zeile 318), bleiben wörtlich stehen — eine „vereinheitlichende" Korrektur dort löschte den
  Nachweis, dass ein Bestandsprojekt mit zuvor `cloud_landmark_detection_enabled=True` ohne erneute
  Bestätigung auch für die Kategorie-Erkennung aktiv wurde. Das ist die Begründung einer getroffenen
  Consent-Entscheidung, nicht ein veralteter Feldname.

- **S5 — Kein Auth-Pfad, keine Eingabevalidierung, keine Sichtbarkeit berührt.** Es entsteht kein
  Endpunkt und kein Feld in einer API-Antwort. Kein Pfad nimmt einen neuen Wert von außen an — die
  Allow-Liste ist eine Code-Konstante, die Modellausgabe entsteht lokal, `--project-id` ist ein
  `int`. Die Sichtbarkeit zwischen den beiden Nutzern bleibt unverändert: Kriterien-Werte sind
  projekt- und laufbezogen, nicht personenbezogen.

**Geprüft und ohne Befund:** kein Secret, keine neue Abhängigkeit, kein neues Modell-Asset, kein
SSRF-Pfad, keine neue Tabelle und keine neue Spalte, keine Änderung an
`project_deletion.py`/`tests/project_graph.py` nötig, keine neue Nutzereingabe, keine
Frontend-Renderstelle, kein Log-Kanal für eine neue Datenklasse.

### Nachzuziehen im Sicherheitskonzept

`specs/architecture/0003-securitykonzept.md` ist im selben Pull Request fortzuschreiben:

1. **Abschnitt „Cloud-Vision-API", nach dem Bullet zur Vorfilterungs-Verschiebung (ADR 0047):** eine
   Fortschreibung zu dieser Spec — die Kandidatenmenge wächst erneut, diesmal durch eine reparierte
   und erweiterte Allow-Liste; Zweck, Empfänger, Datenumfang pro Foto und Consent-Mechanik
   unverändert; **der Zuwachs bleibt unbeziffert und ist als solcher einzutragen**, nie als `0` und
   nie als Schätzung. Ausdrücklich festhalten: zwischen Allow-Listen-Treffer und Cloud-Aufruf liegt
   keine dämpfende Schwelle — jede künftige Erweiterung dieser Liste ist damit unmittelbar eine
   Ausweitung des Abflusses und wird beziffert; die Abweichung hier ist eine ausgesprochene
   Produktentscheidung und steht mit eigenem Eintrag unter „Bewusst akzeptierte Restrisiken".
2. **Ankerliste:** eine Zeile für die Ausgabe-Hygiene von `criterion_probe.py` (verbotene Klassen
   plus die verbotene Verbindung Klassenname ↔ einzelnes Foto, Ausfallrichtung `NICHT GEMESSEN`),
   rein lesend dreifach gesichert, samt Testnamen — nach dem Muster der bestehenden Zeilen zu
   `place_probe.py`/`event_probe.py`.
3. **Die Fundstellen aus S4** auf die heutigen Feldnamen korrigieren, Zeile 318 unverändert lassen.

## Teststrategie

**Testebene: Unit, rein, ohne Datenbank, ohne Modell**, in `backend/tests/test_criteria.py` — der
Datei, die die Listen heute schon hält. Es entsteht keine neue Funktion im Produktivpfad und kein
neuer Aufrufpfad; die Story ist eine Konstantenänderung mit einer Regelschicht darunter.

**Was die Tests tragen — und was ausdrücklich nicht:**

| Zusage | Träger |
|---|---|
| AK4 — jeder Eintrag jeder kuratierten Liste steht in der Label-Datei ihres Assets | automatisierter Test, parametrisiert über fünf Paare |
| AK1/AK2/AK3 — die konkrete neue Zusammensetzung: vier Umbenennungen, sechs Ergänzungen, 22 Einträge | automatisierter Test, exakte Mengenprüfung |
| AK6 — welche Einträge vorher unwirksam waren | der Rot-Lauf desselben Tests, wörtlich im Test-Docstring; einziger Beleg der Verhaltensänderung |
| mehr Gebäude-Erkennung an echten Fotos | **kein Träger.** Keine Messung, kein Test — als trägerlose Lücke im Testkonzept geführt |
| AK5/AK7/AK8 | Text und Kommentar, kein Test |
| Erkennungsgüte an echten Fotos, Vollständigkeit der kuratierten Auswahl, Index-Behauptung zu `LANDSCAPE_SCENE_CATEGORIES` | bewusst nicht geprüft (ADR 0124 Punkt 4) |

**Der Prüftest (AK4).** Eine Funktion `_assert_allow_list_is_covered_by_label_file(categories,
asset)` — als Funktion, nicht als Schleifenrumpf im Testfall, weil die Gegenprobe dieselbe Funktion
mit einer verfälschten Liste aufrufen muss. Der Dateiname kommt aus dem `zipfile`-Inventar
(`namelist()`, genau ein `.txt`-Eintrag), nie hartkodiert. Geprüft wird jeder Eintrag als **exakte
String-Gleichheit, ohne jede Normalisierung** (`casefold`, `strip`, `_`→` ` verboten). Die Meldung
nennt Listenname, fehlende Einträge und Asset-Dateinamen.

**Exakte Mengenprüfung als zweiter, bewusst redundanter Fall.** Die ⊆-Prüfung allein ist mit *jeder*
Teilmenge der Label-Datei erfüllt — auch mit einer versehentlich geschrumpften Liste. Die Substanz
der Story braucht deshalb einen literalen Fall auf die exakte neue Menge, nach dem Muster
„geschlossene Taxonomie" (ADR
[`0049`](../decisions/0049-festes-kategorien-set-mit-vorrangreihenfolge-und-freien-feinlabels.md)).
Er pinnt das Akzeptanzkriterium, nicht eine Formulierung.

**Vollständigkeitsschutz für jede künftige Liste.** Der Test leitet die zu prüfenden Listen nicht aus
einer Handliste ab, sondern aus der Quelle: Die Menge der kuratierten `frozenset[str]`-Konstanten aus
`criteria.py` **und** `classification.py` muss der Namensmenge der Parametrisierung entsprechen.
Gesammelt wird **dedupliziert über Objektidentität** — `criteria.py` importiert `ANIMAL_CATEGORIES`,
ein naives Sammeln über beide Module fände sie sonst doppelt. Die Ableitung wird als Funktion über
ein Namespace-Abbild gebaut, nicht als direkter `modul.__dict__`-Zugriff: nur so ist sie
gegenprobefähig. Suchraum und Auslassungen (`_INVISIBLE_CATEGORIES` in `cameras.py` filtert
Codepoints, keine Modelllabels) gehören in den Testkommentar.

**Rot-Beleg im TDD-Zyklus.** Der Test wird zuerst gegen den unveränderten Bestand geschrieben und rot
gesehen; die Fehlermeldung muss genau die vier toten Einträge und das Asset benennen. Dieser Rot-Lauf
ist der Beleg der Verhaltensänderung und gehört mit Befehl und vollständiger Meldung
wörtlich in den Test-Docstring. **Er trägt zugleich das Normalisierungsverbot:** Er ist nur
reproduzierbar, solange exakt verglichen wird — die vier toten Einträge scheitern *an der
Schreibweise*. Wer die Prüfung später normalisiert, kann den Rot-Beleg nicht mehr erzeugen und hat
die geprüfte Zusage stillschweigend auf das Niveau des Kommentars zurückgesetzt, den sie ablöst.

**Gegenproben — je eine, jede mit benennbarem Fehlermodus:**

1. **Verfälschte Liste, echte Funktion.** Ein Eintrag wird auf eine Form gebracht, die nicht in der
   Label-Datei steht (Unterstrich-Variante); der Fall ist nur bestanden, wenn die Zusicherung rot
   wird und genau diesen Eintrag nennt. Fängt: „der Test liest die Liste gar nicht".
2. **Positiv-Gegenprobe der Normalisierung.** Derselbe Fall belegt, dass nicht klammheimlich gefaltet
   wird — er *muss* scheitern, obwohl dieselbe Klasse unter anderer Schreibweise in der Datei steht.
3. **Ableitungswächter:** ein sechstes `frozenset` im Abbild macht den Lauf rot; dazu die Untergrenze
   (die Ableitung findet die fünf bekannten Namen), sonst besteht der Wächter, weil er nichts findet.

### Wichtigste Edge Cases

- **Asset fehlt oder ist umbenannt:** harter Fehler, **kein `pytest.skip`** — ein Skip hielte den
  Test nach einem Asset-Umzug dauerhaft grün.
- **ZIP ohne (oder mit mehr als einer) Label-Datei:** harter Fehler statt stiller Leerprüfung.
- **Leere Liste:** die ⊆-Prüfung ist vakuum-grün; der exakte Mengenfall deckt das ab.
- **Künftige sechste Liste:** der Ableitungswächter färbt den Lauf rot, bis sie in der
  Parametrisierung steht.
- **Mehrteilige Klassennamen:** die ImageNet-Datei führt `dam` **und** `damselfly`, die COCO-Datei
  `hot dog`/`wine glass` mit Leerzeichen. Eine Teilstring- oder Präfixprüfung wäre an
  `photocopier`/`pier` bzw. `dam`/`damselfly` blind — die zweite, unabhängige Begründung für exakte
  Gleichheit.

Für `criterion_probe.py` gelten die drei Rein-lesend-Zusagen nach dem Muster `test_place_probe.py`:
Erreichbarkeit (kein Importpfad aus `main.py`/`worker.py`, kein Endpunkt, kein Compose-`command`),
Form (Syntaxbaum-Wächter mit Mikrotests je erkannter Schreibform und Positiv-Gegenproben) und Wirkung
(echter `main()`-Lauf gegen eine dateibasierte SQLite in `tmp_path` mit Schnappschuss jeder Tabelle
aus `Base.metadata.sorted_tables` davor und danach, inklusive Selbstschutz, dass der Schnappschuss
überhaupt etwas umfasst). Die autouse-Netzsperre aus `conftest.py` ist unberührt: `zipfile` gegen
eine lokale Datei öffnet keinen Socket.

### Nachzuziehen im Testkonzept

1. **Neue Sektion „Kuratierte Allow-Listen werden gegen die Label-Datei ihres Modell-Assets
   geprüft"** (ADR 0124 / Spec 0283): die fünf Paare, `zipfile`-Inventar statt hartkodiertem
   Dateinamen, exakte Gleichheit, der Ableitungswächter über beide Module, die Rot-Beleg-Regel, die
   Gegenprobe-Pflicht auf der geprüften Funktion.
2. **Präzisierung der Konvention „kein modellladender Test"** (Sektion zu Spec 0217): verboten ist
   das **Modell** (Inferenz, Instanziierung), nicht das **Asset** (Dateizugriff auf die eingecheckte
   `.tflite`). Belegstelle ist der vorhandene SHA-256-Test in `test_classification.py`.
3. **`category_diff.py`-Verweise umhängen** (Sektion zu ADR 0047, Zeilen ~437 und ~505): die Datei
   entfiel mit ADR 0091; die Verweise gehen auf `place_probe.py`/`event_probe.py`, das Muster bleibt
   wörtlich gültig.
4. **Sektion „Bekannte Lücken"** ergänzen: die inhaltliche Erkennungsgüte der kuratierten Listen
   bleibt außerhalb jeder Automatisierung; für diese Erweiterung ist die Lücke **ohne Träger** — es
   wird nicht gemessen, auch das `criterion_probe.py`-Kommando belegt sie nicht.

## Entscheidungen

- `architect` konsultiert (Schritt 1): ADR
  [`0124`](../decisions/0124-allow-listen-werden-gegen-die-label-datei-des-assets-geprueft.md)
  angelegt.
- `ux-ui-designer` **nicht konsultiert** (Schritt 2): Es gibt keinen konkret benennbaren Bezug zu
  einer sichtbaren Oberfläche. Der Umfang endet an einer Code-Konstante, einem Prüftest und einem
  CLI-Messkommando; kein `frontend/`-Pfad wird berührt, kein API-Vertrag geändert, kein neues Feld
  angezeigt. Die einzige sichtbare Zahl (`landmark_candidate_count`) existiert bereits und ändert nur
  ihren Wert hinter unveränderter Anzeigelogik. Der Issue-Body trägt keinen `## Design`-Abschnitt.
- `test-engineer` konsultiert (Schritt 3): Teststrategie, Gegenproben und Edge Cases wie oben.
- `security-engineer` konsultiert (Schritt 3): S1–S5 und die Fortschreibung des Sicherheitskonzepts.
- **Entschieden durch Daniel (Refinement):** Reparatur und Überarbeitung in einer Story; die vier
  toten Einträge werden ersetzt, nicht gestrichen; AK8 bleibt Teil dieser Story.
- **Selbst entschieden (architect):** die Prüfung erfasst alle kuratierten Listen statt nur der
  Gebäude-Liste; der Label-Dateiname kommt aus dem ZIP-Inventar statt hartkodiert; AK8 wird nicht
  abgetrennt, sondern als isolierter `docs:`-Commit geführt.
- **Selbst entschieden (Hauptsession, gegen den ersten Entwurf):** Es sind **fünf** kuratierte
  Allow-Listen, nicht vier — `ANIMAL_CATEGORIES` (`classification.py:265`, COCO-80) trägt dieselbe
  Fehlerklasse und fehlte in ADR 0124 und im Architektur-Entwurf. ADR und Prüfumfang wurden vor der
  Spec-Anlage entsprechend korrigiert.
- **Selbst entschieden (test-engineer):** exakte Mengenprüfung zusätzlich zur ⊆-Prüfung; harter
  Fehler statt `pytest.skip` bei fehlendem Asset; Normalisierung ausgeschlossen.
- **Selbst entschieden (security-engineer):** für `criterion_probe.py` gilt die schärfere
  `event_probe`-Regel statt der `place_probe`-Regel.
- **Entschieden durch Daniel (Umsetzung, nach der ersten Review-Runde):** die Material-Messung des
  Kandidaten-Zuwachses (AK6(b)) entfällt. Die Zielinstanz ist ausschließlich über die Weboberfläche
  zugänglich — kein getipptes Kommando, keine Datei in den Container —, deployt werden nur gemergte
  Stände, und ein Vorher-Wert wird vom nächsten Kriterien-Lauf überschrieben
  (`PhotoCriterionScore`, kein Laufbezug). Der Zuwachs bleibt damit unbeziffert; die Regel-Ebene
  (Rot-Lauf) gilt als alleiniger Beleg. Das Messkommando `criterion_probe.py` bleibt im Code,
  umgewidmet zum Messwerkzeug jeder künftigen Änderung an einer Kriterienliste. Sicherheitlich ist das
  eine bewusste, im Sicherheitskonzept ausgewiesene Risikoübernahme, kein Versehen.

## Offene Fragen

- Keine.

## Out of Scope

- Die strukturelle Innenraum-Lücke (AK5) — sie bleibt bestehen und wird nicht behoben.
- Eine Begrenzung der Landmark-Kandidatenzahl, eine zweite Kostenschwelle oder ein Kostendeckel.
- Jede Änderung an `compute_gebaeude_score`, `is_landmark_candidate` und den beiden Schwellen.
- Ein Nachziehen bereits berechneter Läufe (kein Backfill), kein Schemaeingriff, keine Migration.
- Eine inhaltliche Überarbeitung der übrigen vier Allow-Listen — geprüft werden sie, angefasst nicht.
- Die Index-Behauptung zu `LANDSCAPE_SCENE_CATEGORIES` (Positionen 970, 972-980) und die
  Erkennungsgüte an echten Fotos.
- Manuell gesetzte Kategorie-Korrekturen bleiben unberührt.
- Eine Messung des Kandidaten-Zuwachses an einem echten Projekt — sie ist auf der Zielinstanz
  nicht durchführbar und wurde mit der Umsetzungs-Entscheidung fallengelassen.

---

*Umfang: Diese Spec liegt über dem Richtwert von ~200 Zeilen, weil sie die vier Fachkonsultationen
(Architektur, UI/UX, Security, Teststrategie) samt Umsetzungsplan, Aufnahme-/Ablehnungstabellen und
Nachzieh-Listen vollständig trägt — das ist die Arbeitsgrundlage des anschließenden
`developer`-Laufs; der Inhalt steht nirgends sonst.*
