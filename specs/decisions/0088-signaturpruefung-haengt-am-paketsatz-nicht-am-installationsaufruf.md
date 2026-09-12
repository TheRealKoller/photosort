# 0088 - Die Signaturprüfung hängt am npm-Paketsatz, nicht am Installationsaufruf

**Status:** Accepted
**Datum:** 2026-09-12
**Bezug:** [GitHub-Issue #404](https://github.com/TheRealKoller/photosort/issues/404), Spec [`0404`](../features/0404-signaturpruefung-alle-npm-paketsaetze.md)

## Kontext

`npm audit signatures` steht heute an genau einer Stelle: im `e2e`-Job, hinter dessen `npm ci`. Der
`frontend`-Job installiert ohne diesen Schritt — ausgerechnet der Paketsatz, der als einziger in
das ausgelieferte Bundle eingeht, ist ungeprüft.

Am Bestand gemessen (2026-09-12, `frontend/package-lock.json` unverändert gegen `origin/main`):
`npm audit signatures` in `frontend/` endet mit Exit 0, „audited 496 packages", **496 von 496** mit
verifizierter Registry-Signatur, **188 von 496** mit verifizierter Attestierung.

Drei Randbedingungen des Bestands, die die Bauform einschränken:

- **Ein neuer CI-Job trägt nicht.** Sein Name müsste von Hand in
  `required_status_checks.contexts` der Branch Protection nachgetragen werden und blockierte bis
  dahin nichts (ADR [`0064`](./0064-pr-titel-pruefung-eigener-blockierender-workflow.md)
  Abschnitt 6, ebenso abgewogen in ADR
  [`0080`](./0080-maschinelle-formatierung-ruff-format-und-prettier.md)).
- **`npm ci` steht nicht nur in der CI**, sondern auch in `frontend/Dockerfile` (Zeile 4), also im
  Image-Bau — derselbe Paketsatz, ein anderer Aufrufort.
- **PyYAML ist in `scripts/pyproject.toml` keine Abhängigkeit**; die bestehenden
  Workflow-Wächtertests unter `scripts/tests/` arbeiten deshalb textbasiert.

## Entscheidung

### 1. Zugesichert wird je Paketsatz, nicht je Installationsaufruf

Ein **Paketsatz** ist ein von Git verwaltetes `package-lock.json` außerhalb von `node_modules`.
Für jeden gilt: In `.github/workflows/ci.yml` existiert mindestens ein Schritt, der `npm ci` in
seinem Verzeichnis ausführt, und **jeder** solche Schritt hat als unmittelbaren Nachfolger im
selben Job einen Schritt, der `npm audit signatures` im selben Verzeichnis ausführt. Maßgeblich
ist das wirksame Arbeitsverzeichnis, gleich ob es am Schritt steht (`e2e`) oder aus
`defaults.run.working-directory` des Jobs kommt (`frontend`).

Damit ist die Regel selbsterweiternd: Ein künftiger dritter Paketsatz fällt ohne erneute
Entscheidung darunter, auch wenn er ausschließlich in einem Image-Bau installiert wird — dann
fehlt der CI-Schritt und die Prüfung wird rot.

### 2. Durchgesetzt wird sie mechanisch, durch einen Wächtertest

Neuer Test unter `scripts/tests/`, gefahren vom bestehenden Job `demo-scripts`. Die Menge der
Paketsätze wird **abgeleitet, nicht gepflegt** (`git ls-files`), und es gibt **keine
Ausnahmeliste, auch keine leere vorbereitete**. Weil der Erfolgsfall „nichts gefunden" ist, gehört
zur Zusicherung die Gegenprobe: Die Ableitung muss überhaupt etwas finden, `frontend` und `e2e`
müssen darunter sein, und an einem mutierten Textabbild des echten Workflows (Schritt entfernt,
Reihenfolge getauscht, Arbeitsverzeichnis verfälscht) muss der Befund tatsächlich anschlagen.

Gelesen wird der Workflow **textbasiert, ohne YAML-Bibliothek** — konsistent mit den drei
Nachbartests. Eine neue externe Abhängigkeit ausgerechnet in einer Lieferketten-Story wäre die
falsche Richtung.

### 3. Zwei gewöhnliche Schritte, kein neuer Mechanismus

Der `frontend`-Job bekommt einen Schritt, wortgleich benannt und formuliert wie der bestehende im
`e2e`-Job. Keine Composite Action, kein Skript unter `scripts/`, kein neuer Job: Sie
zentralisieren nur die Schreibweise und sichern nichts zu. Die Zusicherung leistet allein der
Wächter aus Abschnitt 2, und mit ihm ist die Wiederholung zweier Zeilen billiger als eine
Indirektion.

### 4. Verlangt wird die Registry-Signatur, blockierend, ohne Nachsicht

Kein `continue-on-error`, kein `if:`, kein `|| true`, keine Wiederholung, kein ausgenommenes
Paket — die drei ersten Formen lassen den Job grün melden, obwohl die Prüfung nicht greift, und
werden deshalb vom Wächter zurückgewiesen. Eine **fehlende** Signatur
ist derselbe Befund wie eine falsche — `npm audit signatures` endet in beiden Fällen mit Exit ≠ 0,
und daran wird nichts abgeschwächt. Eine Provenance-Attestierung wird **nicht** gefordert; bei 188
von 496 Paketen wäre das eine Forderung, die der Paketsatz heute nicht erfüllen kann.

Der Schritt steht unmittelbar hinter `npm ci` und damit vor Formatprüfung, Lint, Typprüfung, Test
und Build. Er liegt ausdrücklich **nicht** vor jeder Ausführung fremden Codes: `npm ci` führt
Installationsskripte der Pakete aus, bevor der Schritt überhaupt läuft.

### 5. Der Image-Bau bleibt ungeprüft, bewusst

`frontend/Dockerfile` bekommt **keinen** Signaturschritt. Er installiert denselben Paketsatz, den
der `frontend`-Job im selben Lauf prüft; der Nachweis ist also innerhalb eines CI-Laufs nicht
verloren. Was ein Schritt im Dockerfile zusätzlich kostete, ist unverhältnismäßig: Jeder
Image-Bau — auch Daniels lokaler `docker compose build` — bräuchte dann Netzzugang zur
Signatur-API der Registry und scheiterte ohne ihn. Für den lokalen Bau tragen weiterhin
Lockfile-Integritätshash und `npm ci`.

### 6. `scripts/check.sh` bleibt unverändert

Der lokale Schnellprüflauf bekommt die Signaturprüfung nicht: Er ist bewusst netzfrei und
sekundenschnell und lässt schon Tests und Build aus. Die **zehn** Aufrufe aus ADR
[`0084`](./0084-frueheres-qualitaets-feedback-ein-pruefbefehl-und-ein-pruefpunkt-je-tdd-einheit.md)
Abschnitt 2 bleiben zehn.

## Begründung

Die naheliegende Alternative zu Abschnitt 1 ist ein Wächter über **jedes `npm ci` im Repository**.
Er ist strenger, aber an der falschen Stelle: Er erzwänge einen Signaturschritt im Dockerfile
(Abschnitt 5 sagt begründet nein) und müsste in Shell- und Doku-Text zwischen einem ausgeführten
und einem bloß genannten `npm ci` unterscheiden — `scripts/check.sh` nennt den Befehl wörtlich in
einer Meldung und darf ihn genau nicht ausführen. Die Anknüpfung am Paketsatz umgeht diese
Unterscheidung vollständig und schließt dieselbe Lücke.

## Konsequenzen

- Ein dritter Paketsatz macht den `demo-scripts`-Job rot, bis ein Schritt-Paar ergänzt ist. Das
  ist die Absicht: Die Aufnahme wird entschieden, statt einzusickern.
- Die Zahl der Prüfläufe mit Fremdabhängigkeit verdoppelt sich. Eine Störung der Registry kann
  einen Pull Request rot machen, dessen Änderung damit nichts zu tun hat — derselbe Preis, der für
  den `e2e`-Job bereits bezahlt wird.
- Was diese Entscheidung nicht leistet: Sie belegt „npm hat dieses Paket signiert", nicht „dieses
  Paket stammt aus dem Quell-Repository". Gegen Kontoübernahme beim Paketautor oder eine
  kompromittierte Release-Pipeline tragen weiterhin allein Lockfile-Hash und `npm ci`.
