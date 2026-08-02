# 0010 - Explizites IPv4-only Docker-Netzwerk

**Status:** Implemented ([PR #15](https://github.com/TheRealKoller/photosort/pull/15))
**Erstellt:** 2026-08-02
**Akzeptiert:** 2026-08-02
**Implementiert:** 2026-08-02, Feature-Branch `feature/0010-ipv4-only-network`
**Bezug:** Idea-Sharpening-Gespräch mit Daniel im Chat, 2026-08-02. Vorbedingung/Vorarbeit für die künftige Anbindung des externen Deploy-Tools "Dockhand" (siehe Spec/ADR [`0007`](./0007-github-repo-access-hardening.md)), analog zu dessen Teil 1 — anderes technisches Problem, gemeinsamer Auslöser.

## Ziel

Damit das externe Deploy-Tool "Dockhand" (Daniel testet es aktuell experimentell) den PhotoSort-Compose-Stack zuverlässig auf- und abbauen kann, soll `docker-compose.yml` (Root) ein explizites, IPv4-only Docker-Netzwerk definieren statt sich auf das automatisch angelegte Default-Netzwerk von Docker Compose zu verlassen. Dessen automatisch aktiviertes IPv6 führt bei Dockhand laut Daniel zu Netzwerken, die sich nicht sauber löschen lassen.

## User Story

Als Betreiber, der PhotoSort über Dockhand deployt, möchte ich, dass der Compose-Stack ein explizit definiertes, IPv4-only Netzwerk verwendet, damit Dockhand Deployments zuverlässig durchführen kann, ohne an automatisch angelegten, nicht löschbaren IPv6-Netzwerken zu scheitern.

## Akzeptanzkriterien

- [ ] `docker compose config -q` (bestehender CI-Job `docker-compose-check`) validiert `docker-compose.yml` weiterhin fehlerfrei inkl. neuem `networks`-Block.
- [ ] Nach `docker compose up -d` existiert genau ein Netzwerk für den Stack; `docker network inspect <name> --format '{{.EnableIPv6}}'` liefert `false`.
- [ ] `docker network inspect <name> --format '{{.Driver}}'` liefert `bridge`.
- [ ] Alle 5 Services (postgres, redis, backend, worker, frontend) erreichen sich weiterhin gegenseitig per Servicename (Regressionscheck: `backend` erreicht `postgres:5432`/`redis:6379`, Migrationen laufen durch) — IPv4-only darf nichts brechen.
- [ ] `docker compose down` entfernt das Netzwerk vollständig (`docker network ls` listet es danach nicht mehr) — direkter, mit Docker-CLI prüfbarer Indikator für das eigentliche Dockhand-Problem, ohne Dockhand selbst zu benötigen.
- [ ] Der geplante Service `opencloud-demo` aus dem `docker-compose.demo.yml`-Overlay (Spec 0009, noch nicht implementiert) deklariert kein eigenes `networks:` und tritt damit automatisch demselben `default`-Netzwerk bei.
- [ ] Manuell verifiziert (`ss -tlnp`/`docker port` auf dem Host nach `docker compose up -d`), ob für `BACKEND_PORT`/`FRONTEND_PORT` weiterhin ein IPv6-Host-Listener existiert — Ergebnis wird in `architecture/0003-securitykonzept.md` als tatsächlich verifizierter Wert nachgetragen (siehe Security-Abschnitt, aktuell nicht belastbar zugesichert).

## Datenmodell-Bezug

Keines. Reine Infrastruktur-/Deploy-Konfiguration, kein Anwendungscode, kein Datenmodell betroffen.

## Architektur / Umsetzung

**Ansatz:** `docker-compose.yml` (Root) erhält einen expliziten Top-Level-`networks:`-Block mit dem Schlüssel `default` (nicht ein neu benannter Netzwerkname), der IPv6 explizit deaktiviert:

```yaml
networks:
  default:
    driver: bridge
    enable_ipv6: false
```

Da der Schlüssel `default` heißt, hängen sich alle 5 bestehenden Services (`postgres`, `redis`, `backend`, `worker`, `frontend`) automatisch weiter an dieses Netzwerk — keiner von ihnen braucht ein eigenes `networks:`-Element, an den Service-Definitionen ändert sich sonst nichts. Kein `driver_opts`/Subnetz nötig; Docker vergibt weiterhin automatisch ein IPv4-Subnetz, nur die automatische IPv6-Aktivierung entfällt. Das ist die minimalinvasivste Umsetzung: das Netzwerk wird explizit konfiguriert (Treiber, IPv6 aus), bleibt aber technisch der Compose-Default-Slot — kein neuer Name hätte einen funktionalen Vorteil geboten, aber Änderungen an jedem einzelnen Service erzwungen.

**Betroffene Dateien:** ausschließlich `docker-compose.yml` (Root), ein zusätzlicher Top-Level-Block.

**Kompatibilität mit Spec 0009 (`docker-compose.demo.yml`):** Der dort geplante Service `opencloud-demo` definiert kein eigenes `networks:`, tritt also beim kombinierten Aufruf (`docker compose -f docker-compose.yml -f docker-compose.demo.yml up`) automatisch demselben `default`-Netzwerk bei wie die Basis-Services. `backend`/`worker` erreichen ihn weiterhin per Servicename (`http://opencloud-demo:9200`) — keine Anpassung an Spec 0009 nötig, bei deren Umsetzung aber explizit nachzuprüfen, dass kein eigener `networks:`-Key ergänzt wird.

**CI:** Der bestehende `docker-compose-check`-Job wird um einen funktionalen Netzwerk-Check erweitert (siehe Teststrategie) — reine `config -q`-Syntaxvalidierung deckt den neuen Block zwar ab, prüft aber nicht, ob Docker tatsächlich kein IPv6-Netzwerk mehr anlegt.

**ADR:** Keine neue ADR — reine technische Detailentscheidung ohne neue Technologie, ohne Datenmodell-Bezug, ohne externe Abhängigkeit; eine technische Wahl innerhalb der bereits von Daniel vorgegebenen Richtung.

**Nicht betroffen:** `specs/architecture/0001-overview.md` (dokumentiert keine Netzwerktopologie auf dieser Ebene) und `README.md` (kein neuer Setup-Schritt/Env-Var für Nutzer).

## UI/UX

Nicht relevant. Reine Docker-Netzwerkkonfiguration (ein `networks:`-Block in `docker-compose.yml`) ohne Berührung von Anwendungscode, Frontend oder Nutzerinteraktion.

## Security

Primär durch das Dockhand-Deploy-Problem motiviert, nicht durch einen Sicherheitsfund. `enable_ipv6: false` nimmt Containern im `default`-Netzwerk die IPv6-Adresse und ist tendenziell eher eine Reduktion der Angriffsfläche als eine Vergrößerung — ob es auch verhindert, dass für `BACKEND_PORT`/`FRONTEND_PORT` bei dual-stack-fähigen Docker-Hosts zusätzlich ein IPv6-Host-Listener entsteht, ist **nicht belastbar zugesichert**: Netzwerk-`enable_ipv6` (Container-seitige Adressvergabe) und Host-Port-Publishing (`ports:`) sind technisch unabhängige, versions-/konfigurationsabhängige Docker-Mechanismen. Bei der Umsetzung per `ss -tlnp`/`docker port` tatsächlich zu verifizieren statt hier als gesichert zu behaupten (siehe Akzeptanzkriterien). Die bestehende IPv4-Port-Bindung (ungebunden auf allen Interfaces, siehe `architecture/0003-securitykonzept.md`, Abschnitt "Docker-Compose-Netzwerk") bleibt in jedem Fall unverändert. Keine Auswirkung auf Auth, interne Container-Kommunikation (läuft über Docker-DNS/Servicenamen) oder bestehende Sicherheitsannahmen.

## Teststrategie

- Der bestehende `docker-compose-check`-CI-Job wird um einen funktionalen Check erweitert: `docker compose up -d postgres redis && docker network inspect ... && docker compose down` (kleine Alpine-Images, kein Image-Build, keine Secrets nötig) — deckt automatisiert ab, dass das Netzwerk tatsächlich `EnableIPv6: false`/`Driver: bridge` hat und beim `down` vollständig entfernt wird. Erster Fall eines *echten* (nicht nur Syntax-)Docker-Checks in CI für dieses Projekt.
- Ergänzend ein manueller Smoke-Test vor Merge (vollen Stack hochfahren, Servicename-Erreichbarkeit prüfen) für das Akzeptanzkriterium "alle 5 Services erreichen sich weiterhin" — analog zum etablierten Muster für Docker-Compose-Änderungen (`specs/architecture/0002-testkonzept.md`).
- Das tatsächliche Dockhand-Verhalten selbst (Drittanbieter-Tool) bleibt außerhalb der PR-Gate-Kriterien — Daniels eigene experimentelle Prüfung, nicht Teil dieses Merge-Kriteriums.
- **Edge Case:** Wer vorher schon `docker compose up` (mit altem, IPv6-fähigem Default-Netz) laufen hatte, bekommt beim Wechsel evtl. einen Compose-Konfliktfehler ("network already exists but was not created by compose"/Config-Mismatch) — vorher `docker compose down` nötig, im PR-Text erwähnen.
- `specs/architecture/0002-testkonzept.md` wird um eine kurze Ergänzung im Abschnitt "Backend" sowie in der Werkzeug-Tabelle (Spalte E2E/Smoke) erweitert — erster Fall eines funktionalen (nicht nur Syntax-)Docker-Compose-Checks in CI.

## Out of Scope

- Implementierung/Anbindung von Dockhand selbst (separate, künftige Spec, außerhalb dieses Repos) — keine Kopplung.
- Explizite Subnetz-Konfiguration (`driver_opts`, feste IP-Ranges) — automatische Subnetzvergabe reicht, kein bekanntes Kollisionsrisiko.
- Anpassung der Host-Firewall-Konfiguration (liegt bei Daniels Homeserver-Betrieb, außerhalb dieses Repos).
- Verifikation des tatsächlichen Dockhand-Verhaltens nach dem Fix (Daniels eigene experimentelle Prüfung, kein Merge-Kriterium dieser Spec).
