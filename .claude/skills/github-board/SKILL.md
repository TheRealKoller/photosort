---
name: github-board
description: Verbindliche Sammlung der `gh`-Einzeiler für das gemeinsame GitHub Project (V2) — Story-Issue anlegen und ins Board aufnehmen, Issue-Body schreiben, Board-Status/Priorität setzen und lesen, PR↔Issue-Verknüpfung prüfen, eine Story verwerfen — plus die Regeln für Fehlschläge und den Berichtsabschnitt `## Lokal nachzuholen`. Nutze diesen Skill, wenn `capture`/`refinement`/`spec-writer`/`ship-feature` an ihren jeweiligen Stellen einen Board-Zugriff brauchen, oder wenn Daniel direkt danach fragt ("setz Issue #NNN auf Ready", "welchen Status hat #NNN").
---

# GitHub Board — die Befehlssammlung

Der Board-Zugriff besteht aus einzelnen `gh`-Befehlen. Es gibt kein eigenes Werkzeug, keine
Zustandsdatei, kein Nummern-Mapping und keinen Content-Push des Spec-Inhalts in den Issue-Body.
Die Zuordnung Spec ↔ Issue ist eine Identität — **die Spec-Nummer einer neuen Spec *ist* die
Nummer ihres Issues** (`specs/features/0262-*.md` gehört zu Issue #262). Nur die Altspecs
`0001`–`0065` folgen dieser Regel nicht; bei ihnen steht die Issue-Nummer in der
`**Bezug:**`-Zeile der Spec-Datei.

Klare Aufgabenteilung, die nicht aufgeweicht wird:

- **Issue-Body = Story** (Ziel, User Story, Akzeptanzkriterien) — geschrieben von `refinement`.
- **Spec-Datei = Technik** (Architektur, UI/UX, Security, Teststrategie) — lebt nur im Repo.

Voraussetzung an die Arbeitsumgebung: `gh` mindestens in der in
[`docs/setup.md`](../../../docs/setup.md) unter `**Mindestversion:**` dokumentierten Version —
erst ab dort kennt `gh project item-edit` die namensbasierte Form. Ein daran gescheiterter Aufruf
ist ein Werkzeugproblem, kein fachlicher Befund.

## Der Lebenszyklus: fünf Werte, und wer sie schreibt

```
Unrefined → Ready → In Progress → Review → Done
```

**Was GitHub selbst erkennen kann, löst GitHub aus. Was nur eine Session weiß, schreibt die
Session.** Nur zwei der fünf Übergänge sind noch Board-Schreibzugriffe eines Ablaufs:

| Übergang | Ausgelöst durch | Geschrieben von |
|---|---|---|
| → `Unrefined` | Das Issue wird ins Projekt aufgenommen | **GitHub**, Workflow `Item added to project` |
| → `Ready` | `refinement` hat die Story fachlich geschärft | Session (`refinement`, Schritt 6) |
| → `In Progress` | `spec-writer` beginnt — **vor** Branch und Spec-Datei | Session (`spec-writer`, Schritt 0) |
| → `Review` | Ein Pull Request verweist per `Closes #NNN` auf das Issue | **GitHub**, Workflow `Pull request linked to issue` |
| → `Done` | Das Issue wird geschlossen (Regelweg: Merge über das Keyword) | **GitHub**, Workflow `Item closed` |
| → `In Progress` (zurück) | Ein Pull Request wird ohne Merge geschlossen | Session (`ship-feature`) |

`Done` heißt **„vom Board"**, nicht „ausgeliefert" — sowohl eine umgesetzte als auch eine ohne
Umsetzung verworfene Story landet dort. Den Unterschied trägt GitHubs Close-Grund: Der
Verwerfen-Pfad in `refinement` schließt mit `--reason "not planned"`, der Merge schließt als
`completed`. Ein wieder geöffnetes Issue bleibt auf `Done` stehen (es gibt keinen
„Item reopened"-Workflow) — das ist ein bewusst hingenommener Handgriff Daniels am Board, kein
Fehler des Ablaufs.

Der lokale Spec-Datei-Lebenszyklus (`Proposed → Accepted → Implemented → Superseded`,
`specs/README.md`) ist davon unberührt und bleibt unverändert.

## Die Befehle

Immer genau ein Befehl pro Zweck, aus dem Repo-Root heraus. Andere Formen sind nicht zulässig —
insbesondere keine ID-basierten Varianten (`--id`/`--field-id`/`--project-id`), die vier
Knoten-IDs als Literale in Skill-Dateien verlangten.

```bash
# Board-Status setzen (namensbasiert, keine IDs)
gh project item-edit 8 --owner TheRealKoller --url <issue-url> --field "Status" --value "<Wert>"

# Priorität setzen - nur nach dem Lesen, siehe "Priorität" unten
gh project item-edit 8 --owner TheRealKoller --url <issue-url> --field "Priorität" --value "<Hoch|Mittel|Niedrig>"
```

`<issue-url>` wird **aus der Issue-Nummer gebildet**:
`https://github.com/TheRealKoller/photosort/issues/<NNN>`. `<Wert>` ist einer der fünf
Statuswerte oben, als Literal aus diesem Skill-Text.

```bash
# Status und Prioritaet eines Issues lesen - ein Aufruf, konstante Kosten
gh api graphql -F number=<NNN> -f query='
  query($number: Int!) {
    repository(owner: "TheRealKoller", name: "photosort") {
      issue(number: $number) {
        projectItems(first: 5) {
          nodes {
            project { number }
            status: fieldValueByName(name: "Status") {
              ... on ProjectV2ItemFieldSingleSelectValue { name } }
            prio: fieldValueByName(name: "Priorität") {
              ... on ProjectV2ItemFieldSingleSelectValue { name } }
          }
        }
      }
    }
  }'
```

Ausgewertet wird der Knoten mit `project.number == 8`, **nie** schlicht `nodes[0]` — sonst
entscheidet eine fremde Projektzugehörigkeit über ein Ablauf-Gate. Findet sich kein solcher
Knoten, ist das Issue nicht auf unserem Board; das ist ein Befund, kein Statuswert.

```bash
# Story-Issue anlegen und ins Board aufnehmen - bewusst ZWEI Befehle
gh issue create --repo TheRealKoller/photosort --title "$(cat <titel-datei>)" --body-file <pfad> --label <idee|bug>
gh project item-add 8 --owner TheRealKoller --url <issue-url> --format json --jq '.id'

# Issue-Body ueberschreiben
gh issue edit <NNN> --repo TheRealKoller/photosort --body-file <pfad>

# PR<->Issue-Verknuepfung pruefen
gh pr view <MMM> --repo TheRealKoller/photosort --json closingIssuesReferences,baseRefName

# Story ohne Umsetzung verwerfen
gh issue close <NNN> --repo TheRealKoller/photosort --reason "not planned"
```

**Zwei Befehle beim Anlegen, nicht `gh issue create --project`:** Das Issue muss überleben, wenn
der Board-Teil scheitert. Ein kombinierter Aufruf hätte diese Eigenschaft nicht.

**`gh pr view` bleibt bei genau dieser Feldmenge** (`closingIssuesReferences,baseRefName`):
`title`, `body`, `author`, `headRefName` und `comments` werden **nicht** ergänzt, und ein blankes
`gh pr view <MMM>` (das den Body ausgibt) kommt im Ablauf nicht vor. Die abgefragten Felder
liefern nur strukturierte Metadaten — damit gelangt kein fremdbeschreibbarer Freitext in einen
Agenten-Kontext.

### Priorität: erst lesen, dann nur bei leerem Feld schreiben

Ein von Daniel gesetzter Prioritätswert wird **nie** überschrieben. Das garantiert kein Werkzeug
mehr, sondern die Reihenfolge: Lesebefehl absetzen, und nur wenn `prio` leer ist (`null`), die
Empfehlung schreiben. Ist bereits ein Wert gesetzt, findet **kein** Schreibzugriff statt, und die
Zusammenfassung nennt den vorhandenen Wert statt der eigenen Empfehlung.

## Verbindliche Regeln beim Einsetzen von Werten

Mit dem früheren Werkzeug entfiel jede Interpolation von selbst; in einer Befehlszeile ist sie
wieder möglich. Deshalb gilt, ohne Ausnahme:

- **Freitext gelangt nie in eine Kommandozeile.** Bodies **immer** über `--body-file`, Titel über
  `--title "$(cat <pfad>)"`. Beide Dateien werden mit dem Schreib-Werkzeug angelegt (nicht per
  Shell-Umleitung mit interpoliertem Inhalt); die Titel-Datei ist genau eine Zeile lang.
- **Nur geschlossene Werte werden eingesetzt.** Issue-/PR-Nummern gegen `^[0-9]+$`, Spec-Nummern
  gegen `^\d{4}$`, jeweils ausschließlich aus dem laufenden Ablauf. Die Issue-URL wird aus der
  Nummer **gebildet**, nie aus einer `gh`-Ausgabe übernommen. Status- und Prioritätswerte stehen
  als Literale in diesem Skill-Text. **Keine Zeichenkette aus einer `gh`-Ausgabe, einem
  Issue-Body oder einem Kommentar wird je Teil eines Befehls. Kein `eval`.**
- **Die eine Ausnahme, eng gefasst:** `capture` kann die Nummer eines gerade angelegten Issues
  nirgends anders her bekommen als aus der Ausgabe von `gh issue create`. Erlaubt ist dort
  deshalb, und ausschließlich dort, das Herauslösen einer **Zahl** — geparst, gegen `^[0-9]+$`
  validiert und danach ausschließlich als Zahl weiterverwendet. Was nicht auf das Muster passt,
  bricht den Ablauf ab. Übernommen wird nie die Zeichenkette selbst: Die Issue-URL wird auch in
  diesem Fall aus der geprüften Zahl **gebildet**. Freitext (Titel, Body, Fehlermeldungen) fällt
  nie unter diese Ausnahme.
- **Die GraphQL-Query bleibt ein Literal in einfachen Anführungszeichen**, die Nummer geht
  ausschließlich als typisierte Variable `-F number=<NNN>` hinein. In doppelten
  Anführungszeichen expandierte die Shell `$number` zu leer — die Query wäre dann nicht
  fehlerhaft, sondern hätte klaglos eine andere Bedeutung.

## Ein Fehlschlag bleibt sichtbar — das Muster (einmal vollständig, hier)

Gilt für jeden Ablauf mit Board-Schritten (`capture`, `refinement`, `spec-writer`,
`ship-feature`). Die vier Skills verweisen hierher, statt das Muster zu wiederholen.

**1. Kein Urteil vor dem Versuch.** Es wird **nicht** vorab gemessen, ob das Board erreichbar ist
— der Befehl wird abgesetzt. Ihn zu versuchen kostet nicht mehr, als ihn zu messen, und ist
ehrlicher.

**2. Der Exit-Code wird ausgewertet, nie geschluckt.** `gh` beendet sich bei einem Fehlschlag mit
einem Code ≠ 0 und einer Meldung (bei einem unbekannten Optionsnamen z.B.
`option "Quatsch" not found on field "Status"; available options: …`). Der Ablauf bricht deswegen
**nicht** ab — die eigentliche Arbeit ist wichtiger als ihr Etikett —, führt den Schritt aber im
Abschnitt `## Lokal nachzuholen` seines Berichts auf, mit dem unverändert wiederholbaren Befehl.

**3. Struktureller Schutz:** Beide verbliebenen Session-Schreibzugriffe stehen **vor** der
Arbeit, die sie ankündigen (`Ready` vor der Übergabe an `spec-writer`, `In Progress` vor Branch
und Spec-Datei). Ein Fehlschlag lässt die Story deshalb immer auf dem früheren, konservativeren
Wert stehen — nie auf einem weiter fortgeschrittenen.

**4. Ein ausgebliebener nativer Übergang wird bemerkt.** Ein versehentlich deaktivierter
Projects-Workflow schreibt **gar nichts**, und sein Zustand ist per API nicht überwachbar.
Deshalb liest `ship-feature` nach dem Eröffnen des Pull Requests den Board-Wert einmal zurück und
führt ein ausgebliebenes `Review` ebenfalls unter `## Lokal nachzuholen` auf.

**5. Der Abschnitt `## Lokal nachzuholen`** steht wörtlich so im Abschlussbericht des Ablaufs
(Chat) und — sofern der Kanal in dieser Umgebung trägt — zusätzlich im ohnehin geschriebenen
dauerhaften Artefakt (Issue-Kommentar bzw. PR-Body). Trägt der Kanal nicht, bleibt es beim
Chat-Bericht, und der sagt ausdrücklich, dass er der einzige Träger ist.

**In das dauerhafte Artefakt gelangt ausschließlich selbst erzeugter Inhalt** (Muss-Kriterium):
der Schrittname, der aus den eigenen validierten Nummern gebildete Wiederholbefehl und genau
dieser feste Satz —

> Dieser Schritt ist fehlgeschlagen und wurde nicht nachgeholt. Die Befehle sind unverändert
> wiederholbar und lokal nachzuholen.

Eine `gh`-Fehlermeldung oder sonstiger Fremdtext geht dort **nicht** hinein. Sie bleibt dem
Chat-Bericht vorbehalten, den ein Mensch liest. Das Repository ist öffentlich, und ein Fehlgriff
ist nicht zurücknehmbar.

Beispiel für den Bericht:

```markdown
## Lokal nachzuholen

Dieser Schritt ist fehlgeschlagen und wurde nicht nachgeholt. Die Befehle sind unverändert
wiederholbar und lokal nachzuholen.

- `status-ready`: `gh project item-edit 8 --owner TheRealKoller --url https://github.com/TheRealKoller/photosort/issues/318 --field "Status" --value "Ready"`
```

Die Nummern in einem solchen Befehl stammen **ausschließlich** aus dem laufenden Ablauf, nie aus
einer `gh`-Ausgabe, einem Issue-Body oder einem Kommentar.

## Fehler behandeln

- **Meldung unverändert an Daniel weitergeben** und keinen eigenen Lösungsversuch unternehmen,
  der über das Offensichtliche hinausgeht. Insbesondere nicht umgehen, indem eine Spec-Datei oder
  ein Board-Wert von Hand nachgezogen wird.
- Verweist die Meldung auf einen fehlenden Scope (`gh auth refresh -s project`): Den Refresh
  **nicht** selbst auszuführen versuchen (erfordert i.d.R. interaktive Browser-Bestätigung) —
  Daniel den Befehl klar mitteilen.
- Meldet `gh`, dass Projekt, Feld oder Option nicht gefunden wurde, wird **nichts angelegt**:
  Dann wurden Board-Titel oder Feld-Optionen manuell verändert, und das ist ein einmaliger
  manueller Reparaturschritt von Daniel, kein automatischer Dauerbetrieb-Pfad.
- **Vor dem Einfügen lesen (Muss-Schritt, manueller Pfad):** Jede weiterzugebende
  `gh`-Ausgabe wird **gelesen**, bevor sie in ein Issue, einen PR-Kommentar oder eine andere
  GitHub-Ausgabe kopiert wird. Es gibt keinen maschinellen Schwärzungsfilter mehr; der Schritt
  gilt damit strenger als zuvor. Sieht etwas nach einem Geheimnis aus, wird es nicht eingefügt,
  sondern Daniel gemeldet.

  **Zusätzlich beim Messen von Hand in einer fremden/Remote-Umgebung** (z.B. „prüf mal, ob X dort
  geht"): **kein** Befehl, der das Credential ausgeben kann — `gh auth token`, `--show-token`,
  `echo $GH_TOKEN`, `env`/`printenv`, `GH_DEBUG=api`, `--verbose` sind ausgeschlossen. Und:
  **keine Anmeldung mit einem eigenen/persönlichen Token** in einer solchen Umgebung, auch nicht
  temporär — gemessen wird ausschließlich mit dem, was dort ohnehin vorliegt. Schreibmessungen
  nur gegen das Issue der laufenden Story selbst, und das entstandene Artefakt als Messartefakt
  kennzeichnen.

  Beide Pfade bleiben ausdrücklich getrennt: Auf dem **automatischen** Pfad
  (`## Lokal nachzuholen`) ist der Muss-Schritt gegenstandslos, weil dort gar kein Fremdtext
  hingelangt. Diese Ausnahme wird nie auf den manuellen Pfad ausgedehnt.

## Zusammenfassung an Daniel

Kompakte Chat-Antwort, kein separater Report: welcher Befehl mit welchem Ergebnis gelaufen ist,
jede Fehlermeldung wörtlich.
