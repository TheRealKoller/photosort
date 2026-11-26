# 0654 - Die Typen der Oberfläche entstehen aus der Schnittstellenbeschreibung des Servers

**Status:** Implemented ([PR #672](https://github.com/TheRealKoller/photosort/pull/672))
**Erstellt:** 2026-11-26
**Bezug:** Issue [#654](https://github.com/TheRealKoller/photosort/issues/654)
**Umfang:** über dem Richtwert von rund 200 Zeilen, weil das Dokument zwei Umsetzungsschritte
trägt: eine Nachführkette aus drei Prüfungen samt benannter Server-Antworten und die Zerlegung von
sechs Seiten mit je eigener Baustein- und Unverändert-Liste; die Architekturentscheidungen selbst
stehen in [ADR 0153](../decisions/0153-typen-aus-der-schnittstellenbeschreibung.md).

## Ziel

Die Antworttypen der Oberfläche entstehen aus der OpenAPI-Beschreibung des Servers statt aus einer
handgepflegten Datei. `backend/openapi.json` wird aus `create_app().openapi()` erzeugt und
eingecheckt, `frontend/src/api/generated/schema.d.ts` entsteht daraus. `frontend/src/api/types.ts`
bleibt die eine Importquelle und enthält nur noch Aliasse auf erzeugte Schemata sowie
gekennzeichnete oberflächen-eigene Ableitungen. Eine Änderung an einer Antwortstruktur ohne
Nachführung wird an genau der Stelle rot, an der sie entsteht.

Zusätzlich werden die sechs großen Seiten (457–760 Zeilen) in benannte Bausteine zerlegt, ohne ihr
sichtbares Verhalten zu ändern.

## User Story

Als Entwickler von PhotoSort möchte ich, dass die Typen der Serverantworten aus der
Schnittstellenbeschreibung des Backends entstehen und die Aussagen über das Serververhalten dort
stehen, wo der Server sie festlegt — und dass die sechs großen Seiten in überschaubare Bausteine
zerlegt sind —, damit eine Änderung am Server nicht unbemerkt zu einer falschen Annahme in der
Oberfläche wird und ich beim Lesen einer Seite nicht 1.500 Zeilen durchsuchen muss, ohne das
Verhalten der Seiten anzutasten.

## Akzeptanzkriterien

- [ ] **Nachführung ist erzwungen.** Ändert sich eine Antwortstruktur des Servers (Feld,
      `required`-Liste, Typ, Enum-Wert, Beschreibung, Pfad, Methode oder Erfolgs-Statuscode), ohne
      dass das Artefakt nachgeführt wird, scheitert `backend/tests/test_openapi_vertrag.py` mit
      einem Befund, der den geänderten Ort in Punktnotation und beide Nachführbefehle nennt. Ist
      das Artefakt nachgeführt, `schema.d.ts` nicht, scheitert `npm run api:check` (Teil von
      `typecheck`) mit Datei und Befehl. Sind beide nachgeführt, scheitert `tsc` an jeder
      betroffenen Aufruf- oder Anzeigestelle, nicht in `schema.d.ts`. Ohne eine solche Änderung
      enden alle drei Schritte mit 0. Belegt durch die Abfolge (a)–(d) im Pull Request, nicht
      durch eine Momentaufnahme. *(Backend-pytest mit Meldungs-Selbsttest; `api:check`; `tsc`;
      PR-Beleg)*
- [ ] **Eine Fassung je Antwortstruktur.** `frontend/src/api/types.ts` enthält kein `interface`;
      es trägt genau die zwei Marker „Erzeugt" und „Oberflächen-eigen", je einmal und in dieser
      Reihenfolge, und jede Deklaration liegt unter einem von beiden. Jeder Alias unter „Erzeugt"
      ist ein `components["schemas"]["X"]`-Bezug, dessen `X` im Artefakt existiert. Außerhalb von
      `types.ts`, `client.ts` und `generated/` deklariert kein Modul unter `frontend/src/api/`
      einen eigenen Typ — damit bleibt auch eine Kopie fern, die nicht `types.ts` heißt. Die
      verbleibenden eigenen Typen stehen als Liste im Pull Request und decken sich mit der Ausgabe
      des Wächters. *(scripts/tests-Wächter; `tsc`; PR-Liste)*
- [ ] **Kein Verlust an Typgenauigkeit, keine stille Übernahme.** Die 2xx-Antwort der vier
      Auslöser ist ein `$ref` auf ein benanntes Schema mit genau einem `status`-Wert `queued`, die
      des Ausschuss-Abschlusses auf eines mit `confirmed`, die von `/health` auf eines mit `ok`;
      keine 2xx-Antwort mit JSON-Körper ist ein unbenanntes Objekt (keine Ausnahmeliste). Die
      beiden Abweichungen sind entschieden, nicht übernommen: `ExportRunDetailOut` führt kein
      `cancel_requested_at`, und keine Produktivstelle liest es vom Detail; der Exportlauf führt
      ausschließlich `ExportRunStatus`. Aus einem benannten Antworttyp wird keine Stelle ein
      `{ status: string }` oder ein anderer Sammeltyp. *(Backend-pytest; Wächter
      `keine-zweite-fassung`; `tsc`)*
- [ ] **Bewusst getrennte Vokabulare bleiben getrennt.** `ScanStatus` und `ExportRunStatus` sind
      zwei benannte Schemata; jede Statusreferenz einer Scanstruktur nennt das eine, jede einer
      Exportstruktur das andere. In der Oberfläche ist `ScanStatusLabel` als
      `ScanStatus | "never"` abgeleitet, nicht als zweite Literalliste, und die beiden behandelnden
      Stellen sind erschöpfend (`Record<ScanStatusLabel, …>` in `StatusTag.tsx`, `switch` mit
      `const unhandled: never` in `useProjects.ts::isActive`). Ein einseitig ergänzter Wert wird an
      der behandelnden Stelle zum Typfehler; belegt durch Rot-Nachweis 2 im Pull Request.
      *(Backend-pytest; Wächter; `tsc`; PR-Beleg)*
- [ ] **Verhaltensregeln stehen an der Stelle, die sie festlegt.** Im Artefakt trägt jede in
      fester Liste benannte Regelstelle eine nicht-leere Beschreibung mit ihrem Stichwort:
      `null`-statt-`0` an `ScanSummary.total_files`, an den `null`-fähigen Feldern von
      `CloudPhaseSummaryOut`, an `ClassificationEstimatePartOut.price_per_image_usd` und
      `candidate_count` sowie an `CriterionScoringRunSummary.phase_remaining_seconds`;
      „angenommen, noch nicht begonnen" am `ScanStatus`; die Teilfehler-Semantik an
      `ExportRunStatus` und `ExportRunDetailOut`; die Feldwirkung je Schreibendpunkt im
      Route-Docstring. Dieselben Texte erscheinen über den erzeugten Typ in `schema.d.ts`. Die vier
      in der Spec benannten Oberflächenkommentare mit reiner Serveraussage entfallen; die
      Anzeige- und Bedienregeln bleiben und sind durch die vorhandenen Verhaltenstests gedeckt.
      *(Backend-pytest; Wächter `beschreibung-am-typ`; vorhandene vitest-Seitentests)*
- [ ] **Aufruf und Antwort gehören zusammen.** Jede Produktivstelle ruft
      `apiFetch`/`apiFetchBlob` mit einer Endpunktvorlage aus `paths` und getrennten `pathParams`
      auf; ein konkreter Pfad, ein fehlender Pfadparameter und ein `body` an einem körperlosen
      Endpunkt sind Typfehler (`@ts-expect-error`-Proben). Pfadparameter werden mit
      `encodeURIComponent(String(value))` kodiert und ganzzahlig kanonisiert, Query-Werte über
      `URLSearchParams` serialisiert. Kein Produktivcode nennt einen Antworttyp als Typargument
      (`apiFetch<…>`) oder hebt das Ergebnis mit `as any`/`as unknown` auf; die Modultest-Variante
      mit `Promise<unknown>` wird ausschließlich in `*.test.ts` über `vi.mocked` erreicht.
      *(vitest-Laufzeitfälle; `@ts-expect-error` über `tsc`; Wächter)*
- [ ] **Seiten-Aufteilung ohne Verhaltensänderung.** Die 13 Seiten-Testdateien der Spec bleiben in
      jeder Erwartung an sichtbares Verhalten unverändert; nur der Importpfad einer verschobenen
      Textkonstante ändert sich. Ihre Testknoten-Menge und ihr Ausgang sind vor/nach identisch; die
      e2e-Specs bleiben unverändert. Adressen und Direktlinks (Foto, Filter, Herkunft, Seite),
      Lade-, Leer- und Fehlerzustände, Rückmeldungen nach Aktionen sowie Tastatur- und
      Fokusführung sind durch diese Tests gedeckt. Die Sichtprüfung jeder Seite in 360 px und
      Desktop belegt, was jsdom nicht sieht. *(vitest mit Knotenmengen-Gleichheit; e2e;
      Sichtprüfung)*

## Datenmodell-Bezug

Keine neue Entität, keine Migration. Die beiden Statusvokabulare bleiben getrennte Schemata:
`ScanStatus` und `ExportRunStatus` (`backend/src/photosort/models.py`). Der Export-Lauf führt
künftig ausschließlich `ExportRunStatus`. Siehe [`docs/architecture.md`](../../docs/architecture.md)
und ADR 0153.

## Architektur / Umsetzung

### 1. Der Vertrag: eine Beschreibung, ein eingechecktes Artefakt

- **Neu `backend/scripts/export_openapi.py`:** setzt vor dem Import dieselben Test-Vorgaben wie
  `backend/tests/conftest.py` (`SECRET_KEY` ≥ 32 Zeichen, `RATE_LIMIT_STORAGE_URI=memory://`) und
  schreibt `create_app().openapi()` nach `backend/openapi.json` — UTF-8, `indent=2`,
  `sort_keys=True`. Eingecheckt, nie von Hand bearbeitet.
- **Neu `frontend/src/api/generated/schema.d.ts`:** erzeugt aus `backend/openapi.json` mit
  `openapi-typescript`, exakt gepinnt (`7.13.0`) als Dev-Abhängigkeit. Keine
  Laufzeitabhängigkeit. Trägt den Erzeuger-Kopf, steht in `.prettierignore` und in der
  Oxlint-Ausnahme, wird nie editiert.
- **`frontend/package.json`:** `api:generate` (schreibt die Datei), `api:check` (erzeugt in eine
  temporäre Datei und vergleicht), `typecheck` ruft `api:check` vor `tsc` auf. Damit läuft die
  Prüfung in CI und in `scripts/check.sh` ohne neuen Job und ohne neuen Required-Check.

### 2. Der typisierte Aufruf — Aufruf und Antwort gehören zusammen

`frontend/src/api/client.ts` nimmt den **Endpunkt als Vorlage** (`"/projects/{project_id}/scan"`)
und die Pfadparameter getrennt (`pathParams`). Antwort- und Anfragekörper leiten sich aus
`paths[Endpunkt][Methode]` ab; der Aufrufer kann den Antworttyp nicht mehr wählen. `query` ist der
typisierte Query-Typ des Endpunkts, `body` der typisierte Anfragekörper; Endpunkte ohne Körper
erlauben kein `body`. `pathParams` wird aus den `{…}`-Platzhaltern abgeleitet und gepflichtet, die
Laufzeit kodiert mit `encodeURIComponent`. Unverändert: `ApiError`, die zentrale 401-Behandlung,
`204 → undefined`, `apiFetchBlob` (nimmt ebenfalls Vorlage + Pfadparameter).

Die einzige Typaussage an der HTTP-Grenze leitet sich aus dem Endpunkt ab; sie ist nicht mehr
`apiFetch<T>` mit freiem `T`. Für die gemockte Grenze der API-Modultests trägt `apiFetch` als
letzte Signatur eine Variante, die `Promise<unknown>` liefert — sie kann keine Typaussage behaupten,
`vi.mocked(apiFetch).mockResolvedValue(...)` bleibt typisierbar.

### 3. Eine Fassung je Antwortstruktur — `types.ts`

`frontend/src/api/types.ts` bleibt die eine Importquelle und enthält genau zwei gekennzeichnete
Abschnitte:

- **Erzeugt:** je Serverstruktur ein Alias auf `components["schemas"][…]`; der Alias darf einen
  Oberflächennamen tragen, die Struktur kommt unverändert aus der Beschreibung.
- **Oberflächen-eigen:** Typen ohne Servergegenstück (Anzeige-Ableitungen,
  camelCase-Parameterobjekte der API-Module), abgeleitet aus erzeugten Typen, wo ein Serverfeld die
  Aussage trägt.

Nach der Umstellung enthält `types.ts` keine `interface`-Deklaration mehr. Die verbleibenden
eigenen Typen (Liste im Pull Request): `ListPhotosParams`, `ListDraftAlternativesParams`,
`ListAusschussParams`, `ApiFetchOptions` sowie die Anzeige-Ableitungen `ClassificationWay`,
`ClassificationPath`, `ScanStatusLabel`, `PhotoVariant`, `CloudVisionPurpose`/`StatsCostPurpose`.

Mechanischer Wächter: **neu `scripts/tests/test_frontend_typen.py`** (reine Funktion
`Bestand → Befunde`, Invarianten in `scripts/tests/waechter_aussagen.json`, je Invariante eine
Mutation in `scripts/tests/mutationen.py`): keine `interface`-Deklaration mit einem Schemanamen,
jeder `components["schemas"]["X"]`-Bezug nennt einen vorhandenen Schemanamen, beide
Abschnittsmarker vorhanden und in Reihenfolge.

### 4. Die drei Prüfungen und der Rot-Grün-Nachweis

1. **`backend/tests/test_openapi_vertrag.py`** (neu): vergleicht `backend/openapi.json` mit
   `create_app().openapi()` über eine reine Funktion. Die Meldung nennt Schemaname/Feld bzw.
   Pfad/Methode/Status und den Nachführschritt (`backend/scripts/export_openapi.py`, dann
   `npm --prefix frontend run api:generate`). Dieselbe Datei prüft: jede 2xx-Antwort mit
   JSON-Körper ist ein `$ref` (oder ein Array davon), ohne Ausnahmeliste, und die benannten
   Antworten aus Abschnitt 7 sind vorhanden.
2. **`npm run api:check`** (Teil von `typecheck`): meldet fehlende Nachführung von
   `schema.d.ts` samt Datei und Befehl.
3. **`tsc`**: prüft jede Aufrufstelle gegen den nachgeführten Typ.

Rot-Grün im PR: (a) Feld/Rename an einer Antwortstruktur ohne Artefakt-Nachführung → Backend-Test
rot mit benannter Stelle; (b) Artefakt nachgeführt, Typen nicht → `api:check` rot; (c) Typen
nachgeführt → `tsc` rot an der betroffenen Aufruf-/Anzeigestelle; (d) alles nachgeführt → grün.

### 5. Vokabulare getrennt halten

`S["ScanStatus"]` und `S["ExportRunStatus"]` sind zwei benannte Schemata.
`ExportRunSummary`/`ExportRunDetailOut` führen ausschließlich `ExportRunStatus`.
`ScanStatusLabel = ScanStatus | "never"` ersetzt die zweite Literalliste in
`frontend/src/utils/scanStatus.ts`. Zwei `never`-Wächter machen eine Vokabelerweiterung zum
Typfehler: die `Record<ScanStatusLabel, …>`-Abbildung in `components/StatusTag.tsx` und `isActive`
in `hooks/useProjects.ts` als erschöpfender `switch` mit `const unhandled: never = status`. Ein
zusätzlicher Wert im einen Vokabular erscheint nicht im anderen; die jeweils behandelnde Stelle
wird rot.

### 6. Verhaltensregeln an ihren Ort

Regeln über das Serververhalten stehen in der Schnittstellenbeschreibung: als Docstring der
Antwortstruktur bzw. des Enums (erscheint als JSDoc am erzeugten Typ) oder als
`Field(description=…)` am Feld (erscheint am Feldzugriff). Dazu gehören insbesondere „nicht erfasst
ist `null` und nie `0`" (`ScanSummary.total_files`, `CloudPhaseSummaryOut.*`,
`ClassificationEstimatePartOut.price_per_image_usd`/`candidate_count`,
`CriterionScoringRunSummary.phase_remaining_seconds`), „`queued` heißt angenommen, aber noch nicht
begonnen" (Docstring `ScanStatus`) und die `ExportRunStatus`-Semantik (Teilfehler enden `success`)
am Enum und an `ExportRunDetailOut`. „Welcher Endpunkt welches Feld schreibt und welches unberührt
lässt" bleibt in den Route-Docstrings und wird dort ergänzt, wo eine Aussage fehlt.

Oberflächenkommentare, die nur diese Serverregeln wiederholten, entfallen mit dem Umbau von
`types.ts`. Anzeige- und Bedienregeln bleiben und ziehen an die Stelle, die sie umsetzt.

### 7. Server-Änderungen (Antwortstruktur wird benannt/präzise)

- **Neu `backend/src/photosort/api/responses.py`:** `TriggerQueuedOut { status: Literal["queued"] }`,
  `AusschussGateConfirmedOut { status: Literal["confirmed"] }`; `response_model=` an
  `trigger_scan`, `trigger_score`, `trigger_classify`, `trigger_export`, `confirm_ausschuss_gate`.
- **`main.py`:** `HealthOut { status: Literal["ok"] }` für `/health`.
- **`api/operations.py`:** `CancelOutcome(StrEnum)` (`cancel_requested`/`already_finished`) statt
  `outcome: str`.
- **`api/classification_reviews.py`:** `counts_by_purpose`/`verdicts_by_purpose` als feste Modelle
  mit den vier Zwecken statt `dict[...]` — der JSON-Körper bleibt gleich, die
  Schlüssel-Erschöpfung bleibt typisiert.
- **Binärantworten:** `GET /photos/{id}/image`, `GET /photos/{id}/faces/{index}/image` und
  `GET /projects/{id}/classification-reviews/{id}/export` erhalten `response_class`; die
  Beschreibung behauptet dann keinen JSON-Körper mehr. Verhalten unverändert.

### 8. Seiten-Aufteilung (nach Schritt 1–7, Verhalten unverändert)

Alle Bausteine liegen unter `components/` bzw. `hooks/`; die Seiten bleiben Datenzugriff +
Komposition. DOM-Reihenfolge, `aria-*`, `data-testid`, Fokus- und Tastaturführung werden
zeichengleich übernommen. Die konkrete Zerlegung je Seite steht im Abschnitt „UI/UX".

**Nachzuziehende Struktur-Verträge** (keine Erwartung an sichtbares Verhalten ändert sich):
`designSystem.scales.contract.test.ts` — **vier** `file`-Werte der `TALL_CONTROL_ALLOWLIST`:
AlbumDraft-Aufklappzeile → `AlbumDraftDay.tsx`, Gruppen-Navigation → `DuplicateGroupHeader.tsx`,
und die beiden Ausschuss-Einträge (Zähler der automatisch entschiedenen Gruppen, Rückweg aus der
gefilterten Ansicht) → `AusschussOverview.tsx`. `designSystem.usage.contract.test.ts` —
`CURATION_FILES` um `AlbumDraftDay.tsx`, die drei Duplikat-Zusagen (`GRID_LIST_CLASSES`,
Skeleton-Klassen hinter `width + DUPLICATE_TILE_INSET_X_PX`, `px-2`/`border-2`) zielen auf
`DuplicateGroupGrid.tsx`. `albumSelection.structure.test.ts` — `DRAFT_FILES` um die neuen
Entwurfs-Bausteine. `photoDetail.structure.test.ts` — Deklarationsort `api/types.ts` →
`api/generated/schema.d.ts`. Ohne diesen Nachzug fielen die verschobenen Stellen still aus dem
Prüfsatz; ein vergessener Eintrag meldet sich als verwaiste Freigabe.

## UI/UX

### Leitlinie: die Zerlegung ist ein Umzug, keine Umgestaltung

Für jeden Baustein gilt: Markup, Klassen, `aria-*`, `id`s, `data-*`-Haken, Textknoten und
DOM-Reihenfolge werden zeichengleich übernommen. Die Seite bleibt Datenzugriff und Komposition;
die Bausteine liegen unter `frontend/src/components/` bzw. `frontend/src/hooks/`, ihre Wortlaute
in `frontend/src/utils/*Texts.ts`. Drei Regeln halten die Zerlegung prüfbar:

1. **Zustand bleibt oben.** Kein Baustein unterhalb der Seite hält Serverzustand, führt eine
   Mutation aus oder entscheidet über Sperren, Fokusziele und Rückgängig-Zustände.
2. **Refs bleiben Objekte der Seite.** `containerRef`, `barRef`, `headingRef`, `photoHeadingRef`
   werden als dieselben Objekte weitergereicht; ein im Kind neu erzeugtes Ref-Objekt verlöre den
   Knoten still (`useDraftPosition`, Fokus-Effekte).
3. **Keine Zwischen-Wrapper.** Wo ein Test `within(...)`, `compareDocumentPosition` oder
   `not.toContainElement` nutzt, darf der Baustein kein zusätzliches `<div>` um den bestehenden
   Block legen.

### Seite für Seite

#### `pages/AlbumDraftPage.tsx` (760 Zeilen)

Die Seite behält Parameter/Queries/Mutationen, `usePersonFilter`, `useCurationLightbox`, die
abgeleitete Sicht (inklusive `draftMembership`, siehe Struktur-Verträge), Sperren, Aktionsfehler,
Rückgängig-Zustand, Fokuswunsch, Aufklapp-Panel, `renderTile` und den Wurzel-`<div ref>`.

| Baustein | Verantwortung | Props |
|---|---|---|
| `components/AlbumDraftHeader.tsx` | `<header>` mit `h1` (`ref={headingRef}`, `tabIndex={-1}`), Übersichtszeile, `EyeAttribution` | `headingRef`, `overviewText`, `showEye` |
| `components/AlbumDraftBar.tsx` | mitlaufende Leiste (`data-draft-bar`, `ref={barRef}`): Position, Ziel, Eventname, Größenzeile, `smaller-proposal` | `barRef`, `dayNumber`, `dayCount`, `position`, `eventCount`, `selectionPath`, `groupHeading`, `sizeText`, `smallerProposal` |
| `components/AlbumDraftDay.tsx` | ein Tag: `<section data-draft-position>`, aufklappbares `h2` mit `aria-expanded`/`aria-controls`, Panel-`id` | `heading`, `collapsed`, `count`, `firstEventPosition`, `panelId`, `onToggle`, `children` |
| `components/AlbumDraftDayControls.tsx` | „Alle Tage aufklappen/zuklappen" | `onExpandAll`, `onCollapseAll` |
| `components/AlbumDraftNotice.tsx` | der eine Hinweisblock (Satz + sekundärer Link) | `text`, `to`, `linkLabel` |
| `components/AlbumDraftFilterNotices.tsx` | Statuszeile (`role="status"`) und Leerzustand mit Rücksetzknopf | `isFiltered`, `visibleCount`, `inAlbumCount`, `hiddenExchange`, `onReset` |
| `components/AlbumDraftClosing.tsx` | „Stand des Entwurfs", Sätze, primärer Weg | `sentences`, `selectionPath` |
| `hooks/useDraftDecisions.ts` | Schreibwege mit Sperre, Fehlerplatz, Rückgängig-Ziel, Fokuswunsch | `projectId`, `username`, `albumOf`, `struckOf`, `onRequestFocus`, `onCloseBand` → `locked`, `errorAt`, `undoView`, `undoError`, `undoRestart`, fünf Handler |

Unverändert: `?persons=` am Ort (Filter, Zählung, Rücksetzen ohne Neuladen), `?photo=` der
Großansicht, Skeleton mit 6 Kacheln, beide Fehler-Alerts, Vorrang der Leerzustände, Fokusziele
`decide-*`/`readd-*`/`add-*`/`alternatives-*`/`add-trigger-*`/`struck-toggle-*`, Fokus auf die
`h1` nach filterverstecktem Tausch, Scrollposition nach jeder Aktion, Gestrichen-Zeile als
zweiter Weg.

#### `pages/PhotoDetailPage.tsx` (513 Zeilen)

| Baustein | Verantwortung | Props |
|---|---|---|
| `hooks/usePhotoSequenceNavigation.ts` | `goTo`, `handlePrev`, `handleNext`, `advanceToNextUnrated`, `completed` | `projectId`, `photos`, `index`, `hasNextPage`, `fetchNextPage`, `filterQuery`, `username` |
| `hooks/usePhotoDetailKeys.ts` | der eine `keydown`-Listener mit `isTextInputFocused`-Wächter (←/→/1/2/3) | `handlePrev`, `handleNext`, `handleToggleRating`, `handleToggleFavorite` |
| `components/PhotoDetailStates.tsx` | Lade-/Fehlerrahmen der Bühne, Abschluss, „nicht in der Auswahl gefunden" | `status`, `errorText`, `onRetry`, `gridPath`, `selectionPath` |
| `components/PhotoSuggestionNotice.tsx` | Vorschlagskasten mit „Vorschlag übernehmen" | `suggestion`, `busy`, `onAccept` |
| `components/PhotoVerdictSection.tsx` | `verdict-section` mit `PhotoVerdict`, Eye-Band, `motifs-section` | `photo`, `eyeFineLabels`, `motifSet`, `motifSetLoading`, `motifSetError`, `onMotifSetRetry`, `onCorrect`, `onWithdraw`, `pendingMotifKey`, `error` |

`MOTIF_SET_ERROR_TEXT` bleibt in der Seite und wird als Prop weitergereicht. Unverändert:
Blockreihenfolge (Bühne → Vorschlag → `verdict-section` → Personen → Einzelwerte → Aufnahmezeit →
Cloud-Vision-Status → Rückweg), `aria-labelledby`, Personenabschnitt außerhalb von
`verdict-section`, Zähler mit Filterweitergabe, Auto-Advance nur nach Bewertung, Tasten 1/2/3,
Wischschwelle 50 px, Fehler-Alert mit genau einer Wiederholung.

#### `pages/DuplicateComparePage.tsx` (501 Zeilen)

| Baustein | Verantwortung | Props |
|---|---|---|
| `components/DuplicateGroupHeader.tsx` | `h1` mit Stelle/Gesamtzahl/Mitgliedern/Spanne + `Progress`, Gruppennavigation (`role="group"`, Refs, `disabled` am Rand) | `group`, `previousRef`, `nextRef`, `onPrevious`, `onNext` |
| `components/DuplicateGroupNotices.tsx` | automatisch-entschieden-Block, Leertext, Ladefehler, Rücknahme-`role="status"`, Hinweis + Folge-Satz | `filled`, `autoDecided`, `autoUndoneAndOpen`, `empty`, `loadError`, `onRetry` |
| `components/DuplicateGroupActions.tsx` | Alle-behalten/Alle-in-den-Ausschuss, Abschlussknopf, die immer vorhandene Live-Region `duplicate-last-group` | `groupPending`, `groupError`, `autoDecided`, `confirmBlocked`, `confirmPending`, `confirmLabel`, `lastGroupSaved`, `confirmError`, `onGroupDecision`, `onConfirm` |
| `components/DuplicateGroupGrid.tsx` | Skeleton-`ul` und gefülltes `ul`/Großansicht an derselben Stelle; `useElementWidth`, `duplicateGridRows`, `tileSizesByIndex`, `GRID_LIST_CLASSES` | `loading`, `items`, `enlargedItem`, `decidingIds`, `onOpen`, `onClose`, `onSelect`, `onDecide`, `imageRef` |
| `utils/duplicateTexts.ts` | `DUPLICATE_HINT_TEXT`, `DUPLICATE_CONSEQUENCE_TEXT`, `DUPLICATE_EMPTY_TEXT`, `LAST_GROUP_TEXT` — je einmal | — |

Unverändert: Rückweg nur bei `from=ausschuss`, Ankerwechsel setzt Vergrößerung/Sperren/
Abschlussmeldung zurück, Fokusübergabe am Rand, Live-Region bleibt dasselbe Element, Abschluss
fehlt in automatisch entschiedener Gruppe (nicht `disabled`), Skeleton unter der allgemeinen
Überschrift, Leertext und Fehler-Alert schließen einander aus, „Behalten" nimmt eine automatische
Entscheidung zurück.

#### `pages/ClassificationReviewDetailPage.tsx` (499 Zeilen)

| Baustein | Verantwortung | Props |
|---|---|---|
| `hooks/useReviewPhotoPosition.ts` | `?foto=` lesen/prüfen, Ersatz per `replace`, Positionen | `searchParams`, `setSearchParams`, `cases`, `photoCount` |
| `hooks/useReviewKeys.ts` | der eine `keydown`-Listener (Textfeld-/Modifier-Wächter, ←/→, Urteilstasten) | `judge`, `goToPosition`, `markedCase`, `previousPosition`, `nextPosition` |
| `components/ReviewOrigins.tsx` | die beiden Herkunftsblöcke (Marke, Text, Kosten, Eye-Nennung) | `review` |
| `components/ReviewStand.tsx` | `aria-live`-Stand: Marke, Phase, Abbruch, Fortschritt, Abschluss-/Fehlsätze | `review`, `caseTotal`, `onCancel`, `cancelPending`, `cancelFocusToken` |
| `components/ReviewCaseView.tsx` | Fallansicht: Foto-`h2`, Navigation, `PhotoImage` ohne Link, Urteilsfehler, Fallliste | `position`, `photoCount`, `photoCases`, `photoId`, `previousPosition`, `nextPosition`, `nextOpenPosition`, `headingRef`, `onGoToPosition`, `motifs`, `markedCaseId`, `judgeable`, `saving`, `onMark`, `onJudge`, `saveError` |
| `components/ReviewExportSection.tsx` | Export mit `aria-describedby`, Sperrgrund, Inhalt, Fehler, Abbruch-Fehler | `status`, `exportPending`, `exportError`, `onExport`, `cancelError`, `onRetryCancel` |

Unverändert: ungültiges `?foto=` wird ohne Serverrunde und ohne neuen Verlaufseintrag ersetzt,
Fallansicht ohne Foto-Link, vier Urteile in fester Reihenfolge, Sperren und ein Request je Urteil,
Fokus auf die Fotoüberschrift bei Pfeiltasten, Sprung zum nächsten offenen Fall desselben Fotos,
gesperrter Export mit benanntem Grund.

#### `pages/ProjectStatsPage.tsx` (457 Zeilen)

| Baustein | Verantwortung | Props |
|---|---|---|
| `components/ProjectStatsContent.tsx` | die fünf Abschnitte in fester Reihenfolge, danach `FeedbackDiagnosisSection` | `stats` |
| `components/StatsScopeSection.tsx` | „Umfang und Speicher" | `stats` |
| `components/StatsCostSection.tsx` | „Kosten für Remote-Berechnungen" mit `CostEntry`/`IncompleteHint` | `cost` |
| `components/StatsProgressSection.tsx` | „Bearbeitungs- und Bewertungsstand" | `progress`, `ratings`, `total` |
| `components/StatsMotifsSection.tsx` | „Motivverteilung" | `stats` |
| `components/StatsDiagnosticsSection.tsx` | „Vertrauen und Fehlersuche" | `stats` |
| `components/StatsInfoPopover.tsx` | Info-Auslöser (44 px Trefferfläche) | `label`, `children` |
| `utils/statsLabels.ts` | `PURPOSE_LABELS`, `COST_PURPOSE_LABELS` | — |

Unverändert: Abschnittsreihenfolge (Rückmeldung hinter „Vertrauen und Fehlersuche"),
`data-purpose`/`data-motif-key`, dauerhaft sichtbare Zählweisen-Sätze, kein Bedienelement außer den
Info-Auslösern, genau eine Abfrage, `0 MB`/„nicht ermittelbar" bei `null`, kein Prozentwert ohne
beurteiltes Foto.

#### `pages/pipeline/AusschussStepPage.tsx` (749 Zeilen)

| Baustein | Verantwortung | Props |
|---|---|---|
| `utils/ausschussTexts.ts` | die vier Textkonstanten — je einmal | — |
| `components/AusschussDecisionLine.tsx` | Entscheidungswort, `ENTSCHEIDUNG_SCHRIFT`, `Entscheidungshinweise` | `decision`, `reason`, `decisionEffective`, `keepPossible` |
| `components/AusschussTile.tsx` | eine Kachel: `<li>`, Bildfläche als `<button data-testid="ausschuss-image">`, Grund, Entscheidungszeile, Dateiname | `entry`, `width`, `height`, `onOpen` |
| `components/AusschussOverview.tsx` | Filterzeile + Rückweg, Skeleton, Fehler, Leertext, Raster `data-ausschuss-grid`, „Mehr laden" + Zähler | `autoFilter`, `loading`, `error`, `empty`, `entries`, `total`, `hasNextPage`, `isFetchingNextPage`, `gridRef`, `tiles`, `projectId`, `onOpen`, `onLoadMore`, `onRetry`, `onShowAll` |
| `components/AusschussDetail.tsx` | Detailansicht (`?photo=`): Großbild, Entscheidung, Wege, Esc | `projectId`, `photoId`, `onClose` |
| `components/AusschussRecognition.tsx` | Einleitung, „Erneut erkennen", Auslösefehler, Vorschlagszahl, Auto-Zähler, Gate-Zeitpunkt, Fehlschlag | `rerun`, `onRerun`, `busy`, `triggerError`, `scoringStatus`, `suggestionsFoundText`, `autoDecidedGroupCount`, `gateConfirmedAt`, `errorMessage` |
| `components/AusschussActionBar.tsx` | Statuspunkt + Text, Fortschritt, Hauptaktion, Abbruch | `action`, `statusDot`, `statusText`, `photosProcessed`, `photosTotal`, `onAction`, `busy`, `onCancel`, `cancelRequested`, `cancelPending`, `cancelFocusToken` |

Unverändert: `?photo=` als Push (Browser-Zurück = Übersicht), Esc schließt nur die montierte
Detailansicht, `?auto=1` samt Rückweg an der Stelle des Zählers, Bestand erst nach erfolgreichem
Lauf, genau ein Auslöser je Lauf, „Mehr laden" + `aria-live`-Zähler, Leiste auch in der
Detailansicht, benannter Zustand bei fehlender Aufnahme, nicht-numerischer `photo`-Parameter führt
in die Übersicht.

### Tests, die die Unverändert-Zusage tragen

Die Seiten-Tests bleiben in jeder Erwartung an sichtbares Verhalten unangetastet. Zulässig sind nur
der Importpfad einer verschobenen Textkonstante (Duplikat: `utils/duplicateTexts.ts`, Ausschuss:
`utils/ausschussTexts.ts`; kein Re-Export aus der Seite) und die Dateilisten der
Struktur-Verträge oben.

| Seite | tragende Testdateien |
|---|---|
| Album-Entwurf | `AlbumDraftPage.editing.test.tsx`, `.band.test.tsx`, `.lightbox.test.tsx`, `.persons.test.tsx` |
| Bilddetail | `PhotoDetailPage.navigation.test.tsx`, `.persons.test.tsx`, `.assessment.test.tsx`, `.motifs.test.tsx`, `.completeness.test.tsx` |
| Duplikatvergleich | `DuplicateComparePage.test.tsx` |
| Klassifizierungsprüfung | `ClassificationReviewDetailPage.test.tsx` |
| Statistik | `ProjectStatsPage.test.tsx` |
| Ausschuss | `AusschussStepPage.test.tsx` |

Die Browser-Specs unter `e2e/tests/` (Geometrie, Scrollen, Trefferflächen) bleiben ebenfalls
unverändert. Die Sichtprüfung vor dem Pull Request deckt je Seite in 360 px und Desktop ab, was
keine Testebene sieht: Lage der mitlaufenden Leisten und der Bühne, Umbruch und Trefferflächen, kein
waagerechtes Scrollen, keine verschwundene Fläche.

### Oberflächenkommentare: was bleibt, was entfällt

Bleiben darf jeder Kommentar mit einer Anzeige- oder Bedienregel — warum die Oberfläche etwas so
zeigt, ordnet, sperrt, fokussiert oder weglässt. Entfallen muss jeder Kommentar, dessen einzige
Aussage eine Serverzusage ist, die nach Abschnitt 6 jetzt am Feld steht, und dessen Entfernen keine
Entscheidung der Oberfläche unerklärt lässt. Prüffrage: Wüsste ein Leser ohne diesen Satz, warum der
Code hier so aussieht?

Entfallen (Serveraussage wandert an Feld bzw. Route): `AusschussStepPage.tsx` (Bedingung ist der
Serverwert `keep_possible`, nicht aus `reason` abgeleitet — die Anzeige-Regel „nur wo der Serverwert
es erlaubt" bleibt), `PhotoDetailPage.tsx` (Server liefert `suggestion` bereits `null`; die
Anzeige-Regel „eigene Bewertung hat Vorrang" bleibt), `AlbumDraftPage.tsx` (Einfügen ist idempotent;
warum `insert` mitgeht, bleibt), `ClassificationReviewDetailPage.tsx` (während des Laufs keine
Fälle; die Regel für eine fehlgeschlagene Prüfung bleibt). Kein Kommentar wird beim Umzug
umformuliert, außer in genau diesen Fällen.

### Bezug zum Design-System

Die Zerlegung führt kein neues visuelles Muster ein: Sie komponiert aus `ui/button`, `ui/alert`,
`ui/progress`, `ui/skeleton`, `ui/popover`, `StatusTag`, `StatusDot`, `Icon`, `StepActionBar`,
`PhotoImage`, `Section`/`Metric`/`MetricRow`/`DetailRow`. Skeleton statt Spinner, `Alert` mit
„Erneut versuchen" inline, sichtbare Leerzustands-Sätze, `aria-live` für Fortschritt, Rückmeldung
ohne Dialog, Trefferflächen 32/44 px, genau eine Fokusregel, keine neue Bewegung, kein neuer
Farb-, Typo-, Abstands- oder Radiuswert. `specs/architecture/0004-design-system.md` bleibt
unverändert; die Zerlegung ist der Anwendungsfall der Selektor-Stabilität aus
`specs/architecture/0002-testkonzept.md`.

### Offene Risiken der Zerlegung

1. **Gemeinsame Zustandsführung:** Sperren, Fehlerplätze, Rückgängig-Ziel und Fokuswunsch bleiben
   Seitenzustand; zwei Wahrheiten zeigen sich als dauerhaft gesperrte Kachel oder fremdes
   Rückgängig.
2. **Ref-Identität:** neu erzeugte Ref-Objekte brechen `useDraftPosition`, Fokus-Effekte und
   Breitenmessung still.
3. **Fokus über Komponentengrenzen:** `data-focus-key` wird über den Wurzelknoten gesucht; der
   Baustein darf das Ziel nicht im selben Render aushängen.
4. **DOM-Struktur-Kopplung der Tests:** ein zusätzlicher Wrapper bricht `within`,
   `compareDocumentPosition` und `not.toContainElement`.
5. **Stabile Elemente über Renders hinweg:** `duplicate-last-group` und Skeleton ↔ Raster bleiben
   dasselbe Element an derselben Stelle.
6. **`id`- und Label-Kopplungen:** `verdict-heading`, `motifs-heading`, `review-photo-title`,
   `day-panel-*`, `aria-labelledby`/`aria-controls` — ein doppelter oder verlorener `id` fällt in
   jsdom nicht auf.
7. **Mess-Hooks:** `useElementWidth` bleibt für Skeleton und Raster eine Instanz.
8. **Wortlaute** wandern zeichengleich, ihre Definition bleibt genau einmal.

## Security

**Einordnung: sicherheitsrelevant, eng begrenzt.** Keine Änderung an Authentifizierung,
Berechtigung, Endpunkt, Antwortfeld oder Datensichtbarkeit zwischen den beiden Nutzern. Zwei
Punkte tragen Auflagen: das dauerhaft veröffentlichte Artefakt und die eine Stelle, die
Request-URLs baut.

### Das Artefakt stammt ausschließlich aus dem Quelltext

Gültig für `backend/openapi.json`: Es entsteht ausschließlich aus `create_app().openapi()` im
Arbeitsbaum, nie aus einer laufenden Instanz und nie durch Handbearbeitung. Eine URL-Quelle machte
den Bau von einem fremden Dokument abhängig und brächte fremden Beschreibungstext ins Repository.
Der Erzeuger läuft ohne Datenbank und ohne Redis; es gibt keinen Anlass, ihn gegen eine
Produktivinstanz zu richten. Der Inhalt ist derselbe, den `GET /openapi.json` heute tokenlos
ausliefert; neu ist nur die dauerhafte Ablage im öffentlichen Repository.

### Beschreibungstext ist Veröffentlichung

Gültig für jeden Docstring und jedes `Field(description=…)`, das in die Beschreibung gelangt:
Beschrieben wird Verhalten an der HTTP-Grenze (Statuscodes, Feldwirkung, `null`-Semantik,
„`queued` heißt angenommen, aber nicht begonnen"). Nicht hinein gehören Werte aus `settings` oder
Umgebungsvariablen, Hosts, Ports, Volume-Pfade, Container-Namen und personenbezogene Daten;
`Field(examples=…)` trägt nur erkennbar synthetische Werte. Bei Verletzung landet der Wert in einer
eingecheckten Datei und ist im Diff sichtbar.

Wächter: ein Test setzt Sentinel-Werte für alle geheimnis- und infrastrukturtragenden
Settings-Felder (`secret_key`, `opencloud_base_url`/`_username`/`_app_token`,
`anthropic_api_key`, `database_url`, `redis_url`, `auth_seed_user1/2_password`), baut
`create_app().openapi()` und verlangt, dass die serialisierte Beschreibung keinen dieser Werte
enthält; zusätzlich fehlt `servers` oder nennt nur `"/"`.

### `apiFetch` ist die eine URL-Baustelle

Der Antworttyp aus `paths[Endpunkt][Methode]` ist eine Typaussage, keine Laufzeitzusicherung; die
Grenze bleibt die Servervalidierung. Zwei Zusagen müssen in `apiFetch`/`apiFetchBlob` stehen, sonst
geht eine heute vorhandene Eigenschaft verloren:

- Jeder Pfadparameter wird mit `encodeURIComponent(String(value))` kodiert; die Endpunktvorlage
  ist ein Literal aus `paths`, nie Aufrufertext. Ganzzahlig typisierte Parameter werden als ganze
  Zahl kanonisiert. Ungeprüft wäre ein `/`, `?`, `#` oder `..` im Wert ein anderes Request-Ziel.
- Query-Werte gehen über `URLSearchParams` (Liste als wiederholter Schlüssel, `undefined` entfällt,
  Boolean als `true`/`false`), nie über Zeichenketten-Verkettung.

Der Sonderfall `/auth/login` bleibt ein exakter Vergleich der Endpunktvorlage, nie ein Präfix. Die
zweite `apiFetch`-Signatur für Modultests (`Promise<unknown>`) darf aus Produktivcode nicht
erreichbar sein — sonst ist die Typaussage an der Grenze still verloren.

### Unverändert

- Kein Endpunkt, keine Methode, kein `security`-Eintrag, kein Antwortfeld ändert sich; die vier
  Auslöser antworten weiter `{"status": "queued"}`, der Ausschuss-Abschluss `{"status":
  "confirmed"}`, die beiden Zählkarten behalten ihre Zweck-Schlüssel.
- `backend/openapi.json` wird zur Laufzeit von keiner Anwendungsstelle gelesen;
  `frontend/src/api/generated/schema.d.ts` ist reine Typinformation.
- Die Trennung der Nutzerdaten hängt an den Abfragen (`user_id` aus dem JWT-Claim), nicht an
  Typen.

### Dev-Abhängigkeit und erzeugte Datei

`openapi-typescript` ist exakt gepinnt, Bauzeit-Abhängigkeit ohne `install`/`postinstall`-Skript,
über `frontend/package-lock.json` festgeschrieben und von `npm ci` plus `npm audit signatures`
erfasst. Der Vergleich schreibt in eine temporäre Datei außerhalb von `src/` und räumt sie ab. Die
Ausnahme in `.prettierignore`/Oxlint ist Format- und Lint-Hygiene, keine Review-Ausnahme: Die
Datei ist nicht gitignoriert, ihr Diff ist Teil der Vertragsprüfung.

### Binäre Endpunkte

`response_class` dokumentiert den Antworttyp; es ersetzt nicht das ausdrücklich gebaute
`Response`/`FileResponse`-Objekt. Die Handler behalten ihre festen Media-Types und
Sicherheitskopfzeilen (`X-Content-Type-Options: nosniff`, `Cache-Control: no-store`,
`Content-Disposition`). Für `GET /photos/{photo_id}/image` fehlt heute ein Kopfzeilen-Test; er wird
in diesem Feature angelegt.

`specs/architecture/0003-securitykonzept.md` wird um die Angriffsfläche
„Schnittstellenbeschreibung als veröffentlichtes Artefakt" samt Ankerzeilen für beide Zusagen
ergänzt.

## Teststrategie

### Was die Zusage trägt

Gegenstand ist ein erzeugtes Artefakt und eine Typkette, kein neues Verhalten. Keine einzelne
Ebene trägt eine der sieben Zusagen allein; tragend ist die Kette aus drei Prüfungen (ADR 0153
Abschnitt 3), umstellt von einem statischen Wächter und den unveränderten Seiten-Tests.

| Ebene | Was sie prüft | Ort | Kriterium |
|---|---|---|---|
| Backend-pytest | eingechecktes Artefakt gegen `create_app().openapi()`; benannte 2xx-Antworten; Vokabulare; Beschreibungen; Binärantworten; Erzeuger-Skript; Veröffentlichungs-Sentinel | `backend/tests/test_openapi_vertrag.py`, `test_openapi_ohne_geheimnisse.py`, `test_export_openapi_skript.py`, `test_api_binary_responses.py` | 1, 3, 4, 5 |
| `api:check` (in `typecheck`) | `schema.d.ts` ist aus dem Artefakt erzeugt, byte-gleich | `frontend/package.json` | 1 |
| `tsc` | jede Aufruf- und Anzeigestelle gegen den nachgeführten Typ; `@ts-expect-error`-Proben für die Grenze | `npm run typecheck` | 1, 2, 3, 4, 6 |
| Frontend-vitest | Laufzeit der Aufrufgrenze (Pfadkodierung, Query, 204, 401), Aufrufform der API-Module | `api/client.test.ts`, `api/*.test.ts` | 6 |
| scripts/tests-Wächter | `types.ts`-Invarianten, Aufruf ohne Typargument, Verdrahtung von `api:check` | `scripts/tests/test_frontend_typen.py` | 2, 4, 6 |
| e2e | unverändert: Geometrie, Scrollen, Trefferflächen der sechs Seiten | `e2e/tests/**` | 7 (Teil) |
| Sichtprüfung | was keine Testebene sieht | PR-Beleg | 7 (Rest) |

Alle Prüfebenen sind blockierend: `backend`, `frontend` und `demo-scripts` sind geforderte
Kontexte der CI; `demo-scripts` führt `scripts/tests` aus, `frontend` ruft `npm run typecheck`
(und damit `api:check`) vor `tsc`. Ein neuer CI-Job und eine Änderung an `scripts/check.sh`
entstehen nicht.

### Das Artefakt: `backend/tests/test_openapi_vertrag.py`

Der Kern ist eine reine Funktion `vergleiche(soll, ist) -> Befunde`, die der Test mit dem
eingecheckten JSON und `create_app().openapi()` aufruft. Verglichen werden **geparste Strukturen**,
nicht Bytes: die Schlüsselreihenfolge der Datei ist Form, nicht Vertrag. Bei Abweichung nennt der
Befund den Ort in Punktnotation (`components.schemas.ScanSummary.properties.photos_added`,
`paths./projects/{project_id}/scan.post.responses.200`) und beide Nachführbefehle wörtlich
(`backend/scripts/export_openapi.py`, danach `npm --prefix frontend run api:generate`).

**Die Meldung ist selbst getestet** — sonst degradiert sie still: synthetische Soll/Ist-Paare für
Feld umbenannt, Feld entfernt, Enum-Wert ergänzt, Pfad/Status ergänzt; je Fall müssen Ort und
Nachführschritt im Text stehen. Dieselbe Datei prüft weiter, ohne Ausnahmeliste: jede 2xx-Antwort
mit `application/json` ist ein `$ref` (oder ein Array davon); die benannten Antworten aus
Abschnitt 7 sind vorhanden; `CancelOutcome` ist ein geschlossenes Enum mit zwei Werten; die beiden
Zählkarten sind feste Modelle mit den vier Zwecken (kein `additionalProperties`); die drei
Binärendpunkte führen keinen `application/json`-Körper; `ScanStatus` und `ExportRunStatus` sind
zwei benannte Schemata mit den richtigen Referenzen; je Paar aus fester Liste ist eine nicht-leere
Beschreibung mit dem tragenden Stichwort vorhanden (`null`, `queued`, `success`) — Anwesenheit,
kein Satzvergleich.

### Der Erzeuger: `backend/tests/test_export_openapi_skript.py`

Das Skript läuft als Subprozess mit geleertem Umfeld (kein `SECRET_KEY`, kein
`RATE_LIMIT_STORAGE_URI`, kein `DATABASE_URL`/`REDIS_URL`) und endet mit 0 — nur so ist belegt,
dass es seine Vorgaben selbst setzt und ohne DB/Redis läuft. Es schreibt über ein Zielargument in
ein temporäres Verzeichnis (Vorgabe `backend/openapi.json`), damit der Test nie in den Arbeitsbaum
schreibt; zwei Läufe sind byte-gleich. Die kanonische Form ist geprüft: zwei Leerzeichen, sortierte
Schlüssel, UTF-8 mit literalen Umlauten, abschließender Zeilenumbruch.

### Die Veröffentlichung: `backend/tests/test_openapi_ohne_geheimnisse.py`

Sentinel-Werte für alle geheimnis- und infrastrukturtragenden `Settings`-Felder, danach
`create_app().openapi()` bauen und die serialisierte Beschreibung prüfen: keiner der Werte kommt
vor, `servers` fehlt oder nennt nur `"/"`.

### Die Aufrufgrenze: `frontend/src/api/client.test.ts`

Laufzeitfälle (die bisherigen bleiben in ihrer Aussage unverändert, nur die Aufrufform folgt der
Endpunktvorlage): Pfadparameter werden mit `encodeURIComponent(String(value))` kodiert (`a/b` →
`a%2Fb`, `../x` → `..%2Fx`, ebenso `?`, `#`, Leerzeichen), ganzzahlige Werte erscheinen kanonisch;
Query-Werte über `URLSearchParams` (Liste als wiederholter Schlüssel, `undefined` entfällt,
Boolean als `true`/`false`); `204` → `undefined`, `ApiError`-Abbildung, 401-Verhalten unverändert,
`/auth/login` exakter Vergleich; `apiFetchBlob` nimmt dieselbe Vorlagenform.

Typgrenze als `@ts-expect-error`-Proben (laufen über `tsc`, nicht zur Laufzeit): konkreter Pfad,
fehlender Pfadparameter, `body` an einem Endpunkt ohne Körper, eine Methode, die der Endpunkt nicht
führt. Jede Probe schlägt fehl, sobald die Grenze aufgeweicht wird.

### Der Wächter: `scripts/tests/test_frontend_typen.py`

Reine Funktion `Bestand → Befunde`, Registrierung in `waechter_aussagen.json` und je Invariante eine
Mutation in `mutationen.py` (Mechanik aus Spec 0652/ADR 0148). Invarianten:

| Invariante | Aussage | Klasse |
|---|---|---|
| `keine-interface-deklaration` | `api/types.ts` enthält kein `interface` | B |
| `marken-einmalig` | beide Abschnittsmarker kommen genau einmal vor | B |
| `marken-in-reihenfolge` | „Erzeugt" steht vor „Oberflächen-eigen"; jede Deklaration liegt unter einem Marker | B |
| `schemabezug-belegt` | jeder `components["schemas"]["X"]`-Bezug nennt einen Schemanamen aus `backend/openapi.json` | A |
| `keine-zweite-fassung` | `frontend/src/api/*.ts` außer `types.ts`, `client.ts` und `generated/` deklariert keinen Typ | B |
| `aufruf-ohne-typargument` | kein `apiFetch<`/`apiFetchBlob<`, kein `as any`/`as unknown` in Produktivquellen unter `frontend/src` | B |
| `beschreibung-am-typ` | je Paar (Schema, Feld) steht der whitespace-normalisierte Beschreibungstext des Artefakts in `schema.d.ts` | A |
| `nachfuehrung-verdrahtet` | `frontend/package.json`: `typecheck` ruft `api:check` **vor** `tsc` | B |

Der Wächter ist selbstgeschützt: fehlt `backend/openapi.json` oder läuft die Dateimenge leer, ist
das ein Befund. Er liest ausschließlich Dateien — kein Backend-Import, kein Netz —, damit er im
`demo-scripts`-Job ohne Backend-Abhängigkeiten läuft.

### Tragende Edge Cases

1. Umbenanntes Feld (nicht nur ergänzt) — der Normalfall der Kette.
2. Nur `description` geändert — ebenfalls Vertragsänderung, die Beschreibung ist veröffentlichter
   Text.
3. Einseitig ergänzter Enum-Wert (`ExportRunStatus` ohne `ScanStatus`) — der einzige Fall, der die
   Vokabulartrennung sichtbar macht.
4. Neuer Pfad, neuer Statuscode, geänderte `required`-Liste.
5. Unbenanntes 2xx-JSON-Objekt (künftiger Auslöser ohne `response_model`).
6. `204` und Binärantworten ohne behaupteten JSON-Körper.
7. Generator-Drift ohne Vertragsänderung → `api:check` rot.
8. Pfad-/Query-Werte mit `/`, `?`, `#`, Leerzeichen, `../x`; Liste, `undefined`, Boolean.
9. 401-Behandlung und `/auth/login` als exakter Vergleich.
10. Artefakt-Determinismus und UTF-8; leeres Umfeld des Erzeugers.
11. Sentinel-Geheimnisse und `servers` in der veröffentlichten Beschreibung.
12. Fixture-Bruch: `frontend/src/test/fixtures.ts` typisiert `ProjectOut`; ein Feldrename bricht
    dort und in der Anzeigestelle — der gewollte weite Rot-Ausschlag der Kette.
13. Knotenmengen-Gleichheit samt Ausgang je Seiten-Testdatei.

### Der Rot-Grün-Nachweis im Pull Request

Abfolge am selben Arbeitsstand, mit Befehl, Exitcode und erster Meldungszeile:

- **Ausgangslage:** `pytest backend/tests/test_openapi_vertrag.py` und
  `npm --prefix frontend run typecheck` laufen ohne Vertragsänderung durch.
- **(a) Vertrag geändert, Artefakt nicht:** ein Feld an einer Antwortstruktur umbenennen → der
  Backend-Test nennt `components.schemas.…` und beide Nachführbefehle.
- **(b) Artefakt nachgeführt, Typen nicht:** `python backend/scripts/export_openapi.py` laufen
  lassen, `schema.d.ts` unangetastet → `api:check` nennt Datei und `npm run api:generate`.
- **(c) Typen nachgeführt, Aufrufstelle nicht:** `npm --prefix frontend run api:generate`, dann
  `tsc` → rot an der betroffenen Aufruf- oder Anzeigestelle, nicht in `schema.d.ts`.
- **(d) Alles nachgeführt:** alle drei Schritte grün.
- **Rot-Nachweis 2 (Vokabulare):** `ExportRunStatus` befristet um einen Wert erweitern, Artefakt
  und Typen nachführen → `tsc` wird an `isActive(data?.last_export_run?.status)` rot, die
  `Record<ScanStatusLabel, …>`-Abbildung bleibt grün. Zurücknehmen. Dies ist der einzige Beleg für
  Kriterium 4.
- **Rot-Nachweis 3 (Wächter):** `test_waechter_mutationen.py` bricht jede Invariante einmal ein und
  formuliert sie einmal um.

### Seiten-Aufteilung: Nachweis ohne Rot-Grün

Die Zerlegung hat keinen Rot-Zustand. An seine Stelle tritt der Vorher-Nachher-Vergleich aus
`specs/architecture/0002-testkonzept.md`, begrenzt auf die 13 Seiten-Testdateien:

- Kein Testdiff außer dem Importpfad einer verschobenen Textkonstante; keine Erwartung an
  sichtbares Verhalten ändert sich.
- Identische Testknoten-Menge mit identischem Ausgang je Datei (vitest `--reporter=json`); das
  Frontend hat keine Coverage-Konfiguration, Größen (1) und (2) des Vergleichs tragen allein.
- Struktur-Verträge ziehen nur um (Abschnitt 8). Ein vergessener Eintrag meldet sich als verwaiste
  Freigabe; ein zusätzlicher Wrapper bricht `within`/`compareDocumentPosition`.
- e2e unverändert; je Seite ein Screenshotpaar in 360 px und Desktop.
- Die sieben Risiken der Zerlegung werden im PR je einer deckenden Zusicherung zugeordnet oder als
  Sichtprüfpunkt geführt.

### Was bewusst nicht automatisiert wird

Sichtprüfung (Layout), die Beurteilung „dieser Kommentar trägt nur eine Serverregel", die Liste der
verbleibenden eigenen Typen und der Vollzug des Rot-Grün-Nachweises selbst. Diese vier stehen als
benannte Belegpunkte im PR; sie gelten nicht als erfüllt, weil ein Test grün ist.

`specs/architecture/0002-testkonzept.md` wird um den Abschnitt „Vertragsartefakt und
Nachführkette (OpenAPI → erzeugte Typen → tsc)" ergänzt (Muster, Grenze ohne Python/DB,
Wächterumfang, Nachweis ohne Rot-Grün für die Seiten-Aufteilung).

## Entscheidungen

- **Vier unbenannte Auslöse-Antworten → benannte Struktur im Server.** Der Server ist unsere eigene
  Quelle; ein `Literal["queued"]` ist präziser als eine Oberflächen-Ableitung von `string`.
  Ebenfalls benannt: `confirm-ausschuss-gate` und `/health`, damit der Wächter „jede
  2xx-JSON-Antwort ist benannt" ohne Ausnahmeliste auskommt. JSON-Körper unverändert.
- **Feld am Export-Detail → aus der Oberfläche entfernen, Server bleibt.** Keine Stelle liest
  `cancel_requested_at` vom Detail; der Abbruchmerker gehört zum Polling-Zustand
  `ExportRunSummary`. Keine Serveränderung.
- **Status-Wortschatz des Exportlaufs → `ExportRunStatus`, nicht `ScanStatus`.** Die beiden
  Wertevorräte sind heute gleich, deshalb bleibt der Bestand grün; sobald einer einen Wert erhält,
  wird die Vermischung zum Typfehler.
- **Mechanische Nachzüge in API-Modultests sind Teil der Änderung.** Die Module prüfen den an
  `apiFetch` weitergereichten Aufruf; mit Endpunktvorlagen ändert sich dessen Form, nicht die
  Zusicherung. Seitentests bleiben unangetastet — sie prüfen sichtbares Verhalten.
- **`openapi-typescript` als Dev-Abhängigkeit, eingechecktes Artefakt, `api:check` in
  `typecheck`:** Werkzeug der Erzeugung, kein Produktverhalten, kein neuer Required-Check.
- **architect konsultiert (Schritt 1):** generierter Vertrag, Client-Form, Nachführkette und
  Seiten-Aufteilung sind Architekturentscheidungen; Ergebnis in ADR 0153.
- **ux-ui-designer konsultiert (Schritt 2):** sechs sichtbare Seiten mit Direktlink- und
  Fokusverhalten.
- **security-engineer konsultiert (Schritt 3):** neue dauerhafte Veröffentlichungsfläche
  (eingecheckte Beschreibung) und neue einzige URL-Baustelle.
- **test-engineer konsultiert (Schritt 3):** die Zusagen sind nur über Rot-Grün-Nachweise und
  Struktur-Verträge prüfbar.

## Offene Fragen

Keine.

## Out of Scope

- Neues Frontend-Verhalten, neue Seiten, neue Endpunkte.
- Die Tests unter `backend/tests` und `frontend/src` jenseits der Importquelle für Typen; die
  mechanischen Nachzüge der API-Modultests (Aufrufform) sind davon ausgenommen, weil sie ohne
  Typverlust sonst nicht kompilieren.
