# 0452 - Eine Story trägt ihren Designentwurf

**Status:** Accepted
**Erstellt:** 2026-09-13
**Bezug:** [GitHub-Issue #452](https://github.com/TheRealKoller/photosort/issues/452)

**Umfang:** über dem Richtwert von rund 200 Zeilen. Grund: Der Abschnitt `## Design` ist der erste
strukturierte Kanal aus einem öffentlichen Issue-Body in eine Spec-Datei, die `developer` als
Bauanleitung liest. Seine Feldform, die Zeichenauflagen an beiden Werten und die zwölf
Sicherheitsauflagen sind Zusicherungen, nicht Erläuterung — sie stehen vollständig, weil kein Test
dieses Repositoriums je ein Exemplar des Blocks zu sehen bekommt.

## Ziel

Entwürfe und Stories entstehen getrennt voneinander: Ein Entwurfsrundenlauf kennt keine Story, und
eine geschärfte Story kennt keinen Entwurf. Wer eine Idee mit Oberflächenbezug schärft, entscheidet
dabei blind über Aufteilung, Dichte und Rangfolge der Informationen — Fragen, die sich am sichtbaren
Entwurf in Minuten klären und im reinen Gespräch oft gar nicht erst auffallen.

Dazu kommt eine zweite Lücke: Selbst ein vorhandener Entwurf erreicht die Umsetzung nicht. Der
Umsetzungslauf liest die technische Spec, nicht das Issue — ein Verweis, der nur am Issue hängt,
kommt beim Bauen nie an.

Diese Spec schließt beide Lücken. Sie deckt zwei Einstiegspunkte ab, die denselben Mechanismus
teilen: eine noch rohe Idee, die design-unterstützt geschärft wird (A), und eine bereits geschärfte
Story, der nur der Entwurf fehlt (B).

## User Story

Als Daniel möchte ich eine Idee anhand sichtbarer Entwürfe schärfen und einer Story ihren Entwurf
dauerhaft anheften, damit Gestaltungsfragen vor der Umsetzung entschieden sind und der gewählte
Entwurf beim Bauen tatsächlich herangezogen wird.

## Akzeptanzkriterien

Geschärft auf Testbarkeit; die Formulierungen ersetzen die des Issue-Bodys, ohne dessen Aussage zu
verändern.

**Für beide Einstiegspunkte**

- [ ] Schritt 3b in `refinement` läuft nur auf Daniels ausdrückliche Äußerung im Gespräch; ohne sie
      wird er weder angeboten noch ausgeführt, und Schritt 3 geht unverändert in Schritt 4 über.
      `story-entwurf` wird nie von einem anderen Ablauf automatisch aufgerufen.
- [ ] Eine geschärfte Story trägt als **letzten** Abschnitt ihres Bodys genau einen
      `## Design`-Abschnitt mit genau den drei Feldern `Stand`, `Penpot-Seite`, `Schlüssel` in
      dieser Reihenfolge; `Stand` ist genau einer aus `Arbeitsstand` / `ausgearbeitet`.
- [ ] Gibt es keinen Entwurf, entfällt der Abschnitt ersatzlos — kein leerer Abschnitt, kein
      Platzhalter, kein dritter `Stand`-Wert. Ein abgebrochener Entwurfslauf schreibt gar nicht; ein
      bereits vorhandener Abschnitt bleibt dann unverändert stehen.
- [ ] Der Verweis erreicht die Umsetzung: `spec-writer` übernimmt ihn beim Anlegen der technischen
      Spec in deren `## UI/UX`-Abschnitt, sodass der **Umsetzungslauf** (`developer`) ihn dort
      vorfindet, ohne das Issue zu lesen. Ein `Schlüssel`, der in `design/penpot/views.json` nicht
      auflösbar ist, wird als benannter offener Punkt in `## UI/UX` vermerkt und bricht nicht ab.
- [ ] `penpot-entwurfsrunden` und `penpot-design` behalten die Erlaubnisstufe „kein GitHub-Zugriff".
      Genau ein Ablauf schreibt am Issue (`story-entwurf`), und er verwendet genau drei Operationen:
      `board-status-und-prioritaet-lesen`, `issue-lesen`, `issue-body-schreiben`.
- [ ] Die Freigabe zur Ausarbeitung stammt aus `board-status-und-prioritaet-lesen`, ausgewertet am
      Knoten `project.number == 8`. **Fail-closed heißt: jeder Wert außer `Ready` und jeder
      Fehlschlag des Lesens selbst bedeuten „keine Freigabe"** — dann nur Arbeitsstand, keine
      Ausarbeitung, kein Pull Request.
- [ ] Sobald eine ausgearbeitete Ansicht existiert, verweist derselbe `## Design`-Abschnitt auf sie
      statt auf die Arbeitsseite; er wird ersetzt. Es entstehen unter keinen Umständen zwei
      `## Design`-Abschnitte.

**Weg A — design-unterstützte Schärfung einer rohen Idee**

- [ ] Die Idee wird zuerst kurz verstanden (was soll erreicht werden, welche Fragen sind offen),
      bevor der erste Entwurf entsteht.
- [ ] Es entstehen mehrere erkennbar verschiedene Entwurfsansätze zur Auswahl, nicht ein einzelner
      Vorschlag.
- [ ] Fragen und Entscheidungen, die beim Entwerfen auftreten, werden gestellt statt geraten.
      Kritische Rückfragen, die die Idee selbst in Zweifel ziehen, sind ausdrücklich erwünscht.
- [ ] Entwürfe lassen sich über mehrere Runden verfeinern, bis eine Auswahl getroffen ist.
- [ ] Nach der Auswahl läuft die Schärfung regulär zu Ende — einschließlich der kritischen Prüfung,
      ob die Idee es überhaupt wert ist, und des Übergangs auf `Ready`.
- [ ] Während der Runden wird nichts ausgeliefert: keine ausgearbeitete Ansicht, keine Aufnahme in
      die geprüfte Design-Nutzlast, kein Pull Request.
- [ ] Wird die Idee verworfen, ist nichts ausgeliefert worden, das wieder zurückzunehmen wäre.

**Weg B — Entwurf zu einer bereits geschärften Story**

- [ ] Der Weg ist eigenständig aufrufbar für eine Story, die bereits `Ready` ist, ohne dass dafür
      die technische Umsetzung beginnen muss.
- [ ] Es wird kein vollständiges Refinement wiederholt.
- [ ] Zeigt sich beim Entwerfen eine Lücke oder ein Fehler in der geschärften Story, wird das
      gemeldet und gezielt nachgebessert — nachgebessert wird ausschließlich der fachliche Body
      (Ziel/User Story/Akzeptanzkriterien), der Board-Status bleibt unangetastet auf `Ready`.
- [ ] Der Entwurf wird ausgearbeitet und ausgeliefert, da die Story die Lohnenswert-Prüfung bereits
      bestanden hat.
- [ ] Die Story behält ihren Status `Ready`. Ein Entwurfslauf allein beginnt die Umsetzung nicht.

## Datenmodell-Bezug

Nicht relevant. Keine Entität, keine Migration, kein Feld — die Spec berührt ausschließlich
Skill-/Agenten-Dateien, die Wächtertests unter `scripts/tests/` und `docs/ai-workflow.md`.

## Architektur / Umsetzung

**Gewählter Ansatz:** Weg A wird in `refinement` eingebaut, Weg B als neuer Skill `story-entwurf`
angelegt. Beide teilen sich einen **gemeinsamen Nachlauf**, der genau einmal existiert (in
`story-entwurf`) und drei Dinge tut: Freigabe feststellen, ggf. ausarbeiten und ausliefern, den
`## Design`-Abschnitt an das Issue schreiben.

Weg A verlangt Entwurfsrunden *mitten* im Schärfungsgespräch — nach der Code-/Spec-Recherche und vor
dem Lohnenswert-Gate, damit das Gate über die Idee urteilt, die die Entwürfe gezeigt haben. Ein
Skill, der `refinement` umschließt, könnte die Runden nur davor oder danach legen. Weg B umgekehrt
hat eine invertierte Vorbedingung (`Ready` statt ungeschärft), darf das Lohnenswert-Gate gerade
nicht erneut auslösen und schreibt den Body fort statt ihn zu verfassen; als Modus in `refinement`
würde dessen fail-closed-Reihenfolge an drei Stellen bedingt.

### Der Abschnitt `## Design` — Form an genau einer Stelle

Die Form steht vollständig in `story-entwurf` und wird nirgends zweitgeschrieben; `refinement`,
`spec-writer` und `ux-ui-designer` verweisen darauf. Drei Felder, fester Vorrat:

```markdown
## Design

**Stand:** ausgearbeitet
**Penpot-Seite:** Ansicht — Projektübersicht
**Schlüssel:** uebersicht
```

- `Stand` ist genau einer aus `Arbeitsstand` / `ausgearbeitet` — geschlossener Vorrat, kein dritter
  Wert.
- Bei `ausgearbeitet` stammen beide Werte aus dem Eintrag in `design/penpot/views.json` (`seite`,
  `schluessel`), sind also im Repository auflösbar.
- Bei `Arbeitsstand` ist `Schlüssel` der `entwurfslauf` des Rundenlaufs und `Penpot-Seite` dessen
  Arbeitsseite `Entwurf — <Bezeichnung>`; beides existiert ausschließlich in der Design-Datei, und
  der Abschnitt sagt das über `Stand`.
- Das Präfix des Seitennamens folgt aus `Stand` (`Ansicht — ` / `Entwurf — `) und wird gegen ihn
  geprüft — zwei Angaben, die sich gegenseitig belegen.
- Kein Wert stammt aus einer Penpot-Rücklesung.
- **Ort im Body:** immer als letzter Abschnitt. Ein vorhandener `## Design`-Abschnitt wird ab seiner
  Überschrift vollständig ersetzt, nie ergänzt; alles davor bleibt Byte für Byte unverändert. Steht
  ein vorhandener Abschnitt **nicht** am Ende, hält der Lauf an und meldet — umsortiert wird nie:
  Das wäre die einzige Operation, die den Body strukturell umschreibt, und sie fiele niemandem auf.
- Gibt es keinen Entwurf, läuft der Nachlauf nicht und der Abschnitt entsteht nicht — es gibt keinen
  Pfad, der einen leeren Abschnitt schreibt.

**Storygebundene Entwürfe führen ausschließlich den Umfang `ansicht`** (Produktentscheidung
Daniels). `ausschnitt` und `baustein` bleiben dem storyfreien Direktaufruf vorbehalten: Für sie
existiert keine ausgearbeitete, ausgelieferte Ablageform, ihr Verweis wäre nach dem Merge nicht
auflösbar und zeigte ins Leere, sobald die Arbeitsseite weggeworfen wird.

### Wer schreibt, mit welcher Operation

Geschrieben wird ausschließlich im Nachlauf von `story-entwurf` (Stufe *lesend und schreibend*), in
dieser Reihenfolge:

1. `board-status-und-prioritaet-lesen` — die **Auslieferungsfreigabe**, ausgewertet am Knoten
   `project.number == 8`, fail-closed auf `Ready`.
2. Mit Freigabe: Ausarbeitung nach `penpot-entwurfsrunden` Schritt 6 (beide Prüfbreiten,
   Variantenachse `zustand`, Plugin-Daten `ansicht`/`breite`), Eintrag in `design/penpot/views.json`
   samt Lücken, Kardinalitäten in `design/penpot/verify.js`. Ohne Freigabe: nichts davon.
3. `issue-lesen` → Drift-Prüfung gegen den Stand vom Laufbeginn → Body fortschreiben →
   `issue-body-schreiben`. **Die Lesung steht unmittelbar vor dem Schreibzugriff, nicht am
   Laufbeginn**, und das gilt für beide Schreibvorgänge.
4. Mit Freigabe: Übergabeblock an `ship-entwurf`.

Schritt 3 steht **vor** Schritt 4, weil das Anheften die tragende Zusage der Story ist: Scheitert die
Auslieferung, ist der Entwurf trotzdem dauerhaft an der Story.

**Die Nachbesserung aus Weg B ist ein eigener, vorgezogener Schreibvorgang.** Erst der fachliche
Body, dann das Anheften — zwei getrennte `issue-body-schreiben`. Die Byte-Zusage oben gilt
ausschließlich für den Anheft-Vorgang; andernfalls widerspräche sie der zugesagten Nachbesserung.

**Jeder der beiden Schreibvorgänge liest den Body unmittelbar davor neu** (M-S12). Zwischen dem
Laufbeginn und einem Schreibzugriff liegen der gesamte Rundenlauf und die Ausarbeitung; eine
Fortschreibung aus der alten Lesung überschriebe eine zwischenzeitliche Bearbeitung Daniels
stillschweigend, und die Selbstprüfung unten fänge das nicht — sie vergleicht gegen genau diese
veraltete Fassung. Weicht die frische Fassung vom Stand des Laufbeginns ab, hält der Lauf an.

**„Stand vom Laufbeginn" ist für beide Einstiegspunkte definiert**, sonst wäre die Prüfung auf
einem von ihnen nicht ausführbar: auf Weg B die Lesung aus Schritt 0 des Nachlaufs; auf Weg A der
Body, den `refinement` Schritt 6 selbst geschrieben hat und der mit der Übergabe an den Nachlauf
geht — dort läuft dessen Schritt 0 nicht.

**Die Zusicherung „Entwurfs-Skills ohne GitHub-Zugriff" bleibt strukturell gewahrt, weil die
Freigabe den Rundenablauf *erreicht*, statt von ihm *ermittelt* zu werden.**
`penpot-entwurfsrunden` bekommt dafür eine geschlossene Quellenliste: (a) Direktaufruf ohne Story —
Daniel erklärt den Entwurf für fertig, wie bisher; (b) Aufruf aus einem Story-Ablauf — der
aufrufende Ablauf nennt die Freigabe, nachdem er sie am Board festgestellt hat; (c) sonst keine.
Ohne Freigabe laufen Schritt 6 und 7 nicht: keine Ansichtsseite, kein `views.json`-Eintrag, kein
Übergabeblock.

**Der Entwurfs-Pull-Request trägt nie ein Closing-Keyword auf die Story.** Ein `Closes #NNN` zöge die
Karte auf `Review` und schlösse das Issue beim Merge — die Story soll aber `Ready` bleiben. Der
Übergabeblock trägt deshalb `**Story:** keine` (das Feld steuert ausschließlich die `Closes`-Zeile)
plus eine neue, ausdrücklich **nicht steuernde** Zeile `**Herkunft:** Story #NNN` als
Berichtsmaterial.

### Wie der Verweis die Umsetzung erreicht

`spec-writer` liest den Body ohnehin in Schritt 0. Zwei Ergänzungen:

- Ein vorhandener `## Design`-Abschnitt **schließt den Skip in Schritt 2 aus** — er ist per Bauart
  ein konkret benennbarer Anhaltspunkt für eine sichtbare Oberfläche.
- Der Block wird unverändert an `ux-ui-designer` durchgereicht; dieser übernimmt ihn als Kopf des
  `## UI/UX`-Abschnitts und löst den `Schlüssel` in `design/penpot/views.json` auf (Breiten,
  Zustände, Bausteine, Lücken gehen in den Abschnitt ein). Lässt er sich dort nicht auflösen — der
  Entwurfs-PR ist noch offen —, wird das als benannter offener Punkt in `## UI/UX` festgehalten,
  nicht stillschweigend weggelassen und nicht als Abbruch behandelt.

Weder `ux-ui-designer` noch `developer` können Penpot öffnen. Die Umsetzungsinformation trägt
deshalb nicht der Verweis, sondern `## UI/UX` in Worten plus der `views.json`-Eintrag; der Verweis
ist Beleg und Einstieg für Daniel und die Hauptsession.

### Betroffene Dateien, in dieser Reihenfolge

1. `specs/decisions/0094-entwurf-haengt-an-der-story-ausarbeitung-am-ready-gate.md` — neu (Nummer
   beim Anlegen gegen den Bestand prüfen; bei Kollision zieht das jüngere Dokument um).
2. `scripts/tests/test_github_zugriff_an_einer_stelle.py` — `ERWARTETE_STUFEN` um den neuen Skill
   ergänzen; zusätzlich ein benannter Test, dass die beiden Penpot-Skills „kein GitHub-Zugriff"
   tragen. Zuerst rot, dann:
3. `.claude/skills/story-entwurf/SKILL.md` — neu.
4. `scripts/tests/test_story_entwurf_skill.py` — neu.
5. `.claude/skills/penpot-entwurfsrunden/SKILL.md` + `scripts/tests/test_entwurfsrunden_skill.py` —
   Auslieferungsfreigabe als Bedingung für Schritt 6/7, geschlossene Quellenliste, Umfangsgrenze
   `ansicht`; die wörtlichen Zusagen des Direktpfads bleiben unverändert stehen.
6. `.claude/skills/ship-entwurf/SKILL.md` + `scripts/tests/test_ship_entwurf_skill.py` — die
   `**Herkunft:**`-Zeile als nicht steuerndes Berichtsmaterial, `**Story:** keine`, und der
   Erkenner gegen ein Closing-Keyword an dieser Zeile.
7. `.claude/skills/github-access/SKILL.md` — `story-entwurf` in die Erlaubnisstufen-Tabelle und in
   die Aufrufer-Zeilen der drei Operationen; ein Satz bei Härtungsregel 4.3, dass die unveränderte
   Rückschrift desselben Bodys in dasselbe Issue kein Hineingelangen von Fremdtext ist.
8. `specs/architecture/0002-testkonzept.md` und `specs/architecture/0003-securitykonzept.md` — die
   unter „Teststrategie" bzw. „Security" benannten Ergänzungen.

Damit ist Weg B vollständig und für sich nutzbar. Der Durchgriff folgt:

9. `.claude/skills/refinement/SKILL.md` — neuer Schritt 3b (Runden auf ausdrücklichen Wunsch, erste
   Runde im Modus `alternativen`) und die Übergabe an den Nachlauf am Ende von Schritt 6, nach dem
   `board-status-setzen`-Versuch.
10. `.claude/skills/spec-writer/SKILL.md` und `.claude/agents/ux-ui-designer.md` — Skip-Ausschluss
    und Durchreichen.
11. `docs/ai-workflow.md` — Rollen-Landkarte und Workflow-Tabelle um den neuen Skill und die zwei
    Einstiegspunkte.

**Schnitt in zwei Pull Requests:** (1) Punkte 1–8, (2) Punkte 9–11. Kein `xfail` und keine
übersprungenen Tests im ersten PR — die Durchgriff-Tests entstehen mit dem Durchgriff.

`docs/architecture.md` und `docs/setup.md` bleiben unberührt: Systemarchitektur, Datenmodell und
lokales Setup ändern sich nicht.

### Bewusst nicht

- Kein neuer Anker zwischen `refinement` und `story-entwurf`: beide laufen in der Hauptsession, ein
  Skill lädt den anderen. Anker gibt es nur über Agentengrenzen.
- Kein Issue-Kommentar als Träger des Verweises: keine Katalog-Operation liest Kommentare, der
  Verweis erreichte `spec-writer` nie.
- Keine neue Katalog-Operation.
- Keine Funktion unter `scripts/`, die den Body fortschreibt. Der Ablauf bleibt Text; tragend ist
  stattdessen die Selbstprüfung unter „Teststrategie".

## UI/UX

Nicht relevant. Die Spec berührt keine sichtbare Oberfläche der Anwendung — kein Artefakt unter
`frontend/src/`, keine Stelle, an der etwas angezeigt oder eingegeben wird. Dass ihr Gegenstand
Designentwürfe sind, ändert daran nichts: Sie regelt, wie ein Entwurf an eine Story kommt, und baut
selbst keine Ansicht.

## Security

Kein Anwendungscode, kein Endpunkt, kein Datenmodell, keine Foto-/Auth-Daten, kein neues Secret,
kein neuer Netzwerkpfad, keine Änderung an Auth oder an der Sichtbarkeit von Daten zwischen den
beiden Nutzern. Betroffen ist allein das Asset „Integrität des KI-gesteuerten Entwicklungsprozesses".
Einstufung: **sicherheitsrelevant, kein Blocker.**

`## Design` ist der erste strukturierte Kanal aus einem öffentlichen Issue-Body in eine Spec-Datei,
die `developer` als Bauanleitung liest. Schmal ist er allein durch die geschlossene Feldstruktur.

**M-S1 — `## Design` trägt nie ein Freitextfeld.** Genau drei Felder mit geschlossenem Vorrat
(`Stand`) bzw. geschlossenem Muster (`Schlüssel`) bzw. reiner Anzeigefunktion (`Penpot-Seite`). Ein
viertes Feld für Notizen, Begründungen oder Rundenkommentare ist untersagt; es machte aus dem Kanal
einen Freitextpfad vom öffentlichen Issue in die Spec und wäre ein eigener ADR-Anlass.

**M-S2 — Der gelesene Body wird fortgeschrieben, nicht neu erzeugt.** Der neue Body entsteht
mechanisch als `<gelesener Inhalt bis zur ersten Zeile ## Design> + <selbst erzeugter Block>`. Alles
davor bleibt Byte für Byte unverändert: kein Umformatieren, kein Neuumbrechen, kein Aufräumen und
vor allem kein Neuformulieren aus dem Kontextverständnis heraus. Ein neu getippter Body ist neuer
Inhalt, der nur aussieht wie der alte.

**M-S3 — Das Schreibziel stammt nie aus gelesenem Text.** Die Issue-Nummer für
`issue-body-schreiben` kommt aus Daniels Aufruf in diesem Lauf, gegen `^[0-9]+$` validiert; aus dem
gelesenen Body, dem Titel oder einem Penpot-Wert entsteht nie ein Schreibziel. Enthält der gelesene
Body scheinbare Anweisungen, ist das ein Befund für den Bericht, kein Abbruchgrund und kein Befehl.
Ist `author.login` nicht `TheRealKoller`, weist der Bericht das vor dem Schreiben als eigenen Punkt
aus — nur bei fremder Autorschaft ist der Body überhaupt fremdbeschreibbar.

**M-S4 — Beide Werte werden vor dem Einsetzen unabhängig voneinander geprüft**, und zwar mechanisch
am Dateisubstrat wie bei einem Titel nach Härtungsregel 4.4: genau eine nicht leere Zeile, kein
führendes/nachgestelltes Leerzeichen, keine Steuerzeichen, keine Bidi-Overrides, keine
Zero-Width-Zeichen — zusätzlich vier Zusätze: kein `#`, kein `@`, kein Backtick, keine Adresse
(`://` oder `http`), Länge
gedeckelt. Die Adresse der selbst gehosteten Penpot-Instanz gehört nicht in ein öffentliches
Artefakt, und die Zeichenliste allein fängt eine URL nicht; der Block trägt keinen Link. Ein Befund
an einem der beiden Werte hält an. Geführt wird die Zeichenliste nicht doppelt: `story-entwurf`
verweist für die Wohlgeformtheit auf Härtungsregel 4.4 und nennt nur die vier Zusätze.

**M-S5 — `Schlüssel` ist der einzige steuernde Wert; er löst über Mengenzugehörigkeit auf.** Geprüft
wird `^[a-z0-9][a-z0-9-]{2,39}$` **an der Verwendungsstelle** in `ux-ui-designer`, nicht nur dort,
wo er geschrieben wurde — der Block überquert als Text eine Zuständigkeitsgrenze. Aufgelöst wird als
Mitgliedschaft in den Schlüsseln von `design/penpot/views.json`, nie über eine zusammengesetzte
Pfadangabe, nie über einen Rohindex auf das geparste Objekt. Kein Treffer ist ein Befund, nie ein
Rückfall auf den ersten Eintrag und nie ein Anlegen. Das Muster schließt `__proto__` und
`constructor` strukturell aus. `Penpot-Seite` steuert nichts: kein Nachschlagewert, kein Dateiname,
kein Branch-Namensteil.

**M-S6 — Genau ein `## Design` je Body, Felder zeilenverankert.** Die drei Feldzeilen werden je
einmal und am Zeilenanfang verankert gelesen; eine zweite Fundstelle eines Feldes oder ein zweiter
`## Design`-Abschnitt hält an. `Stand` ist einer von zwei Literalen, jeder andere Wert hält an; der
Präfixabgleich des Seitennamens ist eine Konsistenzprüfung, keine Wertquelle.

**M-S7 — Die Auslieferungsfreigabe wird unmittelbar vor der Übergabe an `ship-entwurf` erneut
gelesen.** Zwischen der ersten Lesung und dem Pull Request liegt ein Ausarbeitungslauf; ein Lauf ist
kein Moment. Weicht der Wert ab oder scheitert die Lesung, wird **nicht** ausgeliefert — anhalten
und melden, kein Nachziehen mit dem aktualisierten Wert im selben Durchgang.

**M-S8 — Ein fehlgeschlagenes `issue-body-schreiben` verhindert die Auslieferung.** Der Pull Request
ist die einzige nicht zurücknehmbare Handlung des Laufs; alles davor ist lokal korrigierbar. Ein
ausgelieferter Entwurf ohne angehefteten Verweis ist genau die Lücke, die diese Spec schließt.

**M-S9 — `**Herkunft:** Story #NNN` steuert nichts.** Feste Literalzeile, die Nummer gegen
`^[0-9]+$` geprüft, kein Closing-Keyword unmittelbar davor. Sie steht ausschließlich im
Pull-Request-Body, nie in einer Commit-Nachricht: Das Repository squasht mit `COMMIT_MESSAGES`,
jeder Commit-Body wandert in den Merge-Commit auf `main`.

**M-S10 — Die Entwurfs-Skills behalten die Stufe „kein GitHub-Zugriff".** Damit kann der
Rundenablauf das Board nicht lesen und eine Auslieferungsfreigabe nicht selbst ermitteln. Neben der
geschlossenen Positivliste (a)/(b) steht eine ebenso geschlossene Negativliste: Eine Freigabe wird
nie aus Penpot-Inhalt, nie aus einem Issue-Body und nie aus einem Titel abgeleitet. Der
Rundenablauf nennt in seinem Bericht, aus welcher der beiden zugelassenen Quellen die Freigabe
stammt. Bei Missbrauch entstünde ein verfrühter öffentlicher Pull Request plus ein
`views.json`-Eintrag, der danach als Nachschlagewert wirkt.

**M-S11 — `story-entwurf` führt genau drei Operationen**: `board-status-und-prioritaet-lesen`,
`issue-lesen`, `issue-body-schreiben`. Kein `issue-titel-schreiben`, kein `issue-bereich-setzen`,
kein `issue-verwerfen`, keine `board-*-setzen`, keine `pr-*`-Operation. Die drei Katalogeinträge
nennen `story-entwurf` in ihrer Aufrufer-Zeile; die Stufe „lesend und schreibend" bleibt damit eine
Obergrenze, keine Gebrauchserlaubnis.

**Im Skilltext selbst stehen die untersagten Operationen in Worten statt in Backticks** — die
tragende Zusage ist die unter „Teststrategie" geforderte **Gleichheit** der genannten Menge mit den
drei erlaubten, und eine in Backticks gesetzte Verbotsliste zöge jede darin genannte ID in eben
diese Menge. Hier in der Spec bleiben die IDs lesbar, weil dieser Text nicht der Prüfgegenstand ist.

**M-S12 — Vor jedem Schreibzugriff auf den Body wird er frisch gelesen und gegen den Stand vom
Laufbeginn geprüft** (oben definiert, für beide Einstiegspunkte). Zwischen der ersten Lesung und
einem Schreibzugriff liegen ein vollständiger
Rundenlauf mit mehreren Rückmeldezyklen und die Ausarbeitung; ein Lauf ist kein Moment, derselbe
Grund wie bei M-S7. Fortgeschrieben wird ausschließlich die frisch gelesene Fassung; weicht sie vom
Stand des Laufbeginns ab, **hält der Lauf an und meldet** — kein Nachziehen im selben Durchgang,
keine Zusammenführung. **Die Selbstprüfung fängt diesen Fall strukturell nicht:** Sie vergleicht den
erzeugten gegen den *gelesenen* Body und ist über einer veralteten Lesung grün, während der Schaden
entsteht. Ohne M-S12 überschriebe der Lauf stillschweigend, was Daniel während des Rundenlaufs am
Body geändert hat — sein eigener Text, in einem öffentlichen Artefakt, nicht zurückzunehmen.

**Restrisiken, bewusst getragen.** Ein `views.json`-Eintrag erreicht `main` über `ship-entwurf`,
also ohne Perspektivenrunde und ohne Copilot-Review; „im Repository auflösbar" heißt deshalb nicht
„von einem Prüfer gesehen". Die Zeichenprüfung sagt nichts darüber, ob der aufgelöste Eintrag der
richtige für diese Story ist — ein falscher, aber wohlgeformter Schlüssel führt zu einem falschen
Entwurf, nicht zu einem Zugriff außerhalb der Menge. In einer Cloud-Session ist
`board-status-und-prioritaet-lesen` auf keinem Weg erreichbar; Weg B liefert dort nie aus, sondern
bleibt bei `Arbeitsstand` — fail-closed und beabsichtigt.

**Ergänzung von `specs/architecture/0003-securitykonzept.md`** (im selben Branch): ein neuer
Abschnitt unter „Angriffsflächen" zum strukturierten Kanal aus einem öffentlichen Issue-Body in eine
Spec-Datei, mit M-S1 als projektweiter Auflage, der unveränderten Rückschrift eines fremden Bodys
sowie dem Body-Drift und dem Freigabe-Drift als zwei getrennten Punkten; unter „Bewusst akzeptierte
Restrisiken" der `views.json`-Eintrag, der über
den reviewfreien Auslieferpfad nach `main` kommt und danach als Nachschlagewert eines
Spec-Abschnitts wirkt.

## Teststrategie

Kein Anwendungscode — geprüft wird ausschließlich auf der Repo-Konsistenzebene (`scripts/tests/`,
CI-Job `demo-scripts`); Unit-, Integrations- und E2E-Ebene entfallen, das Backend-Coverage-Gate
bleibt unberührt. Besonderheit dieser Spec: **Die einzige Instanz des neuen Formats liegt außerhalb
des Repositoriums** — der `## Design`-Block lebt in einem Issue-Body, kein Test bekommt je ein
Exemplar zu sehen. Prüfbar ist allein die Erzeugungs- und Leseanweisung an ihren vier Orten.

Tragend sind fünf Zusicherungsklassen: (1) **Bestandsgleichheit** der Erlaubnisstufen — `story-entwurf`
steht mit „lesend und schreibend" in der eingefrorenen Tabelle, die Penpot-Skills behalten „kein
GitHub-Zugriff"; (2) **Whitelist-Gleichheit** der Operations-IDs in `story-entwurf` (genau drei,
nicht mehr und nicht weniger); (3) **Ein-Definitions-Regel** für den `## Design`-Block: Feldnamen und
Vorrat stehen genau einmal im lebenden Anweisungsraum `.claude/**`, die lesenden Dateien verweisen,
ohne zu kopieren — mit einer Gegenprobe, die belegt, dass eine bloße Erwähnung der Feldnamen in
Prosa nicht als Kopie zählt; (4) **Reihenfolge über Zeichenoffsets** — Issue-Fortschreibung vor der
Übergabe an `ship-entwurf`, Ausarbeitung hinter der Freigabeprüfung, in **jedem** Schreibschritt die
frische Lesung vor der Drift-Prüfung und diese vor dem Schreibzugriff, Schritt 3b zwischen Schritt 3
und Schritt 5 von `refinement`, der Skip-Ausschluss **innerhalb** des Skip-Absatzes von
`spec-writer` Schritt 2; (5) **Abwesenheit** — kein Closing-Keyword an der `Herkunft`-Zeile und in
keiner Commit-Vorlage des Entwurfs-Pull-Requests. Das Schlüsselmuster und die Umfangswerte werden
**aus den Quelltexten gelesen und auf Gleichheit geprüft**, nicht als Literal im Test notiert. Jeder
Erkenner trägt eine synthetische Probe seines eigenen Verstoßes und eine Gegenprobe des erlaubten
Falls.

