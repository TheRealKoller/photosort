# 0030 - Scan-Statistik: Layout-Fix und Hilfetext für "Entfernt"/"Übersprungen"

**Status:** Implemented ([PR #97](https://github.com/TheRealKoller/photosort/pull/97))
**Erstellt:** 2026-08-09
**Bezug:** [`inbox/0008-statistiken-darstellung-unklar.md`](../inbox/0008-statistiken-darstellung-unklar.md), [`features/0005-minimal-project-frontend.md`](./0005-minimal-project-frontend.md), Idea-Sharpening-Gespräch mit Daniel am 2026-08-09

## Ziel

Auf der Projekt-Detailseite (`ProjectDetailPage.tsx`) werden nach einem Scan fünf Statistik-Werte angezeigt ("Hinzugefügt", "Aktualisiert", "Entfernt", "Übersprungen", "Dateien gefunden"). Zwei Probleme sind gemeldet: (1) Label und Wert stehen je nach Bildschirmbreite mal nebeneinander, mal in unterschiedlichen Zeilen — ein CSS-Grid-Bug, kein Zufall; (2) unklar bleibt, warum Dateien als "entfernt" oder "übersprungen" gezählt werden. Diese Spec behebt beides rein im Frontend: eine strukturelle Korrektur des Statistik-Grids sowie ein statischer, aufklappbarer Hilfetext an den zwei betroffenen Labels.

## User Story

Als Daniel bzw. seine Frau, der/die nach einem Scan die Projekt-Statistiken ansieht, möchte ich Label und Wert jedes Statistik-Eintrags zuverlässig zusammen sehen und bei Bedarf nachlesen können, was "Entfernt" und "Übersprungen" bedeuten, damit ich der Anzeige vertrauen und unerwartete Zahlen selbst einordnen kann, ohne Code oder Datenbank zu prüfen.

## Akzeptanzkriterien

- [ ] Die fünf Label/Wert-Paare in `ProjectDetailPage.tsx` (`<dl>`-Statistik-Block) sind so strukturiert, dass Label und zugehöriger Wert bei jeder Grid-Spaltenzahl (`grid-cols-2` mobil, `sm:grid-cols-3` ab Breakpoint) im selben DOM-Element gruppiert und damit immer sichtbar zusammenstehen — verifiziert durch DOM-Gruppierung (automatisiert) und visuellen Smoke-Test bei beiden Breakpoints (manuell).
- [ ] "Entfernt" und "Übersprungen" sind als natives `<details>/<summary>` gerendert, initial eingeklappt (kein `open`-Attribut). Klick/Tastaturaktivierung auf das Label togglet wiederholt zwischen ein- und ausgeklappt (nicht nur einmalig).
- [ ] Im aufgeklappten Zustand erscheint der feste Erklärungssatz:
  - "Entfernt" → "Datei wurde am Ursprungsort in OpenCloud nicht mehr gefunden und daher aus PhotoSort entfernt."
  - "Übersprungen" → "Dateiendung wird nicht unterstützt (unterstützt: JPG, PNG, HEIC, HEIF)."
- [ ] Die beiden `<details>`-Elemente togglen unabhängig voneinander (kein gemeinsames `name`-Attribut, kein exklusives Akkordeon-Verhalten).
- [ ] Der Hilfetext erscheint unabhängig vom Zahlenwert, auch wenn `photos_removed`/`files_skipped` gleich 0 sind (statisch, erklärt die Kategorie, nicht das Ergebnis des konkreten Laufs).
- [ ] Die übrigen drei Labels ("Hinzugefügt", "Aktualisiert", "Dateien gefunden") bleiben unverändert als reiner Text, ohne `<details>`-Vorfahren.
- [ ] Kein neues Datenmodell, keine Backend-Änderung, keine neue Abhängigkeit (kein Tooltip-Package) — explizit out-of-scope.

## Datenmodell-Bezug

Keine Änderung. Es werden ausschließlich die bereits vorhandenen `ScanRun`-Zähler (`photos_added`, `photos_updated`, `photos_removed`, `files_skipped`, `files_found`, siehe `backend/src/photosort/models.py:88-101`) unverändert angezeigt. Der Hilfetext ist ein statischer, fest im Frontend-Code hinterlegter String, keine aus der DB geladene Erklärung.

## Architektur / Umsetzung

**Ansatz:** Rein additive, strukturelle Markup-Änderung in `frontend/src/pages/ProjectDetailPage.tsx:334-347`, kein neues Muster, keine neue Abhängigkeit, kein Backend-Eingriff.

**Layout-Fix (Ursachenanalyse):** Der Bug ist strukturell, nicht rein visuell. Die `<dl>` rendert 5 Label/Wert-Paare als flache `dt,dd,dt,dd,...`-Folge (10 direkte Kind-Elemente). CSS-Grid verteilt diese 10 Items als einzelne Zellen auf die jeweilige Spaltenzahl. Bei `grid-cols-2` (mobil) funktioniert das nur zufällig, weil 10 durch 2 teilbar ist — jedes Paar füllt exakt eine Zeile. Bei `sm:grid-cols-3` ist 10 kein Vielfaches von 3, wodurch die Paare "außer Phase" geraten und Label/Wert in unterschiedlichen Zeilen landen können. Ein reiner CSS-Fix (z.B. andere Spaltenzahl) würde das Problem nur verschieben, nicht beheben — er träte bei jeder ungeraden Spaltenzahl oder einem künftigen 6. Zähler wieder auf.

**Fix:** Jedes Label/Wert-Paar wird in ein eigenes `<div className="flex gap-1">` gewrappt (`<dl><div><dt/><dd/></div>…</dl>` ist gültiges HTML5 — `dl` erlaubt entweder direkte `dt`/`dd`-Folgen oder eine Reihe von `div`s mit je einem Paar). Diese 5 Wrapper-`div`s sind dann die tatsächlichen Grid-Items; `grid-cols-2`/`sm:grid-cols-3` bleiben unverändert, verteilen jetzt aber vollständige Paare statt einzelner Zellen. Bei 5 Items auf 3 Spalten bleibt die letzte Zeile unvollständig (2 statt 3 Items), aber nie ein Label ohne zugehörigen Wert. Robust auch gegen einen künftigen 6. Zähler.

**Hilfetext:** Natives `<details>/<summary>` statt `title`-Attribut oder neuer Tooltip-Bibliothek (siehe UX-Begründung unten). `<summary>` ersetzt den bisherigen reinen Label-Text für "Entfernt"/"Übersprungen", der aufklappbare Inhalt ist ein `<p className="mt-1 text-xs text-text">` mit dem festen Erklärungssatz. Die übrigen drei Labels bleiben unverändert.

**Betroffene Dateien:** ausschließlich `frontend/src/pages/ProjectDetailPage.tsx` (Zeilen 334-347). Keine Backend-, keine Datenmodell-, keine `docs/architecture.md`-Änderung nötig.

**ADR nötig?** Nein. Beide Änderungen sind technische Details innerhalb bereits akzeptierter Grundsatzentscheidungen (Tailwind, siehe `decisions/0011-ui-component-library.md`), kein neues Datenmodell, keine neue Abhängigkeit, kein neues architekturelles Muster mit Tragweite über diese eine Ansicht hinaus.

## UI/UX

Design-System: [`architecture/0004-design-system.md`](../architecture/0004-design-system.md) — neues wiederverwendbares Muster "Statischer Hilfetext auf Label-Ebene" ergänzt (native `<details>/<summary>`), gilt als Vorlage für künftige einzelne, statische Erklärungen zu Datenpunkten.

- **Layout-Fix:** unproblematische strukturelle CSS-Korrektur eines bestehenden Musters, keine Designentscheidung — Ansatz des `architect` übernommen.
- **Warum `<details>/<summary>` statt `title`-Attribut:** Der ursprünglich erwogene Ansatz (natives `title` + `underline decoration-dotted cursor-help`, analog zu `CategoryBadge.tsx`) wurde verworfen — `title` ist auf Touchgeräten nicht zuverlässig auslösbar (die meisten mobilen Browser zeigen es beim Tap nicht an) und verletzt damit das Designprinzip "Touch- und Tastatur-gleichwertig" (PWA-Nutzung auf Mobilgeräten ist gleichrangig zur Desktop-Nutzung). Der `CategoryBadge`-Präzedenzfall ist nicht vergleichbar: dort ist `title` nur *Zusatz*info zu einem bereits verständlichen Kürzel, hier wäre `title` der *einzige* Weg an die Erklärung gewesen.
- **Warum `<details>/<summary>` statt Dauertext:** Bleibt standardmäßig eingeklappt — kein permanenter Erklärungstext, der die beiden wiederkehrenden Nutzer bei jedem Blick auf die Statistik stört (Designprinzip "Verlässlichkeit statt Onboarding").
- **Discoverability:** `<summary>` trägt `underline decoration-dotted decoration-text/60 cursor-pointer` als dezente visuelle Andeutung, ergänzt um die native Browser-Auslassungsmarkierung als zweites Signal. Zero-Dependency, nativ vollständig touch-/tastatur-/screenreaderbedienbar (fokussierbar, Enter/Leertaste öffnet/schließt).
- Nur "Entfernt" und "Übersprungen" erhalten das `<details>`-Muster; die übrigen drei Labels bleiben reiner Text, da selbsterklärend.
- Implementierungsfreiheit: die aufgeklappte Erklärung darf strukturell auch außerhalb des `flex gap-1`-Paar-Wrappers gerendert werden, solange die Grid-Ausrichtung der übrigen vier Paare beim Auf-/Zuklappen unberührt bleibt.

## Security

**Nicht relevant.** Reines DOM-Markup-Refactoring ohne neue Daten, neue Logik oder neue externe Schnittstelle. Der Hilfetext ist ein statischer, fest im Frontend-Code hinterlegter String (kein `dangerouslySetInnerHTML`, kein aus Backend/DB geladener oder nutzergesteuerter Text) — React escaped JSX-Text ohnehin automatisch, kein XSS-Risiko. Keine neue Auth-Logik, keine neue Eingabe von außen, keine Berechtigungsänderung, keine neue Abhängigkeit.

## Teststrategie

- **Testebene:** ausschließlich Integrationsebene, im bestehenden `frontend/src/pages/ProjectDetailPage.test.tsx` (keine neue Datei, keine Extraktion einer separaten Komponente — beide Änderungen sind reines JSX/Attribut-Verhalten ohne neue reine Utility-Funktion).
- **Layout:** automatisiert prüfbar ist nur die DOM-*Gruppierung* (Label+Wert teilen sich ein gemeinsames Elternelement) — die tatsächliche visuelle CSS-Grid-Anordnung bei 2 bzw. 3 Spalten kann `jsdom` nicht prüfen (keine Layout-Engine), bleibt manueller Smoke-Test bei beiden Breakpoints.
- **Hilfetext-Verhalten:**
  - Initial-Zustand kollabiert (kein `open`-Attribut) im DOM.
  - Klick öffnet/schließt wiederholt (`open`-Attribut per `userEvent.click()` prüfen, nicht `aria-expanded`/Rollen-Query — installierte `jsdom`-Version synthetisiert Klick-Aktivierung von `<summary>` zuverlässig).
  - Exakter Erklärungssatz erscheint im geöffneten Zustand für "Entfernt" und "Übersprungen".
  - Beide `<details>` togglen unabhängig (kein `name`-Attribut-Gotcha).
  - 0-Werte-Fall (`photos_removed: 0, files_skipped: 0`): Disclosure bleibt vorhanden und togglebar.
  - Negativtest: "Hinzugefügt"/"Aktualisiert"/"Dateien gefunden" haben keinen `<details>`-Vorfahren (`closest('details')` ist `null`).
- **Nicht automatisiert getestet (bewusst):** Tastaturaktivierung (Enter/Space) — die installierte `jsdom`-Version synthetisiert keinen Klick aus `keydown` auf `<summary>`; im Code-Review sicherstellen, dass kein `onClick`/Wrapper-`<div>` das native Verhalten überschreibt. Screenreader-Verhalten — bewusst nicht automatisiert (kein AOM in `jsdom`), begründet durch die Wahl des nativen Elements gerade wegen dessen etablierter AT-Semantik.
- **Testkonzept ergänzt:** `specs/architecture/0002-testkonzept.md` um einen neuen Unterabschnitt "Natives `<details>`/`<summary>`" im Frontend-Teil erweitert (erste Nutzung dieses Elements im Projekt, über den einzelnen Branch hinaus relevant): `open`-Attribut statt `aria-expanded` prüfen, `userEvent.click()` zuverlässig, Tastatur-Toggle nicht in `jsdom` nachweisbar, `name`-Attribut-Gotcha bei mehreren unabhängigen `<details>`.

## Entscheidungen (2026-08-09, im Idea-Sharpening-Gespräch mit Daniel geklärt)

- **Kombinierte Spec statt Trennung:** Layout-Bug und "Warum"-Funktion werden trotz sehr unterschiedlichem technischem Umfang in einer gemeinsamen Spec behandelt (Stakeholder-Entscheidung).
- **Kein neues Datenmodell für die "Warum"-Funktion (zentrale Entscheidung, Devil's Advocate):** Ursprünglich war eine aggregierte, erweiterbare Gründe-Erfassung pro Scan-Lauf angedacht. Recherche ergab: im Scan-Code (`backend/src/photosort/worker.py`) existiert aktuell exakt EIN realer Grund pro Zähler — "übersprungen" bedeutet immer "Dateiendung nicht unterstützt", "entfernt" bedeutet immer "nicht mehr in Quelle gefunden". Eine Aggregation nach Grund wäre also inhaltlich identisch zur bereits vorhandenen Zahl. Statt Infrastruktur für einen heute nicht real existierenden Bedarf zu bauen (Erweiterbarkeit für künftige Gründe wie Duplikate/defekte Dateien), wurde entschieden: statischer Hilfetext im Frontend, kein Datenmodell. Ein zweiter realer Grund im Scan-Code wäre ein separates künftiges Feature/eine künftige Spec, kein Vorgriff jetzt.
- **Damit entfällt auch die ursprünglich offene Frage zu rückwirkenden Daten** (wie mit alten Scan-Läufen ohne erfassten Grund umgegangen wird) — es gibt kein Datenmodell mehr, das rückwirkend befüllt werden müsste. Der Hilfetext ist statisch und gilt unabhängig vom Scan-Zeitpunkt.
- **`<details>/<summary>` statt `title`-Attribut:** siehe Begründung im UI/UX-Abschnitt (Touch-Zuverlässigkeit).
- **Priorität — Hoch:** vom `requirements-engineer` in der Roadmap-Einordnung vergeben und nach Abschluss der Schärfung bestätigt. Begründung: ein bereits produktiv genutztes Kernelement (Projekt-Statistiken, seit Spec 0005) wurde von Daniel selbst im Alltag als verwirrend gemeldet — vergleichbar mit den Hoch-Präzedenzfällen 0016, 0017, 0021 (jeweils ein selbst bemerktes Klarheits-/Vertrauensproblem an bereits ausgeliefertem Verhalten). Durch die Vereinfachung im Devil's-Advocate-Schritt (kein Datenmodell mehr) ist der Umsetzungsaufwand zusätzlich klein — die hohe Priorität bleibt trotzdem gerechtfertigt, da sie sich aus der Nutzungsauswirkung ableitet, nicht aus dem Aufwand.

## Offene Fragen

Keine offenen Fragen mehr für den Scope dieser Spec.

## Out of Scope

Neues Datenmodell/Reason-Tabelle für Skip-/Removal-Gründe; Liste einzelner betroffener Dateinamen; Erfassung/Anzeige weiterer, aktuell nicht real vorkommender Gründe (z.B. Duplikate, defekte Dateien); rückwirkende Datenerfassung für bereits abgeschlossene Scan-Läufe; neue Tooltip-Bibliothek/-Abhängigkeit.
