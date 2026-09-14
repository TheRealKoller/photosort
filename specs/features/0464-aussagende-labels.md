# 0464 - Nur noch Labels, die etwas aussagen

**Status:** Implemented ([PR #475](https://github.com/TheRealKoller/photosort/pull/475))
**Erstellt:** 2026-09-14
**Bezug:** [GitHub-Issue #464](https://github.com/TheRealKoller/photosort/issues/464)

**Umfang:** über dem Richtwert von rund 200 Zeilen, weil der Wächtertest seine drei Prüfarten
einzeln begründen muss — die drei entfallenden Namen sind nicht gleich scannbar, und eine
gemeinsame Regel für alle drei wäre entweder leer oder am Bestand dauerhaft rot.

## Ziel

Beim Erfassen eines neuen Issues wird heute ein Typ-Label vergeben, das keine Information trägt:
Jedes Issue beginnt als Idee, `idee` sagt also nichts aus, was nicht ohnehin für alle gilt.
Unterscheidungskraft hat allein `bug` — „hier ist etwas kaputt" gegenüber „hier soll etwas Neues
entstehen".

Dazu kommt eine Unstimmigkeit zwischen den beiden Wegen, auf denen ein Issue entsteht: Über die
Erfassung im Chat bekommt eine Idee das Label `idee`, über die Vorlage auf GitHub bekommt
dieselbe Sache `feature` und `needs-spec`. Dasselbe Anliegen trägt damit je nach Eingangskanal
unterschiedliche Etiketten, und keines davon wird später ausgewertet — weder steuert es einen
Ablauf noch wird danach gefiltert. Den Bearbeitungsstand, den `needs-spec` andeutet, führt das
Board bereits als Status.

Der Nutzen des Aufräumens ist dauerhaft und klein: Ein Label am Issue bedeutet danach ausnahmslos
etwas, und beim Erfassen entfällt eine Einordnung, die folgenlos bleibt.

## User Story

Als Daniel möchte ich, dass ein Label an einem Issue ausnahmslos eine Aussage trägt, die nicht
ohnehin für jedes Issue gilt, damit ich der Labelliste ansehen kann, was ein Issue von anderen
unterscheidet, und beim Erfassen keine Entscheidung treffen muss, die niemand auswertet.

## Akzeptanzkriterien

- [ ] Der Anlege-Vorgang übergibt genau dann ein Typ-Label, wenn das Issue einen Defekt meldet —
      und dann genau `bug`. In jedem anderen Fall wird kein Typ-Label übergeben (auch kein leeres
      Labelfeld).
- [ ] Das gilt für beide Eingangswege in ihrer jeweiligen Form: die Chat-Erfassung über `capture`
      → `issue-anlegen` (auf `gh`- wie auf `mcp`-Weg) und die Vorlagen unter
      `.github/ISSUE_TEMPLATE/`. Nach der Änderung führt dort genau **eine** Datei eine
      `labels:`-Angabe, `bug_report.yml` mit Wert `bug`.
- [ ] *(Review-Kriterium, kein Test.)* `capture` kennt keinen eigenen Schritt zur Typbestimmung
      mehr; die einzige verbleibende Typfrage ist „ist etwas kaputt?" und steht im Anlege-Schritt.
      Kein Schrittnummern-Verweis im Skill zeigt ins Leere.
- [ ] *(Messung, kein Test.)* Die Labels `idee`, `feature` und `needs-spec` existieren nach dem
      manuellen Schritt auf GitHub nicht mehr. Beleg: Ausgabe einer Label-Auflistung vor und nach
      dem Löschen, als Messung im PR-Body ausgewiesen.
- [ ] *(Messung.)* Übrig bleiben genau die Labels, die eine eigene Aussage tragen: `bug`, die
      `bereich:*`-Labels und `approved-for-agent`.
- [ ] Im Suchraum (alles aus `git ls-files` außer `specs/**` und der Wächterdatei) steht keiner
      der drei Namen mehr — weder als freies Wort (`needs-spec`), noch als kleingeschriebenes Wort
      mit Wortgrenze (`idee`, einzige Ausnahme: das Modell-Vokabular
      `backend/src/photosort/assets/label_embedder_tokenizer.json`), noch als Wert in einem
      Label-Konstrukt (`labels:`-Angabe in **jeder** von YAML akzeptierten Form; Argument hinter
      `--label`/`--add-label`/`--remove-label`, normalisiert und an `|` sowie `,` zerlegt,
      fallunabhängig verglichen).
- [ ] `specs/**` liegt nachweislich **außerhalb** des Suchraums — der Wächter sichert das als
      eigene Assertion zu, damit kein Textscan abgeschlossene Dokumente zum Umschreiben zwingt.

## Datenmodell-Bezug

Keiner. Der Labelraum ist prozess-internes Metadatum auf GitHub, keine Entität der Anwendung;
`docs/architecture.md` ist nicht berührt.

## Architektur / Umsetzung

**Gewählter Ansatz.** Rein anweisungsseitige Änderung — kein Anwendungscode, kein Datenmodell,
keine Abhängigkeit. Welche Klassen der Labelraum führen darf, ist als ADR
[`0101`](../decisions/0101-ein-label-traegt-eine-unterscheidung.md) festgehalten. Der Label-Wert
selbst bleibt Literal an **einem** Ort (Operationskatalog `github-access`); Ablauf-Skills nennen
die Bedingung („ist etwas kaputt"), nicht den Wert.

**Betroffene Dateien.**

| Datei | Änderung |
|---|---|
| `.github/ISSUE_TEMPLATE/feature_request.yml` | Zeile 3 (`labels: ["feature", "needs-spec"]`) ersatzlos entfernen. Kein leeres `labels: []` — eine leere Liste ist eine Vergabe-Aussage, die es nicht mehr gibt. |
| `.github/ISSUE_TEMPLATE/bug_report.yml` | unverändert (`labels: ["bug"]`). |
| `.claude/skills/github-access/SKILL.md`, `issue-anlegen` | `gh`-Block wird zweizeilig: der Aufruf ohne Schalter und, kommentarmarkiert, derselbe Aufruf mit **genau einem** zusätzlichen `--label bug`. Dazu ein Satz, der die Bedingung trägt: Das Label wird genau dann gesetzt, wenn das Issue einen Defekt meldet; sonst entfällt der Schalter ersatzlos. Die `mcp`-Zeile sagt dieselbe Bedingung und dass die Label-Liste im Nicht-Defektfall **nicht** übergeben wird. |
| `.claude/skills/github-access/SKILL.md`, `issue-bereich-setzen` | In „**Auf dem `mcp`-Weg gehören `idee`/`bug` deshalb mit in den Aufruf**, sonst fallen sie still weg" fällt `idee` weg. Die Zusicherung bleibt in voller Aussage stehen — ihr Gegenstand ist die vollständige Menge, nicht die Aufzählung. Der `approved-for-agent`-Absatz darunter bleibt unberührt. |
| `.claude/skills/refinement/SKILL.md`, „Bereich vergeben" | Pfad „Selbst angelegtes Issue": Der Neuanlage-Pfad kennt jetzt entweder `bug` oder **gar kein** Label. Beide Fälle werden ausgesprochen — bei einem Defekt gehört `bug` in die Schreibmenge, sonst ist die bekannte Bestandsmenge leer, und ein Lesezugriff wird dafür weiterhin nicht nachgeholt. |
| `.claude/skills/refinement/SKILL.md`, Zeile 26 | „Schritte 2–4" → „Schritte 1–3" (Folge der Umnummerierung). |
| `.claude/skills/capture/SKILL.md` | „Schritt 1: Typ bestimmen" entfällt; die verbleibenden Schritte werden 1–4. Die Defekt-Frage wandert als eine Zeile in den Anlege-Schritt (Bedingung, kein Label-Wert). In der Bestätigung entfällt „(Typ: Bug)". Interne Schrittnummern mitziehen: Zeile 10 („Schritt 3" → „Schritt 2"), 38 und 40 („Schritt 4" → „Schritt 3"), 54 („Ist Schritt 4 fehlgeschlagen" → „Schritt 3", „Das Issue aus Schritt 3" → „Schritt 2"). |
| `scripts/tests/test_bereichsvorrat.py` | Doku-Block (Z. 22–23): Zitat `labels: ["feature", "needs-spec"]` weg, `labels: ["bug"]` bleibt, die Aussage unverändert. Namentlicher Anker (Z. ~337): `.github/ISSUE_TEMPLATE/bug_report.yml` tritt als Fall mit lebender `labels:`-Zeile hinzu; `feature_request.yml` bleibt als Anker, mit angepasster Begründung („ein Issue-Formular, das Label vergeben *kann*"). Synthetische Pfade (Z. ~652) unverändert. |
| `scripts/tests/test_entfallene_label_restlos.py` | **neu**, siehe unten. |

**Nicht angefasst.**

- `specs/decisions/0085`, `0030`, `0043`, `0057`, `0036`, `0056` — datierte Entscheidungen, die
  die Label beschreibend nennen. Ein Rückschreiben machte aus einer Entscheidung eine Behauptung
  über heute.
- `specs/architecture/0003-securitykonzept.md:220` — beschreibt `ensure_label()` eines entfallenen
  Werkzeugs und verlangt kein Label. Die drei Namen dort beschreiben zutreffend, was jener Code
  tat; sie zu ersetzen machte die Beschreibung falsch.
- `scripts/tests/test_github_zugriff_an_einer_stelle.py` und die von ihm geprüften Zeilen —
  **Auflage aus dem Security-Abschnitt**, sie stehen außerhalb des Änderungsraums dieser Story.
- `docs/**`, `README.md`, `CLAUDE.md` — nennen keines der drei Label.

**Der Wächter (`scripts/tests/test_entfallene_label_restlos.py`, Job `demo-scripts`, kein
Coverage-Gate).** Er ist **kein Wortverbot über drei Namen** — das trüge `feature` nicht
(gemessen: in 210 von 525 gelesenen Dateien legitim). Getragen wird die Zusicherung vierteilig,
jeder Teil so breit wie der Schaden reicht:

1. **`needs-spec`** — freie Wortsuche, unverankert. Am Bestand null legitime Vorkommen.
2. **`idee`** — Wortsuche mit Wortgrenze (`(?<![\w-])idee(?![\w-])`), fallunterscheidend:
   Deutsche Prosa schreibt „Idee" groß, Kleinschreibung ist die Labelform. Genau **eine**
   Fundstelle ist kein Verstoß und wird pfadgebunden ausgenommen: das Modell-Vokabular
   `backend/src/photosort/assets/label_embedder_tokenizer.json`. Der Ausschluss trägt einen
   eigenen Fall, der die **reale** Datei aus dem Suchraum liest und belegt, dass das Muster dort
   tatsächlich trifft — sonst überlebt die Ausnahme ein Ersetzen oder Umbenennen des Assets und
   deckt still die nächste echte Fundstelle.
3. **Label-Konstrukte statt Wörter** — trägt `feature` und schließt zugleich die
   Groß-/Kleinschreib-Lücke von (2). Gesucht werden die beiden Formen, in denen ein Label vergeben
   oder verlangt wird: eine `labels:`-Angabe in **jeder von YAML akzeptierten Form** (Flow-Form
   `labels: [...]` **und** Blockform mit eingerückten `- `-Zeilen) und ein Argument hinter
   `--label`/`--add-label`/`--remove-label`. Der Wert wird normalisiert (Anführungszeichen,
   Backticks, spitze Klammern weg; an `|` **und** `,` getrennt — so zerfallen `<idee|bug>` und
   `--label feature,bug` in Einzelwerte) und **fallunabhängig** gegen die drei Namen geprüft.
   Regexseitig, ohne YAML-Parser: `scripts/pyproject.toml` führt PyYAML nicht, und eine neue
   Abhängigkeit widerspräche dem Ansatz. **Die Blockform ist tragend, nicht kosmetisch:** `feature`
   zurück in die Vorlage, in Blockform geschrieben, träfe ohne sie keine der Prüfungen — (1) und
   (2) decken `feature` nach Konstruktion nicht ab.
4. **Backtick-Konstrukt** — `` `idee` ``, `` `feature` ``, `` `needs-spec` `` kleingeschrieben und
   exakt. Das ist die Form, in der Skill-Texte Labelnamen schreiben, und sie deckt den einen Weg
   ab, auf dem `feature` sonst unbewacht zurückkäme: den `mcp`-Weg in `github-access`, der Label
   in Prosa benennt und kein `--label`-Konstrukt kennt. Am Bestand außerhalb `specs/`:
   `` `feature` `` null Vorkommen, `` `idee` `` nur an den Stellen, die diese Story ohnehin ändert.

**Gegen einen geschlossenen Erlaubnis-Vorrat wird nicht geprüft.** Das erzeugte eine zweite Fassung
des Bereichsvorrats neben `test_bereichsvorrat.py` — zwei Abbilder driften — und schlüge an den
synthetischen `--add-label`-Beispielen ebendieser Nachbardatei fehl.

**Suchraum:** alles aus `git ls-files`, abzüglich `specs/**` und der Wächterdatei selbst.
Negativliste, keine Aufzählung: Genau eine Positivliste hat in diesem Repository schon einmal
`.github/ISSUE_TEMPLATE/*.yml` übersehen. Der `specs/**`-Ausschluss ist notwendig, nicht bequem —
Sicherheits- und Testkonzept nennen die entfallenden Namen beschreibend weiter, und ein Textscan
könnte lebende von historischer Nennung nicht trennen. Nicht als UTF-8 lesbare Dateien werden
übersprungen statt den Lauf abzubrechen (gemessen 2026-09-14: 545 gelistete Dateien, davon 525
gelesen, 19 übersprungen; Lesen 0,09 s, Scan 0,11 s).

**Selbstschutz** (der Erfolgsfall ist eine Abwesenheit, der Wächter startet also grün):
Mindestgröße des Suchraums (Richtwert 300); namentliche Anker, die im Suchraum liegen müssen —
`CLAUDE.md`, `.github/ISSUE_TEMPLATE/bug_report.yml`, `.claude/skills/github-access/SKILL.md`,
`.claude/skills/capture/SKILL.md`, `.claude/skills/refinement/SKILL.md`; Prüfung, dass `specs/`
**nicht** im Suchraum liegt; Selbstausschluss an den eigenen Pfad gebunden und gegen ihn geprüft.
**Die Untergrenze für das *Gesehene* wird wertgebunden zugesichert, nicht gezählt:** Unter den
gesehenen `labels:`-Angaben muss die von `bug_report.yml` mit Wert `bug` sein, unter den
Katalog-Argumenten das `bug` des `issue-anlegen`-Aufrufs. Eine Zählgrenze hätte hier null Reserve
(genau eine `labels:`-Zeile, genau drei Label-Argumente), färbte bei jeder legitimen Änderung rot
und würde dann abgesenkt, bis sie nichts mehr sagt. Dazu synthetische Gegenproben je Muster
(`--label idee`, `--label <idee|bug>`, `--label Idee`, `--label feature,bug`,
`labels: ["feature", "needs-spec"]`, dieselbe Angabe in Blockform, `needs-spec` in Prosa) und je
eine Nicht-Treffer-Probe (`Idee` als deutsches Substantiv, `specs/features/`, `fine_labels:`,
`branch_labels:`). **Mutationsprobe statt Glauben:** je Zusicherung eine echte Wiedereinführung an
einer lebenden Datei, rot gesehen, zurückgenommen — Ergebnis in den PR-Body.

**Benannt bleibende Lücke:** formloser Fließtext („das Label feature") wird von keinem der vier
Teile erfasst. Das ist zugedeckt-vs-benannt eine bewusste Entscheidung für benannt.

**Nicht im Repositorium: das Löschen auf GitHub.** Welche Label im Repository existieren, ist
Zustand einer fremden Oberfläche; kein Test dieses Repositoriums erreicht ihn, und weder
`developer` noch der Orchestrator haben dafür eine Katalog-Operation. Ein **benannter manueller
Schritt Daniels**, ausgeführt **nach** dem Merge — solange die Vorlage das Label noch vergibt,
entstünde es neu:

```bash
gh label delete idee       --repo TheRealKoller/photosort --yes
gh label delete feature    --repo TheRealKoller/photosort --yes
gh label delete needs-spec --repo TheRealKoller/photosort --yes
gh label list --repo TheRealKoller/photosort   # nur noch bug, bereich:*, approved-for-agent
```

Der Operationskatalog bekommt dafür **keinen** neuen Eintrag: Er führt die Zugriffe des
Entwicklungsablaufs, und jeder Eintrag nennt seine Aufrufer. Eine Repo-Administration ohne Aufrufer
wäre ein toter Eintrag.

**Reihenfolge.**

1. Wächtertest anlegen — er ist zu diesem Zeitpunkt **rot** (`--label <idee|bug>`, die
   `labels:`-Zeile der Vorlage, die Prosastelle in `refinement`).
2. Operationskatalog: `issue-anlegen`, danach `issue-bereich-setzen`. Der Katalog ist der Ort des
   Literals; alles Weitere hängt an seiner Form.
3. Issue-Vorlage `feature_request.yml`.
4. `capture` (Schritt streichen, umnummerieren), danach `refinement` (Schreibmengen-Pfad und
   Schrittnummern-Verweis) — in dieser Richtung, weil `refinement` auf `capture` verweist.
5. `test_bereichsvorrat.py`: Belegstellen und Anker nachziehen.
6. Wächtertest grün; Mutationsprobe je Zusicherung.
7. Gesamtlauf: `pytest` im Verzeichnis `scripts/`.

## Teststrategie

Ausschließlich Repo-Konsistenz (`scripts/tests/`, Job `demo-scripts`, kein Coverage-Gate). Kein
Unit-/Integrations-/E2E-Bezug — die Story fasst keine Zeile Anwendungscode an, das Coverage-Gate
bewegt sich um null. Ein neuer Wächter (Aufbau vollständig im Architektur-Abschnitt), ein
bestehender wird mitgezogen (`test_bereichsvorrat.py`).

**Zwei Zusicherungen, die nicht gefordert sind und es auch nicht werden sollen:** Der
GitHub-Labelzustand (Akzeptanzkriterien 4 und 5) ist Zustand einer fremden Oberfläche — einmal
gemessen, als Messung im PR-Body ausgewiesen, nie in einen Test gegossen. Der Wegfall der Typfrage
(Akzeptanzkriterium 3) ist LLM-interpretierter Skill-Text und bleibt Review-Kriterium; ein
Wortscan darüber wäre Formulierungspolizei.

**Testkonzept:** `specs/architecture/0002-testkonzept.md` ist bereits ergänzt — die Belegstelle der
Spec-0259-Sektion nachgezogen (das Zitat der entfallenden `labels:`-Angabe raus, die Aussage
unverändert) und eine eigene Sektion mit den fünf Regeln angelegt, die über diesen Branch hinaus
gelten.

## UI/UX

Nicht relevant — die Story berührt keine sichtbare Oberfläche. Betroffen sind Issue-Vorlagen,
Skill-Texte und ein Repo-Konsistenztest; kein Frontend-Pfad, keine Anzeige, keine Eingabe.

## Security

Sicherheitsrelevant, kein Blocker. Kein Anwendungscode, kein Endpunkt, kein Datenmodell, kein
Secret, keine Abhängigkeit, keine neue Eingabe von außen und kein Foto-/Projekt-/Auth-Datenbezug.
Betroffen ist allein das Asset „Integrität des KI-gesteuerten Entwicklungsprozesses"
([`0003-securitykonzept.md`](../architecture/0003-securitykonzept.md)). Geprüft wurde nicht die
Wahl der Labelnamen, sondern zweierlei: dass die Story den Text einer Operation anfasst, die eine
Muss-Zusicherung trägt, und dass sie den Labelraum schrumpft, in dem `approved-for-agent` lebt.

- **Die Freigabe-Zusicherung an `issue-bereich-setzen` wird nicht geschwächt — sie hing nie an der
  Aufzählung.** Tragend ist die mechanische Mengenbildung (gelesene Menge desselben Laufs, minus
  aller Namen mit dem Präfix `bereich:`, plus der vorgesehenen Werte). Sie ist labelblind; die
  namentlich genannten Label sind ihr Beispiel, nie ihr Träger. Unverändert in Kraft bleiben beide
  Schranken: der Abgleich des übergebenen Werts gegen das Vorrat-Literal und die Drift-Prüfung auf
  dem `mcp`-Weg (unmittelbar vor dem Schreiben erneut lesen, bei Abweichung nicht schreiben, Issue
  überspringen). Bei Verletzung stellte eine veraltete vollständige Menge eine zurückgezogene
  Automatisierungsfreigabe wieder her, für die laut `CLAUDE.md` der Label-Zustand zum
  Bearbeitungszeitpunkt maßgeblich ist. Erzwungen von
  `scripts/tests/test_github_zugriff_an_einer_stelle.py` (Drift-Zeile als Zeilenanfang,
  `approved-for-agent` wörtlich im Block). **Auflage an die Umsetzung:** Dieser Test und die von
  ihm geprüften Zeilen werden nicht angefasst; sie stehen außerhalb des Änderungsraums der Story.

- **Neu erreichbar ist eine leere Schreibmenge — ohne Sicherheitsfolge.** Ein Issue, das allein
  `bereich:x` trägt und dessen Bereich nach der Schärfung nicht mehr zutrifft, hinterlässt nach der
  Präfix-Subtraktion nichts; bis hierher hielt ein Typ-Label die Menge beiläufig gefüllt. Trägt das
  Issue `approved-for-agent`, ist die Menge per Konstruktion nicht leer, und beide
  Ausfallrichtungen des `mcp`-Wegs bei leerer Liste — alles entfernen (der gewollte Zielzustand)
  oder nichts tun (die Entfernung schlägt still fehl) — lassen das Freigabe-Label unberührt. Die
  zweite Richtung ist ein Korrektheitsbefund, kein Angriffspfad, und wird durch die berichtete
  tatsächlich geschriebene Menge sichtbar. Keine neue Auflage. Der Neuanlage-Pfad ohne Label ist
  davon nicht betroffen: dort kommt stets mindestens ein Bereichswert hinzu.

- **Die Issue-Freigabe-Policy verliert keinen Bezugspunkt.** `spec-writer` Schritt 0 prüft bei
  fremder Autorschaft die **Anwesenheit** von `approved-for-agent`; beide Werte stammen aus der
  Feldmenge von `issue-lesen` (`labels`, `author`), die die Story nicht anfasst. Eine gesuchte
  Anwesenheit ist gegen einen schrumpfenden Labelraum unempfindlich — empfindlich wäre allein eine
  Prüfung, die aus der **Abwesenheit** eines anderen Labels etwas ableitet. Eine solche existiert
  im lebenden Anweisungsraum nicht: die drei entfallenden Label werden dort ausschließlich gesetzt
  oder beschrieben, nie gelesen und nie gegen `approved-for-agent` abgegrenzt.

- **Das Fenster zwischen Merge und Löschung auf GitHub ist bereits geschlossen.** Bis Daniel die
  drei Label löscht, tragen Bestands-Issues sie weiter; die mechanische Mengenbildung führt sie
  ungenannt mit, was der gewollte Zielzustand ist. Verschwindet ein Label während eines Laufs,
  weicht die Menge unmittelbar vor dem Schreiben ab, und die Drift-Prüfung überspringt das Issue —
  der `mcp`-Weg legt einen unbekannten Namen still als neues Label an, und genau dieses
  Wiederauferstehen eines gelöschten Labels bleibt damit aus. Auf dem `gh`-Weg ist es strukturell
  unerreichbar, weil kein solcher Name je in einem `--add-label`/`--remove-label` steht.

- **Ausdrücklich nicht sicherheitsrelevant:** welche Label es gibt und wie sie heißen; der Wegfall
  des Schritts „Typ bestimmen" in `capture` samt Umnummerierung; das Entfernen der `labels:`-Zeile
  aus der GitHub-Vorlage (sie setzt Werte, sie liest keine); der neue Wächtertest selbst — eine
  Drift-Schranke über den Anweisungsraum, keine Sicherheitsauflage, deshalb ohne Zeile in der
  Ankerliste des Sicherheitskonzepts.

**Sicherheitskonzept:** ergänzt um einen Nachtrag am Abschnitt `issue-bereich-setzen` (neu
erreichbare leere Schreibmenge, Übergangsfenster bis zur Löschung). Keine neue Auflage, kein neuer
Eintrag in der Ankerliste.

## Entscheidungen

- **ADR 0101 angelegt.** Es entfällt nicht bloß eine Teilmenge; es entsteht ein Aufnahmekriterium
  („ein Label wird genau dann vergeben, wenn seine Aussage nicht ohnehin für jedes Issue gilt"),
  an dem der nächste Labelvorschlag gemessen wird. ADR 0085 gilt unverändert weiter und wird im
  Kopf von 0101 abgegrenzt; keine ältere ADR wird auf `Superseded` gesetzt.
- **Neuer eigener Wächtertest statt Erweiterung von `test_bereichsvorrat.py`.** Jene Datei ist
  vollständig an einen Gegenstand gebunden („der Bereichsvorrat steht an genau einer Stelle") —
  Selbstausschluss, Untergrenze und eingefrorene Erwartungsmenge gehören dazu. Ein zweiter, anders
  geformter Gegenstand mit eigener Pfadausnahme machte ihren Docstring falsch und koppelte zwei
  unabhängige Erwartungsmengen in einen Selbstschutz.
- **Vier Prüfarten statt eines Wortverbots.** Die drei Namen haben verschiedene Legitimitätsgrade:
  `needs-spec` null legitime Vorkommen, `idee` eine pfadgebundene Ausnahme, `feature` in 210 von
  525 Dateien legitim. Ein gemeinsames Wortverbot wäre am Bestand sofort rot und würde so lange
  abgeschwächt, bis es nichts mehr aussagt.
- **`ux-ui-designer` nicht konsultiert (Schritt 2):** Die Story hat keinen konkret benennbaren
  Bezug zu einer sichtbaren Oberfläche — betroffen sind Issue-Vorlagen, Skill-Texte und ein
  Repo-Konsistenztest. Der Issue-Body trägt keinen `## Design`-Abschnitt.

## Offene Fragen

Keine. Die drei Kandidaten — ob `bug` mitfällt, ob der Verlust der Label-Historie an bestehenden
Issues hinnehmbar ist, ob `capture` einen Schritt verliert oder ihn nur umformuliert — sind in den
Akzeptanzkriterien 1, 4 und 3 bereits entschieden.

## Out of Scope

- **Das Löschen der Labels auf GitHub selbst.** Benannter manueller Schritt Daniels nach dem
  Merge, Befehle im Architektur-Abschnitt.
- **Umschreiben abgeschlossener Dokumente.** Die sechs ADRs, die die Labels beschreibend nennen,
  bleiben unverändert.
- **Die Präsens-Veralterung des Abschnitts „GitHub-Project-Sync"** im Sicherheitskonzept
  (Zeilen 203–244, durchgehend Präsens über ein entfallenes Werkzeug). Eigene Aufräumarbeit mit
  eigener Begründung, kein Anhängsel dieser Story.
- **Eine Prüfung gegen einen geschlossenen Erlaubnis-Vorrat aller zulässigen Labels.**
