---
name: github-project-sync
description: Einseitiger Push-Sync von den Feature-Specs unter `specs/features/*.md` (Status + technischer Inhalt) in ein gemeinsames GitHub Project (V2) — Status und Inhalt gehen immer von der Spec-Datei zum Board/Issue, ein Rückfluss aus dem Issue-Body in die Spec-Datei findet nicht statt (die Spec-Datei ist alleinige Quelle für den technischen Inhalt). Die Priorität wird nativ im Board gepflegt und vom Sync-Tool weder gelesen noch geschrieben. Zusätzlich der dateilose Story-Pfad (`--create-issue`, `--only issue:NNN`, `--show-status`, `--adopt-issue`) für Story-Issues ohne lokale Datei. Nutze diesen Skill, wenn Daniel danach fragt, mit GitHub zu syncen ("sync jetzt mit GitHub", "gleich das GitHub-Board ab", o.ä.), oder wenn `spec-writer` am Ende des Story→Spec-Übergangs automatisch `--adopt-issue` aufruft.
---

# GitHub Project Sync — mechanischer Push-Abgleich

Dünner Wrapper um das getestete, netzwerkfreie/-arme Python-Package `scripts/github-project-sync/`. Der Skill selbst trifft keine fachliche Anforderungsentscheidung — er orchestriert den Skript-Aufruf und fasst am Ende zusammen.

Seit Spec [`0059`](../../../specs/features/0059-story-lebenszyklus-github-issues.md) / ADR [`0036`](../../../specs/decisions/0036-github-issue-natives-story-refinement-inbox-entfaellt.md) gibt es zwei strukturell unterschiedliche Bereiche: den Feature-Spec-Sync (Status + Inhalt einseitig Spec→Board/Issue — die Priorität wird nativ im Board gepflegt und vom Tool nicht angefasst) sowie den dateilosen Story-Pfad (eine Story lebt nur im Issue, keine zweite lokale Kopie). Seit Spec [`0065`](../../../specs/features/0065-github-sync-content-pull-entfaellt.md) / ADR [`0041`](../../../specs/decisions/0041-feature-spec-content-sync-nur-noch-push.md) ist auch der Feature-Spec-Sync durchgängig einseitig - der frühere bidirektionale Content-Sync mit Hash-Konflikterkennung (`pulled`/`conflict`) entfällt vollständig.

## Feature-Spec-Sync (voller Lauf oder `--only NNNN`)

Aus dem Repo-Root heraus:

```bash
PYTHONPATH=scripts/github-project-sync/src python3 -m github_project_sync [--only NNNN] [--adopt-issue MMM]
```

`--only NNNN` (nackte Zahl) synct nur diese eine Feature-Spec. Ohne `--only` läuft ein voller Durchlauf über alle `specs/features/*.md`.

`--adopt-issue MMM` nur zusammen mit `--only NNNN` setzen, wenn die frisch angelegte Spec `NNNN` aus dem Story-Issue `MMM` hervorgegangen ist (siehe `.claude/skills/spec-writer/SKILL.md`, letzter Schritt) — adoptiert das bestehende Issue (kein neues Issue, kein Verlust von Historie/Labels), schreibt erstmals den Marker-Kommentar `<!-- photosort-spec: NNNN -->` plus den vollen Spec-Inhalt in den Issue-Body und setzt den Spec-Datei-Status auf `Accepted` (Board-Feld zeigt dafür die Baseline `Todo`, siehe unten).

Die Ausgabe ist ein einziges JSON-Objekt auf stdout: entweder `{"error": "..."}` oder `{"specs": [...], "orphaned": [...], "adopted": {...} | null}` (siehe `scripts/github-project-sync/src/github_project_sync/cli.py` für das genaue Format). Jeder Eintrag in `specs` hat seit Spec 0060 zusätzlich das Feld `finalized_from_pr` (siehe unten).

### Statusfeld-Baseline+Override (Spec 0060 / ADR 0037)

Das native Board-`Status`-Feld ist keine 1:1-Kopie des Spec-Datei-Status mehr, sondern eine Projektion: Datei-Status `Proposed`/`Accepted` → Baseline `Todo`, `Implemented` → Baseline `Done` (`Superseded` bleibt der bestehende Sonderfall — Feld leeren + Label). Ein optionaler Laufzeit-Override (`In Progress`/`Review`) verfeinert diese Baseline, wirkt aber nur, solange sie `Todo` ist — das setzt nicht dieser Skill selbst, sondern gezielt der `developer`-Aufrufer (`In Progress`, vor dem Start) bzw. `ship-feature` Schritt 7 (`Review` + `--pr-number`, direkt nach `gh pr create`):

