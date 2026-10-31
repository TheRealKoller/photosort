# 0561 - Keine Altdaten nach Nutzerwechsel

**Status:** Implemented ([PR #596](https://github.com/TheRealKoller/photosort/pull/596))
**Erstellt:** 2026-10-31
**Bezug:** [#561](https://github.com/TheRealKoller/photosort/issues/561)

## Ziel

Am gemeinsam genutzten Gerät wechseln sich mehrere Familienmitglieder im selben Browser ab. Nach einem Nutzerwechsel — Abmelden oder abgelaufene Sitzung — darf im aktiven Tab kein einziger Rest der vorherigen Sitzung mehr sichtbar sein: keine persönliche Zahl, kein Vorschlag, keine Kennzeichnung, die noch vom vorherigen Nutzer stammt. Heute kann das kurz auftreten, weil der In-Memory-Cache den Nutzerwechsel überlebt: Bis die Daten des neu angemeldeten Nutzers geladen sind, erscheinen noch die des vorherigen. Damit wird am gemeinsamen Gerät die Zusage „die eigene Bewertung hat immer Vorrang“ verletzt.

## User Story

Als Nutzer am gemeinsam genutzten Gerät möchte ich, dass nach dem Abmelden oder nach einem Sitzungsende im aktiven Tab keine Ansichten, Zahlen oder Kennzeichnungen des vorherigen Nutzers mehr erscheinen, sobald ich mich anmelde — damit ich ausschließlich meine eigenen persönlichen Angaben sehe und meine Angaben dem anderen Familienmitglied nicht erscheinen.

## Akzeptanzkriterien

- [ ] Meldet sich im aktiven Tab ein Nutzer an, nachdem zuvor ein anderer Nutzer sich dort abgemeldet hat, sieht er zu keinem Zeitpunkt eine Ansicht, Zahl oder Kennzeichnung, die noch vom vorherigen Nutzer stammt — auch nicht kurzzeitig, bis seine eigenen Daten geladen sind.
- [ ] Dasselbe gilt, wenn eine Sitzung abläuft und danach derselbe oder ein anderer Nutzer sich erneut anmeldet: Es erscheinen keine Überbleibsel der vorherigen Sitzung.
- [ ] Die Zusage gilt für alle Stellen, die persönliche oder von der Identität abhängige Angaben zeigen — insbesondere persönliche Vorschläge, persönliche Zählwerte (z. B. „Deine Eingriffe“) und persönliche Statistikwerte.
- [ ] Der Wechsel wirkt unabhängig davon, welche beiden Nutzer beteiligt sind, nicht nur für ein bestimmtes Nutzerpaar.
- [ ] Ein frisch angemeldeter Nutzer beginnt im aktiven Tab stets in einem Zustand, in dem ausschließlich seine eigenen Daten erscheinen.
- [ ] Der Fall „zweiter, weiterhin offener Tab“ liegt außerhalb des Umfangs dieser Story und wird hier nicht gefordert.

## Datenmodell-Bezug

Keine Änderung am Datenmodell, keine Migration. Rein frontendseitige Änderung des In-Memory-Cache-Lebenszyklus.

## Architektur / Umsetzung

Der React-Query-Cache wird an den beiden Sitzungsende-Punkten — Abmelden und 401/Sitzungsablauf — vollständig geleert (`queryClient.clear()`), und zwar dort, wo bereits heute das Token gelöscht wird. Kein neues Muster: das bestehende `clearToken()`-Paar (Logout-Handler + `UNAUTHORIZED_EVENT`-Kette) wird um die Cache-Leerung ergänzt.

- **Leeren über `queryClient.clear()`**, nicht `removeQueries()`/`resetQueries()`. Der Bug hängt an Einträgen mit `gcTime: Infinity` (insbesondere `useMotifs`, `staleTime`/`gcTime` beide `Infinity`): `clear()` entfernt den Cache bedingungslos inklusive solcher „unvergänglicher“ Einträge.
- **Zugriff über `useQueryClient()`**, nicht über einen Export des Modul-Singletons aus `main.tsx`. Beide Leerstellen liegen in React-Komponenten bzw. -Hooks (`AppShell`, `useUnauthorizedRedirect`); ein Singleton-Export wäre mit einem Importzyklus behaftet und machte `api/client.ts` zum Non-React-Konsumenten des Clients.
- **Abmelden:** in `AppShell.handleLogout` (`frontend/src/App.tsx`), `const queryClient = useQueryClient()` ergänzen, `queryClient.clear()` unmittelbar neben `clearToken()`, **vor** `navigate('/login')`.
- **401/Sitzungsablauf:** im Handler von `useUnauthorizedRedirect` (`frontend/src/auth/useUnauthorizedRedirect.ts`) — nicht in `api/client.ts`. Der Hook ist der einzige React-seitige Listener des `UNAUTHORIZED_EVENT` und deckt damit beide 401-Pfade (`apiFetch` und `apiFetchBlob`) mit genau einer Änderung ab. `clear()` **vor** `navigate('/login', …)`.
- **`useMotifs.ts`:** nur Kommentar-Korrektur — die Behauptung „die Invalidierung erfolgt implizit beim Login-Wechsel, weil dabei der gesamte QueryClient neu aufgebaut wird“ ist falsch und wird korrigiert.
- **Unverändert:** `frontend/src/main.tsx`, `frontend/src/api/client.ts`.

Datenfluss: Beim erneuten Anmelden mountet der geschützte Baum auf leerem Cache; `useQuery`-Hooks feuern frisch mit dem neuen Token. Da die beiden Sitzungsende-Punkte die einzigen Token-Löschstellen sind, ist Akzeptanzkriterium 5 transitiv erfüllt — ein zusätzliches `clear()` beim Login ist nicht nötig. Ein In-Flight-Request mit altem Token wird dadurch geschlossen, dass `clear()` die Queries samt Observer entfernt und die Navigation den geschützten Baum entmountet.

Keine neue ADR: ADR [`0004`](../decisions/0004-frontend-app-shell.md) deckt die Richtung bereits; die Story korrigiert den dort angekündigten Cache-Lebenszyklus an der Session-Grenze. Keine `docs/architecture.md`-Änderung.

## UI/UX

Nicht relevant — keine sichtbare Oberflächenänderung, kein neues Element, kein neues Layout. Das veränderte Verhalten ist das *Ausbleiben* alter Daten, das selbst nicht sichtbar ist.

## Security

Sicherheitsrelevant, kein Blocker. Die Story betrifft die Sitzungs-/Anzeige-Isolation zwischen den beiden Nutzern und schließt eine bereits im Sicherheitskonzept („Bekannte Lücken“) geführte Lücke. Kein klassischer Vertraulichkeitsbruch (die Bewertungen des anderen stehen ohnehin namentlich in `ratings[]`); betroffen sind der nutzerabhängige `PhotoOut.suggestion` und personenbezogene Aggregatzahlen ohne Identität im Schlüssel.

Gegenmaßnahme ist `queryClient.clear()` an den beiden Sitzungsende-Punkten. Sie ist Defense-in-Depth neben (nicht statt) der bestehenden Cache-Schlüssel-Auflage: Sie hebt die Abhängigkeit davon auf, dass jeder künftige Query-Schlüssel die Identität trägt. Die HTTP-Cache-Auflage (ETag/Cache-Control, Nutzer im Schlüssel) bleibt unberührt und weiterhin nötig.

**Nach der Umsetzung ist der „Bekannte Lücken“-Eintrag im Sicherheitskonzept zu schließen** (von „Lücke“ auf „behoben mit Spec #561: `queryClient.clear()` an beiden Sitzungsende-Punkten“), nicht vorher — das Konzept beschreibt den Ist-Zustand.

## Teststrategie

- **Integration (Schwerpunkt):** `App.test.tsx` (Logout leert Cache) und `useUnauthorizedRedirect.test.tsx` (401-Event leert Cache). Nach dem Sitzungsende liefert `queryClient.getQueryData(...)` für zuvor befüllte Keys `undefined` — Assertion über den beobachtbaren Cache-Zustand, nicht über einen Aufrufzähler. Der Test seedet eine repräsentative Query (z. B. `listProjects`) und führt eine langlebige `gcTime: Infinity`-Query, damit er rot würde, wenn nur auf Garbage Collection vertraut würde.
- **Reihenfolge als Regressionsfall:** der Cache ist im Moment der Navigation bereits leer (`clear()` vor `navigate()`).
- **Beide 401-Pfade:** der Handler in `useUnauthorizedRedirect` deckt `apiFetch` und `apiFetchBlob` ab; beides ist explizit zu prüfen.
- **E2E nicht erforderlich:** keine sichtbare Oberflächenänderung; die „auch nicht kurzzeitig“-Zusage folgt deterministisch aus der Aufrufreihenfolge.
- Das Testkonzept (`specs/architecture/0002-testkonzept.md`) ist um die Sektion „Query-Client-Cache bei Sitzungsende leeren“ ergänzt.

## Entscheidungen

- `architect konsultiert (Schritt 1)`: Platzierung des Cache-Reset an den beiden Sitzungsende-Punkten, Zugriff über `useQueryClient()` statt Singleton-Export.
- `ux-ui-designer nicht konsultiert (Schritt 2)`: keine sichtbare Oberflächenänderung, kein `## Design`-Abschnitt im Issue-Body.
- `test-engineer konsultiert (Schritt 3)`: Teststrategie und Testkonzept-Ergänzung (siehe oben).
- `security-engineer konsultiert (Schritt 3)`: Security-Einschätzung und Schließung des „Bekannte Lücken“-Eintrags (siehe oben).

## Offene Fragen

Keine.

## Out of Scope

Der Fall „zweiter, weiterhin offener Tab“ — `queryClient.clear()` wirkt nur im eigenen Tab (eigener JS-Kontext); ein zweiter Tab bleibt ein getrenntes, bewusst nicht gelöstes Szenario.
