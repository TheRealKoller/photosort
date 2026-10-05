# 0558 - Verständlicher Album-Entwurf mit Tauschen und Hinzufügen am Foto

**Status:** Implemented ([PR #560](https://github.com/TheRealKoller/photosort/pull/560))
**Erstellt:** 2026-10-02
**Bezug:** [#558](https://github.com/TheRealKoller/photosort/issues/558), ADR [`0130`](../decisions/0130-album-entwurf-gestrichenes-ausgeblendet-eigener-lesepfad-rueckgaengig-als-wiederherstellung.md)

**Umfang:** über dem Richtwert von rund 200 Zeilen, weil die Story vier Handgriffe mit Rückgängig, einen neuen Lese- und einen neuen Schreibpfad sowie die Begriffe zweier Seiten festlegt und jede Konsultation testbare Zusagen beiträgt.

## Ziel

Beim Kuratieren eines echten Projekts war auf der Album-Entwurf-Seite unklar, was zu tun ist. Das galt beim Einstieg, mittendrin und am Ende. Unverständlich waren auch die Zustände: Der Knopf „Im Album"/„Gestrichen" zeigt Zustand und Handlung zugleich, Vorschlag und eigene Entscheidung sind nicht zu unterscheiden, und gestrichene Fotos bleiben im Entwurf stehen. Ein Foto auszutauschen ist umständlich. Ein Foto zusätzlich aufzunehmen, ohne ein anderes zu ersetzen, geht auf der Seite gar nicht.

Die Seite soll dem Arbeitsmodell „nur abweichen, wo nötig" folgen. Der Vorschlag des Systems gilt, man greift nur dort ein, wo etwas stört, und ist fertig, wenn man zufrieden ist. Es gibt keinen gespeicherten Abschluss.

Bewusst geändertes Verhalten:
- Gestrichene Fotos bleiben nicht mehr an ihrer Stelle stehen, sondern werden sofort ausgeblendet. Dafür gibt es einen kurzen Rückgängig-Hinweis und je Event die Möglichkeit, die gestrichenen Fotos einzublenden.
- Die Alternativen stehen direkt am gewählten Foto statt in einem Dialog.
- Wer eine Streichung an einem vorgeschlagenen Foto zurücknimmt, kehrt zum Vorschlag zurück. Es bleibt keine eigene Entscheidung zurück.

Nicht Teil dieser Story: die Endauswahl-Seite (außer ihren Zustandswörtern, siehe Entscheidungen), der Pipeline-Schritt Kuratierung samt Einstellung des Richtwerts, die Bildung des Vorschlags, die Projektnavigation, Tastenkürzel und Entscheidungen in der Großansicht.

## User Story

Als Nutzer, der aus einem Projekt sein Album zusammenstellt, möchte ich auf der Album-Entwurf-Seite auf Anhieb verstehen, was ich sehe, was ein Klick bewirkt und wo ich stehe. Ich möchte ein Foto direkt am Foto gegen eine Alternative tauschen und weitere Fotos hinzufügen können, ohne etwas zu ersetzen. So kann ich den Vorschlag stehen lassen und nur dort eingreifen, wo mich etwas stört, ohne zu rätseln, was zu tun ist und ob ich fertig bin.

## Akzeptanzkriterien

Begriffe für alle Kriterien:
- **im Album**: im Entwurf und nicht von mir gestrichen.
- **Vorschlag**: vom letzten erfolgreichen Lauf vorgeschlagen, ohne eigene Albumentscheidung.
- **Aufgenommen**: eigene Entscheidung `album_worthy`, auch an einem vorgeschlagenen Foto.
- **Gestrichen**: eigene Entscheidung `rejected` an einem Foto mit Rangzeile im Lauf. Das gilt auch für eine Verwerfung im Bildbestand und unabhängig davon, ob das Foto vorgeschlagen ist.
- **aussortiert**: Foto ohne Rangzeile im Lauf.
- **n** = Fotos im Album, **r** = wirksamer Richtwert, **a** = Aufgenommen im Album, **g** = Gestrichen.

**Einstieg**

- [ ] Beim ersten Öffnen (für diesen Nutzer in diesem Browser nichts gespeichert) steht der Erklärtext aufgeklappt über dem Personenfilter und damit über dem ersten Foto. Er enthält drei Aussagen: Hier steht der Vorschlag des Systems als dein Entwurf. Greif nur ein, wo dich etwas stört (streichen, tauschen, hinzufügen). Nichts muss bestätigt werden. Im Lade-, Leer- und Fehlerzustand fehlt er.
- [ ] „Ausblenden“ klappt den Text zu; an seiner Stelle steht nur noch „So funktioniert der Entwurf“, und darüber ist er jederzeit wieder aufklappbar. Der Zustand gilt je Browser und Nutzer: Er bleibt nach einem Neuladen und bei späteren Besuchen erhalten, ein anderer Nutzer im selben Browser sieht den Text aufgeklappt. Gespeichert wird nur ein Wahrheitswert. Ist kein Speicher verfügbar (Lesen oder Schreiben scheitert), ist der Text aufgeklappt und die Seite voll bedienbar. Beide Umschalter tragen `aria-expanded` und `aria-controls`. Nach dem Umschalten liegt der Fokus auf dem dann sichtbaren Umschalter.
- [ ] Der Kopf nennt „{T} Tage · {E} Events“ aus der Eventliste des Laufs, Events ohne Foto im Entwurf eingeschlossen. Darunter steht „{n} im Album · Richtwert etwa {r} · {a} aufgenommen · {g} gestrichen“. r ist auch dann eine Zahl, wenn kein Richtwert eingestellt ist. Bei n < r, n = r und n > r stehen derselbe Satzbau und dieselbe Darstellung, ohne Farbe, Symbol oder Warnwort.

**Mittendrin**

- [ ] Eine mitlaufende Kopfleiste zeigt „Tag {d} von {T} · Event {p} von {E}“ und den Eventnamen. Sie steht nur, wenn es Events gibt, und bleibt beim Scrollen oben sichtbar, auch bei 360 px.
  - p ist die Position des Events im Lauf (1..E), d die echte Tagesnummer.
  - Als aktuell gilt der Abschnitt, dessen Oberkante zuletzt unter die Leiste gelaufen ist. Vor dem ersten Abschnitt gilt Event 1.
  - Ist dieser Abschnitt ein zugeklappter Tag, gilt dessen erstes Event.
  - Zuklappen und Personenfilter ändern weder p noch E. Ein Event, in dem der Filter alle Fotos verbirgt, steht weiter als Abschnitt und zählt mit.
- [ ] a und g sind aus dem aktuellen Zustand abgeleitet, nicht aus gezählten Handgriffen. Sie und n ändern sich mit der Serverantwort eines Handgriffs im selben Render und ohne Neuladen, und zwar so:

| Handgriff | n | a | g |
|---|---|---|---|
| Streichen eines „Vorschlag“ | −1 | 0 | +1 |
| Streichen eines „Aufgenommen“ | −1 | −1 | +1 |
| Wieder aufnehmen, vorgeschlagen | +1 | 0 | −1 |
| Wieder aufnehmen, nicht vorgeschlagen | +1 | +1 | −1 |
| Hinzufügen eines nicht gestrichenen Fotos | +1 | +1 | 0 |
| Hinzufügen eines gestrichenen Fotos | +1 | +1 | −1 |
| Tausch „Vorschlag“ gegen unberührte Alternative | 0 | +1 | +1 |
| Tausch „Aufgenommen“ gegen unberührte Alternative | 0 | 0 | +1 |
| Tausch „Vorschlag“ gegen gestrichene Alternative | 0 | +1 | 0 |
| Rückgängig | zurück auf die Werte vor dem Handgriff | | |

- [ ] Eine Verwerfung im Bildbestand an einem Foto mit Rangzeile im Lauf erscheint nach dem Wechsel auf den Album-Entwurf in g und in der Gestrichen-Zeile ihres Events. Eine Verwerfung an einem aussortierten Foto erscheint dort nicht.

**Am Ende**

- [ ] Unter dem letzten Tag steht der Abschluss „Stand des Entwurfs“ mit drei Sätzen:
  - „{n} Fotos im Album, Richtwert etwa {r}.“
  - „Deine Eingriffe: {a} aufgenommen, {g} gestrichen.“, bei a = g = 0 stattdessen „Keine Eingriffe – der Vorschlag gilt unverändert.“
  - „Nichts muss bestätigt werden; du kannst jederzeit weiterarbeiten.“

  Darunter steht „Zur Endauswahl“ als einzige primäre Schaltfläche der Seite. Die Zahlen im Abschluss gleichen in jedem Zustand denen der Kopfleiste.
- [ ] „Zur Endauswahl“ steht dauerhaft in der Kopfleiste und führt mit einem Klick auf die Endauswahl des Projekts. Es ist ein Link, der nichts schreibt.
- [ ] Es gibt keinen gespeicherten Zustand „fertig“: Kein Element der Seite löst eine Abschlussanfrage aus, und der Wechsel zur Endauswahl schreibt nichts. Auch nach Entscheidungen in der Endauswahl sind alle Handgriffe dieser Seite weiter möglich und wirksam.

**Zustände und Entscheidungsknopf**

- [ ] Jede Kachel im Album trägt genau ein Kennzeichen, „Vorschlag“ oder „Aufgenommen“. Ohne Farbe trennen die drei Zustände:
  - Wort, zugleich der zugängliche Name.
  - Symbol: „Vorschlag“ trägt `cog` und `book`, „Aufgenommen“ `book`, „Gestrichen“ `x-circle` und einen durchgestrichenen Dateinamen.

  Das Kennzeichen „nicht vorgeschlagen“ trägt eine „Aufgenommen“-Kachel, die der Lauf nicht vorschlägt. Beide Datenformen bekommen es gleich: keine Rangzeile und Rangzeile mit `proposed: false`.
- [ ] Die Wörter „Vorschlag“, „Aufgenommen“ und „Gestrichen“ kommen für Album-Entwurf und Endauswahl aus einer einzigen Begriffsquelle. Sie stehen im Code genau einmal als Literal. Das gilt auch im Dialog „Alle Alternativen“: Gestrichene tragen dort „Gestrichen“, „zuvor im Album“ entfällt. Der Bildbestand (Raster, Einzelbild, Bewertungsleiste) zeigt unverändert „Album-würdig“ und „Verworfen“.
- [ ] Jede Entscheidungsfläche nennt die Handlung, nie den Zustand:
  - „Streichen: {Pfad}“ an der Albumkachel
  - „Wieder aufnehmen: {Pfad}“ an der gestrichenen Kachel
  - „Tauschen: {Pfad}“ im Band ~~**und** im Dialog „Alle Alternativen“~~ *(seit Spec [`0578`](0578-alternativen-serie-und-hinzufuegen.md): in Serie und aufgeklappter Reihe des Bands)*
  - „Hinzufügen: {Pfad}“ im Hinzufügen-Panel *(seit Spec [`0578`](0578-alternativen-serie-und-hinzufuegen.md) auch in Band und aufgeklappter Reihe)*
  - „Foto hinzufügen: {Eventname}“ als Auslöser

  Keine dieser Flächen trägt `aria-pressed`.
- [ ] Streichen ist ein Druck ohne Bestätigung und ohne Dialog und löst genau eine schreibende Anfrage aus. Während sie läuft, ist die Fläche dieses Fotos `busy` und nimmt keinen zweiten Druck an. Andere Fotos bleiben bedienbar.

**Gestrichene Fotos**

- [ ] Nach erfolgreichem Streichen verschwindet die Kachel. Die Reihenfolge der übrigen Kacheln bleibt unverändert, es rückt nichts nach. Im selben Render ändern sich n und g laut Tabelle, die Bildzahl „({k} Bilder)“ des Events und die Motivzeile; beide zählen nur Fotos im Album. Der Fokus geht auf „Streichen“ der nachfolgenden Kachel des Events, sonst der vorigen, sonst auf die Gestrichen-Zeile. Er landet nie auf `body`, und es gibt keinen Scrollsprung.
- [ ] Nach dem Streichen erscheint der Hinweis „Gestrichen“ mit Dateiname und „Rückgängig“.
  - „Rückgängig“ stellt den Zustand vor dem Streichen wörtlich wieder her. Ohne eigene Entscheidung zuvor wird diese entfernt, das Foto ist wieder „Vorschlag“. War es zuvor „Aufgenommen“, ist es wieder „Aufgenommen“.
  - Das Foto steht an seiner alten Stelle, die Zahlen gehen zurück, ein Favoritenkennzeichen bleibt erhalten. Der Fokus geht auf „Streichen“ des wiederhergestellten Fotos.
  - Der Hinweis steht 8 s. Fokus im Hinweis hält die Zeit an, ein Zeiger darüber ebenfalls, aber nur bei feinem Zeiger mit Hover. Danach läuft die Restzeit weiter, sie beginnt nicht neu.
  - Er endet nach Ablauf, nach erfolgreichem Rückgängig, mit Esc bei Fokus darin und mit jedem neuen Handgriff. Rückgängig wirkt immer nur auf den letzten Handgriff.
  - Scheitert das Rückgängig, bleibt der Hinweis. An Stelle des Knopfs steht der Grund aus der Serverantwort als Text, und die 8 s beginnen neu.
  - Titel und Dateiname liegen in einem dauerhaft eingehängten `role="status"`. Der Fokus wird nicht in den Hinweis gezogen.
- [ ] Jedes Event mit mindestens einem gestrichenen Foto zeigt unter seinem Raster „{N} gestrichen – anzeigen“, N ist ihre Zahl. Events ohne Gestrichenes zeigen keine Zeile.
  - Aufgeklappt („{N} gestrichen – ausblenden“) erscheinen die gestrichenen Fotos mit Kennzeichen „Gestrichen“ und durchgestrichenem Dateinamen. Die Großansicht bleibt erreichbar, und je Foto gibt es „Wieder aufnehmen“.
  - Der Aufklappzustand gilt je Event und wird nicht gespeichert.
  - Der Personenfilter filtert die Zeile nicht.
- [ ] Wer ein gestrichenes Foto wieder aufnimmt, das der Vorschlag trägt, entfernt die eigene Entscheidung: Das Foto ist wieder „Vorschlag“ und a bleibt gleich. Trägt der Vorschlag das Foto nicht, wird es „Aufgenommen“ und a steigt um eins. In beiden Fällen steht das Foto an seiner zeitlichen Stelle, es gibt keinen Rückgängig-Hinweis, und ein offener Hinweis endet.
  - Abgrenzung, im selben Fall geprüft: Ein vorgeschlagenes Foto mit eigenem „Aufgenommen“ ist nach Streichen und Rückgängig wieder „Aufgenommen“, nach Streichen und Wiederaufnehmen dagegen „Vorschlag“.
  - Fokus: auf „Wieder aufnehmen“ der nächsten gestrichenen Kachel, sonst der vorigen. Ist die Liste leer, verschwindet die Zeile, und der Fokus geht auf „Streichen“ des zurückgekehrten Fotos.

**Alternativen direkt am Foto**

- [ ] „Alternativen: {Pfad}“ öffnet ohne Dialog ein Band als volle Rasterzeile nach der Zeile des gewählten Fotos.
  - Auf der Seite ist höchstens ein Band oder Panel offen. Der Auslöser trägt `aria-expanded` und `aria-controls`.
  - Geladen wird erst beim Öffnen, nie eine Abfrage je Kachel.
  - ~~Das Band zeigt höchstens vier Alternativen~~ *(abgelöst durch Spec [`0578`](0578-alternativen-serie-und-hinzufuegen.md): das Band zeigt die Aufnahmeserie, 4 bis 12)*: Fotos desselben Events mit Rangzeile im Lauf, die nicht im Album sind. Gestrichene sind eingeschlossen und tragen „Gestrichen“, aussortierte nie.
  - Reihenfolge des Servers: zuerst gleiches Motiv nach Qualität absteigend, dann der Rest des Events nach Qualität. Fotos ohne Qualitätswert stehen jeweils zuletzt, bei Gleichstand gewinnt die kleinere Id.
  - Laden zeigt Platzhalter, ein Fehler eine Meldung mit „Erneut versuchen“, leer „Keine weiteren Fotos in diesem Event.“
  - Esc und „Schließen“ schließen das Band und geben den Fokus an „Alternativen“ zurück.
- [ ] Ein Klick auf „Tauschen“ löst genau eine schreibende Anfrage aus. Danach gilt:
  - Die Alternative steht als „Aufgenommen“ an ihrer zeitlichen Stelle, auch wenn sie ein gestrichenes vorgeschlagenes Foto war.
  - Das bisherige Foto ist gestrichen, ausgeblendet und steht in der Gestrichen-Zeile.
  - n bleibt gleich, a und g ändern sich laut Tabelle.
  - Das Band schließt, der Fokus geht auf „Streichen“ der neuen Kachel, und der Hinweis „Getauscht“ erscheint.
- [ ] „Rückgängig“ nach einem Tausch stellt mit einer Anfrage beide Fotos auf ihren Zustand vor dem Tausch zurück, alle oder keins.
  - Das ursprüngliche Foto steht wieder an seiner Stelle. Die Alternative hat ihren Vorzustand zurück (unberührt bzw. gestrichen) und ist nicht mehr im Album.
  - Während der Anfrage sind beide Fotos gesperrt.
  - Hat sich der Zustand eines der beiden Fotos seit dem Tausch geändert, lehnt der Server ab und schreibt nichts. Der Hinweis zeigt dann den Grund.
- [ ] ~~„Alle Alternativen“ öffnet den Dialog mit dem vollständigen Fotobestand des Events, seitenweise. Begriffe, Namen („Tauschen: {Pfad}“) und die Wirkung des Tauschs samt Hinweis sind dieselben wie im Band.~~ *(abgelöst durch Spec [`0578`](0578-alternativen-serie-und-hinzufuegen.md): „Alle Fotos des Events“ klappt die volle Reihe an Ort und Stelle im Band auf.)*
- [ ] Die Großansicht ist über die Bildfläche jeder Albumkachel und jeder gestrichenen Kachel erreichbar. Verlauf und Fokusrückgabe bleiben wie bisher.

**Fotos hinzufügen, ohne zu ersetzen**

- [ ] Jedes Event hat als letzte Rasterzelle „Foto hinzufügen: {Eventname}“, auch ein Event ohne Foto im Entwurf.
  - Es öffnet ein Panel, das erst beim Öffnen lädt.
  - Kandidaten: alle Fotos dieses Events mit Rangzeile im Lauf, die nicht im Album sind. Gestrichene sind eingeschlossen und gekennzeichnet. Aussortierte und Fotos anderer Events erscheinen nie.
  - Reihenfolge: Qualität absteigend, ohne Qualitätswert zuletzt, Gleichstand nach kleinerer Id. Es gibt kein Bezugsfoto und damit keine Motivstufe.
  - 8 Kandidaten je Seite, darunter „Weitere Fotos“. Der Personenfilter filtert das Panel nicht.
- [ ] Hinzufügen löst genau eine schreibende Anfrage aus.
  - Das Foto steht danach an seiner zeitlichen Stelle als „Aufgenommen“, auch wenn es ein gestrichenes vorgeschlagenes war. n steigt um genau eins.
  - Kein anderes Foto ändert Zustand oder Reihenfolge.
  - Der Kandidat verlässt die Liste, das Panel bleibt offen.
  - Es gibt keinen Rückgängig-Hinweis, ein offener Hinweis endet.
  - Der Fokus geht auf „Hinzufügen“ des nächsten Kandidaten, sonst des vorigen, sonst auf die Überschrift.
- [ ] Ein Event ohne Foto im Entwurf steht mit Überschrift, „Kein Bild im Entwurf“ und dem Hinzufügen-Feld da, auch wenn der Lauf ihm nie etwas vorgeschlagen hat. Nach dem Hinzufügen steht dort das Foto, der Satz entfällt. Nur ein Lauf ohne Events zeigt den Leerzustand der Seite. Der Text zur Cloud-Freigabe behält dabei den Vorrang.
- [ ] Hinzufügen über r hinaus geht ohne Rückfrage, Warnung oder Sperre; die Anfrage geht sofort.

**Für alle Handgriffe**

- [ ] Keine Entscheidung lädt die Seite oder die Entwurfsliste neu: Die Liste wird beim Öffnen genau einmal geladen. Die Scrollposition des Dokuments ist nach jedem Handgriff unverändert. Nach jedem Handgriff zeigt die Seite dieselben Fotos, Kennzeichen, Zahlen und Gestrichen-Zeilen wie nach einem Neuladen.
- [ ] Scheitert ein Handgriff (Streichen, Wieder aufnehmen, Tausch, Hinzufügen), ändert sich nichts. Am Ort der Handlung erscheint eine Meldung mit dem Grund aus der Serverantwort, und der Fokus bleibt auf dem Auslöser.
- [ ] Bei 360 px Breite gilt:
  - Alle Handgriffe dieser Story sind per Touch treffbar: Erklärtext umschalten, Streichen, Alternativen, Tauschen, ~~Alle Alternativen~~ *(entfallen, Spec [`0578`](0578-alternativen-serie-und-hinzufuegen.md))*, Schließen, gestrichene anzeigen, Wieder aufnehmen, Foto hinzufügen, Hinzufügen, Weitere Fotos, Rückgängig, Zur Endauswahl.
  - Die Seite scrollt in keinem Zustand waagerecht: Ruhe, Band offen, Panel offen, Gestrichene eingeblendet, Hinweis sichtbar.
  - Der Hinweis liegt vollständig im Sichtbereich, und „Rückgängig“ wird nicht abgeschnitten.

**Endauswahl: Zustandswörter (Produktentscheidung Option C)**

- [ ] Die Haltungszeilen je Teilnehmer in der Endauswahl zeigen:
  - entschieden aufgenommen → „Aufgenommen“
  - gestrichen → „Gestrichen“
  - unberührt und vom Lauf vorgeschlagen → „Vorschlag“
  - unberührt und nicht vorgeschlagen → „–“ mit dem zugänglichen Namen „Nicht im Entwurf“; beide Datenformen gleich (keine Rangzeile bzw. `proposed: false`)

  Symbole und Wörter kommen aus derselben Begriffsquelle wie im Album-Entwurf. Unverändert bleiben:
  - die Zeilenform „{Name}: {Kennzeichen}“, die Zuordnung über den Teilnehmer und „Haltung zu {Pfad}“
  - „gemeinsam entschieden“, die Herausnahme sowie „Aufnehmen“, „Nicht aufnehmen“ und „Herausnehmen“
  - beide Sichten und die Leerzustände
- [ ] Bei 360 px brechen die Kennzeichen der Haltungszeilen nicht um, und die Endauswahl scrollt in beiden Sichten nicht waagerecht.

## Datenmodell-Bezug

Keine Änderung am Datenmodell, keine Migration. Gelesen und geschrieben werden die bestehenden Entitäten `Rating`, `PhotoRanking`, `Event` und der letzte erfolgreiche Kuratierungslauf (siehe [`docs/architecture.md`](../../docs/architecture.md)).

## Architektur / Umsetzung

Die Entscheidung steht in ADR [`0130`](../decisions/0130-album-entwurf-gestrichenes-ausgeblendet-eigener-lesepfad-rueckgaengig-als-wiederherstellung.md). Sie löst ADR 0098 Punkt 3 (Ort des Lesepfads, Anzeige gestrichener Fotos) und ADR 0071 Entscheidung 3 (Anzeigeteil) teilweise ab. ADR 0098 Punkt 5 und ADR 0100 Punkt 3 werden ergänzt, nicht geändert. Am Datenmodell ändert sich nichts, es gibt keine Migration.

### Gewählter Ansatz

- **Ein eigener Lesepfad mit Eventliste.** `GET /projects/{id}/album-draft` liefert `AlbumDraftOut { events: list[EventOut], items: list[PhotoOut] }` aus einer Anfrage. Es gibt kein `total` und kein Blättern, wie bei `AlbumSelectionOut`.
  - `events` umfasst alle Events des letzten erfolgreichen Laufs, geordnet nach `position` (lückenlos 1..m). Daraus kommen „Event 4 von 17“, die Zahl der Tage und Events im Kopf und das Hinzufügen-Feld in Events ohne Foto im Entwurf.
  - `items` ist `Vorschlag ∪ eigene album_worthy ∪ (eigene rejected ∩ Rangzeile im Lauf)`. Die Reihenfolge bleibt `(events.position, taken_at, id)`.
  - Innerhalb der Antwort gilt ausnahmslos: im Album ⇔ eigener `status ≠ rejected`.
  - Der Entwurfsmodus `draft` an `GET /projects/{id}/photos` entfällt. Er bleibt nach dem Muster von `selection` als `None`-typisierter Riegel stehen und antwortet mit `422`.
- **Gestrichenes bleibt in der Antwort, die Ansicht blendet es aus.** Gestrichene Fotos erscheinen nur noch in der Zeile „N gestrichen – anzeigen“ ihres Events. Es rückt nichts nach.
- **Der Cache ist jederzeit die Antwort, die der Server jetzt gäbe.** Die Entwurfsliste wird nicht neu geladen; das ist das bestehende Muster aus ADR 0098 Punkt 6. Damit bleibt auch die Scrollposition erhalten.
  - Jeder Handgriff setzt den Zustand ein, den der Server zurückmeldet (`RatingWriteOut`).
  - Ein Foto, das danach nicht mehr in die Antwortmenge gehört, wird entfernt. Ein neu dazugehörendes wird mit dem Sortierschlüssel des Servers eingefügt (`insertDraftPhoto`).
  - Die Updates sind nicht optimistisch und haben keinen Rollback-Pfad. Sie greifen bei Erfolg der Anfrage, mit der bestehenden Sperre je Foto (`decidingPhotoIdsRef`).
  - Andere Fotoabfragen werden weiterhin invalidiert, darunter die Alternativen. Der eigene Entwurfsschlüssel ist davon ausgenommen.
- **Welcher Handgriff was schreibt:**

| Handgriff | Aufruf | Ergebnis |
|---|---|---|
| Streichen | `PUT /photos/{id}/rating` `rejected` | Foto gestrichen und ausgeblendet |
| Rückgängig nach Streichen | Vorzustand `null` → `DELETE`; `album_worthy` → `PUT album_worthy` | Zustand vor dem Handgriff, wörtlich |
| Wiederaufnehmen aus der Gestrichen-Zeile | `ranking.proposed` → `DELETE`; sonst `PUT album_worthy` | zurück zum Vorschlag bzw. „von mir aufgenommen“ |
| Hinzufügen | `PUT album_worthy` | „von mir aufgenommen“, auch bei einem gestrichenen vorgeschlagenen Foto |
| Tausch | `POST /projects/{id}/draft/exchange` (unverändert) | Alternative `album_worthy`, bisheriges Foto `rejected` |
| Rückgängig nach Tausch | **neu** `POST /projects/{id}/draft/exchange/undo` | beide Vorzustände atomar wiederhergestellt |

### Backend (`backend/src/photosort/`)

1. `selection.py::order_alternatives(reference: AlternativeCandidate | None, candidates)`: Ohne Bezugsbild entfällt die Motivstufe. Sortiert wird dann nach Qualität absteigend, Fotos ohne Qualitätswert zuletzt, bei Gleichstand nach der kleineren Id. Die Funktion bleibt rein.
2. `api/photos.py`:
   - `_draft_photo_ids`: Das Prädikat bekommt einen dritten Zweig `ranking.photo_id IS NOT NULL AND own.status = REJECTED`.
   - `_event_spans_and_positions` wird so umgebaut, dass es die `Event`-Zeilen **einmal** lädt und daraus Spannen, Positionen und `EventOut` (`_event_out`) bildet. Keine zweite Abfrage, Auflage S14.
   - Neu sind `AlbumDraftOut` und `GET /projects/{project_id}/album-draft`. Die Hydratation wird aus dem bisherigen `draft`-Zweig von `list_photos` übernommen; danach steht der Riegel `draft: None = Query(None, include_in_schema=False)`. Die Auth-Dependency steht ausgeschrieben.
   - `draft_alternatives`: `photo_id` wird optional. Ist es gesetzt, gilt Auflage S3 unverändert: Auflösung über die Rangzeile desselben Laufs und Events, sonst `200` mit leerer Liste. Fehlt es, entfällt Schritt (1). Die Bindung ans Projekt läuft weiter allein über das Laufprädikat der Kandidatenabfrage.
   - Neu sind `DraftExchangeUndoIn` und `POST /projects/{project_id}/draft/exchange/undo`.
     - Body mit `extra="forbid"`: `photo_id` und `replaced_photo_id`, dieselben Ids wie beim Tausch. Dazu `photo_previous_status: Literal[rejected] | None` und `replaced_previous_status: Literal[album_worthy] | None`.
     - Ablehnungen wie beim Tausch über `_exchange_sides`: gleiche Id, kein Lauf, fremdes Projekt oder anderes Event ergeben `422` mit `_EXCHANGE_REFUSAL`.
     - Precondition: aktuell `photo_id` = `album_worthy` und `replaced_photo_id` = `rejected`. Sonst `409`, und es wird nichts geschrieben.
     - Geschrieben wird über `write_own_rating(record=False)` zweimal. Dazu kommt **ein** `record_exchange(photo_id=replaced, replaced_photo_id=photo)`, also der Tausch in Gegenrichtung (ADR 0100 Punkt 3), und genau **ein** Commit.
     - Antwort: `DraftExchangeUndoOut { photo: RatingWriteOut, replaced: RatingWriteOut }`.
3. `api/ratings.py::delete_rating`: Statt `204` antwortet der Endpunkt mit `200` und `RatingWriteOut` (Rückgabe von `write_own_rating`). Die Semantik bleibt gleich.
4. Register: `tests/test_openapi_beschreibungen.py` (neue Endpunkte). Für beide neuen Endpunkte je ein eigener `401`-Nachweis; `api/photos.py` hat kein Vollständigkeitsnetz.
5. `demo_state.py`: Der Bestand braucht mindestens ein gestrichenes vorgeschlagenes Foto, ein aufgenommenes nicht vorgeschlagenes, ein gestrichenes nicht vorgeschlagenes Foto mit Rangzeile und ein Event ohne Vorschlag. Ohne diese Fälle sind Gestrichen-Zeile, Eingriffszähler und Hinzufügen im leeren Event in E2E und in `browse-app` nicht sichtbar.

### Frontend (`frontend/src/`)

1. `api/types.ts`: `AlbumDraftOut`, `DraftExchangeUndoIn`, `DraftExchangeUndoOut`.
   - `api/photos.ts`: neu `getAlbumDraft`, `listDraftAlternatives` mit optionalem `photoId`, neu `undoDraftExchange`; die Option `draft` an `listPhotos` entfällt.
   - `api/ratings.ts::deleteRating` liefert `Promise<RatingWriteOut>`.
2. `hooks/usePhotos.ts`:
   - `useDraftQuery` ruft `getAlbumDraft` auf; der Schlüssel `['photos', id, 'draft']` bleibt.
   - `applyWrittenRating` arbeitet auf `AlbumDraftOut` und entfernt Einträge, die die Antwortmenge verlassen.
   - `useDraftDecisionMutation` nimmt `status: RatingStatus | null` (`null` → `deleteRating`) und optional ein einzufügendes `PhotoOut` (Hinzufügen).
   - neu `useDraftExchangeUndoMutation`.
   - `useDraftAlternativesQuery`: `photoId` optional, `pageSize` kommt in den Schlüssel. So holen das Band (Seite 4) und „alle Alternativen“ nicht dieselbe Cache-Zeile.
3. `utils/albumDraft.ts`, rein:
   - `draftMembership(photo, ownStatus): 'album' | 'struck' | 'out'` ist die eine Stelle, die das Serverprädikat nachbildet.
   - `draftCounts(items, username)` liefert im Album, aufgenommen und gestrichen.
   - `reAddDecision(photo)` liefert `null` oder `'album_worthy'`.
   - `draftSizeText` zählt nur noch Fotos im Album.
4. `utils/eventGrouping.ts`: neu `groupEventsByDay(events, items)`. Die Gruppen kommen aus der Eventliste, leere Events eingeschlossen. `groupPhotosByDay` bleibt für die Endauswahl. `knownEventGroupsRef` in `AlbumDraftPage` entfällt.
5. `pages/AlbumDraftPage.tsx` wird in Bausteine zerlegt. Die Namen sind Vorschlag, die Gestalt gehört UX/Penpot:
   - `components/DraftExplainer.tsx`: zuklappbar. Der Zustand liegt in `localStorage` unter einem Schlüssel mit dem Nutzernamen, damit er je Browser und Nutzer gilt; es wird nur ein Boolean gespeichert. Ist der Speicher nicht verfügbar, ist der Text aufgeklappt.
   - `components/DraftEventSection.tsx`: Albumkacheln, Gestrichen-Zeile mit lokalem Aufklappzustand je `eventId` (nicht persistiert), Hinzufügen-Feld (`useDraftAlternativesQuery` ohne `photoId`, nur auf Anforderung geladen).
   - `components/DraftAlternativesBand.tsx`: Band am **einen** gewählten Foto der Seite, also eine Abfrage je gewähltem Foto, nie eine je Kachel.
   - ~~`DraftAlternativesDialog.tsx` bleibt als Ansicht „alle Alternativen“ mit Seitenabruf. Kommentar und Test „kein Rückgängig-Knopf“ werden angepasst.~~ *(entfernt mit Spec [`0578`](0578-alternativen-serie-und-hinzufuegen.md))*
   - `components/UndoToast.tsx`: eigene Komponente ohne neue Abhängigkeit, `role="status"`. Rückgängig gilt nur für den letzten Handgriff. Ein neuer Handgriff ersetzt den Hinweis, die Gestrichen-Zeile bleibt der zweite Weg zurück. Die Sperre gilt für beide Ids.
   - Positionsanzeige über ein `IntersectionObserver` auf den Eventabschnitten, als eigener Hook mit injizierbarem Observer.
   - Abschluss unter dem letzten Event und ein dauerhafter Link auf `PROJECT_ROUTE_PATHS.selection`.
   - Leerzustand: `events.length === 0` zeigt `DRAFT_EMPTY_TEXT`; der Text zur Cloud-Freigabe behält den Vorrang.
6. `components/CurationPhotoTile.tsx`: Die Entscheidungsfläche nennt die Handlung („Streichen“ bzw. „Wieder aufnehmen“), ohne `aria-pressed`. Der Zustand (Vorschlag, aufgenommen, gestrichen) ist nicht allein farbcodiert. Er kommt aus derselben Begriffsquelle wie die Endauswahl, nie aus neuen Literalen; siehe offener Punkt 1.
7. Strukturwächter `albumSelection.structure.test.ts`: Die neuen Entwurfsdateien kommen in die Liste der Dateien, die keine Endauswahlfelder nennen dürfen.

### E2E

- `tap-targets`, `no-horizontal-scroll` und `popover-position` gehen auf die neuen Namen der Entscheidungsfläche (`DRAFT_TILE_TOGGLE`, `/^(Im Album|Gestrichen): /`).
- Die 360-px-Prüfung wird um Band, Gestrichen-Zeile, Hinzufügen und Rückgängig-Hinweis ergänzt.
- Der asynchrone Verlauf der Großansicht (`kuratierung-grossansicht`) bleibt.

### Reihenfolge

`selection.py` → `api/photos.py` (Lesepfad, Riegel, Alternativen, Undo) → `api/ratings.py` → Register, `demo_state.py` → Frontend-API, Typen, Hooks → `utils` → Komponenten und Seite → E2E → `docs/architecture.md`.

### Doku im selben PR

In `docs/architecture.md`, Kuratierungszweig (ca. Z. 538–635):
- Der Entwurfsmodus von `GET /projects/{id}/photos` wird durch `GET /projects/{id}/album-draft` ersetzt, samt erweiterter Antwortmenge und Eventliste.
- „Gestrichenes bleibt stehen“ wird zu „ausgeblendet, Gestrichen-Zeile“.
- „kein Rückgängig-Knopf“ wird zum Undo-Endpunkt.
- `photo_id` am Alternativen-Endpunkt wird optional.
- `DELETE /photos/{id}/rating` liefert `200`.
- `AlbumDraftPage` mit Band ~~und Dialog „alle Alternativen“~~ *(seit Spec [`0578`](0578-alternativen-serie-und-hinzufuegen.md): aufgeklappte Reihe im Band)*.

`docs/setup.md` bleibt unberührt.

## UI/UX

### Design

**Stand:** ausgearbeitet
**Penpot-Seite:** Ansicht — Album-Entwurf
**Schlüssel:** album-entwurf

**Auflösung des Schlüssels.** `album-entwurf` erfüllt `^[a-z0-9][a-z0-9-]{2,39}$` und gehört zu den Schlüsseln in `design/penpot/views.json` (`ansichten[]`, Treffer über `schluessel`). Der Eintrag nennt:
- Breiten `mobile` und `desktop`.
- Zustände `gefuellt`, `leer`, `ladend` und `fehler` (Variantenachse `zustand`).
- Bausteine `button`, `badge`, `alert`, `skeleton` und `input`.

Für seine Lücken gilt der Text unten, nicht das Brett:
- `behaelter`: Kachel, Band und Rückgängig-Hinweis sind dort Rahmen.
- `kachelmasse`: sechs Kacheln je Zeile auf dem Desktop, zwei auf dem Handy.
- `ueberlagerung`: Der Hinweis schwebt.
- `toastzeit`: siehe unten.
- `bewegung`: Der Puls der Platzhalter ist nicht abbildbar.
- `rueckgaengigwege`: Der zweite Weg zurück ist die Gestrichen-Zeile.
- `bildzuschnitt`, `seitengrund`, `trefferflaeche`: Darstellungsdetails ohne Token.

Verbindlich für das Verhalten ist dieser Text, Maße und Optik kommen aus dem Brett. Widersprechen sich beide, wird das als Befund gemeldet und nicht still aufgelöst.

### Zustandswörter (Produktentscheidung Daniel, 2026-10-02)

Der Album-Entwurf **und** die Endauswahl benennen die Haltung zu einem Foto mit drei Wörtern:

- **„Vorschlag“**: Teil des Vorschlags und nicht angefasst.
- **„Aufgenommen“**: von mir aufgenommen.
- **„Gestrichen“**.

Die Wörter kommen aus **einer** Begriffsquelle: eine neue Konstante neben `RATING_STATUS_LABELS`, vorgeschlagen ist `utils/albumStateLabels.ts`. An der Aufrufstelle steht nie ein Literal. Der Bildbestand (Raster, Einzelbild, Bewertungsleiste) behält „Album-würdig“ und „Verworfen“; `RATING_STATUS_LABELS` bleibt unverändert.

Dargestellt werden die Zustände über die bestehenden Kennzeichen-Konstruktionen. Das Wort ist zugleich der zugängliche Name:

| Zustand | Konstruktion | Symbol |
|---|---|---|
| Vorschlag | `Badge tone="album-worthy" suggested` (Toast-Fläche, Rand `--accent-2`) | `cog` + `book` |
| Aufgenommen | `Badge tone="album-worthy"`, gefüllt | `book` |
| Gestrichen | `Badge tone="rejected"`, gefüllt, mit `data-struck` und durchgestrichenem Dateinamen | `x-circle` |

Ohne Farbe trennen Zahnrad, Rand gegen Füllung, Symbol und Wort die drei Zustände. Handlungswörter sind davon getrennt: „Streichen“, „Wieder aufnehmen“, „Tauschen“, „Hinzufügen“, „Rückgängig“ sowie in der Endauswahl unverändert „Aufnehmen“, „Nicht aufnehmen“ und „Herausnehmen“.

### Ablauf und Layout des Album-Entwurfs (von oben nach unten)

1. **Seitenkopf.** `h1` „Album-Entwurf“ wie bisher. Darunter steht `text-sm text-text` „{T} Tage · {E} Events“ aus `events`, erst nach dem Laden.
2. **Erklärtext** (`DraftExplainer`). Er steht vor dem Personenfilter und damit über dem ersten Foto.
   - Aufgeklappt: Fläche `rounded-lg border border-border bg-surface p-3` mit `info` und drei Sätzen in `text-sm text-text`:
     - „Hier steht der Vorschlag des Systems als dein Entwurf.“
     - „Greif nur dort ein, wo dich etwas stört – streichen, tauschen oder ein Foto hinzufügen.“
     - „Nichts muss bestätigt werden; du bist fertig, wenn du zufrieden bist.“
   - Oben rechts steht `ghost sm` „Ausblenden“.
   - Zugeklappt steht an derselben Stelle nur `ghost sm` mit `info` „So funktioniert der Entwurf“.
   - Beide tragen `aria-expanded` und `aria-controls`. Der Fokus bleibt auf dem Umschalter, der danach sichtbar ist.
   - Gespeichert wird ein Wahrheitswert in `localStorage` je Browser und Nutzer. Ist kein Speicher verfügbar, ist der Text aufgeklappt.
   - Im Leer-, Lade- und Fehlerzustand fehlt der Erklärtext.
3. **Mitlaufende Kopfleiste**: `sticky top-header z-10 bg-bg border-b border-separator py-2`, nur bei `events.length > 0`.
   - Zeile 1 (`text-sm text-text-h`): „Tag {d} von {T} · Event {p} von {E}“. Rechts daneben steht `Button asChild variant="secondary" size="sm"` „Zur Endauswahl“ (`shrink-0`, `tap-target`).
   - Zeile 2 (`text-sm text-text`, `truncate`): der Eventname.
   - Zeile 3 (`text-sm text-text`, umbrechend): „{n} im Album · Richtwert etwa {r} · {a} aufgenommen · {g} gestrichen“.
   - Eine Abweichung vom Richtwert erscheint neutral: ohne Farbe, Symbol oder Warnung.
   - Die Zahlen kommen aus `draftCounts` und ändern sich im selben Render wie der Handgriff. Ein Tausch zählt +1 aufgenommen und +1 gestrichen.
   - Als Position gilt der Abschnitt, dessen Oberkante zuletzt unter die Leiste gelaufen ist (`IntersectionObserver`-Hook). Vor dem ersten Abschnitt gilt Event 1. Zugeklappte Tage zählen mit.
   - Die Leiste ist nicht live. Fokussierbar ist nur der Link.
4. **Personenfilter und seine Statuszeile** bleiben unverändert. Die Kopfzahlen zählen den ganzen Entwurf. Gestrichen-Zeile und Hinzufügen-Feld werden nicht gefiltert.
5. **Tage und Events.** Die Tage bleiben klappbar, „Alle Tage auf-/zuklappen“ bleibt. Die Gruppen kommen aus `groupEventsByDay`, leere Events eingeschlossen. Je Event:
   - `h3` mit „({k} Bilder)“; k zählt nur Fotos im Album.
   - Die Motivzeile, gebildet nur aus den Fotos im Album.
   - Das Raster `grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-6` mit den Kacheln im Album. Seine **letzte Zelle ist das Hinzufügen-Feld**.
   - Im leeren Event steht zuerst „Kein Bild im Entwurf“ (`DRAFT_EMPTY_EVENT_TEXT`), darunter ein Raster nur mit dem Hinzufügen-Feld.
   - Die Gestrichen-Zeile, nur wenn es im Event Gestrichenes gibt.
6. **Abschluss** unter dem letzten Tag: `section` mit `border-t border-separator pt-6` und `h2` „Stand des Entwurfs“.
   - Erster Satz: „{n} Fotos im Album, Richtwert etwa {r}.“
   - Zweiter Satz: „Deine Eingriffe: {a} aufgenommen, {g} gestrichen.“ Bei 0/0 lautet er „Keine Eingriffe – der Vorschlag gilt unverändert.“
   - Dritter Satz: „Nichts muss bestätigt werden; du kannst jederzeit weiterarbeiten.“
   - Darunter die **einzige primäre Schaltfläche** der Seite: `Button asChild` (default) „Zur Endauswahl“.
   - Es gibt keinen Zustand „fertig“, es wird nichts gespeichert.

### Kachel im Album (`CurationPhotoTile`)

- **Kennzeichen im Kartenkörper:** „Vorschlag“ oder „Aufgenommen“ (siehe Tabelle). Das bestehende Badge „nicht vorgeschlagen“ bleibt an aufgenommenen Kacheln, die der Lauf nicht trägt.
  - `status={inAlbum ? undefined : 'rejected'}` und `RatingBadge` entfallen auf dieser Kachel. An ihre Stelle tritt das Album-Zustandskennzeichen aus der neuen Begriffsquelle.
- **Handlungen untereinander:** `flex-col gap-4`, `h-11 sm:h-8`.
  - `outline` „Streichen“, zugänglicher Name „Streichen: {Pfad}“.
    - Kein `aria-pressed`. Nicht `destructive`, wegen der Kollision mit dem Kennzeichen „Gestrichen“.
    - Ein Druck streicht, ohne Bestätigung. Während der Anfrage ist die Fläche `busy` und gesperrt.
  - `ghost` „Alternativen“, zugänglicher Name „Alternativen: {Pfad}“, mit `aria-expanded` und `aria-controls` auf das Band.
- **Gewählte Kachel** (Band offen): anliegende Akzentkante `border-2 border-accent`.
- **Unverändert:** Die Bildfläche öffnet die Großansicht („Großansicht: {Pfad}“). Info-Popover, Qualitätsstufe und Begründung bleiben.

### Alternativen-Band (`DraftAlternativesBand`)

- **Öffnen:** Ein Druck auf „Alternativen“ fügt eine volle Rasterzeile (`col-span-full`) nach dem letzten Element der Rasterzeile der gewählten Kachel ein. Die Spaltenzahl wird aus dem gerenderten Raster gelesen. Auf der Seite ist höchstens ein Band oder Panel offen; ein weiteres schließt das offene.
- **Aufbau:** `bg-surface rounded-lg border border-border p-3`.
  - Überschrift `h4` (`tabIndex={-1}`): „Alternativen zu {Dateiname}“.
  - 3–4 Alternativen in Serverreihenfolge; auf dem Desktop `grid-cols-4`, auf dem Handy 2×2.
  - Je Alternative: Bild (eingepasst, `rounded-md`), Dateiname (`font-mono text-xs truncate`) und Qualitätsstufe. Gestrichene tragen das Kennzeichen „Gestrichen“.
  - Je Alternative `outline` „Tauschen“, zugänglicher Name „Tauschen: {Pfad}“, `h-11 sm:h-8`.
  - Darunter ~~`ghost sm` „Alle Alternativen“ (bestehender `DraftAlternativesDialog`) und~~ `ghost sm` „Schließen“. *(Spec [`0578`](0578-alternativen-serie-und-hinzufuegen.md): Umschalter „Alle Fotos des Events“ über dem Raster.)*
- **Laden:** vier Platzhalter, `role="status"`, „Alternativen werden geladen…“.
- **Fehler:** `Alert` mit „Erneut versuchen“.
- **Leer:** „Keine weiteren Fotos in diesem Event.“ Ohne ~~„Alle Alternativen“~~ Umschalter *(Spec [`0578`](0578-alternativen-serie-und-hinzufuegen.md))*.
- **Fokus:**
  - Beim Öffnen auf die Überschrift.
  - Esc und „Schließen“ geben ihn an „Alternativen“ zurück.
  - Nach dem Tausch schließt das Band. Der Fokus geht auf „Streichen“ der neuen Kachel (`focusDecision`), bei Bedarf mit `scrollIntoView({block:'nearest'})`.
- **Nach dem Tausch:** Das ersetzte Foto ist gestrichen und ausgeblendet. Es folgt der Rückgängig-Hinweis „Getauscht“.

### Hinzufügen-Feld

- **Auslöser:** Die letzte Rasterzelle hat die Grundfläche einer Kachel: `rounded-lg border border-border-control bg-surface`, mittig „Foto hinzufügen“.
  - Nativer Button, zugänglicher Name „Foto hinzufügen: {Eventname}“, mit `aria-expanded` und `aria-controls`.
- **Panel:** Konstruktion und Einfügestelle wie beim Band, `h4` „Foto zu {Eventname} hinzufügen“.
  - Kandidaten in Serverreihenfolge, 8 je Seite, darunter `ghost sm` „Weitere Fotos“.
  - Gestrichene tragen „Gestrichen“. Im Ausschuss aussortierte Fotos erscheinen nie.
  - Je Kandidat `outline` „Hinzufügen“, zugänglicher Name „Hinzufügen: {Pfad}“, `h-11 sm:h-8`.
  - Geladen wird erst beim Öffnen.
- **Nach dem Hinzufügen:**
  - Das Panel bleibt offen, und der Kandidat verlässt die Liste.
  - Das Foto steht an seiner zeitlichen Stelle als „Aufgenommen“, auch wenn es ein gestrichenes vorgeschlagenes war. Die Zahl im Album steigt um genau eins.
  - Der Fokus geht auf „Hinzufügen“ des nächsten Kandidaten, sonst des vorigen, sonst auf die Überschrift. Bei leerer Liste steht dann „Keine weiteren Fotos in diesem Event.“
  - Es gibt keinen Rückgängig-Hinweis. Ein offener Hinweis endet.
  - Über dem Richtwert gibt es weder Rückfrage, Warnung noch Sperre.
- Laden, Fehler und leer wie beim Band.

### Gestrichene Fotos

- **Streichen:** Die Kachel fällt ohne Animation heraus, nichts rückt nach. Im selben Render ändern sich:
  - die Zahl im Album,
  - die Eingriffszahl,
  - die Bildzahl des Events,
  - die Motivzeile.

  Danach erscheint der Rückgängig-Hinweis.
- **Fokus nach dem Streichen:** auf „Streichen“ der nachfolgenden Kachel im Event, sonst der vorigen, sonst auf die Gestrichen-Zeile des Events. Nie auf `body`, kein Scrollsprung.
- **Gestrichen-Zeile** unter dem Raster: `ghost sm` „{N} gestrichen – anzeigen“ bzw. „{N} gestrichen – ausblenden“, mit `aria-expanded` und `aria-controls`. Der Zustand gilt je `eventId` und wird nicht gespeichert.
  - Aufgeklappt folgt ein eigenes Raster derselben Klasse.
  - Die Kacheln tragen das Kennzeichen „Gestrichen“ (`x-circle` und Wort) und einen durchgestrichenen Dateinamen in `--text-muted`. Die Bildfläche bleibt voll hell.
  - Je Kachel `outline` „Wieder aufnehmen“, zugänglicher Name „Wieder aufnehmen: {Pfad}“. Ohne „Alternativen“; die Großansicht bleibt erreichbar.
- **Wieder aufnehmen:**
  - Das Foto kehrt an seine Stelle zurück: als „Vorschlag“, wenn der Vorschlag es trägt, sonst als „Aufgenommen“.
  - Der Fokus geht auf „Wieder aufnehmen“ der nächsten gestrichenen Kachel, sonst der vorigen. Ist die Liste leer, verschwindet die Zeile, und der Fokus geht auf „Streichen“ der zurückgekehrten Kachel.
  - Es gibt keinen Rückgängig-Hinweis.

### Rückgängig-Hinweis (`UndoToast`)

- **Auslöser:** nur Streichen und Tausch.
- **Inhalt:**
  - Vorschaubild 40px (`size-10 rounded-md`) des ausgeblendeten Fotos.
  - Titel in `--text-h`: „Gestrichen“ bzw. „Getauscht“.
  - Dateiname (`font-mono text-xs truncate`).
  - Rechts `secondary sm` „Rückgängig“.
  - Sichtbar ergibt das „Gestrichen – Rückgängig“.
  - Fläche `--elevated`, Rand 1px `--border-control`, `rounded-md p-3`.
- **Lage:** `fixed` oben unter der App-Kopfzeile, über Seitenkopf und Kopfleiste (`z-20`, unter Dialog und Großansicht). Auf dem Handy 16px Seitenrand; ab `sm` `max-w-md`, mittig.
- **Verweildauer 8 s.**
  - Ein Zeiger darüber hält die Zeit an (nur `(hover: hover) and (pointer: fine)`), ebenso Fokus darin. Danach läuft die Restzeit weiter.
  - Ein- und Ausblenden höchstens als Deckkraftübergang von 150 ms; unter `motion-reduce` ohne Übergang.
- **Ende:**
  - nach Ablauf,
  - nach erfolgreichem Rückgängig,
  - mit Esc bei Fokus darin,
  - mit jedem neuen Handgriff auf der Seite. Er ersetzt den Hinweis; Rückgängig gilt nur für den letzten Handgriff.

  Es gibt keinen Schließen-Knopf.
- **Rückgängig:**
  - Während der Anfrage ist der Knopf `busy` und die Zeit steht. Die Sperre gilt für beide Ids.
  - Erfolg: Der Hinweis schließt. Der Vorzustand ist wiederhergestellt, nach einem Tausch steht das ursprüngliche Foto wieder an seiner Stelle und die Alternative ist weg. Der Fokus geht auf „Streichen“ des wiederhergestellten Fotos.
  - Fehlschlag (`409` oder anderer Fehler): Der Hinweis bleibt. An Stelle des Knopfs steht der Grund in `--danger-text`; das Server-`detail` steht als Textknoten. Die 8 s beginnen neu.
- **Live-Region:** Titel und Dateiname liegen in einem **dauerhaft eingehängten** `role="status"`, das ohne Inhalt keine Höhe hat. Die Schaltfläche liegt außerhalb davon. Der Fokus wird nicht in den Hinweis gezogen.
- **Zweiter Weg:** Die Gestrichen-Zeile direkt am Fokus trägt für Tastatur und Screenreader.

### Endauswahl: Zustandswörter (Umfang nach Produktentscheidung)

Aus der Endauswahl ändern sich nur die Haltungszeilen je Teilnehmer in `SelectionPhotoTile` (`StanceBadge`). Alles andere bleibt unverändert.

| Haltung (`participantStance`) | bisher | neu |
|---|---|---|
| `taken` | `RatingBadge` „Album-würdig“ | „Aufgenommen“ (gefüllt, `book`) |
| `struck` | `RatingBadge` „Verworfen“ | „Gestrichen“ (gefüllt, `x-circle`, `data-struck`) |
| `untouched` und `photo.ranking?.proposed === true` | „–“ / „Unbewertet“ | „Vorschlag“ (Vorschlags-Konstruktion, `cog` + `book`) |
| `untouched` und nicht vorgeschlagen | „–“ / „Unbewertet“ | neutrales „–“, zugänglicher Name „Nicht im Entwurf“ |

- Die Zeilenform „{username}: {Kennzeichen}“, die Zuordnung über `user_id` und die Liste `aria-label` „Haltung zu {Pfad}“ bleiben.
- Ebenfalls unverändert: „gemeinsam entschieden“, `setAside` (herausgenommen), die Entscheidungsflächen „Aufnehmen“, „Nicht aufnehmen“, „Herausnehmen“, die Sichten „Unterschiede“ und „Endauswahl“ sowie die Leerzustände.
- `participantStance` wird nicht geändert. Die Unterscheidung bei `untouched` liest das lauf-globale `ranking.proposed` an der Ansicht. Zur Endauswahl gehört weiterhin keine Ableitung über `isInAlbum`.
- 360 px: Die Haltungszeilen stehen weiter untereinander, die Kennzeichen umbrechen nicht. „Aufgenommen“ ist das längste Wort, etwa 11 Zeichen in `text-xs`. Bei 158px Kachelbreite passt es mit Benutzernamen `truncate` (bestehendes `min-w-0 truncate`).

### Zustände der Seite

- **Laden:** sechs Platzhalter wie bisher (`role="status"`, „Fotos werden geladen…“). Kein Erklärtext, keine Kopfleiste, keine Zahlen.
- **Ladefehler:** `Alert` mit „Erneut versuchen“ wie bisher.
- **Fehler eines Handgriffs:** Streichen, Wieder aufnehmen, Tausch und Hinzufügen sind nicht optimistisch. Bei einem Fehler ändert sich nichts. Am Ort der Handlung erscheint ein `Alert` mit dem Server-`detail`: in der Kachelfußzeile, im Band bzw. Panel oder in der Gestrichen-Liste. Der Fokus bleibt auf dem Auslöser.
- **Leer:** Bei `events.length === 0` erscheint `DRAFT_EMPTY_TEXT` mit dem Weg zur Kriterien-Bewertung. Der Cloud-Freigabe-Text hat Vorrang. Ein leeres Event ist kein Leerzustand der Seite.
- **Gestrichene eingeblendet**, **Alternativen offen**, **Hinzufügen-Feld offen:** siehe oben.

### Handy, 360 px

- **Raster:** zwei Spalten. Die Kachelhandlungen stehen untereinander und sind sichtbar 44px hoch. Kein waagerechtes Scrollen.
- **Kopfleiste:** drei Zeilen. „Zur Endauswahl“ steht neben Zeile 1, der Eventname wird gekürzt.
- **Band und Panel:** volle Breite, Kandidaten 2×2. ~~„Alle Alternativen“,~~ „Weitere Fotos“ und „Schließen“ dürfen umbrechen. *(Spec [`0578`](0578-alternativen-serie-und-hinzufuegen.md))*
- **Rückgängig-Hinweis:** 16px Rand. Der Dateiname wird gekürzt, der Knopf nie.
- **Bedienung:** Alles ist per Touch erreichbar. Das Anhalten per Zeiger entfällt; der dauerhafte Weg zurück ist die Gestrichen-Zeile.
- **E2E:**
  - `tap-targets`, `no-horizontal-scroll` und `popover-position` auf `/^(Streichen|Wieder aufnehmen): /`, „Tauschen: …“, „Hinzufügen: …“, „Foto hinzufügen: …“ und „Rückgängig“ umstellen.
  - Die neuen `h-11`-Fundstellen (Band, Panel, Gestrichen-Liste) fallen unter heißer Pfad und gehören in die Freigabeliste des Vertragstests.
  - Die Endauswahl misst `no-horizontal-scroll` weiter in beiden Sichten.

### Barrierefreiheit

- „Vorschlag“, „Aufgenommen“ und „Gestrichen“ sind ohne Farbe unterscheidbar: über Zahnrad, Rand gegen Füllung, Symbol, Wort und bei „Gestrichen“ die Durchstreichung. Das Wort ist der zugängliche Name.
- Entscheidungsflächen nennen die Handlung. Die Beschriftung ist der Anfang des zugänglichen Namens (WCAG 2.5.3).
- Fokusregeln nach Streichen, Tausch, Rückgängig, Wieder aufnehmen und Hinzufügen wie oben; der Fokus landet nie auf `body`.
- Eine Live-Region gibt es nur für den Rückgängig-Hinweis. Kopfleiste und Zähler sind bewusst nicht live.
- Erklärtext, Gestrichen-Zeile, Band und Hinzufügen-Feld sind Aufklapper mit `aria-expanded` und `aria-controls`. Esc schließt Band und Panel.
- Keine neue Bewegung, nur Deckkraftübergänge bis 150 ms.

### Bezug zum Design-System

Neu in `specs/architecture/0004-design-system.md` und im Skill `design-system`:
- „Gestrichenes verlässt die Ansicht, je Gruppe einblendbar“
- „Rückgängig-Hinweis nach einer ausblendenden Handlung“, die einzige benannte Ausnahme von „kein Toast-Verhalten“
- „Die Entscheidungsfläche nennt die Handlung“
- „Band am gewählten Element“
- „Zuklappbarer Erklärtext mit gemerktem Zustand“
- „Mitlaufende Kopfleiste mit Position“
- „Zustandswörter des Albums: Vorschlag / Aufgenommen / Gestrichen“

„Verworfene Kachel bleibt stehen“ gilt für den Album-Entwurf nicht mehr; für die Herausnahme in der Endauswahl gilt es weiter. Unter Bekannte Lücken steht ein Punkt zu Zeit und Lage des Hinweises. Es gibt keine neue Abhängigkeit.

## Security

Einstufung: **sicherheitsrelevant, kein Blocker.** Kein Secret, kein externer Dienst, kein Cloud-Aufruf, kein zusätzlicher Bilddatenfluss, keine Migration, kein neuer Fremdtext in Antwort, Persistenz oder Log. Neu sind:

- ein Lese-Endpunkt mit nutzerabhängiger Antwortmenge,
- ein Schreibendpunkt, der zwei Bewertungszeilen aus einem vom Client genannten Vorzustand wiederherstellt,
- ein optional gewordener Objektparameter,
- eine geänderte Antwort eines Schreibendpunkts,
- der erste Wert in `localStorage` neben dem JWT.

Die Auflagen der Specs 0429, 0430 (S1–S14), 0431 und 0432 (S1–S14) gelten unverändert weiter. Wo unten „S2/S3/S14 der Spec 0432“ steht, sind die Auflagen des Austauschs gemeint. „S2/S3/S14 der Spec 0430“ meint die Auflagen des Alternativen-Endpunkts bzw. des Entwurfszweigs. Abgeglichen mit `specs/architecture/0003-securitykonzept.md`; dort ist ein Abschnitt ergänzt (siehe Ende).

**S1 — Beide neuen Endpunkte tragen die Auth-Dependency ausgeschrieben, haben je einen eigenen, pfadbenannten 401-Nachweis und begrenzte Pfad-Ids.**

- `GET /projects/{project_id}/album-draft` und `POST /projects/{project_id}/draft/exchange/undo` liegen in `photos.router`. Dieser Router hat bewusst keine router-weite `dependencies`-Liste und keinen Vollständigkeitstest.
- Ein vergessener `current_user`-Parameter ist dort still öffentlich. Beim Lesepfad ist dann der Entwurf offen, beim Rückgängig-Endpunkt entsteht ein unauthentifizierter Schreibzugriff auf zwei Bewertungszeilen.
- `project_id` ist `Annotated[int, PathParam(ge=1, le=MAX_QUERY_POSITION)]`, nach dem Muster der Duplikat-Endpunkte.
- Die `401` steht vor jeder Aussage über das Projekt.
- `DELETE /photos/{id}/rating` behält seinen 401-Nachweis.

**S2 — Die Projektbindung des Lesepfads ist eine UND-Bedingung über alle drei Zweige der Vereinigung. „Eigen“ heißt in allen dreien `current_user`.**

- Der dritte Zweig von `_draft_photo_ids` (`ranking.photo_id IS NOT NULL AND own.status = REJECTED`) steht **innerhalb** des bestehenden `or_(…)`.
- `Photo.project_id == project_id` bleibt außerhalb davon.
- Die Rangzeile bleibt per `outerjoin` an `criterion_scoring_run_id == latest_run_id` gebunden, und dieser Wert stammt aus `_latest_successful_criterion_scoring_run_id(session, project_id)`.
- Alle Zweige lesen denselben Alias `own_rating` mit `own_rating.user_id == current_user.id` in der Join-Bedingung.
- **Untersagt:**
  - ein zweiter `Rating`-Alias ohne Nutzerbedingung für den neuen Zweig,
  - ein Projektprädikat innerhalb des `or_`,
  - eine Rangzeile ohne Laufprädikat.
- Angriffsmodell, zweifach:
  - Ohne Laufbindung kommen kohärent aussehende Fotos eines fremden Projekts in die Antwort, denn `PhotoRanking` trägt keine `project_id`.
  - Ohne Nutzerbedingung stehen die Streichungen des anderen als eigene in der Gestrichen-Zeile und im Zähler „gestrichen“. Keine Anzeige weist das als falsch aus.
- `events` stammt ausschließlich aus `Event.criterion_scoring_run_id == latest_run_id`, wird **einmal** geladen (S14 der Spec 0430) und nur über `_event_out` gebildet. Nur dort steht die Mitgliedschaftsprüfung des Ortsteils (`_event_place_out`, M8).
- Ohne erfolgreichen Lauf gilt `events: []` und `items: []`.

**S3 — Der alte Entwurfsmodus scheitert laut.**

- An `GET /projects/{id}/photos` steht `draft: None = Query(None, include_in_schema=False)`. Die Antwort ist `422` in **beiden** Belegungen.
- Angriffsmodell: Ein vom Service Worker (`registerType: 'autoUpdate'`) noch nicht ersetzter Client fiele mit `draft=true` sonst still in den Listing-Zweig. Er zeigte dann den vollen Bestand als Entwurf, mit einem Zähler, der niemandes Eingriffe misst.

**S4 — Die Cache-Schlüssel-Auflage gilt für den neuen Lesepfad, und der Entwurf trägt die Identität im Client-Schlüssel.**

- **HTTP:** Bekommt `GET /projects/{id}/album-draft` eine Zwischenspeicherung, ein `ETag` oder ein `Cache-Control` über `no-store` hinaus, muss der Schlüssel den Nutzer enthalten. Menge **und** Felder (`PhotoOut.suggestion`) sind nutzerabhängig.
- Die SICHERHEIT-Passage am Docstring von `_to_photo_out` wird umgeschrieben, nicht gelöscht. Der Entwurfsmodus von `GET …/photos` wird dort durch den neuen Endpunkt ersetzt.
- **Client, Ausgangslage:**
  - Der `QueryClient` ist ein Modul-Singleton (`frontend/src/main.tsx`).
  - Die Anmeldung ist eine SPA-Navigation ohne Neuladen.
  - Das Abmelden (`App.tsx::handleLogout`) leert nur das Token.
- Ohne Identität im Schlüssel sieht der zweite Nutzer an einem gemeinsamen Gerät den Entwurf des ersten, bis der Refetch abgeschlossen ist. Das schließt „Deine Eingriffe“ ein, nach der Statistik die zweite rein personenbezogene Aggregatzahl.
- **Muss:**
  - Entwurfs- und Alternativen-Schlüssel hängen die angemeldete Identität an, nach dem Muster `projectStatsQueryKey`. `decodeUsername` dient dabei nur der Cache-Unterscheidung.
  - Die Identität steht **hinter** dem Präfix `['photos', projectId]`. So trifft die breite Invalidierung beide Schlüssel weiter, und die Ausnahme für den eigenen Entwurfsschlüssel greift über ein Präfix.

**S5 — Der Rückgängig-Endpunkt bindet beide Ids wortgleich wie der Austausch (S2/S3/S14 der Spec 0432), und zwar vor der Vorbedingung.**

- Beide Ids werden ausschließlich über `_exchange_sides` mit dem jüngsten erfolgreichen Lauf **dieses** Projekts aufgelöst, nie über `session.get(Photo, …)`.
- `event_id`, Modellstufe und Qualität des Gegenereignisses stammen ausschließlich aus den Rangzeilen.
- Diese Fälle ergeben **denselben** `422` mit `_EXCHANGE_REFUSAL`:
  - gleiche Id auf beiden Seiten,
  - kein erfolgreicher Lauf,
  - unbekannte Id,
  - projektfremde Id,
  - verschiedene Events.
- Reihenfolge, verbindlich: `404` Projekt → `422` Bindung → `409` Vorbedingung → Schreiben.
- Angriffsmodell:
  - Stünde die Vorbedingung vorn, unterschiede die Antwort eine unbekannte Id (`409`, keine eigene Zeile) von einer projektfremden (`409` oder `422`, je nach eigener Bewertung im fremden Projekt). Das ist das Existenz-Orakel, das S14 der Spec 0432 ausschließt.
  - Ohne die Bindung stellte der Endpunkt kohärent zwei Bilder eines fremden Projekts wieder her.

**S6 — Der Body trägt genau vier Felder. Die beiden Vorzustände sind ein geschlossener Vorrat ohne Vorgabewert.**

- `DraftExchangeUndoIn` hat `model_config = ConfigDict(extra="forbid")`.
- `photo_id` und `replaced_photo_id` sind je `Field(ge=1, le=MAX_QUERY_POSITION)`.
- `photo_previous_status: Literal[RatingStatus.REJECTED] | None` und `replaced_previous_status: Literal[RatingStatus.ALBUM_WORTHY] | None` sind **Pflichtfelder**: nullbar, aber ohne Default.
- Nicht im Body: `user_id`, `event_id`, `weight`, `kind`, `criterion_scoring_run_id`, `favorite`.
- Angriffsmodell:
  - Ein Default `None` machte ein vergessenes oder abgeschnittenes Feld zu einer stillen Rücknahme der Albumentscheidung.
  - Ein offener Vorrat ließe die Wiederherstellung Zustände schreiben, die kein Austausch erzeugt hat.
- Mit dem geschlossenen Vorrat kann der Endpunkt nichts, was der Nutzer nicht schon über `PUT`/`DELETE /photos/{id}/rating` an seinen eigenen Zeilen könnte. Er ist deshalb keine Rechteausweitung, auch wenn ihm kein Austausch vorausging.

**S7 — Vorbedingung, Schreiben und Gegenereignis sind eine Transaktion über die eigenen Zeilen. Bei `409` entsteht nichts.**

- Die Vorbedingung liest ausschließlich die eigenen Zeilen (`(photo_id, current_user.id)`), nie die des anderen Nutzers. Sonst entschiede dessen Zustand über den eigenen Schreibweg.
- Ist `photo_id` nicht `album_worthy` oder `replaced_photo_id` nicht `rejected`:
  - `409` mit festem Text, ohne Rückspiegelung des gelesenen Zustands,
  - keine Zeile geändert, kein Ereignis.
- Andernfalls:
  - zweimal `write_own_rating(record=False)`; `favorite` bleibt auf beiden Seiten unberührt (S7 der Spec 0430), und die Invariante (nie `status IS NULL AND favorite IS FALSE`) wird dort und nur dort durchgesetzt,
  - genau **ein** `record_exchange(photo_id=replaced, replaced_photo_id=photo, …)`,
  - genau **ein** `commit` (S5 der Spec 0432).
- Der Zweig `IntegrityError` → `409` der Schreibstelle bleibt.
- **Keine Zeilensperre.** Die Vorbedingung fängt die Wiederholung nach Abschluss ab: Doppelklick, zweiter Tab, erneuter Versuch nach Zeitüberschreitung. Zwei wirklich gleichzeitige Rücknahmen haben dieselbe Eigenschaft, die der Austausch ganz ohne Vorbedingung trägt, begrenzt auf die eigenen Zeilen.
- Kein neuer Hebel auf die Gewichtsableitung: Jedes Gegenereignis kann ein Aufrufer heute schon über einen Austausch in Gegenrichtung erzeugen.

**S8 — Ohne `photo_id` entfällt am Alternativen-Endpunkt die Sortierung, nie die Bindung.**

- Signatur: `photo_id: int | None = Query(None, ge=1, le=MAX_QUERY_POSITION)`.
- Ist `photo_id` gesetzt, gilt S3 der Spec 0430 unverändert: Auflösung über eine Rangzeile desselben Laufs und Events, sonst `200`, `[]`, `0` vor jeder weiteren Abfrage.
- Fehlt es, steht die Kandidatenabfrage mit Lauf- **und** Event-Prädikat unverändert (S2 der Spec 0430). Eine unbekannte oder projektfremde `event_id` ergibt `200` mit `items: []` und `total: 0` auf demselben Antwortpfad.
- **Untersagt:**
  - ein Ersatz-Bezugsbild, etwa das erste Foto des Events,
  - eine ausgeweitete Menge ohne Event-Prädikat,
  - eine Bindung, die nur im Zweig mit Bezugsbild steht.
- `event_id`, `limit` (≤ 200) und `offset` behalten ihre Grenzen.

**S9 — `DELETE /photos/{id}/rating` liefert den eigenen Zeilenzustand und sonst nichts.**

- Die Antwort ist die von `write_own_rating` gebildete `RatingWriteOut`. `user_id` stammt aus `current_user` (S7 der Spec 0430). Es kommt kein Feld hinzu.
- Die Antwort ist idempotent. Sie unterscheidet „Zeile bestand“ von „bestand nicht“ nur, soweit `favorite` die Zeile trägt, also nur über den eigenen Zustand.
- Der Satz „`DELETE` antwortet `204`, ob eine Zeile bestand oder nicht“ (S9 der Spec 0430) gilt sinngemäß als `200` weiter.
- `404` bei unbekanntem Foto bleibt unverändert.

**S10 — Die Oberfläche leitet Zugehörigkeit, Zähler und Wiederaufnahme ausschließlich aus dem eigenen Zustand ab.**

- `draftMembership`, `draftCounts` und `reAddDecision` lesen den eigenen Status nur über `utils/ownRating.ts` (`findOwnRating`/`ownRatingStatus`, S6 der Spec 0430).
- „Vorgeschlagen“ kommt nur aus `ranking.proposed`.
- Nie `ratings.some(…)`, nie „erster Eintrag“, nie `ratings.length`.
- In der Endauswahl ordnen die Haltungszeilen weiter über `user_id` zu. „Vorschlag“ liest allein das lauf-globale `ranking.proposed`.
- Prüfbar:
  - Ein nur vom anderen Nutzer gestrichenes Foto erscheint in der eigenen Ansicht weder in der Gestrichen-Zeile noch im Zähler „gestrichen“.
  - Ein nur vom anderen aufgenommenes Foto erscheint weder als „Aufgenommen“ noch im Album.

**S11 — Dateiname, Eventname und Server-`detail` bleiben Text.**

- Geltungsbereich: `AlbumDraftPage`, alle neuen Bausteine (`DraftExplainer`, `DraftEventSection`, `DraftAlternativesBand`, `UndoToast`, Kopfleiste, Abschluss) und die geänderten Haltungszeilen der Endauswahl.
- Diese Werte erscheinen ausschließlich als React-Textknoten oder als von React maskierte Attribut-Props (`aria-label`). Nie `dangerouslySetInnerHTML`, nie in `href`, `src`, `style` oder `url()`.
- Das gilt auch für das Server-`detail` im Rückgängig-Hinweis und in den Fehler-`Alert`s, einschließlich des Rohwert-Echos einer FastAPI-`422` (S4 der Spec 0430).
- Der zusammengesetzte Eventname (`eventPlaceName`) ist nie React-`key`, nie DOM-`id`, nie Teil eines CSS-Selektors und nie Aufsuchschlüssel. Aufklappzustand, `aria-controls` und Positions-Hook schlüsseln über `event.id` bzw. `useId`.
- Das Vorschaubild des Hinweises kommt über den bestehenden authentifizierten Bildabruf nach Foto-Id, nie aus einem Pfad.
- Angriffsmodell: Datei- und Ordnernamen stammen aus OpenCloud, der Ortsteil des Eventnamens aus einer Modellantwort bzw. einem Fremddatensatz. Als HTML gerendert läuft ein präparierter Name im Browser beider Nutzer, während das JWT in `localStorage` liegt.

**S12 — Der Erklärtext merkt sich einen Wahrheitswert, nie Inhalt, und liest ihn als nicht vertrauenswürdige Eingabe.**

- **Schlüssel:** festes Präfix plus Anmeldename aus `decodeUsername`. Der Anmeldename dient nur zur Unterscheidung, nicht als Zugriffsentscheidung.
- **Wert:** ein einziges festes Literal für „zugeklappt“.
- **Lesen:** Nur genau dieses Literal gilt als zugeklappt. Alles andere gilt als aufgeklappt: fehlend, fremd oder beschädigt.
- Kein `JSON.parse` in eine weiterverwendete Struktur, keine Anzeige des Werts, keine Verwendung für andere Zwecke.
- **Nie gespeichert:** Projekt-Id, Foto-Id, Dateiname, Eventname, Zähler oder eine Serverantwort. Der Eintrag überlebt das Abmelden in der Profil-Ablage.
- Jeder Zugriff steht in `try/catch` (gesperrter Speicher, Private-Modus, Kontingent). Die Ausfallrichtung ist „aufgeklappt“.
- Dass der Eintrag beim Abmelden stehen bleibt, ist getragen: Er verrät nur, dass dieser Anmeldename den Text einmal zugeklappt hat.

**Ausdrücklich geprüft und ohne Befund:**

- Keine neue Datenklasse zwischen den beiden Nutzern. Die Albumentscheidungen des anderen stehen namentlich in `PhotoOut.ratings[]`. Die Menge `events` ist lauf-global und samt Ortsteil über das Listing desselben Projekts ohnehin lesbar.
- Die Zustandswörter „Vorschlag“, „Aufgenommen“ und „Gestrichen“ in der Endauswahl ändern Beschriftung, nicht Daten. Sie stammen aus einer Konstante, nicht aus Serverwerten.
- Der Lesepfad hat weiterhin kein `limit`/`offset` (S4 der Spec 0429, S14 der Spec 0430). Der dritte Zweig wächst nur bis zu den Rangzeilen des Laufs und nur durch eigene Handlungen.
- Die Rückgängig-Antwort trägt nur die beiden eigenen geschriebenen Zeilen. Die Cache-Schlüssel-Auflage greift dort nicht.
- Dass die Gestrichen-Zeile auch Verwerfungen aus dem Bildbestand zählt, betrifft nur eigene Zeilen und ist kein Sicherheitsthema.
- Kein Rate-Limiting, konsistent mit der übrigen API. Keine neue Abhängigkeit.
- `demo_state.py` bekommt nur synthetische Fälle. Screenshots aus `browse-app` und E2E tragen ausschließlich Demo-Dateinamen (Screenshot-Hygiene, Spec 0321).

**`specs/architecture/0003-securitykonzept.md`** ist ergänzt:

- ein neuer Abschnitt direkt hinter dem Austausch-Abschnitt (ADR 0100/Spec 0432) mit vier projektweiten Aussagen:
  - Wiederherstellung mit Vorzustand vom Client,
  - optionaler Bezugsparameter,
  - Cache-Schlüssel am neuen Lesepfad samt Identität im Client-Schlüssel,
  - Browser-Speicher neben dem Token;
- die neue bekannte Lücke „Der `QueryClient` überlebt den Nutzerwechsel im selben Tab“;
- der Kopfvermerk.

Bei der Umsetzung werden die beiden Ankerzeilen zum Austausch um den Rückgängig-Endpunkt und seine Nachweise erweitert. Dazu kommt eine neue Zeile für die Projekt- und Nutzerbindung des Entwurfs-Lesepfads.

## Teststrategie

Leitsatz: Jede Zusage wird auf der niedrigsten Ebene geprüft, die sie widerlegen kann. Die neuen projektweiten Muster stehen im Testkonzept, Sektion „Ein Prädikat in zwei Sprachen …“ (Issue #558).

### Backend (pytest)

- **`test_selection.py::TestTheOrderOfTheAlternatives`**: `order_alternatives(None, …)` ohne Motivstufe.
  - Ein Kandidat mit geteiltem Motiv springt nicht vor.
  - Qualität absteigend, `None` zuletzt, Gleichstand nach kleinerer Id.
  - Permutationsfall gegen die vollständige Id-Folge.
- **`test_api_photos.py`, neue Klasse `TestTheAlbumDraft`** (ersetzt `TestTheDraft`):
  - **Falltabelle** `backend/tests/data/album_draft_membership.json`: 9 Zeilen (Rangzeile keine / nicht vorgeschlagen / vorgeschlagen × eigener Status keiner / `album_worthy` / `rejected`), je Zeile eine Gegenbewertung des anderen Nutzers. Zuerst wird die Vollständigkeit des Kreuzprodukts geprüft, dann je Zeile Lage anlegen und `GET /album-draft` lesen: `out` heißt nicht in `items`, `album` und `struck` sind am eigenen Status in `items` erkennbar.
  - **Invariantenhelfer als Nachsatz jedes Falls**:
    - `events[].position` ist lückenlos 1..m und aufsteigend.
    - Jedes `item.event.id` liegt in `events`.
    - Im Album gilt genau dann, wenn der eigene Status nicht `rejected` ist.
    - Kein `rejected` ohne Rangzeile.
  - Eventliste: Ein Lauf mit Events ohne Vorschlag liefert alle Events und `items: []`. Ohne Lauf und bei einem Lauf ohne Events sind beide Listen leer. Die Zahl der SELECT-Anweisungen hängt nicht von der Zahl der Events ab (S14).
  - Eine Verwerfung über `PUT /photos/{id}/rating` an einem nicht vorgeschlagenen Foto mit Rangzeile steht in `items` als gestrichen. Ohne Rangzeile steht sie nicht darin.
  - Riegel: `GET /photos?draft=true` und `draft=false` antworten beide mit `422`.
  - Die Reihenfolge `(events.position, taken_at, id)` gilt auch mit eingestreuten gestrichenen Fotos.
  - `401`-Nachweis für den neuen Endpunkt.
- **`TestDraftAlternatives` ohne `photo_id`**:
  - Qualitätsordnung.
  - Gestrichene sind enthalten. Eigene Album-Fotos sind ausgeschlossen, auch unberührt vorgeschlagene. Aussortierte und Fotos anderer Events sind ausgeschlossen.
  - Eine `event_id` aus einem fremden Projekt ergibt eine leere Liste **und** `total == 0`.
  - Die zweite Seite ist geprüft.
  - Mit `photo_id` bleibt alles wie bisher.
- **Neu `test_api_draft_exchange_undo.py`**:
  - `401`.
  - Body: Zusatzfeld, Literalwert außerhalb von `{rejected, None}` bzw. `{album_worthy, None}`, Id außerhalb der Grenzen → `422`.
  - Ablehnungen: gleiche Id, kein Lauf, fremdes Projekt, anderes Event → `422` mit `_EXCHANGE_REFUSAL`. Eine unbekannte und eine fremde Id sind nicht unterscheidbar.
  - **`409` je Seite einzeln**: Zeilen und Ereignislog unverändert.
  - **Schnappschussgleichheit** von `GET /album-draft` und den eigenen Zeilen samt `favorite` vor dem Tausch und nach dem Rückgängig, parametrisiert 2×2 Vorzustände × mit/ohne Favoritenzeile.
  - Genau ein zusätzliches Tauschereignis in Gegenrichtung.
  - Atomarität nach dem Muster `TestTheAtomicity` (der zweite `flush` scheitert, dann bleibt nichts zurück).
- **`test_api_ratings.py`**: `DELETE` antwortet `200` mit `RatingWriteOut`; geprüft werden `status: null`, `favorite` (erhalten bzw. `false`), `photo_id` und `user_id`. Idempotent `200`/`200`.
- **`test_openapi_beschreibungen.py`**: beide neuen Endpunkte im Register.
- **`test_demo_state.py`**: je eine Zusicherung über den Lesepfad, dass der Bestand enthält:
  - ein gestrichenes vorgeschlagenes Foto
  - ein aufgenommenes nicht vorgeschlagenes Foto
  - ein gestrichenes nicht vorgeschlagenes Foto mit Rangzeile
  - ein Event ohne Vorschlag
  - in der Endauswahl je eine Haltung „Vorschlag“ und „Nicht im Entwurf“
- `test_models.py::TestTheDraftFunctionsNeverTouchTheJointDecision` deckt die neuen Funktionen von selbst ab (Gleichheit über den ganzen Quellbaum); dort ist nichts zu ändern.

### Frontend (vitest)

- **Reine Funktionen** (`utils/albumDraft.test.ts` u. a.):
  - `draftMembership` gegen dieselbe JSON-Tabelle, gelesen über `new URL('../../../backend/tests/data/…', import.meta.url)`, inklusive der Vollständigkeitsprüfung.
  - `draftCounts`: die Zählertabelle der AK als Zustandsübergänge über **eine** Fixture, Rückgängig ergibt wieder die Ausgangszahlen.
  - `reAddDecision`.
  - Kopf- und Abschlusstexte (beide Abweichungsrichtungen, 0/0-Satz).
  - `groupEventsByDay`: leere Events, Reihenfolge nach `position`, Testdaten fern von Mitternacht.
  - Positionsauswahl tabellengetrieben: vor dem ersten Abschnitt, an der Kante, zurückscrollen, zugeklappter Tag, leeres Event, Filter verbirgt alle Fotos.
  - Begriffsquelle: Einmaligkeit der drei Literale im Quellbaum (nur ganze String-Literale), die drei Wörter paarweise verschieden.
- **Hooks** (`usePhotos.test.tsx`):
  - `useDraftQuery` ruft `getAlbumDraft`.
  - `applyWrittenRating` auf `AlbumDraftOut`, mit dem Fall „verlässt die Antwortmenge“ (`DELETE` an nicht vorgeschlagenem Foto mit Rangzeile).
  - `insertDraftPhoto` mit Gleichstand auf `taken_at`.
  - `useDraftDecisionMutation`: `null` führt zu `deleteRating`; Einfügen; der Entwurfsschlüssel wird nicht invalidiert, die anderen schon.
  - `useDraftExchangeUndoMutation`: Erfolg schreibt beide; `409` lässt den Cache unberührt.
  - `useDraftAlternativesQuery`: ~~Band (`photoId`, 4), Dialog~~ Serie (`photoId`, `series`), volle Reihe *(Spec [`0578`](0578-alternativen-serie-und-hinzufuegen.md))* und Panel (ohne `photoId`, 8) ergeben drei verschiedene Schlüssel unter `['photos', id]`.
  - **Gegenfall:** `useSetRatingMutation` (Bildbestand) invalidiert den Entwurfsschlüssel.
  - **Folgentest:** Streichen → Rückgängig → Wiederaufnehmen → Hinzufügen → Tausch → Rückgängig. Nach jedem Schritt gilt Cache-Menge = Fotos mit `draftMembership ≠ out` in Sortierfolge, und `getAlbumDraft` lief insgesamt genau einmal.
- **Komponenten:**
  - `DraftExplainer`: Speicherschlüssel je Nutzer, zweiter Nutzer sieht ihn aufgeklappt, `getItem`/`setItem` werfen → aufgeklappt und bedienbar, `aria-*`, Fokus.
  - `UndoToast` unter Fake-Timern:
    - Ablauf: sichtbar bei 7 999 ms, fort bei 8 000 ms.
    - Pause partitioniert nach `matchMedia` (fein wahr/falsch) mit Restzeit; Fokus-Pause.
    - Esc; Fehlschlag mit Server-`detail` als Textknoten und Neustart der 8 s; `busy` während der Anfrage.
    - Knotenidentität des `role="status"`, der Knopf liegt außerhalb.
  - `DraftAlternativesBand`: lädt nur beim Öffnen, Serverreihenfolge, „Gestrichen“-Kennzeichen, drei Zustände, Fokusregeln, „Tauschen: {Pfad}“.
  - `DraftEventSection`: N der Gestrichen-Zeile, Aufklappen je Event ohne Speicherung, Hinzufügen-Feld, „Kein Bild im Entwurf“.
  - `CurationPhotoTile`: „Streichen: {Pfad}“ ohne `aria-pressed`; Kennzeichen je Zustand über Wort und `data-icon`; beide Datenformen von „nicht vorgeschlagen“.
  - `SelectionPhotoTile`: Haltungstabelle mit 4 Zeilen, „Nicht im Entwurf“ in **einem** Fall mit beiden Datenformen.
  - ~~`DraftAlternativesDialog`: „Gestrichen“, „Tauschen: {Pfad}“.~~ *(Dialog entfernt mit Spec [`0578`](0578-alternativen-serie-und-hinzufuegen.md); dieselben Fälle in `DraftAlternativesBand.test.tsx`)*
  - Keine CSS-Assertions; Geometrie gehört nach E2E.
- **Seite `AlbumDraftPage.test.tsx`:**
  - Verdrahtung von Kopf, Position und Abschluss (Observer-Attrappe mit Meldung je Element).
  - Streichen und Rückgängig aus beiden Vorzuständen (`DELETE` bzw. `PUT album_worthy`).
  - **Ein Fall:** Rückgängig gegen Wiederaufnehmen am vorgeschlagenen Foto mit eigenem `album_worthy`.
  - Tausch, Rückgängig und `409`.
  - Hinzufügen eines gestrichenen vorgeschlagenen Fotos ergibt „Aufgenommen“; Hinzufügen im leeren Event; über r ohne Rückfrage.
  - Fokusregeln, nie auf `body`.
  - Personenfilter: Kopf zählt alles, Abschnitte bleiben stehen, Gestrichen-Zeile und Panel sind ungefiltert.
  - Fehlerfall je Handgriff.
  - Leerzustand und Vorrang der Cloud-Freigabe; Großansicht-Sonde unverändert.
- **Wächter:**
  - `albumSelection.structure.test.ts`: die neuen Entwurfsdateien kommen in `DRAFT_FILES`. Die Endauswahl-Dateien importieren zusätzlich `draftMembership` nicht.
  - `designSystem.contract.test.ts`: Freigabeliste für `h-11` mit neuen Fundstellen (Kachel, Band, Panel, Gestrichen-Liste).

### E2E (Playwright, 360 px und Desktop)

- `tap-targets.spec.ts`: alle Handgriffnamen der AK, einschließlich „Zur Endauswahl“ und „Rückgängig“.
- `no-horizontal-scroll.spec.ts`:
  - `DRAFT_TILE_TOGGLE` wird zu `/^(Streichen|Wieder aufnehmen): /`.
  - Im Dialogfall wird `Austauschen gegen` zu `Tauschen`.
  - Neue Zustände: Band offen, Panel offen, Gestrichene eingeblendet.
  - Endauswahl wie bisher in beiden Sichten.
- **Neu `album-entwurf.spec.ts`:**
  - Kopfleiste: Nach dem Scrollen zum Abschnitt k steht „Event k von E“, die Leiste bleibt sichtbar.
  - **Schreibender Fall**, Rücksetzung im `finally` über `page.request`:
    - Streichen ergibt einen Hinweis im Sichtbereich, treffbar, Knopf nicht abgeschnitten, kein waagerechtes Scrollen.
    - `scrollY` ist unverändert, die Kopfzahlen ändern sich.
    - Nach `page.reload()` sind Kopfzahlen und Gestrichen-Zeile identisch.
    - Rückgängig stellt die Anfangszahlen wieder her, und das wird zugesichert.
- Endauswahl bei 360 px: Jedes Haltungskennzeichen ist einzeilig (`Range.getClientRects().length === 1`).
- `kuratierung-grossansicht.spec.ts` und `popover-position.spec.ts` bleiben unverändert.

### Bestehende Tests: ändern oder löschen

**Backend**
- `test_api_photos.py::TestTheDraft`: alle Fälle auf `GET /album-draft` und `{events, items}` umziehen, ohne `total`. Einzeln:
  - `test_a_rejected_photo_that_was_never_proposed_stays_out` **umkehren**: Mit Rangzeile steht das Foto als gestrichen darin, ohne Rangzeile bleibt es draußen.
  - `test_a_run_without_a_draft_answers_empty`: Die Events stehen jetzt in der Antwort.
  - `test_without_the_draft_mode_the_default_listing_answers` **löschen**, an seine Stelle tritt der Riegelfall `true`/`false` → `422`.
  - `test_limit_and_offset_stay_without_effect_in_the_draft_mode`: gegen den neuen Endpunkt (ignorierte Parameter ergeben die volle Liste).
  - `test_rejecting_a_photo_does_not_change_the_draft` und `test_a_rejected_photo_stays_in_the_draft_with_its_rating`: Die Zusage gilt weiter für die **Antwort**; Docstrings anpassen.
  - `test_the_time_assignment_costs_no_query_per_photo`: um die Eventzahl erweitern.
  - Ebenfalls auf den neuen Endpunkt: `test_a_rejected_photo_is_in_the_draft_and_among_the_alternatives`, `TestTheProposedFlag::test_proposed_is_run_global…`, `test_the_event_is_the_same_with_and_without_the_draft_mode`.
- `test_api_persons.py::test_the_filter_is_bounded`: Parameterzeile `mit-entwurf` **löschen**. Sie wäre jetzt aus einem anderen Grund grün, den der Riegelfall abdeckt.
- `test_api_ratings.py`: fünf `204`-Assertions → `200` mit Body. Den Docstring „weiterhin `204`“ (Z. ~783) und den in Z. 325 anpassen.

**Frontend**
- `api/photos.test.ts`: die beiden `draft`-Fälle **löschen**. Neu: `getAlbumDraft`, `listDraftAlternatives` ohne `photo_id` (Parameter fehlt, nicht `undefined`) und `undoDraftExchange`.
- `api/ratings.test.ts`: `deleteRating` liefert `RatingWriteOut`.
- `usePhotos.test.tsx`:
  - `useDraftQuery` „asks for the draft mode“ wird zu `getAlbumDraft`.
  - Den Mock in `useDeleteRatingMutation` auf `RatingWriteOut` umstellen.
  - `applyWrittenRating` auf `AlbumDraftOut` umstellen.
  - Den Kommentar in `useDraftExchangeMutation` „ersetztes Bild bleibt an seiner Stelle“ ändern: Es bleibt im Cache, die Ansicht blendet es aus.
- `AlbumDraftPage.test.tsx`:
  - Alle `listPhotos`-Mocks werden zu `getAlbumDraft` mit `events`.
  - `strikes a photo without reloading … without moving the tiles` **umschreiben**: Kachel weg, Reihenfolge der übrigen gleich.
  - `takes a struck photo back` geht jetzt über die Gestrichen-Zeile.
  - `exchanges in ONE write … shows BOTH photos` → ersetztes Foto ausgeblendet.
  - `is reversible: … "zuvor im Album"` **löschen**, ersetzt durch den Rückgängig-Fall.
  - `keeps an emptied event group standing` → aus der Eventliste, ohne Neuladen-Mock.
  - `laesst Tage und Gruppen ohne sichtbares Foto entfallen` **umschreiben**: Abschnitte bleiben stehen.
  - `filtert den Alternativen-Dialog nicht` → Band.
  - Alle Namen `Im Album:` werden zu `Streichen:`.
  - Die Konstante „zuvor im Album“ (Z. 24/648) entfällt.
- `CurationPhotoTile.test.tsx`: den Describe „Zweizustand Im Album ⇄ Gestrichen“ samt `aria-pressed` und `keeps the struck photo in place` **löschen** und durch Handlungsname plus Kennzeichen ersetzen. Die Alternativen-Fälle prüfen `aria-expanded`/`aria-controls`.
- `DraftAlternativesDialog.test.tsx`:
  - `marks a struck photo as "zuvor im Album"` → „Gestrichen“ aus der Begriffsquelle.
  - S6-Fall mit neuem Wort.
  - Name `Austauschen gegen` → `Tauschen`.
  - Kommentar „kein Rückgängig-Knopf“.
- `SelectionPhotoTile.test.tsx`: Z. 88–121 „Album-würdig“/„Verworfen“/„Unbewertet“ → neue Wörter; dazu die Fälle Vorschlag und Nicht im Entwurf.
- `utils/albumDraft.test.ts`:
  - `draftSizeText`-Erwartungen auf den neuen Kopftext umstellen.
  - Kommentar „gestrichenes Bild bleibt sichtbar“ in `leaves out the motifs of a struck photo` ändern.
  - `isInAlbum` nur behalten, wenn es noch Aufrufer hat; sonst mit Tests entfernen.
- `PersonsPage.test.tsx` Z. 230: Cache-Fixture auf `{events: [], items: []}` umstellen.
- `designSystem.contract.test.ts`: Fundstelle `CurationPhotoTile` `h-11 flex-1 sm:h-8` nachziehen, die neuen Fundstellen aufnehmen.
- Unverändert grün bleiben müssen, ohne angepasste Erwartung: `RatingBadge`/`RatingButtons` (Bildbestand).

**E2E**
- `tap-targets.spec.ts` Z. 184–188 und `no-horizontal-scroll.spec.ts` Z. 50, 418–436: neue Namen, Band statt Dialog als Ruhezustand.

### Testkonzept

Ergänzt (`specs/architecture/0002-testkonzept.md`):
- neue Sektion „Ein Prädikat in zwei Sprachen …“ mit sieben Mustern und zwei Einzelregeln
- Stand-Vermerk in der Sektion zu ADR 0098
- zwei Einträge unter „Bekannte Lücken“
- Datum aktualisiert

### Selbst getroffene Entscheidungen knapp unter der Abgabeschwelle (rein technisch)

- **Ort der gemeinsamen Falltabelle** unter `backend/tests/data/`. Der Server ist die Autorität. Das Frontend liest von dort nach dem bestehenden Muster aus `frontend/penpot/*.test.ts`.
- **Erster schreibender E2E-Fall**, mit API-Rücksetzung im `finally`. Ohne ihn blieben Reload-Gleichstand, Scrollposition und Hinweis-Geometrie im echten Browser ungeprüft.
- **Endauswahl-Wächter um `draftMembership` erweitert.** Grund: dieselbe Begründung wie beim bestehenden `isInAlbum`-Verbot.
- **Erweiterung der vorhandenen Observer-Attrappe** um eine Meldung je Element, statt einer zweiten Attrappe.

## Entscheidungen

- **Zustandswörter (Produktentscheidung Daniel, 2026-10-02, Option C):** „Vorschlag“, „Aufgenommen“, „Gestrichen“ sind die gemeinsame Begriffsquelle für Album-Entwurf und Endauswahl (Haltungszeilen). Der Bildbestand behält „Album-würdig“/„Verworfen“. Der Ausschluss „Endauswahl-Seite“ ist für deren Zustandswörter aufgehoben.
- **Cache-Schlüssel:** Abweichend vom Architekturabschnitt („Schlüssel `['photos', id, 'draft']` bleibt“) gilt Security-Auflage S4: Entwurfs- und Alternativen-Schlüssel tragen die angemeldete Identität hinter dem Präfix `['photos', projectId]`; die Ausnahme des eigenen Entwurfsschlüssels von der Invalidierung greift über ein Präfix/Prädikat.
- **Personenfilter:** Abweichend von Spec 0292 (UI/UX, „Tage und Eventgruppen ohne sichtbares Foto entfallen“) bleiben im Album-Entwurf Eventabschnitte ohne sichtbares Foto stehen, weil Hinzufügen-Feld und Gestrichen-Zeile zum Event gehören und „Event p von E“ stabil bleiben muss. Für den Album-Entwurf ist diese Zusage von 0292 abgelöst.
- **Grenzfälle (architect):** Als gestrichen gilt jedes eigene `rejected` an einem Foto mit Rangzeile im Lauf, auch aus dem Bildbestand. Hinzufügen und Tausch mit einem gestrichenen vorgeschlagenen Foto ergeben „Aufgenommen“; zurück zum Vorschlag führen nur Rückgängig und „Wieder aufnehmen“ aus der Gestrichen-Zeile. Ohne Bezugsbild ordnet das Hinzufügen-Feld nach Qualität. Der Erklärtext-Zustand liegt in `localStorage` je Browser und Nutzer.
- **Zähler** werden aus dem Zustand abgeleitet, nicht aus Handgriffen gezählt (Tabelle in den Akzeptanzkriterien).
- **Rückgängig nach Streichen** hat keine Precondition; ein veralteter Stand aus einem zweiten Tab wird überschrieben. Hingenommen: Der Vorzustand stammt aus derselben Sitzung, und die Gestrichen-Zeile bleibt als zweiter Weg.
- **`DELETE /photos/{id}/rating`** antwortet künftig `200` mit `RatingWriteOut` statt `204`.
- Alle vier Konsultationen (architect, ux-ui-designer, test-engineer, security-engineer) sind gelaufen; keine wurde übersprungen.

## Offene Fragen

- Penpot-Abgleich beim Umsetzen: Rolle des Bausteins `input` in der Ansicht `album-entwurf` (hier ist das Hinzufügen-Feld eine Schaltfläche mit Panel), Lage des Alternativen-Bands, Aufteilung der Kopfleiste. Ein Widerspruch zum Brett wird als Befund gemeldet. Die Penpot-Ansichten für Entwurf und Endauswahl zeigen die neuen Zustandswörter noch nicht.

## Out of Scope

- Endauswahl-Seite außer ihren Zustandswörtern; Pipeline-Schritt Kuratierung samt Richtwert-Einstellung; Bildung des Vorschlags; Projektnavigation; Tastenkürzel; Entscheidungen in der Großansicht.
- Leeren des `QueryClient` beim Abmelden/Nutzerwechsel (vorbestehende Lücke, im Sicherheitskonzept vermerkt).
- Pfadgrenze für `project_id` am bestehenden `POST /projects/{id}/draft/exchange`.
