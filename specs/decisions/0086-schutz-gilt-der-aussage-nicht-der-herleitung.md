# 0086 - Der Schutz gilt der Aussage, nicht ihrer Herleitung — und ein Inhalts-Kriterium im Review

**Status:** Accepted
**Datum:** 2026-09-11
**Löst teilweise ab:** ADR
[`0079`](./0079-doku-ballast-eine-regel-an-einer-stelle-richtwerte-statt-gate.md), Abschnitt 1
(Spiegelstrich „das Geschützte") und Abschnitt 2 (der Satz über das fehlende
`review-*`-Kriterium). Die übrigen fünf Abschnitte von 0079 gelten unverändert.
**Bezug:** [Issue #411](https://github.com/TheRealKoller/photosort/issues/411), Spec
[`../features/0411-doku-im-code.md`](../features/0411-doku-im-code.md)
**Umfang:** rund 137 statt der Richtwert-100 Zeilen, weil Abschnitt 1 den neuen Schutztext
wörtlich trägt — er *ist* die Regel und geht in keiner Zusammenfassung auf.

## Kontext

ADR 0079 hat die Doku-Ballast-Regel gesetzt und die einmalige Verdichtung angestoßen. Zwei
Stellen tragen nicht.

**Der Schutz ist zu weit.** 0079 schützt „Invarianten, Zusicherungen und bewusste Abweichungen".
Die Prüffrage dazu wurde in Spec 0397 als geschlossenes Vokabular formuliert (`muss`, `darf
nicht`, `nie`, `immer`, `bewusst`, `sonst`, `Grund:` …). Diese Wörter stehen in nahezu jedem
Doku-Block — und weil sie eine *Zeile* markieren statt einer *Aussage*, deckt der Schutz den
gesamten Absatz mit, in dem sie steht: Abwägung, Vorfall, Messung, verworfene Alternative.

**Für Code fehlt der wiederkehrende Prüfpunkt.** 0079 Abschnitt 3 verankert die Regel an zwei
Stellen — beide für *Dokumente* (`spec-writer`, `architect`). Wer Code schreibt, durchläuft keinen.
Gemessen am Bestand (11.09.2026, 159 Nicht-Test-Quelldateien, 24.834 nicht-leere Zeilen): 8.671
Doku-Zeilen (34,9 %), 110 Dateien über dem Richtwert von 25 %, 497 Verweiszeilen. Das Backend
steht dabei bei 38,9 % — **nach** der abgeschlossenen Verdichtung aus PR #410. Eine Momentaufnahme
ohne Prüfpunkt wächst nach.

## Entscheidung

### 1. Geschützt ist die Aussage, nicht ihre Herleitung

Ersetzt den Spiegelstrich „das Geschützte" aus 0079 Abschnitt 1. Geschützt — und von jedem Kürzen
ausgenommen — ist eine Zusicherung, Invariante oder bewusste Abweichung in drei Teilen:

**was gilt oder nicht gelten darf**, **wofür es gilt** (Bereich, Bedingung) und **was bei
Verletzung passiert**, sofern das nicht offensichtlich ist. Diese drei bleiben vollständig, auch
wenn der Block dadurch jeden Richtwert überschreitet.

**Nicht geschützt, auch nicht innerhalb eines geschützten Blocks:** die Abwägung gegen verworfene
Alternativen; der Vorfall, aus dem die Regel entstand (Datum, Review-Fund, „früher stand hier");
die Messung, die zu ihr führte; die Wiederholung derselben Aussage in anderen Worten; der Verweis
auf Spec/ADR/PR/Issue, der nur belegt, dass es die Regel gibt.

**Bei einer Sicherheitsauflage gehört das Angriffsmodell zu *wofür*.** Der benannte Angriff
(`alg: none`, Broken Object-Level Authorization, User-Enumeration …) und die eine dadurch
untersagte Alternative sind der Bereich, für den die Auflage gilt — nicht ihre Herleitung; sie
bleiben stehen, der belegende Spec-/ADR-Verweis fällt. Ein Test ersetzt eine solche Auflage nur,
wenn er beim Entfernen des Schutzes rot wird; ist das nicht am Bestand nachgewiesen, bleibt sie in
voller Aussage.

**Ein Signalwort macht eine Zeile nicht geschützt.** `muss`, `nie`, `bewusst`, `Grund:` und ihre
Geschwister markieren die Stelle, an der die Frage zu stellen ist — nicht ihre Antwort. Die Frage
lautet: Steht hier die Regel, oder steht hier, wie man auf sie kam?

**Erzwingt ein Test die Zusicherung, ersetzt er ihre Wiederholung.** Der Kommentar nennt sie dann
in einem Satz und nennt den Test. Ohne nachgewiesenen Test bleibt sie in voller Aussage stehen —
ein Testverweis, der ins Leere zeigt, löscht die Aussage ersatzlos.

**Ein Verweis auf eine Testdatei oder einen Testknoten ist kein belegender Verweis.** Er sagt, was
bei Verletzung passiert, und ist damit geschützt. Der Verweis-Schnitt erfasst Verweise auf
`specs/`, `decisions/`, PR- und Issue-Nummern — Testverweise nicht.

### 2. Ein Inhalts-Kriterium im Review, weiterhin kein Längen-Gate

Ersetzt den Satz „Es entsteht **kein** CI-Check, **kein** Test und **kein** `review-*`-Kriterium"
aus 0079 Abschnitt 2 — aber nur für seine Inhaltshälfte. Die Längenhälfte gilt unverändert und
absolut: **Nichts weist eine Änderung allein wegen ihrer Länge zurück.**

Der Ort ist `.claude/skills/review-tests/SKILL.md`, Prüfkatalog Punkt 2 („Abweichungen von
Code-Konventionen"). Dieser Skill trägt das Kriterium bereits — heute nur für Skill- und
Agenten-Dateien („keine rein historischen ADR-/Spec-Verweise", Abschnitt „Statischer
Konsistenz-Check"). Es wird auf Doku-Blöcke im Code ausgeweitet. Kein neuer `review-*`-Skill, kein
CI-Job, kein Wächtertest, keine zweite Regelstelle: geprüft wird gegen den Konventions-Punkt in
`CLAUDE.md`. Ein Befund lautet nie „zu lang", sondern nennt Inhaltsklasse und Zeile.

### 3. Zwei geschlossene Aufnahmekriterien statt „der gesamte Produktivcode"

Gegenstand der Aufräumarbeit sind genau zwei gemessene Mengen, nicht jede Datei:

- **A — Verweis-Schnitt:** jede Nicht-Test-Quelldatei mit mindestens einer Verweiszeile im
  Doku-Block. Heute 114 Dateien, 497 Zeilen.
- **B — Doku-Blöcke:** jede Nicht-Test-Quelldatei mit Doku-Anteil ≥ 35 % **und** ≥ 60 nicht-leeren
  Zeilen. Heute 44 Dateien, 5.548 Doku-Zeilen.

Alles darunter ist nicht Gegenstand. Ohne diese Grenze ist die Story nie fertig, und die Liste
wird mit jeder Lesestunde länger statt kürzer. Es entsteht **keine Zielgröße** für eine
prozentuale Reduktion: Eine Datei, an der nichts zu entfernen ist, bleibt unverändert.

### 4. Vier Pull Requests, in dieser Reihenfolge

Die Reihenfolge ist Teil der Entscheidung: die Regel vor ihrer Anwendung, der mechanische Schnitt
vor dem urteilenden, der nie erreichte Bereich vor dem schon einmal bearbeiteten.

1. **Regel** — Spec, diese ADR, `CLAUDE.md`, `review-tests`. Keine Code-Datei.
2. **Verweis-Schnitt** (Menge A), Backend und Frontend zusammen. Mechanisch auffindbar.
3. **Doku-Blöcke Frontend** (Menge B, `frontend/`) — der ausgelassene Bereich.
4. **Doku-Blöcke Backend** (Menge B, `backend/`).

Das geht über die Zwei-PR-Ausnahme aus 0079 Abschnitt 7 und über ADR
[`0045`](./0045-spec-writer-legt-feature-branch-an-ein-pr-pro-story.md) hinaus. Grund: 8.671
Doku-Zeilen sind in einem Diff nicht mehr Datei für Datei beurteilbar — und das Review ist die
einzige Stelle, an der ein irrtümlich gelöschter Invariantensatz noch auffällt.

### 5. Nachvollziehbar je Datei, im PR-Body

Der PR-Body trägt eine Zeile **je geänderter Datei**: Datei → entfernte Inhaltsklasse(n) →
Doku-Zeilen vorher/nachher. Bei einem entfernten Verweis zusätzlich, wo der Inhalt weiterhin steht.
Commits werden je Bereich und Inhaltsklasse geschnitten; der Commit-Body nennt beide. Eine Datei im
Repository, die das festhält, entstünde genau aus dem, was die Regel verbietet.

## Begründung

- **Drei Teile statt eines Vokabulars:** „was / wofür / was sonst" ist am Text entscheidbar und
  schließt den Absatz drumherum nicht mit ein. Ein Wortlisten-Schutz trifft eine Zeile und schützt
  dadurch einen Absatz.
- **`review-tests` statt eines Prüfpunkts in `developer.md`:** Die Herleitung des eigenen Blocks
  wirkt seinem Autor stets nötig. Der Blick von außen auf den Diff ist die Stelle, an der das
  auffällt — und der Skill trägt dasselbe Kriterium für Skills/Agenten schon nachweislich.
- **Kein Wächtertest für den Verweis-Schnitt:** Ob ein Verweis funktional nötig ist, ist nicht
  mechanisch entscheidbar. Ein Test bräuchte eine Ausnahmeliste, die mit jedem berechtigten
  Verweis wächst, und erzöge zum Umschreiben des Verweises statt zum Weglassen.

## Konsequenzen

- **`CLAUDE.md`**, Konventions-Punkt „Doku-Ballast": der Schutzsatz wird durch Abschnitt 1 ersetzt;
  der Satz über das fehlende Gate trennt Länge (unverändert absolut) von Inhalt (Abschnitt 2).
- **`.claude/skills/review-tests/SKILL.md`:** Prüfkatalog Punkt 2 bekommt das Kriterium.
- **ADR 0079** bekommt eine Kopfzeile `**Teilweise abgelöst:**`; ihr Entscheidungstext bleibt
  unangetastet.
- **Kein Effekt auf `.github/workflows/`, die übrigen `review-*`-Skills und die Testsuiten.** Die
  PRs 2 bis 4 dürfen kein Verhalten ändern und keine Testdatei anfassen.
- Der Richtwert von 25 % wird von vielen Dateien weiter überschritten werden. Das ist kein Mangel
  dieser Entscheidung: Was nach Abschnitt 1 bleiben muss, bleibt.
