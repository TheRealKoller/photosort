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

**Umfang:** über dem Richtwert von rund 100 Zeilen, weil jeder der fünf Entscheidungspunkte eine
Zusicherung samt Geltungsbereich und Verletzungsfolge trägt und diese ADR die einzige Stelle ist,
an der die beiden Klassen von Abwesenheit auseinandergehalten werden.

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

Der Anker gilt für alle sieben Rollen und ersetzt jede bisherige `AskUserQuestion`-Stelle in
ihnen. Es entsteht **ein** Weg für alle diese Fälle, nicht je Fall einer: Unterschiedlich ist nur
der Inhalt der Frage, nicht der Übergabemechanismus.

Das Blockformat samt Feldnamen ist **ausschließlich** in `.claude/skills/produktentscheidung/SKILL.md`
definiert; keine zweite Datei führt eine Kopie. Die Ankerzeile selbst darf dort stehen, wo sie
erkannt oder ausgegeben werden muss — das ist ein funktionaler Verweis, keine zweite
Formatdefinition (ADR 0040 Teil 3, unverändert angewendet).

### 3. Der Anker geht nach oben, die Antwort kommt über `SendMessage` zurück

Die aufrufende Sitzung erkennt den Anker im Rückgabewert, legt die Frage Daniel vor
(`AskUserQuestion`, in der Hauptsitzung vorhanden) und gibt die Antwort per `SendMessage` an
denselben, weiterhin offenen Lauf zurück, der danach fortfährt. Das ist derselbe Mechanismus, den
`## Blockiert: Architektur-Konsultation nötig` bereits trägt.

**Aus der zweiten Subagenten-Ebene wird weitergemeldet, nicht abgekürzt.** Der Rückgabewert eines
Rechercheurs erreicht nur den Fachagenten, der ihn gestartet hat. Trägt er den Anker, übernimmt
der Fachagent die Frage **unverändert** in seinen eigenen Bericht unter demselben Anker und hält
seinerseits an. Er beantwortet sie nicht und formt sie nicht um; sonst versandet die Frage genau
eine Ebene unter der einzigen Stelle, die sie stellen könnte.

**`SendMessage` an die Hauptsitzung als Weg nach oben ist untersagt**, auch wenn `to: "main"` für
einen Hintergrund-Subagenten eine gültige Adresse ist. Drei Gründe, jeder für sich tragend. Er
spart keinen Schritt: Der Fachagent muss ohnehin anhalten, weil er die Recherche gerade deshalb
beauftragt hat, weil er ohne ihr Ergebnis nicht weiterkommt — die Ebene wird also nicht
übersprungen, sondern nur um eine zweite Meldung ergänzt. Er legt Daniel nichts vor: Eine
Nachricht kann keine Zustimmung erteilen und trifft die Sitzung an beliebiger Stelle ihres
Ablaufs; ob sie eine ruhende Sitzung überhaupt weckt, ist nicht zugesichert. Und er wäre ein
zweiter Weg für denselben Fall, der dem einen das Merkmal nimmt, das ihn tragfähig macht: Der
Rückgabewert kommt zwangsläufig bei der Stelle an, die weiterarbeitet.

`SendMessage` bleibt damit ausschließlich der Weg **nach unten**, für die Antwort.

**Der Bericht ist einmalig, deshalb hält der Fachagent seinen Bericht zurück, solange eine
beauftragte Recherche aussteht.** Ein Subagent kann seinen Abschlussbericht **genau einmal**
abgeben; danach hat er keinen Kanal nach oben mehr, und seine freie Textausgabe erreicht den
Aufrufer nicht. Ein Fachagent, der berichtet und **erst danach** das Ergebnis seines Rechercheurs
erhält, kann eine darin enthaltene Produktentscheidung nicht mehr weitermelden — sie ist dann
endgültig verloren, ohne Fehler und ohne Spur. Er wartet das Ergebnis deshalb ab, bevor er
berichtet. Fällt eine weiterzumeldende Feststellung dennoch nach dem Bericht an, ist der einzige
verbleibende Weg, sie in das Dokument zu schreiben, das ohnehin Gegenstand des Auftrags ist; ein
eigenes Berichtsdokument entsteht dafür nicht.

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
- **Der Weg nach unten ist vor der Umsetzung zu prüfen, nicht vorauszusetzen.** In der Sitzung, in
  der diese ADR entstand, ist `SendMessage` sitzungsweit abgeschaltet — „disabled for this session,
  in subagents as well as here". Trifft das beim Umsetzen wieder zu, kann die aufrufende Sitzung
  eine Antwort nicht an den offenen Lauf zurückgeben; dann bleibt nur, den Lauf mit der Antwort im
  Auftrag neu zu starten. Betroffen sind davon auch die bestehenden `SendMessage`-Schritte in
  `ship-feature` (Findings-Rückspielung, Architektur-Ergebnis, CI-Nachbesserung) — diese ADR ändert
  sie nicht, hängt aber am selben Kanal. Die Verfügbarkeit von `SendMessage` in der Hauptsitzung
  gehört deshalb als eigener Eintrag in den Messartefakt aus Punkt 5.
- `docs/ai-workflow.md` beschreibt den Rückfrageweg der Agenten und zieht den vierten Anker im
  selben Pull Request nach.
- Vier Aufrufstellen weisen `run_in_background: false` an, obwohl der Vordergrund aus einer
  interaktiven Sitzung nicht erzwingbar ist. Diese ADR ändert das nicht; sie verlangt nur, dass
  der Messartefakt die Aufrufparameter der echten Aufrufstellen verwendet, damit das Gemessene
  dem Betrieb entspricht.
