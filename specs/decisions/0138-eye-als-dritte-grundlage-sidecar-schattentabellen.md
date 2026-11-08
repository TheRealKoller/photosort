# 0138 - Eye als dritte Klassifizierungsgrundlage: eigener Sidecar, Schattentabellen, Rangfolge der Grundlagen

**Status:** Accepted
**Teilweise abgelöst:** Punkt 8 (Vergleich als CLI ohne Endpunkt) durch ADR
[`0139`](./0139-pruefung-von-klassifizierungsverfahren-in-der-app.md); Punkt 3 (Motivstärke nur
aus Tags) für das Motiv Tiere durch ADR
[`0140`](./0140-eye-uebersetzung-v2-lauf-fassung-tiererkennung-fassung-je-ergebnis.md); Punkt 6
(Laufwahl `cloud`/`eye`/`local`) und Punkt 7 (Kostenvorschau je Modus) durch ADR
[`0143`](./0143-modellwahl-je-projekt-und-taetigkeit.md); alle übrigen Punkte gelten weiter.
**Datum:** 2026-11-03
**Bezug:** Issue [#609](https://github.com/TheRealKoller/photosort/issues/609), Spec
[`0606`](../features/0606-eye-lokaler-cloud-ersatz-bewerten.md) (ihr Auswertungsweg wird durch
diese Entscheidung abgelöst), ADR
[`0091`](./0091-motive-mit-staerke-statt-hauptkategorie.md) (Kopfzeile und Motivstärken, hier
dreiwertig erweitert), ADR
[`0095`](./0095-albumtauglichkeit-vom-modell-qualitaet-getrennt-vom-inhalt.md) (Albumtauglichkeit
getrennt vom Inhalt), ADR
[`0033`](./0033-modell-asset-download-statt-commit-label-embedder.md) (gepinnte Modell-Assets),
ADR [`0062`](./0062-projektloeschung-als-metadatengeordnete-mengenloeschung.md) (Löschumfang), ADR
[`0116`](./0116-fortschritt-und-restdauer-am-klassifizierungslauf.md) (Teilschritte der
Fortschrittsanzeige)

**Umfang:** über dem Richtwert von rund 100 Zeilen, weil Schreibpfad, Leseregel, Kostenweg und
Rückbau in einem Zug festgelegt werden müssen — vier Stellen, die auseinanderlaufen, sobald man
sie auf mehrere Entscheidungen verteilt.

## Kontext

Motivstärken, Dokumentausschluss, Albumtauglichkeit und Feinlabels entstehen heute in zwei
Schreibpfaden: dem lokalen Kriterien-Lauf (nur Motivstärken, `source='local'`) und der
Remote-Kategorie-Klassifizierung (`source='cloud'`). Eye (Desert Ant Labs, lokales TFLite-Modell)
soll dieselben vier Aussagen auf dem Heimserver liefern, als dritte Laufwahl neben „Cloud" und
„nur lokal" — kein Ersatz: Cloud-Ergebnisse bleiben gültig, Eye-Ergebnisse werden für den Vergleich
aufbewahrt, und ein Ausbau muss ohne Datenverlust möglich sein. Der bisher geplante
Auswertungsweg (eigenes Werkzeug mit Paarvergleichsseiten, Spec 0606) entfällt.

## Entscheidung

### 1. Eye läuft als eigener Node-Sidecar im Compose-Netz, nicht im Worker-Image

Neuer Baum `eye/` (eigenes npm-Projekt, eingechecktes `package-lock.json`, exakter Pin
`@desert-ant-labs/eye@4.2.3`, `Dockerfile` auf `node:22-bookworm-slim` — das native Binary braucht
`libcurl.so.4`). Dienst `eye`, Port `8090`, **kein** veröffentlichter Port, Lauf als `node`-Nutzer,
keine Datenbank, keine Geheimnisse, kein Zugriff auf `photo_cache`. Er ersetzt `tools/eye-eval/`
vollständig; Werkzeug und CI-Job entfallen.

Das Backend-Image ist `python:3.12-slim`; ein zweiter Node-Stack darin vergrößerte jedes
Worker-Image und gäbe dem Fremdpaket Worker-Rechte (Datenbank, Cache, Redis), ein Subprozess je
Foto wäre weder begrenzbar noch beobachtbar. Der Sidecar hält das Modell einmal geladen; der
Rückbau ist „Dienst und Baum löschen".

Das Backend erreicht ihn nur im Compose-Netz (`EYE_SERVICE_URL`, Vorgabe `http://eye:8090`). Der
Dienst steht in `docker-compose.yml` hinter `profiles: ["eye"]`: ohne Profil startet ihn niemand,
Prüf- und Demo-Stacks bauen ihn nicht. `EYE_ENABLED` (Vorgabe `false`) ist der app-seitige
Schalter: bei `false` lehnt die API `mode=eye` mit `403` ab, die Oberfläche bietet zwei Wege an.
**Was gilt:** beide Schalter müssen zusammenpassen. **Wo:** `.env` und `docker-compose.yml`. **Bei
Verletzung:** `EYE_ENABLED=true` ohne gestarteten Sidecar endet im sichtbaren `503` des Auslösers,
nie in einem stillen Rückfall.

Vertrag, mehr nicht: `GET /health` (200 erst, wenn Pins geprüft und Modell geladen sind) und
`POST /analyze` mit den rohen Bytes der `display`-Variante, Antwort ist die SDK-Analyse als JSON.
Der Sidecar rechnet **keine** Motive: er liefert `tags` (Tag-Konfidenzen), `faces`, `pets`, `scores`,
`details.layout.shot`, `kind`, `model` unverändert. Verarbeitung ist sequenziell (ein Modell, eine
Anfrage), Aufrufe laufen über `httpx` mit fester Zeitgrenze; die Eye-Phase ist deshalb bewusst
nicht nebenläufig.

### 2. Gewichte und Pins liegen außerhalb von Repository und Image

`eye.tflite` und `eye_meta.json` werden nie eingecheckt und nie ins Image gebacken. Sie liegen im
Volume `eye_model`, einmalig gefüllt über den Einmal-Dienst `eye-model` (Profil `eye-setup`,
`node src/fetch-model.js`). Revision (`v1.0.0`), Commit-SHA und beide SHA-256 stehen als
Konstanten in `eye/src/pins.json`, nach dem Muster von `model_assets.py`: kein Env-Wert, kein
Build-Argument.

**Was gilt:** der Sidecar prüft beide Dateien bei **jedem** Start gegen die Pins und lädt nichts
nach. **Wo:** `eye/src/model.js` vor dem ersten `analyze`. **Bei Verletzung:** Start bricht ab,
`/health` bleibt ungleich 200, Eye gilt als nicht verfügbar. Ein Modellwechsel ist ein neuer Pin
plus neuer `model_revision`-Wert in den Ergebniszeilen, kein stiller Wechsel unter bestehenden
Daten.

Lizenz: `DAL_APP_ID=photosort` ist im Image fest gesetzt; ist `DAL_LICENSE_ENDPOINT` oder
`HF_TOKEN` gesetzt, verweigert der Dienst den Start. `HOME` liegt auf dem Volume `eye_home`, damit
die Zählkennung (Install-ID) Neustarts übersteht. Die Lizenzprüfung des SDK wird nicht
deaktiviert, nicht blockiert, nicht umgeleitet. Das SDK kontaktiert ausschließlich
`events.desertant.com` (Metadaten, keine Bilder); **erzwungen ist das nicht** — die Durchsetzung
bleibt Betreiberpflicht des Heimservers, benannt wie in Spec 0606 (S21).

### 3. Die Abbildung Eye → Motiv, Ausschluss, Albumstufe, Feinlabel lebt in Python

Neues reines Modul `backend/src/photosort/eye_mapping.py`, Port von `mapping.js` und `signals.js`
des entfallenden Werkzeugs: je Motiv die Stärke als größte Konfidenz der zugeordneten Tags (0..1,
alle acht Motive, nicht genannt = `0.0`), `excluded` aus `excludedTypes`, Albumstufe 1–5 aus
`scores.aesthetic` in festen Bändern, Feinlabels als stärkste Tags ab 0.5. Es steht neben
`motifs.py` und importiert nur die Standardbibliothek.

Der Node-Teil bleibt dumm, weil die Tabelle sonst zweimal existierte und die Vergleichsseite eine
andere benutzte als der Lauf. **Was gilt:** genau eine Tabelle `EYE_PURPOSE_MAPPING` im
Repository. **Wo:** `eye_mapping.py`, mit Tag-Abgleich gegen `eye_meta.json` als Test. **Bei
Verletzung:** ein Pin-Wechsel ohne Nachprüfung der Tabelle liefert still Nullen für verschwundene
Tags.

### 4. Schattentabellen statt Umbau der Cloud-Pfade; Rangfolge cloud > eye > lokal

Eye schreibt bei **jedem** Eye-Lauf für jedes analysierte Foto einen vollständigen Satz in eigene
Tabellen — auch dann, wenn für das Foto ein Cloud-Ergebnis gilt:

- `photo_eye_results` (`photo_id` PK und FK auf `photos`, `excluded_document: bool` NOT NULL
  **ohne Default**, `album_level: int` 1–5, `model_revision: str`, `computed_at`)
- `photo_eye_motif_strengths` (FK auf `photo_eye_results.photo_id`, `Unique(photo_id, motif_key)`)
- `photo_eye_fine_labels` (FK auf `photo_eye_results.photo_id`, roher Eye-Tag als Text,
  `confidence`, `Unique(photo_id, label)`)

In `photo_motif_assessments` schreibt Eye nur, wenn dort **keine** oder eine **lokale** Kopfzeile
steht; eine Cloud-Kopfzeile bleibt unberührt. `MotifAssessmentSource` bekommt den dritten Wert
`eye` (`SQLEnum(native_enum=False)`, kein Migrationsschritt für den Wertebereich). Die Regel steht
in `motif_strengths.py::upsert_assessment` als Rangfolge `local < eye < cloud`, nicht in der
Reihenfolge der Teilschritte.

**Was gilt:** Eye schreibt **nie** in `photo_album_suitability`, nie in `photo_fine_labels`, nie in
`fine_labels`. **Wo:** der Eye-Schreibpfad im Worker. **Bei Verletzung:** die Album-Entwurfsmenge
(liest ausschließlich `photo_album_suitability`, ADR 0095) und die Cloud-Kandidatenauswahl
(`source == CLOUD` **und** Albumtauglichkeit) verschöben sich still — Eye veränderte dann den
nächsten Cloud-Lauf, was ausgeschlossen ist.

Eye's Albumstufe und Feinlabels sind deshalb **eigene Anzeige**: `PhotoOut.eye_result` (Albumstufe,
Feinlabels, `model_revision`, `computed_at`) ist genau dann gesetzt, wenn die Kopfzeile
`source='eye'` trägt. Feinlabels bleiben getrennt, weil das Vokabular ein anderes ist als das der
geschlossenen Cloud-Registry; eine erzwungene Zuordnung wäre eine Aussage, die das Modell nicht
getroffen hat. Der Ausschluss steht dagegen in der Kopfzeile und wird nicht doppelt geführt.
Korrekturen (`photo_motif_corrections`) fasst kein Eye-Pfad an: sie hängen am Foto und überdauern
jeden Eye-Lauf.

