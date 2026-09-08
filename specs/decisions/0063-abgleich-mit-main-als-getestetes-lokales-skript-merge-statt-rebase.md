# 0063 - Der Abgleich mit `main` ist ein getestetes lokales Skript, und er merged statt zu rebasen

**Status:** Accepted
**Datum:** 2026-09-08
**Bezug:** [GitHub-Issue #338](https://github.com/TheRealKoller/photosort/issues/338), [`features/0338-abgleich-mit-main-vor-der-freigabe.md`](../features/0338-abgleich-mit-main-vor-der-freigabe.md), `.claude/skills/ship-feature/SKILL.md` (Schritt 6 und 8), `.claude/agents/developer.md`

**Berührt außerdem (keine Ablösung):** [`decisions/0057-board-lebenszyklus-nativ-statt-eigenbau.md`](./0057-board-lebenszyklus-nativ-statt-eigenbau.md) und [`decisions/0061-ein-ort-fuer-jeden-github-zugriff-wege-in-fester-reihenfolge.md`](./0061-ein-ort-fuer-jeden-github-zugriff-wege-in-fester-reihenfolge.md). Beide bleiben unverändert in Kraft. Ihr Verbot eines Werkzeugs gilt dem **GitHub-Zugriff** und nur ihm; Abschnitt 1 dieser ADR zieht die Grenze ausdrücklich nach, damit aus „`github-access` bleibt Text" nicht stillschweigend „im Ablauf gibt es keine Skripte mehr" wird. [`decisions/0045-spec-writer-legt-feature-branch-an-ein-pr-pro-story.md`](./0045-spec-writer-legt-feature-branch-an-ein-pr-pro-story.md) (Abzweig von aktuellem `main`) und [`decisions/0042-pre-merge-finalisierung-statt-nachzieh-pr.md`](./0042-pre-merge-finalisierung-statt-nachzieh-pr.md) (Finalisierung gebündelt mit dem letzten Push) bleiben gültig und bekommen mit dieser ADR ihre Fortsetzung am anderen Ende des Ablaufs.

## Kontext

Der Ablauf zweigt den Feature-Branch von einem aktuellen `main` ab (ADR 0045, `spec-writer` Schritt 4) und zieht danach an keiner Stelle mehr nach. Zwischen Abzweig und Freigabe liegt aber die gesamte Umsetzungs-, Review- und Copilot-Runde — im Regelfall Stunden bis Tage. Läuft `main` in dieser Zeit weiter, steht Daniel vor einem Pull Request, der inhaltlich fertig ist und trotzdem nicht freigegeben werden kann. Der Blocker hat mit der Änderung nichts zu tun; es fehlt allein der aktuelle Stand.

Drei Eigenschaften des Repositories bestimmen den Lösungsraum, und alle drei sind am Bestand nachgeprüft:

**Erstens squasht das Repository beim Merge** (`COMMIT_MESSAGES` + `COMMIT_OR_PR_TITLE`). Die Historie von `main` enthält deshalb **keinen einzigen Merge-Commit** (`git log --merges main` ist leer), und der Body eines Squash-Commits trägt sämtliche Commit-Nachrichten des Branches als Aufzählung — nachprüfbar am zuletzt gemergten PR #351. release-please liest genau diesen Body: Die Squash-Titel der letzten Releases sind überwiegend **nicht** konventionell (`Projekte löschen mit Namensbestätigung (Spec 0044) (#351)`), und Releases entstehen trotzdem. Was auf dem Feature-Branch an Commit-Nachrichten liegt, landet also in der Release-Auswertung. Ein Abgleich, der eine Nachricht hinterlässt, muss sich dazu verhalten.

**Zweitens hängt die gesamte Review-Phase an `git diff main...HEAD`** — sechs Stellen (`ship-feature` Schritt 2 und 5, `review`, und die vier `review-*`-Perspektivskills). Die Drei-Punkt-Form vergleicht gegen die **Merge-Basis**, und die Merge-Basis wird aus dem **lokalen** `main`-Ref gebildet. Zieht ein Abgleich `origin/main` in den Branch, ohne den lokalen `main`-Ref mitzuziehen, bleibt die Merge-Basis auf dem alten Stand stehen, und `main...HEAD` liefert ab da den Feature-Diff **plus** alles, was zwischenzeitlich auf `main` passiert ist. Jede Review-Perspektive bekäme fremde Dateien vorgelegt. Das ist keine theoretische Feinheit, sondern der wahrscheinlichste Weg, diese Story falsch zu bauen.

**Drittens sind die Akzeptanzkriterien 3, 5 und 6 Verhaltensaussagen**, keine Formulierungen: „geschieht nichts", „wird erneut geprüft", „bricht ab". `CLAUDE.md` verlangt für neue Funktionalität Tests, und der einzige Prüfer, den reiner Skill-Text zulässt, ist ein statischer Textprüfer — er belegt, dass ein Satz dasteht, nie, dass das beschriebene Verhalten eintritt. Das Repository unterhält solche Textprüfer bewusst (`scripts/tests/test_*_in_skills.py`) und weiß aus ihren Docstrings sehr genau, was sie **nicht** zusichern.

## Entscheidung

### 1. Der Abgleich ist ein eigenständiges, getestetes Skript: `scripts/merge-main-into-branch.sh`

Der Abgleich läuft nicht als Ablauf-Text im Skill, sondern als aufrufbares Skript mit definierten Exit-Codes, das `ship-feature` an beiden Zeitpunkten aufruft. Es nimmt **keine Argumente**: `origin` und `main` stehen als Literale darin, gearbeitet wird im aktuellen Repository auf dem aktuell ausgecheckten Branch. Es kann damit nicht auf ein anderes Ziel gerichtet werden.

**Warum die Präzedenz aus ADR 0057/0061 hier nicht trägt.** Das gelöschte Board-Werkzeug ist nicht daran gescheitert, dass es ein Werkzeug war, sondern an zwei benannten Gründen: Es kapselte eine ID-Auflösungsschicht, die `gh` 2.97 überflüssig gemacht hatte („ein Wrapper um zwei konstante Argumente"), und — der tragende Grund in ADR 0061, Abschnitt 1 — **ein Werkzeug in einem Subprozess erreicht die MCP-Werkzeuge der Session nicht**, kann also den Wegewechsel, um den es dort geht, gar nicht ausführen. Beide Gründe sind hier gegenstandslos: `git` ist ein Prozess und nichts anderes, es gibt keinen zweiten Weg zu ihm, keine Session-Werkzeuge, keine Wegereihenfolge. Und gekapselt wird kein konstantes Argument, sondern eine Folge mit Verzweigung, Vorbedingungen und drei unterscheidbaren Ausgängen.

Der Unterschied lässt sich als Regel formulieren, und sie ist die eigentliche Entscheidung dieses Abschnitts: **Ein GitHub-Zugriff bleibt Text, weil sein Weg von der Session abhängt. Eine rein lokale, deterministische Befehlsfolge darf ein Skript sein, wenn ihr Verhalten prüfbar ist.**

**Was das Skript einbringt, was Text nicht kann:** Gegen ein Skript sind AK 3/5/6 mit echten temporären Git-Repositories testbar (`git init`, ein bares „origin", ein Feature-Branch) — No-Op, sauberer Merge, Konflikt, jede Vorbedingung. AK 4 („schreibt keine bereits veröffentlichten Commits um") wird sogar zu einer *beweisbaren* Zusicherung statt zu einer Absichtserklärung: Der Test hält fest, dass der Commit vor dem Lauf danach ein Vorfahre des neuen Kopfes ist (`git merge-base --is-ancestor`). Kein Textprüfer der Welt sagt das zu.

Sprache ist Bash, wie bei den beiden bestehenden Shell-Skripten in `scripts/`. Die Tests liegen als pytest unter `scripts/tests/` und laufen im bestehenden CI-Job `demo-scripts`; sie rufen das Skript als Unterprozess auf, weil der Prüfgegenstand die Exit-Codes und der Zustand des Repositories sind — dieselbe Testbauart hätte auch eine Python-Fassung, die Sprache entscheidet hier nichts.

### 2. Merge, nie Rebase — genau ein Merge-Commit mit fester `chore:`-Nachricht

Der Abgleich ist `git merge --no-ff --no-edit -m "<feste Nachricht>" main`. Kein `rebase`, kein `commit --amend`, kein `push --force`, kein `reset --hard`. Das folgt zwingend aus AK 4: Ein Rebase schreibt veröffentlichte Commits um, und ein Force-Push darauf hängt die Inline-Kommentare und Threads des laufenden Reviews an Commits, die es nicht mehr gibt.

Das `--no-ff` ist nicht Geschmack: Es sichert zu, dass der bisherige Kopf des Feature-Branches **immer** erster Elternteil des neuen Kopfes ist, auch in dem Sonderfall, in dem der Branch vollständig in `main` enthalten wäre. Ohne es könnte ein Vorspulen den Feature-Branch stillschweigend auf `main` schieben und den Pull Request leeren.

Die Merge-Nachricht lautet fest und einzeilig:

```
chore: Stand von main in den Feature-Branch übernehmen
```

Sie ist konventionell (Konvention aus `CLAUDE.md`) und trägt den Typ `chore`, den release-please in seinen Vorgabe-Sektionen ausblendet: kein Changelog-Eintrag, keine Versionsanhebung — AK 8. Sie nennt bewusst **keinen** Commit-Hash und keine Konfliktliste; welcher Stand übernommen wurde, steht bereits im zweiten Elternteil des Merge-Commits, und jede zusätzliche Zeile stünde später im Body des Squash-Commits. Was bleibt, ist genau eine ausgeblendete Zeile dort — das ist die verbleibende Spur, und sie ist der Preis dafür, veröffentlichte Commits nicht anzufassen.

### 3. Der lokale `main`-Ref wird mitgezogen, sonst lügt der Review-Diff

Geholt wird mit `git fetch origin main:main` — das spult den **lokalen** `main`-Ref auf `origin/main` vor, ohne ihn auszuchecken, und schlägt fehl, wenn das kein Vorspulen wäre (`main` wurde umgeschrieben; ein Fall für Daniel, nicht für eine Korrektur nebenbei). Erst danach wird gemerged, und zwar `main`, nicht `origin/main`.

Damit bleibt die Merge-Basis nach dem Abgleich exakt der übernommene `main`-Stand, und `git diff main...HEAD` zeigt weiterhin genau die Änderungen dieses Branches — an allen sechs Stellen, die diese Form benutzen, ohne dass eine davon angefasst werden müsste. Der Kontext oben beschreibt, was ohne diesen Punkt passierte: Die Review-Perspektiven bekämen fremde Dateien vorgelegt und meldeten Findings zu Code, den dieser Branch nie berührt hat.

### 4. Drei Ausgänge, drei Exit-Codes — und der No-Op wird gerechnet, nicht gelesen

| Exit | Bedeutung | Zustand danach |
|---|---|---|
| `0` | `main` ist bereits enthalten | unverändert; **keine Ausgabe** |
| `10` | `main` sauber übernommen | ein neuer Merge-Commit, Arbeitsverzeichnis sauber |
| `20` | Konflikt (**mindestens ein Pfad unmerged**, siehe Nachtrag) | Merge steht offen (`MERGE_HEAD`), Konfliktpfade auf stdout |
| alles andere | Vorbedingung/Umgebung | unverändert |

Der No-Op-Fall wird mit `git merge-base --is-ancestor main HEAD` entschieden, **bevor** ein `git merge` überhaupt abgesetzt wird — nicht an der Ausgabe „Already up to date" erkannt. Ausgabetexte von `git` sind übersetzbar und formulierungsabhängig; die Vorfahren-Frage ist eine Plumbing-Auskunft mit Exit-Code. Weil in diesem Fall gar nicht gemerged wird, kann auch unter keiner Git-Konfiguration ein leerer Commit entstehen (AK 3). Und weil das Skript dabei nichts ausgibt, hat der Ablauf nichts zu berichten — „keine Meldung" ist eine Eigenschaft des Skripts, keine Disziplin des Aufrufers.

Vorbedingungen, die zu „alles andere" führen und den Ablauf anhalten: unsauberes Arbeitsverzeichnis, `main` selbst ausgecheckt, kein `origin`, fehlgeschlagener `fetch`, `main` nicht vorspulbar. Das Skript **pusht nie** und checkt nie `main` aus (AK 7).

### 5. Wer merged, wer auflöst, wer prüft

`ship-feature` (Hauptsession) ruft das Skript auf — reines lokales `git`, wie `git status`/`git push` dort ohnehin. Was danach passiert, hängt am Exit-Code, und die Rollenteilung aus `ship-feature` Schritt 5 („kein eigener erneuter Testlauf durch den Orchestrator") bleibt unangetastet:

- **`0`:** weiter, ohne jede Meldung.
- **`10` und `20`:** per `SendMessage` an den weiterhin offenen `developer`-Subagenten. Bei `20` löst er den bereits offen stehenden Merge auf und schließt ihn mit `git add <genau die Konfliktpfade>` + `git commit --no-edit --cleanup=strip` ab (siehe Nachtrag) — die Nachricht aus Punkt 2 liegt dafür in `MERGE_MSG` bereit, sie wird an keiner zweiten Stelle wiederholt. In **beiden** Fällen läuft danach sein Schritt 4 (abschließender Qualitätscheck) vollständig.

**Auch der saubere Merge (`10`) löst den Qualitätscheck aus.** AK 5 verlangt ihn wörtlich nur für den Konfliktfall, AK 3 verbietet ihn wörtlich nur für den No-Op — aber ein textuell konfliktfreier Merge ist kein fachlich konfliktfreier: Eine Umbenennung auf `main` und ihr Aufrufer im Feature-Branch stehen an verschiedenen Stellen und kollidieren für `git` nie. Der Branch enthielte dann Code, gegen den nie ein Test gelaufen ist, die CI färbte sich nach dem Push rot, und AK 9 („ein vollständig durchlaufener Ablauf hinterlässt einen freigabefähigen Pull Request") wäre verfehlt — nur mit einem anderen Blocker als vorher.

**Der `developer`-Agent bekommt dafür einen eigenen Folgeauftrag mit zwei eigenen Ankern**, nicht den bestehenden „Findings beheben": Es gibt keine Findings-Liste, und ein Bericht `## Abschlussbericht (Folgeauftrag: Findings behoben)` behauptete etwas, das nicht stattgefunden hat. Die Anker sind `## Abschlussbericht (Folgeauftrag: main-Abgleich)` und, für AK 6, `## Blockiert: main-Abgleich fehlgeschlagen`. Der zweite ist erforderlich, weil der bestehende „Blockiert"-Anker die Architektur-Konsultation auslöst; er bedeutet: Auflösung nicht sauber möglich oder Qualitätscheck bleibt rot, Merge zurückgenommen (`git merge --abort`), Branch im Stand vor dem Abgleich. `ship-feature` bricht daraufhin ab, pusht nichts und meldet an Daniel. Wie bisher gilt: Die Anker sind ausschließlich in `.claude/agents/developer.md` definiert; `ship-feature` verweist funktional darauf.

### 6. Zwei Aufrufzeitpunkte, und der zweite ist der tragende

- **Vor dem Eröffnen des Pull Requests** (`ship-feature` Schritt 6), **nach** dem Committen etwaiger Reste und **vor** dem Push — das Skript verlangt ein sauberes Arbeitsverzeichnis.
- **Vor der Freigabe** (`ship-feature` Schritt 8), als **erste** Handlung des Schritts, vor der Verknüpfungsprüfung und vor dem Setzen der Spec-Statuszeile. Der Merge-Commit, ein etwaiger Konflikt-Fix und der Finalisierungs-Commit gehen danach in **einem** Push hinaus — die Bündelungsregel aus ADR 0042 gilt unverändert und umfasst ab jetzt auch den Abgleich, damit kein zusätzlicher CI-Lauf entsteht.

Ein dritter Zeitpunkt (nach dem letzten Push, unmittelbar vor Daniels Merge) wird **nicht** eingeführt. Er existierte nicht als Zeitpunkt, den der Ablauf erreichen kann: Nach dem letzten Push endet der Lauf. Läuft `main` zwischen Push und Freigabe erneut weiter, bleibt ein Handgriff bei Daniel — bewusst offene Restlücke (AK 9).

## Begründung

Die Alternative — der Abgleich als reiner Ablauf-Text in `ship-feature`, wie der Rest des Schritts — wäre billiger und passte äußerlich besser zur Bewegung der letzten ADRs, die Werkzeuge aus dem Ablauf entfernt haben. Sie scheitert an einem Punkt, und der ist nicht verhandelbar: Sie kann AK 3, 5 und 6 nicht prüfen. Ein statischer Textprüfer belegte, dass in `ship-feature` ein Satz über den No-Op steht, und wäre auch dann grün, wenn jeder Lauf einen leeren Merge-Commit erzeugte. Das Repository weiß das über seine eigenen Textprüfer bereits sehr genau — ihre Docstrings sagen es selbst („Was diese Tests ausdrücklich NICHT zusichern"). Eine neue Zusicherung dieser Klasse einzuführen, obwohl der Gegenstand diesmal vollständig lokal, deterministisch und in einem temporären Repository nachstellbar ist, wäre die falsche Sparsamkeit.

Dass die Bewegung der letzten ADRs damit nicht umgekehrt wird, hängt an der Regel aus Abschnitt 1. `gh-board.py` war kein Skript zu viel, weil es ein Skript war, sondern weil es fremden Zustand kopierte und in einem Subprozess lag, der die Werkzeuge der Session nicht erreicht. Ein Skript, das `git merge` aufruft, hat keine dieser Eigenschaften — und es bringt die eine mit, die Text nie hat: Sein Verhalten kann fehlschlagen, bevor Daniel es merkt.

Rebase wurde nicht abgewogen, sondern ist durch AK 4 ausgeschlossen. Der Vollständigkeit halber, weil die Frage wiederkommt: Rebase hinterließe die sauberere Historie — und die ist in einem Repository, das ohnehin squasht, wertlos, weil die Historie des Branches beim Merge zu einer einzigen Zeile zusammenfällt. Der Preis wären verlorene Review-Threads an einem laufenden Pull Request. Teurer Kauf für nichts.

## Konsequenzen

- **Feature-Branches tragen ab jetzt Merge-Commits.** `main` bleibt merge-frei (Squash), aber `git log` auf einem Feature-Branch ist nicht mehr linear. Wer dort etwas sucht, braucht ggf. `--first-parent`.
- **Der Body eines Squash-Commits trägt bis zu zwei `chore:`-Zeilen mehr.** Sie sind in `CHANGELOG.md` unsichtbar und lösen keine Versionsanhebung aus. Fällt diese Zusicherung — etwa weil `changelog-sections` in `release-please-config.json` einmal `chore` sichtbar schaltet —, ist dieser Punkt nachzuziehen.
- **`git diff main...HEAD` bleibt an allen sechs Fundstellen korrekt**, aber nur, solange Abschnitt 3 gilt. Wer den `fetch` je auf `git fetch origin` ohne Refspec vereinfacht, bricht die Review-Runde still: Sie meldete Findings zu fremden Dateien, und nichts würde rot.
- **Ein abgebrochener Lauf kann ein Repository mit offenem Merge hinterlassen** (Exit `20`, danach `SendMessage`-Fehlschlag). Der Recovery-Abschnitt von `ship-feature` nimmt dafür einen Satz auf: erst `git merge --abort`, dann den neuen `developer`-Lauf starten. Das ist der bewusste Preis dafür, dass der Konflikt dort aufgelöst wird, wo er entsteht, statt den Merge zweimal auszuführen.
- **Die Tests brauchen eine Git-Identität im Unterprozess.** In CI ist keine konfiguriert; die Fixtures setzen `GIT_AUTHOR_*`/`GIT_COMMITTER_*` und legen ihre Repositories mit `git init -b main` an. Ohne das sind sie lokal grün und in CI rot — die klassische Falle dieser Testbauart, hier einmal benannt statt zweimal gefunden.
- **Der Ablauf hängt ab jetzt an einer Datei außerhalb von `.claude/`.** Verschwindet `scripts/merge-main-into-branch.sh`, scheitert `ship-feature` an einer sichtbaren Stelle mit einem Kommando-nicht-gefunden — nicht still. Dass die beiden Aufrufstellen im Skill erhalten bleiben (insbesondere die zweite, tragende aus AK 2), sichert eine kleine statische Prüfung ab; sie ist der einzige Teil dieser Story, für den ein Textprüfer das richtige Werkzeug ist.

## Nachtrag (2026-09-08): drei Präzisierungen aus der Konsultation von `test-engineer` und `security-engineer`

**Einordnung gegen die Unveränderlichkeitsregel aus [`specs/README.md`](../README.md):** Erstfassung und
Nachtrag dieser ADR sind am selben Tag im selben, noch nicht gemergten Pull Request entstanden — die
Entscheidung war zu keinem Zeitpunkt in `main` und hat damit nie den Zustand erreicht, den die Regel
schützt. Jede spätere Änderung an dieser Entscheidung geht den regulären Weg über eine neue ADR.

Alle drei sind **am laufenden `git` gemessen**, nicht abgeleitet, und je zweimal unabhängig
nachgestellt. Sie ändern keine Entscheidung dieser ADR, sondern schärfen drei Formulierungen, die in
der ursprünglichen Fassung ein falsches Verhalten zugelassen hätten. Die Messprotokolle stehen in
`specs/architecture/0002-testkonzept.md` und `specs/architecture/0003-securitykonzept.md`.

**1. Der Konflikt-Abschlusscommit braucht `--cleanup=strip`** (betrifft Abschnitt 2 und 5). `git`
hängt nach einem Konflikt eine `# Conflicts:`-Liste an `MERGE_MSG`. Ohne Editor-Durchlauf bleibt sie
im Commit-**Body** stehen und wandert in den Body des Squash-Commits — genau das Rauschen, das
Abschnitt 2 ausschließt („nennt bewusst keine Konfliktliste"). Gemessen an Git 2.43: `git commit
--no-edit` erzeugt eine dreizeilige Nachricht mit der Konfliktliste, `git commit --no-edit
--cleanup=strip` exakt die eine `chore:`-Zeile. Die Zusage aus Abschnitt 2 hängt damit am Flag, nicht
an der Absicht.

**2. Exit `20` verlangt mindestens einen Pfad im Konfliktzustand** (betrifft Abschnitt 4). „Merge-Exit
≠ 0" ist nicht gleich „Konflikt": Mit einem `pre-merge-commit`-Hook nachgestellt endet `git merge` mit
Exit 1, `MERGE_HEAD` **existiert**, und `git diff --name-only --diff-filter=U` liefert **null** Pfade
(dieselbe Signatur entsteht bei `commit.gpgsign` ohne Schlüssel). Ein Skript, das darauf `20` meldete,
schickte den `developer` Konfliktmarker suchen, die es nicht gibt, und `git commit --no-edit` schlösse
den vom Hook abgelehnten Merge stillschweigend ab. Regel: Ohne unmerged Pfad räumt das Skript auf
(`git merge --abort`) und endet in der Fehlerfamilie.

**3. „Keine Argumente" bindet das Ziel nicht — die Umgebung muss bereinigt werden** (betrifft
Abschnitt 1). Der Satz „kann nicht auf ein anderes Ziel gerichtet werden" trägt für die
Kommandozeile, nicht für die Umgebung: Mit gesetztem `GIT_DIR`/`GIT_WORK_TREE` meldet `git branch
--show-current` gemessen den Branch eines **anderen** Repositoriums, und über
`GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_0=core.hooksPath` wurde während `git merge` ein `post-merge`-Hook
aus einem beliebigen Verzeichnis ausgeführt. Das Skript setzt deshalb direkt nach `set -euo pipefail`
ein `unset` auf `GIT_DIR`, `GIT_WORK_TREE`, `GIT_COMMON_DIR`, `GIT_INDEX_FILE`,
`GIT_OBJECT_DIRECTORY`, `GIT_ALTERNATE_OBJECT_DIRECTORIES` und `GIT_CONFIG_COUNT`. Einordnung ohne
Überzeichnung: Wer diese Variablen setzen kann, hat bereits Codeausführung in derselben Sitzung — es
geht um Tiefenstaffelung und vor allem um Unfallschutz.

**Zur Konsequenz „Zustand danach: unverändert" bei nicht vorspulbarem `main`:** Gemessen gilt das für
den lokalen `main`-Ref, **nicht** für `refs/remotes/origin/main` — die Standard-Refspec aus
`.git/config` feuert parallel und aktualisiert die Tracking-Referenz zwangsweise mit. Für die
Review-Basis folgenlos (`main...HEAD` liest den lokalen Ref); nur nicht darauf bauen, dass der
Abbruchpfad seiteneffektfrei ist.
