# 0045 - `spec-writer` legt den Feature-Branch samt Spec-Commit an, `developer` übernimmt ihn statt neu zu branchen — ein PR pro Story

**Status:** Accepted
**Datum:** 2026-08-30
**Bezug:** GitHub-Issue [`#269`](https://github.com/TheRealKoller/photosort/issues/269) ("Ein Feature-Branch/PR statt getrenntem Spec-PR pro Story"), `.claude/skills/spec-writer/SKILL.md` (Schritt 4), `.claude/agents/developer.md` (Schritt 0), `.claude/skills/ship-feature/SKILL.md` (Schritt 6), beobachteter Altfall bei Issue [`#218`](https://github.com/TheRealKoller/photosort/issues/218) (separater Spec-Branch + eigener Spec-PR, gefolgt von einem zweiten, unabhängigen Feature-Branch für die Implementierung), `architect`-Konsultation für Story #269 am 2026-08-30.

## Kontext

`developer.md`, Schritt 0, legt bislang für jede Umsetzung einen komplett neuen Feature-Branch von einem aktuellen `main` an ("Der gesamte Rest des Ablaufs passiert auf diesem Branch"). Das erzwingt für jedes Issue ohne bereits vorhandene, unabhängig entstandene Spec einen eigenen, rein dokumentarischen Zwischen-PR nur für die neue Spec-Datei — sie muss auf `main` liegen, bevor `developer` von dort abzweigen kann. Historisch lief das bei vergleichbaren Prozess-Features (Issue #240/PR #261, Issue #262/PR #267) anders: Spec-Commit und Implementierung liefen dort auf einem einzigen Branch/PR, vermutlich weil das noch in einer durchgehenden Session vor dem heutigen `developer`-Subagenten-Mechanismus passierte. Der bei Issue #218 beobachtete Ablauf (separater Spec-Branch + eigener Spec-PR, gefolgt von einem zweiten, unabhängigen Feature-Branch) ist der unerwünschte Regelfall, den diese ADR beendet.

Zwei Randbedingungen bestimmen die Lösung:

1. `developer` ist ein per Agent-Tool gestarteter Subagent ohne Gedächtnis über vorherige Aufrufe — er kennt ausschließlich das, was im Start-Prompt steht.
2. Push und PR-Eröffnung passieren weiterhin erst ganz am Ende, durch `ship-feature` (bereits bestätigter Rahmen, keine offene Frage dieser ADR) — der Branch existiert also während der gesamten Spec- und Implementierungsphase ausschließlich lokal.

## Entscheidung

### 1. `spec-writer` legt den Feature-Branch selbst an, direkt mit dem Spec-Commit

`spec-writer`, Schritt 4, bekommt eine Vorbedingung vor dem Anlegen der Spec-Datei: Git-Ausgangszustand prüfen (uncommittete Änderungen klären, analog zu `developer.md` Schritt 0 Punkt 3 — nicht stillschweigend überschreiben), von einem aktuellen `main` abzweigen (`git fetch`/`pull`, analog zu `developer.md` Schritt 0 Punkt 4), und einen neuen Feature-Branch anlegen:

```
git checkout -b feature/<NNNN>-<kurzer-slug>
```

`NNNN` ist die vierstellige Spec-/Issue-Nummer aus Schritt 0, `<kurzer-slug>` derselbe Slug wie im Dateinamen der Spec (`specs/features/NNNN-<kurzer-slug>.md`) — ein einziges, deterministisches Namensschema für beide Anlegestellen (hier und den unveränderten Fallback in `developer.md`, Abschnitt 2). Die neue Spec-Datei wird direkt auf diesem Branch angelegt und lokal committet (Conventional Commits, z.B. `docs(specs): Spec NNNN anlegen (Issue #NNN)`) — kein Push, keine PR-Eröffnung an dieser Stelle.

### 2. Übergabe an die Orchestrator-Session ist reiner Freitext, kein neuer Mechanismus

`spec-writer` läuft als Skill in derselben Session, die später `developer` per Agent-Tool aufruft — es gibt keine zwei getrennten, gedächtnislosen Prozesse, die einen dedizierten Übergabekanal (Datei, `SendMessage`) bräuchten. Der angelegte Branch-Name wird im Abschlussbericht von `spec-writer` explizit genannt; die Session, die anschließend `developer` startet, nimmt ihn wortgleich in den Start-Prompt auf. Das ist strukturell identisch mit jeder anderen Spec-Referenz, die die Hauptsession schon heute an `developer` weiterreicht (z.B. die Spec-Nummer selbst) — keine neue Kategorie von Übergabe.

### 3. `developer` übernimmt einen explizit genannten Branch, statt selbst zu erkennen oder zu raten

`developer.md`, Schritt 0, unterscheidet ab jetzt zwei Fälle, rein anhand dessen, was im Start-Prompt steht — `developer` versucht an keiner Stelle, selbst zu erkennen, ob ein passender Branch schon existiert (er hat dafür keine zuverlässige Grundlage, ein Subagent ohne Vorwissen könnte allenfalls raten):

- **Branch-Name im Prompt genannt:** `git checkout <branch>`, kein neuer Branch. Das deckt den Regelfall ab, seit `spec-writer` den Branch samt Spec-Commit selbst anlegt (Abschnitt 1).
- **Kein Branch-Name genannt:** wie bisher ein neuer Feature-Branch von einem aktuellen `main` (Fallback für ältere Specs ohne Vorab-Branch, oder einen Ablauf, der `spec-writer` nicht durchlaufen hat — Akzeptanzkriterium 3 der Story).

Der Fallback bleibt damit sauber, weil er nicht erkannt, sondern lediglich das Fehlen einer expliziten Angabe ist — keine Heuristik, kein Raten.

### 4. `ship-feature`, Schritt 6, braucht keine inhaltliche Änderung

Der Push (`git push -u origin <branch>`) und die PR-Erstellung sind unabhängig davon, ob der lokale Branch von `spec-writer` (mit vorherigem Spec-Commit) oder von `developer` selbst (ohne) angelegt wurde — in beiden Fällen liegt zum Zeitpunkt von Schritt 6 ein lokal vollständiger, committeter Branch vor, der als Ganzes gepusht wird. `git diff --name-only main...HEAD` (Schritt 2/Verifikation) erfasst in beiden Fällen korrekt alle Commits inklusive des Spec-Commits, sofern er in diesem Branch entstanden ist — das ist im neuen Regelfall sogar erwünscht, da Spec und Implementierung jetzt bewusst derselbe PR sind.

## Begründung

- **Anlegepunkt bei `spec-writer` statt eines dritten, neuen Koordinationsmechanismus:** `spec-writer` kennt Spec-Nummer und -Titel (für den Branch-Namen) bereits an der Stelle, an der die Datei entsteht — ihn dort anlegen zu lassen vermeidet jede zusätzliche Übergabe-Infrastruktur zwischen zwei sonst unabhängigen Anlegepunkten.
- **Explizite Prompt-Angabe statt Erkennungslogik in `developer`:** ein gedächtnisloser Subagent kann einen bereits vorhandenen, zur aktuellen Aufgabe passenden Branch nicht zuverlässig von einem zufällig ähnlich benannten unterscheiden — die Verantwortung für "welcher Branch ist gemeint" bleibt bei der Session, die sowieso beide Aufrufe orchestriert, statt sie implizit an eine Heuristik im Subagenten zu delegieren.
- **Kein Push/keine PR-Eröffnung bei `spec-writer`:** hält die bereits bestätigte Rahmenentscheidung (Push/PR ausschließlich am Ende, durch `ship-feature`) konsequent ein — der neue Branch existiert bis zum Ende des gesamten Ablaufs ausschließlich lokal, exakt wie ein von `developer` selbst angelegter Branch es heute schon tut.
- **Gleiches Namensschema an beiden Anlegestellen:** vermeidet zwei parallel gepflegte Konventionen für denselben Zweck; der Fallback in `developer.md` bleibt dadurch ein reiner Spezialfall derselben Regel, keine eigenständige zweite Regel.

## Konsequenzen

- **`.claude/skills/spec-writer/SKILL.md`:** Schritt 4 bekommt eine neue Vorbedingung (Git-Ausgangszustand prüfen, von aktuellem `main` abzweigen, Feature-Branch anlegen nach dem Schema `feature/<NNNN>-<kurzer-slug>`) sowie eine explizite lokale Committierung der neuen Spec-Datei auf diesem Branch. Der Abschlussbericht nennt den Branch-Namen explizit für die Weitergabe an den späteren `developer`-Aufruf.
- **`.claude/agents/developer.md`:** Schritt 0, Punkt 4, wird von "Feature-Branch anlegen" zu "Feature-Branch übernehmen oder neu anlegen" umformuliert — Fallunterscheidung anhand einer expliziten Prompt-Angabe, kein eigenes Erkennen.
- **`.claude/skills/ship-feature/SKILL.md`:** keine inhaltliche Änderung an Schritt 6 nötig (siehe Abschnitt 4) — optionale klarstellende Fußnote, dass der Branch zu diesem Zeitpunkt bereits vor `developer`s Start existiert haben kann.
- **Kein Effekt auf `docs/architecture.md`/`docs/setup.md`/Root-`README.md`/`docs/ai-workflow.md`** — reines Entwickler-/Prozess-Tooling ohne PhotoSort-System-/Datenmodell-Bezug und ohne Änderung an der in `docs/ai-workflow.md` beschriebenen Schritt-Tabelle (sie beschreibt bewusst nicht die interne Branch-Mechanik), identische Einordnung wie ADR 0037/0042.
- **`specs/README.md`:** unverändert — Nummerierungsschema und Spec-Lebenszyklus sind von dieser ADR nicht betroffen.
- Ein späterer Wechsel dieses Modells (z.B. doch ein dedizierter Übergabemechanismus statt Freitext, oder eine erneute Trennung von Spec- und Implementierungs-PR) bleibt architekturrelevant und braucht eine neue, diese ADR als "Superseded" markierende ADR.
