# 0639 - Automatisch entschiedene Duplikatgruppen

**Status:** Accepted
**Erstellt:** 2026-11-12
**Bezug:** Issue [#639](https://github.com/TheRealKoller/photosort/issues/639); ADR
[`0146`](../decisions/0146-automatisch-entschiedene-duplikatgruppen.md); Voraussetzung Spec
[`0637`](./0637-duplikatgruppen-nur-echte-duplikate.md)

Umfang über dem Richtwert: Die Akzeptanzkriterien tragen die Zusagen dieses Features vollständig —
Laufbindung, Wettlauf, Merker-Invariante, Filter und Demo hängen an je eigenen Bedingungen, und eine
Zusammenfassung wäre eine zweite, ungeprüfte Fassung derselben Zusage.

## Ziel

Der Ausschuss-Schritt fragt jede Duplikatgruppe einzeln ab, auch dort, wo es nichts zu entscheiden
gibt. In einem großen Projekt sind das Hunderte Gruppen.

Gruppen aus **praktisch identischen** Aufnahmen entscheidet der Lauf deshalb selbst: eine Aufnahme
bleibt, alle übrigen gelten als Ausschuss. Solche Gruppen erscheinen nicht mehr unter den offenen
Fällen, bleiben aber als automatisch entschieden erkennbar, in der Übersicht erreichbar und
jederzeit umkehrbar. Auf OpenCloud bleibt alles unverändert.

**Nicht Teil dieser Story:** eine teilweise automatische Gruppe und eine automatische Entscheidung
in Gruppen bloß ähnlicher Aufnahmen; sie bleibt der Entscheidung des Nutzers vorbehalten.

## User Story

Als Nutzer, der den Ausschuss eines großen Projekts durchgeht, möchte ich, dass praktisch identische
Aufnahmen ohne mein Zutun entschieden werden, damit ich nur die Fälle prüfen muss, in denen es etwas
zu entscheiden gibt.

## Akzeptanzkriterien

- [ ] **Nur praktisch identische Aufnahmen:** Automatisch entschieden wird ausschließlich ein Stern
  aus Durchgang 1 (Kanten „praktisch identisch“ im Sinne von #637, mindestens zwei Aufnahmen). Jede
  Verliererin hat eine **direkte identische Kante zur behaltenen Aufnahme**; paarweise Identität
  unter den Verliererinnen wird nicht verlangt. Bloß ähnliche Gruppen (Serienbild, verschobener
  Ausschnitt) und Ketten ohne direkte Kante zur behaltenen bleiben offen. Eine teilweise
  automatische Gruppe entsteht nie.
- [ ] **Ergebnis:** Genau eine Aufnahme der Gruppe bleibt erhalten, alle übrigen tragen
  `suggested_status = REJECTED` und `duplicate_of` auf die behaltene; es entsteht **keine**
  `photo_duplicate_decisions`-Zeile und keine wird gelöscht. Auf OpenCloud findet keine
  Schreiboperation statt (aufzeichnender Fake-Client: leere Mutationsmenge).
- [ ] **Gewinnerregel, fünf Stufen:** (1) bekannte Auflösung vor unbekannter, (2) höhere
  `pixel_count`, (3) verlässliche Aufnahmezeit vor einer aus dem Dateidatum abgeleiteten —
  unabhängig vom Datum, (4) ältere verlässliche Zeit, (5) bei gleichem Aufnahmezeitpunkt die
  kleinere `photo_id`. Ordner und Dateiname sind nie Eingabe.
- [ ] **Gewinnerregel gilt nur für praktisch identische Gruppen:** In einer bloß ähnlichen Gruppe
  bleibt der Vorschlag die schärfste Aufnahme (`−sharpness, photo_id`) — Produktentscheidung Daniel,
  2026-11-12; die Auflösungsregel ersetzt sie dort nicht.
- [ ] **Verkleinerte Kopie:** In einer praktisch identischen Gruppe verdrängt sie nie die höher
  aufgelöste Aufnahme, auch wenn sie schärfer misst. In einer bloß ähnlichen Gruppe entscheidet
  weiterhin die Schärfe.
- [ ] **Schärfeschwelle:** Automatisch entschieden wird nur, wenn der Gewinner `sharpness ≥
  SHARPNESS_REJECT_THRESHOLD` hat; exakt auf der Konstante ja, ein Schritt darunter nein. Steht die
  zu behaltende Aufnahme ohnehin im Ausschuss (zu geringe Schärfe), wird nichts automatisch
  entschieden.
- [ ] **Alle Auflösungen bekannt:** Ist `pixel_count` irgendeines Gruppenmitglieds unbekannt, wird
  die Gruppe nicht automatisch entschieden (kein Schätzwert, keine Teilmenge). Die Gruppierung
  selbst bleibt bestehen, das unbekannte Foto sortiert in Durchgang 1 zuletzt.
- [ ] **Keine offenen Fälle:** Automatisch entschiedene Aufnahmen fehlen in
  `AusschussOut.open_count`, im Filter `suggested`, in `PhotoOut.suggestion` und in der Auswahl von
  Projekt- und Gruppenabschluss; sie werden in der Zahl der offenen Fälle nicht mitgezählt. Sie
  bleiben Einträge des Ausschuss-Bestands (`has_ausschuss_entry` unverändert, `items`/`total`
  enthalten sie).
- [ ] **Gate-Autoset:** Bleibt nach Abzug der automatisch entschiedenen Aufnahmen keine offene
  Ablehnung, setzt derselbe SUCCESS-Commit `gate_confirmed_at`; `suggestions_found` zählt weiterhin
  **alle** Abgelehnten, auch die automatisch entschiedenen.
- [ ] **Erkennbar (Antwort):** `AusschussGroupEntryOut.auto_decided` und
  `AusschussPhotoEntryOut.auto_decided` sind gesetzt; `decision` bleibt `null`, `effective_decision`
  ist „Ausschuss“ für Verlierer und „behalten“ für die behaltene; `decision_counts` zählt
  unverändert die gespeicherten Zeilen.
- [ ] **Erkennbar (Oberfläche):** Der Stapel trägt das sichtbare Wort „Automatisch entschieden“ in
  der Zusammenfassungszeile und im `aria-label` (statt „N vorgeschlagen“); die Unterscheidung hängt
  an Wort und Zahl, nicht an Farbe. Je Aufnahme bleibt es bei genau „behalten“ und „Ausschuss“.
- [ ] **Zähler:** `auto_decided_group_count` zählt **Gruppen**, ist projektweit und unabhängig von
  `limit`, `offset` und Filter. Der Ausschuss-Schritt nennt „N Gruppen automatisch entschieden“ und
  führt als Link auf `?auto=1` zu ihnen; bei 0 entfällt der Zähler.
- [ ] **Filter:** `GET /projects/{id}/ausschuss?auto_decided=true` liefert ausschließlich Stapel
  automatisch entschiedener Gruppen; `items`/`total` zählen dann die gefilterten Einträge,
  `open_count` und `auto_decided_group_count` bleiben projektweit und gleich den Werten des
  ungefilterten Aufrufs. Der Zustand liegt nur in der Adresse und hat einen Rückweg zur
  vollständigen Übersicht.
- [ ] **Filter-Konflikt:** `auto_decided=true` zusammen mit `photo_id` ergibt `422` mit festem
  `detail`; `auto_decided=false` wirkt wie weggelassen.
- [ ] **Auffindbar:** Automatisch entschiedene Gruppen bleiben in der Ausschuss-Übersicht und in der
  Reihenfolge der Vergleichsansicht erreichbar; `position`/`total`/Nachbarn zählen alle Gruppen, ein
  Durchlauf der Kette besucht jede Gruppe genau einmal, `?photo=<id>` liefert den Eintrag auch
  außerhalb der geladenen Seite. Der Gruppenabschluss trifft sie nicht (kein offener Vorschlag).
- [ ] **Umkehrbar:** `keep` über den bestehenden Einzelweg; danach ist die Aufnahme erhalten, die
  Gruppe trägt keine Kennzeichnung mehr, `auto_decided_group_count` sinkt um 1, die übrigen
  Verlierer sind wieder offene Vorschläge. Wegen der Entscheidungszeile entscheidet kein späterer
  Lauf die Gruppe automatisch — auch nach einem weiteren erfolgreichen Lauf nicht. Es gibt keinen
  neuen Schreibweg.
- [ ] **Kein Übergreifen:** Trägt irgendein Mitglied der Gruppe eine Entscheidung des Nutzers, wird
  nichts automatisch entschieden; kein Lauf löscht oder ändert eine solche Zeile. Jeder
  Nutzer-Schreibweg (`_write`, Einzel- und Gruppenweg) räumt den Merker **aller** Mitglieder des
  Sterns in derselben Transaktion ab; andere Sterne und Projekte bleiben unberührt.
- [ ] **Gebunden an den Lauf:** Im Commit, der den `RUNNING`-Lauf anlegt, ist der Merker projektweit
  `false`. Gesetzt wird er ausschließlich im SUCCESS-Commit für die in genau diesem Lauf erneut
  erkannten Sterne. Nach einem fehlgeschlagenen, abgebrochenen oder am finalen Commit gescheiterten
  Lauf wirkt keine automatische Entscheidung mehr; die Aufnahmen werden nach dem Ergebnis dieses
  Laufs bewertet. Wiederholte erfolgreiche Läufe erzeugen denselben Zustand, weder doppelte noch
  widersprüchliche Einträge.
- [ ] **Merker-Invariante:** Der Merker steht nur an Verlierern (`duplicate_of IS NOT NULL`,
  `suggested_status = REJECTED`) eines Sterns aus Durchgang 1 ohne Entscheidungszeile; nie am
  Gewinner, nie an einem Foto ohne Vorschlag. Der Merker ist nicht Teil des Überlebens-Prädikats
  (Cloud-Kandidatenmenge unverändert).
- [ ] **Wettlauf Nutzerentscheidung während des Laufs:** Eine Entscheidung, die nach dem Einlesen
  der Gruppen und vor dem SUCCESS-Commit geschrieben wird, gewinnt: kein Merker an der Gruppe, die
  Zeile bleibt inhaltlich unverändert, kein `500`, keine automatische Entscheidung, die sie
  überschreibt.
- [ ] **Projektbindung:** Merker, Zähler, Filter und Reset wirken nur im laufenden bzw. angefragten
  Projekt; ein zweites Projekt mit eigenen offenen Vorschlägen bleibt unverändert.
- [ ] **Auflösung am Foto:** `Photo.pixel_count: int | None` und `Photo.pixel_count_probed: bool`
  (NOT NULL, `server_default false`) in Modell und Migration. Der volle Arbeitsposten schreibt den
  Wert unbedingt, auch zurück auf `None`; ein Nachhol-Posten liest nur die Maße aus dem bestehenden
  Range-Fenster, setzt den Merker auch ohne Fund und lässt Zeit, Ort und Kamera unberührt; er deckt
  alle `IMAGE_EXTENSIONS` inklusive HEIC und PNG ab; eine unveränderte Datei mit gesetztem Merker
  erzeugt keinen erneuten Lesevorgang.
- [ ] **Migration:** Revision `8c0f0296e1cd` mit Vorgänger `6299223059c8`, drei Spalten, kein
  Backfill, keine neue Tabelle; `downgrade` entfernt genau diese drei Spalten.
- [ ] **Demo bleibt vorführbar:** Das Projekt „Demo — Duplikate“ hat drei Gruppen;
  `_DEMO_DUPLICATE_GROUP_SIZES` bleibt `(7, 3)`, die automatisch entschiedene Gruppe läuft als
  eigene Konstante. Die beiden bestehenden Gruppen bleiben offen, einschließlich des unveränderlich
  abgelehnten Gewinners. Die automatische Gruppe hat genau einen Verlierer mit Merker, keine
  Entscheidungszeile, einen Gewinner über der Schärfeschwelle mit höherer Auflösung; alle Demo-Fotos
  tragen `pixel_count` und `pixel_count_probed=True`. `photo_count` ist die Summe über alle drei
  Gruppen, `suggestions_found` zählt alle Abgelehnten, die Zahl der Demo-Projekte bleibt gleich.

## Datenmodell-Bezug

`Photo.pixel_count` und `Photo.pixel_count_probed` (beide neu), `PhotoScore.auto_decided` (neu),
Revision `8c0f0296e1cd` mit Vorgänger `6299223059c8` — drei Spalten, kein Backfill, keine neue
Tabelle. Unverändert bleiben `photo_duplicate_decisions`, der Stern aus ADR 0145 und das
Überlebens-Prädikat aus ADR 0104. [`docs/architecture.md`](../docs/architecture.md) zieht im selben
PR nach; Grundlage ist ADR [`0146`](../decisions/0146-automatisch-entschiedene-duplikatgruppen.md).

## Architektur / Umsetzung

Grundlage ist ADR [`0146`](../decisions/0146-automatisch-entschiedene-duplikatgruppen.md); sie trägt
Begründung und Ausfallrichtung der fünf Punkte. Hier steht der Plan.

### Gewinnerregel: zwei Durchgänge in `scoring.py`

`assign_duplicate_groups` arbeitet in zwei Durchgängen. Durchgang 1 baut Sterne **nur über
identische Kanten**, sortiert nach `(pixel_count is None, −pixel_count, not taken_at_trusted,
taken_at, photo_id)` — höchste Auflösung, dann ältere verlässliche Aufnahmezeit, zuletzt kleinere
Id; Pfad und Dateiname sind nie Eingabe. Durchgang 2 ist der bisherige Stern über die verbliebenen
freien Fotos nach `(−sharpness, photo_id)`. Rückgabe: `DuplicateAssignment(duplicate_of,
identical_winners: frozenset[int])`; `PhotoFingerprint` bekommt `pixel_count`. Eine Gruppe aus
Durchgang 1 ist bauartbedingt vollständig identisch — eine teilweise automatische Gruppe entsteht
nicht. `duplicate_probe.py` zieht die Rückgabeform nach.

### Auflösung am Foto

- `Photo.pixel_count: int | None`, `Photo.pixel_count_probed: bool` (NOT NULL,
`server_default="false"` in Modell und Migration).
- Voller Arbeitsposten: `thumbnails.py::generate_variants` gibt `VariantResult(aspect_ratio,
pixel_count)` zurück, aus derselben Dekodierung; unbedingt geschrieben, auch zurück auf `None`.
- Nachhol-Posten für unveränderte Dateien ohne Merker: liest **nur** die Maße aus dem bestehenden
Range-Fenster (`opencloud/exif.py::extract_pixel_count`, neues `ScanWorkItem.dimensions_only`),
deckt alle `IMAGE_EXTENSIONS` ab, lässt Zeit, Ort und Kamera unberührt und setzt den Merker auch
ohne Fund. Ein bestehender Kamera-Nachhol-Posten liest die Maße aus demselben Fenster mit.

### Merker und Laufbindung

- `PhotoScore.auto_decided: bool` (NOT NULL, `server_default="false"`).
- `run_project_scoring` setzt ihn projektweit auf `false`, im selben Commit, der den
`RUNNING`-Lauf anlegt.
- Gesetzt wird er nur im SUCCESS-Commit, für die Verlierer eines Sterns aus Durchgang 1, wenn der
Gewinner `sharpness ≥ SHARPNESS_REJECT_THRESHOLD` hat, `pixel_count` aller Mitglieder bekannt ist
und kein Mitglied eine Entscheidungszeile trägt — als `NOT EXISTS` in derselben Anweisung.
- `api/duplicate_decisions.py::_write` setzt ihn für alle Mitglieder des Sterns in derselben
Transaktion auf `false`; die Mitgliedermenge kommt vom Endpunkt aus den projektgebundenen `links`,
und der Reset trägt `Photo.project_id` in derselben Anweisung.

### Offen, Überleben, Abschluss

- `has_open_suggestion()`/`_for()` erhalten das UND-Glied `auto_decided.is_(False)`, nur dort. Damit
verlassen die Aufnahmen `AusschussOut.open_count`, den `suggested`-Filter, `PhotoOut.suggestion`,
`confirm_ausschuss_gate` und `confirm_duplicate_group`, ohne Änderung an einer Aufrufstelle.
- `survives_ausschuss*()` und `has_ausschuss_entry()` bleiben wörtlich unverändert.
- Gate-Autoset, wenn `len(rejected_ids − auto_decided_ids) == 0`; `suggestions_found` zählt weiter
alle Abgelehnten.

### Lesepfade und Antwortfelder

`duplicates.py` bekommt `auto_decided_representatives(links, auto_ids)` und `auto_decided_for(photo,
links)`; `DuplicateLink` und `load_duplicate_links` bleiben ohne Entscheidungsauskunft. In
`api/photos.py`: `AusschussGroupEntryOut.auto_decided`, `AusschussPhotoEntryOut.auto_decided`,
`AusschussOut.auto_decided_group_count` (projektweit, unabhängig von `limit`/`offset`),
`DuplicateGroupOut.auto_decided`, dazu `GET /projects/{id}/ausschuss?auto_decided=true` als Filter
über denselben Bestand; mit `photo_id` zusammen `422`. `decision` bleibt die gespeicherte
Nutzerzeile, `effective_decision` und `decision_counts` behalten ihre Bedeutung,
`position`/`total`/Nachbarn zählen alle Gruppen.

### Frontend

`api/types.ts`, `api/ausschuss.ts` (Parameter `autoDecided`), `hooks/useAusschuss.ts`,
`components/DuplicateStackTile.tsx`, `pages/DuplicateComparePage.tsx`,
`pages/pipeline/AusschussStepPage.tsx` — Ausgestaltung im Abschnitt `## UI/UX`.

### Demo

`demo_state.py`: „Demo — Duplikate“ bekommt eine dritte, automatisch entschiedene Gruppe aus zwei
Aufnahmen (Gewinner höhere Auflösung, über der Schärfeschwelle, keine Entscheidungszeile);
`_DEMO_DUPLICATE_GROUP_SIZES` bleibt `(7, 3)`, die neue Gruppe ist eine eigene Konstante, alle
Demo-Fotos tragen `pixel_count` und `pixel_count_probed=True`.

### Reihenfolge

1. Migration und Modelle.
2. `thumbnails.py`/`exif.py` und der Scan-Pfad.
3. `scoring.py` (zwei Durchgänge) und `duplicate_probe.py`.
4. `worker.py::run_project_scoring`: Reset, Setzen, Gate-Autoset.
5. `duplicates.py`: offen-Prädikat, Repräsentanten-Menge.
6. `api/duplicate_decisions.py::_write`.
7. `api/photos.py`.
8. Frontend.
9. Demo-Bestand.
10. Doku: `docs/architecture.md`, Sicherheitskonzept, Statuszeilen in ADR 0145/0111, Skill
      `browse-app`.

## Teststrategie

Grundlage `0002-testkonzept.md`; keine neue Testebene, kein neues Werkzeug, kein neuer E2E-Fall (die
neue Fläche ist jsdom-fähig).

| Zusage | Ebene / Ort |
|---|---|
| Zwei Durchgänge, Sortierschlüssel in allen fünf Stufen, deterministisch und eingabereihenfolge-unabhängig; Rückgabe `DuplicateAssignment` | Unit `test_scoring.py` |
| Direkte identische Kante statt paarweiser Identität (Stern mit drei Verlierern, Kette A~B, B~C, A≁C bleibt ungruppiert); keine teilweise automatische Gruppe | Unit `test_scoring.py` |
| Unbekannte Auflösung sortiert zuletzt und blockiert die automatische Entscheidung, nicht die Gruppierung | Unit + Integration |
| Kein Pfad/Dateiname im Fingerprint (Feldmenge von `PhotoFingerprint`) | Unit (Struktur-Assertion) |
| Maße-Extraktion aus dem Range-Fenster, HEIC/PNG, kein Fund | Unit `test_exif.py` |
| Voller Posten schreibt Wert und Merker, auch `None`; Nachhol-Posten schreibt nur Maße + Merker, Zeit/Ort/Kamera unberührt; kein zweiter Lesevorgang bei gesetztem Merker | Integration `test_worker_scan_project.py`, `test_worker_scan_classification.py` |
| Merker nur bei allen vier Bedingungen; Schärfeschwelle exakt und ein Schritt darunter; Gewinner im Ausschuss | Integration `test_worker_score_project.py` |
| Laufbindung: Reset im RUNNING-Commit, gesetzt nur im SUCCESS-Commit, kein Merker nach Fehlschlag/Abbruch/Commit-Fehler; zweiter erfolgreicher Lauf idempotent; Gruppe nicht mehr identisch → Merker weg | Integration `test_worker_score_project.py` |
| Wettlauf: Fremdzeile zwischen Lesen und Erfolgs-Commit (Wrapper um `assign_duplicate_groups`) mit Gegenprobe ohne Zeile | Integration |
| Projektbindung des Reset/Setzens (zweites Projekt behält seinen Merker) | Integration |
| `open_count`, `total`, Einträge, `auto_decided`-Felder, `decision`/`effective_decision`, Gate-Autoset-Interaktion | Integration `test_api_ausschuss.py` |
| Zähler projektweit, unabhängig von `limit`/`offset`, auch im `photo_id`-Zweig | Integration `test_api_ausschuss.py` |
| Filter `auto_decided=true` (nur Auto-Stapel, `total` gefiltert, beide Zähler projektweit), `false` = weggelassen, `true`+`photo_id` = 422 mit `detail` | Integration `test_api_ausschuss.py` |
| `suggested`-Filter und `PhotoOut.suggestion` schließen Auto-Aufnahmen aus; Parität beider Prädikate bleibt | Integration `test_api_photos.py`, `test_ausschuss_ueberlebende.py` |
| `auto_decided` in `DuplicateGroupOut`; `position`/`total`/Nachbarn zählen alle Gruppen; Kettenlauf besucht jede genau einmal | Integration `test_api_duplicate_groups.py`, `test_duplicate_group_index.py` |
| Rücknahme per `keep`: Aufnahme bleibt, Kennzeichnung weg, Zähler −1, Rest wieder offen, späterer Lauf entscheidet nicht automatisch; `keep` auf Repräsentant | Integration `test_api_duplicate_decisions.py` |
| Nutzer-Schreibwege räumen den Merker des ganzen Sterns ab (Einzel- und Gruppenweg), nie fremde Sterne/Projekte | Integration `test_api_duplicate_decisions.py` |
| Gruppenabschluss trifft Auto-Gruppen nicht (kein offener Vorschlag → keine Auswahl, kein Schreibvorgang) | Integration `test_api_duplicate_decisions.py` |
| Migration: drei Spalten, NOT NULL/Default, Vorgänger, Downgrade | `test_migration_automatisch_entschiedene_duplikate.py` |
| Demo: drei Gruppen, eigene Konstante, Merker/keine Zeile/Schwelle/Auflösung, offene Gruppen unverändert, `photo_count`/`suggestions_found` | `test_demo_state.py` |
| Probe zieht die neue Rückgabeform nach, Bericht bleibt datensparsam | `test_duplicate_probe.py` |
| Wort „Automatisch entschieden“ (Zeile + `aria-label`), genau zwei Entscheidungen je Aufnahme, „Gruppe abschließen“ abwesend (über Anzahl, nicht Namensabfrage) | `vitest` `DuplicateStackTile.test.tsx`, `DuplicateComparePage.test.tsx` |
| Zähler + Link `?auto=1`, Filter im Query-Key, Rückweg zur vollständigen Übersicht, Zähler bei 0 nicht vorhanden | `vitest` `AusschussStepPage.test.tsx`, `useAusschuss.test.tsx`, `api/ausschuss.test.ts` |

**Edge Cases, die je einen eigenen Fall bekommen:** Gleichstand in `pixel_count` mit verlässlicher
vs. abgeleiteter Zeit (abgeleitet verliert trotz früherem Datum); Gleichstand in Zeit → kleinere Id;
Schärfeschwelle exakt/ein Schritt darunter; unbekannte Auflösung bei genau einem Mitglied; Stern aus
drei Verlierern mit gemischter Auflösung; identisches Paar plus ähnliches Kettenmitglied (letzteres
bleibt offen); Wettlauf mit und ohne Fremdzeile; `keep` auf Verlierer und auf Repräsentant;
`auto_decided=true` mit `limit` kleiner als der Bestand und mit `offset`; zweites Projekt mit
eigenem Merker; Demo-Gruppe mit unveränderlich abgelehntem Gewinner.

**Bewusste Erwartungsänderungen (keine Regressionen):** `test_scoring.py` (elf
`assign_duplicate_groups(...) == {...}` wandern auf `.duplicate_of`), `test_demo_state.py` (zwei →
drei Gruppen, `len(Repräsentanten)`),
`test_api_ausschuss.py::test_the_answer_carries_exactly_the_agreed_fields`,
`test_duplicate_probe.py`, `e2e/tests/ausschuss-stapel.spec.ts` (Stapelzahl 2 → 3).
`_ERWARTETE_VERWENDUNGEN` in `test_ausschuss_ueberlebende.py` bleibt laut Architektur unverändert.

## UI/UX

Sichtbare Oberfläche: **ja** — an drei bestehenden Stellen, ohne neue Ansicht, ohne neuen Dialog,
ohne neue Route, ohne neues Symbol. Der Träger der Kennzeichnung ist ein **Wort**; eine automatische
Entscheidung bekommt nie die Form einer Nutzerentscheidung (kein `--accent`, keine
`--danger`-Fläche, kein neues Kennzeichen, keine eigene Schaltfläche). Die frühere
Produktentscheidung zu Serien ähnlicher Bilder ändert daran nichts: Ein Stapel ist entweder ganz
automatisch entschieden oder gar nicht — es gibt keinen dritten Kachelzustand und keinen Mischfall.

### Ablauf

1. **Ausschuss-Schritt, Übersicht** (`pages/pipeline/AusschussStepPage.tsx`) — direkt unter der
     Zeile `suggestionsFoundText`, im selben Textblock, ein neuer Zähler als Link: `Button asChild
     variant="outline" size="sm"`, Beschriftung `{n} Gruppen automatisch entschieden` bzw. `1 Gruppe
     automatisch entschieden`, Ziel `ausschussStepPath(id, { auto: true })` → `?auto=1`. Die Zahl
     steht im Linktext, nicht in einem `aria-label` daneben. `className="h-11 sm:h-8"` (heißer Pfad,
     44 px am Telefon), in `flex flex-wrap`, damit die Zeile bei 360 px umbricht statt waagerecht zu
     scrollen.
     - Bei `auto_decided_group_count === 0` **entfällt die Zeile ganz** (kein Link ins Leere) — sie
    ist kein Statusfeld, das immer dastehen müsste.
     - Solange der Bestand lädt oder das Laden fehlschlägt, gibt es keinen Zähler: keine `0`, kein
    Platzhalter für eine Zeile (ein Zähler, der erst nachträglich „0 → 3“ springt, wäre die falsche
    Aussage).
2. **Gefilterte Ansicht** — dieselbe Seite, derselbe Aufbau; der Filter liegt **nur in der Adresse**
     (`?auto=1`) und geht als `autoDecided` in `useAusschussQuery`. Über dem Raster, an derselben
     Stelle wie sonst der Zähler, steht ein Block aus zwei Elementen: `p` (`text-sm text-text`,
     `data-testid="ausschuss-auto-filter"`) mit `Nur automatisch entschiedene Gruppen` und
     daneben/darunter `Button asChild variant="ghost" size="sm"` mit Text `Alle Gruppen anzeigen` als
     `<Link to={ausschussStepPath(id)}>` (`h-11 sm:h-8`).
     - Dieser Block hängt **an der Adresse, nicht an der Antwort**: Er steht auch während des Ladens
    und bei einem Fehler, damit der Rückweg nie von Daten abhängt.
     - `open_count` und `auto_decided_group_count` bleiben projektweit (Architektur) — Statuszeile und
    Abschluss-Aktion der Leiste zeigen also weiter die Gesamtlage, nicht die gefilterte Menge. Die
    gefilterte Menge zeigt nur das Raster.
     - Ein Eintrag der gefilterten Liste öffnet wie heute die Detailansicht über `?photo=`;
    `closeDetail` kopiert die übrigen Parameter, `?auto=1` bleibt also stehen, und der
    Browser-Zurück-Knopf führt in die gefilterte Liste. Die Vergleichsansicht wird von dort mit
    `fromAusschuss` betreten wie aus der Vollansicht.
3. **Stapel-Kachel** (`components/DuplicateStackTile.tsx`) — bei `entry.auto_decided` ersetzt das
     Wort `Automatisch entschieden` den Teil `{undecided} vorgeschlagen`; die Zusammenfassungszeile
     lautet dann `{group_size} Aufnahmen · Automatisch entschieden`. Die gespeicherten
     `decision_counts` entfallen in diesem Fall ganz (sie sind leer und läsen sich als „nichts
     passiert“, obwohl die Gruppe entschieden ist). Schrift `text-text-h` wie `{group_size} Aufnahmen`
     — weder `text-accent` noch `text-danger-text`, weil der Zustand weder „behalten“ noch „Ausschuss“
     ist. Der zugängliche Name des einen Links trägt dasselbe Wort: `Duplikat-Gruppe mit {n}
     Aufnahmen, automatisch entschieden: {pfad}`. Kein zusätzliches Kennzeichen an der Bildecke (der
     Platz dort gehört dem Grund-Kennzeichen „Duplikat“).
4. **Vergleichsansicht** (`pages/DuplicateComparePage.tsx`) — bei `query.data.auto_decided` stehen
     unter der `h1` zwei Absätze (`text-sm text-text`, unmittelbar beieinander):
     - `Automatisch entschieden – praktisch identische Aufnahmen`
    (`data-testid="duplicate-auto-decided"`) — die Überschrift selbst und die Gruppen-Navigation
    bleiben unverändert.
     - `Zurücknehmen: „Behalten“ auf einer Aufnahme wählen. Die Gruppe ist danach offen, und ein
    späterer Lauf entscheidet sie nicht erneut automatisch.` — dauerhaft sichtbar, kein Toast, direkt
    über den Kacheln; der Satz nennt Folge und Dauer der Rücknahme, weil beides aus der Handlung
    selbst nicht ablesbar ist.
     - Die Kacheln bleiben bei genau „Behalten“/„Ausschuss“; `DUPLICATE_HINT_TEXT` und
    `DUPLICATE_CONSEQUENCE_TEXT` bleiben wörtlich. „Gruppe abschließen“ **entfällt** in diesen Gruppen
    (nicht `disabled`): Er schriebe einen Stand fest, der schon festgeschrieben ist, und er steht
    allein am Ende der Seite — es rückt nichts unter dem Finger nach. „Alle behalten“ / „Alle in den
    Ausschuss“ bleiben: Sie sind ein gültiger Weg zurück in eine Nutzerentscheidung.
     - Nach einem erfolgreichen `keep` in einer automatisch entschiedenen Gruppe ersetzt ein `p
    role="status"` (`text-sm text-text`) den Kennzeichnungs- und den Rücknahme-Absatz: `Automatische
    Entscheidung zurückgenommen — die Gruppe ist jetzt offen.` Der Zustand wird lokal gemerkt (die
    Antwort liefert danach `auto_decided: false`) und wie die übrigen Seitenzustände beim
    Gruppenwechsel zurückgesetzt. Damit ist die verschwindende Kennzeichnung angesagt und nicht nur zu
    sehen.

### Zustände

- **Leer, 0 automatische Gruppen (ungefiltert):** nichts Neues — kein Zähler, kein Hinweis.
  `AUSSCHUSS_EMPTY_TEXT` und der übrige Seitenaufbau bleiben unverändert.
- **Leer, gefiltert (0 Einträge):** eigener Leertext `Keine automatisch entschiedenen Gruppen.`
  (`text-sm text-text`, ohne `Alert`, ohne Fehlerfarbe); der Rückweg-Block steht darüber bereits.
  Der allgemeine Leertext erscheint dann **nicht** zusätzlich (Muster „zwei getrennte Leerzustände,
  nie zugleich“).
- **Ladend:** ungefiltert wie heute (Skeleton-Raster mit `role="status"`, `aria-label="Ausschnitt
  wird geladen…"`); kein Zähler, bis die erste Seite da ist. Gefiltert ebenso, mit sichtbarem
  Rückweg (siehe oben).
- **Fehler:** bestehendes `Alert` mit „Erneut versuchen“; der Zähler fehlt statt `0` zu zeigen.
  Gefiltert wiederholt der Retry die gefilterte Anfrage, der Rückweg bleibt bedienbar.
- **Rücknahme wirkt:** Die Kachel verschwindet in der gefilterten Liste ohne Animation (Muster
  „Erledigte Karte verlässt die Ansicht“), der Zähler sinkt im selben Render; in der
  Vergleichsansicht erscheint die Statuszeile aus Punkt 4 und „Gruppe abschließen“ tritt hinzu.

### Barrierefreiheit

- **Nicht nur Farbe:** Der Zustand steht als Wort in der sichtbaren Zusammenfassungszeile, im
  `aria-label` des Stapel-Links und als Absatz im Gruppenkopf. Weder Zähler noch Kennzeichnung
  führen eine neue Farbe ein; es kommen nur die bestehenden Textstufen `--text`/`--text-h` zum
  Einsatz.
- **Zähler und Rückweg sind echte Links mit Textnamen** („3 Gruppen automatisch entschieden“, „Alle
  Gruppen anzeigen“), kein `onClick` auf einem `<span>`, kein „hier klicken“; der Zahlenwert ist
  Teil des Linktextes, damit er beim Durchtabben mitgelesen wird.
- **Trefferflächen:** beide neuen Links `h-11 sm:h-8` (44 px am Telefon), Zeile bricht um statt
  waagerecht zu scrollen; der Fokusring bleibt unbeschnitten (kein `overflow-hidden` am Container).
- **Tastatur und Adresse:** Der Filter ist ausschließlich über die Adresse gesetzt und über einen
  fokussierbaren Link wieder zu verlassen; der Browser-Zurück-Knopf führt ebenfalls zurück. Der
  Zähler ist genau **ein** zusätzlicher Tab-Stop vor dem Raster.
- **Kontrast:** Wörter und Zähler stehen auf `--bg` in `--text`/`--text-h`, also in den bereits
  geprüften Paaren; keine Fläche über einem Bild, keine Deckkraft auf einem Bedeutungsträger.
- **Ansage des Wechsels:** Nur die Rücknahme erhält eine Live-Meldung (`role="status"`), weil dort
  ein Zustand verschwindet. Der Zähler selbst ist kein Live-Bereich — er änderte sich sonst bei
  jedem Lauf.

### Design-System

Ergänzt werden muss es, aber **ohne neues Token, ohne neue Komponente, ohne neue Bibliothek** — zwei
Einträge in `specs/architecture/0004-design-system.md` (und wortgleich im Schnellreferenz-Skill
`.claude/skills/design-system/SKILL.md`):

1. **Eintrag „Duplikat-Stapel“ fortschreiben:** Bei automatisch entschiedenen Gruppen trägt die
     Zusammenfassungszeile das Wort „Automatisch entschieden“ **statt** der Vorschlagszahl, in
     `--text-h`; die gespeicherten Entscheidungszahlen entfallen dort. Begründung im Dokument: leer
     wirkende Zahlen an einer entschiedenen Gruppe sind eine falsche Aussage.
2. **Neues Muster „Eine automatische Entscheidung trägt nie die Form einer Nutzerentscheidung“**
     (Fortschreibung von „Die Schätzung eines Modells trägt nie die Form der Entscheidung eines
     Menschen“): Wort statt Farbe/Symbol/gefüllter Fläche; Rücknahme ausschließlich über die
     bestehende Handlung, mit der Folge („gilt auch für weitere Läufe“) als dauerhaftem Satz an der
     Handlung; kein Bestätigungsdialog; eine gefilterte Ansicht liegt nur in der Adresse, hat einen
     sichtbaren Rückweg an derselben Stelle und bei Zahl 0 keinen Link.

Penpot: Die Seite `duplikate` ist laut „Bekannte Lücken“ bereits in zwei Punkten veraltet; die
Wortvariante der Zusammenfassungszeile ist dort mit nachzuziehen, wenn die Seite ohnehin
überarbeitet wird. Kein Baustein, kein Penpot-Blocker für die Umsetzung.


## Security

**Einstufung: sicherheitsrelevant, kein Blocker.** Kein Secret, keine Umgebungsvariable, kein neuer
externer Dienst, kein neuer Empfänger, kein neuer Freitext aus fremder Quelle, kein neuer Endpunkt,
keine Änderung an Authentifizierung oder an der Sichtbarkeit zwischen den beiden Nutzern. Neu ist
dreierlei: Der Automat schreibt erstmals einen Zustand, den die Oberfläche bisher nur aus einer
Nutzerentscheidung kannte; das Gate des Ausschuss-Schritts öffnet in einem Fall **ohne Sichtung**;
und jeder Nutzer-Schreibweg setzt zusätzlich einen Merker über einen ganzen Stern zurück. Die
berührte Grenze ist die Cloud-Abflussgrenze aus ADR 0104 — sie wird gelesen, nicht verschoben.

- **S1 — Der Merker ist keine Entscheidungszeile.** `PhotoScore.auto_decided` ist Lauf-Zustand;
  `photo_duplicate_decisions` bleibt allein Nutzerentscheidung, kein Lauf schreibt oder löscht dort.
  Ausfallrichtung: Läge die automatische Entscheidung in derselben Tabelle, trüge sie die Autorität
  eines Klicks — der nächste Lauf und jeder Lesepfad behandelten sie als „der Nutzer hat
  entschieden", und die Rücknahme wäre von einer Nutzerentscheidung nicht mehr zu unterscheiden.
- **S2 — Der Merker bleibt außerhalb des Überlebens-Prädikats.**
  `survives_ausschuss`/`survives_ausschuss_for` bleiben wörtlich unverändert, die cloud-bestimmenden
  Abfragen in `worker.py` und `api/projects.py` ebenfalls, und **kein** Eintrag in
  `tests/test_ausschuss_ueberlebende.py::_ERWARTETE_VERWENDUNGEN` wird gesenkt oder entfernt. Grund:
  Das Prädikat bestimmt, welche Bilddaten den Homeserver verlassen; ein laufabhängiger,
  maschinengeschriebener Wert darin machte die Cloud-Kandidatenmenge davon abhängig, ob ein Lauf
  erfolgreich war. Zu gewinnen ist nichts — der Merker steht nur an `REJECTED`-Verlierern, die
  ohnehin nicht überleben. **Zusätzlich** zur Zählung ein struktureller Wächter: kein
  Attributzugriff `auto_decided` im Syntaxbaum von `survives_ausschuss*`/`decision_effective*` (die
  Aufrufstellenzahl sieht den Inhalt des Prädikats nicht).
- **S3 — Das Gate-Autoset zählt offene Vorschläge, nicht Abgelehnte, und ist keine Einwilligung.**
  Bedingung ist `len(rejected_ids − auto_decided_ids) == 0`, gebildet im SUCCESS-Commit in
  derselben Transaktion aus den Id-Mengen des Laufs, nicht aus einem vor dem Schreiben gelesenen
  Stand; `suggestions_found` bleibt die Zahl aller Ablehnungen. Der Zeitstempel ist
  Arbeitsfluss-Voraussetzung (`409` an den Cloud-Endpunkten ohne ihn), der Datenabfluss hängt
  allein am projektweiten Einwilligungsschalter
  (`cloud_vision_consent_at`/`cloud_vision_detection_enabled`), der unberührt bleibt, ohne Zutun
  `False` ist und ohne den jeder Cloud-Aufruf `403` ergibt.
- **S4 — Setzen und Zurücksetzen sind projektgebunden und gegen die Nutzerentscheidung
  abgesichert.** `PhotoScore` trägt keine `project_id`: Der projektweite Reset beim Laufstart führt
  `Photo.project_id` in **derselben** Anweisung (sonst löschte der Lauf eines Projekts den Merker in
  allen). „Kein Mitglied trägt eine Entscheidungszeile" steht als `NOT EXISTS` in der setzenden
  `UPDATE`-Anweisung, nie aus einem vorher gelesenen Stand — ein Nutzer-Schreibvorgang während des
  Laufs gewinnt.
- **S5 — Die Rücknahme setzt den Merker des Sterns über die projektgebundene Kantenliste zurück, und
  „kein Stern" ist die leere Menge.** `_write` nimmt die Mitglieder aus denselben `links`, die den
  Repräsentanten aufgelöst haben — nie aus einer zweiten Abfrage auf `photo_scores.duplicate_of`
  (die kennt kein Projekt), nie aus dem Körper. `member_ids_of(None, …)` ist jedes Foto ohne
  `duplicate_of`; ein Reset über diese Menge wäre ein projektweiter Schreibweg. Entscheidungszeile
  und Reset liegen in **einer** Transaktion, und der `rollback` des `409`-Falls nimmt beides zurück
  — sonst bliebe eine Gruppe zugleich automatisch und vom Nutzer entschieden.
- **S6 — Der neue Query-Parameter wählt eine Variante, keine Zugriffsmarke.** `auto_decided` ist ein
  deklarierter `bool` (kein eigenes String-Parsing); zusammen mit `photo_id` ergibt er `422` **vor**
  jeder Abfrage. Der gefilterte Zweig baut seine Einträge weiter aus `load_duplicate_links(session,
  project.id)`; `total` zählt die gefilterten Einträge, `open_count` und `auto_decided_group_count`
  bleiben projektweit — kein Zähler aus einer zweiten, ungebundenen Abfrage. Der Wert wird nie
  gespiegelt. Ausgeschriebener Torwächter und pfadbenannter 401-Fall bleiben, `limit` bleibt
  gedeckelt.
- **S7 — Die neuen Antwortfelder sind Serverurteile.** Zwei Wahrheitswerte und eine Zahl, kein
  Freitext, keine Spiegelung einer Eingabe → kein neuer XSS-Sink. „Automatisch entschieden" ist ein
  Literal der Oberfläche samt Zahl; auch im `aria-label` steht kein Server-Text. `?auto=1` liegt in
  der Adresse, ist ein Filter und **kein** Umleitungsziel — die Regel „Rückweg-Parameter wählt eine
  Variante und nennt kein Ziel" (Spec 0533, S11) gilt unverändert, Linkziele entstehen aus der
  numerischen Projekt-Id.
- **S8 — Kein neues Eingabefeld, kein neuer Schreibweg; die Cache-Auflage gilt unverändert.**
  `DuplicateDecisionIn` behält genau ein Feld und `extra="forbid"` — der Merker ist aus keinem
  Körper schreibbar. Die Rücknahme ist ein `keep` über den bestehenden Endpunkt: dieselbe Auth,
  dieselbe Projektbindung, dieselbe 401/404-Lage. Der Stapel trägt `cover` als `PhotoOut` und ist
  damit eine Funktion des anfragenden Nutzers; jede Zwischenspeicherung über `no-store` hinaus führt
  den Nutzer im Schlüssel.
- **S9 — Der Maße-Leser ist ein Parser über Fremdtext.** `opencloud/exif.py::extract_pixel_count`
  liest Kopfdaten einer Datei vom WebDAV-Server und bleibt deshalb in diesem Modul, dessen Import
  den HEIF-Opener registriert (`image_codecs.py`) — ein neues Modul mit eigenem `from PIL import
  Image` umginge die Registrierung. Gelesen werden nur Maße, keine Pixeldaten; ein unlesbarer oder
  entarteter Kopf ergibt `None` und setzt trotzdem `pixel_count_probed` (kein Endlos-Abruf je Scan).
  Eine geschätzte Zahl ist untersagt — sie verschöbe die Gewinnerregel stillschweigend.
  `pixel_count` verlässt die Datenbank nicht: kein Antwortfeld trägt es.

**Restrisiko (von der Story getragen, hier nicht neu entschieden):** Eine fälschlich als praktisch
identisch erkannte Gruppe wird ohne menschlichen Blick Ausschuss. Getragen von vier Eigenschaften
zusammen: jederzeit umkehrbar über den bestehenden Schreibweg; laufgebunden (ein fehlgeschlagener
Lauf hält nichts fest); fail-closed (kein `keep`, kein Bild verlässt den Homeserver, OpenCloud
unberührt); jede Nutzerentscheidung gewinnt. **Nicht getragen:** bis zur Rücknahme ist die Gruppe
unsichtbar, und ein systematischer Fehler der Identisch-Erkennung träfe viele Gruppen auf einmal —
bemerkbar über die Zahl der automatisch entschiedenen Gruppen, nicht über die offenen Fälle.
Voraussetzung bleibt die verbesserte Erkennung aus #637.

**Sicherheitskonzept:** ergänzt — Abschnitt „Automatisch entschiedene Duplikatgruppen …" und fünf
Ankerzeilen in [`0003-securitykonzept.md`](../architecture/0003-securitykonzept.md), dazu ein
Restrisiko-Eintrag.

## Entscheidungen

- **Merker statt Entscheidungszeile** (ADR 0146 Punkt 3): Die automatische Entscheidung ist
Lauf-Zustand am Verlierer, `photo_duplicate_decisions` bleibt allein Nutzerentscheidung. Damit gilt
„kein Lauf ändert eine Nutzerentscheidung" durch die Bauart, und die Rücknahme braucht keinen neuen
Schreibweg.
- **Zurücksetzen im RUNNING-Commit, Setzen im SUCCESS-Commit:** Ein fehlgeschlagener, abgebrochener
oder am Commit gescheiterter Lauf hält keine automatische Entscheidung fest; die Kehrseite ist eine
kurze Spanne, in der die betroffenen Aufnahmen als offen lesen.
- **Gewinnerregel nur für praktisch identische Gruppen** (Produktentscheidung Daniel, 2026-11-12):
In Serien ähnlicher Bilder bleibt die Schärfe das Kriterium; bei Kopien entscheidet die Auflösung,
weil die Schärfe auf der verkleinerten `display`-Variante irreführt.
- **Auflösung als `pixel_count`:** ein Produkt statt zweier Spalten; das Seitenverhältnis gibt es
bereits.
- **Unbekannte Auflösung heißt keine automatische Entscheidung** und sortiert zuletzt — eine
geschätzte Zahl könnte eine verkleinerte Kopie bevorzugen.
- **Gleichstand: kleinere `photo_id`, „älter" nur bei verlässlicher Zeit.** Eine aus dem Dateidatum
abgeleitete Zeit ist keine Messung (ADR 0145) und verliert gegen jede verlässliche.
- **Merker nur im Offen-Prädikat, nie im Überlebens-Prädikat** (Security S2): Die
Cloud-Kandidatenmenge darf nicht davon abhängen, ob ein Lauf erfolgreich war.
- **Filter `?auto_decided=true` statt eines Ankerfelds:** „führt zu ihnen" heißt in der Mehrzahl
eine Liste; das Muster des `photo_id`-Filters trägt.
- **Zähler entfällt bei 0, Rückweg hängt an der Adresse:** Ein Link auf eine garantiert leere
Ansicht ist eine Sackgasse; der Rückweg darf nicht von Daten abhängen.
- **„Gruppe abschließen" fehlt in automatisch entschiedenen Gruppen statt `disabled`:** Es gibt
keine Aktion, die nur gerade nicht erlaubt wäre.
- **Demo: dritte Gruppe im bestehenden Projekt** statt eines neuen Projekts; Projektzahl und
Doku-Verweise bleiben stabil.
- **Testkonzept ergänzt** (`specs/architecture/0002-testkonzept.md`): Laufbindung wird am
Abbruchpfad geprüft, der Wettlauf mit einer Fremdzeile zwischen Lesen und Erfolgs-Commit samt
Gegenprobe, zwei sich ausschließende Filter in einem Aufruf.

## Offene Fragen

Keine. Die Gewinnerregel war die einzige offene Weggabelung; Daniel hat sie am 2026-11-12 wie
empfohlen bestätigt (nur praktisch identische Gruppen).

## Out of Scope

- Teilweise automatische Gruppen, automatische Entscheidungen in bloß ähnlichen Gruppen.
- Rücknahme-Protokoll, Verlauf oder Benachrichtigung über automatische Entscheidungen.
- Neue Tabellen, ein neuer Schreibweg oder ein neuer Endpunkt.
- Änderung von Stern, Entscheidungstabelle, Überlebens-Prädikat, Vergleichsansicht-Aufbau oder
Abschluss-Aktion.
- Herabsetzen der Schärfeschwelle oder Aufweichen der Identisch-Erkennung aus #637.
