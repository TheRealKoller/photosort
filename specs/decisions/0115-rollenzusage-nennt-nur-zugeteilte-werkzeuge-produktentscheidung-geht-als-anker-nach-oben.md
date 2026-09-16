# 0115 - Eine Rollenzusage nennt nur zugeteilte Werkzeuge; die Produktentscheidung geht als Anker nach oben

**Status:** Accepted
**Datum:** 2026-09-16
**Bezug:** [GitHub-Issue #454](https://github.com/TheRealKoller/photosort/issues/454), Spec 0454,
ADR [`0024`](./0024-review-agenten-und-pr-workflow-beim-orchestrator.md) und
[`0040`](./0040-ki-workflow-schritte-2-8-konsolidiert.md) (Teil 3: Anker an genau einer
Definitionsstelle — hier angewendet, nicht geändert), ADR
[`0093`](./0093-laufstand-in-der-ausgabe-des-laufs-gelesen-nicht-erfragt.md) (dessen Kontext
einen Werkzeugsatz aus einer Einzelmessung verallgemeinert), ADR
[`0016`](./0016-research-engineer-agent.md) (Tragfähigkeit der Rechercheur-Rolle)

**Umfang:** rund 130 statt 100 Zeilen zu 100 Zeichen, weil jeder der fünf
Entscheidungspunkte eine Zusicherung samt Geltungsbereich und Verletzungsfolge trägt, diese ADR
die einzige Stelle ist, an der die beiden Klassen von Abwesenheit auseinandergehalten werden, und
die Reichweite jedes Kanals hier an der Messung festgemacht wird statt an einer Annahme.

## Kontext

Alle sieben Rollenbeschreibungen unter `.claude/agents/` sagen zu, bei einer echten
Produktentscheidung per `AskUserQuestion` nachzufragen. Ein Subagent hat dieses Werkzeug nicht —
es wird aus **jedem** Subagenten entfernt, unabhängig von seiner `tools:`-Zeile. Die Zusage ist
damit in genau den Lagen unerfüllbar, in denen die Entscheidung Daniel gehört. Was ein Lauf dort
tut, ist nicht vorgeschrieben; die naheliegende Auflösung — er entscheidet still selbst — bleibt
unbemerkt.

Die `tools:`-Zeile ist eine Allowlist über zwei Filtern der Laufzeit: Sie verengt die ohnehin
angebotene Menge und fügt nichts hinzu. **Warum** die Laufzeit so zuteilt, ist hier nicht
Gegenstand.

## Entscheidung

### 1. Zwei Klassen von Abwesenheit, unterschiedlich behandelt

**Strukturell abwesend** ist ein Werkzeug, das einem Hintergrund-Subagenten nie zugeteilt wird.
Ein solches Werkzeug steht **in keiner** `tools:`-Zeile und **in keinem** `description:`-Feld
unter `.claude/agents/`, und keine Prosa dort sagt eine Fähigkeit zu, die es braucht. Nach der
Feststellung zu dieser ADR sind das `AskUserQuestion`, `TaskCreate`, `TaskUpdate`, `TaskGet` und
`TaskList`. Bei Verletzung entsteht wieder eine Zusage, die kein Lauf einlösen kann, und ein Lauf
entscheidet an ihrer Stelle still selbst.

**Die Entfernung ist still.** Eine Rollendatei, die ein entferntes Werkzeug listet, läuft ohne
Fehler und ohne Warnung mit weniger Werkzeugen als da stehen; laut wird die Laufzeit allein dann,
wenn die `tools:`-Zeile zu nichts mehr auflöst. Diese Klasse ist deshalb durch einen Wächtertest
zu sichern und nicht durch Beobachtung im Betrieb.

**Sitzungsabhängig abwesend** ist ein Werkzeug, das die Laufzeit zwar an Subagenten zuteilt, das
aber fehlt, wenn es der aufrufenden Sitzung fehlt — gemessen an `Grep` und `Glob`, ebenso jedes
MCP-Werkzeug. Es darf in der `tools:`-Zeile stehen; die Allowlist verlangt seine Anwesenheit
nicht. Eine Zusage in der Prosa darf sich aber **nicht darauf verlassen, dass es da ist**: Wo
eine Arbeitsanweisung es nennt, nennt sie einen Weg, der auch ohne es trägt, oder nennt es nicht.

Die Unterscheidung ist der Kern dieser ADR: Nur die erste Klasse ist eine Eigenschaft der Rolle
und damit statisch prüfbar; die zweite ist eine Eigenschaft der Sitzung und wäre als CI-Zusage
falsch.

### 2. Ein vierter Anker für die abgegebene Produktentscheidung

Steht eine Entscheidung an, die Daniel gehört, **hält der Lauf an** und beendet seinen Turn mit
dem wörtlich festen Anker `## Blockiert: Produktentscheidung nötig`. Er rät nicht, und er
entscheidet die Frage nicht ersatzweise selbst — auch nicht „vorläufig" oder „als Annahme, die
später geprüft werden kann".

Der Anker gilt für die **sechs** Rollen, deren Rückgabewert die Hauptsitzung erreicht, und ersetzt
jede bisherige `AskUserQuestion`-Stelle in ihnen. Es entsteht **ein** Weg für alle diese Fälle,
nicht je Fall einer: Unterschiedlich ist nur der Inhalt der Frage, nicht der Übergabemechanismus.
Der Rechercheur ist die einzige Ausnahme und setzt den Anker nie (Punkt 3) — er ist die einzige
Rolle, die auch auf einer zweiten Ebene laufen kann, und die einzige ohne Produktmandat.

Das Blockformat samt Feldnamen ist **ausschließlich** in `.claude/skills/produktentscheidung/SKILL.md`
definiert; keine zweite Datei führt eine Kopie. Die Ankerzeile selbst darf dort stehen, wo sie
erkannt oder ausgegeben werden muss — das ist ein funktionaler Verweis, keine zweite
Formatdefinition (ADR 0040 Teil 3, unverändert angewendet).

### 3. Der Anker geht nach oben; der Weg nach unten trägt genau eine Ebene

Die Hauptsitzung erkennt den Anker im Rückgabewert, legt die Frage Daniel vor
(`AskUserQuestion`, dort vorhanden) und gibt die Antwort per `SendMessage` an denselben,
weiterhin offenen Lauf zurück, der danach fortfährt. Gemessen: Der Hauptsitzung ist `SendMessage`
zugeteilt, ein bereits abgeschlossener Lauf wird dadurch fortgesetzt und antwortet, und sein
Werkzeugsatz ist nach der Wiederaufnahme unverändert. Es ist derselbe Mechanismus, den
`## Blockiert: Architektur-Konsultation nötig` bereits trägt. Fehlt der Hauptsitzung `SendMessage`
einmal, wird der Lauf mit der Antwort im Auftrag neu gestartet — die Antwort verfällt nie.

**Der Weg nach unten endet nach einer Ebene, und das ist strukturell, nicht sitzungsabhängig.**
Keiner der sieben Subagenten hat `SendMessage`; je Rolle gemessen und mit Aufrufversuch bestätigt.
Ein Fachagent kann einem Lauf, den er selbst gestartet hat, nichts zustellen — auch keine Antwort,
die er gerade von oben erhalten hat.

**Der Rechercheur gibt deshalb keine Produktentscheidung ab.** Er setzt den Anker **nie**. Eine
Mehrdeutigkeit seines Auftrags nennt er in dem Abschnitt „offene Unsicherheiten", den sein Bericht
ohnehin trägt, und liefert ihn ab, statt anzuhalten. Drei Gründe, jeder für sich tragend. Er hat
laut ADR 0016 kein Produktmandat — die Entscheidung bleibt beim Aufrufer. Seine Eskalationsfälle
sind Mehrdeutigkeiten des **Auftrags** („günstig — Lizenzkosten oder Rechenkosten?"), und deren
Adressat ist, wer den Auftrag geschrieben hat, nicht Daniel. Und eine Pflicht, seinen Text
**unverändert** zwei Ebenen hinaufzutragen, wäre ein Kanal, der Inhalt aus einem Lauf, der
unvertrauenswürdige Webseiten liest, wortgetreu in eine menschliche Entscheidungsvorlage führt —
dieselbe Rollendatei verlangt an anderer Stelle, eingebettete Anweisungen aus Quellen auffällig zu
kennzeichnen. Bei Verletzung entsteht genau diese Einflussmöglichkeit auf Daniels Entscheidung.

**Der Aufrufer einer Recherche löst die Mehrdeutigkeit selbst auf** — er hat den Auftrag
formuliert — oder erkennt, dass dahinter doch eine Produktentscheidung steht, und gibt sie unter
dem Anker als **seine eigene** Frage nach oben, mit eigener Formulierung und eigener Empfehlung.
Es entsteht dadurch keine Lücke: Die Frage erreicht Daniel über die Rolle, die sie ohnehin zu
verantworten hätte. Ist der Aufrufer die Hauptsitzung selbst, liest sie den Bericht und fragt
unmittelbar; ein Anker wäre dort ein Umweg über einen Mechanismus, den sie nicht braucht.

**Nach oben trägt allein der Rückgabewert.** Kein zweiter Kanal tritt daneben: Er nähme dem einen
das Merkmal, das ihn tragfähig macht — der Rückgabewert kommt zwangsläufig bei der Stelle an, die
weiterarbeitet —, und eine Nachricht kann ohnehin keine Zustimmung erteilen.

**Der Bericht ist einmalig, deshalb hält ein Fachagent seinen Bericht zurück, solange eine
beauftragte Recherche aussteht.** Ein Subagent gibt seinen Abschlussbericht **genau einmal** ab;
danach hat er keinen Kanal nach oben mehr, und seine freie Textausgabe erreicht den Aufrufer
nicht. Wer berichtet und das Ergebnis seiner Recherche erst danach erhält, kann es nicht mehr
verwenden und nicht mehr weitergeben — es ist ohne Fehler und ohne Spur verloren. Fällt eine
Feststellung dennoch nach dem Bericht an, bleibt allein, sie in das Dokument zu schreiben, das
ohnehin Gegenstand des Auftrags ist; ein eigenes Berichtsdokument entsteht dafür nicht.

### 4. Die drei bestehenden Anker des Umsetzungslaufs bleiben unberührt

Der neue Anker tritt **neben** `## Blockiert: Architektur-Konsultation nötig`,
`## Blockiert: CI-Fehlschlag außerhalb der zulässigen Klasse` und
`## Blockiert: main-Abgleich fehlgeschlagen`; er subsumiert keinen davon. Alle drei bezeichnen
technische Lagen mit je eigener Folge beim Aufrufer — eine Architektur-Konsultation, ein Abbruch
ohne Push —, keine Frage an Daniel. Sie behalten Wortlaut, Felder und Definitionsstelle in
`.claude/agents/developer.md`. Der Umsetzungslauf führt danach vier Anker, von denen drei
unverändert sind.

### 5. Die Feststellung je Rolle ist ein eingecheckter Messartefakt; der Wächter kodiert keine Filterliste

Was ein Lauf tatsächlich zugeteilt bekommt, wird **je Rollendatei** festgestellt, nie an einer
gemessen und auf die übrigen übertragen — die Zuteilung ist nicht für alle Rollen dieselbe.
Ergebnis ist eine eingecheckte Datei `scripts/tests/werkzeugzuteilung.json` mit je Rolle den
tatsächlich angebotenen Werkzeugen, den in der `tools:`-Zeile verlangten und nicht zugeteilten,
und den Aufrufparametern, unter denen gemessen wurde.

Der Wächter vergleicht **ausschließlich zwei Dinge, die beide im Repositorium liegen**: diesen
Artefakt und die sieben Rollendateien. Er trägt keine Kopie der Filterlisten der Laufzeit. Grund:
Eine hart kodierte Filterliste veraltet mit der nächsten Version der Laufzeit und würde dann
etwas Falsches erzwingen, das im Repositorium nicht behebbar ist. Ein veralteter Artefakt ist
umgekehrt kein CI-Fehlschlag — in CI läuft keine Laufzeit, die ihn widerlegen könnte.

Dass eine Zuteilung sich künftig ändert, fällt deshalb an einer zweiten, unabhängigen Stelle auf:
Jede Rollendatei nennt die ihr strukturell fehlenden Werkzeuge ausdrücklich und verlangt, eine
beobachtete Abweichung davon als eigene Zeile in den Bericht aufzunehmen. Zugesichert ist damit
die **Anwesenheit dieser Anweisung**, nie ihre Befolgung; das ist derselbe Zuschnitt, den
`test_laufstand_verankert.py` für den Laufstand trägt.

## Konsequenzen

- Die Rechercheur-Rolle ist tragfähig. Gemessen an einem Lauf unter den Parametern seiner echten
  Aufrufstelle sind ihm `Read`, `WebSearch`, `WebFetch`, `Skill` und `SubagentHandback` zugeteilt,
  und die Recherche selbst gelang. Es entfallen allein `AskUserQuestion` und die vier
  Aufgabenlisten-Werkzeuge. Fiele die Web-Fähigkeit bei einer späteren Feststellung doch aus, hätte
  die Rolle keine Aufgabe mehr, die sie erfüllen kann; dann ist ihr Fortbestand eine
  Produktentscheidung (Anker aus Punkt 2) und ihr Ergebnis braucht eine ADR, die ADR 0016 ablöst.
  Ein stilles Kürzen der Zusage ist in diesem Fall ausgeschlossen — es ließe eine Rolle stehen, die
  nichts mehr tut.
- Der Rechercheur hat weder `Write` noch `Bash`. Er kann an keinem Artefakt mitschreiben; seine
  Feststellung reist in seinem Bericht, und die aufrufende Sitzung trägt sie ein.
- ADR 0093 verallgemeinert im Abschnitt „Kontext" einen an zwei Proben gemessenen Werkzeugsatz zu
  „dem" Werkzeugsatz eines Subagenten. Für `Agent` ist das widerlegt. Die Aufzählung dort entfällt
  zugunsten eines Verweises auf den Messartefakt aus Punkt 5; die Entscheidung der ADR 0093 bleibt
  unberührt, weil keiner ihrer vier Punkte an der Aufzählung hängt — der Ausschluss von
  `SendMessage` als Statuskanal ist dort mit dem Eingriff in den Lauf begründet, nicht mit
  Verfügbarkeit.
- Die bestehenden `SendMessage`-Schritte in `ship-feature` (Findings-Rückspielung,
  Architektur-Ergebnis, CI-Nachbesserung) laufen alle von der Hauptsitzung zu einem Lauf der ersten
  Ebene und sind damit durch Punkt 3 gedeckt. Diese ADR ändert sie nicht.
- **Aus einer Fehlermeldung der Laufzeit ist kein Schluss auf die Ursache einer Abwesenheit zu
  ziehen.** Gemessen: `Agent` fehlt dem Umsetzungslauf mit der Begründung „disabled for this
  session, in subagents as well as here", während in **derselben** Sitzung ein anderer Lauf ein
  funktionierendes `Agent` hatte. Die Begründung ist also falsch. Der Messartefakt hält deshalb
  fest, **was angeboten wurde**, nie warum; und ein Wächter, der aus solchen Meldungen eine
  Filterlogik ableitete, kodierte eine Unwahrheit.
- Ein strukturell abwesendes Werkzeug ist auch nicht nachladbar: `ToolSearch` ist keinem der sieben
  zugeteilt. Die Aussicht, ein fehlendes Werkzeug zur Laufzeit nachzuladen, besteht nicht und
  entlastet keine Zusage.
- `docs/ai-workflow.md` beschreibt den Rückfrageweg der Agenten und zieht den vierten Anker im
  selben Pull Request nach.
- Vier Aufrufstellen weisen `run_in_background: false` an, obwohl der Vordergrund aus einer
  interaktiven Sitzung nicht erzwingbar ist. Diese ADR ändert das nicht; sie verlangt nur, dass
  der Messartefakt die Aufrufparameter der echten Aufrufstellen verwendet, damit das Gemessene
  dem Betrieb entspricht.
