# 0107 - Ein verwendbarer Sehenswürdigkeitsname: eine Grenze und ein projektgebundenes Namensregister

**Status:** Accepted
**Datum:** 2026-09-14
**Bezug:** ADR [`0025`](./0025-cloud-landmark-erkennung.md) Punkt 6 (die Tabelle, die der Name
bewohnt), ADR [`0087`](./0087-event-als-persistierte-einheit-und-trennsignale-als-liste.md)
(`LandmarkChangeSignal` als Trennsignal), ADR
[`0106`](./0106-grobe-ortsangabe-geht-in-die-sehenswuerdigkeits-erkennung.md) (liefert den
Ortsnamen, der hier als Sperre wirkt), Spec
`specs/features/0469-verlaessliche-sehenswuerdigkeitsnamen.md`

## Kontext

Ein erkannter Name wird heute an zwei verschieden strengen Maßstäben gemessen: Für die Bewertung
zählt er erst ab der registrierten Konfidenzschwelle, als Gruppenname erscheint er unabhängig
davon — `_upsert_landmark_detection` schreibt die Zeile, sobald überhaupt ein Name geliefert
wurde. Und `LandmarkChangeSignal` vergleicht Namen zeichengenau, weshalb zwei Schreibweisen
derselben Sehenswürdigkeit eine Reise in zwei Gruppen zerlegen.

## Entscheidung

### 1. Eine Grenze, an einer Stelle, für jede Verwendung des Namens

Die Konfidenzschwelle des Kriteriums zieht nach `landmark.py` und wird von dort als
`presence_threshold` in `CRITERIA_REGISTRY["landmark"]` gelesen (die Richtung ist erzwungen:
`criteria.py` importiert bereits aus `landmark.py`, umgekehrt entstünde ein Zyklus). Bewertung und
Name messen danach an **demselben** Wert; zwei Maßstäbe für dasselbe Ergebnis kann es nicht mehr
geben, ohne dass jemand den Wert an zwei Stellen schreibt.

Der Zahlwert bleibt zunächst unverändert. Die Änderung ist die Gleichheit des Maßstabs, nicht
seine Höhe; ob er steigen muss, entscheidet die Abnahme an einer echten Reise.

### 2. Über die Verwendbarkeit entscheidet die Lesestelle, nicht die Schreibstelle

Die Erkennungszeile wird unverändert geschrieben, sobald ein Name geliefert wurde — **die Antwort
ist bezahlt und bleibt vollständig erhalten**. Ob aus ihr ein verwendbarer Name wird, entscheidet
`worker.py::_landmark_names`, dieselbe Stelle, die schon heute als einzige Quelle von
`events.landmark_name` gilt und dort bereits die Sanitisierung des Altbestands trägt.

**Folge, und sie ist gewollt:** Eine spätere Änderung der Grenze wirkt beim nächsten Neuaufbau der
Gruppierung, ohne einen einzigen erneuten Cloud-Aufruf. Läge die Entscheidung an der Schreibstelle,
wäre jede Korrektur der Grenze kostenpflichtig und für den Altbestand gar nicht mehr möglich.

Ein verworfener Treffer ist von „nie erkannt" nicht zu unterscheiden: Das Foto fällt auf Ortsangabe
bzw. Koordinate zurück, es entsteht kein Anzeigezustand und kein Hinweis auf die Vermutung.

### 3. Das Namensregister ist projektgebunden

Neue Tabelle `landmark_names` mit `project_id`, dem normalisierten Namen als projektweit
eindeutigem Schlüssel, dem zuerst gesehenen Namen als Anzeigeform, dem Einbettungsvektor und dem
aufgelösten Ortsnamen.

Das ist die **bewusste Abweichung** vom Vorbild `fine_labels`, das projektübergreifend steht und
das ausdrücklich damit begründet: „hund" ist kein personenbezogenes Datum. Ein
Sehenswürdigkeitsname ist eines — er benennt einen Ort, an dem diese Familie war, und ein
projektübergreifendes Register führte die Reisen verschiedener Projekte in einer Tabelle zusammen.
Das Register fällt deshalb unter dieselbe projektgebundene Lebensdauer wie `place_lookups` (ADR
0102) und wird in `project_deletion.py` mitgelöscht.