### 5. Der lokale Vektor bleibt als Rückbaudaten erhalten

Verdrängt Eye eine lokale Kopfzeile, wandert deren Vektor vorher in
`photo_local_motif_snapshots` (+ `photo_local_motif_snapshot_strengths`, Zeilenform wie die
Motivstärken). Trifft ein späterer Lauf „nur lokal" ein Foto mit Eye-Kopfzeile, ersetzt er nichts,
sondern schreibt seinen frischen lokalen Vektor in den Schnappschuss. Ein erneuter Eye-Lauf
überschreibt den Schnappschuss **nicht** mit Eye-Werten.

**Was gilt:** zu jedem Foto mit Eye-Kopfzeile existiert höchstens ein Schnappschuss, und er trägt
den jüngsten lokalen Vektor. **Wo:** Worker (Eye-Phase und lokale Kopfzeilen-Schleife). **Bei
Verletzung:** der Rückbau kann das lokale Ergebnis nicht wiederherstellen, und das Foto fiele nach
dem Ausbau auf „noch nicht klassifiziert" zurück, obwohl es eines hatte.

### 6. Laufwahl: `mode` ersetzt `use_cloud`; Eye ist ein eigener Teilschritt; kein Rückfall

`ClassifyRequest.use_cloud: bool` wird durch `mode: Literal["cloud", "eye", "local"]` **ohne
Vorgabe** ersetzt (sauberer Schnitt, das Frontend zieht im selben PR mit); `CriterionScoringRun`
bekommt die Spalte `mode` (nullable — Altzeilen). `403` für `mode=cloud` ohne Einwilligung bleibt.
`mode=eye` prüft vor dem Einreihen `GET /health` und antwortet ohne gesunden Sidecar `503` mit
deutscher Meldung; es gibt **keinen** Rückfall auf einen anderen Modus.

