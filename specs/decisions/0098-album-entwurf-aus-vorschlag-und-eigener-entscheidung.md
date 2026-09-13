# 0098 - Album-Entwurf je Nutzer: abgeleitet aus Vorschlag und eigener Entscheidung, Favorit daneben

**Status:** Accepted
**Datum:** 2026-09-13
**Bezug:** Spec [`features/0430-album-entwurf-je-nutzer.md`](../features/0430-album-entwurf-je-nutzer.md), ADR
[`0097`](./0097-auswahl-mit-richtwert-kontingente-je-event-und-motivgefuehrte-vergabe.md) (der
Vorschlag, auf dem der Entwurf aufsetzt), ADR
[`0071`](./0071-kuratierung-stabile-auswahl-ohne-backfill-und-einsehbarer-vorrat.md) (kein
Nachrücken, einsehbarer Vorrat), ADR [`0091`](./0091-motive-mit-staerke-statt-hauptkategorie.md)
(Motivstärken ohne Rangfolge), ADR
[`0095`](./0095-albumtauglichkeit-vom-modell-qualitaet-getrennt-vom-inhalt.md) (Qualitätswert und
Begründung)

**Löst ab (teilweise):**

- [`0071`](./0071-kuratierung-stabile-auswahl-ohne-backfill-und-einsehbarer-vorrat.md),
  Entscheidung 1 — ausschließlich der Satz „welche Fotos die Ansicht zeigt, hängt danach
  ausschließlich vom Lauf ab". Der Entwurf hängt zusätzlich von den eigenen Entscheidungen des
  anfragenden Nutzers ab. **Unverändert gültig bleibt der Kern derselben Entscheidung:** es rückt
  nichts nach, kein Backfill, keine Fensterfunktion. Ebenso Entscheidung 5 — der Vorrats-Endpunkt
  `GET /projects/{id}/curation-candidates` wird durch den Alternativen-Endpunkt aus Punkt 5 unten
  ersetzt; die dort getroffenen Festlegungen (eigener Lese-Endpunkt, Seitenweise mit `total` als
  Restmenge, Projektbindung ausschließlich über die Lauf-Id) gelten wortgleich weiter.
- [`0097`](./0097-auswahl-mit-richtwert-kontingente-je-event-und-motivgefuehrte-vergabe.md),
  Punkt 6 — ausschließlich der Query-Parameter `selection: bool` und seine Zusage, der Modus
  liefere genau die Fotos mit `selection_position IS NOT NULL`. Punkte 1-5 und 7 (Richtwert,
  persistierter Vorschlag, beide Verfahrensstufen, Determinismus, die drei Auslöser) gelten
  unverändert; `selection_position` bleibt lauf-global und ohne Nutzerbezug.

**Umfang:** über dem Richtwert von rund 100 Zeilen, weil die Entscheidung zwei Dinge zugleich
festlegt, die einzeln prüfbar bleiben müssen: die Herkunft des Entwurfs und die Neufassung der
Bewertung samt Datenmodell-Änderung.

## Kontext

Nach ADR 0097 liegt je Lauf genau ein Auswahlvorschlag vor. Er ist eine Aussage des Verfahrens und
niemandes Album: Es gibt keinen Ort, an dem ein Nutzer ihn zu seiner Auswahl macht, und keinen
Zustand, in dem eine Korrektur daran einen zweiten Lauf überlebt. Zugleich trägt die bestehende
Bewertung (`ratings.status`) drei sich ausschließende Werte, deren mittlerer — `album_worthy` —
inhaltlich genau die Aussage ist, die der Entwurf braucht.

## Entscheidung

### 1. Der Entwurf wird abgeleitet, nicht gespeichert

Der Entwurf eines Nutzers `u` für ein Projekt ist zur Lesezeit

    Entwurf(u) = Vorschlag(letzter erfolgreicher Lauf) ∪ Aufgenommen(u) \ Gestrichen(u)

Es entsteht **keine** Entwurfstabelle, keine Entwurfszeile und kein Entwurfsfeld. Daraus folgt ohne
eine Zeile durchsetzenden Code: Jeder Nutzer hat je Projekt genau einen Entwurf, es gibt keine
benannten Fassungen, und der Entwurf überdauert jede Sitzung, weil seine beiden Bestandteile es tun.

**„Diesen Platz habe ich nie angefasst" ist die ABWESENHEIT einer eigenen Albumentscheidung für
dieses Foto** — dasselbe Muster wie „unbewertet" und „nicht korrigiert". Deshalb befüllt ein neuer
Lauf genau die unangefassten Plätze neu und lässt jede getroffene Entscheidung stehen, ohne dass
irgendwo ein Abgleich zwischen altem und neuem Vorschlag stattfände. Ein Platz ist kein Objekt: Der
Entwurf eines Events ist eine Menge, keine Liste fester Fächer.