```bash
PYTHONPATH=scripts/github-project-sync/src python3 -m github_project_sync --only NNNN --runtime-status "In Progress"
PYTHONPATH=scripts/github-project-sync/src python3 -m github_project_sync --only NNNN --runtime-status "Review" --pr-number <PR-Nummer>
```

`--runtime-status` erfordert `--only NNNN` (bare Feature-Scope, kein `issue:NNN`); `Review` erfordert zusätzlich `--pr-number`. Gibt `{"spec_number": NNNN, "runtime_status": ..., "pr_number": ...}` zurück (kein voller Content-Abgleich, nur das Status-Feld). Ein `{"error": "..."}` unverändert weitergeben.

### Fehler zuerst behandeln

Enthält die Ausgabe `"error"`:

- Verweist die Fehlermeldung auf `gh auth refresh -s project` (fehlender `project`-Scope der lokalen `gh`-Session): das **nicht** selbst versuchen zu beheben (erfordert i.d.R. interaktive Browser-Bestätigung) — Daniel den Befehl klar mitteilen und den Sync-Lauf abbrechen.
- Jeder andere Fehler (z.B. unbekannte `--only`-Spec-Nummer, `gh`-Aufruf fehlgeschlagen): die Meldung unverändert an Daniel weitergeben, keinen eigenen Lösungsversuch unternehmen, der über das Offensichtliche hinausgeht.

### Pro-Spec-Ergebnisse auswerten

Für jeden Eintrag in `specs` (Feld `classification`):

- **`created`/`pushed`/`unchanged`**: keine weitere Aktion nötig, nur für die Zusammenfassung vormerken.
- **`aborted_reason` ist nicht `null`** (Marker-Integritätsbruch): als eigene, deutlich hervorgehobene Warnung vormerken — braucht Daniels manuelle Prüfung des betroffenen Issues, keinen automatischen Fix.

Einträge in `orphaned` (Spec-Datei gelöscht, zugehöriges Issue automatisch geschlossen): für die Zusammenfassung vormerken, keine weitere Aktion nötig. Ist `adopted` nicht `null`, ebenfalls erwähnen (welches Story-Issue wurde zu welcher Spec adoptiert).

### `finalized_from_pr` — automatische PR-Merge-Erkennung (Spec 0060 / ADR 0037, Abschnitt 5)

Ist `finalized_from_pr` für einen Spec-Eintrag nicht `null` (die referenzierte PR wurde gemerged, `sync.py` hat die Spec-Datei bereits selbst auf `Implemented ([PR #NNN](url))` umgeschrieben und `Done` gepusht): keine weitere Aktion nötig — nur für die Zusammenfassung vormerken, welche Spec(s) auf diesem Weg finalisiert wurden.

## Dateiloser Story-Pfad

Diese drei Modi adressieren ein Story-Issue ausschließlich über seine Nummer (kein lokales File) und werden i.d.R. nicht direkt von Daniel angefragt, sondern von `capture`/`refinement`/`spec-writer` selbst aufgerufen — siehe dort für den jeweiligen Aufrufkontext:

- **`--create-issue --type idee|bug --title TITLE --body-file PATH`**: legt ein neues Story-Issue an (Status `Unrefined`). Gibt `{"issue_number": NNN}` zurück.
- **`--only issue:NNN [--status Ready|Unrefined|Done] [--body-file PATH]`**: aktualisiert optional Body/Status eines bestehenden Story-Issues. Gibt `{"issue_number": NNN, "status": ...}` zurück. Ohne `--status`/`--body-file` ein sauberer No-op ohne Board-Schreibzugriff. `--status Done` schließt das Issue zusätzlich nativ (ADR 0037, Abschnitt 6 — deckt sowohl eine tatsächlich umgesetzte als auch eine ohne Umsetzung verworfene Story ab, kein eigener Statuswert für den Unterschied).
- **`--only issue:NNN --show-status`** (rein lesend): liefert `{"status": "<aktueller Wert>"}`.

Ein `{"error": "..."}` bei einem dieser drei Modi unveraendert an den aufrufenden Skill/Daniel weitergeben, kein eigener Lösungsversuch.

## Zusammenfassung an Daniel

Fasse den Lauf knapp zusammen: Anzahl `created`/`pushed`/`unchanged`, jede Warnung (Marker-Integrität) einzeln benannt, automatisch geschlossene Issues aus `orphaned`, sowie — falls `adopted` nicht `null` war — welches Story-Issue zu welcher neuen Spec adoptiert wurde. Kein separater Report nötig — eine kompakte Chat-Antwort reicht.
