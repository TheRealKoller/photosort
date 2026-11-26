# 0153 - Die Typen der Oberfläche entstehen aus der Schnittstellenbeschreibung des Servers

**Status:** Accepted
**Datum:** 2026-11-26
**Bezug:** Issue [#654](https://github.com/TheRealKoller/photosort/issues/654), Story „Typen aus
der Schnittstellenbeschreibung, sechs Seiten geteilt"
**Umfang:** rund 120 statt 100 Zeilen. Abschnitt 3 trägt die drei Prüfungen samt Meldungspflicht;
sie gehen in keiner Zusammenfassung auf.

## Kontext

`frontend/src/api/types.ts` führt die Antwortstrukturen des Servers als handgeschriebene
Schnittstellen. An nichts gebunden, bleibt eine Umbenennung oder Feldergänzung im Backend für
Typprüfung, Lint und Tests unsichtbar. `create_app().openapi()` ist die vollständige, maschinenlesbare
Beschreibung derselben Strukturen und wird bereits gepflegt.

## Entscheidung

### 1. Eine Beschreibung, ein eingechecktes Artefakt

`backend/scripts/export_openapi.py` schreibt `create_app().openapi()` als `backend/openapi.json`
(sortierte Schlüssel, zwei Leerzeichen Einrückung, UTF-8). Die Datei ist eingecheckt: Sie macht
jede Vertragsänderung im Diff sichtbar und erlaubt die Typ-Erzeugung ohne laufenden Server. Sie
entsteht ausschließlich aus dem Code; von Hand wird sie nie bearbeitet.

### 2. Erzeugte Typen, gekennzeichnete eigene Ableitungen

`frontend/src/api/generated/schema.d.ts` entsteht aus `backend/openapi.json` mit
`openapi-typescript` (Dev-Abhängigkeit, exakt gepinnt). Die Datei trägt den Erzeuger-Kopf, ist von
Prettier und Lint ausgenommen und wird nie von Hand geändert.

`frontend/src/api/types.ts` bleibt die eine Importquelle der Oberfläche und enthält danach genau
zwei gekennzeichnete Abschnitte:

- **Erzeugt** — je Serverstruktur ein Alias auf `components["schemas"][...]`; der Alias darf einen
  Oberflächennamen tragen, die Struktur kommt unverändert aus der Beschreibung.
- **Oberflächen-eigen** — Typen ohne Servergegenstück (Anzeige-Ableitungen, camelCase-Parameterobjekte
  der API-Module). Sie werden aus erzeugten Typen abgeleitet, wo ein Serverfeld die Aussage trägt.

Eine zweite handgepflegte Fassung einer Serverstruktur ist ausgeschlossen: `types.ts` enthält
keine `interface`-Deklaration mehr, und `scripts/tests/test_frontend_typen.py` meldet jede
Typdeklaration, deren Name ein Schemaname aus `backend/openapi.json` ist. Derselbe Wächter prüft,
dass jeder `components["schemas"]["X"]`-Bezug einen vorhandenen Schemanamen nennt.

### 3. Nachführung ist eine Kette aus drei Prüfungen

1. `backend/tests/test_openapi_vertrag.py` vergleicht `backend/openapi.json` mit
   `create_app().openapi()`. Bei Abweichung nennt die Meldung den betroffenen Pfad bzw. Schema samt
   Feld und den Nachführschritt (`backend/scripts/export_openapi.py`, dann
   `npm --prefix frontend run api:generate`).
2. `npm run api:check` erzeugt die Typen erneut in eine temporäre Datei und vergleicht sie mit dem
   eingecheckten Stand; bei Abweichung nennt die Meldung die Datei und `npm run api:generate`.
   Der Schritt läuft als Teil von `npm run typecheck` in CI und in `scripts/check.sh`.
3. `tsc` prüft anschließend jede Aufrufstelle gegen den nachgeführten Typ.

Eine Antwortstruktur, die sich ändert, ohne dass beide Dateien nachgeführt werden, wird damit rot;
ohne eine solche Änderung bleiben alle drei Schritte grün. Der Rot-Grün-Nachweis steht im Pull
Request als Abfolge der drei Läufe.

### 4. Der Aufruf trägt seinen Endpunkt

`apiFetch` nimmt den **Endpunkt als Vorlage** (`"/projects/{project_id}/scan"`) und die
Pfadparameter getrennt entgegen; Antwort- und Anfragekörper leitet es aus
`paths[Endpunkt][Methode]` ab. Ein Aufruf mit einem konkreten Pfad ist kein gültiger Aufruf, und
der Antworttyp ist nicht mehr vom Aufrufer wählbar — eine Verwechslung zweier Endpunkte meldet
`tsc`.

Die eine Typaussage an der HTTP-Grenze leitet sich aus dem Endpunkt ab; sie ist nicht mehr
`apiFetch<T>` mit freiem `T`. Für die gemockte Grenze in den API-Modultests trägt `apiFetch` eine
zweite Signatur, die `Promise<unknown>` liefert: Sie kann keine Typaussage behaupten, und eine
Zuweisung an einen erwarteten Antworttyp scheitert an `unknown`.

`apiFetchBlob` bleibt für Bild- und Exportdateien; auch sein Pfad ist eine Endpunktvorlage.
Endpunkte mit binärem Körper werden mit `response_class` deklariert, damit die Beschreibung dort
keinen JSON-Körper behauptet.

### 5. Statusvokabulare bleiben getrennt

`ScanStatus` und `ExportRunStatus` bleiben zwei benannte Schemata. Die Oberfläche verwendet je
Stelle das Vokabular ihres Laufs; `ScanStatusLabel` ist `ScanStatus | "never"`, nicht eine zweite
Literalliste. Wo eine Stelle alle Werte eines Vokabulars behandelt, steht ein `never`-Wächter
(`utils/scanStatus.ts::ScanStatusLabel`-Abbildung, `hooks/useProjects.ts::isActive`). Ein
zusätzlicher Wert im einen Vokabular erscheint damit nicht im anderen und wird an der
behandelnden Stelle zum Typfehler.

### 6. Verhaltensregeln stehen an der Struktur oder am Feld

Regeln über das Serververhalten stehen in der Schnittstellenbeschreibung: als Docstring der
Antwortstruktur bzw. des Enums oder als `Field(description=...)` am betroffenen Feld, damit sie
über den erzeugten Typ an jeder Lesestelle sichtbar sind. Dazu gehören insbesondere „nicht erfasst
ist `null` und nie `0`", „`queued` heißt angenommen, aber noch nicht begonnen" und die
Feld-Wirkung eines Schreibendpunkts (Route-Docstring). Oberflächenkommentare, die nur diese Regeln
wiederholten, entfallen; Anzeige- und Bedienregeln der Oberfläche bleiben.

### 7. Unbenannte Antworten werden benannt

Die vier Auslöser (`scan`, `score`, `classify`, `export`) antworten mit `TriggerQueuedOut`
(`status: Literal["queued"]`), der Ausschuss-Abschluss mit `AusschussGateConfirmedOut`
(`status: Literal["confirmed"]`), `/health` mit `HealthOut`. Kein 2xx-JSON-Körper der Anwendung
bleibt ein anonymes Objekt; `test_openapi_vertrag.py` hält das fest und kennt keine Ausnahmeliste.
Ein Feld, das die Oberfläche als geschlossene Menge führt, ist auch im Server geschlossen
(`CancelOutcome` statt `str`; die beiden Zählkarten der Prüfung als feste Modelle statt `dict`).

## Begründung

- **Warum das Artefakt eingecheckt ist:** Der Diff zeigt den Vertragswechsel an der Stelle, an der
  er entsteht, und die Typprüfung der Oberfläche braucht weder Datenbank noch laufenden Server.
- **Warum der Endpunkt die Typquelle ist:** Nur so ist eine Verwechslung zweier Endpunkte ein
  Typfehler statt einer Annahme, die erst an einer Lesestelle auffällt.
- **Warum `openapi-typescript`:** Es liest genau die Beschreibung, die FastAPI erzeugt, ohne
  zusätzliche Schemadefinitionen; die Ausgabe ist Text und damit im Diff prüfbar. Es kommt keine
  Laufzeitabhängigkeit hinzu.
- **Warum die Trennung erzeugt/eigen mechanisch geprüft wird:** Ein Kommentarabschnitt allein
  hindert die nächste handgeschriebene Kopie nicht.

## Konsequenzen

- Eine Änderung an einer Antwortstruktur zieht `backend/openapi.json` und
  `frontend/src/api/generated/schema.d.ts` in denselben Pull Request; beide Dateien sind erzeugt.
- Die API-Module rufen `apiFetch` mit Endpunktvorlage, Pfadparametern und typisiertem Query-Objekt
  auf. Die Erwartungen ihrer Unit-Tests an den weitergereichten Aufruf folgen dieser Form; die
  Seitentests bleiben unverändert.
- Die Struktur-Verträge, die Quelldateien namentlich prüfen, führen die beim Teilen entstehenden
  Bausteine in ihren Dateilisten — die Zusicherung bleibt dieselbe.
