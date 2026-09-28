# 0551 - Personenübersicht je Projekt: Gesichter zuordnen, Namen prüfen

**Status:** Accepted
**Erstellt:** 2026-09-28
**Bezug:** [Issue #551](https://github.com/TheRealKoller/photosort/issues/551), ADR [`0127`](../decisions/0127-personen-gesichtsbezug-nur-fuer-festgelegte-ohne-namen-auf-anfrage.md), Vorgänger [Spec 0292](./0292-personen-erkennen.md)

**Umfang:** über dem Richtwert von rund 200 Zeilen. Grund: Die Story ändert eine biometrische Datenklasse, bringt einen Endpunkt mit Modellläufen auf Anfrage, eine Schreibsperre und eine neue Seite mit progressiver Suche, und jede davon hat eigene Zusagen zu Test und Sicherheit.

## Ziel

PhotoSort erkennt Daniel und seine Frau auf Fotos und lernt beide ausschließlich über Gesichter, die ein Nutzer ihm zeigt. Zeigen lässt sich ein Gesicht heute nur Foto für Foto in der Detailansicht, und ebenso lassen sich falsch benannte Fotos nur einzeln prüfen und korrigieren. Das macht das Anlernen mühsam und die Kontrolle unübersichtlich – und von beidem hängt ab, wie gut die Erkennung wird und wie viel spätere Funktionen mit den Namen anfangen können.

Eine Übersicht je Projekt soll beides an einer Stelle erlauben: sehen, welche Fotos welchen der beiden Namen tragen, falsche Namen direkt entfernen und Gesichter ohne Namen schnell einer der beiden Personen zuordnen. Benannt werden weiterhin nur die beiden Nutzer; über andere Menschen speichert PhotoSort weiterhin nichts.

## User Story

Als einer der beiden Nutzer möchte ich in einem Projekt auf einen Blick sehen, welche Fotos unsere Namen tragen und welche gefundenen Gesichter noch keinem Namen zugeordnet sind, und dort direkt ein Gesicht einem von uns zuordnen oder einen falschen Namen entfernen, damit ich PhotoSort unsere Gesichter ohne Foto-für-Foto-Arbeit beibringe und falsche Benennungen im Überblick finde und behebe.

## Akzeptanzkriterien

**Übersicht**

- [ ] Jedes Projekt hat eine Personenübersicht, erreichbar über die Projektnavigation. Sie umfasst alle Fotos des Projekts unabhängig von ihrer Bewertung, auch die im Ausschuss, und zwar in den Gruppen der Personen ebenso wie in „Ohne Namen“.
- [ ] Die Übersicht zeigt je festgelegter Person genau eine Gruppe und genau eine Gruppe „Ohne Namen“.
  - Ohne festgelegte Person gibt es nur „Ohne Namen“.
  - Nach dem Entfernen einer Person fehlt ihre Gruppe beim nächsten Laden der Übersicht, und keine Schaltfläche nennt sie mehr.
- [ ] Gesichter ohne Namen stehen als flache Liste einzelner Gesichter. Nichts in der Übersicht fasst zwei Gesichter ohne Namen zusammen oder weist sie als zusammengehörig aus, auch nicht zwei Gesichter desselben Fotos.
- [ ] Beide Nutzer sehen für dasselbe Projekt beim selben Datenstand dieselbe Übersicht: dieselben Gruppen, Fotos, Anzahlen, Herkünfte und Gesichter ohne Namen. Was einer der beiden ändert, sieht der andere beim nächsten Laden.

**Gruppe einer Person – falsche Namen finden**

- [ ] Die Gruppe einer Person zeigt genau die Fotos des Projekts, die ihren Namen tragen, ob erkannt oder von Hand zugeordnet. Sie nennt ihre Anzahl, und zwar auch dann, wenn noch nicht alle Fotos der Gruppe geladen sind.
  - Je Foto ist die Herkunft erkennbar: „Erkannt“ oder „Von Hand zugeordnet“.
  - Je Foto ist außerdem erkennbar, ob ein Gesicht dieser Person darauf gewählt wurde, und wenn ja, ob PhotoSort daraus gelernt hat („Gesicht gezeigt“) oder nicht („Gesicht gewählt, nicht gelernt“, siehe Obergrenze).
  - Menge und Anzahl sind dieselben wie bei der Einschränkung des Bildbestands auf diese Person ohne Bewertungsfilter. Ein Foto mit beiden Namen steht in beiden Gruppen.
- [ ] Aus der Gruppe heraus lässt sich der Name eines Fotos entfernen, ohne die Detailansicht zu öffnen.
  - Sobald der Server die Änderung bestätigt, verlässt das Foto die Gruppe, ohne dass die Seite neu lädt, und die Anzahl sinkt um eins.
  - Die Wirkung ist dieselbe wie beim Entfernen in der Detailansicht: Der Name kehrt auch nach weiteren Klassifizierungsläufen nicht von selbst zurück, auch wenn die Erkennung die Person auf dem Foto erneut findet, und er ist für beide Nutzer entfernt.
  - War ein Gesicht auf dem Foto an diesen Namen gebunden, steht es danach in „Ohne Namen“.

**Gruppe „Ohne Namen“ – zuordnen**

- [ ] „Ohne Namen“ zeigt als Ausschnitt jedes Gesicht des Projekts, das die Gesichterwahl der Detailansicht für sein Foto anbieten würde und das noch keiner Person zugeordnet ist. Jedes Gesicht erscheint dabei genau einmal.
  - Zu kleine oder unsicher gefundene Gesichter erscheinen nicht; es gilt dieselbe Regel wie in der Detailansicht.
  - Ein Gesicht, das die Erkennung auf seinem Foto einer der Personen zugeordnet hat, erscheint nicht. Erkennungen aus Läufen vor dieser Story kennen ihr Gesicht nicht. Deren Gesicht steht bis zum nächsten Klassifizierungslauf des Projekts in „Ohne Namen“.
  - Trägt ein Foto einen Namen nur als Ganzes (von Hand ergänzt, ohne gewähltes Gesicht), bleiben seine Gesichter in „Ohne Namen“, bis eines davon zugeordnet wird.
- [ ] Ein Gesicht lässt sich mit einem einzigen Druck auf den Namen einer festgelegten Person zuordnen, ohne weitere Rückfrage.
  - Das Foto trägt danach den Namen als „Von Hand zugeordnet“.
  - Das Gesicht gilt ab dem nächsten Klassifizierungslauf in jedem Projekt als gezeigtes Gesicht der Person, genau wie eines, das in der Detailansicht gezeigt wurde, und zählt bei der Anzahl ihrer gezeigten Gesichter mit.
- [ ] Sobald der Server die Zuordnung bestätigt, verlässt das Gesicht „Ohne Namen“, ohne dass die Gruppe neu lädt, und das Foto steht in der Gruppe der Person.
  - Das Gesicht kehrt nicht von selbst nach „Ohne Namen“ zurück, auch nicht nach erneutem Öffnen der Übersicht oder nach weiteren Klassifizierungsläufen.
  - Das gilt, solange die Bilddatei des Fotos unverändert bleibt.
- [ ] Mehrere Gesichter lassen sich nacheinander zuordnen, ohne die Übersicht zu verlassen und ohne die Stelle in der Gruppe zu verlieren.
  - Nach jeder Zuordnung liegt der Fokus auf dem nachrückenden Gesicht an derselben Stelle.
  - Die Suche beginnt dabei nicht von vorn.
  - Ein weiteres Gesicht lässt sich zuordnen, während die vorige Zuordnung noch gespeichert wird.
- [ ] Sind weniger als zwei Personen festgelegt, lässt sich aus „Ohne Namen“ heraus mit einem Gesicht eine neue Person samt Namen festlegen.
  - Es gelten dieselben Namensregeln wie bisher.
  - Eine dritte Person wird abgewiesen und legt nichts an, auch wenn zwei Festlegungen gleichzeitig eintreffen.
- [ ] Hat eine Person bereits die Höchstzahl gezeigter Gesichter, benennt eine weitere Zuordnung nur noch das Foto („Von Hand zugeordnet“), ohne dass PhotoSort daraus lernt; die Zahl ihrer gezeigten Gesichter bleibt gleich.
  - Das wird bei der Zuordnung sichtbar gesagt, in der Übersicht wie in der Detailansicht.
  - Das Gesicht verlässt trotzdem „Ohne Namen“.
  - Die Abweisungen der nächsten Regel gelten auch an der Höchstzahl.
- [ ] Eine abgewiesene Zuordnung ändert nichts, nennt den Grund ohne einen Namen und lässt das Gesicht in „Ohne Namen“. Abgewiesen wird eine Zuordnung in diesen Fällen, auch wenn zwei Zuordnungen gleichzeitig eintreffen:
  - Das Gesicht gleicht der anderen Person.
  - Das Gesicht gehört auf diesem Foto schon der anderen Person, von Hand zugeordnet oder erkannt. Soll ein als die andere Person erkanntes Gesicht umbenannt werden, ist zuerst deren Name auf dem Foto zu entfernen.
  - Dieser Person ist auf diesem Foto schon von Hand ein Gesicht zugeordnet. Hat die Erkennung ihr dort ein Gesicht zugewiesen, sperrt das nicht: Die Zuordnung von Hand geht dann vor.
  - Der Name ist doppelt.
  - Es gibt schon zwei Personen.
  - An der Stelle ist auf dem Foto kein Gesicht mehr zu finden. In diesem Fall werden die Gesichter dieses Fotos in „Ohne Namen“ neu gesucht.

**Zurücknehmen eines gezeigten Gesichts**

- [ ] Ein auf einem Foto des Projekts gezeigtes Gesicht lässt sich in der Übersicht zurücknehmen.
  - Danach trägt das Foto den Namen nicht mehr, und die Zahl der gezeigten Gesichter der Person sinkt um eins.
  - Das Gesicht steht wieder in „Ohne Namen“, an seiner Stelle in der Reihenfolge und ohne Neuladen der Übersicht.
  - Ab dem nächsten Klassifizierungslauf wirkt es in keinem Projekt mehr auf die Erkennung.
  - Andere gezeigte Gesichter derselben Person bleiben unberührt.
- [ ] Das gilt für Gesichter, die ab dieser Story gezeigt werden, gleich ob in der Übersicht oder in der Detailansicht. Das Entfernen des Namens in der Detailansicht nimmt ein solches Gesicht ebenso zurück.
  - Früher gezeigte Gesichter sind keinem Foto zuzuordnen: Das Entfernen eines Namens nimmt keines davon zurück, und die Zahl der gezeigten Gesichter bleibt dabei gleich.
  - Sie lassen sich wie bisher nur durch Entfernen der Person loswerden.

**Schutz der Gesichtsdaten**

- [ ] Über Menschen, die nicht festgelegt sind, bleibt nichts dauerhaft gespeichert.
  - Öffnen und vollständiges Durchsehen der Übersicht hinterlassen in der Datenbank, im Dateispeicher und im Protokoll keine Spur eines Gesichts: keine Box, keinen Index, keinen Ausschnitt, keine Anzahl.
  - Der Datenbestand ist danach derselbe wie vorher.
  - Auch eine Zuordnung speichert nur das zugeordnete Gesicht, nichts über die übrigen Gesichter desselben Fotos.
  - Ein fremdes Gesicht lässt sich deshalb nicht als „niemand von uns“ abhaken; es bleibt in „Ohne Namen“.
- [ ] Gesichtssuche und Ausschnitte entstehen ausschließlich auf dem eigenen Server, auch mit Cloud-Einwilligung. Keine Anfrage an einen Dritten enthält einen Gesichtsausschnitt, ein Gesichtsmerkmal oder einen Namen.
- [ ] Die Übersicht zeigt zu einem Gesicht keine Zahl, Ähnlichkeit oder Sicherheit und schlägt für ein Gesicht ohne Namen keine Person vor.
  - Die Namen stehen an jedem Gesicht gleich: in derselben Reihenfolge und Ausprägung, keiner hervorgehoben oder vorgewählt.
  - Die Reihenfolge in „Ohne Namen“ ergibt sich allein aus dem Foto und der Lage des Gesichts darauf (von links nach rechts). Für das Auflisten wird kein Gesichtsmerkmal berechnet.
  - Gezählt werden in „Ohne Namen“ nur Fotos, nie Gesichter.

**Zusammenspiel und große Projekte**

- [ ] Jede Änderung in der Übersicht ist beim nächsten Laden in Detailansicht, Personeneinschränkung und Album-Entwurf sichtbar, und umgekehrt: Eine Änderung dort ist beim nächsten Laden der Übersicht sichtbar.
- [ ] Zuordnen, Festlegen, Entfernen und Zurücknehmen ändern weder Bewertungen, Motive, Statistik, Album-Entwurf noch Auswahlvorschlag. Das Ergebnis dieser Ansichten ist danach dasselbe wie in einem gleichen Projekt ohne diese Handlungen, abgesehen von den Namen selbst.
- [ ] Die Übersicht ist auch in einem Projekt mit mehreren tausend Fotos bedienbar.
  - Die Gruppen der Personen erscheinen, ohne auf die Gesichtssuche zu warten.
  - Solange „Ohne Namen“ noch zusammengestellt wird, ist sichtbar, dass die Gruppe unvollständig ist, und wie viele Fotos schon durchgesehen sind.
  - Bereits gefundene Gesichter lassen sich schon zuordnen. Eine Zuordnung wartet dabei auf höchstens ein Foto der laufenden Suche, nie auf deren Ende.
  - Unterbricht ein Fehler die Suche, bleiben die gefundenen Gesichter stehen, und die Suche lässt sich an derselben Stelle fortsetzen.
  - Fotos, die dafür noch nicht bereit sind (noch ohne Vorschau oder nicht lesbar), fehlen erkennbar: Ihre Zahl wird genannt.

## Datenmodell-Bezug

Keine neue Tabelle. `photo_person_detections` und `photo_person_corrections` bekommen je eine Gesichtsbox (vier Spalten, nur für das Gesicht einer festgelegten Person), `photo_person_corrections` zusätzlich `reference_id → person_references`. `person_references` bleibt ohne Foto- und Projektbezug. Form, Einschränkungen und Migration stehen im Unterabschnitt „Datenmodell“ unten; `docs/architecture.md` zieht im Umsetzungs-PR nach.

## Architektur / Umsetzung

**Entscheidung:** ADR [`0127`](../decisions/0127-personen-gesichtsbezug-nur-fuer-festgelegte-ohne-namen-auf-anfrage.md) regelt vier Punkte: den Gesichtsbezug als Box nur für die festgelegten Personen, die Rücknahme, die Regel, welches Gesicht als zugeordnet gilt, und „Ohne Namen" als Auflistung auf Anfrage im API-Prozess. Sie löst ADR 0126 in Punkt 3 (API-Prozess) und Punkt 6 (Spaltensätze) teilweise ab, die Kopfzeile dort ist gesetzt. Alles Übrige aus ADR 0126 und Spec 0292 gilt weiter: Verfahren, Entscheidungsregel, Ein-Thread-Executor, Import-Graph, Löschen und Telemetrie. `docs/architecture.md` (Datenmodell, Personenabschnitt) zieht im Umsetzungs-PR nach.

### Ansatz

- **Die Gruppen der Personen sind die bestehende Personeneinschränkung.** Je Person liest die Übersicht `GET /projects/{id}/photos?person_id=<id>` seitenweise, ohne Bewertungsfilter. Menge, Reihenfolge (`taken_at, id`) und Anzahl (`total`) sind damit genau die des Bildbestands, einschließlich Ausschuss. Die Gruppen kommen rein aus der Datenbank und stehen deshalb sofort. Ein Foto mit beiden Namen steht in beiden Gruppen.
- **Herkunft und gezeigtes Gesicht:** `PhotoPersonOut` bekommt `face: "shown" | "assigned" | null`.
  - `shown`: Die Korrektur trägt Box und Referenz.
  - `assigned`: Die Korrektur trägt eine Box ohne Referenz. Das Gesicht wurde an der Obergrenze zugeordnet, oder die Referenz fiel durch einen Modellwechsel weg.
  - `null`: Name nur für das ganze Foto, oder erkannt.
  - Den Wert liefert das eine Konstrukt `effective_person_assignments()` als zusätzliche Spalte. Im Zweig der Erkennung ist sie immer `NULL`.
- **Name entfernen und Gesicht zurücknehmen sind dieselbe Schreiboperation:** `PUT /photos/{id}/persons/{person_id}` mit `{applies: false}`.
  - Trägt die Korrektur eine Box, leert der Aufruf Box und `reference_id` und löscht die verknüpfte Referenz in derselben Transaktion (ADR 0127 Punkt 2).
  - Das gilt ebenso für „Entfernen" in der Detailansicht. Ein gezeigtes Gesicht auf einem Foto, das diesen Namen nicht mehr trägt, gibt es nicht.
- **Zuordnen:** Der Weg ist derselbe wie beim Festlegen in der Detailansicht, `POST /persons` bzw. `POST /persons/{id}/references` mit `{photo_id, face_index}`.
  - Neu speichert er in der Korrektur die Box des Gesichts und die Id der neuen Referenz.
  - **An der Obergrenze** entsteht keine Referenz, sondern nur die Korrektur mit Box. Die Antwort meldet `learned: false`, statt wie bisher `409` zu liefern. Das gilt in beiden Ansichten, denn es ist derselbe Endpunkt.
- **„Ohne Namen"** listet `GET /projects/{id}/unnamed-faces?after_id=<cursor>` seitenweise auf. Der Client lädt die Seiten selbsttätig nacheinander, solange die Übersicht offen ist.
  - Eine Seite umfasst die Fotos des Projekts nach `Photo.id`, ab dem Foto nach `after_id`. Sie endet nach `max_photos` Fotos (Vorgabe und Höchstwert `UNNAMED_PAGE_MAX_PHOTOS = 24`) oder am Ende des Fotos, mit dem `UNNAMED_PAGE_MAX_FACES = 48` Gesichter erreicht sind.
  - **Gesicht wieder einfügen:** Nach „Name entfernen" oder „Gesicht zurücknehmen" in der Übersicht fragt der Client dasselbe Foto einzeln neu ab (`after_id = photo_id - 1`, `max_photos = 1`). Das tut er nur, wenn der Cursor der Suche dieses Foto schon passiert hat; sonst findet die Suche es ohnehin. Die Gesichter dieses Fotos ersetzt er an ihrer Stelle in der Folge (Foto-Id, Index). Es gibt keinen eigenen Endpunkt und keine eigene Regel.
  - Die Antwort trägt einen Fortschritt (`photos_done`/`photos_total`) und die Ids der Fotos, die nicht bereit sind. So ist die Gruppe erkennbar unvollständig, und fehlende Fotos fehlen nicht stillschweigend.
  - Je Foto gibt es **einen** Aufruf auf dem bestehenden Ein-Thread-Executor: Display-Variante laden, `analyzer.detect`, dann `unassigned_faces` gegen die zugeordneten Boxen des Fotos, dann `face_crop_jpeg` für die übrigen. Eine Zuordnung, die währenddessen eintrifft, reiht sich zwischen zwei Fotos ein und wartet nie eine ganze Seite ab.
  - **Keine DB-Verbindung über den Modellaufruf:** Je Foto werden Variantenpfad und zugeordnete Boxen in einer kurzen Lesetransaktion gelesen. Die Transaktion endet, die Verbindung geht an den Pool zurück, erst dann folgt der Auftrag an den Executor. Der Endpunkt öffnet dafür je Foto eine eigene Sitzung aus einer neuen Dependency `get_session_factory` in `api/deps.py` (liefert `db.async_session_factory`, in Tests per `dependency_overrides` auf die Test-Engine gesetzt).
    - **Die Anfrage-Sitzung wird vorher freigegeben.** `get_current_user` liest den Nutzer über `get_session`. FastAPI gibt dem Endpunkt je Anfrage dieselbe Sitzung (`Depends(get_session)`), und ihre automatisch begonnene Transaktion hielte die Verbindung sonst bis zum Ende der Anfrage.
    - Der Endpunkt nimmt diese Sitzung als Parameter. Er liest mit ihr Projektprüfung (`404`), `photos_total` und die Foto-Ids der Seite und ruft dann `await session.close()` vor dem ersten Executor-Auftrag. Danach benutzt er sie nicht mehr.
    - Nachweis: `get_session` und `get_session_factory` auf derselben Test-Engine; während eines angehaltenen `detect` hält die Anfrage keine Verbindung (Pool-Saldo 0).
  - Zwischen zwei Fotos prüft der Endpunkt `await request.is_disconnected()`. Bei getrennter Verbindung bricht er ab, ohne Antwort.
  - **`embed` läuft in der Auflistung nie.** Es entsteht kein Merkmal und keine Ähnlichkeit. Die Reihenfolge (Foto-Id, dann Gesichtsindex links→rechts) kann deshalb keine Ähnlichkeit verraten, und unbekannte Gesichter werden nie gruppiert.
  - Die Ausschnitte kommen base64-codiert in der Seitenantwort, damit nicht jede Kachel einen zweiten Detektionslauf auslöst.
  - Fehlt die Display-Variante, ist das Bild nicht lesbar oder wirft der Analyzer, steht das Foto in `not_ready_photo_ids`. Ohne Variante wird das Modell nicht gerufen. Eine Ausnahme wird nur mit Typname und `photo_id` protokolliert.
  - Die Auflistung schreibt nichts, weder in die Datenbank noch in eine Datei oder einen Prozess-Cache.
- **Welches Gesicht als zugeordnet gilt**, entscheidet allein `persons.py::assigned_face_boxes` (ADR 0127 Punkt 3). Je Paar (Foto, Person) gilt die erste zutreffende Regel:
  1. Korrektur `applies=false`: kein Gesicht.
  2. Korrektur mit Box: diese Box.
  3. Erkennung mit Box: diese Box.
  4. Sonst: kein Gesicht.

  Ein Name, der nur für das ganze Foto vergeben wurde, lässt die Gesichter des Fotos in „Ohne Namen", solange die Erkennung das Gesicht nicht benennt.
- **Gleiches Gesicht:** Die IoU mit einer gespeicherten Box erreicht `SAME_FACE_MIN_OVERLAP = 0.5`. Jede Box gilt für höchstens ein Gesicht, nämlich das mit der größten Überdeckung.
- **Erkennung mit Gesichtsbezug:** `decide_assignments` liefert `dict[person_id, face_index]`, also das eine Kandidatengesicht je erkannter Person. Die Phase `persons` schreibt dessen Box in die Erkennungszeile. Eine Erkennung aus einem früheren Lauf trägt keine Box, bis ein neuer Klassifizierungslauf sie ersetzt.
- **Zwei neue Abweisungen**, beide `409` ohne Schreiben:
  - Diese Person hat auf diesem Foto schon ein Gesicht **per Korrektur** (Regel 2 aus ADR 0127 Punkt 3). Das wird vor dem Modellaufruf geprüft und unter der Schreibsperre per bedingtem Setzen wiederholt. Eine Erkennung derselben Person mit Box sperrt nicht: Ein erkanntes Gesicht ausdrücklich zu zeigen ist Anlernen, und die Box der Korrektur geht vor. `detail`: „Diese Person hat auf diesem Foto schon ein Gesicht.“
  - Das Gewählte überdeckt das Gesicht, das auf diesem Foto der anderen Person zugeordnet ist, nach **`assigned_face_boxes`**, also auch ein erkanntes. Wer ein fälschlich als A erkanntes Gesicht B zuordnen will, entfernt erst den Namen A. Das wird nach der Detektion unter der Schreibsperre geprüft. `detail`: „Dieses Gesicht gehört auf diesem Foto schon der anderen Person.“
- **Frontend:** eine neue Projektseite `/projects/:projectId/persons` (`ProjectPersonsPage`).
  - Je Person eine Gruppe über den neuen Hook `usePersonGroupQuery(projectId, personId)`, danach die Gruppe „Ohne Namen" über den neuen Hook `useUnnamedFaces`.
  - `usePersonGroupQuery` ruft `listPhotos(projectId, {limit: PERSON_GROUP_PAGE_SIZE = 24, offset, personIds: [personId]})` und liegt unter `['photos', projectId, 'person-group', personId]`. Er teilt seinen Schlüssel **nicht** mit `usePhotoSequenceQuery`, denn dessen Schlüssel enthält die Seitengröße nicht. Ein Neuladen setzt die gespeicherten Offsets mit der Seitengröße des jeweils ladenden Beobachters ein, und bei 24 und 60 unter demselben Schlüssel entstünden doppelte oder fehlende Fotos. Unter dem Präfix `['photos', projectId]` bleibt er, damit `storePhotoPersons` und die breiten Invalidierungen ihn erreichen.
  - **Großansicht** über `useCurationLightbox` mit einer Instanz je Seite. `items` sind die geladenen Fotos aller Personengruppen, nach Id entdoppelt.
  - Die Gesichtsausschnitt-Kachel wird aus `PersonFacePicker` herausgelöst und von beiden Stellen genutzt.

### Datenmodell

Migration `b0814fc600bf_gesichtsbezug_personen.py`, `down_revision = 1f4027405ea5`; die Kennung stammt aus `scripts/nummern.py migration gesichtsbezug-personen`. Es gibt keine neue Tabelle. Alle Fremdschlüssel und Prüfeinschränkungen sind benannt.

| Tabelle/Spalte | Inhalt | Löschen |
|---|---|---|
| `photo_person_detections.face_box_x/_y/_width/_height` | `FLOAT NULL`. Die Box des erkannten Gesichts, auf die Display-Variante normiert. `ck_photo_person_detections_face_box`: alle vier `NULL` oder alle vier gesetzt, mit `0 <= x,y <= 1` und `0 < width,height <= 1`. Bestehende Zeilen bleiben `NULL`. | mit der Zeile (unverändert) |
| `photo_person_corrections.face_box_x/_y/_width/_height` | wie oben; `ck_photo_person_corrections_face_box`, dazu `ck_photo_person_corrections_face_requires_applies` (`face_box_x IS NULL OR applies`) | mit der Zeile |
| `photo_person_corrections.reference_id` | `→ person_references`, `NULL`, `fk_photo_person_corrections_reference_id` ohne DB-Aktion, `uq_photo_person_corrections_reference_id`, `ck_photo_person_corrections_reference_requires_face` (`reference_id IS NULL OR face_box_x IS NOT NULL`) | Eine Rücknahme löscht die Referenz. Ein Modellwechsel leert die `reference_id`, bevor die Referenz fällt. Eine Projekt- oder Fotolöschung löscht die Korrektur, die Referenz bleibt. |
| `person_references` | Spalten unverändert, **kein** Foto- oder Projektbezug. Sie ist FK-Elternteil der Korrektur wie `users` und deshalb von `projects` aus nicht erreichbar. | mit der Person; bei einer Rücknahme |

- `delete_person` behält seine Reihenfolge: Korrekturen, Erkennungen, Referenzen, Person. Die Korrekturen fallen zuerst, deshalb braucht `reference_id` dort keinen eigenen Schritt.
- `_store_reference` löscht beim ersten Referenz-Schreiben des aktuellen Modells die Referenzen fremder `model_key`. Vorher setzt es per Mengenanweisung `reference_id = NULL` in den Korrekturen, die auf diese Referenzen zeigen.
- Die Werte einer Box werden vor dem Schreiben auf Endlichkeit geprüft, in Einschlussform. Die Prüfeinschränkung ist die zweite Linie.

### Betroffene Dateien

**Backend, geändert:**
- `models.py`: vier Box-Spalten an `PhotoPersonDetection` und `PhotoPersonCorrection`, `reference_id` samt Einschränkungen; Doku-Blöcke beider Klassen nachgezogen.
- `alembic/versions/b0814fc600bf_gesichtsbezug_personen.py` (neu), Muster wie `1f4027405ea5`.
- `person_matching.py`: `decide_assignments(faces) -> dict[int, int]` (Person → Index des einen Kandidatengesichts); Regel und Konstanten unverändert.
- `face_analysis.py`:
  - `FaceAnalyzer.detect`: Eine Detektorzeile ist nur verwertbar, wenn alle 15 Werte endlich sind (Box, Landmarken, Wert). Die Prüfung steht in Einschlussform und läuft vor `is_usable`. Ein Gesicht mit nicht endlicher Geometrie wird damit nie benannt, nie mitgezählt, nie aufgelistet und nie gespeichert. Worker und Auflistung sehen deshalb keine nicht endliche Box.
  - Die Schreibstellen für eine Box prüfen trotzdem auf Endlichkeit. Scheitert die Prüfung, benennt der Worker die Person auf diesem Foto nicht, statt sie ohne Box zu schreiben. Ein übersehenes Foto ist zulässig, eine Erkennung, deren Gesicht in „Ohne Namen“ steht, nicht. Die API antwortet `409` mit `InvalidEmbedding`.
- `face_analysis.py`, rein:
  - `SAME_FACE_MIN_OVERLAP`, `box_overlap(a, b) -> float` (IoU; NaN ergibt „nicht gleich");
  - `unassigned_faces(faces, taken) -> list[int]`: die Indizes, die nach Abzug gehen; je gespeicherter Box fällt höchstens das Gesicht mit der größten Überdeckung, und nur ab der Schwelle.
- `persons.py`:
  - `effective_person_assignments()` mit Spalte `face`, `PersonAssignment.face`;
  - `assigned_face_boxes(session, photo_ids) -> dict[int, list[FaceBox]]` als einzige Stelle der Regel aus ADR 0127 Punkt 3;
  - `create_person(..., face_box)` und `assign_face(...) -> bool`. `assign_face` ersetzt `add_reference`, der Rückgabewert ist `learned`. Die Reihenfolge der Prüfungen ist: Person vorhanden → schon eine Korrektur-Box dieser Person auf dem Foto → Merkmal gültig → gleicht der anderen Person → Gesicht der anderen Person auf diesem Foto (`assigned_face_boxes`) → Obergrenze (nur noch benennen) → schreiben;
  - Die Box an einer bestehenden Korrektur wird **bedingt** gesetzt: `UPDATE … WHERE photo_id = … AND person_id = … AND face_box_x IS NULL`. Trifft das nicht genau eine Zeile, folgen `FaceAlreadyAssignedOnPhoto` (`409`) und ein Rollback samt neuer Referenz. Beim Anlegen trägt `UNIQUE(photo_id, person_id)`, und ein `IntegrityError` wird `409`. Das ist die zweite Linie hinter der Schreibsperre und wirkt unter SQLite wie unter PostgreSQL.
  - `set_correction`: Rücknahme bei `applies=false`; `_store_reference` gibt die Referenz zurück und leert beim Modellwechsel die `reference_id`;
  - `ReferenceLimitReached` entfällt, neu sind `FaceAlreadyAssignedOnPhoto` („Diese Person hat auf diesem Foto schon ein Gesicht.“) und `FaceAssignedToOtherPerson` („Dieses Gesicht gehört auf diesem Foto schon der anderen Person.“). Kein `detail`-Text nennt einen Namen.
- `worker.py`: `_persons_on_photo` liefert `dict[int, FaceBox] | None`. `_recognize_persons` schreibt die Box in die Erkennungszeile. Block-, Commit- und FK-Fehlerverhalten bleiben unverändert.
- `api/persons.py`:
  - `_embedding_at` liefert Merkmal und Box aus demselben Detektionslauf;
  - neu `_unnamed_on_photo(analyzer, path, taken)` für den Executor, der Endpunkt `GET /projects/{project_id}/unnamed-faces` und die Schemata `UnnamedFaceOut`, `UnnamedFacesPageOut`, `FaceAssignmentOut`;
  - `PhotoPersonOut.face`;
  - Router, Auth-Dependency und Executor bleiben dieselben.
  - **Schreibsperre `_person_write_lock`** (ADR 0127 Punkt 2): eine prozessweite `asyncio.Lock`.
    - Gilt für `POST /persons`, `POST /persons/{id}/references`, `PUT /photos/{id}/persons/{person_id}` und `DELETE /persons/{id}`.
    - Unter der Sperre laufen alle Prüfungen in der Datenbank (beide neuen Abweisungen, „gleicht der anderen Person“, Obergrenze), dann Schreiben und Commit.
    - `detect`/`embed` laufen vorher auf dem Executor und nie unter der Sperre. Die frühe Vorprüfung „schon ein Gesicht dieser Person auf dem Foto“ vor dem Modellaufruf bleibt und wird unter der Sperre wiederholt.
    - Ablauf je Schreibaufruf: Vorprüfungen über die Anfrage-Sitzung, dann `await session.rollback()` (gibt die Verbindung frei, auch die aus `get_current_user`), dann Modellaufruf, dann Sperre nehmen, dann alle Prüfungen, Schreiben und Commit in derselben Sitzung (sie beginnt neu). Während des Modellaufrufs und des Wartens auf die Sperre hält die Anfrage keine Verbindung.
    - `rollback()` lässt alle geladenen Objekte verfallen, auch `current_user`. Ein späterer Attributzugriff lädt unter `AsyncSession` implizit nach und scheitert (`MissingGreenlet`). `current_user.id` und alle anderen gebrauchten Werte werden deshalb **vor** dem Rollback in lokale Variablen gelesen.
    - Voraussetzung ist genau ein API-Prozess (`uvicorn` ohne `--workers` und ohne `WEB_CONCURRENCY`, `backend/Dockerfile`, `docker-compose.yml`). Bei mehr als einem Prozess muss die Sperre in die Datenbank.
    - Es gibt **keine** Sperre der Fotozeile (`with_for_update`). Die Schreibsperre deckt Paar, Foto und Obergrenze ab und ist unter SQLite nachweisbar. Eine Sperre der Fotozeile deckte die Obergrenze nicht ab, weil diese über Fotos hinweg gilt, und wirkte in der Testsuite nicht.
    - Die Rücknahme liest `reference_id` unter der Schreibsperre und löscht genau diese Referenz.
- `api/photos.py`: nur indirekt über `photo_person_outs`.
- `project_deletion.py` bleibt unverändert. Dafür legt `tests/project_graph.py::build_project_graph` eine Korrektur mit Box und `reference_id` an. Die Projektlöschung muss dann die Referenz stehen lassen.
- `demo_state.py`: eine Erkennung mit Box und eine Korrektur mit Box und synthetischer Referenz. So ist `face: "shown"` im Prüfstack sichtbar.

**Frontend:**
- `api/types.ts`: `PhotoPersonOut.face`, `FaceAssignmentOut {person, learned, photo_persons}`, `UnnamedFaceOut`, `UnnamedFacesPageOut`.
- `api/persons.ts`: `createPerson`/`addReference` liefern `FaceAssignmentOut`, neu `listUnnamedFaces(projectId, afterId)`; `PERSON_REFUSALS` um die beiden neuen Texte ergänzt.
- `hooks/useFaceAssignment.ts` (neu):
  - Die Mutation für Festlegen und Zeigen, genutzt von `PersonFacePicker` und von „Ohne Namen".
  - Bei Erfolg schreibt `storePhotoPersons` die Liste `photo_persons` aus der Antwort, statt sie lokal zusammenzusetzen, und `PERSONS_QUERY_KEY` wird invalidiert.
  - In der Übersicht wird zusätzlich die Gruppe der Person (`['photos', projectId, 'person-group', personId]`) aktiv neu geladen.
- `hooks/usePersonGroupQuery.ts` (neu): wie oben unter Ansatz beschrieben; getrennt von `usePhotoSequenceQuery` wegen der Seitengröße. **Nachladen nach „Name entfernen“** ohne Neuladen der Gruppe:
  - *Verbleibend* sind die geladenen Einträge (über alle Seiten, nach Id entdoppelt), deren `persons` die Person noch tragen. Die übrigen geladenen Einträge sind *verloren*. „Name entfernen“ ändert über `storePhotoPersons` nur `persons` im Cache.
  - *Rest* = `max(0, letzteSeite.total − (letzterOffset + letzteSeite.items.length))`, mit `letzterOffset` als `lastPageParam`. Das ist die Zahl der Fotos hinter dem geladenen Fenster, so wie der Server sie beim letzten Abruf sah. Entfernen lässt sich nur, was geladen ist, deshalb ändert ein Entfernen diesen Rest nicht.
  - Nächster Offset = Anzahl *verbleibend*. `hasNextPage` gilt genau dann, wenn *Rest* > 0. Grund: Der Server zählt die verlorenen Fotos nicht mehr, alle späteren rücken um ihre Zahl vor.
  - Angezeigte Anzahl = *verbleibend* + *Rest*. Nie `total` der ersten Seite, nie `total` minus verlorene.
  - Gezeigt werden nur *verbleibende* Einträge, nach Id entdoppelt.
  - Nach einer Invalidierung lädt TanStack v5 die Seiten neu und berechnet die Offsets über dieselbe Funktion aus den frischen Seiten. Dort gibt es keine verlorenen Einträge, also gilt Offset = Anzahl geladen.
  - Beispiel: 30 Fotos, Seite 24, 2 Namen entfernt: Anzahl 22 + 6 = 28. „Mehr laden“ lädt ab Offset 22 genau die übrigen 6. Danach ist die Anzahl 28 + 0 = 28, und es gibt keine weitere Seite.
- `hooks/useCurationLightbox.ts`: Der Auslöser wird über einen Schlüssel registriert, nicht mehr über die Foto-Id. Ein Foto mit beiden Namen hat zwei Auslöser.
  - `open(photoId, triggerKey = photoId)` und `triggerRef(triggerKey: number | string)`.
  - Der Schlüssel des öffnenden Auslösers liegt nur in einem Ref, **nie** im Verlaufszustand. Dieser trägt weiter nur die Id (Auflage S2 aus Spec 0531).
  - Beim Schließen bekommt der Auslöser mit diesem Schlüssel den Fokus, sonst der mit der Foto-Id, sonst die Überschrift. Nach einem Reload gibt es den Ref nicht, und es gilt das heutige Verhalten.
  - Die Übersicht nutzt `${personId}:${photoId}`. Die bestehenden Aufrufer (`AlbumDraftPage`, `AlbumSelectionPage`) bleiben unverändert, weil der Standardschlüssel die Foto-Id ist.
- `hooks/useUnnamedFaces.ts` (neu):
  - `useInfiniteQuery` unter `['unnamed-faces', projectId]`. Der Schlüssel liegt bewusst **außerhalb** von `['photos', projectId]`: Sonst startete jede breite Invalidierung die Suche neu, und die Stelle ginge verloren.
  - `gcTime: 0` wirft die Ausschnitte beim Verlassen weg. `refetchOnWindowFocus`/`refetchOnReconnect: false`.
  - Ein Effekt holt die nächste Seite, solange `hasNextPage` gilt und kein Fehler vorliegt.
  - `removeFace(photoId, faceIndex)` entfernt ein zugeordnetes Gesicht lokal aus den Seiten, ohne neu zu laden.
  - `refreshPhoto(photoId, fileName: string | null)` holt ein schon durchsuchtes Foto einzeln neu (`max_photos = 1`) und ersetzt **alle** Gesichter dieses Fotos an ihrer Stelle in der Folge (Foto-Id, Index). Liefert die Antwort null Gesichter, entfallen sie. Steht das Foto in `not_ready_photo_ids`, geht es in die Menge der nicht bereiten Fotos. Liefert die Antwort ein anderes Foto (das Foto ist inzwischen gelöscht), entfallen seine Gesichter. Bei einem Foto, das der Cursor noch nicht erreicht hat, tut es nichts.
    - Aufrufer: ein erfolgreiches `applies=false` aus der Übersicht (`fileName` kommt aus der Karte der Personengruppe) und ein `409` „An dieser Stelle ist auf dem Foto kein Gesicht mehr zu finden.“ beim Zuordnen aus „Ohne Namen“ (`fileName = null`, denn `UnnamedFaceOut` trägt bewusst keinen Pfad).
    - Fehlerzustand: `refreshFailures: readonly {photoId, fileName}[]` (je Foto höchstens ein Eintrag) und `retryRefresh(photoId)`. Ein Erfolg entfernt den Eintrag. Der Fehler berührt die Seiten und den Cursor der Suche nicht. Die Seite zeigt je Eintrag den Alert aus UI/UX, ohne `fileName` in der Fassung ohne Dateinamen.
    - Die Einzelabfrage übernimmt **nichts** in Cursor und Fortschritt (`next_after_id`, `photos_done`, `photos_total`), nur Gesichter und die Angabe „nicht bereit“ dieses Fotos.
    - **Seite im Flug:** Ist eine Seite unterwegs, deren Bereich (`after_id`, offen nach oben) das Foto enthält, wird der Aufruf vorgemerkt. Nach Ankunft oder Fehlschlag der Seite wird gegen den neuen Cursor neu entschieden. Sonst fehlte ein zurückgenommenes Gesicht, das der Server vor dem Commit der Rücknahme bearbeitet hat.
    - **Entfernen während einer Abfrage:** `removeFace(p, i)` wirkt auch auf jede Antwort, deren Abfrage vor dem Entfernen gestartet ist (Seite oder Einzelabfrage). Die spätere Antwort setzt das entfernte Gesicht nicht wieder ein. Eine nach dem Entfernen gestartete Abfrage gilt unverändert.
- `components/FaceCropTile.tsx` (neu): die Kachel aus `PersonFacePicker` (`FaceTiles`), dazu ein Hook, der aus base64 bzw. Blob eine Blob-URL macht und sie beim Entfernen oder Aushängen der Kachel freigibt.
- `components/PersonFacePicker.tsx`:
  - nutzt `useFaceAssignment` und `FaceCropTile`;
  - bei `learned: false` die Meldung, dass nur benannt und nicht gelernt wurde;
  - die neuen Abweisungen; die Behandlung der Obergrenze als `409` entfällt.
- `pages/ProjectPersonsPage.tsx`, `components/PersonPhotoGroup.tsx` und `components/UnnamedFacesGroup.tsx` (neu).
  - **Name entfernen** nutzt `usePhotoPersonControls` bzw. `storePhotoPersons`.
  - Die Gruppe zeigt nur Einträge, die die Person noch tragen. Anzahl und Nachladen folgen der Regel unter `usePersonGroupQuery`. Die übrigen Fotolisten gelten danach als veraltet, wie bisher.
- `utils/projectRoutes.ts`, `App.tsx`, `components/ProjectNav.tsx`: Route `persons` und das Nebenziel „Personen" (`ProjectNavTargetId` um `'persons'`).

### API

Der Router ist derselbe `persons.router` mit `dependencies=[Depends(get_current_user)]`. Der Vollständigkeitstest in `test_auth_guard.py` durchläuft die Routen des Routers und erfasst den neuen Endpunkt damit von selbst. Sein Kommentar zählt dann acht statt sieben Endpunkte. Dazu kommt ein `401`-Fall für den neuen Endpunkt. Alle Eingaben sind begrenzt, alle Eingabeschemata haben `extra="forbid"` mit unveränderten Feldmengen.

- **Neu:** `GET /projects/{project_id}/unnamed-faces?after_id=<int>&max_photos=<int>`.
  - `project_id` hat `ge=1, le=MAX_ID`, `after_id` hat `ge=0, le=MAX_ID` mit Vorgabe `0`, `max_photos` hat `ge=1, le=UNNAMED_PAGE_MAX_PHOTOS` mit Vorgabe `UNNAMED_PAGE_MAX_PHOTOS`.
  - `200` mit `{faces: [{photo_id, face_index, crop_jpeg}], not_ready_photo_ids: [int], next_after_id: int | null, photos_done: int, photos_total: int}`.
    - `crop_jpeg` ist base64 eines neu codierten JPEG, höchstens 160 px.
    - `photos_done` zählt die Fotos des Projekts mit `id <= ` dem letzten bearbeiteten Foto, `photos_total` alle Fotos des Projekts.
    - `next_after_id` ist die Id des letzten bearbeiteten Fotos. Sie ist `null` genau dann, wenn das Projekt kein Foto mit größerer Id hat. Bei genau `max_photos` restlichen Fotos gibt es also keine leere Folgeseite.
  - Kopfzeilen `Cache-Control: no-store` und `X-Content-Type-Options: nosniff`.
  - `404` bei unbekanntem Projekt. Es gibt keine Box, keinen Wert und keinen Namen in der Antwort.
- **Geändert:** `POST /persons` → `201 FaceAssignmentOut {person: PersonOut, learned: true, photo_persons: [PhotoPersonOut]}`.
  - Neu ist `409` „Gesicht der anderen Person auf diesem Foto".
  - Die übrigen Fälle sind unverändert: `422` für einen ungültigen Namen, `409` für zwei Personen, einen doppelten Namen, ein fehlendes Gesicht, ein ungültiges Merkmal oder „gleicht der anderen Person", `404` für ein fehlendes Foto oder eine fehlende Variante.
- **Geändert:** `POST /persons/{id}/references` → `201 FaceAssignmentOut`.
  - An der Obergrenze gilt `learned: false` statt `409`.
  - Neu sind `409` „schon ein Gesicht dieser Person auf diesem Foto" und `409` „Gesicht der anderen Person auf diesem Foto".
  - Die übrigen Fälle sind unverändert.
- **Geändert (Wirkung):** `PUT /photos/{id}/persons/{person_id}` mit `{applies: false}` auf einem Paar mit Box ist die Rücknahme. Antwort und Schema sind unverändert.
- **Geändert (Schema):** `PhotoPersonOut` ist `{person_id, origin, face}`, überall, wo er vorkommt: Liste, Entwurf, Detail, PUT.
- `GET /photos/{id}/faces`, `…/faces/{index}/image`, `GET /persons` und `DELETE /persons/{id}` bleiben unverändert.
- Es schreibt kein `FeedbackEvent`. Bewertungen, Motive, Rangfolge, Entwurf und Auswahlvorschlag werden nicht berührt.

### Invarianten

Die Auswahl der Tests bleibt beim test-engineer.

- **Nichts über Unbekannte:**
  - Eine Auflistung über beliebig viele Seiten hinterlässt in allen Tabellen denselben Stand.
  - Die Auflistung ruft `embed` nie auf, der Fake-Analyzer zählt die Aufrufe.
  - Box, Index, Ausschnitt oder Anzahl eines Gesichts ohne festgelegte Person werden nie gespeichert.
- **Spaltensätze** (S5 fortgeschrieben):
  - `photo_person_detections` = `{photo_id, person_id, computed_at, face_box_x, face_box_y, face_box_width, face_box_height}`;
  - `photo_person_corrections` = Satz aus 0292 plus die vier Box-Spalten und `reference_id`;
  - `person_references` unverändert und ohne Foto- oder Projektspalte;
  - Antwortschemata auf Gleichheit: `UnnamedFaceOut = {photo_id, face_index, crop_jpeg}`, `PhotoPersonOut = {person_id, origin, face}`.
- **Vorrang je Gesicht:** Die Regel aus ADR 0127 Punkt 3 steht nur in `assigned_face_boxes`. Die wirksame Zuordnung je Foto steht weiter nur in `effective_person_assignments`.
- **Rücknahme:**
  - Nach `applies=false` auf einem Paar mit Box existiert die verknüpfte Referenz nicht mehr, Box und `reference_id` sind `NULL`, und andere Referenzen sind unberührt.
  - Das Gesicht erscheint danach wieder in der Auflistung, auch wenn eine Erkennung mit Box für das Paar besteht.
- **Obergrenze:** Eine Zuordnung an der Obergrenze legt keine Referenz an. Sie schreibt eine Korrektur mit Box ohne `reference_id` und liefert `learned: false`. Das Gesicht fehlt danach in der Auflistung.
- **Eindeutigkeit:** Je (Foto, Person) gibt es höchstens eine Box. Eine Box an einer Korrektur und die Box der anderen Person auf demselben Foto überdecken sich nie über der Schwelle. Ein Verstoß ergibt `409` ohne Schreiben.
  - Das gilt auch bei gleichzeitigen Anfragen, ebenso wie „höchstens `MAX_REFERENCES_PER_PERSON` Referenzen“. Beides sichert die Schreibsperre.
  - Nachweis: Ein zweiter Aufruf wird zwischen die Detektion und das Schreiben des ersten eingeschoben. Ergebnis ist genau ein `201`, ein `409` und eine Box. Zwei gleichzeitige Zuordnungen bei 19 Referenzen ergeben 20 Referenzen und `learned: false` beim zweiten Aufruf.
- **Beständigkeit:** Kein Lauf schreibt oder löscht eine Korrektur, ihre Box oder `reference_id`. Ein zugeordnetes Gesicht kehrt deshalb nie von selbst nach „Ohne Namen" zurück.
- **Löschen:**
  - Nach `delete_person` bleibt keine Zeile mit der `person_id`.
  - Die Projektlöschung lässt `persons` und alle `person_references` stehen, auch die über eine Korrektur verknüpften.
  - Ein Modellwechsel scheitert nicht am Fremdschlüssel `reference_id`.
- **Unverändert aus 0292:**
  - Importregeln aus ADR 0126 Punkt 1. `face_analysis` bleibt ohne `models`, `db` und `config`, `persons.py` importiert direkt keinen Netzwerk-Client.
  - Keine Personendaten in `selection.py`, `quality.py`, `ranking.py`, `motifs.py` und `api/stats.py`.
  - Nur lokal, auch mit Cloud-Einwilligung.
  - Log-Hygiene S11: Die Auflistung loggt keine Box, keinen Index je Foto und keinen Ausschnitt, bei Ausnahmen nur Typname und `photo_id`.
  - Die Modellaufrufe laufen nur auf dem Ein-Thread-Executor, und gelesen wird nur die `display`-Variante.
- **Gleiche Menge:** Die Gruppe einer Person ist der Aufruf der Personeneinschränkung und kein eigener Lesepfad.
- **Frontend:**
  - Ausschnitte existieren nur als Blob-URL. Die URL wird beim Entfernen der Kachel und beim Verlassen der Seite freigegeben.
  - Der Cache der Auflistung liegt außerhalb von `['photos', …]` mit `gcTime: 0`. Eine Zuordnung lädt „Ohne Namen" nicht neu.

### Reihenfolge der Umsetzung

1. **Datenmodell:** Modelle, Migration `b0814fc600bf` samt Migrationstest (auf- und abwärts), Einschränkungen, `tests/project_graph.py`.
2. **Rein:** `decide_assignments` mit Index, `box_overlap` und `unassigned_faces`.
3. **`persons.py`:**
   - `assigned_face_boxes`;
   - `effective_person_assignments` mit `face`;
   - `create_person` und `assign_face` mit Box, Obergrenze und den zwei Abweisungen;
   - Rücknahme in `set_correction`;
   - `_store_reference` beim Modellwechsel.
4. **Worker:** Box in der Erkennungszeile.
5. **API:**
   - `FaceAssignmentOut` für beide POST-Endpunkte, dazu `PhotoPersonOut.face`;
   - danach `GET /projects/{id}/unnamed-faces` mit Executor je Foto, Seitengrenzen, `not_ready_photo_ids` und Kopfzeilen;
   - `401`-Fall für den neuen Endpunkt;
   - `_person_write_lock` um die vier schreibenden Endpunkte.
6. **`demo_state.py`.**
7. **Frontend:**
   - Typen und API;
   - `FaceCropTile` herauslösen und `useFaceAssignment` einführen; `PersonFacePicker` umstellen, dabei bleiben die bestehenden Tests grün, bis auf die gewollten Änderungen an Obergrenze und Antwortform;
   - `useUnnamedFaces`;
   - Seite und Gruppen;
   - Route und Nebenziel.
8. **Prüfstack und Oberflächenprüfung.** `no-horizontal-scroll` bekommt die neue Route.

## UI/UX

Zur Story gibt es keinen `## Design`-Block und keinen Penpot-Entwurf. Maßgeblich sind `specs/architecture/0004-design-system.md` und der Skill `design-system`. Es kommen keine neue Abhängigkeit, kein neues Symbol und kein neues Farbtoken hinzu. Namen und Dateinamen sind Fremdtext und werden nur als React-Textknoten gerendert.

### 1. Einstieg und Seitenaufbau (`ProjectPersonsPage`, `/projects/:projectId/persons`)

**Einstieg:**
- `ProjectNav` bekommt das Nebenziel „Personen“ (`ProjectNavTargetId` `'persons'`). Es steht **hinter** „Einstellungen“ und „Statistik“: Die beiden bestehenden Ziele behalten ihren Platz, das ist bei wiederkehrender Nutzung verlässlicher als eine Umsortierung.
  - Ab `lg:` liegt es im Panel des Auslösers „Projektbereiche“. Darunter steht es im zweiten Block des Panels. Aktiv-Markierung, `aria-current` und Zeilenhöhe übernimmt es aus dem Bestand.
- Keine weitere Verknüpfung aus der Detailansicht. Deren Kopfzeile trägt schon „Personen verwalten“, ein zweiter Link bräche bei 360 px um.

**Kopf:**
- `h1` „Personen“ (`text-xl sm:text-2xl`, `tabIndex={-1}`, Fokus-Rückfallziel), darunter „Alle Fotos dieses Projekts, auch im Ausschuss. Namen und gezeigte Gesichter gelten in allen Projekten.“ (`text-sm text-text`).
- Rechts „Personen verwalten“ (`Button asChild variant="ghost" size="sm"` → `/persons`), wie im Personenabschnitt der Detailansicht. Unter `sm` bricht die Zeile um (`flex flex-wrap justify-between gap-3`).
- **Sprungleiste**, sobald mindestens eine Person festgelegt ist:
  - `nav aria-label="Gruppen"` mit `ul flex flex-wrap gap-3`. Je Gruppe ein `a href="#…"` als `Button asChild variant="outline" size="sm"`, beschriftet mit dem Namen bzw. „Ohne Namen“, in Gruppenreihenfolge. Namen werden nie gekürzt.
  - Ein Druck scrollt zur Gruppenüberschrift und setzt den Fokus darauf. Die Überschrift trägt `tabIndex={-1}` und `scroll-mt-header`, damit sie nicht unter der festen Kopfzeile liegt. Die Adresse ändert sich nicht.
  - Zweck: In einem großen Projekt liegen vor „Ohne Namen“ zwei Personengruppen. Am Telefon wären das mehrere Bildschirmhöhen.

**Gruppen:** je festgelegte Person eine Gruppe in der Reihenfolge von `GET /persons`, danach **immer zuletzt** „Ohne Namen“. Das folgt dem Muster „Auffang-/Restgruppe“, hat hier aber einen zweiten Grund: „Ohne Namen“ wächst während der Suche am Ende. Stünde sie oben, verschöbe jede nachgeladene Seite alles darunter.
- Jede Gruppe ist eine `section` mit `aria-labelledby` auf ihr `h2` (`text-lg`) und mit einer stabilen `id` als Sprungziel.
- Zwischen den Gruppen liegt `gap-8`. Es gibt keine Trennlinie: Die Überschriften tragen die Gliederung.

**Seitenzustände:**
- Personen laden: zwei Gruppen-Platzhalter (Überschriftbalken plus drei Kartenplatzhalter, siehe unten), `role="status"` „Personen werden geladen…“.
- Personen-Ladefehler: nur ein `Alert` „Die Personen konnten nicht geladen werden.“ mit „Erneut versuchen“. Ohne Personenliste lassen sich weder Gruppen bilden noch Gesichter zuordnen.
- Keine Person festgelegt: Die Sprungleiste entfällt. An Stelle der Personengruppen steht der ruhige Satz „Noch keine Person festgelegt. Wähle bei einem Gesicht unter „Ohne Namen“ „Neue Person…“, um sie festzulegen.“ (`text-sm text-text`). Darunter folgt nur „Ohne Namen“.
- Unbekanntes Projekt (`404` aus Fotoliste oder Auflistung): „Projekt nicht gefunden.“ wie auf `ProjectStatsPage`.

**Karten beider Gruppen:** Beide Gruppen nutzen dieselbe Zeilenkarte, damit lange Namen, Meldungen und das Namensformular auch bei 360 px Platz haben.
- Liste `ul grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3`.
- Karte `li flex items-start gap-3 rounded-lg border border-border bg-elevated p-2`.
- Links die Bildfläche mit sichtbaren 96 px (`size-24 shrink-0 rounded-md`), rechts eine Spalte `flex min-w-0 flex-1 flex-col` mit Text und Aktionen.
- Platzhalter: `Skeleton` `h-28 w-full rounded-lg`.
- Die `key`s sind stabil: `photo.id` in Personengruppen, `${photo_id}-${face_index}` in „Ohne Namen“.

### 2. Gruppe einer Person (`PersonPhotoGroup`)

**Kopf:**
- `h2` mit dem Namen, darunter die Anzahl (`text-sm text-text`): „{n} Fotos“, bei 1 „1 Foto“. Die Anzahl ist `total` minus die geladenen Einträge, die den Namen verloren haben. Sie steht erst, wenn die erste Seite da ist.
- Darunter eine dauerhaft vorhandene Statuszeile `p role="status" text-sm text-text`. Ohne Text hat sie keine Höhe.

**Karte je Foto:**
- **Bildfläche:** ein natives `button` mit dem Vorschaubild (`PhotoImage variant="thumbnail"`, `object-cover`), Name „Großansicht: {Pfad}“, `cursor-zoom-in`. Es öffnet die bestehende Großansicht (`CurationLightbox` über `useCurationLightbox`, Muster „Großansicht aus dem Raster“).
  - Wer einen falschen Namen sucht, muss das Foto größer sehen können, ohne die Seite zu verlassen. Ein Wechsel in die Detailansicht verwürfe die Suche in „Ohne Namen“, deren Zwischenspeicher `gcTime: 0` hat.
  - Es gibt eine Großansicht für die ganze Seite. Ihre Fotoliste sind die geladenen Fotos aller Personengruppen.
  - Die Fokus-Rückgabe geht an den Auslöser in **der** Gruppe, aus der geöffnet wurde. Ein Foto mit beiden Namen steht zweimal auf der Seite.
- **Textspalte** (`gap-1`):
  1. der Dateiname (nur der Basisname, `font-mono text-xs text-text-muted`, `min-w-6 truncate`);
  2. die Herkunft als ein Wort (`text-sm text-text`): „Erkannt“ oder „Von Hand zugeordnet“;
  3. nur wenn ein Gesicht gebunden ist, eine zweite Zeile (`text-sm text-text`): „Gesicht gezeigt“ bei `face: "shown"`, „Gesicht gewählt, nicht gelernt“ bei `face: "assigned"`. Bei `face: null` entfällt sie.

  Das bleiben Wörter: kein Badge, keine Farbe, kein Symbol (Muster „Zuordnung mit Herkunft“).
- **Aktion** (`Button variant="outline" size="sm"`, `self-start`, `mt-2`), abhängig von `face`:

| `face` | Beschriftung | `aria-label` | während der Anfrage |
|---|---|---|---|
| `"shown"` | „Gesicht zurücknehmen“ | „Gesicht zurücknehmen: {Dateiname}“ | „Wird zurückgenommen…“ |
| `"assigned"`, `null` | „Name entfernen“ | „Name entfernen: {Dateiname}“ | „Wird entfernt…“ |

  - Beide Aktionen sind dieselbe Schreiboperation (`applies: false`). Die Beschriftung sagt, was zusätzlich geschieht: Bei einem gezeigten Gesicht verschwindet mit dem Namen auch das Gelernte.
  - Keine Bestätigung. Beide Aktionen sind korrigierbar: Das Gesicht steht danach wieder in „Ohne Namen“ und lässt sich neu zuordnen.
  - Nie `destructive`: Nichts wird unwiederbringlich entfernt.
- **Busy je Karte:** Nur die Schaltfläche dieser Karte ist gesperrt und zeigt den Busy-Text. Alle anderen Karten bleiben bedienbar.

**Nach Erfolg:**
- Die Karte verlässt die Gruppe sofort, und die Anzahl sinkt um eins.
- Die Statuszeile meldet:
  - „{Name} auf {Dateiname} entfernt.“
  - „Gesicht auf {Dateiname} zurückgenommen. Es steht wieder unter „Ohne Namen“ und wirkt ab dem nächsten Klassifizierungslauf nicht mehr auf die Erkennung.“
- **Fokus** auf die Aktion der Karte, die jetzt an derselben Stelle steht; gibt es keine, auf die der vorherigen Karte, sonst auf das `h2` der Gruppe.
- War auf dem Foto ein Gesicht gebunden (gezeigt, gewählt oder erkannt mit Box), erscheint es in „Ohne Namen“ **an seiner Stelle** in der Folge (Foto-Id, dann Index). Die Mechanik ist `useUnnamedFaces.refreshPhoto` (Architektur). Da „Ohne Namen“ unter allen Personengruppen liegt, verschiebt das nichts oberhalb der Stelle, an der gearbeitet wird.

**Fehler einer Karte:**
- Ein `Alert` mit wörtlichem `detail` in der Textspalte unter der Schaltfläche, ohne „Erneut versuchen“. Die Schaltfläche ist die Wiederholung.
- Bei `404` (Person inzwischen entfernt) lädt die Personenliste neu, und die Gruppe verschwindet. Der Fokus geht auf das `h1`, die Statuszeile der Seite meldet nichts.

**Nachladen:**
- Die erste Seite umfasst 24 Fotos (Seitengröße der Übersicht, nicht `PHOTOS_PAGE_SIZE`). So stehen beide Personengruppen und der Anfang von „Ohne Namen“ in erreichbarer Nähe.
- Weitere Seiten lädt „Mehr laden“ (`outline size="sm"`, Busy während des Abrufs) unter der Liste, daneben `p aria-live="polite"` „{geladen} von {n} Fotos geladen“. Das ist das Muster der Ausschuss-Sichtung.
- Fehler beim Nachladen: `Alert` mit „Erneut versuchen“ an derselben Stelle.

**Zustände der Gruppe:**
- Laden: drei Kartenplatzhalter, `role="status"` „Fotos werden geladen…“ (`sr-only`).
- Fehler: `Alert` mit wörtlichem `detail` bzw. „Die Fotos konnten nicht geladen werden.“ und „Erneut versuchen“.
- Leer, auch nachdem die letzte Karte die Gruppe verlassen hat: „Kein Foto in diesem Projekt trägt diesen Namen.“ Ein ruhiger Satz ohne `Alert`.

### 3. Gruppe „Ohne Namen“ (`UnnamedFacesGroup`)

**Kopf:**
- `h2` „Ohne Namen“, darunter der strukturelle Hinweis (`text-sm text-text`): „Gesichter, die noch keiner Person zugeordnet sind – auch auf Fotos, die schon einen Namen tragen. Fremde Gesichter bleiben hier stehen: Über andere Menschen speichert PhotoSort nichts.“
  - Der erste Satz deckt zwei Fälle ab: Namen, die nur für das ganze Foto vergeben wurden, und Erkennungen aus Läufen vor der Migration, die bis zum nächsten Klassifizierungslauf ohne Box sind. Einen eigenen Übergangshinweis gibt es nicht, weil der Zustand von selbst endet und aus der Antwort nicht erkennbar ist.
  - Der zweite Satz beantwortet die naheliegende Frage nach „niemand von uns“, ohne eine Schaltfläche dafür anzubieten.
  - Keine Fehler-Optik: kein `Alert`, kein Symbol.

**Mitlaufende Statusleiste:**
- Direkt unter dem Hinweis steht `div sticky top-header z-10 flex flex-col gap-2 border-b border-separator bg-bg py-3`. Die Fläche ist deckend `bg-bg` ohne Deckkraft-Modifikator.
- Sie bleibt sichtbar, solange die Gruppe im Bild ist, denn die Karte, an der gehandelt wurde, verlässt die Liste. So bleiben zwei Dinge sichtbar: dass die Gruppe noch unvollständig ist und was die letzte Handlung bewirkt hat (AC Obergrenze „sichtbar gesagt“).
- Sie hat drei Zeilen:
  1. **Fortschritt:** ein `p` mit `id`, **nicht** live, damit jede Seite keine Ansage auslöst. Darunter `Progress`, per `aria-labelledby` an diese Zeile gebunden. Die Zustände:

| Zustand | Text | Balken |
|---|---|---|
| vor der ersten Seite | „Gesichter werden gesucht…“ | unbestimmt |
| Suche läuft | „Gesichter werden gesucht – {done} von {total} Fotos durchgesehen.“ | bestimmt (`value={done}`, `max={total}`) |
| unterbrochen | „Suche unterbrochen – {done} von {total} Fotos durchgesehen.“ | entfällt; stattdessen `Alert` mit wörtlichem `detail` bzw. „Die Suche nach Gesichtern ist unterbrochen.“ und „Erneut versuchen“, das an der Stelle fortsetzt. Bereits gefundene Gesichter bleiben stehen und zuordenbar. |
| abgeschlossen | „Suche abgeschlossen: {total} Fotos durchgesehen.“ (bei 1 „1 Foto“) | entfällt |
| Projekt ohne Fotos | „Das Projekt hat noch keine Fotos.“ | entfällt |

  2. **Nicht bereit**, sobald `not_ready_photo_ids` mindestens ein Foto enthielt, auch schon während der Suche: „{k} Fotos nicht bereit – noch ohne Vorschau oder nicht lesbar. Gesichter darauf fehlen hier.“ (bei 1 „1 Foto“).
     - `k` zählt eindeutige Ids.
     - Kein `Alert` und keine Wiederholung: Ein fehlendes Ergebnis ist kein Fehler, und die Auflistung kann einzelne Fotos nicht gezielt nachholen.
  3. **Ergebnis der letzten Handlung:** `p role="status" text-sm text-text`. Ohne Text hat die Zeile keine Höhe, eine neue Meldung ersetzt die alte:
     - „Gesicht als {Name} gezeigt.“ (`learned: true`);
     - „Als {Name} benannt, aber nicht gelernt: Für {Name} sind schon genug Gesichter gezeigt.“ (`learned: false`);
     - „{Name} ist festgelegt.“ (neue Person);
     - „An dieser Stelle ist auf dem Foto kein Gesicht mehr zu finden.“ (siehe Ablehnungen; die Karte ist dann ersetzt).
- Scheitert `refreshPhoto` (`refreshFailures`), steht in der Leiste je betroffenes Foto ein `Alert` mit „Erneut versuchen“ (`retryRefresh(photoId)`). Das Foto fehlt sonst still.
  - Nach einer Rücknahme aus einer Personengruppe (Dateiname bekannt): „Das Gesicht auf {Dateiname} konnte nicht wieder aufgenommen werden.“
  - Nach „kein Gesicht mehr zu finden“ beim Zuordnen (`fileName = null`, die Auflistung trägt bewusst keinen Pfad): „Die Gesichter eines Fotos konnten nicht neu gesucht werden.“

**Karte je Gesicht:**
- **Ausschnitt:** `FaceCropTile` in der statischen Ausprägung mit 96 px (`size-24 rounded-md object-cover`).
  - Er ist kein Bedienelement und hat keinen Auswahlzustand, also keine Akzentkante. Der Ausschnitt wird nicht gedämpft. `alt` ist „Gesicht ohne Namen“.
  - Der Ausschnitt existiert nur als Blob-URL und wird beim Entfernen der Karte und beim Verlassen der Seite freigegeben.
  - Lässt er sich nicht darstellen, bleibt eine Platzhalterfläche `bg-overlay` stehen (auf `--elevated` trennt die nächste Flächenstufe, nicht `--separator`), `alt` „Ausschnitt nicht verfügbar“. Zuordnen bleibt möglich, denn es adressiert Foto und Index.
- Gesichter werden einzeln in einer flachen Liste gezeigt. Sie werden weder nach Foto noch nach sonst etwas gruppiert, und die Reihenfolge ist die der Antwort (Foto-Id, dann Index).
- **Aktionsspalte** (`gap-3`):
  - **Je festgelegte Person eine Schaltfläche** (`Button variant="outline" size="sm"`) mit dem Namen als sichtbarer Beschriftung und dem `aria-label` „Zuordnen: {Name}“. Ein Druck ist die eine Handlung, die das Gesicht zuordnet.
    - In `flex flex-wrap gap-3`, in der Reihenfolge von `GET /persons`, auf jeder Karte gleich.
    - Alle Personen-Schaltflächen haben dieselbe Ausprägung. Keine ist hervorgehoben oder vorgewählt, denn das wäre ein Vorschlag.
    - **Heißer Pfad:** `min-h-11 sm:min-h-8`. Ein Fehlgriff benennt hier nicht nur, er bringt PhotoSort ein falsches Gesicht bei.
    - Dazu `h-auto whitespace-normal break-words`: Namen bis 40 Zeichen brechen um, statt gekürzt zu werden oder die Karte zu sprengen.
  - **Bei weniger als zwei Personen** zusätzlich „Neue Person…“ (`Button variant="ghost" size="sm"`, `aria-expanded`, `aria-controls`). Ohne festgelegte Person ist sie die einzige Schaltfläche der Karte.
  - **Namensformular** (aufgeklappt, in der Aktionsspalte, statt der Schaltflächenreihe):
    - `form flex flex-col gap-2` mit `label` „Name der neuen Person“ (`text-xs font-medium text-text-h`) und `Input` (`autoComplete="off"`).
    - Darunter `flex flex-wrap gap-3` mit „Festlegen“ (`default`, → `POST /persons`) und „Abbrechen“ (`ghost`).
    - „Festlegen“ ist deaktiviert, solange der getrimmte Name leer ist. Enter sendet ab. Weitere Namensregeln werden nicht gespiegelt, darüber entscheidet die `422`.
    - Beim Aufklappen geht der Fokus ins Feld. „Abbrechen“ oder Esc im Feld klappt zu, der Fokus geht zurück auf „Neue Person…“.
    - Es ist höchstens ein Formular auf der Seite offen. Das Öffnen in einer anderen Karte schließt das vorige samt Eingabe.
- **Busy je Karte:** Während einer Anfrage sind alle Schaltflächen **dieser** Karte gesperrt. Die gedrückte zeigt „Wird gespeichert…“. Andere Karten bleiben bedienbar: Mehrere Zuordnungen hintereinander warten nicht aufeinander.

**Nach erfolgreichem Zuordnen:**
- Die Karte verlässt die Liste sofort (`removeFace`), ohne dass die Gruppe neu lädt.
- Die Statusleiste meldet das Ergebnis, bei `learned: false` mit dem Satz zur Obergrenze.
- **Fokus** auf die erste Personen-Schaltfläche der Karte, die an derselben Stelle nachrückt; sonst auf die der vorherigen Karte, sonst auf das `h2` „Ohne Namen“. So bleibt die Stelle erhalten, und das nächste Gesicht ist sofort dran.
- Die Gruppe der Person lädt neu. Das Foto erscheint dort bzw. wechselt auf „Von Hand zugeordnet“ und „Gesicht gezeigt“ oder „Gesicht gewählt, nicht gelernt“.

**Nach erfolgreichem Festlegen:**
- Die Personenliste lädt neu. Die neue Gruppe erscheint oberhalb, und die Sprungleiste bekommt ihren Eintrag.
- Jede Karte bekommt die Schaltfläche der neuen Person. Bei zwei Personen entfällt „Neue Person…“ überall.
- Karte, Statusleiste und Fokus verhalten sich wie beim Zuordnen.

**Ablehnungen** (Karte und Gesicht bleiben stehen, außer wo anders genannt):
- `Alert` mit wörtlichem `detail` in der Aktionsspalte unter den Schaltflächen bzw. unter dem Formular, ohne „Erneut versuchen“. Der nächste Druck auf dieser Karte hebt ihn auf.
- „Dieses Gesicht gleicht der anderen Person …“, die beiden neuen Abweisungen (Gesicht dieser Person schon auf dem Foto, Gesicht der anderen Person auf diesem Foto), „kein verwertbares Merkmal“ und „gleichzeitig geändert“: nur die Meldung.
- „Es sind bereits zwei Personen festgelegt.“: Die Meldung erscheint, die Personenliste lädt neu, und das Formular verschwindet. Die Karte bekommt die Namens-Schaltflächen.
- Doppelter oder ungültiger Name (`409`/`422`): Die Meldung erscheint, am Feld `aria-invalid`, die Meldung ist per `aria-describedby` verknüpft, und die Eingabe bleibt.
- `404` Person: Die Meldung erscheint, und die Personenliste lädt neu.
- „An dieser Stelle ist auf dem Foto kein Gesicht mehr zu finden.“: Die Datei hat sich geändert. Die Gesichter dieses Fotos werden über `refreshPhoto` an ihrer Stelle ersetzt, und die Meldung steht in der Statusleiste, weil die Karte ersetzt ist. Der Fokus geht wie nach einem Zuordnen.
- Sonstige Fehler: „Das Gesicht konnte nicht gespeichert werden.“
- Vorschlag für die beiden neuen `detail`-Texte, ohne Namen: „Diese Person hat auf diesem Foto schon ein Gesicht.“ und „Dieses Gesicht gehört auf diesem Foto schon der anderen Person.“

**Liste leer oder im Aufbau:**
- Solange die Suche läuft, stehen am Listenende drei Kartenplatzhalter. Sie zeigen, dass noch etwas kommt, auch wenn bisher kein Gesicht gefunden ist.
- Abgeschlossen ohne Gesicht: „Kein Gesicht ohne Namen.“ (ruhiger Satz). Die Zeile „nicht bereit“ bleibt stehen, wenn Fotos fehlen.

### 4. Tastatur, Fokus, ARIA

- Es gibt nur native Elemente (`button`, `a`, `form`, `input`) und keine eigenen Tastenkürzel. Die Tab-Reihenfolge ist Kopf → Sprungleiste → je Personengruppe die Karten (Bildfläche, Aktion) und „Mehr laden“ → Statusleiste (nur ein etwaiges „Erneut versuchen“) → Karten von „Ohne Namen“.
- Verlässt eine Karte die Liste, wird der Fokus nie dem `body` überlassen, sondern nach den Regeln in 2 und 3 gesetzt.
- Status: je Personengruppe und in der Statusleiste genau ein `role="status"`. Die Fortschrittszeile ist nicht live. „{geladen} von {n} Fotos geladen“ ist `aria-live="polite"`. Fehler sind `Alert` (`role="alert"`).
- Die Überschriften der Gruppen sind `h2` mit `tabIndex={-1}`, Sprung- und Fokusziel. `h1` ist das Rückfallziel.
- Zugängliche Namen:
  - „Großansicht: {Pfad}“;
  - „Name entfernen: {Dateiname}“, „Gesicht zurücknehmen: {Dateiname}“;
  - „Zuordnen: {Name}“; die sichtbare Beschriftung ist im Namen enthalten (WCAG 2.5.3);
  - „Neue Person…“ mit `aria-expanded`/`aria-controls`.
- Die sticky Statusleiste ist keine Landmark und trägt keine Überschrift.

### 5. Schmale Breite und Stelle halten

- **360 px:**
  - Die Karten stehen einspaltig. Die Textspalte ist dann rund 200 px breit und trägt `Alert` und Namensformular.
  - Namens-Schaltflächen brechen um, die Sprungleiste und die Kopfzeile umbrechen.
  - Die Statusleiste spannt die Inhaltsbreite.
  - Kein horizontales Scrollen. `no-horizontal-scroll` bekommt die Route (Architektur).
- Ab `sm:` stehen die Karten zweispaltig, ab `xl:` dreispaltig.
- Zwischen aufgespannten Schaltflächen liegen überall mindestens 12 px (`gap-3`). Die Karte beschneidet nicht (`overflow-hidden` nur an der Bildfläche).
- **Stelle halten:** Die Seite verlässt sich auf das native Scroll Anchoring der Browser.
  - Es gibt kein `overflow-anchor: none`, keine Virtualisierung und keine Inline-Höhen an Vorfahren der Karten. Die `key`s sind stabil.
  - Wächst eine Personengruppe oberhalb (Neuladen nach dem Zuordnen), bleibt die Stelle in „Ohne Namen“ stehen. Die sticky Leiste ist von der Ankerwahl ausgenommen, das ist gewollt.
  - Die Unterstützung (Recherche 2026-09-28) umfasst Chrome/Edge, Firefox und Safari ab 27 (macOS, iOS/iPadOS). Auf iOS/iPadOS ≤ 26 springt die Seite in diesem Fall. Das nehmen wir in Kauf: Eine JS-Kompensation ausschließlich für Safari ≤ 26 ist ungeprüft auf Doppelausgleich unter Safari 27 und unterbräche dort laut Release-Notes das Momentum-Scrollen.

### 6. Detailansicht

**`PhotoPersonsSection`:**
- Das Zustandswort nennt zusätzlich ein gebundenes Gesicht: „Von Hand zugeordnet, Gesicht gezeigt“ (`face: "shown"`) bzw. „Von Hand zugeordnet, Gesicht gewählt – nicht gelernt“ (`face: "assigned"`). „Erkannt“, „Von Hand zugeordnet“ und „Nicht zugeordnet“ bleiben unverändert.
- Die Schaltfläche heißt bei `face: "shown"` „Gesicht zurücknehmen“ (`aria-label` „Gesicht zurücknehmen: {Name}“), sonst wie bisher „Entfernen“ bzw. „Ergänzen“. **Das ist der Hinweis**, dass Entfernen hier ein gezeigtes Gesicht zurücknimmt. Ein zusätzlicher Erklärsatz entfällt.
- Nach der Antwort steht die Zeile auf „Nicht zugeordnet“. Busy, Fehler und „das aktuelle Foto bleibt stehen“ gelten unverändert.

**`PersonFacePicker`:**
- Die Kacheln kommen aus `FaceCropTile` (wählbare Ausprägung, 64 px, unverändert).
- Die Statuszeile meldet bei `learned: false` „Als {Name} benannt, aber nicht gelernt: Für {Name} sind schon genug Gesichter gezeigt.“, sonst unverändert „Gesicht als {Name} gezeigt.“ bzw. „{Name} ist festgelegt.“ Die Wahl klappt in beiden Fällen zu.
- Die beiden neuen Abweisungen erscheinen als `Alert` über den Wahl-Schaltflächen, die Gesichtswahl bleibt stehen. Die Behandlung der Obergrenze als Ablehnung entfällt.

### 7. Seite `/persons`

- Der Leertext wird auf beide Wege erweitert: „Noch keine Person festgelegt. Eine Person legst du in der Personenübersicht eines Projekts fest oder in der Detailansicht eines Fotos im Abschnitt „Personen“ mit „Gesicht zeigen“.“
- Sonst ändert sich an der Seite nichts.

### 8. Was die Übersicht nie zeigt

- Keine Zahl, Ähnlichkeit oder Sicherheit zu einem Gesicht.
- Keine Anzahl der Gesichter ohne Namen. Fortschritt und „nicht bereit“ zählen **Fotos**.
- Kein Vorschlag: keine hervorgehobene, vorgewählte oder umsortierte Personen-Schaltfläche, kein „vielleicht {Name}“.
- Keine Gruppierung unbekannter Gesichter und keine Sortierung außer Foto-Id und Index.
- Keine Aktion „niemand von uns“ bzw. „ausblenden“.
- Keine Bewertungskennzeichen und keine Bewertungsleiste auf den Karten: Bewertungen sind hier nicht Gegenstand, und die Übersicht ändert keine. Die Kollisionsregel ist ohnehin gewahrt, weil nirgends `destructive` steht.
- Keine Box oder Markierung auf einem Foto.

### 9. Prüfstack und Sichtprüfung

- Die synthetischen Demo-Bilder enthalten keine Gesichter. „Ohne Namen“ zeigt dort nach der Suche „Kein Gesicht ohne Namen.“ und, je nach Demo-Stand, die Zeile „nicht bereit“.
  - Karte, Formular, Busy, Ablehnung und Obergrenzen-Satz von „Ohne Namen“ sind im Prüfstack **nicht sichtbar**. Sie werden über Komponententests mit base64-Ausschnitten abgedeckt.
  - Das ist eine benannte Grenze der Sichtprüfung.
- Sichtbar über `demo_state.py`: eine Personengruppe mit einer Karte „Gesicht gezeigt“ plus „Gesicht zurücknehmen“ und einer „Erkannt“-Karte mit „Name entfernen“.
- Sichtprüfung in 360 und 1280 px: Sprungleiste, Kartenraster, Statusleiste beim Scrollen, Großansicht und Fokusrückgabe, kein horizontales Scrollen.

### Design-System ergänzen (im Umsetzungs-PR, in `0004` und im Skill `design-system`)

1. **Gesichtsausschnitt-Kachel:** Neu ist eine statische Ausprägung mit 96 px (`size-24`) für Listen, in denen der Ausschnitt Inhalt und nicht Wahl ist. Sie hat keinen Auswahlzustand und keine Akzentkante. Ihre Platzhalterfläche auf `--elevated` ist `--overlay`. Die Quelle darf auch ein base64-Ausschnitt aus einer Listenantwort sein, immer als Blob-URL, und wird beim Entfernen der Karte freigegeben.
2. **Heißer Pfad, neue Fundstelle:** die Zuordnen-Schaltflächen in „Ohne Namen“ (`min-h-11 sm:min-h-8`). Begründung: Ein Fehlgriff lehrt ein falsches Gesicht. Die Freigabe kommt in die Liste des Vertragstests.
3. **Zeilenkarte mit Bildfläche:** Bild 96 px links, Text- und Aktionsspalte rechts, `grid-cols-1 sm:grid-cols-2 xl:grid-cols-3`. Sie ist für Arbeitslisten gedacht, deren Karten Meldungen oder ein Formular aufnehmen müssen.
4. **Erledigte Karte verlässt die Arbeitsliste:** Das ist das Gegenstück zu „Verworfene Kachel bleibt stehen“ und gilt, wo die Liste eine Warteschlange ist.
   - Die Karte fällt ohne Animation heraus.
   - Der Fokus geht auf die nachrückende Karte an derselben Stelle, sonst auf die vorige, sonst auf die Gruppenüberschrift.
   - Das Ergebnis meldet eine Statuszeile, die sichtbar bleibt.
5. **Mitlaufende Statusleiste einer Gruppe:** `sticky top-header`, deckend `bg-bg`, `border-b border-separator`. Sie trägt den Fortschritt einer Gruppe, die im Hintergrund zusammengestellt wird, dazu fehlende Einträge („nicht bereit“) und das Ergebnis der letzten Handlung. Die Fortschrittszeile ist nicht live, die Ergebniszeile ist `role="status"`.
6. **Zuordnung mit Herkunft:** Neu ist die Gesichtszeile „Gesicht gezeigt“ bzw. „Gesicht gewählt, nicht gelernt“. Auch sie ist Wort, nie Badge, Farbe oder Symbol. Eine Aktion, die zusätzlich Gelerntes entfernt, sagt das in ihrer Beschriftung („Gesicht zurücknehmen“) statt in einem Hinweissatz.
7. **Sprungleiste zu Gruppen:** `nav` mit `outline`-Links in `flex flex-wrap gap-3`. Ziel ist das `h2` mit `tabIndex={-1}` und `scroll-mt-header`, die Adresse bleibt unverändert.

## Security

**Einstufung:** Das Feature ist sicherheitsrelevant, aber kein Blocker. Neu sind:

- ein Zuwachs an der biometrischen Datenklasse: die Gesichtsbox des Gesichts, das auf einem Foto einer der beiden festgelegten Personen gehört, und die Kante Korrektur → Referenz, über die ein gezeigtes Gesicht einzeln zurücknehmbar wird;
- ein achter Endpunkt am `persons.router`, der je Aufruf bis zu 24 Modellläufe auslöst und Ausschnitte **auch unbekannter Gesichter** (Kinder, Verwandte, Fremde) base64-codiert in einer JSON-Antwort ausliefert;
- eine neue Wirkung am bestehenden `PUT /photos/{id}/persons/{person_id}`: `applies=false` löscht eine Referenz;
- ein neuer Wettlauf: Beide Nutzer arbeiten auf derselben Liste und können gleichzeitig Gesichter desselben Fotos zuordnen.

Es gibt kein neues Secret, keinen neuen Empfänger, keine neue Abhängigkeit, keinen externen Dienst und keine Änderung an Auth oder an der Sichtbarkeit zwischen den beiden Nutzern. Die projektweiten Aussagen stehen in `specs/architecture/0003-securitykonzept.md`: im Asset „Biometrische Referenzmerkmale“ und im Abschnitt „Personen auf Fotos erkennen“ samt Fortschreibung zu Spec 0551. Die Auflagen S1–S15 aus Spec 0292 gelten weiter, soweit unten nichts fortgeschrieben ist. S12 (Messkommando), S13 (Manifest) und S15 (Telemetrie) bleiben unberührt; `person_probe` gibt auch die neuen Spalten nie aus.

**Einordnung der Box.** Eine Box ist für sich kein biometrisches Merkmal. Jeder öffentliche Detektor findet sie im Bild in Millisekunden neu. Sensibel ist die Verbindung Box + Name, also ein beschrifteter Gesichtsausschnitt eines der beiden Nutzer. Gegenüber „Name je Foto“ ist das ein kleiner Zuwachs. Die harte Grenze bleibt: Über ein nicht festgelegtes Gesicht wird weder Box noch Index, Ausschnitt, Anzahl oder Merkmal gespeichert.

**Bedrohungen**

- **B1:** Gesichtsdaten fließen über den neuen Pfad ab. Ausschnitte unbekannter Gesichter bleiben im HTTP-Cache, im Service-Worker-Cache, in einem persistierten Query-Cache, in einer nicht freigegebenen Blob-URL oder im Log zurück, oder eine gespeicherte Box erscheint in einer Antwort.
- **B2:** Ausschnitt, Box oder Name erreichen einen Cloud-Anbieter. Das ist auch mit Einwilligung ausgeschlossen.
- **B3:** Dritte werden wiedererkennbar oder gruppierbar: Die Auflistung speichert etwas über unbekannte Gesichter, bildet ein Merkmal, oder Reihenfolge bzw. Vorschlag verraten eine Ähnlichkeit.
- **B4:** Eine falsche Referenz entsteht, etwa weil beide Nutzer dasselbe Gesicht gleichzeitig den beiden Personen zuordnen, weil eine Dateiänderung die Gesichtsnummer verschiebt (TOCTOU), durch ein gestohlenes JWT oder durch eine Box, die der Client liefert.
- **B5:** Die Rücknahme bleibt unvollständig. Eine Referenz verwaist, weil eine gleichzeitige Zuordnung desselben Paars die Korrektur überschreibt, ein Zwischenspeicher hält den alten Schwerpunkt, oder nach einer Projekt- bzw. Fotolöschung ist die Referenz nicht mehr einzeln erreichbar.
- **B6:** Die Auflistung lastet API und Datenbank aus. Der Modell-Thread ist für die Detailansicht blockiert, oder wartende Anfragen halten Datenbankverbindungen, bis der Pool leer ist.
- **B7:** Ein Name oder Dateiname manipuliert Anzeige oder Navigation über neue Stellen: Sprungleiste (`href="#…"`), Gruppen-`id`, `aria-label`.
- **B8:** Echte Gesichter gelangen in öffentliche Artefakte: Test-Fixtures mit Ausschnitten, Demo-Bestand, Playwright-Traces.

**Auflagen.** **Muss** ist eine Abnahmebedingung. **Soll** ist empfohlen; eine Abweichung wird im PR begründet.

- **S1 – Muss – Auth am neuen Endpunkt.**
  - `GET /projects/{project_id}/unnamed-faces` liegt im `persons.router` mit `dependencies=[Depends(get_current_user)]`.
  - Der Vollständigkeitstest in `test_auth_guard.py` erfasst ihn über die Router-Iteration. Sein Kommentar zählt acht Endpunkte.
  - Nachweis: der Vollständigkeitstest und ein pfadbenannter `401`-Fall für den neuen Endpunkt.
- **S2 – Muss – Eingaben, Projektbindung, Box nur vom Server.**
  - Grenzen: `project_id` `ge=1, le=MAX_ID`; `after_id` `ge=0, le=MAX_ID`; `max_photos` `ge=1, le=UNNAMED_PAGE_MAX_PHOTOS`. Ein Wert außerhalb ergibt `422`, nie `500`.
  - Ein unbekanntes Projekt ergibt `404`, bevor eine Variante gelesen oder das Modell gerufen wird.
  - Eine Seite enthält ausschließlich Fotos mit `Photo.project_id == project_id`. Das gilt ebenso für `not_ready_photo_ids`, `photos_done` und `photos_total`.
  - Die Eingabeschemata der Schreibwege bleiben `{name, photo_id, face_index}`, `{photo_id, face_index}` und `{applies}`, jeweils mit `extra="forbid"`.
  - **Die Box entsteht nur serverseitig:** beim Zuordnen aus demselben Detektionslauf wie das Merkmal (`_embedding_at`), in der Phase `persons` aus dem einen Kandidatengesicht. Kein Weg nimmt Box, Ausschnitt oder Merkmal vom Client an.
  - Vor dem Schreiben wird die Box in Einschlussform geprüft (endlich, `0 <= x, y <= 1`, `0 < width, height <= 1`). Ein NaN fällt damit auf „ungültig“. Die Prüfeinschränkungen sind die zweite Linie. Eine ungültige Box endet ohne Schreiben mit `409`, nie mit `500`.
  - `user_id` kommt weiter nur aus `current_user.id` und bleibt Auditfeld. `FaceAssignmentOut`, `PhotoPersonOut` und `UnnamedFacesPageOut` tragen keine `user_id`.
  - Nachweis:
    - Grenzfälle je Parameter;
    - eine Seite enthält kein Foto eines anderen Projekts, auch wenn `after_id` direkt vor einem fremden Foto steht;
    - ein zusätzliches Feld `face_box_x` bzw. `box` im Body ergibt `422`;
    - eine NaN- bzw. Inf-Box aus dem Fake-Analyzer ergibt `409`, ohne dass etwas geschrieben wird.
- **S3 – Muss – Nichts über Unbekannte (fortgeschrieben aus 0292 S5).**
  - Die Auflistung schreibt nichts: kein `INSERT`/`UPDATE`/`DELETE`, keine Datei, kein Prozess-Zwischenspeicher. Es gibt kein Memo der Detektion und keine modulweite Ablage von Ausschnitten oder Boxen über den Aufruf hinaus.
  - `embed` läuft in der Auflistung nie. Die Reihenfolge ist (Foto-Id, Gesichtsindex) und nichts sonst. Kein Feld trägt Wert, Ähnlichkeit, Sicherheit, Box oder Vorschlag.
  - Eine Box wird nur für das Gesicht einer festgelegten Person geschrieben: an der Korrektur für das ausdrücklich gewählte Gesicht, an der Erkennung für das eine Kandidatengesicht der erkannten Person. Kein Pfad schreibt eine Box für ein anderes Gesicht des Fotos.
  - Spaltensätze und Antwortschemata sind auf Gleichheit festgehalten, wie in der Architektur unter „Invarianten / Spaltensätze“. `person_references` bleibt ohne Foto- und ohne Projektspalte.
  - Gespeicherte Boxen verlassen die Datenbank über keine Antwort: `PhotoPersonOut.face` ist ein Aufzählungswert, `UnnamedFaceOut` ist `{photo_id, face_index, crop_jpeg}`. Die einzige Box nach außen bleibt die frisch detektierte aus `GET /photos/{id}/faces`.
  - Nachweis:
    - Die Zeilenzahl aller Tabellen ist vor und nach einer Auflistung über mehrere Seiten gleich.
    - Der Fake-Analyzer zählt null `embed`-Aufrufe.
    - Eine Zuordnung bzw. ein Lauf auf einem Foto mit einem Gesicht der Person und zwei unbekannten Gesichtern hinterlässt genau eine Box.
    - Die Feldmengen der Schemata werden auf Gleichheit geprüft.
- **S4 – Muss – Nur lokal (0292 S6, bestätigt).**
  - `photosort.api.persons` bleibt in `PERSON_MODULES` und `DATABASE_BOUND_PERSON_MODULES` des Import-Graph-Wächters. `_unnamed_on_photo` liegt dort bzw. in `face_analysis.py`, und kein Cloud-Modul erreicht es.
  - Ausschnitte gehen ausschließlich in die Antwort an den Browser. Das Frontend schickt keinen Ausschnitt und keine Box zurück, denn eine Zuordnung adressiert (Foto, Index).
  - Nachweis: der bestehende Import-Graph-Wächter und die Schemata aus S2.
- **S5 – Muss – Last der Auflistung (fortgeschrieben aus 0292 S7).**
  - Je Foto gibt es genau einen Auftrag auf dem bestehenden Ein-Thread-Executor, und er wird abgewartet, bevor der nächste gestellt wird. Eine Anfrage hat nie mehr als einen Auftrag in der Warteschlange (kein `gather` über die Seite). Nur so reiht sich eine Zuordnung oder ein `GET /faces` nach höchstens einem Foto ein.
  - Die Seitengrenzen gelten serverseitig:
    - höchstens `UNNAMED_PAGE_MAX_PHOTOS = 24` Fotos;
    - Schluss nach dem Foto, mit dem `UNNAMED_PAGE_MAX_FACES = 48` erreicht ist;
    - je Foto höchstens `MAX_FACES_PER_PHOTO = 20` Gesichter.

    Eine Seite trägt damit höchstens 67 Ausschnitte mit je höchstens 160 px.
  - Gelesen wird nur die `display`-Variante über `thumbnails.variant_path` aus dem Datensatz. Nie ein Pfad aus der Anfrage, nie das Original, nie OpenCloud. Fehlt die Variante, steht das Foto in `not_ready_photo_ids`, und das Modell wird nicht gerufen.
  - Der Client lädt die Seiten streng nacheinander: höchstens eine Auflistungsanfrage gleichzeitig je geöffneter Seite, dazu nur die Einzelabfragen von `refreshPhoto` (`max_photos = 1`). Beim Verlassen der Seite und nach einem Fehler stellt er keine weitere Seitenanfrage, auch nicht bei Fokus oder Reconnect.
  - Es gibt kein eigenes Rate-Limit. Ein gestohlenes JWT gewinnt damit nichts Neues, wie in 0292 S7.
  - Die Anfrage hält keine Datenbankverbindung, während sie auf den Executor wartet. Je Foto öffnet sie eine kurze Lesesitzung aus `get_session_factory` (`api/deps.py`), liest Variantenpfad und zugeordnete Boxen, schließt die Sitzung und stellt erst dann den Executor-Auftrag. Sonst belegte jede gleichzeitig wartende Auflistung eine Verbindung des Pools (Vorgabe 5 + 10 Überlauf) für bis zu 24 Modellläufe, und alle anderen Endpunkte warteten mit.
  - Zwischen zwei Fotos prüft der Endpunkt `await request.is_disconnected()` und bricht bei getrennter Verbindung ab. Eine verlassene Seite belegt den Modell-Thread dann noch höchstens ein Foto lang statt bis zu 24.
  - Nachweis:
    - Mit einem blockierenden Fake kommt der Auftrag einer zweiten Anfrage zwischen zwei Detektionen einer laufenden Auflistung an die Reihe.
    - Eine fehlende Variante ergibt null Aufrufe des Fake-Analyzers.
    - Seitengrenzen: Die Seite endet nach 24 Fotos, und nach 48 Gesichtern endet sie am Ende des laufenden Fotos.
    - vitest: Nach einem Fehler oder dem Aushängen folgt keine weitere Seitenanfrage.
- **S6 – Muss – Ausschnitte in der Listenantwort (fortgeschrieben aus 0292 S8).**
  - `crop_jpeg` ist base64 eines aus den Bildpunkten neu codierten JPEG (Pillow, ohne `exif`), höchstens 160 px, aus dem geklemmten Ausschnitt.
  - Die Antwort trägt `Cache-Control: no-store` und `X-Content-Type-Options: nosniff`, auch als `200` mit leerer Liste. Sie hat kein `ETag`.
  - Im Frontend gibt es den Ausschnitt nur als Blob-URL mit festem Typ `image/jpeg`, nie als `data:`-URL im DOM. Freigegeben wird die URL beim Entfernen der Karte (`removeFace`), beim Ersetzen über `refreshPhoto`, beim Aushängen der Kachel und beim Verlassen der Seite.
  - Die base64-Zeichenketten liegen nur im Query-Cache `['unnamed-faces', projectId]` mit `gcTime: 0`. Sie stehen nie in `localStorage`, `sessionStorage`, IndexedDB, im Verlaufszustand oder in einem persistierten Query-Cache.
  - Der Service Worker bekommt kein `runtimeCaching` für API-Pfade; heute hält er nur statische Dateien vor. Ein Workbox-Cache hielte die Ausschnitte unbekannter Gesichter unabhängig von `no-store` im Cache Storage des Browserprofils.
  - Kein Ausschnitt, kein base64 und kein Antwortkörper erscheint in `console.*` oder in einem Fehlertext.
  - Nachweis:
    - die Kopfzeilen im API-Test;
    - vitest: `revokeObjectURL` für die URL eines zugeordneten und eines über `refreshPhoto` ersetzten Gesichts sowie für alle URLs beim Aushängen der Seite;
    - der Service-Worker-Stand ist ein Review-Punkt ohne Laufzeitprobe.
- **S7 – Muss – Personen-Schreibwege laufen nacheinander (neu).**
  - **Anlass:** Die Prüfungen „diese Person hat hier schon ein Gesicht“, „das Gesicht gehört der anderen Person“ und die Obergrenze lesen erst und schreiben dann. Ohne Serialisierung folgen drei Fehlerfälle:
    - (a) Zwei Zuordnungen für dasselbe Paar (Foto, Person) laufen gleichzeitig. Das Upsert überschreibt Box und `reference_id` der ersten, und deren Referenz verwaist. Sie wirkt weiter auf die Erkennung und ist nur noch mit der Person löschbar. Das bricht die Rücknahme-Zusage.
    - (b) Beide Nutzer ordnen dasselbe Gesicht gleichzeitig den beiden Personen zu. Aus einem Gesicht entstehen zwei Referenzen, und eine davon ist falsch.
    - (c) Zwei gleichzeitige Zuordnungen an der Obergrenze legen eine Referenz über `MAX_REFERENCES_PER_PERSON` hinaus an.
  - **Tragend ist die Prozesssperre `_person_write_lock`** (`asyncio.Lock` in `api/persons.py`, ADR 0127 Punkt 2). Alle vier schreibenden Endpunkte laufen darunter: `POST /persons`, `POST /persons/{id}/references`, `PUT /photos/{id}/persons/{person_id}` und `DELETE /persons/{id}`. Unter der Sperre laufen alle Prüfungen, das Schreiben und der Commit. `detect` und `embed` laufen nie darunter, und der Modellaufruf wartet nie auf die Sperre.
  - **Voraussetzung ist genau ein API-Prozess.** Der Docstring der Sperre und die Ankerzeile in 0003 nennen diese Voraussetzung. Kommt ein `--workers` in den Backend-Start oder `WEB_CONCURRENCY` in dessen Umgebung (uvicorn liest die Variable), braucht es vorher eine Datenbanksperre (ADR 0127).
  - **Zweite Linie, bedingtes Setzen:** Die Box an einer bestehenden Korrektur wird mit `UPDATE … WHERE photo_id = … AND person_id = … AND face_box_x IS NULL` gesetzt. Trifft es keine Zeile, folgt `FaceAlreadyAssignedOnPhoto` (`409`), und der Rollback nimmt die neue Referenz mit zurück. Beim Neuanlegen trägt `UNIQUE(photo_id, person_id)`: `IntegrityError` wird `409`.
  - „Gesicht der anderen Person“ prüft gegen `assigned_face_boxes` und bezieht damit auch deren erkannte Box ein.
  - Die Rücknahme liest `reference_id` unter der Sperre und löscht genau diese Referenz.
  - Nachweis, unter SQLite deterministisch:
    - Ein zweiter Aufruf, der sich zwischen Modellaufruf und Schreiben eines ersten einschiebt, ergibt einmal `201`, einmal `409` und genau eine Box.
    - Bei 19 Referenzen ergeben zwei gleichzeitige Zuordnungen 20 Referenzen, und eine davon antwortet `learned: false`.
    - Das bedingte Setzen allein, bei umgangener Vorprüfung auf eine Korrektur mit Box, ergibt `409`, und die Zahl der Referenzen bleibt gleich.
- **S8 – Muss – Rücknahme und Löschen (fortgeschrieben aus 0292 S10).**
  - `applies=false` auf einem Paar mit Box leert Box und `reference_id` und löscht die verknüpfte Referenz in **derselben** Transaktion. Übersicht und Detailansicht nutzen dafür denselben Endpunkt.
  - Jede ab dieser Story entstandene Referenz hängt an genau einer Korrektur. Die Kante endet nur durch Rücknahme, Projekt- oder Fotolöschung oder Modellwechsel.
  - `fk_photo_person_corrections_reference_id` bleibt ohne `ON DELETE`-Aktion. Wer eine Referenz löscht, ohne die Kante zu leeren, scheitert dadurch laut statt still.
  - Schwerpunkte werden weiter je Lauf bzw. Anfrage frisch gebildet, ohne Zwischenspeicher. Die Rücknahme wirkt ab dem nächsten Lauf; ein laufender Lauf rechnet mit seinem Schwerpunkt zu Ende.
  - `delete_person` bleibt eine Transaktion in der Reihenfolge Korrekturen, Erkennungen, Referenzen, Person.
  - Nachweis:
    - Nach der Rücknahme existiert die Referenz nicht mehr, und die anderen sind unberührt.
    - `current_centroids` gleicht danach dem Schwerpunkt ohne sie.
    - Zehnmal Zuordnen und Zurücknehmen desselben Gesichts hinterlässt keine zusätzliche Referenz.
    - Eine Referenz bei gesetzter Kante direkt zu löschen, scheitert am Fremdschlüssel.
- **S9 – Muss – Log-Hygiene (fortgeschrieben aus 0292 S11).**
  - Die Auflistung loggt keine Box, keinen Index je Foto, keine Gesichterzahl je Foto, keinen Ausschnitt und kein base64. Ausnahmen je Foto erscheinen nur als `type(exc).__name__` mit `photo_id`.
  - Die beiden neuen `detail`-Texte nennen keinen Namen.
  - Nachweis: eine Auflistung mit einem Fake, der einprägsame Boxwerte liefert und bei einem Foto wirft. `caplog` enthält keinen Boxwert, keinen base64-JPEG-Anfang (`/9j/`) und keinen Dateipfad.
- **S10 – Muss – Namen und Dateinamen an den neuen Anzeigestellen (fortgeschrieben aus 0292 S4).**
  - `id` und `href="#…"` von Sprungleiste und Gruppen werden aus der Personen-Id gebildet (etwa `person-{id}`), nie aus dem Namen. „Ohne Namen“ hat eine feste `id`.
  - Namen und Dateinamen erscheinen nur als React-Textknoten oder über `aria-label`/`alt` als React-Prop. Sie stehen nie in `href`, `src`, `style` oder `dangerouslySetInnerHTML`, nie als `key` und nie in URL oder Hash.
  - Der Verlaufszustand der Großansicht trägt weiter nur die Foto-Id (Spec 0531 S2). Der Auslöserschlüssel `${personId}:${photoId}` lebt nur im Ref.
  - Nachweis: vitest mit einem Namen, der `#`, `"` und Leerzeichen enthält. Das `href` ist `#person-{id}`, und die Adresse bleibt nach dem Sprung unverändert.
- **S11 – Muss – Keine echten Gesichter (fortgeschrieben aus 0292 S14).**
  - `demo_state.py` legt Box und Referenz synthetisch an: eine erfundene Box, ein Einheitsvektor, der nie aus einem Gesicht stammt, und erfundene Namen.
  - Komponententests mit base64-Ausschnitten verwenden erzeugte Bilder ohne Gesicht, etwa ein einfarbiges JPEG. Kein Foto einer realen Person, auch keines aus einem öffentlichen Datensatz.
  - Für die Sichtprüfung kommt kein Fixture mit Gesicht hinzu. „Ohne Namen“ bleibt im Prüfstack leer, und die Playwright-Traces bleiben damit unbedenklich.
- **S12 – Muss – Sicherheitskonzept im Umsetzungs-PR nachziehen.**
  - Die Ankerzeilen in 0003 „Für ein nicht festgelegtes Gesicht gibt es keinen Speicherort“, „Die Modellaufrufe des API-Prozesses …“ und „Die Löschung einer Person …“ werden umgestellt. Sie nennen danach die neuen Spaltensätze, `assign_face`, die Rücknahme in `set_correction`, den neuen Endpunkt mit `no-store` und die zugehörigen Tests.
  - Für S7 kommt eine Ankerzeile hinzu.
  - Die neue Ankerzeile für S7 nennt die Voraussetzung „genau ein API-Prozess“.
  - Die Fortschreibung zu Spec 0551 im Abschnitt „Personen auf Fotos erkennen“ wechselt von „Vorausschau“ auf „umgesetzt“.

**Geprüft und ohne Befund**

- **Sichtbarkeit zwischen den Nutzern:** unverändert gemeinsam (0292 S2). `UnnamedFacesPageOut` und `FaceAssignmentOut` tragen kein nutzerabhängiges Feld. Die Personengruppen nutzen den bestehenden Lesepfad `GET /projects/{id}/photos?person_id=…`, dessen Cache-Schlüssel-Auflage aus 0003 unverändert gilt.
- **`learned: false` statt `409`:** Über der Obergrenze entsteht keine Referenz. Neu ist nur die Korrektur mit Box, die ohnehin für beide Nutzer gilt.
- **Übergang:** Erkennungen ohne Box stehen bis zum nächsten Lauf in „Ohne Namen“. Dabei wird nichts gespeichert. Ordnet ein Nutzer ein solches Gesicht zu, ist das eine ausdrückliche Handlung und kein automatisches Lernen.
- **Prüfstack ohne Gesichter:** Sicherheitlich ist das richtig (S11). Der gefüllte Zustand ist über Tests mit dem Fake-Analyzer abgedeckt.
- **Migration:** Sie füllt keine Boxen nach. `downgrade` entfernt Boxen und Kante, und die Referenzen bleiben stehen, wie bei einer Projektlöschung.
- Kein neuer XSS-Sink außer den unter S10 genannten Stellen, kein neues Secret, keine neue Abhängigkeit.

**Restrisiken (zur Annahme mit der Spec; im Konzept vermerkt)**

- **R1 – Gesichtsnummer nach Dateiänderung (ADR 0127):** Erzeugt ein Scan die Display-Variante zwischen Auflistung und Klick neu, lernt PhotoSort ein anderes Gesicht desselben Fotos. Das wird in der Personengruppe als „Gesicht gezeigt“ sichtbar und lässt sich zurücknehmen. Gleicht das Gesicht der anderen Person, weist die bestehende Prüfung es ab.
- **R2 – Mehr als ein API-Prozess oder gleichzeitiges Schreiben des Workers:** Die Prozesssperre aus S7 trägt nur bei genau einem API-Prozess (siehe S7). Die Phase `persons` des Workers schreibt ihre Erkennungsbox nicht unter dieser Sperre. Überschneidet sie sich mit einer Zuordnung desselben Gesichts zur anderen Person, kann ein Gesicht auf einem Foto als erkannt für B und als zugeordnet für A gelten. Das ist sichtbar und korrigierbar, und dabei entsteht keine zusätzliche Referenz aus der Erkennung.
- **R3 – Referenzen ohne Korrektur sind nur mit der Person löschbar.** Das betrifft Referenzen, die vor dieser Story gezeigt wurden, und solche, deren Projekt oder Foto gelöscht wurde. Darunter kann ein versehentlich gezeigtes fremdes Gesicht sein, dessen Projekt vor der Rücknahme gelöscht wurde. Es wirkt dann weiter auf die Erkennung, bis die Person entfernt und neu angelernt wird.
- **R4 – Box eines fremden Gesichts an einer Fehlerkennung:** „Name entfernen“ überstimmt die Zuordnung, aber die Box an der Erkennungszeile bleibt stehen, bis ein Lauf die Zeile ersetzt oder die Person entfernt wird. Gespeichert sind nur Koordinaten, kein Merkmal, und sie sind aus dem Bild ohnehin ableitbar.
- **R5 – Ausschnitte im Browser-Speicher:** Solange die Übersicht offen ist, liegen die Ausschnitte aller bisher gefundenen unbekannten Gesichter des Projekts im Arbeitsspeicher des Browsers, in großen Projekten viele tausend. Sie werden nicht dauerhaft abgelegt und sind beim Verlassen weg. Wer an einem offenen, entsperrten Gerät sitzt, sieht sie, so wie die Fotos selbst.
- **R6 – Gestohlenes JWT:** Es kann den Modell-Thread mit Auflistungen belegen sowie Gesichter zuordnen und zurücknehmen. Das ist keine neue Fähigkeit (0292).

## Teststrategie

Grundlage ist das Testkonzept 0002 mit den Sektionen „Biometrische Merkmale ohne echtes Modell …“ (0292) und „Nebenläufige Schreibwege unter einer prozessweiten Sperre, eine Hintergrundsuche mit Antworten im Flug …“ (neu mit dieser Spec). Alles aus der Teststrategie von 0292 gilt weiter: Modellsperre, Fake-Analyzer, dyadische Schwellen, Zwilling plus Sentinel, Import-Graph und Fremdschlüssel-Durchsetzung. Die Pflichtfälle unten sind namentlich verbindlich und werden nie aus der Coverage-Zahl abgeleitet.

### Fake-Analyzer (`backend/tests/face_fakes.py`), Erweiterung

- `boxes_by_color`: Je Vollfarbe lassen sich die Boxen der Gesichter setzen. Die feste Box je Index bleibt die Vorgabe. Gebraucht wird das für Überdeckungsgrenzen, für eine geänderte Datei (Box verschoben, Gesicht weg) und für eine NaN-Detektorzeile.
- `BOX_SENTINEL`: Eine einprägsame Koordinate (z. B. `x = 0.0987654321`), nach der wie nach `SENTINEL` gesucht wird.
- Die Aufrufzählung (`calls`) unterscheidet `detect` und `embed` schon heute. Neu ist, dass sie für jede Auflistung ausgewertet wird.
- `on_detect` bleibt der Haken für eine zweite Verbindung während eines Modellaufrufs (Muster `test_a_person_deleted_mid_run…`).
- Ein zweiter Haken `before_detect_returns` hält den Modell-Thread an einem `threading.Event` fest. Damit wird die Reihenfolge der Executor-Aufträge beobachtbar.

### Ebene je Kriterium

| Kriterium | Ebene | Ort |
|---|---|---|
| Übersicht je Projekt, auch Ausschuss | API + vitest | `test_api_unnamed_faces.py`, `test_api_persons.py`, `ProjectPersonsPage.test.tsx`, `ProjectNav.test.tsx` |
| Gruppen je Person, „Ohne Namen“ | vitest | `ProjectPersonsPage.test.tsx` |
| Keine Gruppierung Unbekannter | API (Zählung `embed`) + vitest | `test_api_unnamed_faces.py`, `UnnamedFacesGroup.test.tsx` |
| Beide Nutzer dieselbe Übersicht | API | `test_api_unnamed_faces.py`, `test_api_persons.py` |
| Gruppe = Personeneinschränkung, Anzahl, Herkunft, Gesicht | API + vitest | `test_api_persons.py`, `test_persons.py`, `usePersonGroupQuery.test.tsx`, `PersonPhotoGroup.test.tsx` |
| Name entfernen aus der Gruppe | Integration Worker + API + vitest | `test_worker_persons.py`, `test_api_persons.py`, `PersonPhotoGroup.test.tsx` |
| Menge „Ohne Namen“ | Unit + API | `test_face_analysis.py`, `test_persons.py`, `test_api_unnamed_faces.py` |
| Zuordnen, gilt global | API + Worker | `test_api_persons.py`, `test_worker_persons.py` |
| Verlässt sofort, kehrt nicht zurück | API + Worker + vitest | `test_api_unnamed_faces.py`, `test_worker_persons.py`, `useUnnamedFaces.test.tsx` |
| Nacheinander, Stelle halten | vitest | `UnnamedFacesGroup.test.tsx`, `useUnnamedFaces.test.tsx` |
| Neue Person aus „Ohne Namen“ | API + vitest | `test_api_persons.py`, `UnnamedFacesGroup.test.tsx` |
| Obergrenze | Integration + API + vitest | `test_persons.py`, `test_api_persons.py`, `UnnamedFacesGroup.test.tsx`, `PhotoPersonsSection.test.tsx` |
| Abweisungen, auch gleichzeitig | Integration + API (Nebenläufigkeit) + vitest | `test_persons.py`, `test_api_persons.py`, `UnnamedFacesGroup.test.tsx` |
| Zurücknehmen | Integration + API + Worker + vitest | `test_persons.py`, `test_api_persons.py`, `test_worker_persons.py`, `PersonPhotoGroup.test.tsx` |
| Früher gezeigte Gesichter | Integration | `test_persons.py` |
| Nichts über Unbekannte | API (Schnappschuss, Sentinel, Verzeichnis, `caplog`) + Schema | `test_api_unnamed_faces.py`, `test_migration_gesichtsbezug_personen.py` |
| Nur lokal | Struktur | `test_persons_import_graph.py` |
| Keine Zahl, kein Vorschlag, Reihenfolge | API-Schema + vitest | `test_api_unnamed_faces.py`, `UnnamedFacesGroup.test.tsx` |
| Zusammenspiel | API + vitest | `test_api_persons.py`, `useFaceAssignment.test.tsx` |
| Keine Wirkung auf Bewertung usw. | API (Zwilling) | `test_api_persons.py` |
| Große Projekte | API (Executor) + vitest | `test_api_unnamed_faces.py`, `useUnnamedFaces.test.tsx`, `UnnamedFacesGroup.test.tsx` |
| Datenmodell | Migration | `test_migration_gesichtsbezug_personen.py`, `test_postgres_ddl_compatibility.py` |

### Backend – Unit

**`test_face_analysis.py`**

- **`box_overlap`** mit dyadischen Boxen, damit die IoU binär exakt ist:
  - gleiche Box ergibt 1, disjunkte ergeben 0, und die Funktion ist symmetrisch;
  - eine Lage mit IoU genau `0.5` gilt als gleich, eine knapp darunter (z. B. `0.5 - 2**-10`) nicht;
  - NaN in einer der beiden Boxen gilt als „nicht gleich“ (Einschlussform, Muster S9).
- **`unassigned_faces`:**
  - Eine gespeicherte Box überdeckt zwei Gesichter über der Schwelle. Nur das mit der größten Überdeckung fällt weg, das zweite bleibt.
  - Zwei gespeicherte Boxen auf verschiedenen Gesichtern lassen beide wegfallen.
  - Eine Box ohne passendes Gesicht (geänderte Datei) nimmt nichts weg.
  - Ohne gespeicherte Box bleiben alle Indizes.
  - Die Ausgabe ist aufsteigend nach Index und damit von der Reihenfolge der gespeicherten Boxen unabhängig (Permutationsfall).
- **Endlichkeit der Detektorzeile:** Eine Zeile mit NaN oder Inf an irgendeinem der 15 Werte ergibt kein Gesicht. Sie wird vor `is_usable` verworfen und zählt nicht auf `MAX_FACES_PER_PHOTO`. Lage: 21 Zeilen, davon eine mit NaN in der Box, ergeben 20 Gesichter.
- **Adapter:** Die Box, die `detect` liefert, ist dieselbe Box, die `face_crop_jpeg` ausschneidet. Das wird mit einer Attrappe geprüft, nicht mit dem echten Modell.

**`test_person_matching.py`**

- `decide_assignments` liefert `{person_id: face_index}`. Alle 1:1-Fälle aus 0292 werden auf den Index umgestellt, keiner fällt weg.
- Der Index ist der des Kandidatengesichts, nicht der des ersten Gesichts. Lage: Kandidat an Index 2 von 3.
- Vertauschte Reihenfolge der Gesichter ergibt denselben Index für dasselbe Gesicht, gemessen an der Box.

### Backend – Integration

**Personen (`test_persons.py`)**

- **`assigned_face_boxes`**, die Regel aus ADR 0127 Punkt 3 als Wahrheitstabelle je Paar (Foto, Person): Korrektur {keine, `applies=false`, `applies=true` ohne Box, `applies=true` mit Box} × Erkennung {keine, ohne Box, mit Box}. Erwartet werden genau die vier Regeln.
  - Pflichtfall 1: Korrektur `applies=false` plus Erkennung mit Box ergibt kein Gesicht.
  - Pflichtfall 2: Korrektur mit Box plus Erkennung mit **anderer** Box ergibt die Box der Korrektur.
  - Zwei Personen auf einem Foto ergeben zwei Boxen.
  - Fotos außerhalb der übergebenen Ids erscheinen nicht.
- **Quelltext-Wächter:** Die Box-Spalten beider Tabellen werden im Lesepfad an genau einer Stelle gelesen (`assigned_face_boxes`), mit `effective_person_assignments` als zweiter, benannter Ausnahme für `face`. Muster: „genau eine Stelle nennt die Korrekturspalte“ aus 0292.
- **`effective_person_assignments`, Spalte `face`:** Matrix wie in 0292, erweitert um Box und Referenz. Erwartet werden `shown` (Box + Referenz), `assigned` (Box ohne Referenz) und `null` (sonst). Im Erkennungszweig ist `face` immer `null`, auch bei einer Erkennung mit Box.
- **`assign_face`, Reihenfolge der Prüfungen:** Je Stufe gibt es einen Fall, in dem die vorige Stufe bestanden ist und genau diese scheitert. Dazu kommt je Paar benachbarter Stufen ein Fall, in dem **beide** scheitern und die frühere gewinnt:
  - Person fehlt vor „schon eine Korrektur-Box dieser Person“;
  - „gleicht der anderen Person“ vor „Gesicht der anderen Person auf diesem Foto“;
  - „Gesicht der anderen Person“ vor der Obergrenze. An der Obergrenze wird ein Doppelgänger abgewiesen, nicht nur benannt.
  - Nach jeder Abweisung ist der Schnappschuss der drei Personentabellen gleich wie vorher.
- **Umfang der beiden neuen Abweisungen** (Entscheidung der Architektur):
  - „Schon ein Gesicht dieser Person“ sperrt **nur** eine Korrektur-Box, nie eine Erkennungs-Box derselben Person. Zwei Fälle auf einem Foto, auf dem A mit Box erkannt ist:
    - Wird das erkannte Gesicht A zugeordnet, gelingt das, und die Box der Korrektur gilt.
    - Wird ein **anderes** Gesicht A zugeordnet, gelingt das ebenfalls. Danach gilt die Korrektur-Box, und das zuvor erkannte Gesicht steht wieder in „Ohne Namen“ (Regel 2 vor Regel 3).
  - „Gesicht der anderen Person“ prüft gegen `assigned_face_boxes` und damit auch gegen die **Erkennungs**-Box der anderen Person. Ein als A erkanntes Gesicht B zuzuordnen ergibt `409`. Nach `applies=false` für A auf diesem Foto gelingt dieselbe Zuordnung zu B. Gegenprobe: Hat A dort nur einen Namen ohne Box (Regel 4), sperrt nichts.
- **Bedingtes Setzen der Box** (zweite Linie hinter der Schreibsperre). Die Wiederholung der Vorprüfung unter der Sperre wird per `monkeypatch` umgangen, Muster „Vorabprüfung umgehen“ aus 0292:
  - Besteht schon eine Korrektur mit Box für das Paar, trifft `UPDATE … WHERE face_box_x IS NULL` null Zeilen. Ergebnis: `FaceAlreadyAssignedOnPhoto` (`409`), die alte Box ist unverändert, und die in derselben Transaktion angelegte Referenz ist zurückgerollt (`reference_count` gleich, kein `SENTINEL` des neuen Gesichts in `person_references`).
  - Besteht noch keine Korrektur und entsteht sie gleichzeitig, greift `UNIQUE(photo_id, person_id)`. Aus dem `IntegrityError` wird `409`, nie `500`, ebenfalls ohne übrig gebliebene Referenz.
  - Gegenfälle, in denen das bedingte Setzen genau eine Zeile trifft und gelingt: eine Korrektur `applies=true` ohne Box (Name nur für das ganze Foto) und eine Korrektur `applies=false` ohne Box. Danach gilt `applies=true` mit Box und Referenz.
- **Obergrenze:**
  - Das 20. Gesicht des aktuellen Modells ergibt `learned=True`.
  - Das 21. ergibt `learned=False`, keine Referenz und eine Korrektur mit Box ohne `reference_id`. `reference_count` bleibt 20.
  - Referenzen fremden `model_key` zählen nicht mit.
  - Nach einer Rücknahme (19) lernt die nächste Zuordnung wieder.
  - Die bestehenden Fälle `test_the_twentieth_is_accepted_the_twenty_first_refused…` werden umgeschrieben, nicht gelöscht.
- **Rücknahme (`set_correction` mit `applies=false`):**
  - Paar mit Box und Referenz: Die Referenz ist gelöscht, Box und `reference_id` sind `NULL`, `applies=false`. Die übrigen Referenzen beider Personen sind unverändert (Zwilling).
  - Paar mit Box ohne Referenz: Die Box ist leer, keine Referenz wird gelöscht (`reference_count` gleich).
  - Nur Erkennung, oder Korrektur ohne Box: Keine Referenz wird gelöscht.
  - Zweimal `applies=false`: Beim zweiten Mal ändert sich nichts, und es gibt keinen Fehler.
  - `applies=true` auf einem Paar mit Box und Referenz lässt Box und Referenz stehen. Ein Leeren der Box verletzte `ck_…_reference_requires_face` und ergäbe `500`.
  - `applies=true` nach einer Rücknahme ergibt einen Namen für das ganze Foto ohne Box. Das Gesicht bleibt damit in „Ohne Namen“.
  - Alles in **einer** Transaktion: Scheitert das Löschen der Referenz (per `monkeypatch` erzwungen), bleibt die Korrektur unverändert.
- **Früher gezeigte Gesichter:** Eine Referenz ohne verknüpfte Korrektur (Bestand aus 0292) übersteht `applies=false` auf jedem Foto dieser Person. Erst `delete_person` entfernt sie.
- **Modellwechsel (`_store_reference`):** Mit durchgesetztem Fremdschlüssel zeigen Korrekturen auf Referenzen des alten `model_key`. Eine neue Zuordnung ergibt:
  - Die alten Referenzen sind weg, deren Korrekturen behalten die Box mit `reference_id = NULL` und stehen damit auf `face = "assigned"`.
  - Kein `IntegrityError`.
  - Die neue Korrektur trägt ihre neue Referenz.
  - Gegenprobe ohne das Leeren (per `monkeypatch` übersprungen): `IntegrityError`. So ist belegt, dass der Fall den Fremdschlüssel wirklich erreicht.
- **`delete_person`:** Die Korrektur mit `reference_id` fällt vor ihrer Referenz, ohne `IntegrityError`. Die andere Person bleibt unverändert.
- **Schreibstelle:** `PersonReference` wird weiter an genau einer Stelle geschrieben (bestehender Wächter). Neu wird `reference_id` an genau einer Stelle gesetzt und an genau zwei Stellen geleert (Rücknahme, Modellwechsel).

**Worker (`test_worker_persons.py`)**

- **Box in der Erkennung:** Die geschriebene Box ist die des Kandidatengesichts, nicht die des ersten Gesichts. Lage: der Kandidat an Index 1 mit `BOX_SENTINEL`.
- **Übergang:** Eine Erkennung ohne Box aus einem früheren Lauf wird vom nächsten Lauf durch eine mit Box ersetzt.
- **Nicht endliche Box an der Schreibstelle** (zweite Linie, per `monkeypatch` hinter dem Adapter erzwungen): Die Person wird auf diesem Foto nicht benannt, kein `IntegrityError`, Lauf `SUCCESS`, die übrigen Fotos sind geschrieben.
- **Beständigkeit** (Erweiterung von `test_no_run_writes_or_deletes_a_correction`): Der Schnappschuss der Korrekturen samt vier Box-Spalten und `reference_id` ist nach zwei Läufen gleich.
- **Entfernter Name kehrt nicht zurück:** `applies=false` auf einem erkannten Foto mit Box, danach zwei Läufe, in denen der Fake die Person dort weiter findet. Wirksam bleibt „nicht zugeordnet“.
- **Zugeordnetes Gesicht wirkt global:** Zuordnung in Projekt A über die API. Danach benennt ein Lauf in Projekt B ein Gesicht mit demselben Merkmal.
- **Rücknahme wirkt ab dem nächsten Lauf:** Eine Person hat die Referenzen X und Y. Projekt B hat ein Foto mit X und ist nach einem Lauf benannt. Nach der Rücknahme von X in Projekt A:
  - Bis zum nächsten Lauf bleibt der Name in B stehen (keine rückwirkende Änderung).
  - Nach dem nächsten Lauf ist er weg, weil der Kosinus zu Y 0 ist.
- **Obergrenze lernt nicht:** Ein Gesicht, das an der Obergrenze zugeordnet wurde, verändert den Schwerpunkt nicht. Ein Lauf ergibt dieselben Erkennungen wie ohne diese Zuordnung (Zwilling).

**API – „Ohne Namen“ (`test_api_unnamed_faces.py`, neu)**

- **Menge je Foto** über die Wahrheitstabelle aus `test_persons.py`, jetzt über die Antwort gemessen:
  - Eine Erkennung mit Box nimmt ihr Gesicht heraus, eine Erkennung ohne Box nimmt keines heraus (Übergang).
  - Ein Name nur für das ganze Foto nimmt keines heraus.
  - `applies=false` über einer Erkennung mit Box gibt das Gesicht wieder frei.
  - Zwei Personen auf einem Foto nehmen genau zwei Gesichter heraus.
- **Differenzprobe gegen die Detailansicht:** Je Foto ist `{face_index}` der Auflistung ∪ zugeordnete Indizes gleich `{index}` aus `GET /photos/{id}/faces`, und beide Mengen sind disjunkt. Dazu eine Lage mit 21 Gesichtern, von denen die Auflistung wie die Detailansicht höchstens 20 kennt.
- **Ausschuss:** Ein verworfenes Foto wird aufgelistet.
- **Projektbindung:** Die Ids zweier Projekte liegen verzahnt (A: 1, 3, 5; B: 2, 4). Die Auflistung von A enthält nie ein Foto von B, und `photos_done`/`photos_total` zählen nur A.
- **Seitengrenzen und Cursor:**
  - 25 Fotos ohne Gesicht: Seite 1 umfasst 24 Fotos, `next_after_id` ist die Id des 24. Seite 2 umfasst 1 Foto, `next_after_id` ist `null`.
  - Genau 24 Fotos: eine Seite, `next_after_id` ist `null`, es gibt keine leere Folgeseite.
  - Gesichterschwelle: 20 + 20 + 8 Gesichter (48 erreicht) ergeben eine Seite, die nach dem dritten Foto endet. 20 + 20 + 7 (47) laufen ins vierte Foto weiter. Die Gesichter eines Fotos verteilen sich nie auf zwei Seiten.
  - `after_id` ist exklusiv. Eine `after_id` auf eine gelöschte oder fremde Id setzt beim nächsten Foto des Projekts fort.
  - Einzelabfrage `after_id = photo_id - 1`, `max_photos = 1` liefert genau dieses Foto. Ist es gelöscht, kommt das nächste Foto.
  - `photos_done` zählt die Fotos des Projekts mit Id ≤ dem zuletzt bearbeiteten Foto, auch bei der Einzelabfrage.
  - Projekt ohne Fotos: `faces=[]`, `photos_total=0`, `next_after_id=null`.
  - Vollständigkeit über alle Seiten: Die Vereinigung aller Seiten eines Projekts mit 60 Fotos ergibt jedes Gesicht genau einmal. Die Folge ist streng aufsteigend nach (Foto-Id, Index), auch mit `shuffle=True`.
- **Grenzen:** `after_id` −1 und über `MAX_ID` sowie `max_photos` 0 und 25 ergeben `422`. Ein unbekanntes Projekt ergibt `404`, ohne `401` ein `401` (auch in `test_auth_guard.py`, Kommentar auf acht Endpunkte).
- **Nicht bereit:** Drei Ursachen ergeben je `not_ready_photo_ids` und keine Gesichter dieses Fotos, und die übrigen Fotos der Seite sind vollständig:
  - Die Display-Variante fehlt. Dann gibt es null Modellaufrufe für dieses Foto.
  - Die Datei ist nicht als Bild lesbar.
  - Der Analyzer wirft.
- **Nichts über Unbekannte** (0002, 0292 Punkt 3):
  - Schnappschuss aller Tabellen aus `Base.metadata.sorted_tables` vor und nach der Auflistung über alle Seiten eines Projekts mit drei unbekannten Gesichtern je Foto: gleich.
  - Verzeichnisschnappschuss von Cache-Verzeichnis und `tmp_path` vorher und nachher: gleich.
  - **Kein Prozess-Cache:** Eine zweite vollständige Auflistung ruft `detect` erneut je Foto auf. Die Zahl der `detect`-Aufrufe ist genau 2 × Zahl der bereiten Fotos.
  - `embed` wird nie aufgerufen. Die Zählung läuft über alle Seiten und über eine Einzelabfrage.
  - `BOX_SENTINEL` steht in keiner Tabellenzeile, in keinem Log und in keiner Antwort (die Antwort trägt keine Box).
  - Gegenprobe im selben Modul: Nach einer Zuordnung dieses Gesichts steht `BOX_SENTINEL` in `photo_person_corrections` und nur dort. Sonst wäre die Suche vakuum-grün.
  - **Nur das zugeordnete Gesicht wird gespeichert:** Auf einem Foto mit drei Gesichtern, die je einen eigenen Box-Sentinel tragen, wird Gesicht 1 zugeordnet. Danach finden sich die Sentinels von Gesicht 0 und 2 nirgends.
  - **Log (S11):** Ein werfendes Foto ergibt in `caplog` den Typnamen und die `photo_id`. Nie stehen dort eine Box, ein Index oder ein Präfix eines `crop_jpeg`.
- **Antwortform:**
  - Schlüsselmengen exakt: Seite `{faces, not_ready_photo_ids, next_after_id, photos_done, photos_total}`, Gesicht `{photo_id, face_index, crop_jpeg}`.
  - `crop_jpeg` ist base64 eines JPEG (Magic Bytes). Die längere Seite ist ≤ 160 px, und es gibt kein EXIF.
  - `Cache-Control: no-store` und `X-Content-Type-Options: nosniff`.
- **Beide Nutzer:** Dieselbe Auflistung mit zwei verschiedenen Tokens ergibt byte-gleiche Antworten.
- **Executor, eine Zuordnung wartet höchstens ein Foto:**
  - Die Auflistung einer Seite mit 5 Fotos wird am ersten `detect` über `before_detect_returns` angehalten.
  - Dann wird eine Zuordnung gestartet. Der Modell-Thread wird erst freigegeben, wenn ihr Executor-Auftrag eingereiht ist (Signal aus einer Hülle um `_on_model_thread`).
  - Erwartete Aufruffolge: `detect` (Foto 1), `detect` (Zuordnung), danach Fotos 2–5. Alle laufen auf dem Thread `gesichter`.
  - Rot gegen eine Umsetzung, die eine ganze Seite als **einen** Auftrag abgibt.
- **Keine DB-Verbindung über den Modellaufruf:**
  - Der Test setzt `get_session` **und** `get_session_factory` per `dependency_overrides` auf **dieselbe** dateibasierte Test-Engine. Pool-Ereignisse `checkout`/`checkin` zählen die ausgeliehenen Verbindungen. Nur so ist auch die Verbindung sichtbar, die die Anfrage-Sitzung seit `get_current_user` (`session.get(User, …)`) hält. Läge `get_session` auf einer anderen Engine, wäre der Fall grün, während die Anfrage-Sitzung die Verbindung über alle Modellaufrufe hält.
  - Während `detect` über `before_detect_returns` angehalten ist, hält die Auflistung **keine** Verbindung (ausgeliehen minus zurückgegeben = 0).
  - Gegenprobe im selben Fall: Zwischen zwei Fotos wurde nachweislich ausgeliehen, der Zähler misst also.
- **Zugeordnete Boxen werden je Foto frisch gelesen:** Während `detect` von Foto 1 (`on_detect`, zweite Verbindung) entsteht eine Korrektur mit Box auf Foto 2. In **derselben** Seite fehlt dieses Gesicht von Foto 2 bereits. Das ist rot gegen eine Umsetzung, die die Boxen einmal je Seite vorab liest.
- **Abbruch bei getrennter Verbindung:**
  - Der Endpunkt wird direkt als ASGI-App mit eigenem `receive` aufgerufen. `receive` liefert `http.disconnect`, sobald `on_detect` das erste Foto gemeldet hat, und blockiert vorher. `is_disconnected` fragt nur ab und wartet nicht.
  - Bei einer Seite mit 5 Fotos gibt es danach keinen weiteren `detect`-Aufruf (genau 1). `send` bekommt kein `http.response.start`.
  - Gegenprobe ohne Trennung: 5 Aufrufe und eine Antwort.

**API – Zuordnen, Festlegen, Zurücknehmen (`test_api_persons.py`)**

- **`FaceAssignmentOut`:** `POST /persons` und `POST …/references` liefern `201` mit der exakten Schlüsselmenge `{person, learned, photo_persons}`. `photo_persons` ist die wirksame Liste des Fotos samt `face`.
- **Obergrenze:** `learned: false` statt `409`. Der bestehende Fall `test_a_reference_assigns_writes_no_feedback_event_and_is_capped` wird umgeschrieben.
- **Zwei neue Abweisungen** mit wörtlichem `detail` und ohne Schreiben (Tabellenschnappschuss):
  - „Diese Person hat auf diesem Foto schon ein Gesicht.“ Sie gilt nur für eine Korrektur-Box. Die Prüfung kommt vor dem Modellaufruf, belegt über null `detect`-Aufrufe.
  - „Dieses Gesicht gehört auf diesem Foto schon der anderen Person.“ Die Überdeckung wird gegen die Korrektur-Box **und** gegen die Erkennungs-Box der anderen Person geprüft, beide ergeben `409`.
  - Kein `detail` enthält einen Namen. Die Lage verwendet dafür einprägsame Namen.
- **Geänderte Datei (ADR 0127, akzeptiert):**
  - Der Index liegt jenseits der neuen Liste: `409` „An dieser Stelle ist auf dem Foto kein Gesicht mehr zu finden.“, ohne Schreiben.
  - Merkmal und Box kommen aus **demselben** Detektionslauf (`_embedding_at`). Mit `shuffle=True` trägt die Korrektur die Box des Gesichts, dessen Merkmal in `person_references` steht, nie die des Gesichts, das die Auflistung zeigte.
- **Nicht endliche Detektorzeile im API-Pfad** (per `monkeypatch` hinter dem Adapter): `409` wie „kein verwertbares Merkmal“, ohne Schreiben.
- **Rücknahme über `PUT … {applies: false}`:**
  - Die Antwort ist die wirksame Liste ohne diese Person. `GET /persons` zählt eine Referenz weniger.
  - Danach steht das Gesicht wieder in der Auflistung, auch wenn eine Erkennung mit Box für das Paar besteht.
  - Derselbe Aufruf aus der Detailansicht ist derselbe Endpunkt. Ein eigener Fall entfällt, der Frontend-Test prüft die Beschriftung.
- **`PhotoPersonOut.face`:** Die Schlüsselmenge ist exakt `{person_id, origin, face}` an jedem Lesepfad, der `_to_photo_out` aufruft (Liste, Entwurf, Detail, PUT). Das ist die bestehende Parametrierung, erweitert um die drei Werte von `face`.
- **Gleiche Menge:** Die Personeneinschränkung `?person_id=` liefert ohne Bewertungsfilter dieselbe Menge, Reihenfolge `(taken_at, id)` und `total` wie bisher, einschließlich Ausschuss. Ein Foto mit beiden Namen steht in beiden Abfragen.
- **Zusammenspiel:** Nach Zuordnen, Entfernen und Zurücknehmen über die Übersichts-Endpunkte zeigen Detail, Personeneinschränkung und Entwurf den neuen Zustand. Umgekehrt zeigt die Auflistung nach einem `PUT` aus der Detailansicht den neuen Zustand.
- **Keine Nebenwirkung** (Zwilling, 0002 Sektion 0533 Punkt 2): Zwei gleiche Projekte, eines durchläuft Zuordnen, Festlegen, Entfernen und Zurücknehmen. Verglichen werden:
  - Bewertungen;
  - Motivstärken;
  - `GET …/stats`;
  - Entwurfsmenge und -reihenfolge, ohne das Feld `persons`;
  - Auswahlvorschlag.

  Alle sind gleich, und keines schreibt ein `FeedbackEvent`.
- **Schreibsperre `_person_write_lock`** (neues Muster, 0002). Aufbau:
  - dateibasierte SQLite über `db.make_engine`;
  - `get_session` je Anfrage aus einer eigenen Session-Factory, denn eine geteilte `AsyncSession` erlaubt keine zwei Anfragen;
  - ein Gatter im kritischen Abschnitt. Eine Hülle um `persons.assigned_face_boxes` hält den **ersten** Aufruf an einem `asyncio.Event`.
  - Die zweite Anfrage wird gestartet. Das Gatter öffnet erst, wenn die zweite **entweder** die Prüfungen betreten hat (Umsetzung ohne Sperre) **oder** an der Sperre wartet (aufzeichnender Sperr-Ersatz). Beides ist beobachtet, keine Wartezeit.

  Pflichtfälle:
  - Dasselbe Gesicht, gleichzeitig zwei Personen: genau ein `201`, ein `409` „… schon der anderen Person.“, genau eine Box, genau eine neue Referenz.
  - Obergrenze bei 19 Referenzen, zwei gleichzeitige Zuordnungen: 20 Referenzen, die zweite liefert `learned: false`.
  - Zwei gleichzeitige Festlegungen bei einer Person: genau eine neue Person, der Bestand aus 0292 bleibt.
  - `PUT applies=false` (Rücknahme) gleichzeitig mit einer Zuordnung derselben Person auf demselben Foto: Das Ergebnis ist eine der beiden seriellen Reihenfolgen. Nie bleibt eine Referenz, deren Korrektur keine Box trägt, und nie eine Box ohne `applies`.
  - **Wiederholte Vorprüfung:** Während `detect` einer Zuordnung schreibt eine zweite Verbindung (`on_detect`) eine Korrektur mit Box für dasselbe Paar. Ergebnis: `409` „schon ein Gesicht“, die fremde Box ist unverändert, keine Referenz ist entstanden. Mit umgangener Wiederholung greift das bedingte Setzen (siehe `test_persons.py`) mit demselben Ergebnis. Dieser Fall prüft die erste Linie, jener die zweite.
  - `DELETE /persons/{id}` gleichzeitig mit einer Zuordnung zu dieser Person: Entweder ist die Person weg und die Zuordnung liefert `404`, oder die Zuordnung ist gespeichert und fällt mit der Person. In beiden Fällen bleibt keine Zeile mit der `person_id`.
  - Die Modellaufrufe liegen **nie** unter der Sperre. Während ein `detect` angehalten ist, läuft ein `PUT` einer anderen Person durch.
  - **Keine Verbindung während Modellaufruf und Warten auf die Sperre** (Regel der Architektur: Vorprüfungen, `rollback()`, Modellaufruf, Sperre, Prüfungen und Schreiben). Gemessen wird wie bei der Auflistung am Pool, mit `get_session` auf derselben Test-Engine:
    - Während das `detect` der einzigen laufenden Zuordnung angehalten ist, ist der Saldo 0.
    - Wartet die zweite Zuordnung an der Sperre (Gatter aus dem ersten Pflichtfall), ist der Saldo genau 1, nämlich die Verbindung der ersten im kritischen Abschnitt.
    - Gegenprobe: Vor dem Modellaufruf wurde ausgeliehen.
  - **`current_user` nach dem Rollback:** Jede erfolgreiche Zuordnung, Festlegung und Rücknahme schreibt die `user_id` des Aufrufers in die Korrektur, einmal je Nutzer mit zwei Nutzern. Die Antwort ist `201`/`200` und nie `500` (`MissingGreenlet`, wenn `current_user.id` erst nach `rollback()` gelesen wird). Der Fall läuft über den echten API-Weg, nicht über `persons.py`.
  - **Rot-Nachweis im PR:** Die Sperre wird einmal lokal entfernt, und die ersten beiden Fälle werden rot belegt.
- **Voraussetzung „ein API-Prozess“:** Ein Wächter liest `backend/Dockerfile` und alle `docker-compose*.yml`.
  - Kein `uvicorn`-Aufruf trägt `--workers`, und kein `WEB_CONCURRENCY` ist gesetzt.
  - Gegenprobe: Es gibt mindestens einen gefundenen `uvicorn photosort.main:app`-Aufruf je Datei, in der er erwartet wird. Sonst wäre der Wächter vakuum-grün.
- **Register:** Der neue Endpunkt steht in `test_openapi_beschreibungen.py`.

**Migration und Modelle (`test_migration_gesichtsbezug_personen.py`, Muster `test_migration_personen.py`)**

- Die Revision hängt an `1f4027405ea5`, und `test_migration_chain.py` hat genau einen Head.
- **Upgrade:**
  - Die Spaltensätze beider Tabellen stimmen exakt mit den Invarianten der Architektur überein.
  - `person_references` bleibt unverändert, ohne Foto- oder Projektspalte.
  - Bestehende Zeilen haben alle Box-Spalten und `reference_id` = `NULL`.
- **Benannte Einschränkungen**, je eine Zeile, die sie verletzt, ergibt `IntegrityError`:
  - Box mit drei von vier Werten;
  - `x = 1.0` geht, `x = 1.0 + 2**-20` nicht;
  - `width = 0` nicht, `width = 1` geht;
  - Box bei `applies = false`;
  - `reference_id` ohne Box;
  - dieselbe `reference_id` an zwei Korrekturen;
  - `reference_id` auf eine nicht vorhandene Referenz (Fremdschlüssel durchgesetzt).
- **Kein DB-Löschen am Fremdschlüssel:** Das direkte Löschen einer verknüpften Referenz scheitert. Das belegt „ohne DB-Aktion“ und damit die Reihenfolgepflicht in `delete_person` und `_store_reference`.
- **Downgrade mit Bestand:** Mit Korrekturen samt Box und `reference_id` und Erkennungen mit Box läuft der Downgrade unter SQLite-Batch-Modus durch. Danach entsprechen die Spaltensätze wieder 0292, und die Zeilen sind erhalten (Anzahl je Tabelle gleich).
- Postgres-DDL-Kompatibilität über `test_postgres_ddl_compatibility.py`.
- `test_models.py`: Die Spaltensätze der ORM-Modelle werden auf Gleichheit festgehalten (S5 fortgeschrieben).

**Löschen und Kaskaden**

- `project_graph.py` legt eine Korrektur mit Box und `reference_id` an. Nach der Projektlöschung:
  - Die Korrektur ist weg.
  - `persons` und alle `person_references` sind unverändert, auch die verknüpfte Referenz.
  - Der Schwerpunkt der Person ist gleich, und die Referenz wirkt in einem anderen Projekt weiter.
- Scan (ein Foto verschwindet): Korrektur und Erkennung fallen per Kaskade, die Referenz bleibt.
- Rücknahme einer Referenz, deren Foto inzwischen gelöscht ist, gibt es nicht: Die Korrektur ist mit dem Foto gefallen. Das ist festgehalten, weil „Referenz ohne Korrektur verschwindet nur mit ihrer Person“ sonst eine Behauptung bliebe.

**Import-Graph (`test_persons_import_graph.py`)** bleibt unverändert und deckt `_unnamed_on_photo` ab, weil er in `api/persons.py` liegt. Neu ist nur eine Gegenprobe: Die Funktion ist dort definiert und nicht in einem Modul außerhalb der Prüfmenge.

**Demo-Zustand (`test_demo_state.py`)**

- Es gibt eine Erkennung mit Box und eine Korrektur mit Box und synthetischer Referenz.
- Die Referenz-`model_key` ist der aktuelle `MODEL_KEY`, sodass `face = "shown"` entsteht und nicht `"assigned"`.

### Frontend (vitest)

- **`useUnnamedFaces`** (Muster 0002 „Antworten im Flug“: Antworten über manuell auflösbare Promises, keine Zeitgeber):
  - **Nachladen:** Die nächste Seite folgt selbsttätig, solange `next_after_id` gesetzt ist. Sie stoppt bei einem Fehler. „Erneut versuchen“ setzt mit dem `after_id` der gescheiterten Seite fort, nicht mit `0` (Anfrageprotokoll).
  - **Fortschritt:** Er kommt nur aus Seitenantworten. Eine Einzelabfrage mit kleinerem `photos_done` ändert weder Fortschritt noch Cursor.
  - **`removeFace`:** Das Gesicht verschwindet ohne Anfrage. Es wirkt auch auf eine Seite und eine Einzelabfrage, die vor dem Entfernen gestartet und danach aufgelöst wurde: Das Gesicht erscheint nicht wieder.
    - Gegenfall: Eine Einzelabfrage, die **nach** dem Entfernen startet (Rücknahme), setzt das Gesicht wieder ein.
  - **`refreshPhoto`:**
    - Es ersetzt alle Gesichter des Fotos an ihrer Stelle zwischen den Nachbarfotos.
    - Null Gesichter lassen sie entfallen.
    - `not_ready` fügt die Id zur Menge hinzu, und zwar eindeutig: Zweimal dasselbe Foto zählt einmal.
    - Liefert die Antwort ein anderes Foto, entfallen die Gesichter des angefragten Fotos, und die des gelieferten werden **nicht** eingefügt.
    - Bei einem Foto jenseits des Cursors geht keine Anfrage raus.
    - **Seite im Flug:** Liegt eine Seite im Flug, deren Bereich das Foto enthält, wird der Aufruf vorgemerkt und nach deren Ankunft gegen den neuen Cursor entschieden. Beide Reihenfolgen sind geprüft: die Seite enthält das Foto bereits ohne das Gesicht (dann folgt eine Einzelabfrage) oder die Seite scheitert (dann folgt keine).
  - **`refreshFailures`:** höchstens ein Eintrag je Foto. `retryRefresh` entfernt ihn bei Erfolg. Ein Fehler lässt Seiten und Cursor unberührt.
  - **Cache:**
    - Eine breite Invalidierung von `['photos', projectId]` löst keine Auflistungsanfrage aus.
    - Fokus und Reconnect lösen keine aus.
    - Aushängen und erneutes Einhängen beginnt bei `after_id = 0` (`gcTime: 0`).
- **`usePersonGroupQuery`:**
  - Die Seitengröße ist 24, `personIds` ist `[personId]`, und es gibt keinen Bewertungsfilter.
  - Ein gleichzeitig eingehängter `usePhotoSequenceQuery` mit Seitengröße 60 für dieselbe Person ergibt in keinem der beiden Beobachter doppelte oder fehlende Fotos, auch nach einer breiten Invalidierung. Das ist der Grund für den getrennten Schlüssel.
  - **Offset und Anzahl nach Entfernen** (Regel der Architektur: verbleibend + Rest, nächster Offset = verbleibend). Der Server-Stub filtert wie der echte Endpunkt, damit ein falscher Offset tatsächlich ein Foto überspringt:
    - 30 Fotos, auf Seite 1 werden 2 Namen entfernt: Die Anzahl ist 28. „Mehr laden“ fragt Offset 22 an und bringt genau die übrigen 6 Fotos, keines fehlt, keines doppelt. Danach ist die Anzahl weiter 28, und es gibt keine weitere Seite.
    - Derselbe Fall nach einer Invalidierung, die die aktive Gruppe neu lädt: gleiches Ergebnis.
    - Entfernen, nachdem alle Seiten geladen sind: Die Anzahl sinkt, und `hasNextPage` bleibt falsch.
    - Zwischen Seite 1 und 2 kommt serverseitig ein Foto weiter vorn hinzu, sodass Seite 2 mit einer schon geladenen Id beginnt: Das Foto steht einmal da, es gibt keinen doppelten Listenschlüssel, und nach dem letzten Nachladen ist die Anzahl gleich der Zahl der Karten. Das vorn hinzugekommene Foto fehlt bis zum nächsten Laden. Das ist die bekannte Grenze der Offset-Paginierung und wird nicht als richtige Anzahl festgeschrieben.
- **`useFaceAssignment`:**
  - Bei Erfolg steht `photo_persons` der Antwort unverändert in allen Foto-Caches des Projekts (`storePhotoPersons`). Es wird nichts lokal zusammengesetzt: Die Antwort weicht absichtlich von einem naiven Anhängen ab.
  - `PERSONS_QUERY_KEY` wird neu geladen. In der Übersicht lädt zusätzlich die Gruppe der Person neu.
  - `learned` wird durchgereicht.
- **`useCurationLightbox`:**
  - `open(photoId, triggerKey)`: Beim Schließen bekommt der Auslöser mit diesem Schlüssel den Fokus. Lage: ein Foto mit beiden Namen, geöffnet aus der zweiten Gruppe.
  - Rückfall auf die Foto-Id, dann auf die Überschrift.
  - Der Verlaufszustand trägt nur die Id, nie den Schlüssel (Auflage S2 aus 0531, geprüft am `location.state`).
  - Nach einem Reload (`initialEntries` mit State) gilt das heutige Verhalten.
  - Die bestehenden Fälle von `AlbumDraftPage`/`AlbumSelectionPage` bleiben ohne Änderung grün.
- **`FaceCropTile`:**
  - Die Blob-URL entsteht aus base64 und wird beim Entfernen der Kachel und beim Aushängen der Seite freigegeben (`revokeObjectURL`-Spion, je URL genau einmal).
  - Ein nicht darstellbarer Ausschnitt ergibt die Platzhalterfläche mit `alt` „Ausschnitt nicht verfügbar“. Zuordnen bleibt möglich.
- **`PersonPhotoGroup`:**
  - Anzahl mit Singular und Plural. Sie steht erst nach der ersten Seite.
  - Herkunft und Gesichtszeile: Drei Werte von `face` × zwei Herkünfte. Jeder Wortlaut wird einmal wörtlich geprüft.
  - Die Aktion lautet „Gesicht zurücknehmen“ bei `shown` und sonst „Name entfernen“. Beide senden `applies: false`.
  - Busy gilt nur für die eigene Karte.
  - **Nach Erfolg:**
    - Die Karte ist weg, und die Anzahl ist um eins kleiner.
    - Die Statusmeldung erscheint in beiden Wortlauten.
    - Der Fokus folgt der Regel „nachrückend, sonst vorige, sonst `h2`“, je ein Fall.
    - `refreshPhoto` wird mit dem Dateinamen gerufen.
  - Fehler-`Alert` mit `detail`. Bei `404` lädt die Personenliste neu, und der Fokus geht auf `h1`.
  - „Mehr laden“ mit „{geladen} von {n}“. Der leere Zustand gilt auch, nachdem die letzte Karte gegangen ist.
- **`UnnamedFacesGroup`:**
  - Der Fortschritt hat alle fünf Zustände der Tabelle. Die Fortschrittszeile ist nicht live.
  - „nicht bereit“ zählt eindeutige Ids, steht schon während der Suche und bleibt nach dem Abschluss stehen.
  - Die Liste ist flach und in der Reihenfolge der Antwort, ohne Gruppierung je Foto: zwei Gesichter desselben Fotos als zwei Karten ohne gemeinsamen Container.
  - Die Personen-Schaltflächen stehen in der Reihenfolge von `GET /persons` und sind auf jeder Karte gleich: kein `aria-pressed`, keine abweichende Ausprägung, kein vorgewählter Fokus.
  - Keine Zahl außer Fotozahlen: Ein Textdurchlauf über die Gruppe findet keine Ziffer außerhalb der Fortschritts- und „nicht bereit“-Zeile.
  - **Zuordnen:**
    - Ein Druck sendet genau eine Anfrage mit `{photo_id, face_index}`, ohne Rückfrage.
    - Die Karte ist sofort weg, und die Auflistung wird nicht neu angefragt.
    - Die Meldung lautet bei `learned: true` und `false` je wörtlich.
    - Der Fokus folgt der Regel „nachrückend, sonst vorige, sonst `h2`“.
  - **Zwei Zuordnungen hintereinander:** Die zweite Karte ist bedienbar, während die erste noch aussteht. Beide Antworten treffen in umgekehrter Reihenfolge ein, und beide Karten sind danach weg.
  - **Stabile Schlüssel über ein Entfernen hinweg** (Voraussetzung für das native Scroll Anchoring, 0002 Sektion 0300): Nach `removeFace` und nach dem Eintreffen einer weiteren Seite sind die übrigen Karten dieselben DOM-Knoten wie vorher (Knotenidentität, nicht Text). Dasselbe gilt für `refreshPhoto` bei den Karten anderer Fotos.
  - **Neue Person:**
    - Die Schaltfläche gibt es nur bei weniger als zwei Personen.
    - Es ist höchstens ein Formular offen.
    - Esc und Abbrechen geben den Fokus auf „Neue Person…“ zurück.
    - „Festlegen“ ist bei getrimmt leerem Namen gesperrt.
    - Enter sendet ab. Der Fall hat einen aktivierten Button als Vorbedingung (0002 Sektion 0532 Punkt 2).
    - Nach Erfolg lädt die Personenliste neu, und bei zwei Personen entfällt „Neue Person…“ auf allen Karten.
  - **Ablehnungen**, je `detail` die festgelegte Folge:
    - Karte bleibt, `Alert` mit wörtlichem `detail`, kein Name in einem der beiden neuen Texte.
    - „zwei Personen“: Die Liste lädt neu, und das Formular ist weg.
    - `409`/`422` beim Namen: `aria-invalid` und `aria-describedby`, die Eingabe bleibt.
    - `404`: Die Liste lädt neu.
    - „kein Gesicht mehr“: `refreshPhoto(photoId, null)`, die Meldung steht in der Statusleiste, der Fokus folgt der Regel.
  - `refreshFailures`: je Eintrag ein `Alert` in der Statusleiste mit dem passenden Wortlaut mit oder ohne Dateiname, und „Erneut versuchen“ ruft `retryRefresh`.
- **`ProjectPersonsPage`:**
  - Zustände: Personen laden, Fehler, keine Person (nur „Ohne Namen“, keine Sprungleiste), unbekanntes Projekt.
  - Gruppenreihenfolge: Personen nach `GET /persons`, „Ohne Namen“ zuletzt.
  - **Entfernte Person:** Fehlt eine Person nach dem Neuladen von `GET /persons`, gibt es ihre Gruppe, ihren Eintrag in der Sprungleiste und ihre Schaltfläche auf keiner Karte mehr.
  - Die Sprungleiste setzt den Fokus auf das `h2`, und die Adresse bleibt gleich.
  - **Gruppen warten nicht:** Die Auflistung bleibt unaufgelöst, die Personengruppen rendern trotzdem.
  - **Großansicht:** `items` sind die geladenen Fotos aller Personengruppen, nach Id entdoppelt.
  - **Fremdtext:** Ein Name mit Markup erscheint an jeder Renderstelle als Text (Gruppenüberschrift, Sprungleiste, Schaltfläche, Meldung).
- **`PhotoPersonsSection`/`PersonFacePicker`:**
  - Das Zustandswort nennt das Gesicht (`shown`, `assigned`).
  - Die Schaltfläche heißt bei `shown` „Gesicht zurücknehmen“.
  - `learned: false` ergibt den Satz zur Obergrenze, und die Wahl klappt zu.
  - Die beiden neuen Abweisungen erscheinen als `Alert`, und die Wahl bleibt offen.
  - Der Fall „Obergrenze als `409`“ entfällt.
- **`PersonsPage`:** der neue Leertext.
- **`ProjectNav`/`projectRoutes`:** Das Nebenziel „Personen“ steht hinter „Einstellungen“ und „Statistik“, in beiden Darstellungen (Muster 0298), mit `aria-current` auf der Route.
- **Design-Vertrag:** Die Zuordnen-Schaltflächen stehen in der Freigabeliste des heißen Pfads (`designSystem.contract.test.ts`).

### E2E und Prüfstack

- `no-horizontal-scroll.spec.ts`:
  - Die Route `/projects/:id/persons` kommt dazu.
  - Vorbedingung: Die Personengruppe mit dem 40-Zeichen-Demonamen und die Statusleiste von „Ohne Namen“ sind sichtbar.
- `tap-targets.spec.ts`: „Gesicht zurücknehmen“ bzw. „Name entfernen“ auf einer Demo-Karte bei 360 px.
- `sticky-header.spec.ts`:
  - Die Statusleiste von „Ohne Namen“ liegt im gescrollten Zustand unter der Kopfzeile und disjunkt zu ihr.
  - Die Anzahl sticky Elemente auf der Route ist exakt.
  - Rot-Nachweis im PR.
- **Nicht in E2E:** Karte, Formular, Busy und Obergrenzen-Satz von „Ohne Namen“. Die Demo-Bilder enthalten keine Gesichter. Abgedeckt ist das in `UnnamedFacesGroup.test.tsx`. Dass es im Prüfstack nicht zu sehen ist, ist eine benannte Grenze.
- **Manuell im Prüfstack:**
  - Bei 360 und 1280 px: die Personengruppe mit „Gesicht gezeigt“ und „Gesicht zurücknehmen“, eine „Erkannt“-Karte, die Großansicht mit Fokusrückgabe in die richtige Gruppe.
  - „Ohne Namen“ läuft bis „Suche abgeschlossen“ und zeigt „Kein Gesicht ohne Namen.“. Das belegt die Auflistung im Image mit echtem Modell ohne Absturz.
- **Manuell an der Zielinstanz vor dem Merge (ein echtes Projekt mit Gesichtern):**
  - einige Gesichter zuordnen, eines davon zurücknehmen;
  - einen Klassifizierungslauf starten;
  - danach „Ohne Namen“ öffnen: Das zugeordnete Gesicht fehlt, das zurückgenommene steht wieder da, und erkannte Gesichter fehlen.
  - Stelle halten beim Nachladen in Chrome und Firefox.

### Bewusst nicht getestet

- **Ein Index, der nach einer Dateiänderung auf ein anderes Gesicht desselben Fotos zeigt** (ADR 0127 Punkt 4, akzeptiert). Geprüft sind nur der Fall „kein Gesicht mehr an dieser Stelle“ und dass Merkmal und Box aus einem Detektionslauf stammen.
- **Scroll Anchoring als Browserverhalten.** Geprüft ist allein seine Voraussetzung, die stabilen Schlüssel (oben unter `UnnamedFacesGroup`). Ob der Browser die Stelle hält, bleibt dem manuellen Blick an der Zielinstanz. Das Springen in Safari ≤ 26 hat UI/UX in Kauf genommen.
- **Die Dauer einer vollständigen Suche in einem großen Projekt.** Sie ist linear in der Fotozahl (ADR 0127). Geprüft ist, dass die Arbeit fotoweise auf dem Executor liegt und eine Zuordnung höchstens ein Foto wartet, nicht wie lange.
- **Ein eigenes Rate-Limit der Auflistung.** Es gibt keines (0292 S7). Die Last ist durch 24 Fotos je Aufruf und den Ein-Thread-Executor begrenzt, was geprüft ist.
- **Mehrere API-Prozesse.** Die Sperre gilt je Prozess. Der Wächter hält die Voraussetzung fest, geprüft wird sie nicht unter echter Mehrprozesslast.

### Offene Grenzen, ehrlich benannt

- **Übergang:** Gesichter aus Erkennungen vor der Migration stehen bis zum nächsten Klassifizierungslauf in „Ohne Namen“. Das ist geprüft (Tabelle „Menge je Foto“) und im Akzeptanzkriterium als Übergang ausgewiesen, nicht verdeckt.
- **Gefüllter Zustand von „Ohne Namen“** ist nur in Komponententests mit base64-Ausschnitten und im API-Test mit Fake-Analyzer belegt, nicht im Prüfstack.

## Entscheidungen

- **Im Refinement mit Daniel geklärt (2026-09-28):**
  - Benannt werden nur die beiden Nutzer; die Grenze von zwei Personen bleibt.
  - „Ohne Namen“ ist eine einzige Sammelgruppe; unbekannte Gesichter werden nie gruppiert, über sie wird nichts gespeichert.
  - Die Gruppe zeigt einzelne Gesichtsausschnitte statt ganzer Fotos, in Kenntnis der Suchdauer bei großen Projekten.
  - Reichweite je Projekt.
  - An der Obergrenze gezeigter Gesichter wird nur noch benannt, nicht mehr gelernt.
  - Ein gezeigtes Gesicht lässt sich in dieser Story zurücknehmen.
- **Von der Datenlage erzwungen, nicht gewählt:** Gesichter, die vor dieser Story gezeigt wurden, haben keinen Fotobezug und lassen sich nur durch Entfernen der Person loswerden. Erkennungen aus Läufen vor der Migration kennen ihr Gesicht nicht und stehen bis zum nächsten Klassifizierungslauf in „Ohne Namen“. „Kehrt nicht von selbst zurück“ gilt, solange die Bilddatei unverändert bleibt. Für keinen der drei Punkte gibt es eine Alternative, die nichts über Unbekannte speichert.
- **`architect` konsultiert (Schritt 1):** ADR 0127 (Gesichtsbezug als Box nur für festgelegte Personen, Rücknahme löscht die Referenz, eine Regel für „zugeordnetes Gesicht“, Auflistung auf Anfrage ohne Merkmal). Die Zuordnungs-Race schließt eine prozessweite Schreibsperre, zweite Linie ist das bedingte Setzen der Box; eine Sperre der Fotozeile entfällt, weil sie die projektübergreifende Obergrenze nicht abdeckt und unter SQLite nicht wirkt.
- **`ux-ui-designer` konsultiert (Schritt 2):** neue Projektseite mit Personengruppen und „Ohne Namen“ zuletzt, mitlaufende Statusleiste, Beschriftung der Aktion nach gebundenem Gesicht; Ergänzungen des Design-Systems folgen im Umsetzungs-PR.
- **`test-engineer` konsultiert (Schritt 3):** Akzeptanzkriterien auf Testbarkeit geschärft; `specs/architecture/0002-testkonzept.md` um eine Sektion zu Schreibsperre, Hintergrundsuche und nichts behaltendem Endpunkt ergänzt.
- **`security-engineer` konsultiert (Schritt 3):** S1–S12 und R1–R6 unten; `specs/architecture/0003-securitykonzept.md` im Personenabschnitt fortgeschrieben.
- **Priorität Hoch** (`requirements-engineer`-Konsultation im Refinement): senkt die Einstiegshürde, an der der Nutzen von 0292 und der Folge-Story #548 hängt.

## Offene Fragen

Keine.

## Out of Scope

- Gruppierung unbekannter Gesichter, mehr als zwei Personen, Namen für andere Menschen.
- Personenvorschläge oder Ähnlichkeitsangaben für Gesichter ohne Namen.
- Ein Abhaken fremder Gesichter („niemand von uns“).
- Eine projektübergreifende Übersicht.
- Zurücknehmen von Gesichtern, die vor dieser Story gezeigt wurden.
- Die Berücksichtigung der Personen im Auswahlvorschlag (#548).
