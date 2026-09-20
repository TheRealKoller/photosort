# 0109 - Der Motivwechsel trennt in einem vorgelagerten Durchlauf, nicht als Eintrag der Signalliste

**Status:** Accepted
**Teilweise abgelöst:** Punkt 1, die **Wirkung** des erzwungenen Starts — ein Index aus
`motif_change_starts` eröffnet kein Event mehr und setzt kein Signal zurück, er vermerkt
`motivwechsel` nur noch an einer Grenze, die der Durchlauf ohnehin zieht — durch ADR
[`0119`](./0119-der-motivwechsel-vermerkt-eine-grenze-statt-eine-zu-eroeffnen.md). Der Titel dieser
ADR beschreibt damit die **Berechnung**, nicht mehr die Wirkung. Unverändert gelten die zweistufige
Anlage samt der Begründung, warum der Motivwechsel kein Eintrag der Signalliste ist (Punkt 1, erster
und dritter Absatz), der Wechselbegriff (Punkt 2), Bestätigungsfenster und rückwirkende Lage
(Punkt 3), wer mitredet (Punkt 4) und die geteilte Grenze (Punkt 5). Von den Konsequenzen fallen
zwei: dass `MOTIF_PRESENCE_THRESHOLD` zweierlei verschiebt, und dass ein motivgetrenntes Einzelbild
allein bestehen kann.
**Datum:** 2026-09-14
**Bezug:** Spec [`features/0477-motivwechsel-trennsignal.md`](../features/0477-motivwechsel-trennsignal.md),
ADR [`0087`](./0087-event-als-persistierte-einheit-und-trennsignale-als-liste.md) (das Protokoll der
Trennsignale; Abschnitt 3 letzter Satz wird hier abgelöst), ADR
[`0091`](./0091-motive-mit-staerke-statt-hauptkategorie.md) (Punkt 8: die Anzeigebänder sind keine
Zugehörigkeitsschwelle), ADR [`0097`](./0097-auswahl-mit-richtwert-kontingente-je-event-und-motivgefuehrte-vergabe.md)
(`MOTIF_PRESENCE_THRESHOLD`, hier mitbenutzt)

**Umfang:** über dem Richtwert von rund 100 Zeilen, weil die Entscheidung fünf Punkte trägt und der
Wechselbegriff ohne seine drei Randfälle (leeres Motivbild, fehlende Kopfzeile, ausgeschlossenes
Foto) nicht eindeutig anwendbar ist.

## Kontext

`BoundarySignal` entscheidet **rein vorwärts**: `is_boundary(candidate)` antwortet sofort und
endgültig, und `build_events` hängt den Kandidaten unmittelbar an das laufende oder an ein neu
eröffnetes Event. Der Motivwechsel braucht beides nicht: Die Grenze steht erst fest, nachdem
mehrere weitere Fotos gesehen wurden, und sie gehört dann an eine **frühere** Stelle, an der
bereits entschieden und angehängt wurde.

## Entscheidung

### 1. Zwei Stufen: erst die Motivgrenzen, dann die unveränderte Signalkette

`build_events` sortiert wie bisher, ruft dann die **reine** Funktion
`events.py::motif_change_starts(ordered) -> frozenset[int]` — die Indizes, an denen ein bestätigter
Motivwechsel ein neues Event erzwingt — und durchläuft die Kandidaten danach wie zuvor. Ein
erzwungener Index wirkt im Durchlauf genau wie eine gemeldete Grenze: `begin` läuft auf **allen**
Signalen, und das ist bauartbedingt ihre vollständige Rücksetzung (jedes `begin` überschreibt den
gesamten Zustand seines Signals). Die Rückwirkung verschwindet damit, weil sie **vor** der
Zustandsfortschreibung stattfindet — zurückzudrehen ist nichts.

Weiterhin gilt und wird weiterhin geprüft: Jedes Signal wird zu **jedem** Kandidaten gefragt, auch
an einem erzwungenen Start, und bekommt je Kandidat genau **eine** schreibende Methode. Die
Signatur von `build_events` und die Liste `default_signals()` bleiben unverändert; ohne
Motivangaben am Kandidaten liefert die erste Stufe die leere Menge und der Durchlauf ist der alte.

**Nicht gewählt: der Umbau des Protokolls auf verzögerte Grenzen.** Er zwänge jedem Signal einen
Rückwärtsweg auf — die vier übrigen haben ihren Zustand an der rückwirkenden Stelle längst
fortgeschrieben —, und die Reinheit von `is_boundary` samt der nicht kurzgeschlossenen Auswertung,
also genau die Zusage, die die Auswertungsreihenfolge aus dem Ergebnis heraushält, wäre für ein
einziges Signal aufgegeben. Der Preis der gewählten Lösung ist, dass der Motivwechsel **kein**
Listeneintrag ist: Er ist keine paarweise Frage, sondern eine Segmentierung über die ganze Folge,
und die Liste kann das nicht ausdrücken, ohne ihre Zusagen zu verlieren.

### 2. Das Motivbild und sein Wechsel

Das **Motivbild** eines Fotos ist die Menge der Motive, die es trägt (Punkt 5). Ein Wechsel ist die
**symmetrische Differenz** zum Motivbild des Fotos, das den laufenden Motivabschnitt eröffnet hat:
ein Motiv wird neu getragen, oder ein bisher getragenes fällt weg. Ausdrücklich **nicht**: der
Wechsel des stärksten Motivs (er benennt eine Rangfolge, die das Motivset nicht kennt) und kein
Gesamtabstand über die acht Stärken (er verrechnete acht Aussagen zu einer Zahl, die keine mehr
ist).

