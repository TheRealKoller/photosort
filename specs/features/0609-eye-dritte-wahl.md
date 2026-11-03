# 0609 - Eye als dritte Laufwahl: Sidecar, Rangfolge der Grundlagen, Vergleich zur Cloud

**Status:** Accepted
**Erstellt:** 2026-11-03
**Bezug:** Issue [#609](https://github.com/TheRealKoller/photosort/issues/609), ADR
[`0138`](../decisions/0138-eye-als-dritte-grundlage-sidecar-schattentabellen.md)

**Umfang:** über dem Richtwert von rund 200 Zeilen, weil Schreibpfad, Leseregel, Kostenweg,
Anzeige, Löschkette und Rückbau derselben Daten in einer Spec beieinanderstehen müssen — verteilt
auf mehrere Dokumente liefen Rangfolge und Rückbau auseinander.

## Ziel

Motivstärken, Dokumentausschluss, Albumtauglichkeit und Feinlabels liefert heute nur die Cloud. Das
kostet Geld, setzt eine Einwilligung voraus und hängt an fremden Diensten. Das lokale Bildmodell
„Eye" (Desert Ant Labs) kommt als dritte Wahl beim Klassifizierungslauf dazu, neben „Cloud" und
„nur lokal", und liefert diese vier Aussagen auf dem Heimserver. Seine Ergebnisse werden den
Cloud-Ergebnissen derselben Fotos gegenübergestellt, damit belegt entschieden werden kann, ob Eye
bleibt oder wieder ausgebaut wird.

Damit wird der Auswertungsweg aus Spec
[`0606`](./0606-eye-lokaler-cloud-ersatz-bewerten.md) (eigenes Werkzeug mit
Paarvergleichsseiten) abgelöst. Die Lizenz ist für die private Nutzung zu zweit als „klar zulässig"
eingestuft; ihre Auflagen sind die nicht abschaltbare Lizenzmeldung mit Zählkennung, aber ohne
Bildinhalte, und die sichtbare Namensnennung. Die Modelldateien gehören weder ins Repository noch in
ein öffentlich verteiltes Image.

## User Story

Als Betreiber von PhotoSort möchte ich bei jedem Klassifizierungslauf zwischen „Cloud", „Eye" und
„nur lokal" wählen. Eye soll Motivstärken, Dokumentausschluss, Albumtauglichkeit und Feinlabels auf
dem Heimserver liefern, und ich möchte seine Ergebnisse den Cloud-Ergebnissen derselben Fotos
gegenübergestellt sehen. So kann ich belegt entscheiden, ob Eye bleibt oder wieder ausgebaut wird.

## Akzeptanzkriterien

- [ ] **Laufwahl.** Der Auslöser bietet genau drei Radio-Zeilen („Cloud", „Eye", „Nur lokal") in
      einem `fieldset` mit `legend`; beim ersten Rendern ist keine gewählt, der Auslöser ist gesperrt
      und nennt die Begründung. `POST …/classify` ohne `mode` → `422`, `mode` mit unbekanntem Wert →
      `422`. `mode=cloud`/`mode=local` erzeugen dieselbe Phasenfolge, dieselben Cloud-Gates und
      dieselbe eingefrorene Schätzung wie `use_cloud=true/false` heute.
- [ ] **Eye auch ohne Einwilligung wählbar.** `ProjectOut.eye_available=true` → genau drei Zeilen,
      unabhängig von `cloud_vision_detection_enabled`; `POST … {mode:"eye"}` ohne Einwilligung →
      `202`.
- [ ] **Eye ohne Einwilligung: kein Cloud-Kontakt, keine Namen, kostenfrei.** Aufrufzähler von
      Vision- und Remote-Kategorie-Client bleiben `0`; `PhotoLandmarkDetection`/`LandmarkName`
      bleiben zeilenlos; `GET …/classify/estimate?mode=eye` liefert `remote_categories` und
      `landmark` je `{candidate_count: null, estimated_cost_usd: null}`, `candidate_count: 0`,
      `estimated_cost_usd: 0.0`; die Vorschau zeigt „kostenfrei" als Wort, nie „0,00 USD".
- [ ] **Eye mit Einwilligung.** Nur die Landmark-Phase läuft, über dieselbe Kandidatenmenge wie
      heute (`criteria.is_landmark_candidate` + `survives_ausschuss()`); der
      Remote-Kategorie-Client wird nie gebaut. `?mode=eye` liefert `remote_categories` zweifach
      `null` und `landmark` wie heute; die Vorschau nennt nur die Sehenswürdigkeits-Zeile.
      `cloud_requested=true`, `cloud_phases` enthält genau `landmark`.
- [ ] **Vollständigkeit.** Je überlebtem, lesbarem Foto genau eine `photo_eye_results`-Zeile
      (`excluded_document` ohne Default, `album_level ∈ 1..5`, `model_revision`), genau acht
      `photo_eye_motif_strengths` (Schlüssel = `MOTIF_REGISTRY`, nicht genannter Tag → `0.0`),
      `photo_eye_fine_labels` nur mit `confidence >= 0.5`.
- [ ] **Cloud gilt weiter.** Eine Cloud-Kopfzeile bleibt nach einem Eye-Lauf unverändert in
      `source`, `excluded_document`, allen acht Stärken, `provider`, `computed_at`; Schattenzeilen
      existieren daneben; `PhotoOut.eye_result == null`, `motif_assessment.source == "cloud"`.
- [ ] **Keine Wirkung auf den nächsten Cloud-Lauf.** `select_remote_category_candidates()` liefert
      vor und nach dem Eye-Lauf dieselben `photo_id`s; `?mode=cloud` liefert gleiche
      `candidate_count`/`estimated_cost_usd`; die Cloud-Zählung in `GET …/stats` bleibt gleich.
- [ ] **Rangfolge `local < eye < cloud`.** Keine Kopfzeile → Eye schreibt. Lokale Kopfzeile → Eye
      verdrängt sie, ihr Vektor liegt danach im Schnappschuss. Eye-Kopfzeile → Eye überschreibt sich
      selbst, der Schnappschuss bleibt. Cloud-Kopfzeile → keine Kopfzeile wird geschrieben.
      `mode=local` bei Eye-Kopfzeile: die Kopfzeile bleibt `eye`, der frische lokale Vektor geht in
      den Schnappschuss (höchstens eine Zeile je Foto); ein zweiter Eye-Lauf ändert ihn nicht, ein
      Cloud-Lauf ersetzt die Kopfzeile und lässt ihn stehen. `photo_motif_corrections` bleibt
      unverändert.
- [ ] **Kein Album-Entwurf.** `photo_album_suitability`, `photo_fine_labels`, `fine_labels`:
      Zeilenzahlen vor und nach dem Eye-Lauf gleich; die Antwort von `GET …/draft-alternatives` ist
      für beide Nutzer unverändert.
- [ ] **Herkunft.** `MotifAssessmentOut.source` serialisiert `"eye"`; die Grundlagenzeile trägt
      `data-motif-source` ∈ {`cloud`, `eye`, `local`}; Eye-Zweig „Grundlage: Eye-Auswertung,
      {Zeitpunkt}", auch in der schreibgeschützten Kachel-Fassung.
- [ ] **Namensnennung und Lizenz.** `EyeAttribution` (Text „Powered by Desert Ant Labs",
      `href="https://desertant.com"`, `rel="noreferrer"`, `target="_blank"`) an genau drei Stellen:
      unter der Eye-Zeile der Laufwahl, unter der Grundlagenzeile bei `source='eye'`, unter dem
      Eye-Band. Der Lizenzsatz steht in **beiden** Eye-Fassungen des Umfangssatzes, ist nicht
      schließbar und übersteht Moduswechsel wie Neuladen.
- [ ] **Nicht verfügbar.** Reihenfolge der Ablehnungen: `category_selection_enabled=false` → `403`;
      `EYE_ENABLED=false` + `mode=eye` → `403` mit eigenem, vom Consent-`403` unterscheidbarem
      `detail`, **vor** jedem Projektzugriff; unbekanntes Projekt → `404`; die drei `409` wie
      heute; `mode=cloud` ohne Einwilligung → `403`; Schalter an, Health ≠ 200 → `503` innerhalb
      der Anfrage, kein Job eingereiht. UI: `Alert` mit `detail` und dem Satz, dass nicht gestartet
      und nichts verändert wurde; die Auswahl bleibt auf Eye; `503` trägt „Erneut versuchen", `403`
      nicht; nach einem Start ist die Auswahl geleert. Bricht der Dienst im Lauf weg → Lauf
      `FAILED`, Teilschritt fehlgeschlagen, keine Promotion.
- [ ] **Rückbau** (eigene Story). Die Migration stellt je `source='eye'` den Schnappschuss als
      `local` her bzw. löscht die Kopfzeile; Cloud, lokal, Album, Feinlabels und Korrekturen bleiben
      unverändert; danach keine `source='eye'`-Zeile, keine Eye-Tabelle, kein `mode`, kein
      `eye_available`, keine Namensnennung.
- [ ] **Vergleich.** `python -m photosort.eye_comparison --project-id N [--seed S] [--out DATEI]`:
      stdout nur Zählungen; feste Schlüsselmenge **ohne** Urteilsfeld; je Zweck (Motiv bei Schwelle
      0.5 inklusiv, Ausschluss, Albumstufe) Übereinstimmungen, Abweichungen und `min(30,
      Abweichungen)` Zeilen mit `photo_id` und `/projects/{id}/photos/{photo_id}`; Feinlabels nicht
      verglichen; gleicher Seed → gleiche Auswahl; `--out` innerhalb des Repos wird abgelehnt (Exit
      ≠ 0, keine Datei); keine Schreiboperation; kein Dateiname und keine Bilddaten in der Ausgabe.
- [ ] **0606 und Werkzeug.** `tools/eye-eval/` und CI-Job `eye-eval` entfallen; Job `eye` (`npm
      ci`, `npm audit signatures`, `npm test`, Arbeitsverzeichnis `eye`) tritt an seine Stelle;
      `JOB_SCHLUESSEL` in `scripts/tests/test_backend_ci_beschleunigung.py` nennt `eye`; der
      Signaturwächter findet `eye/package-lock.json` über `git ls-files`. Spec 0606 trägt den
      Ablösungsvermerk.

## Datenmodell-Bezug

Neu (ADR [`0138`](../decisions/0138-eye-als-dritte-grundlage-sidecar-schattentabellen.md)):

- `photo_eye_results` (`photo_id` PK/FK auf `photos`, `excluded_document: bool` NOT NULL **ohne**
  Default, `album_level: int` 1–5, `model_revision: str`, `computed_at`)
- `photo_eye_motif_strengths` (`Unique(photo_id, motif_key)`)
- `photo_eye_fine_labels` (roher Eye-Tag, `confidence`, `Unique(photo_id, label)`)
- `photo_local_motif_snapshots` (Rückbaudaten, `Unique(photo_id)`) und
  `photo_local_motif_snapshot_strengths`

Geändert: `photo_motif_assessments.source` bekommt `eye` (`MotifAssessmentSource.EYE`,
`native_enum=False`); `criterion_scoring_runs` bekommt `mode` (nullable, Altzeilen bleiben `NULL`)
und `eye_photos_processed`/`eye_photos_total`. `provider` bleibt bei `source='eye'` `NULL` — Eye ist
kein Cloud-Anbieter, ein Wert behauptete einen Kontakt, der nicht stattfand; die Modellrevision
steht in `photo_eye_results`.

`project_deletion.py` nimmt alle neuen Tabellen auf; die Löschkette hängt an `photos` → `projects`
(ADR [`0062`](../decisions/0062-projektloeschung-als-metadatengeordnete-mengenloeschung.md)).
[`docs/architecture.md`](../../docs/architecture.md) ist fortgeschrieben.

## Architektur / Umsetzung

**Ein neuer Dienst, zwei Schalter, ein sauberer Schnitt.** Eye läuft als eigener Node-Container
`eye` (Baum `eye/`, Port `8090`, kein veröffentlichter Port, kein Zugriff auf Datenbank oder
`photo_cache`) im Compose-Netz; er ersetzt `tools/eye-eval/` samt CI-Job. Das Compose-Profil `eye`
hält ihn aus jedem Standard-`up` heraus, `EYE_ENABLED` (Vorgabe `false`) hält die Laufwahl aus der
Anwendung heraus. Beide müssen zusammenpassen: `true` ohne gesunden Dienst endet im sichtbaren
`503`, nie in einem stillen Rückfall. Die Gewichte liegen im Volume `eye_model`, einmalig gefüllt
über den Einmal-Dienst `eye-model` (`--profile eye-setup`), geprüft gegen die SHA256-Konstanten in
`eye/src/pins.json` bei **jedem** Start; `GET /health` antwortet erst danach `200`. `POST /analyze`
nimmt die Bytes der `display`-Variante und gibt die SDK-Analyse unverändert zurück — der Dienst
rechnet keine Motive.

**Abbildung in Python, nicht im Dienst.** `backend/src/photosort/eye_mapping.py` (reines Modul,
Standardbibliothek) bildet die SDK-Ausgabe auf die acht Motivstärken (0..1), den Dokumentausschluss,
die Albumstufe 1–5 und die Feinlabels (stärkste Tags ab 0.5) ab. Genau eine Zuordnungstabelle im
Repository; ein Test gleicht ihre Tags gegen `eye_meta.json` ab, damit ein Pin-Wechsel nicht still
Nullen liefert.

**Laufwahl statt Checkbox.** `ClassifyRequest.use_cloud: bool` wird durch
`mode: Literal["cloud", "eye", "local"]` **ohne Vorgabe** ersetzt, `criterion_scoring_runs.mode`
friert die Wahl ein. `403` für `mode=cloud` ohne Einwilligung bleibt; `mode=eye` prüft vor dem
Einreihen `/health` und antwortet sonst `403` (Schalter aus) bzw. `503` (Dienst weg) mit deutscher
Meldung. Der Lauf bekommt den Teilschritt `eye` zwischen `remote_categories` und `criteria` —
**vor** der Kriterien-Phase, damit Rangfolge, Events und Auswahlvorschlag desselben Laufs schon den
wirksamen Vektor lesen. Die Phase verarbeitet die Ausschuss-Überlebenden sequenziell und schreibt in
**einer** Transaktion am Phasenende: Schattenzeilen für alle analysierten Fotos,
Kopfzeilen-Promotion nur für Fotos ohne Cloud-Kopfzeile. Scheitert sie, endet der Lauf `FAILED` ohne
jede Promotion; ein einzelnes unlesbares Bild wird übersprungen und gezählt, nicht phasenfatal.
Fortschritt über `eye_photos_processed`/`_total` nach dem Muster von `persons_*`.

**Rangfolge.** `local < eye < cloud` steht in `motif_strengths.py::upsert_assessment`, nicht in der
Reihenfolge der Teilschritte, und meldet zurück, ob geschrieben wurde. Verdrängt Eye eine lokale
Kopfzeile, wandert deren Vektor vorher in den Schnappschuss. Eye schreibt **nie** in
`photo_album_suitability`, `photo_fine_labels` oder `fine_labels`: die Album-Entwurfsmenge (ADR
[`0095`](../decisions/0095-albumtauglichkeit-vom-modell-qualitaet-getrennt-vom-inhalt.md)) und die
Cloud-Kandidatenauswahl bleiben unberührt.

**Lesen.** `PhotoOut.eye_result` ist genau dann gesetzt, wenn die Kopfzeile `source='eye'` trägt
(Albumstufe, Feinlabels, `model_revision`, `computed_at`); `MotifAssessmentOut.source` kennt `eye`;
`ProjectOut.eye_available` kommt allein aus `EYE_ENABLED` — nie aus einer Lebendprüfung, sonst
würde das Laden der Projektliste zur Erreichbarkeitssonde. `GET …/classify/estimate?mode=` liefert
Cloud beide Anteile, Eye nur den Landmark-Anteil, lokal keinen; nicht stattfindende Anteile sind
`null`, `estimated_cost_usd` ist die Summe der stattfindenden Anteile (also `0.0` = kostenfrei).

**Vergleich ohne Endpunkt.** `python -m photosort.eye_comparison --project-id N [--seed S]
[--out DATEI]` liest Cloud-Kopfzeilen samt Stärken, `excluded_document` und
`photo_album_suitability.level` gegen `photo_eye_*`, zählt je Zweck Übereinstimmungen und
Abweichungen und benennt mindestens 30 seeded ausgewählte Abweichungen (oder alle) mit Foto-Id und
App-Pfad. stdout nur Zählungen, Details in eine Datei außerhalb des Repos, keine Schreiboperation,
kein Gesamturteil, Feinlabels nicht verglichen.

**Grenzen, bewusst.** Der Eye-Lauf ist sequenziell (ein Modell, eine Anfrage, feste Zeitgrenze je
Aufruf). Ohne Cloud-Einwilligung entstehen keine Sehenswürdigkeitsnamen, nie Cloud-Kosten und kein
Rückfall auf einen anderen Modus. Der Egress des Fremdpakets ist **nicht** erzwungen — es
kontaktiert ausschließlich `events.desertant.com` mit Metadaten; die Durchsetzung bleibt
Betreiberpflicht des Heimservers, `docs/setup.md` nennt den Weg. Eye v1.0.0 ist Beta.

**Berührte Stellen.** `backend/src/photosort/{models,worker,config,motif_strengths,eye_mapping,
eye_comparison,project_deletion}.py`, `api/projects.py`, `api/photos.py`, Migration; `eye/` (neu);
`docker-compose.yml`, `docker-compose.e2e.yml`; `frontend/src/{api/projects.ts,api/types.ts,
hooks/useProjects.ts,components/ClassificationSection.tsx,components/ClassificationEstimate.tsx,
components/ClassificationProgress.tsx,components/ClassificationBalance.tsx,
components/MotifStrengthSection.tsx,components/EyeAttribution.tsx,utils/classificationSteps.ts,
utils/motifStrength.ts,pages/PhotoDetailPage.tsx}`; CI (`eye-eval` → `eye`); `docs/`.

## UI/UX

**Kein Weg vorausgewählt, drei gleichrangige Zeilen.** Die Laufwahl ersetzt in
`ClassificationSection.tsx` das Kontrollkästchen „Cloud-Bilderkennung für diesen Durchlauf nutzen"
und steht als erstes Bedienelement direkt unter der Erklärzeile; der Erneut-Auslöser folgt darunter,
die Kostenvorschau bleibt an ihrem heutigen Platz. *Abweichung vom Muster „Erneut-Auslöser im
Schrittkopf": die Wahl ist Vorbedingung beider Auslöser, und ein gesperrter Auslöser über dem
Bedienelement, das ihn freigibt, ist eine Sackgasse.*

- **Form.** `fieldset` + `legend` „Weg für diesen Durchlauf", darin drei Zeilen **Cloud · Eye · Nur
  lokal** — dieselbe Konstruktion wie die Richtungswahl in `CameraTimeOffsetDialog.tsx`: natives
  `<input type="radio">` mit `name` aus `useId`, `accent-accent`, die ganze Zeile per `<label>`
  treffbar (`min-h-11`). Kein neues Primitiv, keine Symbole je Weg, keine neue Farbe.
- **Inhalt je Zeile.** Name (`text-sm font-medium text-text-h`) und eine Metazeile (`text-xs
  text-text-muted`): Cloud „Fotos an {Anbieter} · Abrechnung nach Verbrauch"; Eye „Bleibt auf diesem
  Server · kostenfrei", mit Einwilligung zusätzlich „— abgerechnet wird nur die
  Sehenswürdigkeits-Erkennung"; Nur lokal „Bleibt auf diesem Server · kostenfrei".
- **Keine Voreinstellung.** Kein Wert beim Öffnen, keine gemerkte Wahl über ein Neuladen, kein
  gespeicherter „letzter Weg"; nach dem Start des Laufs wird die Auswahl geleert. Solange nichts
  gewählt ist, lädt keine Kostenvorschau. Ist `eye_available=false`, sind es genau zwei Zeilen.
- **Umfangssatz mit drei Fassungen.** Der Absatz `data-testid="classification-scope-text"` bleibt,
  Cloud und Nur lokal wortgleich zu heute. Bei Eye nennt er, was Eye beurteilt, dass kein Foto den
  Rechner verlässt, bei Einwilligung die Abgabe der Foto- und Ortsangaben für die
  Sehenswürdigkeits-Erkennung — und in **beiden** Eye-Fassungen: „Eye sendet bei jedem Lauf eine
  Lizenzmeldung mit einer Zählkennung, aber ohne Bildinhalte an Desert Ant Labs; diese Meldung lässt
  sich nicht abschalten." Kein einmaliger Dialog, kein „schon gesehen"-Speicher.
- **Kostenvorschau je Weg** (`ClassificationEstimate`): eine Zeile je Anteil, der **stattfindet**;
  ein kostenfreier Anteil ist das Wort „kostenfrei", nie „0,00 USD"; nicht stattfindende Anteile
  fehlen ganz. Ein Weg ganz ohne Kosten zeigt eine Zeile: „Dieser Durchlauf ist kostenfrei." Anbieter,
  Modell und Preisgrundlage stehen nur am Cloud-Anteil. Während sie lädt: „Kostenvorschau wird
  geladen…"; scheitert sie, der bestehende `Alert` mit „Erneut versuchen".
- **Auslöser.** Gesperrt ohne Wahl, mit Begründung unter der Gruppe („Wähle einen Weg — ohne Wahl
  startet kein Lauf."); gesperrt, solange der gewählte Weg Kosten tragen kann und seine Vorschau
  nicht geladen ist; gesperrt während des Laufs, die Gruppe bleibt sichtbar und deaktiviert.
- **Eye nicht verfügbar.** Die Ablehnung erscheint als `Alert` am Auslöser: `detail` des Servers plus
  der Satz, dass der Lauf **nicht** gestartet und nichts verändert wurde. Die Auswahl bleibt stehen,
  es wird **nicht** auf einen anderen Weg umgeschaltet; `503` trägt „Erneut versuchen", `403` nicht.
  Bricht der Dienst im Lauf weg, bleibt der bestehende Fehler-`Alert` am Lauf, der Teilschritt steht
  auf fehlgeschlagen.
- **Fortschritt und Bilanz.** Neuer Teilschritt „Eye-Auswertung" zwischen „Kategorie-Vorschläge" und
  „Qualität und Bildinhalt", Zähler „{verarbeitet} von {gesamt} Fotos", nach Laufende ohne Zähler
  ausgeblendet. Die Bilanz bekommt eine Zeile „Eye-Auswertung · {n} Fotos · kostenfrei" ohne Betrag;
  die Summenzeile bleibt Cloud-only.
- **Herkunft.** Die Grundlagenzeile in `MotifStrengthSection` bekommt den dritten Zweig „Grundlage:
  Eye-Auswertung, {Zeitpunkt}" (`text-xs text-text`) und trägt `data-motif-source`; die beiden
  bestehenden Zweige bleiben wortgleich. Sie gilt auch in der schreibgeschützten Kachel-Fassung.
- **Eye-Band in der Fotoansicht.** Genau bei gesetztem `photo.eye_result` steht unter `PhotoVerdict`
  und über der Motiv-Überschrift: „Albumtauglichkeit und Feinlabels stammen aus der Eye-Auswertung —
  Modellrevision {r}, {Zeitpunkt}." Die Werte selbst stehen darüber bereits und werden nicht doppelt
  gezeigt.
- **Namensnennung.** `EyeAttribution` in `text-xs text-text-muted`, Form der GeoNames-Nennung, an der
  Verwendungsstelle statt in einer Fußzeile: unter der Eye-Zeile, unter der Grundlagenzeile bei
  `source='eye'`, unter dem Eye-Band. Nicht aufklappbar, nicht ausblendbar, nie in einem `Alert`.

**Unverändert.** Kuratierung und Album-Entwurf zeigen nichts Neues. Neue Muster in
[`0004`](../architecture/0004-design-system.md): „Laufwahl mit mehreren Wegen", „Namensnennung eines
Drittanbieters an der Verwendungsstelle", „kostenfrei ist ein Wort, keine 0".

## Security

**Sicherheitsrelevant, kein Blocker.** Fortschreibung in
[`0003`](../architecture/0003-securitykonzept.md): Angriffsflächen-Zeile `eye`, REST-API-Grundsatz
„Weg abfragen statt raten", Compose-Zeile, Restrisiko Egress.

- **S1 — Kein Weg zu Datenbank, Cache, Geheimnissen, Host.** `profiles: ["eye"]`, **kein**
  `ports:`, `user: node`, Volumes nur `eye_model` (ro) und `eye_home` (rw), keine
  `POSTGRES_*`/`REDIS_*`/`OPENCLOUD_*`/`SECRET_KEY`/`ANTHROPIC_API_KEY`/`MISTRAL_API_KEY`, nur das
  Default-Netz. **Erzwingung:** Schritt „Static check – eye sidecar exposure" im CI-Job
  `docker-compose-check` über `docker compose --profile eye config --format json`.
- **S2 — Egress nur `events.desertant.com`, und das bleibt Betreiberzusage.** Nicht erzwungen;
  `docs/setup.md` benennt die Pflicht, 0003 führt sie als akzeptiertes Restrisiko, Code täuscht sie
  nicht vor. `DAL_LICENSE_ENDPOINT`, `HF_TOKEN` oder eine gesetzte `*_PROXY`-Variable brechen den
  Start ab; im Image steht nur `DAL_APP_ID=photosort`.
- **S3 — Der Sidecar nimmt Bytes, keine Pfade, keine Header, in fester Grenze.** Nur
  `Content-Type: image/jpeg`, Körpergrenze **8 MiB** → `413`/`415` vor dem Modell, kein Multipart,
  kein URL-/Feldparameter (kein SSRF), Antwort nur JSON, Fehler als feste Sätze. Backendseitig genau
  `display_path(photo_id, etag)`, sequenziell, **30 s je Foto**, kein Retry, keine Browser-Kopfzeile
  weitergegeben; `EYE_SERVICE_URL` nur aus den Settings, nur `http`/`https`,
  `follow_redirects=False`, Antwortkörper vor `json.loads` auf **1 MiB** gedeckelt.
- **S4 — Start fail-closed, Gewichte außerhalb von Repository und Image.** Kein `COPY`, keine
  `.gitignore`-Lücke, kein Env-Wert als Pin; Prüfung bei jedem Start vor `/health` 200, ohne
  Nachladen. Die Install-ID liegt auf `eye_home` und erscheint in keinem Repo-Artefakt.
- **S5 — `mode` ist eine Anfrage ohne Vorgabe, kein stiller Rückfall, keine Infrastruktur in der
  Meldung.** Unbekannter oder fehlender Wert → `422`, kein Abbilden auf einen anderen Weg. Meldungen
  sind feste deutsche Sätze ohne Variablennamen, Host, Port, Version, Pin oder Stacktrace — auch die
  persistierte `error_message`. Die Oberfläche startet keinen zweiten Lauf aus dem Fehlerfall.
- **S6 — Der alte Job-Parameter darf `"eye"` nie als Cloud-Freigabe lesen.** `use_cloud` bleibt
  vierter Positionsparameter (`bool | None`), `mode` ist keyword-only; fehlt er, wird er aus
  `use_cloud` abgeleitet, und ein alter Worker verwirft den Job sichtbar mit `TypeError`.
  `cloud_requested` = `mode='cloud'` **oder** (`mode='eye'` **und** Einwilligung).
- **S7 — Die Kostenvorschau behauptet keine Kosten, die nicht stattfinden, und keine Null, wo Geld
  fließt.** Nicht stattfindender Anteil `null`, nie `0.0`; Antwort trägt `mode`; die Vorgabe `cloud`
  existiert nur auf diesem Lesepfad, nie auf dem Laufpfad.
- **S8 — Eye schreibt nie in einen Pfad, der Cloud-Auswahl, Album-Entwurf oder Kosten verschiebt.**
  Nie `photo_album_suitability`, nie `photo_fine_labels`/`fine_labels`; Promotion nur ohne
  Cloud-Kopfzeile; Rangfolge in `upsert_assessment`; Korrekturen unberührt; `provider` bleibt `NULL`.
  Schattenzeilen und Promotion in **einer** Transaktion; Scheitern → `FAILED`, keine Promotion.
- **S9 — Eye-Ergebnisse fallen mit dem Projekt.** Über `photos` erreichbar, `project_deletion.py`
  und `tests/project_graph.py` mitgezogen, kein `user_id`, Schnappschüsse nur mit lokalem Vektor.
- **S10 — Vergleichs-CLI rein lesend, ohne Namen, Ausgabe außerhalb des Repos.** Kein Importpfad aus
  `main.py`/`worker.py`, kein Endpunkt, kein Compose-`command`; Formwächter über dem Syntaxbaum
  lässt genau eine Schreibstelle (die `--out`-Datei) zu und verbietet Logging; `--out` im Repo wird
  vor dem Schreiben laut abgelehnt. Gelesen werden nur Eye-, Cloud-, Motiv- und Albumspalten — nie
  `photos.relative_path`, `users`, Personen-, Orts- oder Sehenswürdigkeitsnamen.
- **S11 — Keine Nutzerdimension.** Beide Nutzer erhalten denselben `eye_result`; kein neuer Router.
- **S12 — Modelltext ist Text, die Nennung ein fremder Link.** Eye-Feinlabels am Parser mit
  `cloud_vision._sanitize_label_text` saniert, längenbegrenzt, leer → weggelassen, nur als
  React-Textknoten gerendert; `EyeAttribution` mit fester `https`-Adresse und
  `rel="noopener noreferrer"`; der Lizenzhinweis ist nicht abwählbar (kein `localStorage`-Flag).

**Ohne Befund:** Auth, JWT, Rate-Limit, CSRF, Secrets-Pfade, Projektbindung, Sichtbarkeit zwischen
den Nutzern unverändert; kein Schreibzugriff auf OpenCloud; keine Bilddaten im Repository.

## Tests

Kein neues Werkzeug, keine neue Fixture-Art; die Ebenen des
[`Testkonzepts`](../architecture/0002-testkonzept.md) gelten unverändert.

| Ebene | Gegenstand | Ort |
|---|---|---|
| Unit | `eye_mapping` (SDK-Dict → Motive/Ausschluss/Album/Feinlabels/Tag-Tabelle), Rangfolge-Matrix, reine Vergleichslogik, `Settings`-Felder | `test_eye_mapping.py` (neu), `test_motif_strengths.py`, `test_eye_comparison.py` (neu), `test_config.py` |
| Integration | Eye-Phase gegen In-Memory-DB mit Fake-Client, Rangfolge/Schnappschuss, Fehlerpfade, Unberührtheit von Album/Cloud, Migration | `test_worker_eye_phase.py` (neu), `test_worker_classification.py`, `test_migration_eye_*.py`, `test_project_deletion.py` + `project_graph.py` |
| API | `mode`-Pflicht, 403/503-Reihenfolge, `estimate?mode=`, `eye_available`, `eye_result` | `test_api_criterion_scoring.py`, `test_api_classification_estimate.py`, `test_api_projects.py`, `test_api_photos.py` |
| Sidecar | Pins, Health-Zustand, Bytes-Grenze, Routen, Lizenzabbruch — ohne Modell | `eye/test/*.test.js` (`node --test`) |
| Frontend | Auswahl, Kostenzeile, Alert, Herkunft, Attribution, Teilschritt, Bilanz | `ClassificationSection.test.tsx`, `ClassificationEstimate.test.tsx`, `ClassificationProgress.test.tsx`, `ClassificationBalance.test.tsx`, `classificationSteps.test.ts`, `MotifStrengthSection.test.tsx`, `PhotoDetailPage.test.tsx`, `useProjects.test.tsx` |
| E2E | Prüfstack mit `EYE_ENABLED=true` ohne Dienst: sichtbare `503`-Ablehnung, kein Rückfall | `e2e/tests/eye-nicht-verfuegbar.spec.ts` (neu, `DESKTOP_ONLY`) |

**Tragende Zusagen** (je eigener Test, nicht aus dem Erfolgsfall miterschlossen): „Eye verdrängt
nichts Höherrangiges", „Eye hinterlässt bei jedem Fehler null Spuren", „ein Ausbau verliert nichts".
Weitere Zusagen: ein Transportfehler bricht die Phase ab, ein unlesbares Bild nicht (es wird
übersprungen, `eye_photos_processed` bleibt unter `_total`); die Phase ist sequenziell (Höchststand
gleichzeitiger Aufrufe == 1); `CancelledError` → `FAILED`, Bestand unberührt; Alter vierten
Positionsparameter bleibt kompatibel; `data-motif-source` in allen drei Zweigen; „kostenfrei" nie
als `0,00 USD`; gleicher Seed gleiche Auswahl; Migration `upgrade`/`downgrade` Postgres-fest.
`demo_state.py` bekommt genau ein Eye-Foto, indem eine bisher lokale Kopfzeile umgestellt wird.

**Bekannte Lücken** (in 0002 eingetragen): die Inferenz prüft kein Test (keine Gewichte im Repo, CI
läuft ohne Modell); der Tag-Abgleich gegen `eye_meta.json` bleibt Heimserver-Schritt.

**Entfällt mit `tools/eye-eval/`:** 21 Testdateien samt `args`, `baseline`, `cache`, `calls`, `cli`,
`db`, `decisions`, `page`, `paths`, `prepare`, `report`, `runfile`, `sample`, `savings`, `session`,
`summary`, `votes` und dem Read-only-Postgres-Test. Umziehen: `mapping`/`signals` →
`test_eye_mapping.py`, `pins` → `eye/test/pins.test.js`, `compare` → `test_eye_comparison.py`.

## Entscheidungen

- `architect` konsultiert (Schritt 1): Anbindung des Node-SDK ist eine Architekturfrage; ADR 0138
  angelegt, docs/architecture.md, docs/setup.md, README, `.env.example` fortgeschrieben.
- `ux-ui-designer` konsultiert (Schritt 2): Laufwahl, Kostenzusage, Herkunft, Attribution sind
  sichtbare Oberfläche. Der offene Punkt des Agenten („woran erkennt die Oberfläche den
  Schalterzustand?") ist durch `ProjectOut.eye_available` beantwortet — kein zusätzlicher Aufruf.
- `test-engineer` konsultiert (Schritt 3): Teststrategie und Testebenen oben; 0002 um zwei
  Lücken-Einträge ergänzt.
- `security-engineer` konsultiert (Schritt 3): Bewertung oben; 0003 fortgeschrieben.
- **`provider` bei `source='eye'` ist `NULL`** — die bestehende Zusage „nur `local` trägt keinen
  Anbieter" bleibt damit die einzige Ausnahme; ein Provider-Wert behauptete einen Cloud-Kontakt. Die
  Modellrevision steht in `photo_eye_results`.
- **`mode` fehlt in `CriterionScoringRunSummary`** — die Anzeige leitet den Eye-Teilschritt aus
  `eye_photos_total is not None` ab (Muster `persons_*`), kein zweiter Wahrheitsstand.
- **Reihenfolge der Ablehnungen:** beide Deployment-Schalter vor dem Projektzugriff, Consent-`403`
  und Health-`503` nach den `409`ern — billigste, projektunabhängige Prüfung zuerst, keine DB-Zeile
  für eine Ablehnung.
- **E2E prüft den Schalter-fall „an, Dienst fehlt"**, nicht „aus": mit ausgeschaltetem Schalter
  bietet die Oberfläche nur zwei Wege, es gäbe keine sichtbare Ablehnung.
- **Zahlen des Vergleichs:** Motiv bei Schwelle 0.5 inklusiv, Zufallsauswahl `min(30, Abweichungen)`
  je Zweck und Projekt, Details nur in der `--out`-Datei.

## Offene Fragen

Keine.

## Out of Scope

- Die Auswertung selbst und das Urteil je Zweck — das ist Story
  [#610](https://github.com/TheRealKoller/photosort/issues/610).
- Der Rückbau — eigene Story; diese Spec legt nur fest, dass er verlustfrei möglich bleibt.
- Eye-Ergebnisse im Album-Entwurf (ADR 0095 bleibt unverändert) und Eyes Albumtauglichkeit als
  Grundlage irgendeiner Auswahl.
- Sehenswürdigkeitsnamen aus Eye — das Modell liefert keine Eigennamen.
- Feinlabels-Vergleich im Vergleichs-CLI (Vokabulare nicht vergleichbar).
- Parallele Verarbeitung im Eye-Lauf.
