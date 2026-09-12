# 0088 - Die korrigierte Zeit **ist** die Aufnahmezeit der Anwendung, die Kamera ist eine projekteigene Entität

**Status:** Accepted
**Datum:** 2026-09-12
**Bezug:** Spec `specs/features/0426-*.md`, ADR
[`0087`](./0087-event-als-persistierte-einheit-und-trennsignale-als-liste.md) (Event als
Lauf-Artefakt, projektweite Ortsherleitung), ADR
[`0029`](./0029-gps-landmark-cluster-bildung.md) (Schwellen als Modulkonstanten), ADR
[`0062`](./0062-projektloeschung-als-metadatengeordnete-mengenloeschung.md) (Erreichbarkeit entlang
der Fremdschlüsselkanten)

**Umfang:** über dem Richtwert von rund 100 Zeilen, weil die Entscheidung sechs Punkte trägt und
einer davon (Punkt 1) die Umkehrung der Bedeutung einer bestehenden Spalte ist.

## Kontext

Eine Kamera ohne Ortsbestimmung, deren Uhr von Hand gestellt wird, liefert Aufnahmezeiten, die um
Stunden neben denen des Handys liegen. Zwei Folgen, beide ohne Fehlermeldung: die Gliederung trennt
Zusammengehöriges, und ein Kamerafoto ohne eigene Koordinate erbt (ADR 0087, Punkt 4) den Ort des
zeitlich nächsten Fotos — bei falscher Uhr den eines ganz anderen Moments.

Die Aufnahmezeit wird heute an fünf Stellen gelesen: der Gliederung vor dem Ausschuss-Gate
(`assign_clusters`), der Event-Bildung, der Ortsherleitung (`infer_locations`, in Worker **und**
Lesepfad), der Sortierung der Fotoliste (in SQL, mit Paginierung) und dem Aufnahmezeitraum der
Statistik (`min`/`max`, in SQL). Jede dieser Stellen einzeln korrigieren zu lassen hieße, dieselbe
Rechnung fünfmal zu führen — und die sechste, künftige Lesestelle vergisst sie.

## Entscheidung

### 1. `Photo.taken_at` **ist** die korrigierte Zeit, `taken_at_original` tritt daneben

Die bestehende Spalte behält ihren Namen und ihre Rolle als „die Zeit, mit der die Anwendung
arbeitet", trägt aber ab jetzt den korrigierten Wert. Neu daneben: `taken_at_original` (NOT NULL),
der beim Scan ermittelte Wert — EXIF `DateTimeOriginal`, sonst der Fallback auf `last_modified`.

**Warum diese Richtung.** Die Alternative (`taken_at` bleibt roh, eine neue Spalte trägt die
korrigierte Zeit) verlangt, dass jede der fünf Lesestellen und jede künftige umgestellt wird. Ihre
Ausfallrichtung ist eine übersehene Stelle, die still mit der falschen Uhr weiterrechnet — genau der
Defekt, den diese Story behebt. In der gewählten Richtung ändert sich keine Lesestelle, und eine
übersehene Stelle zeigt die korrigierte Zeit, wo die aufgezeichnete gemeint war: sichtbar und
folgenlos für Gruppierung, Reihenfolge und Ortsübernahme.

Kriterium „Originaldateien bleiben unverändert" bezieht sich auf die **Datei**: PhotoSort schreibt
nie in eine Quelldatei, und `taken_at_original` hält den aufgezeichneten Wert unverändert fest.

**Invariante, im Schreibpfad gehalten:** `taken_at == taken_at_original + offset_minutes` der
Kamera, die dieses Foto aufgenommen hat, in genau diesem Projekt — bei fehlender Kamera oder
`offset_minutes = 0` sind beide Werte gleich. Es gibt **zwei** Schreibstellen (Scan und
Versatz-Änderung), beide über **eine** reine Funktion. Eine dritte Schreibstelle auf `taken_at` gibt
es nicht.