Der Bezug ist das **eröffnende** Foto des Abschnitts und wird nicht je Foto nachgezogen — dieselbe
Lehre wie bei der Ausdehnung (ADR 0087 Punkt 5): Gegen den jeweiligen Vorgänger gemessen, liefe ein
langsames Abdriften unbegrenzt weiter, ohne je zu trennen.

### 3. Bestätigungsfenster und Rückwirkung

`MOTIF_CHANGE_CONFIRMING_PHOTOS = 3`, dokumentierte, **unkalibrierte** Modulkonstante in `events.py`
im Muster von `EVENT_EXTENT_MAX_METERS`: so viele aufeinanderfolgende mitredende Fotos, das erste
abweichende eingeschlossen, müssen den Wechsel zeigen. Ein Wert von `1` widerspräche der Zusage „ein
einzelnes abweichendes Foto trennt nie" und ist keine zulässige Einstellung.

Bestätigt ist der Wechsel, wenn jedes weitere Foto des Fensters **mindestens eines** der Motive
weiterhin geändert zeigt, die das erste abweichende Foto geändert hat. Zeigt ein Foto keines davon,
zerfällt das Fenster: Es beginnt an diesem Foto neu, wenn es selbst abweicht, und entfällt, wenn es
zum Bezug zurückkehrt. Verlangt wird bewusst nicht das *identische* Motivbild — eine Aufnahme
desselben Mittagessens mit Personen im Bild ist dieselbe Situation und darf die Bestätigung nicht
abreißen lassen.

Ist der Wechsel bestätigt, ist die Grenze das **erste** Foto des Fensters, nicht das bestätigende;
sein Motivbild wird der neue Bezug.

### 4. Wer mitredet

Ein Foto **ohne Kopfzeile** (`PhotoMotifAssessment`) trägt noch keine Motive: Es wird übergangen —
es löst keine Grenze aus, zerfällt kein Fenster und zählt in keinem mit. Ein Foto **mit** Kopfzeile,
dessen acht Stärken alle unter der Grenze liegen, hat dagegen ein Motivbild, nämlich das leere; es
redet voll mit, und der Wegfall aller getragenen Motive ist ein Wechsel wie jeder andere. Ebenso
übergangen wird ein als Dokument oder Bildschirmabbild ausgeschlossenes Foto
(`excluded_document`) — fortgeschrieben aus ADR 0091 Punkt 2: Es zählt in keiner Motivauswahl als
Motivträger und darf die Gliederung dann auch nicht lenken. Übergangen heißt in beiden Fällen
**nicht** ausgeschlossen: Das Foto bleibt Mitglied seines Events.

Eine Cloud-Aussage wird nicht vorausgesetzt; die lokale Grundlage trennt mit. Gelesen werden die
**wirksamen** Stärken (`motif_strengths.py::load_effective_strengths`), womit eine Nutzerkorrektur
genau wie eine Modellaussage wirkt — sichtbar beim nächsten Lauf, weil ein Event ein Lauf-Artefakt
ist und keine Korrektur eine bestehende Gliederung neu bildet.

### 5. Die Grenze „getragen" wird geteilt, nicht verdoppelt

Was als getragenes Motiv gilt, beantwortet `selection.py::carried_motifs` — dieselbe eine
Herleitung, die der Auswahlvorschlag und `MotifStrengthOut.present` benutzen, mit derselben
unkalibrierten, inklusiven Grenze `MOTIF_PRESENCE_THRESHOLD`. Eine eigene Grenze für die Gliederung
wäre ein zweiter Begriff von „dieses Foto zeigt X" im selben Produkt.

Das bleibt innerhalb von ADR 0091 Punkt 8: Gelesen wird **keines** der Anzeigebänder, und es
entsteht keine Zugehörigkeit eines Fotos zu einem Motiv — die Partition ist weiterhin allein das
Event. Entschieden wird ausschließlich über die **Grenze zwischen zwei Fotos**.

## Konsequenzen

- ADR 0087 bekommt einen Teil-Vermerk: Abschnitt 3, letzter Satz, gilt nicht mehr. Protokoll,
  Reinheit, nicht kurzgeschlossene Auswertung und die Liste als Erweiterungspunkt für **paarweise**
  Signale bleiben unberührt.
- Eine Änderung an `MOTIF_PRESENCE_THRESHOLD` verschiebt ab jetzt zweierlei: welche Fotos der
  Auswahlvorschlag als Motivträger sieht **und** wo Events beginnen.
- Eröffnet ein atypisches Foto ein Event und folgt ihm ein anhaltend anderes Motivbild, entsteht ein
  Event aus diesem einen Foto. Das ist zulässig (die Zusagen über Events kennen keine Mindestgröße)
  und die Kehrseite des festen Bezugs aus Punkt 2.
- Keine Migration, keine Schemaänderung, keine Änderung an der API: Der Motivwechsel verschiebt
  Grenzen, nicht Felder. `EventCandidate` bekommt zwei Felder mit Vorgabewerten, die ohne
  Motivangabe die bisherige Gliederung liefern.
- Der Zusatzaufwand ist ein weiterer linearer Durchlauf über die Kandidaten des Laufs.
- `docs/architecture.md` zieht im selben Pull Request nach.