### 4. Der Ortsname ist die Sperre, die Ähnlichkeit die Brücke

Ein Rohname trifft einen Registereintrag in zwei Schritten, nach dem Muster von
`remote_classification.py::resolve_canonical_label`:

1. **Gleicher normalisierter Name** — trifft immer, ohne Ortsprüfung und ohne Modellaufruf. Zwei
   zeichengleiche Namen gelten schon heute als dieselbe Sehenswürdigkeit; daran ändert diese
   Entscheidung nichts.
2. **Ähnlichkeit** oberhalb einer eigenen Schwelle — trifft **nur**, wenn nicht beide Seiten einen
   aufgelösten Ortsnamen tragen, der verschieden ist.

Die Sperre in Schritt 2 trägt die Zusicherung „zwei tatsächlich verschiedene Sehenswürdigkeiten
werden nie zu einer zusammengezogen" gegen die gefährlichste Klasse: Ein mehrsprachiges
Satz-Einbettungsmodell hält „Kölner Dom" und „Ulmer Dom" für nahe verwandt, weil es die Bauform
vergleicht und nicht den Eigennamen. Ohne Sperre entstünde aus zwei Sehenswürdigkeiten eine — und
damit genau der falsche Gruppenname, den diese Story abschaffen soll. Trägt eine der beiden Seiten
keinen aufgelösten Ortsnamen, entscheidet die Ähnlichkeit allein; das ist das bewusst getragene
Restrisiko dieser Entscheidung.

Die Ähnlichkeitsschwelle ist **eine eigene Konstante**, nicht die der Feinlabels: Eigennamen
verlangen einen strengeren Maßstab als Sachbegriffe, und beide müssen sich unabhängig bewegen
können. Sie ist wie ihr Vorbild dokumentiert-unkalibriert — es gibt keinen Namenskorpus im
Repository.

### 5. Kanonisiert wird an der Schreibstelle, Altbestand fällt auf den Rohnamen zurück

Die Erkennungszeile bekommt eine zusätzliche Spalte für den kanonischen Namen, gefüllt in der
Cloud-Phase, in der das Einbettungsmodell ohnehin gebaut wird. Die Lesestelle nimmt den kanonischen
Namen, sonst den Rohnamen.

**Kein Nachziehen für frühere Erkennungsläufe** (Vorgabe der Story). Ohne die Spalte verhält sich
eine Altzeile exakt wie heute. Der Neuaufbau der Gruppierung bleibt dadurch eine reine
Datenbankoperation — er läuft auch aus dem Anfragepfad heraus (`rebuild_run_grouping` nach einer
Zeitversatz-Änderung), und dort darf kein 113-MB-Modell geladen werden.

Kanonisiert wird nur ein Name, der die Grenze aus Punkt 1 erreicht: Ein unsicherer und
wahrscheinlich falscher Name soll nicht die Anzeigeform eines Registereintrags besetzen, dem sich
später der richtige anschließt.

## Konsequenzen

- **Migration, additiv:** neue Tabelle `landmark_names`, eine neue Spalte auf
  `photo_landmark_detections`. `project_deletion.py` bekommt eine Löschanweisung in der per Test
  erzwungenen Reihenfolge.
- Die reine Auflösungslogik bekommt ein eigenes, datenbankfreies Modul (Muster `places.py`); der
  Datenbankzugriff bleibt in `worker.py`. Die beiden generischen Helfer (Textnormalisierung,
  Kosinus-Ähnlichkeit) ziehen dafür nach `label_embedding.py` um, damit der
  Sehenswürdigkeits-Pfad nicht aus dem Kategorie-Pfad importieren muss — eine Verschiebung ohne
  Verhaltensänderung.
- `LandmarkChangeSignal` bleibt unverändert und vergleicht weiter zeichengenau. Seine
  Selbstbeschreibung („zwei Schreibweisen-Varianten desselben Orts trennen") wird falsch und
  gehört im selben Pull Request korrigiert: Die Vereinheitlichung liegt jetzt davor.
- Keine neue Abhängigkeit und kein neues Modell-Asset — das Einbettungsmodell ist seit den
  Feinlabels im Bestand.
- `docs/architecture.md` zieht im selben Pull Request nach.
