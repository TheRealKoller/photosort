# 0150 - Privat heißt dateilokal; geteilt heißt öffentlich am Definitionsort

**Status:** Accepted
**Datum:** 2026-11-18
**Bezug:** Issue [#648](https://github.com/TheRealKoller/photosort/issues/648), Story „Was andere Module brauchen, ist öffentlich und liegt fachlich richtig"; löst die Abschnitte 1 und 2 von ADR [`0149`](./0149-ein-lauf-eine-datei-ein-einstiegspunkt.md) teilweise ab

## Kontext

Die Aufteilung aus ADR 0149 hat die private Schicht in viele Dateien verteilt, ohne die
Sichtbarkeit mitzunehmen: `worker/_runs.py`, `worker/_criterion/*`, `api/photos/_reads.py` und
`api/photos/_conversion.py` definieren Namen mit führendem Unterstrich, die andere Dateien
importieren, über `modul._name` lesen oder als Patch-Zeichenkette nennen — gemessen 225 Bezüge
auf 61 Symbole im Produktionscode und 71 Symbole in 35 Testdateien. Der Unterstrich sagt damit
nichts mehr über die Reichweite; er markiert einen Namen, den trotzdem jeder liest. Zwei weitere
Folgen derselben Lücke: `worker/__init__.py` trägt die Namen zusätzlich als zweites Abbild
(`__all__`), und sechs Importe innerhalb von Funktionen existieren allein, weil sonst ein Zyklus
entstünde.

## Entscheidung

### 1. Privat heißt dateilokal

Ein Name mit genau einem führenden Unterstrich ist nur in der Datei benutzbar, die ihn definiert.
Ausgenommen sind Dunder-Namen und der reine `_`. Eine `__init__.py` ist eine Datei wie jede
andere: was sie nicht selbst definiert, bietet sie nicht an.

### 2. Ein Unterstrich am Modulnamen ist paketintern

`_runs`, `_criterion`, `_reads` und `_conversion` behalten ihren Namen. Sie werden nie über die
Paketgrenze benutzt — das hält der Paketgrenzen-Wächter aus ADR 0149 fest. Die Regel hier misst
gebundene Namen, nicht die Ablage; ein Modulsegment mit Unterstrich bleibt deshalb außerhalb der
Messung.

### 3. Öffentlich werden heißt: am Definitionsort umbenannt

Der Unterstrich fällt dort, wo der Name definiert ist. Der alte Name verschwindet vollständig —
kein Alias, kein Re-Export, kein zweiter Name daneben. Aufrufer nennen den neuen Namen an der
Definitionsstelle. Das Paket exportiert die neu öffentlichen Namen nicht: `worker/__init__.py`
verliert jede Zeile, die nur das Abbild eines Untermoduls war.

### 4. Geteiltes bleibt in der gemeinsamen Schicht; wer es braucht, zieht dorthin

`_runs` bleibt der Ort für Laufverhalten, die Phasen bleiben die Orte ihrer Kriterien. Ein Modul,
das einen dieser Orte braucht, liegt im selben Paket. Deshalb zieht `classification_review.py`
nach `worker/classification_review.py`: es ist ein Lauf (ADR 0149 Punkt 5) und bezieht `_runs`
und `_criterion.local` auf Modulebene. Sein Einstieg bleibt `run_classification_review`. Kein
Import innerhalb einer Funktion bleibt zurück, der nur einen Zyklus vermeidet; die Kante, die er
verdeckte, steht im Import-Graph.

### 5. Ein Wächter liest den ganzen Baum

`backend/tests/test_private_name_boundary.py` prüft Produktion und Tests über den Syntaxbaum:
`from … import _name`, Attributzugriff `alias._name` auf ein `photosort`-Modul,
`setattr`/`getattr`/`monkeypatch.setattr`/`patch.object` mit `_name` und Patch-Zeichenketten der
Form `photosort.a.b._name`. Die Meldung nennt Fundstelle und Namen: `datei:zeile: _name aus
modul`. Der eigene private Name der Datei bleibt erlaubt, ein Modulsegment mit Unterstrich wird
übersprungen (Punkt 2), `TYPE_CHECKING`-Importe zählen mit.

### 6. Testbezug ist die öffentliche Schnittstelle

Ein Test importiert und patcht keinen privaten Produktionsnamen. Geprüfte Funktionen werden über
ihren öffentlichen Namen gelesen, gepatcht wird an der Nachschlagestelle. Namen, die nur ein Test
benutzt, werden am Definitionsort öffentlich; Struktur-Wächter, die einen Funktionsnamen als
Zeichenkette führen, nennen den öffentlichen Namen.

### 7. Der Einstiegspunkt zieht weiterhin alle Dateien mit

`import photosort.worker` lädt jede Datei des Pakets — künftig transitiv über die Laufzeitkanten
statt über Re-Exporte. Die Zusage bleibt, ihre Form ändert sich mit Punkt 3.

## Begründung

Ein Sichtbarkeitsmerkmal, das nur eine Absicht ausdrückt, ist eine Behauptung, die niemand prüft.
Punkt 1 macht aus dem Unterstrich eine Regel, die der Compiler nicht kennt, der Wächter aber
mechanisch nachweist. Punkt 3 hält die zweite Adresse aus dem Weg, an der ein Name still
veralten kann; ein Re-Export ist eine Kopie, die beim nächsten Umbenennen driftet. Punkt 4 löst
die Zyklus-Importe an der Wurzel statt am Symptom: wer einen Baustein braucht, zieht an den Ort
des Bausteins, und die Abhängigkeit wird sichtbar. Punkt 5 ist die einzige Stelle, an der die
Zusage testbar wird, ohne dass jemand die Konvention auswendig kennt; Punkt 2 hält den Wächter
davon ab, die gewollte Paketbildung als Verstoß zu lesen.

## Konsequenzen

- Die Sichtbarkeit ist eine reine Namensänderung: Verhalten, Testfallzahl und Aussage bleiben;
  die Zusicherungen aus Spec 0648 AK5 (genau eine Stelle je Remote-Pfad, je Zeichensanitisierung,
  je Abbruch-Endzustand und je Lauf-Übernahme) gelten unverändert.
- `worker/__init__.py` und `api/photos/__init__.py` schrumpfen um die Abbilder; ihre
  `__all__`-Zusagen gelten für den verbleibenden Bestand.
- Die Sichtbarkeitsprüfung ist ein Test, keine Laufzeitprüfung: ein privater Name bleibt zur
  Laufzeit erreichbar, er wird nur nicht mehr benutzt.
- Ein Test, der heute über das Paket liest, adressiert künftig das Untermodul; ein
  Patch-Ziel folgt der Nachschlagestelle.
- Für die neu öffentlichen Namen gilt dieselbe Dokumentationspflicht wie für jeden anderen
  öffentlichen Namen: fachlicher Zweck und geltende Zusicherung.
