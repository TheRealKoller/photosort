# 0068 - Der Klassifizierungslauf als vier benannte Teilschritte mit laufeigener Cloud-Bilanz

**Status:** Accepted
**Datum:** 2026-09-09
**Bezug:** [GitHub-Issue #348](https://github.com/TheRealKoller/photosort/issues/348), [`features/0348-klassifizierungs-transparenz.md`](../features/0348-klassifizierungs-transparenz.md), `architect`-Konsultation für Story #348 am 2026-09-09.

**Löst teilweise ab:** [`decisions/0050-verketteter-klassifizierungslauf-mit-laufbezogener-cloud-freigabe.md`](./0050-verketteter-klassifizierungslauf-mit-laufbezogener-cloud-freigabe.md) — dort **Punkt 3, Absatz „Kein FK zwischen den beiden Run-Tabellen"**. Alles Übrige von ADR 0050 bleibt unverändert in Kraft: die Verkettung selbst (Punkt 1), das Konjunktions-Gate `use_cloud AND cloud_vision_detection_enabled` (Punkt 2), `criterion_scoring_runs` als **der** Lauf-Datensatz des Gesamtlaufs samt `phase`-Spalte und der Verzicht auf eine vierte Run-Tabelle (Punkt 3 im Übrigen), die laufweite `cloud_error_message` (Punkt 4) und die Vorab-Schätzung am Auslöser (Punkt 5). ADR 0050 trägt deshalb den Vermerk **Teilweise abgelöst** und bleibt `Accepted`; die Abstufung ist in [`../README.md`](../README.md) beschrieben.

**Berührt außerdem (keine Ablösung):**
- [`decisions/0051-ist-kostenerfassung-remote-laeufe.md`](./0051-ist-kostenerfassung-remote-laeufe.md) Punkt 3 („Tokens und Aufrufzahl sind persistierte Daten ohne Anzeigepfad", dort als eng begrenzte Ausnahme von der Regel „keine persistierte Zahl ohne Lesepfad" geführt) und Punkt 5 (Befund (b): `api_calls > 0` bei Betrag `0`/`NULL` = Erfassungslücke). Die Entscheidungen selbst — den Verbrauch zu persistieren, den Betrag am Phasenende einzufrieren, die Lücke strukturell zu erkennen — bleiben unverändert. Was endet, ist die *Eigenschaft* „ohne Anzeigepfad": Aufrufzahl, Tokens und Betrag werden mit dieser ADR in der Lauf-Bilanz gelesen. Punkt 4 dieser ADR sichert Befund (b) ausdrücklich gegen die neuen Live-Zähler ab.
- [`decisions/0059-modellwahl-je-anbieter-und-modellgebundene-kostenschaetzung.md`](./0059-modellwahl-je-anbieter-und-modellgebundene-kostenschaetzung.md) Punkt 6 (Modellspalte je Lauf, dort „bewusst ohne Lesepfad in der Oberfläche: Adressat ist der Betreiber, nicht der Anwender"). PhotoSort hat genau zwei Nutzer, und einer davon ist der Betreiber; die Story verlangt das verwendete Modell ausdrücklich vor und nach dem Lauf. Die Spalte bekommt damit ihren Lesepfad. Punkt 7 (eine Modellauflösung je Cloud-Phase, derselbe lokale Wert für Client, Kosten und Spalte) bleibt in Kraft und wird durch Punkt 6 dieser ADR nur zeitlich vorgezogen.
- [`decisions/0019-job-lauf-heartbeat-watchdog.md`](./0019-job-lauf-heartbeat-watchdog.md): die neuen Live-Zähler werden an denselben Punkten committet wie `last_progress_at` und schließen dabei eine bestehende Lücke (Punkt 2 unten).

## Kontext

Seit ADR 0050 ist die Klassifizierung **ein** Lauf mit einer laufbezogenen Cloud-Freigabe, und seit ADR 0051/0059 führt jeder Lauf Buch darüber, was seine Cloud-Anteile tatsächlich verbraucht und gekostet haben. Beides ist im Datenmodell vorhanden — und an der Stelle, an der der Lauf ausgelöst wird, unsichtbar:

- **Vor dem Start** zeigt die Schätzung eine Gesamtsumme. Die beiden Anteile, die sie addiert (`remote_category_candidate_count`, `landmark_candidate_count`), liegen bereits in der Antwort und werden nicht angezeigt; `provider`/`model` ebenso. Der Landmark-Anteil ist vor dem ersten Durchlauf eines Projekts strukturell `0` (ADR 0050 Punkt 5: er wird aus den Kriterienwerten geschätzt, die genau dieser Lauf erst berechnet) — angezeigt wird diese `0` heute als Tatsache statt als Wissenslücke.
- **Während des Laufs** kennt `ClassificationPhase` zwei Werte. Die Sehenswürdigkeits-Erkennung ist keiner davon: sie läuft innerhalb der Kriterien-Phase, nach deren Foto-Schleife — `photos_processed` steht dann bereits auf `photos_total` und bewegt sich nicht mehr. Ein Lauf mit 400 Landmark-Kandidaten steht dort minutenlang unbewegt. Dieselbe Lücke trifft den Fortschritts-Watchdog: `last_progress_at` wird während der gesamten Landmark-Phase nicht angefasst, ein Lauf, der dort länger als `STALL_THRESHOLD` (15 Minuten) verbringt, wird von `reap_stalled_runs` als hängend abgeräumt, obwohl er arbeitet.
- **Nach dem Lauf** existieren Aufrufzahl, Tokens, Betrag und Modell je Cloud-Phase — nur ohne Leser. Die Statistikseite summiert bewusst projektweit über alle Läufe; die Frage „was hat *dieser* Durchlauf gekostet" beantwortet sie nicht und soll sie nicht beantworten.

Der gemeinsame Nenner: es fehlt keine Information, es fehlt ihre **Zuordnung zu einem Durchlauf** und ihr Weg an die Oberfläche.

## Entscheidung

### 1. Vier benannte Teilschritte statt zweier

`ClassificationPhase` bekommt zwei weitere Werte, in Ausführungsreihenfolge:

```
remote_categories  ->  criteria  ->  landmark  ->  ranking
```

`landmark` ist der Schritt, den die Story sichtbar machen will. `ranking` (Kategorieableitung, `rank_photos` je Partition, Schreiben der `PhotoRanking`-Zeilen) kommt hinzu, weil die Reihenfolge sonst **rückwärts laufen müsste**: der Ranking-Teil gehört fachlich zur Kriterien-Phase, läuft aber *nach* der Landmark-Phase. Ohne eigenen Namen bliebe `phase` dort entweder auf `landmark` stehen (die Anzeige behauptete dann Cloud-Aufrufe, die nicht mehr stattfinden, mit einem Fortschritt, der auf 100 % steht — exakt das gemeldete „hängt oder läuft?"-Symptom, nur eine Phase später) oder müsste auf `criteria` zurückspringen. Ein vierter Wert kostet eine Zeile und macht die Abfolge monoton.

Der Wertebereich bleibt eine Zeichenkette in einer `VARCHAR(20)`-Spalte ohne DB-seitige Prüfeinschränkung (`SQLEnum(..., native_enum=False)`, `create_constraint` aus) — **keine Migration** für die zwei neuen Werte. `NULL` behält seine Bedeutung aus ADR 0050 Punkt 3 unverändert: „läuft nicht mehr".

### 2. Live-Zähler sind eigene Spalten und nie die Kosten-Buchführung

Die Story verlangt während eines Cloud-Teilschritts drei Zahlen: Fortschritt, Zahl der bereits abgesetzten Aufrufe und Zahl der Fehlschläge. Nahe läge, dafür die vorhandenen `api_calls`/`landmark_api_calls` laufend fortzuschreiben. **Das ist ausgeschlossen.** Diese Spalten sind die Kosten-Buchführung, sie werden nach ADR 0051 Punkt 4 **einmal am Phasenende** zusammen mit dem eingefrorenen Betrag geschrieben, und ADR 0051 Punkt 5 Befund (b) liest sie: `api_calls > 0` bei `cost_usd` `0`/`NULL` ist der Indikator für eine Erfassungslücke. Ein laufend hochgezählter `api_calls` erfüllte diese Bedingung bei **jedem** laufenden Cloud-Lauf und färbte die Statistikseite mitten im Betrieb mit einem falschen Unvollständigkeits-Vorbehalt ein — auf einer Seite, deren einziger Zweck Kostenkontrolle ist, ist ein Fehlalarm so schädlich wie eine Fehlzahl.

Getrennte Zähler, laufend committet, mit klar anderer Bedeutung:

| Tabelle | Spalte | Bedeutung |
|---|---|---|
| `criterion_scoring_runs` | `landmark_photos_total` | Kandidatenzahl der Landmark-Phase. `NULL` = Phase fand nicht statt (oder Altzeile) — zugleich der **Marker**, ob es diesen Teilschritt in diesem Lauf überhaupt gab. |
| `criterion_scoring_runs` | `landmark_photos_processed` | **Abgesetzte** Aufrufe (Erfolge *und* Fehlschläge), je Block fortgeschrieben. |
| `criterion_scoring_runs` | `landmark_failed_calls` | Fehlgeschlagene Einzelaufrufe, je Block fortgeschrieben. |
| `remote_category_classification_runs` | `failed_calls` | dasselbe für die Remote-Kategorie-Phase; deren `photos_total`/`photos_processed` existieren bereits und werden bereits je Block committet. |

Alle vier sind nullable mit Python-Default `None` — dasselbe `ScanRun.total_files`-Idiom wie bei den Kostenspalten: `NULL` = „nicht erfasst" (Altzeile oder Phase nicht betreten), `0` = „erfasst, nichts passiert". Gesetzt werden sie auf `0` beim **Betreten** der jeweiligen Phase, nicht bei der Zeilenanlage.

Die Fehlerzahl ist damit doppelt vorhanden (`photos_processed - api_calls` liefert sie nach dem Lauf ebenfalls) — bewusst: die abgeleitete Form ist erst nach dem Phasenende verfügbar, die Story verlangt die Zahl **währenddessen**. Für Läufe ab dieser Migration gilt die Invariante `photos_processed == api_calls + failed_calls`; sie wird per Test festgeschrieben, damit die beiden Wege nicht auseinanderlaufen.

Die Commit-Punkte der Landmark-Phase (bisher: keine, erst der `finally`-Block) setzen dabei **auch `last_progress_at`** — die im Kontext beschriebene Watchdog-Lücke schließt sich dadurch als Nebenwirkung, nicht als Zufall: sie ist derselbe Defekt in anderer Kleidung („ein arbeitender Lauf sieht aus wie ein stehender").

### 3. Ein Fremdschlüssel vom Klassifizierungslauf auf seinen Remote-Lauf

`criterion_scoring_runs.remote_category_classification_run_id` (nullable, FK auf `remote_category_classification_runs.id`), gesetzt von `run_classification`, **bevor** Phase 1 startet.

Das kehrt ADR 0050 Punkt 3 um, und zwar mit dem Argument, das dort schon die Grenze markierte: *„ein FK formalisierte eine Zuordnung, die nur für Altdaten uneindeutig war"*. Solange die Zuordnung nur die Fortschrittsanzeige speiste, war „die jüngste Remote-Zeile des Projekts" (`ProjectOut.last_remote_category_classification_run`) genau genug. Die Bilanz eines bestimmten Durchlaufs ist etwas anderes: sie nennt einen **Geldbetrag** und ordnet ihn einem Lauf zu. Die Heuristik ist dafür nachweislich falsch, sobald zwei Läufe hintereinander unterschiedlich viel Cloud nutzen — ein Lauf ohne Cloud-Phase (abgewählte Checkbox, oder zwischen Auslösen und Start entzogene Einwilligung) erbte die Zahlen des Laufs davor und zeigte fremde Kosten als seine eigenen. Eine Zuordnungsfrage, die einen Betrag trägt, gehört in den Schlüssel, nicht in eine Sortierung.

Der FK ist additiv und nullable (`NULL` = dieser Lauf hatte keine Remote-Phase, oder Altzeile). Die Löschreihenfolge in `project_deletion.py` passt bereits: `criterion_scoring_runs` wird vor `remote_category_classification_runs` gelöscht. Ein Test hält das fest, damit die Reihenfolge nicht unbemerkt umsortiert wird.

Damit die Zeile schon **während** Phase 1 verknüpft ist, legt `run_classification` den `RemoteCategoryClassificationRun` an und reicht ihn hinein — genau das Muster, das ADR 0050 Punkt 3 bereits für `CriterionScoringRun` eingeführt hat („sonst zeigte `last_criterion_scoring_run` während der Remote-Phase noch auf den Lauf davor"), jetzt eine Ebene tiefer und aus demselben Grund. `run_remote_category_classification` behält den Parameter `run: … | None = None` und legt die Zeile beim Direktaufruf weiterhin selbst an.

### 4. Eine Struktur für Live-Fortschritt und Bilanz, keine zweite

Je Cloud-Teilschritt liefert die API **einen** Eintrag, der ab dem Betreten der Phase existiert und sich füllt:

```
CloudPhaseSummaryOut:
    purpose            'remote_category' | 'landmark'   (CloudVisionPhase, wie in der Statistik)
    photos_total       Kandidaten
    photos_processed   abgesetzte Aufrufe          <- bewegt sich live
    failed_calls       Fehlschläge                 <- bewegt sich live
    responses_used     api_calls, verwertete Antworten   (erst am Phasenende)
    input_tokens / output_tokens                       (erst am Phasenende)
    cost_usd           eingefrorener Betrag, null = kein Preis/nicht erfasst
    model / provider   Preis- und Aufrufgrundlage
```

Während des Laufs ist das die Fortschrittsanzeige, danach die Bilanz — es ist derselbe Datensatz, gelesen zu zwei Zeitpunkten. Eine getrennte „Bilanz"-Struktur wäre eine zweite Definition derselben Zahlen und driftete.

Die Liste hängt an `CriterionScoringRunSummary` (`cloud_phases`), also an dem Objekt, das die Oberfläche für den Lauf ohnehin schon pollt. **Kein neuer Endpunkt** und keine zweite Poll-Schleife: die Bilanz ist eine Eigenschaft des Laufs, kein eigener Bericht. Eine leere Liste heißt „dieser Durchlauf hatte keinen Cloud-Teilschritt" und ist der Anker für die Aussage, die die Story dafür verlangt.

`ProjectOut.last_remote_category_classification_run` entfällt ersatzlos — sein einziger Leser war die Fortschrittsanzeige, die jetzt über `cloud_phases` geht. Zwei Wege zu derselben Zeile, von denen einer die falsche treffen kann, sind genau der Zustand, den Punkt 3 beseitigt.

### 5. Die Schätzung, mit der ein Lauf gestartet wurde, wird am Lauf eingefroren

Neue Spalte `criterion_scoring_runs.estimated_cost_usd` (nullable). Ohne sie ist das Akzeptanzkriterium „die tatsächlich angefallenen Kosten sind gegen die Schätzung vor dem Start einordenbar" nach dem Lauf unerfüllbar: die Schätzung wird aus dem **noch offenen** Kandidatenbestand berechnet, und den hat genau dieser Lauf gerade abgearbeitet — unmittelbar nach dem Lauf schätzt derselbe Endpunkt nahe null. Die Zahl, gegen die verglichen werden soll, existiert nach dem Lauf nirgends mehr.

Berechnet wird sie **serverseitig im Auslöse-Endpunkt** (`POST /classify`) mit denselben Hilfsfunktionen, die die angezeigte Schätzung erzeugen, und als Job-Argument an `classify`/`run_classification` durchgereicht, das sie beim Anlegen der Lauf-Zeile schreibt. Zwei Alternativen wurden verworfen: der Client könnte den angezeigten Betrag mitschicken — ein vom Client gelieferter Geldwert, der ungeprüft in die Buchführung wanderte; oder der Worker könnte selbst neu schätzen — dann bräuchte die Worker-Schicht eine dritte Kopie der Kandidaten-Zählung (die Trennung „API zählt für die Schätzung, Worker selektiert für den Lauf" ist eine bewusste, im Code dokumentierte Modulgrenze). Der Endpunkt kennt die Zahl bereits; sie von dort weiterzureichen fügt keine neue Rechenstelle hinzu. Bei `use_cloud=false` wird `NULL` geschrieben: ein Lauf ohne Cloud hat keine Kostenschätzung, und `0.0` wäre eine Aussage, die niemand getroffen hat.

Der Job bekommt das Argument mit Default `None`, damit ein zum Zeitpunkt eines Deployments bereits eingereihter Job nicht an einer Signaturänderung scheitert.

### 6. Der Anbieter wird aus dem gespeicherten Modell abgeleitet, nicht zusätzlich gespeichert

Die Lauf-Zeilen speichern das Modell (ADR 0059 Punkt 6), nicht den Anbieter. Die Bilanz nennt beides. Die fehlende Hälfte kommt aus einer reinen Rückwärtssuche über `cloud_vision.py::VISION_MODELS_BY_PROVIDER` (`provider_for_vision_model(model) -> str | None`), nicht aus einer weiteren Spalte und **nie** aus `settings.landmark_provider`: die aktuelle Betriebseinstellung sagt nichts darüber, womit ein vergangener Lauf gerechnet hat — genau die Verwechslung, die ADR 0059 behoben hat. Ein Modell, das nicht mehr in der Registry steht (Altlauf, entferntes Modell), liefert `None`; die Oberfläche zeigt dann die Modell-ID allein, statt einen Anbieter zu raten.

Damit Modell und Anbieter **während** eines laufenden Cloud-Teilschritts schon dastehen, wandert das Schreiben der Modellspalte vom `finally`-Block an den **Phasenanfang**, unmittelbar nach der einmaligen Auflösung. Es bleibt derselbe lokale Wert, der den Client baut und die Kosten rechnet (ADR 0059 Punkt 7 unverändert) — nur früher sichtbar. Der Betrag bleibt dagegen im `finally` und am Phasenende eingefroren (ADR 0051 Punkt 4).

### 7. „Nicht schätzbar" ist ein eigener Wert, keine Null

`ClassificationEstimateOut` weist die beiden Anteile getrennt aus, jeweils Kandidatenzahl und Betrag, dazu die unveränderte Gesamtsumme. Der Landmark-Anteil ist dabei `null`, solange für das Projekt kein abgeschlossener Klassifizierungslauf existiert — dieselbe Semantik, die `price_per_image_usd` seit ADR 0059 Punkt 4 hat: `null` heißt „unbekannt", nie „kostenlos". Vor dem ersten Lauf gibt es keine gespeicherten Kriterienwerte, aus denen sich Landmark-Kandidaten ableiten ließen; die heutige `0` behauptet an dieser Stelle Kostenfreiheit für einen Anteil, der gleich Geld kostet. Die Gesamtsumme bleibt die Summe der **bekannten** Anteile und ist in diesem Fall ausdrücklich eine untere Schranke.

Als Merkmal für „es gab schon einen Durchlauf" dient die Existenz eines `CriterionScoringRun` mit `status = success` im Projekt — eine Zeile, kein neuer Zustand. Der feinere Fall (nach einem Re-Scan haben *einige* Fotos noch keine Kriterienwerte) bleibt bewusst ungedeckt: die Schätzung ist als Schätzung ausgewiesen, und die Story verlangt die Aussage für den Erstlauf.

### 8. Die Statistikseite bleibt unangetastet

Kein Feld, keine Query und keine Aussage von `GET /projects/{id}/stats` ändert sich. Sie bleibt die projektweite Auswertung über alle Läufe, die Bilanz ist die laufbezogene Sicht — zwei Fragen, zwei Orte. Die einzige Berührung ist die in Punkt 2 beschriebene Nicht-Änderung: die Live-Zähler bleiben von den Spalten fern, die Befund (b) auswertet.

## Begründung

Alle drei Lücken der Story haben dieselbe Ursache und deshalb dieselbe Behandlung: **der Lauf führt bereits Buch, aber niemand kann diese Buchführung dem Durchlauf zuordnen, den er gerade angestoßen hat.** Der Eingriff liegt folglich nicht in neuen Berechnungen, sondern an drei Stellen: der Lauf benennt seine Teilschritte vollständig (Punkt 1), er hält seine Zwischenstände fest, während sie entstehen (Punkt 2), und er weiß, welche Remote-Zeile ihm gehört (Punkt 3). Alles Weitere — Aufschlüsselung vor dem Start, Fortschritt je Teilschritt, Bilanz danach — ist eine reine Lesesicht auf Spalten, die es bereits gibt oder die diese ADR additiv daneben stellt.

Zwei Regeln des Projekts bleiben dabei tragend und wurden nicht aufgeweicht: ein Geldbetrag wird nie geschätzt, wo er gemessen werden kann, und eine unbekannte Zahl wird nie als `0` ausgegeben.

## Konsequenzen

- **Positiv:** Ein Durchlauf ist erstmals von der Freigabeentscheidung bis zur Abrechnung an einer Stelle nachvollziehbar. Der Landmark-Teilschritt hat einen Namen, einen Fortschritt und eine Bilanz; die Watchdog-Lücke, die einen langen Landmark-Lauf nach 15 Minuten abräumen konnte, schließt sich mit denselben Commit-Punkten. Die Zuordnung „welcher Remote-Lauf gehört zu welchem Klassifizierungslauf" ist nicht mehr geraten. Aufrufzahl, Tokens, Betrag und Modell verlieren ihren Status als persistierte Daten ohne Leser.
- **Negativ / bewusst getragen:** Sechs weitere Spalten an den beiden Run-Tabellen und ein FK zwischen ihnen — die Tabellen tragen damit endgültig zwei Rollen (Ablaufzustand und Abrechnung). Die Fehlerzahl ist redundant zu `photos_processed - api_calls` und wird per Invariantentest zusammengehalten. Läufe von vor dieser Migration zeigen keine Bilanz (`cloud_phases` bleibt leer, obwohl `cloud_requested` wahr sein kann); die Oberfläche sagt das ausdrücklich, statt Nullwerte zu zeigen — es ist nicht nachholbar und heilt mit dem nächsten Lauf. Der Auslöse-Endpunkt führt jetzt zwei Zählabfragen mehr aus (dieselben, die die Seite ohnehin beim Laden ausführt).
- **Folgearbeit:** Eine Historie mehrerer Läufe (in der Story ausdrücklich out of scope) ist über dieselben Spalten ohne Datenmodell-Änderung erreichbar — die Bilanz hängt am Lauf, nicht am Projekt, und die Läufe sind vollständig gespeichert.
