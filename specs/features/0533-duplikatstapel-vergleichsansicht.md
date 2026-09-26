# 0533 - Duplikatgruppen im Ausschuss als Stapel und in einer Vergleichsansicht

**Status:** Accepted
**Erstellt:** 2026-09-26
**Bezug:** [Issue #533](https://github.com/TheRealKoller/photosort/issues/533), ADR
[`0125`](../decisions/0125-duplikatentscheidung-des-ausschusses-in-der-vergleichsansicht.md)

**Umfang:** über dem Richtwert von rund 200 Zeilen. Grund: Zwei Ansichten, eine neue Antwortform, ein
neuer Schreibweg und zwölf Sicherheitsauflagen in der geschützten Dreiteilung müssen samt der
namentlich umzuschreibenden Bestandstests für den Umsetzungslauf vollständig stehen.

## Ziel

Wer den Ausschuss durchsieht, soll Duplikat-Gruppen schon in der Übersicht als zusammengehörige
Stapel erkennen und die Wahl unter den Aufnahmen in einer Ansicht treffen, die die ganze Serie, ihre
Messwerte und die getroffene Wahl je Aufnahme gleichzeitig zeigt. Heute ist die Duplikatentscheidung
auf zwei getrennte Oberflächen verteilt, und der Einstieg aus dem Ausschuss ist bei der letzten
Überarbeitung entfallen; beides soll wieder zusammenkommen.

Zwei Festlegungen gelten ausdrücklich abweichend vom vorliegenden Entwurf:

- Je Aufnahme gibt es nur zwei Zustände — **Behalten** oder **Ausschuss**. Ein „Noch offen" gibt es
  nicht (auch nicht als Umriss oder Kennzeichen).
- Als Ausschuss markierte Aufnahmen werden **nicht verdunkelt**; unterschieden wird über den
  Zustandsrahmen und das Wort im Klartext, nie über Farbe oder Helligkeit allein.

## User Story

Als Nutzer, der den Ausschuss sichtet, möchte ich Duplikate schon in der Übersicht als Stapel erkennen
und sie in einer Vergleichsansicht durchgehen, die Serie, Messwerte und meine Wahl je Aufnahme zeigt,
damit ich bei Serienaufnahmen zügig die richtige behalte, statt die Gruppe aus einzelnen Kacheln
zusammenzusuchen.

## Akzeptanzkriterien

### Teil A — Vergleichsansicht

- [ ] A1 — Der Kopf nennt die Stelle in der Reihe aller Duplikat-Gruppen des Projekts sowie die Serie selbst: `h1` „Gruppe {position} von {total} · {n} Aufnahmen in {Spanne}“ (Muster „Gruppe 2 von 4 · 6 Aufnahmen in 9 Sekunden“). `position` und `total` kommen unverändert aus `DuplicateGroupOut`, `n` ist die Zahl der gelieferten Mitglieder, die Spanne kommt aus `span_seconds` (Abstand zwischen frühestem und spätestem korrigiertem `taken_at` der Mitglieder, ganze Sekunden, abgerundet). Die Spanne wird so formatiert: `0` → „unter einer Sekunde“, unter 60 s → „{s} Sekunde(n)“, unter 3600 s → „{m} Minute(n)“, sonst „{h} Stunde(n) {m} Minute(n)“; der Minutenteil entfällt bei 0. Die Gesamtzahl bleibt während des Durchgangs konstant, auch nach Einzelentscheidung, Gruppenentscheidung und Gruppenabschluss.
- [ ] A2 — Neben dem Zähler steht eine Fortschrittsanzeige derselben Größe: natives `progress` mit `value = position` und `max = total`, `aria-hidden`. Sie ist nie die einzige Quelle der Zahl; beide Zahlen stehen als Text im `h1`.
- [ ] A3 — Im Zustand „gefüllt“ stehen in Raster und Großansicht zwei Absätze immer sichtbar unmittelbar vor der Gruppe „Ganze Gruppe“. Sie stehen nicht in einem `details`, sind kein `Alert` und liegen hinter keiner Aufklapp-Schaltfläche.
  1. `DUPLICATE_HINT_TEXT` nennt das sofortige Speichern beim Antippen. „Bleibt erhalten“ bindet er an den **angezeigten** Zustand „Behalten“; über nicht angetippte Aufnahmen sagt er nichts zu.
  2. `DUPLICATE_CONSEQUENCE_TEXT` bleibt wortgleich, ebenso `data-testid="duplicate-consequence"`.
- [ ] A4 — Je Karte sind gleichzeitig und ohne Aufklappen sichtbar: Bildfläche (Schaltfläche „{Pfad} vergrößern“), Dateiname, Zustandskennzeichen (Symbol und Wort), Bewertungszeile sowie Wahlzeile bzw. A8-Text. Kein Element der Karte trägt `aria-expanded` oder liegt in einem geschlossenen `details`.
- [ ] A5 — Jede Aufnahme trägt beim Öffnen den Zustand aus `effective_decision`: „Behalten“ oder „Ausschuss“. `data-duplicate-decision` kennt nur `keep` und `discard`; in der Wahlzeile ist genau eine Schaltfläche `aria-pressed="true"`. Einen Zustand „Noch offen“ gibt es weder als Wert noch als Wort, Umriss oder Kennzeichen.
- [ ] A6 — Keine Bildfläche der Vergleichsansicht trägt Deckkraft, Filter, Mischmodus oder eine Überlagerung. Das gilt für die Karte, die Bühne der Großansicht und den Streifen. Eine Ausschuss-Aufnahme ist so hell wie eine behaltene. Unterschieden wird über den je Zustand eigenen Zustandsrahmen und über Zustandswort samt Symbol, nie über Farbe oder Helligkeit allein.
- [ ] A7 — Die Bewertungszeile nennt „Schärfe {Wert}“, wo vorhanden auch „Belichtung {x,x} % ohne Zeichnung“.
  - Schärfe: 3 signifikante Stellen, `de-DE`; ohne Messwert steht „nicht gemessen“.
  - Belichtung: Anteil × 100, höchstens eine Nachkommastelle; ohne Wert entfällt die Zeile.
  - Die Werte stammen aus `sharpness`/`exposure` der Gruppenantwort, nie aus `PhotoOut.suggestion`.
  - „— schärfste“ (Maximum) bzw. „— beste Belichtung“ (Minimum) wird über den **angezeigten, gerundeten** Werten gebildet. Bei Gleichstand tragen alle gleichauf liegenden Aufnahmen die Auszeichnung. Keine trägt sie bei weniger als zwei Werten oder wenn alle angezeigten Werte gleich sind; ein fehlender Wert zählt nicht mit.
  - Die Auszeichnung ist nur ein Wort in der Bewertungszeile. Sie ändert weder Zustand, Rahmen, `aria-pressed` noch die Bedienelemente der Karte und steht widerspruchsfrei neben einer Behalten-Wahl auf einer anderen Aufnahme.
- [ ] A8 — Bei `keep_possible = false` (Ablehnung wegen geringer Bildqualität, darunter der Gewinner mit Schärfe-Ablehnung) zeigen Karte und Seitenspalte statt der Wahlzeile `DUPLICATE_IMMUTABLE_TEXT` samt Grund. Es gibt dann keine deaktivierte Schaltfläche, sondern gar keine: Die Karte trägt genau ein Bedienelement, die Bildfläche.
- [ ] A9 — Gruppenaktionen und Gruppenabschluss:
  - „Alle behalten“ und „Alle in den Ausschuss“ setzen alle Mitglieder in genau einem Aufruf des Gruppenwegs.
  - „Gruppe abschließen“ ruft `POST …/duplicate-groups/{anker}/confirm` ohne Body auf. Der Server schreibt `discard` genau für die Projekt-Mitglieder dieser Gruppe mit offenem Vorschlag: nur einfügen, in einer Transaktion, `409` bei Konflikt, nie `keep`, nie überschreiben, `gate_confirmed_at` bleibt unberührt. Kein angezeigter Zustand ändert sich. Ein zweiter Aufruf schreibt nichts und antwortet `200` mit derselben Gruppe.
  - Beschriftung: „Gruppe abschließen, nächste“, wenn `next_photo_id` gesetzt ist; „Gruppe abschließen, zum Ausschuss“ an der letzten Gruppe mit `from=ausschuss`; „Gruppe abschließen“ an der letzten Gruppe ohne `from`. Während der Anfrage lautet sie „Wird abgeschlossen…“. Gesperrt ist die Schaltfläche, solange eine Einzelentscheidung, eine Gruppenentscheidung oder der Abschluss selbst läuft.
  - Erst nach dem Erfolg wird navigiert: Push auf die nächste Gruppe mit erhaltenem `from`, Push nach `/projects/{id}/pipeline/ausschuss`, oder die Ansicht bleibt stehen und meldet per `aria-live` „Gespeichert — das war die letzte Gruppe.“. Diese Meldung verschwindet beim Ankerwechsel.
  - Ein Fehler erscheint als `Alert` mit `detail`; es wird nicht navigiert.
  - Keine dieser Aktionen erzeugt einen Gruppenzustand „erledigt“, weder als Feld der Antwort noch als dauerhaftes Wort in der Ansicht.
- [ ] A10 — Einstiege und Rückweg:
  - Der Stapel (Teil B) führt auf `/projects/{id}/photos/{group_anchor_photo_id}/duplicates?from=ausschuss`.
  - Der listenweite Einstieg der nach Vorschlägen gefilterten Fotoliste bleibt unverändert und trägt keinen Parameter.
  - „Zurück zum Ausschuss“ erscheint in allen vier Zuständen genau beim wörtlichen Wert `from=ausschuss`. Er führt fest auf `/projects/{projectId}/pipeline/ausschuss`; das Ziel wird nie aus dem Parameterwert gebildet.
  - Gruppennavigation und Abschluss tragen `from` weiter.
  - Die Ausschuss-Detailansicht (`?photo=`) lädt keine Gruppe mehr und zeigt die Einzelentscheidung unverändert. Bei gesetztem `group_anchor_photo_id` zeigt sie unabhängig von `reason` den Link „Duplikat-Gruppe vergleichen“ auf den Anker mit `from=ausschuss`; ohne Anker gibt es keinen solchen Link.
  - Kein Einstieg führt auf eine leere Ansicht: Stapel gibt es nur für aufgelöste Gruppen, den Detail-Link nur bei gesetztem Anker, den listenweiten Einstieg nur bei `total > 0`.
- [ ] A11 — Antippen der Bildfläche ersetzt das Raster an derselben Stelle durch die Großansicht. Sie ist kein Dialog; Kopf, Hinweise, Gruppenaktionen und Abschluss bleiben stehen.
  - Bühne: das Bild in `display`-Qualität, eingepasst und unverfälscht, ohne Deckkraft, Filter, Überlagerung und ohne Zustandsrahmen am Bild.
  - Seitenspalte: `h2` „Aufnahme {i} von {n}“ (bekommt beim Öffnen den Fokus), Dateiname, Zustandskennzeichen, Bewertungszeile, Wahlzeile bzw. A8-Text.
  - Streifen darunter: alle Mitglieder, Knopfname „Aufnahme {i} von {n}: {Pfad}, {Zustandswort}“, die aktuelle Aufnahme mit `aria-current="true"`.
  - „Vorherige Aufnahme“, „Nächste Aufnahme“ sowie ← und → verschieben die Vergrößerung, ohne sie aufzuheben. Am ersten bzw. letzten Mitglied bleibt sie stehen (kein Rundlauf); die jeweilige Schaltfläche ist `disabled`, und ein Fokus darauf springt auf die Gegenschaltfläche.
  - Eine Entscheidung in der Seitenspalte ändert nur den Zustand.
  - Esc und „Vergrößerung schließen“ führen zum Raster zurück; der Fokus liegt dann auf der Bildfläche der zuletzt gezeigten Aufnahme.
  - Ab `lg` steht die Seitenspalte neben der Bühne, darunter untereinander. Der Streifen bricht um und scrollt nie waagerecht.
- [ ] A12 — „Vorherige Gruppe“ und „Nächste Gruppe“ (zugänglicher Name gleich sichtbarem Text) stehen in Raster und Großansicht. Am Rand sind sie `disabled`, statt zu fehlen; ein Fokus darauf springt auf die Gegenschaltfläche. Geblättert wird per Push über `duplicateComparePath` mit erhaltenem `from`; das hebt Vergrößerung, laufende Entscheidungen und die Abschlussmeldung auf. Eine vollständig entschiedene oder abgeschlossene Gruppe bleibt erreichbar und wird nicht übersprungen.
- [ ] A13 — Die vier Zustände sind voneinander unterscheidbar:
  - Ladend: `h1` „Duplikate vergleichen“ und `role=status` „Duplikat-Gruppe wird geladen…“ mit Kartenplatzhaltern.
  - Gefüllt.
  - Leer: bei `404` **oder** `200` ohne Mitglieder `DUPLICATE_EMPTY_TEXT`, kein `Alert`, Rückweg bei gesetztem `from`.
  - Fehler: `Alert` mit `detail` und „Erneut versuchen“.
  
  Hinweise, Gruppenaktionen und Abschluss stehen nur im Zustand „gefüllt“. Solange die Nachbargruppe lädt, bleibt die bisherige Gruppe samt Navigation stehen.
- [ ] A14 — Die Wirkung einer Entscheidung bleibt unverändert: „Ausschuss“ wirkt unbedingt, „behalten“ nur gegenüber der Duplikatablehnung. Es gibt kein `DELETE` und keine Rücknahme nach „Noch offen“. Der Abschluss einer Gruppe wirkt auf ihre Mitglieder genau so, wie der spätere Abschluss des Ausschuss-Schritts gewirkt hätte.

### Teil B — Kartenstapel in der Ausschuss-Übersicht

- [ ] B1 — Ein Eintrag `kind: "group"` erscheint als Stapel: vorn das Titelbild (`cover`), dahinter genau zwei versetzte Rahmenkarten ohne Bild (`aria-hidden`, keine Bildanfrage). Sie ragen oben und rechts sichtbar über die vordere Karte hinaus, sodass der Eintrag ohne Text als „mehrere gleiche Aufnahmen“ lesbar ist.
- [ ] B2 — Der Stapel ersetzt das Grund-Kennzeichen nicht: Zeichen und Wort „Duplikat“ bleiben sichtbar am Bild. Die Unterscheidung zu „Geringe Bildqualität“ hängt nie an Form oder Farbe allein.
- [ ] B3 — Einträge `kind: "photo"` bleiben unverändert Einzelkacheln mit Detailansicht über `?photo=`. Dazu gehören Einträge wegen geringer Bildqualität ohne Gruppe und Aufnahmen mit nicht auflösbarem Zeiger. Beide Formen stehen im selben Raster.
- [ ] B4 — Der Stapel ist genau ein Link und das einzige fokussierbare Element im Stapel.
  - Zugänglicher Name: „Duplikat-Gruppe mit {group_size} Aufnahmen vergleichen ({Zusammenfassung, durch Kommas getrennt}): {cover.relative_path}“. Er beginnt weder mit „Duplikate vergleichen:“ noch mit „Duplikate vergleichen —“.
  - Die hinteren Karten sind keine eigenen Ziele: Ein Tipp auf ihre sichtbare Fläche öffnet denselben Link. Sie verdecken weder Dateiname noch Kennzeichen.
  - Das Ziel ist die Vergleichsansicht am Anker mit `from=ausschuss`. Aus der Übersicht führt kein Weg in die Detailansicht eines Gruppenmitglieds.
- [ ] B5 — Die Stapelkachel hat genau die Maße aus `justifiedRows` (Seitenverhältnis aus `cover.aspect_ratio`); der Versatz liegt innerhalb dieser Maße. Bei 360 px wie in der breiten Fassung gibt es kein waagerechtes Scrollen, und außer dem Dateinamen wird keine Beschriftung gekürzt (Kennzeichen, „{group_size} Aufnahmen“, Zusammenfassung).
- [ ] B6 — Ein Stapel je Gruppe:
  - Jede aufgelöste Duplikatgruppe mit mindestens einer Ausschuss-Aufnahme ist über alle Seiten hinweg genau ein Eintrag `kind: "group"`, unabhängig vom `reason` ihrer Mitglieder. Auch der Gewinner mit Schärfe-Ablehnung und ein Gewinner, der nur über eine `keep`-Zeile in den Bestand kommt, liegen im Stapel.
  - Im Listenzweig trägt kein `photo`-Eintrag einen Gruppenanker.
  - Jede Ausschuss-Aufnahme steht genau einmal: als `photo`-Eintrag oder gezählt in `member_count` genau eines Stapels.
  - Der Anker ist der Repräsentant der Gruppe. `cover` ist die erste Ausschuss-Aufnahme der Gruppe nach (`taken_at`, `id`), nicht zwingend der Gewinner.
- [ ] B7 — Zwei Zahlen am Stapel:
  - `group_size` zählt alle Mitglieder der Gruppe. Es ist dieselbe Zahl wie `n` im Kopf der Vergleichsansicht (A1); der Stapel zeigt sie als „{group_size} Aufnahmen“.
  - `member_count` zählt die Ausschuss-Aufnahmen der Gruppe; es gilt 1 ≤ `member_count` ≤ `group_size`.
  - `decision_counts` zählt die **gespeicherten** Zeilen dieser Ausschuss-Aufnahmen, `undecided` die ohne Zeile; es gilt `undecided + keep + discard = member_count`.
  - Die Zusammenfassung nennt nur Teile ungleich null, in der Reihenfolge „{undecided} vorgeschlagen · {discard} Ausschuss · {keep} behalten“.
- [ ] B8 — Paginierung nach Einträgen:
  - `limit`, `offset` und `total` zählen Einträge, also Einzelaufnahmen und Stapel. Jeder Eintrag steht an der Stelle seiner ersten Ausschuss-Aufnahme (`taken_at`, `id`). Eine Gruppe zerfällt nie über eine Seitengrenze.
  - `open_count` zählt weiterhin projektweit Aufnahmen mit offenem Vorschlag.
  - Die Nachladezeile lautet „{n} von {total} Einträgen geladen“; die nächste Seite beginnt bei `offset` gleich der Zahl geladener Einträge.
  - Der Detailfilter `?photo=<id>` liefert genau einen `photo`-Eintrag, bei einem Gruppenmitglied mit gesetztem Anker, oder keinen. Eine fremde oder unbekannte Id ergibt eine leere Liste. `total` und `open_count` sind dieselben wie im Listenzweig.

## Abgelöste Zusagen

Diese Zusagen gelten ab dieser Spec **nicht mehr**; daran gebundene Tests gelten als umgeschrieben,
nicht als Regression (Liste unter `## Teststrategie`):

- Die eingebettete Duplikatgruppe in der Ausschuss-Detailansicht (Spec 0525 AK8 / ADR 0121 Punkt 3) —
  sie verweist stattdessen in die Vergleichsansicht.
- Die Form der Übersichtseinträge (eine Aufnahme je Eintrag) und die Paginierung nach Aufnahmen
  (ADR 0121 Punkt 2) — Duplikatgruppen werden ein Eintrag, gezählt wird nach Einträgen.
- Der entfallene Einstieg „Duplikate vergleichen" aus dem Ausschuss-Schritt (Spec 0486 AK7) — er
  kehrt über den Stapel zurück; der listenweite Einstieg der Fotoliste bleibt daneben.
- Die Dämpfung als Zustandsträger und der dritte Zustand „Noch offen".
- Der Hinweis-Test aus Spec 0486, der „bleibt"/„erhalten" in `DUPLICATE_HINT_TEXT` verbietet: A3
  verlangt die an den angezeigten Zustand gebundene Zusage.

## Datenmodell-Bezug

**Keine Migration, keine neue Spalte, keine Änderung an `photo_duplicate_decisions`.** Neu sind die
Eintragsarten der Antwort von `GET /projects/{id}/ausschuss`, die Felder `sharpness`/`exposure`/
`span_seconds` der Gruppenantwort und der Schreibweg `POST /projects/{id}/duplicate-groups/{photo_id}/confirm`.
[`docs/architecture.md`](../../docs/architecture.md) wird im Umsetzungs-PR nachgezogen.

## Architektur / Umsetzung

**Grundlage:** ADR [`0125`](../decisions/0125-duplikatentscheidung-des-ausschusses-in-der-vergleichsansicht.md). Sie löst zwei Teile von ADR 0121 ab: aus Punkt 2 die Form der Übersichtseinträge und die Paginierung, aus Punkt 3 die eingebettete Gruppe. Unberührt bleiben ADR 0104, ADR 0111, das Überlebens-Prädikat (`duplicates.py::_survives`), der Ausschuss-Bestand (`has_ausschuss_entry`) und die Ableitung von `reason`. **Keine Migration, keine neue Spalte, keine Änderung an `photo_duplicate_decisions`.** Betroffen sind die Antwortformen von Übersicht und Gruppe, ein neuer Schreibweg und das Frontend.

### Ausgangslage

- **Vergleichsansicht:** `pages/DuplicateComparePage.tsx` unter `PROJECT_ROUTE_PATHS.photoDuplicates` (`/projects/:projectId/photos/:photoId/duplicates`, Pfadwert = Anker-Foto).
  - Lesepfad `GET /projects/{id}/duplicate-groups/{photo_id}` liefert `DuplicateGroupOut {items[{photo, effective_decision, keep_possible}], position, total, previous_photo_id, next_photo_id}`.
  - Geschrieben wird sofort über `PUT …/photos/{id}/duplicate-decision` bzw. `PUT …/duplicate-groups/{id}/decision` (`api/duplicate_decisions.py`).
  - Zwei Zustände gibt es schon heute (`effective_decision`). Die Vergrößerung auf Rasterbreite liegt in `components/DuplicatePhotoTile.tsx`; eine Dämpfung trägt die Karte nicht mehr (A6 ist am Bestand erfüllt und bleibt es).
  - Einziger Einstieg ist heute der listenweite in `pages/PhotoGridPage.tsx`.
- **Ausschuss:** `GET /projects/{id}/ausschuss` liefert je Bestandsaufnahme einen `AusschussEntryOut {photo, reason, decision (gespeicherter Zeilenwert oder null), group_anchor_photo_id, keep_possible}`.
  - Paginiert wird in SQL nach `(taken_at, id)`.
  - Die Detailansicht hängt an `?photo=` in `pages/pipeline/AusschussStepPage.tsx` und bettet die Gruppe über `AusschussDetailGruppe` ein.
- **Messwerte:** `PhotoScore.sharpness` ist die Laplace-Varianz (höher = schärfer), `PhotoScore.exposure` der Anteil geclippter Pixel (niedriger = besser). Heute erreichen sie die Oberfläche nur über `PhotoOut.suggestion`, das nach jeder Entscheidung und bei eigener Albumbewertung `null` ist.
- **Zeit:** `Photo.taken_at` (korrigiert) liegt in `DuplicateLink.taken_at` bereits geladen vor.

### Backend

1. **`duplicates.py` (reine Funktionen, keine eigene Abfrage):**
   - `group_span_seconds(representative_id, links) -> int`: Abstand zwischen frühestem und spätestem `taken_at` der Mitglieder, ganze Sekunden, abgerundet.
   - `group_ausschuss_stock(rows, links) -> list[AusschussSlot]`: Gruppiert die geordnete Bestandsliste (`photo_id`, `taken_at`, gespeicherte Entscheidung) nach `representative_of`.
     - Aufnahmen ohne auflösbare Gruppe werden je ein Einzel-Slot.
     - Alle Bestandsaufnahmen derselben Gruppe werden **ein** Gruppen-Slot. Er trägt den Anker, die Bestandsmitglieder, `cover_id` (erstes Bestandsmitglied nach `taken_at`, `id`), die Zählung `undecided`/`keep`/`discard` über den gespeicherten Zeilen und `group_size = len(member_ids_of(...))`.
     - Reihenfolge der Slots: nach ihrem ersten Bestandsmitglied.
2. **`api/photos.py`, Übersicht:**
   - `items` wird eine diskriminierte Vereinigung über `kind`:
     - `AusschussPhotoEntryOut {kind: "photo", photo, reason, decision, group_anchor_photo_id, keep_possible}` — die bisherige Form.
     - `AusschussGroupEntryOut {kind: "group", group_anchor_photo_id, cover: PhotoOut, member_count, group_size, decision_counts: {undecided, keep, discard}}`.
     - Gruppiert wird nach **Mitgliedschaft, nicht nach `reason`**: Auch der Gewinner mit Schärfe-Ablehnung und der nur durch eine `keep`-Zeile getragene Gewinner liegen im Stapel ihrer Gruppe. Einträge wegen geringer Bildqualität ohne Gruppe bleiben Einzelkacheln (B3).
   - `list_ausschuss` lädt den Bestand als leichte Liste `select(Photo.id, Photo.taken_at, PhotoDuplicateDecision.decision)`.
     - Innerer Join auf `PhotoScore`, äußerer auf `PhotoDuplicateDecision`.
     - `Photo.project_id == project_id` und `has_ausschuss_entry()` stehen in **derselben** Anweisung, `order_by(Photo.taken_at, Photo.id)`.
     - Danach werden `load_duplicate_links` und `group_ausschuss_stock` angewandt; `total = len(slots)`.
     - Die Seite ist `slots[offset:offset + limit]`; hydratisiert werden nur Einzel-Aufnahmen und Titelbilder der Seite (bestehende Kontextbeschaffung aus `_ausschuss_entries_out`).
     - Kein SQL-`LIMIT` vor dem Gruppieren, sonst zerfällt eine Gruppe über zwei Seiten in zwei Stapel.
   - `open_count` bleibt die projektweite Zahl der **Aufnahmen** mit offenem Vorschlag (eigene Zählung wie heute), weil der Abschluss je Aufnahme schreibt.
   - `has_ausschuss_entry` bleibt **eine** Aufrufstelle. Die Parameter `limit` (60, `le=200`), `offset` und `photo_id` bleiben mit ihren Grenzen erhalten.
   - **Detailfilter `?photo=<id>`:** Er liefert genau einen `photo`-Eintrag oder eine leere Liste, auch für ein Gruppenmitglied — dann mit gesetztem `group_anchor_photo_id`. `total` und `open_count` sind wie im Listenzweig.
   - **Invariante:** Im Listenzweig trägt kein `photo`-Eintrag einen Gruppenanker.
3. **`api/photos.py`, Gruppe:**
   - `DuplicateGroupPhotoOut` bekommt `sharpness: float | None` und `exposure: float | None` aus `photo.score`; ohne Zeile sind beide `None` (Auflage S3 der Spec 0486).
   - `DuplicateGroupOut` bekommt `span_seconds: int`; `empty_duplicate_group_out` setzt `0`.
   - Kein Auszeichnungsfeld. Nie aus `PhotoOut.suggestion` lesen.
4. **`api/duplicate_decisions.py`:** neuer Endpunkt **`POST /projects/{project_id}/duplicate-groups/{photo_id}/confirm`** ("Gruppe abschließen").
   - Ohne Body, Pfad-Ids mit `ge=1, le=MAX_QUERY_POSITION`, router-weite Auth-Dependency.
   - Der Stern wird zuerst aufgelöst (`404` vor jedem Schreiben).
   - **Eine** Anweisung wählt `Photo.project_id == project_id ∧ Photo.id ∈ member_ids_of(...) ∧ has_open_suggestion()`.
   - Für diese Menge wird `discard` geschrieben: nur einfügen, kein `DELETE`, eine Transaktion, `IntegrityError` wird `409`.
   - `gate_confirmed_at` bleibt unberührt. Die Antwort ist `DuplicateGroupOut`.
   - Kein Umbau von `confirm_ausschuss_gate`: Sein Eintrag im Wächter darf nicht sinken.

### Sicherheitsbindung

- Bestand, Projektbindung und `has_ausschuss_entry()` stehen in **einer** Anweisung, nie als nachgelagerter Filter.
- Gruppenschlüssel, Anker, Titelbild und Mitglieder des Stapels stammen ausschließlich aus dem projektbegrenzten Bestand und `load_duplicate_links(session, project.id)`. Eine eigene SQL-Fassung des Sterns ist untersagt, weil `duplicate_of` ohne Projektbedingung auf `photos.id` zeigt.
- Ein Zeiger, der sich nicht auflöst, bleibt ein `photo`-Eintrag. Eine fremde oder unbekannte `photo_id` im Detailfilter liefert eine leere Liste.
- `cover` ist ein `PhotoOut` und damit eine Funktion des anfragenden Nutzers; die Cache-Auflage gilt für beide Eintragsarten.
- Der Abschluss schreibt ausschließlich `discard`, die Menge bestimmt der Server, es gibt keine Id-Liste und kein Überschreiben.
- Wächter: `_ERWARTETE_VERWENDUNGEN[("api/duplicate_decisions.py", "has_open_suggestion")]` steigt von 1 auf 2. Kein Eintrag wird gesenkt, die Einträge in `api/photos.py` bleiben unverändert.

### Zustände und Wirkung (A5, A8, A9, A14)

Beim Öffnen trägt jede Aufnahme den Zustand aus `effective_decision`, ohne Änderung gegenüber heute:

| Mitglied | Zustand beim Öffnen | Wahl |
|---|---|---|
| Duplikat-Verlierer ohne Zeile | Ausschuss | änderbar |
| Gewinner ohne Vorschlag (auch ohne `PhotoScore`-Zeile) | Behalten | änderbar |
| Gewinner mit Schärfe-Ablehnung | Ausschuss | keine Wahlzeile, Grund statt Wahl (A8) |
| Mitglied mit Zeile | Auswertung des Prädikats | änderbar, außer bei `keep_possible = false` |

- **Antippen:** unverändert der Einzelweg, sofort wirksam.
- **"Alle behalten" / "Alle in den Ausschuss":** unverändert der Gruppenweg.
- **"Gruppe abschließen, nächste":** erst `POST …/confirm`, dann Push-Navigation auf `next_photo_id`. Die Aktion ist gesperrt, solange eine Einzel- oder Gruppenentscheidung läuft.
- Ein offener Vorschlag zeigt vorher schon `discard`. Der Abschluss ändert also keinen angezeigten Zustand, er schreibt ihn fest — mit derselben Wirkung, die `confirm-ausschuss-gate` später hätte.
- Es gibt keinen Gruppenzustand, kein `DELETE` und keine Rücknahme nach "Noch offen".
- **Untersagt:** das Festschreiben des angezeigten Werts aus dem Client. Es schriebe `keep` auf den Gewinner ohne Vorschlag und überschriebe gespeicherte Handlungen.

### Routen, Einstiege und Rückweg (A10, B4)

- `PROJECT_ROUTE_PATHS` bleibt bei zehn Einträgen. Neu ist der Query-Parameter **`?from=ausschuss`** an der Vergleichsroute.
- `duplicateComparePath(projectId, photoId, { fromAusschuss })` in `utils/projectRoutes.ts` ist die einzige Stelle, die den Pfad baut. Sie wird von Stapel, Detail-Link, Gruppennavigation und Abschluss genutzt.
- "Zurück zum Ausschuss" erscheint nur beim wörtlichen Wert `ausschuss`. Das Ziel ist fest `/projects/{projectId}/pipeline/ausschuss`.
- **Stapel** (`kind: "group"`) → Vergleichsansicht an `group_anchor_photo_id`, mit `from=ausschuss`.
- **Einzelkachel** (`kind: "photo"`) → Detailansicht (`?photo=`) wie heute.
- **Detailansicht eines Gruppenmitglieds:** Sie bleibt über den Deep-Link `?photo=<id>` und über den Browser-Verlauf erreichbar; aus der Übersicht führt kein Weg mehr dorthin (B4). Sie zeigt die Einzelentscheidung und bei gesetztem `group_anchor_photo_id` einen Link in die Vergleichsansicht statt der eingebetteten Gruppe (A10).
- Der listenweite Einstieg in `PhotoGridPage` bleibt unverändert, ohne Parameter.
- Kein Einstieg ins Leere: Stapel gibt es nur für aufgelöste Gruppen, den Detail-Link nur bei gesetztem Anker, den listenweiten Einstieg nur bei `total > 0`.

### Frontend

- **`api/types.ts`:**
  - `AusschussEntryOut` wird zur Vereinigung `AusschussPhotoEntry | AusschussGroupEntry` über `kind`.
  - `DuplicateGroupItem` bekommt `sharpness`/`exposure`, `DuplicateGroupOut` bekommt `span_seconds`.
- **`api/duplicates.ts`:** `confirmDuplicateGroup(projectId, photoId)`; die Exportmenge wächst auf fünf.
- **`hooks/useDuplicates.ts`:** `useDuplicateGroupConfirmMutation(projectId, anchorId)` über `applyGroup`. Die breite Invalidierung unter `['photos', projectId]` aktualisiert auch Übersicht und `open_count`.
- **`hooks/useAusschuss.ts`:** Schlüssel unverändert. `useAusschussEntryQuery` verengt auf `kind === 'photo'`.
- **`utils/duplicateMetrics.ts` (neu, rein):**
  - Formatierung von Schärfe, Belichtung und Zeitspanne, auch für Spannen ≥ 60 s (die Demo-Gruppen umfassen 51 bzw. 102 Minuten).
  - Die Auszeichnung "beste je Messwert" wird über den **angezeigten** Werten gebildet: Schärfe = Maximum, Belichtung = Minimum.
  - Bei Gleichstand tragen alle gleichauf liegenden Aufnahmen die Auszeichnung. Keine trägt sie bei weniger als zwei Werten oder wenn alle gleich sind; `null` fällt aus der Wertung.
- **`components/DuplicatePhotoTile.tsx`:**
  - Bleibt ohne Dämpfung (A6); `designSystem.contract.test.ts::OPACITY_ALLOWLIST` bekommt keinen Eintrag.
  - Mit Bewertungszeile (A4, A7).
  - Die Props `enlarged`/`controls` entfallen.
- **`components/DuplicateEnlargedView.tsx` (neu, A11):**
  - Großbild über `PhotoImage` in der Variante `display`, `object-contain`, ohne Opacity oder Filter.
  - Seitenspalte mit "Aufnahme N von M" und Bewertung; darunter ein Streifen aller Mitglieder.
  - Vor/Zurück ohne Rundlauf, am Rand `disabled`; Esc und Pfeiltasten.
  - **Kein Dialog**: ersetzt das Raster auf derselben Seite. `enlargedId` als Foto-Id, beim Ankerwechsel zurückgesetzt.
- **`pages/DuplicateComparePage.tsx`:**
  - Kopf "Gruppe N von M · K Aufnahmen in X" (A1) plus `components/ui/progress`, die Zahlen zusätzlich als Text (A2).
  - Hinweistexte sichtbar (A3); `DUPLICATE_CONSEQUENCE_TEXT` bleibt wortgleich.
  - Gruppennavigation und alle drei Gruppenaktionen in beiden Modi (A12).
  - `from`-Parameter, Rückweg, Abschluss. Die vier Zustände Laden, Leer, Fehler und Gefüllt bleiben (A13).
- **`components/DuplicateStackTile.tsx` (neu, B1–B5):**
  - Genau ein `<Link>` mit zugänglichem Namen; das Präfix `Duplikate vergleichen:` bzw. `Duplikate vergleichen —` ist ausgeschlossen.
  - Vorn `cover`; die hinteren Karten sind reine Rahmen (`aria-hidden`, `pointer-events-none`) ohne Bild und ohne Anfrage. Der Versatz liegt **innerhalb** der von `justifiedRows` gerechneten Maße (Seitenverhältnis aus `cover.aspect_ratio`), also ohne waagerechtes Scrollen bei 360 px (B5).
  - Sichtbar bleiben Grund-Kennzeichen "Duplikat" (B2), Dateiname des Titelbilds, Anzahl (`group_size`/`member_count`) und eine Zusammenfassung aus `decision_counts`. Wortlaut und Auswahl der Zahl gehören der UX-Konsultation.
- **`pages/pipeline/AusschussStepPage.tsx`:**
  - Das Raster verzweigt nach `kind`; "X von Y geladen" zählt Einträge.
  - `AusschussDetailGruppe` entfällt samt der Importe von `DuplicatePhotoTile` und `useDuplicateGroupQuery`.
  - Die Detailansicht bekommt den Link in die Vergleichsansicht.

### Doku im selben PR

- `docs/architecture.md`:
  - Endpunktblock: `ausschuss` mit Eintragsarten und Paginierung nach Einträgen; neuer `POST …/confirm`; neue Gruppenfelder.
  - Ausschuss-Abschnitt: Stapel statt eingebetteter Gruppe.
  - Abschnitt Vergleichsansicht: Einstiege, Rückweg-Parameter, Großansicht, keine Dämpfung.
- `specs/architecture/0003-securitykonzept.md` und `design/penpot/views.json` gehören der Security- bzw. UX-Konsultation.

### Reihenfolge

1. `duplicates.py`: `group_ausschuss_stock` und `group_span_seconds`
2. `api/photos.py`: Übersicht mit Eintragsarten, Paginierung nach Einträgen und Detailfilter
3. `api/photos.py`: Gruppenfelder
4. Abschluss-Endpunkt: 404, 409, 401, Wächter-Eintrag, `DOCUMENTED_ROUTES`
5. Frontend: Typen, Clients, Hooks
6. `utils/duplicateMetrics.ts` und `duplicateComparePath`
7. `DuplicatePhotoTile`
8. `DuplicateEnlargedView`
9. `DuplicateComparePage`
10. `DuplicateStackTile` und `AusschussStepPage` (Raster, Detail-Link, Wegfall der eingebetteten Gruppe)
11. Doku

## UI/UX

**Design-Quelle.** Maßgeblich ist die Penpot-Datei „PhotoSort — Dark Utility Register“ mit zwei Seiten:
- „Ansicht — Duplikate vergleichen“: `design/penpot/views.json`, Schlüssel `duplikate`, Zustände `gefuellt/vergroessert/leer/ladend/fehler`;
- „Ansicht — Ausschuss“: Schlüssel `ausschuss`, Lücke `stapel`.

Das ist der „vorliegende Entwurf“. Am Issue steht kein `## Design`-Block. Zwei Festlegungen der Story gehen dem Entwurf vor:
1. Es gibt nur **Behalten** und **Ausschuss**. Einen dritten Zustand „noch offen“ gibt es nicht, auch keinen neutralen Umriss.
2. Es gibt **keine Dämpfung**. Die Bildfläche ist in beiden Zuständen gleich hell.

Seitenspalte, Streifen, Bewertungszeile und die Serienangabe im Kopf beschreibt die Nutzlast nicht; für sie gilt dieser Abschnitt. Design-System: `specs/architecture/0004-design-system.md`, Skill `design-system`.

### Vergleichsansicht: Aufbau

Die Reihenfolge von oben nach unten ist zugleich die DOM- und die Fokusreihenfolge. Sie gilt für Raster und Großansicht gleich.

1. **Rückweg (nur bei `from=ausschuss`)**
   - `Button asChild variant="ghost" size="sm"` mit einem `Link` „Zurück zum Ausschuss“, linksbündig über der Überschrift.
2. **Kopf (A1, A2)** — `flex flex-wrap items-center justify-between gap-3`
   - Links steht ein `h1` (`text-xl sm:text-2xl`) „Gruppe {position} von {total}“. Im selben `h1` folgt eine Spanne ` · {n} Aufnahmen in {Spanne}` (`text-base font-normal text-text sm:text-lg`).
   - Daneben steht `Progress` mit `value={position} max={total}`, Ton `accent`, Breite `w-24 sm:w-40`. Er ist `aria-hidden`, weil der `h1` die Zahlen als Text trägt.
   - Rechts steht die Gruppennavigation: `role="group" aria-label="Duplikat-Gruppen"` mit „Vorherige Gruppe“ und „Nächste Gruppe“.
     - `outline`, `size="sm"`, heißer Pfad `h-11 sm:h-8`, Abstand `gap-3`.
     - Der zugängliche Name ist gleich dem sichtbaren Text.
     - Am Rand ist die Schaltfläche `disabled`; sie verschwindet nicht (A12).
     - Sie navigiert per Push über `duplicateComparePath`, `from` bleibt erhalten.
   - Bei 360 px brechen die Teile um. Nichts wird gekürzt.
3. **Hinweisblock (A3)**
   - Zwei Absätze `p.text-sm.text-text` in `max-w-3xl`. Sie sind immer sichtbar, nie eingeklappt, keine `Alert`.
   - `DUPLICATE_HINT_TEXT` wird neu gefasst: „Antippen von „Behalten“ oder „Ausschuss“ wird sofort gespeichert. Es gilt der angezeigte Zustand: Was „Behalten“ zeigt, bleibt erhalten; nur was „Ausschuss“ zeigt, scheidet aus der weiteren Bearbeitung aus.“
   - `DUPLICATE_CONSEQUENCE_TEXT` bleibt wortgleich, ebenso `data-testid="duplicate-consequence"`.
   - Der Block steht unmittelbar über den Gruppenaktionen, also an der Handlung.
4. **Gruppenaktionen (A9)**
   - `role="group" aria-label="Ganze Gruppe"` mit „Alle behalten“ und „Alle in den Ausschuss“.
   - `outline`, Busy-Muster, `flex flex-wrap gap-3`. Ein Fehler erscheint als `Alert` darunter.
5. **Inhalt:** entweder das Raster oder die Großansicht, nie beides zugleich.
6. **Abschluss (A9)** — steht unter dem Raster bzw. unter dem Streifen, also am Ende des Durchgangs.
   - Hauptschaltfläche `default`. Die Beschriftung hängt von der Lage ab:
     - „Gruppe abschließen, nächste“, wenn es eine nächste Gruppe gibt (`next_photo_id ≠ null`);
     - „Gruppe abschließen, zum Ausschuss“ an der letzten Gruppe mit `from=ausschuss`;
     - „Gruppe abschließen“ an der letzten Gruppe ohne `from`.
   - Während der Anfrage lautet sie „Wird abgeschlossen…“. Gesperrt ist sie, solange eine Einzel- oder Gruppenentscheidung läuft.
   - Nach dem Erfolg:
     - Gibt es eine nächste Gruppe, wird per Push dorthin gewechselt; `from` bleibt erhalten.
     - An der letzten Gruppe mit `from` geht es per Push nach `/projects/{id}/pipeline/ausschuss`.
     - An der letzten Gruppe ohne `from` bleibt die Ansicht stehen. Darunter erscheint `p[aria-live=polite].text-sm.text-text` „Gespeichert — das war die letzte Gruppe.“ Der Satz verschwindet beim Wechsel des Ankers.
   - Ein Fehler erscheint als `Alert` mit `detail` unter der Schaltfläche. Die Schaltfläche selbst ist die Wiederholung.
   - Es entsteht kein dauerhaftes Wort „erledigt“ oder „abgeschlossen“ als Gruppenzustand.

### Raster und Karte (A4–A8, `DuplicatePhotoTile`)

- Das Raster bleibt `grid grid-cols-2 items-start gap-3 sm:grid-cols-3`.
- Die Karte bleibt `li.flex.flex-col.gap-3.rounded-lg.bg-elevated.p-2.sm:p-3`.
  - Zustandsrahmen: `border-2 border-accent` für Behalten, `border-2 border-danger` für Ausschuss.
  - `data-duplicate-decision` bleibt.
  - Die Props `enlarged` und `controls` entfallen.

Inhalt der Karte von oben nach unten:

- **Bildfläche**
  - Natives `<button>` mit dem Namen „{Pfad} vergrößern“, `aspect-square`, Vorschaubild mit `object-cover`.
  - Keine Deckkraft, kein Filter (A6).
- **Statuszeile**
  - Links das Zustandskennzeichen: `Icon` `check` bzw. `x-circle` (14 px) plus das Wort „Behalten“ (`text-accent`) bzw. „Ausschuss“ (`text-danger-text`).
  - Rechts der Dateiname: `font-mono text-xs text-text-muted min-w-6 truncate`.
  - Kein `Badge` (Lücke `kennzeichenbaustein`).
- **Bewertungszeile (A7)**
  - Aufbau: `dl.flex.flex-col.gap-1.text-xs`; je Messwert ein `div.flex.flex-wrap.gap-x-1` mit `dt.text-text-muted` und `dd.text-text`.
  - Zeilen: „Schärfe {Wert}“, bei Bestwert mit „— schärfste“; „Belichtung {x,x} % ohne Zeichnung“, bei Bestwert mit „— beste Belichtung“.
  - Die Auszeichnung ist `span.font-semibold.text-text-h` und nur ein Wort: **kein** Akzent, kein Symbol, kein Rahmen. Akzent heißt in dieser Ansicht „Behalten“.
  - Fehlt die Schärfe, steht im `dd` „nicht gemessen“. Ist die Belichtung `null`, entfällt ihre Zeile.
  - Die Auszeichnung wird über den **angezeigten**, also gerundeten Werten gebildet.
- **Formatierung** in `utils/duplicateMetrics.ts`, Locale `de-DE`:
  - Schärfe mit 3 signifikanten Stellen (`412,7 → 413`, `0,7341 → 0,734`).
  - Belichtung: Anteil × 100, höchstens eine Nachkommastelle.
  - Zeitspanne, abgerundet:
    - `0` → „unter einer Sekunde“;
    - unter 60 s → „{s} Sekunde(n)“;
    - unter 3600 s → „{m} Minute(n)“;
    - sonst „{h} Stunde(n) {m} Minute(n)“; die Minuten entfallen bei 0.
- **Wahlzeile**
  - `div.flex.flex-wrap.gap-3` mit zwei `Button variant="outline" size="sm" className="h-11 grow sm:h-8"`.
  - Ist die Karte zu schmal (etwa unter 170 px Innenbreite), brechen die Schaltflächen untereinander um, statt überzulaufen.
  - `aria-pressed` folgt `effective_decision`. Die gedrückte Schaltfläche zeigt zusätzlich ihr Zustandssymbol vor dem Wort; so trägt die Form den Zustand, nicht nur die Farbe.
  - Namen wie heute: „Behalten: {Pfad}“ und „Ausschuss: {Pfad}“. Busy-Muster je Aufnahme.
- **`keep_possible === false` (A8)**
  - Es gibt keine Wahlzeile, auch keine deaktivierte.
  - An ihrer Stelle steht `p.text-xs.text-text-muted` mit `DUPLICATE_IMMUTABLE_TEXT`.

### Großansicht (A11, `DuplicateEnlargedView`)

Die Großansicht ist **kein Dialog**. Sie ersetzt das Raster an derselben Stelle. Kopf, Hinweisblock, Gruppenaktionen und Abschluss bleiben sichtbar.

- **Anordnung**
  - `section aria-labelledby` mit `flex flex-col gap-4 lg:flex-row`.
  - Bühne `min-w-0 lg:flex-1`, Seitenspalte `lg:w-72 lg:shrink-0`.
  - Der Streifen läuft darunter über die volle Breite.
- **Bühne**
  - `rounded-md bg-surface` mit fest reservierter Höhe `h-96 lg:h-144`, damit nichts springt, wenn das Bild eintrifft.
  - `PhotoImage variant="display"`, `size-full object-contain`.
  - Unverfälscht: keine Deckkraft, kein Filter, keine Überlagerung und kein Zustandsrahmen am Bild.
- **Seitenspalte**
  - `rounded-lg bg-elevated p-4 flex flex-col gap-3` mit dem Zustandsrahmen der Aufnahme.
  - Inhalt von oben nach unten:
    - `h2.text-lg` „Aufnahme {i} von {n}“ mit `tabIndex={-1}`; er bekommt beim Öffnen den Fokus;
    - Dateiname in `font-mono text-xs text-text-muted break-all`;
    - Zustandskennzeichen;
    - Bewertungszeile;
    - **Wahlzeile** bzw. der A8-Text, wie auf der Karte;
    - „Vorherige Aufnahme“ / „Nächste Aufnahme“: `outline sm`, `h-11 sm:h-8`, `gap-3`; kein Rundlauf, am Rand `disabled`;
    - „Vergrößerung schließen“ als `ghost sm`.
  - Tasten: Esc schließt, ← und → blättern.
- **Streifen**
  - `ul.flex.flex-wrap.gap-3`. Er bricht um und scrollt nie waagerecht.
  - Je Mitglied ein `li.relative` mit einem `<button>` `size-16 sm:size-20 overflow-hidden rounded-md` (Vorschaubild, `object-cover`).
  - Name des Knopfs: „Aufnahme {i} von {n}: {Pfad}, {Zustandswort}“.
  - Die aktuelle Aufnahme trägt `aria-current="true"` und `border-2 border-text-h`, die übrigen `border-2 border-transparent`. Bewusst nicht Akzent, denn Akzent heißt hier „Behalten“.
  - Neben dem Knopf liegt ein Zustandsplättchen als Geschwisterelement: `pointer-events-none absolute bottom-1 left-1 rounded-sm bg-overlay p-1`, nur das Symbol in Zustandsschrift.
- **Fokus**
  - Wird eine fokussierte Vor- oder Zurück-Schaltfläche am Rand `disabled`, springt der Fokus auf die Gegenschaltfläche. Das gilt auch für die Gruppennavigation.
  - Nach dem Schließen liegt der Fokus auf der Bildfläche der zuletzt gezeigten Aufnahme im Raster. Sie wird in den Sichtbereich gescrollt.

### Zustände (A13)

Hinweisblock, Gruppenaktionen und Abschluss stehen nur im Zustand *gefüllt*.

- **Ladend**
  - `h1` „Duplikate vergleichen“, ohne `Progress`.
  - `ul[role=status][aria-label="Duplikat-Gruppe wird geladen…"]` mit 4 Platzhaltern in **Kartenform**: `Skeleton aspect-square rounded-md`, darunter drei Zeilen `h-3 rounded-xs` und ein Block `h-8 rounded-sm`.
- **Leer** (404 oder keine Mitglieder)
  - `h1` „Duplikate vergleichen“ und `p.text-sm.text-text` mit `DUPLICATE_EMPTY_TEXT`.
  - Keine `Alert`. Der Rückweg erscheint, wenn `from` gesetzt ist.
- **Fehler**
  - `h1` „Duplikate vergleichen“ und `Alert` mit `detail` und „Erneut versuchen“.
- **Gefüllt:** Raster oder Großansicht.

### Ausschuss-Übersicht: Duplikat-Stapel (B1–B5, `DuplicateStackTile`)

- **Maße**
  - Die Kachel hat genau die Maße aus `justifiedRows`; das Seitenverhältnis kommt aus `cover.aspect_ratio`.
  - Der Versatz liegt **innerhalb** dieser Maße: oben und rechts sind 8 px reserviert, in den Stufen 4 und 8 px.
- **Aufbau**
  - `li.relative`, **ohne** `overflow-hidden`, damit der Fokusring sichtbar bleibt.
  - Darin genau ein `Link` `relative block size-full`.
  - Zwei hintere Karten: `span[aria-hidden] pointer-events-none absolute rounded-md border border-border-control bg-elevated`.
    - Die hinterste liegt bei `top-0 right-0 bottom-2 left-2`, die mittlere bei `top-1 right-1 bottom-1 left-1`.
    - Sie tragen kein Bild und lösen keine Anfrage aus.
  - Vordere Karte: `absolute top-2 right-2 bottom-0 left-0 overflow-hidden rounded-md border border-border-control bg-elevated` mit dem Titelbild (`thumbnail`, `object-cover`).
- **Grund-Kennzeichen (B2)**
  - Oben links, unverändert wie heute: `StapelZeichen` plus „Duplikat“ auf `bg-overlay`.
- **Fußleiste**
  - `pointer-events-none absolute inset-x-0 bottom-0 flex flex-wrap items-center gap-x-2 bg-overlay px-2 py-1 text-xs`.
  - Inhalt in dieser Reihenfolge:
    - „{group_size} Aufnahmen“ in `text-text-h`;
    - die Zusammenfassung aus `decision_counts`: nur Teile ungleich null, in fester Reihenfolge „{undecided} vorgeschlagen“ (`text-text-muted`) · „{discard} Ausschuss“ (`text-danger-text`) · „{keep} behalten“ (`text-accent`); jeder Teil als eigene Spanne mit `hyphens-auto`, der Trenner `·` ist `aria-hidden`;
    - der Dateiname in `min-w-6 flex-1 truncate font-mono text-text-muted`.
  - Nur der Dateiname wird gekürzt. So wird bei 360 px keine Beschriftung abgeschnitten (B5).
- **Zugänglicher Name (B4):** „Duplikat-Gruppe mit {group_size} Aufnahmen vergleichen ({Zusammenfassung, durch Kommas getrennt}): {cover.relative_path}“.
- **Ziel:** `duplicateComparePath(projectId, group_anchor_photo_id, { fromAusschuss: true })`.
- **Einzelkachel:** bleibt unverändert (B3).
- **Nachladezeile:** „{n} von {total} Einträgen geladen“.

### Ausschuss-Detailansicht (A10)

- Die eingebettete Gruppe entfällt. Die Anordnung wird einspaltig; `lg:grid-cols-2` entfällt.
- Ist `group_anchor_photo_id` gesetzt, steht unter der Entscheidungszeile ein `Button asChild variant="outline" size="sm"` mit einem `Link` „Duplikat-Gruppe vergleichen“ (mit `from=ausschuss`).

### Design-System-Bezug

- Es werden nur bestehende Bausteine und Tokens genutzt:
  - Bausteine: `Button`, `Alert`, `Skeleton`, `Progress`, `Icon`, `PhotoImage`;
  - Tokens: `--elevated`, `--overlay`, `--surface`, `--border-control`, `--accent`, `--danger`/`--danger-text`, `--text-h`/`--text`/`--text-muted`.
- Keine neue Abhängigkeit, kein neues Symbol, kein neuer Farbwert, keine `opacity`-Freigabe.
- Neu im Vertragstest sind die Freigaben `h-11 sm:h-8` für den heißen Pfad: Wahlzeile, Aufnahme-Navigation und Gruppennavigation.

## Security

Sicherheitsrelevant, ohne neue Vertrauensgrenze: kein Secret, keine Umgebungsvariable, kein externer
Dienst, kein Freitext, keine Migration, keine neue Aufzählbarkeit und keine Änderung an
Authentifizierung oder an der Sichtbarkeit zwischen den beiden Nutzern. Neu sind drei Dinge: ein
dritter Schreibweg auf `photo_duplicate_decisions`, dessen Menge der Server bildet, eine Übersicht,
die ihre Einträge aus `duplicate_of`-Kanten zusammensetzt, und der erste Query-Parameter, der einen
Rückweg auswählt.

**Fortgeltung.** S1–S12 der Spec 0374, S1–S7 der Spec 0486 und S1–S10 der Spec 0525 gelten
unverändert. Keine davon wird abgelöst, denn die abgelösten Zusagen dieser Story tragen keine
Sicherheitsauflage. Die folgenden Auflagen treten daneben; einige übertragen bestehende auf die neuen
Stellen.

### Gruppenabschluss (`POST /projects/{project_id}/duplicate-groups/{photo_id}/confirm`)

- **S1 — Der Stern wird zuerst aufgelöst. Ohne Gruppe antwortet der Endpunkt `404`, bevor irgendetwas
  geschrieben wird — auch für ein Foto mit offenem Vorschlag.** Die erweiterte Vorbedingung des
  Einzelwegs („Gruppe oder offener Vorschlag“, Spec 0525 S10) gilt hier nicht. Angriff:
  `member_ids_of(None, links)` liefert jedes Foto des Projekts mit `duplicate_of IS NULL`. Zusammen
  mit `has_open_suggestion()` schriebe ein Aufruf auf ein einzelnes unscharfes Foto dann `discard` auf
  jede Unschärfe-Ablehnung des Projekts. Das wäre der projektweite Massenabschluss ohne dessen
  Bestätigungsdialog. Test:
  `test_api_duplicate_decisions.py::test_the_group_confirm_resolves_the_group_before_writing` (zwei
  unscharfe Einzelfotos mit offenem Vorschlag; ein Aufruf auf eines ⇒ `404`, die Tabelle bleibt leer).

- **S2 — Projektbindung, Mitgliedschaft und `has_open_suggestion()` stehen als UND-Glieder in einer
  Anweisung mit innerem Join auf `PhotoScore`.** `has_open_suggestion` trägt keine eigene
  Projektbedingung und setzt den Join voraus. Fehlt er, entsteht ein kartesisches Produkt: Die
  Bedingung wird für jedes Mitglied wahr, sobald irgendein Foto der Instanz einen offenen Vorschlag
  trägt. Der Gewinner, der „Behalten“ zeigt, verliert dann still seinen Platz in Bewertung und Album.
  Tests: `::test_the_group_confirm_writes_discard_only_for_the_open_suggestions_of_this_group`. Der
  Aufbau: eine Gruppe mit offenem Verlierer, einem Gewinner ohne Vorschlag und einem `keep`-Mitglied,
  dazu eine zweite Gruppe und ein zweites Projekt mit offenen Vorschlägen. Danach trägt allein der
  Verlierer `discard`, der Gewinner hat keine Zeile, `keep` bleibt `keep`, und alles andere bleibt
  leer. Dazu `::test_a_photo_of_another_project_is_a_404_for_the_group_confirm`: `404`, ohne den
  übergebenen Wert zu spiegeln.

- **S3 — Es wird nur eingefügt und nur `discard` geschrieben, in einer Transaktion. Der `flush` liegt
  vor dem `commit`, ein `IntegrityError` wird `409` mit vollständigem Rückzug. `_write` und jedes
  `DELETE` sind untersagt.** Zwischen Auswahl und Schreiben kann der andere Nutzer eine `keep`-Zeile
  committen. Ein vorangestelltes `DELETE` räumte sie weg und ersetzte seine Handlung durch `discard`,
  ohne Fehler und ohne Meldung. Das ist der Fall, den Spec 0525 S4 ausschließt, hier nur im
  Wettlauf. Der Primärschlüssel macht daraus einen `409`. Ein zweiter Aufruf findet keine offene
  Aufnahme mehr und antwortet `200`. Tests:
  - `::test_the_group_confirm_never_issues_a_delete` (Mitschnitt über `before_cursor_execute`);
  - `::test_a_concurrent_write_during_the_group_confirm_is_a_409_and_writes_nothing` (eingesetzter
    `IntegrityError` nach dem Muster des bestehenden 409-Falls, mit Zähler auf den betretenen Zweig);
  - `::test_the_group_confirm_is_idempotent`.

- **S4 — Weder Menge noch Wert kommen vom Aufrufer.** Der Endpunkt nimmt kein Eingabeschema
  entgegen; ein mitgeschickter Körper wird nie gelesen. Untersagt ist außerdem, den angezeigten
  Zustand aus dem Client über Einzel- oder Gruppenweg festzuschreiben. Angriff: Eine Id-Liste wäre ein
  Massen-Schreibweg auf beliebige Fotos, ein Wert ein Massen-`keep`. Aus der Anzeige geschrieben,
  bekäme der Gewinner ohne Vorschlag eine `keep`-Zeile. Sie ist heute wirkungslos und wird wirksam,
  sobald ein neuer Lauf ihn zum Verlierer macht — dann geht eine Aufnahme an den Cloud-Anbieter, die
  niemand je behalten hat. Tests:
  - `::test_the_group_confirm_reads_no_body` (Körper mit `photo_ids` und `"decision": "keep"` ⇒ kein
    `keep`, das genannte Foto bleibt unberührt);
  - `DuplicateComparePage.test.tsx`: „Gruppe abschließen“ ruft `confirmDuplicateGroup` genau einmal
    und keinen der beiden `set…`-Aufrufe (Aufrufzähler der gemockten API).

- **S5 — `gate_confirmed_at` bleibt unberührt.** Der Zeitstempel öffnet die Klassifizierung und damit
  den Cloud-Teilschritt. Setzte ihn der Abschluss der letzten Gruppe, liefe der nächste Schritt ohne
  die projektweite Bestätigung an. Diese übernimmt auch die Unschärfe-Ablehnungen außerhalb jeder
  Gruppe. Test: `::test_the_group_confirm_never_sets_the_gate` (die einzige Gruppe ist
  abgeschlossen, danach gibt es keine offenen Vorschläge mehr, der Zeitstempel bleibt `NULL`).

- **S6 — Der Torwächter ist dreifach gesichert, die Pfad-Ids sind begrenzt.** Der Endpunkt liegt in
  `api/duplicate_decisions.py` mit router-weiter Dependency. Die Router-Iteration von
  `test_auth_guard.py::test_all_project_opencloud_and_stats_routes_require_token` erfasst ihn
  automatisch, und er trägt einen eigenen, pfadbenannten 401-Fall. `project_id` und `photo_id` sind
  mit `ge=1, le=MAX_QUERY_POSITION` begrenzt. In `photos.router` wäre ein vergessener Torwächter still
  öffentlich — ein unauthentifizierter Schreibweg auf den Ausschuss. Tests:
  `::test_the_group_confirm_requires_a_token`; `::test_a_photo_id_outside_the_declared_bounds_is_a_422`
  wird um die Abschluss-URL erweitert.

- **S7 — Der Wächter benennt die neue Aufrufstelle, und kein Eintrag wird gesenkt.**
  `_ERWARTETE_VERWENDUNGEN[("api/duplicate_decisions.py", "has_open_suggestion")]` steigt von 1 auf
  2. Die Einträge für `api/photos.py` bleiben, wie sie sind, und `confirm_ausschuss_gate` wird nicht
  umgebaut. Sonst entstünde unbemerkt eine zweite Fassung von „offen“, die von der Abflussgrenze
  wegläuft. Test:
  `test_ausschuss_ueberlebende.py::test_the_predicates_are_drawn_at_exactly_the_expected_call_sites`.

### Übersicht und Gruppenantwort

- **S8 — Der Stapel ist projektgebunden.** Gruppenschlüssel ist allein `representative_of` über
  `load_duplicate_links(session, project.id)`. Anker, `cover`, `member_count`, `group_size` und
  `decision_counts` stammen aus dem projektbegrenzten Bestand und diesen Kanten. Untersagt sind ein
  eigener SQL-Stern und das Gruppieren über das rohe `duplicate_of`; `None` ist nie ein
  Gruppenschlüssel. Angriff: `duplicate_of` zeigt ohne Projektbedingung auf `photos.id`. Ein Stapel
  nähme sonst fremde Aufnahmen auf oder nennte eine fremde Id als Anker. Ein `None`-Schlüssel fasste
  alle Aufnahmen ohne Gruppe zu einem Stapel zusammen, dessen Link ins Leere führt. Der Detailfilter
  antwortet für eine fremde Id weiter mit einer leeren Liste (Spec 0525 S6). Tests in
  `test_api_ausschuss.py`:
  - `::test_a_group_of_another_project_is_never_named_as_the_anchor`, umgeschrieben: Ein Zeiger ins
    fremde Projekt ergibt `kind: "photo"` mit Anker `null`, und kein `group`-Eintrag nennt die
    fremde Id;
  - `::test_the_stock_of_another_project_never_shows_up`, erweitert auf beide Eintragsarten;
  - `::test_photos_without_a_resolvable_group_stay_single_entries`.

- **S9 — Die Cache-Auflage gilt für beide Eintragsarten.** `cover` ist ein `PhotoOut` und damit eine
  Funktion des anfragenden Nutzers. Die Auflage betrifft jede Zwischenspeicherung der Übersicht, ein
  `ETag`, ein `Cache-Control` über `no-store` hinaus und jeden künftigen clientseitigen
  Laufzeit-Cache: Sie alle führen den Nutzer im Schlüssel. Dass `decision_counts`, `total` und
  `open_count` nutzerunabhängig sind, erlaubt nichts anderes. Bei Verletzung sähe der eine Nutzer
  Vorschlagsanzeige und Bewertungen aus der Sicht des anderen. Kein Test: Die Auflage ist mechanisch
  nicht erzwingbar und steht deshalb in voller Aussage an `AusschussOut`.

- **S10 — Die Messwerte dürfen die Gruppenantwort nicht zerreißen.** `sharpness` und `exposure` kommen
  aus `photo.score`, und zwar über eine Fassung, die `score is None` kennt (dann sind beide `null`),
  nie aus `PhotoOut.suggestion`. `span_seconds` kommt nur aus den projektbegrenzten Kanten. Ein
  ungeschützter Attributzugriff wirft für den Repräsentanten ohne `PhotoScore`. Die Antwort wird dann
  zur `500` — und sie ist der einzige Zugang zur Ansicht, in der über den Abfluss entschieden wird
  (Spec 0486 S3). Test:
  `test_api_duplicate_groups.py::test_a_member_without_a_score_row_reads_as_keep_instead_of_tearing_the_whole_group`,
  erweitert um `sharpness is None and exposure is None`.

### Frontend

- **S11 — `from` wählt eine Variante, er nennt kein Ziel.** Den Rückweg gibt es nur bei
  `searchParams.get('from') === 'ausschuss'`. Sein Ziel ist fest `/projects/{id}/pipeline/ausschuss`,
  gebildet aus der numerischen Projekt-Id der Route. Untersagt ist, das Ziel aus dem Parameterwert,
  aus `document.referrer` oder als `navigate(-1)` zu bilden. Ebenso untersagt ist, den Rohwert
  weiterzureichen oder anzuzeigen: `duplicateComparePath` nimmt einen Bool und schreibt das Literal.
  Angriff: Ein präparierter Link führte einen angemeldeten Nutzer von einer vertrauten Oberfläche auf
  eine fremde Seite, etwa auf ein nachgebautes Login (offene Weiterleitung). Tests in
  `DuplicateComparePage.test.tsx`:
  - `from=ausschuss` ⇒ Link mit `href` genau `/projects/7/pipeline/ausschuss`;
  - `from=https://evil.example`, `from=//evil.example` und `from=Ausschuss` ⇒ kein Link;
  - der Abschluss an der letzten Gruppe navigiert auf den festen Pfad.

  Dazu `projectRoutes.test.ts`: Die Gruppennavigation trägt `from=ausschuss` weiter.

- **S12 — Die Folge von „behalten“ steht in beiden Modi an der Handlung, und der Zustand kommt vom
  Server.** `DUPLICATE_CONSEQUENCE_TEXT` bleibt wortgleich und sichtbar, im Raster wie in der
  Großansicht. Zustandsrahmen, Zustandswort und die Zusammenfassung am Stapel stammen aus
  `effective_decision` bzw. `decision_counts`. Sie kommen nie aus `PhotoOut.suggestion` oder aus einer
  Ableitung in TypeScript (Spec 0486 S2). Der neue `DUPLICATE_HINT_TEXT` aus dem UX-Abschnitt ist
  bestätigt: „erhalten“ hängt am angezeigten Zustand, und der angezeigte Zustand ist das Prädikat.
  Bei Verletzung entschiede der Nutzer über einen Abfluss, von dem er nichts weiß. Tests: Der
  bestehende Fall „benennt an der Handlung …“ läuft zusätzlich in der Großansicht. Der Hinweis-Test
  aus Spec 0486 verliert das Verbot von `bleib|erhalten` und behält das von `noch nicht|offen`.

**Geprüft und ohne Befund:**

- Der Abschluss ändert keinen gegenwärtigen Zustand, denn ein offener Vorschlag wertet schon als
  `discard`. Er löst den Zustand nur von künftigen Läufen, und zwar allein in der zurückhaltenden
  Richtung. Das Restrisiko „verwaistes `discard`“ aus Spec 0374 tritt dadurch häufiger auf, bleibt
  aber dieselbe Art Risiko — wie beim projektweiten Abschluss.
- Kein CSRF: Die Anmeldung läuft über den Bearer-Header, nicht über ein Cookie.
- Keine neue Aufzählbarkeit: `404` und die leere Liste unterscheiden fremd, unbekannt und „ohne
  Gruppe“ nicht.
- Kein neuer XSS-Sink:
  - Der Dateiname erscheint nur als Textknoten und im zugänglichen Namen.
  - Die Kachelmaße des Stapels laufen als Zahl über `justifiedRows` (Regel aus Spec 0489/0531).
  - `Progress` ist ein natives `<progress>` ohne Stil.
- `enlargedId` ist Komponentenzustand, kein Verlaufszustand.
- Der leichte Gesamtbestand im Speicher ist eine Frage der Robustheit, nicht der Sicherheit.
  Hydratisiert wird nur die Seite (`limit ≤ 200`).

`specs/architecture/0003-securitykonzept.md` wird im Umsetzungs-PR ergänzt; die Stellen stehen unter
„Pflegestellen“.

## Teststrategie

Jede Zusage wird auf der niedrigsten Ebene geprüft, die sie widerlegen kann. E2E gibt es nur für Geometrie und echtes CSS. E2E-Specs bleiben lesend: Der Abschluss wird ausschließlich in pytest und vitest geprüft.

### Ebenen je Kriterium

| AK | pytest (Unit/API) | vitest | e2e |
|---|---|---|---|
| A1 | `test_duplicates.py`: `group_span_seconds` rundet ab, ergibt 0 bei gleichem `taken_at` und liest korrigiertes `taken_at` (Lage mit abweichendem `taken_at_original`). `test_api_duplicate_groups.py`: `span_seconds` in der Antwort. Gesamtzahl und Position bleiben über **`POST …/confirm`** gleich (vorher/nachher, über den Schreibweg des Produkts). | `utils/duplicateMetrics.test.ts`: Tabelle der Zeitspannen. Seite: `h1`-Name aus `position`/`total`/`items.length`/`span_seconds` | – |
| A2 | – | Seite: `progress` (`hidden: true`) mit `value`/`max` gleich den Zahlen im `h1`, `aria-hidden` | – |
| A3 | – | Seite: beide Absätze in Raster **und** Großansicht, per `compareDocumentPosition` vor `group` „Ganze Gruppe“, kein Vorfahre `details`/`[role=alert]`. Wächter gegen eine falsche Zusage: `DUPLICATE_HINT_TEXT` passt auf `/angezeigt/i`, nicht auf `/nicht (angetippt\|markiert)\|unentschieden\|noch offen/i` | – |
| A4 | – | `DuplicatePhotoTile.test.tsx`: alle fünf Teile je Karte, kein `[aria-expanded]` | – |
| A5 | bestehend: `test_the_answer_never_says_whether_a_state_came_from_the_automaton_or_the_user` | bestehende Schlüsselmenge `DUPLICATE_ZUSTAENDE`. Seite: jedes `li[data-duplicate-decision]` ∈ {keep, discard}, genau ein `aria-pressed=true` je Wahlzeile | – |
| A6 | – | Der Vertragswächter „Regel 5“ (abgeleitete Menge) erfasst `DuplicateEnlargedView` und `DuplicateStackTile` ohne Zutun; die Kernliste in `designSystem.contract.test.ts` bekommt beide Dateien dazu. Karte und Großansicht ohne `data-dimmed` | Bühne: Treffertest an den vier Ecken des Inhaltsrechtecks des `object-contain`-Bildes liefert das Bild selbst |
| A7 | `test_api_duplicate_groups.py`: `sharpness`/`exposure` aus `PhotoScore`, beide `None` ohne Zeile. **Tragender Fall:** Die Werte bleiben nach einer Entscheidung und nach eigener Albumbewertung (`suggestion` wird `null`) unverändert. | `duplicateMetrics.test.ts`: Formatierung und Auszeichnung (Tabelle unten). Seite: Fixture, in der `photo.suggestion` andere Werte trägt als das Item; angezeigt werden die des Items | – |
| A8 | bestehend: `test_keep_possible_is_false_exactly_where_the_rejection_does_not_follow_from_the_duplicate` | Karte und Seitenspalte: **Anzahl** der Bedienelemente in beiden Datenlagen nebeneinander, kein `disabled` | – |
| A9 | Abschluss-Suite in `test_api_duplicate_decisions.py` (siehe Randfälle) | Seite: Abschluss (Beschriftung ×3, Navigation ×3, Sperre, ein Aufruf bei Doppelklick, Fehler ohne Navigation, Meldung verschwindet beim Ankerwechsel). `useDuplicates.test.tsx`: Die Abschluss-Mutation schreibt die Antwort fort und invalidiert `['photos', projectId]`, also auch den Ausschuss. `api/duplicates.test.ts`: `POST` ohne Body | – |
| A10 | – | `utils/projectRoutes.test.ts`: `duplicateComparePath` mit und ohne `fromAusschuss`. Seite: Tabelle zum Rückweg-Parameter. `AusschussStepPage.test.tsx`: Detail-Link (mit/ohne Anker, auch bei `reason = low_quality` mit Anker), `getDuplicateGroup` wird **nicht** aufgerufen. Bestehend: `PhotoGridPage.test.tsx` (listenweiter Einstieg) | – |
| A11 | – | `DuplicateEnlargedView.test.tsx` (neu) plus Seiten-Integration | Anordnung bei 1280 und 360, Streifen ohne waagerechtes Scrollen, Bühne unverfälscht |
| A12 | bestehend: Kettendurchlauf, „fertige Gruppe bleibt“. Neu: dasselbe nach `confirm` | Seite: Namen, `disabled` am Rand, Fokussprung, Push mit `from`, Rücksetzung von Vergrößerung, Entscheidung und Meldung | `tap-targets`: umbenannte Gruppennavigation |
| A13 | bestehend: `empty_duplicate_group_out` | Seite: vier Zustände, `200` ohne Mitglieder = leer, Rückweg im Leerzustand bei `from` | – |
| A14 | Bestehende Asymmetrie-Suite bleibt **unverändert grün** (Regressionsnachweis). Neu: Zwillingsprojekt-Differenz (siehe unten) | `api/duplicates.test.ts`: Exportmenge genau um `confirmDuplicateGroup` gewachsen, weiterhin kein Rücknahmeweg | – |
| B1 | – | `DuplicateStackTile.test.tsx`: genau zwei `aria-hidden`-Rahmen ohne `img`, genau ein `img` je Stapel, Rahmen im DOM **vor** der vorderen Karte | Rahmen ragen oben und rechts ≥ 1 px über die vordere Karte, Rahmenbreite > 0, beides in `li` enthalten |
| B2 | – | Stapel trägt Zeichen und Wort „Duplikat“ | – |
| B3 | – | `AusschussStepPage`: gemischtes Raster; `photo` → Schaltfläche „… öffnen“ (`?photo=`), `group` → Link | – |
| B4 | – | Genau ein fokussierbares Element je Stapel (Zählung, nicht Namensabfrage); exakter Name; beide Präfixe ausgeschlossen; `href` = Anker mit `from=ausschuss`; kein „öffnen“-Knopf für Gruppenmitglieder | Treffertest in der nur von hinteren Karten belegten Fläche liefert den Link oder einen Nachfahren; Kennzeichen- und Dateinamen-Rechteck liegen in der vorderen Karte |
| B5 | – | – | bei 360 und 1280: `li` füllt mit den Nachbarn die Zeile (Summe der Breiten plus Abstände = Containerbreite ± 1); außer dem Dateinamen gilt je Fußleisten-Teil und Kennzeichen `scrollWidth ≤ clientWidth`; keine waagerechte Scrollbreite |
| B6 | `test_duplicates.py`: `group_ausschuss_stock` rein. `test_api_ausschuss.py`: Partition, Einzigkeit über alle Seiten, Invariante „kein Anker im Listenzweig“ | – | – |
| B7 | `group_size == len(GET duplicate-groups/{anker}.items)` als Gleichheit zweier Beobachtungen; Summe aus `decision_counts` = `member_count` | Stapel zeigt `group_size`, getestet an einer Fixture mit `member_count ≠ group_size`; Zusammenfassung nur mit Teilen ≠ 0, feste Reihenfolge | – |
| B8 | Paginierung über der Gruppierung (siehe unten) | `useAusschuss.test.tsx`: `offset` = Zahl der Einträge (Seite mit einem Stapel aus 5 → nächster `offset` 2, nicht 6). `AusschussStepPage`: Nachladezeile | `no-horizontal-scroll`: Ausschuss-Route |

### Pflicht-Randfälle

**Gruppe über der Seitengrenze (pytest).**
- Gruppe mit 3 Ausschuss-Aufnahmen (t = 0, 1, 2) und eine Einzelaufnahme (t = 3), `limit=2`: Seite 1 = [Stapel, Einzelaufnahme], `member_count` des Stapels **3**. Ein naiver SQL-Schnitt ergäbe 2. `total` ist 2.
- Verschränkte Lage: Gruppe bei t = 0 und t = 5, Einzelaufnahme bei t = 3. Die Reihenfolge ist [Stapel, Einzelaufnahme]; Seite 2 (`offset=1`) = [Einzelaufnahme], ohne zweiten Eintrag derselben Gruppe.
- Seitendurchlauf mit `limit=1`: Jeder Anker kommt genau einmal vor, die Zahl der Einträge ist `total`.
- Bei 3 offenen Verlierern in einer Gruppe ist `total = 1` und `open_count = 3`. Das sind zwei Einheiten in einem Fall; hier fallen sie auseinander.
- Detailfilter auf ein Gruppenmitglied: `photo`-Eintrag mit Anker, `total` gleich dem des Listenzweigs.

**Gewinner mit Schärfe-Ablehnung.**
- Er liegt im Stapel, nicht als Einzelkachel „Geringe Bildqualität“, und zählt in `member_count`.
- In der Vergleichsansicht hat er keine Wahlzeile (A8).
- `confirm` schreibt für ihn `discard`; sein angezeigter Zustand bleibt „Ausschuss“.
- Detailansicht über `?photo=`: `reason = low_quality` bei gesetztem Anker → der Link wird trotzdem angeboten.
- Zusätzlich der Gewinner **nur mit `keep`-Zeile**, entstanden über „Alle behalten“ auf dem Schreibweg des Produkts: danach `member_count == group_size` und `decision_counts.keep == group_size`.

**Die Zahlen des Stapels unterscheiden sich.**
- Gewinner ohne Vorschlag, nicht im Bestand und zeitlich zuerst: `group_size` = `member_count` + 1, und `cover` ist **nicht** der Gewinner.
- Unveränderliches Mitglied mit `keep`-Zeile: `decision_counts.keep = 1`, obwohl der angezeigte Zustand „Ausschuss“ ist. Hier weichen gespeicherte Zeile und Wirkung voneinander ab.

**Fehlende Messwerte.**
- pytest: Repräsentant ohne `PhotoScore`-Zeile → `sharpness`/`exposure` sind `None`; die übrigen Mitglieder tragen Werte.
- vitest, einzeln parametrisiert, weil der Typ beides zulässt:
  - `sharpness` null → „nicht gemessen“;
  - `exposure` null → die Zeile fehlt;
  - `0` ist ein Wert und keine Abwesenheit: Schärfe „0“, Belichtung „0 % ohne Zeichnung“.
  - Ein `null`-Wert trägt nie eine Auszeichnung.

**Gleichstand bei „schärfste“** (`duplicateMetrics`, jeweils die Menge der ausgezeichneten Indizes).
- [100, 200, 300] → {2}
- [412.7, 413.2, 100] → {0, 1}: Rohwerte verschieden, angezeigt beide „413“. **Das ist der tragende Fall.**
- [300, 300, 100] → {0, 1}
- [300, 300] → ∅
- [300, null] → ∅
- [null, null] → ∅
- [300, null, 100] → {0}
- Belichtung (Minimum): [0.0004, 0.0, 0.2] → {0, 1}
- Schärfe und Belichtung werden unabhängig ausgezeichnet: Beste Schärfe auf A und beste Belichtung auf B in einer Gruppe.
- Seitentest: Die Auszeichnung auf einer Karte mit Zustand `discard` neben `keep` auf einer anderen ändert an keiner Karte `data-duplicate-decision`, `aria-pressed` oder die Menge der Schaltflächen.

**Formatierung.**
- Schärfe: 412.7 → „413“, 0.7341 → „0,734“ und ein Wert ≥ 1000 (Erwartung siehe Hinweise).
- Zeitspanne: 0, 1, 59, 60, 119, 3599, 3600 („1 Stunde“), 3660, 7320, dazu die Demo-Spannen 51 und 102 min.

**Letzte Gruppe (vitest).**
- „Nächste Gruppe“ ist `disabled`.
- Die Beschriftungen des Abschlusses mit und ohne `from`.
- Mit `from`: Push auf `/projects/1/pipeline/ausschuss`, geprüft am beobachteten Pfad, nicht an einem Spion auf `navigate`.
- Ohne `from`: Der Pfad bleibt, und `aria-live` meldet den Satz. Nach „Vorherige Gruppe“ ist der Satz verschwunden.
- Scheitert der Abschluss (`409`), gibt es keine Navigation, `Alert` mit `detail`, und die Schaltfläche ist wieder bedienbar.

**Rand der Großansicht (vitest).**
- Erstes und letztes Mitglied: `disabled`; ← bzw. → ohne Wirkung; ein Fokus auf der gesperrten Schaltfläche springt auf die Gegenschaltfläche. Dasselbe gilt für die Gruppennavigation.
- Klick im Streifen springt direkt.
- Nach dem Schließen liegt der Fokus auf der Bildfläche der zuletzt **gezeigten** Aufnahme, nicht der zuerst geöffneten.
- `enlargedId` ist eine Foto-Id: Eine Entscheidungsantwort in anderer Reihenfolge hält dieselbe Aufnahme. Fehlt die Aufnahme in der neuen Antwort, fällt die Ansicht auf das Raster zurück.
- Beim Ankerwechsel wird zurückgesetzt, über Hin- und Rückweg (bestehendes Muster).
- Die Pfeiltasten wirken nur in der Großansicht.

**360 px (e2e).**
- Neuer Spec `duplikat-vergleich.spec.ts`:
  - Rasterzustand: Beide Wahlschaltflächen jeder Karte liegen vollständig im Rechteck ihrer Karte. Die UX-Rechnung (169 px Bedarf gegen 142 px) ist hier erstmals gemessen.
  - Großansicht bei 1280: Seitenspalte waagerecht disjunkt rechts neben der Bühne und senkrecht überlappend; Streifen unter beiden. Bei 360: untereinander. Das sind zwei Anordnungen, die sich unterscheiden müssen.
  - Bühnenbild unverfälscht per Eck-Treffertest.
- Neuer Spec `ausschuss-stapel.spec.ts`: B1, B4 und B5 bei 360 und 1280 im Projekt „Demo — Duplikate“. Vorbedingung: genau 2 Stapel.
- `no-horizontal-scroll`:
  - neue Route `/projects/{dup}/pipeline/ausschuss` mit Vorbedingung „Stapel sichtbar“;
  - eigene Messung der Großansicht, weil sie ein anderes DOM an derselben Route ist, ohne zweiten Routeneintrag;
  - der Kopf mit langer Spanne („… in 1 Stunde 42 Minuten“) muss umbrechen.
- `tap-targets`: Gruppennavigation (umbenannt) sowie „Vorherige/Nächste Aufnahme“ in der Großansicht.
- Rot-Nachweise im PR:
  - `flex-wrap` der Wahlzeile entfernen;
  - `lg:flex-row` entfernen;
  - eine Überlagerung über das Bühnenbild legen;
  - Stapelversatz nach außen (`-top-2`);
  - hintere Karten ohne `pointer-events-none` außerhalb des Links;
  - `whitespace-nowrap` an der Zählangabe.

**Fremdprojekt-Ids (pytest).**
- Übersicht:
  - Eigener Verlierer zeigt auf den Gewinner eines fremden Projekts → `photo`-Eintrag, Anker `null`, kein Stapel.
  - Fremde Aufnahme zeigt in die eigene Gruppe → `group_size` bleibt die Zahl der eigenen Mitglieder.
- `confirm`:
  - `401` ohne Token.
  - `422` bei `photo_id` ∈ {0, −1, MAX+1}.
  - `404` bei unbekanntem Projekt.
  - `404` bei einer Foto-Id eines fremden Projekts; **keine** Zeile in beiden Projekten.
  - Scharfe Form: Eine fremde Aufnahme mit offenem Vorschlag und `duplicate_of` auf den eigenen Gewinner bekommt keine Zeile.
  - Ein Body mit Id-Liste (`{"photo_ids": [x]}`, x offener Vorschlag außerhalb der Gruppe) wird nicht gelesen; x bleibt ohne Zeile.
  - Einzelaufnahme mit geringer Bildqualität ohne Gruppe in einem Projekt, das zugleich eine Gruppe hat → `404`, projektweit keine neue Zeile. Das ist der `None`-Repräsentant-Fall.
  - `confirm` über eine Verlierer-Id schreibt dieselbe Menge wie über die Gewinner-Id.

**Idempotenz und Menge des Abschlusses (pytest).**
- Menge:
  - `discard` genau für Mitglieder ∩ offener Vorschlag ∩ Projekt.
  - Mitglied mit `keep`- oder `discard`-Zeile: Die Zeile bleibt **inhaltlich** unverändert.
  - Gewinner ohne Vorschlag: bekommt keine Zeile. Das ist der Fall, der das untersagte Festschreiben aus dem Client unterscheidet.
  - Die andere Gruppe desselben Projekts bleibt unberührt.
  - `gate_confirmed_at` bleibt unverändert.
- Wiederholung: Der zweite Aufruf antwortet `200` mit gleichem Körper, die Zeilenzahl bleibt gleich, kein `409`.
- Nebenläufigkeit: `IntegrityError` → `409`, nie `500` (bestehendes Monkeypatch-Muster).
- Erzwungener Abbruch nach der ersten Zeile → keine Teilmenge (bestehendes Muster).
- Anzeige-Invarianz: `effective_decision` jedes Mitglieds ist vor und nach dem Abschluss gleich.
- `open_count` sinkt genau um die offenen Vorschläge der Gruppe.
- Antwortform: Lesepfad, Einzelweg, Gruppenweg und `confirm` liefern dieselbe Struktur (Gleichheit über vier Aufrufe).
- A14 als Zwillingsprojekt-Differenz: Projekt P1 durchläuft Gruppenabschluss und danach `confirm-ausschuss-gate`, Projekt P2 nur `confirm-ausschuss-gate`. Die Mengen (`relative_path`, `decision`) sind gleich, und kein `409` tritt auf.
- UI: Doppelklick → genau ein Aufruf. Die Schaltfläche ist gesperrt, solange eine Einzel- oder Gruppenentscheidung hängt.

**Rückweg-Parameter (vitest, eine parametrisierte Tabelle).**
- `from=ausschuss` → Link mit `href` exakt `/projects/1/pipeline/ausschuss`.
- Kein Link bei: fehlendem `from`, `from=`, `from=Ausschuss`, `from=ausschuss2`, `from=https%3A%2F%2Fexample.org`, `from=%2Fprojects%2F2%2Fpipeline%2Fausschuss`, `?from=x&from=ausschuss`.
- „Nächste Gruppe“ und Abschluss erhalten `?from=ausschuss`; ohne `from` wird keiner angehängt.

### Bewusst nicht automatisiert

- Die Wahrnehmungsaussagen („ohne Text als mehrere gleiche Aufnahmen lesbar“, „so hell wie“) sind gestalterisches Urteil. Die nachrechenbaren Teile tragen der Vertragswächter A6 und die Geometrie B1; der Rest wird im `review-ux`-Blick mit `browse-app` geprüft.
- Dass `DUPLICATE_CONSEQUENCE_TEXT` wortgleich bleibt, wird im Review am Diff geprüft. Ein neuer Wortlaut-Test würde nur den Ist-Text festschreiben.
- Dass nur die Seite hydratisiert wird, ist Leistung ohne beobachtbares Verhalten.

### Umzuschreibende Bestandstests

#### A. Abgelöste Zusagen — bewusst umschreiben (keine Regression)

**Backend**
- `backend/tests/test_api_ausschuss.py::test_the_group_anchor_names_the_representative_of_the_duplicate_group` — Im Listenzweig trägt der Verlierer keinen `photo`-Eintrag mit Anker mehr. Neu: Stapel im Listenzweig plus `photo`-Eintrag mit Anker über `?photo=`.
- `backend/tests/test_api_ausschuss.py::test_the_reason_matches_the_suggestion_reason_of_the_score` — Der `duplicate`-Fall erscheint im Listenzweig nicht mehr als `photo`-Eintrag. Neu: `low_quality` im Listenzweig, `duplicate` über den Detailfilter.
- `backend/tests/test_api_ausschuss.py::test_the_answer_carries_exactly_the_agreed_fields` — Die Feldmenge wächst um `kind`; hinzu kommt eine zweite Eintragsart mit eigener Feldmenge. Neu: je Art Gleichheit der Feldmenge; `cover` hat dieselbe Feldmenge wie ein Item der Fotoliste.

**Frontend**
- `frontend/src/pages/DuplicateComparePage.test.tsx` › „nennt Position und Gesamtzahl in der Seitenueberschrift“ — `Duplikat-Gruppe 2 von 5` wird zu `Gruppe 2 von 5 · {n} Aufnahmen in {Spanne}`.
- dieselbe Datei › „traegt eine unveraenderliche Hinweiszeile ueber den DARGESTELLTEN Zustand“ — Der Test verbietet `bleib|erhalten`, A3 verlangt genau diese Zusage, gebunden an den angezeigten Zustand. Neuer Wächter siehe Teststrategie A3.
- dieselbe Datei, Block „die Gruppennavigation“ (alle sechs Fälle):
  - „steht ohne jede Vergroesserung im Seitenkopf“ — Namen ändern sich zu „Vorherige/Nächste Gruppe“; neu ist die Präsenz in **beiden** Modi.
  - „traegt Namen, die sich nicht mit dem Blaettern INNERHALB der Gruppe ueberschneiden“ — neue Namenspaare Gruppe gegen Aufnahme.
  - „beginnt den zugaenglichen Namen mit der sichtbaren Beschriftung (WCAG 2.5.3)“ — `Zurück`/`Vor` mit `aria-label` wird zu Name = sichtbarer Text ohne `aria-label`.
  - „ist %s genau dort disabled, wo der Nachbarwert null ist“ — nur die Namen; zusätzlich der Fokussprung.
  - „bleibt WAEHREND DES LADENS der Nachbargruppe stehen“ — nur die Namen.
  - „navigiert auf den Anker der Nachbargruppe - als Push, nicht als Ersetzung“ — nur die Namen; zusätzlich die Fälle mit `from`.
- dieselbe Datei, Block „der Ankerwechsel“ › „nimmt die Vergroesserung zurueck“ und „nimmt die laufende Entscheidung zurueck“ — Marker `/verkleinern$/` und die alten Gruppennamen. Die Zusage bleibt, der Nachweis läuft über `h2` „Aufnahme … von …“.
- dieselbe Datei, Block „die Vergroesserung“:
  - „vergroessert hoechstens EIN Mitglied und laesst alle uebrigen im Dokument“ — **abgelöst**: Die Großansicht ersetzt das Raster. Neu: Raster nicht im Dokument, der Streifen führt alle Mitglieder.
  - „verkleinert beim erneuten Antippen derselben Kachel“ — **abgelöst**: Es gibt kein Umschalten an der Karte mehr. Entfällt; das Schließen decken die Esc- und Schließen-Fälle ab.
  - „verkleinert per Esc“, „bietet ein sichtbares Schliessen-Element …“, „blaettert mit Vor/Zurueck, ohne zu verkleinern“, „blaettert auch mit den Pfeiltasten“, „bleibt am ersten und letzten Mitglied stehen und weist das aus“, „haelt die Vergroesserung bei einer Entscheidung und blaettert nicht weiter“ — `Nächste/Vorherige Aufnahme der Gruppe` wird zu `Nächste/Vorherige Aufnahme`; Marker `verkleinern` wird zu `h2`/`aria-current`. Diese Fälle wandern in `DuplicateEnlargedView.test.tsx`.
- `frontend/src/components/DuplicatePhotoTile.test.tsx` (Props `enlarged`/`controls` entfallen):
  - „traegt in keinem Zustand und in keiner Darstellung ein data-dimmed“ — die Schleife über `enlarged` entfällt; die Großansicht bekommt einen eigenen Fall.
  - „reserviert die Hoehe der Bildflaeche in BEIDEN Zustaenden, bevor das Bild da ist“ — `h-96` wandert von der Karte in die Bühne (`h-96 lg:h-144`).
  - „zeigt Zustandsrahmen, Symbol und Wort auch in der Vergroesserung“ — wandert zur Seitenspalte.
  - „nennt in der Vergroesserung die Gegenaktion“ — **abgelöst** (kein „verkleinern“ an der Karte); entfällt.
  - „laesst die Entscheidung auch in der Vergroesserung zu“ — wandert zur Seitenspalte.
- `frontend/src/pages/pipeline/AusschussStepPage.test.tsx`:
  - › „zeigt beim Duplikat die ganze Gruppe ueber den Gruppenanker“ — **abgelöst**: Die eingebettete Gruppe entfällt. Neu: Link „Duplikat-Gruppe vergleichen“ auf den Anker mit `from=ausschuss`, `getDuplicateGroup` wird nicht aufgerufen, kein `duplicate-image`.
  - › „nennt den Grund je Kachel mit Zeichen UND Wort, unterscheidbar nach Art“ — „Duplikat“ kommt jetzt vom Stapel (`kind: group`) neben der Einzelkachel.
  - › „laedt bei mehr Bestand als einer Seite nach“ — `60 von 61 geladen` wird zu `60 von 61 Einträgen geladen`.

**E2E**
- `e2e/tests/grid-columns.spec.ts` › „vergroesserte Kachel spannt die Rasterbreite und laesst die Gruppe im Blick“ — **abgelöst** (A11). Entfällt; Ersatz ist der neue `duplikat-vergleich.spec.ts`.
- `e2e/lib/demo.ts::openDuplicateGroup` — Überschrift `/^Duplikat-Gruppe \d+ von \d+$/` wird zu `/^Gruppe \d+ von \d+ · /`, `Vor zur nächsten Gruppe` wird zu `Nächste Gruppe`. Das trägt alle nutzenden Specs mit.
- `e2e/tests/tap-targets.spec.ts` › „Bedienelemente des heissen Pfads sind auf 44 x 44 px treffbar“, Abschnitt Gruppennavigation — neue Namen.

#### B. Benannte Sollgrößen- und Fixture-Nachzüge (die Zusage bleibt)

- `backend/tests/test_ausschuss_ueberlebende.py`:
  - `_ERWARTETE_VERWENDUNGEN[("api/duplicate_decisions.py", "has_open_suggestion")]` geht von 1 auf 2 (trägt `::test_the_predicates_are_drawn_at_exactly_the_expected_call_sites`). Kein Eintrag sinkt.
  - `::test_the_six_replaced_occurrences_and_the_written_call_sites_are_held_side_by_side`: `sum == 11` wird `12`, `sql == 9` wird `10`.
- `backend/tests/test_api_duplicate_groups.py::test_the_item_carries_an_unextended_photo_out` — Die Feldmengen von Item und Gruppe wachsen um `sharpness`/`exposure` bzw. `span_seconds`; die Zusage „`PhotoOut` unerweitert“ bleibt.
- `backend/tests/test_api_duplicate_decisions.py::test_a_low_quality_suggestion_is_decidable_on_the_single_path` — das exakte Leer-Dict bekommt `"span_seconds": 0`.
- `backend/tests/test_api_duplicate_decisions.py::test_both_write_paths_answer_in_the_same_form_as_the_read_path` — wird auf vier Aufrufe erweitert (mit `confirm`).
- `backend/tests/test_openapi_beschreibungen.py::DOCUMENTED_ROUTES` — neu `("post", "/projects/{project_id}/duplicate-groups/{photo_id}/confirm")`.
- `backend/tests/test_api_ausschuss.py`:
  - Helfer `_ids`/`_entry` verzweigen nach `kind`.
  - `::test_two_pages_do_not_overlap_and_the_total_counts_everything` — Docstring auf „total zählt Einträge“; der Fall bleibt als Spezialfall nur mit Einzelaufnahmen.
- `frontend/src/api/duplicates.test.ts` › „kennt keinen Weg zurueck nach "noch nicht entschieden"“ — die Sollmenge der Exporte bekommt `confirmDuplicateGroup` (fünf Exporte), weiterhin kein Rücknahmeweg.
- `frontend/src/pages/pipeline/AusschussStepPage.test.tsx`:
  - Fixture `entry()`: `kind: 'photo'`, Vorgabe `reason: 'low_quality'`, `groupAnchorPhotoId: null`. Ein `photo`-Eintrag mit Anker ist im Listenzweig nicht mehr möglich; die Vorgabe darf ihn nicht erzeugen.
  - Die `beforeEach`-Vorgabe von `getDuplicateGroup` entfällt.
- `frontend/src/hooks/useAusschuss.test.tsx` — Fixture `stand()`: `kind: 'photo'`, Anker `null`.
- `frontend/src/api/ausschuss.test.ts` (`STAND`), `frontend/src/hooks/useDuplicates.test.tsx` (`GROUP`), `frontend/src/api/duplicates.test.ts` (`GROUP`), `frontend/src/pages/DuplicateComparePage.test.tsx` (`group()`) — Typnachzug `kind` bzw. `sharpness`/`exposure`/`span_seconds`.
- `frontend/src/pages/DuplicateComparePage.test.tsx::tiles()` — auf `[data-duplicate-decision]` einengen, sonst zählt der Streifen mit.
- `frontend/src/components/DuplicatePhotoTile.test.tsx` — `onToggle` wird durch den neuen Öffnen-Rückruf ersetzt (betrifft „ist ein natives button …“, „wirkt mit Enter und Leertaste …“, „nennt den Dateinamen in JEDEM zugaenglichen Namen der Kachel (%s)“).
- `frontend/src/designSystem.contract.test.ts` — Kernliste in „daempft in keiner bildtragenden Datei …“ um `DuplicateEnlargedView` und `DuplicateStackTile` erweitern; `TALL_CONTROL_ALLOWLIST` um die drei `h-11 sm:h-8`-Stellen (Wahlzeile, Aufnahme- und Gruppennavigation).
- `e2e/tests/no-horizontal-scroll.spec.ts` › „keine Route erzeugt horizontales Scrollen bei 360 px“ — neue Ausschuss-Route; Großansicht als eigene Messung.

#### C. Bewusst unverändert — Regressionsnachweis für A5, A8, A12 und A14

Folgende Tests bleiben unverändert:
- `test_api_duplicate_decisions.py`: die Asymmetrie- und Neulauf-Fälle.
- `test_api_duplicate_groups.py`:
  - Zähler- und Nachbar-Fälle;
  - `::test_a_finished_group_keeps_its_place_and_stays_reachable`;
  - `::test_the_answer_never_says_whether_a_state_came_from_the_automaton_or_the_user`.
- `test_api_duplicate_group_index.py`, komplett.
- `test_duplicates.py`: Kettendurchlauf.
- `test_api_ausschuss.py`:
  - `::test_a_group_of_another_project_is_never_named_as_the_anchor` — gilt weiter für den Listenzweig und wird um `kind == "photo"` ergänzt;
  - `::test_a_photo_filter_outside_the_stock_answers_an_empty_list`;
  - die Auth- und Grenzfälle.
- `PhotoGridPage.test.tsx`: listenweiter Einstieg.
- `grid-columns.spec.ts` › „Duplikat-Vergleich bricht um, statt die Bilder zu verkleinern“ (nur über den Helfer nachgezogen).

## Pflegestellen im Umsetzungs-PR

### `design/penpot/views.json`

Schlüssel `duplikate`:

- `produktdateien`: `src/components/DuplicateEnlargedView.tsx` ergänzen.
- `luecken` streichen: `daempfung`, `neutralerumriss` und `zaehlerbaustein`. Der Zähler ist jetzt `progress` über einer konstanten Gesamtzahl; `progress` bleibt in `bausteine`.
- `umrissstaerke` neu fassen: eine Stärke (2 px) für beide Zustände, weiterhin ohne Token für Linienstärken.
- `kennzeichenbaustein`: in der Stelle „noch offen“ streichen, den Grund behalten.
- `behaelter`: die Stelle um die Seitenspalte der Großansicht erweitern.
- Neue Lücke `entwurfsabweichung`: Die Penpot-Seite zeigt noch den dritten Zustand mit neutralem Umriss und die gedämpfte Ausschuss-Fläche. Die Umsetzung kennt nach Story #533 zwei Zustände in voller Helligkeit.
- Neue Lücke `buehnenhoehe`: Die reservierte Höhe der Bühne (`h-96`/`lg:h-144`) hat kein Token.
- Neue Lücke `streifen`: Die Vorschaugröße (64/80 px) hat kein Token; die aktuelle Aufnahme ist in `--text-h` statt Akzent ausgezeichnet.
- Neue Lücke `trefferflaeche`: Heißer Pfad mit sichtbaren 44 px auf der schmalen Breite.
- `zustaende` bleiben unverändert, es gibt keine neue Ansicht. Die ERWARTET-Zähler in `payload.test.ts` bleiben gleich.

Schlüssel `ausschuss`:

- `produktdateien`: `src/components/DuplicatePhotoTile.tsx` durch `src/components/DuplicateStackTile.tsx` ersetzen. Die Seite importiert die Karte nicht mehr.
- `stapel` neu fassen: Versatz 4/8 px aus der Abstandsskala innerhalb der gerechneten Kachelmaße; hintere Karten sind Rahmen in `--border-control` ohne Bild; die Bibliothek hat keinen Stapel-Baustein.

### `specs/architecture/0004-design-system.md` und Skill `design-system`

- Neues Muster „Duplikat-Stapel“ unter „Zusammengesetzte Bausteine“: ein `Link`, hintere Karten `aria-hidden` ohne Bild, Versatz innerhalb der Kachel, `overflow-hidden` nur an der vorderen Karte (sonst wird der Fokusring abgeschnitten), Kanten in `--border-control`, das Grund-Wort bleibt.
- Neues Muster „Großansicht der Vergleichsansicht“: am Ort statt als Dialog, die Seitenspalte trägt Zustand und Wahl. Abgrenzung zu „Großansicht aus dem Raster“ (Spec 0531): Die dortige bewertet nichts, diese entscheidet.
- Begründete Abweichung von „Auswahl = Akzentkante“: Wo Akzent schon einen Zustand trägt (hier „Behalten“), wird die aktuelle Position in `--text-h` ausgezeichnet und mit `aria-current` versehen.
- Muster „Auszeichnung je Messwert“: nur ein Wort, nie Akzent, Symbol oder Rahmen; über den angezeigten Werten gebildet.
- Trefferflächen: Wahlzeile und Blätter-Navigation der Vergleichsansicht zählen zum heißen Pfad (`h-11 sm:h-8`).
- Eintrag zu `Progress`: neue Aufrufstelle als Positionsanzeige mit bestimmtem Wert; die Zahl steht als Text im `h1`.
- Bekannte Lücken: Die Penpot-Seite `duplikate` ist in den Punkten dritter Zustand und Dämpfung veraltet.
- Skill `design-system` im selben PR nachziehen: Stapel, Großansicht der Vergleichsansicht, Messwert-Auszeichnung, heißer Pfad.

### `specs/architecture/0003-securitykonzept.md`

Zeilennummern: Stand bei Anlage der Spec.

1. **Kopfzeile „Letzte Aktualisierung“ (Z. 4):** vorn einen neuen Eintrag setzen, etwa: „Spec 0533 —
   der Gruppenabschluss löst den Stern vor dem Schreiben auf, fügt nur `discard` ein und lässt das Gate
   unberührt; der Duplikat-Stapel ist projektgebunden; ein Query-Parameter wählt einen Rückweg und
   nennt kein Ziel; davor …“.

2. **Ankerliste, Zeile zum Ausschuss-Überlebender-Bestand (Z. 140):**
   - Aussagespalte um diesen Satz ergänzen: „Seit Spec 0533 zieht der gruppenbezogene Abschluss
     `has_open_suggestion` als dritte Schreibstelle; sein Wächter-Eintrag steigt von 1 auf 2, keiner
     sinkt.“
   - Codespalte nach `api/duplicate_decisions.py::_has_open_suggestion` ergänzen: „seit Spec 0533 die
     Auswahl des Gruppenabschlusses in `api/duplicate_decisions.py` (Auflage S2)“.

3. **Ankerliste, neue Zeile direkt nach der Zeile zum projektweiten Massenabschluss (Z. 142):**
   - Aussage: Der **gruppenbezogene** Abschluss löst den Stern zuerst auf. Er antwortet `404`, bevor
     geschrieben wird, auch bei offenem Vorschlag, denn `member_ids_of(None, …)` wäre jedes Foto ohne
     `duplicate_of`. Er wählt Projektbindung, Mitgliedschaft und `has_open_suggestion()` in **einer**
     Anweisung mit innerem Join auf `PhotoScore`. Er fügt nur `discard` ein, ohne `DELETE`, ohne
     Körper und nie über `_write`. Ein Wettlauf ergibt `409` statt `500`, und `gate_confirmed_at`
     bleibt unberührt (Spec 0533, S1–S6).
   - Codespalte: die Abschluss-Funktion in `api/duplicate_decisions.py`.
   - Testspalte (alle in `test_api_duplicate_decisions.py`):
     - `::test_the_group_confirm_resolves_the_group_before_writing`
     - `::test_the_group_confirm_writes_discard_only_for_the_open_suggestions_of_this_group`
     - `::test_a_photo_of_another_project_is_a_404_for_the_group_confirm`
     - `::test_the_group_confirm_never_issues_a_delete`
     - `::test_a_concurrent_write_during_the_group_confirm_is_a_409_and_writes_nothing`
     - `::test_the_group_confirm_reads_no_body`
     - `::test_the_group_confirm_never_sets_the_gate`
     - `::test_the_group_confirm_requires_a_token`

4. **Ankerliste, neue Zeile (Frontend):**
   - Aussage: Ein Rückweg-Parameter wählt eine Variante und nennt kein Ziel. Es zählt nur der wörtliche
     Wert `ausschuss`. Das Ziel ist ein fester Pfad aus der numerischen Projekt-Id, nie der
     Parameterwert, `document.referrer` oder `navigate(-1)`; sonst entsteht eine offene Weiterleitung
     (Spec 0533, S11).
   - Codespalte: `frontend/src/utils/projectRoutes.ts::duplicateComparePath`,
     `pages/DuplicateComparePage.tsx`.
   - Testspalte: `DuplicateComparePage.test.tsx` (fremde Werte ⇒ kein Link, fester `href`, Abschluss
     an der letzten Gruppe) und `projectRoutes.test.ts`.

5. **Angriffsflächen › Frontend, neuer projektweiter Punkt nach „Browser-Verlaufszustand als
   App-Zustand“ (nach Z. 213):** „**Query-Parameter, die eine Navigation beeinflussen (seit Spec
   0533, projektweit):** Ein solcher Parameter wählt zwischen Zielen, die im Code festgelegt sind.
   Sein Wert wird verglichen, aber nie eingesetzt, weitergereicht oder angezeigt. Ein Link, der ihn
   weiterträgt, schreibt das eigene Literal. Bei Verletzung wird die Anwendung zur offenen
   Weiterleitung: Ein präparierter Link führt den angemeldeten Nutzer auf eine fremde Seite, etwa auf
   ein nachgebautes Login.“

6. **Angriffsflächen, neuer Abschnitt nach dem zu ADR 0121/Spec 0525 (nach Z. 1264):**
   - Überschrift: „### Der Ausschuss fasst Duplikatgruppen zu Stapeln, und ein Abschluss schreibt je
     Gruppe (ADR 0125/Spec 0533)“, beide verlinkt wie in den Nachbarabschnitten.
   - Einleitung wie in den Nachbarabschnitten:
     - Fortschreibung, keine neue Klasse von Angriffsflächen, ADR 0104 unangetastet.
     - Neu sind ein dritter Schreibweg mit servergebildeter Menge, eine Übersicht aus
       `duplicate_of`-Kanten und der erste Rückweg-Parameter.
     - Die Auflagen der Specs 0374, 0486 und 0525 gelten fort.
   - Danach S1–S12 der Spec 0533 in verkürzter Form, je ein Satz mit dem benannten Angriff:
     - **S1:** `member_ids_of(None, …)` ⇒ ein projektweites `discard` über ein Einzelfoto.
     - **S2:** Ohne inneren Join entsteht ein kartesisches Produkt, und der Gewinner verliert still
       seinen Platz.
     - **S3:** Das `DELETE` aus `_write` ersetzte eine im Wettlauf committete `keep`-Zeile.
     - **S4:** Ein aus der Anzeige geschriebenes `keep` wird nach einem Neulauf wirksam.
     - **S5:** Ein gesetztes Gate öffnet den Cloud-Teilschritt ohne projektweite Bestätigung.
     - **S6:** dreifacher Torwächter.
     - **S7:** Der Wächter steigt von 1 auf 2.
     - **S8:** Stapelschlüssel nur über `representative_of` und projektgebundene Kanten, `None` nie
       als Schlüssel.
     - **S9:** Die Cache-Auflage gilt für beide Eintragsarten.
     - **S10:** Messwerte sind `null`-sicher.
     - **S11:** Verweis auf den neuen Frontend-Punkt.
     - **S12:** Der Folgetext steht in beiden Modi.
   - Zum Schluss „Ausdrücklich geprüft und ohne Befund“ wie in der Spec.

7. **Abschnitt zu Spec 0525, Auflage S5 (Z. 1257), Korrektur:** Der Satz „`limit`/`offset` sind es
   ebenfalls“ stimmt am Bestand nicht. `offset` trägt in `api/photos.py::list_ausschuss` nur `ge=0`.
   Neue Fassung: „`limit` ist es ebenfalls; `offset` ist nur nach unten begrenzt und erreicht seit
   Spec 0533 die Datenbank nicht mehr, weil erst nach dem Gruppieren geschnitten wird.“

8. **Bewusst akzeptierte Restrisiken, „Ein verwaistes `discard` ist unerreichbar“ (Z. 1317):**
   Halbsatz ergänzen: „seit Spec 0525 und 0533 entsteht es zusätzlich über beide Abschlüsse —
   häufiger, aber dieselbe Art Risiko“.

**Keine Änderung nötig:**
- Auth-Zeile für `photos`/`ratings` (Z. 119): Der neue Endpunkt liegt in einem Router mit
  Dependency.
- REST-API-Punkt zu den Routern (Z. 165): Es kommt kein neuer Router hinzu.
- Cloud-Vertrauensgrenze: Die vier cloud-bestimmenden Abfragen bleiben unberührt.

### `specs/architecture/0002-testkonzept.md`

**1. Neue Sektion nach der 0525-Sektion:** „Einträge, die erst nach dem Laden entstehen: Paginierung über einer Gruppierung, ein Teilmengen-Schreibweg als Differenz und ein Rückweg-Parameter mit Wortlaut-Vergleich“ — neu für Spec 0533 / ADR 0125. Sie enthält vier Muster:

1. **Eine Paginierung über im Speicher gebildeten Einträgen wird an der Lage geprüft, in der der SQL-Schnitt eine Gruppe teilte.** Zugesichert wird über die Mitgliederzahl des Eintrags auf der ersten Seite und über die Abwesenheit eines zweiten Eintrags derselben Gruppe auf der Folgeseite. Ids allein bestehen auch gegen den naiven Schnitt. Zählt dieselbe Antwort zwei Einheiten (Einträge und Aufnahmen), gehört ein Fall dazu, in dem die beiden auseinanderfallen.
2. **Ein Schreibweg, der als Einschränkung eines bestehenden zugesagt ist („dieselbe Wirkung, die der Gesamtweg später hätte“), wird als Differenz zweier Projektzwillinge geprüft.** Zwilling 1 läuft über Teilweg und Gesamtweg, Zwilling 2 nur über den Gesamtweg; verglichen wird die gleiche Zeilenmenge. Dazu kommt die Invarianz der Anzeige vor und nach dem Teilweg. Einzelne Erwartungswerte bestehen auch dann, wenn beide Wege auseinanderlaufen und beide Erwartungen mitgezogen werden.
3. **Ein URL-Parameter, der ein Bedienelement freischaltet, wird über eine Tabelle abgelehnter Werte geprüft, und das Ziel über exakte Gleichheit.** Zur Tabelle gehören Groß-/Kleinschreibung, Präfix und Suffix, eine absolute URL, ein interner Pfad und ein doppelter Parameter. So fällt eine Ableitung des Ziels aus dem Wert auf (offene Weiterleitung).
4. **E2E: `pointer-events: none` macht ein Element für `elementFromPoint` unsichtbar.** „Verdeckt nicht“ ist für solche Elemente per Treffertest nicht prüfbar und wird über das Enthaltensein der Rechtecke nachgewiesen. „Kein eigenes Ziel“ wird umgekehrt per Treffertest auf die **nur** von ihnen belegte Fläche geprüft: Er muss das eine Bedienelement liefern. Dieser Satz gehört zusätzlich in den Absatz „Trefferflächen werden getroffen, nicht gemessen“.

**2. Tabelle „Umfang: welche Specs es gibt“:**
- neue Zeile `duplikat-vergleich`:
  - Prüft: Wahlzeile im Kartenrechteck bei 360; Großansicht neben- bzw. untereinander bei 1280/360; Bühnenbild unverfälscht per Eck-Treffertest.
  - Macht rot: zwei Anordnungen, die sich unterscheiden müssen; Vorbedingung, dass die Großansicht offen ist (`h2` sichtbar).
- neue Zeile `ausschuss-stapel`:
  - Prüft B1/B4/B5 bei 360 und 1280.
  - Macht rot: exakt 2 Stapel als Vorbedingung, Überstand der hinteren Karten, Treffertest auf die Fläche der hinteren Karten, Zeilenfüllung, `scrollWidth ≤ clientWidth` der Beschriftung.
- `no-horizontal-scroll`: Ausschuss-Route und Großansicht ergänzen.
- `tap-targets`: Aufnahme-Navigation der Großansicht ergänzen, Gruppennavigation umbenennen.

**3. Keine neue „Bekannte Lücke“:** Die Wahrnehmungsaussagen fallen unter das bestehende „gestalterische Urteil“ in „Was bewusst nicht getestet wird“.

## Entscheidungen

- **Ein Stapel je Gruppe** (Produktentscheidung Daniel, 2026-09-26): Alle Ausschuss-Aufnahmen einer
  Duplikatgruppe fallen in der Übersicht zu einem Stapel zusammen, nicht ein Stapel je Aufnahme.
- **Gruppe abschließen** schreibt `discard` nur auf offene Vorschläge der Gruppe (ADR 0125 Punkt 4);
  kein Festschreiben des angezeigten Werts aus dem Client.
- **Auszeichnung „beste je Messwert"** über den angezeigten, gerundeten Werten im Frontend;
  **Zeitspanne** serverseitig aus `taken_at`.
- **Rückweg** als Query-Parameter `?from=ausschuss` mit festem Ziel.
- **Stapel-Zahl** `group_size` (ganze Serie, deckt sich mit dem Kopf der Vergleichsansicht);
  Zusammenfassung aus `decision_counts` in den Wörtern der Einzelkachel.
- **Letzte Gruppe:** „Gruppe abschließen, zum Ausschuss" (mit `from`) bzw. „Gruppe abschließen"
  (ohne `from`, Ansicht bleibt stehen).
- **Seitenspalte der Großansicht** trägt Zustand und Wahlzeile.
- **A3-Wortlaut** an den angezeigten Zustand gebunden (UX-Fassung, von Security bestätigt).
- architect, ux-ui-designer, test-engineer und security-engineer wurden konsultiert; keine
  Konsultation übersprungen.

## Offene Fragen

keine

## Out of Scope

- Die Duplikat-Erkennung selbst (welche Aufnahmen eine Gruppe bilden, welche das System wählt).
- Eine Rücknahme nach „Noch offen".
- Ein dauerhafter Gruppenzustand „erledigt" im Datenmodell.
- Änderungen an der Wirkung von Entscheidungen auf den weiterlaufenden Bestand.
- Änderungen an der Ausschuss-Detailansicht über den Wegfall des eingebetteten Gruppenbereichs hinaus.
- Deckung der Stapel-Reihenfolge der Übersicht mit der Gruppenreihenfolge der Vergleichsansicht.
- Die Zuordnung der Vergleichsroute in der Projekt-Navigation; die Penpot-Seite „Duplikate
  vergleichen" selbst; `reason = low_quality` am Deep-Link eines Gewinners mit `keep`-Zeile; der
  abgeschnittene Fokusring der Einzelkachel (`li.overflow-hidden`).
