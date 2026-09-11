# 0077 - Dateiarbeit läuft über die dedizierten Werkzeuge; die Shell ist die begründete Ausnahme

**Status:** Accepted — vollständig. Der eine Punkt, der über eine technische Detailfrage hinausging (die Verankerungstiefe, Abschnitt 7), ist Daniel vor der Umsetzung vorgelegt und von ihm am 2026-09-11 zugunsten der hier beschriebenen Fassung entschieden worden: nur Text, kein Hook.
**Datum:** 2026-09-11
**Bezug:** [GitHub-Issue #395](https://github.com/TheRealKoller/photosort/issues/395), [`features/0395-dateiarbeit-dedizierte-werkzeuge.md`](../features/0395-dateiarbeit-dedizierte-werkzeuge.md), `CLAUDE.md`, `.claude/skills/github-access/SKILL.md` (Härtungsregel 4.1), `scripts/tests/`

**Ergänzt, ohne abzulösen:** ADR [`0061`](./0061-ein-ort-fuer-jeden-github-zugriff-wege-in-fester-reihenfolge.md), Härtungsregel 4.1 („Freitext ist immer ein abgegrenzter Wert, nie Teil der Aufrufstruktur"). Diese ADR verallgemeinert deren Einsicht auf die alltägliche Dateiarbeit — sie schwächt sie an keiner Stelle ab (Abschnitt 6).

## Kontext

Die Werkzeugwahl während der Entwicklung folgt heute dem, was gerade am reibungsärmsten ist, statt einer Festlegung. Der `/insights`-Report vom 2026-09-10 zählt **6.394 Shell-Aufrufe** gegen **277 lesende, 336 ändernde und 338 schreibende** Aufrufe der dedizierten Werkzeuge. Dateien werden also weit überwiegend per `sed`, `grep`, Heredoc und Umleitung gelesen und geändert.

Zwei naheliegende Begründungen dieses Zustands tragen **nicht**, und das ist für den Zuschnitt entscheidend:

**Der Kontextverbrauch ist kein Argument für die Umkehr.** Ein gezielter Ausschnitt über `sed -n '120,180p'` ist sparsamer als das vollständige Einlesen, das eine gezielte Änderung voraussetzt. Wer die Konvention mit Sparsamkeit begründete, begründete sie falsch — und verlöre die Begründung beim ersten Nachrechnen.

**Die Reibung ist real, aber teilweise hausgemacht.** In Hintergrund-Läufen lehnt die Arbeitsumgebung Änderungen am geteilten Arbeitsstand ab, solange kein isolierter Arbeitsstand (Worktree) betreten wurde; die Shell ist von dieser Sperre nicht betroffen. Eine Änderung per `sed` läuft dort also durch, während das Änderungs-Werkzeug abgewiesen wird. Das erklärt einen Teil der Zahlen oben — es rechtfertigt sie nicht, denn die Sperre hat einen vorgesehenen Ausgang, und der ist das Herstellen des isolierten Arbeitsstands, nicht das Ausweichen.

**Was tatsächlich trägt, ist die Fehlerklasse.** Eine gezielte Änderung über das Änderungs-Werkzeug scheitert **laut**, wenn die zu ersetzende Stelle nicht eindeutig ist: Sie verlangt Eindeutigkeit und meldet deren Fehlen. Eine Ersetzung über die Shell greift in derselben Lage **still** daneben — sie trifft die erste Fundstelle, oder alle, oder keine, und meldet in allen drei Fällen Erfolg. Dazu kommen die Quoting-Fallen beim Schreiben: Ein Heredoc mit nicht maskiertem Inhalt expandiert `$…` und Backticks, ein `sed`-Ausdruck mit ungeschütztem `&` oder `/` schreibt etwas anderes als gemeint.

Das Projekt hat diese Lektion an einer Stelle bereits bezahlt und dort die härtere Antwort gegeben: Härtungsregel 4.1 verlangt seit ADR 0061, dass Freitext für GitHub-Artefakte „mit dem Schreib-Werkzeug angelegt" wird, „nie per Shell-Umleitung mit interpoliertem Inhalt". Diese Einsicht steht bis heute **punktuell und sicherheitsbegründet** da — als Regel über einen Sonderfall, nicht als Arbeitsweise. Die Fehlerklasse ist aber dieselbe; nur der Schaden ist außerhalb des GitHub-Falls kleiner und dafür häufiger.

**Betroffen ist ausschließlich die Arbeitsweise der Entwicklung.** Für die Nutzer der Anwendung ändert sich nichts, am Produktcode ändert sich nichts, und die Systemarchitektur (`docs/architecture.md`) bleibt unberührt.

## Entscheidung

### 1. Genau ein Ort: ein eigener Abschnitt in `CLAUDE.md`

Die Konvention steht als eigener Abschnitt `## Werkzeugwahl bei Dateiarbeit` in `CLAUDE.md`, zwischen `## Konventionen` und `## Doku-Pflege`. **Keine andere Datei formuliert die Regel noch einmal.**

Drei Gründe, warum es dieser Ort ist und kein anderer:

**Kein Skill.** Ein Skill wird geladen, wenn sein Auslöser zutrifft. Eine Konvention, die bei *jeder* Dateiänderung gilt, hat keinen Auslöser — sie müsste immer geladen sein, und ein immer geladener Skill ist `CLAUDE.md` mit Zusatzschritt. Schlimmer: Ein Skill, der in der Hälfte der Läufe nicht geladen wird, erzeugt eine Regel, die in der Hälfte der Läufe nicht gilt, ohne dass irgendwo auffiele, welche Hälfte gerade läuft.

**Kein Bullet in `## Konventionen`.** Die Regel braucht ihre Begründung, ihre benannten Ausnahmen und ihre Vorrangklausel — ohne die Begründung wird die Abweichung beiläufig statt begründet (das ist ein Akzeptanzkriterium, kein Schmuck). Das sind rund zehn Zeilen; als Aufzählungspunkt in einer Liste heterogener Einzeiler ginge die Struktur unter. Eine eigene Überschrift ist außerdem der stabile Anker, an dem die statische Prüfung (Abschnitt 8) überhaupt festmachen kann.

**Keine Wiederholung in den Agenten-/Skill-Dateien.** Das ist die bewusste Abweichung vom `github-access`-Muster, und sie ist zu begründen, weil das Muster hier naheliegt: Dort trägt jede Datei eine eigene `**GitHub-Erlaubnisstufe:**`-Zeile, weil sich die Stufe **je Datei unterscheidet** — die Zeile transportiert Information. Die Werkzeugwahl ist dagegen für alle 24 Dateien identisch. 24 gleichlautende Zeilen transportieren keine Information, sie sind Rauschen, und `CLAUDE.md` untersagt ausdrücklich Verweise in Skills/Agents, die nicht funktional nötig sind.

**Was in andere Dateien gehört, ist nicht die Regel, sondern die Ablauf-Logik** — dieselbe Trennung wie bei `github-access`. Konkret betrifft das genau eine Stelle: Der `developer`-Agent bekommt in seine Schrittfolge den Schritt, vor der ersten Repo-Änderung den isolierten Arbeitsstand herzustellen (Abschnitt 5). Das ist ein Ablaufschritt mit einem Zeitpunkt, keine Wiederholung der Begründung.

### 2. Die Vorgabe, und der Grund, warum sie so herum liegt

**Lesen, Ändern und Schreiben von Dateien laufen im Regelfall über die dedizierten Werkzeuge.** Das Lese-Werkzeug zum Lesen, das Änderungs-Werkzeug zum Ändern, das Schreib-Werkzeug zum Anlegen und vollständigen Ersetzen; für das Suchen die dafür vorgesehenen Such-Werkzeuge.

Der Grund steht **in** der Konvention, nicht nur hier in der ADR, und er ist genau einer:

> Eine gezielte Änderung über das Änderungs-Werkzeug scheitert **laut**, wenn die zu ersetzende Stelle nicht eindeutig ist. Eine Ersetzung über die Shell greift in derselben Lage **still** daneben oder gar nicht. Dazu kommt, dass das Schreib-Werkzeug keine Quoting-Fallen kennt — kein Heredoc, das `$…` und Backticks expandiert, kein `sed`-Ausdruck, den ein `&` oder ein `/` im Ersatztext umdeutet.

Warum die Begründung mitgeschrieben wird, statt nur die Regel: Die Konvention ist ein **Default**, und ein Default ohne Begründung ist nicht abweichungsfähig. Wer weiß, wogegen die Regel schützt, kann prüfen, ob der Schutz im vorliegenden Fall greift, und sauber abweichen. Wer die Regel nur als Setzung kennt, hat genau zwei Umgangsformen — sklavisch befolgen oder beiläufig ignorieren —, und beide sind schlechter.

### 3. Ein Default, kein Verbot: die Fälle, in denen die Shell die bessere Wahl ist, sind benannt

Die Konvention nennt die Gegenfälle **abschließend genug, um zitierbar zu sein, und offen genug, um nicht zu lügen**:

- **Versionsverwaltung, Paketmanager, Testläufe, Builds.** Dafür gibt es kein dediziertes Werkzeug; die Shell ist dort nicht die zweitbeste, sondern die einzige Wahl.
- **Gezieltes Lesen eines Ausschnitts einer großen Datei.** Hier ist die Shell dem vollständigen Einlesen sachlich überlegen, und zwar messbar. Dieser Punkt steht ausdrücklich drin, damit die Konvention nicht an ihrer eigenen Übertreibung scheitert.
- **Mehrere zusammengehörige Schritte, die sich in einem Aufruf bündeln lassen.**

**Ein Verbot wäre hier der falsche Zuschnitt**, und das ist eine Entscheidung, keine Milde: Ein Verbot mit drei Ausnahmen erzeugt Grenzfälle, die niemand entscheiden kann, und die erste unvermeidbare Übertretung entwertet die ganze Regel. Ein Default mit benannten Gegenfällen bleibt bei jedem Grenzfall anwendbar — man weicht ab und sagt warum.

### 4. Zusammengehörige Shell-Aufrufe werden gebündelt

Wo die Shell zum Einsatz kommt, werden zusammengehörige Aufrufe in **einem** Aufruf abgesetzt statt als Kette einzelner. Das ist kein Stilpunkt: Jeder einzelne Aufruf kostet eine volle Runde, und eine Kette aus fünf `grep`s, die zusammen eine Frage beantworten, kostet fünfmal so viel wie die Frage wert ist.

### 5. Die Konvention gilt auch gegen einen gegenteiligen Hinweis der Arbeitsumgebung

Die Konvention trägt eine ausdrückliche **Vorrangklausel**: Rät ein Hinweis der Arbeitsumgebung von sich aus zur Shell für Dateiarbeit, gilt trotzdem diese Konvention; eine Abweichung wird benannt, nicht stillschweigend vollzogen.

Das ist kein hypothetischer Fall — es ist der Fall, in dem diese Entscheidung entstanden ist. `CLAUDE.md` wird als Projektanweisung eingebunden, die ausdrücklich Vorrang vor Vorgabeverhalten hat; das ist die Stelle, an der sich ein solcher Widerspruch überhaupt auflösen lässt. **Der Preis wird nicht schöngeredet** (Abschnitt 7): Ein wiederholter, näher am Zug stehender Hinweis hat gegenüber einem einmaligen Satz am Anfang einen Stellungsvorteil, den kein Text im Repository wegschreiben kann.

**Die Vorrangklausel ist auch der Grund, warum die Konvention den Hinweis nennt, statt ihn zu ignorieren.** Eine Regel, die den ihr bekannten Widerspruch verschweigt, wird beim ersten Auftreten für veraltet gehalten.

### 6. Härtungsregel 4.1 bleibt hart — die weichere Konvention weicht sie nicht auf

Die Konvention trägt eine Abgrenzungszeile: Für Freitext, der in GitHub-Artefakte gelangt, gilt unverändert Härtungsregel 4.1 aus `github-access` — **immer über eine Datei, nie über die Kommandozeile**. Das ist ein Verbot, kein Default; es kennt die Gegenfälle aus Abschnitt 3 nicht und wird durch sie nicht relativiert.

Diese Zeile ist die wichtigste der ganzen Konvention, weil sie die einzige ist, deren Fehlen aktiv Schaden anrichtet. Ohne sie liest sich die neue Konvention wie eine Lockerung derselben Materie — „Shell ist in Ordnung, wo sie sachlich passt" —, und genau dieses Argument ist der Weg, auf dem eine Sicherheitsregel erodiert. Der Unterschied ist zu benennen, nicht vorauszusetzen: 4.1 schützt nicht vor einem Vertipper, sondern vor fremdem Text, der in eine Aufrufstruktur läuft. Die Konvention aus Abschnitt 2 schützt vor einem stillen Fehlgriff in eigenem Text. Gleiche Fehlerklasse, unvergleichbarer Schaden, deshalb unterschiedliche Härte.

### 7. Verankert wird als Text — kein eingechecktes `.claude/settings.json`, kein Hook

Die Konvention wird **nicht** mechanisch durchgesetzt. Es entsteht kein eingechecktes `.claude/settings.json` und kein `PreToolUse`-Hook, der Shell-Aufrufe auf Änderungsmuster (`sed -i`, `cat > …`, `tee`, `>>`) absucht.

Abgewogen wurde gegen genau diesen Hook, und er ist nicht an seiner Machbarkeit gescheitert — er wäre baubar, er würde greifen, und er wäre als Skript sogar echt testbar statt nur auf seine Verankerung prüfbar. Gescheitert ist er an drei Kosten:

- **Er wirkt nicht nur auf Agentenläufe, sondern auf jede Session in diesem Repository**, auch auf Daniels eigene. Ein eingecheckter Hook ist eine Verhaltensänderung der Arbeitsumgebung für alle, beschlossen in einer Story über eine Konvention.
- **Blockieren darf er nicht** — das wäre das Verbot aus Abschnitt 3, ausdrücklich ausgeschlossen. Bleibt der Hinweis, und ein Hinweis, der bei jedem legitimen `git`-Einzeiler mit `>>` mitfeuert, wird binnen weniger Tage überlesen. Ein überlesener Wächter ist schlechter als keiner: Er erzeugt das Gefühl von Absicherung ohne die Absicherung.
- **Er wäre das erste eingecheckte Konfigurations-Artefakt dieser Art** und damit eine neue, dauerhaft zu pflegende Fläche — Skript, Muster, Tests, Fehlalarm-Nachjustierung — für eine Regel, deren Verletzung keinen irreversiblen Schaden anrichtet.

**Der Preis dieser Entscheidung, unbeschönigt:** Die Konvention wirkt allein über Befolgung. Ob sie befolgt wird, steht nirgends im Repository — kein Artefakt zeichnet auf, welches Werkzeug eine Zeile geschrieben hat. Der einzige verfügbare Messpunkt ist derselbe, der diese Story ausgelöst hat: die Werkzeug-Zählung eines künftigen `/insights`-Reports, von Hand gelesen. Bleibt die Verteilung dort nach einigen Wochen unverändert, ist diese Entscheidung widerlegt, und der Hook ist die naheliegende Nachfolge — als neue ADR, nicht als Nachbesserung dieser.

**Von Daniel entschieden (2026-09-11):** Diese Abwägung geht über eine technische Detailfrage hinaus, weil sie Daniels eigene Sessions beträfe, und wurde ihm deshalb vor der Umsetzung vorgelegt. Er hat sich für die hier beschriebene Fassung entschieden — nur Text, kein Hook. Der Abschnitt gilt damit unverändert; die Nachfolge-Option bleibt die im vorigen Absatz benannte.

### 8. Abgesichert wird die Verankerung, ausdrücklich nicht die Befolgung

Ein Test unter `scripts/tests/` (CI-Job `demo-scripts`) hält zwei Zusicherungen, und beide sind eng gefasst:

1. **Der Abschnitt in `CLAUDE.md` existiert und trägt seine tragenden Aussagen.** Geprüft wird über **feste Markerzeilen** innerhalb des abgegrenzten Abschnitts (`**Vorgabe:**`, `**Grund:**`, `**Shell ist die bessere Wahl bei:**`, `**Bündelung:**`, `**Vorrang:**`, `**Hintergrund-Läufe:**`, `**Unberührt:**`), jede mit nicht-leerem Inhalt. Jeder Marker entspricht genau einem Akzeptanzkriterium; fällt einer bei einem künftigen Umbau weg, wird das Kriterium laut statt still ungültig.
2. **Härtungsregel 4.1 behält ihre absolute Form.** Der Text in `github-access` enthält weiterhin „mit dem Schreib-Werkzeug angelegt" und „nie per Shell-Umleitung mit interpoliertem Inhalt". Das ist der substanzielle Teil der Prüfung: Dass die härtere Regel bei einer späteren Überarbeitung mit dem Argument „die neue Konvention deckt das ab" weichgeschrieben wird, ist der realistischste Weg, auf dem dieses Feature Schaden anrichtet.

   **Gemessen, nicht angenommen (2026-09-11):** Die zweite Zeichenkette kommt im Bestand **null** mal vor, wenn man sie roh sucht — sie steht dort über einen Zeilenumbruch verteilt („… mit interpoliertem\\n  Inhalt."). Erst über whitespace-normalisiertem Text ergeben sich die erwarteten Trefferzahlen (2 / 1 / 1 für „mit dem Schreib-Werkzeug angelegt", „nie per Shell-Umleitung mit interpoliertem Inhalt", ``Bodies **immer** über `--body-file` ``). Die Prüfung normalisiert deshalb vor dem Suchen. Ohne diesen Schritt wäre der Wächter beim ersten Umbruch-Wechsel rot geworden, ohne dass sich an der Regel etwas geändert hätte — und beim Reparieren wäre der naheliegende Griff gewesen, die Zusicherung zu lockern statt sie zu normalisieren.

**Zwei Lehren aus ADR 0061 werden übernommen, nicht neu bezahlt.** Erstens: **Form statt Suche über einen Block.** Gesucht wird nach Zeilen an fester Stelle, nicht nach Formulierungen irgendwo im Abschnitt — ein Wächter, der eine Zeichenkette über einen Textblock sucht, kann „gilt" nicht von „galt einmal" unterscheiden, sobald der Text über seinen früheren Zustand reden darf. Zweitens: **Selbstschutz.** Der Test weist nach, dass er die Dateien tatsächlich gelesen hat (Existenz, plausible Mindestgröße) und dass die Abschnittsgrenze wirklich am nächsten `## ` endet — sonst zöge der Abschnitt den Rest der Datei in sich und bestünde jede Marker-Zusicherung zufällig.

**Was der Test ausdrücklich NICHT zusichert, und was deshalb auch nicht gebaut wird:** dass die Konvention befolgt wird. Eine Verhaltensregel ist kein Dateiinhalt. Es gibt im Repository keine Spur davon, welches Werkzeug eine Änderung erzeugt hat, und jede Konstruktion, die so täte — eine Heuristik über Commit-Muster, eine Zählung aus Sitzungsprotokollen — wäre ein Scheintest: grün, ohne etwas zu wissen, und damit schädlicher als gar kein Test, weil sie die offene Flanke aus Abschnitt 7 zudeckte.

## Konsequenzen

**Positiv**

- Die Werkzeugwahl ist eine bewusste Festlegung mit nachlesbarer Begründung statt eines eingeschliffenen Musters. Eine Abweichung ist ab jetzt eine Aussage, keine Gewohnheit.
- Die Fehlerklasse „still danebengegriffene Ersetzung" wird im Regelfall strukturell ausgeschlossen, statt durch Aufmerksamkeit abgefangen zu werden.
- Die punktuelle Einsicht aus Härtungsregel 4.1 steht nicht mehr allein und unverbunden da; ihre Sonderstellung ist zugleich ausdrücklich abgegrenzt und damit gegen Erosion gesichert.
- Der Ort ist einer, und er ist derjenige, der ohnehin bei jedem Lauf gilt. Es entsteht keine zweite Regelquelle, die driften könnte.

**Negativ, und benannt**

- Die Wirkung hängt allein an der Befolgung (Abschnitt 7). Gegen einen wiederholten, näher stehenden gegenteiligen Hinweis der Arbeitsumgebung hat ein Abschnitt in `CLAUDE.md` einen Stellungsnachteil, den diese Entscheidung nicht auflöst, sondern nur benennt.
- Der Test prüft die Verankerung, nicht die Wirkung. Eine grüne CI ist hier keine Aussage über die tatsächliche Werkzeugwahl — derselbe ehrliche Vorbehalt wie in `test_setup_docs.py`.
- `CLAUDE.md` wächst um einen Abschnitt. Das ist die Datei, die bei jedem Lauf vollständig gelesen wird; jede Zeile darin hat laufende Kosten. Die Länge ist deshalb auf das begrenzt, was die Akzeptanzkriterien verlangen — sieben Markerzeilen, kein Fließtext daneben, keine Wiederholung der Begründung aus dieser ADR.
