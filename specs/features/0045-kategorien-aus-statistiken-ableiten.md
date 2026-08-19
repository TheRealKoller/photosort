# 0045 - Kategorien aus Bild-Statistiken ableiten

**Status:** Implemented ([PR #106](https://github.com/TheRealKoller/photosort/pull/106))
**Erstellt:** 2026-08-16
**Bezug:** `specs/inbox/0025-kategorien-aus-bildstatistiken-ableiten.md` (Ursprungs-Idee), idea-sharpener-Gespräch mit Daniel, ADR [`decisions/0023-dynamische-kategorie-ableitung-aus-kriterien-haeufigkeit.md`](../decisions/0023-dynamische-kategorie-ableitung-aus-kriterien-haeufigkeit.md). Revidiert bewusst Teile von ADR [`0021`](../decisions/0021-kriterien-datenmodell-kuratierungs-pipeline.md) (nur Punkt 2, Kategorie-Ableitung) und den UI/UX-Abschnitt von Spec [`0038`](./0038-vier-zusaetzliche-kriterien-tier-gebaeude-schnitt-aesthetik.md).

## Ziel

Kategorien für die Top-N-Auswahl und die Kuratierungsansicht sollen sich künftig aus der tatsächlichen Häufigkeit von Inhalts-Kriterien im jeweiligen Projekt ergeben, statt aus einer festen, im Code gepflegten Prioritätskette (bisher: Mensch → Landschaft → Fallback „Detail"). Kommen in einem Projekt viele Tierfotos vor, wird „Tier" eine eigene Kategorie; kommen viele Gebäude vor, „Gebäude" — und so weiter für künftige neue Inhalts-Kriterien, ohne dass dafür Ableitungscode geändert werden muss. Reine Qualitätskriterien (Goldener Schnitt, Ästhetik, Schärfe, Belichtung) bilden nie Kategorien.

## User Story

Als Nutzer (Daniel oder seine Frau) möchte ich, dass die Kategorien in der Kuratierungsansicht zum tatsächlichen Inhalt meines jeweiligen Projekts passen (z.B. „Tier" bei einer Safari-Reise, „Gebäude" bei einer Städtereise), statt immer nur zwischen den immer gleichen, teils gar nicht zutreffenden Standardkategorien zu wählen.

## Akzeptanzkriterien

**Registry-Erweiterung**
- [ ] `CriterionDefinition` bekommt zwei neue optionale Felder: `category_eligible: bool = False`, `category_presence_threshold: float | None = None`. Es gilt die Invariante `category_eligible == (category_presence_threshold is not None)` für jeden Eintrag der `CRITERIA_REGISTRY`, durchgesetzt durch einen eigenen Test.
- [ ] Genau `content_people` (Presence-Schwelle `0.5`), `content_landscape` (`0.5`), `tier` und `gebaeude` (je eine neue, kleine Konstante ~`0.01`) haben `category_eligible=True`. `sharpness`, `exposure`, `goldener_schnitt`, `aesthetics` bleiben beim Default `False` und können nie eine Kategorie bilden.

**Aggregation (`derive_active_categories`)**
- [ ] Neue reine Funktion `derive_active_categories(candidate_values: dict[int, dict[str, float]], threshold_fraction: float = CATEGORY_ACTIVE_THRESHOLD_FRACTION) -> frozenset[str]`, ohne DB-/I-O-Zugriff. Ein `category_eligible=True`-Kriterium gilt als aktiv, wenn der Anteil der Kandidaten-Fotos, deren Wert `>= category_presence_threshold` ist, `>= threshold_fraction` ist (inklusiver Vergleich in beide Richtungen). Fehlende Werte für einzelne Fotos zählen als „nicht vorhanden".
- [ ] Default `CATEGORY_ACTIVE_THRESHOLD_FRACTION = 0.15` (15 % der Kandidaten-Fotos des Laufs).
- [ ] Bei `candidate_values == {}` liefert die Funktion `frozenset()` ohne Exception (kein `ZeroDivisionError`).
- [ ] Ein Kriterium mit 0 Treffern im Lauf bleibt inaktiv.
- [ ] Wird in `run_criterion_scoring` (`worker.py`) genau einmal pro Lauf, projektweit über alle Kandidaten-Fotos (nicht pro `cluster_key`), nach Abschluss der Foto-Schleife aufgerufen; das Ergebnis wird an die bestehende Partitionierungs-Schleife durchgereicht.

**Zuweisung (`derive_category_key`)**
- [ ] Geänderte Signatur `derive_category_key(criterion_values: dict[str, float], active_criteria: frozenset[str]) -> str` — prüft pro Foto nur noch gegen die für den Lauf ermittelte aktive Menge, nicht mehr gegen eine feste Prioritätskette.
- [ ] Erfüllt ein Foto mehrere aktive Kriterien gleichzeitig, gewinnt der höchste normierte Score; bei exakt gleichem Score entscheidet die alphabetische Reihenfolge des `criterion_key` (deterministisch, testbar).
- [ ] Kein erfülltes aktives Kriterium → Catch-all `CATEGORY_DETAIL` (bestehender String-Wert `"detail"`, unverändert).
- [ ] `category_key` wird generisch aus dem gewinnenden `criterion_key` gebildet: `criterion_key.removeprefix("content_")` — liefert für Bestandskriterien identische Werte wie bisher (`"people"`/`"landscape"`), für `tier`/`gebaeude` automatisch die richtigen Keys, ohne manuelles Mapping.

**Regression und Konsistenz**
- [ ] Regressionstest: dasselbe Foto mit identischem `content_landscape`-Score landet je nach Lauf in unterschiedlichen Kategorien, abhängig davon, ob die 15%-Häufigkeitsschwelle im jeweiligen Lauf erreicht wird — das ist die beabsichtigte Kernverhaltensänderung, nicht ein Bug.
- [ ] Bestandsverhalten bleibt bei ausreichender Häufigkeit unverändert: ein Projekt, in dem `content_people`/`content_landscape` weiterhin die 15%-Schwelle erreichen, liefert dieselben `category_key`-Werte wie bisher.
- [ ] `worker.py::_CONTENT_CRITERION_KEYS`/`_CONTENT_CRITERION_SOURCES` werden zu `_IMAGE_ANALYSIS_CRITERION_KEYS`/`_IMAGE_ANALYSIS_CRITERION_SOURCES` umbenannt (rein kosmetisch, andere Bedeutung als `category_eligible` — bezeichnet die best-effort bildbasiert berechneten Kriterien für Upsert-Buchhaltung, keine Verhaltensänderung).

**Frontend**
- [ ] `frontend/src/utils/categoryLabels.ts` bekommt ein explizites Anzeigenamen-Mapping für Kategorien mit Sonderzeichen: `"gebaeude"` → `"Gebäude"` (mit Umlaut). `formatCategoryKey()` bleibt der generische Fallback (automatische Groß-/Kleinschreibung) für alle unbekannten/künftigen Keys.
- [ ] Keine weiteren Frontend-Änderungen nötig — `CategoryBadge.tsx`/`CurateCategoriesPage.tsx` sind bereits vollständig `category_key`-agnostisch (Spec 0039/0043) und rendern neue Kategorie-Abschnitte automatisch.

## Datenmodell-Bezug

Keine Migration. `PhotoRanking.category_key` war bereits ein freier String (kein Enum). Die neuen `CriterionDefinition`-Felder sind reine In-Code-Registry-Metadaten, keine DB-Spalten. Siehe [`docs/architecture.md`](../../docs/architecture.md).

## Architektur / Umsetzung

Siehe ADR [`decisions/0023-dynamische-kategorie-ableitung-aus-kriterien-haeufigkeit.md`](../decisions/0023-dynamische-kategorie-ableitung-aus-kriterien-haeufigkeit.md) für die vollständige Begründung. Zusammenfassung:

`criteria.py::derive_category_key` ist heute eine fest codierte, projektunabhängige Prioritätskette. Diese Spec macht die Kategorie-Zuweisung datengetrieben: welche Inhalts-Kriterien in einem `CriterionScoringRun` überhaupt eine eigene Kategorie bilden, hängt von ihrer tatsächlichen Häufigkeit im jeweiligen Lauf ab, nicht mehr von einer im Code gepflegten Liste. `run_criterion_scoring` (`worker.py`) hält die dafür nötige Datengrundlage (`candidate_values: dict[photo_id, dict[criterion_key, float]]`) bereits vollständig im Speicher, bevor die bisherige Kategorie-Zuweisung passiert — kein struktureller Umbau des Kontrollflusses, nur ein zusätzlicher Aggregationsschritt dazwischen.

**Registry-Erweiterung:** `CriterionDefinition.category_eligible`/`.category_presence_threshold` — ein künftiges neues Inhalts-Kriterium wird kategorie-fähig, indem sein Registry-Eintrag diese zwei Felder setzt, keine weitere Code-Stelle muss angefasst werden. Löst zugleich eine terminologische Unschärfe auf: `_CONTENT_CRITERION_KEYS` in `worker.py` bezeichnete bisher etwas fachlich anderes (bildbasiert berechnete Kriterien für Upsert-Buchhaltung, inkl. `goldener_schnitt`/`aesthetics`) — wird umbenannt, um Verwechslung mit der neuen `category_eligible`-Bedeutung zu vermeiden.

**Aggregation vor Zuweisung:** `derive_active_categories` läuft einmal pro Lauf (projektweit), `derive_category_key` bekommt die aktive Menge als Parameter. „Höchster Score gewinnt" statt einer gepflegten Prioritätsliste ist die einzige Regel, die ohne Wartungsaufwand mit einer offenen, wachsenden Kriterien-Menge skaliert — approximiert im Regelfall das bisherige Verhalten, da `content_people` binär ist und fast immer gegen die niedrigeren, kontinuierlichen Tier-/Gebäude-Konfidenzen gewinnt.

**Betroffene Dateien / Umsetzungsreihenfolge:**
1. `backend/src/photosort/criteria.py` — `CriterionDefinition`-Felder, Registry-Einträge, neue Konstanten (`CATEGORY_ACTIVE_THRESHOLD_FRACTION`, Presence-Schwellwerte für `tier`/`gebaeude`), `derive_active_categories`, geänderte `derive_category_key`-Signatur.
2. `backend/tests/test_criteria.py` — Registry-Invarianten-Test, neue Testklasse für `derive_active_categories`, `TestDeriveCategoryKey` auf neue Signatur umgestellt.
3. `backend/src/photosort/worker.py` — `run_criterion_scoring`: Aggregationsaufruf nach der Foto-Schleife, Umbenennung `_CONTENT_CRITERION_KEYS`→`_IMAGE_ANALYSIS_CRITERION_KEYS`.
4. `backend/tests/test_worker_criterion_scoring.py` — Integrationstests (siehe Teststrategie).
5. `frontend/src/utils/categoryLabels.ts` — Mapping-Eintrag für „gebaeude".

Kein neuer Endpunkt. `docs/architecture.md` wird im selben PR um die neuen `CriterionDefinition`-Felder und `derive_active_categories` ergänzt.

## UI/UX

**Sichtbare Oberfläche:** Ja, aber nur indirekt — keine neuen Views, rein Backend-seitige Erweiterung der bestehenden Kategorisierungslogik. Die Kuratierungsansicht (`/projects/:projectId/curate`, `CurateCategoriesPage.tsx`) ist bereits vollständig `category_key`-agnostisch (Spec 0039) — neue Kategorie-Keys wie „tier" oder „gebaeude" erfordern keine Frontend-Komponenten-Änderungen, da Kategorien dynamisch als Abschnitte gerendert werden.

**Sichtbare Auswirkung:** Bestandsprojekte zeigen nach einem erneuten Kriterien-Scoring-Lauf möglicherweise neue Kategorie-Abschnitte, je nachdem, welche Inhalts-Kriterien im Lauf die 15%-Häufigkeitsschwelle erreichen. Ein Projekt, das bisher nur „people"/„landscape"/„detail" zeigte, könnte künftig zusätzlich „gebaeude" und „tier" enthalten. Diese Verschiebung erfolgt ohne Hinweistext — konsistent mit dem Designprinzip „Durchsatz vor Erklärung" und etablierter Praxis im Projekt (Re-Scans/Re-Scoring verändern Daten bereits heute ohne Erklär-Overlay).

**Kategorie-Abschnittsreihenfolge:** bleibt alphabetisch nach `category_key` (unverändert, Spec 0039) — keine Sonderbehandlung für „detail" als Catch-all.

**Anzeigenamen:** `categoryLabels.ts` bekommt ein explizites Mapping nur für Kategorien mit Sonderzeichen-Bedarf: „gebaeude" → „Gebäude" (mit Umlaut). `formatCategoryKey()` bleibt der generische Fallback (automatische Großschreibung) für alle unbekannten/künftigen Keys — kein Mapping-Eintrag für jedes künftige Kriterium nötig.

**Design-System:** keine neuen Muster nötig. Die bestehende Kategorie-Kennzeichnung (Badge mit Kürzel auf der Grid-Kachel, ausgeschriebener Name als Abschnittsüberschrift) ist bereits für beliebig viele Keys ausgelegt.

**Platzproblem bei mehr Kategorien:** Mit potenziell 5+ Kategorien statt bisher 3 werden Abschnitte in der Kuratierungsansicht natürlicherweise verdünnter — kein zusätzlicher UI-Mechanismus in dieser Spec, da Spec 0043 (auf-/zuklappbare Tage) die Übersichtlichkeit bereits auf Tages-Ebene adressiert (siehe Out of Scope).

## Security

Nicht relevant. `security-engineer` nicht konsultiert (siehe Entscheidungen) — reine Änderung der Klassifikations-/Kategorisierungslogik ohne neue externe Eingaben, ohne Auth-/Berechtigungsbezug, ohne Migration, ohne Auswirkung auf die Sichtbarkeit von Daten zwischen den beiden Nutzern (beide sehen weiterhin dieselben Kategorien für dasselbe Projekt).

## Teststrategie

Erstes zweistufiges Aggregations-vor-Zuweisungs-Muster im Projekt (bisher war jede Ableitungsfunktion rein pro Kandidat/Partition unabhängig) und erste über zwei gekoppelte Dataclass-Felder ausgedrückte Registry-Invariante mit eigenem Äquivalenz-Test.

**Unit (`test_criteria.py`):** `derive_active_categories` als eigene Testklasse — leerer Kandidatenpool (kein `ZeroDivisionError`), genau an der 15%-Schwelle (inklusiv) + je ein Fall knapp drüber/drunter, Kriterium mit 0 Treffern bleibt inaktiv, fehlende Kriterien-Werte pro Foto. `TestDeriveCategoryKey` auf neue Signatur umgestellt (bestehende vier Fälle werden zum Regressionstest für Bestandsverhalten), plus neue Fälle für Score-Priorität bei mehreren aktiven Kriterien und alphabetischen Tie-Break. Eigener Registry-Invarianten-Test (`category_eligible ⇔ threshold gesetzt`) über alle `CRITERIA_REGISTRY`-Einträge.

**Integration (`test_worker_criterion_scoring.py`):** Aufrufzähler-Nachweis „genau einmal pro Lauf, projektweit, nach der Foto-Schleife"; Ende-zu-Ende-Häufigkeitsszenario (gleiche Tierfoto-Scores, einmal über/einmal unter 15% verdünnt → unterschiedlicher `category_key`); Bestandsverhalten-Regression; leerer Kandidatenpool.

**Testkonzept-Ergänzung:** `specs/architecture/0002-testkonzept.md` wurde bereits um eine neue Sektion „Zweistufige Häufigkeits-Aggregation vor Zuweisung + Registry-Invariante (`derive_active_categories`/`category_eligible`)" im Backend-Abschnitt ergänzt (inkl. Verlaufseintrag) — als Vorlage für künftige Features mit vorgelagerter, batch-weiter Aggregation vor einer Pro-Item-Zuweisung.

## Entscheidungen

- **Bewusste Revision von ADR 0021 (Punkt 2) und Spec 0038:** beide hatten festgelegt bzw. entschieden, dass Tier/Gebäude trotz Berechnung nicht zu Kategorien werden. Daniel hat im Sharpening-Gespräch bestätigt, dass das jetzt bewusst revidiert werden soll — siehe ADR 0023 für die vollständige Begründung.
- **People/Landscape/Detail verlieren ihren festen Vorrang:** sie unterliegen jetzt derselben Häufigkeits-Regel wie jedes andere Inhalts-Kriterium, sind aber weiterhin als Kandidaten im Spiel (nicht als Konzept entfernt) — Bestätigung aus dem Verständnis-Gespräch mit Daniel.
- **Exklusive Kategorie-Zuordnung pro Foto** (keine Mehrfachzuordnung) beibehalten — Daniel bestätigt, damit die bestehende Quoten-basierte Top-N-Logik unverändert funktioniert.
- **Auffangkategorie statt Ausschluss:** Fotos ohne erfülltes aktives Kriterium landen im bestehenden Catch-all `"detail"`, fallen nicht aus der automatischen Auswahl heraus — Daniel bestätigt.
- **Schwellwert-Mechanik:** Prozentsatz der Kandidaten-Fotos des Laufs (nicht absolute Mindestanzahl) — Daniel bestätigt, skaliert automatisch mit der Projektgröße. Exakter Wert (15 %) als technische Empfehlung vom `architect`-Agenten festgelegt (siehe ADR 0023), keine eigene Präferenz von Daniel.
- **Aggregation projektweit, nicht pro Cluster:** entspricht dem Wortlaut der Ursprungsidee ("in einem Projekt viele Bilder mit Tieren") — technische Detailentscheidung des `architect`-Agenten.
- **`security-engineer` nicht konsultiert (Schritt 8):** reine Klassifikationslogik-Änderung ohne Auth-/Daten-/Schnittstellenbezug, keine Migration, keine veränderte Datensichtbarkeit zwischen den Nutzern.
- **Spec 0038 nicht auf `Superseded` gesetzt:** nur ihr UI/UX-Abschnitt (Entscheidung gegen Kategorie-Erweiterung) wird revidiert und mit einem Verweis auf diese Spec versehen — die Kriterien-Berechnung selbst (Tier-/Gebäude-Scores, Modellwahl, ADR 0022) bleibt vollständig gültig und unverändert. Eine komplette Supersession würde das falsch darstellen.

## Offene Fragen

Keine.

## Out of Scope

- Mehrfachzuordnung eines Fotos zu mehreren Kategorien gleichzeitig.
- Persistierung/Konfigurierbarkeit des 15%-Schwellwerts pro Projekt (aktuell globale Konstante) — ein späterer Wechsel bleibt laut ADR 0023 architekturrelevant und bräuchte eine neue ADR.
- Zusätzlicher UI-Mechanismus gegen Platzprobleme bei vielen Kategorie-Abschnitten (adressiert bereits über Spec 0043 auf Tages-Ebene).
- Neue Inhalts-Kriterien selbst (z.B. Bildkomposition aus Inbox 0023, Sehenswürdigkeit aus Inbox 0017/0022) — diese Spec liefert nur den Mechanismus, mit dem künftige Inhalts-Kriterien automatisch kategorie-fähig werden können.
- Rückwirkende Neuberechnung bereits abgeschlossener `CriterionScoringRun`-Läufe — die neue Logik gilt erst für künftige Läufe.
