# 0096 - Auswahl mit Richtwert: Kontingente je Event, motivgeführte Vergabe mit Ähnlichkeitsabwertung

**Status:** Accepted
**Datum:** 2026-09-13
**Bezug:** Spec `specs/features/0429-*.md`, ADR
[`0091`](./0091-motive-mit-staerke-statt-hauptkategorie.md) (Stärkevektor als Datengrundlage; die
dort offen gelassene Auswahlregel wird hier getroffen), ADR
[`0087`](./0087-event-als-persistierte-einheit-und-trennsignale-als-liste.md) (das Event als
Partition), ADR [`0095`](./0095-albumtauglichkeit-vom-modell-qualitaet-getrennt-vom-inhalt.md)
(der Qualitätswert, der hier sortiert)

**Löst ab (teilweise):**
[`0071`](./0071-kuratierung-stabile-auswahl-ohne-backfill-und-einsehbarer-vorrat.md) — ausschließlich
die **Auswahlregel** „die besten N je Partition, N als Leseparameter" (Entscheidung 1, erster
Absatz) und der Query-Parameter `top_n_per_event`. Unverändert weiter gelten: die Auswahl ist eine
Eigenschaft des Laufs und nicht des Betrachters (kein Ablehnungsfilter, kein Backfill),
`curation_position` als alleinige Auskunft darüber, wo die Auswahl ein Foto zeigt, der einsehbare
Kandidatenvorrat samt `GET /projects/{id}/curation-candidates`, und die Auflage am Antwortaufbau,
einen Zwischenspeicher oder `ETag` über `no-store` hinaus nur mit dem Nutzer im Schlüssel zu führen.

**Umfang:** über dem Richtwert von rund 100 Zeilen, weil die Entscheidung ein mehrstufiges
Rechenverfahren festlegt, dessen Stufen einzeln prüfbar benannt sein müssen.

## Kontext

Seit ADR 0091 ist ein Motiv keine Zugehörigkeit mehr, sondern eine Stärke — und damit ist die
Motivmischung aus der Auswahl verschwunden: die besten Fotos eines Events sind die qualitativ
besten, und überwiegt dort ein Motiv, zeigen alle Plätze dasselbe. Zugleich gibt es keinen
Gesamtumfang: `top_n_per_event` vergibt jedem Event gleich viele Plätze, unabhängig davon, ob es
fünf oder fünfhundert Bilder trägt.

## Entscheidung

### 1. Der Richtwert lebt am Projekt, `NULL` heißt „Vorbelegung"

Neue Spalte `projects.selection_target: int | None`, Default `NULL`. **`NULL` heißt nicht „kein
Richtwert", sondern „nicht selbst eingestellt"** — der wirksame Richtwert ist dann ein Zehntel der
Bilderzahl des Projekts, aufgerundet und mindestens 1, berechnet im Moment der Auswahl. Eine
eingestellte Zahl gilt absolut und unverändert; sie zurückzusetzen heißt, die Spalte auf `NULL` zu
setzen.

Daraus folgt unmittelbar, was ein wachsender Bildbestand bewirkt: Solange nichts eingestellt ist,
wächst die Vorbelegung mit jedem Scan mit; eine eingestellte Zahl tut das nie. Die Vorbelegung wird
deshalb **nie** in die Spalte geschrieben — ein eingeschriebener Vorgabewert wäre von einer
Nutzereingabe nicht mehr zu unterscheiden, und beide Aussagen stünden an einer Stelle.

Die Ableitung ist genau eine Funktion (`selection.py::effective_target`); die Zahl `10` steht nur
dort. `ProjectOut` trägt beide Werte: `selection_target` (die eingestellte Zahl oder `null`) und
`effective_selection_target` (die wirksame). Das Frontend leitet die zweite nicht selbst ab.

### 2. Der Vorschlag ist ein persistiertes Lauf-Artefakt: eine Spalte, keine Tabelle

Neue Spalte `photo_rankings.selection_position: int | None`. `NULL` heißt „gehört nicht zum
Vorschlag"; sonst steht dort der 1-basierte Platz **innerhalb seines Events**, in der Reihenfolge,
in der das Verfahren die Plätze vergeben hat. Die Anzeigereihenfolge des Vorschlags ist
`(events.position, selection_position)` und damit chronologisch.

Persistiert und nicht zur Lesezeit gerechnet: Das Verfahren ist eine Greedy-Vergabe über alle
Kandidaten eines Events und nicht die Kosten jeder Anfrage wert; vor allem aber braucht der
Album-Entwurf je Nutzer (Story 6) einen Vorschlag, der sich unter ihm nicht bewegt, während er
darin arbeitet. Eine Motivkorrektur wirkt deshalb erst auf den nächsten Neuaufbau (Punkt 7).