**Selbstprüfung statt Test, verbindlich:** Vor jedem `issue-body-schreiben` liest der Ablauf den
Body **erneut**, prüft ihn gegen den Stand vom Laufbeginn (Abweichung hält an) und schreibt die
frisch gelesene sowie die erzeugte Fassung in je eine Datei, um sie mechanisch zu vergleichen.
Einziger zulässiger Unterschied ist der Bereich ab der `## Design`-Überschrift; jede weitere
Abweichung hält an. Existenz und Position **beider** Schritte — der Lesung und der Selbstprüfung,
je vor dem Schreibzugriff — sind per Offset prüfbar. Die Reihenfolge ist tragend, nicht
redaktionell: Die Selbstprüfung vergleicht gegen den gelesenen Body und wäre über einem veralteten
gelesenen Body grün, während sie den Schaden durchlässt.

**Edge Cases für die Umsetzung.** Body: ohne `## Design`; mit vorhandenem Abschnitt am Ende
(Idempotenz — ein zweiter Lauf ersetzt, verdoppelt nicht); Abschnitt nicht am Ende; zwei Abschnitte;
`### Design` statt `## Design`; `## Design` innerhalb eines umzäunten Codeblocks im Body; Body ohne
abschließenden Zeilenumbruch; CRLF. Werte: Präfix-Drift (`ausgearbeitet` + `Entwurf — `); Seitenname
mit Halbgeviertstrich statt Geviertstrich; doppeltes oder fehlendes Präfix; `#`, `@`, Backtick,
Zeilenumbruch, Zero-Width/Bidi, leer, Überlänge; `Schlüssel` mit Großbuchstabe, Unterstrich,
führendem Bindestrich, 2 bzw. 41 Zeichen. Ablauf: `Schlüssel` gültig, aber in `views.json` nicht
auflösbar; Board meldet nicht `Ready`; Board-Lesen scheitert; Knoten `project.number == 8` fehlt;
Weg B auf `In Progress`/`Review`/`Done`; storygebunden `ausschnitt`/`baustein` gewünscht;
Rundenlauf abgebrochen; **Body während des Laufs von Daniel bearbeitet** — vor dem
Nachbesserungs-Schreibzugriff, vor dem Anheft-Schreibzugriff, und zwischen beiden; erneutes
`issue-lesen` scheitert.

