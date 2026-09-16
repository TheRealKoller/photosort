# 0113 - Motivstärke als Füllstandssymbol: Bandfarbe statt Balkenliste

**Status:** Accepted
**Datum:** 2026-09-16
**Bezug:** Spec [`features/0490-motivstaerke-kompakt.md`](../features/0490-motivstaerke-kompakt.md),
ADR [`0091`](./0091-motive-mit-staerke-statt-hauptkategorie.md) (Stärkevektor und Korrektur, hier
gelesen und nicht geändert)

## Kontext

Die acht Motivstärken stehen als Liste aus Balken und Prozentzahlen und brauchen rund 290 px Höhe —
neben dem Foto, das beurteilt werden soll. Die Stärke soll in einer Zeile aus acht Symbolen stehen,
deren Füllhöhe und Füllfarbe den Wert tragen. Damit treffen drei bestehende Zusagen aufeinander: die
Bänder der Statistik gelten am Einzelwert nicht, der Symbolsatz ist auf zwölf geschlossen, und
Bedienelemente sind auf 44 px treffbar.

## Entscheidung

### 1. Die Farbstufe kommt aus `strength_bands`, nie aus `present`

Die Füllfarbe eines Symbols entsteht aus der wirksamen Stärke gegen die beiden Grenzen aus
`GET /motifs`:

| wirksame Stärke | Füllung |
|---|---|
| `>= strength_bands.strong` | `--status-success` |
| `>= strength_bands.medium` | `--status-running` |
| `> 0` | `--status-failed` |
| `=== 0` oder lokal nicht beurteilbar | keine Füllung, Umriss in `--text-muted` |

**`MotifStrengthOut.present` wird für die Farbe nicht gelesen.** Die Präsenzgrenze liegt bei 0.5 und
damit mitten im mittleren Band: Aus beiden Skalen zugleich entstünde für dieselbe Stärke einmal
„mittel" und einmal „nicht vertreten", und die Stufe „schwach" wäre unerreichbar, weil unterhalb 0.5
kein Motiv als vorhanden gilt. `present` bleibt unverändert die einzige Aussage über Zugehörigkeit
und wird weiterhin ausschließlich dort gelesen, wo über Zugehörigkeit entschieden wird.

**Das Bandwort bleibt außerhalb der Statistiktabelle verboten.** Die Zusage der Spec 0427 gilt
weiter für den Text und wird nur für die Farbe aufgehoben: Am Einzelwert erscheint nie „stark",
„mittel" oder „schwach", sondern der genaue Prozentwert. Eine Korrektur setzt die wirksame Stärke
bereits auf 1.0 bzw. 0.0; in der Symbolreihe ist sie deshalb von einer gleich hohen Modellaussage
nicht zu unterscheiden — das Korrekturwort steht in der aufgeklappten Zeile.

### 2. Der Füllstand entsteht aus zwei übereinanderliegenden Symbolen

Das Symbol wird zweimal gezeichnet: unten vollständig in `--text-muted`, darüber deckungsgleich in
der Bandfarbe, beschnitten auf die unteren `strength`-Prozent seiner Höhe. Der Beschnitt steht als
`clip-path`-Rezept an genau einer Stelle (`@layer utilities` in `index.css`), die Aufrufstelle
übergibt nur den Prozentwert als CSS-Variable.

**Kein Verlauf und keine Maske im SVG.** Beide verlangen je Symbol eine eindeutige Id im Dokument
und damit einen Eingriff in `ui/icon.tsx` — die Datei, deren Ausgabe zugleich der Penpot-
Schnappschuss ist.

### 3. Der Symbolsatz wird um genau acht Namen geöffnet, die Zuordnung lebt im Frontend

`ICONS` in `frontend/src/components/ui/icon.tsx` wächst auf zwanzig Einträge: `user-round`,
`mountain-snow`, `landmark`, `building-2`, `paw-print`, `utensils`, `footprints`, `sparkles`.

