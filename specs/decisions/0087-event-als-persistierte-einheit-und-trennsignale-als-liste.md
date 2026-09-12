# 0087 - Das Event ist eine persistierte Einheit je Kriterien-Lauf, seine Grenzen entstehen aus einer Liste gleichrangiger Trennsignale

**Status:** Accepted
**Datum:** 2026-09-12
**Bezug:** Spec `specs/features/0425-*.md`, ADR
[`0021`](./0021-kriterien-datenmodell-kuratierungs-pipeline.md) (gateführte Zwei-Phasen-Pipeline),
ADR [`0029`](./0029-gps-landmark-cluster-bildung.md) und ADR
[`0072`](./0072-ortsbezogene-cluster-anzeigeort-als-antwortableitung.md) (die bisherige
Cluster-Bildung, siehe Abgrenzung), ADR [`0062`](./0062-projektloeschung-als-metadatengeordnete-mengenloeschung.md)
(Erreichbarkeit entlang der Fremdschlüsselkanten)

**Umfang:** über dem Richtwert von rund 100 Zeilen, weil die Entscheidung sechs Punkte trägt und
einer davon (der Träger) einen gemessenen Befund und eine Datenlöschung mitführen muss.

## Kontext

Die heutige Gliederung trennt bei einer Zeitlücke oder einem Ortssprung zwischen zwei Fotos;
`refine_clusters_by_landmark` gruppiert das Ergebnis nachträglich nach erkannten Namen um. Drei
Eigenschaften dieses Aufbaus tragen die Story nicht:

1. Die Schwelle begrenzt den **Schritt**, nicht die Ausdehnung — ein Spaziergang in 400-m-Schritten
   trennt nie und überspannt Kilometer.
2. Die nachträgliche Umgruppierung erzeugt **zeitlich zerrissene** Gruppen: ein Basis-Cluster mit
   zwei Namen und namenlosen Fotos ergibt drei Schlüssel, von denen einer die beiden anderen
   durchsetzt. „Überschneidungsfrei" ist so nicht herstellbar.
3. Der übernommene Ort entsteht aus der **fertigen** Gruppe und kommt für die Gliederung zu spät.

## Abgrenzung zu ADR 0029 und ADR 0072

Beide bleiben `Accepted` und tragen einen Teil-Vermerk im Kopf. Abgelöst wird ausschließlich der
**Mechanismus** der Verfeinerung: `refine_clusters_by_landmark` und die Schlüsselform
`cluster-<n>-<i>` entfallen. Alles übrige gilt unverändert — Haversine aus der Stdlib, Schwellen
als Modulkonstanten, keine Persistenz des Ortswerts eines Fotos, kein Name im Schlüssel,
Reverse-Geocoding außen vor, die Verwerfungsregeln in `extract_gps`.

## Entscheidung

### 1. Das Event ist eine Zeile, kein Schlüsselstring

Neue Tabelle `events`, je Zeile ein Event eines `CriterionScoringRun`: `position` (1-basiert,
chronologisch), `started_at`/`ended_at`, `landmark_name`, `place_kind`/`place_lat`/`place_lon`.
`PhotoRanking.cluster_key` wird durch `event_id` **ersetzt**, nicht ergänzt.

**Warum persistiert.** Nummer und Zeitspanne sind Bestandteil des **Namens** und müssen deshalb
unabhängig davon feststehen, welche Fotos eine Antwort gerade enthält — dieselbe
Teilmengen-Abhängigkeit, die ADR 0072 für den Ortsteil bereits als Fehlerquelle benannt hat. Das
ist kein Bruch mit „abgeleitete Werte nicht persistieren": ein Event ist ein **Lauf-Artefakt** wie
`PhotoRanking`, kein reiner Funktionswert über `photos`. Der Ortswert eines Fotos bleibt
unpersistiert (Punkt 4). Zwei Träger derselben Zugehörigkeit nebeneinander wären die „zweite,
driftende Abbildung", vor der ADR 0072 warnt; der Wechsel nimmt zugleich freien Text aus dem
Query-Parameter der Kuratierung heraus.

**Beide Spalten sind echte Fremdschlüssel, `event_id` ist NOT NULL.** Die Löschzusage aus ADR 0062
prüft Erreichbarkeit über die Kanten in `Base.metadata`; eine bloß logische Spalte fiele still
heraus. Nullbarkeit wertet sie dagegen **nicht** aus — **gemessen am 2026-09-12**: die Ableitung
liest ausschließlich `table.foreign_keys`, und das bestehende, nullable
`criterion_scoring_runs.remote_category_classification_run_id` ist ein voller Kantenzug. NOT NULL
ist deshalb eine fachliche, keine testgetriebene Festlegung.

