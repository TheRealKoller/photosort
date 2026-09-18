# 0497 - Bilddetailansicht zeigt das Foto groß und das Urteil zuerst

**Status:** Implemented ([PR #509](https://github.com/TheRealKoller/photosort/pull/509))
**Erstellt:** 2026-09-18
**Bezug:** [Issue #497](https://github.com/TheRealKoller/photosort/issues/497)

**Zum Umfang:** Diese Spec überschreitet den Richtwert von rund 200 Zeilen, weil elf geschärfte
Akzeptanzkriterien, der Schnitt einer bestehenden Seite in vier neue Komponenten und die
Messvorschriften für drei in jsdom nicht prüfbare Geometriezusagen zusammen in einem Dokument
stehen müssen — getrennt gelesen führt jeder Teil in die Irre.

## Ziel

Die Bilddetailansicht ist die eine Ansicht, deren Zweck das Beurteilen eines einzelnen Fotos ist.
Heute bekommt das Foto rund ein Drittel der Bildschirmbreite, während Bewertung, Motive,
Qualitätswerte, Bildinhalt, Aufnahmezeit und Cloud-Status als eine lange Spalte darunter stehen.
Beim Durchsehen vieler Fotos entscheidet aber die Größe des Bildes, wie gut sich beurteilen lässt.

Die Ansicht wird deshalb neu gestaltet: das Foto groß und immer vollständig, die Bewertung
unmittelbar darunter, und alles, was das System über das Foto weiß, dahinter — mit dem Urteil
vorweg und den Einzelwerten als Nachschlagraster. Für beide Nutzer und für beide Prüfbreiten.

## User Story

Als Nutzer, der ein einzelnes Foto beurteilt, möchte ich das Bild so groß wie möglich und zusammen
mit den Bewertungstasten sehen, ohne zu scrollen, damit ich schnell und sicher entscheiden kann —
und die Einzelheiten erst dann lesen muss, wenn ich sie wirklich brauche.

## Akzeptanzkriterien

- [x] **AK1 — Entwurf vorhanden.** Für die Bilddetailansicht liegt ein Entwurf in der Design-Datei
      vor, in beiden Prüfbreiten und mit den Zuständen Regelfall, ladend und fehler.
- [x] **AK2 — Bühne ohne Scrollen.** Beim Öffnen der Ansicht liegen auf beiden Prüfbreiten
      (360×740 und 1280×800) Fotofläche, Bewertungsleiste **und** Navigationszeile (Zurück/Weiter)
      vollständig im Sichtfenster, ohne dass gescrollt wurde (`scrollY === 0`) — und zwar obwohl
      die Seite darunter nachweislich weiteren Inhalt trägt (`scrollHeight > innerHeight`). Der
      zweite Halbsatz gehört zur Zusage: ohne ihn ist sie auf einer zufällig kurzen Seite trivial
      erfüllt.
- [x] **AK3 — Das Foto vollständig.** Drei getrennte Messungen:
      **3a nicht beschnitten** — das aus `naturalWidth`/`naturalHeight` und Elementkasten
      errechnete Inhaltsrechteck des Bildes liegt vollständig im Elementkasten und vollständig im
      Sichtfenster.
      **3b nicht überlagert, nicht geklippt** — an den vier Ecken des Inhaltsrechtecks (1 px
      eingerückt) liefert `document.elementFromPoint` das Bild selbst oder einen Nachfahren.
      **3c nicht gedämpft** — auf dem Bild und auf keinem seiner Vorfahren steht eine Deckkraft-,
      Filter- oder Mischmodus-Utility.
- [x] **AK4 — Keine Angabe geht verloren.** Eine Maximal-Fixture zeigt **ohne jede Bedienhandlung**:
      Albumtauglichkeitsstufe und Begründung, Rang im Ereignis, alle Feinlabel, die acht
      Qualitätswerte, die sieben Bildinhalt-Werte, die Grundlagenzeile, die acht Motivstärken (als
      zugänglicher Name der Symbole), die wirksame Aufnahmezeit samt Originalzeit und
      Korrekturmarke, Kamera, Ort und beide Cloud-Phasen. Hinter **genau einer** Aufklapphandlung
      stehen nur: das Motiv-Glossar und die Detailzeile eines Motivs samt Korrekturschaltern. Die
      Sollmenge steht literal als Sondenliste im Test und wird als **Menge** verglichen.
- [x] **AK5 — Urteil deutlich größer.** Die Schriftgröße der Albumtauglichkeits-Zeile beträgt im
      Browser mindestens das **1,4-fache** der Schriftgröße eines Werts im Einzelwerte-Raster,
      gemessen im selben Lauf; beide Bezugsgrößen sind vorher als > 0 zugesichert. Das Urteil
      (Albumtauglichkeit mit Begründung, Rang, Feinlabel, Motive) steht im Dokument **vor** den
      Einzelwerten.
- [x] **AK6 — Reservierter Platz bewegt nichts.** Auf beiden Prüfbreiten ändert sich die Oberkante
      des ersten Elements unterhalb des Motivbereichs (Kopfzeile „Qualität — Einzelwerte") um höchstens 1 px,
      wenn nacheinander (i) das Motiv mit dem **längsten** Anzeigenamen angeheftet, (ii) ein Motiv
      **mit bestehender Korrektur** angeheftet, (iii) ein Motiv per **Tastaturfokus** vorangezeigt
      und (iv) wieder zugeklappt wird. Vorbedingung je Schritt: der Inhalt der Detailzeile hat
      nachweislich gewechselt. Das längste Motiv wird zur Laufzeit aus den acht zugänglichen Namen
      ermittelt, nie hartkodiert — sonst ist die Reservierung auf den heutigen Registry-Stand
      kalibriert und bricht still, wenn ein Anzeigename wächst.
- [x] **AK7 — Der reservierte Platz erklärt die Bedienung.** Solange kein Motiv aufgeklappt ist,
      steht dort der Aufforderungssatz statt einer leeren Fläche. Beide Zustände trägt **derselbe**
      Container — das ist die Bauform, die die Reservierung möglich macht.
- [x] **AK8 — Bedienelemente vor Information.** Die Soll-Folge in `PhotoDetailPage.test.tsx`
      („Reihenfolge: Bedienelemente zuerst") wird um die neuen Abschnitts-Handles erweitert und
      bleibt **eine** Liste in **einem** `toEqual`.
- [x] **AK9 — Gleiche Lesereihenfolge, kein Querscrollen.**
      **9a** Die Abschnittsfolge ist auf beiden Prüfbreiten dieselbe. Nachgewiesen als
      Abwesenheitszusage am Quelltext: keine breakpoint-gebundene `order-*`-Utility, kein
      `*-reverse`, keine viewport-abhängige Verzweigung im Rendering.
      **9b** Auf Telefonbreite erzeugt die Ansicht kein horizontales Scrollen.
- [x] **AK10 — Die Bühnenhöhe hängt am Sichtfenster, nicht am Bild.** Für vier Fotos mit paarweise
      verschiedenen Originalseitenverhältnissen (quer 4:3, hoch 3:4, breit 12:5, quadratisch 1:1)
      ist die gemessene Bühnenhöhe auf derselben Prüfbreite identisch (≤ 1 px), und in allen vier
      Fällen bleiben Bewertungsleiste und Navigation im Sichtfenster und das Bild vollständig
      eingepasst (AK3a/3b). Die Verschiedenheit der vier Eingaben ist Vorbedingung, sonst ist
      Gleichheit trivial erfüllt. Ein breitengeführtes Bild (`aspect-*`) fällt damit durch: es
      machte die Bühne je Format verschieden hoch und schöbe beim Hochformat die Bewertungsleiste
      aus dem Bild.
- [x] **AK11 — Design-Nutzlast geführt.** Die Ansicht ist in der Design-Nutzlast des Repositories
      geführt, und die beiden aus Story #490 stammenden Motiv-Bausteine sind dort ebenfalls
      aufgenommen.

## Datenmodell-Bezug

Keine Änderung. Alle Angaben liegen bereits auf `PhotoOut` (`motifs`, `album_suitability`,
`ranking`, `fine_labels`, `criterion_scores`, `camera`, `event`/`place`, `cloud_vision_status`).

## Architektur / Umsetzung

Reine Frontend- und Design-Nutzlast-Änderung: kein Backend-Anteil, kein neues API-Feld, keine neue
Abhängigkeit, keine neue ADR.

### Aufbau der Seite

`pages/PhotoDetailPage.tsx` bleibt der einzige Ort für Datenzugriff, Navigation (Pfeiltasten,
Wischen, Auto-Advance) und Bewertungs-Mutationen. Die Darstellung wird in vier Teile geschnitten:

1. **`components/PhotoDetailStage.tsx` (neu)** — die Bühne: Zählerzeile, Fotofläche,
   `RatingButtons`, Zurück/Weiter. Sie trägt die gesamte Höhengeometrie und bekommt Zustand und
   Handler als Props; sie entscheidet nichts selbst.
2. **`components/PhotoVerdict.tsx` (neu)** — das Urteil: Albumtauglichkeit mit Begründung, Rang im
   Ereignis, Feinlabel. Die Motive stehen als `MotifStrengthSection` daneben; die Seite setzt beide
   in eine gemeinsame Urteilsfläche.
3. **`components/CriterionScoreGrid.tsx` (neu)** — die fünfzehn Einzelwerte (acht Qualität, sieben
   Bildinhalt) als mehrspaltiges Nachschlagraster, auf Telefonbreite einspaltig.
4. Unverändert weiter darunter: Aufnahmezeit/Kamera-Abschnitt, `CloudVisionStatusList`, der
   Vorschlagskasten.

`components/CriterionDetailsList.tsx` bleibt bestehen und behält seine Aufrufstelle im
Kachel-Popover (`CriterionDetailsPopover.tsx`). Die Detailseite bindet sie **nicht** mehr ein —
kompaktes Popover und großes Seitenurteil sind zwei Darstellungen, keine Variante voneinander.
Geteilt wird nur, was zeichengleich ist:

- **`utils/criterionScores.ts` (neu)** — die Aufteilung nach `has_presence_threshold`, bisher privat
  in `CriterionDetailsList.tsx`. Beide Darstellungen lesen dieselbe Funktion, damit Qualität und
  Bildinhalt nicht an zwei Stellen verschieden geschnitten werden.
- **`components/FineLabelList.tsx` (neu)** — die Feinlabel-Chips, von `CriterionDetailsList` und
  `PhotoVerdict` benutzt.

### Foto vollständig ohne Scrollen

Die Bühne ist ein Flex-Spalten-Behälter mit einer an den Sichtbereich gebundenen Höhe:
`h-[calc(100dvh-var(--spacing-header)-var(--spacing)*6)]` — sichtbare Höhe abzüglich Kopfzeile und
des oberen Innenabstands der Inhaltsspalte (`py-6` an `main` in `App.tsx`). Die Kopfzeilenhöhe
kommt aus demselben `--spacing-header`, aus dem `h-header`/`top-header` entstehen; ein zweiter
Zahlenwert dafür ist verboten. Innerhalb der Bühne behalten Bewertungsleiste und Navigationszeile
ihre inhaltsbestimmte Höhe, die Fotofläche nimmt mit `flex-1 min-h-0` den Rest. Das Bild steht
darin als `h-full w-full object-contain` — vollständig, nie beschnitten, weder auf Breite noch auf
Höhe festgelegt und damit auf Telefonbreite von selbst höhengeführt. Keine Mindesthöhe auf der
Fotofläche: bei einem sehr flachen Fenster schrumpft das Bild, statt die Bedienleiste
hinauszuschieben. Keine in JavaScript gemessene Höhe und kein gerechneter Wert in einem Inline-Stil.

Der willkürliche Wert ist im Design-Vertrag freigabepflichtig: In `designSystem.contract.test.ts`
entfällt der Eintrag `aspect-[4/3] w-full` für `src/pages/PhotoDetailPage.tsx` (eine verwaiste
Freigabe ist rot) und kommt ein Eintrag für die Bühnenhöhe in `src/components/PhotoDetailStage.tsx`
hinzu. Weist der Vertrag die Klasse zurück, ist der Ausweg **weder** eine in JavaScript gemessene
Höhe im Inline-Stil **noch** eine CSS-Custom-Property als Träger eines gerechneten Wertes — beides
ist im Sicherheitskonzept untersagt; der Widerspruch wird im Design-Vertrag aufgelöst.

Die Zustände *ladend* und *fehler* rendern denselben Rahmen wie der Regelfall — Bühne mit
Platzhaltern statt eines vorgezogenen Satzes, Fehlertext im `Alert` innerhalb des Rahmens. Sonst
springt die Seite beim Eintreffen der Daten.

### Reservierter Platz der Motivzeile

Die Reservierung sitzt in `components/MotifStrengthSection.tsx` an der Detailzeile und folgt
`rowsEditable` (`editable && !excluded`), nicht `editable` allein: Bei einem als Dokument
ausgeschlossenen Foto gibt es keine Korrekturschalter, und eine Reservierung nach `editable` ließe
dort dauerhaft leere Fläche stehen, die nie gefüllt wird. Umgesetzt als `min-h-*` auf dem Behälter
der Detailzeile, bemessen am ungünstigsten Fall (Telefonbreite, längster Motivname neben dem
längsten Werttext, drei Schaltflächen in zwei Reihen) und **am Bestand gemessen statt geschätzt**.
`min-h-*` ist eine Größen-, keine Abstands-Utility und unterliegt der Rasterregel nicht; landet der
gemessene Wert nicht auf einer Tailwind-Stufe, braucht er seinerseits einen Freigabeeintrag mit
Begründung im Design-Vertrag.

### Ort

Der Ort eines Fotos ist der Ort seines Ereignisses. Die dreistufige Namenswahl (Sehenswürdigkeit →
aufgelöster Ortsname → keiner) steht heute in `utils/timeOfDay.ts::formatEventHeading`; sie wird
dort als eigene Funktion herausgezogen und von beiden Stellen benutzt, damit die Rangfolge nicht
ein zweites Mal entsteht. Die Detailseite zeigt allein den Namen ohne Zeitspanne — die Aufnahmezeit
steht direkt darüber — und ohne Ortsangabe „nicht bestimmbar" statt einer Lücke. Die Koordinate
erscheint nicht als Name.

### Design-Nutzlast

Die Ansicht `bilddetail` steht bereits in `design/penpot/views.json`. Die beiden Motiv-Bausteine
kommen hinzu; das zieht fünf Stellen nach, und wird eine vergessen, wird
`frontend/penpot/payload.test.ts` rot:

1. `design/penpot/components.json`: `motiv-reihe` („Motivreihe", Quelle
   `src/components/MotifStrengthSymbol.tsx`) mit der Achse der vier Füllstufen und den drei
   Bandfarben plus dem Umriss als Tokens je Ausprägung; `motiv-bereich` („Motivbereich", Quelle
   `src/components/MotifStrengthSection.tsx`) mit der Achse `zustand` und den vier Ausprägungen
   `regelfall`, `gewaehlt`, `schreibgeschuetzt`, `nicht-klassifiziert`. Beide ans Ende der Liste,
   hinter die Schrittmarke. Trägt eine Achse keine eigenen Tokens, bekommt sie einen Eintrag in
   `ACHSEN_OHNE_EIGENE_TOKENS` mit Begründung statt einer Achse ohne Aussage.
2. `design/penpot/views.json`, Ansicht `bilddetail`: die Lücke `motivbaustein` entfällt, die beiden
   Schlüssel treten in `bausteine` ein, und `produktdateien` nennt die tatsächlich gebauten Dateien.
   Die übrigen Lücken bleiben stehen.
3. `design/penpot/verify.js`: `ERWARTETE_BAUSTEINE` folgt der Regel „Bausteine aus
   `components.json` plus der Chip, der in der Datei geführt wird und in der Liste nicht" — die
   Ableitung steht neben der Konstante.
4. `frontend/penpot/payload.test.ts`, `FREIGABEN`: der Eintrag zu `ERWARTETE_BAUSTEINE` trägt den
   Wert doppelt (`wert` und `ausschnitt`) und wird an beiden Stellen mitgeändert.
5. `frontend/penpot/payload.test.ts`: die hart hinterlegte Liste der Bausteinschlüssel und
   Anzeigenamen (Reihenfolge zählt), die eingefrorene Variantenzahl, und die Karte der gebauten
   Ansichten bekommt `bilddetail` mit `src/pages/PhotoDetailPage.tsx`.

Der Pull Request ändert ausschließlich Repository-Dateien. Die Design-Datei selbst wird nicht
angefasst — die Nutzlast ist die Quelle, die Datei folgt ihr beim nächsten Aufbaulauf.

### Reihenfolge der Umsetzung

Von unten nach oben, jeder Schritt für sich rot-grün lauffähig:

1. `utils/criterionScores.ts` herausziehen, `CriterionDetailsList` darauf umstellen — ohne sichtbare
   Änderung.
2. `components/FineLabelList.tsx` herausziehen, `CriterionDetailsList` darauf umstellen.
3. Ortsnamen-Funktion aus `formatEventHeading` herausziehen.
4. `CriterionScoreGrid.tsx`.
5. `PhotoVerdict.tsx`, samt Regressionstest gegen `dangerouslySetInnerHTML`.
6. Reservierter Platz in `MotifStrengthSection.tsx`.
7. `PhotoDetailStage.tsx` — zuerst die Höhengeometrie samt Freigabe im Design-Vertrag, dann die
   Zusammensetzung, dann die Zustände ladend und fehler.
8. `PhotoDetailPage.tsx` neu zusammensetzen; Navigation, Tastenbelegung, Wischen und Auto-Advance
   bleiben unverändert dort.
9. Design-Nutzlast (die fünf Stellen oben), danach `npx vitest run penpot/payload.test.ts`.
10. `docs/architecture.md` im selben Pull Request nachziehen.

## UI/UX

**Stand:** ausgearbeitet
**Penpot-Seite:** Ansicht — Bilddetail
**Schlüssel:** bilddetail

### Ablauf und Layout

**Beide Breiten, vier übereinanderliegende Bereiche:**

1. **Bühne** (höhenbegrenzt): Zählerzeile, Fotofläche mit `object-contain`, Bewertungsleiste,
   Navigationszeile. Zusammen ohne Scrollen im Sichtbereich, gemessen ab Unterkante Kopfzeile.
2. **Urteilsfläche**: Albumtauglichkeit mit Begründung, Rang im Ereignis, Feinlabel. Darunter der
   Motivbereich, dessen Detailzeile den reservierten Platz hält.
3. **Einzelwerte-Raster**: zwei Kopfzeilen („Qualität — Einzelwerte", „Bildinhalt — Einzelwerte"), darunter die acht bzw.
   sieben Werte als kompakte Zeilen (Name, Wert). Desktop zwei bis drei Spalten, Telefonbreite
   einspaltig.
4. **Weitere Angaben**: Aufnahmezeit mit Originalzeit und Korrekturmarke, Kamera, Ort,
   Cloud-Phasen.

**Auf Telefonbreite** nimmt die Bühne die gesamte verfügbare Höhe; das Foto folgt der Höhe statt
der Breite und bleibt auch im Hochformat vollständig sichtbar. Bewertungsleiste und
Navigationszeile bleiben ohne Scrollen erreichbar, die übrigen Bereiche folgen darunter scrollbar.

**Zustände.** *Regelfall:* Foto geladen, alle Werte sichtbar. *Ladend:* Fotofläche mit
Platzhalter, Raster mit Platzhalterzeilen; Bühne und Bewertungsleiste stehen bereits in ihrer
endgültigen Geometrie. *Fehler:* Bühnenrahmen bleibt, in der Fotofläche ein `Alert`
(„Bild konnte nicht geladen werden"); Bewertung und Navigation sichtbar, aber nicht aktiv.

### Typografie

| Element | Stufe |
|---|---|
| Albumtauglichkeitsstufe | `text-lg` (20px) |
| Feinlabel-Chips, Motivbereich-Inhalte | `text-base` (16px) |
| Begründung, Rang, Einzelwert-Zeilen | `text-sm` (14px) |
| Labels und Kopfzeilen | `text-xs font-semibold uppercase tracking-wide` |

Der Sprung von `text-lg` auf `text-sm` ist der Faktor 1,43 und trägt damit AK5 (Schwelle 1,4). Er
entspricht dem Abstand „Fließtext (Medium)" zu „Komponententext" der Typografie-Leiter des
Design-Systems.

**Groß gesetzt ist allein die Stufe.** Begründung und Rang stehen klein unter ihren Labels — sie
erläutern die Stufe, sie wiederholen ihren Rang nicht. Sie liegen damit auf derselben Stufe wie
die Einzelwerte, so wie im Entwurf.

### Oberflächentexte

- Fehlende Ortsangabe: „nicht bestimmbar".
- Motivbereich-Kopf: „Motive". Raster-Kopfzeilen: „Qualität — Einzelwerte" und
  „Bildinhalt — Einzelwerte".
- Labels der Urteilsfläche: „Albumtauglichkeit" und „Rang im Ereignis"; der Rang steht darunter
  als „3 von 14", ohne das vorangestellte Wort.
- Motivzeile ohne Auswahl: der bestehende Aufforderungssatz aus Spec 0490.

### Design-System

Urteil und Motivbereich in `--text-h`, Einzelwerte in `--text`. Abstände auf dem 8-Punkt-Raster,
Fotofläche `rounded-md`, Urteilsfläche in der gewohnten Panelform. Hierarchie darf **nicht** allein
über `--text` gegen `--text-muted` aufgebaut werden — diese beiden Stufen sind nebeneinander nur
schwach unterscheidbar; Größe, Schnitt und Reihenfolge tragen sie.

### Offener Punkt am Entwurf

Ob der Entwurf eine **Ortszeile** führt, lässt sich aus `design/penpot/views.json` nicht
feststellen — sie steht dort weder als Lücke noch als Eintrag. Die Spec sieht sie vor, weil AK4
den Ort nennt; ein Blick in die Design-Datei entscheidet, ob sie im Entwurf tatsächlich vorkommt.
Weicht der Entwurf ab, ist die Zeile billig zu streichen.

## Security

Sicherheitsrelevant, und zwar aus genau einem Grund: Der Neuschnitt verteilt extern erzeugten Text
auf neue Komponenten und bringt den **Ort erstmals auf diese Route**. Kein Backend-Anteil, kein
neues API-Feld, kein neues Secret, keine Änderung an Auth und keine an der Sichtbarkeit zwischen
den beiden Nutzern.

**S1 — Fünf Fremdtextfelder, eine Auflage.** Ausschließlich als regulärer React-Textknoten rendern:
nie `dangerouslySetInnerHTML`, nie als HTML-String-Prop einer Radix-/shadcn-Komponente, nie als
Markdown oder Rich-Text, nie in `href`/`src`/`style`, nie in einem `url()`-Kontext, nie als
React-`key`. Betroffen sind `fine_labels[].display_name` (und `raw_label`, falls er in ein
`title`-Attribut geht), `album_suitability.reason`, `event.place.landmark_name`, `event.place_name`
und `camera.label`. **Angriffsmodell:** Das Session-Token liegt in `localStorage`; ein
eingeschleustes Skript liest es unmittelbar aus und hat damit bis zu 30 Tage Sitzungsübernahme ohne
Widerrufsweg. Das Verbot ist die tragende Voraussetzung jener Auth-Entscheidung.

**S2 — Der Ort ist auf dieser Seite Erstkontakt, und es sind zwei Felder, nicht eines.** Die
dreistufige Namenswahl liest `event.place.landmark_name` (Modellantwort) **und** `event.place_name`
(Ortsdatensatz Dritter); beide tragen S1. Die herausgezogene Funktion bleibt eine reine Funktion
über der Event-Zeile und setzt nichts zusammen — die zusammengesetzte Form „Ort, Viertel" kommt
fertig vom Server. **Der Nachweis gehört an die Renderstelle, nicht in den Test der Funktion:** Dass
die Funktion nichts interpretiert, sagt nichts darüber, was das Markup daraus macht.

**S3 — Schlüssel kommen nie aus dem Text.** Feinlabel-Chips werden über `canonical_key`
geschlüsselt, Kriterienzeilen über ihren Registry-Schlüssel, nie über einen Anzeigenamen. Bei
`place_name` ist das nicht nur XSS-Hygiene: Gleichnamigkeit ist der Normalfall, und ein doppelter
Schlüssel bringt die Listenabgleichung von React durcheinander.

**S4 — Die Begründung bleibt als Aussage des Modells kenntlich.** `album_suitability.reason` stammt
aus einem Bild, das selbst Text enthalten kann. `PhotoVerdict.tsx` weist sie erkennbar als
Modellaussage aus, nicht als Aussage von PhotoSort. Bei Verletzung wird eine über Prompt-Injection
erzeugte Zeile zur Systemaussage — Wirkung ist Irreführung des Nutzers, nicht Codeausführung. Die
Begründung wird ungekürzt gezeigt; Kappung findet an der Quelle statt.

**S5 — Die Regressionstests wandern mit der Renderstelle.** Jede neue Komponente, die eines der
Felder aus S1 trägt, bekommt den Test, den `CriterionDetailsList.test.tsx` und
`CloudVisionStatusList.test.tsx` dafür bereits führen: feindlich belegtes Feld hinein, Text im DOM,
`document.querySelector('img[src="x"]')` leer, kein gesetztes `window`-Flag. Konkret
`PhotoVerdict.tsx`, `FineLabelList.tsx` und die Stelle, die den Ort zeigt. **Bei Verletzung bleibt
der Schutz nominell bestehen und ist tatsächlich weg:** Ein in `CriterionDetailsList.test.tsx`
verbliebener Test bleibt grün, obwohl die Komponente den Text nicht mehr rendert.

**S6 — Keine Sanitisierung im Frontend.** Zeichensanitisierung und Längengrenzen bleiben
ausschließlich an der Quelle. Eine zweite Fassung im Frontend liefe mit der ersten auseinander.

**Geprüft und ohne Befund.** Die Höhengeometrie ist eine statische Zeichenkette ohne jeden API-Wert
und fällt nicht unter die Custom-Property-Auflage. Motivnamen, Kriterien-Beschriftungen und
Vorschlagsgründe stammen aus geschlossenen Server-Registries. `camera.label` ist an der Quelle von
unsichtbaren Zeichen befreit und längenbegrenzt und wird im Frontend nie aus `make`/`model`
zusammengesetzt. Das Sicherheitskonzept braucht keine Fortschreibung: die Auflagen hängen am Feld,
nicht an der Route, und seine Ankerliste führt keine Frontend-Renderstelle.

**Bewusst getragen.** Zeigt die Bühne den Dateinamen als sichtbaren Text, gilt der Präzedenzfall aus
Spec 0321: reiner Textknoten, kein `href`/`src` (Bildabrufe sind id-basiert), das Restrisiko der
optischen Verdrehung durch Unicode-Richtungssteuerzeichen ist abgewogen. Jeder Screenshot dieser
Ansicht entsteht gegen den synthetischen Demo-Stand, nie gegen echte Fotos; kein echter Dateiname
steht in Spec, Commit-Nachricht oder PR-Beschreibung.

## Teststrategie

Kein Backend-Anteil, also keine `pytest`-Zeile und kein Einfluss auf `--cov-fail-under=80`.

**Unit/Komponente (`vitest`, jsdom) — der Schwerpunkt.**

- `utils/criterionScores.ts`: Partition nach `has_presence_threshold` tabellengetrieben, inkl. leere
  Eingabe und ein Kriterium ohne das Feld.
- `FineLabelList`, `PhotoVerdict`, `CriterionScoreGrid`, `PhotoDetailStage`: je Testfall für
  Regelfall / leer / fehlend. Keine CSS-Assertions; Selektion über Rolle, `aria-*`, semantische
  `data-*`.
- **Bestandsliste (AK4)** als ein `toEqual` über eine literal notierte Sondenliste.
- **Abschnittsfolge (AK5, AK8)**: die bestehende `inDocumentOrder`-Hilfe weiterverwenden, Soll-Folge
  um Urteilsfläche und Einzelwerte-Raster erweitern.
- **Drei Zustände**: dieselbe Sondenliste für den Rahmen (Zählerzeile, Bewertungsgruppe,
  Navigationszeile) dreimal, plus im Fehlerfall `disabled` an Bewertung und Navigation. Ladezustände
  kommen ausdrücklich **nicht** in den e2e-Satz.
- **Sicherheit:** die Regressionsfälle aus S5.

**Regressionsnachweis mit Zahl.** Gemessene Ausgangslage vor der Umsetzung:
`PhotoDetailPage.test.tsx` 54, `MotifStrengthSection.test.tsx` 84, `CriterionDetailsList.test.tsx`
32, `CriterionDetailsPopover.test.tsx` 26 — zusammen 196 grüne Fälle. Für die drei
Komponentendateien gilt: kein geänderter Bestandsfall, neue Fälle nur in neuen `describe`-Blöcken;
ein Diff an einem Bestandsfall ist ein begründungspflichtiger Review-Befund. `PhotoDetailPage.test.tsx`
wird umgebaut — dort bleibt die **Menge der geprüften Verhaltensweisen** vollständig, Fälle dürfen in
die neuen Komponentendateien umziehen, aber keiner verschwindet ersatzlos.

**E2E — ein neuer Spec `e2e/tests/bilddetail-buehne.spec.ts`.** Aufnahmekriterium erfüllt: alle drei
Zusagen sind echte Geometrie bzw. echtes CSS, in jsdom prinzipiell nicht messbar (`dvh`/`calc`
werden dort nicht ausgewertet). Drei Fälle, eine Route, ein geseedeter Durchgang:

1. **Bühne** (AK2, AK3a/3b, AK10): vier Formate durchblättern, natürliche Seitenverhältnisse als
   paarweise verschieden zusichern, Bühnenhöhe gleich, Bewertungsleiste und Navigation im
   Sichtfenster, Inhaltsrechteck eingepasst, Treffertest an dessen vier Ecken.
2. **Reservierter Platz** (AK6): Oberkante der Kopfzeile „Qualität — Einzelwerte" über vier Zustände,
   Wechselnachweis der Detailzeile je Schritt.
3. **Typografischer Abstand** (AK5): Verhältnis zweier im selben Lauf gemessener `font-size`-Werte.

Der Spec läuft **in beiden Viewport-Projekten** — er steht damit in **keiner** der Listen
`MOBILE_ONLY`/`DESKTOP_ONLY` in `e2e/playwright.config.ts` und wird in `toolchain.spec.ts` in die
Liste `beidbreitig` aufgenommen, sonst ließe sich die Zweibreitigkeit später still wegkonfigurieren.
Der Spec ist **lesend**: Motive anheften ist reiner Client-Zustand; Korrekturschalter werden nur
gemessen, nie geklickt. Das Format wird aus `naturalWidth`/`naturalHeight` gelesen, nie aus dem
Index des Demo-Seeders geschlossen.

**Rot-Nachweis (Pflicht bei Einführung, gehört in die PR-Beschreibung):** je Fall einmal mutwillig
brechen und den roten Lauf belegen — (1) `flex-1 min-h-0` durch `aspect-[4/3] w-full` ersetzen, (2)
die `min-h-*`-Reservierung entfernen, (3) die Typo-Stufe des Urteils auf die des Rasters setzen.

**Ein struktureller Wächter, `frontend/src/photoDetail.structure.test.ts`**, Umgebung `node`,
Bauform wie `photoGridTile.structure.test.ts` (Selbstausschluss, Positiv-Gegenprobe,
Mengengleichheit statt „enthält nicht"):

- `CriterionDetailsList` hat **genau** die Aufrufstelle `components/CriterionDetailsPopover.tsx`.
  Ein späterer Rück-Import in die Detailseite zeigte die Aufschlüsselung doppelt in zwei Idiomen und
  sähe in jedem Komponententest richtig aus.
- Der Feldname `has_presence_threshold` steht in den Produktivquellen **genau** in `api/types.ts`
  und `utils/criterionScores.ts`. Eine zweite, inline nachgebaute Aufteilung bricht still.
- Die dreistufige Ortsnamen-Wahl steht in genau einer Funktion; beide Aufrufstellen importieren sie.

Ein **zweiter** Wächter über die Höhen-Klassenliterale entsteht nicht: Die fundstellengenaue
Freigabeliste des Design-Vertrags leistet die Literal-Bindung bereits vollständig, inklusive der
Fehlerklasse „verwaiste Freigabe". Ebenfalls **nicht** in einen Test kommt „keine JS-Höhenmessung" —
kein stiller Fehlermodus; das gehört auf die Liste von `review-architecture`.

**Unverändert bestehen bleiben müssen (ohne Anpassung der Assertions):**
`no-horizontal-scroll.spec.ts` (die Vorbedingung der Detailroute hängt an `role="group"` /
„Bewertung"; die Gruppe wandert in `PhotoDetailStage`, Rolle und `aria-label` bleiben — ebenso der
Fall „acht Motivsymbole in einer Zeile bei 360 px") und `tap-targets.spec.ts`
(`EXPECTED_CONTROL_COUNT = 21`; ändert der Umbau den Weg zum Motiv-Korrekturschalter, ist die Zahl
anzuheben und der Grund zu nennen, nie stillschweigend anzupassen).

**Edge Cases.** Hochformat 3:4 bei 360 px (der Leitfall); Breitformat 12:5 und Quadrat 1:1 als
Gegenrichtung; Bildfehler (Bühnenrahmen bleibt, `Alert` in der Fotofläche); Foto ohne
Klassifizierungslauf (Urteilsfläche und Raster fallen weg, Bühnenrahmen bleibt — dann existiert
keine Motiv-Detailzeile, und das ist kein Verstoß gegen AK6); ausgeschlossenes Dokument (Reihe
einsehbar, keine Korrekturschalter, keine Reservierung); längster Motivname neben längstem Werttext
mit drei Schaltflächen bei 360 px; Tastaturfokus statt Klick; Abschlusszustand „kein unbewertetes
Foto mehr"; viele Feinlabel-Chips. **Nicht von AK6 erfasst:** der `Alert` einer fehlgeschlagenen
Korrektur verschiebt, was darunter steht — das ist kein Auf-/Zuklappen.

**Bekannte Lücke.** `100dvh` gegen eine dynamische Browserleiste ist im Prüfsatz nicht belegbar —
headless Chromium hat keine ein- und ausfahrende Adressleiste. Der Spec belegt die Rechnung, nicht
das Verhalten auf einem echten Telefon; das bleibt ein manueller Blick vor dem Merge.

`specs/architecture/0002-testkonzept.md` wird im Umsetzungs-PR ergänzt: die Umkehrung der
Unterschiedsregel (n Messungen, die gleich sein müssen, mit der Verschiedenheit der Eingaben als
Vorbedingung); „nichts bewegt sich" als Testgegenstand (Bezugselement unterhalb des wachsenden
Bereichs, je Zustandswechsel der Nachweis, dass er stattgefunden hat); ein dritter Beleg für
„Trefferflächen werden getroffen, nicht gemessen" (das Inhaltsrechteck eines
`object-contain`-Bildes taucht in keiner `boundingBox()` auf); und die `dvh`-Lücke.

## Entscheidungen

- **AK10 umformuliert.** „Das Foto folgt der Höhe" ist als Invariante formatabhängig und hätte einen
  auf den Ist-Zustand kalibrierten Test erzwungen. Die Formatinvarianz der Bühnenhöhe ist strenger,
  nicht schwächer: sie schließt jede breitengetriebene Höhe aus.
- **AK4 nennt den Ort, obwohl er neu ist.** Die Detailseite zeigt heute keinerlei Ortsangabe; das
  Kriterium „alle heute vorhandenen Angaben … Ort" ist an dieser Stelle sachlich falsch. Der Ort
  wird trotzdem gezeigt — die Absicht des Kriteriums ist eindeutig —, aber als Neuzugang behandelt:
  mit eigenem XSS-Nachweis an der neuen Renderstelle (S2), nicht unter Berufung auf den bestehenden
  Nachweis in `AlbumDraftPage.test.tsx`.
- **Schwelle für AK5 ist 1,4** — `text-lg` gegen `text-sm` ergibt 1,43. Die Schwelle steht als
  Produktzusage in der Spec, nicht im Test.
- **`CriterionDetailsList` bleibt bestehen**, statt für beide Stellen parametrisiert zu werden: Der
  geteilte Anteil ist klein und wird tatsächlich geteilt; der Rest unterscheidet sich in
  Elementstruktur und Schriftgröße, eine gemeinsame Komponente hätte zwei sich ausschließende Zweige.
- **Reservierung folgt `rowsEditable`, nicht `editable`** — sonst bliebe bei einem ausgeschlossenen
  Foto dauerhaft toter Raum stehen.
- **Vollabdeckung statt Stichprobe bei AK4:** Bei einem Umbau, dessen einziger ernster Fehlermodus
  der stille Verlust einer Angabe ist, wäre eine Stichprobe die teurere Wahl.
- **Kein neuer ADR.** Keine neue Technologie, keine externe Abhängigkeit, keine
  Datenmodell-Änderung; alle Entscheidungen liegen innerhalb bestehender, dokumentierter Muster.
- **Keine Fortschreibung des Sicherheitskonzepts:** Die bestehenden Auflagen hängen am Feld und
  decken die neuen Renderstellen wortgleich ab.

### Bei der Umsetzung hinzugekommen

Drei Festlegungen, die der Umsetzungsplan nicht vorsah und die erst der Prüfsatz erzwungen hat:

- **Die Seite setzt den Scrollstand je Foto zurück.** Ohne das ist AK2 im Normalgebrauch verletzt:
  Wer ein Foto aus einem bereits gescrollten Raster öffnet, landet auf einer gescrollten
  Detailseite, und die aus dem Sichtfenster gerechnete Bühne steht teilweise darunter. Gebunden an
  `currentPhotoId`, nicht an den Seitenaufbau — jedes neue Foto ist erneut ein „Öffnen der
  Ansicht", innerhalb desselben Fotos nimmt die Rücksetzung dem Nutzer sein Scrollen nicht weg.
  Navigation, Tastenbelegung, Wischen und Auto-Advance bleiben davon unberührt.
- **Die Korrekturschaltflächen tragen `gap-y-4` statt `gap-3`.** In der Urteilsfläche bricht die
  dritte Schaltfläche auf Telefonbreite in eine zweite Reihe um; bei 12 px Reihenabstand stoßen die
  beiden 44-px-Trefferflächen genau aneinander, und die Subpixel-Rundung entscheidet, wer den
  Randpunkt bekommt. In einer Überlappung gewinnt das obenliegende Element — hier wäre das ein
  falsch geschriebener Datenwert.
- **Der Tastaturhinweis gehört in die Bühne und ist auf Telefonbreite ausgeblendet.** Über der
  Bühne schöbe er ihre Unterkante um die eigene Höhe unter den Sichtrand (AK2 verfehlt), unter ihr
  stünde er im Informationsteil, obwohl er über das Foto nichts sagt. Auf 360 px bricht er
  mehrzeilig um und nimmt der Fotofläche diese Höhe, ohne dort etwas zu nützen — ein Telefon hat
  keine Tastatur. Ausgeblendet wird ein Hinweis, kein Abschnitt; AK9a bleibt erfüllt.

## Offene Fragen

Keine. Der offene Punkt zur Ortszeile im Entwurf (siehe UI/UX) ist am Bild zu klären, nicht als
Produktentscheidung.

## Out of Scope

- Jede Änderung an Modell, Schwellen oder Kalibrierung der Bewertung.
- Änderungen an Navigation, Tastenbelegung, Wischen und Auto-Advance — sie bleiben unverändert in
  `PhotoDetailPage.tsx`.
- Die Darstellung im Kachel-Popover (`CriterionDetailsPopover.tsx`) bleibt zeichengleich.
- Der Wortlaut des Aufforderungssatzes der Motivzeile (offene Frage aus Spec 0490).
