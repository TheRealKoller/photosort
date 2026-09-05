# 0048 - Board-Operationen sind zielzustands-idempotent: ein bereits erreichter Zielzustand ist Erfolg

**Status:** Superseded — abgelöst durch ADR [`0057`](./0057-board-lebenszyklus-nativ-statt-eigenbau.md). Das *Prinzip* aus Abschnitt 1 (Maßstab ist der Zielzustand, nicht die Urheberschaft dieses Aufrufs) ist in ADR 0057, Abschnitt 5.2 ausdrücklich übernommen und bleibt in Kraft — es ist dort strukturell erfüllt, statt eigens hergestellt zu werden. Der *Mechanismus* dieser ADR (Nachprüfen des Issue-Zustands nach fehlgeschlagenem `gh issue close`, enge Ausnahme in `cmd_finalize`) entfällt mit dem Werkzeug und mit seiner Ursache: Keine Session schließt mehr ein Issue.
**Datum:** 2026-08-30
**Bezug:** GitHub-Issue [`#278`](https://github.com/TheRealKoller/photosort/issues/278) ("Feature-Abschluss meldet Fehler, obwohl alles Gewollte passiert ist"), zugehörige Feature-Spec `specs/features/0278-*.md`, `scripts/gh-board.py` (`GhBoard.close_issue`, `cmd_set_status`, `cmd_finalize`), ADR [`0046`](./0046-pr-issue-verknuepfung-closing-keyword.md) (Abschnitt 5 — `Auto-close issue` darf anbleiben; bleibt unverändert gültig, die dortige Nebenannahme wird hier korrigiert), ADR [`0037`](./0037-status-lebenszyklus-umsetzungsfortschritt-pr-merge-erkennung.md) (Abschnitt 5/6 — Status-Feld nur über den getesteten Tool-Layer, `Done` schließt zusätzlich das Issue), ADR [`0042`](./0042-pre-merge-finalisierung-statt-nachzieh-pr.md) (Pre-Merge-Finalisierung), ADR [`0043`](./0043-spec-nummer-gleich-issue-nummer-sync-tool-entfaellt.md) (`gh-board.py` als einzige Board-Schreibstelle).

## Kontext

`gh-board.py` schließt an zwei Stellen ein Issue: `cmd_finalize` (Spec finalisieren) und `cmd_set_status` beim Wert `Done` (u.a. der Verwerfen-Pfad in `refinement`). Beide setzen zuerst die Board-Spalte auf `Done` und rufen danach `close_issue()`.

Auf dem Board ist der native Workflow `Auto-close issue` aktiv — bewusst so entschieden in ADR 0046, Abschnitt 5, mit der Begründung, er schreibe nur den offen/geschlossen-Zustand des Issues und feuere ausschließlich als Reaktion auf ein `Done`, "dem es ohnehin ein eigenes `gh issue close` folgen lässt". Genau diese Nebenannahme trägt nicht: Der Workflow ist schneller als der eigene Folgeaufruf. Das `gh issue close` trifft ein bereits geschlossenes Issue und quittiert das als Fehlschlag:

```
{"error": "gh-Aufruf fehlgeschlagen (gh issue close 209): GraphQL: Could not close the issue. (closeIssue)"}
```

Der Zielzustand — Spalte `Done`, Issue geschlossen, Spec-Statuszeile auf `Implemented` — ist zu diesem Zeitpunkt vollständig erreicht. Die Fehlermeldung ist trotzdem teuer, weil `ship-feature` einen `{"error": ...}` an dieser Stelle vorschriftsgemäß so behandelt, dass die bereits korrekt geschriebene Statuszeile verworfen und der Aufruf wiederholt wird — die Wiederholung scheitert dann erneut, diesmal zusätzlich am Datei-Status `Implemented`. Jeder Feature-Abschluss braucht dadurch eine Handbeurteilung.

`Auto-close issue` ist dabei nicht die einzige Quelle des Zustands "schon geschlossen". Der Issue-Zustand war nie exklusiv unter Tool-Kontrolle (ADR 0046, Abschnitt 5): Daniel schließt Issues von Hand, und im Ausnahmepfad aus ADR 0042/0046 (Merge vor der Finalisierung) schließt GitHub das Issue selbst über das Closing-Keyword — der nachgezogene `finalize`-Aufruf träfe dieselbe Situation.

## Entscheidung

### 1. Maßstab ist der Zielzustand, nicht die Urheberschaft dieses Aufrufs

Für die schreibenden Board-Operationen gilt: Erfolg heißt "der gewünschte Zustand liegt vor", nicht "dieser Aufruf hat ihn hergestellt". Ein Issue, das bereits geschlossen ist, erfüllt die Zusicherung von `close_issue()` vollständig — unabhängig davon, wer es geschlossen hat.

Die Erfolgsmeldung ist in beiden Fällen identisch: Weder `cmd_finalize` noch `cmd_set_status` bekommen ein zusätzliches Feld ("war schon geschlossen"). Der aufrufende Ablauf soll diesen Unterschied nicht kennen müssen, weil er für ihn keinen Unterschied macht — eine Unterscheidung im Rückgabewert wäre eine Fallunterscheidung, die jeder Aufrufer nur wieder wegwerfen müsste.

### 2. Unterschieden wird durch Nachprüfen des Zustands, nicht am Fehlertext

`close_issue()` reicht einen Fehlschlag von `gh issue close` nicht mehr direkt weiter, sondern fragt einmalig den tatsächlichen Issue-Zustand ab (`gh issue view <NNN> --json state`):

- Zustand `closed` → Erfolg, der Fehlschlag wird verworfen.
- Zustand `open` → der **ursprüngliche** Fehler wird unverändert weitergereicht.
- Die Prüfung selbst schlägt fehl (nicht existierendes Issue, fehlende Berechtigung, Dienst nicht erreichbar) → ebenfalls der ursprüngliche Fehler, verkettet mit dem Fehler der Prüfung als Ursache.

Bewusst **nicht** entschieden wurde eine Heuristik auf den Fehlertext (`"Could not close the issue"`). Diese Meldung ist eine undokumentierte, jederzeit einseitig änderbare GraphQL-Formulierung, und sie ist nicht trennscharf: Sie steht ebenso für Fälle, die keinen Erfolg bedeuten. Ein Textmuster würde also genau in die gefährliche Richtung irren — echten Fehlschlag als Erfolg quittieren. Der Zustandsabruf ist dagegen die Quelle, um die es eigentlich geht. Dieselbe Abwägung wie in ADR 0046, Abschnitt 3 (GitHubs eigenes Ergebnis statt eines nachgebildeten Parsers), nur eine Ebene tiefer.

Die Prüfung läuft **nach** dem Fehlschlag, nicht als Vorabprüfung. Eine Vorabprüfung ("erst lesen, dann ggf. schließen") kostet in jedem `Done`-Pfad einen zusätzlichen Aufruf und beseitigt das Problem trotzdem nicht: Zwischen Lesen und Schließen bleibt genau das Rennen offen, um das es hier geht — der Board-Workflow feuert asynchron auf das `Done`, das unmittelbar davor gesetzt wurde. Die Prüfung nach dem Fehlschlag deckt beide Reihenfolgen ab und kostet im Regelfall nichts.

### 3. Dieselbe Regel für die Spec-Statuszeile in `cmd_finalize`

`cmd_finalize` bricht heute ab, wenn der Datei-Status nicht `Accepted` ist. Diese Prüfung bleibt — mit einer eng gefassten Ausnahme: Steht in der Spec-Datei bereits **exakt die Zeile, die dieser Aufruf schreiben würde** (`Implemented ([PR #MMM](url))` mit demselben aufgelösten PR), ist der Zielzustand erreicht, und der Aufruf läuft ohne Fehler weiter (Board `Done`, Issue schließen, identischer Rückgabewert wie beim ersten Lauf).

Jeder andere abweichende Datei-Status bricht unverändert ab, insbesondere `Implemented` mit einem **anderen** PR — das ist kein erreichter Zielzustand, sondern ein Hinweis auf die falsche Spec-Nummer oder einen echten Konflikt, und darf nicht stillschweigend überschrieben werden.

Damit ist ein `finalize`-Aufruf als Ganzes wiederholbar, statt nur seine Einzelschritte. Der bisher nötige Rückbau der bereits geschriebenen Statuszeile vor einem zweiten Versuch (`git checkout -- specs/features/NNNN-*.md`, dokumentiert in `ship-feature` und `github-board`) entfällt für diesen Fall.

### 4. `Auto-close issue` bleibt aktiv, die Robustheit liegt im Code

Die naheliegende Alternative — den Workflow `Auto-close issue` im Projekt-UI abschalten, damit nur noch `gh-board.py` Issues schließt — wird verworfen:

- Sie behebt nur eine von mehreren Quellen. Ein von Hand geschlossenes Issue und der Ausnahmepfad "Merge vor der Finalisierung" (dort schließt das Closing-Keyword das Issue) erzeugen dieselbe Situation und blieben unbehandelt.
- Sie verlegt die Korrektheit in eine manuelle, nicht versionierte, nicht testbare Board-Einstellung, die jederzeit unbemerkt zurückgedreht werden kann. Die Idempotenz im Code ist dagegen an derselben Stelle wie die Operation, in `FakeGh` prüfbar und überlebt jede Board-Konfiguration.
- `Auto-close issue` ist zudem ein nützliches Netz für den Fall, dass das eigene `close` gar nicht erst zustande kommt.

Die Entscheidung aus ADR 0046, Abschnitt 5, bleibt damit bestehen; korrigiert wird nur ihre dort mitgeführte Annahme, das eigene `gh issue close` folge dem Workflow folgenlos.

## Begründung

- **Idempotenz statt Ausnahmebehandlung beim Aufrufer:** Der Alternativweg wäre, `ship-feature` beizubringen, diese eine Fehlermeldung zu erkennen und zu ignorieren. Das verteilt Wissen über eine `gh`-Fehlerformulierung in eine Prosa-Datei, die niemand testet, und macht die Meldung zu einer Schnittstelle, die sie nicht ist. Die Regel gehört dorthin, wo die Operation stattfindet.
- **Zustandsabruf statt Textmuster:** Ein Textmuster kann nur falsch-positiv oder falsch-negativ irren; falsch-positiv (echter Fehlschlag gilt als Erfolg) ist hier die teure Richtung, weil sie einen offenen Zielzustand als erledigt meldet. Der Zustandsabruf schließt diese Richtung per Konstruktion aus.
- **Ursprünglichen Fehler erhalten:** Scheitert die Nachprüfung selbst, wäre ihre Meldung ("Issue-Zustand nicht lesbar") die weniger aussagekräftige. Der erste, unmittelbar zur beabsichtigten Operation gehörende Fehler bleibt deshalb die gemeldete Ursache.
- **Enge Ausnahme statt aufgeweichtem Statusgate:** Die `Accepted`-Prüfung in `cmd_finalize` verhindert, dass eine nie freigegebene oder eine fremde Spec finalisiert wird — das bleibt wertvoll. Der Vergleich gegen die vollständige Zielzeile (inklusive PR-Nummer) unterscheidet "schon fertig, exakt so" trennscharf von "steht auf etwas anderem" und gibt von diesem Wert nichts auf.
- **Ein Prinzip, zwei Anwendungen:** Beide Änderungen folgen derselben Regel (Abschnitt 1). Ein Werkzeug, das an einer Stelle zielzustands-idempotent ist und an der nächsten nicht, erzeugt genau die Handbeurteilung wieder, die hier abgeschafft wird.
- **Bewusst in Kauf genommen:** Fehlt die Schreibberechtigung und ist das Issue aus anderem Grund bereits geschlossen, meldet `close_issue()` Erfolg, obwohl der Aufruf nichts bewirkt hat. Das ist konsistent mit Abschnitt 1 — der zugesicherte Zustand liegt vor —, und ein fehlendes Recht fällt spätestens bei der nächsten schreibenden Operation auf, die tatsächlich etwas ändern muss.

## Konsequenzen

- **`scripts/gh-board.py`:** `GhBoard` bekommt eine lesende Methode für den Issue-Zustand (`gh issue view <NNN> --json state`); `close_issue()` wertet einen Fehlschlag gegen diesen Zustand aus, statt ihn direkt zu propagieren. `cmd_finalize` lässt zusätzlich zum Datei-Status `Accepted` den Fall "bereits exakt diese Zielzeile" zu. `cmd_set_status` bleibt unverändert — es profitiert allein über `close_issue()`.
- **`scripts/tests/test_gh_board.py`:** `FakeGh` bekommt einen Issue-Zustand (offen/geschlossen), beantwortet `gh issue view --json state` und lässt `gh issue close` auf einem bereits geschlossenen Issue mit der real beobachteten Meldung scheitern. Neue Fälle für beide Aufrufwege, für den weiterhin gemeldeten echten Fehlschlag, für die fehlgeschlagene Nachprüfung und für die Wiederholbarkeit.
- **`.claude/skills/ship-feature/SKILL.md` / `.claude/skills/github-board/SKILL.md`:** Der Hinweis, ein wiederholter `finalize`-Aufruf verlange erst den Rückbau der Statuszeile bzw. sei nur bei Datei-Status `Accepted` wiederholbar, trifft nicht mehr zu und wird korrigiert. Die übrige `{"error": ...}`-Behandlung (Meldung unverändert weitergeben, nicht umgehen) bleibt für echte Fehler unverändert.
- **Kein manueller Rollout-Schritt.** Insbesondere bleibt die Board-Workflow-Konfiguration aus ADR 0046, Abschnitt 5, unverändert (`Item closed` aus, `Auto-close issue` an).
- **Kein Effekt auf `docs/architecture.md`/`docs/setup.md`/Root-`README.md`** — reines Entwickler-/Prozess-Tooling ohne Bezug zur Laufzeitarchitektur oder zum Datenmodell der Anwendung, gleiche Einordnung wie ADR 0037/0042/0043/0045/0046.
- **ADR 0046 bleibt unverändert `Accepted`** und wird nicht editiert; ihre Entscheidung zu `Auto-close issue` wird hier bestätigt, nicht abgelöst.
- Sollte künftig doch der Weg "genau ein Schreiber des Issue-Zustands" gewählt werden (Board-Workflow abschalten, Idempotenz zurückbauen), ist das architekturrelevant und braucht eine neue ADR, die diese hier als "Superseded" markiert.
