# 0104 - Die Ausschuss-Entscheidung: eigenes projektweites Datum, das den Automaten übersteuert

**Status:** Accepted
**Datum:** 2026-09-14
**Bezug:** Spec [`features/0374-duplikate-vergleichen.md`](../features/0374-duplikate-vergleichen.md),
ADR [`0099`](./0099-endauswahl-als-projektentscheidung-ueber-zwei-entwuerfen.md) (Punkt 3: das
Muster der projektweiten Entscheidung je Foto, hier wiederverwendet), ADR
[`0100`](./0100-nacharbeit-als-ereignis-log-gewichte-persistiert-und-versioniert.md) (das
Ereignis-Log, in das diese Entscheidung ausdrücklich **nicht** schreibt)

## Kontext

Der Ausschuss-Schritt erkennt Duplikate über die Hamming-Distanz der dHashes, bildet Cluster und
schreibt je Cluster `PhotoScore.duplicate_of` — **nur für die Verlierer**, jeweils auf den Gewinner.
Welche Fotos danach weiterlaufen (Kriterien-Bewertung, Cloud-Klassifizierung, Album), hängt
ausschließlich an `PhotoScore.suggested_status IS NULL`, ausgeschrieben an sechs Abfragestellen.

Die bisherige Nutzerhandlung „Vorschlag übernehmen" schreibt eine `Rating`-Zeile und ändert daran
nichts. Ein Nutzer, der in einer Serienaufnahme eine **andere** als die vom Automaten gewählte
Aufnahme behalten will, hat dafür kein Mittel: Seine Zustimmung wie sein Widerspruch bleiben ohne
Wirkung auf den Bestand, der weiterläuft.

## Entscheidung

### 1. Die Duplikat-Gruppe bleibt abgeleitet — ein Stern, keine gespeicherte Identität

Die Gruppe wird zur Lesezeit aus `PhotoScore.duplicate_of` gebildet. Repräsentant ist der Gewinner
(der Wert, auf den gezeigt wird); zu einem Foto `P` des Projekts ist der Repräsentant `P.duplicate_of`,
sonst `P` selbst, und die Gruppe ist `{Repräsentant} ∪ {x : x.duplicate_of = Repräsentant}`. Zeigt
niemand auf `P` und trägt `P` selbst nichts, gibt es keine Gruppe.

Es entsteht **keine** Gruppen-Id und keine Gruppentabelle. Der Stern ist bauartbedingt flach — der
Gewinner zeigt nirgendwohin, Ketten sind ausgeschlossen —, und eine gespeicherte Identität wäre ein
zweites Abbild derselben Aussage, das beim nächsten Lauf neu vergeben werden müsste.

`PhotoScore.cluster_key` ist **nicht** die Duplikat-Gruppe: Er trägt den Zeit-/Ortscluster und wird
nur für die *nicht* aussortierten Fotos gesetzt. Ein Griff danach wäre still falsch.

### 2. Die Entscheidung ist ein eigenes, projektweites Datum — und keine Albumentscheidung

Neue Tabelle `photo_duplicate_decisions`, `photo_id` als Primär- **und** Fremdschlüssel (Muster
`final_selection_decisions`), Spalte `decision ∈ {keep, discard}`, kein `user_id`, keine
Lauf-Bindung. Keine Zeile heißt „noch nicht entschieden"; ändern heißt den anderen Wert schreiben.

- **`discard` und nicht `rejected`.** `RatingStatus.REJECTED` ist die Albumentscheidung eines
  Nutzers und ausdrücklich keine Aussage über die Bildgüte. Hier steht die andere Frage: ob die
  Aufnahme den Ausschuss-Schritt überlebt. Ein geteilter Wertevorrat machte die beiden Fragen an
  jeder Lesestelle verwechselbar.
- **Die Vergleichsansicht schreibt keine `Rating`-Zeile und kein `FeedbackEvent`.** Über
  `write_own_rating` geschrieben, zöge jedes „behalten" ein `photo_included`-Ereignis nach sich und
  das Foto zugleich in den Album-Entwurf des Nutzers. Beides sind Aussagen, die niemand getroffen
  hat: Die Nacharbeit misst Korrekturen am Album, nicht am Ausschuss.
- **Projektweit, nicht je Nutzer.** Was nach dem Ausschuss weiterläuft, ist ein Projektvorgang.
  Zwei nutzereigene Antworten darauf wären zwei widersprüchliche Wahrheiten über denselben Bestand,
  und der Kriterien-Lauf müsste eine davon wählen.
- **Die Zeile hängt am Foto und überlebt deshalb einen erneuten Lauf**, ohne dass es dafür
  durchsetzenden Code braucht: `run_project_scoring` setzt `duplicate_of`, `cluster_key` und
  `suggested_status` zurück und fasst diese Tabelle nicht an.

### 3. Der Überlebenden-Bestand wird ein Prädikat an genau einer Stelle

`discard` überlebt nie, `keep` überlebt **solange die Aufnahme Duplikat-Verlierer ist**
(`duplicate_of IS NOT NULL`), ohne Zeile entscheidet `suggested_status` — als **eine** korrelierte
Skalar-Unterabfrage in `duplicates.py`, die alle bisherigen sechs Stellen ersetzt (`worker.py`
Kriterien-Lauf und Remote-Kandidaten, `api/projects.py` Schätzung und Kandidatenzahl,
`api/photos.py` `is_candidate` und der Vorschlags-Zweig). Die Objektfassung (`has_suggestion`)
bleibt über den bestehenden Paritätstest an die SQL-Fassung gebunden.

