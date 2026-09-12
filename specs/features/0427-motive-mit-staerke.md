# 0427 - Motive mit Stärke statt einer Hauptkategorie

**Status:** Accepted
**Erstellt:** 2026-09-12
**Bezug:** [Issue #427](https://github.com/TheRealKoller/photosort/issues/427) (Story unter dem Zielbild [#424](https://github.com/TheRealKoller/photosort/issues/424))

**Umfang:** ein Mehrfaches des Richtwerts von rund 200 Zeilen. Die Story fasst drei Ebenen zugleich
an (Pipeline, Datenmodell, Oberfläche), läuft über drei Pull Requests und löst drei Specs und drei
ADRs ab. Vier Abschnitte tragen den Umfang, jeder aus einem eigenen Grund: „Architektur /
Umsetzung" und „UI/UX" führen die betroffenen Dateien je Schritt, weil der `developer` sie ohne
eigene Planung abarbeitet; „Security" führt einundzwanzig einzeln abhakbare Auflagen samt
Angriffsmodell und untersagter Alternative; „Teststrategie" benennt fünf Zusicherungen, die ohne
Ausnahme und ohne auffällige Anzeige brechen. Gekürzt ist, was nur belegt — Verdichtung dieser vier
Abschnitte würde eine Auflage oder eine Datei verlieren, nicht einen Verweis.

## Ziel

Heute bekommt jedes Foto genau eine Hauptkategorie, bestimmt durch eine feste Vorrangreihenfolge.
Diese Reihenfolge entscheidet unabhängig davon, wie sicher sich das Modell ist: Ein Gesicht im
Hintergrund gewinnt gegen eine klar erkannte Kathedrale, ein Auto am Bildrand gegen die Landschaft
dahinter. Nebenkategorien kommen erst ab einer festen Sicherheitsschwelle hinzu. Das Ergebnis sind
Fotos, die in Kategorien liegen, zu denen sie nicht passen.

Die Ursache steckt im Mechanismus, nicht im Modell: Ein Foto wird in genau eine Schublade
gezwungen, und welche das wird, entscheidet eine Rangliste statt des Bildinhalts. Für die
Kuratierung als Albumauswahl braucht kein Foto eine Hauptkategorie. Ein Foto zeigt mehreres
zugleich — Menschen vor einem Bauwerk beim Essen —, und genau diese Mischung soll die Auswahl
später nutzen können. Nutznießer sind die beiden Menschen, die mit PhotoSort ihre Reisefotos
durchsehen: Sie finden Fotos dort wieder, wo sie sie vermuten, und korrigieren eine
Fehleinschätzung, indem sie ein Motiv abwählen statt ein Foto umzuhängen.

## User Story

Als jemand, der seine Reisefotos mit PhotoSort durchsieht, möchte ich, dass jedes Foto alle Motive
trägt, die darauf zu sehen sind — jeweils mit einer Stärke statt einer einzigen Zuordnung —, damit
Fotos nicht länger in einer Kategorie landen, die eine Rangliste ausgewählt hat, und ich beim
Zusammenstellen eines Albums die tatsächliche Mischung eines Bildes nutzen kann.

## Akzeptanzkriterien

**Motive statt Hauptkategorie**

- [ ] Ein Foto trägt für jedes Motiv eine Stärke zwischen 0 und 1. Es gibt keine Hauptkategorie,
      keine Vorrangreihenfolge und keine feste Schwelle mehr, ab der ein Motiv „zählt".
- [ ] Sichtbar im Ergebnis: Ein Foto, auf dem das Modell ein Bauwerk deutlich und Menschen nur
      schwach erkennt, wird als Bauwerk stark und als Menschen schwach geführt — nicht umgekehrt.
- [ ] Es gibt genau acht Motive: Menschen, Landschaft, Bauwerk und Sehenswürdigkeit, Stadt und
      Straße, Tiere, Essen und Trinken, Aktivität, Detail und Stimmung.
- [ ] Jede der heute bestehenden Kategorien hat entweder eine benannte Entsprechung im Motivset
      oder fällt begründet weg — keine verschwindet unbemerkt. Prüfbar: Eine Abbildungstabelle
      führt jeden der dreizehn heutigen Kategorieschlüssel genau einmal, entweder auf einen
      Motivschlüssel oder auf „entfällt" samt Begründung; Vollständigkeit und Eindeutigkeit sind
      maschinell geprüft.
- [ ] „Dokument und Screenshot" ist kein Motiv mehr, sondern ein Ausschluss-Signal: Ein so
      erkanntes Foto trägt `excluded_document = true`, der Lesehelfer der wirksamen Stärken weist
      es als ausgeschlossen aus, die Statistik zählt es in keinem Band, und die Oberfläche bietet
      für es kein Korrektur-Bedienelement an.
- [ ] Ein Foto, auf dem kein Motiv erkennbar ist, trägt durchgehend niedrige Stärken und erscheint
      dadurch in keiner Auswahl. Es gibt keine Auffangkategorie „nicht erkannt" mehr.
- [ ] Eine erkannte Sehenswürdigkeit ist kein eigenes Motiv: Sie verstärkt „Bauwerk und
      Sehenswürdigkeit", und ihr Name steht für die Benennung des Ereignisses zur Verfügung.

**Lokale Erkennung als Rückfall**

- [ ] Liegt eine Modellaussage vor, bestimmt allein sie die Motivstärken. Lokal erkannte Objekte
      treten nie als Gegenkandidat dagegen an.
- [ ] Ohne Cloud-Klassifizierung liefert die lokale Erkennung Stärken für die Motive, die sie
      beurteilen kann; die übrigen bleiben bei 0. Dass eine Auswahl auf dieser schwächeren
      Grundlage beruht, ist erkennbar: Die Antwort nennt die Grundlage (`cloud`/`local`), die
      Oberfläche benennt sie, und die lokal nicht beurteilbaren Motive sind als solche
      gekennzeichnet statt mit „0 %" dargestellt. Welche Motive lokal beurteilbar sind, liefert
      `GET /motifs` mit; es gibt keine zweite Liste im Frontend.
- [ ] Ein lokal erkanntes Objekt wirkt nach seinem Anteil am Bild, nicht nach bloßer Anwesenheit:
      Ein bildfüllender Hund ergibt eine hohe Tier-Stärke, ein Hund am Bildrand eine niedrige.

**Korrigieren**

- [ ] Eine Korrektur besteht darin, ein Motiv als zutreffend oder als nicht zutreffend zu
      markieren. Es ist nie nötig, eine Stärke oder Zahl selbst einzuschätzen.
- [ ] Eine Korrektur schlägt die Einschätzung des Modells für dieses Foto und dieses Motiv und
      bleibt über weitere Klassifizierungsläufe hinweg erhalten.
- [ ] Zu einem Foto sind alle Motive mit ihrer Stärke einsehbar, und jedes einzelne lässt sich
      korrigieren.
- [ ] Die Korrekturen sind so festgehalten, dass die spätere Feedback-Story sie als Signal
      auswerten kann: Eine Korrekturzeile trägt Foto, Nutzer, Motiv, die Aussage zutreffend/nicht
      zutreffend und ihren Zeitpunkt, verweist auf **keinen** Klassifizierungslauf und wird von
      keinem Lauf gelöscht oder überschrieben.

**Übergang und Auswirkungen**

- [ ] Bereits klassifizierte Fotos erhalten Motivstärken erst bei einem Klassifizierungslauf, den
      der Nutzer selbst auslöst. Es entstehen keine ungefragten Cloud-Kosten.
- [ ] Bis ein Foto neu klassifiziert ist, ist erkennbar, dass es noch keine Motive trägt — es wirkt
      nicht wie ein Foto ohne erkennbares Motiv. Prüfbar: Ein Foto ohne Kopfzeile trägt in der
      Antwort **keine** Motiveinträge (nicht acht mit Wert 0) und zeigt an ihrer Stelle einen
      Hinweissatz; die Darstellung unterscheidet sich nachweisbar von der eines Fotos, dessen acht
      Stärken alle 0 sind.
- [ ] Die Statistik über die Motive ist neu festgelegt und ausgewiesen: Da ein Foto zu mehreren
      Motiven zählt, ergibt die Summe über alle Motive nicht mehr die Anzahl der Fotos. Die
      Erklärung dieser Zählweise ist **ohne Interaktion** sichtbar, nicht hinter einem Aufklapp-
      oder Popover-Element.
- [ ] Die bisherigen Festlegungen zu Hauptkategorie, Vorrangreihenfolge, Nebenkategorien und
      Konfidenz-Schwelle (Specs 0289, 0299, 0300; ADR 0049, 0067, 0069) sind ausdrücklich abgelöst
      und nicht stillschweigend umgangen.

## Datenmodell-Bezug

Drei neue Entitäten, beschrieben in [`docs/architecture.md`](../../docs/architecture.md):
`PhotoMotifAssessment` (die Kopfzeile je Foto: welche Grundlage beurteilt hat, Ausschluss-Flag),
`PhotoMotifStrength` (acht Stärkezeilen je Kopfzeile) und `PhotoMotifCorrection` (Foto × Motiv ×
zutreffend/nicht zutreffend, lauf-unabhängig).

Entfallende Entitäten und Felder: `PhotoCategoryClassification` vollständig,
`photo_rankings.category_key`, `photo_rankings.is_primary`, `photo_scores.category_override`.

## Architektur / Umsetzung

Grundlage: ADR [`0091`](../decisions/0091-motive-mit-staerke-statt-hauptkategorie.md) (löst ADR
0049, 0067 und 0069 ab, berührt 0047 Punkt 7 und 0071 im Partitionsschlüssel). Die dort
festgelegten acht Punkte sind hier nicht wiederholt; dieser Abschnitt nennt Dateien, Reihenfolge
und Grenzen.

### Gewählter Ansatz

Ein Foto trägt eine **Kopfzeile** (welche Grundlage beurteilt hat: Cloud oder lokal, und ob es als
Dokument/Screenshot ausgeschlossen ist) und dazu **acht Stärkezeilen**. Die Abwesenheit der
Kopfzeile ist der Zustand „noch nicht klassifiziert". Korrekturen liegen in einer dritten,
lauf-unabhängigen Tabelle; die wirksame Stärke entsteht erst im Lesepfad und wird nie in die
Stärkezeile materialisiert. Cloud und lokale Erkennung mischen sich nie — die Cloud-Grundlage
ersetzt die lokale vollständig, eine lokale überschreibt eine vorhandene Cloud-Grundlage nie.

### Neue und entfallende Module

- **neu** `backend/src/photosort/motifs.py` — rein (keine DB-, Netz-,
  Bildverarbeitungs-Abhängigkeit, Kriterien-Keys nur als Strings, Auflage wie beim entfallenden
  `categories.py`): `MOTIF_REGISTRY` (acht Einträge, `key`/`display_name`/`definition`/
  `delimitation`, **kein** Ordnungsattribut), `EXCLUSION_KEY = "dokument_screenshot"`,
  `is_motif_key`, `LOCAL_MOTIF_SIGNALS` samt Sättigungsanteilen, `local_motif_strengths(...)`,
  `MOTIF_STRENGTH_BAND_STRONG`/`_MEDIUM`, `build_motif_prompt()`.
- **neu** `backend/src/photosort/motif_strengths.py` — DB-nah:
  `effective_strength_expression()` (der eine `CASE` über Stärke und Korrektur),
  `load_effective_strengths(session, photo_ids)`, `upsert_assessment(session, photo_id, source,
  ...)` mit der Regel „lokal schreibt nur, wenn keine Zeile existiert oder die vorhandene
  `source='local'` trägt".
- **neu** `backend/src/photosort/api/motifs.py` — `GET /motifs` (acht Einträge in
  Registry-Reihenfolge + `strength_bands`), ersetzt `api/categories.py`. Jeder Eintrag trägt
  zusätzlich `locally_assessable: bool`, abgeleitet aus `LOCAL_MOTIF_SIGNALS`: ohne dieses Feld
  könnte die Oberfläche „0 weil nicht zu sehen" nicht von „0 weil nicht angesehen" unterscheiden,
  ohne die Signalliste zu spiegeln.
- **entfällt** `backend/src/photosort/categories.py`, `backend/src/photosort/category_diff.py`,
  `backend/src/photosort/api/categories.py` samt ihren Tests.

### Umsetzungsreihenfolge — drei Pull Requests

Der Schnitt ist durch eine Abhängigkeit erzwungen, nicht gewählt: `photo_category_classifications`
ist heute gleichzeitig Kategoriequelle **und** Erledigt-Marker des Cloud-Teilschritts. Der Marker
kann erst umziehen, wenn der Cloud-Teilschritt Stärken liefert — also muss die Cloud-Umstellung
**vor** der Ablösung liegen.

**PR 1 — Motivregister, Datenmodell, lokale Stärken, Korrekturen (rein additiv, nichts abgelöst)**

1. `motifs.py` mit Registry, Ausschluss-Schlüssel, lokaler Signal-Registry und
   `local_motif_strengths` (reine Funktion, zuerst testbar ohne DB).
2. `models.py`: `PhotoMotifAssessment`, `PhotoMotifStrength`, `PhotoMotifCorrection` samt
   `Photo`-Relationships (`cascade="all, delete-orphan"`); `motif_strengths.py`.
3. Migration (nur anlegen, `down_revision = "a6b7c8d9e0f1"`), dazu ein `test_migration_*.py` im
   Muster der bestehenden. `project_deletion.py` nimmt die drei neuen Tabellen in derselben PR auf,
   in Fremdschlüssel-Reihenfolge (S16).
4. `worker.py::_compute_content_criteria` liefert zusätzlich die Flächenanteile je Allow-Liste
   (Gesichter, COCO-Tiere/-Fahrzeuge/-Speisen) aus den **bereits vorhandenen** Detektionen — kein
   zweiter Detektoraufruf, keine neue Kriterien-Spalte, Boxen werden nicht persistiert.
   `run_criterion_scoring` schreibt daraus je Foto eine lokale Kopfzeile samt Stärkevektor.
5. `api/motifs.py` + Router-Registrierung in `main.py`; `PhotoOut.motif_assessment`/`.motifs`
   **additiv** (die Kategoriefelder bleiben in dieser PR unberührt);
   `PUT`/`DELETE /photos/{id}/motif-corrections/{motif_key}`.
6. Frontend: `api/motifs.ts`, `hooks/useMotifs.ts`, `hooks/useMotifCorrection.ts`,
   `utils/motifLabels.ts`, `components/MotifStrengthList.tsx`; eingebunden in
   `pages/PhotoDetailPage.tsx`. `demo_state.py` erzeugt Kopfzeilen, Stärken und eine Korrektur.

**PR 2 — Die Cloud-Klassifizierung liefert Motivstärken**

1. `remote_classification.py`: `build_motif_prompt()` verlangt **alle acht** Zahlen plus das
   Ausschluss-Feld; `RemoteClassification` wird zum Stärkevektor. Validierung wie bisher
   strukturell hart / inhaltlich tolerant: kein Objekt bzw. fehlendes `motifs` → Fehler (Foto
   best-effort übersprungen); unbekannter Schlüssel oder unbrauchbare Zahl → verworfen, ein
   `WARNING` mit festem Grund-Token, Wert `0.0`; `excluded` nur als echter `bool`, sonst `false`.
   `_MAX_RESPONSE_TOKENS` von 256 auf 384 — die Obergrenze bleibt zugleich die Schranke für die
   Menge geparsten Fremdtexts.
2. `worker.py::run_remote_category_classification` schreibt Kopfzeile (`source='cloud'`) und
   Stärkevektor statt `photo_category_classifications`; `select_remote_category_candidates` und die
   Erfolgs-Ableitung in `api/photos.py::_cloud_vision_status_out` prüfen ab hier die Kopfzeile.
   Feinlabels und Sehenswürdigkeits-Erkennung unverändert; `bauwerk_sehenswuerdigkeit` erhält
   lokal `max(Szenen-Konfidenz, Sehenswürdigkeits-Konfidenz)`.
3. `api/projects.py`: die Kandidatenschätzung spiegelt die geänderte WHERE-Klausel — dieselbe
   Bedingung wie im Lauf, in derselben PR (S14, S15).
4. `pricing.py::ASSUMED_USAGE_BY_PROVIDER.output_tokens` wird gegen die neue vollbesetzte Antwort
   neu hergeleitet, samt Wächtertest auf den neuen Schrankenwert (S12).

**Zwischenzustand nach PR 2, bewusst und genau eine PR lang:** `photo_category_classifications`
wird nicht mehr geschrieben (aber noch nicht gelöscht). Die alte Hauptkategorie eines **neu**
klassifizierten Fotos entsteht dadurch nur noch aus lokalen Signalen. Doppelte Cloud-Kosten
entstehen nicht, weil der Erledigt-Marker in derselben PR umzieht.

**PR 3 — Ablösung**

1. `worker.py`: `derive_photo_category`, `_remote_category_evidence`, `_partition_confidence`,
   `reassign_photo_category` entfallen; die Partition ist allein `event_id`.
   `ranking.py`: `confidence_ordering_score` und `CONFIDENCE_RANK_PENALTY` entfallen.
2. `models.py`: `photo_rankings.category_key`/`.is_primary` und `photo_scores.category_override`
   entfallen, Unique-Constraint zurück auf `(criterion_scoring_run_id, photo_id)`;
   `PhotoCategoryClassification` entfällt. Zwei Migrationen (Spalten/Constraint, dann Tabelle) —
   die Löschung der Nebenzeilen (`WHERE is_primary = false`) muss dem Constraint-Tausch
   **vorausgehen**, sonst ist der Weg an einer echten Datenbank nicht ausführbar. `downgrade()`
   stellt Struktur wieder her, nie Daten.
3. `criteria.py`: `category_eligible` entfällt (es war redundant zur Schwelle),
   `category_presence_threshold` heißt `presence_threshold` — `is_landmark_candidate` bleibt
   unverändert dessen Nutzer. `categories.py` und `category_diff.py` werden gelöscht.
4. `api/photos.py`: die vier Kategoriefelder von `PhotoOut` entfallen, `rankings` wird wieder
   `ranking`, der Kuratierungsparameter heißt `top_n_per_event`, `curation-candidates` verliert
   `category_key`. `api/stats.py`: `motifs` (drei Bandzahlen + Mittelwert je Motiv),
   `strength_bands`, `motif_correction_count`, `unassessed_photo_count` und
   `excluded_photo_count` statt der drei alten Felder.
5. Frontend: `CategoryBadge`, `CategorySelect`, `SecondaryCategoryMarker`,
   `CategoryOverrideMarker`, `utils/categoryLabels.ts`, `hooks/useCategories.ts`,
   `hooks/useCategoryOverrideControls.ts`, `test/categorySetFixture.ts` entfallen; neu
   `components/MotifBadge.tsx`, `test/motifSetFixture.ts`. Angepasst: `api/types.ts`,
   `api/photos.ts`, `api/projects.ts`, `utils/rankings.ts`, `utils/formatStats.ts`,
   `utils/curationTopN.ts`, `components/CurationPhotoTile.tsx`,
   `components/CurationCandidates.tsx`, `components/PhotoCard.tsx`,
   `components/ClassificationBalance.tsx`, `pages/CurateCategoriesPage.tsx` (die Kategorie-Ebene
   der Gruppierung fällt weg), `pages/pipeline/KuratierungStepPage.tsx`,
   `pages/PhotoGridPage.tsx`, `pages/ProjectStatsPage.tsx`, `e2e/lib/demo.ts` und die betroffenen
   `e2e/tests/*`.
6. Die Statistik erklärt sichtbar, dass ein Foto zu mehreren Motiven zählt und die Summe deshalb
   nicht die Fotoanzahl ergibt; die Fotos ohne Kopfzeile stehen als eigene Zahl daneben.
7. `docs/architecture.md` ist bereits auf diesen Zielzustand gebracht — beim Abweichen nachziehen.
   Die Specs [`0289`](./0289-feste-kategorien.md), [`0299`](./0299-kategorie-konfidenz-anzeigen.md)
   und [`0300`](./0300-nebenkategorien.md) gehen in **dieser** PR auf `Superseded` mit Verweis auf
   diese Spec — erst hier ist die Ablösung wahr.

### Grenzen

- Kein Backfill und kein automatisch ausgelöster Cloud-Lauf: Bestandsfotos bleiben ohne Kopfzeile,
  bis der Nutzer selbst klassifiziert.
- `aktivitaet` und `detail_stimmung` sind ohne Cloud-Aussage strukturell nicht erreichbar.
- Die Sättigungsanteile der Flächengewichtung und die beiden Bandgrenzen sind
  dokumentiert-unkalibrierte Startwerte; es gibt keinen Fotokorpus im Repository.

## UI/UX

Verbindliche Muster: [`0004-design-system.md`](../architecture/0004-design-system.md) — „Mehrwertige
Eigenschaft als Stärkeliste, nicht als Zuordnung", „Anzeigeband nur in der Auswertung, nie am
Einzelwert", „‚Noch nicht erhoben' ist keine Null", „Nicht korrigierbare Einstufung benennt ihren
einzigen Weg zurück". Die Motivstärke wird nirgends als Eingabe erhoben — der Nutzer schätzt keine
Zahl, er wählt ein Motiv ab oder zu.

### Grundlagen (PR 1)

- `api/motifs.ts` + `hooks/useMotifs.ts` (`staleTime`/`gcTime: Infinity`, ein Request für alle
  Konsumenten). Anzeigenamen, Reihenfolge und Erklärtexte kommen ausschließlich aus `GET /motifs`;
  im Frontend wird keine Motivliste gespiegelt. `utils/motifLabels.ts::formatMotifKey(key, set)`
  liefert den Anzeigenamen mit generischem Fallback für einen unbekannten Schlüssel — kein
  Absturz, kein leeres Label.
- **Zeilenreihenfolge ist die Registry-Reihenfolge aus `GET /motifs`**, auf jedem Foto dieselbe.
  Die Stärke wird je Schlüssel aus `photo.motifs` nachgeschlagen, nie über den Index der
  Antwortliste. Es wird **nicht** nach Stärke sortiert: acht gleichnamige Korrekturschalter, die
  von Foto zu Foto die Position wechseln, laden zum Fehlklick ein, und ein Fehlklick schreibt hier
  einen Datenwert.
- `components/ui/progress.tsx` bekommt ein Prop `tone`: `accent` (Vorgabe, die drei bestehenden
  Aufrufstellen bleiben unverändert) und `neutral` (Füllung `--text-h`, Spur `--separator`). Beide
  Paare in die Kontrastmatrix von `designSystem.contract.test.ts` aufnehmen.
- Keine neuen Formatierer: `formatCriterionPercent`, `formatDateTime`, `formatProviderLabel`,
  `NOT_AVAILABLE`.

### `components/MotifStrengthList.tsx` (PR 1)

Ein Baustein mit Prop `editable`: bedienbar in der Einzelbildansicht, schreibgeschützt im
Info-Popover der Kachel. Aufbau: Grundlagenzeile, `<ul aria-label="Motive">` mit acht
`<li data-motif-key=…>`, darunter das Glossar.

Je Zeile:

1. `flex items-baseline justify-between gap-3`: Motivname in `--text-h`, rechts der Wert
   (`formatCriterionPercent`) in `font-mono text-xs`.
2. Darunter `<Progress tone="neutral" value={strength} max={1} aria-hidden="true" className="h-2" />`
   — das Verhältnis trägt `value`/`max`, nie ein Inline-Style und nie ein willkürlicher Wert.
3. Nur bei `editable`: `flex flex-wrap gap-3` mit „Trifft zu" / „Trifft nicht zu" (`size="sm"`,
   `variant="outline"`, die geltende Richtung `variant="default"` + `aria-pressed="true"`), dazu
   „Zurücknehmen" (`variant="ghost" size="sm"`) **nur solange eine Korrektur besteht**.
   `aria-label` = sichtbarer Text + `: {Motivname}` — acht gleichnamige Schaltflächen sind sonst
   per Tastatur nicht auseinanderzuhalten. `gap-3` ist die Pflichtgrenze zwischen aufgespannten
   Trefferflächen; `h-8` + `tap-target`, kein `h-11` — die Korrektur ist nicht der heiße Pfad.
4. Korrigierte Zeile: `data-motif-corrected="applies"|"rejected"`, **statt der Prozentzahl** der
   Text „Trifft zu (korrigiert)" bzw. „Trifft nicht zu (korrigiert)", Balken voll bzw. leer. Die
   überstimmte Modellzahl steht nicht daneben.
5. Lokal nicht beurteilbares Motiv (`locally_assessable === false` bei `source='local'`): weder
   Balken noch Zahl, sondern „lokal nicht beurteilbar" in `--text-muted`; die Schaltflächen
   bleiben bedienbar. Ein `0 %` wäre dort die Aussage „nicht zu sehen" statt „nicht angesehen".

Grundlagenzeile aus `motif_assessment`, `text-xs text-text`, kein `Alert`: bei `source='cloud'`
„Grundlage: Cloud-Klassifizierung ({Anbieter}), {Zeitpunkt}", bei `source='local'` „Grundlage:
lokale Erkennung — sie kann nicht jedes Motiv beurteilen."

Glossar: ein einziges `<details>` am Listenende, `<summary>Was die acht Motive bedeuten</summary>`,
darin ein `<dl>` mit `display_name` → `definition` und darunter „Abgrenzung: {delimitation}" in
`--text-muted`. Kein Info-Auslöser je Zeile (acht zusätzliche Trefferflächen für Nachschlagetext)
und kein Popover — die Liste wird ihrerseits in einem Popover gerendert. Registry-Text
ausschließlich als React-Textknoten.

Zustände der Liste: `/motifs` lädt → acht `Skeleton`-Zeilen (`rounded-lg`), kein Spinner.
`/motifs` fehlgeschlagen → `Alert` mit „Erneut versuchen", keine Liste mit Rohschlüsseln.
Korrektur fehlgeschlagen → ein `Alert` unter der Liste mit dem Backend-`detail` wörtlich als
Textknoten und dem Motivnamen; kein „Erneut versuchen", die Schaltfläche der Zeile **ist** die
Wiederholung. Laufende Korrektur → nur die Schaltflächen dieser Zeile `disabled` + `busy`, die
übrige Liste bleibt bedienbar.

### Die vier Fotozustände

- **Noch nicht klassifiziert** (`motif_assessment === null`): **keine Liste**, an ihrer Stelle ein
  Satz — „Noch nicht klassifiziert — dieses Foto hat noch keinen Klassifizierungslauf gesehen."
  Keine Korrektur-Schaltflächen. Acht Nullzeilen sind von „nichts erkannt" nicht zu
  unterscheiden; der Unterschied ist damit strukturell (Satz statt Liste) und nicht farblich. Auf
  der Kachel: Ecken-Marker (PR 3).
- **Klassifiziert, nichts deutlich erkannt**: die acht Zeilen mit ihren kurzen Balken. **Kein
  berechnetes Urteil „nichts erkannt"** — dafür bräuchte die Oberfläche eine Schwelle, und die
  schafft diese Story ab. Kein Kachel-Marker.
- **Lokale Grundlage**: Grundlagenzeile plus die nicht beurteilbaren Zeilen wie oben. Kein
  Kachel-Marker.
- **Als Dokument/Screenshot ausgeschlossen** (`excluded_document`): der Satz zuerst — „Als
  Dokument oder Bildschirmabbildung erkannt — dieses Foto erscheint in keiner Motivauswahl. Diese
  Einstufung lässt sich nicht von Hand ändern; ein neuer Klassifizierungslauf beurteilt das Foto
  erneut." Darunter die Liste **schreibgeschützt** (`editable={false}`): einsehbar bleibt
  einsehbar, aber kein deaktivierter Schalter, nach dem niemand suchen soll.

`components/MotifAssessmentMarker.tsx` (PR 3): Aufbau und Backdrop-Technik wie der entfallende
`CategoryOverrideMarker` (`flex size-6 items-center justify-center rounded-full bg-bg/85
backdrop-blur-sm`), Zeichen `○` als `aria-hidden`, `role="img"` + `aria-label="Motive noch nicht
bestimmt"` am Wrapper, nicht interaktiv, keine aufgespannte Trefferfläche. Er ist der **einzige**
Motiv-Marker der Kachel; lokale Grundlage und Ausschluss stehen im Info-Popover und in der
Einzelansicht, nicht als weitere Ecken-Glyphen.

### Einzelbildansicht `pages/PhotoDetailPage.tsx` (PR 1)

Neue permanente Sektion „Motive" (`<section aria-labelledby>`, `h2` in der Panelkopf-Rolle wie
„Aufnahmezeit"), **nach dem Vorschlagskasten und vor der Trennlinie** — letzter Bedienblock vor
dem Informationsteil, damit Bewertungsleiste und Zurück/Weiter ohne Scrollen erreichbar bleiben.
`hooks/useMotifCorrectionControls.ts` nach dem Vorbild von `useCategoryOverrideControls`
(`PUT`/`DELETE`, `pendingMotifKeyFor(photoId)`). Die bestehende Kategorie-Sektion bleibt in PR 1
unberührt daneben stehen.

### Kachel und Raster (PR 3)

- Motivnamen und Stärken erscheinen **nicht** auf der Kachel — acht Werte haben bei 158px
  Kachelbreite keinen Platz, und der stärkste allein behauptete wieder eine Hauptkategorie.
- `PhotoGridPage`/`CurationPhotoTile`: `topLeft` trägt nur noch den `MotifAssessmentMarker`;
  Übersteuerungs- und Nebenkategorie-Marker fallen mit den Kategorien.
- `CriterionDetailsPopover` (`topRight`) rendert `MotifStrengthList` mit `editable={false}` und
  darunter den Satz „Korrigieren in der Einzelbildansicht." — 24 Bedienelemente in einem Popover
  sind am Telefon nicht bedienbar, und die Kachel führt ohnehin dorthin.
- `CriterionDetailsList` verliert den Kategorien-Block (Kandidatenliste, „Kategorie"-Zeile,
  „Rolle", „Alle Kategorien"-Auswahl, Konfidenz-Erklärung). Qualitätsblock, „Rang", Feinlabels und
  Ausschuss-Vorschlag bleiben wörtlich unverändert; `part='controls'|'info'` und
  `hasCategoryControls` entfallen mit ihrem Inhalt.

### Statistikseite `pages/ProjectStatsPage.tsx` (PR 3)

Die Abschnitte „Kategorienverteilung" und „Konfidenz der Kategorie-Erkennung" weichen **einem**
Abschnitt „Motivverteilung":

- Unmittelbar unter der `h2` ein **dauerhaft sichtbarer** Satz: „Jedes Foto trägt alle acht Motive
  mit unterschiedlicher Stärke und zählt deshalb in mehreren Zeilen — die Summe der Zahlen ist
  größer als die Zahl der Fotos." Kein Info-Popover: eine Summe, die nicht aufgeht, wird sonst als
  Fehler gelesen, und dieser Effekt tritt beim ersten Blick ein.
- Tabelle in Registry-Reihenfolge im bestehenden Stil (`table-fixed text-sm`, Kopf in der
  Beschriftungsrolle, `break-words` in der Motivspalte), Spalten „Motiv | stark | mittel | schwach
  | Ø Stärke". `average_strength === null` → `NOT_AVAILABLE` (Prüfung auf `=== null`, `0` ist ein
  gültiger Mittelwert).
