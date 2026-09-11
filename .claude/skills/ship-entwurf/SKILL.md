---
name: ship-entwurf
description: Liefert aus, was ein abgeschlossener Penpot-Entwurfsrundenlauf im Repository verändert hat — misst den Diff selbst, prüft ihn gegen eine geschlossene Pfad-Zulassungsmenge, committet pfadgenau, gleicht mit `main` ab, pusht und eröffnet einen Pull Request. Nutze diesen Skill, wenn ein Rundenlauf mit der Zeile `## Entwurfslauf abgeschlossen: Pull Request erwünscht` endet, oder wenn Daniel direkt danach fragt ("mach aus dem Entwurfslauf einen Pull Request"). Nicht nutzen für die Nachbereitung eines `developer`-Laufs (dafür `ship-feature`) und nicht, um einen Entwurf selbst zu bauen (dafür `penpot-entwurfsrunden`).
---

# Ship Entwurf — ein Entwurfsrundenlauf endet im Pull Request

**GitHub-Erlaubnisstufe:** lesend und schreibend

**Nur in der Hauptsession.** Dieser Skill ist der Auslieferpfad eines Entwurfsrundenlaufs: Er
committet, was der Lauf im Repository verändert hat, gleicht mit `main` ab, pusht und eröffnet
einen Pull Request. Er fasst die Penpot-Datei nicht an, er löscht nichts, und er beurteilt keinen
Entwurf — beurteilt wird ein Entwurf durch Hinsehen.

**Jeder GitHub-Zugriff läuft über eine Operation des Skills `github-access`.** Lade ihn einmal
über das Skill-Werkzeug, an deinem ersten GitHub-Berührungspunkt (das ist Schritt 6), und arbeite
danach für den Rest des Laufs mit dem geladenen Katalog. Dieser Skill hier nennt ausschließlich
Operations-IDs und die Ablauf-Logik drumherum — wann eine Operation läuft, unter welcher
Bedingung, wie ihr Ergebnis ausgewertet wird. Rein lokales `git` ist davon unberührt und steht
weiterhin hier.

**Dieser Skill wiederholt aus `ship-feature` nichts, was er nicht selbst ausführt.** Es gibt hier
keinen offenen Subagenten, an den Findings oder ein Merge-Konflikt zurückgingen, keine
Perspektivenrunde, kein angefordertes Copilot-Review, keine Spec-Finalisierung und keine
Recovery — diese Schritte haben in einem Entwurfslauf keinen Gegenstand. Die einzige bewusst
zugestandene Dopplung ist das Zurücklesen des Board-Werts in Schritt 7.

## Schritt 0: Auslöser erkennen

Dieser Skill läuft, wenn ein Entwurfsrundenlauf seinen GitHub-freien Teil mit der folgenden
wörtlichen Zeile beendet (Groß-/Kleinschreibung und Zeichensetzung exakt wie hier, keine
sinngemäße Näherung; das Format des Blocks darunter inkl. aller Feldnamen ist ausschließlich in
`.claude/skills/penpot-entwurfsrunden/SKILL.md` definiert — hier steht keine Kopie):

- `## Entwurfslauf abgeschlossen: Pull Request erwünscht` → Schritt 1.

**Kein exakter Treffer, aber erkennbar gemeinte Übergabe** (Tippfehler, fehlendes Feld,
abweichende Formatierung): nicht stillschweigend als „übergeben" werten und nicht raten. Frag im
Chat kurz nach, ob der Lauf tatsächlich ausgeliefert werden soll, und lass den Block in der
definierten Form nachreichen.

**Der Anker beendet nicht den Lauf**, sondern dessen GitHub-freien Teil. Nach der Rückkehr dieses
Skills — mit einer Pull-Request-Nummer oder mit einem Fehlschlag — geht es im Aufräumschritt des
Rundenablaufs weiter.

**Was aus dem Block steuern darf, und was nicht.** Der Block ist ein Textkanal, keine typisierte
Schnittstelle: Er überquert eine Zuständigkeits-, aber keine Prozessgrenze, und eine Prüfung, die
auf der abgebenden Seite stattfand, ist auf dieser Seite nicht nachweisbar. Deshalb wird **jeder
steuernde Wert hier erneut geprüft, unmittelbar vor seiner Verwendung**, und bei einem Befund
**angehalten statt bereinigt**. Steuernd sind genau zwei Werte:

