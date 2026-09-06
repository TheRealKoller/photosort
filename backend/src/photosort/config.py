from typing import Literal

from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from photosort.cloud_vision import (
    VISION_MODELS_BY_PROVIDER,
    default_vision_model_for_provider,
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://photosort:photosort@localhost:5432/photosort"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "change-me"
    opencloud_base_url: str = ""
    opencloud_username: str = ""
    opencloud_app_token: str = ""
    opencloud_drive_name: str = ""

    # Lokaler Verarbeitungs-Cache fuer Thumbnails (specs/features/0002-manual-categorization.md),
    # ueber das "photo_cache"-Docker-Volume auf backend/worker gemountet (docker-compose.yml).
    photo_cache_dir: str = "/data/photo-cache"

    # Initiale Benutzerkonten fuer die Seed-Migration (specs/features/0006-auth.md). Die
    # Usernamen-Platzhalter sind bewusst unterschiedlich: identische Defaults wuerden bei
    # unveraendertem .env dazu fuehren, dass die idempotente Seed-Migration nur EINEN statt
    # zwei Accounts anlegt (seed_user() findet den zweiten Username bereits vor und ueberspringt
    # ihn still, siehe seed.py).
    auth_seed_user1_username: str = "change-me"
    auth_seed_user1_password: str = "change-me"
    auth_seed_user2_username: str = "change-me-2"
    auth_seed_user2_password: str = "change-me"

    # Storage-Backend fuer das Login-Rate-Limiting (slowapi). Leer = redis_url wird
    # wiederverwendet (Produktion, siehe decisions/0005-auth-implementation.md - "kein neuer
    # Infrastruktur-Baustein"). Nur zu Testzwecken auf z.B. "memory://" ueberschreibbar, damit
    # die Testsuite ohne echtes Redis auskommt (siehe architecture/0002-testkonzept.md).
    rate_limit_storage_uri: str = ""

    def resolved_rate_limit_storage_uri(self) -> str:
        return self.rate_limit_storage_uri or self.redis_url

    # Erlaubte Frontend-Origins fuer CORS (specs/features/0005-minimal-project-frontend.md,
    # architecture/0003-securitykonzept.md) - komma-getrennt, kein Wildcard "*". Defaults decken
    # lokale Entwicklung ab (Vite-Dev-Server auf 5173, das ueber docker-compose gebaute
    # nginx-Frontend auf FRONTEND_PORT-Default 8080); in Produktion ueber CORS_ALLOWED_ORIGINS
    # auf die tatsaechliche(n) Frontend-Origin(s) setzen.
    cors_allowed_origins: str = "http://localhost:5173,http://localhost:8080"

    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    # Feature-Flag fuer die lokale Kriterien-Bewertung + Kategorie-Kuratierung
    # (urspruenglich specs/features/0024-top-photo-selection-category-mix.md, seit
    # specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md bewusst unter demselben
    # Namen weiterverwendet fuer POST /classify - keine funktionale Aenderung des Flags
    # selbst, nur ein neuer Endpunkt dahinter). Default AN (anders als ein Cloud-Feature): rein
    # lokale/kostenlose Verarbeitung, kein Grund fuer einen restriktiven Default.
    category_selection_enabled: bool = True

    # Obergrenze fuer die begrenzte Parallelisierung von Download + Thumbnail-Erzeugung in Phase 2b
    # des Scans (specs/features/0036-scan-performance-zweiphasig-parallel.md, ADR 0020). Echter
    # Betriebsparameter (Ueberlastschutz fuer den Einzelnutzer-Homeserver-OpenCloud), deshalb ein
    # env-ueberschreibbares Settings-Feld statt einer reinen Modul-Konstante wie
    # worker.py::SCAN_COMMIT_BATCH_SIZE (das ist reiner Test-Kalibrierungswert). Default 4:
    # spuerbare Parallelisierung gegenueber dem bisherigen strikt seriellen Ablauf, ohne den Server
    # mit Dutzenden gleichzeitigen Downloads zu fluten. `Field(ge=1)` (test-engineer-/security-
    # engineer-Review-Fund): faellt bei einer fehlerhaften .env-Konfiguration (0/negativ) bereits
    # beim Prozessstart auf, statt sich erst mitten im naechsten Scan-Lauf als range(step=0)-Crash
    # zu aeussern - worker.py verlaesst sich seitdem direkt auf diesen validierten Wert, ohne
    # eigenen Laufzeit-Clamp.
    scan_download_concurrency: int = Field(default=4, ge=1)

    # Obergrenze fuer die begrenzte Parallelisierung der pro-Unterordner-Bilddatei-Zaehlung im
    # Ordner-Browser (specs/features/0050-dateianzahl-im-ordner-browser.md, ADR
    # decisions/0028-ordner-browser-bilddatei-zaehlung.md). Echter Betriebsparameter
    # (Ueberlastschutz fuer den Einzelnutzer-Homeserver-OpenCloud bei parallelen
    # Zaehl-Traversierungen mehrerer Unterordner), deshalb analog scan_download_concurrency ein
    # env-ueberschreibbares Settings-Feld statt einer reinen Modul-Konstante wie
    # api/opencloud.py::FOLDER_COUNT_LIMIT (das ist reiner Anzeige-/UX-Wert ohne Tuning-Bedarf).
    # Default 4, `Field(ge=1)` faellt bei fehlerhafter .env-Konfiguration bereits beim
    # Prozessstart auf statt sich erst als Semaphore(0)-Deadlock zu aeussern.
    opencloud_folder_count_concurrency: int = Field(default=4, ge=1)

    # Erste tatsaechlich produktive Cloud-Abhaengigkeit im Kriterien-Scoring-Pfad
    # (specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md, decisions/0025-cloud-
    # landmark-erkennung.md) - exakt das opencloud_app_token-Muster (Secret nur ueber Env-Variable,
    # nie eingecheckt), kein Format-Check. Der ".env.example"-Platzhalter existierte bereits (aus
    # einem nie umgesetzten frueheren Cloud-Entwurf, ADR-0015-Kontext), war aber nie in Settings
    # verdrahtet - wird jetzt fuer einen echten, neuen Zweck reaktiviert.
    anthropic_api_key: str = ""

    # Obergrenze fuer die begrenzte Parallelisierung der Anthropic-Vision-Aufrufe in
    # run_criterion_scoring (ADR 0025 Punkt 3) - bewusst deutlich konservativer als
    # scan_download_concurrency (Default 4): reales Geld pro Anfrage und ein fremdes Rate-Limit,
    # nicht nur ein selbst betriebener OpenCloud-Server. `Field(ge=1)` faellt bei einer
    # fehlerhaften .env-Konfiguration bereits beim Prozessstart auf, analog den beiden
    # Concurrency-Feldern oben.
    landmark_api_concurrency: int = Field(default=2, ge=1)

    # Zweite, waehlbare Cloud-Provider-Option fuer das landmark-Kriterium
    # (specs/features/0054-mistral-provider-option-cloud-landmark.md, decisions/0031-mistral-
    # provider-option-cloud-landmark.md Punkt 3) - reine Betreiber-/Deployment-Entscheidung, kein
    # Project-Feld/Runtime-Selektor. `Literal` statt Enum (Minimalismus-Prinzip ADR 0006,
    # analog scan_download_concurrency-Field(ge=1) oben): pydantic validiert einen nicht
    # unterstuetzten .env-Wert bereits beim Prozessstart (ValidationError), kein stiller Fallback.
    landmark_provider: Literal["anthropic", "mistral"] = "anthropic"

    # specs/features/0304-cloud-modell-je-anbieter-waehlbar.md, decisions/0059-modellwahl-je-
    # anbieter-und-modellgebundene-kostenschaetzung.md Punkt 1: die zweite Betriebseinstellung
    # neben der Anbieterwahl - WELCHES Modell des eingestellten Anbieters benutzt wird. Leer
    # heisst "Voreinstellung des eingestellten Anbieters" (erstes Element seiner Registry), NICHT
    # "kein Modell": ohne gesetzten Wert verhaelt sich die Installation exakt wie vor dieser Spec.
    #
    # Der Name erbt bewusst die Ungenauigkeit von `landmark_provider` daneben (beide gelten fuer
    # BEIDE Cloud-Anteile - Sehenswuerdigkeits-Erkennung UND Kategorie-Vorschlaege, nicht nur fuer
    # landmark): die Zusammengehoerigkeit des Schalterpaars `LANDMARK_PROVIDER`/`LANDMARK_MODEL`
    # wiegt schwerer als die Wortgenauigkeit, und ein Umbenennen von `LANDMARK_PROVIDER` waere
    # eine fuer diese Story sachfremde, fuer den Betrieb breaking Aenderung (ADR 0059 Punkt 1).
    #
    # `str` + Validator statt `Literal`, anders als bei landmark_provider: die zulaessigen Werte
    # haengen vom eingestellten Anbieter ab, das laesst sich in einem Feld-`Literal` nicht
    # ausdruecken. Die Startvalidierung unten liefert dafuer dieselbe Zusicherung.
    landmark_model: str = ""

    def resolved_landmark_model(self) -> str:
        """Das tatsaechlich zu verwendende Modell (Muster `resolved_rate_limit_storage_uri()`).

        EINMAL je Cloud-Phase aufzurufen und der Wert dann durchzureichen (ADR 0059 Punkt 7) -
        Client-Bau, Kostenrechnung und Modellspalte des Laufs muessen strukturell denselben Wert
        benutzen, nicht drei zufaellig uebereinstimmende Lesevorgaenge derselben globalen
        `settings`."""
        return self.landmark_model or default_vision_model_for_provider(self.landmark_provider)

    @field_validator("landmark_model")
    @classmethod
    def _check_landmark_model_is_offered_by_the_provider(
        cls, value: str, info: ValidationInfo
    ) -> str:
        """Akzeptanzkriterium: ein Wert ausserhalb der gepflegten Auswahl fuehrt zu einer
        verstaendlichen Fehlermeldung BEIM START; die Anwendung startet dann nicht, statt mitten
        in einem laufenden - kostenpflichtigen - Durchgang still fehlzuschlagen. Wegen
        `settings = Settings()` auf Modulebene ist das der Prozessstart, dasselbe Verhalten, das
        `landmark_provider` ueber sein `Literal` schon hat ("kein stiller Fallback").

        Geprueft wird gegen die Registry DES EINGESTELLTEN ANBIETERS: ein fuer Anthropic gueltiges
        Modell unter `mistral` ist ebenfalls ein Startfehler - sonst waere es ein Aufruf, den der
        Anbieter erst zur Laufzeit ablehnt, mitten im kostenpflichtigen Durchgang.

        FELD-VALIDATOR, NICHT `model_validator(mode="after")` (Security-Muss-Kriterium der Spec
        0304, Befund `security-engineer` 2026-09-06, am Branch nachgemessen): pydantic haengt an
        eine `ValidationError` die Eingabe an, an der die Pruefung scheiterte. Bei einem
        Modell-Validator ist das das VOLLSTAENDIGE Settings-Dict - und damit landen `SECRET_KEY`,
        `ANTHROPIC_API_KEY`, `MISTRAL_API_KEY` und `OPENCLOUD_APP_TOKEN` im Startup-Traceback
        (`docker compose logs`) und in `exc.errors()`/`exc.json()`. Beim Feld-Validator ist die
        Eingabe nur der beanstandete Modellwert selbst. Das verletzte sonst direkt den
        CLAUDE.md-Grundsatz "keine Secrets in Logs oder Fehlermeldungen".

        `landmark_model` ist hinter `landmark_provider` deklariert, deshalb steht der Anbieter in
        `info.data`. Fehlt er dort, ist er selbst ungueltig - dann bricht der Start ohnehin an
        seinem eigenen Feldfehler ab, und eine zweite Meldung hier hilft niemandem."""
        if not value:
            return value
        provider = info.data.get("landmark_provider")
        if provider is None:
            return value
        allowed = VISION_MODELS_BY_PROVIDER.get(provider, ())
        if value not in allowed:
            # Bewusst enthalten: der beanstandete Wert, der eingestellte Anbieter und die
            # zulaessigen Werte - Modell-IDs sind keine Geheimnisse (die Registry liegt im
            # oeffentlichen Repository), und der Betreiber soll handlungsfaehig sein.
            raise ValueError(
                f"LANDMARK_MODEL={value!r} ist fuer LANDMARK_PROVIDER={provider!r} nicht "
                f"waehlbar. Erlaubt sind: {', '.join(allowed)} (oder leer lassen fuer die "
                f"Voreinstellung {default_vision_model_for_provider(provider)})."
            )
        return value

    # Exakt das anthropic_api_key-Muster (Secret nur ueber Env-Variable, nie eingecheckt, kein
    # Format-Check) - der Wert wird wie jedes andere Settings-Feld beim Prozessstart eingelesen,
    # aber nur verwendet (build_landmark_client()), wenn landmark_provider == "mistral".
    mistral_api_key: str = ""

    # Obergrenze fuer die begrenzte Parallelisierung der Remote-Kategorie-Klassifizierungs-Cloud-
    # Aufrufe (specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md,
    # decisions/0032 Punkt 5) - analog landmark_api_concurrency (Default 2, konservativer als
    # scan_download_concurrency: reales Geld pro Anfrage und ein fremdes Rate-Limit). Eigenes,
    # neues Setting statt Wiederverwendung von landmark_api_concurrency - ein eigenstaendiger Job
    # mit eigener Kandidatenmenge (kompletter Ausschuss-Bestand statt eines Vorfilter-Ergebnisses),
    # soll unabhaengig voneinander tunbar bleiben. `Field(ge=1)` analog den uebrigen Concurrency-
    # Feldern.
    remote_category_classification_concurrency: int = Field(default=2, ge=1)


settings = Settings()
