# 0392 - Ein Entwurfsrundenlauf endet auf Wunsch mit einem eröffneten Pull Request

**Status:** Accepted
**Erstellt:** 2026-09-11
**Bezug:** [GitHub-Issue #392](https://github.com/TheRealKoller/photosort/issues/392), ADR [`decisions/0077-entwurfslauf-endet-im-pull-request-uebergabe-per-anker.md`](../decisions/0077-entwurfslauf-endet-im-pull-request-uebergabe-per-anker.md)

## Ziel

Ein Entwurfsrundenlauf endet heute mit einem gepushten Branch und sonst nichts. Was der Lauf im
Repository verändert hat, liegt damit außerhalb jedes Reviews, und es bleibt Daniel überlassen,
den Pull Request von Hand nachzuschieben oder den Branch liegen zu lassen — beim Lauf zur
Fotoansicht ist genau das passiert. Der Abschluss soll deshalb bis zum eröffneten Pull Request
reichen, ohne dass der Entwurfsablauf selbst GitHub berührt.

## User Story

Als Gestalter möchte ich einen fertigen Entwurfsrundenlauf auf Wunsch mit einem eröffneten Pull
Request abschließen, damit die Arbeit nicht als loser Branch liegen bleibt und ich nach dem Lauf
keinen Handgriff mehr nachholen muss.

## Akzeptanzkriterien

Legende: **[M]** mechanisch geprüft · **[S]** Sichtprüfung · **[—]** bewusst nicht prüfbar

- [ ] **[M/S]** Erklärt Daniel einen Lauf für **fertig**, wird **genau einmal** gefragt, ob ein Pull Request eröffnet werden soll. Die Frage steht in einem **eigenen Schritt zwischen** Abschluss- und Aufräumschritt und ersetzt keinen bisherigen Abschlussinhalt. Die Antwortmöglichkeit „ja" nennt ihre Folge mit (`Closes #NNN` bzw. keine Verknüpfung und keine Board-Bewegung). *(Dass der eigene Schritt existiert, genau eine `AskUserQuestion`-Stelle trägt und die Folge wörtlich mitnennt: [M] über Überschrift und Zeichenoffsets. Dass zur Laufzeit gefragt wird und nur einmal: [S].)*
- [ ] **[M/S]** Bei „nein" bleibt es beim heutigen Verhalten: Auskunft über Arbeitsseite, Runden/Vorschläge und Ergebnis, kein Pull Request. *(Dass die Auskunftsteile des Aufräumschritts wörtlich unverändert dastehen: [M]. Das Verhalten: [S].)*
- [ ] **[M/S]** Beim **Abbruch** wird nicht gefragt und kein Pull Request eröffnet. *(Geprüft als **Kardinalität, nicht als Abwesenheit**: Der Übergabeanker kommt im Skilltext **genau einmal** vor, und der Offset dieses Vorkommens liegt zwischen der Überschrift des Fertig-Schritts und der des Aufräumschritts; zusätzlich steht der Bedingungssatz wörtlich in diesem Schritt: [M]. Dass der Schritt im Abbruchfall übersprungen wird: [S].)*
- [ ] **[M]** Die Erlaubnisstufe des Rundenablaufs bleibt **wörtlich** „kein GitHub-Zugriff". `ship-entwurf` trägt „lesend und schreibend" und nennt **ausschließlich Operations-IDs** aus `github-access` — keinen Werkzeugnamen, keinen Befehl.
- [ ] **[M/S]** Bei „ja" schreibt der Ablauf den **Übergabeblock** und hört damit auf; die Hauptsession erkennt den Anker und ruft `ship-entwurf`. Der Block samt Feldnamen ist **an genau einer Stelle definiert** (im erzeugenden Skill, als umzäunter Block); `ship-entwurf` führt nur die **Ankerzeile** in seiner Auslöseliste, als Inline-Code, nicht als eigene `##`-Überschrift. *(Einzige Definitionsstelle, Ankerzeile in beiden Dateien wortgleich, keine zweite Blockkopie: [M]. Dass die Hauptsession den Anker erkennt: [S].)*
- [ ] **[M/S]** Vor jedem Schreibzugriff steht die Bestandsaufnahme; jeder Pfad wird gegen die geschlossene Zulassungsmenge `design/penpot/**`, `frontend/penpot/**`, `specs/**` geprüft, jeder Pfad außerhalb hält an (kein Commit, kein Push, kein Pull Request). Die geprüfte Menge wird **selbst gemessen** (`git status --porcelain` plus `git diff --name-only origin/main...HEAD`); die Zeile `Geänderte Dateien` des Übergabeblocks wird dafür **nicht gelesen**. *(Präfixe, Ausschlüsse und Vergleichsbasis wörtlich: [M]. Dass tatsächlich angehalten wird: [S].)*
- [ ] **[M]** Der Commit ist **pfadgenau** über die gemessenen Pfade: kein pauschales Hinzufügen (`git add -A`), kein Commit über den Arbeitsbaum (`git commit -a`). Ohne dieses Kriterium ist die Zulassungsmenge Zierde.
- [ ] **[M/S]** **Wächter-Halt:** `ship-entwurf` hält zusätzlich an, wenn der gemessene Diff (a) eine **neue** `*.js`-Datei unter `design/penpot/` enthält oder (b) hinzugefügte/entfernte Zeilen in `frontend/penpot/payload.test.ts` enthält, die `VERBOTENE_BEZEICHNER`, `BEZEICHNER_FREIGABEN`, `bezeichner:` oder `muster:` berühren. Grund: Nutzlast und ihre Verbotsliste liegen beide in der Zulassungsmenge — ein Pull Request mit Nutzlast-Zeile *und* passender Freigabe wäre sonst grün und sähe keinen Prüfer. *(Die beiden Fälle wörtlich im Skilltext, prüfbar an `git diff -U0`: [M]. Dass angehalten wird: [S].)*
- [ ] **[M/S]** Vor dem Commit wird die gemessene Pfadmenge gegen dasselbe Bilddatei-Muster geprüft, das die CI verwendet (`\.(png|jpe?g|gif|webp|bmp|tiff?|avif|heic|ico)$`, ohne Beachtung der Groß-/Kleinschreibung); ein Treffer hält an. Grund: Der CI-Schritt ist ein Detektor **nach** dem Push, und ein roter Check nimmt einen gepushten Blob nicht zurück.
- [ ] **[M/S]** Abgleich mit `main` über `scripts/merge-main-into-branch.sh` **nach** dem Commit und **vor** dem Push; Exit `0` weiter, `10` weiter mit Zeile im Bericht, `20` und jeder andere Code: anhalten, nichts pushen. Konfliktpfade gehen einzeln in den Chat-Bericht, nie in den Pull-Request-Body; keine Meldung zitiert rohe `git`-Ausgabe oder nennt die Remote-URL. *(Skriptpfad, Reihenfolge über Offsets, die drei Exit-Fälle wörtlich: [M]. Die Auswertung selbst: [S].)*
- [ ] **[M/S]** Der Pull Request trägt Titel `chore(design): <Beschreibung>` und einen Body nach `.github/pull_request_template.md` mit **Arbeitsseite** und **Ergebnis-Ansicht**; beide Namen stammen aus dem validierten `entwurfslauf` (`^[a-z0-9][a-z0-9-]{2,39}$`) bzw. aus `anzeigename`/`schluessel` in `views.json`, **nicht** aus einem Penpot-Rücklesen. Brettnamen, Beschreibungen und Rundentexte gelangen nicht in den Body. Gemessene `specs/`-Pfade werden **einzeln und getrennt** von den Entwurfs-Nachträgen benannt. *(Titelform, beide Muster, Herkunftsregel, getrennte Nennung: [M]. Der tatsächliche Body: [S].)*
- [ ] **[M/S/—]** Mit Story trägt der Body `Closes #NNN`, Nummer geprüft gegen `^[0-9]+$` **und** `^[1-9][0-9]{0,5}$`; ohne Story entfällt die Zeile, der Pull Request entsteht trotzdem und wandert dann nicht von selbst auf `Review` — das wird **gemeldet**, nicht durch eigenmächtiges Setzen verdeckt. Board-Rücklesen nur mit Story; bleibt der Wert aus, wandert `board-status-setzen` in `## Lokal nachzuholen` samt festem Satz. *(Abschnitt und fester Satz: [M]. Die tatsächliche Board-Bewegung: [—].)*
- [ ] **[M]** Der Pull Request durchläuft **keine** Perspektivenrunde und **kein** angefordertes Copilot-Review. *(Geprüft als **Gleichheit einer geschlossenen Whitelist**, nicht als Verbotsliste: Die Menge der in `ship-entwurf` genannten Operations-IDs ist gleich `{pr-erstellen, board-status-und-prioritaet-lesen, board-status-setzen}` — ein auftauchendes `copilot-review-anfordern` wird rot, eine vergessene ID ebenfalls. Zusätzlich: `ship-feature` bekommt keinen zweiten Anker in seiner Auslöseliste.)*
- [ ] **[M/S]** Der Aufräumschritt bleibt vollständig (Arbeitsseite, Runden/Vorschläge, Ort des Ergebnisses, Wegwerf-Hinweis, „Zwischenstand nirgends gesichert") und nennt zusätzlich den eröffneten Pull Request, falls es einen gibt. Er trägt weiterhin **keinen** umzäunten Codeblock. *(Wortlaut und Codeblock-Kardinalität: [M]. Die Auskunft im Lauf: [S].)*
- [ ] **[M]** Die abgelöste Festlegung ist **ersetzt, nicht ergänzt**: Der Satz „Beides gehört in denselben Pull Request wie der fertige Entwurf — in die Story, in deren Rahmen der Lauf stattfand" steht nirgends mehr im Skilltext. *(Abwesenheit eines **bekannten Literals** ist mechanisch prüfbar — im Unterschied zur Abwesenheit einer Idee.)*
- [ ] **[M/S]** Ein leerer Diff ist eine Auskunft, kein Fehler: kein Pull-Request-Versuch, sondern Meldung. *(Der Fall steht wörtlich im Skill: [M]. Das Verhalten: [S].)*
- [ ] **[—]** Dass der Pull Request bei GitHub tatsächlich entsteht, die Karte auf `Review` wandert, das Issue beim Merge schließt und ein zweiter Versuch auf einem Branch mit offenem Pull Request eindeutig fehlschlägt. Kein Test dieses Repositories erreicht GitHub; belegt wird das am ersten echten Lauf.

## Datenmodell-Bezug

Nicht relevant. Es entstehen keine neuen Entitäten und keine Änderung an bestehenden; die Story
fasst weder Backend noch Datenbank an. `docs/architecture.md` bleibt unberührt.

## Architektur / Umsetzung

**Diese Spec trägt eine neue ADR:** [`decisions/0077-entwurfslauf-endet-im-pull-request-uebergabe-per-anker.md`](../decisions/0077-entwurfslauf-endet-im-pull-request-uebergabe-per-anker.md). Sie entscheidet die Übergabe per Anker, den eigenen Auslieferpfad, die Zulassungsmenge des Diffs und den begründeten Verzicht auf Perspektivenrunde und Copilot. ADR [`0073`](../decisions/0073-entwurfsrunden-auf-arbeitsseite-aufraeumen-als-handgriff.md) wird dabei **teilweise abgelöst** — Abschnitt 5, letzter Absatz (der Satz, der die Nachträge „in die Story, in deren Rahmen der Lauf stattfand" schob). Alles Übrige von ADR 0073 bleibt wörtlich in Kraft, insbesondere Abschnitt 4 (der Ablauf löscht nichts) und Abschnitt 7 (jederzeit aufrufbar, Erlaubnisstufe „kein GitHub-Zugriff").

**In dieser Spec entsteht kein Produktcode.** Kein `.tsx`, kein Backend, kein Datenmodell, keine Abhängigkeit — `docs/architecture.md` und `docs/setup.md` bleiben unberührt (Penpot ist Werkzeug- und keine Laufzeitabhängigkeit). `docs/ai-workflow.md` ändert sich dagegen **doch**, und zwar minimal: Es gibt ab jetzt einen zweiten Skill mit GitHub-Schreibzugriff, und die Rollen-Landkarte behauptet heute das Gegenteil.

### 1. Die Übergabe: ein wörtlicher Anker, kein eigener Zugriff

Die Erlaubnisstufe **kein GitHub-Zugriff** des Rundenablaufs bleibt wörtlich unverändert. Bei „ja" eröffnet er nichts, sondern schreibt einen Übergabeblock und hört damit auf; die Hauptsession erkennt den Anker und ruft den Auslieferpfad auf. Das ist dasselbe Muster, das `developer` → `ship-feature` bereits trägt (`## Abschlussbericht`, `## Blockiert: Architektur-Konsultation nötig`) — nur ohne Subagenten-Fenster dazwischen: Der Anker überquert eine **Zuständigkeitsgrenze**, keine Prozessgrenze, und ist damit die Stelle, an der ein Text ohne Zugriffsrecht aufhört und einer mit Zugriffsrecht anfängt.

**Der Block wird an genau einer Stelle definiert.** Das ist die bereits geltende Ein-Definitions-Regel (Testkonzept Punkt 8, `test_die_ankerdefinition_steht_ausschliesslich_in_developer_md`): Das Format steht als umzäunter Block **nur im erzeugenden Skill** (`penpot-entwurfsrunden`), und `ship-entwurf` führt in seiner Auslöseliste ausschließlich die **Ankerzeile** als Inline-Code — genau so, wie `ship-feature` es heute mit den `developer`-Ankern hält. Beidseitiges Ausschreiben wäre Doppelpflege und machte den Gleichheitstest wertlos, sobald beide Fundstellen leer sind.

Ankerzeile (wortgleich in beiden Dateien), Blockfelder (nur im erzeugenden Skill):

```
## Entwurfslauf abgeschlossen: Pull Request erwünscht

**Arbeitsseite:** Entwurf — <entwurfslauf>
**Runden und Vorschläge:** <n> Runden, <k> Vorschläge
**Ergebnis-Ansicht:** <anzeigename aus views.json> (`<schluessel>`) | keine
**Story:** #<NNN> | keine
**Geänderte Dateien:** <Pfad>, <Pfad>, …
```

Der Anker **beendet nicht den Lauf**, sondern dessen GitHub-freien Teil: Nach der Rückkehr des Auslieferpfads — mit Pull-Request-Nummer oder mit Fehlschlag — geht es im Aufräumschritt weiter.

**Achtung beim Prüfen der Platzierung:** Der Abschnittsleser `abschnitt()` schneidet am nächsten `\n## ` und kennt keine Code-Zäune — der Übergabeblock **enthält** eine `##`-Zeile. Ein auf `abschnitt()` gestützter Platzierungsnachweis schnitte den Schritt genau am Anker ab. Der Nachweis läuft deshalb über **Zeichenoffsets der Schritt-Überschriften**, nicht über den Abschnittsleser.

### 2. Ein eigener schlanker Skill `ship-entwurf` statt eines zweiten Pfads in `ship-feature`

Neu: `.claude/skills/ship-entwurf/SKILL.md`, Erlaubnisstufe **lesend und schreibend**, Hauptsession, nennt ausschließlich Operations-IDs aus `github-access` (kein `gh`, kein Werkzeugname).

Nachgesehen statt gefühlt entschieden: Von den neun Schritten des `ship-feature`-Ablaufs berührt ein Entwurfslauf **einen** — „committen, abgleichen, pushen, Pull Request". Alles andere (Anker auf `developer`-Berichte, Branch-/Diff-Verifikation gegen einen gemeldeten Stand, `review`-Orchestrator, Findings per `SendMessage`, Folgebericht, Copilot-Runde, Spec-Finalisierung, Recovery bei geschlossenem Subagenten-Fenster) hat keinen Gegenstand. Und **innerhalb** des einen berührten Schritts stimmt die Semantik nicht überein: kein Subagent, an den ein Merge-Konflikt zurückginge; der Branch muss unter Umständen erst entstehen; die Closing-Zeile ist bedingt statt Pflicht. Ein zweiter Einstieg in `ship-feature` wäre also ein Anker mehr plus acht Schritte mit „gilt im Entwurfspfad nicht" — genau die Konstruktion, gegen die ADR 0073 Abschnitt 1 den Rundenablauf aus `penpot-design` herausgehalten hat.

**Gegen Doppelpflege dieselbe harte Regel:** `ship-entwurf` wiederholt aus `ship-feature` nichts, was er nicht selbst ausführt. Die einzige zugestandene Dopplung sind die vier Zeilen Board-Rücklesen (Schritt 9), benannt, weil sie der erste Ort sein werden, an dem Drift auftritt.

### 3. Was `ship-entwurf` tut, in dieser Reihenfolge

1. **Bestandsaufnahme vor jedem Schreibzugriff.** `git status --porcelain`, `git diff --name-only origin/main...HEAD`. Die so **selbst gemessene** Menge ist die einzige Grundlage; die Zeile `Geänderte Dateien` des Übergabeblocks wird dafür nicht gelesen (Begründung im Abschnitt „Security"). Jeder Pfad wird gegen eine **geschlossene Zulassungsmenge** geprüft: `design/penpot/**`, `frontend/penpot/**`, `specs/**`. **Jeder Pfad außerhalb hält den Ablauf an** — kein Commit, kein Push, kein Pull Request, Meldung an Daniel. Ein leerer Diff ist kein Fehler, sondern eine Auskunft: dann entsteht kein Pull Request, statt einen leeren zu versuchen.
2. **Zwei Halte-Prüfungen auf der gemessenen Menge, vor dem Commit.** (a) **Wächter-Halt:** neue `*.js` unter `design/penpot/`, oder hinzugefügte/entfernte Zeilen in `frontend/penpot/payload.test.ts`, die `VERBOTENE_BEZEICHNER`, `BEZEICHNER_FREIGABEN`, `bezeichner:` oder `muster:` berühren (an `git diff -U0` geprüft). (b) **Bilddatei-Halt:** ein Pfad, der auf `\.(png|jpe?g|gif|webp|bmp|tiff?|avif|heic|ico)$` passt.
3. **Branch.** Aktueller Branch ≠ `main` → dieser wird verwendet. Auf `main` → `design/<entwurfslauf>` anlegen. Der Namensteil ist genau der Wert, der ohnehin gegen `^[a-z0-9][a-z0-9-]{2,39}$` validiert ist (ADR 0073, Abschnitt 6a) — der einzige Wert aus der Design-Datei, der unter geschlossenem Muster steht und deshalb einen Befehl steuern darf.
4. **Commit** der gemessenen Pfade, **pfadexplizit** (`git add <Pfade>`, nie `git add -A`, nie `git commit -a`), Conventional Commits.
5. **Abgleich mit `main`** über `scripts/merge-main-into-branch.sh`, nach dem Commit und vor dem Push. Exit `0` → weiter ohne Meldung; `10` → weiter, eine Zeile im Bericht; **`20` (Konflikt) und jeder andere Code → anhalten, nichts pushen, an Daniel melden.** Konflikte werden hier nicht aufgelöst: Es gibt keinen Subagenten, an den sie gingen, und die Kardinalitäten der Nutzlast sind handgepflegte Zahlen.
6. **Push** des Branches.
7. **`pr-erstellen`.** Titel `chore(design): <Beschreibung>` — `chore`, weil ein Entwurfslauf kein ausgeliefertes Produkt-Delta erzeugt und ein `feat`-Titel über `release-please` die Minor-Version für etwas bumpte, das kein Nutzer sieht. Body nach `.github/pull_request_template.md`: was der Lauf verändert hat, **Arbeitsseite** und **Ergebnis-Ansicht**. Beide Namen kommen **nicht** aus einem Penpot-Rücklesen — die Arbeitsseite über den validierten `entwurfslauf`, die Ergebnis-Ansicht über `anzeigename`/`schluessel` aus `views.json`. Brettnamen, Beschreibungen und Runden-Textinhalte gelangen nicht in den Body (Härtungsregel 4.3). Gemessene `specs/`-Pfade werden einzeln und getrennt von den Entwurfs-Nachträgen benannt.
8. **Story-Bezug.** Mit Story: ausgefüllte Zeile `Closes #NNN`, Nummer aus dem Übergabeblock, geprüft gegen `^[0-9]+$` und `^[1-9][0-9]{0,5}$`. Ohne Story: Zeile entfällt (die Vorlage sieht das als Ausnahme vor), der Pull Request entsteht trotzdem und wandert nicht von selbst auf `Review` — **bewusst hingenommen** und gemeldet, nicht durch eigenmächtiges Setzen verdeckt.
9. **Board-Rücklesen, nur mit Story:** einmal `board-status-und-prioritaet-lesen` (Knoten mit `project.number == 8`). Steht nicht `Review`: einmal kurz warten, zweites Mal lesen; dann immer noch nicht → Wert **nicht** selbst nachsetzen, sondern `board-status-setzen` in den Abschnitt `## Lokal nachzuholen`.
10. **Was ausdrücklich nicht passiert:** keine Perspektivenrunde, kein `copilot-review-anfordern`, keine Spec-Finalisierung, kein Merge, kein Schließen eines Issues, kein `Done`.

### 4. Warum der Verzicht auf Review und Copilot vertretbar ist

Der Verzicht ist der einzige unbequeme Teil und hängt an der Reihenfolge: **Zulassungsmenge zuerst, Verzicht danach.** (a) Die CI bleibt vollständig in Kraft — `payload.test.ts`, der Rückleseabgleich gegen `views.json`, Lint, Typprüfung, Coverage-Gate und `pr-titel` laufen wie an jedem anderen Pull Request; entfallen ist die *Perspektivenrunde*, nicht die mechanische Absicherung. (b) Die Diff-Klasse ist geschlossen: kein Backend-Endpunkt, keine Frontend-Komponente, keine Abhängigkeit kann darin liegen, sonst hätte der Pfad angehalten. (c) Gemerged wird von Daniel.

**Die Lücke, die daraus zunächst blieb, ist geschlossen worden, nicht nur benannt:** Nutzlast (`design/penpot/**`) und ihre statische Verbotsliste (`frontend/penpot/payload.test.ts`) liegen beide in der Zulassungsmenge, ein Pull Request mit Nutzlast-Zeile *und* passender Freigabe wäre grün gewesen. Der **Wächter-Halt** aus Schritt 2a fängt genau diese Klasse ab; er ist an `git diff -U0` mechanisch prüfbar und trifft den Regelfall (Kardinalität anheben, `views.json`-Eintrag) nicht. Was als Restrisiko bleibt, steht in den Konsequenzen der ADR und im Sicherheitskonzept.

### 5. Der Umbau in `penpot-entwurfsrunden`

- **Schritt 6 (Abschluss)** bleibt inhaltlich unverändert, abgesehen von der Streichung des abgelösten Satzes (siehe vorletztes Akzeptanzkriterium).
- **Neuer Schritt 7 „Pull Request — einmal fragen, dann übergeben":** nur im Fertig-Fall, **beim Abbruch ausdrücklich übersprungen**. `AskUserQuestion`, genau einmal, zwei Antworten. Die Antwort „ja" **nennt ihre Folge mit**: mit Story `Closes #NNN` (Karte wandert auf `Review`, Issue schließt beim Merge), ohne Story kein Verweis und keine Board-Bewegung; die Antwortmöglichkeit nennt die **konkrete** Nummer, nicht einen Platzhalter. „Nein" → direkt zu Schritt 8, Verhalten wie heute. Hier steht der Übergabeblock aus Abschnitt 1 — und nur hier, weil Schritt 6 und der Aufräumschritt **keinen** Codeblock tragen dürfen.
- **Bisheriger Schritt 7 wird Schritt 8**, Text unverändert, ergänzt um: nennt zusätzlich den eröffneten Pull Request, falls es einen gibt. Der Querverweis in Schritt 2 („der Handgriff aus Schritt 7") wird mitgezogen.

### 6. Betroffene Dateien

| Datei | Was |
|---|---|
| `specs/decisions/0077-entwurfslauf-endet-im-pull-request-uebergabe-per-anker.md` | **neu**, bereits angelegt |
| `specs/decisions/0073-…aufraeumen-als-handgriff.md` | **bereits erledigt**: Kopfzeile `**Teilweise abgelöst:**`; Entscheidungstext unverändert |
| `specs/architecture/0002-testkonzept.md` | **bereits erledigt**: neuer Punkt 10, zwei bekannte Lücken, Kopfzeile fortgeschrieben |
| `specs/architecture/0003-securitykonzept.md` | **bereits erledigt**: neuer Abschnitt zu ADR 0077, Einschränkung am ersten Restrisiko-Punkt |
| `.claude/skills/ship-entwurf/SKILL.md` | **neu** — Erlaubnisstufe „lesend und schreibend", Hauptsession, nur Operations-IDs |
| `.claude/skills/penpot-entwurfsrunden/SKILL.md` | neuer Schritt 7, Umnummerierung 7→8, Pull-Request-Zeile in der Aufräum-Auskunft, Querverweis in Schritt 2, abgelösten Satz streichen; **Erlaubnisstufe unverändert** |
| `.claude/skills/github-access/SKILL.md` | Erlaubnisstufen-Tabelle: `ship-entwurf` unter „lesend und schreibend"; `description` nennt ihn als Aufrufer |
| `scripts/tests/test_github_zugriff_an_einer_stelle.py` | `ERWARTETE_STUFEN` += `.claude/skills/ship-entwurf/SKILL.md` → `STUFE_SCHREIBEND` |
| `scripts/tests/test_ship_entwurf_skill.py` | **neu** — Anker, Platzierung, Zulassungsmenge, Diff-Hygiene, Whitelist-Gleichheit, wörtliche Zusagen |
| `scripts/tests/test_entwurfsrunden_skill.py` | `ABSCHNITTE_OHNE_CODEBLOCK` auf die neue Schritt-8-Überschrift; neue wörtliche Zusagen; abgelösten Satz aus den Zusagen streichen |
| `scripts/tests/test_board_befehle_in_skills.py` | `ABLAUF_SKILLS` += `ship-entwurf` — **ohne diesen Eintrag findet die Prüfung auf `## Lokal nachzuholen` für den neuen Skill schlicht nicht statt** (still grün, nicht rot) |
| `scripts/tests/test_penpot_ohne_instanzadresse.py` | `SUCHRAUM_PRAEFIXE` += `.claude/skills/ship-entwurf/`, Docstring („vier Pfade" → fünf) |
| `.claude/skills/review/SKILL.md`, `specs/decisions/0040-…md` Teil 2, `specs/decisions/0014-…md` Teil 1 | Security-Trigger += `.claude/skills/ship-entwurf/**`; **synchronpflichtig**, alle drei im selben Commit |
| `CLAUDE.md` | Ausnahme benennen: Ein Pull Request aus einem Entwurfslauf durchläuft die Review-Phase nicht |
| `docs/ai-workflow.md` | Rollen-Landkarte: Zeile `ship-entwurf`; die Aussage „GitHub-Schreibzugriff gibt es nur hier" bei `ship-feature` auf den neuen Stand bringen |
| `design/penpot/**`, `frontend/penpot/payload.test.ts`, `.claude/skills/ship-feature/SKILL.md`, `.claude/skills/penpot-design/SKILL.md`, `docs/architecture.md`, `docs/setup.md`, `backend/**`, `frontend/src/**` | **unverändert** |

### 7. Reihenfolge der Umsetzung (TDD, rot vor grün)

1. ADR lesen (liegt vor).
2. `test_github_zugriff_an_einer_stelle.py`: `ERWARTETE_STUFEN`-Eintrag ergänzen → **rot** (Eintrag ohne Datei); dann `.claude/skills/ship-entwurf/SKILL.md` in erster Fassung anlegen **und `git add`** → **grün**. Der Suchraum kommt aus `git ls-files`; eine nur im Arbeitsverzeichnis liegende Datei ließe den Test **still grün** — `git add` gehört in denselben Schritt wie das Anlegen, nicht in den Commit am Ende. Das ist der einzige Anker, der von allein rot wird.
3. `scripts/tests/test_ship_entwurf_skill.py` schreiben → **rot**; Skilltext ergänzen → **grün**.
4. `test_entwurfsrunden_skill.py` anpassen → **rot**; `penpot-entwurfsrunden/SKILL.md` umbauen → **grün**. Erst die Testkonstante, dann umbenennen.
5. `test_board_befehle_in_skills.py` (`ABLAUF_SKILLS`) und `test_penpot_ohne_instanzadresse.py` (Suchraum, Docstring). Letzterer startet grün; **tragender Beleg ist die Mutationsprobe** (eine Adresse probeweise in `ship-entwurf` setzen, rot sehen, zurücknehmen) — sie gehört benannt in den Abschlussbericht.
6. Security-Trigger an den drei synchronpflichtigen Stellen, `github-access` (Tabelle + `description`), `CLAUDE.md`, `docs/ai-workflow.md`.
7. Gesamtlauf: `pytest` in `scripts/tests/`, `npm test` in `frontend/` und `e2e/`, Lint und Typprüfung.

**Der erste echte Einsatz ist nicht Teil dieser Story** — sie liefert den Auslieferpfad, nicht seinen ersten Lauf. Der findet in der nächsten Ansichts-Story statt, in der Hauptsession mit verbundener Penpot-Sitzung.

## UI/UX

Nicht relevant. Die Story ändert ausschließlich Skill-, Prozess- und Testtexte; `frontend/src/**`
wird nicht angefasst, es entsteht keine Ansicht, kein Zustand und kein Bedienelement. Die einzige
Interaktion ist eine Rückfrage im Chat (`AskUserQuestion`) — das ist Ablaufsteuerung, keine
sichtbare Produktoberfläche, und das Design-System wird davon nicht berührt.

## Security

Sicherheitsrelevant. Nicht wegen des Produkts (kein Endpunkt, kein Secret, keine
Abhängigkeit, kein Fotobezug), sondern wegen der Richtung: Ein Skill mit
GitHub-Schreibrecht nimmt die Ausgabe eines Ablaufs **ohne** Zugriffsrecht als Auslöser
und macht daraus ein öffentliches, nicht zurücknehmbares Artefakt — als einziger
PR-Pfad des Repositories ohne Perspektivenrunde und ohne Copilot-Review. Vollständige
Herleitung im Sicherheitskonzept
([`architecture/0003`](../architecture/0003-securitykonzept.md), Abschnitt zu ADR 0077).

**Der Übergabeblock ist ein Textkanal, keine typisierte Schnittstelle.** Anker und Block
überqueren eine Zuständigkeits-, aber keine Prozessgrenze: Beide Seiten laufen in
derselben Hauptsession, im selben Kontextfenster, in dem zuvor Brettnamen und Rundentexte
aus Penpot standen. Eine Validierung der abgebenden Seite ist auf der empfangenden nicht
nachweisbar.

- **Muss:** `ship-entwurf` prüft **jeden steuernden Wert selbst**, unmittelbar vor der
  Verwendung, und **hält an statt zu bereinigen** (Härtungsregel 4.2).
- **Steuernd sind genau zwei Werte.** `entwurfslauf` (wird Branch-Namensteil): das Muster
  `^[a-z0-9][a-z0-9-]{2,39}$` ist dafür **ausreichend** — verankert, kein `.`, `/`, `:`,
  `~`, `^`, `?`, `*`, `\`, kein Leer-/Steuerzeichen, kein führender `-`, kein `.lock`,
  Länge gedeckelt. Die **Story-Nummer** (wird `Closes #NNN`): `^[0-9]+$` ist **nicht
  hinreichend** — es wehrt Injektion ab, nicht die Wahl des falschen Ziels.
  **Muss:** zusätzlich `^[1-9][0-9]{0,5}$`; die Nummer stammt ausschließlich aus Daniels
  Angabe in der Sitzung bzw. aus Branch-/Spec-Namen, **nie** aus einem Penpot-Wert und nie
  aus einer GitHub-Antwort; die Antwortmöglichkeit „ja" nennt die **konkrete** Nummer,
  nicht einen Platzhalter — weicht der Block davon ab, hält der Pfad an.
- **Alles Übrige im Block steuert nichts** (Rundenzahlen, Ergebnis-Ansicht, Dateiliste):
  Berichtsmaterial.

**Die Zeile `Geänderte Dateien` bestimmt den Diff-Umfang nicht.**

- **Muss:** Die Zulassungsprüfung läuft ausschließlich über die **selbst gemessene** Menge
  (`git status --porcelain` + `git diff --name-only origin/main...HEAD`); die Zeile des
  Blocks wird dafür **nicht gelesen**. Grund: Die geschlossene Diff-Klasse ist die
  Bedingung, unter der der Reviewverzicht vertretbar ist — ruhte sie auf einer Textzeile
  aus demselben Kontext, der auch die Penpot-Rücklesungen enthielt, reichte ein
  ausgelassener Pfad, damit etwas außerhalb der Klasse mitfährt, ohne dass etwas rot wird.
- **Muss:** Commit **pfadexplizit** über die gemessenen Pfade (`git add <Pfade>`, nie
  `git add -A`, nie `git commit -a`).
- Abweichung zwischen Blockzeile und Messung ist **kein** Abbruchgrund (ein
  `spec-writer`-Commit steht dort legitim nicht drin), geht aber in den Chat-Bericht.

**Erste automatisierte Stelle, die von sich aus nach `design/`-Pfaden committet.** Der
CI-Schritt „keine Bilddatei unter `e2e/` oder `design/` im Git-Index" ist laut `.gitignore`
ausdrücklich „ein Detektor nach dem Push, kein Verhinderer" — `ship-entwurf` committet und
pusht **vor** jeder CI-Auswertung, und ein roter Check nimmt einen gepushten Blob nicht
zurück.

- **Muss:** Die gemessene Pfadmenge wird **vor dem Commit** gegen dasselbe Muster wie die
  CI geprüft (`\.(png|jpe?g|gif|webp|bmp|tiff?|avif|heic|ico)$`, ohne Beachtung der
  Groß-/Kleinschreibung); ein Treffer hält an.

**Härtungsregel 4.3/4.4 am öffentlichen Artefakt.** Richtig in ADR 0077 angelegt:
Arbeitsseite aus dem validierten `entwurfslauf`, Ergebnis-Ansicht aus
`anzeigename`/`schluessel` in `views.json`, kein Penpot-Rücklesen, keine Brettnamen und
Rundentexte im Body. Zwei Lücken bleiben:

- **Muss:** `anzeigename`/`schluessel` sind Repository-Inhalt, aber **nicht selbst
  erzeugt** — der Eintrag entstand meist im selben Lauf. Vor dem Einsetzen prüfen: genau
  eine nicht leere Zeile, keine Steuerzeichen, keine Bidi-Overrides (U+202A–U+202E,
  U+2066–U+2069), keine Zero-Width-Zeichen (U+200B–U+200D, U+FEFF), kein `#`, kein `@`,
  kein Backtick, Länge gedeckelt. Grund: GitHub wertet Closing-Keywords **überall** im Body
  aus — ein Anzeigename mit `#123` schlösse beim Merge ein fremdes Issue. Scheitert die
  Prüfung, steht im Body der geschlossene `schluessel` allein, die Abweichung im Bericht.
- **Muss:** Die Beschreibung in `chore(design): <Beschreibung>` wird von `ship-entwurf`
  selbst formuliert oder aus `entwurfslauf`/`schluessel` gebildet, nie aus einem
  Penpot-Wert übernommen, enthält kein `#`, und wird über die **Titel-Datei** mechanisch
  gegen Härtungsregel 4.4 geprüft.

**Die Beispieldaten-Regel bekommt eine dritte Prüfstelle.** Bisher war der
Veröffentlichungskanal das von Hand angehängte Bild; ab jetzt veröffentlicht der Pfad
**automatisch den Diff**, dessen Freitext-Anteil der `luecken`-Block in `views.json` ist.

- **Muss:** `ship-entwurf` liest die **hinzugefügten Zeilen** des gemessenen Diffs einmal
  gegen die Beispieldaten-Regel aus `penpot-design` und hält bei einem Befund an. Das ist
  der einzige ehrliche Teilersatz für den entfallenen Prüferblick.

**Zulassungsmenge: `design/penpot/**`, `frontend/penpot/**`, `specs/**` — tragfähig, mit
zwei benannten Kanten.**

1. **Wächter und Bewachtes liegen darin beieinander.** `design/penpot/**` trägt die
   Nutzlast (`seed-*.js`, `verify.js`), `frontend/penpot/payload.test.ts` ihre
   Verbotsliste `VERBOTENE_BEZEICHNER` samt `BEZEICHNER_FREIGABEN`. Ein Pull Request mit
   Nutzlast-Zeile **und** passender Freigabe wäre grün, weil die aufgeweichte Prüfung im
   selben Diff liegt. Die ADR nennt nur `verify.js`-Kardinalitäten; die Klasse ist
   breiter. **Entschieden (Daniel, 2026-09-11): Wächter-Halt.** `ship-entwurf` hält an bei
   (a) **neuer** `*.js` unter `design/penpot/` oder (b) hinzugefügten/entfernten Zeilen in
   `payload.test.ts`, die `VERBOTENE_BEZEICHNER`, `BEZEICHNER_FREIGABEN`, `bezeichner:`
   oder `muster:` enthalten. Mechanisch an `git diff -U0` prüfbar, trifft den Regelfall
   (Zahl anheben, `views.json`-Eintrag) nicht.
2. **`specs/**` ist weit, und die Begründung trägt** (vorhandene `spec-writer`-Commits auf
   einem Story-Branch). Mitgedeckt sind aber `specs/decisions/**`,
   `specs/architecture/0003-securitykonzept.md` und `specs/diagrams/*.svg`.
   **Muss, bewusst schwach und billig:** keine zweite Zulassungsmenge — `ship-entwurf`
   benennt die gemessenen `specs/`-Pfade **einzeln und getrennt** von den
   Entwurfs-Nachträgen in Chat-Bericht und Pull-Request-Body, damit beim Merge sichtbar
   ist, dass ein ADR- oder Konzepttext mitfährt.

**Die Trigger-Tabelle deckt die Datei, nicht den Pfad.** `design/penpot/**` ist bereits
Security-Trigger, und ADR 0077 Abschnitt 9 nimmt `.claude/skills/ship-entwurf/**` auf —
beides greift nur, wenn eine Perspektivenrunde **stattfindet**. Der Eintrag schützt
Änderungen **an** dem Skill, nicht Änderungen, die **durch** ihn fahren. Festgehalten,
damit die Aufnahme nicht als Schließung dieser Lücke gelesen wird.

**Unverändert scharf und richtig so:** Abgleich mit `main` vor dem Push, Exit ≠ `0`/`10`
hält an und pusht nichts, keine Konfliktauflösung ohne Gegenlager; Konfliktpfade einzeln
in den Chat-Bericht, nie in den Pull-Request-Body, keine Meldung zitiert rohe `git`-Ausgabe
oder nennt die Remote-URL (credential-behaftete `origin`-URLs sind ein Secret).

**Ausdrücklich geprüft und ohne Befund:** kein neues Secret, kein neuer Empfänger, keine
neue Abhängigkeit, kein neuer Endpunkt, keine Datenmodell-Änderung, keine Änderung an
Authentifizierung oder Datensichtbarkeit zwischen den beiden Nutzern. Die Erlaubnisstufe
des Rundenablaufs wird nicht aufgeweicht, sondern prüfbarer. Kein zweites Artefakt bei
Fehlgriff (`pr-erstellen` scheitert bei offenem Pull Request eindeutig; die
Verifikationspflicht bei mehrdeutigem Fehlschlag gilt unverändert). Kein eigenmächtiges
Board-Schreiben. Leerer Diff ist eine Auskunft. Kein Merge, kein Issue-Schließen, kein
`Done`.

## Teststrategie

**Keine neue Testebene, kein Anwendungscode, Coverage-Gate unberührt.** Alles Mechanische liegt
als `pytest` unter `scripts/tests/` (Job `demo-scripts`, blankes `pytest`, ohne `--cov`);
`backend/src/photosort/**` wird nicht angefasst, die gemessene Zahl bewegt sich
konstruktionsbedingt nicht.

**Neu: `scripts/tests/test_ship_entwurf_skill.py`** — fünf Gruppen, jede mit synthetischer Probe
(Erkenner findet seinen eigenen Verstoß) und Gegenprobe (der erlaubte Fall bleibt grün), dazu
Selbstschutz (Mindestlänge des Skilltexts, Nachweis, dass die geprüften Überschriften existieren):

1. **Anker.** Ankerzeile wortgleich in beiden Dateien; die **Blockdefinition** nur im erzeugenden Skill; im verbrauchenden keine zweite umzäunte Kopie.
2. **Platzierung/Kardinalität.** Anker im erzeugenden Skill genau einmal, Offset zwischen Fertig- und Aufräumschritt — über **Zeichenoffsets**, nicht über `abschnitt()`.
3. **Zulassungsmenge.** Die drei Präfixe und die namentlichen Ausschlüsse wörtlich; `origin/main...HEAD` als Vergleichsbasis; Wächter-Halt und Bilddatei-Halt als wörtliche Zusagen.
4. **Diff-Hygiene.** Kein `-A`, kein `-a`, pfadgenaues Hinzufügen; Skriptpfad und die drei Exit-Fälle.
5. **Operations-IDs als Whitelist-Gleichheit** — die genannte Menge ist gleich `{pr-erstellen, board-status-und-prioritaet-lesen, board-status-setzen}`; das deckt „kein Copilot, keine Perspektivenrunde" ohne Abwesenheitstest ab, und beide Richtungen (zu viel, zu wenig) werden rot. Plus die wörtlichen Zusagen (Titelform, `Closes #NNN`, alle Validierungsmuster, Herkunft der Namen).

**Änderungen an vier Bestandsdateien:** `test_github_zugriff_an_einer_stelle.py`
(`ERWARTETE_STUFEN`, der einzige von allein rote Anker), `test_entwurfsrunden_skill.py`
(`ABSCHNITTE_OHNE_CODEBLOCK` auf Schritt 8 — der neue Schritt 7 steht bewusst **nicht** darin, er
trägt den Übergabeblock), `test_board_befehle_in_skills.py` (`ABLAUF_SKILLS`, sonst findet die
Prüfung auf `## Lokal nachzuholen` gar nicht statt), `test_penpot_ohne_instanzadresse.py`
(Suchraum, Docstring — startet grün, tragender Beleg ist die Mutationsprobe).

**Vier Bestandstests tragen ohne Zutun** und sind beim Formulieren mitzudenken statt neu zu bauen:
Operations-ID im Katalog vorhanden, kein Werkzeugname am Katalog vorbei, `main...HEAD` ohne
`origin/`, Einmaligkeit der festen Merge-Nachricht.

**Was Sichtprüfung bleibt und keine erfundene Kennzahl bekommt:** dass tatsächlich einmal gefragt
wird; dass beim Abbruch übersprungen wird; dass der Ablauf beim ersten Pfad außerhalb der
Zulassungsmenge anhält; dass der Übergabeblock mit korrekten Werten entsteht; jede Wirkung bei
GitHub und im Board.

Das Testkonzept ([`architecture/0002`](../architecture/0002-testkonzept.md)) ist bereits ergänzt:
neuer Punkt 10 in „Agenten-Steuerungslogik selbst" (Anker-Übergabe innerhalb derselben Session,
Kardinalität statt Abwesenheit als projektweite Regel, `-A`/`-a`-Verbot für jede Skill-Datei mit
Schreibpfad, was `ABLAUF_SKILLS` von allein leistet und was nicht) plus zwei neue „Bekannte
Lücken".

## Entscheidungen

- **`architect` konsultiert (Schritt 1):** legt Anker-Übergabe, eigenen Skill `ship-entwurf`, Zulassungsmenge und Umsetzungsreihenfolge fest; ADR 0077 angelegt, ADR 0073 teilweise abgelöst.
- **`ux-ui-designer` nicht konsultiert (Schritt 2):** Die Story berührt keine sichtbare Oberfläche — es entsteht keine Ansicht, kein Zustand, kein Bedienelement, und `frontend/src/**` steht ausdrücklich als unverändert in der Dateitabelle. Die einzige Interaktion ist eine Chat-Rückfrage der Ablaufsteuerung.
- **`test-engineer` konsultiert (Schritt 3):** Akzeptanzkriterien geschärft, Testkonzept ergänzt; sechs Befunde gegen die Umsetzungsplanung sind oben eingearbeitet (Ein-Definitions-Regel für den Block, Kardinalität statt Abwesenheit beim Abbruch, Offsets statt `abschnitt()`, `-A`/`-a`-Verbot, `ABLAUF_SKILLS`, Whitelist-Gleichheit statt Verbotsliste).
- **`security-engineer` konsultiert (Schritt 3):** sicherheitsrelevant; Sicherheitskonzept ergänzt. Schärfster Befund: Wächter und Bewachtes liegen in derselben Zulassungsmenge.
- **Reviewverzicht — Wächter-Halt (Daniel, 2026-09-11):** Von vier Möglichkeiten (Wächter-Halt / nur melden / jede `*.js` triggert `review-security` / unverändert) ist der **Wächter-Halt** gewählt. Er ist mechanisch prüfbar und trifft den Regelfall nicht; „jede `*.js`" hätte fast jeden Lauf ausgebremst, weil eine angehobene Kardinalität immer `verify.js` berührt, und wäre zudem am Akzeptanzkriterium vorbeigegangen.
- **Story-Bezug — `Closes #NNN` (Daniel, 2026-09-11):** Nur das Closing-Keyword bewegt die Karte auf `Review`. Bewusst hingenommene Nebenwirkung: Der Merge schließt das Issue auch dann, wenn der Entwurfslauf die Story nicht abschließt. Gegenmittel ist die Antwort „nein" auf die Abschlussfrage — deshalb steht die Folge **im Text der Antwortmöglichkeit**, nicht in einer Fußnote.
- **Keine Spec-Finalisierung im Entwurfs-Pull-Request:** Kein Akzeptanzkriterium nennt sie, und `Implemented` ist eine Aussage über einen reviewten Stand. Preis: Eine Story, die vollständig aus einem Entwurfslauf besteht, braucht ihre `**Status:**`-Zeile als gewöhnliche lokale Textänderung in den Commits des Laufs.
- **Titel `chore(design):`, nicht `feat`:** Ein Entwurfslauf erzeugt kein ausgeliefertes Produkt-Delta; ein `feat`-Titel bumpte über `release-please` die Minor-Version für etwas, das kein Nutzer sieht.

## Offene Fragen

Keine. Die beiden Produktentscheidungen (Reviewverzicht, Story-Bezug) sind am 2026-09-11
entschieden und oben unter „Entscheidungen" festgehalten.

## Out of Scope

- **Der erste echte Entwurfslauf über den neuen Pfad.** Diese Story liefert den Auslieferpfad, nicht seinen ersten Einsatz; der findet in der nächsten Ansichts-Story mit verbundener Penpot-Sitzung statt.
- **Merge, Issue-Schließen und `Done`.** Der Pfad endet am eröffneten Pull Request; gemerged wird von Daniel.
- **Ein zweiter Einstieg in `ship-feature`.** Ausdrücklich verworfen (Abschnitt 2).
- **Jede Änderung an der Nutzlast selbst** (`design/penpot/**`) und an `frontend/penpot/payload.test.ts`: Diese Story fasst beide nicht an, sie definiert nur, wie ein späterer Lauf sie ausliefert.
- **Nachträgliche Absicherung bereits liegengebliebener Branches.** Der Lauf zur Fotoansicht bleibt, wie er ist.
