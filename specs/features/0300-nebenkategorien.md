# 0300 - Nebenkategorien: ein Foto gehört mehreren Kategorien an

**Status:** Accepted
**Erstellt:** 2026-09-09
**Bezug:** [GitHub-Issue #300](https://github.com/TheRealKoller/photosort/issues/300) (Refinement vor dieser Spec-Erstellung abgeschlossen, Story-Inhalt unverändert übernommen und auf Testbarkeit geschärft). Setzt Spec [`0299`](./0299-kategorie-konfidenz-anzeigen.md) voraus (umgesetzt, [PR #362](https://github.com/TheRealKoller/photosort/pull/362)).

## Ziel

Ein Foto zeigt oft mehr als ein Motiv — ein Kind mit dem Hund, ein Auto vor einer Berglandschaft. Heute erhält jedes Foto genau eine Kategorie, bestimmt über eine feste Vorrangreihenfolge, und die Kuratierung gruppiert nach genau dieser einen Kategorie. Das Foto mit Kind und Hund erscheint deshalb ausschließlich unter „Menschen" und fehlt beim Durchsehen der Tierbilder vollständig — auch dann, wenn es das beste Tierbild des Tages wäre. Die manuelle Übersteuerung hilft dagegen nicht: Sie hängt das Foto nur um, statt es an beiden Stellen zu zeigen.

Ziel ist, dass ein Foto neben seiner Hauptkategorie weitere Nebenkategorien führen kann und beim Kuratieren in jeder Kategorie auftaucht, zu der es tatsächlich gehört. Wie sicher sich das Bilderkennungsmodell bei einer Kategorie war, entscheidet dabei zweierlei: ob sie überhaupt als Nebenkategorie gilt, und wie weit vorne das Foto in dieser Kategorie steht. Ein nur vermutetes Tier steht damit hinter den eindeutigen Tierbildern — verschwindet aber nicht mehr aus der Kategorie.

Diese Spec verwendet die Sicherheitsangabe aus Spec 0299 erstmals **steuernd** statt nur anzeigend. Die Wahl der Hauptkategorie bleibt davon ausdrücklich unberührt.

## User Story

Als kuratierender Nutzer möchte ich, dass ein Foto mit mehreren Motiven in jeder passenden Kategorie erscheint und dort nach Erkennungssicherheit einsortiert wird, damit ich beim Durchsehen einer Kategorie kein Foto übersehe, nur weil ein anderes Motiv darauf noch stärker vertreten war.

## Akzeptanzkriterien

Die Kriterien der Story sind bei der Spec-Erstellung auf Prüfbarkeit geschärft worden (`test-engineer`). Die Kriterien 19–25 sind dabei neu hinzugekommen, jeweils um eine Zusage prüfbar zu machen, die die Story nur mitmeinte.

**Mehrfachzugehörigkeit**

- [ ] 1. Ein Foto hat pro Lauf genau eine `photo_rankings`-Zeile mit `is_primary = true`; deren `category_key` entsteht unverändert aus `derive_photo_category`/`resolve_category` (gleiche Signatur, kein Konfidenz-Parameter). Zwei Läufe mit identischer Kandidatenmenge, aber unterschiedlichen Konfidenzen liefern dieselbe Hauptkategorie.
- [ ] 2. Zusätzlich entsteht je Kategorie, die (a) im festen Set steht, (b) nicht die Hauptkategorie ist, (c) nicht `nicht_erkannt` ist und (d) eine Modellkonfidenz `>= SECONDARY_CATEGORY_MIN_CONFIDENCE` trägt, genau eine Zeile mit `is_primary = false` in der Partition `(cluster_key des Fotos, diese Kategorie)`. Die Nebenkategorien werden in Registry-Anzeigereihenfolge geliefert, nicht in der Reihenfolge der Modellantwort.
- [ ] 3. Ein Wert echt unterhalb der Schwelle erzeugt keine Nebenzeile. Am Rand geprüft: exakt der Schwellwert erzeugt sie (inklusiv `>=`), der nächstkleinere darstellbare Wert nicht.
- [ ] 4. Die Schwelle ist eine benannte Konstante in `categories.py`: sie erscheint in keiner API-Antwort, keiner Umgebungsvariable und keiner Frontend-Datei (repoweite Abwesenheits-Assertion) und ist für alle Projekte und Nutzer dieselbe.
- [ ] 5. `nicht_erkannt` wird nie Nebenkategorie — auch dann nicht, wenn zu diesem Schlüssel eine Konfidenz oberhalb der Schwelle vorliegt.
- [ ] 6. Eine erkannte Kategorie ohne Zahl (kein `confidence`-Eintrag, verworfener Wert, oder `detected_category_confidences = NULL` aus der Zeit vor Spec 0299) wird nicht zur Nebenkategorie und bleibt zugleich vollwertiger Kandidat der Hauptkategorie-Vorrangreihenfolge.
- [ ] 19. Nebenkategorien entstehen ausschließlich aus der Modellkonfidenz: ein rein lokal erkanntes Signal erzeugt nie eine Nebenzeile, auch wenn sein Kriterium die `category_presence_threshold` deutlich überschreitet.
- [ ] 20. Ein Foto steht pro Lauf höchstens einmal je Kategorie: eine zweite Zeile mit gleichem `(Lauf, Foto, Kategorie)` wird von der Datenbank abgewiesen. Je Foto entstehen höchstens **vier** Zeilen (bis zu `MAX_REMOTE_CATEGORIES_PER_PHOTO = 3` Nebenkategorien plus eine Hauptkategorie, die aus einem lokalen Signal oder einem Override außerhalb dieser drei liegen kann).

**Reihenfolge in der Kuratierung**

- [ ] 7. Eine Kategorie eines Clusters ist **eine** Liste: Haupt- und Nebenzeilen derselben Partition werden in einem Durchgang sortiert und tragen `rank_position` `1..n` — lückenlos und doppelungsfrei.
- [ ] 8. Sortiert wird nach `rank_score - CONFIDENCE_RANK_PENALTY * (1 - confidence)`; `PhotoRanking.rank_score` bleibt der ungedämpfte Wert. Nachprüfbare Zusage: liegt der `rank_score` eines Fotos um **mehr als** `CONFIDENCE_RANK_PENALTY` über dem eines anderen derselben Partition, kehrt keine Kombination zulässiger Konfidenzen die Reihenfolge der beiden um.
- [ ] 9. Die Dämpfung benutzt ausschließlich die Konfidenz zum `category_key` genau dieser Partition; Konfidenzen zweier Kategorien werden an keiner Stelle miteinander verglichen. Dasselbe Foto kann in zwei Kategorien unterschiedliche `rank_position` haben, nie unterschiedliche `rank_score`.
- [ ] 10. Ein Foto ohne Konfidenz zu dieser Kategorie wird nicht gedämpft: seine Position in der Partition ist gleich oder besser als in derselben Partition ohne jede Dämpfung — nie schlechter.
- [ ] 21. `rank_position` ist innerhalb einer Partition nicht mehr monoton in `rank_score`: ein Foto mit höherem Rang-Score darf hinter einem anderen stehen. Die Docstrings von `rank_photos`/`confidence_ordering_score` sagen das aus.
- [ ] 22. Eine manuell übersteuerte Hauptzeile wird nicht gedämpft: ihr Sortierwert ist ihr `rank_score`, unabhängig davon, welche Zahl das Modell zu diesem Schlüssel geliefert hat.

**Bestbild-Auswahl**

- [ ] 11. Die Auswahl wird je Partition gebildet: ein Foto kann in mehreren Kategorien vorgeschlagen werden. In der API kommt es trotzdem höchstens einmal in `PhotoListOut.items` vor; welche seiner Zugehörigkeiten zur Auswahl gehören, steht an den einzelnen `rankings`-Einträgen (`curation_position != null`).
- [ ] 12. `top_n` wirkt unverändert je Partition — eine Partition liefert genau so viele Vorschläge wie vor der Umstellung; das `row_number()` nach dem Ausschluss eigener Ablehnungen bleibt unverändert und zählt Neben- wie Hauptzeilen mit.
- [ ] 23. `curation_position` ist ausdrücklich nicht `rank_position`: hinter einem vom Nutzer abgelehnten Foto ist sie kleiner als `rank_position`; eine Zugehörigkeit außerhalb der angeforderten Auswahl und jede Zugehörigkeit ohne Auswahlmodus trägt `null`.

**Erkennbarkeit**

- [ ] 13. In den Bewertungsdetails (geteilte Komponente, alle drei Ansichten) ist zu jeder Kategorie des Fotos seine Rolle ablesbar. Die Rolle kommt ausschließlich aus `is_primary`, nie aus einem Zahlenvergleich; die Konfidenzzahlen aus Spec 0299 werden dort nicht wiederholt.
- [ ] 14. Eine Kachel, die in der Kuratierung unter einer ihrer **Neben**kategorien steht, trägt einen Marker mit Textalternative (`role="img"` + `aria-label`, Rolle nie nur über Farbe); dieselbe Kachel unter ihrer Hauptkategorie trägt ihn nicht.
- [ ] 24. Ohne Nebenkategorien sieht die Oberfläche exakt wie heute aus: ein Foto mit genau einer Zugehörigkeit rendert weder Marker noch Rollenzeile (Negativ-Assertion auf Text/Textalternative), und die Gruppenüberschriften der Kuratierung ändern sich nicht.

**Bestehendes Verhalten**

- [ ] 15. Ein Override setzt weiterhin nur `photo_scores.category_override` und bestimmt daraus die Hauptzeile; die Nebenkategorien werden aus der unveränderten Modellaussage neu abgeleitet. Die bisher automatisch bestimmte Hauptkategorie wird dabei zur Nebenkategorie, sofern sie die Schwelle erreicht — das Foto verschwindet nicht aus ihr. Ein Override auf eine bereits bestehende Nebenkategorie führt beide Zeilen zu einer Hauptzeile zusammen (kein `409`, keine zweite Zeile in der Partition). Zurücknehmen stellt die Zugehörigkeitsmenge des automatischen Laufs wieder her. Nebenkategorien sind nie manuell setzbar oder entfernbar.
- [ ] 16. Auswertungen zählen die Hauptkategorie: Kategorienverteilung der Statistikseite und `category_diff.py::collect_assignments` filtern auf `is_primary`, die Summe über alle Kategorien bleibt gleich der Fotoanzahl. Die Partitionsgröße („von N" im Popover) zählt dagegen **alle** Zeilen der Partition.
- [ ] 17. Ein Projekt ohne aktivierte Cloud-Klassifizierung verhält sich unverändert: je Foto genau eine Zeile mit `is_primary = true`, keine Dämpfung, und bei gleicher Eingabe dieselbe Reihenfolge wie vor der Umstellung.
- [ ] 18. Läufe von vor der Migration behalten ihre Zeilen unverändert (`is_primary = true`, keine Nebenzeilen); die Migration schreibt keine neuen Zeilen. Nebenkategorien entstehen erst in einem neuen Kriterien-Lauf und dort nur für Fotos, deren Klassifizierungszeile Konfidenzen trägt — der vor Spec 0299 klassifizierte Bestand bleibt ohne Nebenkategorien, bis „Neu-Klassifizierung erzwingen" ihn erneuert.
- [ ] 25. Nach `upgrade()` trägt `is_primary` keinen `server_default` mehr, und ein Insert ohne die Spalte scheitert; `downgrade()` entfernt zuerst die Nebenzeilen und stellt den alten, benannten Constraint her, sodass beide Richtungen an einer Datenbank **mit** Nebenzeilen fehlerfrei laufen.
- [ ] 26. Die Tageszählung der Kuratierung („N Fotos" in der Tagesüberschrift) zählt **eindeutige Fotos**, nicht Zugehörigkeiten: ein Foto, das an diesem Tag in zwei Kategorien erscheint, erhöht die Zahl um eins.

## Datenmodell-Bezug

Betroffen ist ausschließlich die Entität **PhotoRanking** (`photo_rankings`), siehe [`docs/architecture.md`](../../docs/architecture.md):

| Änderung | Form | Bedeutung |
|---|---|---|
| neu `is_primary` | `Boolean`, NOT NULL | Unterscheidet Haupt- von Nebenkategorie. Genau eine `true`-Zeile je `(criterion_scoring_run_id, photo_id)`. |
| Unique-Constraint | `(run, photo)` → `(run, photo, category_key)` | Ein Foto steht pro Lauf höchstens einmal **je Kategorie** statt höchstens einmal überhaupt. Name: `uq_photo_ranking_run_photo_category`. |

`rank_score` bleibt unverändert der ungedämpfte gewichtete Kriterien-Mittelwert und ist über alle Zugehörigkeitszeilen eines Fotos identisch. `rank_position` ist es nicht — es ist innerhalb einer Partition **nicht mehr monoton in `rank_score`** (gewollt, siehe „Gewichtung der Rangfolge").

**Kein anderes Modell ändert sich.** `photo_category_classifications` bleibt 1:1 zum Foto; die Nebenkategorien werden vollständig aus der mit Spec 0299 eingeführten Spalte `detected_category_confidences` abgeleitet — **kein neuer Cloud-Aufruf, keine Prompt-Änderung, keine Kostenänderung**.

## Architektur / Umsetzung

Architekturentscheidung: ADR [`0069`](../decisions/0069-nebenkategorien-mehrfachzugehoerigkeit-und-konfidenzgewichtete-rangfolge.md) (löst ADR [`0049`](../decisions/0049-festes-kategorien-set-mit-vorrangreihenfolge-und-freien-feinlabels.md), [`0021`](../decisions/0021-kriterien-datenmodell-kuratierungs-pipeline.md) und [`0067`](../decisions/0067-modellkonfidenz-je-kategorie-anzeige-und-auswertung.md) in benannten Punkten teilweise ab).

### Gewählter Ansatz in einem Satz

Ein Foto bekommt pro Klassifizierungslauf **eine Rangfolgen-Zeile je Kategorie**, zu der es gehört (`photo_rankings.is_primary` unterscheidet Haupt- von Nebenkategorie); die Hauptkategorie entsteht unverändert über die feste Vorrangreihenfolge, die Nebenkategorien ausschließlich aus der bereits persistierten Modellkonfidenz, und dieselbe Konfidenz dämpft — begrenzt — den Sortierschlüssel innerhalb einer Kategorie.

### Migration

Alembic, `down_revision` = der zum Umsetzungszeitpunkt tatsächliche Head (nicht aus dieser Spec abschreiben, sondern nachsehen), ein `batch_alter_table("photo_rankings")`:

1. `add_column("is_primary", sa.Boolean(), nullable=False, server_default=sa.true())` — jede bestehende Zeile ist die Hauptzeile ihres Fotos; das ist die bis hierhin geltende Invariante, keine Schätzung.
2. `alter_column("is_primary", server_default=None)` — der Default versorgt den Altbestand und verschwindet danach; sonst erzeugte ein Schreibpfad, der die Spalte vergisst, still eine zweite Hauptkategorie.
3. `drop_constraint('uq_photo_ranking_run_photo', type_='unique')` + `create_unique_constraint('uq_photo_ranking_run_photo_category', ['criterion_scoring_run_id', 'photo_id', 'category_key'])`. Beide Constraints in `upgrade()` **und** `downgrade()` **benannt** (`Base.metadata` hat keine `naming_convention`, unbenannt ist unter SQLite nicht droppbar — dieselbe Falle wie in der Revision zu Spec 0299). `downgrade()` löscht vor dem Zurücktauschen `DELETE FROM photo_rankings WHERE is_primary = false`.

**Abwärtskompatibilität ohne Sonderfallcode:** Läufe von vor der Umstellung behalten ihre Zeilen (`is_primary=true`, keine Nebenzeilen). Klassifizierungszeilen von vor Spec 0299 tragen `NULL` in `detected_category_confidences` und erzeugen auch in einem neuen Lauf keine Nebenkategorie. Ohne aktivierte Cloud-Klassifizierung existiert gar keine Klassifizierungszeile → keine Nebenkategorien, keine Dämpfung, Verhalten exakt wie heute.

### Ableitung der Nebenkategorien

Neu in `categories.py` (dort und nicht in `ranking.py`/`worker.py`, weil es eine Aussage über die **Taxonomie** ist — dieselbe Trennung wie ADR 0049 Punkt 1):

```python
SECONDARY_CATEGORY_MIN_CONFIDENCE = 0.7

def usable_confidence(value: object) -> float | None
def secondary_categories(confidences: Mapping[str, object], primary_key: str) -> tuple[str, ...]
```

Liefert in Registry-Anzeigereihenfolge alle Schlüssel, die (a) im festen Set stehen, (b) nicht die Hauptkategorie sind, (c) nicht `nicht_erkannt` sind und (d) eine Zahl `>= SECONDARY_CATEGORY_MIN_CONFIDENCE` tragen (inklusiv, wie `category_presence_threshold`). Einzige Eingabe ist die Konfidenz-Abbildung — ein Schlüssel mit Zahl ist konstruktionsbedingt ein erkannter Schlüssel (ADR 0067 Punkt 2), ein erkannter Schlüssel ohne Zahl ist per Akzeptanzkriterium keine Nebenkategorie. Die Iteration läuft über `CATEGORY_REGISTRY` (nicht über die Eingabe) und ist damit zugleich die dritte Verteidigungslinie gegen einen Fremdwert.

**Lesepfad-Härtung (Muss, siehe Security Punkt 2):** Die Funktion liest die JSON-Spalte, deren Typzusage über die Datenbank statt über den Parser läuft. Ein Wert, der nicht `int`/`float` (ohne `bool`, endlich) im Band `[0, 1]` ist, gilt als **„keine Angabe"** — nicht als `0.0`.

**`usable_confidence` ist die eine Stelle, an der „was gilt als Angabe" beantwortet wird** (Umsetzungsentscheidung, gegenüber dem ADR-Entwurf präzisiert): sie steht in `categories.py` und wird von `ranking.py` importiert, statt in beiden Modulen ein zweites Mal geschrieben zu werden — zwei Kopien könnten auseinanderlaufen, und genau das ist der Fehler, den die Härtung verhindern soll. Deshalb tragen beide Funktionen `object` statt `float | None` bzw. `Mapping[str, float]`: die engere Annotation behauptete gerade das, was am Lesepfad zu prüfen ist, und die Prüfung sähe für den Typprüfer wie toter Code aus. Die Werte stammen aus `detected_category_confidences`; der Aufrufer reicht sie unverändert durch.

**Lokale Signale erzeugen nie eine Nebenkategorie** — sie tragen keine mit der Modellaussage vergleichbare Zahl (das Skalenproblem, an dem ADR 0047 gescheitert ist). `resolve_category` und `derive_photo_category` bleiben unverändert; der Invariantentest aus ADR 0067 Punkt 1 bleibt gültig.

### Gewichtung der Rangfolge

Neu in `ranking.py`:

```python
CONFIDENCE_RANK_PENALTY = 0.15

def confidence_ordering_score(rank_score: float, confidence: object) -> float:
    number = usable_confidence(confidence)
    if number is None:
        return rank_score
    return rank_score - CONFIDENCE_RANK_PENALTY * (1.0 - number)
```

`rank_photos(candidates, weights, confidences: Mapping[int, object] | None = None)` sortiert nach diesem Wert (Tie-Break unverändert: kleinere `photo_id`), gibt aber in `RankedPhoto.rank_score` weiterhin den **ungedämpften** Wert zurück. Ohne den neuen Parameter verhält sich die Funktion exakt wie bisher. Der gedämpfte Wert wird nicht persistiert. Dieselbe Lesepfad-Härtung wie oben, und zwar buchstäblich dieselbe Funktion (`usable_confidence` aus `categories.py`): ein entarteter persistierter Wert wird zu `None` (keine Dämpfung), nie zu `0.0` (volle Dämpfung) — `None` ist die Wahl, die nachweislich kein Foto schlechter stellen kann.

Die verwendete Zahl ist die Konfidenz **zum Schlüssel der jeweiligen Partition** (`detected_category_confidences.get(category_key)`) — damit wird nie zwischen zwei Kategorien verglichen, sondern immer nur zwischen zwei Fotos derselben Kategorie.

Zwei nachprüfbare Zusagen (je ein literaler Testfall):

- **„verdrängt kein deutlich besser bewertetes Foto":** Der Abzug liegt in `[0, 0.15]` (Konfidenzen sind seit Spec 0299 auf `[0, 1]` validiert). Liegt der Rang-Score eines Fotos um **mehr als** `CONFIDENCE_RANK_PENALTY` über dem eines anderen derselben Kategorie, kann keine Konfidenzdifferenz die Reihenfolge der beiden umkehren.
- **„ohne Sicherheitsangabe nicht schlechter als heute":** Der eigene Sortierwert bleibt unverändert, jeder andere derselben Partition wird kleiner oder gleich — die Position kann nur gleich bleiben oder besser werden. Eigenschaft der Formel, keine Zusatzprüfung.

Additiv statt multiplikativ, weil `rank_score` ein auf `[0, 1]` normierter gewichteter Mittelwert ist: auf dieser Skala ist ein Abstand eine Aussage, ein Faktor nicht (und ein Faktor bestrafte gut bewertete Fotos absolut stärker als schlecht bewertete — genau verkehrt herum). **`rank_score` bleibt bewusst ungedämpft**, weil er im Frontend die grobe Qualitäts-Einordnung trägt (`utils/qualityLevel.ts`): gedämpft hätte dasselbe Foto in zwei Kategorien zwei verschiedene „Bildqualitäten".

### Datenfluss von der Klassifizierung bis zur Bestbild-Auswahl

1. **Cloud-Phase** (`worker.py::run_remote_category_classification`) — **unverändert**.
2. **RANKING-Teilschritt** (`worker.py::run_criterion_scoring`): `_remote_category_candidates` wird zu `_remote_category_evidence` und liefert je Foto Kandidatenliste **und** Konfidenz-Abbildung (ein frozen Dataclass `RemoteCategoryEvidence(candidates, confidences)`, von `worker.py` und `api/photos.py` gemeinsam genutzt). Je Foto:
   - `primary = score.category_override or derive_photo_category(values, evidence.candidates)` — unverändert;
   - `secondary = secondary_categories(evidence.confidences, primary)`;
   - je Zugehörigkeit eine Partition `(cluster_key, category_key)` befüllen, dazu die Konfidenz für diese Partition: `None`, wenn es die Hauptzeile eines Fotos **mit aktivem Override** ist, sonst `evidence.confidences.get(category_key)`;
   - `rank_photos(partition, DEFAULT_CRITERION_WEIGHTS, confidences)` je Partition, `PhotoRanking(..., is_primary=...)` schreiben.
3. **Kuratierung/Bestbild** (`api/photos.py::_top_n_per_category_photo_ids`): Query strukturell unverändert — `row_number()` je `(cluster_key, category_key)` nach `rank_position`, berechnet nach dem `REJECTED`-Filter des aktuellen Nutzers. Ein Foto kann jetzt in mehreren Partitionen unter die Top-N fallen; `top_n` wirkt weiterhin je Partition. Die Funktion gibt zusätzlich das berechnete `rn` je `(photo_id, category_key)` zurück (siehe `curation_position`).

### API-Auswirkungen

`api/photos.py`:

- **`PhotoOut.ranking: RankingOut | None` entfällt ersatzlos**, ersetzt durch `PhotoOut.rankings: list[RankingOut]` (immer eine Liste, analog `ratings`; leer, solange kein erfolgreicher Lauf existiert). Der brechende Feldwechsel ist beabsichtigt: der Compiler soll an jeder Lesestelle erzwingen, dass sie sich entscheidet, welche Zugehörigkeit sie meint. In beiden Modi enthält `rankings` alle Zugehörigkeiten des Fotos im letzten erfolgreichen Lauf. **Reihenfolge festgelegt: Hauptzeile zuerst**, danach die Nebenzeilen in Registry-Anzeigereihenfolge (sonst flackert die Anzeige mit der Zeilenreihenfolge der Datenbank).
- `RankingOut` neu: `is_primary: bool` und `curation_position: int | None`. `curation_position` ist der Platz dieser Zugehörigkeit in der um die eigenen Ablehnungen bereinigten Auswahl ihrer Kategorie; `null`, wenn diese Zugehörigkeit nicht zur angeforderten Auswahl gehört oder keine angefordert wurde. `rank_position`/`partition_size` bleiben unverändert die lauf-globale, ungefilterte Rangaussage des Info-Popovers — ausdrücklich nicht dieselbe Zahl.
- `_current_ranking_for_photo` filtert auf `is_primary.is_(True)`. **Achtung Kardinalitätswechsel:** `scalar_one_or_none()` wirft ab der zweiten Zeile, und `_rankings_by_photo_id` baut heute ein `dict[int, PhotoRanking]`, das ab jetzt **still** verliert. Jede Lesestelle wird auf 1:N umgestellt, nicht nur die offensichtliche.
- `PUT /photos/{id}/category-override`: Statuscodes unverändert (`404`/`422`). Zielt der Override auf eine Kategorie, die bereits **Neben**kategorie ist, gibt es **kein** `409` — die Hauptzeile ersetzt die Nebenzeile. Ein `IntegrityError` aus dem neuen Constraint wird zu `409`, nie zu einer 500 (Security Punkt 5).
- `DELETE /photos/{id}/category-override`: rekonstruiert wie bisher die automatische Hauptkategorie über denselben Codepfad; die Nebenzeilen werden dabei neu abgeleitet.
- `PhotoListOut.items` enthält jedes Foto weiterhin **höchstens einmal**.

`worker.py::reassign_photo_category` (Signatur unverändert) stellt jetzt die **gesamte** Zugehörigkeitsmenge eines Fotos für den Lauf her: Zielmenge = neue Hauptkategorie + `secondary_categories(confidences, neue_hauptkategorie)`; überzählige Zeilen löschen, fehlende anlegen, alle betroffenen Partitionen (alte ∪ neue Kategorien) mit Konfidenzen neu ranken, ein `commit()`. **Vorher die Sperre setzen** (Security Punkt 5): `with_for_update()` auf der `photo_scores`-Zeile des Fotos als erste Anweisung, vor dem Lesen der Ranking-Zeilen.

`api/stats.py::_ranking_counts_by_category` und `category_diff.py::collect_assignments` filtern auf `is_primary == True`. `_partition_sizes` zählt dagegen **alle** Zeilen der Partition. Zwei Zählweisen, zwei Fragen.

Unberührt: `GET /categories`, Ausschuss-Erkennung, Statistikblock `category_confidence`, Feinlabel-Auswertung, Kostenerfassung, `project_deletion.py`, `pricing.py`.

### Frontend

- `api/types.ts`: `RankingOut` um `is_primary`/`curation_position` erweitert (beide pflichtig); `PhotoOut.ranking` → `rankings: RankingOut[]`.
- Neues reines Modul `utils/rankings.ts`: `primaryRanking(photo)` (Hauptzugehörigkeit oder `null` — nie „das erste Element") und `curatedRankings(photo)` (Zugehörigkeiten mit `curation_position !== null`, geprüft auf `!== null`, nicht auf Falsyness).
- `CurateCategoriesPage.tsx::groupByClusterAndCategory` iteriert je Foto über `curatedRankings(photo)`. Der React-Key der Kachel wird `${photo.id}-${category_key}` — `photo.id` allein ist beim Mehrfachrendering desselben Datensatzes keine belastbare Zusage mehr. `countPhotosInDay` zählt **eindeutige Fotos** (Kriterium 26).
- `PhotoDetailPage.tsx`/`PhotoGridPage.tsx` verwenden `primaryRanking(photo)`.
- `CriterionDetailsPopover`/`CriterionDetailsList` bekommen zusätzlich `rankings` und weisen die Rollen aus (siehe UI/UX).
- Der clientseitige „unsicher"-Filter der Kuratierung bleibt unverändert.
- `demo_state.py` erzeugt deterministisch die in der Teststrategie genannten Fälle, damit der Zustand in `browse-app` und im `e2e`-Lauf sichtbar ist.

### Umsetzungsreihenfolge (verbindlich, `developer` plant nicht selbst)

1. **`categories.py`**: `SECONDARY_CATEGORY_MIN_CONFIDENCE` + `secondary_categories()` inkl. Lesepfad-Härtung. Reine Funktion, keine Abhängigkeit — zuerst, weil alles Weitere sie benutzt.
2. **`ranking.py`**: `CONFIDENCE_RANK_PENALTY` + `confidence_ordering_score()` + `rank_photos(..., confidences=None)`.
3. **Migration + `models.py`**: `is_primary`, Constraint-Tausch, `downgrade()` inkl. `DELETE`.
4. **`worker.py::run_criterion_scoring`**: `_remote_category_evidence`, Zugehörigkeits-Schleife, `is_primary`, Konfidenz je Partition inkl. Override-Ausnahme.
5. **`worker.py::reassign_photo_category`**: Sperre, Zielmengen-Logik, Re-Ranking der betroffenen Partitionen.
6. **`api/photos.py`**: `RankingOut`-Felder, `rankings` (Hauptzeile zuerst), `curation_position`, alle Lesestellen auf 1:N, Override-Endpunkte inkl. `409`-Abbildung.
7. **`api/stats.py` + `category_diff.py`**: `is_primary`-Filter.
8. **`demo_state.py`**: die Demo-Fälle aus der Teststrategie.
9. **Frontend**: `types.ts` → `utils/rankings.ts` (+ Test) → `CurateCategoriesPage` → Detail-/Grid-Seite → Popover/Details → `SecondaryCategoryMarker`. `tsc` führt nach dem Entfallen von `PhotoOut.ranking` durch alle Fundstellen.
10. **`docs/architecture.md`** im selben PR fortschreiben (`PhotoRanking`, `PhotoOut.rankings`, die beiden neuen Konstanten); `docs/setup.md` bleibt unberührt (keine neue Umgebungsvariable, kein neuer Setup-Schritt).

## UI/UX

Grundsatz: Die Rolle einer Zugehörigkeit kommt ausschließlich aus `is_primary`; im Frontend wird keine Schwelle nachgebildet. Ohne Nebenkategorien ist die Oberfläche von heute nicht zu unterscheiden — kein Platzhalter, kein „keine Nebenkategorien"-Hinweis (Kriterium 24).

**Marker auf der Kuratierungskachel.** Eine Kachel, die unter einer ihrer Nebenkategorien steht, trägt einen dezenten Ecken-Marker nach dem Muster des bestehenden `CategoryOverrideMarker`: neue Komponente `SecondaryCategoryMarker.tsx`, gleicher Aufbau (`flex size-6 items-center justify-center rounded-full bg-bg/85 backdrop-blur-sm`), Symbol `↳` (`aria-hidden`), `role="img"` mit `aria-label="Nebenkategorie"` auf dem umschließenden Element. Das Zeichen ist bewusst ein Verzweigungspfeil und kein `↓`: es bezeichnet eine Nebenzugehörigkeit, keine Abwertung. Farbe trägt die Aussage nicht — der `aria-label` und die Rollenzeile in den Bewertungsdetails tun es.

**Marker-Kollision (Detailentscheidung dieser Spec).** `PhotoCard` hat genau einen `topLeft`-Slot, in dem bereits der `CategoryOverrideMarker` sitzen kann. Ein übersteuertes Foto, das anderswo als Nebenkategorie steht, braucht beide. Der Slot nimmt deshalb einen `flex gap-1`-Container: **Override-Marker zuerst, Nebenkategorie-Marker rechts daneben** — kein Stapeln, kein Verdrängen. Zwei `size-6`-Kreise nebeneinander passen auch im 360px-Viewport in die Ecke. Die Demo-Daten enthalten diesen Fall, damit er im Browser prüfbar ist.

**Rollen in den Bewertungsdetails.** `CriterionDetailsList` (geteilt von Detailseite, Grid und Kuratierung) bekommt unterhalb der bestehenden Kandidatenliste eine Sektion „Kategorien dieses Fotos", sichtbar nur bei `rankings.length > 1`. Je Zeile der Kategoriename (über den vorhandenen `formatCategoryKey`-Fallback) plus ein Text-Kennzeichen „Haupt" bzw. „Neben" als `Badge tone="neutral"` — als Text, nicht als Farbe. Die Konfidenzzahlen aus Spec 0299 werden hier **nicht** wiederholt; sie stehen unverändert in der Kandidatenliste darüber. In der Kuratierung weist die Zeile zusätzlich die Rolle **an dieser Stelle** aus (`is_primary` der gerenderten Zugehörigkeit).

**Zustände.** Kein Lauf: `rankings` ist leer, Anzeige wie heute. Genau eine Zugehörigkeit: weder Marker noch Rollensektion. Override aktiv: Override-Marker wie bisher, Rollensektion zeigt die übersteuerte Kategorie als „Haupt". Foto mehrfach sichtbar: jede Kachel trägt die Rolle ihrer eigenen Zugehörigkeit; die Qualitätsstufe (`qualityLevel`) ist an beiden Kacheln identisch, weil `rank_score` über alle Zugehörigkeiten gleich ist.

**Design-System.** Das Muster „Sekundär-Marker auf der Fotokarte" und die Erweiterung des `topLeft`-Slots auf mehrere Marker werden in [`specs/architecture/0004-design-system.md`](../architecture/0004-design-system.md) unter „Wiederkehrende Muster" ergänzt; der `design-system`-Skill bekommt denselben Hinweis in Kurzform.

## Security

Sicherheitsrelevant, kein Blocker. Kein neuer externer Dienst, kein neues Secret, kein neuer Endpunkt, keine Prompt-Änderung, kein zusätzlicher Datenfluss Richtung Cloud, keine neue Abhängigkeit, keine neue Umgebungsvariable — die Story arbeitet ausschließlich auf einer Zahl, die seit Spec 0299 bereits bezahlt, validiert und persistiert ist. Sicherheitsrelevant ist allein die **Rollenänderung** dieser Zahl: sie war anzeigend, sie wird steuernd. Fünf Punkte, davon vier Muss-Kriterien.

1. **Die steuernde Verwendung ist zulässig, aber nur mit bezifferter Wirkungsgrenze — Muss-Kriterium.** Spec 0299 hat als projektweite Zusage festgehalten, die Konfidenz gehe „in keine Auswahl, keine Sortierung, keine Filterung und keine Schwelle" ein, und dazu gesagt, ein Antasten sei ein eigener ADR-Anlass. ADR 0069 ist dieser Anlass; die Zusage wird deshalb nicht gebrochen, sondern durch eine engere, gleich harte ersetzt:
   - Die Zahl entscheidet **nie**, welche Kategorie die Hauptkategorie ist. `resolve_category` und `worker.py::derive_photo_category` behalten ihre Signatur über Schlüsseln allein; der Invariantentest aus Spec 0299 Akzeptanzkriterium 12 bleibt unverändert gültig.
   - Erlaubt ist genau zweierlei, beides strikt **innerhalb** einer Kategorie: ob eine zusätzliche Zugehörigkeit besteht, und an welcher Stelle das Foto in der Liste seiner eigenen Kategorie steht.
   - Jede dieser Wirkungen hat eine **nach oben bezifferte** Schranke. Das ist der Unterschied zum in ADR 0047 gescheiterten „höchster Wert gewinnt".

   Was ein präpariertes Bild dadurch zusätzlich erreichen kann: in bis zu drei weiteren Kuratierungspartitionen erscheinen, und dort um höchstens 0,15 auf der `[0, 1]`-Skala des Rang-Scores nach vorn rutschen. Es kann **nicht**: die Hauptkategorie erzwingen, einen Schlüssel außerhalb des festen Sets erzeugen, ein um mehr als 0,15 besser bewertetes Foto verdrängen, oder ein Foto ohne Angabe schlechter stellen. Der verbleibende Effekt setzt voraus, dass die Angreiferseite bereits eine Datei in die OpenCloud der Familie legen kann, also die Vertrauensgrenze schon überschritten hat. Kein neues Restrisiko im Sicherheitskonzept.

2. **Die Bandvalidierung aus Spec 0299 reicht am Parser-Rand aus, braucht aber eine zweite, lesende Verteidigungslinie — Muss-Kriterium.** `NaN` als Sortierschlüssel wirft in Python keinen Fehler, sondern macht jeden Vergleich `False` und erzeugt eine still falsche, von der Eingabereihenfolge abhängige Ordnung. Die Lücke liegt nicht am Parser, sondern am Lesepfad: `secondary_categories` und `confidence_ordering_score` lesen die JSON-Spalte, deren Zusicherung über die Datenbank statt über den Parser läuft. Beide behandeln einen Wert, der nicht `int`/`float` (ohne `bool`) im Band `[0, 1]` ist, wie **„keine Angabe"**. Neutralwert ist ausdrücklich `None` (keine Dämpfung), nie `0.0` (volle Dämpfung).

3. **Mengenbegrenzung: wirksam, aus zwei unabhängigen Gründen — kein Handlungsbedarf.** Die harte Schranke ist die Iteration über `CATEGORY_REGISTRY` statt über die Modellantwort: selbst eine vollständig entartete Abbildung könnte höchstens die Registry-Schlüssel treffen, und ihr Inhalt wird nie zum Schlüssel einer Ranking-Zeile. Die praktische Schranke ist `MAX_REMOTE_CATEGORIES_PER_PHOTO = 3` samt der Invariante `set(detected_category_confidences) <= set(detected_categories)` aus Spec 0299. Die tatsächliche Obergrenze je (Lauf, Foto) ist **vier** Zeilen, nicht drei — die Hauptkategorie kann aus einem lokalen Signal oder einem Override außerhalb der drei Remote-Schlüssel liegen. Das ist die Zahl, gegen die der Mengentest schreibt.

4. **Nutzertrennung über `curation_position`: kein Leck, aber zwei Muss-Kriterien gegen die naheliegende Optimierung.** Der Ablehnungsfilter in `_top_n_per_category_photo_ids` ist über `own_rejection.user_id == current_user_id` an den anfragenden Nutzer gebunden; die Bewertungen des jeweils anderen Nutzers gehen an keiner Stelle ein. Zwei Auflagen, weil das Feld dazu einlädt, sie zu brechen:
   - `curation_position` wird **nie** an `photo_rankings` persistiert und **nie** über Requests hinweg zwischengespeichert. Ein gespeicherter Wert bildete zwangsläufig die Ablehnungen *irgendeines* Nutzers ab und wäre für den anderen ein Leck.
   - Bekommt `GET /projects/{id}/photos` je eine Antwort-Zwischenspeicherung oder ein `ETag`, muss der Schlüssel den Nutzer enthalten. Heute existiert beides nicht — Auflage für später, kein Fund.

5. **Datenintegrität bei Nebenläufigkeit — hier fehlt eine Gegenmaßnahme, Muss-Kriterium.** Der neue Constraint verhindert eine doppelte Zugehörigkeitszeile; die zweite Invariante — *genau eine* Zeile mit `is_primary = true` je (Lauf, Foto) — ist durch **keine** Datenbankbedingung abgesichert. `reassign_photo_category` aktualisiert bisher eine bestehende Zeile, ab jetzt leitet es die gesamte Menge neu ab und schreibt/löscht Zeilen im Request-Pfad. Zwei überlappende Aufrufe für dasselbe Foto (zwei Nutzer, realistischer: ein Doppelklick auf lahmer Verbindung) können eine verlorene Aktualisierung, **zwei** Hauptzeilen oder **keine** hinterlassen. Zwei Hauptzeilen brechen still die Zusage, dass die Summe über alle Kategorien die Fotoanzahl ergibt. Gegenmaßnahmen, alle drei in die Umsetzung:
   - **Sperre auf dem Anker vor dem Lesen:** `with_for_update()` auf der `photo_scores`-Zeile des Fotos als **erste** Anweisung von `set_category_override`/`delete_category_override`, vor dem Lesen der Ranking-Zeilen; die Neuableitung bleibt in der bestehenden Transaktion. Unter PostgreSQL serialisiert das konkurrierende Overrides desselben Fotos, unter SQLite ist die Schreibtransaktion ohnehin serialisiert — testneutral, eine Zeile.
   - **`IntegrityError` aus dem neuen Constraint wird zu `409`, nie zu einer 500.**
   - **Test auf die Invariante**, nicht nur auf das Ergebnis: nach jeder Override-Folge existiert genau eine Zeile mit `is_primary = true` je (Lauf, Foto).

   Nicht betroffen: ein *laufender* Klassifizierungslauf — er schreibt unter einer neuen `criterion_scoring_run_id`, während der Lesepfad am letzten erfolgreichen Lauf hängt.

**Ausdrücklich geprüft und ohne Befund:** kein neuer Fremdtext in Persistenz, Antwort oder Log; Auth unverändert (kein neuer Endpunkt, Whitelist-Prüfung des Override-Keys bleibt erste Anweisung nach dem 404-Pfad); `is_primary` ist ein Bool, `curation_position` eine Zahl — keine Textfläche; keine Kostenwirkung. Das Sicherheitskonzept [`0003`](../architecture/0003-securitykonzept.md) ist fortgeschrieben (neuer Abschnitt „Nebenkategorien: die Modellkonfidenz steuert erstmals"; die projektweite Absolutzusage aus Spec 0299 ist durch die engere Fassung aus Punkt 1 ersetzt).

## Teststrategie

Das Testkonzept [`0002`](../architecture/0002-testkonzept.md) ist um zwei Sektionen fortgeschrieben (Backend „Aus 1:1 wird 1:N", Frontend „Dasselbe Foto zweimal auf einem Bildschirm").

**Ebenenaufteilung.** Die tragenden Zusagen sind reine Funktionen und Datenbank-Invarianten; der Schwerpunkt liegt auf **Backend/Unit** (`secondary_categories`, `confidence_ordering_score`/`rank_photos`, Migration) und **Backend/Integration** (Schreibpfad, Override, Endpunkte, Statistik). **Kein neuer E2E-Spec** — keine Zusage braucht eine Layout-Engine; Ausnahme nur, falls die beiden Ecken-Marker im 360px-Viewport tatsächlich kollidieren, dann kommt die Kuratierungsroute in `no-horizontal-scroll.spec.ts` (nur bei gelingendem Rot-Nachweis).

- **Backend/Unit:** `test_categories.py`, `test_ranking.py`, `test_models.py`, neu `test_migration_nebenkategorien.py`, `test_postgres_ddl_compatibility.py` (nur `upgrade()`), `test_migration_chain.py`.
- **Backend/Integration:** `test_worker_criterion_scoring.py`, `test_worker_reassign_photo_category.py`, `test_api_photos.py`, `test_api_category_override.py`, `test_api_stats.py`, `test_category_diff.py`, `test_demo_state.py`.
- **Frontend:** neu `utils/rankings.test.ts`; angepasst `CurateCategoriesPage.test.tsx`, `CriterionDetailsList.test.tsx`, `PhotoCard.test.tsx`; Fabrik-Anpassung (`rankings: []` statt `ranking: null`) in `PhotoGridPage.test.tsx`, `PhotoDetailPage.test.tsx`, `PhotoComparePage.test.tsx`, `api/photos.test.ts`, `hooks/usePhotos.test.tsx`. Ein geänderter **Zugriffspfad** dort ist angekündigt, eine geänderte **Erwartung** ein Review-Befund.

**Edge Cases, die sonst durchrutschen:**

- *Migration/Constraint-Tausch:* `downgrade()` an einer Tabelle **mit** Nebenzeilen; nach `upgrade()` das vorher verbotene Insert (gleicher Lauf+Foto, andere Kategorie) als Beweis, dass der alte Constraint wirklich weg ist — ein Namensvergleich bleibt grün, wenn `drop_constraint` unter SQLite still nichts tut; der neue Constraint wird ausgelöst; Altzeile trägt `true` **und** ein Insert ohne `is_primary` scheitert; `down_revision` gegen den tatsächlichen Head prüfen.
- *1:1 → 1:N (die eigentliche Bug-Klasse):* jede Lesestelle bekommt eine Fixture mit **zwei** Zeilen als Vorbedingung. `scalar_one_or_none()` wirft ab der zweiten Zeile, `_rankings_by_photo_id` verliert **still**. Reihenfolge in `PhotoOut.rankings` (Hauptzeile zuerst) festhalten.
- *Doppelvorkommen in Listen:* `len(ids) == len(set(ids))` auf `items` in Kuratierungs- **und** Grid-Modus; `rankings` ist leere Liste statt `null`; React-Key beim Mehrfachrendering; `countPhotosInDay` zählt eindeutige Fotos (Kriterium 26).
- *Gewichtungsformel:* Dominanz über ein deterministisches Wertegitter (Konfidenzen `{0, 0.25, 0.5, 0.75, 1}`, Score-Differenz knapp über der Konstante) **plus Gegenprobe** knapp darunter, in der sich die Reihenfolge tatsächlich umkehrt — ohne sie wäre der Test auch bei Penalty `0` grün. „Nie schlechter als vorher" als paarweiser Vergleich zweier Aufrufe derselben Funktion. `confidence=1.0` → Abzug exakt `0`, `0.0` → exakt die Konstante, `None` → Identität. Assertion auf die **Zahl** `rank_score` (ungedämpft, über alle Zeilen identisch). Tie-Break mit exakt darstellbaren Werten (Vielfache von `0.25`/`0.125`), sonst flackert der Float-Vergleich. Entartete persistierte Werte (`"0.9"`, `None`, `True`, `2.0`) direkt an den beiden reinen Funktionen. Keine neue Abhängigkeit (`hypothesis` bewusst nicht aufgenommen).
- *Override-Zusammenführung:* Override auf eine bestehende Nebenkategorie → vorher zwei Zeilen, nachher zwei (**nicht** drei); zwei getrennte Fälle für die alte Hauptkategorie (mit Konfidenz über der Schwelle bleibt sie als Nebenzeile, ohne Zahl wird ihre Zeile gelöscht); Override auf eine nie kandidierte Kategorie; Rücknahme = Mengengleichheit der `(category_key, is_primary)`-Paare mit dem automatischen Lauf; No-op bei Override auf die geltende Hauptkategorie; in jeder berührten Partition danach `rank_position` lückenlos `1..n`; nach jeder Schreiboperation die Invariante „genau eine `is_primary`-Zeile je (Lauf, Foto)" als Hilfsfunktion.
- *Zwei Zählweisen:* `_ranking_counts_by_category`/`collect_assignments` (nur `is_primary`) und `_partition_sizes` (alle Zeilen) in **einem** Testfall mit derselben Fixture gegeneinander — getrennte Positivtests bleiben beide grün, wenn der Filter an der falschen Stelle sitzt.
- *Frontend-Ableitung:* `primaryRanking` auf einer Liste ohne Hauptzeile → `null`; `curatedRankings` filtert auf `!== null`, nicht auf Falsyness; Qualitätsstufe desselben Fotos an zwei Kacheln identisch; Konfidenzfilter aus Spec 0299 und Nebenkategorie-Anzeige zusammen in einem Fall.
- *Demo-Daten:* je ein Foto mit zwei und mit drei Zugehörigkeiten, eines ohne Nebenkategorie, eines mit Override **und** Nebenkategorie (Marker-Kollision sichtbar), eines mit `detected_category_confidences = NULL`.
- *Schwellwert:* alle Verhaltenstests leiten Grenzfälle aus der **Konstante** ab; **genau ein** Test pinnt ihren literalen Wert, damit eine Wertänderung eine sichtbare Handlung ist statt eines stillen Nebeneffekts.

**Coverage-Gate (≥ 80 %)** unkritisch: der neue Anwendungscode ist klein und wird vollständig durchlaufen; `backend/alembic/versions/` liegt außerhalb von `--cov=photosort`, `demo_state.py` innerhalb.

## Entscheidungen

- **`architect` konsultiert (Schritt 1):** Ansatz übernommen, neue ADR 0069 angelegt; ADR 0049, 0021 und 0067 mit Teil-Vermerken versehen.
- **`ux-ui-designer` konsultiert (Schritt 2):** Ansatz in der Sache übernommen (Ecken-Marker nach dem Muster des `CategoryOverrideMarker`, Rollen als Text-Badges in den Bewertungsdetails). Redaktionell überarbeitet: Begriffe auf „Haupt"/„Neben" der Story vereinheitlicht (statt „Sekundär"), Symbol `↳` statt `↓` (ein Abwärtspfeil liest sich als Abwertung), und die vom Agenten am Design-System vorgenommenen Änderungen zurückgenommen, weil sie unbeteiligte Zeilen typografisch beschädigt hatten — die Muster werden im Umsetzungs-PR sauber nachgetragen.
- **`test-engineer` konsultiert (Schritt 3):** Akzeptanzkriterien geschärft, Kriterien 19–25 ergänzt, Testkonzept fortgeschrieben.
- **`security-engineer` konsultiert (Schritt 3):** Feature ist sicherheitsrelevant; Sicherheitskonzept fortgeschrieben. Sein Befund zur Nebenläufigkeit von `reassign_photo_category` (Punkt 5) ist als Muss-Kriterium in die Umsetzungsreihenfolge übernommen — er war im Architekturentwurf nicht enthalten. Ebenso die Lesepfad-Härtung (Punkt 2) und die Korrektur der Mengenobergrenze auf vier.
- **Daniel (Produktentscheidung):** `SECONDARY_CATEGORY_MIN_CONFIDENCE = **0.7**` — „Präzision vor Recall" statt der vom `architect` vorgeschlagenen 0,5. ADR 0069 Punkt 3 ist entsprechend nachgezogen, inklusive der Begründung, warum die dortige Gegenrede nicht mehr trägt, und des bewusst getragenen Preises: liefert das Modell durchgehend vorsichtige Zahlen, entstehen selten Nebenkategorien.
- **Daniel (Produktentscheidung):** `CONFIDENCE_RANK_PENALTY = **0.15**` — spürbar, aber gedeckelt; ein um mehr als 0,15 besser bewertetes Foto ist durch keine Sicherheitsdifferenz zu überholen.
- **Technische Detailentscheidungen** (innerhalb dieser Spec getroffen): Marker-Kollision wird durch Nebeneinanderstellen im `topLeft`-Slot gelöst, nicht durch Stapeln oder Verdrängen; die Tageszählung zählt eindeutige Fotos, weil die Beschriftung „N Fotos" lautet (Kriterium 26); `PhotoOut.rankings` liefert die Hauptzeile zuerst, damit die Anzeige nicht mit der Zeilenreihenfolge der Datenbank flackert; React-Key der Kuratierungskachel wird `photo.id` + `category_key`.
- **Bewusst hingenommen, für Daniel ausdrücklich festgehalten:** Auf dem realen Bestand entstehen **vorerst gar keine** Nebenkategorien. Kriterium 18 in Verbindung mit Spec 0299 Kriterium 9 (der Worker überspringt Fotos mit vorhandener Klassifizierungszeile, Kostenschutz) bedeutet, dass die Wirkung dieser Story erst mit der Folge-Story „Neu-Klassifizierung erzwingen" sichtbar wird — oder für Fotos, die ab jetzt neu klassifiziert werden.

## Offene Fragen

Keine. Die beiden Produktentscheidungen (Schwelle, Dämpfung) sind bei der Spec-Erstellung mit Daniel geklärt worden; die beiden vom `test-engineer` gemeldeten Detailfragen (Marker-Kollision, Tageszählung) sind als technische Detailentscheidungen innerhalb dieser Spec entschieden und oben festgehalten.

## Out of Scope

- **Die Hauptkategorie bleibt unberührt.** Welche Kategorie ein Foto als Hauptkategorie erhält, entscheidet unverändert allein die feste Vorrangreihenfolge. Zwei Kategorien werden nie anhand ihrer Zahlen gegeneinander abgewogen.
- **Kein Nachziehen bestehender Fotos.** Dass Nebenkategorien erst nach einem erneuten, kostenpflichtigen Klassifizierungslauf entstehen, ist bewusstes Verhalten.
- **„Neu-Klassifizierung erzwingen"** — eigene Folge-Story, hier ausdrücklich nicht enthalten.
- **Manuell gesetzte oder entfernte Nebenkategorien** sind nicht vorgesehen: sie geben die Modellaussage wieder, und das Datenmodell könnte eine handverlesene nicht davon unterscheiden.
- **Keine projekt- oder nutzerspezifische Schwelle**, keine Sichtbarkeit der beiden Konstanten in der Oberfläche.
- **Unverändert bleiben:** Ausschuss-Erkennung, Zählung in den Auswertungen (weiterhin die Hauptkategorie), Statistikblock `category_confidence`, Feinlabel-Auswertung, Kostenerfassung und der Klassifizierungs-Prompt.
