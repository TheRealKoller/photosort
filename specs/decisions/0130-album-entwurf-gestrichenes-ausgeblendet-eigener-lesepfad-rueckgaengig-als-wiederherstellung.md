# 0130 - Album-Entwurf: Gestrichenes ausgeblendet, eigener Lesepfad mit Eventliste, Rückgängig als Wiederherstellung

**Status:** Accepted
**Datum:** 2026-10-02
**Bezug:** [GitHub-Issue #558](https://github.com/TheRealKoller/photosort/issues/558), Spec 0558.
Löst ADR [`0098`](./0098-album-entwurf-aus-vorschlag-und-eigener-entscheidung.md) in Punkt 3
(Ort des Lesepfads, Anzeige gestrichener Fotos) und ADR
[`0071`](./0071-kuratierung-stabile-auswahl-ohne-backfill-und-einsehbarer-vorrat.md) in
Entscheidung 3 (Anzeigeteil) teilweise ab. Ergänzt ADR 0098 Punkt 5 und ADR
[`0100`](./0100-nacharbeit-als-ereignis-log-gewichte-persistiert-und-versioniert.md) Punkt 3, ohne
sie zu ändern.

## Kontext

Der Entwurf folgt dem Arbeitsmodell „nur abweichen, wo nötig". Gestrichenes soll sofort aus dem
Entwurf verschwinden, je Event einblendbar und rücknehmbar sein; jedes Event soll ein Foto
aufnehmen können, auch eines ohne Foto im Entwurf; ein Tausch soll als ein Handgriff rückgängig zu
machen sein. Der heutige Lesepfad kennt nur Events, in denen ein Foto des Entwurfs steht, und eine
Streichung eines nicht vorgeschlagenen Fotos ist nach dem Neuladen nicht mehr in der Antwort.

## Entscheidung

### 1. Die Antwort führt Gestrichenes weiter, die Ansicht blendet es aus

Ein gestrichenes Foto bleibt in der Antwort (ADR 0071 Entscheidung 3, serverseitig unverändert),
steht in der Ansicht aber nicht mehr an seiner Stelle. Es erscheint ausschließlich in der
Gestrichen-Zeile seines Events. Es rückt nichts nach.

Die Antwortmenge wird dafür vollständig:

    Antwort(u) = Vorschlag ∪ Aufgenommen(u) ∪ (Gestrichen(u) ∩ Kandidaten des Laufs)

`Kandidaten des Laufs` sind die Fotos mit Rangzeile im letzten erfolgreichen Lauf. Im
Ausschuss-Schritt aussortierte Fotos tragen keine Rangzeile und erscheinen damit nie als
gestrichen. Innerhalb der Antwort gilt `im Album ⇔ eigener status ≠ rejected` ausnahmslos.

### 2. Der Entwurf hat einen eigenen Lesepfad mit der Eventliste des Laufs

`GET /projects/{id}/album-draft` liefert `AlbumDraftOut { events, items }`: alle Events des
letzten erfolgreichen Laufs nach `position` und die Antwort aus Punkt 1 in der bisherigen
Reihenfolge. Beide stammen aus **einer** Anfrage und damit aus demselben Lauf. Zwei getrennte
Abfragen könnten zwischen zwei Läufen liegen; ein Foto verwiese dann auf ein Event, das die Liste
nicht kennt.

Der Entwurfsmodus von `GET /projects/{id}/photos` entfällt. `draft` bleibt als `None`-typisierter,
schemaloser Parameter stehen und endet mit `422`, wie `selection`.

### 3. Der Cache des Entwurfs ist jederzeit die Antwort, die der Server jetzt gäbe

Kein Handgriff lädt die Entwurfsliste neu (ADR 0098 Punkt 6 gilt weiter). Jeder Schreibvorgang
setzt den vom Server zurückgemeldeten Zustand in die geladene Antwort ein. Ein Foto, das dadurch
die Antwortmenge aus Punkt 1 verlässt, wird entfernt; eines, das hineinkommt, wird mit dem
Sortierschlüssel des Servers eingefügt. Die Zugehörigkeit (`im Album` / `gestrichen` / `nicht
enthalten`) entscheidet genau eine reine Funktion im Frontend. Sie bildet das Prädikat von
`_draft_photo_ids` nach.

Bei Verletzung zeigt die Ansicht bis zum nächsten vollständigen Laden einen Entwurf, den der Server
so nicht liefert. Zahlen im Kopf und die Gestrichen-Zeilen springen dann beim nächsten Laden.

Damit der zurückgemeldete Zustand immer vom Server kommt, liefert `DELETE /photos/{id}/rating`
`200` mit `RatingWriteOut` statt `204`.

### 4. Rücknahme stellt her, Aufnahme entscheidet

- **Rückgängig** stellt den Zustand vor dem Handgriff wörtlich her: die vorherige Entscheidung
  oder deren Abwesenheit.
- **Wiederaufnehmen aus der Gestrichen-Zeile** nimmt die Streichung zurück. Für ein
  vorgeschlagenes Foto ist das die Abwesenheit einer Entscheidung (`DELETE`), sonst
  `album_worthy`.
- **Hinzufügen und Tausch** sind Aufnahmen und schreiben `album_worthy`, auch für ein
  vorgeschlagenes, gestrichenes Foto.

Der Unterschied wirkt über die Ansicht hinaus: Nur eine Aufnahme überlebt einen neuen Lauf, der
das Foto nicht mehr vorschlägt.

### 5. Rückgängig eines Tauschs ist eine atomare Wiederherstellung

`POST /projects/{id}/draft/exchange/undo` nimmt dieselben beiden Ids wie der Tausch und dazu die
beiden Vorzustände: für das aufgenommene Foto `rejected` oder `null`, für das ersetzte
`album_worthy` oder `null`. Andere Werte sind `422`. Er schreibt beide Zeilen in einer Transaktion
über `write_own_rating(record=False)`. Die Projektbindung läuft wie beim Tausch über
`_exchange_sides`.

Er gilt nur, solange der Tausch steht: Ist das aufgenommene Foto nicht mehr `album_worthy` oder das
ersetzte nicht mehr `rejected`, endet er mit `409` und schreibt nichts. Sonst überschriebe er eine
inzwischen getroffene Entscheidung.

Aufgezeichnet wird **ein** `exchanged`-Ereignis in der Gegenrichtung (ADR 0100 Punkt 3).

### 6. Hinzufügen nutzt den Alternativen-Endpunkt ohne Bezugsbild

`photo_id` an `GET /projects/{id}/draft-alternatives` wird optional. Ohne Bezugsbild entfällt die
Motivstufe; die Reihenfolge ist die zweite Stufe aus ADR 0098 Punkt 5 (Qualität absteigend, ohne
Qualitätswert zuletzt, Gleichstand über die kleinere Id). Menge und Projektbindung bleiben
unverändert.

## Konsequenzen

- Kein neues Feld am Datenmodell, keine Migration.
- Die Projektbindung und die Auflagen S2/S3/S14 des Tauschs gelten für den Rückgängig-Endpunkt
  wortgleich. Beide neuen Endpunkte tragen die Auth-Dependency ausgeschrieben und brauchen je einen
  eigenen `401`-Nachweis (`api/photos.py` hat kein Vollständigkeitsnetz).
- Die Antwortmenge des Entwurfs hängt weiter am anfragenden Nutzer. Die Auflage an
  Zwischenspeicher, `ETag` und `Cache-Control` gilt für `GET /projects/{id}/album-draft`.
- Das Design-System-Muster „Verworfene Kachel bleibt stehen" gilt für den Album-Entwurf nicht mehr.