### 2. Aufnehmen und Streichen sind die bestehende Bewertung — Favorit zieht daneben

`ratings.status` trägt künftig die **Albumentscheidung** und nichts sonst: `album_worthy` heißt
„gehört ins Album", `rejected` heißt „gehört nicht ins Album". Beide sind ausdrücklich **keine
Aussage über die Bildgüte** — ein bewusst aufgenommener schlechter Schnappschuss und ein
gestrichenes gutes Bild sind widerspruchsfreie, gewollte Zustände. Die Bildgüte steht weiterhin
allein in `PhotoAlbumSuitability` (ADR 0095).

`favorite` verlässt dafür den Wertevorrat von `status` und wird eine eigene, unabhängige Spalte
`ratings.favorite: bool`. `status` wird nullable; `NULL` heißt „keine Albumentscheidung". Eine
Zeile, die weder eine Albumentscheidung noch das Favoriten-Kennzeichen trägt, existiert nicht — sie
wird gelöscht, wie heute schon „unbewertet" das Fehlen der Zeile ist.

**Warum nicht bei drei sich ausschließenden Werten bleiben:** Dann setzte jedes Markieren als
Favorit still eine bestehende Aufnahme- oder Streich-Entscheidung zurück. Kein Fehler, keine
Meldung, keine Anzeige — die Entscheidung wäre schlicht fort. Die Alternative „Favorit gilt als
aufgenommen" vermeidet den Verlust, hebt aber die Zusage der Story auf, dass die Auszeichnung auf
den Entwurf nicht wirkt.

Die Migration ist strukturverändernd und konvertiert die Bestandszeilen (`status='favorite'` →
`favorite=true, status=NULL`), damit kein Lesepfad auf einen Wert außerhalb des neuen Vorrats
trifft. Der Rückwärtsweg stellt die Struktur wieder her, nie die Daten.

### 3. Der Lesepfad liefert Vorschlag und Aufgenommenes — und filtert nichts weg

Der Entwurfs-Modus von `GET /projects/{id}/photos` (Parameter `draft: bool`, er ersetzt
`selection`) liefert die Vereinigung aus dem Vorschlag des Laufs und den vom **anfragenden** Nutzer
aufgenommenen Fotos, sortiert nach `(events.position, Platz im Event)`.

