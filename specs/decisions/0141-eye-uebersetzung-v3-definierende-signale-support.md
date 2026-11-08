# 0141 - Eye-Übersetzung v3: definierende Signale, Support-Bedingung, Richtungszähler im Export

**Status:** Accepted
**Datum:** 2026-11-08
**Bezug:** Issue [#622](https://github.com/TheRealKoller/photosort/issues/622), Spec
[`0622`](../features/0622-eye-uebersetzung-v3.md), ADR
[`0140`](./0140-eye-uebersetzung-v2-lauf-fassung-tiererkennung-fassung-je-ergebnis.md) (Punkt 1
und 6 teilweise abgelöst), ADR
[`0139`](./0139-pruefung-von-klassifizierungsverfahren-in-der-app.md) (Prüfung und Export), ADR
[`0091`](./0091-motive-mit-staerke-statt-hauptkategorie.md) (eine Präsenzgrenze für alle Motive)

**Umfang:** über dem Richtwert, weil die fünf geänderten Motivtabellen und die Messregel je
einzeln nachprüfbar sein müssen.

## Kontext

Prüfung 1 (373 Fotos, Eye `eye-4.2.3/v2` gegen Cloud `ministral-3b-2512`) zeigt Eye in 24 von 30
beurteilten Motivfällen schlechter. Eye vergibt vor allem zu viele Motive: Die Max-Regel über
Tag-Listen macht Gegenstände und Umgebungssignale zu Motivbelegen — ein parkendes Rad belegt
Aktivität, ein Auto oder Gebäude „Stadt und Straße“, Himmel jede Landschaft, ein Zimmerinventar ein
Detail, `animal`/`pet`/`wildlife` auch Spielzeug und Abbildungen. v2 ist unveränderlich und bleibt
aufrufbar. Die rohe SDK-Antwort wird nicht gespeichert, nur abgeleitete Stärken; eine neue Fassung
braucht deshalb einen neuen Eye-Lauf bzw. eine neue Prüfung. `deviating` ist richtungslos, damit
lässt sich „v3 vergibt weniger überzählige Motive als v2“ je Motiv nicht beziffern.

## Entscheidung

### 1. v3 als dritte Fassung; v1 und v2 unverändert

`eye-4.2.3/v3` ist ein weiterer Eintrag in `MAPPINGS`. `MAPPING_VERSION` ist die Lauf-Fassung (v3);
`MAPPING_VERSION_V2` hält den bisherigen Laufwert, wie `MAPPING_VERSION_V1` den ersten.
`MAPPING_V1` und `MAPPING_V2` behalten Tabelle, Ausschluss, Feinlabel-Filter, Albumbänder und
Schwelle wörtlich; v3 erbt die unveränderten Tabellen als dieselben Objekte. `analyze(payload,
version)` hat weiterhin keinen Default und wirft bei unbekannter Fassung `EyeMappingError`.
Bestehende Ergebniszeilen behalten ihre Fassung und werden nicht neu berechnet.

### 2. Nur definierende Signale je Motiv

Ein Tag belegt ein Motiv nur, wenn er das Motiv selbst benennt, nicht einen Gegenstand, eine
Örtlichkeit oder eine Umgebungsbedingung, die ohne das Motiv vorkommt. Gegenstände sind nie Beleg;
Örtlichkeiten nur dort, wo eine Support-Bedingung (Punkt 3) die zweite Hälfte liefert.
Oberbegriffe, die keine Art benennen, entfallen bei `tiere` zugunsten benannter Arten und Klassen.
Jeder Tabellentag muss im gepinnten SDK-Vokabular stehen (`eye/test/tags.test.js`).

| Motiv | entfällt | kommt hinzu |
|---|---|---|
| `aktivitaet` | `bicycle`, `football`, `soccer`, `skateboard` | Support-Bedingung statt weiterer Tags |
| `stadt_strasse` | `car`, `bus`, `building` | `cityscape`, `metropolis`, `metropolitan_area`, `urban_area`, `neighbourhood`, `street_light`, `traffic_sign`, `pedestrian`, `skyline` |
| `landschaft` | `sky`, `cloud`, `sunset`, `water` | `mountain_range`, `hill`, `grassland`, `landscape`, `ocean`, `shore` |
| `detail_stimmung` | `furniture` | `blossom` |
| `tiere` | `animal`, `pet`, `wildlife` | benannte Arten und Klassen des Vokabulars |

`menschen`, `bauwerk_sehenswuerdigkeit` und `essen_trinken` bleiben wertgleich mit v2. Eyes
Tiererkennung `pets` bleibt als Motivsignal für `tiere` erhalten; sie meldet eine tierförmige
Region, keinen Oberbegriff.

### 3. `motif_support`: eine generische Support-Bedingung

`EyeMapping` erhält `motif_support: Mapping[str, tuple[str, ...]]`. v1 und v2 führen eine leere
Abbildung, v3 genau `{"aktivitaet": (...)}` mit den Personensignalen des Vokabulars. **Was gilt:**
Hat ein Motiv einen Eintrag, zählt es nur, wenn mindestens einer seiner Support-Tags die Schwelle
`tag_confidence` erreicht; sonst ist seine Stärke `0.0`. Die Stärke selbst bleibt das Maximum der
Motivsignale (Tags und `pets`) — der Support hebt sie nicht an. Die Schwelle ist `tag_confidence`
(inklusiv, wie bei den Feinlabels); eine eigene Support-Schwelle gibt es nicht. Ein leerer
Support-Eintrag ist unzulässig, weil er das Motiv dauerhaft auf `0.0` schließen würde; ein Test
hält das fest. **Bei Verletzung:** ein Tippfehler im Support-Tag schließt die Bedingung still und
das Motiv fällt ohne Fehlermeldung aus jedem Ergebnis.

Der Support ist eine Datenregel der Fassung, kein Sonderfall im Code. Eine Schwelle je Motiv wäre
eine zweite Auswahlgrenze neben `selection.py::motif_is_present` (ADR 0091 Punkt 8) und behebt die
Ursache nicht — ein parkendes Rad mit 0.9 überschreitet jede sinnvolle Schwelle; eine zweite
Tag-Klasse addiert Belege, statt zu gaten, und ließe ein Porträt weiter als Aktivität gelten.

Die Support-Tag-Werte laufen durch dieselbe Funktion wie jede andere Fremdkonfidenz
(`_confidence`): fehlend, nicht numerisch, `bool`, NaN oder unendlich ergibt 0 und schließt die
Bedingung, ohne den Lauf abzubrechen. Fehlende `tags` ergeben für jedes Motiv `0.0`.

### 4. `motif_strengths` bleibt eine reine Regel

Die Präsenzentscheidung bleibt ausschließlich `selection.py::motif_is_present` mit einer Grenze
für alle Motive; `MOTIF_PRESENT` bleibt ihre Beschreibung. Die Support-Bedingung ist Teil der
Frage „welche Signale belegen dieses Motiv“, nicht der Frage „ab wann gilt es als vorhanden“.
`motif_strengths` bleibt DB- und sessionfrei, deterministisch und ohne zweite Auswahlregel.
`EYE_PURPOSE_MAPPING` veröffentlicht die Support-Abbildung und ihre Schwelle als Beschreibung der
Lauf-Fassung.

### 5. Pins sind die Vereinigung aller Motiv- und Support-Tags

`eye/src/pins.json::mappingTags` umfasst die Vereinigung der Motiv-Tags **und** der Support-Tags
aller Fassungen. **Bei Verletzung:** ein Pin-Wechsel, der einen Support-Tag umbenennt, bliebe
unbemerkt und schlösse die Bedingung still.

### 6. Richtungszähler im Prüfexport

Die Motiv-Aufschlüsselung des Exports erhält je Merkmal die Richtung der Abweichung:
`a_only` (nur Seite A hält das Motiv für vorhanden) und `b_only` (nur Seite B), zusätzlich zu
`compared`/`matching`/`deviating`. **Was gilt:** Für Merkmalszählungen gilt `a_only + b_only ==
deviating`; `PurposeCounts` und `counts_by_purpose` bleiben unverändert, die Übersicht
(`ReviewPurposeCountsOut`) führt die Richtung nicht. Der Export baut die Zählungen wie bisher aus
den **gespeicherten** Ergebnissen, nicht aus den vorgelegten Fällen; damit wird auch der Export
einer alten Prüfung nachträglich richtungsscharf, ohne Cloud-Aufruf. Additiv, kein Schemawechsel,
keine Migration, kein Frontend-Bezug.

Ein eigener `MotifCounts`-Typ hält die Invariante `a_only + b_only == deviating` und lässt
`PurposeCounts` als Form von `counts_by_purpose` unangetastet.

### 7. Kein Schemawechsel, keine Betriebsänderung

`photo_eye_results.mapping_version` bleibt ein String ohne Enum und trägt v3; es gibt keine
Migration und kein neues Feld. Dokument-Ausschluss (Menge von v2), Albumstufe, Feinlabels,
`tag_confidence`, Cloud-Ergebnisse, Album-Entwurf, Albumtauglichkeit und die
Cloud-Kandidatenauswahl bleiben unverändert. Der Sidecar wird nicht umgebaut; Eye verursacht
keinen zusätzlichen Datenabfluss.

## Konsequenzen

- Ein durch den Support ausgeschlossenes Motiv steht als `0.0` in der Ergebnistabelle und ist von
  „nicht erkannt“ nicht unterscheidbar. Das ist die gewollte Aussage: Eye vergibt das Motiv nicht.
- v2 bleibt vollständig aufrufbar; eine Prüfung kann v2 und v3 auf derselben Sidecar-Antwort
  vergleichen, ohne einen zweiten Dienstaufruf.
- Die Übervergabe wird je Motiv belegbar: Der neu exportierte Bestand von Prüfung 1 (v2 gegen
  Cloud) und die Bestätigungsprüfung (v3 gegen Cloud) nennen für dasselbe Projekt je Motiv
  `a_only`/`b_only`; ein kostenfreier Lauf v2 gegen v3 zeigt die Gesamtrichtung, trennt aber nicht
  Über- von Untervergabe.
- Bleibt die Tierübervergabe trotz entfernter Oberbegriffe bestehen, ist die Tiererkennung
  `pets` als Ursache zu prüfen; sie zu ändern ist eine weitere Fassung, kein stiller Eingriff.
- Jede künftige Fassung ergänzt `MAPPINGS` und die Pin-Vereinigung; keine bestehende Tabelle wird
  nachträglich verändert.
