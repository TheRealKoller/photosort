# 0616 - Klassifizierungsverfahren am Foto vergleichen und beurteilen

**Status:** Accepted
**Erstellt:** 2026-11-07
**Bezug:** [Issue #616](https://github.com/TheRealKoller/photosort/issues/616), ADR
[`0139`](../decisions/0139-pruefung-von-klassifizierungsverfahren-in-der-app.md) (löst ADR 0138
Punkt 8 ab)

**Umfang:** über dem Richtwert von rund 200 Zeilen, weil die Spec Datenmodell, Prüfjob, API,
Oberfläche und die drei Auflagen (Isolation, Export, Cloud-Einwilligung) je vollständig tragen muss;
kein Teil davon ist ohne den anderen prüfbar.

## Ziel

Es ist nicht abschließend geklärt, welche Art der Klassifizierung für PhotoSort am besten taugt. In
der App soll sich deshalb belegt vergleichen lassen, welches von zwei Klassifizierungsverfahren am
Foto das bessere Ergebnis liefert. Verglichen werden können verschiedene Modelle (Cloud gegen Eye,
zwei Cloud-Modelle) und verschiedene Fassungen oder Methoden desselben Modells (alte gegen neue
Eye-Übersetzung). Die Urteile sollen anschließend von der KI ausgewertet werden können, um
nachzuschärfen oder Verfahren gegeneinander abzuwägen.

Diese Story liefert nur das Werkzeug. Die Bestätigung der Verbesserungen aus #615 ist ein späterer,
eigener Prüflauf, der dieses Werkzeug benutzt.

## User Story

Als Nutzer von PhotoSort möchte ich in der App für Fotos eines Projekts die Ergebnisse von zwei
Klassifizierungsverfahren nebeneinander am Foto sehen und beurteilen, welches besser ist. Dafür
sollen auch bereits klassifizierte Fotos eigens für die Prüfung neu klassifiziert werden können,
ohne dass sich die geltenden Ergebnisse ändern. So kann ich belegt entscheiden, welche
Klassifizierung für PhotoSort am besten taugt.

## Akzeptanzkriterien
Auf Testbarkeit geschärft; was Architektur und UI/UX schon festlegen, ist konkreter benannt, nicht neu
entschieden.

- [ ] **Prüfung anlegen.** Jeder der beiden Nutzer kann in einem Projekt eine Prüfung anlegen; der
  anlegende Nutzer wird gespeichert. Eine Prüfung hat genau zwei Seiten `a` und `b` mit je genau
  einem Verfahren; die Seiten müssen sich in mindestens einem Herkunftsmerkmal unterscheiden (`kind`,
  `provider`, `model`, `eye_model_revision`, `eye_mapping_version`) — zwei Fassungen desselben
  Eye-Modells gelten als verschieden, zwei identische Seiten werden abgelehnt. Beide Nutzer sehen
  dieselben Prüfungen des Projekts, ohne Nutzerfilter, und ein zweiter Nutzer kann fremde Prüfungen
  öffnen, beurteilen und ändern. Mehrere Prüfungen je Projekt sind zulässig, solange keine läuft.
  Prüfungen eines anderen Projekts sind über die Route nicht erreichbar (`404`). Die
  Ablehnungsreihenfolge ist Teil der Zusage: `403` (Feature-Schalter aus) → `403` (Eye-Seite bei
  abgeschaltetem Eye) → `404` → `409` (kein erfolgreicher Ausschusslauf, Gate nicht bestätigt, eine
  Prüfung läuft) → `403` (Cloud-Seite ohne Einwilligung) → `503` (Eye-Dienst nicht erreichbar, vor
  dem Einreihen des Jobs) → `422` (zwei identische Seiten, unbekanntes Modell, unbekannte Fassung,
  Prüfgröße außerhalb der Grenzen).
- [ ] **Abgegrenzt von der Bewertungs-Vergleichsansicht.** Auf den Prüfseiten stehen „Prüfung“,
  „Fall“ und „Urteil“; „Vergleich“ und „Bewertung“ stehen dort nicht allein. Kein `RatingButtons`,
  `RatingBadge`, `PhotoCard`, `PhotoGridTile` und kein Bewertungskennzeichen wird auf einer Prüfseite
  gerendert. Die Zifferntasten 1, 2 und 3 lösen dort nichts aus. Die Urteilsflächen tragen weder
  `--accent-2` noch `--danger`. Das Foto der Fallansicht ist kein Link in die Einzelbildansicht. Die
  Route `/compare` existiert weiterhin nicht. Das Nebenziel „Klassifizierung prüfen“ ist der vierte
  Eintrag in `PROJECT_NAV_SECONDARY_TARGETS`, steht nach „Personen“ und ist auf beiden Prüfrouten
  aktiv.
- [ ] **Erneut klassifizieren ohne Wirkung.** Die Prüfmenge sind alle Fotos mit
  `survives_ausschuss()` — ohne Skip-Kriterium. Bereits klassifizierte Fotos sind darin enthalten und
  werden für beide Seiten neu klassifiziert. Nach einer Prüfung sind für jedes Foto unverändert:
  Motiv-Kopfzeile samt `source`, wirksame Motivstärken, Korrekturen, Kriterien-Scores,
  Albumtauglichkeit, Ausschuss- und Qualitätswerte, Rangfolge, Cloud-Vision-Fehlerzeilen, alle
  `photo_eye_*`-Zeilen, `photo_local_motif_snapshot*`, die Fotozeilen selbst und die Kostenspalten
  aller vier Lauf-Tabellen. Ebenso unverändert bleiben die Kandidatenmenge von
  `select_remote_category_candidates` und die Schätzung des nächsten Klassifizierungslaufs. Ein
  normaler Klassifizierungslauf nach einer Prüfung verhält sich wie ohne sie, geprüft an der
  Kostenschätzung, die der Auslöser an den Job übergibt, und an der Kandidatenmenge.
- [ ] **Kosten vor dem Start.** Die Schätzung wird serverseitig je Seite aus der Größe der Prüfmenge ×
  `estimate_usd_per_image(model, provider)` berechnet; sie ist keine Eingabe des Clients, wird beim
  Anlegen neu berechnet und an der Seite eingefroren. Es gilt die bestehende Dreizweigregel von
  `_estimate_part`: unbekannte Menge → `null`, null Fotos → `0.0`, kein Preis hinterlegt → `null`
  (nie `0.0`). Eye und lokal sind kostenfrei und heißen in der Anzeige „kostenfrei“, nie „0,00 USD“.
  Cloud-Verfahren sind nur wählbar, wenn die Projekteinwilligung vorliegt **und** für den Anbieter des
  Modells ein API-Schlüssel hinterlegt ist; Eye nur bei `eye_enabled`; lokal immer. Der Start ist eine
  ausdrückliche Auslösehandlung.
- [ ] **Herkunft erkennbar.** Jede Seite speichert und nennt ihre Herkunft vollständig: Cloud „Cloud ·
  {Anbieter} · Modell {Modell}“, Eye „Eye · {`MODEL_REVISION`} · Übersetzung
  {`eye_mapping_version`}“, lokal „Lokal · ohne Sehenswürdigkeits-Beitrag“. Die Herkunft wird beim
  Anlegen gespeichert, nicht beim Lesen abgeleitet — eine später hinzugefügte Fassung ändert die
  Herkunft einer bestehenden Prüfung nicht. Zwei Fassungen desselben Eye-Modells sind in jeder Ansicht
  und im Export unterscheidbar.
- [ ] **Prüfmenge als Stichprobe der Abweichungen.** Ein Zweck wird für ein Foto nur verglichen, wenn
  **beide** Seiten dazu eine Aussage haben; fehlt eine, ist das Foto für diesen Zweck „nicht
  verglichen“ und zählt weder als übereinstimmend noch als abweichend. Zähl-Einheit: „Motive“,
  „Dokument-Ausschluss“ und „Albumtauglichkeit“ werden in **Fotos** gezählt, „Merkmale“ in
  **(Foto, Motiv)**-Paaren. Eine Abweichung ist: unterschiedliche Motiv-Präsenzmenge (Motive, ein Fall
  je Foto), unterschiedliches `excluded_document`, unterschiedliche `album_level`, bzw. je Motiv mit
  abweichender Präsenz ein Merkmal-Fall. Die Stichprobe wird je Zweck mit dem gespeicherten Seed
  gezogen: `vorgelegt = min(Prüfgröße, Abweichungen)`, bei weniger Abweichungen alle. Gleicher Seed
  und gleiche Abweichungsliste ergeben dieselbe Auswahl, unabhängig von der Zeilenreihenfolge der
  Datenbank. Es gelten `übereinstimmend + abweichend = verglichen` und `vorgelegt = min(Prüfgröße,
  abweichend)` je Zweck; die Übersicht rechnet mit derselben Funktion, die die Stichprobe gezogen hat.
  Die Fotoposition ist 1-basiert und stabil vergeben.
- [ ] **Vergleichsansicht.** Je vorgelegtem Foto zeigt die App das Foto und, offen benannt mit
  A/B-Marke und Herkunftszeile, die Ergebnisse beider Verfahren für alle Fälle dieses Fotos. Ein
  `NULL` einer Seite erscheint als „keine Aussage“, nie als `false` oder `0`. Die Position ist
  1-basiert in Serverreihenfolge; ein ungültiger `?foto=`-Wert führt zum ersten Foto mit offenem Fall.
  Das Setzen eines Urteils ändert weder Position noch Reihenfolge.
- [ ] **Urteil.** Je Fall kann genau eines von vier Urteilen gesetzt werden: `a_better`, `b_better`,
  `both_ok`, `both_wrong`. Es gibt genau **ein** Urteil je Fall, nicht eines je Nutzer: jeder der
  beiden Nutzer kann es setzen und ändern (Upsert, letzter Schreiber gewinnt, `updated_by_user_id`
  und `updated_at` nennen ihn). Ein erneutes Setzen desselben Urteils ändert nichts. Urteile sind nur
  an einer abgeschlossenen (`SUCCESS`) Prüfung möglich; eine laufende oder fehlgeschlagene Prüfung
  antwortet mit `409`, ein fremder oder unbekannter Fall mit `404`. Ein unbekannter Urteilswert wird
  vom Schema abgelehnt (`422`), bevor der Handler ihn sieht. Eine angefangene Prüfung ist später
  fortsetzbar; „offen“ ist die Zahl der Fälle ohne Urteil.
- [ ] **Übersicht in der App.** Je Prüfung zeigt die App: Herkunft beider Seiten, Größe der Prüfmenge,
  Zahl der nicht klassifizierbaren Fotos, und zwei Tabellen — „Abweichungen je Zweck“ (Zweck ·
  übereinstimmend · abweichend · vorgelegt) und „Urteile je Zweck“ (Zweck · A besser · B besser ·
  beide ok · beide falsch · offen), dazu die acht Merkmale als eigene Zeilengruppe mit der Einheit
  „Foto × Motiv“. Ein Zweck ohne gemeinsame Aussage zeigt „nicht verglichen — Seite X trifft dazu
  keine Aussage“ statt Zahlen. Ist `verglichen = 0`, sagt die Seite „keine Fotos verglichen“ und nennt
  die Zahl der fehlgeschlagenen Fotos; sie behauptet **nicht**, die Verfahren stimmten überein. Es
  gibt kein automatisches Gesamturteil und keine Empfehlung: keine Hervorhebung, kein Fettdruck einer
  Spalte, keine Balken, keine Farbe. Die Kosten je Seite erscheinen als „Ist (vor dem Start geschätzt:
  …)“, „kostenfrei“ oder „nicht erfasst“.
- [ ] **Export für die KI.** `GET …/{review_id}/export` liefert JSON mit genau diesem Inhalt: Herkunft
  beider Seiten, Prüfgröße und Seed; Zählungen je Zweck und je Merkmal; Urteilszählungen inklusive
  „offen“; je Fall eine **laufende Fotonummer innerhalb der Prüfung** (keine Foto-Id), den Zweck,
  `motif_key` nur bei Merkmal-Fällen, beide Rohwerte ungerundet und das Urteil oder `null`. Nicht
  enthalten: Bilddaten, Foto-Ids, Pfade, Dateinamen, Zeitstempel, Orte und GPS, Personen- und
  Sehenswürdigkeitsnamen, Projektname, Nutzer und Modellfreitext. Der Dateiname enthält nur die
  Prüfungs-Id. Der Download antwortet `409`, solange die Prüfung nicht `SUCCESS` ist; offene Fälle
  erscheinen in der Datei ohne Urteil. Die Fotonummer des Exports ist dieselbe Zahl, die die
  Fallansicht als Position zeigt.
- [ ] **Löschung mit dem Projekt.** Alle sechs Tabellen (`classification_reviews`, `…_sides`,
  `…_results`, `…_result_strengths`, `…_cases`, `…_verdicts`) werden mit dem Projekt gelöscht; danach
  ist die Zeilenzahl jeder dieser Tabellen für dieses Projekt `0`. Eine Prüfung eines zweiten Projekts
  bleibt vollständig erhalten, `users` ebenfalls. Eine laufende Prüfung sperrt die Projektlöschung mit
  `409` wie die anderen Lauftypen (nur der neueste Lauf zählt) und das Projekt ist danach nachweislich
  unverändert. Nach der Löschung erscheint keine Prüfung irgendwo als geltendes Ergebnis eines Fotos.
- [ ] **Fehlschlag und Stillstand.** Scheitert ein einzelnes Foto, wird es übersprungen und gezählt;
  für dieses Foto entsteht keine Ergebniszeile und kein Fall, die Prüfung läuft weiter und kann
  `SUCCESS` erreichen. Die Detailantwort nennt die Zahl der Fotos ohne Ergebnis auf mindestens einer
  Seite. Die Prüfung wird nie automatisch wiederholt (`max_tries=1`); ein gescheiterter Lauf zeigt die
  Servermeldung ohne „Erneut versuchen“, die bis zum Abbruch angefallenen Ist-Kosten bleiben sichtbar.
  Eine hängende Prüfung setzt der Watchdog nach der Stillstandsschwelle auf `FAILED` und löscht dabei
  ihren Teilschritt. Die Prüfung nimmt als fünfter Lauftyp an `reap_stalled_runs` und
  `_fail_if_stalled` teil; ein Fehler beim Reapen eines anderen Lauftyps verhindert das Reapen der
  Prüfung nicht.

## Datenmodell-Bezug

Sechs neue Tabellen, keine Änderung an einer bestehenden Tabelle (ADR 0139 Punkt 2). Siehe
[`docs/architecture.md`](../../docs/architecture.md), Abschnitt „Datenmodell".

- `classification_reviews`: Projekt, anlegender Nutzer, `ScanStatus`, Teilschritt, Prüfgröße je
  Zweck, Seed, Fotozahlen, `last_progress_at`.
- `classification_review_sides`: Primärschlüssel Prüfung + `a`/`b`; `kind`
  (`cloud|eye|local`), `provider`, `model`, `eye_model_revision`, `eye_mapping_version`, eingefrorene
  `estimated_cost_usd`, Ist-Kosten wie in `remote_category_classification_runs`.
- `classification_review_results` und `classification_review_result_strengths`: je Prüfung, Seite
  und Foto; `excluded_document` und `album_level` nullable (`NULL` = „das Verfahren sagt dazu
  nichts“), alle acht Motive.
- `classification_review_cases`: Prüfung, Foto-Id (intern), **`photo_position`**, Zweck
  (`motifs|motif_feature|excluded_document|album_level`), `motif_key` nur bei `motif_feature`;
  eindeutig je Prüfung, Foto, Zweck und Merkmal.
- `classification_review_verdicts`: Primärschlüssel = Fall, `a_better|b_better|both_ok|both_wrong`,
  `updated_by_user_id`, `updated_at`; ein Urteil je Fall, Upsert, letzter Schreiber gewinnt.

## Architektur / Umsetzung

Grundlage ist ADR [`0139`](../decisions/0139-pruefung-von-klassifizierungsverfahren-in-der-app.md).
Sie löst ADR 0138 Punkt 8 ab („Vergleich ist ein CLI“).

**Ansatz.** Eine Prüfung ist ein eigener Lauf mit eigenen Tabellen. Sie klassifiziert die Prüfmenge
für beide Seiten neu und schreibt ausschließlich in die Prüftabellen. Geltende Ergebnisse,
Album-Entwurf, Kandidatenauswahl und Kostenschätzung des normalen Laufs bleiben dadurch strukturell
unberührt; `select_remote_category_candidates`, `_build_classification_estimate` und
`upsert_assessment` werden nicht angefasst. Das CLI `photosort.eye_comparison` entfällt; seine reine
Vergleichslogik wird zu einem A/B-Vergleich verallgemeinert und von der Prüfung genutzt.

**Vier Prüfzwecke.** `motifs`, `motif_feature`, `excluded_document`, `album_level`. `motifs`,
`excluded_document` und `album_level` zählen Fotos, `motif_feature` zählt Paare aus Foto und Motiv.
Jeder Zweck hat einen eigenen Deckel (`min(Prüfgröße, abweichende Einheiten)`) und eine eigene Zählung
(übereinstimmend, abweichend, vorgelegt); ein Foto mit drei abweichenden Motiven ist damit ein Fall
für `motifs` und drei für `motif_feature`. Verglichen wird ein Zweck je Foto nur, wenn beide Seiten
eine Aussage haben.

**Backend**

- **Datenmodell** (`models.py`, eine Alembic-Revision, Id über `scripts/nummern.py migration
  <slug>`): die sechs Tabellen aus dem Abschnitt „Datenmodell-Bezug“. Der Anzeige-Teilschritt ist ein
  eigener Aufzählungswert in einer `SQLEnum(native_enum=False)`-Spalte; neue Aufzählungswerte
  brauchen damit keine Migration.
- **`classification_comparison.py`** (neu, rein): `motif_present`, `compare_motifs`, Zählung je
  Zweck, `_sample` aus `eye_comparison.py` — A gegen B statt Cloud gegen Eye, `PURPOSES` um
  `motif_feature` erweitert. Feine Merkmale: ein Fall je (Foto, abweichendem Motiv). Sortierung
  `(photo_id, purpose, motif_key)`, seeded je Zweck. Die Übersicht ruft dieselbe Funktion für die
  Zählungen. `eye_comparison.py` und seine Tests entfallen.
- **`eye_mapping.py`**: Fassungstabelle `MAPPING_VERSION → Abbildung` und `analyze(payload,
  version)`; `eye-4.2.3/v1` bleibt unverändert aufrufbar.
- **`remote_classification.py`**: `build_category_classification_client(model)` und die Drosselung
  leiten den Anbieter aus `provider_for_vision_model(model)` ab statt aus
  `settings.landmark_provider`; die Aufrufer im normalen Lauf ziehen mit, für sie ist das
  wirkungsgleich.
- **`classification_review.py`** (neu): Job `run_classification_review`, in
  `WorkerSettings.functions` mit `max_tries=1`. Prüfmenge: `join(PhotoScore)` +
  `survives_ausschuss()`, ohne Skip-Kriterium, einmal geordnet nach `photo_id`. Aus dieser
  eingefrorenen Menge entsteht `photo_position` (laufende Nummer, gespeichert, nicht abgeleitet).
  - **Reihenfolge im Job:** erst die kostenfreien Seiten (eye, dann local), danach die
    kostenpflichtige (cloud). Fällt der Sidecar mitten im Lauf, ist noch nichts bezahlt.
  - **eye:** sequenziell über `build_eye_client`, **ein** Dienstaufruf je Foto; bei zwei Eye-Seiten
    beide Fassungen auf dieselbe Antwort im Speicher.
  - **local:** `_compute_content_criteria` + `local_motif_strengths`, ohne
    Sehenswürdigkeits-Beitrag, ohne Schreiben von `PhotoCriterionScore`.
  - **cloud:** Client des gewählten Modells, Parallelität wie `remote_category_classification_concurrency`,
    Kosten im `finally` eingefroren.
  - Danach Fälle über `classification_comparison` ziehen und speichern. Ein Fotofehler wird
    übersprungen, in `unclassifiable_photo_count` gezählt und für keinen Zweck verglichen. Liefert
    eine Seite auf keinem Foto ein Ergebnis, endet die Prüfung `FAILED` statt mit leerer Übersicht.
  - `reap_stalled_runs`/`_fail_if_stalled` nehmen den neuen Lauftyp auf.
- **`api/classification_reviews.py`** (neu, Router-Auth, Projektbindung nur aus dem Pfad):
  - `GET …/options`: wählbare Verfahren mit `available` und `unavailable_reasons` (`no_consent` vor
    `no_api_key`), Eye-`eye_disabled`, `sample_size {default: 30, min: 1, max: 200}`, dazu die
    wählbaren Eye-Fassungen und Cloud-Modelle.
  - `GET …/estimate`: je Seite Fotozahl × `estimate_usd_per_image`; Eye/lokal `0.0`, Lücken `null`.
  - `POST …`: `403` (Feature-Schalter aus) → `403` (Eye-Seite bei abgeschaltetem Eye) → `404`
    (Projekt unbekannt) → `409` (kein Ausschusslauf, Gate fehlt, Prüfung läuft) → `403` (Cloud-Seite
    ohne Einwilligung) → `503` (Eye-Seite und `eye_service_is_healthy()` falsch, **vor** dem Einreihen
    des Jobs) → `422` (zwei gleiche Seiten, unbekanntes Modell oder Fassung, Prüfgröße außerhalb
    1…200). Danach Schätzung neu berechnen und einfrieren.
  - `GET …`, `GET …/{review_id}` (Status, `phase`, Fortschritt, `photo_count`,
    `unclassifiable_photo_count`, Herkunft beider Seiten, Zählungen je Zweck und Merkmal mit Einheit,
    Urteilszählungen).
  - `GET …/{review_id}/cases`: immer `200`, bei laufender Prüfung leer; sortiert nach
    `(photo_position, Zweck, Merkmal)`, Zweck in der Reihenfolge oben, Merkmal in Registry-Ordnung;
    je Fall Urteil und `updated_by` als `{user_id, username}` aus ausdrücklicher Projektion wie
    `api/photos.py::_participants`.
  - `PUT …/cases/{case_id}/verdict`: `404` (Prüfung oder Fall unbekannt) → `409` (Prüfung nicht
    `SUCCESS`) → Upsert. Ein unbekannter Urteilswert ist `422` aus dem Schema, vor dem Handler.
  - `GET …/{review_id}/export`: `409`, solange die Prüfung nicht `SUCCESS` ist; sonst JSON mit festem
    Schlüsselsatz, je Fall die `photo_position` statt Foto-Id. Bildabruf bleibt beim bestehenden
    Foto-Endpunkt.
- **`project_deletion.py`**: alle sechs Tabellen in `reversed(Base.metadata.sorted_tables)`-Ordnung,
  `tests/project_graph.py` zieht nach; `delete_project` nimmt die laufende Prüfung in die `409`-Sperre
  auf.
- **`api/stats.py`**: Kostenposten `review` aus `classification_review_sides.cost_usd` mit derselben
  Lückenregel (b).

**Frontend**

- `PROJECT_ROUTE_PATHS`: `classificationReviews` = `/projects/:projectId/klassifizierung-pruefen`
  und `classificationReviewDetail` = `/projects/:projectId/klassifizierung-pruefen/:reviewId`; neues
  Nebenziel „Klassifizierung prüfen“ in `PROJECT_NAV_SECONDARY_TARGETS`.
- Seiten: Liste; Anlegen (Verfahrenswahl mit Herkunft, `unavailable_reasons` als Text, Kosten oder
  „kostenfrei“, Prüfgröße vorbelegt aus `options`, ausdrücklicher Start); Fallansicht (Foto, Seite
  A/B offen benannt, vier Urteile je Fall, „n offen“); Übersicht mit Download.
- Fallansicht liest `?foto=` (nur `^\d+$`, 1…`photo_count`), ungültig → erstes offenes Foto per
  `replace`, ohne Serverrunde.
- Neuer Client `api/classificationReviews.ts`; Abgrenzung zur Bewertungs-Vergleichsansicht über Name,
  Pfad und Navigationsplatz (die frühere Route `/compare` gibt es nicht mehr).

**Zu sichernde Invarianten**

- **Isolation (ADR 0139 Punkt 2):** Strukturwächter (keine Importe von
  `upsert_assessment`/Lauf- und Phasenfunktionen, keine Fremdtabelle als Schreibziel) +
  Verhaltenstest (geltende Kopfzeilen, Stärken, Albumtauglichkeit, Kandidatenmenge und Schätzung des
  nächsten Laufs vor/nach einer Prüfung gleich). Bei Verletzung ändern sich geltende Ergebnisse oder
  die nächsten Cloud-Kosten.
- **Export:** fester Schlüsselsatz plus Formwächter; bei Verletzung gelangen Inhaltsangaben an eine
  KI.
- **Cloud nur mit Einwilligung:** Client wird nicht gebaut, wenn keine Cloud-Seite gewählt ist.
- **`updated_by`:** Projektion auf `(user_id, username)`; ein Test hält fest, dass die Fall-Antwort
  kein weiteres `User`-Feld trägt.
- **Sampling-Einheiten:** ein Test hält fest, dass `motifs` je Foto und `motif_feature` je (Foto,
  Motiv) zählt und beide Deckel unabhängig greifen.
- **Kosten vor dem Bezahlen:** bei falschem `eye_service_is_healthy()` wird kein Job eingereiht, und
  im Job laufen die kostenfreien Seiten vor der Cloud-Seite (Reihenfolge über eine injizierte
  Client-Attrappe).
- **Fotoposition:** Fallliste und Export tragen für denselben Fall dieselbe Nummer; die Nummer ist
  gespeichert, nicht zweimal abgeleitet.

**Reihenfolge der Umsetzung** (ein Branch, gestuft, jede Stufe für sich grün)

1. Datenmodell, Migration, Löschung, Lösch-Sperre, Watchdog.
2. Anbieter aus dem Modell ableiten (Refactor ohne Verhaltensänderung) und Fassungstabelle in
   `eye_mapping.py`.
3. `classification_comparison.py` aus `eye_comparison.py` herauslösen, CLI entfernen.
4. Prüfjob mit den drei Seitenarten, Seitenreihenfolge, Fallziehung samt `photo_position`,
   Isolationswächter und Verhaltenstest.
5. API inklusive Options, Fehlerreihenfolge mit `503`, Schätzung, Urteil, Export und Kostenposten in
   der Statistik.
6. Frontend inklusive `?foto=`.
7. Doku (`docs/architecture.md`, Kopfvermerk ADR 0138).

**Top-Level-Schlüssel des Exports (fest, Gleichheitstest):** `review` (`sample_size`, `seed`,
`photo_count`, `counts_by_purpose`), `sides` (`a`, `b` mit `kind`, `provider`, `model`,
`eye_model_revision`, `eye_mapping_version`), `verdict_counts`, `cases` (je Eintrag `photo_position`,
`purpose`, `motif_key`, `a`, `b`, `verdict`). Kein weiterer Schlüssel auf keiner Ebene.

**Job-Meldungen:** `error_message` einer Prüfung enthält ausschließlich feste deutsche Sätze aus
einer geschlossenen Menge; `str(exc)` fremder Systeme wird nie übernommen. Fotofehler werden gezählt,
nicht als Text gespeichert.

## UI/UX

Grundlage sind ADR [`0139`](../decisions/0139-pruefung-von-klassifizierungsverfahren-in-der-app.md)
und das Design-System [`0004`](../architecture/0004-design-system.md). Einen Penpot-Entwurf gibt es
nicht; dieser Abschnitt ist bis dahin maßgeblich.

### Navigation und Abgrenzung

- **Neues Nebenziel „Klassifizierung prüfen“** als letzter Eintrag in
  `PROJECT_NAV_SECONDARY_TARGETS`, nach „Personen“. Es ist aktiv auf `classificationReviews` und
  `classificationReviewDetail`. Sichtbarer Text und zugänglicher Name sind gleich.
- **Abgrenzung zur Bewertung.** Die Prüfseiten haben eigenes Vokabular, eigene Bedienelemente und
  eigene Tasten:
  - Nirgends steht „Vergleich“ oder „Bewertung“ allein; es heißt „Prüfung“, „Fall“ und „Urteil“.
  - Auf den Prüfseiten stehen weder `RatingButtons` noch `RatingBadge`, `PhotoCard` oder
    `PhotoGridTile`, auch kein Bewertungskennzeichen.
  - Die Ziffern 1, 2 und 3 lösen hier nichts aus („gleiche Taste macht immer dasselbe“).
  - Die Urteile tragen keine Bewertungsfarben (kein `--accent-2`, keine `--danger`-Fläche).
  - Das Foto der Fallansicht ist kein Link in die Einzelbildansicht.
- **Eine Begriffsquelle.** Die vier Urteile, die drei Zwecke und „Merkmal: {Motivname}“ (Motivname aus
  `formatMotifKey`) kommen aus `utils/classificationReviewLabels.ts`, nie aus Literalen an der
  Aufrufstelle.

### Herkunft einer Seite (gilt auf allen Prüfseiten)

- **Kennung.** Jede Seite trägt eine neutrale Buchstabenmarke „A“ bzw. „B“: Kästchen `--overlay`,
  `font-mono text-xs`, `rounded-xs`. Keine Seitenfarbe — A und B unterscheiden sich nur über den
  Buchstaben.
- **Herkunftszeile**, immer vollständig, nie gekürzt (`break-words` statt `truncate`), weil zwei
  Fassungen sich oft nur am Ende unterscheiden:
  - Cloud: „Cloud · {Anbieter} · Modell {model}“
  - Eye: „Eye · {eye_model_revision} · Übersetzung {eye_mapping_version}“, darunter die bestehende
    `EyeAttribution`
  - Lokal: „Lokal · ohne Sehenswürdigkeits-Beitrag“
- **Fremdtext** (Anbieter-, Modell- und Fassungsnamen) ausschließlich als React-Textknoten.

### Seite 1: Liste und Anlegen (`/projects/:projectId/klassifizierung-pruefen`)

- **Kopf.** `h1` „Klassifizierung prüfen“, darunter der dauerhafte Satz in `text-sm text-text`: „Zwei
  Klassifizierungsverfahren am Foto gegenüberstellen und beurteilen. Die geltenden Ergebnisse der
  Fotos bleiben dabei unverändert.“ Rechts `Button` „Neue Prüfung anlegen“ (Standard) mit
  `aria-expanded`/`aria-controls`; er öffnet das Anlegen-Panel inline unter dem Kopf, keinen Dialog.
  Bei leerer Liste ist das Panel von Anfang an offen.
- **Liste.** Neueste zuerst, jede Zeile ein Link auf die Übersicht, mindestens 44 px hoch
  (`min-h-11`), die Zeile ist die Trefferfläche.
  - Erste Zeile: Datum und Uhrzeit, „angelegt von {Nutzer}“.
  - Darunter die Herkunft A und B mit Marke.
  - Rechts der Stand: `StatusTag` „läuft…“ oder „fehlgeschlagen“, sonst „{n} von {m} Fällen offen“,
    „alle beurteilt“ oder „keine Abweichungen“.
- **Anlegen-Panel** (`rounded-lg border border-border bg-surface p-4`), Muster „Wegwahl ohne
  Vorgabe“:
  - **Zwei `fieldset`s** „Seite A“ und „Seite B“ mit vollbreiten Radio-Zeilen (`min-h-11`), **keine
    Vorauswahl**. Je Zeile der Name als Herkunftszeile, darunter „kostenfrei“ (als Wort, nie „0,00
    USD“) oder „Cloud · kostenpflichtig“. Cloud-Modelle nach Anbieter gruppiert, Eye eine Zeile je
    Fassung; Inhalte aus `GET …/options`.
  - Fehlt eine Option, steht der Grund aus `unavailable_reasons` als Satz an der Stelle der Gruppe
    („keine Cloud-Einwilligung im Projekt“, „für keinen Cloud-Anbieter ist ein API-Schlüssel
    hinterlegt“).
  - **Prüfgröße** als Zahlenfeld „Prüfgröße je Zweck“, vorbelegt mit `sample_size.default`, mit
    `min`/`max` aus `options`; darunter „Weichen mehr Fotos ab, wird zufällig ausgewählt.“
  - **Kostenvorschau**, erst wenn beide Seiten gewählt sind, dauerhaft vor dem Auslöser (kein
    Bestätigungsdialog), im Muster der bestehenden `ClassificationEstimate`: eine Zeile je Seite
    („Seite A: kostenfrei“ / „Seite B: 1,23 USD für 412 Fotos“), Gesamtzeile, bei unbekanntem Preis
    der bestehende Hinweis.
  - Auslöser `Button` „Prüfung starten“ (Standard); deaktiviert ohne beide Seiten und während des
    Sendens.
- **Zustände:** leer (Panel offen), läuft, fehlgeschlagen (`Alert` mit dem festen Satz und
  „erneut anlegen“), keine Abweichungen (Panel bleibt bedienbar, Hinweis „die beiden Verfahren stimmen
  auf allen Fotos überein“).

### Seite 2: Detail mit Fallansicht und Übersicht

- **Kopf.** Herkunft A und B als zwei Blöcke nebeneinander; darunter Fortschritt „{n} offen von {m}“,
  `unclassifiable_photo_count` (nur wenn > 0, als Satz) und bei Fehlschlag der `Alert`.
- **Fallansicht.** Zweispaltig ab `sm:`, sonst untereinander: links das Foto (bestehende
  Bildkomponente, kein Link), rechts die Fallliste.
  - Je Fall ein Block: Zweck als Überschrift, bei feinen Merkmalen „Merkmal: {Motivname}“, darunter
    zwei Zeilen mit Seitenmarke und Rohwert (`ja`/`nein` für Motive und Dokument-Ausschluss, die
    Albumstufe als bestehender Text; „keine Aussage“, wenn die Seite nichts dazu sagt).
  - **Urteile** als Radiogruppe aus vier `min-h-11`-Schaltflächen je Fall in der Reihenfolge „A
    besser“, „B besser“, „beide ok“, „beide falsch“; gesetztes Urteil trägt `aria-pressed`-Zustand
    und zusätzlich den Namen des Schreibers („von {Nutzer}“), wenn vorhanden. Tastatur: `A`, `B`,
    `O`, `F` setzen das Urteil des markierten Falls, wenn der Fokus nicht in einem Textfeld liegt und
    kein Modifier gedrückt ist; die Kästchen neben den Schaltflächen nennen die Taste. Danach springt
    die Markierung zum nächsten offenen Fall desselben Fotos.
  - **Foto wechseln** über `?foto=<Position>` (vor/zurück, „offen“-Sprung); die Position ist die
    laufende Nummer, das Label zeigt „Foto {n} von {photo_count}“.
- **Übersicht.** Zwei Tabellen statt einer breiten (kein waagerechtes Scrollen bei 360 px), jede
  Zählung mit ihrer Einheit im Spaltenkopf:
  - „Abweichungen“ für die drei fotozählenden Zwecke (Motive, Dokument-Ausschluss, Albumtauglichkeit)
    mit „Fotos“ als Einheit: übereinstimmend · abweichend · vorgelegt.
  - Eigene Zeilengruppe „Merkmale (Foto × Motiv)“ mit derselben Zählung und der Einheit „Paare“.
  - „Urteile“ je Zweck: A besser · B besser · beide ok · beide falsch · offen; darunter
    `verdict_counts` gesamt. Ein Zweck ohne gemeinsame Aussage zeigt „nicht verglichen — Seite X
    trifft dazu keine Aussage“; bei `verglichen = 0` steht „keine Fotos verglichen“ mit der Zahl der
    fehlgeschlagenen Fotos. Kein Gesamturteil, keine Empfehlung.
- **Download.** `Button` „Für die KI exportieren“ lädt die Datei über den authentifizierten
  Blob-Weg; darunter der Satz, was die Datei nicht enthält (Bilddaten, Dateinamen, Orte, Namen).
- **Zustände:** läuft (Fortschritt nach Teilschritt `side_a|side_b|cases`, Filter für Urteile
  gesperrt), fehlgeschlagen, alle Fälle beurteilt (Hinweis, Download bleibt).
- **Barrierefreiheit:** Seitenmarken und Urteile mit zugänglichem Namen, Fokusring wie üblich,
  Statusmeldungen in einer `aria-live`-Region, Kontrast wie im Design-System; die Herkunftszeile
  bricht um statt abzuschneiden (dokumentierte Abweichung für schmale Geräte).

**Design-System:** keine Ergänzung nötig. Verwendet werden bestehende Muster (Wegwahl ohne Vorgabe,
dauerhaft sichtbare Kostenschätzung, StatusTag, Alert, Tabellen) und die bestehenden Tokens.

## Security

Sicherheitsrelevant, kein Blocker. Die Prüfung führt **keine neue Vertrauensgrenze** ein: gleicher
Cloud-Anbieter, gleicher `eye`-Dienst, eigene Tabellen, beide Nutzer unverändert die vertrauenswürdige
Basis. Neu sind ein Schreibpfad auf gemeinsame Urteile, ein Endpunkt mit geschlossener
Verfahrenswahl und der **erste Datei-Download des Produkts**. Fortschreibung von
[`0003`](../architecture/0003-securitykonzept.md) in dessen Angriffsflächen-Zeilen „Das Vergleichs-CLI“
(entfällt), „REST-API“ (neuer Router) und „Cloud-Vision-API“ (Modell je Seite).

- **S1 — Ein Urteil ist Projektdatum, kein Nutzerdatum.** `updated_by_user_id` ist ein **Auditfeld,
  nie ein Zugriffsschlüssel**: geschrieben ausschließlich aus `current_user.id`, gelesen nur zur
  Anzeige „von {Nutzer}“, nie als Aufsuch- oder Filterbedingung. `VerdictIn` trägt genau ein Feld; ein
  geschmuggeltes `user_id`/`updated_at` bleibt wirkungslos. Kein Grund für Nutzerfilterung — beide
  Nutzer beurteilen dasselbe Urteil, das ist die entschiedene Produktlinie.
- **S2 — Projektbindung ist eine UND-Bedingung in derselben Anweisung.** `review_id` wird zusammen
  mit `project_id` aufgelöst, `case_id` über einen Join `cases → reviews`. Fremd- oder Zufallswerte
  ergeben `404` (wortgleich „nicht gefunden“), nie `403` — ein `403` wäre ein Inhalts-Orakel. Keine
  Prüfungs-, Fall- oder Foto-Id aus Body oder Query. `GET …/cases` darf die `photo_id` tragen (Fotos
  sind für beide Nutzer sichtbar), aber nur für Fälle dieser Prüfung im Projekt.
- **S3 — Der Export ist eine Positivliste, keine Ausblendliste.** Der Serialisierer baut aus einem
  ausdrücklich typisierten Zeilenobjekt, nie aus ORM-Objekten, `__dict__` oder `model_dump()`.
  Zulässig ist ausschließlich die Schlüsselmenge aus `## Architektur / Umsetzung`. Ausgeschlossen
  bleiben Bilddaten, Foto-Ids, Dateinamen, Pfade, alle Zeitstempel, Orte/GPS, Personen-,
  Sehenswürdigkeits- und Projektnamen, Nutzer, Modellfreitext und jede `error_message`. Die Datei
  entsteht nur im Antwortkörper.
- **S4 — Download-Header ohne Nutzereingabe.** `Content-Type: application/json; charset=utf-8`,
  `Content-Disposition: attachment; filename="klassifizierungspruefung-<review_id>.json"` (die Zahl der
  Prüfungs-Id, sonst Literal), `X-Content-Type-Options: nosniff`, `Cache-Control: no-store`. Das
  Frontend lädt über `apiFetchBlob` (Bearer) und `URL.createObjectURL` mit `revokeObjectURL`; kein
  `<a href>`, kein Token in der URL.
- **S5 — Cloud nur mit Projekteinwilligung, ohne stillen Rückfall.** `Project.cloud_vision_detection_enabled`
  wird an drei Stellen geprüft: `options` bietet ohne Einwilligung keine Cloud-Zeile, `POST` antwortet
  `403`, der Job prüft unmittelbar vor der Client-Konstruktion erneut. Kein Abbilden auf Eye oder
  Lokal. Eine Eye-Seite setzt `settings.eye_enabled` voraus, ebenfalls ohne Ersatzweg.
- **S6 — Verfahrenswahl ist eine geschlossene Eingabe, der Anbieter folgt serverseitig.** `kind` ist
  `cloud|eye|local` ohne Vorgabe; `model` muss in `VISION_MODELS_BY_PROVIDER` stehen und einen
  hinterlegten Schlüssel haben; `provider` wird ausschließlich über `provider_for_vision_model(model)`
  abgeleitet und so persistiert — ein `provider`-Feld aus dem Client existiert nicht.
  `eye_mapping_version` muss ein Schlüssel der Fassungstabelle sein. Zwei effektiv gleiche Seiten
  ergeben `422` vor jedem Schreibvorgang. Der Ziel-Host bleibt im Code fest (kein SSRF über ein
  Modellfeld).
- **S7 — Kein Schlüssel, keine Infrastruktur in Antwort, Meldung oder Log.** `options` nennt Gründe,
  keine Variablennamen; Meldungen sind feste Sätze; `error_message` trägt nie `str(exc)` eines fremden
  Systems; der Export führt keine Fehlermeldung.
- **S8 — Kosten entstehen serverseitig und sind gedeckelt.** Die Schätzung wird beim Start neu
  berechnet und eingefroren; `ReviewCreate` trägt kein Betrags-, Preis-, Anbieter- oder Kostenfeld.
  `null` heißt „nicht schätzbar“, nie „kostenlos“. Ist-Kosten schreibt allein der Job (`finally`).
  Eine laufende Prüfung je Projekt (`409`), `max_tries=1`. **Kein neues Rate-Limit**: die
  bestehende, akzeptierte Risikoklasse („ein gestohlenes JWT löst bezahlte Läufe aus“) deckt den Fall,
  ein Limit wäre neue Mechanik ohne neue Schutzwirkung.
- **S9 — Eingabevalidierung vor jedem Schreibvorgang.** Prüfgröße strikt ganzzahlig in
  `1..sample_size.max`; `0`, negativ, zu groß, Kommazahl, Zeichenkette, `true` und fehlendes Feld
  ergeben `422`, ohne dass eine Zeile entsteht. `review_id`/`case_id` sind Pfad-Ganzzahlen, das Urteil
  ein geschlossener `Literal`.
- **S10 — Kein neuer Endpunkt ohne Torwächter.** `dependencies=[Depends(get_current_user)]` am
  `APIRouter` **und** Eintrag in der handgepflegten Router-Liste von
  `tests/test_auth_guard.py::_protected_router_operations()`.
- **S13 — Der Eye-Kanal bleibt der bestehende, auch bei zwei Eye-Seiten.** Nur `display`-Bytes ohne
  Pfad, Dateiname oder Kopfzeile; bei zwei Fassungen **ein** Dienstaufruf je Foto; keine Rohantwort
  gespeichert. Zwei Eye-Seiten sind kein zweiter Empfänger.

Ohne Befund bleiben Auth-Modell, JWT, CORS/CSRF, Secrets-Pfade, OpenCloud-Schreibzugriff, Bilddaten im
Repository und die Sichtbarkeit der übrigen Projektdaten.

## Teststrategie

Grundlage ist [`0002`](../architecture/0002-testkonzept.md). Neue Ebenen entstehen nicht: Backend
`pytest` (Unit und Integration gegen die echte In-Memory-SQLite), Frontend `vitest`, E2E nur für
Geometrie. Die Prüfung ist der erste Job des Projekts, der **ausschließlich in eigene Tabellen
schreiben darf** — deshalb tragen zwei Wächter, die einander nicht vertreten: ein Strukturwächter über
den Syntaxbaum und ein Verhaltenstest über den Bestand.

- **Unit (`test_classification_comparison.py`, DB-frei):** `motif_present`/`compare_motifs` gegen
  `selection.motif_is_present` (keine zweite Schwelle), die Zweigdeckung „nur vergleichen, wenn beide
  Seiten eine Aussage haben“, die Zählung je Zweck samt Merkmalen, `_sample` (Grenze, Seed,
  Sortierung).
- **Unit (`test_eye_mapping.py`):** die Fassungstabelle liefert für jede eingetragene Fassung ein
  Ergebnis; `eye-4.2.3/v1` liefert wertgleiche Ausgaben wie vor dem Umbau; eine unbekannte Fassung
  scheitert statt still auf die Vorgabe zurückzufallen.
- **Unit (`test_remote_classification.py`):** der Anbieter des Kategorie-Clients folgt aus dem Modell,
  nicht aus `settings.landmark_provider` — mit gepatchten Client-Klassen und gepatchtem
  `throttle_for_provider` (kein Netz, kein Secret).
- **Integration Job (`test_worker_classification_review.py`):** Prüfmenge ohne Skip-Kriterium, alle
  drei Seitenarten, Eye genau einmal je Foto bei zwei Eye-Seiten, Anbieter aus dem Modell,
  Einzelfoto-Fehler, Kosten im `finally`, Fälle ziehen, `max_tries=1`.
- **Integration API (`test_api_classification_reviews.py`):** `options`, `estimate`, Anlegen mit der
  Prüfreihenfolge `404 → 409 → 403 → 503 → 422`, Liste/Detail/Fälle/Urteil/Export, Projektbindung nur
  über den Pfad, beide Nutzer sehen und schreiben dasselbe.
- **Integration Bestand (`test_project_deletion.py`, `project_graph.py`, `test_api_projects.py`,
  `test_api_stats.py`):** die sechs Tabellen fallen mit dem Projekt, der Datengraph wächst um sie, die
  Prüfung ist der fünfte Lauftyp der `409`-Sperre, der neue Kostenposten folgt der bestehenden
  Lückenregel.
- **Integration Watchdog (`test_worker_reap_stalled_runs.py`):** eine Prüfung wird gereapt, ihr
  Teilschritt gelöscht, andere Lauftypen unabhängig davon.
- **Frontend (`vitest`):** `utils/classificationReviewLabels.ts` als reine Konstanten (Urteile,
  Zwecke, Merkmal-Label); die vier Seiten als Komponententests über Rollen und `aria-*` (Liste und
  Anlegen inklusive Sperrgründe, Übersicht inklusive Zählungstabellen und Export-Sperren, Fallansicht
  inklusive Urteilsleiste, markiertem Fall und Tastatur); `App.test.tsx` und
  `utils/projectRoutes.test.ts` (vier Nebenziele, beide Routen real geroutet);
  `designSystem.contract.test.ts` (A/B-Marke ohne Farbe, keine Hervorhebung im Urteilsblock).
- **E2E (`e2e/`):** ausschließlich Geometrie und CSS auf einer geseedeten, abgeschlossenen Prüfung —
  zwei Spalten ab `lg`, eine darunter, mitlaufende Kopfleiste ohne verdeckte Fotoüberschrift,
  `object-contain`-Inhaltsrechteck frei, 44-px-Treffer der vier Urteilsflächen bei 360 px, kein
  waagerechtes Scrollen bei 360 px. Kein E2E-Spec löst den Job aus; die Prüfung wird im Demo-Seeder
  als Ergebnis angelegt.
- **Rot-Nachweis:** die Isolationswächter, der Export-Formwächter und jeder Layout-Spec werden einmal
  mutwillig verletzt und rot belegt — ein Wächter, der nichts findet, ist immer grün.

### Edge Cases

1. **Isolation geltender Ergebnisse.** Vorher/Nachher-Vergleich über den gesamten Bestand:
   `photo_motif_assessments` (inklusive `source`), `photo_motif_strengths`, `photo_motif_corrections`,
   `photo_criterion_scores`, `photo_album_suitability`, `photo_scores`, `photo_rankings`,
   `photo_cloud_vision_errors`, `photo_eye_results`/`_motif_strengths`/`_fine_labels`,
   `photo_local_motif_snapshot(_strengths)`, `photos.*` sowie `api_calls`/`failed_calls`/`cost_usd` der
   vier Lauf-Tabellen. Dazu `GET /projects/{id}`, `GET …/classification/estimate` und die
   Kandidatenmenge von `select_remote_category_candidates`. Gegentest „normaler Lauf nach Prüfung ==
   normaler Lauf ohne Prüfung“ über zwei Projekte mit gleicher Fixture (Vergleich der
   `estimated_cost_usd`, die der Auslöser an den Enqueuer übergibt).
2. **Stichprobe und Seed.** Genau an der Grenze (`Abweichungen == Prüfgröße`), eins darüber, eins
   darunter, `Prüfgröße = 1`, null Abweichungen (kein Fall, kein Fehler). Gleicher Seed → gleiche
   Auswahl bei vertauschter Einfügereihenfolge der Zeilen; zwei verschiedene Seeds liefern bei genug
   Abweichungen verschiedene Auswahlen (sonst prüft der Test den Seed nicht). Die Auswahl wird
   zusätzlich als Literalliste `(Fotonummer, Zweck, motif_key)` gepinnt.
3. **`NULL`-Aussagen.** Alle vier Kombinationen je Zweck: beide `NULL` → nicht verglichen; eine Seite
   `NULL`, andere `false`/`0` → nicht verglichen, keine Abweichung; beide `false` → verglichen,
   übereinstimmend; `false` gegen `true` → Abweichung. Lokal gegen Cloud ergibt für Ausschluss und
   Album `verglichen = 0` (nicht „alle Fotos weichen ab“) und für Motive normale Zahlen; gemischt (nur
   einige Fotos ohne Aussage) ergibt `verglichen < Fotos`, die fehlenden Fotos erscheinen in keiner der
   beiden anderen Zahlen.
4. **Fehler bei einzelnen Fotos.** Ein Foto scheitert auf einer Seite → übersprungen, gezählt, keine
   Ergebniszeile für diese Seite, kein Fall für das Foto, Prüfung endet `SUCCESS`; die übrigen Fotos
   sind vollständig. Ein Foto scheitert auf beiden Seiten → einmal gezählt. Alle Fotos scheitern →
   `SUCCESS` mit `verglichen = 0`, und die Übersicht sagt „keine Fotos verglichen“.
5. **Watchdog.** `last_progress_at` älter als die Schwelle → `FAILED`, Teilschritt `NULL`; exakt auf
   der Schwelle → nicht gereapt; innerhalb → nicht gereapt; ein Fehler beim Lesen einer anderen
   Lauf-Tabelle verhindert das Reapen der Prüfung nicht; ein bereits über die erste Schicht
   gescheiterter Lauf wird nicht angefasst; Ist-Kosten bleiben lesbar.
6. **Löschung.** Zeilenzählung je sechs Tabellen nach `DELETE`, zweites Projekt unverändert, `users`
   unverändert, `409` je Lauftyp einzeln mit Nachweis „Projekt unverändert“ (nicht nur „kein 204“),
   Altlauf `RUNNING` blockiert nicht, zweiter `DELETE` → erneut `404`.
7. **Exportschlüssel.** Der Schlüsselsatz wird literal gepinnt (oberste Ebene und je Fall); ein
   Syntaxbaum-Wächter über den Serialisierer verbietet jede Attributlesung auf Foto-Id, Pfad,
   Dateiname, Zeitstempel, Ort/GPS, Personen- und Sehenswürdigkeitsnamen, Projektname, Nutzer und
   `reason`/Feinlabel-Text — mit Gegenprobe. Dazu die Marker-Technik: in jede verbotene Spalte wird
   eine einprägsame Zeichenfolge geschrieben und deren Abwesenheit im serialisierten JSON geprüft.
   Fotonummer: bei Foto-Ids ab 1000 steht `1..n`; dieselbe Nummer für alle Fälle eines Fotos; die
   Nummer ist identisch mit der Position der Fallansicht.
8. **Tastenschutz.** A/B/O/F schreiben am markierten Fall; mit Strg/Meta/Alt nicht (insbesondere
   `Strg+A` schreibt nicht „A besser“, `Strg+F` nicht „beide falsch“); bei Fokus in einem Textfeld
   nicht; die Ziffern 1/2/3 lösen weder Urteil noch Bewertung aus. Nach einem Urteil springt die
   Markierung zum nächsten offenen Fall desselben Fotos und wechselt nie das Foto; ein zweiter
   Tastendruck während des Speicherns erzeugt keinen zweiten Request; die Pfeiltasten wechseln das
   Foto und setzen den Fokus auf die Fotoüberschrift.

## Testkonzept-Vorschlag

[`0002`](../architecture/0002-testkonzept.md) wird ergänzt, nicht ersetzt. Vorschlag für den Backend-
Teil, dazu drei Nachträge: die Zahl der Lauftypen der `409`-Sperre wächst von vier auf fünf, die
Sektion zu `eye_comparison.py` bekommt einen Kopfvermerk (Modul und Tests entfallen mit ADR 0139), die
E2E-Spec-Tabelle eine Zeile für die Prüfseite (Navigation, kein waagerechtes Scrollen und
Trefferflächen werden dort um die neue Route ergänzt, nicht abgeschwächt).

Grund für den neuen Abschnitt: Die Prüfung ist der erste Job, dessen Zusage eine **Schreibgrenze** ist.
Sie hat keinen Rot-Zustand, den ein Verhaltenstest allein einnehmen könnte, und keinen Fehlercode, der
sie meldet. Acht Muster:

1. **Die Schreibgrenze wird über die Form geprüft, nicht über ein Verhalten** — `write_statements()` je
   Modul plus eine Ziel-Allowlist der Modelle in den Schreibaufrufen, gegen die sechs Prüfmodelle.
   Gegenprobe in beide Richtungen; die Allowlist wird aus dem Modulimport abgeleitet, nicht als
   Zeichenkettenliste abgeschrieben.
2. **Ein Namenswächter für verbotene Aufrufe, weil ein Import-Wächter hier blind ist:** die verbotenen
   Funktionen liegen im selben Modul wie der neue Job. Geprüft wird der aufgerufene Name über
   `ast.Call` (Attribut und blanker Name), mit Positiv- und Negativ-Gegenprobe.
3. **Der Strukturwächter allein genügt nie.** Ein Schreibpfad hinter einem nicht betretenen Zweig ist
   ihm unsichtbar. Der Verhaltenstest snapshotet den gesamten Bestand, der geltende Ergebnisse trägt,
   und vergleicht Zeile für Zeile; die Fehlermeldung nennt die verletzte Tabelle.
4. **„Verhält sich wie ohne“ ist eine Aussage über einen zweiten Lauf, nicht über den Zustand.**
   Geprüft wird die Kostenschätzung, die der Auslöser an den Enqueuer übergibt, und die Kandidatenmenge
   — gegen ein Zwillingsprojekt ohne Prüfung, nicht gegen eine abgeschriebene Zahl.
5. **Eine verallgemeinerte Zufallsauswahl wird gegen das alte Werkzeug gepinnt, solange beide
   existieren:** `_sample` zieht um; ein Test vergleicht für dieselbe Abweichungsliste und denselben
   Seed die Auswahl und wird mit dem alten Modul gelöscht. Dauerhafter Rest ist die Literalliste.
6. **Ein Export, der keine Kennung tragen darf, ersetzt sie durch eine Ordnungszahl — und die Bindung
   dieser Zahl ist selbst ein Test.** Geprüft wird die Gleichheit der Nummer aus Export und Fallansicht
   aus einer Fixture, dazu dass sie bei lückenhaften Foto-Ids bei `1` beginnt. Die Marker-Technik gilt
   unverändert; der Syntaxbaum-Wächter bekommt zusätzlich die Attributendungen `relative_path`,
   `taken_at`, `latitude`/`longitude`, `display_name` auf `fine_labels` und die Lesung von
   `Project.name` und `User.*`.
7. **Ein Vergleich hat drei Ausgänge, nicht zwei:** „nicht verglichen“ darf weder als Übereinstimmung
   noch als Abweichung zählen. Pflichtfall ist der mit **einer** fehlenden Seite; bei zwei fehlenden
   Seiten ist das Ergebnis auch mit einer naiven Implementierung richtig. Dazu die Invarianten
   `übereinstimmend + abweichend = verglichen` und `vorgelegt = min(Prüfgröße, abweichend)` über jeder
   Fixture.
8. **Tastenkürzel, die mit Browserkürzeln kollidieren, werden als Partition geprüft:** ohne Modifier →
   schreibt; mit Strg/Meta/Alt → schreibt nicht, kein Request; Fokus in einem Textfeld → schreibt
   nicht; im schreibenden Fall setzt die Taste genau ihr Urteil und lässt die anderen drei unberührt.

Für die E2E-Sektion zusätzlich ein Aufnahmekriterium: Ein Feature, dessen Seite ein Ergebnis eines
Hintergrundjobs zeigt, wird im Demo-Seeder als **Ergebnis** angelegt, nie durch einen ausgelösten Job.

## Entscheidungen

- `architect` konsultiert (Schritt 1): eigenes Lauf- und Tabellenmodell, Anbieter aus dem Modell,
  Fassungstabelle, CLI-Entfall; ADR 0139 angelegt, ADR 0138 Punkt 8 im Kopf als teilweise abgelöst
  vermerkt.
- `ux-ui-designer` konsultiert (Schritt 2): Navigation, Inline-Panel, Fallansicht mit Tastatur,
  Buchstabenmarken statt Farben, Begriffsquelle.
- `test-engineer` konsultiert (Schritt 3): Akzeptanzkriterien auf Testbarkeit geschärft (Zähl-Einheiten
  Fotos bzw. Foto × Motiv, Prüfreihenfolge, `409` an nicht abgeschlossener Prüfung, Fehlschlag und
  Stillstand); Testkonzept wird um einen Abschnitt ergänzt, nicht ersetzt.
- `security-engineer` konsultiert (Schritt 3): S1–S10, S13; kein neues Rate-Limit, `photo_id` in der
  Fall-Antwort erlaubt.
- Aus dem Refinement übernommen: ein gemeinsames Urteil je Fall, Stichprobe der Abweichungen,
  Kostenanzeige vor dem Start, Zwecke **und** feine Merkmale, Übersicht plus Export, keine Wirkung auf
  geltende Ergebnisse.
- Selbst entschieden (unterhalb der Produktschwelle): Prüfgröße 1…200 mit Vorgabe 30 und ohne stille
  Kappung; `photo_position` wird gespeichert statt gerechnet; `?foto=` wird clientseitig aufgelöst;
  `unavailable_reasons` ist eine geordnete Liste; beide Seiten werden immer neu klassifiziert (kein
  Wiederverwenden geltender Ergebnisse als Seite); `NULL` statt `false` für Ausschuss und Album bei
  der lokalen Seite; Cloud-Prüfkosten als eigener Statistikposten; CLI entfernt statt behalten.
- Bewusst **nicht** entschieden: eine Kadenz oder Tageskostengrenze für Prüfungen. Für die Abnahme
  nicht nötig; die bestehende akzeptierte Risikoklasse deckt den Fall. Wenn gewünscht, eigene Story.

## Offene Fragen

- keine

## Out of Scope

- Der Bestätigungslauf zu #615 (eigene Story; braucht diese Story und #615).
- Eine Prüfung, die vorhandene geltende Ergebnisse als eine Seite wiederverwendet.
- Löschen einzelner Prüfungen (mit dem Projekt verschwinden sie).
- Export in einem anderen Format als JSON, automatische Deutung oder Empfehlung durch die App.
- Ein neues Rate-Limit oder eine Kostengrenze für Prüfläufe.
- Eigene Einstellungen für Prüfläufe (Skip-Kriterium, Sehenswürdigkeits-Phase der lokalen Seite).
- Die Lücke aus 0609 (geschlossene Augen, verdeckte Gesichter) als eigener Prüfzweck.
