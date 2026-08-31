# 0023 - Dynamische Kategorie-Ableitung aus Kriterien-Häufigkeit

**Status:** Superseded — abgelöst durch ADR [`0049`](./0049-festes-kategorien-set-mit-vorrangreihenfolge-und-freien-feinlabels.md). Die Kernaussage dieser ADR ("Kategorien ergeben sich projektweit aus der Häufigkeit eines Kriteriums im Lauf") entfällt vollständig: `derive_active_categories`, `CATEGORY_ACTIVE_THRESHOLD_FRACTION` und die generische Ableitung des `category_key` aus dem `criterion_key` sind ersatzlos gelöscht, das Kategorien-Set ist seither fest und global. Erhalten bleibt allein das Registry-Attribut `CriterionDefinition.category_eligible`/`.category_presence_threshold` (Punkt 1), in ADR 0049 Punkt 4 neu begründet; `category_specificity` (ADR 0047) entfällt ebenfalls.
**Datum:** 2026-08-16
**Bezug:** Revidiert [`decisions/0021-kriterien-datenmodell-kuratierungs-pipeline.md`](./0021-kriterien-datenmodell-kuratierungs-pipeline.md) (nur Punkt 2, "Kategorie-Ableitung" — der Rest von ADR 0021 bleibt unverändert gültig: `PhotoCriterionScore`, `PhotoRanking`, `CriterionScoringRun`, das Gate). Revidiert außerdem explizit die in [`features/0038-vier-zusaetzliche-kriterien-tier-gebaeude-schnitt-aesthetik.md`](../features/0038-vier-zusaetzliche-kriterien-tier-gebaeude-schnitt-aesthetik.md) (UI/UX-Abschnitt) getroffene bewusste Entscheidung, `tier`/`gebaeude` NICHT in die Kategorie-Ableitung aufzunehmen. Architektur-Konsultation zur Idee `specs/inbox/0025-kategorien-aus-bildstatistiken-ableiten.md` (wird als Spec 0045 verfeinert).

## Kontext

`criteria.py::derive_category_key` (Spec 0037, ADR 0021 Punkt 2) ist bisher eine fest codierte, projektunabhängige Prioritätskette: erkannter Mensch → `"people"`, sonst hoher Uniform-Flächen-Anteil → `"landscape"`, sonst Fallback → `"detail"`. Spec 0038 hat bewusst entschieden, die beiden dort neu eingeführten Inhalts-Kriterien `tier`/`gebaeude` NICHT in diese Kette aufzunehmen ("diese Spec erweitert die Prioritätskette nicht").

Daniel möchte das jetzt bewusst ändern: Kategorien sollen sich **projektweit aus der tatsächlichen Häufigkeit** eines Inhalts-Kriteriums im jeweiligen `CriterionScoringRun` ergeben, nicht aus einer statischen, im Code gepflegten Liste. Ein Costa-Rica-Projekt mit vielen Tierfotos soll eine "Tier"-Kategorie bekommen; ein Städtereise-Projekt mit vielen Gebäudefotos eine "Gebäude"-Kategorie — ohne dass dafür jedes Mal Code geändert werden muss. `"people"`/`"landscape"`/`"detail"` sind dabei explizit keine bevorzugten Standardkategorien mehr, sondern unterliegen derselben Regel wie jedes andere Inhalts-Kriterium. Reine Qualitätskriterien (`goldener_schnitt`, `aesthetics`, `sharpness`, `exposure`) dürfen nie Kategorien bilden.

Zwei Datenmodell-Fakten machen das ohne Schema-Änderung umsetzbar: `PhotoRanking.category_key` ist bereits ein freier String (kein Enum), und `run_criterion_scoring` (`worker.py`) hält bereits alle Kriterien-Werte aller Kandidaten-Fotos eines Laufs vollständig im Speicher (`candidate_values`), bevor pro Foto eine Kategorie zugewiesen wird — die für eine Häufigkeits-Aggregation nötige Datengrundlage existiert also bereits am richtigen Punkt im Kontrollfluss.

## Entscheidung

### 1. `CriterionDefinition` bekommt zwei neue, optionale Felder — Kategorie-Fähigkeit wird ein Registry-Attribut, keine externe Liste mehr

```python
@dataclass(frozen=True)
class CriterionDefinition:
    key: str
    display_name: str
    source: CriterionSource
    category_eligible: bool = False
    category_presence_threshold: float | None = None
```

`category_eligible=True` markiert ein Kriterium als potenzielle Kategorie-Quelle; `category_presence_threshold` ist der Wert, ab dem das Kriterium in einem einzelnen Foto als "vorhanden" gilt (Invariante, durch einen Registry-Test erzwungen: `category_eligible=True` ⇒ `category_presence_threshold is not None`, und umgekehrt). Reine Qualitätskriterien (`sharpness`, `exposure`, `goldener_schnitt`, `aesthetics`) behalten den Default `category_eligible=False`. Ein künftiges neues Inhalts-Kriterium ("und so weiter", Rohtext der Idee) wird kategorie-fähig, indem sein Registry-Eintrag diese zwei Felder setzt — keine zusätzliche Stelle im Code muss angefasst werden.

