# 0432 - Laufende Diagnose der Modellfehler und Gewichte aus der Nacharbeit

**Status:** Accepted
**Erstellt:** 2026-09-13
**Bezug:** [Issue #432](https://github.com/TheRealKoller/photosort/issues/432) (Story 8 und Abschluss des Zielbilds [#424](https://github.com/TheRealKoller/photosort/issues/424))

**Umfang:** ein Mehrfaches des Richtwerts von rund 200 Zeilen. Vier Abschnitte tragen ihn, jeder aus
einem eigenen Grund: „Architektur / Umsetzung" führt die betroffenen Dateien je Pull Request auf,
weil der `developer` sie ohne eigene Planung abarbeitet; „Security" führt die Auflagen einzeln
abhakbar samt Angriffsmodell; „Teststrategie" benennt die Zusicherungen, die ohne eigenen Testfall
still brechen; die Akzeptanzkriterien sind auf Prüfbarkeit geschärft und dadurch zahlreicher als im
Issue. Der gemeinsame Grund: Fast jede Zusage dieses Features ist eine **Abwesenheit im
Zeitverlauf** — ein Ereignis, das nicht entstehen darf; eine Zeile, die eine spätere Neuberechnung
überleben muss; eine Zahl, die sich nach einer Änderung nicht bewegen darf. Solche Zusagen brechen
ohne Ausnahme und ohne Fehlermeldung.

## Ziel

Jede Schwelle und jedes Gewicht im System ist ein unkalibrierter Startwert. Der einzige bekannte Weg
zu kalibrierten Werten wäre, Fotos von Hand zu labeln — das ist ausdrücklich nicht gewollt.

Die Nacharbeit am Album-Entwurf liefert dieselbe Information beiläufig: Wer ein Motiv korrigiert,
einen Vorschlag austauscht, ein Bild streicht oder aufnimmt, sagt damit, wo das System danebenlag.
Heute verpufft das. Diese Story hält es als unveränderliches Ereignis fest, macht daraus eine
laufende Diagnose der Modellfehler und leitet daraus angepasste Gewichte der Qualitätskriterien ab.

Sie schließt den Umbau des Zielbilds ab und räumt zugleich eine Blockade weg: Der Vergleich
stärkerer Modelle (#420) und die Bewertung spezialisierter Modelle (#423) setzen bisher einen
handgelabelten Stichprobensatz voraus, den es nicht geben soll. Die Diagnose tritt an dessen Stelle.

## User Story

Als jemand, der ein Album aus einer Reise zusammenstellt, möchte ich, dass meine Korrekturen am
Entwurf nicht verpuffen, sondern sichtbar machen, wo das System danebenliegt, und dass ich die
Qualitätsgewichte daraus nachziehen kann, damit die Vorschläge mit der Zeit besser werden — ohne
dass ich dafür Fotos von Hand labeln muss oder ein Modell trainiert wird.

## Akzeptanzkriterien

Auf Prüfbarkeit geschärfte Fassung der Kriterien aus dem Issue.

### Was festgehalten wird

- [ ] **L1** — Jede Korrektur am Album-Entwurf erzeugt **genau ein** Ereignis mit Zeitpunkt und
  Nutzer. Ein Schreibvorgang, der die Albumentscheidung des Fotos **nicht wechselt**, erzeugt
  **kein** Ereignis: dieselbe Entscheidung erneut gesetzt, eine nicht vorhandene zurückgenommen,
  und ausdrücklich das Setzen oder Entfernen des Favoriten-Kennzeichens, das durch dieselbe
  Schreibstelle läuft. Das entscheidende Prädikat ist der Wechsel des Status, nicht der
  Schreibvorgang an der Zeile.
- [ ] **L2** — Der Austausch ist **ein** Aufruf und **ein** Ereignis mit beiden Foto-Verweisen. Er
  erzeugt daneben kein Streich- und kein Aufnahme-Ereignis. Scheitert einer der beiden
  Schreibvorgänge, ist **keine** der beiden Bewertungszeilen geändert und **kein** Ereignis
  geschrieben. Der Aufruf antwortet mit dem geschriebenen Zustand **beider** Bewertungszeilen.
- [ ] **L3** — Der Austausch wird mit `422` abgewiesen, wenn beide Foto-Verweise dasselbe Foto
  benennen, wenn eines der Fotos nicht zum angegebenen Projekt gehört, oder wenn die beiden Fotos
  nicht zum selben Event des jüngsten erfolgreichen Laufs gehören.
- [ ] **L4** — Ein Ereignis trägt die **eingefrorene** Entscheidungslage: die Modellstufe der
  beteiligten Fotos, deren Qualitätswert aus dem damals jüngsten erfolgreichen Lauf, bei einer
  Motivkorrektur die damals **gespeicherte** Motivstärke. Diese Felder sind **nullbar**; ein Foto
  ohne Modellbewertung erzeugt trotzdem ein Ereignis. Sie bleiben unverändert, wenn das Foto neu
  klassifiziert wird.
- [ ] **L5** — Die Reihenfolge mehrerer Korrekturen am selben Foto ist die aufsteigende laufende
  Nummer, **nie** der Zeitpunkt. Zwei Ereignisse mit identischem Zeitstempel bleiben unterscheidbar
  geordnet.
- [ ] **L6** — Eine zurückgenommene Korrektur erzeugt ein **zusätzliches** Ereignis. Das
  ursprüngliche bleibt unverändert bestehen, und die Fallzahl, in die es eingeht, **verringert sich
  dadurch nicht**.
- [ ] **L7** — Ein Ereignis aus der gemeinsamen Endauswahl trägt **keinen** Nutzer; jedes andere
  trägt einen. Es trägt ein höheres Gewicht; die **angezeigte Fallzahl bleibt in jedem Fall die
  ungewichtete Anzahl**.
- [ ] **L8** — Festgehalten werden ausschließlich Verweise, Zeitpunkt, Art und die eingefrorenen
  Zahlen. Keine Bilddaten.

### Die laufende Diagnose

- [ ] **D1** — Eigener Abschnitt der Projekt-Statistikseite. Der Abschnitt **spricht in seinem Text
  aus**, dass seine Zahlen projektübergreifend und über beide Nutzer gelten.
- [ ] **D2** — Drei Motiv-Fehlerfälle, je mit eigener Fallzahl: richtiges Motiv vorhanden, aber
  unterhalb der Anzeigeschwelle / gar nicht genannt / vom Modell genannt und vom Nutzer weggenommen.
- [ ] **D3** — Die drei Tauschklassen (gleichstufig, stufenübergreifend, unbestimmt) werden
  **getrennt** ausgewiesen und an keiner Stelle summiert. Ihre Summe ist die Gesamtzahl der
  Austausch-Ereignisse — sie sind disjunkt und erschöpfend. Ein Paar mit fehlender Modellstufe ist
  **unbestimmt** und wird keiner der beiden anderen Klassen zugeschlagen.
- [ ] **D4** — Zur Qualität: wie oft beim Austausch ein Bild mit **niedrigerem** eingefrorenem
  Qualitätswert vorgezogen wurde. Paare mit gleichem Wert und Paare mit fehlendem Wert gehen in
  diese Zahl **nicht** ein und werden als eigene Zahl ausgewiesen.
- [ ] **D5** — Je Kriterium ist erkennbar: die Zahl der **tatsächlich auswertbaren** Paare (beide
  Fotos tragen den Messwert) und die Zustimmungsrate. Diese Zahl kann kleiner sein als die Zahl der
  gleichstufigen Austausche; beide stehen nebeneinander.
- [ ] **D6** — Bei null Korrekturen zeigt der Abschnitt einen Hinweistext, der benennt, wodurch
  Zahlen entstehen. Dieser Zustand ist von „N Korrekturen, 0 Fehler" **unterscheidbar**: im
  Leerzustand wird keine einzige Kriterien- oder Fehlerfallzeile dargestellt.

### Gewichte aus dem Feedback

- [ ] **G1** — Genau ein globaler Gewichtssatz, keine Bindung an Projekt oder Nutzer. Es gilt die
  jüngste Fassung. Ohne jede gespeicherte Fassung gelten die Startwerte aus `quality.py`.
- [ ] **G2** — Die wirksamen Gewichte sind die Überlagerung der geltenden Fassung über die
  Startwerte. Ein den Startwerten **unbekannter** Schlüssel der Fassung wird **verworfen**; ein der
  Fassung unbekannter Startwertschlüssel behält seinen Startwert. Der wirksame Schlüsselsatz ist
  damit immer exakt der Startwertsatz — insbesondere gelangt kein Kriterium mit Inhaltsaussage in
  den Qualitätswert.
- [ ] **G3** — Jedes abgeleitete Gewicht ist **strikt positiv** und weicht vom Startwert um weniger
  als die festgelegte Bandbreite ab. Ein Kriterium, dem durchgängig widersprochen wurde, wird
  abgewertet, nie invertiert und nie auf null gesetzt.
- [ ] **G4** — Bei null auswertbaren Paaren für ein Kriterium ist sein abgeleitetes Gewicht
  **exakt** sein Startwert — auch dann, wenn Paare vorliegen und alle auf diesem Kriterium
  Gleichstand zeigen, und auch dann, wenn andere Kriterien derselben Ableitung auswertbare Paare
  haben.
- [ ] **G5** — In die Ableitung gehen ausschließlich **gleichstufige** Austausche ein sowie, je Lauf
  und Event, jedes aufgenommene gegen jedes herausgenommene Foto derselben Stufe aus der
  Endauswahl. Ein Endauswahl-Ereignis ohne Lauf- oder Event-Bezug bildet kein Paar.
- [ ] **G6** — Die Anzeige vor dem Auslösen zeigt je Kriterium das geltende Gewicht, das abgeleitete
  und die Abweichung mit Vorzeichen. Wird die Anpassung ohne zwischenzeitliche Änderung übernommen,
  sind die gespeicherten Werte **exakt** die zuvor angezeigten.
- [ ] **G7** — Der Aufruf zur Übernahme trägt **ausschließlich** den Anker auf den zuletzt
  berücksichtigten Ereignisstand; er trägt keine Gewichtswerte, und ein Aufruf mit zusätzlichen
  Feldern wird abgewiesen. Der Server rechnet neu. Sind seit dem Anker Ereignisse hinzugekommen —
  gleich in welchem Projekt —, antwortet er `409` und schreibt **nichts**. Bei leerem Log ist der
  Anker `0` und die Übernahme möglich.
- [ ] **G8** — Die Anpassung wird ausschließlich von Hand ausgelöst; es gibt keine Schwelle, ab der
  sie von selbst geschieht.
- [ ] **G9** — Die Übernahme schreibt die neue Fassung und **sonst nichts**: Danach sind alle
  `rank_score`, `rank_position` und `selection_position` aller Läufe unverändert, es entsteht kein
  neuer Lauf, es wird kein Hintergrundjob eingereiht, und es ergeht kein Modell- oder Cloud-Aufruf.
  Erst der nächste Durchlauf rechnet mit den neuen Gewichten, liest sie **einmal je Lauf** und hält
  die benutzte Fassung an seiner Lauf-Zeile fest.
- [ ] **G10** — Zurücksetzen erzeugt eine **neue** Fassung mit den Werten der Vorgängerfassung; es
  wird nie eine Fassung gelöscht. Es ist ein **Umschalter**: Der zweite Druck führt zurück auf die
  Werte, von denen der erste zurückgesetzt hat, und geht nicht eine weitere Fassung rückwärts. Ohne
  Vorgängerfassung wird es nicht angeboten und der Aufruf abgewiesen. Der Aufruf nennt die Fassung,
  die zurückgenommen werden soll, und antwortet `409`, wenn sie nicht mehr die geltende ist.

## Datenmodell-Bezug

Drei neue Entitäten und eine neue Spalte an einer bestehenden; Einzelheiten unter „Architektur /
Umsetzung", Aufnahme in [`docs/architecture.md`](../../docs/architecture.md) je Pull Request.

- `FeedbackEvent` (`feedback_events`) — append-only Log der Nacharbeit.
- `QualityWeightSet` (`quality_weight_sets`) — eine Fassung des globalen Gewichtssatzes.
- `QualityWeightEntry` (`quality_weight_entries`) — ein Gewicht je Kriterium innerhalb einer Fassung.
- `CriterionScoringRun.quality_weight_set_id` — mit welcher Fassung dieser Lauf gerechnet hat.

Unverändert bleiben `Rating`, `PhotoMotifCorrection` und `FinalSelectionDecision`: Sie halten den
heutigen Stand, das Log hält, *dass* korrigiert wurde.

## Architektur / Umsetzung

Die Entscheidung ist als ADR
[`0100`](../decisions/0100-nacharbeit-als-ereignis-log-gewichte-persistiert-und-versioniert.md)
festgehalten. Sie löst keine bestehende ADR ab; sie setzt auf ADR
[`0098`](../decisions/0098-album-entwurf-aus-vorschlag-und-eigener-entscheidung.md) (die Gesten am
Entwurf) und ADR
[`0099`](../decisions/0099-endauswahl-als-projektentscheidung-ueber-zwei-entwuerfen.md) (die
gemeinsame Entscheidung) auf.

### Gewählter Ansatz

**Ein append-only Ereignis-Log neben dem unveränderten Zustandsmodell.** Drei Zusagen der Story
sind damit strukturell wahr statt durchgesetzt:

- **„bleibt erhalten, auch wenn zurückgenommen"** — auf die Tabelle läuft ausschließlich `INSERT`;
  kein `UPDATE`, kein `DELETE` außer der Projektlöschung.
- **„Reihenfolge erkennbar"** — die Reihenfolge *ist* die aufsteigende `id`, nie `occurred_at`: Zwei
  Schreibvorgänge derselben Sekunde sind über eine Zeit nicht zu ordnen.
- **„genau ein Satz Gewichte"** — es gilt die Fassung mit der höchsten `id`; es gibt kein
  `active`-Kennzeichen, das danebentreten könnte.

**Das Ereignis friert die Entscheidungslage ein, die lokalen Messwerte nicht.** Modellstufe,
Qualitätswert und Motivstärke werden mitgeschrieben, weil ein neuer Lauf sie überschreibt und die
Frage „zu schwach oder gar nicht genannt?" danach nicht mehr beantwortbar wäre. Die sieben
Kriterienwerte werden dagegen zur Auswertungszeit gelesen: Sie sind eine deterministische Messung
an denselben Pixeln, keine je Lauf neu erfragte Fremdaussage.

**Die Diagnose zählt projektübergreifend**, obwohl sie auf der Projekt-Statistikseite steht. Der
Gewichtssatz gilt global; zählten die Fallzahlen nur ein Projekt, stünden sie neben einem Vorschlag,
den sie nicht belegen. Die Beschriftung spricht das aus (D1).

### Datenmodell und Migration

`backend/src/photosort/models.py`; zwei Alembic-Revisionen (PR 1 und PR 3), die erste mit
`down_revision = "a1b2c3d4e5f6"` (Head nach Spec 0431), getestet im Muster von
`test_migration_endauswahl.py`, dazu Durchlauf von `test_postgres_ddl_compatibility.py`.

#### `feedback_events` (PR 1)

| Spalte | Form | Bedeutung |
|---|---|---|
| `id` | PK | **die Reihenfolge** |
| `project_id` | FK `projects.id`, NOT NULL, indiziert | eigene Spalte, nie über den Foto-Join hergeleitet |
| `user_id` | FK `users.id`, **nullable** | `NULL` = keine Zuschreibung (gemeinsame Entscheidung) |
| `photo_id` | FK `photos.id`, NOT NULL | das Foto, über das die Aussage geht |
| `kind` | `SQLEnum(native_enum=False, length=32)` | Vorrat unten |
| `occurred_at` | NOT NULL, `server_default=func.now()` | Anzeige, nie Sortierschlüssel |
| `weight` | float NOT NULL, `server_default="1.0"` | Multiplikator in der Ableitung |
| `criterion_scoring_run_id` | FK, nullable | der Lauf, auf dem der Entwurf beruhte |
| `event_id` | int, nullable, **ohne Fremdschlüssel** | Gruppierungsschlüssel, nur mit dem Lauf gültig |
| `replaced_photo_id` | FK `photos.id`, nullable | das ersetzte Bild |
| `motif_key` | str, nullable | |
| `motif_strength` | float, nullable | eingefrorene **gespeicherte** Modellstärke |
| `level` / `replaced_level` | int, nullable | eingefrorene Modellstufen |
| `quality` / `replaced_quality` | float, nullable | eingefrorene `rank_score` |

**`kind`-Vorrat, neun Werte:** `photo_included`, `photo_removed`, `decision_withdrawn`, `exchanged`,
`motif_added`, `motif_dropped`, `motif_correction_withdrawn`, `final_decision_in`,
`final_decision_out`.

Die Aussagerichtung steht als **eigener Wert**, nie als nullable Boolean daneben: Eine dritte
Bedeutung von `NULL` wäre auf keinem Lesepfad als Fehler erkennbar. Für die Endauswahl gibt es
folgerichtig keinen Rücknahme-Wert — ADR 0099 kennt kein `DELETE`.

**`user_id` ist nullable, und das ist keine Bequemlichkeit.** `set_album_decision` nimmt bewusst kein
`current_user` entgegen, weil die Entscheidung dem Projekt gehört. Den Endpunkt allein für das Log
um einen zu erweitern, führte das in ADR 0099 verworfene `decided_by` durch die Hintertür ein — und
das Log wäre der Ort, an dem man nachsieht, wer wollte, was das Projekt entschieden hat. Invariante,
an der Schreibstelle gehalten und getestet: `user_id IS NULL` genau für
`final_decision_in`/`final_decision_out`, nie sonst.

**`event_id` trägt keinen Fremdschlüssel**, weil `worker.py::rebuild_run_grouping` die `Event`-Zeilen
eines Laufs löscht und neu anlegt. Ein echter Fremdschlüssel hielte den Neuaufbau an oder risse
Log-Zeilen mit. Ein struktureller Wächter hält fest, dass keine Abfrage `FeedbackEvent.event_id`
gegen `Event.id` verbindet — die Spalte sieht wie eine Referenz aus und ist keine.

Die Feldmatrix je `kind` (welches Feld pflichtig, welches verboten) wird an der **einen**
Schreibstelle gehalten und über einen Fall je `kind` geprüft, nicht über neun `CheckConstraint`s.

`project_deletion.py` nimmt `feedback_events` in die geordnete Löschreihenfolge auf, **vor** `photos`
und `users`.

#### `quality_weight_sets` / `quality_weight_entries` (PR 3)

`quality_weight_sets`: `id` PK (= die Version), `created_at`, `created_by_user_id` FK NOT NULL,
`origin` (`feedback` | `revert`), `based_on_event_id` int nullable, `reverts_set_id` FK auf sich
selbst nullable.

`quality_weight_entries`: `set_id` FK, `criterion_key` **freier String ohne Fremdschlüssel**,
`weight` float, `UniqueConstraint(set_id, criterion_key)`, `cascade="all, delete-orphan"` vom Satz.
Freier String aus demselben Grund wie bei `photo_criterion_scores`: Ein neues Kriterium erzwingt nie
eine Migration.

**Ohne eine einzige Zeile gelten die Startwerte aus `quality.py`.** Keine Migration schreibt sie
ein — ein eingeschriebener Vorgabewert wäre von einer übernommenen Anpassung nicht mehr zu
unterscheiden.

`criterion_scoring_runs.quality_weight_set_id` FK nullable: mit welcher Fassung dieser Lauf gerechnet
hat. `NULL` heißt „Startwerte oder Altzeile". Beide Gewichtstabellen hängen an keinem Projekt und
bleiben von der Projektlöschung unberührt.

### Wo die Ereignisse entstehen

Ohne Verhaltensänderung der bestehenden Endpunkte, jeweils **vor** dem Commit und in derselben
Transaktion.

- **`api/ratings.py::_write_own_rating`** ist bereits *die eine* Schreibstelle und kennt den
  Bestandszustand. Sie bekommt `record: bool = True`. Abbildung: `album_worthy` → `photo_included`,
  `rejected` → `photo_removed`, `None` → `decision_withdrawn`. **Nur wenn
  `new_status != previous_status`.** Daraus fällt ohne Sonderfall heraus, dass
  `PUT /photos/{id}/favorite` kein Ereignis erzeugt — es lässt `status` unberührt, und der Favorit
  wirkt nach ADR 0098 nicht auf den Entwurf.
- **`api/photos.py::set_motif_correction` / `delete_motif_correction`** → `motif_added` /
  `motif_dropped` / `motif_correction_withdrawn`, ebenfalls nur bei tatsächlicher Änderung.
  Eingefroren wird `PhotoMotifStrength.strength`, **nie**
  `motif_strengths.py::effective_strength_expression`: Letztere trägt bereits eine frühere Korrektur
  desselben Paares, und die zweite Korrektur eines Motivs zeigte dann nie einen Modellfehler an.
- **`api/album_decisions.py::set_album_decision`** → `final_decision_in` / `final_decision_out` mit
  `weight=FINAL_DECISION_WEIGHT`, **ohne `user_id`**. Nur bei tatsächlicher Änderung: Der Endpunkt
  ist ein Upsert, und ein wiederholtes identisches `included` ist keine Korrektur. `project_id` kommt
  aus dem bereits geladenen `Photo`; `criterion_scoring_run_id` und `event_id` aus dem letzten
  erfolgreichen Lauf über dieselbe Einordnung, die `album_selection` benutzt.
- **Neuer Austausch-Endpunkt** → **ein** `exchanged`-Ereignis. Er ruft `_write_own_rating` zweimal
  mit `record=False`; ohne diese Unterdrückung zählte jeder Austausch dreifach.

**Die Transaktionsgrenze wandert aus `_write_own_rating` heraus zum Aufrufer.** Die Funktion
committet heute selbst; ein Parameter `record` allein macht den Austausch nicht atomar, weil der
erste Aufruf nach seinem Commit unwiderruflich geschrieben ist. Durch diese Stelle laufen drei
Bestandsendpunkte; deren Fälle in `test_api_ratings.py` sind der Regressionsnachweis und dürfen dabei
keine Erwartung verlieren.

### Die Diagnose-Berechnung

Neues **reines, DB-freies** Modul `backend/src/photosort/feedback.py`, im Muster von
`quality.py`/`selection.py`/`album_selection.py`:

- `MotifErrorCase` (`too_weak` | `missing` | `overcalled`) und
  `classify_motif_error(kind, model_strength) -> MotifErrorCase | None`. Die Präsenzgrenze wird über
  `selection.py::motif_is_present` gelesen, nie als Zahl — der bestehende Wächter verlangt, dass
  `MOTIF_PRESENCE_THRESHOLD` an genau einer Stelle vorkommt. Die Trennung `missing`/`too_weak` läuft
  über eine eigene Konstante `MOTIF_ABSENT_THRESHOLD`. Ein `motif_added` auf ein bereits getragenes
  Motiv, ein `motif_dropped` auf ein nicht getragenes und jedes `motif_correction_withdrawn` sind
  **kein** Fehler und ergeben `None`.
- `ExchangeKind` (`within_level` | `across_level` | `undetermined`) und
  `classify_exchange(level, replaced_level)`.
- `preferred_lower_rated(quality, replaced_quality) -> bool | None`. **Je Tauschart getrennt geführt,
  nie summiert.**
- `criterion_agreement(pairs)` und `derive_weights(agreements, baseline)`.
- Konstanten: `MOTIF_ABSENT_THRESHOLD`, `FEEDBACK_WEIGHT_SPAN` (strikt < 1), `PRIOR_STRENGTH`
  (> 0), `FINAL_DECISION_WEIGHT` (> 1) — dokumentierte unkalibrierte Startwerte in der Klasse von
  `LOCAL_CORRECTION_SPAN`.

**Das Verfahren, konkret** — eine Auszählung, kein Training, kein Modellaufruf. Für jedes Paar („der
Nutzer zog `B` dem `A` vor") und jedes Kriterium `k`, dessen Wert auf **beiden** Fotos vorliegt,
stimmt `k` mit dem Ereignisgewicht ab: zustimmend bei `v_k(B) > v_k(A)`, ablehnend bei `<`, gar nicht
bei Gleichstand.

```
zustimmung_k = (Σ zustimmend − Σ ablehnend) / (Σ zustimmend + Σ ablehnend)   ∈ [−1, 1]
w_k = startwert_k · (1 + FEEDBACK_WEIGHT_SPAN · zustimmung_k · n_k / (n_k + PRIOR_STRENGTH))
```

Der letzte Faktor ist eine **Schrumpfung gegen die Neutrallage**: Bei `n_k = 0` ergibt sich exakt der
Startwert — der Nullzustand fällt ohne Sonderfall heraus. Die Division wird **vor** ihrer Ausführung
gegen `n_k = 0` abgefangen, je Kriterium und nicht je Ableitung. Nur **Vorzeichen** werden
verglichen, nie Beträge, damit ein Kriterium mit gestauchtem Wertebereich nicht benachteiligt wird.
Ein durchgängig widersprechendes Kriterium wird **abgewertet, nie invertiert**: `local_correction`
renormiert auf die Gewichtssumme und kennt kein Vorzeichen — woraus zugleich folgt, dass nur die
**Verhältnisse** wirken und eine gleichmäßige Streckung aller sieben keinen Qualitätswert ändert.

**Iteriert wird über den Schlüsselsatz der Startwerte**, nie über die vorliegenden Messwerte:
`photo_criterion_scores` trägt Kriterien mit Inhaltsaussage, die `quality.py` bewusst nicht
gewichtet, und der umgekehrte Weg brächte eines davon in den Qualitätswert (G2).

**Zwei Paarquellen, und nur diese:**

1. Austausche mit `classify_exchange(...) == within_level` — das Paar steht explizit in der Zeile.
2. Gemeinsame Entscheidungen: je `(criterion_scoring_run_id, event_id)` tritt jedes
   `final_decision_in` gegen jedes `final_decision_out` **derselben `level`** an, mit
   `FINAL_DECISION_WEIGHT`. Die Gruppierung über das eingefrorene Event hält die Gegenüberstellung
   lokal — ohne sie verglichen wir einen Sonnenuntergang von Tag 1 gegen ein Abendessen von Tag 5.

Austausche über Modellstufen hinweg und Paare mit fehlender Stufe gehen **nicht** ein.

**Fallzahl:** Für die Rechnung zählt die gewichtete Stimmenzahl, **angezeigt wird die ungewichtete
Anzahl der Korrekturen** — eine gewichtete Zahl als Fallzahl behauptete Korrekturen, die niemand
vorgenommen hat.

Dazu `backend/src/photosort/feedback_log.py` (mit Session): die `record_*`-Funktionen als *die eine*
Schreibstelle und die Ladeabfragen der Diagnose. **Keine davon filtert nach Projekt.** Die lokalen
Kriterienwerte werden dort live aus `photo_criterion_scores` gejoint; ein Paar mit unvollständigen
Werten fällt heraus, und die Fallzahl macht das sichtbar.

### Die Gewichte

Heute liegen sie als `quality.py::QUALITY_CRITERION_WEIGHTS` (sieben Kriterien), gelesen an genau
zwei Stellen: `worker.py` und `demo_state.py`. Das bleibt so — nur die Herkunft des Werts wechselt.

Neues Modul `backend/src/photosort/quality_weights.py`:

- `effective_weights(session)` — die geltende Fassung **überlagert über die Startwerte**, in beide
  Richtungen geprüft (G2).
- `previous_weights(session)` — die Werte der Vorgängerfassung, Rückfall auf die Startwerte.
- `store_weights(...)` — legt eine neue Fassung an. **Zurücksetzen ist eine neue Fassung** mit den
  Werten der Vorgängerin, nie ein Löschen; die Kette bleibt lückenlos.
- Kein nicht-endlicher und kein nicht-positiver Wert erreicht die Persistenz, und der Lesepfad nimmt
  keinen an (S12).

`worker.py` liest die Gewichte **einmal je Lauf** vor der Partitionsschleife (`run_criterion_scoring`
und `rebuild_run_grouping`) — heute steht die Konstante innerhalb der Schleife, je Foto neu —, reicht
sie in `compute_quality_score` durch und schreibt die benutzte Fassung an die Laufzeile. Der
Anpassungs-Endpunkt löst **weder** `rebuild_run_selection` **noch** `rebuild_run_grouping` aus: das
ist „wirkt erst beim nächsten Durchlauf", und es ist der bewusste Gegensatz zu
`PUT /projects/{id}/selection-target`, das synchron neu rechnet.

### API-Schnitt

- **`POST /projects/{project_id}/draft/exchange`**, Body `{photo_id, replaced_photo_id}` — beide
  Bewertungszeilen in **einer** Transaktion, ein Ereignis. `404` ohne Projekt, `422` nach L3, `409`
  im Muster des bestehenden `flush`-Konflikts. Liefert beide Zeilenzustände, damit die Oberfläche
  wie bisher fortschreibt statt neu zu laden.
- **`GET /feedback/diagnosis`** — **ohne Projektparameter**, eigener Endpunkt statt einer Einbettung
  in `ProjectStatsOut`: Dieser Block rechnet projektübergreifend, ist spürbar teurer und wird nach
  einer Anpassung für sich neu geladen. Antwort: `correction_count`, `motif_errors[]`,
  `exchanges` (die drei Zahlen getrennt, je Art `preferred_lower_rated_count`), `weights` mit
  `current[]`, `proposed[]` (je Kriterium `weight`, `delta`, `case_count`, `agreement`),
  `based_on_event_id`, `can_revert`.
- **`POST /feedback/weights`**, Body `{based_on_event_id}` — rechnet den Vorschlag **serverseitig
  neu** und antwortet `409`, wenn seither Ereignisse hinzugekommen sind.
- **`POST /feedback/weights/revert`**, Body `{reverts_set_id}` — neue Fassung mit den Werten der
  Vorgängerin; `409`, wenn die genannte Fassung nicht mehr die geltende ist.

Alle drei `feedback`-Endpunkte hängen an einem Router mit
`dependencies=[Depends(get_current_user)]` und tragen ihren Eintrag in
`tests/test_auth_guard.py::_protected_router_operations()`.

### Reihenfolge der Umsetzung — drei Pull Requests

Jeder Schnitt ist für sich grün, für sich mergebar und hinterlässt keinen Zwischenzustand mit zwei
Wegen. Jeder steht für sich über dem Coverage-Gate von 80 %.

**PR 1 — „Die Nacharbeit wird festgehalten"**

1. `models.py` (`FeedbackEventKind`, `FeedbackEvent`) + Alembic-Revision
   (`down_revision = "a1b2c3d4e5f6"`) + Migrationstest.
2. `feedback_log.py` (die eine Schreibstelle) + Invariantentest über die Feldmatrix je `kind`,
   inklusive der `user_id`-Invariante.
3. `api/ratings.py` (`record`-Parameter, Transaktionsgrenze zum Aufrufer, nur bei tatsächlicher
   Änderung), `api/photos.py` (Motivkorrektur), `api/album_decisions.py` (gemeinsame Entscheidung,
   ohne Nutzer), neuer Austausch-Endpunkt in `api/photos.py`.
4. `project_deletion.py`, `demo_state.py` (Austausche und Entscheidungen mit Substanz erzeugen).
5. Frontend: `api/photos.ts`, `hooks/usePhotos.ts`, `DraftAlternativesDialog`/`AlbumDraftPage` — ein
   Aufruf statt zweier.
6. `docs/architecture.md` (Tabelle, Austausch-Endpunkt).

*Alleinstehend lauffähig und mit eigenem Nutzen, auch ohne Leser des Logs:* Der Austausch wird
atomar — heute sind es zwei Aufrufe, von denen der zweite fehlschlagen kann und einen halb
ausgeführten Austausch hinterlässt. Ab Merge füllt sich das Log, sodass PR 2 auf Daten trifft statt
auf einen Nullzustand, der sich nur behaupten lässt.

**PR 2 — „Die laufende Diagnose"**

1. `feedback.py` (rein, mit Tests) — muss grün sein, bevor der Endpunkt seinen ersten Fall bekommt.
2. `feedback_log.py` (Ladeabfragen), `api/feedback.py` (`GET /feedback/diagnosis`), Registrierung in
   `main.py`, `test_auth_guard.py` und `test_openapi_beschreibungen.py`.
3. Frontend: `api/feedback.ts`, `hooks/useFeedbackDiagnosis.ts`, `utils/feedbackDiagnosis.ts` (rein),
   `components/FeedbackDiagnosisSection.tsx` als `<Section>` in `ProjectStatsPage`.
4. `docs/architecture.md` (Endpunkt).

**PR 3 — „Gewichte aus dem Feedback"**

1. `models.py` (beide Gewichtstabellen + `criterion_scoring_runs.quality_weight_set_id`) + Revision +
   Migrationstest.
2. `quality_weights.py`, Umstellung von `worker.py` und `demo_state.py`.
3. `api/feedback.py` (Vorschlag im Diagnose-Ergebnis, `POST /feedback/weights`,
   `POST /feedback/weights/revert`).
4. Frontend: Vorschau-Tabelle mit Abweichung je Kriterium, Auslöser, Zurücksetzen.
5. `docs/architecture.md` (Tabellen, Endpunkte).

## UI/UX

Neue Sektion der Projekt-Statistikseite nach „Vertrauen und Fehlersuche": ein eigener `<section>` mit
`<h2>`, durchgehend die bestehende Formsprache (Whitespace, dezente Trennlinie `--separator` am Kopf,
keine Karten-Chrome). Keine neue Komponente und keine neue Abhängigkeit — `Section`, `MetricRow`,
`Metric`, `DetailRow`, `Button`, `AlertDialog`, `Alert` und `Skeleton` bestehen bereits. Bezug:
[`specs/architecture/0004-design-system.md`](../architecture/0004-design-system.md).

### Titel und Erklärebene

**Überschrift:** „Rückmeldung aus der Nacharbeit". Der Titel nennt weder Lernen noch Training — beides
findet nicht statt und ist ausdrücklich ausgeschlossen.

**Unmittelbar darunter, vor allen Inhalten**, eine Unterzeile (`text-xs text-text-muted`): Die Zahlen
dieses Abschnitts zählen die Korrekturen **beider Nutzer über alle Projekte hinweg**, weil die
Gewichte global gelten. Sie behält ihren Platz auch im Leer-, Lade- und Fehlerzustand. Ohne sie liest
jeder die Zahlen als Aussage über das offene Projekt — genau der Fehlschluss, den die
projektübergreifende Zählung sonst einlädt (D1).

### Aufbau

1. **Leerzustand (null Korrekturen).** Ein Hinweistext statt der Inhalte: dass noch keine Korrekturen
   vorliegen, und wodurch sie entstehen — Bilder im Album-Entwurf austauschen, aufnehmen, streichen,
   Motive korrigieren. Keine einzige Fehlerfall- oder Kriterienzeile wird dargestellt, damit dieser
   Zustand von „N Korrekturen, 0 Fehler" unterscheidbar bleibt (D6).
2. **Motivfehler.** Drei `Metric` in einer `MetricRow`: „Zu schwach erkannt", „Gar nicht erkannt",
   „Vom Modell genannt, von uns weggenommen". Kein Fachjargon. Je Kennzahl die Fallzahl und daneben
   klein die Bezugsgröße („von X Korrekturen"). Auf Mobilbreite gestapelt.
3. **Austausche.** Drei `DetailRow`: gleichstufig, stufenübergreifend, unbestimmt — je mit Fallzahl
   und, wo größer als null, der Zusatz, wie oft dabei ein schlechter bewertetes Bild vorgezogen
   wurde. Die drei Zahlen stehen nie summiert nebeneinander (D3).
4. **Gewichts-Vorschau.** Tabelle je Kriterium: geltendes Gewicht, Vorschlag, Abweichung, Fallzahl.
   Die Belastbarkeit trägt allein die sichtbare Fallzahl — keine Fettschrift-Schwelle, die eine
   Belastbarkeitsgrenze behauptet, die niemand festgelegt hat.
5. **Handlungsbereich.** „Gewichte anpassen" (primär, öffnet den Bestätigungsdialog) und „Auf vorige
   Gewichte zurücksetzen" (sekundär, nur bei `can_revert`). Darüber der Hinweis, dass die Änderung
   erst beim nächsten Durchlauf wirkt — ohne ihn erwartet jeder eine sofortige Änderung seines
   offenen Entwurfs.

**Zahlenformat:** Gewichte auf zwei Nachkommastellen. Die Abweichung trägt `+` oder `−`; eine
Abweichung von exakt null wird als `0.00` **ohne** Vorzeichen gezeigt.

**`agreement` wird nicht dargestellt.** Fallzahl und Abweichung tragen die Aussage bereits; die
Zustimmungsrate daneben wäre eine dritte Zahl zur selben Sache, die im Zweifel gegen die Abweichung
gelesen wird, aus der sie stammt. Über den Endpunkt bleibt sie verfügbar (D5 ist damit über die
Fallzahl je Kriterium erfüllt).

### Zustände

- **Ladend:** Skeleton für Kennzahlen, Tauschzeilen und drei Tabellenzeilen. Unterzeile bleibt.
- **Fehler:** `Alert` mit Wiederholen; betrifft nur diesen Abschnitt, nicht die Seite. Unterzeile
  bleibt.
- **Nach Anpassung:** kurze Bestätigung an der Tabelle, „Auf vorige Gewichte zurücksetzen" wird
  sichtbar.
- **Nach Zurücksetzen:** kurze Bestätigung; die Tabelle zeigt wieder die geltenden Werte.

### Dialog

`AlertDialog` mit der verkürzten Gegenüberstellung (Kriterium, geltend, neu) und den Schaltflächen
„Anpassen"/„Abbrechen". Er ist die Einlösung von „vor dem Auslösen ist erkennbar, was sich ändert".

### Barrierefreiheit und Breite

`scope="col"`/`scope="row"` an der Tabelle, `<dl>`/`<dt>`/`<dd>` an den Detailzeilen,
`role="alertdialog"` mit beschreibendem Titel, Trefferflächen 44 × 44 px, durchgehende
Tastaturbedienung. **Keine Aussage allein über Farbe** — Tauscharten unterscheiden sich durch ihr
Label, die Abweichung durch ihr Vorzeichen im Text, die Belastbarkeit durch die Fallzahl. Auf
Mobilbreite: Kennzahlen und Schaltflächen gestapelt, die Tabelle mit horizontalem Scroll im eigenen
Container statt umstrukturiert; Kriteriennamen brechen.

## Teststrategie

### Die Zusicherungen, die ohne eigenen Testfall still brechen

- **Kein Ereignis ohne Änderung**, drei Hälften in **einem** Fall: derselbe Status erneut gesetzt →
  0; nur `favorite` umgeschaltet → 0; anderer Status → genau 1. Der mittlere ist der gefährliche:
  `set_favorite` läuft durch dasselbe `_write_own_rating`, und mit `record=True` als Vorgabewert
  zeichnet es die Auszeichnung als Favorit auf. Getrennt geschrieben besteht jede Hälfte auch bei
  einer Umsetzung, die immer oder nie aufzeichnet.
- **Atomarität des Austauschs:** ein Fall, in dem der zweite Schreibvorgang scheitert, mit drei
  Assertionen — keine der beiden `Rating`-Zeilen geändert, kein Ereignis geschrieben, Antwort kein
  `200`. Gegenstück im selben Fall: ein erfolgreicher Austausch schreibt **genau ein** Ereignis
  (`== 1`, nicht „es gibt ein `exchanged`") — sonst bleibt das ausgeschlossene zusätzliche
  Streich-/Aufnahme-Paar unsichtbar und jeder Austausch zählt dreifach.
- **Reihenfolge:** Der Fall setzt `occurred_at` **gleich** und prüft die vollständige Id-Folge. Mit
  natürlich verschiedenen Zeitstempeln bestünde er auch gegen ein `ORDER BY occurred_at`, und unter
  SQLite ist eine unvollständige Sortierung zufällig stabil.
- **Ereignis überlebt Neuklassifikation:** Der Nachweis ist der **eingefrorene Wert**, nicht das
  Vorhandensein der Zeile — Stärke einfrieren, Lauf schreibt einen anderen Wert, `classify_motif_error`
  sagt weiter dasselbe. Zweiter Weg: `rebuild_run_grouping` löscht und erneuert die `Event`-Zeilen;
  danach sind alle Ereignisse unverändert da und die Diagnose liefert dieselben Zahlen.
- **Zurückgenommene Korrektur:** Das Rücknahme-Ereignis kommt hinzu, das ursprüngliche bleibt
  wortgleich stehen, und die Fallzahl ist danach **unverändert**. Die beiden naheliegenden Fehler
  (erstes Ereignis löschen; Rücknahme abziehen) liefern beide plausible Zahlen.
- **„Wirkt erst beim nächsten Durchlauf"** ist zur Hälfte der Nachweis, dass es überhaupt wirkt: Die
  vollständige Abbildung `photo_id → (rank_score, rank_position, selection_position, event_id)` ist
  vorher und nachher identisch, kein neuer Lauf, null Einreihungen beim Fake-Enqueuer — **und**
  danach `rebuild_run_grouping` auslösen und zusichern, dass sich mindestens ein `rank_score`
  **ändert**. Ohne die zweite Hälfte besteht die erste auch gegen eine Umsetzung, die Gewichte
  speichert, die nie jemand liest. Die gewählten Gewichte dürfen dafür keine gleichmäßige Streckung
  sein.
- **Renormierungs-Invarianz** (`compute_quality_score` ist gegenüber `{k: c·w_k}` für jedes `c > 0`
  unverändert) gehört nach `test_quality.py`, nicht nach `test_feedback.py`: Es ist die Eigenschaft
  des Bestandscodes, auf der die Abwertungsaussage überhaupt ruht.
- **Ein Paar, das ausschließlich in einem Inhaltskriterium abweicht,** ändert **kein** Gewicht, und
  der Schlüsselsatz bleibt exakt der Startwertsatz. Eine Ableitung, die über die vorliegenden
  Messwerte iteriert, brächte ein Inhaltskriterium in den Qualitätswert, ohne dass
  `test_quality.py::TestTheWeightTableCarriesNoContentSignal` rot würde.

### Die drei nicht per Constraint erzwungenen Invarianten

1. **Feldmatrix je `kind`** — Verhalten: ein Fall je `kind`, parametrisiert über
   `tuple(FeedbackEventKind)` (nicht über eine zweite Aufzählung), geschrieben über den
   Produktionsweg, Assertion auf den **exakten** Satz belegter Felder, dazu
   `len(tuple(FeedbackEventKind)) == 9`. Struktur: AST-Wächter über den Konstruktionsstellen von
   `FeedbackEvent`, **Gleichheit** der Fundmenge gegen die benannte Liste, je Schreibform ein
   Mikrotest, plus Positiv-Gegenprobe. Die Matrix hält nur, solange es genau die bekannten
   Schreibstellen gibt; eine weitere rötet keinen Verhaltensfall.
2. **`user_id IS NULL` genau für die Endauswahl** — Verhalten als Allaussage über die Matrix, beide
   Richtungen in einem Fall. Struktur: Wächter auf Funktionsrumpf-Granularität über
   `api/album_decisions.py` — keine Funktion nimmt `current_user` entgegen, keine liest `User`. Mit
   zwei Gegenproben, die hier tatsächlich tragen: Die bloße **Nennung** im Kommentar darf nicht
   anschlagen (der Modulkopf begründet genau das), und die pflichtige Router-Dependency muss
   vorhanden bleiben — ohne sie wäre der Wächter durch Entfernen der Authentifizierung zu erfüllen.
3. **`event_id` ohne Fremdschlüssel** — vier Nachweise, weil kein einzelner trägt: am Modell
   (`event_id.foreign_keys == set()` **und** `photo_id.foreign_keys != set()` im selben Fall, sonst
   bestünde die Aussage auch für eine Tabelle ganz ohne Fremdschlüssel); an der gerenderten
   Postgres-DDL, weil die Suite ohne `PRAGMA foreign_keys=ON` läuft und ein ergänzter Schlüssel dort
   strukturell nicht auffiele; als AST-Wächter gegen jede Verbindung der beiden Spalten mit
   Selbstschutz-Gegenproben; und als Verhaltensfall über `rebuild_run_grouping`.

### Edge Cases

**Rechenverfahren.** `n_k = 0` mangels Paaren → Gewicht **exakt** der Startwert (Gleichheit, kein
`approx`). `n_k = 0` bei vorhandenen Paaren mit durchgehendem Gleichstand → dasselbe, ohne Division:
Ein Schutz der Form `if not pairs: return startwerte` besteht den ersten Fall und wirft hier.
`n_k = 0` für ein Kriterium bei `n_j > 0` für ein anderes in **derselben** Ableitung → `w_k`
unverändert, `w_j` bewegt; ein je Ableitung statt je Kriterium gezogener Frühausstieg besteht die
ersten beiden und liefert hier überall stillschweigend die Startwerte. Vollständige Ablehnung
(`−1`) → strikt positiv und strikt größer als `start·(1−SPAN)`; ein Gewicht null ließe das Kriterium
aus der Renormierung ganz herausfallen, was etwas anderes ist als abgewertet. Vollständige Zustimmung
spiegelbildlich. Austausch und seine Umkehr → zwei Ereignisse, `n_k` wächst um 2, Gewicht exakt der
Startwert, **keines** löscht das andere; nur die Fallzahl trennt das von einer Umsetzung, die die
Umkehr als Rücknahme behandelt.

**Fehlende Werte.** Foto ohne Kriterienwerte und Paar mit nur einseitigen Werten gehen in kein `n_k`
ein, und die Assertion gilt für **alle sieben** Kriterien, nicht nur die fehlenden. Disjunkte
Kriteriensätze → Beitrag null. Foto ohne Modellstufe → Ereignis entsteht, Paar ist `undetermined`.
`rank_score`-Gleichstand beim Austausch → eigene Zahl, nie einer der beiden Seiten zugeschlagen.

**Gewichte und Nebenläufigkeit.** `409` paarweise in einem Fall: veralteter Anker → `409` **und keine
neue Fassung geschrieben** (die negative Hälfte ist die tragende); aktueller Anker → Erfolg. Das
dazwischengekommene Ereignis stammt aus einem **anderen Projekt** → trotzdem `409`, sonst ist eine
projektskopierte Konflikterkennung von der globalen nicht unterscheidbar. Leerer Log → Anker `0`,
Übernahme läuft durch. Zweimal Zurücksetzen → fünf Fassungen in der Kette, keine gelöscht, die
Wertefolge je Fassung vollständig geprüft; der zweite Druck führt auf die Werte des ersten
Ausgangspunkts zurück (G10). Zurücksetzen ohne Vorgängerfassung → abgewiesen. Kriterium kommt nach
einer Fassung hinzu, **paarweise in einem Fall**: unbekannter Startwertschlüssel behält seinen Wert
**und** ein den Startwerten unbekannter Schlüssel der Fassung erscheint **nicht** im wirksamen Satz.
Die erste Hälfte allein bestünde auch gegen `{**startwerte, **fassung}` — und genau das ist der Weg,
auf dem ein entfallenes Kriterium ein Gewicht behält.

**Konstanten** je als Literal festgenagelt plus als Ungleichung mit dem Grund im Docstring.

### Ebenen

- **Unit (rein, DB-frei):** `feedback.py` vollständig, `derive_weights`/`criterion_agreement` mit dem
  Randfallsatz oben, `effective_weights`/`previous_weights` gegen eine **übergebene**
  Startwerttabelle (nicht gegen die Modulkonstante, sonst ist „Kriterium kommt später hinzu" nur per
  `monkeypatch` erreichbar), dazu ein Reinheitswächter (weder `sqlalchemy` noch `photosort.models`).
  Die Übergangsregel „welcher `kind` aus welchem Zustandswechsel" liegt als reine Funktion neben
  `_write_own_rating`, nicht im Endpunkt.
- **Integration (Schwerpunkt, In-Memory-SQLite, `httpx.ASGITransport`):** je Schreibstelle
  Vorhandensein/Abwesenheit und Feldbelegung; `GET /feedback/diagnosis` inklusive eines Ereignisses
  aus einem **zweiten** Projekt (ein Fall mit nur einem Projekt ist von einer projektskopierten
  Umsetzung nicht unterscheidbar); die Gewichts-Endpunkte; die Worker-Zusage.
- **Migration:** Kettenanschluss, Spaltensatz exakt, Nullbarkeit je Spalte, `downgrade()` mit
  Verlusthinweis im Docstring; Postgres-DDL.
- **Frontend (vitest):** `useDraftExchangeMutation` von zwei `setRating`-Aufrufen auf einen
  `exchangeDraft`-Aufruf; die bestehenden Fälle werden **umgeschrieben, nicht gelöscht**, und die
  tragende Assertion ist die negative — `setRating` wird kein einziges Mal aufgerufen. Ohne sie
  bleibt ein stehengebliebener Doppelschreibweg unsichtbar und erzeugt drei Ereignisse je Austausch.
  Dazu der Diagnoseabschnitt mit Leerzustandsprüfung; die Fallzahl je Aussage über ein semantisches
  Attribut, nie über formatierten Text.
- **Projektlöschung:** deckt sich über den Vollständigkeitswächter gegen `Base.metadata` ab. Ein
  eigener Fall ist für die **Gegenrichtung** nötig — die beiden Gewichtstabellen dürfen dort nicht
  auftauchen.
- **Demo-Seeder:** `demo_state.py` erzeugt alle drei Tauscharten und mindestens einen
  Motiv-Fehlerfall. Das ist keine Kosmetik: Die E2E-Spec misst die Statistik-Route bereits, und ohne
  Substanz misst sie dauerhaft den Leerzustand, ohne dass etwas rot wird.
- **Kein neues E2E.** Aufnahmekriterium der Ebene ist, was jsdom prinzipiell nicht kann; der
  Abschnitt ist gewöhnliches DOM und wird von den vorhandenen Routen-Specs erfasst.

**Ein Zwischenzustand ohne Leser ist kein Handeinfügen:** In PR 1 prüfen Tests die geschriebene Zeile
per `select(FeedbackEvent)`, weil der Lesepfad erst mit PR 2 entsteht. Das Muster, das
handeingefügte Zeilen bei abgeschaltetem **Schreib**pfad beanstandet, trifft hier nicht zu.

**Testkonzept:** `specs/architecture/0002-testkonzept.md` bekommt eine neue Backend-Sektion mit den
sechs Mustern, die über dieses Feature hinaus gelten (append-only Log; Reihenfolgezusage auf einer
laufenden Nummer; Spalte mit Referenz-Aussehen ohne Referenz; Verfahren mit Schrumpfung gegen eine
Neutrallage und seinen drei entarteten Wegen; Ableitung, die die Invarianten der neu belegten Größe
erbt; „wirkt erst beim nächsten Durchlauf" als zweiseitiger Nachweis) — ergänzt in PR 1.

## Security

Einstufung: **sicherheitsrelevant, kein Blocker.** Keine Secrets, kein externer Dienst, kein
Cloud-Aufruf, kein Bilddatenfluss, kein Fremdtext von außen, keine neue Umgebungsvariable. Neu sind
drei Tabellen, der erste Schreibendpunkt, der zwei Bewertungszeilen in einem Zug ändert, zwei
Schreibendpunkte auf eine global wirkende Grundlage, ein Lese-Endpunkt ohne Projekt- und Nutzerbezug,
und die erste Tabelle, die **Verlauf statt Zustand** hält. Abgleich mit
[`specs/architecture/0003-securitykonzept.md`](../architecture/0003-securitykonzept.md); dieses
Dokument wird in PR 1 um einen Abschnitt und drei Ankerzeilen ergänzt.

**S1 — Auth an allen vier neuen Endpunkten, zweifach gesichert.** Der `feedback`-Router trägt
`dependencies=[Depends(get_current_user)]` **und** seinen Eintrag in
`test_auth_guard.py::_protected_router_operations()`; der Austausch-Endpunkt hängt an `photos.router`
und trägt die Dependency ausgeschrieben. Für `photos.router` gibt es kein Vollständigkeitsnetz — ein
dort vergessener `current_user`-Parameter ist **still öffentlich**: kein Fehler, keine 401, sondern
ein unauthentifizierter Schreibzugriff, der zwei Bewertungszeilen ändert. Jeder der vier Endpunkte
bekommt seinen eigenen, pfadbenannten 401-Nachweis. Die deklarativen Grenzen der Pfad-Id müssen den
vom Vollständigkeitstest eingesetzten Wert `1` zulassen, sonst antwortet er `422` statt `401` und
prüft die Auth gar nicht mehr.

**S2 — Die Projektbindung des Austauschs läuft über die Rangzeile, nicht über das Foto.** Beide Ids
des Bodys werden ausschließlich über eine Zeile von `PhotoRanking` mit dem Prädikat
„jüngster erfolgreicher Kriterienlauf dieses Projekts" aufgelöst, nie über `session.get(Photo, …)`
mit nachgelagerter Projektprüfung. Grund: `PhotoRanking` trägt keine `project_id`, `event_id` ist ein
globaler Surrogatschlüssel, und ohne das Laufprädikat identifiziert eine Id aus Projekt B unter
`/projects/A/…` eindeutig fremde Zeilen — der Endpunkt liefe dann nicht in eine erkennbar falsche
Menge, sondern **tauschte kohärent zwei Bilder eines fremden Projekts**. Die untersagte Alternative
ist die nachgelagerte Prüfung auf `Photo.project_id`; sie ist keine zweite Verteidigungslinie,
sondern der Ersatz der richtigen Bedingung durch eine schwächere.

**S3 — Beide Fotos liegen im selben Event desselben Laufs, und `event_id` stammt aus dessen
Rangzeile.** Ohne diese Bedingung paart ein Client zwei Bilder verschiedener Events; die Zeile trägt
dann die `event_id` des ersetzten Fotos, und die Ableitung rechnet über eine Gegenüberstellung, die
es nie gab — ohne Fehler und an keinem Ergebnis erkennbar. `event_id` kommt nie aus dem Body.

**S4 — Das Eingabeschema des Austauschs trägt genau zwei Felder, beide mit deklarativen Grenzen.**
`photo_id` und `replaced_photo_id`, jeweils `ge=1, le=1_000_000_000` (ein unbeschränkter
Pydantic-`int` erzeugt unter SQLite jenseits von 2^63 einen `OverflowError` und damit `500` statt
`422`). Kein `user_id`, kein `event_id`, kein `weight`, kein `kind`, kein `criterion_scoring_run_id`,
kein `motif_strength` — Massenzuweisung ist strukturell ausgeschlossen, nicht im Handler
herausgefiltert. `weight` wiegt am schwersten: Es ist der einzige Wert, mit dem ein Aufrufer die
eigene Korrektur in der global wirkenden Gewichtsableitung überproportional zählen ließe.

**S5 — Ein Austausch ist eine Transaktion und läuft durch `_write_own_rating`.** Die Funktion
committet heute selbst; der Austausch braucht eine commit-freie Variante und committet genau einmal
über beide Zeilen und das Ereignis. Zwei getrennte Commits lassen den halb ausgeführten Austausch
bestehen — jetzt zusätzlich mit einem Ereignis, das ihn als vollständig ausweist. Ein eigener
Schreibpfad daneben ist untersagt: Dort und nur dort wird die Invariante aus Spec 0430 durchgesetzt
(nie `status IS NULL AND favorite IS FALSE`), und eine zweite Stelle läuft auseinander.

**S6 — `based_on_event_id` ist das Zustimmungs-Token, nicht ein Objektverweis.** Es wird nie zu einer
Zeile aufgelöst und trägt keine Autorisierung; es ist das Einzige, was „der Nutzer hat übernommen,
was ihm angezeigt wurde" wahr macht. Geprüft wird **strikte Gleichheit** gegen die höchste `id` des
**gesamten** Logs, nie gegen ein nach Projekt oder Art gefiltertes Maximum; sonst gehen Ereignisse
unbemerkt durch, und die Fassung entsteht gegen eine Lage, die niemand gesehen hat. Bei leerem Log
ist der Wert `0`, von der Diagnose ausgewiesen — ohne einen definierten Wert wäre der erste
Schreibvorgang ungeprüft. Deklarative Grenzen wie in S4. Untersagte Alternative: den Vorschlag beim
Schreiben neu rechnen und ohne Abgleich übernehmen — dann trägt „jede Anpassung wird vorher
angezeigt" nichts mehr. Gewichte kommen nie aus dem Body.

**S7 — Auch die Rücknahme trägt einen Wächter.** `POST /feedback/weights/revert` nennt die Fassung,
die zurückgenommen werden soll, und antwortet `409`, wenn sie nicht mehr die geltende ist. Ohne ihn
legen zwei Aufrufe kurz hintereinander (Doppelklick, zweites Gerät, Wiederholung nach
Zeitüberschreitung) erst die Rücknahme und dann deren Rücknahme an: Das Ergebnis ist der
Ausgangszustand, die Kette sieht lückenlos aus, und keine Anzeige weist das als falsch aus.

**S8 — Die Diagnose liefert ausschließlich Aggregate.** Keine Einzelereignisse, keine `user_id`,
keine Foto-Id-Listen, keine Aufschlüsselung je Nutzer. Das ist die einzige Auflage, die das Log vom
Zustandsmodell unterscheidet: Es hält **zurückgenommene** Korrekturen fest, die der Bestand nicht
mehr zeigt. Alles andere, was die Diagnose zählt, ist über `PhotoOut.ratings[]` ohnehin je Foto und
namentlich lesbar — die Aggregation ist strikt weniger Information, nicht mehr. Ein späterer
Verlaufs-Lesepfad ist eine neue Entscheidung, keine Erweiterung dieser.

**S9 — `user_id IS NULL` der gemeinsamen Entscheidung wird nie aufgefüllt.** Strukturell getragen,
weil `album_decisions.router` kein `current_user` kennt. Ein Ereignisschreiber, der sich dafür eines
besorgt, führt das in ADR 0099 verworfene `decided_by` ein — und das Log wäre der Ort, an dem man
nachsieht, wer wollte, was das Projekt entschieden hat.

**S10 — Append-only wird strukturell festgehalten, nicht nur zugesagt.** Ein Wächtertest hält fest,
dass außerhalb von `project_deletion.py` kein Modul `update(FeedbackEvent)` oder
`delete(FeedbackEvent)` absetzt. Weder Schema noch Datenbank erzwingen die Zusage; ihr Bruch — eine
spätere Bereinigungsmigration, ein Feature, das ein Ereignis „korrigiert" — nimmt still weg, worauf
sich jede Zahl der Diagnose stützt.

**S11 — Der Ereigniseintrag der Motivkorrektur steht hinter der Schlüsselprüfung.** Nie aus dem rohen
Pfadparameter vor der Prüfung. Sonst gelangt eine beliebige, vom Aufrufer gewählte Zeichenkette in
die Persistenz und von dort in die nach Motiv gruppierte Diagnoseantwort — und die Prüfung gegen das
geschlossene Motiv-Set wäre für den einen Pfad umgangen, der sie nicht nachholt.

**S12 — Kein `NaN`, kein `Inf`, kein Wert ≤ 0 erreicht `quality_weight_entries`, und der Lesepfad
nimmt keinen an.** Die Ableitung teilt durch die Stimmenzahl, die bei einem Kriterium ohne Stimmen
null ist; `n_k = 0` muss **vor** der Division abgefangen werden. Ein gespeichertes `NaN` vergiftet
danach jeden Qualitätswert aller Projekte, ohne einen Fehler zu erzeugen: `total_weight <= 0` ist für
`NaN` falsch, `min`/`max` reichen es durch, `compute_quality_score` liefert `NaN`, und die Rangfolge
wird beliebig — ohne Logzeile, bis zum nächsten Lauf unbemerkt. Ein negatives Gewicht wäre zudem die
ausgeschlossene Invertierung eines Kriteriums.

**S13 — Die Projektlöschung nimmt `feedback_events` mit.** Position nach
`reversed(Base.metadata.sorted_tables)`, abgesichert vom Vollständigkeitswächter. Ohne die Anweisung
überleben Aussagen über gelöschte Familienfotos ihr Projekt. Die beiden Gewichtstabellen bleiben
bewusst stehen — sie tragen sieben Zahlen und einen Nutzerverweis, keinen Foto-Bezug, und sind auf
kein Foto zurückzurechnen.

**S14 — Der `422`-Fall des Austauschs ist für die unbekannte und die projektfremde Id identisch**, in
Status und Text. Verschiedene Antworten machten den Endpunkt zum Existenz-Orakel über fremde
Foto-Ids.

**Ausdrücklich geprüft und ohne Befund:** Keine neue Datenklasse zwischen den beiden Nutzern — die
Albumentscheidungen des anderen stehen namentlich in `PhotoOut.ratings[]`, der volle Projektbestand
in `GET /projects/{id}/photos`, und Motivkorrekturen sind ohnehin eine geteilte Zeile; die
Entwurfs-Trennung ist eine Ansichts-, keine Vertraulichkeitsgrenze. Die **Cache-Schlüssel-Auflage
greift hier nicht**: `GET /feedback/diagnosis` ist in Menge und in jedem Feld nutzerunabhängig,
keine der beiden Ursachen liegt vor; die Veralterung, die sie sonst mitbehandelt, fängt
`based_on_event_id` mit `409`. Das steht hier, weil die vorangegangenen Specs sie tragen und ihre
Abwesenheit sonst wie ein Versehen aussähe. `criterion_key` ist auf dem Schreibweg kein
Nutzereingabewert. Kein Rate-Limiting, konsistent mit der übrigen API — dass die Diagnose bei jedem
Aufruf über das gesamte Log rechnet, ist bei zwei Nutzern bewusst getragen.

## Entscheidungen

- **Aufteilung in drei Pull Requests** (Daniel, beim Schärfen dieser Spec): Der Umfang liegt über
  Spec 0430, die bereits als drei PRs lief. Jeder Teil ist für sich grün und mergebar; Teil 1 trägt
  mit dem atomaren Austausch einen eigenen Nutzen.
- **Die Diagnose zählt projektübergreifend** (Daniel): damit die Fallzahlen die Belege des global
  geltenden Gewichtsvorschlags sind. Der Preis — eine Zahl auf der Projektseite, die nicht dieses
  Projekt beschreibt — ist gesehen und wird durch die Beschriftung ausgesprochen (D1).
- **Die Endauswahl bildet Paare aus aufgenommen gegen herausgenommen derselben Modellstufe** je Lauf
  und Event (Daniel): dieselbe Aussageform wie ein Austausch. Stufenübergreifende Paare bleiben
  draußen, damit die Aussage über die lokalen Kriterien nicht mit der über das Modell vermischt wird.
- **Keine Aufschlüsselung der Diagnose je Nutzer** (Claude, als Auflage S8 festgeschrieben): Die
  Story verlangt sie nicht, und es wäre die erste Ansicht, die die beiden Personen gegeneinander
  stellt. Vertraulich wäre sie unbedenklich — die Daten sind längst je Foto und namentlich lesbar.
- **Zurücksetzen ist ein Umschalter, kein schrittweises Rückwärtsgehen** (Claude): Die Story sagt „auf
  die zuvor geltenden Werte". Der Umschalter folgt direkt aus `previous_weights` und braucht keine
  zweite Zustandsgröße neben der Kette.
- **Der Austausch verlangt beide Fotos im selben Event desselben Laufs** (Claude): Ohne die Bedingung
  ist unbestimmt, welches `event_id` das Ereignis trägt (S3).
- **Der Anker bei leerem Log ist `0`** (Claude): Ohne definierten Wert wäre der erste Schreibvorgang
  ungeprüft (S6).
- **`agreement` wird berechnet und ausgeliefert, aber nicht dargestellt** (Claude): Fallzahl und
  Abweichung tragen die Aussage; eine dritte Zahl zur selben Sache wird gegen die Abweichung gelesen,
  aus der sie stammt.
- Alle vier Konsultationen des `spec-writer`-Ablaufs sind gelaufen (`architect`, `ux-ui-designer`,
  `test-engineer`, `security-engineer`); keine wurde übersprungen.

## Offene Fragen

Keine.

## Out of Scope

- Kein Modelltraining und kein Labeln von Fotos von Hand.
- Keine neue Modellanbindung und kein Wechsel des Modells. Der Vergleich stärkerer Modelle (#420) und
  die Bewertung spezialisierter Modelle (#423) bleiben eigene Stories; diese liefert ihnen die
  Grundlage.
- Wie ein Auswahlvorschlag grundsätzlich zustande kommt, ändert sich nicht — nur die Gewichte, mit
  denen er gerechnet wird.
- Keine Gewichte je Projekt oder je Nutzer.
- Kein Lesepfad auf Einzelereignisse und kein Verlaufs-Endpunkt (S8).
