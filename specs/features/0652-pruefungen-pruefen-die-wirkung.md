# 0652 - Prüfungen prüfen die Wirkung statt den Wortlaut

**Status:** Accepted
**Erstellt:** 2026-11-16
**Bezug:** Issue [#652](https://github.com/TheRealKoller/photosort/issues/652)

## Ziel

Unter `scripts/tests` liegen rund 27.000 Zeilen in 1.129 Testfunktionen. Ein großer Teil davon prüft
nicht, was der Ablauf tut, sondern wie er es aufschreibt: Markerzeilen an fester Stelle,
Mindestlängen von Begründungen, die Abwesenheit gelöschter Namen, Abschnittstitel und
Zeilenreihenfolgen im GitHub-Katalog, die exakte Schlüsselmenge und Schrittfolge der CI-Konfiguration.
Jede inhaltlich gleichwertige Umformulierung an Skills, Agenten oder CI macht den Prüflauf dadurch
rot — Doku-Kürzen ist blockiert, und anstehende Vorhaben (Katalogaufteilung, CI-Umbau) scheitern an
ihren eigenen Wächtern.

Nach dieser Story prüfen die Wächter die Wirkung der Abläufe und Entscheidungen: eine echte
Verletzung fällt weiterhin auf und wird mit Ort und verletzter Aussage benannt, eine gleichwertige
Umformulierung bleibt grün.

## User Story

Als Entwickler von PhotoSort möchte ich, dass die Repo-Prüfungen die Wirkung der Abläufe prüfen statt
ihren Wortlaut, damit eine inhaltlich gleichwertige Textänderung an Skills, Agenten und
CI-Konfiguration nicht mehr rot wird, eine echte Verletzung aber weiterhin auffällt — und damit
Katalogaufteilung, CI-Umbau und Testordnung nicht an ihren eigenen Wächtern scheitern.

## Akzeptanzkriterien

- [ ] **Gleichwertige Umformulierung bleibt grün.** Eine Änderung, die den Wortlaut einer
      überwachten Anweisung ändert, ohne ihre Aussage zu ändern (Satzstellung, Synonym, gekürzte
      Herleitung, anderer Zeilenumbruch), macht den Prüflauf nicht rot. Belegt für mindestens drei
      überwachte Stellen: Der Pull Request nennt je Stelle einen Umformulierungsfall, der vorher rot
      war und danach grün bleibt.
- [ ] **Jede echte Verletzung bleibt rot und wird benannt.** Für jede Schutzfunktion, deren Prüfung
      entfällt oder gelockert wird, gibt es weiterhin einen Fall, der den Prüflauf rot macht und
      dabei Ort und verletzte Aussage nennt. Belegt durch je eine herbeigeführte und zurückgenommene
      Verletzung am Bestand; ein Fall, der grün bleibt, gilt als nicht abgeschlossen.
- [ ] **Bilanz statt stillem Schwund.** Jede entfernte Prüfung ist im Pull Request einzeln benannt
      mit der Aussage, die sie trug, und der Prüfung, die diese Aussage ab jetzt trägt — oder mit der
      Feststellung, dass sie keine Aussage über das Verhalten des Ablaufs trug, samt Grund. Die
      Bilanz ist gegen den Diff abgleichbar.
- [ ] **Der GitHub-Operationskatalog wird nicht mehr über seine Ablageform geprüft.** Weiterhin
      durchgesetzt: geschlossene Operationsmenge (keine fehlende, keine erfundene), genau eine
      Definitionsstelle je Operation, die Zugangswege je Operation, und jeder Verweis nennt einen
      existierenden Abschnitt. Nicht mehr durchgesetzt: Ablageort, Reihenfolge und Abschnittsnamen.
      Belegt: Werden die Operationen auf mehrere Dokumente verteilt, ohne eine Operation zu ändern,
      bleibt der Prüflauf grün; wird eine Operation entfernt, doppelt definiert oder ihr Weg
      geändert, wird er rot.
- [ ] **Die CI-Prüfungen binden an die Wirkung, nicht an den Bestand.** Geprüft bleibt: jede
      Prüfqualität (Formatierung, Lint, Typprüfung, Tests) läuft und blockiert, die Abdeckungsschwelle
      bleibt in Kraft, kein Prüfschritt ist überspringbar. Nicht mehr geprüft werden Job-Inventar,
      Schrittfolge und der Wortlaut einzelner Schritte. Belegt: Ein zusätzlicher Job, eine
      Umbenennung oder eine Umordnung macht den Prüflauf nicht rot; eine abgesenkte Schwelle, eine
      entfernte Prüfqualität oder ein überspringbar gemachter Schritt macht ihn rot.
- [ ] **Entscheidungen und Testkonvention sind nachgezogen.** Für jede Entscheidung, die eine
      geänderte Prüfung trägt, steht im Pull Request, ob ihre Zusicherung weiterhin durch eine
      Prüfung getragen wird; wo sie eine Prüfform festschreibt, die es nicht mehr gibt, ist sie
      nachgezogen oder abgelöst. Kein Dokument behauptet danach eine Prüfung, die nicht existiert.
- [ ] **Die Rolle des roten Wächtertests ist neu gefasst.** Eine eigene Entscheidung hält beide
      Grenzen fest: Eine tragende Zusicherung wird nie durch Abschwächen ihrer Prüfung grün gemacht;
      unterschieden wird zwischen einer Prüfung, die eine Aussage trägt, und einer, die nur eine Form
      festhält. Die Vorgabe im Umsetzungsablauf ist auf diese Fassung gebracht.
- [ ] **Auch die Prüfungen außerhalb von `scripts/tests` sind erfasst, soweit sie Text statt Wirkung
      prüfen.** Prüfungen im Backend und im Frontend, die eine Formulierung im Quelltext als
      Erwartungswert lesen — etwa ein Wort im Docstring einer Funktion oder einer Migration —, sind
      auf die Wirkung umgestellt: Sie prüfen, was die Stelle tut, nicht wie sie es beschreibt. Ein
      Test, der einen Satz im Kommentar festhält, ist danach kein Wächter mehr; die zugehörige
      Zusicherung ist durch eine Prüfung gedeckt, die bei ihrer Verletzung rot wird. Ausgangsstand:
      eine Wortlaut-Prüfung auf die Monotonie-Beschreibung, neun Migrationsprüfungen auf Wörter in
      Auf- und Rückweg-Docstrings, eine Prüfung auf Quelle und Datum in einem Throttle-Modul.

**Umfang:** über dem Richtwert von ~200 Zeilen, weil die Invariantentabellen je Wächterfamilie und
die Sicherheitsauflagen den Auftrag selbst tragen — sie sind die vollständige Liste dessen, was
erhalten bleibt, und jede Zeile, die hier fehlt, wäre im Umsetzungslauf eine Entscheidung ohne
Grundlage.

## Datenmodell-Bezug

Keiner: Die Story ändert weder Entitäten noch Migrationen noch die Systemarchitektur. Sie ändert
Prüfungen über dem Bestand und die Dokumentation dieser Prüfungen.

## Architektur / Umsetzung

**Entscheidung:** ADR [`0148`](../decisions/0148-der-rote-waechtertest-traegt-eine-aussage-oder-eine-form.md)
— jede Prüfung ist Aussage, Protokoll oder Form; Formprüfungen fallen oder werden auf ihre Aussage
gehoben, Wirkungsloses wird deklariert statt bewacht. Jeder umgestellte Wächter wird **eine reine
Funktion** `Bestand → Befunde`; die Fehlererkennung belegen Mutationen in **einer** Liste, nicht
Negativtests je Muster.

### Gerüst (zuerst, ohne Verhaltensänderung)

- `scripts/tests/waechter.py` (neu): `Befund(ort, invariante, text)`, `Invariante(id, satz)`,
  `Bestand` (Abbild `pfad → text`, aufgezählt über `git ls-files` — ein Verzeichnislauf fände
  `.claude/worktrees/` und damit jede Definition mehrfach) und `pruefe(bestand) -> list[Befund]`.
  Jeder Befund nennt `datei:zeile` **und** die verletzte Invariante; deren Satz steht in der
  Invariantenmenge des Wächters.
- `scripts/tests/mutationen.py` (neu): `Mutation(name, datei, alt, neu, invariante)` als
  geschlossene Liste über alle umgestellten Wächter.
- `scripts/tests/test_waechter_mutationen.py` (neu): **ein** Test über diese Liste — unmutierter
  Bestand grün; jede Mutation erzeugt mindestens einen Befund mit der deklarierten Invariante und
  einem Ort; jede Invariante eines umgestellten Wächters hat mindestens eine Mutation; jedes `alt`
  kommt im Bestand genau einmal vor (sonst mutiert der Eintrag nichts und belegt nichts).
- `scripts/tests/conftest.py`: ein Bestandsleser, von beiden Wächterfamilien genutzt.

Die Mutationsliste läuft im Speicher gegen `Bestand`, nicht gegen eine Dateikopie: kein
`tmp_path`-Repo, keine Laufzeitkosten.

### GitHub-Operationskatalog (`test_github_zugriff_an_einer_stelle.py`)

Prüfgegenstand ist der Bestand aus `.claude/**`, `docs/**` und `CLAUDE.md`. **Die Ablage ist frei:**
die Operationen dürfen auf mehrere Dokumente verteilt werden, in beliebiger Reihenfolge und unter
beliebigen Abschnittsnamen.

Eine Operation ist **definiert** durch eine Überschrift, deren Text mit ihrer ID in Backticks
beginnt (jede Ebene `##` bis `######`); ihr Block reicht bis zur nächsten Überschrift gleicher oder
höherer Ebene. Das ist die einzige verbleibende Konvention und ausdrücklich keine Ablageform: ohne
einen maschinell lesbaren Marker ist „genau eine Definitionsstelle je Operation" nicht prüfbar, und
ohne diese Prüfung ist die geschlossene Menge nicht durchsetzbar.

Erhalten und je als Invariante mit Mutation belegt:

| Invariante | Aussage |
|---|---|
| `katalog-geschlossen` | Die definierten IDs sind genau die erwarteten 21 — keine fehlt, keine kommt dazu, keine doppelt. |
| `wege-geschlossen` | Je Operation 1..n Wege aus `{mcp, gh}`, ohne Dopplung. |
| `wege-belegt` | Jeder deklarierte Weg ist im Block belegt (`mcp__github__…` bzw. eine `gh <unterbefehl>`-Zeile) **und** jeder belegte Weg ist deklariert. Das ist der Rot-Fall für „Weg geändert". |
| `wege-board` | Die vier Board-Operationen nennen genau `gh` und tragen „remote auf keinem Weg erreichbar". |
| `ziel-literal` | Jeder Block nennt `TheRealKoller` und `photosort` als Literal. |
| `lesende-grenze` | Jede lesende Operation nennt mindestens ein ausgewertetes Feld. Die exakte Feldmenge bleibt für `issue-liste-lesen` und `pr-pruefstand-lesen` (dort ist sie die Sicherheitszusage) und für `pr-pruefstand-abwarten`, dessen Grenze **leer** ist: aus dem blockierenden Aufruf gelangt nichts in Kontext oder Protokoll. |
| `verweis-abschnitt` | Jeder Verweis `Abschnitt „…"` trifft eine existierende Überschrift irgendwo im Bestand. |
| `id-verwendung` | Jede verwendete Operations-ID ist definiert; eine unbekannte ID ist ein Befund. |
| `zugriff-nur-im-katalog` | Kein `gh`-Befehl und kein `mcp__github__`-Name außerhalb einer Datei, die mindestens eine Operation definiert. `docs/` bleibt als Setup-Doku ausgenommen, Suchraum bleiben `.claude/**` und `CLAUDE.md`. |
| `messbegriffe` | Kein enumerierter Messbegriff (`gh auth status`, `CODESPACES`, `GITHUB_ACTIONS` …) — unverändert. |
| `erlaubnisstufe` | Je Skill-/Agenten-Datei genau eine Stufe, künftig als **geschlossener Wert** auf der Zeile `**GitHub-Erlaubnisstufe:**`: `schreibend`, `lesend` oder `keins`. Der Satz daneben ist frei. |

Entfallen (Bilanz im PR): Ablageort `.claude/skills/github-access/SKILL.md`, Überschriftenebene,
`mcp`-vor-`gh`-Reihenfolge, Mindestlänge 20, die exakte Feldmenge der übrigen Leseoperationen, der
„Stichproben-Audit"-Marker, Forderungen nach wortgleichen Sätzen — und **alle** Negativtests des
Moduls.

Die Stufe wird damit zur **Deklaration** (ADR 0148 Abschnitt 3): Migration in **einem** Commit über
alle Skill- und Agenten-Dateien, kein Übergangsformat mit zwei akzeptierten Schreibweisen. Deklariert
bleibt auch die Erwartungstabelle selbst — sie ist eine Entscheidung und wird bei Änderung bewusst
nachgezogen, nicht abgeleitet.

### Befehlsform der `gh`-Zeilen (bleibt, weil sie Härtungsregeln trägt)

Die Prüfungen der `gh`-Aufrufe und des CI-Wartepunkts fallen **nicht** als Form: sie setzen
Härtungsregeln durch. Sie werden von der Optionsschreibweise auf die tragende Eigenschaft gehoben.
Ein Aufruf, den der Parser nicht klassifizieren kann, ist ein Befund — kein Überspringen.

| Invariante | Aussage |
|---|---|
| `freitext-nur-als-datei` | Jede Option eines `gh`-Aufrufs, die Freitext trägt, referenziert eine Datei (`--body-file`, `-F …=@…`, `"$(cat <pfad>)"`, `"$(<pfad>)"`); Inline-Inhalt ist ein Befund. Damit bleibt Härtungsregel 4.1 (kein Freitext als Teil der Aufrufstruktur) durchgesetzt, unabhängig von der Schreibweise der Option. |
| `ziel-geschlossen` | Jeder schreibende Aufruf nennt sein Ziel selbst — über `--repo`, `-R` oder das Repo-Segment im API-Pfad —, und es ist `TheRealKoller/photosort`. Ein fremdes Ziel oder ein fehlendes Ziel ist ein Befund (Härtungsregel 4.2). |
| `board-werte` | Jeder Board-Schreibzugriff nennt genau ein Feld und einen Wert aus der Optionsmenge des Boards; Projektnummer und Owner sind geschlossene Literale. Unquotierte Werte werden gelesen, nicht übersprungen. |
| `pruefstand-blockierend` | Der Wartepunkt wartet blockierend (`--watch`), ist zeitlich begrenzt (endliches `timeout`), filtert nicht auf erforderliche Checks (kein `--required`), läuft nicht durch eine Pipe und liest die Feldauswahl als ganzen Optionswert. Die Zahlenwerte tragen nichts und dürfen sich ändern. |
| `kommentar-pfad` | Keine deklarierte Operations-ID liest Issue-Kommentare außer der benannten PR-Ausnahme, keine Auswertungsgrenze nennt ein Kommentarfeld, und kein Endpunkt- oder Feldpfad mit `/comments` steht in einer deklarierten Aufrufzeile außerhalb dieser Ausnahme. |
| `reihenfolge-ausfuehrung` | Die Ausführungsstellen von `refinement` folgen der Kette Body → Titel → Bereich → `Ready`; `Ready` ist das letzte Glied. Gelesen wird die deklarierte Operations-ID samt Wert, nicht die Satzform. |

Alle übrigen Prüfungen dieser vier Wächter entfallen: Satz- und Markerwortlaute, Zahlen, Mindestlängen,
Negativtests. Die Bilanz nennt sie einzeln (ADR 0148, AC3).

### CI (`.github/workflows/*.yml`, neu `scripts/tests/test_ci_wirkung.py`)

Gelesen werden **alle** Workflow-Dateien, nicht nur `ci.yml`: ein kleiner Blockleser (Einrückung;
`jobs:` → Job → `steps:` → `run`/`uses`/`if`/`continue-on-error`), der bei einer Form, die er nicht
versteht, **laut** scheitert statt still zu überspringen. Keine neue Abhängigkeit (kein PyYAML).

| Invariante | Aussage |
|---|---|
| `qualitaet-laeuft` | Für jede der vier Qualitäten (Formatierung, Lint, Typprüfung, Tests) gibt es mindestens einen Schritt in einem bei `pull_request` auslösenden Workflow. Erkannt wird am **Befehl**, nicht am Namen: `ruff format --check`, `prettier --check`; `ruff check`, `oxlint`; `mypy`, `tsc`; `pytest`, `vitest`. `npm run <skript>` wird **eine Stufe** über `package.json` aufgelöst. |
| `tests-je-baum` | Für jeden Baum mit Testkonfiguration im Dateibaum (`backend`, `frontend`, `scripts`, `eye`) läuft ein blockierender Schritt, dessen Arbeitsverzeichnis dieser Baum ist und der sein Testwerkzeug aufruft. Der Baum wird aus dem Repository abgeleitet, nicht in der CI aufgezählt. |
| `coverage-schwelle` | Genau eine `--cov-fail-under=<N>`-Angabe im Workflowbestand mit `N ≥ 80`, dazu `--cov=photosort`; kein `--no-cov` in Workflow oder pytest-Konfiguration und kein `addopts`, das die Schwelle unterschreitet. |
| `nicht-ueberspringbar` | Kein `if:` und kein `continue-on-error: true` an einem Qualitätsschritt oder seinem Job; im `run` dieser Schritte keine Abschwächung (`|| true`, `|| exit 0`, `set +e`, `exit 0`). |
| `pr-ausloeser` | Der Workflow, der die Qualitäten trägt, läuft bei `pull_request`. |

Entfallen: Job-Schlüsselmenge, Job-Namen, Job- und Schrittfolge, Schrittnamen, Wortlaut der
Kommandos, `-n auto`, UV-Cache-Pfad/-Schlüssel/-Position, `pytest-xdist` im dev-Extra. Zusätzliche
Jobs und umbenannte oder umgestellte Schritte bleiben grün, solange die fünf Invarianten halten.

### Wo die Wirkung nicht beobachtbar ist

Ob ein Lauf eine Skill-Anweisung befolgt, ist statisch nicht beobachtbar. Deshalb wird nicht die
Prosa geprüft, sondern ein Token, den eine andere Stelle liest — oder die Prüfung fällt. Ohne Ersatz
entfallen: die wortgleichen Zusagen in `test_werkzeugwahl_verankert.py` und
`test_laufstand_verankert.py` (etwa „Weg A steht vor Weg B", „die Auskunft nennt kein schreibendes
Werkzeug"), die Satz- und Markerwortlaute in `test_ci_warten_verankert.py`, soweit sie keine von
einem Ablauf gelesene Zeile sind, und die Sätze in `test_rollenzusagen_verankert.py`, die nur eine
Formulierung festhalten. Erhalten bleiben dort die Protokolle: Frontmatter `tools:`,
`werkzeugzuteilung.json`, die Anker `## Blockiert: …` / `## Abschlussbericht` /
`## Architektur / Umsetzung`, die geschlossenen Ergebnis- und Zahlenmengen, die ein Lauf liest.

### Prüfungen außerhalb von `scripts/tests` (AC8)

| Stelle | Heute | Danach |
|---|---|---|
| `backend/tests/test_ranking.py::TestRankingDocstrings::test_rank_photos_documents_the_restored_monotonicity` | Wort „monoton" im Docstring | Eigenschaft über ein Wertegitter: gilt `rank_position[i] < rank_position[j]`, so `rank_score[i] >= rank_score[j]` — genau die Dämpfung, die der Docstring verhindern soll, wird damit rot. |
| sechs `test_the_downgrade_docstring_*` in `test_migration_{albumentscheidung,duplikat_entscheidung,endauswahl,export,feedback_events,gewichtssaetze}.py` | Wörter („Verlust", „Entscheidung") in Auf-/Rückweg-Docstrings | entfällt. Die Aussage trägt der jeweilige Nachbarfall, der `downgrade()` **ausführt**, eine Zeile einfügt und danach Zeile bzw. Tabelle als fort nachweist. |
| `test_migration_events.py::test_the_module_documents_the_irreversible_deletion`, `test_migration_kamera_zeitversatz.py::…the_irreversible_loss_of_the_offsets` | Wörter im Modultext | entfällt ohne Ersatz: ein Wort macht eine Migration nicht umkehrbar. Keine Verhaltensaussage; die Irreversibilität steht als Kommentar und im PR. |
| `test_migration_duplikat_entscheidung.py` (DML-Scan `INSERT`/`UPDATE`/`DELETE` über den Migrationsquelltext) | Abwesenheit im Text | Wirkung: Zeilen in der Altform anlegen, `upgrade()` fahren, Zeilen unverändert zählen. |
| `test_cloud_vision_throttle.py::TestTheProviderDefaults::test_every_default_is_documented_with_its_source` | Datum `2026-09-10` und `0074` im Quelltext | entfällt: die Vollständigkeit einer Herleitung ist keine Wirkung; die Werte deckt `test_they_cover_exactly_the_selectable_providers`. |
| `test_cloud_vision_throttle.py::TestTheThrottleIsAlwaysPassedIn::test_both_factories_pull_the_process_wide_throttle_of_the_derived_provider` | Quelltext-Schnipsel beider Factories | Wirkung: Factory mit gepatchten Client-Klassen aufrufen; `client.throttle is throttle_for_provider(provider)`, und der Client-Typ folgt dem **Modell**, auch wenn `settings.landmark_provider` einen anderen Anbieter nennt. Kein Netz, kein Secret — der Bau ist offline. |

Ausdrücklich **nicht** in diesem Zuschnitt: die `*.structure.test.ts` im Frontend und die
Syntaxbaum-Wächter im Backend. Sie lesen Quelltext, aber nicht als Formulierung: sie prüfen, welche
Datei welches Feld lesen darf, und eine verletzte Zusage daran rötet keinen Verhaltenstest. Sie
bleiben (Klasse A über die Abhängigkeitsrichtung).

### Vorgehensreihenfolge

1. ADR 0148 und dieser Abschnitt (nur Doku).
2. Gerüst (`waechter.py`, `mutationen.py`, `test_waechter_mutationen.py`, Bestandsleser). Noch kein
   alter Test gelöscht.
3. Katalogwächter auf reine Funktion und Invarianten umstellen, Erlaubnisstufe auf den geschlossenen
   Wert migrieren (ein Commit über alle Skill-/Agenten-Dateien), Mutationsliste füllen, danach die
   entfallenden Zusicherungen und alle Negativtests in **einem** Commit löschen.
4. `test_ci_wirkung.py` neu; `test_backend_ci_beschleunigung.py` im selben Commit löschen;
   Mutationsliste ergänzen.
5. AC8-Fälle im Backend umstellen: sechs Docstring- und zwei Irreversibilitätsfälle löschen, die
   beiden Quelltextfälle durch Wirkungsfälle ersetzen.
6. `developer.md`, Testkonzept, ADR-0061-Kopf nachziehen.
7. Bilanz in den PR-Body: je entfallener Prüfung eine Zeile (Aussage → neuer Träger | keine Aussage,
   Grund). Abgleichbar gegen den Diff, nicht gegen diese Liste.

### Belege im PR

- **AC1:** drei Umformulierungsfälle vorher/nachher — der Stufensatz einer Skill-Datei, die
  Begründungszeile einer Operation ohne `mcp`-Weg, der Name und die Argumentfolge des Testschritts.
  Alle drei waren vorher rot, sind danach grün, ohne dass eine Invariante der Tabellen oben ausfällt.
- **AC2:** je Invariante eine Mutation in `mutationen.py`; der Lauf der Mutationsliste zeigt für jede
  den Befund mit Ort und Invariantensatz. Zusätzlich je ein herbeigeführter und zurückgenommener
  Verstoß am Bestand für die drei Invarianten, die eine Schutzfunktion ersetzen
  (`katalog-geschlossen`, `wege-belegt`, `coverage-schwelle`).
- **AC4/AC5:** Verteilung der Operationen auf zwei Dokumente bleibt grün; Entfernen, Doppeln oder
  Wechsel eines Wegs wird rot. Zusätzlicher Job, Umbenennung und Umordnung bleiben grün; gesenkte
  Schwelle, entfernte Qualität und überspringbarer Schritt werden rot.

### Abgrenzung — unverändert

- Alle Tests mit eigener Logik: `test_nummern.py`, `test_merge_main_into_branch.py`,
  `test_main_abgleich_verdrahtung.py`, `test_pr_titel_pruefung.py`, `test_produktentscheidung.py`,
  `test_dokumentnummern_eindeutig.py`, `test_verweisnummern_in_markdown.py`.
- Alle Verhaltensprüfungen der Skripte (`test_check_sh.py`, `test_format_sh.py`,
  `test_seed_opencloud_demo.py`): sie führen das Skript in einem Spielplatz aus.
- `test_signaturpruefung_je_paketsatz.py`: liest Workflow-Struktur, prüft aber eine Wirkung
  (signaturgeprüfte Installation je Paketsatz) — bleibt.
- Kein Produktcode, keine Skill-Inhalte außer der Erlaubnisstufen-Zeile, kein Kommentar wird gekürzt.

### Risiken

- **Der Blockleser ist die Schwachstelle.** GitHub-Actions-YAML kennt Anker, `<<`, Flow-Listen und
  `strategy.matrix`. Der Leser versteht nur den Block-Stil und scheitert sonst laut. Ein legitimer
  Umbau in eine unverstandene Form wird damit rot — bewusst: laut statt still, und der Nachzug ist
  ein Leser-Fall, kein Prüfungsverlust. Eine Mutation belegt, dass er scheitert.
- **Der Überschrifts-Marker bleibt eine Konvention.** Wer ihn ändert, zieht den Wächter mit. Das ist
  die eine Stelle, an der die Story eine Form behält; sie ist in der Bilanz als solche benannt.
- **Die Mutationsliste kann verwaisen.** Abgedeckt sind Invarianten, nicht Aufrufe: eine Invariante
  ohne Mutation fällt auf, eine Mutation ohne Wirkung ebenfalls (`alt` kommt nicht vor). Beides ist
  ein Fall im Gerüst-Test, kein Review-Punkt.
- **Ein großer mechanischer Commit** (Stufenwert in rund 20 Dateien). Rein textlich und zeilenweise
  prüfbar; ein Übergangsformat mit zwei akzeptierten Schreibweisen wird bewusst nicht gebaut.

## Teststrategie

Grundlage ist das Testkonzept [`0002`](../architecture/0002-testkonzept.md). Es gibt **keine neue
Testebene und kein neues Werkzeug**: die Wächter bleiben `pytest` unter `scripts/tests`, die
umgestellten Backend-Fälle laufen im bestehenden `pytest`-Lauf gegen In-Memory-SQLite. Geändert
wird die Ebene, auf der ein Wächter prüft: nicht mehr über dem Wortlaut einer Datei, sondern über
einer reinen Funktion `Bestand → Befunde`.

**Die drei Prüfklassen, entschieden am Konsumenten.** **A** — beobachtbare Wirkung: die Stelle tut
etwas, das ein Test nachrechnen kann. **B** — ein Token, den eine andere Stelle maschinell liest:
Operations-ID, `**Wege:**`, Frontmatter `tools:`, Anker `## Blockiert: …`, das geschlossene
Erlaubnisstufen-Wort. **C** — nur ein Mensch liest es. C bleibt nie als Formprüfung stehen: sie
fällt, oder ihr Träger wird A/B. Die Grenze im Beispiel: „`--cov-fail-under` ist in Kraft" ist A
(die Zahl wirkt), „`pr-pruefstand-lesen` steht im Katalog" ist B (die ID wird von einem Ablauf
gelesen), „die lesende Board-Operation begründet ihre fehlende Nachhol-Zeile" ist C und fällt —
kein Konsument, keine beobachtbare Wirkung.

| Prüfgegenstand | Ebene | Warum |
|---|---|---|
| Wächter-Entscheidung `pruefe(bestand)` | Unit, Bestand als Abbild im Speicher | deterministisch, ohne Dateisystem; prüft genau die Funktion, die auch der Wächterlauf nutzt |
| Bestandsleser (`git ls-files`) | Integration am echten Baum, **einmal** je Lauf | die einzige I/O-Stelle; ein temporärer Klon prüfte den Klon statt das Repositorium |
| Mutations- und Umformulierungsliste | Unit, je Eintrag **ein** `pytest`-Knoten (`pytest.param(..., id=…)`) | ein roter Eintrag nennt sich selbst; jeder Eintrag startet vom unveränderten Bestand |
| AC8, Migrationen | bestehende In-Memory-SQLite-Fälle, unverändert | der Gegenstand ist das Schema, nicht der Text |
| AC8, Factory | Unit mit gepatchten Client-Klassen und gepatchtem Schrittmacher | kein Netz, kein Secret; der Bau läuft offline |
| Frontend | kein Fall | die Story erzeugt keinen Text, den ein Frontend-Wächter lesen könnte |

**AC1 und AC2 bekommen je einen dauerhaften Träger; der PR-Text belegt den Vorher-Stand.** Die
Mutationsliste (`MUTATIONEN`, rot-erwartend) ist die Trägerin von AC2 — sie deckt jede Invariante
ab, nicht nur die drei im PR vorgeführten. Ergänzt wird in derselben Datei eine zweite, gleich
gebaute Liste `UMFORMIERUNGEN` (grün-erwartend): je Eintrag eine Funktion `Bestand → Bestand`. Sie
ist nötig, weil eine Umformulierung mehrere Dateien und mehrere Stellen treffen kann (Verteilung
auf zwei Dokumente, Umordnung, Umbenennung) — mit einem einzelnen `(datei, alt, neu)`-Tupel ist
das nicht ausdrückbar. Sie ist die Trägerin von AC1; der PR nennt zusätzlich die drei
Umformulierungsfälle, die am **alten** Wächter rot waren (Stufensatz einer Skill-Datei:
`**GitHub-Erlaubnisstufe:**` umformuliert; Begründungszeile einer Operation ohne `mcp`-Weg:
gekürzt unter die Mindestlänge; Testschritt: umbenannt und in der Argumentfolge getauscht).

Der zentrale Test `test_waechter_mutationen.py` prüft in **einem** Lauf, je Umformulierung und je
Mutation ein Knoten:

1. Unmutierter Bestand: `pruefe` liefert für jeden Wächter **keine** Befunde.
2. Je Umformulierung: der Bestand ist danach ein anderer, und die Befundmenge ist **gleich** der
   des unmutierten Bestands (nicht nur „leer" — sonst versteckte ein bestehender Befund sich).
3. Je Mutation: der Bestand ist danach ein anderer, und mindestens ein Befund nennt die
   deklarierte Invariante **und** einen Ort im veränderten Zeilenbereich (bei einer Löschung: die
   Zeile, an der der entfernte Block stand).
4. Jede Invariante eines umgestellten Wächters hat mindestens eine Mutation (Mengengleichheit
   `Invarianten == Mutationen.invarianten`); jedes `datei` eines Eintrags liegt im Bestand.
5. Ein `alt`, das im Bestand nicht (oder nicht genau einmal) vorkommt, ist ein **Fehlschlag des
   Eintrags** — niemals ein grüner Lauf. Bei mehrfach vorkommender Zeichenkette gehört die
   Fundstelle in den Eintrag.
6. Ein leerer Bestand ist für **jeden** Wächter rot (mindestens ein Befund); der Leser scheitert
   bei null gefundenen Dateien laut.
7. Ein Bestand mit BOM und CRLF liefert dieselben Befunde wie derselbe ohne — der Leser normalisiert
   Zeilenenden und BOM an genau einer Stelle.

**Warum die Mutationsliste keine Wortlautprüfung ist.** Die Mutation ist an den heutigen Bestand
gebunden, die Invariante nicht. Formuliert jemand die überwachte Stelle um, kann ein Eintrag
unanwendbar werden; er scheitert dann mit „Mutation greift nicht" und wird im selben PR
nachgezogen. Das ist der bewusste Preis dafür, dass die falsche Richtung (Mutation greift, Befund
bleibt aus) niemals still bleibt.

**AC3: die Bilanz hat einen mechanischen Träger.** `scripts/tests/waechter_aussagen.json` führt
zwei Listen: `aktiv` (je Invariante `modul`, `invariante`, `klasse`) und `entfernt` (je Prüfung
`pruefung` als `datei::testfunktion`, `satz`, `klasse`, `traeger`, `grund`). Der zentrale Test
prüft vier Dinge: die aktive Menge ist **gleich** der aus den Modulen gelesenen (beide Richtungen,
also fällt auch ein Modul, das mitsamt seinen Mutationseinträgen verschwindet); jede aktive Klasse
ist A oder B; jede entfernte Prüfung ist im Testbaum **nicht mehr vorhanden** (sonst behauptet die
Bilanz eine Löschung, die nicht stattfand); jede genannte Trägerin existiert als
`def test_…` im Baum, sonst steht ein `grund` da. Dazu eine Untergrenze der aktiven Aussagen,
bewusst deutlich unter dem Ist-Stand — sie fängt den Massenverlust, den kein Einzeleintrag
verrät. Was die Bilanz **nicht** kann: den GitHub-Verlauf prüfen; die Decke ist der Diff, und der
ist im PR benannt.

**Was mit den rund 148 Negativtests der Wächter geschieht.** Entschieden am Gegenstand, nicht am
Namen:

- *Fällt* jede Gegenprobe, deren einzige Eingabe ein erfundener Textschnipsel ist — die
  Musterfamilien des Katalogwächters, die Gegenproben des CI-Wächters, die „wird gemeldet"/„gilt
  nicht als Verstoß"-Familie der Formmodule. Sie lehrte, dass ein Muster matcht; die Mutation
  lehrt dasselbe am echten Bestand, mit Ort und Invariante.
- *Bleibt* jede Probe, deren Eingabe der Testgegenstand selbst ist, weil die geprüfte Funktion
  echte Verzweigungen hat: `test_nummern.py` (Rechnung, Leser, Unterbefehle),
  `test_merge_main_into_branch.py` (Konfliktzustände), `test_pr_titel_pruefung.py` (führt den
  `run:`-Block aus), `test_check_sh.py`/`test_format_sh.py`/`test_seed_opencloud_demo.py`
  (Spielplatz), `test_produktentscheidung.py` (Auswertung an einem vorgefertigten Bericht),
  `test_dokumentnummern_eindeutig.py`, `test_verweisnummern_in_markdown.py`,
  `test_signaturpruefung_je_paketsatz.py`. Dort ist die Eingabe kein Wortlaut, sondern ein Fall,
  den nur die Funktion selbst kennt (zwei gleiche Nummern, ein Konflikt, ein Titel außerhalb der
  Form).
- Die reinen Selbstschutz-Proben („der Suchraum ist nicht leer", „der Katalog hat Einträge")
  werden zu Punkt 6 der Liste oben: der leere Bestand ist eine Mutation, kein eigener Test.

**AC4 und AC5.** Die Invarianten stehen oben in den Tabellen; je Invariante gehört mindestens ein
Rot-Fall in die Mutationsliste (Punkt 4). Zwei Entscheidungen dazu: (a) Die Wege werden **je
Operation nicht auf einen festen Satz** genagelt — welche Wege eine Operation nutzt, ist eine
Entscheidung, kein prüfbarer Formwert. Rot wird „Weg geändert" über die Belegbarkeit (Invariante
`wege-belegt`): ein deklarierter Weg ohne Beleg im Block, ein belegter Weg ohne Deklaration,
ein Weg außerhalb `{mcp, gh}`, eine Dopplung oder eine Board-Operation mit `mcp`.
Damit ist die alte Zusicherung erhalten (sie pinnte ebenfalls nur die Board-Fälle) und die
Forderung „Weg geändert wird rot" erfüllt, ohne eine Änderung an allen 21 Einträgen zu erzwingen.
(b) Ein Abschnittsverweis wird gegen die Überschriften des **ganzen Bestands** aufgelöst, nicht
gegen eine feste Datei. Das ist die wörtliche Hebung der heutigen Zusicherung („der genannte
Abschnitt existiert") und keine neue Bindung an einen Ablageort. Eine Bindung an das auf
derselben Zeile genannte Dokument wäre strenger, machte aber jede legitime Katalogaufteilung
wieder rot — genau die Brittleness, die diese Story entfernt.

**AC8.** Die Tabelle oben nennt die Träger. Eine Verschärfung ist dabei nachzuholen, sonst fällt
der Quelltextanker ohne Ersatz: `TestTheLandmarkClientFollowsTheModel` und
`TestTheCategoryClientFollowsTheModel` prüfen heute, **welcher** Anbieter-Schrittmacher angefragt
wird (`throttles == ["mistral"]`), aber nicht, dass dessen Rückgabe beim Client ankommt. Der
gepatchte Schrittmacher gibt deshalb ein Sentinel-Objekt zurück, und der Bau wird zusätzlich über
`built[0][1]["throttle"] is sentinel` geprüft. `test_no_client_constructor_defaults_the_throttle`
bleibt: eine Signatur ohne Default ist Klasse B (maschinell gelesen), keine Formulierung.

**Testkonzept.** Ergänzung nötig, mit den Stellen: `## Nachweis ohne Rot-Grün
(bereichsübergreifend)` („Kein Testdiff" grenzt sich gegen den genehmigten C-Nachzug im selben PR
ab, sonst widerspricht es ADR 0148); ein neuer Abschnitt zu den drei Klassen und der
Mutationspflicht; `#### Die neue tragende Ebene: Repo-Konsistenztests (scripts/tests/)`
(Negativfälle je Muster → Mutationen je Invariante); `### Erweiterung für ADR 0061 …` (ein Ort →
Definitionsmenge über mehrere Dokumente); `### Erweiterung für Spec 0404 / ADR 0088`
(Job-Inventar und Schrittzahl → Prüfqualitäten); `### Der erste Testgegenstand, der WARTET …`
(„die Factories laufen in keinem Test" ist durch die gepatchten Fälle überholt; der Quelltextanker
entfällt); `## Was bewusst nicht getestet wird` (die gefallenen C-Prüfungen, namentlich der
Quelle-Datum-Beleg der Voreinstellungen und `-n auto`); `## Bekannte Lücken` (Mutationen sind an
den Bestand gebunden; der Blockleser ist die Schwachstelle); `## Werkzeuge im Überblick` (die
CI-Tabelle nennt Jobs und Schritte, als wären sie fest). Kopfzeile „Letzte Aktualisierung"
mitziehen.

**Edge Cases, die je einen eigenen Fall bekommen.** Löschung am Rand eines Blocks (Ort ist die
Folgezeile); Mutation, die nur außerhalb des bewachten Blocks trifft (muss **rot** werden, sonst
ist der Blockschnitt zu weit); `run: |`-Block mit mehreren Kommandos (jede Qualität wird auch dort
erkannt); `npm run <skript>` in der CI (eine Stufe über `package.json` aufgelöst); Mutation, die
ein Feld zweimal einfügt (Dopplung statt Ersatz); Umformulierung, die den Bestand leert (wird rot,
weil die Invarianten greifen); doppelte Operations-ID in zwei Dokumenten (rot über die
Definitionsmenge); ungetrackte Datei (kein Bestand — `git ls-files`, kein Verzeichnislauf).

## UI/UX

Nicht relevant: kein sichtbarer Oberflächenbezug. Die Story ändert Prüfungen über Dateien des
Repositories und die CI-Konfiguration; keine Komponente, kein Zustand und keine Eingabe wird
angezeigt oder verändert.

## Security

**Sicherheitsrelevant: ja — über das Asset „Integrität des KI-gesteuerten Entwicklungsprozesses“**,
im Sinne des Sicherheitskonzepts. Kein Anwendungscode, kein Endpunkt, kein neues Secret, kein neuer
Empfänger, kein Foto- oder Projektdatenbezug, keine Änderung an Auth oder Datensichtbarkeit.

Betroffen sind die vier Wächter, die den GitHub-Zugriff und den CI-Wartepunkt statisch absichern. Sie
sind heute die einzige automatisierte Absicherung der Befehlsform des `gh`-Wegs und die einzige
gegen ein leer grünes Warten auf den Prüfstand.

### Drei tragende Kontrollen, drei Prüfformen

| Kontrolle | Heute | Danach |
|---|---|---|
| Ein Ort | Kein `gh`-Aufruf und kein `mcp__github__`-Name außerhalb der Katalogdatei | Muster über den deklarierten Anweisungsraum (`.claude/**`, `CLAUDE.md`) |
| Befehlsform des `gh`-Wegs | Optionsnamen und Wortlaut | Wertklassen: Freitext nur als Dateiverweis, Ziel als geschlossenes Literal, Board-Werte gegen die Optionsmenge; ein unklassifizierbarer Aufruf ist ein Befund |
| Blockierendes, begrenztes, leer ausgewertetes Warten | Zahlen und Satzform des Wartepunkts | Eigenschaften am geparsten Aufruf: `--watch`, endliches `timeout`, kein `--required`, keine Pipe, leere Auswertungsgrenze |

**Die Story entfernt keine Kontrolle; sie ändert die Prüfform von drei Kontrollen** und entfernt
Redundanz. Ohne die Hebung fiele eine Kontrolle weg: ein zweiter, ungeprüfter GitHub-Zugriff wäre
möglich; eine Injektion in die Kommandozeile oder ein Schreibzugriff auf ein fremdes öffentliches
Repository wäre nicht mehr statisch ausgeschlossen; die CI-Prüfung könnte leer wahr sein und ein
roter Lauf als grün durchgehen.

### Auflagen an die Umsetzung

1. **Keine tragende Prüfung fällt.** Die Aussagen „ein Ort“, „geschlossene Operationsmenge mit genau
   einer Definitionsstelle je Operation“, „Wertklasse der Befehle“, „blockierend, begrenzt, ohne
   `--required`, ohne Pipe, leere Auswertungsgrenze“ und „kein Kommentar-Lesepfad“ bleiben prüfbar —
   in der mechanismsunabhängigen Form oben.
2. **Bilanzpflicht auch für Sicherheitsaussagen.** Jede gefallene Prüfung nennt
   `datei::testfunktion`, Klasse und erhaltene Aussage oder ausdrücklich „trug keine“.
3. **Mutationsliste je tragender Invariante.** Ein Wächter ohne Mutation für eine seiner Invarianten
   fällt — der einzige maschinelle Ersatz für die heutigen Negativtests.
4. **Zwei Verschärfungen statt Gleichstand.** Die Kommentar-Aussage gilt zusätzlich für Endpunkt- und
   Feldpfade (nicht nur ID und Feldliste); der blockierende Aufruf darf nicht durch eine Pipe laufen.
5. **Erlaubnisstufen bleiben Deklaration.** Genau eine Stufe je Datei, entdeckter Bestand gleich
   Erwartungstabelle; die Stufe macht die Befolgung nicht prüfbar.
6. **Anker bleiben Protokoll.** Die beiden CI-Anker stehen wortgleich an genau einer
   Definitionsstelle; die Prosa daneben ist frei.
7. **Klassengrenze beim Nachbessern.** Ein roter Wächter der Klasse A/B ist weder Fix noch Nachzug;
   Klasse C fällt nur mit benannter Aussage in der Bilanz. `scripts/tests/**` bleibt für den
   Fix-Lauf gesperrt.

### Nachzuziehen

- `specs/architecture/0003-securitykonzept.md`: Kopfzeile „Letzte Aktualisierung“; Abschnitt
  „Angriffsflächen“ — „Den Prüfer grün machen statt den Fehler beheben“ (A/B-Rot ist kein Nachzug,
  Klasse C nur mit Bilanzzeile) und „Was das nicht leistet“ (Klassenzuordnung nicht maschinell
  geprüft; Beweis sind Bilanz und Mutationsliste); Ankerliste, Zeile zur Nachbesserungsschleife;
  „Ein zweiter Zugangsweg zu GitHub“, Punkt 4 (Wertklassen statt Befehlsformen); die drei
  Lücken-Einträge zu statischen Prüfungen und Erlaubnisstufen.
- Nicht nachzuziehen: Auth-Modell, Secrets-Handling, GitHub-Repository-Zugriff und die Datenpfade —
  dort ändert sich nichts.

## Offene Fragen

Keine.

## Out of Scope

- Die Tests mit echter Logik (Nummernvergabe, Abgleich mit `main`, Produktentscheidungs-Anker,
  PR-Titel-Prüfung, Verweis- und Nummerneindeutigkeit) bleiben unverändert.
- Das Aufteilen von Testdateien unter `backend/tests` und `frontend/src` (eigenes Thema).
- Das Kürzen von Kommentaren selbst: Diese Story stellt die Prüfungen auf Wirkung um, sie entfernt
  keinen Kommentar.
- Das Kürzen der Doku selbst (eigenes Thema) — diese Story macht es erst möglich.