**Altläufe bekommen keine Events, und die Migration löscht ihre Rangzeilen** (Daniels Entscheidung:
die Kuratierung zeigt für einen Altlauf nichts, bis er neu berechnet wird). Damit gilt
„überschneidungsfrei" ausnahmslos, ohne Ausnahmezweig in Lesepfad, Spec und Testkonzept — ein
nullable `event_id` wäre genau dieser Zweig, dauerhaft im Schema, für einen Zustand, den die
Anwendung selbst nie erzeugt.

**Die Lauf-Zeilen selbst bleiben unangetastet.** Sie tragen die Ist-Kosten der Cloud-Aufrufe; die
sind nicht wiederherstellbar. Rangzeilen sind es: ein erneuter Kriterien-Lauf liest Erkennungen aus
`photo_landmark_detections`/`photo_category_classifications` und kostet lokale Rechenzeit, kein
Geld.

### 2. Die Event-Bildung ist **ein** Durchlauf, und er sitzt nach der Cloud-Phase

Ort: `worker.py::run_criterion_scoring`, die Stelle von `refine_clusters_by_landmark` — nach der
Landmark-Phase, vor dem Aufbau der Partitionen. Alle Trennsignale wirken dort gleichrangig in einem
sortierten Durchlauf.

`run_project_scoring` bleibt **unverändert**: `assign_clusters`/`PhotoScore.cluster_key` sind
weiterhin die grobe Gliederung vor dem Ausschuss-Gate. Mehr braucht das Gate nicht, das Signal
„Sehenswürdigkeit wechselt" kann dort nicht wirken (die Erkennung läuft erst nach dem Gate, ADR
0021), und eine zweimal nach unterschiedlichen Signalmengen gebildete Gliederung hätte zwei
Wahrheiten über dieselbe Frage.

**Umfang:** die Kandidaten des Laufs. „Jedes Foto gehört zu genau einem Event" gilt in dieser Menge;
aussortierte Fotos haben auch heute keine Rangzeile.

### 3. Trennsignale sind eine Liste gleichrangiger Objekte, Frage und Fortschreibung getrennt

Ein Signal hat drei Methoden: `is_boundary(candidate) -> bool` (**rein**, ohne Zustandsänderung),
`begin(candidate)` (Rücksetzen an jeder Grenze), `advance(candidate)`. Der Durchlauf wertet
**alle** Signale aus, nie kurzgeschlossen, und ruft danach genau eine der schreibenden Methoden auf
allen auf. Diese Trennung ist der tragende Teil: nur sie erlaubt ein zustandsbehaftetes Signal
(Ausdehnung) neben einem paarweisen (Zeitlücke), ohne dass die Auswertungsreihenfolge zum
Bestandteil des Ergebnisses wird. Das Motivwechsel-Signal aus Story #427 ist danach eine Klasse und
ein Listeneintrag.

Die Sehenswürdigkeit wird dabei **vom Gruppierungsmerkmal zum Trennsignal**: Grenze ist der Übergang
auf einen anderen Namen. Namenlose Fotos lösen nie aus. Ein Name, der nach
`sanitize_landmark_name` leer oder länger als `MAX_LANDMARK_NAME_LENGTH` ist, gilt als **nicht
vorhanden** — er löst keine Grenze aus und wird nicht geschrieben. **Kein Abschneiden:** ein
gekürzter Name wäre eine Ortsbehauptung, die so nie erkannt wurde; das Event fällt auf Nummer und
Zeitspanne zurück.

### 4. Der übernommene Ort entsteht vor der Event-Bildung, projektweit — und bleibt unpersistiert

Bezugsmenge ist **jedes Foto des Projekts mit gemessener Koordinate**, nicht das Event (zirkulär)
und nicht die Kandidatenmenge (ein aussortiertes Foto trägt eine ebenso gültige Koordinate). Eine
Funktion, zwei Aufrufer — Worker und Lesepfad; zwei Herleitungen derselben Sache liefen an dem Tag
auseinander, an dem eine ihre Bezugsmenge ändert.

Die Bindung an `Photo.project_id` steht in **beiden** Aufrufern ausgeschrieben, im Worker abgeleitet
aus `CriterionScoringRun.project_id`. Ohne sie erbt ein Foto Koordinaten aus einem fremden Projekt.

`source` (`"exif"` | `"derived"`) trägt unverändert die Zusage, dass ein übernommener Ort nie als
gemessener ausgegeben wird. Der **Ortsbezug des Events** wird ausschließlich aus **gemessenen**
Koordinaten gebildet: eine Ortsaussage über eine Einheit darf nicht aus Schätzungen entstehen. Ein
Event ohne jede gemessene Koordinate trägt keinen Ortsbezug; seine Fotos zeigen ihren übernommenen
Ort trotzdem, als übernommen gekennzeichnet.