Die Zuordnung Motivschlüssel → Symbolname steht im Frontend (`utils/motifIcons.ts`), nicht als Feld
an `MotifOut`. Ein Symbolname ist eine Eigenschaft des ausgelieferten Symbolsatzes, nicht des
Motivs: Das Backend könnte nur einen Namen nennen, dessen Bestand es nicht kennt. Die Zusage „kein
Motivschlüssel wird im Frontend in Text übersetzt" bleibt davon unberührt — Anzeigename, Definition
und Abgrenzung kommen weiterhin ausschließlich vom Server.

Ein Schlüssel ohne Eintrag fällt auf `tag` zurück, damit ein Altwert die Reihe nicht zerreißt.

### 4. Kein neues Farbtoken

Die drei Füllfarben sind die bestehenden `--status-success`/`--status-running`/`--status-failed` —
in diesem Farbvorrat die einzige dreistufige Signalfolge, als Flächenfarbe deklariert und in der
Kontrastmatrix bereits mit der grafischen Schwelle (3:1) auf allen vier Flächen belegt.

**`--danger` ist ausgeschlossen:** Es ist als Fließtextfarbe gesperrt, und über `currentColor` wäre
die Füllung genau das.

Die Zusage des Design-Systems „kein Akzent als Füllung" gilt für die Motivstärke nicht mehr. Dass
Grün und Rot im Produkt zugleich „albumwürdig" und „aussortiert" bedeuten, trägt die Füllhöhe als
zweiter, farbunabhängiger Träger.

### 5. Die acht Symbole spannen nur die kurze Achse auf

Jedes Symbol ist eine Schaltfläche, vertikal über `tap-target` auf 44 px aufgespannt, waagerecht so
breit wie ein Achtel der Reihe — bei 360 px Gerätebreite rund 41 px, im Popover rund 32 px.

**Die 44 px der waagerechten Achse werden bewusst unterschritten.** Acht nebeneinanderliegende
Trefferflächen zu je 44 px brauchen 352 px zuzüglich Zwischenräumen und sind mit der Zusage „alle
acht in einer Zeile ohne waagerechtes Scrollen" nicht vereinbar. Die Mindestgröße 24 × 24 px
(WCAG 2.5.8, Stufe AA) bleibt auf beiden Achsen deutlich überschritten. Die Symbolreihe gehört
deshalb **nicht** in den Trefferflächen-Prüfsatz `e2e/tests/tap-targets.spec.ts` und trägt nie
`tap-target-square`; sie wäre dort zwangsläufig rot, weil der Treffertest an den Ecken das
Nachbarsymbol meldet.

## Konsequenzen

- Ein neues Symbol zieht vier Stellen nach: `ui/icon.tsx`, die Zusage über die Symbolzahl in
  `frontend/penpot/icons.test.ts`, `ERWARTETE_SYMBOLE` in `design/penpot/verify.js` und der an Datei
  **und Zeile** gebundene Wächtereintrag in `frontend/penpot/payload.test.ts`. `design/penpot/
  icons.json` ist der erzeugte Schnappschuss und wird nie von Hand gepflegt.
- Kein Backend-Anteil, keine Änderung an `GET /motifs`, `GET /photos` oder am Korrekturweg. Die
  Stufen entstehen aus Feldern, die die Antwort bereits trägt.
- Die drei Muster des Design-Systems zur Stärkeliste beschreiben nach dieser Änderung eine
  Oberfläche, die es nicht mehr gibt, und werden im selben Pull Request neu gefasst.
- `e2e/tests/tap-targets.spec.ts` erreicht die Korrekturschaltflächen erst nach einem Klick auf ein
  Symbol; die Zahl der geprüften Bedienelemente bleibt gleich.
- `docs/architecture.md` zieht den Absatz zur Motivdarstellung im selben Pull Request nach.