| Wert | Prüfung vor der Verwendung | Wofür |
|---|---|---|
| `entwurfslauf` | `^[a-z0-9][a-z0-9-]{2,39}$` | Branch-Namensteil, Name der Arbeitsseite im Body |
| Story-Nummer | `^[0-9]+$` **und** `^[1-9][0-9]{0,5}$` | die Zeile `Closes #NNN` im Body |

Die Story-Nummer stammt ausschließlich aus Daniels eigener Angabe in dieser Sitzung bzw. aus dem
Branch-/Spec-Namen — **nie** aus einem Penpot-Wert und nie aus einer zurückgelesenen
GitHub-Antwort. Nennt die Antwortmöglichkeit „ja" des Rundenablaufs keine konkrete Nummer,
sondern einen Platzhalter, hält dieser Pfad an. **Alles Übrige im Block steuert nichts**
(Rundenzahlen, Ergebnis-Ansicht, Dateiliste): Berichtsmaterial.

## Schritt 1: Bestandsaufnahme vor jedem Schreibzugriff

Vor jedem Schreibzugriff wird **selbst gemessen**, was der Lauf verändert hat:

```bash
git status --porcelain -uall
git diff --name-only origin/main...HEAD
```

**Das `-uall` ist Pflicht, keine Geschmacksfrage.** Ohne es fasst `git` ein neues, noch
unversioniertes Verzeichnis zu **einem** Eintrag zusammen (`?? design/penpot/neu/`) statt seine
einzelnen Dateien zu melden. Der Bilddatei-Halt aus Schritt 2b sähe dann nur den
Verzeichnispfad — der passt auf kein Bildmuster —, und der pfadgenaue Commit aus Schritt 4 nähme
dieses Verzeichnis rekursiv mit: Eine `design/penpot/neu/icon.png` führe genau an der Prüfung
vorbei, die sie abfangen soll, und der CI-Schritt ist ausdrücklich nur ein Detektor **nach** dem
Push. Die Ausgabe wird deshalb **zu einzelnen Dateipfaden aufgelöst** —
**bevor** Zulassungsmenge, Wächter-Halt und Bilddatei-Halt greifen.
Endet ein gemessener Pfad trotzdem auf `/`, ist die Auflösung nicht gelungen: Dann hält der
Ablauf an, statt zu raten.

Die Vereinigung beider Ausgaben ist die **gemessene Pfadmenge** und die einzige Grundlage jeder
folgenden Prüfung; die Zeile `Geänderte Dateien` des Übergabeblocks wird dafür **nicht** gelesen.
Grund: Die geschlossene Diff-Klasse ist die Bedingung, unter der der Verzicht auf eine
Perspektivenrunde überhaupt vertretbar ist — ruhte sie auf einer Textzeile aus demselben Kontext,
der auch die Penpot-Rücklesungen enthielt, reichte ein ausgelassener Pfad, damit etwas außerhalb
der Klasse mitfährt, ohne dass irgendwo etwas rot wird.

Weicht die Zeile des Blocks von der Messung ab, ist das **kein** Abbruchgrund (ein bereits
abgelegter Spec-Commit steht dort legitim nicht drin) — die Abweichung geht in den Chat-Bericht.

**Die geschlossene Zulassungsmenge — genau drei Präfixe:**

| Zugelassen | Was darin liegt |
|---|---|
| `design/penpot/**` | die Nachträge des Laufs: `views.json`, angehobene Kardinalitäten in `verify.js`, ggf. `README.md` |
| `frontend/penpot/**` | die zeilengebundenen Freigaben, die eine angehobene Kardinalität nach sich zieht |
| `specs/**` | Spec-/ADR-Commits, die auf einem Story-Branch bereits abgelegt sind |

**Jeder Pfad außerhalb dieser Menge hält den Ablauf an**: kein Commit, kein Push, kein Pull
Request, Meldung an Daniel. Namentlich ausgeschlossen — und damit nie Teil eines
Entwurfs-Pull-Requests — sind `backend/**`, `frontend/src/**`, `e2e/**`, `scripts/**`,
`.github/**` und `.claude/**`. Ein Lauf, der dort etwas geändert hat, ist kein Entwurfslauf mehr;
seine Änderung gehört in den gewöhnlichen Story-Weg mit Perspektivenrunde.

**Ein leerer Diff ist eine Auskunft, kein Fehler.** Hat der Lauf im Repository nichts verändert
(ein Ausschnitts- oder Bausteinentwurf, der die Nutzlast nicht berührt), entsteht kein Pull
Request; gemeldet wird genau das, statt einen leeren zu versuchen.

