# 0108 - Die Nummer folgt dem Rang des Arbeitsstands, nicht dem Zeitpunkt des Merges

**Status:** Accepted
**Datum:** 2026-09-14
**Bezug:** GitHub-Issue [`#485`](https://github.com/TheRealKoller/photosort/issues/485), Spec
`specs/features/0485-*.md`

## Kontext

Vier Arbeitsstände laufen gleichzeitig, und zwei vergeben regelmäßig dieselbe Nummer — für ein
Entscheidungsdokument oder für eine Alembic-Revisions-ID. Die konkurrierende Vergabe liegt dabei in
einem Branch, der noch nirgends gepusht ist: Gemessen am 2026-09-14 endet `origin/main` bei ADR
`0105`, während ein nicht gepushter Nachbar-Arbeitsstand bereits `0106` **und** `0107` führt. Ein
Wächter im CI-Job kann das strukturell nicht sehen — dort gibt es weder einen zweiten Arbeitsbaum
noch einen ungepushten Branch.

ADR [`0081`](./0081-dokumentnummer-ist-identitaet-die-juengere-dublette-zieht-um.md) Punkt 2
bestimmt das umzugspflichtige Dokument als dasjenige, dessen einführender Commit später auf `main`
liegt — bei zwei ungemergten Branches liegt keiner dort. Punkt 3 („die nächste freie Nummer") ist
für beide Seiten dieselbe Rechnung und führt deshalb zweimal auf dasselbe Ergebnis.

Diese ADR überschreitet den Richtwert von ~100 Zeilen, weil sie zwei getrennte Nummernräume mit je
eigener Mechanik regelt und zusätzlich festlegt, wo geprüft wird — die Aufteilung auf mehrere ADRs
hätte genau die verteilte Zuständigkeit erzeugt, gegen die Akzeptanzkriterium 5 gerichtet ist.

## Entscheidung

### 1. Die Belegtmenge umfasst jeden aktiven Arbeitsstand, nicht nur den eigenen

Belegt ist eine Nummer, sobald sie in einer dieser Quellen auftaucht: `origin/main`; der eigene
Arbeitsbaum einschließlich noch nicht hinzugefügter Dateien; jeder weitere Arbeitsbaum aus
`git worktree list` — sowohl sein ausgechecktes Verzeichnis als auch der committete Stand seines
Branches; sowie jeder gepushte Branch, der nicht in `origin/main` enthalten ist.

Alle vier Quellen sind ohne Abstimmung mit einer anderen Sitzung lesbar: Die Arbeitsbäume teilen
sich einen Ref-Speicher, und `git ls-tree <branch>` liest den Stand eines Nachbarbranches aus dem
eigenen Arbeitsbaum heraus.

### 2. Die Basis ist der Stand auf `origin/main`, nie der eigene Blick

Basis ist die höchste auf `origin/main` vergebene Nummer des Verzeichnisses, plus eins. Sie hängt
nicht davon ab, welche Nachbarn ein Lauf gerade sieht — sonst errechnete jede Seite eine andere
Basis, je nachdem, wer wann geschrieben hat.

### 3. Bei Kontention entscheidet der Branchname, und er entscheidet immer

Kontrahenten sind alle Branches nach Punkt 1, die im selben Nummernraum eine Nummer ≥ Basis führen,
zuzüglich des eigenen Branches. Sie werden nach ihrem vollständigen Namen byteweise aufsteigend
sortiert. Zugeteilt wird dann in zwei Gängen über der gesamten Kontrahentenmenge:

1. **In Rangfolge behält jeder Kontrahent seine niedrigste sichtbar geführte Nummer**, sofern eine
   rangniedrigere Seite sie nicht bereits beansprucht hat. Ein Dokument zieht damit nur um, wenn
   seine Nummer einer rangniedrigeren Seite zusteht — nie aus Rechenmechanik heraus.
2. **Wer nichts behalten konnte** — weil er noch keine Datei angelegt hat oder weil eine
   rangniedrigere Seite dieselbe Nummer führte —, bekommt, wieder in Rangfolge, die nächste Nummer
   ab der Basis, die **kein** Kontrahent führt.

**Gezählt wird nicht.** Eine Zuteilung, die nur die Anzahl der von rangniedrigeren Kontrahenten
geführten Nummern auf die Basis addiert, ist ausschließlich dann kollisionsfrei, wenn diese Nummern
lückenlos ab der Basis liegen; andernfalls teilt sie Nummern zu, die andere Branches bereits
führen. Eine Lücke entsteht ohne jede Handvergabe: Nach Punkt 1 ist ein Branch ohne Arbeitsbaum und
ohne `origin`-Gegenstück kein Kontrahent mehr, und wer die Basisnummer führte, hinterlässt beim
Verschwinden genau diese Lücke.

Der Branchname trägt diese Ordnung, weil git denselben Branch nie in zwei Arbeitsbäumen auscheckt:
Er ist ohne Abstimmung eindeutig, beiden Seiten bekannt und von keiner Seite zu den eigenen Gunsten
zu wählen. Ein bereits nach `origin/main` übernommenes Dokument ist nie Kontrahent, sondern Teil
der Basis — es behält seine Nummer ausnahmslos.

Die Regel entscheidet damit auch dann, wenn **kein** Beteiligter gemergt ist.

### 4. Eine Nummer gilt als vergeben, sobald ihre Datei im Arbeitsbaum liegt

Es gibt keine gemerkte, noch nicht geschriebene Nummer: Wer eine zugeteilt bekommt, legt die Datei
unmittelbar an. Erst dadurch wird sie für die Nachbarn sichtbar.

Greifen zwei Läufe im verbleibenden Fenster doch zur selben Nummer, ist das kein Sonderfall: Beim
nächsten Lauf des Zuteilers sehen beide dieselbe Kontrahentenmenge, rechnen nach Punkt 3, und die
rangniedrigere Seite behält. Keine Seite benachrichtigt die andere, keine wartet auf eine
Bestätigung, keine zweite Runde ist nötig.

### 5. Migrationen: die Kennung kommt aus dem Branch, die Kette aus `origin/main`

Eine Alembic-Revisions-ID wird nicht mehr von Hand als Hex-Folge gewählt, sondern als die ersten
zwölf Hex-Zeichen aus `sha256(<Branchname> + NUL + <Slug>)` abgeleitet. Nach Punkt 3 ist der
Branchname ohne Abstimmung eindeutig; eine doppelt vergebene Kennung ist damit nicht mehr
aufzulösen, sondern konstruktiv ausgeschlossen, und dieselbe Eingabe liefert bei jedem Lauf
dieselbe Kennung. Preis: Die neue Kennung sieht anders aus als die 35 bestehenden, deren scheinbar
fortlaufende Form genau die Kollisionsquelle war.

`down_revision` ist der Kopf der aufgelösten Kette des Arbeitsstands — solange der Branch keine
eigene Migration trägt, ist das genau der Head von `origin/main`. Trägt er bereits eine, hängt die
nächste hinter der eigenen: Setzten beide auf den Head von `origin/main`, hätte die Kette zwei
Köpfe, und `alembic upgrade head` bräche beim Containerstart ab. Verschiebt sich der Head, während
der Branch offen ist, hängt sich die eigene Migration beim Abgleich mit `main` selbsttätig und **ohne
Rückfrage** hinter den neuen Head; die bereits übernommene Migration wird nie angefasst. Bei
mehreren eigenen Migrationen wird nur die unterste umgehängt, die eigene Reihenfolge bleibt.

Welche Reihenfolge festgelegt wurde, ist ohne Lesen der Migrationsdateien erkennbar: Der Zuteiler
druckt die aufgelöste Kette auf Verlangen, und ein Umhängen wird im Abschlussbericht des Abgleichs
als eigene Zeile (`<eigene Revision> hinter <neuer Head> gehängt`) ausgewiesen.

### 6. Der Zuteiler läuft lokal; das Sicherheitsnetz in CI bleibt unberührt

Die Früherkennung ist ein lokales Skript, aufgerufen an den Stellen, an denen eine Nummer entsteht
— kein CI-Job (der zu prüfende Zustand existiert dort nicht) und kein Hook (die Hook-Konfiguration
liegt nicht im Repository und wäre weder testbar noch für Hintergrundläufe zugesichert).

`test_dokumentnummern_eindeutig.py` und `test_migration_chain.py` bleiben wortgleich in Kraft und
laufen unverändert in CI weiter. Was heute spätestens beim Zusammenführen laut wird, wird weiterhin
laut; die Frühwarnung tritt daneben, nie an ihre Stelle. Der nachbarlesende Teil des Zuteilers ist
in CI wirkungslos, weil es dort keine Nachbarn gibt — das wird im Skript benannt, statt eine grüne
CI als Beleg für eine Prüfung auszugeben, die dort nichts gesehen hat.

### 7. Eine Umbenennung nach der Prüfrunde wird nachgeprüft

Ein Abgleich mit `main` liegt hinter der Review-Phase und kann eine Kollision erst dort sichtbar
machen. Ändert der Lauf daraufhin noch Nummern-Token, Dateinamen oder ein `down_revision`, läuft
`review-architecture` auf dem neuen Diff erneut, zusammen mit dem Zuteiler und dem vollen Lauf der
Repo-Konsistenztests. Berührt die Nachänderung mehr als diese drei Dinge, läuft die vollständige
Review-Runde erneut.

## Begründung

- **Rang statt Alter:** „Wer ist jünger" ist bei zwei ungemergten Branches nicht beantwortbar.
  „Welcher Branchname steht vorn" ist es immer, für beide Seiten gleich.
- **Ausschließen statt auflösen:** Eine Migrationskennung trägt keine Bedeutung, die eine Handwahl
  rechtfertigte — und damit keinen Grund, die Kollision überhaupt möglich zu lassen.
- **Lokal statt CI:** Eine Prüfung am Ort, an dem der zu prüfende Zustand gar nicht existiert, ist
  grün, ohne etwas zu wissen.

## Konsequenzen

- ADR 0081 trägt einen Teil-Vermerk für Punkt 2 und den ersten Satz von Punkt 3. Ihre Punkte 1, 4,
  5 und 6 gelten unverändert weiter, insbesondere das fundstellengenaue Umschreiben mit Bilanz und
  die `**Frühere Nummer:**`-Kopfzeile der umgezogenen Datei — ebenso der zweite Satz von Punkt 3:
  Eine frei gewordene Nummer wird nie ein zweites Mal vergeben.
- `specs/features/` bleibt außen vor: Dort vergibt GitHub die Nummer mit dem Issue (ADR 0043), und
  zwei Läufe können sie nicht doppelt ziehen. Der Zuteiler lehnt dieses Verzeichnis mit einer
  Meldung ab, statt still eine Nummer zu liefern.
- Diese ADR ist der erste Anwendungsfall ihrer eigenen Regel: Basis `0106`, ein rangniedrigerer
  Kontrahent mit zwei geführten Nummern, Ergebnis `0108`.
- Kein Effekt auf Systemarchitektur, lokales Setup und Rollenmodell — `docs/` bleibt unberührt.