### 5. Die Ausdehnung ist die Diagonale der umschließenden Box, nicht der Durchmesser

`EVENT_EXTENT_MAX_METERS = 1000.0`, dokumentierte, **unkalibrierte** Modulkonstante im Muster von
`TIME_CLUSTER_GAP`. Größenordnung Stadtviertel, über der Streuung eines einzelnen Ortsbesuchs
(100–300 m) und über der Schrittschwelle von 500 m.

Gemessen wird die Haversine-Distanz der Eckpunkte der umschließenden Box aller Koordinaten des
laufenden Events, geprüft **einschließlich** des gerade betrachteten Fotos — sonst begänne das neue
Event ein Foto zu spät. Obere Schranke des Durchmessers bei konstantem Aufwand je Foto; der exakte
Durchmesser wäre quadratisch. Zwei bewusste Kehrseiten: die Schranke trennt etwas früher, und eine
Box über den 180. Längengrad fällt maximal groß aus — die Ausfallrichtung ist „trennt", nicht
„behauptet einen Ort".

Die Tagesgrenze braucht keine Zahl: verglichen wird der Kalendertag zweier aufeinanderfolgender
Aufnahmen über die ersten zehn Zeichen des Zeitstempels. `taken_at` ist zonenlos; eine
Zeitzonen-Umrechnung hinge an der Umgebung des ausführenden Prozesses.

### 6. Das Event ersetzt `cluster_place` in der Antwort

`PhotoOut.cluster_place` entfällt und geht in `PhotoOut.event` auf (`id`, `position`, `started_at`,
`ended_at`, `place`); `RankingOut.cluster_key` wird zu `RankingOut.event_id`. Der brechende
Feldwechsel ist beabsichtigt, wie schon bei `ranking` → `rankings`. `PhotoOut.location` bleibt
unverändert. Das Backend liefert weiterhin **keine fertige Überschrift**, sondern ihre Teile.

Drei Zusagen, die persistiert driften können und deshalb geprüft gehören:

- **Feldkombination:** `place_kind='landmark'` ⇒ `landmark_name` gesetzt; `'coordinate'` ⇒ beide
  Koordinaten gesetzt; `'multiple'` ⇒ beide Koordinaten **NULL** — es gibt den einen Ort, den sie
  vertreten müssten, gerade nicht. Koordinaten werden **gerundet** geschrieben, nie in voller
  Präzision „für später".
- **Unbekannter Wert:** `place` ist `None`, wenn `place_kind` NULL oder nicht aus dem Vorrat ist —
  Mitgliedschaftsprüfung statt Cast, sonst legt ein einzelner Wert die Listenantwort auf 500.
- **Laufbindung:** `event_id` ist ein **globaler** Surrogatschlüssel. Das Laufprädikat steht in
  **jeder** Abfrage des Kandidaten-Endpunkts, die Zählabfrage hinter `total` eingeschlossen; der
  Parameter bekommt neben der Unter- auch eine **Obergrenze**. Ohne das Prädikat ist die
  Ausfallrichtung unauffälliger, nicht harmloser: kohärente Fotos eines fremden Projekts.

## Konsequenzen

- Eine Migration, die Daten löscht (`photo_rankings` der Altläufe) und nicht rückholbar ist. Eine
  Tabelle mehr in `project_deletion.py` (nach `photo_rankings`, vor `criterion_scoring_runs` —
  gemessen aus `Base.metadata`) und in den beiden Vollständigkeitstests.
- Die Kuratierung zeigt bis zum nächsten Kriterien-Lauf nichts. Der Leerzustand der Ansicht muss
  diesen Fall tragen: ein erfolgreicher Lauf **ohne** Rangzeilen ist neu.
- `scoring.py::refine_clusters_by_landmark` entfällt samt Tests; die neue Logik lebt in einem
  eigenen Modul `events.py`, weil `scoring.py` Phase A ist.
- Der Partitionsschlüssel wechselt von `(cluster_key, category_key)` zu `(event_id, category_key)`.
- Die Tageszeit-Bezeichnungen der Überschrift entfallen (`timeOfDayBucketLabel` wird unbenutzt). Eine
  Koordinate erscheint nicht mehr als Name; der Ortsbezug bleibt in der Antwort und wird mit
  Reverse-Geocoding wieder zu einem Namen.
- `docs/architecture.md` zieht im selben Pull Request nach.