Das löst zugleich eine bestehende terminologische Unschärfe auf: `worker.py::_CONTENT_CRITERION_KEYS` bezeichnet bisher etwas anderes (die Menge der über `_compute_content_criteria` best-effort *bildbasiert berechneten* Kriterien, inkl. `goldener_schnitt`/`aesthetics` — reine Upsert-/Source-Buchhaltung, keine Kategorie-Aussage). Diese ADR führt mit `category_eligible` eine zweite, fachlich andere "Inhalt vs. Qualität"-Unterscheidung ein. Beide bleiben nötig, aber `_CONTENT_CRITERION_KEYS` wird zur Vermeidung von Verwechslung umbenannt (siehe Umsetzungsteil der Spec) — keine funktionale Änderung an diesem Konstrukt.

### 2. Neue reine Funktion `derive_active_categories`: Häufigkeits-Aggregation über den gesamten Lauf

```python
def derive_active_categories(
    candidate_values: dict[int, dict[str, float]],
    threshold_fraction: float = CATEGORY_ACTIVE_THRESHOLD_FRACTION,
) -> frozenset[str]:
```

Für jedes `category_eligible=True`-Kriterium wird der Anteil der Kandidaten-Fotos ermittelt, deren Wert die jeweilige `category_presence_threshold` erreicht/überschreitet; ein Kriterium wird "aktiv", wenn dieser Anteil `>= threshold_fraction` ist. `candidate_values` ist dieselbe Struktur, die `run_criterion_scoring` bereits vollständig im Speicher hält — **die Aggregation läuft einmal pro Lauf (projektweit), nicht pro `cluster_key`**, konsistent mit dem Wortlaut der Idee ("im Lauf"). Fehlende Werte (best-effort-Kriterium für ein Foto nicht berechenbar) zählen als "nicht vorhanden", kein Sonderfall.

**Default-Schwellwert: `CATEGORY_ACTIVE_THRESHOLD_FRACTION = 0.15`** (15 % der Kandidaten-Fotos des Laufs). Begründung: hoch genug, um eine Kategorie mit nur 2-3 zufälligen Treffern in einem mittelgroßen Projekt (100+ Kandidaten) zu vermeiden (reines Rauschen würde sonst zu einer eigenen Abschnittsüberschrift in der Kuratierungs-Ansicht führen); niedrig genug, dass ein thematisch relevanter, aber nicht dominanter Anteil (z.B. 20 von 150 Tierfotos auf einer Costa-Rica-Reise) zuverlässig eine eigene Kategorie auslöst. Wie alle bereits bestehenden Schwellwert-Konstanten in `criteria.py`/`classification.py` (`SHARPNESS_NORMALIZATION_CEILING`, `LANDSCAPE_UNIFORM_FRACTION_THRESHOLD`) ist das eine dokumentierte, nicht gegen einen echten Fotokorpus kalibrierte Setzung, austauschbar ohne Architektur-Änderung. **Bekannte, akzeptierte Grenze:** bei sehr kleinen Projekten (< ca. 20 Kandidaten-Fotos) kann bereits 1 Foto 15 % überschreiten — kein Blocker, gleiche Klasse von Limitierung wie bereits an anderer Stelle im Projekt dokumentiert (z.B. ImageNet-Innenraum-Lücke, ADR 0022).

Presence-Schwellwerte pro Kriterium (Wiederverwendung bestehender Konstanten, keine neue Kalibrierung):
- `content_people`: `0.5` (bereits vorhandene `_CONTENT_PEOPLE_DETECTED_THRESHOLD`).
- `content_landscape`: `0.5` (bereits vorhandene `LANDSCAPE_UNIFORM_FRACTION_THRESHOLD`, `classification.py`).
- `tier`/`gebaeude`: neue, kleine Konstanten (z.B. `0.01`) statt einer inhaltlich neuen Kalibrierung — `compute_tier_score`/`compute_gebaeude_score` liefern ohnehin entweder exakt `0.0` (nichts erkannt) oder einen Wert, der bereits oberhalb der jeweiligen Detektor-eigenen Konfidenzschwelle (`ANIMAL_DETECTION_CONFIDENCE_THRESHOLD`/`SCENE_CLASSIFICATION_CONFIDENCE_THRESHOLD`, beide `0.5`) liegt — die neue Konstante trennt nur "nichts erkannt" von "irgendetwas erkannt", keine zweite Konfidenzschwelle.

### 3. `derive_category_key` bekommt die aktive Menge als Parameter; Priorität bei mehreren Treffern: höchster normierter Score gewinnt

```python
def derive_category_key(
    criterion_values: dict[str, float], active_criteria: frozenset[str]
) -> str:
```

