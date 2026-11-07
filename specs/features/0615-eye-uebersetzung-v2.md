# 0615 - Treffendere Eye-Übersetzung für Dokument-Ausschluss, Tiere und Aktivität

**Status:** Implemented ([PR #619](https://github.com/TheRealKoller/photosort/pull/619))
**Erstellt:** 2026-11-07
**Bezug:** Issue [#615](https://github.com/TheRealKoller/photosort/issues/615), ADR
[`0140`](../decisions/0140-eye-uebersetzung-v2-lauf-fassung-tiererkennung-fassung-je-ergebnis.md)

## Ziel

Die Eye-Übersetzung `eye-4.2.3/v1` schließt gewöhnliche Fotos als Dokument aus, sobald Eye eine
der zwölf Fotoarten erkennt, erkennt Tiere nur bei vier Arten und Aktivität nur bei Sport. Eine
neue Fassung `eye-4.2.3/v2` übersetzt treffender, der Eye-Lauf rechnet mit ihr, und an jedem
Eye-Ergebnis steht, mit welcher Fassung es entstand.

## User Story

Als Nutzer möchte ich, dass die Eye-Auswertung gewöhnliche Fotos nicht als Dokument aussortiert
und Tiere und Aktivitäten so erkennt, wie ich sie verstehe, damit Eye eine brauchbare Grundlage
für die Motivauswahl ist.

## Akzeptanzkriterien

- [ ] Gewöhnliche Fotos bleiben eingeschlossen, auch mit Schild, Karte oder Bildschirm im
  Hintergrund; v2 schließt nur aus, wenn Eyes Fotoart (`kind`) Dokument, Screenshot, Beleg,
  abfotografierter Bildschirm oder Ausweis ist.
- [ ] Tiere umfasst jede Art: Oberbegriffe und Tierklassen des Eye-Vokabulars sowie Eyes eigene
  Tiererkennung (`pets`).
- [ ] Aktivität umfasst Tätigkeiten über Sport hinaus (Wandern, Gehen, Laufen, Baden/Schwimmen,
  Spielen, Radfahren, Tanzen, Wintersport); reine Gegenstände, Orte, Kleidung, Zuschauersport,
  Segelboot und Schach zählen nicht.
- [ ] Die Regeln sind allgemein (Fotoarten, Tag-Klassen), nicht auf einzelne Fotos abgestimmt.
- [ ] Die übrigen sechs Motive, die Albumstufe und die Feinlabels sind in v1 und v2 identisch.
- [ ] Ein Eye-Lauf rechnet mit v2; jedes Eye-Ergebnis trägt seine Fassung, und das Eye-Band der
  Einzelbildansicht nennt sie. Bestehende Ergebnisse tragen `eye-4.2.3/v1`.
- [ ] v1 bleibt aufrufbar; die Klassifizierungsprüfung bietet v1 und v2 an.
- [ ] Cloud-Ergebnisse, Album-Entwurf und Cloud-Kandidatenauswahl bleiben unverändert; kein neuer
  Eye-Egress; keine Neubewertung bestehender Ergebnisse.

## Datenmodell-Bezug

`photo_eye_results` erhält `mapping_version` (String, NOT NULL, ohne bleibenden Default); siehe
`PhotoEyeResult` in [`docs/architecture.md`](../../docs/architecture.md).

## Architektur / Umsetzung

**Fassungen.** `eye_mapping.py` registriert `eye-4.2.3/v2` als zweiten Eintrag in `MAPPINGS`;
v1 bleibt wertgleich und ist als `MAPPING_VERSION_V1` aufrufbar. `MAPPING_VERSION` ist die
Lauf-Fassung und wird `eye-4.2.3/v2`; `EYE_PURPOSE_MAPPING` beschreibt sie. `analyze(payload,
version)` hat keinen Default: Der Worker übergibt `MAPPING_VERSION`, die Klassifizierungsprüfung
die gespeicherte Fassung ihrer Seite. Der Rückfall `side.eye_mapping_version or MAPPING_VERSION`
in `classification_review.py` entfällt; fehlt die Fassung, entsteht `EyeMappingError`.

**Ausschluss.** v2: ausgeschlossen genau dann, wenn `payload["kind"]` in {`document`,
`screenshot`, `receipt`, `photo_of_screen`, `id_card`} liegt. Fehlendes, unbekanntes oder
nicht-textuelles `kind` schließt nicht aus. Tags spielen für den Ausschluss keine Rolle.

**Tiere.** Stärke = Maximum aus den Tag-Konfidenzen von `dog`, `cat`, `bird`, `horse`, `animal`,
`pet`, `wildlife`, `insect`, `reptile`, `fish`, `marine_mammal` und der größten `confidence` in
`pets`. `EyeMapping` erhält `motif_detections: Mapping[str, str]` (v2 `{"tiere": "pets"}`, v1
leer). Fehlerhaftes `pets` (fehlt, kein Array, Eintrag kein Objekt, `confidence` nicht numerisch,
`bool`, NaN, unendlich) zählt als 0; Werte werden auf [0, 1] geklemmt.

**Aktivität.** v1-Tags plus `hiking`, `walking`, `running`, `cross_country_running`,
`ultramarathon`, `track_and_field_athletics`, `skiing`, `snowboarding`, `ice_skating`,
`water_skiing`, `cycle_sport`, `racing_bicycle`, `dance`, `playground`, `sports`,
`volleyball_sport`, `baseball_sport`, `american_football`, `golf`, `hockey`, `bowling`, `canoe`.

**Feinlabels und übrige Motive.** `EyeMapping` erhält `fine_label_excluded` (die bisherigen zwölf
Fotoarten, in v1 und v2 gleich); `fine_labels` filtert darüber statt über die Ausschlussmenge.
Übrige sechs Motive, Albumstufe und Schwellen sind in v2 identisch mit v1.
`eye/src/pins.json::mappingTags` ist die Vereinigung der Motiv-Tags aller Fassungen.

**Fassung je Ergebnis.** Migration (Vorgänger `44ba5fe0184a`, Kennung über
`scripts/nummern.py migration eye_mapping_version`): erster `batch_alter_table`-Block legt
`mapping_version` mit `server_default="eye-4.2.3/v1"` an, ein zweiter entfernt den Default;
Downgrade entfernt die Spalte. `_write_eye_shadow_rows` schreibt `MAPPING_VERSION`.
`EyeResultOut` (`api/photos.py`) und `frontend/src/api/types.ts` erhalten `mapping_version`.
Demo-Stand (`demo_state.py`) und Testgraph (`tests/project_graph.py`) setzen die Spalte.

**Grenzen.** Die Fotoart gibt es nur als `kind`; ein Bildschirmfoto, das Eye als `photo`
einstuft, bleibt eingeschlossen. Kein Sidecar-Umbau, keine Neubewertung, Rangfolge
`local < eye < cloud` unverändert.

**Reihenfolge.** 1. `eye_mapping.py` + `pins.json` + Tests. 2. Modell, Migration,
Migrationstest. 3. Worker, Demo-Stand, Prüfpfad. 4. API, Frontend-Typ, Eye-Band.

### Teststrategie

Alle Eye-Tests laufen mit synthetischen `toJSON()`-Payloads und Fake-Eye-Client.

- **Ausschluss (`test_eye_mapping.py`):** jeder der fünf Typen schließt in v2 aus; `map`,
  `whiteboard`, `chart_or_slide`, `meme_or_graphic` und die drei `*_reference` schließen in v2
  nicht aus, in v1 schon; `kind="photo"` mit starkem Tag `map`/`document` bleibt drin; fehlendes
  oder nicht-textuelles `kind` schließt nicht aus.
- **Tiere:** Stärke über `animal` und über eine Tierklasse (`insect`); Stärke über `pets` ohne
  Tier-Tag; Maximum aus Tag und `pets`; in v1 zählt `pets` nicht; fehlerhaftes `pets` ergibt 0,
  Werte > 1 bzw. < 0 werden geklemmt.
- **Aktivität:** parametrisiert über `hiking`, `walking`, `cycle_sport`, `playground`, `dance`
  > 0; `surfboard`, `stadium`, `swimming_pool`, `swimwear`, `sailboat`, `chess`,
  `horse_racing`, `motorsport` allein ergeben 0.
- **Unverändertes:** eine Payload mit allen Tabellen-Tags der sechs übrigen Motive und
  `aesthetic` an jeder Bandgrenze liefert in v1 und v2 dieselben Stärken und Albumstufen;
  Feinlabels identisch, auch bei `map: 0.9`.
- **Allgemeine Regeln:** testbar ist die Reinheit der Funktion, der Importwächter und der
  Vokabularabgleich (`eye/test/tags.test.js` über `pins.json`); dass die Listen Klassen statt
  Einzelbilder benennen, prüft das Review.
- **Worker (`test_worker_eye_phase.py`):** Zeile trägt `MAPPING_VERSION`; ein neuer Lauf ersetzt
  eine v1-Zeile durch v2; `kind="map"` → nicht ausgeschlossen, `kind="receipt"` → ausgeschlossen.
- **Migration (`test_migration_eye_mapping_version.py`):** `down_revision`; Altzeile erhält v1,
  übrige Spalten unverändert; danach NOT NULL ohne Default, INSERT ohne Fassung scheitert;
  Downgrade entfernt die Spalte.
- **API/Prüfpfad:** `eye_result.mapping_version` gesetzt (`test_api_photos.py`); Prüfoptionen
  listen v1 und v2; Eye-Seite ohne Fassung wirft `EyeMappingError`.
- **Frontend (`PhotoDetailPage.test.tsx`):** Band nennt „Übersetzung eye-4.2.3/v2“ bzw. v1, in
  der Reihenfolge Modellrevision, Übersetzung, Zeitpunkt.
- **Regression:** bestehende Cloud-, Album- und Isolationstests bleiben grün.
- **Anzupassen:** Pins von `MAPPING_VERSION`, `len(excluded_types)` (auf v1), Pin-Vergleich über
  die Vereinigung, `analyze`-Aufrufe ohne Version, exaktes `eye_result`-Dict, Fixtures mit
  `PhotoEyeResult`.
- **Bekannte Lücke:** ob reale Fotos mit Hintergrundschild `kind=photo` liefern, ist nur am
  echten Modell prüfbar (Heimserver-Stichprobe).

## UI/UX

Einzige sichtbare Änderung: das Eye-Band der Einzelbildansicht (`data-testid="eye-band"`). Text:

> Albumtauglichkeit und Feinlabels stammen aus der Eye-Auswertung — Modellrevision
> {model_revision}, Übersetzung {mapping_version}, {Zeitpunkt}.

- Die Fassung erscheint als Rohwert (`eye-4.2.3/v2`), Begriff „Übersetzung“ wie auf der
  Prüfseite; keine Namenstabelle im Frontend.
- Reihenfolge Modellrevision, Übersetzung, Zeitpunkt; im bestehenden `text-xs text-text`-Absatz,
  ohne Chip, Farbe oder Symbol. `EyeAttribution` bleibt darunter.
- Kein neuer Zustand: Das Band erscheint wie bisher nur bei `eye_result`; die Fassung ist immer
  gesetzt.
- Grundlagenzeile des Motivabschnitts, Prüfseite und Design-System bleiben unverändert.

## Security

Sicherheitsrelevant, kein Blocker. Kein neuer Endpunkt, kein Auth-Pfad, kein Secret, kein neuer
Empfänger, kein Eye-Egress. Neu: `pets` aus der Sidecar-Antwort als zweites Fremdsignal einer
Motivstärke, eine Spalte, ein Antwortfeld.

- **S1 — `pets` ist Fremdeingabe und bringt den Lauf mit keinem JSON-Wert zum Absturz.**
  Gelesen nur bei `isinstance(pets, list)` (ein `dict`/`str` ergibt 0); ein Eintrag zählt nur als
  `Mapping`; `confidence` läuft durch dieselbe Funktion wie die Tag-Konfidenz (`_confidence`):
  `bool` ausgeschlossen, NaN → 0, Ergebnis endlich in [0, 1]. Eine JSON-Ganzzahl jenseits des
  float-Bereichs ergibt 0 statt `OverflowError` — auch für Tags; v1 bleibt für jede heute nicht
  scheiternde Eingabe wertgleich. **Wo:** `eye_mapping.py`. **Bei Verletzung:** ein kaputter Wert
  bricht die Eye-Phase ab, oder NaN legt die Fotoliste auf `500`.
- **S2 — `pets` bleibt eine Zahl.** Antwortkörper ist schon auf 1 MiB gedeckelt; ausgewertet wird
  ein Maximum über die oberste Listenebene ohne Rekursion. Label, Box und übrige Felder von `pets`
  werden weder persistiert noch geloggt noch ausgegeben. **Bei Verletzung:** ungesäuberter
  Fremdtext in Datenbank oder Oberfläche.
- **S3 — Der Ausschluss bleibt exakte Mitgliedschaft.** Nur bei `isinstance(kind, str)` und genauer
  Übereinstimmung mit der festen v2-Menge; `excluded_document` bleibt `bool`, NOT NULL ohne
  Default. Der Ausschluss ist keine Vertraulichkeitskontrolle (die Cloud-Kandidatenauswahl liest
  ihn nicht); seine Breite ist eine Produktfrage.
- **S4 — Die Fassung kommt nur vom Server.** `mapping_version` ist im Worker immer die Konstante
  `MAPPING_VERSION`, nie ein Wert aus Request, Sidecar-Antwort oder Umgebung; die Prüfung nimmt
  Fassungen weiter nur als Schlüssel von `MAPPINGS` an (`422`). **Bei Verletzung:** ein Ergebnis
  behauptet eine Fassung, mit der es nicht entstand.
- **S5 — Kein stiller Rückfall auf eine Fassung.** Fehlende Fassung → `EyeMappingError`; die
  Prüfung endet `FAILED` mit festem deutschem Satz ohne Fassungsstring, Host oder Stacktrace.
  **Bei Verletzung:** eine Prüfung rechnet unbemerkt mit einer anderen Fassung, als sie ausweist.
- **S6 — Die Migration ist additiv und hält NOT NULL ohne bleibenden Default.** Der
  `server_default` dient nur dem Backfill und wird im zweiten Batch-Block entfernt; keine neue
  Löschkante. **Bei Verletzung:** ein Schreibpfad, der die Spalte vergisst, behauptet still „v1“.
- **S7 — Die Fassung wird nur als Text gerendert:** React-Textknoten, nie
  `dangerouslySetInnerHTML`, `href`, `src`, `style`, `key`, `aria-label` oder `title`.
- **S8 — Keine Wirkung auf Cloud und Kosten:** Rangfolge `local < eye < cloud`; Eye schreibt nie in
  `photo_album_suitability` oder `photo_fine_labels`.

**Nicht relevant:** Auth, Nutzersichtbarkeit, Secrets, Consent, Kostenschätzung, Bilddatenfluss,
Compose-Netz.

## Entscheidungen

- **Breite des Ausschlusses** (Daniel, 2026-11-07): die vier in der Story genannten Typen plus
  `id_card`; Karte, Whiteboard, Folie, Meme und die drei Referenztypen bleiben eingeschlossen.
- **Aktivität** (Daniel, 2026-11-07): ohne Zuschauersport, Segelboot und Schach.
- **Fassung sichtbar im Eye-Band** (ux-ui-designer): Rohwert statt freundlichem Namen.
- Keine Konsultation übersprungen.

## Offene Fragen

Keine.

## Out of Scope

- Neubewertung bestehender Eye-Ergebnisse.
- Umbau des Sidecars (Typwahrscheinlichkeit, `details`).
- Änderungen an Cloud-Ergebnissen, Album-Entwurf, Cloud-Kandidatenauswahl, Feinlabels und den
  übrigen sechs Motiven.
