# 0071 - Kuratierung: stabile Auswahl ohne Backfill, sichtbarer und einsehbarer Kandidatenvorrat

**Status:** Accepted
**Datum:** 2026-09-09
**Bezug:** [`decisions/0021-kriterien-datenmodell-kuratierungs-pipeline.md`](./0021-kriterien-datenmodell-kuratierungs-pipeline.md) (Punkt 4, Backfill-Teil — dort als teilweise abgelöst vermerkt), [`decisions/0069-nebenkategorien-mehrfachzugehoerigkeit-und-konfidenzgewichtete-rangfolge.md`](./0069-nebenkategorien-mehrfachzugehoerigkeit-und-konfidenzgewichtete-rangfolge.md) (Punkt 8, Definition von `curation_position` — ebenfalls dort vermerkt), [`decisions/0067-modellkonfidenz-je-kategorie-anzeige-und-auswertung.md`](./0067-modellkonfidenz-je-kategorie-anzeige-und-auswertung.md), [`features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md`](../features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md), [`features/0040-bewertungsdetails-info-popover.md`](../features/0040-bewertungsdetails-info-popover.md), [`features/0300-nebenkategorien.md`](../features/0300-nebenkategorien.md), [`features/0357-voller-bildvorrat-kuratierung.md`](../features/0357-voller-bildvorrat-kuratierung.md)

## Kontext

Die Kuratierungsansicht (`GET /projects/{id}/photos?top_n_per_category=N`) liefert je Partition (`cluster_key` × `category_key`) des letzten erfolgreichen `CriterionScoringRun` die besten N Zugehörigkeiten — **nach Ausschluss der vom anfragenden Nutzer verworfenen Fotos**. Das ist der Backfill aus ADR [`0021`](./0021-kriterien-datenmodell-kuratierungs-pipeline.md) Punkt 4: `row_number()` läuft erst nach dem `REJECTED`-Filter, ein verworfenes Foto macht dadurch automatisch für das nächste Platz, ohne dass Server-Code aktiv nachrückt.

