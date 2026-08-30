# 0278 - Board-Operationen melden einen bereits erreichten Zielzustand nicht mehr als Fehler

**Status:** Implemented ([PR #290](https://github.com/TheRealKoller/photosort/pull/290))
**Erstellt:** 2026-08-30
**Bezug:** [Issue #278](https://github.com/TheRealKoller/photosort/issues/278)

## Ziel

Der Abschluss eines Features soll ohne manuelle Beurteilung durchlaufen. Heute meldet das Board-Werkzeug beim Finalisieren einen Fehler, obwohl alles Gewollte bereits passiert ist: Die Spalte im Board steht auf `Done`, das Issue ist geschlossen, die Spec-Statuszeile ist umgeschrieben. Ursache ist, dass das Setzen der Spalte auf `Done` das Issue bereits über die Board-Automation schließt — der danach folgende eigene Schließen-Schritt trifft ein schon geschlossenes Issue und quittiert das als Fehlschlag.

Das ist teuer an genau der falschen Stelle: Der `ship-feature`-Ablauf behandelt eine Fehlermeldung an dieser Stelle vorschriftsgemäß so, dass die bereits korrekt geschriebene Spec-Statuszeile wieder verworfen und der Aufruf wiederholt wird. Beides wäre hier falsch — die Statuszeile stimmte, und die Wiederholung scheitert erneut an derselben Stelle. Jeder Feature-Abschluss braucht dadurch eine Handbeurteilung.

Betroffen sind beide Stellen, an denen ein Issue über das Board geschlossen wird: das Finalisieren einer Spec und das Setzen des Status auf `Done` (letzteres nutzt u.a. der Verwerfen-Pfad beim Schärfen einer Idee).

Beobachteter Fall (Finalisierung von Spec 0209, PR #277):

```
{"error": "gh-Aufruf fehlgeschlagen (gh issue close 209): GraphQL: Could not close the issue. (closeIssue)"}
```

## User Story

Als Nutzer des Board-Werkzeugs möchte ich, dass ein bereits geschlossenes Issue als erreichter Zielzustand gilt und nicht als Fehler, damit der Feature-Abschluss ohne falschen Fehlalarm und ohne Rückbau korrekter Arbeit durchläuft.

## Akzeptanzkriterien

> Gegenüber der Story-Fassung im Issue durch den `test-engineer` präzisiert: jedes Kriterium nennt den beobachtbaren Nachweis (Exit-Code/JSON/Aufruflog/Dateiinhalt). Kriterien 8 und 9 sind neu — sie halten zwei Zusicherungen fest, die im Ergebnis unsichtbar sind und sonst unbemerkt wegrefactort würden.

- [ ] **1. Finalisieren bei bereits geschlossenem Issue meldet Erfolg.** Schlägt `gh issue close` fehl, während das Issue zu diesem Zeitpunkt tatsächlich geschlossen ist, endet `finalize` mit Exit-Code 0 und dem regulären JSON-Payload — kein `{"error": …}`.
- [ ] **2. `set-status --status Done` verhält sich identisch:** derselbe Ausgangszustand führt zu Exit-Code 0 und dem regulären Payload `{"issue_number": …, "status": "Done"}`.
- [ ] **3. Ununterscheidbarkeit:** Rückgabewert bzw. ausgegebenes JSON sind in beiden Fällen *gleich* denen eines Laufs, in dem dieser Aufruf das Issue selbst geschlossen hat — insbesondere ohne zusätzliches Feld ("war schon geschlossen").
- [ ] **4. Zielzustand unverändert:** Board-Item wird per `item-edit` auf die `Done`-Options-ID gesetzt, das Schließen des Issues wird versucht, und beim Finalisieren steht in der Header-Zone der Spec-Datei exakt `**Status:** Implemented ([PR #MMM](URL))` mit dem aufgelösten PR.
- [ ] **5. Echte Fehlschläge bleiben Fehler:** Schlägt `gh issue close` fehl und ist das Issue danach nachweislich `open` — oder lässt sich der Zustand nicht ermitteln (nicht existierendes Issue, fehlende Berechtigung, Dienst nicht erreichbar) —, wird der **ursprüngliche** Fehler von `gh issue close` mit unverändertem Meldungstext als `{"error": …}` mit Exit-Code 1 gemeldet; bei gescheiterter Nachprüfung ist deren Fehler als Ursache verkettet (`__cause__`).
- [ ] **6. Wiederholter Aufruf nach erfolgreichem Abschluss:** Zwei identische `finalize`-Aufrufe hintereinander (gleiche Spec, gleiches Issue, gleiche `--pr-number`) enden beide mit Exit-Code 0 und identischem JSON; der Inhalt der Spec-Datei ist nach dem zweiten Lauf identisch zu dem nach dem ersten. Ein Rückbau der Statuszeile zwischen den Läufen ist nicht nötig.
- [ ] **7. `ship-feature` braucht keine Handbeurteilung mehr:** In `ship-feature`/`github-board` steht kein Hinweis mehr auf einen nötigen Rückbau der Statuszeile bzw. auf "nur bei Datei-Status `Accepted` wiederholbar"; die übrige `{"error": …}`-Behandlung (unverändert weitergeben, nicht umgehen) bleibt unangetastet.
- [ ] **8. Kein Mehraufwand im Regelfall:** Im ungestörten Erfolgsfall setzen `finalize` und `set-status --status Done` weiterhin genau die bisherigen `gh`-Aufrufe ab — insbesondere **keine** zusätzliche Zustandsabfrage (`gh issue view … --json state`). Die Prüfung findet ausschließlich nach einem Fehlschlag statt.
- [ ] **9. Eng gefasstes Statusgate:** Datei-Status `Implemented` lässt den Aufruf nur weiterlaufen, wenn die vorhandene Statuszeile exakt der Zeile entspricht, die dieser Lauf schreiben würde. Ein `Implemented` mit anderem PR — und jeder andere Status — bricht unverändert ab, ohne Board-Schreibzugriff und ohne die Datei zu verändern.

## Datenmodell-Bezug

Keiner. Die Änderung betrifft ausschließlich das Entwickler-/Prozess-Werkzeug `scripts/gh-board.py` und berührt weder die Anwendungsdatenbank noch [`docs/architecture.md`](../../docs/architecture.md).

## Architektur / Umsetzung

**Grundregel** (neu festgehalten in ADR [`0048`](../decisions/0048-board-operationen-zielzustands-idempotent.md)): Für die schreibenden Board-Operationen zählt der **Zielzustand**, nicht die Urheberschaft des einzelnen Aufrufs. Ein bereits geschlossenes Issue erfüllt die Zusicherung von `close_issue()` vollständig — unabhängig davon, wer es geschlossen hat.

### Ursache

Auf dem Board ist der native Workflow `Auto-close issue` aktiv (bewusst so entschieden, ADR 0046 Abschnitt 5). Er feuert auf das `Done`, das `gh-board.py` unmittelbar davor gesetzt hat, und ist schneller als der eigene Folgeaufruf `gh issue close`. ADR 0046 nahm an, das eigene `close` folge dem Workflow folgenlos — diese Nebenannahme trägt nicht. `Auto-close issue` ist dabei nicht die einzige Quelle: ein von Hand geschlossenes Issue und der Ausnahmepfad "Merge vor der Finalisierung" (dort schließt das Closing-Keyword) erzeugen dieselbe Situation.

### Betroffene Stellen (alle in `scripts/gh-board.py`)

- `GhBoard.close_issue()` — der eigentliche Fix, wirkt für **beide** Aufrufwege (`cmd_finalize` und `cmd_set_status` bei `Done`).
- `GhBoard` — neue lesende Methode `issue_state(issue_number) -> str` (`gh issue view <NNN> --json state`, Ergebnis kleingeschrieben, analog zur bestehenden Behandlung in `get_pull_request()`).
- `cmd_finalize()` — Statusgate um den Fall "bereits exakt diese Zielzeile" erweitert (siehe unten).
- `cmd_set_status()` bleibt **unverändert** — es profitiert allein über `close_issue()`.
- Tests: `scripts/tests/test_gh_board.py` (`FakeGh` bekommt einen Issue-Zustand).

### Lösungsansatz: Nachprüfen des Zustands statt Fehlertext-Heuristik

`close_issue()` reicht einen Fehlschlag nicht mehr direkt weiter, sondern prüft den tatsächlichen Issue-Zustand:

```python
def close_issue(self, issue_number: int) -> None:
    """Zielzustand ist 'Issue geschlossen', nicht 'dieser Aufruf hat es geschlossen': Der
    Board-Workflow 'Auto-close issue' schliesst das Issue schon beim Setzen der Spalte auf
    'Done' (ADR 0046, Abschnitt 5) und ist dabei schneller als dieser Aufruf. Ein Fehlschlag
    wird deshalb gegen den tatsaechlichen Zustand geprueft statt gegen den Fehlertext von
    `gh` - der ist undokumentiert, aenderbar und nicht trennscharf (ADR 0048, Abschnitt 2)."""
    try:
        self._run_text(["gh", "issue", "close", str(issue_number)])
    except BoardError as close_error:
        try:
            already_closed = self.issue_state(issue_number) == "closed"
        except BoardError as probe_error:
            # Ist die Pruefung selbst nicht moeglich, bleibt der urspruengliche Fehlschlag die
            # gemeldete Ursache - er ist der aussagekraeftigere.
            raise close_error from probe_error
        if not already_closed:
            raise
```

Abgrenzung echter Fehler — sie werden **weiterhin gemeldet**, ohne Sonderregel:

| Fall | Verhalten |
|---|---|
| Issue bereits geschlossen | Erfolg, Fehlschlag verworfen |
| Fehlende Berechtigung, Issue offen | `issue_state` liefert `open` → ursprünglicher Fehler |
| Issue existiert nicht | `gh issue view` scheitert ebenfalls → ursprünglicher Fehler (verkettet) |
| Dienst nicht erreichbar | wie oben → ursprünglicher Fehler |

**Race-Condition:** Die Prüfung läuft bewusst **nach** dem Fehlschlag, nicht als Vorabprüfung. Eine Vorabprüfung ("erst lesen, dann ggf. schließen") kostet in jedem `Done`-Pfad einen zusätzlichen Aufruf und beseitigt das Rennen trotzdem nicht — der Workflow feuert asynchron auf das unmittelbar davor gesetzte `Done` und kann zwischen Lesen und Schließen zuschlagen. Die Nachprüfung deckt beide Reihenfolgen ab und kostet im Erfolgsfall nichts.

**Erfolgsmeldung bleibt ununterscheidbar:** `cmd_finalize`/`cmd_set_status` bekommen **kein** zusätzliches Feld ("war schon geschlossen"). Der aufrufende Ablauf soll den Unterschied nicht kennen müssen.

### Wiederholbarkeit von `finalize` (Akzeptanzkriterium 6)

`cmd_finalize` bricht heute bei jedem Datei-Status ≠ `Accepted` ab — ein zweiter Aufruf nach erfolgreichem Abschluss wäre also weiterhin ein Fehler. Dieselbe Zielzustands-Regel wird deshalb eng gefasst auch hier angewandt: Steht in der Spec-Datei bereits **exakt die Zeile, die dieser Aufruf schreiben würde** (`Implemented ([PR #MMM](url))` mit demselben aufgelösten PR), läuft der Aufruf ohne Fehler weiter (Board `Done`, Issue schließen, identischer Rückgabewert). Jeder andere Status bricht unverändert ab, insbesondere `Implemented` mit einem **anderen** PR — das ist kein erreichter Zielzustand, sondern ein Hinweis auf die falsche Spec-Nummer.

Ablauf in `cmd_finalize` dafür minimal umgestellt: Datei-Status gegen `{"Accepted", "Implemented"}` prüfen → PR wie bisher über `_resolve_pull_request()` auflösen (rein lesend, vor jedem Schreibzugriff) → Zielzeile bauen → bei `Implemented` die vorhandene Statuszeile des Headers (`_STATUS_LINE_RE`) gegen die Zielzeile vergleichen und bei Abweichung abbrechen → schreiben (bei Gleichheit inhaltlich ein No-op) → Board `Done` → `close_issue()`.

### Reihenfolge der Umsetzung

1. `issue_state()` + `close_issue()` mit Nachprüfung (TDD: erst der Test "close scheitert, Issue ist geschlossen → Erfolg"). Deckt damit bereits beide Akzeptanzkriterien zu `finalize` und `set-status Done` ab.
2. `FakeGh` erweitern: Issue-Zustand (offen/geschlossen), Antwort auf `gh issue view --json state` (der bestehende `gh issue view`-Zweig unterscheidet nach den angefragten `--json`-Feldern), und `gh issue close` auf einem bereits geschlossenen Issue scheitert mit der real beobachteten Meldung (`GraphQL: Could not close the issue. (closeIssue)`) — die Fehlermeldung darf im Test vorkommen, das Produktivverhalten hängt aber nachweislich nicht an ihr.
3. Negativfälle: Issue offen → ursprünglicher Fehler; Nachprüfung selbst nicht möglich → ursprünglicher Fehler; Erfolgspfad setzt **keinen** zusätzlichen `gh issue view`-Aufruf ab (Regressionsschutz gegen eine schleichende Vorabprüfung).
4. `cmd_finalize`: Zielzeilen-Vergleich, danach die Tests für Wiederholbarkeit und für "`Implemented` mit anderem PR bricht ab".
5. Doku-Nachzug im selben PR: In `.claude/skills/ship-feature/SKILL.md` (Schritt 8) und `.claude/skills/github-board/SKILL.md` trifft der Hinweis "wiederholbar, solange der Datei-Status noch `Accepted` ist" bzw. "Statuszeile vorher verwerfen" nicht mehr zu. Die übrige `{"error": ...}`-Behandlung bleibt für echte Fehler unverändert.

### Bewusst nicht gewählt

- **`Auto-close issue` im Projekt-UI abschalten:** behebt nur eine von mehreren Quellen (Handschluss, Closing-Keyword im Ausnahmepfad bleiben) und verlegt die Korrektheit in eine manuelle, nicht versionierte, nicht testbare Board-Einstellung. Begründung vollständig in ADR 0048, Abschnitt 4.
- **Fehlertext-Heuristik auf `"Could not close the issue"`:** undokumentierte, jederzeit änderbare GraphQL-Formulierung und nicht trennscharf — würde in die teure Richtung irren (echter Fehlschlag gilt als Erfolg).
- **Sonderfall beim Aufrufer (`ship-feature` erkennt diese eine Meldung):** verteilt Wissen über eine `gh`-Fehlerformulierung in eine ungetestete Prosa-Datei und macht die Meldung zu einer Schnittstelle, die sie nicht ist.

## Teststrategie

**Ebene:** ausschließlich Unit-Tests in `scripts/tests/test_gh_board.py` gegen den injizierten `FakeGh` (kein echtes `gh`, kein Netzwerk, kein `subprocess`), plus die bestehende CLI-Ebene über `main([...], run=fake, repo_root=tmp_path)`. Kein Integrationstest-Pendant, kein neuer Coverage-Bezug (`scripts/` läuft weiterhin ohne `--cov-fail-under` im `demo-scripts`-CI-Job). Der einzige Bruch mit dem bisherigen Muster ist, dass der `FakeGh` zustandsbehaftet wird. Über diesen Branch hinaus geltende Regeln stehen in der Sektion "Erweiterung für ADR 0048" in [`specs/architecture/0002-testkonzept.md`](../architecture/0002-testkonzept.md).

**`FakeGh`-Erweiterung (Voraussetzung, nicht Beiwerk):**

- Neuer Parameter `issue_states: dict[int, str] | None` (Default: alle Issues offen).
- `gh issue view` wird ab jetzt anhand des `--json`-Arguments unterschieden: `state` → `{"state": "OPEN"|"CLOSED"}`, `closedByPullRequestsReferences` → wie bisher. Der bisherige pauschale Zweig genügt nicht mehr.
- `gh issue close` wird zustandsbehaftet: auf offenem Issue Erfolg **und** Zustandswechsel auf geschlossen; auf bereits geschlossenem Issue Fehlschlag mit der real beobachteten Meldung `GraphQL: Could not close the issue. (closeIssue)`. Der bestehende `failing`/`failure_stderr`-Mechanismus behält Vorrang (Berechtigungs-/Netzwerkfehler).
- Optionales Flag (Default **aus**), das ein `item-edit` auf die `Done`-Options-ID das Issue schließen lässt — modelliert den Board-Workflow `Auto-close issue` und wird von genau einem Test benutzt (Bug-Reproduktion). Als Default würde es alle unbeteiligten Tests mit einem fremden Verhalten belasten.
- Der Fehlertext im Fake ist Kulisse, **nie** Prüfgegenstand: Keine Assertion darf auf ihm aufsetzen, sonst wäre die in ADR 0048 verworfene Fehlertext-Heuristik durch die Hintertür zurück.

**Testfälle `GhBoard.issue_state()`/`close_issue()`:**

1. `issue_state()` setzt exakt `["gh","issue","view","<NNN>","--json","state"]` ab und liefert kleingeschrieben (`CLOSED` → `"closed"`).
2. Fehlendes/unparsbares `state`-Feld → `BoardError` (kein `KeyError`, der die JSON-Ausgabekonvention des Werkzeugs mit einem Traceback bräche).
3. `close` schlägt fehl, Issue ist `closed` → `close_issue()` kehrt still zurück (AK 1/2-Kern).
4. `close` schlägt fehl, Issue ist `open` → ursprünglicher Fehler, Assertion auf den **Originaltext** (z.B. das gesetzte `failure_stderr`), nicht nur auf den Typ (AK 5).
5. `close` schlägt fehl **und** die Nachprüfung schlägt fehl (`failing={("gh","issue","view","<NNN>","--json","state")}`) → ursprünglicher `close`-Fehler wird gemeldet, der Lesefehler ist als `__cause__` verkettet (AK 5).
6. `close` erfolgreich → **kein** `gh issue view … --json state` im Aufruflog (AK 8, Regressionsschutz gegen ein Umbauen zur Vorabprüfung).

**Testfälle `cmd_set_status` / `cmd_finalize`:**

7. `set-status --status Done` auf bereits geschlossenem Issue → regulärer Payload, Board-`item-edit` auf `OPT_Done` nachweisbar abgesetzt (AK 2/4).
8. Bug-Reproduktion end-to-end mit aktivierter Fake-Automation: `Done` setzen schließt das Issue, das eigene `close` trifft es geschlossen an → Erfolg.
9. **Ununterscheidbarkeit als Gleichheit zweier Läufe:** `assert ergebnis_bereits_geschlossen == ergebnis_frisch_geschlossen`, je einmal für `cmd_finalize` und `cmd_set_status` (AK 3). Bewusst keine Feldliste — nur die Gleichheitsform benennt beim Bruch die verletzte Zusicherung und fängt ein später nachgerüstetes `already_closed`-Feld ab.
10. Erfolgspfad `finalize` ungestört → kein `gh issue view … --json state` im Log (AK 8).
11. Statusgate (a): Datei steht auf `Implemented ([PR #281](…))`, Aufruf mit `--pr-number 281` → läuft durch, Rückgabewert identisch zum Erstlauf, Dateiinhalt unverändert (AK 9 positiv).
12. Statusgate (b): `Implemented` mit **anderem** PR → `BoardError`, Datei unverändert, **kein** `item-edit`/`issue close` im Log (AK 9 negativ).
13. Statusgate (c): `Proposed` → unveränderter Abbruch mit der bisherigen Begründung.
14. Statusgate (d): gleiches Schlüsselwort, abweichender Freitext (z.B. andere URL bei gleicher Nummer) → Abbruch. Verglichen wird die vollständige Zeile aus der **Header-Zone** (`_split_header`), nicht das führende Schlüsselwort aus `read_spec_status()`.
15. **Wiederholbarkeit als ganzer Aufruf:** `cmd_finalize` zweimal auf demselben zustandsbehafteten `FakeGh`, ohne dazwischen etwas zurückzunehmen → beide erfolgreich, Rückgabewerte gleich, Datei nach Lauf 2 identisch zu nach Lauf 1 (AK 6).
16. **CLI-Ebene:** `main(["finalize", "--spec", …, "--pr-number", …])` zweimal → beide Male Exit-Code 0 und identisches JSON auf stdout (AK 7 — das ist die Ebene, die `ship-feature` tatsächlich auswertet).

**Anpassung eines bestehenden Tests (nicht übersehen):** `test_finalize_lehnt_eine_nicht_akzeptierte_spec_ab` benutzt heute `Implemented ([PR #1](x))` als Beispiel für "nicht akzeptiert" und wird durch diese Änderung inhaltlich zu Fall 12 mit anderer Begründung. Er wird **geteilt statt umgebogen**: ein Test bleibt beim Statusgate (`Proposed`, Assertion auf "Accepted" in der Meldung), einer prüft die abweichende Zielzeile mit eigener Assertion.

**Bewusst nicht getestet:** *wann* GitHub `Could not close the issue.` wirft und ob `Auto-close issue` vor dem eigenen `gh issue close` feuert — beides Verhalten/Timing eines Fremdsystems. Die Idempotenz ist gerade so gebaut, dass beide Reihenfolgen erfolgreich sind; ein Test darüber würde nur den Fake prüfen. Realer Nachweis ist der Abschluss dieses PRs selbst (`finalize` läuft ohne `{"error": …}` durch).

**Skill-Dateien (`ship-feature`, `github-board`): kein `pytest`-Gegenstand**, sondern statischer Konsistenz-Check im `review-tests`-Durchlauf — kein Rückbau-Hinweis mehr für diesen Fall, und die übrige `{"error": …}`-Behandlung unverändert streng. Letzteres ist der wichtigere Teil der Prüfung: Das Risiko dieser Änderung ist nicht die vergessene Zeile, sondern ein insgesamt aufgeweichter Umgang mit echten Fehlern.

## UI/UX

Nicht relevant. `scripts/gh-board.py` ist ein reines CLI-Werkzeug des Entwicklungsablaufs ohne jede sichtbare Oberfläche; es wird keine Datei unter `frontend/` berührt und es entstehen keine Daten, die irgendwo dargestellt würden.

## Security

Sicherheitsrelevant, kein Blocker. Reines Entwickler-/Prozess-Tooling (`scripts/gh-board.py`) ohne Bezug zum Auth-, Sichtbarkeits- oder Datenmodell der Anwendung — keine Foto-/Projektdaten, keine neue Sichtbarkeitsasymmetrie zwischen den beiden Nutzern, kein neues Secret, kein zusätzlicher `gh`-Scope (`gh issue view` braucht nur das bereits vorhandene Repo-Leserecht). Neu ist eine Klasse, die es im Werkzeug bisher nicht gab: **ein fehlgeschlagener Schreibaufruf wird bewusst verworfen, statt weitergereicht zu werden.** Die bisherige Linie war ausnahmslos "jeder `gh`-Fehlschlag wird als `{"error": ...}` gemeldet". Vollständige Herleitung im Abschnitt "Zielzustands-Idempotenz der Board-Operationen" von [`specs/architecture/0003-securitykonzept.md`](../architecture/0003-securitykonzept.md).

### Bedrohung 1: Ein echter Fehlschlag wird als Erfolg quittiert

Ein Berechtigungsfehler, ein nicht existierendes Issue oder ein nicht erreichbarer Dienst darf nicht über die neue Fehlerbehandlung zu einem Erfolg werden. Abgedeckt durch die Konstruktion aus ADR 0048: Die Nachprüfung hängt an derselben `gh`-Session wie der Schreibaufruf — scheitert der Zugriff grundsätzlich, scheitert auch `gh issue view <NNN> --json state`, und der **ursprüngliche** Fehler wird gemeldet. Der Verzicht auf eine Heuristik über den `gh`-Fehlertext ist dabei auch sicherheitsseitig die tragende Entscheidung: ein Textmuster kann nur falsch-positiv oder falsch-negativ irren, und falsch-positiv (echter Fehlschlag gilt als Erfolg) ist hier die teure Richtung. Der Zustandsabruf schließt sie per Konstruktion aus.

**Muss-Kriterium (Auswertung des Zustands):** Erfolg gilt nur bei einer **positiven Gleichheitsprüfung** auf `closed`. Jeder andere Wert — `open`, ein künftiger neuer Enum-Wert, ein fehlendes/leeres/`null`-`state`-Feld — führt auf den Fehlerpfad. Ein `!= "open"` würde einen unbekannten Wert als Erfolg verbuchen und ist unzulässig. Zu beachten: `gh` liefert den Zustand als GraphQL-Enum in Großschreibung (`CLOSED`); es braucht dieselbe Normalisierung wie bereits in `GhBoard.get_pull_request()` (`str(data["state"]).lower()`), sonst greift die Ausnahme nie.

**Muss-Kriterium (Abfrageumfang):** Die neue Methode fragt ausschließlich `--json state` ab, nie Titel, Body, Labels oder Kommentare. Das Repo ist `PUBLIC`, diese Felder sind von Dritten befüllbarer Freitext, und jede Meldung des Werkzeugs wird vom `github-board`-Skill wörtlich in den Hauptsession-Kontext gespiegelt, der GitHub-Schreibzugriff hat. Dieselbe Begründung wie bei der Entscheidung gegen das Einlesen des PR-Bodys (ADR 0046, Abschnitt 3): verarbeitet werden nur strukturierte, von GitHub selbst erzeugte Metadaten. Der gelesene Wert wird ausschließlich gegen eine Konstante verglichen — er fließt nie in einen Pfad, ein `gh`-Argument oder in geschriebenen Dateiinhalt.

**Muss-Kriterium (unveränderte Härtung):** Aufruf in Listenform ohne `shell=True`, Issue-Nummer als `int` bzw. aus der gegen `^\d{4}$` validierten Spec-Nummer abgeleitet (ADR 0017, Abschnitt 5).

### Bedrohung 2: Das gelockerte Datei-Status-Gate erlaubt einen unerwünschten Schreibzugriff oder eine Fehlzuordnung

Geprüft und verneint: Verglichen wird gegen die **vollständige** Zielzeile inklusive aufgelöster PR-Nummer und PR-URL. Der einzige neu zulässige Schreibvorgang schreibt damit exakt den Inhalt, der bereits in der Datei steht — es gibt keinen Inhalt, der jetzt schreibbar wäre und es vorher nicht war. `Implemented` mit einem **anderen** PR bricht unverändert ab. Der Schutzzweck des Gates (eine nie freigegebene oder eine fremde Spec wird nicht finalisiert) bleibt erhalten, weil der Zustand `Implemented ([PR #MMM](url))` regulär nur durch einen vorherigen, aus `Accepted` heraus erfolgreichen Lauf entsteht; wer die Datei von Hand auf diese Zeile setzen könnte, könnte sie ebenso auf `Accepted` setzen — kein Rechtezuwachs.

**Muss-Kriterium (Header-Zone):** Die Zeilengleichheit wird ausschließlich in der Header-Zone geprüft, über dieselbe Trennung wie `set_status_line()` (`_split_header`), nicht über eine Suche im gesamten Dateitext. Sonst könnte eine in der Inhalts-Zone zitierte `**Status:**`-Zeile die Gleichheit erfüllen, während der Header auf etwas anderem steht — dieselbe Falle, gegen die es für das Schreiben bereits einen Regressionstest gibt.

**Muss-Kriterium (Reihenfolge):** Jeder Datei-Status außer `Accepted`/`Implemented` bricht weiterhin ab, **bevor** ein GitHub-Zugriff stattfindet. Nur `Implemented` darf die Entscheidung bis nach der PR-Auflösung verschieben (die Zielzeile ist ohne aufgelösten PR nicht bildbar). Die übrigen Zuordnungs-Sicherungen bleiben unangetastet: genau ein Treffer in `find_spec_path()`, Spec-Nummer = Issue-Nummer, repo-qualifizierte Prüfung der Closing-Referenz und Default-Branch-Prüfung in `_require_linked_issue()`.

### Bewusst akzeptiertes Restrisiko

Fehlt das Schreibrecht auf Issues **und** ist das Issue aus anderem Grund bereits geschlossen (Board-Workflow `Auto-close issue`, Closing-Keyword beim Merge, manuelles Schließen), meldet `close_issue()` Erfolg, obwohl der Aufruf nichts bewirkt hat. Akzeptiert, weil der zugesicherte Zielzustand tatsächlich vorliegt, das fehlende Recht spätestens bei der nächsten tatsächlich ändernden Operation auffällt (insbesondere beim unmittelbar vorausgehenden `set_status`-Aufruf, der weiterhin ungefiltert scheitert, sowie beim `project`-Scope-Check zu Beginn jedes Laufs) und ausschließlich Prozess-Metadaten betroffen sind. Übernommen aus ADR 0048, Abschnitt "Bewusst in Kauf genommen"; im Sicherheitskonzept unter "Bewusst akzeptierte Restrisiken" verankert.

## Entscheidungen

- **Zielzustands-Idempotenz statt Urheberschaft** (ADR [`0048`](../decisions/0048-board-operationen-zielzustands-idempotent.md), neu angelegt): Ein bereits geschlossenes Issue erfüllt die Zusicherung von `close_issue()`. Korrigiert eine Nebenannahme aus ADR 0046 Abschnitt 5, ohne diese abzulösen.
- **Nachprüfung nach dem Fehlschlag statt Vorabprüfung:** deckt beide Reihenfolgen des Rennens mit der asynchronen Board-Automation ab und kostet im Erfolgsfall keinen zusätzlichen `gh`-Aufruf.
- **Keine Fehlertext-Heuristik:** Die GraphQL-Formulierung ist undokumentiert und nicht trennscharf; ein Textmuster würde in die teure Richtung irren.
- **Akzeptanzkriterium 6 wörtlich gelesen, eng gefasst umgesetzt:** Der Issue-Text nennt ausdrücklich beide Stellen als betroffen, deshalb gilt die Wiederholbarkeit auch für `finalize` — aber nur die *identische* Zielzeile inkl. PR-Nummer/URL gilt als erreichter Zustand; jeder andere Status bricht unverändert ab. (Vom `architect` als offene Alternative markiert, hier entschieden.)
- **`ux-ui-designer` nicht konsultiert (Schritt 2):** Die Story hat keinen konkret benennbaren Bezug zu einer sichtbaren Oberfläche — betroffen ist ausschließlich ein CLI-Werkzeug des Entwicklungsablaufs, keine Datei unter `frontend/`, keine dargestellten Daten.
- **Testkonzept ergänzt:** neue Sektion "Erweiterung für ADR 0048" in `specs/architecture/0002-testkonzept.md` (Pflicht-Achsen für Zielzustands-Nachprüfungen, Ununterscheidbarkeit als Gleichheit zweier Läufe, Aufruflog-Assertions, Abgrenzung des zustandsbehafteten Test-Doubles).
- **Sicherheitskonzept ergänzt:** neuer Abschnitt "Zielzustands-Idempotenz der Board-Operationen", neues akzeptiertes Restrisiko, Nachführung bei "Bekannte Lücken" zum `review-security`-Trigger für `scripts/**`.

## Offene Fragen

Keine. (Ein Punkt zur Kenntnis, außerhalb dieser Spec: `scripts/**` löst den `review-security`-Trigger weiterhin nicht aus — ob das dauerhaft so bleibt, ist eine eigene Entscheidung Daniels und im Sicherheitskonzept unter "Bekannte Lücken" nachgeführt.)

## Out of Scope

- Abschalten oder Umkonfigurieren des Board-Workflows `Auto-close issue` im GitHub-Projekt-UI.
- Wiedereröffnen eines Issues durch das Werkzeug — alle Statuswerte außer `Done` fassen den Issue-Zustand weiterhin nicht an.
- Änderungen an der übrigen `{"error": ...}`-Behandlung des `github-board`-Skills für echte Fehler.
- Idempotenz weiterer Board-Operationen über `close_issue()` und das `finalize`-Statusgate hinaus.
