# 0040 - Berechnete Bewertungsdetails zu Fotos anzeigen (Info-Popover)

**Status:** Implemented ([PR #85](https://github.com/TheRealKoller/photosort/pull/85))
**Erstellt:** 2026-08-15
**Bezug:** Inbox-Eintrag [`specs/inbox/0010-berechnete-bewertungsdetails-anzeigen.md`](../inbox/0010-berechnete-bewertungsdetails-anzeigen.md) (2026-08-07, vor Spec 0037 erfasst), idea-sharpener-Gespräch mit Daniel

## Ziel

Seit Spec [0037](./0037-gateführte-bewertungs-pipeline-mit-backfill.md) berechnet PhotoSort für jedes Foto mehrere Einzelkriterien-Scores, eine abgeleitete Kategorie und eine Rangfolge innerhalb der Kategorie — sichtbar ist davon im UI heute aber nichts. Nutzer sehen nur das Endergebnis (Kategorie-Chip, Ausschuss-Vorschlag), nicht die Begründung dahinter. Diese Spec ergänzt ein Info-Icon an jedem bewerteten Foto, das auf Wunsch die vollständige Aufschlüsselung zeigt — sowohl für die vier heutigen Kriterien als auch automatisch für die vier zusätzlichen aus Spec [0038](./0038-vier-zusaetzliche-kriterien-tier-gebaeude-schnitt-aesthetik.md), sobald diese implementiert sind. Spec 0038 hat diese Notwendigkeit selbst bereits vorgesehen ("UI-Exponierung der neuen Kriterien … falls gewünscht, eigene Spec").

## User Story

Als Nutzer (Daniel oder seine Frau) möchte ich zu jedem bewerteten Foto über ein Info-Icon die detaillierten Bewertungskriterien einsehen können — Einzelkriterien-Scores, abgeleitete Kategorie, Rang innerhalb der Kategorie, ggf. Ausschuss-Grund — damit ich nachvollziehen kann, warum das System dieses Foto so eingestuft hat.

## Akzeptanzkriterien

**Icon-Sichtbarkeit**
1. Das Info-Icon wird nur gerendert, wenn `photo.criterion_scores.length > 0`; bei leerer Liste ist weder Icon noch Popover im DOM (kein Leer-Zustand-Popover).
2. Das Icon erscheint nach identischer Sichtbarkeitsregel in allen drei Ansichten: Foto-Grid (`PhotoGridPage.tsx`), Einzelbild (`PhotoDetailPage.tsx`), Kuratierung (`CurateCategoriesPage.tsx`).

**Interaktion — geräteunabhängig**
3. Klick/Tap auf das Icon öffnet das Popover in allen drei Ansichten, unabhängig vom Gerätetyp.
4. Erneuter Klick/Tap auf das Icon, Klick außerhalb, der "×"-Button im Popover-Header, oder Escape schließen das Popover.

**Interaktion — Desktop-Hover**
5. Bei `matchMedia('(hover: hover) and (pointer: fine)').matches === true` öffnet zusätzlich Hover über dem Trigger das Popover.
6. Bei `matches === false` (Touch/kein Fine-Pointer) hat Hover keine Wirkung — nur Klick/Tap öffnet.

**Generische Kriterien-Anzeige**
7. Alle in `criterion_scores` enthaltenen Einträge werden angezeigt, in `CRITERIA_REGISTRY`-Reihenfolge, unabhängig von ihrer Anzahl — künftige Kriterien aus Spec 0038 erscheinen automatisch, ohne Frontend-Codeänderung.
8. Fehlt ein Kriterium in `criterion_scores` (Best-effort-Lücke), wird es weder mit `0` noch mit einem Platzhalter aufgefüllt — es fehlt einfach in der Liste.
9. Jeder Kriterien-Wert wird als Prozentzahl ohne Nachkommastelle dargestellt (`value=0.734` → "73%", kaufmännisch gerundet) — vermeidet eine Scheingenauigkeit, die die zugrundeliegenden, teils heuristischen Scores nicht hergeben.

**Kategorie/Rang**
10. Ist `photo.ranking !== null`, zeigt das Popover Kategorie (`category_key`, ausgeschrieben über `formatCategoryKey`) und "Rang M von N" (`rank_position` von `partition_size`, beide aus der gleichen Cluster×Kategorie-Partition).
11. Ist `photo.ranking === null` (kein Scoring-Lauf mit diesem Foto, oder außerhalb des Kandidatenpools), entfällt die Kategorie/Rang-Gruppe vollständig — kein leerer Abschnitt.

**Ausschuss-Grund**
12. Ist `photo.suggestion !== null`, zeigt das Popover die Ausschuss-Begründung über `suggestionLabels.ts` (identische Formatierung wie der bestehende Ausschuss-Kasten in `PhotoDetailPage.tsx`).
13. Ist `photo.suggestion === null`, entfällt die Ausschuss-Gruppe vollständig — kein leerer Abschnitt.

**Barrierefreiheit**
14. Trigger hat `aria-label="Bewertungsdetails anzeigen"`, Touch-Ziel ≥44×44px.
15. Trigger ist per Tab erreichbar, Enter/Space öffnet, Escape schließt bei Fokus im Popover.
16. Popover-Content nutzt `<dl>/<dt>/<dd>` mit den drei Gruppen (Einzelkriterien / Kategorie+Rang / Ausschuss-Grund), über Radix als `dialog`-artige Region auffindbar.

**Grid-Struktur**
17. In `PhotoGridPage.tsx` liegt der Trigger als Geschwisterelement neben, nicht innerhalb, des `<Link>`-Kachel-Wrappers; ein Klick auf den Trigger navigiert nicht zur Detailseite.

## Datenmodell-Bezug

Keine neue Tabelle/Migration — `PhotoCriterionScore` und `PhotoRanking` existieren bereits seit Spec 0037/ADR [0021](../decisions/0021-kriterien-datenmodell-kuratierungs-pipeline.md). Erweiterung der API-Response um bisher nicht exponierte, bereits vorhandene Daten (siehe Architektur-Abschnitt). Siehe [`docs/architecture.md`](../../docs/architecture.md).

## Architektur / Umsetzung

**Backend (`backend/src/photosort/api/photos.py`):**

- Neues `CriterionScoreOut` (Pydantic): `criterion_key: str`, `display_name: str`, `value: float`, `source: CriterionSource`. Display-Name kommt aus `criteria.py::CRITERIA_REGISTRY` (Fallback auf `criterion_key`, falls ein DB-Wert nicht im Register steht — defensiv gegen Registry-/Daten-Drift).
- `PhotoOut` bekommt ein neues Pflichtfeld `criterion_scores: list[CriterionScoreOut]` (immer eine Liste, nie `None`, analog zu `ratings`). Best-effort: enthält nur Kriterien, für die tatsächlich eine `PhotoCriterionScore`-Zeile existiert. Sortiert nach `CRITERIA_REGISTRY`-Reihenfolge.
- Datenzugriff: `Photo.criterion_scores` ist bereits eine ORM-Relationship (`models.py:87`) — `_photos_by_id` bekommt zusätzlich `selectinload(Photo.criterion_scores)`, kein neuer Query pro Foto.
- `RankingOut` wird jetzt **auch im Standard-Listing-Zweig** von `list_photos` befüllt (bisher nur bei `top_n_per_category`): `_rankings_by_photo_id` wird zusätzlich im Default-Zweig aufgerufen. War laut ADR 0021 eine an den developer-Agenten delegierte technische Detailentscheidung — hier bewusst erweitert, da Grid-/Detailansicht jetzt ebenfalls Rang-Score/-Position zeigen sollen.
- `RankingOut` bekommt zusätzlich `partition_size: int` (Größe der Cluster×Kategorie-Partition, für "Rang M von N"). Berechnet über eine neue Helper-Funktion `_partition_sizes(session, criterion_scoring_run_id)`: ein `GROUP BY cluster_key, category_key`-Query über `PhotoRanking` pro `list_photos`-Aufruf (nicht pro Foto), Ergebnis-Dict per `(cluster_key, category_key)`-Lookup an jedes `RankingOut` durchgereicht. Bewusst **lauf-global, nicht nutzerspezifisch gefiltert** (nicht "N minus von diesem Nutzer abgelehnte Fotos") — `rank_position` verschiebt sich beim Ablehnen eines Fotos ebenfalls nicht (nur die sichtbare Top-N-Backfill-Query wechselt), beide Felder bleiben also konsistent auf derselben, für beide Nutzer identischen Ebene.
- `SuggestionOut` bleibt unverändert (kein Feld-Merge mit `criterion_scores` — dient weiterhin einem eigenen, bereits dokumentierten Zweck).

**Frontend:**

- `api/types.ts`: `CriterionScoreOut`-Interface analog zum Backend, `PhotoOut.criterion_scores: CriterionScoreOut[]` und `RankingOut.partition_size: number` ergänzt.
- Neue Abhängigkeit `@radix-ui/react-popover` — schrittweise Ergänzung innerhalb der bereits akzeptierten Radix/shadcn-Richtung (ADR [0011](../decisions/0011-ui-component-library.md): "nur die tatsächlich genutzten Primitives, schrittweise ergänzt"), keine neue ADR nötig. Bewusst **Popover statt Tooltip**: Radix Tooltip ist als ARIA-Tooltip-Pattern hover/focus-only konzipiert und öffnet sich absichtlich nicht per Tap — kollidiert mit der Anforderung "Tap Mobile". Popover hat einen echten Button-Trigger (funktioniert nativ per Tap), Hover wird zusätzlich manuell über einen kontrollierten `open`-State ergänzt (nur aktiv bei `matchMedia('(hover: hover) and (pointer: fine)')`, um synthetische Mouse-Events auf Touch-Geräten nicht als Hover zu werten).
- Neue generische Primitive `frontend/src/components/ui/popover.tsx` (dünner Radix-Wrapper: `Popover`/`PopoverTrigger`/`PopoverContent`, Styling konsistent mit `ui/card.tsx`/`ui/alert.tsx`).
- Neue Komponente `frontend/src/components/CriterionDetailsPopover.tsx` — feature-spezifische Komposition auf `ui/popover.tsx`, analog zum bestehenden Muster `ui/badge.tsx` → `CategoryBadge.tsx`. Props: `criterionScores: CriterionScoreOut[]`, `ranking: RankingOut | null`, `suggestion: SuggestionOut | null`.
- Ausschuss-Grund-Formatierung wird aus der bestehenden Inline-Logik in `PhotoDetailPage.tsx` in einen neuen gemeinsamen Util `frontend/src/utils/suggestionLabels.ts` extrahiert (analog `ratingLabels.ts`/`categoryLabels.ts`), damit keine zweite, potenziell auseinanderlaufende Kopie derselben Formatierung entsteht.
- Einbindung strukturell unterschiedlich: in `PhotoGridPage.tsx` liegt die Kachel heute komplett in einem `<Link>` — der Trigger wird als Geschwister-Element neben (nicht innerhalb) des `<Link>` platziert (`relative` wandert von `<Link>` auf einen neuen umschließenden `<div>`), analog zum bereits etablierten Sibling-Muster des "Übernehmen"-Buttons. `PhotoDetailPage.tsx`/`CurateCategoriesPage.tsx` haben diese Einschränkung nicht.

**Reihenfolge der Umsetzung:** Backend (`CriterionScoreOut`/`criterion_scores`, `RankingOut`-Erweiterung inkl. `partition_size`, Tests zuerst) → `api/types.ts` → `ui/popover.tsx` + Dependency → `suggestionLabels.ts` (Extraktion) + `CriterionDetailsPopover.tsx` → Einbindung in den drei Seiten (Grid zuerst, einziger strukturell nicht-trivialer Fall).

Kein neues ADR nötig — beide Kernentscheidungen (Backend-Feldstruktur, Popover statt Tooltip) sind technische Details innerhalb bereits akzeptierter Architektur-Richtungen (ADR 0021, ADR 0011).

## UI/UX

**Erscheinungsorte:** `CriterionDetailsPopover` an drei Stellen, jeweils als Icon-Button oben rechts über dem Foto — Grid-Kachel (Geschwister-Element neben `<Link>`), Einzelbild-Ansicht, Kuratierungs-Grid. Einheitliche Position an allen drei Stellen (Designprinzip "Verlässlichkeit statt Onboarding").

**Icon & Trigger:** dezentes "i" in abgerundetem Quadrat/Kreis, `text-text` (neutral, konkurriert nicht mit Bewertungsfarben), 44×44px Touch-Ziel, `aria-label="Bewertungsdetails anzeigen"`. Hoverstate Desktop: dezentes `bg-border/50`.

**Popover-Content:**
- `border border-border rounded-md shadow-sm` (Hell-Modus), im Dark-Modus Schatten durch Border ersetzt.
- Überschrift "Bewertungsdetails" (`text-sm font-semibold text-text-h`), 12px Abstand darunter.
- `<dl>` mit `<dt>`/`<dd>`-Paaren, drei Gruppen (Einzelkriterien / Kategorie+Rang / Ausschuss-Grund), `gap-1.5` innerhalb einer Gruppe, `gap-3` zwischen Gruppen.
- Werte: Kriterien als "NN%" (siehe AK 9), Kategorie ausgeschrieben, Rang als "Rang M von N", Ausschuss-Grund als eigene Zeile.
- `max-h-[60vh]` mit `overflow-y-auto` als Absicherung für viele Kriterien (nach Spec 0038 bis zu 8), in der Praxis meist kein Scroll nötig.

**Schließen:** Klick außerhalb, "×"-Button oben rechts im Header (zuverlässiger auf Mobilgeräten als Außerhalb-Tap), Escape.

**Barrierefreiheit:** `<dl>/<dt>/<dd>`-Semantik für Screenreader, Radix-Popover als `dialog`-artige Region mit automatischem Fokus-Management, alle Informationen als Text (nicht nur über Farbe/Form), Trigger voll tastaturbedienbar.

**Design-System-Bezug:** wiederverwendet `Badge`/`QualityMeter` wo sinnvoll, `rounded-md`/`shadow-sm` wie bestehende Cards (Spec 0012), 4px-Spacing-Skala, System-Font-Stack — keine neue visuelle Sprache.

## Security

Nicht sicherheitsrelevant. Der Endpunkt `GET /projects/{project_id}/photos` bleibt unverändert authentifizierungspflichtig; es wird kein neuer Endpunkt und keine neue Auth-/Autorisierungslogik eingeführt. Die neu exponierten Felder (`criterion_scores`, `RankingOut` im Default-Fall inkl. `partition_size`) sind projektweite, nicht nutzerspezifische Werte (keine `user_id`-Spalte in `PhotoCriterionScore`/`PhotoRanking`) und waren teilweise bereits über denselben Endpoint mit `top_n_per_category` abrufbar — es entsteht keine neue Sichtbarkeitsasymmetrie zwischen den beiden Nutzern. Die rohen Kriterien-Werte (`sharpness`, `exposure`, `content_people`, `content_landscape`) sind rein technische Bildmetriken bzw. ein binäres "Person(en) im Bild erkannt", ohne Identitäts-/Gesichtserkennungsbezug — keine über das bereits akzeptierte Grundmodell (private Familienfotos, nur für die beiden Nutzer sichtbar) hinausgehende Datenschutzimplikation. Die neue Frontend-Abhängigkeit `@radix-ui/react-popover` ergänzt die bereits genutzte `@radix-ui`-Bibliotheksfamilie ohne erkennbare Supply-Chain-Auffälligkeit.

## Offene Fragen

Keine — alle im Gespräch aufgekommenen Punkte wurden geklärt (siehe Entscheidungen).

## Entscheidungen (2026-08-15, im Idea-Sharpening-Gespräch mit Daniel geklärt)

- **Erscheinungsort:** überall wo Fotos gezeigt werden (Grid, Einzelbild, Kuratierung) — nicht nur an einer Stelle.
- **Detailtiefe:** vollständige Aufschlüsselung aller berechneten Werte, nicht nur eine kompakte Kernauswahl (Kategorie+Rang allein hätte auch zur Wahl gestanden).
- **Popover statt Tooltip:** technische Entscheidung des `architect`-Agenten, da die ursprüngliche Idee "Hover" für Desktop UND eine sichtbare Oberfläche für Mobile impliziert — ARIA-Tooltip unterstützt kein Tap, Radix Popover schon.
- **Rang-Anzeige "M von N":** `RankingOut` um `partition_size` erweitert (Nachfrage an `architect`, da die ursprüngliche Datenmodell-Planung nur `rank_position` ohne Gesamtgröße vorsah) — lauf-global berechnet, nicht nutzerspezifisch gefiltert, damit beide Nutzer dieselbe Zahl sehen.
- **Rundung der Prozentwerte:** ganzzahlig, kaufmännisch gerundet (z.B. "73%" statt "73,4%") — vermeidet Scheingenauigkeit bei teils heuristischen Scores; vom idea-sharpener selbst entschieden, keine Produktentscheidung mit Alternativen-Charakter.
- Alle fünf Fachrollen konsultiert (requirements-engineer, architect, ux-ui-designer, test-engineer, security-engineer je Standard/Haiku) — keine Skip-Entscheidungen in dieser Spec.
- `specs/architecture/0002-testkonzept.md` wurde ergänzt: neue Sektion zu Radix Popover mit gerätespezifischem Hover-Verhalten, insbesondere der Hinweis, dass `window.matchMedia` in `jsdom` nicht existiert und per `vi.stubGlobal` gemockt werden muss.

## Out of Scope

- Sortier-/Filteroptionen basierend auf einzelnen Kriterien-Werten (eigene, spätere Idee, falls gewünscht).
- Änderung der Kriterien-Berechnung selbst (Schärfe-/Belichtungs-Algorithmen, ML-Modelle) — reine Anzeige der bereits vorhandenen Werte.
- Anzeige für Fotos ganz ohne jeden berechneten Wert (Icon bleibt dort schlicht ausgeblendet, kein Sonderzustand).