Kein Foto wird mehr gegen eine fest codierte Prioritätskette geprüft, sondern gegen die für den Lauf ermittelte aktive Menge. Erfüllt ein Foto mehrere aktive Kriterien gleichzeitig (z.B. Mensch und Tier im selben Bild), **gewinnt der höchste normierte Score** unter den erfüllten aktiven Kriterien, Tie-Break alphabetisch nach `criterion_key` (deterministisch, testbar). Kein fest gepflegter Prioritäts-Rang wie zuvor — der wäre bei einer offenen, wachsenden Kriterien-Menge genau die Wartungslast, die diese ADR vermeiden soll. In der Praxis approximiert das die alte Reihenfolge im Regelfall: `content_people` ist binär (`0.0`/`1.0`), gewinnt also fast immer gegen die typischerweise niedrigeren, kontinuierlichen Konfidenzwerte von `tier`/`gebaeude`. Kein erfülltes aktives Kriterium → `CATEGORY_DETAIL` (Catch-all, unverändert der bestehende String-Wert `"detail"`).

### 4. Kategorie-Schlüssel wird automatisch aus dem Kriterien-Schlüssel abgeleitet, kein manuelles Mapping mehr

Statt der bisherigen Konstanten `CATEGORY_PEOPLE = "people"`/`CATEGORY_LANDSCAPE = "landscape"` (Handarbeit pro Kriterium) wird der `category_key` generisch aus dem gewinnenden `criterion_key` gebildet: `criterion_key.removeprefix("content_")`. Das liefert für die bestehenden Kriterien identische Werte wie bisher (`"content_people"` → `"people"`, `"content_landscape"` → `"landscape"`) und für die neuen automatisch `"tier"`/`"gebaeude"` (kein `"content_"`-Präfix vorhanden, bleibt unverändert) — ohne dass für ein künftiges fünftes oder sechstes kategorie-fähiges Kriterium irgendeine Mapping-Stelle im Code ergänzt werden müsste. Das ist der konkrete technische Baustein, der die "und so weiter"-Anforderung der Idee erfüllt.

## Begründung

- Löst das eigentliche Ziel der Idee strukturell: eine neue Kategorie entsteht durch Registry-Erweiterung + tatsächliche Häufigkeit in den Daten, nie durch eine Code-Änderung an der Ableitungslogik selbst.
- Bleibt konsistent mit dem in ADR 0021 bereits etablierten Grundsatz ("neues Kriterium braucht nur einen Registry-Eintrag, keine Migration") — diese ADR wendet denselben Grundsatz konsequent auf die Kategorie-Ableitung an, die bisher die einzige verbliebene hart codierte Stelle war.
- Kein Schema-/Migrations-Bedarf: `PhotoRanking.category_key` war bereits ein freier String.
- "Höchster Score gewinnt" statt einer gepflegten Prioritätsliste ist die einzige Regel, die ohne Wartungsaufwand mit einer offenen, wachsenden Kriterien-Menge skaliert, und approximiert nachweislich das bisherige, vertraute Verhalten im Regelfall (Begründung siehe Punkt 3).

## Konsequenzen

- **Verhaltensänderung, kein reiner Zusatz:** Fotos, die bisher z.B. wegen eines hohen `content_landscape`-Werts als `"landscape"` kategorisiert wurden, landen in einem Lauf, in dem `content_landscape` die 15-%-Schwelle nicht erreicht, jetzt in `"detail"` — auch wenn sich am Einzelfoto-Score nichts geändert hat. Das ist beabsichtigt (Kernaussage der Idee: "Detail, People und Landscape sollen nicht mehr Standard-Kategorien sein"), aber sichtbar für Bestandsprojekte bei einem erneuten `CriterionScoringRun`.
- `worker.py::_CONTENT_CRITERION_KEYS`/`_CONTENT_CRITERION_SOURCES` werden umbenannt (z.B. `_IMAGE_ANALYSIS_CRITERION_KEYS`/`_IMAGE_ANALYSIS_CRITERION_SOURCES`), um die Verwechslung mit der neuen `category_eligible`-Bedeutung von "Inhalt" zu vermeiden — rein kosmetisch, keine Verhaltensänderung.
- `docs/architecture.md` (Owner: `architect`) wird **nach** der Umsetzung um die neuen `CriterionDefinition`-Felder, `derive_active_categories` und die geänderte `derive_category_key`-Signatur ergänzt, analog zum bereits etablierten Muster (ADR 0021 Konsequenzen).
- Kein Frontend-Effekt: `CategoryBadge`/`categoryLabels.ts`/`CurateCategoriesPage.tsx` sind bereits vollständig `category_key`-agnostisch (bestätigt bei dieser Konsultation, Spec 0039/0043).
- Ein späterer Wechsel des Aggregationsprinzips (z.B. Schwellwert wird eine Projekt-Einstellung statt einer globalen Konstante, oder ein anderes Prioritätsprinzip als "höchster Score gewinnt") bleibt architekturrelevant und braucht eine neue ADR, die diese hier als "Superseded" markiert.
