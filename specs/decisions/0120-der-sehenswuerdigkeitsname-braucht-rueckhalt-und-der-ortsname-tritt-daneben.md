# 0120 - Der Sehenswürdigkeitsname braucht Rückhalt, und der Ortsname tritt daneben

**Status:** Accepted
**Teilweise abgelöst:** ADR
[`0118`](./0118-sehenswuerdigkeit-trennt-nicht-mehr-und-eine-eigene-ausdehnungsgrenze-fuers-zusammenlegen.md)
Punkt 3 — sowohl „der früheste Name gewinnt" als auch „Ein Event mit Namen bekommt keinen Ortsnamen
(`locality_of_event`)". Unberührt gelten dort Punkt 1, 2 und 4. In ADR
[`0102`](./0102-ortsauskunft-je-zelle-projektgebunden-eventname-als-laufartefakt.md) entfällt allein
die Konsequenz „Der Ortsname wird zur **zweiten** Quelle einer Event-Überschrift"
(`formatEventHeading` bekommt eine dritte Stufe zwischen Sehenswürdigkeit und Nummer); Punkt 1 bis 6
gelten unverändert. ADR
[`0107`](./0107-sehenswuerdigkeitsname-eine-grenze-und-ein-projektgebundenes-namensregister.md) gilt
vollständig weiter: Das Namensregister entscheidet, **welchen** Namen ein Event trägt, diese
Entscheidung entscheidet, **ob**.
**Datum:** 2026-09-20
**Bezug:** Spec `specs/features/0514-*.md`, Issue #514, ADR 0118 Punkt 3, ADR 0102, ADR 0107

**Umfang:** rund 120 Zeilen gegen einen Richtwert von 100. Die beiden abgelösten Zusagen (wer den
Namen trägt, was der Ortsname mit ihm zu tun hat) sind ohne ihre Kehrseite nicht anwendbar, und die
Kehrseite der zweiten liegt außerhalb des Codes.

## Kontext

Die Sehenswürdigkeitserkennung läuft regelmäßig ortsblind: Am gemessenen Projekt 3 entstanden 42,3 %
der Erkennungen **ohne jeden Ortshinweis**, und 8 Events wurden von genau einem von vielen Fotos
benannt (Spec 0506, Messprotokoll Block C3). Ein Name benennt heute das Event des **frühesten**
benannten Fotos (ADR 0118 Punkt 3) und verdrängt dort dessen aufgelösten Ortsnamen — der früheste
Treffer entscheidet, unabhängig davon, ob ihn ein einziges Foto oder die Mehrheit der Aufnahmen
stützt, und ob er überhaupt zum Ort passt.

## Entscheidung

### 1. Ein Name braucht Rückhalt: `LANDMARK_MIN_SHARE = Fraction(1, 10)`

**Gewinner** ist der Name mit den **meisten** Trägerfotos unter den Mitgliedern; bei Gleichstand der
**frühere** (kleinster Index in der nach `(taken_at, photo_id)` sortierten Mitgliederfolge).
**Danach** wird sein Anteil geprüft: Er benennt das Event nur, wenn er mindestens
`LANDMARK_MIN_SHARE` der Mitglieder trägt — ein Zehntel **einschließlich**. Scheitert er, trägt das
Event **keinen** Namen; kein zweiter Kandidat rückt nach.

**Warum kein zweiter Kandidat nachrücken kann:** Der Gewinner hat per Konstruktion das Maximum der
Trägerzahlen. Ist sein Anteil zu klein, ist jeder andere es erst recht — die Prüfung steht hinter
der Auswahl und braucht keine Schleife.