## Schritt 2: Zwei Halte-Prüfungen auf der gemessenen Menge

Beide laufen **vor** dem Commit, beide auf der in Schritt 1 gemessenen Menge, beide halten an,
statt zu bereinigen.

**(a) Wächter-Halt.** Angehalten wird, wenn der gemessene Diff

- eine **neue** `*.js`-Datei unter `design/penpot/` enthält, **oder**
- hinzugefügte oder entfernte Zeilen in `frontend/penpot/payload.test.ts` enthält, die
  `VERBOTENE_BEZEICHNER`, `BEZEICHNER_FREIGABEN`, `bezeichner:` oder `muster:` berühren.

Geprüft an `git diff -U0` über die gemessenen Pfade. Grund: Die ausgeführte Nutzlast und ihre
statische Verbotsliste liegen beide in der Zulassungsmenge — ein Pull Request mit einer
Nutzlast-Zeile **und** der passenden Freigabe wäre in der CI grün, weil die Prüfung, die er
aufweicht, im selben Diff liegt, und sähe auf diesem Pfad keinen Prüfer. Der Regelfall eines
Laufs (eine Kardinalität anheben, einen `views.json`-Eintrag ergänzen) wird davon nicht
getroffen.

**(b) Bilddatei-Halt.** Angehalten wird, wenn ein gemessener Pfad auf
`\.(png|jpe?g|gif|webp|bmp|tiff?|avif|heic|ico)$` passt —
**ohne Beachtung der Groß-/Kleinschreibung**, wortgleich mit dem Muster der CI.
Grund: Der CI-Schritt ist ein Detektor
**nach** dem Push, kein Verhinderer; hier wird vor dem Push committet, und ein roter Check nimmt
einen gepushten Blob nicht zurück. Bisher schrieb an dieser Stelle immer ein Mensch das `git add`.

**(c) Beispieldaten-Prüfung am Diff.** Die **hinzugefügten** Zeilen des gemessenen Diffs werden
einmal gegen die Beispieldaten-Regel aus `penpot-design` gelesen; bei einem Befund wird
angehalten. Der Freitext-Anteil eines Laufs ist der `luecken`-Block in `views.json`, und dieser
Pfad veröffentlicht den Diff automatisch. Das ist der einzige ehrliche Teilersatz für den
entfallenen Prüferblick.

## Schritt 3: Branch

- **Aktueller Branch ≠ `main`:** Dieser wird verwendet — der Lauf hat dort stattgefunden.
- **Aktueller Branch ist `main`:** Zuerst entsteht `design/<entwurfslauf>`. Der Namensteil ist
  genau der Wert, der in Schritt 0 gegen `^[a-z0-9][a-z0-9-]{2,39}$` geprüft wurde; er ist der
  einzige Wert aus der Design-Datei, der unter einem geschlossenen Muster steht und deshalb einen
  Befehl steuern darf. Scheitert die Prüfung, hält der Ablauf an.

Auf `main` wird nie committet und nie gepusht.

## Schritt 4: Commit — pfadgenau über die gemessenen Pfade

Committet werden **genau die in Schritt 1 gemessenen Pfade**, einzeln aufgezählt:
`git add <gemessene Pfade>`, **nie `git add -A`, nie `git commit -a`**. Eine Zulassungsmenge
hinter einem pauschalen Hinzufügen ist Zierde: Sie nähme eine danebenliegende, nicht versionierte
Datei mit, und der Branch geht unmittelbar danach in ein öffentliches Repositorium.

Commit-Nachricht in Conventional-Commits-Form (`CLAUDE.md`), Typ `chore`, kein `#` in der
Nachricht.

## Schritt 5: Abgleich mit `main` — nach dem Commit, vor dem Push

Führ `scripts/merge-main-into-branch.sh` aus — argumentlos, im Repositorium des aktuellen
Arbeitsverzeichnisses, auf dem Branch aus Schritt 3. Es steht **nach** dem Commit, weil es ein
sauberes Arbeitsverzeichnis verlangt, und **vor** dem Push, damit der Merge-Commit im selben Push
hinausgeht. Reines lokales `git`; das Skript pusht nie und checkt `main` nie aus. Ausgewertet wird
ausschließlich der Exit-Code:

- `0` → weiter, ohne Meldung. Kein Berichtseintrag; das Skript gibt in diesem Fall auch selbst
  nichts aus.
- `10` → weiter, mit einer Zeile im Bericht: Der Stand von `main` ist sauber übernommen worden.
- `20` (Konflikt) und jeder andere Code → anhalten, nichts pushen, an Daniel melden.