Neu ist `ClassificationPhase.EYE` zwischen `remote_categories` und `criteria`. Sie steht **vor** der
Kriterien-Phase, damit Rangfolge, Event-Bildung und Auswahlvorschlag desselben Laufs schon den
wirksamen Vektor lesen; die lokale Kopfzeilen-Schleife dort überschreibt sie nicht, sondern schreibt
ihren Vektor als Schnappschuss (Punkt 5). Die Phase läuft nur bei `mode=eye`, verarbeitet die
Ausschuss-Überlebenden sequenziell und schreibt in **einer** Transaktion am Phasenende:
Schattenzeilen für alle, Kopfzeilen-Promotion für die Fotos ohne Cloud-Kopfzeile. Scheitert die
Phase (Sidecar weg, Pins, Transport), endet der Lauf `FAILED` mit Meldung und ohne jede Promotion —
bestehende Ergebnisse bleiben unberührt. Ein einzelnes unlesbares Bild bricht die Phase nicht ab:
es wird übersprungen und am Lauf gezählt gemeldet (Muster der Cloud-Fehlerzählung), damit ein
defektes Foto Eye nicht dauerhaft blockiert.

Fortschritt: der Lauf bekommt `eye_photos_processed`/`eye_photos_total` (Muster `persons_*`);
`_phase_progress` und die Schrittableitung im Frontend kennen den neuen Wert.

