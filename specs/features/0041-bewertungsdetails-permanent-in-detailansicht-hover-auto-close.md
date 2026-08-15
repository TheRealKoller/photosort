# 0041 - Bewertungsdetails permanent in der Detailansicht + Hover-Auto-Close im Popover

**Status:** Accepted
**Erstellt:** 2026-08-15
**Bezug:** Inbox-Eintrag [`specs/inbox/0020-bewertungsdetails-immer-sichtbar-in-detailansicht.md`](../inbox/0020-bewertungsdetails-immer-sichtbar-in-detailansicht.md) (2026-08-15), idea-sharpener-Gespräch mit Daniel; erweitert Spec [0040](./0040-bewertungsdetails-info-popover.md).

## Ziel

Seit Spec [0040](./0040-bewertungsdetails-info-popover.md) zeigt PhotoSort die Bewertungsdetails (Einzelkriterien-Scores, Kategorie/Rang, Ausschuss-Grund) überall nur über ein Info-Icon mit On-Demand-Popover. In der Einzelbild-Detailansicht (`PhotoDetailPage.tsx`) ist der zusätzliche Klick unnötig — anders als im Grid oder in der Kuratierung, wo Platz knapp ist, steht dort ohnehin nur ein einziges Foto im Fokus. Diese Spec macht die Kriterien-Aufschlüsselung dort permanent sichtbar und entfernt das Icon an dieser einen Stelle; Grid und Kuratierung behalten Icon+Popover unverändert. Zusätzlich bekommt das verbleibende Popover ein natürlicheres Schließverhalten: wurde es per Hover geöffnet, schließt es automatisch, sobald die Maus es verlässt, statt nur über Klick/Escape/Außenklick.

## User Story

Als Nutzer (Daniel oder seine Frau) möchte ich in der Einzelbild-Detailansicht die Bewertungsdetails direkt unter dem Foto sehen, ohne extra auf ein Icon klicken zu müssen, und im Grid/der Kuratierung soll sich das Info-Popover von selbst schließen, wenn ich mit der Maus weggehe, damit die Bedienung an beiden Stellen natürlicher wirkt.

## Akzeptanzkriterien

**Permanente Sektion in der Detailansicht**
1. In `PhotoDetailPage.tsx` wird direkt unter dem Foto (vor den Vor-/Zurück-Navigationsbuttons) ein permanenter, eigener Abschnitt "Bewertungsdetails" gerendert, der Einzelkriterien-Scores sowie Kategorie/Rang zeigt — analog zu den bisherigen Popover-Inhalten, aber ohne die Ausschuss-Gruppe (die bleibt exklusiv im bestehenden "Automatischer Vorschlag"-Kasten weiter unten).
2. Der Abschnitt wird nur gerendert, wenn `criterionScores.length > 0` (gleiche Regel wie die bisherige Icon-Sichtbarkeit, Spec 0040 AK1) — bei leerer Liste erscheint kein leerer Bereich.
3. Das Info-Icon (`CriterionDetailsPopover`) entfällt in `PhotoDetailPage.tsx` vollständig — ersetzt durch die permanente Sektion.
4. In `PhotoGridPage.tsx` und `CurateCategoriesPage.tsx` bleibt das Info-Icon mit Popover unverändert bestehen (keine funktionale Änderung dort außer dem neuen Hover-Auto-Close unten).

**Geteilte Darstellung (DRY)**
5. Die bisher inline in `CriterionDetailsPopover.tsx` liegende `<dl>`-Darstellung wird in eine neue, wiederverwendbare Präsentationskomponente `CriterionDetailsList.tsx` extrahiert, mit einem zusätzlichen Prop `showSuggestion: boolean`. Das Popover nutzt sie weiterhin mit `showSuggestion={true}`, die neue permanente Sektion mit `showSuggestion={false}`.
6. `showSuggestion={false}` unterdrückt die Ausschuss-Gruppe auch dann, wenn eine nicht-`null` `suggestion` übergeben würde (defensiver Test gegen die Prop-Logik selbst) — `PhotoDetailPage.tsx` reicht `suggestion` an die neue Sektion ohnehin gar nicht erst durch.

**Hover-Auto-Close im verbleibenden Popover (Grid/Kuratierung)**
7. Wurde das Popover per Hover geöffnet (`openedByHoverRef.current === true`), schließt es automatisch, sobald die Maus sowohl den Trigger als auch den Popover-Content verlassen hat — geprüft über `event.relatedTarget` per `Node.contains()` gegen `triggerRef`/`contentRef`, kein Timer/Delay.
8. Der Grace-Bereich deckt Trigger UND Content gemeinsam ab: ein direkter Cursor-Wechsel zwischen Trigger und Content (in beide Richtungen) schließt das Popover NICHT.
9. Wurde das Popover per Klick/Tap geöffnet (`openedByHoverRef.current === false`), hat `mouseleave` auf Trigger oder Content keine Wirkung — es schließt weiterhin nur über die bestehenden Wege (erneuter Klick, Klick außerhalb, Escape, "×"-Button).
10. Verlässt die Maus Trigger oder Content zu einem dritten, unbeteiligten Element (oder `relatedTarget === null`, z.B. beim Verlassen des Fensters), schließt ein hover-geöffnetes Popover sofort.
11. Die bestehende Klick-Unterdrückungslogik (`justOpenedByHoverRef`, Spec 0040) bleibt unverändert und unabhängig vom neuen, über die gesamte Offen-Dauer persistenten `openedByHoverRef` — die neue Auto-Close-Logik greift auch nach einem per Klick unterdrückten ersten Schließversuch weiterhin.

