# 0099 - Die Endauswahl: abgeleitet aus beiden Entwürfen, überschrieben von der Projektentscheidung

**Status:** Accepted
**Datum:** 2026-09-13
**Bezug:** Spec [`features/0431-endauswahl-gemeinsam.md`](../features/0431-endauswahl-gemeinsam.md),
ADR [`0098`](./0098-album-entwurf-aus-vorschlag-und-eigener-entscheidung.md) (die beiden Entwürfe, auf
denen die Endauswahl aufsetzt), ADR
[`0097`](./0097-auswahl-mit-richtwert-kontingente-je-event-und-motivgefuehrte-vergabe.md) (der
lauf-globale Vorschlag), ADR
[`0071`](./0071-kuratierung-stabile-auswahl-ohne-backfill-und-einsehbarer-vorrat.md)
(Entscheidung 3: verworfen ist ein Anzeigezustand, kein Filterkriterium)

## Kontext

Nach ADR 0098 hat jeder der beiden Nutzer einen abgeleiteten Album-Entwurf, und keiner sieht den des
anderen. Es gibt damit zwei Meinungen, aber kein Album — und keine Menge, die ein Export nehmen
könnte. Beide Entwürfe gehen dabei vom **selben** Vorschlag aus; ein Unterschied entsteht nur dort,
wo mindestens einer eine eigene Albumentscheidung getroffen hat.

## Entscheidung

### 1. Gespeichert wird nur die ausdrückliche Entscheidung, die Endauswahl selbst ist abgeleitet

Mit `im Entwurf(u, p) = (Albumentscheidung(u,p) = album_worthy) ∨ (vorgeschlagen(p) ∧ keine
Albumentscheidung(u,p))` und `n` = Zahl der Nutzer:

    einig_drin(p) = ∀u: im Entwurf(u, p)
    Endauswahl(p) = Entscheidung(p), falls vorhanden; sonst einig_drin(p)

Persistiert wird ausschließlich `Entscheidung(p) ∈ {aufnehmen, nicht aufnehmen}`. Daraus folgt ohne
durchsetzenden Code: Einigkeit ist eine **Vorbelegung** (sie wirkt nur, solange keine Entscheidung
vorliegt), und eine getroffene Entscheidung überlebt jede spätere Änderung eines Entwurfs und jeden
neuen Vorschlagslauf, weil beide nur in den Zweig ohne Entscheidung hineinwirken.

**Ein strittiges, noch unentschiedenes Bild gehört NICHT zur Endauswahl.** Automatische
Zugehörigkeit gibt es allein bei Einigkeit; alles andere verlangt eine Entscheidung.

