# 0037 - Status-Lebenszyklus mit Umsetzungsfortschritt (Ready/Todo/In Progress/Review/Done), PR-Merge-Erkennung statt nativer Board-Automatisierung

**Status:** Accepted
**Datum:** 2026-08-27
**Bezug:** GitHub-Issue [`#222`](https://github.com/TheRealKoller/photosort/issues/222) ("Status-Lebenszyklus: Umsetzungsfortschritt statt Proposed/Accepted"), `specs/features/0060-status-lebenszyklus-umsetzungsfortschritt.md` (neu, aus dieser ADR hervorgegangen), ADR [`decisions/0030-github-sync-natives-status-feld-inbox-einbindung.md`](./0030-github-sync-natives-status-feld-inbox-einbindung.md) (Abschnitte 1–3/6 bleiben für Feature-Specs gültig, unverändert durch diese ADR), ADR [`decisions/0036-github-issue-natives-story-refinement-inbox-entfaellt.md`](./0036-github-issue-natives-story-refinement-inbox-entfaellt.md) (Abschnitt 2 — der dortige 5-Werte-Status-Lebenszyklus — wird hiermit durch den neuen 6-Werte-Lebenszyklus ersetzt; alle übrigen Abschnitte von ADR 0036 bleiben unverändert gültig), `architect`-Konsultation für Story #222 am 2026-08-27.

**Nachtrag (2026-08-29):** Die in Abschnitt 5 beschriebene automatische PR-Merge-Erkennung bleibt unverändert im Code, ist seit ADR [`decisions/0042-pre-merge-finalisierung-statt-nachzieh-pr.md`](./0042-pre-merge-finalisierung-statt-nachzieh-pr.md) aber der **Ausnahmepfad** statt des Regelwegs: regulär wird eine Feature-Spec jetzt vor dem Merge im Feature-PR selbst finalisiert (`--only NNNN --finalize --pr-number NNN`), damit die Statuszeile nicht mehr über ein separates Nachzieh-PR nach `main` kommt. Alle übrigen Abschnitte dieser ADR bleiben unverändert gültig, diese ADR bleibt `Accepted`. Reiner Verweis, kein nachträgliches Editieren der ursprünglichen Entscheidung/Begründung unten.

## Kontext

Das native `Status`-Feld unterscheidet aktuell (ADR 0036, Abschnitt 2) `Unrefined → Story → Proposed/Accepted → Implemented`. Sobald eine Story als Feature-Spec akzeptiert ist, bleibt sie bis zur Fertigstellung ununterscheidbar auf `Accepted` stehen — Daniel sieht auf dem Board nicht, ob gerade aktiv daran gearbeitet wird, ein Pull Request offen ist, oder noch niemand angefangen hat.

Zwei technische Fakten bestimmen die Lösung, beide bereits aus ADR 0030/0036 bekannt:

1. `gh` (weiterhin kein `field-edit`) erzwingt für jede Options-Änderung des nativen `Status`-Felds denselben einmaligen, manuellen Migrationsschritt (Feld löschen, mit neuen Optionen neu anlegen) wie in ADR 0030 Abschnitt 3 / ADR 0036 Abschnitt 2.
2. Status/Priorität sind seit ADR 0017 Abschnitt 4 eine bewusste **Einbahnstraße**: das Board wird bei jedem Sync-Lauf deterministisch aus einer lokalen Quelle der Wahrheit neu berechnet und überschrieben, nie umgekehrt gelesen. Board-Drift wird nie still hingenommen (`_apply_fields`-Kommentar, ADR 0030 Begründung).

Neu an dieser Story: zum ersten Mal sollen Statuswerte (`In Progress`, `Review`) entstehen, die **nicht** aus einer lokalen Datei ableitbar sind — eine Spec-Datei kennt nur `Proposed`/`Accepted`/`Implemented`/`Superseded` (unverändert, `specs/README.md`), nie "gerade in Arbeit" oder "PR offen". Die bestehende Einbahnstraßen-Architektur muss deshalb um eine zusätzliche, GitHub-seitig gespeicherte **Laufzeit-Information** erweitert werden, ohne das Grundprinzip "das Board ist nie Source of Truth, wird nie zurückgelesen" zu brechen.

## Entscheidung

### 1. Sechs Board-Werte, `Ready` ersetzt `Story`, `Proposed` bleibt Datei-intern

```
STATUS_OPTIONS = ["Unrefined", "Ready", "Todo", "In Progress", "Review", "Done"]
```

`Ready` ist eine reine Umbenennung von `Story` (ADR 0036, Abschnitt 2) — inhaltlich unverändert (`story-refiner` setzt ihn). `Proposed` verschwindet als Board-Wert vollständig, bleibt aber unverändert Teil des **lokalen** Spec-Datei-Lebenszyklus (`specs/README.md`, `Proposed → Accepted → Implemented → Superseded` bleibt exakt so bestehen — diese ADR ändert nichts an `specs/README.md`). Der Board-Wert ist ab jetzt eine reine **Projektion**, keine 1:1-Kopie des Datei-Status mehr (siehe Abschnitt 2).

### 2. Board-Status wird aus Datei-Status **plus optionalem Laufzeit-Override** berechnet, nicht mehr 1:1 aus dem Datei-Status kopiert

Neue Baseline-Abbildung (ersetzt die bisherige "push exakt den Datei-Status"-Logik für Feature-Specs):

```python
_BOARD_STATUS_BASELINE = {"Proposed": "Todo", "Accepted": "Todo", "Implemented": "Done"}
_RUNTIME_OVERRIDE_STATUSES = {"In Progress", "Review"}
```

`Superseded` bleibt unverändert Sonderfall (Feld leeren + Label, ADR 0030 Abschnitt 2 — **nicht** Teil dieser Baseline-Tabelle, siehe Begründung).

Der `SyncStateEntry` (`specs/.github-sync-state.json`, `features`-Namensraum) bekommt zwei neue, optionale Felder: `runtime_status: str | None` (`"In Progress"` | `"Review"` | `None`) und `pr_number: int | None`. Der tatsächlich gepushte Board-Wert ist `runtime_status`, **falls gesetzt und die Baseline `"Todo"` ist** — sobald die Baseline `"Done"` wird (Datei-Status `Implemented`), gewinnt sie immer, ein `runtime_status` wird dabei defensiv geleert. Ein `runtime_status` ist damit strukturell nie mehr als eine Verfeinerung von `"Todo"`, nie ein eigenständiger, vom Datei-Status unabhängiger Zustand — die Einbahnstraße bleibt intakt: die lokale Spec-Datei bestimmt weiterhin abschließend, ob überhaupt "in Arbeit" sinnvoll ist (nur solange sie `Accepted` ist); GitHub liefert nur die zusätzliche, dort tatsächlich beobachtbare Verfeinerung *innerhalb* dieses einen Datei-Zustands.

Zentraler Änderungspunkt ist `_apply_fields()` in `sync.py` (bereits heute der einzige Ort, der Status+Priorität pusht, verwendet von `_sync_one()` **und** `_adopt_story_and_push_first_content()`) — beide Aufrufer profitieren automatisch von der neuen Baseline-Abbildung, ohne separate Änderung.

### 3. `In Progress`: Schreibpunkt beim Orchestrator, nicht bei `developer` selbst

`developer` hat laut eigener Definition (`.claude/agents/developer.md`) explizit **keinen** GitHub-Schreibzugriff (kein `gh`, kein Push, keine weitere Agent-Tool-Verschachtelung) — diese Grenze bleibt durch diese ADR unangetastet, sie wird nicht aufgeweicht für einen einzelnen, vermeintlich risikoarmen Statuswert. Stattdessen: **wer auch immer den `developer`-Subagenten per Agent-Tool startet** (Daniel direkt im Chat, oder ein künftiger Orchestrator-Skill), setzt unmittelbar davor

```bash
PYTHONPATH=scripts/github-project-sync/src python3 -m github_project_sync --only NNNN --runtime-status "In Progress"
```

Diese Anweisung wird direkt in `.claude/agents/developer.md`, Schritt 0, als an den Aufrufer gerichteter Hinweis verankert (nicht als etwas, das `developer` selbst tut) — der Aufrufer liest die Agenten-Beschreibung ohnehin vor dem Start (sichtbar z.B. in der Agent-Auswahl-Liste). Schlägt der Aufruf fehl (`{"error": ...}`), ist das **nicht blockierend**: die Implementierung startet trotzdem, der Fehler wird im späteren Abschlussbericht an Daniel vermerkt — ein kaputtes Board-Feld darf niemals die eigentliche Arbeit verhindern.

### 4. `Review`: Schreibpunkt in `ship-feature` Schritt 7, direkt nach `gh pr create`

`ship-feature` hat als Einziger im gesamten Ablauf echten GitHub-Schreibzugriff (Push, PR-Erstellung) — der natürliche, einzige sinnvolle Ort für diesen Touchpoint. Direkt nach erfolgreicher PR-Erstellung (`gh pr create`) in Schritt 7:

```bash
PYTHONPATH=scripts/github-project-sync/src python3 -m github_project_sync --only NNNN --runtime-status "Review" --pr-number <PR-Nummer>
```

Der mitgegebene `--pr-number` wird im State-Eintrag gespeichert und ist die Grundlage für die automatische `Done`-Erkennung (Abschnitt 5). Der bisherige Schritt 7.4 ("Spec-Status in `specs/features/` von `Accepted` auf `Implemented` setzen, direkt nach PR-Erstellung") **entfällt** — er war strukturell verfrüht (ein gerade erst eröffneter PR ist nicht "fertig") und wird durch die Merge-Erkennung in Abschnitt 5 ersetzt. Schritt 7.5 (Roadmap-Eintrag auf `Implemented`) entfällt aus demselben Grund an dieser Stelle, verschiebt sich ebenfalls (Abschnitt 5).

### 5. `Done`: automatische Erkennung beim nächsten Sync-Lauf, kein neuer manueller Befehl — explizit **kein** natives GitHub-Projects-Workflow

Beantwortet die im Issue explizit offen gelassene Frage (nativer Workflow vs. Code-Pfad) zugunsten des **expliziten Code-Pfads**, konsistent mit der in ADR 0017/0030 wiederholt getroffenen Grundsatzentscheidung, jede Board-Schreiblogik durch den getesteten `gh_adapter`/`sync.py`-Layer laufen zu lassen statt durch unkontrollierte, nicht über `FakeGhAdapter` testbare native GitHub-Automatisierung:

- Ein natives GitHub-Projects-Workflow ("Pull request merged" / "Item closed") wäre ein **zweiter, unkontrollierter Schreiber** auf dasselbe Feld — bricht die in ADR 0017 Abschnitt 4 etablierte Einbahnstraßen-Garantie (nur `sync.py` schreibt das Feld) und würde beim nächsten regulären Sync-Lauf zu Flip-Flopping führen (Board zeigt z.B. schon `Done`, `run_sync()` würde es ohne Kenntnis dieses Fremdschreibers wieder auf `Todo`/`In Progress` zurücksetzen, da die lokale Datei ja noch `Accepted` sagt).
- Zusätzlich technisch fraglich: das getrackte Project-Item ist das **Issue**, nicht der PR (`add_item_to_project(..., issue_url=...)`, unverändert) — "Pull request merged" als natives Workflow griffe für unsere Items gar nicht direkt, nur über den Umweg eines PR-seitigen "Closes #NNN" plus "Item closed"-Workflow, ein zusätzlicher, fragiler impliziter Mechanismus.

Stattdessen: **Merge-Erkennung als fester Bestandteil von `_sync_one()`**, aktiv für jeden Feature-Spec-Eintrag mit `stored_entry.runtime_status == "Review"` und gesetztem `pr_number` (also nur für die kleine, aktive Teilmenge an Specs mit offenem PR — kein unnötiger Overhead für die übrigen). Neue `gh_adapter`-Methode `get_pull_request(pr_number) -> PullRequestView(state, url)` (analog zu `get_issue()`, wrapped `gh pr view <NNN> --json state,url`). Zeigt der Zustand `"merged"`:

1. Die lokale Spec-Datei wird **von `sync.py` selbst** umgeschrieben — neue Funktion `spec_parser.set_status_line(text, new_status) -> str`, ersetzt nur das führende Schlüsselwort der `**Status:**`-Zeile (Header, nicht Inhalts-Zone, exakt wie das bereits bestehende Parsing dort trennt) mit `f"Implemented ([PR #{pr_number}]({pr_url}))"` — reproduziert exakt das bereits im Bestand etablierte Freitext-Muster (siehe z.B. `specs/features/0100...Implemented ([PR #101](...))`-Konvention in `specs/roadmap.md`).
2. `status` wird für den Rest dieses Funktionsdurchlaufs lokal auf `"Implemented"` gesetzt (alle nachgelagerte Logik — Hash, `_apply_fields`, `is_open` — behandelt die Spec danach wie jede regulär auf `Implemented` gesetzte Spec, keine Sonderpfade nötig).
3. `runtime_status`/`pr_number` werden im neuen State-Eintrag geleert.
4. `SpecSyncResult` bekommt ein neues, optionales Feld `finalized_from_pr: int | None` — signalisiert dem aufrufenden `github-project-sync`-Skill, dass gerade eine Merge-Erkennung stattgefunden hat.

Dieser Pfad greift bei **jedem** Sync-Lauf, der die betroffene Spec berührt (voller Lauf oder `--only NNNN`) — kein neuer, dedizierter `--mark-done`-Befehl nötig. Das ist bewusst konsistent mit dem bereits etablierten, rein pull-basierten Modell dieses Projekts (nichts läuft unaufgefordert/im Hintergrund — jeder Sync-Lauf ist weiterhin ausschließlich Daniel-/Claude-initiiert, `github-project-sync`-Skill).

**`specs/roadmap.md` wird bei einer erkannten Finalisierung nicht vom Python-Skript verändert** (das Skript liest `roadmap.md` nur, schreibt es nie — unverändertes Prinzip). Stattdessen dokumentiert `.claude/skills/github-project-sync/SKILL.md` neu: bei `finalized_from_pr != null` ruft der Skill `requirements-engineer` (Haiku) auf, der die Roadmap-Zeile von der "Offen"-Tabelle in "Bereits umgesetzt" verschiebt (bereits bestehende, an anderer Stelle im Projekt vermerkte Erwartung: physisches Verschieben statt reinem Status-Text-Update).

### 6. Story-Ebene: `Done` für ohne Umsetzung geschlossene Issues, keine Baseline-Rekonstruktion nötig

Anders als bei Feature-Specs gibt es für eine Story **keine** lokale Datei, aus der sich `Ready`/`Unrefined`/`Done` jederzeit neu herleiten ließe (ADR 0036, Kontext: "Story lebt ausschließlich im Issue"). Story-Status bleibt deshalb wie bisher ein **explizit gesetzter, nicht rekonstruierbarer** Wert (kein Baseline/Override-Modell wie bei Feature-Specs nötig). `sync_story()` wird um zwei Dinge erweitert:

- Die Statuswert-Validierung wird auf `{"Unrefined", "Ready", "Done"}` verengt (bisher fälschlich der volle, jetzt auch Feature-Board-Werte enthaltende `STATUS_OPTIONS`) — `Todo`/`In Progress`/`Review` ergeben für eine Story keinen Sinn.
- Wird `status="Done"` übergeben, schließt `sync_story()` zusätzlich das Issue (`gh.set_issue_state(issue_number, open=False)`) — bildet exakt den in Story #222 geforderten Fall "Issue ohne technische Umsetzung geschlossen" ab. `story-refiner`, Schritt 5 ("Devil's Advocate"), bekommt eine kurze Ergänzung: entscheidet sich Daniel dort für "verwerfen" statt "schärfen", ruft `story-refiner` `--only issue:<NNN> --status Done` auf, statt den bisher unbeschriebenen Fall offen zu lassen.

Der bereits produktive `superseded`-Label-Mechanismus für **Feature-Specs** (ADR 0030, Abschnitt 2 — Feld leeren + Label statt eines Statuswerts) bleibt davon bewusst unberührt und wird **nicht** durch `Done` ersetzt (siehe Begründung).

### 7. Migration: einmalig, manuell, kein Dauerbetrieb-Code — mit einer Story-spezifischen Ergänzung gegenüber ADR 0030/0036

Wie in ADR 0030 Abschnitt 3 / ADR 0036 Abschnitt 2:

1. Feld `Status` per `gh project field-delete` löschen, Code mit den sechs neuen Optionen deployen, `ensure_fields()` legt es frisch an.
2. Ein voller `github-project-sync`-Lauf (kein `--only`) — pusht für **jede** Feature-Spec automatisch die korrekte Baseline (`Todo`/`Done`) neu, exakt wie bei den vorherigen Migrationen (kein Datenverlust, da Board nie Source of Truth war).

**Neu gegenüber den Vorgänger-ADRs:** Schritt 2 stellt für Feature-Specs die Werte automatisch wieder her, für **offene Story-Issues nicht** — deren Statuswert ist (Abschnitt 6) nicht aus einer lokalen Datei rekonstruierbar, ein Feld-Löschen+Neuanlegen setzt sie faktisch auf leer zurück. Da es sich aktuell um eine kleine, bekannte Anzahl offener Stories handelt (laut `specs/roadmap.md` zum Zeitpunkt dieser ADR: Issues `#222`, `#224`), ist dafür **kein Automatismus** nötig oder verhältnismäßig — stattdessen ein manueller, einmaliger Nachzieh-Schritt: für jedes offene Story-Issue den Issue-Body inspizieren (enthält er bereits `## Ziel`/`## User Story`/`## Akzeptanzkriterien`, also von `story-refiner` verfeinert → `Ready`; enthält er nur `## Rohtext`, also frisch von `capture` → `Unrefined`) und den passenden Wert gezielt mit `--only issue:<NNN> --status <Ready|Unrefined>` zurücksetzen. Kein Code-Pfad, da die Menge betroffener Issues naturgemäß klein und zeitlich auf den Rollout-Moment begrenzt ist — identische Verhältnismäßigkeitsabwägung wie bei den bereits etablierten Migrationsschritten.

## Begründung

- **Baseline+Override statt eines dritten, komplett neuen Zustandsmodells:** löst das Grundproblem (Board-Werte, die keine lokale Entsprechung haben) mit der kleinstmöglichen Erweiterung des bereits bestehenden Modells — ein einziger neuer, optionaler State-Wert (`runtime_status`) statt eines parallelen, unabhängigen Tracking-Mechanismus. Die Einbahnstraßen-Garantie bleibt strukturell erhalten, weil ein Override nie unabhängig vom Datei-Status wirken kann (nur innerhalb der Baseline `"Todo"` sichtbar).
- **Kein natives GitHub-Projects-Workflow für `Done`:** siehe Abschnitt 5 — ein zweiter, unkontrollierter Schreiber widerspricht der in ADR 0017/0030 mehrfach bekräftigten Grundregel, dass ausschließlich der getestete `sync.py`/`gh_adapter`-Layer das Board schreibt. Diese Entscheidung war laut Story #222 explizit offengelassen — hiermit bewusst zugunsten von Konsistenz mit der bereits etablierten Architektur entschieden, nicht zugunsten der (auf den ersten Blick einfacheren) nativen Lösung.
- **Merge-Erkennung beim nächsten Sync-Lauf statt eines dedizierten `--mark-done`-Befehls:** vermeidet einen weiteren, manuell zu merkenden Zusatzschritt für Daniel/Claude nach jedem Merge — reiht sich stattdessen nahtlos in das bereits etablierte, rein Pull-/Recompute-basierte Sync-Modell ein (dieselbe Philosophie wie die bestehende `pulled`-Klassifikation, die auch erst beim nächsten Sync-Lauf verarbeitet wird, nicht in Echtzeit).
- **`In Progress` beim Aufrufer, nicht bei `developer` selbst:** hält die bewusst gezogene Grenze "kein GitHub-Schreibzugriff im Subagenten" konsequent ein, statt für einen einzelnen, vermeintlich harmlosen Schreibvorgang eine Ausnahme zu schaffen — Ausnahmen an dieser Stelle würden die gesamte in ADR 0024/0046 etablierte Architektur-Begründung (Subagent hat strukturell keinen GitHub-Zugriff) untergraben.
- **`Superseded` bleibt eigenständig, wird nicht durch `Done` ersetzt:** `Superseded` transportiert eine zusätzliche, für Daniel beim Board-Scannen wertvolle Information ("wurde durch etwas anderes ersetzt", nicht nur "ist fertig") — dieses Signal ginge verloren, würde man es in ein generisches `Done` auflösen. Für eine **Story**, die ohne Umsetzung verworfen wird, existiert dieses reichhaltigere Signal dagegen nicht (es gibt keine Nachfolge-Spec, auf die verwiesen werden könnte) — dort ist `Done` die einzig sinnvolle Wahl, kein Widerspruch zur unterschiedlichen Behandlung.
- **Story-Status-Migration manuell statt automatisiert:** eine Wiederherstellungslogik aus Issue-Body-Heuristiken (strukturierter Text vs. Rohtext) wäre Code für ein einmaliges, kleines, zeitlich begrenztes Problem (aktuell zwei betroffene Issues) — unverhältnismäßig gegenüber der Kosten eines manuellen Nachzieh-Schritts, identische Abwägung wie in ADR 0030 Abschnitt 3.

## Konsequenzen

- **`scripts/github-project-sync/src/github_project_sync/`:**
  - `gh_adapter.py`: `STATUS_OPTIONS = ["Unrefined", "Ready", "Todo", "In Progress", "Review", "Done"]`; neue Methode `get_pull_request(pr_number) -> PullRequestView(state, url)` im `GhAdapter`-Protokoll (+ `GhCliAdapter`, + `FakeGhAdapter` in `tests/fakes.py`).
  - `classify.py`: `SyncStateEntry` um `runtime_status: str | None = None`, `pr_number: int | None = None` erweitert.
  - `state.py`: `_parse_namespace`/`_serialize_namespace` lesen/schreiben die beiden neuen, optionalen Felder (rückwärtskompatibel: fehlen sie in einer alten Zustandsdatei, `None`).
  - `spec_parser.py`: neue Funktion `set_status_line(text, new_status) -> str` (Header-Zeilen-Ersetzung, analog zu `replace_content_zone`, aber für den Header statt die Inhalts-Zone).
  - `sync.py`: `_BOARD_STATUS_BASELINE`/`_RUNTIME_OVERRIDE_STATUSES`; `_apply_fields()` um `runtime_status`-Parameter erweitert; `_sync_one()` um die Merge-Erkennung (Abschnitt 5) ergänzt, inkl. neuem `SpecSyncResult.finalized_from_pr`; neue Funktion `set_feature_runtime_status()` (`--only NNNN --runtime-status ...`); `sync_story()` Statuswert-Validierung verengt + `Done` schließt das Issue.
  - `cli.py`: neue Flags `--runtime-status`, `--pr-number`.
- **`.claude/agents/developer.md`:** Schritt 0 bekommt den in Abschnitt 3 beschriebenen Hinweis an den Aufrufer (Statusfeld auf `In Progress` setzen, nicht-blockierend).
- **`.claude/skills/ship-feature/SKILL.md`:** Schritt 7 — neuer Teilschritt (Statusfeld auf `Review` + `--pr-number` direkt nach `gh pr create`), bisherige Teilschritte 7.4/7.5 (verfrühter `Implemented`-Bump) entfallen.
- **`.claude/skills/story-refiner/SKILL.md`:** Schritt 5 bekommt die kurze Ergänzung für den "verwerfen"-Fall (`--only issue:<NNN> --status Done`).
- **`.claude/skills/idea-sharpener/SKILL.md`:** Schritt 0 ("ist das Issue wirklich eine Story?") prüft ab jetzt gegen `"Ready"` statt `"Story"`.
- **`.claude/skills/github-project-sync/SKILL.md`:** dokumentiert `--runtime-status`/`--pr-number`, sowie den neuen Zusammenfassungs-Fall `finalized_from_pr` (Aufruf von `requirements-engineer` zum Verschieben der Roadmap-Zeile).
- **`docs/ai-workflow.md`:** muss aktualisiert werden (verweist heute noch auf `Story` statt `Ready`, kennt den neuen Umsetzungsfortschritt-Teil des Lebenszyklus noch nicht) — Umsetzung durch `developer`, nicht Teil dieser ADR.
- **Kein Effekt auf `docs/architecture.md`/`docs/setup.md`/Root-`README.md`** — reines Entwickler-/Prozess-Tooling ohne PhotoSort-System-/Datenmodell-Bezug, identische Einordnung wie ADR 0017/0030/0036.
- **`specs/README.md`:** unverändert — der lokale Spec-Datei-Lebenszyklus (`Proposed → Accepted → Implemented → Superseded`) bleibt exakt bestehen, nur die Board-Projektion wird granularer.
- **Rollout:** einmaliger, manueller Feld-Bereinigungsschritt (Abschnitt 7) plus einmaliger, manueller Story-Status-Nachzug für die zum Zeitpunkt des Rollouts offenen Story-Issues.
- **ADR 0036 bleibt `Accepted`** für alle Abschnitte außer dem hier abgelösten Abschnitt 2 (5-Werte-Statusliste); erhält einen kurzen Nachtrag-Verweis auf diese ADR. **ADR 0030 bleibt vollständig unverändert gültig** (Abschnitte 1–3/6, betreffen ausschließlich den `Superseded`-Mechanismus und das Feld-Grundprinzip, unberührt von dieser ADR).
- Ein späterer Wechsel dieses Modells (z.B. doch native Board-Automatisierung, oder ein feingranularerer Lebenszyklus) bleibt architekturrelevant und braucht eine neue, diese ADR als "Superseded" markierende ADR.
