# 0406 - Doppelte Dokumentnummern fallen auf statt still zu bleiben

**Status:** Accepted
**Erstellt:** 2026-09-11
**Bezug:** GitHub-Issue [`#406`](https://github.com/TheRealKoller/photosort/issues/406)

## Ziel

Specs, ADRs und Konzeptdokumente tragen ihre Identität in ihrer vierstelligen Nummer. Ist dieselbe
Nummer zweimal vergeben, bezeichnet jede Nennung der Form „ADR 0069" zwei verschiedene Dokumente,
und kein Leser kann entscheiden, welches gemeint ist. Bemerkt wird das heute von nichts: Die
bestehende Prüfung `scripts/tests/test_verweisnummern_in_markdown.py` bindet den sichtbaren
Linktext an seine Zieldatei — bei einer Dublette passt der Text zu beiden Dateien, und die Prüfung
bleibt grün.

Der Zustand ist belegt, nicht befürchtet. Unter `specs/decisions/` ist `0069` doppelt vergeben —
einmal für die Penpot-Ansichtsentwürfe, einmal für die Nebenkategorien. Von 129 Fundstellen der
Nummer im Bestand (gemessen auf `f50375e`, ohne das Tokenizer-Asset) nennen 87 die blanke Nummer
ohne Dateinamen und sind damit nur durch Lesen auflösbar; das Sicherheitskonzept allein trägt 13
solcher Zeilen und handelt von **beiden** Entscheidungen.

Die gefährlichere Hälfte des Problems ist nicht die Kollision selbst, sondern ihre naheliegende
Reparatur: Eine pauschale Textersetzung über die alte Nummer schreibt die Nennungen des fremden
gleichnamigen Dokuments stillschweigend mit — und meldet Erfolg.

## User Story

Als Leser der Projektdokumentation möchte ich, dass eine genannte Dokumentnummer genau ein Dokument
bezeichnet, damit ein Verweis mich nicht an eine fremde Entscheidung schickt und eine doppelt
vergebene Nummer auffällt, bevor sie sich im Bestand verteilt.

## Akzeptanzkriterien

Gegenüber dem Issue-Body sind AK 1, 2, 3, 6 und 8 auf Prüfbarkeit geschärft und AK 9 ist
hinzugekommen; AK 4, 5 und 7 stehen unverändert.

- [ ] **AK 1** — Eine automatische Prüfung stellt sicher, dass in `specs/decisions/`,
      `specs/architecture/` und `specs/features/` **je Verzeichnis** keine zwei unmittelbar darin
      liegenden `.md`-Dateien dasselbe vierstellige Nummernpräfix tragen. Dieselbe Nummer in zwei
      verschiedenen dieser Verzeichnisse ist **kein** Befund.
- [ ] **AK 2** — Findet die Prüfung eine Dublette, nennt ihre Meldung **alle** betroffenen Dateien
      vollständig (repo-relativer Pfad, stabile Reihenfolge), auch wenn es mehr als zwei sind — die
      Nummer allein genügt nicht, denn sie ist genau das Mehrdeutige.
- [ ] **AK 3** — Die Prüfung läuft im regulären Prüfsatz mit und lässt ihn fehlschlagen; sie ist
      keine bloße Warnung, die überlesen werden kann. Belegt dadurch, dass der festgehaltene
      Rot-Lauf mit dem CI-Befehl erzeugt wurde (`pytest` im Verzeichnis `scripts/`, ohne Angabe der
      Testdatei).
- [ ] **AK 4** — Die Prüfung führt **keine** Ausnahmeliste. Eine gefundene Dublette wird aufgelöst,
      nicht ausgenommen.
- [ ] **AK 5** — Die heute bestehende Dublette `0069` ist aufgelöst: Eines der beiden Dokumente
      trägt eine neue, freie Nummer.
- [ ] **AK 6** — Jede Nennung der umgezogenen Nummer ist einzeln geprüft und zugeordnet; die
      Nennungen des anderen gleichnamigen Dokuments bleiben unverändert. Eine pauschale
      Textersetzung über die alte Nummer findet nicht statt. Belegt durch drei Zahlen: Summenprobe
      |A| + |N| = Gesamtzahl des Inventars, `git diff --name-only` gegen die vorab festgelegte
      Dateiliste, und eine Restbestandsprobe auf **beide vollständigen alten Dateinamen**.
- [ ] **AK 7** — Nach der Auflösung ist die Prüfung auf dem gesamten Bestand grün, und die
      bestehende Verweis-Prüfung bleibt es ebenfalls.
- [ ] **AK 8** — Es ist belegt, dass die Prüfung eine Dublette findet: durch eine **dauerhaft im
      Testcode verbleibende** Gegenprobe an synthetischem Material, die auch den Meldungstext prüft,
      **und** durch den wörtlich festgehaltenen Rot-Lauf auf dem echten Bestand.
- [ ] **AK 9** — Die Prüfung sichert zusätzlich zu, dass jede `.md` unmittelbar in den drei
      Verzeichnissen ein vierstelliges Nummernpräfix trägt — sonst entkäme ein Dokument der
      Eindeutigkeitszusage, indem es sein Präfix verliert.

## Datenmodell-Bezug

Keiner. Die Story berührt ausschließlich Dateinamen und Texte im Repository, keine Entität und
keine Migration.

## Architektur / Umsetzung

**Ansatz.** Die Prüfung wird ein weiterer Repo-Konsistenztest unter `scripts/tests/`, in der
Bauform der Nachbarn (`test_verweisnummern_in_markdown.py`): dünner Leser über den von Git
verwalteten Bestand, reine Funktion darüber, Gegenproben an synthetischem Material. Sie läuft
**ohne jede CI-Änderung** im bestehenden Job `demo-scripts` mit (`scripts/pyproject.toml`,
`testpaths = ["tests"]`) — getrennt von den Backend-Tests, außerhalb des Coverage-Gates. Kein
neuer Job, kein neues Werkzeug, keine neue Abhängigkeit.

Die tragende Entscheidung steht in ADR
[`0081`](../decisions/0081-dokumentnummer-ist-identitaet-die-juengere-dublette-zieht-um.md): Die
Dokumentnummer ist Identität; eine Dublette wird durch **Umzug des jüngeren** Dokuments aufgelöst,
nie ausgenommen; die neue Nummer ist die nächste freie und die alte wird nie recycelt; die
Umnummerierung folgt einem dreiteiligen Verfahren (Inventar → Klassifikation → Bilanz).

### Entwurfsentscheidungen

1. **Geprüft wird je Verzeichnis, nicht verzeichnisübergreifend.** Die drei Nummernräume
   überlappen von Bauart wegen (ADR 0043: Feature-Nummer = Issue-Nummer). Gemessen: 65 Nummern
   führen `decisions/` und `features/` gemeinsam, vier `architecture/` und `features/`, vier
   `decisions/` und `architecture/`. Eine gemeinsame Prüfung wäre an 73 Nummern rot — und sachlich
   falsch.

2. **Suchraum ist `git ls-files --cached --others --exclude-standard`**, nicht `git ls-files`
   allein. Die Dublette entsteht in dem Moment, in dem die Datei angelegt wird — vor dem
   `git add`; genau dann soll die Prüfung am lautesten sein. Gitignorierte Ablagen bleiben
   draußen, im CI-Checkout liefern beide Formen dasselbe.

3. **Die Meldung nennt alle betroffenen Dateinamen vollständig.** Die Nummer allein ist genau das
   Mehrdeutige; sie steht nur zusätzlich dabei.

4. **Keine Ausnahmeliste, auch keine leere vorbereitete.** Eine Ausnahme, die nichts ausnimmt,
   ist eine Einladung, später eine echte danebenzustellen.

5. **Selbstschutz aus drei Teilen** — Untergrenze je Verzeichnis, namentlicher Anker je
   Verzeichnis, lauter Fehlerfall bei leerem Suchraum. Der Zuschnitt steht in der Teststrategie.

6. **Der Rot-Start ist eingeplant, nicht zu umgehen.** Prüfung und Auflösung liegen im selben
   Pull Request: rot ab Schritt 1, grün ab Schritt 7. Daraus entsteht **keine** allgemeine
   Projektregel (siehe „Out of Scope"); hier ist es für diesen einen Fall entschieden.

7. **Zweites, schon vorhandenes Netz:** `test_verweisnummern_in_markdown.py` bindet Linktext an
   Linkziel. Es erwischt den **halb** nachgezogenen Verweis — eine Seite geändert, die andere
   nicht. Ein Verweis, an dem **keine** Seite nachgezogen wurde, bleibt grün und zeigt auf eine
   Datei, die es nicht mehr gibt; Existenz prüft dieser Test bewusst nicht. Das mechanische Netz
   der Umnummerierung ist deshalb der **alte vollständige Dateiname**, nicht die Nummer.

### Betroffene Dateien

**Neu:** `scripts/tests/test_dokumentnummern_eindeutig.py`; ADR
`specs/decisions/0081-dokumentnummer-ist-identitaet-die-juengere-dublette-zieht-um.md`.

**Umbenannt (`git mv`):** die Ansichtsentwurf-ADR aus `specs/decisions/` von Präfix `0069` auf
`0082`, Dateirumpf `-ansichtsentwuerfe-als-handarbeit-mit-soll-struktur-im-repository.md`
unverändert, samt Titelzeile und der neuen Kopfzeile `**Frühere Nummer:**` (ADR 0081, Abschnitt 4).

**Geändert — vorab festgelegte Menge, Teil der Bilanz in Schritt 6.** Die Zeilennummern sind eine
Momentaufnahme auf `f50375e` und dienen als Gegenprobe zum eigenen Inventar, nicht als Quelle:

| Datei | Fundstellen |
|---|---|
| `.gitignore` | 37 (Kommentar mit vollem Dateinamen) |
| `design/penpot/README.md` | 130 |
| `specs/architecture/0002-testkonzept.md` | **nur** 642 |
| `specs/architecture/0003-securitykonzept.md` | **nur** 589, 593, 596, 597, 869 |
| `specs/decisions/0070-bausteinmenge-regelgebunden-offen-statt-geschlossen.md` | 98 |
| `specs/decisions/0073-entwurfsrunden-auf-arbeitsseite-aufraeumen-als-handgriff.md` | 6, 9, 10, 16, 85, 130, 178, 299 |
| `specs/decisions/0077-entwurfslauf-endet-im-pull-request-uebergabe-per-anker.md` | 5 |
| `specs/features/0358-projektverwaltung-entwurf.md` | 157, 306, 408, 744, 766, 816, 842, 974, 998, 1002 |
| `specs/features/0380-entwurfsrunden.md` | 53, 95 |

**Bleibt unverändert, obwohl `0069` darin steht** — zwei verschiedene Gründe:

- *Nennungen der Nebenkategorien-Entscheidung:* `specs/decisions/0021`, `0049`, `0067`,
  `0069-nebenkategorien-…` (behält seine Nummer), `0071`, `0072`;
  `specs/architecture/0004-design-system.md` und `0002-testkonzept.md` Zeile 496;
  `specs/features/0051`, `0300`, `0357`; sowie **rund 26 Fundstellen unter `backend/` und
  `frontend/`** (Doku-Blöcke, Tests, eine Migration).
- *Nennungen der Kollision selbst:* in ADR `0081` und in **dieser Spec** beschreiben die
  Nennungen von `0069` die doppelt vergebene Nummer als solche und meinen keines der beiden
  Dokumente. Sie bleiben; das schließt die Stellen ein, an denen hier der alte Dateirumpf genannt
  wird, um die Umbenennung überhaupt beschreiben zu können.

**Die zwei gefährlichen Dateien** sind `specs/architecture/0002-testkonzept.md` und
`specs/architecture/0003-securitykonzept.md`: Sie führen Nennungen **beider** Dokumente. Genau
dort zerstört eine pauschale Ersetzung etwas und meldet Erfolg.

**Doku:** `docs/setup.md` nennt im Tests-Block zusätzlich `cd scripts && pytest`.
`specs/architecture/0002-testkonzept.md` ist um eine Sektion ergänzt.
`docs/architecture.md` ist nicht berührt — keine neue Komponente, kein geändertes Datenmodell.

### Reihenfolge der Umsetzung

1. **Prüfung schreiben.** Sie ist auf dem Bestand **rot** und nennt beide Dateien der Dublette
   vollständig. Diesen Lauf wörtlich im Test-Docstring festhalten — mit dem CI-Befehl
   (unqualifiziertes `pytest` im Verzeichnis `scripts/`) und der vollständigen Meldung. Er ist der
   Verdrahtungsbeleg, den ein späterer grüner Lauf nicht mehr liefern kann.
2. **Selbstschutz und Gegenproben** ergänzen; die reinen Funktionen bleiben ohne Dateisystem
   prüfbar.
3. **Inventar.** Jede Fundstelle von `0069` im **gesamten** von Git verwalteten Bestand als
   `datei:zeile`, alle Dateitypen, mit genau einer Ausnahme:
   `backend/src/photosort/assets/label_embedder_tokenizer.json` (dort sind es Nachkommastellen von
   Gleitkommazahlen, mehrere hundert Treffer). Außerhalb dieses Assets gibt es keine
   Nachkomma-Fundstelle — jeder Treffer ist eine echte Dokumentnennung, die Summenprobe gilt daher
   ohne Rauschabzug. Gesamtzahl und Dateimenge notieren. Das Inventar-Skript ist Wegwerfgut und
   wird nicht committet.
4. **Klassifizieren.** Jede Fundstelle genau einem der beiden Dokumente zuordnen — oder der dritten
   Klasse „meint die Kollision, nicht ein Dokument" (nur ADR 0081 und diese Spec). Auflösbar sind
   alle, die in einem Linkziel oder als vollständiger Dateiname stehen; jede blanke Nennung wird
   einzeln gelesen. Summenprobe: |A| + |N| + |K| = Gesamtzahl, keine Fundstelle ohne Klasse.
5. **Umsetzen.** `git mv`, Titelzeile, `**Frühere Nummer:**`-Kopfzeile; danach jede Klasse-A-
   Fundstelle **einzeln** über das Änderungs-Werkzeug, mit umgebendem Kontext im Suchmuster. Kein
   `sed`, kein `replace_all` auf `0069` — eine Mehrdeutigkeit muss laut scheitern
   (`CLAUDE.md`, „Werkzeugwahl bei Dateiarbeit").
6. **Bilanz — das ist die strukturelle Einhaltung, nicht der Vorsatz:**
   - `git diff --name-only` ergibt exakt die Tabelle oben plus die neuen Dateien. Insbesondere
     **keine** Datei unter `backend/`, `frontend/`, `e2e/`.
   - Verbliebene `0069`-Fundstellen = |N| + |K|; `0082`-Fundstellen = |A|.
   - Der alte vollständige Dateiname der umgezogenen ADR kommt **außerhalb von ADR 0081 und dieser
     Spec** nirgends mehr vor; der Dateirumpf der bleibenden ADR trägt nirgends das Präfix `0082`.
7. **Grün.** Neue Prüfung und `test_verweisnummern_in_markdown.py` grün, danach der volle
   Prüfsatz (`backend`, `frontend`, `scripts`). Die Umbenennung fasst keinen Code an — ein roter
   Backend-Test wäre hier selbst schon der Befund.

## UI/UX

Nicht relevant — die Story ändert Dateinamen, Verweistexte und einen Prüfsatz-Test; die Bilanz in
Schritt 6 schließt `frontend/` ausdrücklich aus dem Diff aus.

## Security

Nicht relevant — kein Auth-, Secret-, Berechtigungs- oder Datenmodell-Bezug, keine neue Eingabe von
außen. Die Prüfung liest ausschließlich Dateinamen aus dem eigenen, von Git verwalteten Bestand.
Dass `specs/architecture/0003-securitykonzept.md` im Diff steht, ändert daran nichts: Dort werden
Verweisnummern berichtigt, keine Sicherheitsaussage.

## Teststrategie

**Eine Ebene, sonst keine.** Repo-Konsistenztest unter `scripts/tests/` im Job `demo-scripts`,
außerhalb des Coverage-Gates — kein Backend-, kein Frontend-, kein E2E-Bezug, weil die Story keine
Zeile Anwendungscode anfasst. Bauform der Nachbarn: reine Funktionen über ein Pfad-Abbild (ohne
Dateisystem prüfbar), ein dünner Leser drumherum.

**Zwei Zusicherungen in einer Datei.** (1) *Eindeutigkeit* (AK 1). (2) *Präfix-Vollständigkeit*
(AK 9; Ist-Stand 2026-09-11: 197 von 197). Die zweite schließt das Schlupfloch der ersten: Wer sein
Präfix verliert, fiele sonst aus dem Suchraum, statt gemeldet zu werden. Preis: Eine künftige
`README.md` in einem der drei Verzeichnisse färbt rot — bewusst so, denn eine Ausweitung der
Namenskonvention soll entschieden werden statt einzusickern, und ein Ausnahmeeintrag dafür wäre
genau die Liste, die AK 4 verbietet.

**Selbstschutz.** (a) Leerer Suchraum — insgesamt **und je Verzeichnis** — ist ein lauter
Fehlerfall mit eigener Meldung, kein Nullbefund. (b) Untergrenzen je Verzeichnis, bewusst weit
unter dem Ist-Stand (82/4/111): `decisions` ≥ 60, `features` ≥ 80, `architecture` ≥ 2. (c) Je
Verzeichnis eine namentlich genannte Ankerdatei, die im gelesenen Bestand vorkommen muss — bei
einem Verzeichnis mit vier Dokumenten entartet die Untergrenze, und nur der Anker fängt den Fall,
dass ein Verzeichnis ganz aus der Aufzählung fällt. Als Anker taugt kein Dokument, das selbst zur
Umbenennung ansteht. (d) Gegenproben an synthetischem Material in beide Richtungen.

**Wirksamkeitsbeleg — beide Formen, eine trägt.** Tragend für AK 8 ist die **dauerhafte
synthetische Gegenprobe**, weil sie nach jeder künftigen Änderung am Muster noch läuft; damit sie
die Meldung selbst prüfen kann, liefert die reine Funktion den fertigen Befundtext (wie
`nummern_verstoesse` in `test_verweisnummern_in_markdown.py`), nicht nur ein Urteil. Der echte
Rot-Lauf ergänzt, was sie nicht leisten kann: die Verdrahtung über die ganze Kette an echten Daten
— und er belegt mit demselben Lauf AK 3 (CI-Befehl) und AK 2 (Meldung mit allen Dateinamen). Der
Docstring-Eintrag ist als Beleg **plus Anweisung** zu formulieren („wer das Muster ändert, erzeugt
den Fall synthetisch nach"), nicht als Erzählung des Vorfalls.

**Edge Cases, die abgedeckt sein müssen:**

1. **Merge-Konflikt:** `git ls-files --cached` listet einen unvereinigten Pfad **mehrfach** (eine
   Zeile je Stage; gemessen: dreimal). Pfade werden zu einer Menge zusammengefasst, und ein Befund
   zählt erst ab zwei **verschiedenen** Pfaden — sonst meldet der Wächter mitten im Abgleich mit
   `main` eine Datei als Dublette ihrer selbst.
2. **Drei und mehr Dateien auf derselben Nummer:** die Meldung nennt alle, nicht die ersten zwei.
3. **Dieselbe Nummer in verschiedenen Verzeichnissen ist kein Befund** (73 Nummern betroffen).
4. **Nicht verwaltete Datei** (`--others`) zählt mit, ignorierte nicht.
5. **Kein gültiges Präfix** (fünfstellig, ohne Trennstrich, Ziffern mitten im Namen): keine
   Dokumentnummer — fällt nicht still heraus, sondern in die zweite Zusicherung.
6. **Nicht-`.md` und Unterverzeichnisse:** beides heute nicht vorhanden, beides ausdrücklich
   außerhalb der Zusicherung statt stillschweigend mitgeprüft.
7. **Meldungsform:** repo-relative Pfade, stabile (sortierte) Reihenfolge, Nummer zusätzlich.
8. **Dateinamen mit Leerzeichen:** `-z`-getrennte Aufzählung wie bei den Nachbarn.

**Was nicht geprüft wird:** dass eine neu vergebene Nummer die *nächste freie* ist (Handarbeit,
siehe „Out of Scope"); dass ein Markdown-Linkziel existiert (repo-weite Lücke, im Testkonzept
vermerkt); die Zuordnung einer blanken Nennung zu einem der beiden Dokumente — die ist Lesearbeit
und mechanisch allein über Summenprobe und Restbestandsprobe abgesichert.

## Entscheidungen

- **Die Penpot-Ansichtsentwürfe ziehen um, nicht die Nebenkategorien** — und zwar auf `0082`. Drei
  unabhängige Gründe zeigen in dieselbe Richtung: Sie ist die **jüngere** Vergabe (18:35 gegenüber
  18:11 desselben Tages) und hat damit eine belegte Nummer genommen; sie hat außerhalb von Markdown
  genau **eine** Fundstelle (ein Kommentar in `.gitignore`), während die Nebenkategorien-Nummer an
  rund 26 Stellen quer durch `backend/` und `frontend/` steht; und auf die Nebenkategorien-ADR
  zeigen vier **Teil-Vermerke** anderer ADRs, die nach `specs/README.md` unveränderlich sind, auf
  die Ansichts-ADR keiner.
- **Die Prüfung prüft je Verzeichnis, nicht verzeichnisübergreifend** — die Nummernräume überlappen
  von Bauart wegen, eine gemeinsame Prüfung wäre an 73 Nummern rot und sachlich falsch.
- **Die Prüfung kommt ohne CI-Änderung aus** — `scripts/tests/` läuft bereits im Job
  `demo-scripts`.
- **Die Präfix-Vollständigkeit (AK 9) gehört in dieselbe Prüfung**, nicht daneben: Ohne sie entkommt
  ein Dokument der Eindeutigkeitszusage still, indem es aus dem Suchraum fällt.
- `ux-ui-designer` nicht konsultiert (Schritt 2): Die Story berührt keine sichtbare Oberfläche; die
  Bilanz in Schritt 6 schließt `frontend/` strukturell aus dem Diff aus, es gibt weder eine Stelle,
  an der etwas angezeigt oder eingegeben wird, noch neue darzustellende Daten.
- `security-engineer` nicht konsultiert (Schritt 3): Kein konkret benennbarer Bezug zu Auth,
  externen Schnittstellen, Secrets, neuen Eingaben von außen, Berechtigungen, dem Datenmodell oder
  der Datensichtbarkeit zwischen den beiden Nutzern. Der Suchraum der Prüfung ist der eigene, von
  Git verwaltete Bestand; die Berührung des Sicherheitskonzepts betrifft ausschließlich
  Verweisnummern.

## Offene Fragen

Keine.

## Out of Scope

- **Die Vergabe der nächsten freien Nummer bleibt Handarbeit.** Diese Story verhindert die Kollision
  nicht, sie macht sie laut. Das deckt auch den Fall ab, in dem die Nummer ohne jede Parallelarbeit
  falsch bestimmt wurde — die entstehende Dublette ist dieselbe.
- **Keine allgemeine Projektregel** dazu, wie mit Prüfungen umzugehen ist, die auf dem Bestand rot
  starten. Issue #404 wirft dieselbe Frage auf; hier wird sie nur für diesen einen Fall entschieden.
- **Keine Umstellung des Nummernschemas** für `specs/decisions/` und `specs/architecture/` auf
  extern vergebene Nummern.
