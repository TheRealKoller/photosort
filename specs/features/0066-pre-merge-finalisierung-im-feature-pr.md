# 0066 - Pre-Merge-Finalisierung: Spec-Status im Feature-PR statt im Nachzieh-PR

**Status:** Accepted
**Erstellt:** 2026-08-29
**Bezug:** [GitHub-Issue #248](https://github.com/TheRealKoller/photosort/issues/248), [`decisions/0042-pre-merge-finalisierung-statt-nachzieh-pr.md`](../decisions/0042-pre-merge-finalisierung-statt-nachzieh-pr.md) (neue ADR dieser Spec), [`decisions/0037-status-lebenszyklus-umsetzungsfortschritt-pr-merge-erkennung.md`](../decisions/0037-status-lebenszyklus-umsetzungsfortschritt-pr-merge-erkennung.md) (Abschnitt 5 — die dort eingeführte PR-Merge-Erkennung bleibt bestehen, wird aber vom Regel- zum Ausnahmepfad)

## Ziel

Nach dem Merge eines Feature-Pull-Requests entsteht aktuell zuverlässig ein zweites, separates Pull Request, das ausschließlich den Spec-Status auf "Implemented" nachträgt (zuletzt z.B. [#250](https://github.com/TheRealKoller/photosort/pull/250), [#245](https://github.com/TheRealKoller/photosort/pull/245), [#242](https://github.com/TheRealKoller/photosort/pull/242)). Ursache ist die Reihenfolge aus ADR 0037, Abschnitt 5: die Finalisierung passiert erst *nach* dem Merge, wenn der nächste Sync-Lauf den gemergten PR erkennt und die Spec-Datei lokal auf `Implemented` umschreibt — zu einem Zeitpunkt, an dem der ursprüngliche PR bereits geschlossen ist und die Änderung nur noch über einen neuen PR nach `main` kommt.

Dieses zweite PR durchläuft die komplette CI-Pipeline erneut (Backend inkl. Modell-Download, Frontend, beide Skript-Pakete), obwohl es inhaltlich nur zwei Zeilen Metadaten ändert: die `**Status:**`-Zeile der Spec-Datei und den zugehörigen Eintrag in `specs/.github-sync-state.json`.

Ziel ist, die Finalisierung in den ursprünglichen Feature-PR vorzuziehen: sie wird zum letzten Commit *vor* dem Merge, statt zum ersten Commit eines Folge-PRs danach.

## User Story

Als Daniel möchte ich, dass nach Abschluss eines Feature-Pull-Requests keine zusätzliche, separate Pull-Request-Runde mehr allein für die Status-Finalisierung nötig ist, damit ich nicht wiederholt eine komplette CI-Pipeline für eine reine Metadaten-Änderung abwarten muss.

## Akzeptanzkriterien

- [x] Nach einem gemergten Feature-Pull-Request gibt es im Normalfall kein separates, ausschließlich der Finalisierung dienendes Folge-PR mehr.
- [x] Der betroffene Spec-Status wird spätestens mit dem Merge des ursprünglichen Feature-PRs korrekt auf `Implemented` (inkl. PR-Referenz) gesetzt — nicht bereits, bevor Review und Copilot-Auswertung abgeschlossen sind (siehe "Entscheidungen", Punkt 3, zur Einordnung der noch laufenden CI).
- [x] Für den Ausnahmefall, dass die Finalisierung nicht wie vorgesehen erfolgt ist (z.B. bei einem Merge außerhalb des üblichen Ablaufs), bleibt ein Weg bestehen, den Status nachträglich korrekt nachzuziehen, ohne dass das zum Regelfall wird.
- [x] Die Nachvollziehbarkeit der Statuswerte bleibt erhalten — kein Feature wird auf `main` als `Implemented` geführt, dessen Pull Request tatsächlich nicht gemergt wurde.
- [x] Nach dem Merge eines regulär finalisierten Feature-PRs erzeugt ein anschließender `--only NNNN`-Sync-Lauf für diese Spec keine erneut zu committende lokale Änderung (weder in der Spec-Datei noch im Sync-State-Eintrag außer dem laufenden `last_synced_at`).
- [x] Ein Pull Request, der geschlossen wurde ohne gemergt zu werden, kann über den Finalisierungsweg nicht zu einem `Implemented`-Status führen.

## Datenmodell-Bezug

Kein Bezug zum PhotoSort-Datenmodell (Projekte/Fotos/Bewertungen, siehe [`docs/architecture.md`](../../docs/architecture.md)) — betroffen ist ausschließlich das Entwickler-Tooling `scripts/github-project-sync` und dessen Zustandsdatei `specs/.github-sync-state.json` (Feature-Namensraum: `runtime_status`, `pr_number`, `pushed_state_hash`).

## Architektur / Umsetzung

Vollständige Begründung und Abwägung der verworfenen Alternativen: ADR [`decisions/0042-pre-merge-finalisierung-statt-nachzieh-pr.md`](../decisions/0042-pre-merge-finalisierung-statt-nachzieh-pr.md).

1. **Neuer, expliziter Finalisierungsmodus im Sync-Tool** — `--only NNNN --finalize --pr-number NNN`, umgesetzt als `sync.py::finalize_feature_spec()`:
   - validiert Spec-Nummer, vorhandenen Feature-State-Eintrag und Datei-Status (`Accepted`; alles andere bricht ab),
   - liest den PR über die bereits vorhandene Adapter-Methode `get_pull_request()`; Zustand `closed` (geschlossen ohne Merge) bricht ab, `open` (Regelfall: kurz vor dem Merge) und `merged` (Ausnahme-/Wiederholungsfall) sind zulässig,
   - schreibt die `**Status:**`-Zeile über das bestehende `spec_parser.set_status_line()` auf `Implemented ([PR #NNN](url))`,
   - delegiert danach den eigentlichen Push an den regulären `run_sync(only=NNNN)`-Pfad: keine Sonderlogik für Board-Feld, Issue-Zustand, Labels oder State-Eintrag — die Spec verhält sich ab hier wie jede andere `Implemented`-Spec (Board-Baseline `Done`, Issue geschlossen, `runtime_status`/`pr_number` geleert, `pushed_state_hash` neu).
   - Ergebnis-JSON: `{"spec_number", "pr_number", "status_line", "issue_number", "classification"}`; Fehler wie überall als `{"error": "..."}`.
2. **Stimmt eine gespeicherte `pr_number` nicht mit der übergebenen überein**, bricht der Aufruf ab (Verwechslungsschutz für Akzeptanzkriterium 4). Ist keine gespeichert (Finalisierung ohne vorherigen `--runtime-status Review`-Lauf), ist das zulässig.
3. **Aufrufpunkt** ist der Skill `ship-feature` (einziger Punkt im Ablauf mit GitHub-Schreibzugriff): nach abgeschlossener Review-Runde *und* ausgewertetem Copilot-Review, gebündelt mit dem letzten Push des Feature-Branches, sodass im Regelfall kein zusätzlicher CI-Lauf entsteht.
4. **Die PR-Merge-Erkennung aus ADR 0037, Abschnitt 5 (`finalized_from_pr`) bleibt unverändert im Code** — sie greift weiterhin für jede Spec, die mit `runtime_status == "Review"` und gesetzter `pr_number` in einen Merge gelaufen ist, ohne vorher finalisiert worden zu sein. Sie ist damit der dokumentierte Ausnahmepfad (Akzeptanzkriterium 3), nicht mehr der Regelweg.

Betroffene Dateien: `scripts/github-project-sync/src/github_project_sync/sync.py`, `.../cli.py`, `scripts/github-project-sync/tests/test_sync_integration.py`, `.../test_cli.py`, `.claude/skills/ship-feature/SKILL.md`, `.claude/skills/github-project-sync/SKILL.md`, `docs/ai-workflow.md`.

## UI/UX

Nicht relevant — reines Entwickler-/Prozess-Tooling ohne sichtbare Oberfläche (kein Frontend-Bezug).

## Teststrategie

Unit-/Integrationsebene im bestehenden, netzwerkfreien Muster des Pakets (`FakeGhAdapter`, keine echten `gh`-Aufrufe — siehe [`architecture/0002-testkonzept.md`](../architecture/0002-testkonzept.md)):

- `finalize_feature_spec()`: Happy Path bei offenem PR (Status-Zeile inkl. PR-Link, Board `Done`, Issue geschlossen, `runtime_status`/`pr_number` geleert, Hash aktualisiert); Idempotenz-/Wiederholungsfall bei bereits gemergtem PR; Abbruch bei `closed`-PR; Abbruch bei Datei-Status ≠ `Accepted`; Abbruch ohne State-Eintrag; Abbruch bei abweichender gespeicherter `pr_number`; unbekannte Spec-Nummer; Prioritäts-Feld wird nicht angefasst.
- Regressionstest zu Akzeptanzkriterium 5: nach einer Finalisierung klassifiziert ein direkt folgender `run_sync(only=...)`-Lauf dieselbe Spec als `unchanged` und schreibt die Spec-Datei nicht erneut um.
- CLI-Ebene: `--finalize` erfordert `--only NNNN` (bare Feature-Scope) und `--pr-number`, verträgt sich nicht mit `--runtime-status`/`--adopt-issue`/`--create-issue`, gibt das Ergebnis-JSON aus und meldet Fehler als `{"error": ...}` mit Exit-Code 1.

## Security

Nicht relevant im Sinne neuer Bedrohungen: kein neuer Eingabekanal von außen, keine neuen Secrets, keine geänderte Datensichtbarkeit. Die einzige sicherheitsnahe Eigenschaft ist die bereits im Bestand etablierte Pfad-Traversal-Verteidigung über `validate_spec_number()` vor jeder Dateipfad-Konstruktion aus einer Spec-Nummer — sie wird im neuen Pfad genauso angewandt. Die PR-Nummer wird ausschließlich als Ganzzahl (`argparse type=int`) verarbeitet und in eine `gh`-Argumentliste (kein Shell-String) übergeben.

## Entscheidungen

- **Finalisierung als expliziter Aufruf, nicht als Automatismus:** konsistent mit dem rein Pull-/Recompute-basierten Modell des Projekts (nichts läuft unaufgefordert im Hintergrund, ADR 0037, Abschnitt 5). Kein GitHub-Actions-Workflow, der nach dem Merge auf `main` committet — das wäre ein zweiter, unkontrollierter Schreiber neben `sync.py` (ADR 0042, Abschnitt "Verworfene Alternativen").
- **Board-Wert `Done` und geschlossenes Issue entstehen bereits mit der Finalisierung, also wenige Minuten vor dem Merge.** Bewusst in Kauf genommen: Das Board ist seit ADR 0017 eine bei jedem Lauf neu berechnete Projektion — wird der PR wider Erwarten nicht gemergt, stellt der nächste Sync-Lauf aus der Datei auf `main` (weiterhin `Accepted`) sowohl Board-Spalte als auch Issue-Zustand selbsttätig wieder her.
- **Verhältnis zu Akzeptanzkriterium 2 ("nicht bevor alle Prüfungen abgeschlossen sind"):** Die Finalisierung passiert nach Review und Copilot-Auswertung, aber bewusst gebündelt mit dem letzten Push — die CI läuft danach noch einmal über den finalen Stand. Anders wäre das Ziel der Story nicht erreichbar: ein Finalisierungs-Commit erst *nach* grüner CI würde genau den CI-Lauf für eine reine Metadaten-Änderung erzwingen, den die Story vermeiden will. Wirksam wird der `Implemented`-Status auf `main` weiterhin ausschließlich durch den Merge, der Daniels Freigabe und grüne CI voraussetzt — der verfrühte Zustand aus ADR 0037, Abschnitt 4 (Status direkt nach `gh pr create`) kehrt damit nicht zurück.
- **Kein neuer `--mark-done`-Alias für den Ausnahmefall:** die bestehende automatische Merge-Erkennung deckt ihn bereits ab; ein zweiter manueller Befehl für denselben Zweck wäre redundant.
- **Keine Konsultation der Fachagenten (`architect`, `ux-ui-designer`, `test-engineer`, `security-engineer`) in dieser Session:** die Session läuft im Hintergrund (Claude Code on the web) mit ausdrücklicher Vorgabe, keine Subagenten zu starten; die Inhalte der Abschnitte "Architektur / Umsetzung", "Teststrategie" und "Security" sind stattdessen direkt hier festgehalten und in ADR 0042 begründet.

## Out of Scope

- Die zweite, in der Historie sichtbare Sorte von Nachzieh-PRs ("Story-State-Eintrag für Issue #NNN nachtragen", entsteht beim Anlegen/Verfeinern von Story-Issues) — anderer Auslöser, eigene Story.
- CI-Laufzeit oder Pfadfilter der Pipeline selbst (`.github/workflows/ci.yml` bleibt unverändert).
- Automatisches Mergen des Feature-PRs durch Claude: Daniels Freigabe bleibt Pflicht-Gate (`docs/ai-workflow.md`, Schritt 8).
