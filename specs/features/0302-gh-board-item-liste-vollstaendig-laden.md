# 0302 - gh-board.py lädt die Board-Item-Liste vollständig

**Status:** Accepted
**Erstellt:** 2026-08-31
**Bezug:** [GitHub-Issue #302](https://github.com/TheRealKoller/photosort/issues/302), [ADR 0043](../decisions/0043-spec-nummer-gleich-issue-nummer-sync-tool-entfaellt.md) (dort als bekannte, akzeptierte Grenze aufgeführt), [Spec 0262](./0262-github-project-sync-tool-entfernen.md) (Ursprung von `scripts/gh-board.py`)

## Ziel

`scripts/gh-board.py` löst Board-Items über die Issue-Nummer auf und holt dafür die Item-Liste mit einem hart kodierten `--limit 100`. Diese Grenze ist in ADR 0043 ausdrücklich als bekannt und akzeptiert vermerkt — mit der Begründung, das Board habe "heute ~70 Items". Diese Annahme trägt nicht mehr: "PhotoSort Roadmap" hat inzwischen 106 Items.

Die Folge ist ein stilles Abschneiden mit irreführender Fehlermeldung. Jedes Issue jenseits der ersten 100 Items ist für `set-status`, `set-priority` und `show-status` unsichtbar und wird als `Issue #NNN ist kein Item des Boards 'PhotoSort Roadmap'` gemeldet, obwohl es im Board steht. Konkret aufgetreten beim Refinement von Issue #296 (Position 101); ebenso betroffen waren #297 (102) und #301 (106).

Das ist kein Randfall, sondern blockiert genau die zuletzt angelegten Issues — also immer die, an denen gerade gearbeitet wird — und damit `capture`, `refinement`, `spec-writer` und `ship-feature`. Mit jedem weiteren Issue wächst der blockierte Anteil.

## Akzeptanzkriterien

- [ ] Ein Issue wird unabhängig von seiner Position im Board über die Issue-Nummer aufgelöst; die feste Obergrenze von 100 Items entfällt.
- [ ] Liefert `gh project item-list` weniger Items als es unter `totalCount` meldet, wird die Liste mit der gemeldeten Gesamtzahl genau einmal nachgefordert.
- [ ] Ist die gelieferte Liste vollständig, findet keine zweite Abfrage statt (kein zusätzlicher `gh`-Aufruf im Normalfall).
- [ ] Bleibt die Liste auch nach der Nachforderung unvollständig, bricht die Operation mit einer Fehlermeldung ab, die gelieferte und gemeldete Anzahl benennt — statt ein vorhandenes Issue fälschlich als "kein Item des Boards" zu melden.
- [ ] Die Fehlermeldung für ein tatsächlich nicht im Board befindliches Issue nennt die 100er-Grenze nicht mehr, da sie nicht mehr existiert.

## Datenmodell-Bezug

Keine Änderung. Reines Tooling-Script, kein Anwendungs-Datenmodell betroffen.

## Architektur / Umsetzung

Kein architektonischer Neuentwurf — das Abrufmuster bleibt `gh project item-list --format json`, nur die Vollständigkeit wird sichergestellt.

**Gewählter Ansatz — selbstkorrigierendes Nachfordern statt größerer Magic Number:** `gh project item-list --format json` liefert neben `items` immer auch `totalCount` mit der echten Gesamtzahl des Boards, unabhängig vom gesetzten `--limit`. Damit ist ein Abschneiden am Rückgabewert selbst erkennbar, statt an einer Schätzung über die künftige Board-Größe. Ein bloßes Anheben des Limits (etwa auf 1000) wurde verworfen: es verschiebt dasselbe stille Versagen nur in die Zukunft und ist genau der Fehler, der schon einmal gemacht wurde.

**Betroffene Dateien:**
- `scripts/gh-board.py` — neue Konstante `ITEM_LIST_START_LIMIT`; `_item_list()` in einen wiederverwendbaren `_fetch_items(limit)` (liefert Items und `totalCount`) und die Vollständigkeitslogik aufgeteilt; Fehlermeldung in `find_item()` bereinigt.
- `scripts/tests/test_gh_board.py` — `FakeGh` bildet `--limit` realistisch ab; vier neue Tests.

**Entwurfsentscheidungen:**
1. **`ITEM_LIST_START_LIMIT = 200`** ist ein Startwert, kein Deckel: er hält den Normalfall bei genau einem `gh`-Aufruf, und wird er überschritten, korrigiert das Nachfordern das Ergebnis. Ein zu klein gewordener Startwert kostet damit nur einen zweiten Aufruf, nie Korrektheit.
2. **Genau eine Nachforderung, danach harter Fehler.** Keine Schleife: die zweite Abfrage fordert exakt die gemeldete Gesamtzahl an: eine dritte könnte nur bei einer Board-Änderung mitten im Lauf nötig werden, und dann ist Abbrechen mit klarer Meldung ehrlicher als weiteres Nachladen. Entscheidend ist, dass eine unvollständige Liste nie stillschweigend durchgereicht wird — genau daran ist der ursprüngliche Fehler so lange unbemerkt geblieben.
3. **Keine ADR-Änderung.** ADRs sind nach Annahme unveränderlich (CLAUDE.md). ADR 0043 nennt die 100er-Grenze als bewusst in Kauf genommene Einschränkung unter einer Annahme über die Board-Größe, die nicht mehr gilt; diese Spec hebt die Einschränkung auf, ohne die Entscheidung selbst zu berühren. Die Auflösungsstrategie (Item-Suche über die Issue-Nummer statt zwischengespeicherter `item_id`) bleibt unverändert.

**ADR-Bedarf:** Keine neue ADR — keine neue Technologie, keine neue Abhängigkeit, keine Datenmodell-Änderung.

**`docs/`:** Keine Aktualisierung nötig — weder Architektur noch lokales Setup ändern sich; die 100er-Grenze war ausschließlich im Script und in ADR 0043 vermerkt, nicht in `docs/`.

## UI/UX

Nicht betroffen — Kommandozeilen-Werkzeug ohne Oberfläche. Die einzige nutzersichtbare Änderung ist die bereinigte Fehlermeldung.

## Security

`security-engineer` nicht konsultiert: keine neue Eingabequelle, keine Auth-Änderung, keine veränderte Datensichtbarkeit. Es werden dieselben Board-Daten über denselben authentifizierten `gh`-Aufruf gelesen, lediglich vollständig statt abgeschnitten.

## Teststrategie

`specs/architecture/0002-testkonzept.md` unverändert — bestehender Testtyp (Script-Tests gegen ein injiziertes `run`-Callable, kein Netzwerk, kein echtes `gh`).

**Voraussetzung im Test-Fake:** `FakeGh` ignorierte `--limit` bisher vollständig und gab stets alle Items zurück. Genau deshalb konnte der Fehler unbemerkt bleiben — kein Test konnte ihn überhaupt ausdrücken. Der Fake schneidet jetzt bei `--limit` ab und meldet unter `totalCount` weiterhin die volle Anzahl, wie das echte `gh` es tut. Zusätzlich bildet `item_list_hard_limit` den Fall ab, dass `gh` ein höheres Limit nicht bedient.

**Neue Testfälle:**
- Regression: Bei 106 Items werden Einträge jenseits der ersten Seite gefunden (der reale Fall von #296).
- Eine vollständig gelieferte erste Seite löst keine zweite Abfrage aus.
- Eine abgeschnittene Liste wird genau einmal nachgefordert, und zwar mit der gemeldeten Gesamtzahl.
- Bleibt die Liste trotz Nachforderung unvollständig, ist das ein `BoardError`, der gelieferte und gemeldete Anzahl nennt.