**Bewusst ungeprüft:** die Laufzeittreue der Anweisungen (nur auf Wunsch, Fragen statt Raten,
erkennbar verschiedene Ansätze) — Laufzeiteigenschaft eines LLM-interpretierten Textes, es wird
ausdrücklich keine Kennzahl erfunden; die Byte-Gleichheit eines real geschriebenen Issue-Bodys;
die Existenz der genannten Penpot-Seite. Dafür tragen die Selbstprüfung und Daniels Hinsehen.

**Ergänzung von `specs/architecture/0002-testkonzept.md`** (im selben Branch): eine neue Sektion zur
Prüfklasse „ein Format, dessen einzige Instanz außerhalb des Repositoriums liegt"; unter „Was bewusst
nicht getestet wird" die Byte-Gleichheit samt Nennung der Selbstprüfung; unter „Bekannte Lücken",
dass der `Stand`/`Penpot-Seite`-Wert gegen Penpot unbelegt ist und dass der Durchgriff bis in die
Umsetzung nur als Kette von Textzusagen gesichert ist.

## Entscheidungen

- **Storygebundener Entwurfsumfang: nur `ansicht`** (Daniel). `ausschnitt`/`baustein` haben keine
  ausgelieferte Ablageform; ihr Verweis wäre nach dem Merge nicht auflösbar. Damit gelten die
  Zusagen „wird vollständig ausgearbeitet und ausgeliefert" und „der Verweis erreicht die Umsetzung"
  ausnahmslos, statt eine zweite, schwächere Klasse von Verweisen zu erzeugen.
