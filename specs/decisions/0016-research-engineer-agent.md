# 0016 - Recherche-Agent `research-engineer` mit Web-Zugriff, delegierbar von den fünf Fachagenten

**Status:** Accepted
**Datum:** 2026-08-08
**Bezug:** Wird im Rahmen der idea-sharpener-Konsultation für eine neue, noch anzulegende Feature-Spec (Meta-/Tooling-Idee, Nummer zum Zeitpunkt dieser ADR noch nicht vergeben) getroffen, analog zum Ablauf von ADR [`0014`](./0014-review-agenten-selektion-und-modellzuweisung.md).

## Kontext

Kein Agent im Projekt hat aktuell Web-Zugriff (`WebSearch`/`WebFetch`) — weder der Hauptchat-Kontext im engeren Sinne der fünf Fachagenten, noch `architect`, `security-engineer`, `test-engineer`, `ux-ui-designer` oder `requirements-engineer` selbst. Technische Entscheidungen, die von aktueller externer Information abhängen (welches lokale Modell eignet sich für Y, welche Alternativen zu `mediapipe` gibt es, aktuelle CVEs für Paket X, Doku eines externen Tools nachschlagen), beruhen bislang entweder auf dem Trainingswissen des jeweiligen Agenten oder auf Ad-hoc-Recherche im Hauptchat-Kontext (der als Claude-Code-Assistent selbst bereits `WebSearch`/`WebFetch` besitzt) — nie auf einer strukturierten, quellenbelegten Recherche, die einem Fachagenten während seiner eigenen Arbeit zur Verfügung steht.

Devil's-Advocate-Punkt aus dem Schärfungsgespräch, mit Daniel geklärt: Der Hauptchat-Kontext hat bereits direkten `WebSearch`/`WebFetch`-Zugriff, ein neuer Agent wäre für Daniels eigene Ad-hoc-Anfragen technisch nicht zwingend nötig. Daniel hat sich trotzdem bewusst für einen dedizierten Agenten entschieden ("beides": direkt aufrufbar und von den Fachagenten delegierbar) — der Mehrwert liegt nicht im Zugriff selbst, sondern in einem **strukturierten, quellenbelegten Recherche-Bericht** (Empfehlung, Quellen, offene Unsicherheiten getrennt, Quellenbewertung nach Aktualität/Vertrauenswürdigkeit/Relevanz als Kernbestandteil) statt Rohtreffern im Hauptkontext oder in einem Fachagenten-Kontext, der dafür nicht ausgelegt ist.

Kontingent-Warnung aus der `requirements-engineer`-Konsultation dieses Schärfungsgesprächs: ADR [`0014`](./0014-review-agenten-selektion-und-modellzuweisung.md) hält fest, dass Subagenten-Aufrufe ein spürbarer Verbrauchsposten von Daniels Nutzungskontingent sind. Ein delegierbarer Recherche-Agent erzeugt potenziell zusätzliche Hops (Fachagent → `research-engineer` → zurück). Das ist hier bewusst in Kauf genommen, weil es eine **neue Fähigkeit** ist (Web-Recherche existiert aktuell in keinem Fachagenten), kein Ersatz für einen bestehenden Aufruf — anders als bei ADR 0014, wo es um das Einsparen bereits bestehender, teils unnötiger Aufrufe ging.

Bestehendes Vorbild im System: `claude-code-guide` (globaler/Plugin-Agent, nicht unter `.claude/agents/`) hat bereits `Bash, Read, WebFetch, WebSearch` als Tools, ist aber inhaltlich strikt auf Fragen zu Claude Code/Agent SDK/API beschränkt — belegt, dass das Muster "Agent mit Web-Zugriff" im System bereits existiert, ohne direktes inhaltliches Vorbild für allgemeine technische Recherche zu sein.

Diese ADR ist wie [`0007`](./0007-github-repo-access-hardening.md), [`0013`](./0013-diagram-tooling-d2.md) und [`0014`](./0014-review-agenten-selektion-und-modellzuweisung.md) eine reine **Prozess-/Tooling-Entscheidung für den KI-Entwicklungsprozess selbst**, keine Änderung an PhotoSorts Technologie-Stack, Datenmodell oder externer Abhängigkeit im engeren produktiven Sinn — wird aber genau wie diese als ADR festgehalten, weil sie eine dauerhafte, projektweite Regel setzt (ein neuer Agent im festen Rollenmodell, ein neues Tool-Grant an fünf bestehende Agentendateien, eine Ergänzung der einzigen Quelle der Wahrheit für Modellzuordnung).

