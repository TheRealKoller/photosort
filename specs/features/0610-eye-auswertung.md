# 0610 - Eye gegen die Cloud auswerten: Werte je Abweichung, Herkunft, Laufzeit, Urteil

**Status:** Implemented ([PR #617](https://github.com/TheRealKoller/photosort/pull/617))
**Erstellt:** 2026-11-04
**Bezug:** [Issue #610](https://github.com/TheRealKoller/photosort/issues/610)

**Umfang:** über dem Richtwert von rund 200 Zeilen, weil die Spec drei Dinge vollständig trägt — die
Story-Kriterien, an denen das Ergebnis gemessen wird, die technischen Kriterien der CLI-Erweiterung
und den Auswertungsablauf, den Daniel ohne weitere Vorlage durchführt.

## Ziel

Mit [`0609`](./0609-eye-dritte-wahl.md) läuft das lokale Bildmodell Eye als dritte Laufwahl neben
der Cloud, und seine Ergebnisse liegen als Schatten neben den Cloud-Ergebnissen derselben Fotos.
Offen ist, ob Eye etwas taugt. Diese Spec legt fest, wie die Antwort entsteht: das Vergleichs-CLI
trägt je Abweichung **beide** Werte, dazu Herkunft, Laufzeit und Aufrufzahl; Daniel beurteilt eine
Zufallsauswahl der Abweichungen am Foto und schreibt das Ergebnis als Abschnitt „Vergleichsergebnis"
in die Spec zu #609. Die Anwendung selbst ändert sich nicht.

## User Story

Als Betreiber von PhotoSort möchte ich Eye auf echten Projekten neben die Cloud-Klassifizierung
stellen und eine Zufallsauswahl der abweichenden Fotos je Zweck selbst beurteilen. Damit kann ich
belegt festhalten, ob Eye als lokale Wahl in der Anwendung bleibt oder zurückgebaut wird.

## Akzeptanzkriterien (Story)

Aus [Issue #610](https://github.com/TheRealKoller/photosort/issues/610), unverändert:

- [ ] **Stichprobe:** Ausgewertet werden mindestens zwei bestehende Projekte unterschiedlicher Art,
      zum Beispiel eine Reise mit Sehenswürdigkeiten und ein Familienalltag mit vielen Menschen. Je
      Projekt tragen mindestens 100 Fotos sowohl ein Cloud- als auch ein Eye-Ergebnis. Im Ergebnis
      steht, welcher Art jedes Projekt ist.
- [ ] **Herkunft und Kosten:** Das Ergebnis nennt Anbieter und Modell der Cloud-Ergebnisse sowie die
      Eye-Version. Fehlende Cloud-Ergebnisse entstehen nur über den normalen Klassifizierungslauf mit
      vorher angezeigten Kosten. Für Eye verlässt kein Foto den Heimserver.
- [ ] **Bewertete Zwecke:** Bewertet werden drei Zwecke: Motivstärken, der Ausschluss als Dokument
      oder Screenshot und die Albumtauglichkeit, einschließlich geschlossener Augen und verdeckter
      Gesichter. Feinlabels und Sehenswürdigkeitsnamen werden nicht bewertet. Das Ergebnis führt beide
      ausdrücklich als „nicht bewertet": Feinlabels, weil die Vokabulare von Eye und Cloud nicht
      vergleichbar sind; Sehenswürdigkeitsnamen, weil Eye keine Eigennamen liefert und die Namen
      weiter aus der Cloud kommen.
- [ ] **Prüfmenge:** Je bewertetem Zweck und Projekt zieht der Vergleich aus #609 eine Zufallsauswahl
      von mindestens 30 abweichenden Fällen. Gibt es weniger Abweichungen, werden alle geprüft. Daniel
      prüft jeden ausgewählten Fall mit beiden Ergebnissen am Foto. Er sieht dabei, welches Ergebnis
      von Eye kommt, und labelt kein Foto von Hand. Das Ergebnis nennt je Zweck und Projekt die Zahl
      der Übereinstimmungen, die Zahl der Abweichungen und die Größe der geprüften Auswahl.
- [ ] **Urteil je Zweck:** Jeder bewertete Zweck bekommt genau eines von drei Urteilen: „Eye ist
      besser", „gleichwertig" oder „schlechter / nicht geeignet". Dazu gehört eine Begründung mit
      beschriebenen Beispielfällen. Ein Gesamturteil über alle Zwecke gibt es nicht. Für einen Ersatz
      der Cloud genügt „gleichwertig".
- [ ] **Laufzeit und Einsparung:** Das Ergebnis sagt, ob Eye ein typisches Projekt auf dem Heimserver
      in vertretbarer Zeit auswertet, gemessen an der Dauer des Cloud-Laufs. Es beziffert, wie viele
      Cloud-Aufrufe je Projekt wegfielen. Als eingespart zählt ein Aufruf nur, wenn alle drei
      bewerteten Zwecke mindestens „gleichwertig" sind. Das Ergebnis vermerkt, dass die Feinlabels
      dann ungeprüft von Eye kämen. Aufrufe für Sehenswürdigkeitsnamen zählen nie als eingespart.
- [ ] **Entscheidung:** Am Ende steht genau eine Entscheidung, „Eye bleibt" oder „Rückbau". Ihre
      Begründung stützt sich auf die Urteile je Zweck, auf Laufzeit und Einsparung sowie auf die
      Einstufung der Lizenz, die im Ergebnis steht. Ist die Lizenz als „unklar" oder „unzulässig"
      eingestuft, lautet die Entscheidung „Rückbau".
- [ ] **Folge von „Rückbau":** Der Rückbau wird als eigene Story erfasst und im Ergebnis verlinkt.
      Diese Story selbst ändert die Anwendung nicht.
- [ ] **Folge von „Eye bleibt":** Das Ergebnis nennt die Zwecke, für die Eye als Ersatz taugt. Eyes
      Albumtauglichkeit fließt weiterhin nicht in den Album-Entwurf. Eine Änderung daran wäre eine
      eigene Story. Der Beta-Status des Modells und seine künftige Pflege stehen als Restrisiko im
      Ergebnis.
- [ ] **Ablage:** Das Ergebnis steht als Abschnitt „Vergleichsergebnis" in der Spec zu #609. Spec
      0606 bekommt kein Ergebnis.
- [ ] **Inhaltsauflagen:** Das Ergebnis enthält keine Bilddaten, keine Dateinamen und Pfade, keine
      Aufnahmedaten, Aufnahmeorte oder GPS-Angaben. Personen erscheinen nur als Rolle („Kind",
      „Großmutter"), Orte nur als Gattung („Kirche", „Strand"), und es stehen keine Namen von
      Sehenswürdigkeiten darin. Projekte heißen „Projekt A/B", wenn ihr Name einen Ort verrät. Keine
      Angabe darf zusammen mit anderen auf ein Reiseziel schließen lassen. Das Ergebnis enthält nur
      Zählungen, Zwecke, Urteile und handgeschriebene Prosa, keine Zeile je Foto.
- [ ] **Gegenlesen vor dem Push:** Daniel liest das Ergebnis vor dem ersten Push gegen. Ein Verstoß
      gegen die Inhaltsauflagen wird vor dem Push umformuliert und nie in einem späteren Commit
      nachgebessert.

## Akzeptanzkriterien (Vergleichs-CLI)

- [ ] **Beide Werte in jeder Abweichungszeile.** `Deviation` behält `photo_id`, `purpose`,
      `motif_key` und trägt neu **ohne Vorgabewert** drei Wertepaare: `cloud_strength`/`eye_strength`
      (Motivzweck), `cloud_excluded_document`/`eye_excluded_document` (Ausschluss),
      `cloud_album_level`/`eye_album_level` (Albumstufe). Jede `--out`-Zeile führt **alle** diese
      Schlüssel; `null` steht dort, wo der Zweck das Paar nicht führt. Kein Vorgabewert, weil ein in
      `summarize` vergessenes Setzen dann beim Bau scheitert statt als stilles `null` in die Datei zu
      gehen.
- [ ] **Rohwerte, unverändert und ungerundet.** Die Stärke steht so in der Datei, wie sie in der
      Datenbank steht: kein `round`, keine Formatierung, keine Prozentangabe. Die Entscheidung
      „vorhanden" bleibt ausschließlich `selection.motif_is_present` — kein eigenes Schwellenliteral
      im Modul.
- [ ] **Grenze und fehlende Seite.** Cloud 0.5 / Eye 0.5 → Übereinstimmung, keine Zeile; 0.5 /
      0.4999999 → Zeile mit beiden Rohwerten. Fehlt der Schlüssel auf einer Seite, steht dort `null`
      (nicht `0.0`): „nicht beurteilt" ist nicht „als 0.0 beurteilt". `cloud_album_level=None` fällt
      weiterhin ganz aus dem Albumvergleich.
- [ ] **`origin`.** Genau drei Listen: `cloud_providers`, `cloud_models`, `eye_model_revisions`; je
      aufsteigend sortiert, dedupliziert, `NULL` verworfen, kein Vorkommen → `[]` (nie `null`).
      Bezugsmengen: Anbieter = `provider` der Cloud-Kopfzeilen der **verglichenen** Fotos; Modelle =
      `model` **aller erfolgreichen** Remote-Läufe des Projekts; Revisionen = `model_revision` der
      Eye-Zeilen der verglichenen Fotos.
- [ ] **`runtime.cloud_run`.** Gewählt wird der jüngste `CriterionScoringRun` mit `status=success`
      **und** gesetztem `finished_at`, dessen `remote_category_classification_run_id` auf einen
      `RemoteCategoryClassificationRun` mit `status=success` zeigt; `mode` wird **nicht** gefiltert,
      eine Altzeile `mode IS NULL` zählt mit. Der Filter greift **vor** der Ordnung (jüngster =
      `finished_at` absteigend, bei Gleichstand `id` absteigend). Felder: `duration_seconds` (int),
      `remote_photos_total`, `remote_api_calls` — aus dem **verknüpften** Remote-Lauf, verbatim,
      `NULL` bleibt `null`. Kein Kandidat → `null`.
- [ ] **`duration_seconds` ist eine ganze Sekunde, abgeschnitten.** `int(total_seconds)` der
      Differenz `finished_at − started_at`, nicht gerundet.
- [ ] **`runtime.eye_run`.** Jüngster Lauf mit `mode='eye'` **und** `status=success` **und** gesetztem
      `finished_at`; Felder `duration_seconds`, `eye_photos_total`, `eye_photos_processed` verbatim —
      `NULL` bleibt `null`. Eine Altzeile `mode IS NULL` ist **nie** ein Eye-Lauf, auch wenn
      `eye_photos_*` gefüllt sind. Kein Kandidat → `null`. Projekt ohne jeden Lauf: beide Blöcke
      `null`, `origin` leer, Exitcode 0, Zählungen 0.
- [ ] **`remote_api_calls_total` ist vollständig oder `null`.** Summe über `api_calls` **aller**
      erfolgreichen Remote-Läufe des Projekts; in irgendeinem davon `api_calls` `NULL` oder kein
      solcher Lauf → `null`; alle `0` → `0`. Nie eine Teilsumme, nie eine Hochrechnung.
      `landmark_api_calls` geht nicht ein, auch nicht anteilig; ein fehlgeschlagener Remote-Lauf geht
      gar nicht ein.
- [ ] **Schlüsselsatz und stdout.** `full_report(report, runs, *, project_id)` liefert die bisherigen
      Schlüssel plus `origin` und `runtime` und kein Urteilsfeld. stdout bleibt unverändert: nur
      Zählungen, kein `origin`/`runtime`, keine Fotozeilen. `--out` bleibt außerhalb des Repos,
      Ablehnung vor jedem Datenbankzugriff, genau **eine** Schreibstelle im Modul.
- [ ] **Kein Fremdtext, kein Zeitstempel in der Datei.** `load_run_facts(session, project_id) ->
      RunFacts` selektiert Einzelspalten und liest weder `error_message` noch `cloud_error_message`;
      weder `RunFacts` noch die Ausgabe führen eine Zeitangabe, nur `duration_seconds`. Wächter über
      den Syntaxbaum: keine Attributlesung mit Endung `error_message`, kein Import eines Netzwerk-
      oder Client-Moduls, kein `add`/`add_all`/`merge`/`delete`/`commit`/`flush`. Verhaltensseitig:
      ein Marker aus beiden Meldungsspalten fehlt im serialisierten JSON, ein ISO-Zeitstempel-Muster
      ebenfalls.
- [ ] **Die Repo-Grenze der Ausgabe prüft den Zielpfad, nicht das Paket.** `_resolve_out` lehnt ein
      Ziel ab, wenn über ihm ein Verzeichnis mit `.git` liegt; ohne Arbeitsbaum über dem Ziel ist es
      zulässig. Eine Messung ab dem installierten Modul ist unzulässig: Sie endet im Container ohne
      `.git` bei `/` und lehnt damit jeden Pfad ab, auch das in `docs/setup.md` dokumentierte
      `/tmp/...`. Abgelehnt wird vor jedem Schreibzugriff, ohne Datei.
- [ ] **Doku.** `docs/setup.md` (Vergleichsabschnitt) und `docs/architecture.md` nennen die
      Abweichungswerte, `origin`/`runtime` und die Grenze „Dauern, keine Zeitstempel, keine
      Fehlermeldungstexte".

## Datenmodell-Bezug

Keine Änderung. Gelesen werden zusätzlich `criterion_scoring_runs.{mode, status, started_at,
finished_at, eye_photos_total, eye_photos_processed, remote_category_classification_run_id}`,
`remote_category_classification_runs.{status, model, photos_total, api_calls}` und
`photo_eye_results.model_revision` ([`docs/architecture.md`](../docs/architecture.md)).

## Architektur / Umsetzung

**Das bestehende Werkzeug wird erweitert, kein neuer Weg.** Die Auswertung läuft über
`python -m photosort.eye_comparison` (Spec 0609, ADR 0138 Punkt 8): kein Endpunkt, keine
Oberfläche, keine Migration, keine Schreiboperation. Bei geltender Cloud-Kopfzeile zeigt die
Fotoansicht den Eye-Schatten nicht (`PhotoOut.eye_result` nur bei `source='eye'`), und daran
ändert diese Story nichts. Beide Werte stehen deshalb in der `--out`-Zeile neben dem App-Pfad,
über den Daniel das Foto öffnet. stdout bleibt unverändert: nur Zählungen.

**Werte an jeder Abweichungszeile.** `Deviation` bekommt drei Pflichtpaare, eines je Zweck:
`cloud_strength`/`eye_strength` (Motiv, `float`, ungerundet — die inklusive Grenze 0.5 muss lesbar
bleiben), `cloud_excluded_document`/`eye_excluded_document` (`bool`) und
`cloud_album_level`/`eye_album_level` (`int`). Jede Zeile führt **alle** Schlüssel; `null` steht
dort, wo der Zweck das Paar nicht führt oder eine Seite den Schlüssel nicht beurteilt hat. Die
Herkunft steht im Schlüssel, nicht in einer Reihenfolge. Auswahl, Sortierung und Seed-Strom bleiben
gleich, dieselbe Seed wählt dieselben Zeilen.

**Herkunft (`origin`).** `cloud_providers` enthält die `provider`-Werte der Cloud-Kopfzeilen der
verglichenen Fotos, `cloud_models` die `model`-Werte aller erfolgreichen
`remote_category_classification_runs` des Projekts, `eye_model_revisions` die `model_revision`
der verglichenen Eye-Zeilen. Alle drei sind sortiert und ohne Dubletten. `NULL` (nicht erfasst)
entfällt, ergänzt wird nichts; ohne Quelle bleibt die Liste leer.

**Laufzeit (`runtime`).** `cloud_run` ist der jüngste Lauf in `criterion_scoring_runs` mit
`status='success'` und gesetztem `finished_at`, dessen `remote_category_classification_run_id`
auf einen erfolgreichen Remote-Lauf zeigt. Das gilt unabhängig von `mode`: Eine Remote-Phase gibt es
nur bei Cloud, so zählen auch Altzeilen von vor der Laufwahl. Felder: `duration_seconds`
(`finished_at − started_at`, ganzzahlig), `remote_photos_total`, `remote_api_calls`. `eye_run`
ist der jüngste erfolgreiche Lauf mit `mode='eye'`, Felder: `duration_seconds`,
`eye_photos_total`, `eye_photos_processed`. „Jüngster" heißt: nach `finished_at`, dann `id`
absteigend. Fehlt ein Lauf, ist das Objekt `null`. Beide Dauern messen den ganzen Lauf, Landmark,
Personen und Kriterien eingeschlossen, auf beiden Seiten gleich. An den Zählfeldern ist ablesbar,
ob ein Lauf nur eine Nachklassifizierung war.
`remote_api_calls_total` ist die Summe von `api_calls` aller erfolgreichen Remote-Läufe des
Projekts und damit die Grundlage der Einsparung. Landmark-Aufrufe stehen in eigenen Spalten und
gehen nie ein. Ohne Lauf, oder wenn ein Lauf `api_calls = NULL` hat, ist der Wert `null`, nie eine
Teilsumme.

**Schnitt.** Die reine Logik sammelt Anbieter und Revisionen in `ComparisonReport`
(`PhotoComparison` bekommt `cloud_provider` und `eye_model_revision`). Der neue Leser
`load_run_facts(session, project_id) -> RunFacts` wählt Spalten einzeln aus, nie ganze Zeilen:
nie `error_message`/`cloud_error_message`, kein Zeitpunkt in der Ausgabe. `full_report(report, runs,
*, project_id)` hat die bisherige feste Schlüsselmenge plus `origin` und `runtime`, weiterhin ohne
Urteilsfeld. Der Formwächter bleibt (eine Schreibstelle, kein Logging, kein `relative_path`) und
bekommt dazu: kein Zugriff auf ein Attribut `*error_message`.

**Reihenfolge.** (1) Werte an `Deviation`/`summarize`, (2) Herkunft sammeln, (3) `load_run_facts`
gegen die In-Memory-DB: kein Lauf, Altzeile `mode=NULL` mit Remote-Lauf, Nachklassifizierung als
jüngster Lauf, `api_calls=NULL`, fehlgeschlagener Lauf, (4) Schlüsselmenge von `full_report`,
(5) Doku. Die Auswertung selbst ist kein Code: Urteile, Entscheidung und den Abschnitt
„Vergleichsergebnis" in 0609 schreibt Daniel. Die `--out`-Datei bleibt außerhalb des Repos.

**Berührte Stellen.** `backend/src/photosort/eye_comparison.py`,
`backend/tests/test_eye_comparison.py`, `docs/setup.md` („Vergleich mit der Cloud"),
`docs/architecture.md` (Absatz zum Vergleich); danach `specs/features/0609-eye-dritte-wahl.md`
(nur der Abschnitt „Vergleichsergebnis"). Keine neue ADR.

## UI/UX

Nicht relevant — und zwar aus einem fachlichen Grund, nicht aus einem Formfehler: Die Story sagt
ausdrücklich, dass sie die Anwendung nicht ändert. Dieselbe Grenze schließt die naheliegende
Anzeige aus. Bei geltender Cloud-Kopfzeile zeigt die Fotoansicht den Eye-Schatten nicht
(`PhotoOut.eye_result` nur bei `source='eye'`), und ein eigenes Vergleichsband wäre eine Änderung
der Oberfläche, die der Story widerspräche. Beide Werte stehen deshalb in der `--out`-Datei; das
Foto öffnet Daniel über den dort mitgegebenen App-Pfad, die Eye-Seite liest er dort mit.

`ux-ui-designer` nicht konsultiert (`spec-writer` Schritt 2): kein sichtbarer Teil der Oberfläche
wird angefasst — die Ausgabe ist eine Datei, die ein Betreiber am Terminal erzeugt.

## Security

**Sicherheitsrelevant, kein Blocker.** Dieselbe Angriffsfläche, eine neue Ausgabeform: Fortschreibung
in [`0003`](../architecture/0003-securitykonzept.md), Ankerzeile „Das Vergleichs-CLI".

- **S1 — Keine Fehlermeldung, an keiner Stelle gelesen.** `load_run_facts` liest Zahlen und
  Kennungen; `error_message`, `cloud_error_message` und `RemoteCategoryClassificationRun.error_message`
  bleiben unberührt. Dort steht `str(exc)` eines fremden Systems — der einzige Fremdtext, den dieses
  Werkzeug übernehmen könnte. **Erzwingung:** der Formwächter verbietet jedes Attribut auf
  `*error_message`.
- **S2 — Dauern ja, Zeitpunkte nein.** In die Datei geht ausschließlich `duration_seconds`, nie
  `finished_at`/`started_at`. Ein Zeitpunkt wäre die einzige *neue* Klasse dieser Ausgabe: das Muster,
  wann der Haushalt nicht zu Hause war. Eine Dauer verrät keine Uhrzeit; „most recent" wird zum
  Auswählen gelesen, nicht ausgegeben.
- **S3 — Herkunft ist eine Kennung, kein Name.** `provider`, `model` und `model_revision` sind
  Anbieter- und Modellbezeichnungen, keine Personen-, Orts- oder Sehenswürdigkeitsnamen; `NULL` fällt
  weg statt als Leerstring zu erscheinen, und `cloud_models` kommt nur aus **erfolgreichen** Läufen.
- **S4 — `--out` bleibt der einzige Schreibpfad und liegt außerhalb des Repos.** Foto-Id und App-Pfad
  bleiben pseudonym (nur mit der eigenen Datenbank auflösbar), Dateiname, OpenCloud-Pfad, Ort, GPS
  und Zeitstempel fehlen. Ohne `.git` fällt `repository_root()` auf `/` zurück, also auf Ablehnung
  statt Durchlass.
- **S5 — Kein Egress, kein Kostenpfad.** Das Werkzeug baut keinen Client und importiert keinen; es
  **liest** `api_calls` einer erfolgreichen Zeile. Fehlende Cloud-Ergebnisse entstehen nur über den
  normalen Lauf mit angezeigter Schätzung, nie hier. **Erzwingung:** Formwächter gegen
  Netzwerk-/Client-Importe und gegen `add`/`delete`/`commit` im Modul.
- **S6 — Eine Summe ohne Lücke oder gar keine.** `remote_api_calls_total` bleibt `null`, sobald ein
  erfolgreicher Lauf `NULL` trägt oder keiner existiert; Landmark-Aufrufe zählen nie mit. Eine zu
  kleine Zahl trägt die Ausbauentscheidung und wäre dort eine falsche Grundlage.
- **S7 — Der Ergebnistext in 0609 ist öffentlich; die Sichtprüfung ist die einzige Kontrolle.** Eine
  *menschliche* Kontrolle auf einem nicht zurücknehmbaren Artefakt. Tragbar nur, weil die Datei die
  sensiblen Klassen gar nicht führt (S1/S2/S4): im schlimmsten Fall leckt eine Zahl, keine
  Inhaltsangabe. **Muss:** nur Zahlen und Prosa — keine Zeile je Foto, keine Foto-Id, kein
  Zweck-Sample, keine Dauer je Lauf; Herkunft, Laufzeit und Ersparnis als Kennzahl. Zahlen **je
  Motivklasse** sind erlaubt; die Klassennamen stehen ohnehin im Repository.

**Ohne Befund:** Auth, JWT, Rate-Limit, Secrets, Projektbindung und Sichtbarkeit zwischen den beiden
Nutzern unverändert; kein Endpunkt, kein Compose-`command`, keine Migration. **Eye-Egress
unverändert** (0609 S2): dieses Werkzeug spricht den `eye`-Dienst nicht an, es liest Datenbankzeilen.

`specs/architecture/0003-securitykonzept.md` ist um die Ankerzeile ergänzt.

## Tests

| Ebene | Was | Wo |
|---|---|---|
| Unit (DB-frei) | Motivzeile trägt beide Rohstärken ungerundet; exakt 0.5 → Übereinstimmung, 0.4999 → Abweichung; fehlende Seite → `null`, nie `0.0` | `test_eye_comparison.py::TestTheDeviationValues` (neu) |
| Unit | Ausschluss-/Albumzeile trägt beide `bool`/`int`; `cloud_album_level=None` erzeugt weiter keine Zeile | dito |
| Unit | Pflichtfelder ohne Vorgabewert: ein vergessenes Setzen scheitert beim Bau | dito |
| Unit | Seed-Pin aus dem Vorher-Stand (100 Abweichungen, Seed 17), `min(30,n)` je Zweck, Sortierung | `TestTheSeededSelection` (erweitert) |
| Unit | `full_report`: alter Schlüsselsatz + `origin` + `runtime`, kein Urteilsfeld, kein Zeitfeld; stdout unverändert nur Zählungen | `TestTheOutputShape` |
| Unit | `origin`: drei Listen, sortiert, dedupliziert, `NULL` raus, kein Vorkommen → `[]`; Bezugsmengen getrennt (verglichene Fotos vs. erfolgreiche Remote-Läufe) | `TestTheOrigin` (neu) |
| Unit | `runtime`-Form: `duration_seconds` als `int` (abgeschnitten), `eye_photos_*` verbatim, fehlende Läufe → `null` | `TestTheRuntime` (neu) |
| Integration (In-Memory-DB) | Filter vor Ordnung: neuerer Lauf ohne passenden Remote-Lauf verdrängt den älteren gültigen nicht; `finished_at` `NULL`, `status` ≠ success, FK `NULL`, FK auf fehlgeschlagenen Lauf, `mode` ≠ eye nie gewählt | `TestTheRunSelection` (neu) |
| Integration | Gleichstand `finished_at` → `id` absteigend; Zahlen des **verknüpften** Remote-Laufs, nicht des jüngsten | dito |
| Integration | Altzeilen: `mode=NULL` zählt als Cloud-Lauf, ist aber nie Eye-Lauf (auch mit gefüllten `eye_photos_*`) | dito |
| Integration | `remote_api_calls_total` als Vierfeldertafel (gemischt → `null`), alle `0` → `0`, `landmark_api_calls` bleibt draußen | `TestTheApiCallsTotal` (neu) |
| Integration | Projektbindung: Läufe und Kopfzeilen eines zweiten Projekts lecken nicht; Kopfzeile ohne Eye-Zeile trägt keinen Anbieter bei | `TestTheRunSelection`, `TestTheOrigin` |
| Unit (AST) | Kein Attributzugriff `*error_message` (+ Gegenproben), kein Netzwerk-/Client-Import, keine Schreibaufrufe, weiterhin genau eine Schreibstelle | `TestTheFormGuard` |
| Unit (CLI) | `main` mit erweiterten Seams: Datei trägt Laufdaten, stdout nur Zählungen, Marker aus `error_message` fehlt, kein ISO-Zeitstempel darin | `TestTheFormGuard` (bestehender Fall) |
| Unit | Repo-Grenze: jedes `.git` über dem Ziel lehnt ab, kein Arbeitsbaum lässt zu — die Lage des Pakets entscheidet nicht (Container-Fall) | `TestTheOutFileGuard` |

**Bestehende Tests, die sich ändern** (namentlich, damit der Review sie nicht als abgeschwächte
Erwartung liest): `TestTheSummary::test_names_deviation_rows_by_photo_and_purpose` (vergleicht
künftig `(photo_id, purpose)`-Paare statt ganzer `Deviation`-Bauten),
`test_the_file_report_has_a_fixed_key_set_without_a_verdict_field` (Schlüsselmenge wächst um
`origin`/`runtime`; die Urteilsfeld-Assertion bleibt wörtlich),
`test_deviations_carry_photo_id_and_app_path` (Dict je Zeile bekommt die neuen Schlüssel), sowie
jeder `full_report`-Aufruf und der `_fake_run`-Seam in `main` (neues `runs`-Argument).
`test_has_exactly_one_write_site`, `TestTheReadPath` und `TestTheThreshold` bleiben wörtlich stehen.

`specs/architecture/0002-testkonzept.md` ist um das Muster „Ein Bericht wächst um Laufdaten"
ergänzt.

## Auswertung

Der Code liefert die Zahlen; die Urteile trifft Daniel. Dieser Ablauf ist Teil der Story, nicht
Schritt einer Implementierung:

1. **Je Projekt** (mindestens zwei, verschiedene Art; je ≥ 100 Fotos mit beiden Ergebnissen) im
   Compose-Netz auf dem Heimserver, mit derselben Seed:

   ```bash
   docker compose exec backend python -m photosort.eye_comparison --project-id <id> --seed 0 --out /tmp/eye-vergleich-<projekt>.json
   ```

   stdout liefert `photos_compared` und die Zählungen je Zweck; die Datei `origin` (Anbieter,
   Cloud-Modell, Eye-Revision), `runtime` und je Abweichung beide Werte mit App-Pfad. `--out` liegt
   außerhalb des Repos; die Datei geht nicht ins Repository.
2. **Prüfmenge:** jede Zeile der Datei ist bereits die Zufallsauswahl `min(30, Abweichungen)` je
   Zweck. Daniel öffnet den App-Pfad, sieht das Foto und beide Werte und notiert je Zeile, welches
   Ergebnis trägt. Kein Foto wird von Hand gelabelt.
3. **Urteil je Zweck und Projekt:** „Eye ist besser", „gleichwertig" oder „schlechter / nicht
   geeignet", dazu die beschriebenen Beispielfälle. Für einen Ersatz der Cloud genügt
   „gleichwertig". Ein Gesamturteil gibt es nicht.
4. **Entscheidung:** „Eye bleibt" oder „Rückbau", gestützt auf die drei Urteile, Laufzeit,
   Einsparung und die Lizenz-Einstufung (0609: „klar zulässig", damit ist der
   `Rückbau`-Auslöser „unklar"/„unzulässig" nicht erfüllt). Eingespart zählt ein Cloud-Aufruf nur,
   wenn **alle drei** Zwecke mindestens „gleichwertig" sind; `remote_api_calls_total` ist die
   Obergrenze, Sehenswürdigkeitsnamen zählen nie. Bei „Rückbau" entsteht eine eigene, hier
   verlinkte Story; bei „Eye bleibt" nennt das Ergebnis die tauglichen Zwecke und den Beta-Stand als
   Restrisiko.
5. **Ergebnis:** der Abschnitt `## Vergleichsergebnis` in
   [`0609`](./0609-eye-dritte-wahl.md), mit genau diesen Feldern je Projekt: Art des Projekts, Zahl
   der Fotos mit beiden Ergebnissen, Anbieter/Modell/Eye-Revision, je Zweck Übereinstimmungen,
   Abweichungen und Größe der geprüften Auswahl, Dauer beider Läufe, `remote_api_calls_total`,
   Urteil mit Beispielen; dann die Entscheidung mit Begründung. Feinlabels und
   Sehenswürdigkeitsnamen stehen ausdrücklich als „nicht bewertet" darin.
6. **Inhaltsauflagen vor dem Push:** keine Bilddaten, Dateinamen, Pfade, Aufnahmedaten, Orte oder
   GPS-Angaben, keine Sehenswürdigkeitsnamen, Projekte als „Projekt A/B", wenn der Name einen Ort
   verrät, keine Zeile je Foto und keine Dauer je Lauf — nur Zählungen, Zwecke, Urteile und Prosa.
   Daniel liest gegen, bevor der erste Push passiert; ein Verstoß wird umformuliert, nie in einem
   späteren Commit nachgebessert.

## Entscheidungen

- **Welcher Cloud-Lauf zählt:** der jüngste erfolgreiche Lauf mit erfolgreichem Remote-Lauf, nicht
  „jüngster Lauf mit `mode=cloud`". Läufe von vor 0609 tragen `mode = NULL` und zählten sonst nie;
  Projekte, die vorher schon mit Cloud klassifiziert wurden, hätten dann keinen Cloud-Lauf.
- **Einsparung über alle Remote-Läufe:** Summe statt der Zahl eines einzelnen Laufs, weil der
  jüngste Lauf eine kleine Nachklassifizierung sein kann.
- **Gefiltert wird vor der Ordnung:** „jüngster passender Lauf" heißt nicht „jüngster Lauf, geprüft
  ob passend" — sonst verdrängte ein neuerer unpassender Lauf den älteren gültigen.
- **`null` statt Teilsumme** folgt der vorhandenen Regel „`NULL` = nicht erfasst" an den
  Kostenspalten.
- **Ganzer Lauf statt Eye-Phase als Dauer:** Für das Ende der Eye-Phase gibt es keinen Zeitstempel;
  einen einzuführen wäre eine Migration und eine Verhaltensänderung, und die schließt die Story aus.
- **Fehlende Stärke → `null`, nicht `0.0`:** „hat das Motiv nicht beurteilt" und „hat 0.0 geurteilt"
  sind genau der Unterschied, den Daniels Durchsicht braucht.
- **Abgeschnittene Sekunden statt gerundet:** projektüblicher Boden (`//`), überschätzt keine Dauer.
- **Repo-Grenze am Ziel statt am Modul:** Die Auflage bleibt („Eye-Ergebnisse gehören nicht in die
  Versionsverwaltung"), der Maßstab wandert. Ab dem Modul gemessen gilt im Container ohne `.git`
  die Wurzel `/`, und damit wäre jedes Ziel „im Repo" — der dokumentierte Aufruf schlüge fehl.
- **Diese Spec ändert das Verhalten der Anwendung nicht.** Sie ist die technische Grundlage der
  Auswertung; Urteile, Entscheidung und der Abschnitt „Vergleichsergebnis" in 0609 sind Daniels
  Handarbeit und kein Schritt für `developer`. Kein Gesamturteil, kein Empfehlungsfeld in der Datei.
- `architect` konsultiert (Schritt 1): Erweiterung des bestehenden CLI statt neuem Werkzeug;
  keine neue ADR, weil ADR 0138 Punkt 8 die Grenze (rein lesend, Datei außerhalb des Repos) bereits
  zieht.
- `ux-ui-designer` nicht konsultiert (Schritt 2): kein sichtbarer Teil der Oberfläche — die Story
  schließt eine Anzeige ausdrücklich aus (siehe `## UI/UX`).
- `test-engineer` konsultiert (Schritt 3): Teststrategie oben, 0002 um das Muster ergänzt.
- `security-engineer` konsultiert (Schritt 3): Bewertung oben, 0003 um die Ankerzeile ergänzt.

## Offene Fragen

Keine.

## Out of Scope

- Der Rückbau — eigene Story (Story-Kriterium „Folge von Rückbau").
- Eine Änderung daran, dass Eyes Albumtauglichkeit nicht in den Album-Entwurf fließt — eigene Story.
- Feinlabels-Vergleich (Vokabulare nicht vergleichbar) und eigene Anzeige der Eye-Werte bei geltender
  Cloud-Kopfzeile.
- Der frühere Auswertungsweg aus Spec 0606 mit blinden Paarvergleichsseiten; `tools/eye-eval/` ist
  mit 0609 entfallen.
- Automatische Urteile, Schwellenwerte oder Empfehlungen — die Datei trägt Zählungen und Werte, das
  Urteil schreibt ein Mensch.
