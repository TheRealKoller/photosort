# 0093 - Der Entwurf hängt an der Story, die Ausarbeitung am `Ready`-Gate

**Status:** Accepted
**Datum:** 2026-09-13
**Bezug:** [GitHub-Issue #452](https://github.com/TheRealKoller/photosort/issues/452), Spec [`0452`](../features/0452-story-traegt-entwurf.md)

**Umfang:** über dem Richtwert von rund 100 Zeilen. Grund: Der Abschnitt `## Design` ist der erste
strukturierte Kanal aus einem öffentlichen Issue-Body in eine Spec-Datei, und seine Feldform ist
eine Zusicherung, die an keiner zweiten Stelle steht.

## Kontext

Entwürfe und Stories entstehen heute getrennt. `penpot-entwurfsrunden` kennt keine Story und hat
die Erlaubnisstufe „kein GitHub-Zugriff"; `refinement` kennt keinen Entwurf. Wer eine Idee mit
Oberflächenbezug schärft, entscheidet über Aufteilung, Dichte und Rangfolge blind.

Die zweite Lücke liegt hinter der ersten: Selbst ein vorhandener Entwurf erreicht die Umsetzung
nicht. `developer` liest die technische Spec, nicht das Issue — ein Verweis, der nur am Issue
hängt, kommt beim Bauen nie an.

Ein Entwurf hat außerdem zwei sehr verschiedene Zustände. Der Rundenstand liegt auf einer
Arbeitsseite in der Design-Datei und existiert im Repository überhaupt nicht; die ausgearbeitete
Ansicht steht in `design/penpot/views.json` und ist damit auflösbar. Ausgearbeitet wird nur, was
sich lohnt — und ob es sich lohnt, sagt der Board-Status.

## Entscheidung

### 1. Der Verweis ist ein Abschnitt `## Design` im Issue-Body, mit drei Feldern

Eine geschärfte Story trägt als **letzten** Abschnitt ihres Bodys genau einen `## Design`-Abschnitt
mit genau den drei Feldern `Stand`, `Penpot-Seite`, `Schlüssel` in dieser Reihenfolge. `Stand` ist
genau einer aus `Arbeitsstand` / `ausgearbeitet` — geschlossener Vorrat, kein dritter Wert. Bei
`ausgearbeitet` stammen beide Werte aus dem Eintrag in `design/penpot/views.json`; bei
`Arbeitsstand` ist `Schlüssel` der `entwurfslauf` des Rundenlaufs und `Penpot-Seite` dessen
Arbeitsseite.

**Ein viertes Feld für Notizen, Begründungen oder Rundenkommentare ist untersagt.** Es machte aus
dem geschlossenen Kanal einen Freitextpfad vom öffentlichen Issue in eine Spec-Datei, die
`developer` als Bauanleitung liest, und wäre ein eigener ADR-Anlass.

Gibt es keinen Entwurf, entfällt der Abschnitt ersatzlos: kein leerer Abschnitt, kein Platzhalter.
Ein abgebrochener Entwurfslauf schreibt gar nicht; ein bereits vorhandener Abschnitt bleibt dann
unverändert stehen. Sobald eine ausgearbeitete Ansicht existiert, wird derselbe Abschnitt
**ersetzt** — es entstehen unter keinen Umständen zwei.

**Ein vorhandener, nicht am Ende stehender Abschnitt hält den Lauf an**, statt umsortiert zu
werden. Umsortieren wäre die einzige Operation, die den Body strukturell umschreibt, und sie fiele
niemandem auf.

### 2. Die Form steht genau einmal, in `story-entwurf`

Feldnamen und Vorrat stehen vollständig in `.claude/skills/story-entwurf/SKILL.md` und werden im
lebenden Anweisungsraum `.claude/**` nirgends zweitgeschrieben; `refinement`, `spec-writer` und
`ux-ui-designer` verweisen darauf. Zwei wörtliche Abbilder desselben Formats sind der Drift-Fall,
gegen den die Ein-Definitions-Regel dieses Repositoriums geschrieben ist.

### 3. Weg B wird ein eigener Skill, nicht ein Modus in `refinement`

Weg A (design-unterstützte Schärfung einer rohen Idee) verlangt Entwurfsrunden *mitten* im
Schärfungsgespräch — nach der Code-/Spec-Recherche und vor dem Lohnenswert-Gate, damit das Gate
über die Idee urteilt, die die Entwürfe gezeigt haben. Er gehört deshalb in `refinement`.

Weg B (Entwurf zu einer bereits geschärften Story) hat eine invertierte Vorbedingung (`Ready`
statt ungeschärft), darf das Lohnenswert-Gate gerade nicht erneut auslösen und schreibt den Body
fort, statt ihn zu verfassen. Als Modus in `refinement` bedingte er dessen fail-closed-Reihenfolge
an drei Stellen. Beide teilen sich einen **gemeinsamen Nachlauf**, der genau einmal existiert (in
`story-entwurf`).

### 4. Die Ausarbeitung hängt am `Ready`-Gate, fail-closed

Die Auslieferungsfreigabe stammt aus `board-status-und-prioritaet-lesen`, ausgewertet am Knoten
`project.number == 8`. **Jeder Wert außer `Ready` und jeder Fehlschlag des Lesens selbst bedeuten
„keine Freigabe"** — dann nur Arbeitsstand, keine Ausarbeitung, kein Pull Request. In einer
Cloud-Session ist diese Operation auf keinem Weg erreichbar; Weg B liefert dort nie aus. Das ist
beabsichtigt.

Die Freigabe wird **unmittelbar vor der Übergabe an `ship-entwurf` erneut gelesen**. Zwischen der
ersten Lesung und dem Pull Request liegt ein Ausarbeitungslauf; ein Lauf ist kein Moment. Weicht
der Wert ab oder scheitert die Lesung, wird nicht ausgeliefert.

### 5. Die Freigabe *erreicht* den Rundenablauf, statt von ihm *ermittelt* zu werden

`penpot-entwurfsrunden` und `penpot-design` behalten die Erlaubnisstufe „kein GitHub-Zugriff".
Der Rundenablauf bekommt dafür eine geschlossene Quellenliste: **(a)** Direktaufruf ohne Story —
Daniel erklärt den Entwurf für fertig; **(b)** Aufruf aus einem Story-Ablauf — der aufrufende
Ablauf nennt die Freigabe, nachdem er sie am Board festgestellt hat; **(c)** sonst keine. Dazu
eine ebenso geschlossene Negativliste: nie aus Penpot-Inhalt, nie aus einem Issue-Body, nie aus
einem Titel. Ohne Freigabe laufen Abschluss und Übergabe nicht: keine Ansichtsseite, kein
`views.json`-Eintrag, kein Übergabeblock.

### 6. Storygebundene Entwürfe führen ausschließlich den Umfang `ansicht`

`ausschnitt` und `baustein` bleiben dem storyfreien Direktaufruf vorbehalten. Für sie existiert
keine ausgearbeitete, ausgelieferte Ablageform; ihr Verweis wäre nach dem Merge nicht auflösbar
und zeigte ins Leere, sobald die Arbeitsseite weggeworfen wird. Damit gelten die Zusagen „wird
vollständig ausgearbeitet und ausgeliefert" und „der Verweis erreicht die Umsetzung" ausnahmslos,
statt eine zweite, schwächere Klasse von Verweisen zu erzeugen.

### 7. Anheften vor Ausliefern, und ein fehlgeschlagenes Anheften verhindert die Auslieferung

Der Schreibzugriff auf den Issue-Body steht **vor** der Übergabe an `ship-entwurf`: Scheitert die
Auslieferung, ist der Entwurf trotzdem dauerhaft an der Story. Umgekehrt verhindert ein
fehlgeschlagenes `issue-body-schreiben` die Auslieferung — der Pull Request ist die einzige nicht
zurücknehmbare Handlung des Laufs, und ein ausgelieferter Entwurf ohne angehefteten Verweis ist
genau die Lücke, die diese Entscheidung schließt.

**Die Nachbesserung aus Weg B ist ein eigener, vorgezogener Schreibvorgang.** Erst der fachliche
Body, dann das Anheften — zwei getrennte Schreibzugriffe. Die Byte-Zusage aus Abschnitt 8 gilt
ausschließlich für den Anheft-Vorgang; andernfalls widerspräche sie der zugesagten Nachbesserung.

### 8. Der Body wird fortgeschrieben, nicht neu erzeugt — als Anweisungstext

Der neue Body entsteht mechanisch als `<gelesener Inhalt bis zur ersten Zeile ## Design> +
<selbst erzeugter Block>`. Alles davor bleibt Byte für Byte unverändert: kein Umformatieren, kein
Neuumbrechen, kein Neuformulieren aus dem Kontextverständnis heraus. Ein neu getippter Body ist
neuer Inhalt, der nur aussieht wie der alte.

**Es entsteht keine Funktion unter `scripts/`, die den Body fortschreibt.** Der Ablauf ist
durchgehend Text, und zwei Orte derselben Regel driften. Getragen wird die Zusage stattdessen von
einer verbindlichen mechanischen Selbstprüfung vor jedem Schreibzugriff: Der gelesene und der
erzeugte Body werden in je eine Datei geschrieben und verglichen; einziger zulässiger Unterschied
ist der Bereich ab der `## Design`-Überschrift, jede weitere Abweichung hält an.

### 9. Der Entwurfs-Pull-Request trägt nie ein Closing-Keyword auf die Story

Ein `Closes #NNN` zöge die Karte auf `Review` und schlösse das Issue beim Merge — die Story soll
`Ready` bleiben. Der Übergabeblock an `ship-entwurf` trägt deshalb `**Story:** keine` (dieses Feld
steuert ausschließlich die `Closes`-Zeile) plus eine neue, ausdrücklich **nicht steuernde** Zeile
`**Herkunft:** Story #NNN` als Berichtsmaterial. Sie steht ausschließlich im Pull-Request-Body,
**nie in einer Commit-Nachricht**: Das Repository squasht mit `COMMIT_MESSAGES`, jeder Commit-Body
wandert in den Merge-Commit auf `main`.

### 10. `Schlüssel` ist der einzige steuernde Wert und löst über Mengenzugehörigkeit auf

Geprüft wird `^[a-z0-9][a-z0-9-]{2,39}$` **an der Verwendungsstelle** in `ux-ui-designer`, nicht
nur dort, wo der Wert geschrieben wurde — der Block überquert als Text eine Zuständigkeitsgrenze.
Aufgelöst wird als Mitgliedschaft in den Schlüsseln von `design/penpot/views.json`, nie über eine
zusammengesetzte Pfadangabe und nie über einen Rohindex auf das geparste Objekt; das Muster
schließt `__proto__` und `constructor` strukturell aus. Kein Treffer ist ein Befund, nie ein
Rückfall auf den ersten Eintrag und nie ein Anlegen. `Penpot-Seite` steuert nichts.

## Begründung

Der Kanal ist schmal allein durch seine geschlossene Feldstruktur — nicht dadurch, dass der Body
vertrauenswürdig wäre. Das Repository ist öffentlich; ein fremd erstelltes Issue ist
fremdbeschreibbar, und der Block wandert von dort in eine Datei, die ein Umsetzungslauf als
Bauanleitung liest. Drei Felder mit geschlossenem Vorrat, geschlossenem Muster und reiner
Anzeigefunktion sind die einzige Form, für die sich das mechanisch prüfen lässt.

Die Kopplung der Ausarbeitung an `Ready` löst zugleich ein Aufwandsproblem: Die Ausarbeitung ist
die teure Hälfte eines Rundenlaufs (beide Prüfbreiten, alle Zustände, `views.json`-Eintrag,
Kardinalitäten). Sie an das Gate zu hängen, das ohnehin über die Lohnenswertigkeit entschieden
hat, spart sie für verworfene Ideen vollständig ein — und ein verworfener Weg-A-Lauf hat dann
nichts ausgeliefert, das zurückzunehmen wäre.

## Konsequenzen

- Ein neuer Skill `story-entwurf` mit der Erlaubnisstufe „lesend und schreibend" und **genau drei**
  Operationen: `board-status-und-prioritaet-lesen`, `issue-lesen`, `issue-body-schreiben`. Kein
  `issue-titel-schreiben`, keine `board-*-setzen`, keine `pr-*`-Operation. Die Stufe bleibt eine
  Obergrenze, keine Gebrauchserlaubnis.
- Es entsteht **keine** neue Katalog-Operation und **kein** Issue-Kommentar als Träger des
  Verweises: Keine Katalog-Operation liest Kommentare, der Verweis erreichte `spec-writer` nie.
- Ein `views.json`-Eintrag erreicht `main` über `ship-entwurf`, also ohne Perspektivenrunde und
  ohne Copilot-Review. „Im Repository auflösbar" heißt deshalb nicht „von einem Prüfer gesehen" —
  bewusst getragenes Restrisiko, im Sicherheitskonzept geführt.
- Die Zeichenprüfung sagt nichts darüber, ob der aufgelöste Eintrag der richtige für diese Story
  ist. Ein falscher, aber wohlgeformter Schlüssel führt zu einem falschen Entwurf, nicht zu einem
  Zugriff außerhalb der Menge.
- Kein Test dieses Repositoriums bekommt je ein Exemplar des `## Design`-Blocks zu sehen — die
  einzige Instanz des Formats liegt im Issue-Body und damit außerhalb. Prüfbar ist allein die
  Erzeugungs- und Leseanweisung an ihren vier Orten.
