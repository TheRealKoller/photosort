# 0100 - Die Nacharbeit als Ereignis-Log, die Qualitätsgewichte persistiert und versioniert

**Status:** Accepted
**Datum:** 2026-09-13
**Bezug:** Spec [`features/0432-diagnose-und-gewichte-aus-der-nacharbeit.md`](../features/0432-diagnose-und-gewichte-aus-der-nacharbeit.md),
ADR [`0098`](./0098-album-entwurf-aus-vorschlag-und-eigener-entscheidung.md) (die Gesten am Entwurf),
ADR [`0099`](./0099-endauswahl-als-projektentscheidung-ueber-zwei-entwuerfen.md) (die gemeinsame
Entscheidung), ADR
[`0095`](./0095-albumtauglichkeit-vom-modell-qualitaet-getrennt-vom-inhalt.md) (Modellstufe führt,
lokale Kriterien korrigieren), ADR [`0091`](./0091-motive-mit-staerke-statt-hauptkategorie.md)
(Motivstärken ohne Rangfolge untereinander)

**Umfang:** über dem Richtwert von rund 100 Zeilen, weil die Entscheidung drei Dinge zugleich
festlegt, die einzeln prüfbar bleiben müssen: die Form des Logs, die Herkunft des geltenden
Gewichtssatzes und das Rechenverfahren, das den einen aus dem anderen ableitet.

## Kontext

Das Datenmodell hält bis hierher ausschließlich den **heutigen Stand**: `ratings` und
`photo_motif_corrections` sind Upserts, `photo_criterion_scores` überschreibt je Lauf,
`final_selection_decisions` kennt ausdrücklich keinen Verlauf. Woran das System danebenlag, ist
daraus nicht ableitbar — eine zurückgenommene Korrektur hinterlässt keine Spur, zwei Korrekturen am
selben Foto sind nicht unterscheidbar, und ein Austausch besteht aus **zwei unabhängigen**
Schreibvorgängen, deren Zusammengehörigkeit allein der Client kennt. Zugleich ist jedes Gewicht in
`quality.py::QUALITY_CRITERION_WEIGHTS` eine Modulkonstante: ein dokumentiert unkalibrierter
Startwert, der ohne Codeänderung nicht bewegt werden kann.

## Entscheidung

### 1. Ein append-only Ereignis-Log neben dem Zustandsmodell

Es entsteht die Tabelle `feedback_events`, auf die **ausschließlich `INSERT`** läuft. Kein
Schreibpfad der Anwendung ändert oder löscht je eine ihrer Zeilen; einzige Ausnahme ist die
Projektlöschung. Daraus folgen ohne durchsetzenden Code beide Zusagen der Story: Ein Ereignis
überlebt eine spätere Neuklassifizierung und die Rücknahme der Korrektur, und mehrere Korrekturen am
selben Foto bleiben in ihrer Reihenfolge erkennbar — die Reihenfolge **ist** die aufsteigende `id`,
nie der Zeitstempel: Zwei Schreibvorgänge derselben Sekunde sind über eine Zeit nicht zu ordnen.

Das Log ist eine **zweite, unabhängige Aufzeichnung**. Kein Lesepfad des Entwurfs, der Endauswahl,
der Bewertung oder der Motive liest es, und sein Inhalt leitet sich nie aus dem Zustand ab. Das
Zustandsmodell bleibt unverändert.

### 2. Das Ereignis friert die Entscheidungslage ein — die lokalen Messwerte nicht

Ein Ereignis trägt die Angaben, die zum Zeitpunkt der Korrektur galten und **später überschrieben
werden**: die Modellstufe (`PhotoAlbumSuitability.level`) der beteiligten Fotos, deren Qualitätswert
(`PhotoRanking.rank_score` des damals letzten erfolgreichen Laufs) und bei einer Motivkorrektur die
damals wirksame Motivstärke. Ohne das Einfrieren wäre nach dem nächsten Klassifizierungslauf nicht
mehr entscheidbar, ob das Modell ein Motiv *zu schwach* oder *gar nicht* genannt hatte — die Aussage
des Ereignisses hinge am heutigen Stand, und genau das schließt die Story aus.

**Die lokalen Kriterienwerte werden dagegen zur Auswertungszeit gelesen**, nicht eingefroren: Sie
sind eine deterministische Messung an denselben Pixeln, während die Modellstufe eine je Lauf neu
erfragte Fremdaussage ist. Ein Paar, dessen Werte nicht mehr vollständig vorliegen, fällt aus der
Ableitung heraus; die ausgewiesene Fallzahl macht das sichtbar.

### 3. Der Austausch ist ein atomarer Schreibvorgang und genau ein Ereignis

