# 0050 - Ein verketteter Klassifizierungslauf mit laufbezogener Cloud-Freigabe

**Status:** Accepted
**Datum:** 2026-09-01
**Bezug:** [GitHub-Issue #296](https://github.com/TheRealKoller/photosort/issues/296), [`specs/features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md`](../features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md)

**Revidiert (nicht abgelöst):**
- [`decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md`](./0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md) Punkt 5 ("eigenständiger, explizit ausgelöster Job") und Punkt 6 (zwei getrennte Auslöse-Endpunkte). Die ADR ist bereits als Ganzes `Superseded` (durch ADR 0049); ihre hier berührte Mechanik lebt in ADR 0049 fort und wird deshalb dort mit revidiert. Die Remote-Kategorisierung bleibt ein eigener Job mit eigener Run-Tabelle — sie ist nur nicht länger **eigenständig auslösbar**, sondern ausschließlich erste Phase des verketteten Laufs.
- [`decisions/0049-festes-kategorien-set-mit-vorrangreihenfolge-und-freien-feinlabels.md`](./0049-festes-kategorien-set-mit-vorrangreihenfolge-und-freien-feinlabels.md) in dem Punkt, an dem die Remote-Klassifikations-Zeilen als "aus einem früheren, separaten `classify-categories-remote`-Lauf" stammend beschrieben sind: sie stammen künftig im Regelfall aus der ersten Phase **desselben** Laufs. Die Ableitungslogik selbst (`derive_photo_category`, `resolve_category`, `_remote_category_candidates`) bleibt unverändert.
- [`decisions/0025-cloud-landmark-erkennung.md`](./0025-cloud-landmark-erkennung.md) Punkt 5 (projektweiter Einwilligungs-Schalter als alleiniges Gate für den Cloud-Datenfluss): der projektweite Schalter bleibt die **Einwilligung**, ist aber nicht mehr allein hinreichend — er wird um eine zweite, laufbezogene Bedingung ergänzt (siehe Punkt 2). Die Richtung ist ausschließlich verschärfend.

**Berührt außerdem:** [`decisions/0021-kriterien-datenmodell-kuratierungs-pipeline.md`](./0021-kriterien-datenmodell-kuratierungs-pipeline.md) Punkt 5 (`CriterionScoringRun` als Run-Tracking) — die Tabelle bekommt drei zusätzliche Spalten und wird damit zum Run-Datensatz des **gesamten** Klassifizierungslaufs, nicht mehr nur seiner Kriterien-Phase.

## Kontext

Die Klassifizierung eines Projekts zerfällt heute in zwei getrennt auszulösende Läufe mit einer **impliziten, nur textuell erklärten Reihenfolge-Regel**: Erst `POST .../classify-categories-remote` (Kategorie-Vorschläge aus dem Cloud-Vision-Modell), dann `POST .../score-criteria` — denn `run_criterion_scoring` liest die Remote-Ergebnisse über `_remote_category_candidates` aus der Datenbank und kann sie nur dann in die Kategorieableitung einrechnen, wenn sie zum Zeitpunkt des Laufs bereits geschrieben sind. Wer die Reihenfolge nicht kennt, bekommt ein vollständiges, plausibel aussehendes Ergebnis **ohne** die Cloud-Anreicherung, ohne dass irgendetwas sichtbar fehlschlägt. Spec 0218 hat das mit einem Hinweistext nachträglich erklärt statt strukturell aufzulösen.

Verschärfend kommt hinzu, dass die Aufteilung in "lokal" und "remote" faktisch nicht stimmt. `run_criterion_scoring` enthält seit ADR 0025 selbst eine produktive Cloud-Phase (Sehenswürdigkeits-Erkennung), die immer dann mitläuft, wenn `project.cloud_vision_detection_enabled` gesetzt ist. Der Erklärtext auf der Kriterien-Seite behauptet an derselben Stelle ausdrücklich das Gegenteil ("läuft vollständig lokal auf diesem Server"). Es gibt damit **keine Stelle im Produkt, an der verlässlich erkennbar oder steuerbar wäre, ob ein Durchlauf Cloud-Kosten verursacht** — der projektweite Consent-Schalter ist eine Dauereinstellung, kein Durchlauf-Schalter, und die Kostenschätzung im Bestätigungsdialog deckt nur den Kategorie-Anteil ab.

Beide Probleme haben dieselbe strukturelle Ursache: **die Verkettung der Phasen ist Wissen im Kopf des Nutzers statt Code**, und **die Cloud-Nutzung ist ein Projektzustand statt einer Laufeigenschaft**.

## Entscheidung

### 1. Ein verketteter Lauf; die Remote-Kategorisierung wird Phase 1 statt eigener Auslöser

Ein neuer Orchestrator `worker.py::run_classification` führt beide Phasen in einem einzigen Job aus, in der fachlich einzig sinnvollen Reihenfolge:

```
run_classification(project, scoring_run_id, use_cloud)
  Phase "remote_categories"  (nur bei use_cloud)  -> run_remote_category_classification
  Phase "criteria"           (immer)              -> run_criterion_scoring
                                                        └── Cloud-Teilphase landmark (nur bei use_cloud)
                                                        └── derive_photo_category / rank_photos
```

Die Remote-Ergebnisse sind damit **im selben Lauf** geschrieben, bevor `_remote_category_candidates` sie liest — die Reihenfolge-Regel wird von einer Bedienanweisung zu einer Codezeile. Ein zweiter, manuell angestoßener Lauf ist nicht mehr nötig, und der Hinweistext aus Spec 0218 entfällt ersatzlos.

Bewusst **nicht** gewählt: die Remote-Kategorisierung in `run_criterion_scoring` hineinzuziehen. Beide Phasen behalten ihre eigene Run-Tabelle (`remote_category_classification_runs` / `criterion_scoring_runs`), ihr eigenes Concurrency-Setting, ihre eigene Best-effort-Fehlerbehandlung und ihre eigene Fortschrittszählung. Genau diese Trennung ist es, die den Teilschritt-Fortschritt in der Oberfläche überhaupt möglich macht — eine Verschmelzung hätte zwei fachlich unterschiedliche Fortschrittszähler in einen gemeinsamen gepresst.

### 2. Cloud-Nutzung wird eine Laufeigenschaft; der projektweite Consent bleibt die Einwilligung

Der Auslöser bekommt einen Parameter `use_cloud: bool`. Das Gate für **jeden** Cloud-Aufruf im Lauf ist ab sofort die Konjunktion:

```
use_cloud AND project.cloud_vision_detection_enabled
```

Beide Bedingungen müssen erfüllt sein, für beide Cloud-Anteile (Remote-Kategorisierung **und** Sehenswürdigkeits-Erkennung). Das ist eine reine Verschärfung: `use_cloud` kann nie eine fehlende Einwilligung ersetzen, sondern eine vorhandene nur für diesen einen Lauf ungenutzt lassen. Die Einwilligung selbst wird weiterhin ausschließlich über `PUT .../cloud-vision-consent` erteilt (ADR 0025 Punkt 5, unverändert).

Serverseitig wird `use_cloud=true` ohne Einwilligung mit `403` abgewiesen, statt still auf "lokal" herunterzufallen — ein Client, der Cloud-Verarbeitung anfordert, für die keine Einwilligung vorliegt, soll das erfahren. Die Prüfung im Endpunkt ist dabei nicht das Sicherheitsnetz, sondern nur die frühe, sprechende Rückmeldung: das eigentliche Muss-Kriterium ist die Konjunktion oben, ausgewertet im Worker unmittelbar vor der Client-Konstruktion.

**Fail-closed als Default:** `run_criterion_scoring` bekommt den Parameter `use_cloud: bool = False`. Ein Aufrufer, der ihn vergisst, verliert die Cloud-Anreicherung — er verursacht keine ungewollten Kosten und keinen ungewollten Datenabfluss. Der umgekehrte Default wäre bequemer für den Bestandscode, aber an einer Vertrauensgrenze die falsche Richtung.

### 3. `CriterionScoringRun` wird der Run-Datensatz des gesamten Laufs

Drei additive Spalten, eine Migration:

| Spalte | Typ | Bedeutung |
|---|---|---|
| `phase` | `ClassificationPhase \| None` | Der gerade laufende Teilschritt (`remote_categories` / `criteria`); `NULL`, sobald der Lauf beendet ist. |
| `cloud_requested` | `bool`, Default `False` | War die Cloud-Nutzung für **diesen** Lauf angefordert? Macht nachträglich erkennbar, ob ein Ergebnis überhaupt Cloud-Anreicherung enthalten kann. |
| `cloud_error_message` | `str \| None` | Menschenlesbare Zusammenfassung aller Cloud-Probleme dieses Laufs; `NULL`, wenn keines auftrat. |

Der Lauf-Datensatz wird deshalb **vom Orchestrator angelegt**, nicht mehr von `run_criterion_scoring` — sonst gäbe es während Phase 1 keinen Anker, an dem die Oberfläche den laufenden Gesamtvorgang festmachen könnte, und `last_criterion_scoring_run` zeigte weiter auf den Lauf davor. `run_criterion_scoring` nimmt den Datensatz über einen optionalen Parameter `run` entgegen und legt ihn nur dann selbst an, wenn keiner übergeben wurde.

Bewusst **keine** neue, vierte Run-Tabelle für den Gesamtlauf: sie hätte dieselben fünf Statusfelder ein drittes Mal geführt, ohne eine Frage zu beantworten, die `criterion_scoring_runs` + `phase` nicht schon beantwortet. Bewusst auch **kein** FK von `criterion_scoring_runs` auf `remote_category_classification_runs`: beide Läufe entstehen im selben Job unmittelbar nacheinander, `last_criterion_scoring_run`/`last_remote_category_classification_run` gehören damit zusammen; ein FK würde eine Zuordnung formalisieren, die nur für Altdaten aus der Zeit der getrennten Auslösung überhaupt uneindeutig war.

### 4. Cloud-Fehler brechen den Lauf nicht ab, werden aber laufweit berichtet

Der lokale Bewertungsanteil ist der Kern des Laufs und muss auch dann vollständig durchlaufen, wenn die Cloud nicht erreichbar ist. Alle Cloud-Fehler bleiben deshalb best-effort (unverändert gegenüber ADR 0025 Punkt 3 / ADR 0032 Punkt 5) — neu ist nur, dass sie zusätzlich **auf Laufebene sichtbar** werden, in `cloud_error_message` aus bis zu drei Teilen zusammengesetzt:

1. Phase 1 endete mit `failed` → deren `error_message`.
2. Der Landmark-Client ließ sich nicht konstruieren (`_try_build` → `None`) → fester Text. Dieser Fall war bisher vollständig stumm.
3. Einzelne Landmark-Aufrufe schlugen fehl → Zähl-Zusammenfassung (`N von M`), nicht N Einzelmeldungen. Die Einzelfehler bleiben pro Foto in `photo_cloud_vision_errors` abrufbar (ADR 0035) — das ist die Detailebene, `cloud_error_message` ist die Laufebene.

Der Lauf selbst endet in allen drei Fällen mit `success`, sofern der lokale Anteil durchlief: das Ergebnis ist gültig, nur nicht angereichert. `cloud_requested=true` zusammen mit einem gesetzten `cloud_error_message` ist genau das Signal, an dem die Oberfläche "ohne (vollständige) Cloud-Anreicherung entstanden" festmacht.

### 5. Ein Auslöser-Endpunkt, eine Schätzung über alle Cloud-Anteile

`POST /projects/{id}/classify` mit `{scoring_run_id, use_cloud}` ersetzt `POST .../score-criteria` **und** `POST .../classify-categories-remote`; beide werden ersatzlos entfernt (kein Redirect, kein Deprecation-Zeitraum — es gibt genau einen Client, und ein zweiter Auslöseweg wäre exakt der Zustand, den diese ADR beseitigt). Die Vorbedingungs-Prüfungen von `score-criteria` (Feature-Flag, erfolgreicher `ScoringRun`, bestätigtes Gate, `scoring_run_id`-Staleness) gelten unverändert für den gesamten Lauf.

`GET /projects/{id}/classify/estimate` ersetzt `GET .../classify-categories-remote/estimate` und schätzt **beide** Cloud-Anteile, weil die Checkbox beide freigibt:

- `remote_category_candidate_count` — unverändert über `select_remote_category_candidates`.
- `landmark_candidate_count` — Fotos, die aus den **bereits vorliegenden** `PhotoCriterionScore`-Werten heraus `criteria.py::is_landmark_candidate` erfüllen und noch keine `landmark`-Zeile haben. Dieselbe reine Funktion, die auch der Live-Lauf nutzt.
- `candidate_count` = Summe beider, `estimated_cost_usd` = `candidate_count * COST_PER_IMAGE_USD[provider]`.

Die Landmark-Zahl ist **strukturell eine Schätzung, keine Vorausberechnung**: die Landmark-Kandidaten des kommenden Laufs ergeben sich aus Kriterien-Werten, die in diesem Lauf erst neu berechnet werden. Vor dem allerersten Lauf eines Projekts liegen gar keine Vorwerte vor und die Zahl ist 0. Das ist vertretbar, weil die Zahl als Schätzung ausgewiesen ist und weil ein Foto, das schon einmal Landmark-Kandidat war, es in aller Regel bleibt — und es ist der einzige Weg, der ohne einen vorgezogenen, kompletten lokalen Bewertungslauf auskommt. Die Alternative (Landmark-Anteil gar nicht schätzen) wurde verworfen: sie hätte die Schätzung erneut nur einen Teil der freigegebenen Kosten abdecken lassen, also genau den Zustand konserviert, den diese ADR beseitigt.

Beide Anteile werden mit demselben `COST_PER_IMAGE_USD` bewertet. Der Landmark-Prompt ist kürzer als der Kategorie-Prompt, die Bild-Tokens dominieren beide (siehe Herleitung in `remote_classification.py`) — die Schätzung überschätzt damit eher, und das ist bei einer Freigabeentscheidung die richtige Richtung.

### 6. Kein Bestätigungsdialog mehr; die Schätzung am Auslöser tritt an seine Stelle

ADR 0032 Punkt 8 forderte eine Kostenschätzung **vor** dem Lauf, nicht einen Dialog — diese Anforderung bleibt vollständig erfüllt, weil die Schätzung unmittelbar an der Checkbox steht und dort dauerhaft sichtbar ist, statt erst nach einem Klick aufzutauchen. Der Dialog verschwindet ersatzlos; das Design-System-Muster "Bestätigungsdialog vor kostenpflichtiger Aktion" wird entsprechend nachgezogen.

**Bewusst in Kauf genommenes Restrisiko** (Produktentscheidung aus der Story, hier nur festgehalten): ohne Dialog und mit vorausgewählter Checkbox löst ein einzelner Klick Cloud-Kosten aus. Abgefedert wird das ausschließlich durch die dauerhaft am Auslöser sichtbare Schätzung — die damit vom flüchtigen Dialoginhalt zur ständigen Anzeige aufgewertet wird.

## Begründung

Die beiden Kernprobleme sind Reihenfolgen-Wissen und unsichtbare Kosten. Beide lassen sich nur an der Stelle lösen, an der sie entstehen: die Reihenfolge gehört in den Code, die Kostenentscheidung an den Auslöser. Jede Zwischenlösung (besserer Hinweistext, Warnung bei "falscher" Reihenfolge, zweiter Consent-Schalter) hätte die Kopplung erhalten und nur zusätzlich erklärt.

Die drei zusätzlichen Spalten auf `criterion_scoring_runs` sind der kleinste Eingriff, der die drei neuen Fragen der Oberfläche beantwortet ("welcher Teilschritt läuft", "durfte dieser Lauf in die Cloud", "ist dabei etwas schiefgegangen"), ohne eine vierte Run-Tabelle und ohne die bestehende, gut abgedeckte Best-effort-Mechanik der beiden Phasen anzufassen.

## Konsequenzen

- **Positiv:** Die Reihenfolge-Regel ist nicht mehr lernbar-oder-nicht, sondern strukturell garantiert. Die Cloud-Nutzung ist erstmals pro Durchlauf entscheidbar **und** vollständig beziffert. Die Aussage "läuft vollständig lokal auf diesem Server" wird erstmals wahr — nämlich genau dann, wenn die Checkbox abgewählt ist. Ein bisher stummer Fehlerfall (Landmark-Client nicht konstruierbar) wird sichtbar.
- **Negativ / bewusst getragen:** Ein Lauf dauert bei aktivierter Cloud-Nutzung länger als eine der beiden bisherigen Einzelphasen — die Gesamtdauer bis zum verwertbaren Ergebnis sinkt jedoch, weil der bisher nötige zweite Bewertungslauf entfällt. Die Remote-Kategorisierung lässt sich nicht mehr isoliert wiederholen; wer nur sie erneut braucht, zahlt den lokalen Bewertungsanteil mit (Rechenzeit, keine Kosten). Die Landmark-Schätzung ist vor dem ersten Lauf eines Projekts 0 und damit dort systematisch zu niedrig.
- **Folgearbeit:** Issue #297 (Sehenswürdigkeits-Erkennung als eigener Auslöser mit eigener Kostenschätzung) bleibt eigenständig und wird durch diese ADR weder vorweggenommen noch verbaut: sie gibt der Sehenswürdigkeits-Erkennung keinen eigenen Auslöser, sondern nimmt sie nur mit unter die gemeinsame Checkbox.
