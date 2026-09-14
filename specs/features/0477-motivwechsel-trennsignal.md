# 0477 - Motivwechsel als Trennsignal für Events

**Status:** Implemented ([PR #491](https://github.com/TheRealKoller/photosort/pull/491))
**Erstellt:** 2026-09-14
**Bezug:** [Issue #477](https://github.com/TheRealKoller/photosort/issues/477)

**Umfang:** über dem Richtwert von rund 200 Zeilen, weil der Prüfsatz die Unterscheidung dreier
Abwesenheitszustände und die Nicht-Pinnung zweier Stellschrauben trägt, und weil vier
Sicherheitsauflagen in ihren drei Teilen vollständig bleiben.

## Ziel

Ein Reisetag besteht aus Situationen, die einander ablösen: erst der Ruinenbesuch, dann das
Mittagessen im Lokal um die Ecke. Heute verschmelzen die beiden zu einem einzigen Event, weil
keines der bestehenden Trennsignale greift — die Pause ist zu kurz, und der Weg ist zu kurz.

Das trifft nicht nur die Überschrift im Album. Die Auswahl-Richtwerte werden je Event vergeben:
Ein verschmolzenes Event bekommt einen Richtwert statt zwei, und die schwächer vertretene Situation
verliert dabei ihre Plätze. Das Mittagessen verschwindet aus dem Album, obwohl es ein eigener Teil
des Tages war.

Diese Spec ergänzt den Motivwechsel als weiteres Trennsignal: Ändert sich, was auf den Fotos zu
sehen ist, beginnt ein neues Event — auch dann, wenn Zeit und Ort unauffällig bleiben.

## User Story

Als jemand, der nach einer Reise seine Fotos durchgeht, möchte ich, dass ein neues Event auch dann
beginnt, wenn sich das Gezeigte deutlich ändert, damit aufeinanderfolgende Situationen am selben Ort
getrennt bleiben und jede von ihnen im Album ihren eigenen Platz bekommt.

## Akzeptanzkriterien

**Wann ein Motivwechsel trennt**

- [ ] Ein Motiv gilt als getragen, wenn seine **wirksame** Stärke die geteilte Präsenzgrenze
      erreicht — inklusiv, dieselbe Grenze wie im Auswahlvorschlag, keine eigene. Eine Event-Grenze
      entsteht, wenn sich die Menge der getragenen Motive gegenüber dem **eröffnenden Foto des
      laufenden Motivabschnitts** unterscheidet (symmetrische Differenz nicht leer) — nicht gegenüber
      dem unmittelbaren Vorgänger. Ein bloßer Wechsel des jeweils stärksten Motivs bei gleicher
      getragener Menge genügt nicht, und es wird kein Gesamtabstand über alle Motivstärken gebildet.
- [ ] Der Wechsel muss anhalten: Getrennt wird erst, wenn `MOTIF_CHANGE_CONFIRMING_PHOTOS`
      aufeinanderfolgende mitredende Fotos ihn zeigen, das erste abweichende eingeschlossen.
      Bestätigt ist er, wenn jedes weitere Foto des Fensters mindestens eines der Motive weiterhin
      geändert zeigt, die das erste abweichende Foto geändert hat — das identische Motivbild wird
      nicht verlangt. Zeigt ein Foto keines davon, zerfällt das Fenster: es beginnt an diesem Foto
      neu, wenn es selbst abweicht, und entfällt, wenn es zum Bezug zurückkehrt. Ein einzelnes
      abweichendes Foto innerhalb eines laufenden Events trennt nie.
- [ ] Ist der Wechsel bestätigt, beginnt das neue Event rückwirkend bei dem **ersten** Foto, das das
      neue Motivbild zeigt — nicht bei dem Foto, das den Wechsel bestätigt.
- [ ] Der Beispielfall ist prüfbar erfüllt: Ruinenbesuch und anschließendes Mittagessen um die Ecke
      ergeben zwei Events statt einem, obwohl weder Zeitlücke noch Ortssprung greifen. Das erste
      Essensfoto gehört zum zweiten Event. Der Fall ist so gebaut, dass **kein** anderes Signal ihn
      erklären könnte: Zeitabstand unter der Zeitlücke, Distanz unter Schritt- und
      Ausdehnungsschwelle, derselbe Kalendertag, kein Sehenswürdigkeitsname. Ohne die neue Regel
      ergibt er genau ein Event.
- [ ] Fällt eine Motivgrenze auf einen Index, an dem ohnehin schon getrennt wird, ändert sie nichts
      an Anzahl, Mitgliedschaft und Positionen der Events.
- [ ] Ein Event aus einem einzigen Foto ist zulässig: Eröffnet ein atypisches Foto einen Abschnitt
      und folgt ihm ein anhaltend anderes Motivbild, beginnt das neue Event unmittelbar dahinter.

**Welche Fotos mitreden**

- [ ] Ein Foto **ohne Motiv-Kopfzeile** (keine wirksamen Stärken) wird für dieses Signal übergangen:
      Es löst keine Grenze aus, lässt ein laufendes Bestätigungsfenster nicht zerfallen und zählt in
      keinem mit — bleibt aber Mitglied seines Events. Ein Foto **mit** Kopfzeile, bei dem keine
      Stärke die Präsenzgrenze erreicht, ist davon verschieden: Es hat ein Motivbild, nämlich das
      leere, redet voll mit, und der Wegfall aller getragenen Motive ist ein Wechsel wie jeder andere.
- [ ] Motive aus der schwächeren lokalen Erkennung dürfen mittrennen; eine Cloud-Klassifizierung
      wird nicht vorausgesetzt.
- [ ] Ein als Dokument oder Screenshot ausgeschlossenes Foto löst nie eine Grenze aus.
- [ ] Hat ein Nutzer ein Motiv als zutreffend oder nicht zutreffend korrigiert, wirkt diese Korrektur
      auf die Gliederung genauso wie die Einschätzung des Modells — eine Gliederung, die allein aus
      den Modellstärken nicht entstünde, entsteht mit der Korrektur. Sichtbar wird das beim nächsten
      Lauf: Der Korrektur-Endpunkt selbst lässt Events und Rangzeilen des bestehenden Laufs
      unverändert.

**Verhältnis zu den bestehenden Trennsignalen**

- [ ] Der Motivwechsel tritt neben die bestehenden Signale (Zeitlücke, Kalendertagsgrenze,
      Ortssprung, räumliche Ausdehnung, Wechsel der Sehenswürdigkeit) und hebt keines davon auf.
      Ein erzwungener Start wirkt wie jede andere Grenze und setzt alle Signale zurück — eine erst
      später fällige Grenze von Ausdehnung, Schritt oder Name kann dadurch entfallen, weil an der
      früheren Stelle bereits getrennt wurde.
- [ ] Trägt kein Foto eines Projekts Motive — weder Kopfzeilen noch getragene Motive —, ist das
      Ergebnis identisch zu dem derselben Kandidaten ohne Motivangaben: gleiche Anzahl, gleiche
      Mitgliedschaft, gleiche Positionen.
- [ ] Die zugesagten Eigenschaften eines Events gelten unverändert weiter: chronologisch geordnet,
      überschneidungsfrei, jedes Kandidatenfoto in genau einem Event, lückenlose Position, und kein
      Event reicht über eine Kalendertagsgrenze.

**Einstellbarkeit**

- [ ] Wie stark ein Motiv sein muss, um als tragend zu gelten, und wie viele Fotos einen Wechsel
      bestätigen müssen, sind bewusst nicht kalibrierte und änderbare Festlegungen — wie die
      bestehende Grenze für die räumliche Ausdehnung. Kein Test pinnt einen der beiden Zahlwerte;
      der Prüfsatz bleibt bei jeder Fensterlänge ab 2 vollständig grün. Ein Wert von 1 widerspräche
      „ein einzelnes abweichendes Foto trennt nie" und ist keine zulässige Einstellung.

## Datenmodell-Bezug

Keine neue Entität, keine neue Spalte, keine Migration. Gelesen werden die bestehenden wirksamen
Motivstärken und `PhotoMotifAssessment.excluded_document`; geschrieben wird ausschließlich, was die
Event-Bildung ohnehin schreibt.

## Architektur / Umsetzung

**Gewählter Ansatz (ADR [`0109`](../decisions/0109-motivwechsel-trennt-in-einem-vorgelagerten-durchlauf.md)):
zwei Stufen statt eines sechsten Trennsignals.** Die Motivgrenzen werden in einem eigenen, reinen
Durchlauf **vor** der Signalkette bestimmt; die Kette selbst und ihre fünf Signale bleiben
unverändert. Ein so bestimmter Index wirkt im Durchlauf wie eine gemeldete Grenze: `begin` läuft auf
allen Signalen und ist deren vollständige Rücksetzung. Rückwirkung und Bestätigungsfenster brauchen
deshalb keinen Rückwärtsweg im Protokoll — an der rückwirkenden Stelle ist noch nichts
fortgeschrieben.

### Betroffene Dateien

| Datei | Änderung |
|---|---|
| `backend/src/photosort/events.py` | `EventCandidate` +2 Felder, `MOTIF_CHANGE_CONFIRMING_PHOTOS`, `_motif_picture`, `motif_change_starts`, ein Zweig in `build_events` |
| `backend/src/photosort/worker.py` | `_build_grouping_and_rankings` befüllt die beiden neuen Felder |
| `backend/tests/test_events.py` | Regel- und Zusammenspiel-Fälle, Kandidatenhelfer erweitert |
| `backend/tests/test_worker_criterion_scoring.py` | Verdrahtung: wirksame Stärken und Ausschluss kommen wirklich an |
| `docs/architecture.md` | Block „Gebildet wird in EINEM sortierten Durchlauf" |

### Die neue Regel in `events.py`

`EventCandidate` bekommt zwei Felder mit Vorgabewerten — ohne Motivangabe ist die Gliederung die
bisherige:

```python
motif_strengths: Mapping[str, float] | None = None   # WIRKSAME Staerken; None = keine Kopfzeile
excluded_document: bool = False
```

Das **Motivbild** eines Fotos ist `selection.carried_motifs(motif_strengths)` — dieselbe Herleitung
wie im Auswahlvorschlag und hinter `MotifStrengthOut.present`, **keine eigene Grenze**.
`selection.py` trägt die Auflage, dass jeder weitere Leser das Prädikat teilt statt die Konstante
nachzubauen; eine zweite Schwelle in `events.py` wäre ein zweiter Begriff von „dieses Foto zeigt X".
`None` (keine Kopfzeile) und `excluded_document` heißen „redet nicht mit"; ein leeres Motivbild ist
davon verschieden und redet voll mit.

Neu ist damit genau **eine** Konstante, die Fensterlänge:

```python
# Wie viele aufeinanderfolgende mitredende Fotos einen Motivwechsel bestaetigen muessen, das erste
# abweichende eingeschlossen. Dokumentierte, UNKALIBRIERTE Modulkonstante im Muster von
# EVENT_EXTENT_MAX_METERS - aenderbar, durch keinen Test auf den Zahlwert gepinnt.
# Ein Wert von 1 widerspraeche der Zusage "ein einzelnes abweichendes Foto trennt nie".
MOTIF_CHANGE_CONFIRMING_PHOTOS = 3
```

`motif_change_starts(ordered: Sequence[EventCandidate]) -> frozenset[int]` liefert die Indizes der
bereits sortierten Folge, an denen ein bestätigter Motivwechsel ein neues Event erzwingt. Die
tragenden Festlegungen:

- **Wechsel = symmetrische Differenz** zum Motivbild des Fotos, das den laufenden Motivabschnitt
  eröffnet hat. Kein Wechsel des stärksten Motivs, kein Gesamtabstand über die Stärken.
- **Der Bezug wird nicht je Foto nachgezogen** (wie der Name bei `LandmarkChangeSignal`, nicht wie
  die Koordinate bei `StepDistanceSignal`): gegen den Vorgänger gemessen liefe ein langsames
  Abdriften unbegrenzt weiter.
- **Bestätigung ist nicht das identische Motivbild**, sondern dass mindestens eines der beim ersten
  abweichenden Foto geänderten Motive weiterhin geändert ist. Ein zweites Essensfoto mit Personen im
  Bild darf die Bestätigung nicht abreißen lassen.
- **Rückwirkung** ist der Index des **ersten** Fotos des Fensters, nicht des bestätigenden. Ein
  solcher Index ist nie `0`, weil er einen bereits gesetzten Bezug voraussetzt; ein leeres führendes
  Event kann nicht entstehen.
- Der Durchlauf kennt die übrigen Signale nicht. Fällt eine Motivgrenze auf eine Stelle, an der
  ohnehin schon getrennt wird, ändert sie nichts.

In `build_events` bleibt die Auswertung aller Signale **vor** der Verzweigung und in einer eigenen
Anweisung:

```python
    ordered = sorted(candidates, key=lambda candidate: (candidate.taken_at, candidate.photo_id))
    forced_starts = motif_change_starts(ordered)
    ...
    for index, candidate in enumerate(ordered):
        boundary = any([signal.is_boundary(candidate) for signal in active])   # UNVERAENDERT zuerst
        if boundary or index in forced_starts or not events:
```

Stünde `index in forced_starts` im selben `or` links davon, würde an einem erzwungenen Start kein
Signal mehr gefragt, und dessen Fortschreibung hinge wieder an der Auswertungsreihenfolge. Signatur
und `default_signals()` bleiben unverändert; die Liste behält ihre fünf Einträge.

### Die Verdrahtung in `worker.py`

In `_build_grouping_and_rankings`, vor dem `build_events`-Aufruf, im Muster von
`_apply_run_selection`:

- `await load_effective_strengths(session, values_by_photo_id.keys())` — die **wirksamen** Stärken,
  nie die rohe Stärkezeile. Damit wirkt eine Nutzerkorrektur genau wie die Modellaussage, ohne eine
  zweite Fassung des `CASE`.
- eine Abfrage auf `PhotoMotifAssessment.photo_id` mit `excluded_document.is_(True)`, eingeschränkt
  auf die Kandidaten.
- Ein Foto, das in `load_effective_strengths` fehlt, hat keine Kopfzeile → `motif_strengths=None`.
  Ein kleiner privater Helfer wandelt `dict[str, EffectiveStrength] | None` nach `dict[str, float] |
  None`, damit die Umwandlung nicht im Generator der Kandidaten steht.

Der zweite Aufrufer (`rebuild_run_grouping`) ist damit automatisch mit abgedeckt. Preis: zwei
Abfragen mehr je Lauf, dieselbe bewusst hingenommene Klasse wie bisher an dieser Funktion.

### Umsetzungsreihenfolge (testgetrieben)

1. **`events.py`, die reine Regel.** Zuerst die beiden Felder an `EventCandidate` und
   `motif_change_starts` mit `MOTIF_CHANGE_CONFIRMING_PHOTOS`. Die Fensterlänge wird in den Tests
   **über das Symbol** aufgebaut, nie über den Zahlwert.
2. **Einbau in `build_events`.** Der Beispielfall der Story als Fall mit `default_signals()`.
3. **`worker.py`.** Ein Lauf-Fall, dessen Gliederung sich nur durch den Motivwechsel ändert, plus je
   ein Fall für „Korrektur wirkt wie das Modell" und „ausgeschlossenes Dokument löst keine Grenze
   aus".
4. **`docs/architecture.md`.** Der Block sagt heute, ein weiteres Signal sei „eine Klasse und ein
   Listeneintrag". Er bekommt die zweite Stufe und behält die Aussage, dass die Liste der
   Erweiterungspunkt für **paarweise** Signale bleibt.

### Was sich ausdrücklich nicht ändert

- Keine Tabelle, keine Spalte, keine Migration, kein Feld in der Antwort.
- Die Motivkorrektur-Endpunkte (`api/photos.py`) stoßen **keine** Neugliederung an; das ist die
  Umsetzung von „sichtbar beim nächsten Lauf".
- `default_signals()` behält seine fünf Einträge; kein Signal ändert sein Verhalten.
- Phase A (`scoring.py::assign_clusters`, `PhotoScore.cluster_key`) bleibt unberührt.
- `demo_state.py` schreibt seine `events`-Zeilen direkt und läuft nicht über `build_events`.

## UI/UX

Nicht relevant — keine sichtbare Oberfläche. `EventOut` bleibt unverändert, und weder die
Album-Ansicht noch die Endauswahl unterscheiden, durch welches Signal ein Event entstanden ist. Die
Gliederung ändert sich, ihre Darstellung nicht.

## Teststrategie

**Ebenen.** Schwerpunkt Unit (`test_events.py`, DB-frei): die Regel wird an `motif_change_starts`
selbst geprüft, nicht nur durch `build_events` hindurch — sie ist eine Segmentierung über die ganze
Folge und ihr Ergebnis (eine Indexmenge) ist direkt beobachtbar. Die Integrationsebene
(`test_worker_criterion_scoring.py`) prüft ausschließlich die Verdrahtung. **Kein E2E-Fall und kein
Frontend-Fall:** API, `EventOut` und Oberfläche ändern sich nicht, der `e2e`-Job fährt keinen
Worker, und `demo_state.py` schreibt seine `events`-Zeilen direkt — ein Fall dort erreichte
`build_events` gar nicht.

### Beide Stellschrauben werden nie am Zahlwert geprüft

Die Fälle bauen ihre Länge aus dem **Symbol**: ein Folgenbauer erzeugt aus einer Liste von
Motivbildern Kandidaten mit fortlaufender `photo_id`, kleinem Zeitabstand und ohne Ort, sodass kein
anderes Signal mitspricht, gleich wie lang die Folge wird. Ein Fenster heißt
`MOTIF_CHANGE_CONFIRMING_PHOTOS`, ein zu kurzes `MOTIF_CHANGE_CONFIRMING_PHOTOS - 1`.

Erzwungen wird das durch eine `autouse`-Fixture, die die Modulkonstante über
`params=sorted({2, 5, MOTIF_CHANGE_CONFIRMING_PHOTOS})` per `monkeypatch.setattr` setzt: die
Regelfälle laufen unter jeder dieser Fensterlängen. Das Testmodul liest die Konstante deshalb als
**Modulattribut** (`events.MOTIF_CHANGE_CONFIRMING_PHOTOS`); ein `from ... import` bände den Wert
beim Import und die Fälle wären unter der Fixture falsch dimensioniert. Wird die Konstante geändert,
muss der gesamte Prüfsatz unverändert grün bleiben — ein Fall, der dabei rot wird, spiegelt den Code
und wird umgeschrieben, nicht in seiner Erwartung nachgezogen.

Genau **eine** Aussage über den Zahlwert steht, und sie ist eine Ungleichung:
`MOTIF_CHANGE_CONFIRMING_PHOTOS >= 2`, plus ihr verhaltensnaher Zwilling „ein einzelnes abweichendes
Foto trennt nie". Beide werden bei `1` rot, und das ist die zugesagte Wirkung.

Die Motivgrenze wird gar nicht erst nachgebaut: Der bestehende Wächter in `test_selection.py`
verlangt, dass `MOTIF_PRESENCE_THRESHOLD` unter `src/photosort/` **nur** in `selection.py` vorkommt;
`events.py` tritt der Liste `_SELECTING_MODULES` desselben Wächters bei, weil es ab jetzt eine
Auswahlgrenze liest. Gegen eine *eingetippte* zweite Schwelle hilft nur Verhalten: ein Fall mit einer
Stärke **exakt auf** der Präsenzgrenze (Motiv wird getragen) und einer knapp darunter (nicht
getragen) — ein re-implementiertes `>` ist hier rot.

### Die Fälle der reinen Regel

- Wechsel ist die **symmetrische Differenz**: ein neu getragenes Motiv trennt, ein weggefallenes
  trennt; ein bloßer Wechsel des *stärksten* Motivs bei gleicher getragener Menge trennt nicht, und
  eine Stärkeänderung unterhalb der Grenze trennt nicht.
- Der Bezug ist das **eröffnende** Foto des Abschnitts: eine Folge, die sich Foto für Foto um je ein
  Motiv weiterschiebt, trennt — gegen den Vorgänger gemessen träte keine Grenze ein.
- **Rückwirkung**: der gelieferte Index ist der des ersten Fotos des Fensters, nicht des
  bestätigenden. Geprüft wird der Index, nicht nur die Event-Anzahl.
- **Bestätigung ohne Bildgleichheit**: ein Foto des Fensters trägt zusätzlich ein weiteres Motiv und
  reißt die Bestätigung nicht ab.
- **Zerfall**: `MOTIF_CHANGE_CONFIRMING_PHOTOS - 1` abweichende Fotos, dann eine Rückkehr zum Bezug →
  keine Grenze; direkt danach ein volles Fenster → Grenze am ersten Foto des **zweiten** Fensters.
- `0` ist nie in der Ergebnismenge, und jeder Index liegt in `range(len(ordered))`.
- Ein einzelnes atypisches Foto am Abschnittsanfang, dem ein anhaltend anderes Motivbild folgt, ergibt
  ein Event aus genau diesem einen Foto. Das ist zugesagt, nicht versehentlich, und steht als eigener
  Fall — sonst meldet es der nächste Leser als Fehler.
- Der Beispielfall der Story mit `default_signals()`. Ohne die neue Regel ist das **ein** Event — das
  ist der Rot-Anker; das erste Essensfoto steht im zweiten Event.

### „Keine Kopfzeile" gegen „leeres Motivbild"

Die beiden Zustände werden als **Zwillingspaar** geprüft: identisch gebaute Folgen, die sich nur in
`motif_strengths=None` gegen `motif_strengths={...}` (Kopfzeile da, keine Stärke erreicht die Grenze)
unterscheiden, mit **entgegengesetzter** Erwartung — `None` ergibt ein Event, das leere Motivbild
zwei. Ein einzelner Fall bewiese hier nichts: Fallen die Zustände zusammen, ist genau einer der beiden
rot, gleich in welche Richtung sie zusammenfallen. Dazu je ein Fall für die drei Folgen von
„übergangen": ein unklassifiziertes Foto löst keine Grenze aus, lässt ein laufendes Fenster nicht
zerfallen und zählt in keinem mit — und bleibt trotzdem Mitglied seines Events. Dasselbe Zwillings-
und Dreierpaar noch einmal für `excluded_document=True`.

### Zusammenspiel mit den fünf Signalen

- **Ein erzwungener Start ruft `begin` auf allen Signalen** — die tragende Annahme von ADR 0109. Der
  Nachweis läuft über das bestehende **Spion-Signal**: an einem erzwungenen Start wurde es gefragt
  (`is_boundary`) und danach `begin`, nicht `advance`, aufgerufen. Kehrseite, die derselbe Fall
  festhält: Der Start setzt Ausdehnung, Schrittbezug und Namensbezug zurück, und eine erst später
  fällige Grenze dieser Signale kann dadurch entfallen. Ein Superset-Vergleich der Grenzindizes mit
  dem motivfreien Lauf wäre deshalb falsch und steht nicht.
- **Kalendertag**: ein bestätigtes Fenster, dessen rückwirkender Beginn auf dem Vortag liegt, während
  das bestätigende Foto nach Mitternacht aufgenommen ist — beide Grenzen entstehen, kein Event reicht
  über die Tagesgrenze. Der Fall braucht `default_signals()`, weil der Invariantenhelfer `_build` mit
  injizierten Signallisten ohne `DayBoundarySignal` läuft.
- **Koinzidenz**: fällt die Motivgrenze auf einen Index, an dem ohnehin getrennt wird, sind Anzahl,
  Mitgliedschaft und Positionen identisch zum motivfreien Lauf.
- **Ohne jede Motivangabe** ist das Ergebnis identisch zu dem derselben Kandidaten heute — geprüft
  über Anzahl, Mitgliedschaft und Positionen, nicht nur über die Anzahl.

Der bestehende Helfer `_build` trägt unverändert und prüft je Fall lückenlose Positionen,
Überschneidungsfreiheit, kein leeres Event und „jeder Kandidat in genau einem Event" mit; die
Motivfälle laufen über ihn. Erweitert werden müssen die Kandidatenhelfer: sie kennen bisher keine
Motivfelder.

### Erschöpfende Aufzählung statt Property-Testing

Kein `hypothesis` (ADR-pflichtige neue Abhängigkeit). An seine Stelle tritt eine **vollständige
Aufzählung über einem winzigen Alphabet**: alle Folgen der Länge `MOTIF_CHANGE_CONFIRMING_PHOTOS + 2`
über den vier Motivbildern `None`, `{}`, `{A}`, `{A, B}` — beim aktuellen Wert 1024 Läufe, jeder
linear und DB-frei. Geprüft wird je Folge der Invariantensatz plus die Indexzusagen von
`motif_change_starts`. Das deckt die Formen ab, die eine handverlesene Fallmenge nicht aufzählt (leeres
führendes Event, Index 0, ein Foto in zwei Events), ohne eine Abhängigkeit und ohne Zufall.

### Integration: die Verdrahtung (`test_worker_criterion_scoring.py`)

Vier Fälle, jeder mit dem Ergebnis an den geschriebenen `Event`-/`PhotoRanking`-Zeilen gemessen:

1. **Ein Lauf, dessen Gliederung sich nur durch den Motivwechsel ändert.**
2. **Die lokale Grundlage trennt mit** — ein Lauf ganz ohne Cloud-Phase, dessen Motivbilder aus dem
   echten `local_motif_strengths` über einen eingespielten Szenen-Klassifizierer entstehen.
3. **Eine Korrektur wirkt wie die Modellaussage**: die Modellstärken allein ergäben ein Event, erst
   die Korrekturzeilen erzeugen die Grenze. Rot-Anker gegen ein Lesen der rohen Stärkezeile statt
   `load_effective_strengths`. Dazu die Gegenrichtung: der Korrektur-Endpunkt selbst gliedert nichts
   neu — `Event`- und `PhotoRanking`-Zeilen des bestehenden Laufs bleiben nach dem Aufruf unverändert.
4. **Ein ausgeschlossenes Dokument löst keine Grenze aus**, obwohl sein Motivbild abweicht.

Der Zwilling **„keine Kopfzeile" gegen „leeres Motivbild" gehört auch hierher**, denn der Fehler
entsteht an der Aufrufstelle, nicht in der reinen Funktion: Ein `.get(photo_id, {})` — die
naheliegende Übernahme aus `_apply_run_selection`, wo genau das richtig ist — lässt beide Zustände
zusammenfallen, und keine Prüfung des privaten Umwandlungshelfers allein sieht das. Im vollen
Kriterien-Lauf ist die Kopfzeilen-Abwesenheit nicht herstellbar (die lokale Phase schreibt für jeden
Kandidaten eine); der Fall gehört deshalb an `rebuild_run_grouping` mit einem Kandidaten ohne
Motiv-Kopfzeile und deckt damit zugleich den zweiten Aufrufer ab.

### Was bewusst nicht geprüft wird

- **Keine Kalibrierung.** Kein Fall behauptet, dass 3 Fotos oder die Präsenzgrenze die *richtigen*
  Werte sind; es gibt keinen Fotokorpus, gegen den das zu belegen wäre.
- **Keine neue Projektbindungs-Prüfung** für die beiden neuen Abfragen: ihre Id-Menge ist die
  Kandidatenmenge des Laufs und damit bereits projektgebunden. Anders als bei `infer_locations`,
  dessen Bezugsmenge das ganze Projekt ist, entsteht hier keine neue Bindung, die auseinanderlaufen
  könnte.
- **Keine Wiederholung der Motivvektor-Vollständigkeit.** Dass „kein erkennbares Motiv" acht Werte
  unter der Grenze sind und nicht eine fehlende Zeile, hält `test_motifs.py`; die Unterscheidung
  oben ruht darauf.

### Testkonzept

`specs/architecture/0002-testkonzept.md` bekommt im selben Pull Request eine neue Sektion hinter der
bestehenden zu `events.py`/ADR 0087, mit vier über diesen Branch hinaus geltenden Festlegungen: die
`autouse`-Fixture, die die Nicht-Pinnung einer Stellschraube selbst prüft (samt der still brechenden
Voraussetzung, die Konstante als Modulattribut zu lesen); das Zwillingspaar als einzige Form, in der
zwei ununterscheidbare Abwesenheiten geprüft werden können; die erschöpfende Aufzählung als
abhängigkeitsfreier Ersatz für Property-Testing samt ihrer Zulässigkeitsbedingung; und dass bei einem
Durchlauf mit vorgelagerter Stufe die reine Funktion direkt und die Verzahnung am Spion-Signal
geprüft wird, während ein Superset-Vergleich der Grenzindizes die falsche Zusage wäre.

## Security

Sicherheitsrelevant, kein Blocker: Kein Secret, kein Endpunkt, keine Migration, kein neues
Antwortfeld, keine neue Eingabe von außen, keine Änderung an Auth oder an der Sichtbarkeit
zwischen den beiden Nutzern. Neu ist **ein zweiter Leser** der Motivstärken — dieselbe Modellzahl
bestimmt ab hier mit, wo ein Event beginnt. Die Fortschreibung steht im Sicherheitskonzept
(`specs/architecture/0003-securitykonzept.md`, Abschnitt „Die Motivzahl des Modells bewegt
erstmals eine Event-Grenze").

**S1 — Das Vergleichsverbot zwischen Motiven gilt in `events.py` unverändert.** Entschieden wird
über die symmetrische Differenz zweier Motivmengen, gebildet je Motiv einzeln gegen dieselbe eine
Grenze über `selection.py::carried_motifs`. Untersagt bleiben: der Wechsel des *stärksten*
Motivs, ein Gesamtabstand über die acht Zahlen, jede Vorrangreihenfolge — und eine eigene Grenze
in `events.py`, also ein zweiter Begriff von „dieses Foto zeigt X". Bei Verletzung verliert die
bezifferte Obergrenze der Prompt-Injection-Eindämmung ihre Grundlage: Ein präpariertes Bild (Foto
eines Textes, eines Bildschirms, eines Schildes) könnte dann über eine Rangfolge zwischen Motiven
die Gliederung des Projekts steuern statt nur eine einzelne Stärke zu heben.

**S2 — Die Kontrollflusswirkung bleibt beziffert.** Ein bestätigter Wechsel erzeugt eine
Event-**Grenze**; die Zahl der Events bleibt durch die Zahl der Kandidatenfotos begrenzt, jedes
Signal trennt nur und führt nichts zusammen. Es wird kein Fremdtext persistiert, geloggt oder
ausgeliefert: Der Motivschlüsselraum ist mit acht Einträgen geschlossen, die Stärke verlässt das
Backend weiterhin nur als Ja/Nein. Die Logauflage im Kopf von `events.py` gilt unverändert; das
neue Trennsignal loggt nichts.

**S3 — `excluded_document` bekommt seinen zweiten Hebel, und die Richtung ist Muss.** Der einzige
Fremdwert mit fotoweitem Hebel und ohne Handkorrekturpfad nimmt eine Aufnahme ab hier zusätzlich
aus dem Trennsignal. Übergangen heißt „redet nicht mit", nie „fällt aus seinem Event" — sonst
verschwänden fälschlich ausgeschlossene Aufnahmen aus einer Gliederung, in der sie bloß nichts
lenken sollen. Die Zusage „jedes Kandidatenfoto in genau einem Event" bleibt der Prüfstein.

**S4 — Die Projektgrenze trägt die Kandidatenmenge, nicht die einzelne Abfrage.**
`load_effective_strengths` und die Ausschluss-Abfrage bleiben auf `values_by_photo_id.keys()`
eingeschränkt und werden je Kandidat über `photo_id` nachgeschlagen; sie dürfen die Menge, die
`build_events` und damit `motif_change_starts` sieht, **nie erweitern**. Das ist ausdrücklich
nicht der Fall von `infer_locations`: Dort ist die Bezugsmenge bewusst breiter als die Kandidaten
und trägt deshalb ihre eigene ausgeschriebene `Photo.project_id`-Bindung. Eine „analog
verbreiterte" Motivabfrage brächte hier keinen Nutzen, sondern nur einen Weg, auf dem ein
projektfremdes Foto in die geordnete Folge gelangt und Grenzen in einem Projekt an Fotos eines
anderen hängen.

**Produkteigenschaft, die benannt gehört (keine Auflage):** Die Motivkorrektur ist eine Aussage
über das FOTO und wird von beiden Nutzern geteilt (`user_id` ist Auditfeld, der Unique-Constraint
lautet `(photo_id, motif_key)`). Dass die Korrektur des einen ab jetzt auch die Gliederung
verschiebt, die der andere sieht, ist die Ausweitung einer bereits gemeinsamen Wirkung — keine
neue Vertrauensgrenze und innerhalb von „kein Innentäter-Modell zwischen den beiden Nutzern".

**Ausdrücklich geprüft und ohne Befund:** Die Gliederung steuert nicht, welche Bilddaten den
Homeserver verlassen — die vier cloud-bestimmenden Abfragen wählen je Foto und kennen kein Event;
eine Motivkorrektur bekommt damit keinen Kosten- oder Abflusshebel. Eine entartete Stärke aus der
`double precision`-Spalte fällt am inklusiven `>=` von `motif_is_present` auf „nicht getragen" und
erzeugt hier keine `500`; die Abwehr dieser Defektklasse bleibt am Parser. Keine neue
Abhängigkeit, kein neues Modell-Asset, kein SSRF-Pfad, kein neuer XSS-Sink.

## Entscheidungen

- Der Motivwechsel wird **nicht** ein sechster Eintrag in `default_signals()`, sondern ein
  vorgelagerter reiner Durchlauf (ADR 0109). Bestätigungsfenster und rückwirkender Beginn sind im
  vorwärts entscheidenden `BoundarySignal`-Protokoll nicht ausdrückbar.
- Die Grenze „ab wann gilt ein Motiv als tragend" wird **nicht** neu eingeführt, sondern von
  `selection.py` mitbenutzt. Folge, die nicht unter den Tisch fällt: Eine Änderung an
  `MOTIF_PRESENCE_THRESHOLD` verschiebt ab jetzt auch, wo Events beginnen — nicht mehr nur, welche
  Fotos der Auswahlvorschlag als Motivträger sieht.
- ADR 0087 Abschnitt 3 letzter Satz („Das Motivwechsel-Signal ist danach eine Klasse und ein
  Listeneintrag") ist durch ADR 0109 abgelöst; der übrige Entscheidungstext gilt unverändert.
- Ein motivgetrenntes Event darf aus einem einzigen Foto bestehen. Weil die Auswahl-Richtwerte je
  Event vergeben werden, bekommt ein solcher Ausreißer damit ein eigenes Kontingent — die Mechanik,
  die diese Spec repariert, wirkt in diesem Randfall gegen sich selbst. Bewusst zugelassen statt
  über eine Mindestgröße abgefangen; eine Mindestgröße wäre eine eigene Spec-Änderung.
- `events.py` liest ab jetzt eine Auswahlgrenze und tritt deshalb dem Struktur-Wächter
  `_SELECTING_MODULES` in `test_selection.py` bei. Ohne das deckt der Anzeigeband-Wächter
  ausgerechnet die neu hinzugekommene lesende Datei nicht ab.

## Offene Fragen

Keine.

## Out of Scope

- Eine Kalibrierung der Fensterlänge oder der Motivgrenze an echten Daten.
- Eine nachträgliche Neugliederung eines bereits gebildeten Laufs nach einer Motivkorrektur.
- Jede Änderung an Phase A, am Datenmodell, an der API und am Frontend.
