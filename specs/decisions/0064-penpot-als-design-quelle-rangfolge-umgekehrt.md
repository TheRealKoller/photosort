# 0064 - Penpot ist die Design-Quelle: Rangfolge umgekehrt, Figma-Board archiviert

**Status:** Accepted
**Datum:** 2026-09-08
**Bezug:** [GitHub-Issue #352](https://github.com/TheRealKoller/photosort/issues/352), [`features/0352-penpot-design-quelle.md`](../features/0352-penpot-design-quelle.md)

**Nimmt ausdrücklich zurück (Festlegung eines Referenzdokuments, keine ADR):**
- [`architecture/0005-board-dark-utility-register.md`](../architecture/0005-board-dark-utility-register.md), die beiden Sätze „**Diese Datei ist die maßgebliche Werteliste im Repo**" und „bei Widerspruch gilt die ADR, nicht diese Momentaufnahme". Beide fallen: Die maßgebliche Werteliste im Repo ist ab jetzt `frontend/src/index.css` (Abschnitt 3), und die Rangfolge zwischen Repo und Design-Quelle kehrt sich um (Abschnitt 2). Der **Inhalt** der Datei bleibt wortgetreu stehen — sie ist eine Momentaufnahme, und eine nachträglich umgeschriebene Momentaufnahme wäre eine Fälschung. Angefasst wird ausschließlich ihr Kopf (Abschnitt 5).

**Berührt außerdem (keine Ablösung):**
- [`decisions/0055-dark-utility-register-fundament.md`](./0055-dark-utility-register-fundament.md): Alle acht Entscheidungspunkte bleiben unverändert in Kraft, insbesondere Punkt 4 (Kontrast-Untergrenze schlägt den Wert der Design-Quelle) — Abschnitt 4 dieser ADR schreibt ihn ausdrücklich fort statt ihn zu ersetzen. Abgelöst ist allein der Satz der dortigen Begründung „Board-Werte sind eine Vorlage, kein Gesetz" **in seiner vorwärtsgerichteten Wirkung**; ab hier ist die Design-Quelle für die Gestaltung normativ. ADR 0055 trägt dafür einen `**Teilweise abgelöst:**`-Vermerk im Kopf, kein `Superseded` — ihr Kern fällt nicht.
- [`decisions/0011-ui-component-library.md`](./0011-ui-component-library.md): Tailwind v4 (CSS-first, `@theme`) + Radix + shadcn-Copy-in-Repo bleiben unverändert die Grundlage. Diese ADR ändert nichts an der Umsetzung im Produkt.
- [`decisions/0065-penpot-stand-als-erzeugte-idempotente-nutzlast.md`](./0065-penpot-stand-als-erzeugte-idempotente-nutzlast.md) entscheidet, **wie** das System nach Penpot kommt und wer es ausführt. Diese ADR entscheidet nur, **dass** Penpot die Quelle ist und was das für die Rangfolge heißt. Die Trennung ist Absicht: Die Rangfolge soll auch dann noch gelten, wenn der Mechanismus einmal ausgetauscht wird.

## Kontext

Das Design-System „Dark Utility Register" liegt heute in einer Figma-Datei. Der Zugang hängt an einem Starter-Plan mit hartem Aufruflimit, das zuletzt nach einem einzigen Zugriff pro Sitzung erschöpft war. Damit ist das Werkzeug für Entwurfsarbeit unbrauchbar geworden — nicht langsam, sondern nicht benutzbar. Die praktische Folge ist bereits eingetreten: Gestaltungsänderungen entstehen unmittelbar im Code, weil der Zwischenschritt „erst sehen, dann bauen" faktisch nicht mehr existiert. Für ein Projekt, dessen einziger Entwickler die Oberfläche ohne Browserlauf nicht sieht, ist das die teuerste aller Lücken.

Daniel betreibt inzwischen eine eigene, selbst gehostete Penpot-Instanz. Sie hat kein Aufruflimit, ihre Verfügbarkeit hängt aber an ihm: Ohne offene, verbundene Penpot-Sitzung antwortet der Penpot-MCP-Server mit „No Penpot instance connected". Das ist keine Störung, sondern die dauerhafte Nutzungsbedingung — anders als beim bisherigen Werkzeug läuft nichts im Hintergrund ohne Daniel.

Der Wechsel ist deshalb nicht bloß ein Ortswechsel. Er wirft eine Frage auf, die das Projekt bisher andersherum beantwortet hatte: **Wer gewinnt, wenn Design-Quelle und Repository sich widersprechen?** Bis heute das Repository — die Board-Momentaufnahme 0005 sagt das ausdrücklich über sich selbst, und ADR 0055 hat auf dieser Grundlage acht Board-Werte begründet korrigiert. Diese Antwort war richtig, solange die Quelle ein Standbild war, das niemand mehr pflegen konnte. Sie ist falsch, sobald die Quelle wieder ein Arbeitsort ist, an dem entworfen wird, bevor gebaut wird: Dann wäre jeder Entwurf von vornherein unverbindlich, und der Wechsel hätte keinen Zweck.

Zugleich darf die Umkehrung nicht dazu führen, dass eine ausgefallene oder verlorene Instanz das Projekt sein Design-System kostet, und sie darf die begründeten Kontrast-Korrekturen nicht durch die Hintertür wieder aufheben. Genau diese drei Ansprüche — Penpot gewinnt, das Repo weiß trotzdem was gilt, die Untergrenze bleibt — stehen scheinbar gegeneinander. Sie stehen es nicht, sobald man trennt, **worüber** jeweils entschieden wird.

## Entscheidung

### 1. Penpot ist die alleinige Design-Quelle; Figma wird nicht mehr gepflegt

Die Datei „PhotoSort — Dark Utility Register" in Daniels selbst gehosteter Penpot-Instanz ist ab dieser ADR der Ort, an dem das Design-System gepflegt und an dem entworfen wird. Die Figma-Datei „Photosort Dark" wird nicht mehr gepflegt; ihr letzter gültiger Stand ist die Momentaufnahme 0005 (Abschnitt 5).

Übertragen wird der **heute im Code umgesetzte Stand**, nicht der ältere Stand des Figma-Boards. Die acht in [`architecture/0004-design-system.md`](../architecture/0004-design-system.md) geführten Abweichungen sind in Penpot der gültige Wert. Andernfalls kehrten die begründet korrigierten, schlechter lesbaren Farbwerte über die neue Quelle zurück — der Wechsel würde eine bereits getroffene Entscheidung stillschweigend rückgängig machen.

**Die Instanzadresse steht nicht im Repository.** Weder Hostname noch URL noch Zugangsdaten der selbst gehosteten Instanz werden eingecheckt; der MCP-Server ist in Daniels lokaler Werkzeugkonfiguration eingerichtet, nicht in einer Repo-Datei. Im Repo steht ausschließlich der **Dateiname** der Penpot-Datei — er genügt, um sie zu finden, und verrät nichts über die Infrastruktur. Das ist dieselbe Linie, die das Projekt für Tokens und Endpunkte ohnehin fährt (`.env`, nie eingecheckt).

### 2. Die Rangfolge kehrt sich um — und zwar getrennt nach Gestaltung und Wert

Die Umkehrung, die Akzeptanzkriterium 7 verlangt, wird hier ausdrücklich vollzogen und nicht stillschweigend praktiziert. Sie lautet in drei Sätzen:

1. **Gestaltung — Penpot gewinnt.** Welche Farbe, Form, Größe oder welchen Zustand ein Baustein haben *soll*, entscheidet Penpot. Weicht das Repository davon ab, ist das ein Mangel des Repositorys und nicht ein Argument gegen den Entwurf. Bis heute galt das Gegenteil.
2. **Gültiger Wert — `frontend/src/index.css` gewinnt.** Was im Produkt heute tatsächlich *gilt und ausgeliefert wird*, steht in `index.css`. Eine Änderung in Penpot wird nicht dadurch wirksam, dass sie dort steht, sondern erst, wenn sie über den normalen Weg (Story → Spec → PR) im Repository ankommt. Das ist keine zweite Quelle, sondern der Unterschied zwischen Absicht und Zustand.
3. **Kein Ort erklärt den anderen für falsch.** Ein Auseinanderlaufen zwischen 1 und 2 ist kein Streitfall, sondern eine offene Aufgabe: Der Entwurf ist schon da, die Umsetzung fehlt noch.

Bewusst nicht gewählt: „Penpot gewinnt über alles, auch über den ausgelieferten Wert." Das klingt konsequenter und wäre unbrauchbar — es hieße, dass ein halbfertiger Entwurf in Penpot den Produktstand für ungültig erklärt, ohne dass irgendjemand ihn gebaut hat. Ebenso nicht gewählt: „beide gleichrangig, mit dokumentiertem Abgleich." Zwei gleichrangige Orte ohne Vorrang sind genau die Konstruktion, in der Drift unbemerkt bleibt, weil niemand entscheiden muss.

### 3. Das Repository bleibt ohne Penpot auskunftsfähig — mit `index.css` als Werteliste

Akzeptanzkriterium 8 verlangt, dass die Werte im Repo nachvollziehbar bleiben, auch wenn die Instanz gerade nicht erreichbar ist. Es wird **nicht** über ein zweites Wertedokument erfüllt, sondern über das, was ohnehin da ist:

- **`frontend/src/index.css`** ist die maßgebliche Werteliste im Repo. Jedes Token trägt dort einen ausgeschriebenen Hexwert bzw. eine ausgeschriebene Größe, nie `var()` oder `color-mix()` — diese Eigenschaft existiert bereits und ist die Voraussetzung dafür, dass `frontend/src/designSystem.contract.test.ts` die vollständige Kontrastmatrix nachrechnet. Sie wird damit vom Prüfmittel zusätzlich zum Auskunftsmittel.
- **`specs/architecture/0004-design-system.md`** bleibt der Ort für die *Regeln* (welches Token welche Rolle hat, welche Verwendung verboten ist, welche Abweichungen begründet sind). Werte ohne Regeln sind nicht benutzbar; Penpot trägt die Werte, nicht die Begründungen.
- Ein **drittes**, von Hand gepflegtes Wertedokument entsteht nicht. Genau das wäre der zweite Wahrheitsort, den Akzeptanzkriterium 8 nicht meint und den 0005 heute darstellt.

Damit ist auch der Ausfall beantwortet: Ist die Instanz weg, weiß das Repository vollständig, was gilt — und ADR 0065 sorgt dafür, dass daraus der Penpot-Stand wieder aufgebaut werden kann, statt ihn von Hand nachklicken zu müssen.

Die beiden Laufrichtungen zusammen ergeben einen Kreis, und genau der ist die Stelle, an der man diese ADR falsch lesen kann. Er ist deshalb als Diagramm festgehalten: [`../diagrams/design-quelle-penpot.svg`](../diagrams/design-quelle-penpot.svg) (Quelle: `../diagrams/design-quelle-penpot.d2`). Abwärts laufen **Werte**, erzeugt und maschinell; aufwärts läuft **Gestaltung**, über den normalen Story-Weg und durch den Vertragstest.

### 4. Die eine Ausnahme: die Kontrast-Untergrenze schlägt auch Penpot

Ein Wert aus Penpot, der WCAG-AA gegen die Fläche verfehlt, auf der er tatsächlich steht (4,5:1 Fließtext, 3:1 grafisch und Bedienelement-Umrisse), wird **nicht** unverändert übernommen. Er wird nach derselben Regel korrigiert, die ADR 0055 Punkt 4 bereits anwendet — **die Fläche bleibt, angepasst wird die Schrift- oder Linienfarbe** — und **die Korrektur wird nach Penpot zurückgeschrieben**.

Das ist kein Vetorecht des Repositorys über die Design-Quelle, und es weicht Abschnitt 2 nicht auf. Erstens ist die Untergrenze ein eigenständiges Akzeptanzkriterium des Produkts, kein Geschmacksurteil des Repositorys; Daniel hat für den Vorgänger bereits entschieden, dass sie gewinnt, wo die Quelle ihr widerspricht. Zweitens — und das ist der eigentliche Punkt — endet der Vorgang **in Penpot**, nicht im Repository: Nach der Korrektur stimmen beide Orte wieder überein, und die Quelle trägt den gültigen Wert. Eine Regel, die die beiden zusammenführt, ist etwas anderes als eine Regel, die sie auseinanderhält.

Ohne diese Klausel wäre Akzeptanzkriterium 2 nicht haltbar: Die acht Korrekturen wären ab dem nächsten Entwurf jederzeit widerrufbar, ohne dass es jemand bemerkt. Der Vertragstest ist die Stelle, an der ein solcher Wert auffällt — er rechnet nach, statt zu glauben.

**Von Daniel bestätigt (2026-09-08).** Dieser Abschnitt und die Frage aus ADR 0065 Abschnitt 4 (Was darf ein erneuter Lauf überschreiben?) sind Produktentscheidungen; beide sind im `spec-writer`-Ablauf zu Spec 0352 vorgelegt und nach der Empfehlung des `architect` bestätigt worden. Eine spätere Abweichung davon ist eine neue ADR, keine stille Korrektur hier.

### 5. Was mit den heutigen Figma-Fundstellen geschieht — und was ausdrücklich nicht

Akzeptanzkriterium 7 verlangt, dass die Stellen, die heute Figma als Quelle benennen, danach Penpot nennen. Maßgeblich ist dabei die Unterscheidung zwischen einer **normativen** Aussage (*das ist die Quelle, daran halten wir uns*) und einer **historischen** (*dieser Wert kam damals von dort*). Nur die erste wird geändert. Die zweite umzuschreiben hieße, die Herkunft der Werte zu fälschen — und ausgerechnet die Herkunft ist das, was Akzeptanzkriterium 9 erhalten will.

**Wird geändert (normativ):**

| Datei | Änderung |
|---|---|
| `specs/architecture/0005-board-dark-utility-register.md` | **Nur der Kopf.** Status wird `Archiv — abgelöste Design-Quelle, wird nicht mehr gepflegt`, mit Verweis auf diese ADR und dem Hinweis, dass die maßgebliche Werteliste `frontend/src/index.css` ist. Der Rumpf bleibt unverändert. |
| `specs/architecture/0004-design-system.md` | Der Satz „Grundlage ist das Figma-Board …" wird auf Penpot umgestellt; die Tabelle der acht Abweichungen bleibt, ihre Überschrift sagt künftig, dass sie die **Herkunft** der Werte festhält und nicht mehr einen offenen Abgleich gegen eine fremde Quelle. Der Verweis auf 0005 wird als Archivverweis gekennzeichnet. |
| `.claude/skills/design-system/SKILL.md` | Die Quellenzeile nennt zusätzlich Penpot als Design-Quelle und den Skill `penpot-design` als den Weg dorthin. |
| `.claude/skills/review/SKILL.md` (+ ADR 0040 Teil 2, ADR 0014 Teil 1) | Die Trigger-Tabelle des `review`-Orchestrators nimmt `design/penpot/**` und `.claude/skills/penpot-design/**` als **Security**-Trigger auf. Heute greift dort kein Trigger, obwohl der Diff ausführbaren Code enthält, der später in einer angemeldeten Browsersitzung startet und den CI nicht nachstellen kann — das Review wäre sonst nur über die Ermessensklausel gedeckt. Die drei Stellen sind synchronpflichtig (statischer Konsistenz-Check). **Von Daniel bestätigt (2026-09-08)**, ausdrücklich eng: das breitere `.claude/skills/**` bleibt außen vor. |
| `specs/decisions/0055-…md` | **Nur der Kopf**, `**Teilweise abgelöst:**`-Vermerk (siehe Kopf dieser ADR). |

**Wird nicht geändert (historisch):** `specs/features/0320-…`, `specs/features/0321-…` und der Rumpf von ADR 0055. Umgesetzte Feature-Specs und angenommene ADRs sind Aufzeichnungen; sie berichten zutreffend, dass die Werte aus einem Figma-Board stammen. Ebenso bleiben die Wörter „Board"/„Board-Maß" in Code-Kommentaren und Tests stehen: Sie benennen die Herkunft einer Zahl, nicht eine geltende Quelle. **Eine pauschale Ersetzung Figma → Penpot über das Repository ist ausdrücklich unzulässig.**

## Begründung

Der Kern ist, dass „Quelle der Wahrheit" zwei verschiedene Fragen zusammenfasst, die hier auseinanderfallen: *Was soll gelten?* und *Was gilt?* Solange die Design-Quelle ein totes Standbild war, konnten beide beim Repository liegen. Sobald wieder entworfen wird, bevor gebaut wird, gehört die erste Frage dorthin, wo entworfen wird, und die zweite bleibt dort, wo ausgeliefert wird. Der scheinbare Widerspruch zwischen den Akzeptanzkriterien 7 und 8 ist genau diese Zusammenfassung — er löst sich auf, sobald man sie trennt, und er ließe sich mit keiner Ablage-Entscheidung lösen, solange man sie nicht trennt.

Die zweite Entscheidung ist die Ausnahme in Abschnitt 4. Sie ist die einzige Stelle, an der diese ADR die Umkehrung begrenzt, und sie ist es aus einem Grund, den das Issue selbst benennt: Der Wechsel des Aufbewahrungsorts soll die Gestaltung nicht ändern. Eine Untergrenze, die beim Ortswechsel fällt, hätte die Gestaltung geändert — nur eben unbemerkt und in die schlechtere Richtung.

Die dritte ist die Trennung normativ/historisch in Abschnitt 5. Sie kostet etwas: Ein Leser, der im Repository nach „Figma" sucht, findet weiterhin Treffer und muss am Kopf der jeweiligen Datei erkennen, dass sie historisch sind. Die Alternative — alle Treffer umschreiben — kostet mehr: Sie behauptet, die heutigen Werte kämen aus Penpot, und macht damit ausgerechnet die acht Abweichungen unerklärlich, deren Begründung an ihrer Herkunft hängt.

## Konsequenzen

- **Positiv:** Entwurfsarbeit ist wieder möglich, ohne Fremdlimit. Das Repository ist zum ersten Mal eindeutig darüber, welcher Ort welche Frage beantwortet — bisher beanspruchten 0005 („maßgebliche Werteliste"), 0004 („hier steht das Ergebnis") und `index.css` (der tatsächlich wirksame Wert) diese Rolle nebeneinander. Die Abweichungstabelle in 0004 hört auf, ein offener Abgleich gegen eine fremde Quelle zu sein, und wird zur Herkunftsangabe.
- **Neue externe Abhängigkeit — und ihre ehrliche Bilanz:** Eine selbst gehostete Penpot-Instanz plus MCP-Server tritt an die Stelle eines fremden SaaS-Kontingents. Betriebskosten und Wartung liegen ab jetzt bei Daniel (Hosting, Updates, Sicherung), dafür entfällt die Abhängigkeit von einem fremden Preismodell. **Kein Produktcode und kein Container von PhotoSort hängt daran**; Build, Tests, CI und Betrieb laufen unverändert ohne Penpot. Die Abhängigkeit ist eine Werkzeugabhängigkeit der Entwicklung, keine Laufzeitabhängigkeit — deshalb ändern sich weder `docs/architecture.md` noch `docs/setup.md`.
- **Negativ / bewusst getragen:**
  - **Design-Arbeit setzt Daniels Anwesenheit voraus.** Ohne verbundene Sitzung ist die Quelle nicht erreichbar. Ein Hintergrundlauf, der „mal eben" etwas in Penpot nachzieht, existiert nicht und wird es nicht geben. Wer das übersieht, plant Arbeit ein, die nicht stattfinden kann.
  - **Datenverlust der Instanz ist ein reales Risiko**, weil sie selbst gehostet ist und niemand sie vertraglich sichert. ADR 0065 macht den Stand deshalb wiederherstellbar; das ersetzt keine Sicherung, begrenzt aber den Schaden auf „einmal neu bespielen".
  - **Die Umkehrung erzeugt eine neue Pflicht:** Ein Entwurf in Penpot, der nie ins Repository wandert, ist ab jetzt eine offene Aufgabe und keine Notiz. Wächst dort ein Rückstand, ist das Design-System auseinandergelaufen — sichtbar wird das nur, wenn jemand hinsieht, denn kein Test kann Penpot lesen.
  - Ein Leser findet weiterhin „Figma" im Repository (Abschnitt 5). Das ist gewollt und am jeweiligen Dateikopf erkennbar.
- **Folgearbeit:** Issue #336 („figma variablen") wird ohne Umsetzung verworfen — sein einziger Zweck war, das nun abgelöste Figma-Board wartbar zu machen. Die beiden dort genannten Farbkorrekturen sind über ADR 0055 Punkt 4a/4f im Code bereits umgesetzt und gehen damit nicht verloren. Issue #333 bleibt unberührt; es betrifft Ansichten, nicht die Quelle.
