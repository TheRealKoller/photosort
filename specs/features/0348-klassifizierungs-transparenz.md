# 0348 - Transparenz über den Klassifizierungsprozess

**Status:** Implemented ([PR #367](https://github.com/TheRealKoller/photosort/pull/367))
**Erstellt:** 2026-09-09
**Bezug:** [Issue #348](https://github.com/TheRealKoller/photosort/issues/348)

## Ziel

Die Klassifizierung eines Projekts kann Fotos an einen Cloud-Anbieter senden und dabei echtes Geld kosten. Die Cloud-Nutzung ist inzwischen pro Durchlauf an- und abwählbar, und eine Kostenschätzung steht vor dem Start sichtbar daneben (Story #296). Was fehlt, ist Einblick in den Vorgang selbst — an drei Stellen:

**Vor dem Start** erscheint nur eine Gesamtsumme. Es ist nicht erkennbar, welcher Anteil auf die Kategorie-Vorschläge und welcher auf die Sehenswürdigkeits-Erkennung entfällt und mit welchem Anbieter und Modell gerechnet wurde. Beim allerersten Durchlauf eines Projekts ist der Anteil der Sehenswürdigkeits-Erkennung in der Schätzung überhaupt nicht enthalten — es entstehen also Kosten, die die Schätzung nicht angekündigt hat.

**Während des Laufs** ist nur erkennbar, ob gerade die Remote-Kategorisierung oder die Kriterien-Bewertung läuft. Die Sehenswürdigkeits-Erkennung ist kein sichtbarer Schritt, sondern läuft unbemerkt innerhalb der Kriterien-Bewertung — und währenddessen bewegt sich der Fortschritt überhaupt nicht. Ein langer Durchlauf ist in dieser Phase von einem hängengebliebenen nicht zu unterscheiden.

**Nach dem Lauf** bleibt offen, was tatsächlich passiert ist: wie viele Fotos wirklich an die Cloud gingen, wie viele Antworten zurückkamen, was der Durchlauf am Ende gekostet hat und mit welchem Modell er gerechnet hat. Diese Werte werden bereits erfasst, sind aber nirgends abrufbar. Die Projekt-Statistikseite zeigt ausschließlich projektweite Summen über alle Läufe hinweg, nicht das Ergebnis dieses einen Durchlaufs.

Ziel ist, dass ein Klassifizierungslauf von der Kostenabschätzung bis zur Abrechnung nachvollziehbar ist — vor, während und nach der Ausführung, an der Stelle, an der er ausgelöst wird.

## User Story

Als Betreiber der PhotoSort-Installation möchte ich vor, während und nach einem Klassifizierungslauf nachvollziehen können, was mit meinen Fotos geschieht und was es kostet, damit ich die Cloud-Nutzung bewusst freigeben, einen laufenden Durchlauf richtig einschätzen und im Nachhinein prüfen kann, ob Aufwand und Ergebnis zusammenpassen.

## Akzeptanzkriterien

**Vor dem Start: aufgeschlüsselte Schätzung**

- [ ] Die Kostenschätzung am Auslöser weist die beiden Cloud-Anteile getrennt aus — Kategorie-Vorschläge und Sehenswürdigkeits-Erkennung — jeweils mit Fotoanzahl und geschätztem Betrag, zusätzlich zur Gesamtsumme.
- [ ] Anbieter und Modell, auf denen die Schätzung beruht, sind vor dem Start erkennbar.
- [ ] Solange für das Projekt noch **kein Klassifizierungslauf erfolgreich abgeschlossen** wurde, weist die Schätzung den Anteil der Sehenswürdigkeits-Erkennung als unbekannt aus — nicht als 0 — und sagt dazu, dass dieser Anteil trotzdem Kosten verursacht. Ein laufender oder fehlgeschlagener Durchlauf gilt dabei nicht als stattgefunden.
- [ ] Erkennbar bleibt, dass es sich um eine Schätzung handelt und nicht um eine Abrechnung.

**Während des Laufs: sichtbare Teilschritte mit konkreten Werten**

- [ ] Die Sehenswürdigkeits-Erkennung ist ein eigener, benannter Teilschritt des Durchlaufs statt eines unsichtbaren Teils der Kriterien-Bewertung.
- [ ] Jeder Teilschritt zeigt seinen eigenen Fortschritt aus eigenen Zählern. Während der Sehenswürdigkeits-Erkennung wird der Fortschritt **mindestens einmal je parallel abgearbeitetem Aufruf-Block** fortgeschrieben und gespeichert, gemeinsam mit dem Fortschritts-Zeitstempel des Laufs; ein laufender Durchlauf ist dadurch von einem stehengebliebenen unterscheidbar und wird auch nicht mehr fälschlich als hängend abgeräumt.
- [ ] Während eines Cloud-Teilschritts ist erkennbar, wie viele Cloud-Aufrufe bereits abgesetzt wurden und an welchen Anbieter mit welchem Modell sie gehen.
- [ ] Fehlgeschlagene Einzelaufrufe sind bereits während des Laufs erkennbar, nicht erst nach seinem Abschluss.

**Nach dem Lauf: Bilanz des Durchlaufs**

- [ ] Nach Abschluss steht an der Stelle, an der der Lauf ausgelöst wurde, eine Bilanz dieses einen Durchlaufs.
- [ ] Die Bilanz nennt je Cloud-Teilschritt: wie viele Fotos gesendet wurden, wie viele Antworten verwertet werden konnten, wie viele Aufrufe fehlgeschlagen sind, was der Teilschritt tatsächlich gekostet hat und welches Modell dabei verwendet wurde.
- [ ] Die Bilanz nennt die Grundlage ihres Kostenbetrags: das verwendete Modell und den abgerechneten Tokenverbrauch, aus dem der Betrag entstanden ist. Der Preis je Bild bleibt der Schätzung vorbehalten und wird in der Bilanz nicht als Abrechnungsgrundlage dargestellt.
- [ ] Die tatsächlich angefallenen Kosten sind gegen die Schätzung vor dem Start einordenbar.
- [ ] Lief der Durchlauf ohne Cloud-Nutzung, sagt die Bilanz das verständlich, statt leere Felder oder Nullwerte zu zeigen.
- [ ] Ist für das verwendete Modell kein Preis hinterlegt, wird das benannt, statt einen Betrag zu erfinden.
- [ ] Die Bilanz beschreibt den zuletzt abgeschlossenen Durchlauf. Eine Historie früherer Läufe ist nicht Teil dieser Story.

**Abgrenzung und Darstellung**

- [ ] Die Projekt-Statistikseite bleibt unverändert und behält ihre Rolle als projektweite Auswertung über alle Läufe hinweg.
- [ ] Der Auslöser selbst und die Steuerung der Cloud-Nutzung bleiben unverändert. Diese Story fügt keinen zweiten Auslöser hinzu und ändert nicht, wann Cloud-Aufrufe stattfinden oder welche Fotos die Installation verlassen.
- [ ] Unterhalb des Auslösers steht zu jedem Zeitpunkt **genau einer** der beiden Zustandsblöcke — Fortschrittsliste oder Bilanz, nie beide gleichzeitig. Auslöser und Cloud-Checkbox bleiben die ersten Bedienelemente der Sektion; die Detailwerte stehen als Sekundärzeilen unter dem jeweiligen Namen und erzeugen auf schmalen Viewports kein horizontales Scrollen.

## Datenmodell-Bezug

Betroffen sind die beiden Lauf-Tabellen `criterion_scoring_runs` und `remote_category_classification_runs` (siehe [`docs/architecture.md`](../../docs/architecture.md)). Der Eingriff ist rein additiv: sechs nullable Spalten plus ein Fremdschlüssel, keine Datenmigration, kein Backfill. Details in ADR [`0068`](../decisions/0068-klassifizierungslauf-vier-teilschritte-und-laufeigene-cloud-bilanz.md) und im Abschnitt „Architektur / Umsetzung".

## Architektur / Umsetzung

Architektonischer Ansatz und Begründung vollständig in der ADR [`decisions/0068-klassifizierungslauf-vier-teilschritte-und-laufeigene-cloud-bilanz.md`](../decisions/0068-klassifizierungslauf-vier-teilschritte-und-laufeigene-cloud-bilanz.md) (löst ADR [`0050`](../decisions/0050-verketteter-klassifizierungslauf-mit-laufbezogener-cloud-freigabe.md) Punkt 3 im Absatz „Kein FK zwischen den beiden Run-Tabellen" teilweise ab). Kurzfassung:

**Der tragende Befund:** Es fehlt keine Information — Aufrufzahl, Tokens, Betrag und Modell je Cloud-Phase liegen seit ADR 0051/0059 an den Lauf-Zeilen, die Anteile der Schätzung liegen seit ADR 0050 in der Estimate-Antwort. Es fehlt ihre **Zuordnung zu einem Durchlauf** und ihr Weg an die Oberfläche. Der Eingriff ist deshalb überwiegend additiv (Spalten, Lesesichten), nicht rechnerisch.

### 1. Vier benannte Teilschritte (`worker.py`, `models.py`)

`ClassificationPhase` bekommt zwei Werte, in Ausführungsreihenfolge:

```
remote_categories  ->  criteria  ->  landmark  ->  ranking
```

`ranking` (Kategorieableitung + `rank_photos` + Schreiben der `PhotoRanking`-Zeilen) ist nötig, damit die Abfolge monoton bleibt: dieser Teil gehört fachlich zur Kriterien-Phase, läuft aber **nach** der Landmark-Phase; ohne eigenen Namen bliebe `phase` dort auf `landmark` bei 100 % Fortschritt stehen — genau das gemeldete Symptom, nur eine Phase später. `NULL` behält unverändert die Bedeutung „läuft nicht mehr". Der Wertebereich liegt als `VARCHAR(20)` ohne DB-Prüfeinschränkung vor (`SQLEnum(..., native_enum=False)`) — **für die zwei neuen Werte ist keine Migration nötig**.

Phasenwechsel in `run_criterion_scoring`: `phase = LANDMARK` beim Betreten des `if use_cloud and project.cloud_vision_detection_enabled and rows:`-Blocks (vor `_try_build`), `phase = RANKING` unmittelbar danach, vor `_remote_category_candidates(...)`.

### 2. Live-Zähler als eigene Spalten — niemals die Kosten-Buchführung fortschreiben

`api_calls`/`landmark_api_calls` bleiben unangetastet bei „einmal am Phasenende, im `finally`" (ADR 0051 Punkt 4). Sie laufend hochzuzählen würde ADR 0051 Punkt 5 **Befund (b)** (`api_calls > 0` bei Betrag `0`/`NULL` = Erfassungslücke) bei jedem laufenden Cloud-Lauf auslösen und die Statistikseite mit einem falschen Unvollständigkeits-Vorbehalt einfärben.

Neue Spalten, alle **nullable mit Python-Default `None`** (`ScanRun.total_files`-Idiom: `NULL` = nicht erfasst/Phase nicht betreten, `0` = erfasst, nichts passiert), auf `0` gesetzt beim **Betreten** der Phase, danach je Block fortgeschrieben:

| Tabelle | Spalte | Bedeutung |
|---|---|---|
| `criterion_scoring_runs` | `landmark_photos_total` | Kandidatenzahl der Landmark-Phase; zugleich **Marker**, ob dieser Teilschritt stattfand |
| `criterion_scoring_runs` | `landmark_photos_processed` | abgesetzte Aufrufe (Erfolge + Fehlschläge), live |
| `criterion_scoring_runs` | `landmark_failed_calls` | fehlgeschlagene Einzelaufrufe, live |
| `criterion_scoring_runs` | `estimated_cost_usd` | die Schätzung, mit der dieser Lauf gestartet wurde (Punkt 5) |
| `criterion_scoring_runs` | `remote_category_classification_run_id` | FK auf `remote_category_classification_runs.id` (Punkt 3) |
| `remote_category_classification_runs` | `failed_calls` | fehlgeschlagene Einzelaufrufe, live |

Die Landmark-Schleife bekommt damit erstmals **Commit-Punkte innerhalb des Blocks** (bisher erst der `finally`): je `asyncio.gather`-Block `landmark_photos_processed`, `landmark_failed_calls` **und `last_progress_at`** setzen und committen — dasselbe Muster wie in `run_remote_category_classification`. Das schließt nebenbei einen bestehenden Defekt: `last_progress_at` wurde während der gesamten Landmark-Phase nicht angefasst, ein Lauf mit mehr als `STALL_THRESHOLD` (15 min) Landmark-Arbeit wurde von `reap_stalled_runs` als hängend abgeräumt, obwohl er arbeitete. In der Remote-Phase wird `failed_calls` am bereits vorhandenen Block-Commit-Punkt mitgeschrieben.

Invariante für Läufe ab dieser Migration: `photos_processed == api_calls + failed_calls` (per Test festgeschrieben, damit der Live-Zähler und die Kosten-Buchführung nicht auseinanderlaufen).

### 3. Fremdschlüssel vom Klassifizierungslauf auf seinen Remote-Lauf

`run_classification` legt den `RemoteCategoryClassificationRun` selbst an und reicht ihn per neuem `run: RemoteCategoryClassificationRun | None = None` in `run_remote_category_classification` hinein — exakt das Muster, das ADR 0050 Punkt 3 bereits für `CriterionScoringRun`/`run_criterion_scoring` eingeführt hat, eine Ebene tiefer. Der FK wird **vor** dem Start von Phase 1 gesetzt und committet, damit die Oberfläche schon während der Remote-Phase einen Anker hat. Beim Direktaufruf (Tests) legt `run_remote_category_classification` die Zeile weiterhin selbst an.

Grund für die Umkehr von ADR 0050: die Heuristik „jüngste Remote-Zeile des Projekts" ordnet einem Lauf ohne Cloud-Phase die Zahlen des Laufs davor zu — bei einer Anzeige, die einen **Geldbetrag** einem Durchlauf zuschreibt, ist das falsch, nicht nur ungenau. Die Löschreihenfolge in `project_deletion.py` passt bereits (`criterion_scoring_runs` vor `remote_category_classification_runs`); ein Test hält das fest.

### 4. Eine Struktur für Live-Fortschritt und Bilanz (`api/projects.py`)

Neues Antwortmodell, geschlüsselt über den bereits vorhandenen `CloudVisionPhase`-Enum (`landmark`/`remote_category`, dieselbe Schlüsselung wie `CostByPurposeOut` der Statistikseite):

```python
class CloudPhaseSummaryOut(BaseModel):
    purpose: CloudVisionPhase
    photos_total: int | None
    photos_processed: int | None      # abgesetzte Aufrufe – bewegt sich live
    failed_calls: int | None          # bewegt sich live
    responses_used: int | None        # api_calls, erst am Phasenende
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None            # eingefroren; None = kein Preis/nicht erfasst
    model: str | None
    provider: str | None              # abgeleitet, siehe Punkt 6
```

`CriterionScoringRunSummary` bekommt additiv:

- `cloud_phases: list[CloudPhaseSummaryOut]` — Reihenfolge `remote_category`, dann `landmark`; ein Eintrag entsteht, sobald die Phase betreten wurde (Remote: FK gesetzt; Landmark: `landmark_photos_total is not None`). **Leere Liste = dieser Durchlauf hatte keinen Cloud-Teilschritt.**
- `estimated_cost_usd: float | None`
- `cloud_cost_total_usd: float | None` — Summe der Beträge; `None`, sobald ein beteiligter Anteil `None` ist (die Regel „unvollständig ≠ 0" bleibt serverseitig an einer Stelle, wie `CostOut.total_usd`).

Während des Laufs ist das die Fortschrittsanzeige, danach die Bilanz — **derselbe Datensatz zu zwei Zeitpunkten**, keine zweite Struktur, kein neuer Endpunkt, keine zweite Poll-Schleife (alles hängt an dem `ProjectOut`, das die Seite ohnehin alle 2 s pollt).

`ProjectOut.last_remote_category_classification_run` **entfällt ersatzlos** (einziger Leser war die Fortschrittsanzeige). `_to_project_out` ersetzt `_latest_remote_category_classification_run(...)` durch ein `session.get` über den FK — Query-Anzahl unverändert. Die Polling-Bedingung in `useProjects.ts` fällt auf den Klassifizierungslauf zusammen (er ist während des gesamten verketteten Laufs `running`).

### 5. Die Schätzung des Laufs wird am Lauf eingefroren

Ohne sie ist „die tatsächlichen Kosten sind gegen die Schätzung einordenbar" nach dem Lauf unerfüllbar: die Schätzung rechnet über den **noch offenen** Kandidatenbestand, den genau dieser Lauf gerade abgearbeitet hat — unmittelbar danach schätzt derselbe Endpunkt nahe null.

`POST /projects/{id}/classify` berechnet den Betrag serverseitig mit denselben Helfern wie `GET .../classify/estimate` (`_count_remote_category_candidates`, `_count_landmark_candidates`, `estimate_usd_per_image`) und reicht ihn als Job-Argument durch: `enqueue_job("classify", project_id, scoring_run_id, use_cloud, estimated_cost_usd)`; `worker.classify(...)`/`run_classification(..., estimated_cost_usd: float | None = None)` schreibt ihn beim Anlegen der Lauf-Zeile. Default `None` in der Job-Signatur, damit ein zum Deployment-Zeitpunkt bereits eingereihter Job nicht scheitert. Bei `use_cloud=false` wird `NULL` geschrieben (nicht `0.0` — niemand hat diese Aussage getroffen).

Verworfen: den angezeigten Betrag vom Client mitschicken (ungeprüfter Geldwert über die Vertrauensgrenze) und der Worker schätzt selbst neu (dritte Kopie der Kandidaten-Zählung, bricht die bewusste Modulgrenze „API zählt für die Schätzung, Worker selektiert für den Lauf").

### 6. Anbieter aus dem gespeicherten Modell ableiten, Modell früher schreiben

Neue reine Funktion `cloud_vision.py::provider_for_vision_model(model: str) -> str | None` (Rückwärtssuche über `VISION_MODELS_BY_PROVIDER`, `None` bei unbekanntem/entferntem Modell). **Nie** `settings.landmark_provider` für einen vergangenen Lauf lesen — die aktuelle Betriebseinstellung sagt nichts darüber, womit gerechnet wurde (genau die Verwechslung, die ADR 0059 behoben hat).

Damit Modell/Anbieter schon **während** eines laufenden Cloud-Teilschritts dastehen, wandert das Schreiben von `run.landmark_model` bzw. `run.model` aus dem `finally` an den **Phasenanfang**, direkt nach der einmaligen Auflösung `settings.resolved_landmark_model()` — derselbe lokale Wert, der den Client baut und die Kosten rechnet (ADR 0059 Punkt 7 unverändert), nur früher committet. Der **Betrag** bleibt im `finally` und am Phasenende eingefroren.

### 7. Aufgeschlüsselte Schätzung, „nicht schätzbar" als eigener Wert

`ClassificationEstimateOut` wird umgebaut (ein Client, deshalb ersetzt statt akkumuliert — die bisherigen Flachfelder `remote_category_candidate_count`/`landmark_candidate_count` gehen darin auf):

```python
class ClassificationEstimatePartOut(BaseModel):
    candidate_count: int | None       # None = nicht verlässlich schätzbar
    estimated_cost_usd: float | None  # None = kein Preis hinterlegt ODER Anteil nicht schätzbar

class ClassificationEstimateOut(BaseModel):
    provider: str
    model: str
    price_per_image_usd: float | None
    remote_categories: ClassificationEstimatePartOut
    landmark: ClassificationEstimatePartOut
    candidate_count: int              # Summe der BEKANNTEN Anteile (untere Schranke)
    estimated_cost_usd: float | None
```

`landmark.candidate_count` ist `None`, solange im Projekt **kein** `CriterionScoringRun` mit `status = success` existiert: vor dem ersten Lauf gibt es keine gespeicherten Kriterienwerte, aus denen sich Landmark-Kandidaten ableiten ließen, und die heutige `0` behauptet dort Kostenfreiheit für einen Anteil, der gleich Geld kostet. Dieselbe `null`-Semantik wie `price_per_image_usd` seit ADR 0059 Punkt 4 — `null` heißt „unbekannt", nie „kostenlos". Die Zweig-Reihenfolge des Gesamtbetrags bleibt wie heute (`candidate_count == 0` zuerst, dann `price is None`, Copilot-Fund PR #341); je Anteil gilt dieselbe Reihenfolge, ergänzt um „Anteil unbekannt → `None`".

Kein neuer Rechenweg: beide Anteile werden mit demselben `price_per_image_usd` multipliziert (die bewusste Grobheit „ein Preis je Bild für beide Cloud-Anteile", ADR 0059 Punkt 3, bleibt unverändert und wird an der Oberfläche als solche benannt).

### 8. Frontend

Die Ableitung „welche Teilschritte hat dieser Lauf, in welchem Zustand, mit welchem Fortschritt" kommt in ein **reines, unit-getestetes Modul** statt in JSX:

`frontend/src/utils/classificationSteps.ts`

```ts
// Alias auf den API-Typ statt eines eigenen Unions: eine Quelle, die `tsc` gegen die Antwort
// bindet — zwei getrennte Aufzählungen derselben vier Werte liefen auseinander.
export type ClassificationStepId = ClassificationPhase
export type ClassificationStepState = 'pending' | 'running' | 'done' | 'skipped'
export interface ClassificationStep {
  id: ClassificationStepId
  label: string
  state: ClassificationStepState
  processed: number | null
  total: number | null                       // null -> unbestimmter Fortschritt (ranking)
  cloud: CloudPhaseSummaryOut | null
}
export function deriveClassificationSteps(run: CriterionScoringRunSummary): ClassificationStep[]
```

Regeln: feste Reihenfolge `PHASE_ORDER`; Schritte vor `phase` = `done`, danach = `pending`; die beiden Cloud-Schritte erscheinen nur bei `cloud_requested === true` und gelten als `skipped`, wenn der Lauf beendet ist und kein zugehöriger `cloud_phases`-Eintrag existiert (deckt den schmalen Fall „Einwilligung zwischen Auslösen und Start entzogen" und Altläufe ab). Fortschrittsquellen: `remote_categories`/`landmark` aus dem jeweiligen `cloud_phases`-Eintrag, `criteria` aus `run.photos_total/photos_processed`, `ranking` unbestimmt.

Komponenten (flach in `components/`, `Classification*`-Präfix — die bestehende Konvention, Unterordner gibt es nur für `ui/`):

- `ClassificationSection.tsx` bleibt der Container (Checkbox-Zustand, Gate, Mutation, Auslöser) und delegiert die drei neuen Blöcke.
- `ClassificationEstimate.tsx` — aufgeschlüsselte Schätzung inkl. Anbieter/Modell und der „nicht schätzbar"-Aussage.
- `ClassificationProgress.tsx` — Teilschrittliste aus `deriveClassificationSteps`, je Schritt eigener Fortschritt; beim laufenden Cloud-Schritt zusätzlich abgesetzte Aufrufe, Fehlschläge, Anbieter/Modell.
- `ClassificationBalance.tsx` — Bilanz des zuletzt abgeschlossenen Laufs aus `cloud_phases` + `estimated_cost_usd` + `cloud_cost_total_usd`.

**Eine Währungsformatierung im Produkt:** das lokale `formatUsd` in `ClassificationSection.tsx` (`$1.23`) entfällt, alle Beträge dieser Sektion nutzen `utils/formatStats.ts::formatUsd` (`1,23 USD`, inkl. `< 0,01 USD`-Regel). Zwei Formate direkt nebeneinander unterliefen genau das Akzeptanzkriterium „tatsächliche Kosten gegen die Schätzung einordenbar".

`api/types.ts` spiegelt alle neuen Modelle (`| null` statt `?? 0`, damit `tsc` die Behandlung der Unbekannt-Fälle erzwingt). `KriterienStepPage.tsx` bleibt unverändert (eine Sektion).

### 9. Was ausdrücklich nicht angefasst wird

- `api/stats.py` und `ProjectStatsPage.tsx`: kein Feld, keine Query, keine Aussage. Die Statistikseite bleibt die projektweite Auswertung.
- Auslöser, Checkbox, Consent-Gate, Cloud-Aufruf-Zeitpunkte, was ein Request enthält (weiter ausschließlich die auf 2048 px begrenzte `display`-Variante), `pricing.py`-Werte, Prompt, Provider-Dispatch.
- `photo_cloud_vision_errors`/ADR 0035: bleibt der Ort der Einzelfehler je Foto; die neuen Zähler sind Laufebene, keine zweite Fehlerquelle.

### Betroffene Dateien

- `backend/src/photosort/models.py` — zwei `ClassificationPhase`-Werte, fünf Spalten + FK an `CriterionScoringRun`, eine Spalte an `RemoteCategoryClassificationRun`, Relationship.
- `backend/alembic/versions/<rev>_classification_run_transparency.py` — neu, `down_revision = 'a3b4c5d6e7f8'` (aktueller Head). Rein additiv, kein `server_default`, kein Backfill, kein Datenverlust; `batch_alter_table` wie in `5ab22032843c`.
- `backend/src/photosort/cloud_vision.py` — `provider_for_vision_model` (rein, kein `photosort.config`-Import — die Regel aus ADR 0059 Punkt 2 gilt unverändert).
- `backend/src/photosort/worker.py` — `run_classification` (Remote-Run-Anlage + FK + `estimated_cost_usd`), `run_criterion_scoring` (Phasen `landmark`/`ranking`, Live-Zähler, `last_progress_at`, Modell-Frühschreibung), `run_remote_category_classification` (`run`-Parameter, `failed_calls`, Modell-Frühschreibung), `classify`-Job-Signatur.
- `backend/src/photosort/api/projects.py` — `CloudPhaseSummaryOut`, erweitertes `CriterionScoringRunSummary`, umgebautes `ClassificationEstimateOut`, `estimate_classification`, `trigger_classify` (Schätzung berechnen + durchreichen), `_to_project_out`; das Antwortfeld `last_remote_category_classification_run` und sein Modell `RemoteCategoryClassificationRunSummary` entfallen. Der Helfer `_latest_remote_category_classification_run` **bleibt** — er hat einen zweiten Leser (den 409-Wächter der Projektlöschung); es entfällt nur seine Verwendung in `_to_project_out`.
- `backend/src/photosort/demo_state.py` — die neuen Spalten im „bewertet"-Projekt so setzen, dass die Bilanz im Prüfstack/`browse-app` sichtbar ist (ein Lauf mit Cloud-Anteil samt verknüpftem Remote-Lauf); das bestehende „ohne Cloud"-Szenario bleibt in einem der anderen Projekte erhalten.
- `frontend/src/api/types.ts`, `frontend/src/hooks/useProjects.ts`.
- `frontend/src/utils/classificationSteps.ts` (neu), `frontend/src/components/ClassificationEstimate.tsx` (neu), `ClassificationProgress.tsx` (neu), `ClassificationBalance.tsx` (neu), `ClassificationSection.tsx` (Umbau zum Container).
- `docs/architecture.md` (Datenmodell + Komponenten + „Letzte Aktualisierung", im selben PR).

### Umsetzungsreihenfolge (TDD, rot vor grün)

1. `models.py` + Migration (Spalten, FK, Enum-Werte) — Migration-Round-Trip-Test.
2. `worker.py`: Phasenfolge und Live-Zähler inkl. `last_progress_at` (Worker-Tests: Phasenwerte, Zähler bewegen sich, Fehlschläge werden gezählt, `photos_processed == api_calls + failed_calls`).
3. `worker.py`: Remote-Run-Anlage in `run_classification` + FK + Modell-Frühschreibung; Regressionstest, dass ein Lauf ohne Cloud-Phase **keinen** FK setzt.
4. `cloud_vision.py::provider_for_vision_model` (reine Funktion, Invariantentest gegen die Registry).
5. `api/projects.py`: Estimate-Umbau (Anteile, `null`-Semantik) — API-Tests.
6. `api/projects.py`: `cloud_phases`/`estimated_cost_usd`/`cloud_cost_total_usd` an der Run-Zusammenfassung, `trigger_classify`-Durchreichung, Entfernen des alten Feldes.
7. `demo_state.py`.
8. Frontend: `classificationSteps.ts` (pure, zuerst), dann Typen/Hook, dann `ClassificationEstimate` → `ClassificationProgress` → `ClassificationBalance` → Container-Verdrahtung.
9. `docs/architecture.md`.

## UI/UX

Die Sektion zeigt die vier Teilschritte der Klassifizierung in fester Reihenfolge, je mit eigenem Zustand und Fortschritt. Auslöser und Cloud-Checkbox bleiben unverändert im Vordergrund; die zusätzlichen Angaben sind vertikal in drei Blöcken angeordnet. Grundlage ist das Design-System [`architecture/0004-design-system.md`](../architecture/0004-design-system.md); es kommen ausschließlich vorhandene Bausteine (`Progress`, `Alert`, `StatusDot`, `Button`) und vorhandene Tokens zum Einsatz.

### 1. `ClassificationEstimate.tsx` — aufgeschlüsselte Schätzung (vor dem Start)

Bleibt an seiner heutigen Stelle **vor** dem Auslöser-Button, damit die Kosten sichtbar sind, während der Nutzer ihn betätigt. Sichtbar nur bei angewählter Cloud-Checkbox. Darstellung als schlichte Textspalten-Auflistung, nicht als Diagramm:

- Kopfzeile „Kostenvorschau" (`text-sm font-semibold`, `--text-h`).
- Je Anteil eine Zeile — „Kategorie-Vorschläge" und „Sehenswürdigkeits-Erkennung" — mit Name (links, `text-sm`, `--text`), Fotoanzahl (rechtsbündig, `text-xs`, `--text-muted`) und Betrag (rechtsbündig, `text-sm`, `--text-h`, formatiert mit `formatUsd`).
- Abschlusszeile „Gesamtsumme" mit dem Gesamtbetrag, hervorgehoben.
- Darunter klein (`text-xs`, `--text-muted`) Anbieter und Modell, auf denen die Schätzung beruht.

Die drei Unbekannt-Fälle werden ausdrücklich benannt statt als `0` dargestellt:

- **Landmark-Anteil vor dem ersten Lauf** (`landmark.candidate_count === null`): statt Zahl und Betrag der Text „Menge noch unbekannt — für dieses Projekt gab es noch keinen Durchlauf. Dieser Anteil verursacht trotzdem Kosten." (`text-xs`, `--text-muted`). Entscheidend ist der zweite Satz: Eine bloße Leerstelle liest sich sonst wie „fällt nicht an".
- **Kein hinterlegter Preis** (`price_per_image_usd === null`): unter der Gesamtsumme „Für dieses Modell ist kein Preis hinterlegt — die Kosten lassen sich nicht schätzen." Nicht als Fehler eingefärbt, und der Auslöser bleibt bedienbar.
- **Schätzcharakter**: dauerhaft sichtbarer Abschlusshinweis „Schätzung, keine Abrechnung — die tatsächlichen Kosten können abweichen." (`text-xs`, `--text-muted`). Ergänzend wird die bewusste Grobheit benannt, dass beide Cloud-Anteile mit demselben Preis je Bild gerechnet werden.

### 2. `ClassificationProgress.tsx` — Teilschrittliste während des Laufs

Vier Zeilen in fester Reihenfolge (`remote_categories` → `criteria` → `landmark` → `ranking`), sichtbar, solange der Lauf läuft. Je Zeile:

- **Statuszeichen** links, das den Zustand nicht allein über Farbe trägt: `pending` ein Kreis-Umriss in `--text-muted` (Zeile insgesamt gedämpft), `running` ein Spinner in `--accent`, `done` ein Haken in `--accent`, `skipped` ein durchgestrichener Kreis in `--border-control` (Zeile gedämpft).
- **Name** des Teilschritts (`text-sm`, `--text-h`), darunter bei einem Cloud-Teilschritt eine Detailzeile (`text-xs`, `--text-muted`): laufend „Aufrufe abgesetzt: 12 · fehlgeschlagen: 0 · <Anbieter>, Modell <Modell>", abgeschlossen „42 Fotos · 40 Antworten · 2 fehlgeschlagen · 1,23 USD · Modell <Modell>". Fehlgeschlagene Einzelaufrufe stehen damit schon während des Laufs da, nicht erst danach.
- **Fortschrittsbalken** (`h-1.5`, Radius `rounded-xs`, Lauffarbe `--accent`, Spur `--separator`) für `remote_categories`, `criteria` und `landmark`, gespeist aus den jeweils eigenen Zählern. Für `ranking` gibt es **keinen** Balken, weil dieser Schritt kein Total kennt — dort steht stattdessen „läuft" bzw. der Haken.
- **Fortschrittswert** rechts (`text-xs`), z.B. „42/100"; bei `pending`/`skipped`/`ranking` leer.

Der bestehende Cloud-Fehler-`Alert` bleibt unverändert unter der Liste.

### 3. `ClassificationBalance.tsx` — Bilanz nach dem Lauf

Tritt an die Stelle der Fortschrittsliste, sobald der Lauf beendet ist (`success` oder `failed`), und beschreibt ausschließlich diesen zuletzt abgeschlossenen Durchlauf. Kopfzeile „Ergebnis dieses Durchlaufs". Drei Fälle:

- **(A) Cloud-Teilschritte vorhanden** (`cloud_phases` nicht leer): je Teilschritt zwei Zeilen — Name mit gesendeten Fotos und verwerteten Antworten (`text-sm`), darunter fehlgeschlagene Aufrufe, tatsächliche Kosten und Modell (`text-xs`, `--text-muted`), getrennt durch `border-separator`. Darunter die Gesamtkosten des Durchlaufs, hervorgehoben, und die Einordnung gegen die Schätzung: „Vor dem Start geschätzt: 2,50 USD". Die Grundlage des Betrags wird genannt — das verwendete Modell und der abgerechnete Tokenverbrauch (`input_tokens`/`output_tokens`), aus dem er entstanden ist —, damit er nicht unerklärt dasteht. Der Preis je Bild erscheint hier **nicht**: Er ist die Grundlage der Schätzung, nicht der Abrechnung, und stünde in der Bilanz für eine Rechnung, die so nie stattgefunden hat. Ist für einen Anteil kein Preis hinterlegt, steht dort „kein Preis hinterlegt" statt eines Betrags, und die Gesamtsumme sagt „unvollständig" statt einer Zahl.
- **(B) Ohne Cloud-Nutzung** (`cloud_requested === false`): eine erklärende Zeile „Ohne Cloud-Anreicherung durchgeführt — es wurden keine Fotos an einen Anbieter gesendet." Keine leere Tabelle, keine Nullwerte, kein Fehler-Styling.
- **(C) Cloud angefragt, aber keine Bilanz erfasst** (`cloud_requested === true`, `cloud_phases` leer — Altläufe oder ein zwischen Auslösen und Start entzogenes Einverständnis): „Für diesen Durchlauf wurde keine Cloud-Bilanz erfasst." Ehrliche Aussage statt erfundener Zahlen.

Die Bilanz bleibt stehen, bis ein neuer Lauf ausgelöst wird; dann tritt wieder die Fortschrittsliste an ihre Stelle. Eine Historie entsteht dadurch ausdrücklich nicht.

### Anordnung im Container

`ClassificationSection.tsx` behält Checkbox, Consent-Gate, Mutation und Auslöser und ordnet darunter genau einen der beiden Zustandsblöcke an — Fortschrittsliste **oder** Bilanz, nie beide gleichzeitig. Dadurch wächst die Sektion nicht über ihre heutige Höhe hinaus, und das Akzeptanzkriterium „überfrachtet die Seite nicht" bleibt gewahrt: Auslöser und Fortschritt stehen oben, die Detailwerte tragen sich als schmale Sekundärzeilen unter den jeweiligen Namen.

### Zustände, Barrierefreiheit, Responsivität

- **Leer/ladend:** Solange die Schätzung lädt, bleibt der Block an seiner Stelle mit gedämpftem Platzhaltertext statt eines Sprungs im Layout. Existiert noch kein Lauf, erscheint weder Fortschrittsliste noch Bilanz.
- **Fehler:** Die bestehenden `Alert`-Muster für Lauf- und Cloud-Fehler bleiben unverändert und werden nicht durch die neuen Blöcke ersetzt.
- **Screenreader:** Die Fortschrittszusammenfassung trägt `aria-live="polite"`; der Wechsel von Fortschritt auf Bilanz wird einmalig als „Klassifizierung abgeschlossen" bzw. „Klassifizierung fehlgeschlagen" angekündigt. Jeder Teilschritt-Zustand ist zusätzlich als Text vorhanden, nie allein über Farbe oder Icon. Der Spinner respektiert `prefers-reduced-motion`.
- **Responsivität:** Die Zeilen brechen auf schmalen Viewports um, ohne horizontales Scrollen; Balken laufen dort über die volle Breite. Zahlen werden nicht abgeschnitten.
- **Eine Währungsformatierung:** Schätzung und Bilanz nutzen dasselbe `formatUsd` aus `utils/formatStats.ts` (`1,23 USD`, `< 0,01 USD`); das lokale `$1.23`-Format entfällt, sonst wäre der geforderte Vergleich zwischen Schätzung und Abrechnung optisch gebrochen.

## Security

**Sicherheitsrelevant, kein Blocker.** Kein neuer Endpunkt, kein neues Secret, kein neuer Empfänger, kein geänderter Datenumfang pro Bild, keine Änderung an Consent-Gate, Auslöser oder Aufruf-Zeitpunkten. Der Eingriff ist überwiegend eine Lesesicht auf Spalten, die es seit ADR 0051/0059 gibt. Drei Dinge sind neu: ein serverseitig berechneter Geldbetrag, der über die Modulgrenze API→Worker geht; Betriebsdaten je Lauf in einer Antwort, die sie bisher nicht trug; der erste nachträglich an eine bestehende Tabelle gehängte Fremdschlüssel des Projekts. Projektweite Einordnung im Abschnitt „Laufeigene Cloud-Bilanz und Live-Fortschritt" des [Sicherheitskonzepts](../architecture/0003-securitykonzept.md).

### Die Vertrauensgrenze beim Geldbetrag — gewählte Variante ist die richtige

Die verworfene Alternative (der Client schickt den angezeigten Betrag mit) hätte einen ungeprüften Geldwert in die Buchführung gelassen. Die gewählte Variante hält die Grenze sauber: die einzige Zahl, die je persistiert wird, entsteht serverseitig aus Datenbankzählungen und der validierten Betriebseinstellung. Muss-Kriterien, damit das trägt:

- `ClassifyRequest` bekommt **kein** Betrags-, Kosten-, Modell- oder Anbieterfeld. Pydantic ignoriert unbekannte Felder heute still — deshalb muss ein Test ausdrücklich belegen, dass ein im Body mitgeschicktes `estimated_cost_usd` den persistierten Wert **nicht** verändert. Ohne diesen Test fiele eine spätere versehentliche Aufnahme ins Schema niemandem auf.
- Modell und Anbieter der Schätzung stammen ausschließlich aus `settings.resolved_landmark_model()` bzw. `settings.landmark_provider`, nie aus Body, Query oder Job-Payload (die fünf Bedingungen aus ADR 0059/dem Sicherheitskonzept gelten unverändert).
- Der eingefrorene Betrag ist ein **Beleg, nie eine Eingabe**: er darf in keine spätere Rechnung, kein Budget-Gate und keine Ableitung der Ist-Kosten eingehen. Sonst würde eine Momentaufnahme autoritativ.
- `use_cloud=false` schreibt `NULL`, nicht `0.0` — dieselbe „`null` heißt unbekannt, nie kostenlos"-Linie wie bei `price_per_image_usd`.
- Das zusätzliche Job-Argument ist unkritisch: die arq-Payload trug schon `project_id`/`scoring_run_id`/`use_cloud`, Redis hat im Compose-Netz kein `ports:`-Mapping, ein Float ist kein Geheimnis. Der Default `None` verhindert, dass ein zum Deployment bereits eingereihter Job an der Signatur scheitert.

### Neue Antwortfelder — kein Konfigurationsleck, mit harter Grenze

`model` bekommt hier den Lesepfad, den ADR 0059 Punkt 6 ihm bewusst noch verwehrt hatte; ADR 0068 löst das auf. Unbedenklich: eine Hersteller-Modellbezeichnung, deren Auswahl ohnehin im öffentlichen Repository steht, ausgeliefert über den router-weiten `dependencies=[Depends(get_current_user)]`-Torwächter von `api/projects.py` (bleibt so).

Dass der **Anbieter aus dem gespeicherten Modell abgeleitet** wird (`provider_for_vision_model` über `VISION_MODELS_BY_PROVIDER`) statt aus `settings.landmark_provider`, ist über die Korrektheitsfrage hinaus auch sicherheitlich die bessere Wahl: eine historische Lauf-Antwort kann damit strukturell nicht die heutige Betriebseinstellung preisgeben.

Muss-Kriterien:

- Die Antwort wächst um genau die in ADR 0068 Punkt 4 aufgezählten Felder und um kein weiteres — keine Basis-URLs, keine `*_concurrency`-Werte, kein „API-Key gesetzt ja/nein", kein Umgebungsvariablenname, kein Pfad.
- Ein unbekanntes Modell liefert `provider = null`; die Oberfläche zeigt dann die Modell-ID allein, **nie** einen Konfigurationshinweis der Art „Anbieter prüfen" / „`LANDMARK_PROVIDER` nicht gesetzt".
- `model`/`provider` werden im Frontend als reguläre JSX-Textknoten gerendert (bestehende Konvention, kein `dangerouslySetInnerHTML`, keine HTML-String-Prop).

### Zähler sind Zahlen, kein Fremdtext

`failed_calls`/`landmark_failed_calls`/`landmark_photos_processed` machen Fehlschläge erstmals *während* des Laufs sichtbar — aber ausschließlich als Anzahl. Der Fehler**grund** bleibt, wo er liegt: laufweit in `cloud_error_message` (an der Exception-Konstruktionsstelle sanitiert, auf 1000 Zeichen gekappt) und je Foto in `photo_cloud_vision_errors`.

- Kein neues Antwort- oder Spaltenfeld mit Rohtext einer Provider-Antwort.
- Das Zählen greift auf die `asyncio.gather(return_exceptions=True)`-Ergebnisliste zu und darf dabei **keine** neue Logzeile mit `repr(exc)`, `response.text`, `response.json()`, `response.headers` oder `exc_info=True` einführen. Es gilt unverändert feste Meldung + `type(exc).__name__` (ADR 0034 Punkt 5) — eine Provider-Antwort kann die Modellaussage über ein Familienfoto und im Fehlerfall Base64-Bilddaten sowie ein Key-Echo enthalten. Per `caplog` abzusichern.
- Die Live-Zähler bleiben strikt von `api_calls`/`landmark_api_calls` getrennt (ADR 0068 Punkt 2): ein laufend hochgezähltes `api_calls` löste den Unvollständigkeits-Indikator aus ADR 0051 Punkt 5 Befund (b) bei jedem laufenden Lauf aus und färbte die Kostenseite mit einem Fehlalarm.

### Drei nullable Geldfelder, dieselbe Regel

`estimated_cost_usd`, `cloud_phases[].cost_usd` und `cloud_cost_total_usd` erben das Muss-Kriterium aus ADR 0059 wortgleich: `null` muss bis in die Anzeige durchschlagen, **kein `?? 0` / `|| 0` / `or 0.0` irgendwo im Pfad**. Ein stilles „0,00 USD" ist die gefährlichste aller Anzeigen, weil es einen unerwarteten (z.B. über ein gestohlenes JWT ausgelösten) Lauf als kostenlos tarnt. Dass `cloud_cost_total_usd` serverseitig auf `None` fällt, sobald ein Anteil `None` ist, hält die Regel an einer Stelle statt in jeder Komponente.

### Sichtbarkeit zwischen den beiden Nutzern: unverändert

Keine der sechs neuen Spalten und keines der neuen Antwortfelder trägt einen `user_id`-Bezug; `criterion_scoring_runs` hat keinen und bekommt keinen. Die Lauf-Bilanz ist eine feinere Granularität von Kosteninformation, die die Statistikseite bereits projektweit zeigt — kein neuer Kanal, konsistent mit „kein Innentäter-Modell zwischen den beiden Nutzern". Der Betrag bleibt private Ausgabeninformation der Familie: nur über den auth-pflichtigen Endpunkt, nie in einer Logzeile oder Client-Fehlermeldung.

### Migration

Rein additiv: sechs nullable Spalten ohne `server_default`, kein Backfill. Unter Postgres ein `ADD COLUMN` ohne Table-Rewrite; die Validierung des neuen FK läuft gegen ausschließlich `NULL`-Werte und ist trivial erfüllt — kein Datenverlustpfad, keine Sperrzeit von Belang.

**Befund mit Muss-Charakter:** Bisher hat keine Migration des Projekts einen Fremdschlüssel an eine bestehende Tabelle gehängt (nachgeprüft: kein `create_foreign_key` in `backend/alembic/versions/`), und `Base.metadata` trägt keine `naming_convention`. Ein per `batch_alter_table` **unbenannt** angelegter FK ist im `downgrade()` unter SQLite nicht droppbar — der Rückwärtsweg der Migration wäre nicht ausführbar. Der Constraint muss deshalb explizit benannt werden, und der Round-Trip-Test muss `upgrade` **und** `downgrade` abdecken.

Zweite Nebenwirkung: der FK zieht eine Kante in den Graphen, auf dem die Projektlöschung ruht (ADR 0062). Die Reihenfolge passt bereits (`criterion_scoring_runs` vor `remote_category_classification_runs`, nachgemessen in `project_deletion.py`), der Metadaten-Reihenfolgetest hält sie fest, und die neue Kante macht den Vollständigkeitstest über die FK-Erreichbarkeit nicht schwächer, sondern strenger. Muss: beide `project_deletion`-Tests bleiben grün, und ein Test belegt, dass ein Lauf **ohne** Cloud-Phase keinen FK setzt — sonst erbte eine Bilanz fremde Beträge, genau der Zuordnungsfehler, den ADR 0068 Punkt 3 beseitigt.

### Der geschlossene Watchdog-Defekt ist sicherheitlich der wertvollste Teil der Story

Bis hierher hatte die Landmark-Phase keinen einzigen Commit-Punkt vor dem `finally`, und `reap_stalled_runs` setzte einen Lauf mit mehr als `STALL_THRESHOLD` (15 min) Landmark-Arbeit auf `FAILED`. Der Reaper **bricht die Coroutine nicht ab** — er ist bewusst vom Worker-Prozess unabhängig und flippt nur die Datenbankzeile. Der Lauf rief danach unverändert weiter kostenpflichtig beim Anbieter an, während die Oberfläche „fehlgeschlagen" sagte, und die Kostenerfassung des `finally` schrieb ihren eingefrorenen Betrag auf eine bereits als gescheitert ausgewiesene Zeile. Das ist keine reine Verfügbarkeitsfrage, sondern eine Lücke in der Kostenerkennung: die Wirkung „Erkennungsmechanismus für den `gestohlenes JWT → teure Läufe`-Missbrauch", die das Sicherheitskonzept der Ist-Kostenerfassung zuschreibt, setzt voraus, dass ein Geld ausgebender Lauf auch als laufend dasteht. Die neuen Commit-Punkte je `asyncio.gather`-Block schreiben `last_progress_at` mit und beenden das. Als projektweite Regel im Sicherheitskonzept unter „Job-Lauf-Terminierung" verankert.

### Screenshot- und Demo-Hygiene

Die Bilanz zeigt erstmals **an der Auslöse-Stelle** einen Geldbetrag, und `demo_state.py` wird ausdrücklich so bespielt, dass sie im Prüfstack/`browse-app` sichtbar ist. Damit trifft die Regel aus Spec 0321 („nur synthetische Demo-Daten"; das Repository ist öffentlich, PR-Anhänge liegen öffentlich auf GitHub, der CI-Schritt gegen eingecheckte Bilddateien greift nicht an PR-Anhängen) erstmals auch auf Ausgabeninformation der Familie statt nur auf Dateinamen und Bildinhalte. Muss-Kriterien: die Demo-Werte sind frei erfunden; Screenshots und Ad-hoc-Läufe entstehen ausschließlich gegen den synthetischen Demo-Stand, nie gegen Daniels Instanz; in Spec, PR-Beschreibung und Commit-Nachrichten steht kein realer Betrag und kein realer Modell-/Aufrufwert eines echten Laufs. Die dreiteilige Demo-Seeder-Sperre M3 bleibt unangetastet: `demo_state.py` bekommt nur zusätzliche Spaltenwerte, keinen neuen Aufrufpfad und keine neue Importrichtung.

### Ausdrücklich nicht sicherheitsrelevant

Die zwei zusätzlichen `ClassificationPhase`-Werte (`VARCHAR(20)` ohne DB-Prüfeinschränkung), die Vereinheitlichung der Währungsformatierung, der Wegfall von `ProjectOut.last_remote_category_classification_run`, die Aufteilung von `ClassificationSection.tsx` in vier Komponenten und die Invariante `photos_processed == api_calls + failed_calls` (eine Korrektheits-, keine Sicherheitszusage).

### Review-Abdeckung

Der Diff berührt `backend/src/photosort/api/projects.py` und löst den `review-security`-Trigger regulär aus — keine Sondermaßnahme nötig.

## Teststrategie

Keine neue Testebene. Der Eingriff ist überwiegend additiv und trifft vier bereits im Testkonzept beschriebene Muster: die `NULL`-Vierfeldertafel additiver Lauf-Spalten (ADR 0051 Punkt 3), die Dreifach-Identität eines einmal aufgelösten Werts (ADR 0059 Punkt 7), die `null`-vs-`0`-Kette bis in die Anzeige (Spec 0207/0299) und die reine Ableitungsdatei vor dem JSX (`pipelineSteps.ts`). Neu — und deshalb im Testkonzept [`architecture/0002-testkonzept.md`](../architecture/0002-testkonzept.md) als eigene Sektion festgehalten — ist der erste **laufend fortgeschriebene Zähler unmittelbar neben einer eingefrorenen Kosten-Buchführung**.

### Ebenenzuordnung

| Gegenstand | Ebene | Ort |
|---|---|---|
| Migration (6 Spalten + FK), Enum-Werte | Unit, isolierte Revision | `backend/tests/test_migration_classification_run_transparency.py` (neu), `test_postgres_ddl_compatibility.py`, `test_models.py` |
| Phasenfolge, Live-Zähler, `last_progress_at`, Modell-Frühschreibung, Invariante | Integration gegen `db_session` | `test_worker_criterion_scoring.py`, `test_worker_remote_category_classification.py` |
| Remote-Run-Anlage, FK, `estimated_cost_usd` | Integration gegen `db_session` | `test_worker_classification.py` |
| `provider_for_vision_model` | Unit, reine Funktion | `test_cloud_vision.py` |
| Estimate-Umbau, `cloud_phases`, Bilanz-Felder, Job-Argument | API-Test (`authenticated_api_client`) | `test_api_classification_estimate.py`, `test_api_projects.py` |
| Negativ-Zusage Statistikseite | API-Test | `test_api_stats.py` |
| Löschreihenfolge des neuen FK | Integration | `test_project_deletion.py` |
| Demo-Zustand | Integration | `test_demo_state.py` |
| `deriveClassificationSteps` | Unit, reine Funktion | `frontend/src/utils/classificationSteps.test.ts` (neu) |
| Die drei neuen Blöcke | Komponententest ohne Provider/Router | `ClassificationEstimate.test.tsx`, `ClassificationProgress.test.tsx`, `ClassificationBalance.test.tsx` (alle neu) |
| Container-Verdrahtung, Zustandsauswahl | Integration (`QueryClientProvider` + `MemoryRouter`, `vi.mock` auf `api/projects.ts`) | `ClassificationSection.test.tsx` |
| Polling-Bedingung, Typabbau | Unit/Integration | `hooks/useProjects.test.tsx`, `api/projects.test.ts` |
| Umbruch der neuen Detailzeilen bei 360 px | E2E (Chromium) | `e2e/tests/no-horizontal-scroll.spec.ts` (Route ergänzt, kein neuer Spec) |

### Backend

**B1 — Migration und Modell** (`test_migration_classification_run_transparency.py`, neu; Muster `test_migration_classification_run_cloud_phase.py`: isolierte Revision über `importlib`, nachgebauter Vorzustand, Auf- **und** Abwärtsrichtung)

- `test_upgrade_adds_the_five_columns_and_the_foreign_key_to_criterion_scoring_runs`
- `test_upgrade_adds_failed_calls_to_remote_category_classification_runs`
- `test_no_new_column_has_a_server_default` — die Assertion mit Begründung im Docstring: ein `server_default='0'` an `landmark_photos_total` löschte den Marker „diese Phase fand statt" unumkehrbar, nicht nur eine Nuance.
- `test_existing_rows_keep_null_in_every_new_column` — Bestandszeile vor dem Upgrade angelegt, danach in allen sechs Spalten `NULL` (kein Backfill).
- `test_the_foreign_key_targets_remote_category_classification_runs` — Ziel-Tabelle/-Spalte über `inspect(...).get_foreign_keys()`; unter SQLite entsteht der FK nur über `batch_alter_table`, ein vergessener `batch`-Block wäre sonst unsichtbar.
- `test_downgrade_removes_every_new_column_and_the_foreign_key` — der Constraint muss dafür **explizit benannt** sein (siehe Security-Befund; ein unbenannter FK ist unter SQLite nicht droppbar).
- `test_postgres_ddl_compatibility.py`: neue Revision in die bestehende Renderprüfung aufnehmen (SQLite unterscheidet `INTEGER`/`FLOAT` nicht und schluckte einen unbeabsichtigten Default).
- `test_models.py`: `ClassificationPhase` hat genau vier Werte **in Ausführungsreihenfolge** (Tupelvergleich, keine Mengengleichheit — die Reihenfolge trägt die Aussage), und der längste Wert passt in `VARCHAR(20)`.
- `test_migration_chain.py` bleibt **ohne Anpassung** grün.

**B2 — Phasenfolge** (`test_worker_classification.py`)

- `test_the_phase_sequence_of_a_cloud_run_is_monotone` — ein einziger Test, der die beobachtete Folge als Liste vergleicht: `['remote_categories', 'criteria', 'landmark', 'ranking', None]`. Beobachtet wird aus den Test-Doubles heraus (Kategorie-Client, Detektor-Stub, Landmark-Client) plus einem Spy auf `worker_module.rank_photos` für die Ranking-Phase; vier Einzelasserts belegten die Monotonie nicht.
- `test_a_run_without_cloud_keeps_the_order_and_skips_both_cloud_phases` → `['criteria', 'ranking', None]`.
- `test_a_failed_run_leaves_no_phase_behind` — `_fail_run` nullt `phase`; hält fest, dass auch der neue Ranking-Zweig darüber läuft.
- Regression: `ranking` existiert genau deshalb, weil `phase` sonst auf `landmark` bei 100 % Fortschritt stünde — ein Testfall assertiert, dass während des `rank_photos`-Aufrufs `phase != 'landmark'` ist.

**B3 — Live-Zähler, Commit-Punkte, Modell-Frühschreibung** (`test_worker_criterion_scoring.py`, neue Klasse `TestLandmarkPhaseLiveCounters`; `test_worker_remote_category_classification.py` analog)

Grundmuster: der Landmark-Client schnappschüsst bei **jedem** Aufruf `(run.landmark_photos_total, run.landmark_photos_processed, run.landmark_failed_calls, run.landmark_api_calls, run.landmark_model, run.landmark_cost_usd)`; assertiert wird über die Schnappschussliste, nicht über den Endzustand.

- `test_the_counters_are_set_to_zero_when_the_phase_is_entered` — beim ersten Aufruf steht `landmark_photos_total` bereits auf der Kandidatenzahl, `processed`/`failed_calls` auf `0` — nicht `None`.
- `test_the_processed_counter_grows_block_by_block` — `landmark_api_concurrency = 1` monkeygepatcht, drei Kandidaten: Schnappschüsse `0, 1, 2`. Das ist der Nachweis „der Fortschritt bewegt sich mit".
- `test_the_live_counters_are_committed_at_every_block_end_not_only_at_the_end` — `session.commit` für die Testdauer umhüllt, jeder Commit schreibt denselben Schnappschuss; ohne diesen Test ist „die pollende Oberfläche sieht es" unbelegt (Attributänderung ≠ Sichtbarkeit).
- `test_last_progress_at_advances_during_the_landmark_phase` — Sentinel-`_now_utc`-Muster wie `test_criterion_scoring_updates_last_progress_at_at_each_checkpoint`; schließt die Watchdog-Lücke belegbar. **Kein** zweiter Testfall in `test_worker_reap_stalled_runs.py` — `reap_stalled_runs` liest nur `last_progress_at`, ein Test dort verdoppelte die Zusage.
- `test_failed_single_calls_are_counted_while_the_run_is_still_going` — Client, der beim zweiten von vier Aufrufen wirft: `failed_calls` steht bereits im Schnappschuss des dritten Aufrufs auf `1`.
- `test_the_model_is_written_at_the_phase_start_while_the_amount_is_not` — beim ersten Aufruf ist `landmark_model` gesetzt und `landmark_api_calls == 0`; **derselbe Test** hält damit beide Hälften der ADR-Zusage fest (früh sichtbar / spät eingefroren). Der Sentinel-Modellwert kommt aus einer nicht voreingestellten Einstellung, sonst wäre die Assertion tautologisch.
- Die vier `NULL`-Fälle, je ein Test: Cloud-Checkbox aus, Einwilligung aus, keine zu bewertenden Fotos, Client nicht konstruierbar → `landmark_photos_total is None` (nicht `0`) und `landmark_failed_calls is None`.
- **Der `0`-Fall daneben, als eigener Test:** Fotos sind vorhanden, die Einwilligung liegt vor, der Client ist gebaut — aber unter den bewerteten Fotos ist kein Landmark-Kandidat. Die Phase **hat** stattgefunden, also steht dort `0`, nicht `NULL`. Das ist die Grenze der Vierfeldertafel und der einzige Fall, der sich mit den vier obigen verwechseln lässt; er wird auf beiden Ebenen festgehalten (Worker: die drei Zähler stehen auf `0`; API: der Lauf bekommt trotzdem seinen Landmark-Eintrag in `cloud_phases`). Ohne ihn läge genau die Bedingung unbelegt, an der die API entscheidet, ob ein Teilschritt überhaupt erscheint — und ein weggelassener Teilschritt liest sich in der Oberfläche als „übersprungen", obwohl er lief.
- Der Fall „Client nicht konstruierbar" ist zugleich der bestehende Regressionsschutz „kein Cloud-Client-Bau bei abgewählter Checkbox" — die vorhandenen Tests (`test_consent_disabled_by_default_never_calls_landmark_client_builder`, `test_a_flat_photo_without_a_landscape_label_triggers_no_cloud_call_anymore`) bleiben **unverändert** grün; jede Anpassung dort ist ein Review-Befund.
- Remote-Seite: `test_failed_calls_are_written_at_the_existing_block_commit_point`, `test_the_model_is_written_before_the_first_classification_call`.

**B4 — Die Bindungs-Invariante** (`test_worker_criterion_scoring.py` / `test_worker_remote_category_classification.py`)

- Gemeinsamer Testhelfer `assert_call_bookkeeping_invariant(run)`: prüft `photos_processed == api_calls + failed_calls`, **übersprungen, solange die Phase nicht betreten wurde** (`failed_calls is None`) — sonst liefe der Vergleich für einen Lauf ohne Cloud-Phase in ein `0 == 0 + None`.
- Angewendet in mindestens vier Läufen: alle Aufrufe erfolgreich; gemischt (2 Erfolge, 1 Fehlschlag); alle Aufrufe fehlgeschlagen; ein Lauf, der **nach** der Cloud-Phase scheitert (Erweiterung von `test_costs_survive_a_run_that_fails_after_the_landmark_block`).
- `test_the_invariant_is_not_claimed_for_a_run_cancelled_inside_a_block` — hält die Ausnahme ausdrücklich fest, statt sie beim ersten Abbruch-Testfall stillschweigend zu streichen.
- Die daraus folgende Implementierungsvorgabe wird mitgetestet: der Live-Zähler wird **am Blockende** fortgeschrieben, nie beim Betreten — `test_a_cancelled_block_counts_neither_as_processed_nor_as_an_api_call`.

**B5 — Fremdschlüssel statt Heuristik** (`test_worker_classification.py`, `test_project_deletion.py`)

- `test_a_cloud_run_links_its_own_remote_run` — FK == id der von `run_classification` angelegten Zeile.
- `test_the_link_exists_before_the_first_remote_call` — Beobachtung aus dem Kategorie-Client heraus (die Oberfläche braucht den Anker während Phase 1).
- `test_a_run_without_a_cloud_phase_links_no_remote_run` — **mit einer älteren, fremden Remote-Zeile im selben Projekt**. Ohne diese zweite Hälfte bestünde der Test auch bei leerer Datenbank, und genau dieser Fall ist der Grund für die Umkehr von ADR 0050 Punkt 3.
- `test_two_consecutive_runs_each_carry_their_own_remote_run`
- `test_a_direct_call_still_creates_its_own_row` / `test_a_passed_run_is_reused_and_no_second_row_is_created` (Zeilenzahl == 1).
- `test_project_deletion.py`: der bestehende Metadaten-Reihenfolgetest erfasst den neuen FK automatisch; ein benannter Testfall hält fest, dass ein Projekt mit verknüpften Läufen vollständig löschbar bleibt — sonst liest sich die passende Reihenfolge später wie ein Zufall.

**B6 — `provider_for_vision_model`** (`test_cloud_vision.py`)

- Parametrisiert über `VISION_MODELS_BY_PROVIDER` (alle Provider/Modell-Paare, nie abgeschrieben): `test_every_registered_model_resolves_to_its_provider`.
- `test_an_unknown_model_yields_none_not_a_guess` — `None`, kein Default-Provider.
- `test_the_function_does_not_read_the_configuration` — Abwesenheits-Assertion: kein `photosort.config`-Import im Modul; die aktuelle Betriebseinstellung darf einen vergangenen Lauf nicht beschreiben (ADR 0059).

**B7 — Estimate-Umbau** (`test_api_classification_estimate.py`)

- `TestLandmarkShareOfTheEstimate`: bekommt in jedem Testfall einen erfolgreichen `CriterionScoringRun` in die Fixture (neue Vorbedingung), die **Zahlen-Erwartungen bleiben unverändert**. `TestTheEstimateFollowsTheConfiguredModel::test_the_default_estimate_still_matches_the_previous_constant` bleibt vollständig unangetastet grün (dort gab es nie einen Landmark-Anteil) — der literale Altwert-Pin ist der Anker, dass die Umstellung additiv ist.
- Neue Klasse `TestTheLandmarkShareIsUnknownBeforeTheFirstRun`, vier Fälle: kein Lauf → `landmark.candidate_count is None`; nur ein **fehlgeschlagener** Lauf → `None`; nur ein **laufender** Lauf → `None`; ein erfolgreicher Lauf → `int` (auch `0` ist erlaubt und bedeutet etwas anderes).
- `test_a_successful_run_in_another_project_does_not_unlock_the_share` — Pflichtfall jeder projektskopierten Abfrage.
- `test_the_total_is_the_sum_of_the_known_shares_only` — bei unbekanntem Landmark-Anteil ist `candidate_count` die untere Schranke und `estimated_cost_usd` ein Betrag (keine `None`), `landmark.estimated_cost_usd` dagegen `None`.
- Zweigreihenfolge je Anteil, parametrisiert: `candidate_count == 0` → `0.0`; `price is None` → `None`; Anteil unbekannt → `None`. Die Reihenfolge ist die Aussage (Copilot-Fund PR #341) und wird je Anteil einzeln geprüft.
- `test_the_two_flat_candidate_fields_are_gone` — Abwesenheits-Assertion auf `remote_category_candidate_count`/`landmark_candidate_count` in der Antwort.
- Unverändert: `provider`/`model`/`price_per_image_usd` stehen in der Antwort (bestehende Tests).

**B8 — Bilanz an der Run-Zusammenfassung und Job-Argument** (`test_api_projects.py`)

- `test_cloud_phases_is_empty_for_a_run_without_any_cloud_step` — leere Liste, nicht `null`, nicht erfundene Nullzeilen.
- `test_cloud_phases_lists_remote_category_before_landmark` — feste Reihenfolge; die Fixture gibt beiden Phasen **unterschiedliche** Zahlen, sonst wäre eine Vertauschung unsichtbar.
- `test_a_phase_appears_as_soon_as_it_was_entered` — Remote: FK gesetzt; Landmark: `landmark_photos_total is not None`; beide Fälle einzeln.
- `test_a_running_phase_reports_live_counters_and_no_amount_yet` — `photos_processed`/`failed_calls` > 0, `responses_used == 0`, `cost_usd` noch nicht eingefroren.
- `test_an_unpriced_phase_reports_null_not_zero` und `test_the_total_is_null_as_soon_as_one_share_is_null` — die Regel „unvollständig ≠ 0" bleibt serverseitig an einer Stelle.
- `test_the_provider_is_derived_from_the_stored_model` / `test_an_unknown_model_leaves_the_provider_null`.
- `test_the_estimate_of_the_run_is_forwarded_to_the_job` — Fake-Enqueuer; der erwartete Wert wird **aus `GET .../classify/estimate` gelesen**, nicht im Test nachgerechnet.
- `test_a_local_run_forwards_none_and_stores_null` — nicht `0.0`.
- `test_the_classify_job_argument_has_a_default` (`inspect.signature`) — ein bereits eingereihter Job darf an der Signaturänderung nicht scheitern.
- `test_the_request_body_cannot_influence_the_stored_estimate` (Security-Muss): ein im Body mitgeschicktes `estimated_cost_usd` verändert den persistierten Wert **nicht**.
- `test_project_out_no_longer_exposes_last_remote_category_classification_run` — ersetzt `test_project_out_exposes_last_remote_category_classification_run` (bisher in `test_api_classification_estimate.py`). Die Frage des gestrichenen Tests („zeigt die API die Remote-Zahlen an?") wird ab jetzt von `test_cloud_phases_*` gestellt; das gehört in den Docstring des neuen Tests.

**B9 — Negativ-Zusagen**

- `test_api_stats.py`, neuer Testfall `test_a_running_cloud_run_does_not_trigger_the_incompleteness_hint`: Zeile direkt konstruiert (`phase='landmark'`, `landmark_photos_total=10`, `landmark_photos_processed=4`, `landmark_failed_calls=1`, `landmark_api_calls=0`, `landmark_cost_usd=0.0`) **plus** mindestens ein vorhandenes Landmark-Ergebnis im Projekt (damit die zweite Teilbedingung von Befund (a) erfüllt ist) → `has_unrecorded_runs is False` für **beide** Zwecke. Derselbe Fall für die Remote-Phase. Das ist der Test, der rot wird, falls jemand die Live-Zähler doch in die Buchführungsspalten legt.
- Alle übrigen Tests in `test_api_stats.py` und in `ProjectStatsPage.test.tsx` bleiben **unverändert**; jede angepasste Erwartung dort ist ein Review-Befund, kein Nachzug.
- `caplog`-Nachweis (Security-Muss): das Zählen der Fehlschläge führt keine Logzeile mit `repr(exc)`, `response.text`, `response.json()`, `response.headers` oder `exc_info=True` ein.

**B10 — Demo-Zustand** (`test_demo_state.py`)

- `test_the_rated_project_has_a_run_with_a_cloud_balance` — verknüpfter Remote-Lauf, `landmark_photos_total is not None`, `estimated_cost_usd is not None`; abgeleitet assertiert (`any(...)`), nie über einen festen Index.
- `test_at_least_one_project_still_has_a_run_without_any_cloud_phase` — das „ohne Cloud"-Szenario bleibt erhalten, sonst verliert die Bilanz-Variante (B) ihren Prüfstack-Fall.
- Die bestehenden Zusagen des Seeders (Byte-Identität, Zielzustands-Idempotenz, Schutzabbruch) gelten unverändert und decken die neuen Spalten mit ab.

### Frontend

**F1 — `utils/classificationSteps.test.ts` (neu, reine Funktion, kein Provider/Router)**

Literale Fixture-Tabelle aus `CriterionScoringRunSummary`-Objekten; beide `cloud_phases`-Einträge tragen in jeder Fixture **unterschiedliche** Zahlen.

- Reihenfolge und Menge: vier Schritte bei `cloud_requested === true`, zwei bei `false` (`criteria`, `ranking`).
- Zustände, parametrisiert über `PHASE_ORDER` statt vier abgeschriebener Fälle: Schritte vor `phase` = `done`, der aktuelle = `running`, danach = `pending`; `phase === null` bei `status === 'success'` → alle `done`.
- `skipped`: Lauf beendet, `cloud_requested === true`, kein zugehöriger `cloud_phases`-Eintrag — je ein Fall für „Altlauf" (beide fehlen) und „Einwilligung zwischen Auslösen und Start entzogen".
- **Vertauschungstest:** `test_the_landmark_entry_never_feeds_the_criteria_step` und die Gegenrichtung; zusätzlich ein Fall mit **umgekehrter Reihenfolge** in `cloud_phases` (die Anzeigereihenfolge ist eine Zusage der Ableitung, nicht der Serverantwort).
- Fortschrittsquellen: `criteria` aus `run.photos_total/photos_processed`, `ranking` mit `total === null` (unbestimmt), Cloud-Schritte aus ihrem eigenen Eintrag.
- `null` bleibt `null`: ein laufender Schritt ohne Zahlen liefert `processed === null`, nicht `0`.
- Werte werden unverändert durchgereicht (kein Clampen, kein Rechnen in der Ableitung).

**F2 — `ClassificationEstimate.test.tsx` (neu)**

- Beide Anteile mit Name, Fotoanzahl und Betrag; Gesamtsumme; Anbieter und Modell sichtbar.
- Landmark-Anteil unbekannt: der Satz erscheint **wörtlich inklusive** „Dieser Anteil verursacht trotzdem Kosten." und die Zeile enthält weder `0` noch einen Betrag (Negativ-Assertion). Ohne den zweiten Satz liest sich die Leerstelle wie „fällt nicht an" — die Assertion auf ihn ist der eigentliche Testfall.
- Kein hinterlegter Preis: Hinweistext statt Betrag, **kein** `Alert`-Styling.
- Schätzcharakter dauerhaft sichtbar; der Hinweis auf denselben Preis je Bild für beide Anteile ebenfalls.
- Format: genau ein Testfall hält `1,23 USD` wörtlich fest; zusätzlich eine Negativ-Assertion, dass im gerenderten Baum der Sektion **kein** `$`-Betrag mehr vorkommt (das lokale `formatUsd` entfällt).

**F3 — `ClassificationProgress.test.tsx` (neu)**

- Vier bzw. zwei Zeilen in fester Reihenfolge; `ranking` hat **keinen** Fortschrittsbalken (`queryAllByRole('progressbar')` == 3 im Cloud-Lauf) und keinen `x/y`-Wert.
- Laufender Cloud-Schritt: abgesetzte Aufrufe, Fehlschläge, Anbieter und Modell in der Detailzeile — die Fehlschläge ausdrücklich **während** `status === 'running'` (eigener Testfall, das ist ein eigenes Akzeptanzkriterium).
- Unbekannter Anbieter: nur die Modell-ID, kein geratener Anbieter, kein Konfigurationshinweis, und keine der Zeichenketten `null`/`undefined` im Text.
- Der Zustand steht **als Text** an jeder Zeile, nicht allein als Farbe/Icon — je ein Testfall pro Zustand über den Text, nicht über eine Klasse.
- „Bewegt sich mit" als Rerender-Test: höherer `photos_processed` im Landmark-Eintrag → der angezeigte Wert der Landmark-Zeile ändert sich, **und** die Kriterien-Zeile bleibt unverändert (belegt, dass die Quellen nicht geteilt sind).
- `aria-live="polite"` an der Zusammenfassung; der bestehende Cloud-Fehler-`Alert` steht unverändert unter der Liste (Regression).

**F4 — `ClassificationBalance.test.tsx` (neu)**

- Fall (A): je Teilschritt gesendete Fotos, verwertete Antworten, Fehlschläge, Kosten, Modell und Tokenverbrauch; Gesamtkosten; „Vor dem Start geschätzt: …".
- Fall (B) ohne Cloud: der erklärende Satz, **keine** Nullwerte, kein leeres Feld, kein Fehler-Styling (Negativ-Assertionen).
- Fall (C) Cloud angefragt, keine Bilanz: ehrliche Aussage, keine erfundenen Zahlen.
- Kein Preis für einen Anteil: „kein Preis hinterlegt" statt Betrag, Gesamtsumme „unvollständig" statt Zahl — Negativ-Assertion, dass **nirgends** `0,00 USD` steht.
- `estimated_cost_usd === null`: keine erfundene Vergleichszeile.
- Ein fehlgeschlagener Lauf zeigt die Bilanz trotzdem (das Geld war ausgegeben).
- Keine Historie: genau eine Kopfzeile, und die angezeigten Teilschritte stammen ausschließlich aus dem übergebenen Lauf.

**F5 — Container, Hook, Typen**

- `ClassificationSection.test.tsx`: `test_exactly_one_of_progress_and_balance_is_rendered` über alle Laufzustände (laufend / erfolgreich / fehlgeschlagen / kein Lauf) — das ist die prüfbare Form des Kriteriums „überfrachtet die Seite nicht"; und `test_a_new_run_replaces_the_balance_with_the_progress_list`.
- **Test-Migrationskarte:** der Block `describe('Teilschritt-Fortschritt')` (heute Zeilen 309–372) wandert nach `ClassificationProgress.test.tsx`; im Container bleibt je ein schlanker Wiring-Nachweis. Die Blöcke „ein Auslöser", „Cloud-Nutzung pro Durchlauf", „Fehlerverhalten und Herkunft des Ergebnisses" und „Feinlabel-Häufigkeiten" bleiben **unverändert** im Container — sie prüfen den Auslöser, der sich laut Spec nicht ändert.
- `hooks/useProjects.test.tsx`: `keeps polling while the last remote category classification run is running` entfällt mit dem Feld. Nachfolger im selben Commit: `test_keeps_polling_during_the_remote_phase_of_a_classification_run` (`last_criterion_scoring_run.status === 'running'`, `phase === 'remote_categories'`) — die Frage bleibt gestellt, nur an der Zeile, die sie ab jetzt beantwortet.
- `api/types.ts`: das Feld wird **zuerst** im Typ gelöscht; die `tsc`-Fehlerliste ist die vollständige Fundstellenliste der ~15 Testfabriken. Alle neuen Felder werden pflichtig (`| null`, kein `?`) typisiert, damit eine Auslassung ein Typfehler ist.
- `designSystem.contract.test.ts` läuft automatisch über die drei neuen Dateien; braucht eine Regel eine Freigabe, ist sie **fundstellengenau** einzutragen, nie dateiweise.

**F6 — E2E**

Kein neuer Spec. `e2e/tests/no-horizontal-scroll.spec.ts` bekommt die Route `/projects/{ratedId}/pipeline/kriterien` mit der Bilanz-Überschrift als Vorbedingung (nicht der Seitenüberschrift — eine Route, deren Vorbedingung schon vorher erfüllt war, bestünde den Spec auch mit fehlendem Inhalt). Grund: mehrteilige Detailzeilen neben einem Fortschrittsbalken sind genau der Fall, den jsdom prinzipiell nicht prüfen kann. **Rot-Nachweis ist Pflicht** — lässt sich die Zeile nicht zum Überlaufen bringen, trägt die Route nichts bei und wird nicht aufgenommen. Die übrigen E2E-Specs bleiben unverändert.

### Edge Cases (Kurzliste, alle oben verortet)

Landmark-Phase ohne Kandidaten (`total = 0`, nicht `NULL`) · Phase gar nicht betreten (`NULL`, nicht `0`) · alle Aufrufe fehlgeschlagen · Abbruch mitten im Parallelblock · Lauf scheitert nach der Cloud-Phase · Modell nicht mehr in der Registry · kein Preis hinterlegt · Landmark-Anteil vor dem ersten Lauf unbekannt · erfolgreicher Lauf nur in einem *anderen* Projekt · zwei Läufe hintereinander mit unterschiedlicher Cloud-Nutzung · Altlauf ohne Bilanz bei `cloud_requested === true` · Einwilligung zwischen Auslösen und Start entzogen · bereits eingereihter Job ohne das neue Argument.

### Was bewusst nicht getestet wird

- Die Richtigkeit der Preiswerte in `pricing.py` (unveränderte bekannte Lücke).
- Echte Nebenläufigkeit zwischen pollender Oberfläche und laufendem Worker: die Suite konstruiert bzw. beobachtet Zwischenzustände in **einer** Session; die In-Memory-SQLite kann keine zweite Verbindung öffnen. Für die hier getroffenen Zusagen reicht das (keine der beteiligten Zahlen wird gelesen und zurückgeschrieben) — vor einer künftigen Read-Modify-Write-Erweiterung neu zu bewerten.
- Das tatsächliche Screenreader-Verhalten der `aria-live`-Ankündigung (etabliert, nicht erneut zu beweisen); geprüft wird die Anwesenheit der Auszeichnung und des Texts.

## Entscheidungen

- **Alle vier Fachkonsultationen des `spec-writer`-Ablaufs sind gelaufen** (`architect`, `ux-ui-designer`, `test-engineer`, `security-engineer`) — keine Skip-Entscheidung. Jede hatte einen konkret benennbaren Anhaltspunkt: berührter Pipeline-Code und Datenmodell, eine sichtbare Oberfläche, nicht-triviales Zähl- und Lauf-Verhalten, eine Datenmodell-Änderung mit einem Geldwert über eine Modulgrenze.
- **Vier statt drei Teilschritte.** `ranking` bekommt einen eigenen Namen, obwohl es fachlich zur Kriterien-Phase gehört: ohne ihn stünde `phase` nach der Landmark-Phase auf `landmark` bei 100 % Fortschritt — dasselbe gemeldete Symptom, nur eine Phase später (ADR 0068 Punkt 1).
- **Live-Zähler bekommen eigene Spalten und fassen die Kosten-Buchführung nicht an.** Ein laufend hochgezähltes `api_calls` löste den Unvollständigkeits-Vorbehalt der Statistikseite bei jedem laufenden Cloud-Lauf als Fehlalarm aus (ADR 0068 Punkt 2).
- **Fremdschlüssel statt Sortier-Heuristik**, in Umkehr von ADR 0050 Punkt 3: „jüngste Remote-Zeile des Projekts" schriebe einem Lauf ohne Cloud-Phase den Geldbetrag des Laufs davor zu. ADR 0050 trägt dafür einen Teil-Vermerk, ihr Entscheidungstext bleibt unberührt.
- **Die Start-Schätzung wird serverseitig berechnet und am Lauf eingefroren** — nicht vom Client mitgeschickt (ungeprüfter Geldwert über die Vertrauensgrenze) und nicht im Worker neu gerechnet (dritte Kopie der Kandidaten-Zählung). Ohne das Einfrieren ist der geforderte Vergleich „Ist gegen Schätzung" nach dem Lauf unmöglich, weil derselbe Endpunkt danach nahe null schätzt.
- **Der Anbieter wird aus dem gespeicherten Modell abgeleitet**, nie aus der aktuellen Betriebseinstellung gelesen — sonst beschriebe die heutige Konfiguration einen vergangenen Lauf.
- **Drei Akzeptanzkriterien wurden auf Testbarkeit geschärft** (Vorschlag `test-engineer`, übernommen): „kein Durchlauf stattgefunden" → „kein Lauf **erfolgreich abgeschlossen**"; „der Fortschritt bewegt sich mit" → Fortschreibung **je Aufruf-Block** samt Zeitstempel; „überfrachtet die Seite nicht" → genau **einer** der beiden Zustandsblöcke, plus kein horizontales Scrollen.
- **Sachliche Korrektur an der Bilanz-Grundlage** (Befund `test-engineer`, übernommen): Der Ist-Betrag entsteht über `compute_cost_usd(model, TokenUsage(...))` aus dem tatsächlichen Tokenverbrauch. Die Bilanz nennt deshalb Modell und Tokenverbrauch; der Preis je Bild bleibt der Schätzung vorbehalten. Eine frühere Fassung des UI/UX-Abschnitts hatte hier den Preis je Bild genannt — das hätte eine Abrechnung behauptet, die so nie stattgefunden hat.
- **Ein nebenbei geschlossener Defekt wird zur Zusage erhoben:** `last_progress_at` wurde während der gesamten Landmark-Phase nicht angefasst. `reap_stalled_runs` setzte einen Lauf mit mehr als 15 Minuten Landmark-Arbeit auf `failed`, **ohne die Coroutine abzubrechen** — er rief danach weiter kostenpflichtig beim Anbieter an, während die Oberfläche „fehlgeschlagen" sagte. Das ist keine Verfügbarkeitsfrage, sondern eine Lücke in der Kostenerkennung, und steht deshalb im geschärften Akzeptanzkriterium statt nur in der Umsetzungsnotiz.
- **Der neue Fremdschlüssel wird explizit benannt** (Muss aus dem Security-Abschnitt): ein per `batch_alter_table` unbenannt angelegter FK ist im `downgrade()` unter SQLite nicht droppbar, der Rückwärtsweg der Migration wäre nicht ausführbar.
- **Zwei sichtbare Änderungen am Auslöser-Bereich, die das Akzeptanzkriterium „der Auslöser bleibt unverändert" nicht wörtlich deckt** (Befund der Review-Runde, hier nachdokumentiert statt stillschweigend gelassen):
  - Die Statuszeile heißt jetzt „Klassifizierung abgeschlossen" bzw. „Klassifizierung fehlgeschlagen" statt „Erfolgreich klassifiziert"/„Fehlgeschlagen". Grund: Der UI/UX-Abschnitt gibt genau diese beiden Texte als Screenreader-Ankündigung beim Wechsel von Fortschritt auf Bilanz vor; zwei verschiedene Formulierungen für denselben Zustand nebeneinander wären die schlechtere Lösung.
  - Der Hinweis „Alle Fotos bereits klassifiziert — keine Cloud-Kosten zu erwarten" erscheint nur noch, wenn der Kandidatenbestand **vollständig bekannt** ist. Ist der Landmark-Anteil unbekannt (vor dem ersten erfolgreichen Lauf), tritt die Aufschlüsselung mit dem Unbekannt-Satz an seine Stelle. Grund: Die alte Aussage beruhte auf `candidate_count == 0` und behauptete damit Kostenfreiheit über eine Menge, die niemand kennt — genau die Fehlaussage, gegen die diese Story geschrieben ist.
  - Unverändert bleiben dagegen die Dinge, die das Kriterium schützt: der Auslöser selbst, die Cloud-Checkbox, das Consent-Gate, der Zeitpunkt der Cloud-Aufrufe und welche Fotos die Installation verlassen.
- **Zwei Abweichungen der Umsetzung von der Umsetzungsplanung dieser Spec**, beide bewusst und hier nachgezogen: `_latest_remote_category_classification_run` wird **nicht** entfernt (sie hat einen zweiten Leser, den 409-Wächter der Projektlöschung — nur ihre Verwendung in `_to_project_out` entfällt), und `ClassificationStepId` ist ein Alias auf den API-Typ `ClassificationPhase` statt eines eigenen String-Unions (eine Quelle statt zweier, die auseinanderlaufen können).
- **Keine Rückfrage an Daniel nötig.** Weder `architect` noch `security-engineer` noch `test-engineer` sind auf eine offene Produktentscheidung gestoßen; alle getroffenen Festlegungen sind technische Detailentscheidungen innerhalb der bereits geschärften Story.

## Offene Fragen

Keine.

## Out of Scope

- Eine Historie früherer Klassifizierungsläufe.
- Änderungen an der Projekt-Statistikseite (`api/stats.py`, `ProjectStatsPage.tsx`) — sie bleibt die projektweite Auswertung über alle Läufe hinweg.
- Ein zweiter Auslöser sowie jede Änderung daran, wann Cloud-Aufrufe stattfinden oder welche Fotos die Installation verlassen.
