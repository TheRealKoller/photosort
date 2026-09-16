# 0498 - Jede Aufnahme wird in voller Helligkeit gezeigt

**Status:** Implemented ([PR #501](https://github.com/TheRealKoller/photosort/pull/501))
**Erstellt:** 2026-09-16
**Bezug:** [Issue #498](https://github.com/TheRealKoller/photosort/issues/498), ADR
[`0112`](../decisions/0112-keine-bildflaeche-wird-gedaempft.md)

**Diese Spec hebt die Zusagen zur gedämpften Bildfläche in vier Specs bewusst auf:**
Spec [`0320`](./0320-dark-utility-register.md) (Kartenzustand „Aussortiert" und Abnahmepunkt 9),
Spec [`0431`](./0431-endauswahl-gemeinsam.md) (Zustandstabelle, Zelle „Bildfläche gedämpft"),
Spec [`0486`](./0486-duplikate-durchgehen.md) (Abschnitt „Dämpfung") und
Spec [`0489`](./0489-fotouebersicht-ohne-beschnitt.md) AK6. Wer die Umsetzung prüft, behandelt das
als gewollt, nicht als Regression. AK6 der Spec 0374 fiel bereits mit Spec 0486 und wird hier nicht
ein zweites Mal aufgehoben; deren AK8 („das vergrößerte Bild wird ungedämpft gezeigt") bleibt gültig
und gilt ab hier für jede Aufnahme.

## Ziel

Eine gedämpft dargestellte Bildfläche verfälscht die Beurteilung des Motivs. Am deutlichsten fällt
das in der Duplikat-Vergleichsansicht auf: Dort liegen mehrere ähnliche Aufnahmen nebeneinander, und
genau ihr Helligkeits- und Qualitätsunterschied soll beurteilt werden. Die als Ausschuss
vorausgewählten Aufnahmen wirken durch die Dämpfung dunkler, als sie sind — der Vergleich geht am
Motiv vorbei, und die Vorauswahl lässt sich nicht mehr zuverlässig überprüfen.

Die Dämpfung sollte den Blick auf die behaltene Aufnahme lenken. Sie war dabei nie das einzige
Mittel, den Zustand einer Aufnahme zu zeigen, und es galt schon bisher: Eine Aufnahme, die beurteilt
werden soll, bleibt unverfälscht. Inzwischen wird überall dort beurteilt, wo die Dämpfung sitzt. Sie
entfällt deshalb ersatzlos, und zwar in allen Ansichten — nicht nur im Duplikat-Vergleich.

## User Story

Als Nutzer möchte ich jede Aufnahme in ihrer echten Helligkeit sehen, unabhängig davon, ob sie als
Ausschuss, als verworfen oder als zurückgetreten markiert ist, damit ich das Motiv beurteilen und
Aufnahmen miteinander vergleichen kann, ohne dass die Darstellung mein Urteil verfälscht.

## Akzeptanzkriterien

- [ ] AK1 — In der Duplikat-Vergleichsansicht trägt weder die Bildfläche einer Aufnahme noch ein
      sie umschließendes Element ein Deckkraft-, Filter- oder Mischmodus-Mittel — für beide
      wirksamen Entscheidungen (`keep`/`discard`) und in beiden Darstellungen (Übersicht und
      Vergrößerung). Kein Element der Kachel trägt noch `data-dimmed`.
- [ ] AK2 — Dasselbe gilt für die verworfene Aufnahme der Fotoübersicht (`PhotoGridTile`, auch dort
      entfällt `data-dimmed`) und für die zurückgetretene Aufnahme der Foto-Karte (`PhotoCard`) in
      **beiden** Datenwegen, die sie erzeugen: eigene Streichung (`status="rejected"`) und
      gemeinsame Herausnahme (`setAside`). Keine Produktivdatei des Frontends trägt danach noch
      ein Deckkraft-Mittel auf einer Bildfläche.
- [ ] AK3 — Die Dämpfung entfällt ersatzlos, und das ist im Prüfsatz verankert: Über den
      bildtragenden Produktivdateien weist der Design-Vertrag `opacity-`, `grayscale`,
      `brightness-`, `contrast-`, `saturate-`, `invert`, `sepia` und `mix-blend-` **ohne
      Ausnahmemöglichkeit** zurück; die Freigabeliste der bestehenden `opacity-*`-Regel führt
      danach ausschließlich Zustände von Bedienelementen und keinen Eintrag mehr, der eine
      Bildfläche nennt.
- [ ] AK4 — Der Zustand bleibt in jeder betroffenen Ansicht erkennbar, je Ansicht über die dort
      vorhandenen Träger:
      **Duplikat-Vergleich** sichtbares Symbol **und** Wort im Zustandsfeld plus der
      zustandsabhängige Rahmen der Kachel, auch in der Vergrößerung;
      **Kuratierung und gemeinsame Endauswahl** (`PhotoCard`) das Bewertungs-Kennzeichen aus
      Symbol und Wort bzw. — bei `setAside` ohne Bewertungszustand — der durchgestrichene
      Dateiname (`data-struck="true"`);
      **Fotoübersicht** der Punkt in der Bildecke (gefüllt bei Entscheidung, Ring beim Vorschlag,
      `data-mark-status`) plus die Zustandswörter als Text der Kachel.
      Kein Zustandsträger liegt auf einer teildeckenden Fläche; die Rahmen- und Kennzeichenfarben
      bleiben unverändert, es entsteht keine neue Kontrastpaarung.
- [ ] AK5 — Die Ortsregel für eine Dämpfung (sie säße auf der Bildfläche, nie am Kachel- oder
      Kartenkörper) bleibt als Zusage in ADR 0112 und im Design-System-Dokument stehen. Sie
      bekommt **keinen** eigenen Test: Ihr Gegenstand existiert nicht mehr, und die Regel aus AK3
      schließt jede Dämpfung in diesen Dateien bereits aus — ein Test auf den nicht mehr
      existierenden Fall wäre grün, ohne etwas zu wissen.
- [ ] AK6 — Die aufgehobenen Zusagen sind an genau zwei Sorten Ort festgehalten und nirgends
      widersprochen: ADR 0112 nennt sie namentlich (Specs 0320, 0431, 0486, 0489 AK6), ADR 0055
      trägt den `**Teilweise abgelöst:**`-Vermerk. `specs/architecture/0004-design-system.md`,
      `.claude/skills/design-system/SKILL.md` und `docs/architecture.md` enthalten danach keine
      Aussage mehr, die eine gedämpfte Bildfläche behauptet. Abgeschlossene Feature-Specs werden
      nicht angefasst; ihre Aufhebung steht ausschließlich in ADR 0112.

## Datenmodell-Bezug

Keiner. Kein Backend, kein API-Vertrag, keine Migration, kein Demo-Bestand. Die Änderung ist
vollständig eine Darstellungsänderung im Frontend.

## Architektur / Umsetzung

Die Entscheidung steht in ADR
[`0112`](../decisions/0112-keine-bildflaeche-wird-gedaempft.md): Auf einer Bildfläche liegt keine
Dämpfung, in keiner Ansicht, und kein anderes bildveränderndes Mittel tritt an ihre Stelle. ADR
[`0055`](../decisions/0055-dark-utility-register-fundament.md) trägt dafür einen
`**Teilweise abgelöst:**`-Vermerk im Kopf (Punkt 4b, nur die kompensierende Maßnahme).

### Gemessener Bestand

Drei `opacity-*`-Fundstellen auf Bildflächen. Darüber hinaus nichts: kein Inline-`style` mit
`opacity`, keine `opacity`/`filter`-Regel in den CSS-Dateien, kein `grayscale`/`brightness-*`/
`saturate-*`/`invert`/`sepia`/`mix-blend-*` in `frontend/src`, kein `opacity` in der
Penpot-Nutzlast unter `design/penpot/`. Die drei `backdrop-blur-sm`-Stellen sind
Marker-Hinterlegungen über einer Kachel, keine Bildflächen, und bleiben unberührt.

### Betroffene Dateien

| Datei | Änderung |
|---|---|
| `frontend/src/components/DuplicatePhotoTile.tsx` | `gedaempft` entfällt (einzige Verwender sind `data-dimmed` und `opacity-40`), beide entfallen mit. `enlarged` bleibt — es trägt weiterhin Höhe, Bildvariante und `object-fit`. Doku-Block der Bildfläche neu gefasst. |
| `frontend/src/components/PhotoGridTile.tsx` | `const rejected` (Zeile 145) entfällt vollständig (sonst ungenutzt ⇒ Lint/`tsc`), `data-dimmed` und `opacity-40` mit ihm. Die gleichnamigen **Schlüssel** in `DOT_COLOR`/`DOT_FILL` bleiben — sie sind der AK4-Träger dieser Ansicht. Das umschließende `<div>` **bleibt**: es trägt `size-full overflow-hidden rounded-md`, also Beschnitt und Rundung der Bildfläche. Entfiele es, bliebe jeder Test grün und die Bildfläche liefe über die Kachelrundung hinaus. |
| `frontend/src/components/PhotoCard.tsx` | `imageAreaClassName` verliert `stepsBack && 'opacity-40'` und wird dadurch zur Konstante. **`stepsBack` bleibt** — es trägt weiterhin `data-struck` und die Durchstreichung des Dateinamens, und es deckt **zwei** Datenwege (`status === 'rejected'` und `setAside`). Doku-Block neu gefasst. |
| `frontend/src/components/CurationPhotoTile.tsx`, `SelectionPhotoTile.tsx` | Nur Doku-Blöcke: beide zählen „gedämpfte Bildfläche" als Bestandteil der Kartendarstellung auf. Kein Verhaltenswechsel. |
| `frontend/src/designSystem.contract.test.ts` | Drei Einträge aus `OPACITY_ALLOWLIST` entfernen samt ihrem begründenden Kommentarblock; zwei neue Regeln (unten); der bestehenden `opacity-`-Regel die fehlende Positiv-Gegenprobe ergänzen. |
| `frontend/src/components/DuplicatePhotoTile.test.tsx` | Drei Fälle entfallen; Ersatz ist **ein** Fall über `discard`/`keep` × `enlarged`, der zusichert, dass kein Knoten der Kachel `data-dimmed` trägt. Der Rahmen-Fall in der Vergrößerung **bleibt** und trägt jetzt AK4. |
| `frontend/src/components/PhotoCard.test.tsx` | Die `.opacity-40`-Abfrage entfällt aus dem `setAside`-Fall; `data-struck` bleibt der Träger. Testname und Doku-Block anpassen. |
| `frontend/src/components/PhotoGridTile.test.tsx` | Der `describe`-Block „der Rücktritt einer verworfenen Aufnahme (AK6)" entfällt. **Sein dritter Fall hielt zugleich die Zusage „ein Vorschlag ist keine Entscheidung" fest** — der Ersatz iteriert über `rejected`/`album_worthy`/vorgeschlagen-`rejected` und prüft beides: kein `data-dimmed` im Baum, und Füllung vs. Ring bleibt unterschieden (Spec 0489 AK5). |
| `frontend/src/components/SelectionPhotoTile.test.tsx`, `CurationPhotoTile.test.tsx` | Je ein Testname behauptet die Dämpfung („dimmed image", „dimmed display state") ohne zugehörige Assertion. Ein stehengelassener Name ist derselbe Fehler in Prosa. |
| `e2e/tests/no-horizontal-scroll.spec.ts` | Nur ein Kommentar spricht von „den gedämpften, herausgenommenen Bildern". Keine Assertion betroffen. |
| `specs/architecture/0004-design-system.md` | Board-Abweichung 7, Vertragsregel 4, Grid-Kachel-Muster, Kuratierungs-Muster, Stufen-Abschnitt. |
| `.claude/skills/design-system/SKILL.md` | Drei Stellen — die beiden Muster-Einträge und der Zustandsmittel-Satz der stehenbleibenden Kachel. |
| `docs/architecture.md` | Der Satz zur Dämpfung im `PhotoGridTile`-Absatz. |

`frontend/src/photoGridTile.structure.test.ts` ist **nicht** anzufassen: Sie prüft ausschließlich die
Aufrufstellen von `PhotoCard` und nennt das `<div>` der Rasterkachel nirgends.

Kein Backend, kein API-Vertrag, keine Migration, kein Demo-Bestand.

### Reihenfolge der Umsetzung

1. **Vertragstest zuerst.** `OPACITY_ALLOWLIST` um die drei Bildflächen-Einträge kürzen und die
   neuen Regeln anlegen — beide werden damit **rot**, weil die drei Fundstellen noch stehen.
   Umgekehrt wäre die neue Regel von Geburt an grün und nie im roten Zustand gesehen worden. Die
   Freigabeliste meldet dabei **beide** Richtungen: ein Eintrag ohne Fundstelle als verwaiste
   Freigabe, ein Vorkommen ohne Eintrag als nicht freigegeben.
2. Die fünf Komponenten-Testdateien umschreiben (rot).
3. Die drei Komponenten ändern (grün). `gedaempft` und die lokale Konstante `rejected` mit
   entfernen, `stepsBack` und die `DOT_*`-Schlüssel stehen lassen.
4. Doku-Blöcke der beiden aufrufenden Kacheln und des E2E-Falls nachziehen.
5. `docs/architecture.md` und die verbliebene Stelle im Design-System-Skill nachziehen.

### Die beiden Wächter, die AK3 dauerhaft tragen

`OPACITY_ALLOWLIST` wird **nicht leer**: Acht Einträge bleiben (`ui/button.tsx`,
`RatingButtons.tsx`), ausschließlich Zustände von Bedienelementen. Die Regel bleibt damit voll
wirksam — jedes nicht freigegebene `opacity-`-Vorkommen in einer Produktions-`.tsx` ist rot. Sie ist
aber ein Freigabe-, kein Verbotsmechanismus: Wer eine Bildfläche wieder dämpfen will, könnte einen
Eintrag mit Begründung nachtragen.

Deshalb treten zwei Regeln daneben:

- **Ohne Freigabeliste, über die bildtragenden Dateien.** `opacity-`, `grayscale`, `brightness-`,
  `contrast-`, `saturate-`, `invert`, `sepia` und `mix-blend-` sind dort unzulässig, auch mit
  Begründung. Die Dateimenge wird **abgeleitet statt aufgezählt** — jede Produktionsdatei, die
  `PhotoImage` nennt (heute zehn) —, damit eine neue bildtragende Komponente ohne Zutun
  darunterfällt.
- **Mit fundstellengenauer, heute leerer Freigabeliste, über alle Produktiv-`.tsx`**, für die sechs
  Filter- und Mischmodus-Muster. Grund: Die abgeleitete Menge erfasst drei Seiten **nicht**, die
  eine Foto-Kachel rendern, ohne `PhotoImage` selbst zu nennen (`AlbumDraftPage`,
  `AlbumSelectionPage`, `DuplicateComparePage`). Deckkraft und Filter wirken von **jedem** Vorfahren
  auf das Kind — ein `<div className="grayscale">` um die Kachel liefe sonst durch. Die Ableitung
  stattdessen über den Import-Graphen bis zum Fixpunkt auszuweiten trägt nicht: Die Kette läuft bis
  `App.tsx` und `main.tsx`, und eine ausnahmefreie Regel über praktisch alles ist keine Zusage über
  Bildflächen mehr. Gemessen kostet die zweite Liste nichts — es gibt heute null Vorkommen dieser
  sechs Muster in Produktiv-`.tsx`.

Beide neuen Regeln brauchen eine **Gegenprobe auf eine nicht leere Kandidatenmenge** (ohne die
Kardinalität festzuschreiben — eine neue bildtragende Datei soll in die Regel fallen, nicht die
Gegenprobe rot färben) und einen **Erkenner-Mikrotest an literalen Eingaben**: Der Erkenner bindet
an die Tailwind-Klassenform, nicht an die Teilzeichenkette, sonst trifft er `inverted` als
Bezeichner, `-moz-osx-font-smoothing: grayscale` bei erweitertem Suchraum und das `animate-pulse`
des `PhotoImage`-Skeletons.

**Eine Grenze, die keine Regel dieser Art schließt:** Beide Wächter sind klassen-in-Datei-basiert,
nicht render-baum-basiert. Ein Kind-Baustein, der selbst dämpft, bliebe außerhalb.

### Entwurfsentscheidungen

- **`data-dimmed` entfällt an beiden Stellen.** Das Attribut hatte genau einen Zweck: einen
  berechneten Deckkraftwert gegen eine Absicht zu halten. Ohne Dämpfung sagt es nichts, und ein
  dauerhaftes `"false"` behauptete, es gebe einen zweiten Fall. Gemessen null Verwender in E2E,
  Penpot-Nutzlast und Produktivcode — die Entfernung bricht nichts still.
  `data-duplicate-decision`, `data-struck` und `data-rating-status` bleiben unberührt.
- **Die Ortsregel bleibt stehen** (AK5): Entstünde je wieder eine Dämpfung an einer Foto-Kachel,
  säße sie auf der Bildfläche und nie am Kachel- oder Kartenkörper. Sie lebt ab hier im
  Design-System-Dokument und im Doku-Block der Vertragsregel 4, nicht mehr in einem
  Komponenten-Kommentar neben einer Zeile, die es nicht mehr gibt.
- **Keine implementierte Spec wird editiert.** Die Aufhebung steht in den `## Konsequenzen` der
  ADR 0112 und in der Kopfnotiz dieser Spec.
- **DOM-Struktur bleibt unverändert.** Weder das `<button>` der Vergleichskachel noch das `<div>`
  der Rasterkachel wird entfernt; beide tragen Layout.

## UI/UX

Bildflächen werden in allen drei betroffenen Ansichten (Duplikat-Vergleich, Fotoübersicht,
Kuratieren) ohne Dämpfung gezeigt. Der Zustand einer Aufnahme bleibt erkennbar über Kennzeichen
(Symbol + sichtbarer Text), Rahmeneinfärbung und die Durchstreichung des Dateinamens. Diese Träger
liegen sämtlich **außerhalb** der Bildfläche oder auf undurchsichtigen Flächen (`--overlay`,
Kartenkörper) — es entsteht deshalb an keiner Stelle eine neue Kontrastpaarung gegen ein jetzt
helleres Bild.

**Bewusst getragene Lücke (Entscheidung Daniels vom 2026-09-16):** In der Fotoübersicht
unterscheidet nach dem Wegfall der Dämpfung **nichts Achromatisches** mehr „verworfen" von
„album-würdig" — beide sind derselbe gefüllte Punkt in derselben Form, getrennt allein durch
`--danger` gegen `--accent-2`. Die Formunterscheidungen der Kachel greifen hier nicht: Stern gegen
Kreis trennt Favorit von Bewertung, Ring gegen Füllung trennt Vorschlag von Entscheidung. Bisher trug
die Dämpfung diesen Unterschied. Die Lücke wird ohne Ersatz hingenommen und steht als bekannte Lücke
im Testkonzept, neben `StatusDot` und `QualityMeter`; die Aussage bleibt für Bildschirmleser über die
Zustandswörter der Kachel vollständig.

## Teststrategie

**Vertragstest** (`frontend/src/designSystem.contract.test.ts`) trägt AK1–AK3: Er ist die einzige
Ebene mit CSS-Assertions, und die Abwesenheit einer Utility ist genau seine Fehlerklasse.

**Komponentenebene** (`vitest`/jsdom) trägt AK1/AK2 nur, soweit es um **DOM-Attribute** geht
(`data-dimmed` ist nirgends mehr im Baum), und AK4 vollständig. Klassennamen werden dort nicht
geprüft — die bestehenden Fälle, die `opacity-40` als Zeichenkette abfragen, wandern in den
Vertragstest, statt umgeschrieben zu werden.

**Keine E2E-Prüfung.** Aufnahmekriterium der Ebene ist, was jsdom prinzipiell nicht kann; eine
fehlende Klasse ist statisch nachweisbar.

**Ad hoc, nicht als Dauertest:** Graustufen-Lauf plus Hinsehen über die drei Ansichten — die
achromatische Unterscheidbarkeit zweier Kennzeichen ist keine assertion-fähige Eigenschaft.

## Security

Nicht relevant. Die Änderung berührt weder Auth, externe Schnittstellen, Secrets, neue Eingaben von
außen, Berechtigungen, das Datenmodell noch die Sichtbarkeit von Daten zwischen den beiden Nutzern —
sie entfernt eine Darstellungs-Utility von drei Bildflächen.

## Offene Fragen

Keine.

## Out of Scope

- **Eine Formunterscheidung im Punkt der Rasterkachel.** Ausdrücklich nicht Teil dieser Spec, siehe
  die bewusst getragene Lücke unter UI/UX.
- **Die Ortsregel aufräumen.** Sie bleibt in Kraft, obwohl sie gegenstandslos wird (AK5).
- **Bestehende `opacity-*`-Verwendungen an Bedienelementen** (`ui/button.tsx`, `RatingButtons.tsx`).
  Sie sind Zustände von Bedienelementen, keine Bildflächen, und bleiben freigegeben.

## Entscheidungen

- `architect` konsultiert (Schritt 1): ADR 0112 angelegt, Kopfvermerk an ADR 0055 gesetzt.
- `ux-ui-designer` konsultiert (Schritt 2): Design-System-Dokument und -Skill nachgezogen.
- `test-engineer` konsultiert (Schritt 3): Akzeptanzkriterien auf Testbarkeit geschärft, zweiter
  Wächter um die projektweite Filter-Regel ergänzt, Testkonzept ergänzt.
- `security-engineer` nicht konsultiert (Schritt 3): Die Story berührt keinen konkret benennbaren
  Anhaltspunkt der Skip-Prüfung — kein Auth, keine externe Schnittstelle, kein Secret, keine neue
  Eingabe von außen, keine Berechtigung, keine Datenmodell-Berührung und keine veränderte
  Datensichtbarkeit zwischen den beiden Nutzern. Gegenstand ist das Entfernen einer CSS-Utility von
  drei Bildflächen.
- **Die Dreierliste des Schärfungsgesprächs war an einer Stelle falsch** und wurde am Bestand
  korrigiert: Spec 0374 AK6 ist bereits mit Spec 0486 gefallen; betroffen sind stattdessen die
  Specs 0320, 0431, 0486 und 0489 AK6.
- **Die achromatische Lücke der Fotoübersicht wird ohne Ersatz getragen** (Daniel, 2026-09-16).