## Entscheidung

### 1. Neuer Agent: `research-engineer`

Datei `.claude/agents/research-engineer.md`, Format/Struktur analog zu den fünf bestehenden Agentendateien (Frontmatter `name`/`description`/`tools`, Abschnitte "Warum diese Rolle", nummerierte Aufgaben, "Abschlussbericht"). Name folgt der bereits etablierten `-engineer`-Konvention (`test-engineer`, `security-engineer`, `requirements-engineer`).

**Zwei Aufgaben** (kein Konzept-Dokument, kein Review-Schritt — anders als die fünf bestehenden Agenten hat `research-engineer` keine dritte, "lebende Dokument pflegen"-Rolle, da externe Recherche naturgemäß keinen projektinternen, dauerhaft gültigen Zustand hat, der gepflegt werden müsste):

1. **Direkte Ad-hoc-Recherche für Daniel** im Hauptchat (z.B. "welches lokale Modell eignet sich für Y").
2. **Delegierte Recherche für die fünf Fachagenten** während deren eigener Aufgabenbearbeitung (z.B. `architect` bei "welche Alternativen zu `mediapipe`", `security-engineer` bei "aktuelle CVEs für Paket X").

Beide Aufgaben laufen über denselben Mechanismus (Recherche → strukturierter, quellenbelegter Bericht), nur der Aufrufer unterscheidet sich — keine getrennte Logik nötig.

**Ergebnisformat (bindend für beide Aufgaben):** strukturierter Bericht mit getrennten Abschnitten für Empfehlung, Quellenliste (mit Aktualitäts-/Vertrauenswürdigkeits-/Relevanzeinschätzung je Quelle) und offene Unsicherheiten. `research-engineer` trifft **keine** Produkt- oder Architekturentscheidung selbst — er liefert die recherchierte Entscheidungsgrundlage zurück, die Entscheidung bleibt beim Aufrufer (Daniel direkt, oder dem jeweiligen Fachagenten in dessen eigener Verantwortung).

**Abgrenzung (bindend):** keine Recherche zu PhotoSort-internem Code/Verhalten — dafür haben die Fachagenten bereits `Read`/`Grep`/`Glob`. Fokus ausschließlich auf externe Informationsbeschaffung.

### 2. Tool-Ausstattung

```
tools: Read, WebSearch, WebFetch, Skill, AskUserQuestion, TaskCreate, TaskUpdate, TaskGet, TaskList
```

- **`WebSearch`/`WebFetch`**: Kern der Rolle.
- **`Read`**: bewusst eng ausgelegt — zum Lesen eines vom Aufrufer konkret referenzierten Kontext-Dokuments (z.B. eine genannte ADR, ein Spec-Abschnitt), nicht für offene, eigenständige Erkundung der Codebasis. Genau deshalb **kein** `Grep`/`Glob` — diese beiden sind die eigentlichen "im Code/in Specs herumsuchen"-Werkzeuge, ihr Fehlen macht die Abgrenzung aus Aufgabenbeschreibung Punkt 6 technisch verbindlich statt nur als Text-Anweisung.
- **Kein `Write`/`Edit`**: `research-engineer` pflegt kein eigenes lebendes Dokument (anders als die fünf Fachagenten) und schreibt nichts selbst in die Codebasis — er gibt seinen Bericht an den Aufrufer zurück, der entscheidet, was davon wo landet (Spec-Abschnitt, ADR, Chat-Antwort).
- **Kein `Bash`**: Registry-/Paket-Abfragen (z.B. PyPI-/npm-JSON-Metadaten, wie sie `architect` in ADR 0013 einmalig manuell per `npm view`/`pip download` durchgeführt hat) lassen sich über `WebFetch` gegen die öffentlichen JSON-APIs der jeweiligen Registries ebenso erledigen, ohne ein zusätzliches, generisches Shell-Werkzeug zu benötigen — kleinerer Tool-Footprint, weniger Berechtigungs-Rückfragen.
- **Kein `Agent`**: `research-engineer` ist ein Blatt im Aufrufgraphen, kein weiterer Delegations-Hop — verhindert unkontrollierte Verschachtelung (Fachagent → `research-engineer` → ein weiterer Agent → …) und hält die Kontingent-Kosten aus dem Kontext-Abschnitt oben vorhersehbar.
- **`Skill`**: konsistent mit den fünf bestehenden Agenten, u.a. relevant für die `claude-api`-Skill bei Fragen zu Claude/Anthropic-Themen.
- **`AskUserQuestion`**: für Rückfragen bei mehrdeutigem Rechercheauftrag (z.B. unklare Anforderungen: "günstig" heißt Lizenzkosten oder Rechenkosten?).
- **`TaskCreate`/`TaskUpdate`/`TaskGet`/`TaskList`**: konsistent mit den fünf bestehenden Agenten, nützlich bei mehrstufiger Recherche mit mehreren Teilfragen.

