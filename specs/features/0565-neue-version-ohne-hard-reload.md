# 0565 - Neue Versionen ohne Strg+F5 automatisch im Browser und in der PWA

**Status:** Accepted
**Erstellt:** 2026-10-03
**Bezug:** [Issue #565](https://github.com/TheRealKoller/photosort/issues/565)

## Ziel

Nach jedem Release sehen beide Nutzer die neuen Funktionen und Fehlerbehebungen erst, wenn sie im
Browser Strg+F5 drücken. Wer das nicht weiß, arbeitet unbemerkt mit einer veralteten Oberfläche
weiter, die mit dem neuen Stand auf dem Server kollidieren kann. Künftig kommt die neue Version von
selbst an: still und ohne Zutun, beim nächsten Öffnen oder Neuladen der App.

## User Story

Als Nutzer von PhotoSort möchte ich, dass nach einem neuen Release beim nächsten Öffnen oder
Neuladen automatisch die neue Version aktiv ist, ohne Strg+F5 und ohne Unterbrechung meiner
laufenden Arbeit, damit neue Funktionen und Fehlerbehebungen bei mir ankommen, ohne dass ich etwas
über Browser-Zwischenspeicher wissen muss.

## Akzeptanzkriterien

„Neue Version“ heißt: Das geladene Einstiegs-Bundle ist dasjenige, auf das die aktuell vom Server
ausgelieferte `index.html` verweist.

- [ ] **AK1:** Nach einem Release zeigt der Desktop-Browser beim normalen Öffnen oder nach
  einfachem Neuladen (F5, ohne Strg) **beim ersten Mal** die neue Version, ohne zweites Neuladen —
  auch für Deep-Links wie `/projects/3`.
- [ ] **AK2:** Eine installierte PWA, die vollständig geschlossen und neu gestartet wird, zeigt
  beim ersten Start nach dem Release die neue Version. Ein bloßes Zurückholen aus dem Hintergrund
  gilt nicht als Neustart.
- [ ] **AK3:** In einer laufenden Sitzung löst ein Release keinen Selbst-Reload aus, auch nicht,
  wenn der neue Service Worker die Kontrolle übernimmt; Eingaben und aktuelle Ansicht (Route,
  Scrollposition) bleiben erhalten.
- [ ] **AK4:** Zur neuen Version erscheint weder Hinweis noch Banner, Dialog oder Rückfrage. Der
  Code enthält keinen Update-Prompt-Pfad (`onNeedRefresh`, `virtual:pwa-register` mit Reload,
  `location.reload` wegen eines SW-Updates).
- [ ] **AK5:** Ein Client auf Version A lädt, während der Server über B hinweg bereits C ausliefert,
  beim nächsten Öffnen oder F5 direkt C; kein Request geht an Assets von A oder B.
- [ ] **AK6:** Ohne Netz oder wenn der Server nicht innerhalb der Netz-Zeitgrenze antwortet, startet
  die App mit der zuletzt vollständig geladenen Version — HTML und Assets aus demselben Precache,
  keine gemischten Versionen, keine Browser-Fehlerseite; für `/` und Deep-Links.
- [ ] **AK7:** Beim Versionswechsel (F5 wie PWA-Neustart) bleibt die Anmeldung erhalten: keine
  Umleitung auf `/login`, `photosort_token` steht unverändert in `localStorage`.

## Datenmodell-Bezug

Keiner.

## Architektur / Umsetzung

**Ursache heute.** `vite-plugin-pwa` mit `registerType: 'autoUpdate'` (generateSW, `skipWaiting` +
`clientsClaim`) und Standard-`navigateFallback` beantwortet jede Navigation aus dem Precache des
gerade aktiven Service Workers (`frontend/vite.config.ts`). F5 liefert also die alte `index.html`
mit alten Asset-Hashes; der neue SW installiert sich erst im Hintergrund. `frontend/nginx.conf`
setzt keine `Cache-Control`-Header, sodass zusätzlich heuristisches HTTP-Caching greift.

**Ansatz: Navigation zuerst aus dem Netz, offline aus dem Precache.** generateSW bleibt, keine neue
Abhängigkeit, keine eigene Registrierung (das Plugin schleust weiterhin `registerSW.js` ein).

1. `frontend/vite.config.ts`, `workbox`:
   - `navigateFallback: null` — Navigationen kommen nicht mehr aus dem Precache.
   - Ein `runtimeCaching`-Eintrag ausschließlich für `request.mode === 'navigate'`, `handler:
     'NetworkOnly'`, `options.precacheFallback: { fallbackURL: 'index.html' }` (Precache-Schlüssel
     im erzeugten `sw.js` prüfen) und `options.plugins` mit **einem** Zeitgrenzen-Plugin.
     `networkTimeoutSeconds` ist hier nicht nutzbar: workbox-build erlaubt es nur mit `NetworkFirst`
     (`workbox-build/build/lib/runtime-caching-converter.js`).
   - Zeitgrenzen-Plugin (Objektliteral, wird von workbox-build als Quelltext in `sw.js` serialisiert
     — daher ohne Closure/Import, die 3 s als Literal im Plugin): `requestWillFetch({ request, state
     })` legt einen `AbortController` an, merkt `setTimeout(() => c.abort(), 3000)` in `state` und
     gibt `new Request(request, { signal: c.signal })` zurück; `fetchDidSucceed` und `fetchDidFail`
     löschen den Timer (sonst bräche ein langsamer Body nach 3 s ab). Der Abbruch lässt `NetworkOnly`
     scheitern, `PrecacheFallbackPlugin.handlerDidError` liefert die Precache-`index.html`.
   - Online lädt jedes Öffnen und jedes F5 die aktuelle `index.html` vom Server; sie verweist auf die
     neuen gehashten Assets. Damit ist AK5 strukturell erfüllt: Der Server hält nur einen Stand.
   - Offline/Timeout liefert der SW `index.html` aus demselben Precache wie die Assets.
   - `registerType: 'autoUpdate'` und `globPatterns` bleiben. Kein `virtual:pwa-register` mit
     Reload, kein UI-Hinweis.
2. `frontend/nginx.conf`, Cache-Header:
   - `location /assets/`: `Cache-Control: public, max-age=31536000, immutable`; `try_files … =404`
     bleibt.
   - `/index.html`, `/sw.js`, `/registerSW.js`, `/manifest.webmanifest`, `workbox-*.js` und der
     SPA-Fallback `location /`: `Cache-Control: no-cache`.

**Datenfluss nach einem Release.** Laufende Sitzung: kein Reload; der neue SW übernimmt per
`clientsClaim` im Hintergrund, die offene Seite hat ihr Bundle vollständig geladen (keine `lazy()`
bzw. dynamischen Imports im Produktivcode) und läuft weiter. Nächstes F5/PWA-Neustart: `index.html`
aus dem Netz, neue Version aktiv, Precache wird nachgezogen. Anmeldung: Token in `localStorage`
(`frontend/src/auth/token.ts`), von SW- und Cache-Wechsel unberührt.

**Keine ADR:** keine neue Technologie, kein Datenmodell, keine externe Abhängigkeit (innerhalb ADR
0001). `docs/architecture.md` erhält im PWA-Absatz einen Satz zur Navigationsstrategie.

**Restrisiken.**
- Bei langsamem Netz wartet der Start bis zur Zeitgrenze (3 s), bevor die Offline-Fassung erscheint.
- Das Zeitgrenzen-Plugin hängt am Plugin-Vertrag von Workbox (`state`, `requestWillFetch`,
  `fetchDidSucceed`/`fetchDidFail`); ein Workbox-Major-Update muss den Build-Check grün halten.
- Ein offener Alt-Tab, der nach dem Deploy ein nicht mehr vorhandenes Asset nachlädt, bekäme 404.
  Heute ausgeschlossen, weil es keine Code-Splits gibt; wer `lazy()`-Routen einführt, muss das neu
  bewerten.
- Manche Plattformen holen eine installierte PWA nur in den Vordergrund, statt sie neu zu starten;
  dann gilt die neue Version erst nach echtem Neustart (deckt sich mit AK2).

### Teststrategie

- **Build-Check (vitest, `frontend/`, Umgebung `node`):** baut mit der echten `vite.config.ts`
  programmatisch in ein Temp-Verzeichnis und prüft das erzeugte `sw.js`. Positiv: Navigationsroute
  mit `NetworkOnly`, `precacheFallback` auf einen im Precache-Manifest vorhandenen Schlüssel, ein
  Plugin mit `requestWillFetch`, `AbortController` und Zeitgrenze `3000`. Nicht geprüft wird
  `networkTimeoutSeconds` (siehe Entscheidungen).
  Negativ: keine `NavigationRoute`/`createHandlerBoundToURL` auf den
  Precache; keine Strategie `CacheFirst`/`StaleWhileRevalidate`/`NetworkFirst`; keine Route, die
  `/api` trifft. Dazu eine Prüfung über `src/**` gegen `virtual:pwa-register`, `onNeedRefresh`,
  `location.reload` (AK3/AK4).
- **nginx-Header (Compose-Check im `docker-compose-check`-Job, Muster Spec 0016):** `curl -I` auf
  `/`, `/index.html`, eine erfundene Client-Route, `/sw.js`, `/registerSW.js`,
  `/manifest.webmanifest`, eine `workbox-*.js` → `Cache-Control: no-cache`; ein echtes Asset unter
  `/assets/` → `max-age=31536000, immutable`; ein fehlendes Asset → weiter `404`; `/api/` ohne
  eigenen `Cache-Control`. Dateiliste aus dem gebauten `dist/`, Vorbedingung je Datei `200`.
- **E2E (Playwright, `e2e/tests/release-wechsel.spec.ts`, nur Projekt `desktop`):** zwei echte
  Builds A und B mit verschiedenem Einstiegs-Bundle-Hash (Vorbedingung Hash A ≠ Hash B). A laden,
  auf SW-Kontrolle warten; im Frontend-Container A durch B ersetzen und A-Assets entfernen wie ein
  realer Deploy; ein F5 → Einstiegsskript von B, kein Request an A-Assets (AK1/AK5).
  - AK3: Fenster-Marker plus Eingabe vor dem Tausch, nach `controllerchange` beide unverändert.
  - AK6: `context.setOffline(true)`, F5 auf `/` und einen Deep-Link → letzte Version ohne
    Netzfehler.
  - AK7: nach F5 auf B kein Umweg über `/login`, Token unverändert.
  - AK2-Ersatz: alle Seiten des Kontexts schließen, neue Seite im selben Kontext → B.
  - `retries: 0`, kein `waitForTimeout`; Warten nur auf SW-Zustände (`ready`, `controllerchange`);
    Tausch im `finally` auf A zurückgesetzt. Rot-Nachweis: E2E gegen die heutige Konfiguration rot.
- **Nicht automatisierbar:** echter Neustart einer installierten PWA (AK2) — manueller Blick nach
  dem ersten Release auf Desktop und installierter Mobil-PWA.
- **Testkonzept:** `specs/architecture/0002-testkonzept.md` erhält im E2E-Teil eine Sektion
  „Release-Wechsel mit Service Worker“: SW-Verhalten nur gegen ein gebautes `sw.js`, „neue Version“
  als Gleichheit Einstiegs-Bundle = Server-`index.html` mit Vorbedingung Hash A ≠ Hash B, Tausch
  entfernt alte Assets und wird zurückgesetzt, Warten auf SW-Zustände statt Zeit, Netz-Zeitgrenze
  nur als Konfigurationswert belegt.

## UI/UX

Nicht relevant: Die Story hat keine sichtbare Oberfläche; AK4 schließt jeden Hinweis ausdrücklich
aus.

## Security

Sicherheitsrelevant mit geringer Tragweite: nur Auslieferung und Caching statischer Dateien; Auth,
Token und API-Pfad bleiben unberührt.

- **Geerbte Security-Header gehen in neuen `location`-Blöcken verloren.** nginx erbt `add_header`
  nur in Blöcke ohne eigene `add_header`-Direktive. Heute setzt `frontend/nginx.conf` keine; die
  Falle betrifft künftige Header, ausgerechnet auch bei `index.html`. **Muss:** Ein Kommentar über
  dem `server`-Block hält fest, dass jeder `location`-Block mit `add_header` alle Security-Header
  wiederholen muss — oder `Cache-Control` wird über eine `map` auf `$uri` mit einem einzigen
  `add_header` auf `server`-Ebene gesetzt (robustere Variante).
- **Service Worker cached nutzerbezogene API-Antworten.** Der SW-Cache gilt pro Browserprofil,
  zwei Personen an einem Gerät sind realistisch (Cache-Schlüssel-Auflage in
  `specs/architecture/0003-securitykonzept.md`). **Muss:** Der neue `runtimeCaching`-Eintrag trifft
  ausschließlich `request.mode === 'navigate'`, nutzt `NetworkOnly`, hat keinen `cacheName` und
  schreibt in keinen Runtime-Cache. Der Build-Check sichert das ab (siehe Teststrategie).
- **`immutable` an falscher Stelle hält eine fehlerhafte `index.html` ein Jahr fest.** **Muss:**
  `immutable` steht ausschließlich in `location /assets/`, nie in `location /` oder `/api/`.
  `location /api/` erhält keinen eigenen `Cache-Control`; maßgeblich bleibt das Backend.
- **`no-cache` statt `no-store`:** zulässig — die betroffenen Dateien sind statisch, für alle
  Nutzer gleich und enthalten weder Token noch Nutzerdaten.
- **Token-Ablage:** bleibt in `localStorage`; kein Wechsel zu Cookie oder SW-Speicher, keine
  Weitergabe an den SW.

## Entscheidungen

- `NetworkOnly` + `precacheFallback` statt `NetworkFirst` mit eigenem Runtime-Cache, damit offline
  HTML und Assets immer aus demselben Precache kommen und kein nutzerbezogener Cache entsteht.
- generateSW bleibt, kein Wechsel zu injectManifest.
- Netz-Zeitgrenze für Navigationen: 3 s, umgesetzt als eigenes Plugin mit `AbortController` an
  `NetworkOnly`, weil workbox-build `networkTimeoutSeconds` nur für `NetworkFirst` zulässt.
  Verworfen: injectManifest (eigener SW, mehr Wartung für eine Zeitgrenze), Verzicht auf die
  Zeitgrenze (bricht AK6).
- AK5 wird ohne dritten Build geprüft: Der Server hält nur einen Stand, A→C ist strukturell A→B.
- E2E nur im Projekt `desktop`: SW-Verhalten hängt nicht vom Viewport ab.
- Wie Build B einen anderen Hash bekommt, entscheidet die Umsetzung (z. B. Test-Build-Argument in
  einer harmlosen Konstante); kein Versionsanzeige-Element in der UI.
- ux-ui-designer nicht konsultiert (Schritt 2): Die Story hat keinen Bezug zu einer sichtbaren
  Oberfläche; AK4 verbietet jeden Hinweis, es wird nichts angezeigt oder eingegeben.

## Offene Fragen

Keine.

## Out of Scope

- Sichtbare Versionsanzeige oder Update-Hinweis.
- Code-Splitting/`lazy()`-Routen und deren Verhalten bei offenen Alt-Tabs.
