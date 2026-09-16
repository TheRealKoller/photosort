# 0112 - Keine Bildfläche wird gedämpft

**Status:** Accepted
**Datum:** 2026-09-16
**Bezug:** Spec [`features/0498-volle-helligkeit.md`](../features/0498-volle-helligkeit.md), ADR
[`0055`](./0055-dark-utility-register-fundament.md) (Punkt 4b, durch diese ADR teilweise abgelöst)

## Kontext

Die gedämpfte Bildfläche kam als Ersatz für die Board-Angabe „ganze Karte Deckkraft 40 %" (ADR 0055
Punkt 4b): Das Zurücktreten sollte dort entstehen, wo es keinen Textkontrast kostet. Sie steht heute
an drei Stellen, und an allen dreien wird inzwischen das Motiv selbst beurteilt — am deutlichsten im
Duplikat-Vergleich, wo mehrere ähnliche Aufnahmen nebeneinander liegen und genau ihr
Helligkeitsunterschied die Frage ist. Deckkraft auf einer Bildfläche mischt gegen den Seitengrund:
Die Aufnahme wirkt dunkler, als sie ist.

## Entscheidung

### 1. Auf einer Bildfläche liegt keine Dämpfung, in keiner Ansicht

Kein Element, das ein Foto trägt oder es umschließt, trägt `opacity-*`. An diese Stelle tritt auch
kein anderes Mittel, das die Bildfläche selbst verändert: kein Filter (`grayscale`, `brightness-*`,
`contrast-*`, `saturate-*`, `invert`, `sepia`), kein Mischmodus (`mix-blend-*`), keine über das Bild
gelegte teildeckende Fläche. Das gilt für jeden Zustand einer Aufnahme — Ausschuss, verworfen,
zurückgetreten — und unabhängig von Vergrößerung und Ansicht.

Bei Verletzung geht die Beurteilung am Motiv vorbei: Die Aufnahme wird nach einer Helligkeit
beurteilt, die die Darstellung erzeugt hat, und eine Vorauswahl, die den Zustand gesetzt hat, lässt
sich an ihrem eigenen Ergebnis nicht mehr überprüfen.

### 2. Den Zustand tragen Rahmen und Kennzeichen — ersatzlos, ohne drittes Mittel

Der Zustand einer Aufnahme bleibt in jeder betroffenen Ansicht erkennbar und weiterhin auch ohne
Farbwahrnehmung, über das Kennzeichen aus **Symbol und sichtbarem Text** sowie über den **Rahmen**;
auf der Foto-Karte zusätzlich über die **Durchstreichung** des Dateinamens. Diese Mittel sind
vollständig ohne die Dämpfung — sie war nie Teil der Mehrfachcodierung, sondern lag daneben.

Eine schwächere Dämpfung ist damit ebenso ausgeschlossen wie die volle: Der abgelehnte Zustand ist
„Bildfläche verändert", nicht „Bildfläche zu stark verändert".

### 3. Die Ortsregel für eine Dämpfung bleibt in Kraft, obwohl sie gegenstandslos wird

Entstünde je wieder eine Dämpfung an einer Foto-Kachel, sitzt sie auf der Bildfläche und nie am
Kachel- oder Kartenkörper. Am Körper drückt dieselbe Utility Kennzeichen, Dateiname und
Bedienelemente gemeinsam unter die Kontrastschwelle, und über einer Bildfläche ist ein Kontrast mit
Deckkraft statisch nicht nachrechenbar. Die Regel wird ausdrücklich **nicht** mit aufgeräumt.

### 4. Drei Wächter, und nur der erste kennt eine besetzte Freigabeliste

Punkt 1 hängt an `frontend/src/designSystem.contract.test.ts`:

- Die bestehende fundstellengenaue `opacity-*`-Regel behält ihre Freigabeliste. Deren Einträge sind
  ab hier ausschließlich **Zustände von Bedienelementen** (deaktiviert, überfahren, gedrückt); die
  drei Bildflächen-Einträge entfallen. Jedes neue `opacity-`-Vorkommen in einer Produktionsdatei ist
  rot, bis jemand es mit Fundstelle und Begründung einträgt — ein Eintrag, der eine Bildfläche
  nennt, widerspricht dabei Punkt 1 sichtbar an der Stelle, an der er entsteht.