Kein `model:` im Frontmatter — konsistent mit allen bestehenden Agentendateien und ADR 0014, Teil 2 (Modellwahl passiert ausschließlich am Aufrufort, nie im Agenten selbst).

### 3. Delegationsmechanismus: `Agent`-Tool an den fünf Fachagenten ergänzen

Ist-Zustand-Prüfung: Keiner der fünf bestehenden Fachagenten (`architect`, `security-engineer`, `test-engineer`, `ux-ui-designer`, `requirements-engineer`) hat aktuell das `Agent`-Tool in seinem Frontmatter — nur `developer` hat es. Ohne dieses Tool kann keiner der fünf technisch einen Subagenten aufrufen, unabhängig davon, was seine Beschreibung sagt. Eine reine Text-Anweisung ("bei Bedarf an `research-engineer` delegieren") ohne das zugehörige Tool wäre wirkungslos.

**Entscheidung:** Alle fünf Fachagenten-Dateien bekommen `Agent` zu ihrer `tools:`-Zeile ergänzt, **ausschließlich** zum Zweck der Delegation an `research-engineer` (nicht als generelle Erlaubnis, beliebige andere Subagenten aufzurufen — das bleibt Aufgabe von `developer`/Hauptchat). Zusätzlich bekommt jede der fünf Dateien einen kurzen, wörtlich vergleichbaren Absatz (Platzierung: im jeweiligen "Warum diese Rolle"-Abschnitt oder direkt danach, analog zur bereits bestehenden AskUserQuestion-Anleitung in jeder Datei), der beschreibt: wann delegieren (externe Information fehlt/ist unsicher — Tool-/Modellvergleich, aktuelle Sicherheitsinformationen, Doku eines externen Systems), wie (`Agent`-Tool, `subagent_type: research-engineer`, `model: Standard`, siehe Abschnitt 4), und dass die fachliche Entscheidung trotzdem beim delegierenden Agenten bleibt (`research-engineer` liefert nur die Grundlage).

Kein zentraler, gemeinsam eingebundener Textbaustein — das Projekt hat kein Include-/Partial-Mechanismus für Agentendateien, jede der fünf Dateien ist bewusst eigenständig lesbar (jede beginnt bereits mit einer strukturell ähnlichen, aber nicht wörtlich geteilten Einleitung). Der neue Absatz reiht sich in dieses bestehende Muster ein, statt eine neue Abstraktionsebene einzuführen.

### 4. Modellzuweisung (Ergänzung zu ADR 0014, Teil 2)

`research-engineer` läuft **immer mit Standardmodell**, unabhängig vom Aufrufer (Hauptchat/Daniel direkt oder einer der fünf Fachagenten) und unabhängig vom Anlass. Kein Haiku-Sonderfall für diesen Agenten.

**Begründung nach dem bestehenden ADR-0014-Kriterium** ("überwiegt mechanischer Checklisten-Abgleich, bleibt Günstig vertretbar; überwiegt echtes fachliches Abwägen ohne feste Checkliste, bleibt es bei Standard"): Der Kern der Rolle — Quellenbewertung nach Aktualität, Vertrauenswürdigkeit und Relevanz (siehe Akzeptanzkriterium 4 der zugehörigen Spec) — ist per Definition kein Abgleich gegen eine bereits fixierte Liste (anders als z.B. `requirements-engineer`s Akzeptanzkriterien-Abgleich), sondern eine Einschätzung ohne festes Schema, strukturell näher an `security-engineer`s Bedrohungsmodellierung als an einer Checkliste. ADR 0014 stuft genau solches Urteilsvermögen nie herab.

Neue Zeile für die Tabelle in ADR 0014, Teil 2 (dort bei Gelegenheit der Implementierung dieser Spec nachzutragen, da ADR 0014 selbst nach Annahme unveränderlich bleibt — siehe unten):