**Nicht persistiert wird, unter welchem Motiv ein Foto seinen Platz bekam.** Ein Foto kann mehrere
vorkommende Motive zugleich vertreten; eine einzelne Spalte zwänge zur Wahl eines davon, und diese
Wahl wäre eine Rangfolge zwischen Motiven — genau das, was ADR 0091 abschafft. Welche Motive ein
Foto trägt, ist aus seinen Stärken und der Grenze aus Punkt 4 jederzeit ableitbar.

### 3. Das Verfahren, Stufe 1: Kontingente je Event

Auswahlfähig ist ein Kandidat des letzten erfolgreichen Kriterien-Laufs mit `rank_score IS NOT
NULL` und ohne `excluded_document`. Der erste Teil ist das Akzeptanzkriterium „ein Bild ohne
Qualitätsurteil erscheint nicht im Vorschlag"; der zweite ist die Zusage aus ADR 0091 Punkt 2 — ein
als Dokument oder Bildschirmabbild erkanntes Foto erscheint in **keiner** Motivauswahl, und der
Vorschlag ist eine.

Mit `n_i` als Zahl der auswahlfähigen Kandidaten des Events `i`, `m` als Zahl der Events mit
`n_i > 0` und `T` als wirksamem Richtwert:

1. **Abdeckung zuerst:** jedes Event bekommt einen Platz. Ist `m > T`, umfasst der Vorschlag mehr
   als `T` Bilder — die Abdeckung geht dem Richtwert vor.
2. **Der Rest nach gedämpftem Gewicht:** die verbleibenden `T - m` Plätze werden nach
   `w_i = √n_i` verteilt (Größte-Reste-Verfahren). Die Wurzel ist die Dämpfung: ein Event mit
   hundertfacher Bilderzahl bekommt das Zehnfache an Plätzen, nicht das Hundertfache.
3. **Obergrenze je Event:** `min(n_i, max(⌈T/m⌉, ⌈0,25 · T⌉))`. Kein Event bekommt mehr als ein
   Viertel aller Plätze — und nie weniger als den gleichen Anteil, sonst griffe die Kappe bei
   wenigen Events zwangsläufig immer. Gekappte Plätze gehen an die nicht gekappten Events; die
   Verteilung wiederholt sich, bis keine Plätze mehr frei sind oder alle Events an ihrer
   Obergrenze stehen.
4. **Kein Auffüllen über die Kandidaten hinaus:** bleiben danach Plätze übrig, verfallen sie. Das
   ist der Fall „es fehlt an guten Bildern", und der Vorschlag ist dann kleiner als `T`.

`0,25` ist ein dokumentiert-unkalibrierter Startwert derselben Klasse wie `TIME_CLUSTER_GAP` — es
gibt keinen Fotokorpus im Repository, gegen den ein anderer Wert zu belegen wäre.

### 4. Das Verfahren, Stufe 2: motivgeführte Vergabe mit Ähnlichkeitsabwertung

Je Event, unabhängig von den übrigen — alles, was als ähnlich gilt, liegt im selben Event, deshalb
ist die eventweise Vergabe dasselbe wie eine globale mit Kontingenten.

Ein Motiv **kommt im Event vor**, wenn mindestens ein auswahlfähiges Bild es mit einer wirksamen
Stärke ≥ `MOTIF_PRESENCE_THRESHOLD` (0,5) trägt. Diese Grenze gilt für alle acht Motive gleich, und
sie ist **nicht** eines der Anzeigebänder aus `motifs.py` (ADR 0091 Punkt 8 untersagt ausdrücklich,
dass ein auswählender Codepfad jene liest). Sie wohnt deshalb bei der Auswahl, in `selection.py`,
zusammen mit den übrigen Stellschrauben dieses Verfahrens.

Die Plätze werden nacheinander vergeben. Der **Wert** eines noch nicht gewählten Bildes `p` ist

    wert(p) = rank_score(p) · 0,5 ^ Σ_{s bereits gewählt} ähnlichkeit(p, s)

mit `ähnlichkeit(p, s) = geteiltes_motiv(p, s) · zeitnähe(p, s)`, wobei `geteiltes_motiv` 1 ist,
wenn es ein Motiv gibt, das **beide** mit mindestens `MOTIF_PRESENCE_THRESHOLD` tragen, sonst 0,
und `zeitnähe = max(0, 1 − |Δt| / 15 min)`. Ein zeitgleiches Bild desselben Motivs halbiert den
Wert eines weiteren; jenseits von 15 Minuten wertet nichts mehr ab. Ein eigenes Maß für visuelle
Ähnlichkeit gibt es nicht — Duplikate und Serien fängt der Ausschuss-Schritt ab.

Jeder Platz geht an das Bild mit dem höchsten Wert, aber aus einer eingeschränkten Menge:

- Gibt es ein vorkommendes Motiv, das kein bereits gewähltes Bild trägt, kommen **nur** Bilder in
  Frage, die ein solches Motiv tragen. Das gewählte Bild vertritt dann **alle** unvertretenen
  Motive, die es trägt — es wird keines gegen ein anderes abgewogen und keine Stärke mit einer
  anderen verglichen.
- Sonst kommen alle verbliebenen Bilder in Frage.

Diese Menge kann nicht leer sein: Ein vorkommendes Motiv hat per Definition ein Trägerbild, und ist
dieses gewählt, gilt das Motiv als vertreten. Hat ein Event weniger Plätze als vorkommende Motive,
entscheidet damit der Wert, welche Motive vertreten sind — ohne dass irgendwo eine Rangfolge
zwischen Motiven entstünde.

**„Innerhalb eines Motivs wird das qualitativ beste Bild gewählt" heißt: das mit dem höchsten
Wert.** Die Abwertung ist Teil der Auswahl und nicht ein Zusatz daneben; ein Bild kann deshalb
hinter einem qualitativ schwächeren zurückfallen, wenn ihm bereits ein ähnliches gewählt ist.

### 5. Determinismus ist strukturell, nicht zugesichert

Kandidaten werden beim Eintritt in die reine Funktion nach `photo_id` sortiert, Events nach
`position` durchlaufen, und jede Wahl des größten Werts bricht Gleichstand über die kleinere
`photo_id` (Konvention aus `ranking.py`). Kein Schritt liest eine Datenbankreihenfolge, eine
Mengeniteration oder eine Uhr.

### 6. Der Top-N-Pfad entfällt

`GET /projects/{id}/photos` verliert `top_n_per_event` und bekommt stattdessen `selection: bool`.
Im Auswahlmodus liefert der Endpunkt genau die Fotos mit `selection_position IS NOT NULL` des
letzten erfolgreichen Laufs, sortiert nach `(events.position, selection_position)`;
`curation_position` trägt dort die `selection_position`. Das Antwortschema bleibt unverändert. Ein
Übergangsweg, der beide Parameter kennt, entsteht nicht — er wäre eine zweite Auswahlregel.

### 7. Drei Auslöser, ein Rechenweg

Der Vorschlag entsteht ausschließlich in `_build_grouping_and_rankings`, unmittelbar nach den
Rangzeilen und innerhalb der bestehenden Phase `RANKING` — er ist deren Fortsetzung, kein neuer
Teilschritt mit eigener Fortschrittsanzeige. Damit deckt er beide bestehenden Aufrufer ab: den
Kriterien-Lauf und den Neuaufbau nach einer Versatz-Änderung.

Der dritte Auslöser ist die Änderung des Richtwerts (`PUT /projects/{id}/selection-target`). Sie
rechnet **nur** den Vorschlag des letzten erfolgreichen Laufs neu, aus persistierten Zeilen, ohne
Cloud-Aufruf und ohne Bildverarbeitung, synchron im Endpunkt — Events und Rangzeilen bleiben dabei
unangetastet. Beide Wege rufen dieselbe Funktion; ein zweiter Rechenweg liefe auseinander.

## Konsequenzen

- Ein Foto ohne Cloud-Grundlage hat keinen Qualitätswert und steht in keinem Vorschlag. Ohne
  Cloud-Freigabe ist der Vorschlag deshalb leer — die Ansicht sagt das bereits (ADR 0095).
- Eine Motivkorrektur verschiebt den Vorschlag nicht sofort, sondern beim nächsten Neuaufbau. Das
  ist die Kehrseite von Punkt 2 und gewollt: ein Vorschlag, der sich unter der Hand ändert, ist
  kein Entwurf mehr.
- `demo_state.py` schreibt `PhotoRanking`-Zeilen selbst und muss den Vorschlag über dieselbe
  Funktion setzen — sonst zeigt die Demo-Instanz eine leere Auswahl.
- Der Rückwärtsweg beider Migrationen stellt die Struktur wieder her, nie die Daten.
- `docs/architecture.md` (Owner: `architect`) beschreibt `PhotoRanking`, den Kuratierungsparameter
  und die Projekt-Endpunkte und wird im selben PR nachgezogen. `docs/setup.md` bleibt unberührt:
  keine neue Umgebungsvariable, kein neuer Setup-Schritt.
- Drei Stellschrauben (`0,25`, `0,5` für Grenze wie Abwertung, `15 min`) sind
  dokumentiert-unkalibrierte Startwerte an einer Stelle. Ob sie zu treffen sind, zeigt erst ein
  Vorschlag über echten Bildern; sie zu ändern ist eine Zahl in `selection.py` und ein erneuter
  Aufbau, keine Migration.
