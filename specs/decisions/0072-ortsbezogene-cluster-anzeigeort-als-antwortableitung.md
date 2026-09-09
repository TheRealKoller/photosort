# 0072 - Ortsbezogene Cluster: der Cluster-Ort als Server-Aggregat, Sehenswürdigkeit aus der Persistenz, 500 m Trennabstand

**Status:** Accepted
**Datum:** 2026-09-09
**Bezug:** [`decisions/0029-gps-landmark-cluster-bildung.md`](./0029-gps-landmark-cluster-bildung.md) (die zweiphasige Cluster-Bildung selbst — gilt unverändert weiter, siehe Abgrenzung unten), [`decisions/0021-kriterien-datenmodell-kuratierungs-pipeline.md`](./0021-kriterien-datenmodell-kuratierungs-pipeline.md) (Ownership-Grenze `PhotoScore` vs. `PhotoRanking`), [`decisions/0049-festes-kategorien-set-mit-vorrangreihenfolge-und-freien-feinlabels.md`](./0049-festes-kategorien-set-mit-vorrangreihenfolge-und-freien-feinlabels.md)/[`decisions/0069-nebenkategorien-mehrfachzugehoerigkeit-und-konfidenzgewichtete-rangfolge.md`](./0069-nebenkategorien-mehrfachzugehoerigkeit-und-konfidenzgewichtete-rangfolge.md) (die Stelle, an der ADR 0029 die Landmark-Verfeinerung verorten wollte, ist seither eine andere), [`decisions/0071-kuratierung-stabile-auswahl-ohne-backfill-und-einsehbarer-vorrat.md`](./0071-kuratierung-stabile-auswahl-ohne-backfill-und-einsehbarer-vorrat.md) (Top-N-Auswahl + Nachladen in einer eigenen Abfrage — der Grund, warum der Cluster-Ort nicht im Frontend entstehen kann), [`features/0039-kuratierung-tage-und-benannte-cluster.md`](../features/0039-kuratierung-tage-und-benannte-cluster.md) (die bestehende, rein clientseitige Cluster-Überschrift), [`features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md`](../features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md) (Quelle der Namen, inzwischen umgesetzt), [`features/0051-gps-landmark-cluster-bildung.md`](../features/0051-gps-landmark-cluster-bildung.md) (Accepted, Issue #169).

## Kontext

ADR 0029 hat die Struktur der ortsbezogenen Cluster-Bildung entschieden, wurde aber geschrieben, als die Sehenswürdigkeit-Erkennung (Spec 0047) noch nicht umgesetzt war und die Kriterien-Pipeline anders aussah als heute. Vor der Umsetzung von Spec 0051 sind drei Annahmen von ADR 0029 nicht mehr tragfähig, ein vierter Punkt war dort ausdrücklich offen gelassen, und zwei weitere Fragen stellen sich erst durch den heutigen Code:

1. ADR 0029 verortete die Landmark-Verfeinerung „an exakt der Stelle, an der heute schon `derive_active_categories` läuft". Dieses Paar ist mit ADR 0049 ersatzlos entfallen; die Kategorieableitung ist seither eine reine Pro-Foto-Funktion, und seit ADR 0069 erzeugt dieselbe Schleife mehrere Zugehörigkeiten je Foto.
2. ADR 0029 nahm eine laufinterne In-Memory-Abbildung `landmark_name_by_photo` an. Seit Spec 0047 umgesetzt ist, steht der Name dauerhaft in `photo_landmark_detections` — ein Lauf ohne Cloud-Phase hätte mit der In-Memory-Annahme keinen einzigen Namen gesehen, obwohl die Namen längst vorliegen.
3. ADR 0029 nannte die API-Form der Ortsdarstellung „Implementierungsdetail". Mit ADR 0071 ist sie das nicht mehr (siehe Entscheidung 1).
4. `GPS_CLUSTER_SPLIT_DISTANCE_METERS` stand in ADR 0029 als unverbindlicher „Vorschlag: 2000.0".
5. Das EXIF-GPS-Feld kennt zwei Fehlerbilder, die kein Parserfehler sind und deshalb von einem `except Exception` nicht erfasst werden (Entscheidung 6).
6. `cluster_key` ist projektübergreifend derselbe String und `PhotoRanking` trägt keine `project_id` — eine clusterweite Abfrage braucht deshalb eine ausgeschriebene Laufbindung (Entscheidung 7).

## Abgrenzung zu ADR 0029

ADR 0029 bleibt **`Accepted` und in ihrem Kern unberührt**: die zweiphasige Cluster-Bildung ohne neuen Job, die bewusste Divergenz `PhotoScore.cluster_key` ≠ `PhotoRanking.cluster_key`, Haversine aus der Stdlib ohne neue Abhängigkeit, Schwellenwerte als Modulkonstanten, keine Persistenz abgeleiteter Ortswerte und Reverse-Geocoding als Out-of-Scope gelten unverändert. Diese ADR ersetzt keine Aussage von ADR 0029, sondern füllt die Lücken, die der veränderte Code hinterlassen hat.

## Entscheidung

### 1. Der Ort eines CLUSTERS und der Ort eines FOTOS sind zwei getrennte Antwortfelder — der Cluster-Ort ist ein Server-Aggregat

`PhotoOut` bekommt **zwei** additive, optionale Felder:

- **`location`** — der Ort **dieses Fotos**: `lat`, `lon` (volle EXIF-Präzision, keine serverseitige Rundung — Daniels Entscheidung, siehe Security-Abschnitt der Spec) und `source` (`"exif"` für die eigene Koordinate, `"derived"` für die vom zeitlich nächstgelegenen Foto mit Koordinate im selben Cluster übernommene). `null`, wenn das Foto weder eine eigene noch eine herleitbare Koordinate hat. Dieses Feld ist die Auslieferung des Akzeptanzkriteriums „Ort für Fotos ohne eigene Ortsangabe" und ausdrücklich **nicht** die Grundlage der Cluster-Überschrift.
- **`cluster_place`** — der bereits **aufgelöste** Ort des Clusters, auf jedem Foto desselben Clusters identisch: `kind` (`"landmark"` | `"coordinate"` | `"multiple"`), dazu `landmark_name` bei `"landmark"` bzw. `lat`/`lon` **auf zwei Nachkommastellen gerundet** bei `"coordinate"`. `null`, wenn der Cluster gar keine Ortsinformation trägt — dann sieht die Überschrift zeichengleich aus wie heute.

Beide Felder werden zur Anfragezeit über den **vollständigen** Cluster des Bezugslaufs berechnet, keines wird persistiert.

**Warum der Cluster-Ort nicht im Frontend entstehen kann.** Die Kuratierungsansicht bildet ihre Überschrift heute in `CurateCategoriesPage.tsx::groupByClusterAndCategory()` aus `items` — und `items` enthält je Partition nur `rank_position <= topN` (ADR 0071, Entscheidung 1). Die auf Abruf nachgeladenen Kandidaten laufen über eine **eigene** Abfrage in `CurationCandidates.tsx` und fließen nie in `items` zurück. Jede Aussage, die eine Aggregation über den Cluster ist, wäre im Frontend deshalb dauerhaft eine Aussage über die Top-N — und zusätzlich sprunghaft, weil `topN` ein Suchparameter der Seite ist (`curationTopN.ts`, 1–10). Betroffen sind **beide** Bestandteile des Ortsteils, nicht nur einer:

- *„Mehrere Orte"* ist per Definition ein Vergleich aller Koordinaten des Clusters. Über die Top-N gebildet, verschwiege er jede Abweichung, die weiter hinten im Vorrat liegt.
- *Der Sehenswürdigkeit-Name* ebenso: trägt im Cluster nur ein Foto auf Rang 12 eine Erkennung, bliebe der Cluster in der Überschrift dauerhaft unbenannt, obwohl der Name vorliegt.

Ein Feld pro Foto — auch das vom test-engineer vorgeschlagene `multiple_places: bool` — löst nur den ersten der beiden Fälle und lässt den zweiten offen. Deshalb wird nicht ein Flag ergänzt, sondern der **fertig aufgelöste Zustand** ausgeliefert: `kind` benennt, welche Stufe der Rangfolge (erkannte Sehenswürdigkeit → ungefähre Koordinate → mehrere Orte) tatsächlich gilt. Damit bildet das Frontend die Rangfolge nicht nach, und der Fall `"multiple"` kann strukturell keine stellvertretende Koordinate mitführen: er hat keine.

**Warum zwei Felder und nicht eines.** Sie beantworten verschiedene Fragen und tragen verschiedene Präzision: `location` ist die volle Koordinate genau dieses Fotos, `cluster_place` die gerundete, gemeinsame Ortsaussage seines Clusters. Sie zu einem Feld zu verschmelzen hieße, entweder die Pro-Foto-Herleitung zu verlieren (die ein eigenes Akzeptanzkriterium ist) oder auf jedem Foto eine Koordinate zu führen, die je nach Cluster mal seine eigene und mal die des Clusters ist. Dasselbe Nebeneinander gibt es bereits bei `RankingOut.rank_position` und `.curation_position`, aus derselben Begründung. Dass `cluster_place` auf allen Fotos eines Clusters identisch wiederholt wird, ist ebenfalls kein neues Muster, sondern genau das von `RankingOut.partition_size` (lauf-globales Aggregat, auf jeder Zeile wiederholt).

**Warum der Sehenswürdigkeit-Name nur in `cluster_place` steht.** Er ist für die Überschrift eine Cluster-Aussage; ein zweites Mal pro Foto ausgeliefert wäre er eine zweite Abbildung derselben Sache, die driften kann. Die in Spec 0047 gesetzte Grenze „kein UI-Verweis in v1" wird damit exakt so weit aufgehoben, wie ADR 0029 Punkt 6 es vorsah — für den Cluster-Namenszweck, nicht weiter.

**Warum trotzdem keine Persistenz.** Unverändert ADR 0029, Punkt 3: beide Werte sind aus `Photo.gps_lat`/`.gps_lon`, `photo_landmark_detections` und der Cluster-Zugehörigkeit jederzeit günstig neu berechenbar und haben keinen manuell editierbaren Anteil. Der Preis ist ein zusätzlicher Query je Anfrage; er liegt in derselben Größenordnung wie das bereits vorhandene `_partition_sizes`.

**Was das für die Überschrift bedeutet.** Sie bleibt eine Frontend-Ableitung — aber nur noch in ihrer Zusammensetzung, nicht mehr in ihrer Ermittlung: Tag, Tageszeit und Zeitspanne entstehen unverändert aus den sichtbaren Fotos (Spec 0039, Früheste-Foto-Regel), der Ortsteil wird fertig aufgelöst übernommen. Das Backend liefert weiterhin keine fertige Überschrift und kennt keinen Cluster-Namen.

### 2. Sehenswürdigkeit-Namen kommen aus `photo_landmark_detections`, nicht aus dem laufenden Lauf

Die Verfeinerungsfunktion bekommt ihre Namen aus einem Lesezugriff auf die persistierte Tabelle über die Kandidaten des Laufs — dasselbe Muster wie `_remote_category_evidence` für die Remote-Kategorien. Sie wirkt damit auch in einem Lauf, in dem die Cloud-Phase gar nicht lief (Einwilligung aus, Cloud-Häkchen abgewählt, oder alle Fotos bereits in einem früheren Lauf erkannt), und ein erneuter Kriterien-Lauf teilt dieselben Cluster wieder gleich auf. Die In-Memory-Variante aus ADR 0029 hätte die Aufteilung still an die Frage gekoppelt, ob im **selben** Lauf zufällig Geld ausgegeben wurde.

### 3. Verfeinerte Cluster-Schlüssel sind indexbasiert, nicht namensbasiert

Ein aufgeteilter Basis-Cluster erzeugt `cluster-3-1`, `cluster-3-2`, … — je ein Suffix pro erkanntem Namen, in alphabetischer Reihenfolge der Namen vergeben (deterministisch ohne Zeitstempel-Kenntnis). Fotos ohne Namen behalten den unveränderten Basis-Schlüssel `cluster-3`.

**Warum kein Name im Schlüssel?** `cluster_key` ist ein Partitionsschlüssel, der als Query-Parameter an `GET /projects/{id}/curation-candidates` zurückläuft (`_MAX_PARTITION_KEY_LENGTH`) und im Frontend als React-Key sowie in zusammengesetzten Zustandsschlüsseln dient. Freier, extern erzeugter LLM-Text an dieser Stelle wäre eine unnötige zweite Verwendung derselben Zeichenkette mit anderen Anforderungen (Länge, Trennzeichen, Sanierung). Der Name gehört in die Anzeige, nicht in den Schlüssel.

### 4. `GPS_CLUSTER_SPLIT_DISTANCE_METERS = 500.0`

Statt der 2000,0 aus dem unverbindlichen Vorschlag in ADR 0029; von Daniel bestätigt. Der auslösende Fall der Spec ist „zwei Sehenswürdigkeiten kurz hintereinander"; innerstädtisch liegen die typischerweise einige hundert Meter auseinander (Eiffelturm ↔ Trocadéro ≈ 700 m), womit 2000 m genau den benannten Fall nicht getrennt hätte. 500 m liegt zugleich sicher oberhalb der Streuung eines einzelnen Ortsbesuchs (Umherlaufen plus GPS-Ungenauigkeit, in der Größenordnung 100–300 m).

Bekannte Kehrseite, bewusst in Kauf genommen: Aufnahmen aus einem fahrenden Fahrzeug erzeugen viele kleine Cluster. Der Wert bleibt eine dokumentierte, unkalibrierte Modulkonstante in `scoring.py` (ADR 0029, Punkt 5) — die Kalibrierung ist wie bei `SHARPNESS_REJECT_THRESHOLD` ein manueller Stichproben-Review an echten Fotos, kein Testfall.

### 5. Klarstellung: der Distanzvergleich läuft gegen das letzte Foto **mit** Koordinate im laufenden Cluster

Nicht gegen den unmittelbaren zeitlichen Vorgänger. ADR 0029 („Fotos ohne eigene GPS-Daten werden übersprungen") meint genau das; die Formulierung des Akzeptanzkriteriums („zwei zeitlich aufeinanderfolgende Fotos") lädt zur strengeren Lesart ein, unter der ein einziges Foto ohne Koordinate zwischen zwei weit auseinanderliegenden Aufnahmen die Trennung vollständig unterdrückte. Das Kriterium „ein Foto ohne eigene Ortsangabe löst nie selbst eine Trennung aus" bleibt gewahrt: die Trennung entsteht am nächsten Foto, das selbst eine Koordinate trägt. Die Referenz wird an jeder Cluster-Grenze zurückgesetzt, damit nie über eine Grenze hinweg verglichen wird.

### 6. Zwei Werte gelten beim Einlesen als „kein Ort", obwohl sie technisch lesbar sind

Beide Regeln gehören in `extract_gps` selbst, nicht in die Verbraucher: was hier verworfen wird, erreicht die Datenbank gar nicht erst, und keine spätere Stelle muss die Ausnahme kennen.

- **Exakt `(0.0, 0.0)`** wird verworfen. Ein GPS-IFD, das vollständig mit Nullen gefüllt ist, ist ein bekanntes Kamera-/Software-Artefakt („Null Island") und keine Ortsangabe. Ohne diese Regel risse ein einziges solches Foto jedes Cluster auf, in dem es liegt — und zwar zweimal, beim Hinein- und beim Hinauslaufen, weil `(0,0)` von jedem realen Aufnahmeort tausende Kilometer entfernt liegt. Verworfen wird ausschließlich der exakte Doppel-Nullwert; der reale Punkt im Golf von Guinea ist der bewusst in Kauf genommene, dokumentierte Verlust.
- **Ein fehlender `GPSLatitudeRef`/`GPSLongitudeRef`** ergibt `None` statt der Annahme „Nord/Ost". Die Referenz ist im EXIF-Standard verpflichtend; fehlt sie, ist der Datensatz unvollständig. Sie zu raten hieße, eine Aufnahme der Südhalbkugel oder westlich des Nullmeridians mit einer *falschen*, aber plausibel aussehenden Koordinate zu führen — die sowohl Cluster falsch trennte als auch eine falsche Ortsangabe anzeigte. „Kein Ort" ist ein Zustand, den das Produkt an jeder Stelle sauber behandelt; „falscher Ort" ist es nicht. Das deckt sich mit dem Akzeptanzkriterium „fehlt die Ortsangabe oder ist sie unlesbar, gilt das Foto als ohne Ort".

### 7. Jede clusterweite Ortsabfrage trägt die Laufbindung ausgeschrieben

`PhotoRanking` hat keine `project_id`, und `cluster_key` ist `cluster-<n>` — je Lauf neu vergeben und **in jedem Projekt derselbe String**. Die einzige Bindung eines Clusters an sein Projekt ist `criterion_scoring_run_id` aus `_latest_successful_criterion_scoring_run_id(session, project_id)`. Eine Abfrage, die Koordinaten „aller Fotos in `cluster-0`" holt, ohne dieses Prädikat auszuschreiben, liefert deshalb Koordinaten aus fremden Projekten — und zwar genau bei der Datenklasse, die dieses Feature erstmals überhaupt exponiert. Dieselbe Auflage steht bereits am Endpunkt `curation_candidates` (Spec 0357, Muss-Kriterium 2); sie gilt ab hier ausdrücklich auch für die Orts-Hilfsfunktion. `_photos_by_id` filtert nur nach Id und ist ausdrücklich **keine** zweite Verteidigungslinie.

## Konsequenzen

- `PhotoOut` bekommt zwei additive Felder; kein bestehendes Feld ändert Form oder Bedeutung. Beide sind optional mit Vorgabewert `null`, damit bestehende Testfixtures unverändert bleiben.
- Drei Lesepfade liefern die Felder (`list_photos` in beiden Modi, `curation_candidates`) — Herleitung und Aggregation gehören deshalb in **eine** Hilfsfunktion mit **einer** Abfrage, nicht in drei Aufrufstellen.
- Die Rundung auf ~1 km findet ausschließlich im Backend statt, weil dort auch die Entscheidung „eine Koordinate oder mehrere Orte" fällt. Beides aus derselben Zahl abzuleiten verhindert, dass Anzeige und Zustandsurteil auseinanderlaufen; das Frontend formatiert nur noch (zwei Nachkommastellen, `-0.0` als `0.0`).
- **Kein Nachzug des Bestands (Daniels Entscheidung).** Bereits gescannte Fotos bekommen keine Koordinaten, weil der Scan jede Datei mit unverändertem `Etag` überspringt (`worker.py::_classify_scan_entries`) und die Cache-Varianten ihr EXIF verloren haben (`thumbnails.py::generate_variants`). Koordinaten entstehen ausschließlich für ab jetzt neu eingelesene oder auf OpenCloud geänderte Dateien. Keine Markerspalte, kein zusätzlicher Arbeitsposten im Scan — die Grenze wird in Spec 0051 im Architektur-Abschnitt und unter „Out of Scope" dokumentiert, statt umgangen.
- `docs/architecture.md` (Owner: `architect`) wird im selben Pull Request um die beiden neuen `Photo`-Spalten, die orts- und namensbezogene Cluster-Bildung, die beiden neuen `PhotoOut`-Felder und die dokumentierte `PhotoScore`/`PhotoRanking`-Divergenz ergänzt.
