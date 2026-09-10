# 0370 - Bedienelemente zuerst in der Einzelbildansicht

**Status:** Accepted
**Erstellt:** 2026-09-10
**Bezug:** [Issue #370](https://github.com/TheRealKoller/photosort/issues/370)

## Ziel

Die Einzelbildansicht ist die Fläche, auf der ein Foto tatsächlich bearbeitet wird: bewerten,
Kategorie prüfen und gegebenenfalls korrigieren, weiterblättern. Heute stehen genau diese
Bedienelemente hinter mehreren reinen Informationsblöcken, deren Länge von Foto zu Foto
schwankt — bei jedem einzelnen Foto ist deshalb erst Scrollen nötig, bevor gehandelt werden
kann. Tastenkürzel und Wischgesten entschärfen das nur teilweise: Sie decken Bewerten und
Navigieren ab, nicht aber die Kategorie-Korrektur und das Übernehmen eines Vorschlags, und auf
einem Mobilgerät stehen sie gar nicht zur Verfügung.

Die Informationsblöcke sollen nicht verschwinden — sie werden weiterhin gebraucht, nur nicht bei
jedem Foto. Sie gehören deshalb hinter die Bedienelemente statt davor.

Damit wird eine frühere eigene Festlegung bewusst revidiert: Spec
[0041](./0041-bewertungsdetails-permanent-in-detailansicht-hover-auto-close.md) hat die permanente
Detail-Sektion ausdrücklich direkt unter dem Foto und vor den Navigationsbuttons platziert. Nach
längerer echter Nutzung erweist sich diese Reihenfolge als hinderlich.

## User Story

Als Nutzer, der in der Einzelbildansicht seine Fotos durchgeht, möchte ich alle Bedienelemente
unmittelbar unter dem Bild vorfinden, damit ich bewerten, die Kategorie korrigieren und
weiterblättern kann, ohne bei jedem Foto erst an Informationen vorbeizuscrollen.

## Akzeptanzkriterien

Die Kriterien des Story-Issues, vom `test-engineer` auf Testbarkeit geschärft. Ersetzt sind die
nicht entscheidbaren Formulierungen ("unmittelbar unter dem Bild", "bleiben unverändert",
"dauerhaft und vollständig sichtbar") durch prüfbare Aussagen. Fachlich ist nichts hinzugekommen
und nichts gestrichen; die Aufzählungen benennen nur aus, was das Issue zusammenfasst.

### Reihenfolge: Bedienen zuerst

- [ ] 1. In der Einzelbildansicht (`PhotoDetailPage`) stehen unmittelbar unter dem Foto und **vor**
      jeder reinen Informationsanzeige, in dieser Dokumentreihenfolge: (a) die Bewertungsleiste
      (Favorit, Album-würdig, Verwerfen), (b) der Kategorie-Bedienteil — Kandidatenliste
      "Kategorie-Kandidaten" mit "Übernehmen"/"Zurücksetzen"/"Aktuell"/"Manuell übernommen" bzw.
      die einzeilige "Kategorie"-Anzeige bei höchstens einem Kandidaten, dazu der
      Konfidenz-Erklärhinweis und die Auswahl "Alle Kategorien" —, (c) die Navigation
      "Zurück"/"Weiter", (d) der Kasten "Automatischer Vorschlag" mit "Vorschlag übernehmen".
      Nachgewiesen über die tatsächliche DOM-Position, nicht über bloßes Vorhandensein.
- [ ] 2. Jede reine Informationsanzeige steht im DOM **hinter** allen unter AK1 genannten
      Bedienelementen — namentlich: Cloud-Vision-Status, Block "Qualität", Block "Kategorien" mit
      den kategoriefähigen Kriterienzeilen, "Rolle", "Rang", Sektion "Kategorien dieses Fotos" und
      die Feinlabel-Chips. Kein Element dieser Aufzählung steht vor einem Bedienelement.
- [ ] 3. Diese Informationsanzeigen sind nach dem Laden ohne jede weitere Bedienhandlung
      vollständig sichtbar: der Informationsbereich enthält kein zuklappbares Element
      (`<details>`/`<summary>`), kein Element mit `aria-expanded` und keinen Popover-/Dialog-
      Trigger. (Der Konfidenz-Erklärhinweis bleibt als `<details>` unverändert im **Bedienteil** —
      er erläutert eine Bedienzahl und ist keine der hier gemeinten Informationsanzeigen.)

### Unverändertes Verhalten

- [ ] 4. Funktion, Beschriftung und Verhalten sämtlicher Bedienelemente sind unverändert:
      Bewerten per Klick einschließlich Zurücknehmen durch erneuten Klick auf dieselbe Option;
      "Übernehmen" eines Kandidaten; Auswahl aus allen Kategorien; "Zurücksetzen" einer manuellen
      Kategorie; "Vorschlag übernehmen" über denselben Mutationspfad wie ein manueller Klick;
      "Zurück"/"Weiter" samt Deaktivierung am Anfang bzw. Ende der Sequenz; Auto-Advance zum
      nächsten unbewerteten Foto nach dem **Setzen** einer Bewertung und ausdrücklich **nicht**
      nach dem Zurücknehmen. Beschriftungen und `aria-label` bleiben wörtlich gleich; insbesondere
      behält die Bewertungsleiste `role="group"` mit `aria-label="Bewertung"`.
- [ ] 5. Tastenkürzel (1 Favorit, 2 Album-würdig, 3 Verwerfen, ←/→ blättern, sämtlich wirkungslos,
      solange ein Texteingabefeld den Fokus hat) und Wischgesten (nach rechts = vorheriges, nach
      links = nächstes Foto, ab 50 px Auslenkung; unterhalb der Schwelle keine Navigation) wirken
      unverändert. Die Shortcut-Hinweiszeile bleibt erhalten.

### Sichtbarkeitsregeln

- [ ] 6. Die bestehenden Regeln, wann ein Bereich gar nicht erscheint, gelten unverändert weiter —
      kein leerer Platzhalter, keine überflüssige Überschrift: ohne `criterion_scores` erscheint
      weder Bedien- noch Informationsteil der Kategorie-Details; ohne Ranking erscheint kein
      Kategorie-Bedienteil; ohne Feinlabels kein Feinlabel-Bereich; bei genau einer Zugehörigkeit
      weder "Rolle" noch "Kategorien dieses Fotos"; ohne Vorschlag kein Vorschlagskasten. Der
      Bedienteil trägt dabei bewusst **keine** eigene Überschrift und kein `role="group"`
      (zwei gleichlautende "Kategorien"-Überschriften wären mehrdeutig); der Informationsteil
      behält "Qualität" und "Kategorien" unverändert.
- [ ] 7. Die Anordnung ist auf allen Bildschirmbreiten dieselbe: es existiert keine
      breitenabhängige Reihenfolge-Logik — keine `order-*`-Utility hinter einem Breakpoint, kein
      `flex-*-reverse`, keine viewport-abhängige Verzweigung im Rendering.

### Keine Auswirkung auf andere Ansichten, Spec-Hygiene

- [ ] 8. Rasteransicht, Kuratierungsansicht und Vergleichsansicht bleiben unverändert:
      `CriterionDetailsPopover.tsx` zeigt weiterhin die vollständige, verschränkte Darstellung und
      bleibt im Diff **ohne eine einzige geänderte Zeile**; `CriterionDetailsPopover.test.tsx` und
      `CriterionDetailsList.test.tsx` bleiben inhaltlich unverändert (siehe Teststrategie).
- [ ] 9. Die überholte Platzierungsvorgabe aus Spec 0041 (AK1: permanenter Abschnitt "direkt unter
      dem Foto, vor den Vor-/Zurück-Navigationsbuttons") ist in
      `specs/features/0041-bewertungsdetails-permanent-in-detailansicht-hover-auto-close.md` als
      durch diese Spec revidiert kenntlich gemacht, mit Nummernverweis auf 0370. Der übrige Inhalt
      von Spec 0041 bleibt unverändert gültig; ihr Status bleibt `Implemented`.

## Datenmodell-Bezug

Keiner. Es entsteht keine neue Entität, kein neues Feld und keine Migration; es ändert sich auch
kein Antwortschema. Die Story rendert ausschließlich bereits geladene Daten
(`criterion_scores`, `rankings`, `category_candidates`, `fine_labels`, `cloud_vision_status`,
`suggestion`) an einer anderen Stelle derselben Seite. `docs/architecture.md` ist deshalb nur um
einen Einordnungssatz zu ergänzen, nicht am Datenmodell.

## Architektur / Umsetzung

**Reines Frontend.** Kein Backend-Anteil, kein neues API-Feld, keine Migration, keine neue
Abhängigkeit, keine neue Route. Es ändert sich ausschließlich, an welcher Stelle der
Einzelbildansicht bereits vorhandene, bereits geladene Daten gerendert werden.

### Ausgangslage und der eigentliche Knoten

`CriterionDetailsList.tsx` ist eine geteilte Präsentationskomponente mit genau zwei Aufrufern:
`PhotoDetailPage.tsx` (permanente Sektion) und `CriterionDetailsPopover.tsx` (Info-Popover in
Raster und Kuratierung, das seinerseits von `PhotoGridPage.tsx` und `CurationPhotoTile.tsx`
eingebunden wird). Sie mischt genau die beiden Gruppen, die diese Spec trennt — und zwar
**verschränkt**, nicht als zwei Hälften: Kategorie-Kriterienzeilen (Information) → Kandidatenliste
bzw. einzeilige "Kategorie"-Anzeige (Bedienung) → Rolle/Rang (Information) → Konfidenz-Erklärhinweis
und "Alle Kategorien"-Auswahl (Bedienung) → "Kategorien dieses Fotos"/Feinlabels (Information),
alles innerhalb eines `<dl>` und einer beschrifteten `role="group"`-Gruppe, mit einer bewusst
gesetzten Abstands-Feinheit (`mt-2`, Copilot-Review-Fund auf PR #277, "pixelgleich"-Zusage aus
Spec [0209](./0209-bewertungsdetails-bloecke-qualitaet-kategorien.md)). Akzeptanzkriterium 8
verlangt, dass Raster/Kuratierung — und damit diese verschränkte Gesamtdarstellung im Popover —
unverändert bleiben.

### Gewählter Ansatz: ein Teilbereichs-Prop `part` an `CriterionDetailsList`

`CriterionDetailsList` bekommt ein optionales Prop

```ts
/** Welcher Teil der Aufschlüsselung gerendert wird. `'all'` (Vorgabe) ist die unveränderte,
 *  verschränkte Gesamtdarstellung des Popovers; `'controls'` und `'info'` rendern die beiden
 *  Teilmengen, aus denen die Einzelbildansicht ihre neue Reihenfolge zusammensetzt. */
part?: 'all' | 'controls' | 'info'
```

mit Vorgabe `'all'`. Damit bleibt `CriterionDetailsPopover.tsx` **buchstäblich unverändert** (keine
Zeile, kein Prop) und die vollständige bestehende Testdatei `CriterionDetailsList.test.tsx` ist die
Regressionsabsicherung für Akzeptanzkriterium 8: sie muss ohne inhaltliche Änderung grün bleiben.
Ergänzt werden nur neue Fälle für `part='controls'`/`part='info'`.

`PhotoDetailPage.tsx` bindet die Komponente **zweimal** ein — einmal oben mit `part="controls"`,
einmal unten mit `part="info"` —, über ein einziges, gemeinsam gebildetes Props-Objekt, damit die
beiden Instanzen nicht auseinanderlaufen können:

```tsx
const detailsProps = {
  criterionScores: currentPhoto.criterion_scores,
  ranking: primaryRanking(currentPhoto),
  rankings: currentPhoto.rankings,
  suggestion: null,
  showSuggestion: false,
  categoryCandidates: currentPhoto.category_candidates,
  fineLabels: currentPhoto.fine_labels,
  categories: categorySet,
  /* … die übrigen bestehenden Props unverändert … */
}
```

### Zuordnung: was ist Bedienelement, was Information

**Bedienteil (`part='controls'`, oben):**

- Kandidatenliste "Kategorie-Kandidaten" mit "Übernehmen"/"Zurücksetzen"/"Aktuell"/"Manuell
  übernommen" inklusive der Waisen-Zeile (`isOrphan`).
- Die einzeilige "Kategorie"-Anzeige (der Fall `candidateRows.length <= 1`) samt ihrer
  Konfidenzzahl. **Begründung:** sie ist der Degenerationsfall genau der Kandidatenliste und
  zugleich die einzige Stelle, an der die *wirksame* Kategorie ausgeschrieben steht. Das Ziel der
  Story ist "bewerten, Kategorie **prüfen** und gegebenenfalls korrigieren" — stünde die Zeile
  unten, müsste man zum Prüfen genau das tun, was die Story abschaffen will: an Informationen
  vorbeiscrollen und wieder zurück. Sie bleibt damit außerdem direkt über der Auswahl stehen, wie
  bisher.
- Der Konfidenz-Erklärhinweis (`<details>`, `showsAnyConfidence`). **Begründung:** er erklärt
  ausschließlich die Zahlen, die im Bedienteil stehen; sein Sichtbarkeitsgate hängt an genau diesen
  Zahlen. Er ist eine Fußnote zu einer Zahl, keine der in Akzeptanzkriterium 2 genannten
  Informationsanzeigen — Akzeptanzkriterium 3 ("nicht zugeklappt") greift auf ihn deshalb **nicht**,
  er bleibt exakt wie heute ein `<details>` (alles andere wäre eine von Akzeptanzkriterium 4/6
  verbotene Verhaltensänderung).
- Die "Alle Kategorien"-Auswahl (`CategorySelect`) inklusive ihres `mt-2`-Abstands.

**Informationsteil (`part='info'`, unten):**

- Block "Qualität" (alle nicht kategoriefähigen Kriterienzeilen).
- Block "Kategorien": kategoriefähige Kriterienzeilen, "Rolle", "Rang", Sektion "Kategorien dieses
  Fotos", Feinlabel-Chips. **Begründung:** allesamt nicht interaktiv; "Rolle" und "Kategorien
  dieses Fotos" hängen an derselben Bedingung (`showMembershipRoles`) und gehören sachlich zu
  "Rang" — die Einordnung dieses Fotos, nicht seine Bedienung.
- Die Ausschuss-Gruppe (`showSuggestion`) — im Popover-Fall Information; in der Einzelbildansicht
  ohnehin nicht vorhanden, weil dort `showSuggestion={false}` gilt (unverändert).

### Neue Reihenfolge in `PhotoDetailPage.tsx`

1. Shortcut-Zeile, Zähler "x/y", Foto — **unverändert an ihrer Stelle** (der Zähler ist zwar
   Information, steht aber schon heute *über* dem Foto und ist von der Story nicht berührt).
2. `RatingButtons` (Favorit / Album-würdig / Verwerfen).
3. Bedienteil: `<CriterionDetailsList {...detailsProps} part="controls" />`.
4. Zurück/Weiter-Navigation.
5. "Automatischer Vorschlag"-Kasten (`suggestion && …`) mit "Vorschlag übernehmen".
6. Trennlinie zwischen Bedien- und Informationsteil (siehe UI/UX).
7. `CloudVisionStatusList`.
8. Informationsteil: `<CriterionDetailsList {...detailsProps} part="info" />`.
9. "Zurück zum Grid" (unverändert am Seitenende).

Die Reihenfolge 2–5 folgt der Aufzählung in Akzeptanzkriterium 1. Punkt 7 vor 8 erhält die
bisherige relative Ordnung: der Kommentar in `PhotoDetailPage.tsx` zu Spec
[0058](./0058-cloud-vision-status-transparenz.md) hält fest, dass die dortige Vorgabe "unmittelbar
vor der `CriterionDetailsList`" und "nach den Bewertungs-Buttons" gleichzeitig nicht erfüllbar war.
Mit dieser Spec sind **beide** erfüllt; der Kommentar ist entsprechend neu zu fassen statt stehen
zu lassen.

### Abbildung der Sichtbarkeitsgates (Akzeptanzkriterium 6)

Innerhalb der Komponente werden `showControlsPart = part !== 'info'` und
`showInfoPart = part !== 'controls'` abgeleitet; jedes heutige Gate bleibt erhalten und wird nur um
den passenden Teil-Faktor ergänzt:

| Bereich | Gate heute | Gate danach |
|---|---|---|
| Block "Qualität" | `qualityScores.length > 0` | `showInfoPart && qualityScores.length > 0` |
| Block "Kategorien" | `categoryScores.length > 0 \|\| ranking !== null` | `(showControlsPart && ranking !== null) \|\| (showInfoPart && (categoryScores.length > 0 \|\| ranking !== null))` |
| Kriterienzeilen des Kategorien-Blocks | — | zusätzlich `showInfoPart` |
| `mt-2` am Kandidaten-/Rang-Wrapper | `categoryScores.length > 0` | `showInfoPart && categoryScores.length > 0` (der Abstand entfällt genau dann, wenn ihm keine Kriterienzeile vorausgeht — die ursprüngliche Begründung, jetzt auch teilbezogen richtig) |
| Kandidatengruppe vs. einzeilige Anzeige | `showCandidateGroup` | unverändert, zusätzlich `showControlsPart` |
| "Rolle" / "Kategorien dieses Fotos" | `showMembershipRoles` | unverändert, zusätzlich `showInfoPart` |
| "Rang" | `ranking !== null` | unverändert, zusätzlich `showInfoPart` |
| Konfidenz-Hinweis | `showsAnyConfidence` | unverändert, zusätzlich `showControlsPart` |
| "Alle Kategorien" | `onOverrideCategory` gesetzt | unverändert, zusätzlich `showControlsPart` |
| Feinlabels | `fineLabels.length > 0` (innerhalb des Kategorien-Blocks) | unverändert, zusätzlich `showInfoPart` |
| Ausschuss-Gruppe | `showSuggestion && suggestion !== null` | unverändert, zusätzlich `showInfoPart` |

Für `part='all'` ergibt jede Zeile wörtlich das heutige Gate — das Popover ist damit nachweislich
unberührt.

**Kein leerer Platzhalter auf Seitenebene.** Der äußere Container der Komponente
(`flex flex-col gap-4`) wird heute auch dann gerendert, wenn nichts darin steht; im
`flex flex-col gap-4` der Seite verbrauchte eine leere Instanz einen sichtbaren Abstand. Deshalb:

- Neue exportierte, unit-testbare Vorbedingung in `CriterionDetailsList.tsx` als **einzige** Quelle
  der Wahrheit — `hasCategoryControls(criterionScores, ranking)` ⇔
  `criterionScores.length > 0 && ranking !== null`. Die Seite gated ihren Bedienteil-Wrapper damit,
  die Komponente gibt bei `part === 'controls'` ohne erfüllte Vorbedingung `null` zurück.
- Der Informationsteil braucht keine eigene Vorbedingung: bei `criterion_scores.length > 0` enthält
  er immer mindestens eine Kriterienzeile. Sein Wrapper behält deshalb das heutige Gate
  `currentPhoto.criterion_scores.length > 0` unverändert.
- Damit gilt **unverändert**: ohne Kriterien erscheint keiner der beiden Bereiche; ohne Ranking
  erscheint kein Bedienteil (bisher: keine Kandidaten/Auswahl innerhalb der Sektion). Es entsteht
  weder ein neuer Bereich, der vorher nicht da war, noch verschwindet einer.
- `part !== 'all'` gibt generell `null` zurück (nicht ein leeres `<div>`), wenn keiner der
  Bereiche des jeweiligen Teils rendert — Rückfallschutz gegen künftige Gate-Änderungen.

**Keine zweite Überschrift.** Der Bedienteil rendert den Kategorien-Block **ohne** `<h3>` und ohne
`role="group"`/`aria-labelledby` (schlichter `<div>` + `<dl>` mit unverändertem Innenleben). Zwei
gleichlautende "Kategorien"-Überschriften auf einer Seite wären mehrdeutig, und eine neu erfundene
Überschrift wäre eine Beschriftungsänderung, die Akzeptanzkriterium 4 gerade ausschließt. Die
Bedienelemente tragen ihre Beschriftungen bereits selbst ("Kategorie-Kandidaten" bzw. "Kategorie"
als `<dt>`, "Alle Kategorien" als `<label>`). Der Informationsteil behält beide Überschriften
unverändert — Spec 0209 ("zwei beschriftete Blöcke, auch in der permanenten Sektion") bleibt für
ihn damit erfüllt.

**Der Bedienteil braucht ein eigenes `<dl>` — kein nackter Teilbaum.** Die Kandidatengruppe und die
einzeilige "Kategorie"-Anzeige rendern `<dt>`/`<dd>` und sitzen heute im `<dl>` des
Kategorien-Blocks. Gäbe `part='controls'` nur den inneren Teilbaum aus, stünden `dt`/`dd` ohne
`<dl>`-Vorfahren — invalides Markup und ein stiller Bruch von Spec 0041 AK12. Der Bedienteil
rendert deshalb ein eigenes `<dl>` mit denselben Klassen (`flex flex-col gap-2`) um seinen Inhalt.
Ein Testfall hält das fest (siehe Teststrategie).

### Test-Kennzeichnung

Der bestehende `data-testid="criterion-details-section"` bleibt am **Informationsteil** (bestehende
Tests in `PhotoDetailPage.test.tsx` behalten ihre Bedeutung: Blocküberschriften, "kein leerer
Bereich"). Der Bedienteil bekommt einen eigenen `data-testid="category-controls-section"`. Die
Reihenfolge aus Akzeptanzkriterium 1/2 wird über die tatsächliche DOM-Reihenfolge geprüft (siehe
Teststrategie), nicht über Klassennamen.

### Betroffene Dateien

| Datei | Änderung |
|---|---|
| `frontend/src/components/CriterionDetailsList.tsx` | neues Prop `part`, teilbezogene Gates, eigenes `<dl>` im Bedienteil, exportierte Vorbedingung `hasCategoryControls`, `null`-Rückgabe für leere Teile |
| `frontend/src/components/CriterionDetailsList.test.tsx` | bestehende Fälle inhaltlich unverändert; neue Fälle für `part='controls'`/`'info'` in neuen `describe`-Blöcken |
| `frontend/src/pages/PhotoDetailPage.tsx` | neue Reihenfolge, zwei Instanzen über ein gemeinsames Props-Objekt, zwei Wrapper-Gates, Trennlinie, Neufassung der veralteten Kommentare zu Spec 0058/0041 |
| `frontend/src/pages/PhotoDetailPage.test.tsx` | neue Reihenfolge- und Verdrahtungstests; bestehende Tests bleiben inhaltlich gültig |
| `frontend/src/components/CriterionDetailsPopover.tsx` (+ Test) | **keine Änderung** — bewusst, als Nachweis für Akzeptanzkriterium 8 |
| `frontend/src/pages/PhotoGridPage.tsx`, `components/CurationPhotoTile.tsx`, `pages/PhotoComparePage.tsx` | **keine Änderung** (die Vergleichsansicht bindet die Bewertungsdetails ohnehin nicht ein) |
| `specs/features/0041-…md` | datierter Nachtrag im Kopf (Akzeptanzkriterium 9) |
| `specs/features/0209-…md` | datierter Nachtrag im Kopf (siehe unten) |
| `docs/architecture.md` | Einordnungssatz in der Kopfzeile "Letzte Aktualisierung" |

### Reihenfolge der Umsetzung (TDD)

1. `CriterionDetailsList`: Tests für `part='controls'`/`part='info'` (Zuordnung je Element, alle
   Gates der Tabelle oben, `null`-Rückgabe, `<dl>`-Vorfahre, `hasCategoryControls`) schreiben →
   rot → Prop und teilbezogene Gates umsetzen → grün. **Abnahmebedingung dieses Schritts:** die
   bestehende Testdatei läuft ohne inhaltliche Änderung durch, `CriterionDetailsPopover.test.tsx`
   ebenfalls.
2. `PhotoDetailPage`: Test für die DOM-Reihenfolge (Akzeptanzkriterien 1/2) und für die beiden
   Wrapper-Gates (Akzeptanzkriterium 6) schreiben → rot → Umbau → grün. Die bestehenden Tests zu
   Bewerten/Auto-Advance/Navigation/Tastenkürzel sind der Nachweis für Akzeptanzkriterien 4/5 und
   bleiben unverändert; die in der Teststrategie benannten Lücken (ArrowLeft, Wischgesten,
   "Zurücksetzen", "Alle Kategorien") werden ergänzt.
3. Doku: Nachträge an Spec 0041 und 0209, Eintrag in `docs/architecture.md` — im selben PR.

### Kein ADR

Keine neue Technologie, keine externe Abhängigkeit, keine Datenmodell-Grundstruktur. Die
Entscheidung ist eine Detailentscheidung innerhalb der bereits akzeptierten Richtung (ADR
[`0011`](../decisions/0011-ui-component-library.md), Specs 0040/0041) — dieselbe Einordnung, die
Spec 0041 für ihre eigene Komponenten-Extraktion getroffen hat. Keine bestehende ADR ist berührt;
die revidierte Platzierungsvorgabe steht ausschließlich in Spec 0041, nicht in einer ADR.

### Nachträge an Spec 0041 und Spec 0209

Der Feature-Lifecycle in [`specs/README.md`](../README.md) kennt den Teil-Vermerk formal nur für
ADRs; für Feature-Specs gibt es aber ein etabliertes, mehrfach angewandtes Muster — datierter
Nachtrag im Kopf, Status bleibt, Rumpf unangetastet (Spec 0033 gegenüber 0298, Spec 0038 gegenüber
0045). Beide Specs sind nur in einem Punkt überholt, ein `Superseded` wäre eine falsche Auskunft.

- **Spec 0041** (Akzeptanzkriterium 9): Nachtrag unmittelbar nach der `**Bezug:**`-Zeile. Abgelöst
  ist genau die **Platzierung** — AK1, der entsprechende Satz im Abschnitt "Architektur /
  Umsetzung" und der erste Aufzählungspunkt "Platzierung" im Abschnitt "UI/UX". Unverändert gültig
  bleiben die permanente Sichtbarkeit selbst (AK2/AK3), die unveränderten Popover in Raster und
  Kuratierung (AK4), die geteilte Präsentationskomponente inklusive `showSuggestion` (AK5/AK6),
  das Hover-Auto-Close (AK7–AK11) sowie AK12/AK13.
- **Spec 0209** (über den Wortlaut von AK9 hinaus, aber derselbe Zustand, den AK9 verhindern will):
  Abgelöst ist ausschließlich der Schlusssatz von AK6 ("Kandidatenliste und 'Rang' stehen dabei
  innerhalb des Kategorien-Blocks"), und auch der nur für die **Einzelbildansicht**. Im Popover
  gilt AK6 vollständig weiter, ebenso alle übrigen Kriterien an beiden Anzeigestellen —
  insbesondere AK1 (zwei beschriftete Blöcke, auch in der permanenten Sektion) und AK7 (kein
  leerer Block, keine leere Überschrift).

## UI/UX

**Feature-Typ:** sichtbare Oberfläche — Umordnung und Aufteilung einer bestehenden Komponente in
`PhotoDetailPage`. Es entsteht kein neues Bedienelement, kein neues Token und keine neue
Formsprache; das Design-System (`specs/architecture/0004-design-system.md`) ist um zwei
Muster-Einträge ergänzt.

### Ablauf und neue Reihenfolge

1. **Shortcut-Zeile** ("Shortcuts: 1 Favorit, 2 Album-würdig, 3 Verwerfen, ←/→ navigieren")
2. **Zähler** ("x/y")
3. **Fotofläche** — Wischgesten unverändert (nach rechts = vorheriges, nach links = nächstes Foto)
4. **Bewertungsleiste** (`RatingButtons`) — unmittelbar unter dem Foto; behält ihr Layout
   (`flex-col` unterhalb `sm:`, `sm:flex-row` darüber) und ihre Trefferflächen (`h-11 sm:h-8`)
5. **Kategorie-Bedienbereich** (`CriterionDetailsList part="controls"`,
   `data-testid="category-controls-section"`): Kandidatenliste "Kategorie-Kandidaten" mit
   "Übernehmen"/"Zurücksetzen"/"Aktuell"/"Manuell übernommen", sofern mehr als ein Kandidat
   existiert; sonst die einzeilige "Kategorie"-Anzeige mit optionaler Konfidenzzahl; der
   Konfidenz-Erklärhinweis (`<details>`); die Auswahl "Alle Kategorien" (`CategorySelect`)
6. **Navigation** — "Zurück" und "Weiter" nebeneinander (`flex justify-between gap-3`, ohne
   Breakpoint), an den Grenzen der Sequenz deaktiviert
7. **Automatischer Vorschlag** (sofern vorhanden) — Kasten mit Akzent-Rand (`border-accent`,
   `bg-elevated`, `p-3`), Statuszeile, Grund, Schaltfläche "Vorschlag übernehmen"
8. **Trennlinie** — `border-t border-separator` (siehe unten)
9. **Cloud-Vision-Status** (`CloudVisionStatusList`) — reine Information, unverändert **immer**
   sichtbar (bewusst kein `.length > 0`-Gate, Spec 0058)
10. **Kriterien-Informationsbereich** (`CriterionDetailsList part="info"`,
    `data-testid="criterion-details-section"`): Block "Qualität", Block "Kategorien" mit
    kategoriefähigen Kriterienzeilen, "Rolle", "Rang", Sektion "Kategorien dieses Fotos",
    Feinlabel-Chips
11. **"Zurück zum Grid"** — unverändert am Seitenende, Filter bleibt erhalten

Die Reihenfolge 4–7 folgt der Aufzählung in Akzeptanzkriterium 1: erst bewerten (die primäre,
häufigste Handlung), dann die Kategorie prüfen/korrigieren (nur bei Bedarf), dann weiterblättern,
dann der Vorschlag als Angebot statt als Haupthandlung.

### Visuelle Gliederung

**Trennlinie zwischen Bedien- und Informationsteil — verbindlich.** Ein `border-t border-separator`
unmittelbar vor `CloudVisionStatusList`. Begründung: Ohne sie stoßen Vorschlagskasten und
Informationsblöcke unvermittelt aneinander, und der Wechsel von "was ich mit diesem Foto tue" zu
"was das System über dieses Foto weiß" wäre nicht ablesbar. `--separator` ist im Design-System
genau dafür vorgesehen ("Linie auf dem Grund", abgegrenzt von `--border` = Kante einer Fläche und
`--border-control` = Umriss eines Bedienelements) und wird bereits so verwendet (`App.tsx`,
`ProjectNav.tsx`). Kein neues Token, keine neue Farbe, keine Umrahmung eines Bereichs.

**Keine Überschrift für den Bedienteil.** Die enthaltenen Elemente tragen ihre Beschriftungen
selbst: "Kategorie-Kandidaten" bzw. "Kategorie" als `<dt>`, "Alle Kategorien" als `<label>`. Eine
zusätzliche Überschrift wäre entweder mehrdeutig (zweimal "Kategorien" auf einer Seite) oder eine
neue Beschriftung, die Akzeptanzkriterium 4 ausschließt.

**Unveränderte Formsprache im Detail.** Kandidatenzeilen behalten `rounded-md border border-border
p-2`, `CategorySelect` behält `h-11 rounded-sm border border-border-control`, der Vorschlagskasten
seinen Akzent-Rand. Der Seitencontainer bleibt `flex flex-col gap-4`; die Abstände zwischen allen
Blöcken sind damit unverändert.

### Zustände

- **Kategorienliste lädt:** `CategorySelect` ist deaktiviert und zeigt seinen Ladezustand; der
  übrige Bedienteil (Bewertungsleiste, Kandidatenliste, Navigation) bleibt vollständig bedienbar.
- **Kategorienliste fehlerhaft:** Inline-`Alert` mit "Erneut versuchen" innerhalb `CategorySelect`,
  die Auswahl bleibt deaktiviert (kein Bypass auf eine leere Liste). Unverändertes Bestandsverhalten.
- **Laufende Übernehmen-/Zurücksetzen-Anfrage:** nur die betroffene Schaltfläche wird `busy` und
  deaktiviert; die übrige Liste bleibt bedienbar. Unverändertes Bestandsverhalten — es gibt hierfür
  bewusst **keinen** eigenen Fehler-Alert, und diese Spec führt keinen ein.
- **Laufende Bewertungs-Mutation:** Bewertungsleiste und "Vorschlag übernehmen" sind `busy`; die
  Übernehmen-Schaltflächen des Kategorie-Bedienteils bleiben davon unberührt (getrennte
  Mutationspfade — sie stehen nach dem Umbau erstmals direkt untereinander und dürfen nicht
  gekoppelt werden).
- **Fehler beim Laden der Fotos:** unverändert der bestehende ganzseitige `Alert` mit Retry.
- **Leere Zustände:** kein Platzhalter und keine Überschrift ohne Inhalt — siehe
  Akzeptanzkriterium 6. Bewertungsleiste und Cloud-Vision-Status sind die einzigen immer sichtbaren
  Bereiche.

### Barrierefreiheit

- Die Bewertungsleiste behält `role="group"` mit `aria-label="Bewertung"` — sie wandert nur nach
  oben. (Der e2e-Fall `no-horizontal-scroll.spec.ts` hängt seine Vorbedingung daran.)
- Der **Informationsteil** behält seine beiden beschrifteten Gruppen: `role="group"` +
  `aria-labelledby` auf die `<h3>` "Qualität" bzw. "Kategorien".
- Der **Bedienteil** bekommt bewusst **kein** `role="group"` und kein `aria-labelledby` — es gäbe
  keine Überschrift, auf die es zeigen könnte, und eine unbeschriftete Gruppe ist im
  Accessibility-Tree wertlos. Seine Elemente sind einzeln beschriftet.
- Die `<dl>`/`<dt>`/`<dd>`-Semantik bleibt in beiden Teilen intakt: Der Bedienteil rendert ein
  eigenes `<dl>` um seine `<dt>`/`<dd>`-Paare (siehe Architektur-Abschnitt).
- Die Tab-Reihenfolge folgt der neuen DOM-Reihenfolge und damit der Handlungsreihenfolge:
  Bewertung → Kandidaten-Schaltflächen → "Alle Kategorien" → Zurück/Weiter → "Vorschlag
  übernehmen" → "Zurück zum Grid". Kein Sprung rückwärts, kein `tabindex`.
- Der `useId()`-Mechanismus für die Überschriften-Ids bleibt nötig und unverändert: Popover und
  permanente Sektion können weiterhin gleichzeitig im DOM stehen, und jetzt zusätzlich zwei
  Instanzen derselben Komponente auf einer Seite.

### Responsivität

Die vertikale Stapelung gilt auf allen Breiten; es gibt keine breitenabhängige Reihenfolge-Logik
(Akzeptanzkriterium 7). Das heutige `flex flex-col gap-4` des Seitencontainers trägt das
unverändert — die Umordnung ist eine reine Änderung der Quelltextreihenfolge, keine
Layout-Änderung. Die vorhandenen Breakpoints innerhalb einzelner Bausteine (`RatingButtons`
stapelt unterhalb `sm:`) bleiben, sie betreffen die Anordnung *innerhalb* eines Bausteins, nicht
die Reihenfolge der Bausteine.

## Security

**Nicht sicherheitsrelevant.** Die Story ordnet ausschließlich die DOM-Reihenfolge bereits
geladener Daten in der Einzelbildansicht um und teilt `CriterionDetailsList.tsx` dafür über ein
reines Anzeige-Prop `part` in zwei Ausschnitte. Kein Backend-Anteil, kein neues API-Feld, keine
Migration, keine neue Route, keine neue Abhängigkeit, keine neue Eingabe von außen, keine Änderung
an Auth, Berechtigungen oder der Datensichtbarkeit zwischen den beiden Nutzern.

Geprüft wurde der einzige Anhaltspunkt: Die umgebaute Datei trägt an den Feinlabel-Chips ein
Sicherheits-Muss-Kriterium (freier, extern erzeugter LLM-Text ausschließlich als regulärer
React-Textknoten — tragende Voraussetzung der `localStorage`-Token-Entscheidung, ADR
[`0005`](../decisions/0005-auth-implementation.md)). Es trägt nach dem Umbau unverändert: Der
Chip-Block wandert als Ganzes in den `part="info"`-Ausschnitt und bleibt ein `Badge`-Kind, ohne
`dangerouslySetInnerHTML`, ohne HTML-String-Prop, ohne `href`/`src`/`style` und ohne neue
Formatierung. Dasselbe gilt für Kategorie- und Konfidenzwerte (`formatCategoryKey`/
`formatCriterionPercent` liefern Strings in Textknoten). Das Sicherheitskonzept wird dadurch nicht
berührt (nur ein Konsultationsvermerk im Kopf).

**Eine Auflage, rein testseitig (für Umsetzung und Review):** Der bestehende Regressionstest
"never renders a fine label via dangerouslySetInnerHTML" (`CriterionDetailsList.test.tsx`) rendert
ohne `part` und deckt nach dem Umbau nur noch den Vorgabewert `'all'` ab, während die
Einzelbildansicht `part="info"` rendert. Er muss den tatsächlich benutzten Ausschnitt mit abdecken:
dieselbe Nutzlast zusätzlich mit `part="info"` (kein `<img>` im DOM, Rohtext sichtbar) und — gegen
versehentliche Doppelplatzierung — mit `part="controls"` die Abwesenheit der Feinlabel-Chips.

## Teststrategie

**Ebenen.** Reines Frontend, kein Backend-Anteil. Komponentenebene
(`frontend/src/components/CriterionDetailsList.test.tsx`, neue `describe`-Blöcke): das
Teilrendering über `part`, die Sichtbarkeitsgates je Teil, `hasCategoryControls`.
Integrationsebene (`frontend/src/pages/PhotoDetailPage.test.tsx`, gemockte `api/*`): die
DOM-Reihenfolge der Seite, die Verdrahtung beider Einbindungen und die Regressionsfälle für
Bewerten/Blättern/Auto-Advance/Tastenkürzel/Wischgesten. **Kein neuer E2E-Spec** — die Reihenfolge
ist in jsdom vollständig prüfbar, das Aufnahmekriterium der E2E-Ebene ("nur, was jsdom prinzipiell
nicht kann") ist nicht erfüllt.

**Der tragende Regressionsnachweis für AK8 ist eine unveränderte Testdatei.** `part` hat den
Vorgabewert `'all'`, der wörtlich die heutige Darstellung ergibt. `CriterionDetailsList.test.tsx`
(62 Fälle) und `CriterionDetailsPopover.test.tsx` (24 Fälle) bleiben deshalb **inhaltlich
unverändert** grün: kein angepasstes Fixture, keine gelockerte Erwartung, kein umgeschriebener
Abfrageweg. Neue Fälle werden ausschließlich in neuen `describe`-Blöcken angehängt. Ein Diff an
einem Bestandsfall dieser beiden Dateien ist ein Review-Befund, der begründet werden muss.
Ausgangslage vor der Umsetzung: 62 + 24 + 27 = 113 grüne Fälle in den drei betroffenen Dateien.

**AK1/AK2 werden über die Dokumentreihenfolge geprüft, in EINER Assertion.** Die Abschnitts-Handles
werden gesammelt, per `compareDocumentPosition` (Bitmaske, nie `.toBe(...)`) in Dokumentreihenfolge
sortiert und in einem `toEqual` gegen die literal notierte Soll-Folge gestellt: Shortcut-Zeile →
Zähler → Foto → Bewertungsleiste → `category-controls-section` → Zurück/Weiter → "Automatischer
Vorschlag" → Cloud-Vision-Status → `criterion-details-section` → "Zurück zum Grid". Dazu eine
zweite Variante ohne Vorschlagskasten (`suggestion === null`), damit die Zusage nicht an einem
optionalen Bereich hängt. `toBeInTheDocument()` genügt hier nicht — die Reihenfolge *ist* das
Feature. **Rot-Beleg Pflicht:** zwei Blöcke im Produktivcode tauschen, Lauf muss rot werden, Tausch
zurücknehmen; Ergebnis in die PR-Beschreibung.

**AK1/AK2 bekommen zusätzlich eine Partitions-Zusicherung auf Komponentenebene.** Dieselbe
Maximal-Props-Menge wird dreimal gerendert (`'all'`, `'controls'`, `'info'`); über eine literal
notierte Sondenliste je Bereich gilt: jeder in `'all'` vorhandene Bereich erscheint in **genau
einem** der beiden Teile, keiner in beiden, keiner in keinem. Zwei getrennte Positivtests fänden
weder die Doppelanzeige noch den verschluckten Bereich.

**AK3** wird als Abwesenheitszusage **innerhalb** des Informationsabschnitts geprüft (`within`):
kein `<details>`/`<summary>`, kein `aria-expanded`, kein Popover-Trigger. Seitenweit wäre die
Abfrage falsch — der Konfidenz-Erklärhinweis bleibt bewusst ein `<details>` im Bedienteil.

**AK6 hat eine exportierte, ans Rendern gebundene Vorbedingung.**
`hasCategoryControls(criterionScores, ranking)` wird tabellengetrieben über alle vier
Kombinationen geprüft **und** in derselben Tabelle gegen "das `part='controls'`-Rendering ist nicht
`null`" gestellt. Ohne diese Bindung wird die exportierte Funktion beim nächsten Gate zu einer
zweiten, driftenden Meinung. Zusätzlich seitenseitig: bei leeren `criterion_scores` existiert
weder `category-controls-section` noch `criterion-details-section` (kein leerer Kasten), während
die Cloud-Vision-Sektion unverändert sichtbar bleibt.

**Zwei Struktur-Zusagen mit eigenem Testfall:** Das `<dt>` des Bedienteils hat einen
`<dl>`-Vorfahren (sonst invalides Markup, siehe Architektur-Abschnitt). Und `part='controls'`
bzw. `'info'` geben `null` zurück statt eines leeren `<div>` (`container.firstChild === null`) —
ein leerer Flex-Container erzeugte sonst je nach `gap` eine sichtbare Lücke, die kein anderer Test
bemerkte.

**AK4/AK5 — Bestandstests plus drei benannte Lücken.** Abgedeckt sind bereits: Bewerten per Klick,
alle drei Zifferntasten samt sichtbarem Tasten-Kästchen, Toggle-zurück **ohne** Auto-Advance,
Auto-Advance nach dem Setzen, Vorschlag übernehmen samt Auto-Advance, Weiter-Klick, ArrowRight,
Deaktivierung am Rand der Sequenz, Ignorieren der Kürzel bei fokussiertem Texteingabefeld,
Kandidaten-Override aus der Detailsektion. Neu zu ergänzen, weil AK4/AK5 sie ausdrücklich zusagen
und heute kein Test sie berührt: **ArrowLeft**; **Wischgeste** nach links und nach rechts sowie ein
Fall **unter** der 50-px-Schwelle; **"Zurücksetzen" einer manuellen Kategorie** und **Auswahl aus
"Alle Kategorien"** auf Seitenebene, beide mit `within(category-controls-section)` — sie prüfen die
Verdrahtung der neuen, zweiten Einbindung, nicht die Logik (die liegt auf Komponentenebene).
Wischgesten: `fireEvent.touchStart/touchEnd` mit `touches`/`changedTouches`, gefeuert auf dem Bild
(`findByAltText`), das Ereignis blubbert zum Handler; in dieser Toolchain am 2026-09-10 verifiziert.

**AK7 ist keine Testzusage, sondern eine Diff-Zusage.** jsdom hat keine Layout-Engine; ein zweiter
Lauf in einer zweiten Breite renderte denselben Baum und wäre ein immer-grüner Test. Geprüft wird
im Review die Abwesenheit jeder breakpoint-abhängigen Reihenfolge-Logik (keine `order-*` hinter
`sm:`/`md:`/`lg:`, kein `flex-*-reverse`, keine viewport-abhängige Verzweigung). Bestehende
Absicherung, die nicht verloren gehen darf: `e2e/tests/no-horizontal-scroll.spec.ts` hängt die
Vorbedingung der Detailroute an `role="group"` / "Bewertung" — die Gruppe wandert nur nach oben,
`role` und `aria-label` bleiben.

**AK9** ist eine Doku-Änderung; die Nummer-Ziel-Konsistenz des neuen Verweises deckt der
bestehende `scripts/tests/test_verweisnummern_in_markdown.py` automatisch ab, das Vorhandensein des
Vermerks selbst ist Review-Pflicht.

**Abgedeckte Grenzfälle** (je Fall mindestens eine Assertion, dass der Bereich im *richtigen* Teil
und in keinem anderen steht): kein Ranking; leere `criterion_scores`; genau ein Kandidat
(einzeilige Anzeige) vs. mehrere (Kandidatenliste); verwaister Override (`isOrphan`) samt
"Zurücksetzen"; nur Qualitätskriterien bei vorhandenem Ranking (Informationsteil zeigt "Kategorien"
mit ausschließlich "Rang"); kategoriefähige Kriterien ohne Ranking (Bedienteil fehlt ganz); keine
Feinlabels; genau eine vs. mehrere Zugehörigkeiten (`showMembershipRoles`); `suggestion === null`;
Cloud-Vision-Status `not_run`/`not_candidate`; laufende Mutation (`isMutating`, mit der
ausdrücklichen Gegenprobe, dass Bewertungs- und Override-Mutation **nicht** gekoppelt sind).

**Mehrdeutige Abfragen sind ein Fund, keine Testschuld.** Die Seite montiert dieselbe Komponente
ab hier zweimal. Schlägt ein Bestandsfall mit "found multiple elements" fehl, wird **nicht** auf
`getAllBy…`/`.first()` ausgewichen — entweder ist die Aufteilung falsch, oder die Abfrage bekommt
ihren `within(...)`-Rahmen.

**Coverage-Gate:** nicht berührt. `--cov-fail-under=80` gilt ausschließlich für den `pytest`-Lauf
über `backend/`; diese Story ändert keine Backend-Datei. Das Frontend hat kein numerisches Gate;
die Absicherung kommt aus dem TDD-Gebot und der AK-zu-Testebene-Zuordnung oben.

## Entscheidungen

- **Steuer-Prop `part` statt Komponenten-Aufspaltung** (`architect`, Schritt 1): Bedienung und
  Information sind im Kategorien-Block nicht zweigeteilt, sondern fünffach verschränkt, innerhalb
  eines `<dl>` und einer beschrifteten Gruppe. Zwei Komponenten müssten im Popover in genau dieser
  Verschränkung wieder zusammengesetzt werden — mehr bewegtes Markup und ein reales Risiko stiller
  visueller Abweichung dort, wo Akzeptanzkriterium 8 gerade Unverändertheit verlangt. Der Preis des
  gewählten Wegs ist ausdrücklich benannt: die Komponente behält die Vermischung und bekommt einen
  Rendermodus dazu.
- **Verworfen: Bedienelemente ganz aus `CriterionDetailsList` herausziehen.** Das Popover braucht
  dieselben Bedienelemente an derselben verschränkten Stelle; es entstünde eine zweite Kopie der
  Kandidatenliste inklusive Waisen-Zeile, Pending-Zuständen und Badge-Logik. Zwei Abbilder
  derselben Darstellung driften — genau das hat Spec 0041 mit der Extraktion vermieden.
- **Einzeilige "Kategorie"-Anzeige und Konfidenz-Erklärhinweis gehören in den Bedienteil**
  (`architect`, Schritt 1): Trennlinie ist "was man braucht, um die Kategorie zu prüfen und zu
  korrigieren" gegen "was man über das Foto erfährt". Die Alternative hätte den Bedienteil im
  häufigsten Fall auf eine nackte Auswahlbox ohne Angabe der wirksamen Kategorie reduziert —
  formal AK1-konform, aber am Ziel der Story vorbei.
- **Kein ADR** (`architect`, Schritt 1): kein Kriterium aus `CLAUDE.md` erfüllt, keine bestehende
  ADR berührt.
- **Trennlinie `border-t border-separator` verbindlich** (`ux-ui-designer`, Schritt 2), nicht als
  Ermessensfrage an die Umsetzung delegiert: ohne sie stoßen Vorschlagskasten und Informationsteil
  unvermittelt aneinander.
- **Bedienteil ohne Überschrift und ohne `role="group"`** (`architect`/`ux-ui-designer`): zwei
  gleichlautende "Kategorien"-Überschriften wären mehrdeutig, eine neue Beschriftung verstieße
  gegen AK4, und eine unbeschriftete `role="group"` ist im Accessibility-Tree wertlos.
- **Eigenes `<dl>` im Bedienteil** (`test-engineer`, Schritt 3): ohne es stünden `dt`/`dd` ohne
  `<dl>`-Vorfahren — invalides Markup und ein stiller Bruch von Spec 0041 AK12. Vom `architect`
  nicht adressiert, hier nachgetragen.
- **AK7 als Diff-Zusage statt Testzusage** (`test-engineer`, Schritt 3): jsdom hat keine
  Layout-Engine, ein zweiter Lauf in zweiter Breite wäre ein immer-grüner Test; ein
  Playwright-Fall verletzte das Aufnahmekriterium der E2E-Ebene.
- **XSS-Regressionstest muss `part="info"` mit abdecken** (`security-engineer`, Schritt 3): sonst
  verliert die Feinlabel-Zusage ihren Wächter auf genau dem Pfad, auf dem sie ab dieser Story
  hängt.
- **Datierter Nachtrag statt `Superseded` für Spec 0041 und 0209**: beide sind nur in einem Punkt
  überholt; etabliertes Muster (Spec 0033, Spec 0038).
- **Alle vier Fachagenten konsultiert**, keine Skip-Entscheidung: `architect` (Schritt 1),
  `ux-ui-designer` (Schritt 2), `test-engineer` und `security-engineer` (Schritt 3). Der
  `security-engineer` wurde trotz reiner Frontend-Umordnung gerufen, weil die umgebaute Datei die
  XSS-Zusage an den Feinlabels trägt; sein Ergebnis ist "nicht sicherheitsrelevant" plus die
  Testauflage oben.
- **Begleitend gepflegte lebende Dokumente:** `specs/architecture/0002-testkonzept.md` (neue
  Frontend-Sektion zum Teilrendering derselben Komponente),
  `specs/architecture/0003-securitykonzept.md` (Konsultationsvermerk),
  `specs/architecture/0004-design-system.md` (zwei Muster-Einträge).

## Offene Fragen

Keine. Die einzige Weggabelle mit Produktcharakter (wohin gehört die einzeilige
"Kategorie"-Anzeige?) ist durch den Zielabschnitt der Story bereits beantwortet: "bewerten,
Kategorie prüfen und gegebenenfalls korrigieren".

## Out of Scope

- Rasteransicht, Kuratierungsansicht und Vergleichsansicht — bleiben ausdrücklich unverändert
  (Akzeptanzkriterium 8).
- Jede Änderung an Funktion, Beschriftung oder Verhalten der Bedienelemente selbst
  (Akzeptanzkriterium 4). Insbesondere: kein neuer Fehler-Alert für fehlgeschlagenes
  Übernehmen/Zurücksetzen — den gibt es heute nicht, und diese Spec führt ihn nicht ein.
- Zuklappen, Ausblenden oder Verbergen der Informationsanzeigen hinter einer Bedienhandlung
  (Akzeptanzkriterium 3) — ausdrücklich verworfene Alternative zur Umordnung.
- Änderungen an Tastenkürzeln oder Wischgesten, etwa neue Kürzel für die Kategorie-Korrektur
  (Akzeptanzkriterium 5).
- Die Position von Shortcut-Zeile und Zähler oberhalb des Fotos.
- Eine Ergänzung von `specs/README.md` um den für Feature-Specs längst praktizierten
  Teil-Vermerk — sinnvoll, aber eigenständiger Doku-Nachzug.