„B statt A" ist die Aussage; die beiden Bilder für sich tragen sie nicht. Zwei getrennte Aufrufe
lassen sich nachträglich nur über eine Heuristik (gleicher Nutzer, gleiches Event, zeitlich nah) zu
einem Paar zusammenfügen — die stille Fehlpaarung zweier unabhängiger Handgriffe wäre an keinem
Ergebnis erkennbar. Der Austausch bekommt deshalb einen eigenen Endpunkt, der beide
Bewertungszeilen in **einer** Transaktion schreibt und **ein** Ereignis mit beiden Foto-Ids ablegt.
Er erzeugt dabei ausdrücklich **kein** zusätzliches Streich- und Aufnahme-Ereignis; sonst zählte
jeder Austausch dreifach.

Die Umkehr eines Austauschs ist ein weiterer Austausch in der Gegenrichtung mit eigenem Ereignis.
Sie löscht nichts: Es zählt, dass korrigiert wurde.

### 4. Ein Ereignis entsteht nur bei tatsächlicher Änderung

Die Schreibstelle kennt den Bestandszustand. Ein Schreibvorgang, der ihn nicht verändert (dieselbe
Albumentscheidung erneut gesetzt, eine nicht vorhandene zurückgenommen, dieselbe Motivkorrektur
erneut geschrieben), erzeugt **kein** Ereignis: Eine Wiederholung ist keine Korrektur, und die Story
misst Korrekturen.

Aufgezeichnet wird **jede** Albumentscheidung, gleich von welcher Ansicht aus getroffen — nach ADR
0098 Punkt 2 ist es dieselbe Geste. Der Client teilt seine Herkunft nicht mit; ein vom Client
gelieferter Kontext wäre eine Angabe, die niemand prüfen kann. Die Auszeichnung als Favorit erzeugt
**kein** Ereignis: Sie wirkt nicht auf den Entwurf und ist damit keine Aussage über einen
Modellfehler.

### 5. Jedes Ereignis trägt ein Gewicht, und die gemeinsame Entscheidung wiegt schwerer

`weight: float NOT NULL`, Vorbelegung `1.0`; ein Ereignis aus der gemeinsamen Endauswahl (ADR 0099)
trägt `FINAL_DECISION_WEIGHT > 1`. Es ist der Multiplikator dieses Ereignisses in der **Ableitung**,
nie in der Anzeige: **Die ausgewiesene Fallzahl bleibt die ungewichtete Anzahl der Korrekturen.**
Eine gewichtete Zahl als Fallzahl behauptete Korrekturen, die niemand vorgenommen hat.

### 6. Der Gewichtssatz wird persistiert und versioniert, Abwesenheit heißt Startwert

Zwei Tabellen: `quality_weight_sets` (die Fassung, mit Zeitpunkt, auslösendem Nutzer und Herkunft)
und `quality_weight_entries` (`criterion_key` als freier String, `weight`) — dasselbe Muster wie
`photo_criterion_scores`: Ein neues Kriterium erzwingt nie eine Migration.

**Es gilt die Fassung mit der höchsten `id`, und es gibt genau eine Kette.** Kein Projektbezug, kein
Nutzerbezug, kein `active`-Kennzeichen — ein zweiter Ort für „welche gilt" liefe auseinander.

**Ohne eine einzige Zeile gelten die Startwerte aus `quality.py`.** Keine Migration schreibt sie
ein; ein eingeschriebener Vorgabewert wäre von einer übernommenen Anpassung nicht mehr zu
unterscheiden (dasselbe Muster wie `Project.selection_target`). Die wirksamen Gewichte entstehen an
**einer** Stelle als Überlagerung der geltenden Fassung über die Startwerte: Ein Kriterium, das die
Fassung nicht kennt, behält seinen Startwert, statt aus der Rechnung zu fallen.

Zurücksetzen ist eine **neue Fassung** mit den Werten der Vorgängerfassung, nie ein Löschen. Die
Kette bleibt lückenlos, und „was galt wann" bleibt beantwortbar.

### 7. Eine Gewichtsänderung wirkt erst beim nächsten Durchlauf

Der Anpassungs-Endpunkt schreibt die neue Fassung und **sonst nichts** — insbesondere löst er weder
`rebuild_run_selection` noch `rebuild_run_grouping` aus. Das ist der bewusste Gegensatz zu
`PUT /projects/{id}/selection-target`, das synchron neu rechnet: Dort ändert sich eine Zahl *dieses*
Projekts, hier eine Grundlage *aller* Projekte, und ein laufender Entwurf soll sich nicht unter der
Hand bewegen. Gelesen werden die Gewichte an genau der Stelle, an der heute die Konstante steht, und
**einmal je Lauf**; der Lauf hält die benutzte Fassung an seiner Zeile fest.

### 8. Das Ableitungsverfahren: gewichtete Vorzeichenabstimmung mit Schrumpfung

