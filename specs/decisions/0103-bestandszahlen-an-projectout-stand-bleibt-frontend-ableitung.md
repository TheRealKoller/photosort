# 0103 - Bestandszahlen an `ProjectOut`, Bearbeitungsstand bleibt Frontend-Ableitung

**Status:** Accepted
**Datum:** 2026-09-14
**Bezug:** [GitHub-Issue #375](https://github.com/TheRealKoller/photosort/issues/375), Spec 0375

## Kontext

Die Projektübersicht soll je Projekt drei Angaben zeigen: Fotoanzahl, Aufnahmezeitraum und den
nächsten offenen Schritt. Für jede stellt sich dieselbe Frage — entsteht sie im Backend als Feld
oder im Frontend als Ableitung? Die Antwort fällt für die ersten beiden anders aus als für die
dritte, und beide Antworten setzen einen Präzedenzfall für jede weitere Listenansicht.

Zwei Randbedingungen schneiden die Lösungsmenge:

- `ProjectOut` wird von `useProjectQuery` alle zwei Sekunden abgefragt, solange ein Lauf läuft. Was
  an `ProjectOut` hängt, wird in dieser Taktung mitgerechnet.
- Es gibt bereits eine gegenläufige Entscheidung im Bestand: `GET /projects/{id}/fine-labels` ist
  bewusst ein eigener Endpunkt statt eines Feldes an `ProjectOut`. Ein Feld ohne Regel, wann es
  dort hingehört, machte die eine Entscheidung zum Gegenbeispiel der anderen.

## Entscheidung

### 1. Aufnahmekriterium für `ProjectOut`

Ein Wert darf an `ProjectOut`, wenn er alle drei Bedingungen erfüllt:

- Er ist für die **ganze Liste** in einer von der Projektzahl **unabhängigen** Zahl von Abfragen zu
  haben (eine gruppierte Abfrage über alle Projekte, kein Aggregat je Projekt).
- Seine Antwortgröße ist konstant und wächst nicht mit dem Fotobestand.
- Er darf im Zwei-Sekunden-Takt mitgerechnet werden.

Verfehlt ein Wert eine der drei Bedingungen, bekommt er einen eigenen Endpunkt. `fine-labels`
bleibt genau dafür das Beispiel, `GET /projects/{id}/stats` ebenfalls: dessen Kennzahlen messen
zwei `os.stat` je Foto und die Datenbankgröße — sie sind an `ProjectOut` ausgeschlossen.

### 2. Fotoanzahl und Aufnahmezeitraum werden Felder von `ProjectOut`

`photo_count`, `taken_at_earliest` und `taken_at_latest` treten additiv an `ProjectOut`. Sie
erfüllen alle drei Bedingungen: `COUNT(*)`, `MIN(taken_at)`, `MAX(taken_at)` über `photos` mit
`GROUP BY project_id` liefert sie für beliebig viele Projekte in **einer** Abfrage.

Dieselben drei Werte zeigt die Statistikseite. Sie werden deshalb **einmal** als Spaltenausdrücke
definiert und von beiden Endpunkten benutzt; keiner der beiden schreibt seine eigene Zählung. Zwei
Definitionen liefen spätestens dann auseinander, wenn eine von ihnen auf `taken_at_original`
umgestellt würde, und die Übersicht widerspräche der Statistikseite desselben Projekts, ohne dass
ein Test das bemerkte.

### 3. Der Bearbeitungsstand wird kein Feld

Das Backend liefert **keinen** Schritt- oder Standtext. Der Stand bleibt eine reine Ableitung im
Frontend (`frontend/src/utils/pipelineSteps.ts`) aus Feldern, die `ProjectOut` ohnehin trägt.

Grund ist keine Sparsamkeit, sondern eine Invariante: Dieselbe Ableitung bestimmt, wohin
`/projects/:id` weiterleitet. Ein zweiter Ort für denselben Schluss — hier der Text auf der Karte,
dort das Ziel des Klicks — kann nur gleich bleiben, solange niemand einen der beiden ändert. Läuft
er auseinander, benennt die Karte einen Schritt und führt auf einen anderen; nichts schlägt dabei
fehl, es stimmt nur nicht mehr. Die Ableitung lebt deshalb an genau einer Stelle, und die
Stand-Zeile liest sie, statt sie nachzubauen.

### 4. „Alles erledigt" hängt an erledigten Schritten, nicht an einer leeren Frontier

Der Zustand „nichts mehr offen" gilt genau dann, wenn **jeder** Pipeline-Schritt `isDone` ist.
Ausdrücklich **nicht**, wenn die Frontier-Suche keinen offenen Schritt findet: Bei
ausgeschaltetem `category_selection_enabled` ist die Kette hinter dem Ausschuss-Gate unerreichbar,
die Frontier-Suche läuft leer und fällt auf den letzten erreichbaren Schritt zurück. Ein an diese
Leere gebundener Abschluss behauptete Fertigkeit für ein Projekt, das nur abgeschnitten ist — und
verletzte zugleich Punkt 3, weil der Klick weiterhin auf den Rückfallschritt führte.

Weil `kuratierung.isDone` ohne Abschlusssignal im Datenmodell konstant `false` ist, ist der Zustand
damit heute strukturell unerreichbar. Er wird trotzdem gebaut und wird von selbst erreichbar, sobald
ein Abschlusssignal existiert — ohne dass die Bedingung dann noch einmal angefasst werden muss.

## Konsequenzen

- `GET /projects`, `GET /projects/{id}`, `POST /projects` und `PUT /projects/{id}/selection-target`
  antworten mit drei zusätzlichen Feldern. Der TypeScript-Typ `ProjectOut` bekommt sie als
  Pflichtfelder; die fünfzehn lokalen Testfabriken im Frontend ziehen mit, `tsc` findet jede.
- Die bisherige Einzelabfrage der Fotoanzahl je Projekt (für `effective_selection_target`) entfällt
  zugunsten des gemeinsamen Stapel-Aggregats. `GET /projects` setzt damit eine Abfrage **weniger**
  je Projekt ab als zuvor, nicht mehr.
- Ein Projekt ohne Fotos fehlt im Ergebnis der gruppierten Abfrage. Es bekommt `0` und zweimal
  `null` — nie eine fehlende oder geratene Zahl.
- Die Übersicht bleibt von der Statistikseite unabhängig: Sie fordert für keine der drei Angaben
  einen zweiten Endpunkt an, weder je Projekt noch insgesamt.
- Wer künftig ein Feld an `ProjectOut` hängen will, prüft es gegen Punkt 1 und begründet eine
  Abweichung, statt sie beiläufig zu vollziehen.
