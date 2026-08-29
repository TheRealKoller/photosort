# 0042 - Pre-Merge-Finalisierung im Feature-PR statt Post-Merge-Nachzieh-PR

**Status:** Accepted
**Datum:** 2026-08-29
**Bezug:** GitHub-Issue [`#248`](https://github.com/TheRealKoller/photosort/issues/248) ("überprüfen der post-merge-finalisierung"), `specs/features/0066-pre-merge-finalisierung-im-feature-pr.md` (neu, aus dieser ADR hervorgegangen), ADR [`0037`](./0037-status-lebenszyklus-umsetzungsfortschritt-pr-merge-erkennung.md) (Abschnitt 5 — die dort eingeführte PR-Merge-Erkennung bleibt im Code, wechselt aber vom Regel- zum Ausnahmepfad; alle übrigen Abschnitte unverändert gültig), ADR [`0017`](./0017-github-projects-v2-spec-sync.md) (Abschnitt 4: Board als Einbahnstraßen-Projektion, unverändert)

## Kontext

ADR 0037, Abschnitt 5, hat die Finalisierung einer Feature-Spec (`Accepted` → `Implemented ([PR #NNN](url))`) bewusst *hinter* den Merge gelegt: `_sync_one()` fragt für jede Spec mit `runtime_status == "Review"` und gespeicherter `pr_number` den PR-Zustand ab und schreibt die Spec-Datei um, sobald er `merged` ist. Damit war die Nachvollziehbarkeit maximal — nichts wird als umgesetzt geführt, was nicht tatsächlich gemergt wurde.

Der Preis dieser Reihenfolge ist im Betrieb sichtbar geworden: Die umgeschriebene Spec-Datei plus der aktualisierte Eintrag in `specs/.github-sync-state.json` sind lokale Änderungen, die nach dem Merge nur noch über einen **neuen** Pull Request auf den geschützten `main`-Branch kommen. Genau das ist zuletzt bei praktisch jedem Feature passiert (`#250`, `#245`, `#242`, `#237`, `#231`, …): ein Zwei-Zeilen-PR, der die komplette CI-Pipeline (Backend inkl. ~113 MiB Modell-Download, Frontend, zwei Skript-Pakete) erneut durchläuft und eine zweite Merge-Runde kostet.

Beide Dateien sind zwingend Teil derselben Änderung: schreibt man nur die Spec-Datei fort, weicht der `pushed_state_hash` im State-Eintrag ab (der Hash deckt Status *und* Inhaltszone ab), und der nächste Sync-Lauf erzeugt erneut eine lokale, zu committende Änderung — das Folge-PR wäre nur verschoben, nicht vermieden.

## Entscheidung

### 1. Regelweg ist die Finalisierung *vor* dem Merge, im Feature-PR selbst

Die Statuszeile wird zum letzten Commit des Feature-Branches, nicht zum ersten Commit eines Folge-PRs. Dadurch enthält der ursprüngliche Feature-PR bereits den vollständigen, konsistenten Endzustand (Spec-Datei `Implemented ([PR #NNN](url))` + passender State-Eintrag), und mit seinem Merge ist die Spec fertig finalisiert — ohne zweiten PR.

### 2. Expliziter Finalisierungsmodus im Sync-Tool: `--only NNNN --finalize --pr-number NNN`

Neue Funktion `sync.py::finalize_feature_spec()` (analog zum bereits bestehenden, zielgerichteten `set_feature_runtime_status()`):

1. `validate_spec_number()`, Feature-State-Eintrag muss existieren, Datei-Status muss `Accepted` sein.
2. `gh.get_pull_request(pr_number)` (bereits vorhandene Adapter-Methode aus ADR 0037): Zustand `closed` — geschlossen, ohne gemergt zu sein — bricht ab; `open` ist der Regelfall (kurz vor dem Merge), `merged` ist zulässig und deckt den nachträglichen/wiederholten Aufruf ab.
3. Weicht eine im State gespeicherte `pr_number` von der übergebenen ab, bricht der Aufruf ab (Verwechslungsschutz). Ohne gespeicherte `pr_number` (kein vorheriger `--runtime-status Review`-Lauf) ist der Aufruf zulässig.
4. `spec_parser.set_status_line()` schreibt die Header-Zeile auf `Implemented ([PR #NNN](url))` — dieselbe Funktion und dasselbe Textformat wie die Merge-Erkennung, kein zweites Format.
5. Der eigentliche Push läuft danach über den **regulären** `run_sync(only=NNNN)`-Pfad. Kein Sonderpfad für Board-Feld, Issue-Zustand, Labels oder State: die Spec ist ab Schritt 4 eine ganz normale `Implemented`-Spec (Baseline `Done`, Issue geschlossen, `runtime_status`/`pr_number` defensiv geleert, neuer `pushed_state_hash`).

Der Aufrufpunkt ist `ship-feature` — der einzige Schritt des Ablaufs mit GitHub-Schreibzugriff (ADR 0037, Abschnitt 4). `developer` bekommt diese Verantwortung ausdrücklich **nicht**; die Grenze "kein GitHub-Schreibzugriff im Subagenten" (ADR 0024/0037) bleibt unangetastet.

### 3. Zeitpunkt: nach Review und Copilot-Auswertung, gebündelt mit dem letzten Push

Die Finalisierung passiert, wenn Review-Runde und Copilot-Review ausgewertet und alle Muss-Fix-Findings behoben sind — und zwar zusammen mit dem Push dieser letzten Fixes, sodass im Regelfall **kein zusätzlicher CI-Lauf** entsteht. Erst danach folgen Daniels Freigabe und der Merge.

Damit ist der Status bewusst gesetzt, während die CI über den finalen Stand noch läuft. Das ist kein Rückfall in den mit ADR 0037, Abschnitt 4, abgeschafften Zustand (`Implemented` direkt nach `gh pr create`, also vor jedem Review): wirksam wird der Status auf `main` weiterhin ausschließlich durch den Merge, und der setzt grüne CI und Daniels Freigabe voraus. Ein Finalisierungs-Commit erst nach grüner CI würde dagegen exakt den CI-Lauf für eine reine Metadaten-Änderung erzwingen, den Issue #248 abschaffen will — der Nutzen der Änderung wäre damit weitgehend aufgehoben.

### 4. Vorgezogener Board-Wert `Done` ist zulässig, weil das Board selbstheilend ist

Mit der Finalisierung springt die Board-Spalte auf `Done` und das Issue wird geschlossen, obwohl der PR noch offen ist — ein Zeitfenster von typischerweise Minuten. Das ist vertretbar, weil das Board seit ADR 0017, Abschnitt 4, keine eigene Wahrheit hält, sondern bei jedem Lauf aus der lokalen Datei neu berechnet wird: Wird der PR doch nicht gemergt (Branch verworfen), führt `main` die Spec weiterhin als `Accepted`, und der nächste Sync-Lauf setzt Spalte und Issue-Zustand selbsttätig zurück. Ein Hinweis darauf steht im `ship-feature`-Skill, damit dieser Fall bewusst behandelt und nicht als Datenverlust missverstanden wird.

### 5. Die automatische PR-Merge-Erkennung bleibt — als Ausnahmepfad

`_sync_one()` behält die Merge-Erkennung aus ADR 0037, Abschnitt 5, unverändert inklusive `SpecSyncResult.finalized_from_pr`. Sie greift genau dann, wenn die reguläre Pre-Merge-Finalisierung nicht stattgefunden hat: Merge außerhalb des üblichen Ablaufs, abgebrochene Session, manuell gemergter PR. Damit bleibt Akzeptanzkriterium 3 der Story erfüllt, ohne dass ein zweiter manueller Befehl (`--mark-done` o.ä.) nötig wäre. Dokumentiert wird sie ab jetzt als Ausnahme, nicht mehr als Regelweg (`.claude/skills/github-project-sync/SKILL.md`).

## Verworfene Alternativen

- **GitHub-Actions-Workflow, der nach dem Merge die Statuszeile auf `main` committet:** wäre ein zweiter, unkontrollierter Schreiber neben `sync.py` (Board *und* Repository), widerspricht der in ADR 0017/0030/0037 mehrfach bekräftigten Grundregel, dass ausschließlich der getestete `sync.py`/`gh_adapter`-Layer schreibt, und würde zusätzlich einen Push auf den geschützten Default-Branch aus CI heraus erfordern.
- **Nur die Spec-Datei vorziehen, den State-Eintrag beim nächsten Sync nachziehen:** verschiebt das Folge-PR nur, statt es zu vermeiden (der `pushed_state_hash` deckt den Status mit ab, siehe Kontext).
- **Finalisierung erst nach grüner CI, unmittelbar vor dem Merge:** streng genommen die sauberste Reihenfolge, kostet aber genau den CI-Lauf für eine reine Metadaten-Änderung, den die Story abschaffen will (siehe Abschnitt 3). Ein Merge ohne erneuten CI-Lauf ist keine Option, solange `main` geschützt ist und Statuschecks verlangt.
- **Pfadfilter in `.github/workflows/ci.yml` (Doku-/Spec-only-PRs überspringen die schweren Jobs):** löst das Problem nicht — bei `pull_request`-Events wertet GitHub Actions den gesamten PR-Diff aus, und der enthält beim Feature-PR weiterhin Code. Als eigenständige Idee für reine Doku-PRs bleibt das unbenommen, ist aber nicht Teil dieser Entscheidung.
- **Squash-Merge mit nachträglich ergänzter Commit-Message statt Statuszeile:** die Spec-Datei ist die Quelle der Wahrheit für den Status (`specs/README.md`); eine Commit-Message ersetzt sie nicht.

## Konsequenzen

- **`scripts/github-project-sync/src/github_project_sync/sync.py`:** neue Funktion `finalize_feature_spec()`; `_sync_one()`/`run_sync()` unverändert.
- **`scripts/github-project-sync/src/github_project_sync/cli.py`:** neues Flag `--finalize` (erfordert `--only NNNN` im bare Feature-Scope und `--pr-number`, unverträglich mit `--runtime-status`, `--adopt-issue`, `--create-issue`, `--show-status`); `--pr-number` ist damit nicht mehr ausschließlich an `--runtime-status Review` gebunden.
- **Tests:** `tests/test_sync_integration.py` (Finalisierungs-Happy-Path, Abbruchfälle, Idempotenz, Folgelauf-`unchanged`-Regression), `tests/test_cli.py` (Flag-Validierung, JSON-Ausgabe, Fehlerkonvention) — netzwerkfrei über `FakeGhAdapter` wie der gesamte Bestand.
- **`.claude/skills/ship-feature/SKILL.md`:** neuer Schritt "Finalisierung im selben PR" nach der Copilot-Auswertung, inkl. Verhalten bei nicht gemergtem PR.
- **`.claude/skills/github-project-sync/SKILL.md`:** dokumentiert `--finalize`; `finalized_from_pr` wird als Ausnahmepfad beschrieben.
- **`docs/ai-workflow.md`:** die Schritt-Tabelle 2–8 bekommt den Finalisierungsschritt.
- **Kein Effekt auf `docs/architecture.md`/`docs/setup.md`/Root-`README.md`** — reines Entwickler-/Prozess-Tooling ohne PhotoSort-System-/Datenmodell-Bezug, identische Einordnung wie ADR 0017/0030/0036/0037.
- **`specs/README.md`:** unverändert — der Datei-Lebenszyklus `Proposed → Accepted → Implemented → Superseded` bleibt exakt bestehen, nur der Zeitpunkt des letzten Übergangs verschiebt sich vom Post- in den Pre-Merge-Moment.
- **ADR 0037 bleibt `Accepted`** und in allen Abschnitten gültig; Abschnitt 5 beschreibt ab jetzt den Ausnahme- statt den Regelpfad und erhält einen Nachtrag-Verweis auf diese ADR.
- Ein späterer Wechsel dieses Modells (z.B. doch CI-seitige Automatisierung nach dem Merge) bleibt architekturrelevant und braucht eine neue, diese ADR als "Superseded" markierende ADR.