**Barrierefreiheit / Konsistenz**
12. Die permanente Sektion in der Detailansicht nutzt dieselbe `<dl>/<dt>/<dd>`-Semantik wie das bisherige Popover (Spec 0040 AK16).
13. Prozent-Rundung, Kriterien-Reihenfolge und Best-effort-Verhalten bei fehlenden Kriterien (Spec 0040 AK7-9) bleiben unverändert — reine Wiederverwendung derselben Formatierungslogik über `CriterionDetailsList.tsx`.

## Datenmodell-Bezug

Keine neue Tabelle/Migration, keine neuen Backend-Felder — reine Frontend-Umstrukturierung bereits vorhandener, bereits exponierter Daten (`criterion_scores`, `ranking` aus Spec 0040). Siehe [`docs/architecture.md`](../../docs/architecture.md).

## Architektur / Umsetzung

**Frontend:**

- Neue Präsentationskomponente `frontend/src/components/CriterionDetailsList.tsx`: extrahiert die bisherige `<dl>`-Struktur aus `CriterionDetailsPopover.tsx` unverändert, Props `criterionScores: CriterionScoreOut[]`, `ranking: RankingOut | null`, `suggestion: SuggestionOut | null`, `showSuggestion: boolean`. `CriterionDetailsPopover.tsx` bindet sie innerhalb von `<PopoverContent>` mit `showSuggestion={true}` ein.
- `PhotoDetailPage.tsx`: Import und Einbindung von `CriterionDetailsPopover` entfallen. Direkt nach dem `<PhotoImage>`-Block, vor den Navigationsbuttons, kommt ein neuer, mit `criterionScores.length > 0` bedingter Abschnitt, der `CriterionDetailsList` mit `showSuggestion={false}` rendert. Die bestehende `suggestion`-Ableitung bleibt unverändert für den weiterhin eigenständigen "Automatischer Vorschlag"-Kasten (kein Feld-/Logik-Merge zwischen beiden Bereichen).
- `ui/popover.tsx::PopoverContent` bekommt Ref-Forwarding (React 19: `ref` als normale Prop, kein `forwardRef` nötig), damit `CriterionDetailsPopover.tsx` einen `contentRef` an den tatsächlichen DOM-Knoten binden kann.
- `CriterionDetailsPopover.tsx`: neuer, über die gesamte Offen-Dauer persistenter `openedByHoverRef` (zu unterscheiden vom bestehenden, nur für die Klick-Unterdrückung genutzten transienten `justOpenedByHoverRef`), neue `triggerRef`/`contentRef`. Neuer `handlePossibleHoverClose(event)`-Handler an `onMouseLeave` von Trigger-Button UND `PopoverContent`: prüft bei `openedByHoverRef.current === true` per `Node.contains()` gegen beide Refs, ob `event.relatedTarget` außerhalb beider liegt, und ruft in diesem Fall `setOpen(false)` auf. Ein `handleOpenChange`-Wrapper (ersetzt das bisherige direkte `onOpenChange={setOpen}`) setzt `openedByHoverRef.current` synchron zu `justOpenedByHoverRef` beim Öffnen und setzt ihn beim Schließen zurück. Grund für den Ref-basierten statt eines naiven Bubbling-Checks: `PopoverContent` liegt über `PopoverPrimitive.Portal` an einer anderen Stelle im DOM-Baum als der Trigger, ein einfacher `event.currentTarget.contains(event.relatedTarget)`-Check würde beim Übergang Trigger→Content fälschlich "verlassen" melden.
- `PhotoGridPage.tsx`/`CurateCategoriesPage.tsx`: keine Änderung — nutzen `CriterionDetailsPopover` unverändert weiter.

**Reihenfolge der Umsetzung:** `CriterionDetailsList.tsx` extrahieren (Tests zuerst, migriert aus `CriterionDetailsPopover.test.tsx`) → `ui/popover.tsx` Ref-Forwarding → `CriterionDetailsPopover.tsx` Hover-Auto-Close-Logik (Tests zuerst) → `PhotoDetailPage.tsx`-Umbau (Icon raus, permanente Sektion rein).

Kein neues ADR nötig — beide technischen Kernentscheidungen (Komponenten-Extraktion, Ref-basiertes Grace-Bereich-Pattern) sind Details innerhalb der bereits akzeptierten Architektur-Richtung aus Spec 0040/ADR [0011](../decisions/0011-ui-component-library.md).

