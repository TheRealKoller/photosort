# 0318 - Remote-Lebenszyklus: Grenze messen statt raten, und den Ablauf ehrlich machen

**Status:** Accepted
**Erstellt:** 2026-09-05
**Bezug:** GitHub-Issue [`#318`](https://github.com/TheRealKoller/photosort/issues/318), ADR [`0055`](../decisions/0055-remote-grenze-gemessene-board-faehigkeit-statt-session-erkennung.md), Vorgänger-Specs [`0309`](./0309-story-lebenszyklus-remote-sessions.md) / [`0314`](./0314-gh-bereitstellung-remote-sessions.md) / [`0317`](./0317-setup-script-fehlerregime.md), ADR [`0052`](../decisions/0052-remote-lebenszyklus-diagnose-kommando-und-echter-board-preflight.md) (Abschnitt 6 Punkt 1 abgelöst), ADR [`0043`](../decisions/0043-spec-nummer-gleich-issue-nummer-sync-tool-entfaellt.md), ADR [`0048`](../decisions/0048-board-operationen-zielzustands-idempotent.md), `scripts/gh-board.py`, `docs/setup.md`, `specs/architecture/0002-testkonzept.md`, `specs/architecture/0003-securitykonzept.md`

## Ziel

Nach Spec 0309, 0314 und 0317 sollten Remote-Sessions ein normaler Arbeitsmodus werden. Der erste `doctor`-Lauf, der dort überhaupt bis zu den Board-Prüfungen kommt, sagt etwas anderes: `verdict: "blocked"`, **alle acht** Lebenszyklus-Schritte blockiert. Der Ablauf warnt an keiner Stelle davor — wer dort eine Story beginnt, merkt es erst mittendrin und lässt sie halb fortgeschrieben zurück.

Der Befund trennt zwei Ursachen, die vorher als eine erschienen:

- **Echt und unumgehbar:** Die Session-Zwischenschicht bedient GraphQL nur für einen festen Satz von PR-Operationen (`HTTP 403: only the pinned set of PR-review operations is served`). Projects V2 spricht ausschließlich GraphQL — die vier Board-Schritte sind damit strukturell verloren, kein Transportwechsel hilft.
- **Vermutlich nur ein Umweg:** `repo_access` und `issue_read` scheitern an derselben Sperre, **weil `gh issue list --json` und `gh repo view --json` GraphQL sprechen** — nicht, weil Issues gesperrt wären. Dieselbe Meldung benennt REST (`gh api repos/{owner}/{repo}/…`) ausdrücklich als Weg, und `.claude/skills/ship-feature/SKILL.md` benutzt ihn für PR-Kommentare bereits erfolgreich. Ob er auch für die Issue-Schritte trägt, ist ungeprüft.

Damit ist die Prämisse widerlegt, mit der ADR 0052 Abschnitt 6 Punkt 1 den REST-Weg ausgeschlossen hat („die Frage ist Autorisierung, nicht Transport"). Hier ist es sehr wohl Transport. ADR 0055 löst diesen einen Punkt ab, **ohne** die Richtung zu wählen.

Ein Vorbehalt bleibt: Der Lauf meldet zusätzlich `The token in GH_TOKEN is invalid`. Weil `gh auth status` seine Prüfung über dieselbe gesperrte API führt, kann diese Meldung selbst ein Artefakt der Sperre sein — der Token muss nicht kaputt sein. Der 403 ist davon unabhängig belastbar (eine ungültige Anmeldung ergäbe `401 Bad credentials`, kein 403 mit Policy-Text), die Board-Prüfungen sind es nicht.

Diese Spec **stellt fest** und **macht den Ablauf ehrlich**. Sie wählt keine Richtung und baut keine Konsequenz.

## User Story

Als Daniel möchte ich vor und während einer Remote-Session wissen, welche Teile meines Entwicklungsablaufs dort tatsächlich tragen und welche nicht, damit ich nicht mitten in einer Story auf eine Wand laufe und die begonnene Arbeit in einem halb fortgeschriebenen Zustand zurücklassen muss.

## Akzeptanzkriterien

Fachlich wortgleich zum Issue-Body von [`#318`](https://github.com/TheRealKoller/photosort/issues/318); die Kriterien der Gruppe „Ablauf ehrlich machen" sind durch `test-engineer` auf Testbarkeit geschärft, AC 4 musste dabei geteilt werden (siehe „Entscheidungen").

### Feststellen (manuell, außerhalb des `developer`-Auftrags)

- [ ] Die gemeldete ungültige Anmeldung ist geklärt: entweder behoben, oder es ist festgehalten, dass sie sich nicht beheben lässt und dass sie ein Artefakt der Endpunkt-Sperre sein kann.
- [ ] Es ist geprüft und wörtlich am Issue dokumentiert, ob die Issue-Schritte über REST (`gh api repos/{owner}/{repo}/…`) erreichbar sind — mit der tatsächlichen Ausgabe, **Lesen und Schreiben getrennt gemessen**, nicht aus einer anderen Ausgabe abgeleitet.
- [ ] Für jeden der acht Lebenszyklus-Schritte (`idee-erfassen`, `issue-body-schreiben`, `status-ready`, `spec-anlegen`, `status-in-progress`, `pr-eroeffnen`, `status-review`, `abschluss-finalisieren`) steht fest, ob er remote trägt, und falls nicht, ob eine echte Sperre oder nur der gewählte Zugangsweg schuld ist.
- [ ] Am Issue ist festgehalten, dass die `doctor`-Zuordnungstabelle in dieser Umgebung **zu weit greift**: `repo_access`/`issue_read` sprechen GraphQL und blockieren dadurch auch `pr-eroeffnen` — ausgerechnet das, was die Zwischenschicht laut eigener Auskunft bedient. Befund, keine Reparatur in dieser Spec.
- [ ] Der korrigierte Befund ersetzt die ursprüngliche Annahme des Issues, die Issue- und PR-Schritte blieben unbeeinträchtigt.

### Ablauf ehrlich machen (Code)

- [ ] `python3 scripts/gh-board.py capabilities` liefert ohne Argumente ein JSON-Objekt mit genau den Feldern `board_reachable`, `blocked_lifecycle_steps`, `detail`, `note` und Exit-Code 0 — auch wenn das Board unerreichbar ist oder `gh` fehlt. Scheitert die Board-Auflösung, nennt `blocked_lifecycle_steps` genau die vier Board-Schritte aus `BOARD_LIFECYCLE_STEPS`; gelingt sie, ist die Liste leer.
- [ ] Die vier Ablauf-Skills (`capture`, `refinement`, `spec-writer`, `ship-feature`) werten das Ergebnis vor ihrem ersten Board-Aufruf aus und versuchen einen so gemeldeten Schritt nicht.
- [ ] Trifft ein Ablauf auf einen gemeldeten Schritt, führt er alle übrigen Schritte aus und **bricht nicht ab**. Sein Abschlussbericht trägt den wörtlichen Abschnitt `## Lokal nachzuholen` mit je einem kopierbaren `python3 scripts/gh-board.py …`-Befehl samt Issue-/Spec-Nummer je ausgelassenem Schritt. Kein Schritt wird stillschweigend ausgelassen. Es entsteht **keine** Zustandsdatei.
- [ ] `abschluss-finalisieren` gilt nur in seinem Board-Anteil als blockiert; Spec-Statuszeile und Issue-Abschluss werden weiterhin versucht.
- [ ] `board_reachable: true` erzeugt nie einen Eintrag in `blocked_lifecycle_steps` und wird nirgends als Beleg für Schreibbarkeit geführt; `note` sagt das ausdrücklich und steht in **beiden** Fällen im Bericht.
- [ ] `capabilities` setzt keinen schreibenden `gh`-Aufruf ab und keinen Aufruf außer `gh project list` sowie — nur im Fehlerfall — dem bestehenden Deutungsaufruf `gh auth status`. Nachweis über die protokollierten Argumentlisten.
- [ ] **(4a)** Jede Warnung hängt ausschließlich am Messergebnis, an keinem Umgebungsmerkmal und an keinem eingetragenen Satz. Nachweis: Bei identischem `gh`-Verhalten liefert `capabilities` dasselbe Ergebnis, unabhängig von gesetzten Umgebungsvariablen (`GH_TOKEN`, `CODESPACES`, `GITHUB_ACTIONS`). Es entsteht keine Codestelle, die aus einem Umgebungsmerkmal auf eine Session-Art schließt.
- [ ] **(4b, Review-Kriterium)** Der Abschnitt „Remote-/Cloud-Umgebungen" in `docs/setup.md` benennt beide Sensoren wörtlich — `doctor` meldet `project_visible` als erfolgreich und führt die vier Board-Schritte nicht mehr auf; `capabilities` meldet `board_reachable: true` — und sagt, dass der Absatz dann nachzuziehen ist.

### Entscheidung vorbereiten, nicht treffen

- [ ] Die Entscheidungsvorlage liegt in ADR 0055 Abschnitt 7 vor und benennt jede in Frage kommende Richtung mit Tragweite und Preis, einschließlich der beiden erst durch den Befund sichtbaren Punkte (Board-Schritte anders gelagert als Issue-Schritte; die bisherige Begründung gegen den Alternativweg beruht auf einer widerlegten Annahme).
- [ ] Für jede Richtung ist benannt, welche bestehenden Festlegungen sie berührt und ob sie eine ablösen müsste.
- [ ] Die Vorlage nennt ausdrücklich, was **gegen** die jeweilige Richtung spricht.
- [ ] Die Richtungsentscheidung selbst wird nicht getroffen und keine Konsequenz umgesetzt.

## Datenmodell-Bezug

Nicht relevant. Die Spec berührt ausschließlich Entwickler-Werkzeug (`scripts/gh-board.py`), Skill-Dateien und Dokumentation — keine Anwendungsentität, weder Projekte, Fotos, Kategorien noch Klassifizierungsläufe. Keine Änderung an [`docs/architecture.md`](../../docs/architecture.md) nötig; gleiche Einordnung wie ADR 0017/0037/0043/0046/0052/0053.

## Architektur / Umsetzung

Grundlage ist ADR [`0055`](../decisions/0055-remote-grenze-gemessene-board-faehigkeit-statt-session-erkennung.md). Die Story hat drei Teile unterschiedlicher Natur, und die Trennung bestimmt den Zuschnitt:

- **Feststellen** — einmalige Messungen in einer echten Remote-Session, Ausgabe wörtlich ans Issue. **Kein Code.**
- **Ablauf ehrlich machen** — ein rein lesendes Subkommando plus ein einheitliches Reaktionsmuster in den Skills. **Der einzige Code-Anteil.**
- **Entscheidung vorbereiten** — die Vorlage lebt in ADR 0055 Abschnitt 7. **Keine Richtungswahl, keine Konsequenz.**

### Der tragende Entwurf: Fähigkeit messen statt Session erkennen

Die Story sagt „der Ablauf erkennt eine Remote-Session". Umgesetzt wird die **Wirkung**, nicht der Wortlaut (bewusste Abweichung, siehe „Entscheidungen"). Jedes Merkmal für „das ist remote" — Umgebungsvariable, Hostname, Auth-Quelle `GH_TOKEN`, fehlender Keyring — wäre ein Urteil aus Fremdtext über eine fremde Umgebung **vor** dem ersten Versuch, also genau die Fehlerklasse, die ADR 0052 abgeschafft hat. Lokaler Token-Auth, CI-Lauf und Remote-Session sind daran nicht unterscheidbar, und beim Wegfall der Sperre würde weitergewarnt, bis jemand es von Hand zurücknimmt.

Gemessen wird stattdessen die eine zwingend auswertbare Tatsache: **Lässt sich das Board auflösen?** Der Aufruf dafür (`gh project list --owner …`) ist derselbe, den jeder schreibende Board-Pfad ohnehin zuerst absetzt. Ausgewertet wird **nur die zwingende Richtung**:

- Auflösung scheitert ⇒ **jeder** Board-Schreibvorgang scheitert sicher (er muss durch dieselbe Auflösung).
- Auflösung gelingt ⇒ **nichts bewiesen**; der Ablauf verhält sich unverändert und versucht es.

Die Messung ist damit einseitig: Sie kann Schritte als sicher blockiert melden, nie einen Schritt freigeben. Das erfüllt „Lesen ist kein Beleg für Schreiben" strukturell statt per Disziplin.

**Kein wiederauferstandener Preflight:** Er urteilt nicht aus Text, sondern aus einem abgesetzten Aufruf; er verhindert keinen Befehl (kein Board-Befehl fragt ihn); er kann nur blockiert-melden, nie freigeben. Der abgeschaffte Preflight hatte alle drei Eigenschaften umgekehrt.

### Aufteilung der Zuständigkeit

- **`scripts/gh-board.py` misst und ordnet zu** — einzige Board-Stelle (ADR 0043), besitzt die Lebenszyklus-Schritte bereits als Datenbestand, ohne Netzwerk testbar.
- **Die Skills entscheiden, was folgt** — nur sie kennen ihren Ablauf, das bereits Erledigte und ihr Berichtsformat.

Neues Subkommando, ohne Argumente, rein lesend:

```
python3 scripts/gh-board.py capabilities
→ {"board_reachable": false,
   "blocked_lifecycle_steps": ["status-ready","status-in-progress","status-review","abschluss-finalisieren"],
   "detail": "<redigierte gh-Meldung samt Deutung>",
   "note": "Ein erreichbares Board ist kein Beleg fuer Schreibzugriff. Nicht genannte Schritte
            sind damit nicht als tragfaehig erwiesen."}
```

Verbindliche Entwurfsentscheidungen:

1. **Genau ein Board-Aufruf** über die bestehende `GhBoard.project()`-Auflösung samt `_explain_project_failure`; **im Fehlerfall zusätzlich der eine bestehende, rein lesende `gh auth status`**, den `_explain_project_failure()` über `auth_info()` ohnehin absetzt. Ein Aufruf im Erfolgsfall und beim umbenannten Board, zwei im Fehlerfall — testgesichert als **exakte** Aufrufliste, nicht als Obergrenze. Unter zwei Sekunden pro Ablauf statt neun Aufrufen wie bei `doctor`; das ist die Bedingung dafür, dass es überhaupt vor jedem Ablauf stehen darf.
2. **Rein lesend**, testgesichert an den protokollierten Argumentlisten (wie `doctor`).
3. **Exit-Code 0, sobald ein Ergebnis entsteht** — die **zweite** dokumentierte Ausnahme von der `{"error": …}`/Exit-1-Konvention. Der Modul-Docstring („einzige Ausnahme `doctor`") wird auf zwei benannte Ausnahmen korrigiert.
4. **Blockierte Schritte aus `BOARD_LIFECYCLE_STEPS` abgeleitet**, nicht daneben aufgezählt. Abgesichert per **Monkeypatch der Quellkonstante**, nicht bloß per Konstantenvergleich (siehe Teststrategie).
5. **Redaktion/Sanitisierung/Kürzung** über dieselbe `redact_for_report`-Funktion — **auf den zusammengesetzten Endtext**, nicht nur auf `str(error)`: `_explain_project_failure()` redigiert die Ursprungsmeldung und hängt den Deutungstext danach an, sodass die 500-Zeichen-Kürzung sonst faktisch nicht gilt.
6. **Kein Torwächter** — kein Board-Befehl ruft `capabilities`, keiner wird dadurch verhindert.
7. **`doctor` bleibt unverändert.** Keine REST-Prüfung (entschiede die offene Richtung), keine Schreibprobe (verletzt ADR 0052 Abschnitt 5), keine 403-Deutung (macht aus Daten wieder ein Urteil).

**Warum nicht einfach `doctor` aufrufen:** `doctor` ist das Beweismittel (neun Prüfungen, Bericht für ein öffentliches Issue, eigene Redaktionsauflagen), `capabilities` ist ein Betriebssignal vor jedem Ablauf. Verschiedene Rollen, Kosten und Änderungsrisiken — würde `doctor` die Steuerung mit übernehmen, wäre jede spätere Diagnoseänderung eine Verhaltensänderung des Workflows. Ein Umfangs-Schalter an `doctor` scheidet zusätzlich aus (ADR 0052 Abschnitt 5: nimmt keine Argumente entgegen).

**Bewusst hingenommene Ungenauigkeit:** In derselben kaputten Umgebung meldet `doctor` acht blockierte Schritte, `capabilities` vier. Beide sind richtig — verschiedene Fragen (Diagnose über alle Prüfungen vs. einseitige Board-Messung). Der Unterschied lässt sich nicht wegtesten und gehört deshalb in `note`, in den Hilfetext des Subparsers und ins Testkonzept.

### Muster „Board nicht erreichbar" — nachvollziehbarer Zustand ohne Zustandsdatei

Keine neue Zustandsdatei (ADR 0043 hat sie abgeschafft), und es braucht auch keine: Board-Operationen sind zielzustands-idempotent (ADR 0048), das Nachzuholende ist aus Issue-/Spec-Nummer und Ablaufstelle **ableitbar** statt erinnerungspflichtig. Verbindlich ist ein Ausgabeverhalten:

1. Ausführen, was geht — **nicht abbrechen**.
2. Den blockierten Schritt **nicht versuchen** (als aussichtslos gemessen).
3. Ihn **ausdrücklich als ausgelassen melden**, nie stillschweigend, im festen Abschnitt `## Lokal nachzuholen` des Abschlussberichts, mit wörtlich kopierbarem Befehl.
4. Dieselbe Liste in das **ohnehin geschriebene dauerhafte Artefakt** (Issue-Kommentar bzw. `## Lokal nachzuholen` im PR-Body) — **sofern dieser Kanal in dieser Umgebung trägt**; sonst nur in den Chat-Bericht, mit dem ausdrücklichen Hinweis, dass er der einzige Träger ist.

Punkt 4 ist bedingt formuliert, weil offen ist, ob Issue-Schreibvorgänge remote tragen. Das Muster steht **einmal vollständig** in `.claude/skills/github-board/SKILL.md`; die vier aufrufenden Skills verweisen darauf, statt es zu wiederholen.

### Betroffene Dateien

| Datei | Änderung |
|---|---|
| `scripts/gh-board.py` | einzige Code-Datei: Subkommando `capabilities` (`cmd_capabilities()`, Subparser ohne Argumente, `_dispatch`-Zweig), Docstring-Korrektur zur zweiten Exit-0-Ausnahme. **`doctor` unverändert** |
| `scripts/tests/test_gh_board.py` | Pflicht-Tests entlang der bestehenden `FakeGh`-Technik (siehe Teststrategie) |
| `.claude/skills/github-board/SKILL.md` | `capabilities` in der Befehlstabelle; neuer Abschnitt mit dem Muster „Board nicht erreichbar" (einmal vollständig); Trennung von automatischem und manuellem Pfad beim Lese-Muss-Schritt |
| `.claude/skills/capture/SKILL.md` | vor dem ersten Board-Aufruf `capabilities` auswerten, im Blockierungsfall dem Muster folgen; `## Lokal nachzuholen` im Bericht |
| `.claude/skills/refinement/SKILL.md` | dito (betrifft `set-body`/`set-priority`/`set-status Ready` und den Verwerfen-Pfad `set-status Done`) |
| `.claude/skills/spec-writer/SKILL.md` | dito (betrifft `show-status` und `set-status Todo`) |
| `.claude/skills/ship-feature/SKILL.md` | dito (betrifft `set-status In Progress`/`Review` und `finalize`) |
| `docs/setup.md` | Unterabschnitt „Remote-/Cloud-Umgebungen": die Grenze, warum Board- und Issue-Schritte verschieden gelagert sind, das Ablaufverhalten, und die Sensoren für das Überholtsein |
| `docs/ai-workflow.md` | kurzer Zusatz bei „Zwei Arbeitsmodi" mit Verweis auf `docs/setup.md`; **kein** Umbau der Schritt-Tabelle |
| `specs/architecture/0002-testkonzept.md` | neue Sektion „Erweiterung für ADR 0055" (vier Regeln, siehe Teststrategie) plus Eintrag unter „Bekannte Lücken" |
| `specs/architecture/0003-securitykonzept.md` | drei Ergänzungen (siehe Security) |
| `specs/decisions/0055-…md` | die zugehörige ADR (liegt bereits vor) |
| `specs/decisions/0052-…md` | reiner Verweis-Nachtrag in der Kopfzeile; Entscheidung/Begründung unberührt, bleibt `Accepted` |

**Ausdrücklich unverändert:** `.claude/agents/developer.md` (sein Board-Schritt ist ein Hinweis an den Aufrufer, und der ist über die Skills gebunden), `docs/architecture.md`, Root-`README.md`, `.env.example`, `.github/workflows/`, Board-Felder.

### Umsetzungsreihenfolge

1. **`capabilities` im Script, testgetrieben** (rot → grün je Verhalten): Berichtsvertrag, Erfolgs- und Fehlerfall, Exit-0 in beiden, kein schreibender Aufruf, exakte Aufrufliste je Fall, Ableitung aus `BOARD_LIFECYCLE_STEPS`, Redaktion und Kürzung, fehlendes Binary als Befund. Zuerst, weil alles Weitere auf der Ausgabeform aufsetzt.
2. **CLI-Anbindung** (Subparser, `_dispatch`, Erweiterung der bestehenden CLI-Parametrisierung um `capabilities`) und Docstring-Korrektur.
3. **`.claude/skills/github-board/SKILL.md`** — Befehlstabelle und das Muster „Board nicht erreichbar" an einer Stelle vollständig. Vor den vier aufrufenden Skills, damit diese nur noch verweisen.
4. **Die vier aufrufenden Skills** (`capture`, `refinement`, `spec-writer`, `ship-feature`) — je der Verweis plus `## Lokal nachzuholen` im Abschlussbericht.
5. **`docs/setup.md`**, der Zusatz in **`docs/ai-workflow.md`**, sowie Test- und Securitykonzept. Was zu diesem Zeitpunkt belegt ist, wird als belegt geschrieben; die noch offene Frage nach den Issue-Schritten wird ausdrücklich als offen benannt statt vermutet.
6. **Manueller Schritt außerhalb des `developer`-Auftrags** (Daniel/Orchestrator, nach PR-Eröffnung und vor dem Merge, wie in Spec 0309/ADR 0053): in einer echten Remote-Session die Anmeldung klären, den REST-Weg für die Issue-Schritte messen (Lesen und Schreiben **getrennt**, gegen Issue #318 selbst statt gegen ein Wegwerf-Issue), je Lebenszyklus-Schritt festhalten, ob er trägt und ob eine echte Sperre oder nur der Zugangsweg schuld ist. Ausgabe wörtlich an #318 unter den Auflagen aus Security-Kriterium 11. Danach ggf. **Nachzug der offenen Stelle in `docs/setup.md` im selben PR**.

### Teststrategie

Alles auf Unit-Ebene gegen das injizierte `run`-Callable — kein echtes `gh`, kein Netzwerk. Das 80%-Coverage-Gate gilt hier **nicht** (`demo-scripts` fährt `ruff check .` + `pytest` über `scripts/` ohne `--cov`); Maßstab ist die folgende Pflicht-Liste, wie schon bei `doctor`.

| Ebene | Gegenstand |
|---|---|
| Unit (`scripts/tests/test_gh_board.py`) | `cmd_capabilities` — Berichtsform, Ableitung, Aufrufliste, Redaktion, Fehlerformen |
| Unit-CLI (`main()`/`build_parser()`) | Exit-Code-Konvention, Argumentlosigkeit, genau ein JSON-Objekt auf stdout |
| Statischer Kopplungstest (liest `.claude/skills/**/SKILL.md`) | Befehlstabelle ↔ Subparser; die vier Ablauf-Skills nennen `capabilities` und `## Lokal nachzuholen` |
| Manuell, außerhalb CI | Der eine echte Remote-Lauf (Umsetzungsschritt 6) — Ausgabe wörtlich ans Issue, kein Test |
| Bewusst nicht | Skill-Verhalten zur Laufzeit (LLM-interpretiert), echtes `gh`, Netzwerk, Integrationstest |

**Pflicht-Tests** (benannt, damit im Review abhakbar):

*Berichtsvertrag* — (1) Struktur in **beiden** Fällen exakt `{board_reachable, blocked_lifecycle_steps, detail, note}`, `board_reachable` ist `bool`, Liste ist `list[str]`, **kein** `error`-Schlüssel (ein Skill, der auf `"error" in payload` prüft, darf hier nie anschlagen); (2) erreichbares Board → `True`/`[]` (leere Liste, nicht `null`); (3) unerreichbares Board → `False`/`== list(BOARD_LIFECYCLE_STEPS)`.

*Ableitung und Drift* — (4) **Monkeypatch von `BOARD_LIFECYCLE_STEPS` auf einen Sentinel-Wert**, Ergebnis muss den Sentinel nennen; (5) Konstantenvergleich gegen `PROBE_LIFECYCLE_STEPS["project_visible"]`; (6) Verhaltensvergleich: dieselbe `FakeGh` durch `cmd_doctor` und `cmd_capabilities`, `set(capabilities) ⊆ set(doctor)` **und** `set(PROBE_LIFECYCLE_STEPS["project_visible"]) ⊆ set(capabilities)`; (7) parametrisiert über `set(LIFECYCLE_STEPS) - set(BOARD_LIFECYCLE_STEPS)` — insbesondere darf `idee-erfassen` nie auftauchen, sonst ließe `capture` den einen Schritt aus, der nachweislich geht.

*Einseitigkeit* — (8) Fake, in dem `gh project list` gelingt, aber `project item-edit`/`issue edit` scheitern: `board_reachable` bleibt `True`, `blocked` bleibt `[]`. Das ist der ausführbare Wächter dagegen, dass das Kommando später zum Orakel ausgebaut wird; (9) `note` steht in **beiden** Fällen im Bericht.

*Aufrufe* — (10) **exakte** Aufrufliste: Erfolgsfall genau `[["gh","project","list","--owner",OWNER,"--format","json"]]`, Fehlerfall exakt diese plus `["gh","auth","status"]`; (11) kein schreibender `gh`-Aufruf, parametrisiert erreichbar/unerreichbar gegen die bestehende Konstante `SCHREIBENDE_GH_AUFRUFE`.

*Exit-Code und CLI* — (12) Exit 0 auch bei unerreichbarem Board, über `main(["capabilities"], …)`, stdout genau **ein** JSON-Objekt; (13) fehlendes `gh`-Binary → Befund statt Traceback; (14) `capabilities` fängt nur `BoardError` — ein `RuntimeError` aus `run` muss durchschlagen, damit ein Programmierfehler nicht als „Board nicht erreichbar" erscheint; (15) nimmt keine Argumente entgegen; (16) **Totalitätstest** über alle CLI-Aufrufformen in einer kaputten Umgebung: Exit 0 nur für `doctor` und `capabilities`, Exit 1 für alle übrigen — der belastbare Ersatz für einen Docstring-Grep.

*Redaktion* — (17) tokenhaltiges `stderr`, Assertion über die **gesamte** Serialisierung, plus Gegenprobe, dass der Befundtext erhalten bleibt; (18) 5000-Zeichen-`stderr` → `len(detail) < 600` (fällt ohne die äußere `redact_for_report`-Anwendung); (19) unerwartete Antwortform (Nicht-JSON, JSON falscher Struktur) → Bericht statt Traceback.

*Abgrenzung der Ursachen* — (20) umbenanntes Board (`projects=[]`): `board_reachable False`, **genau ein** `gh`-Aufruf (die Deutung greift hier nicht), `detail` nennt den Board-Titel und enthält **kein** „Scope"/„auth refresh". Sonst liest ein Skill „Umgebung gesperrt", wo das Board nur umbenannt wurde.

*Doku-Kopplung* — (21) `capture`, `refinement`, `spec-writer`, `ship-feature`: jede `SKILL.md` enthält wörtlich `gh-board.py capabilities` **und** `## Lokal nachzuholen`. Einzige automatische Absicherung, die die Skill-Seite überhaupt bekommt.

**Zusätzliche Edge Cases:** Umgebungs-Unabhängigkeit (identische `FakeGh` mit und ohne gesetzte `GH_TOKEN`/`CODESPACES`/`GITHUB_ACTIONS` → identisches Ergebnis; Wächter gegen später eingeschmuggelte Merkmalserkennung, trägt AC 4a); `stderr` mit ANSI-/Bidi-/Nullbreiten-Zeichen und anweisungsförmigem Text landet als JSON-String mit entfernten Steuerzeichen. **Bewusst nicht getestet:** `PermissionError`/`OSError` aus `run` (nur `FileNotFoundError` wird gefangen — vorbestehende Eigenschaft aller Befehle), parallele Läufe, echte Laufzeit.

**Bestehende Tests — erweitern, nicht löschen:** `test_cli_kennt_alle_in_den_skills_dokumentierten_befehle` um `capabilities` (Empfehlung: Liste als Modulkonstante herausziehen, damit Pflicht-Test 16 dieselbe Quelle nutzt); `test_die_cli_kennt_genau_die_in_der_skill_tabelle_dokumentierten_befehle` wird **rot**, bis die Tabellenzeile in `github-board/SKILL.md` steht — nicht anpassen, sondern die Doku nachziehen (so ist er gedacht); `test_die_zuordnungstabelle_deckt_jeden_lebenszyklus_schritt_ab` bleibt unverändert gültig, Pflicht-Test 7 ist sein Gegenstück für die Board-Teilmenge, kein Ersatz. `SCHREIBENDE_GH_AUFRUFE`, `_board`, `_gesunder_fake`, `TOKEN_BEISPIELE` wiederverwenden; ein `_capabilities`-Helfer analog `_doctor` genügt. **Kein bestehender Test wird gelöscht oder umgehängt** — `doctor` bleibt unverändert, also verliert keine Zusicherung ihren Träger.

**Testkonzept-Ergänzung** (`specs/architecture/0002-testkonzept.md`, neue Sektion „Erweiterung für ADR 0055" nach der ADR-0053-Sektion), vier Regeln über diese Story hinaus: (1) Eine einseitig gültige Aussage braucht einen Test für die Richtung, in der sie *nichts* sagt — der Erfolgsfall-Test ist der wertvollere; (2) „abgeleitet, nicht aufgezählt" wird per Monkeypatch der Quellkonstante geprüft, nicht per Gleichheit zweier Konstanten (das ist Buchhaltung, kein Verhaltensnachweis); (3) die Exit-Code-Konvention wird ab jetzt als **Totalität** geprüft statt jede Ausnahme einzeln zu bezeugen; (4) die verschieden großen Schrittmengen von `doctor` und `capabilities` sind festgehalten, damit sie nicht später als Regression neu „entdeckt" werden. Unter „Bekannte Lücken": Das Skill-Verhalten (`## Lokal nachzuholen`) ist LLM-interpretiert und nur statisch verankert (Pflicht-Test 21) — die tatsächliche Befolgung bleibt Review-Gegenstand.

## UI/UX

Nicht relevant. Die Spec berührt ausschließlich Entwickler-Werkzeug (ein CLI-Subkommando, Skill-Dateien, Dokumentation) und hat an keiner Stelle eine sichtbare Oberfläche — kein Pfad unter `frontend/`, keine dargestellten Daten, keine berührte Komponente.

## Security

Sicherheitsrelevant (kein Blocker) — **unter der Bedingung von Muss-Kriterium 1**. Ohne dieses Kriterium wäre es ein Blocker: Ein Ablauf, der redigierten Fremdtext ohne Menschen dazwischen in den PR-Body eines öffentlichen Repositories schreibt, hebelt Muss-Kriterium 10 aus Spec 0309 tatsächlich aus.

Kein Anwendungscode, keine Foto-/Projektdaten, kein neues Secret, keine geänderte Authentifizierung. Führendes Schutzziel ist wie bei Spec [`0309`](./0309-story-lebenszyklus-remote-sessions.md) **Vertraulichkeit** — das Repository ist öffentlich, ein Fehlgriff nicht zurücknehmbar (Edit-Historie, Mail-Benachrichtigungen). Neu daneben tritt die **Integrität des Ablaufs**: `capabilities` ist das erste Ausgabeartefakt, das nicht nur weitergereicht wird, sondern steuert, welche Schritte ein Agent mit GitHub-Schreibzugriff auslässt. Ausführliche Einordnung: `specs/architecture/0003-securitykonzept.md`.

Die zehn Muss-Kriterien aus Spec 0309 gelten unverändert weiter, soweit `capabilities` dieselben Stellen benutzt (`redact_for_report`, `_explain_project_failure`, `auth_info`-Whitelist). Neu hinzu kommen 1–4, 9 und 11; Kriterium 10 wird **nicht gelockert**, sondern in seiner Reichweite präzisiert.

**Muss-Kriterien (testgetrieben umzusetzen, im Review abhakbar):**

1. **Kein Fremdtext im automatisch geschriebenen öffentlichen Artefakt.** Der Abschnitt `## Lokal nachzuholen` in PR-Body bzw. Issue-Kommentar enthält ausschließlich selbst erzeugten Inhalt aus geschlossenen Quellen: Schrittnamen aus `BOARD_LIFECYCLE_STEPS`, die daraus gebildeten Nachhol-Befehle und einen festen, im Skill-Text stehenden Begründungssatz. `detail` und jede andere `gh`-Ausgabe gelangen dort **nicht** hinein — sie bleiben dem Chat-Abschlussbericht vorbehalten, den ein Mensch liest. Damit gibt es auf dem automatischen Pfad keinen Fremdtext, für den „vor dem Einfügen lesen" nötig wäre.
2. **Ablaufsteuerung ausschließlich aus geschlossenen Werten.** Was ein Ablauf auslässt, entscheidet sich allein an `board_reachable` (Boolean) und `blocked_lifecycle_steps` (im Script aus `BOARD_LIFECYCLE_STEPS` abgeleitet, nie aus einer `gh`-Ausgabe geparst). `detail` und `note` sind reine Anzeigefelder: nie gematcht, nie geparst, nie Bedingung. Test: `gh`-stderr mit anweisungsförmigem Text, JSON-Fragmenten, Anführungszeichen, Zeilenumbrüchen und Steuerzeichen verändert weder die JSON-Struktur noch die gemeldete Schrittmenge.
3. **Unbrauchbares Messergebnis heißt „nicht gemessen", nicht „blockiert".** Läuft `capabilities` nicht (fehlendes Binary, Exit ≠ 0, fehlendes/ungültiges JSON, unbekannter Schrittname), verhält sich der Ablauf wie heute und **versucht** den Schritt. Nur ein wohlgeformtes `board_reachable: false` darf einen Schritt auslassen. Ohne diese Richtung könnte Umgebungsrauschen einen Agenten dazu bringen, Board-Schritte stillschweigend zu überspringen — die einseitige Auswertung ist damit zugleich die sichere Voreinstellung.
4. **Der Erfolgsfall gibt nichts aus der `gh`-Antwort weiter.** `gh project list --owner …` liefert **alle** Projekte des Owners samt Titeln, IDs und Nummern. `capabilities` gibt im Erfolgsfall ausschließlich `board_reachable: true`, eine leere Schrittliste und die feste `note` aus — keinen Titel, keine ID, keine Nummer, keinen Zähler. Test mit einer Antwort, die ein zweites Projekt mit auffälligem Titel enthält: Der Titel steht in keinem Feld der Ausgabe. (Übertragung von Kriterium 6 aus Spec 0309.)
5. **Redaktion, Sanitisierung und Kürzung über dieselbe eine Funktion** (`redact_for_report`), angewandt auf jede in `detail` übernommene Zeichenkette **und auf den zusammengesetzten Endtext**. Geprüft über das vollständig serialisierte Objekt, nicht über ein Einzelfeld.
6. **Kein zweiter Deutungspfad.** Die Deutung läuft über das bestehende `_explain_project_failure`; Auth-Whitelist und Beschränkung auf das aktive Konto (Spec 0309 Nr. 2, 3, 4) gelten unverändert. `capabilities` baut keine eigene Textauswertung.
7. **Rein lesend, testgesichert über die protokollierten Argumentlisten.** Hier gewichtiger als bei `doctor`: `capabilities` läuft vor **jedem** Ablauf und in Umgebungen, die noch nicht beurteilt sind.
8. **Härtungsregeln ADR 0017 Abschnitt 5 unverändert:** kein `shell=True`, Argumente in Listenform über dasselbe injizierte `run`-Callable, keine Interpolation gelesener oder aus der Umgebung stammender Werte, Owner/Repo/Board-Titel bleiben Modulkonstanten.
9. **Nachhol-Befehle nur aus validierten eigenen Zahlen.** Die im öffentlichen Artefakt veröffentlichten Befehlszeilen werden ausschließlich aus Issue- und Spec-Nummer des laufenden Ablaufs gebildet (Spec-Nummer weiterhin gegen `^\d{4}$`, Issue-Nummer gegen `^\d+$`) — nie aus einer `gh`-Ausgabe, einem Issue-Body oder einem Kommentar. Der Block ist ausdrücklich als lokal von Daniel auszuführender Handgriff gekennzeichnet: Er steht dauerhaft in einem öffentlichen Artefakt und wird später von Agenten gelesen.
10. **„Vor dem Einfügen lesen" bleibt gültig, mit benannter Grenze.** Der Muss-Schritt aus `.claude/skills/github-board/SKILL.md` gilt unverändert für alles, was aus einer `gh`-Ausgabe in ein GitHub-Artefakt kopiert wird (`doctor`-Bericht, weiterzureichende Fehlermeldungen, Ausgabe des manuellen Messschritts). Auf dem automatischen Pfad wird er nicht abgeschwächt, sondern durch Kriterium 1 gegenstandslos. Der Skill-Text hält beide Pfade ausdrücklich getrennt, damit die Ausnahme nicht später auf den manuellen Pfad ausgedehnt wird.
11. **Auflagen für den manuellen Messschritt** (Daniel/Orchestrator, echte Remote-Session, Ausgabe an Issue #318):
    - **(a)** Kein Befehl, der das Credential ausgeben kann: `gh auth token`, `--show-token`, `echo $GH_TOKEN`, `env`/`printenv`, `GH_DEBUG=api`, `--verbose` sind ausgeschlossen. Der Filter in `redact_for_report` ist eine Musterliste; das Format des von der Plattform gestellten Tokens ist uns **nicht bekannt** und trifft die Muster möglicherweise nicht.
    - **(b)** Keine Anmeldung mit einem eigenen/persönlichen Token in der Remote-Umgebung, auch nicht temporär — das wäre faktisch das von ADR 0052 Abschnitt 6 ausgeschlossene zusätzliche Geheimnis in fremder Umgebung. Gemessen wird ausschließlich mit dem, was dort ohnehin vorliegt.
    - **(c)** Schreibmessungen ausschließlich gegen Issue #318 selbst — kein anderes Issue, kein Board-Feld, kein fremdes Repository. Jedes so entstandene Artefakt wird als Messartefakt gekennzeichnet.
    - **(d)** Die Ausgabe wird vor dem Anhängen Zeile für Zeile gelesen. Wirkt etwas wie ein Geheimnis oder ein opaker Bezeichner unbekannter Herkunft, wird es nicht eingefügt, sondern Daniel gemeldet.
    - **(e)** Lesen und Schreiben getrennt messen, je Messung Befehl und Ausgabe wörtlich (nach (d)) — keine paraphrasierte Ableitung aus einer anderen Ausgabe.

**Verschärfung gegenüber heute — benannt und aufgefangen:** Es ist eine echte Verschärfung auf zwei Achsen. *Frequenz:* `doctor` wird gelegentlich und bewusst gezogen, `capabilities` läuft vor jedem Ablauf. *Kanal:* `doctor` wird von einem Menschen eingefügt, der ihn vorher liest. Beides fängt Kriterium 1 auf, indem es den Fremdtext gar nicht erst auf den automatischen Pfad lässt — der Informationsverlust ist gering, denn *warum* ein Schritt ausgelassen wurde, trägt ein fester Satz genauso gut wie eine `gh`-Meldung; der Wortlaut ist eine Diagnose-Frage und gehört zu `doctor`.

**Securitykonzept-Ergänzungen** (`specs/architecture/0003-securitykonzept.md`): (1) neuer Unterabschnitt unter „Angriffsflächen" zum Betriebssignal `capabilities` — Fremdtext auf einem automatischen Pfad und Messwert als Ablaufsteuerung, gelöst durch Kanaltrennung, geschlossene Steuerwerte und Fail-open; ausdrücklich festhalten, dass Kriterium 10 aus Spec 0309 nicht gelockert, sondern präzisiert wird. (2) Neuer Eintrag unter „Bekannte Lücken": Das Format des von der Cloud-Plattform gestellten `gh`-Credentials ist unbekannt und muss die Muster in `redact_for_report` nicht treffen — die musterbasierte Schwärzung ist remote nachweislich schwächer als lokal, kompensiert durch 11(a) und 11(d), nicht durch Code. Reiht sich an den dokumentierten blinden Fleck bei 40-Hex-Alt-PATs an. (3) Neuer Eintrag unter „Bewusst akzeptierte Restrisiken": Der 403-Wortlaut der Cloud-Zwischenschicht steht wörtlich in einem öffentlichen Issue und in ADR 0055 — Infrastruktur-Information eines Drittanbieters, kein PhotoSort-Geheimnis; akzeptiert, weil der Befund ohne den Wortlaut nicht belegbar wäre.

**Keine neuen Secrets:** unverändert die in der jeweiligen Umgebung bereits vorhandene `gh`-Authentifizierung (remote ein von der Plattform gestellter Umgebungstoken, den wir weder anlegen noch ablegen noch rotieren) — deckt sich mit ADR 0017 Abschnitt 2 und ADR 0052 Abschnitt 6.

## Entscheidungen

- **Abweichung vom Wortlaut eines Akzeptanzkriteriums (`architect`, ADR 0055 Abschnitt 1):** Erkannt wird nicht die Session-Art, sondern die Board-Fähigkeit. Grund: Session-Erkennung ist nur ratend möglich (lokaler Token-Auth, CI und Remote sind an keinem Merkmal unterscheidbar) und würde beim Wegfall der Sperre weiterwarnen, bis jemand es von Hand zurücknimmt. Die Wirkung des Kriteriums ist erfüllt, sein Wortlaut nicht. Dieselbe Form der ausgewiesenen Abweichung wie ADR 0053 Abschnitt 7.
- **ADR 0052 Abschnitt 6 Punkt 1 wird abgelöst (`architect`, ADR 0055 Abschnitt 6):** Die Begründung („Autorisierung, nicht Transport") ist durch den Befund widerlegt. Der Ausschluss fällt für die Issue-/PR-Schritte, die Richtung wird **nicht** gewählt. Für die Board-Schritte bleibt er richtig. Alle übrigen Abschnitte von 0052 bleiben gültig, die ADR bleibt `Accepted` und erhält nur einen Verweis-Nachtrag.
- **Kein zweites Diagnosekommando aus `doctor` heraus (`architect`):** eigenes, schlankes `capabilities` statt `doctor`-Aufruf oder `doctor`-Schalter — Trennung von Rolle, Kosten und Änderungsrisiko.
- **Korrektur der Aufrufzahl (`test-engineer` und `security-engineer`, unabhängig voneinander):** ADR 0055 sagte zunächst „genau ein `gh`-Aufruf". Das trifft nicht zu, sobald die Deutung über `_explain_project_failure` mitbenutzt wird — `auth_info()` setzt `gh auth status` ab. Korrigiert auf einen Aufruf im Erfolgsfall, zwei im Fehlerfall, testgesichert als exakte Liste. Die Alternative (Deutung weglassen) wurde verworfen: Sie nähme `detail` die Ursachenunterscheidung, die das Kriterium „nachvollziehbarer Zustand" trägt.
- **Äußere Redaktion des zusammengesetzten `detail`-Texts (`test-engineer`):** `_explain_project_failure()` redigiert `str(error)` und hängt den Deutungstext danach an; ohne eine zweite Anwendung von `redact_for_report` auf den Endtext gälte die 500-Zeichen-Kürzung faktisch nicht. Eigener Pflicht-Test.
- **Kanaltrennung statt Kompensation (`security-engineer`):** Der Entwurf hätte redigierten Fremdtext ohne Menschen dazwischen in öffentliche PR-Bodies gebracht. Statt zusätzlicher Filter geht auf dem automatischen Pfad **gar kein** Fremdtext mehr ins dauerhafte Artefakt. Muss-Kriterium 10 aus Spec 0309 wird dadurch nicht gelockert, sondern gegenstandslos.
- **Zwei der vier Skills haben keinen Schritt in `BOARD_LIFECYCLE_STEPS` — ausgeschrieben statt verschwiegen (`developer`, Umsetzung):** Das Akzeptanzkriterium sagt, die vier Ablauf-Skills werteten das Ergebnis aus und versuchten einen *gemeldeten* Schritt nicht. Für `capture` und `spec-writer` kann aber nie ein Schritt gemeldet werden: `idee-erfassen` steht bewusst nicht in `BOARD_LIFECYCLE_STEPS` (das Issue entsteht, bevor das Board angefasst wird), und für das `Todo`-Setzen durch `spec-writer` existiert überhaupt kein eigener Schrittname (bekannte Granularitäts-Grenze aus ADR 0052). Ohne eine Festlegung wäre die Auswertung dort folgenlos. Umgesetzt ist deshalb, was aus derselben zwingenden Richtung folgt — beide Aufrufe laufen durch die gemessene Board-Auflösung:
  - **`capture`** führt `create-issue` bei `board_reachable: false` **trotzdem** aus (der Schritt ist gemessen *nicht* blockiert, das Issue entsteht) und scheitert danach erwartbar an der Board-Aufnahme. Gemeldet wird die Issue-Nummer plus der Nachhol-Handgriff (Board-Aufnahme, danach `set-status … --status Unrefined`). **`create-issue` wird nie wiederholt** — das legte ein zweites Issue an; die Zielzustands-Idempotenz aus ADR 0048 gilt für Board-Operationen, nicht für das Anlegen.
  - **`spec-writer`** lässt `show-status` und `set-status Todo` aus (beide gehen durch dieselbe Auflösung, beide scheitern sicher), fragt die `Ready`-Vorbedingung **einmal bei Daniel** nach, statt sie zu raten, und führt Branch, Spec-Datei und Spec-Commit unverändert aus. `set-status Todo` steht danach unter `## Lokal nachzuholen`.

  Beides erfüllt die Wirkung des Kriteriums (nicht mittendrin auf eine Wand laufen, nichts stillschweigend auslassen), geht aber über seinen Wortlaut hinaus und ist deshalb hier festgehalten.
- **AC 4 geteilt (`test-engineer`):** „macht die Warnungen nicht zur Lüge" ist als Aussage über die Zukunft nicht prüfbar. Geteilt in 4a (automatisch geprüfte Eigenschaft: Warnung hängt nur am Messergebnis) und 4b (Review-/Doku-Kriterium: `docs/setup.md` benennt die Sensoren).
- **`ux-ui-designer` nicht konsultiert (Schritt 2):** Die Story berührt ausschließlich ein CLI-Werkzeug, Skill-Dateien und Dokumentation; es existiert kein konkret benennbarer Anhaltspunkt für eine sichtbare Oberfläche — kein Pfad unter `frontend/`, keine dargestellten Daten, keine berührte Komponente.
- **Prioritäts-Empfehlung `Hoch` (Refinement, 2026-09-05):** entgegen der `Mittel`-Empfehlung des `requirements-engineer`. Grund: In die Remote-Fähigkeit sind mit 0309/0314/0317 drei Specs geflossen, und der Befund zeigt, dass sie für den Lebenszyklus ins Leere laufen, ohne dass irgendetwas davor warnt. Der Kostenanteil ist klein.

## Offene Fragen

Keine blockierenden. Zwei Punkte sind Daniel im Refinement bzw. hier ausdrücklich vorgelegt und bleiben ohne Widerspruch bestehen:

- **Daniels Richtungstendenz** (nativer GitHub-Projects-Workflow plus Kommentar-Verlinkung) ist **nicht** die gewählte Richtung dieser Spec — sie steht als eine Option in der Entscheidungsvorlage (ADR 0055 Abschnitt 7), zusammen mit dem Gegenargument aus ADR 0037 Abschnitt 5 / 0046 Abschnitt 5: Ein PR-getriggerter Workflow kann bestenfalls `Done` setzen, während die übrigen fünf Statuswerte und alle Body-Schreibvorgänge stattfinden, bevor ein PR existiert.
- **Veröffentlichung des 403-Wortlauts** der Cloud-Zwischenschicht in einem öffentlichen Repository: Infrastruktur-Information eines Drittanbieters, kein PhotoSort-Geheimnis. Faktisch bereits entschieden — Daniel hat den `doctor`-Bericht selbst als Kommentar an #318 gehängt, und ADR 0055 stützt sich zentral auf den Wortlaut. Als bewusst akzeptiertes Restrisiko im Securitykonzept zu führen.

## Out of Scope

- **Umsetzung einer der Richtungen.** Diese Spec stellt fest, macht den Ablauf ehrlich und bereitet die Entscheidung vor. Gebaut wird danach, in einer eigenen Story mit eigener ADR.
- **Umstellung irgendeines Aufrufs auf REST** — auch nicht in `doctor`. Der Ausschluss aus ADR 0052 Abschnitt 6 Punkt 1 fällt, aber die Richtung wird nicht gegangen.
- **Änderung an `doctor`.** Weder REST-Prüfung noch Schreibprobe noch 403-Deutung noch eine Korrektur der zu weit greifenden Zuordnungstabelle — letztere ist als Befund festzuhalten, nicht zu reparieren.
- **Umgehung der Einschränkung.** Ein Weg, der die Sperre technisch aushebelt, wird nicht ohne ausdrückliche Entscheidung gegangen.
- **Änderung an der `gh`-Bereitstellung** (ADR 0053/0054, Spec 0314/0317) — läuft getrennt.
- **Ein zusätzliches, dauerhaft in der Remote-Umgebung abgelegtes Geheimnis.**
- **Eine Zustandsdatei**, eine Datei unter `.github/workflows/`, eine neue Variable in `.env.example`, eine Änderung an Board-Feldern oder Board-Workflows.
- **Ausweitung auf autonom, ohne Daniels Session laufende Agenten.** Der Lebenszyklus bleibt session-getriggert.
- **`.claude/agents/developer.md`** bleibt unverändert — sein Board-Schritt ist ein Hinweis an den Aufrufer, und der ist über die Skills gebunden.