Genau dieses Verhalten macht die Kernschleife des Produkts schwer bedienbar (Story #357):

1. **Die Entscheidung läuft gegen eine unsichtbare Restmenge.** Die Ansicht sagt nirgends, wie groß der Kandidatenvorrat einer Kategorie oder eines Clusters ist. Wer verwirft, weiß nicht, ob er die letzte Alternative wegwirft oder eine von vierzig.
2. **Der Backfill nimmt die Rückmeldung über die eigene Handlung.** Das verworfene Foto verschwindet, ein fremdes rückt an dieselbe Stelle — man sieht weder, was man entschieden hat, noch dass der Vorrat kleiner geworden ist.
3. **Der Vorrat ist überhaupt nicht einsehbar.** Alles jenseits von N (Obergrenze 10) existiert als `PhotoRanking`-Zeile, ist aber über keine Leseoperation erreichbar.

Punkt 1 und 3 sind Lücken; Punkt 2 ist eine bewusste, jetzt widerrufene Entscheidung. Das Datenmodell steht dem nicht im Weg — im Gegenteil: die Grundentscheidung aus ADR 0021 Punkt 4 (den **vollen** sortierten Kandidatenpool persistieren, nicht nur die Top-N) ist die Voraussetzung dafür, dass diese ADR ohne Migration auskommt.

## Entscheidung

### 1. Der Ablehnungsfilter fällt aus der Kuratierungsabfrage — die Auswahl wird eine Eigenschaft des Laufs, nicht des Betrachters

`api/photos.py::_top_n_per_category_photo_ids` verliert den Outer-Join auf `Rating` und damit den `REJECTED`-Ausschluss. Ausgewählt werden die Zugehörigkeiten mit `rank_position <= N` je Partition.

Damit entfällt zugleich die Fensterfunktion. `PhotoRanking.rank_position` ist je Partition lückenlos ab 1 vergeben (`ranking.py::rank_photos` gibt `index + 1` über die vollständige Partition zurück; `worker.py::run_criterion_scoring` ruft sie je Partition auf, Haupt- wie Nebenzugehörigkeiten in derselben Liste; `worker.py::reassign_photo_category` vergibt bei einem Kategorie-Override die Positionen beider betroffener Partitionen vollständig neu). Ein `row_number()` über dieselbe Sortierung liefert deshalb per Konstruktion denselben Wert — es hat ausschließlich die Lücken geschlossen, die der Ablehnungsfilter riss.

**Die Kernaussage:** Welche Fotos die Ansicht zeigt, hängt danach ausschließlich vom Lauf ab. Es ändert sich nur noch durch einen neuen Kriterien-Lauf oder einen Kategorie-Override — nicht mehr durch die Bedienung der Ansicht selbst. Das ist die technische Fassung von "es rückt nichts nach".

**Die Antwort wird dadurch nicht nutzerunabhängig** — dieser naheliegende Schluss ist falsch und wäre teuer: `_to_photo_out` blendet `PhotoOut.suggestion` genau dann ein, wenn der **anfragende** Nutzer noch keine eigene `Rating`-Zeile für dieses Foto hat (`has_own_rating`). Diese Regel gilt in beiden Query-Modi, wird hier nicht angefasst, und zwei Nutzer bekommen für dasselbe Foto weiterhin verschiedene Antwortkörper. Was der Wegfall des Ablehnungsfilters ändert, ist ausschließlich die **Quelle** dieser Abhängigkeit — siehe Entscheidung 2.

### 2. `curation_position` bleibt, mit geschärfter Bedeutung

Das Feld ist seit ADR 0069 Punkt 8 die **einzige** Auskunft darüber, unter welchen ihrer Kategorien die Ansicht ein Foto zeigen soll (ein Foto steht seit Spec 0300 in mehreren Partitionen, `PhotoOut.items` enthält es aber nur einmal). Diese Rolle bleibt unverändert und ist weiterhin nötig; das Frontend darf die Auswahlregel nicht nachbilden.

Was sich ändert, ist die Definition des Wertes: nicht mehr "der Platz in der um die eigenen Ablehnungen bereinigten Auswahl", sondern schlicht **der Platz dieser Zugehörigkeit in der angezeigten Auswahl ihrer Kategorie** — nach Entscheidung 1 identisch mit `rank_position`, solange die Zugehörigkeit zur Auswahl gehört, sonst `null`. Die Unterscheidung zu `rank_position` bleibt trotzdem bestehen und ist keine Formalie: `rank_position` ist die lauf-globale Rangaussage (Info-Popover), `curation_position` die Zugehörigkeit zur angeforderten Auswahl. Die zweite ist vom Query-Parameter abhängig, die erste nicht.

**Die Sicherheitsauflage aus ADR 0069 Punkt 8 wird verlegt, nicht aufgehoben.** Sie hing dort an `curation_position` und lautete: der Wert wird nie persistiert und nie über Requests hinweg zwischengespeichert, weil er die Ablehnungen des Anfragenden abbildet und für den jeweils anderen Nutzer ein Leck wäre. Diese *Begründung* fällt — ohne Ablehnungsfilter ist der Wert nicht mehr nutzerabhängig. Die *Auflage* fällt nicht, weil sie eine zweite, davon unabhängige Ursache hat: `PhotoOut.suggestion`. Sie wandert deshalb an die Stelle, an der sie tatsächlich hängt — an den **Antwortaufbau** (`_to_photo_out`/`list_photos`) statt an ein einzelnes Feld — und lautet dort: *Bekommt `GET /projects/{id}/photos` oder der Kandidaten-Endpunkt je eine Antwort-Zwischenspeicherung, ein `ETag` oder ein `Cache-Control` über `no-store` hinaus, muss der Schlüssel den Nutzer enthalten.*

Das ist kein theoretischer Vorbehalt: Das Frontend ist eine PWA mit Workbox (`registerType: 'autoUpdate'`), heute ohne `runtimeCaching` für API-Antworten — dessen Ergänzung ist der naheliegende nächste Schritt. Der Service-Worker-Cache ist pro Browserprofil geteilt, das JWT liegt in `localStorage`; ein nutzerloser Cache-Schlüssel zeigte dem zweiten Nutzer die Vorschläge des ersten. Eine Auflage, die beim Umzug ihrer Begründung verloren geht, ist die Sorte Regel, die genau dann fehlt, wenn sie gebraucht wird.

**Verworfen: das Feld durch ein `in_selection: bool` ersetzen oder ganz streichen.** Streichen zwänge das Frontend, `rank_position <= topN` selbst zu rechnen — genau die Nachbildung der Auswahlregel, die ADR 0069 Punkt 8 ausdrücklich vermeidet. Ein Umbenennen wäre eine Schema-Änderung an einem gerade erst eingeführten Feld, ohne dass ein Konsument davon profitierte (der einzige liest es auf `!== null`).

### 3. Verworfen ist ein Anzeigezustand, kein Filterkriterium

Das verworfene Foto bleibt in der Antwort und trägt seinen Zustand dort, wo er im Produkt immer steht: in `PhotoOut.ratings[]`. Die Ansicht liest ihn mit der bestehenden `utils/ownRating.ts::ownRatingStatus` (`username` aus dem JWT-Claim, wie in Raster- und Detailansicht) und gibt ihn an die bestehende `PhotoCard`-Prop `status` weiter, die "aussortiert" bereits vollständig darstellt: gedämpfte Bildfläche, `RatingBadge` mit `x-circle` und Produktwort, durchgestrichener Dateiname. Kein neues Feld, kein neues Bauteil, keine neue Farbe — ein eigener Verworfen-Marker nur für die Kuratierung wäre eine zweite Darstellung desselben Zustands und müsste die Mehrfachcodierung des Design-Systems ein zweites Mal von Hand nachbauen.

### 4. Beide Mengenangaben werden abgeleitet — die Cluster-Zahl ist die Summe der Kategorie-Zahlen

Die Story verlangt eine Zahl je Kategorie-Überschrift und eine je Cluster-Überschrift, jeweils über den **vollständigen** Kandidatenbestand (unabhängig von Anzeige und Verwerfen).

- **Kategorie-Zahl = `RankingOut.partition_size`**, unverändert übernommen. Es zählt seit Spec 0300 ausdrücklich **alle** Zeilen der Partition, Haupt- wie Nebenzugehörigkeiten — "wie viele Fotos stehen in dieser Kategorie dieses Clusters", und dort steht ein Foto mit Nebenzugehörigkeit tatsächlich. Lauf-global, nicht nutzerspezifisch gefiltert, also genau der geforderte Bestand.
- **Cluster-Zahl = Summe der `partition_size`-Werte** der Kategorien dieses Clusters, im Frontend gebildet.

Das Antwortschema bleibt damit unverändert, und es entsteht keine zweite serverseitig gepflegte Zahl neben `partition_size`.

**Die Folge ist ausgesprochen, nicht versteckt:** Ein Foto, das im selben Cluster in zwei Kategorien steht, zählt in der Cluster-Zahl doppelt. Die Zahl beantwortet damit nicht "wie viele Fotos enthält dieser Moment", sondern "wie viele Vorschlagsplätze stehen hier zur Sichtung" — und das ist genau das, was der Nutzer vor sich sieht: die Kachel erscheint tatsächlich zweimal, in beiden Kategorien, jeweils einzeln zu beurteilen. **Beide Zahlen tragen deshalb die Beschriftung "Kandidaten", nicht "Fotos"** (endgültige Wortwahl beim `ux-ui-designer`). Das ist keine Kosmetik, sondern der Träger der Entscheidung: Unter der Beschriftung "Fotos" wäre die Zahl schlicht falsch.

**Verworfen: die Zahl der eindeutigen Fotos** (`COUNT(DISTINCT photo_id)` je `cluster_key`, ausgeliefert als zusätzliches `RankingOut.cluster_size`). Ihr Argument war die Anschlussfähigkeit an die Tages-Überschrift, die seit Spec 0300 (Akzeptanzkriterium 26) ausdrücklich eindeutige Fotos zählt und "N Fotos" beschriftet ist — zwei Zählweisen hinter demselben Wort in einer Ansicht wären ein Fehler. **Daniel hat sich in Kenntnis dieser Folge dagegen entschieden** (Produktentscheidung, gegen die Empfehlung des `architect`): Die Summe ist die Zahl, die zur Ansicht passt, in der jede Zugehörigkeit einzeln bewertet wird, und sie kostet weder ein Antwortfeld noch eine zusätzliche Aggregation. Der Konflikt mit der Tages-Zahl wird stattdessen über die **Beschriftung** aufgelöst: "Fotos" oben, "Kandidaten" auf den beiden Ebenen darunter — verschiedene Wörter für verschiedene Größen, statt derselben Beschriftung für zwei Bedeutungen.

**Die Tages-Zahl bleibt deshalb unangetastet** (eindeutige Fotos, wie in Spec 0300 festgelegt). Sie ändert durch diese ADR nur ihr Verhalten, nicht ihre Bedeutung: Weil verworfene Fotos in der Antwort bleiben (Entscheidung 3), schrumpft sie beim Arbeiten nicht mehr.

### 5. "Weitere Kandidaten" ist ein eigener Lese-Endpunkt

`GET /projects/{project_id}/curation-candidates?cluster_key=…&category_key=…&after_rank=N&limit=…&offset=…` liefert die Zugehörigkeiten **einer** Partition mit `rank_position > after_rank`, aufsteigend nach `rank_position`, als `PhotoListOut` (`total` = Restmenge der Partition). Bezugslauf ist derselbe wie in der Hauptabfrage. `curation_position` wird dabei ausschließlich für die **angefragte** Zugehörigkeit gesetzt — sonst erschiene ein nachgeladenes Foto zusätzlich unter seinen anderen Kategorien, obwohl dort niemand aufgeklappt hat.

Drei Alternativen wurden verworfen:

- **Den vollen Pool immer mitliefern und im Frontend schneiden.** Die Antwort umfasst heute N × Partitionsanzahl Zugehörigkeiten; der volle Pool sind alle Ausschuss-Überlebenden des Projekts, jedes Foto mit Kriterien-Werten, Feinlabels, Kandidaten- und Zugehörigkeitsliste. Das lädt für den Normalfall (zugeklappt) ein Vielfaches der Daten, die nie angesehen werden.
- **`list_photos` um `cluster_key`/`category_key` erweitern.** Der Endpunkt trägt bereits einander ausschließende Modi und die ausdrückliche Zusage, dass im Kuratierungsmodus `limit`/`offset` nicht gelten. Ein Sonderfall, in dem sie doch wieder gelten, macht aus einer klaren Zusage eine Ausnahmeregel.
- **Ein Endpunkt ohne Seitenweise mit stillem Server-Deckel.** Die Größe einer Partition ist durch nichts im Produkt beschränkt; ein Deckel verschwiege den Rest — genau das Verhalten, gegen das diese Story antritt. Die Seitenweise ist deshalb dieselbe wie im Standard-Listing (`limit` 60, ≤ 200), mit `total`.

**Die Projektbindung des Endpunkts läuft ausschließlich über die Lauf-Id.** `PhotoRanking` trägt keine `project_id`; `cluster_key` ist projektübergreifend derselbe Bezeichner (`cluster-<n>`, je Lauf neu vergeben) und `category_key` stammt aus einem festen, global gleichen Set. Die einzige Bindung an das Projekt des Pfadparameters ist `criterion_scoring_run_id` aus `_latest_successful_criterion_scoring_run_id(session, project_id)`. Dieses Prädikat gehört deshalb in die `WHERE`-Klausel **jeder** Abfrage des Endpunkts — auch der Zählabfrage hinter `total` — und darf ausschließlich aus dem Pfadparameter abgeleitet werden, nie aus einem Query-Parameter. `_photos_by_id` filtert nur nach Id und ist keine zweite Verteidigungslinie.

`cluster_key`/`category_key` sind freie Strings aus der Laufhistorie und werden ausschließlich als gebundene Query-Parameter verwendet; eine Allowlist gegen `CATEGORY_REGISTRY` wäre falsch, weil Altläufe Kategorien außerhalb des heutigen Sets führen dürfen (Spec 0289, toleranter Lesepfad). Unbekannte Werte liefern eine leere Liste, keinen Fehler.

### 6. Keine Änderung an Datenmodell, Job, Rangfolge und Antwortschema

Keine neue Tabelle, keine neue Spalte, keine Migration, keine Änderung an `ranking.py`, `criteria.py`, `categories.py` oder `worker.py` — und nach Entscheidung 4 auch kein neues Feld auf `RankingOut`/`PhotoOut`. Diese ADR bewegt sich vollständig auf der Leseseite. Das ist die Einlösung von ADR 0021 Punkt 4: weil der volle Pool persistiert ist, sind "wie viele gibt es" und "zeig mir mehr davon" jeweils Abfragen gegen vorhandene Zeilen.

## Begründung

- Die widerrufene Entscheidung war eine **Anzeige**entscheidung, die als **Speicher**vorteil auftrat: Der Backfill war attraktiv, weil er nichts kostete ("reiner Query-Effekt"), nicht weil er die Kuratierung besser machte. Seine tatsächliche Wirkung — die Restmenge verbergen und die eigene Handlung unsichtbar machen — war zum Zeitpunkt von ADR 0021 nicht absehbar, weil es die Ansicht noch nicht gab.
- Was von ADR 0021 Punkt 4 fällt, ist ein Satz; was trägt, ist der Rest desselben Punktes (voller Pool statt Top-N, N erst beim Lesen). Die Entscheidung ist keine Korrektur am Datenmodell, sondern dessen erste vollständige Nutzung.
- **An drei Stellen entsteht weniger Code:** Outer-Join und Fensterfunktion entfallen in der Abfrage; im Frontend entfallen der Skeleton-Platzhalter des gerade verworfenen Fotos und der Effekt, der auf sein Verschwinden wartet. Ein Zustand, der nur einen Reflow überbrückte, hat ohne Reflow keinen Grund mehr.
- Beide Mengenangaben kommen ohne neuen persistenten oder übertragenen Zustand aus. Es gibt damit keine Zahl, die aus dem Takt geraten kann — die Konsistenzzusage ist strukturell, nicht durch Sorgfalt erkauft. Dass zwei Ebenen dieser Ansicht verschieden zählen, ist der Preis dafür; er wird über die Beschriftung bezahlt und nicht durch eine dritte Zahl verdeckt.

## Konsequenzen

- **ADR [`0021`](./0021-kriterien-datenmodell-kuratierungs-pipeline.md) bekommt eine zweite `**Teilweise abgelöst:**`-Zeile.** Sie muss zusätzlich die bestehende Zeile richtigstellen: die von ADR 0069 dort ausgesprochene Bestätigung "Backfill als reiner Query-Effekt (`row_number()` nach dem `REJECTED`-Filter) gilt unverändert" trifft ab hier nicht mehr zu. Alles Übrige von Punkt 4 — die Persistenz des vollen Pools, auf der beide ablösenden ADRs aufbauen — gilt weiter.
- **ADR [`0069`](./0069-nebenkategorien-mehrfachzugehoerigkeit-und-konfidenzgewichtete-rangfolge.md) bekommt eine `**Teilweise abgelöst:**`-Zeile** für die **Definition** von `curation_position` in Punkt 8 (die Formel "um die eigenen Ablehnungen bereinigt" und die daraus abgeleitete Auflage an einen künftigen Antwort-Zwischenspeicher). Der Grund für das Feld, seine Rolle und alles Übrige der ADR (Datenmodell der Mehrfachzugehörigkeit, konfidenzgewichtete Rangfolge, Migration) bleiben unberührt — das ist deutlich weniger als die Hälfte eines von neun Punkten, also `Accepted` mit Vermerk, nicht `Superseded`.
- **Der Ausschuss-Filter der Phase A bleibt unangetastet.** Aufgehoben wird ausschließlich der Filter über die *persönliche* Bewertung. Fotos ohne `PhotoRanking`-Zeile tauchen unverändert nicht auf.
- **Der Konfidenzfilter aus Spec 0299 bleibt eine reine Sicht.** Er wirkt weiterhin nur auf die geladenen Daten; die drei Mengenangaben beschreiben unverändert den vollen Bestand, auch bei aktivem Filter. Das ist gewollt: die Zahl beantwortet "wie viel liegt hier", nicht "wie viel sehe ich gerade".
- **Das Design-System-Dokument verliert ein Muster.** `specs/architecture/0004-design-system.md` führt "In-place Nachrücken (Backfill) statt Reflow"; es ist zurückgenommen. Nachzuziehen vom `ux-ui-designer` (Owner), nicht hier.
- **`docs/architecture.md`** (Owner: `architect`) beschreibt beim Eintrag `PhotoRanking` den Backfill als `row_number()` nach dem `REJECTED`-Filter und wird im selben PR nachgezogen, zusammen mit dem neuen Endpunkt.
- **Ein Produkttext wird unwahr:** `KuratierungStepPage.tsx` verspricht "sortierst du eines aus, rückt automatisch das nächstbeste derselben Kategorie nach". Er gehört zur Umsetzung dieser Entscheidung, nicht in eine spätere Aufräumrunde.
- **Bestehende Tests kodieren das alte Verhalten** (`backend/tests/test_api_photos.py`, Backfill-Test; die Kuratierungstests im Frontend). Sie werden umgeschrieben, nicht gelöscht: derselbe Aufbau prüft künftig die Gegenaussage.
- **Bewusst offen gelassen:** Ein Verwerfen lässt sich in der Kuratierungsansicht nicht zurücknehmen (weiterhin nur über die Rasteransicht mit Filter "Aussortiert"). Das ist der Umfang der Story; durch Entscheidung 3 ist der Platz dafür jetzt vorhanden, sollte es später gewünscht sein.