**Ein Konflikt wird hier nicht aufgelöst.** Es gibt keinen Subagenten, an den er ginge, und die
Kardinalitäten der Nutzlast sind handgepflegte Zahlen, deren Zusammenführung Augen braucht. Setz
in diesem Fall `git merge --abort` ab, damit nichts halb Aufgelöstes stehen bleibt, und melde die
Konfliktpfade **einzeln im Chat-Bericht** — **nie in den Pull-Request-Body**. Keine Meldung
zitiert rohe `git`-Ausgabe und keine nennt die Adresse des Remotes; eine credential-behaftete
`origin`-URL ist ein Secret.

Ein unbekannter Exit-Code wird **nie** wie `0` behandelt: Das hieße „`main` ist bereits
enthalten" für ein Repositorium, in dem gar nicht gemessen wurde.

## Schritt 6: Push und Pull Request

1. Push den Branch aus Schritt 3 (`git push -u origin <branch>`), nie `main`.
2. Eröffne einen Pull Request: Operation `pr-erstellen`.

**Titel:** `chore(design): <Beschreibung>`. Der Typ ist `chore`, weil ein Entwurfslauf kein
ausgeliefertes Produkt-Delta erzeugt — ein `feat`-Titel bumpte über die Release-Automatik die
Minor-Version der Anwendung für eine Änderung, die kein Nutzer je sieht. Die **Beschreibung**
formulierst du selbst oder bildest sie aus `entwurfslauf`/`schluessel`; sie wird nie aus einem
Penpot-Wert übernommen und enthält kein `#` — ein Closing-Keyword gehört ausschließlich in den
Body.

**Body** nach `.github/pull_request_template.md`, mit:

- was der Lauf im Repository verändert hat,
- dem Namen der **Arbeitsseite** — aus dem in Schritt 0 validierten `entwurfslauf`,
- dem Namen der **Ergebnis-Ansicht** — aus `anzeigename` und `schluessel` des betroffenen
  Eintrags in `design/penpot/views.json`.

Beide Namen kommen **nicht aus einem Penpot-Rücklesen**, sondern aus dem Repository. Brettnamen,
Beschreibungen und Textinhalte der Runden gelangen **nicht** in den Body; dort steht ausschließlich
selbst erzeugter Inhalt (Härtungsregel 4.3 des Katalogs).

**`anzeigename` und `schluessel` sind Repository-Inhalt, aber nicht selbst erzeugt** — der
Eintrag entstand in aller Regel im selben Lauf. Prüf beide vor dem Einsetzen, und zwar
**unabhängig voneinander**: genau eine nicht leere Zeile, keine Steuerzeichen, keine
Bidi-Overrides (U+202A–U+202E, U+2066–U+2069), keine Zero-Width-Zeichen (U+200B–U+200D, U+FEFF),
kein `#`, kein `@`, kein Backtick, Länge gedeckelt. Grund: Closing-Keywords werden **überall** im
Body ausgewertet — ein Anzeigename mit `#123` schlösse beim Merge ein fremdes Issue.

Was aus einem Befund folgt, hängt davon ab, **welcher** der beiden Werte ihn ausgelöst hat:

- Nur der `anzeigename` ist unzulässig: Im Body steht der geprüfte `schluessel` allein, die
  Abweichung geht in den Chat-Bericht.
- **Ist `schluessel` selbst unzulässig, hält der Ablauf an** — kein Pull Request, Meldung an
  Daniel. Ein Rückfall auf ihn schriebe genau den Wert in den öffentlichen Body, der die Prüfung
  nicht bestanden hat; enthielte er `#123`, schlösse der Merge ein fremdes Issue. Der Rückfall
  gilt deshalb ausschließlich für den einen Wert, der einen **geprüften** Ersatz hat.

**Gemessene `specs/`-Pfade werden einzeln und getrennt** von den Entwurfs-Nachträgen benannt —
im Body wie im Chat-Bericht. Damit ist beim Merge sichtbar, dass ein ADR- oder Konzepttext
mitfährt; der eigentliche Schutz dafür bleibt Daniels Merge.

**Story-Bezug.** Mit Story trägt der Body die ausgefüllte Zeile `Closes #NNN` mit der in Schritt 0
geprüften Nummer; nur sie erzeugt die strukturierte Verknüpfung und lässt GitHub das Issue beim
Merge schließen. Ohne Story entfällt die Zeile (die Vorlage sieht das als Ausnahme vor) — der Pull
Request entsteht trotzdem und wandert dann nicht von selbst auf `Review`. Das wird **gemeldet**,
nicht durch ein eigenmächtiges Setzen des Board-Werts verdeckt.

