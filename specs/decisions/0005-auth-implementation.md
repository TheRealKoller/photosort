# 0005 - Auth-Implementierung: Token-Transport und Bibliotheken

**Status:** Accepted
**Datum:** 2026-07-20

## Kontext

[`0003-auth-model.md`](./0003-auth-model.md) legt das grundsätzliche Auth-Modell fest (getrennte Konten, Argon2-Hashing, Sessions via JWT, kein Self-Signup), aber bewusst nicht die konkrete technische Umsetzung ("in der jeweiligen Feature-Spec zu klären, sobald Auth implementiert wird" — siehe dort, Abschnitt Konsequenzen). Mit der Feature-Spec "Auth-Implementierung" (0006) wird diese Umsetzung jetzt konkret, und drei Punkte daraus sind neue externe Abhängigkeiten bzw. eine schwer revidierbare, cross-cuttende Sicherheitsentscheidung — beides laut `CLAUDE.md` architekturrelevant und daher hier statt nur im Spec-Text festgehalten:

1. Welche Python-Bibliotheken Argon2-Hashing und JWT-Handling implementieren (neue externe Abhängigkeiten in `backend/pyproject.toml`).
2. Wie das JWT vom Frontend zum Backend transportiert und dort gespeichert wird — diese Entscheidung war in [`specs/features/0002-manual-categorization.md`](../features/0002-manual-categorization.md) ("CSRF: abhängig davon, wie die Auth-Spec das JWT überträgt") und [`specs/features/0005-minimal-project-frontend.md`](../features/0005-minimal-project-frontend.md) ("CSRF/Token-Transport: noch keine Auth-Entscheidung getroffen") explizit als offene, auf diese Spec verschobene Frage geführt.

Beide Punkte sind technische Entscheidungen *innerhalb* der bereits akzeptierten Richtung aus ADR 0003 (kein neues Grundmodell), aber mit spürbaren Folgekosten (Abhängigkeitspflege, CSRF-Architektur quer über mehrere Specs) — daher als eigene, ergänzende ADR statt nur im Spec-Text vergraben.

## Entscheidung

### Bibliotheken (`backend/pyproject.toml`)

- **Passwort-Hashing:** `argon2-cffi` (Modul `argon2`, `PasswordHasher`). Direkter, gepflegter Binding der Argon2-Referenzimplementierung — keine Umweg-Abstraktion wie `passlib` nötig, da nur ein einziges Hash-Verfahren verwendet wird (kein Migrationsbedarf von einem Alt-Hash-Verfahren).
- **JWT:** `PyJWT` (Modul `jwt`), Algorithmus **HS256** (symmetrisch, signiert mit dem bereits vorhandenen `settings.secret_key`). Kein `python-jose`: PyJWT hat die einfachere API für den hier benötigten Umfang (encode/decode, `exp`-Prüfung eingebaut) und wird aktiver gepflegt; asymmetrische Algorithmen (RS256 o.ä.) sind nicht nötig, da PhotoSort selbst sowohl Aussteller als auch einziger Prüfer der Tokens ist (kein Drittanbieter verifiziert JWTs).
- Token-Extraktion aus dem `Authorization`-Header nutzt FastAPIs eingebautes `fastapi.security.HTTPBearer` — keine weitere Abhängigkeit nötig.
- **Rate-Limiting:** `slowapi`, ausschließlich auf `POST /auth/login` (5 Versuche/Minute pro Client-IP, Zähler in Redis über `settings.redis_url`). Nötig geworden, weil PhotoSort laut Stakeholder-Entscheidung vom 2026-07-20 aus dem offenen Internet erreichbar ist (nicht nur LAN/VPN) — Argon2 allein bremst verteilte Brute-Force-Versuche nicht ausreichend (siehe `architecture/0003-securitykonzept.md`). Kein API-weites Limit, da einziger unauthentifizierter, rechenintensiver Endpunkt.

### Token-Transport: Bearer-Header + `localStorage`, keine Cookies

