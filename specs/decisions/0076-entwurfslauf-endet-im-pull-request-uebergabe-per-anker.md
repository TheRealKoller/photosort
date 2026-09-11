# 0076 - Ein Entwurfslauf endet im Pull Request: Übergabe per Anker an einen eigenen schlanken Auslieferpfad

**Status:** Accepted
**Datum:** 2026-09-11
**Bezug:** [GitHub-Issue #392](https://github.com/TheRealKoller/photosort/issues/392), [`decisions/0073-entwurfsrunden-auf-arbeitsseite-aufraeumen-als-handgriff.md`](./0073-entwurfsrunden-auf-arbeitsseite-aufraeumen-als-handgriff.md), [`decisions/0069-ansichtsentwuerfe-als-handarbeit-mit-soll-struktur-im-repository.md`](./0069-ansichtsentwuerfe-als-handarbeit-mit-soll-struktur-im-repository.md), [`decisions/0061-ein-ort-fuer-jeden-github-zugriff-wege-in-fester-reihenfolge.md`](./0061-ein-ort-fuer-jeden-github-zugriff-wege-in-fester-reihenfolge.md), [`decisions/0045-spec-writer-legt-feature-branch-an-ein-pr-pro-story.md`](./0045-spec-writer-legt-feature-branch-an-ein-pr-pro-story.md)

**Löst teilweise ab:** [`decisions/0073`](./0073-entwurfsrunden-auf-arbeitsseite-aufraeumen-als-handgriff.md), **Abschnitt 5, letzter Absatz** — der Satz „Beides gehört in denselben Pull Request wie der fertige Entwurf — in die Story, in deren Rahmen der Lauf stattfand". Er band die Auslieferung der Nachträge (`views.json`, Kardinalitäten in `verify.js`) an eine Story, die es nicht geben muss, und benannte niemanden, der den Pull Request eröffnet. **Alles Übrige von ADR 0073 bleibt unverändert in Kraft**: der eigene Skill neben `penpot-design` (Abschnitt 1), die Arbeitsseite und ihre Vereinfachungen (Abschnitt 2), die Marken und die Wiederaufnahme (Abschnitt 3), **der Ablauf löscht nichts** und das Aufräumen bleibt eine Auskunft (Abschnitt 4), das Ausarbeiten statt Verschieben samt Nachtrag an der Nutzlast (Abschnitt 5 im Übrigen), die beiden Auflagen (Abschnitt 6), die jederzeitige Aufrufbarkeit ohne Story und die Erlaubnisstufe „kein GitHub-Zugriff" (Abschnitt 7) und der Security-Trigger (Abschnitt 8, hier erweitert statt ersetzt).

## Kontext

Ein Entwurfsrundenlauf endet heute mit einem gepushten Branch und sonst nichts. Was der Lauf im
Repository verändert hat — der Eintrag in `design/penpot/views.json`, die angehobenen
Kardinalitäten in `design/penpot/verify.js`, gelegentlich eine Freigabe in
`frontend/penpot/payload.test.ts` — liegt damit außerhalb jedes Reviews und außerhalb der CI, und
es bleibt Daniel überlassen, den Pull Request von Hand nachzuschieben. **Beim Lauf zur Fotoansicht
ist genau das passiert** (Merge-Commit `715a45f`, „chore(design): Fotoansicht als Soll-Struktur
aufnehmen").

Die Ursache ist keine Nachlässigkeit, sondern eine Lücke im Rollenzuschnitt. Zwei Festlegungen
stoßen aneinander:

- ADR [`0073`](./0073-entwurfsrunden-auf-arbeitsseite-aufraeumen-als-handgriff.md) Abschnitt 7
  gibt dem Rundenablauf die Erlaubnisstufe **kein GitHub-Zugriff** und macht ihn zugleich
  **jederzeit aufrufbar, auch ohne Story**. Er darf den Pull Request also nicht selbst eröffnen.
- ADR 0073 Abschnitt 5 schiebt die Auslieferung deshalb „in die Story, in deren Rahmen der Lauf
  stattfand". Findet kein Lauf in einer Story statt — der Regelfall bei einem jederzeit
  aufrufbaren Ablauf —, zeigt dieser Satz ins Leere.

Der bestehende Auslieferpfad `ship-feature` schließt die Lücke nicht: Er ist von Anfang bis Ende
um einen **offenen `developer`-Subagenten** gebaut (Findings per `SendMessage`, Folgeaufträge,
Konfliktauflösung im Subagenten), um eine **Perspektivenrunde** und um die **Finalisierung einer
Spec**. Ein Entwurfslauf hat nichts davon — und er hat etwas, das `ship-feature` nicht kennt:
einen Zwischenstand in einer privaten Design-Datei, aus der Namen in ein öffentliches Artefakt
wandern.

## Entscheidung

### 1. Der Abschluss fragt genau einmal; der Abbruch fragt nicht

Erklärt Daniel einen Lauf für **fertig**, wird **genau einmal** gefragt, ob ein Pull Request
eröffnet werden soll. Die Frage tritt zu den bisherigen Abschlussinhalten hinzu und ersetzt
keinen davon. Bei „nein" bleibt alles wie heute: die Auskunft über Arbeitsseite, Runden und
Ergebnis, kein Pull Request.

Beim **Abbruch** wird **nicht** gefragt und nichts eröffnet. Das ist keine Ersparnis, sondern die
Bedeutung des Abbruchs: Ein abgebrochener Lauf hat kein Ergebnis, das ausgeliefert werden
könnte — was an der Nutzlast steht, gehört zum ausgearbeiteten Entwurf, und den gibt es dann
nicht. Ein Pull Request an dieser Stelle wäre die teuerste Art, einen Abbruch zu dokumentieren.

**Die Frage trägt ihre Folge mit sich.** Die Antwortmöglichkeit „ja" nennt, was daraus folgt:
mit Story-Bezug die Zeile `Closes #NNN` — die Karte wandert auf `Review` und das Issue schließt
beim Merge —, ohne Story-Bezug keine Verknüpfung und keine Board-Bewegung. Daniel entscheidet
damit vor der Handlung und nicht danach; das ist der einzige Ort, an dem diese Folge überhaupt
noch wählbar ist.

### 2. Übergeben wird per Anker, nicht per eigenem Zugriff

Die Erlaubnisstufe **kein GitHub-Zugriff** des Rundenablaufs bleibt **wörtlich unverändert**. Er
eröffnet den Pull Request nicht, er fordert kein Review an, er liest keinen Board-Wert. Bei „ja"
schreibt er stattdessen einen **wörtlichen Übergabeblock** und hört damit auf; die Hauptsession
erkennt den Anker und ruft den Skill aus Abschnitt 3 auf.

Der Anker lautet wörtlich:

```
## Entwurfslauf abgeschlossen: Pull Request erwünscht
```

Der Block darunter trägt genau die Angaben, die der Auslieferpfad braucht, und keine weitere:
Arbeitsseite, Zahl der Runden und Vorschläge, Ergebnis-Ansicht (oder „keine"), Story-Bezug
(`#NNN` oder „keine"), geänderte Dateien.

**Das ist dasselbe Muster, das im Repository bereits trägt:** `developer` hat ebenfalls keinen
GitHub-Zugriff und meldet mit `## Abschlussbericht` bzw.
`## Blockiert: Architektur-Konsultation nötig` an den Orchestrator zurück, der daraufhin
`ship-feature` bzw. `architect` aufruft. Neu ist allein, dass hier kein Subagenten-Fenster
dazwischenliegt — der Anker überquert eine **Zuständigkeits**grenze, keine Prozessgrenze. Er ist
deshalb nicht weniger wert: Er ist die Stelle, an der ein Text ohne Zugriffsrecht aufhört und
einer mit Zugriffsrecht anfängt, und er ist wörtlich prüfbar, während „der Ablauf übergibt dann
halt" es nicht wäre.

Der Anker **beendet nicht den Lauf**, sondern dessen GitHub-freien Teil. Nach der Rückkehr des
Auslieferpfads — mit einer Pull-Request-Nummer oder mit einem Fehlschlag — geht es im
Aufräumschritt weiter (Abschnitt 6).

### 3. Ein eigener schlanker Skill `ship-entwurf`, kein zweiter Pfad in `ship-feature`

Die Auslieferung bekommt einen **eigenen** Skill `.claude/skills/ship-entwurf/SKILL.md`,
Erlaubnisstufe **lesend und schreibend**, Hauptsession. Er nennt wie jeder andere Ablauf-Skill
ausschließlich **Operations-IDs** aus `github-access` (ADR
[`0061`](./0061-ein-ort-fuer-jeden-github-zugriff-wege-in-fester-reihenfolge.md)); kein `gh`, kein
Werkzeugname, kein zweiter Katalog.

Geprüft, nicht gefühlt entschieden: Von den neun Schritten des `ship-feature`-Ablaufs berührt ein
Entwurfslauf **einen** — die Gruppe „committen, abgleichen, pushen, Pull Request". Alles andere
(Anker-Trigger auf `developer`-Berichte, Branch-/Diff-Verifikation gegen einen gemeldeten Stand,
`review`-Orchestrator, Findings per `SendMessage`, Folgebericht, Copilot-Runde,
Spec-Finalisierung, Recovery bei geschlossenem Subagenten-Fenster) hat keinen Gegenstand. Und
innerhalb des einen berührten Schritts stimmt die Semantik **nicht** überein: Es gibt keinen
Subagenten, an den ein Merge-Konflikt zurückgehen könnte; der Branch muss unter Umständen erst
entstehen; die Closing-Zeile ist bedingt statt Pflicht.

Ein zweiter Einstieg in `ship-feature` hieße deshalb: ein Anker mehr in der Trigger-Liste, acht
Schritte mit einer Ausnahmeklausel „gilt im Entwurfspfad nicht" und ein neunter mit abweichender
Semantik. Das ist genau die Konstruktion, gegen die ADR
[`0073`](./0073-entwurfsrunden-auf-arbeitsseite-aufraeumen-als-handgriff.md) Abschnitt 1 den
Rundenablauf aus `penpot-design` herausgehalten hat — „zwei Einstiegspunkte und ein gemeinsamer
Rumpf, der zu keinem von beiden ganz passt" —, und die Begründung ist hier dieselbe, nur eine
Ebene weiter: andere Auslösung, andere Auflagen, eigene Erlaubnisstufe als eigener prüfbarer
Eintrag.

**Gegen Doppelpflege gilt dieselbe harte Regel wie dort:** `ship-entwurf` wiederholt aus
`ship-feature` nichts, was er nicht selbst ausführt. Was beide brauchen und was im Text beider
steht, ist auf das Zurücklesen des Board-Werts beschränkt (Abschnitt 5) — vier Zeilen, bewusst
in Kauf genommen, weil die Alternative eine dritte Datei wäre, die nur diese vier Zeilen trägt.

### 4. Der Pfad trägt genau eine Diff-Klasse und hält an, sobald mehr darin steht

Vor jedem Schreibzugriff stellt `ship-entwurf` fest, was der Lauf verändert hat
(`git status`, `git diff --name-only origin/main...HEAD`), und prüft jeden Pfad gegen eine
**geschlossene Zulassungsmenge**:

| Zugelassen | Warum |
|---|---|
| `design/penpot/**` | die Nachträge des Laufs: `views.json`, Kardinalitäten in `verify.js`, ggf. `README.md` |
| `frontend/penpot/**` | die zeilengebundenen Freigaben in `payload.test.ts`, die eine angehobene Kardinalität nach sich zieht |
| `specs/**` | die Spec-/ADR-Commits, die `spec-writer` auf einem Story-Branch bereits abgelegt hat |

**Jeder Pfad außerhalb dieser Menge hält den Ablauf an**: kein Commit, kein Push, kein Pull
Request, Meldung an Daniel. Insbesondere `backend/**`, `frontend/src/**`, `e2e/**`,
`scripts/**`, `.github/**` und `.claude/**` — ein Lauf, der dort etwas geändert hat, ist kein
Entwurfslauf mehr, und seine Änderung gehört in den gewöhnlichen Story-Weg mit Perspektivenrunde.

Diese Zulassungsmenge ist **die Bedingung**, unter der Abschnitt 6 (keine Perspektivenrunde)
vertretbar ist, und sie steht deshalb vor ihm. Sie ist außerdem der Grund, warum der Pfad keine
Einschätzung braucht: Er entscheidet an Pfaden, die dastehen, nicht an einer aus dem Diff
herausgelesenen Absicht.

**Ein leerer Diff ist kein Fehler, sondern eine Auskunft.** Hat der Lauf im Repository nichts
verändert (ein Ausschnitts- oder Bausteinentwurf, der die Nutzlast nicht berührt), entsteht kein
Pull Request; gemeldet wird genau das, statt einen leeren zu versuchen.

### 5. Der Pull Request eines Laufs

- **Branch.** Steht die Sitzung auf einem Branch ≠ `main`, wird dieser verwendet — der Lauf fand
  dort statt. Steht sie auf `main`, entsteht zuerst `design/<entwurfslauf>`. Der Namensteil ist
  **genau der Wert**, der ohnehin schon gegen `^[a-z0-9][a-z0-9-]{2,39}$` validiert ist (ADR
  0073, Abschnitt 6a) — der einzige Wert aus der Design-Datei, der unter einem geschlossenen
  Muster steht, und damit der einzige, der einen Befehl steuern darf.
- **Abgleich mit `main`** über `scripts/merge-main-into-branch.sh`, nach dem Commit und vor dem
  Push. Ausgewertet wird der Exit-Code: `0` weiter ohne Meldung, `10` weiter mit einer Zeile im
  Bericht, **`20` (Konflikt) und jeder andere Code: anhalten, nichts pushen, an Daniel melden.**
  Hier wird ein Konflikt **nicht** aufgelöst — es gibt keinen Subagenten, an den er ginge, und
  die Kardinalitäten der Nutzlast sind handgepflegte Zahlen, deren Zusammenführung Augen braucht.
- **Titel:** `chore(design): <Beschreibung>`. Conventional-Commit-Form wie jeder PR-Titel des
  Repositories; der Typ ist `chore`, weil ein Entwurfslauf **kein ausgeliefertes Produkt-Delta**
  erzeugt — ein `feat`-Titel bumpte über `release-please` die Minor-Version der Anwendung für
  eine Änderung, die kein Nutzer je sieht.
- **Body** nach `.github/pull_request_template.md`, mit: was der Lauf verändert hat, dem Namen
  der **Arbeitsseite** und dem der **Ergebnis-Ansicht**, damit nachvollziehbar bleibt, woraus der
  Pull Request entstanden ist. Beide Namen werden **nicht** aus einem Penpot-Rücklesen
  übernommen: die Arbeitsseite über den validierten `entwurfslauf`, die Ergebnis-Ansicht über
  `anzeigename`/`schluessel` aus `views.json`, also aus dem Repository. Brettnamen,
  Beschreibungen und Textinhalte der Runden gelangen **nicht** in den Body (Härtungsregel 4.3:
  in ein dauerhaftes GitHub-Artefakt gelangt ausschließlich selbst erzeugter Inhalt).
- **Story-Bezug.** Mit Story trägt der Body die ausgefüllte Zeile `Closes #NNN`; die Nummer
  stammt aus dem Übergabeblock und wird gegen `^[0-9]+$` geprüft. Ohne Story entfällt die Zeile
  (die Vorlage sieht das als Ausnahme ausdrücklich vor) — der Pull Request entsteht trotzdem,
  wandert dann aber nicht von selbst auf `Review`. Das ist **bewusst hingenommen** und wird
  gemeldet, nicht durch ein eigenmächtiges Setzen des Board-Werts verdeckt.
- **Board-Rücklesen**, nur mit Story: nach dem Eröffnen einmal `board-status-und-prioritaet-lesen`
  (Knoten mit `project.number == 8`). Steht nicht `Review`, einmal kurz warten und ein zweites
  Mal lesen; steht es dann immer noch nicht, den Wert **nicht** selbst nachsetzen, sondern
  `board-status-setzen` in den Abschnitt `## Lokal nachzuholen` aufnehmen. Begründung unverändert
  wie bei `ship-feature`: Ein deaktivierter nativer Workflow schreibt gar nichts, und eine Karte,
  die auf `In Progress` liegen bleibt, ist von einer bearbeiteten nicht zu unterscheiden.

### 6. Keine Perspektivenrunde, kein Copilot — und was stattdessen trägt

Der so eröffnete Pull Request durchläuft **nicht** die Nachbereitung eines Feature-Laufs: keine
Runde der `review-*`-Skills, kein automatisiert angefordertes Copilot-Review. **Ein Entwurf wird
durch Hinsehen beurteilt, nicht durch eine Findings-Runde** — und die Design-Datei, an der er
hängt, kann ohnehin kein Prüfer dieses Projekts lesen (ADR 0073: „Kein Test kann Penpot lesen").

Weggenommen wird damit weniger, als es klingt, und das ist die tragende Hälfte dieser
Entscheidung:

1. **Die CI bleibt vollständig in Kraft.** `payload.test.ts`, der Rückleseabgleich gegen
   `views.json`, Lint, Typprüfung, das Coverage-Gate und der Check `pr-titel` laufen an diesem
   Pull Request wie an jedem anderen. Was entfällt, ist die *Perspektivenrunde*, nicht die
   mechanische Absicherung.
2. **Die Diff-Klasse ist durch Abschnitt 4 geschlossen.** Es kann kein Backend-Endpunkt, keine
   Frontend-Komponente und keine Abhängigkeit darin liegen — sonst hätte der Pfad angehalten.
3. **Gemerged wird von Daniel**, wie bei jedem Pull Request dieses Repositories. Der Pfad endet
   am eröffneten Pull Request.

Die ehrliche Gegenrechnung steht in den Konsequenzen: `design/penpot/verify.js` ist JavaScript,
und eine angehobene Kardinalität ist eine Änderung an Code, die hier ohne Perspektivenblick nach
`main` gelangen kann.

### 7. Der Aufräumschritt bleibt vollständig und nennt zusätzlich den Pull Request

Die Auskunft aus ADR 0073 Abschnitt 4 bleibt **wörtlich und vollständig** erhalten — Name der
Arbeitsseite, Zahl der Runden und Vorschläge, Ort des Ergebnisses, der Hinweis, dass Daniel die
Seite in Penpot selbst wegwerfen kann und dass sie sonst stehen bleibt, und dass der
Zwischenstand nirgends gesichert ist. Sie tritt **nach** der Rückkehr des Auslieferpfads ein und
nennt zusätzlich den eröffneten Pull Request, falls es einen gibt.

Unverändert gilt auch, was dort **nicht** steht: kein Codeblock im Abschluss- und im
Aufräumabschnitt. Der Übergabeblock aus Abschnitt 2 steht deshalb in einem **eigenen** Schritt
zwischen beiden, nicht in einem von ihnen.

### 8. Was dieser Pfad ausdrücklich nicht tut

- **Er finalisiert keine Spec.** Die `**Status:**`-Zeile bleibt unberührt; die Finalisierung
  gehört zum Story-Weg und hängt an einer Review-Runde, die es hier nicht gibt. Eine Story, die
  vollständig aus einem Entwurfslauf besteht, setzt ihre Statuszeile als gewöhnliche lokale
  Textänderung in den Commits des Laufs.
- **Er merged nicht**, schließt kein Issue, setzt kein `Done`, fordert kein Review an.
- **Er löscht nichts.** ADR [`0066`](./0066-penpot-stand-als-erzeugte-idempotente-nutzlast.md)
  Abschnitt 4 und ADR 0073 Abschnitt 4 bleiben unangetastet; dieser Pfad berührt die Design-Datei
  überhaupt nicht, er berührt das Repository.
- **Er ist kein zweiter Weg für Code.** Läuft eine Story, die ihre Änderungen ohnehin über
  `ship-feature` ausliefert, lautet die Antwort auf die Frage aus Abschnitt 1 „nein" — die
  Nachträge fahren dann im Pull Request der Story mit. Greift trotzdem jemand daneben, schlägt
  `pr-erstellen` für einen Branch mit bereits offenem Pull Request **eindeutig** fehl; es
  entsteht kein zweites Artefakt, und der Fehlschlag geht in den Chat-Bericht.

### 9. Der Security-Trigger nimmt den neuen Skill auf

`.claude/skills/ship-entwurf/**` tritt der Security-Trigger-Tabelle bei — synchronpflichtig an
den drei bekannten Stellen (`.claude/skills/review/SKILL.md`, ADR
[`0040`](./0040-ki-workflow-schritte-2-8-konsolidiert.md) Teil 2, ADR
[`0014`](./0014-review-agenten-selektion-und-modellzuweisung.md) Teil 1), dasselbe Vorgehen wie
bei der Aufnahme von `penpot-design` (ADR 0065) und `penpot-entwurfsrunden` (ADR 0073).

Begründung, und sie ist eine andere als dort: Nicht der Werkzeugkanal ist der Grund, sondern die
**Richtung** — dies ist der einzige Text des Repositories, der festlegt, welche Namen aus einer
privaten Design-Quelle in ein öffentliches, nicht zurücknehmbares Artefakt gelangen, und der
zugleich den einen Pull-Request-Pfad ohne Perspektivenrunde beschreibt. Ein Pull Request, der
**nur** diese Datei anfasst, träfe sonst keinen einzigen Trigger: keine neue Datei, kein
`specs/decisions/**`, keine Code-Datei — genau die Lücke, die ADR 0065 Abschnitt 5 und ADR 0073
Abschnitt 8 an ihrer Stelle geschlossen haben.

`.claude/skills/github-access/**` bleibt weiterhin außen vor. Das ist **keine** Aussage, sondern
eine benannte Asymmetrie, die diese ADR nicht auflöst; das breitere `.claude/skills/**` bleibt
ebenfalls außen vor.

## Begründung

Der tragende Gedanke ist ein Zuschnitt, kein Mechanismus: **Ein Ablauf ohne Zugriffsrecht endet
an einem prüfbaren Satz, nicht an einer Absichtserklärung.** Die Erlaubnisstufen dieses
Repositories sind Text plus statischer Test (`github-access`, „Die Stufen sind Text plus
statischer Test"); sie halten nur, solange die Stelle, an der ein Recht anfängt, benennbar ist.
Hätte der Rundenablauf den Pull Request „über die Hauptsession" eröffnet, ohne dass irgendwo
stünde, wo sein Text aufhört, wäre die Stufe „kein GitHub-Zugriff" zu einer Formulierung
geworden, die niemand mehr prüfen kann. Der Anker kostet sechs Zeilen und hält sie prüfbar.

Die zweite Überlegung ist der Verzicht auf Wiederverwendung. `ship-feature` und `ship-entwurf`
teilen ein Vokabular (committen, pushen, Pull Request) und sonst nichts: Der eine bedient einen
offenen Subagenten mit Findings, der andere eine Design-Datei, die kein Prüfer lesen kann.
Gemeinsame Schritte mit „gilt hier nicht"-Klauseln sind der zuverlässigste Weg, dass später eine
Klausel übersehen wird — und die übersehene wäre im schlechteren Fall eine Sicherheitsklausel,
nicht eine Bequemlichkeit.

Die dritte betrifft die Reihenfolge von Zulassungsmenge und Reviewverzicht. Der Verzicht auf die
Perspektivenrunde ist der einzige wirklich unbequeme Teil dieser Entscheidung, und er ist nur
deshalb vertretbar, weil die Klasse dessen, was auf diesem Pfad überhaupt fahren kann, **vorher**
geschlossen wird. Umgekehrt herum — erst der bequeme Pfad, dann die Frage, was darüber fährt —
wäre es eine Abkürzung um das Review herum, die mit jedem Lauf breiter würde.

Die vierte ist die Antwortmöglichkeit, die die Folge mitnennt. `Closes #NNN` schließt beim Merge
ein Issue; eine Story, von der noch etwas aussteht, wäre damit zu früh erledigt. Diese Folge ist
nicht durch Automatik entscheidbar (nur Daniel weiß, ob der Lauf die Story abschließt), aber sie
ist im Moment der Frage entscheidbar — deshalb steht sie dort und nicht in einer Fußnote der
Konsequenzen.

## Konsequenzen

- **Positiv:** Kein Lauf endet mehr als loser Branch. Was ein Lauf im Repository verändert hat,
  liegt ab jetzt in einem Pull Request und damit in der CI, statt daran vorbei. Die
  Erlaubnisstufe des Rundenablaufs bleibt wörtlich unverändert und wird prüfbarer als vorher. Der
  Pfad funktioniert **ohne** Story — genau der Fall, für den ADR 0073 Abschnitt 5 keine Antwort
  hatte. `ship-feature` bleibt unangetastet und wird nicht um Ausnahmeklauseln schwerer.
- **Negativ / bewusst getragen:**
  - **`verify.js` ist JavaScript, und eine angehobene Kardinalität gelangt auf diesem Pfad ohne
    Perspektivenblick nach `main`.** Getragen wird das von der Zulassungsmenge (Abschnitt 4), der
    unveränderten CI und Daniels Merge — nicht von der Annahme, die Änderung sei harmlos.
  - **Ein achter Skill.** Der Preis für die eigene Auslösung und die eigene Erlaubnisstufe. Er
    ist nur tragbar, solange `ship-entwurf` nichts wiederholt, was er nicht selbst ausführt; die
    vier Zeilen Board-Rücklesen sind die einzige zugestandene Dopplung und der erste Ort, an dem
    Drift auftreten wird.
  - **`Closes #NNN` kann eine Story zu früh schließen**, wenn der Lauf sie nicht abschließt.
    Gegenmittel ist die Antwort „nein" auf die Frage aus Abschnitt 1, nicht eine Erkennung.
  - **Die Spec-Statuszeile einer reinen Entwurfs-Story wird nicht automatisch finalisiert.**
    Wer sie vergisst, zahlt ein kleines Nachzieh-PR — dieselbe Kosten, die `ship-feature`
    Schritt 8 für den Story-Weg vermeidet. Bewusst nicht mitgenommen, weil `Implemented` eine
    Aussage über einen reviewten Stand ist.
  - **Zwei Ankerformate mehr im Umlauf.** Der Anker aus Abschnitt 2 muss in beiden Dateien
    wörtlich gleich stehen; das ist ein statischer Test wert und keine Konvention auf Zuruf.
- **Folgearbeit:** Dieselbe Lücke besteht für einen einmaligen Durchlauf von `penpot-design`, der
  eine Ansicht ausarbeitet. `ship-entwurf` ist so geschnitten, dass ein zweiter Anker ihn später
  auch von dort aus erreichbar macht; gebaut wird das hier **nicht**, und ob es gebraucht wird,
  entscheidet der nächste solche Lauf statt dieser ADR.