**Warum ein exakter Bruch und kein Zahlenwert.** Die Konstante steht in `events.py`, wird überall
als **Modulattribut** gelesen (nie als Default-Parameterwert gebunden — sonst liefe
`monkeypatch.setattr` ins Leere) und wird als `Fraction` gehalten. Verglichen wird
kreuzmultipliziert über Zähler und Nenner der Konstante, also in ganzen Zahlen: Ein Float-Vergleich
entschiede über `1/10` an der Rundungsgrenze und damit über das Akzeptanzkriterium. Der Wert selbst
ist der Nenner des Kriteriums und **kein kalibrierter** — er wird nicht verschoben, sondern
dokumentiert.

### 2. Der Ortsname tritt daneben — und es gilt EINE Ortsregel

`locality_of_event` verliert die Sehenswürdigkeits-Sperre vollständig. Ein Ortsname wird für
**jedes** Event nach derselben Regel vergeben, samt Viertel-Ergänzung, und die
Gleichnamigkeitszählung in `assign_place_names` liest `landmark_name` danach **überhaupt nicht mehr**.

**Der Grund ist das Akzeptanzkriterium, nicht die Bequemlichkeit.** Verlangt ist der Ortsname, den
*dasselbe Event ohne Sehenswürdigkeitsnamen zeigen würde*. Eine zweite, dann teilweise gesperrte
Regel — benannte Events zählen nicht mit, bekommen aber einen Namen — erfüllte das nur, solange
kein anderes Event denselben Ortsnamen trägt: Benannte und unbenannte Events bildeten zwei Klassen,
und welche Klasse ein Viertel bekommt, hinge an der Anwesenheit eines modellgelieferten Strings.
Eine Regel statt zwei ist die einzige Fassung, in der der Satz auch bei Gleichnamigkeit stimmt.

**Getragene Kehrseite:** Ein vorher unbenanntes Event kann sein Viertel neu bekommen oder verlieren,
weil ein benanntes Event denselben Ortsnamen trägt und jetzt mitzählt. Das ist eine
Anzeigeverschiebung, keine neue Abflussrichtung — die Ergänzung fügt dem Ortsnamen die feinere
Stufe hinzu, die `place_lookups` ohnehin führt — und sie trifft nur Läufe, in denen zwei Events
denselben Ortsnamen tragen.

**Die Koordinatenstufe bleibt verdrängt.** `_place_of` wird **nicht** angefasst: Ein Event mit
verwendbarem Namen bleibt `place_kind='landmark'` mit `place_lat`/`place_lon = NULL`. Neben dem
Namen steht ab jetzt der **Ortsname**, nicht die Koordinate. Das ist die zweite Hälfte des
Akzeptanzkriteriums, und sie hängt an `_place_of` allein.

### 3. Die Prüfung sitzt am fertigen Event, nicht an der Erkennung

Der Anteil ist eine Eigenschaft des **Events**; die Erkennung sieht ein einzelnes Foto und liegt
zeitlich **vor** der Event-Bildung. Ein Riegel dort könnte die Frage gar nicht stellen und wäre
zudem eine Schwelle auf einem persistierten, lauf-unabhängigen Feld
(`photo_landmark_detections`) für eine lauf-abhängige Aussage. Die Prüfung steht deshalb in
`events.py::_name_of` — der **einen** Stelle, an der der Name eines Events entsteht (eine
Aufrufstelle: `_built`) — und wirkt damit auch über eine Zusammenlegung hinweg, ohne zweiten Zweig.

Der Rumpf der Auswahl wird dabei zur Zählung über die Mitglieder; die Zusicherung
`place_kind='landmark'` ⇒ `landmark_name` gesetzt läuft weiterhin über dieselbe eine Aufrufstelle
und kann nicht auseinanderlaufen. **Ein Name, der die Schwelle reißt, wird verworfen, nie gekürzt
oder ersetzt** — im Muster von `_usable_name` und `MAX_LANDMARK_NAME_LENGTH`.

## Konsequenzen

