# 0069 - Nebenkategorien: ein Foto gehört mehreren Kategorien an, die Modellkonfidenz gewichtet die Rangfolge innerhalb einer Kategorie

**Status:** Accepted
**Teilweise abgelöst:** in **Punkt 8** ausschließlich die **Definition** von `curation_position` („der Platz dieser Zugehörigkeit in der um die eigenen Ablehnungen bereinigten Auswahl ihrer Kategorie") und die dort genannte **Begründung** ihrer Sicherheitsauflage, durch ADR [`0071`](./0071-kuratierung-stabile-auswahl-ohne-backfill-und-einsehbarer-vorrat.md). Dort entfällt der Ablehnungsfilter der Kuratierungsabfrage; der Wert ist danach der Platz in der angezeigten Auswahl und hängt nicht mehr vom anfragenden Nutzer ab. **Die Auflage selbst gilt weiter** — sie hat mit `PhotoOut.suggestion` (nur sichtbar ohne eigene Bewertung des Anfragenden) eine zweite, unberührte Ursache und wandert deshalb vom Feld an den Antwortaufbau: ein Antwort-Zwischenspeicher/`ETag` über `no-store` hinaus muss den Nutzer im Schlüssel führen. **Das Feld selbst, sein Zweck und seine Begründung bleiben unverändert** — es bleibt die alleinige Auskunft darüber, unter welchen Kategorien die Kuratierung ein Foto zeigt, und das Frontend bildet die Auswahlregel weiterhin nicht nach. Alles Übrige dieser ADR (Datenmodell der Mehrfachzugehörigkeit, konfidenzgewichtete Rangfolge, Sortierung, Migration) ist unberührt; die Abstufung ist in [`../README.md`](../README.md) beschrieben.
**Datum:** 2026-09-09
**Bezug:** [GitHub-Issue #300](https://github.com/TheRealKoller/photosort/issues/300), [`features/0300-nebenkategorien.md`](../features/0300-nebenkategorien.md), `architect`-Konsultation für Story #300 am 2026-09-09.

**Löst teilweise ab:**

- [`decisions/0049-festes-kategorien-set-mit-vorrangreihenfolge-und-freien-feinlabels.md`](./0049-festes-kategorien-set-mit-vorrangreihenfolge-und-freien-feinlabels.md) — dort **den letzten Aufzählungspunkt der Konsequenzen** („Ein späterer Wechsel des Grundprinzips — … Mehrfachzuordnung eines Fotos zu mehreren Kategorien … braucht eine neue ADR, die diese hier als ‚Superseded' markiert") und den Begründungs-Halbsatz in **Abschnitt 7a** („1:1 statt 1:N, weil pro Foto genau eine Kategorie entsteht — das ist die Kernaussage der Story"). Diese ADR **ist** die dort verlangte neue Entscheidung. Sie markiert ADR 0049 trotzdem nicht als `Superseded`, sondern als teilweise abgelöst: deren Kern gilt wörtlich weiter — das feste Set samt Definitionen und Vorrangreihenfolge (Abschnitte 1/2), der eine Kandidatenpool aus lokalen und remoten Signalen (Abschnitt 3), die lokal bestimmbare Teilmenge (Abschnitt 4), das geschlossene Antwortschema (Abschnitt 5), die Feinlabels (Abschnitt 6), Datenmodell und Migration im Übrigen (Abschnitt 7 — `photo_category_classifications` bleibt unverändert 1:1 zum Foto), die Override-Validierung (Abschnitt 8) und das Frontend ohne gespiegeltes Set (Abschnitt 9). Insbesondere gilt unverändert: **die Hauptkategorie bestimmt allein die Vorrangreihenfolge, nie ein Zahlenvergleich.** Die Formvorgabe „als Superseded markieren" stammt aus der Zeit vor der in [`../README.md`](../README.md) beschriebenen Abstufung; ihr Zweck („das ist nicht nebenbei änderbar, es braucht eine bewusste Entscheidung") ist mit dieser ADR erfüllt, ein volles `Superseded` wäre dagegen eine falsche Auskunft über das feste Set.
- [`decisions/0021-kriterien-datenmodell-kuratierungs-pipeline.md`](./0021-kriterien-datenmodell-kuratierungs-pipeline.md) — dort in **Punkt 4** ausschließlich der `UniqueConstraint(criterion_scoring_run_id, photo_id)` samt der Lesart „jedes Foto gehört zu genau einer Partition". Alles Übrige von Punkt 4 gilt unverändert und wird hier sogar tragend: der volle sortierte Pool statt nur der Top-N, und Backfill als reiner Query-Effekt (`row_number()` nach dem `REJECTED`-Filter) — beides funktioniert je Partition und damit unverändert, wenn ein Foto in zwei Partitionen steht.
- [`decisions/0067-modellkonfidenz-je-kategorie-anzeige-und-auswertung.md`](./0067-modellkonfidenz-je-kategorie-anzeige-und-auswertung.md) — dort **Punkt 1** in seiner Reichweite (die Grenze gilt ab hier für die **Haupt**kategorie: `resolve_category` bleibt buchstäblich unverändert und ohne Konfidenz-Parameter, aber die Konfidenz entscheidet ab jetzt über **Neben**kategorie-Zugehörigkeit und Reihenfolge) und **Punkt 6** vollständig („Keine Schwelle im Backend" und „Auch nicht entschieden wird eine serverseitige Sortierung nach Konfidenz"). Punkt 2 (die Zahl hängt am Schlüssel), Punkt 3 (kein Wert wird erfunden), Punkt 4 (zwei Spalten), Punkt 5 (Auswertung nach der Modell-Kategorie) und Punkt 7 (tolerantes Antwortschema) gelten unverändert.

## Kontext

ADR 0049 hat die Kategorie eines Fotos zu einer reinen Pro-Foto-Funktion über einem geschlossenen Set gemacht: aus allen in Frage kommenden Kategorien gewinnt die mit der kleinsten `precedence`. Das hat die Vorhersehbarkeit hergestellt, die die Kuratierung braucht — und zugleich eine Nebenwirkung erzeugt, die im Betrieb sichtbar wurde: **jede nicht gewinnende Kategorie eines Fotos wird weggeworfen.** Das Foto mit Kind und Hund steht unter „Menschen"; bei den Tierbildern fehlt es, obwohl es das beste Tierbild des Tages wäre. Der manuelle Override hilft nicht — er hängt das Foto um, statt es an beiden Stellen zu zeigen, und nimmt es damit aus „Menschen" heraus.

Der Verlust ist strukturell, nicht graduell: `resolve_category` reduziert eine Menge auf ein Element, und `PhotoRanking` hält diese Reduktion per `UniqueConstraint(run, photo)` fest. Die Information, die fehlt, liegt seit ADR 0049 vollständig vor (`detected_categories`) und seit ADR 0067 sogar mit einer Zahl je Kandidat (`detected_category_confidences`) — sie wird nur nirgends in eine zweite Zugehörigkeit übersetzt.

Zwei Vorgeschichten begrenzen, was hier entschieden werden darf:

- **ADR 0047/0049:** „höchster Wert gewinnt" ist im Produkt nachweislich gescheitert. Werte unterschiedlicher Skalen wurden verglichen, die unspezifischere Zahl gewann regelmäßig. Deshalb darf keine Zahl darüber entscheiden, **welche** Kategorie die Hauptkategorie ist.
- **ADR 0067 Punkt 6:** Eine Umsortierung der Kuratierung nach Konfidenz wurde ausdrücklich abgelehnt, weil sie der Ansicht „bestes Foto der Partition zuerst" genau ihre Aussage nähme. Diese Ablehnung war richtig für das, was sie ablehnte — eine Sortierung **nach** Konfidenz. Was Story #300 verlangt, ist etwas anderes: eine begrenzte **Gewichtung** der bestehenden Rangfolge, die die Qualitätsaussage nicht ersetzt, sondern nur bei sonst ähnlicher Bewertung ausschlägt.

Diese ADR trennt deshalb konsequent zwei Fragen, die im bisherigen Code eine waren: **„welche Kategorie gilt für dieses Foto"** (unverändert Vorrangreihenfolge, keine Zahl) und **„in welchen Kategorien taucht dieses Foto auf und an welcher Stelle"** (neu, und dort ist die Zahl zuständig).

## Entscheidung

### 1. Die Mehrfachzugehörigkeit lebt in `photo_rankings` — eine Zeile je (Foto, Kategorie), unterschieden durch `is_primary`

`photo_rankings` bekommt eine Spalte `is_primary: bool` (NOT NULL). Der Unique-Constraint wandert von `(criterion_scoring_run_id, photo_id)` auf `(criterion_scoring_run_id, photo_id, category_key)`: ein Foto steht pro Lauf höchstens einmal **je Kategorie**, aber in mehreren Kategorien. Genau eine dieser Zeilen trägt `is_primary=True`.

**Verworfen: eine eigene Tabelle `photo_secondary_rankings`.** Sie hätte `photo_rankings` unangetastet gelassen und dafür jede lesende Stelle verdoppelt: die Kuratierungs-Query (`row_number()` je Partition nach dem Ablehnungsfilter) müsste über eine `UNION` laufen, die Partitionsgrößen ebenso, und die Rangfolge innerhalb einer Kategorie wäre über zwei Tabellen verteilt — obwohl die Story ausdrücklich **eine** gemeinsame Liste je Kategorie verlangt. Zwei Tabellen für zwei Zeilenarten derselben Sache sind hier die teurere Lösung, nicht die vorsichtigere.

**Verworfen: gar keine Persistenz — die Nebenzugehörigkeiten beim Lesen aus `detected_category_confidences` ableiten.** Das käme ohne Migration aus, verlangte aber, eine JSON-Abbildung in der Kuratierungs-Query zu Zeilen zu expandieren (in SQLite und PostgreSQL unterschiedlich zu schreiben, dieselbe Portabilitätsfalle wie in ADR 0067 Punkt 4) und Rangposition sowie Partitionsgröße einer Nebenkategorie zur Lesezeit zu berechnen. Die Rangfolge wird seit ADR 0021 Punkt 4 **bewusst persistiert**, weil der Backfill sonst nicht als reine Query funktioniert; für Nebenzugehörigkeiten kann nichts anderes gelten.

`is_primary` ist ein `bool` und kein Enum: es gibt genau zwei Zustände, und die Invariante „genau eine Hauptzeile je (Lauf, Foto)" ist als Bedingung über einem Wahrheitswert direkt lesbar. Der Wert wird an keiner Stelle mit einem Default geschrieben — die Migration setzt ihn einmalig für den Altbestand und entfernt den `server_default` danach wieder (Punkt 9), damit ein Schreibpfad, der ihn vergisst, auffällt statt still eine zweite Hauptkategorie zu erzeugen.

### 2. Die Hauptkategorie bleibt buchstäblich unberührt; die Nebenkategorien sind eine zweite, getrennte Ableitung

`categories.py::resolve_category` und `worker.py::derive_photo_category` bleiben **unverändert** — gleiche Signatur, gleiche Regeln, kein Konfidenz-Parameter. Der Invariantentest aus ADR 0067 Punkt 1 (`resolve_category` hat genau einen Parameter, die Kategorie ist unabhängig von jeder Konfidenz reproduzierbar) bleibt gültig und wird nicht abgeschwächt.

Daneben tritt eine zweite reine Funktion in `categories.py`:

```python
def secondary_categories(confidences: Mapping[str, float], primary_key: str) -> tuple[str, ...]
```

Sie liefert in Registry-Anzeigereihenfolge alle Schlüssel, die (a) im festen Set stehen, (b) nicht die Hauptkategorie sind, (c) nicht `nicht_erkannt` sind und (d) eine Zahl `>= SECONDARY_CATEGORY_MIN_CONFIDENCE` tragen. Sie liest **ausschließlich** die Konfidenz-Abbildung und nicht `detected_categories`: ein Schlüssel mit Zahl ist konstruktionsbedingt ein erkannter Schlüssel (ADR 0067 Punkt 2), und ein erkannter Schlüssel ohne Zahl ist per Akzeptanzkriterium keine Nebenkategorie. Eine Eingabe, zwei Regeln, kein Abgleich zweier Listen, der auseinanderlaufen könnte.

Die Iteration über `CATEGORY_REGISTRY` statt über die Eingabe ist zugleich die dritte Verteidigungslinie gegen einen Fremdwert (nach der Validierung in `remote_classification.py` und der Persistenzform): ein Schlüssel außerhalb des Sets kann hier nicht durchfallen.

**Lokale Signale erzeugen niemals eine Nebenkategorie.** Sie tragen keine mit der Modellaussage vergleichbare Zahl — dasselbe Skalenproblem, an dem ADR 0047 gescheitert ist. Sie speisen unverändert die Kandidatenmenge der **Haupt**kategorie. Daraus folgt unmittelbar und ohne Sonderfallcode das Akzeptanzkriterium „ohne aktivierte Cloud-Klassifizierung verhält sich das Projekt wie bisher": ohne `photo_category_classifications`-Zeile gibt es keine Konfidenzen, ohne Konfidenzen keine Nebenkategorien und keine Dämpfung (Punkt 4).

### 3. Die Schwelle ist eine Konstante der Taxonomie, kein Konfigurationswert

`categories.py::SECONDARY_CATEGORY_MIN_CONFIDENCE = 0.7`, verglichen mit `>=` (inklusiv, wie `category_presence_threshold` in `criteria.py`). Anwendungsweit gleich, in keiner API-Antwort, in keiner Oberfläche, in keiner Umgebungsvariable.

Sie steht in `categories.py` und nicht in `ranking.py` oder `worker.py`, weil sie eine Aussage über die **Taxonomie** ist („ab wann gehört ein Foto zu einer Kategorie") und nicht über die Rangfolge — dieselbe Trennung, die ADR 0049 Punkt 1 zwischen Produkt-Taxonomie und Mess-Signal gezogen hat.

**Der Wert 0,7 ist eine Produktentscheidung Daniels, keine Kalibrierung** (Spec-Erstellung am 2026-09-09; zur Wahl standen 0,5, 0,6 und 0,7). Er folgt dem Grundsatz „Präzision vor Recall" aus ADR 0049 Punkt 4: Eine Nebenkategorie soll eine Aussage des Modells wiedergeben, nicht dessen Unentschiedenheit. Die Rollenteilung dieser ADR bliebe auch mit einer großzügigeren Schwelle tragfähig — Nebenkategorien werden nicht durch die Schwelle sortiert, sondern durch die Gewichtung (Punkt 4/5), und alles oberhalb der Schwelle findet über die Rangfolge seinen Platz. Der bewusst getragene Preis der strengen Wahl: Liefert das Modell durchgehend vorsichtige Selbsteinschätzungen, entsteht selten eine Nebenkategorie, und die Story wirkt sich im Alltag kaum aus. Das ist beobachtbar (Statistikseite je Kategorie, Spec 0299) und mit einer Ein-Zeilen-Änderung ohne Migration und ohne Schema-Wirkung korrigierbar; der Wert bleibt damit die am billigsten revidierbare Festlegung dieser ADR.

`nicht_erkannt` ist ausgeschlossen, weil es keine Motivaussage ist, sondern deren Abwesenheit — eine „Nebenkategorie Nicht erkannt" neben einer erkannten Hauptkategorie wäre ein Widerspruch in sich (ADR 0049 Punkt 2: es steht außerhalb der Vorrangreihenfolge und greift nur bei leerer Kandidatenmenge).

### 4. Die Konfidenz gewichtet die **Ordnung**, nicht den `rank_score`

`PhotoRanking.rank_score` bleibt der ungedämpfte, gewichtete Mittelwert der Kriterien-Werte — unverändert in Bedeutung, Berechnung und Wertebereich. Gedämpft wird ausschließlich der **Sortierschlüssel**, aus dem `rank_position` entsteht.

Das ist keine Feinheit, sondern die Bedingung dafür, dass diese Story keine zweite Aussage kaputtmacht: `rank_score` trägt im Frontend die grobe Qualitäts-Einordnung (`utils/qualityLevel.ts` → „Hohe/Gute/Einfache Bildqualität") und im Popover den Rang-Kontext. Würde die Konfidenz in den Wert selbst gerechnet, hätte **dasselbe Foto in zwei Kategorien zwei verschiedene Bildqualitäten** — eine offensichtlich falsche Aussage, erzeugt aus einer Zahl, die über Bildqualität nichts sagt. Getrennt gehalten gilt: `rank_score` ist über alle Zugehörigkeitszeilen eines Fotos identisch, `rank_position` ist es nicht.

Die sichtbare Folge ist beabsichtigt und gehört in die Dokumentation der Funktion: **`rank_position` ist innerhalb einer Partition nicht mehr monoton in `rank_score`.** Ein Foto kann mit höherem Rang-Score hinter einem anderen stehen; die Erklärung dafür steht bereits am Foto — die Konfidenz wird seit Spec 0299 angezeigt.

Der gedämpfte Wert wird **nicht persistiert**. Er ist ein Zwischenergebnis der Sortierung; ihn zu speichern hieße, eine zweite Zahl im Datenmodell zu führen, deren einziger Verwender die Reihenfolge ist, die daneben schon als `rank_position` steht (dieselbe Prüfung, mit der ADR 0067 Punkt 4 den einen redundanten Skalar *begründet* hat — dort gab es einen SQL-Verwender, hier gibt es keinen).

### 5. Die Formel: ein begrenzter Abzug, mit nachprüfbarer Zusage

In `ranking.py`:

```python
CONFIDENCE_RANK_PENALTY = 0.15

def confidence_ordering_score(rank_score: float, confidence: float | None) -> float:
    if confidence is None:
        return rank_score
    return rank_score - CONFIDENCE_RANK_PENALTY * (1.0 - confidence)
```

`rank_photos` bekommt einen optionalen Parameter `confidences: Mapping[int, float | None] | None` und sortiert nach diesem Wert (Tie-Break unverändert: kleinere `photo_id` gewinnt); `RankedPhoto.rank_score` bleibt der ungedämpfte Wert. Ohne den Parameter verhält sich die Funktion exakt wie bisher.

Beide Akzeptanzkriterien werden damit zu Zusagen, die man hinschreiben und testen kann:

- **„Geringere Sicherheit rutscht nach hinten, verdrängt aber kein deutlich besser bewertetes Foto":** Der Abzug liegt für jede zulässige Konfidenz in `[0, 0.15]` (die Werte sind seit ADR 0067 Punkt 3 auf `[0, 1]` validiert). Daraus folgt: **liegt der Rang-Score eines Fotos um mehr als `CONFIDENCE_RANK_PENALTY` über dem eines anderen derselben Kategorie, kann keine Konfidenzdifferenz die Reihenfolge der beiden umkehren.** „Deutlich besser" ist damit exakt beziffert (0,15 auf der `[0, 1]`-Skala des Rang-Scores) statt eine Absichtserklärung zu bleiben.
- **„Ein Foto ohne Sicherheitsangabe steht nicht schlechter als heute":** Sein eigener Sortierwert ist unverändert, jeder andere Wert derselben Partition ist kleiner oder gleich seinem bisherigen. Seine Position kann deshalb nur gleich bleiben oder besser werden — nie schlechter. Das ist eine Eigenschaft der Formel, keine Zusatzprüfung im Code.

**Additiv und nicht multiplikativ**, weil `rank_score` bereits ein auf `[0, 1]` normierter gewichteter Mittelwert ist: auf dieser Skala ist ein Abstand eine Aussage, ein Faktor nicht. Ein Faktor würde zudem gut bewertete Fotos absolut stärker bestrafen als schlecht bewertete — genau verkehrt herum.

**Verglichen wird ausschließlich innerhalb derselben Kategorie**, weil der Sortierwert je Partition gebildet wird und die verwendete Zahl die Konfidenz **zum Schlüssel dieser Partition** ist (`detected_category_confidences.get(category_key)`, ADR 0067 Punkt 2: die Zahl folgt dem Schlüssel). Zwei Kategorien werden an keiner Stelle anhand ihrer Zahlen gegeneinander abgewogen — die Abgrenzung der Story ist strukturell erfüllt, nicht durch Disziplin.

### 6. Die manuelle Übersteuerung setzt die Hauptkategorie, lässt die Nebenkategorien stehen — und wird selbst nicht gedämpft

Ein Override schreibt weiterhin ausschließlich `PhotoScore.category_override` und bestimmt darüber die Hauptzeile. Die Nebenzeilen werden **aus der Modellaussage neu abgeleitet**, nicht mitverschoben: `secondary_categories(confidences, neue_hauptkategorie)`. Drei Folgen, alle gewollt:

- Die bisher automatisch ermittelte Hauptkategorie wird nach dem Übersteuern zur **Nebenkategorie**, sofern sie die Schwelle erreicht. Das Foto verschwindet also nicht mehr aus der Kategorie, aus der es umgehängt wurde — genau die Beschwerde, mit der die Story beginnt.
- Wird auf eine Kategorie übersteuert, die bereits Nebenkategorie war, entsteht **keine zweite Zeile** in derselben Partition: die Hauptzeile ersetzt die Nebenzeile. Der Endpunkt antwortet nicht mit `409`, sondern führt die Zusammenführung durch — der neue Unique-Constraint erzwingt sie ohnehin.
- Die Nebenkategorien selbst sind nie manuell setzbar oder entfernbar. Sie geben die Modellaussage wieder; eine handverlesene Nebenkategorie wäre eine Aussage über das Bild, die das Datenmodell nicht von der Modellaussage unterscheiden könnte.

**Der Override-Pfad braucht eine Sperre** (Befund der `security-engineer`-Konsultation zu Spec 0300, nach dem ersten Entwurf dieser ADR ergänzt): `reassign_photo_category` aktualisierte bisher **eine** bestehende Zeile, leitet ab hier die gesamte Zugehörigkeitsmenge neu ab und schreibt und löscht dabei Zeilen — im Request-Pfad. Der neue Unique-Constraint trägt davon nur die halbe Invariante: er verhindert die doppelte Zugehörigkeitszeile, nicht das Wettrennen um „genau eine `is_primary`-Zeile je (Lauf, Foto)". Zwei überlappende Overrides desselben Fotos könnten sonst zwei Hauptzeilen oder keine hinterlassen und damit still die Summenzusage aus Punkt 8 brechen. Deshalb verbindlich: `with_for_update()` auf der `photo_scores`-Zeile des Fotos als **erste** Anweisung von `set_category_override`/`delete_category_override`, vor dem Lesen der Ranking-Zeilen; ein `IntegrityError` aus dem neuen Constraint wird zu `409`, nie zu einer 500.

**Eine manuell gesetzte Hauptzeile wird nicht gedämpft** (`confidence=None` für diese Zeile, unabhängig davon, was das Modell zu diesem Schlüssel gesagt hat). Eine menschliche Festlegung mit einer Modellzahl abzuwerten hieße, den Nutzer für die Unsicherheit des Modells zu bestrafen — und zwar sichtbar an der Stelle, an der er gerade korrigiert hat. Alle **automatischen** Zugehörigkeiten werden dagegen einheitlich gedämpft, Haupt- wie Nebenzeile: die Story verlangt **eine** Liste je Kategorie, und zwei Ordnungsregeln in einer Liste wären willkürlich.

### 7. Lesepfad: `PhotoOut.rankings` statt `PhotoOut.ranking`, und ein eigenes Feld für die Kuratierungsauswahl

`PhotoOut.ranking: RankingOut | None` wird zu `PhotoOut.rankings: list[RankingOut]` (immer eine Liste, analog `ratings`/`criterion_scores`; leer, solange kein erfolgreicher Lauf existiert). `RankingOut` bekommt zwei Felder:

- `is_primary: bool` — trägt beide Erkennbarkeits-Kriterien der Story: am Foto (welche seiner Kategorien ist die Haupt-, welche eine Nebenkategorie) und beim Durchsehen einer Kategorie (steht das Foto hier als Haupt- oder Nebenkategorie).
- `curation_position: int | None` — der Platz dieser Zugehörigkeit in der um die eigenen Ablehnungen bereinigten Auswahl ihrer Kategorie, also das bereits berechnete `row_number()` der Kuratierungs-Query; `null`, wenn diese Zugehörigkeit nicht zur angeforderten Auswahl gehört oder gar keine angefordert wurde.

**Warum ein eigenes Feld und nicht ein modusabhängiger Inhalt von `rankings`:** Der Client muss zwei verschiedene Fragen beantworten können — „welche Kategorien hat dieses Foto" (immer alle) und „in welchen Kategorien soll ich es in dieser Kuratierungsansicht zeigen" (nur die, die den Schnitt gemacht haben, und das kann nur der Server wissen, weil der Backfill-Filter serverseitig läuft). Würde `rankings` im Kuratierungsmodus nur die qualifizierten Zugehörigkeiten führen, wäre die Bedeutung desselben Feldes vom Query-Parameter abhängig, und einem nur als Nebenkategorie eingeblendeten Foto fehlte ausgerechnet die Angabe seiner Hauptkategorie. `rank_position`/`partition_size` bleiben unberührt: sie sind die lauf-globale, ungefilterte Rangaussage des Info-Popovers (ADR 0040-Erbe) und ausdrücklich nicht dieselbe Zahl.

**Verworfen: dasselbe Foto mehrfach in `items` ausliefern** (eine Antwortzeile je Zugehörigkeit). Das hätte die Frontend-Gruppierung unverändert gelassen, aber `PhotoListOut.items` die Eigenschaft genommen, dass eine `id` darin höchstens einmal vorkommt — und jede volle `PhotoOut`-Nutzlast (Kriterien-Werte, Cloud-Status, Feinlabels) bis zu dreimal wiederholt.

Die Kuratierungsansicht rendert ein Foto in einer Kategorie genau dann, wenn seine Zugehörigkeit zu dieser Kategorie ein `curation_position != null` trägt. `top_n` wirkt unverändert je Partition — eine Kategorie liefert genau so viele Vorschläge wie bisher, ein Foto kann in mehreren Kategorien vorgeschlagen werden.

### 8. Gezählt wird die Hauptkategorie

Jede Aggregation über `photo_rankings` filtert auf `is_primary == True`: die Kategorienverteilung der Statistikseite (`api/stats.py::_ranking_counts_by_category`) und das Vorher/Nachher-Werkzeug `category_diff.py::collect_assignments` (ADR 0047 Punkt 7, das eine Zuordnung je Foto abbildet). Damit bleibt die Summe über alle Kategorien die Fotoanzahl — die Zusage, die die Verteilung überhaupt lesbar macht.

Die **Partitionsgröße** (`_partition_sizes`, das „von N" im Popover) zählt dagegen ausdrücklich **alle** Zeilen der Partition, Haupt- wie Nebenzeilen: sie beantwortet „wie viele Fotos stehen in dieser Kategorie dieses Clusters", und dort steht ein Foto mit Nebenzugehörigkeit tatsächlich. Zwei Zählweisen, zwei Fragen — dieselbe Unterscheidung, die ADR 0067 Punkt 5 zwischen Bestandsverteilung und Erkennungsqualität getroffen hat.

Unberührt bleiben: die Ausschuss-Erkennung (`PhotoScore.suggested_status`, kennt keine Kategorie), der Statistikblock `category_confidence` (gruppiert unverändert über die Modell-Kategorie), die Feinlabel-Häufigkeit und die Kostenerfassung.

### 9. Migration und Altbestand: eine additive Spalte, ein getauschter Constraint, kein Backfill

Eine Alembic-Revision (`down_revision = 'b8c9d0e1f2a3'`), drei Schritte in einem `batch_alter_table("photo_rankings")`:

1. `add_column("is_primary", sa.Boolean(), nullable=False, server_default=sa.true())` — jede bestehende Zeile **ist** die Hauptzeile ihres Fotos; das ist keine Schätzung, sondern die bis hierhin geltende Invariante.
2. `alter_column("is_primary", server_default=None)` — der Default hat den Altbestand zu versorgen und danach zu verschwinden. Bliebe er stehen, würde ein Schreibpfad, der `is_primary` vergisst, still eine zweite Hauptkategorie erzeugen; die Invariante „genau eine Hauptzeile je (Lauf, Foto)" ist genau das, was die Spalte tragen soll.
3. `drop_constraint('uq_photo_ranking_run_photo')` + `create_unique_constraint('uq_photo_ranking_run_photo_category', ['criterion_scoring_run_id', 'photo_id', 'category_key'])` — beide **benannt**, in `upgrade()` wie in `downgrade()` (`Base.metadata` trägt keine `naming_convention`, ein unbenannter Constraint ist unter SQLite nicht droppbar; dieselbe Falle wie in Revision `b8c9d0e1f2a3`). Der `downgrade()`-Weg muss vor dem Zurücktauschen des Constraints die Nebenzeilen entfernen (`DELETE FROM photo_rankings WHERE is_primary = false`), sonst verletzt der alte Constraint die vorhandenen Daten.

**Kein Nachziehen bestehender Fotos**, in doppelter Hinsicht und ohne Sonderfallcode: Läufe von vor der Umstellung behalten ihre Zeilen unverändert (`is_primary=True`, keine Nebenzeilen) — Nebenkategorien entstehen erst mit dem nächsten Klassifizierungslauf. Und Klassifizierungszeilen von vor Migration `a3b4c5d6e7f8` tragen `NULL` in `detected_category_confidences`; sie erzeugen auch in einem neuen Lauf keine Nebenkategorie, weil ohne Zahl kein Maßstab existiert. Ein erneuter Cloud-Aufruf findet dafür nicht statt (das Skip-Kriterium aus ADR 0049/0067 bleibt unangetastet).

## Begründung

- **Die Reduktion war die Nebenwirkung, nicht das Ziel.** ADR 0049 brauchte eine eindeutige Kategorie, um die Kuratierung vorhersehbar zu gruppieren. Vorhersehbar bleibt sie auch mit Nebenkategorien: die Zugehörigkeit ist weiterhin eine reine Pro-Foto-Ableitung über einem geschlossenen Set, ohne Laufkontext und ohne Projektabhängigkeit. Was fällt, ist allein die Annahme, dass diese Ableitung **genau ein** Ergebnis haben muss.
- **Die Zahl bekommt eine Zuständigkeit, aber nicht die alte.** ADR 0047 ist daran gescheitert, dass eine Zahl entschied, **welche** Kategorie gilt. Hier entscheidet sie, **ob** eine weitere Zugehörigkeit besteht und **an welcher Stelle** — beides innerhalb einer Kategorie, nie zwischen zweien. Die gescheiterte Vergleichsart (zwei Kategorien anhand ihrer Zahlen) kommt an keiner Stelle vor; die neue (zwei Fotos derselben Kategorie) ist die einzige, für die die Zahlen überhaupt vergleichbar sind, weil sie dieselbe Frage an dasselbe Modell beantworten.
- **Die Begrenzung ist das ganze Argument gegen ADR 0067 Punkt 6.** Dort wurde eine Sortierung **nach** Konfidenz abgelehnt, weil sie die Aussage „bestes Foto zuerst" zerstört hätte. Ein auf `0,15` gedeckelter Abzug zerstört sie nicht: Die Rangfolge bleibt eine Qualitätsrangfolge, in der die Konfidenz nur dort ausschlägt, wo die Qualität kaum unterscheidet — und das ist überprüfbar, nicht behauptet (Punkt 5).
- **Die teuerste Alternative wäre gewesen, nichts zu persistieren.** Sie hätte keine Migration gekostet und dafür jede Leseoperation verkompliziert, den Backfill-Mechanismus untergraben und Dialekt-spezifisches JSON-SQL eingeführt. Eine Spalte und ein getauschter Constraint sind der kleinere Eingriff.

## Konsequenzen

- **Ein Foto kann in bis zu vier Kategorien erscheinen** — nicht drei: die drei Remote-Schlüssel (`MAX_REMOTE_CATEGORIES_PER_PHOTO = 3`, ADR 0049 Punkt 5) werden sämtlich zu Nebenkategorien, wenn die Hauptkategorie aus einem lokalen Signal (`LOCAL_CATEGORY_SIGNALS`) oder aus einem Override stammt und damit außerhalb dieser drei liegt (Befund der `security-engineer`-Konsultation zu Spec 0300). Vier ist die Zahl, gegen die der Mengentest schreibt. Der Kuratierungspool wächst entsprechend — bei `top_n ≤ 10` je Partition und der Größenannahme des Projekts (ADR 0002) bleibt er klein; eine neue Abfrage entsteht nicht, `photo_rankings` bekommt bis zu doppelt so viele Zeilen je Lauf.
- **`PhotoOut.ranking` entfällt ersatzlos.** Das ist ein brechender Feldwechsel in einer Antwort, die drei Ansichten lesen (Kuratierung, Grid, Detail). Er ist beabsichtigt: der Compiler soll an jeder Stelle erzwingen, dass sie sich entscheidet, welche Zugehörigkeit sie meint — ein beibehaltenes `ranking` neben `rankings` wäre genau die zweite, driftende Abbildung derselben Sache.
- **`rank_position` ist innerhalb einer Partition nicht mehr monoton in `rank_score`.** Wer das später als Defekt liest und „repariert", nimmt der Story ihre halbe Wirkung; die Docstrings von `rank_photos`/`confidence_ordering_score` und ein literaler Testfall halten es fest.
- **Neue Abhängigkeiten: keine. Neue Secrets: keine. Neue Cloud-Aufrufe: keine.** Die Nebenkategorien entstehen vollständig aus einer Modellantwort, die bereits bezahlt, validiert und persistiert ist — dasselbe Muster, mit dem ADR 0049 Punkt 4 zwei lokale Kategorien aus einer bereits berechneten Modellausgabe gewonnen hat. Der Prompt ändert sich nicht, die Kostenannahmen (`pricing.py`) bleiben unberührt und brauchen deshalb — anders als bei ADR 0049/0067 — **keine** erneute Nachrechnung.
- **Zwei Werte sind bewusst frei justierbar gehalten und gehören zusammen betrachtet:** `SECONDARY_CATEGORY_MIN_CONFIDENCE` (wie viel erscheint überhaupt) und `CONFIDENCE_RANK_PENALTY` (wie stark Unsicheres nach hinten rutscht). Beide sind Konstanten ohne Schema- oder API-Wirkung; eine Änderung wirkt ab dem nächsten Lauf bzw. sofort, ohne Migration. Beide sind **nicht gegen einen echten Fotokorpus kalibriert** — derselbe ausdrückliche Vorbehalt wie bei `SHARPNESS_REJECT_THRESHOLD` und den Schwellwerten in `qualityLevel.ts`.
- **`docs/architecture.md`** (Owner: `architect`) wird im Umsetzungs-PR fortgeschrieben: `PhotoRanking` (neue Spalte, neuer Constraint, mehrere Zeilen je Foto), `PhotoOut.rankings`, die neue Konstante samt Ableitungsfunktion in `categories.py` und die Gewichtung in `ranking.py`. `docs/setup.md` bleibt unberührt (keine neue Umgebungsvariable, kein neuer Setup-Schritt).
- **Was diese ADR ausdrücklich nicht öffnet:** manuell gesetzte oder entfernte Nebenkategorien, eine projekt- oder nutzerspezifische Schwelle, eine Sichtbarkeit der beiden Konstanten in der Oberfläche, und jede Form von Zahlenvergleich zwischen zwei Kategorien. Wer eines davon will, braucht eine neue ADR — die Grenze aus ADR 0047/0049 („die Kategorie bestimmt die Vorrangreihenfolge, nie ein Zahlenvergleich") gilt für die Hauptkategorie unverändert weiter.