`cloud_requested` bleibt die Aussage „in diesem Lauf ist überhaupt Cloud-Kontakt angefordert":
`mode='cloud'` oder (`mode='eye'` **und** Einwilligung). Die Landmark-Phase hängt weiter an
`use_cloud and project.cloud_vision_detection_enabled`; die Remote-Kategorie-Phase läuft
ausschließlich bei `mode='cloud'`.

Der arq-Job behält seinen alten vierten Positionsparameter (`use_cloud`, jetzt `bool | None`) und
bekommt `mode` keyword-only; fehlt `mode`, wird er aus `use_cloud` abgeleitet — derselbe Grund wie
bei `estimated_cost_usd`: ein zum Deploy-Zeitpunkt bereits eingereihter Job darf nicht an der
Signaturänderung scheitern. Neue Aufrufe übergeben `mode` als Schlüsselwort, damit ein noch
laufender **alter** Worker den Job sichtbar mit `TypeError` verwirft, statt die Zeichenkette `"eye"`
als wahrheitswertige Cloud-Freigabe zu lesen.

### 7. Kostenvorschau je Modus

`GET .../classify/estimate?mode=` liefert die Anteile des **gewählten** Modus: `cloud` beide wie
heute, `eye` nur den Landmark-Anteil (ohne Einwilligung keinen — kostenfrei), `local` keinen. Der
Antwortkörper trägt `mode`; ein Anteil, der nicht stattfindet, ist `null`, und der Aufrufer
unterscheidet „findet nicht statt" von „nicht schätzbar" an der von ihm angefragten `mode` und der
projektweiten Einwilligung (beide ihm bekannt). `estimated_cost_usd` ist die Summe der
stattfindenden Anteile — bei `local` und bei `eye` ohne Einwilligung also `0.0`, das ist die
Anzeige „kostenfrei". Der Parameter hat die Vorgabe `cloud` (= bisheriges Verhalten) für ein noch
gecachtes Frontend-Bundle; er ist ein Leseweg, keine Laufentscheidung. Der Auslöser reicht als
`estimated_cost_usd` weiterhin `None` durch, wenn kein Cloud-Kontakt stattfindet.

### 8. Der Vergleich ist ein CLI, kein Endpunkt