**Die Asymmetrie zwischen den beiden Werten ist die Entscheidung, nicht ein Detail.**
`suggested_status = REJECTED` trägt zwei Gründe — Duplikat-Verlierer und Unschärfe unterhalb
`SHARPNESS_REJECT_THRESHOLD`, wobei `duplicate_of` im zweiten Fall `NULL` bleibt. Ein unbedingtes
`keep` höbe damit eine Ablehnung auf, zu der der Nutzer nie befragt wurde: Er hat die Duplikatfrage
beantwortet, nicht die Schärfefrage. `discard` bleibt unbedingt, weil es den abfließenden Bestand
verkleinert. Die Bindung hat eine zweite Wirkung: Zerfällt die Gruppe später — der Repräsentant wird
gelöscht, der Hash ändert sich —, wird eine übrig gebliebene `keep`-Zeile von selbst wirkungslos,
ohne Aufräumlauf und ohne eigene Oberfläche. Ohne sie trüge die Aufnahme eine dauerhafte,
unsichtbare Ausnahme vom Ausschuss-Gate: Die Vergleichsansicht antwortet dann `404`, die Zeile ist
weder sichtbar noch widerrufbar, und die Aufnahme ginge bei jedem künftigen Lauf erneut an den
Anbieter.

**Sicherheitsauflage — dasselbe Prädikat ist die Grenze des Homeservers.** Es begrenzt, welche
Fotos den Homeserver Richtung Cloud-Anbieter verlassen dürfen (Auflage S8), und gilt für **jede**
Abfrage, die Cloud-Kandidaten bestimmt. Das sind **vier**, nicht eine: die beiden Läufe
(`worker.py::run_criterion_scoring`, das zugleich den Sehenswürdigkeits-Teilschritt speist, und
`worker.py::select_remote_category_candidates`) und die beiden vorgelagerten Kostenschätzungen
(`api/projects.py::_count_remote_category_candidates`, `api/projects.py::_count_landmark_candidates`).
Die Schätzungen folgen der Auswahl nicht von selbst, sondern sind eigene Anweisungen; sie zählen
dieselbe Menge, die der Lauf sendet. Angriffsmodell ist nicht ein Angreifer, sondern der Abfluss
selbst: Familienfotos, die zu einem Dritten gehen, gehen unwiederbringlich, und jedes Bild kostet
Geld. Der benannte Fehlgriff ist die naheliegende Teilumsetzung — das Prädikat in die Lesepfade der
Oberfläche zu legen und die Kandidatenwahl des Workers beim alten `suggested_status IS NULL` zu
belassen. Diese Alternative ist damit untersagt. Bei Verletzung verlassen ausdrücklich verworfene
Aufnahmen den Homeserver, behaltene fehlen in der Bewertung, und die Kostenschätzung nennt eine
andere Zahl, als der Lauf sendet — die Freigabe eines kostenpflichtigen Laufs beruht dann auf einer
Zahl, die nicht gilt. Alles drei ohne Fehler, ohne Meldung, sichtbar erst an der Abrechnung des
Anbieters.

**Folge, die benannt sein muss:** Eine entschiedene Aufnahme ist kein offener Vorschlag mehr und
verschwindet aus dem Filter `suggested` und aus der Zählung des Ausschuss-Gates. Form und Bedienung
des Gates — eine Liste, eine Abschluss-Aktion, keine Einzelbestätigungspflicht — bleiben unberührt.

## Konsequenzen

- **Die Schreibwege tragen keine Id-Liste im Body.** Es gibt einen Endpunkt je Aufnahme und einen je
  Gruppe; welche Fotos die Gruppe umfasst, bestimmt der Server aus dem Stern. Eine vom Aufrufer
  gelieferte Menge wäre ein Massen-Schreibweg auf beliebige Fotos des Projekts.
- **`PhotoOut` bekommt kein Feld.** Die Entscheidung hat außerhalb der Vergleichsansicht keine
  Anzeigerolle; sie reist in einem eigenen Antwortmodell neben dem Foto, nicht an ihm.
- **`project_deletion.py`** nimmt die neue Tabelle auf; der Vollständigkeitswächter gegen
  `Base.metadata` fängt ein Vergessen.
- **Der Demo-Bestand bekommt mindestens eine Duplikat-Gruppe.** Ohne sie ist die Ansicht weder
  vorführbar noch im Browser prüfbar, und kein Test würde rot. *Umgesetzt wurden zwei Gruppen in
  einem eigenen, fünften Demo-Projekt:* Die Zusage „bricht um, statt die Bilder kleiner zu machen"
  ist nur über zwei Gruppen **verschiedener Größe** belegbar — eine einzelne zeigt nicht, dass die
  Kachelbreite an der Fensterbreite hängt und nicht an der Mitgliederzahl. Ein eigenes Projekt
  statt zusätzlicher Fotos im bewerteten, weil dort an jedem Index ein benannter Sonderzustand
  hängt und die Event-/Ortsverteilung gegen die Fotoanzahl rechnet. **Folge:** `docs/setup.md` und
  der Skill `browse-app` nennen die Projektzahl und ziehen im selben Pull Request nach.
- **`docs/architecture.md`** bekommt die neue Tabelle, die drei Endpunkte und die neue Definition des
  Ausschuss-Überlebender-Bestands im selben Pull Request.
- **Die Duplikaterkennung bleibt unverändert** — Schwellwert, Clusterbildung und die Wahl des
  Gewinners werden nicht angefasst. Die Entscheidung setzt sich über ihr Ergebnis hinweg, statt es
  zu ändern.