**Ein gestrichenes Foto wird nicht herausgefiltert.** ADR 0071 Entscheidung 3 („verworfen ist ein
Anzeigezustand, kein Filterkriterium") gilt unverändert: Ein gestrichenes Foto des Vorschlags bleibt
in der Antwort, trägt seinen Zustand in `PhotoOut.ratings[]` und steht an seiner Stelle, statt beim
Streichen unter dem Finger zu verschwinden und die folgenden Kacheln nachrücken zu lassen. Die
Antwortmenge entsteht damit ausschließlich additiv; kein Ausschluss bildet sie.

`RankingOut` bekommt dafür **ein** neues Feld: `proposed: bool` (`selection_position IS NOT NULL`).
Es ist lauf-global, ohne Nutzerbezug, und wird auf allen Lesepfaden geliefert, nicht nur im
Entwurfs-Modus — ein je Query-Modus verschiedenes `PhotoOut` wäre die zweite, driftende Abbildung.
Damit ist „vom Nutzer aufgenommen, vom neuen Lauf aber nicht vorgeschlagen" am Foto erkennbar, ohne
dass die Oberfläche die Auswahlregel nachbildet. Die eigene Entscheidung liest sie wie überall aus
`ratings[]`.

Die Antwort ist damit **nutzerabhängig geworden**, und zwar nicht mehr nur über
`PhotoOut.suggestion`: Die Auflage am Antwortaufbau (ein Zwischenspeicher, ein `ETag` oder ein
`Cache-Control` über `no-store` hinaus nur mit dem Nutzer im Schlüssel) trägt ab hier eine zweite,
unabhängige Ursache. `selection_position` selbst bleibt lauf-global (ADR 0097 Punkt 2) —
nutzerabhängig ist die **Menge der Antwort**, nie die Spalte.

### 4. Ein aufgenommenes Foto ohne Rangzeile wird über die Zeit eingeordnet

Sortiert ein neuer Lauf ein aufgenommenes Foto aus dem Kandidatenbestand aus, hat es keine
`PhotoRanking`-Zeile mehr und damit kein Event. Es bleibt trotzdem im Entwurf und wird dem Event
zugeordnet, dessen Zeitspanne seine (korrigierte) Aufnahmezeit enthält; liegt es in keiner, dem
zeitlich nächstgelegenen Event, bei gleichem Abstand dem früheren. Die Zuordnung ist eine reine,
deterministische Funktion in `events.py` und wird nirgends persistiert.

Verworfen: das Foto ohne Event in einer Restgruppe am Ende zeigen. Der Entwurf ist chronologisch;
eine Gruppe außerhalb der Chronologie wäre ein zweiter Ordnungsbegriff für denselben Zweck.

### 5. Alternativen sind ein eigener Lese-Endpunkt und ersetzen den Vorrats-Endpunkt

`GET /projects/{id}/draft-alternatives?event_id=…&photo_id=…&limit=…&offset=…` liefert die Fotos
**eines** Events des letzten erfolgreichen Laufs, die nicht zum Entwurf des anfragenden Nutzers
gehören — einschließlich der von ihm gestrichenen, denn genau daraus folgt, dass ein Austausch
umkehrbar ist. `photo_id` ist der Bezugspunkt des Austauschs und steuert allein die Sortierung:

1. Bilder, die mit dem Bezugsbild mindestens ein Motiv teilen (wirksame Stärke ≥
   `selection.py::MOTIF_PRESENCE_THRESHOLD`, für alle Motive dieselbe Grenze), nach Qualität
   absteigend;
2. danach die übrigen Bilder des Events, ebenso nach Qualität absteigend; Bilder ohne
   Qualitätswert zuletzt. Gleichstand bricht über die kleinere `photo_id`.

Zeitliche Nähe ist **kein** Sortierkriterium, und es wird nie eine Motivstärke mit einer anderen
verglichen — die Eindämmung aus ADR 0091 Punkt 1 und 8 bleibt gewahrt, weil ausschließlich gegen
die eine Konstante aus `selection.py` geprüft wird und keine Anzeigebandgrenze gelesen wird.

Der Endpunkt ersetzt `GET /projects/{id}/curation-candidates` übernehmend: Beide beantworten „zeig
mir den weiteren Bestand dieses Events"; zwei Wege dorthin wären zwei Reihenfolgen derselben Menge.
Der volle Bestand bleibt damit einsehbar.

### 6. Der Entwurf bewegt sich nicht unter der Hand

Eine Entscheidung (aufnehmen, streichen, austauschen) **darf kein Neuladen der Entwurfsliste
auslösen.** Sie schreibt eine Bewertungszeile und schreibt das betroffene Foto im bereits geladenen
Zustand fort. Ein Neuladen nach jedem Handgriff ordnete die Liste neu, ließe gerade gestrichene
Bilder verschwinden und nähme der Handlung ihre Rückmeldung.

### 7. Es gibt danach genau eine Ansicht

`CuratePage.tsx` und die Route `/projects/:id/curate` entfallen; an ihre Stelle tritt eine neue
Seite unter `/projects/:id/album`. Kein Redirect: Ein zweiter Weg auf die eine verbleibende Ansicht
wäre ein zweiter Ort für eine Sache, von der die Story genau einen verlangt.

## Konsequenzen

- **Die Neufassung der Bewertung wirkt über den Entwurf hinaus.** Bewertungsleiste, Tastenbelegung,
  Rasterfilter, Statistikzahlen, `demo_state.py` und der Prüfstack führen `favorite` heute als einen
  von drei Werten und ziehen mit. Diese Arbeit ist der erste von drei Pull Requests der Story und
  für sich abgeschlossen.
- **Bestandsdaten werden nicht überführt** (Vorgabe der Story: Der Bestand wird zurückgesetzt und
  neu berechnet). Die Migration konvertiert trotzdem, damit ein nicht zurückgesetzter Bestand keinen
  Lesepfad auf einen unbekannten Enum-Wert laufen lässt.
- **`docs/architecture.md`** beschreibt `Rating`, den Kuratierungszweig von
  `GET /projects/{id}/photos`, den Vorrats-Endpunkt und die Route `/curate` und wird im jeweils
  betroffenen Pull Request nachgezogen. `docs/setup.md` bleibt unberührt — keine neue
  Umgebungsvariable, kein neuer Setup-Schritt.
- **Zwei e2e-Spezifikationen** (`no-horizontal-scroll`, `popover-position`) rufen `/curate` auf und
  ziehen auf die neue Route nach.
- **Bestehende Tests kodieren die alte Bedeutung** (`test_api_ratings.py`, `test_api_photos.py`,
  `CuratePage.test.tsx`, `RatingButtons`/`RatingBadge`/`PhotoDetailPage`). Sie werden umgeschrieben,
  nicht gelöscht.
- **Bewusst offen gelassen:** Der Vergleich der beiden Nutzer-Entwürfe (Story 7) und die Auswertung
  der Korrekturen als Feedback (Story 8). Beide finden in den Bewertungszeilen vor, was sie
  brauchen; keine von beiden braucht dafür eine Entwurfstabelle.