| Aufrufer → Ziel-Agent (Zweck) | Modell | Begründung |
|---|---|---|
| Hauptchat/Daniel direkt **oder** einer der fünf Fachagenten → `research-engineer` (externe Recherche) | Standard | Quellenbewertung (Aktualität/Vertrauenswürdigkeit/Relevanz) ist Kernbestandteil der Rolle und strukturell Abwägen ohne feste Checkliste, keine Checklisten-Prüfung gegen bereits fixierte Kriterien — analog zu `security-engineer`, nie herabstufen. |

**Zum Kontingent-Einwand explizit:** Ein zusätzlicher Hop (Fachagent → `research-engineer`) erhöht die Kosten pro Recherche-Fall gegenüber "der Fachagent hätte selbst Web-Zugriff" — aber genau diese Alternative (jedem der fünf Fachagenten direkt `WebSearch`/`WebFetch` geben) wurde im Schärfungsgespräch bewusst verworfen (siehe zugehörige Spec, Abschnitt Entscheidungen), weil sie Quellenbewertung als Nebenaufgabe in fünf verschiedenen Rollenprofilen dupliziert hätte statt sie an einer Stelle konsistent zu bündeln. Diese ADR wählt bewusst die konservative statt die aggressiv kontingent-sparende Variante (kein Haiku-Rabatt für `research-engineer`) — konsistent mit der bereits in ADR 0014 gewählten und von Daniel bestätigten konservativen Grundhaltung ("im Zweifel Standard"). Eine spätere Abschwächung (z.B. Haiku für besonders einfache, rein aggregierende Rechercheanfragen) bliebe eine technische Detailentscheidung innerhalb dieser Richtung und würde keine neue ADR erzeugen, solange am Grundprinzip (Quellenbewertung nie herabgestuft) festgehalten wird — ein Wechsel dieses Grundprinzips selbst bräuchte eine neue, diese ADR ablösende ADR, analog zur entsprechenden Klausel in ADR 0014.

## Begründung

- **Eigener Agent statt Tool-Grant an alle fünf Fachagenten:** Direktes `WebSearch`/`WebFetch` an jedem der fünf Fachagenten hätte Quellenbewertung fünffach dupliziert (jeder Fachagent müsste selbst lernen, Quellen einzuordnen) statt sie an einer Stelle konsistent zu bündeln, und hätte den Tool-Footprint jedes Fachagenten unnötig vergrößert, obwohl externe Recherche für die meisten ihrer Aufrufe nicht der Regelfall ist. Ein dedizierter Agent macht die Fähigkeit explizit sichtbar und einzeln auditierbar (ein Ort, an dem alle Web-Zugriffe im Projekt stattfinden), statt sie über fünf Rollenprofile zu verstreuen.
- **`Agent`-Tool-Ergänzung an den fünf Fachagenten statt eines anderen Delegationswegs:** Das Agent-Tool ist der einzige im Projekt bereits etablierte Mechanismus für Subagenten-Aufrufe (siehe `developer.md`). Eine Alternative (z.B. der Fachagent formuliert nur eine Recherchefrage, die der Hauptchat/`developer` stellvertretend an `research-engineer` weiterleitet) hätte einen zusätzlichen Umweg über den aufrufenden Kontext erzeugt und wäre inkonsistent mit dem bestehenden Direktaufruf-Muster.
- **Kein Konzept-Dokument/keine dritte Aufgabe für `research-engineer`:** Anders als die fünf Fachagenten hat externe Recherche keinen projektinternen Dauerzustand, der als lebendes Dokument gepflegt werden müsste (es gibt kein "Recherchekonzept" analog zum Testkonzept/Sicherheitskonzept/Design-System) — jede Recherche ist für sich abgeschlossen, ihr Ergebnis lebt im jeweiligen Spec-Abschnitt/der jeweiligen ADR, nicht in einem eigenen Dokument.
- **Kein `Grep`/`Glob`/`Write`/`Edit`/`Bash`/`Agent`:** Jedes dieser Tools würde die Rolle über reine externe Informationsbeschaffung hinaus erweitern (interne Code-Suche, eigenständiges Schreiben in die Codebasis, Shell-Zugriff, weitere Delegation) — die Abgrenzung aus der zugehörigen Spec (Akzeptanzkriterium 6) wird damit technisch statt nur textuell durchgesetzt, konsistent mit dem generellen Projekt-Grundsatz, Tool-Grants so eng wie für die Aufgabe nötig zu halten.
- **Standardmodell ohne Ausnahme statt eines Haiku-Sonderfalls:** Quellenbewertung ist genau die Art von Urteilsarbeit, die ADR 0014 explizit vom Herabstufen ausnimmt. Ein Haiku-Rabatt für den einen Agenten, dessen zentraler Zweck Bewertung/Einordnung ist, widerspräche dem eigenen Kriterium dieser Tabelle unmittelbar.

