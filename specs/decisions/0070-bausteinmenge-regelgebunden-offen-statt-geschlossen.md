# 0070 - Die Bausteinmenge der Design-Bibliothek ist regelgebunden offen; der Platzhalter ist der elfte

**Status:** Accepted
**Datum:** 2026-09-09
**Bezug:** [GitHub-Issue #358](https://github.com/TheRealKoller/photosort/issues/358), [`features/0358-projektverwaltung-entwurf.md`](../features/0358-projektverwaltung-entwurf.md), [`features/0352-penpot-als-alleinige-design-quelle.md`](../features/0352-penpot-als-alleinige-design-quelle.md), [`decisions/0066-penpot-stand-als-erzeugte-idempotente-nutzlast.md`](./0066-penpot-stand-als-erzeugte-idempotente-nutzlast.md)

**Berührt außerdem (keine Ablösung):**
- [`decisions/0066`](./0066-penpot-stand-als-erzeugte-idempotente-nutzlast.md): unverändert gültig, **ohne** Teil-Vermerk im Kopf. Die Entscheidung dort lautet, dass gegen `components.json` verglichen wird — die Zahl „zehn" ist in Abschnitt 1 und 6 beschreibend, nicht entscheidend. Ein `Superseded`- oder Teil-Vermerk auf eine Zahl, die die Entscheidung gar nicht trägt, schickte den nächsten Leser auf die Suche nach einer Nachfolgeentscheidung, die es nicht gibt.
- [`features/0352`](../features/0352-penpot-als-alleinige-design-quelle.md) Akzeptanzkriterium 3 („Die Menge ist **geschlossen**: weder mehr noch weniger"): Die Spec bleibt `Implemented` und wird **nicht** umgeschrieben — sie beschreibt zutreffend den Stand ihrer Umsetzung. Diese ADR ist die spätere, benannte Öffnung.

## Kontext

Spec 0352 hat die Bibliothek mit zehn Bausteinen aufgebaut und die Menge ausdrücklich als
geschlossen festgelegt: „weder mehr noch weniger". Das war richtig und war der Punkt der Sache —
eine Bibliothek, die beim Aufbau schon „und was man sonst noch brauchen könnte" mitnimmt, ist am
ersten Tag ein Wunschzettel statt eines Abbilds.

Spec 0358 entwirft die erste Ansicht, und der Ladezustand der Projektübersicht (Akzeptanzkriterium
5) braucht den Platzhalter. Der existiert im Produkt seit langem
(`frontend/src/components/ui/skeleton.tsx`, im Design-System-Dokument als eigenes Muster geführt)
und steht an vier Stellen mit der längsten Wartezeit: Projektliste, Fotoraster, Kuratierung,
Einzelbild. Er fehlt in Penpot nur deshalb, weil beim Aufbau niemand ihn zu den zehn gezählt hat.

Damit steht eine Grundsatzfrage an, nicht eine Einzelfallentscheidung: Wenn die Menge geschlossen
ist, wird jeder künftige Entwurf, der einen fehlenden Baustein braucht, entweder blockiert oder
zeichnet ihn frei nach — und Letzteres bricht die Zusage, dass Entwürfe aus Instanzen bestehen.

## Entscheidung

### 1. Die Menge wächst auf elf und ist künftig nicht mehr geschlossen, sondern regelgebunden

An die Stelle von „geschlossen: weder mehr noch weniger" tritt eine **Aufnahmeregel**. Ein Baustein
gehört in die Bibliothek, wenn **alle drei** Bedingungen erfüllt sind:

1. **Er existiert im Produkt.** Es gibt mindestens eine Datei unter `frontend/src/components/`, die
   ihn heute rendert. Nichts wird „zur Vorsorge" angelegt; was das Produkt nicht hat, kommt mit der
   Story, die es einführt.
2. **Er trägt Tokens.** Mindestens eine seiner Eigenschaften ist an ein Token des Satzes
   `photosort` gebunden. Ein Baustein ohne Tokenbindung beschriebe nichts, was zentral änderbar
   wäre, und multiplizierte nur das Kreuzprodukt auf.
3. **Ein Entwurf braucht ihn.** Die Aufnahme geschieht in der Story, die ihn zum ersten Mal
   verwendet — nicht in einer Sammelstory „Bibliothek vervollständigen".

Die Menge bleibt damit **abzählbar und im Repository geführt** (`components.json` ist weiterhin die
einzige Liste), nur nicht mehr eingefroren. Die statische Zusicherung in
`frontend/penpot/payload.test.ts` bleibt eine **geschlossene Namensmenge** — sie wird mit der
Aufnahme fortgeschrieben, nicht aufgeweicht: „genau elf" bestünde auch mit elf beliebigen, deshalb
wird weiterhin die Namensliste geprüft, nicht die Kardinalität.

### 2. Der elfte Baustein: `skeleton` / „Platzhalter"

- **Maschineller Schlüssel:** `skeleton`. **Anzeigename:** „Platzhalter".
- **Quelle:** `src/components/ui/skeleton.tsx`.
- **Einsortierung in `components.json`:** nach `dialog`, **vor** `chip`. Die zehn Einträge sind
  heute so geordnet, dass die Bausteine aus `components/ui/` zusammenstehen und der Kategorie-Chip
  als einziger aus `components/` daneben am Ende liegt. Ein Anhängen ans Ende zerrisse diese
  Ordnung still.
- **Achse `auspraegung`** mit zwei Ausprägungen, beide aus dem Produktcode abgeleitet statt
  erfunden: `zeile` (Listenzeile, `radius.lg` — Projektliste) und `kachel` (quadratische Kachel und
  bildfüllender Platzhalter, `radius.md` — Fotoraster, Kuratierung, Einzelbild). Eine dritte
  Ausprägung für den bildfüllenden Fall gibt es **nicht**: Sie trüge dieselben Tokens wie `kachel`
  und wäre damit eine Ausprägung ohne Unterschied.
- **Tokens:** Fläche `color.text-disabled` (das Token trägt diese zweite, nicht-textliche Rolle
  ausdrücklich, siehe `specs/architecture/0004-design-system.md`), Radius je Ausprägung.
- **Keine Zustandsachse.** `skeleton.tsx` trägt keinen Zustand aus dem geschlossenen
  Zustandsvokabular; `motion-reduce:` ist davon ausdrücklich ausgenommen.
- **Benannte Lücke:** Der Puls (`animate-pulse`) ist Bewegung; Penpot bildet ihn nicht ab, und es
  gibt kein Token dafür. Der Baustein steht in Penpot ohne Bewegung, und das wird als Lücke
  geführt, nicht als erledigt.

Das Kreuzprodukt der Varianten steigt damit von **144 auf 146**.

### 3. Der elfte Baustein entsteht in Penpot von Hand — der Wächter wird nicht umgangen

`seed-components.js` trägt die Laufregel `nur-auf-leerer-datei` und prüft fail-closed, ob die Datei
bereits einen bekannten Baustein trägt. Sie trägt zehn. **Ein erneuter Lauf ist damit ausgeschlossen
und wird nicht ermöglicht** — weder durch Umschreiben der Nutzlast noch durch einen Aufruf ohne die
Prüfung. Nach ADR 0065 ist der Penpot-Stand das Original; ein zweiter Lauf zerstörte es.

Der elfte Baustein wird deshalb **in Penpot angelegt**, in derselben Hauptsession, in der die
Ansicht entsteht: als Bibliotheks-Komponente mit den Plugin-Daten `schluessel = skeleton`, mit dem
Varianten-Container der Achse `auspraegung` und mit den Tokenbindungen aus Abschnitt 2.
`seed-components.js` wird trotzdem mitgezogen — aber ausschließlich für seine dauerhafte Rolle, die
**Wiederherstellung nach Instanzverlust**. Es läuft in dieser Story nicht.

Das hat eine Folge, die man kennen muss, statt sie für einen Fehler zu halten: Zwischen dem
Repository-Teil und dem Penpot-Teil der Story ist `verify.js` mit `ERWARTETE_BAUSTEINE = 11`
**erwartbar rot**, solange der Baustein in Penpot noch nicht von Hand steht. Das ist die richtige
Reihenfolge, kein Fehlschlag.

### 4. Was die Zahl heute trägt und mitgezogen werden muss

Die Zahl steht an mehr Stellen, als man beim ersten Hinsehen vermutet. Abschließend:

| Ort | Was dort steht |
|---|---|
| `design/penpot/components.json` | der neue Eintrag selbst |
| `frontend/penpot/payload.test.ts` | Blocktitel „Die zehn Bausteine", die Liste der maschinellen Schlüssel, die Liste der Anzeigenamen, der Kommentar „neun der zehn liegen unter `ui/`", die Zusicherung „baut genau 144 Varianten auf", der Suchraum der Wertfreiheits-Zusicherung (fünf → sechs Dateien, siehe ADR 0082) |
| `design/penpot/verify.js` | `ERWARTETE_BAUSTEINE = 10` |
| `frontend/penpot/payload.test.ts`, Freigabeliste | der zeilen- und ausschnittgebundene Eintrag zu `ERWARTETE_BAUSTEINE`; **jede** Zeilenverschiebung in `verify.js` betrifft zusätzlich die drei übrigen Einträge |
| `design/penpot/seed-components.js` | Kopfkommentar („zehn Bausteine", „144 Varianten") und der Kommentar an `pruefeLeereDatei` |
| `design/penpot/README.md` | zwei Tabellenzeilen und der Abschnitt zum Kreuzprodukt |
| `.claude/skills/penpot-design/SKILL.md` | Schritt 2 (Zeitüberschreitungs-Hinweis) und Schritt 4 (Rücklese-Kriterium) |
| `specs/architecture/0004-design-system.md` | der Platzhalter ist dort als Muster geführt, künftig zusätzlich als Bibliotheks-Baustein — gepflegt vom `ux-ui-designer` |

## Begründung

Eine geschlossene Menge war beim Aufbau die richtige Zusage und ist bei der ersten Verwendung die
falsche. Ihr Zweck war, einen Wunschzettel zu verhindern; dieser Zweck wird von der Aufnahmeregel
in Abschnitt 1 genauso gut erfüllt, weil deren erste und dritte Bedingung genau das ausschließen —
nur eben ohne den Nebeneffekt, dass der erste Entwurf blockiert oder zum Nachzeichnen gezwungen ist.

Die Alternative wäre gewesen, den Ladezustand ohne Bibliotheks-Baustein zu entwerfen. Sie ist
abzulehnen, weil sie die tragende Zusage der ganzen Konstruktion aushebelt: Eine spätere
Wertänderung schlägt nur auf den Entwurf durch, wenn er aus Instanzen besteht. Eine nachgezeichnete
graue Fläche wäre ab dem Tag ihrer Entstehung stumm.

Die Regel wird bewusst **nicht** an eine Zahl gebunden („bis zu fünfzehn"), sondern an
Bedingungen. Eine Obergrenze wäre willkürlich und träfe irgendwann eine Story, die nichts dafür
kann.

## Konsequenzen

- **Positiv:** Der erste Ansichtsentwurf kann seinen Ladezustand aus der Bibliothek bauen. Künftige
  Entwürfe haben einen benannten Weg für einen fehlenden Baustein statt einer Blockade. Die
  Bibliothek bleibt ein Abbild des Produkts, nicht ein Wunschzettel.
- **Negativ / bewusst getragen:**
  - Die Zahl steht an acht Stellen und muss bei jeder Aufnahme mitgezogen werden. Kein Test kann
    das erzwingen, weil mehrere dieser Stellen Prosa sind.
  - Repository und Penpot werden für diesen Baustein durch **zwei verschiedene Handlungen** in
    Übereinstimmung gebracht (Eintrag im Repository, Handarbeit in Penpot). Bis beide erfolgt sind,
    meldet das Rücklesen eine Abweichung.
  - `seed-components.js` wächst um einen Baustein, den es nie ausführen wird, solange die Instanz
    lebt — unausgeführter Code, der erst im Wiederherstellungsfall zählt.
- **Folgearbeit:** Ob der Puls des Platzhalters ein Token bekommt (und damit Bewegung überhaupt
  tokenisiert wird), bleibt offen und ist keine Aufgabe dieser Story.