**Kein SQL-Ausdruck statt der Spalte.** Die Korrektur als Ausdruck über einer Versatz-Tabelle würde
Datumsarithmetik in SQL verlangen; SQLite und PostgreSQL schreiben sie unterschiedlich, und die
Testsuite läuft auf SQLite. Sortierung mit Paginierung und `min`/`max` müssen aber in SQL bleiben.

### 2. Die Kamera ist eine projekteigene Zeile, der Versatz eine Spalte darauf

Neue Tabelle `project_cameras`: `project_id` (echter Fremdschlüssel), `make`, `model`,
`offset_minutes` (NOT NULL, Vorgabe `0`), `UniqueConstraint(project_id, make, model)`.
`Photo.camera_id` ist ein echter, **nullabler** Fremdschlüssel darauf — `NULL` heißt „Kamera nicht
bestimmbar" und ist ein regulärer Zustand ohne Versatz.

Eine projektübergreifende Kamera-Registry mit einer zweiten Tabelle für den Versatz wäre die
Alternative. Sie erkauft geteiltes Vokabular, das niemand auswertet (anders als bei `fine_labels`,
wo die Häufigkeitsauswertung es braucht), mit einem Prädikat, das in **jeder** Abfrage
ausgeschrieben stehen müsste. Projekteigene Zeilen machen „der Versatz gilt nur in diesem Projekt"
**strukturell**: es gibt keine Zeile, die zwei Projekte sehen könnten.

Die Kehrseite steht: `Photo.camera_id` muss auf eine Zeile **desselben** Projekts zeigen. Das hält
der eine Schreibpfad (der Scan löst die Kamera innerhalb des Projekts des Fotos auf), und ein Test
prüft es.

### 3. Identität ist Hersteller **und** Modell, ohne Seriennummer

Gelesen werden EXIF `Make` (271) und `Model` (272) aus demselben Range-Read-Fenster wie Zeit und
Koordinate — kein zusätzlicher Netzwerkzugriff. Normalisiert wird durch Trimmen von
Whitespace/NUL und Zusammenziehen innerer Leerraumfolgen; ein Wert, der danach leer oder länger als
`MAX_CAMERA_FIELD_LENGTH` ist, gilt als nicht vorhanden. Sind beide nicht vorhanden, bleibt
`camera_id` `NULL`. **Verworfen, nie abgeschnitten** — ein gekürztes Modell wäre eine andere Kamera.

Die Gehäuse-Seriennummer geht **nicht** ein. Sie fehlt in vielen Dateien; eine Identität, die sie
nutzt, wenn sie da ist, spaltet dieselbe Kamera in zwei Einträge mit getrennten Versätzen, und das
fällt erst auf, wenn die Gruppierung wieder falsch ist. Die in Kauf genommene Kehrseite: zwei
baugleiche Gehäuse im selben Projekt sind **eine** Kamera und teilen einen Versatz.

Verglichen wird zeichengenau, ohne Groß-/Kleinschreibungs-Normalisierung: die Werte stammen aus der
Firmware und sind über die Dateien einer Kamera byte-gleich. Ein Modellname, der sich in einer
Firmware-Version anders schreibt, erscheint zweimal in der Liste — sichtbar, und der Nutzer setzt
den Versatz zweimal.

### 4. Einheit ist die vorzeichenbehaftete Ganzzahl Minuten

`offset_minutes: int`, negativ wie positiv, mit Ober- und Untergrenze am Endpunkt. Kein
`timedelta`-Feld, kein Sekundenanteil (die Story verlangt Minutengenauigkeit), keine
Zeitzonenzugehörigkeit: abgebildet wird eine feste Zeitspanne, keine Regel mit Sommer-/Winterzeit.
`taken_at` bleibt zonenlos wie bisher.

Die Anwendung des Versatzes ist eine reine Funktion. Ergäbe sie ein Datum außerhalb des
darstellbaren Bereichs, liefert sie „kein Ergebnis" statt einer Ausnahme; der Schreibpfad am
Endpunkt **weist den Versatz dann zurück** (kein Teilschreiben), der Scan schreibt für dieses eine
Foto die unkorrigierte Zeit und protokolliert das mit festem Grund-Token.

### 5. Ein Versatzwechsel gliedert den letzten erfolgreichen Kriterien-Lauf neu — in derselben Transaktion

