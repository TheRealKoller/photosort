# 0075 - Der Abgleich mit `main` fasst den lokalen `main`-Ref nicht mehr an: Vergleichsbasis der Review-Phase ist `origin/main`

**Status:** Accepted
**Datum:** 2026-09-10
**Bezug:** [GitHub-Issue #365](https://github.com/TheRealKoller/photosort/issues/365), [`features/0365-abgleich-mit-main-aus-dem-arbeitsbaum.md`](../features/0365-abgleich-mit-main-aus-dem-arbeitsbaum.md), `scripts/merge-main-into-branch.sh`, `scripts/tests/test_merge_main_into_branch.py`, `scripts/tests/test_main_abgleich_verdrahtung.py`, die acht Fundstellen der Vergleichsbasis in `.claude/` (`ship-feature`, `review`, die fünf `review-*`-Skills, `developer.md`)

**Löst teilweise ab:** [`decisions/0063-abgleich-mit-main-als-getestetes-lokales-skript-merge-statt-rebase.md`](./0063-abgleich-mit-main-als-getestetes-lokales-skript-merge-statt-rebase.md), **Abschnitt 3** („Der lokale `main`-Ref wird mitgezogen, sonst lügt der Review-Diff") und die daran hängende Konsequenz-Aufzählung („`git diff main...HEAD` bleibt an allen sechs Fundstellen korrekt … Wer den `fetch` je auf `git fetch origin` ohne Refspec vereinfacht, bricht die Review-Runde still"). Alles Übrige von ADR 0063 bleibt unverändert in Kraft: der Abgleich als getestetes lokales Skript ohne Argumente (Abschnitt 1), Merge statt Rebase mit fester einzeiliger `chore:`-Nachricht und `--no-ff` (Abschnitt 2), die Ausgänge samt gerechnetem No-Op (Abschnitt 4), die Rollenteilung mit den beiden Ankern (Abschnitt 5) und die zwei Aufrufzeitpunkte (Abschnitt 6). Der Kern jener Entscheidung — **Skript statt Ablauftext, Merge statt Rebase** — wird hier nicht angetastet; abgelöst wird ausschließlich, **welcher Ref** dabei geschrieben und **gegen welchen Ref** danach verglichen wird.

## Kontext

Hintergrund-Läufe dieses Repositories arbeiten in einem eigenen Arbeitsbaum unter `.claude/worktrees/`, während der Haupt-Checkout nach jedem Merge `main` ausgecheckt hat — der Normalzustand, nicht der Sonderfall. In genau dieser Konstellation bricht der Abgleich ab.

**Gemessen am laufenden `git` 2.55.0** (Wegwerf-Repositorium mit barem `origin`, Haupt-Checkout auf `main`, verbundener Arbeitsbaum auf einem Feature-Branch; jede Zeile unten nachgestellt, nicht abgeleitet):

1. `git fetch origin main:main` aus dem verbundenen Arbeitsbaum endet mit **Exit 128**: „Anfordern in Branch 'refs/heads/main' verweigert, ausgecheckt in '…'". Die Verweigerung gilt dem Ref, nicht dem Verzeichnis — sie tritt auf, sobald `refs/heads/main` in *irgendeinem* Arbeitsbaum desselben Repositoriums ausgecheckt ist.
2. Das Skript bildet jeden Fehlschlag dieser Zeile auf Exit `30` ab und nennt drei Ursachen (Remote unerreichbar, dort kein `main`, `main` lokal nicht vorspulbar). Keine davon trifft zu. Die Meldung endet mit „Ein Fall fuer Daniel" — und ist damit die teuerste Sorte Fehlmeldung: Sie verbraucht die Eskalationsstufe für einen Fall, der ohne jedes Zutun weiterlaufen könnte.
3. `git fetch --quiet origin "+refs/heads/main:refs/remotes/origin/main"` läuft in derselben Lage durch (Exit 0). `refs/heads/main` bleibt danach byte-gleich, der Haupt-Checkout meldet `git status --porcelain` leer.
4. Nach `git merge --no-ff origin/main` zeigt `git diff --name-only origin/main...HEAD` **exakt** die Dateien des Feature-Branches; `git diff --name-only main...HEAD` zeigt in derselben Lage zusätzlich die zwischenzeitlich auf `main` entstandene Datei — das ist genau der Bruch, den ADR 0063, Abschnitt 3 verhindern wollte, nur mit umgekehrtem Vorzeichen: Er entsteht jetzt dadurch, dass der lokale Ref *nicht mehr* mitgezogen werden **kann**.
5. Bei umgeschriebenem (force-gepushtem) `main` bewegt die Refspec mit `+` den Tracking-Ref ohne Fehlschlag (Exit 0); `git merge-base --is-ancestor <alter Tracking-Stand> <neuer Tracking-Stand>` meldet dann Rückgabe **1**. Ohne `+` verweigert `git fetch` die Aktualisierung des benannten Ziels („kein Vorspulen", Exit 1), und wegen `--quiet` bleibt dieser Fehlschlag ohne jede Meldung.
6. **Gegenüber einer ersten Fassung dieses Punktes korrigiert, weil zweimal unabhängig nachgemessen:** Die konfigurierte Standard-Refspec (`remote.origin.fetch`) feuert sehr wohl parallel mit, auch wenn eine Refspec auf der Kommandozeile steht. Gemessen bewegte `git fetch origin main:refs/heads/uebernommen` den Ref `refs/remotes/origin/main` **mit**, obwohl die Kommandozeilen-Refspec ein ganz anderes Ziel benannte (opportunistische Aktualisierung); erst mit entfernter `remote.origin.fetch` blieb er stehen. Für diese Entscheidung folgenlos — benanntes Ziel und opportunistisch aktualisierter Ref sind hier derselbe —, aber die Zusage der ausgeschriebenen Form ist entsprechend eng zu fassen (Abschnitt 1). Der Punkt steht ausgeschrieben hier, weil eine zu weit formulierte Messung später als generelle Eigenschaft zitiert würde.

`git update-ref refs/heads/main …` scheidet als Ausweg aus, ohne dass es abzuwägen wäre: Der Ref wanderte, während Index und Arbeitsbaum des Haupt-Checkouts stehen blieben. Daniel fände dort einen Berg vermeintlich gelöschter und geänderter Dateien — ein Schaden an einem Arbeitsverzeichnis, das dieser Lauf gar nichts angeht.

## Entscheidung

### 1. Der Abgleich schreibt ausschließlich in den Remote-Tracking-Namensraum

Geholt wird mit einer expliziten, erzwingenden Refspec in den Tracking-Ref:

```
git fetch --quiet origin "+refs/heads/main:refs/remotes/origin/main"
```

Gemerged wird `refs/remotes/origin/main`, nicht `main`. **`refs/heads/main` wird von diesem Skript nie mehr geschrieben und nie mehr gelesen.** Damit verschwindet die Klasse „ein anderer Arbeitsbaum hält den Ref" vollständig, statt sie zu umgehen: Es gibt keinen zweiten Pfad, keine Erkennung, keine Ausweichlogik — die Ursache ist weg, nicht abgefangen.

Die Refspec steht **vollständig ausgeschrieben** auf der Kommandozeile (`refs/heads/…:refs/remotes/…`), nicht als `git fetch origin main`. Grund ist Punkt 6 der Messung, und zwar in dessen enger Fassung: Konfigurationsunabhängig ist das **benannte Ziel** — nicht die Menge der insgesamt berührten Refs (die Standard-Refspec aktualisiert nebenher weiter, was sie will) und erst recht nicht die Auflösung des Remote selbst (`remote.origin.url`, `url.<base>.insteadOf` und `credential.helper` hängen unverändert an der lokalen Konfiguration). `git fetch origin main` überließe der `.git/config`, **ob und welcher** Tracking-Ref danach den geholten Stand trägt; die ausgeschriebene Form legt genau den einen Ref fest, auf den sich Merge und Vergleichsbasis anschließend stützen. Das ist dieselbe Härtungslinie wie das `unset` der `GIT_*`-Variablen aus ADR 0063 — das Verhalten des Abgleichs darf, soweit es in der Hand des Skripts liegt, nicht von der Konfiguration des Repositoriums abhängen, in dem er zufällig läuft.

Alle übrigen Refs im Skript werden ebenfalls voll qualifiziert benutzt (`refs/remotes/origin/main`), damit ein lokaler Branch namens `origin/main` die Auflösung nicht mehrdeutig machen kann.

### 2. Vergleichsbasis der gesamten Review-Phase ist `origin/main...HEAD`

Die acht Fundstellen, die heute `main...HEAD` nennen — `ship-feature` (Schritt 5), `review`, `review-tests`, `review-requirements`, `review-security`, `review-architecture`, `review-ux` und `developer.md` (Berichtsformat) — vergleichen ab jetzt gegen `origin/main`. Die Drei-Punkt-Form bleibt, und mit ihr die Zusicherung: Weil der Abgleich `origin/main` in den Branch merged, ist `origin/main` danach Vorfahre von `HEAD`, die Merge-Basis ist genau der übernommene Stand, und der Diff zeigt genau die Änderungen dieses Branches.

Die Form ist dabei **robuster als vorher**, nicht nur gleichwertig: Läuft `origin/main` nach dem Abgleich weiter (ein `git fetch` von irgendwoher, ein zweiter Lauf im selben Repositorium), bleibt die Merge-Basis der letzte in `HEAD` enthaltene `main`-Stand, und der Diff bleibt der Feature-Diff. Der frühere lokale Ref war nicht stabiler, sondern nur seltener in Bewegung.

Ein zweiter, situationsabhängiger Vergleichsweg („im Arbeitsbaum `origin/main`, sonst `main`") wird ausdrücklich **nicht** eingeführt. Die acht Fundstellen sind Prosa, die zur Laufzeit ein LLM interpretiert; eine Fallunterscheidung dort ist die zuverlässigste Art, dass in der Hälfte der Läufe die falsche Basis gewählt wird — und der Fehler wäre still, wie schon 2026-09-08 festgehalten.

### 3. „`main` wurde umgeschrieben" wird gemessen, nicht aus einem Fehlschlag geraten

Der Abgleich merkt sich vor dem `fetch` den Stand von `refs/remotes/origin/main` (leer, falls der Ref noch nicht existiert) und prüft danach mit `git merge-base --is-ancestor <vorher> <nachher>`:

- Rückgabe `0` (oder kein Vorher-Stand): regulärer Fortschritt, weiter.
- Rückgabe `1`: `main` auf `origin` ist **umgeschrieben** worden. Exit `30` mit einer Meldung, die genau diese eine Ursache nennt.
- Jede andere Rückgabe: Exit `30` mit „hier wurde nichts gemessen" — dieselbe Behandlung, die ADR 0063, Abschnitt 4 für den No-Op-Vorfahrentest festlegt.

Damit tritt Exit `30` in der Ausgangslage aus dem Kontext nicht mehr auf, und die verbleibenden Ursachen des `fetch`-Fehlschlags schrumpfen von drei auf zwei (Remote unerreichbar, `main` dort nicht vorhanden) — beide echte Hindernisse. Die Unterscheidung fällt weiterhin an Exit-Codes und Ref-Ständen, nie an einem Ausgabetext von `git`.

Der erzwingende Charakter der Refspec (`+`) ist die Voraussetzung dafür, dass diese Messung überhaupt stattfindet, statt vom `fetch` vorweggenommen zu werden. Preis: Im Abbruchfall steht der Tracking-Ref bereits auf dem umgeschriebenen Stand. Das ist keine neue Eigenschaft — der Nachtrag zu ADR 0063 hält dasselbe bereits fest — und es ist folgenlos, weil weder der ausgecheckte Branch noch `refs/heads/main` noch das Arbeitsverzeichnis angefasst werden.

### 4. Die vier Ausgänge bleiben, was sie sind

`0` (enthalten), `10` (übernommen), `20` (Konflikt, mindestens ein Pfad unmerged), `30` (Vorbedingung/Umgebung) behalten Bedeutung, Zustandszusage und Unterscheidbarkeit. Der No-Op wird weiterhin **vor** dem Merge gerechnet, jetzt mit `git merge-base --is-ancestor refs/remotes/origin/main HEAD`. Die Vorbedingungen bleiben unverändert, ebenso das Verbot von `push`, `rebase`, `commit --amend`, `reset --hard` und `--force`-Schreibzugriffen auf Branches — die Refspec trägt zwar ein `+`, das aber ausschließlich für einen Ref unter `refs/remotes/` und ausschließlich lesend gegenüber dem Remote.

### 5. Der Arbeitsbaum-Fall wird Fixture, nicht Fußnote

Die Verhaltenstests bekommen einen Spielplatz mit **zwei** Arbeitsbäumen: Haupt-Checkout auf `main`, verbundener Arbeitsbaum (`git worktree add`) auf dem Feature-Branch, das Skript läuft im verbundenen. Zugesichert wird dort der volle Durchlauf (Exit `10`, Review-Diff genau die Branch-Dateien), die Unversehrtheit des Haupt-Checkouts (`refs/heads/main` unverändert, `git status --porcelain` leer, `HEAD` unverändert) und der Konfliktausgang (`MERGE_HEAD` liegt im arbeitsbaumeigenen Git-Verzeichnis).

Dazu gehört zwingend die **Gegenprobe**, die von Hand `git fetch origin main:main` in derselben Lage absetzt und den Fehlschlag festhält. Ohne sie belegte der neue Test nur, dass irgendein Repositorium funktioniert — nicht, dass die Fixture die gemeldete Konstellation überhaupt herstellt. Das ist dieselbe Bauart, mit der ADR 0063 ihren tragenden Regressionstest abgesichert hat, und sie gilt hier unverändert weiter.

## Begründung

Erwogen wurde, die Refspec zu behalten und nur den Fehlerfall abzufangen: erkennen, ob `main` in einem anderen Arbeitsbaum ausgecheckt ist (`git worktree list --porcelain`), und dann auf `origin/main` ausweichen. Das scheitert nicht an der Erkennung, sondern an dem, was danach kommt. Im Ausweichfall bliebe `refs/heads/main` stehen, während `origin/main` gemerged wäre — die Review-Phase müsste ihre Vergleichsbasis **von der Lage abhängig** wählen. Genau dort ist der Fehler still: `main...HEAD` liefert dann fremde Dateien, alle Prüfer bleiben grün, und die Findings beziehen sich auf Code, den der Branch nie berührt hat. Zwei Pfade, zwei Basen, ein LLM als Weiche — das ist teurer und unzuverlässiger als eine Basis für alle Fälle.

Die Umstellung auf `origin/main` nimmt dem Ablauf dagegen eine Eigenschaft weg, statt eine hinzuzufügen: Der Abgleich muss keinen lokalen Branch-Ref mehr pflegen. Was ADR 0063 als Notwendigkeit beschrieb („sonst lügt der Review-Diff"), war die Folge einer freien Wahl — nämlich gegen `main` zu diffen statt gegen `origin/main`. Die andere Wahl trägt dieselbe Zusage, ohne einen Ref zu brauchen, den ein zweiter Arbeitsbaum halten kann.

Dass ADR 0063 vor dieser Vereinfachung ausdrücklich warnt („wer den `fetch` je auf `git fetch origin` ohne Refspec vereinfacht, bricht die Review-Runde still"), bleibt richtig — für die dort beschriebene Welt. Die Warnung gilt der Kombination „lokaler Ref bleibt stehen **und** es wird weiter gegen ihn verglichen". Diese ADR bricht die Kombination auf, indem sie beide Hälften gemeinsam bewegt; sie hebt die Warnung nicht auf, sondern macht ihren Gegenstand gegenstandslos. Der Prüfer, der die Warnung durchsetzt, wandert entsprechend mit: Statt „die `fetch`-Zeile trägt eine Refspec" sichert er ab jetzt zu, dass das **Ziel** der Refspec unter `refs/remotes/` liegt und **kein** `refs/heads/`-Ref ist — die schärfere Aussage, denn sie verbietet die schädliche Form, statt eine unschädliche zu verlangen.

## Konsequenzen

- **Der lokale `main`-Ref altert ab jetzt.** Kein Ablaufschritt zieht ihn mehr nach. Für die Review-Phase folgenlos (sie liest ihn nicht mehr), für Daniels Haupt-Checkout unverändert (dort zieht `git pull` ihn wie immer). Wer in einem Arbeitsbaum `git log main` liest, sieht einen alten Stand — bewusst in Kauf genommen, weil jede automatische Pflege dieses Refs genau das Problem zurückholt, das hier gelöst wird.
- **`spec-writer` Schritt 4 bleibt unangetastet und behält seine eigene Lücke.** Der dortige Abzweig (`git fetch origin && git checkout main && git pull`) scheitert in einem Arbeitsbaum aus derselben Wurzel — `main` ist anderswo ausgecheckt. Das ist ein anderer Ablaufschritt mit einem anderen Ziel (einen Branch von aktuellem `main` abzweigen) und nicht Gegenstand dieser Entscheidung; wer ihn anfasst, tut das über eine eigene Story.
- **Die Vergleichsbasis liegt jetzt auf einem Ref, den jeder `git fetch` bewegen kann.** Nachgerechnet ist, dass die Drei-Punkt-Form davon nicht kippt (siehe Abschnitt 2); ein Test hält es fest, damit es nicht bei „nachgerechnet" bleibt.
- **Die statische Verdrahtungsprüfung ändert ihre Aussage, nicht ihren Zweck.** `scripts/tests/test_main_abgleich_verdrahtung.py` sichert ab jetzt zu: genau eine `git fetch`-Zeile, mit `--quiet`, deren Refspec-Ziel unter `refs/remotes/` liegt, und nirgends im Skript ein Schreibzugriff auf `refs/heads/main` (`update-ref`, `branch -f`, `fetch …:main`). Der Mutationsnachweis dieser Familie ist zu wiederholen, nicht zu glauben.
- **Ein Rückfall in die alte Form fällt ab jetzt auf.** Er ist zweifach abgedeckt: statisch über das Refspec-Ziel und verhaltensseitig über den Zwei-Arbeitsbaum-Fall, der mit `main:main` gemessen Exit 128 liefert.
- **ADR 0063 trägt ab jetzt einen `**Teilweise abgelöst:**`-Kopf.** Ihr Entscheidungstext bleibt unverändert; angefasst wird ausschließlich der Kopf, der dafür vorgesehene Mechanismus aus [`../README.md`](../README.md).
