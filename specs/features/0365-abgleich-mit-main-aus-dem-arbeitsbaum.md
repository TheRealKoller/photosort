# 0365 - Der Abgleich mit `main` läuft aus dem Arbeitsbaum durch

**Status:** Implemented ([PR #393](https://github.com/TheRealKoller/photosort/pull/393))
**Erstellt:** 2026-09-10
**Bezug:** GitHub-Issue [`#365`](https://github.com/TheRealKoller/photosort/issues/365), Architekturentscheidung ADR [`0075`](../decisions/0075-abgleich-mit-main-fasst-den-lokalen-main-ref-nicht-mehr-an.md), teilweise abgelöste ADR [`0063`](../decisions/0063-abgleich-mit-main-als-getestetes-lokales-skript-merge-statt-rebase.md), fortgeführte Spec [`0338`](./0338-abgleich-mit-main-vor-der-freigabe.md), `specs/architecture/0002-testkonzept.md`, `specs/architecture/0003-securitykonzept.md`

## Ziel

Der Abgleich eines Feature-Branches mit `main` gehört zu jedem Freigabe-Ablauf und läuft zweimal
je Story (`ship-feature` Schritt 6 und Schritt 8). Hintergrund-Läufe dieses Repositories arbeiten
grundsätzlich in einem eigenen Arbeitsbaum unter `.claude/worktrees/`, während der Haupt-Checkout
meist `main` ausgecheckt hat — der Normalzustand nach jedem Merge. In genau dieser Konstellation
bricht der Abgleich mit Exit `30` ab, nennt drei mögliche Ursachen, von denen keine zutrifft, und
stuft den Fall als einen für Daniel ein. Er ist keiner: Der Ablauf könnte ohne jedes Zutun
fortfahren.

Das kostet zweierlei. Erstens einen Handgriff je Lauf, obwohl der Ablauf autonom laufen soll.
Zweitens, und schwerer wiegend, die Verlässlichkeit der Eskalationsstufe selbst: Eine Meldung, die
„Fall für Daniel" sagt, muss einer sein. Löst sie falsch aus, wird sie beim nächsten Mal weniger
ernst genommen.

Aufgetreten am 2026-09-09 im Ablauf zu Issue #299 (PR #362), danach erneut bei Spec 0300 und bei
Spec 0370 (PR #386). Da die auslösende Ausgangslage der Regelfall ist und nicht die Ausnahme,
wiederholt es sich.

## User Story

Als Entwickler möchte ich, dass der Abgleich mit `main` auch aus einem eigenen Arbeitsbaum heraus
durchläuft, damit ein Hintergrund-Job seine Freigabe ohne Handgriff zu Ende bringt und Daniel nur
bei echten Hindernissen gerufen wird.

## Akzeptanzkriterien

Fachlich aus dem Issue-Body übernommen, von `test-engineer` auf Entscheidbarkeit geschärft — die
Rohfassung ist an fünf Stellen nicht prüfbar formuliert („mit demselben Ergebnis", „weder
Handgriff noch Rückfrage", „sieht genau die Änderungen", „in Bedeutung und Unterscheidbarkeit
unverändert", „die festgehaltene Begründung"). **AK 8 ist neu hinzugekommen:** Kein Kriterium der
Rohfassung deckt ab, was der Abgleich am Haupt-Checkout anrichtet, obwohl genau das der Grund ist,
aus dem `git update-ref refs/heads/main` als Weg ausscheidet.

- [ ] **AK 1 — Durchlauf aus dem Arbeitsbaum.** Der Abgleich mit `main` läuft aus einem Arbeitsbaum
      unter `.claude/worktrees/` heraus vollständig durch, auch wenn der Haupt-Checkout zur selben
      Zeit `main` ausgecheckt hat, und zwar mit demselben Ausgang (`0`/`10`/`20`/`30`) und
      demselben Zustand des Feature-Branches wie aus dem Haupt-Checkout heraus: bei Übernahme genau
      ein neuer Merge-Commit, dessen erster Elternteil der bisherige Kopf ist, Arbeitsverzeichnis
      sauber.
- [ ] **AK 2 — kein Handgriff.** Das Skript endet in dieser Ausgangslage mit `0` oder `10` und
      schreibt bei `0` weder auf stdout noch auf stderr. Die andere Hälfte der ursprünglichen
      Formulierung (der Ablauf fragt nicht bei Daniel nach) ist Ablauftext, den zur Laufzeit ein
      LLM interpretiert, und ausdrücklich **nicht** automatisiert zugesichert.
- [ ] **AK 3 — Review-Diff.** `git diff --name-only origin/main...HEAD` listet nach dem Abgleich
      exakt die Dateien des Feature-Branches, `origin/main` ist Vorfahre von `HEAD`, und alle
      Stellen der Review-Phase nennen genau diese Vergleichsbasis. Der bisher von Hand benutzte
      Behelf (`git merge --no-ff origin/main` bei stehen gelassener Vergleichsbasis) ist damit als
      Lösung ausgeschlossen.
- [ ] **AK 4 — die vier Ausgänge.** Bedeutung und Unterscheidbarkeit bleiben unverändert, je
      Ausgang einschließlich Zustandszusage und Ausgabekanal: `0` stdout und stderr leer; `10`
      sauberes Arbeitsverzeichnis; `20` Konfliktpfade auf stdout, stderr leer; `30` Begründung auf
      stderr, stdout leer, Zustand unverändert.
- [ ] **AK 5 — keine falsche Eskalation mehr.** Der Ausgang „Vorbedingung verletzt" tritt nicht
      mehr auf, wenn `main` in einem anderen Arbeitsbaum ausgecheckt ist, wenn der
      Remote-Tracking-Ref noch gar nicht existiert, oder wenn ein lokaler Branch denselben Namen
      wie der Tracking-Ref trägt; im letzten Fall darf der Ausgang auch nicht fälschlich `0` sein.
      Die Einstufung „Fall für Daniel" bleibt echten Hindernissen vorbehalten.
- [ ] **AK 6 — automatisierte Abdeckung.** Das Zusammenspiel aus eigenem Arbeitsbaum und
      gleichzeitig ausgechecktem `main` ist auf beiden Ebenen abgedeckt: verhaltensseitig auf einer
      Fixture mit zwei Arbeitsbäumen samt Gegenprobe, dass die alte Refspec dort nachweislich
      scheitert, und statisch darüber, dass das Refspec-Ziel unter `refs/remotes/` liegt und kein
      Schreibzugriff auf `refs/heads/main` im Skript steht.
- [ ] **AK 7 — Begründung deckt sich mit dem Verhalten.** In allen vier Artefakten: ADR 0063
      (Teil-Vermerk), ADR 0075, der Kopfkommentar von `scripts/merge-main-into-branch.sh` (er zählt
      die Ursachen des Fetch-Fehlschlags auf und benennt, was das Skript nie tut) und die Sektion
      „Bash-Skript mit echter Verzweigung" im Testkonzept. Der Kopfkommentar ist die einzige dieser
      Stellen, die dem Code direkt widersprechen kann — Review-Gegenstand, kein Test.
- [ ] **AK 8 — Unversehrtheit des Haupt-Checkouts (neu).** Der Abgleich schreibt `refs/heads/main`
      nie. Nach jedem Ausgang — auch bei offenem Konflikt und nach dessen Abbruch — sind im
      Haupt-Checkout `refs/heads/main` und `HEAD` unverändert und `git status --porcelain` leer.

## Datenmodell-Bezug

Nicht relevant. Die Story berührt kein Anwendungs-Datenmodell, keine Entität und keine
Persistenz — Gegenstand sind ein lokales Shell-Skript, seine Tests und die Vergleichsbasis in
Ablauftexten unter `.claude/`. `docs/architecture.md` und `docs/setup.md` bleiben unverändert (der
Abgleich kommt dort nicht vor).

## Architektur / Umsetzung

**Gewählter Ansatz (ADR [`0075`](../decisions/0075-abgleich-mit-main-fasst-den-lokalen-main-ref-nicht-mehr-an.md), löst Abschnitt 3 von ADR [`0063`](../decisions/0063-abgleich-mit-main-als-getestetes-lokales-skript-merge-statt-rebase.md) teilweise ab):**
Der Abgleich fasst `refs/heads/main` nie mehr an. Geholt wird mit
`git fetch --quiet origin "+refs/heads/main:refs/remotes/origin/main"`, gemerged wird
`refs/remotes/origin/main`, und die Vergleichsbasis der gesamten Review-Phase wird
`origin/main...HEAD`. Damit verschwindet die Ursache („ein anderer Arbeitsbaum hält den Ref"),
statt abgefangen zu werden — ein Pfad, eine Basis, keine Fallunterscheidung.

Die Alternative „Refspec behalten, Fehlerfall erkennen und ausweichen" ist verworfen: Im
Ausweichfall bliebe `refs/heads/main` stehen, während `origin/main` gemerged wäre; die
Review-Phase müsste ihre Basis lageabhängig wählen. Genau dort wäre der Fehler still —
`main...HEAD` zeigte fremde Dateien, alle Prüfer blieben grün. `git update-ref refs/heads/main`
ist ausgeschlossen (der Ref wanderte, Index und Arbeitsbaum des Haupt-Checkouts blieben stehen).

**Gemessene Grundlage** (git 2.55.0, zwei Arbeitsbäume, bares `origin`; die Messreihe steht
vollständig im Kontext-Abschnitt von ADR 0075): `git fetch origin main:main` aus dem Arbeitsbaum →
Exit 128; die Tracking-Refspec → Exit 0 bei unverändertem `refs/heads/main` und sauberem
Haupt-Checkout; `origin/main...HEAD` nach dem Merge → exakt die Branch-Dateien, `main...HEAD` →
zusätzlich die zwischenzeitlich auf `main` entstandene Datei; umgeschriebenes `main` → Fetch mit
`+` läuft durch, `merge-base --is-ancestor <vorher> <nachher>` meldet 1.

### Umsetzungsreihenfolge (TDD, jeder Schritt rot vor grün)

1. **Verhaltenstests zuerst** (`scripts/tests/test_merge_main_into_branch.py`): Zwei-Arbeitsbaum-
   Fixture plus Gegenprobe anlegen → rot, weil das Skript noch `main:main` fetcht.
2. **Skript umstellen** (`scripts/merge-main-into-branch.sh`) → grün.
3. **Statische Verdrahtungsprüfung** (`scripts/tests/test_main_abgleich_verdrahtung.py`):
   Zusicherung von „Refspec vorhanden" auf „Refspec-Ziel liegt unter `refs/remotes/`, und nirgends
   steht ein Schreibzugriff auf `refs/heads/main`" umbauen, inkl. Gegenprobe je Musterfamilie und
   Mutationsnachweis **nach** Grün.
4. **Die acht Prosa-Fundstellen** der Vergleichsbasis umstellen.
5. **Bestandstests nachziehen**, die die alte Semantik festhalten (Liste unter „Teststrategie").
6. **Doku** (AK 7).

### Änderungen am Skript `scripts/merge-main-into-branch.sh`

- Neue Konstante für den Tracking-Ref (`readonly TRACKING_REF="refs/remotes/origin/main"`); alle
  Ref-Nennungen **voll qualifiziert**, damit ein lokaler Branch namens `origin/main` die Auflösung
  nicht mehrdeutig machen kann. Das ist keine Kosmetik, sondern die Zusicherung selbst: Gemessen
  löst `git rev-parse origin/main` bei existierendem `refs/heads/origin/main` auf **diesen** auf
  (nur Warnung auf stderr), und `merge-base --is-ancestor` meldete dann `0` — das Skript hätte
  „`main` ist bereits enthalten" für einen Stand gemeldet, den es nie geholt hat.
- Vor dem Fetch den bisherigen Stand merken:
  `tracking_vorher="$(git rev-parse --verify --quiet "$TRACKING_REF" || true)"`.
- Fetch: `git fetch --quiet "$REMOTE" "+refs/heads/$HAUPTZWEIG:$TRACKING_REF"`. Fehlschlag → Exit
  `30`, Meldung nennt jetzt nur noch **zwei** Ursachen (Remote nicht erreichbar, `$HAUPTZWEIG`
  dort nicht vorhanden) — die dritte („lokal nicht vorspulbar") entfällt hier und wird stattdessen
  gemessen. Selbst erzeugter Text wie bisher, nie rohe git-Ausgabe.
- Nach dem Fetch: `git rev-parse --verify --quiet "$TRACKING_REF"` als Gürtel-und-Hosenträger →
  fehlt er, Exit `30`.
- **Umschreib-Prüfung, gemessen statt geraten:** ist `tracking_vorher` nicht leer,
  `git merge-base --is-ancestor "$tracking_vorher" "$TRACKING_REF"` auswerten. Rückgabe `0` →
  weiter; Rückgabe `1` → Exit `30` mit einer Meldung, die **genau diese eine** Ursache nennt
  („`main` auf `origin` wurde umgeschrieben"); jede andere Rückgabe → Exit `30` im Stil des
  bestehenden „hier wurde nichts gemessen"-Pfades. Der leere Vorher-Stand ist ein **eigener,
  ausgeschriebener Zweig**, keine Klammerbemerkung: Gemessen liefert
  `git merge-base --is-ancestor "" <ref>` Rückgabe `128`, ein ungeprüft eingesetzter leerer Wert
  machte also jeden frischen Klon zu einem falschen Exit `30` — genau die Fehlmeldung, gegen die
  diese Story geschrieben ist.
- No-Op-Rechnung: `git merge-base --is-ancestor "$TRACKING_REF" HEAD` (Verzweigung 0/1/sonst
  unverändert).
- Merge: `git merge --no-ff --no-edit -m "$MERGE_NACHRICHT" "$TRACKING_REF"`.
- Kopfkommentar nachziehen (die „drei möglichen Ursachen" stimmen nicht mehr; ergänzen, dass
  `refs/heads/main` nie geschrieben wird und warum die Refspec ausgeschrieben statt als
  `git fetch origin main` steht). Die Erläuterung gehört auf **eigene Zeilen**, nicht hinter Code:
  `wirksame_zeilen` in der Verdrahtungsprüfung schneidet nur ganzzeilige Kommentare weg.
- **Unangetastet bleiben:** das `unset` der `GIT_*`-Variablen direkt nach `set -euo pipefail`, die
  Argumentlosigkeit, alle fünf Vorbedingungen, „kein Push / kein Rebase / kein `commit --amend` /
  kein `reset --hard` / `main` wird nie ausgecheckt", die Entscheidung an Exit-Codes und
  Dateizuständen statt an Ausgabetexten von git, die feste einzeilige `chore:`-Merge-Nachricht und
  die vier Ausgänge (AK 4). Das `+` in der Refspec ist kein `--force` auf einen Branch: Es betrifft
  ausschließlich einen Ref unter `refs/remotes/` und ist gegenüber dem Remote rein lesend. Es wird
  ausdrücklich **nicht** als `--force` geschrieben — das machte die Abwesenheitsprüfung im Required
  Check `demo-scripts` rot und wird nicht gebraucht.

### Die acht Fundstellen der Vergleichsbasis (`main...HEAD` → `origin/main...HEAD`)

`.claude/skills/ship-feature/SKILL.md:41`, `.claude/skills/review/SKILL.md:38`,
`.claude/skills/review-tests/SKILL.md:8`, `.claude/skills/review-requirements/SKILL.md:8`,
`.claude/skills/review-security/SKILL.md:8`, `.claude/skills/review-architecture/SKILL.md:8`,
`.claude/skills/review-ux/SKILL.md:8`, `.claude/agents/developer.md:87`. Reine Ersetzung der
Diff-Form, keine Umformulierung drumherum; die Drei-Punkt-Form bleibt (sie hält den Diff auch dann
korrekt, wenn `origin/main` nach dem Abgleich weiterläuft). Ein zweiter, situationsabhängiger
Vergleichsweg wird **nicht** eingeführt.

Bewusst **nicht** gehärtet wird die Prosa gegen den mehrdeutigen Refnamen
(`refs/remotes/origin/main...HEAD` in acht Skill-Texten). Im Skript ist die volle Qualifizierung
Pflicht, weil dort Exit `0` fail-open ist; in der Prosa wäre sie Lärm gegen ein Restrisiko, das im
Diff sichtbar wäre.

### AK 7 — festgehaltene Begründung nachziehen

- **ADR 0075** (neu) hält die Entscheidung samt Messwerten fest.
- **ADR 0063** trägt den Kopf-Vermerk `**Teilweise abgelöst:**` (Abschnitt 3 + der daran hängende
  Konsequenz-Punkt); Entscheidungstext unverändert — Mechanismus aus `specs/README.md`.
- **`docs/architecture.md` / `docs/setup.md`:** keine Änderung.
- **`docs/ai-workflow.md`**, Satz unter der Ablauftabelle: „…und zieht dabei den lokalen
  `main`-Ref mit, damit `git diff main...HEAD` …" ist nach der Änderung falsch und wird auf
  `origin/main` umgestellt, mit Verweis auf ADR 0075. Das ist die einzige Stelle in `docs/`, die
  vom Verhalten spricht.
- **`specs/architecture/0002-testkonzept.md`** und **`specs/architecture/0003-securitykonzept.md`**
  sind im Rahmen dieser Spec bereits nachgezogen (siehe „Teststrategie" und „Security").
- **Spec 0338** bleibt als Zeitdokument unverändert (`Implemented`); die Abweichung ist über den
  Teil-Vermerk in ADR 0063 auffindbar.

## Teststrategie

Zwei Ebenen, wie bei Spec 0338 etabliert; das Testkonzept ist mit einem datierten Nachtrag zur
Sektion „Bash-Skript mit echter Verzweigung" bereits nachgezogen (drei bisherige Zusagen kehren
sich dort um).

**Verhalten** (`scripts/tests/test_merge_main_into_branch.py`, echtes Wegwerf-Repositorium, kein
Netz): Die Fixture bekommt eine **zweite Bauform** — Haupt-Checkout auf `main`, verbundener
Arbeitsbaum auf dem Feature-Branch, Skript läuft im verbundenen. Über beide Bauformen läuft der
Ausgangs-Kern (`0`/`10`/`20`/Fehlerfamilie); der lange Rest (Umlautpfad, `diff.relative`,
`--cleanup=strip`, Secret-Leck, `merge-base`-Shim) bleibt einläufig, die
Vorbedingungs-Parametrisierung bleibt am Einzel-Checkout (`main` auszuchecken ist im Arbeitsbaum
unmöglich und erzeugte einen Fixture-Fehlschlag, den ein Leser für einen Befund hielte). Pflicht
dazu: die **Gegenprobe**, dass `git fetch origin main:main` in derselben Lage mit Exit 128
scheitert — sonst belegt der Test nur, dass irgendein Repositorium funktioniert. Zustandsdateien
über `git rev-parse --absolute-git-dir` (`.git` ist im verbundenen Arbeitsbaum eine **Datei**),
Hooks über `--git-common-dir` (zwei verschiedene Helfer, nicht einer). `Momentaufnahme` nimmt
`refs/heads/main` auf, `refs/remotes/origin/main` ausdrücklich **nicht** — der bewegt sich
planmäßig.

Zugesichert nach Exit `10`: `git merge-base --is-ancestor refs/remotes/origin/main HEAD` = 0
**und** `git diff --name-only origin/main...HEAD` = genau die Branch-Dateien — mit der Gegenprobe
im selben Lauf, dass dieselbe Messung über die alte Basis `main...HEAD` die zwischenzeitlich auf
`main` entstandene Datei mitliefert. Ohne die `is-ancestor`-Hälfte bliebe der schmale Diff auch
dann grün, wenn gar nichts übernommen wurde (der veraltete lokale `main` gemerged statt
`origin/main` — die naheliegende Halbumsetzung). Dazu die Unversehrtheit des Haupt-Checkouts
(AK 8), auch bei offenem Konflikt und nach `merge --abort`.

**Drei neue Pflichtfälle**, alle gemessen, alle aus der Familie „fail-open oder falsch eskaliert":
Tracking-Ref existiert noch nicht (`merge-base --is-ancestor "" HEAD` endet 128); ein lokaler
Branch namens `origin/main` (unqualifiziert löst git auf ihn auf und meldet „bereits enthalten" —
Exit `0` fail-open); umgeschriebenes `main` (mit `+` Exit 0 + `is-ancestor` 1 → Exit `30` mit
einer Ursache, ohne `+` Exit 1 und wegen `--quiet` stumm).

**Anzupassen im Bestand:** `branch_diff()`; `test_nach_dem_abgleich_zeigt_main_head_...`
(Assertion umgedreht + umbenannt); `test_gegenprobe_ohne_refspec_...` (Aussage getauscht — die
alte Gegenprobe ist ab jetzt die *richtige* Implementierung; zweiter Spielplatz entfällt);
`test_no_op_bleibt_still_...` (Setup muss über den **Pfad** des baren `origin` fetchen — über den
Remote-Namen zieht git den Tracking-Ref opportunistisch mit und der Test verliert **still** seinen
Gegenstand); `_main_nicht_vorspulbar` samt `test_bei_nicht_vorspulbarem_main_...` (auf Tracking-Ref
umgebaut: regulär holen → auf `origin` umschreiben und force-pushen → Skript läuft, plus die
zugestandene Bewegung des Tracking-Refs als eigene Assertion); `test_merge_abort_...`;
**zusätzlich, vom `architect` nicht erfasst:** `test_sauberer_merge_...` (`HEAD^2` gegen den
Tracking-Ref) und `test_branch_vollstaendig_in_main_enthalten_...` (sonst trivial grün, und
`--no-ff` prüft nichts mehr); der Hook in `test_merge_scheitert_ohne_konflikt_...` wandert nach
`--git-common-dir`.

**Statisch** (`scripts/tests/test_main_abgleich_verdrahtung.py`): Die Zusicherung wandert von
„Refspec vorhanden" auf „Refspec-**Ziel** liegt unter `refs/remotes/`, und nirgends steht ein
Schreibzugriff auf `refs/heads/main`". Vier Bauregeln, damit sie nicht aus dem falschen Grund grün
ist: (a) geprüft wird die eine `fetch`-Zeile, nicht der Skripttext, Anzahl-Zusicherung bleibt
tragend; (b) das Ziel ist die Hälfte hinter dem letzten `:`, sonst ist
`+refs/remotes/origin/main:main` grün; (c) `readonly`-Literale werden vor dem Vergleich aufgelöst,
und bleibt danach eine `$`-Expansion stehen, ist **das ein Befund**, kein Freispruch; (d) die
Abwesenheitsprüfung ist eine Musterfamilie (`update-ref` auf `refs/heads/…`,
`branch -f`/`--force`/`-M`/`-m`, `symbolic-ref`, jede `fetch`-Refspec mit Ziel außerhalb
`refs/remotes/`) mit je einer Gegenprobe und dem Nachweis, dass eine ganzzeilige Doku-Zeile im
Kopfkommentar den Prüfer nicht rot färbt.

**Neu: ein Prüfer über die acht Prosa-Fundstellen** — unter `.claude/` keine Fundstelle
`main...HEAD` ohne vorangestelltes `origin/`, und jede der acht Dateien führt die neue Form, mit
Untergrenze für den Suchraum und Gegenprobe in beide Richtungen an synthetischem Text. Geprüft
wird eine Befehlsform, die dasteht oder nicht — keine aus Prosa herausgelesene Absicht.

**Mutationsnachweise nach Grün** (nicht der triviale Rot-Lauf auf dem Altbestand), einschließlich
der beiden **Nicht**-Reaktionen: `+` entfernt → darf nicht rot werden (der Prüfer verbietet das
Ziel, nicht die Erzwingung); eine neunte Datei mit `origin/main...HEAD` ergänzt → nicht rot (der
Prüfer friert keine Dateiliste ein). Dazu: Refspec-Ziel zurückgedreht, Refspec in eine nicht
auflösbare Variable ausgelagert, `update-ref`/`branch -f`/`symbolic-ref` eingesetzt, eine der acht
Fundstellen zurückgedreht. `'git fetch --quiet origin main:main'` wandert aus der grünen
Parametrisierung (`test_die_zugesicherte_fetch_form_bleibt_gruen`) in die **rote** — der billigste
hochwertige Nachweis der ganzen Umstellung.

**Mit erledigt, bewusst und kein Beifang:** `suchraum()` in
`test_main_abgleich_verdrahtung.py` zählt künftig über die von Git verwalteten Dateien auf statt
über `rglob`. Gemessen sieht der Prüfer aus dem Haupt-Checkout heraus **5297 statt 30** Dateien und
findet die Merge-Nachricht an **16 statt an einer** Stelle, weil drei Arbeitsbäume unter
`.claude/worktrees/` liegen — zwei Tests sind damit lokal rot aus einem Grund, der mit ihrem
Gegenstand nichts zu tun hat, und in CI (frischer Klon) fällt das nie auf. Drei Schwestermodule
(`test_board_befehle_in_skills.py`, `test_issue_befehle_in_skills.py`,
`test_github_zugriff_an_einer_stelle.py`) lösen das längst über `git ls-files` und begründen es
wörtlich mit „etwa ein Worktree unterhalb von `.claude/`"; diese Datei ist der letzte Nachzügler.
Ohne die Umstellung ist die von AK 6 geforderte Abdeckung im Alltag nicht ablesbar.

**Bewusst nicht abgedeckt** (steht als benannte Lücke im Testkonzept): dass die Review-Phase die
neue Basis zur Laufzeit auch benutzt — das ist LLM-interpretierter Text, und die Lücke ist
**gefährlicher als vorher**, weil der lokale Ref jetzt altert (früher war die alte Gewohnheit
folgenlos, heute lügt sie). Ebenso, dass ein Hintergrund-Lauf überhaupt im Arbeitsbaum startet.

Ebene und Ort im Übrigen unverändert: `pytest` unter `scripts/tests/`, CI-Job `demo-scripts`, kein
neues Testframework, kein Netzwerk, keine neue Abhängigkeit.

## UI/UX

Nicht relevant. Die Story berührt ausschließlich ein lokales Shell-Skript, dessen Tests, Ablauf-
und Spec-Texte — es gibt keine Stelle, an der etwas angezeigt oder eingegeben wird, keine
Frontend-Komponente und keine neuen darzustellenden Daten.

## Security

**Einordnung: sicherheitsrelevant, aber eng umgrenzt** — nicht am Produkt (kein Anwendungscode,
kein Endpunkt, kein Secret, keine Abhängigkeit, keine Auth- oder Sichtbarkeitsänderung, kein
Foto-/Projektdatenbezug), sondern am Asset **„Integrität des KI-gesteuerten Entwicklungsprozesses"**,
das das Bedrohungsmodell ausdrücklich führt: Die Story bewegt die Vergleichsbasis der gesamten
Review-Phase und ersetzt eine von git durchgesetzte Fail-closed-Eigenschaft durch eine selbst
geschriebene Prüfung. Beides sind Stellen, an denen ein Fehler **still** ist. Gegenüber `origin`
bleibt der Zugriff rein lesend: Eine *Fetch*-Refspec kann nicht auf den Remote schreiben, und das
`+` erzwingt ausschließlich auf der lokalen Seite. `specs/architecture/0003-securitykonzept.md`
ist mit einem vorausschauenden Abschnitt bereits nachgezogen.

**Bedrohung 1 — die Review-Basis wandert auf einen Ref, den das Skript selbst erzwingend
schreibt.** Gemessen, in welche Richtung der Diff kippen kann: zieht `origin/main` regulär weiter →
Diff bleibt exakt der Feature-Diff; wird `origin/main` rückwärts umgeschrieben → Diff **wächst** um
fremde Dateien (laut, nicht still); leer wird er nur, wenn `origin/main` den Branch-Kopf enthält.
Ein stilles Verschwinden von Branch-Änderungen setzt Schreibrecht auf `main` voraus — abgewehrt
durch Branch Protection (`enforce_admins: true`, PR-Pflicht, `allow_force_pushes: false`). Keine
Verschärfung gegenüber vorher (der lokale `main`-Ref war als Basis genauso lokal fälschbar), **aber**
der Grund, warum die Umstellung vollständig sein muss.
*Prüfbar:* alle acht Prosa-Fundstellen umgestellt, kein lageabhängiger zweiter Vergleichsweg; die
beiden Verhaltenstests aus der Teststrategie; statisch Refspec-Ziel und Abwesenheitsfamilie.

**Bedrohung 2 — die Umschreib-Prüfung ist Diagnose, keine Sicherheitszusage.** Gemessen: ohne `+`
scheitert die Refspec bei umgeschriebenem `main` (Exit 1, Ref unverändert), mit `+` läuft sie durch
(Exit 0), und `merge-base --is-ancestor <vorher> <nachher>` liefert dann 1. Die Prüfung stellt also
her, was git vorher selbst tat — mit drei blinden Stellen, die niemand später für eine Zusage
halten darf: (a) **kein Vorher-Stand** (frischer Klon/Arbeitsbaum) heißt „keine Messung", nicht
„geprüft"; (b) ein **paralleler `git fetch`** aus einem anderen Arbeitsbaum bewegt den Ref zwischen
Merken und Prüfen (geteilter Ref-Speicher); (c) sie vergleicht lokale Ref-Stände, nicht die
Echtheit des Remote-Inhalts. Der eigentliche Schutz bleibt Branch Protection + PR-Pflicht.
*Prüfbar:* Rückgabe `0` → weiter, `1` → Exit `30` mit der einen Ursache, **jede andere** → Exit
`30` „hier wurde nichts gemessen"; der leere Vorher-Stand ist ein eigener, ausgeschriebener Zweig;
je Rückgabeklasse ein Test.

**Bedrohung 3 — zwei neue Fehlerpfade auf dem Kanal, der nur selbst erzeugten Text tragen darf.**
Der Bestand ist hier **nicht lückenlos**:
`git merge-base --is-ancestor "$HAUPTZWEIG" HEAD || vorfahre_rueckgabe=$?` (Zeile 100 in
`scripts/merge-main-into-branch.sh`) leitet stderr nicht um; im 128-Fall schreibt git dort einen
rohen `fatal:`-Text auf genau den Kanal, den `ship-feature` in Chat-Bericht und `SendMessage`
übernimmt. Die Story schreibt diese Zeile ohnehin um und fügt zwei gleichartige hinzu.
*Prüfbar:* alle drei Prüfungen und das Merken des Vorher-Standes verschlucken ihre Ausgabe
(`>/dev/null 2>&1` bzw. `rev-parse --verify --quiet … || true`); die `fetch`-Zeile behält ihre
Umleitung; keine neue Meldung nennt die Remote-URL oder zitiert einen git-Text. Commit-Hashes und
der Literal `origin` sind unbedenklich, `git remote get-url`-Ausgabe nie (credential-behafteter
Remote = Secret-Leck).

**Bedrohung 4 — `GIT_*`-Härtung bleibt wirksam, aber unverändert unvollständig.** Voll
qualifizierte Refs unter `refs/remotes/` ändern daran nichts: Der Hebel ist nicht, *welcher* Ref
geschrieben wird, sondern *in welchem Repositorium* und *unter welcher Konfiguration*. Das `unset`
bleibt unverändert direkt nach `set -euo pipefail`. `GIT_CONFIG_GLOBAL` bleibt weiterhin ungedeckt
(trägt `core.hooksPath` und `url.<base>.insteadOf`) — bestehendes, bewusst getragenes Restrisiko,
von dieser Story weder verbreitert noch verengt.

**Ausdrücklich ohne Befund.** Hereingezogener Inhalt führt weiterhin keinen Code aus (`origin/main`
und `main` sind inhaltlich derselbe Commit; Merge-Treiber kommen aus der Konfiguration, Hooks aus
`.git/hooks`/`core.hooksPath`, `git fetch` überträgt weder das eine noch das andere).
Konfliktauflösung bleibt der einzige unreviewte Inhalt, mit denselben Auflagen wie bisher
(Konfliktpfade einzeln in den Chat-Bericht, nie in den PR-Body; `git add <Pfade>` statt
`git add -A`).

## Entscheidungen

- **Ansatz (Schritt 1, `architect`):** Vergleichsbasis durchgängig auf `origin/main`, statt den
  Fehlerfall abzufangen — eine Basis für alle Lagen schlägt zwei Pfade mit einem LLM als Weiche.
  Festgehalten als ADR 0075; ADR 0063 trägt einen `**Teilweise abgelöst:**`-Kopf.
- **`ux-ui-designer` nicht konsultiert (Schritt 2):** Die Story berührt ausschließlich ein
  Shell-Skript, dessen Tests sowie Skill-, Agenten- und Spec-Texte. Es existiert keine Stelle, an
  der etwas angezeigt oder eingegeben wird, keine berührte Frontend-Komponente und keine neuen
  Daten, die irgendwo dargestellt würden — also kein konkret benennbarer Bezug zu einer sichtbaren
  Oberfläche.
- **`test-engineer` konsultiert (Schritt 3):** AK 6 verlangt automatisierte Abdeckung eines
  nicht-trivialen Zusammenspiels. Er hat drei Pflichtfälle ergänzt, die der `architect` nicht
  hatte, zwei zusätzliche Bestandstests gefunden, die sonst still trivial grün geworden wären, und
  einen eigenständigen Defekt am Bestand aufgedeckt (`rglob`-Suchraum zählt Arbeitsbäume mit).
- **`security-engineer` konsultiert (Schritt 3):** Das Skript trägt eine explizite Härtung gegen
  `GIT_DIR`/`GIT_WORK_TREE`-Unterschiebung und eine Zusicherung gegen Secret-Lecks aus rohen
  git-Ausgaben; die Änderung fasst genau diesen Fetch-Pfad an. Er hat eine bestehende Lücke auf dem
  Meldungskanal gefunden (Zeile 100, stderr nicht umgeleitet), die diese Story mit erledigt.
- **ADR 0075, Messpunkt korrigiert:** Die erste Fassung behauptete, die konfigurierte
  Standard-Refspec feuere nicht mit, sobald eine Refspec auf der Kommandozeile steht.
  `test-engineer` und `security-engineer` haben das unabhängig voneinander widerlegt
  (opportunistische Aktualisierung); der Punkt ist in ADR 0075 als eigener Messpunkt 6 richtig-
  gestellt und die daraus gezogene Begründung eng gefasst. Die Entscheidung selbst bleibt
  unberührt.
- **Keine Rückfrage an Daniel nötig:** Alle Entscheidungen waren technischer Natur innerhalb der
  bereits akzeptierten Abgleich-Strategie und durch Messungen am laufenden git entschieden — keine
  neue Abhängigkeit, kein Datenmodell, kein neu zu akzeptierendes Restrisiko, kein Produkt-
  Trade-off.

## Offene Fragen

Keine.

## Out of Scope

- **`spec-writer` Schritt 4** zweigt mit `git fetch origin && git checkout main && git pull` ab —
  das scheitert in einem Arbeitsbaum aus derselben Wurzel („`main` ist bereits ausgecheckt in …").
  Anderer Ablaufschritt, anderes Ziel, eigene Story. Hier wird er nicht angefasst.
- **Der lokale `main`-Ref wird nicht mehr gepflegt** und altert dadurch. Kein Ablaufschritt zieht
  ihn nach; das ist Folge der Entscheidung, nicht eine zu behebende Lücke.
- **Härtung der acht Prosa-Fundstellen gegen den mehrdeutigen Refnamen** (voll qualifizierte Form
  in Skill-Texten) — dokumentiert statt geschlossen, siehe „Architektur / Umsetzung".
- **`GIT_CONFIG_GLOBAL`** bleibt ungedeckt; bestehendes Restrisiko, von dieser Story unberührt.