- **Das Fortschreiben des Bodys bleibt Anweisungstext** (Daniel), abgesichert durch die verbindliche
  mechanische Selbstprüfung vor dem Schreibzugriff. Keine Funktion unter `scripts/`: Der Ablauf ist
  durchgehend Text, und zwei Orte derselben Regel driften.
- **Weg B wird ein eigener Skill statt eines Modus in `refinement`** — invertierte Vorbedingung,
  kein erneutes Lohnenswert-Gate, fortgeschriebener statt verfasster Body.
- **Die Nachbesserung aus Weg B ist ein eigener, vorgezogener Schreibvorgang**, damit die
  Byte-Zusage des Anheftens widerspruchsfrei bleibt.
- **Ein vorhandener, nicht am Ende stehender `## Design`-Abschnitt hält den Lauf an**, statt
  umsortiert zu werden.
- **Ein abgebrochener Entwurfslauf schreibt nicht**; ein vorhandener Block bleibt stehen.
- **Ein `## Design`-Block aus einem fremdautorisierten Issue wird durchgereicht**, aber mit
  Autor-Kennzeichnung im Bericht (M-S3). Die Freigabe-Policy `approved-for-agent` aus `CLAUDE.md`
  bindet die künftige Automatisierung, nicht einen von Daniel selbst gestarteten Lauf, und wird hier
  nicht erweitert.
- **Die Wohlgeformtheitsprüfung der beiden Werte läuft mechanisch am Dateisubstrat** (M-S4), wie
  Härtungsregel 4.4 es für Titel vorschreibt — Bidi-Overrides und Zero-Width-Zeichen sind genau die
  Klasse, die ein Modell im eigenen Kontext nicht sieht.
- **`ux-ui-designer` nicht konsultiert (Schritt 2):** kein konkret benennbarer Bezug zu einer
  sichtbaren Oberfläche der Anwendung — kein Artefakt unter `frontend/src/`, keine Stelle, an der
  etwas angezeigt oder eingegeben wird.

## Offene Fragen

Keine.

## Out of Scope

- Eine ausgearbeitete, ausgelieferte Ablageform für `ausschnitt` und `baustein`.
- Eine technische Durchsetzung der Erlaubnisstufen zwischen Agent und Werkzeug; die Stufen bleiben
  Text plus statischer Wächtertest.
- Eine Rücklesung aus Penpot, die belegt, dass die genannte Seite existiert.
- Jede Änderung an `docs/architecture.md`, `docs/setup.md` oder am Datenmodell.
