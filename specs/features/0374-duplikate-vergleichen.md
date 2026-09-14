# 0374 - Duplikate im Ausschuss vergleichen und einzeln entscheiden

**Status:** Accepted
**Erstellt:** 2026-09-14
**Bezug:** [Issue #374](https://github.com/TheRealKoller/photosort/issues/374), ADR [`0104`](../decisions/0104-ausschuss-entscheidung-uebersteuert-den-automaten.md)

**Umfang:** über dem Richtwert von rund 200 Zeilen. Grund: Der Abschnitt `## Security` führt zwölf
Auflagen in der geschützten Dreiteilung (was gilt, wofür, was bei Verletzung passiert). Diese
Story ist die erste, bei der eine Nutzerhandlung je Aufnahme mitbestimmt, welche Bilddaten den
Homeserver Richtung Cloud-Anbieter verlassen.

## Ziel

Beim Sichten des Ausschusses sind Duplikate heute nur als Textzeile erkennbar ("Duplikat von Foto
#123") — das Gegenstück ist eine Nummer, kein Bild. Wer entscheiden will, welche Aufnahme einer
Serie bleibt, muss die Fotos einzeln öffnen und im Kopf vergleichen. Bei Serienaufnahmen, die
Sekunden auseinanderliegen, ist das der häufigste Fall und der mühsamste.

Ziel ist, alle Aufnahmen einer Duplikat-Gruppe nebeneinander zu sehen und für jede einzeln zu
entscheiden, ob sie bleibt oder in den Ausschuss geht. Betrifft beide Nutzer und jedes Projekt, in
dem Serienaufnahmen vorkommen.

## User Story

Als Nutzer möchte ich beim Sichten des Ausschusses alle Aufnahmen einer Duplikat-Gruppe
nebeneinander sehen und je Aufnahme einzeln entscheiden, ob sie bleibt oder Ausschuss ist, damit
ich bei Serienaufnahmen die beste behalten kann, ohne die Fotos einzeln zu öffnen.

## Akzeptanzkriterien

- [ ] **AK1 — Erreichbarkeit und Gruppenbegriff.** Aus der Ausschuss-Sichtung ist zu einer Aufnahme
      mit `suggestion.reason === 'duplicate'` — und nur zu diesen — die Vergleichsansicht unter
      `/projects/:projectId/photos/:photoId/duplicates` erreichbar. Sie zeigt genau den Stern: den
      Repräsentanten (trägt selbst kein `duplicate_of`, kann ganz ohne Vorschlagszeile dastehen)
      und alle Aufnahmen, die auf ihn zeigen. Eine `photo_id`, auf die niemand zeigt und die selbst
      kein `duplicate_of` trägt, ergibt HTTP 404; eine `photo_id` aus einem fremden Projekt ergibt
      HTTP 404 ohne Hinweis darauf, dass es das Foto gibt.
- [ ] **AK2 — Gleichrangig.** Alle Mitglieder werden von derselben Kachelkomponente gerendert; kein
      Mitglied trägt eine Auszeichnung als Gewinner, Original oder Vorgeschlagener. Die
      Mitgliederreihenfolge ist `taken_at`, bei Gleichstand `id`; die Zusage gilt als vollständige
      Id-Folge, auch bei geschüttelter Einfügereihenfolge und bei durchgehend gleichem `taken_at`.
- [ ] **AK3 — Umbruch statt Verkleinerung.** Bei 360 px genau 2 Spalten, bei 1280 px genau 3; die
      beiden Zahlen müssen verschieden sein. Eine Gruppe mit 7 Mitgliedern rendert 7 Kacheln,
      paarweise gleich breit und mit Breite > 0, und die Kachelbreite bei 1280 px ist dieselbe wie
      bei einer Gruppe mit 3 Mitgliedern (Toleranz ≤ 1 px). Das letzte Paar *ist* die Zusage
      "bricht um, statt die Bilder kleiner zu machen" — ohne es ist sie unprüfbar.
- [ ] **AK4 — Einzelentscheidung.** Je Mitglied unabhängig `behalten` oder `Ausschuss`. "Alle
      behalten" und "alle verwerfen" sind zulässige Endzustände; es gibt keinen Gewinnerzwang. Ein
      wiederholtes Setzen überschreibt (danach genau eine Zeile, kein Konflikt- und kein
      Serverfehler); der Wechsel behalten → Ausschuss → behalten ist möglich. Eine Rücknahme nach
      "noch nicht entschieden" gibt es nicht, und die Ansicht bietet sie nicht an.
- [ ] **AK5 — Wirkung auf den Ausschuss.** `Ausschuss` wirkt unbedingt: Die Aufnahme überlebt den
      Ausschuss-Schritt nie, auch wenn gar kein Vorschlag vorlag. `behalten` wirkt **nur, solange
      die Aufnahme Duplikat-Verlierer ist** (`duplicate_of IS NOT NULL`) — es übersteuert die
      Duplikatablehnung und ausdrücklich **keine** Ablehnung aus einem anderen Grund. Eine wegen
      Unschärfe abgelehnte Aufnahme bleibt abgelehnt, auch mit `behalten`; das gilt namentlich für
      den Repräsentanten, der nie ein `duplicate_of` trägt. Ohne Zeile entscheidet weiterhin allein
      `suggested_status`. Eine entschiedene Aufnahme ist kein offener Vorschlag mehr: Sie
      verschwindet aus `rating_status=suggested`, aus der Vorschlagsanzeige am Foto und aus der
      Zählung des Ausschuss-Gates. **"Überlebender" und "offener Vorschlag" sind dabei nicht
      komplementär** — eine mit `Ausschuss` entschiedene Aufnahme ist weder das eine noch das
      andere.
- [ ] **AK6 — Zustand ohne Farbwahrnehmung.** Die drei Zustände sind je Kachel paarweise
      verschieden in (a) sichtbarem Beschriftungstext, (b) `data-duplicate-decision`
      (`keep`/`discard`/`undecided`), (c) `data-icon`. Bei `Ausschuss` trägt die Bildfläche in der
      Übersicht zusätzlich `data-dimmed="true"`, überall sonst `data-dimmed="false"`. Die
      tatsächliche Dämpfung hängt an genau einem `opacity-*`-Vorkommen an der Bildfläche, nie am
      Kachelkörper.
- [ ] **AK7 — Vergrößern und Verkleinern.** Die Kachel ist ein natives `<button>`, dessen
      zugänglicher Name die Aktion nennt ("… vergrößern" / "… verkleinern"). Antippen vergrößert,
      erneutes Antippen verkleinert; Enter und Leertaste tun dasselbe; Esc verkleinert; zusätzlich
      existiert ein sichtbares Schließen-Element mit eigenem zugänglichen Namen. Die
      Hover-Ankündigung am Zeigegerät ist reines CSS und wird ausdrücklich **nicht** automatisiert
      geprüft (jsdom berechnet keinen `:hover`); zugesichert und geprüft ist stattdessen, dass kein
      eigenes `onClick`/`onKeyDown` das native Element ersetzt.
- [ ] **AK8 — In der Vergrößerung.** Zu jedem Zeitpunkt ist höchstens ein Mitglied vergrößert, und
      alle n Mitglieder bleiben im Dokument. Eine Entscheidung in der Vergrößerung ändert den
      Zustand, hebt die Vergrößerung nicht auf und blättert nicht weiter. Pfeil links/rechts sowie
      Vor/Zurück verschieben die Vergrößerung auf das benachbarte Mitglied, ohne zu verkleinern; am
      ersten bzw. letzten Mitglied bleibt sie stehen (kein Rundlauf), und die jeweilige Schaltfläche
      ist dort als nicht verfügbar ausgewiesen. Das vergrößerte Bild wird ungedämpft gezeigt, trägt
      aber unverändert `data-duplicate-decision`. Geometrie: Die vergrößerte Kachel spannt die volle
      Rasterbreite, und bei ≥ 4 Mitgliedern ist mindestens ein weiteres Mitglied ober- **und**
      unterhalb im Sichtbereich.
- [ ] **AK9 — Gruppenweite Abkürzungen.** "Alle behalten" und "alle in den Ausschuss" setzen alle n
      Mitglieder in **genau einem** Aufruf; die Menge bestimmt der Server aus dem Stern, der Body
      trägt ausschließlich die Entscheidung. Danach trägt jedes Mitglied denselben Zustand, auch
      jene, die vorher einzeln anders entschieden waren. Ein anschließender Einzelaufruf übersteuert
      nur dieses eine Mitglied.
- [ ] **AK10 — Gruppenzähler.** Die Ansicht nennt `position` und `total` als "Duplikat-Gruppe
      {position} von {total}", 1-basiert, mit `1 ≤ position ≤ total`. Bezugsmenge sind die **noch
      offenen** Gruppen: Eine Gruppe, in der jedes Mitglied entschieden ist, zählt nicht mehr mit.
      Der Zähler beschreibt damit die verbleibende Arbeit und läuft auf null zu; dass `position`
      sich verschiebt, sobald eine Gruppe abgeschlossen wird, ist die bewusst getragene Folge. Die
      Gruppenreihenfolge ist der früheste `taken_at` der Mitglieder, bei Gleichstand die
      Repräsentanten-Id — als vollständige Folge zugesichert.
- [ ] **AK11 — Was ohne Entscheidung geschieht.** Die Ansicht trägt eine unveränderliche
      Hinweiszeile, die aussagt, dass ohne Entscheidung der Vorschlag des Systems gilt. Sie sagt
      **nicht** zu, dass unentschiedene Aufnahmen erhalten bleiben — ein unentschiedener
      Duplikat-Verlierer trägt weiter `suggested_status = REJECTED` und fällt am Gate heraus. Die
      Vergleichsansicht verwirft von sich aus nichts; sie ändert nur, was der Nutzer ausdrücklich
      entscheidet.
- [ ] **AK12 — Überlebt den erneuten Lauf.** `run_project_scoring` setzt `duplicate_of`,
      `cluster_key` und `suggested_status` zurück und fasst `photo_duplicate_decisions` nicht an.
      Jede Entscheidung gilt danach unverändert weiter — auch dann, wenn die Aufnahme nach dem neuen
      Lauf in einer anderen Gruppe oder in gar keiner Gruppe mehr liegt. Ein `behalten` wird dabei
      von selbst wirkungslos, sobald die Aufnahme kein Duplikat-Verlierer mehr ist (AK5); ein
      `Ausschuss` wirkt weiter.
- [ ] **AK13 — Abgrenzung.** Für Vorschläge wegen geringer Bildqualität ändert sich nichts: kein
      Einstieg an der Kachel, und der Lese-Endpunkt antwortet 404.
- [ ] **AK14 — Das Gate bleibt.** Das Ausschuss-Gate behält genau eine Abschluss-Aktion und keine
      Einzelbestätigungspflicht. Die einzige beabsichtigte Änderung an ihm ist, dass sein Inhalt und
      seine Zahl um die entschiedenen Aufnahmen schrumpfen.
- [ ] **AK15 — Zustände der Seite.** Ladend (Skelette), gefüllt, Fehler (Alert), leer. HTTP 404
      rendert den **leeren** Zustand mit eigener Aussage, nicht den Fehler-Alert; jeder andere
      Fehler den Alert. Nach jeder Entscheidung werden die Gruppenabfrage, die Fotoliste (Filter
      `suggested`) und die Gate-Zählung invalidiert.

## Datenmodell-Bezug

Neue Tabelle `photo_duplicate_decisions` mit `photo_id` als Primär- und Fremdschlüssel auf
`photos.id` und der Spalte `decision` (`DuplicateDecision`: `keep`, `discard`), `NOT NULL`, ohne
Vorgabewert. Abwesenheit der Zeile heißt "noch nicht entschieden". Kein `user_id` — die Entscheidung
ist projektweit. Bauart nach dem Muster von `final_selection_decisions`. Die Duplikat-Gruppe selbst
bekommt **keine** eigene Entität; sie bleibt ein zur Lesezeit gebildeter Stern über
`PhotoScore.duplicate_of`. Nachzuziehen in [`docs/architecture.md`](../../docs/architecture.md):
Datenmodell-Skizze, die Beschreibung des Ausschuss-Überlebender-Bestands und der neue
Endpunktblock.

## Architektur / Umsetzung

### Gruppenbildung — abgeleitet, nicht gespeichert

Die Duplikat-Gruppe ist ein **Stern über `PhotoScore.duplicate_of`** und wird zur Lesezeit gebildet;
die Erkennung bleibt unangetastet. `scoring.py::assign_duplicate_clusters` bildet Cluster per
Union-Find und schreibt `duplicate_of` nur für die Verlierer, jeweils auf den Gewinner; der Gewinner
trägt `NULL`, Ketten sind ausgeschlossen. Repräsentant einer Gruppe ist der Gewinner. Zu einem Foto
`P` des Projekts:

- `P.duplicate_of = W` → Repräsentant ist `W`;
- sonst ist `P` selbst Repräsentant, sofern mindestens ein Foto auf ihn zeigt;
- Gruppe = `{Repräsentant} ∪ {x : x.duplicate_of = Repräsentant}`, jeweils mit
  `Photo.project_id == project_id` ausgeschrieben.

Zeigt niemand auf `P` und trägt `P` selbst kein `duplicate_of`, gibt es keine Gruppe → `404`. Das
ist zugleich die Durchsetzung von "nur für als Duplikat erkannte Aufnahmen".

`PhotoScore.cluster_key` ist **nicht** die Gruppe (Zeit-/Ortscluster der Ausschuss-Überlebenden) und
wird hier nirgends gelesen.

### Die Entscheidung je Aufnahme

Neue Tabelle `photo_duplicate_decisions` (siehe Datenmodell-Bezug) mit

    class DuplicateDecision(enum.StrEnum):
        KEEP = "keep"
        DISCARD = "discard"

`DISCARD` und nicht `rejected`: `RatingStatus.REJECTED` ist die Albumentscheidung eines Nutzers. Die
Entscheidung hier sagt, ob die Aufnahme den Ausschuss-Schritt überlebt — eine andere Frage auf einer
anderen Ebene. Die Vergleichsansicht schreibt deshalb **keine** `Rating`-Zeile und erzeugt kein
Ereignis der Nacharbeit.

Projektweit statt je Nutzer: Was nach dem Ausschuss weiterläuft, ist ein Projektvorgang
(Kriterien-Lauf, Cloud-Klassifizierung). Zwei nutzereigene Antworten darauf wären zwei
widersprüchliche Wahrheiten über denselben Bestand.

### Der Ausschuss-Überlebender-Bestand bekommt eine Stelle

Bisher steht `PhotoScore.suggested_status IS NULL` an sechs Stellen ausgeschrieben. Neu: **ein**
Prädikat in `backend/src/photosort/duplicates.py`, das alle sechs verwenden —

    DISCARD überlebt nie · KEEP überlebt, solange duplicate_of IS NOT NULL ·
    sonst entscheidet suggested_status

als korrelierte Skalar-Unterabfrage, damit keine Aufrufstelle eine Join-Buchführung erbt. Betroffen:
`worker.py` (Kriterien-Lauf, Remote-Kandidaten), `api/projects.py` (Schätzung, Kandidatenzahl),
`api/photos.py` (`is_candidate`, `_filtered_photo_ids`-Zweig `SUGGESTED`, `has_suggestion`).

Die Asymmetrie zwischen `KEEP` und `DISCARD` ist kein Versehen: Sie hält die Entscheidung an die
Frage gebunden, auf die der Nutzer geantwortet hat, und lässt eine verwaiste `KEEP`-Zeile von selbst
wirkungslos werden, wenn die Gruppe zerfällt — ohne Aufräumlauf und ohne eigene Oberfläche.

**Überleben eines erneuten Laufs** folgt ohne durchsetzenden Code: `run_project_scoring` setzt
`duplicate_of`/`cluster_key`/`suggested_status` zurück, fasst `photo_duplicate_decisions` aber nicht
an. Ein Verhaltensfall sichert das ab.

### Endpunkte

- `GET /projects/{project_id}/duplicate-groups/{photo_id}` → `DuplicateGroupOut` mit
  `items: list[DuplicateGroupPhotoOut]` (je Eintrag `photo: PhotoOut` und
  `decision: DuplicateDecision | null`), `position` (1-basiert) und `total` (Zahl der **noch
  offenen** Gruppen im Projekt, AK10). Sortierung der Gruppen: frühester `taken_at` der Mitglieder,
  Gleichstand nach Repräsentanten-Id; Mitglieder nach `taken_at`, `id`. `PhotoOut` wird
  **wiederverwendet und nicht erweitert** — die Entscheidung hat außerhalb dieser Ansicht keine
  Rolle und stünde sonst als Feld auf jedem Lesepfad.
- `PUT /projects/{project_id}/photos/{photo_id}/duplicate-decision` — eine Aufnahme.
- `PUT /projects/{project_id}/duplicate-groups/{photo_id}/decision` — die ganze Gruppe, atomar.

Beide Schreibwege tragen als Body ausschließlich `{"decision": "keep"|"discard"}`; **keine Id-Liste
aus dem Body**, die Menge bestimmt der Server aus dem Stern. Beide antworten mit derselben
`DuplicateGroupOut`-Form wie der Lesepfad. `photo_id` deklarativ begrenzt
(`ge=1, le=_MAX_QUERY_POSITION`), Projektbindung als ausgeschriebenes Prädikat in jeder Abfrage. Eine
Rücknahme nach "noch nicht entschieden" gibt es nicht; ändern heißt den anderen Wert schreiben.

Die beiden Schreibendpunkte liegen in einem **eigenen Router** mit
`dependencies=[Depends(get_current_user)]` (Muster `api/album_decisions.py`), siehe S8. Der
Lesepfad braucht die Hydratation aus `api/photos.py` (`_photos_by_id`, `_to_photo_out` samt Event-,
Orts- und Rang-Kontext).

### Betroffene Dateien

**Backend** — `models.py` (`DuplicateDecision`, `PhotoDuplicateDecision`); neue
Alembic-Migration samt Migrationstest; `duplicates.py` (neu: Sternabfrage, Gruppenreihenfolge,
Überlebenden-Prädikat); `api/photos.py` (Lesepfad, `_filtered_photo_ids`, `has_suggestion`,
`is_candidate`); neuer Router für die beiden Schreibwege; `worker.py` und `api/projects.py`
(Umstellung auf das gemeinsame Prädikat); `project_deletion.py`; `demo_state.py` (eine
Duplikat-Gruppe im Demo-Bestand).

**Frontend** — `api/types.ts`, `api/duplicates.ts`, `hooks/useDuplicates.ts` (Query-Schlüssel
`['photos', projectId, 'duplicates', photoId]`, damit die bestehende breite Invalidierung greift);
`pages/DuplicateComparePage.tsx`; `components/DuplicatePhotoTile.tsx` — ausdrücklich **nicht**
`CurationPhotoTile`/`SelectionPhotoTile` und **nicht** `RatingBadge`, deren Vokabular ist die
Albumentscheidung; `utils/projectRoutes.ts` + `App.tsx` (Route
`/projects/:projectId/photos/:photoId/duplicates`, aufgenommen in die `activeRoutePaths` des Ziels
"Fotos"); `pages/PhotoGridPage.tsx` (Einstieg im Kachel-Fuß, nur bei
`photo.suggestion?.reason === 'duplicate'`).

Die Vergrößerung ist **kein Dialog**: Die übrige Gruppe bleibt sichtbar, die vergrößerte Kachel
spannt die Rasterbreite, zeigt das Bild ungedämpft, trägt denselben Zustandsrahmen und führt
Verkleinern sowie Vor/Zurück innerhalb der Gruppe als sichtbare Bedienelemente.

**Design** — `design/penpot/views.json`: `produktdateien` der Ansicht `duplikate` füllen.

### Reihenfolge der Umsetzung

1. Modell + Migration **samt Projektlöschung**. Beides gehört zusammen: Sobald die neue Tabelle
   über ihren Fremdschlüssel aus `Base.metadata` erreichbar ist, wird
   `test_project_deletion.py::test_delete_projects_covers_every_table_reachable_from_projects`
   sofort rot. Getrennt wäre die Suite über fünf TDD-Einheiten hinweg rot und `scripts/check.sh`
   verlöre seine Aussage.
2. Sternabfrage und Gruppenreihenfolge in `duplicates.py` (Repräsentant ohne eigene Vorschlagszeile,
   Projektgrenze, Foto ohne Gruppe).
3. Überlebenden-Prädikat, Umstellung aller sechs Stellen, Parität SQL ↔ Objektfassung.
4. Lese-Endpunkt (Gruppe, `position`, `total`, `404`-Fälle, Projektgrenze).
5. Beide Schreib-Endpunkte im eigenen Router; Verhaltensfälle "überlebt erneuten Lauf" und
   "veraltete Entscheidung".
6. Demo-Bestand.
7. Frontend: Typen, Client, Hook.
8. Frontend: Kachel (drei Zustände über Rahmen, Beschriftung und Dämpfung).
9. Frontend: Seite (Raster/Umbruch, Vergrößerung, Abkürzungen, Zähler, leer/ladend/fehler).
10. Route und Einstieg aus der Ausschuss-Sichtung.
11. `views.json` nachziehen, `npx vitest run penpot/payload.test.ts`.
12. `docs/architecture.md` und `specs/architecture/0003-securitykonzept.md` nachziehen.

## UI/UX

**Stand:** ausgearbeitet
**Penpot-Seite:** Ansicht — Duplikate vergleichen
**Schlüssel:** duplikate

Offener Punkt der Entwurfsdatei: Das Feld `produktdateien` der Ansicht ist leer und wird im
Umsetzungslauf gefüllt (Schritt 11).

### Ablauf und Layout

Die Ansicht zeigt alle Aufnahmen einer Gruppe in einem Raster — drei Spalten breit, zwei schmal —
und bricht bei mehr Mitgliedern in weitere Zeilen um, statt die Bilder zu verkleinern. Jede Kachel
trägt Bildfläche, Dateiname, Zustandskennzeichen und die Wahlzeile (behalten / Ausschuss). Oben
steht der Gruppenzähler "Duplikat-Gruppe {position} von {total}" als Seitenüberschrift, darunter die
Hinweiszeile aus AK11. Die gruppenweiten Abkürzungen sind beschriftete Schaltflächen, keine Symbole.

Die Vergrößerung ist eine Inline-Transformation, kein Dialog: Die gewählte Kachel spannt die
Rasterbreite, die übrigen Kacheln bleiben darüber und darunter stehen. Das Bild wird dort
unverfälscht gezeigt, die Entscheidung ist auch dort möglich, und Vor/Zurück blättert innerhalb der
Gruppe, ohne zu verkleinern.

### Zustände

`gefuellt`, `vergroessert`, `leer` (keine offenen Duplikat-Gruppen mehr zu sichten — nach AK10
erreichbar, weil der Zähler nur offene Gruppen führt), `ladend` (Skelette, ruhend), `fehler`
(Alert). Bausteine: `button`, `badge`, `alert`, `skeleton`, `progress`.

### Zustand ohne Farbwahrnehmung

Drei Ausprägungen, jede mehrfach codiert über Umriss, Beschriftung und Symbol:

- **noch nicht entschieden** — Umriss in `--border-control`. Dieser Umriss hält den Kontrastwert für
  grafische Elemente **bewusst nicht ein**: Er ist der Ruhezustand und nicht der Träger der Aussage.
  Dass nichts entschieden ist, zeigt die Abwesenheit einer Auszeichnung; die Aussage selbst trägt
  das Kennzeichen im Text. Ein angehobener Umriss ließe Unbearbeitetes auffälliger erscheinen als
  Entschiedenes.
- **behalten** — Umriss in `--accent` (#ffb000), stärker als im Ruhezustand, plus Kennzeichen.
- **Ausschuss** — Umriss in `--danger` (#ff3d00), Beschriftung in `--danger-text` (#ff5a26), plus
  gedämpfte Bildfläche. **Die Dämpfung gilt ausschließlich in der Übersicht.** Die vergrößerte
  Aufnahme bleibt unverfälscht, weil sie beurteilt werden soll; Kennzeichen, Dateiname und Umriss
  bleiben in beiden Fällen voll deckend, damit der Zustand ohne Farbwahrnehmung lesbar ist.

### Barrierefreiheit

Die Kachel ist ein natives `<button>` — Enter und Leertaste wirken ohne eigenen Tastatur-Handler,
Esc verkleinert, und ein sichtbares Schließen-Element bleibt zusätzlich bestehen. Fokusmarkierung
nach Design-System (`outline: 2px solid var(--accent)`, 2 px Offset), Fokusreihenfolge zeilenweise;
beim Vergrößern wandert der Fokus auf den Rückweg. Kein eigenes Tastenkürzelschema.

### Lücken ohne Token im Satz

Umrissstärke, Dämpfungsgrad, Spaltenzahl und die daraus folgenden Kartenmaße führt der Tokensatz
nicht; sie stehen im Entwurf als Werte. Bewegung (der Puls der Ladeplatzhalter) bildet Penpot nicht
ab, der Satz führt kein Token dafür — der Entwurf zeigt die Platzhalter ruhend. Karte und
Großbildrahmen sind tokengebundene Rahmen statt Bibliotheks-Instanzen, weil die Bibliothek keinen
Behälter-Baustein führt.

## Security

Kein neues Secret, keine neue Umgebungsvariable, kein neuer externer Dienst, kein Freitext aus einer
fremden Quelle und keine neue Sicherheitsgrenze. Neu ist etwas anderes: Eine Nutzerhandlung bestimmt
erstmals **je Aufnahme** mit, welche Bilddaten den Homeserver Richtung Cloud-Anbieter verlassen.
Bisher entschied das allein der Automat, gedeckelt durch den projektweiten Einwilligungsschalter.
Einstufung: **sicherheitsrelevant**.

### Die Grenze des Homeservers

- **S1 — Das Prädikat steht an vier cloud-bestimmenden Abfragen, nicht an einer.** Dasselbe Prädikat
  begrenzt in `worker.py::run_criterion_scoring` (die Foto-Auswahl des Laufs, die zugleich den
  Sehenswürdigkeits-Teilschritt speist), in `worker.py::select_remote_category_candidates`, in
  `api/projects.py::_count_remote_category_candidates` und in
  `api/projects.py::_count_landmark_candidates`, welche Fotos an einen Cloud-Anbieter gehen. Die
  beiden Zählungen sind die Kostenschätzung, auf der die Freigabe eines kostenpflichtigen Laufs
  beruht; sie folgen der Auswahl nicht von selbst, sondern sind eigene Anweisungen. Für **beide**
  Cloud-Teilschritte gilt: Die Schätzung zählt dieselbe Menge, die der Lauf sendet, geprüft als
  Mengengleichheit über demselben Datenbestand, nicht als zwei getrennt hingeschriebene
  Erwartungswerte. Untersagte Alternative ist die naheliegende Teilumsetzung — das Prädikat in die
  Lesepfade der Oberfläche zu legen und eine der vier Stellen beim alten `suggested_status IS NULL`
  zu belassen. Bei Verletzung verlassen verworfene Aufnahmen den Homeserver, behaltene fehlen in der
  Bewertung, und die Schätzung nennt eine andere Zahl als der Lauf sendet — ohne Fehler, ohne
  Meldung, sichtbar erst an der Abrechnung des Anbieters. Der fünfte Ort
  (`api/photos.py::_cloud_vision_status_out`, `is_candidate`) trägt dieselbe Bedingung, ist aber
  Anzeige und keine Grenze.
- **S2 — Die Form des Prädikats ist fail-closed.** Drei Festlegungen, jede einzeln tragend: Überleben
  wird **positiv auf `keep`** geprüft, nie negativ auf `discard` — die Spalte ist Zeichenkette, der
  Wertevorrat wird von der Datenbank nicht erzwungen, und ein unerwarteter Wert muss zur
  zurückhaltenden Seite fallen, nicht zum Abfluss. Der Fall "keine Zeile" ist ein ausdrückliches
  `IS NULL` auf die Unterabfrage, nie ein Ungleichheitsvergleich: `<Unterabfrage> != 'discard'` ergibt
  bei fehlender Zeile `NULL`, und die Auswahl liefert dann den leeren Bestand. Der innere Join auf
  `PhotoScore` bleibt ein innerer Join, und das Prädikat tritt als weiterer Konjunktionsteil **in
  dieselbe Anweisung**; ein Umbau auf einen Outer Join oder auf eine vorgeschaltete Auflösung macht
  das Gate zu einem nachgelagerten Filter über einer bereits gebildeten Menge und ist untersagt.
- **S3 — `keep` ist an die Duplikatfrage gebunden, `discard` nicht.** `suggested_status = REJECTED`
  trägt zwei Gründe: Duplikat-Verlierer *und* Unschärfe unterhalb `SHARPNESS_REJECT_THRESHOLD`
  (`duplicate_of` bleibt dort `NULL`). `keep` wirkt deshalb nur bei `duplicate_of IS NOT NULL` —
  sonst höbe eine Antwort auf die Duplikatfrage eine Ablehnung auf, zu der der Nutzer nie befragt
  wurde. `discard` wirkt unbedingt; das ist die Richtung, die den abfließenden Bestand verkleinert.
  Bei Verletzung entsteht eine dauerhafte, unsichtbare Ausnahme vom Ausschuss-Gate: Zerfällt die
  Gruppe (Repräsentant gelöscht, Hash geändert), antwortet die Vergleichsansicht `404`, die Zeile ist
  weder sichtbar noch widerrufbar, und die Aufnahme geht bei jedem künftigen Lauf erneut an den
  Anbieter.
- **S4 — Die Vergleichsansicht benennt die Folge.** "Behalten" ist keine ansichtsinterne
  Buchführung: Die Aufnahme läuft in die Kriterien-Bewertung und, bei erteilter Einwilligung, in die
  Cloud-Klassifizierung. Steht das nicht an der Handlung, trifft der Nutzer eine Entscheidung über
  einen Datenabfluss, von dem er nichts weiß.

### Die drei Endpunkte

- **S5 — Der gruppenweite Schreibweg darf nie auf einem `NULL`-Repräsentanten stehen.** Der
  Repräsentant wird zuerst aufgelöst; gibt es keine Gruppe, ist die Antwort `404`, **bevor**
  geschrieben wird. Ein `None` als Vergleichswert des Gruppenprädikats wird in SQLAlchemy zu
  `duplicate_of IS NULL` und trifft damit jede nicht aussortierte Aufnahme des Projekts: Ein Klick
  schriebe `discard` oder `keep` auf den gesamten Bestand — im einen Fall verschwindet das Projekt
  aus Bewertung und Album, im anderen geht es vollständig an den Cloud-Anbieter. Die Gruppengröße
  ist die Verstärkung dieses einen Schreibwegs und der Grund, warum er schärfer ist als der
  einzelne.
- **S6 — Kein Id-Vorrat im Körper.** Der Körper trägt genau ein Feld (`decision`), geprüft als
  Feldmenge auf Gleichheit; eine mitgeschickte Id-Liste, `photo_id` oder `user_id` wird nicht
  gelesen. Eine vom Aufrufer gelieferte Menge wäre ein Massen-Schreibweg auf beliebige Fotos.
  `project_id` und `photo_id` sind deklarativ begrenzt (`ge=1, le=_MAX_QUERY_POSITION`) — ein
  unbeschränkter Pydantic-`int` erreicht die Datenbank und wird jenseits von 2^63 zu `500` statt
  `404`.
- **S7 — Die Projektbindung steht ausgeschrieben in jeder Abfrage**, die eine Id auflöst: beim
  Repräsentanten, bei der Gruppenbildung und bei jeder geschriebenen Zeile, nie als nachgelagerte
  Prüfung über einer bereits gebildeten Menge. `photo_scores.duplicate_of` zeigt auf `photos.id`
  ohne Projektbedingung; ohne das ausgeschriebene Prädikat entscheidet eine Aufnahme des einen
  Projekts über den abfließenden Bestand eines anderen. Ein Treffer aus einem fremden Projekt ist
  ein `404`, das den Wert nicht spiegelt und von einer unbekannten Id nicht unterscheidbar ist.
- **S8 — Authentifizierung, dreifach gesichert.** Beide Schreibendpunkte nehmen kein `current_user`
  entgegen; ihr Fehlen fiele an der Signatur nicht auf. Sie gehören deshalb in einen eigenen Router
  mit `dependencies=[Depends(get_current_user)]` (Muster `api/album_decisions.py`), bekommen einen
  Eintrag in `tests/test_auth_guard.py::_protected_router_operations()` und je einen eigenen,
  pfadbenannten 401-Fall. Liegt einer von ihnen stattdessen in `photos.router`, greift von den
  dreien nur der 401-Fall: Dieser Router trägt keine Dependency-Liste und keinen
  Vollständigkeitstest, ein vergessener Torwächter ist dort still öffentlich — ein
  unauthentifizierter Schreibzugriff, der bestimmt, welche Bilder den Homeserver verlassen.
- **S9 — Der gruppenweite Weg ist eine Transaktion**, ein `commit` über alle Zeilen. Eine halb
  entschiedene Gruppe wäre eine willkürliche Teilmenge im abfließenden Bestand, ohne dass ein
  Lesepfad den Zwischenzustand als solchen erkennt. Der Primärschlüssel ist `photo_id`: Ein
  gleichzeitiger Schreibzugriff beider Nutzer auf dieselbe Aufnahme wird `409`, nie `500`.
- **S10 — Die Antwort des Lesepfads ist eine Funktion des anfragenden Nutzers.** Sie trägt `PhotoOut`
  und damit `suggestion`/`ratings`; bekommt sie je eine Zwischenspeicherung, ein `ETag` oder ein
  `Cache-Control` über `no-store` hinaus, muss der Schlüssel den Nutzer enthalten. Damit gilt die
  Auflage von `api/photos.py::_to_photo_out` unverändert für einen vierten Endpunkt.

### Datenmodell und Migration

- **S11 —** `photo_id` ist Primär- und Fremdschlüssel mit **ausgeschriebenem** Constraint-Namen
  (`Base.metadata` trägt keine `naming_convention`; ein unbenannter Fremdschlüssel ist unter SQLite
  im Rückwärtsweg nicht droppbar). Der echte Fremdschlüssel ist Pflicht: Die Löschzusage in
  `project_deletion.py` prüft Erreichbarkeit über die Kanten in `Base.metadata`, eine bloß logische
  Spalte fiele still aus der Prüfung. Die Tabelle wird dort in
  `reversed(Base.metadata.sorted_tables)`-Reihenfolge vor `photos` eingetragen; der
  Vollständigkeitswächter fängt ein Vergessen.
- **S12 —** `decision` ist `NOT NULL` **ohne** Python- und ohne `server_default`. Abwesenheit der
  Zeile heißt "nicht entschieden"; ein Vorgabewert erfände eine Entscheidung, die niemand getroffen
  hat — und diese Entscheidung bestimmt, was den Homeserver verlässt.

### Projektweite Reichweite ohne `user_id` — tragbar

Die Zeile kennt keinen Nutzer, Nutzer A überschreibt eine Entscheidung von Nutzer B spurlos. Das ist
im Bedrohungsmodell gedeckt: Schutz der beiden legitimen Nutzer gegeneinander ist ausdrücklich kein
Ziel, und dieselbe Reichweite tragen bereits `final_selection_decisions` und der projektweite
Cloud-Einwilligungsschalter. Die klassische BOLA-Falle entfällt hier von selbst, weil es kein
Nutzerfeld gibt, das aus dem Körper stammen könnte (S6).

### Bewusst akzeptierte Restrisiken

- **Keine Deckelung der `keep`-Menge und keine zweite Bestätigung.** Ein gruppenweites "behalten"
  kann in einem Klick zweistellig viele Aufnahmen zu Cloud-Kandidaten machen. Getragen wird das von
  den bestehenden Schranken und keiner weiteren: Die Einwilligung steht auf `False`, solange sie
  niemand setzt, und die Vorab-Kostenschätzung benutzt dieselben Auswahlfunktionen und zeigt den
  Sprung deshalb an, bevor ein Lauf startet. S1 ist damit die Bedingung, unter der dieses Restrisiko
  tragbar bleibt.
- **Ein verwaistes `discard` ist unerreichbar.** Zerfällt die Gruppe, bleibt die Aufnahme dauerhaft
  aus dem Bestand, ohne Weg zurück über die Vergleichsansicht. Die Richtung ist fail-closed — nichts
  verlässt den Homeserver, der Verlust ist Bedienbarkeit, nicht Sicherheit. Für die Gegenrichtung
  gilt das nicht; sie ist über S3 aufgelöst.
- **Kein neuer XSS-Sink.** Die Ansicht zeigt Datei- und Ordnernamen aus OpenCloud wie die bestehende
  Fotoliste; der Körper der beiden Schreibwege trägt keinen Freitext.

Nachzuziehen in [`specs/architecture/0003-securitykonzept.md`](../architecture/0003-securitykonzept.md):
zwei Zeilen in der Ankerliste (S1, S5), ein Abschnitt unter Angriffsflächen, und ein Halbsatz an der
Cloud-Vertrauensgrenze.

## Teststrategie

**Ebenen.** *Unit:* Sternbildung und Gruppenreihenfolge als reine Funktionen, parametriert über
`n ∈ {1, 2, 3, 5}` — der entartete Fall `n = 1` ist der trennende, er darf **keine** Gruppe ergeben
und deckt sowohl ein hartkodiertes "mindestens zwei" als auch ein Mitzählen des Repräsentanten auf.
Dazu die Wahrheitstabelle des Überlebenden-Prädikats als `parametrize` über alle Kombinationen aus
`{keine Zeile, keep, discard}`, `{suggested_status NULL, gesetzt}` und
`{duplicate_of NULL, gesetzt}` — die dritte Achse trägt S3. *Integration (Schwerpunkt):* alle drei
Endpunkte, die sechs umgestellten Stellen, `run_project_scoring`, Projektlöschung, Demo-Bestand;
Frontend die Seite mit `MemoryRouter` + `QueryClientProvider` und gemocktem API-Modul. *E2E:* nur,
was jsdom prinzipiell nicht kann — AK3 und die Geometrie-Hälfte von AK8; die bestehenden Specs
`grid-columns`, `no-horizontal-scroll` und `tap-targets` werden erweitert, kein neuer Spec.
Rot-Nachweis für die neuen Layout-Zusagen gehört in den PR.

**Die sechs Umstellungsstellen.** Je Stelle ein Fall, der nur über sie hineinkommt, plus Gegenprobe.
Die cloud-bestimmenden Stellen bekommen **beide Richtungen ausdrücklich**: `keep` macht eine zuvor
aussortierte Aufnahme zur Kandidatin, `discard` nimmt eine zuvor kandidierende heraus. Ohne die
zweite Richtung bestünde jeder Fall auch gegen ein Prädikat, das schlicht alles durchlässt.

**Nicht komplementär.** Der bestehende Paritätstest wird **erweitert, nicht ersetzt**, und trägt
beide Mengen in *einem* Fall: dieselbe Fotomenge über `rating_status=suggested`, über
`suggestion != null` und über die Überlebendenmenge. Eine Umsetzung, die "offener Vorschlag" als
`NOT überlebt` schreibt, liefert sonst plausible, falsche Listen, und das fällt nur nebeneinander
auf.

**S3 in beiden Richtungen.** `keep` auf ein Mitglied mit `duplicate_of IS NOT NULL` wirkt; `keep` auf
eine wegen Unschärfe abgelehnte Aufnahme ohne `duplicate_of` — namentlich den Repräsentanten — wirkt
**nicht**; `discard` auf eine Aufnahme mit `suggested_status IS NULL` wirkt. Getrennt geschrieben
bestünde jede Hälfte auch gegen eine Umsetzung, die immer oder nie übersteuert.

**Der erneute Lauf, zwei Fälle.** (1) Entscheidung überlebt einen unveränderten Neulauf. (2) Die
veraltete Entscheidung: Nach einem Neulauf, in dem die Aufnahme kein Duplikat mehr ist, wirkt ein
altes `discard` weiter und entfernt sie dauerhaft aus dem Überlebendenbestand, während ein altes
`keep` von selbst wirkungslos wird (S3). Beides ist Folge der Architektur und wird festgeschrieben,
damit es nicht als Bug wiederentdeckt wird.

**Projektgrenze, scharfe Form.** Nicht nur "fremdes Foto → 404", sondern: Ein Foto in Projekt B,
dessen `duplicate_of` auf ein Foto in Projekt A zeigt, darf in der Gruppe von Projekt A **nicht**
erscheinen. Nur diese Datenlage deckt ein fehlendes `Photo.project_id`-Prädikat auf; der bloße
404-Fall besteht auch ohne es.

**Schreibwege.** Wiederholtes `PUT` überschreibt (Primärschlüssel `photo_id` — ein naives `INSERT`
läuft in `IntegrityError` und damit in eine 500); Gruppen-`PUT` nach Einzel-`PUT` setzt alle gleich;
Einzel-`PUT` nach Gruppen-`PUT` übersteuert genau eins. Der Gruppenweg schreibt in *einer*
Transaktion und antwortet in derselben Form wie der Leseweg — geprüft über die Gleichheit der
Antwortstruktur beider Wege in einem Fall. Eingabegrenzen: `photo_id` = 0, negativ und oberhalb
`_MAX_QUERY_POSITION` ergeben 422.

**Register, die einen neuen Endpunkt oder eine neue Route still übergehen** — jedes einzeln, sonst
fällt die Zusage lautlos aus: `test_openapi_beschreibungen.py::DOCUMENTED_ROUTES`;
`test_auth_guard.py` (S8); `projectRoutes.ts` (`PROJECT_ROUTE_PATHS` wächst von 9 auf 10, die Zahl
steht literal im Test, und `resolveActiveNavTargetId` muss die Route dem Ziel "Fotos" zuordnen —
eine unregistrierte Route markiert still *kein* Ziel aktiv); `designSystem.contract.test.ts`
(`OPACITY_ALLOWLIST` braucht eine fundstellengenaue Freigabe, die zeigt, dass die Dämpfung an der
Bildfläche und nicht am Kachelkörper hängt); `frontend/penpot/payload.test.ts` an drei Stellen samt
`views.json`; `test_postgres_ddl_compatibility.py` und `test_migration_chain.py` plus ein eigener
Migrationstest im Zuschnitt von `test_migration_endauswahl.py` — datenlos in beide Richtungen, mit
ausdrücklicher Prüfung, wie `DuplicateDecision` in der gerenderten Postgres-DDL erscheint (unter
SQLite ist jeder Enum ein VARCHAR, ein Auseinanderlaufen von Modell- und Migrationsseite bliebe
sonst bis zur Produktion unsichtbar).

**Frontend.** Cache-Invalidierung nach jeder Entscheidung (Gruppenabfrage, Fotoliste mit Filter
`suggested`, Gate-Zählung) — ohne sie zeigt die Ausschuss-Liste die entschiedenen Aufnahmen weiter,
und kein Rendering-Test sieht es. Die Gruppenabkürzung löst genau *einen* API-Aufruf aus. Die
Einstiegsschaltfläche erscheint genau dann, wenn `suggestion.reason === 'duplicate'`, mit Gegenprobe
für `low_quality` und für "kein Vorschlag".

**Bewusst nicht getestet.** Die Hover-Ankündigung am Zeigegerät (CSS, jsdom hat kein `:hover`; die
Tastaturbedienbarkeit ist stattdessen über das native `<button>` zugesichert). Screenreader-Ausgabe.
Nebenläufiges Entscheiden beider Nutzer an derselben Gruppe — "letzter gewinnt" ist beabsichtigt.

Das Testkonzept (`specs/architecture/0002-testkonzept.md`) wird um vier projektweit wiederverwendbare
Muster ergänzt: ein zweiwertiges Prädikat, das einen dritten Zustand bekommt und dessen Verneinung
nicht mehr sein Komplement ist; die Zahl der Verwendungsstellen eines zusammengezogenen Prädikats als
Sollgröße; eine Nutzerentscheidung, die einen Automaten übersteuert und deshalb den Fall mit dem
*fremden* Ablehnungsgrund braucht; und eine Entscheidungszeile, die eine Neuberechnung überlebt und
deshalb den Fall braucht, in dem ihr Bezugsgegenstand verschwunden ist.

## Entscheidungen

- **Reichweite der Entscheidung (Daniel):** Die Entscheidung übersteuert den Automaten. Ein
  "behalten"-markiertes Duplikat läuft in Kriterien-Bewertung, Cloud-Klassifizierung und Album
  weiter; "Ausschuss" fliegt raus. Der Gegenentwurf — ein reiner Sicht- und Merkzustand — hätte die
  Cloud-Grenze nicht berührt, aber die User Story wirkungslos gelassen.
- **Umfang (Daniel):** ein einziger Pull Request, keine Aufteilung in Backend und Frontend.
- **Bindung von `keep` an die Duplikatfrage (Daniel):** `keep` wirkt nur bei
  `duplicate_of IS NOT NULL`, `discard` unbedingt (S3).
- **Bedeutung von "ohne Entscheidung" (Daniel):** Es bleibt beim Vorschlag des Systems; die Ansicht
  sagt das aus, statt Erhalt zuzusichern (AK11).
- **Bezugsmenge des Gruppenzählers (Daniel):** nur die noch offenen Gruppen (AK10).
- `architect` konsultiert (Schritt 1) — Ergebnis: ADR 0104 und der Abschnitt
  `## Architektur / Umsetzung`.
- `ux-ui-designer` konsultiert (Schritt 2) — Ergebnis: der Abschnitt `## UI/UX`.
- `test-engineer` konsultiert (Schritt 3) — Ergebnis: die geschärften Akzeptanzkriterien und der
  Abschnitt `## Teststrategie`.
- `security-engineer` konsultiert (Schritt 3) — Ergebnis: der Abschnitt `## Security`.

## Offene Fragen

Keine.

## Out of Scope

- Die Duplikaterkennung selbst (Schwellwert, Gruppenbildung, Wahl der vorgeschlagenen Aufnahme)
  bleibt unverändert.
- Kein Vergleich für Vorschläge wegen geringer Bildqualität.
- Keine Auswahl über mehrere Gruppen hinweg und kein neuer Filter in der Fotoliste.
- Keine Rücknahme einer Entscheidung nach "noch nicht entschieden".
- Keine Audit-Spalte "wer hat zuletzt entschieden" — fachlich denkbar, ohne Sicherheitsgewicht, und
  nicht Teil dieser Story.
