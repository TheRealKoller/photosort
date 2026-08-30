# 0218 - Remote-Kategorisierung auf die Kriterien-Bewertungsseite verschieben

**Status:** Accepted
**Erstellt:** 2026-08-30
**Bezug:** [GitHub-Issue #218](https://github.com/TheRealKoller/photosort/issues/218) (Refinement bereits vor dieser Spec-Erstellung abgeschlossen)

## Ziel

Daniel nutzt im Pipeline-Workflow den Schritt "Kriterien-Bewertung", um Fotos lokal bewerten zu lassen, und den Schritt "Kuratierung", um Kategorien zuzuweisen. Die Remote-Kategorisierung (Cloud-Vision-Vorschläge für Kategorien) wird heute auf der Kuratierungsseite ausgelöst, obwohl ihre Ergebnisse fachlich erst durch die Kriterien-Bewertung eingearbeitet werden. Diesen Bruch zwischen Auslösung und Wirkung hat Daniel konkret als störend erlebt: Für einen fachlich zusammenhängenden Vorgang muss zwischen zwei getrennten Seiten hin- und hergesprungen werden. Ziel ist, die Remote-Kategorisierung dorthin zu verschieben, wo sie fachlich hingehört — auf die Kriterien-Bewertungsseite.

## User Story

Als Betreiber der PhotoSort-Installation möchte ich die Remote-Kategorisierung (Auslösen und Ergebnisse einsehen) auf derselben Seite wie die Kriterien-Bewertung vorfinden, damit ich Auslösung und Einarbeitung der Ergebnisse in einem zusammenhängenden Workflow erledige, statt zwischen zwei getrennten Seiten hin- und herzuspringen.

## Akzeptanzkriterien

- [ ] Die Remote-Kategorisierung (Auslösen inkl. Kostenschätzung, Ergebnisanzeige, Möglichkeit einzelne erkannte Kategorien abzulehnen/zu modifizieren) ist auf der Kriterien-Bewertungsseite verfügbar — funktional identisch zur bisherigen Kuratierungsseiten-Einbindung, keine neue Verhaltensvariante.
- [ ] Die Remote-Kategorisierung ist nicht mehr auf der Kuratierungsseite verfügbar (kein doppeltes Vorhalten an zwei Stellen).
- [ ] Die bestehende Kostenschätzungs-Bestätigung vor Auslösung der Remote-Kategorisierung bleibt unverändert erhalten.
- [ ] Nach einem Remote-Kategorisierungs-Lauf ist auf derselben Seite erkennbar, dass die Ergebnisse erst durch einen (ggf. erneuten) Kriterien-Bewertungs-Lauf in die Kategorie-Vorschläge einfließen — ein Hinweistext ist ausschließlich sichtbar, wenn der letzte Lauf `status === 'success'` hat, nicht bei `running`, `failed` oder keinem Lauf.
- [ ] Die Kuratierungsseite bleibt weiterhin für das eigentliche Zuweisen/Übernehmen von Kategorien zuständig (Scope-Grenze: nur die Remote-Kategorisierung selbst zieht um, nicht die Kategorie-Kuratierung — die Kandidaten-/Override-Mechanik auf Foto-Kacheln/`PhotoDetailPage` bleibt unverändert).

## Datenmodell-Bezug

Keine Änderung. Reine Frontend-Verschiebung, kein Backend-/Datenmodell-Eingriff.

## Architektur / Umsetzung

`architect`-Konsultation, 2026-08-30. Gewählter Ansatz: reine Verschiebung einer bereits selbstständigen, prop-getriebenen Komponente zwischen zwei Geschwister-Routen derselben Pipeline — kein neues Muster, kein neuer Datenfluss, kein Backend-Eingriff.

`RemoteCategoryClassificationSection` (`frontend/src/components/RemoteCategoryClassificationSection.tsx`) ist bereits vollständig entkoppelt von der Seite, die sie einbindet: sie erhält nur `project: ProjectOut` und `refetchProject: () => unknown` als Props und zieht sich alle weiteren Daten selbst über `useClassifyCategoriesRemoteEstimateQuery`/`useTriggerClassifyCategoriesRemoteMutation` (`hooks/useProjects.ts`, projekt-ID-basiert, seitenunabhängig). `KriterienStepPage.tsx` und `KuratierungStepPage.tsx` beziehen `project`/`refetchProject` beide bereits identisch aus `useOutletContext<PipelineOutletContext>()` (`ProjectPipelineLayout.tsx`). Die Verschiebung ist damit ein reiner Aufrufort-Wechsel derselben Props an dieselbe Komponente — kein neuer Zustand muss zwischen Seiten geteilt werden, keine neue Abstraktion nötig.

**Betroffene Dateien:**
- `frontend/src/pages/pipeline/KriterienStepPage.tsx` — Import von `RemoteCategoryClassificationSection` ergänzen, Einbindung **nach** der bestehenden "Kriterien-Bewertung"-Sektion; veralteten Docstring-Kommentar zur bisherigen Seiten-Zusammensetzung aktualisieren.
- `frontend/src/pages/pipeline/KuratierungStepPage.tsx` — JSX-Zeile + jetzt ungenutzten Import entfernen; Docstring-Kommentar entsprechend anpassen. Rest der Datei (Top-N-Eingabe, Link zur Kuratierungsansicht) bleibt unverändert (AC5).
- `frontend/src/components/RemoteCategoryClassificationSection.tsx` — neuer Hinweistext für AC4.
- Tests: `RemoteCategoryClassificationSection.test.tsx`, `KriterienStepPage.test.tsx`, `KuratierungStepPage.test.tsx` (siehe Teststrategie).

**Kein Backend-Eingriff:** Sämtliche vier Endpunkte (`GET .../classify-categories-remote/estimate`, `POST .../classify-categories-remote`, `PUT`/`DELETE /photos/{id}/category-override`) sowie `ProjectOut.last_remote_category_classification_run`/`.cloud_vision_detection_enabled` bleiben unverändert — sie sind nie an eine bestimmte Frontend-Route gebunden gewesen.

**Entwurfsentscheidungen:**
1. **Reihenfolge auf der Seite:** Kriterien-Bewertung zuerst, Remote-Kategorisierung darunter — spiegelt den tatsächlichen fachlichen Ablauf (erst lokal bewerten, optional remote anreichern, danach ggf. erneut lokal bewerten, um die Anreicherung einzuarbeiten).
2. **AC4-Hinweistext:** sichtbar wenn `run !== null && runStatus === 'success'`, Text: "Diese Ergebnisse fließen erst durch einen (ggf. erneuten) Kriterien-Bewertungs-Lauf in die Kategorie-Vorschläge ein." Bewusst **ohne** positionalen Verweis ("oben"/"unten"), damit die Komponente nicht implizit an ihre neue Position auf dieser einen Seite gekoppelt wird. Platzierung: direkt nach der Status-Zeile.
3. **Scope-Abgrenzung zur Kandidatenliste (Klarstellung, kein neuer Umsetzungsschritt):** Die in AC1 genannte "Möglichkeit einzelne erkannte Kategorien abzulehnen/zu modifizieren" ist die bereits bestehende, unabhängige Kandidaten-/Override-Mechanik (`CriterionDetailsList`/`CriterionDetailsPopover`, `PUT`/`DELETE /photos/{id}/category-override`), die auf Foto-Kacheln (Grid/Kuratierung) und `PhotoDetailPage.tsx` lebt — **nicht** Teil von `RemoteCategoryClassificationSection`. AC5 bestätigt das explizit. Diese Mechanik zieht **nicht** um.

**Umsetzungsreihenfolge (TDD):**
1. Test in `RemoteCategoryClassificationSection.test.tsx` für den neuen AC4-Hinweistext (present bei `status: 'success'`, absent bei `running`/`failed`/kein Lauf) → Implementierung.
2. `KriterienStepPage.test.tsx`: `beforeEach`-Mock für `getClassifyCategoriesRemoteEstimate` ergänzen (sonst schlägt der Query-Aufruf mit `undefined` fehl, siehe Teststrategie), Test für Vorhandensein/Reihenfolge der neuen Sektion → Verschiebung der JSX-Zeile + Import von `KuratierungStepPage.tsx` nach `KriterienStepPage.tsx`.
3. `KuratierungStepPage.test.tsx`: nicht mehr benötigten API-Mock entfernen, Negativ-Assertion (Sektion nicht mehr vorhanden) ergänzen — Regressionsschutz für AC2.
4. Voller Frontend-Check (`vitest`, `oxlint`, `tsc`).

**ADR-Bedarf:** Keine neue ADR nötig — reine UI-Verschiebung einer bereits bestehenden, selbstständigen Komponente ohne neue Technologie, ohne Datenmodell-Änderung, ohne neue externe Abhängigkeit.

**`docs/architecture.md`:** Keine Aktualisierung nötig — das Dokument beschreibt Systemarchitektur/Komponenten/Datenmodell, nicht die Zusammensetzung einzelner Frontend-Pipeline-Seiten.

## UI/UX

`ux-ui-designer`-Konsultation, 2026-08-30. Sichtbare Oberfläche: ja — reine Frontend-Komponenten-Verschiebung, keine neue Gestaltung außer dem AC4-Hinweistext.

**Layout nach der Verschiebung (`KriterienStepPage.tsx`):** zwei Sektionen untereinander — (1) Kriterien-Bewertungs-Sektion (bestehend: Heading, Erklärtext, Auslöse-Button, Status-Anzeige), (2) Remote-Kategorisierungs-Sektion (neu hier: Heading, Erklärtext, Auslöse-Button mit Kostenschätzungs-Dialog, Status-Anzeige mit Fortschrittsanzeige bei laufendem Prozess). Gleicher vertikaler Spacing-Stil wie bisher (`gap-3` intern, `gap-8` zwischen Sektionen).

**Zustände:** Die Komponente deckt bereits alle erforderlichen Zustände ab — Laden der Kostenschätzung (Button deaktiviert bis Schätzung/Fehler vorliegt), Busy-Button während des Laufs, natives Bestätigungsdialog-Element vor der kostenpflichtigen Aktion, Status-Anzeige (`StatusDot` + Text) für `running`/`success`/`failed`/kein Lauf mit Foto-Zähler + `<progress>` bei `running`, `Alert`-Banner mit optionalem `onRetry` bei Fehlern. Alle Muster bereits im Design-System dokumentiert, keine neuen.

**AC4-Hinweistext:** Text "Diese Ergebnisse fließen erst durch einen (ggf. erneuten) Kriterien-Bewertungs-Lauf in die Kategorie-Vorschläge ein.", sichtbar bei `runStatus === 'success'`, `className="text-sm text-text"` (konsistent mit bestehenden Erklärtexten), kein Alert-/Warning-Styling (neutrale Information, kein Fehler), Platzierung direkt nach der Status-Zeile.

**Design-System-Impact:** keiner — ausschließlich bereits dokumentierte, validierte Muster (Busy-Button, Bestätigungsdialog, Status-Semantik, Inline-Fehler). `specs/architecture/0004-design-system.md` bleibt unverändert.

## Security

`security-engineer` nicht konsultiert (Schritt 3): reine Verschiebung einer bestehenden, bereits abgesicherten UI-Komponente zwischen zwei Frontend-Seiten derselben Pipeline. Kein neuer externer Eingabekanal, keine Auth-/Berechtigungs-Änderung, keine Datenmodell-Änderung, keine veränderte Datensichtbarkeit zwischen den beiden Nutzern — alle vier betroffenen Endpunkte bleiben unverändert und bereits über `get_current_user` geschützt.

## Teststrategie

`test-engineer`-Konsultation, 2026-08-30. `specs/architecture/0002-testkonzept.md` unverändert — reine Verschiebung einer bereits etablierten, prop-getriebenen Komponente, kein neues externes System, kein neuer Testtyp.

**Unit-Ebene** (`RemoteCategoryClassificationSection.test.tsx`, Datei bleibt am Ort): neuer Testfall für den AC4-Hinweistext bei `runStatus === 'success'`; Negativ-Assertionen (`queryByText(...).not.toBeInTheDocument()`) in den bestehenden `running`/`failed`/kein-Lauf-Tests, damit der Hinweis nicht versehentlich in allen Zuständen erscheint.

**Integrations-Ebene** (`vitest` + Testing Library, bestehendes Seiten-Test-Muster):
- `KriterienStepPage.test.tsx`: **kritischer Umbauschritt** — `vi.mock('../../api/projects')` ist aktuell ein volles Auto-Mock ohne Rückgabewert für `getClassifyCategoriesRemoteEstimate`; TanStack Query wirft bei `undefined` aus der `queryFn` einen Fehler. Braucht einen expliziten `beforeEach`-Mock (analog dem bisherigen Muster in `KuratierungStepPage.test.tsx`) sowie ein zurückgesetztes `triggerClassifyCategoriesRemote`. Neue Tests: Sektion "Remote-Kategorisierung" vorhanden und erscheint nach der Kriterien-Bewertungs-Sektion; ein schlanker Smoke-Test (Schätzung laden → Dialog öffnen → bestätigen → Mutation aufgerufen) — die volle Verhaltensmatrix bleibt bei der Komponente. Zusätzlicher Regressionstest: Koexistenz beider Sektionen, Auslösen der einen darf Button/Zustand der anderen nicht beeinflussen.
- `KuratierungStepPage.test.tsx`: Mock-Override von `getClassifyCategoriesRemoteEstimate` sowie zugehöriger `beforeEach`-Teil entfernen, ungenutzten `api/projects`-Mock/Import streichen. Neuer Negativ-Test (AC2): Remote-Kategorisierung-Sektion nicht mehr im DOM.

**Was nicht neu getestet werden muss:** die Kandidaten-/Override-Mechanik (Foto-Kacheln/`PhotoDetailPage`) bleibt unverändert und unangetastet.

## Entscheidungen

- **architect konsultiert (Schritt 1):** konkreter Bezug zu bestehenden Frontend-Komponenten (`RemoteCategoryClassificationSection`, zwei Pipeline-Step-Seiten) — kein Skip möglich.
- **ux-ui-designer konsultiert (Schritt 2):** konkreter Bezug zu einer sichtbaren Oberfläche (Verschiebung zwischen zwei Seiten, neuer Hinweistext) — kein Skip möglich.
- **test-engineer konsultiert (Schritt 3):** konkretes, nicht-triviales zu testendes Verhalten (Komponentenverschiebung inkl. Mock-Umbau, neuer bedingter Hinweistext) — kein Skip möglich.
- **security-engineer nicht konsultiert (Schritt 3):** reine Verschiebung einer bestehenden UI-Komponente zwischen zwei Frontend-Seiten, kein neuer externer Eingabe-/Auth-/Datenmodell-Bezug, keine veränderte Datensichtbarkeit zwischen den beiden Nutzern.
- **Keine neue ADR:** reine UI-Verschiebung ohne neue Technologie, kein neues Architekturmuster.
- **`docs/architecture.md` unverändert:** betrifft keinen dort dokumentierten Abschnitt (Systemarchitektur/Datenmodell, nicht Frontend-Seiten-Zusammensetzung).

## Offene Fragen

Keine — das Refinement-Gespräch (Issue #218, Status `Ready`) sowie die technischen Konsultationen in dieser Spec haben alle Unklarheiten geklärt.

## Out of Scope

- Änderung der Kandidaten-/Override-Mechanik (Kategorien ablehnen/modifizieren auf Foto-Kacheln/`PhotoDetailPage`) — bleibt unverändert auf der Kuratierungsseite/den Foto-Kacheln (AC5).
- Jede Backend-/API-/Datenmodell-Änderung — reine Frontend-Verschiebung.
- Neue Gestaltung der `RemoteCategoryClassificationSection` selbst über den AC4-Hinweistext hinaus.
