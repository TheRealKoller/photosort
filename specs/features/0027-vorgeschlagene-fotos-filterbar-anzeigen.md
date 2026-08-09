# 0027 - Vorgeschlagene Fotos filterbar anzeigen

**Status:** Implemented ([PR #61](https://github.com/TheRealKoller/photosort/pull/61))
**Erstellt:** 2026-08-08
**Bezug:** [`features/0003-automatic-best-photo-selection.md`](./0003-automatic-best-photo-selection.md), [`features/0024-top-photo-selection-category-mix.md`](./0024-top-photo-selection-category-mix.md), [`decisions/0006-local-scoring-datamodel.md`](../decisions/0006-local-scoring-datamodel.md), Idea-Sharpening-Gespräch mit Daniel am 2026-08-08

## Ziel

Nach einem Lauf von "Ausschuss aussortieren" (Phase A, Spec 0003) oder "Top-Fotos auswählen" (Spec 0024) zeigt `ProjectDetailPage.tsx` nur einen Ergebnistext ("N Vorschläge gefunden" bzw. "N Top-Fotos ausgewählt") plus einen generischen, ungefilterten "Fotos ansehen"-Link. Es gibt aktuell keine Möglichkeit, gezielt die soeben gefundenen, noch unbestätigten Vorschläge zu sehen — der Nutzer muss "Alle" oder "Unbewertet" manuell durchblättern und die Vorschlags-Badges suchen, was bei größeren Fotomengen unpraktikabel ist. Diese Spec ergänzt einen neuen Filter "Vorgeschlagen" in der bestehenden Foto-Grid-Ansicht, der gezielt alle Fotos mit einem noch unbestätigten Vorschlag zeigt — sowohl Phase-A-Ausschuss-Kandidaten als auch Top-Picks gemeinsam — und verlinkt die Ergebnistexte beider Läufe dorthin.

## User Story

Als Daniel bzw. seine Frau, der/die gerade "Top-Fotos auswählen" oder "Ausschuss aussortieren" ausgeführt hat, möchte ich die gefundenen, noch unbestätigten Vorschläge gezielt gefiltert in der Foto-Grid-Ansicht sehen, damit ich das Ergebnis eines automatischen Laufs sofort überprüfen und die Vorschläge bestätigen/verwerfen kann, ohne manuell durch alle Fotos zu blättern.

## Akzeptanzkriterien

- [x] Neuer Filterwert `suggested` (Label "Vorgeschlagen") in der Filterleiste der Foto-Grid-Ansicht (`PhotoGridPage.tsx`), Position im `FILTERS`-Array direkt nach "Unbewertet", vor "Favorit" — gleicher Button-/`aria-pressed`-Mechanismus wie die bestehenden fünf Filter.
- [x] `GET /projects/{id}/photos?rating_status=suggested` liefert exakt die Teilmenge, für die bei einem ungefilterten Aufruf desselben Nutzers `PhotoOut.suggestion is not None` wäre (1:1-Parität zur bestehenden `has_suggestion`-Logik in `_to_photo_out`), konkret:
  - Foto mit `PhotoScore.suggested_status` gesetzt, keine eigene Rating-Zeile des anfragenden Nutzers → enthalten.
  - Foto mit `PhotoScore.suggested_status` gesetzt, aber eigene Rating-Zeile vorhanden → nicht enthalten.
  - Foto ganz ohne `PhotoScore` → nicht enthalten.
  - Foto mit `PhotoScore`, aber `suggested_status IS NULL` → nicht enthalten.
  - Foto mit `PhotoScore.suggested_status` gesetzt, Rating eines *anderen* Nutzers vorhanden (nicht des anfragenden) → weiterhin enthalten (eigene Bewertung entscheidet, nicht fremde — Multi-User-Fall).
- [x] Der Filter deckt beide Vorschlagsarten gemeinsam ab (`reason` = `duplicate`/`low_quality` aus Phase A und `top_pick` aus Spec 0024), keine Unterteilung nach Vorschlagsart als eigene Filterwerte in v1 — gemischte Kacheln im selben gefilterten Grid sind gewollt, bleiben aber pro Kachel über die bestehenden `RatingBadge`/`CategoryBadge` unterscheidbar.
- [x] Nach einem "Ausschuss aussortieren"-Lauf (`scoringStatus === 'success'`) erscheint bei `suggestionsFoundText` zusätzlich ein Link "Vorschläge ansehen" zu `/projects/{id}/photos?filter=suggested` — auch wenn `suggestionsFound === 0` (kein Ausblenden bei 0 Treffern).
- [x] Nach einem "Top-Fotos auswählen"-Lauf (`topSelectionStatus === 'success'`) erscheint bei `topSelectionSuggestionsFoundText` derselbe Link (identischer sichtbarer Text "Vorschläge ansehen", zu `/projects/{id}/photos?filter=suggested`) — auch bei `topSelectionSuggestionsFound === 0`.
- [x] Beide neuen Links tragen ein je unterschiedliches, kontextualisiertes `aria-label` (z.B. "Vorschläge aus der Ausschuss-Aussortierung ansehen" / "Vorschläge aus der Top-Foto-Auswahl ansehen"), damit sie trotz identischem sichtbarem Text per Screenreader-Linkliste unterscheidbar sind.
- [x] Der bestehende generische, ungefilterte "Fotos ansehen"-Link (`ProjectDetailPage.tsx`, ganz unten auf der Seite) bleibt zusätzlich unverändert bestehen — wird durch die zwei neuen gefilterten Links ergänzt, nicht ersetzt.
- [x] 0 Treffer im `suggested`-Filter im Grid selbst → bestehender generischer Leerzustand-Mechanismus ("Keine Fotos mit diesem Filter." + "Filter zurücksetzen"-Button), keine filterspezifische Sondertext-Variante.
- [x] Der Filterwert ist über die URL (`?filter=suggested`) direkt verlink-/teilbar (bestehender `parseRatingFilter`/`VALID_RATING_FILTERS`-Mechanismus wird um `'suggested'` erweitert, unbekannte Werte fallen weiterhin auf `''` zurück).

## Datenmodell-Bezug

Keine Änderung. `PhotoScore`/`Rating` (siehe [`decisions/0006-local-scoring-datamodel.md`](../decisions/0006-local-scoring-datamodel.md)) bleiben unverändert — reine Leseabfrage über bereits vorhandene Felder (`suggested_status`, bestehender `own_rating`-Join).

## Architektur / Umsetzung

**Ansatz:** Rein additive Erweiterung des bestehenden `RatingFilter`-Mechanismus um einen dritten, orthogonalen Filterwert `suggested` — kein neues Muster, keine neue Abhängigkeit, kein Eingriff ins Datenmodell aus ADR 0006. Backend und Frontend folgen exakt der vorhandenen Struktur (`RatingFilter`-Enum → SQL-`WHERE`-Zweig → URL-Query-Param → Filter-Button).

**Backend (`backend/src/photosort/api/photos.py`):**
- `RatingFilter`-Enum um `SUGGESTED = "suggested"` ergänzen (neben `UNRATED`/`FAVORITE`/`ALBUM_WORTHY`/`REJECTED`).
- Neuer Zweig in `_filtered_photo_ids`: bei `rating_status is RatingFilter.SUGGESTED` join gegen `PhotoScore` (`PhotoScore.photo_id == Photo.id`) hinzufügen und filtern auf `own_rating.id.is_(None)` (bestehender, bereits auf `current_user_id` gescopeter `own_rating`-Outerjoin wird wiederverwendet, identisch zum `UNRATED`-Zweig) **UND** `PhotoScore.suggested_status.is_not(None)`. Bildet exakt die Bedingung nach, die aktuell nur clientseitig-nachgelagert in `_to_photo_out` (`has_suggestion`) berechnet wird — jetzt zusätzlich als SQL-Prädikat für die Filterung.
- Kein gemeinsam extrahierter Helper zwischen SQL-Bedingung und Python-`has_suggestion`-Check — beide sind strukturell verschiedene Ausdrucksformen derselben Regel (ORM-Query vs. Objekt-Prädikat). Stattdessen ein Kommentar am neuen SQL-Zweig, der explizit auf die Parallelität zu `_to_photo_out`/`has_suggestion` verweist (Konsistenz über Doku + Paritäts-Test, siehe Teststrategie, statt über Code-Sharing).
- Kein neuer Endpunkt, keine Response-Schema-Änderung — `GET /projects/{id}/photos?rating_status=suggested` ist der einzige neue Oberflächenpunkt.

**Frontend:**
- `frontend/src/api/types.ts`: `RatingFilter` um `'suggested'` erweitert (`export type RatingFilter = 'unrated' | 'suggested' | RatingStatus`).
- `frontend/src/utils/ratingFilter.ts`: `'suggested'` in `VALID_RATING_FILTERS` aufnehmen.
- `frontend/src/pages/PhotoGridPage.tsx`: neuer Eintrag im `FILTERS`-Array, `{ value: 'suggested', label: 'Vorgeschlagen' }`, Position nach `'unrated'`/vor `'favorite'`.
- `frontend/src/pages/ProjectDetailPage.tsx`: zwei neue `Button asChild variant="secondary" size="sm"`-Links zu `/projects/${project.id}/photos?filter=suggested`, Text "Vorschläge ansehen", direkt unter der jeweiligen `aria-live`-Ergebniszeile (`suggestionsFoundText` bzw. `topSelectionSuggestionsFoundText`) — additiv neben dem bestehenden generischen "Fotos ansehen"-Link, der unverändert bleibt.

**Betroffene Dateien:** `backend/src/photosort/api/photos.py`; `frontend/src/api/types.ts`, `frontend/src/utils/ratingFilter.ts`, `frontend/src/pages/PhotoGridPage.tsx`, `frontend/src/pages/ProjectDetailPage.tsx`.

**ADR nötig?** Nein. Additiver Query-Filter innerhalb bereits akzeptierter Architektur (ADR 0006), kein neues Muster, keine neue Abhängigkeit, keine schwer revidierbare Grundstrukturentscheidung.

## UI/UX

Design-System: [`architecture/0004-design-system.md`](../architecture/0004-design-system.md) — keine Ergänzung nötig, reine Komposition bestehender Muster (Filterleiste, Sekundär-Button-als-Link-Navigation, generischer Leerzustand).

- **Filter "Vorgeschlagen":** Label-Text "Vorgeschlagen" (Adjektivform wie die übrigen Labels). Platzierung direkt nach "Unbewertet", vor "Favorit" — "Vorgeschlagen" ist inhaltlich eine Teilmenge von "Unbewertet" (kein eigener Rating-Datensatz vorhanden), die Nachbarschaft macht das visuell nachvollziehbar, statt zwischen die drei echten, vom Nutzer gesetzten Bewertungsstufen zu geraten.
- **Links auf der Projektseite:** `Button asChild variant="secondary" size="sm"` statt `variant="link"` (garantiert das 44×44px-Touch-Ziel automatisch, kein Präzedenzfall für die bislang ungenutzte `link`-Variante). Text "Vorschläge ansehen", identisch an beiden Stellen (gleiche Position für gleiche Aktion — beide führen zum selben Ziel mit demselben Zweck), aber unterschiedlichem `aria-label` je Kontext. Bewusst **ohne** Foto-Anzahl im Linktext, da `suggestions_found`/`suggestions_found` die Trefferzahl *dieses einen Laufs* zum Abschlusszeitpunkt ist, während der Filter den *aktuellen* Bestand aller offenen Vorschläge zeigt (könnte nach teilweisem Bestätigen oder einem zweiten Lauf abweichen).
- **0-Treffer-Verhalten:** Link wird trotzdem angezeigt (kein Ausblenden) — "0 gefunden" ist bereits ein normales, nicht-fehlerhaftes Laufergebnis; ob der Filter *insgesamt* leer ist, hängt zusätzlich vom Bestand aus anderen Läufen/der jeweils anderen Vorschlagsart ab. Landet der Nutzer auf einem leeren gefilterten Grid, greift der bestehende generische Leerzustand (keine filterspezifische Sondertext-Variante, Konsistenz mit den übrigen vier Filtern).
- **Sonstige Zustände:** Ladezustand/Skeleton, Fehlerzustand, Pagination unverändert (nur ein zusätzlicher `ratingStatus`-Wert im bestehenden Query-Mechanismus). Filterleiste ist bereits `flex flex-wrap`, ein sechster Button verhält sich wie die bestehenden fünf, kein neuer Responsive-Fall.

## Security

**Nicht relevant.** `GET /projects/{id}/photos` (einziger betroffener Endpunkt) hängt bereits an `Depends(get_current_user)` — kein neuer Endpunkt, kein neuer Auth-Pfad. Der neue Enum-Wert `SUGGESTED` fließt in den bereits bestehenden, serverseitig gegen eine geschlossene Allowlist validierten Query-Parameter `rating_status` ein (ungültige Werte → 422, wie bei den vier bestehenden Werten). Der neue SQL-Zweig erweitert lediglich den bereits vorhandenen, korrekt auf `current_user_id` gescopeten `own_rating`-Join um eine zusätzliche Bedingung — `current_user_id` stammt weiterhin ausschließlich aus dem JWT, nie aus Client-Eingabe, keine neue Umgehungsmöglichkeit. Projekt-Zugehörigkeit ist laut `architecture/0003-securitykonzept.md` bereits bewusst kein Autorisierungsmerkmal in diesem Zwei-Nutzer-System (ADR 0003 Auth-Modell) — daran ändert dieser Filter nichts. Keine neue externe Schnittstelle, kein Secret-Bezug, keine neue Eingabe von außen im sicherheitsrelevanten Sinn.

## Teststrategie

- **Backend, Integrationsebene** (`backend/tests/test_api_photos.py`, `authenticated_api_client` + In-Memory-SQLite, Muster identisch zu bestehenden `test_list_photos_filters_by_own_*`-Tests):
  - Fallmatrix für den `suggested`-Zweig (siehe Akzeptanzkriterien): kein `PhotoScore`, `suggested_status IS NULL`, eigenes Rating vorhanden/fehlt, fremdes Rating eines anderen Nutzers.
  - **Paritäts-Test** (wichtigster neue Test): gleicher Datensatz einmal ungefiltert abgefragt, Menge der IDs mit `item["suggestion"] is not None` gebildet, gegen die Menge der IDs aus `rating_status=suggested` verglichen — müssen identisch sein. Sichert die bewusste Doppelimplementierung (Python-Boolean in `_to_photo_out` vs. SQL-`WHERE` in `_filtered_photo_ids`) gegen künftiges Auseinanderlaufen ab.
  - Mix-Test: drei Fotos (`REJECTED`+`duplicate_of` gesetzt, `REJECTED` ohne `duplicate_of`, `ALBUM_WORTHY`) erscheinen gemeinsam im `suggested`-Filter, keine serverseitige Unterteilung nach `reason`.
  - Multi-User-Test analog `test_list_photos_filter_is_scoped_to_own_rating_not_others`: zwei Nutzer, gleiches Foto mit Vorschlag, Nutzer A hat eigenes Rating gesetzt (sieht Vorschlag nicht mehr), Nutzer B nicht (sieht ihn weiterhin).
  - Leerer Zustand analog bestehendem `test_list_photos_returns_empty_list_when_filter_matches_nothing`-Muster, nur mit `rating_status=suggested`.
  - Kein dedizierter neuer Test für Pagination/404/401 nötig — filterwert-unabhängig, bereits generisch abgedeckt.
- **Frontend, Integrationsebene** (`vitest` + Testing Library, bestehendes Mock-Muster):
  - `PhotoGridPage.test.tsx`: neuer Filterbutton "Vorgeschlagen" klickbar, setzt URL, ruft API mit `rating_status: 'suggested'`; direkter URL-Aufruf mit `?filter=suggested` markiert Button als aktiv.
  - `ProjectDetailPage.test.tsx`: da beide neuen Links denselben sichtbaren Text tragen, über `getByRole('link', { name: <aria-label-Text> })` selektieren, nicht über `getByText` (Mehrfachtreffer). 0-Treffer-Sichtbarkeit (`suggestions_found: 0` → Link trotzdem im DOM), Koexistenz aller drei Links (generisch + 2 neue) in einem Render.
  - `ratingFilter.test.ts`: `'suggested'` in `VALID_RATING_FILTERS`, `parseRatingFilter('suggested')` liefert `'suggested'`, unbekannter Wert weiterhin `''`.
- **Nicht gesondert nötig:** `RatingBadge`/`CategoryBadge`-Rendering selbst (bereits aus Spec 0003/0021 getestet, keine neue Rendering-Logik).
- `specs/architecture/0002-testkonzept.md` wird **nicht** ergänzt — der Filter folgt exakt dem bei Spec 0002 etablierten Integrationstest-Muster und der bei Spec 0003/0021 dokumentierten "berechnet, aber bedingt sichtbar"-Logik, kein neues externes System, kein neuer Testebenen-Typ.

## Entscheidungen (2026-08-08, im Idea-Sharpening-Gespräch mit Daniel geklärt)

- **Anzeigeform — Filter statt eigener Ergebnis-Ansicht:** kein neues, separates Ergebnis-Screen, sondern ein neuer Filterwert in der bestehenden Foto-Grid-Ansicht. Einfacher, wiederverwendbarer, und der Link braucht den Filter ohnehin als Grundlage.
- **Filter-Umfang — beide Vorschlagsarten gemeinsam:** bewusst nicht nur Top-Picks (Spec 0024), sondern auch der ältere Phase-A-Ausschuss (Spec 0003) — deckt das analoge Problem nach "Ausschuss aussortieren" gleich mit ab, nicht nur den ursprünglich genannten Top-Foto-Fall. Keine Unterteilung nach Vorschlagsart als eigene Filterwerte in v1.
- **Bestehender genereller Link bleibt:** der generische, ungefilterte "Fotos ansehen"-Link bleibt zusätzlich zu den zwei neuen gefilterten Links bestehen, statt ersetzt zu werden.
- **Priorisierung:** von Daniel indirekt bestätigt (Roadmap-Einordnung durch `requirements-engineer`, unter "Jetzt" — direkte, aktive Nutzungseinschränkung eines gerade erst ausgelieferten Kernfeatures aus Spec 0024, keine Verdrängung bereits geplanter Arbeit).

## Offene Fragen

Keine offenen Fragen mehr für den Scope dieser Spec.

## Out of Scope

Separate Filterwerte je Vorschlagsart (z.B. "nur Top-Picks" vs. "nur Ausschuss") — bewusst ein gemeinsamer Filter in v1; eigenes, vom Foto-Grid losgelöstes Ergebnis-Screen pro Lauf; Änderungen an der Bestätigungs-/Verwerfungs-Logik selbst (`PUT /photos/{id}/rating`); ein "aktueller Live-Zähler" im Linktext der beiden neuen Projektseiten-Links.
