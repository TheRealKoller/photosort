# 0590 - Klassifizierung mit Cloud bricht bei großen Projekten fälschlich als Stillstand ab

**Status:** Accepted
**Erstellt:** 2026-10-07
**Bezug:** [Issue #590](https://github.com/TheRealKoller/photosort/issues/590)

## Ziel

Bei einem größeren Projekt bricht die Klassifizierung mit Cloud-Kategorisierung nach rund 15 Minuten mit „Kein Fortschritt seit über 15 Minuten erkannt — vermutlich hängender Verarbeitungsschritt" ab, obwohl der Lauf arbeitet. Der Status wird FAILED, die Verarbeitung läuft kostenpflichtig weiter. Ein lange, aber stetig laufender Schritt darf nie als Stillstand gelten.

## User Story

Als Nutzer, der ein großes Projekt mit Cloud-Bilderkennung klassifiziert, möchte ich, dass der Lauf nur dann als fehlgeschlagen gilt, wenn er tatsächlich hängt, damit ich große Projekte ohne Fehlalarm klassifizieren kann.

## Akzeptanzkriterien

- [ ] **AK1** Läuft ein Klassifizierungslauf mit aktiver Cloud-Nutzung in der Phase `remote_categories`, wird bei jedem Block-Commit der Remote-Kategorisierung (worker.py ~Z. 3577–3579) auch `CriterionScoringRun.last_progress_at` des übergeordneten Laufs auf denselben `_now_utc()`-Wert gesetzt und im selben Commit festgeschrieben. Prüfbar: Nach jedem Block gilt `parent.last_progress_at == remote_run.last_progress_at`, und der Wert ist neuer als der beim Anlegen.
- [ ] **AK2** Liegt der letzte Block-Commit der Remote-Phase weniger als 15 Minuten zurück (Grenze: genau 15:00 zählt nicht, wie bisher), setzt `reap_stalled_runs` weder den RemoteCategoryClassificationRun noch den übergeordneten CriterionScoringRun auf FAILED. Das ergibt sich direkt aus AK1 und den bestehenden Reaper-Tests.
- [ ] **AK3** Ohne neuen Block-Commit wird der Stempel des übergeordneten Laufs nicht vorgeschoben. Es gibt keinen Heartbeat und keinen Timer, der unabhängig vom Fortschritt stempelt. Ist er strikt älter als 15 Minuten, wird der Lauf wie bisher mit `_stall_message` auf FAILED gesetzt.
- [ ] **AK4** Die Phase `criteria` mit der Landmark-Teilphase, der Lauf ohne Cloud (es entsteht kein RemoteCategoryClassificationRun) und der Fehlerpfad der Remote-Phase (`cloud_error_message`, danach läuft `criteria` weiter) verhalten sich wie bisher. Die bestehenden Tests in test_worker_classification.py, test_worker_criterion_scoring.py, test_worker_remote_category_classification.py und test_worker_reap_stalled_runs.py bleiben ohne Änderung grün.
- [ ] **AK5** Wird `run_remote_category_classification` ohne übergeordneten Lauf aufgerufen (`parent_run=None`), stempelt sie wie bisher nur ihre eigene Zeile.

## Datenmodell-Bezug

Keiner — bestehende Spalte `last_progress_at` an `criterion_scoring_runs`.

## Architektur / Umsetzung

**Ansatz:** Während der Phase `remote_categories` erhält auch der übergeordnete `CriterionScoringRun` an jedem Block-Commit seinen Fortschrittsstempel. `reap_stalled_runs` bleibt unverändert. Er liest weiterhin ausschließlich `last_progress_at` je Tabelle; das ist die etablierte Zusage, siehe Docstring des Landmark-Watchdog-Tests in `test_worker_criterion_scoring.py`. Damit wird dieselbe Lücke geschlossen wie zuvor bei der Landmark-Phase (`worker.py` ~Z. 2955–2966) und der Seitenverhältnis-Runde des Scans (~Z. 774–806): Jeder Commit-Punkt, der echte Arbeit abschließt, setzt den Stempel des Laufs, den die Oberfläche als laufend zeigt.

**Verworfen:** Den Reaper so umbauen, dass er den Parent über den verknüpften Remote-Lauf beurteilt, etwa mit `greatest(parent, child)` per Join. Das bräche die Regel „der Reaper liest nur `last_progress_at` der eigenen Zeile“, verschöbe die Fortschrittslogik aus dem Worker-Lauf in die Abfrage und beträfe alle vier Tabellen (AK 3).

**Betroffene Stellen (`backend/src/photosort/worker.py`):**

1. `run_remote_category_classification`: neuer keyword-only Parameter `parent_run: CriterionScoringRun | None = None`. Am bestehenden Block-Commit-Punkt (~Z. 3578) wird **ein** `_now_utc()`-Wert in `run.last_progress_at` und, falls `parent_run` gesetzt ist, auch in `parent_run.last_progress_at` geschrieben. Beides geht in denselben Commit, kein zweiter. Direktaufrufe ohne Parent, etwa aus Tests, verhalten sich unverändert.
2. `run_classification` (~Z. 3171): `parent_run=run` durchreichen.
3. Docstring/Kommentar am Stempel: Warum der Parent mitgestempelt werden muss (Reaper setzt den Parent sonst auf FAILED, die Coroutine läuft kostenpflichtig weiter).

**Phasenwechsel `remote_categories` → `criteria`:** Hier ist kein eigener Stempel nötig. Nach Punkt 1 liegt der letzte Parent-Stempel am letzten Remote-Block. Bis zum ersten Kriterien-Stempel vergehen nur Aufräumarbeit (`aclose`, Kosten-Commit), Guard-Abfrage, Kandidatenladen, Modellaufbau und der erste Batch von `CRITERION_SCORING_COMMIT_BATCH_SIZE`. Das ist dieselbe Strecke, die ein Lauf ohne Cloud heute ab seiner Anlage hat. `_set_phase` bleibt unverändert und setzt bewusst nur `phase` und `phase_started_at` (ADR 0116).

**Fehlerpfad:** Scheitert der Remote-Lauf, setzt `_fail_run` ihn per Rollback auf FAILED. Der Parent-Stempel des zuletzt committeten Blocks bleibt erhalten, ein unvollständiger Block wird verworfen. AK 2 bleibt gewahrt: Ohne neuen Block-Commit altern beide Stempel, und beide Läufe werden nach `STALL_THRESHOLD` gereapt.

**Tests (in `test_worker_criterion_scoring.py` oder im Testmodul der Remote-Klassifizierung, Muster wie der Landmark-Watchdog-Test bei ~Z. 3635):**
- Kontrollierte `_now_utc`-Ticks, Ablauf über `run_classification` mit Cloud. Erwartet: `CriterionScoringRun.last_progress_at` bewegt sich während der Remote-Phase mit jedem Block und ist gleich dem Stempel des Remote-Laufs.
- Direktaufruf ohne `parent_run` funktioniert unverändert.
- Kein neuer Fall in `test_worker_reap_stalled_runs.py`, weil der Reaper unverändert bleibt.

**Reihenfolge:** zuerst der Test, rot; dann Parameter und Stempel in `run_remote_category_classification`; dann das Durchreichen in `run_classification`.

## UI/UX

nicht relevant — keine Änderung an einer Oberfläche; die bestehende Statusanzeige zeigt danach den tatsächlichen Laufzustand.

## Security

nicht relevant — kein Bezug zu Auth, Eingaben von außen, Secrets, Berechtigungen, Datenmodell oder Datensichtbarkeit.

## Teststrategie

- **Ebene:** Integrationstest auf Worker-Ebene in backend/tests/test_worker_classification.py, über den bestehenden Helper `run_classification(...)` (Z. ~238) mit der In-Memory-SQLite-Session und einem gefälschten Category-Client. Kein Redis, kein arq, kein echtes Warten. Wie im Präzedenzfall `test_last_progress_at_advances_during_the_landmark_phase` (test_worker_criterion_scoring.py:3632) kommt bewusst kein zusätzlicher Test in test_worker_reap_stalled_runs.py dazu: Der Reaper liest nur `last_progress_at`, und das ist dort für CriterionScoringRun schon abgedeckt (stalled, Grenze 15:00, aktiver Lauf).
- **Zeit:** `monkeypatch.setattr(worker, "_now_utc", lambda: next(ticks))` mit monoton steigenden Ticks, z. B. `datetime(2030,1,1,12,0,s)` oder Minutenabstände wie 12:00, 12:10, 12:20, 12:30. Damit liegt die Remote-Phase in der simulierten Zeit über 15 Minuten. `remote_category_classification_concurrency=1` sorgt für einen Block pro Foto, Projekt mit 3 Fotos. Ein Snapshot-Category-Client (Vorlage: `SnapshottingCategoryClient` in test_worker_remote_category_classification.py:1858) liest vor jedem `classify()` per Query über die Session den übergeordneten CriterionScoringRun des Projekts und zeichnet `last_progress_at` auf.
- T1 (AK1, Kern): Die Snapshots der Eltern-Stempel sind monoton, und der letzte Snapshot ist strikt größer als der erste. Da `_now_utc` gepatcht ist, folgt der Stempel exakt den Ticks und ist deterministisch.
- T2 (AK2, Ende-zu-Ende ohne Dopplung, optional, aber empfohlen): Nach dem letzten Remote-Block wird `reap_stalled_runs({}, session_factory=make_session_factory(db_session.bind))` direkt im Client aufgerufen, mit `_now_utc` = letzter Tick + 14 min. Der Elternlauf ist dann nicht FAILED, obwohl seit dem Anlegen mehr als 15 min simuliert sind. Der Test belegt den gemeldeten Symptomfall unmittelbar.
- T3 (AK3): Ein Category-Client, dessen Aufruf ein Event nie freigibt (oder vor dem ersten Block-Ende abbricht): Der Eltern-Stempel bleibt auf seinem Anlagewert, ein Heartbeat würde hier sichtbar. Alternativ und billiger: Es reicht die Aussage, dass nur Block-Commits stempeln. Dafür sind die Snapshots aus T1 vor dem ersten Block gleich dem Anlagewert, also gibt es keinen Stempel vor dem ersten Fortschritt.
- T4 (AK4): Keine neuen Tests. Die bestehende Suite ist der Nachweis. Hinzu kommt ein Testfall für den Lauf ohne Cloud: Der Stempel des Elternlaufs bewegt sich in der Remote-Phase nicht, weil es sie nicht gibt. Den decken bestehende Tests mit ExplodingClient ab.

**Edge Cases:**

- Block, der nur aus fehlgeschlagenen Einzelaufrufen besteht (`failed_calls` steigt): Das zählt als Fortschritt und stempelt den Elternlauf, so wie die Remote-Zeile heute auch gestempelt wird.
- Die Remote-Phase endet mit FAILED: Der Elternlauf geht in `criteria` über und stempelt dort selbst. Kein Fehlalarm in der Übergabelücke.
- `server_default now()` beim Anlegen gegenüber der gepatchten Uhr: Assertions vergleichen Snapshots untereinander und mit den Tick-Werten, nie mit der Wanduhr.
- Grenze genau 15:00: Sie ist schon in test_worker_reap_stalled_runs.py für das Reaper-Verhalten abgedeckt und wird hier nicht wiederholt.
- Die Session läuft mit expire_on_commit=False, der Snapshot liest das Identity-Map-Objekt. Das ist wie beim Landmark-Präzedenzfall akzeptabel, weil Attribut und Commit im selben Codepfad sitzen. Wer Sichtbarkeit für eine andere Verbindung belegen will, nutzt das `_recording_commit`-Muster (test_worker_criterion_scoring.py:3612).

**Rot-Nachweis:** T1 auf dem unveränderten main-Stand ausführen: Alle Eltern-Snapshots tragen denselben Anlagewert (`stamps[-1] == stamps[0]`), die Assertion schlägt mit der Meldung „last_progress_at des übergeordneten Laufs hat sich während der Remote-Phase nicht bewegt“ fehl. T2 schlägt auf main fehl, weil der Elternlauf nach dem Reaper-Aufruf FAILED mit `_stall_message` ist. Beides vor dem Fix ausführen und im Abschlussbericht vermerken.

## Entscheidungen

- Parent wird am Block-Commit der Remote-Phase mitgestempelt; Reaper bleibt unverändert. Keine ADR.
- ux-ui-designer nicht konsultiert (Schritt 2): keine sichtbare Oberfläche berührt, nur ein Zeitstempel im Worker.
- security-engineer nicht konsultiert (Schritt 3): kein Bezug zu Auth, externen Eingaben, Secrets, Berechtigungen, Datenmodell oder Datensichtbarkeit.
- Story ohne `refinement` direkt aus dem Bug-Gespräch entstanden; Daniel hat die direkte Behebung freigegeben (2026-10-07).

## Offene Fragen

Keine.

## Out of Scope

- Ranking-Teilschritt ohne Stempel: Weder das Schreiben der lokalen Motiv-Kopfzeilen (~Z. 3018–3030) noch `_set_phase(RANKING)` (~Z. 3037) noch `_build_grouping_and_rankings` setzen `last_progress_at`. Dauern beide bei einem sehr großen Projekt zusammen mehr als 15 min seit dem letzten Kriterien- bzw. Landmark-Stempel, setzt der Reaper einen arbeitenden Lauf auf FAILED. Das gilt auch ohne Cloud. Eigene Story vorgeschlagen.
- Kriterien-Prelude: Zwischen Phasenbeginn bzw. Anlage und dem ersten Stempel liegen Modellaufbau (fünf `_try_build`) und `CRITERION_SCORING_COMMIT_BATCH_SIZE` Fotos. Der letzte Teilbatch nach dem Schleifenende (~Z. 2670) committet `photos_processed`, aber ohne Stempel. Das ist heute unkritisch und fällt nur bei extrem langsamem Modellaufbau ins Gewicht; nur festgehalten.
- Landmark-Phase: `_set_phase(LANDMARK)` (~Z. 2689) stempelt nicht. Die Strecke bis zum ersten Landmark-Block ist kurz, ein Risiko ist nicht erkennbar; nur festgehalten.
