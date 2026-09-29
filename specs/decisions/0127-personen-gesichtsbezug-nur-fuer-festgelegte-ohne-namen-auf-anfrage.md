# 0127 - Personen: Gesichtsbezug nur für die festgelegten Personen, „Ohne Namen" auf Anfrage

**Status:** Accepted
**Datum:** 2026-09-28
**Bezug:** [GitHub-Issue #551](https://github.com/TheRealKoller/photosort/issues/551), Spec 0551.
Löst ADR [`0126`](./0126-personen-lokal-erkennen-global-festlegen-korrektur-getrennt.md) in
Punkt 3 (Zweck des API-Prozesses) und Punkt 6 (Spaltensätze von Erkennung und Korrektur) teilweise
ab.

## Kontext

Die Personenübersicht eines Projekts zeigt jedes unbenannte Gesicht einzeln zum Zuordnen. Sie
blendet erkannte und zugeordnete Gesichter aus und nimmt ein gezeigtes Gesicht wieder zurück. Mit
ADR 0126 kennen Erkennung und Korrektur nur das Paar (Foto, Person), und eine Referenz kennt kein
Foto. Über unbekannte Gesichter wird weiterhin nichts gespeichert. Die Menge „Ohne Namen" muss
deshalb bei jedem Öffnen neu entstehen.

## Entscheidung

### 1. Gesichtsbezug als Box, nur für die festgelegten Personen

- `photo_person_detections` und `photo_person_corrections` bekommen je eine optionale Box
  (`face_box_x`, `face_box_y`, `face_box_width`, `face_box_height`). Sie ist auf die
  Display-Variante normiert (0..1), und es gibt entweder alle vier Werte oder keinen. Die Box
  beschreibt das Gesicht, das auf diesem Foto einer festgelegten Person gehört: bei der Erkennung
  das eine Kandidatengesicht, bei der Korrektur das gewählte.
- Die Korrektur bekommt `reference_id` → `person_references` (optional, `UNIQUE`), also die
  Referenz, die aus diesem Gesicht entstand. Der Fremdschlüssel liegt an der Korrektur, die
  Referenz selbst bekommt keinen Foto- oder Projektbezug. Eine Projektlöschung löscht deshalb die
  Korrektur und lässt die Referenz stehen, danach ohne Foto.
- Wir speichern eine Box statt eines Index, weil der Index von der Datei und von den Konstanten
  der Verwertbarkeit abhängt, und die dürfen nach ADR 0126 Punkt 4 verschärft werden. Ein
  gefundenes Gesicht ist dasselbe wie eine gespeicherte Box, wenn ihre Überdeckung (IoU)
  `SAME_FACE_MIN_OVERLAP = 0.5` erreicht (fest, keine Einstellung). Jede Box gilt für höchstens
  ein Gesicht, nämlich das mit der größten Überdeckung. YuNet unterdrückt Überlappungen ab 0.3,
  deshalb erreichen zwei gefundene Gesichter diese Schwelle nie gemeinsam.
- Prüfeinschränkungen: Die Box ist vollständig oder leer und liegt im Bereich 0..1, Breite und
  Höhe sind größer als 0. An der Korrektur gibt es eine Box nur mit `applies = true` und eine
  `reference_id` nur zusammen mit einer Box.
- **Nie gespeichert werden** Box, Index, Ausschnitt oder Anzahl eines Gesichts, das keiner
  festgelegten Person gehört.

### 2. Zuordnen und Zurücknehmen

- Ein gezeigtes Gesicht, ob in der Detailansicht oder in der Übersicht, schreibt in einer
  Transaktion die Referenz und die Korrektur `applies = true` samt Box und `reference_id`.
- Ist die Obergrenze `MAX_REFERENCES_PER_PERSON` erreicht, entsteht keine Referenz. Die Korrektur
  trägt dann die Box ohne `reference_id`: Das Foto ist benannt und das Gesicht zugeordnet, gelernt
  wird nichts.
- Je Foto und Person trägt höchstens eine Korrektur eine Box. Das Setzen ist bedingt
  (`UPDATE … WHERE face_box_x IS NULL`, beim Anlegen `UNIQUE(photo_id, person_id)`). Ein erkanntes
  Gesicht derselben Person sperrt das nicht: Es ausdrücklich zu zeigen ist Anlernen, und die Box
  der Korrektur geht der erkannten vor. Je Foto gehört ein Gesicht höchstens einer Person. Geprüft
  wird dafür die Überdeckung mit dem zugeordneten Gesicht der anderen Person nach Punkt 3, also
  auch mit einem erkannten. Ein Verstoß ergibt `409`, und es wird nichts geschrieben.
- **Ein Schreiber zur Zeit:** Die Personen-Endpunkte, die schreiben (Festlegen, Zeigen, `PUT` der
  Korrektur, Entfernen der Person), laufen mit Prüfungen, Schreiben und Commit unter einer
  prozessweiten `asyncio.Lock`. Detektion und Merkmal laufen außerhalb davon auf dem Executor.
  Das gilt, weil es genau einen API-Prozess gibt (`uvicorn` ohne `--workers` und ohne
  `WEB_CONCURRENCY`). Die Sperre deckt auch die Obergrenze ab, die über Fotos hinweg gilt; eine
  Sperre der Fotozeile täte das nicht.
  Ohne die Sperre könnten zwei gleichzeitige Zuordnungen dasselbe Gesicht zwei Personen geben
  oder eine 21. Referenz anlegen. Wer einen zweiten API-Prozess einführt, muss die Sperre durch
  eine Sperre in der Datenbank ersetzen.
- **Rücknahme:** Jede Korrektur `applies = false` für ein Paar mit Box ist eine Rücknahme. Box und
  `reference_id` werden geleert, und die verknüpfte Referenz wird in derselben Transaktion
  gelöscht. Den Zustand „gezeigtes Gesicht auf einem Foto ohne diesen Namen" gibt es nicht.
- Fällt eine Referenz durch einen Modellwechsel weg, wird vorher die `reference_id` ihrer Korrektur
  geleert. Das geschieht per Mengenanweisung in Fremdschlüssel-Reihenfolge, wie in `delete_person`.

### 3. Welches Gesicht als zugeordnet gilt

Je Paar (Foto, Person) gilt die erste zutreffende Regel:

1. Korrektur `applies = false`: kein Gesicht.
2. Korrektur mit Box: diese Box.
3. Erkennung mit Box: diese Box.
4. Sonst: kein Gesicht. Das betrifft einen Namen, der nur für das ganze Foto vergeben wurde, und
   eine Erkennung aus einem Lauf vor dieser ADR.

Diese Regel steht nur an einer Stelle, in `persons.py::assigned_face_boxes`.

### 4. „Ohne Namen" entsteht im API-Prozess, seitenweise und ohne Schreiben

- Die Gesichter laufen über denselben Ein-Thread-Executor wie das Festlegen (ADR 0126 Punkt 3).
  Der API-Prozess listet damit jetzt auch die unbenannten Gesichter eines Projekts auf.
- Eine Seite umfasst eine begrenzte Folge von Fotos des Projekts, geordnet nach `Photo.id` ab
  einem Cursor. Jedes Foto ist ein eigener Aufruf im Executor, sodass sich Zuordnungen zwischen den
  Fotos einreihen können. Ein Aufruf lädt die Display-Variante, führt `detect` aus, zieht die
  zugeordneten Boxen ab und schneidet die übrigen Gesichter aus. **`embed` läuft dabei nie.** Es
  entsteht also weder ein Merkmal noch eine Ähnlichkeit, und die Reihenfolge (Foto-Id, dann Index)
  kann keine Ähnlichkeit verraten.
- Die Ausschnitte kommen mit der Seitenantwort (`Cache-Control: no-store`), damit nicht jeder
  Ausschnitt einen eigenen Detektionslauf braucht.
- Fehlt die Display-Variante oder ist das Bild nicht lesbar, führt die Antwort das Foto als
  „nicht bereit". Für dieses Foto wird das Modell nicht gerufen.
- Die Anfrage schreibt nichts. Der Datenbestand ist danach derselbe wie vorher.
- Beim Zuordnen wird ein Gesicht weiter über (Foto, Index) adressiert, und der Server sucht die
  Gesichter neu. Ändert ein Scan die Datei zwischen Auflistung und Zuordnung, kann der Index auf
  ein anderes Gesicht desselben Fotos zeigen. Das nehmen wir in Kauf.

## Konsequenzen

- ADR 0126 Punkt 3 („API-Prozess nur zum Festlegen") und Punkt 6 (Erkennung „keine Box",
  Spaltensatz der Korrektur) sind insoweit abgelöst, die Kopfzeile dort verweist hierher. Der
  Grundsatz „nichts über unbekannte Gesichter" gilt unverändert.
- Erkennungen aus Läufen vor der Migration haben keine Box. Bis zum nächsten Klassifizierungslauf
  steht ihr erkanntes Gesicht deshalb in „Ohne Namen".
- Eine Referenz ohne Korrektur verschwindet nur mit ihrer Person. Das betrifft Referenzen, die vor
  dieser ADR gezeigt wurden, und solche, deren Projekt gelöscht ist.
- `person_matching.decide_assignments` liefert je erkannter Person den Index ihres einen Gesichts.
- Die Zeit, bis „Ohne Namen" vollständig ist, wächst linear mit der Zahl der Fotos, denn je Foto
  laufen Laden und Detektion auf einem Thread.
