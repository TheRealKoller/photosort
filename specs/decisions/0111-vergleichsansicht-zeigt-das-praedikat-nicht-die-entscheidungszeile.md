# 0111 - Die Vergleichsansicht zeigt das Überlebens-Prädikat, nicht die Entscheidungszeile

**Status:** Accepted
**Datum:** 2026-09-15
**Bezug:** Spec [`features/0486-duplikate-durchgehen.md`](../features/0486-duplikate-durchgehen.md),
ADR [`0104`](./0104-ausschuss-entscheidung-uebersteuert-den-automaten.md) (das Überlebens-Prädikat
und seine Asymmetrie, hier gelesen und nicht geändert), ADR
[`0103`](./0103-bestandszahlen-an-projectout-stand-bleibt-frontend-ableitung.md) (Punkt 1: das
Aufnahmekriterium für `ProjectOut`, hier angewendet)

## Kontext

Die Vergleichsansicht zeigt je Mitglied die Entscheidungszeile: `keep`, `discard` oder — bei
fehlender Zeile — „noch nicht entschieden". Was ohne Zutun tatsächlich geschieht, bestimmt aber ein
anderes, zusammengesetztes Prädikat (ADR 0104 Punkt 3). Beide Aussagen fallen genau dort
auseinander, wo keine Zeile steht: Ein unentschiedener Duplikat-Verlierer trägt
`suggested_status = REJECTED` und scheidet aus, sieht in der Ansicht aber aus wie der Repräsentant,
der bleibt.

## Entscheidung

### 1. Der angezeigte Zustand ist die Auswertung des Prädikats

`DuplicateGroupPhotoOut` trägt `effective_decision: DuplicateDecision` — `KEEP`, wenn das Foto den
Ausschuss-Schritt überlebt, sonst `DISCARD`, berechnet durch
`duplicates.py::survives_ausschuss_for`. Das Feld `decision` entfällt aus der Antwort. Die Ansicht
kennt damit keinen dritten Wert und unterscheidet nicht mehr, ob ein Zustand vom Automaten oder vom
Nutzer stammt.

**Untersagt ist die Ableitung im Frontend aus `PhotoOut.suggestion`.** Dieses Feld ist eine
Anzeigegröße mit eigenen Unterdrückungsregeln — eine Albumbewertung des anfragenden Nutzers und
jede getroffene Duplikat-Entscheidung lassen es auf `null` fallen — und trägt `suggested_status`
deshalb nicht verlässlich. Eine Ableitung daraus wäre zugleich eine weitere, nur in TypeScript
bestehende Fassung des Prädikats, die der Wächter über die Verwendungsstellen nicht sieht. Bei
Verletzung zeigt die Ansicht für entschiedene und für fremdbewertete Aufnahmen einen anderen
Zustand, als der Ausschuss-Schritt anwendet — ohne Fehler, ohne Meldung.

### 2. „Behalten wirkt hier nicht" ist dasselbe Prädikat an einer hypothetischen Entscheidung

`DuplicateGroupPhotoOut` trägt `keep_possible: bool` — das Prädikat, ausgewertet mit `KEEP` statt
der tatsächlichen Zeile. Ausdrücklich **keine** zweite Regel neben ADR 0104 Punkt 3.

`keep_possible` ist genau dann `false`, wenn `duplicate_of IS NULL AND suggested_status IS NOT NULL`
— der Ausschuss folgt dann nicht aus dem Duplikat, und `keep` wirkt laut ADR 0104 Punkt 3 nicht.
Ein solches Mitglied steht damit **unveränderlich** auf `discard`: Kein Wert der Entscheidungszeile
ändert seinen Zustand. Die Ansicht bietet dort keine Wahl an, statt einen Klick anzunehmen, der
still wirkungslos bleibt.

Der gruppenweite Schreibweg schreibt weiterhin auf **alle** Mitglieder, das unveränderliche
eingeschlossen. Die Menge bestimmt der Server aus dem Stern (ADR 0104, Konsequenzen); eine Ausnahme
im Schreibweg wäre eine zweite Mengendefinition, und die dort geschriebene Zeile bleibt ohnehin ohne
Wirkung.

### 3. Der Durchgang läuft über Nachbar-Anker derselben Antwort, der Zähler über alle Gruppen

`DuplicateGroupOut` trägt zusätzlich `previous_photo_id` und `next_photo_id` — die
Repräsentanten-Id der jeweils benachbarten Gruppe in der Gruppenreihenfolge, `null` am Rand.
`position` und `total` beziehen sich auf **alle** Duplikat-Gruppen des Projekts.

**Kein Gruppenindex in der Route.** Die Route bleibt
`/projects/:projectId/photos/:photoId/duplicates` und ihr Pfadwert ein Anker-Foto. Ein Index ist
über einen erneuten Lauf hinweg nicht stabil und benennt nichts, was es im Datenmodell gibt; die
Gruppe hat bauartbedingt keine Identität (ADR 0104 Punkt 1).

**Keine Liste aller Gruppen an das Frontend.** Sie wäre eine zweite Quelle derselben Reihenfolge
neben `position`/`total`, deren Momentaufnahmen auseinanderlaufen können. Die Nachbarn reisen in
derselben Antwort; beide Schreibwege liefern sie ohne zweite Abfrage mit.

Die Gruppenreihenfolge — frühester `taken_at` der Mitglieder, bei Gleichstand die
Repräsentanten-Id — hängt an keinem Wert, den eine Entscheidung ändert. Sie ist über einen
Durchgang hinweg invariant; nur ein erneuter Lauf kann sie ändern.

### 4. Der Einstieg bekommt einen eigenen Endpunkt, kein Feld an `ProjectOut`

`GET /projects/{project_id}/duplicate-groups` antwortet mit `total` und `first_photo_id` (`null`
ohne Gruppe). Gemessen an ADR 0103 Punkt 1: Die Gruppenbildung ist je Projekt formuliert
(`duplicates.py::load_duplicate_links`); eine projektübergreifende Fassung wäre ein zweites Abbild
von ADR 0104 Punkt 1, und die Auskunft würde im Zwei-Sekunden-Takt von `useProjectQuery` über den
gesamten `photo_scores`-Bestand mitgerechnet.

## Konsequenzen

- `duplicates.py::open_group_representative_ids` und `DuplicateLink.decided` entfallen,
  `load_duplicate_links` liest die Entscheidungstabelle nicht mehr mit. Die Gruppenreihenfolge kennt
  keinen Unterschied zwischen offen und erledigt mehr, und `group_position` braucht seine
  Vereinigung mit der angesehenen Gruppe nicht länger.
- Die Zusagen AK2, AK6 und AK10 der Spec 0374 gelten nicht mehr. ADR 0104 bleibt unberührt — keine
  der drei steht dort.
- Der neue Lese-Endpunkt liegt neben seinem Geschwister in `api/photos.py` und braucht keine
  Foto-Hydratation. Er trägt seine Auth-Dependency ausgeschrieben und einen eigenen 401-Fall; die
  Auflage S8 aus Spec 0374 gilt für `photos.router` unverändert, weil dieser Router keine
  router-weite Dependency-Liste und keinen Vollständigkeitstest trägt.
- Entsteht eines Tages ein dritter Ablehnungsgrund neben Duplikat und Unschärfe, trägt
  `keep_possible === false` seine Begründung nicht mehr eindeutig. Der Grund wird dann ein eigenes
  Feld der Antwort, statt in der Oberfläche als fester Text zu stehen.
- `docs/architecture.md` zieht den Endpunktblock und den Abschnitt zur Vergleichsansicht im selben
  Pull Request nach.
