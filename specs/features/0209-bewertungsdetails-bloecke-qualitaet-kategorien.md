# 0209 - Bewertungsdetails: Blöcke Qualität und Kategorien

**Status:** Accepted
**Erstellt:** 2026-08-30
**Bezug:** [GitHub-Issue #209](https://github.com/TheRealKoller/photosort/issues/209) (Refinement bereits vor dieser Spec-Erstellung abgeschlossen)

## Ziel

Die Foto-Detailansicht (permanente Sektion) und das Info-Popover in Grid-/Kuratierungsansicht zeigen aktuell alle Bewertungskriterien eines Fotos als eine einzige undifferenzierte Liste, gefolgt von einem unbeschrifteten Bereich mit den erkannten Kategorie-Kandidaten. Dabei ist nicht auf einen Blick erkennbar, welche Werte die technische Bildqualität betreffen und welche zur Kategorie-Erkennung beitragen. Ziel ist, die Bewertungsdetails in zwei klar beschriftete, fachlich sinnvolle Blöcke zu gliedern — "Qualität" und "Kategorien" — damit die Darstellung auf einen Blick verständlich ist.

## User Story

Als Nutzer der PhotoSort-Installation möchte ich die Bewertungsdetails eines Fotos in zwei klar beschrifteten Blöcken "Qualität" und "Kategorien" sehen, damit ich auf einen Blick unterscheiden kann, welche Werte die technische Bildqualität betreffen und welche zur Kategorie-Erkennung beitragen, statt eine undifferenzierte Liste durchgehen zu müssen.

## Akzeptanzkriterien

- [ ] Die Bewertungsdetails eines Fotos sind sowohl in der permanenten Sektion der Foto-Detailansicht als auch im Info-Popover (Grid-/Kuratierungsansicht) in zwei beschriftete Blöcke gegliedert: "Qualität" und "Kategorien". Die Beschriftungen stehen als `<h3>` mit exakt dem Text "Qualität" bzw. "Kategorien" im DOM und sind über `useId()` + `aria-labelledby` programmatisch mit ihrem Block verknüpft (siehe Architektur-Entscheidung 3 zur wirksamen Platzierung).
- [ ] Block "Qualität" enthält die rein qualitätsbezogenen Merkmale: Schärfe, Belichtung, Goldener Schnitt, Ästhetik, Symmetrie, Horizont-Neigung, Freiraum/Fluchtrichtung.
- [ ] Block "Kategorien" enthält die kategorie-relevanten Merkmale (Menschen erkannt, Landschaft/Flächig, Tier erkannt, Gebäude erkannt, Sehenswürdigkeit) sowie den bereits bestehenden Bereich mit erkannten Kategorie-Kandidaten und Rang.
- [ ] Die Zuordnung eines Merkmals zu einem Block folgt **ausschließlich** dem `category_eligible`-Flag der API-Antwort — es gibt keine im Frontend hartkodierte Merkmalsliste; die in den beiden vorigen Kriterien genannten Merkmale sind der Registry-Stand zum Umsetzungszeitpunkt.
- [ ] Jedes gelieferte Kriterium erscheint in genau einem Block; keines geht verloren oder erscheint doppelt. Die Reihenfolge innerhalb eines Blocks entspricht der von der API gelieferten Reihenfolge.
- [ ] Alle bisherigen Interaktionsmöglichkeiten (z.B. eine Kategorie manuell übernehmen/zurücksetzen) bleiben unverändert erhalten — reine Umgruppierung/Beschriftung, keine funktionale Änderung. Konkret: die bestehenden Interaktionstests (Übernehmen-Callback, Reset-Callback, "Aktuell"-Chip, Orphan-Override-Zeile, selektiv deaktivierter pending-Button) bleiben inhaltlich unverändert gültig; die einzige zulässige Änderung an ihnen ist das neue Pflichtfeld in den Fixture-Factories. Kandidatenliste und "Rang" stehen dabei innerhalb des Kategorien-Blocks.
- [ ] Ist einer der beiden Blöcke ohne Inhalt (z.B. keine Kategorie-Kandidaten und kein Ranking vorhanden), wird kein leerer Block angezeigt — weder die `<h3>` noch ein leeres `<dl>`. Bei komplett leerer Eingabe (keine Kriterien, kein Ranking, kein Ausschuss-Vorschlag) rendert die Komponente keine Überschrift und kein `dt`/`dd`.
- [ ] Der separate "Ausschuss-Vorschlag"-Bereich (nur im Popover in Grid/Kuratierung sichtbar) bleibt unverändert ein eigener, dritter Bereich außerhalb der beiden neuen Blöcke, ohne eigene `<h3>`-Überschrift, und erscheint auch dann, wenn beide Blöcke leer sind.
- [ ] Ein `criterion_key`, der nicht (mehr) in der Registry steht (`category_eligible`-Fallback `false`), wird weiterhin angezeigt und erscheint im Block "Qualität".

## Datenmodell-Bezug

Unverändert — keine neue oder geänderte Entität, keine Alembic-Migration. Das neue Antwortfeld `CriterionScoreOut.category_eligible` wird zur Anfragezeit aus der statischen Kriterien-Registry abgeleitet und nicht persistiert. `docs/architecture.md` bleibt damit unverändert.

## Architektur / Umsetzung

### Ausgangslage

Beide betroffenen Stellen teilen sich bereits eine gemeinsame Präsentationskomponente (`frontend/src/components/CriterionDetailsList.tsx`, extrahiert mit Spec 0041): das Info-Popover (`CriterionDetailsPopover.tsx`, eingebunden in `PhotoGridPage.tsx` und `CurateCategoriesPage.tsx`) und die permanente Sektion in `PhotoDetailPage.tsx` rendern beide dieselbe Komponente. Es gibt keinen zweiten, duplizierten Renderpfad. Die Umgruppierung wird deshalb an genau einer Stelle umgesetzt und wirkt automatisch in beiden Ansichten (Akzeptanzkriterium 1) — es ist ausdrücklich **nicht** vorgesehen, dafür eine zusätzliche Komponente oder eine Varianten-Prop einzuführen.

Heute rendert die Komponente ein einziges `<dl>` mit drei ungruppierten Blöcken: alle `criterion_scores` in Registry-Reihenfolge, danach (nur bei `ranking !== null`) die Kategorie-Kandidaten bzw. die einzeilige "Kategorie"-Anzeige plus "Rang", und ganz unten — nur bei `showSuggestion` — der Ausschuss-Vorschlag.

### Entscheidung 1: Die Block-Zuordnung kommt aus der Backend-Registry, nicht aus einer Frontend-Liste

Die Zuordnung "Merkmal → Qualität/Kategorien" wird **nicht** als Key-Liste im Frontend gepflegt, sondern aus dem bereits existierenden Registry-Attribut `CriterionDefinition.category_eligible` (`backend/src/photosort/criteria.py`, eingeführt mit ADR 0023) abgeleitet und additiv über die API exponiert:

- `CriterionScoreOut` (`backend/src/photosort/api/photos.py`) bekommt ein zusätzliches Feld `category_eligible: bool`, befüllt in `_criterion_scores_out` analog zum bestehenden `display_name` aus `CRITERIA_REGISTRY`.
- Verbindliche Zuordnungsregel: `category_eligible == true` → Block **"Kategorien"**, `category_eligible == false` → Block **"Qualität"**.

Begründung: Die in der Story geforderte Aufteilung ist mit dem bestehenden `category_eligible`-Flag über alle zwölf Registry-Kriterien hinweg deckungsgleich (Qualität: `sharpness`, `exposure`, `goldener_schnitt`, `aesthetics`, `symmetrie`, `horizont`, `freiraum`; Kategorien: `content_people`, `content_landscape`, `tier`, `gebaeude`, `landmark`). Eine parallele Key-Liste im Frontend wäre eine zweite Wahrheit über dieselbe Sachfrage und würde spätestens beim nächsten neuen Kriterium auseinanderlaufen. Mit dem Registry-Flag landet ein künftiges Kriterium ohne Frontend-Änderung automatisch im fachlich richtigen Block. Der Preis (die UI-Gruppierung folgt der Kategorie-Fähigkeit) ist hier kein Kompromiss, sondern genau die fachliche Aussage der beiden Blöcke: "trägt zur Kategorie-Erkennung bei" vs. "betrifft die technische Bildqualität".

Bewusst **nicht** gewählt: ein eigenes, von `category_eligible` unabhängiges Anzeige-Feld (`group: "quality" | "category"`). Das wäre ein zweites, redundant zu pflegendes Registry-Attribut mit identischem Wert und würde denselben Drift-Fall nur ins Backend verlagern.

Registry-Drift-Fall (ein `criterion_key` in der DB, der nicht in `CRITERIA_REGISTRY` steht): fällt auf `category_eligible = false` zurück und landet damit im Qualitäts-Block — gleiche defensive Linie wie der bestehende `display_name`-Fallback auf den rohen Key und identisch zum Registry-Default des Attributs.

### Entscheidung 2: Additive API-Änderung, kein neuer Endpunkt, keine Migration

`category_eligible` wird zur Anfragezeit aus der Registry abgeleitet, nicht persistiert — es gibt keine neue Spalte, keine Alembic-Migration und keinen neuen Endpunkt. Das Feld ist rein additiv; bestehende Konsumenten bleiben unberührt. Im Frontend wird `CriterionScoreOut` in `frontend/src/api/types.ts` um dasselbe Pflichtfeld erweitert (bewusst nicht optional, damit `tsc` alle Test-Fixtures erzwingt statt stillschweigend `undefined` durchzureichen).

### Entscheidung 3: DOM-Struktur — pro Block ein beschrifteter Wrapper mit eigenem `<dl>`

Eine Block-Überschrift darf nicht direktes Kind eines `<dl>` sein (HTML erlaubt dort nur `<div>`/`<dt>`/`<dd>`). Die Komponente wird deshalb von einem einzelnen `<dl>` auf einen `<div>`-Container umgestellt, der pro Block einen Wrapper mit einem Überschriftselement und einem eigenen, in sich vollständigen `<dl>` enthält.

Die Beschriftung wird über `useId()` + `aria-labelledby` mit dem Block verknüpft, damit die Gruppierung nicht nur visuell, sondern auch für Screenreader trägt (zwei Instanzen der Komponente gleichzeitig im DOM bleiben dadurch kollisionsfrei). `aria-labelledby` gehört dabei **an den Block-Wrapper-`<div>` mit `role="group"`**, nicht an das `<dl>`: ein `<dl>` hat in dieser Toolchain keine namensfähige, abfragbare Rolle — die Beschriftung käme dort weder im Accessibility-Tree noch in einer Rollenabfrage an (empirisch in vitest/jsdom verifiziert, siehe Teststrategie und `specs/architecture/0002-testkonzept.md`).

Der Ausschuss-Vorschlag-Bereich bleibt ein dritter, eigener `<dl>`-Block **außerhalb** der beiden neuen Blöcke und **ohne** eigene neue Überschrift — visuell und inhaltlich unverändert (Akzeptanzkriterium 8). Die bestehende `showSuggestion`-Prop und ihre Semantik bleiben unangetastet.

Die Reihenfolge der Kriterien innerhalb eines Blocks bleibt die vom Backend gelieferte Registry-Reihenfolge — die Aufteilung erfolgt über einen ordnungserhaltenden Filter, es wird nirgends neu sortiert.

### Sichtbarkeitsregeln der Blöcke

- Block **"Qualität"**: nur wenn mindestens ein Kriterium mit `category_eligible === false` vorliegt.
- Block **"Kategorien"**: nur wenn mindestens ein Kriterium mit `category_eligible === true` vorliegt **oder** `ranking !== null` (Kandidatenliste bzw. einzeilige "Kategorie"-Anzeige und "Rang" gehören in diesen Block).
- Die bestehenden übergeordneten Sichtbarkeits-Gates bleiben unverändert: das Popover rendert weiterhin gar nichts bei leerer `criterionScores`-Liste, `PhotoDetailPage.tsx` bindet die permanente Sektion weiterhin nur bei `criterion_scores.length > 0` ein. Kein leerer Block, keine leere Überschrift.
- Der bisher dokumentierte Sonderfall "rendert bei komplett leerer Eingabe ein leeres `<dl>`" entfällt (Doc-Kommentar in `CriterionDetailsList.tsx` entsprechend mitziehen).

### Keine funktionale Änderung, keine neuen Props

Alle Interaktionen (Kandidat "Übernehmen"/"Zurücksetzen", `pendingOverrideKey`, `resetPending`, Badges "Aktuell"/"Manuell übernommen", die Prozent-Formatierung, die Orphan-Override-Zeile) wandern unverändert in den Kategorien-Block (Akzeptanzkriterium 6). Die Props-Signaturen von `CriterionDetailsList` und `CriterionDetailsPopover` ändern sich **nicht** — die Gruppierung ergibt sich vollständig aus den gelieferten Daten. Damit bleiben auch `PhotoGridPage.tsx` und `CurateCategoriesPage.tsx` unverändert (außer ihren Test-Fixtures).

### Betroffene Dateien

- `backend/src/photosort/api/photos.py` — `CriterionScoreOut` um `category_eligible` erweitert, `_criterion_scores_out` befüllt es aus `CRITERIA_REGISTRY`.
- `frontend/src/api/types.ts` — `CriterionScoreOut` um `category_eligible: boolean`.
- `frontend/src/components/CriterionDetailsList.tsx` — Umstrukturierung in zwei beschriftete Blöcke plus unveränderten dritten Ausschuss-Bereich.
- Tests: `backend/tests/test_api_photos.py`, `frontend/src/components/CriterionDetailsList.test.tsx`, `frontend/src/components/CriterionDetailsPopover.test.tsx`, `frontend/src/pages/PhotoDetailPage.test.tsx`, `frontend/src/pages/PhotoGridPage.test.tsx`, `frontend/src/pages/CurateCategoriesPage.test.tsx` (die letzten beiden nur Fixture-Anpassung).

### ADR-Bewertung

Es wird **keine** neue ADR angelegt. Die Änderung führt weder eine neue Technologie noch eine neue externe Abhängigkeit ein und ändert die Datenmodell-Grundstruktur nicht (kein persistiertes Feld, keine Migration). Die einzige nicht-triviale Entscheidung — die Block-Zuordnung an das bestehende `category_eligible`-Attribut zu binden statt eine zweite Liste zu pflegen — ist eine Anwendung der mit ADR 0023 bereits getroffenen Entscheidung ("Kategorie-Fähigkeit ist ein reines Registry-Attribut"), keine neue Richtungsentscheidung. Aus demselben Grund ist keine Aktualisierung von `docs/architecture.md` erforderlich.

## UI/UX

Das Feature hat eine sichtbare Oberfläche an zwei Stellen (Info-Popover in Grid-/Kuratierungsansicht, permanente Sektion in `PhotoDetailPage.tsx`), die beide dieselbe Komponente rendern. Es ist eine reine Neugruppierung ohne neue Interaktionsmuster.

**Layout:** Die bisherige flache `<dl>`-Liste wird durch einen äußeren `<div>`-Container mit Spalten-Flexbox ersetzt. Reihenfolge von oben nach unten: Qualität-Block → Kategorien-Block → Ausschuss-Vorschlag (letzterer ohne eigene Überschrift).

**Überschriften:** `<h3>` mit `text-xs font-medium text-text-h`. Die Popover-Kopfzeile "Bewertungsdetails" ist `text-sm font-semibold text-text-h`; die Block-Überschriften ordnen sich ihr über eine volle Größenstufe kleiner (`text-xs`) und geringeres Gewicht (`font-medium`) klar unter. Dieselbe Ausprägung funktioniert unverändert in der permanenten Sektion auf `PhotoDetailPage`, wo diese Kopfzeile fehlt.

**Abstände:** äußerer Container `flex flex-col gap-4` (deutlicher Schnitt zwischen den drei Bereichen), innerhalb eines Blocks (Überschrift + `<dl>`) `flex flex-col gap-1.5` analog zum bestehenden Abstand zwischen `dt`/`dd`-Paaren.

**Enge Breiten:** keine zusätzliche Responsive-Logik nötig — die Überschriften sind einfache Textzeilen, und die bestehenden `dt`/`dd`-Paare (`flex items-baseline justify-between gap-3`) wrappen bereits auf Popover-Breite.

**Zustände:** nur Qualität-Block / nur Kategorien-Block / beide / keiner (dann rendert die Komponente nichts außer einem ggf. vorhandenen Ausschuss-Vorschlag).

**Design-System:** keine Ergänzung von `specs/architecture/0004-design-system.md` nötig — Typografie (`text-xs`, `font-medium`, `text-text-h`) und Spacing (`gap-4`, `gap-1.5`) stammen vollständig aus der bestehenden Skala, es kommen keine neuen Komponentenklassen, Icons oder Farbvarianten hinzu.

## Teststrategie

`specs/architecture/0002-testkonzept.md` wurde um eine neue Frontend-Sektion ergänzt ("Beschriftete Teilblöcke mit generierter ID (`useId`) …") — erste `useId()`-Verwendung im Projekt und ein neues, wiederverwendbares Prüfmuster. Kein E2E (Projektentscheidung); die rein visuelle Gruppierung bleibt manueller Smoke-Test vor dem Merge.

**Backend (Integration, `test_api_photos.py`):** Die beiden bestehenden Exakt-Dict-Assertions brechen durch das neue Feld — das ist der gewollte Rot-Schritt; beide um `category_eligible` erweitern, im Drift-Test (unbekannter Key) mit `False` als Fallback-Nachweis. Dazu **ein** Registry-weiter Test: für jeden `CRITERIA_REGISTRY`-Key eine `PhotoCriterionScore`-Zeile anlegen, ein Request, dann die ausgelieferte Key→Flag-Abbildung gegen die Registry vergleichen. Dieser Test trägt, weil `test_criteria.py::test_exactly_five_content_criteria_are_category_eligible` die Menge bereits mit Literalen festnagelt. Keine Parametrisierung pro Key. `_to_photo_out` ist der einzige Pfad für beide Endpunkt-Zweige, daher keine Zweig-Duplikate. Keine neue Logik ⇒ kein Effekt auf das Coverage-Gate.

**Frontend Unit (`CriterionDetailsList.test.tsx`, Schwerpunkt):** Die Blockbildung wird vollständig hier abgedeckt. Block-Zugehörigkeit immer positiv **und** negativ prüfen (`within(blockA).getByText` plus `within(blockB).queryByText → not.toBeInTheDocument`) sowie eine Partitions-Assertion (Vereinigung beider Blöcke == Eingabeliste). "Text existiert irgendwo im DOM" ist für ein Gliederungsfeature keine gültige Assertion. Generierte IDs nie als Wert asserten, sondern auflösen (`aria-labelledby` → `getElementById` → Textvergleich); dazu ein Kollisionstest mit zwei Instanzen im selben Render. Reihenfolge-Erhalt nur mit bewusst verschränkter Eingabe testen.

**Frontend Oberflächennachweis (je genau eine Assertion, keine Logik-Dopplung):** `CriterionDetailsPopover.test.tsx` (beide `<h3>` im geöffneten Popover) und `PhotoDetailPage.test.tsx` (beide `<h3>` in der permanenten Sektion) — damit ist Akzeptanzkriterium 1 an beiden geforderten Oberflächen belegt. `PhotoGridPage.test.tsx`/`CurateCategoriesPage.test.tsx` bekommen nur ein Fixture-Update, keinen neuen Test (sie mounten dasselbe Popover).

**Regressionsabsicherung für Akzeptanzkriterium 6:** Die Absicherung ist die Unveränderlichkeit der bestehenden Interaktionstests (`CriterionDetailsList.test.tsx`, `useCategoryOverrideControls.test.tsx`, Override-Tests der drei Seiten). Review-Regel für den Diff: in diesen Dateien darf nichts außer der `criterionScore()`-Factory angefasst werden. Ein zusätzlicher Test sichert die neue Verschachtelung: Kandidaten-Gruppe und "Rang" liegen innerhalb des Kategorien-Blocks, und "Übernehmen" funktioniert von dort aus unverändert.

**Edge Cases:** nur Qualitätskriterien ohne Ranking; nur kategoriefähige Kriterien; verschränkte Eingabereihenfolge; unbekannter `criterion_key` → Qualitäts-Block; leere Kriterienliste mit `ranking != null` (nur auf Komponentenebene erreichbar — bekannte, im Testkonzept vermerkte Lücke, da die Aufrufer-Gates zu ändern eine funktionale Änderung wäre); alles leer → keine Überschrift, kein `dt`/`dd`; nur Ausschuss-Vorschlag; `showSuggestion=false` mit vorhandener `suggestion` (bestehender Defensivtest bleibt gültig); zwei Instanzen im selben Render ohne ID-Kollision.

## Security

**Nicht sicherheitsrelevant.** Kein neuer Endpunkt, keine Änderung an Auth/Berechtigungen, keine neue Eingabe von außen, kein Secret-Bezug. Das additive `CriterionScoreOut.category_eligible` ist ein statisches Registry-Konfigurationsattribut (gleich für alle Fotos, Projekte und beide Nutzer, kein foto-/nutzerbezogenes Datum); sein Informationsgehalt ist über `category_candidates`/`ranking.category_key` am selben, bereits `get_current_user`-geschützten `GET /projects/{id}/photos` ohnehin ableitbar und steht im öffentlichen Repository ohnehin im Quelltext (`criteria.py`). Keine neue Sichtbarkeitsasymmetrie zwischen den beiden Nutzern. Der Frontend-Umbau bleibt innerhalb der bestehenden XSS-Konvention: nur React-Textknoten, kein `dangerouslySetInnerHTML`, die neuen Blocküberschriften sind statische Literale. `specs/architecture/0003-securitykonzept.md` muss nicht ergänzt werden.

## Entscheidungen

- **Block-Zuordnung aus dem Backend-Registry-Flag** `category_eligible` statt einer Frontend-Key-Liste (Architektur-Entscheidung 1) — verhindert das von der Story ausdrücklich ausgeschlossene Auseinanderlaufen von Backend und Frontend.
- **Additive API-Erweiterung ohne Persistenz** (Architektur-Entscheidung 2) — kein neues Feld in der DB, keine Migration, kein neuer Endpunkt.
- **`aria-labelledby` + `role="group"` am Block-Wrapper statt am `<dl>`** — der `architect` hatte die Verknüpfung ursprünglich am `<dl>` vorgesehen; der `test-engineer` hat empirisch nachgewiesen, dass ein `<dl>` in dieser Toolchain keine namensfähige Rolle hat und die Beschriftung dort weder wirksam noch prüfbar wäre. Die Verknüpfung wandert deshalb an den Wrapper, das visuelle Ergebnis bleibt identisch.
- **Verhalten bei komplett leerer Eingabe geändert:** statt eines leeren `<dl>` wird nichts gerendert — folgt direkt aus dem Akzeptanzkriterium "kein leerer Block"; der Doc-Kommentar in `CriterionDetailsList.tsx` wird mitgezogen.
- **Keine neue ADR** — die Entscheidung ist eine Anwendung von ADR 0023, keine neue Richtungsentscheidung.
- `architect` konsultiert (Schritt 1), `ux-ui-designer` konsultiert (Schritt 2), `test-engineer` und `security-engineer` konsultiert (Schritt 3) — keine Konsultation übersprungen.

## Offene Fragen

Keine.

## Out of Scope

- Änderungen an der Menge, Berechnung oder Benennung der Bewertungskriterien selbst.
- Änderungen an der Kategorie-Erkennung, am Ranking oder am Ausschuss-Vorschlag (inhaltlich wie visuell).
- Neue Interaktionen, Filter oder Klapp-/Aufklapp-Verhalten für die beiden Blöcke.
- Anpassung der Aufrufer-Gates in `CriterionDetailsPopover.tsx`/`PhotoDetailPage.tsx` (wäre eine funktionale Änderung).