- **`worker.py` löst ab jetzt auch die Zellen benannter Events auf.** Der Zellenfilter
  `if built.landmark_name is None` fällt: Das Akzeptanzkriterium verlangt den Ortsnamen neben dem
  Namen, also muss seine Zelle gefragt werden. Mehr gestellte Anfragen je Lauf, und die Zahl der
  `place_lookups`-Zeilen wächst — beides endlich (Zellen sind gerundet und projektweit
  wiederverwendet).
- **Das Sicherheitskonzept zieht nach** (`specs/architecture/0003-securitykonzept.md`, Muster
  `security-engineer`): In der M9-Fortschreibung fallen die ortsmindernden Pfade (2) und (3) weg — (2)
  mit dem Zellenfilter, (3) dadurch, dass der Name keinen Zähler mehr liest; es bleibt (1), und auch
  der nur für die Koordinatenstufe. **Zwei Bewegungen gehen dabei in die Gegenrichtung:** Ein Event,
  das seinen Namen verliert, rückt in die Koordinatenstufe und schreibt erstmals
  `events.place_lat`/`place_lon`, und ein benanntes Event trägt seinen Ortsnamen jetzt auch in
  `EventOut.place_name` hinaus. Die Entlastungsbegründung („es geht weniger Ort hinaus") trägt so
  nicht mehr, und der Restrisiko-Eintrag, der die Plausibilisierung an #514 verweist, ist ein
  erledigter Vorgang, kein Risiko.
- **Die Prüfkommandos messen die Gegenanzeige mit.** `event_probe.py` Block C3 weist ab jetzt aus,
  wie viele Events einen Namen tragen und wie viele **keinen** Trägeranteil unter der Schwelle haben
  (kleinster vorkommender Anteil als Zahl) — die eine Zahl, die die neue Regel belegen oder
  widerlegen kann. `events_named_by_a_single_photo` bleibt gültig und wird erst dadurch aussagekräftig:
  Ein Ein-Foto-Träger in einem Zwei-Foto-Event erfüllt ein Zehntel, einer in einem dreißig-Foto-Event
  nicht. `place_probe.py::heading_counts` bildet seine Partition neu — ein benanntes Event ist ab
  jetzt **gleichzeitig** benannt und ortsbenannt, die beiden Mengen subtrahieren sich nicht mehr.
- **Tests, die die alte Zusage behaupten, werden ersetzt statt angepasst** — das sind Aussagen über
  eine abgelöste Regel, und ein grüner Fall über `Eiffelturm` nach einem verdrängten `Paris` wäre die
  falsche Aussage über das laufende System. Betroffen sind die Namens- und Ortsnamensfälle in
  `backend/tests/test_events.py`, `backend/tests/test_worker_place_names.py` und
  `frontend/src/utils/timeOfDay.test.ts`. Der bestehende 1:1-Fall bleibt im Ergebnis gleich und wird
  zum Gleichstandsfall (beide Namen ein Trägerfoto → der frühere gewinnt).
- **Die Gliederung bleibt, wie sie ist.** Der Name bewegt seit ADR 0118/0119 keine Kante und keinen
  Riegel; diese Entscheidung ändert nur, **ob** ein Event einen trägt und **was** daneben steht.
  Betroffen sind die Namen und Ortsnamen jedes neu berechneten Laufs; bestehende Läufe behalten ihre
  Zeilen, bis sie neu berechnet werden. **Keine Migration, keine Schemaänderung, kein neues Feld:**
  `events.place_name` existiert, und `place_kind='landmark'` gibt es unverändert.
- **`docs/architecture.md` zieht im selben Pull Request nach** — die Antwortbeschreibung nennt die
  Rangfolge der Überschrift als drei Stufen, und die ist ab jetzt keine.
- **Die Plausibilisierung ist damit beantwortet, nicht verschoben:** Kein einzelnes Foto benennt
  ein Event mehr, und ein Name, den weniger als ein Zehntel seiner Aufnahmen stützt, verschwindet
  aus der Anzeige — nicht aus `photo_landmark_detections`.
