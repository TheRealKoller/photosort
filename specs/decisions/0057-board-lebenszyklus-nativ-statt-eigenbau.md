# 0057 - Der Board-Lebenszyklus wird nativ: GitHub schreibt, was GitHub erkennt, `gh-board.py` entfällt

**Status:** Accepted
**Datum:** 2026-09-05
**Bezug:** GitHub-Issue [`#327`](https://github.com/TheRealKoller/photosort/issues/327) („Flow für tickets neu denken", löst [`#305`](https://github.com/TheRealKoller/photosort/issues/305) mit ab), zugehörige Feature-Spec `specs/features/0327-*.md`, `scripts/gh-board.py` (1.536 Zeilen) und `scripts/tests/test_gh_board.py` (3.294 Zeilen), Projekt „PhotoSort Roadmap" (`PVT_kwHOAdvbTs4Bg-8x`, Nummer 8), `architect`-Konsultation für Story #327 am 2026-09-05.

**Löst ab (jeweils benannt, nicht stillschweigend übergangen):**

- [`decisions/0037-status-lebenszyklus-umsetzungsfortschritt-pr-merge-erkennung.md`](./0037-status-lebenszyklus-umsetzungsfortschritt-pr-merge-erkennung.md) — **vollständig `Superseded`.** Abschnitt 1 (sechs Board-Werte inkl. `Todo`), Abschnitt 3 (`In Progress` beim Aufrufer des `developer`), Abschnitt 4 (`Review` in `ship-feature`), Abschnitt 5 (**keine** native Board-Automatisierung, Merge-Erkennung im eigenen Code) und die Abschnitte 6/7 werden hier sämtlich ersetzt. Abschnitt 2 (Baseline/Override aus dem Datei-Status) war bereits durch ADR 0043 gegenstandslos.
- [`decisions/0048-board-operationen-zielzustands-idempotent.md`](./0048-board-operationen-zielzustands-idempotent.md) — **`Superseded`.** Ihr *Prinzip* (Abschnitt 1: Maßstab ist der Zielzustand, nicht die Urheberschaft dieses Aufrufs) wird in Abschnitt 5 dieser ADR ausdrücklich übernommen; ihr *Mechanismus* (Nachprüfen des Issue-Zustands nach fehlgeschlagenem `gh issue close`, enge Ausnahme in `cmd_finalize`) entfällt mit dem Werkzeug und mit der Ursache, die ihn nötig machte.
- [`decisions/0052-remote-lebenszyklus-diagnose-kommando-und-echter-board-preflight.md`](./0052-remote-lebenszyklus-diagnose-kommando-und-echter-board-preflight.md) — **`Superseded`.** Abschnitt 1/3/4/5 (`doctor`, Scope-Deutung im Fehlerfall) entfallen mit dem Werkzeug. Abschnitt 6, zweiter Punkt („ein nativer GitHub-Projects-Workflow als Schreiber des Status-Felds: unverändert ausgeschlossen") wird durch Abschnitt 2 dieser ADR umgekehrt. Abschnitt 2/3 (**kein Urteil vor dem Versuch**) bleibt tragend und wird in Abschnitt 6 übernommen.
- [`decisions/0056-remote-grenze-gemessene-board-faehigkeit-statt-session-erkennung.md`](./0056-remote-grenze-gemessene-board-faehigkeit-statt-session-erkennung.md) — **`Superseded`.** Das Subkommando `capabilities` und die Vorabmessung vor jedem Ablauf entfallen (Abschnitt 6 dieser ADR begründet, warum sie ihren Gegenstand verloren haben). Die dort dokumentierte Remote-Grenze selbst bleibt als **Befund** gültig und wird in Abschnitt 7 neu bewertet.

**Löst teilweise ab (die betroffenen ADRs bleiben `Accepted` und bekommen einen Nachtrag-Verweis):**

- [`decisions/0046-pr-issue-verknuepfung-closing-keyword.md`](./0046-pr-issue-verknuepfung-closing-keyword.md), **Abschnitt 5** („Das Board-Status-Feld bleibt alleinige Domäne von `gh-board.py` — der Workflow `Item closed` wird abgeschaltet"). Die Abschnitte 1–4 — Closing-Keyword `Closes #NNN` im PR-Body, Prüfung gegen GitHubs eigene Auskunft `closingIssuesReferences` — bleiben nicht nur gültig, sie werden **tragend**: Ohne sie entsteht `Done` künftig gar nicht.
- [`decisions/0043-spec-nummer-gleich-issue-nummer-sync-tool-entfaellt.md`](./0043-spec-nummer-gleich-issue-nummer-sync-tool-entfaellt.md), **Abschnitt 4** („Ersatz ist ein einzelnes, dünnes Helferscript: `scripts/gh-board.py`"). Abschnitt 1–3 (Spec-Nummer = Issue-Nummer, keine Zustandsdatei, kein Content-Push) bleiben unverändert gültig.
- [`decisions/0042-pre-merge-finalisierung-statt-nachzieh-pr.md`](./0042-pre-merge-finalisierung-statt-nachzieh-pr.md), **Abschnitt 2 und 4** (Finalisierungsmodus des Werkzeugs; vorgezogener Board-Wert `Done` vor dem Merge). Abschnitt 1 und 3 — die **Spec-Statuszeile** wird vor dem Merge im Feature-PR selbst geschrieben, nach Review und Copilot-Auswertung — bleiben unverändert gültig.
- [`decisions/0044-prioritaet-startwert-automatisch-im-board-setzen.md`](./0044-prioritaet-startwert-automatisch-im-board-setzen.md), **Abschnitt 3** (eigener Befehl `set-priority`). Abschnitt 1/2/4 (Startwert aus der Empfehlung, first-write-wins, Reihenfolge Body → Priorität → Status) bleiben gültig; Abschnitt 4 dieser ADR sagt, wodurch first-write-wins ab jetzt hergestellt wird.

**Berührte Feature-Specs (keine Ablösung, nur Hinweis):** [`0262`](../features/0262-github-project-sync-tool-entfernen.md) (hat `gh-board.py` eingeführt), [`0278`](../features/0278-board-close-idempotent.md), [`0302`](../features/0302-gh-board-item-liste-vollstaendig-laden.md), [`0309`](../features/0309-story-lebenszyklus-remote-sessions.md), [`0318`](../features/0318-remote-lebenszyklus-grenze.md). Sie bleiben `Implemented` — sie beschreiben korrekt, was zu ihrer Zeit gebaut wurde.

## Kontext

Zwei Beobachtungen, beide aus Issue #327, beide am Bestand überprüfbar.

**Erstens bildet die Board-Spalte `Todo` keinen Zustand ab, den irgendjemand beobachtet.** Sie wird von `spec-writer` gesetzt, sobald die Spec-Datei liegt (ADR 0037, Abschnitt 1), und wenige Augenblicke später vom `In Progress` des beginnenden `developer`-Laufs überschrieben. Was dort tatsächlich liegenbleibt, sind Altlasten: zum Zeitpunkt dieser ADR vier offene Issues (#162, #167, #169, #174), an denen niemand arbeitet. Der Zustand, den `Todo` behauptet — „fertig spezifiziert, wartet auf Bearbeitung" — dauert im Regelfall Sekunden und im Ausnahmefall Monate; er unterscheidet nichts.

Damit verbunden eine zweite, bisher unbenannte Abweichung: Das Schreiben der Spec **ist** der Beginn der Umsetzung (`spec-writer` legt dafür bereits den Feature-Branch an, ADR 0045), aber das Board sagt währenddessen noch `Ready`. Der Zeitpunkt, ab dem eine Story sichtbar in Arbeit ist, liegt heute später als der Zeitpunkt, ab dem tatsächlich an ihr gearbeitet wird.

**Zweitens hängt die gesamte Board-Pflege an `scripts/gh-board.py`:** 1.536 Zeilen Code, 3.294 Zeilen Tests. Sein fachlicher Kern ist, an einem Issue ein Auswahlfeld zu setzen und den Beschreibungstext zu schreiben. Seit seiner Einführung (Spec 0262 / ADR 0043, Abschnitt 4) wurde er sechsmal nachgebessert — ADR 0044, 0046, 0048, 0052, 0056 und Spec 0302 sind jeweils eine Runde daran. Jede Änderung am Ablauf zieht Pflegeaufwand an diesem Werkzeug nach sich.

Der Grund, warum das Werkzeug diesen Umfang hat, steht in seinem eigenen Modulkopf: „Die fehleranfällige Projects-V2-Logik (Projekt-/Feld-/Options-/Item-ID-Auflösung, Setzen eines Single-Select-Werts) liegt bewusst nur hier". **Diese Begründung ist inzwischen überholt.** `gh` 2.97.0 (31.07.2026) hat `gh project item-edit` eine namensbasierte Form gegeben:

```bash
gh project item-edit 8 --owner TheRealKoller --url <issue-url> --field "Status" --value "In Progress"
```

Keine Projekt-ID, keine Feld-ID, keine Options-ID, keine Item-ID — und `gh` prüft den Wert gegen die tatsächlich am Board vorhandenen Optionen (`option "Quatsch" not found on field "Status"; available options: …`, Exit-Code 1). Die gesamte ID-Auflösungsschicht, die den größten und fehleranfälligsten Teil des Werkzeugs ausmacht, ist damit ersatzlos entfallen. Was übrig bliebe, wäre ein Wrapper um einen Einzeiler.

**Drei Feststellungen zur nativen Automatisierung**, alle am eigenen Board (Projekt 8) verifiziert:

1. Das Projekt kennt genau sechs eingebaute Workflows: `Auto-add sub-issues to project` (an), `Auto-close issue` (an), `Item added to project` (aus), `Item closed` (aus), `Pull request linked to issue` (aus), `Pull request merged` (aus). Der Zustand ist über GraphQL (`ProjectV2.workflows { enabled }`) **lesbar**.
2. Er ist über GraphQL **nicht schreibbar**: Die Schema-Abfrage über alle Mutationen liefert genau eine, `deleteProjectV2Workflow`. Es gibt kein Aktivieren, kein Deaktivieren, kein Konfigurieren des Zielwerts. Das bestätigt den Befund aus ADR 0046, Abschnitt 5, und macht das Ein-/Ausschalten zwingend zu einem manuellen Schritt im Projekt-UI.
3. Die Options eines Single-Select-Felds sind dagegen **sehr wohl** per API änderbar: `updateProjectV2Field` nimmt `singleSelectOptions` entgegen und überschreibt die Optionsliste; bestehende Optionen behalten ihre ID, wenn man sie mit ID erneut mitsendet. Die in ADR 0037, Abschnitt 7 und ADR 0030, Abschnitt 3 beschriebene Migration „Feld löschen, neu anlegen, alles neu pushen" ist damit **nicht mehr nötig**. Eine einzelne Option lässt sich gezielt entfernen, ohne die übrigen Spalten anzufassen.

**Der Einwand, um den es eigentlich geht.** ADR 0046, Abschnitt 5, hat den Workflow `Item closed` mit einem präzisen Argument abgeschaltet, und Issue #327 verlangt ausdrücklich, dieses Argument zu *beantworten* statt zu überstimmen:

> Er würde `Done` auch dann setzen, wenn ein Issue aus einem ganz anderen Grund geschlossen wird, während die Spec-Datei noch `Accepted` sagt — ein Board-Wert, den keine lokale Quelle mehr deckt und den nichts wieder zurückrechnet.

Abschnitt 3 dieser ADR beantwortet ihn.

Diese ADR ist wie 0013/0016/0017/0033/0037/0042–0046/0052–0054/0056 eine Prozess-/Tooling-Entscheidung für den Entwicklungsablauf selbst. Sie berührt PhotoSorts Laufzeitsystem, sein Datenmodell und seine Produktiv-Abhängigkeiten an keiner Stelle.

## Entscheidung

### 1. Fünf Board-Werte; `Todo` entfällt, `In Progress` beginnt beim Schreiben der Spec

```
Unrefined → Ready → In Progress → Review → Done
```

Die Option `Todo` wird aus dem Single-Select-Feld `Status` entfernt. Der Board-Wert ist damit endgültig kein Abbild des Spec-Datei-Status mehr, sondern die Antwort auf genau eine Frage: *Wie weit ist diese Story?* Der lokale Spec-Datei-Lebenszyklus (`Proposed → Accepted → Implemented → Superseded`, `specs/README.md`) bleibt unverändert und unberührt.

`In Progress` wird **zu Beginn** von `spec-writer` gesetzt, vor dem Anlegen von Branch und Spec-Datei — nicht mehr an dessen Ende und nicht mehr beim Start des `developer`. Das Schreiben der Spec ist Umsetzung; das Board sagt das ab jetzt auch. Der Nebeneffekt ist, dass der einzige Grund für `Todo` (der Zwischenzustand zwischen „Spec fertig" und „Umsetzung läuft") entfällt, statt nur unbenutzt zu bleiben.

### 2. Wer welchen Übergang auslöst — die vollständige Tabelle

| Übergang | Ausgelöst durch | Geschrieben von |
|---|---|---|
| → `Unrefined` | Das Issue wird ins Projekt aufgenommen | **GitHub**, Workflow `Item added to project` |
| → `Ready` | `refinement` hat die Story fachlich geschärft und den Issue-Body geschrieben | Session (`refinement`, Schritt 6) |
| → `In Progress` | `spec-writer` beginnt die technische Umsetzung | Session (`spec-writer`, Schritt 0) |
| → `Review` | Ein Pull Request verweist per Closing-Keyword auf das Issue | **GitHub**, Workflow `Pull request linked to issue` |
| → `Done` | Das Issue wird geschlossen — im Regelweg durch den Merge des PR über `Closes #NNN` | **GitHub**, Workflow `Item closed` |
| → `In Progress` (zurück) | Der Pull Request wird geschlossen, ohne gemergt zu werden | Session (`ship-feature` bzw. Daniel, Abschnitt 8) |

Die Regel dahinter, und der eigentliche Gehalt dieser Entscheidung: **Was GitHub selbst erkennen kann, löst GitHub aus. Was nur eine Session weiß, schreibt die Session.** `Ready` („diese Story ist fachlich fertig durchdacht") und `In Progress` („ich fange jetzt an") sind Urteile, die auf keinem GitHub-Ereignis beruhen — sie bleiben session-getriggert. Alles andere hängt an einem Ereignis, das GitHub ohnehin registriert.

Damit sind drei der fünf Übergänge nicht mehr davon abhängig, dass eine Session zum richtigen Zeitpunkt läuft und Schreibzugriff hat. Das ist kein Nebeneffekt, sondern der Hauptgrund (siehe Abschnitt 7 zu Remote-Sessions).

Manuell zu konfigurieren (Projekt-UI, siehe Konsequenzen — per API nicht möglich): `Item added to project` → `Unrefined`, `Pull request linked to issue` → `Review`, `Item closed` → `Done`, jeweils einschalten. `Auto-close issue` bleibt **an** und unverändert (ADR 0046, Abschnitt 5, letzter Punkt, und ADR 0048, Abschnitt 4, bleiben in dieser Hinsicht bestätigt). `Pull request merged` bleibt **aus**: Unsere Projekt-Items sind ausschließlich Issues, nie Pull Requests; der Workflow hätte keinen Gegenstand und wäre allenfalls ein zweiter Schreiber auf denselben Wert.

**Verifikation von `Pull request linked to issue`:** Dass dieser Workflow auf das *Issue*-Item anspricht, wenn ein PR es per Closing-Keyword referenziert, ist die einzige Annahme dieser ADR, die sich nicht vorab am eigenen Board messen ließ (sie verlangt einen echten PR). Der Pull Request der zugehörigen Story ist selbst die Probe: Er trägt `Closes #327` und muss das Item sichtbar auf `Review` bewegen. Feuert er nicht, greift die Regel dieses Abschnitts unverändert in die andere Richtung — GitHub erkennt den Übergang dann eben nicht, und `ship-feature` setzt `Review` direkt nach `gh pr create` mit demselben Einzeiler wie `Ready`/`In Progress`. Diese Rückfallebene ist Teil der Entscheidung, kein Notbehelf: Sie ändert nichts an der Regel, nur an ihrer Anwendung auf einen Übergang.

**Bewusst akzeptiertes Restrisiko dieses Workflows:** Das Repository ist öffentlich, und für die keyword-basierte PR↔Issue-Verknüpfung dokumentiert GitHub keine Berechtigungsprüfung des PR-Autors. Ein beliebiger Nutzer kann forken und einen Pull Request mit `Closes #NNN` eröffnen; der Workflow zieht die Karte dann auf `Review` — ohne Merge, ohne Repo-Recht. Das ist am 2026-09-05 gegen die beiden Alternativen abgewogen und von Daniel entschieden worden: Der Gewinn (der Übergang funktioniert auch aus Remote-Sessions, in denen jeder Board-Zugriff scheitert — bisher der teuerste Ausfall) wiegt schwerer als ein Schaden, der sichtbar ist, keinen Nutzerdaten-Bezug hat und mit einem Einzeiler behoben wird. Die beiden anderen nativen Übergänge sind nicht fremdauslösbar: `Item added to project` verlangt Projekt-Schreibrecht, und ein Fremder kann unsere Story-Issues nicht schließen. Zwei Folgen sind verbindlich: Das Statusgate in `spec-writer` bleibt **fail-closed** — ein Status ≠ `Ready` bricht ab und wird gemeldet, nie automatisch „repariert" oder umgangen —, und der Abbruchtext nennt neben „schon einmal zu einer Spec geworden" ausdrücklich die zweite mögliche Ursache: ein fremder Pull Request, der auf dieses Issue verweist. Ohne diesen Satz würde eine gültige Story fälschlich als erledigt abgewiesen. Die Issue-Freigabe-Policy (`approved-for-agent`, `CLAUDE.md`) ist davon unberührt — sie hängt am Label-Zustand, nicht an der Board-Spalte; eine erzwungene Spalte gibt keine Story frei.

### 3. Die Antwort auf den Einwand: `Done` heißt „vom Board", nicht „ausgeliefert"

Der Einwand aus ADR 0046, Abschnitt 5, trifft eine reale Situation: Wird ein Issue aus einem anderen Grund als dem Abschluss der Arbeit geschlossen — Duplikat, hinfällig, anders gelöst —, setzt `Item closed` es auf `Done`. Er wird hier nicht überstimmt, sondern beantwortet, in drei Schritten.

**Erstens: Der befürchtete Wert ist genau der Wert, den der kontrollierte Pfad ohnehin schreibt.** Der Verwerfen-Pfad in `refinement` (ADR 0037, Abschnitt 6) setzt heute schon `Done` und schließt das Issue — für eine Story, die nie umgesetzt wurde. `.claude/skills/github-board/SKILL.md` hält das ausdrücklich fest: „`Done` schließt das Issue zusätzlich nativ — sowohl für eine umgesetzte als auch für eine ohne Umsetzung verworfene Story (kein eigener Statuswert für den Unterschied)." Der Board-Wert `Done` bedeutet in diesem Projekt seit ADR 0037 **nicht** „ausgeliefert", sondern „dieses Ticket ist vom Board". Ein nativ gesetztes `Done` an einem aus anderem Grund geschlossenen Issue ist deshalb kein Wert, den keine Schreibstelle deckt — es ist der Wert, den die eigene Regel vorschreibt. Der Einwand von 2026-08-30 hat einen Zustand als unkontrolliert beschrieben, der schon damals der vorgesehene war.

**Zweitens: Die Unterscheidung, um die es Daniel geht, trägt ein anderes Feld — und GitHub führt es.** „Geliefert" gegen „verworfen" steht im Close-Grund des Issues (`completed` gegen `not planned`), den GitHub bei jedem Schließen mitführt und in Issue-Liste, Timeline und Projekt-Ansicht mit unterschiedlichem Symbol anzeigt. Diese Information war nie im Statusfeld und geht deshalb auch nicht verloren. Verbindlich wird ab jetzt nur, sie zu setzen: Der Verwerfen-Pfad in `refinement` schließt mit `gh issue close --reason "not planned"`.

**Drittens: Die Sorge „nichts rechnet es zurück" hat ihren Gegenstand verloren.** Sie stammt aus der Zeit der Einbahnstraßen-Architektur (ADR 0017, Abschnitt 4), in der ein voller Sync-Lauf das Board deterministisch aus lokalen Dateien neu berechnete und ein fremder Wert deshalb zu Flip-Flopping führte. Diesen Lauf gibt es seit ADR 0043 nicht mehr — kein Mechanismus rechnet *irgendeinen* Board-Wert zurück, auch keinen selbst geschriebenen. Der befürchtete Zustand unterscheidet sich also nicht von jedem anderen Board-Wert im heutigen System.

**Was bleibt, und was es kostet:** Wird ein geschlossenes Issue **wieder geöffnet**, bleibt der Wert auf `Done` stehen. Einen Workflow „Item reopened" gibt es an unserem Projekt nicht. Das wird als Rest bewusst hingenommen: Wiedereröffnen ist ein seltener Handgriff Daniels am Board selbst, und wer eine Karte wieder aufmacht, sieht sie in der `Done`-Spalte liegen. Der Handgriff dagegen ist derselbe Einzeiler wie jeder andere Statuswechsel — oder ein Ziehen der Karte.

### 4. Der Board-Zugriff sind ab jetzt einzelne `gh`-Befehle in den Skill-Dateien

`scripts/gh-board.py` und `scripts/tests/test_gh_board.py` werden gelöscht. An ihre Stelle tritt kein neues Werkzeug, sondern eine Befehlssammlung in `.claude/skills/github-board/SKILL.md`, aus der die Ablauf-Skills zitieren. Verbindlich sind genau diese Formen:

```bash
# Status setzen (namensbasiert, keine IDs; gh >= 2.97.0)
gh project item-edit 8 --owner TheRealKoller --url <issue-url> --field "Status" --value "<Wert>"

# Priorität setzen (nur nach dem Lesen aus Schritt darunter, siehe Abschnitt 5)
gh project item-edit 8 --owner TheRealKoller --url <issue-url> --field "Priorität" --value "<Hoch|Mittel|Niedrig>"

# Status und Priorität eines Issues lesen - ein Aufruf, konstante Kosten
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

# Story-Issue anlegen und ins Board aufnehmen - bewusst ZWEI Befehle, siehe unten
gh issue create --repo TheRealKoller/photosort --title "<Titel>" --body-file <pfad> --label <idee|bug>
gh project item-add 8 --owner TheRealKoller --url <issue-url> --format json --jq '.id'

# Issue-Body überschreiben
gh issue edit <NNN> --repo TheRealKoller/photosort --body-file <pfad>

# PR<->Issue-Verknüpfung prüfen (siehe Abschnitt 5, Punkt 4)
gh pr view <MMM> --repo TheRealKoller/photosort --json closingIssuesReferences,baseRefName

# Story ohne Umsetzung verwerfen (Abschnitt 3)
gh issue close <NNN> --repo TheRealKoller/photosort --reason "not planned"
```

Vier Festlegungen dazu:

- **Namensbasiert, nicht ID-basiert.** Die ID-Form (`--id`/`--field-id`/`--project-id`/`--single-select-option-id`) funktioniert auch auf älterem `gh`, verlangt aber vier Knoten-IDs als Literale in Skill-Dateien plus einen Auflösungsschritt für die Item-ID. Genau diese Schicht ist der Grund, warum das Werkzeug existierte. Die Namensform hat sie nicht ersetzt, sondern abgeschafft; sie ist beim Lesen verständlich und validiert sich am echten Board statt an einer mitgeführten Liste.
- **`MIN_GH_VERSION` steigt auf `2.97.0`.** Das ist die Version, die die Namensform eingeführt hat (`cli/cli#13807`, Release v2.97.0 vom 31.07.2026); die bisherige Untergrenze 2.72.0 stammt aus ADR 0046 (`closingIssuesReferences`) und ist darin enthalten. Die Konstante verliert mit `gh-board.py` ihre Heimat und zieht nach `docs/setup.md` — die Datei, die sie ohnehin erklärt und in der auch der Setup-Script-Block der Cloud-Umgebung steht. Die CI-Bindung zwischen beiden Angaben (`scripts/tests/test_setup_docs.py`) bleibt bestehen und prüft ab jetzt zwei Angaben innerhalb derselben Datei.
- **Anlegen bleibt zweistufig.** `gh issue create` kennt zwar `--project`, aber `capture` verlässt sich ausdrücklich darauf, dass das Issue auch dann existiert, wenn der Board-Teil scheitert („Schritt 4 hat das Issue angelegt und ist danach an der Board-Aufnahme gescheitert. Das ist kein Abbruch"). Zwei Befehle erhalten diese Eigenschaft, ein kombinierter nicht.
- **Ein `gh api graphql`-Aufruf zum Lesen, bewusst statt `gh project item-list`.** ADR 0017, Abschnitt 1 hat `gh`-Subcommands gegenüber rohen API-Aufrufen bevorzugt; das bleibt die Regel, und der Aufruf hier ist weiterhin `gh` mit dessen Authentifizierung, mit fester Query und einer typisierten Variablen (`-F number=`) statt Textinterpolation. Der Grund für die Ausnahme ist konkret: `gh project item-list` lädt die gesamte Item-Liste (116 Items und wachsend) und hat genau daraus schon einmal einen Fehler erzeugt (Spec 0302). Eine Abfrage, die am Issue ansetzt, hat konstante Kosten und kann diesen Fehler nicht wiederbekommen.

### 5. Was die vier bisherigen Prüfungen ersetzt

Issue #327 verlangt für jede der vier Prüfungen des Werkzeugs einen benannten Ersatz oder eine Begründung des Wegfalls. Einzeln:

**5.1 Zurückweisung ungültiger Status- und Prioritätswerte** — *ersetzt, und zwar besser.* `gh project item-edit --field/--value` löst den Optionsnamen am echten Board auf und bricht bei einem unbekannten Wert mit Exit-Code 1 und der Liste der gültigen Optionen ab (am eigenen Board gemessen). Die bisherige Prüfung verglich gegen die Konstanten `STATUS_VALUES`/`PRIORITY_VALUES` im Script — eine mitgeführte Kopie, die vom Board abdriften konnte und bei jeder Board-Änderung nachzuziehen war. Der Ersatz kann nicht abdriften.

**5.2 Ein bereits erreichter Zielzustand gilt als Erfolg** — *entfällt, weil seine Ursache entfällt.* ADR 0048 hatte zwei Auslöser. Der erste: `gh issue close` auf ein Issue, das der Workflow `Auto-close issue` unmittelbar zuvor schon geschlossen hatte. Diesen Aufruf gibt es nicht mehr — im Regelweg schließt der Merge das Issue (Abschnitt 6), keine Session. Der zweite: ein wiederholter `finalize`-Lauf, der die schon geschriebene Spec-Statuszeile erneut schreiben wollte. Das ist ab jetzt eine gewöhnliche lokale Dateiänderung durch den Ablauf selbst; sie ein zweites Mal zu schreiben ändert nichts und scheitert an nichts. Das *Prinzip* aus ADR 0048, Abschnitt 1 — Maßstab ist der Zielzustand, nicht die Urheberschaft dieses Aufrufs — bleibt in Kraft und ist im neuen Zuschnitt strukturell erfüllt statt eigens hergestellt: `item-edit` auf den bereits gesetzten Wert ist ein erfolgreicher Aufruf (gemessen), weil er einen Zustand setzt und keinen Übergang ausführt.

**5.3 Priorität first-write-wins** — *ersetzt, mit einem benannten Verlust.* `refinement` liest vor dem Schreiben (der Lesebefehl aus Abschnitt 4 liefert Status und Priorität in einem Aufruf) und setzt die Priorität nur, wenn das Feld leer ist. Die Zusicherung aus ADR 0044, Abschnitt 2 — ein von Daniel gesetzter Wert wird nie überschrieben — bleibt damit erhalten. Verloren geht ihre Atomarität: Zwischen Lesen und Schreiben liegt ein Fenster. Das ist folgenlos, weil es genau einen Schreiber gibt (Daniels Session, ein Ablauf zur Zeit) und das Fenster im ungünstigsten Fall bedeutet, dass eine im selben Moment von Hand gesetzte Priorität überschrieben wird — ein Fall, den es nicht gibt und dessen Behebung ein Werkzeug kostete, das genau hier abgeschafft wird.

**5.4 Beim Abschluss wird geprüft, dass PR und Issue verknüpft sind** — *ersetzt, doppelt.* Erstens als Schritt in `ship-feature` vor dem Merge: `gh pr view <MMM> --json closingIssuesReferences,baseRefName`, geprüft wird ein repo-qualifiziert passender Eintrag auf die Issue-Nummer und der Default-Branch `main` — inhaltlich exakt die Prüfung aus ADR 0046, Abschnitt 3, nur an einer anderen Stelle. Zweitens, und das ist der eigentliche Ersatz, **strukturell**: `Done` entsteht ab jetzt ausschließlich dadurch, dass der Merge das Issue über das Keyword schließt. Fehlt die Verknüpfung, passiert nichts Falsches — die Story bleibt sichtbar auf `Review` stehen, während der PR gemergt ist.

Damit ist auch das Argument beantwortet, mit dem ADR 0046 diese Prüfung ausdrücklich zu Code statt zu einer Skill-Zeile gemacht hat („Der Schaden einer vergessenen Zeile fällt erst nach dem Merge auf, wenn sie nicht mehr nachtragbar ist"). Er galt, solange `finalize` selbst `Implemented` schrieb und das Issue selbst schloss: Dann sah das Ergebnis auch ohne Verknüpfung vollständig aus. Ab jetzt ist der Schaden **sichtbar** (eine gemergte Story hängt auf `Review`) und **nachtragbar** (Issue von Hand schließen → `Done`). Eine Prüfung, deren Versäumnis sich selbst anzeigt, braucht keinen Torwächter aus Code mehr.

### 6. Ein Fehlschlag bleibt sichtbar — und kann eine Story nie zu weit vorne erscheinen lassen

Drei Festlegungen, die zusammen das Akzeptanzkriterium tragen:

1. **Kein Urteil vor dem Versuch.** ADR 0052, Abschnitt 2/3 bleibt tragend: Der Befehl wird abgesetzt, nicht vorab beurteilt. Die Vorabmessung `capabilities` (ADR 0056) entfällt ersatzlos — ihr Zweck war, vier Board-Schritte gar nicht erst zu versuchen, von denen jeder einen mehrstufigen Werkzeugaufruf bedeutete. Übrig sind zwei Schritte, die je ein einzelner Befehl sind; ihn zu versuchen kostet nicht mehr als ihn zu messen, und ist ehrlicher.
2. **Eine fehlgeschlagene Board-Operation wird gemeldet, nie geschluckt.** `gh` beendet sich mit einem Code ≠ 0 und einer Meldung. Der Ablauf bricht deswegen nicht ab (die eigentliche Arbeit ist wichtiger als ihr Etikett), führt aber den Schritt im Abschnitt `## Lokal nachzuholen` seines Berichts auf — mit dem unverändert wiederholbaren Befehl. Die Konvention selbst (welcher Text hineindarf, welcher nicht) bleibt wörtlich wie in `.claude/skills/github-board/SKILL.md` etabliert und wandert nur von einem Werkzeug-Rahmen in einen Befehls-Rahmen.
3. **Struktureller Schutz gegen zu weit fortgeschrittene Anzeige.** Beide verbliebenen Session-Schreibzugriffe bewegen den Wert vorwärts und stehen **vor** der Arbeit, die sie ankündigen: `Ready` vor der Übergabe an `spec-writer`, `In Progress` vor dem Anlegen von Branch und Spec. Ein Fehlschlag lässt die Story deshalb immer auf dem **früheren**, konservativeren Wert stehen. Eine Story kann durch einen fehlgeschlagenen Board-Zugriff nie weiter fortgeschritten erscheinen, als sie ist — nur weniger weit. Die nativen Übergänge können diesen Fehler per Konstruktion nicht machen: Sie feuern auf ein Ereignis, das bereits eingetreten ist.

4. **Ein ausgebliebener nativer Übergang wird bemerkt.** Mit drei von fünf Übergängen auf GitHubs Seite dreht sich die Richtung des Fehlers um: Bisher war der Fehlerfall ein *falscher* Wert und fiel dadurch auf; ein versehentlich deaktivierter Workflow schreibt dagegen **gar nichts**, und eine Karte, die auf `In Progress` liegen bleibt, ist von einer Karte, an der gerade gearbeitet wird, nicht zu unterscheiden. Der Zustand der Workflows ist per API weder les- noch überwachbar (siehe Konsequenzen). Deshalb liest `ship-feature` nach dem Eröffnen des Pull Requests den Board-Wert **einmal zurück** — mit dem Lesebefehl aus Abschnitt 4, der ohnehin in der Sammlung steht — und führt ein ausgebliebenes `Review` unter `## Lokal nachzuholen` auf. Ein zusätzlicher Befehl pro Story, der zugleich die Probe aus Abschnitt 2 dauerhaft macht, statt sie einmalig am Pull Request dieser Story zu belassen. Am 2026-09-05 gegen „als bekannte Lücke akzeptieren" abgewogen und von Daniel entschieden.

### 7. Remote-Sessions: die Grenze bleibt, aber sie schrumpft von vier Schritten auf zwei

Der Befund aus ADR 0056 gilt unverändert: In Cloud-Sessions bedient die Zwischenschicht GraphQL nur für einen festen Satz von PR-Operationen, und GitHub Projects (V2) spricht ausschließlich GraphQL. Jeder Board-Zugriff aus einer solchen Session scheitert — mit `gh project item-edit` genauso wie zuvor mit `gh-board.py`. Ein Werkzeugwechsel ändert daran nichts, und diese ADR behauptet nichts anderes.

Was sich ändert, ist der **Umfang** der Grenze. Drei der fünf Übergänge laufen ab jetzt auf GitHubs Servern und sind von der Sperre der Session gar nicht berührt: `Unrefined` (sobald das Item im Projekt ist), `Review` (sobald der PR verlinkt ist), `Done` (sobald der Merge das Issue schließt). Übrig bleiben `Ready` und `In Progress`. Eine remote begonnene Story landet damit **von selbst** korrekt auf `Review` und `Done` — genau die beiden Schritte, die bisher am Ende einer langen Arbeit standen und deren Ausfall am teuersten war.

Was remote weiterhin ausfällt: `Ready`, `In Progress` und die Board-Aufnahme eines neu angelegten Issues (`gh project item-add`) — letztere zieht `Unrefined` mit, weil ohne Item auch kein „Item added" feuert. Alle drei werden versucht, ihr Fehlschlag wird nach Abschnitt 6 gemeldet und ist ein Einzeiler zum Nachholen.

### 8. Ein Pull Request, der ohne Merge geschlossen wird, setzt die Story auf `In Progress` zurück

GitHub löst dabei nichts aus (das Issue bleibt offen), also schreibt die Session, die den PR schließt. `In Progress` und nicht `Ready`, weil die Umsetzung nachweislich begonnen hat: Spec und Branch existieren. `In Progress` und nicht `Review`, weil es keinen Review mehr gibt und eine Karte, die auf `Review` liegen bleibt, genau die Karteileiche wäre, die diese ADR abschafft.

Soll die Story stattdessen ganz zurück in den Vorrat (Branch und Spec werden verworfen), ist das ein bewusster Handgriff Daniels: Karte auf `Ready` ziehen. Es gibt dafür keine Automatik, weil die Unterscheidung „Branch bleibt für einen zweiten Anlauf" gegen „Branch ist weg" nur der Mensch kennt.

Wird der PR außerhalb einer Session geschlossen (Daniel auf GitHub), bleibt der Wert auf `Review` stehen. Auch das ist ein bewusst hingenommener Rest derselben Art wie das Wiedereröffnen in Abschnitt 3 — sichtbar, an einer Stelle, an der Daniel ohnehin gerade steht, und mit einem Einzeiler behoben.

### 9. Die Umstellung selbst: vier Items umsetzen, dann die Option entfernen

Reihenfolge zwingend, weil GitHub die Option nicht entfernt, solange Items sie tragen — und weil eine entfernte Option ihre Items wertlos zurückließe:

1. Die vier Issues auf `Todo` (#162, #167, #169, #174) auf `Ready` setzen. Alle vier tragen einen vollständig geschärften Issue-Body (`## Ziel`, `## User Story`, `## Akzeptanzkriterien`) und an keinem wird gearbeitet — das ist die Definition von `Ready`. Dass für #162/#167/#169 zusätzlich schon eine akzeptierte Spec-Datei im Repo liegt, ändert daran nichts; es ist Vorarbeit, kein Zustand. `spec-writer` überspringt bei ihnen das Anlegen und arbeitet mit der vorhandenen Datei weiter.
2. Die Option `Todo` aus dem Feld `Status` entfernen — per `updateProjectV2Field` mit `singleSelectOptions`, in dem die fünf verbleibenden Optionen mit ihren bestehenden IDs erneut gesendet werden. Kein Löschen und Neuanlegen des Feldes, kein Datenverlust, keine Migration der übrigen 112 Items (anders als bei allen bisherigen Feld-Änderungen, ADR 0030 Abschnitt 3 / ADR 0037 Abschnitt 7).

Beides sind schreibende Eingriffe am Live-Board und liegen deshalb beim Orchestrator bzw. bei Daniel, nicht beim `developer` (der keinen GitHub-Schreibzugriff hat). Sie gehören **vor** die Umstellung der Skill-Dateien: Ein Skill, der `Todo` nicht mehr kennt, während die Spalte noch existiert, ist folgenlos; eine entfernte Spalte, auf die ein Skill noch schreibt, ist ein Fehlschlag mitten im Ablauf.

## Begründung

- **Warum der ganze Umbau und nicht eine der billigeren Teillösungen:** Nur die tote Spalte zu streichen ließe 1.500 Zeilen Werkzeug für fünf statt sechs Werte stehen — dieselbe Pflegelast für eine Kosmetik. Nur die nativ erkennbaren Übergänge abzugeben ließe das Werkzeug für die verbleibenden zwei stehen, also die volle ID-Auflösungs-, Fehler- und Testmaschinerie für zwei Einzeiler. Beide Hälften erzeugen ihren Ertrag erst zusammen: Die nativen Übergänge nehmen dem Werkzeug drei seiner fünf Aufgaben, und die Namensform von `gh` nimmt ihm die Existenzberechtigung für den Rest. Issue #327 hat beide Teillösungen ausdrücklich verworfen; diese ADR begründet, warum das richtig war.
- **Warum die Token-Ersparnis ausdrücklich nicht die Begründung ist:** Ein Board-Schreibzugriff kostet praktisch nichts. Was trägt, ist der Wartungsaufwand (sechs Nachbesserungsrunden in fünf Wochen) und ein Ablauf, der zur tatsächlichen Arbeitsweise passt. Das ist hier festgehalten, damit eine spätere Lektüre die Entscheidung nicht an einem Argument misst, das sie nie getragen hat.
- **Warum die Umkehrung von ADR 0037/0046/0052 keine Kehrtwende ist:** Alle drei haben native Automatisierung mit derselben Begründung ausgeschlossen — ein zweiter, unkontrollierter Schreiber neben dem getesteten Tool-Layer, in einer Architektur, in der ein voller Sync-Lauf das Board deterministisch neu berechnete. Diese Architektur gibt es seit ADR 0043 nicht mehr. Es rechnet nichts mehr zurück, also kann es auch nichts mehr gegen einen Fremdschreiber zurückrechnen; „unkontrolliert" hat seinen Bezugspunkt verloren. Was 2026-08-27 richtig war, ist 2026-09-05 gegenstandslos — nicht, weil die Bewertung sich geändert hat, sondern weil ihr Gegenstand verschwunden ist.
- **Warum `Done` gerade nicht auf einen eigenen Wert für „verworfen" aufgeteilt wird:** Ein sechster Statuswert (`Verworfen`) wäre nur von einer Session setzbar; damit wäre der Übergang, den GitHub am zuverlässigsten erkennt, wieder von einer laufenden Session abhängig. Der Preis für eine Unterscheidung, die GitHub im Close-Grund bereits sichtbar führt, wäre der Kern dieser ADR.
- **Warum die Skills die Befehle wörtlich tragen und kein dünner Wrapper übrig bleibt:** Ein Wrapper um `gh project item-edit --field --value` hätte genau eine Aufgabe — das Wiederholen von `8 --owner TheRealKoller`. Dafür ein Script mit Testsuite, CI-Job und eigener Fehlerkonvention zu unterhalten, ist der Zustand, der hier abgeschafft wird. Die Wiederholung von zwei konstanten Argumenten ist in einer Skill-Datei billiger als jede Abstraktion darüber.
- **Warum `In Progress` an den Anfang von `spec-writer` und nicht an den Start des `developer` wandert:** Der `developer` hat weiterhin keinen GitHub-Schreibzugriff (ADR 0037, Abschnitt 3, hatte das mit einem Hinweis an den Aufrufer gelöst). Diese Grenze bleibt unangetastet — sie wird nur nicht mehr gebraucht, weil der Zeitpunkt ohnehin früher liegt: bei `spec-writer`, der Schreibzugriff hat.
- **Warum die Prüfung der PR↔Issue-Verknüpfung von Code zu einer Skill-Zeile werden darf, obwohl ADR 0046 das Gegenteil entschied:** Weil sich die Folge ihres Versäumnisses geändert hat, nicht die Prüfung. ADR 0046 begründete die Code-Form damit, dass der Schaden nach dem Merge nicht mehr nachtragbar sei. Das galt für einen Ablauf, in dem `finalize` das Issue selbst schloss und die Spec selbst auf `Implemented` setzte — ohne Verknüpfung sah das Ergebnis vollständig aus, obwohl es das nicht war. Jetzt zeigt sich das Versäumnis am Board von selbst und ist mit einem Handgriff zu heilen.
- **Warum kein Ersatz für `doctor`:** Sein Wert lag darin, neun Prüfungen einzeln zu stellen und ihre Antworten nebeneinanderzulegen, weil eine Handvoll manueller Befehle beim ersten Fehler abbricht (ADR 0052, Begründung). Der Gegenstand dieser Diagnose waren acht Lebenszyklus-Schritte mit vier Board-Anteilen. Davon bleiben zwei Board-Schreibzugriffe, deren Fehlschlag eine einzige, eindeutige Ursache hat und deren Meldung `gh` selbst liefert. Ein Diagnosewerkzeug für zwei Einzeiler wäre größer als sein Gegenstand.
- **Warum die vier `Todo`-Issues nach `Ready` und nicht geschlossen werden:** Sie sind vergessen, nicht erledigt und nicht verworfen. Drei von ihnen tragen eine akzeptierte Spec, alle vier eine geschärfte Story. Sie zu schließen hieße, Arbeit wegzuwerfen, um eine Spalte zu leeren; sie auf `In Progress` zu setzen hieße, das Problem dieser Story (eine Spalte behauptet etwas, das nicht stimmt) in eine andere Spalte zu verschieben.

## Konsequenzen

- **Gelöscht:** `scripts/gh-board.py` (1.536 Zeilen), `scripts/tests/test_gh_board.py` (3.294 Zeilen). Der CI-Job `demo-scripts` bleibt (Seed-Script, `test_setup_docs.py`); sein erklärender Kommentar in `.github/workflows/ci.yml` wird nachgezogen.
- **`.claude/skills/github-board/SKILL.md`:** wird von einem Script-Wrapper zu der Befehlssammlung aus Abschnitt 4 plus der Lebenszyklus-Tabelle aus Abschnitt 2, der Fehlerregel aus Abschnitt 6 und der `## Lokal nachzuholen`-Konvention (wörtlich erhalten). Die Abschnitte zu `doctor`, `capabilities`, `finalize` und zur Vorabmessung entfallen.
- **`.claude/skills/capture/SKILL.md`:** Schritt „Board-Fähigkeit messen" entfällt; Issue-Anlage und Board-Aufnahme werden zwei `gh`-Befehle; `Unrefined` wird nicht mehr gesetzt, sondern entsteht nativ.
- **`.claude/skills/refinement/SKILL.md`:** Schritt 6 wird `gh issue edit` + Prioritäts-Lesen + bedingtes Prioritäts-Schreiben + `Ready`; der Verwerfen-Pfad aus Schritt 5 wird `gh issue close --reason "not planned"` (der Board-Wert `Done` entsteht nativ). Die Reihenfolge Body → Priorität → Status bleibt (ADR 0044, Abschnitt 4).
- **`.claude/skills/spec-writer/SKILL.md`:** Schritt 0 liest den Status per GraphQL-Einzeiler und setzt anschließend `In Progress` — vor Branch und Spec-Datei. Das `set-status Todo` am Ende von Schritt 4 entfällt ersatzlos. Neu: Existiert bereits eine Spec-Datei zur Issue-Nummer (die drei Altlasten aus Abschnitt 9), wird sie weiterverwendet statt eine neue anzulegen.
- **`.claude/skills/ship-feature/SKILL.md`:** Schritt 2.4 (Board-Fähigkeit messen) entfällt. Schritt 6.4 (`set-status Review`) entfällt im Regelfall — der Wert entsteht nativ (Rückfallebene siehe Abschnitt 2). Schritt 8 wird: Verknüpfung prüfen (`gh pr view --json closingIssuesReferences,baseRefName`), dann die `**Status:**`-Zeile der Spec-Datei lokal auf `Implemented ([PR #MMM](url))` setzen und mit den letzten Fixes pushen. **Das Issue wird nicht mehr vor dem Merge geschlossen und `Done` nicht mehr vorgezogen** (ADR 0042, Abschnitt 4 abgelöst) — beides entsteht beim Merge. Neu: Wird der PR ohne Merge geschlossen, `In Progress` zurücksetzen (Abschnitt 8).
- **`.claude/agents/developer.md`:** Der „Hinweis an den Aufrufer" (Statusfeld auf `In Progress` setzen) entfällt — der Wert steht zu diesem Zeitpunkt längst.
- **`docs/setup.md`:** neue Heimat der Mindestversion (`2.97.0`), Begründung nachgezogen (Namensform von `gh project item-edit`, nicht mehr allein `closingIssuesReferences`); `GH_VERSION` im dokumentierten Setup-Script-Block angehoben; sämtliche Absätze zu `doctor`/`capabilities` sowie der Remote-Abschnitt neu gefasst nach Abschnitt 7.
- **`scripts/tests/test_setup_docs.py`:** bindet den `GH_VERSION`-Block ab jetzt an die Prosa-Angabe in derselben Datei statt an eine Konstante im gelöschten Script. Zusätzlich ein neuer Test, der festhält, dass keine Skill-, Agent- oder `docs/`-Datei mehr auf `gh-board.py` verweist (`CHANGELOG.md` und `specs/` ausgenommen — dort ist die Erwähnung historisch korrekt).
- **`docs/ai-workflow.md`:** Lebenszyklus ohne `Todo`, Auslöser-Spalte nach Abschnitt 2, der Satz zur Vorabmessung entfällt.
- **Kein Effekt auf `docs/architecture.md` / Root-`README.md`** — reines Entwickler-/Prozess-Tooling ohne Bezug zur Laufzeitarchitektur oder zum Datenmodell der Anwendung, gleiche Einordnung wie ADR 0037/0043/0046/0052/0056.
- **Kein neues Secret, keine neue Abhängigkeit, keine neue Datei unter `.github/workflows/`.** Der `project`-Scope der bestehenden `gh`-Anmeldung reicht unverändert.
- **Manuelle Schritte, nicht skriptbar (Daniel, Projekt-UI „PhotoSort Roadmap" → Workflows):** `Item added to project` einschalten → `Unrefined`; `Pull request linked to issue` einschalten → `Review`; `Item closed` einschalten → `Done`. `Auto-close issue` und `Auto-add sub-issues to project` bleiben unverändert an, `Pull request merged` bleibt aus. Grund für die Handarbeit: GraphQL kennt für Workflows nur `deleteProjectV2Workflow`, kein Aktivieren und kein Konfigurieren (am Schema geprüft).
- **Manueller Schritt außerhalb des Repositories:** `GH_VERSION` im Setup-Script der Cloud-Umgebung (Weboberfläche) auf `2.97.0` anheben — der in `docs/setup.md` seit ADR 0053/0054 als Pflichtschritt benannte letzte, ungesicherte Übergang.
- **Einmalige Board-Umstellung (Orchestrator/Daniel, nicht `developer`):** vier Items von `Todo` auf `Ready`, danach die Option `Todo` per `updateProjectV2Field` entfernen (Abschnitt 9).
- **Issue [`#305`](https://github.com/TheRealKoller/photosort/issues/305)** wird mit dem Abschluss der zugehörigen Story geschlossen.
- Ein späterer Wechsel dieses Modells — zurück zu einem eigenen Werkzeug, zu einem sechsten Statuswert oder zu abgeschalteten nativen Workflows — bleibt architekturrelevant und braucht eine neue ADR, die diese hier als „Superseded" markiert.
