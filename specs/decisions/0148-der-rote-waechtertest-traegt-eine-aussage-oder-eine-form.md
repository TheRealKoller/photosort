# 0148 - Der rote Wächtertest trägt eine Aussage oder eine Form — nie beides

**Status:** Accepted
**Datum:** 2026-11-16
**Bezug:** Issue [#652](https://github.com/TheRealKoller/photosort/issues/652), Story „Prüfungen
prüfen die Wirkung statt den Wortlaut"
**Umfang:** rund 120 statt 100 Zeilen. Abschnitt 1 trägt die beiden Grenzen wörtlich; sie gehen in
keiner Zusammenfassung auf.

## Kontext

Der Umsetzungsablauf hat aus einem richtigen Satz eine falsche Regel gemacht. Richtig ist: Ein roter
Lauf unter `scripts/tests` sagt zuerst etwas über den Arbeitsstand, nicht über einen zu
reparierenden Test. Falsch ist die Verallgemeinerung in `.claude/agents/developer.md`, Abschnitt
„Folgeauftrag: CI-Fehlschlag beheben", Punkt 3: Ein roter Wächtertest sei **nie** ein zu
reparierender Test. Denn ein großer Teil dieser Prüfungen hält keine Zusicherung fest, sondern eine
Schreibweise — Ablageort, Reihenfolge, Abschnittstitel, Satzstellung, das Wort „monoton" in einem
Docstring.

Gemessen am Bestand (16.11.2026): 1129 Testfunktionen unter `scripts/tests`, davon rund 150 schon im
Namen Negativtests eines Wächters gegen sich selbst („… wird gemeldet", „… gilt nicht als Verstoß");
in `test_backend_ci_beschleunigung.py` stehen rund 20 von 26, im Katalogwächter rund die Hälfte. Die
Folge ist keine Geschmacksfrage: Rot entsteht bei einer gleichwertigen Umformulierung genauso wie
bei einer echten Verletzung. Wer beides nicht unterscheiden kann, behandelt beides gleich — die
Verletzung wird nachgezogen, oder die Umformulierung wird verboten. Beides ist eingetreten.

## Entscheidung

### 1. Die beiden Grenzen

**Eine tragende Zusicherung wird nie durch Abschwächen ihrer Prüfung grün gemacht.** Steht eine
Prüfung im Weg, wird zuerst entschieden, ob sie eine Aussage über das Verhalten trägt. Trägt sie
eine, wird die **Aussage** geändert — als bewusste Entscheidung mit eigener Spur —, nicht die
Prüfung. Eine Prüfung zu lockern, damit die Änderung durchgeht, ist derselbe Fehler wie ein
abgeschwächter Test in einem TDD-Zyklus.

**Unterschieden wird zwischen einer Prüfung, die eine Aussage trägt, und einer, die nur eine Form
festhält.** Nur die Form darf fallen, und nur mit benannter Aussage: entweder sie wird auf ihre
Aussage gehoben (Abschnitt 2), oder es wird festgestellt, dass sie keine trug — samt Grund, im
selben Pull Request, gegen den Diff abgleichbar. Stiller Schwund ist ausgeschlossen.

### 2. Drei Prüfklassen, entschieden am Konsumenten

**Aussage (A)** — beobachtbare Wirkung: eine Funktion liefert für eine Eingabe ein anderes Ergebnis,
ein Skript setzt andere Befehle ab, ein Lauf endet in einem anderen Zustand. Prüfbar, ohne den
Quelltext zu lesen. Bleibt unverändert.

**Protokoll (B)** — ein Token, den eine andere Stelle maschinell liest: der Anker
`## Blockiert: Produktentscheidung nötig`, eine Operations-ID, die Zeile `**Wege:**`, das
Frontmatter-Feld `tools:`, ein Feld in `scripts/tests/werkzeugzuteilung.json`, ein Marker wie
``**Kein `mcp`-Weg:**``. Bleibt, weil ein Konsument existiert, der ihn liest.

**Form (C)** — alles, was nur ein Mensch liest: Ablageort, Reihenfolge, Abschnittstitel, Satzbau,
Zeilenumbruch, Mindestlänge einer Begründung, ein Wort in einem Docstring. Fällt oder wird auf
A oder B gehoben.

**Die Frage, die entscheidet, ist eine einzige: Wer liest das außer einem Menschen?** Niemand →
Form. Sie ist am Text beantwortbar und braucht kein Urteil über Wichtigkeit.

### 3. Wo die Wirkung nicht beobachtbar ist, wird deklariert statt bewacht

Ob ein Lauf eine Anweisung befolgt, ist statisch nicht beobachtbar. Deshalb wird eine Anweisung mit
prüfbarer Eigenschaft zu einem **deklarierten Feld**, das der Ablauf ohnehin liest — nicht zu einer
bewachten Satzformel. Die Deklaration ist normativ; die Prosa daneben ist frei und ungeprüft. Gibt
es weder Konsumenten noch beobachtbare Invariante, **fällt die Prüfung**, und die Bilanz sagt, dass
sie keine Verhaltensaussage trug. Eine Wortlautsuche als Ersatz ist untersagt: Sie prüft die
Formulierung und nennt die Verletzung nicht.

### 4. Rot heißt zweierlei, und das wird jetzt gesagt

Ein roter Lauf einer Prüfung aus Klasse **A** oder **B** ist ein Befund über den Arbeitsstand: Die
überwachte Stelle verletzt eine Aussage, oder ein Protokoll ist gebrochen. Er wird weder durch
Umformulieren der überwachten Stelle noch durch Anpassen der Erwartung grün.

Ein roter Lauf einer Prüfung aus Klasse **C** ist ein **Nachzug**: Die Prüfung wird entfernt oder
auf A/B gehoben, im selben Pull Request wie die Änderung, die sie rot gemacht hat, mit einer Zeile
in der Bilanz.

Der Unterschied ist nicht der Grad der Aufmerksamkeit, sondern die Frage aus Abschnitt 2.

### 5. Fehlererkennung wird einmal geprüft, nicht je Wächter

Jeder Wächter wird zu **einer reinen Funktion** `Bestand → Befunde`; ein Befund nennt Ort
(`datei:zeile`) und die verletzte Invariante. Die Invarianten eines Wächters stehen als geschlossene
Menge mit je einem Satz. Die Fehlererkennung selbst prüft **eine** Mutationsliste an einer Stelle:
je Invariante eine Mutation des Bestands, die rot werden muss, und ein unmutierter Bestand, der grün
ist. Ein Wächter ohne Mutation für eine seiner Invarianten fällt auf. Damit entfallen die
Negativtests je Muster („… wird gemeldet", „… gilt nicht als Verstoß"); sie werden nicht durch
andere Negativtests ersetzt.

## Begründung

- **Warum nicht alle Wortlautprüfungen löschen:** Ein Teil trägt echte Zusicherungen, nur über einen
  Text: dass genau eine Stelle einen GitHub-Zugriff definiert, dass die Operationsmenge geschlossen
  ist, dass kein Prüfschritt überspringbar ist. Diese Aussagen sind von der Schreibweise unabhängig
  formulierbar — und genau das ist der Auftrag, nicht ihr Wegfall.
- **Warum die Klasse am Konsumenten hängt und nicht an der Wichtigkeit:** „Wichtig" ist nicht am
  Text entscheidbar, „wird von einer anderen Stelle gelesen" schon. Ein Token ohne Leser ist eine
  Form, die sich als Protokoll verkleidet — der häufigste Fall im Bestand.
- **Warum eine Mutationsliste statt Negativtests:** Ein Negativtest belegt, dass ein Muster eine
  Zeichenkette findet; er belegt nicht, dass der Wächter eine Verletzung bemerkt. Die Mutation
  belegt das am Bestand, an einer Stelle, und macht den Wächter beim nächsten Umbau mit einem
  Eintrag nachziehbar. Rund 150 benannte Negativtests sind 150 Stellen, an denen eine Umformulierung
  nachgezogen werden muss.
- **Warum die Bilanz Pflicht ist:** Eine gelockerte Prüfung ohne benannte Aussage ist von einer
  vergessenen nicht unterscheidbar. Die Bilanz ist der einzige Ort, an dem beides auseinanderfällt.

## Konsequenzen

- `.claude/agents/developer.md`, Abschnitt „Folgeauftrag: CI-Fehlschlag beheben", Punkt 3: Der Satz
  „ein roter Wächtertest ist eine Aussage über den Arbeitsstand, nie ein zu reparierender Test" wird
  durch Abschnitt 4 ersetzt.
- `specs/architecture/0002-testkonzept.md` nennt künftig die drei Klassen und die Mutationspflicht;
  die Sektionen, die je Wächter eine eigene Negativprobe vorschreiben, werden nachgezogen.
- `scripts/tests`: Die betroffenen Wächter bekommen je eine reine Funktion und eine
  Invariantenmenge; die Mutationsliste ist **eine** Datei, kein Muster je Testmodul.
- Unverändert bleiben alle Prüfungen mit eigener Logik (Nummernvergabe, Abgleich mit `main`,
  Produktentscheidungs-Anker, PR-Titel, Verweis- und Nummerneindeutigkeit) und alle
  Verhaltensprüfungen der Skripte unter `scripts/`.
- **Preis, benannt:** Ein Protokoll-Token bleibt eine feste Zeichenkette; wer den Anker umbenennt,
  muss beide Seiten umbenennen. Das ist gewollt — der Anker ist die Schnittstelle, nicht die
  Beschreibung. Eine Mutation, die eine Invariante nicht rot macht, kostet künftig einen Eintrag
  in der Liste, nicht eine neue Testfunktion.