### 2. „Strittig" ist Uneinigkeit ohne Entscheidung

    strittig(p) = (keine Entscheidung(p)) ∧ (0 < #{u : im Entwurf(u, p)} < n)

Die Zahl **zwei** steht an keiner Stelle im Code: „alle einig" bzw. „nicht alle einig" ist für jede
Nutzerzahl definiert und fällt bei zwei Nutzern mit der Aussage der Story zusammen. Weil beide
Entwürfe vom selben Vorschlag ausgehen, ist jedes strittige Bild eines, für das mindestens ein
Nutzer eine Albumentscheidung getroffen hat — daraus folgt die Kürze des Durchgangs, ohne dass sie
irgendwo zugesichert werden müsste.

### 3. Die Entscheidung gehört dem Projekt: eine Zeile je Foto, ohne Nutzer, ohne Lauf, ohne Verlauf

Neue Tabelle `final_selection_decisions` mit `photo_id` als **Primärschlüssel** (Muster
`photo_album_suitability`) und `included: bool`. Die Trennung von den beiden Entwürfen ist damit
strukturell: Es gibt keine Spalte, in der ein Nutzerbezug stehen könnte.

- **Kein `user_id`** — „wer angemeldet ist, spielt für die Wirkung der Entscheidung keine Rolle".
- **Kein `decided_by`** — es ist der Anfang eines Verlaufs, und ein Verlauf ist ausgeschlossen. Eine
  Spalte, die niemand liest, lädt zur Zuschreibung ein, die die Story gerade nicht will.
- **Keine Lauf-Bindung** — die Zeile hängt am Foto; genau deshalb überlebt sie einen neuen Lauf.
- **Keine Zeile bedeutet „unentschieden"**, wie bei `Rating` und `PhotoMotifCorrection`. Es gibt
  keinen Weg zurück in diesen Zustand: Es entsteht kein `DELETE`-Endpunkt. Ändern heißt den anderen
  Wert schreiben; „wieder strittig werden" ist kein Zustand, den die Story kennt.

### 4. Die drei Werte stehen am Foto, auf allen Lesepfaden

`PhotoOut` bekommt drei Felder, überall befüllt — nicht nur im neuen Zweig, aus demselben Grund wie
`RankingOut.proposed` (ADR 0098 Punkt 3): ein je Query-Modus verschiedenes `PhotoOut` wäre die
zweite, driftende Abbildung.

- `final_selection_decision: bool | null` — die persistierte Entscheidung, `null` = keine.
- `in_final_selection: bool` — das Ergebnis der Regel aus Punkt 1.
- `contested: bool` — das Ergebnis der Regel aus Punkt 2.

Die Regel selbst lebt in **genau einer** reinen, DB-freien Funktion (`album_selection.py`, Muster
`selection.py`/`events.py`); die Oberfläche bildet sie nirgends nach. Sie braucht das auch nicht:
Nach einer Entscheidung sind beide abgeleiteten Werte trivial bestimmt (`contested = false`,
`in_final_selection = Entscheidung`), der Konsenszweig wird im Frontend nie betreten.

### 5. Die Antwortmenge ist additiv — auch eine Herausnahme bleibt sichtbar

Die gemeinsame Ansicht liefert `strittig ∪ Endauswahl ∪ entschieden`. Der dritte Teil ist keine
Redundanz: Ein ausdrücklich **herausgenommenes** Bild gehört nicht zur Endauswahl und wäre ohne ihn
aus beiden Sichten verschwunden — die Entscheidung ließe sich dann nicht mehr ändern, obwohl die
Story das ausdrücklich zusagt. Es bleibt stattdessen an seiner Stelle stehen und trägt einen
Anzeigezustand, genau wie ein gestrichenes Foto im Entwurf (ADR 0071 Entscheidung 3, ADR 0098
Punkt 3). Kein Ausschluss bildet die Menge.

Ein Bild, das **beide** gestrichen haben und über das niemand entschieden hat, erscheint hier nicht.
Der Weg zurück führt über den Einzelentwurf, in dem es weiterhin steht: Nimmt einer es dort wieder
auf, wird es strittig und taucht auf.

### 6. Ein Ort, zwei Sichten, eine Abfrage — und kein Neuladen nach einer Entscheidung

Arbeitssicht („nur die Unterschiede") und Ergebnissicht („die ganze Endauswahl") sind zwei Filter
über **derselben** geladenen Antwort, kein zweiter Abruf und kein zweiter Endpunkt. Eine
Entscheidung schreibt eine Zeile und schreibt den Eintrag im bereits geladenen Zustand fort (ADR 0098
Punkt 6). Daraus folgt beides zugleich: Das entschiedene Bild verlässt die Arbeitssicht sofort, und
die Ergebnissicht ordnet sich dabei nicht neu.

### 7. Der Einzelentwurf bleibt unberührt, und das ist strukturell prüfbar

Die Endauswahl ist eine Ebene **über** beiden Entwürfen, nicht daneben. Nachweisbar an vier Stellen
statt an einer Zusicherung: `ratings` bekommt keine Spalte und `RatingStatus` keinen Wert; die neue
Tabelle hat keinen Nutzerbezug (Punkt 3); der Entwurfs-Lesepfad und der Alternativen-Endpunkt lesen
sie nicht (struktureller Wächter); und eine gemeinsame Entscheidung ändert weder die Antwortmenge
des Entwurfszweigs noch die `ratings[]` eines der beiden Nutzer.

### 8. Die Vergleichsseite entfällt ersatzlos und gibt ihren Navigationsplatz ab

`PhotoComparePage` und die Route `/projects/:id/compare` entfallen ohne Weiterleitung; das dritte
Hauptziel der Projektnavigation heißt künftig „Endauswahl" und führt auf die neue Route. Kein
Redirect, aus demselben Grund wie bei `/curate` (ADR 0098 Punkt 7): Ein zweiter Weg auf den einen
verbleibenden Ort wäre ein zweiter Ort. Die alte Seite hatte keinen eigenen Endpunkt — sie las das
Standard-Listing; backendseitig entfällt mit ihr nichts.

## Konsequenzen

- **Die drei neuen `PhotoOut`-Felder kosten zwei Abfragen je Anfrage** (die Entscheidungszeilen der
  gelieferten Fotos, die Nutzerzahl), unabhängig von der Fotoanzahl. `_to_photo_out` bekommt beide
  als **pflichtige** Parameter, damit ein vergessener Aufrufer am Typprüfer scheitert statt still
  „nicht im Album" zu antworten.
- **Die Antwort der gemeinsamen Ansicht kennt keine Seitenweise**, wie der Entwurfszweig (ADR 0098,
  Auflage S14). Ihre Obergrenze ist `Vorschlag ∪ jemals bewertet ∪ entschieden`.
- **Die Demo-Instanz wird zwischen den beiden Nutzern absichtlich uneins.** Bisher bekommen alle
  Nutzer dieselben Bewertungen; ohne einen benannten Dissens zeigte die Arbeitssicht dort dauerhaft
  „keine Unterschiede", und kein Test würde rot.
- **`project_deletion.py`** nimmt die neue Tabelle auf; der Vollständigkeitswächter gegen
  `Base.metadata` fängt ein Vergessen.
- **`docs/architecture.md`** bekommt die neue Tabelle, die zwei Endpunkte, die neue Route und den
  Wegfall der Vergleichsseite im jeweils betroffenen Pull Request.
- **Spec [`0347`](../features/0347-navigation-nebenbereich.md) (AK1) nennt „Vergleich" als drittes
  Hauptziel.** Die Spec bleibt als abgeschlossenes Dokument unangetastet; die neuere Spec ist die
  geltende Aussage, und `e2e/tests/project-nav.spec.ts` wird umgeschrieben, nicht gelöscht.
- **Der Export ([#263](https://github.com/TheRealKoller/photosort/issues/263)) findet hier seine
  Menge** und braucht dafür keine weitere Datenstruktur.
