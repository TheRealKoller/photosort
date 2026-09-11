# 0259 - Issues zeigen den betroffenen Bereich

**Status:** Implemented ([PR #418](https://github.com/TheRealKoller/photosort/pull/418))
**Erstellt:** 2026-09-11
**Bezug:** GitHub-Issue [`#259`](https://github.com/TheRealKoller/photosort/issues/259), ADR
[`0085`](../decisions/0085-bereich-als-label-mit-geschlossenem-vorrat.md)

**Umfang:** über dem Richtwert von rund 200 Zeilen, weil die Spec zwei neue Einträge eines
verbindlichen Operationskatalogs vollständig festlegen muss — deren Zusicherungen sind Invarianten
und vom Kürzen ausgenommen.

## Ziel

Das Board führt die gesamte offene Arbeit an PhotoSort in einer einzigen Liste. Woran ein Issue
tatsächlich rührt — die Oberfläche, das Backend, die Verarbeitungskette der Fotos, der KI-gestützte
Entwicklungsablauf, das Design oder der Betrieb — ist dort kein eigenes Merkmal, sondern steht
bestenfalls zwischen den Zeilen des Titels. Das trifft ausgerechnet die gut geschärften Stories am
härtesten: Ein Titel soll per Konvention das Ergebnis benennen und nicht die Technik, und genau
dadurch verschwindet der Bereich aus ihm.

Nutznießer ist Daniel als einziger Betrachter des Boards: Er soll beim Blick auf die Spalten sofort
sehen, welche Bereiche offene Arbeit haben, und gezielt eingrenzen können. Gut gelöst ist es, wenn
die Zuordnung ohne zusätzlichen Pflegeschritt entsteht — also beim Schärfen einer Story mit
anfällt.

## User Story

Als Daniel möchte ich an jedem Issue sehen, welche Bereiche des Projekts es betrifft, damit ich das
Board auf einen Blick überblicke und gezielt nach einem Bereich eingrenzen kann, ohne einzelne
Issues zu öffnen.

## Akzeptanzkriterien

- [x] **Vorrat.** Der Bereichsvorrat steht als geschlossene Menge in **genau einer Zeile fester
      Form** im Operationskatalog (`.claude/skills/github-access/SKILL.md`). In **allem von Git
      Verwalteten außer `specs/**` und der Wächterdatei selbst** kommt außerhalb dieser Datei
      **kein** `bereich:`-Wert vor. Eine Erweiterung verlangt eine Änderung an dieser Zeile
      **und** an der eingefrorenen Erwartungsmenge des Wächters — dieses Paar ist die „bewusste
      Ergänzung".
      *Nachgezogen im Review (Muss-Fix 1):* Die ursprüngliche Fassung nannte hier den
      aufgezählten Anweisungsraum (`.claude/**`, `CLAUDE.md`, `docs/**`) und ließ damit
      `.github/ISSUE_TEMPLATE/*.yml` durch — Dateien, die nachweislich Label vergeben. Der
      Suchraum ist eine Negativliste geworden; die Zusicherung wird dadurch **weiter**, nicht
      schwächer.
- [x] **Startvorrat**, in Trägerform: `bereich:frontend`, `bereich:backend`, `bereich:pipeline`,
      `bereich:ai-workflow`, `bereich:design`, `bereich:infra`. Die Präfixbindung ist Teil des
      Kriteriums, nicht Umsetzungsdetail (Begründung unter „Teststrategie"). Die sechs Label sind
      im Repository angelegt.
- [x] **Mehrere oder keiner.** Träger ist eine Label-Menge; mehrere Werte und die leere Menge sind
      zulässige Zustände. Der Katalogeintrag beschreibt den **Zielzustand** der Menge, nicht einen
      Zuwachs, und hält fest, dass auf dem `mcp`-Weg die vollständige Menge einschließlich
      `idee`/`bug` zu übergeben ist. Nicht automatisiert prüfbar (Zustand auf GitHub) —
      Review-Kriterium plus Beleg aus dem Nachlauf: **Alle 11 vorbestehenden `bug`/`idee`-Label
      sind erhalten geblieben**, es gab kein stilles Wegfallen. `bereich:design` ist an keinem
      Issue vergeben — die leere Menge eines Werts ist damit ebenfalls belegt, und der Wert bleibt
      im Vorrat.
- [ ] **Auf der Karte sichtbar.** **Offen**, bis die Board-Ansicht das Label zeigt und es einmal
      belegt ist. Kein Test dieses Repositoriums prüft das; der Nachweis ist eine
      Ansichtseinstellung des Boards und liegt bei Daniel.
- [x] **Board eingrenzbar** (`label:"bereich:…"`). Im Nachlauf gemessen: `bereich:pipeline` grenzt
      auf 8 Issues ein, `bereich:ai-workflow` auf 5, `bereich:design` auf 0.
- [x] **Beim Schärfen vergeben, beim Erfassen leer.** In `refinement`, Schritt 6, steht eine
      Ausführungsstelle von `issue-bereich-setzen` — zeilenanfangs-verankert in Backticks — hinter
      `issue-titel-schreiben` und vor **jeder** Ausführungsstelle einer `board-`-Operation. In
      `capture/SKILL.md` kommt weder die Operations-ID noch ein `bereich:`-Wert vor. Zur Laufzeit
      darf der Schritt entfallen (kein Bereich trifft zu); die **Ausführungsstelle im Text** muss
      trotzdem existieren — ihr Fehlen ist ein Befund, kein Sonderfall.
- [x] **Einmalige Nachkennzeichnung.** Maßgeblicher Zeitpunkt ist der Lauf unmittelbar vor
      Eröffnung des Pull Requests. Beleg im PR-Body: die über `issue-liste-lesen` erhobene Liste
      der offenen Issues vorher und nachher, die Zahl der gekennzeichneten Issues und die
      namentliche Nennung jedes bewusst ohne Bereich belassenen Issues samt Grund. Benannte
      Nachweispflicht, kein Test — danach geöffnete Issues fallen unter das vorige Kriterium.
      **Gelaufen: 21 offene Issues, alle gekennzeichnet, keines bewusst ohne Bereich gelassen.**
- [x] **Tritt neben Status und Priorität.** Kein Katalogeintrag einer `board-`-Operation ändert
      sich; `issue-bereich-setzen` schreibt kein Board-Feld und trägt keine Nachhol-Zeile; die
      Kette in `refinement` behält `board-prioritaet-setzen` und `board-status-setzen` mit Wert
      `Ready` unverändert als letzte Schritte.
- [x] **Fehlschlag hält die Story zurück.** Scheitert `issue-bereich-setzen` auf allen Wegen,
      entfallen alle nachfolgenden Operationen, das Issue erreicht `Ready` nicht, und der Schritt
      erscheint **nicht** unter `## Lokal nachzuholen`.

## Datenmodell-Bezug

Nicht relevant. Kein Anwendungscode, keine Entität, keine Änderung an
[`docs/architecture.md`](../../docs/architecture.md) oder `docs/setup.md`.

## Architektur / Umsetzung

Gewählter Ansatz (ADR [`0085`](../decisions/0085-bereich-als-label-mit-geschlossenem-vorrat.md)):
Der Bereich ist ein **GitHub-Label** mit dem Präfix `bereich:`, kein Projects-V2-Feld — Projects V2
kennt kein Multi-Select, und alle vier Board-Operationen sind remote über keinen Weg erreichbar,
also genau dort, wo der Wert entstehen soll. Die Änderung lebt vollständig im Ablauf-/Katalogtext
unter `.claude/` und in den Repo-Konsistenztests unter `scripts/tests/`.

**Datenfluss.** `refinement` schärft die Story, leitet den Bereich aus `## Ziel` und den
Akzeptanzkriterien ab und schreibt ihn über eine neue Katalog-Operation ans Issue. Das Label reist
von dort ohne weiteren Schritt auf die Projects-Karte und in die Filterleiste. Kein zweiter
Wahrheitsort, keine Synchronisation, kein Zustand im Repository.

**Wiederverwendetes Muster:** Ein Label-Vorrat als Literal im Katalog existiert bereits
(`idee`/`bug` bei `issue-anlegen`); der Wächter folgt der Bauart von `ERWARTETE_OPERATIONEN`.

### Betroffene Dateien

- **`.claude/skills/github-access/SKILL.md`** — zwei neue Katalogeinträge:
  - **`issue-bereich-setzen`** (Wege `mcp`, `gh`). Trägt den Vorrat als Literal in genau einer
    Zeile fester Form (`**Bereichsvorrat (geschlossen):** …`). Gegenstand ist der **Zielzustand**
    der Label-Menge. `gh`: `--add-label`/`--remove-label`; `mcp`: `labels` als typisierte Liste mit
    der **vollständigen** Menge, sonst fallen `idee`/`bug` still weg. Der Eintrag hält beide
    wegabhängigen Eigenheiten fest: Ein unbekannter Wert scheitert auf dem `gh`-Weg laut
    (gemessen) und wird auf dem `mcp`-Weg von der Issues-API stillschweigend angelegt (unbelegte
    Annahme, siehe „Teststrategie", Punkt 4). Dazu die **Drift-Prüfung** des `mcp`-Wegs: erneut
    lesen unmittelbar vor dem Schreiben, bei Abweichung nicht schreiben — sonst stellte die
    vollständige, veraltete Menge eine zwischenzeitlich zurückgezogene
    `approved-for-agent`-Freigabe wieder her. Keine Nachhol-Zeile.
  - **`issue-liste-lesen`** (Wege `mcp`, `gh`). Auswertungsgrenze `number`, `labels`, `state`,
    `author` — **ohne `title`** (Begründung unter „Security"). `gh issue list --repo … --state open
    --limit <n> --json number,labels,state,author`; die Vorgabegrenze von 30 trägt hier nicht.
- **`.claude/skills/refinement/SKILL.md`** — Schritt 6 bekommt die Ausführungsstelle, hinter
  `issue-titel-schreiben` und vor den Board-Zugriffen. Der Skill nennt nur die Operations-ID,
  **niemals** einen der sechs Werte. Drei Festlegungen: (1) Der Bereich ist Metadatum — das Verbot
  technischer Details in Schritt 6 gilt unverändert und betrifft den **Body**, nicht das Label.
  (2) Trifft kein Bereich zu und trägt das Issue auch keinen, entfällt die Operation ersatzlos; der
  bisherige Bestand kommt aus `labels` des Schritt-0-`issue-lesen`, ein zusätzlicher Lesezugriff
  entsteht nicht. (3) Ihr Fehlschlag hält die Story zurück (siehe Akzeptanzkriterium).
- **`.claude/skills/capture/SKILL.md`** — **unverändert.** Die Leere beim Erfassen ist das Fehlen
  eines Schritts, geprüft als Abwesenheit.
- **`scripts/tests/test_github_zugriff_an_einer_stelle.py`** — `ERWARTETE_OPERATIONEN` um beide IDs
  erweitern, `assert len(ids) == 17` → `19`, `issue-liste-lesen` in `LESENDE_OPERATIONEN`.
- **`scripts/tests/test_issue_befehle_in_skills.py`** — `list` in `LESENDE_VERBEN`; die Kette in
  `reihenfolge_verstoesse` von drei auf vier Glieder: Body < Titel < **Bereich** < jede
  `board-`-Ausführungsstelle. Jedes neue Glied erbt die vier Bedingungen der Spec-0288-Sektion,
  insbesondere die Existenz-Zusicherung mit eigener Meldung.
- **`scripts/tests/test_bereichsvorrat.py`** *(neu)* — siehe „Teststrategie".
- **`.github/workflows/ci.yml`** — der Kommentar am `demo-scripts`-Job „(17 Operationen, …)" → 19.
- **`docs/ai-workflow.md`** — ein Satz im `capture`/`refinement`-Absatz, der nur die Operations-ID
  nennt, keinen Wert.
- **`specs/architecture/0002-testkonzept.md`** — eine neue `###`-Sektion (siehe „Teststrategie").
- **`specs/architecture/0003-securitykonzept.md`** — ein neuer Abschnitt (siehe „Security").
- **Nicht anfassen:** `specs/features/0339-ein-ort-fuer-jeden-github-zugriff.md` nennt „17
  Operationen" in einem Zitatblock; die Spec ist `Implemented` und wird nicht nachgezogen.

### Reihenfolge der Umsetzung (jede Einheit rot vor grün)

1. **Katalog-Operationen.** Erst die beiden bestehenden Wächter mitziehen (Operationsmenge → 19,
   `LESENDE_OPERATIONEN`, `LESENDE_VERBEN`) — sie werden dadurch rot —, dann die zwei
   Katalogeinträge samt Vorrat-Zeile schreiben.
2. **Vorrat-Wächter.** `test_bereichsvorrat.py` mit synthetischen Gegenproben, danach gegen den
   echten Bestand verdrahten. Mutationsnachweis wird geführt, nicht geglaubt.
3. **Ablauf.** `refinement` Schritt 6 ergänzen, Ketten-Zusicherung mitziehen.
4. **Mitziehen.** `ci.yml`-Kommentar, `docs/ai-workflow.md`, Test- und Sicherheitskonzept.
5. **Einmalige Einrichtung und Nachlauf** — **gelaufen** (kein Code, vor Eröffnung des Pull
   Requests; Ergebnisse unter „Teststrategie" und in den Akzeptanzkriterien): Daniel legt
   die sechs Label einmal im Repository an — keine Operation legt sie an. Danach ein Sitzungslauf:
   `issue-liste-lesen`, je Issue `issue-lesen`, Zuordnung, `issue-bereich-setzen`. Dazu der
   Repro-Lauf am Wegwerf-Issue (siehe „Teststrategie").

## UI/UX

Nicht relevant. Die Änderung lebt vollständig in `.claude/`-Ablauftext, `scripts/tests/` und Doku —
keine Datei unter `frontend/`, keine in PhotoSort dargestellten Daten. Das Board ist GitHubs
Oberfläche und nicht Gegenstand des Design-Systems.

## Security

Kein Anwendungscode, kein Endpunkt, kein Datenmodell, keine Foto-/Auth-Daten, kein neues Secret,
kein neuer Netzwerkpfad und kein neuer Scope. Betroffen ist allein das Asset „Integrität des
KI-gesteuerten Entwicklungsprozesses". Einstufung: **sicherheitsrelevant, kein Blocker.** Drei
Verschiebungen tragen den Gehalt: eine schreibende Operation an einem öffentlichen Repository, die
erste **listende** Leseoperation des Katalogs, und ein Stapellauf über eine Zielmenge, die Dritte
mitbestimmen.

### 1. `issue-liste-lesen` ist keine zweite Ausnahme von Härtungsregel 4.2

Die Nummern dieser Antwort sind Leseergebnis, nicht frei verwendbare Steuerwerte. `^[0-9]+$` führt
sie **nicht** auf die Regel zurück: Ein Muster prüft die Form eines Werts, nicht seinen Referenten
— jede Nummer dieses Repositoriums erfüllt es, auch die eines fremd angelegten Issues. Was die
bestehende Ausnahme bei `issue-anlegen`/`pr-erstellen` trägt, ist die **kausale Eigenherkunft**:
Der Ablauf hat das Artefakt selbst erzeugt. Diese Herkunft fehlt hier.

**Muss — der Katalogeintrag zieht die Grenze wörtlich.** Eine gelesene Nummer darf einen
schreibenden Aufruf nur unter **allen vier** Bedingungen steuern:

1. gegen `^[0-9]+$` validiert und ausschließlich als Zahl weiterverwendet (Typverengung, kein
   Herkunftsnachweis — sie ersetzt keine der folgenden drei);
2. aus **derselben Ausführung dieser Operation im selben Lauf** — nie eine gespeicherte, nie eine
   aus einem früheren Lauf, nie eine aus einem Issue-Body, einem Titel oder einem Kommentar;
3. `owner`/`repo` bleiben auf beiden Wegen Literale aus dem Katalogtext;
4. der einzige schreibende Aufruf, den sie steuern darf, ist `issue-bereich-setzen`.

Bedingung 2 schließt den Zielentführungs-Pfad: Ein Body, der „setz bereich X auf #123" sagt, kann
die Zielmenge nicht erweitern. **Muss — die Grenze gilt nur für diese Operation**; jeder künftige
Ablauf, der Schreibziele aus einer Liste ableiten will, braucht seinen eigenen Eintrag.

### 2. Erste listende Leseoperation — Prompt-Injection-Fläche

Bisher war jeder Lesezugriff auf fremdbeschreibbaren Text entweder auf ein von Daniel benanntes
Artefakt gerichtet oder auf das eigene Artefakt des Ablaufs. `issue-liste-lesen` ist die erste
Operation, deren Auswahl niemand trifft: Wer ein Issue anlegt, entscheidet selbst, dass sein Text
in den Kontext gelangt. Aus „auf Zuruf geholt" wird „mitgenommen".

- **Muss — `title` entfällt aus der Auswertungsgrenze.** Von den Feldern ist es das einzige
  fremdbeschreibbare: `number` und `state` erzeugt GitHub, `labels` kann nur setzen, wer
  Schreib-/Triage-Recht hat. Der Nachlauf holt den Body ohnehin je Issue über `issue-lesen`, dessen
  Grenze `title` enthält — die Verengung kostet nichts und nimmt der listenden Operation jeden
  fremdbeschreibbaren Freitext.
- **Muss — `author` gehört hinein**, ausschließlich zum Vergleich gegen das Literal
  `TheRealKoller`; der Wert fließt nie in einen Aufruf.
- **Muss — Auswertungsgrenze als Obergrenze, wegunabhängig.** Auf dem `gh`-Weg über `--json`
  erzwungen, auf dem `mcp`-Weg zusätzlich über die Umfangsbegrenzung des Werkzeugs verengt.
- **Muss — `body` und `comments` werden nicht geholt.** Beide wären über `gh issue list --json`
  erreichbar; die Katalogeigenschaft „es gibt keine Operation, die Issue-Kommentare liest" bleibt
  unangetastet.
- **Muss — `<n>` in `--limit <n>` ist ein selbst gebildeter Wert**, nie aus einer Antwort
  abgeleitet. Er begrenzt, wie viel Fremdtext auf einmal in den Kontext gelangt, und ist damit ein
  Sicherheits-, kein Bequemlichkeitsparameter.
- **Muss — die Datenmaterial-Klausel steht am Eintrag selbst**, nicht als Verweis.

### 3. Der einmalige Nachlauf über die offenen Issues

Neu ist nicht der einzelne Lesezugriff, sondern die **Häufung**: zwanzig fremdbeschreibbare Bodys
in einem Kontext, gefolgt von zwanzig Schreibzugriffen aus demselben Kontext. Strukturell trägt,
dass ausschließlich einer der sechs Werte oder keiner ableitbar ist — erzwingbar ist höchstens ein
falscher, aber gültiger Bereich, nie ein freier Wert.

- **Muss — Zielmenge.** Geschrieben wird ausschließlich an Nummern aus derselben Ausführung von
  `issue-liste-lesen`. Aus keinem gelesenen Body und keinem Titel entsteht je ein Schreibziel.
- **Muss — Kennzeichnungspflicht.** Enthält ein Body eine eingebettete Anweisung, weist der Bericht
  das als eigenen, auffälligen Punkt aus. Der Lauf wird nicht abgebrochen; der Fund wird sichtbar.
- **Muss — Sichtbarkeit vor dem Schreiben.** Die vollständige Liste (Nummer → vorgesehene Werte,
  fremde Autorschaft markiert) erscheint einmal im Chat, bevor der erste Schreibzugriff läuft. Bei
  zwanzig nicht zurücknehmbaren Schreibvorgängen an einem öffentlichen Repository ist das die
  billigste wirksame Kontrolle.
- **Muss — kein Dauerbetrieb.** Einmalig und interaktiv. Kein Workflow, kein Cron, kein Trigger.

### 4. `issue-bereich-setzen`: Zielzustand über einer gelesenen Menge

Das still anlegbare Label auf dem `mcp`-Weg ist ein **Qualitätsbefund mit dünner Sicherheitskante**:
Der geschriebene Wert stammt aus einem geschlossenen Literal, es gibt keinen Eingabepfad, über den
ein Dritter die Zeichenkette wählen könnte. Der schwerere Punkt derselben Konstruktion ist das
**stille Wegfallen** — es ist ein Lesen-Ändern-Schreiben über eine Menge, an der die
`approved-for-agent`-Freigabepolitik hängt, für die laut `CLAUDE.md` der Label-Zustand zum
Bearbeitungszeitpunkt maßgeblich ist. Ein Rückschreiben könnte eine zurückgezogene Freigabe
wiederherstellen.

- **Muss — die Schreibmenge wird mechanisch gebildet:** gelesene Menge desselben Laufs, minus aller
  `bereich:`-präfigierten Einträge, plus der vorgesehenen Werte. Kein Label wird erfunden, keines
  durch Auslassen entfernt.
- **Muss — `approved-for-agent` wird von dieser Operation nie geschrieben.** Trägt ein Issue das
  Label, bleibt es unberührt und der Fall geht in den Bericht.
- **Muss — Lesen und Schreiben liegen im selben Lauf.**
- **Muss — der übergebene Wert wird vor dem Aufruf gegen das Vorrat-Literal abgeglichen**, weil der
  `mcp`-Weg einen unbekannten Wert nicht abweist.
- **Muss — der Bericht nennt je Issue die tatsächlich geschriebene Menge**, damit ein stilles
  Wegfallen sichtbar wird.

### 5. Erlaubnisstufen

Mechanisch ändert sich nichts. Ein stiller Zuwachs entsteht trotzdem: „nur lesend" heißt „jede
lesende Operation", der `review`-Orchestrator bekäme `issue-liste-lesen` ungefragt dazu.
**Muss — jeder der beiden neuen Einträge nennt seine Aufrufer** (`refinement` Schritt 6 und der
einmalige Nachlauf). Die Stufentabelle bleibt damit eine Obergrenze, keine Gebrauchserlaubnis.

### 6. Ausdrücklich nicht sicherheitsrelevant

Die Wahl Label statt Board-Feld, die sechs Namen selbst, die Sichtbarkeit auf der Karte, die
Eingrenzung, die Einordnung neben Status und Priorität, und dass `capture` den Bereich leer lässt.

## Teststrategie

**Ebene: ausschließlich Repo-Konsistenztests über Dateitext** (CI-Job `demo-scripts`). Kein
Produktcode, also kein Unit-, Integrations- oder E2E-Anteil, und **kein Bezug zum Coverage-Gate** —
die gemessene Zahl bewegt sich um exakt null. **Zugesichert wird die Verankerung, nie die
Befolgung:** Kein Artefakt zeichnet auf, ob bei einem Lauf tatsächlich ein Bereich vergeben wurde;
jede Konstruktion, die das behauptete, wäre grün, ohne etwas zu wissen.

**`scripts/tests/test_bereichsvorrat.py`** *(neu)* — reine Funktionen über ein Pfad→Text-Abbild,
Leser über `git ls-files`, leerer Suchraum als lauter `ValueError`, synthetische Gegenproben je
Zusicherung. Vier Zusicherungen:

- **(a)** Genau **eine** Zeile fester Form trägt den Vorrat, geparst über `^\*\*Bereichsvorrat`,
  verglichen gegen eine eingefrorene Menge. „Genau eine" statt „mindestens eine" — eine zweite
  Vorrat-Zeile ist ein Widerspruch und muss laut auffallen.
- **(b)** Kein `bereich:`-Wert außerhalb des Katalogs, unverankert gesucht. **Suchraum als
  Negativliste: alles von Git Verwaltete außer `specs/**` und der Wächterdatei selbst** — erstere
  sind eingefrorene Momentaufnahmen und diese Spec nennt den Vorrat selbst, letztere führt ihn als
  Erwartungsmenge und in jeder Gegenprobe. Nicht als UTF-8 lesbare Dateien werden übersprungen.
  Eine Positivliste wäre hier die falsche Bauart und ist im Review am Bestand widerlegt worden:
  Sie übersah `.github/ISSUE_TEMPLATE/*.yml`, wo `labels:`-Zeilen stehen, und blieb bei einem dort
  eingesetzten Bereichswert grün.
- **(c)** `refinement` führt eine Ausführungsstelle von `issue-bereich-setzen` an der richtigen
  Kettenposition (ausgelagert in `test_issue_befehle_in_skills.py`).
- **(d)** `capture` nennt weder die Operation noch einen Wert.

Zusätzlich: Der Block von `issue-bereich-setzen` trägt **keine** Nachhol-Zeile; und das
Label-Argument des `gh`-Wegs enthält keine Variable und keine Substitution — der Wert kommt aus
einem geschlossenen Vokabular, Regel 4.1 greift dort also nicht, und das gehört als Feststellung in
den Eintrag.

**Warum die Präfixbindung die Prüfbarkeit trägt.** Ein Scan nach den blanken Werten ist unmöglich:
`ai-workflow` ist der Dateiname `docs/ai-workflow.md`, und `design`, `backend`, `frontend`,
`pipeline`, `infra` sind Alltagswörter dieses Projekts. Ein Wortverbot wäre am eigenen Bestand
sofort rot und würde so lange abgeschwächt, bis es nichts mehr aussagt. `bereich:` ist deshalb die
Bedingung dafür, dass (b) überhaupt existieren kann.

**Mutationsnachweis**, fünf Familien, alle Proben werden zurückgenommen, Lauf als unqualifiziertes
`pytest` im Verzeichnis `scripts/`:

- **F1 Vorrat-Formzeile:** siebter Wert eingesetzt → rot; bestehenden Wert entfernt → rot; Zeile
  dupliziert → rot.
- **F2 Abwesenheits-Scan:** `bereich:frontend` **und** `bereich:doku` je einmal in
  `.claude/skills/spec-writer/SKILL.md` **und** in `docs/ai-workflow.md` → je rot.
- **F3 Kette:** Bereich-Zeile gelöscht / über den Titel geschoben / hinter den ersten Board-Zugriff
  geschoben / in Fließtext umgeschrieben → je rot.
- **F4 `capture`-Abwesenheit:** Operation und Wert je einmal eingesetzt → rot.
- **F5 Katalogmenge/Verben:** je einen neuen Eintrag entfernt → rot; `list` aus `LESENDE_VERBEN`
  entfernt → rot.

Drei nicht verhandelbare Regeln: (1) **Welcher Wächter rot startet, wird benannt** — (a), (c) und
die beiden Erweiterungen starten rot, (b) und (d) starten grün, weil ihr Erfolgsfall eine
Abwesenheit ist; für sie ist die Mutationsprobe die **einzige** Evidenz. (2) **Untergrenze für das
Gesehene:** Derselbe Test sichert zu, dass das `bereich:`-Muster im Katalog mindestens sechs
Vorkommen findet — sonst ist ein kaputtes Muster von einem sauberen Bestand nicht unterscheidbar.
(3) Bei mehrfach vorkommenden Zeichenketten wird die angefasste Fundstelle genannt.

**Board-Karte und Board-Filter — der Beleg statt eines Ersatztests.** Kein Test dieses
Repositoriums kann prüfen, dass das Label auf der Karte sichtbar ist oder dass sich das Board
eingrenzen lässt; beides sind Eigenschaften von GitHubs Oberfläche. Die einzige repo-seitige
Ersatzzusicherung ist die **Wahl des Trägers**. Vier Dinge sollten gemessen statt angenommen
werden. **Drei sind es inzwischen, eines bleibt offen und wird als Auslassung ausgewiesen, nicht
als erledigt:**

1. **Das Label erscheint auf der Karte — offen.** Eine Ansichtseinstellung des Boards; der
   Nachweis liegt bei Daniel.
2. **Das Board lässt sich eingrenzen — belegt.** `bereich:pipeline` grenzt auf 8 Issues ein,
   `bereich:ai-workflow` auf 5, `bereich:design` auf 0.
3. **Ein unbekannter Wert scheitert auf dem `gh`-Weg laut — belegt.**
   `--add-label bereich:tippfehler` scheitert mit `'bereich:tippfehler' not found`, Exit 1, **und
   legt kein Label an**. Es gab folglich auch nichts aufzuräumen.
4. **Derselbe Wert wird auf dem `mcp`-Weg still angelegt — nicht belegt, und das bleibt so.** Der
   `mcp`-Schreibzugriff wurde vom Berechtigungs-Klassifizierer der Umgebung abgelehnt. Auf dem
   `gh`-Weg ist dieser Nachweis **grundsätzlich nicht führbar**: Dass ein unbekannter Wert *still*
   angelegt wird, ist gerade die Eigenschaft des anderen Wegs. Die Aussage stammt damit weiterhin
   aus der API-Dokumentation und nicht aus einer Messung dieses Repositoriums, und die auf ihr
   ruhende Risikoabwägung (Variante A unter „Entscheidungen") steht **unter diesem Vorbehalt**.
   Tragend ist ohnehin nicht sie, sondern der Abgleich gegen das Vorrat-Literal vor dem Aufruf —
   der greift unabhängig davon, wie sich der `mcp`-Weg tatsächlich verhält.

Das Ergebnis gehört als benannter Nachweis in den PR-Body.

**`specs/architecture/0002-testkonzept.md`** bekommt eine neue `###`-Sektion mit vier Regeln: ein
geschlossener Wertvorrat wird an einer Formzeile geparst und durch einen Abwesenheits-Scan
gesichert, dessen Prüfbarkeit an einem Präfix hängt; eine Reihenfolge-Kette wächst nur mit ihren
Bedingungen; eine Zusage, die nur in einer Datei genannt wird, kann nicht desynchronisieren; die
Board-**Ansicht** ist eine neue Klasse untestbarer Zusage neben Branch Protection und
`main`-Workflows.

## Entscheidungen

- `architect` konsultiert (Schritt 1): Träger ist ein Label, ADR 0085 angelegt.
- `ux-ui-designer` nicht konsultiert (Schritt 2): Die Änderung berührt keine Datei unter
  `frontend/` und keine in PhotoSort dargestellten Daten; das Board ist GitHubs Oberfläche.
- `test-engineer` konsultiert (Schritt 3).
- `security-engineer` konsultiert (Schritt 3). Sein Befund korrigiert ADR 0085, Punkt 7: Die
  Konstruktion ist **keine** zweite Ausnahme von Härtungsregel 4.2, sondern eine Lesart mit vier
  Bedingungen. Die ADR wurde entsprechend nachgezogen.
- **Vier Punkte sind ohne Rückfrage entschieden**, weil sie vor dem Merge revidierbar sind und der
  Nachlauf ohnehin erst zum Schluss läuft; Daniel kann jeden davon kippen:
  1. `issue-liste-lesen` kommt als dauerhafte Operation in den Katalog, statt die Label von Hand zu
     vergeben — die Story verlangt „ohne zusätzlichen Pflegeschritt", und der Bereich steht laut
     Story gerade nicht im Titel.
  2. Der Nachlauf umfasst **alle** offenen Issues, auch die rohen Ideen (wörtliche Lesart des
     Akzeptanzkriteriums). Folge: Danach entstehen in `Unrefined` wieder unbeschriftete Issues —
     das ist die Regel, kein Rückstand.
  3. Fremd angelegte Issues werden **mitgekennzeichnet**, aber über `author` erkannt und in der
     Vorab-Liste markiert. Die Wirkung eines `bereich:`-Labels ist gering und reversibel.
  4. Das still anlegbare Label auf dem `mcp`-Weg wird **hingenommen** (Variante A), abgesichert
     durch den Abgleich gegen das Vorrat-Literal. *Nachtrag nach dem Nachlauf:* Die Eigenschaft
     selbst ist unbelegt geblieben (Teststrategie, Punkt 4) — die Entscheidung steht unter diesem
     Vorbehalt, ihre Absicherung hängt aber nicht daran. Die Alternativen wären, die Operation auf den
     `gh`-Weg zu beschränken (fiele in Cloud-Sessions aus) oder nach jedem Schreiben zurückzulesen.
- **Bekannte, bewusst getragene Lücke:** Der `ci.yml`-Kommentar ist eine ungewachte zweite Nennung
  der Operationszahl. Ein Kommentar trägt keine Zusage, deshalb entsteht dafür kein Wächter.
- **Hinweis für die Review-Phase, im Review selbst korrigiert:** Der Diff liegt unter
  `.claude/**`, `scripts/tests/**`, `specs/**` — und unter `.github/workflows/ci.yml`. Die
  Trigger-Tabelle in `.claude/skills/review/SKILL.md` nennt von diesen Pfaden allein
  `.github/workflows/**`; `review-security` lief damit mechanisch getriggert, eine ausdrückliche
  Anforderung war nicht nötig. Ausgelöst hat das aber eine **Kommentarzeile** („17 Operationen" →
  „19") — ohne sie hätte der Diff keinen Trigger getroffen. Der Befund steht unter „Bekannte
  Lücken" im Sicherheitskonzept.

## Out of Scope

- Eine Auswertung oder Statistik über die Bereiche.
- Eine automatische Herleitung des Bereichs aus geänderten Dateien eines Pull Requests.
- Bereiche an Pull Requests; es geht ausschließlich um Issues auf dem Board.
- Eine generische „Label setzen"-Operation — ein steuernder Wert ohne geschlossenen Vorrat ist
  genau das, was Härtungsregel 4.2 ausschließt.