`python -m photosort.eye_comparison --project-id N [--seed S] [--out DATEI]` liest
`photo_motif_assessments` (`source='cloud'`) samt Stärken, `excluded_document` und
`photo_album_suitability.level` gegen `photo_eye_*`, zählt je Zweck (Motiv bei Schwelle 0.5,
Ausschluss, Albumstufe) Übereinstimmungen und Abweichungen und zieht daraus eine seeded
Zufallsauswahl von mindestens 30 Abweichungen je Zweck (oder alle). Feinlabels werden nicht
verglichen. Ausgegeben werden Foto-Ids und der App-Pfad `/projects/{id}/photos/{photo_id}`; auf
stdout stehen nur Zählungen, Details in die Datei `--out` (außerhalb des Repos). Kein Endpunkt,
keine Schreiboperation, kein Gesamturteil.

Ein Endpunkt erzwänge eine zweite, dauerhaft zu pflegende Darstellung derselben Zahlen und trüge
die Vergleichslogik in die Anwendung; die Auswertung ist #610 und bleibt Werkzeug.

### 9. Anzeige: Herkunft, Namensnennung, Lizenzhinweis

`MotifAssessmentOut.source` und die Frontend-Typen kennen `eye`; die Fotoansicht zeigt die Herkunft
der geltenden Motivstärken als `cloud`/`eye`/`lokal`, bei `eye` zusätzlich den Eye-Block
(Albumstufe, Feinlabels). „Powered by Desert Ant Labs" mit Link steht dort, wo Eye wählbar ist und
wo Eye-Ergebnisse erscheinen (Muster der GeoNames-Nennung in `ProjectListPage.tsx`). Vor dem ersten
Eye-Lauf erklärt die Oberfläche, dass Eye eine nicht abschaltbare Lizenzmeldung mit Zählkennung,
aber ohne Bildinhalte sendet.

### 10. Rückbau in einem Schritt

Der Ausbau selbst ist eine eigene Story; diese ADR legt den Weg fest, den sie gehen muss. Eine
Migration stellt für jedes Foto mit `source='eye'` den Schnappschuss als `source='local'`
wieder her (oder löscht die Kopfzeile, wenn keiner existiert), lässt Cloud-Kopfzeilen,
Albumtauglichkeit, Feinlabels und Korrekturen unangetastet und löscht danach die Eye- und
Schnappschusstabellen. `mode`, das Enum-Mitglied `eye`, die Laufwahl, der Sidecar, der Baum `eye/`,
`EYE_SERVICE_URL`/`EYE_ENABLED` und die Namensnennung fallen mit demselben PR. **Was gilt:** kein
Foto zeigt danach eine Eye-Herkunft. **Wo:** die Rückbau-Migration. **Bei Verletzung:** Eye-Zeilen
blieben als Waise zurück, und die Oberfläche zeigte eine Herkunft, die es nicht mehr gibt.

## Konsequenzen

- **`project_deletion.py`** nimmt die Eye- und Schnappschusstabellen auf; der
  Vollständigkeitswächter gegen `Base.metadata` fängt ein Vergessen (ADR 0062).
- **CI:** der Job `eye-eval` entfällt; neuer Job `eye` mit `npm ci`, unmittelbar gefolgt von
  `npm audit signatures`, plus `npm test`. `scripts/tests/test_signaturpruefung_je_paketsatz.py`
  leitet die Paketsätze aus `git ls-files` ab und macht den Job ohne das Schritt-Paar rot;
  `scripts/tests/test_backend_ci_beschleunigung.py` führt die Jobnamen als feste Liste
  (`JOB_SCHLUESSEL`) und wird mit umbenannt.
- **`docs/architecture.md`**, **`docs/setup.md`** und **README** (Projektstruktur) bekommen Dienst,
  Env-Variablen, Modell-Beschaffung, Tabellen und die Annahme zum nicht erzwungenen Egress.
- **Spec 0606** trägt danach den Vermerk, dass ihr Auswertungsweg abgelöst ist.
- **Kein Cloud-Risiko und keine neuen Kosten im Eye-Lauf ohne Einwilligung.** Eye ist Beta; ein
  Modell-Update gilt unter der dann aktuellen Lizenz.