## Konsequenzen

- Neue Datei `.claude/agents/research-engineer.md` wird bei Umsetzung der zugehörigen Feature-Spec angelegt (Frontmatter/Aufbau gemäß Abschnitt 1/2 dieser ADR).
- `.claude/agents/architect.md`, `security-engineer.md`, `test-engineer.md`, `ux-ui-designer.md`, `requirements-engineer.md`: `tools:`-Zeile um `Agent` ergänzt; je ein neuer, kurzer Delegations-Absatz (siehe Abschnitt 3) ergänzt.
- `specs/decisions/0014-review-agenten-selektion-und-modellzuweisung.md`: neue Tabellenzeile in Teil 2 (siehe Abschnitt 4) wird ergänzt. Das ist eine **additive Ergänzung**, keine inhaltliche Änderung einer bestehenden Zeile — verletzt damit nicht die Unveränderlichkeit einer angenommenen ADR im engeren Sinn (die bestehenden Zeilen/Entscheidungen bleiben exakt wie sie sind), ist aber dennoch als Abweichung vom Grundsatz "ADR nach Annahme unveränderlich" explizit zu vermerken: Rechtfertigung ist, dass ADR 0014 sich selbst als "die einzige Quelle der Wahrheit für Modellzuordnung" bezeichnet und damit implizit als der Ort definiert, an dem jede künftige Aufrufstelle nachgetragen wird, statt für jede neue Aufrufstelle eine eigene ADR mit einer Ein-Zeilen-Tabelle zu erzeugen. Eine inhaltliche Änderung einer *bestehenden* Zeile bliebe weiterhin ausschließlich über eine neue, ablösende ADR möglich.
- `docs/ai-workflow.md`: Abschnitt "Ein Team spezialisierter Agenten" bekommt eine neue Zeile für `research-engineer` (Verantwortung: externe Recherche, kein eigenes Konzept-Dokument, delegierbar von den anderen fünf); Abschnitt "Kosteneffiziente Agenten-Nutzung" erwähnt kurz, dass `research-engineer`-Aufrufe immer mit Standardmodell laufen. Qualifiziert für ein Update, da sich das Rollenmodell selbst ändert (`CLAUDE.md`, Abschnitt Doku-Pflege).
- `specs/README.md`: `research-engineer` hat kein eigenes Konzept-Dokument unter `specs/architecture/` — kurzer Hinweis in der Agenten-Übersicht ergänzen, damit die Abwesenheit eines Dokuments nicht wie ein Versehen wirkt.
- `.claude/agents/developer.md`, Schritt 4 (Review-Trigger-Tabelle): **keine Änderung** — `research-engineer` ist kein Review-Agent, läuft nie automatisch im `developer`-Review, ausschließlich On-Demand-Delegation. Kein neuer Trigger-Tabelleneintrag nötig.
- `specs/diagrams/workflow-overview.d2`/`.svg`: **keine zwingende Änderung** — `research-engineer` ist kein fester Schritt im linearen Ablauf (weder `idea-sharpener` noch `developer`-Review), sondern ein optionaler, ad-hoc genutzter Seitenzweig von mehreren Knoten aus. Ihn in das bestehende, bereits dichte Sequenzdiagramm einzuzeichnen, würde eher verwirren als klären (er ist kein Schritt "nach" etwas, sondern von überall aus aufrufbar). Wird bei Bedarf später per eigener ADR-Revision nachgezogen, falls sich in der Praxis zeigt, dass die fehlende Sichtbarkeit im Diagramm tatsächlich zu Verständnisproblemen führt.
- Kein Effekt auf `docs/architecture.md`/`docs/setup.md` — reine Prozess-/Tooling-Änderung, kein PhotoSort-System-/Datenmodell betroffen.
- Ein späterer Wechsel des Grundprinzips (z.B. doch Haiku für `research-engineer`, oder direkter Web-Zugriff für einzelne Fachagenten statt Delegation) bleibt architekturrelevant und braucht eine neue ADR, die diese hier als "Superseded" markiert.