- Das JWT wird ausschließlich über den `Authorization: Bearer <token>`-Header übertragen, nie als Cookie gesetzt.
- Das Frontend speichert das Token in `localStorage` (nicht Memory-only, nicht `sessionStorage`).
- Damit entfällt CSRF strukturell: Browser hängen den `Authorization`-Header nie automatisch an fremdinitiierte Requests an (anders als bei Cookies) — die in Spec 0002/0005 aufgeschobene CSRF-Frage ist damit beantwortet: **kein CSRF-Schutzmechanismus nötig**, da kein Cookie-basierter Transport verwendet wird.

## Begründung

- **`localStorage` statt Memory-only:** Die Session-Dauer wurde bewusst auf ~30 Tage ohne Refresh-Mechanismus festgelegt (Stakeholder-Entscheidung, siehe Spec 0006). Ein rein speicherresidentes Token (State/Variable, kein Storage) würde bei jedem Neuladen der PWA — regulärer Vorgang bei einer installierten PWA — den Nutzer erneut zum Login zwingen und die 30-Tage-Session damit faktisch aushebeln. `localStorage` übersteht Reloads und App-Neustarts und passt damit zur bereits getroffenen Vereinfachung.
- **`localStorage` statt httpOnly-Cookie:** Ein httpOnly-Cookie wäre gegen XSS robuster, bringt aber CSRF-Schutzbedarf (`SameSite`, ggf. zusätzliches CSRF-Token) und — bei Frontend/Backend auf unterschiedlichen Origins (lokal: Vite-Dev-Server auf 5173, Backend auf 8000) — CORS-Komplexität durch `credentials: "include"` mit sich, die bei Bearer-Header komplett entfällt (keine `allow_credentials`-Notwendigkeit in der CORS-Konfiguration, die Spec 0005 ohnehin schon ergänzt). Das XSS-Risiko wird als vertretbar eingeschätzt: PhotoSort ist eine geschlossene Zwei-Nutzer-Anwendung ohne nutzergenerierten HTML-Inhalt und ohne Drittanbieter-Skripte — die typische Angriffsfläche für gespeichertes `localStorage`-Token-Diebstahl (injizierbarer fremder Content) existiert hier praktisch nicht. React escaped Ausgaben standardmäßig; `dangerouslySetInnerHTML` darf für nutzergenerierte Werte nicht verwendet werden (Konvention, vom `security-engineer` im Sicherheitskonzept zu verankern).
- **Konsistent mit ADR [0004](./0004-frontend-app-shell.md):** Diese hatte den Fetch-Wrapper (`api/client.ts`) bereits explizit als künftigen "Choke Point" für einen `Authorization`-Header vorgesehen ("Wenn die separate Auth-Spec später einen Authorization-Header/Token-Refresh braucht, wird das dort ergänzt") — keine Cookie-Übertragung. Diese ADR bestätigt und konkretisiert das nur.

## Konsequenzen

- Neue Backend-Abhängigkeiten: `argon2-cffi`, `PyJWT` (`backend/pyproject.toml`).
- `settings.secret_key` (bisher ungenutzt) wird produktiv für JWT-Signing verwendet — muss in Produktion zwingend über die Umgebungsvariable überschrieben werden (bereits als Hinweis in `.env.example` vorhanden, `README.md` wird ergänzt).
- Kein CSRF-Schutzmechanismus in Spec 0002/0005 nötig; beide Specs können ihre entsprechende offene Frage als durch diese ADR beantwortet schließen.
- XSS wird durch diese Entscheidung zum relevantesten Angriffsvektor auf die Session (Token-Diebstahl aus `localStorage`) — als Konvention festzuhalten im Sicherheitskonzept (`specs/architecture/0003-securitykonzept.md`, `security-engineer`): kein `dangerouslySetInnerHTML` mit nutzergenerierten/externen Werten.
- Kein Token-Refresh, keine serverseitige Widerrufbarkeit einzelner Tokens vor Ablauf (Konsequenz aus der bereits in ADR 0003/Spec 0006 getroffenen Entscheidung gegen Refresh-Tokens, nicht neu durch diese ADR) — bei Bedarf (z.B. kompromittiertes Gerät) künftig eigenes Thema (Token-Blocklist o.ä.), aktuell kein Ziel.