Reihenfolge, Anzeige und Ortsherleitung sind mit Punkt 1 sofort richtig; die **Events** sind
persistierte Lauf-Artefakte (ADR 0087) und wären es nicht. Der Endpunkt, der den Versatz setzt,
verwirft deshalb die Rangzeilen und Events des letzten erfolgreichen Laufs und schreibt sie neu —
aus **bereits persistierten** Werten (`photo_criterion_scores`, `photo_category_classifications`,
`photo_landmark_detections`, `photo_scores.category_override`). Kein Cloud-Aufruf, keine
Bildverarbeitung, kein neuer Lauf.

Löschen und Neuschreiben statt Umhängen: `UniqueConstraint(criterion_scoring_run_id, position)`
verbietet, dass alte und neue Events desselben Laufs gleichzeitig existieren.

**Es ist derselbe Code wie im Lauf.** Die Kategorie-Zugehörigkeiten werden **neu abgeleitet**, nicht
aus den alten Zeilen übernommen — sonst gäbe es zwei Wege zur Hauptkategorie, und ein
zwischenzeitlich gesetzter Override könnte still verloren gehen. Daraus folgt eine prüfbare Zusage:
ein Neuaufbau mit Versatz `0` erzeugt denselben Zustand wie der Lauf selbst.

Läuft gerade ein Kriterien-Lauf des Projekts, wird die Versatz-Änderung **abgelehnt** (`409`) statt
gegen einen halb geschriebenen Lauf zu arbeiten.

### 6. Der Vorschlag rechnet auf der aufgezeichneten Zeit und wird nicht persistiert

Vorgeschlagener Versatz = `taken_at` des Referenzfotos − `taken_at_original` des Kamerafotos, auf
die nächste Minute gerundet. Die **aufgezeichnete** Zeit des Kamerafotos ist der Bezug: rechnete der
Vorschlag auf ihrer korrigierten Zeit, hinge er vom bereits gesetzten Versatz ab und ein zweiter
Aufruf schlüge etwas anderes vor. Beim Referenzfoto ist es umgekehrt die korrigierte Zeit — sie ist
die Zeit, die die Anwendung für richtig hält.

Der Vorschlag ist ein Lesevorgang ohne Zustand: kein „vorgeschlagen"-Feld, keine Zeile. Übernommen
wird er, indem der Nutzer den Wert über denselben Weg setzt wie einen selbst getippten.

## Konsequenzen

- Zwei Tabellenänderungen in der Migration (`project_cameras` neu, drei Spalten an `photos`) und
  eine Tabelle mehr in `project_deletion.py` — nach `photos`, vor `projects`, weil `photos` auf sie
  zeigt. `Photo.camera_id` ist eine neue Kante in der Erreichbarkeitsprüfung.
- Bereits gescannte Fotos tragen keine Kamera. Damit bestehende Projekte nicht ohne Kameraliste
  bleiben, bekommt `photos` einen Merker „EXIF auf Kamera geprüft"; ein Foto ohne ihn wird beim
  nächsten Scan trotz unveränderten Etags erneut gelesen — nur das EXIF-Fenster, ohne Voll-Download
  und ohne Thumbnail-Neuerzeugung. Einmalig; danach ist der Merker gesetzt, auch wenn die Datei
  keine Kamera nennt.
- `PhotoOut.taken_at` liefert ab jetzt die korrigierte Zeit. Der brechende Bedeutungswechsel ist
  beabsichtigt; `taken_at_original` und der Versatz treten als eigene Felder daneben, damit eine
  korrigierte Anzeige als korrigiert erkennbar bleibt.
- Der Aufnahmezeitraum der Statistik und die Sortierung der Fotoliste ändern sich ohne
  Codeänderung, sobald ein Versatz gesetzt ist.
- Ein Versatzwechsel vergibt neue Event- und Rangzeilen-Ids. Der Lesepfad muss danach neu abgefragt
  werden; ein Client, der Event-Ids zwischenspeichert, hält sie nicht über die Änderung hinweg.
- `docs/architecture.md` zieht im selben Pull Request nach.
