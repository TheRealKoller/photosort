# 0062 - Geteilte Farbhoheit: Figma führt die Board-Farben, `index.css` führt die ausgelieferte Palette

**Status:** Accepted
**Datum:** 2026-09-07
**Bezug:** GitHub-Issue [`#336`](https://github.com/TheRealKoller/photosort/issues/336), zugehörige Feature-Spec `specs/features/0336-*.md`, `architect`-Konsultation für Story #336 am 2026-09-07 (die Zahlen dieser ADR sind an diesem Tag aus `frontend/src/index.css` und [`architecture/0005-board-dark-utility-register.md`](../architecture/0005-board-dark-utility-register.md) nachgerechnet, nicht übernommen).

**Ergänzt, ohne abzulösen:**

- ADR [`0055`](./0055-dark-utility-register-fundament.md). Deren Punkt 4a (`--text-muted` = `#8D92A4` statt `#62677A`) und Punkt 4f (Chip-Schrift „Gebäude" = `#FF44A1` statt `#FF007F`) bleiben unverändert in Kraft und werden hier **nur in der Richtung** ergänzt, in der sie bisher nichts sagen: Sie gelten ab jetzt auch für die Figma-Datei, nicht nur für den Code. ADR 0055 wird dadurch weder geändert noch teilweise abgelöst.
- ADR [`0048`](./0048-board-operationen-zielzustands-idempotent.md), tragende Regel „Zielzustand setzen statt Übergang auslösen". Sie ist dort für die GitHub-Board-Operationen formuliert; Abschnitt 4 überträgt sie auf die Figma-Operationen, weil dort dasselbe Problem in schärferer Form auftritt (Abbruch mitten im Lauf bei einem harten Aufrufkontingent).

## Kontext

> **Zahlenkorrektur am 2026-09-07, nach dem ersten `use_figma`-Lauf.** Dieser Abschnitt nannte zuerst die Handmessung vom 2026-09-06: 459 Knoten, 418 Vorkommen, 318 Fills. Der Lauf hat 460 / 419 / 319 gemessen (Strokes unverändert 100) und ist in der Vorprüfung abgebrochen, ohne zu schreiben. Die Differenz ist exakt ein Eintrag: die Füllung des **Board-Knotens selbst** (`2:4 fills 0 #0B0C10`), die die Handmessung ausgelassen hatte, weil sie nur die Nachfahren zählte. Er ist hexgleich, verschiebt also nur die Zählwerte und die hexgleichen Gruppen (289 → 290, 336 → 337, 370 → 371) und lässt die 48 geänderten Vorkommen unberührt. Die Zahlen unten sind auf den gemessenen Stand gezogen; die Begründung steht ausführlich in AK0 der Spec.

Das Figma-Board `photosort-design-system` („Photosort Dark", V1.2) ist die Entwurfsquelle des Design-Systems „Dark Utility Register". Es trägt **460 Knoten mit 419 fest eingetragenen Farbvorkommen** (319 Solid-Fills, 100 Solid-Strokes) in **23 verschiedenen Farbwerten** — und **null** Bindungen an eine Variable, obwohl die Collection „PhotoSort Farben" (ein Modus `Dunkel`) seit dem 2026-09-03 zwölf Farbvariablen führt. Eine Farbe zu ändern heißt heute, bis zu 72 Knoten von Hand anzufassen.

Zwei Dinge machen daraus mehr als eine Aufräumaufgabe in einem fremden Werkzeug.

**Erstens driftet das Board bereits sichtbar vom ausgelieferten Code.** ADR 0055 hat zwei Board-Werte aus Kontrastgründen bewusst korrigiert. Der Code führt diese Korrektur seit Spec 0320; das Board zeigt an 48 Stellen weiterhin die verworfenen Werte. Wer das Board für einen Entwurf heranzieht, entwirft gegen eine Palette, die die App nie ausliefert — und es gibt heute nichts, was das bemerkt.

**Zweitens deckt Figma die Palette nicht vollständig ab, und das ist beabsichtigt.** Am 2026-09-07 nachgerechnet: `frontend/src/index.css` deklariert **63 Farbtokens mit 40 verschiedenen Hexwerten**. Davon stehen **21** auch im Board. Die zwei Board-Werte ohne Entsprechung im Code sind exakt die beiden von ADR 0055 verworfenen (`#62677A`, `#FF007F`). Die **19** Code-Werte ohne Board-Entsprechung sind: die sieben nach der Ableitungsregel aus ADR 0055 Punkt 6a erzeugten Kategorie-Chip-Paare (14 Werte), dazu `--border-control` `#727891`, `--separator` `#474E68`, `--danger-text` `#FF5A26` sowie die beiden Korrekturwerte `--text-muted` `#8D92A4` und `--chip-gebaeude-bauwerk-fg` `#FF44A1`.

Ohne eine ausgesprochene Entscheidung ist diese Teilabdeckung von einer Lücke nicht zu unterscheiden. Die nächste Person, die das Board öffnet, wird entweder die fehlenden neunzehn nachtragen (und einen zweiten Wahrheitsort für Werte schaffen, die nie in einem Entwurf vorkommen) oder die zwei alten Board-Werte für gültig halten.

**Zur Zahl „16" aus dem Issue.** Issue #336 spricht von „den übrigen 16 Farbwerten des Codes". Nachgerechnet sind es **19 vor** und **17 nach** dieser Umstellung — die Differenz entsteht dadurch, dass die beiden Korrekturwerte `#8D92A4` und `#FF44A1` mit dieser Story selbst zu Figma-Variablenwerten werden und danach nicht mehr code-eigen sind, und dadurch, dass ADR 0055 Punkt 6a **sieben** abgeleitete Buntpaare kennt, nicht acht (das dreizehnte Paar „Nicht erkannt" ist bewusst neutral und benutzt zwei Board-Werte weiter). Die Zahl im Issue ist um eins bzw. drei zu niedrig; maßgeblich ist die hier nachgerechnete.

## Entscheidung

### 1. Figma führt die 23 Board-Farben, `index.css` führt die ausgelieferte Palette — und jede Figma-Farbe muss im Code vorkommen

Die Collection „PhotoSort Farben" führt **genau die Farben, die auf dem Board vorkommen**, als Variablen: die zwölf bestehenden plus elf neue (`Rahmen/Trennlinie` `#2A2E3D` sowie die fünf Kategorie-Chip-Paare des Boards). Kein Knoten des Boards trägt danach noch einen fest eingetragenen Farbwert.

**Die tragende Zusicherung ist eine Richtungsaussage, keine Gleichheit:** Jeder Wert, den eine Figma-Variable führt, muss auch als `:root`-Token in `frontend/src/index.css` stehen. Umgekehrt gilt das ausdrücklich **nicht** — der Code darf Werte führen, die Figma nicht kennt.

Nach der Umstellung ist die Zusicherung erfüllt: Die 23 Variablenwerte sind die 21 geteilten plus `#8D92A4` plus `#FF44A1`, und alle 23 stehen in `index.css`. Die beiden verworfenen Board-Werte `#62677A` und `#FF007F` verschwinden damit vollständig aus der Figma-Datei, statt dort als tote Alternative weiterzuleben.

`index.css` bleibt die auslieferungsrelevante Quelle. Die Figma-Variablen sind ein **Abbild für den Entwurf**, keine zweite Wahrheit: Aus einer Figma-Variablen wird nichts generiert, nichts gebaut und nichts importiert.

### 2. Bei Widerspruch gilt ADR 0055 — die Korrektur wandert nach Figma, nie zurück

`Text/Gedämpft` trägt ab jetzt `#8D92A4` statt des Board-Werts `#62677A`; die neue Variable für die Chip-Schrift „Gebäude" trägt `#FF44A1` statt `#FF007F`. Beide Variablen tragen den Grund in ihrer **Beschreibung im Figma-Dokument selbst** — nicht nur hier —, samt der ausdrücklichen Aussage, dass der Board-Wert nicht zurückzuschreiben ist.

Warum die Beschreibung und nicht nur die ADR: Die Person, die in Figma den vermeintlich „falschen" Wert sieht, hat das Repository in dem Moment nicht offen. Eine Begründung, die nur im Repository steht, erreicht sie nicht — und die naheliegendste Korrektur ist genau die falsche.

Die 47 Knoten in `#62677A` und der eine in `#FF007F` verändern durch die Bindung ihr Aussehen. Das ist der beabsichtigte Effekt, nicht ein Nebeneffekt: Das Board zeigt danach die Farben, die die App ausliefert.

### 3. Kein Abgleichmechanismus — die Grenze wird stattdessen im Repository abgeprüft

Es entsteht **kein** Werkzeug, das Figma und `index.css` gegeneinander abgleicht, weder in eine Richtung noch periodisch, weder in CI noch von Hand. Ein solcher Abgleich bräuchte in jedem Lauf einen Zugriff auf ein fremdes System mit hartem Aufrufkontingent (Abschnitt 5) und würde eine Divergenz zu einem CI-Fehler machen, obwohl sie in aller Regel schlicht bedeutet, dass jemand in Figma etwas ausprobiert.

An seine Stelle tritt eine Prüfung, die **ausschließlich Dateien dieses Repositories liest** (`scripts/tests/`, gleiche Bauart wie die dort bereits vorhandenen Konsistenztests, kein Netzwerk, kein Aufrufkontingent):

- Das im Repository geführte **Farbregister** — der Soll-Zustand aller 23 Figma-Variablen mit Name, Wert, Scopes und Beschreibung — muss vollständig unter den Hexwerten aus `index.css` liegen (Abschnitt 1).
- Die **17 code-eigenen Werte** stehen namentlich und einzeln begründet im selben Register. Ein Wert in `index.css`, der weder eine Figma-Variable noch einen Eintrag in dieser Liste hat, färbt den Test rot. Damit ist die Teilhoheit erzwungen statt nur behauptet: Wer die Palette erweitert, muss sich entscheiden, auf welcher Seite der Grenze der neue Wert liegt.

Der Preis ist benannt: Ändert jemand in Figma einen Wert von Hand, merkt das Repository es nicht. Das Register bleibt dann als Soll stehen und ist beim nächsten Lauf des Skripts (Abschnitt 4) sofort wieder maßgeblich — der Lauf setzt den Zielzustand, er liest ihn nicht ab.

### 4. Nachweis für eine Änderung, deren Wirkung außerhalb des Repositories liegt: gemessenes Vorher und Nachher

Ein Pull Request, dessen eigentliche Wirkung in einer fremden Datei eintritt, kann seine Wirkung nicht zeigen — nur behaupten. Die Gegenmaßnahme sind drei Artefakte, die zusammen im Repository liegen:

1. **Ein einziger Skript-Payload** (`scripts/figma/`), der wortgleich das ist, was ausgeführt wurde. Er trägt das Farbregister als abgegrenzten, strikt JSON-parsbaren Block in sich — nicht als zweite Datei. Ein Register, das gesplittet oder vor dem Senden zusammengesetzt werden muss, driftet vom Ausgeführten ab; ein eingebetteter Block kann es nicht.
2. **Ein gemessenes Inventar vor und nach dem Lauf**, je ein Eintrag pro Farbvorkommen mit Knoten-ID, Eigenschaft, Index, Hexwert, Deckkraft, Mischmodus und Sichtbarkeit, deterministisch sortiert. Beide Dateien schreibt die Hauptsession aus dem Rücklauf desselben Laufs.

   **Präzisiert am 2026-09-07 durch Spec [`0336`](../features/0336-figma-board-farbvariablen.md), Abschnitt „Schema der Inventardateien" — dort steht die verbindliche Form, hier die Begründung der drei Abweichungen von der Zeile darüber:**

   - **Die Inventare führen zusätzlich die Variablen selbst** (`id`, `name`, `wert`, `scopes`, `beschreibung`), nicht nur die Vorkommen. Ohne ein gemessenes Vorher der Variablen sind die Zusagen „die zwölf bleiben unverändert", „elf kommen hinzu", „beide Korrekturwerte tragen ihre Begründung" und „die Version ist hochgezogen" nur behauptet. Es kostet nichts — derselbe eine Lauf misst es mit.
   - **Das Register trägt je Variable die erwartete Vorkommenszahl** (Summe 419). Ohne sie wäre „alle 419 sind gebunden" mit einer *falschen* Bindung genauso grün wie mit der richtigen; die Gesamtzahl stimmt ja.
   - **Das Feldschema ist geschlossen und deutschsprachig benannt**, jeder Wert gegen eine Form geprüft, und jeder unbekannte Schlüssel färbt den Test rot. Das ist keine Namenskosmetik, sondern die Umsetzung des Muss-Kriteriums M3 der Sicherheitsbetrachtung: Freitext aus einem fremden System ist gleichzeitig Leck- und Injektionskanal, und eine Ausschlussliste, die nur im Text steht, ist keine.
3. **Die Prüfung aus Abschnitt 3**, die beide Inventare gegen das Register und gegeneinander rechnet: gleiche Schlüsselmenge (kein Knoten verloren oder hinzugekommen), nach dem Lauf kein einziges ungebundenes Vorkommen mehr, genau 48 geänderte Hexwerte in genau den zwei erwarteten Übergängen, die übrigen 371 unverändert, und Deckkraft/Mischmodus/Sichtbarkeit an allen 419 unangetastet.

**Die Prüfung überspringt sich nicht, wenn die Inventare fehlen — sie schlägt fehl.** Ein Test, der bei fehlendem Nachweis grün wird, ist der Nachweis nicht wert: Genau dann wäre eine unfertige Umstellung nicht von einer fertigen zu unterscheiden. Der Zwischenzustand mit rotem Test ist deshalb der gewollte Zustand des Branches, solange der Figma-Lauf aussteht.

### 5. Ein Aufruf, idempotent und selbstverortend

Der Figma-MCP-Zugang hängt an einem Starter-Plan mit hartem Aufrufkontingent — am 2026-09-06 nach **drei** `use_figma`-Aufrufen erschöpft. Jeder Aufruf führt beliebig viel JavaScript im Plugin-Kontext aus; das Kontingent zählt Aufrufe, nicht Arbeit. Daraus folgt eine Bauform, die auch dann richtig ist, wenn das Kontingent später wegfällt:

- **Ein Aufruf macht den ganzen Weg**: Inventar messen → Vorprüfung → Variablen setzen → binden → Versionsangabe hochziehen → erneut messen → beides zurückgeben. Kein Aufruf dient allein dem Nachsehen.
- **Zielzustands-idempotent** (ADR 0048): Eine Variable wird auf ihren Sollwert gesetzt, gleich ob sie existiert; eine Bindung wird gesetzt, wo sie fehlt. Ein zweiter Lauf ist folgenlos, ein Lauf nach einem Abbruch räumt den Rest auf.
- **Selbstverortend**: Jeder Lauf gibt den vollständigen erreichten Stand zurück. Nach einem Abbruch ist der Stand aus dem letzten Rücklauf ablesbar, ohne einen weiteren Aufruf zu verbrauchen.
- **Vorprüfung mit Abbruch vor jeder Änderung**: Der Lauf ändert nichts, solange nicht *jedes* gemessene Vorkommen durch das Register erklärt ist — entweder bereits wie vorgesehen gebunden oder mit einem Hexwert aus dem Register. Die Prüfung ist damit **unabhängig vom Fortschritt** und schlägt nach einem Teillauf nicht fälschlich an. Findet sich etwas Unerwartetes, kehrt der Lauf mit dem Inventar zurück, ohne zu schreiben; korrigiert wird dann am Register, was nichts kostet.

Ein reiner Schau-Lauf bleibt möglich, ohne eine zweite Datei und ohne den Payload zu verändern: Die Hauptsession stellt dem Payload `globalThis.NUR_PRUEFEN = true;` voran.

## Begründung

- **Warum eine Richtungsaussage statt Gleichheit.** Gleichheit („Figma und Code führen dieselbe Palette") wäre die einzige Regel, die man sich merken müsste — und sie wäre falsch, sobald der Code eine Farbe braucht, die in keinem Entwurf vorkommt. Genau das ist bei sieben der dreizehn Kategorie-Paare der Fall: Sie sind nach einer Regel *gerechnet* worden, nicht entworfen. Sie nach Figma zu tragen hieße, eine Ableitung als Entwurfsentscheidung auszugeben. Die Richtungsaussage erlaubt das Wachstum genau dort, wo es entsteht, und verbietet die eine Sache, die wirklich schadet: eine Farbe in Figma, die es in der App nicht gibt.
- **Warum die Korrektur nach Figma wandert und nicht der Code zum Board zurück.** Der Board-Wert `#62677A` verfehlt 4,5:1 auf allen vier Flächen und trägt im Board echten Fließtext; das ist in ADR 0055 Punkt 4a ausgerechnet und entschieden. Diese ADR trifft die Entscheidung nicht neu, sie zieht nur die Konsequenz dort nach, wo sie bisher fehlt.
- **Warum der Grund in der Figma-Beschreibung steht und nicht nur hier.** Eine Begründung muss dort stehen, wo der Zweifel entsteht. Er entsteht beim Blick auf den Wert in Figma — der einzige Ort, an dem der Wert ohne Kontext aussieht wie ein Fehler.
- **Warum kein Abgleichmechanismus.** Er hätte genau zwei Betriebszustände: rot, weil jemand in Figma gearbeitet hat, oder abgeschaltet, weil das Rot nervt. Beide sind schlechter als eine geprüfte Registeraussage im Repository, die kein fremdes System befragt und deshalb auch nicht an dessen Kontingent hängt.
- **Warum das Register im Payload steht und nicht daneben.** Zwei Dateien, von denen eine ausgeführt und eine geprüft wird, sind zwei Abbilder derselben Aussage — und zwei Abbilder driften. Die Prüfung liest deshalb genau den Block, der auch ausgeführt worden ist. Das Zusammensetzen vor dem Senden wäre die dritte Variante und die schlechteste: ein Handgriff, den niemand im Diff sieht.
- **Warum die Vorprüfung fortschrittsunabhängig formuliert ist.** Eine Prüfung „419 Vorkommen tragen einen Hexwert aus dem Register" wäre nach einem Teillauf falsch und würde die Wiederaufnahme genau dann blockieren, wenn man sie braucht. Die Formulierung „gebunden **oder** im Register" gilt in jedem Zwischenzustand und ist trotzdem vollständig — sie lässt keine unerklärte Farbe durch.
- **Warum ein Aufruf und nicht erst schauen, dann ändern.** Getrennt wären es zwei Aufrufe von dreien für einen Blick, den die Vorprüfung ohnehin schärfer leistet: Sie prüft nicht stichprobenartig, sondern verlangt, dass *jedes* Vorkommen erklärt ist. Der Blick vor dem Anfassen ist damit nicht weggelassen, sondern automatisiert — und weil das Vor-Inventar im selben Rücklauf zurückkommt, geht auch der Beweis nicht verloren. Wer trotzdem zuerst sehen will, hat den Schau-Lauf.
- **Warum die Zahl aus dem Issue korrigiert und nicht übernommen wird.** Eine Prüfung, die eine falsche Zahl festschreibt, ist schlimmer als keine: Sie sieht aus wie eine Zusicherung und ist eine. Die 17 ist aus `index.css` gerechnet und in der Prüfung namentlich aufgeschlüsselt, nicht als Zahl gesetzt — eine später hinzukommende Farbe verschiebt sie und muss begründet werden.

## Konsequenzen

- **Neu unter `scripts/figma/`:** der `use_figma`-Payload mit eingebettetem Farbregister (23 Variablen, 17 code-eigene Werte), die zwei gemessenen Inventardateien, eine `README.md` mit Ablauf, Aufrufbudget und Wiederaufnahme. Kein Python, keine neue Abhängigkeit — der bestehende CI-Job `demo-scripts` lintet nur Python und läuft unverändert.
- **Neu unter `scripts/tests/`:** ein Konsistenztest, der Register, Inventare und `frontend/src/index.css` gegeneinander rechnet. Kein Netzwerk, keine MCP-Werkzeuge, kein Aufrufkontingent, kein numerisches Coverage-Gate — gleiche Einordnung wie die dort bereits vorhandenen Tests. Er führt die **reinen** Teile des Payloads unter `node` aus, statt seinen Quelltext nach Schlüsselwörtern zu durchsuchen (Entscheidungsfunktionen werden geprüft, indem man sie aufruft); `node` ist damit ab dieser Story auch in `scripts/tests/` eine Testlaufzeit. Der Job `demo-scripts` bleibt trotzdem unverändert — `ubuntu-latest` bringt Node vorinstalliert mit, die Aussage „keine Änderung an `.github/workflows/`" hält.
- **Kein Effekt auf `frontend/`.** `index.css` wird gelesen, nicht geändert; kein `.tsx` wird angefasst; `designSystem.contract.test.ts` bleibt unverändert und behält seine Zuständigkeit für den Code. Der neue Test rechnet ausdrücklich **nicht** noch einmal Kontraste nach — das täte er sonst an zweiter Stelle mit einer zweiten Fehlerquelle.
- **`specs/architecture/0005-board-dark-utility-register.md`** bekommt einen Kopfvermerk, dass das Board inzwischen auf einer höheren Version steht und seine Farben variabelgebunden sind. Die Werteliste selbst bleibt unangetastet — sie ist eine Momentaufnahme des Stands V1.2 und wird das bleiben.
- **Kein Effekt auf `docs/architecture.md`, `docs/setup.md` und das Root-`README.md`.** Figma ist kein Bestandteil der laufenden Anwendung, kein Schritt des lokalen Setups und keine Laufzeitabhängigkeit; gleiche Einordnung wie ADR 0037/0043/0046/0052/0056/0057/0061.
- **Kein Secret, keine neue Laufzeit- oder Entwicklungsabhängigkeit, keine Änderung an `.github/workflows/`.** Der Figma-MCP-Zugang ist Umgebungs- und Nutzerkonfiguration (Konto daniel@koller.dk) und wird vom Repository nicht vorausgesetzt: Fehlt er, bleibt die Prüfung aus Abschnitt 3 lauffähig und schlägt lediglich fehl, solange die Inventare fehlen.
- **Der Figma-Lauf kann nicht im `developer`-Subagenten stattfinden** — dessen Werkzeugsatz enthält die MCP-Werkzeuge nicht. Die Arbeit teilt sich deshalb: `developer` erstellt Register, Payload, Prüfung und Dokumentation und übergibt mit rotem Test; der Lauf und das Einpflegen der Inventare geschehen in der Hauptsession. Das ist keine Ausnahme von der Umsetzungsordnung, sondern ihre Anwendung auf einen Schritt, den der Subagent nachweislich nicht ausführen kann.
- **Nicht Teil dieser Entscheidung:** Variablen für Abstände, Radien und Typografie in Figma (bewusst weiter vertagt, im Board nirgends beschriftet); ein hellerer Modus in der Collection (es gibt nur `Dunkel`); Figma-Variablen für die 17 code-eigenen Werte; ein Generator, der aus Figma `index.css` erzeugt oder umgekehrt.
- Ein späterer Wechsel dieses Modells — volle Deckungsgleichheit beider Seiten, ein echter Abgleichmechanismus, oder Figma als führende Quelle für die Palette — bleibt architekturrelevant und braucht eine neue ADR, die diese hier als „Superseded" markiert.
