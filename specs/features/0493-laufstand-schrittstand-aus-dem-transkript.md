# 0493 - Stand eines laufenden Umsetzungslaufs ist jederzeit ablesbar

**Status:** Accepted
**Erstellt:** 2026-09-16
**Bezug:** [Issue #493](https://github.com/TheRealKoller/photosort/issues/493)

**Umfang:** über dem Richtwert von rund 200 Zeilen, weil der Abschnitt `## Security` sieben
Zusicherungen in voller Aussage führt — was gilt, wofür, was bei Verletzung passiert — und der
Abschnitt `## Akzeptanzkriterien` je Kriterium seine Nachweisart trägt, ohne die ein Teil von
ihnen nicht prüfbar wäre.

## Ziel

Der Stand eines laufenden Umsetzungslaufs soll wieder ablesbar sein. Heute ist er es nicht: Der
Skill `laufstand` liefert während eines Laufs regelmäßig nur den Hinweis, dass kein Schrittstand
abrufbar sei — also genau in dem Fall nichts, für den es ihn gibt.

Die Ursache ist der Lesekanal, nicht der Ablauf. `TaskOutput` wird von der Arbeitsumgebung als
überholt geführt und liefert für Läufe dieser Art kein Ausgabefenster, sondern einen Verweis auf
das vollständige Sitzungstranskript im JSONL-Format. Die Formprüfung auf den Block `## Laufstand`
scheitert daran, und die Auskunft fällt in den Zweig „Kein abrufbarer Schrittstand".

Betroffen ist Daniel als einziger Beobachter der Läufe. Ein Umsetzungslauf dauert lang und meldet
sich bis zu seinem Abschlussbericht nicht von selbst. Ohne verlässliche Auskunft bleibt das Warten
blind, und ein steckengebliebener Lauf sieht genauso aus wie ein arbeitender. Der Branch-Stand
zeigt, was fertig ist, nie was gerade läuft — und damit gerade nicht das, was die Frage „steckt
der fest?" beantwortet.

## User Story

Als Beobachter eines laufenden Umsetzungslaufs möchte ich jederzeit erfahren, welcher Teilschritt
gerade bearbeitet wird und welche bereits erledigt sind, damit ich erkenne, ob der Lauf vorangeht
oder feststeckt — ohne ihn dabei zu stören.

## Akzeptanzkriterien

Jedes Kriterium trägt seine **Nachweisart**: `[statisch]` = Wächtertest über den Text,
`[Fixture]` = ausführender Prüfer gegen synthetisches JSONL, `[Lauf]` = nur an einem echten
Umsetzungslauf.

- [ ] **AK1 — Schrittstand, drei Zustände getrennt.** Die Auskunft gibt die Teilschritte des
      zuletzt **formgültigen** Blocks je Zeile mit genau einem der drei Zustände `erledigt` /
      `in Arbeit` / `offen` wieder. Sie fasst nie zusammen, zählt nie („3 von 7") und ersetzt nie
      durch einen Prozentwert. **Formgültigkeit ist eine Eigenschaft je Zeile, nicht eine
      Kardinalität über den Block:** Ein Block, dessen Zeilen sämtlich `erledigt` tragen, ist
      formgültig. Eine Kardinalitätsforderung „genau einer in Arbeit" auf Leseseite verwürfe die
      Auskunft eines fertig werdenden Laufs. `[statisch]` `[Fixture]` `[Lauf]`
- [ ] **AK2 — Kein zweiter Ort des Fortschritts.** Der Diff enthält keine Zeile in
      `.claude/agents/developer.md`, und `## Laufstand` bleibt genau einmal definiert. Der Lauf
      ändert sich nicht. `[statisch]`
- [ ] **AK3 — Kein überholter Weg.** `TaskOutput` kommt in `.claude/skills/laufstand/SKILL.md` an
      keiner Stelle mehr vor. **Reichweite ausdrücklich:** Erfüllt ist „der Pfad wird von der
      Arbeitsumgebung selbst herausgegeben, und der als überholt geführte Weg entfällt". **Nicht**
      erfüllt — und nicht erfüllbar — ist „das Dateiformat ist eine zugesagte Schnittstelle". Es
      ist ein Innenleben der Arbeitsumgebung; genau deshalb existiert AK9. `[statisch]`
- [ ] **AK4 — Die Auskunft verändert den Lauf nicht.** Kein Schreibwerkzeug genannt; `SendMessage`
      ausschließlich im Verbotsabschnitt; jeder `git`-Aufruf aus der geschlossenen Dreiermenge;
      jeder Transkriptzugriff aus einer geschlossenen Menge von Extraktionsformen mit dem Pfad als
      **einem** gequoteten Argument, und keine rohe Lesart trifft diesen Pfad. `[statisch]`
- [ ] **AK5 — Branch-Stand als benannte Gegenprobe.** In **jeder** Antwortform — Schrittstand
      vorhanden wie Ausgang A, B, C, D — steht der Commit-Stand, ausdrücklich als Commit-Stand
      bezeichnet, mit dem wörtlichen Verbot „Ein Commit-Stand wird nie als Schrittstand
      ausgegeben". `[statisch]`
- [ ] **AK6 — Alter des zuletzt gemeldeten Fortschritts.** Die Auskunft nennt die Differenz
      zwischen dem `timestamp` **genau jener Transkriptzeile**, aus der der Block stammt, und dem
      Abrufzeitpunkt. Weder der Abrufzeitpunkt allein noch das Alter des letzten Commits tritt an
      diese Stelle. Liegt kein Block vor, entfällt das Feld, statt einen Platzhalterwert zu
      tragen. `[statisch]` `[Fixture]` `[Lauf]`
- [ ] **AK7 — Vier getrennte Ausgänge, nie verschmolzen.** Die Auskunft benennt den eingetretenen
      Ausgang aus der geschlossenen Menge A/B/C/D. A und D lauten „kein Schrittstand"; B und C
      werden als **Strukturbefund** ausgesprochen, der die gebrochene Stufe und die gelesene
      Version der Arbeitsumgebung nennt. Das Wort „Strukturbefund" steht in keiner A-/D-Antwort
      und umgekehrt. Die beiden Verbotssätze bleiben wörtlich. `[statisch]` `[Fixture]`
- [ ] **AK7a — Die Schwelle für Ausgang C ist eine gemessene Zahl.** „Aus einer Datei nennenswerter
      Größe kein einziger Textblock" ist so nicht entscheidbar. Der Skilltext nennt die Schwelle
      als Zahl **geparster JSONL-Zeilen**, nicht als Bytes, und die Zahl wird vor dem Schreiben am
      Bestand gemessen, nicht erfunden. `[statisch]` `[Fixture]`
- [ ] **AK8 — Nur der Umsetzungslauf.** Entschieden an `agentType` der neben dem Transkript
      liegenden `agent-<Kennung>.meta.json`, auf **Gleichheit** mit `developer`, kein Teilstring.
      Fehlt die Datei oder trägt sie einen anderen Wert, wird verweigert. `[statisch]` `[Fixture]`
- [ ] **AK9 — Ein Umgebungswechsel fällt auf.** Ein Bruch an der Ablagestruktur äußert sich als
      Strukturbefund (B/C), der die gemessene Version nennt. Die Version wird **berichtet, nicht
      verglichen**: Im Skilltext steht keine Versionszahl als Vergleichswert und kein
      Abgleichschritt. Ein Abgleich gegen eine festgehaltene Messversion schlüge bei jeder
      Wartungsversion an und verbrauchte die Aufmerksamkeit, die der Befund braucht.
      `[statisch]` `[Fixture]`

## Datenmodell-Bezug

Nicht relevant. Keine Entität, keine Migration, keine Zeile unter `backend/`. Der Gegenstand ist
eine Anweisungsdatei und ihr Wächtertest.

## Architektur / Umsetzung

Vollständige Entscheidung in ADR
[`0114`](../decisions/0114-laufstand-aus-dem-transkript-ueber-einen-gelieferten-pfad.md) — vor der
Umsetzung zu lesen. ADR [`0093`](../decisions/0093-laufstand-in-der-ausgabe-des-laufs-gelesen-nicht-erfragt.md)
gilt in seinen Punkten 1, 2, 3 und 5 unverändert weiter; nur die Begründung seines Punktes 4 fällt.

**Der Lauf selbst ändert sich nicht** (AK2): Der Block `## Laufstand` bleibt der einzige Ort des
Fortschritts, `.claude/agents/developer.md` bleibt unberührt.

### Der neue Leseweg

1. `ListAgents` — läuft ein Lauf, unter welcher Kennung (unverändert).
2. **Der Transkriptpfad wird entgegengenommen, nie gebildet.** Weg A: der Wert `output_file` aus
   dem Ergebnis des Agent-Starts; er ist ein Symlink aufs Transkript. Weg B, nur wenn A nicht
   vorliegt: Suche über die Kennung als Schlüssel mit **genau einem** geforderten Treffer.
   Scheitern beide, gibt es keinen Schrittstand — ein Pfad wird nie geraten.
   Am Bestand belegt (2026-09-16): Für **eine** Sitzung tragen die beiden beteiligten Bäume
   **verschiedene** Projekt-Kennungen — die tmp-Seite folgt dem Arbeitsverzeichnis der rufenden
   Sitzung, die projects-Seite dem des Laufs. Ein selbst gebildeter Slug trifft im Worktree-Fall
   daneben.
3. **Gezielte Extraktion, nie rohes Lesen.** Aus den **Assistenz**-Zeilen die Textblöcke, daraus
   das **letzte** formgültige Vorkommen von `## Laufstand` **am Zeilenanfang**, und der
   `timestamp` eben jener Zeile als Alter (AK6). Die Datei erreicht Megabytes; ein rohes Lesen
   macht die Sitzung unbrauchbar, die die Auskunft geben soll.
   Beide Einschränkungen — Assistenz-Zeilen und Zeilenanfang — sind tragend, nicht kosmetisch: Ein
   Lauf, der an den Dateien dieses Ablaufs arbeitet, hat den Anker vielfach in empfangenen
   Werkzeugergebnissen und in Erwähnungen im Fließtext stehen, und zwar regelmäßig **ohne einen
   einzigen** eigenen Block. Ohne beide Einschränkungen greift die Extraktion gerade bei dieser
   Klasse von Lauf am gründlichsten daneben.
4. **Der Lauftyp kommt aus der `meta.json`** neben dem Transkript (AK8).
5. Die git-Messung über den Arbeitsort bleibt unverändert und steht weiter in **jeder** Auskunft,
   ausdrücklich als Commit-Stand bezeichnet (AK5) — sie ist die aus dem Transkript heraus nicht
   fälschbare Gegenprobe.

### Vier getrennte Ausgänge (AK7 und AK9)

| Ausgang | Lage | Antwort |
|---|---|---|
| A | weder Weg A noch Weg B liefert einen Pfad | kein Schrittstand |
| B | Pfad da, Ziel fehlt/unauflösbar/außerhalb des Transkriptbaums | **Strukturbefund** |
| C | Datei da, aber keine Zeile parst, oder kein Textblock oberhalb der Zeilenschwelle | **Strukturbefund** |
| D | extrahiert, aber kein formgültiger Block | kein Schrittstand |

Ausgang C ist der Trennschnitt, der AK9 trägt: Ein laufender Umsetzungslauf erzeugt stets Text.
Nichts zu finden ist deshalb keine Aussage über den Lauf, sondern über die Extraktion. Ohne diese
Stufe sähe ein Wechsel der Arbeitsumgebung exakt aus wie ein Lauf, der noch nichts gemeldet hat.

### Betroffene Dateien

| Datei | Änderung |
|---|---|
| `specs/decisions/0114-….md` | liegt mit dieser Spec vor |
| `specs/decisions/0093-….md` | **nur die Kopfzeile** `**Teilweise abgelöst:**` (Punkt 4, Begründung) |
| `.claude/skills/laufstand/SKILL.md` | Schritt 2 ersetzt; Schritt 5 um Alter, Version und Strukturbefund erweitert; `## Kein abrufbarer Schrittstand` auf vier Ausgänge; M-S2…M-S5 fortgeschrieben, **M-S6 neu**; `**Umfang:**`-Zeile von fünf auf sechs Auflagen |
| `scripts/tests/test_laufstand_verankert.py` | `QUELLE_FENSTER` und die Reihenfolgezusage nachziehen; Fallsätze auf vier Ausgänge; Auflagenmenge um M-S6; neuer ausführender Fixture-Prüfer |
| `specs/architecture/0003-securitykonzept.md` | mit dieser Spec bereits vorgenommen |
| `specs/architecture/0002-testkonzept.md` | mit dieser Spec bereits vorgenommen |

**Nicht betroffen:** `.claude/agents/developer.md` (AK2), `docs/architecture.md`, `docs/setup.md`,
`docs/ai-workflow.md` (gemessen: nennt weder `TaskOutput` noch den Lesekanal), `ship-feature`,
`github-access`.

Spec [`0449`](./0449-laufstand-auf-abruf.md) wird als `Implemented` **nicht nachbearbeitet**; diese
Spec hebt ihre AK4 (Leseweg `TaskOutput`) und die Fenster-Prämisse ihrer AK5 auf und nennt das
hier.

### Reihenfolge

Testgetrieben bindend — Schritt 2 muss rot sein, bevor 3 anfängt:

1. ADR 0093 die Kopfzeile `**Teilweise abgelöst:**` geben.
2. Wächtertest zuerst: `QUELLE_FENSTER`, Reihenfolgezusage, vier Ausgänge, M-S6, Fixture-Prüfer.
3. Skill Schritt 2 und der Pfad-Abschnitt.
4. Skill: vier Ausgänge und die erweiterte Antwortform (Alter, Version, Weg-A/B-Angabe).
5. Skill: M-S6 ergänzen, M-S2…M-S5 nachziehen, Umfangssatz.
6. Gesamtlauf: `./scripts/check.sh` und `pytest` im Verzeichnis `scripts/`.
7. **Verifikationslauf im selben Lauf:** Sobald der Skilltext steht, wendet die Hauptsession das
   neue Verfahren rein lesend auf **genau diesen noch laufenden** Agenten an. Das Ergebnis
   (gefundener Block, gemeldetes Alter, eingetretener Ausgang, gemessene Version) gehört als
   Messung mit Zahlen in den PR-Body, nicht als Behauptung „funktioniert".

## UI/UX

Nicht relevant. Die Story berührt ausschließlich Anweisungsdateien unter `.claude/` und Dokumente
unter `specs/`; es entsteht keine sichtbare Oberfläche, keine Zeile unter `frontend/`, und der
Issue-Body trägt keinen `## Design`-Abschnitt. Die Auskunft erscheint als Chat-Antwort.

## Security

Sicherheitsrelevant, kein Blocker. Kein Anwendungscode, kein Endpunkt, kein Datenmodell, kein
Secret des Produkts, keine Änderung an Authentifizierung oder an der Sichtbarkeit von Daten
zwischen den beiden Nutzern. Betroffen ist allein das Asset „Integrität des KI-gesteuerten
Entwicklungsprozesses". Neu ist eine **Quelle**, nicht ein Recht: Der Ablauf liest erstmals ein
Artefakt außerhalb des Repositories und außerhalb seiner Arbeitsbäume.

Die Exposition bewegt sich dabei in beide Richtungen, und nur so ist die Aussage tragfähig. **Je
Abruf sinkt sie:** Eine geschlossene Extraktion liefert Assistenz-Textblöcke und daraus den
letzten formgültigen Block, statt ein Fenster beliebigen Inhalts einzulesen. **Erreichbare Menge
und Lebensdauer steigen:** Das Ausgabefenster war endlich und flüchtig, das Transkript ist
vollständig und bleibt (gemessen 2026-09-16: 55 Projektverzeichnisse, Einträge ab Juli, keine
Bereinigung durch dieses Projekt), und es enthält auch die Werkzeugergebnisse, die der Lauf
empfangen hat. Die Auflagen der Spec 0449 gelten unverändert weiter; die folgenden treten daneben.

- **S1 — Der Transkriptpfad wird entgegengenommen und an die Kennung des Laufs gebunden, nicht an
  seine Wurzel.** Nach `readlink -f` wird am aufgelösten Ziel geprüft: absolut, unterhalb von
  `~/.claude/projects/`, in einem Verzeichnis `subagents`, Basisname **exakt**
  `agent-<Kennung>.jsonl` mit der Kennung, die `ListAgents` in diesem Abruf nennt, daneben
  `agent-<Kennung>.meta.json` mit `agentType == "developer"` bei Gleichheit. Die Wurzelprüfung
  allein trägt nachweislich nicht: Unter derselben Wurzel liegen fremde Projekte und das
  Gedächtnisverzeichnis der Sitzung. Tragend ist die Kennung — von der Sitzung selbst bezogen, von
  außen nicht beschreibbar, und ein fremdes Transkript kann sie nicht führen. Fehlermodell ist die
  Wahl des falschen Ziels (Härtungsregel 4.2), hier mit dem Zusatz, dass das falsche Ziel Text
  eines fremden Projekts in diesen Kontext trüge.
- **S2 — Zwei Pfadklassen, zwei Wurzeln, keine gegenseitige Freigabe.** Der über
  `git worktree list --porcelain` **gemessene** Arbeitsort fällt unter M-S2 (Wurzel:
  Haupt-Checkout, drei `git`-Literale), der **entgegengenommene** Transkriptpfad unter M-S6
  (Wurzel: Transkriptbaum, lesende Extraktionsformen). Beide Wurzeln enthalten ein Verzeichnis
  `.claude` — eine auf „irgendwo unter `.claude`" verkürzte Prüfung bestünde beide Klassen. Jede
  Auflage nennt ihre Wurzel als Literal und die andere Klasse namentlich; geprüft wird je
  Verwendungsstelle. **Untersagte Alternative: M-S2 aufweichen, damit der Transkriptpfad
  durchkommt** — M-S2s Wurzelprüfung scheitert an ihm zwangsläufig, und die Lockerung nähme dem
  git-Pfad still seine Wurzel, ohne dass ein Wächter das sieht.
- **S3 — Die Extraktion ist selektiv, und die Selektivität ist die Schutzwirkung.** Gelesen werden
  ausschließlich die Textblöcke der **Assistenz**-Zeilen, nie `toolUseResult`, nie Zeilen der
  Nutzer-Rolle. Das Transkript trägt die **empfangenen** Werkzeugergebnisse des Laufs, also Text,
  den der Lauf nie selbst verfasst hat; ein lax geschriebener Ausdruck zöge ihn mit herein. Anders
  als die Verhaltensauflage M-S3 ist das am Extraktionsausdruck prüfbar. M-S3 bleibt daneben scharf
  und gilt ausdrücklich **auch innerhalb** des Blocks: Die Teilschritt-Beschreibungen sind
  Freitext, überleben die Formprüfung und werden wörtlich in den Chat wiedergegeben. **Und der
  Anker zählt nur am Zeilenanfang** — eine Erwähnung im Fließtext („der Block `## Laufstand`") ist
  kein Kandidat.
- **S4 — Die Datei wird nie als Ganzes gelesen, und das ist eine Secrets-Auflage, nicht nur eine
  Kontextregel.** Ein Transkript zeichnet jede Werkzeugantwort auf; liest ein Lauf einmal `.env`
  oder gibt er die Umgebung aus, steht der Wert dort im Klartext. Dass der Bestand heute keinen
  echten Secret-Wert trägt, ist eine Momentaufnahme, keine Eigenschaft — der Weg dorthin ist offen
  und am Bestand belegt. Rohes Lesen zöge beliebig viel Empfangenes in den **persistenten**
  Hauptsession-Kontext, der über `ship-feature` GitHub-Schreibzugriff hat. Eine unvollständige
  letzte Zeile — das Transkript wird während des Laufs angehängt — wird verworfen, nie repariert:
  Ein halb gelesener Block zeigte einen laufenden Teilschritt als erledigt.
- **S5 — Weg B sucht begrenzt, mit geprüftem Schlüssel und Kardinalität eins.** Der Suchraum ist
  `~/.claude/projects/`, nicht `~` und nicht `/`, und folgt keinem Symlink aus dem Baum heraus.
  Die Kennung wird **vor** ihrer Verwendung in einem Suchmuster gegen ihre Form geprüft. Gefordert
  ist genau ein Treffer auf einen Basisnamen der Form `agent-<Kennung>.jsonl`; damit ist ein
  blindes Glob auf eine Dateiendung strukturell ausgeschlossen. Null Treffer ist Ausgang A.
  **Untersagte Alternative: mehr als einen Treffer über „der jüngste gewinnt" oder „bester
  Treffer" auflösen.**
- **S6 — Wiedergegeben wird eine geschlossene Menge aus sechs Bestandteilen.** Erlaubt sind: der
  formgültige Laufstand-Block, die git-Messung, der `timestamp` seiner Zeile, das `version`-Feld
  der Arbeitsumgebung, der Name der Stufe eines Strukturbefunds und die Herkunftsangabe des
  Auszugs (aufgelöster Pfad, Kennung, benutzter Weg). Ohne diese Aufzählung kollidierten AK9 und
  M-S5, und eine der beiden Zusagen verlöre still. Alles übrige bleibt draußen, insbesondere jeder
  Ausschnitt der Werkzeugergebnisse des Laufs.
- **S7 — Der garantiert vorhandene Anker.** M-S4 gilt unverändert, wird aber zwingender: Der Lauf
  liest zu Beginn `.claude/agents/developer.md`, deren Text steht damit in **jedem** Transkript
  eines Umsetzungslaufs. Hinzu kommt eine Lage, die das Ausgabefenster nicht kannte: Der Lauf kann
  seinen Abschlussbericht bereits geschrieben haben, während `ListAgents` ihn noch als laufend
  führt. Übergabepunkt bleibt allein der Rückgabewert des Laufs. **Untersagte Alternative: aus dem
  Transkript einen Abschluss ableiten und `ship-feature` daraus anstoßen.**

**Ausdrücklich geprüft und ohne Befund.** Der Skill behält „kein GitHub-Zugriff"; die Auskunft
bleibt rein lesend; es entsteht keine Statusdatei.

## Teststrategie

Keine neue Testebene, kein neues Framework, kein neues CI-Gate. Der Gegenstand ist Markdown, das
ein Modell zur Laufzeit deutet — mit **einer neuen Ausnahme**: Das Extraktionskommando ist ein
Befehlsliteral und damit ausführbar. Daraus drei Prüfebenen:

1. **Statische Verankerung** (`scripts/tests/test_laufstand_verankert.py`, bestehend, wird
   nachgezogen): Whitelist-Gleichheit für die `git`-Formen **und neu** für die Extraktionsformen;
   die vier Ausgänge als geschlossene Menge mit Kopf je Zeile; die Auflagen M-S1…M-S6 auf
   Kennungsgleichheit; Abwesenheit von `TaskOutput` und jeder Versionszahl; Reihenfolge
   `ListAgents` → Pfadbestimmung → Extraktion; Weg A vor Weg B mit „genau ein Treffer" wörtlich.
2. **Ausführender Prüfer gegen Fixtures** (neu, Testkonzept Punkt 12): Das Extraktionsliteral wird
   **aus der Skill-Datei gelesen und ausgeführt**, mit dem Pfad-Platzhalter auf ein im Test
   erzeugtes JSONL. Kein Nachbau in Python — der wäre eine zweite, driftende Quelle der Wahrheit.
   Geprüft wird je Ausgang, nicht nur der Erfolgsfall.
3. **Verifikationslauf** am 0493-Umsetzungslauf selbst (siehe Reihenfolge, Schritt 7).

**Edge Cases der Fixture-Ebene**, jeder einzeln: zwei formgültige Blöcke → der spätere gewinnt,
Alter aus dessen Zeile; letzter Block formungültig, früherer formgültig → der frühere gewinnt;
Block mit ausschließlich `erledigt`-Zeilen → formgültig; Anker nur in einem Werkzeugergebnis →
zählt nicht; Anker im eingezäunten Codeblock innerhalb des eigenen Textes → zählt nicht (während
der Umsetzung dieser Spec der Regelfall); Anker im Fließtext erwähnt statt am Zeilenanfang →
zählt nicht; Zeilen ohne `type`/`timestamp` → tragen nicht bei; keine
Zeile parst bzw. kein Textblock über der Schwelle → Ausgang C, darunter → Ausgang D; `meta.json`
fehlt oder trägt einen anderen Typ → Verweigerung; **Maskierung:** Eine Extraktionsform, die
Zeilenumbrüche maskiert, macht die Formprüfung auf Zustandszeilen still unmöglich — genau die
Fehlerklasse, die diese Spec behebt.

**Coverage-Gate unberührt:** keine Zeile unter `backend/`. Die neuen Prüfer laufen im Job
`demo-scripts` mit blankem `pytest`. Berührt der Umsetzungslauf trotzdem `backend/`, ist **das**
der Befund.

**Werkzeugverfügbarkeit:** Der ausführende Prüfer braucht `jq` im Job `demo-scripts`. Fehlt es,
wird der Prüfer **rot statt übersprungen**. Stellt sich das bei der Umsetzung heraus, ist der
Rückfall die reine Formprüfung der Extraktionsliterale, und der Verlust gehört als benannte Lücke
ins Testkonzept — nicht stillschweigend.

## Entscheidungen

- `architect` konsultiert (Schritt 1): ADR 0114 angelegt; Leseweg, Wegordnung A/B, vier Ausgänge.
- `ux-ui-designer` nicht konsultiert (Schritt 2): Die Story berührt ausschließlich Anweisungs- und
  Spec-Dateien; es gibt keine Stelle, an der etwas angezeigt oder eingegeben wird, keine
  Frontend-Komponente, und der Issue-Body trägt keinen `## Design`-Abschnitt.
- `test-engineer` konsultiert (Schritt 3): Nachweisarten je AK, AK1 gegen eine falsche
  Kardinalitätsforderung geschärft, AK7a ergänzt, Testkonzept um Punkt 12 erweitert.
- `security-engineer` konsultiert (Schritt 3): S1–S7; die Wurzelprüfung allein trägt nicht, die
  Bindung an die Kennung ist tragend; M-S2/M-S6 als zwei Klassen mit getrennten Wurzeln.
- **AK10 zurückgestellt** (siehe `## Out of Scope`).
- Der Verifikationslauf wandert von „erster Lauf nach dem Merge" auf „während der Umsetzung
  selbst": Der Lauf, der diese Spec umsetzt, ist ein Umsetzungslauf und damit rein lesend
  beobachtbar.

## Offene Fragen

Keine offenen Fragen an den Stakeholder. Die einzige Frage mit Produktcharakter — der Zuschnitt
von AK10 — ist im Issue-Body bereits vorab entschieden („darf als eigener Schritt zurückgestellt
werden").

## Out of Scope

- **AK10 des Issues — die mitlaufende Fortschrittsanzeige.** Das Issue erlaubt die Zurückstellung
  ausdrücklich. Gründe: Es wird kein Bauteil geteilt (der Leseweg ist eine Anweisung, kein
  Codemodul); eine Dauerleitung schöbe Transkriptinhalt **unaufgefordert** in den Kontext und
  braucht damit eine eigene Abwägung statt einer mitgenommenen; ein dauerhaft lesender Prozess
  braucht Lebensdauergrenze und Ausschalter als neue Zusagen; und die Verifikation von AK1–AK9
  wäre nicht mehr zuordenbar, wenn zwei unbewiesene Dinge zugleich am selben Lauf hängen.
  Folge-Issue nach dem Merge.
- Jede Änderung an `.claude/agents/developer.md` (AK2).
- Eine Bereinigung oder Verwaltung der Transkript-Ablage durch dieses Projekt.
- Ein Wächtertest über `~/.claude/**`: In CI existiert das Verzeichnis nicht, und eine Aussage über
  einen vergangenen Lauf sagt über den nächsten nichts.