- Am Spaltenkopf „stark" ein `InfoPopover`, dessen Grenzen aus `strength_bands` **formatiert**
  werden (nicht im Frontend hinterlegt): „Die Grenzen sind eine Anzeigehilfe dieser Tabelle. Sie
  entscheiden nicht, ob ein Foto zu einem Motiv gehört — dafür gibt es keine Schwelle."
  **Außerhalb dieser Tabelle erscheint kein Bandwort.** Ein Bandwort neben dem Einzelwert eines
  Fotos lehrte den Nutzer genau die Zugehörigkeitsschwelle, die diese Story abschafft, und er
  korrigierte dann, um ein Motiv über die Grenze zu heben.
- `MetricRow` darunter: `unassessed_photo_count` als „Noch nicht klassifiziert" mit `InfoPopover`
  („Diese Fotos fehlen in jeder Zahl der Tabelle. Sie erhalten Motive erst bei einem
  Klassifizierungslauf, den du selbst auslöst."), `motif_correction_count` als „Von Hand
  korrigiert", `excluded_photo_count` als „Als Dokument ausgeschlossen" mit `InfoPopover` („Diese
  Fotos erscheinen in keiner Motivauswahl. Die Einstufung lässt sich nicht von Hand ändern."). Die
  projektweite Zahl ist die einzige Stelle, an der ein systematisch überschießendes Modell
  auffällt, statt fotoweise entdeckt zu werden.
- Beschriftungen im Bearbeitungsstand und im Diagnoseblock, die das Wort „Kategorie" tragen, gehen
  auf die Motiv-Sprache über, soweit ihr Feld bestehen bleibt.
- Fünf Spalten sind bei 360px eng: Sichtprüfung in Telefonbreite ist Pflicht, aber **kein zweiter
  DOM-Baum** für schmale Breiten.

### Kuratierung (PR 3)

- Die Kategorie-Ebene der Gruppierung entfällt: `GroupedPhotos` wird `{Tag: {Event: Eintrag[]}}`,
  ein Foto steht je Lauf in genau einer Zeile, der Kachel-`key` ist wieder `photo.id`.
  `sortCategoryKeys`, `CategoryBadge` als Abschnittsmarke, der Auffangkorb-Abschnitt samt
  Erklärtext und `candidateCountOfCategory` entfallen; die Kandidatenzahl eines Events ist die
  `partition_size`. `CurationCandidates` verliert `categoryKey`, der Partitionsschlüssel wird das
  2-Tupel `[dayKey, eventKey]` (weiterhin `JSON.stringify`).
- **Der Filter „Nur unsichere Zuordnungen" entfällt** mit `category_confidence`, ebenso die vier
  Leertexte zur 60-%-Schwelle; ein Motivfilter ist ausdrücklich nicht Teil dieser Story. Der
  Leerzustand der erschöpften Partition („Kein weiteres Foto verfügbar") bleibt der einzige.
- **Umbenennung** „Kategorie-Kuratierung" → „Kuratierung" an den drei sichtbaren Stellen:
  `PIPELINE_STEPS`-Label in `utils/pipelineSteps.ts`, `h2` in
  `pages/pipeline/KuratierungStepPage.tsx`, `h1` der Ansicht. „Top-Fotos pro Kategorie" →
  „Top-Fotos pro Foto-Moment", der Erklärsatz „pro Foto-Moment und Kategorie" → „pro
  Foto-Moment", `CURATION_EMPTY_TEXT` ohne das Wort „Kategorie". Route `/curate`, Schritt-ID
  `kuratierung` und `getBlockedReason` bleiben unverändert (nicht sichtbar). Datei
  `pages/CurateCategoriesPage.tsx` → `pages/CuratePage.tsx`.

### Barrierefreiheit und Mobil

- **Die Stärke wird nie allein über Farbe getragen:** der Balken ist `aria-hidden` und neutral
  gefüllt (kein Bewertungston), der eigentliche Text ist die Prozentzahl bzw. das Korrekturwort.
- Der Korrekturzustand steht dreifach: `aria-pressed`, Wortwechsel in der Wertspalte,
  `data-motif-corrected`.
- 360px: Name und Wert in einer Zeile, Balken darunter über die volle Breite, Schaltflächen in
  einer eigenen `flex-wrap`-Zeile — **ein** DOM-Baum, kein breitenabhängiger Zweig. Die längsten
  Namen („Bauwerk und Sehenswürdigkeit", „Detail und Stimmung") müssen umbrechen dürfen.
- Testselektoren: `data-motif-key`, `data-motif-corrected`, `aria-pressed`, Rollen und Labels —
  nie Klassennamen.

## Security

Einstufung: **sicherheitsrelevant, kein Blocker.** Kein neues Secret, kein neuer Netzwerkpfad, kein
zusätzlicher Empfänger von Bilddaten, unveränderter Consent-Schalter, unveränderter Datenumfang je
Foto. Neu sind drei Dinge: ein Pfadsegment aus einem geschlossenen Schlüsselraum, eine bewusst von
beiden Nutzern geteilte Korrekturzeile, und eine Modellzahl, die erstmals selbst die
Auswahlgrundlage ist. Die Auflagen sind nummeriert, damit Umsetzung und Review sie einzeln abhaken
können.

### Auth und Autorisierung (PR 1)

- **S1** `api/motifs.py` trägt den Torwächter als Router-Dependency
  (`dependencies=[Depends(get_current_user)]`) **und** wird in die handgepflegte Router-Liste von
  `tests/test_auth_guard.py::_protected_router_operations` eingetragen. Untersagte Alternative: den
  Router ohne diesen Eintrag lassen — ein später ergänzter zweiter Endpunkt desselben Routers wäre
  von keinem Vollständigkeitstest erfasst.
- **S2** Beide Korrektur-Endpunkte tragen `current_user: User = Depends(get_current_user)` als
  eigenen Parameter. Für diesen Router gibt es keinen Vollständigkeitstest — ein dort vergessener
  Parameter ist still öffentlich: keine 401, nur Daten. Der 401-Test ist deshalb für `PUT` **und**
  `DELETE` Pflicht.
- **S3** `photo_id` wird über `_get_photo_or_404` aufgelöst, ausdrücklich **ohne**
  Projektbedingung: das Auth-Modell kennt keine Eigentümer, beide Nutzer sehen dieselben Projekte,
  `photo_id` ist global eindeutig. Untersagt ist der umgekehrte Fehler, aus dem Kamera-Muster eine
  Projektbedingung zu übernehmen, die als Filter über einer fremden Projekt-Id eine
  Zugriffsentscheidung nur vortäuschte. Ein nicht existierendes Foto ist `404` und spiegelt den
  Eingabewert nicht in der Meldung.

### Eingabevalidierung (PR 1)

- **S4** `motif_key` wird **vor** jeder Schreib- und Löschaktion gegen `motifs.py::is_motif_key`
  geprüft, sonst `422` — reine Mitgliedschaftsprüfung im geschlossenen Achter-Schlüsselraum, kein
  `startswith`, kein Regex, keine Normalisierung des Eingabewerts, für `PUT` **und** `DELETE`.
  `EXCLUSION_KEY` ist kein gültiger Wert und darf nicht über eine Registry-Iteration in den
  Prüfraum geraten. Angriffsmodell: ein erratener oder aus der Laufhistorie bekannter Schlüssel.
  Untersagte Alternative: eine auf die vorhandenen Stärkezeilen dieses Fotos skopierte
  Existenzprüfung — sie hängt an Daten statt am Vokabular und wiese das Korrigieren eines nie
  erkannten Motivs zu Unrecht ab.
- **S5** Der Body trägt ausschließlich `applies: bool`. Kein `user_id`, `photo_id`, `motif_key`,
  `strength` oder `updated_at` im Eingabeschema — Massenzuweisung ist strukturell ausgeschlossen
  statt im Handler herausgefiltert. Ein Feld, über das ein Client eine Stärke setzen könnte, hebt
  die Unterscheidung zwischen Modellaussage und Korrektur auf.

### Die von beiden Nutzern geteilte Korrekturzeile (PR 1)

- **S6** `user_id` stammt ausschließlich aus `current_user.id` — sonst schreibt Nutzer A eine
  Korrektur unter dem Namen von B. Es ist ein **Auditfeld** und kein Zugriffsschlüssel:
  Unique-Constraint und Aufsuch-Bedingung des Upsert lauten `(photo_id, motif_key)`, bewusst ohne
  `user_id`. Beide Richtungen sind Auflage und brauchen je einen Test: der Schreibweg nimmt
  `user_id` nie aus Body oder Query, und der Aufsuchpfad filtert nie zusätzlich auf `user_id` —
  sonst entstehen zwei widersprüchliche Zeilen für dasselbe Paar, und welche gilt, entscheidet die
  Sortierung. Tragender Test: der `PUT` des zweiten Nutzers **überschreibt** die Zeile des ersten
  und legt keine zweite an.
- **S7** Ein gleichzeitiger `PUT` beider Nutzer auf dasselbe Paar läuft in den Unique-Constraint;
  der `IntegrityError` wird auf `409` abgebildet, nie auf eine `500`. Eine Sperre
  (`with_for_update()`) ist nicht nötig und nicht vorzusehen — die Korrektur schreibt eine Zeile
  und leitet nichts ab, sie hat keinen Schreibzugriff auf die Rangfolge. `DELETE` bleibt idempotent
  (`204` auch ohne Zeile) und verlangt keinen Body.

### Die Cloud-Antwort als Vertrauensgrenze (PR 2)

- **S8** Der Prompt entsteht ausschließlich aus `MOTIF_REGISTRY` — nie aus einem Literal daneben,
  nie aus Datenbankinhalten, nie aus einer früheren Modellantwort. Untersagt bleibt jeder
  Rückkopplungspfad („häufige Motive/Feinlabels in den Prompt aufnehmen").
- **S9** Eine Stärke wird nur als echter Zahlentyp im Band `0.0 <= v <= 1.0` übernommen, `bool`
  vorher ausgeschlossen (`isinstance(True, int)` ist `True`; `"menschen": true` erschiene sonst als
  die stärkste Aussage, die das Produkt kennt). Die Bereichsprüfung bleibt als **Vergleich**
  geschrieben, damit `NaN`/`±Infinity` durchfallen, und ein unbrauchbarer Wert wird **verworfen**
  (Ersatzwert `0.0`), nie geklemmt — ein späteres `if v > 1.0: v = 1.0` ließe `NaN` wieder durch.
  Ausfallfolge: `json.loads` parst `NaN` klaglos, `strength` ist hier erstmals eine
  `double precision`-**Spalte** (PostgreSQL nimmt `NaN` an) und Starlette rendert mit
  `allow_nan=False` — ein einziger entarteter Wert legt die **gesamte** Fotoliste des Projekts auf
  `500`, nicht nur den einen Eintrag. Die Prüfung gehört an den Parser, nicht an die
  Datenbankschicht. Dieselbe Deckelung gilt für die lokal berechnete Stärke:
  `min(1, Summe/Sättigungsanteil)` mit Sättigungsanteilen strikt größer als `0`, per
  Invariantentest.
- **S10** `excluded` wird nur als echter `bool` übernommen, sonst `false`. Kein `bool(...)` auf
  einen Fremdwert, keine Umdeutung von `1`, `"true"` oder `"ja"` — jeder nicht-leere Fremdwert
  führte sonst zum Ausschluss. Das ist die Stelle mit dem größten Hebel dieser Story: ein einziger
  Wert nimmt ein Foto aus **jeder** Motivauswahl und ist von Hand nicht korrigierbar.
  `excluded_document` bleibt `NOT NULL` **ohne** Default, damit ein Schreibpfad, der die Spalte
  vergisst, laut scheitert statt still ein Foto auszuschließen.
- **S11** Die WARNING-Zeile für einen verworfenen Schlüssel behält Längenbegrenzung und `%r`
  (Log-Injection über eine mehrzeilige Antwort); die Zeilen für eine verworfene Zahl und für ein
  verworfenes `excluded` tragen einen **festen Grund-Token** und keinen Fremdtext. Geloggt wird
  ausschließlich der einzelne verworfene Wert plus `photo_id` — nie die vollständige Antwort, nie
  der Request-Body, nie Base64-Bilddaten, nie der API-Key.
- **S12** `_MAX_RESPONSE_TOKENS` steigt auf 384 und bleibt eine **Sicherheits**schranke. Beim
  Anheben gehören drei Dinge zusammen nachgezogen: der Kommentar an der Konstante nennt die neue
  Grenze samt Grund, der Wächtertest hält den neuen Wert fest statt gelöscht zu werden, und
  `pricing.py::ASSUMED_USAGE_BY_PROVIDER.output_tokens` (heute 120) wird gegen die neue
  vollbesetzte Antwort neu hergeleitet — die Schätzung ist die einzige Absicherung **vor** der
  kostenpflichtigen Aktion. **Reißt dabei die bestehende Reserve-Invariante
  (`Schranke >= 2 × Annahme`), hält der `developer` an und meldet den Konflikt, statt die Testzahl
  anzupassen.**

### Die Vertrauensgrenze vor dem Cloud-Aufruf (PR 2, Rename in PR 3)

- **S13** `criteria.py::is_landmark_candidate` bleibt rein lokal und vor jedem Cloud-Aufruf. Der
  Rename `category_presence_threshold` → `presence_threshold` ist mechanisch; der Sicherheitsblock
  an der Funktion bleibt in voller Aussage stehen und wird nur im Feldnamen nachgezogen.
  Untersagt: ihn beim Umbenennen mit-kürzen.
- **S14** Das Skip-Kriterium des Cloud-Teilschritts ist eine Kopfzeile **mit `source='cloud'`**,
  nicht das bloße Vorhandensein einer Kopfzeile. Der Kriterien-Lauf schreibt ab PR 1 lokale
  Kopfzeilen; ein reiner Existenztest macht jedes lokal beurteilte Foto dauerhaft zum
  Nicht-Kandidaten, und die Cloud-Klassifizierung wird zum stillen No-op mit Kostenschätzung `0`.
  Der Fehler in die andere Richtung schickt bereits klassifizierte Fotos erneut an den Anbieter.
- **S15** `api/projects.py::_count_remote_category_candidates` ist eine bewusste Duplikation
  derselben Bedingung. Beide Stellen ändern sich in **derselben** PR und bekommen den Testfall „ein
  Foto mit lokaler Kopfzeile ist weiterhin Kandidat und wird mitgezählt". Eine Schätzung, die eine
  andere Menge zählt als der Lauf sendet, ist eine falsche Grundlage für die Freigabe einer
  kostenpflichtigen Aktion.

### Migrationen und Löschpfad (PR 1 und PR 3)

- **S16** Die drei neuen Tabellen werden in `project_deletion.py` aufgenommen — in derselben PR,
  die sie anlegt, und in Fremdschlüssel-Reihenfolge (`photo_motif_strengths` vor
  `photo_motif_assessments`). Sonst überleben Aussagen über den Bildinhalt gelöschter Familienfotos
  die Projektlöschung. Die Testsuite läuft ohne `PRAGMA foreign_keys=ON`, eine falsche Reihenfolge
  fällt dort strukturell nicht auf; dafür gibt es die beiden Wächtertests des Moduls.
  `PhotoCategoryClassification` verlässt die Aufzählung in PR 3.
- **S17** Die Löschung der Nebenzeilen vor dem Constraint-Tausch muss die Nachbedingung „höchstens
  eine Zeile je `(criterion_scoring_run_id, photo_id)`" **herstellen**, nicht sie voraussetzen.
  `WHERE is_primary = false` allein setzt voraus, dass es je Lauf und Foto nie zwei Hauptzeilen
  gibt — eine Eigenschaft, die im Bestand nur eine unter SQLite wirkungslose Sperre schützte.
  Trägt die echte Datenbank ein solches Paar, bricht der Constraint-Tausch mitten in der Migration
  ab. Der Migrationstest deckt den Doppel-Hauptzeilen-Fall mit ab.
- **S18** Der Rückwärtsweg stellt Struktur wieder her, nie Daten, und sagt das in einem Satz in
  seinem eigenen Doku-Block. Ohne diesen Satz sieht ein `downgrade` wie eine Rücknahme aus und
  liefert eine strukturell gültige Datenbank, in der jedes Foto kategorielos ist.

### Frontend und Abbau (PR 1 und PR 3)

- **S19** `display_name`, `definition` und `delimitation` stammen aus der Registry im Repository und
  sind kein Fremdtext; sie werden trotzdem ausschließlich als React-Textknoten gerendert, nie über
  `dangerouslySetInnerHTML`, nie als HTML-String-Prop, und fließen in kein `href`, `src`, `style`
  und keinen `url()`-Kontext. Die Story bringt **keinen** neuen Fremdtext in die Oberfläche: der
  Beitrag des Modells ist ab hier eine Zahl je Motiv plus ein Wahrheitswert. Die Feinlabels bleiben
  der bestehende Fremdtext-Fall samt Sanitierung.
- **S20** Mit `category_diff.py` fällt der bisherige Ort der projektweiten Ausgabe-Hygiene für
  Werkzeuge, die `relative_path`-Werte ausgeben. Die Auflage ist deshalb ins Sicherheitskonzept
  übernommen; die Datei darf danach gelöscht werden. Untersagt: die Regel als gelöschten Kommentar
  verschwinden lassen.
- **S21** Entfällt ein Endpunkt oder eine Codestelle, die in der Ankerliste des Sicherheitskonzepts
  steht (`categories`-Router, `reassign_photo_category`-Sperre), wird die Liste in derselben PR
  nachgezogen, und die neuen Auflagen aus S6, S9, S10 und S14 bekommen dort ihre eigene Zeile samt
  brechendem Test.

### Ausdrücklich nicht sicherheitsrelevant an dieser Story

Secrets (kein neuer Schlüssel, keine neue Umgebungsvariable, kein neuer Anbieter); SSRF,
Rechtsraum/DSGVO und Einwilligung (unveränderte Ziel-Hosts, unveränderter projektweiter
Consent-Schalter, unverändertes Vorfilter- und Datenumfangsmodell je Foto); CSRF (unverändert durch
den Bearer-Header-Transport gedeckt); Denial of Service über die Korrektur-Endpunkte (ein `PUT`
schreibt genau eine Zeile, der Unique-Constraint deckelt den Bestand auf `Fotos × 8`, kein
Bildzugriff und kein Cloud-Aufruf im Request-Pfad). Der Datenverlust in PR 3 ist eine getroffene
Entscheidung und kein Sicherheitsereignis; die Lauf- und Kostentabellen bleiben unberührt.

### Restrisiken dieser Story

- Nutzer A kann die Korrektur von B überschreiben; nur `user_id`/`updated_at` zeigen, wer zuletzt
  geschrieben hat, eine Historie gibt es nicht. Gewollt und innerhalb des bestehenden „kein
  Innentäter-Modell zwischen den beiden Nutzern".
- Ein präpariertes Bild kann `excluded=true` erzwingen und ein Foto damit aus jeder Auswahl nehmen;
  der Rückweg ist ein erneuter, kostenpflichtiger Lauf. Schaden auf ein Foto begrenzt, sichtbar in
  der Oberfläche.

## Teststrategie

Ebenen und Konventionen wie in [`0002-testkonzept.md`](../architecture/0002-testkonzept.md); der
dort neu angelegte Abschnitt führt die sieben Muster, die dieses Feature einbringt. Hier stehen die
Zuordnung zu den drei Pull Requests und die Fälle, die sonst durchgehen.

### Die fünf Kriterien, die nur ein Test hält

Sie brechen ohne Ausnahme, Typfehler oder auffällige Anzeige. Fehlt der genannte Test, ist das
Kriterium unbelegt, auch wenn die Oberfläche richtig aussieht.

1. **„Erkennbar, dass ein Foto noch keine Motive trägt."** Der Fehlerpfad ist ein `?? 0` oder eine
   leere Standardliste: acht Nullzeilen statt eines Satzes. Gehalten wird es **paarweise** —
   derselbe Aufbau ohne Kopfzeile und mit einer Kopfzeile, deren acht Stärken alle 0.0 sind, mit
   einer Assertion darauf, dass die beiden Antworten bzw. Renderings **verschieden** sind. Dazu im
   ersten Fall die Kardinalität Null auf `[data-motif-key]`, nicht eine Textsuche nach dem Satz:
   der Satz kann über acht Nullzeilen stehen, und dann ist er grün und falsch.
2. **„Lokal erkannte Objekte treten nie als Gegenkandidat an."** Beide Richtungen in einem Paar:
   Cloud nach lokal ersetzt, lokal nach Cloud lässt Herkunft, Zeitstempel und alle acht Werte
   **unverändert**. Der zweite Fall ist der eigentliche; ohne ihn bestünde auch ein bedingungsloses
   Überschreiben.
3. **„Eine Korrektur bleibt über weitere Klassifizierungsläufe erhalten."** Nach einem Lauf über
   ein korrigiertes Foto: die Korrekturzeile existiert noch **und** die wirksame Stärke ist weiter
   der korrigierte Wert. Nur die erste Hälfte deckt ein `cascade` nicht ab, das die Zeile mit der
   Kopfzeile abräumt; nur die zweite deckt nicht ab, dass sie neu geschrieben statt bewahrt wurde.
4. **Die Statistikbänder rechnen über der wirksamen, nicht der gespeicherten Stärke.** Ein Foto mit
   gespeicherter Stärke 0.9 und `applies=false` zählt ins schwache Band. Eine Statistikabfrage
   direkt auf `photo_motif_strengths` liefert überall sonst dieselben Zahlen — dies ist der einzige
   Aufbau, der sie von der richtigen unterscheidet.
5. **Die Flächengewichtung darf `content_people` nicht verändern.** In **einem** Fall: ein kleines
   Gesicht ergibt eine Menschen-Stärke < 1.0, und `content_people` desselben Fotos ist weiter genau
   1.0. Getrennt geschrieben bestünden beide Assertions auch dann, wenn die alte
   Präsenz-Berechnung stillschweigend zur neuen geworden ist — und damit wären Rangfolge und
   Landmark-Kandidatenwahl mitverändert.

### PR 1 — Register, Datenmodell, lokale Stärken, Korrekturen

**Neu:** `test_motifs.py` (Unit, DB-frei), `test_motif_strengths.py`, `test_api_motifs.py`,
`test_api_motif_corrections.py`, `test_migration_motivstaerken.py`. **Erweitert:**
`test_models.py`, `test_worker_criterion_scoring.py`, `test_api_photos.py`, `test_demo_state.py`,
`test_postgres_ddl_compatibility.py`, `tests/project_graph.py`, `test_project_deletion.py`,
`test_api_projects.py`, `test_auth_guard.py`, `test_openapi_beschreibungen.py`. **Frontend neu:**
`test/motifSetFixture.ts`, `api/motifs.test.ts`, `hooks/useMotifs.test.tsx`,
`hooks/useMotifCorrection.test.tsx`, `utils/motifLabels.test.ts`,
`components/MotifStrengthList.test.tsx`; erweitert `pages/PhotoDetailPage.test.tsx`.

Nicht offensichtliche Nachweise:

- `MOTIF_REGISTRY` trägt **kein** Ordnungsattribut — Invariantentest über den Feldern des Eintrags,
  nicht über einem Namen. `motifSetFixture.ts` ist die einzige Frontend-Liste und spiegelt die
  Antwort.
- `EXCLUSION_KEY` ist **nicht** in der Registry, `is_motif_key(EXCLUSION_KEY)` ist falsch.
- Flächengewichtung: Monotonie über drei Flächen, Sättigungsgrenze als Paar (genau auf dem Anteil
  → 1.0, nächstkleinerer darstellbarer Wert → < 1.0). `LOCAL_MOTIF_SIGNALS` referenziert nur
  existierende Motiv- und Kriterien-Keys, abgeleitet geprüft statt als Zweitliste.
  `aktivitaet`/`detail_stimmung` sind in **keinem** Aufbau > 0.
- Wirksamkeit: Fallmatrix auf `effective_strength_expression()` gegen hohe und niedrige Grundlage,
  **plus** struktureller Wächter gegen eine zweite Fassung dieses `CASE` (Zählung der Stellen, die
  die Korrekturspalte nennen; der Wächter nennt die Datei).
- Lauf-Unabhängigkeit maschinell: `PhotoMotifCorrection.__table__.foreign_keys` verweist
  ausschließlich auf `photos` und `users` — kein Lauf.
- `PhotoOut.motifs` trägt acht Einträge auch bei unvollständigen Stärkezeilen.
- Migration: nach `upgrade()` sind alle drei Tabellen leer (kein Backfill).
- **Projektlöschung:** Reihenfolge- und Vollständigkeitstest leiten aus `Base.metadata` ab und
  werden automatisch rot; der Verhaltenstest dagegen **nicht** — er zählt Zeilen und besteht mit
  null Zeilen stillschweigend. `project_graph.py` muss je eine Zeile in allen drei neuen Tabellen
  anlegen, sonst prüft die Löschung nichts.
- **Postgres-DDL:** Stärke als Fließkommaspalte (SQLite kennt den Unterschied zu INTEGER nicht),
  `excluded_document`/`applies` als BOOLEAN, Unique-Constraint `(photo_id, motif_key)` **benannt**.
- `("get", "/motifs")` und die beiden Korrektur-Routen in
  `test_openapi_beschreibungen.py::DOCUMENTED_ROUTES` eintragen — ein nicht eingetragener Endpunkt
  fällt ohne roten Test aus der Beschreibungspflicht.

### PR 2 — Die Cloud-Klassifizierung liefert Motivstärken

**Erweitert:** `test_remote_classification.py`, `test_worker_remote_category_classification.py`,
`test_api_classification_estimate.py`, `test_api_photos.py`.

- Bauwerk stark / Menschen schwach: eine Antwort mit `0.9`/`0.2` erzeugt genau diese Relation in
  den persistierten Zeilen, die Gegenprobe mit getauschten Zahlen die getauschte. Der Fall mit
  **gleichen** Zahlen gehört nicht dazu — er deckte jede Implementierung.
- Der Prompt entsteht aus der Registry, nicht aus einem Literal: Registry per `monkeypatch`
  verändert → Prompt ändert sich mit. `_MAX_RESPONSE_TOKENS` als Literal festgenagelt.
- Validierungs-Fallmatrix: kein Objekt → Fehler; fehlendes `motifs` → Fehler; unbekannter Schlüssel
  → verworfen mit `WARNING` (per `caplog` auf den **Grund-Token**, nicht auf den Satz);
  unbrauchbare Zahl (`None`, `"0.7"`, `NaN`, `-0.1`, `1.5`) → 0.0 mit Grund-Token; `excluded` als
  `"true"`/`1`/fehlend → `false`, nur echtes `true` → `true`.
- Erledigt-Marker: ein Foto mit Kopfzeile ist kein Kandidat mehr, ein Foto mit bloßer Altzeile in
  `photo_category_classifications` **ist** wieder Kandidat. Die Schätzung in `api/projects.py`
  spiegelt dieselbe Bedingung — geprüft an einem Bestand, in dem die beiden Bedingungen
  verschiedene Zahlen liefern.
- **Regel für den Zwischenzustand:** In dieser PR darf **kein** Test durch eine von Hand
  eingefügte `photo_category_classifications`-Zeile grün gehalten werden, die der Produktivpfad
  nicht mehr schreibt. Betroffen sind die Fälle in `test_worker_criterion_scoring.py`, die über
  einen Remote-Lauf gehen und danach eine abgeleitete Kategorie erwarten: ihre Erwartung wandert
  auf die Kopfzeile, oder der Fall entfällt mit dem Schreibpfad.

### PR 3 — Ablösung

**Ersatzlos entfallen:** `test_categories.py`, `test_category_diff.py`, `test_api_categories.py`,
`test_api_category_override.py`, `test_worker_reassign_photo_category.py`; Frontend
`CategoryBadge.test.tsx`, `CategorySelect.test.tsx`, `CategoryOverrideMarker.test.tsx`,
`SecondaryCategoryMarker.test.tsx`, `utils/categoryLabels.test.ts`, `hooks/useCategories.test.tsx`,
`hooks/useCategoryOverrideControls.test.tsx`, `test/categorySetFixture.ts`.

**Bleiben unberührt stehen, obwohl ihr Gegenstand verschwindet:**
`test_migration_feste_kategorien.py`, `test_migration_kategorie_konfidenz.py`,
`test_migration_nebenkategorien.py`, `test_migration_remote_category_classification.py`. Sie laden
ihre Revision per `importlib` und bauen den Vorher-Schema-Stand von Hand, hängen also an keinem
Modell. Ihre Revisionen laufen bei jedem Containerstart weiter; mitgelöscht wäre die Lücke lautlos.

**Umgeschrieben:** `test_api_stats.py`, `test_criteria.py`, `test_ranking.py`,
`test_worker_criterion_scoring.py`, `test_api_photos.py`, `test_demo_state.py`; Frontend
`CurateCategoriesPage.test.tsx`, `ProjectStatsPage.test.tsx`, `PhotoGridPage.test.tsx`,
`CurationPhotoTile.test.tsx`, `PhotoCard.test.tsx`, `ClassificationBalance.test.tsx`,
`utils/rankings.test.ts`, `utils/formatStats.test.ts`, `utils/curationTopN.test.ts`,
`designSystem.contract.test.ts`; neu `components/MotifBadge.test.tsx`.

- **Struktureller Wächter für die negative Hälfte:** kein Modul unter `backend/src/photosort/` und
  keine Datei unter `frontend/src/` nennt `category_key`, `is_primary`, `category_override`,
  `nicht_erkannt`, `precedence` oder `CONFIDENCE_RANK_PENALTY`; der Wächter nennt Datei und Zeile.
- **Reihenfolge der Migration:** Index-Vergleich auf der **gerenderten Postgres-DDL** —
  `DELETE FROM photo_rankings` steht vor dem Constraint-Tausch. Über die SQLite-Probe ist die
  Zusage nicht haltbar (dort wird die Tabelle neu aufgebaut und die falsche Reihenfolge verziehen);
  die Datenwirkung derselben Anweisung bleibt der SQLite-Probe.
- `downgrade()`: Spalten und Tabelle existieren wieder **und sind leer**; ein vorübergehender
  `server_default` ist danach fort.
- Statistik: Aufbau, in dem ein Foto in drei Motiven stark ist — die Summe der starken Bandzahlen
  übersteigt die Fotozahl. Als Nachsatz **jedes** Statistikfalls: die drei Bänder je Motiv sind
  disjunkt und ihre Summe ist die Zahl der beurteilten Fotos.
- Bandgrenzen: Inklusivität als Paar (genau `2/3` → stark, nächstkleinerer darstellbarer Wert →
  mittel; dasselbe an `1/3`), und **kein** Modul des Auswahl- oder Rangfolgepfads und keine
  Frontend-Datei liest die Konstanten.
- Der Erklärsatz der Zählweise ist **ohne Interaktion** im DOM — nicht in `<details>`, nicht in
  einem Popover.
- **Repo-Konsistenz:** die Statuszeile der Specs 0289/0299/0300 und der ADR 0049/0067/0069 lautet
  `Superseded` und nennt 0427. Eigener Testfall, weil „ausdrücklich abgelöst" sonst eine
  Behauptung im Pull-Request-Text ist.

**E2E.** Das Aufnahmekriterium bleibt „nur, was jsdom prinzipiell nicht kann"; die geforderten
Oberflächenzustände sind **alle** jsdom-Zusicherungen und entstehen als `vitest`-Fälle. Kein neuer
Spec. Angepasst werden drei bestehende, die sonst am geänderten Produkt vorbeilaufen:
`tap-targets.spec.ts` (die Trefferfläche „Alle Kategorien" verschwindet), `no-horizontal-scroll.spec.ts`
und `popover-position.spec.ts` (die Vorbedingungs-Überschrift ändert sich — eine nicht nachgezogene
Vorbedingung ist genau der immer-grüne Fall) sowie `e2e/lib/demo.ts`. Die Fotozahl des
Demo-Projekts leitet sich aus der Registrygröße ab und sinkt von dreizehn auf acht — bei 1280px
muss weiter eine **vollständige** Vierer-Zeile entstehen, sonst wird `grid-columns` rot.

### Edge Cases, die der Umsetzung sonst durchgehen

- **Stärke genau auf einer Bandgrenze:** `>=` inklusiv, je Grenze mit dem nächstkleineren
  darstellbaren Wert als Gegenprobe. Die Konstante genau einmal geschrieben — `0.67` an einer
  Stelle und `2/3` an einer anderen verschiebt die Grenze um einen Betrag, den kein Fall trifft.
- **`applies=false` auf einem Motiv, dessen Grundlage schon 0 ist:** Die Zeile entsteht, wird
  gezählt, und die Oberfläche zeigt das Korrekturwort — obwohl sich keine Zahl bewegt. Eine
  Implementierung, die eine wirkungslose Korrektur „einspart", macht sie unsichtbar.
- **Korrektur auf einem Foto ohne Kopfzeile:** wird angenommen und gespeichert (die Tabelle ist
  lauf-unabhängig); `load_effective_strengths` liefert für dieses Foto nichts, und beim ersten
  Klassifizierungslauf greift sie sofort. Genau so als Fall: korrigieren, danach klassifizieren,
  die Korrektur gewinnt bereits im ersten Lauf.
- **Zwei Nutzer korrigieren dasselbe Paar:** der zweite Aufruf ist ein Update, kein
  `IntegrityError` — und er schreibt `user_id` mit. Bleibt das Feld stehen, schreibt die
  Feedback-Story das Signal der falschen Person zu. Ebenso das `DELETE` durch die andere Person.
- **Ein Cloud-Lauf nach einer Korrektur**, und der Sonderfall: das Modell liefert nun denselben
  Wert, den die Korrektur erzwingt. Die Zeile darf nicht als „überflüssig" entfernt werden — sie
  ist eine Nutzeraussage, keine Zwischenspeicherung.
- **Projektlöschung mit Korrekturen:** `photo_motif_corrections` hängt zugleich an `users` — der
  Nutzer darf dabei nicht mitgelöscht werden.
- **Ungültiger Motiv-Schlüssel** → `422`, auch für `dokument_screenshot`, für einen anders
  geschriebenen Schlüssel (`Menschen`, ` menschen`) und für einen entfallenen Kategorieschlüssel
  (`pflanze`, `innenraum`).
- **Bandzahlen bei null Fotos und bei null beurteilten Fotos:** acht Einträge mit drei Nullen, der
  Mittelwert `None` und nie `0.0`, keine Division.
- **Überlappende Boxen desselben Typs**, eine über den Bildrand hinausreichende Box, eine Box der
  Fläche 0, und eine Objektklasse, die zu zwei Motiven beiträgt: der Anteil bleibt in allen vier
  Fällen in [0,1].
- **Eine lokale Kopfzeile ohne jede Detektion** entsteht trotzdem — mit acht Nullen und
  `source='local'`. Sonst gilt das Foto als „noch nicht klassifiziert", obwohl es beurteilt wurde.
- **`excluded_document=true` bei gleichzeitig hohen Stärken:** Der Ausschluss gewinnt; die Stärken
  bleiben gespeichert und werden nicht auf 0 gesetzt.

### Was bewusst nicht geprüft wird

Ob eine Motivstärke der Wahrheit entspricht: Sättigungsanteile und Bandgrenzen sind
dokumentiert-unkalibrierte Startwerte, und es gibt keinen Fotokorpus. Geprüft ist, dass die Zahl
des Modells unverändert ankommt, dass ein Flächenanteil monoton wirkt und dass die Sättigung
greift. Ein Test auf die Werte selbst bestätigte nur sich selbst.

### Coverage

Das globale Gate (Backend ≥ 80 %, Stand 97 %) ist durch die Löschungen in PR 3 nicht gefährdet und
für dieses Feature auch kein Nachweis: es bliebe grün, wenn der gesamte neue Lesepfad ungetestet
wäre. Maßgeblich sind stattdessen zwei Größen je Pull Request — `motifs.py`, `motif_strengths.py`
und `api/motifs.py` stehen bei 100 %, und in PR 3 sinkt `Cover` an keiner Datei, die nur einen
Zweig verliert.

## Entscheidungen

- **Korrigierbar sind ausschließlich die acht Motive** (Daniel, 2026-09-12): „Dokument und
  Screenshot" ist nicht von Hand korrigierbar. Ein fälschlich ausgeschlossenes Foto kommt allein
  über einen erneuten Klassifizierungslauf zurück; die Oberfläche macht den Ausschluss deshalb
  sichtbar, ohne einen Schalter anzubieten.
- **Die Umsetzung läuft in drei Pull Requests** (Daniel, 2026-09-12) in der oben festgelegten
  Reihenfolge, samt des benannten Zwischenzustands von einer PR Länge.
- **Die alten Kategoriedaten werden restlos entfernt** (Daniel, 2026-09-12): Tabelle und Spalten
  fallen in PR 3, die bereits bezahlten Kategoriekonfidenzen früherer Cloud-Läufe gehen dabei
  verloren. Motivstärken brauchen ohnehin einen neuen Lauf.
- **Die Stärkebänder (stark ab 2/3, mittel ab 1/3) sind eine Anzeigekonvention der Statistik**,
  keine Auswahlschwelle. Kein Pfad der Auswahl oder Rangfolge liest sie, und außerhalb der
  Statistiktabelle erscheint kein Bandwort.
- **Stärke-Anzeige am Einzelfoto: neutraler Balken plus Prozentzahl** (Daniel, 2026-09-12).
- **Auf der Kachel erscheint kein Motiv** (Daniel, 2026-09-12), nur die Marke „Motive noch nicht
  bestimmt". Die acht Stärken stehen im Info-Popover der Kachel und in der Einzelbildansicht.
- **Die Kuratierungsansicht heißt künftig „Kuratierung"** (Daniel, 2026-09-12).
- **Die Motivzeilen stehen immer in Registry-Reihenfolge**, nie nach Stärke sortiert: springende
  Positionen unter acht gleichnamigen Korrekturschaltern provozieren Fehlklicks, und ein Fehlklick
  schreibt hier einen Datenwert.
- **`GET /motifs` trägt je Motiv `locally_assessable`**, damit die Oberfläche „0 weil nicht zu
  sehen" von „0 weil nicht angesehen" unterscheiden kann, ohne die Signalliste zu spiegeln.
- **Eine Korrektur je Foto und Motiv, letzter Zugriff gewinnt** (Daniel, 2026-09-12): Korrigiert
  der zweite Nutzer dasselbe Paar, überschreibt er die Aussage des ersten; `user_id` hält fest, wer
  zuletzt geschrieben hat. Keine Historie, kein Hinweis an die erste Person.
- **Die Statistik weist `excluded_photo_count` projektweit aus.** Der Ausschluss hat keinen
  Korrekturpfad; ohne diese Zahl fällt ein systematisch überschießendes Modell nur fotoweise auf.
- `ux-ui-designer` konsultiert (Schritt 2) mit dem Standardmodell statt mit Haiku: Die
  Relevanzprüfung, die die Herabstufung begründet, war hier bereits erledigt — es stand ein
  Entwurf für vier Ansichten an.

## Out of Scope

- Wie die Albumauswahl die Motivmischung nutzt — eigene Story des Zielbilds.
- Das Auswerten der Korrekturen als Rückmeldung an die Bewertung — Feedback-Story.
- Die Wahl eines spezialisierten Modells für die Motiv-Erkennung.
- Ob die Stärkewerte des Modells gegen eine Referenz nachjustiert werden müssen. Das lässt sich
  erst beurteilen, wenn Korrekturen vorliegen.
