---
name: idea-sharpener
description: Hilft dabei, eine neue Produkt-/Feature-Idee zu schärfen, bevor sie zur Spec wird — stellt Verständnisfragen, untersucht parallel den bestehenden Code und die vorhandenen specs/features/*.md auf Konflikte/Überschneidungen, hakt bei Unklarheiten nach, stellt kritische Gegenfragen (Devil's Advocate) und legt erst danach eine neue, direkt akzeptierte Feature-Spec an (ersetzt dabei ggf. eine bestehende Spec, falls die Idee sie obsolet macht). Nutze diesen Skill IMMER, wenn der Nutzer eine neue Idee, einen Feature-Wunsch oder eine Anforderung informell einwirft — z.B. "ich hab da eine Idee", "was hältst du davon, wenn wir X einbauen", "könnten wir nicht auch Y machen", "neue Anforderung: ...". Nicht nutzen, wenn der Nutzer eine bereits akzeptierte Spec tatsächlich umsetzen lassen will — dafür gibt es den `developer`-Agenten.

---

# Idea Sharpener — von der Idee zur akzeptierten Spec

Begleitet eine rohe Idee bis zu einer belastbaren, ins Projekt eingeordneten Feature-Spec. Der Punkt des Skills ist, dass eine Idee erst dann zur Spec wird, wenn sie drei Dinge überstanden hat: echtes gegenseitiges Verständnis, Abgleich mit dem, was schon existiert, und kritischen Gegenwind. Jeder dieser drei Schritte fängt eine andere Art von Fehler ab — Verständnisfragen verhindern, dass an der eigentlichen Absicht vorbei geplant wird; der Code-/Spec-Abgleich verhindert Doppelarbeit und stille Konflikte mit bereits Bestehendem; die kritische Prüfung verhindert, dass Ideen ungeprüft durchgewunken werden, nur weil sie zuerst gut klingen.

## Schritt 1: Verständnis schärfen

Stell Rückfragen, bis du die Idee wirklich verstehst — nicht nur, was gebaut werden soll, sondern warum und für wen. Typische Lücken, die es zu füllen lohnt: Welches konkrete Problem löst das? Wer nutzt es (beide Nutzer, nur einer, ein bestimmter Anwendungsfall)? Wie sieht "fertig"/"gut gelöst" aus? Gibt es einen Auslöser (z.B. gerade erlebtes Problem) oder ist es eine allgemeine Idee?

Nutze AskUserQuestion, wenn sich sinnvolle, klar unterscheidbare Optionen anbieten; sonst normale Rückfragen im Chat. Halte diesen Schritt knapp — es geht um ein grundsätzliches Verständnis, nicht um jedes Detail (Details klären sich oft erst durch die nächsten Schritte).

## Schritt 2: Roadmap-Einordnung und Anforderungsaufbereitung

Ruf den `requirements-engineer`-Agenten (Agent-Tool, `subagent_type: requirements-engineer`, im Vordergrund/`run_in_background: false`, da du das Ergebnis für die folgenden Schritte brauchst) mit dem Verständnis aus Schritt 1 auf. Er ordnet die Idee gegen `specs/roadmap.md` ein (Priorität, Konflikte mit bereits Geplantem) und liefert eine strukturierte erste Fassung von User Story und Akzeptanzkriterien, die du in den folgenden Schritten weiter verfeinerst statt bei roher Ideenbeschreibung zu starten.

## Schritt 3: Code und bestehende Specs untersuchen

Sobald du die Idee grundsätzlich verstehst, untersuche zwei Dinge — bei einer größeren Codebasis lohnt es sich, dafür zwei parallele Explore-Agenten zu starten (einen für Code, einen für Specs), bei einem kleinen Projekt reicht ein Durchgang selbst:

- **Bestehende Implementierung:** Was gibt es im Code schon, das die Idee berührt, worauf sie aufbauen müsste, oder was ihr im Weg steht? Wie groß wäre der Eingriff wirklich?
- **Bestehende Feature-Specs** (`specs/features/*.md`, alle Status): Gibt es Überschneidungen mit einer bereits geplanten oder umgesetzten Spec? Widerspricht die Idee einer bestehenden Entscheidung (`specs/decisions/*.md`)? Macht sie eine bestehende Spec teilweise oder ganz obsolet?

Das Ziel ist nicht erschöpfende Recherche, sondern genug, um echte Konflikte und Überschneidungen zu erkennen, bevor sie zum Problem werden.

## Schritt 4: Nachfragen bei Unklarheiten

Wenn die Recherche aus Schritt 3 etwas zutage fördert, das der ursprünglichen Vorstellung widerspricht oder eine neue Frage aufwirft (z.B. "die Idee setzt X voraus, aber im Code/in Spec Y ist das anders gelöst"), frag genau danach nach — nicht raten oder die Idee stillschweigend anpassen. Wenn nach Schritt 1 bis 3 wirklich nichts unklar ist, diesen Schritt einfach überspringen.

## Schritt 5: Kritisch hinterfragen (Devil's Advocate)

Bevor irgendetwas aufgeschrieben wird, stell dich bewusst gegen die Idee — jede Idee sollte ein wenig Gegenwind aushalten müssen, sonst ist sie nicht wirklich geprüft. Nütz­liche Angriffspunkte:

- Gibt es einen einfacheren Weg zum selben Ergebnis?
- Was ist der Aufwand im Verhältnis zum Nutzen — lohnt sich das wirklich jetzt?
- Was passiert im Fehlerfall / bei Edge Cases, die die Idee bisher nicht berücksichtigt?
- Steht das im Widerspruch zu einer bestehenden Priorität oder einem MVP-Zuschnitt (z.B. aus `specs/decisions/`)?
- Wer genau braucht das, und was passiert, wenn man es einfach nicht baut?

Das ist keine Formalität — wenn die Idee unter der Prüfung merklich schwächer wird oder sich ändert, ist das ein gutes Ergebnis: schärfen oder verwerfen, statt schönreden. Erst wenn die Idee (ggf. in angepasster Form) plausibel Stand hält, geht es weiter.

## Schritt 6: Architektonischen Ansatz festlegen

Ruf den `architect`-Agenten (Agent-Tool, `subagent_type: architect`, im Vordergrund/`run_in_background: false`, da du das Ergebnis für die folgenden Schritte brauchst) mit dem aktuellen Entwurf von Ziel, User Story, Akzeptanzkriterien und Datenmodell-Bezug auf. Er legt den technischen Ansatz fest (betroffene Komponenten, Datenfluss, wiederverwendetes vs. neues Muster), legt bei Bedarf eine neue ADR in `specs/decisions/` an, und liefert den Inhalt für den Abschnitt `## Architektur / Umsetzung` der Spec. Übernimm diesen Abschnitt in die Spec — er beeinflusst die folgenden Schritte, da er festlegt, was überhaupt zu testen und sicherheitsrelevant zu prüfen ist.

## Schritt 7: UI/UX-Ansatz festlegen

Ruf den `ux-ui-designer`-Agenten (Agent-Tool, `subagent_type: ux-ui-designer`, im Vordergrund/`run_in_background: false`, da du das Ergebnis für die folgenden Schritte brauchst) mit dem aktuellen Entwurf von Ziel, User Story, Akzeptanzkriterien und dem Abschnitt "Architektur / Umsetzung" auf. Er entscheidet, ob das Feature eine sichtbare Oberfläche hat. Ist das nicht der Fall, trägst du im `## UI/UX`-Abschnitt der Spec kurz "nicht relevant" ein. Andernfalls übernimmst du seinen Ansatz (Ablauf/Layout, betroffene Zustände, Bezug zum Design-System `specs/architecture/0004-design-system.md`) in den Abschnitt.

## Schritt 8: Teststrategie und Security-Aspekt klären

`test-engineer` und `security-engineer` hängen an dieser Stelle nicht voneinander ab — beide brauchen nur die Abschnitte "Architektur / Umsetzung" und "UI/UX", nicht das Ergebnis des jeweils anderen. Ruf deshalb beide parallel auf (Agent-Tool, beide Aufrufe in derselben Nachricht, beide im Vordergrund/`run_in_background: false`, da du beide Ergebnisse für Schritt 9 brauchst):

- **`test-engineer`** (`subagent_type: test-engineer`) mit dem aktuellen Entwurf von Ziel, User Story, Akzeptanzkriterien und den Abschnitten "Architektur / Umsetzung" und "UI/UX": schärft die Akzeptanzkriterien auf Testbarkeit (verfeinert dabei die von `requirements-engineer` in Schritt 2 gelieferte erste Fassung, statt bei roher Ideenbeschreibung neu anzufangen), legt fest, was auf welcher Ebene (Unit/Integration/E2E) getestet werden soll, nennt relevante Edge Cases, und sagt, ob das Testkonzept (`specs/architecture/0002-testkonzept.md`) ergänzt werden muss.
- **`security-engineer`** (`subagent_type: security-engineer`) mit demselben Entwurf plus Datenmodell-Bezug: entscheidet, ob das Feature sicherheitsrelevant ist (z.B. Auth-Logik, externe Schnittstellen, Secrets, neue Eingaben von außen, Berechtigungsänderungen), und liefert bei Relevanz Bedrohungen/Gegenmaßnahmen für den `## Security`-Abschnitt.

Übernimm die geschärften Akzeptanzkriterien und eine kurze "Teststrategie"-Notiz (analog zum Abschnitt "Entscheidungen") von `test-engineer`. Trag im `## Security`-Abschnitt entweder die Einschätzung von `security-engineer` ein oder, falls nicht sicherheitsrelevant, kurz "nicht relevant".

## Schritt 9: Feature-Spec anlegen

Wenn die Idee Schritt 1–5 überstanden hat, entscheide zuerst, ob es um eine **neue** Spec-Datei geht oder um die **Erweiterung einer bestehenden**:

- **Betrifft eine bestehende Spec, die noch `Proposed` ist** (noch nicht freigegeben, noch nicht umgesetzt): diese Datei direkt erweitern statt eine neue anzulegen — Ziel/User Story/Akzeptanzkriterien ergänzen, Status auf `Accepted` setzen (falls noch nicht), "Bezug" um einen Hinweis auf das Idea-Sharpening-Gespräch ergänzen. Es handelt sich um dieselbe, noch offene Idee, nur präziser gefasst — eine zweite Datei zum selben Thema würde nur verwirren.
- **Betrifft eine bestehende Spec, die schon `Accepted` oder `Implemented` ist**, und macht sie teilweise oder ganz obsolet: neue Datei mit der nächsten freien Nummer in `specs/features/` nach `specs/TEMPLATE.md` anlegen. Sprich explizit an, dass die alte Spec dadurch überholt wäre, und frag den Nutzer, ob sie auf `Superseded` gesetzt und auf die neue verwiesen werden soll — das nicht stillschweigend selbst entscheiden, auch wenn es aus der Analyse naheliegend erscheint.
- **Keine bestehende Spec zum Thema:** neue Datei mit der nächsten freien Nummer anlegen.

Bei einer neuen Datei: **Status: Accepted** setzen — das Schärfen-Gespräch mit dem Nutzer *ist* die Stakeholder-Freigabe, ein separater Freigabeschritt danach wäre doppelte Arbeit (siehe Umgang mit Spec 0001 in diesem Projekt).

In jedem Fall: Ziel, User Story und Akzeptanzkriterien aus dem Gespräch ableiten oder ergänzen. Halte einen Abschnitt "Entscheidungen" mit den im Gespräch geklärten Punkten aktuell (analog zu bestehenden Specs), damit spätere Leser nachvollziehen können, warum etwas so und nicht anders entschieden wurde.

Falls die Idee die Architektur oder das Datenmodell spürbar verändert: `specs/architecture/0001-overview.md` entsprechend ergänzen.

Trag außerdem den in Schritt 2 vom `requirements-engineer` angelegten Eintrag in `specs/roadmap.md` mit dem jetzt feststehenden Spec-Pfad/-Nummer nach — der frühere Eintrag zeigte noch auf keine konkrete Datei, da die Spec erst jetzt angelegt wird. Kein erneuter Agenten-Aufruf nötig, reine Pfad-Ergänzung.

Fasse am Ende kurz zusammen, was angelegt/geändert wurde, mit Datei-Pfaden.