Kein Training, kein Modellaufruf, keine Optimierung — eine Auszählung über Paarvergleichen. Für
jedes Paar („der Nutzer zog `B` dem `A` vor") und jedes Kriterium `k`, dessen Wert **auf beiden**
Fotos vorliegt, stimmt `k` mit dem Gewicht des Ereignisses ab: zustimmend bei `v_k(B) > v_k(A)`,
ablehnend bei `<`, gar nicht bei Gleichstand. Daraus

    zustimmung_k = (Σ zustimmend − Σ ablehnend) / (Σ zustimmend + Σ ablehnend)  ∈ [−1, 1]
    w_k = startwert_k · (1 + FEEDBACK_WEIGHT_SPAN · zustimmung_k · n_k / (n_k + PRIOR_STRENGTH))

`n_k` ist die gewichtete Stimmenzahl. Der letzte Faktor ist eine **Schrumpfung gegen die
Neutrallage**: Bei `n_k = 0` ergibt sich exakt der Startwert, und wenige Korrekturen bewegen wenig.
Ohne ihn schlüge der dritte Austausch voll auf die Gewichte durch.

Verglichen werden ausschließlich **Vorzeichen**, nie Beträge: Ein Kriterium mit gestauchtem
Wertebereich wird dadurch nicht benachteiligt, und die Ableitung braucht keine Normierungsannahme
über die Kriterien hinweg. Ein durchgängig widersprechendes Kriterium wird **abgewertet, nie
invertiert** — es hört auf mitzureden, statt seine Aussage umzudrehen: `local_correction`
renormiert auf die Summe der Gewichte und kennt kein Vorzeichen. Aus derselben Renormierung folgt,
dass nur die **Verhältnisse** der Gewichte wirken; eine gleichmäßige Streckung aller sieben ändert
keinen Qualitätswert.

`FEEDBACK_WEIGHT_SPAN` und `PRIOR_STRENGTH` sind dokumentiert unkalibrierte Startwerte in der Klasse
von `LOCAL_CORRECTION_SPAN`. Die Sicherung gegen einen schlechten Wert ist nicht ihre Höhe, sondern
dass jede Anpassung von Hand ausgelöst, vorher angezeigt und zurücknehmbar ist.

### 9. Die zwei Tauscharten werden nie zusammengezählt

Ein Austausch **innerhalb derselben Modellstufe** ist eine Aussage über die lokalen
Qualitätskriterien, ein Austausch **über Stufen hinweg** eine über die Bewertung des Modells selbst.
Zusammengezählt heben sie einander auf. Deshalb: Sie werden getrennt ausgewiesen, und **nur der
gleichstufige Austausch geht in die Gewichte ein**. Ein Paar, bei dem eine der beiden Modellstufen
fehlt, ist keiner der beiden Arten zuzuordnen, wird als eigene dritte Zahl ausgewiesen und geht in
keine Gewichtsrechnung ein — nie stillschweigend einer der beiden Arten zugeschlagen.

### 10. Die Motivdiagnose bewegt keine Gewichte

Die Motiv-Fehlerfälle sind **Diagnose und nur Diagnose**. Motive tragen keine Gewichte: Ihre Stärken
werden nach ADR 0091 nie untereinander verglichen und bilden keine Rangfolge, die zu kalibrieren
wäre. Die einzige Größe, die dieses Feature bewegt, sind die sieben Qualitätskriterien-Gewichte.

## Konsequenzen

- **Der Austausch ändert seinen Schreibweg.** Die Oberfläche ruft statt zweier Bewertungsschreiber
  einen Endpunkt; ein halb ausgeführter Austausch kann danach nicht mehr entstehen.
- **Das Log wächst mit der Nacharbeit, nicht mit dem Bestand.** Es trägt Foto-Verweis, Zeitpunkt,
  Art und die eingefrorene Entscheidungslage — nie Bilddaten, nie einen Fremdtext.
- **Die Projektlöschung bekommt eine weitere Tabelle** in ihrer geordneten Löschreihenfolge; der
  Vollständigkeitswächter gegen `Base.metadata` fängt ein Vergessen. Die beiden Gewichtstabellen
  hängen an keinem Projekt und bleiben davon unberührt.
- **`quality.py` bleibt rein und DB-frei.** Die Startwerte stehen weiter dort; wer die geltende
  Fassung auflöst, ist ein eigenes Modul mit Session.
- **Die Demo-Instanz braucht Korrekturen mit Substanz.** Ohne Austausche im erzeugten Bestand zeigt
  der Diagnoseabschnitt dort dauerhaft seinen Nullzustand, und kein Test würde rot.
- **`docs/architecture.md`** bekommt die drei neuen Tabellen, den Austausch-Endpunkt und die
  Diagnose-Endpunkte im jeweils betroffenen Pull Request. `docs/setup.md` bleibt unberührt — keine
  neue Umgebungsvariable, kein neuer Setup-Schritt, kein neuer Dienst.