- Daneben tritt eine Regel **ohne Freigabeliste** über die bildtragenden Dateien: Dort ist keines
  der in Punkt 1 genannten Muster zulässig, auch nicht mit Begründung. Die Menge wird **abgeleitet**
  statt aufgezählt — jede Produktionsdatei, die `PhotoImage` nennt —, damit eine neue bildtragende
  Komponente ohne Zutun darunterfällt. Eine Gegenprobe weist die Menge als nicht leer und eine
  bekannte Datei als enthalten nach; sonst liefe die Regel nach einer Umbenennung gegen nichts.
- Dazu eine dritte Regel über **alle** Produktiv-`.tsx`, für die sechs Filter und den Mischmodus,
  mit fundstellengenauer und heute leerer Freigabeliste. Grund: Die abgeleitete Menge erfasst drei
  Seiten **nicht**, die eine Foto-Kachel rendern, ohne `PhotoImage` selbst zu nennen
  (`AlbumDraftPage`, `AlbumSelectionPage`, `DuplicateComparePage`) — und Filter wie Mischmodus
  wirken von **jedem** Vorfahren auf das Kind, ein `<div className="grayscale">` um die Kachel
  liefe sonst durch. `opacity-*` bleibt hier außen vor: Dafür gibt es die erste Regel mit ihrer
  begründeten Freigabe der Bedienelement-Zustände.

Dass die zweite Regel keine Ausnahme kennt, kostet nichts: Deckkraft für Bedienelement-Zustände
liegt im Produkt ohnehin in `ui/button.tsx`, nicht in der aufrufenden Ansicht. Auch die dritte
Regel kostet gemessen nichts — es gibt heute kein Vorkommen dieser Muster in einer Produktiv-`.tsx`.
Tritt der Fall je ein, wird die Regel laut rot, statt dass eine Bildfläche still wieder dunkler
wird.

**Eine Grenze, die keine dieser Regeln schließt:** Alle drei sind klassen-in-Datei-basiert, nicht
render-baum-basiert. Ein Kind-Baustein, der selbst dämpft, bliebe außerhalb.

## Konsequenzen

- Folgende Zusagen gelten nicht mehr: Spec 0320 („Aussortiert: gedämpft wird nur die Bildfläche" und
  Abnahmepunkt 9 „die einzige zulässige Dämpfung ist die Bildfläche der aussortierten Karte"), Spec
  0431 (Zustandstabelle der Endauswahl, Zelle „Bildfläche gedämpft"), Spec 0486 (Abschnitt
  „Dämpfung": die Dämpfung der Verlierer-Kacheln bleibt unverändert), Spec 0489 AK6 (der Rücktritt
  einer verworfenen Aufnahme). AK6 der Spec 0374 fiel bereits mit Spec 0486 und wird hier nicht ein
  zweites Mal aufgehoben. Wer die Umsetzung prüft, behandelt das als gewollt, nicht als Regression.
- `data-dimmed` entfällt in `DuplicatePhotoTile` und `PhotoGridTile`. Das Attribut hatte genau einen
  Zweck: einen berechneten Deckkraftwert gegen eine Absicht zu halten. Ohne Dämpfung sagt es nichts,
  und ein dauerhaftes `false` behauptete, es gebe einen zweiten Fall. `data-duplicate-decision`,
  `data-struck` und `data-rating-status` bleiben unberührt.
- ADR 0055 trägt ab jetzt einen `**Teilweise abgelöst:**`-Vermerk im Kopf. Ihr Entscheidungstext
  bleibt unverändert; angefasst wird ausschließlich der Kopf. Kein `Superseded` — betroffen ist in
  Punkt 4b allein die kompensierende Maßnahme „gedämpfte Bildfläche"; dass die Board-Angabe „ganze
  Karte Deckkraft 40 %" entfällt, gilt unverändert und schärfer als zuvor.
- ADR 0071 Punkt 3 bleibt unberührt und bekommt keinen Vermerk: Dort ist entschieden, dass
  „verworfen" ein Anzeigezustand ist und die bestehende Karte ihn darstellt — nicht, woraus ihre
  Darstellung besteht.
- `specs/architecture/0004-design-system.md`, `.claude/skills/design-system/SKILL.md` und
  `docs/architecture.md` ziehen im selben Pull Request nach.
