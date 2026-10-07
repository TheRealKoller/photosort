# 0585 - Tippen auf ein Foto öffnet am Tablet nur die Großansicht

**Status:** Accepted
**Erstellt:** 2026-10-07
**Bezug:** [Issue #585](https://github.com/TheRealKoller/photosort/issues/585)

Umfang über dem Richtwert, weil Teststrategie und Zustandstabelle je Eingabeart die jsdom-Grenze bei `:focus-visible` tragen, ohne die die Tests den Fehler nicht zeigen.

## Ziel

Am Tablet löst ein einzelnes Tippen auf ein Foto in der Kuratierung zwei Dinge zugleich aus: Die Großansicht öffnet sich, und die Leiste mit den Zusatzangaben klappt auf. Eine Geste soll genau eine vorhersehbare Wirkung haben. Zugesagt ist (Spec 0579, Spec 0489): Kurzes Tippen öffnet die Großansicht, langes Drücken zeigt die Zusatzangaben. Die Fotoübersicht folgt derselben Zusage und wird mit behoben. Touch-Nutzung ist gleichrangig zur Desktop-Nutzung.

## User Story

Als Nutzer, der am Tablet Fotos kuratiert oder durchsieht, möchte ich, dass ein kurzes Tippen auf ein Foto nur die Großansicht öffnet. Mit einem langen Druck möchte ich die Zusatzangaben sehen, ohne die Großansicht zu öffnen. So hat jede Geste genau eine vorhersehbare Wirkung.

## Akzeptanzkriterien

Begriffe: **kurzes Tippen** = Touch-Zeiger (`pointerType: 'touch'`), Abstand `pointerdown`→`pointerup` < 500 ms (`LONG_PRESS_MS`). **Langer Druck** = Touch-Zeiger gehalten ≥ 500 ms. **Leiste** = Zusatzangaben-Leiste der Kachel (sichtbar ⇔ `data-visible="true"`). **Kachel** = jede Kachel aus AK8.

- [ ] **AK1** **Tippen auf das Foto öffnet nur die Großansicht.** Kurzes Tippen auf das Foto einer Kachel öffnet die Großansicht dieses Fotos; die Leiste dieser Kachel ist weder währenddessen noch nach dem Schließen der Großansicht (Esc, Schließen-Knopf, Zurück) sichtbar, obwohl der Fokus an das Foto zurückkehrt.
- [ ] **AK2** **Langer Druck zeigt die Leiste, öffnet nichts.** Langer Druck auf das Foto macht die Leiste sichtbar, sobald 500 ms vergangen sind (noch vor dem Loslassen); nach 499 ms ist sie nicht sichtbar. Der auf das Loslassen folgende Klick öffnet keine Großansicht und löst keine Kachel-Handlung aus.
- [ ] **AK3** **Leiste nach langem Druck schließt** bei (a) Tippen/Klick außerhalb der Kachel, (b) Scrollen der Seite. Tippen innerhalb der Kachel schließt nicht per se (es gilt AK1/AK4 für die Folgehandlung).
- [ ] **AK4** **Tippen auf einen Kachel-Knopf** (Streichen, Alternativen, Tauschen/Hinzufügen) löst genau dessen Handlung aus; die Leiste wird nicht sichtbar, auch nicht, solange der Knopf danach fokussiert bleibt.
- [ ] **AK5** **Eingabeart statt Gerät.** Ausschlaggebend ist `pointerType` des jeweiligen Ereignisses, nicht Gerätemerkmale: kein `matchMedia`-Aufruf im Hook. `touch` → Verhalten AK1–AK4; `mouse` und `pen` → Verhalten AK6 — unabhängig davon, was `(hover: hover)` meldet (Touch-Laptop mit Finger = Touch; Tablet mit Maus/Stift = Desktop).
- [ ] **AK6** **Maus/Stift unverändert.** Zeiger über der Kachel → Leiste sichtbar; Zeiger verlässt Kachel → Leiste nicht sichtbar (sofern kein Tastaturfokus, AK7); Klick auf das Foto öffnet die Großansicht; Maus-/Stift-Druck ≥ 500 ms startet **keinen** langen Druck (Klick öffnet weiterhin).
- [ ] **AK7** **Tastatur unverändert.** Erhält ein Bedienelement der Kachel Tastaturfokus (Tab), ist die Leiste sichtbar, bis der Fokus die Kachel verlässt; Enter auf dem Foto öffnet die Großansicht. Nach Schließen einer per Tastatur geöffneten Großansicht kehrt der Fokus zurück und die Leiste ist sichtbar (Tastaturfokus bleibt Tastaturfokus).
- [ ] **AK8** **Geltungsbereich.** AK1–AK7 gelten für: Album-Entwurf, Endauswahl, Alternativen-Band, aufgeklappte Reihe, Hinzufügen-Bereich und Fotoübersicht (`PhotoGridTile`). Nachweis: alle nutzen `useRevealOnDemand`, keine Kachel setzt eine eigene Sichtbarkeitslogik.
- [ ] **AK9** **Spec 0579 AK14** lautet nach der Änderung sinngemäß „… solange ein Bedienelement darin den **Tastatur**fokus hat“; Fokus durch Tippen/Klick oder programmatische Rückgabe nach Zeigerinteraktion zeigt die Leiste nicht.

## Datenmodell-Bezug

Keiner — reine Frontend-Interaktion.

## Architektur / Umsetzung

### Ursache (im Code festgestellt)
Alle betroffenen Kacheln beziehen die Sichtbarkeit der Leiste aus **einem** Hook: `frontend/src/hooks/useRevealOnDemand.ts` (`visible = hovered || focused || pressed`). Die Handler hängen am `<li>` der Kachel (`{...handlers}` in `PhotoCard.tsx` bzw. `PhotoGridTile.tsx`). Zwei Fehler im Hook:

1. **`onFocus: () => setFocused(true)` reagiert auf jeden Fokus**, nicht nur auf Tastaturfokus. Ein Tippen auf den Bild-Knopf (`imageTriggerRef`) bzw. den Link der Rasterkachel fokussiert das Element → Leiste erscheint zusammen mit der Großansicht. Nach dem Schließen gibt die Großansicht den Fokus programmatisch an `imageTriggerRef` zurück → Leiste erscheint erneut (AK1). Dasselbe beim Tippen auf `TileAction`-Knöpfe (AK4).
2. **Hover vs. langer Druck hängt am Gerät**, nicht an der Eingabe: `hoverCapable` wird einmalig per `matchMedia('(hover: hover) and (pointer: fine)')` bestimmt. Ein Tablet mit Maus/Stift bekommt so keinen Hover, ein Touch-Laptop keinen langen Druck (verletzt AK5).

### Ansatz
Korrektur ausschließlich in `useRevealOnDemand`; alle Kacheln erben sie (AK8). Kein neuer Hook, kein CSS-Umbau – der Hook bleibt bei drei unabhängigen Auslösern (bestehendes, dokumentiertes Muster gegen das `pointerleave` des zerstörten Touch-Pointers).

- **Fokus nur bei Tastaturfokus:** `onFocus(event)` setzt `focused` nur, wenn `event.target` `:focus-visible` erfüllt (`(event.target as Element).matches(':focus-visible')`). Browser melden `:focus-visible` nach Tippen/Klick und bei programmatischer Fokus-Rückgabe nach einer Zeigerinteraktion nicht, nach Tab-Navigation schon. Damit: Tippen → kein Fokus-Auslöser; Fokus-Rückgabe aus der Großansicht nach Tippen → keine Leiste; Tab auf Bedienelement → Leiste (AK7, AK9). Fokus-Rückgabe selbst bleibt unverändert (Barrierefreiheit). `onBlur` bleibt `setFocused(false)`.
- **Eingabeart statt Gerät:** `matchMedia`/`HOVER_QUERY`/`hoverCapable` entfallen ersatzlos. Handler erhalten das `PointerEvent`:
  - `onPointerEnter(e)`: `hovered = true` nur bei `e.pointerType !== 'touch'` (Maus und Stift = Desktop-Verhalten, AK5/AK6).
  - `onPointerDown(e)`: Long-Press-Timer (`LONG_PRESS_MS = 500`) nur bei `e.pointerType === 'touch'`; sonst return.
  - `onPointerLeave`: unverändert (Timer abbrechen, `hovered = false`) – `hovered` wird von Touch nie gesetzt, das Touch-`pointerleave` nach `pointerup` nimmt `pressed` weiterhin nicht mit.
  - `onPointerEnter` ist damit immer definiert (Typ in `RevealOnDemand.handlers` anpassen: kein `| undefined` mehr; alle Handlertypen auf `(event: PointerEvent/FocusEvent) => void`).
- **Unverändert wiederverwendet:** `consumeSuppressedClick` (langer Druck öffnet nichts, AK2), das Schließen per `pointerdown` (capture) am Dokument und `scroll` (AK3), `onClickCapture` in `PhotoCard`/`PhotoGridTile`.

### Betroffene Dateien
- `frontend/src/hooks/useRevealOnDemand.ts` – einzige Produktivänderung (Fokus-Filter, pointerType-Weiche, `matchMedia` raus, Doku-Block anpassen: „solange ein Bedienelement darin den **Tastatur**fokus hat").
- `frontend/src/components/PhotoCard.tsx`, `frontend/src/components/PhotoGridTile.tsx` – nur falls die Handler-Typänderung es erfordert (Spread `{...handlers}` bleibt); Verbraucher von `PhotoCard`: `CurationPhotoTile.tsx`, `SelectionPhotoTile.tsx`, `DraftAlternativesBand.tsx` (inkl. aufgeklappte Reihe/Hinzufügen-Bereich) – keine Änderung erwartet.
- Tests: `hooks/useRevealOnDemand.test.tsx`, `components/PhotoCard.test.tsx`, `components/PhotoGridTile.test.tsx`, `components/CurationPhotoTile.test.tsx` – Druck-Helfer senden `PointerEvent` mit `pointerType: 'touch'` bzw. `'mouse'`/`'pen'` statt `matchMedia`-Stub. `pages/PhotoGridPage.test.tsx` stubbt `matchMedia` nur für diesen Hook → Stub entfernen. Hinweis: jsdom wertet `:focus-visible` nicht wie ein Browser aus; Tipp-/Fokus-Rückgabe-Fälle in Unit-Tests über einen gezielten `matches`-Stub abbilden, die echte Browser-Heuristik (Tippen, Rückgabe nach Schließen der Großansicht) gehört in einen E2E-Fall mit Touch-Emulation.
- Spec 0579 (AK14) textlich präzisieren: nur Tastaturfokus zeigt die Leiste (AK9).

### Reihenfolge
1. Hook-Tests auf pointerType und `:focus-visible` umstellen (rot) → Hook ändern. 2. Kachel-Tests (PhotoCard, PhotoGridTile, CurationPhotoTile) inkl. Fokus-Rückgabe nach Schließen der Großansicht. 3. `matchMedia`-Stubs entfernen. 4. E2E mit Touch-Emulation (Tippen auf Kachel der Kuratierung und der Fotoübersicht). 5. Spec 0579 AK14 nachziehen.

## UI/UX

Es gibt kein neues Layout, kein neues Token und keinen neuen Baustein. Aufbau, Fläche und Inhalt der Leiste bleiben so, wie Spec 0579 (Kuratierungskacheln) und Spec 0489 (Rasterkachel der Fotoübersicht) sie festlegen. Geändert wird nur, **wodurch die Leiste sichtbar wird**. Das gilt für alle Kacheln, die `useRevealOnDemand` nutzen: Album-Entwurf, Endauswahl, Alternativen-Band, aufgeklappte Reihe, Hinzufügen-Bereich und Fotoübersicht.

### Zustände je Eingabeart

Entscheidend ist die Eingabeart des einzelnen Ereignisses (`pointerType`), nicht der Gerätetyp. Maus und Stift verhalten sich wie am Desktop.

| Eingabe | Handlung | Leiste | Großansicht/Detailansicht bzw. Knopf |
|---|---|---|---|
| Touch | Tippen < 500 ms auf das Foto | nicht sichtbar, auch nicht nach dem Schließen der Großansicht (Fokus-Rückgabe ist kein Tastaturfokus) | öffnet |
| Touch | Druck ≥ 500 ms auf das Foto | sichtbar | öffnet **nicht** (Klick unterdrückt) |
| Touch | Leiste offen → Tippen anderswo oder Scrollen | schließt | – |
| Touch | Tippen auf einen Kachel-Knopf (Streichen, Alternativen, Tauschen, …) | nicht sichtbar | nur die Handlung des Knopfs |
| Maus/Stift | Überfahren der Kachel | sichtbar, solange der Zeiger auf der Kachel ist | – |
| Maus/Stift | Klick auf Foto bzw. Knopf | unverändert durch Hover bestimmt; der Klick-Fokus blendet nichts **zusätzlich** ein | öffnet bzw. löst aus |
| Maus/Stift | langer Druck | kein Sonderverhalten (kein Long-Press-Timer) | Klick wie gewohnt |
| Tastatur | Tab auf ein Bedienelement der Kachel (Bildauslöser, Knöpfe) | sichtbar, solange der Fokus in der Kachel ist | – |
| Tastatur | Enter auf dem Foto, dann Schließen der Großansicht | nach Rückkehr wieder sichtbar (der zurückgegebene Fokus ist nach Tastaturbedienung `:focus-visible`) | öffnet |

Alle übrigen Zustände bleiben wie in 0579/0489: Ruhezustand `sr-only` (Kuratierung) bzw. nicht im DOM (Raster), Laden, Bild lädt nicht, Leer, Fehler des Handgriffs. Die Leiste bekommt keine Ein- oder Ausblendanimation. Den Fokusring zeichnet weiterhin allein die globale `:focus-visible`-Regel.

**Sichtbare Rückmeldung beim Tippen:** Tippen zeigt keine Leiste mehr. Die Rückmeldung kommt aus dem Öffnen der Großansicht bzw. aus dem `active:`-Zustand des Knopfs. Diese Pflichtregel des Design-Systems („Gedrückt ist Pflicht“) ist unberührt.

**Bildschirmleser:** Unverändert. In der Kuratierung steht die Leiste immer im DOM (AK18 aus 0579). Ob sie sichtbar ist, ändert nichts an der Lesereihenfolge.

### Bezug zum Design-System

- Das Prinzip **„Touch- und Tastatur-gleichwertig“** bleibt gewahrt. Jede Angabe bleibt ohne Maus erreichbar: per Touch über langen Druck, per Tastatur über Tab.
- Die Regel **„Fokus: genau eine globale Regel“** passt dazu. Die Unterscheidung über `:focus-visible` ist dieselbe Heuristik, die schon den Fokusring und das Kurzwort im Symbolmodus des `TileAction` steuert (0579, Nebenbefund „beim Fokussieren gelesenes `:focus-visible`“). Leiste, Kurzwort und Fokusring folgen damit derselben Bedingung.
- Es gibt keine neuen Utilities, keine `focus-visible:`-Variante im TSX und keine Änderung an Farben, Abständen oder Trefferflächen. Für den statischen Vertragstest ist nichts nachzuziehen.

### Design-System-Doku: anzupassen (im Umsetzungs-PR)

`specs/architecture/0004-design-system.md`, zwei Fundstellen:
1. **Kuratierungskachel, Punkt „Leiste bei Bedarf“** (heute: „sichtbar bei Hover (feiner Zeiger), Fokus auf einem Bedienelement der Kachel oder nach ≥ 500 ms Druck“). Neu: „sichtbar beim Überfahren mit Maus oder Stift, bei **Tastatur**fokus (`:focus-visible`) auf einem Bedienelement der Kachel oder nach ≥ 500 ms Fingerdruck. Entscheidend ist die Eingabeart des Ereignisses (`pointerType`), nicht das Gerät. Ein kurzes Tippen zeigt die Leiste nie, auch nicht über die Fokus-Rückgabe beim Schließen der Großansicht.“
2. **Rasterkachel (`PhotoGridTile`), Punkt „Die Angaben erscheinen erst auf Anforderung“** (heute: „Überfahren an einem Gerät mit `(hover: hover) and (pointer: fine)`, durch Fokus, sonst …“). Hier dieselbe Formulierung wie unter 1, ohne Gerätebedingung.

Dazu kommt ein Eintrag in die Änderungshistorie mit Verweis auf Spec 0585.

`.claude/skills/design-system/SKILL.md`, Eintrag **Kuratierungskachel**: einen Halbsatz zu den Auslösern ergänzen („Leiste per Hover (Maus/Stift), Tastaturfokus oder ≥ 500 ms Fingerdruck, nie per kurzem Tippen“). Heute nennt der Skill die Auslöser gar nicht. Ohne diese Ergänzung könnte jemand die Leiste nachbauen und dabei wieder auf `onFocus` reagieren lassen.

Nicht betroffen und bewusst unverändert: Der Info-Popover der Schrittleiste (`StepMarker`) und der Rückgängig-Hinweis nutzen weiterhin `(hover: hover) and (pointer: fine)` bzw. „Zeiger darüber (nur feiner Zeiger)“. Sie liegen außerhalb dieser Story.

### Spec-Präzisierungen

- **0579 AK14:** Aus „bei Fokus auf **jedem** Bedienelement der Kachel“ wird „bei **Tastatur**fokus (`:focus-visible`) auf jedem Bedienelement der Kachel“. Die Gerätebedingung beim Überfahren lautet künftig „mit Maus oder Stift“. Abschnitt „Bei-Bedarf-Leiste → Auslöser“ und Tastaturabschnitt („Jeder Fokus in der Kachel blendet …“) entsprechend nachziehen.
- **0489 AK8 und Abschnitt „Kurzer Klick/Tipp / Überfahren oder Fokus“:** Die Gerätebedingung `(hover: hover) and (pointer: fine)` wird zu „Eingabe mit Maus oder Stift“, und „Fokus“ wird zu „Tastaturfokus“. Die Architektur nennt bisher nur 0579. Ich empfehle, 0489 im selben PR mitzuziehen, weil dieselbe Formulierung dort sonst veraltet stehen bleibt.

### Randfälle (für Test-/Sichtprüfung)

- **Stift ohne Schwebeerkennung:** `pointerenter` kommt erst beim Aufsetzen. Beim Tippen mit dem Stift kann die Leiste deshalb kurz zusammen mit der Großansicht erscheinen. Das folgt aus der Story-Festlegung „Stift = Desktop“ und ist hingenommen, kein Fehler.
- **Gerät mit Touch und Maus:** Dieselbe Kachel reagiert auf Fingertipp mit Touch-Verhalten und auf Mausbewegung mit Hover. Zwischen beiden Eingabearten zu wechseln braucht keinen Neuladevorgang.
- **Fokus-Rückgabe nach dem Schließen:** Wurde mit Tippen geöffnet, erscheint keine Leiste. Wurde mit Enter geöffnet, erscheint sie. Das zeigt sich verlässlich nur im echten Browser: Ein E2E-Test mit Touch-Emulation ist nötig, jsdom reicht nicht.

## Security

nicht relevant — reine clientseitige Gestenauswertung ohne neue Eingabe von außen, ohne Auth-, Secret-, Datenmodell- oder Sichtbarkeitsbezug.

## Teststrategie

Leitsatz unverändert: jede Zusage auf der niedrigsten Ebene, die sie widerlegen kann; E2E nur für die echte Browser-Heuristik von `:focus-visible` und echte Touch-Ereignisfolgen.

| AK | Ebene | Kern |
|---|---|---|
| 1 | Hook-Unit + `PhotoCard`/`PhotoGridTile`/`CurationPhotoTile` (jsdom, mit `:focus-visible`-Stub) **+ E2E** | Fokus ohne Tastaturfokus → unsichtbar; Fokus-Rückgabe nach Schließen → unsichtbar |
| 2 | Hook-Unit (Fake-Timer 499/500 ms, Klickunterdrückung) + bestehender E2E-Fall | |
| 3 | Hook-Unit (Dokument-`pointerdown` außerhalb, `scroll`) | unverändert, Regression |
| 4 | `PhotoCard`/`CurationPhotoTile`-Test: `onStrike`/Alternativen-Callback genau 1×, Leiste unsichtbar | |
| 5 | Hook-Unit, parametrisiert über `pointerType ∈ {touch, mouse, pen}`; Zusicherung `matchMedia` nicht aufgerufen (`vi.fn` als Global, `not.toHaveBeenCalled`) | |
| 6 | Hook-Unit: `pointerenter` mouse/pen → sichtbar, `pointerleave` → unsichtbar; mouse/pen-Druck 700 ms → kein Reveal, Klick nicht unterdrückt | |
| 7 | Hook-Unit + `PhotoCard`-Test (`userEvent.tab()`, Stub `:focus-visible`=true); Fokus-Rückgabe-Fall mit Tastatur-Öffnung | |
| 8 | je ein Kacheltest pro Komponente (`PhotoCard`, `PhotoGridTile`, `CurationPhotoTile`/`SelectionPhotoTile`/`DraftAlternativesBand` nur Verdrahtung: `{...handlers}` am `<li>`); kein Durchtesten aller Ansichten | |
| 9 | Doku-Änderung, kein Test | |

### `:focus-visible` in jsdom vs. E2E
- **Empirisch geprüft (jsdom dieses Repos, 2026-10-07):** nach `el.focus()` liefert `el.matches(':focus-visible')` **`true`** — jsdom hat keine Zeiger-Heuristik, jeder Fokus gilt als sichtbar. Folge: ohne Stub bestünde der Tastaturfall (AK7) trivial, und der Tipp-Fall (AK1/AK4) wäre **nicht** darstellbar; ein ungestubbter Test „Tippen → keine Leiste“ wäre rot gegen die korrekte Umsetzung bzw. würde zum Entfernen des Filters verleiten.
- **Unit-Muster:** gezielter Stub nur für diesen Selektor, z. B. `vi.spyOn(Element.prototype, 'matches').mockImplementation(function (sel) { return sel === ':focus-visible' ? focusVisible : original.call(this, sel) })`, in `afterEach` zurückgesetzt. **Partition Pflicht:** derselbe Fokusvorgang einmal mit `false` (→ unsichtbar) und einmal mit `true` (→ sichtbar) — nur so ist „Filter wirkt“ von „Fokus wird ignoriert“ unterscheidbar (Gegenprobe: `onFocus` ganz entfernen muss den `true`-Fall rot machen).
- **E2E (echte Heuristik):** in `e2e/tests/foto-karte-raster.spec.ts`, bestehende Gruppe „Telefon (Touch, ohne Hover)“ (`hasTouch`, `isMobile`). Kurzes Tippen **mit `locator.tap()`**, nicht mit `dispatchEvent('pointerdown'…)` — synthetisch verschickte Ereignisse fokussieren nicht und hätten den Fehler nie gezeigt (genau deshalb ist der bestehende „kurzer Druck“-Abschnitt dort grün geblieben). Fälle: (i) Album-Entwurf: `tap()` aufs Foto → Dialog offen, Leiste nicht `data-visible`; schließen → Vorbedingung `expect(trigger).toBeFocused()` (schließt den trivialen Grün-Fall aus) und Leiste weiterhin nicht sichtbar. (ii) Fotoübersicht: `tap()` auf Rasterkachel, dort analog (Navigation/Großansicht statt Dialog gemäß Bestandsverhalten). (iii) `tap()` auf Streichen-Knopf → Handlung erfolgt, Leiste nicht sichtbar, Knopf fokussiert. Langer Druck bleibt beim bestehenden `dispatchEvent`-Fall (Playwright kennt kein Halten bei `tap()`). Tastaturfall bleibt bei jsdom (keine Doppelung).
- **Rot-Nachweis im PR:** E2E-Fall (i) einmal gegen den unveränderten Hook laufen lassen (muss rot sein) und belegen.

### Edge Cases
- Tippen auf Foto, Großansicht schließen, danach **Tab** → Leiste sichtbar (Heuristik wechselt korrekt auf Tastatur).
- Maus-Hover aktiv und Tastaturfokus: Hover endet → bleibt sichtbar (bestehender Überlappungstest, auf pointerType umgestellt); umgekehrt Blur bei Hover → bleibt sichtbar.
- Touch-`pointerenter` (feuert vor `pointerdown`) setzt nie `hovered` — sonst bliebe die Leiste nach dem Tippen hängen, weil Touch-`pointerleave` erst nach `pointerup` kommt.
- Touch-Druck < 500 ms, dann Klick → Großansicht öffnet (Klick nicht fälschlich unterdrückt).
- Wechsel der Eingabeart in derselben Sitzung: erst Touch-Tipp, dann Maus-Hover → Hover-Reveal funktioniert (kein gemerkter Gerätezustand).
- `pointerdown` mit `pointerType: 'pen'` ≥ 500 ms → kein Reveal.
- Testhelfer: `fireEvent.pointerDown(el, { pointerType })` — prüfen, dass jsdom `pointerType` bis in den React-Handler transportiert (jsdom 29 hat `PointerEvent`; im Rot-Schritt einmal verifizieren, sonst Helfer mit `new PointerEvent(...)`).
- `PhotoGridPage.test.tsx`: `matchMedia`-Stub entfernen; die Seite muss danach ohne Stub rendern (belegt AK5 auf Seitenebene mit).

### Testkonzept-Ergänzung
Ergänzung nötig (kurz, in der 0579-/Reveal-Sektion bzw. als eigener Nachtrag): (1) **jsdom-Fallstrick `:focus-visible`**: `matches(':focus-visible')` ist in jsdom nach jedem Fokus `true`; Muster gezielter Selektor-Stub + Partition. (2) **E2E-Regel für Touch-Fokus:** Zusagen, die an Fokus nach Tippen hängen, nur mit `locator.tap()` unter `hasTouch` prüfen, nie mit synthetischem `dispatchEvent` — letzteres fokussiert nicht. (3) Der bisherige Eintrag zum `matchMedia`-Stub (Abschnitt ~Zeile 1259) bleibt für Popover gültig, gilt aber nicht mehr für `useRevealOnDemand`; dort vermerken.

## Entscheidungen

- Ursache und Ansatz: Korrektur allein in `useRevealOnDemand` (Tastaturfokus via `:focus-visible`, `pointerType` statt `matchMedia`); keine ADR, da keine neue Technologie/Abhängigkeit.
- Stift (`pen`) verhält sich wie Maus (folgt aus AK5); ein Stift ohne Schwebeerkennung kann beim Tippen die Leiste kurz zeigen — hingenommen.
- Spec 0489 (AK8, Abschnitt Klick/Tipp/Überfahren) wird im selben PR mit präzisiert, nicht nur 0579 AK14.
- Design-System-Doku (`specs/architecture/0004-design-system.md`) und Skill `design-system` werden im Umsetzungs-PR nachgezogen; Popover der Schrittleiste und Rückgängig-Hinweis bleiben bei `(hover: hover) and (pointer: fine)`.
- E2E nur für Album-Entwurf und Fotoübersicht mit `locator.tap()`; AK8 sonst über gemeinsamen Hook und Verdrahtungstests je Komponente belegt.
- security-engineer nicht konsultiert (Schritt 3): kein konkret benennbarer Bezug zu Auth, externen Schnittstellen, Secrets, Eingaben von außen, Berechtigungen, Datenmodell oder Datensichtbarkeit — die Änderung betrifft ausschließlich, welches lokale Zeigerereignis eine bereits gerenderte Leiste einblendet.

## Offene Fragen

Keine.

## Out of Scope

- Info-Popover der Schrittleiste (`StepMarker`) und Rückgängig-Hinweis.
- Gestalt, Inhalt oder Animation der Leiste.
