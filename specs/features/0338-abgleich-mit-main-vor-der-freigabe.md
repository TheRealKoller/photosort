# 0338 - Pull Request bleibt bis zur Freigabe mergebar: Abgleich mit `main`

**Status:** Accepted
**Erstellt:** 2026-09-08
**Bezug:** GitHub-Issue [`#338`](https://github.com/TheRealKoller/photosort/issues/338), Architekturentscheidung ADR [`0063`](../decisions/0063-abgleich-mit-main-als-getestetes-lokales-skript-merge-statt-rebase.md), fortgeführte Entscheidungen ADR [`0045`](../decisions/0045-spec-writer-legt-feature-branch-an-ein-pr-pro-story.md) (Abzweig von aktuellem `main`) und ADR [`0042`](../decisions/0042-pre-merge-finalisierung-statt-nachzieh-pr.md) (Finalisierung gebündelt mit dem letzten Push), `specs/architecture/0002-testkonzept.md`, `specs/architecture/0003-securitykonzept.md`

## Ziel

Ein fertiggestellter Pull Request lässt sich regelmäßig nicht freigeben, weil `main` inzwischen
weitergelaufen ist. Der Merge ist dann blockiert, obwohl inhaltlich nichts kollidiert — es fehlt
allein der aktuelle Stand im Feature-Branch. Der Ablauf zweigt den Branch zwar von einem aktuellen
Stand ab (ADR 0045, `spec-writer` Schritt 4), zieht danach aber an keiner Stelle mehr nach, obwohl
zwischen Abzweig und Freigabe die gesamte Umsetzungs-, Review- und Copilot-Runde liegt.

Betroffen ist Daniel als einziger Freigebender: Er stößt beim Mergen auf einen Blocker, den er von
Hand auflösen muss, bevor er überhaupt zur eigentlichen Entscheidung kommt. Gelöst ist das Problem,
wenn ein abgeschlossener Lauf einen Pull Request hinterlässt, der ohne manuellen Zwischenschritt
freigegeben werden kann.

## User Story

Als Freigebender möchte ich, dass der Feature-Branch den aktuellen Stand von `main` bereits
enthält, wenn ich einen Pull Request vor mir habe, damit ich ihn direkt freigeben kann, statt
zuerst einen Blocker aufzulösen, der nichts mit dem Inhalt der Änderung zu tun hat.

## Akzeptanzkriterien

Fachlich aus dem Issue-Body übernommen, von `test-engineer` auf Entscheidbarkeit geschärft: Die
Rohfassung ist an vier Stellen nicht prüfbar formuliert („geschieht nichts", „keine Meldung",
„unversehrt", „kein Rauschen"). AK 10 und AK 11 sind **neu** hinzugekommen und decken zwei Fälle,
die weder Story noch ADR nennen; beide beruhen auf einer Messung am laufenden `git`, nicht auf
einer Vermutung.

- [ ] **AK 1 — erster Zeitpunkt.** `ship-feature` Schritt 6 ruft `scripts/merge-main-into-branch.sh`
      genau einmal auf, **nach** dem Committen etwaiger Reste (das Skript verlangt ein sauberes
      Arbeitsverzeichnis) und **vor** `git push`.
- [ ] **AK 2 — zweiter, tragender Zeitpunkt.** `ship-feature` Schritt 8 ruft es als erste Handlung
      auf, **vor** der Verknüpfungsprüfung und **vor** dem Setzen der `**Status:**`-Zeile. Zwischen
      Eröffnung und Freigabe vergeht die meiste Zeit; dieser Aufruf ist der entscheidende.
- [ ] **AK 3 — No-Op.** Ist `main` bereits Vorfahre von `HEAD`, endet das Skript mit Exit `0`,
      **ohne** ein `git merge` abzusetzen. `HEAD`, Commit-Anzahl und Arbeitsverzeichnis sind
      unverändert; **stdout und stderr sind leer** (verlangt ein `--quiet` am `fetch`, der seinen
      Fortschritt sonst nach stderr schreibt). Kein leerer Commit, kein zusätzlicher Testlauf,
      keine Meldung.
- [ ] **AK 4 — keine umgeschriebenen Commits.** Nach Exit `10` ist der Kopf **vor** dem Lauf der
      erste Elternteil des neuen Kopfes (`git rev-parse HEAD^1`) und damit dessen Vorfahre; kein
      bestehender Commit-Hash ändert sich. Bestehende Review-Kommentare und -Threads am Pull
      Request bleiben dadurch unversehrt. Das Skript enthält kein `rebase`, `commit --amend`,
      `push` und kein `reset --hard`.
- [ ] **AK 5 — Konflikt.** *Skript-Hälfte:* Exit `20`, `MERGE_HEAD` existiert, stdout enthält genau
      die Konfliktpfade (eine Zeile je Pfad, repo-relativ, sonst nichts), die feste Merge-Nachricht
      liegt in `MERGE_MSG`. *Ablauf-Hälfte:* Exit `10` **und** `20` gehen per `SendMessage` an den
      offenen `developer`-Subagenten; in beiden Fällen läuft dessen Schritt 4 (vollständiger
      Qualitätscheck) erneut, und erst bei grünem Ergebnis geht es weiter.
- [ ] **AK 6 — Abbruch statt fraglicher Stand.** Gelingt die Auflösung nicht sauber oder bleibt der
      Qualitätscheck rot: `git merge --abort`, Anker `## Blockiert: main-Abgleich fehlgeschlagen`,
      `ship-feature` pusht **nicht** und meldet an Daniel. Skript-seitig prüfbar: Nach
      `git merge --abort` sind `HEAD` und `git diff --name-only main...HEAD` exakt wie vor dem Lauf.
- [ ] **AK 7 — Einbahnstraße.** Nach *jedem* Ausgang sind sämtliche Refs des `origin`-Repositoriums
      unverändert (`git for-each-ref`, nicht nur `main`), der ausgecheckte Branch ist unverändert,
      `main` wurde nie ausgecheckt. Das Skript arbeitet im Repositorium des **aktuellen
      Arbeitsverzeichnisses** und leitet sein Ziel nie aus dem eigenen Ablageort ab. Die Freigabe
      nach `main` bleibt vollständig eine Entscheidung von Daniel.
- [ ] **AK 7b — Wirkung der Refspec.** Nach Exit `10` gilt `git rev-parse main == git rev-parse
      origin/main`, und `git diff --name-only main...HEAD` listet exakt die Dateien dieses Branches
      — keine der zwischenzeitlich auf `main` entstandenen.
- [ ] **AK 8 — kein Rauschen.** Die Merge-Nachricht ist **genau eine** Zeile, beginnt mit `chore: `,
      enthält keinen Commit-Hash, keine Konfliktliste und kein `#`; `chore` ist in
      `release-please-config.json` nicht sichtbar geschaltet. Das gilt auch für die Nachricht des
      Konflikt-Abschlusscommits.
- [ ] **AK 9 — freigabefähiger Pull Request.** Ein vollständig durchlaufener Ablauf hinterlässt
      einen Pull Request, der ohne manuellen Eingriff freigegeben werden kann. Bekannte Restlücke:
      Läuft `main` zwischen dem letzten Push und der Freigabe erneut weiter, bleibt ein manueller
      Handgriff nötig — diese Lücke ist bewusst nicht geschlossen.
- [ ] **AK 10 — Vorbedingungen, einzeln aufgezählt (neu).** Unsauberes Arbeitsverzeichnis (gestagt
      **oder** ungestagt), `main` ausgecheckt, losgelöster `HEAD`, kein `origin`, fehlgeschlagener
      `fetch`, `origin` ohne `main`, `main` nicht vorspulbar → Exit außerhalb `{0, 10, 20}`, Zustand
      unverändert, Begründung auf stderr. **Unversionierte Dateien blockieren nicht.**
- [ ] **AK 11 — Exit `20` nur bei echtem Konflikt (neu).** Exit `20` entsteht ausschließlich, wenn
      mindestens ein Pfad im Konfliktzustand ist. Scheitert der Merge ohne Konflikt, räumt das
      Skript auf (`git merge --abort`) und endet in der Fehlerfamilie.

## Datenmodell-Bezug

Nicht betroffen. Die Story ändert ausschließlich den Entwicklungsablauf (Skill-/Agenten-Dateien und
ein lokales Git-Skript); es entstehen keine neuen oder geänderten Entitäten, `docs/architecture.md`
bleibt unverändert.

## Architektur / Umsetzung

Grundlage: ADR [`0063`](../decisions/0063-abgleich-mit-main-als-getestetes-lokales-skript-merge-statt-rebase.md)
(neu angelegt für diese Story). Sie entscheidet die drei tragenden Fragen — Skript statt
Ablauf-Text, Merge statt Rebase, Mitziehen des lokalen `main`-Refs — und begründet, warum die
Werkzeug-Abkehr aus ADR [`0057`](../decisions/0057-board-lebenszyklus-nativ-statt-eigenbau.md) /
[`0061`](../decisions/0061-ein-ort-fuer-jeden-github-zugriff-wege-in-fester-reihenfolge.md) hier
nicht trägt: Sie gilt dem GitHub-Zugriff, dessen Weg von der Session abhängt, nicht einer rein
lokalen, deterministischen Befehlsfolge.

### Gewählter Ansatz

Der Abgleich ist ein eigenständiges, argumentloses Bash-Skript `scripts/merge-main-into-branch.sh`
mit definierten Exit-Codes, das `ship-feature` an beiden Zeitpunkten aufruft. Der Grund ist
Prüfbarkeit: AK 3, 5 und 6 sind Verhaltensaussagen und gegen ein Skript mit echten temporären
Git-Repositorien testbar; gegen Skill-Text bliebe nur ein statischer Textprüfer, der auch dann grün
wäre, wenn jeder Lauf einen leeren Merge-Commit erzeugte.

### Vertrag des Skripts

Keine Argumente, `origin`/`main` als Literale, arbeitet im Repositorium des aktuellen
Arbeitsverzeichnisses auf dem aktuell ausgecheckten Branch.

1. Umgebung bereinigen (siehe `## Security`, Bedrohung 1), dann Vorbedingungen prüfen:
   Arbeitsverzeichnis sauber (unversionierte Dateien ausgenommen), `HEAD` nicht losgelöst,
   aktueller Branch **nicht** `main`, `origin` vorhanden.
2. `git fetch --quiet origin main:main` — spult den **lokalen** `main`-Ref vor, ohne ihn
   auszuchecken. Schlägt fehl, wenn das kein Vorspulen wäre (`main` umgeschrieben) → Abbruch.
3. `git merge-base --is-ancestor main HEAD` → Rückgabe **exakt `0`**: Ende, Exit `0`, keine Ausgabe.
   Es wird kein `git merge` abgesetzt.
4. Sonst `git merge --no-ff --no-edit -m "chore: Stand von main in den Feature-Branch übernehmen" main`.

| Exit | Bedeutung | Zustand danach |
|---|---|---|
| `0` | `main` bereits enthalten | unverändert, **keine Ausgabe auf stdout und stderr** |
| `10` | sauber übernommen | ein neuer Merge-Commit, Arbeitsverzeichnis sauber |
| `20` | Konflikt (mindestens ein unmerged Pfad) | Merge steht offen (`MERGE_HEAD`), Konfliktpfade auf stdout |
| sonstige | Vorbedingung/Umgebung fehlgeschlagen | unverändert, Begründung auf stderr |

Das Skript **pusht nie**, checkt nie `main` aus und enthält kein `rebase`, `commit --amend`,
`push --force` oder `reset --hard` (AK 4, AK 7). Das `--no-ff` sichert zu, dass der bisherige
Branch-Kopf immer erster Elternteil des neuen Kopfes bleibt — ohne es könnte ein Vorspulen den
Feature-Branch stillschweigend auf `main` schieben und den Pull Request leeren.

**Warum `main:main` als Refspec und nicht `git fetch origin` + `git merge origin/main`:** Die
Review-Phase hängt an sechs Stellen an `git diff main...HEAD` (`ship-feature` Schritt 2 und 5,
`review`, die vier `review-*`-Skills). Die Drei-Punkt-Form vergleicht gegen die Merge-Basis, und die
wird aus dem **lokalen** `main`-Ref gebildet. Bliebe der stehen, zeigte `main...HEAD` ab dem Abgleich
den Feature-Diff **plus** alles zwischenzeitlich auf `main` Passierte — jede Review-Perspektive
bekäme fremde Dateien vorgelegt, und nichts würde rot. Mit der Refspec bleibt die Merge-Basis exakt
der übernommene `main`-Stand; keine der sechs Fundstellen muss angefasst werden.

**Merge-Commit-Nachricht:** fest, einzeilig, konventionell, Typ `chore` — von release-please in den
Vorgabe-Sektionen ausgeblendet, also kein Changelog-Eintrag und keine Versionsanhebung (AK 8).
Bewusst ohne Commit-Hash und ohne Konfliktliste: Der übernommene Stand steht im zweiten Elternteil,
und jede Zusatzzeile landete im Body des Squash-Commits.

### Verdrahtung in `ship-feature`

Zeitpunkt 1 — **Schritt 6**, neu als 6.2 zwischen dem Committen etwaiger Reste (6.1) und dem Push.

Zeitpunkt 2 — **Schritt 8**, als **erste** Handlung, vor der Verknüpfungsprüfung und vor dem Setzen
der Spec-Statuszeile. Merge-Commit, etwaiger Konflikt-Fix und Finalisierungs-Commit gehen danach in
**einem** Push hinaus; die Bündelungsregel aus ADR 0042 umfasst ab jetzt auch den Abgleich, damit
kein zusätzlicher CI-Lauf entsteht.

Auswertung an beiden Stellen identisch:

- **Exit `0`:** weiter, ohne jede Meldung — kein Berichtseintrag, kein Testlauf.
- **Exit `10` und `20`:** per `SendMessage` an den weiterhin offenen `developer`-Subagenten
  (Folgeauftrag „Abgleich mit `main`"). Der Orchestrator führt **selbst keinen Testlauf** aus — die
  Rollenteilung aus Schritt 5 bleibt unverändert.
- **Jeder andere Exit-Code sowie der Anker `## Blockiert: main-Abgleich fehlgeschlagen`:** Ablauf
  anhalten, nichts pushen, an Daniel melden (AK 6). Ein unbekannter Exit-Code wird **nie** wie `0`
  behandelt.

Ergänzung im Abschnitt „Recovery": Schlägt `SendMessage` nach Exit `20` fehl, wird vor dem neuen
`developer`-Lauf `git merge --abort` abgesetzt, damit kein Repositorium mit offenem Merge übergeben
wird.

### Verdrahtung in `developer.md`

Neuer Folgeauftrag „Abgleich mit `main`" (eigener Abschnitt, analog zum bestehenden „Findings
beheben"):

- Bei Konflikt: den **bereits offen stehenden** Merge auflösen und mit
  `git add <genau die Konfliktpfade>` + `git commit --no-edit --cleanup=strip` abschließen. Die
  Nachricht liegt in `MERGE_MSG` bereit und wird an keiner zweiten Stelle wiederholt; `--cleanup=strip`
  entfernt die von git angehängte `# Conflicts:`-Liste (AK 8), `git add -A`/`git commit -a` sind
  ausgeschlossen (siehe `## Security`, Bedrohung 4).
- In **beiden** Fällen (Konflikt wie sauberer Merge) danach Schritt 4 vollständig.
- Erfolgsanker: `## Abschlussbericht (Folgeauftrag: main-Abgleich)`, mit den Konfliktpfaden
  **einzeln** aufgeführt, je Pfad mit einem Wort, welche Seite gewonnen hat.
- Abbruchanker (AK 6): `## Blockiert: main-Abgleich fehlgeschlagen` — vorher `git merge --abort`,
  Branch steht wieder im Stand vor dem Abgleich.

Beide Anker kommen zusätzlich in die Trigger-Liste in `ship-feature` Schritt 0. Definiert werden sie
wie alle anderen ausschließlich in `.claude/agents/developer.md`; `ship-feature` verweist nur
funktional darauf. **Warum eigene Anker statt des bestehenden „Findings beheben":** Es gibt keine
Findings-Liste, und ein Bericht `## Abschlussbericht (Folgeauftrag: Findings behoben)` behauptete
etwas, das nicht stattgefunden hat. Der bestehende „Blockiert"-Anker ist fest an die
Architektur-Konsultation gebunden.

**Warum auch der saubere Merge (Exit `10`) den Qualitätscheck auslöst:** Ein textuell konfliktfreier
Merge ist kein fachlich konfliktfreier (Umbenennung auf `main`, Aufrufer im Branch — für `git` keine
Kollision). Der Branch enthielte sonst Code, gegen den nie ein Test gelaufen ist, die CI färbte sich
nach dem Push rot, und AK 9 wäre mit einem anderen Blocker verfehlt. AK 3 verbietet den Testlauf
ausschließlich für den No-Op-Fall, AK 5 verlangt ihn ausdrücklich für den Konfliktfall.

### Betroffene Dateien

| Datei | Art | Inhalt |
|---|---|---|
| `specs/decisions/0063-*.md` | neu | die Architekturentscheidung |
| `scripts/merge-main-into-branch.sh` | neu | das Skript |
| `scripts/tests/test_merge_main_into_branch.py` | neu | Verhaltenstests gegen echte temporäre Repositorien |
| `scripts/tests/test_main_abgleich_verdrahtung.py` | neu | statische Prüfung der Skill-/Agenten-Verdrahtung |
| `.claude/skills/ship-feature/SKILL.md` | geändert | Schritt 0 (zwei neue Anker), Schritt 6 (neuer 6.2), Schritt 8 (neue erste Handlung), Recovery |
| `.claude/agents/developer.md` | geändert | neuer Folgeauftrag „Abgleich mit `main`" samt zwei Ankern |
| `docs/ai-workflow.md` | geändert | Schritt-Tabelle nennt den Abgleich (neue Zeile 5c, erweiterte Zeile 7b); dabei wird die veraltete Angabe in Zeile 7b mitgezogen (siehe „Entscheidungen“) |
| `specs/architecture/0002-testkonzept.md` | geändert | neue Sektion und drei neue bekannte Lücken |
| `specs/architecture/0003-securitykonzept.md` | geändert | neue Angriffsfläche, Restrisiken, bekannte Lücken |

Nicht betroffen: `docs/architecture.md` (Laufzeitsystem und Datenmodell unberührt), `docs/setup.md`
(das Skript ist kein Schritt eines lokalen Setups, sondern Teil des Agenten-Ablaufs), `README.md`,
`spec-writer` (zweigt schon heute von aktuellem `main` ab, ADR 0045).

## UI/UX

nicht relevant — die Story berührt ausschließlich den Agenten-Ablauf (Skill-/Agenten-Dateien und ein
lokales Git-Skript). Es gibt keine Stelle, an der etwas angezeigt oder eingegeben wird, und keine
Frontend-Komponente im Umsetzungsplan (`ux-ui-designer` deshalb in Schritt 2 nicht konsultiert).

## Teststrategie

**Ebene und Ort.** `pytest` unter `scripts/tests/`, bestehender CI-Job `demo-scripts`, kein neuer
Job, kein neues Werkzeug (**kein** `bats-core`/`shunit2`/`shellcheck`). Zwei Dateien mit
unterschiedlicher Fehlersemantik: `test_merge_main_into_branch.py` (Verhalten, echte temporäre
Repositorien mit barem `origin`, Skript als Unterprozess) und `test_main_abgleich_verdrahtung.py`
(statische Prüfung der Verdrahtung). Kein Coverage-Gate (`CLAUDE.md` fordert es nur für `backend/`);
der Abdeckungsanspruch ist die Fallliste.

**Umgebung (jeder Unterprozess, auch der des Skripts selbst):** `GIT_AUTHOR_*`/`GIT_COMMITTER_*` (in
CI ist keine Identität konfiguriert — sonst lokal grün, in CI rot); `GIT_CONFIG_GLOBAL=/dev/null` und
`GIT_CONFIG_SYSTEM=/dev/null`; `git init -b main` explizit statt `init.defaultBranch`;
`GIT_CEILING_DIRECTORIES` als Sicherheitsnetz, damit ein falsches Arbeitsverzeichnis nicht im echten
Repositorium merged; `GIT_TERMINAL_PROMPT=0`, `GIT_EDITOR=true`, Timeout an jedem Aufruf;
Git-Mindestversion als eigener Test mit Klartext-Fehlschlag (kein `skip`).

**Locale:** wird nicht gesetzt, sondern überflüssig gemacht — alle Entscheidungen fallen an
Exit-Codes und Dateizuständen (`--is-ancestor`, `MERGE_HEAD`, `--diff-filter=U`), nie an
Ausgabetexten. Der ehrliche Prüfer dafür ist ein statischer Abwesenheitstest auf
`Already up to date`/`CONFLICT`/`Automatic merge failed` im Skripttext.

**Tragender Test:** der Regressionstest auf `git diff --name-only main...HEAD` nach Exit `10` — **mit
Gegenprobe**: derselbe Test stellt von Hand den Zustand der naheliegenden Falschimplementierung her
(`git fetch origin` ohne Refspec + `git merge origin/main`) und weist nach, dass die Assertion dort
rot wird. Ohne diese Hälfte prüft er nur, dass eine Liste nicht leer ist.

**Pflichtfälle:** No-Op (inkl. zweiter Lauf direkt nach erfolgreichem Abgleich, stdout+stderr leer) ·
sauberer Merge (Erst-Elternteil-Nachweis) · Branch vollständig in `main` enthalten
(`--no-ff`-Nachweis) · Konflikt in drei Klassen (modify/modify, add/add, delete/modify) ·
dokumentierter Auflösungsweg (`git commit --no-edit --cleanup=strip` → genau eine Zeile) ·
`git merge --abort` stellt her · Merge scheitert ohne Konflikt (`pre-merge-commit`-Hook) ·
Einbahnstraße nach jedem Ausgang · die sieben Vorbedingungen einzeln · untracked blockiert nicht /
tracked blockiert.

**Statisch verdrahtet:** Existenz und Ausführbarkeit des Skripts; genau zwei Aufrufstellen in
`ship-feature`; Reihenfolge in Schritt 6 (nach Commit, vor Push) und Schritt 8 (vor
Verknüpfungsprüfung und Statuszeile) über Zeichenoffsets; beide neuen Anker wortgleich in
`developer.md` und **nur** dort; die feste Merge-Nachricht genau einmal im Suchraum `scripts/` +
`.claude/`; `chore` in `release-please-config.json` nicht sichtbar; die Abwesenheit von `push`,
`rebase`, `commit --amend` und `reset --hard` im Skripttext (AK 7, zugleich Sicherheitsinvariante).
Selbstschutz wie bei den übrigen Repo-Konsistenztests (Suchraum-Untergrenze, Gegenprobe je
Musterfamilie, Mutationsnachweis nach Grün).

**Bewusst nicht gebaut:** ein Prüfer, der aus dem Prosatext herausliest, dass nach Exit `10` der
Qualitätscheck läuft oder bei Rot abgebrochen wird. Er wäre grün, weil ein Satz dasteht, und fröre
nebenbei die Formulierung ein. AK 2, 5, 6 und 9 sind damit je zur Hälfte zugesichert — Skript
ausführbar bewiesen, Ablauf nur verankert. Vollständig in
[`specs/architecture/0002-testkonzept.md`](../architecture/0002-testkonzept.md).

## Security

Sicherheitsrelevant, kein Blocker. Vollständige Herleitung im Sicherheitskonzept
([`specs/architecture/0003-securitykonzept.md`](../architecture/0003-securitykonzept.md), Abschnitt
„Abgleich mit `main` als lokales Skript" unter „Angriffsflächen", plus je zwei Einträge unter
Restrisiken und Bekannten Lücken). Kein Anwendungscode, keine Foto-/Projektdaten, kein neues Secret,
keine neue externe Abhängigkeit. Alle Messungen am 2026-09-08 in Wegwerf-Repositorien.

**Nicht-Befund, ausdrücklich festgehalten — der hereingezogene Inhalt führt keinen Code aus.** Ein
mit `main` hereinkommendes `.gitattributes` mit `* merge=evil` löst ohne passenden
`merge.evil.driver` in der Konfiguration nachgemessen nichts aus; git fällt auf den
Standard-Textmerge zurück. Merge-Treiber kommen aus der **Konfiguration**, Hooks aus `.git/hooks`
bzw. `core.hooksPath` — `git fetch` überträgt beides nicht. `main` ist derselbe Ursprung, aus dem der
Branch ohnehin abzweigt, mit genau einem Collaborator, PR-Pflicht und `enforce_admins: true` davor:
**kein neuer Vertrauensübergang.**

**Bedrohung 1 — „keine Argumente" ist keine Zielbindung.** Mit gesetztem `GIT_DIR`/`GIT_WORK_TREE`
meldete `git branch --show-current` gemessen den Branch eines **anderen** Repositoriums; mit
`GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_0=core.hooksPath` wurde während `git merge` ein `post-merge`-Hook
aus einem beliebigen Verzeichnis ausgeführt. Wer diese Variablen setzen kann, hat bereits
Codeausführung in derselben Sitzung — es geht um Tiefenstaffelung und vor allem Unfallschutz (ein
stehen gebliebenes `GIT_DIR` richtete ein `git merge` auf ein fremdes Arbeitsverzeichnis).
*Gegenmaßnahme, Muss-Kriterium:* direkt nach `set -euo pipefail` ein `unset` von `GIT_DIR`,
`GIT_WORK_TREE`, `GIT_COMMON_DIR`, `GIT_INDEX_FILE`, `GIT_OBJECT_DIRECTORY`,
`GIT_ALTERNATE_OBJECT_DIRECTORIES` und `GIT_CONFIG_COUNT`. `GIT_AUTHOR_*`/`GIT_COMMITTER_*` und
`GIT_CONFIG_GLOBAL` bleiben ausdrücklich stehen (die Test-Fixtures brauchen sie).

**Bedrohung 2 — fail-open an genau einem Ausgang.** Von den drei Ausgängen lösen `10` und `20` eine
Handlung aus, „alles andere" hält den Ablauf an; still falsch sein kann allein `0`.
`git merge-base --is-ancestor` liefert gemessen `0` (Vorfahre), `1` (nicht) und **`128`**
(unbekanntes Objekt/kaputtes Repositorium). Wird „nicht 1" oder „Fehler" auf den No-Op-Ausgang
gemappt, meldet das Skript „`main` ist bereits enthalten" für ein Repositorium, in dem es gar nicht
gemessen hat. *Muss-Kriterien:* Exit `0` entsteht an genau einer Stelle und ausschließlich bei
Rückgabe `0`; jeder Pfad endet in einem expliziten `exit`; kein Kommando am Skriptende, dessen Status
durchfällt; `ship-feature` behandelt einen unbekannten Exit-Code als Abbruch, nie wie `0`.

**Bedrohung 3 — die Ein-Richtungs-Grenze (AK 7) muss geprüft sein, nicht zugesagt.** Sie hält in drei
Lagen: Eine Fetch-Refspec kann nicht auf den Remote schreiben (und `git fetch origin main:main`
bricht mit ausgechecktem `main` von sich aus mit `fatal: refusing to fetch into branch` ab — diese
Vorbedingung setzt git selbst durch). Die Abwesenheit von `push`/`rebase`/`--force`/`reset --hard`/
`commit --amend` ist eine Texteigenschaft und wird deshalb *Muss-Kriterium* des statischen Tests,
womit AK 7 im Required Check `demo-scripts` liegt. Und Branch Protection auf `main`
(`enforce_admins: true`, PR-Pflicht, `allow_force_pushes: false`) weist einen versehentlichen Push
unabhängig von Skript und Agent ab.

**Bedrohung 4 — der einzige Inhalt des Ablaufs, den niemand reviewt.** Beide Aufrufstellen liegen
**nach** der Review-Runde, die zweite zusätzlich nach dem Copilot-Review. Bei Exit `20` ist die
Konfliktauflösung eine inhaltliche, agentenerzeugte Codeänderung, die als letzte Handlung vor Daniels
Merge hinausgeht. Sichtbar bleibt sie (nach dem Merge ist die Merge-Basis exakt der übernommene
`main`-Stand, eine Auflösung, die eine `main`-Seite verwirft, erscheint in `git diff main...HEAD`) —
es sieht sie nur niemand mehr. *Muss-Kriterien:* Der Bericht führt die Konfliktpfade **einzeln** auf,
je Pfad mit einem Wort, welche Seite gewonnen hat; `ship-feature` übernimmt diese Liste in den
Chat-Bericht an Daniel und **nie** in den PR-Body (Härtungsregel 4.3 des Skills `github-access`); der
`developer` schließt mit `git add <genau die Konfliktpfade>`, **nie** `git add -A`/`git commit -a`
(gemessen: `git commit --no-edit` committet nur den Index, eine danebenliegende untracked `.env`
bleibt untracked; `git add -A` nähme sie mit, und der Branch geht unmittelbar danach in ein
öffentliches Repositorium).

**Bedrohung 5 — Secrets in der Ausgabe.** Die Ausgabe des Skripts fließt in den Chat-Bericht und in
eine `SendMessage`. *Muss-Kriterien:* Die Vorbedingung „`origin` vorhanden" wird über den Exit-Code
geprüft (`git remote get-url origin >/dev/null`), der Wert nie ausgegeben und in keine Fehlermeldung
übernommen — in Umgebungen mit credential-behaftetem Remote wäre die Fehlermeldung ein Secret-Leck.
Bei Exit `20` gehen **Konfliktpfade** auf stdout, nicht die stderr-Ausgabe von `git merge`.

**Review-Trigger:** Der Diff dieser Story liegt vollständig unter `scripts/**`, `.claude/**`,
`specs/**` und `docs/**`; die Trigger-Tabelle in `.claude/skills/review/SKILL.md` nennt für die
Sicherheitsperspektive ausschließlich Pfade unter `backend/`, `frontend/`, `.env.example`,
`.github/workflows/**` und die Docker-Compose-Netzwerkkonfiguration. Die Perspektive wird für diesen
Branch deshalb **einmalig explizit** angefordert („im Zweifel aufrufen", ADR 0014).

**Genauigkeitskorrektur:** Für den Vorbedingungsfehler „`main` nicht vorspulbar" gilt „Zustand
unverändert" gemessen für den lokalen `main`-Ref, nicht für `refs/remotes/origin/main` — die
Standard-Refspec aus `.git/config` feuert parallel und aktualisiert die Tracking-Referenz zwangsweise
mit. Für die Review-Basis folgenlos (`main...HEAD` liest den lokalen Ref); nur nicht darauf bauen,
dass der Abbruchpfad seiteneffektfrei ist.

## Entscheidungen

- **Skript statt Ablauf-Text** (ADR 0063 Abschnitt 1). Die Werkzeug-Abkehr aus ADR 0057/0061 trägt
  hier nicht: Das Board-Werkzeug fiel, weil es eine ID-Auflösungsschicht kapselte, die `gh` 2.97
  überflüssig gemacht hatte, und weil ein Werkzeug im Subprozess die MCP-Werkzeuge der Session nicht
  erreicht. Für `git` gilt keiner der beiden Gründe. Verallgemeinerte Regel: *GitHub-Zugriff bleibt
  Text, weil sein Weg von der Session abhängt; eine rein lokale, deterministische Befehlsfolge darf
  ein Skript sein, wenn ihr Verhalten prüfbar ist.*
- **Merge statt Rebase** — durch AK 4 vorgegeben, nicht abgewogen. Ein Force-Push nach Rebase hängt
  Review-Threads an nicht mehr existierende Commits; die sauberere Historie wäre in einem
  Repositorium, das ohnehin squasht, wertlos.
- **Der Konflikt-Abschlusscommit trägt `--cleanup=strip`** (am laufenden Git nachgemessen, zweimal
  unabhängig bestätigt): `git commit --no-edit` allein lässt die von git angehängte
  `# Conflicts:`-Liste im Commit-Body stehen; sie wanderte in den Squash-Body und verletzte AK 8.
  Präzisiert ADR 0063 Abschnitt 5.
- **Exit `20` verlangt mindestens einen unmerged Pfad** (ebenfalls nachgemessen): Ein
  `pre-merge-commit`-Hook lässt `git merge` mit Exit 1 enden, `MERGE_HEAD` existiert, und es gibt
  **null** Konfliktpfade. „Merge-Exit ≠ 0" auf `20` abzubilden schickte den `developer`
  Konfliktmarker suchen, die es nicht gibt. Ergänzt ADR 0063 Abschnitt 4 um AK 11.
- **Auch der saubere Merge löst den Qualitätscheck aus** — bewusst über den Wortlaut von AK 5 hinaus,
  weil ein semantischer Konflikt keine Textkollision erzeugt und ein PR mit roter CI nach AK 9
  genauso wenig freigabefähig ist wie einer mit Merge-Blocker.
- **Unversionierte Dateien blockieren den Abgleich nicht** (AK 10). Ein Entwicklungslauf hat fast
  immer Streudateien, und ein Abbruch daran träfe ausgerechnet den tragenden zweiten Zeitpunkt.
  Kollidiert eine davon tatsächlich, verweigert git den Merge von sich aus.
- **Mitgenommene Korrektur in `docs/ai-workflow.md`, nicht aus einem Akzeptanzkriterium abgeleitet:**
  Zeile 7b der Schritt-Tabelle nannte weiterhin `Schritt 8: --finalize --pr-number` — ein Rückstand aus
  der Zeit des mit ADR [`0057`](../decisions/0057-board-lebenszyklus-nativ-statt-eigenbau.md) gelöschten
  `gh-board.py`, der seit dessen Wegfall auf ein nicht mehr existierendes Aufrufmuster verweist. Weil
  dieselbe Zeile für den zweiten Abgleich-Zeitpunkt ohnehin angefasst wird, ist die Angabe mitgezogen
  statt in einer zweiten Änderung an derselben Zeile nachgeholt worden. Kein Verhaltensbezug, keine
  weitere Datei betroffen.
- **Ein dritter Zeitpunkt wird nicht eingeführt.** Nach dem letzten Push endet der Lauf; einen
  Zeitpunkt danach kann der Ablauf nicht erreichen. Das ist die bewusst offene Restlücke aus AK 9.
- **`ux-ui-designer` nicht konsultiert (Schritt 2):** Die Story hat keinen konkret benennbaren Bezug
  zu einer sichtbaren Oberfläche — der gesamte Umsetzungsplan besteht aus einem lokalen Git-Skript,
  zwei Skill-/Agenten-Dateien und Dokumentation.
- **`architect` konsultiert (Schritt 1), `test-engineer` und `security-engineer` konsultiert
  (Schritt 3).** Keine Konsultation übersprungen außer der genannten.
- **Board-Gate in Schritt 0 nicht auswertbar:** `board-status-und-prioritaet-lesen` ist in der
  Cloud-Session über keinen Weg erreichbar (dokumentierte Eigenschaft der Umgebung, `github-access`).
  Der Statuswechsel auf `In Progress` steht deshalb unter `## Lokal nachzuholen`.

## Offene Fragen

- **Soll ein Konflikt an der zweiten Aufrufstelle (`ship-feature` Schritt 8) in einem
  sicherheitstragenden Pfad einen erneuten `review-security`-Lauf auslösen?** Vorgeschlagene
  Pfadliste: `scripts/tests/**`, `.github/workflows/**`, `.claude/skills/github-access/SKILL.md`,
  `backend/src/photosort/{security,config,rate_limit,main,seed}.py`,
  `backend/src/photosort/api/**`, `backend/src/photosort/opencloud/**`, `.env.example`.
  *Gewinn:* Der einzige unreviewte Inhalt des Ablaufs bekommt genau dann eine Prüfung, wenn er die
  Stellen trifft, an denen das Sicherheitskonzept Zusicherungen macht. *Preis:* gelegentlich ein
  zusätzlicher Review-Lauf am Ende eines ohnehin langen Ablaufs. *Empfehlung des
  `security-engineer`: ja*, aber ausschließlich an der zweiten Aufrufstelle und nur für diese
  Pfadliste. **Nicht Teil dieser Spec** — bis zu einer Entscheidung bleibt es bei der Meldepflicht
  (Konfliktpfade einzeln im Chat-Bericht), die unabhängig davon Muss-Kriterium ist.

## Out of Scope

- **Ein Abgleich nach dem letzten Push.** Nach dem Push endet der Lauf; die Restlücke aus AK 9 bleibt
  bewusst offen.
- **Automatisches Mergen nach `main`.** Unverändert Daniels Entscheidung (AK 7).
- **Rebase, Force-Push oder das Umschreiben veröffentlichter Commits** — durch AK 4 ausgeschlossen.
- **Ein Abgleich innerhalb des `developer`-Laufs** (z.B. nach jedem TDD-Zyklus). Er brächte nichts,
  was die beiden Zeitpunkte nicht abdecken, und verteilte Merge-Commits über den ganzen Branch.
- **Ein erneuter `review-security`-Lauf nach einer Konfliktauflösung** — siehe „Offene Fragen".
