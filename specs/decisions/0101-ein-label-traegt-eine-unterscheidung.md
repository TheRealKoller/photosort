# 0101 - Ein Label trägt eine Unterscheidung, keinen Allgemeinzustand

**Status:** Accepted
**Datum:** 2026-09-14
**Bezug:** [GitHub-Issue #464](https://github.com/TheRealKoller/photosort/issues/464), Spec 0464

ADR [`0085`](./0085-bereich-als-label-mit-geschlossenem-vorrat.md) gilt unverändert weiter: Form,
Vorrat und Präfixbindung der `bereich:*`-Label sind von dieser Entscheidung nicht berührt. Sie
regelt, *welche* Label es überhaupt geben darf, nicht wie ein einzelner Vorrat aussieht.

## Kontext

Ein Issue entsteht auf zwei Wegen — über die Erfassung im Chat und über eine Vorlage auf GitHub.
Beide Wege vergeben ein Typ-Label, und sie vergeben verschiedene: `idee` hier, `feature` plus
`needs-spec` dort. Dasselbe Anliegen trägt damit je nach Eingangskanal unterschiedliche Etiketten.

Keines der drei wird ausgewertet: Kein Ablauf liest sie, kein Board-Filter nutzt sie, und der
Bearbeitungsstand, den `needs-spec` andeutet, ist bereits ein Status auf dem Board. `idee` und
`feature` benennen zudem den Zustand, in dem jedes Issue beginnt — eine Aussage, die für alle
gilt, unterscheidet nichts.

## Entscheidung

**Ein Label wird genau dann vergeben, wenn seine Aussage nicht ohnehin für jedes Issue gilt.** Ein
Zustand, den jedes Issue teilt, wird nicht etikettiert. Ein Bearbeitungsstand wird nicht
etikettiert, solange das Board ihn als Status führt.

Daraus folgt für den Typ eines Issues: Er ist genau im Defektfall ein Label — `bug`. Jedes andere
Issue trägt **kein** Typ-Label, nicht ein anderes.

Der Labelraum besteht damit aus drei Klassen:

- `bug` — hier ist etwas kaputt, im Unterschied zu: hier soll etwas entstehen.
- `bereich:*` — welche Seite des Projekts betroffen ist (Vorrat und Form: ADR 0085).
- `approved-for-agent` — die Freigabe für die künftige Hintergrund-Automatisierung.

**Ein viertes Label kommt nur über eine ADR hinzu, die es gegen das Kriterium oben prüft.** Ohne
diese Schranke wächst der Labelraum an genau der Stelle, an der er entstanden ist: beim Erfassen,
aus dem Wunsch heraus, etwas einzuordnen. Ein folgenloses Label kostet bei jedem Erfassen eine
Entscheidung und liest sich später wie eine Information.

**Was das Repositorium hält und was nicht.** Repo-seitig zugesichert ist, dass keine lebende
Anweisung eines der entfallenen Label setzt oder verlangt; das trägt ein Wächtertest. Welche
Label auf GitHub existieren, ist Zustand außerhalb des Repositoriums — er wird einmal hergestellt
und als Messung ausgewiesen, nicht in einen Test gegossen, der ihn nicht erreichen kann.

## Konsequenzen

- Beim Erfassen entfällt die Einordnung „Idee oder Bug" als eigener Schritt; zu klären bleibt
  allein, ob etwas kaputt ist.
- `idee`, `feature` und `needs-spec` werden auf GitHub gelöscht. Das entfernt sie von allen
  Issues, die sie tragen; welches Issue welches der drei trug, ist danach nicht mehr ablesbar.
  Das ist gewollt — die Angabe trug keine Aussage, die sich später auswerten ließe.
- Die GitHub-Issue-Vorlage für Anforderungen vergibt gar kein Label mehr. Ein Anliegen, das doch
  ein Defekt ist, kommt über die Bug-Vorlage oder bekommt `bug` beim Schärfen.
- ADRs, die eines der drei Label beschreibend erwähnen, bleiben unverändert. Sie beschreiben den
  Stand ihrer Zeit; ein Rückschreiben machte aus einer Entscheidung eine Behauptung über heute.