Scheitert `pr-erstellen` mehrdeutig, wird erst lesend verifiziert, nie blind der nächste Weg
gegangen. Für einen Branch mit bereits offenem Pull Request scheitert die Operation eindeutig; es
entsteht kein zweites Artefakt, und der Fehlschlag geht in den Chat-Bericht.

## Schritt 7: Board-Rücklesen — nur mit Story

Ohne Story entfällt dieser Schritt vollständig.

Mit Story: Lies den Wert einmal mit `board-status-und-prioritaet-lesen` zurück — ausgewertet wird
der Knoten mit `project.number == 8`, nie schlicht `nodes[0]`. `Review` schreibt GitHub selbst,
ausgelöst durch die Closing-Zeile aus Schritt 6.

- **Steht `Review`:** nichts zu tun, im Bericht einzeilig vermerken.
- **Steht etwas anderes:** GitHub verarbeitet die Verknüpfung asynchron. Einmal kurz warten
  (wenige Sekunden), ein zweites Mal lesen.
- **Steht es dann immer noch nicht** (oder scheitert die Leseoperation auf allen ihren Wegen):
  Den Wert **nicht** selbst nachsetzen — das verdeckte genau die Ursache, die dieser Schritt
  sichtbar machen soll. Stattdessen `board-status-setzen` mit Wert `Review` in den Abschnitt
  `## Lokal nachzuholen`. Form und Inhalt dieses Abschnitts stehen vollständig im Katalog.

## Was dieser Pfad ausdrücklich nicht tut

- **Keine Perspektivenrunde und kein angefordertes Copilot-Review.** Ein Entwurf wird durch
  Hinsehen beurteilt, nicht durch eine Findings-Runde, und die Design-Datei, an der er hängt,
  kann kein Prüfer dieses Projekts lesen. Getragen wird der Verzicht von der geschlossenen
  Zulassungsmenge aus Schritt 1, den beiden Halte-Prüfungen aus Schritt 2, der unverändert
  laufenden CI und davon, dass Daniel merged — **nicht** von der Annahme, die Änderung sei
  harmlos.
- **Keine Spec-Finalisierung.** Die `**Status:**`-Zeile einer Spec bleibt unberührt;
  `Implemented` ist eine Aussage über einen reviewten Stand. Eine Story, die vollständig aus
  einem Entwurfslauf besteht, setzt ihre Statuszeile als gewöhnliche lokale Textänderung in den
  Commits des Laufs.
- **Kein Merge, kein Schließen eines Issues, kein `Done`.** Der Pfad endet am eröffneten Pull
  Request.
- **Kein Löschen, kein Zugriff auf die Penpot-Datei.** Dieser Pfad berührt das Repository, nicht
  die Design-Datei.

## Bericht an Daniel

Am Ende im Chat, in Worten:

- die Nummer und der Titel des eröffneten Pull Requests — oder der Grund, warum keiner entstand
  (leerer Diff, Halt in Schritt 1, 2 oder 5);
- die gemessenen Pfade, **die `specs/`-Pfade einzeln und getrennt** von den Entwurfs-Nachträgen;
- eine etwaige Abweichung zwischen der Zeile des Übergabeblocks und der Messung;
- die Zeile zum Abgleich mit `main`, falls er etwas übernommen hat, bzw. die Konfliktpfade
  einzeln, falls er angehalten hat;
- der zurückgelesene Board-Wert, falls es eine Story gab.

Blieb ein nativer Übergang aus oder schlug eine Board-Operation fehl, trägt der Bericht
zusätzlich denselben Abschnitt, der auch im Pull-Request-Body steht — je Zeile die Operations-ID
und die Nachhol-Zeile aus ihrem Katalogeintrag:

```markdown
## Lokal nachzuholen

Dieser Schritt ist fehlgeschlagen und wurde nicht nachgeholt. Die Befehle sind unverändert
wiederholbar und lokal nachzuholen.

- <Operations-ID>: <Nachhol-Zeile aus dem Katalogeintrag, mit den Nummern dieses Laufs>
```

Im Chat — und **nur** dort — kommt die wörtliche Fehlermeldung des zuletzt versuchten Wegs bzw.
der tatsächlich vorgefundene Board-Wert dazu. In den Pull-Request-Body gelangt beides nicht.