## UI/UX

- **Platzierung:** die permanente Sektion sitzt direkt unter dem Foto, vor den Vor-/Zurück-Navigationsbuttons — als eigener, klar abgegrenzter Bereich, nicht in den bestehenden "Automatischer Vorschlag"-Kasten integriert (Klärung im Sharpening-Gespräch: "Zusätzlich, eigener Bereich").
- **Visuelle Zurückhaltung** (Designprinzip "Die Fotos sind der Star"): kein eigener Card-Rahmen mit Schatten wie das Popover — ein schlichter, dezenter Block (`text-sm text-text`), der sich optisch unterordnet und nicht mit dem Foto konkurriert. Gleiche `<dl>`-Struktur und Formatierung (Prozentwerte, Kategorie/Rang) wie im Popover, aber ohne Popover-typischen Header ("Bewertungsdetails"-Überschrift + "×"-Button) — die Sektion ist nicht schließbar, ein Schließen-Button wäre irreführend.
- **Icon-Entfall in der Detailansicht:** die bisherige Position oben rechts über dem Foto (`absolute right-2 top-2`) bleibt für Grid/Kuratierung unverändert; in der Detailansicht entfällt diese Ecke einfach, kein Ersatzelement nötig.
- **Hover-Auto-Close:** rein interaktive Änderung ohne eigene sichtbare Gestaltung — der Grace-Bereich ist für den Nutzer nicht separat markiert, wirkt sich nur auf das Schließverhalten aus.
- **Barrierefreiheit:** `<dl>/<dt>/<dd>`-Semantik wie bisher; die permanente Sektion ist als normaler Seiteninhalt fokus-/screenreader-zugänglich (kein Dialog-Pattern nötig, da nicht mehr on-demand).

## Security

Nicht sicherheitsrelevant (`security-engineer` nicht konsultiert, siehe Entscheidungen). Keine neuen Endpunkte, keine neue Auth-/Berechtigungslogik, keine neu exponierten Daten — dieselben bereits über `GET /projects/{project_id}/photos` verfügbaren, projektweiten (nicht nutzerspezifischen) Felder (`criterion_scores`, `ranking`) werden lediglich an einer zusätzlichen Stelle im Frontend gerendert statt hinter einem Klick versteckt.

## Offene Fragen

Keine — alle im Gespräch aufgekommenen Punkte wurden geklärt (siehe Entscheidungen).

## Entscheidungen (2026-08-15, im Idea-Sharpening-Gespräch mit Daniel geklärt)

- **Darstellung in der Detailansicht:** eigener, zusätzlicher Bereich unter dem Foto, nicht in den bestehenden "Automatischer Vorschlag"-Kasten integriert — Antwort auf Rückfrage im Sharpening-Gespräch.
- **Hover-Auto-Close nur bei Hover-geöffnet:** ein klick-/tap-geöffnetes Popover schließt NICHT automatisch bei `mouseleave` — nur ein per Hover geöffnetes. Antwort auf Rückfrage.
- **Grace-Bereich über Trigger UND Content:** das Popover bleibt offen, solange die Maus im Trigger ODER im Content ist — kein Schließen beim direkten Übergang zwischen beiden. Antwort auf Rückfrage.
- `test-engineer` konsultiert: hat `specs/architecture/0002-testkonzept.md` um zwei neue Punkte (7: Hover-Auto-Close mit Grace-Bereich über die Portal-Grenze hinweg; 8: Extraktion `CriterionDetailsList.tsx` inkl. Test-Migration) in der bestehenden Sektion "Radix Popover mit gerätespezifischem Hover-Verhalten" ergänzt.
- `security-engineer` nicht konsultiert (Schritt 8): reine Umplatzierung bereits sichtbarer, gleicher, projektweiter (nicht nutzerspezifischer) Daten aus einem On-Demand-Popover in eine permanente Sektion; keine neue Datenexposition, kein neuer Endpunkt, keine neue Auth-/Berechtigungslogik.
- **Priorität — Niedrig:** reine UX-Komfortverbesserung ohne aktive Nutzungseinschränkung (anders als z.B. Spec 0027/0030, dort jeweils "Hoch"), kein Konflikt mit bereits Geplantem — orthogonal zu Spec 0039 ("Mittel", Tages-/Cluster-Gruppierung im Kuratierungs-Grid), verdrängt nichts.

## Out of Scope

- Änderung der Icon-Sichtbarkeitsregel in Grid/Kuratierung (bleibt dort exakt wie in Spec 0040).
- Auto-Close für klick-/tap-geöffnete Popover (bleibt unverändert nur über die bestehenden Wege schließbar).
- Visuelle Neugestaltung des Popover-Inhalts selbst (Content/Styling unverändert, nur die zugrunde liegende `<dl>`-Struktur wandert in eine separate, wiederverwendbare Komponente).
